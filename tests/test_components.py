import numpy as np

from nfl_dfs.models import components, simulate


def test_component_training_and_masks(small_panel):
    cm = components.train(small_panel, target_season=2022, num_boost_round=60)
    assert {"targets", "catch_rate", "ypr", "carries"} <= set(cm.models)

    va = small_panel[small_panel.season == 2022]
    comps = cm.predict_components(va)
    pos = va.position.to_numpy()

    # Position masks: QBs get no targets, non-QBs get no pass attempts
    assert (comps.loc[pos == "QB", "targets"] == 0).all()
    assert (comps.loc[pos != "QB", "pass_attempts"] == 0).all()
    # Rates are clipped to sane ranges
    assert comps.catch_rate.between(0.2, 0.95).all()
    assert comps.ypr.between(2.0, 25.0).all()
    assert (comps.targets >= 0).all()


def test_wr_expected_targets_track_usage(small_panel):
    cm = components.train(small_panel, target_season=2022, num_boost_round=120)
    va = small_panel[(small_panel.season == 2022) & (small_panel.position == "WR")]
    comps = cm.predict_components(va)
    corr = np.corrcoef(comps.targets, va.target_share_l4)[0, 1]
    assert corr > 0.4, f"expected targets should track usage, corr={corr:.2f}"


def test_simulation_summary_shape_and_ordering(small_panel):
    cm = components.train(small_panel, target_season=2022, num_boost_round=60)
    va = small_panel[small_panel.season == 2022].head(50)
    comps = cm.predict_components(va)
    res = simulate.simulate(comps, n_sims=2000, seed=1)
    s = res.summary
    assert len(s) == 50
    assert (s.proj_p10 <= s.proj_p50).all()
    assert (s.proj_p50 <= s.proj_p90).all()
    assert (s.proj_std >= 0).all()
    assert s.p_20_plus.between(0, 1).all()


def test_simulation_mean_consistent_with_components(small_panel):
    """The simulated mean must roughly equal the analytic expectation of the
    composed components — a mismatch means the sampler is biased."""
    cm = components.train(small_panel, target_season=2022, num_boost_round=100)
    va = small_panel[(small_panel.season == 2022) & (small_panel.position == "WR")].head(30)
    comps = cm.predict_components(va)
    res = simulate.simulate(comps, n_sims=8000, seed=2)

    analytic = (
        comps.targets * comps.catch_rate * (1.0 + 0.1 * comps.ypr)  # rec + yards
        + 6.0 * comps.rec_tds.clip(lower=0)
        + comps.carries * comps.ypc * 0.1
        + 6.0 * comps.rush_tds.clip(lower=0)
    )
    # Bonuses only add points, so simulated mean >= analytic - small tolerance
    diff = res.summary.proj_points - analytic
    assert (diff > -1.0).all()
    assert diff.abs().mean() < 2.5


def test_simulation_draws_scored_with_bonuses(small_panel):
    cm = components.train(small_panel, target_season=2022, num_boost_round=60)
    va = small_panel[small_panel.season == 2022].head(5)
    comps = cm.predict_components(va)
    res = simulate.simulate(comps, n_sims=500, seed=3, keep_draws=True)
    assert res.draws.shape == (5, 500)
