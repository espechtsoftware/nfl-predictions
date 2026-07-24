import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models import calibration


def test_apply_widen_math():
    preds = pd.DataFrame(
        {"proj_points": [12.0], "proj_p10": [5.0], "proj_p50": [10.0],
         "proj_p90": [15.0], "proj_std": [4.0]}
    )
    out = calibration.apply_widen(preds, pd.Series(["QB"]), factors={"QB": 1.5})
    assert out.proj_p10.iloc[0] == pytest.approx(2.5)
    assert out.proj_p90.iloc[0] == pytest.approx(17.5)
    assert out.proj_std.iloc[0] == pytest.approx(6.0)
    assert out.proj_points.iloc[0] == 12.0  # mean untouched
    # Unknown position -> factor 1.0, unchanged
    same = calibration.apply_widen(preds, pd.Series(["DST"]), factors={"QB": 1.5})
    assert same.proj_p10.iloc[0] == 5.0


def test_fit_recovers_needed_widen():
    rng = np.random.default_rng(0)
    n = 4000
    actual = rng.normal(12, 6, n)
    # Bands built from a too-narrow sigma of 4: true 10/90 quantiles need ~1.5x
    proj = pd.DataFrame({
        "position": "RB",
        "actual": actual,
        "proj_p50": np.full(n, 12.0),
        "proj_p10": np.full(n, 12.0 - 1.2816 * 4),
        "proj_p90": np.full(n, 12.0 + 1.2816 * 4),
    })
    factors = calibration.fit_widen_factors(proj)
    assert factors["RB"] == pytest.approx(1.5, abs=0.1)
    widened = calibration.apply_widen(
        proj.assign(proj_std=4.0), proj.position, factors
    )
    assert np.mean(actual < widened.proj_p10) == pytest.approx(0.10, abs=0.02)
    assert np.mean(actual < widened.proj_p90) == pytest.approx(0.90, abs=0.02)
