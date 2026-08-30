"""Root-last outcome-blind R6-v2 release for the candidate-rooted source.

This is the release successor to ``corpus_r6_v2_analysis_release``.  The
legacy release intentionally terminates ``complete-source-blocked`` because
it understands only the old simple matchup snapshot.  This module accepts
only the generation-pinned candidate-authority v2 matchup-source root and
executes each ordinal through
``execute_r6_v2_matchup_candidate_authority_ordinal_v2``.

The release is deliberately small and crash-safe:

* ``prepare`` exact-replays Gate G0, exact-opens the 54-member matchup root,
  cross-binds both ordinal lattices, and publishes one immutable manifest;
* one worker process executes one ordinal and publishes all 276 rank-80 books
  plus explicit nested 4/14/80 prefixes;
* a different measured process exact-reopens the worker and independently
  re-executes the scientific consumer before publishing acceptance; and
* ``finish`` exact-reopens all 54 acceptances and their workers before it
  creates the terminal accepted root.

No function imports a realized-outcome reader, lists object storage, scores a
historical lineup, changes policy, or grants promotion/decision authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import importlib
import os
from pathlib import Path
import re
import sys
from typing import Final

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_matchup_source_release_candidate_authority_v2 as source_release_v2,
)
from nfl_dfs.research import (
    corpus_r6_v2_matchup_candidate_authority_consumer_v2 as consumer,
)
from nfl_dfs.research import corpus_v12_panel_index as panel_index
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_neo4j_transport import ExactObjectStore, ObjectIdentity
from nfl_dfs.research.corpus_v12_import import canonical_lineup_id


MANIFEST_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-analysis-execution-manifest/v2"
)
WORKER_RESULT_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-analysis-worker-result/v2"
)
BOOK_CATALOG_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-analysis-book-catalog/v2"
)
BOOK_DESCRIPTOR_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-analysis-book-descriptor/v2"
)
PREFIX_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-analysis-book-prefix/v2"
)
PROCESS_RUNTIME_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-analysis-process-runtime/v2"
)
ACCEPTANCE_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-analysis-slate-acceptance/v2"
)
TERMINAL_ROOT_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-analysis-accepted-root/v2"
)
PREPARE_RECEIPT_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-analysis-prepare-receipt/v2"
)
WORKER_RECEIPT_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-analysis-worker-receipt/v2"
)
VERIFIER_RECEIPT_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-analysis-verifier-receipt/v2"
)
FINISH_RECEIPT_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-analysis-finish-receipt/v2"
)
EMBEDDED_RUNTIME_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-embedded-runtime-authority/v1"
)
PROVIDER_RUNTIME_IMAGE_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-provider-runtime-image-authority/v1"
)
PROVIDER_IMAGE_OBSERVATION_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-provider-image-observation/v1"
)

PUBLICATION_MODE: Final = "create_once"
AUTHORITATIVE_SLATE_COUNT: Final = 54
LANE_TASK_COUNTS: Final = (28, 26)
FIT_SCOPE_IDS: Final = (
    "holdout-R0",
    "holdout-R1",
    "holdout-R2",
    "holdout-R3",
    "holdout-R4",
    "all-block-final-fit",
)
PREFIX_SIZES: Final = (4, 14, 80)
BOOKS_PER_SCOPE: Final = 46
BOOKS_PER_SLATE: Final = 276
PREFIXES_PER_SLATE: Final = 828
PANEL_BOOK_COUNT: Final = 14_904
PANEL_PREFIX_COUNT: Final = 44_712
ENTRY_BUDGET: Final = 80
ADMISSION_CAP: Final = 200
NEUTRAL_REPLICATES: Final = 32
NEUTRAL_SEED_ROOT: Final = "r6-v2-neutral-v1"
WORLDS_PER_BLOCK: Final = 10_000
MINIMUM_SUPPORTED_PLAYERS: Final = 2
MINIMUM_COMPLETENESS: Final = 0.5
TERMINAL_STATUS: Final = "accepted-outcome-blind-analysis-release"
IMAGE_RUNTIME_AUTHORITY_RECEIPT_PATH: Final = Path(
    "/app/runtime/r6-v2-runtime-authority.json"
)

_DIRECT_RUNTIME_PATHS: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_v2_matchup_candidate_analysis_release_v2.py",
    "src/nfl_dfs/research/"
    "corpus_r6_v2_matchup_candidate_analysis_controller_v1.py",
    "src/nfl_dfs/research/"
    "corpus_r6_v2_matchup_candidate_authority_consumer_v2.py",
    "src/nfl_dfs/research/"
    "corpus_r6_v2_matchup_source_release_consumer_v1.py",
    "src/nfl_dfs/research/"
    "corpus_r6_candidate_population_scored_union_v1.py",
    "src/nfl_dfs/research/"
    "corpus_r6_matchup_source_release_candidate_authority_v2.py",
    "src/nfl_dfs/research/corpus_r6_matchup_source_release_v1.py",
    "src/nfl_dfs/research/corpus_r6_fixed_g0_candidate_authority_release_v1.py",
    "src/nfl_dfs/research/corpus_r6_fixed_g0_candidate_authority_v1.py",
    "src/nfl_dfs/research/corpus_batch_retrieval_runner_v2.py",
    "src/nfl_dfs/research/corpus_legal_feasibility.py",
    "src/nfl_dfs/research/corpus_parametric_snapshot.py",
    "src/nfl_dfs/research/corpus_r6_matchup_source_v1.py",
    "src/nfl_dfs/research/corpus_r6_matchup_source_v2.py",
    "src/nfl_dfs/research/corpus_r6_v2_one_slate_execution.py",
    "src/nfl_dfs/research/corpus_r6_v2_one_slate_execution_v2.py",
    "src/nfl_dfs/research/corpus_v12_import.py",
    "src/nfl_dfs/research/corpus_v12_panel_index.py",
    "src/nfl_dfs/research/corpus_parametric_batch.py",
    "src/nfl_dfs/research/corpus_retrieval_engine.py",
    "src/nfl_dfs/research/residual_world_columns.py",
    "src/nfl_dfs/research/corpus_neo4j_transport.py",
    "scripts/run_corpus_r6_v2_matchup_candidate_analysis_release_v2.py",
    "scripts/run_corpus_r6_v2_matchup_candidate_analysis_controller_v1.py",
)
_MODULE_REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[3]
_PROJECT_PYTHON_PATHS: Final = tuple(
    path.relative_to(_MODULE_REPOSITORY_ROOT).as_posix()
    for path in sorted(
        (_MODULE_REPOSITORY_ROOT / "src" / "nfl_dfs").rglob("*.py")
    )
)
CRITICAL_RUNTIME_PATHS: Final = tuple(dict.fromkeys((
        *_DIRECT_RUNTIME_PATHS,
        *_PROJECT_PYTHON_PATHS,
    )))

_RUNTIME_FILE_FIELDS: Final = frozenset({
    "relative_path",
    "sha256",
    "bytes",
})
_EMBEDDED_RUNTIME_AUTHORITY_FIELDS: Final = frozenset({
    "schema_version",
    "source_commit_sha",
    "critical_runtime_paths",
    "critical_runtime_paths_sha256",
    "file_count",
    "file_measurements",
    "critical_runtime_files_sha256",
    "clean_git_head_verified_at_build",
    "clean_git_status_verified_at_build",
    "working_tree_equals_commit_blobs_verified_at_build",
    "runtime_authority_sha256",
})
_PROVIDER_IMAGE_OBSERVATION_FIELDS: Final = frozenset({
    "schema_version",
    "provider",
    "observation_kind",
    "resource_name",
    "build_id",
    "job_name",
    "job_uid",
    "execution_id",
    "source_commit_sha",
    "immutable_image",
    "provider_observed",
})
_PROVIDER_RUNTIME_IMAGE_AUTHORITY_FIELDS: Final = frozenset({
    "schema_version",
    "provider_observation",
    "provider_observation_sha256",
    "embedded_runtime_authority",
    "source_commit_sha",
    "immutable_image",
    "image_digest",
    "embedded_runtime_authority_sha256",
    "critical_runtime_paths_sha256",
    "critical_runtime_files_sha256",
    "provider_attestation_claimed",
    "provider_runtime_image_authority_sha256",
})

_FALSE_AUTHORITY_FIELDS: Final = (
    "analytical_authority",
    "automatic_retry_licensed",
    "corpus_fill_licensed",
    "corpus_retrieval_licensed",
    "decision_authority",
    "fill_authority",
    "graph_authority",
    "graph_mutation_licensed",
    "historical_scoring_authority",
    "historical_scoring_licensed",
    "live_policy_access_licensed",
    "live_strategy_authority",
    "outcome_authority",
    "outcome_verdict_authority",
    "production_authority",
    "production_change_licensed",
    "production_policy_authority",
    "promotion_authority",
    "r6_freeze_authority",
    "retrieval_authority",
    "scoring_authority",
    "source_execution_authority",
    "source_publication_authority",
    "uses_realized_outcomes",
)
_FORBIDDEN_OUTCOME_FIELDS: Final = frozenset({
    "actual_points",
    "actual_score",
    "contest_finish",
    "contest_place",
    "contest_rank",
    "contest_score",
    "entry_rank",
    "lineup_actual",
    "lineup_points",
    "lineup_score",
    "outcome_reader",
    "payout",
    "realized_outcome",
    "realized_points",
    "realized_reader",
    "realized_score",
    "score_reader",
    "winner",
    "winning_score",
})
_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_IMAGE = re.compile(r"[^\s@]+@sha256:[0-9a-f]{64}")
_ACCEPTANCE_VERIFICATION_FIELDS: Final = frozenset({
    "worker_exact_reopened",
    "candidate_root_full_predecessor_replayed",
    "source_member_full_predecessor_replayed",
    "accepted_v12_slate_reconstructed",
    "scientific_consumer_independently_reexecuted",
    "all_276_rank80_books_canonical_replayed",
    "all_4_14_80_prefixes_canonical_replayed",
    "worker_and_verifier_processes_distinct",
})
_ACCEPTANCE_FIELDS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "status",
    "accepted",
    "target_uri",
    "manifest_identity",
    "execution_manifest_sha256",
    "source_ordinal",
    "slate_id",
    "panel_member_sha256",
    "matchup_source_release_identity",
    "matchup_source_member_sha256",
    "worker_result_identity",
    "worker_result_sha256",
    "worker_process_runtime",
    "worker_process_runtime_sha256",
    "verifier_process_runtime",
    "verifier_process_runtime_sha256",
    "worker_task_result_sha256",
    "independent_reexecution_task_result_sha256",
    "book_catalog_sha256",
    "scope_count",
    "rank_80_book_count",
    "prefix_sizes",
    "prefix_count",
    "verification",
    "outcome_columns_read",
    *_FALSE_AUTHORITY_FIELDS,
    "slate_acceptance_sha256",
})


class CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(RuntimeError):
    """The accepted outcome-blind release could not be proven exactly."""


ReadExact = Callable[[Mapping[str, object]], bytes]
GitHead = source_release_v2.GitHead
GitBlob = source_release_v2.GitBlob
GitStatus = source_release_v2.GitStatus
ExecuteOrdinal = Callable[..., dict[str, object]]
ValidateOrdinal = Callable[..., dict[str, object]]


def _fail(message: str) -> None:
    raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if frozenset(value) != expected:
        _fail(f"{label} fields differ")


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(str(exc)) from exc


def _object_identity(value: object, *, label: str) -> ObjectIdentity:
    row = _identity(value, label=label)
    return ObjectIdentity(
        uri=str(row["uri"]),
        generation=str(row["generation"]),
        sha256=str(row["sha256"]),
        bytes=int(row["bytes"]),
    )


def _identity_key(value: object, *, label: str) -> tuple[str, str, str, int]:
    row = _identity(value, label=label)
    return (
        str(row["uri"]),
        str(row["generation"]),
        str(row["sha256"]),
        int(row["bytes"]),
    )


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in value:
        _fail(f"{field} must not be supplied before hashing")
    result = dict(value)
    result[field] = batch.canonical_sha256(result)
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _digest(value.get(field), label=f"{label} {field}")
    body = {key: nested for key, nested in value.items() if key != field}
    if batch.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _runtime_file_path(
    repository_root: Path, relative_path: object, *, label: str,
) -> Path:
    if type(relative_path) is not str or not relative_path:
        _fail(f"{label} relative path differs")
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
        _fail(f"{label} relative path differs")
    candidate = repository_root / relative
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
            f"{label} is absent"
        ) from exc
    if resolved != candidate or not resolved.is_file():
        _fail(f"{label} must be one non-symlink regular file")
    return resolved


def _runtime_file_measurement(
    repository_root: Path, relative_path: str,
) -> tuple[dict[str, object], bytes]:
    path = _runtime_file_path(
        repository_root, relative_path, label=f"runtime file {relative_path!r}"
    )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
            f"runtime file {relative_path!r} cannot be read"
        ) from exc
    return {
        "relative_path": relative_path,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }, raw


def build_embedded_runtime_authority_v1(
    *, repository_root: Path, source_commit_sha: str,
    git_head: GitHead, git_blob: GitBlob, git_status: GitStatus,
) -> dict[str, object]:
    """Measure a tracked-clean build context before it enters the image."""
    if (
        not isinstance(repository_root, Path)
        or not repository_root.is_absolute()
        or type(source_commit_sha) is not str
        or _COMMIT.fullmatch(source_commit_sha) is None
        or not callable(git_head)
        or not callable(git_blob)
        or not callable(git_status)
    ):
        _fail("embedded runtime build authority arguments differ")
    try:
        root = repository_root.resolve(strict=True)
        head = git_head(root)
        status = git_status(root, ["."])
    except Exception as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
            "embedded runtime clean-Git measurement failed"
        ) from exc
    if head != source_commit_sha or type(status) is not bytes or status != b"":
        _fail("embedded runtime build context is not the exact clean commit")
    measurements: list[dict[str, object]] = []
    for relative_path in CRITICAL_RUNTIME_PATHS:
        measurement, raw = _runtime_file_measurement(root, relative_path)
        try:
            committed = git_blob(root, source_commit_sha, relative_path)
        except Exception as exc:
            raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
                f"embedded runtime committed blob read failed: {relative_path}"
            ) from exc
        if type(committed) is not bytes or committed != raw:
            _fail(f"embedded runtime file differs from commit: {relative_path}")
        measurements.append(measurement)
    body = {
        "schema_version": EMBEDDED_RUNTIME_AUTHORITY_SCHEMA,
        "source_commit_sha": source_commit_sha,
        "critical_runtime_paths": list(CRITICAL_RUNTIME_PATHS),
        "critical_runtime_paths_sha256": batch.canonical_sha256(
            list(CRITICAL_RUNTIME_PATHS)
        ),
        "file_count": len(measurements),
        "file_measurements": measurements,
        "critical_runtime_files_sha256": batch.canonical_sha256(measurements),
        "clean_git_head_verified_at_build": True,
        "clean_git_status_verified_at_build": True,
        "working_tree_equals_commit_blobs_verified_at_build": True,
    }
    return _with_hash(body, field="runtime_authority_sha256")


def validate_embedded_runtime_authority_v1(
    value: object,
) -> dict[str, object]:
    item = _mapping(value, label="embedded runtime authority")
    _exact_keys(
        item,
        _EMBEDDED_RUNTIME_AUTHORITY_FIELDS,
        label="embedded runtime authority",
    )
    _validate_self_hash(
        item,
        field="runtime_authority_sha256",
        label="embedded runtime authority",
    )
    measurements = [
        _mapping(row, label=f"runtime file measurement[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(item.get("file_measurements"), label="runtime files")
        )
    ]
    for ordinal, measurement in enumerate(measurements):
        _exact_keys(
            measurement,
            _RUNTIME_FILE_FIELDS,
            label=f"runtime file measurement[{ordinal}]",
        )
        _digest(
            measurement.get("sha256"),
            label=f"runtime file measurement[{ordinal}] SHA",
        )
        if (
            type(measurement.get("relative_path")) is not str
            or type(measurement.get("bytes")) is not int
            or int(measurement["bytes"]) < 0
        ):
            _fail(f"runtime file measurement[{ordinal}] structure differs")
    expected_paths = list(CRITICAL_RUNTIME_PATHS)
    if (
        item.get("schema_version") != EMBEDDED_RUNTIME_AUTHORITY_SCHEMA
        or type(item.get("source_commit_sha")) is not str
        or _COMMIT.fullmatch(str(item.get("source_commit_sha"))) is None
        or item.get("critical_runtime_paths") != expected_paths
        or item.get("critical_runtime_paths_sha256")
        != batch.canonical_sha256(expected_paths)
        or item.get("file_count") != len(expected_paths)
        or [row["relative_path"] for row in measurements] != expected_paths
        or item.get("critical_runtime_files_sha256")
        != batch.canonical_sha256(measurements)
        or item.get("clean_git_head_verified_at_build") is not True
        or item.get("clean_git_status_verified_at_build") is not True
        or item.get("working_tree_equals_commit_blobs_verified_at_build")
        is not True
    ):
        _fail("embedded runtime authority closure differs")
    return item


def load_image_embedded_runtime_authority_v1() -> dict[str, object]:
    """Read the sole fixed, canonical receipt embedded in the runtime image."""
    path = IMAGE_RUNTIME_AUTHORITY_RECEIPT_PATH
    if not path.is_absolute():
        _fail("image runtime authority receipt path differs")
    try:
        resolved = path.resolve(strict=True)
        raw = resolved.read_bytes()
    except OSError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
            "image runtime authority receipt is absent"
        ) from exc
    if resolved != path or not resolved.is_file() or not raw:
        _fail("image runtime authority receipt must be one fixed regular file")
    try:
        parsed = batch.parse_canonical_json_bytes(
            raw, label="image embedded runtime authority receipt"
        )
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(str(exc)) from exc
    embedded = validate_embedded_runtime_authority_v1(parsed)
    if raw != batch.canonical_json_bytes(embedded):
        _fail("image runtime authority receipt bytes are not canonical")
    return embedded


def _provider_image_observation(value: object) -> dict[str, object]:
    item = _mapping(value, label="provider image observation")
    _exact_keys(
        item,
        _PROVIDER_IMAGE_OBSERVATION_FIELDS,
        label="provider image observation",
    )
    kind = item.get("observation_kind")
    job_name = item.get("job_name")
    job_uid = item.get("job_uid")
    execution_id = item.get("execution_id")
    if (
        item.get("schema_version") != PROVIDER_IMAGE_OBSERVATION_SCHEMA
        or item.get("provider")
        not in {"google-cloud-build", "google-cloud-run-v2"}
        or kind
        not in {"cloud-build-image", "cloud-run-job", "cloud-run-execution"}
        or type(item.get("resource_name")) is not str
        or not item["resource_name"]
        or type(item.get("build_id")) is not str
        or not item["build_id"]
        or type(item.get("source_commit_sha")) is not str
        or _COMMIT.fullmatch(str(item.get("source_commit_sha"))) is None
        or type(item.get("immutable_image")) is not str
        or _IMAGE.fullmatch(str(item.get("immutable_image"))) is None
        or item.get("provider_observed") is not True
    ):
        _fail("provider image observation differs")
    if kind == "cloud-build-image" and any(
        value is not None for value in (job_name, job_uid, execution_id)
    ):
        _fail("provider build image observation carries Cloud Run identity")
    if (
        (kind == "cloud-build-image")
        != (item.get("provider") == "google-cloud-build")
    ):
        _fail("provider image observation kind/provider pairing differs")
    if kind in {"cloud-run-job", "cloud-run-execution"} and (
        type(job_name) is not str
        or not job_name
        or type(job_uid) is not str
        or not job_uid
    ):
        _fail("provider Cloud Run job identity differs")
    if kind == "cloud-run-job" and execution_id is not None:
        _fail("provider job observation carries an execution identity")
    if kind == "cloud-run-execution" and (
        type(execution_id) is not str or not execution_id
    ):
        _fail("provider execution identity differs")
    return item


def build_provider_runtime_image_authority_v1(
    *, provider_observation: Mapping[str, object],
    embedded_runtime_authority: Mapping[str, object],
) -> dict[str, object]:
    observation = _provider_image_observation(provider_observation)
    embedded = validate_embedded_runtime_authority_v1(
        embedded_runtime_authority
    )
    if observation["source_commit_sha"] != embedded["source_commit_sha"]:
        _fail("provider image commit differs from embedded runtime authority")
    immutable_image = str(observation["immutable_image"])
    body = {
        "schema_version": PROVIDER_RUNTIME_IMAGE_AUTHORITY_SCHEMA,
        "provider_observation": observation,
        "provider_observation_sha256": batch.canonical_sha256(observation),
        "embedded_runtime_authority": embedded,
        "source_commit_sha": embedded["source_commit_sha"],
        "immutable_image": immutable_image,
        "image_digest": immutable_image.rsplit("@", 1)[1],
        "embedded_runtime_authority_sha256": embedded[
            "runtime_authority_sha256"
        ],
        "critical_runtime_paths_sha256": embedded[
            "critical_runtime_paths_sha256"
        ],
        "critical_runtime_files_sha256": embedded[
            "critical_runtime_files_sha256"
        ],
        "provider_attestation_claimed": False,
    }
    return _with_hash(body, field="provider_runtime_image_authority_sha256")


def validate_provider_runtime_image_authority_v1(
    value: object,
) -> dict[str, object]:
    item = _mapping(value, label="provider runtime image authority")
    _exact_keys(
        item,
        _PROVIDER_RUNTIME_IMAGE_AUTHORITY_FIELDS,
        label="provider runtime image authority",
    )
    _validate_self_hash(
        item,
        field="provider_runtime_image_authority_sha256",
        label="provider runtime image authority",
    )
    observation = _provider_image_observation(item.get("provider_observation"))
    embedded = validate_embedded_runtime_authority_v1(
        item.get("embedded_runtime_authority")
    )
    immutable_image = str(item.get("immutable_image"))
    if (
        item.get("schema_version") != PROVIDER_RUNTIME_IMAGE_AUTHORITY_SCHEMA
        or item.get("provider_observation_sha256")
        != batch.canonical_sha256(observation)
        or item.get("source_commit_sha") != observation["source_commit_sha"]
        or item.get("source_commit_sha") != embedded["source_commit_sha"]
        or immutable_image != observation["immutable_image"]
        or _IMAGE.fullmatch(immutable_image) is None
        or item.get("image_digest") != immutable_image.rsplit("@", 1)[1]
        or item.get("embedded_runtime_authority_sha256")
        != embedded["runtime_authority_sha256"]
        or item.get("critical_runtime_paths_sha256")
        != embedded["critical_runtime_paths_sha256"]
        or item.get("critical_runtime_files_sha256")
        != embedded["critical_runtime_files_sha256"]
        or item.get("provider_attestation_claimed") is not False
    ):
        _fail("provider runtime image authority differs")
    return item


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }


def _validate_policy(value: Mapping[str, object], *, label: str) -> None:
    if value.get("outcome_columns_read") != [] or any(
        value.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS
    ):
        _fail(f"{label} outcome/authority policy differs")


def _reject_outcome_carriers(value: object, *, label: str) -> None:
    stack: list[tuple[str, object]] = [(label, value)]
    while stack:
        path, current = stack.pop()
        if isinstance(current, Mapping):
            for key, nested in current.items():
                if type(key) is not str:
                    _fail(f"{path} contains a non-string key")
                normalized_key = key.strip().lower()
                if normalized_key in _FORBIDDEN_OUTCOME_FIELDS:
                    _fail(f"{path} carries forbidden outcome field {key!r}")
                stack.append((f"{path}.{key}", nested))
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
            stack.extend(
                (f"{path}[{index}]", nested)
                for index, nested in enumerate(current)
            )


def _output_prefix(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith("gs://")
        or not value.endswith("/")
        or any(character.isspace() for character in value)
    ):
        _fail("output prefix must be one canonical trailing-slash GCS prefix")
    bucket_and_object = value[5:]
    bucket, separator, object_name = bucket_and_object.partition("/")
    if not bucket or not separator or not object_name or "//" in object_name:
        _fail("output prefix must name a non-root canonical GCS prefix")
    return value


def _bind_identity_to_body(
    identity: object, body: object, *, label: str,
) -> dict[str, object]:
    row = _identity(identity, label=label)
    raw = batch.canonical_json_bytes(body)
    if row["sha256"] != sha256(raw).hexdigest() or row["bytes"] != len(raw):
        _fail(f"{label} content identity differs from body")
    return row


def _read_exact_callback(storage: ExactObjectStore) -> ReadExact:
    def read_exact(identity: Mapping[str, object]) -> bytes:
        return storage.read_exact(_object_identity(identity, label="exact object"))

    return read_exact


def _read_json(
    storage: ExactObjectStore, identity: object, *, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    row = _identity(identity, label=label)
    try:
        raw = storage.read_exact(_object_identity(row, label=label))
    except Exception as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
            f"{label} exact reopen failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != row["bytes"]
        or sha256(raw).hexdigest() != row["sha256"]
    ):
        _fail(f"{label} exact bytes differ")
    try:
        parsed = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(str(exc)) from exc
    return row, _mapping(parsed, label=label)


def _publish_or_recover(
    storage: ExactObjectStore, *, uri: str, value: Mapping[str, object], label: str,
) -> dict[str, object]:
    raw = batch.canonical_json_bytes(value)
    try:
        existing = storage.resolve_optional(uri)
    except Exception as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
            f"{label} create-once preflight failed"
        ) from exc
    if existing is not None:
        if existing[1] != raw:
            _fail(f"{label} create-once collision differs")
        retained = _identity(existing[0].as_dict(), label=label)
    else:
        try:
            retained = _identity(
                storage.publish_create_once(uri, raw).as_dict(), label=label
            )
        except Exception as exc:
            raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
                f"{label} create-once publication failed"
            ) from exc
    if retained["uri"] != uri:
        _fail(f"{label} published URI differs")
    reopened = storage.read_exact(_object_identity(retained, label=label))
    if reopened != raw:
        _fail(f"{label} post-publication exact reopen differs")
    return retained


def _replay_panel(
    *, panel_index_identity: object, lane_terminal_identities: Sequence[object],
    read_exact: ReadExact,
) -> dict[str, object]:
    raw_terminals = _sequence(lane_terminal_identities, label="lane terminals")
    if len(raw_terminals) != 2:
        _fail("the release requires exactly two Gate-G0 lane terminals")
    terminals = [
        _identity(value, label=f"lane terminal[{ordinal}]")
        for ordinal, value in enumerate(raw_terminals)
    ]
    try:
        lanes = [
            panel_index.derive_v12_lane_input(
                lane_ordinal=ordinal,
                lane_id=str(panel_index.V12_LANE_LATTICE[ordinal]["lane_id"]),
                terminal_receipt_identity=terminals[ordinal],
                read_exact=read_exact,
            )
            for ordinal in range(2)
        ]
        panel = panel_index.reopen_v12_panel_index(
            panel_index_identity=_identity(
                panel_index_identity, label="Gate-G0 panel index"
            ),
            lane_inputs=lanes,
            read_exact=read_exact,
        )
    except Exception as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
            "Gate-G0 panel did not exact-replay from both lane terminals"
        ) from exc
    item = _mapping(panel, label="Gate-G0 panel")
    members = _sequence(item.get("accepted_slates"), label="panel members")
    coverage = _mapping(item.get("coverage"), label="panel coverage")
    if (
        item.get("schema_version") != panel_index.PANEL_INDEX_SCHEMA
        or item.get("accepted_slate_count") != AUTHORITATIVE_SLATE_COUNT
        or len(members) != AUTHORITATIVE_SLATE_COUNT
        or item.get("exclusions") != []
        or item.get("failures") != []
        or item.get("missing_tasks") != []
        or coverage.get("expected_task_count") != AUTHORITATIVE_SLATE_COUNT
        or coverage.get("accepted_task_count") != AUTHORITATIVE_SLATE_COUNT
        or coverage.get("complete") is not True
        or item.get("uses_realized_outcomes") is not False
    ):
        _fail("Gate-G0 panel is not the complete outcome-blind 54-slate panel")
    _validate_self_hash(item, field="panel_index_sha256", label="Gate-G0 panel")
    return item


def _reopen_source_release_structure(
    *, identity: object, read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    row = _identity(identity, label="candidate-rooted matchup release")
    try:
        raw = read_exact(row)
        parsed = batch.parse_canonical_json_bytes(
            raw, label="candidate-rooted matchup release"
        )
        root = source_release_v2.validate_matchup_source_release_candidate_authority_v2(
            parsed
        )
    except Exception as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
            "candidate-rooted matchup release structure exact reopen failed"
        ) from exc
    _bind_identity_to_body(row, root, label="candidate-rooted matchup release")
    expected_uri = f"{root['namespace']}{source_release_v2.ROOT_FILENAME}"
    if row["uri"] != expected_uri or root.get("task_count") != AUTHORITATIVE_SLATE_COUNT:
        _fail("candidate-rooted matchup release namespace/count differs")
    return row, root


def _source_members(
    *, panel: Mapping[str, object], source_root: Mapping[str, object],
    output_prefix: str,
) -> list[dict[str, object]]:
    panel_members = _sequence(panel.get("accepted_slates"), label="panel members")
    source_entries = _sequence(source_root.get("entries"), label="source entries")
    if len(panel_members) != 54 or len(source_entries) != 54:
        _fail("panel/source member counts differ from 54")
    rows: list[dict[str, object]] = []
    seen_slates: set[str] = set()
    for ordinal, (raw_panel, raw_source) in enumerate(
        zip(panel_members, source_entries, strict=True)
    ):
        panel_member = _mapping(raw_panel, label=f"panel member[{ordinal}]")
        source_member = _mapping(raw_source, label=f"source member[{ordinal}]")
        slate = _mapping(source_member.get("slate"), label=f"source slate[{ordinal}]")
        slate_id = panel_member.get("slate_id")
        if (
            type(slate_id) is not str
            or not slate_id
            or slate_id in seen_slates
            or panel_member.get("source_task_ordinal") != ordinal
            or source_member.get("source_task_ordinal") != ordinal
            or slate.get("slate_id") != slate_id
        ):
            _fail(f"panel/source ordinal[{ordinal}] identity differs")
        seen_slates.add(slate_id)
        member_prefix = f"{output_prefix}slates/{ordinal:02d}-{slate_id}/"
        rows.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "task_id": source_member["task_id"],
            "panel_member_sha256": batch.canonical_sha256(panel_member),
            "task_acceptance_identity": _identity(
                panel_member["task_acceptance_identity"],
                label=f"panel task acceptance[{ordinal}]",
            ),
            "carrier_identity": _identity(
                panel_member["carrier_identity"],
                label=f"panel carrier[{ordinal}]",
            ),
            "matchup_source_member_sha256": _digest(
                source_member[
                    "matchup_source_member_candidate_authority_sha256"
                ],
                label=f"source member SHA[{ordinal}]",
            ),
            "candidate_artifact_identity": _identity(
                source_member["candidate_artifact_identity"],
                label=f"candidate artifact[{ordinal}]",
            ),
            "candidate_artifact_sha256": _digest(
                source_member["candidate_artifact_sha256"],
                label=f"candidate artifact SHA[{ordinal}]",
            ),
            "candidate_count": source_member["candidate_count"],
            "ordered_candidate_ids_sha256": _digest(
                source_member["ordered_candidate_ids_sha256"],
                label=f"candidate order SHA[{ordinal}]",
            ),
            "worker_result_uri": f"{member_prefix}worker-result.json",
            "acceptance_uri": f"{member_prefix}verified-acceptance.json",
        })
    return rows


def _build_manifest(
    *, panel_index_identity: object, panel: Mapping[str, object],
    lane_terminal_identities: Sequence[object],
    matchup_source_release_identity: object,
    matchup_source_release: Mapping[str, object],
    runtime_image_authority_identity: object,
    runtime_image_authority: Mapping[str, object], output_prefix: str,
) -> dict[str, object]:
    panel_identity = _bind_identity_to_body(
        panel_index_identity, panel, label="Gate-G0 panel index"
    )
    source_identity = _bind_identity_to_body(
        matchup_source_release_identity,
        matchup_source_release,
        label="candidate-rooted matchup release",
    )
    image_authority = validate_provider_runtime_image_authority_v1(
        runtime_image_authority
    )
    image_authority_identity = _bind_identity_to_body(
        runtime_image_authority_identity,
        image_authority,
        label="provider runtime image authority",
    )
    source_commit_sha = str(image_authority["source_commit_sha"])
    immutable_image = str(image_authority["immutable_image"])
    prefix = _output_prefix(output_prefix)
    terminals = [
        _identity(value, label=f"lane terminal[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(lane_terminal_identities, label="lane terminals")
        )
    ]
    if len(terminals) != 2:
        _fail("manifest requires exactly two lane terminals")
    lanes = _sequence(panel.get("lanes"), label="panel lanes")
    if len(lanes) != 2 or terminals != [
        _identity(
            _mapping(lanes[index], label=f"panel lane[{index}]")[
                "terminal_receipt_identity"
            ],
            label=f"panel lane terminal[{index}]",
        )
        for index in range(2)
    ]:
        _fail("manifest lane terminals differ from Gate G0")
    members = _source_members(
        panel=panel, source_root=matchup_source_release, output_prefix=prefix
    )
    seed = {
        "panel_index_identity": panel_identity,
        "matchup_source_release_identity": source_identity,
        "runtime_image_authority_identity": image_authority_identity,
        "provider_runtime_image_authority_sha256": image_authority[
            "provider_runtime_image_authority_sha256"
        ],
        "output_prefix": prefix,
    }
    body: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "manifest_id": "r6-v2-matchup-candidate:" + batch.canonical_sha256(seed),
        "panel_index_identity": panel_identity,
        "panel_index_sha256": panel["panel_index_sha256"],
        "lane_terminal_identities": terminals,
        "matchup_source_release_identity": source_identity,
        "matchup_source_release_sha256": matchup_source_release[
            "matchup_source_release_candidate_authority_sha256"
        ],
        "runtime_image_authority_identity": image_authority_identity,
        "provider_runtime_image_authority_sha256": image_authority[
            "provider_runtime_image_authority_sha256"
        ],
        "embedded_runtime_authority_sha256": image_authority[
            "embedded_runtime_authority_sha256"
        ],
        "critical_runtime_paths_sha256": image_authority[
            "critical_runtime_paths_sha256"
        ],
        "critical_runtime_files_sha256": image_authority[
            "critical_runtime_files_sha256"
        ],
        "source_commit_sha": source_commit_sha,
        "immutable_image": immutable_image,
        "critical_runtime_paths": list(CRITICAL_RUNTIME_PATHS),
        "source_member_count": len(members),
        "source_members": members,
        "source_members_sha256": batch.canonical_sha256(members),
        "execution_lattice": {
            "fit_scope_ids": list(FIT_SCOPE_IDS),
            "scope_count": len(FIT_SCOPE_IDS),
            "books_per_scope": BOOKS_PER_SCOPE,
            "books_per_slate": BOOKS_PER_SLATE,
            "entry_budget": ENTRY_BUDGET,
            "prefix_sizes": list(PREFIX_SIZES),
            "prefixes_per_slate": PREFIXES_PER_SLATE,
            "admission_cap": ADMISSION_CAP,
            "neutral_replicates": NEUTRAL_REPLICATES,
            "neutral_seed_root": NEUTRAL_SEED_ROOT,
            "worlds_per_block": WORLDS_PER_BLOCK,
            "worker_requires_distinct_verifier_process": True,
        },
        "output_prefix": prefix,
        "terminal_root_uri": f"{prefix}accepted-root.json",
        **_policy(),
    }
    return _with_hash(body, field="execution_manifest_sha256")


def prepare_release_v2(
    *, storage: ExactObjectStore, panel_index_identity: object,
    lane_terminal_identities: Sequence[object],
    matchup_source_release_identity: object,
    runtime_image_authority_identity: object, output_prefix: str,
) -> dict[str, object]:
    """Exact-replay both complete roots and publish one deterministic manifest."""
    read_exact = _read_exact_callback(storage)
    panel = _replay_panel(
        panel_index_identity=panel_index_identity,
        lane_terminal_identities=lane_terminal_identities,
        read_exact=read_exact,
    )
    source_identity, source_root = _reopen_source_release_structure(
        identity=matchup_source_release_identity, read_exact=read_exact
    )
    image_authority_identity, image_authority = _read_json(
        storage,
        runtime_image_authority_identity,
        label="provider runtime image authority",
    )
    image_authority = validate_provider_runtime_image_authority_v1(
        image_authority
    )
    manifest = _build_manifest(
        panel_index_identity=panel_index_identity,
        panel=panel,
        lane_terminal_identities=lane_terminal_identities,
        matchup_source_release_identity=source_identity,
        matchup_source_release=source_root,
        runtime_image_authority_identity=image_authority_identity,
        runtime_image_authority=image_authority,
        output_prefix=output_prefix,
    )
    identity = _publish_or_recover(
        storage,
        uri=f"{_output_prefix(output_prefix)}execution-manifest.json",
        value=manifest,
        label="analysis execution manifest",
    )
    _, reopened, _, _ = reopen_manifest_v2(storage=storage, manifest_identity=identity)
    if batch.canonical_json_bytes(reopened) != batch.canonical_json_bytes(manifest):
        _fail("published analysis manifest canonical replay differs")
    return _with_hash({
        "schema_version": PREPARE_RECEIPT_SCHEMA,
        "manifest_identity": identity,
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "source_slate_count": AUTHORITATIVE_SLATE_COUNT,
        "rank_80_book_count": PANEL_BOOK_COUNT,
        "prefix_count": PANEL_PREFIX_COUNT,
        **_policy(),
    }, field="prepare_receipt_sha256")


def reopen_manifest_v2(
    *, storage: ExactObjectStore, manifest_identity: object,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object], dict[str, object]
]:
    retained_identity, manifest = _read_json(
        storage, manifest_identity, label="analysis execution manifest"
    )
    _validate_self_hash(
        manifest, field="execution_manifest_sha256", label="analysis manifest"
    )
    _validate_policy(manifest, label="analysis manifest")
    if (
        retained_identity["uri"]
        != f"{manifest.get('output_prefix')}execution-manifest.json"
        or manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("publication_mode") != PUBLICATION_MODE
        or manifest.get("source_member_count") != AUTHORITATIVE_SLATE_COUNT
        or manifest.get("critical_runtime_paths") != list(CRITICAL_RUNTIME_PATHS)
    ):
        _fail("analysis manifest schema/path/count differs")
    read_exact = _read_exact_callback(storage)
    panel = _replay_panel(
        panel_index_identity=manifest["panel_index_identity"],
        lane_terminal_identities=manifest["lane_terminal_identities"],
        read_exact=read_exact,
    )
    source_identity, source_root = _reopen_source_release_structure(
        identity=manifest["matchup_source_release_identity"], read_exact=read_exact
    )
    image_authority_identity, image_authority = _read_json(
        storage,
        manifest.get("runtime_image_authority_identity"),
        label="provider runtime image authority",
    )
    image_authority = validate_provider_runtime_image_authority_v1(
        image_authority
    )
    expected = _build_manifest(
        panel_index_identity=manifest["panel_index_identity"],
        panel=panel,
        lane_terminal_identities=manifest["lane_terminal_identities"],
        matchup_source_release_identity=source_identity,
        matchup_source_release=source_root,
        runtime_image_authority_identity=image_authority_identity,
        runtime_image_authority=image_authority,
        output_prefix=str(manifest["output_prefix"]),
    )
    if batch.canonical_json_bytes(expected) != batch.canonical_json_bytes(manifest):
        _fail("analysis manifest canonical dependency replay differs")
    return retained_identity, expected, panel, source_root


def _process_start_ticks(pid: int) -> int:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        value = int(raw.rsplit(") ", 1)[1].split()[19])
    except (OSError, ValueError, IndexError) as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
            "cannot measure process start identity"
        ) from exc
    if value < 1:
        _fail("process start identity differs")
    return value


def _current_process_runtime_v2(*, role: str) -> dict[str, object]:
    if role not in {"ordinal-worker", "independent-verifier"}:
        _fail("process runtime role differs")
    try:
        boot = Path("/proc/sys/kernel/random/boot_id").read_text(
            encoding="utf-8"
        ).strip()
        namespace = os.readlink("/proc/self/ns/pid")
    except OSError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
            "cannot measure process host/namespace identity"
        ) from exc
    pid = os.getpid()
    body = {
        "schema_version": PROCESS_RUNTIME_SCHEMA,
        "role": role,
        "pid": pid,
        "process_start_ticks": _process_start_ticks(pid),
        "boot_id_sha256": sha256(boot.encode("utf-8")).hexdigest(),
        "pid_namespace_sha256": sha256(namespace.encode("utf-8")).hexdigest(),
    }
    return _with_hash(body, field="process_runtime_sha256")


def _validate_process_runtime(value: object, *, role: str) -> dict[str, object]:
    item = _mapping(value, label=f"{role} process runtime")
    _exact_keys(item, frozenset({
        "schema_version", "role", "pid", "process_start_ticks",
        "boot_id_sha256", "pid_namespace_sha256", "process_runtime_sha256",
    }), label=f"{role} process runtime")
    _validate_self_hash(
        item, field="process_runtime_sha256", label=f"{role} process runtime"
    )
    if (
        item.get("schema_version") != PROCESS_RUNTIME_SCHEMA
        or item.get("role") != role
        or type(item.get("pid")) is not int
        or int(item["pid"]) < 1
        or type(item.get("process_start_ticks")) is not int
        or int(item["process_start_ticks"]) < 1
        or _SHA256.fullmatch(str(item.get("boot_id_sha256"))) is None
        or _SHA256.fullmatch(str(item.get("pid_namespace_sha256"))) is None
    ):
        _fail(f"{role} process runtime structure differs")
    return item


def _process_instance_key(
    value: Mapping[str, object],
) -> tuple[str, str, int, int]:
    return (
        str(value["boot_id_sha256"]),
        str(value["pid_namespace_sha256"]),
        int(value["pid"]),
        int(value["process_start_ticks"]),
    )


def _runtime_module_origins_v1() -> dict[str, Path]:
    origins: dict[str, Path] = {}
    try:
        for relative_path in _DIRECT_RUNTIME_PATHS:
            if not relative_path.startswith("src/") or not relative_path.endswith(
                ".py"
            ):
                continue
            module_name = relative_path[4:-3].replace("/", ".")
            importlib.import_module(module_name)
        for module_name, module in list(sys.modules.items()):
            if module_name != "nfl_dfs" and not module_name.startswith(
                "nfl_dfs."
            ):
                continue
            origin = getattr(module, "__file__", None)
            if type(origin) is not str or not origin:
                _fail(f"runtime module {module_name!r} has no file origin")
            origin_path = Path(origin).resolve(strict=True)
            if origin_path.name == "__init__.py":
                relative_path = (
                    "src/" + module_name.replace(".", "/") + "/__init__.py"
                )
            else:
                relative_path = "src/" + module_name.replace(".", "/") + ".py"
            if relative_path in origins and origins[relative_path] != origin_path:
                _fail(f"runtime module {module_name!r} origin is ambiguous")
            origins[relative_path] = origin_path
    except (ImportError, OSError, RuntimeError) as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
            "runtime imported-module origin measurement failed"
        ) from exc
    return origins


def _runtime_repository_callbacks_v1(
    *, repository_root: Path,
    embedded_runtime_authority: Mapping[str, object],
) -> tuple[GitHead, GitBlob, GitStatus]:
    embedded = validate_embedded_runtime_authority_v1(
        embedded_runtime_authority
    )
    root = repository_root.resolve(strict=True)
    by_path = {
        str(row["relative_path"]): dict(row)
        for row in embedded["file_measurements"]
    }

    def _same_root(value: Path) -> None:
        if not isinstance(value, Path) or value.resolve(strict=True) != root:
            _fail("runtime tracked-source root differs")

    def _read_current(relative_path: str) -> bytes:
        expected = by_path.get(relative_path)
        if expected is None:
            _fail(f"runtime tracked blob is outside embedded authority: {relative_path}")
        measured, raw = _runtime_file_measurement(root, relative_path)
        if measured != expected:
            _fail(f"runtime tracked blob drifted: {relative_path}")
        return raw

    def head(value: Path) -> str:
        _same_root(value)
        return str(embedded["source_commit_sha"])

    def blob(value: Path, commit: str, relative_path: str) -> bytes:
        _same_root(value)
        if commit != embedded["source_commit_sha"]:
            _fail(
                "historical tracked blob is absent from embedded runtime authority"
            )
        return _read_current(relative_path)

    def status(value: Path, relative_paths: Sequence[str]) -> bytes:
        _same_root(value)
        paths = _sequence(relative_paths, label="runtime tracked status paths")
        if any(type(path) is not str for path in paths):
            _fail("runtime tracked status paths differ")
        for relative_path in paths:
            _read_current(str(relative_path))
        return b""

    return head, blob, status


def validate_runtime_files_v1(
    *, repository_root: Path, embedded_runtime_authority: object,
) -> dict[str, object]:
    """Validate image bytes and imported origins without invoking Git."""
    if not isinstance(repository_root, Path) or not repository_root.is_absolute():
        _fail("runtime repository root differs")
    embedded = validate_embedded_runtime_authority_v1(
        embedded_runtime_authority
    )
    try:
        root = repository_root.resolve(strict=True)
    except OSError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
            "runtime repository root cannot be resolved"
        ) from exc
    expected_by_path = {
        str(row["relative_path"]): dict(row)
        for row in embedded["file_measurements"]
    }
    for relative_path in CRITICAL_RUNTIME_PATHS:
        measured, _ = _runtime_file_measurement(root, relative_path)
        if measured != expected_by_path[relative_path]:
            _fail(f"runtime critical file drifted: {relative_path}")
    origins = _runtime_module_origins_v1()
    measured_source_paths = {
        path for path in CRITICAL_RUNTIME_PATHS if path.startswith("src/")
    }
    required_direct_origins = {
        path for path in _DIRECT_RUNTIME_PATHS if path.startswith("src/")
    }
    if (
        not required_direct_origins <= set(origins)
        or not set(origins) <= measured_source_paths
        or any(
            origin != root / relative_path
            for relative_path, origin in origins.items()
        )
    ):
        _fail("runtime scientific module origin differs from embedded authority")
    return embedded


def _validate_runtime_binding(
    *, manifest: Mapping[str, object], repository_root: Path,
    embedded_runtime_authority: object,
) -> tuple[GitHead, GitBlob, GitStatus]:
    embedded = validate_runtime_files_v1(
        repository_root=repository_root,
        embedded_runtime_authority=embedded_runtime_authority,
    )
    if (
        embedded.get("source_commit_sha") != manifest.get("source_commit_sha")
        or embedded.get("runtime_authority_sha256")
        != manifest.get("embedded_runtime_authority_sha256")
        or embedded.get("critical_runtime_paths_sha256")
        != manifest.get("critical_runtime_paths_sha256")
        or embedded.get("critical_runtime_files_sha256")
        != manifest.get("critical_runtime_files_sha256")
    ):
        _fail("runtime authority differs from provider-bound manifest")
    root = repository_root.resolve(strict=True)
    return _runtime_repository_callbacks_v1(
        repository_root=root,
        embedded_runtime_authority=embedded,
    )


def _book_catalog(task_result: Mapping[str, object]) -> dict[str, object]:
    result = _mapping(task_result, label="candidate-rooted R6 task result")
    _validate_self_hash(
        result, field="task_result_sha256", label="candidate-rooted R6 task result"
    )
    surface = _mapping(result.get("retrieval_surface"), label="retrieval surface")
    _validate_self_hash(
        surface, field="retrieval_surface_sha256", label="retrieval surface"
    )
    folds = _sequence(surface.get("folds"), label="retrieval folds")
    scopes = [*folds, surface.get("final_fit")]
    if (
        surface.get("schema_version") != runner.RUNNER_SCHEMA
        or len(folds) != len(rw.WORLD_BLOCKS)
        or surface.get("fold_count") != len(rw.WORLD_BLOCKS)
        or surface.get("books_per_scope") != BOOKS_PER_SCOPE
        or surface.get("cross_fit_book_count") != 5 * BOOKS_PER_SCOPE
        or surface.get("final_fit_book_count") != BOOKS_PER_SCOPE
        or surface.get("neutral_replicate_count") != NEUTRAL_REPLICATES
        or surface.get("worlds_per_block") != WORLDS_PER_BLOCK
        or surface.get("admission_cap") != ADMISSION_CAP
        or surface.get("dose_authority") != runner.AUTHORITATIVE_DOSE
        or surface.get("require_authoritative") is not True
        or surface.get("final_fit_is_distinct_all-block-refit") is not True
        or surface.get("uses_realized_outcomes") is not False
        or surface.get("promotion_authority") is not False
    ):
        _fail("retrieval surface does not preserve the authoritative 276-book dose")
    slate = _mapping(surface.get("slate"), label="retrieval slate")
    descriptors: list[dict[str, object]] = []
    seen_books: set[str] = set()
    for scope_ordinal, raw_scope in enumerate(scopes):
        scope = _mapping(raw_scope, label=f"fit scope[{scope_ordinal}]")
        _validate_self_hash(
            scope, field="fit_scope_sha256", label=f"fit scope[{scope_ordinal}]"
        )
        expected_scope = FIT_SCOPE_IDS[scope_ordinal]
        expected_heldout = (
            rw.WORLD_BLOCKS[scope_ordinal] if scope_ordinal < 5 else None
        )
        books = _sequence(scope.get("books"), label=f"scope books[{scope_ordinal}]")
        if (
            scope.get("schema_version") != runner.SCOPE_SCHEMA
            or scope.get("fit_scope_id") != expected_scope
            or scope.get("heldout_block") != expected_heldout
            or scope.get("book_count") != BOOKS_PER_SCOPE
            or len(books) != BOOKS_PER_SCOPE
            or scope.get("uses_realized_outcomes") is not False
            or scope.get("promotion_authority") is not False
        ):
            _fail(f"fit scope[{scope_ordinal}] lattice differs")
        for scope_book_ordinal, raw_book in enumerate(books):
            book = _mapping(
                raw_book,
                label=f"book[{scope_ordinal},{scope_book_ordinal}]",
            )
            book_sha = _validate_self_hash(
                book,
                field="book_sha256",
                label=f"book[{scope_ordinal},{scope_book_ordinal}]",
            )
            book_id = book.get("book_id")
            selected_ids = _sequence(
                book.get("selected_lineup_ids"), label="selected lineup IDs"
            )
            selected_rosters = _sequence(
                book.get("selected_rosters"), label="selected rosters"
            )
            if (
                book.get("schema_version") != runner.BOOK_SCHEMA
                or type(book_id) is not str
                or not book_id
                or book_id in seen_books
                or book.get("fit_scope_id") != expected_scope
                or book.get("entry_count") != ENTRY_BUDGET
                or len(selected_ids) != ENTRY_BUDGET
                or len(set(selected_ids)) != ENTRY_BUDGET
                or len(selected_rosters) != ENTRY_BUDGET
                or book.get("uses_realized_outcomes") is not False
                or book.get("promotion_authority") is not False
            ):
                _fail("retrieval book rank-80 identity differs")
            seen_books.add(book_id)
            normalized_rosters: list[list[str]] = []
            for rank, (lineup_id, raw_roster) in enumerate(
                zip(selected_ids, selected_rosters, strict=True)
            ):
                roster = [str(value) for value in _sequence(
                    raw_roster, label=f"selected roster[{rank}]"
                )]
                if (
                    type(lineup_id) is not str
                    or not lineup_id
                    or len(roster) != 9
                    or roster != sorted(set(roster))
                    or canonical_lineup_id(slate, roster) != lineup_id
                ):
                    _fail("retrieval book lineup/roster order differs")
                normalized_rosters.append(roster)
            rank_80_sha = batch.canonical_sha256({
                "selected_lineup_ids": selected_ids,
                "selected_rosters": normalized_rosters,
            })
            prefixes: list[dict[str, object]] = []
            for size in PREFIX_SIZES:
                prefix = _with_hash({
                    "schema_version": PREFIX_SCHEMA,
                    "entry_count": size,
                    "prefix_of_rank_80": True,
                    "rank_80_sha256": rank_80_sha,
                    "selected_lineup_ids": selected_ids[:size],
                    "selected_rosters": normalized_rosters[:size],
                    "selected_lineup_ids_sha256": batch.canonical_sha256(
                        selected_ids[:size]
                    ),
                    "selected_rosters_sha256": batch.canonical_sha256(
                        normalized_rosters[:size]
                    ),
                }, field="prefix_sha256")
                prefixes.append(prefix)
            descriptor = _with_hash({
                "schema_version": BOOK_DESCRIPTOR_SCHEMA,
                "book_ordinal": len(descriptors),
                "fit_scope_ordinal": scope_ordinal,
                "fit_scope_id": expected_scope,
                "scope_book_ordinal": scope_book_ordinal,
                "book_id": book_id,
                "admission_id": book.get("admission_id"),
                "strategy_id": book.get("strategy_id"),
                "book_sha256": book_sha,
                "rank_80_sha256": rank_80_sha,
                "entry_count": ENTRY_BUDGET,
                "prefix_sizes": list(PREFIX_SIZES),
                "prefixes": prefixes,
                "prefix_count": len(prefixes),
            }, field="book_descriptor_sha256")
            descriptors.append(descriptor)
    if len(descriptors) != BOOKS_PER_SLATE:
        _fail("derived book catalog does not contain exactly 276 books")
    body = {
        "schema_version": BOOK_CATALOG_SCHEMA,
        "task_result_sha256": result["task_result_sha256"],
        "retrieval_surface_sha256": surface["retrieval_surface_sha256"],
        "fit_scope_ids": list(FIT_SCOPE_IDS),
        "scope_count": len(FIT_SCOPE_IDS),
        "book_count": len(descriptors),
        "books": descriptors,
        "prefix_sizes": list(PREFIX_SIZES),
        "prefix_count": sum(int(row["prefix_count"]) for row in descriptors),
        "prefix_roster_occurrence_counts": {
            str(size): BOOKS_PER_SLATE * size for size in PREFIX_SIZES
        },
        **_policy(),
    }
    return _with_hash(body, field="book_catalog_sha256")


def _validate_task_result_shell(
    task_result: object, *, manifest: Mapping[str, object],
    source_ordinal: int,
) -> dict[str, object]:
    result = _mapping(task_result, label="candidate-rooted task result")
    _validate_self_hash(
        result, field="task_result_sha256", label="candidate-rooted task result"
    )
    _reject_outcome_carriers(result, label="candidate-rooted task result")
    member = _mapping(
        _sequence(manifest["source_members"], label="manifest source members")[
            source_ordinal
        ],
        label="manifest source member",
    )
    projection = _mapping(
        result.get("matchup_source_projection"), label="matchup source projection"
    )
    configuration = _mapping(result.get("configuration"), label="task configuration")
    verification = _mapping(result.get("verification"), label="task verification")
    if (
        result.get("schema_version") != consumer.RESULT_SCHEMA
        or result.get("source_task_ordinal") != source_ordinal
        or result.get("slate_id") != member["slate_id"]
        or result.get("panel_index_identity") != manifest["panel_index_identity"]
        or projection.get("source_release_identity")
        != manifest["matchup_source_release_identity"]
        or configuration != {
            "minimum_supported_players": MINIMUM_SUPPORTED_PLAYERS,
            "minimum_completeness": MINIMUM_COMPLETENESS,
            "admission_m": ADMISSION_CAP,
            "neutral_replicates": NEUTRAL_REPLICATES,
            "neutral_seed_root": NEUTRAL_SEED_ROOT,
            "worlds_per_block": WORLDS_PER_BLOCK,
            "require_authoritative": True,
        }
        or result.get("outcome_columns_read") != []
        or result.get("uses_realized_outcomes") is not False
        or any(
            result.get(field) is not False
            for field in _FALSE_AUTHORITY_FIELDS
            if field != "uses_realized_outcomes"
        )
        or any(
            verification.get(field) is not True
            for field in (
                "candidate_rooted_source_release_exact_reopened",
                "candidate_root_full_predecessor_replay_verified",
                "selected_candidate_artifact_exact_reopened",
                "authorized_candidate_order_matches_scored_matrix_verified",
                "full_seven_law_fold_final_surface_canonical_replay_verified",
                "canonical_authoritative_dose_verified",
            )
        )
    ):
        _fail("candidate-rooted task result release binding differs")
    return result


def _executor_inputs(
    *, manifest: Mapping[str, object], panel: Mapping[str, object],
    source_ordinal: int, repository_root: Path, read_exact: ReadExact,
    git_head: GitHead, git_blob: GitBlob, git_status: GitStatus,
) -> dict[str, object]:
    panel_members = _sequence(panel["accepted_slates"], label="panel members")
    panel_member = _mapping(
        panel_members[source_ordinal], label=f"panel member[{source_ordinal}]"
    )
    return {
        "validated_panel_index": panel,
        "panel_index_identity": manifest["panel_index_identity"],
        "accepted_slate_membership": panel_member,
        "task_acceptance_identity": panel_member["task_acceptance_identity"],
        "carrier_identity": panel_member["carrier_identity"],
        "matchup_source_release_identity": manifest[
            "matchup_source_release_identity"
        ],
        "source_task_ordinal": source_ordinal,
        "repository_root": repository_root,
        "read_exact": read_exact,
        "git_head": git_head,
        "git_blob": git_blob,
        "git_status": git_status,
        "minimum_supported_players": MINIMUM_SUPPORTED_PLAYERS,
        "minimum_completeness": MINIMUM_COMPLETENESS,
        "admission_m": ADMISSION_CAP,
        "neutral_replicates": NEUTRAL_REPLICATES,
        "neutral_seed_root": NEUTRAL_SEED_ROOT,
        "worlds_per_block": None,
        "require_authoritative": True,
    }


def _build_worker_result(
    *, manifest_identity: Mapping[str, object], manifest: Mapping[str, object],
    source_ordinal: int, worker_runtime: Mapping[str, object],
    task_result: Mapping[str, object], book_catalog: Mapping[str, object],
) -> dict[str, object]:
    member = _mapping(
        _sequence(manifest["source_members"], label="manifest source members")[
            source_ordinal
        ],
        label="manifest source member",
    )
    body = {
        "schema_version": WORKER_RESULT_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "target_uri": member["worker_result_uri"],
        "manifest_identity": dict(manifest_identity),
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "source_ordinal": source_ordinal,
        "slate_id": member["slate_id"],
        "panel_member_sha256": member["panel_member_sha256"],
        "matchup_source_release_identity": manifest[
            "matchup_source_release_identity"
        ],
        "matchup_source_member_sha256": member["matchup_source_member_sha256"],
        "worker_process_runtime": dict(worker_runtime),
        "worker_process_runtime_sha256": worker_runtime["process_runtime_sha256"],
        "task_result": dict(task_result),
        "task_result_sha256": task_result["task_result_sha256"],
        "book_catalog": dict(book_catalog),
        "book_catalog_sha256": book_catalog["book_catalog_sha256"],
        "scope_count": len(FIT_SCOPE_IDS),
        "rank_80_book_count": BOOKS_PER_SLATE,
        "prefix_sizes": list(PREFIX_SIZES),
        "prefix_count": PREFIXES_PER_SLATE,
        "complete": True,
        **_policy(),
    }
    return _with_hash(body, field="worker_result_sha256")


def _validate_worker_result(
    value: object, *, identity: object, manifest_identity: Mapping[str, object],
    manifest: Mapping[str, object], source_ordinal: int,
) -> dict[str, object]:
    item = _mapping(value, label=f"worker result[{source_ordinal}]")
    _exact_keys(item, frozenset({
        "schema_version", "publication_mode", "target_uri", "manifest_identity",
        "execution_manifest_sha256", "source_ordinal", "slate_id",
        "panel_member_sha256", "matchup_source_release_identity",
        "matchup_source_member_sha256", "worker_process_runtime",
        "worker_process_runtime_sha256", "task_result", "task_result_sha256",
        "book_catalog", "book_catalog_sha256", "scope_count",
        "rank_80_book_count", "prefix_sizes", "prefix_count", "complete",
        "outcome_columns_read", *_FALSE_AUTHORITY_FIELDS, "worker_result_sha256",
    }), label="worker result")
    _validate_self_hash(item, field="worker_result_sha256", label="worker result")
    _validate_policy(item, label="worker result")
    worker_identity = _bind_identity_to_body(identity, item, label="worker result")
    member = _mapping(
        _sequence(manifest["source_members"], label="manifest source members")[
            source_ordinal
        ],
        label="manifest source member",
    )
    runtime = _validate_process_runtime(
        item["worker_process_runtime"], role="ordinal-worker"
    )
    task_result = _validate_task_result_shell(
        item["task_result"], manifest=manifest, source_ordinal=source_ordinal
    )
    catalog = _book_catalog(task_result)
    if (
        item.get("schema_version") != WORKER_RESULT_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
        or worker_identity["uri"] != member["worker_result_uri"]
        or item.get("target_uri") != member["worker_result_uri"]
        or item.get("manifest_identity") != manifest_identity
        or item.get("execution_manifest_sha256")
        != manifest["execution_manifest_sha256"]
        or item.get("source_ordinal") != source_ordinal
        or item.get("slate_id") != member["slate_id"]
        or item.get("panel_member_sha256") != member["panel_member_sha256"]
        or item.get("matchup_source_release_identity")
        != manifest["matchup_source_release_identity"]
        or item.get("matchup_source_member_sha256")
        != member["matchup_source_member_sha256"]
        or item.get("worker_process_runtime_sha256")
        != runtime["process_runtime_sha256"]
        or item.get("task_result_sha256") != task_result["task_result_sha256"]
        or item.get("book_catalog") != catalog
        or item.get("book_catalog_sha256") != catalog["book_catalog_sha256"]
        or item.get("scope_count") != 6
        or item.get("rank_80_book_count") != BOOKS_PER_SLATE
        or item.get("prefix_sizes") != list(PREFIX_SIZES)
        or item.get("prefix_count") != PREFIXES_PER_SLATE
        or item.get("complete") is not True
    ):
        _fail("worker result manifest/source/book binding differs")
    return item


def _reopen_worker_result(
    *, storage: ExactObjectStore, identity: object,
    manifest_identity: Mapping[str, object], manifest: Mapping[str, object],
    source_ordinal: int,
) -> tuple[dict[str, object], dict[str, object]]:
    retained, body = _read_json(
        storage, identity, label=f"worker result[{source_ordinal}]"
    )
    return retained, _validate_worker_result(
        body,
        identity=retained,
        manifest_identity=manifest_identity,
        manifest=manifest,
        source_ordinal=source_ordinal,
    )


def run_worker_v2(
    *, storage: ExactObjectStore, manifest_identity: object, source_ordinal: int,
    repository_root: Path,
    execute: ExecuteOrdinal = (
        consumer.execute_r6_v2_matchup_candidate_authority_ordinal_v2
    ),
) -> dict[str, object]:
    """Execute and create one outcome-blind worker result."""
    if type(source_ordinal) is not int or not 0 <= source_ordinal < 54:
        _fail("worker source ordinal must be one exact integer in 0..53")
    retained_manifest, manifest, panel, _ = reopen_manifest_v2(
        storage=storage, manifest_identity=manifest_identity
    )
    embedded_runtime_authority = load_image_embedded_runtime_authority_v1()
    git_head, git_blob, git_status = _validate_runtime_binding(
        manifest=manifest,
        repository_root=repository_root,
        embedded_runtime_authority=embedded_runtime_authority,
    )
    member = _mapping(
        _sequence(manifest["source_members"], label="manifest source members")[
            source_ordinal
        ],
        label="manifest source member",
    )
    existing = storage.resolve_optional(str(member["worker_result_uri"]))
    if existing is not None:
        worker_identity, worker = _reopen_worker_result(
            storage=storage,
            identity=existing[0].as_dict(),
            manifest_identity=retained_manifest,
            manifest=manifest,
            source_ordinal=source_ordinal,
        )
        recovered = True
    else:
        runtime = _current_process_runtime_v2(role="ordinal-worker")
        inputs = _executor_inputs(
            manifest=manifest,
            panel=panel,
            source_ordinal=source_ordinal,
            repository_root=repository_root,
            read_exact=_read_exact_callback(storage),
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
        try:
            task_result = execute(**inputs)
        except Exception as exc:
            raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
                f"candidate-rooted R6 worker[{source_ordinal}] failed closed"
            ) from exc
        validated_task = _validate_task_result_shell(
            task_result, manifest=manifest, source_ordinal=source_ordinal
        )
        catalog = _book_catalog(validated_task)
        worker = _build_worker_result(
            manifest_identity=retained_manifest,
            manifest=manifest,
            source_ordinal=source_ordinal,
            worker_runtime=runtime,
            task_result=validated_task,
            book_catalog=catalog,
        )
        worker_identity = _publish_or_recover(
            storage,
            uri=str(member["worker_result_uri"]),
            value=worker,
            label=f"worker result[{source_ordinal}]",
        )
        _, worker = _reopen_worker_result(
            storage=storage,
            identity=worker_identity,
            manifest_identity=retained_manifest,
            manifest=manifest,
            source_ordinal=source_ordinal,
        )
        recovered = False
    return _with_hash({
        "schema_version": WORKER_RECEIPT_SCHEMA,
        "manifest_identity": retained_manifest,
        "source_ordinal": source_ordinal,
        "slate_id": worker["slate_id"],
        "worker_result_identity": worker_identity,
        "worker_result_sha256": worker["worker_result_sha256"],
        "task_result_sha256": worker["task_result_sha256"],
        "book_catalog_sha256": worker["book_catalog_sha256"],
        "rank_80_book_count": BOOKS_PER_SLATE,
        "prefix_count": PREFIXES_PER_SLATE,
        "recovered_without_reexecution": recovered,
        **_policy(),
    }, field="worker_receipt_sha256")


def _build_acceptance(
    *, manifest_identity: Mapping[str, object], manifest: Mapping[str, object],
    source_ordinal: int, worker_identity: Mapping[str, object],
    worker: Mapping[str, object], verifier_runtime: Mapping[str, object],
    independently_rebuilt: Mapping[str, object],
) -> dict[str, object]:
    member = _mapping(
        _sequence(manifest["source_members"], label="manifest source members")[
            source_ordinal
        ],
        label="manifest source member",
    )
    worker_runtime = _validate_process_runtime(
        worker["worker_process_runtime"], role="ordinal-worker"
    )
    verifier = _validate_process_runtime(
        verifier_runtime, role="independent-verifier"
    )
    if _process_instance_key(worker_runtime) == _process_instance_key(verifier):
        _fail("worker and verifier must be distinct measured process instances")
    if independently_rebuilt["task_result_sha256"] != worker["task_result_sha256"]:
        _fail("independent reexecution task result differs from worker")
    body = {
        "schema_version": ACCEPTANCE_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "status": "accepted",
        "accepted": True,
        "target_uri": member["acceptance_uri"],
        "manifest_identity": dict(manifest_identity),
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "source_ordinal": source_ordinal,
        "slate_id": member["slate_id"],
        "panel_member_sha256": member["panel_member_sha256"],
        "matchup_source_release_identity": manifest[
            "matchup_source_release_identity"
        ],
        "matchup_source_member_sha256": member["matchup_source_member_sha256"],
        "worker_result_identity": dict(worker_identity),
        "worker_result_sha256": worker["worker_result_sha256"],
        "worker_process_runtime": worker_runtime,
        "worker_process_runtime_sha256": worker_runtime["process_runtime_sha256"],
        "verifier_process_runtime": verifier,
        "verifier_process_runtime_sha256": verifier["process_runtime_sha256"],
        "worker_task_result_sha256": worker["task_result_sha256"],
        "independent_reexecution_task_result_sha256": independently_rebuilt[
            "task_result_sha256"
        ],
        "book_catalog_sha256": worker["book_catalog_sha256"],
        "scope_count": 6,
        "rank_80_book_count": BOOKS_PER_SLATE,
        "prefix_sizes": list(PREFIX_SIZES),
        "prefix_count": PREFIXES_PER_SLATE,
        "verification": {
            "worker_exact_reopened": True,
            "candidate_root_full_predecessor_replayed": True,
            "source_member_full_predecessor_replayed": True,
            "accepted_v12_slate_reconstructed": True,
            "scientific_consumer_independently_reexecuted": True,
            "all_276_rank80_books_canonical_replayed": True,
            "all_4_14_80_prefixes_canonical_replayed": True,
            "worker_and_verifier_processes_distinct": True,
        },
        **_policy(),
    }
    return _with_hash(body, field="slate_acceptance_sha256")


def _validate_acceptance(
    value: object, *, identity: object, manifest_identity: Mapping[str, object],
    manifest: Mapping[str, object], worker_identity: Mapping[str, object],
    worker: Mapping[str, object], source_ordinal: int,
) -> dict[str, object]:
    item = _mapping(value, label=f"acceptance[{source_ordinal}]")
    _exact_keys(item, _ACCEPTANCE_FIELDS, label="slate acceptance")
    _validate_self_hash(
        item, field="slate_acceptance_sha256", label="slate acceptance"
    )
    _validate_policy(item, label="slate acceptance")
    retained_identity = _bind_identity_to_body(identity, item, label="slate acceptance")
    member = _mapping(
        _sequence(manifest["source_members"], label="manifest source members")[
            source_ordinal
        ],
        label="manifest source member",
    )
    worker_runtime = _validate_process_runtime(
        item.get("worker_process_runtime"), role="ordinal-worker"
    )
    verifier_runtime = _validate_process_runtime(
        item.get("verifier_process_runtime"), role="independent-verifier"
    )
    verification = _mapping(item.get("verification"), label="acceptance verification")
    _exact_keys(
        verification,
        _ACCEPTANCE_VERIFICATION_FIELDS,
        label="acceptance verification",
    )
    if (
        item.get("schema_version") != ACCEPTANCE_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
        or item.get("status") != "accepted"
        or item.get("accepted") is not True
        or retained_identity["uri"] != member["acceptance_uri"]
        or item.get("target_uri") != member["acceptance_uri"]
        or item.get("manifest_identity") != manifest_identity
        or item.get("execution_manifest_sha256")
        != manifest["execution_manifest_sha256"]
        or item.get("source_ordinal") != source_ordinal
        or item.get("slate_id") != member["slate_id"]
        or item.get("panel_member_sha256") != member["panel_member_sha256"]
        or item.get("matchup_source_release_identity")
        != manifest["matchup_source_release_identity"]
        or item.get("matchup_source_member_sha256")
        != member["matchup_source_member_sha256"]
        or item.get("worker_result_identity") != worker_identity
        or item.get("worker_result_sha256") != worker["worker_result_sha256"]
        or item.get("worker_process_runtime") != worker["worker_process_runtime"]
        or item.get("worker_process_runtime_sha256")
        != worker_runtime["process_runtime_sha256"]
        or item.get("verifier_process_runtime_sha256")
        != verifier_runtime["process_runtime_sha256"]
        or _process_instance_key(worker_runtime) == _process_instance_key(verifier_runtime)
        or item.get("worker_task_result_sha256") != worker["task_result_sha256"]
        or item.get("independent_reexecution_task_result_sha256")
        != worker["task_result_sha256"]
        or item.get("book_catalog_sha256") != worker["book_catalog_sha256"]
        or item.get("scope_count") != 6
        or item.get("rank_80_book_count") != BOOKS_PER_SLATE
        or item.get("prefix_sizes") != list(PREFIX_SIZES)
        or item.get("prefix_count") != PREFIXES_PER_SLATE
        or any(value is not True for value in verification.values())
    ):
        _fail("slate acceptance dependency/process/science binding differs")
    return item


def _reopen_acceptance(
    *, storage: ExactObjectStore, identity: object,
    manifest_identity: Mapping[str, object], manifest: Mapping[str, object],
    source_ordinal: int,
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    acceptance_identity, acceptance = _read_json(
        storage, identity, label=f"acceptance[{source_ordinal}]"
    )
    worker_identity = _identity(
        acceptance.get("worker_result_identity"), label="acceptance worker result"
    )
    retained_worker, worker = _reopen_worker_result(
        storage=storage,
        identity=worker_identity,
        manifest_identity=manifest_identity,
        manifest=manifest,
        source_ordinal=source_ordinal,
    )
    validated = _validate_acceptance(
        acceptance,
        identity=acceptance_identity,
        manifest_identity=manifest_identity,
        manifest=manifest,
        worker_identity=retained_worker,
        worker=worker,
        source_ordinal=source_ordinal,
    )
    return acceptance_identity, validated, retained_worker, worker


def verify_worker_v2(
    *, storage: ExactObjectStore, manifest_identity: object, source_ordinal: int,
    repository_root: Path,
    validate: ValidateOrdinal = (
        consumer.validate_r6_v2_matchup_candidate_authority_ordinal_result_v2
    ),
) -> dict[str, object]:
    """Independently reexecute one retained worker and publish acceptance."""
    if type(source_ordinal) is not int or not 0 <= source_ordinal < 54:
        _fail("verifier source ordinal must be one exact integer in 0..53")
    retained_manifest, manifest, panel, _ = reopen_manifest_v2(
        storage=storage, manifest_identity=manifest_identity
    )
    embedded_runtime_authority = load_image_embedded_runtime_authority_v1()
    git_head, git_blob, git_status = _validate_runtime_binding(
        manifest=manifest,
        repository_root=repository_root,
        embedded_runtime_authority=embedded_runtime_authority,
    )
    member = _mapping(
        _sequence(manifest["source_members"], label="manifest source members")[
            source_ordinal
        ],
        label="manifest source member",
    )
    existing = storage.resolve_optional(str(member["acceptance_uri"]))
    if existing is not None:
        acceptance_identity, acceptance, _, _ = _reopen_acceptance(
            storage=storage,
            identity=existing[0].as_dict(),
            manifest_identity=retained_manifest,
            manifest=manifest,
            source_ordinal=source_ordinal,
        )
        recovered = True
    else:
        worker_current = storage.resolve_optional(str(member["worker_result_uri"]))
        if worker_current is None:
            _fail(f"worker result[{source_ordinal}] is absent")
        worker_identity, worker = _reopen_worker_result(
            storage=storage,
            identity=worker_current[0].as_dict(),
            manifest_identity=retained_manifest,
            manifest=manifest,
            source_ordinal=source_ordinal,
        )
        verifier_runtime = _current_process_runtime_v2(role="independent-verifier")
        worker_runtime = _validate_process_runtime(
            worker["worker_process_runtime"], role="ordinal-worker"
        )
        if _process_instance_key(worker_runtime) == _process_instance_key(
            verifier_runtime
        ):
            _fail("independent verification requires a distinct process")
        inputs = _executor_inputs(
            manifest=manifest,
            panel=panel,
            source_ordinal=source_ordinal,
            repository_root=repository_root,
            read_exact=_read_exact_callback(storage),
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
        try:
            independently_rebuilt = validate(worker["task_result"], **inputs)
        except Exception as exc:
            raise CorpusR6V2MatchupCandidateAnalysisReleaseV2Error(
                f"independent verifier[{source_ordinal}] failed closed"
            ) from exc
        rebuilt = _validate_task_result_shell(
            independently_rebuilt, manifest=manifest, source_ordinal=source_ordinal
        )
        rebuilt_catalog = _book_catalog(rebuilt)
        if rebuilt_catalog != worker["book_catalog"]:
            _fail("independent verifier rebuilt a different book/prefix catalog")
        acceptance = _build_acceptance(
            manifest_identity=retained_manifest,
            manifest=manifest,
            source_ordinal=source_ordinal,
            worker_identity=worker_identity,
            worker=worker,
            verifier_runtime=verifier_runtime,
            independently_rebuilt=rebuilt,
        )
        acceptance_identity = _publish_or_recover(
            storage,
            uri=str(member["acceptance_uri"]),
            value=acceptance,
            label=f"acceptance[{source_ordinal}]",
        )
        _, acceptance, _, _ = _reopen_acceptance(
            storage=storage,
            identity=acceptance_identity,
            manifest_identity=retained_manifest,
            manifest=manifest,
            source_ordinal=source_ordinal,
        )
        recovered = False
    return _with_hash({
        "schema_version": VERIFIER_RECEIPT_SCHEMA,
        "manifest_identity": retained_manifest,
        "source_ordinal": source_ordinal,
        "slate_id": acceptance["slate_id"],
        "acceptance_identity": acceptance_identity,
        "slate_acceptance_sha256": acceptance["slate_acceptance_sha256"],
        "rank_80_book_count": BOOKS_PER_SLATE,
        "prefix_count": PREFIXES_PER_SLATE,
        "accepted": True,
        "recovered_without_reexecution": recovered,
        **_policy(),
    }, field="verifier_receipt_sha256")


def _build_terminal_root(
    *, storage: ExactObjectStore, manifest_identity: Mapping[str, object],
    manifest: Mapping[str, object], ordered_acceptance_identities: Sequence[object],
) -> dict[str, object]:
    identities = _sequence(
        ordered_acceptance_identities, label="ordered acceptance identities"
    )
    if len(identities) != AUTHORITATIVE_SLATE_COUNT:
        _fail("terminal root requires exactly 54 ordered acceptances")
    rows: list[dict[str, object]] = []
    seen_acceptances: set[tuple[str, str, str, int]] = set()
    seen_workers: set[tuple[str, str, str, int]] = set()
    for ordinal, raw_identity in enumerate(identities):
        acceptance_identity, acceptance, worker_identity, worker = (
            _reopen_acceptance(
                storage=storage,
                identity=raw_identity,
                manifest_identity=manifest_identity,
                manifest=manifest,
                source_ordinal=ordinal,
            )
        )
        acceptance_key = _identity_key(
            acceptance_identity, label=f"acceptance[{ordinal}]"
        )
        worker_key = _identity_key(worker_identity, label=f"worker[{ordinal}]")
        if acceptance_key in seen_acceptances or worker_key in seen_workers:
            _fail("terminal root detected a cloned acceptance/worker object")
        seen_acceptances.add(acceptance_key)
        seen_workers.add(worker_key)
        rows.append(_with_hash({
            "source_ordinal": ordinal,
            "slate_id": acceptance["slate_id"],
            "panel_member_sha256": acceptance["panel_member_sha256"],
            "matchup_source_member_sha256": acceptance[
                "matchup_source_member_sha256"
            ],
            "acceptance_identity": acceptance_identity,
            "slate_acceptance_sha256": acceptance["slate_acceptance_sha256"],
            "worker_result_identity": worker_identity,
            "worker_result_sha256": worker["worker_result_sha256"],
            "task_result_sha256": worker["task_result_sha256"],
            "book_catalog_sha256": worker["book_catalog_sha256"],
            "rank_80_book_count": BOOKS_PER_SLATE,
            "prefix_count": PREFIXES_PER_SLATE,
            "accepted": True,
        }, field="terminal_slate_descriptor_sha256"))
    body = {
        "schema_version": TERMINAL_ROOT_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "status": TERMINAL_STATUS,
        "accepted": True,
        "complete": True,
        "target_uri": manifest["terminal_root_uri"],
        "manifest_identity": dict(manifest_identity),
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "panel_index_identity": manifest["panel_index_identity"],
        "panel_index_sha256": manifest["panel_index_sha256"],
        "matchup_source_release_identity": manifest[
            "matchup_source_release_identity"
        ],
        "matchup_source_release_sha256": manifest[
            "matchup_source_release_sha256"
        ],
        "source_slate_count": len(rows),
        "verified_worker_count": len(rows),
        "accepted_slate_count": len(rows),
        "ordered_acceptances": rows,
        "ordered_acceptances_sha256": batch.canonical_sha256(rows),
        "fit_scope_ids": list(FIT_SCOPE_IDS),
        "scope_count": AUTHORITATIVE_SLATE_COUNT * len(FIT_SCOPE_IDS),
        "rank_80_book_count": PANEL_BOOK_COUNT,
        "prefix_sizes": list(PREFIX_SIZES),
        "prefix_count": PANEL_PREFIX_COUNT,
        "prefix_roster_occurrence_counts": {
            str(size): AUTHORITATIVE_SLATE_COUNT * BOOKS_PER_SLATE * size
            for size in PREFIX_SIZES
        },
        "independent_worker_verification_complete": True,
        "release_graph_outcome_blind_verified": True,
        **_policy(),
    }
    return _with_hash(body, field="accepted_root_sha256")


def reopen_terminal_root_v2(
    *, storage: ExactObjectStore, terminal_root_identity: object,
) -> tuple[dict[str, object], dict[str, object]]:
    retained_root, root = _read_json(
        storage, terminal_root_identity, label="terminal accepted root"
    )
    _validate_self_hash(root, field="accepted_root_sha256", label="accepted root")
    _validate_policy(root, label="accepted root")
    retained_manifest, manifest, _, _ = reopen_manifest_v2(
        storage=storage, manifest_identity=root.get("manifest_identity")
    )
    rows = _sequence(root.get("ordered_acceptances"), label="root acceptances")
    identities = [
        _identity(
            _mapping(row, label=f"root row[{ordinal}]")["acceptance_identity"],
            label=f"root acceptance[{ordinal}]",
        )
        for ordinal, row in enumerate(rows)
    ]
    expected = _build_terminal_root(
        storage=storage,
        manifest_identity=retained_manifest,
        manifest=manifest,
        ordered_acceptance_identities=identities,
    )
    if (
        retained_root["uri"] != manifest["terminal_root_uri"]
        or root.get("target_uri") != manifest["terminal_root_uri"]
        or root.get("schema_version") != TERMINAL_ROOT_SCHEMA
        or root.get("status") != TERMINAL_STATUS
        or root.get("accepted") is not True
        or root.get("complete") is not True
        or batch.canonical_json_bytes(root) != batch.canonical_json_bytes(expected)
    ):
        _fail("terminal accepted root canonical dependency replay differs")
    return retained_root, expected


def finish_release_v2(
    *, storage: ExactObjectStore, manifest_identity: object,
) -> dict[str, object]:
    """Exact-open 54 verified ordinals and create the accepted root last."""
    retained_manifest, manifest, _, _ = reopen_manifest_v2(
        storage=storage, manifest_identity=manifest_identity
    )
    identities: list[dict[str, object]] = []
    missing: list[int] = []
    for raw_member in _sequence(manifest["source_members"], label="source members"):
        member = _mapping(raw_member, label="source member")
        resolved = storage.resolve_optional(str(member["acceptance_uri"]))
        if resolved is None:
            missing.append(int(member["source_ordinal"]))
        else:
            identities.append(
                _identity(resolved[0].as_dict(), label="resolved acceptance")
            )
    if missing:
        _fail(f"terminal root is not ready; missing acceptances {missing}")
    root = _build_terminal_root(
        storage=storage,
        manifest_identity=retained_manifest,
        manifest=manifest,
        ordered_acceptance_identities=identities,
    )
    root_identity = _publish_or_recover(
        storage,
        uri=str(manifest["terminal_root_uri"]),
        value=root,
        label="terminal accepted root",
    )
    _, reopened = reopen_terminal_root_v2(
        storage=storage, terminal_root_identity=root_identity
    )
    if reopened != root:
        _fail("published terminal root exact replay differs")
    return _with_hash({
        "schema_version": FINISH_RECEIPT_SCHEMA,
        "manifest_identity": retained_manifest,
        "terminal_root_identity": root_identity,
        "accepted_root_sha256": root["accepted_root_sha256"],
        "status": TERMINAL_STATUS,
        "source_slate_count": AUTHORITATIVE_SLATE_COUNT,
        "rank_80_book_count": PANEL_BOOK_COUNT,
        "prefix_count": PANEL_PREFIX_COUNT,
        "accepted": True,
        "complete": True,
        **_policy(),
    }, field="finish_receipt_sha256")


__all__ = [
    "ACCEPTANCE_SCHEMA",
    "AUTHORITATIVE_SLATE_COUNT",
    "BOOKS_PER_SLATE",
    "CorpusR6V2MatchupCandidateAnalysisReleaseV2Error",
    "MANIFEST_SCHEMA",
    "PANEL_BOOK_COUNT",
    "PANEL_PREFIX_COUNT",
    "PREFIX_SIZES",
    "TERMINAL_ROOT_SCHEMA",
    "finish_release_v2",
    "prepare_release_v2",
    "reopen_manifest_v2",
    "reopen_terminal_root_v2",
    "run_worker_v2",
    "verify_worker_v2",
]
