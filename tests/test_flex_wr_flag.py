"""The WR flex flag (union_reselect --mix-flex-wr-rows N; study 75's rule; production's agreed format 10-08): off identical;
the first N BOOK solves in build order hold exactly 4 WRs (member_bounds), an infeasible one is built plain and recorded,
spares never; the refusals; the receipt line and the audit's report; and PARITY with the lab's OWN frozen flex_rows (nfl2
experiments/s75_flex_mix.py @ bb66c2e = the frozen f3c6d0d, pasted byte for byte, its text sha-pinned) on the lab's
term_book: with one position-aware stand-in optimizer reading production's member_bounds (WRs, 4, 4) and the lab's
set_constraints (WRs, ">=", 4) alike (the lab optimizer's own WR <= 4 makes ">= 4" exactly 4), the same rows are ruled and
the SAME LINEUPS result (caps off on both sides, so neither side bans); a wrong bound (3) fails it."""
import importlib.util
import sys
import types
from collections import Counter
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


T71 = _load("t71_helpers_fx", ROOT / "tests" / "test_s71_bring_back_top_wr.py")      # the lab's term_book, stand-ins, audit run


# ---------------------------------------------------------------- a 6-game fixture (12 teams: QB, RB, WR, WR, TE, DST)
def frame() -> pd.DataFrame:
    rows = []
    for t in range(12):
        team, opp, g = f"T{t}", f"T{t ^ 1}", f"g{t // 2}"
        for j, pos in enumerate(("QB", "RB", "WR", "WR", "TE", "DST")):
            pid = f"{team}.{pos}{j}"
            rows.append({"id": pid, "name": pid, "pos": pos, "team": team, "opp": opp, "game_id": g,
                         "salary": 4000 + 100 * ((7 * t + 3 * j) % 40), "mean_projection": 5.0 + ((11 * t + 5 * j) % 23)})
    return pd.DataFrame(rows)


def cheap_term(fr):
    return {i: 2.0 for i, s, p in zip(fr.id, fr.salary, fr.pos) if s < 5500 and p != "DST"}


def pick(pool, obj, n_prev, bans, wr_exact):
    """THE shared stand-in solve: the objective order (ties: id) rotated by the rows committed so far; with wr_exact, exactly
    that many WRs (the first in that order) and the rest non-WR; else the first 9."""
    avail = [p for p in pool if not bans or p["id"] not in bans]
    order = sorted(avail, key=lambda p: (-float(p[obj]), str(p["id"])))
    off = n_prev % len(order)
    rot = order[off:] + order[:off]
    if wr_exact is None:
        return rot[:9]
    return [p for p in rot if p["pos"] == "WR"][:wr_exact] + [p for p in rot if p["pos"] != "WR"][:9 - wr_exact]


class Fail:
    """Which bounded solves report infeasible: every `every`-th (None = never)."""
    def __init__(self, every=None):
        self.every, self.n = every, 0

    def __call__(self) -> bool:
        self.n += 1
        return bool(self.every) and self.n % self.every == 0


def production_opt(calls, fail):
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None,
                 member_bounds=None, interaction_floor_weights=None, interaction_floor=None):
        calls.append({"member_bounds": member_bounds})
        exact = None
        if member_bounds:
            ids, lo, hi = member_bounds[0]
            assert lo == hi and set(ids) == {p["id"] for p in pool if p["pos"] == "WR"}
            exact = lo
            if fail():
                return None
        return T71.LU(pick(pool, objective_col, len(banned_lineups), bans, exact))
    return optimize


def build(monkeypatch, n, fr=None, fail_every=None, term=True, caps=True, spares=15):
    calls = []
    T71._install(monkeypatch, calls, production_opt(calls, Fail(fail_every)))
    fr = frame() if fr is None else fr
    kw = dict(exposure_cap=13 if caps else None, dst_cap=6 if caps else None, fill="rr", spares=spares, flex_wr_rows=n)
    if term:
        kw.update(term_rows=8, term_bonus=cheap_term(fr))
    rows, cells, meta, sp = ur.mix_rows(fr, set(), 26, 4, 4, 49_000, [3, 3] + [1] * 24, **kw)
    return rows, cells, meta, sp, calls


def wr_count(row, fr):
    pos = dict(zip(fr.id, fr.pos))
    return sum(1 for i in row if pos[i] == "WR")


# ---------------------------------------------------------------- production behaviour
def test_off_is_the_old_call_exactly(monkeypatch):
    a = build(monkeypatch, 0)
    calls = []
    T71._install(monkeypatch, calls, production_opt(calls, Fail()))
    fr = frame()
    b = ur.mix_rows(fr, set(), 26, 4, 4, 49_000, [3, 3] + [1] * 24, exposure_cap=13, dst_cap=6, fill="rr", spares=15,
                    term_rows=8, term_bonus=cheap_term(fr))
    assert a[:4] == b and a[4] == calls and "flex_wr" not in a[2] and all(c["member_bounds"] is None for c in calls)


@pytest.mark.parametrize("n", [8, 3])
def test_the_first_n_book_solves_hold_four_wrs(monkeypatch, n):
    rows, cells, meta, spares, calls = build(monkeypatch, n)
    fx = meta["flex_wr"]
    assert fx["rows_cap"] == n and fx["plain"] == [] and fx["wr_ids_n"] == 24
    assert [j for _, j in fx["ruled"]] == list(range(n))                                   # build order, any cell
    order = meta["commit_order"]
    assert [c for c, _ in fx["ruled"]] == [x.split(":")[-1] for x in order[:n]]
    assert sum(1 for c in calls if c["member_bounds"]) == n                                 # never on a spare
    fr = frame()
    assert sum(1 for r in rows if wr_count(r, fr) == 4) >= n                                # every ruled row holds 4 WRs
    assert ur.flex_wr_line(fx) == f"FLEX WR: {n} rows; ruled {n}, plain 0"


def test_an_infeasible_ruled_solve_is_built_plain_and_never_retried(monkeypatch):
    rows, cells, meta, spares, calls = build(monkeypatch, 8, fail_every=3)
    fx = meta["flex_wr"]
    assert [j for _, j in fx["plain"]] == [2, 5] and len(fx["ruled"]) == 6                 # the 3rd and 6th attempts failed
    assert sorted([j for _, j in fx["ruled"]] + [j for _, j in fx["plain"]]) == list(range(8))
    assert sum(1 for c in calls if c["member_bounds"]) == 8                                 # one bounded attempt per solve
    assert ur.flex_wr_line(fx) == "FLEX WR: 8 rows; ruled 6, plain 2"


def test_every_book_row_with_n_equal_k_and_never_a_spare(monkeypatch):
    rows, cells, meta, spares, calls = build(monkeypatch, 26)
    fr = frame()
    assert len(meta["flex_wr"]["ruled"]) == 26 and all(wr_count(r, fr) == 4 for r in rows)
    assert sum(1 for c in calls if c["member_bounds"]) == 26


@pytest.mark.parametrize("kw, msg", [(dict(flex_wr_rows=-1), "0 <= N"), (dict(flex_wr_rows=27), "0 <= N"),
                                     (dict(flex_wr_rows=4, fill="group"), "fill rr"), (dict(flex_wr_rows=4, cover_games=2), "no cover")])
def test_mix_rows_refusals(monkeypatch, kw, msg):
    T71._install(monkeypatch, [])
    args = dict(exposure_cap=13, dst_cap=6, fill="rr", spares=0); args.update(kw)
    with pytest.raises(ValueError, match=msg):
        ur.mix_rows(frame(), set(), 26, 4, 4, 49_000, [1] * 26, **args)


@pytest.mark.parametrize("args, ok", [((0, "pmo_x50", None, "group", 0, 0, 26), True), ((8, "mix", "mix", "rr", 0, 0, 26), True),
                                      ((26, "mix", "mix", "rr", 0, 0, 26), True), ((27, "mix", "mix", "rr", 0, 0, 26), False),
                                      ((-1, "mix", "mix", "rr", 0, 0, 26), False), ((8, "pmo_x50", None, "rr", 0, 0, 26), False),
                                      ((8, "mix", "mix", "value", 0, 0, 26), False), ((8, "mix", "mix", "rr", 3, 0, 26), False),
                                      ((8, "mix", "mix", "rr", 0, 6, 26), False)])
def test_the_switch_parses_and_refuses(args, ok):
    if ok:
        assert ur.parse_flex_wr_rows(*args) == args[0]
    else:
        with pytest.raises(SystemExit, match="--mix-flex-wr-rows"):
            ur.parse_flex_wr_rows(*args)


def test_the_audit_reports_the_flag(tmp_path):
    row = ["AQB", "AWR1", "BRB1", "CRB0", "DWR0", "CWR2", "DTE", "EWR1", "G_DST"]
    on = {"config": {"union": {"mix": {"mix": {"flex_wr": {"rows_cap": 8, "ruled": [["A1", 0]] * 7, "plain": [["B", 1]], "wr_ids_n": 40}}}}}}
    res = T71._audit_run(tmp_path / "on", row, "mix_A1", on)
    c = next(x for x in res["checks"] if x["check"] == "flex_wr")
    assert c["ok"] and c["rows_cap"] == 8 and c["ruled"] == 7 and c["plain"] == 1 and "--mix-flex-wr-rows 8" in c["detail"]
    off = next(x for x in T71._audit_run(tmp_path / "off", row, "mix_A1", {})["checks"] if x["check"] == "flex_wr")
    assert off["ok"] and off["rows_cap"] == 0 and off["detail"] == "--mix-flex-wr-rows off"


# ---------------------------------------------------------------- parity with the lab's OWN frozen flex_rows
S24, S18 = T71.S24, T71.S18
FLEX_ROWS_TEXT_SHA256 = "2e397346ba50c8e4fb4f8ef12af2aca8dea1c18497955762f96f2f2c87aa1091"


@contextmanager
def flex_rows(rule: tuple[str, str, int], n_rows: int, k_book: int):
    """Wrap the current S24.CapBuilder (inside S37.built_with): every solve with j < min(n_rows, k_book) carries the lab
    optimizer's set_constraints [(the builder's `rule[0]` ids, sense, k)]; infeasible -> the plain solve, recorded.
    Yields the class (`ruled` / `plain` lists of (cell, j); `ruled_ids` lineups)."""
    orig_cls, orig_opt = S24.CapBuilder, S24.optimize
    target = {id(S18.CELLS[c][1]): c for c in S18.CELLS}
    position, sense, bound = rule

    class FlexBuilder(orig_cls):
        ruled: list = []
        plain: list = []
        ruled_ids: list = []

        def solve_with(self, stack, qb_game_max, pair, extra_bans: set):
            j = len(self.prev)
            if j >= min(n_rows, k_book):
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            cell = target.get(id(stack), "?")
            ids = [str(p["id"]) for p in self.recs if str(p["pos"]) == position]
            S24.optimize = partial(orig_opt, set_constraints=[(ids, sense, bound)])
            try:
                lu = super().solve_with(stack, qb_game_max, pair, extra_bans)
            finally:
                S24.optimize = orig_opt
            if lu is not None:
                type(self).ruled.append((cell, j)); type(self).ruled_ids.append(sorted(str(x) for x in lu.ids))
                return lu
            type(self).plain.append((cell, j))
            return super().solve_with(stack, qb_game_max, pair, extra_bans)

    FlexBuilder.ruled, FlexBuilder.plain, FlexBuilder.ruled_ids = [], [], []
    S24.CapBuilder = FlexBuilder
    try:
        yield FlexBuilder
    finally:
        S24.CapBuilder, S24.optimize = orig_cls, orig_opt


def test_the_vendored_flex_rows_text_is_the_labs():
    import ast
    import hashlib
    src = (ROOT / "tests" / "test_flex_wr_flag.py").read_text()
    lines = src.splitlines(keepends=True)
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "flex_rows")
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    assert hashlib.sha256("".join(lines[start - 1:node.end_lineno]).encode()).hexdigest() == FLEX_ROWS_TEXT_SHA256


class _HLU:
    def __init__(self, ids):
        self.ids = ids


class _FlexHCap:
    """S24.CapBuilder's contract (solve_with commits a solved row) with the frame's records, so the lab's flex_rows can read
    each player's pos; no caps (production's run below has its caps off too)."""
    last = None

    def __init__(self, fr, base, lam, main_cap, dst_cap):
        self.recs = fr.assign(obj=0.0).to_dict("records")
        self.prev, self.count, self.log = [], Counter(), []
        _FlexHCap.last = self

    def solve_with(self, stack, qb_game_max, pair, extra_bans):
        lu = S24.optimize(self.recs, stack=stack, banned_lineups=self.prev)
        if lu is not None:
            self.prev.append(lu.ids); self.count.update(lu.ids); self.log.append((stack.cell, len(self.prev) - 1))
        return lu


def harness_opt(fail):
    def optimize(recs, stack, banned_lineups, set_constraints=None):
        exact = None
        if set_constraints:
            ids, sense, bound = set_constraints[0]
            assert set(ids) == {str(p["id"]) for p in recs if p["pos"] == "WR"}
            if sense == ">=" and bound >= 4:                     # the lab optimizer's own WR 3..4: ">= 4" is exactly 4
                exact = 4
            elif sense == "<=" and bound <= 3:
                exact = 3
            if fail():
                return None
        return _HLU(tuple(str(p["id"]) for p in pick(recs, "obj", len(banned_lineups), None, exact)))
    return optimize


def harness(monkeypatch, n, rule=("WR", ">=", 4), fail_every=None):
    fr = frame()
    term = cheap_term(fr)
    monkeypatch.setattr(T71.S24, "CapBuilder", _FlexHCap)
    T71.S24.optimize = harness_opt(Fail(fail_every))
    base = fr.mean_projection.astype(float).tolist()
    with flex_rows(rule, n, 26) as T:
        book, cells, meta = T71.term_book(fr, base, [term.get(i, 0.0) for i in fr.id], (13, 6), [3, 3] + [1] * 24, 26, 8, 41)
    return [sorted(lu.ids) for lu in book], list(T.ruled), list(T.plain)


def production(monkeypatch, n, fail_every=None):
    rows, cells, meta, spares, _ = build(monkeypatch, n, fail_every=fail_every, caps=False)
    fx = meta["flex_wr"]
    return ([sorted(r) for r in rows] + [sorted(ids) for ids, _ in spares], [tuple(x) for x in fx["ruled"]],
            [tuple(x) for x in fx["plain"]])


@pytest.mark.parametrize("n, fail_every", [(8, None), (3, None), (8, 3), (26, None)])
def test_parity_same_rows_ruled_and_the_same_lineups(monkeypatch, n, fail_every):
    lineups_h, ruled_h, plain_h = harness(monkeypatch, n, fail_every=fail_every)
    lineups_p, ruled_p, plain_p = production(monkeypatch, n, fail_every=fail_every)
    assert ruled_p == ruled_h and plain_p == plain_h                                        # the same (cell, j)
    assert lineups_p == lineups_h and len(lineups_p) == 41                                  # the same 26 book rows + 15 spares
    fr = frame()
    assert sum(1 for r in lineups_p[:26] if wr_count(r, fr) == 4) >= len(ruled_p)


def test_parity_detects_a_wrong_bound(monkeypatch):
    """The mutation check (production's request): a bound of 3 (the lab's own floor, so a no-op there) gives other lineups."""
    lineups_h, ruled_h, _ = harness(monkeypatch, 8, rule=("WR", "<=", 3))
    lineups_p, ruled_p, _ = production(monkeypatch, 8)
    assert ruled_p == ruled_h and lineups_p != lineups_h
