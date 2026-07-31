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
    # 11 drives at the docstring's claimed ~2.0-2.2 pts/drive -> ~22-24;
    # band allows placeholder slop but fails if the table drifts from its
    # own stated calibration (it originally shipped at ~1.4 pts/drive).
    assert 19 <= points.mean() <= 28


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


def test_game_factor_matrix_dispersion_sane():
    """Guard against a wildly over/under-dispersed placeholder table.

    The validated lognormal factor has sd 0.18; real NFL total-points
    relative sd is ~0.30 (13.5 on ~45). The possession factor currently
    measures ~0.32 -- fatter than the lognormal by design (possession
    variance is the point), but it must stay in a band where the replay
    A/B is comparing engines, not a variance bug. Tighten after the pbp
    fit. (The table originally shipped at ~0.45, driven by Poisson
    drive counts with sd ~3.3 vs the real ~1.5-2.)"""
    rng = np.random.default_rng(9)
    factors = game_sim.game_factor_matrix(rng, n_games=4, n_sims=20_000)
    stds = factors.std(axis=1)
    assert (stds > 0.15).all() and (stds < 0.45).all()


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


def test_simulate_default_mode_never_consults_game_sim(small_panel, monkeypatch):
    """With GAME_SIM_MODE unset, simulate() must be deterministic and must
    never touch game_sim at all -- proven by making its entry point raise.
    (Byte-for-byte equivalence with the pre-game_sim code holds by
    inspection: the default branch runs the identical lognormal RNG call.)"""
    monkeypatch.delenv("GAME_SIM_MODE", raising=False)

    def _boom(*args, **kwargs):
        raise AssertionError("game_sim consulted in default mode")

    monkeypatch.setattr(game_sim, "game_factor_matrix", _boom)
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
    baseline = simulate.simulate(comps, n_sims=2000, seed=8, game_ids=game_ids)

    monkeypatch.setenv("GAME_SIM_MODE", "possession")
    possession = simulate.simulate(comps, n_sims=2000, seed=8, game_ids=game_ids)

    assert possession.summary.shape == baseline.summary.shape
    assert (possession.summary.proj_points >= 0).all()
    # different engines, same seed -> shouldn't coincidentally match exactly
    assert not possession.summary.proj_points.equals(baseline.summary.proj_points)
