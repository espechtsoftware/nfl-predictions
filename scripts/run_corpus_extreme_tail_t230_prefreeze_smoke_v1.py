#!/usr/bin/env python3
"""Disposable Rule-1 reality smoke for ordinal-zero T230 science.

The command exact-replays the fixed raw G0 publication, reconstructs accepted
source ordinal zero, and executes the same census/four-law-suite/support-switch
helper used by the production worker.  It publishes nothing and serializes no
support observation, selector effect, book, lineup selection, metric, or score.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Final, Protocol

from nfl_dfs.research import corpus_extreme_tail_panel_execution as execution
from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as suite
from nfl_dfs.research import corpus_extreme_tail_support_switch as support
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as accepted


ENABLE_ENV: Final = "FOUNDRY_T230_PREFREEZE_SMOKE_ENABLED"
CANDIDATE_IMAGE_ENV: Final = "T230_PREFREEZE_CANDIDATE_IMAGE"
REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
_ADDITIONAL_FALSE_AUTHORITY_FIELDS: Final = (
    "selector_effect_inspection_licensed",
    "canonical_t230_publication_licensed",
    "outcome_verdict_authority",
    "release_authority",
)


class CorpusExtremeTailT230PrefreezeSmokeError(ValueError):
    """The disposable real-artifact smoke cannot be executed exactly."""


class ReadStore(Protocol):
    def read(self, identity: Mapping[str, object]) -> bytes: ...


def _fail(message: str) -> None:
    raise CorpusExtremeTailT230PrefreezeSmokeError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _sha(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise CorpusExtremeTailT230PrefreezeSmokeError(
            f"{label} must be generation pinned"
        ) from exc


def _split_gcs_uri(value: object) -> tuple[str, str]:
    if type(value) is not str or not value.startswith("gs://"):
        _fail("exact-read URI must be one GCS object")
    bucket, separator, object_name = value[5:].partition("/")
    if (
        not bucket
        or not separator
        or not object_name
        or object_name.endswith("/")
        or "//" in object_name
    ):
        _fail("exact-read URI must be one canonical GCS object")
    return bucket, object_name


class GCSReadStore:
    """One generation-matched GET method; no list, write, or retry path."""

    def __init__(self, client: object) -> None:
        self._client = client

    def read(self, identity: Mapping[str, object]) -> bytes:
        retained = _identity(identity, label="GCS exact-read identity")
        bucket_name, object_name = _split_gcs_uri(retained["uri"])
        generation = int(str(retained["generation"]))
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        raw = blob.download_as_bytes(
            if_generation_match=generation,
            retry=None,
        )
        if (
            type(raw) is not bytes
            or len(raw) != retained["bytes"]
            or sha256(raw).hexdigest() != retained["sha256"]
        ):
            _fail("GCS exact-read bytes differ from supplied content identity")
        return raw


def _run_git(arguments: Sequence[str]) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=REPOSITORY_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CorpusExtremeTailT230PrefreezeSmokeError(
            "prefreeze smoke Git measurement failed"
        ) from exc
    return completed.stdout


def _candidate_image_from_environment() -> dict[str, str]:
    raw = os.environ.get(CANDIDATE_IMAGE_ENV, "")
    uri, separator, digest = raw.rpartition("@")
    if not separator or not uri or not digest.startswith("sha256:"):
        _fail(f"{CANDIDATE_IMAGE_ENV} must be one digest-pinned image URI")
    try:
        return batch.normalize_image_identity(
            {"uri": raw, "digest": digest}, label="prefreeze candidate image"
        )
    except Exception as exc:
        raise CorpusExtremeTailT230PrefreezeSmokeError(
            f"{CANDIDATE_IMAGE_ENV} must be one digest-pinned image URI"
        ) from exc


def _tracked_source_bindings() -> tuple[str, list[dict[str, object]]]:
    commit_raw = _run_git(["rev-parse", "HEAD"])
    try:
        commit = commit_raw.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise CorpusExtremeTailT230PrefreezeSmokeError(
            "prefreeze smoke Git commit is not ASCII"
        ) from exc
    if (
        len(commit) != 40
        or any(character not in "0123456789abcdef" for character in commit)
    ):
        _fail("prefreeze smoke Git commit differs")
    status = _run_git([
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *execution.PREFREEZE_SMOKE_IMPLEMENTATION_PATHS,
    ])
    if status != b"":
        _fail("prefreeze smoke implementation paths are not clean at Git HEAD")
    rows: list[dict[str, object]] = []
    for relative_path in execution.PREFREEZE_SMOKE_IMPLEMENTATION_PATHS:
        path = REPOSITORY_ROOT / relative_path
        try:
            metadata = path.lstat()
            raw = path.read_bytes()
        except OSError as exc:
            raise CorpusExtremeTailT230PrefreezeSmokeError(
                f"prefreeze implementation file is unavailable: {relative_path}"
            ) from exc
        if not stat.S_ISREG(metadata.st_mode) or path.is_symlink() or not raw:
            _fail(f"prefreeze implementation file is unsafe: {relative_path}")
        tracked = _run_git(["show", f"{commit}:{relative_path}"])
        if tracked != raw:
            _fail(f"prefreeze implementation file differs from Git: {relative_path}")
        rows.append({
            "path": relative_path,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    return commit, rows


def _runtime_body(
    *,
    environment_class: str,
    cloud_run_job: str | None,
    cloud_run_execution: str | None,
    cloud_run_task_index: int | None,
    cloud_run_task_attempt: int | None,
    cloud_run_task_count: int | None,
    source_commit_sha: str,
    immutable_candidate_image: Mapping[str, object],
    implementation_files: Sequence[Mapping[str, object]],
    release_validation_eligible: bool,
) -> dict[str, object]:
    process = execution._measure_process_instance()
    files = [dict(row) for row in implementation_files]
    body: dict[str, object] = {
        "schema_version": execution.PREFREEZE_SMOKE_RUNTIME_SCHEMA,
        "environment_class": environment_class,
        "cloud_run_job": cloud_run_job,
        "cloud_run_execution": cloud_run_execution,
        "cloud_run_task_index": cloud_run_task_index,
        "cloud_run_task_attempt": cloud_run_task_attempt,
        "cloud_run_task_count": cloud_run_task_count,
        "source_commit_sha": source_commit_sha,
        "immutable_candidate_image": dict(immutable_candidate_image),
        "implementation_files": files,
        "implementation_files_sha256": batch.canonical_sha256(files),
        "process_instance": process,
        "process_instance_sha256": process["process_instance_sha256"],
        "release_validation_eligible": release_validation_eligible,
        **{field: False for field in execution._FALSE_AUTHORITY_FIELDS},
        **{field: False for field in _ADDITIONAL_FALSE_AUTHORITY_FIELDS},
    }
    body["runtime_binding_sha256"] = batch.canonical_sha256(body)
    return body


def _measure_cloud_run_runtime_binding() -> dict[str, object]:
    if os.environ.get(ENABLE_ENV) != "1":
        _fail(f"{ENABLE_ENV}=1 is required")
    commit, files = _tracked_source_bindings()
    required = {
        "cloud_run_job": os.environ.get("CLOUD_RUN_JOB"),
        "cloud_run_execution": os.environ.get("CLOUD_RUN_EXECUTION"),
        "cloud_run_task_index": os.environ.get("CLOUD_RUN_TASK_INDEX"),
        "cloud_run_task_attempt": os.environ.get("CLOUD_RUN_TASK_ATTEMPT"),
        "cloud_run_task_count": os.environ.get("CLOUD_RUN_TASK_COUNT"),
    }
    if any(type(value) is not str or not value for value in required.values()):
        _fail("complete Cloud Run job runtime environment is required")
    try:
        task_index = int(str(required["cloud_run_task_index"]))
        task_attempt = int(str(required["cloud_run_task_attempt"]))
        task_count = int(str(required["cloud_run_task_count"]))
    except ValueError as exc:
        raise CorpusExtremeTailT230PrefreezeSmokeError(
            "Cloud Run task environment must contain exact integers"
        ) from exc
    body = _runtime_body(
        environment_class="cloud-run-job-real-runtime-v1",
        cloud_run_job=str(required["cloud_run_job"]),
        cloud_run_execution=str(required["cloud_run_execution"]),
        cloud_run_task_index=task_index,
        cloud_run_task_attempt=task_attempt,
        cloud_run_task_count=task_count,
        source_commit_sha=commit,
        immutable_candidate_image=_candidate_image_from_environment(),
        implementation_files=files,
        release_validation_eligible=True,
    )
    return execution.validate_t230_prefreeze_smoke_runtime_v1(
        body, require_release_runtime=True
    )


def _nonrelease_fixture_runtime_binding_v1() -> dict[str, object]:
    """Build an explicit offline-only fixture that can never pass release."""
    rows = []
    for relative_path in execution.PREFREEZE_SMOKE_IMPLEMENTATION_PATHS:
        raw = (REPOSITORY_ROOT / relative_path).read_bytes()
        rows.append({
            "path": relative_path,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    digest = "sha256:" + "0" * 64
    body = _runtime_body(
        environment_class="offline-test-fixture-nonrelease-v1",
        cloud_run_job=None,
        cloud_run_execution=None,
        cloud_run_task_index=None,
        cloud_run_task_attempt=None,
        cloud_run_task_count=None,
        source_commit_sha="0" * 40,
        immutable_candidate_image={
            "uri": f"us-central1-docker.pkg.dev/fixture/research/t230@{digest}",
            "digest": digest,
        },
        implementation_files=rows,
        release_validation_eligible=False,
    )
    return execution.validate_t230_prefreeze_smoke_runtime_v1(
        body, require_release_runtime=False
    )


def _require_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> str:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if batch.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _require_common_false(value: Mapping[str, object], *, label: str) -> None:
    for field in execution._FALSE_AUTHORITY_FIELDS:
        if value.get(field) is not False:
            _fail(f"{label}.{field} must be false")


def _project_structural_hashes(
    *,
    publication_binding: Mapping[str, object],
    publication_receipt: Mapping[str, object],
    lane_bindings: Sequence[Mapping[str, object]],
    panel_identity: Mapping[str, object],
    panel_member: Mapping[str, object],
    input_bindings: Mapping[str, object],
    science_stack: execution._T230ScienceStack,
) -> dict[str, object]:
    census_body = dict(
        _mapping(science_stack.support_census, label="support census")
    )
    suite_body = dict(
        _mapping(science_stack.extreme_tail_suite, label="extreme-tail suite")
    )
    policy_body = dict(
        _mapping(science_stack.support_policy, label="support-switched policy")
    )
    _require_common_false(census_body, label="support census")
    _require_common_false(suite_body, label="extreme-tail suite")
    _require_common_false(policy_body, label="support-switched policy")
    support_census_sha = _require_self_hash(
        census_body, field="support_census_sha256", label="support census"
    )
    suite_sha = _require_self_hash(
        suite_body, field="suite_sha256", label="extreme-tail suite"
    )
    policy_sha = _require_self_hash(
        policy_body,
        field="support_switched_policy_sha256",
        label="support-switched policy",
    )
    strategies = suite.frozen_extreme_tail_strategies_v1()
    implementation = suite.frozen_selector_implementation_contract_v1()
    selector_binding = {
        "implementation_id": implementation["implementation_id"],
        "selector_implementation_sha256": implementation[
            "selector_implementation_sha256"
        ],
    }
    if (
        suite_body.get("strategy_registry") != strategies
        or suite_body.get("strategy_registry_sha256")
        != batch.canonical_sha256(strategies)
        or suite_body.get("selector_implementation_binding") != selector_binding
        or suite_body.get("selector_implementation_contract") != implementation
        or suite_body.get("entry_budgets") != list(execution.ENTRY_BUDGETS)
        or suite_body.get("fold_count") != 5
        or suite_body.get("books_per_scope") != 12
        or suite_body.get("cross_fit_book_count") != 60
        or suite_body.get("final_fit_book_count") != 12
        or suite_body.get("worlds_per_block") != execution.WORLDS_PER_BLOCK
        or suite_body.get("require_authoritative") is not True
        or suite_body.get("final_fit_is_distinct_all_block_refit") is not True
    ):
        _fail("extreme-tail suite structural lattice differs")
    source_receipts = _mapping(
        policy_body.get("source_receipts"), label="support-switch source receipts"
    )
    if (
        policy_body.get("schema_version") != support.POLICY_SCHEMA
        or policy_body.get("policy_law_id") != support.POLICY_LAW_ID
        or policy_body.get("strategy_registry_sha256")
        != suite_body["strategy_registry_sha256"]
        or policy_body.get("entry_budgets") != list(execution.ENTRY_BUDGETS)
        or policy_body.get("fold_gate_count") != 5
        or policy_body.get("final_fit_gate_count") != 1
        or policy_body.get("worlds_per_block") != execution.WORLDS_PER_BLOCK
        or policy_body.get("require_authoritative") is not True
        or source_receipts.get("support_census_sha256") != support_census_sha
        or source_receipts.get("extreme_tail_suite_sha256") != suite_sha
    ):
        _fail("support-switch structural binding differs")
    lane_projection = []
    for ordinal, raw_binding in enumerate(lane_bindings):
        binding = _mapping(raw_binding, label=f"G0 lane binding[{ordinal}]")
        terminal = _identity(
            binding.get("terminal_receipt_identity"),
            label=f"G0 lane[{ordinal}] terminal identity",
        )
        if (
            binding.get("lane_ordinal") != ordinal
            or type(binding.get("bytes")) is not int
            or int(binding["bytes"]) < 1
        ):
            _fail("G0 lane receipt binding differs")
        lane_projection.append({
            "lane_ordinal": ordinal,
            "receipt_file_sha256": _sha(
                binding.get("sha256"), label=f"G0 lane[{ordinal}] file SHA"
            ),
            "receipt_file_bytes": binding["bytes"],
            "terminal_receipt_identity_sha256": batch.canonical_sha256(terminal),
        })
    if len(lane_projection) != 2:
        _fail("G0 lane receipt binding count differs")
    return {
        "g0_publication_receipt_file_sha256": _sha(
            publication_binding.get("sha256"),
            label="G0 publication receipt file SHA",
        ),
        "g0_publication_receipt_sha256": _sha(
            publication_receipt.get("publication_receipt_sha256"),
            label="G0 publication receipt SHA",
        ),
        "g0_lane_receipt_binding_set_sha256": batch.canonical_sha256(
            lane_projection
        ),
        "panel_object_identity_sha256": batch.canonical_sha256(panel_identity),
        "panel_index_sha256": _sha(
            input_bindings.get("panel_index_sha256"), label="panel index SHA"
        ),
        "panel_member_sha256": batch.canonical_sha256(panel_member),
        "task_acceptance_identity_sha256": batch.canonical_sha256(
            input_bindings["task_acceptance_identity"]
        ),
        "carrier_identity_sha256": batch.canonical_sha256(
            input_bindings["carrier_identity"]
        ),
        "later_source_freeze_identity_sha256": batch.canonical_sha256(
            input_bindings["later_source_freeze_identity"]
        ),
        "world_artifact_identity_set_sha256": _sha(
            input_bindings.get("world_artifact_identity_set_sha256"),
            label="world artifact identity-set SHA",
        ),
        "compatibility_import_sha256": _sha(
            input_bindings.get("compatibility_import_sha256"),
            label="compatibility import SHA",
        ),
        "candidate_provenance_sha256": _sha(
            input_bindings.get("candidate_provenance_sha256"),
            label="candidate provenance SHA",
        ),
        "reconstruction_sha256": _sha(
            input_bindings.get("reconstruction_sha256"),
            label="reconstruction SHA",
        ),
        "matrix_binding_sha256": _sha(
            input_bindings.get("matrix_binding_sha256"),
            label="matrix binding SHA",
        ),
        "score_matrix_sha256": _sha(
            input_bindings.get("score_matrix_sha256"), label="score matrix SHA"
        ),
        "lineup_ids_sha256": _sha(
            input_bindings.get("lineup_ids_sha256"), label="lineup IDs SHA"
        ),
        "world_ids_sha256": _sha(
            input_bindings.get("world_ids_sha256"), label="world IDs SHA"
        ),
        "support_census_sha256": support_census_sha,
        "extreme_tail_suite_sha256": suite_sha,
        "strategy_registry_sha256": _sha(
            suite_body.get("strategy_registry_sha256"),
            label="strategy registry SHA",
        ),
        "selector_implementation_sha256": _sha(
            implementation.get("selector_implementation_sha256"),
            label="selector implementation SHA",
        ),
        "support_switched_policy_sha256": policy_sha,
        "support_source_pair_sha256": _sha(
            source_receipts.get("source_pair_sha256"),
            label="support source-pair SHA",
        ),
    }


def _absolute_for_checks(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _reject_symlink_components(path: Path) -> None:
    checked = _absolute_for_checks(path)
    for component in (checked, *checked.parents):
        if component.is_symlink():
            _fail("receipt output cannot contain a symlink")


def _preflight_output(path: Path | None) -> None:
    if path is None:
        return
    if not path.is_absolute() or path.name in {"", ".", ".."} or ".." in path.parts:
        _fail("receipt output must be one canonical absolute path")
    _reject_symlink_components(path)
    if os.path.lexists(path):
        _fail("receipt output create-once collision already exists")
    if not path.parent.is_dir():
        _fail("receipt output parent must be one existing directory")


def _write_create_once(path: Path, receipt: Mapping[str, object]) -> None:
    raw = batch.canonical_json_bytes(receipt) + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise CorpusExtremeTailT230PrefreezeSmokeError(
            "receipt output create-once write failed"
        ) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run fixed ordinal-zero T230 Rule-1 reality contact"
    )
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument(
        "--receipt-output",
        type=Path,
        help="optional absolute local create-once compact receipt path",
    )
    return parser


def run(
    argv: Sequence[str],
    *,
    store: ReadStore,
    runtime_binding: Mapping[str, object] | None = None,
) -> dict[str, object]:
    args = _parser().parse_args(list(argv))
    _preflight_output(args.receipt_output)
    require_release_runtime = runtime_binding is None
    runtime = (
        _measure_cloud_run_runtime_binding()
        if runtime_binding is None
        else execution.validate_t230_prefreeze_smoke_runtime_v1(
            runtime_binding, require_release_runtime=False
        )
    )
    try:
        publication_binding, publication_receipt, panel_body, lane_bindings = (
            execution._replay_raw_published_v12_panel_v1(read_exact=store.read)
        )
    except execution.CorpusExtremeTailPanelExecutionError as exc:
        raise CorpusExtremeTailT230PrefreezeSmokeError(str(exc)) from exc
    members = _sequence(
        panel_body.get("accepted_slates"), label="published panel accepted slates"
    )
    if len(members) != execution.AUTHORITATIVE_SLATE_COUNT:
        _fail("published panel must contain exactly 54 accepted slates")
    member = dict(_mapping(members[0], label="published panel ordinal zero"))
    if (
        member.get("source_task_ordinal") != execution.PREFREEZE_SMOKE_SOURCE_ORDINAL
        or member.get("slate_id") != execution.PREFREEZE_SMOKE_SLATE_ID
    ):
        _fail("published panel ordinal zero differs from fixed 2023-w01")
    panel_identity = _identity(
        publication_receipt.get("panel_object_identity"),
        label="published panel object",
    )
    try:
        reconstructed_slate = accepted.reconstruct_one_accepted_v12_slate(
            validated_panel_index=panel_body,
            panel_index_identity=panel_identity,
            accepted_slate_membership=member,
            task_acceptance_identity=_mapping(
                member.get("task_acceptance_identity"),
                label="ordinal-zero task acceptance",
            ),
            carrier_identity=_mapping(
                member.get("carrier_identity"), label="ordinal-zero carrier"
            ),
            read_exact=store.read,
            require_authoritative=True,
        )
    except accepted.CorpusR6V2OneSlateExecutionError as exc:
        raise CorpusExtremeTailT230PrefreezeSmokeError(str(exc)) from exc
    if (
        reconstructed_slate.slate_id != execution.PREFREEZE_SMOKE_SLATE_ID
        or batch.canonical_sha256(reconstructed_slate.accepted_slate_membership)
        != batch.canonical_sha256(member)
        or reconstructed_slate.task_acceptance_identity
        != member["task_acceptance_identity"]
        or reconstructed_slate.carrier_identity != member["carrier_identity"]
    ):
        _fail("ordinal-zero accepted reconstruction differs from panel membership")
    reconstruction_receipt = _mapping(
        reconstructed_slate.reconstructed.reconstruction_receipt,
        label="ordinal-zero reconstruction receipt",
    )
    if (
        reconstruction_receipt.get("uses_realized_outcomes") is not False
        or reconstruction_receipt.get("promotion_authority") is not False
    ):
        _fail("ordinal-zero reconstruction carries forbidden authority")
    input_bindings = execution._input_artifact_bindings(
        reconstructed_slate, panel_member=member
    )
    science_stack = execution._execute_t230_science_stack_v1(reconstructed_slate)
    structural_hashes = _project_structural_hashes(
        publication_binding=publication_binding,
        publication_receipt=publication_receipt,
        lane_bindings=lane_bindings,
        panel_identity=panel_identity,
        panel_member=member,
        input_bindings=input_bindings,
        science_stack=science_stack,
    )
    del science_stack, reconstructed_slate, reconstruction_receipt
    receipt = execution.build_t230_prefreeze_smoke_receipt_v1(
        panel_object_identity=panel_identity,
        source_commit_sha=str(runtime["source_commit_sha"]),
        immutable_candidate_image=_mapping(
            runtime["immutable_candidate_image"], label="candidate image"
        ),
        runtime_binding=runtime,
        structural_hashes=structural_hashes,
        require_release_runtime=require_release_runtime,
    )
    if args.receipt_output is not None:
        _write_create_once(args.receipt_output, receipt)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover - production dependency gate
        raise CorpusExtremeTailT230PrefreezeSmokeError(
            "google-cloud-storage is required for this command"
        ) from exc
    receipt = run(
        sys.argv[1:] if argv is None else argv,
        store=GCSReadStore(storage.Client()),
    )
    sys.stdout.buffer.write(batch.canonical_json_bytes(receipt) + b"\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
