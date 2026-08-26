"""Focused pure tests for the R6 realized-grade terminal completion."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_grade_release_v1 as release
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading
from nfl_dfs.research import lr8_label_score_map as shared


def _identity(uri: str, marker: str) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": marker * 64,
        "bytes": 100,
    }


def _config(*, enabled: bool = True) -> release.FullUnionGradeReleaseConfigV1:
    return release.FullUnionGradeReleaseConfigV1(
        run_id="r6-grade-release-fixture",
        job="r6-grade-job",
        execution="r6-grade-job-abc12",
        code_sha="a" * 40,
        image=f"fixture@sha256:{'b' * 64}",
        expected_supply_run_id="r6-supply-fixture",
        expected_supply_job="r6-supply-job",
        expected_supply_code_sha="c" * 40,
        expected_supply_image=f"supply@sha256:{'d' * 64}",
        snapshot_module_sha256="1" * 64,
        snapshot_cli_sha256="2" * 64,
        snapshot_test_sha256="3" * 64,
        snapshot_cli_test_sha256="4" * 64,
        enabled=enabled,
    )


def _case() -> dict[str, object]:
    config = _config()
    panel_identity = _identity(
        "gs://fixture/research/freeze/panel-freeze.json", "1"
    )
    projection_identity = _identity(
        "gs://fixture/supply/outcome-key-projection.json", "2"
    )
    source_identity = _identity(
        "gs://fixture/supply/realized-source.json", "3"
    )
    snapshot_identity = _identity(
        "gs://fixture/supply/outcome-snapshot.json", "4"
    )
    supply_identity = _identity(
        "gs://fixture/supply/completion.json", "5"
    )
    smoke_identity = _identity("gs://fixture/supply/smoke.json", "6")
    later_identity = _identity("gs://fixture/later-source.json", "6")
    projection = {
        "panel_freeze_identity": panel_identity,
        "panel_freeze_sha256": "7" * 64,
        "outcome_key_projection_sha256": "8" * 64,
        "later_source_freeze_identity": later_identity,
        "later_source_freeze_sha256": "9" * 64,
    }
    source = {
        "panel_freeze_identity": panel_identity,
        "outcome_key_projection_identity": projection_identity,
        "realized_source_sha256": "a" * 64,
    }
    snapshot = {
        "panel_freeze_identity": panel_identity,
        "outcome_key_projection_identity": projection_identity,
        "realized_source_identity": source_identity,
        "outcome_snapshot_sha256": "b" * 64,
    }
    supply_completion = {
        "run_id": config.expected_supply_run_id,
        "object_uri": supply_identity["uri"],
        "completion_sha256": "c" * 64,
        "query_job_id": "r6_full_union_realized_fixture",
        "panel_freeze_identity": panel_identity,
        "outcome_key_projection_identity": projection_identity,
        "realized_source_identity": source_identity,
        "outcome_snapshot_identity": snapshot_identity,
        "actual_root_smoke_receipt_identity": smoke_identity,
    }
    smoke_receipt = {
        "panel_freeze_identity": panel_identity,
        "outcome_key_projection_identity": projection_identity,
        "reviewed_source_commit_sha": config.expected_supply_code_sha,
        "runtime_immutable_image": config.expected_supply_image,
        "snapshot_module_sha256": config.snapshot_module_sha256,
        "snapshot_cli_sha256": config.snapshot_cli_sha256,
        "snapshot_test_sha256": config.snapshot_test_sha256,
        "snapshot_cli_test_sha256": config.snapshot_cli_test_sha256,
        "actual_root_smoke_receipt_sha256": "6" * 64,
    }
    lease_body = {
        "version": "historical-outcome-active-v1",
        "run_id": config.expected_supply_run_id,
        "job": config.expected_supply_job,
        "code_sha": config.expected_supply_code_sha,
        "image": config.expected_supply_image,
        "acquired_at": "2026-08-26T00:00:00+00:00",
    }
    lease_raw = shared.canonical_json(lease_body)
    lease_identity = {
        "uri": (
            "gs://nfl-predictions-503414-raw/research-governance/"
            "historical-outcome-active-v1.json"
        ),
        "generation": "1",
        "sha256": sha256(lease_raw).hexdigest(),
        "bytes": len(lease_raw),
    }
    historical_lease = {
        "body": lease_body,
        "object_receipt": {**lease_identity, "create_only": True},
    }
    coverage = {
        "source_slate_count": grading.SOURCE_SLATE_COUNT,
        "rank_80_book_count": grading.PANEL_BOOK_COUNT,
        "prefix_grade_count": grading.PANEL_PREFIX_COUNT,
        "aggregate_cell_count": grading.AGGREGATE_CELL_COUNT,
        "aggregate_slate_row_count": grading.AGGREGATE_SLATE_ROW_COUNT,
        "unique_final_union_roster_count": 123_456,
        "roster_sum_operation_ceiling": 123_456,
        "roster_sum_operation_count": 123_456,
        "actual_player_outcome_row_count": 12_345,
        "every_unique_final_union_roster_scored_once": True,
        "roster_sum_operation_ceiling_equals_final_union_count": True,
        "every_book_projected_from_union_score_lookup": True,
        "all_4_14_80_prefixes_projected_from_rank_80": True,
        "actual_player_outcome_keys_exact": True,
        "complete": True,
    }
    logical = {
        "panel_freeze_identity": panel_identity,
        "outcome_key_projection_identity": projection_identity,
        "realized_source_identity": source_identity,
        "outcome_snapshot_identity": snapshot_identity,
        "realized_grade_sha256": "d" * 64,
        "slate_grade_descriptors_sha256": "e" * 64,
        "aggregate_cells_sha256": "f" * 64,
        "strategy_registry_sha256": "0" * 64,
        "coverage": coverage,
        "contest_metrics": {
            "availability": "unavailable",
            "reason": (
                "full_field_standings_duplicate_tie_settlement_and_"
                "payout_ladder_not_supplied"
            ),
            "rank": None,
            "roi_micro_usd": None,
        },
    }
    persisted = {
        "target_uri": f"{config.output_root}/realized-grade-root.json",
        "source_slate_count": grading.SOURCE_SLATE_COUNT,
        "slate_grade_objects": [{} for _ in range(grading.SOURCE_SLATE_COUNT)],
        "slate_grade_objects_sha256": "1" * 64,
        "persisted_grade_root_sha256": "2" * 64,
        "logical_grade_root": logical,
    }
    persisted_identity = _identity(str(persisted["target_uri"]), "3")
    return {
        "config": config,
        "panel_freeze_identity": panel_identity,
        "outcome_supply_completion": supply_completion,
        "outcome_supply_completion_identity": supply_identity,
        "actual_root_smoke_receipt": smoke_receipt,
        "actual_root_smoke_receipt_identity": smoke_identity,
        "historical_outcome_lease": historical_lease,
        "outcome_key_projection": projection,
        "outcome_key_projection_identity": projection_identity,
        "realized_source": source,
        "realized_source_identity": source_identity,
        "outcome_snapshot": snapshot,
        "outcome_snapshot_identity": snapshot_identity,
        "persisted_grade_root": persisted,
        "persisted_grade_root_identity": persisted_identity,
    }


def _build(case: dict[str, object]) -> dict[str, object]:
    return release.build_grade_completion_v1(**case)  # type: ignore[arg-type]


def test_completion_binds_runtime_upstreams_and_score_once_census() -> None:
    completion = _build(_case())

    assert completion["schema_version"] == release.GRADE_COMPLETION_SCHEMA
    assert completion["job"] == "r6-grade-job"
    assert completion["execution"] == "r6-grade-job-abc12"
    assert completion["source_slate_count"] == 54
    assert completion["slate_grade_object_count"] == 54
    assert completion["rank_80_book_count"] == 2592
    assert completion["prefix_grade_count"] == 7776
    assert completion["aggregate_cell_count"] == 144
    assert completion["every_unique_final_union_roster_scored_once"] is True
    assert completion["canonical_persisted_grade_replay_complete"] is True
    assert completion["uses_realized_outcomes"] is True
    assert completion["historical_outcome_lease_release_required"] is True
    assert completion["terminal_execution_envelope_validated"] is False
    assert completion["runtime_task_attempt"] == 0
    assert completion["contest_metrics_availability"] == "unavailable"
    assert completion["contest_rank"] is None
    assert completion["contest_roi_micro_usd"] is None
    assert completion["contest_rank_available"] is False
    assert completion["contest_roi_available"] is False
    assert completion["expected_supply_run_id"] == "r6-supply-fixture"
    assert completion["expected_supply_job"] == "r6-supply-job"
    assert completion["actual_root_smoke_receipt_identity"] == (
        _case()["actual_root_smoke_receipt_identity"]
    )
    lease_receipt = _case()["historical_outcome_lease"][  # type: ignore[index]
        "object_receipt"
    ]
    assert completion["historical_outcome_lease_identity"] == {
        key: lease_receipt[key]
        for key in ("uri", "generation", "sha256", "bytes")
    }
    for field in (
        "additional_historical_outcome_read", "bigquery_client_constructed",
        "outcome_query_executed", "historical_retry_licensed",
        "historical_retune_licensed", "graph_mutation_licensed",
        "production_change_licensed", "promotion_authority",
        "decision_authority",
    ):
        assert completion[field] is False


def test_completion_exact_round_trip() -> None:
    case = _case()
    completion = _build(case)
    identity = batch.object_identity_for_json(
        completion,
        uri=case["config"].completion_uri,  # type: ignore[union-attr]
        generation="19",
    )

    observed, observed_identity = release.validate_grade_completion_v1(
        completion, identity=identity, **case  # type: ignore[arg-type]
    )

    assert observed == completion
    assert observed_identity == identity


@pytest.mark.parametrize(
    "field",
    [
        "panel_freeze_identity",
        "outcome_key_projection_identity",
        "realized_source_identity",
        "outcome_snapshot_identity",
    ],
)
def test_completion_rejects_wrong_explicit_upstream_identity(field: str) -> None:
    case = _case()
    case[field] = _identity("gs://fixture/wrong.json", "9")

    with pytest.raises(
        release.CorpusR6FullUnionGradeReleaseV1Error,
        match="binding differs",
    ):
        _build(case)


def test_completion_rejects_grade_root_tampering() -> None:
    case = _case()
    persisted = deepcopy(case["persisted_grade_root"])
    persisted["logical_grade_root"]["coverage"][  # type: ignore[index]
        "roster_sum_operation_count"
    ] = 123_455
    case["persisted_grade_root"] = persisted

    with pytest.raises(
        release.CorpusR6FullUnionGradeReleaseV1Error,
        match="score-once coverage differs",
    ):
        _build(case)


@pytest.mark.parametrize(
    ("field", "value"),
    [("reason", "rank_not_loaded"), ("rank", 1), ("roi_micro_usd", 100)],
)
def test_completion_rejects_contest_metric_authority_flip(
    field: str, value: object,
) -> None:
    case = _case()
    persisted = deepcopy(case["persisted_grade_root"])
    persisted["logical_grade_root"]["contest_metrics"][field] = value  # type: ignore[index]
    case["persisted_grade_root"] = persisted

    with pytest.raises(
        release.CorpusR6FullUnionGradeReleaseV1Error,
        match="binding differs",
    ):
        _build(case)


def test_completion_rejects_root_outside_isolated_grade_prefix() -> None:
    case = _case()
    case["persisted_grade_root_identity"] = _identity(
        "gs://fixture/other/realized-grade-root.json", "8"
    )

    with pytest.raises(
        release.CorpusR6FullUnionGradeReleaseV1Error,
        match="binding differs",
    ):
        _build(case)


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("expected_supply_run_id", "wrong-supply-run"),
        ("expected_supply_job", "wrong-supply-job"),
        ("expected_supply_code_sha", "e" * 40),
        ("expected_supply_image", f"wrong@sha256:{'e' * 64}"),
        ("snapshot_module_sha256", "e" * 64),
        ("snapshot_cli_sha256", "e" * 64),
        ("snapshot_test_sha256", "e" * 64),
        ("snapshot_cli_test_sha256", "e" * 64),
    ],
)
def test_completion_rejects_each_independent_supply_pin(
    field: str, wrong: str,
) -> None:
    case = _case()
    case["config"] = replace(case["config"], **{field: wrong})

    with pytest.raises(
        release.CorpusR6FullUnionGradeReleaseV1Error,
        match="binding differs",
    ):
        _build(case)


def test_config_is_default_off_and_requires_runtime_execution() -> None:
    with pytest.raises(
        release.CorpusR6FullUnionGradeReleaseV1Error,
        match="runtime identity differs",
    ):
        release.validate_grade_release_config_v1(_config(enabled=False))

    bad = release.FullUnionGradeReleaseConfigV1(
        run_id="r6-grade-release-fixture",
        job="r6-grade-job",
        execution="not valid",
        code_sha="a" * 40,
        image=f"fixture@sha256:{'b' * 64}",
        expected_supply_run_id="r6-supply-fixture",
        expected_supply_job="r6-supply-job",
        expected_supply_code_sha="c" * 40,
        expected_supply_image=f"supply@sha256:{'d' * 64}",
        snapshot_module_sha256="1" * 64,
        snapshot_cli_sha256="2" * 64,
        snapshot_test_sha256="3" * 64,
        snapshot_cli_test_sha256="4" * 64,
        enabled=True,
    )
    with pytest.raises(
        release.CorpusR6FullUnionGradeReleaseV1Error,
        match="runtime identity differs",
    ):
        release.validate_grade_release_config_v1(bad)
