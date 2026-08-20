from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research import a2a_rank_factor_split as a2a


def _catalog() -> pd.DataFrame:
    return pd.DataFrame([
        {"season": 2025, "week": 1, "player_id": "a_qb", "position": "QB", "team": "A", "mean_projection": 20.0},
        {"season": 2025, "week": 1, "player_id": "a_rb", "position": "RB", "team": "A", "mean_projection": 14.0},
        {"season": 2025, "week": 1, "player_id": "a_te", "position": "TE", "team": "A", "mean_projection": 8.0},
        {"season": 2025, "week": 1, "player_id": "a_wr1", "position": "WR", "team": "A", "mean_projection": 12.0},
        {"season": 2025, "week": 1, "player_id": "a_wr2", "position": "WR", "team": "A", "mean_projection": 10.0},
        {"season": 2025, "week": 1, "player_id": "b_qb", "position": "QB", "team": "B", "mean_projection": 18.0},
        {"season": 2025, "week": 1, "player_id": "b_wr1", "position": "WR", "team": "B", "mean_projection": 9.0},
        {"season": 2025, "week": 1, "player_id": "c_dst", "position": "DST", "team": "C", "mean_projection": 7.0},
        {"season": 2025, "week": 1, "player_id": "d_wr1", "position": "WR", "team": "D", "mean_projection": 3.9},
    ])


def _artifact() -> tuple[list[str], np.ndarray]:
    ids = [
        "extra", "a_wr2", "a_qb", "b_wr1", "a_rb", "c_dst",
        "a_wr1", "d_wr1", "a_te", "b_qb",
    ]
    orders = {
        "extra": [7, 6, 5, 4, 3, 2, 1, 0],
        "a_wr2": [3, 0, 7, 2, 6, 1, 5, 4],
        "a_qb": [0, 7, 1, 6, 2, 5, 3, 4],
        "b_wr1": [2, 1, 0, 3, 4, 5, 7, 6],
        "a_rb": [7, 0, 6, 1, 5, 2, 4, 3],
        "c_dst": [4, 5, 6, 7, 0, 1, 2, 3],
        "a_wr1": [0, 2, 4, 6, 7, 5, 3, 1],
        "d_wr1": [1, 3, 5, 7, 6, 4, 2, 0],
        "a_te": [4, 0, 5, 1, 6, 2, 7, 3],
        "b_qb": [6, 4, 2, 0, 1, 3, 5, 7],
    }
    return ids, np.asarray([orders[player] for player in ids], dtype=np.float32)


def test_stable_open_ranks_and_competitive_ties_are_canonical():
    ranks = a2a.stable_open_unit_ranks(np.array([2.0, 1.0, 1.0, 3.0]))
    assert ranks.tolist() == [0.625, 0.125, 0.375, 0.875]
    constant = a2a.stable_open_unit_ranks(np.ones(4))
    assert constant.tolist() == [0.125, 0.375, 0.625, 0.875]
    selected = a2a.competitive_wr_assignment(np.array([
        [0.2, 0.8, 0.5], [0.2, 0.7, 0.5],
    ]))
    assert selected.tolist() == [0, 0, 0]


def test_transform_is_deterministic_exact_marginal_and_strictly_scoped():
    ids, control = _artifact()
    treatment, report = a2a.transform_and_measure_slate(
        _catalog(), ids, control, expected_worlds=8,
    )
    repeated, repeated_report = a2a.transform_and_measure_slate(
        _catalog(), ids, control, expected_worlds=8,
    )
    assert treatment.tobytes() == repeated.tobytes()
    assert report == repeated_report
    assert treatment.dtype == control.dtype
    assert all(
        np.array_equal(np.sort(before), np.sort(after))
        for before, after in zip(control, treatment, strict=True)
    )
    index = {player: offset for offset, player in enumerate(ids)}
    for player in ("extra", "a_qb", "b_qb", "b_wr1", "c_dst", "d_wr1"):
        assert control[index[player]].tobytes() == treatment[index[player]].tobytes()
    mechanics = report["mechanics"]
    assert mechanics["eligible_groups"] == 1
    assert mechanics["transformed_rows"] == 4
    assert mechanics["one_hot_assignments"] == 8
    assert mechanics["eligible_group_worlds"] == 8
    assert mechanics["changed_world_cells"] > 0
    assert mechanics["passes"] is True
    assert mechanics["exact_sorted_marginals"] is True
    assert mechanics["exact_q90_boom_counts"] is True
    assert mechanics["qb_bit_exact"] is True
    assert mechanics["ineligible_or_unsupported_bit_exact"] is True
    assert report["control"]["qb_wr"]["directed_pairs"] == 3
    assert report["control"]["wr_wr"]["directed_pairs"] == 2


def test_constant_rows_preserve_bits_and_make_local_transform_vacuous():
    frame = _catalog().iloc[:5].reset_index(drop=True)
    ids = frame.player_id.tolist()
    control = np.ones((len(ids), 6), dtype=np.float64)
    treatment, report = a2a.transform_and_measure_slate(
        frame, ids, control, expected_worlds=6,
    )
    assert treatment.tobytes() == control.tobytes()
    assert report["mechanics"]["exact_sorted_marginals"] is True
    assert report["mechanics"]["one_hot_exact"] is True
    assert report["mechanics"]["nonvacuous"] is False
    assert report["mechanics"]["passes"] is False


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("nonfinite", "nonfinite"),
        ("misaligned", "misaligned"),
        ("duplicate_artifact", "identities"),
        ("missing", "missing"),
        ("duplicate_catalog", "repeats"),
        ("noncanonical", "noncanonical"),
        ("forbidden", "forbidden"),
    ],
)
def test_invalid_sources_fail_closed(mutation: str, message: str):
    frame = _catalog()
    ids, draws = _artifact()
    if mutation == "nonfinite":
        draws[0, 0] = np.nan
    elif mutation == "misaligned":
        draws = draws[:-1]
    elif mutation == "duplicate_artifact":
        ids[-1] = ids[0]
    elif mutation == "missing":
        ids[ids.index("a_qb")] = "not_a_qb"
    elif mutation == "duplicate_catalog":
        frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    elif mutation == "noncanonical":
        frame = frame.iloc[::-1].reset_index(drop=True)
    elif mutation == "forbidden":
        frame["actual_score"] = 0.0
    with pytest.raises(ValueError, match=message):
        a2a.transform_and_measure_slate(frame, ids, draws, expected_worlds=8)


def test_multiple_qb_group_is_unsupported_and_bit_exact():
    frame = _catalog()
    frame.loc[frame.player_id.eq("a_rb"), "position"] = "QB"
    ids, control = _artifact()
    treatment, report = a2a.transform_and_measure_slate(
        frame, ids, control, expected_worlds=8,
    )
    index = {player: offset for offset, player in enumerate(ids)}
    for player in ("a_qb", "a_rb", "a_te", "a_wr1", "a_wr2"):
        row = index[player]
        assert treatment[row].tobytes() == control[row].tobytes()
    assert report["mechanics"]["eligible_groups"] == 0
    assert report["mechanics"]["transformed_rows"] == 0
    assert report["mechanics"]["ineligible_or_unsupported_bit_exact"] is True
    assert report["mechanics"]["nonvacuous"] is False
    assert report["mechanics"]["passes"] is False


def test_exact_lift_comparison_handles_equal_greater_less_and_zero_denominator():
    control = {"both": 2, "conditioned": 4, "other_only": 3, "not_conditioned": 6}
    equal = {"both": 5, "conditioned": 10, "other_only": 7, "not_conditioned": 14}
    greater = {"both": 6, "conditioned": 10, "other_only": 7, "not_conditioned": 14}
    less = {"both": 4, "conditioned": 10, "other_only": 7, "not_conditioned": 14}
    assert a2a.compare_conditional_lifts(control, equal) == 0
    assert a2a.compare_conditional_lifts(control, greater) == 1
    assert a2a.compare_conditional_lifts(control, less) == -1
    broken = dict(equal, other_only=0)
    with pytest.raises(ValueError, match="zero denominator"):
        a2a.compare_conditional_lifts(control, broken)


def test_combine_reports_sums_exact_integers_and_rejects_duplicate_slates():
    ids, control = _artifact()
    _draws, first = a2a.transform_and_measure_slate(
        _catalog(), ids, control, expected_worlds=8,
    )
    second_catalog = _catalog().copy()
    second_catalog["week"] = 2
    _draws, second = a2a.transform_and_measure_slate(
        second_catalog, ids, control, expected_worlds=8,
    )
    combined = a2a.combine_reports([second, first])
    assert combined["scope"] == "block"
    assert combined["slate_keys"] == [[2025, 1], [2025, 2]]
    assert combined["control"]["qb_wr"]["both"] == 2 * first["control"]["qb_wr"]["both"]
    assert combined["mechanics"]["one_hot_assignments"] == 16
    with pytest.raises(ValueError, match="repeats a slate"):
        a2a.combine_reports([first, deepcopy(first)])


def _conditional(*, better: bool = False, worse: bool = False) -> dict[str, int]:
    both = 20 if better else 5 if worse else 10
    return {
        "directed_pairs": 10, "both": both, "conditioned": 20,
        "other_only": 10, "not_conditioned": 20, "pair_worlds": 100_000,
    }


def _gate_block() -> dict:
    control = {
        "multiplicity_ge2": {"groups": 10, "events": 100, "group_worlds": 100_000},
        "multiplicity_ge3": {"groups": 10, "events": 100, "group_worlds": 100_000},
        "multiplicity_ge4": {"groups": 10, "events": 100, "group_worlds": 100_000},
        **{cell: _conditional() for cell in a2a.CONDITIONAL_CELLS},
    }
    treatment = deepcopy(control)
    treatment["multiplicity_ge2"]["events"] = 95
    treatment["multiplicity_ge3"]["events"] = 90
    treatment["multiplicity_ge4"]["events"] = 95
    treatment["qb_wr"] = _conditional(better=True)
    mechanics = {
        "eligible_rows": 100, "eligible_groups": 10, "transformed_rows": 40,
        "eligible_group_worlds": 100_000, "one_hot_assignments": 100_000,
        "changed_rows": 40, "changed_world_cells": 1_000,
        "row_world_cells": 1_000_000, "q90_rows_checked": 100,
        "qb_rows_checked": 10, "unchanged_rows_checked": 60,
        "source_alignment_exact": True, "finite_output": True,
        "deterministic_repeat_exact": True, "exact_sorted_marginals": True,
        "exact_q90_boom_counts": True, "qb_bit_exact": True,
        "ineligible_or_unsupported_bit_exact": True,
        "row_world_budget_unchanged": True, "one_hot_exact": True,
        "nonvacuous": True, "passes": True,
        "generic_attenuation": 0.5, "qb_wr_allocation": 1.0,
    }
    return {
        "version": a2a.VERSION, "scope": "block", "slates": 54,
        "slate_keys": [[season, week] for season, week in a2a.EXPECTED_SLATE_KEYS],
        "worlds": 10_000, "artifact_rows": 500, "catalog_rows": 400,
        "mechanics": mechanics, "control": control, "treatment": treatment,
    }


def _gate_blocks() -> dict[str, dict]:
    return {name: _gate_block() for name in a2a.REGISTERED_BLOCKS}


def test_gate_truth_table_and_license_firewall():
    passing = a2a.evaluate_mechanism_gate(_gate_blocks())
    assert passing["passes"] is True
    assert passing["mechanical_invariants_pass"] is True
    assert passing["directional_conditions_pass"] is True
    assert passing["disposition"] == "a2a-scorefree-mechanism-passes"
    assert passing["licenses"] == {
        "uses_realized_outcomes": False,
        "actual_outcomes_queried": False,
        "candidate_or_lineup_scores_read": False,
        "historical_remeasurement_licensed": True,
        "exact80_scoring_licensed": False,
        "single_stack_arm_licensed": False,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
    }

    only_two = _gate_blocks()
    for name in ("R2", "R3", "R4"):
        only_two[name]["treatment"]["qb_wr"] = _conditional()
    failed = a2a.evaluate_mechanism_gate(only_two)
    assert failed["passes"] is False
    assert failed["mechanical_invariants_pass"] is True
    assert failed["directional_conditions_pass"] is False
    assert failed["disposition"] == "a2a-scorefree-mechanism-fails"
    assert failed["licenses"]["historical_remeasurement_licensed"] is False

    invalid = _gate_blocks()
    invalid["R0"]["mechanics"]["passes"] = False
    invalid_result = a2a.evaluate_mechanism_gate(invalid)
    assert invalid_result["disposition"] == "a2a-scorefree-invalid"
    assert invalid_result["mechanical_invariants_pass"] is False


def test_gate_protected_cells_cannot_increase_and_requires_exact_blocks():
    blocks = _gate_blocks()
    blocks["R0"]["treatment"]["wr_wr"] = _conditional(better=True)
    result = a2a.evaluate_mechanism_gate(blocks)
    assert result["passes"] is False
    assert result["conditions"]["aggregate_wr_wr_no_greater"] is False
    incomplete = _gate_blocks()
    incomplete.pop("R4")
    with pytest.raises(ValueError, match="R0--R4"):
        a2a.evaluate_mechanism_gate(incomplete)
