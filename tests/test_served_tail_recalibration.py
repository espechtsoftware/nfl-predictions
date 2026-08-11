import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import served_tail_recalibration as recalibration
from nfl_dfs.backtest.replay import apply_served_tail_scale


def test_apply_served_tail_scale_is_mean_invariant_and_skill_only():
    draws = np.array([
        [1.0, 2.0, 6.0],
        [4.0, 7.0, 10.0],
        [0.0, 3.0, 12.0],
    ])
    positions = pd.Series(["RB", "QB", "WR"])
    out = apply_served_tail_scale(
        draws, positions, env={"SERVED_TAIL_SCALE": "1.2"})
    assert out[[0, 2]].mean(axis=1) == pytest.approx(
        draws[[0, 2]].mean(axis=1), abs=1e-12)
    assert out[1].tolist() == draws[1].tolist()
    assert np.ptp(out[0]) == pytest.approx(1.2 * np.ptp(draws[0]))
    assert np.ptp(out[2]) == pytest.approx(1.2 * np.ptp(draws[2]))


def test_apply_served_tail_scale_identity_and_bounds():
    draws = np.arange(12, dtype=float).reshape(3, 4)
    positions = pd.Series(["RB", "WR", "TE"])
    assert apply_served_tail_scale(
        draws, positions, env={"SERVED_TAIL_SCALE": "1"}) is draws
    assert apply_served_tail_scale(
        draws, positions, env={"SERVED_TAIL_SCALE": "0"}) is draws
    with pytest.raises(ValueError, match="\\[1, 1.25\\]"):
        apply_served_tail_scale(
            draws, positions, env={"SERVED_TAIL_SCALE": "1.251"})


def _fit_fold(season: int) -> tuple[pd.DataFrame, np.ndarray]:
    frame = pd.DataFrame({
        "season": [season] * 100,
        "week": np.repeat(np.arange(1, 11), 10),
        "gsis_id": [f"{season}-{i}" for i in range(100)],
        "position": ["WR"] * 100,
        "market_covered": [True] * 100,
        "tabpfn_covered": [True] * 100,
    })
    base = np.linspace(0.0, 20.0, 100)
    frame["actual"] = base + np.where(np.arange(100) >= 95, 8.0, 0.0)
    offsets = np.linspace(-5.0, 5.0, 1000)
    return frame, base[:, None] + offsets[None, :]


def test_fit_scale_uses_frozen_grid_and_all_calibration_seasons():
    folds = {year: _fit_fold(year) for year in (2019, 2021, 2022)}
    report = recalibration.fit_scale(folds)
    assert len(report["curve"]) == 51
    assert report["selected_factor"] in recalibration.SCALE_GRID
    assert report["selected_factor"] >= 1.0
    with pytest.raises(ValueError, match="all calibration seasons"):
        recalibration.fit_scale({2019: folds[2019]})


def test_recalibration_gate_matches_frozen_requirements():
    source = {
        "q99_calibration_gap": 0.004,
        "q95_calibration_gap": 0.004,
        "q90_calibration_gap": 0.005,
        "crps": 2.0,
        "brier_20": 0.05,
        "brier_30": 0.02,
    }
    treatment = {
        "q99_calibration_gap": 0.003,
        "q95_calibration_gap": 0.003,
        "q90_calibration_gap": 0.0075,
        "crps": 2.01,
        "brier_20": 0.0505,
        "brier_30": 0.0202,
    }
    gate = recalibration.recalibration_gate(
        source, treatment, 1.0, 1e-10)
    assert gate["passes"]
    treatment["q99_calibration_gap"] = 0.0031
    assert not recalibration.recalibration_gate(
        source, treatment, 1.0, 1e-10)["passes"]
