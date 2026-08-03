"""SIM_WIDEN_DRAWS: mean-preserving draw widening (WR-ceiling lever).

The calibration's widen factors only ever stretched summary quantiles;
this lever applies them to the draw matrix the contest engine actually
optimizes against. Mean preservation is the contract — projections and
field behavior must not move, only the joint tail."""

import numpy as np
import pandas as pd

from nfl_dfs.backtest.replay import _widen_draws


def _mk():
    rng = np.random.default_rng(3)
    draws = rng.gamma(2.0, 5.0, size=(4, 5000))
    pos = pd.Series(["WR", "QB", "RB", "TE"])
    return draws, pos


def test_mean_preserved_and_std_scaled():
    draws, pos = _mk()
    out = _widen_draws(draws, pos, "WR:1.3,QB:1.5")
    np.testing.assert_allclose(out.mean(axis=1), draws.mean(axis=1), rtol=1e-9)
    ratio = out.std(axis=1) / draws.std(axis=1)
    np.testing.assert_allclose(ratio, [1.3, 1.5, 1.0, 1.0], rtol=1e-9)


def test_fitted_uses_calibration_factors():
    from nfl_dfs.models.calibration import DEFAULT_WIDEN

    draws, pos = _mk()
    out = _widen_draws(draws, pos, "fitted")
    ratio = out.std(axis=1) / draws.std(axis=1)
    expect = [DEFAULT_WIDEN[p] for p in pos]
    np.testing.assert_allclose(ratio, expect, rtol=1e-9)


def test_tail_actually_deepens():
    draws, pos = _mk()
    out = _widen_draws(draws, pos, "WR:1.3")
    assert np.percentile(out[0], 99) > np.percentile(draws[0], 99)
    assert (out[0] >= 40).mean() > (draws[0] >= 40).mean()


def test_shape_mix_blends_worlds(monkeypatch):
    from nfl_dfs.backtest.replay import apply_draw_shape

    draws, pos = _mk()
    monkeypatch.setenv("SHAPE_MIX", "0.5")
    out = apply_draw_shape(draws, pos, seed=1)
    n = draws.shape[1]
    # raw half untouched, shaped half changed
    np.testing.assert_array_equal(out[:, n // 2:], draws[:, n // 2:])
    assert not np.allclose(out[:, :n // 2], draws[:, :n // 2])


def test_emp_pos_filter(monkeypatch):
    from nfl_dfs.backtest.replay import _empirical_marginals

    draws, pos = _mk()
    monkeypatch.setenv("EMP_POS", "QB,RB,WR")
    out = _empirical_marginals(draws.copy(), pos,
                               np.random.default_rng(1))
    te_row = list(pos).index("TE")
    np.testing.assert_array_equal(out[te_row], draws[te_row])
    monkeypatch.delenv("EMP_POS")
