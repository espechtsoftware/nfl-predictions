import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models import blend, coldstart


def test_fit_blend_weight_recovers_truth():
    rng = np.random.default_rng(4)
    truth = rng.uniform(5, 25, 3000)
    model = truth + rng.normal(0, 3, 3000)
    market = truth + rng.normal(0, 3, 3000)
    w = blend.fit_blend_weight(truth, model, market)
    # Equally-good independent sources -> w near 0.5
    assert 0.35 < w < 0.65


def test_blend_prefers_better_source():
    rng = np.random.default_rng(5)
    truth = rng.uniform(5, 25, 3000)
    model = truth + rng.normal(0, 1, 3000)      # sharp
    market = truth + rng.normal(0, 6, 3000)     # noisy
    w = blend.fit_blend_weight(truth, model, market)
    assert w > 0.75


def test_blend_falls_back_when_market_missing():
    model = np.array([10.0, 12.0])
    market = np.array([np.nan, 8.0])
    out = blend.blend(model, market, w=0.4)
    assert out[0] == 10.0
    assert out[1] == pytest.approx(0.4 * 12 + 0.6 * 8)


def test_prop_line_conversions():
    # Symmetric prob -> mean == line
    assert blend.prop_line_to_mean(62.5, 0.5, "normal") == pytest.approx(62.5, abs=0.1)
    # Higher over-prob -> higher mean
    assert blend.prop_line_to_mean(62.5, 0.6, "normal") > 62.5
    lam = blend.prop_line_to_mean(4.5, 0.5, "poisson")
    assert 4.0 < lam < 5.6


def test_american_odds_and_devig():
    assert blend.american_to_prob(-110) == pytest.approx(0.524, abs=0.001)
    assert blend.american_to_prob(120) == pytest.approx(0.4545, abs=0.001)
    over, under = blend.devig_two_way(0.55, 0.55)
    assert over == pytest.approx(0.5)


def test_cold_start_fill_and_flag_preserved():
    df = pd.DataFrame(
        {
            "position": ["WR", "RB"],
            "depth_rank": [1, 2],
            "implied_team_total": [26.0, 20.0],
            "is_cold_start": [True, True],
            "is_rookie": [True, False],
            "draft_round": [1, None],
            "target_share_l4": [np.nan, np.nan],
            "carry_share_l4": [np.nan, np.nan],
            "wopr_l4": [np.nan, np.nan],
        }
    )
    filled = coldstart.fill_cold_start_features(df)
    assert filled.target_share_l4.notna().all()
    # WR1 rookie with round-1 capital keeps the full role prior
    assert filled.loc[0, "target_share_l4"] == pytest.approx(0.24)
    # RB2 veteran gets the RB2 carry share
    assert filled.loc[1, "carry_share_l4"] == pytest.approx(0.25)
    # Flag must survive filling
    assert filled.is_cold_start.all()


def test_widen_cold_start_quantiles():
    preds = pd.DataFrame(
        {"proj_p10": [5.0], "proj_p50": [10.0], "proj_p90": [15.0], "proj_std": [4.0]}
    )
    out = coldstart.widen_cold_start_quantiles(preds, pd.Series([True]), widen=1.5)
    assert out.proj_p10.iloc[0] == pytest.approx(2.5)
    assert out.proj_p90.iloc[0] == pytest.approx(17.5)
    assert out.proj_std.iloc[0] == pytest.approx(6.0)
