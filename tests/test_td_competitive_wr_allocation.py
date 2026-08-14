from __future__ import annotations

import base64
import copy
from hashlib import sha256
import json

import numpy as np
import pandas as pd

from nfl_dfs.analysis import td_competitive_wr_allocation as allocation


def test_stable_percentile_ranks_use_world_index_for_ties():
    ranks = allocation.stable_percentile_ranks(
        np.asarray([4.0, 1.0, 1.0, 9.0]),
    )
    assert ranks.tolist() == [2 / 3, 0.0, 1 / 3, 1.0]


def test_competitive_allocation_changes_only_eligible_wrs_and_keeps_marginals():
    frame = pd.DataFrame({
        "season": [2025] * 5,
        "week": [1] * 5,
        "game_id": ["2025_01_A_B"] * 5,
        "team": ["A"] * 5,
        "gsis_id": ["qb", "wr-a", "wr-b", "rb", "wr-low"],
        "position": ["QB", "WR", "WR", "RB", "WR"],
        "mean_projection": [20.0, 14.0, 12.0, 11.0, 3.0],
    })
    control = np.asarray([
        [4, 1, 6, 2, 5, 3],
        [60, 10, 50, 20, 40, 30],
        [15, 65, 25, 55, 35, 45],
        [11, 12, 13, 14, 15, 16],
        [21, 22, 23, 24, 25, 26],
    ], dtype=float)
    source = np.asarray([
        [0, 1, 2, 3, 4, 5],
        [6, 1, 5, 2, 4, 3],
        [1, 6, 2, 5, 3, 4],
        [0, 1, 2, 3, 4, 5],
        [5, 4, 3, 2, 1, 0],
    ], dtype=float)

    treatment, audit, eligible = allocation.apply_competitive_wr_allocation(
        control, source, frame,
    )

    assert audit["eligible_groups"] == 1
    assert audit["eligible_wr_rows"] == 2
    assert eligible.tolist() == [False, True, True, False, False]
    assert np.array_equal(treatment[~eligible], control[~eligible])
    assert not np.array_equal(treatment[1], control[1])
    assert not np.array_equal(treatment[2], control[2])
    assert np.array_equal(np.sort(treatment, axis=1), np.sort(control, axis=1))


def test_competitive_allocation_leaves_ambiguous_qb_group_untouched():
    frame = pd.DataFrame({
        "season": [2025] * 4,
        "week": [1] * 4,
        "game_id": ["g"] * 4,
        "team": ["A"] * 4,
        "gsis_id": ["qb-a", "qb-b", "wr-a", "wr-b"],
        "position": ["QB", "QB", "WR", "WR"],
        "mean_projection": [20.0, 10.0, 14.0, 12.0],
    })
    draws = np.arange(24, dtype=float).reshape(4, 6)

    treatment, audit, eligible = allocation.apply_competitive_wr_allocation(
        draws, draws[:, ::-1], frame,
    )

    assert audit["eligible_groups"] == 0
    assert not eligible.any()
    assert np.array_equal(treatment, draws)


def _score() -> dict:
    g1_errors = {
        "QB_WR": {"absolute_log_error": 0.30},
        "WR_WR": {"absolute_log_error": 0.30},
        "QB_TE": {"absolute_log_error": 0.10},
        "QB_RB": {"absolute_log_error": 0.80},
        "RB_RB": {"absolute_log_error": 0.90},
    }
    g0_errors = {
        "qb_wr": 0.30,
        "wr_wr": 0.30,
        "multiplicity_ge3": 0.25,
        "multiplicity_ge2": 0.05,
        "qb_te": 0.10,
        "qb_rb": 0.80,
        "rb_rb": 0.90,
    }
    unchanged_scorecards = {
        key: {"joint_q90_brier": 0.01, "variogram_p0_5": 1.0, "pairs": 10}
        for key in allocation.UNCHANGED_G1_RELATIONSHIPS
    }
    unchanged_broad = {
        key: {"simulated_lift": 1.2, "realized_lift": 1.0, "supported": True}
        for key in allocation.UNCHANGED_G1_RELATIONSHIPS
    }
    g0_cells = {
        key: {"simulated_estimate": 1.2, "realized_estimate": 1.0,
              "supported": True}
        for key in allocation.UNCHANGED_G0_CELLS
    }
    return {
        "primary": {
            "joint_q90_brier": 0.020,
            "variogram_p0_5": 1.40,
            "g0_absolute_log_error_sum": 3.0,
            "g1_weighted_absolute_log_error_sum": 5.0,
            "g1_relationship_errors": g1_errors,
            "g0_cell_errors": g0_errors,
        },
        "scorecard": unchanged_scorecards,
        "broad_relationships": unchanged_broad,
        "g0": {"cells": g0_cells},
    }


def _passing_treatment(control: dict) -> dict:
    treatment = copy.deepcopy(control)
    primary = treatment["primary"]
    primary["joint_q90_brier"] -= 0.001
    primary["variogram_p0_5"] -= 0.01
    primary["g0_absolute_log_error_sum"] -= 0.1
    primary["g1_weighted_absolute_log_error_sum"] -= 0.1
    for key in ("QB_WR", "WR_WR"):
        primary["g1_relationship_errors"][key]["absolute_log_error"] -= 0.02
    for key in ("qb_wr", "wr_wr", "multiplicity_ge3"):
        primary["g0_cell_errors"][key] -= 0.02
    return treatment


def test_gate_passes_only_complete_shape_improvement():
    control = _score()
    result = allocation.gate_decision(
        control, _passing_treatment(control),
        invariants_pass=True, changed_rows=20,
    )
    assert result["disposition"] == "td-competitive-wr-allocation-gate-passes"
    assert result["exact80_licensed"]
    assert result["gate"]["passes"]


def test_gate_rejects_changed_non_wr_negative_control():
    control = _score()
    treatment = _passing_treatment(control)
    treatment["scorecard"]["QB_RB"]["joint_q90_brier"] += 1e-9

    result = allocation.gate_decision(
        control, treatment, invariants_pass=True, changed_rows=20,
    )

    assert result["disposition"] == "td-competitive-wr-allocation-gate-fails"
    assert not result["gate"]["unchanged_qb_rb_te_negative_controls_pass"]


def test_nested_reference_comparison_enforces_structure_and_tolerance():
    expected = {"a": 1.0, "b": [2, "x"]}
    assert allocation.nested_reproduction_failures(
        {"a": 1.0 + 1e-13, "b": [2, "x"]}, expected,
    ) == []
    assert allocation.nested_reproduction_failures(
        {"a": 1.0 + 1e-8, "b": [2, "x"]}, expected,
    )
    assert allocation.nested_reproduction_failures(
        {"a": 1.0, "b": [2, "x"], "c": 3}, expected,
    ) == ["root:keys"]


def test_multiplicity_ge4_is_reported_but_not_gated():
    cell = {
        "supported": False,
        "realized_estimate": 2.0,
        "simulated_estimate": 6.0,
        "support": {
            "realized_events": 7,
            "poisson_binomial_expected_events": 3.0,
        },
    }
    control = {"g0": {"cells": {"multiplicity_ge4": cell}}}
    treatment = copy.deepcopy(control)
    treatment["g0"]["cells"]["multiplicity_ge4"]["simulated_estimate"] = 4.0

    diagnostic = allocation.multiplicity_ge4_diagnostic(control, treatment)

    assert diagnostic["mandatory_report"]
    assert not diagnostic["gated"]
    assert not diagnostic["supported"]
    assert diagnostic["realized_events"] == 7
    assert diagnostic["movement"] == "toward-realized"


def test_reference_attestation_binds_run_code_report_and_score(monkeypatch):
    run_id = "20260814-td-competitive-wr-v1"
    code_sha = "a" * 40
    report_sha = "b" * 64
    attestation = {
        "version": "td-competitive-wr-reference-v1",
        "panel": "panel-1",
        "disposition": "td-competitive-wr-reference-passes",
        "treatment_licensed": True,
        "run_identity": {"run_id": run_id, "code_sha": code_sha},
        "report_sha256": report_sha,
        "score_sha256": "c" * 64,
    }
    content = json.dumps(
        attestation, sort_keys=True, separators=(",", ":"),
    ).encode()
    monkeypatch.setenv(
        "TD_COMP_WR_REFERENCE_ATTESTATION_B64",
        base64.b64encode(content).decode(),
    )
    monkeypatch.setenv(
        "TD_COMP_WR_REFERENCE_ATTESTATION_SHA256", sha256(content).hexdigest(),
    )
    monkeypatch.setenv("TD_COMP_WR_REFERENCE_RUN_ID", run_id)
    monkeypatch.setenv("TD_COMP_WR_REFERENCE_CODE_SHA", code_sha)
    monkeypatch.setenv("TD_COMP_WR_REFERENCE_REPORT_SHA256", report_sha)

    assert allocation._load_reference_attestation("panel-1") == attestation

    monkeypatch.setenv("TD_COMP_WR_REFERENCE_REPORT_SHA256", "d" * 64)
    with np.testing.assert_raises_regex(ValueError, "attestation differs"):
        allocation._load_reference_attestation("panel-1")
