"""BIGPLAY mixture: house-call events for deep threats (sim-shape lever).

Contract: E[points] exactly preserved (the mean subtraction), far tail
mass strictly added for flagged players, zero effect at rate 0."""

import numpy as np
import pandas as pd

from nfl_dfs.models import simulate


def _comps(n=6):
    return pd.DataFrame({
        "targets": [8.0] * n, "catch_rate": [0.65] * n, "ypr": [11.0] * n,
        "rec_tds": [0.4] * n, "carries": [0.0] * n, "ypc": [0.0] * n,
        "rush_tds": [0.0] * n, "pass_attempts": [0.0] * n, "ypa": [0.0] * n,
        "pass_tds": [0.0] * n, "interceptions": [0.0] * n,
    })


def test_mean_preserved_and_tail_deepens():
    comps = _comps()
    rate = pd.Series([0.0, 0.0, 0.0, 0.12, 0.12, 0.12])
    base = simulate.simulate(comps, n_sims=60_000, seed=5, keep_draws=True)
    boom = simulate.simulate(comps, n_sims=60_000, seed=5, keep_draws=True,
                             bigplay_rate=rate)
    # means within MC noise of identical (exact subtraction of E[lump])
    np.testing.assert_allclose(boom.summary.proj_points,
                               base.summary.proj_points, atol=0.25)
    # unflagged rows byte-identical draws
    np.testing.assert_array_equal(boom.draws[0], base.draws[0])
    # flagged rows: 40+ probability strictly up
    p40_base = (base.draws[3] >= 40).mean()
    p40_boom = (boom.draws[3] >= 40).mean()
    assert p40_boom > p40_base


def test_none_rate_is_noop():
    comps = _comps(3)
    a = simulate.simulate(comps, n_sims=5_000, seed=9, keep_draws=True)
    b = simulate.simulate(comps, n_sims=5_000, seed=9, keep_draws=True,
                          bigplay_rate=None)
    np.testing.assert_array_equal(a.draws, b.draws)
