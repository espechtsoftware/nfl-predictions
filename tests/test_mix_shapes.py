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
    rows, cells, meta, _ = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5)
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
    r0, c0, _, _ = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5)
    _install(monkeypatch, term)
    bonus = {f"p{j}": 1.0 for j in range(40)}                             # a constant term keeps the order, so the rows match
    r1, c1, _, _ = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, bonus=bonus)
    assert r0 == r1 and c0 == c1
    strip = lambda cs: [{x: c[x] for x in ("stack", "pair", "qmax", "bans", "n_prev", "env", "max_overlap")} for c in cs]  # noqa: E731
    assert strip(plain) == strip(term)
    assert {c["objective_col"] for c in plain} == {"proj"} and {c["objective_col"] for c in term} == {"obj"}


def test_mix_rows_orders_by_the_interleave_and_reports_entry_shares(monkeypatch):
    fr = _frame(); weights = W_DRAFT_A[:21]
    _install(monkeypatch, [])
    rows, cells, meta, _ = ur.mix_rows(fr, set(), 21, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5)
    assert len(rows) == 21 == len(cells) and set(cells) <= set(M.MIX_CELLS)
    shares = meta["entry_shares_before_overlap_limit"]
    assert abs(sum(shares.values()) - 1) < 1e-9


def test_a_player_without_a_game_id_fails_the_check():
    pos, team, opp, game = _maps()
    b_row = ["a_qb", "a_wr1", "b_wr", "c_wr", "d_te", "e_rb", "c_rb", "f_wr", "c_dst"]
    g2 = dict(game); g2.pop("c_wr"); g2["d_te"] = None
    v = M.shape_violations(b_row, "B", pos, team, opp, g2)
    assert len(v) == 1 and v[0].startswith("players without a game id")


def test_book_cells_resolve_every_main_row_or_refuse_loudly():
    """vet_replace (reviewer 10-05): a MIX main row whose cell cannot be resolved must never be vetted as house."""
    r1, r2, r3, sleeve = (frozenset({f"{x}{i}" for i in range(9)}) for x in "abcd")
    tagged = [(r1, "mix_B"), (r2, "mix_C"), (r2, "mix_C"), (r3, "lev"), (sleeve, "lev")]
    assert M.book_cells([r1, r2, sleeve], tagged + [(r3, "mix_A2")], k_main=2) == ["B", "C", None]   # the sleeve may be untagged
    with pytest.raises(ValueError, match=r"MIX ROWS WITHOUT A CELL TAG: main-block positions \[2\]"):
        M.book_cells([r1, r3, sleeve], tagged, k_main=2)                      # r3 is in the book's main block, untagged
    with pytest.raises(ValueError, match=r"positions \[1, 2\]"):
        M.book_cells([frozenset({"x"}), frozenset({"y"})], tagged, k_main=2)  # rows missing from the candidates entirely


def test_vet_replace_refuses_an_unresolved_mix_book_before_vetting():
    text = (Path(__file__).resolve().parents[1] / "scripts" / "vet_replace_v4.py").read_text()
    assert "cell_at = dict(enumerate(book_cells([frozenset(r) for r in book], _tagged, _k_main)))" in text
    assert 'print(f"REPLACEMENT FAILED: {e}", file=sys.stderr); sys.exit(2)' in text


# ---------------------------------------------------------------- WS (study 18's arm that PASSED, Addendum 129)
def _s18_whole_book(fr, base, lam, shape, k, optimize, MAIN_CAP, DST_CAP, MAX_SHARED):
    """study 18's whole_book with its Builder, VERBATIM apart from the imports (nfl2 experiments/s18_stack_shapes.py @ 5869a1b)."""
    recs = fr.assign(obj=base).to_dict("records"); dst = {p["id"] for p in recs if str(p["pos"]) == "DST"}
    prev, count, out = [], Counter(), []
    stack, qmax, which = shape
    pair = None if which is None else sorted(fr[fr.pos != "DST"].game_id.astype(str).unique())
    for _ in range(k):
        bans = {p for p, c in count.items() if c >= MAIN_CAP} | {p for p, c in count.items() if p in dst and c >= DST_CAP}
        lu = optimize(recs, stack=stack, objective_col="obj", banned_lineups=prev, max_overlap=MAX_SHARED, bans=bans or None,
                      env={"MAX_PER_GAME": "4", "MIN_LINEUP_SALARY": "49000"}, second_game_pair=pair, qb_game_max=qmax)
        if lu is None:
            break
        prev.append(lu.ids); count.update(lu.ids); out.append(lu)
    return out


def test_ws_portfolio_equals_study_18s_whole_book_ws(monkeypatch):
    assert M.PORTFOLIOS["ws"] == {"WS": (1.0, {"qb_stack_min": 1, "bring_back_min": 0}, 3, "all")}
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    prod_calls, s18_calls = [], []
    _install(monkeypatch, prod_calls)
    rows, cells, meta, _ = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, portfolio="ws")
    WS = (StackRules(qb_stack_min=1, bring_back_min=0), 3, "all")                          # s18's WS constant
    book = _s18_whole_book(fr, fr.mean_projection.to_numpy(), 0.0, WS, k, _stand_in(s18_calls), 10, 5, 7)
    assert [frozenset(r) for r in rows] == [lu.ids for lu in book] and set(cells) == {"WS"}
    strip = lambda cs: [{x: c[x] for x in ("stack", "pair", "qmax", "bans", "n_prev", "env", "max_overlap")} for c in cs]  # noqa: E731
    assert strip(prod_calls) == strip(s18_calls) and meta["passes_to_A1"] == 0 and meta["portfolio"] == "ws"


def test_ws_tags_and_shape():
    pos, team, opp, game = _maps()
    assert M.cell_of_tag("mix_WS") == "WS"
    b_row = ["a_qb", "a_wr1", "b_wr", "c_wr", "d_te", "e_rb", "c_rb", "f_wr", "c_dst"]     # QB+1, a pair in g2, 3 from g1
    assert M.shape_violations(b_row, "WS", pos, team, opp, game) == []
    no_pair = ["a_qb", "a_wr1", "b_wr", "c_wr", "c_rb", "e_rb", "e_wr", "a_rb", "c_dst"]
    assert "no second-game pair" in M.shape_violations(no_pair, "WS", pos, team, opp, game)
    four = ["a_qb", "a_wr1", "a_wr2", "b_wr", "c_wr", "d_te", "e_rb", "f_wr", "c_dst"]       # 4 from the QB's game
    assert "4 players from the QB's game > 3" in M.shape_violations(four, "WS", pos, team, opp, game)


# ---------------------------------------------------------------- spares (reviewer 2026-10-06, blocking: no house row fits WS)
def test_spares_leave_the_book_unchanged_and_come_after_it(monkeypatch):
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    c0, c1 = [], []
    _install(monkeypatch, c0)
    r0, cells0, m0, s0 = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, portfolio="ws")
    _install(monkeypatch, c1)
    r1, cells1, m1, s1 = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, portfolio="ws", spares=15)
    assert r0 == r1 and cells0 == cells1 and s0 == []                     # the book is solved first, byte-identical
    assert c1[:len(c0)] == c0                                             # the same calls, then the spares' calls
    assert len(s1) == 15 and {c for _, c in s1} == {"WS"} and m1["spares"] == {"requested": 15, "built": 15, "cells": {"WS": 15},
                                                                                "caps_from_book_entries": k}
    book_sets = {frozenset(r) for r in r1}
    assert not any(frozenset(ids) in book_sets for ids, _ in s1)           # never book rows


def test_spares_run_under_the_books_running_caps_from_its_entries(monkeypatch):
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    calls = []
    _install(monkeypatch, calls)
    rows, _, _, spares = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, portfolio="ws", spares=15)
    count = Counter(p for r in rows for p in r)
    for c, (ids, _) in zip(calls[k:], spares):                            # each spare solve bans exactly the players already
        assert set(c["bans"]) >= {p for p, n in count.items() if n >= 10}   # at the book's cap (10 = from the entries, not k + S)
        assert c["n_prev"] == sum(1 for _ in count.elements()) // 9         # every earlier row (book + spares) stays banned
        count.update(ids)


def test_mix_portfolio_spares_follow_the_quotas(monkeypatch):
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    _install(monkeypatch, [])
    _, _, meta, spares = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, spares=10)
    assert len(spares) == 10 and set(meta["spares"]["cells"]) <= set(M.MIX_CELLS)
    assert meta["spares"]["cells"].get("A1", 0) >= 3                      # A1 0.30 of 10, plus any C passes to A1


# ---------------------------------------------------------------- O-35: the interleave weights keep the operator's pins
def test_plan_weights_count_pinned_entries_like_the_deal(tmp_path):
    import json
    """Rev2-like: super-satellites pinned to the top rows. The weights must equal the entries enter_layout deals to each
    rank (pins included), or MIX's cells are allocated against the wrong entry shares."""
    from collections import Counter
    from nfl_dfs.inference import enter_layout as EL
    plan = [{"name": "milly", "contest_id": 1, "entries": 2, "keep": 2},
            *[{"name": f"sat{i}", "contest_id": 10 + i, "entries": 1, "keep": 1} for i in range(6)],
            {"name": "supersat", "contest_id": 30, "entries": 3, "keep": 3, "ranks": [1, 2, 3]},
            {"name": "supersat2", "contest_id": 31, "entries": 3, "keep": 3, "ranks": [1, 2, 3]},
            {"name": "wildcat", "contest_id": 40, "entries": 2, "keep": 2}]
    f = tmp_path / "contests.json"; f.write_text(json.dumps(plan))
    k = EL.rows_needed(plan, "head")
    dealt = Counter(r for rr in EL.assign_ranks(plan, "head") for r in rr)
    w = M.plan_weights(f, k, "head")
    assert w == [dealt[r] for r in range(k)]
    assert w[0] == 4 and sum(w) == sum(c["entries"] for c in plan)        # rank 1: milly, sat0 and both super-sats
    unpinned = tmp_path / "unpinned.json"; unpinned.write_text(json.dumps([{k_: v for k_, v in c.items() if k_ != "ranks"} for c in plan]))
    assert M.plan_weights(unpinned, k, "head") != w                          # stripping the pins changes the weights


def test_plan_weights_refuse_a_pinned_plan_under_a_layout_that_ignores_pins(tmp_path):
    import json
    plan = [{"name": "milly", "contest_id": 1, "entries": 2, "keep": 2},
            {"name": "supersat", "contest_id": 30, "entries": 2, "keep": 2, "ranks": [1, 2]}]
    f = tmp_path / "contests.json"; f.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="pinned contests need the head or spread layout"):
        M.plan_weights(f, 4, "sequential")


def test_the_per_qb_cap_limits_every_qb_and_is_inert_when_off(monkeypatch):
    """Study 35's lever (operator 10-06: QB diversity): with qb_cap, a QB already in qb_cap rows is banned from later solves,
    in the book and the spares alike; without it the book is exactly today's."""
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    _install(monkeypatch, [])
    base, base_cells, _, _ = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5)
    _install(monkeypatch, [])
    off, off_cells, _, _ = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, qb_cap=None)
    assert off == base and off_cells == base_cells                       # inert when off
    qbs = set(fr[fr.pos == "QB"].id)
    top = max(Counter(p for r in base for p in r if p in qbs).values())
    assert top > 3                                                        # the uncapped book concentrates its QBs
    _install(monkeypatch, [])
    capped, _, _, spares = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, qb_cap=3, spares=4)
    used = Counter(p for r in capped + [s for s, _ in spares] for p in r if p in qbs)
    assert len(capped) == k and max(used.values()) <= 3 and len(used) > len(Counter(p for r in base for p in r if p in qbs))


# ---------------------------------------------- study 42 (operator 10-06): the value fill order, best row across cells first
def _cell_valued(calls, rank_of_cell, fail_cells=()):
    """Pure in the state (a peek is repeatable, as the real solver): each cell takes the 9 best non-banned, not-yet-used
    players starting at its own rank offset, so the cells' next rows differ in value by a known amount."""
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None):
        name = next(n for n, (_, r, _, _) in M.MIX_CELLS.items() if dataclasses.asdict(StackRules(**r)) == dataclasses.asdict(stack))
        calls.append({"cell": name, "n_prev": len(banned_lineups), "bans": sorted(bans or ())})
        if name in fail_cells:
            return None
        order = sorted((p for p in pool if not bans or p["id"] not in bans), key=lambda p: (-p[objective_col], str(p["id"])))
        off = (rank_of_cell[name] + len(banned_lineups)) % len(order)
        return LU([order[(off + j) % len(order)] for j in range(9)])
    return optimize


def _install_valued(monkeypatch, calls, rank_of_cell, fail_cells=()):
    lineup = _install(monkeypatch, calls)
    lineup.optimize = _cell_valued(calls, rank_of_cell, fail_cells)


def test_the_default_fill_is_the_group_order_byte_for_byte(monkeypatch):
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    a, b = [], []
    _install(monkeypatch, a)
    r0, c0, m0, s0 = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, spares=5)
    _install(monkeypatch, b)
    r1, c1, m1, s1 = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, spares=5, fill="group")
    assert (r0, c0, s0) == (r1, c1, s1) and a == b and m0["fill"] == "group"
    assert m0["commit_order"][:12] == ["A1"] * 6 + ["B"] * 6                                       # cells consecutively


def test_value_fill_commits_the_highest_objective_next_row(monkeypatch):
    """B's rows are worth most, then C, A1, A2: the value fill commits B until its quota is met, then C, ...; the group
    fill commits A1 first. Every commit is the best of the peeks made on the same state."""
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    rank = {"B": 0, "C": 1, "A1": 2, "A2": 3}
    calls = []
    _install_valued(monkeypatch, calls, rank)
    rows, cells, meta, _ = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, fill="value")
    assert meta["fill"] == "value" and meta["passes_to_A1"] == 0
    assert meta["commit_order"] == ["B"] * 6 + ["C"] * 6 + ["A1"] * 6 + ["A2"] * 3
    assert sorted(cells) == sorted(["A1"] * 6 + ["A2"] * 3 + ["B"] * 6 + ["C"] * 6)            # the quotas are unchanged
    assert [meta["cells"][n]["rows"] for n in ("A1", "A2", "B", "C")] == [6, 3, 6, 6]
    # the first step peeked every cell on the empty state, then committed B
    assert [c["cell"] for c in calls[:4]] == ["A1", "B", "C", "A2"] and {c["n_prev"] for c in calls[:4]} == {0}
    _install_valued(monkeypatch, [], rank)
    _, _, g, _ = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5)
    assert g["commit_order"][:6] == ["A1"] * 6


def test_value_fill_ties_go_to_the_earlier_cell_in_the_group_order(monkeypatch):
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    _install_valued(monkeypatch, [], {"A1": 0, "A2": 0, "B": 0, "C": 0})
    _, _, meta, _ = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, fill="value")
    assert meta["commit_order"] == ["A1"] * 6 + ["B"] * 6 + ["C"] * 6 + ["A2"] * 3


def test_value_fill_passes_a_failing_cells_remaining_quota_to_a1(monkeypatch):
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    _install_valued(monkeypatch, [], {"B": 0, "C": 1, "A1": 2, "A2": 3}, fail_cells=("C",))
    rows, cells, meta, _ = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, fill="value")
    assert meta["passes_to_A1"] == 6 and "C" not in cells and len(rows) == k
    assert [meta["cells"][n]["rows"] for n in ("A1", "A2", "B", "C")] == [12, 3, 6, 0]
    _install_valued(monkeypatch, [], {"B": 0, "C": 1, "A1": 2, "A2": 3}, fail_cells=("A1",))
    rows, cells, meta, _ = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, fill="value")
    assert "A1" not in cells and len(rows) == 15 and meta["passes_to_A1"] == 0                 # A1 itself cannot pass


def test_value_fill_keeps_the_caps_and_the_qb_cap(monkeypatch):
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    _install(monkeypatch, [])
    rows, _, _, spares = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, qb_cap=3, spares=4,
                                     fill="value")
    qbs = set(fr[fr.pos == "QB"].id)
    used = Counter(p for r in rows + [s for s, _ in spares] for p in r)
    assert len(rows) == k and max(used[q] for q in qbs if q in used) <= 3 and max(used.values()) <= 10
    with pytest.raises(ValueError, match="fill must be"):
        ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, fill="best")


def test_value_fill_commits_in_study_42s_scripted_order(monkeypatch):
    """Parity with the lab's study 42 harness (nfl2 production/s42-fill-order-20261006 @ 4541886,
    test_value_fill_commits_the_best_next_row_and_rolls_every_peek_back): cell c's k-th committed row is worth VALUES[c][k];
    at k 10 (A1 3, A2 1, B 3, C 3) the value fill commits exactly the lab's order, B:1 beating A2:0 at the tie of 9."""
    values = {"A1": [8, 7, 6, 5, 4, 3], "B": [10, 9, 4, 3, 2, 1], "C": [5, 5, 5, 5, 5, 5], "A2": [9, 1, 1, 1, 1, 1]}
    fail: tuple = ()

    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None):
        name = next(n for n, (_, r, _, _) in M.MIX_CELLS.items() if dataclasses.asdict(StackRules(**r)) == dataclasses.asdict(stack))
        if name in fail:
            return None
        j = sum(1 for ids in banned_lineups if any(i.startswith(f"{name}:") for i in ids))     # the cell's committed rows
        return LU([{"id": f"{name}:{j}:{s}", objective_col: (values[name][j] if s == 0 else 0.0)} for s in range(9)])

    lineup = _install(monkeypatch, [])
    lineup.optimize = optimize
    rows, cells, meta, _ = ur.mix_rows(_frame(), set(), 10, 7, 4, 49_000, [1] * 10, exposure_cap=10, dst_cap=5, fill="value")
    assert meta["commit_order"] == ["B", "B", "A2", "A1", "A1", "A1", "C", "C", "C", "B"]
    assert sorted(r[0].rsplit(":", 1)[0] for r in rows) == sorted(["B:0", "B:1", "A2:0", "A1:0", "A1:1", "A1:2", "C:0", "C:1",
                                                                  "C:2", "B:2"])
    assert meta["passes_to_A1"] == 0 and [meta["cells"][n]["target_rows"] for n in ("A1", "A2", "B", "C")] == [3, 1, 3, 3]
    fail = ("A2",)                                                        # the lab's test_a_failing_cell_passes_its_quota_to_a1
    _, _, meta, _ = ur.mix_rows(_frame(), set(), 10, 7, 4, 49_000, [1] * 10, exposure_cap=10, dst_cap=5, fill="value")
    assert meta["passes_to_A1"] == 1 and {n: meta["cells"][n]["rows"] for n in meta["cells"]} == {"A1": 4, "A2": 0, "B": 3, "C": 3}


def test_rr_fill_takes_the_cells_in_turn_as_study_42s_harness(monkeypatch):
    """Parity with the lab's test_round_robin_takes_the_cells_in_turn (lab 4541886): at k 10 (A1 3, A2 1, B 3, C 3) the
    round-robin commits A1 B C A2, A1 B C, A1 B C whatever the values; a failing cell passes its remaining quota to A1."""
    values = {"A1": [8, 7, 6, 5, 4, 3], "B": [10, 9, 4, 3, 2, 1], "C": [5, 5, 5, 5, 5, 5], "A2": [9, 1, 1, 1, 1, 1]}
    fail: tuple = ()

    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None):
        name = next(n for n, (_, r, _, _) in M.MIX_CELLS.items() if dataclasses.asdict(StackRules(**r)) == dataclasses.asdict(stack))
        if name in fail:
            return None
        j = sum(1 for ids in banned_lineups if any(i.startswith(f"{name}:") for i in ids))
        return LU([{"id": f"{name}:{j}:{s}", objective_col: (values[name][j] if s == 0 else 0.0)} for s in range(9)])

    lineup = _install(monkeypatch, [])
    lineup.optimize = optimize
    rows, cells, meta, _ = ur.mix_rows(_frame(), set(), 10, 7, 4, 49_000, [1] * 10, exposure_cap=10, dst_cap=5, fill="rr")
    assert meta["fill"] == "rr" and meta["commit_order"] == ["A1", "B", "C", "A2", "A1", "B", "C", "A1", "B", "C"]
    assert sorted(cells) == sorted(["A1"] * 3 + ["A2"] + ["B"] * 3 + ["C"] * 3) and meta["passes_to_A1"] == 0
    fail = ("C",)
    _, _, meta, _ = ur.mix_rows(_frame(), set(), 10, 7, 4, 49_000, [1] * 10, exposure_cap=10, dst_cap=5, fill="rr")
    assert meta["passes_to_A1"] == 3 and {n: meta["cells"][n]["rows"] for n in meta["cells"]} == {"A1": 6, "A2": 1, "B": 3, "C": 0}


def test_rr_fill_keeps_the_caps_and_the_qb_cap(monkeypatch):
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    _install(monkeypatch, [])
    rows, cells, meta, spares = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, qb_cap=3, spares=4,
                                            fill="rr")
    qbs = set(fr[fr.pos == "QB"].id)
    used = Counter(p for r in rows + [s for s, _ in spares] for p in r)
    assert len(rows) == k and max(used[q] for q in qbs if q in used) <= 3 and max(used.values()) <= 10
    assert meta["commit_order"][:4] == ["A1", "B", "C", "A2"]


# ------------------------------------- study 43 (operator 10-06): one A1 row per top-N game by total, built first
def _cover_frame():
    rows = [{"id": q, "name": q, "pos": "QB", "team": f"T{q}", "opp": f"O{q}", "salary": 6000, "game_id": g,
             "mean_projection": v, "game_total": t}
            for q, g, v, t in (("qb_g1", "g1", 7.5, 50.0), ("qb_g2", "g2", 3.0, 48.0), ("qb_g3", "g3", 1.0, 40.0))]
    return pd.DataFrame(rows)


def _cover_stand_in(values, fail_cover=()):
    """Parity with the lab's scripted builder (lab c98be41 tests/test_s43_game_cover.py): cell c's k-th row is ("c:k",)
    worth values[c][k]; an A1 solve that bans every QB but one game's is a coverage row (that QB + "cov:k")."""
    qbs = {"qb_g1": 7.5, "qb_g2": 3.0, "qb_g3": 1.0}

    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None):
        name = next(n for n, (_, r, _, _) in M.MIX_CELLS.items() if dataclasses.asdict(StackRules(**r)) == dataclasses.asdict(stack))
        live = [q for q in qbs if not bans or q not in bans]
        if name == "A1" and len(live) == 1:
            if live[0] in fail_cover:
                return None
            k = sum(1 for ids in banned_lineups if any(i.startswith("cov:") for i in ids))
            return LU([{"id": live[0], objective_col: qbs[live[0]]}, {"id": f"cov:{k}", objective_col: 0.0}])
        k = sum(1 for ids in banned_lineups if any(i.startswith(f"{name}:") for i in ids))
        return LU([{"id": f"{name}:{k}", objective_col: values[name][k]}])
    return optimize


COVER_VALUES = {"A1": [8, 7, 6, 5, 4, 3, 2, 1], "B": [10, 9, 4, 3, 2, 1, 1, 1], "C": [5] * 8, "A2": [9, 1, 1, 1, 1, 1, 1, 1]}


def test_coverage_rows_come_first_count_toward_a1_and_are_ordered_by_value(monkeypatch):
    """The lab's test of the same name, on production's mix_rows: at k 10 (A1 3), covering the top-2 games builds the g1
    then the g2 row first, A1 then takes 1 more, and A1's rows deal by value: A1:0 (8), cov g1 (7.5), cov g2 (3)."""
    lineup = _install(monkeypatch, [])
    lineup.optimize = _cover_stand_in(COVER_VALUES)
    rows, cells, meta, _ = ur.mix_rows(_cover_frame(), set(), 10, 7, 4, 49_000, [1] * 10, exposure_cap=10, dst_cap=5,
                                       cover_games=2)
    assert meta["cover"] == {"games": 2, "ranked": ["g1", "g2"], "covered": ["g1", "g2"], "missed": []}
    assert meta["commit_order"][:2] == ["A1", "A1"] and meta["cells"]["A1"]["rows"] == 3
    a1 = [r for r, c in zip(rows, cells) if c == "A1"]
    assert a1 == [["A1:0"], ["qb_g1", "cov:0"], ["qb_g2", "cov:1"]]


def test_cover_zero_is_todays_book_for_every_fill(monkeypatch):
    fr = _frame(); k = 21; weights = W_DRAFT_A[:k]
    for fill in ("group", "value", "rr"):
        a, b = [], []
        _install(monkeypatch, a)
        r0 = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, spares=5, fill=fill)
        _install(monkeypatch, b)
        r1 = ur.mix_rows(fr, set(), k, 7, 4, 49_000, weights, exposure_cap=10, dst_cap=5, spares=5, fill=fill, cover_games=0)
        assert r0[0] == r1[0] and r0[1] == r1[1] and r0[3] == r1[3] and a == b
        assert r1[2]["cover"] == {"games": 0, "ranked": [], "covered": [], "missed": []}


def test_a_game_that_cannot_be_covered_is_missed_and_the_quota_stays_with_a1(monkeypatch):
    lineup = _install(monkeypatch, [])
    lineup.optimize = _cover_stand_in(COVER_VALUES, fail_cover=("qb_g1",))
    rows, cells, meta, _ = ur.mix_rows(_cover_frame(), set(), 10, 7, 4, 49_000, [1] * 10, exposure_cap=10, dst_cap=5,
                                       cover_games=3, fill="rr")
    assert meta["cover"]["covered"] == ["g2", "g3"] and meta["cover"]["missed"] == ["g1"]
    assert meta["cells"]["A1"]["rows"] == 3 and len(rows) == 10                  # 2 coverage rows + 1 more A1
    lineup.optimize = _cover_stand_in(COVER_VALUES)
    _, _, meta, _ = ur.mix_rows(_cover_frame(), set(), 10, 7, 4, 49_000, [1] * 10, exposure_cap=10, dst_cap=5, cover_games=4)
    assert meta["cover"]["ranked"] == ["g1", "g2", "g3"] and meta["cover"]["missed"] == []   # only 3 games on this slate
    assert meta["cells"]["A1"]["rows"] == 3                                     # A1's 3 rows are all coverage rows


def test_cover_refuses_without_game_total_or_the_mix_portfolio(monkeypatch):
    lineup = _install(monkeypatch, [])
    lineup.optimize = _cover_stand_in(COVER_VALUES)
    with pytest.raises(SystemExit, match="COVER REFUSED"):
        ur.mix_rows(_cover_frame().drop(columns="game_total"), set(), 10, 7, 4, 49_000, [1] * 10, cover_games=2)
    with pytest.raises(ValueError, match="needs the MIX portfolio"):
        ur.mix_rows(_cover_frame(), set(), 10, 7, 4, 49_000, [1] * 10, cover_games=2, portfolio="ws")
