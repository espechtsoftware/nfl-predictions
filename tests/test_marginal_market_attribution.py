"""Marginal-vs-market attribution audit (S4): exceedance detection,
pinball comparison, strata suppression, and fail-closed validation."""
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis.marginal_market_attribution import (
    AttributionError,
    attribution_report,
    model_quantiles_from_draws,
    pinball_loss,
)


def _panel(n=400, seed=9):
    """Synthetic common-support panel: actual ~ N(10, 4); the market's
    q90 is calibrated, the model's q90 is set too WIDE (higher), so model
    exceedance must land below nominal while market sits near it."""
    rng = np.random.default_rng(seed)
    actual = rng.normal(10, 4, size=n)
    true_q90 = 10 + 4 * 1.2816
    frame = pd.DataFrame({
        "season": 2025,
        "week": np.arange(n) % 18 + 1,
        "player_id": [f"p{i}" for i in range(n)],
        "position": np.where(np.arange(n) % 2 == 0, "WR", "RB"),
        "stratum": np.where(np.arange(n) % 10 == 0, "fast_role", "ordinary"),
        "actual": actual,
        "model_q90": true_q90 + 3.0,
        "market_q90": true_q90,
        "model_q95": 10 + 4 * 1.6449 + 3.0,
        "market_q95": 10 + 4 * 1.6449,
        "model_q99": 10 + 4 * 2.3263 + 3.0,
        "market_q99": 10 + 4 * 2.3263,
    })
    return frame


def test_detects_too_wide_model_against_calibrated_market():
    report = attribution_report(_panel())
    q90 = report["overall"]["q90"]
    assert q90["model_exceedance"] < q90["nominal_exceedance"] - 0.02
    assert abs(q90["market_exceedance"] - 0.10) < 0.04
    assert q90["model_minus_market_pinball"] > 0
    assert q90["instrument_status"] == "validated"
    assert report["overall"]["q95"]["instrument_status"] == "descriptive"
    assert report["overall"]["q99"]["instrument_status"] == "descriptive"


def test_small_strata_are_suppressed_not_reported():
    frame = _panel(n=60)
    report = attribution_report(frame)
    fast = report["by_stratum"]["fast_role"]
    assert "suppressed_below_min_rows" in fast
    ordinary = report["by_stratum"]["ordinary"]
    assert "q90" in ordinary


def test_pinball_loss_known_values():
    realized = np.array([10.0, 10.0])
    assert pinball_loss(realized, np.array([8.0, 12.0]), 0.9) == \
        pytest.approx((0.9 * 2 + 0.1 * 2) / 2)


def test_model_quantiles_from_draws():
    row = np.linspace(0.0, 100.0, 1001)
    quantiles = model_quantiles_from_draws(row)
    assert quantiles["q90"] == pytest.approx(90.0)
    assert quantiles["q99"] == pytest.approx(99.0)
    with pytest.raises(AttributionError):
        model_quantiles_from_draws(row[:50])


def test_fail_closed_validation():
    frame = _panel()
    with pytest.raises(AttributionError):
        attribution_report(frame.drop(columns=["market_q90"]))
    with pytest.raises(AttributionError):
        attribution_report(frame.iloc[:0])
    duplicated = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(AttributionError):
        attribution_report(duplicated)
    bad = frame.copy()
    bad.loc[0, "actual"] = np.nan
    with pytest.raises(AttributionError):
        attribution_report(bad)
