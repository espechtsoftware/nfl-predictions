import numpy as np
import pandas as pd

from nfl_dfs.research.qb_gumbel_factor import (
    apply_qb_gumbel_factor,
    gumbel_conditional_cdf,
    invert_gumbel_conditional,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "season": [2025] * 7,
        "week": [1] * 7,
        "team": ["A", "A", "A", "A", "B", "B", "B"],
        "position": ["QB", "WR", "TE", "RB", "QB", "QB", "WR"],
        "mean_projection": [20.0, 12.0, 8.0, 14.0, 15.0, 8.0, 11.0],
    })


def test_theta_one_is_exact_identity():
    draws = np.random.default_rng(1).normal(size=(7, 501))
    out, audit = apply_qb_gumbel_factor(
        draws, _frame(), theta_wr=1.0, theta_te=1.0)
    assert np.array_equal(out, draws)
    assert audit["changed_rank_rows"] == 0
    assert audit["ambiguous_qb_team_weeks"] == 1


def test_overlay_is_deterministic_exact_marginal_and_scoped():
    draws = np.random.default_rng(2).normal(size=(7, 1000))
    out, audit = apply_qb_gumbel_factor(
        draws, _frame(), theta_wr=1.4, theta_te=1.2)
    again, repeated = apply_qb_gumbel_factor(
        draws, _frame(), theta_wr=1.4, theta_te=1.2)
    assert np.array_equal(out, again)
    assert audit == repeated
    assert all(np.array_equal(np.sort(before), np.sort(after))
               for before, after in zip(draws, out))
    # QB/RB rows and the receiver on an ambiguous-QB team remain unchanged.
    assert all(np.array_equal(out[index], draws[index])
               for index in (0, 3, 4, 5, 6))
    assert audit["target_rows"] == 2
    assert audit["changed_rank_rows"] == 2
    assert audit["maximum_mean_delta"] < 1e-12


def test_conditional_inverse_round_trips():
    rng = np.random.default_rng(3)
    root = rng.uniform(0.001, 0.999, 500)
    innovation = rng.uniform(0.001, 0.999, 500)
    receiver = invert_gumbel_conditional(innovation, root, 1.6)
    recovered = gumbel_conditional_cdf(receiver, root, 1.6)
    assert np.max(np.abs(recovered - innovation)) < 1e-12


def test_gumbel_overlay_increases_qb_receiver_upper_tail():
    rng = np.random.default_rng(4)
    worlds = 10_000
    draws = rng.normal(size=(2, worlds))
    frame = pd.DataFrame({
        "season": [2025, 2025], "week": [1, 1], "team": ["A", "A"],
        "position": ["QB", "WR"], "mean_projection": [20.0, 12.0],
    })
    out, _ = apply_qb_gumbel_factor(
        draws, frame, theta_wr=1.6, theta_te=1.0)
    before = np.mean((draws[0] > np.quantile(draws[0], 0.9))
                     & (draws[1] > np.quantile(draws[1], 0.9)))
    after = np.mean((out[0] > np.quantile(out[0], 0.9))
                    & (out[1] > np.quantile(out[1], 0.9)))
    assert after > before * 2
