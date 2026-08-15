from __future__ import annotations

import copy

import numpy as np
import pandas as pd
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


def test_calibration_row_uses_six_frozen_two_sided_errors():
    score = _score()

    row = copula.calibration_grid_row(score, 0.75)

    expected = sum(abs(score["g0"]["cells"][name][
        "log_simulated_to_realized"
    ]) for name in copula.CALIBRATION_G0_CELLS)
    expected += sum(abs(score["broad_relationships"][name][
        "log_simulated_to_realized"
    ]) for name in copula.CALIBRATION_G1_CELLS)
    assert row["required_support"]
    assert row["registered_absolute_log_error_sum"] == pytest.approx(expected)


def test_calibration_row_is_ineligible_when_registered_cell_is_unsupported():
    score = _score()
    score["g0"]["cells"]["multiplicity_ge3"] = _cell(
        0.0, supported=False,
    )

    row = copula.calibration_grid_row(score, 0.5)

    assert not row["required_support"]
    assert row["support_failure"] == "registered calibration cells unsupported"


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


def _reference_fixture() -> tuple[pd.DataFrame, np.ndarray, dict]:
    frame = pd.DataFrame({
        "season": [2023, 2024, 2025],
        "week": [1, 1, 1],
        "gsis_id": ["p1", "p2", "p3"],
        "position": ["QB", "WR", "RB"],
        "team": ["A", "B", "C"],
        "opp": ["D", "E", "F"],
        "game_id": ["g1", "g2", "g3"],
        "actual": [20.0, 12.0, 8.0],
        "mean_projection": [19.0, 11.0, 9.0],
    })
    draws = np.arange(12, dtype=np.float64).reshape(3, 4)
    terminal = {
        "cache_table": copula.REFERENCE_CACHE_TABLE,
        "cache_rows": 52_307,
        "usage_law": {
            "mode": "data-fitted-dirichlet",
            "game_sim_usage": "dirichlet",
            "k": copula.REFERENCE_DIRICHLET_K,
        },
        "schedule": copy.deepcopy(copula.REFERENCE_POSITION_SCHEDULE),
        "maximum_mean_delta": 0.0,
        "parity": [],
    }
    return frame, draws, terminal


def test_fresh_reference_requires_exact_repeat_and_terminal_contract():
    frame, draws, terminal = _reference_fixture()

    result = copula.reference_invariants(
        frame, draws, terminal,
        frame.copy(), draws.copy(), copy.deepcopy(terminal),
        expected_rows=3, expected_slates=3, expected_worlds=4,
    )

    assert result["passes"]
    assert result["frame_sha256"] == result["repeat_frame_sha256"]
    assert result["draws_sha256"] == result["repeat_draws_sha256"]


def test_fresh_reference_rejects_repeat_drift_and_wrong_terminal():
    frame, draws, terminal = _reference_fixture()
    repeat_frame = frame.copy()
    repeat_frame.loc[0, "mean_projection"] += 0.01
    repeat_draws = draws.copy()
    repeat_draws[0, 0] += 1.0
    repeat_terminal = copy.deepcopy(terminal)
    repeat_terminal["cache_table"] = "wrong"

    result = copula.reference_invariants(
        frame, draws, repeat_terminal,
        repeat_frame, repeat_draws, repeat_terminal,
        expected_rows=3, expected_slates=3, expected_worlds=4,
    )

    assert not result["passes"]
    assert not result["frame_bit_exact_on_repeat"]
    assert not result["draws_bit_exact_on_repeat"]
    assert not result["terminal_contract_exact"]
