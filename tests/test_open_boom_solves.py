"""OPEN_BOOM_SOLVES lever (A3 stack-relaxation carve): with the lever
set, the first k boom visits at a deterministic stride solve without the
QB-stack and bring-back minima; every other solve keeps production
StackRules. Off-by-default must be byte-identical (vacuity law), and the
open solves must actually produce rosters outside the mandated shape on
a slate engineered so the unconstrained optimum is un-stacked.
"""
import numpy as np
import pandas as pd

from nfl_dfs.backtest import engine
from nfl_dfs.optimizer.lineup import StackRules


def _slate(n_worlds: int = 32):
    """Slate whose per-world optima are naturally UN-stacked: each QB's
    teammates score low whenever that QB scores high, so a forced stack
    always costs points and the open solve should drop it."""
    # Symmetric two-game slate whose every nine-player roster lands inside
    # the production salary window (8 skill ~5650-5700 + DST 4000 falls in
    # [49k, 50k]), so the stacked formulation is always feasible.
    partner = {"T0": "T1", "T1": "T0", "T2": "T3", "T3": "T2"}
    game_of = {"T0": "g0", "T1": "g0", "T2": "g1", "T3": "g1"}
    pool, ix = [], 0
    for pos, n in (("QB", 4), ("RB", 8), ("WR", 12), ("TE", 6), ("DST", 4)):
        for k in range(n):
            team = f"T{ix % 4}"
            salary = 4000 if pos == "DST" else 5650 + (k % 3) * 25
            pool.append({
                "id": f"{pos}{k}", "name": f"{pos}{k}", "pos": pos,
                "team": team, "opp": partner[team],
                "game_id": game_of[team], "salary": salary,
                "proj": 8.0 + (k % 6), "actual": 9.0 + (k % 7),
                "season": 2025, "week": 3})
            ix += 1
    slate = pd.DataFrame(pool)
    slate["draw_idx"] = range(len(slate))
    rng = np.random.default_rng(7)
    draws = np.abs(rng.normal(9, 3.0, size=(len(pool), n_worlds)))
    qb_team = {row["id"]: row["team"] for row in pool if row["pos"] == "QB"}
    for w in range(n_worlds):
        hot_qb = f"QB{w % 4}"
        hot_team = qb_team[hot_qb]
        for i, row in enumerate(pool):
            if row["id"] == hot_qb:
                draws[i, w] += 25.0
            elif row["team"] == hot_team and row["pos"] in ("WR", "TE"):
                draws[i, w] = 0.5
    return slate, pool, draws


def _candidates(policy_env):
    slate, pool, draws = _slate()
    captured = {}
    engine.tail_select_lineups(
        slate, pool, draws, tail_line=95.0, n_entries=4,
        stack=StackRules(qb_stack_min=2, bring_back_min=1),
        objective_col="proj", n_boom_solves=6,
        policy_env=policy_env, candidate_capture=captured.__setitem__
        and (lambda b: captured.__setitem__("batch", b)))
    return captured["batch"]


def _structure(candidate, pool):
    team = {r["id"]: r["team"] for r in pool}
    pos = {r["id"]: r["pos"] for r in pool}
    opp = {r["id"]: r["opp"] for r in pool}
    qb = next(p for p in candidate.ids if pos[p] == "QB")
    stack = sum(1 for p in candidate.ids
                if p != qb and team[p] == team[qb] and pos[p] in ("WR", "TE"))
    bring = sum(1 for p in candidate.ids
                if team[p] == opp[qb] and pos[p] in ("RB", "WR", "TE"))
    return stack, bring


def _open_rosters(batch):
    return [
        roster for roster, tags in batch.all_tags.items() if "open" in tags
    ]


def test_off_by_default_is_byte_identical_to_zero():
    plain = _candidates({})
    zero = _candidates({"OPEN_BOOM_SOLVES": "0"})
    assert [c.ids for c in plain.candidates] == \
        [c.ids for c in zero.candidates]
    assert not _open_rosters(plain)


class _Roster:
    def __init__(self, ids):
        self.ids = ids


def test_open_solves_escape_the_mandated_shape():
    batch = _candidates({"OPEN_BOOM_SOLVES": "3"})
    open_rosters = _open_rosters(batch)
    boom_cands = [
        c for c in batch.candidates
        if c.tag == "boom" and "open" not in batch.all_tags.get(c.ids, ())
    ]
    assert len(open_rosters) >= 1
    assert len(boom_cands) >= 1
    slate, pool, draws = _slate()
    # Every mandated solve satisfies stack>=2 and bring-back>=1; at least
    # one open solve must fall OUTSIDE that shape on this slate.
    for c in boom_cands:
        stack, bring = _structure(c, pool)
        assert stack >= 2 and bring >= 1
    assert any(
        _structure(_Roster(tuple(r)), pool)[0] < 2
        or _structure(_Roster(tuple(r)), pool)[1] < 1
        for r in open_rosters
    )


def test_carve_respects_total_boom_budget():
    plain = _candidates({})
    carved = _candidates({"OPEN_BOOM_SOLVES": "3"})
    n_plain = sum(1 for c in plain.candidates if c.tag == "boom")
    n_carved = sum(1 for c in carved.candidates if c.tag == "boom")
    assert n_carved == n_plain
