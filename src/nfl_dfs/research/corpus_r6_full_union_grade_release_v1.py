"""Pure terminal release contract for the R6 full-union realized grade.

The score-once grader publishes 54 slate shards and an identity-bound root.
This module defines the smaller terminal object that may be used by an
external launcher to decide that the historical-outcome lease can be
released.  It owns no storage, query, lease, graph, or deployment client.

The completion is deliberately downstream of a full canonical replay of the
persisted grade.  It binds the exact structural freeze, outcome-supply
completion, projection, realized source, outcome snapshot, persisted grade
root, immutable runtime, and score-once coverage identities.  It grants no
retry, retune, graph, production, promotion, or decision authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_outcome_supply_v1 as supply
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading
from nfl_dfs.research import lr8_label_score_map as shared


GRADE_COMPLETION_SCHEMA: Final = (
    "corpus-r6-full-union-realized-grade-completion/v1"
)
OUTPUT_BUCKET: Final = supply.OUTPUT_BUCKET
OUTPUT_NAMESPACE: Final = "research/corpus-r6-full-union-realized-grades"
LEASE_RELEASE_OWNER: Final = supply.LEASE_RELEASE_OWNER

_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")

_COMPLETION_FIELDS: Final = frozenset({
    "schema_version", "run_id", "job", "execution", "code_sha", "image",
    "object_uri", "expected_supply_run_id", "expected_supply_job",
    "expected_supply_code_sha", "expected_supply_image",
    "panel_freeze_identity", "panel_freeze_sha256",
    "panel_freeze_object_sha256", "outcome_supply_completion_identity",
    "outcome_supply_completion_sha256", "supply_query_job_id",
    "actual_root_smoke_receipt_identity",
    "actual_root_smoke_receipt_sha256", "snapshot_module_sha256",
    "snapshot_cli_sha256", "snapshot_test_sha256",
    "snapshot_cli_test_sha256",
    "historical_outcome_lease_identity",
    "historical_outcome_lease_body_sha256",
    "outcome_key_projection_identity", "outcome_key_projection_sha256",
    "later_source_freeze_identity", "later_source_freeze_sha256",
    "realized_source_identity", "realized_source_sha256",
    "outcome_snapshot_identity", "outcome_snapshot_sha256",
    "persisted_grade_root_identity", "persisted_grade_root_sha256",
    "logical_grade_root_sha256", "slate_grade_objects_sha256",
    "slate_grade_descriptors_sha256", "aggregate_cells_sha256",
    "strategy_registry_sha256", "score_once_identity_sha256",
    "source_slate_count", "slate_grade_object_count",
    "rank_80_book_count", "prefix_grade_count", "aggregate_cell_count",
    "aggregate_slate_row_count", "unique_final_union_roster_count",
    "roster_sum_operation_ceiling", "roster_sum_operation_count",
    "actual_player_outcome_row_count",
    "every_unique_final_union_roster_scored_once",
    "roster_sum_operation_ceiling_equals_final_union_count",
    "every_book_projected_from_union_score_lookup",
    "all_4_14_80_prefixes_projected_from_rank_80",
    "actual_player_outcome_keys_exact",
    "canonical_persisted_grade_replay_complete", "complete",
    "contest_metrics_availability", "contest_rank", "contest_roi_micro_usd",
    "contest_metrics_unavailable_reason", "contest_rank_available",
    "contest_roi_available",
    "uses_realized_outcomes", "historical_outcome_lease_release_required",
    "lease_release_owner", "runtime_task_index", "runtime_task_count",
    "runtime_task_attempt",
    "terminal_execution_envelope_validated",
    "terminal_execution_envelope_validation_owner",
    "additional_historical_outcome_read",
    "bigquery_client_constructed", "outcome_query_executed",
    "historical_retry_licensed", "historical_retune_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "promotion_authority", "decision_authority", "grade_completion_sha256",
})


class CorpusR6FullUnionGradeReleaseV1Error(ValueError):
    """The terminal R6 realized-grade release contract failed closed."""


@dataclass(frozen=True, slots=True)
class FullUnionGradeReleaseConfigV1:
    """Immutable runtime identity and isolated grade output coordinate."""

    run_id: str
    job: str
    execution: str
    code_sha: str
    image: str
    expected_supply_run_id: str
    expected_supply_job: str
    expected_supply_code_sha: str
    expected_supply_image: str
    snapshot_module_sha256: str
    snapshot_cli_sha256: str
    snapshot_test_sha256: str
    snapshot_cli_test_sha256: str
    enabled: bool = False

    @property
    def output_root(self) -> str:
        return f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/{self.run_id}"

    @property
    def completion_uri(self) -> str:
        return f"{self.output_root}/grade-completion.json"


def _fail(message: str) -> None:
    raise CorpusR6FullUnionGradeReleaseV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionGradeReleaseV1Error(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionGradeReleaseV1Error(str(exc)) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be one canonical nonempty string")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def validate_grade_release_config_v1(
    value: object,
) -> FullUnionGradeReleaseConfigV1:
    if not isinstance(value, FullUnionGradeReleaseConfigV1):
        _fail("R6 full-union grade-release config type differs")
    if (
        value.enabled is not True
        or _RUN_ID.fullmatch(value.run_id) is None
        or _JOB.fullmatch(value.job) is None
        or _JOB.fullmatch(value.execution) is None
        or _CODE_SHA.fullmatch(value.code_sha) is None
        or _IMAGE.fullmatch(value.image) is None
        or _RUN_ID.fullmatch(value.expected_supply_run_id) is None
        or _JOB.fullmatch(value.expected_supply_job) is None
        or _CODE_SHA.fullmatch(value.expected_supply_code_sha) is None
        or _IMAGE.fullmatch(value.expected_supply_image) is None
        or any(_SHA256.fullmatch(item) is None for item in (
            value.snapshot_module_sha256,
            value.snapshot_cli_sha256,
            value.snapshot_test_sha256,
            value.snapshot_cli_test_sha256,
        ))
    ):
        _fail("R6 full-union grade-release runtime identity differs")
    return value


def _coverage(logical_root: Mapping[str, object]) -> dict[str, object]:
    value = _mapping(logical_root.get("coverage"), label="grade coverage")
    required = {
        "source_slate_count", "rank_80_book_count", "prefix_grade_count",
        "aggregate_cell_count", "aggregate_slate_row_count",
        "unique_final_union_roster_count", "roster_sum_operation_ceiling",
        "roster_sum_operation_count", "actual_player_outcome_row_count",
        "every_unique_final_union_roster_scored_once",
        "roster_sum_operation_ceiling_equals_final_union_count",
        "every_book_projected_from_union_score_lookup",
        "all_4_14_80_prefixes_projected_from_rank_80",
        "actual_player_outcome_keys_exact", "complete",
    }
    if not required.issubset(value):
        _fail("grade coverage lacks terminal release fields")
    return value


def _score_once_identity(
    *,
    persisted_grade_root: Mapping[str, object],
    logical_root: Mapping[str, object],
    coverage: Mapping[str, object],
) -> str:
    return canonical_sha256({
        "persisted_grade_root_sha256": persisted_grade_root[
            "persisted_grade_root_sha256"
        ],
        "logical_grade_root_sha256": logical_root["realized_grade_sha256"],
        "slate_grade_objects_sha256": persisted_grade_root[
            "slate_grade_objects_sha256"
        ],
        "slate_grade_descriptors_sha256": logical_root[
            "slate_grade_descriptors_sha256"
        ],
        "aggregate_cells_sha256": logical_root["aggregate_cells_sha256"],
        "outcome_snapshot_identity": logical_root["outcome_snapshot_identity"],
        "unique_final_union_roster_count": coverage[
            "unique_final_union_roster_count"
        ],
        "roster_sum_operation_count": coverage[
            "roster_sum_operation_count"
        ],
    })


def build_grade_completion_v1(
    *,
    config: FullUnionGradeReleaseConfigV1,
    panel_freeze_identity: object,
    outcome_supply_completion: object,
    outcome_supply_completion_identity: object,
    actual_root_smoke_receipt: object,
    actual_root_smoke_receipt_identity: object,
    historical_outcome_lease: object,
    outcome_key_projection: object,
    outcome_key_projection_identity: object,
    realized_source: object,
    realized_source_identity: object,
    outcome_snapshot: object,
    outcome_snapshot_identity: object,
    persisted_grade_root: object,
    persisted_grade_root_identity: object,
) -> dict[str, object]:
    """Build the release object after the caller's full persisted replay."""
    retained_config = validate_grade_release_config_v1(config)
    panel_identity = _identity(
        panel_freeze_identity, label="panel-freeze identity"
    )
    supply_completion = _mapping(
        outcome_supply_completion, label="outcome-supply completion"
    )
    supply_identity = _identity(
        outcome_supply_completion_identity,
        label="outcome-supply completion identity",
    )
    smoke_receipt = _mapping(
        actual_root_smoke_receipt, label="actual-root smoke receipt"
    )
    smoke_identity = _identity(
        actual_root_smoke_receipt_identity,
        label="actual-root smoke receipt identity",
    )
    lease = _mapping(
        historical_outcome_lease, label="historical-outcome lease binding"
    )
    lease_body = _mapping(
        lease.get("body"), label="historical-outcome lease body"
    )
    lease_receipt = _mapping(
        lease.get("object_receipt"), label="historical-outcome lease receipt"
    )
    try:
        lease_identity = _identity(
            {
                key: lease_receipt[key]
                for key in ("uri", "generation", "sha256", "bytes")
            },
            label="historical-outcome lease identity",
        )
    except KeyError as exc:
        raise CorpusR6FullUnionGradeReleaseV1Error(
            "historical-outcome lease receipt lacks content identity"
        ) from exc
    lease_raw = shared.canonical_json(lease_body)
    projection = _mapping(
        outcome_key_projection, label="outcome-key projection"
    )
    projection_identity = _identity(
        outcome_key_projection_identity, label="outcome-key projection identity"
    )
    source = _mapping(realized_source, label="realized source")
    source_identity = _identity(
        realized_source_identity, label="realized source identity"
    )
    snapshot = _mapping(outcome_snapshot, label="outcome snapshot")
    snapshot_identity = _identity(
        outcome_snapshot_identity, label="outcome snapshot identity"
    )
    persisted_root = _mapping(
        persisted_grade_root, label="persisted realized-grade root"
    )
    grade_identity = _identity(
        persisted_grade_root_identity, label="persisted grade-root identity"
    )
    logical_root = _mapping(
        persisted_root.get("logical_grade_root"), label="logical grade root"
    )
    coverage = _coverage(logical_root)
    contest_metrics = _mapping(
        logical_root.get("contest_metrics"), label="logical contest metrics"
    )

    for field, value in (
        ("panel_freeze_sha256", projection.get("panel_freeze_sha256")),
        ("outcome_supply_completion_sha256", supply_completion.get("completion_sha256")),
        ("actual_root_smoke_receipt_sha256", smoke_receipt.get("actual_root_smoke_receipt_sha256")),
        ("outcome_key_projection_sha256", projection.get("outcome_key_projection_sha256")),
        ("later_source_freeze_sha256", projection.get("later_source_freeze_sha256")),
        ("realized_source_sha256", source.get("realized_source_sha256")),
        ("outcome_snapshot_sha256", snapshot.get("outcome_snapshot_sha256")),
        ("persisted_grade_root_sha256", persisted_root.get("persisted_grade_root_sha256")),
        ("logical_grade_root_sha256", logical_root.get("realized_grade_sha256")),
        ("slate_grade_objects_sha256", persisted_root.get("slate_grade_objects_sha256")),
        ("slate_grade_descriptors_sha256", logical_root.get("slate_grade_descriptors_sha256")),
        ("aggregate_cells_sha256", logical_root.get("aggregate_cells_sha256")),
        ("strategy_registry_sha256", logical_root.get("strategy_registry_sha256")),
    ):
        _digest(value, label=field)
    query_job_id = _string(
        supply_completion.get("query_job_id"), label="supply query job ID"
    )

    if (
        supply_identity["uri"] != supply_completion.get("object_uri")
        or supply_completion.get("run_id") != retained_config.expected_supply_run_id
        or supply_completion.get("panel_freeze_identity") != panel_identity
        or supply_completion.get("outcome_key_projection_identity")
        != projection_identity
        or supply_completion.get("realized_source_identity") != source_identity
        or supply_completion.get("outcome_snapshot_identity") != snapshot_identity
        or supply_completion.get("actual_root_smoke_receipt_identity")
        != smoke_identity
        or smoke_receipt.get("panel_freeze_identity") != panel_identity
        or smoke_receipt.get("outcome_key_projection_identity")
        != projection_identity
        or smoke_receipt.get("reviewed_source_commit_sha")
        != retained_config.expected_supply_code_sha
        or smoke_receipt.get("runtime_immutable_image")
        != retained_config.expected_supply_image
        or smoke_receipt.get("snapshot_module_sha256")
        != retained_config.snapshot_module_sha256
        or smoke_receipt.get("snapshot_cli_sha256")
        != retained_config.snapshot_cli_sha256
        or smoke_receipt.get("snapshot_test_sha256")
        != retained_config.snapshot_test_sha256
        or smoke_receipt.get("snapshot_cli_test_sha256")
        != retained_config.snapshot_cli_test_sha256
        or frozenset(lease) != frozenset({"body", "object_receipt"})
        or frozenset(lease_body) != frozenset({
            "version", "run_id", "job", "code_sha", "image", "acquired_at",
        })
        or lease_body.get("version")
        != shared.adapter.HISTORICAL_OUTCOME_LEASE_VERSION
        or lease_body.get("run_id") != retained_config.expected_supply_run_id
        or lease_body.get("job") != retained_config.expected_supply_job
        or lease_body.get("code_sha") != retained_config.expected_supply_code_sha
        or lease_body.get("image") != retained_config.expected_supply_image
        or lease_identity["uri"] != shared.adapter.HISTORICAL_OUTCOME_LEASE_URI
        or lease_receipt.get("create_only") is not True
        or lease_identity["sha256"] != sha256(lease_raw).hexdigest()
        or lease_identity["bytes"] != len(lease_raw)
        or projection.get("panel_freeze_identity") != panel_identity
        or source.get("panel_freeze_identity") != panel_identity
        or snapshot.get("panel_freeze_identity") != panel_identity
        or source.get("outcome_key_projection_identity") != projection_identity
        or snapshot.get("outcome_key_projection_identity") != projection_identity
        or snapshot.get("realized_source_identity") != source_identity
        or logical_root.get("panel_freeze_identity") != panel_identity
        or logical_root.get("outcome_key_projection_identity")
        != projection_identity
        or logical_root.get("realized_source_identity") != source_identity
        or logical_root.get("outcome_snapshot_identity") != snapshot_identity
        or grade_identity["uri"] != persisted_root.get("target_uri")
        or grade_identity["uri"]
        != f"{retained_config.output_root}/realized-grade-root.json"
        or persisted_root.get("source_slate_count") != grading.SOURCE_SLATE_COUNT
        or not isinstance(persisted_root.get("slate_grade_objects"), list)
        or len(persisted_root["slate_grade_objects"])
        != grading.SOURCE_SLATE_COUNT
        or contest_metrics != {
            "availability": "unavailable",
            "reason": (
                "full_field_standings_duplicate_tie_settlement_and_"
                "payout_ladder_not_supplied"
            ),
            "rank": None,
            "roi_micro_usd": None,
        }
    ):
        _fail("grade completion upstream/root identity binding differs")

    integer_fields = (
        "source_slate_count", "rank_80_book_count", "prefix_grade_count",
        "aggregate_cell_count", "aggregate_slate_row_count",
        "unique_final_union_roster_count", "roster_sum_operation_ceiling",
        "roster_sum_operation_count", "actual_player_outcome_row_count",
    )
    for field in integer_fields:
        _integer(coverage.get(field), label=f"grade coverage {field}")
    if (
        coverage["source_slate_count"] != grading.SOURCE_SLATE_COUNT
        or coverage["rank_80_book_count"] != grading.PANEL_BOOK_COUNT
        or coverage["prefix_grade_count"] != grading.PANEL_PREFIX_COUNT
        or coverage["aggregate_cell_count"] != grading.AGGREGATE_CELL_COUNT
        or coverage["aggregate_slate_row_count"]
        != grading.AGGREGATE_SLATE_ROW_COUNT
        or coverage["unique_final_union_roster_count"]
        != coverage["roster_sum_operation_ceiling"]
        or coverage["roster_sum_operation_ceiling"]
        != coverage["roster_sum_operation_count"]
        or any(coverage.get(field) is not True for field in (
            "every_unique_final_union_roster_scored_once",
            "roster_sum_operation_ceiling_equals_final_union_count",
            "every_book_projected_from_union_score_lookup",
            "all_4_14_80_prefixes_projected_from_rank_80",
            "actual_player_outcome_keys_exact", "complete",
        ))
    ):
        _fail("grade completion score-once coverage differs")

    body: dict[str, object] = {
        "schema_version": GRADE_COMPLETION_SCHEMA,
        "run_id": retained_config.run_id,
        "job": retained_config.job,
        "execution": retained_config.execution,
        "code_sha": retained_config.code_sha,
        "image": retained_config.image,
        "object_uri": retained_config.completion_uri,
        "expected_supply_run_id": retained_config.expected_supply_run_id,
        "expected_supply_job": retained_config.expected_supply_job,
        "expected_supply_code_sha": retained_config.expected_supply_code_sha,
        "expected_supply_image": retained_config.expected_supply_image,
        "panel_freeze_identity": panel_identity,
        "panel_freeze_sha256": projection["panel_freeze_sha256"],
        "panel_freeze_object_sha256": panel_identity["sha256"],
        "outcome_supply_completion_identity": supply_identity,
        "outcome_supply_completion_sha256": supply_completion[
            "completion_sha256"
        ],
        "supply_query_job_id": query_job_id,
        "actual_root_smoke_receipt_identity": smoke_identity,
        "actual_root_smoke_receipt_sha256": smoke_receipt[
            "actual_root_smoke_receipt_sha256"
        ],
        "snapshot_module_sha256": retained_config.snapshot_module_sha256,
        "snapshot_cli_sha256": retained_config.snapshot_cli_sha256,
        "snapshot_test_sha256": retained_config.snapshot_test_sha256,
        "snapshot_cli_test_sha256": retained_config.snapshot_cli_test_sha256,
        "historical_outcome_lease_identity": lease_identity,
        "historical_outcome_lease_body_sha256": lease_identity["sha256"],
        "outcome_key_projection_identity": projection_identity,
        "outcome_key_projection_sha256": projection[
            "outcome_key_projection_sha256"
        ],
        "later_source_freeze_identity": projection[
            "later_source_freeze_identity"
        ],
        "later_source_freeze_sha256": projection[
            "later_source_freeze_sha256"
        ],
        "realized_source_identity": source_identity,
        "realized_source_sha256": source["realized_source_sha256"],
        "outcome_snapshot_identity": snapshot_identity,
        "outcome_snapshot_sha256": snapshot["outcome_snapshot_sha256"],
        "persisted_grade_root_identity": grade_identity,
        "persisted_grade_root_sha256": persisted_root[
            "persisted_grade_root_sha256"
        ],
        "logical_grade_root_sha256": logical_root["realized_grade_sha256"],
        "slate_grade_objects_sha256": persisted_root[
            "slate_grade_objects_sha256"
        ],
        "slate_grade_descriptors_sha256": logical_root[
            "slate_grade_descriptors_sha256"
        ],
        "aggregate_cells_sha256": logical_root["aggregate_cells_sha256"],
        "strategy_registry_sha256": logical_root["strategy_registry_sha256"],
        "score_once_identity_sha256": _score_once_identity(
            persisted_grade_root=persisted_root,
            logical_root=logical_root,
            coverage=coverage,
        ),
        "source_slate_count": grading.SOURCE_SLATE_COUNT,
        "slate_grade_object_count": grading.SOURCE_SLATE_COUNT,
        "rank_80_book_count": grading.PANEL_BOOK_COUNT,
        "prefix_grade_count": grading.PANEL_PREFIX_COUNT,
        "aggregate_cell_count": grading.AGGREGATE_CELL_COUNT,
        "aggregate_slate_row_count": grading.AGGREGATE_SLATE_ROW_COUNT,
        "unique_final_union_roster_count": coverage[
            "unique_final_union_roster_count"
        ],
        "roster_sum_operation_ceiling": coverage[
            "roster_sum_operation_ceiling"
        ],
        "roster_sum_operation_count": coverage[
            "roster_sum_operation_count"
        ],
        "actual_player_outcome_row_count": coverage[
            "actual_player_outcome_row_count"
        ],
        "every_unique_final_union_roster_scored_once": True,
        "roster_sum_operation_ceiling_equals_final_union_count": True,
        "every_book_projected_from_union_score_lookup": True,
        "all_4_14_80_prefixes_projected_from_rank_80": True,
        "actual_player_outcome_keys_exact": True,
        "canonical_persisted_grade_replay_complete": True,
        "complete": True,
        "contest_metrics_availability": "unavailable",
        "contest_rank": None,
        "contest_roi_micro_usd": None,
        "contest_metrics_unavailable_reason": contest_metrics["reason"],
        "contest_rank_available": False,
        "contest_roi_available": False,
        "uses_realized_outcomes": True,
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": LEASE_RELEASE_OWNER,
        "runtime_task_index": 0,
        "runtime_task_count": 1,
        "runtime_task_attempt": 0,
        "terminal_execution_envelope_validated": False,
        "terminal_execution_envelope_validation_owner": LEASE_RELEASE_OWNER,
        "additional_historical_outcome_read": False,
        "bigquery_client_constructed": False,
        "outcome_query_executed": False,
        "historical_retry_licensed": False,
        "historical_retune_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    body["grade_completion_sha256"] = canonical_sha256(body)
    return body


def validate_grade_completion_v1(
    value: object,
    *,
    identity: object,
    config: FullUnionGradeReleaseConfigV1,
    panel_freeze_identity: object,
    outcome_supply_completion: object,
    outcome_supply_completion_identity: object,
    actual_root_smoke_receipt: object,
    actual_root_smoke_receipt_identity: object,
    historical_outcome_lease: object,
    outcome_key_projection: object,
    outcome_key_projection_identity: object,
    realized_source: object,
    realized_source_identity: object,
    outcome_snapshot: object,
    outcome_snapshot_identity: object,
    persisted_grade_root: object,
    persisted_grade_root_identity: object,
) -> tuple[dict[str, object], dict[str, object]]:
    """Strictly replay a persisted terminal completion from explicit inputs."""
    completion = _mapping(value, label="realized-grade completion")
    _exact_keys(
        completion, _COMPLETION_FIELDS, label="realized-grade completion"
    )
    completion_identity = _identity(
        identity, label="realized-grade completion identity"
    )
    digest = _digest(
        completion.get("grade_completion_sha256"),
        label="grade completion SHA",
    )
    body = {
        key: item
        for key, item in completion.items()
        if key != "grade_completion_sha256"
    }
    if canonical_sha256(body) != digest:
        _fail("realized-grade completion self-hash differs")
    expected = build_grade_completion_v1(
        config=config,
        panel_freeze_identity=panel_freeze_identity,
        outcome_supply_completion=outcome_supply_completion,
        outcome_supply_completion_identity=outcome_supply_completion_identity,
        actual_root_smoke_receipt=actual_root_smoke_receipt,
        actual_root_smoke_receipt_identity=actual_root_smoke_receipt_identity,
        historical_outcome_lease=historical_outcome_lease,
        outcome_key_projection=outcome_key_projection,
        outcome_key_projection_identity=outcome_key_projection_identity,
        realized_source=realized_source,
        realized_source_identity=realized_source_identity,
        outcome_snapshot=outcome_snapshot,
        outcome_snapshot_identity=outcome_snapshot_identity,
        persisted_grade_root=persisted_grade_root,
        persisted_grade_root_identity=persisted_grade_root_identity,
    )
    if (
        completion_identity["uri"] != completion.get("object_uri")
        or completion_identity["sha256"]
        != sha256(canonical_json_bytes(completion)).hexdigest()
        or completion_identity["bytes"] != len(canonical_json_bytes(completion))
        or canonical_json_bytes(completion) != canonical_json_bytes(expected)
    ):
        _fail("realized-grade completion canonical replay differs")
    return completion, completion_identity


__all__ = [
    "CorpusR6FullUnionGradeReleaseV1Error",
    "FullUnionGradeReleaseConfigV1",
    "GRADE_COMPLETION_SCHEMA",
    "LEASE_RELEASE_OWNER",
    "OUTPUT_BUCKET",
    "OUTPUT_NAMESPACE",
    "build_grade_completion_v1",
    "canonical_json_bytes",
    "canonical_sha256",
    "validate_grade_completion_v1",
    "validate_grade_release_config_v1",
]
