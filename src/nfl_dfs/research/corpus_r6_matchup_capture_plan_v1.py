"""Fixed, outcome-blind capture-plan lock for the R6 matchup source.

This module is a pure authority-selection seam.  It freezes the already
accepted August-23 Foundry v12 G0, its fixed-G0 structural-catalog adapter,
one accepted-candidate release, seven immutable source-pack objects, and the
exact source-v2/component-producer bytes.  It deliberately owns no warehouse
or storage client, publication callback, source reducer invocation, outcome
reader, scoring path, or production mutation.

The lock is intended for a two-commit protocol.  Commit A contains the source
and producer implementation bytes.  External, separately reviewed capture
and adapter operations create immutable prerequisite objects from Commit A.
Commit B adds one canonical capture-plan JSON file.  A later finalizer must
secure-read that constant file, prove its Git blob and current bytes equal,
replay the Commit-A implementation measurements, and exact-open every remote
identity pinned here before it derives any of the 54 component bundles.

Nothing emitted by this module grants capture, source execution, publication,
historical scoring, fill, retrieval, graph, promotion, decision, or production
authority.  Those booleans remain literally false, including
``capture_mechanics_authority``.  A later independently reviewed operator may
consume this lock as evidence; the lock never authorizes itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
import re
from typing import Final

from nfl_dfs.research import (
    corpus_r6_matchup_component_producer_v1 as component_producer,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import (
    corpus_r6_player_catalog_fixed_g0_adapter_v1 as fixed_g0,
)
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1


CAPTURE_PLAN_SCHEMA: Final = "corpus-r6-matchup-capture-plan/v1"
CAPTURE_PLAN_ID: Final = "20260826-r6-matchup-source-v2-fixed-g0"
CAPTURE_PLAN_SCOPE: Final = (
    "fixed-g0-seven-pack-input-lock-for-later-offline-finalization"
)
CAPTURE_PLAN_LOCK_PATH: Final = (
    "reports/corpus-r6-matchup-runs/"
    "20260826-r6-matchup-source-v2/capture-plan-lock.json"
)
SOURCE_V2_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_matchup_source_v2.py"
)
COMPONENT_PRODUCER_MODULE_PATH: Final = source.PRODUCER_MODULE_PATH
IMPLEMENTATION_PATHS: Final = (
    SOURCE_V2_MODULE_PATH,
    COMPONENT_PRODUCER_MODULE_PATH,
)
PRODUCTION_PROJECT: Final = "nfl-predictions-503414"
TRACKED_PUBLICATION_MODE: Final = "tracked-two-commit-lock"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")

_FILE_MEASUREMENT_FIELDS: Final = frozenset({
    "relative_path", "sha256", "bytes",
})
_TRACKED_FILE_BINDING_FIELDS: Final = frozenset({
    "commit_sha",
    "relative_path",
    "sha256",
    "bytes",
    "internal_sha256",
})
_SECURE_CURRENT_OBSERVATION_FIELDS: Final = frozenset({
    "relative_path",
    "raw",
    "is_regular_file",
    "is_symlink",
    "opened_nofollow",
})
_PACK_BINDING_FIELDS: Final = frozenset({
    "pack_ordinal",
    "pack_id",
    "source_kind",
    "provenance_kind",
    "exact_rows_identity",
    "row_count",
    "rows_sha256",
    "source_period_min",
    "source_period_max",
    "warehouse_query_receipt_identity",
    "frozen_artifact_manifest_identities",
    "projection_code_identity",
})
_SOURCE_TASK_BINDING_FIELDS: Final = frozenset({
    "source_task_ordinal",
    "task_id",
    "slate",
    "lane_id",
    "lane_ordinal",
    "task_ordinal",
    "accepted_slate_membership_sha256",
    "source_task_authority_sha256",
    "catalog_identity",
    "source_catalog_sha256",
    "player_count",
    "ordered_player_ids_sha256",
    "accepted_candidate_release_entry_sha256",
    "candidate_artifact_identity",
    "candidate_count",
    "ordered_candidate_ids_sha256",
})
_FINALIZER_REQUIREMENT_FIELDS: Final = frozenset({
    "required_source_task_count",
    "required_upstream_pack_count",
    "required_role_count_per_slate",
    "required_component_count_per_slate",
    "required_entry_budget",
    "exact_remote_reopen_required",
    "create_once_only_required",
    "same_reducer_full_and_deleted_replay_required",
    "physical_target_or_later_row_deletion_required",
    "nonzero_deletion_each_required_pack_and_slice",
    "all_54_support_census_required",
    "partial_producer_release_allowed",
    "caller_selected_root_allowed",
    "caller_selected_bundle_allowed",
    "caller_selected_namespace_allowed",
})

FALSE_AUTHORITY_FIELDS: Final = tuple(dict.fromkeys((
    *source.FALSE_AUTHORITY_FIELDS,
    *catalog_v1.FALSE_AUTHORITY_FIELDS,
    "analytical_authority",
    "automatic_retry_licensed",
    "self_authorizing",
)))
_POLICY_FIELDS: Final = frozenset({
    "outcome_columns_read",
    "uses_realized_outcomes",
    *FALSE_AUTHORITY_FIELDS,
})
_FORBIDDEN_OUTCOME_FIELDS: Final = frozenset({
    *source.FORBIDDEN_OUTCOME_CARRIER_FIELDS,
    "actual_fantasy_points",
    "actual_rank",
    "contest_outcome",
    "historical_score",
    "realized_contest_result",
    "roi",
})

_PLAN_FIELDS: Final = frozenset({
    "schema_version",
    "capture_plan_id",
    "capture_plan_scope",
    "capture_plan_lock_relative_path",
    "tracked_publication_mode",
    "allowed_project",
    "fixed_g0_authority_binding",
    "fixed_g0_authority_binding_sha256",
    "adapter_final_release_lock_binding",
    "fixed_g0_replay_receipt_identity",
    "fixed_g0_replay_receipt_sha256",
    "catalog_release_identity",
    "catalog_release_sha256",
    "accepted_candidate_release_identity",
    "accepted_candidate_release_sha256",
    "upstream_source_release_identity",
    "upstream_source_release_sha256",
    "upstream_namespace",
    "upstream_pack_count",
    "upstream_pack_bindings",
    "upstream_pack_binding_manifest_sha256",
    "implementation_commit_sha",
    "implementation_measurements",
    "implementation_measurement_manifest_sha256",
    "source_v2_code_identity",
    "component_producer_code_identity",
    "producer_id",
    "producer_release_id",
    "producer_namespace",
    "source_task_count",
    "source_task_bindings",
    "source_task_binding_manifest_sha256",
    "finalizer_requirements",
    "canonical_json_plus_one_newline_required",
    "current_clean_git_required",
    "git_blob_current_byte_equality_required",
    "remote_exact_reopen_required",
    "lock_builder_capture_performed",
    "lock_builder_cloud_read_performed",
    "lock_builder_cloud_mutation_performed",
    "lock_builder_outcome_read_performed",
    *_POLICY_FIELDS,
    "capture_plan_sha256",
})

ReadGitBlob = Callable[[str, str], bytes]
SecureReadCurrent = Callable[[str], Mapping[str, object]]


class CorpusR6MatchupCapturePlanV1Error(ValueError):
    """The fixed R6 matchup capture-plan lock failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupCapturePlanV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return source.canonical_json_bytes(value)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupCapturePlanV1Error(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if set(value) != set(expected):
        _fail(f"{label} fields differ")


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _identifier(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _IDENTIFIER.fullmatch(text) is None:
        _fail(f"{label} must be a canonical identifier")
    return text


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _commit(value: object, *, label: str) -> str:
    if type(value) is not str or _COMMIT.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 40-hex")
    return value


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _namespace(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if (
        not text.startswith("gs://")
        or not text.endswith("/")
        or ".." in text
        or "//" in text[5:]
        or "?" in text
        or "#" in text
    ):
        _fail(f"{label} must be a canonical GCS namespace")
    return text


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in FALSE_AUTHORITY_FIELDS},
    }


def _validate_policy(value: Mapping[str, object], *, label: str) -> None:
    if value.get("outcome_columns_read") != []:
        _fail(f"{label}.outcome_columns_read must be empty")
    if value.get("uses_realized_outcomes") is not False:
        _fail(f"{label}.uses_realized_outcomes must be false")
    differing = [
        field for field in FALSE_AUTHORITY_FIELDS
        if value.get(field) is not False
    ]
    if differing:
        _fail(f"{label} carries non-false authorities {differing}")


def _reject_outcome_and_authority_carriers(
    value: object, *, label: str,
) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if type(key) is not str:
                _fail(f"{label} contains a non-string field")
            normalized = key.strip().lower()
            if (
                normalized in _FORBIDDEN_OUTCOME_FIELDS
                or (
                    "realized" in normalized
                    and normalized != "uses_realized_outcomes"
                )
            ):
                _fail(f"{label} contains forbidden outcome field {key!r}")
            if normalized == "outcome_columns_read" and nested != []:
                _fail(f"{label}.outcome_columns_read must be empty")
            if normalized == "uses_realized_outcomes" and nested is not False:
                _fail(f"{label}.uses_realized_outcomes must be false")
            if normalized in FALSE_AUTHORITY_FIELDS and nested is not False:
                _fail(f"{label}.{key} must be false")
            _reject_outcome_and_authority_carriers(
                nested, label=f"{label}.{key}"
            )
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, nested in enumerate(value):
            _reject_outcome_and_authority_carriers(
                nested, label=f"{label}[{ordinal}]"
            )


def _parse_canonical_json(
    raw: object, *, label: str, require_one_newline: bool,
) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")
    payload = raw[:-1] if require_one_newline and raw.endswith(b"\n") else raw
    if require_one_newline and payload is raw:
        _fail(f"{label} must end in exactly one newline")
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6MatchupCapturePlanV1Error(
            f"{label} is not canonical JSON"
        ) from exc
    item = _mapping(parsed, label=label)
    expected = canonical_json_bytes(item) + (b"\n" if require_one_newline else b"")
    if raw != expected:
        _fail(f"{label} bytes differ from canonical JSON")
    return item


def _normalize_identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupCapturePlanV1Error(str(exc)) from exc


def _bind_body(
    body: object, identity: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    normalized = _normalize_identity(identity, label=f"{label} identity")
    raw = canonical_json_bytes(body)
    if (
        normalized["sha256"] != sha256(raw).hexdigest()
        or normalized["bytes"] != len(raw)
    ):
        _fail(f"{label} differs from its exact identity")
    return normalized


def _normalize_file_measurement(
    value: object, *, label: str,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, _FILE_MEASUREMENT_FIELDS, label=label)
    path = _string(item["relative_path"], label=f"{label}.relative_path")
    if path.startswith("/") or ".." in path.split("/") or not path:
        _fail(f"{label}.relative_path must be repository-relative")
    return {
        "relative_path": path,
        "sha256": _digest(item["sha256"], label=f"{label}.sha256"),
        "bytes": _exact_int(item["bytes"], label=f"{label}.bytes", minimum=1),
    }


def _normalize_tracked_file_binding(
    value: object, *, label: str,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, _TRACKED_FILE_BINDING_FIELDS, label=label)
    measurement = _normalize_file_measurement({
        "relative_path": item["relative_path"],
        "sha256": item["sha256"],
        "bytes": item["bytes"],
    }, label=f"{label} file")
    return {
        "commit_sha": _commit(item["commit_sha"], label=f"{label}.commit"),
        **measurement,
        "internal_sha256": _digest(
            item["internal_sha256"], label=f"{label}.internal_sha256"
        ),
    }


def _normalize_implementation_measurements(
    value: object,
) -> list[dict[str, object]]:
    rows = _sequence(value, label="implementation measurements")
    normalized = [
        _normalize_file_measurement(
            row, label=f"implementation measurement[{ordinal}]"
        )
        for ordinal, row in enumerate(rows)
    ]
    if [row["relative_path"] for row in normalized] != list(
        IMPLEMENTATION_PATHS
    ):
        _fail("implementation measurements differ from the exact two files")
    return normalized


def _secure_current_bytes(
    *, path: str, secure_read_current: SecureReadCurrent,
) -> bytes:
    try:
        observation = _mapping(
            secure_read_current(path), label=f"secure current read {path}"
        )
    except CorpusR6MatchupCapturePlanV1Error:
        raise
    except Exception as exc:
        raise CorpusR6MatchupCapturePlanV1Error(
            f"secure current read failed for {path}"
        ) from exc
    _exact_keys(
        observation,
        _SECURE_CURRENT_OBSERVATION_FIELDS,
        label=f"secure current read {path}",
    )
    raw = observation["raw"]
    if (
        observation["relative_path"] != path
        or type(raw) is not bytes
        or not raw
        or observation["is_regular_file"] is not True
        or observation["is_symlink"] is not False
        or observation["opened_nofollow"] is not True
    ):
        _fail(f"secure current read evidence differs for {path}")
    return raw


def measure_implementation_files_v1(
    *,
    implementation_commit_sha: str,
    read_git_blob: ReadGitBlob,
    secure_read_current: SecureReadCurrent,
    repository_clean: bool,
) -> list[dict[str, object]]:
    """Measure the exact Commit-A blobs and equal current no-follow bytes."""
    commit = _commit(
        implementation_commit_sha, label="implementation commit SHA"
    )
    if repository_clean is not True:
        _fail("implementation measurement requires a clean repository")
    measurements: list[dict[str, object]] = []
    for ordinal, path in enumerate(IMPLEMENTATION_PATHS):
        try:
            blob = read_git_blob(commit, path)
        except Exception as exc:
            raise CorpusR6MatchupCapturePlanV1Error(
                f"implementation Git blob[{ordinal}] read failed"
            ) from exc
        current = _secure_current_bytes(
            path=path, secure_read_current=secure_read_current
        )
        if type(blob) is not bytes or not blob or blob != current:
            _fail(f"implementation Git/current bytes differ for {path}")
        measurements.append({
            "relative_path": path,
            "sha256": sha256(blob).hexdigest(),
            "bytes": len(blob),
        })
    return _normalize_implementation_measurements(measurements)


def fixed_g0_authority_binding_v1() -> dict[str, object]:
    """Return the sole accepted August-23, all-54 structural root."""
    body: dict[str, object] = {
        "evidence_source_commit_sha": fixed_g0.FIXED_SOURCE_COMMIT_SHA,
        "g0_lock_relative_path": fixed_g0.FIXED_G0_LOCK_PATH,
        "g0_lock_file_sha256": fixed_g0.FIXED_G0_LOCK_FILE_SHA256,
        "g0_lock_file_bytes": fixed_g0.FIXED_G0_LOCK_FILE_BYTES,
        "g0_lock_internal_sha256": fixed_g0.FIXED_G0_LOCK_INTERNAL_SHA256,
        "g0_lock_id": fixed_g0.FIXED_G0_LOCK_ID,
        "panel_id": fixed_g0.FIXED_PANEL_ID,
        "panel_index_sha256": fixed_g0.FIXED_PANEL_INDEX_SHA256,
        "panel_identity": _normalize_identity(
            fixed_g0.FIXED_PANEL_IDENTITY, label="fixed G0 panel"
        ),
        "lane_terminal_identities": [
            _normalize_identity(value, label=f"fixed lane terminal[{ordinal}]")
            for ordinal, value in enumerate(
                fixed_g0.FIXED_LANE_TERMINAL_IDENTITIES
            )
        ],
        "lane_completion_identities": [
            _normalize_identity(value, label=f"fixed lane completion[{ordinal}]")
            for ordinal, value in enumerate(
                fixed_g0.FIXED_LANE_COMPLETION_IDENTITIES
            )
        ],
        "later_source_identity": _normalize_identity(
            fixed_g0.FIXED_LATER_SOURCE_IDENTITY,
            label="fixed later-source freeze",
        ),
        "artifact_source_completion_identity": _normalize_identity(
            fixed_g0.FIXED_SOURCE_COMPLETION_IDENTITY,
            label="fixed artifact-source completion",
        ),
        "catalog_namespace": _namespace(
            fixed_g0.FIXED_CATALOG_NAMESPACE,
            label="fixed catalog namespace",
        ),
        "accepted_slate_count": source.TASK_COUNT,
    }
    return body


def _expected_tracked_root_binding() -> dict[str, object]:
    fixed = fixed_g0_authority_binding_v1()
    return {
        "g0_authority_lock_schema": catalog_v1.G0_AUTHORITY_LOCK_SCHEMA,
        "g0_authority_lock_relative_path": fixed["g0_lock_relative_path"],
        "g0_authority_lock_file_sha256": fixed["g0_lock_file_sha256"],
        "g0_authority_lock_sha256": fixed["g0_lock_internal_sha256"],
        "source_commit_sha": fixed["evidence_source_commit_sha"],
        "panel_object_identity": fixed["panel_identity"],
        "panel_index_sha256": fixed["panel_index_sha256"],
        "accepted_slate_count": source.TASK_COUNT,
    }


def _validate_adapter_final_release_lock_raw(
    raw: object,
) -> dict[str, object]:
    item = _parse_canonical_json(
        raw,
        label="fixed-G0 adapter final release lock",
        require_one_newline=True,
    )
    retained = _digest(
        item.get("final_release_lock_sha256"),
        label="fixed-G0 final release lock internal SHA",
    )
    body = dict(item)
    del body["final_release_lock_sha256"]
    if canonical_sha256(body) != retained:
        _fail("fixed-G0 final release lock self-hash differs")
    _reject_outcome_and_authority_carriers(
        item, label="fixed-G0 adapter final release lock"
    )
    measurements = _sequence(
        item.get("implementation_measurements"),
        label="fixed-G0 final implementation measurements",
    )
    normalized_measurements = [
        _normalize_file_measurement(
            row, label=f"fixed-G0 implementation[{ordinal}]"
        )
        for ordinal, row in enumerate(measurements)
    ]
    paths = [str(row["relative_path"]) for row in normalized_measurements]
    if paths != list(fixed_g0.FIXED_ADAPTER_IMPLEMENTATION_PATHS):
        _fail("fixed-G0 final implementation file order differs")
    preliminary_file = _normalize_file_measurement(
        item.get("preliminary_review_lock_file"),
        label="fixed-G0 final preliminary review lock file",
    )
    smoke_receipt_file = _normalize_file_measurement(
        item.get("task0_smoke_receipt_file"),
        label="fixed-G0 final task-0 smoke receipt file",
    )
    smoke_attempt_file = _normalize_file_measurement(
        item.get("task0_smoke_attempt_file"),
        label="fixed-G0 final task-0 smoke attempt file",
    )
    allowed_attempt_paths = {
        fixed_g0.FIXED_TASK0_SMOKE_ATTEMPT_PATH,
        getattr(
            fixed_g0,
            "FIXED_TASK0_SMOKE_ATTEMPT_V2_PATH",
            fixed_g0.FIXED_TASK0_SMOKE_ATTEMPT_PATH,
        ),
    }
    allowed_smoke_commands = {
        tuple(fixed_g0.FIXED_TASK0_SMOKE_COMMAND),
        tuple(getattr(
            fixed_g0,
            "FIXED_TASK0_SMOKE_V2_COMMAND",
            fixed_g0.FIXED_TASK0_SMOKE_COMMAND,
        )),
    }
    for field in (
        "preliminary_review_lock_internal_sha256",
        "task0_smoke_receipt_internal_sha256",
        "task0_smoke_attempt_internal_sha256",
    ):
        _digest(item.get(field), label=f"fixed-G0 final {field}")
    _commit(
        item.get("implementation_commit_sha"),
        label="fixed-G0 implementation commit",
    )
    _commit(
        item.get("preliminary_review_lock_commit_sha"),
        label="fixed-G0 preliminary review commit",
    )
    if (
        item.get("schema_version") != fixed_g0.FINAL_RELEASE_LOCK_SCHEMA
        or item.get("evidence_source_commit_sha")
        != fixed_g0.FIXED_SOURCE_COMMIT_SHA
        or preliminary_file["relative_path"]
        != fixed_g0.FIXED_ADAPTER_REVIEW_LOCK_PATH
        or smoke_receipt_file["relative_path"]
        != fixed_g0.FIXED_TASK0_SMOKE_RECEIPT_PATH
        or smoke_attempt_file["relative_path"] not in allowed_attempt_paths
        or tuple(_sequence(
            item.get("task0_smoke_command"),
            label="fixed-G0 task-0 smoke command",
        )) not in allowed_smoke_commands
        or item.get("task0_smoke_passed") is not True
        or type(item.get("task0_smoke_invocation_count")) is not int
        or not 1 <= int(item["task0_smoke_invocation_count"]) <= 2
        or item.get("independent_static_review_passed") is not True
        or any(
            type(item.get(field)) is not int or item.get(field) != 0
            for field in ("p0_open_count", "p1_open_count", "p2_open_count")
        )
        or item.get("current_clean_git_required") is not True
        or item.get("required_source_task_count") != source.TASK_COUNT
        or item.get("required_task_acceptance_body_reopen_count")
        != source.TASK_COUNT
        or item.get("required_carrier_body_reopen_count") != source.TASK_COUNT
        or item.get("projection_only_publication_reviewed") is not True
        or item.get("projection_only_publication_licensed") is not True
        or item.get("projection_release_command")
        != list(fixed_g0.FIXED_PROJECTION_RELEASE_COMMAND)
        or item.get("production_enable_environment_variable")
        != fixed_g0.PRODUCTION_ENABLE_ENV
        or item.get("production_enable_environment_value") != "1"
        or item.get("gcs_create_once_required") is not True
        or item.get("gcs_overwrite_licensed") is not False
        or item.get("world_matrix_bodies_read") is not False
        or item.get("result_object_bodies_read") is not False
        or item.get("outcome_columns_read") != []
        or item.get("uses_realized_outcomes") is not False
    ):
        _fail("fixed-G0 final release requirements differ")
    for field in catalog_v1.FALSE_AUTHORITY_FIELDS:
        if item.get(field) is not False:
            _fail("fixed-G0 final release lock claims downstream authority")
    normalized = dict(item)
    normalized["implementation_measurements"] = normalized_measurements
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("fixed-G0 final release lock canonical replay differs")
    return normalized


def _build_adapter_final_lock_binding(
    *, commit_sha: str, raw: bytes,
) -> tuple[dict[str, object], dict[str, object]]:
    lock = _validate_adapter_final_release_lock_raw(raw)
    binding = {
        "commit_sha": _commit(commit_sha, label="adapter final-lock commit"),
        "relative_path": fixed_g0.FIXED_FINAL_RELEASE_LOCK_PATH,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "internal_sha256": lock["final_release_lock_sha256"],
    }
    return lock, _normalize_tracked_file_binding(
        binding, label="adapter final release lock binding"
    )


def _validate_fixed_g0_replay_and_catalog(
    *,
    replay_receipt: Mapping[str, object],
    replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    try:
        receipt, receipt_identity = component_producer._validate_fixed_g0_replay(
            replay_receipt=replay_receipt,
            replay_receipt_identity=replay_receipt_identity,
            catalog_release=catalog_release,
            catalog_release_identity=catalog_release_identity,
        )
        release = catalog_v1.validate_release_v1(catalog_release)
    except (
        component_producer.CorpusR6MatchupComponentProducerV1Error,
        catalog_v1.CorpusR6PlayerCatalogV1Error,
    ) as exc:
        raise CorpusR6MatchupCapturePlanV1Error(str(exc)) from exc
    release_identity = _bind_body(
        release, catalog_release_identity, label="fixed-G0 catalog release"
    )
    fixed = fixed_g0_authority_binding_v1()
    if (
        receipt["tracked_root_binding"] != _expected_tracked_root_binding()
        or release["tracked_root_binding"] != _expected_tracked_root_binding()
        or receipt["lane_terminal_identities"]
        != fixed["lane_terminal_identities"]
        or receipt["lane_completion_identities"]
        != fixed["lane_completion_identities"]
        or receipt["later_source_freeze_identity"]
        != fixed["later_source_identity"]
        or receipt["artifact_source_authority_completion_identity"]
        != fixed["artifact_source_completion_identity"]
        or release["later_source_freeze_identity"]
        != fixed["later_source_identity"]
        or release["artifact_source_authority_completion_identity"]
        != fixed["artifact_source_completion_identity"]
        or receipt["catalog_namespace"] != fixed["catalog_namespace"]
        or release["catalog_namespace"] != fixed["catalog_namespace"]
        or release["release_id"] != fixed_g0.FIXED_RELEASE_ID
        or release_identity["uri"]
        != f"{fixed['catalog_namespace']}catalog-release.json"
        or receipt_identity["uri"]
        != f"{fixed['catalog_namespace']}{fixed_g0.REPLAY_RECEIPT_FILENAME}"
    ):
        _fail("fixed-G0 replay/catalog differs from the accepted August-23 root")
    return receipt, receipt_identity, release, release_identity


def _validate_accepted_candidate_release(
    *,
    value: Mapping[str, object],
    identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        release = source.validate_accepted_candidate_release_v1(value)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupCapturePlanV1Error(str(exc)) from exc
    normalized_identity = _bind_body(
        release, identity, label="accepted candidate release"
    )
    namespace = _namespace(
        release["namespace"], label="accepted candidate namespace"
    )
    if (
        normalized_identity["uri"]
        != f"{namespace}accepted-candidate-release.json"
        or release["source_candidate_panel_identity"]
        != fixed_g0_authority_binding_v1()["panel_identity"]
    ):
        _fail("accepted candidate release differs from fixed G0")
    catalog_entries = _sequence(
        catalog_release["entries"], label="catalog release entries"
    )
    candidate_entries = _sequence(
        release["entries"], label="candidate release entries"
    )
    if len(catalog_entries) != source.TASK_COUNT:
        _fail("catalog release must carry exactly 54 entries")
    for ordinal, (catalog_entry_value, candidate_entry_value) in enumerate(
        zip(catalog_entries, candidate_entries, strict=True)
    ):
        catalog_entry = _mapping(
            catalog_entry_value, label=f"catalog entry[{ordinal}]"
        )
        candidate_entry = _mapping(
            candidate_entry_value, label=f"candidate entry[{ordinal}]"
        )
        artifact = _mapping(
            candidate_entry["candidate_artifact"],
            label=f"candidate artifact[{ordinal}]",
        )
        rows = _sequence(
            artifact["rows"], label=f"candidate artifact rows[{ordinal}]"
        )
        unordered_roster_hashes = [
            canonical_sha256(sorted(
                str(player_id)
                for player_id in _sequence(
                    _mapping(row, label="candidate artifact row")[
                        "player_ids"
                    ],
                    label="candidate artifact player IDs",
                )
            ))
            for row in rows
        ]
        if (
            candidate_entry["catalog_identity"]
            != catalog_entry["catalog_identity"]
            or candidate_entry["candidate_count"] < source.ENTRY_BUDGET
            or len(unordered_roster_hashes)
            != len(set(unordered_roster_hashes))
        ):
            _fail(
                f"candidate entry[{ordinal}] lacks fixed catalog or distinct "
                "entry-budget support"
            )
    return release, normalized_identity


def _validate_upstream_release(
    *,
    value: Mapping[str, object],
    identity: Mapping[str, object],
    pack_row_objects: Sequence[Mapping[str, object]],
    expected_fixed_source_root_identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        release = source.validate_upstream_release_v1(
            value,
            pack_row_objects=pack_row_objects,
            expected_fixed_source_root_identity=(
                expected_fixed_source_root_identity
            ),
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupCapturePlanV1Error(str(exc)) from exc
    normalized_identity = _bind_body(
        release, identity, label="upstream source release"
    )
    namespace = _namespace(release["namespace"], label="upstream namespace")
    if normalized_identity["uri"] != f"{namespace}upstream-release.json":
        _fail("upstream source release URI differs from its namespace")
    return release, normalized_identity


def _pack_bindings(
    upstream_release: Mapping[str, object],
) -> list[dict[str, object]]:
    packs = _sequence(upstream_release["packs"], label="upstream packs")
    if len(packs) != len(source.PACK_IDS):
        _fail("capture plan requires exactly seven upstream packs")
    bindings: list[dict[str, object]] = []
    for ordinal, value in enumerate(packs):
        pack = _mapping(value, label=f"upstream pack[{ordinal}]")
        if pack["pack_id"] != source.PACK_IDS[ordinal]:
            _fail("upstream pack order differs from the frozen registry")
        binding = {
            "pack_ordinal": ordinal,
            "pack_id": pack["pack_id"],
            "source_kind": pack["source_kind"],
            "provenance_kind": pack["provenance_kind"],
            "exact_rows_identity": pack["exact_rows_identity"],
            "row_count": pack["row_count"],
            "rows_sha256": pack["rows_sha256"],
            "source_period_min": pack["source_period_min"],
            "source_period_max": pack["source_period_max"],
            "warehouse_query_receipt_identity": (
                pack["warehouse_query_receipt_identity"]
            ),
            "frozen_artifact_manifest_identities": (
                pack["frozen_artifact_manifest_identities"]
            ),
            "projection_code_identity": pack["projection_code_identity"],
        }
        bindings.append(_normalize_pack_binding(
            binding,
            expected_ordinal=ordinal,
            expected_namespace=str(upstream_release["namespace"]),
        ))
    return bindings


def _normalize_pack_binding(
    value: object, *, expected_ordinal: int, expected_namespace: str,
) -> dict[str, object]:
    item = _mapping(value, label=f"pack binding[{expected_ordinal}]")
    _exact_keys(
        item, _PACK_BINDING_FIELDS, label=f"pack binding[{expected_ordinal}]"
    )
    ordinal = _exact_int(item["pack_ordinal"], label="pack ordinal")
    if ordinal != expected_ordinal or item["pack_id"] != source.PACK_IDS[ordinal]:
        _fail("pack binding ordinal/ID differs")
    registry_entry = _mapping(
        source.frozen_upstream_pack_registry_v1()["packs"][ordinal],
        label=f"frozen pack registry[{ordinal}]",
    )
    period_min = _mapping(
        item["source_period_min"], label="pack source period minimum"
    )
    period_max = _mapping(
        item["source_period_max"], label="pack source period maximum"
    )
    if (
        item["source_kind"] != registry_entry["source_kind"]
        or item["provenance_kind"] != registry_entry["provenance_kind"]
        or period_min != registry_entry["source_period_min"]
        or period_max != registry_entry["source_period_max"]
    ):
        _fail("pack binding source/provenance/period differs from registry")
    rows_identity = _normalize_identity(
        item["exact_rows_identity"], label=f"pack rows[{ordinal}]"
    )
    expected_uri = (
        f"{expected_namespace}packs/{item['pack_id']}/rows.json"
    )
    if rows_identity["uri"] != expected_uri:
        _fail("pack binding rows URI differs from the fixed namespace")
    query_value = item["warehouse_query_receipt_identity"]
    query_identity = (
        None if query_value is None else _normalize_identity(
            query_value, label=f"pack query receipt[{ordinal}]"
        )
    )
    artifact_identities = [
        _normalize_identity(value, label=f"pack artifact[{ordinal}:{index}]")
        for index, value in enumerate(_sequence(
            item["frozen_artifact_manifest_identities"],
            label=f"pack artifact identities[{ordinal}]",
        ))
    ]
    if [identity["uri"] for identity in artifact_identities] != sorted(
        str(identity["uri"]) for identity in artifact_identities
    ) or len({str(identity["uri"]) for identity in artifact_identities}) != len(
        artifact_identities
    ):
        _fail("pack artifact identities are not URI ordered")
    if registry_entry["provenance_kind"] == "warehouse-query-receipt":
        if query_identity is None or artifact_identities:
            _fail("warehouse pack provenance binding differs")
    elif query_identity is not None or not artifact_identities:
        _fail("artifact pack provenance binding differs")
    try:
        code = source.normalize_code_identity_v2(
            item["projection_code_identity"],
            label=f"pack projection code[{ordinal}]",
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupCapturePlanV1Error(str(exc)) from exc
    return {
        "pack_ordinal": ordinal,
        "pack_id": _identifier(item["pack_id"], label="pack ID"),
        "source_kind": registry_entry["source_kind"],
        "provenance_kind": registry_entry["provenance_kind"],
        "exact_rows_identity": rows_identity,
        "row_count": _exact_int(
            item["row_count"], label="pack row count", minimum=1
        ),
        "rows_sha256": _digest(item["rows_sha256"], label="pack rows SHA"),
        "source_period_min": period_min,
        "source_period_max": period_max,
        "warehouse_query_receipt_identity": query_identity,
        "frozen_artifact_manifest_identities": artifact_identities,
        "projection_code_identity": code,
    }


def _source_task_bindings(
    *,
    catalog_release: Mapping[str, object],
    candidate_release: Mapping[str, object],
) -> list[dict[str, object]]:
    catalogs = _sequence(catalog_release["entries"], label="catalog entries")
    candidates = _sequence(
        candidate_release["entries"], label="candidate entries"
    )
    if len(catalogs) != source.TASK_COUNT or len(candidates) != source.TASK_COUNT:
        _fail("capture plan source lattice must contain exactly 54 entries")
    return [
        _normalize_source_task_binding({
            "source_task_ordinal": ordinal,
            "task_id": _mapping(catalogs[ordinal], label="catalog entry")[
                "task_id"
            ],
            "slate": _mapping(catalogs[ordinal], label="catalog entry")[
                "slate"
            ],
            "lane_id": _mapping(catalogs[ordinal], label="catalog entry")[
                "lane_id"
            ],
            "lane_ordinal": _mapping(catalogs[ordinal], label="catalog entry")[
                "lane_ordinal"
            ],
            "task_ordinal": _mapping(catalogs[ordinal], label="catalog entry")[
                "task_ordinal"
            ],
            "accepted_slate_membership_sha256": _mapping(
                catalogs[ordinal], label="catalog entry"
            )["accepted_slate_membership_sha256"],
            "source_task_authority_sha256": _mapping(
                catalogs[ordinal], label="catalog entry"
            )["source_task_authority_sha256"],
            "catalog_identity": _mapping(
                catalogs[ordinal], label="catalog entry"
            )["catalog_identity"],
            "source_catalog_sha256": _mapping(
                catalogs[ordinal], label="catalog entry"
            )["source_catalog_sha256"],
            "player_count": _mapping(
                catalogs[ordinal], label="catalog entry"
            )["player_count"],
            "ordered_player_ids_sha256": _mapping(
                catalogs[ordinal], label="catalog entry"
            )["ordered_player_ids_sha256"],
            "accepted_candidate_release_entry_sha256": _mapping(
                candidates[ordinal], label="candidate entry"
            )["accepted_candidate_release_entry_sha256"],
            "candidate_artifact_identity": _mapping(
                candidates[ordinal], label="candidate entry"
            )["candidate_artifact_identity"],
            "candidate_count": _mapping(
                candidates[ordinal], label="candidate entry"
            )["candidate_count"],
            "ordered_candidate_ids_sha256": _mapping(
                candidates[ordinal], label="candidate entry"
            )["ordered_candidate_ids_sha256"],
        }, expected_ordinal=ordinal)
        for ordinal in range(source.TASK_COUNT)
    ]


def _normalize_source_task_binding(
    value: object, *, expected_ordinal: int,
) -> dict[str, object]:
    item = _mapping(value, label=f"source task binding[{expected_ordinal}]")
    _exact_keys(
        item,
        _SOURCE_TASK_BINDING_FIELDS,
        label=f"source task binding[{expected_ordinal}]",
    )
    ordinal = _exact_int(item["source_task_ordinal"], label="source ordinal")
    try:
        expected_slate = catalog_v1.expected_slate_for_source_task(ordinal)
        expected_lane = catalog_v1.expected_lane_for_source_task(ordinal)
        expected_task = catalog_v1.task_id_for_source_task(ordinal)
    except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6MatchupCapturePlanV1Error(str(exc)) from exc
    if (
        ordinal != expected_ordinal
        or item["task_id"] != expected_task
        or item["slate"] != expected_slate
        or item["lane_id"] != expected_lane["lane_id"]
        or item["lane_ordinal"] != expected_lane["lane_ordinal"]
        or item["task_ordinal"] != expected_lane["task_ordinal"]
    ):
        _fail("source task binding differs from the fixed 54-slate lattice")
    return {
        "source_task_ordinal": ordinal,
        "task_id": expected_task,
        "slate": expected_slate,
        "lane_id": expected_lane["lane_id"],
        "lane_ordinal": expected_lane["lane_ordinal"],
        "task_ordinal": expected_lane["task_ordinal"],
        "accepted_slate_membership_sha256": _digest(
            item["accepted_slate_membership_sha256"],
            label="accepted membership SHA",
        ),
        "source_task_authority_sha256": _digest(
            item["source_task_authority_sha256"],
            label="source-task authority SHA",
        ),
        "catalog_identity": _normalize_identity(
            item["catalog_identity"], label="source task catalog"
        ),
        "source_catalog_sha256": _digest(
            item["source_catalog_sha256"], label="source catalog SHA"
        ),
        "player_count": _exact_int(
            item["player_count"], label="source task player count", minimum=1
        ),
        "ordered_player_ids_sha256": _digest(
            item["ordered_player_ids_sha256"],
            label="ordered player IDs SHA",
        ),
        "accepted_candidate_release_entry_sha256": _digest(
            item["accepted_candidate_release_entry_sha256"],
            label="candidate release entry SHA",
        ),
        "candidate_artifact_identity": _normalize_identity(
            item["candidate_artifact_identity"],
            label="candidate artifact identity",
        ),
        "candidate_count": _exact_int(
            item["candidate_count"],
            label="candidate count",
            minimum=source.ENTRY_BUDGET,
        ),
        "ordered_candidate_ids_sha256": _digest(
            item["ordered_candidate_ids_sha256"],
            label="ordered candidate IDs SHA",
        ),
    }


def _finalizer_requirements() -> dict[str, object]:
    return {
        "required_source_task_count": source.TASK_COUNT,
        "required_upstream_pack_count": len(source.PACK_IDS),
        "required_role_count_per_slate": source.ROLE_COUNT,
        "required_component_count_per_slate": source.COMPONENT_ROLE_COUNT,
        "required_entry_budget": source.ENTRY_BUDGET,
        "exact_remote_reopen_required": True,
        "create_once_only_required": True,
        "same_reducer_full_and_deleted_replay_required": True,
        "physical_target_or_later_row_deletion_required": True,
        "nonzero_deletion_each_required_pack_and_slice": True,
        "all_54_support_census_required": True,
        "partial_producer_release_allowed": False,
        "caller_selected_root_allowed": False,
        "caller_selected_bundle_allowed": False,
        "caller_selected_namespace_allowed": False,
    }


def _code_identity(
    *, commit_sha: str, measurement: Mapping[str, object], module_path: str,
) -> dict[str, str]:
    if measurement["relative_path"] != module_path:
        _fail("code measurement path differs")
    return {
        "source_commit_sha": commit_sha,
        "module_path": module_path,
        "module_sha256": str(measurement["sha256"]),
    }


def build_capture_plan_lock_v1(
    *,
    adapter_final_release_lock_commit_sha: str,
    adapter_final_release_lock_raw: bytes,
    fixed_g0_replay_receipt: Mapping[str, object],
    fixed_g0_replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    implementation_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, object]],
    producer_id: str,
    producer_release_id: str,
    producer_namespace: str,
) -> dict[str, object]:
    """Build one non-authoritative lock from exact, already-frozen inputs."""
    _, final_lock_binding = _build_adapter_final_lock_binding(
        commit_sha=adapter_final_release_lock_commit_sha,
        raw=adapter_final_release_lock_raw,
    )
    receipt, receipt_identity, catalog_release_body, catalog_identity = (
        _validate_fixed_g0_replay_and_catalog(
            replay_receipt=fixed_g0_replay_receipt,
            replay_receipt_identity=fixed_g0_replay_receipt_identity,
            catalog_release=catalog_release,
            catalog_release_identity=catalog_release_identity,
        )
    )
    candidate_release, candidate_identity = _validate_accepted_candidate_release(
        value=accepted_candidate_release,
        identity=accepted_candidate_release_identity,
        catalog_release=catalog_release_body,
    )
    upstream_release, upstream_identity = _validate_upstream_release(
        value=upstream_source_release,
        identity=upstream_source_release_identity,
        pack_row_objects=upstream_pack_row_objects,
        expected_fixed_source_root_identity=receipt_identity,
    )
    commit = _commit(implementation_commit_sha, label="implementation commit")
    measurements = _normalize_implementation_measurements(
        implementation_measurements
    )
    source_code = _code_identity(
        commit_sha=commit,
        measurement=measurements[0],
        module_path=SOURCE_V2_MODULE_PATH,
    )
    producer_code = _code_identity(
        commit_sha=commit,
        measurement=measurements[1],
        module_path=COMPONENT_PRODUCER_MODULE_PATH,
    )
    upstream_namespace = _namespace(
        upstream_release["namespace"], label="upstream namespace"
    )
    candidate_namespace = _namespace(
        candidate_release["namespace"], label="candidate namespace"
    )
    catalog_namespace = _namespace(
        catalog_release_body["catalog_namespace"], label="catalog namespace"
    )
    normalized_producer_namespace = _namespace(
        producer_namespace, label="producer namespace"
    )
    namespaces = (
        catalog_namespace,
        candidate_namespace,
        upstream_namespace,
        normalized_producer_namespace,
    )
    if any(
        left == right or left.startswith(right) or right.startswith(left)
        for index, left in enumerate(namespaces)
        for right in namespaces[index + 1:]
    ):
        _fail("catalog, candidate, upstream, and producer namespaces overlap")
    packs = _pack_bindings(upstream_release)
    tasks = _source_task_bindings(
        catalog_release=catalog_release_body,
        candidate_release=candidate_release,
    )
    fixed_binding = fixed_g0_authority_binding_v1()
    body: dict[str, object] = {
        "schema_version": CAPTURE_PLAN_SCHEMA,
        "capture_plan_id": CAPTURE_PLAN_ID,
        "capture_plan_scope": CAPTURE_PLAN_SCOPE,
        "capture_plan_lock_relative_path": CAPTURE_PLAN_LOCK_PATH,
        "tracked_publication_mode": TRACKED_PUBLICATION_MODE,
        "allowed_project": PRODUCTION_PROJECT,
        "fixed_g0_authority_binding": fixed_binding,
        "fixed_g0_authority_binding_sha256": canonical_sha256(fixed_binding),
        "adapter_final_release_lock_binding": final_lock_binding,
        "fixed_g0_replay_receipt_identity": receipt_identity,
        "fixed_g0_replay_receipt_sha256": receipt["replay_receipt_sha256"],
        "catalog_release_identity": catalog_identity,
        "catalog_release_sha256": catalog_release_body["release_sha256"],
        "accepted_candidate_release_identity": candidate_identity,
        "accepted_candidate_release_sha256": candidate_release[
            "accepted_candidate_release_sha256"
        ],
        "upstream_source_release_identity": upstream_identity,
        "upstream_source_release_sha256": upstream_release[
            "upstream_release_sha256"
        ],
        "upstream_namespace": upstream_namespace,
        "upstream_pack_count": len(source.PACK_IDS),
        "upstream_pack_bindings": packs,
        "upstream_pack_binding_manifest_sha256": canonical_sha256(packs),
        "implementation_commit_sha": commit,
        "implementation_measurements": measurements,
        "implementation_measurement_manifest_sha256": canonical_sha256(
            measurements
        ),
        "source_v2_code_identity": source_code,
        "component_producer_code_identity": producer_code,
        "producer_id": _identifier(producer_id, label="producer ID"),
        "producer_release_id": _identifier(
            producer_release_id, label="producer release ID"
        ),
        "producer_namespace": normalized_producer_namespace,
        "source_task_count": source.TASK_COUNT,
        "source_task_bindings": tasks,
        "source_task_binding_manifest_sha256": canonical_sha256(tasks),
        "finalizer_requirements": _finalizer_requirements(),
        "canonical_json_plus_one_newline_required": True,
        "current_clean_git_required": True,
        "git_blob_current_byte_equality_required": True,
        "remote_exact_reopen_required": True,
        "lock_builder_capture_performed": False,
        "lock_builder_cloud_read_performed": False,
        "lock_builder_cloud_mutation_performed": False,
        "lock_builder_outcome_read_performed": False,
        **_policy(),
    }
    body["capture_plan_sha256"] = canonical_sha256(body)
    return validate_capture_plan_lock_v1(body)


def validate_capture_plan_lock_v1(value: object) -> dict[str, object]:
    """Validate the compact lock without opening any pinned remote body."""
    item = _mapping(value, label="R6 matchup capture plan")
    _exact_keys(item, _PLAN_FIELDS, label="R6 matchup capture plan")
    _validate_policy(item, label="R6 matchup capture plan")
    _reject_outcome_and_authority_carriers(
        item, label="R6 matchup capture plan"
    )
    retained = _digest(
        item["capture_plan_sha256"], label="capture plan self-hash"
    )
    unhashed = dict(item)
    del unhashed["capture_plan_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("capture plan self-hash differs")
    fixed_binding = _mapping(
        item["fixed_g0_authority_binding"], label="fixed G0 authority binding"
    )
    expected_fixed = fixed_g0_authority_binding_v1()
    if (
        fixed_binding != expected_fixed
        or item["fixed_g0_authority_binding_sha256"]
        != canonical_sha256(expected_fixed)
    ):
        _fail("capture plan differs from the accepted August-23 G0")
    final_lock_binding = _normalize_tracked_file_binding(
        item["adapter_final_release_lock_binding"],
        label="adapter final release lock binding",
    )
    if final_lock_binding["relative_path"] != fixed_g0.FIXED_FINAL_RELEASE_LOCK_PATH:
        _fail("adapter final release lock path differs")
    receipt_identity = _normalize_identity(
        item["fixed_g0_replay_receipt_identity"],
        label="fixed-G0 replay receipt",
    )
    catalog_identity = _normalize_identity(
        item["catalog_release_identity"], label="catalog release"
    )
    candidate_identity = _normalize_identity(
        item["accepted_candidate_release_identity"],
        label="accepted candidate release",
    )
    upstream_identity = _normalize_identity(
        item["upstream_source_release_identity"],
        label="upstream source release",
    )
    catalog_namespace = _namespace(
        expected_fixed["catalog_namespace"], label="fixed catalog namespace"
    )
    if (
        catalog_identity["uri"] != f"{catalog_namespace}catalog-release.json"
        or receipt_identity["uri"]
        != f"{catalog_namespace}{fixed_g0.REPLAY_RECEIPT_FILENAME}"
        or not str(candidate_identity["uri"]).endswith(
            "/accepted-candidate-release.json"
        )
    ):
        _fail("capture plan catalog/replay/candidate URI law differs")
    candidate_namespace = _namespace(
        str(candidate_identity["uri"]).removesuffix(
            "accepted-candidate-release.json"
        ),
        label="accepted candidate namespace",
    )
    for field in (
        "fixed_g0_replay_receipt_sha256",
        "catalog_release_sha256",
        "accepted_candidate_release_sha256",
        "upstream_source_release_sha256",
    ):
        _digest(item[field], label=field)
    upstream_namespace = _namespace(
        item["upstream_namespace"], label="upstream namespace"
    )
    if upstream_identity["uri"] != f"{upstream_namespace}upstream-release.json":
        _fail("capture plan upstream release URI differs")
    measurements = _normalize_implementation_measurements(
        item["implementation_measurements"]
    )
    commit = _commit(
        item["implementation_commit_sha"], label="implementation commit"
    )
    if item["implementation_measurement_manifest_sha256"] != canonical_sha256(
        measurements
    ):
        _fail("implementation measurement manifest differs")
    source_code = _code_identity(
        commit_sha=commit,
        measurement=measurements[0],
        module_path=SOURCE_V2_MODULE_PATH,
    )
    producer_code = _code_identity(
        commit_sha=commit,
        measurement=measurements[1],
        module_path=COMPONENT_PRODUCER_MODULE_PATH,
    )
    if (
        item["source_v2_code_identity"] != source_code
        or item["component_producer_code_identity"] != producer_code
    ):
        _fail("capture plan code identities differ from measured bytes")
    packs = [
        _normalize_pack_binding(
            row,
            expected_ordinal=ordinal,
            expected_namespace=upstream_namespace,
        )
        for ordinal, row in enumerate(_sequence(
            item["upstream_pack_bindings"], label="upstream pack bindings"
        ))
    ]
    if (
        item["upstream_pack_count"] != len(source.PACK_IDS)
        or len(packs) != len(source.PACK_IDS)
        or item["upstream_pack_binding_manifest_sha256"]
        != canonical_sha256(packs)
    ):
        _fail("capture plan seven-pack binding differs")
    tasks = [
        _normalize_source_task_binding(row, expected_ordinal=ordinal)
        for ordinal, row in enumerate(_sequence(
            item["source_task_bindings"], label="source task bindings"
        ))
    ]
    if (
        item["source_task_count"] != source.TASK_COUNT
        or len(tasks) != source.TASK_COUNT
        or item["source_task_binding_manifest_sha256"]
        != canonical_sha256(tasks)
    ):
        _fail("capture plan 54-task binding differs")
    for ordinal, task in enumerate(tasks):
        slate_id = str(task["slate"]["slate_id"])
        if task["catalog_identity"]["uri"] != (
            f"{catalog_namespace}tasks/{ordinal:04d}-{slate_id}/"
            "player-catalog.json"
        ):
            _fail("source task catalog URI differs from fixed release law")
        if task["candidate_artifact_identity"]["uri"] != (
            f"{candidate_namespace}source-task-{ordinal:02d}-{slate_id}/"
            "accepted-candidates.json"
        ):
            _fail("source task candidate URI differs from fixed release law")
    object_uris = [
        str(receipt_identity["uri"]),
        str(catalog_identity["uri"]),
        str(candidate_identity["uri"]),
        str(upstream_identity["uri"]),
        *(str(pack["exact_rows_identity"]["uri"]) for pack in packs),
        *(
            str(pack["warehouse_query_receipt_identity"]["uri"])
            for pack in packs
            if pack["warehouse_query_receipt_identity"] is not None
        ),
        *(
            str(identity["uri"])
            for pack in packs
            for identity in pack["frozen_artifact_manifest_identities"]
        ),
        *(str(task["catalog_identity"]["uri"]) for task in tasks),
        *(str(task["candidate_artifact_identity"]["uri"]) for task in tasks),
    ]
    if len(object_uris) != len(set(object_uris)):
        _fail("capture plan reuses an object URI across semantic roles")
    requirements = _mapping(
        item["finalizer_requirements"], label="finalizer requirements"
    )
    _exact_keys(
        requirements,
        _FINALIZER_REQUIREMENT_FIELDS,
        label="finalizer requirements",
    )
    if requirements != _finalizer_requirements():
        _fail("capture plan finalizer requirements differ")
    producer_namespace = _namespace(
        item["producer_namespace"], label="producer namespace"
    )
    _identifier(item["producer_id"], label="producer ID")
    _identifier(item["producer_release_id"], label="producer release ID")
    namespaces = (
        catalog_namespace,
        candidate_namespace,
        upstream_namespace,
        producer_namespace,
    )
    if any(
        left == right or left.startswith(right) or right.startswith(left)
        for index, left in enumerate(namespaces)
        for right in namespaces[index + 1:]
    ):
        _fail("capture plan namespaces overlap")
    if (
        item["schema_version"] != CAPTURE_PLAN_SCHEMA
        or item["capture_plan_id"] != CAPTURE_PLAN_ID
        or item["capture_plan_scope"] != CAPTURE_PLAN_SCOPE
        or item["capture_plan_lock_relative_path"] != CAPTURE_PLAN_LOCK_PATH
        or item["tracked_publication_mode"] != TRACKED_PUBLICATION_MODE
        or item["allowed_project"] != PRODUCTION_PROJECT
        or item["canonical_json_plus_one_newline_required"] is not True
        or item["current_clean_git_required"] is not True
        or item["git_blob_current_byte_equality_required"] is not True
        or item["remote_exact_reopen_required"] is not True
        or item["lock_builder_capture_performed"] is not False
        or item["lock_builder_cloud_read_performed"] is not False
        or item["lock_builder_cloud_mutation_performed"] is not False
        or item["lock_builder_outcome_read_performed"] is not False
    ):
        _fail("capture plan fixed law differs")
    normalized = dict(item)
    normalized.update({
        "fixed_g0_authority_binding": expected_fixed,
        "adapter_final_release_lock_binding": final_lock_binding,
        "fixed_g0_replay_receipt_identity": receipt_identity,
        "catalog_release_identity": catalog_identity,
        "accepted_candidate_release_identity": candidate_identity,
        "upstream_source_release_identity": upstream_identity,
        "upstream_namespace": upstream_namespace,
        "implementation_commit_sha": commit,
        "implementation_measurements": measurements,
        "source_v2_code_identity": source_code,
        "component_producer_code_identity": producer_code,
        "upstream_pack_bindings": packs,
        "source_task_bindings": tasks,
        "finalizer_requirements": requirements,
        "producer_namespace": producer_namespace,
        "capture_plan_sha256": retained,
    })
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("capture plan canonical replay differs")
    return normalized


def validate_capture_plan_against_prerequisites_v1(
    value: object,
    *,
    adapter_final_release_lock_commit_sha: str,
    adapter_final_release_lock_raw: bytes,
    fixed_g0_replay_receipt: Mapping[str, object],
    fixed_g0_replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Rebuild a lock from exact-opened bodies; no remote read occurs here."""
    normalized = validate_capture_plan_lock_v1(value)
    rebuilt = build_capture_plan_lock_v1(
        adapter_final_release_lock_commit_sha=(
            adapter_final_release_lock_commit_sha
        ),
        adapter_final_release_lock_raw=adapter_final_release_lock_raw,
        fixed_g0_replay_receipt=fixed_g0_replay_receipt,
        fixed_g0_replay_receipt_identity=fixed_g0_replay_receipt_identity,
        catalog_release=catalog_release,
        catalog_release_identity=catalog_release_identity,
        accepted_candidate_release=accepted_candidate_release,
        accepted_candidate_release_identity=accepted_candidate_release_identity,
        upstream_source_release=upstream_source_release,
        upstream_source_release_identity=upstream_source_release_identity,
        upstream_pack_row_objects=upstream_pack_row_objects,
        implementation_commit_sha=str(normalized["implementation_commit_sha"]),
        implementation_measurements=normalized[
            "implementation_measurements"
        ],
        producer_id=str(normalized["producer_id"]),
        producer_release_id=str(normalized["producer_release_id"]),
        producer_namespace=str(normalized["producer_namespace"]),
    )
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(normalized):
        _fail("capture plan differs from exact-opened prerequisites")
    return rebuilt


def _read_git_blob_exact(
    *,
    commit_sha: str,
    path: str,
    expected_sha256: str,
    expected_bytes: int,
    read_git_blob: ReadGitBlob,
    secure_read_current: SecureReadCurrent,
) -> bytes:
    try:
        blob = read_git_blob(commit_sha, path)
    except Exception as exc:
        raise CorpusR6MatchupCapturePlanV1Error(
            f"Git blob read failed for {path}"
        ) from exc
    current = _secure_current_bytes(
        path=path, secure_read_current=secure_read_current
    )
    if (
        type(blob) is not bytes
        or not blob
        or len(blob) != expected_bytes
        or sha256(blob).hexdigest() != expected_sha256
        or current != blob
    ):
        _fail(f"Git/current exact-byte replay differs for {path}")
    return blob


def reopen_capture_plan_lock_from_git_v1(
    *,
    plan_commit_sha: str,
    plan_file_sha256: str,
    plan_file_bytes: int,
    read_git_blob: ReadGitBlob,
    secure_read_current: SecureReadCurrent,
    repository_clean: bool,
) -> dict[str, object]:
    """Secure-replay the tracked lock and every local code/root byte.

    This function performs injected local reads only.  The caller must next
    exact-open the remote identities and call
    :func:`validate_capture_plan_against_prerequisites_v1` before finalizing.
    """
    if repository_clean is not True:
        _fail("capture-plan replay requires a clean repository")
    plan_commit = _commit(plan_commit_sha, label="capture-plan commit")
    expected_sha = _digest(plan_file_sha256, label="capture-plan file SHA")
    expected_bytes = _exact_int(
        plan_file_bytes, label="capture-plan file bytes", minimum=1
    )
    raw = _read_git_blob_exact(
        commit_sha=plan_commit,
        path=CAPTURE_PLAN_LOCK_PATH,
        expected_sha256=expected_sha,
        expected_bytes=expected_bytes,
        read_git_blob=read_git_blob,
        secure_read_current=secure_read_current,
    )
    plan = validate_capture_plan_lock_v1(_parse_canonical_json(
        raw, label="tracked capture-plan lock", require_one_newline=True
    ))
    implementation_commit = str(plan["implementation_commit_sha"])
    for measurement_value in plan["implementation_measurements"]:
        measurement = _mapping(
            measurement_value, label="capture-plan implementation measurement"
        )
        _read_git_blob_exact(
            commit_sha=implementation_commit,
            path=str(measurement["relative_path"]),
            expected_sha256=str(measurement["sha256"]),
            expected_bytes=int(measurement["bytes"]),
            read_git_blob=read_git_blob,
            secure_read_current=secure_read_current,
        )
    final_binding = _mapping(
        plan["adapter_final_release_lock_binding"],
        label="adapter final release lock binding",
    )
    final_raw = _read_git_blob_exact(
        commit_sha=str(final_binding["commit_sha"]),
        path=str(final_binding["relative_path"]),
        expected_sha256=str(final_binding["sha256"]),
        expected_bytes=int(final_binding["bytes"]),
        read_git_blob=read_git_blob,
        secure_read_current=secure_read_current,
    )
    final_lock = _validate_adapter_final_release_lock_raw(final_raw)
    if final_lock["final_release_lock_sha256"] != final_binding[
        "internal_sha256"
    ]:
        _fail("adapter final release lock internal binding differs")
    fixed = fixed_g0_authority_binding_v1()
    g0_raw = _read_git_blob_exact(
        commit_sha=str(fixed["evidence_source_commit_sha"]),
        path=str(fixed["g0_lock_relative_path"]),
        expected_sha256=str(fixed["g0_lock_file_sha256"]),
        expected_bytes=int(fixed["g0_lock_file_bytes"]),
        read_git_blob=read_git_blob,
        secure_read_current=secure_read_current,
    )
    g0 = _parse_canonical_json(
        g0_raw, label="accepted August-23 G0 lock", require_one_newline=True
    )
    if g0.get("g0_authority_lock_sha256") != fixed[
        "g0_lock_internal_sha256"
    ]:
        _fail("accepted G0 internal binding differs")
    return plan


__all__ = [
    "CAPTURE_PLAN_ID",
    "CAPTURE_PLAN_LOCK_PATH",
    "CAPTURE_PLAN_SCHEMA",
    "CAPTURE_PLAN_SCOPE",
    "COMPONENT_PRODUCER_MODULE_PATH",
    "CorpusR6MatchupCapturePlanV1Error",
    "FALSE_AUTHORITY_FIELDS",
    "IMPLEMENTATION_PATHS",
    "SOURCE_V2_MODULE_PATH",
    "build_capture_plan_lock_v1",
    "canonical_json_bytes",
    "canonical_sha256",
    "fixed_g0_authority_binding_v1",
    "measure_implementation_files_v1",
    "reopen_capture_plan_lock_from_git_v1",
    "validate_capture_plan_against_prerequisites_v1",
    "validate_capture_plan_lock_v1",
]
