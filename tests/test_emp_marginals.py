"""EMP_MARGINALS: empirical marginal shapes, our copula and moments.

Contracts: mean and std preserved per row (affine match), rank order of
each row's draws preserved exactly (correlation structure untouched),
high-tier WR/RB tails fatten (weibull family), unknown positions pass
through untouched."""

import numpy as np
import pandas as pd

from nfl_dfs.backtest.replay import _empirical_marginals


def _draws(n_rows=4, n_sims=20_000, mu=20.0, sd=8.0, seed=2):
    rng = np.random.default_rng(seed)
    return rng.normal(mu, sd, size=(n_rows, n_sims))


def test_moments_and_ranks_preserved():
    draws = _draws()
    pos = pd.Series(["WR", "RB", "QB", "TE"])
    out = _empirical_marginals(draws, pos, np.random.default_rng(1))
    np.testing.assert_allclose(out.mean(axis=1), draws.mean(axis=1), atol=1e-6)
    np.testing.assert_allclose(out.std(axis=1), draws.std(axis=1), rtol=1e-6)
    for i in range(4):
        assert (np.argsort(out[i]) == np.argsort(draws[i])).all()


def test_wr_high_tier_gains_right_skew():
    draws = _draws(n_rows=1, mu=20.0, sd=8.0)  # normal input: zero skew
    out = _empirical_marginals(draws, pd.Series(["WR"]),
                               np.random.default_rng(1))
    def skew(x):
        z = (x - x.mean()) / x.std()
        return float((z ** 3).mean())
    assert skew(out[0]) > skew(draws[0]) + 0.1


def test_unknown_position_passthrough():
    # position absent from the fitted table -> row must be untouched
    draws = _draws(n_rows=1)
    out = _empirical_marginals(draws, pd.Series(["FB"]),
                               np.random.default_rng(1))
    np.testing.assert_array_equal(out[0], draws[0])
