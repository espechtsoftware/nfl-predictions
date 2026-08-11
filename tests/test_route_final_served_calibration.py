import numpy as np
import pandas as pd

from nfl_dfs.analysis import route_final_served_calibration as diagnostic


def _fold(season: int, n_sims: int = 101):
    positions = list(diagnostic.POSITIONS)
    frame = pd.DataFrame({
        "season": season,
        "week": 1,
        "gsis_id": [f"{season}-{position}" for position in positions],
        "position": positions,
        "actual": 15.0,
        "market_covered": True,
        "tabpfn_covered": True,
    })
    draws = np.tile(np.linspace(0.0, 10.0, n_sims), (len(frame), 1))
    return frame, draws


def test_position_fit_moves_to_frozen_upper_bound_for_high_outcomes():
    fit = diagnostic._fit_position_factors({2022: _fold(2022)})
    assert fit["calibration_seasons"] == [2022]
    assert fit["factors"] == {
        "QB": 1.5, "RB": 1.5, "WR": 1.5, "TE": 1.5}


def test_factor_schedule_is_strictly_walk_forward(monkeypatch):
    calls = []

    def fit(folds):
        seasons = sorted(folds)
        calls.append(seasons)
        return {
            "calibration_seasons": seasons,
            "factors": {position: 1.0 for position in diagnostic.POSITIONS},
            "positions": {},
        }

    monkeypatch.setattr(diagnostic, "_fit_position_factors", fit)
    folds = {season: _fold(season) for season in diagnostic.ALL_SEASONS}
    schedule = diagnostic.fit_walk_forward_schedule(folds)
    assert calls == [[2022], [2022, 2023], [2022, 2023, 2024]]
    assert schedule[2025]["calibration_seasons"] == [2022, 2023, 2024]


def test_walk_forward_scaling_preserves_every_row_mean(monkeypatch):
    monkeypatch.setattr(diagnostic.served, "N_SIMS", 101)
    folds = {season: _fold(season) for season in diagnostic.ALL_SEASONS}
    schedule = {
        season: {
            "calibration_seasons": list(range(2022, season)),
            "factors": {
                "QB": 0.97, "RB": 1.005, "TE": 0.94, "WR": 1.07},
            "positions": {},
        }
        for season in diagnostic.EVALUATION_SEASONS
    }
    scores, mean_delta = diagnostic.score_walk_forward(folds, schedule)
    assert len(scores) == 12
    assert mean_delta <= 1e-10


def test_route_gate_uses_only_calibrated_30_brier_and_mean_invariant():
    assert diagnostic.calibrated_route_gate(
        {"brier_30": 0.02}, {"brier_30": 0.019}, 1e-12)["passes"]
    assert not diagnostic.calibrated_route_gate(
        {"brier_30": 0.02}, {"brier_30": 0.021}, 1e-12)["passes"]
    assert not diagnostic.calibrated_route_gate(
        {"brier_30": 0.02}, {"brier_30": 0.019}, 1e-8)["passes"]


def test_cli_and_cloud_runner_are_packaged():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    cli = (root / "src/nfl_dfs/cli.py").read_text()
    runner = root / "scripts/cloud_route_final_served_calibration.sh"
    assert "route-final-served-calibration-diagnostic" in cli
    assert runner.is_file()
    assert "20260811-route-final-served-calibration-v1" in runner.read_text()
