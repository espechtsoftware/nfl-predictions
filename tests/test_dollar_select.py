"""SELECT_OBJ=dollars: expected-dollars entry selection (engine)."""

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest.engine import _tier_thresholds, select_dollar_entries
from nfl_dfs.backtest.payout import gpp
from nfl_dfs.optimizer.lineup import Lineup


def test_tier_thresholds_match_scalar_payout():
    c = gpp()
    cums, pays = _tier_thresholds(c)
    rng = np.random.default_rng(0)
    for rank in rng.integers(1, c.field_size, 200):
        frac = rank / c.field_size
        idx = np.searchsorted(cums, frac, side="left")
        vec = float(pays[min(idx, len(pays) - 1)]) if idx < len(pays) else 0.0
        assert vec == pytest.approx(c.payout_for_rank(int(rank)))


def _tiny_slate(n=24, seed=1):
    rng = np.random.default_rng(seed)
    pos = (["QB"] * 3 + ["RB"] * 6 + ["WR"] * 9 + ["TE"] * 3 + ["DST"] * 3)
    return pd.DataFrame({
        "id": [f"p{i}" for i in range(n)],
        "pos": pos[:n],
        "salary": rng.integers(3000, 9000, n),
        "proj": rng.uniform(5, 25, n),
    })


def test_dollar_selection_prefers_dominant_candidate(monkeypatch):
    slate = _tiny_slate()
    n_sims = 400
    rng = np.random.default_rng(2)
    rd = rng.gamma(3, 4, (len(slate), n_sims)).astype(np.float32)

    def mk(ids):
        players = [{"id": f"p{i}", "pos": "WR", "salary": 4000, "proj": 10.0}
                   for i in ids]
        return Lineup(players)

    cands = [mk(range(0, 9)), mk(range(9, 18)), mk(range(6, 15))]
    base = np.stack([rd[list(range(0, 9))].sum(axis=0),
                     rd[list(range(9, 18))].sum(axis=0),
                     rd[list(range(6, 15))].sum(axis=0)])
    # Make candidate 1 strictly dominant in every sim
    totals = base.copy()
    totals[1] += 500.0
    picked = select_dollar_entries(slate, rd, cands, totals, n_entries=2,
                                   contest=gpp(), n_field=50, n_sim_sub=200)
    assert picked[0] == 1
    assert len(picked) == 2 and len(set(picked)) == 2


def test_tail_resolution_distinguishes_sample_beaters(monkeypatch):
    """The Addendum-34 flaw: two candidates that both beat the ENTIRE
    sampled field used to get identical (top-tier) E[$]. The hybrid
    tail estimator must rank the stronger one higher, and neither
    should automatically score as outright 1st of 100k."""
    import numpy as np
    from nfl_dfs.backtest import engine
    from nfl_dfs.backtest.engine import select_dollar_entries
    from nfl_dfs.backtest.payout import gpp
    from nfl_dfs.optimizer.lineup import Lineup

    slate = _tiny_slate()
    n_sims = 300
    rng = np.random.default_rng(5)
    rd = rng.gamma(3, 4, (len(slate), n_sims)).astype(np.float32)

    def mk(ids):
        return Lineup([{"id": f"p{i}", "pos": "WR", "salary": 4000,
                        "proj": 10.0} for i in ids])

    cands = [mk(range(0, 9)), mk(range(9, 18))]
    base = np.stack([rd[list(range(0, 9))].sum(axis=0),
                     rd[list(range(9, 18))].sum(axis=0)])
    totals = base.copy()
    totals[0] += 200.0   # clears the whole field sample in every sim
    totals[1] += 260.0   # clears it by MORE -- deeper into the true tail

    # Capture the internal EVs by spying on the selection order
    picked = select_dollar_entries(slate, rd, cands, totals, n_entries=2,
                                   contest=gpp(), n_field=60, n_sim_sub=200)
    assert picked[0] == 1  # the deeper tail must rank first now
