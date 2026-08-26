"""Outcome-closed reporting over one persisted R6 realized-grade publication.

The reporter accepts one generation-pinned terminal completion plus an
independently supplied immutable grade/supply runtime contract. It may read
only that completion's isolated grade-run prefix: the persisted root and its
54 shards. Outcome sources, query evidence, and the historical-outcome lease
are represented only by identities already sealed into the completion/root
and are never opened here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_fast_lane_v1 as lane
from nfl_dfs.research import corpus_r6_full_union_grade_release_v1 as release
from nfl_dfs.research import corpus_r6_full_union_outcome_supply_v1 as supply
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading
from nfl_dfs.research import lr8_label_score_map as shared


REPORT_SCHEMA: Final = "corpus-r6-full-union-score-report/v1"
_COMPLETION_URI: Final = re.compile(
    rf"^gs://{re.escape(release.OUTPUT_BUCKET)}/"
    rf"{re.escape(release.OUTPUT_NAMESPACE)}/"
    r"(?P<run_id>[a-z0-9][a-z0-9-]{7,80})/grade-completion\.json$"
)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_CONTEST_UNAVAILABLE_REASON: Final = (
    "full_field_standings_duplicate_tie_settlement_and_"
    "payout_ladder_not_supplied"
)
_IDENTITY_FIELDS: Final = (
    "panel_freeze_identity",
    "outcome_supply_completion_identity",
    "actual_root_smoke_receipt_identity",
    "historical_outcome_lease_identity",
    "outcome_key_projection_identity",
    "later_source_freeze_identity",
    "realized_source_identity",
    "outcome_snapshot_identity",
    "persisted_grade_root_identity",
)
_TRUE_COMPLETION_FIELDS: Final = (
    "every_unique_final_union_roster_scored_once",
    "roster_sum_operation_ceiling_equals_final_union_count",
    "every_book_projected_from_union_score_lookup",
    "all_4_14_80_prefixes_projected_from_rank_80",
    "actual_player_outcome_keys_exact",
    "canonical_persisted_grade_replay_complete",
    "complete",
    "uses_realized_outcomes",
    "historical_outcome_lease_release_required",
)
_FALSE_COMPLETION_FIELDS: Final = (
    "contest_rank_available",
    "contest_roi_available",
    "terminal_execution_envelope_validated",
    "additional_historical_outcome_read",
    "bigquery_client_constructed",
    "outcome_query_executed",
    "historical_retry_licensed",
    "historical_retune_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "promotion_authority",
    "decision_authority",
)

ReadExact = Callable[[Mapping[str, object]], bytes]


class CorpusR6FullUnionScoreReportV1Error(ValueError):
    """The bounded persisted-score report failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6FullUnionScoreReportV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionScoreReportV1Error(str(exc)) from exc


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionScoreReportV1Error(str(exc)) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def _grade_run_prefix(
    completion_identity: Mapping[str, object],
) -> tuple[str, str]:
    uri = str(completion_identity["uri"])
    matched = _COMPLETION_URI.fullmatch(uri)
    if matched is None:
        _fail("grade completion URI is outside the isolated grade namespace")
    return uri.removesuffix("/grade-completion.json"), matched.group("run_id")


def _scoped_reader(
    *, read_exact: ReadExact, grade_run_prefix: str,
) -> ReadExact:
    """Reject every cross-run identity before delegating an exact read."""
    if not callable(read_exact):
        _fail("grade artifact exact reader differs")
    prefix = f"{grade_run_prefix}/"

    def read_scoped(identity: Mapping[str, object]) -> bytes:
        retained = _identity(identity, label="grade artifact identity")
        if not str(retained["uri"]).startswith(prefix):
            _fail("grade artifact identity escapes the selected grade-run prefix")
        return read_exact(retained)

    return read_scoped


def _exact_json(
    identity: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    retained = _identity(identity, label=f"{label} identity")
    try:
        raw = read_exact(retained)
    except CorpusR6FullUnionScoreReportV1Error:
        raise
    except Exception as exc:
        raise CorpusR6FullUnionScoreReportV1Error(
            f"{label} exact read failed"
        ) from exc
    if type(raw) is not bytes:
        _fail(f"{label} exact read did not return bytes")
    if len(raw) != retained["bytes"] or sha256(raw).hexdigest() != retained["sha256"]:
        _fail(f"{label} identity differs")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6FullUnionScoreReportV1Error(
            f"{label} is not canonical JSON"
        ) from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        _fail(f"{label} canonical bytes differ")
    return value, retained


def _validated_completion_before_root(
    *,
    completion: Mapping[str, object],
    completion_identity: Mapping[str, object],
    config: release.FullUnionGradeReleaseConfigV1,
    grade_run_prefix: str,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    """Validate every completion-only law before opening its root."""
    if frozenset(completion) != release._COMPLETION_FIELDS:  # noqa: SLF001
        _fail("grade completion fields differ")
    if completion.get("schema_version") != release.GRADE_COMPLETION_SCHEMA:
        _fail("grade completion schema differs")
    retained_hash = _digest(
        completion.get("grade_completion_sha256"), label="grade completion SHA"
    )
    body = {
        key: value for key, value in completion.items()
        if key != "grade_completion_sha256"
    }
    if retained_hash != release.canonical_sha256(body):
        _fail("grade completion self-hash differs")
    if (
        completion.get("object_uri") != completion_identity["uri"]
        or completion_identity["sha256"]
        != sha256(canonical_json_bytes(completion)).hexdigest()
        or completion_identity["bytes"] != len(canonical_json_bytes(completion))
        or completion.get("run_id") != config.run_id
        or completion.get("job") != config.job
        or completion.get("execution") != config.execution
        or completion.get("code_sha") != config.code_sha
        or completion.get("image") != config.image
        or completion.get("expected_supply_run_id")
        != config.expected_supply_run_id
        or completion.get("expected_supply_job") != config.expected_supply_job
        or completion.get("expected_supply_code_sha")
        != config.expected_supply_code_sha
        or completion.get("expected_supply_image") != config.expected_supply_image
        or completion.get("snapshot_module_sha256")
        != config.snapshot_module_sha256
        or completion.get("snapshot_cli_sha256") != config.snapshot_cli_sha256
        or completion.get("snapshot_test_sha256") != config.snapshot_test_sha256
        or completion.get("snapshot_cli_test_sha256")
        != config.snapshot_cli_test_sha256
    ):
        _fail("grade completion immutable runtime or supply pins differ")

    identities = {
        field: _identity(completion.get(field), label=field)
        for field in _IDENTITY_FIELDS
    }
    supply_root = (
        f"gs://{supply.OUTPUT_BUCKET}/{supply.OUTPUT_NAMESPACE}/"
        f"{config.expected_supply_run_id}"
    )
    expected_supply_uris = {
        "outcome_supply_completion_identity": f"{supply_root}/completion.json",
        "actual_root_smoke_receipt_identity": (
            f"{supply_root}/actual-root-smoke-receipt.json"
        ),
        "outcome_key_projection_identity": (
            f"{supply_root}/outcome-key-projection.json"
        ),
        "realized_source_identity": f"{supply_root}/realized-source.json",
        "outcome_snapshot_identity": f"{supply_root}/outcome-snapshot.json",
        "persisted_grade_root_identity": (
            f"{grade_run_prefix}/realized-grade-root.json"
        ),
    }
    if any(
        identities[field]["uri"] != expected_uri
        for field, expected_uri in expected_supply_uris.items()
    ):
        _fail("grade completion upstream or grade artifact URI differs")
    if (
        identities["historical_outcome_lease_identity"]["uri"]
        != shared.adapter.HISTORICAL_OUTCOME_LEASE_URI
        or completion.get("panel_freeze_object_sha256")
        != identities["panel_freeze_identity"]["sha256"]
        or completion.get("historical_outcome_lease_body_sha256")
        != identities["historical_outcome_lease_identity"]["sha256"]
    ):
        _fail("grade completion retained authority identity differs")

    for field, value in completion.items():
        if field.endswith("_sha256"):
            _digest(value, label=field)
    for field in (
        "source_slate_count", "slate_grade_object_count",
        "rank_80_book_count", "prefix_grade_count", "aggregate_cell_count",
        "aggregate_slate_row_count", "unique_final_union_roster_count",
        "roster_sum_operation_ceiling", "roster_sum_operation_count",
        "actual_player_outcome_row_count",
    ):
        _integer(completion.get(field), label=field)
    if (
        completion.get("source_slate_count") != grading.SOURCE_SLATE_COUNT
        or completion.get("slate_grade_object_count")
        != grading.SOURCE_SLATE_COUNT
        or completion.get("rank_80_book_count") != grading.PANEL_BOOK_COUNT
        or completion.get("prefix_grade_count") != grading.PANEL_PREFIX_COUNT
        or completion.get("aggregate_cell_count") != grading.AGGREGATE_CELL_COUNT
        or completion.get("aggregate_slate_row_count")
        != grading.AGGREGATE_SLATE_ROW_COUNT
        or completion.get("unique_final_union_roster_count")
        != completion.get("roster_sum_operation_ceiling")
        or completion.get("roster_sum_operation_ceiling")
        != completion.get("roster_sum_operation_count")
    ):
        _fail("grade completion terminal census differs")
    if any(completion.get(field) is not True for field in _TRUE_COMPLETION_FIELDS):
        _fail("grade completion required terminal flag differs")
    if any(completion.get(field) is not False for field in _FALSE_COMPLETION_FIELDS):
        _fail("grade completion forbidden authority flag differs")
    if (
        completion.get("contest_metrics_availability") != "unavailable"
        or completion.get("contest_rank") is not None
        or completion.get("contest_roi_micro_usd") is not None
        or completion.get("contest_metrics_unavailable_reason")
        != _CONTEST_UNAVAILABLE_REASON
        or completion.get("lease_release_owner") != release.LEASE_RELEASE_OWNER
        or completion.get("terminal_execution_envelope_validation_owner")
        != release.LEASE_RELEASE_OWNER
        or completion.get("runtime_task_index") != 0
        or completion.get("runtime_task_count") != 1
        or completion.get("runtime_task_attempt") != 0
        or type(completion.get("supply_query_job_id")) is not str
        or not str(completion.get("supply_query_job_id"))
        or str(completion.get("supply_query_job_id")).strip()
        != completion.get("supply_query_job_id")
    ):
        _fail("grade completion terminal authority law differs")
    return dict(completion), identities


def _validate_exact_strategy_registry_before_shards(
    persisted_root: Mapping[str, object],
) -> None:
    """Reject strategy/T230 drift before opening any grade shard."""
    logical_root = _mapping(
        persisted_root.get("logical_grade_root"), label="logical grade root"
    )
    registry = [
        _mapping(raw, label=f"strategy[{ordinal}]")
        for ordinal, raw in enumerate(
            _sequence(logical_root.get("strategy_registry"), label="strategies")
        )
    ]
    try:
        expected = lane.frozen_full_union_strategies_v1()
    except lane.CorpusR6FullUnionFastLaneV1Error as exc:
        raise CorpusR6FullUnionScoreReportV1Error(str(exc)) from exc
    if (
        len(expected) != grading.STRATEGIES_PER_SCOPE
        or canonical_json_bytes(registry) != canonical_json_bytes(expected)
        or logical_root.get("strategy_registry_sha256")
        != release.canonical_sha256(expected)
    ):
        _fail("exact immutable eight-strategy registry or T230 law differs")


def _validate_completion_root_binding(
    *,
    completion: Mapping[str, object],
    identities: Mapping[str, Mapping[str, object]],
    persisted_root: Mapping[str, object],
    persisted_root_identity: Mapping[str, object],
    logical_root: Mapping[str, object],
    shard_count: int,
) -> None:
    coverage = _mapping(logical_root.get("coverage"), label="grade coverage")
    identity_bindings = (
        ("panel_freeze_identity", "panel_freeze_identity"),
        ("outcome_key_projection_identity", "outcome_key_projection_identity"),
        ("later_source_freeze_identity", "later_source_freeze_identity"),
        ("realized_source_identity", "realized_source_identity"),
        ("outcome_snapshot_identity", "outcome_snapshot_identity"),
    )
    digest_bindings = (
        ("panel_freeze_sha256", "panel_freeze_sha256"),
        ("outcome_key_projection_sha256", "outcome_key_projection_sha256"),
        ("later_source_freeze_sha256", "later_source_freeze_sha256"),
        ("realized_source_sha256", "realized_source_sha256"),
        ("outcome_snapshot_sha256", "outcome_snapshot_sha256"),
        ("logical_grade_root_sha256", "realized_grade_sha256"),
        ("slate_grade_descriptors_sha256", "slate_grade_descriptors_sha256"),
        ("aggregate_cells_sha256", "aggregate_cells_sha256"),
        ("strategy_registry_sha256", "strategy_registry_sha256"),
    )
    if (
        persisted_root_identity != identities["persisted_grade_root_identity"]
        or completion.get("persisted_grade_root_sha256")
        != persisted_root.get("persisted_grade_root_sha256")
        or completion.get("slate_grade_objects_sha256")
        != persisted_root.get("slate_grade_objects_sha256")
        or shard_count != grading.SOURCE_SLATE_COUNT
        or any(
            completion.get(completion_field) != logical_root.get(root_field)
            for completion_field, root_field in digest_bindings
        )
        or any(
            identities[completion_field] != logical_root.get(root_field)
            for completion_field, root_field in identity_bindings
        )
    ):
        _fail("grade completion/root lineage binding differs")
    coverage_fields = (
        "source_slate_count", "rank_80_book_count", "prefix_grade_count",
        "aggregate_cell_count", "aggregate_slate_row_count",
        "unique_final_union_roster_count", "roster_sum_operation_ceiling",
        "roster_sum_operation_count", "actual_player_outcome_row_count",
        "every_unique_final_union_roster_scored_once",
        "roster_sum_operation_ceiling_equals_final_union_count",
        "every_book_projected_from_union_score_lookup",
        "all_4_14_80_prefixes_projected_from_rank_80",
        "actual_player_outcome_keys_exact",
    )
    if any(
        completion.get(field) != coverage.get(field) for field in coverage_fields
    ):
        _fail("grade completion/root score-once coverage binding differs")
    expected_score_once = release._score_once_identity(  # noqa: SLF001
        persisted_grade_root=persisted_root,
        logical_root=logical_root,
        coverage=coverage,
    )
    if completion.get("score_once_identity_sha256") != expected_score_once:
        _fail("grade completion score-once identity differs")
    if logical_root.get("contest_metrics") != {
        "availability": "unavailable",
        "reason": _CONTEST_UNAVAILABLE_REASON,
        "rank": None,
        "roi_micro_usd": None,
    }:
        _fail("grade completion/root contest authority differs")


def build_persisted_score_report_v1(
    *,
    grade_completion_identity: object,
    grade_release_config: release.FullUnionGradeReleaseConfigV1,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Exact-open one completion/root/54 shards and return aggregates only."""
    completion_identity = _identity(
        grade_completion_identity, label="grade completion identity"
    )
    grade_run_prefix, uri_run_id = _grade_run_prefix(completion_identity)
    try:
        config = release.validate_grade_release_config_v1(grade_release_config)
    except release.CorpusR6FullUnionGradeReleaseV1Error as exc:
        raise CorpusR6FullUnionScoreReportV1Error(str(exc)) from exc
    if (
        config.run_id != uri_run_id
        or config.output_root != grade_run_prefix
        or config.completion_uri != completion_identity["uri"]
    ):
        _fail("grade completion URI/runtime coordinate differs")
    read_scoped = _scoped_reader(
        read_exact=read_exact, grade_run_prefix=grade_run_prefix
    )
    completion, reopened_completion_identity = _exact_json(
        completion_identity, read_exact=read_scoped, label="grade completion"
    )
    completion, identities = _validated_completion_before_root(
        completion=completion,
        completion_identity=reopened_completion_identity,
        config=config,
        grade_run_prefix=grade_run_prefix,
    )
    root_identity = identities["persisted_grade_root_identity"]
    root, _ = _exact_json(
        root_identity, read_exact=read_scoped, label="persisted grade root"
    )
    _validate_exact_strategy_registry_before_shards(root)
    try:
        (
            persisted_root,
            reopened_root_identity,
            logical_root,
            shards,
            _shard_identities,
            output_prefix,
        ) = grading._validate_persisted_root_structure_v1(  # noqa: SLF001
            root, identity=root_identity, read_exact=read_scoped
        )
    except CorpusR6FullUnionScoreReportV1Error:
        raise
    except Exception as exc:
        raise CorpusR6FullUnionScoreReportV1Error(str(exc)) from exc
    if output_prefix != grade_run_prefix:
        _fail("persisted grade output prefix differs")
    _validate_completion_root_binding(
        completion=completion,
        identities=identities,
        persisted_root=persisted_root,
        persisted_root_identity=reopened_root_identity,
        logical_root=logical_root,
        shard_count=len(shards),
    )

    registry = list(logical_root["strategy_registry"])
    cells_by_strategy: dict[int, list[dict[str, object]]] = {
        ordinal: [] for ordinal in range(grading.STRATEGIES_PER_SCOPE)
    }
    for raw in logical_root["aggregate_cells"]:
        cell = dict(raw)
        ordinal = int(cell["strategy_ordinal"])
        cells_by_strategy.get(ordinal, []).append({
            "scope_ordinal": cell["scope_ordinal"],
            "fit_scope_id": cell["fit_scope_id"],
            "entry_count": cell["entry_count"],
            "lineup_occurrence_count": cell["lineup_occurrence_count"],
            "lineup_score_mean": cell["lineup_score_mean"],
            "slate_maximum_mean": cell["slate_maximum_mean"],
            "slate_maximum_median": cell["slate_maximum_median"],
            "minimum_slate_maximum_micro": cell["minimum_slate_maximum_micro"],
            "maximum_slate_maximum_micro": cell["maximum_slate_maximum_micro"],
            "thresholds": cell["thresholds"],
        })
    strategies: list[dict[str, object]] = []
    for ordinal, registry_row in enumerate(registry):
        cells = sorted(
            cells_by_strategy[ordinal],
            key=lambda row: (int(row["scope_ordinal"]), int(row["entry_count"])),
        )
        if len(cells) != grading.SCOPES_PER_SLATE * len(grading.PREFIX_SIZES):
            _fail("strategy score-cell census differs")
        strategies.append({
            "strategy_ordinal": ordinal,
            "strategy_id": registry_row["strategy_id"],
            "strategy_sha256": registry_row["strategy_sha256"],
            "strict_230_strategy": registry_row["strategy_id"]
            == lane.STRICT_230_STRATEGY_ID,
            "cells": cells,
        })
    result: dict[str, object] = {
        "schema_version": REPORT_SCHEMA,
        "grade_completion_identity": completion_identity,
        "persisted_grade_root_identity": root_identity,
        "source_slate_count": grading.SOURCE_SLATE_COUNT,
        "slate_grade_object_count": len(shards),
        "strategy_count": len(strategies),
        "strategy_summaries": strategies,
        "contest_metrics": logical_root["contest_metrics"],
        "reads_grade_artifacts_only": True,
        "outcome_source_read": False,
        "bigquery_client_constructed": False,
        "historical_outcome_lease_read": False,
        "complete": True,
    }
    result["score_report_sha256"] = sha256(canonical_json_bytes(result)).hexdigest()
    return result


__all__ = [
    "CorpusR6FullUnionScoreReportV1Error",
    "REPORT_SCHEMA",
    "build_persisted_score_report_v1",
    "canonical_json_bytes",
]
