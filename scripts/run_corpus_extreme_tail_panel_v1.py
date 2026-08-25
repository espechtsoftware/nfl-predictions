#!/usr/bin/env python3
"""Prepare, execute, and finish the outcome-blind 54-slate T230 panel.

All remote writes are explicit ``--execute`` create-once publications.  The
command never lists a bucket or resolves a latest object: every read below the
prepared manifest is generation-pinned, and ``finish-panel`` requires the 54
ordered acceptance identities emitted by independent ``verify-slate`` runs.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Final, Protocol

from nfl_dfs.research import corpus_extreme_tail_panel_execution as execution
from nfl_dfs.research import corpus_extreme_tail_panel_release as manifest_contract
from nfl_dfs.research import corpus_parametric_batch as batch


WORKFLOW_RECEIPT_SCHEMA: Final = "foundry-t230-panel-workflow-receipt/v1"
_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
)
REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]


class CorpusExtremeTailPanelCLIError(RuntimeError):
    """The public T230 workflow cannot proceed without exact identities."""


class ExactCreateOnceStore(Protocol):
    def read(self, identity: Mapping[str, object]) -> bytes: ...

    def publish_create_once(
        self, uri: str, raw: bytes
    ) -> Mapping[str, object]: ...


def _fail(message: str) -> None:
    raise CorpusExtremeTailPanelCLIError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _parse_json(raw: bytes, *, label: str) -> dict[str, object]:
    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        body: dict[str, object] = {}
        for key, value in rows:
            if key in body:
                _fail(f"{label} contains duplicate key {key!r}")
            body[key] = value
        return body

    def reject_constant(value: str) -> object:
        _fail(f"{label} contains non-finite value {value}")

    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusExtremeTailPanelCLIError(
            f"{label} is not valid UTF-8 JSON"
        ) from exc
    return dict(_mapping(parsed, label=label))


def _load_local_json(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute() or path.name in {"", ".", ".."}:
        _fail(f"{label} path must be one absolute file path")
    _reject_symlink_components(path, label=label)
    try:
        if not path.is_file():
            _fail(f"{label} path must be a regular file")
        raw = path.read_bytes()
    except CorpusExtremeTailPanelCLIError:
        raise
    except OSError as exc:
        raise CorpusExtremeTailPanelCLIError(f"{label} read failed") from exc
    body = _parse_json(raw, label=label)
    canonical = batch.canonical_json_bytes(body)
    if raw not in {canonical, canonical + b"\n"}:
        _fail(f"{label} must contain canonical JSON with at most one newline")
    return body


def _identity_from_file(
    path: Path, *, envelope_field: str | None, label: str
) -> dict[str, object]:
    body = _load_local_json(path, label=label)
    value: object = body
    if envelope_field is not None and envelope_field in body:
        value = body[envelope_field]
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise CorpusExtremeTailPanelCLIError(
            f"{label} does not contain the required exact identity"
        ) from exc


def _exact_read_json(
    identity_value: Mapping[str, object],
    *,
    store: ExactCreateOnceStore,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        identity = batch.normalize_object_identity(identity_value, label=label)
    except Exception as exc:
        raise CorpusExtremeTailPanelCLIError(f"{label} identity differs") from exc
    raw = store.read(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact-read content differs")
    body = _parse_json(raw, label=label)
    if batch.canonical_json_bytes(body) != raw:
        _fail(f"{label} remote body is not canonical JSON")
    return identity, body


def _split_gcs_uri(value: object, *, label: str) -> tuple[str, str]:
    if type(value) is not str or not value.startswith("gs://"):
        _fail(f"{label} must be one explicit GCS object URI")
    bucket, separator, object_name = value[5:].partition("/")
    if (
        not separator
        or not bucket
        or not object_name
        or object_name.endswith("/")
        or "//" in object_name
    ):
        _fail(f"{label} must name one canonical GCS object")
    return bucket, object_name


def _collision_exceptions() -> tuple[type[BaseException], ...]:
    try:
        from google.api_core.exceptions import AlreadyExists, PreconditionFailed
    except ImportError as exc:  # pragma: no cover - production dependency gate
        raise CorpusExtremeTailPanelCLIError(
            "google-api-core is required for execute mode"
        ) from exc
    return (AlreadyExists, PreconditionFailed)


class GCSExactCreateOnceStore:
    """Generation-pinned reads and create-once writes; no list/latest API."""

    def __init__(
        self,
        client: object,
        *,
        collision_exceptions: tuple[type[BaseException], ...] | None = None,
    ) -> None:
        self._client = client
        self._collision_exceptions = (
            _collision_exceptions()
            if collision_exceptions is None
            else collision_exceptions
        )
        if not self._collision_exceptions:
            _fail("create-once collision exception set cannot be empty")

    def read(self, identity: Mapping[str, object]) -> bytes:
        try:
            retained = batch.normalize_object_identity(
                identity, label="GCS exact-read identity"
            )
        except Exception as exc:
            raise CorpusExtremeTailPanelCLIError(
                "GCS exact-read identity differs"
            ) from exc
        bucket_name, object_name = _split_gcs_uri(
            retained["uri"], label="GCS exact-read URI"
        )
        generation = int(str(retained["generation"]))
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        return blob.download_as_bytes(if_generation_match=generation)

    def _reopen_generation(
        self, uri: str, *, generation: int
    ) -> tuple[dict[str, object], bytes]:
        bucket_name, object_name = _split_gcs_uri(uri, label="output URI")
        if type(generation) is not int or generation < 1:
            _fail("published object lacks an exact positive generation")
        pinned = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        raw = pinned.download_as_bytes(if_generation_match=generation)
        return (
            {
                "uri": uri,
                "generation": str(generation),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
            raw,
        )

    def publish_create_once(
        self, uri: str, raw: bytes
    ) -> Mapping[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("create-once publication requires nonempty bytes")
        bucket_name, object_name = _split_gcs_uri(uri, label="output URI")
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
            )
        except self._collision_exceptions:
            _fail(
                "create-once collision requires a previously retained exact "
                "generation identity; current/latest lookup is forbidden"
            )
        if blob.generation is None:
            _fail("create response did not return an exact object generation")
        identity, retained = self._reopen_generation(
            uri, generation=int(blob.generation)
        )
        if retained != raw:
            _fail("newly published object differs on exact reopen")
        return identity


def _reject_symlink_components(path: Path, *, label: str) -> None:
    for component in (path, *path.parents):
        if component.is_symlink():
            _fail(f"{label} path cannot contain a symlink")


def _preflight_receipt_output(path: Path | None) -> None:
    if path is None:
        return
    if not path.is_absolute() or path.name in {"", ".", ".."}:
        _fail("receipt output must be one absolute file path")
    try:
        _reject_symlink_components(path, label="receipt output")
        path.parent.mkdir(parents=True, exist_ok=True)
        _reject_symlink_components(path, label="receipt output")
        if not path.parent.is_dir():
            _fail("receipt output parent must be a directory")
        if path.exists() and not path.is_file():
            _fail("receipt output target must be a regular file")
    except CorpusExtremeTailPanelCLIError:
        raise
    except OSError as exc:
        raise CorpusExtremeTailPanelCLIError(
            "receipt output preflight failed"
        ) from exc


def _write_receipt_create_once(
    path: Path | None, receipt: Mapping[str, object]
) -> None:
    if path is None:
        return
    raw = batch.canonical_json_bytes(dict(receipt)) + b"\n"
    try:
        _reject_symlink_components(path, label="receipt output")
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        try:
            _reject_symlink_components(path, label="receipt output")
            if not path.is_file() or path.read_bytes() != raw:
                _fail("create-once local receipt collision differs")
        except CorpusExtremeTailPanelCLIError:
            raise
        except OSError as exc:
            raise CorpusExtremeTailPanelCLIError(
                "create-once local receipt collision read failed"
            ) from exc
    except OSError as exc:
        raise CorpusExtremeTailPanelCLIError(
            "create-once local receipt write failed"
        ) from exc


def _git_head(repository_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CorpusExtremeTailPanelCLIError("measured Git HEAD failed") from exc
    try:
        return completed.stdout.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise CorpusExtremeTailPanelCLIError("measured Git HEAD is not ASCII") from exc


def _git_blob(repository_root: Path, commit: str, relative_path: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "show", f"{commit}:{relative_path}"],
            cwd=repository_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CorpusExtremeTailPanelCLIError(
            f"measured Git blob failed for {relative_path}"
        ) from exc
    return completed.stdout


def _git_status(repository_root: Path, relative_paths: Sequence[str]) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", *relative_paths],
            cwd=repository_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CorpusExtremeTailPanelCLIError(
            "critical-path Git status measurement failed"
        ) from exc
    return completed.stdout


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the exact outcome-blind Foundry T230 panel workflow"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    freeze_g0 = commands.add_parser("freeze-g0-authority")
    freeze_g0.add_argument("--receipt-output", type=Path)
    freeze_g0.add_argument("--execute", action="store_true", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--image-evidence-identity", required=True, type=Path)
    prepare.add_argument("--output-prefix", required=True)
    prepare.add_argument("--receipt-output", type=Path)
    prepare.add_argument("--execute", action="store_true", required=True)

    run_slate = commands.add_parser("run-slate")
    run_slate.add_argument("--execution-authority-identity", required=True, type=Path)
    run_slate.add_argument("--source-ordinal", required=True, type=int)
    run_slate.add_argument("--receipt-output", type=Path)
    run_slate.add_argument("--execute", action="store_true", required=True)

    verify_slate = commands.add_parser("verify-slate")
    verify_slate.add_argument("--execution-authority-identity", required=True, type=Path)
    verify_slate.add_argument("--source-ordinal", required=True, type=int)
    verify_slate.add_argument("--result-identity", required=True, type=Path)
    verify_slate.add_argument("--receipt-output", type=Path)
    verify_slate.add_argument("--execute", action="store_true", required=True)

    finish = commands.add_parser("finish-panel")
    finish.add_argument("--execution-authority-identity", required=True, type=Path)
    finish.add_argument(
        "--acceptance-identity",
        required=True,
        action="append",
        type=Path,
        help=(
            "direct identity or verify-slate receipt; provide exactly 54 in "
            "source-ordinal order"
        ),
    )
    finish.add_argument("--receipt-output", type=Path)
    finish.add_argument("--execute", action="store_true", required=True)
    return parser


def _workflow_receipt(operation: str, fields: Mapping[str, object]) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": WORKFLOW_RECEIPT_SCHEMA,
        "operation": operation,
        **dict(fields),
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["workflow_receipt_sha256"] = batch.canonical_sha256(body)
    return body


def _runtime_kwargs(
    *, store: ExactCreateOnceStore
) -> dict[str, object]:
    return {
        "read_exact": store.read,
        "repository_root": REPOSITORY_ROOT,
        "git_head": _git_head,
        "git_blob": _git_blob,
        "git_status": _git_status,
    }


def _write_g0_authority_lock_create_once(
    lock: Mapping[str, object],
) -> dict[str, object]:
    """Create the literal review lock without following any path component."""
    path = execution.FROZEN_G0_AUTHORITY_LOCK_PATH
    raw = batch.canonical_json_bytes(dict(lock)) + b"\n"
    if not path.is_absolute() or not hasattr(os, "O_NOFOLLOW"):
        _fail("literal G0 authority lock path is not no-follow capable")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    directory_fd: int | None = None
    file_fd: int | None = None
    try:
        directory_fd = os.open("/", directory_flags)
        for component in path.parts[1:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        try:
            file_fd = os.open(
                path.name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o644,
                dir_fd=directory_fd,
            )
        except FileExistsError:
            retained_raw, binding = execution._secure_read_regular_file(
                path, label="existing G0 authority lock"
            )
            if retained_raw != raw:
                _fail("create-once G0 authority lock collision differs")
            return binding
        os.fchmod(file_fd, 0o644)
        offset = 0
        while offset < len(raw):
            written = os.write(file_fd, raw[offset:])
            if written < 1:
                _fail("G0 authority lock write made no progress")
            offset += written
        os.fsync(file_fd)
        retained = os.fstat(file_fd)
        if (
            not stat.S_ISREG(retained.st_mode)
            or retained.st_nlink != 1
            or retained.st_uid != os.geteuid()
            or stat.S_IMODE(retained.st_mode) != 0o644
            or retained.st_size != len(raw)
        ):
            _fail("new G0 authority lock owner/mode/link checks failed")
    except CorpusExtremeTailPanelCLIError:
        raise
    except (OSError, execution.CorpusExtremeTailPanelExecutionError) as exc:
        raise CorpusExtremeTailPanelCLIError(
            "create-once G0 authority lock write failed"
        ) from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)
    retained_raw, binding = execution._secure_read_regular_file(
        path, label="new G0 authority lock"
    )
    if retained_raw != raw:
        _fail("new G0 authority lock differs after no-follow reopen")
    return binding


def _run_freeze_g0(
    _args: argparse.Namespace, *, store: ExactCreateOnceStore
) -> dict[str, object]:
    try:
        lock = execution.build_g0_authority_lock_v1(read_exact=store.read)
        replayed = execution.validate_g0_authority_lock_v1(
            lock, read_exact=store.read
        )
        binding = _write_g0_authority_lock_create_once(replayed)
    except Exception as exc:
        if isinstance(exc, CorpusExtremeTailPanelCLIError):
            raise
        raise CorpusExtremeTailPanelCLIError(str(exc)) from exc
    return _workflow_receipt("freeze-g0-authority", {
        "g0_authority_lock_file": binding,
        "g0_authority_lock_sha256": replayed["g0_authority_lock_sha256"],
        "panel_object_identity": replayed["panel_object_identity"],
        "panel_id": replayed["panel_id"],
        "review_and_git_commit_required_before_prepare": True,
        "tracked_at_head": False,
        "clean_at_head": False,
        "prepare_gate_passed": False,
        "local_lock_created": True,
    })


def _run_prepare(
    args: argparse.Namespace, *, store: ExactCreateOnceStore
) -> dict[str, object]:
    evidence_identity = _identity_from_file(
        args.image_evidence_identity,
        envelope_field="image_evidence_identity",
        label="image evidence identity",
    )
    try:
        receipt_binding, panel_receipt, panel_body, _lane_bindings, _g0_binding = (
            execution.replay_published_v12_panel_v1(
                repository_root=REPOSITORY_ROOT,
                read_exact=store.read,
                git_head=_git_head,
                git_blob=_git_blob,
                git_status=_git_status,
            )
        )
        environment = execution.measure_t230_runtime_v1(
            role="worker",
            output_prefix=args.output_prefix,
            repository_root=REPOSITORY_ROOT,
            image_evidence_identity=evidence_identity,
            read_exact=store.read,
            git_head=_git_head,
            git_blob=_git_blob,
            git_status=_git_status,
        )
        if environment["release_runtime_verified"] is not True:
            _fail("prepare runtime is mechanics-only")
        manifest = manifest_contract.build_t230_panel_execution_manifest_v1(
            panel_index=panel_body,
            panel_index_identity=panel_receipt["panel_object_identity"],
            source_commit_sha=environment["measured_source_commit_sha"],
            immutable_image=environment["immutable_image"],
            output_prefix=args.output_prefix,
        )
        replayed_manifest = manifest_contract.validate_t230_panel_execution_manifest_v1(
            manifest,
            panel_index=panel_body,
            panel_index_identity=panel_receipt["panel_object_identity"],
            source_commit_sha=environment["measured_source_commit_sha"],
            immutable_image=environment["immutable_image"],
            output_prefix=args.output_prefix,
        )
        manifest_identity = store.publish_create_once(
            execution.manifest_uri_for_output_prefix(args.output_prefix),
            batch.canonical_json_bytes(replayed_manifest),
        )
        authority = execution.build_t230_execution_authority_v1(
            manifest_identity=manifest_identity,
            image_evidence_identity=evidence_identity,
            **_runtime_kwargs(store=store),
        )
        authority_identity = store.publish_create_once(
            execution.authority_uri_for_output_prefix(args.output_prefix),
            batch.canonical_json_bytes(authority),
        )
        reopened = execution.reopen_t230_execution_authority_v1(
            execution_authority_identity=authority_identity,
            **_runtime_kwargs(store=store),
        )
    except Exception as exc:
        if isinstance(exc, CorpusExtremeTailPanelCLIError):
            raise
        raise CorpusExtremeTailPanelCLIError(str(exc)) from exc
    return _workflow_receipt("prepare", {
        "execution_authority_identity": authority_identity,
        "execution_authority_sha256": reopened["execution_authority_sha256"],
        "manifest_identity": manifest_identity,
        "manifest_id": reopened["manifest_id"],
        "execution_manifest_sha256": reopened["execution_manifest_sha256"],
        "panel_publication_receipt_binding": receipt_binding,
        "panel_object_identity": reopened["panel_object_identity"],
        "source_member_count": execution.AUTHORITATIVE_SLATE_COUNT,
        "source_commit_sha": reopened["source_commit_sha"],
        "immutable_image": reopened["immutable_image"],
        "output_prefix": args.output_prefix,
        "published": True,
        "exact_reopen_verified": True,
    })


def _publish_current_runtime(
    *,
    authority_identity: Mapping[str, object],
    role: str,
    source_ordinal: int | None,
    store: ExactCreateOnceStore,
) -> dict[str, object]:
    authority = execution.reopen_t230_execution_authority_v1(
        execution_authority_identity=authority_identity,
        **_runtime_kwargs(store=store),
    )
    measurement = execution.measure_t230_runtime_v1(
        role=role,
        output_prefix=str(authority["output_prefix"]),
        repository_root=REPOSITORY_ROOT,
        image_evidence_identity=authority["image_evidence_identity"],
        read_exact=store.read,
        git_head=_git_head,
        git_blob=_git_blob,
        git_status=_git_status,
    )
    if measurement["release_runtime_verified"] is not True:
        _fail(f"{role} process is mechanics-only and cannot execute")
    uri = execution.runtime_measurement_uri_for_output_prefix(
        str(authority["output_prefix"]),
        role=role,
        source_ordinal=source_ordinal,
    )
    return dict(store.publish_create_once(
        uri, batch.canonical_json_bytes(measurement)
    ))


def _run_slate(
    args: argparse.Namespace, *, store: ExactCreateOnceStore
) -> dict[str, object]:
    authority_identity = _identity_from_file(
        args.execution_authority_identity,
        envelope_field="execution_authority_identity",
        label="execution authority identity",
    )
    try:
        worker_runtime_identity = _publish_current_runtime(
            authority_identity=authority_identity,
            role="worker",
            source_ordinal=args.source_ordinal,
            store=store,
        )
        result = execution.execute_t230_panel_slate_v1(
            execution_authority_identity=authority_identity,
            worker_runtime_measurement_identity=worker_runtime_identity,
            source_ordinal=args.source_ordinal,
            **_runtime_kwargs(store=store),
        )
    except execution.CorpusExtremeTailPanelExecutionError as exc:
        raise CorpusExtremeTailPanelCLIError(str(exc)) from exc
    result_identity = store.publish_create_once(
        str(result["result_uri"]), batch.canonical_json_bytes(result)
    )
    return _workflow_receipt("run-slate", {
        "execution_authority_identity": authority_identity,
        "execution_authority_sha256": result["execution_authority_sha256"],
        "manifest_identity": result["manifest_identity"],
        "manifest_id": result["manifest_id"],
        "execution_manifest_sha256": result["execution_manifest_sha256"],
        "source_ordinal": args.source_ordinal,
        "slate_id": result["slate_id"],
        "worker_runtime_measurement_identity": worker_runtime_identity,
        "result_identity": result_identity,
        "t230_slate_result_sha256": result["t230_slate_result_sha256"],
        "terminal_acceptance_published": False,
        "published": True,
        "exact_reopen_verified": True,
    })


def _run_verify_slate(
    args: argparse.Namespace, *, store: ExactCreateOnceStore
) -> dict[str, object]:
    authority_identity = _identity_from_file(
        args.execution_authority_identity,
        envelope_field="execution_authority_identity",
        label="execution authority identity",
    )
    result_identity = _identity_from_file(
        args.result_identity,
        envelope_field="result_identity",
        label="nonterminal result identity",
    )
    try:
        verifier_runtime_identity = _publish_current_runtime(
            authority_identity=authority_identity,
            role="verifier",
            source_ordinal=args.source_ordinal,
            store=store,
        )
        acceptance = execution.verify_t230_panel_slate_v1(
            execution_authority_identity=authority_identity,
            source_ordinal=args.source_ordinal,
            result_identity=result_identity,
            verifier_runtime_measurement_identity=verifier_runtime_identity,
            **_runtime_kwargs(store=store),
        )
        acceptance_identity = store.publish_create_once(
            str(acceptance["acceptance_uri"]),
            batch.canonical_json_bytes(acceptance),
        )
        _, reopened = _exact_read_json(
            acceptance_identity,
            store=store,
            label="published T230 slate acceptance",
        )
        execution.validate_t230_slate_acceptance_v1(
            reopened,
            execution_authority_identity=authority_identity,
            source_ordinal=args.source_ordinal,
            **_runtime_kwargs(store=store),
        )
    except execution.CorpusExtremeTailPanelExecutionError as exc:
        raise CorpusExtremeTailPanelCLIError(str(exc)) from exc
    return _workflow_receipt("verify-slate", {
        "execution_authority_identity": authority_identity,
        "execution_authority_sha256": acceptance["execution_authority_sha256"],
        "manifest_identity": acceptance["manifest_identity"],
        "manifest_id": acceptance["manifest_id"],
        "execution_manifest_sha256": acceptance["execution_manifest_sha256"],
        "source_ordinal": args.source_ordinal,
        "slate_id": acceptance["slate_id"],
        "result_identity": result_identity,
        "verifier_runtime_measurement_identity": verifier_runtime_identity,
        "acceptance_identity": acceptance_identity,
        "t230_slate_result_sha256": acceptance["t230_slate_result_sha256"],
        "t230_slate_acceptance_sha256": acceptance[
            "t230_slate_acceptance_sha256"
        ],
        "support_observation": acceptance["support_observation"],
        "published": True,
        "exact_reopen_verified": True,
    })


def _run_finish(
    args: argparse.Namespace, *, store: ExactCreateOnceStore
) -> dict[str, object]:
    authority_identity = _identity_from_file(
        args.execution_authority_identity,
        envelope_field="execution_authority_identity",
        label="execution authority identity",
    )
    if len(args.acceptance_identity) != execution.AUTHORITATIVE_SLATE_COUNT:
        _fail("finish-panel requires exactly 54 acceptance identity files")
    acceptance_identities = [
        _identity_from_file(
            path,
            envelope_field="acceptance_identity",
            label=f"acceptance identity[{ordinal}]",
        )
        for ordinal, path in enumerate(args.acceptance_identity)
    ]
    try:
        finalizer_runtime_identity = _publish_current_runtime(
            authority_identity=authority_identity,
            role="verifier",
            source_ordinal=None,
            store=store,
        )
        release = execution.build_t230_panel_release_v1(
            execution_authority_identity=authority_identity,
            finalizer_runtime_measurement_identity=finalizer_runtime_identity,
            acceptance_identities=acceptance_identities,
            **_runtime_kwargs(store=store),
        )
    except execution.CorpusExtremeTailPanelExecutionError as exc:
        raise CorpusExtremeTailPanelCLIError(str(exc)) from exc
    release_identity = store.publish_create_once(
        str(release["panel_release_uri"]), batch.canonical_json_bytes(release)
    )
    _, reopened_release = _exact_read_json(
        release_identity, store=store, label="published T230 panel release"
    )
    try:
        replayed = execution.validate_t230_panel_release_v1(
            reopened_release,
            execution_authority_identity=authority_identity,
            finalizer_runtime_measurement_identity=finalizer_runtime_identity,
            acceptance_identities=acceptance_identities,
            **_runtime_kwargs(store=store),
        )
    except execution.CorpusExtremeTailPanelExecutionError as exc:
        raise CorpusExtremeTailPanelCLIError(str(exc)) from exc
    return _workflow_receipt("finish-panel", {
        "execution_authority_identity": authority_identity,
        "execution_authority_sha256": replayed["execution_authority_sha256"],
        "manifest_identity": replayed["manifest_identity"],
        "manifest_id": replayed["manifest_id"],
        "execution_manifest_sha256": replayed[
            "execution_manifest_sha256"
        ],
        "panel_release_identity": release_identity,
        "finalizer_runtime_measurement_identity": finalizer_runtime_identity,
        "t230_panel_release_sha256": replayed["t230_panel_release_sha256"],
        "accepted_slate_count": replayed["accepted_slate_count"],
        "fold_boundary": replayed["fold_boundary"],
        "final_fit_boundary": replayed["final_fit_boundary"],
        "joint_support_boundary_passed": replayed[
            "joint_support_boundary_passed"
        ],
        "source_commit_sha": replayed["source_commit_sha"],
        "immutable_image": replayed["immutable_image"],
        "published": True,
        "exact_reopen_verified": True,
    })


def run(
    argv: Sequence[str], *, store: ExactCreateOnceStore
) -> dict[str, object]:
    args = _parser().parse_args(list(argv))
    _preflight_receipt_output(args.receipt_output)
    if args.command == "freeze-g0-authority":
        receipt = _run_freeze_g0(args, store=store)
    elif args.command == "prepare":
        receipt = _run_prepare(args, store=store)
    elif args.command == "run-slate":
        receipt = _run_slate(args, store=store)
    elif args.command == "verify-slate":
        receipt = _run_verify_slate(args, store=store)
    elif args.command == "finish-panel":
        receipt = _run_finish(args, store=store)
    else:  # pragma: no cover - argparse owns this boundary
        _fail("unknown T230 workflow command")
    _write_receipt_create_once(args.receipt_output, receipt)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover - production dependency gate
        raise CorpusExtremeTailPanelCLIError(
            "google-cloud-storage is required for this command"
        ) from exc
    receipt = run(
        sys.argv[1:] if argv is None else argv,
        store=GCSExactCreateOnceStore(storage.Client()),
    )
    sys.stdout.buffer.write(batch.canonical_json_bytes(receipt) + b"\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
