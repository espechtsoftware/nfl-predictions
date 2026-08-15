from __future__ import annotations

import copy

import pytest

from nfl_dfs.analysis import sis_receiver_copula as copula


def _cell(error: float, *, supported: bool = True) -> dict:
    return {
        "supported": supported,
        "log_simulated_to_realized": error if supported else None,
        "realized_estimate": 1.0,
        "simulated_estimate": 1.0,
        "support": {"events": 100},
    }


def _score() -> dict:
    g0_cells = {
        "qb_wr": _cell(0.30),
        "qb_te": _cell(0.10),
        "qb_rb": _cell(0.20),
        "wr_wr": _cell(0.25),
        "rb_rb": _cell(0.15),
        "multiplicity_ge2": _cell(0.18),
        "multiplicity_ge3": _cell(0.28),
        "multiplicity_ge4": _cell(0.40, supported=False),
    }
    broad = {
        "QB_WR": _cell(0.30),
        "QB_TE": _cell(0.10),
        "QB_RB": _cell(0.20),
        "WR_WR": _cell(0.25),
        "RB_RB": _cell(0.15),
    }
    scorecard = {
        name: {
            "joint_q90_brier": 0.02,
            "variogram_p0_5": 1.0,
            "pairs": 100,
        }
        for name in broad
    }
    return {
        "primary": {
            "joint_q90_brier": 0.020,
            "variogram_p0_5": 1.40,
            "g0_absolute_log_error_sum": 1.76,
            "g1_weighted_absolute_log_error_sum": 5.0,
        },
        "scorecard": scorecard,
        "broad_relationships": broad,
        "g0": {"cells": g0_cells},
    }


def _passing_treatment(control: dict) -> dict:
    treatment = copy.deepcopy(control)
    treatment["primary"].update({
        "joint_q90_brier": 0.019,
        "variogram_p0_5": 1.39,
        "g0_absolute_log_error_sum": 1.66,
        "g1_weighted_absolute_log_error_sum": 4.9,
    })
    treatment["g0"]["cells"]["qb_wr"]["log_simulated_to_realized"] = 0.20
    treatment["broad_relationships"]["QB_WR"][
        "log_simulated_to_realized"
    ] = 0.20
    return treatment


def _decision(control: dict, treatment: dict, **kwargs) -> dict:
    arguments = {
        "invariants_pass": True,
        "selected_strength": 0.75,
        "treatment_audit": {"changed_rows": 20},
    }
    arguments.update(kwargs)
    return copula.gate_decision(control, treatment, **arguments)


def test_calibration_selection_uses_frozen_lexicographic_order():
    grid = [
        {
            "strength": strength,
            "required_support": True,
            "registered_absolute_log_error_sum": 2.0,
            "joint_q90_brier": 0.02,
            "variogram_p0_5": 1.0,
        }
        for strength in copula.STRENGTH_GRID
    ]
    grid[3]["registered_absolute_log_error_sum"] = 1.0
    grid[4]["registered_absolute_log_error_sum"] = 1.0
    grid[3]["joint_q90_brier"] = 0.01
    grid[4]["joint_q90_brier"] = 0.01
    grid[3]["variogram_p0_5"] = 0.9
    grid[4]["variogram_p0_5"] = 0.9

    assert copula.select_calibration_grid(grid)["strength"] == 0.75


def test_calibration_selection_rejects_changed_grid():
    with pytest.raises(ValueError, match="grid differs"):
        copula.select_calibration_grid([])


def test_gate_passes_complete_two_sided_improvement_only_for_shadow():
    control = _score()

    result = _decision(control, _passing_treatment(control))

    assert result["disposition"] == "sis-receiver-copula-gate-passes"
    assert result["prospective_2026_shadow_licensed"]
    assert not result["retrospective_exact80_licensed"]
    assert result["multiplicity"]["multiplicity_ge4"]["mandatory_report"]
    assert not result["multiplicity"]["multiplicity_ge4"]["gated"]


def test_gate_rejects_any_supported_cell_regression():
    control = _score()
    treatment = _passing_treatment(control)
    treatment["g0"]["cells"]["qb_rb"]["log_simulated_to_realized"] = 0.21

    result = _decision(control, treatment)

    assert result["disposition"] == "sis-receiver-copula-gate-fails"
    assert not result["gate"]["all_supported_g0_cells_do_not_worsen"]


def test_gate_rejects_changed_qb_te_negative_control():
    control = _score()
    treatment = _passing_treatment(control)
    treatment["scorecard"]["QB_TE"]["joint_q90_brier"] += 1e-9

    result = _decision(control, treatment)

    assert result["disposition"] == "sis-receiver-copula-gate-fails"
    assert not result["gate"]["qb_te_and_rb_rb_remain_unchanged"]


def test_gate_is_inconclusive_without_required_multiplicity_support():
    control = _score()
    treatment = _passing_treatment(control)
    control["g0"]["cells"]["multiplicity_ge3"] = _cell(
        0.0, supported=False,
    )
    treatment["g0"]["cells"]["multiplicity_ge3"] = copy.deepcopy(
        control["g0"]["cells"]["multiplicity_ge3"]
    )

    result = _decision(control, treatment)

    assert result["disposition"] == "sis-receiver-copula-invalid-or-inconclusive"
    assert not result["gate"]["required_cells_supported"]


def test_gate_rejects_inert_calibration_choice_or_treatment():
    control = _score()
    treatment = _passing_treatment(control)

    zero = _decision(control, treatment, selected_strength=0.0)
    inert = _decision(
        control, treatment, treatment_audit={"changed_rows": 0},
    )

    assert zero["disposition"] == "sis-receiver-copula-gate-fails"
    assert inert["disposition"] == "sis-receiver-copula-gate-fails"
