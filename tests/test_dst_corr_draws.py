"""DST_CORR_DRAWS: anti-correlated, mean-preserving DST draws (A/B gate)."""

import numpy as np
import pandas as pd

from nfl_dfs.backtest.engine import _row_draws


def _slate_and_draws(n_sims=4000, seed=0):
    rng = np.random.default_rng(seed)
    slate = pd.DataFrame({
        "team": ["AAA", "AAA", "BBB", "BBB"],
        "opp":  ["BBB", "BBB", "AAA", "AAA"],
        "proj": [15.0, 12.0, 14.0, 6.0],
        "draw_idx": [0, 1, 2, -1],  # last row is the DST (team BBB vs AAA)
    })
    draws = rng.gamma(4.0, 3.5, (3, n_sims))
    return slate, draws


def test_gate_off_dst_is_constant(monkeypatch):
    monkeypatch.delenv("DST_CORR_DRAWS", raising=False)
    slate, draws = _slate_and_draws()
    rd = _row_draws(slate, draws, env={})
    assert np.allclose(rd[3], 6.0)


def test_gate_on_dst_anticorrelated_and_mean_preserved(monkeypatch):
    monkeypatch.setenv("DST_CORR_DRAWS", "1")
    slate, draws = _slate_and_draws()
    rd = _row_draws(slate, draws, env={"DST_CORR_DRAWS": "1"})
    opp_total = rd[0] + rd[1]  # AAA offense vs the BBB DST
    corr = np.corrcoef(rd[3], opp_total)[0, 1]
    # Fitted moments: corr -0.491, rel-sd 0.93 (both within tolerance)
    assert -0.6 < corr < -0.35
    assert abs(rd[3].mean() - 6.0) < 0.15
    rel_sd = rd[3].std() / rd[3].mean()
    assert 0.7 < rel_sd < 1.1


def test_gate_on_skill_rows_untouched(monkeypatch):
    monkeypatch.setenv("DST_CORR_DRAWS", "1")
    slate, draws = _slate_and_draws()
    rd = _row_draws(slate, draws, env={"DST_CORR_DRAWS": "1"})
    np.testing.assert_allclose(rd[0], draws[0], rtol=1e-6)


def test_gate_on_dst_variance_materially_positive(monkeypatch):
    """External review 4.2: with the gate on, DST rows must carry real
    variance (the whole point vs the static fallback), not a token
    epsilon."""
    import numpy as np

    from nfl_dfs.backtest.engine import _row_draws

    monkeypatch.setenv("DST_CORR_DRAWS", "1")
    slate, draws = _slate_and_draws()
    rd = _row_draws(slate, draws, env={"DST_CORR_DRAWS": "1"})
    dst = slate.index[slate.draw_idx < 0]
    for i in dst:
        rel_sd = rd[i].std() / max(rd[i].mean(), 1e-6)
        assert rel_sd > 0.3, f"DST row {i} rel-sd {rel_sd:.3f} too flat"
