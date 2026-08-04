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


def test_thesis_repair_enforces_portfolio_floor():
    import numpy as np

    from nfl_dfs.backtest.engine import _enforce_theses

    class L:
        def __init__(self, ids):
            self.players = [{"id": i} for i in ids]

    cands = [L([1, 2, 3]), L([4, 5, 6]), L([7, 8, 9]), L([1, 7, 9])]
    totals = np.array([[200.0], [150.0], [140.0], [190.0]])
    picked = _enforce_theses([1, 2], cands, totals, 194.0,
                             [{"players": [1], "min": 2}])
    assert sum(1 for i in picked if 1 in {p["id"] for p in cands[i].players}) == 2


def _engine_slate(n_teams=8):
    """Minimal engine-ready slate + pool + draws for tail_select_lineups."""
    import pandas as pd

    rng = np.random.default_rng(5)
    rows = []
    pid = 0
    for t in range(n_teams):
        team, opp = f"T{t}", f"T{(t + 1) % n_teams}"
        gid = f"g{min(t, (t + 1) % n_teams)}{max(t, (t + 1) % n_teams)}"
        for pos, n in (("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1), ("DST", 1)):
            for i in range(n):
                proj = {"QB": 18, "RB": 12, "WR": 11, "TE": 7, "DST": 6}[pos] \
                    - 2 * i + rng.normal(0, 1)
                rows.append({
                    "id": pid, "name": f"{pos}{i}{team}", "pos": pos,
                    "team": team, "opp": opp, "game_id": gid,
                    "salary": int(1200 + 250 * max(proj, 1)),
                    "proj": max(proj, 1.0), "actual": max(proj, 1.0),
                    "draw_idx": pid, "proj_tourney": max(proj, 1.0)})
                pid += 1
    slate = pd.DataFrame(rows)
    draws = np.maximum(
        slate.proj.to_numpy()[:, None] + rng.normal(0, 6, (len(slate), 300)),
        0).astype(np.float32)
    return slate, slate.to_dict("records"), draws


def test_thesis_generation_path_end_to_end(monkeypatch):
    """Regression (2026-08-04 audit): the thesis candidate batch crashed
    with UnboundLocalError (seen referenced before assignment) and had
    its tags clobbered by the lev retag loop. Exercise the REAL
    generation path, not just the repair function. Salary-floor and punt
    envs neutralized — the synthetic slate tests thesis mechanics only."""
    from nfl_dfs.backtest.engine import tail_select_lineups

    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    monkeypatch.setenv("PUNT_MIN", "0")
    slate, pool, draws = _engine_slate()
    combo = [0, 2]  # QB of T0 + a T0 RB — feasible pair
    picked = tail_select_lineups(
        slate, pool, draws, tail_line=150.0, n_entries=4, stack=None,
        objective_col="proj_tourney", theses=[{"players": combo, "min": 2}])
    assert len(picked) == 4
    n_combo = sum(1 for lu in picked
                  if set(combo) <= {p["id"] for p in lu.players})
    assert n_combo >= 2, f"thesis floor not met: {n_combo}"
