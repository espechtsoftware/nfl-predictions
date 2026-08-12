import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import served_tail_calibration as diagnostic


def test_cluster_standard_error_is_positive_for_clustered_values():
    values = np.array([0.0, 0.0, 1.0, 1.0])
    season = np.array([2025, 2025, 2025, 2025])
    week = np.array([1, 1, 2, 2])
    assert diagnostic._cluster_standard_error(
        values, season, week) == pytest.approx(0.5)


def test_score_and_summary_report_all_frozen_distribution_metrics(monkeypatch):
    monkeypatch.setattr(diagnostic, "N_SIMS", 4)
    frame = pd.DataFrame({
        "season": [2025, 2025],
        "week": [1, 2],
        "gsis_id": ["a", "b"],
        "position": ["RB", "WR"],
        "market_covered": [True, False],
        "tabpfn_covered": [True, True],
        "actual": [30.0, 5.0],
    })
    draws = np.array([
        [10.0, 20.0, 25.0, 28.0],
        [0.0, 4.0, 6.0, 10.0],
    ])
    scored = diagnostic._score_draws(frame, draws)
    report = diagnostic._summarize(scored, "test")
    assert report["rows"] == 2
    assert report["events_30"] == 1
    assert report["market_coverage"] == 0.5
    assert report["q99_exceedance"] == 0.5
    assert report["q99_pinball"] >= 0
    assert report["q99_cluster_se"] >= 0
    assert report["crps"] >= 0


def test_served_tail_gate_requires_all_high_and_q99_cluster_bound():
    report = {
        "q90_exceedance": 0.11,
        "q95_exceedance": 0.07,
        "q99_exceedance": 0.025,
        "q99_cluster_ci95_low": 0.015,
    }
    assert diagnostic.served_tail_gate(report)["passes"]
    report["q99_cluster_ci95_low"] = 0.009
    assert not diagnostic.served_tail_gate(report)["passes"]
    report["q99_cluster_ci95_low"] = 0.015
    report["q95_exceedance"] = 0.049
    assert not diagnostic.served_tail_gate(report)["passes"]


def test_environment_rejects_inherited_arm(monkeypatch):
    monkeypatch.setenv("N_ROUTE_TAIL", "12")
    with pytest.raises(ValueError, match="active levers"):
        diagnostic._validate_environment()


def test_production_environment_restores_process(monkeypatch):
    monkeypatch.setenv("SHAPE_MIX", "0.25")
    monkeypatch.delenv("EXTRA_FEATURES", raising=False)
    with diagnostic._production_environment():
        assert diagnostic.os.environ["SHAPE_MIX"] == "1"
        assert diagnostic.os.environ["EXTRA_FEATURES"] == ""
        assert diagnostic.os.environ["TABPFN_MARGINAL_TABLE"] == ""
    assert diagnostic.os.environ["SHAPE_MIX"] == "0.25"
    assert "EXTRA_FEATURES" not in diagnostic.os.environ


def test_align_evaluation_enforces_accepted_means_and_active_rows(monkeypatch):
    monkeypatch.setattr(diagnostic, "EXPECTED_FOLD_ROWS", {2025: 1})
    projected = pd.DataFrame([
        {
            "season": 2025, "week": 5, "gsis_id": "a", "position": "RB",
            "actual": 12.0, "was_active": True, "model_points_pre": 10.0,
            "proj_points": 11.0, "market_points": 12.0,
        },
        {
            "season": 2025, "week": 5, "gsis_id": "b", "position": "WR",
            "actual": 0.0, "was_active": False, "model_points_pre": 8.0,
            "proj_points": 8.0, "market_points": np.nan,
        },
    ])
    accepted = pd.DataFrame([
        {
            "season": 2025, "week": 5, "gsis_id": "a", "pos": "RB",
            "actual": 12.0, "model_points_pre": 10.0,
            "mean_projection": 11.0,
        },
        {
            "season": 2025, "week": 5, "gsis_id": "b", "pos": "WR",
            "actual": 0.0, "model_points_pre": 8.0,
            "mean_projection": 8.0,
        },
    ])
    tabpfn = pd.DataFrame([{"season": 2025, "week": 5, "gsis_id": "a"}])
    draws = np.arange(8, dtype=float).reshape(2, 4)
    frame, aligned, parity = diagnostic._align_evaluation(
        projected, draws, accepted, tabpfn, 2025)
    assert frame.gsis_id.tolist() == ["a"]
    assert frame.market_covered.tolist() == [True]
    assert frame.tabpfn_covered.tolist() == [True]
    assert aligned.tolist() == [draws[0].tolist()]
    assert parity["rows"] == 1
