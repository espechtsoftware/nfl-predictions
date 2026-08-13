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


def test_effective_model_weight_names_the_ablation_unambiguously():
    assert blend.effective_model_weight({}) == blend.BLEND_W
    assert blend.effective_model_weight({"BLEND_MODEL_WEIGHT": "1"}) == 1.0
    with pytest.raises(ValueError, match="between 0 and 1"):
        blend.effective_model_weight({"BLEND_MODEL_WEIGHT": "1.1"})


def test_shift_draws_to_means_preserves_shape_and_sets_each_mean():
    draws = np.array([[1.0, 2.0, 6.0], [10.0, 14.0, 12.0]])
    shifted = blend.shift_draws_to_means(draws, np.array([5.0, 8.0]))
    assert shifted.mean(axis=1) == pytest.approx([5.0, 8.0])
    assert np.diff(shifted, axis=1) == pytest.approx(
        np.diff(draws, axis=1))
    with pytest.raises(ValueError, match="matching player counts"):
        blend.shift_draws_to_means(draws, np.array([5.0]))


def test_shift_draws_to_means_is_exactly_permutation_invariant_for_float32():
    rng = np.random.default_rng(1)
    source = rng.uniform(0.0, 50.0, (2, 10_000)).astype(np.float32)
    permuted = np.stack([
        row[rng.permutation(row.size)] for row in source
    ])
    # This construction is known to produce an order-dependent float32 mean;
    # the helper must promote before reducing and preserve exact marginals.
    assert not np.array_equal(
        source.mean(axis=1), permuted.mean(axis=1))
    target = np.array([21.0, 17.5])
    left = blend.shift_draws_to_means(source, target)
    right = blend.shift_draws_to_means(permuted, target)
    assert left.dtype == right.dtype == np.float64
    assert np.array_equal(np.sort(left, axis=1), np.sort(right, axis=1))
    assert left.mean(axis=1) == pytest.approx(target, abs=1e-12)


def test_replay_market_blend_uses_post_shape_world_mean_when_market_empty():
    from nfl_dfs.backtest.replay import _market_blend_worlds

    frame = pd.DataFrame({
        "season": [2022, 2022], "week": [1, 1],
        "gsis_id": ["a", "b"], "proj_points": [99.0, 99.0],
    })
    draws = np.array([[1.0, 3.0], [10.0, 14.0]], dtype=np.float32)
    market = pd.DataFrame(columns=[
        "season", "week", "gsis_id", "market_points"])
    out, shifted, pre = _market_blend_worlds(
        frame, draws, market, model_weight=0.45)
    assert pre == pytest.approx([2.0, 12.0])
    assert out.proj_points.to_numpy() == pytest.approx([2.0, 12.0])
    assert shifted.mean(axis=1) == pytest.approx([2.0, 12.0])
    assert out.market_points.isna().all()


def test_replay_market_blend_matches_live_formula_on_covered_rows():
    from nfl_dfs.backtest.replay import _market_blend_worlds

    frame = pd.DataFrame({
        "season": [2025, 2025], "week": [1, 1],
        "gsis_id": ["a", "b"], "proj_points": [99.0, 99.0],
    })
    draws = np.array([[1.0, 3.0], [10.0, 14.0]], dtype=np.float32)
    market = pd.DataFrame({
        "season": [2025], "week": [1], "gsis_id": ["a"],
        "market_points": [10.0],
    })
    out, shifted, pre = _market_blend_worlds(
        frame, draws, market, model_weight=0.25)
    assert pre == pytest.approx([2.0, 12.0])
    assert out.proj_points.to_numpy() == pytest.approx([8.0, 12.0])
    assert shifted.mean(axis=1) == pytest.approx([8.0, 12.0])
    assert out.consensus_div.to_numpy() == pytest.approx([-8.0, 0.0])


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


def test_cold_start_fill_allows_nullable_rookie_metadata():
    """Salary-spined rows can lack roster metadata; unknown rookie status
    must use the ordinary role prior rather than crashing the replay."""
    df = pd.DataFrame({
        "gsis_id": ["unknown"],
        "position": ["WR"],
        "depth_rank": [pd.NA],
        "is_cold_start": [True],
        "is_rookie": pd.Series([pd.NA], dtype="boolean"),
        "draft_round": [pd.NA],
        "target_share_l4": [np.nan],
        "carry_share_l4": [np.nan],
        "wopr_l4": [np.nan],
        "snap_share_l4": [np.nan],
        "rz20_targets_smoothed": [np.nan],
        "gl3_carries_smoothed": [np.nan],
    })
    filled = coldstart.fill_cold_start_features(df)
    assert filled.loc[0, "target_share_l4"] == pytest.approx(0.11)


def test_widen_cold_start_quantiles():
    preds = pd.DataFrame(
        {"proj_p10": [5.0], "proj_p50": [10.0], "proj_p90": [15.0], "proj_std": [4.0]}
    )
    out = coldstart.widen_cold_start_quantiles(preds, pd.Series([True]), widen=1.5)
    assert out.proj_p10.iloc[0] == pytest.approx(2.5)
    assert out.proj_p90.iloc[0] == pytest.approx(17.5)
    assert out.proj_std.iloc[0] == pytest.approx(6.0)
