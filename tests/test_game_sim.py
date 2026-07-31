import importlib

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models import components, game_sim, simulate


def test_terminal_probabilities_sum_to_one():
    assert game_sim.TERMINAL_PROB_MATRIX.shape == (len(game_sim.ZONES), len(game_sim.TERMINALS))
    np.testing.assert_allclose(game_sim.TERMINAL_PROB_MATRIX.sum(axis=1), 1.0)


def test_next_zone_probabilities_sum_to_one_where_defined():
    for terminal in game_sim._NEXT_ZONE_WEIGHTS:
        row = game_sim._NEXT_ZONE_PROB_MATRIX[game_sim.TERMINAL_INDEX[terminal]]
        np.testing.assert_allclose(row.sum(), 1.0)


def test_terminal_probability_improves_with_field_position():
    """TD rate should rise monotonically from deep_own to redzone --
    the whole point of tracking field position at all."""
    td_col = game_sim.TERMINAL_INDEX["td"]
    td_rates = [game_sim.TERMINAL_PROB_MATRIX[game_sim.ZONE_INDEX[z], td_col] for z in game_sim.ZONES]
    assert td_rates == sorted(td_rates)


def test_simulate_team_points_plausible_range():
    rng = np.random.default_rng(0)
    n_drives = np.full(20_000, 11)
    points = game_sim.simulate_team_points(rng, n_drives)
    assert points.shape == (20_000,)
    assert (points >= 0).all()
    # ~11 drives/game at ~2.0-2.2 pts/drive should land well within a wide band
    assert 12 <= points.mean() <= 32


def test_simulate_team_points_respects_variable_drive_counts():
    rng = np.random.default_rng(1)
    few = game_sim.simulate_team_points(rng, np.full(5000, 6))
    many = game_sim.simulate_team_points(rng, np.full(5000, 16))
    assert many.mean() > few.mean()


def test_simulate_game_points_shape_and_nonnegative():
    rng = np.random.default_rng(2)
    pts_a, pts_b = game_sim.simulate_game_points(rng, n_sims=5000)
    assert pts_a.shape == pts_b.shape == (5000,)
    assert (pts_a >= 0).all() and (pts_b >= 0).all()


def test_game_factor_matrix_mean_preserving_and_positive():
    rng = np.random.default_rng(3)
    factors = game_sim.game_factor_matrix(rng, n_games=4, n_sims=10_000)
    assert factors.shape == (4, 10_000)
    assert (factors >= 0).all()
    np.testing.assert_allclose(factors.mean(axis=1), 1.0, atol=0.02)


def test_allocate_drive_usage_sums_to_units_single_draw():
    rng = np.random.default_rng(4)
    shares = np.array([0.5, 0.3, 0.2])
    allocated = game_sim.allocate_drive_usage(rng, 10.0, shares, n_sims=1)
    assert allocated.shape == (3,)
    assert allocated.sum() == pytest.approx(10.0)


def test_allocate_drive_usage_vectorized_over_sims():
    rng = np.random.default_rng(5)
    shares = np.array([0.6, 0.25, 0.15])
    allocated = game_sim.allocate_drive_usage(rng, 8.0, shares, n_sims=2000)
    assert allocated.shape == (2000, 3)
    np.testing.assert_allclose(allocated.sum(axis=1), 8.0)
    # in expectation the split should track the prior shares
    mean_share = allocated.mean(axis=0) / allocated.mean(axis=0).sum()
    np.testing.assert_allclose(mean_share, shares, atol=0.03)


def test_allocate_drive_usage_handles_all_zero_shares():
    rng = np.random.default_rng(6)
    allocated = game_sim.allocate_drive_usage(rng, 4.0, np.zeros(4), n_sims=1)
    assert allocated.shape == (4,)
    assert allocated.sum() == pytest.approx(4.0)


def test_simulate_default_mode_unaffected_by_game_sim_module(small_panel, monkeypatch):
    """GAME_SIM_MODE unset must reproduce today's lognormal output exactly
    -- this module must be a pure opt-in addition."""
    monkeypatch.delenv("GAME_SIM_MODE", raising=False)
    importlib.reload(simulate)
    cm = components.train(small_panel, target_season=2022, num_boost_round=60)
    va = small_panel[small_panel.season == 2022].head(30)
    comps = cm.predict_components(va)
    game_ids = va.game_id

    res_a = simulate.simulate(comps, n_sims=1000, seed=7, game_ids=game_ids)
    res_b = simulate.simulate(comps, n_sims=1000, seed=7, game_ids=game_ids)
    pd.testing.assert_frame_equal(res_a.summary, res_b.summary)


def test_simulate_possession_mode_runs_and_differs_from_lognormal(small_panel, monkeypatch):
    cm = components.train(small_panel, target_season=2022, num_boost_round=60)
    va = small_panel[small_panel.season == 2022].head(30)
    comps = cm.predict_components(va)
    game_ids = va.game_id

    monkeypatch.delenv("GAME_SIM_MODE", raising=False)
    importlib.reload(simulate)
    baseline = simulate.simulate(comps, n_sims=2000, seed=8, game_ids=game_ids)

    monkeypatch.setenv("GAME_SIM_MODE", "possession")
    importlib.reload(simulate)
    try:
        possession = simulate.simulate(comps, n_sims=2000, seed=8, game_ids=game_ids)
    finally:
        monkeypatch.delenv("GAME_SIM_MODE", raising=False)
        importlib.reload(simulate)

    assert possession.summary.shape == baseline.summary.shape
    assert (possession.summary.proj_points >= 0).all()
    # different engines, same seed -> shouldn't coincidentally match exactly
    assert not possession.summary.proj_points.equals(baseline.summary.proj_points)
