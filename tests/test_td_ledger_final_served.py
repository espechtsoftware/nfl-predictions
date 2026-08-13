import copy
from math import log

import pandas as pd

from nfl_dfs.analysis import td_ledger_final_served as ledger


def _score():
    relationships = {
        "QB_WR": 1.0,
        "QB_TE": 0.4,
        "WR_WR": 0.2,
        "RB_RB": 0.3,
    }
    return {
        "primary": {
            "joint_q90_brier": 0.02,
            "variogram_p0_5": 1.4,
            "g0_absolute_log_error_sum": 3.0,
            "g1_weighted_absolute_log_error_sum": 6.0,
            "g1_relationship_errors": {
                key: {"absolute_log_error": value}
                for key, value in relationships.items()
            },
            "g0_cell_errors": {
                "multiplicity_ge2": 0.15,
                "multiplicity_ge3": 0.30,
            },
        },
    }


def test_gate_passes_only_complete_registered_improvement():
    control = _score()
    treatment = copy.deepcopy(control)
    primary = treatment["primary"]
    primary["joint_q90_brier"] -= 0.001
    primary["variogram_p0_5"] -= 0.01
    primary["g0_absolute_log_error_sum"] -= 0.1
    primary["g1_weighted_absolute_log_error_sum"] -= 0.1
    primary["g1_relationship_errors"]["QB_WR"]["absolute_log_error"] -= 0.1

    result = ledger.gate_decision(
        control, treatment, invariants_pass=True, changed_rows=10)

    assert result["disposition"] == "td-ledger-dependence-gate-passes"
    assert result["exact80_licensed"]
    assert result["gate"]["passes"]


def test_gate_rejects_wr_wr_regression_even_when_aggregates_improve():
    control = _score()
    treatment = copy.deepcopy(control)
    primary = treatment["primary"]
    primary["joint_q90_brier"] -= 0.001
    primary["variogram_p0_5"] -= 0.01
    primary["g0_absolute_log_error_sum"] -= 0.1
    primary["g1_weighted_absolute_log_error_sum"] -= 0.1
    primary["g1_relationship_errors"]["QB_WR"]["absolute_log_error"] -= 0.1
    primary["g1_relationship_errors"]["WR_WR"]["absolute_log_error"] += 1e-6

    result = ledger.gate_decision(
        control, treatment, invariants_pass=True, changed_rows=10)

    assert result["disposition"] == "td-ledger-dependence-gate-fails"
    assert not result["gate"]["wr_wr_absolute_log_error_not_worse"]


def test_gate_allows_only_registered_five_percent_guard_regression():
    control = _score()
    treatment = copy.deepcopy(control)
    primary = treatment["primary"]
    primary["joint_q90_brier"] -= 0.001
    primary["variogram_p0_5"] -= 0.01
    primary["g0_absolute_log_error_sum"] -= 0.1
    primary["g1_weighted_absolute_log_error_sum"] -= 0.1
    primary["g1_relationship_errors"]["QB_WR"]["absolute_log_error"] -= 0.1
    primary["g1_relationship_errors"]["QB_TE"]["absolute_log_error"] += log(1.05)

    at_boundary = ledger.gate_decision(
        control, treatment, invariants_pass=True, changed_rows=10)
    assert at_boundary["gate"]["named_material_regression_guards_pass"]

    primary["g1_relationship_errors"]["QB_TE"]["absolute_log_error"] += 1e-9
    beyond = ledger.gate_decision(
        control, treatment, invariants_pass=True, changed_rows=10)
    assert not beyond["gate"]["named_material_regression_guards_pass"]


def test_invalid_invariants_cannot_license_exact80():
    result = ledger.gate_decision(
        _score(), _score(), invariants_pass=False, changed_rows=0)
    assert result["disposition"] == "td-ledger-invalid-or-inconclusive"
    assert not result["exact80_licensed"]


def test_frame_alignment_leaves_mean_drift_to_registered_tolerance():
    control = pd.DataFrame({
        "season": [2025], "week": [1], "gsis_id": ["00-1"],
        "position": ["WR"], "team": ["KC"], "opp": ["LAC"],
        "game_id": ["2025_01_LAC_KC"], "actual": [20.0],
        "mean_projection": [14.0],
    })
    treatment = control.copy()
    treatment.loc[0, "mean_projection"] += 1e-12

    assert ledger._frame_alignment_failures(control, treatment) == []

    treatment.loc[0, "actual"] += 1e-12
    assert ledger._frame_alignment_failures(control, treatment) == ["frame:actual"]
