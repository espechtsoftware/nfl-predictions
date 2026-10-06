"""--main mix (study 18's shape portfolio on the live path): the shared cell definitions, allocation, interleave and
shape check (nfl_dfs.inference.mix_shapes) and union_reselect.mix_rows, against VERBATIM copies of study 18's code
(nfl2 experiments/s18_stack_shapes.py @ 5869a1b) driven by one stand-in optimizer. Offline: no lab clone, no solver."""
import dataclasses
import sys
import types
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.inference import mix_shapes as M

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import union_reselect as ur  # noqa: E402

Q = [0.30, 0.14, 0.28, 0.28]
# the head-layout weights of production's Week-5 draft A (21 entries on 17 ranks) and of study 18's copies-5 plan,
# computed 2026-10-05 with enter_layout.assign_ranks on those (private) plans
W_DRAFT_A = [3, 3] + [1] * 15 + [0] * 88
W_COPIES5 = [11, 11] + [1] * 83 + [0] * 20


def test_cells_are_study_18s_verbatim():
    assert M.MIX_CELLS == {
        "A1": (0.30, {"qb_stack_min": 2, "bring_back_min": 1}, None, None),
        "A2": (0.14, {"qb_stack_min": 2, "bring_back_min": 0, "bring_back_max": 0}, None, None),
        "B": (0.28, {"qb_stack_min": 1, "qb_stack_max": 1, "bring_back_min": 1}, 3, "all"),
        "C": (0.28, {"qb_stack_min": 1, "qb_stack_max": 1, "bring_back_min": 0, "bring_back_max": 0}, 3, None),
    }
    assert M.LIVE_PIN.startswith("f69598b") and len(M.LIVE_PIN) == 40


def test_allocate_and_interleave_equal_study_18s_reference_outputs():
    assert M.allocate(Q, 105) == [32, 15, 29, 29] and M.allocate(Q, 21) == [6, 3, 6, 6] and M.allocate(Q, 17) == [5, 2, 5, 5]
    seq = M.interleave(M.allocate(Q, 105), Q, W_DRAFT_A)
    assert seq[:17] == [0, 2, 3, 3, 1, 3, 1, 0, 2, 3, 0, 2, 3, 1, 0, 2, 3]
    seq5 = M.interleave(M.allocate(Q, 105), Q, W_COPIES5)
    assert seq5[:30] == [0, 2, 3, 3, 3, 3, 1, 3, 3, 1, 3, 1, 3, 1, 3, 3, 1, 3, 0, 1, 2, 3, 0, 2, 3, 0, 1, 2, 3, 0]
    # draft A's dealt entry shares before the overlap limit: A1 6, A2 3, B 6, C 6 of 21
    dealt = Counter()
    for r, j in enumerate(seq[:17]):
        dealt[j] += W_DRAFT_A[r]
    assert [dealt[j] for j in range(4)] == [6, 3, 6, 6]


def test_plan_weights_follow_the_layout(tmp_path):
    import json
    plan = tmp_path / "c.json"
    plan.write_text(json.dumps([{"name": "a", "contest_id": "1", "entries": 3, "keep": 3, "fee": 1, "track": "mean"},
                                {"name": "b", "contest_id": "2", "entries": 1, "keep": 1, "fee": 1, "track": "mean"},
                                {"name": "t", "contest_id": "3", "entries": 2, "keep": 2, "fee": 1, "track": "tail"}]))
    w = M.plan_weights(plan, 10)
    assert sum(w) == 4 and all(x >= 0 for x in w)          # the tail contest is not the main book's


def test_cell_of_tag():
    assert M.cell_of_tag("mix_B") == "B" and M.cell_of_tag("pmo_x50") is None and M.cell_of_tag("lev") is None
    with pytest.raises(ValueError, match="unknown mix cell"):
        M.cell_of_tag("mix_Z")


def _maps():
    # game g1: team A (QB a_qb, WR a_wr1 a_wr2, TE a_te, RB a_rb) vs team B (WR b_wr, RB b_rb); game g2: C vs D
    rows = [("a_qb", "QB", "A", "B", "g1"), ("a_wr1", "WR", "A", "B", "g1"), ("a_wr2", "WR", "A", "B", "g1"),
            ("a_te", "TE", "A", "B", "g1"), ("a_rb", "RB", "A", "B", "g1"), ("b_wr", "WR", "B", "A", "g1"),
            ("b_rb", "RB", "B", "A", "g1"), ("c_wr", "WR", "C", "D", "g2"), ("c_rb", "RB", "C", "D", "g2"), ("c_rb2", "RB", "C", "D", "g2"),
            ("d_wr", "WR", "D", "C", "g2"), ("d_te", "TE", "D", "C", "g2"), ("e_wr", "WR", "E", "F", "g3"),
            ("e_rb", "RB", "E", "F", "g3"), ("f_wr", "WR", "F", "E", "g3"), ("c_dst", "DST", "C", "D", "g2"),
            ("b_dst", "DST", "B", "A", "g1")]
    pos = {r[0]: r[1] for r in rows}; team = {r[0]: r[2] for r in rows}; opp = {r[0]: r[3] for r in rows}; game = {r[0]: r[4] for r in rows}
    return pos, team, opp, game


def test_shape_check_counts_as_the_lab_constrains():
    pos, team, opp, game = _maps()
    v = lambda ids, cell: M.shape_violations(ids, cell, pos, team, opp, game)       # noqa: E731
    house = ["a_qb", "a_wr1", "a_wr2", "b_wr", "c_rb", "e_rb", "d_wr", "f_wr", "c_dst"]
    assert v(house, "A1") == [] and v(house, None) == []
    assert v(house, "A2") == ["1 bring-backs > 0"]
    b_row = ["a_qb", "a_wr1", "b_wr", "c_wr", "d_te", "e_rb", "c_rb", "f_wr", "c_dst"]     # QB+1, bb 1, 3 in g1, pair g2
    assert v(b_row, "B") == []
    assert "3 stack mates > 1" in v(["a_qb", "a_wr1", "a_wr2", "a_te", "b_wr", "c_wr", "d_te", "e_rb", "c_dst"], "B")
    assert "no second-game pair" in v(["a_qb", "a_wr1", "b_wr", "c_wr", "c_rb", "e_rb", "e_wr", "a_rb", "c_dst"], "B")
    assert "4 players from the QB's game > 3" in v(["a_qb", "a_wr1", "b_wr", "b_rb", "c_wr", "d_te", "e_rb", "f_wr", "c_dst"], "B")
    c_row = ["a_qb", "a_wr1", "c_wr", "d_te", "e_rb", "c_rb", "f_wr", "e_wr", "c_dst"]       # QB+1, no bring-back
    assert v(c_row, "C") == [] and "0 bring-backs < 1" in v(c_row, "A1")
    assert "an RB faces the lineup's DST" in v(["a_qb", "a_wr1", "a_wr2", "b_wr", "a_rb", "e_rb", "d_wr", "f_wr", "b_dst"], "A1")
    assert v(["a_qb", "a_wr1", "a_wr2", "b_wr", "c_rb", "c_rb2", "d_wr", "f_wr", "e_wr"], "A1") == ["two RBs of one team"]


# ---------------------------------------------------------------- mix_rows vs study 18's mix_book, one stand-in solver
@dataclasses.dataclass
class StackRules:                                   # the pinned lab's fields (nfl2.core.lineup @ f69598b)
    qb_stack_min: int = 1
    bring_back_min: int = 0
    forbid_rb_vs_dst: bool = True
    forbid_two_rb_same_team: bool = True
    qb_stack_max: int | None = None
    bring_back_max: int | None = None
    require_rb_vs_dst: bool = False
    require_two_rb_same_team: bool = False


class LU:
    def __init__(self, players):
        self.players = players

    @property
    def ids(self):
        return frozenset(p["id"] for p in self.players)


def _stand_in(calls):
    """Deterministic: the 9 best non-banned players by the objective, shifted by the number of earlier lineups so rows
    differ; cell C (qb max 1, bring-back max 0) fails on every 4th of its calls (exercises the pass to A1)."""
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None):
        calls.append({"stack": dataclasses.asdict(stack), "objective_col": objective_col, "pair": second_game_pair,
                      "qmax": qb_game_max, "bans": sorted(bans or ()), "n_prev": len(banned_lineups), "env": dict(sorted(env.items())),
                      "max_overlap": max_overlap})
        if stack.qb_stack_max == 1 and stack.bring_back_max == 0:
            n_c = sum(1 for c in calls if c["stack"]["qb_stack_max"] == 1 and c["stack"]["bring_back_max"] == 0)
            if n_c % 4 == 0:
                return None
        order = sorted((p for p in pool if not bans or p["id"] not in bans), key=lambda p: (-p[objective_col], str(p["id"])))
        if len(order) < 9:
            return None
        off = len(banned_lineups) % len(order)
        return LU([order[(off + j) % len(order)] for j in range(9)])
    return optimize


def _install(monkeypatch, calls):
    lineup = types.ModuleType("nfl2.core.lineup"); lineup.optimize = _stand_in(calls); lineup.StackRules = StackRules
    for name, mod in (("nfl2", types.ModuleType("nfl2")), ("nfl2.core", types.ModuleType("nfl2.core")), ("nfl2.core.lineup", lineup)):
        monkeypatch.setitem(sys.modules, name, mod)
    return lineup


def _frame(n=40):
    rows = []
    for k in range(n):
        g = f"g{k % 4}"
        rows.append({"id": f"p{k}", "name": f"P{k}", "pos": ["QB", "RB", "WR", "WR", "TE"][k % 5], "team": f"T{k % 8}",
                     "opp": f"T{(k % 8) ^ 1}", "salary": 5000 + 37 * k, "game_id": g, "mean_projection": 30.0 - 0.5 * k})
    for t in range(8):
        rows.append({"id": f"d{t}", "name": f"D{t}", "pos": "DST", "team": f"T{t}", "opp": f"T{t ^ 1}", "salary": 3000,
                     "game_id": f"g{t % 4}", "mean_projection": 5.0 + 0.1 * t})
    return pd.DataFrame(rows)


# study 18's code, VERBATIM apart from the imports and its frame record shape (nfl2 experiments/s18_stack_shapes.py @
# 5869a1b: CELLS, Builder, pair_games (game_ranks' keys = the frame's skill game ids), allocate, interleave, mix_book)
def _s18_mix_book(fr, base, lam, weights, k, optimize, MAIN_CAP, DST_CAP, MAX_SHARED):
    CELLS = {n: (q, StackRules(**r), qm, w) for n, (q, r, qm, w) in M.MIX_CELLS.items()}

    class Builder:
        def __init__(self, fr, base, lam):
            self.recs = fr.assign(obj=base).to_dict("records")
            self.base = [float(b) for b in base]
            self.lam = float(lam)
            self.dst = {p["id"] for p in self.recs if str(p["pos"]) == "DST"}
            self.prev = []
            self.count = Counter()

        def solve(self, stack, qb_game_max, pair):
            if self.lam:
                for p, b in zip(self.recs, self.base):
                    p["obj"] = b - self.lam * self.count.get(p["id"], 0)
            bans = {p for p, c in self.count.items() if c >= MAIN_CAP} | {p for p, c in self.count.items() if p in self.dst and c >= DST_CAP}
            lu = optimize(self.recs, stack=stack, objective_col="obj", banned_lineups=self.prev, max_overlap=MAX_SHARED,
                          bans=bans or None, env={"MAX_PER_GAME": "4", "MIN_LINEUP_SALARY": "49000"},
                          second_game_pair=pair, qb_game_max=qb_game_max)
            if lu is not None:
                self.prev.append(lu.ids); self.count.update(lu.ids)
            return lu

    def pair_games(fr, which):
        if which is None:
            return None
        return sorted(fr[fr.pos != "DST"].game_id.astype(str).unique())

    names = list(CELLS)
    target = M.allocate([CELLS[n][0] for n in names], k)
    b = Builder(fr, base, lam)
    rows = {n: [] for n in names}
    passes = 0
    for i in sorted(range(len(names)), key=lambda i: (-target[i], i)):
        name = names[i]
        _, stack, qmax, which = CELLS[name]
        pair = pair_games(fr, which)
        for _ in range(target[i]):
            lu = b.solve(stack, qmax, pair)
            cell = name
            if lu is None:
                passes += 1; cell = "A1"
                _, s1, q1, w1 = CELLS["A1"]
                lu = b.solve(s1, q1, pair_games(fr, w1))
            if lu is None:
                break
            rows[cell].append(lu)
    got = [len(rows[n]) for n in names]
    seq = M.interleave(got, [CELLS[n][0] for n in names], weights)
    pos = [0] * len(names); book, cell_of = [], []
    for j in seq:
        book.append(rows[names[j]][pos[j]]); cell_of.append(names[j]); pos[j] += 1
    return book, cell_of, passes


def test_mix_rows_equals_study_18s_mix_book_row_for_row(monkeypatch):
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    prod_calls, s18_calls = [], []
    _install(monkeypatch, prod_calls)
    rows, cells, meta = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5)
    book, cell_of, passes = _s18_mix_book(fr, fr.mean_projection.to_numpy(), 0.0, weights, k, _stand_in(s18_calls), 10, 5, 7)
    assert [frozenset(r) for r in rows] == [lu.ids for lu in book] and cells == cell_of
    assert meta["passes_to_A1"] == passes > 0                             # the stand-in made C pass to A1
    strip = lambda cs: [{x: c[x] for x in ("stack", "pair", "qmax", "bans", "n_prev", "env", "max_overlap")} for c in cs]  # noqa: E731
    assert strip(prod_calls) == strip(s18_calls)                          # the same constraints, call by call
    assert [c["objective_col"] for c in prod_calls] == ["proj"] * len(prod_calls)
    assert meta["cells"]["A1"]["target_rows"] == 6 and sum(v["rows"] for v in meta["cells"].values()) == k
    assert {c["pair"] is not None for c in prod_calls if c["stack"]["qb_stack_max"] == 1 and c["stack"]["bring_back_min"] == 1} == {True}


def test_with_the_term_only_the_objective_differs(monkeypatch):
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    plain, term = [], []
    _install(monkeypatch, plain)
    r0, c0, _ = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5)
    _install(monkeypatch, term)
    bonus = {f"p{j}": 1.0 for j in range(40)}                             # a constant term keeps the order, so the rows match
    r1, c1, _ = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, bonus=bonus)
    assert r0 == r1 and c0 == c1
    strip = lambda cs: [{x: c[x] for x in ("stack", "pair", "qmax", "bans", "n_prev", "env", "max_overlap")} for c in cs]  # noqa: E731
    assert strip(plain) == strip(term)
    assert {c["objective_col"] for c in plain} == {"proj"} and {c["objective_col"] for c in term} == {"obj"}


def test_mix_rows_orders_by_the_interleave_and_reports_entry_shares(monkeypatch):
    fr = _frame(); weights = W_DRAFT_A[:21]
    _install(monkeypatch, [])
    rows, cells, meta = ur.mix_rows(fr, set(), 21, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5)
    assert len(rows) == 21 == len(cells) and set(cells) <= set(M.MIX_CELLS)
    shares = meta["entry_shares_before_overlap_limit"]
    assert abs(sum(shares.values()) - 1) < 1e-9


def test_a_player_without_a_game_id_fails_the_check():
    pos, team, opp, game = _maps()
    b_row = ["a_qb", "a_wr1", "b_wr", "c_wr", "d_te", "e_rb", "c_rb", "f_wr", "c_dst"]
    g2 = dict(game); g2.pop("c_wr"); g2["d_te"] = None
    v = M.shape_violations(b_row, "B", pos, team, opp, g2)
    assert len(v) == 1 and v[0].startswith("players without a game id")
