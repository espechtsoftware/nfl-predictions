from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from nfl_dfs.research import corpus_r6_fair_fill_retest_v1 as retest
from nfl_dfs.research import corpus_r6_population_challenger_runtime_v1 as runtime
from nfl_dfs.research import residual_world_columns as rw


def _roster(variant: int) -> list[str]:
    return sorted([
        "dst-a",
        "qb-a",
        "rb-a",
        "rb-b",
        "te-a",
        "wr-a",
        "wr-b",
        "wr-c",
        f"wr-v-{variant:03d}",
    ])


def _cell(
    *,
    strategy_id: str,
    profile_id: str,
    variants: int,
    extra_heldout_variant: bool = False,
    family_tag: str | None = None,
    scheduled_attempts: int = 180,
    source_authoritative: bool = False,
    test_only: bool = True,
) -> dict[str, object]:
    occurrences: list[dict[str, object]] = []
    for block in rw.WORLD_BLOCKS:
        count = variants + int(extra_heldout_variant and block == "R4")
        for ordinal in range(count):
            tags = ["lev"]
            if family_tag is not None and ordinal % 2 == 0:
                tags.append(family_tag)
            occurrences.append({
                "origin_id": block,
                "candidate_ordinal": ordinal,
                "roster_player_ids": _roster(ordinal),
                "family_tags": sorted(tags),
            })
    receipts = [
        {
            "schema": retest.WORK_RECEIPT_SCHEMA,
            "origin_id": block,
            "scheduled_optimizer_attempts": scheduled_attempts,
            "attempted_optimizer_calls": scheduled_attempts,
            "optimal_calls": scheduled_attempts,
            "infeasible_calls": 0,
            "error_calls": 0,
            "retained_occurrence_count": variants
            + int(extra_heldout_variant and block == "R4"),
        }
        for block in rw.WORLD_BLOCKS
    ]
    return retest.build_candidate_cell_from_occurrences_v1(
        slate={"season": 2023, "week": 1, "slate_id": "2023-w01"},
        fill_strategy_id=strategy_id,
        construction_profile_id=profile_id,
        occurrences=occurrences,
        work_receipts=receipts,
        source_bindings={
            "schema": "corpus-r6-fair-fill-test-source/v1",
            "fixture_id": "score-free",
        },
        profile_audit_complete=True,
        source_authoritative=source_authoritative,
        test_only=test_only,
    )


def test_registry_freezes_requested_fills_equal_work_and_known_support() -> None:
    registry = retest.fill_strategy_registry_v1()
    assert tuple(row["strategy_id"] for row in registry["strategies"]) == (
        retest.FILL_STRATEGY_ORDER
    )
    by_id = {row["strategy_id"]: row for row in registry["strategies"]}
    for strategy_id in (
        "legacy-mix-v1",
        "boom-heavy-equal-work-v1",
        "all-boom-equal-work-v1",
        "qbvar-expanded-equal-work-v1",
    ):
        assert by_id[strategy_id]["nominal_solve_slot_count"] == 266
        assert (
            by_id[strategy_id]["comparison_cohort_id"]
            == retest.NATIVE_EQUAL_WORK_COHORT
        )
    assert (
        by_id["all-boom-unique-fill-v1"]["comparison_cohort_id"]
        != retest.NATIVE_EQUAL_WORK_COHORT
    )
    assert retest.fill_generation_environment_v1(
        "all-boom-unique-fill-v1"
    )["BOOM_UNIQUE_FILL"] == "1"
    boom_first = retest.fill_generation_environment_v1(
        "boom-heavy-equal-work-v1"
    )
    assert boom_first["N_LEV"] == "40"
    assert boom_first["N_BOOM"] == "160"
    assert boom_first["BOOM_UNIQUE_FILL"] == "0"
    assert retest.selector_registry_v1()["selector_count"] == 7

    controller = retest.compile_fair_fill_retest_controller_v1()
    states = {
        (row["fill_strategy_id"], row["construction_profile_id"]): row["status"]
        for row in controller["matrix"]
    }
    assert states[("per-world-exact-v1", "F7-qb-and-bringback-relaxed")] == (
        "adapter-available"
    )
    assert states[("legacy-mix-v1", "F7-qb-and-bringback-relaxed")] == (
        "generation-required"
    )
    assert states[("game-stack-control-v1", "F8-game-cap-3")] == (
        "mechanically-unsupported"
    )


def test_candidate_cells_build_a_deterministic_equal_count_heldout_fold() -> None:
    first = _cell(
        strategy_id="per-world-exact-v1",
        profile_id="F7-qb-and-bringback-relaxed",
        variants=155,
    )
    second = _cell(
        strategy_id="per-world-exact-v1",
        profile_id="F9-single-partner",
        variants=150,
        extra_heldout_variant=True,
    )
    cells = sorted((first, second), key=lambda row: row["cell_id"])
    plan = retest.build_fair_fill_fold_plan_v1(
        candidate_cells=cells,
        heldout_block="R4",
        allow_non_authoritative=True,
    )
    repeated = retest.build_fair_fill_fold_plan_v1(
        candidate_cells=cells,
        heldout_block="R4",
        allow_non_authoritative=True,
    )
    assert plan == repeated
    assert plan["common_count"] == 150
    assert plan["training_blocks"] == ["R0", "R1", "R2", "R3"]
    assert plan["score_values_read_for_sampling"] is False
    assert all(row["sampled_lineup_count"] == 150 for row in plan["cell_plans"])
    legacy = next(
        row for row in plan["cell_plans"]
        if row["construction_profile_id"] == "F9-single-partner"
    )
    heldout_only_id = retest._lineup_id("2023-w01", _roster(150))
    assert heldout_only_id not in legacy["sampled_lineup_ids"]
    controller = retest.compile_fair_fill_retest_controller_v1(
        candidate_cells=cells, allow_non_authoritative=True
    )
    assert controller["fold_compilation_count"] == 5
    assert {row["status"] for row in controller["fold_compilations"]} == {"ready"}
    assert controller["selector_fold_work_item_count"] == 5 * 2 * 7

    different_work = _cell(
        strategy_id="per-world-exact-v1",
        profile_id="F9-single-partner",
        variants=150,
        scheduled_attempts=181,
    )
    with pytest.raises(
        retest.CorpusR6FairFillRetestV1Error,
        match="attempted-work dose",
    ):
        retest.build_fair_fill_fold_plan_v1(
            candidate_cells=sorted(
                (first, different_work), key=lambda row: row["cell_id"]
            ),
            heldout_block="R4",
            allow_non_authoritative=True,
        )


def test_outcome_metadata_fails_closed_and_family_isolates_stay_diagnostic() -> None:
    with pytest.raises(
        retest.CorpusR6FairFillRetestV1Error,
        match="test source binding fields",
    ):
        retest.build_candidate_cell_from_occurrences_v1(
            slate={"season": 2023, "week": 1, "slate_id": "2023-w01"},
            fill_strategy_id="legacy-mix-v1",
            construction_profile_id="F0-incumbent",
            occurrences=[{
                "origin_id": "R0",
                "candidate_ordinal": 0,
                "roster_player_ids": _roster(0),
                "family_tags": ["lev"],
            }],
            work_receipts=[
                {
                    "schema": retest.WORK_RECEIPT_SCHEMA,
                    "origin_id": block,
                    "scheduled_optimizer_attempts": 1,
                    "attempted_optimizer_calls": 1,
                    "optimal_calls": 1,
                    "infeasible_calls": 0,
                    "error_calls": 0,
                    "retained_occurrence_count": int(block == "R0"),
                }
                for block in rw.WORLD_BLOCKS
            ],
            source_bindings={"actual_score": 225.0},
            profile_audit_complete=True,
            source_authoritative=False,
            test_only=True,
        )

    parent = _cell(
        strategy_id="legacy-mix-v1",
        profile_id="F0-incumbent",
        variants=160,
        family_tag="epi",
    )
    isolate = retest.build_tagged_family_control_cell_v1(
        parent, control_strategy_id="role-epistemic-control-v1"
    )
    assert isolate["diagnostic_only"] is True
    assert isolate["comparison_role"] == "diagnostic-filter"
    assert isolate["unique_lineup_count"] == 80
    with pytest.raises(
        retest.CorpusR6FairFillRetestV1Error,
        match="diagnostic family isolates",
    ):
        retest.build_fair_fill_fold_plan_v1(
            candidate_cells=[isolate],
            heldout_block="R4",
            allow_non_authoritative=True,
        )


def test_existing_seven_selectors_and_heldout_simulated_evaluator_execute() -> None:
    cell = _cell(
        strategy_id="per-world-exact-v1",
        profile_id="F7-qb-and-bringback-relaxed",
        variants=150,
    )
    plan = retest.build_fair_fill_fold_plan_v1(
        candidate_cells=[cell],
        heldout_block="R4",
        allow_non_authoritative=True,
    )
    cell_plan = plan["cell_plans"][0]
    candidate_rows = cell_plan["sampled_candidate_rows"]
    lineup_ids = cell_plan["sampled_lineup_ids"]
    rng = np.random.default_rng(20260828)
    training = np.ascontiguousarray(
        rng.normal(215.0, 31.0, size=(150, 32)), dtype=np.float64
    )
    selection = retest.bind_fair_fill_selection_inputs_v1(
        plan_sha256=plan["plan_sha256"],
        cell_id=cell["cell_id"],
        heldout_block="R4",
        training_blocks=("R0", "R1", "R2", "R3"),
        worlds_per_block=8,
        sampled_lineup_ids=lineup_ids,
        candidate_rows=candidate_rows,
        training_score_matrix=training,
    )
    result = retest.run_fair_fill_selectors_v1(selection)
    assert result["selector_count"] == 7
    assert result["grouped_result"]["selector_count"] == 3
    assert result["rank150_result"]["selector_count"] == 3
    assert result["heldout_matrix_or_digest_read"] is False

    heldout = np.ascontiguousarray(
        rng.normal(215.0, 31.0, size=(150, 8)), dtype=np.float64
    )
    evaluation = retest.bind_fair_fill_evaluation_inputs_v1(
        plan_sha256=plan["plan_sha256"],
        cell_id=cell["cell_id"],
        heldout_block="R4",
        worlds_per_block=8,
        sampled_lineup_ids=lineup_ids,
        rosters=[row["roster_player_ids"] for row in candidate_rows],
        heldout_score_matrix=heldout,
    )
    grade = retest.evaluate_fair_fill_selector_result_v1(
        evaluation, selector_result=result
    )
    assert grade["metric_count"] == 21
    assert grade["simulated_scores_only"] is True
    assert grade["realized_outcomes_read"] is False
    assert {row["prefix_size"] for row in grade["metrics"]} == {4, 14, 80, 100, 150}


def test_tampering_invalidates_cell_hash() -> None:
    cell = _cell(
        strategy_id="legacy-mix-v1",
        profile_id="F0-incumbent",
        variants=150,
    )
    changed = deepcopy(cell)
    changed["occurrences"][0]["family_tags"] = ["boom"]
    with pytest.raises(
        retest.CorpusR6FairFillRetestV1Error, match="self-hash"
    ):
        retest.validate_candidate_cell_v1(changed)


def test_population_profile_adapter_preserves_visit_provenance(monkeypatch) -> None:
    visits = []
    for ordinal, block in enumerate(rw.WORLD_BLOCKS):
        visits.append({
            "world": {"block": block, "index": 0},
            "lineup_identity": {"roster": _roster(ordinal)},
        })
    validated = {
        "profile": {"profile_id": "F7-qb-and-bringback-relaxed"},
        "slate": {"season": 2023, "week": 1, "slate_id": "2023-w01"},
        "visit_results": visits,
        "work": {"solve_attempts_per_block": 1},
        "lineups_sha256": "a" * 64,
        "source_authority_sha256": "b" * 64,
        "work_sha256": "c" * 64,
        "world_schedule_sha256": "d" * 64,
        "authoritative_solver_proofs_complete": True,
        "test_only": False,
    }
    monkeypatch.setattr(
        runtime,
        "validate_profile_lineups_v1",
        lambda value, *, players: validated,
    )
    cell = retest.candidate_cell_from_population_profile_lineups_v1(
        {"fixture": True}, players=()
    )
    assert cell["fill_strategy_id"] == "per-world-exact-v1"
    assert cell["construction_profile_id"] == "F7-qb-and-bringback-relaxed"
    assert [row["origin_id"] for row in cell["occurrences"]] == list(
        rw.WORLD_BLOCKS
    )
    assert cell["source_authoritative"] is False
    assert cell["test_only"] is True
    assert cell["uses_realized_outcomes"] is False


def test_generic_cells_cannot_self_assert_authority_or_override_support() -> None:
    with pytest.raises(
        retest.CorpusR6FairFillRetestV1Error,
        match="cannot self-assert source authority",
    ):
        _cell(
            strategy_id="per-world-exact-v1",
            profile_id="F7-qb-and-bringback-relaxed",
            variants=150,
            source_authoritative=True,
            test_only=False,
        )
    unsupported = _cell(
        strategy_id="boom-heavy-equal-work-v1",
        profile_id="F7-qb-and-bringback-relaxed",
        variants=150,
    )
    with pytest.raises(
        retest.CorpusR6FairFillRetestV1Error,
        match="not artifact-supported",
    ):
        retest.build_fair_fill_fold_plan_v1(
            candidate_cells=[unsupported],
            heldout_block="R4",
            allow_non_authoritative=True,
        )
    controller = retest.compile_fair_fill_retest_controller_v1(
        candidate_cells=[unsupported], allow_non_authoritative=True
    )
    row = next(
        item for item in controller["matrix"]
        if item["cell_id"] == unsupported["cell_id"]
    )
    assert row["status"] == "rejected-unsupported-source"
    assert controller["fold_compilation_count"] == 0


def test_evaluation_operator_cannot_open_heldout_before_selection_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cell = _cell(
        strategy_id="per-world-exact-v1",
        profile_id="F7-qb-and-bringback-relaxed",
        variants=150,
    )
    plan = retest.build_fair_fill_fold_plan_v1(
        candidate_cells=[cell],
        heldout_block="R4",
        allow_non_authoritative=True,
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_bytes(retest.profiles.canonical_json_bytes_v1(plan))
    script_path = (
        Path(__file__).parents[1]
        / "scripts"
        / "run_corpus_r6_fair_fill_retest_v1.py"
    )
    spec = importlib.util.spec_from_file_location("fair_fill_operator", script_path)
    assert spec is not None and spec.loader is not None
    operator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(operator)
    heldout_opened = False

    def forbidden_load(*_args, **_kwargs):
        nonlocal heldout_opened
        heldout_opened = True
        raise AssertionError("heldout opened before selection")

    monkeypatch.setattr(operator, "_load_matrix", forbidden_load)
    args = SimpleNamespace(
        evaluation_output=str(tmp_path / "evaluation.json"),
        plan=str(plan_path),
        cell_id=cell["cell_id"],
        selector_result=str(tmp_path / "missing-selection.json"),
        heldout_matrix=str(tmp_path / "heldout.npy"),
    )
    with pytest.raises(operator.OperatorError, match="cannot read"):
        operator._evaluate_command(args)
    assert heldout_opened is False


def test_incumbent_controls_report_full_and_equal_size_sensitivity() -> None:
    cell = _cell(
        strategy_id="per-world-exact-v1",
        profile_id="F7-qb-and-bringback-relaxed",
        variants=160,
    )
    rows = retest._candidate_rows_for_fit(cell, heldout_block="R4")
    full_ids = [row["lineup_id"] for row in rows]
    equal_ids = sorted(full_ids[:150])
    rng = np.random.default_rng(19)
    training = np.ascontiguousarray(
        rng.normal(215.0, 31.0, size=(160, 32)), dtype=np.float64
    )
    result = retest.run_incumbent_control_sensitivity_v1(
        cell_id=cell["cell_id"],
        full_candidate_rows=rows,
        full_training_score_matrix=training,
        equal_size_lineup_ids=equal_ids,
        training_blocks=("R0", "R1", "R2", "R3"),
        worlds_per_block=8,
    )
    assert result["result_count"] == 8
    assert {row["view_id"] for row in result["results"]} == {
        "full-corpus", "deterministic-equal-size"
    }
    assert {row["strategy_id"] for row in result["results"]} == set(
        retest.INCUMBENT_CONTROL_IDS
    )
    heldout = np.ascontiguousarray(
        rng.normal(215.0, 31.0, size=(160, 8)), dtype=np.float64
    )
    grade = retest.evaluate_incumbent_control_sensitivity_v1(
        sensitivity_result=result,
        full_lineup_ids=full_ids,
        full_heldout_score_matrix=heldout,
    )
    assert grade["metric_count"] == 8
    assert grade["realized_outcomes_read"] is False
