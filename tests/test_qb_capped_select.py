"""MAX_QBS selection cap (harvest attribution follow-up).

The six-season attribution found selection spreading 40 entries over ~16
distinct QBs, so no lineup ever assembled the right stack WITH the right
pieces (max 2-of-8 overlap with the weekly optimal). _select_tail_qb_capped
must (a) never exceed the distinct-QB cap, including in the fill phase,
and (b) reduce to plain tail selection when the cap is loose.
"""

import numpy as np

from nfl_dfs.backtest.engine import _select_tail_qb_capped
from nfl_dfs.optimizer.lineup import select_tail_entries


def _mk(n_cands=30, n_sims=400, seed=7):
    rng = np.random.default_rng(seed)
    base = rng.normal(150, 12, size=(n_cands, 1))
    totals = base + rng.normal(0, 25, size=(n_cands, n_sims))
    qb_of = [f"QB{i % 10}" for i in range(n_cands)]  # 10 distinct QBs
    return totals, qb_of


def test_cap_respected_including_fill():
    totals, qb_of = _mk()
    for cap in (2, 3, 5):
        picked = _select_tail_qb_capped(totals, 12, 190.0, qb_of, cap)
        assert picked, "must select something"
        assert len({qb_of[i] for i in picked}) <= cap
        assert len(picked) == len(set(picked))


def test_loose_cap_matches_uncapped():
    totals, qb_of = _mk()
    capped = _select_tail_qb_capped(totals, 12, 190.0, qb_of, 999)
    plain = select_tail_entries(totals, 12, 190.0)
    assert capped == plain


def test_cap_buys_depth_in_kept_stacks():
    # Construct a pool where QB0 candidates clear the line in disjoint
    # sims (real depth) and nine other QBs each clear one overlapping
    # sliver. Capped selection must concentrate on QB0 variants.
    n_sims = 300
    totals = np.full((12, n_sims), 150.0)
    for v in range(3):  # QB0 variants boom in disjoint sim blocks
        totals[v, v * 60:(v + 1) * 60] = 200.0
    for c in range(3, 12):  # rivals all boom in the same small block
        totals[c, 280:290] = 200.0
    qb_of = ["QB0"] * 3 + [f"QB{c}" for c in range(1, 10)]
    picked = _select_tail_qb_capped(totals, 4, 194.0, qb_of, 2)
    assert set(picked) >= {0, 1, 2}, "all three QB0 variants must be kept"
    assert len({qb_of[i] for i in picked}) <= 2
