#!/usr/bin/env python3
"""Default-off Cloud Run CLI for the Fantasy Points x SIS R6 ablation.

``build-request`` and ``validate`` are local and client-free.  ``task0`` is generation-pinned,
read-only and non-publishing.  ``task`` runs exactly one of 54 slate ordinals;
``collect`` reads their compact results and freezes the score-free root.
``grade`` is the only mode allowed to open the recognized outcome closure.
``grade-reopen`` replays the persisted derived grade and score-free terminal
without reopening the outcome source or live lease.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Final


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from nfl_dfs.research import (  # noqa: E402
    corpus_r6_matchup_batch_candidate_authority_v1 as batch_mechanics,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source  # noqa: E402
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_matchup_source_release_outer_candidate_authority_v3 as source_v3,
)
from nfl_dfs.research import paid_source_ablation_execution_v1 as execution  # noqa: E402
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_paid_source_discovery_matrix_freeze_v1 as matrix_freeze,
)
from nfl_dfs.research import paid_source_ablation_registry_v1 as registry  # noqa: E402
import run_corpus_r6_construction_allocation_grade_v1 as grade_runner  # noqa: E402


ENABLE_ENV: Final = "R6_PAID_SOURCE_FP_SIS_ENABLE"
ENABLE_VALUE: Final = "I_UNDERSTAND_FIXED_CORPUS_FP_SIS_ABLATION_V1"
OUTCOMES_ENV: Final = "R6_PAID_SOURCE_FP_SIS_OUTCOMES_ALLOWED"
CODE_SHA_ENV: Final = "CODE_SHA"
IMAGE_DIGEST_ENV: Final = "IMAGE_DIGEST"
IMAGE_SOURCE_SHA_ENV: Final = "IMAGE_SOURCE_COMMIT_SHA"
MAX_REQUEST_BYTES: Final = 16 * 1024 * 1024
GRADE_REQUEST_SCHEMA: Final = "corpus-r6-paid-source-fp-sis-grade-request/v1"
TERMINAL_REOPEN_REQUEST_SCHEMA: Final = (
    "corpus-r6-paid-source-fp-sis-terminal-reopen-request/v1"
)
GRADE_REOPEN_REQUEST_SCHEMA: Final = (
    "corpus-r6-paid-source-fp-sis-grade-reopen-request/v1"
)
SLATE_PUBLICATION_MANIFEST_SCHEMA: Final = (
    "corpus-r6-paid-source-fp-sis-slate-publication-manifest/v1"
)
CLOUD_RESULT_SCHEMA: Final = execution.TASK0_CLOUD_RESULT_SCHEMA
PREPARE_INPUT_SCHEMA: Final = (
    "corpus-r6-paid-source-fp-sis-prepare-input/v1"
)
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_BUILD_ID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_TASK0_EXECUTION = re.compile(r"atlas-cbc-32g-full-2023-w8-v1-[a-z0-9]{5}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IMAGE = re.compile(
    r"us-central1-docker\.pkg\.dev/nfl-predictions-503414/"
    r"nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}\Z"
)


class PaidSourceFpSisCliV1Error(RuntimeError):
    """The guarded paid-source executable contract differed."""


def _fail(message: str) -> None:
    raise PaidSourceFpSisCliV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PaidSourceFpSisCliV1Error("canonical JSON differs") from exc


def _read_json(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute():
        _fail(f"{label} path must be absolute")
    try:
        before = path.lstat()
    except OSError as exc:
        raise PaidSourceFpSisCliV1Error(f"{label} file is absent") from exc
    if (
        path.is_symlink() or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1 or not 1 <= before.st_size <= MAX_REQUEST_BYTES
    ):
        _fail(f"{label} must be one bounded unaliased regular file")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        _fail(f"{label} requires O_NOFOLLOW support")
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags | nofollow)
        opened = os.fstat(descriptor)
        raw = b""
        while len(raw) <= MAX_REQUEST_BYTES:
            chunk = os.read(
                descriptor, min(64 * 1024, MAX_REQUEST_BYTES + 1 - len(raw))
            )
            if not chunk:
                break
            raw += chunk
        after = os.fstat(descriptor)
    except OSError as exc:
        raise PaidSourceFpSisCliV1Error(f"{label} secure read failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    stable = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns")
    if (
        any(getattr(before, field) != getattr(opened, field) for field in stable)
        or any(getattr(opened, field) != getattr(after, field) for field in stable)
        or len(raw) != opened.st_size
        or not raw
        or len(raw) > MAX_REQUEST_BYTES
    ):
        _fail(f"{label} changed during its bounded read")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaidSourceFpSisCliV1Error(f"{label} JSON differs") from exc
    item = _mapping(value, label=label)
    if raw not in {_canonical(item), _canonical(item) + b"\n"}:
        _fail(f"{label} must be canonical JSON")
    return item


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"uri", "generation", "sha256", "bytes", "create_once"}:
        _fail(f"{label} identity fields differ")
    create_once = item.pop("create_once")
    if create_once is not True:
        _fail(f"{label} must be create-once")
    try:
        retained = source.normalize_object_identity_v2(item, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise PaidSourceFpSisCliV1Error(str(exc)) from exc
    return {**retained, "create_once": True}


class GCSExactCreateOnceAndFileStoreV1(
    grade_runner.GCSExactCreateOnceStoreV1
):
    """Generation-pinned small reads plus streaming exact matrix downloads."""

    def fetch_exact_to_file(
        self, identity_value: Mapping[str, object], destination: Path,
    ) -> None:
        item = _mapping(identity_value, label="matrix file identity")
        try:
            identity = source.normalize_object_identity_v2(
                item, label="matrix file identity"
            )
        except source.CorpusR6MatchupSourceV2Error as exc:
            raise PaidSourceFpSisCliV1Error(str(exc)) from exc
        path = Path(destination)
        if (
            not path.is_absolute()
            or path.exists()
            or path.is_symlink()
            or not path.parent.is_dir()
            or path.parent.is_symlink()
        ):
            _fail("matrix file destination differs")
        blob = self._blob(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        try:
            blob.reload(if_generation_match=generation)
            if (
                str(blob.generation) != str(identity["generation"])
                or int(blob.size) != identity["bytes"]
            ):
                _fail("matrix GCS metadata differs from exact identity")
            blob.download_to_filename(
                str(path), if_generation_match=generation
            )
        except Exception as exc:
            if path.exists() and path.is_file():
                path.unlink()
            raise PaidSourceFpSisCliV1Error(
                "matrix generation-exact file download failed"
            ) from exc
        digest = sha256()
        try:
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
            if (
                path.stat().st_size != identity["bytes"]
                or digest.hexdigest() != identity["sha256"]
            ):
                _fail("matrix generation-exact file bytes differ")
        except Exception:
            if path.exists() and path.is_file():
                path.unlink()
            raise


class ExactReadOnlyFileStoreViewV1:
    """Narrow task-0 adapter with no publication method or storage handle."""

    __slots__ = ("_read_exact", "_fetch_exact_to_file")

    def __init__(self, store: object) -> None:
        reader = getattr(store, "read_exact", None)
        fetcher = getattr(store, "fetch_exact_to_file", None)
        if not callable(reader) or not callable(fetcher):
            _fail("paid-source task0 read-only store differs")
        self._read_exact = reader
        self._fetch_exact_to_file = fetcher

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        return self._read_exact(identity)

    def fetch_exact_to_file(
        self, identity: Mapping[str, object], destination: Path,
    ) -> None:
        self._fetch_exact_to_file(identity, destination)


def _runtime_gate(
    *, request: Mapping[str, object], execute: bool,
    environment: Mapping[str, str], outcomes_allowed: bool,
    task_count: int = 1,
) -> int:
    code_sha = request.get("code_sha")
    image = request.get("immutable_image")
    digest = request.get("image_digest")
    if (
        execute is not True
        or environment.get(ENABLE_ENV) != ENABLE_VALUE
        or environment.get(OUTCOMES_ENV) != str(outcomes_allowed).lower()
        or type(code_sha) is not str
        or _COMMIT.fullmatch(code_sha) is None
        or environment.get(CODE_SHA_ENV) != code_sha
        or environment.get(IMAGE_SOURCE_SHA_ENV) != code_sha
        or type(digest) is not str
        or _DIGEST.fullmatch(digest) is None
        or environment.get(IMAGE_DIGEST_ENV) != digest
        or type(image) is not str
        or _IMAGE.fullmatch(image) is None
        or image.rsplit("@", 1)[1] != digest
    ):
        _fail("paid-source runtime enable/code/image/outcome gate differs")
    index = environment.get("CLOUD_RUN_TASK_INDEX")
    if (
        type(task_count) is not int
        or task_count not in {1, execution.TASK_COUNT}
        or type(index) is not str
        or not index.isdigit()
        or not 0 <= int(index) < task_count
        or environment.get("CLOUD_RUN_TASK_COUNT") != str(task_count)
        or environment.get("CLOUD_RUN_TASK_ATTEMPT") != "0"
    ):
        _fail("paid-source execution task lattice/first attempt differs")
    return int(index)


def _default_store() -> GCSExactCreateOnceAndFileStoreV1:
    return GCSExactCreateOnceAndFileStoreV1()


def _matrix_registry_reopener(**kwargs: object) -> object:
    return matrix_freeze.reopen_terminal_registry_v1(**kwargs)


def _source_reopener(
    *, request: Mapping[str, object], read_exact: object,
) -> object:
    root = batch_mechanics._trusted_repository_root_v1()

    def reopen(ordinal: int) -> Mapping[str, object]:
        return source_v3.reopen_matchup_source_release_outer_candidate_authority_ordinal_v3(
            release_identity=request["source_v3_release_identity"],
            source_task_ordinal=ordinal,
            repository_root=root,
            read_exact=read_exact,
            git_head=batch_mechanics._trusted_git_head_v1,
            git_blob=batch_mechanics._trusted_git_blob_v1,
            git_status=batch_mechanics._trusted_git_status_v1,
        )

    return reopen


def _terminal_reopen_request(value: object) -> dict[str, object]:
    item = _mapping(value, label="terminal reopen request")
    if set(item) != {
        "schema_version", "terminal_identity", "terminal_sha256",
        "code_sha", "immutable_image", "image_digest",
    } or item.get("schema_version") != TERMINAL_REOPEN_REQUEST_SCHEMA:
        _fail("terminal reopen request fields differ")
    _identity(item["terminal_identity"], label="terminal reopen identity")
    if not registry.is_sha256(item.get("terminal_sha256")):
        _fail("terminal reopen SHA differs")
    return item


def _grade_request(value: object) -> dict[str, object]:
    item = _mapping(value, label="grade request")
    if set(item) != {
        "schema_version", "terminal_identity", "terminal_sha256", "grade_id",
        "outcome_authority_identity", "code_sha", "immutable_image",
        "image_digest",
    } or item.get("schema_version") != GRADE_REQUEST_SCHEMA:
        _fail("grade request fields differ")
    _identity(item["terminal_identity"], label="grade terminal identity")
    if not registry.is_sha256(item.get("terminal_sha256")):
        _fail("grade terminal SHA differs")
    return item


def _grade_reopen_request(value: object) -> dict[str, object]:
    item = _mapping(value, label="grade reopen request")
    if set(item) != {
        "schema_version", "grade_identity", "code_sha", "immutable_image",
        "image_digest",
    } or item.get("schema_version") != GRADE_REOPEN_REQUEST_SCHEMA:
        _fail("grade reopen request fields differ")
    _identity(item["grade_identity"], label="grade reopen identity")
    return item


def _slate_publication_manifest(value: object) -> list[dict[str, object]]:
    item = _mapping(value, label="slate publication manifest")
    if set(item) != {
        "schema_version", "slate_publications",
        "slate_publication_manifest_sha256",
    } or item.get("schema_version") != SLATE_PUBLICATION_MANIFEST_SCHEMA:
        _fail("slate publication manifest fields differ")
    values = item.get("slate_publications")
    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Sequence)
        or len(values) != execution.TASK_COUNT
        or item.get("slate_publication_manifest_sha256")
        != registry.canonical_sha256(values)
    ):
        _fail("slate publication manifest differs")
    return [
        _mapping(value, label=f"slate publication[{ordinal}]")
        for ordinal, value in enumerate(values)
    ]


def _build_execution_request(
    value: object, *, code_sha: str, immutable_image: str, build_id: str,
) -> dict[str, object]:
    """Build the public execution request from one typed, score-free input."""

    item = _mapping(value, label="paid-source prepare input")
    expected_fields = {
        "schema_version", "run_id", "frozen_at",
        "source_v3_release_identity",
        "discovery_matrix_freeze_terminal_identity",
        "runtime_build_attestation_identity",
    }
    if (
        set(item) != expected_fields
        or item.get("schema_version") != PREPARE_INPUT_SCHEMA
    ):
        _fail("paid-source prepare input fields differ")
    return execution.build_fp_sis_execution_request_v1(
        run_id=item.get("run_id"),
        frozen_at=item.get("frozen_at"),
        source_v3_release_identity=item.get("source_v3_release_identity"),
        discovery_matrix_freeze_terminal_identity=item.get(
            "discovery_matrix_freeze_terminal_identity"
        ),
        code_sha=code_sha,
        immutable_image=immutable_image,
        build_id=build_id,
        runtime_build_attestation_identity=item.get(
            "runtime_build_attestation_identity"
        ),
    )


def validate_cloud_task0_launch_gate_v1(
    *,
    request_value: object,
    cloud_result_value: object,
    request_file_sha256: str,
    code_sha: str,
    immutable_image: str,
    build_id: str,
    task0_execution: str,
) -> dict[str, object]:
    """Bind a full-cohort launch to one exact terminal task-0 execution."""

    request = execution.validate_fp_sis_execution_request_v1(request_value)
    try:
        result = execution.validate_fp_sis_task0_provider_gate_v1(
            cloud_result_value, request_value=request
        )
    except execution.PaidSourceAblationExecutionV1Error as exc:
        raise PaidSourceFpSisCliV1Error(
            "paid-source exact terminal task0 cloud launch gate differs"
        ) from exc
    execution_row = result["execution"]
    if (
        type(request_file_sha256) is not str
        or not registry.is_sha256(request_file_sha256)
        or type(code_sha) is not str
        or _COMMIT.fullmatch(code_sha) is None
        or type(immutable_image) is not str
        or _IMAGE.fullmatch(immutable_image) is None
        or type(build_id) is not str
        or _BUILD_ID.fullmatch(build_id) is None
        or type(task0_execution) is not str
        or _TASK0_EXECUTION.fullmatch(task0_execution) is None
        or result.get("code_sha") != code_sha
        or result.get("cloud_build_id") != build_id
        or result.get("provider_resolved_image") != immutable_image
        or result.get("request_sha256") != request_file_sha256
        or execution_row.get("name") != task0_execution
    ):
        _fail("paid-source exact terminal task0 cloud launch gate differs")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build_request = commands.add_parser("build-request")
    build_request.add_argument("--input", type=Path, required=True)
    build_request.add_argument("--code-sha", required=True)
    build_request.add_argument("--immutable-image", required=True)
    build_request.add_argument("--build-id", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--request", type=Path, required=True)
    cloud_gate = commands.add_parser("validate-task0-cloud-gate")
    cloud_gate.add_argument("--request", type=Path, required=True)
    cloud_gate.add_argument("--cloud-result", type=Path, required=True)
    cloud_gate.add_argument("--request-file-sha256", required=True)
    cloud_gate.add_argument("--code-sha", required=True)
    cloud_gate.add_argument("--immutable-image", required=True)
    cloud_gate.add_argument("--build-id", required=True)
    cloud_gate.add_argument("--task0-execution", required=True)
    task0 = commands.add_parser("task0")
    task0.add_argument("--request", type=Path, required=True)
    task0.add_argument("--execute", action="store_true")
    task = commands.add_parser("task")
    task.add_argument("--request", type=Path, required=True)
    task.add_argument("--task0-receipt", type=Path, required=True)
    task.add_argument("--task0-provider-gate", type=Path, required=True)
    task.add_argument("--execute", action="store_true")
    collect = commands.add_parser("collect")
    collect.add_argument("--request", type=Path, required=True)
    collect.add_argument("--task0-receipt", type=Path, required=True)
    collect.add_argument("--task0-provider-gate", type=Path, required=True)
    collect.add_argument("--slate-publications", type=Path, required=True)
    collect.add_argument("--execute", action="store_true")
    reopen = commands.add_parser("reopen")
    reopen.add_argument("--request", type=Path, required=True)
    reopen.add_argument("--execute", action="store_true")
    grade_parser = commands.add_parser("grade")
    grade_parser.add_argument("--request", type=Path, required=True)
    grade_parser.add_argument("--execute", action="store_true")
    grade_reopen = commands.add_parser("grade-reopen")
    grade_reopen.add_argument("--request", type=Path, required=True)
    grade_reopen.add_argument("--execute", action="store_true")
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    read_store: object | None = None,
    write_store: object | None = None,
    lease_verifier_factory: object | None = None,
) -> dict[str, object]:
    args = _parser().parse_args(argv)
    environment = dict(os.environ if environ is None else environ)
    if args.command == "build-request":
        return _build_execution_request(
            _read_json(args.input, label="paid-source prepare input"),
            code_sha=args.code_sha,
            immutable_image=args.immutable_image,
            build_id=args.build_id,
        )
    request = _read_json(args.request, label=f"{args.command} request")
    if args.command == "validate":
        return execution.validate_fp_sis_execution_request_v1(request)
    if args.command == "validate-task0-cloud-gate":
        return validate_cloud_task0_launch_gate_v1(
            request_value=request,
            cloud_result_value=_read_json(
                args.cloud_result, label="task0 cloud result"
            ),
            request_file_sha256=args.request_file_sha256,
            code_sha=args.code_sha,
            immutable_image=args.immutable_image,
            build_id=args.build_id,
            task0_execution=args.task0_execution,
        )

    outcomes_allowed = args.command in {"grade", "grade-reopen"}
    task_count = execution.TASK_COUNT if args.command == "task" else 1
    task_index = _runtime_gate(
        request=request, execute=args.execute, environment=environment,
        outcomes_allowed=outcomes_allowed,
        task_count=task_count,
    )
    if args.command in {"task0", "task", "collect"}:
        validated = execution.validate_fp_sis_execution_request_v1(request)
        retained_store = (
            read_store if args.command == "task0" and read_store is not None
            else write_store if write_store is not None
            else _default_store()
        )
        if args.command == "task0":
            retained_store = ExactReadOnlyFileStoreViewV1(retained_store)
        reader = getattr(retained_store, "read_exact", None)
        fetcher = getattr(retained_store, "fetch_exact_to_file", None)
        if not callable(reader):
            _fail("paid-source exact read store differs")
        if args.command in {"task0", "task"} and not callable(fetcher):
            _fail("paid-source streaming matrix store differs")
        source_reopener = _source_reopener(
            request=validated, read_exact=reader
        )
        work_root = Path(
            environment.get("R6_PAID_SOURCE_MATRIX_WORK_ROOT", "/tmp")
        )
        if not work_root.is_absolute() or work_root.is_symlink():
            _fail("paid-source matrix work root differs")
        work_root.mkdir(parents=True, exist_ok=True)
        if args.command == "task0":
            with tempfile.TemporaryDirectory(
                prefix="paid-source-task0-", dir=work_root
            ) as workspace:
                return execution.run_fp_sis_task0_v1(
                    validated,
                    read_exact=reader,
                    fetch_exact_to_file=fetcher,
                    matrix_workspace=Path(workspace),
                    reopen_discovery_matrix_registry=_matrix_registry_reopener,
                    canonical_source_v3_reopen_by_ordinal=source_reopener,
                )
        task0_receipt = _read_json(args.task0_receipt, label="task0 receipt")
        task0_provider_gate = _read_json(
            args.task0_provider_gate, label="task0 provider gate"
        )
        writer = getattr(retained_store, "publish_create_once", None)
        if not callable(writer):
            _fail("paid-source selection write store differs")
        if args.command == "task":
            with tempfile.TemporaryDirectory(
                prefix=f"paid-source-task-{task_index:02d}-", dir=work_root
            ) as workspace:
                return execution.run_fp_sis_slate_task_v2(
                    validated,
                    task0_receipt_value=task0_receipt,
                    task0_provider_gate_value=task0_provider_gate,
                    source_task_ordinal=task_index,
                    read_exact=reader,
                    fetch_exact_to_file=fetcher,
                    matrix_workspace=Path(workspace),
                    publish_create_once=writer,
                    reopen_discovery_matrix_registry=_matrix_registry_reopener,
                    canonical_source_v3_reopen_by_ordinal=source_reopener,
                )
        publication_manifest = _slate_publication_manifest(
            _read_json(
                args.slate_publications, label="slate publication manifest"
            )
        )
        return execution.collect_fp_sis_score_free_terminal_v2(
            validated,
            task0_receipt_value=task0_receipt,
            task0_provider_gate_value=task0_provider_gate,
            slate_publications=publication_manifest,
            read_exact=reader,
            publish_create_once=writer,
            reopen_discovery_matrix_registry=_matrix_registry_reopener,
        )

    retained_store = write_store or _default_store()
    reader = getattr(retained_store, "read_exact", None)
    if not callable(reader):
        _fail("paid-source grade/reopen store differs")
    if args.command == "reopen":
        item = _terminal_reopen_request(request)
        return execution.reopen_fp_sis_score_free_terminal_v1(
            terminal_identity=item["terminal_identity"],
            terminal_sha256=str(item["terminal_sha256"]),
            read_exact=reader,
            reopen_discovery_matrix_registry=_matrix_registry_reopener,
        )
    if args.command == "grade":
        item = _grade_request(request)
        writer = getattr(retained_store, "publish_create_once", None)
        if not callable(writer):
            _fail("paid-source grade write store differs")
        factory = (
            lease_verifier_factory
            or grade_runner.GCSLiveHistoricalOutcomeLeaseVerifierV1
        )
        verifier = factory(store=retained_store)
        return execution.publish_fp_sis_grade_v1(
            terminal_identity=item["terminal_identity"],
            terminal_sha256=str(item["terminal_sha256"]),
            grade_id=str(item["grade_id"]),
            outcome_authority_identity=_mapping(
                item["outcome_authority_identity"],
                label="recognized outcome authority identity",
            ),
            read_exact=reader,
            publish_create_once=writer,
            verify_live_lease=verifier,
            reopen_discovery_matrix_registry=_matrix_registry_reopener,
        )
    item = _grade_reopen_request(request)
    return execution.reopen_fp_sis_grade_v1(
        grade_identity=item["grade_identity"], read_exact=reader,
        reopen_discovery_matrix_registry=_matrix_registry_reopener,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = run(argv)
    except (
        PaidSourceFpSisCliV1Error,
        execution.PaidSourceAblationExecutionV1Error,
        batch_mechanics.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        source_v3.CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(_canonical(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
