"""The one-catcher flag (union_reselect --mix-one-catcher-rows N; study 79's ONEPC rule; production's agreed format 10-09): off
identical; the first N BOOK solves of B / C in build order hold at most ONE WR / TE of every team (member_bounds (team T's
WR / TE, 0, 1) for every team), an infeasible one is built plain and recorded, spares never; the rows keep their B / C
cells; the refusals (other row rules included); the record check; the receipt line and the audit's identity check; and
PARITY with the lab's OWN frozen one_catcher (nfl2 experiments/s79_nopairs.py @ a51d4238, module d48790cf, pasted byte for
byte, its text sha-pinned) on the lab's term_book: one team-aware stand-in optimizer reading production's member_bounds and
the lab's set_constraints alike, the same (cell, j) ruled / plain and the SAME 41 lineups; a bound of 2 fails it."""
import ast
import hashlib
import importlib.util
import sys
from collections import Counter
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402
from nfl_dfs.inference import mix_shapes as M  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


T71 = _load("t71_helpers_oc", ROOT / "tests" / "test_s71_bring_back_top_wr.py")      # the lab's term_book, stand-ins, audit run
W = [3, 3] + [1] * 24
Q = [c[0] for c in M.MIX_CELLS.values()]


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


def pick(pool, obj, n_prev, bans, per_team):
    """THE shared stand-in solve: the objective order (ties: id) rotated by the rows committed so far; with per_team, the
    first 9 in that order skipping a WR / TE whose team already holds per_team of them; else the first 9."""
    avail = [p for p in pool if not bans or p["id"] not in bans]
    order = sorted(avail, key=lambda p: (-float(p[obj]), str(p["id"])))
    off = n_prev % len(order)
    rot = order[off:] + order[:off]
    if per_team is None:
        return rot[:9]
    out, held = [], Counter()
    for p in rot:
        if p["pos"] in ("WR", "TE"):
            if held[p["team"]] >= per_team:
                continue
            held[p["team"]] += 1
        out.append(p)
        if len(out) == 9:
            break
    return out


class Fail:
    """Which bounded solves report infeasible: every `every`-th (None = never)."""
    def __init__(self, every=None):
        self.every, self.n = every, 0

    def __call__(self) -> bool:
        self.n += 1
        return bool(self.every) and self.n % self.every == 0


def _teams_of(pool):
    t: dict = {}
    for p in pool:
        if p["pos"] in ("WR", "TE"):
            t.setdefault(str(p["team"]), set()).add(str(p["id"]))
    return t


def production_opt(calls, fail):
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None,
                 member_bounds=None, interaction_floor_weights=None, interaction_floor=None):
        cell = next(n for n, (_, r, _, _) in M.MIX_CELLS.items() if all(getattr(stack, f) == v for f, v in r.items()))
        calls.append({"cell": cell, "bounded": member_bounds is not None, "j": len(banned_lineups)})
        per = None
        if member_bounds is not None:
            assert {frozenset(ids) for ids, _, _ in member_bounds} == {frozenset(v) for v in _teams_of(pool).values()}
            assert {(lo, hi) for _, lo, hi in member_bounds} == {(0, 1)}
            per = 1
            if fail():
                return None
        return T71.LU(pick(pool, objective_col, len(banned_lineups), bans, per))
    return optimize


def build(monkeypatch, n, fail_every=None, term=True, caps=True, spares=15, **extra):
    calls = []
    T71._install(monkeypatch, calls, production_opt(calls, Fail(fail_every)))
    fr = frame()
    kw = dict(exposure_cap=13 if caps else None, dst_cap=6 if caps else None, fill="rr", spares=spares, one_catcher_rows=n)
    if term:
        kw.update(term_rows=8, term_bonus=cheap_term(fr))
    kw.update(extra)
    rows, cells, meta, sp = ur.mix_rows(fr, set(), 26, 4, 4, 49_000, W, **kw)
    return rows, cells, meta, sp, calls


def max_per_team(row, fr):
    pos, team = dict(zip(fr.id, fr.pos)), dict(zip(fr.id, fr.team))
    return max(Counter(team[i] for i in row if pos[i] in ("WR", "TE")).values() or [0])


# ---------------------------------------------------------------- production behaviour
@pytest.mark.parametrize("term", [True, False])
def test_off_is_the_old_call_exactly(monkeypatch, term):
    """The known-answer gate: N = 0 is the call without the argument, byte for byte (rows, cells, meta, spares and every
    optimizer call)."""
    a = build(monkeypatch, 0, term=term)
    calls = []
    T71._install(monkeypatch, calls, production_opt(calls, Fail()))
    fr = frame()
    kw = dict(exposure_cap=13, dst_cap=6, fill="rr", spares=15)
    if term:
        kw.update(term_rows=8, term_bonus=cheap_term(fr))
    b = ur.mix_rows(fr, set(), 26, 4, 4, 49_000, W, **kw)
    assert a[:4] == b and a[4] == calls and "one_catcher" not in a[2] and not any(c["bounded"] for c in calls)


@pytest.mark.parametrize("term", [True, False])
@pytest.mark.parametrize("n", [8, 3, 14])
def test_the_first_n_b_c_book_solves_hold_one_catcher_per_team(monkeypatch, n, term):
    rows, cells, meta, spares, calls = build(monkeypatch, n, term=term)
    _, off_cells, _, _, _ = build(monkeypatch, 0, term=term)
    oc = meta["one_catcher"]
    assert oc["rows_cap"] == n and oc["plain"] == [] and oc["cells"] == ["B", "C"] and oc["max_per_team"] == 1 and oc["teams"] == 12
    bc = [(c.split(":")[-1], j) for j, c in enumerate(meta["commit_order"]) if c.split(":")[-1] in ("B", "C")]
    assert [tuple(x) for x in oc["ruled"]] == bc[:n]                                        # the first n B / C solves, build order
    assert [b["commit_index"] for b in oc["ruled_rows"]] == [j for _, j in bc[:n]]
    assert sum(1 for c in calls if c["bounded"]) == n and all(c["j"] < 26 and c["cell"] in ("B", "C") for c in calls if c["bounded"])
    fr = frame()
    ruled = {frozenset(b["row"]) for b in oc["ruled_rows"]}
    assert ruled <= {frozenset(r) for r in rows}                                           # book rows
    assert all(max_per_team(sorted(r), fr) <= 1 for r in ruled)
    assert all(b["row_sha256"] == hashlib.sha256(",".join(b["row"]).encode()).hexdigest() for b in oc["ruled_rows"])
    assert cells == off_cells                                                              # the cells and positions are unchanged
    assert ur.one_catcher_line(oc) == f"ONE CATCHER: {n} rows; ruled {n}, plain 0"


def test_an_infeasible_ruled_solve_is_built_plain_and_the_slot_counts(monkeypatch):
    rows, cells, meta, spares, calls = build(monkeypatch, 8, fail_every=3)
    oc = meta["one_catcher"]
    bc = [j for j, c in enumerate(meta["commit_order"]) if c.split(":")[-1] in ("B", "C")]
    assert [j for _, j in oc["plain"]] == [bc[2], bc[5]] and len(oc["ruled"]) == 6          # the 3rd and 6th attempts failed
    assert sorted(j for _, j in oc["ruled"] + oc["plain"]) == bc[:8]
    assert sum(1 for c in calls if c["bounded"]) == 8 and len(oc["ruled_rows"]) == 6
    assert ur.one_catcher_line(oc) == "ONE CATCHER: 8 rows; ruled 6, plain 2"


@pytest.mark.parametrize("kw, msg", [(dict(one_catcher_rows=-1), "0 <= N"), (dict(one_catcher_rows=15), r"B \+ C book rows \(14\)"),
                                     (dict(one_catcher_rows=3, fill="group"), "fill rr"),
                                     (dict(one_catcher_rows=3, cover_games=2), "no cover"),
                                     (dict(one_catcher_rows=3, bring_back_top_wr=("A1", "B")), "no study-71 floor")])
def test_mix_rows_refusals(monkeypatch, kw, msg):
    T71._install(monkeypatch, [])
    args = dict(exposure_cap=13, dst_cap=6, fill="rr", spares=0); args.update(kw)
    with pytest.raises(ValueError, match=msg):
        ur.mix_rows(frame(), set(), 26, 4, 4, 49_000, [1] * 26, **args)


def test_one_catcher_max_is_the_b_c_book_rows():
    assert ur.one_catcher_max(Q, 26) == 14 == ur.one_catcher_max(Q, 26, 8)
    a = M.allocate([0.30, 0.14, 0.40, 0.16], 26)
    assert ur.one_catcher_max([0.30, 0.14, 0.40, 0.16], 26) == a[2] + a[3]


@pytest.mark.parametrize("args, others, ok", [
    ((0, "pmo_x50", None, "group", 0, 0, 26, Q, 0), None, True),
    ((8, "mix", "mix", "rr", 0, 0, 26, Q, 8), None, True),
    ((14, "mix", "mix", "rr", 0, 0, 26, Q, 8), {"--mix-qb-alone-rows": 0, "--mix-flex-wr-rows": 0}, True),
    ((15, "mix", "mix", "rr", 0, 0, 26, Q, 8), None, False),
    ((-1, "mix", "mix", "rr", 0, 0, 26, Q, 8), None, False),
    ((8, "pmo_x50", None, "rr", 0, 0, 26, Q, 0), None, False),
    ((8, "mix", "ws", "rr", 0, 0, 26, Q, 0), None, False),
    ((8, "mix", "mix", "value", 0, 0, 26, Q, 0), None, False),
    ((8, "mix", "mix", "rr", 3, 0, 26, Q, 0), None, False),
    ((8, "mix", "mix", "rr", 0, 9, 26, Q, 0), None, False),
    ((8, "mix", "mix", "rr", 0, 0, 26, Q, 8, ("A1", "B")), None, False),
    ((8, "mix", "mix", "rr", 0, 0, 26, Q, 8), {"--mix-qb-alone-rows": 3}, False),
    ((8, "mix", "mix", "rr", 0, 0, 26, Q, 8), {"--mix-flex-wr-rows": 8}, False),
    ((8, "mix", "mix", "rr", 0, 0, 26, Q, 8), {"--mix-top-game-qb1": 4, "--mix-top-game-stack": 0}, False),
])
def test_the_switch_parses_and_refuses(args, others, ok):
    if ok:
        assert ur.parse_one_catcher_rows(*args, others=others) == args[0]
    else:
        with pytest.raises(SystemExit, match="--mix-one-catcher-rows"):
            ur.parse_one_catcher_rows(*args, others=others)


def test_the_cli_carries_the_flag_and_reads_the_other_row_rules_when_merged():
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert src.count("one_catcher_rows=oc_g") == 2                                          # the book and the ownership-term book
    assert 'for k in ("mix_qb_alone_rows", "mix_flex_wr_rows", "mix_top_game_qb1", "mix_top_game_stack")})' in src
    assert "does NOT carry the rule" in src


# ---------------------------------------------------------------- the build fails closed on a broken record
def _state(ruled, plain=(), used=None, pending=None, rows=None):
    return {"used": len(ruled) + len(plain) if used is None else used, "pending": pending, "ruled": [list(x) for x in ruled],
            "plain": [list(x) for x in plain], "rows": [{}] * (len(ruled) if rows is None else rows)}


def test_a_clean_record_passes():
    ur.one_catcher_close(_state([("B", 1), ("C", 2)], [("B", 5)]), ["A1", "B", "C", "A2", "A1", "B"])


@pytest.mark.parametrize("state, order, msg", [
    (_state([("B", 1)], pending="C"), ["A1", "B"], "never committed"),
    (_state([("B", 1)], used=2), ["A1", "B"], "2 attempts but 1 ruled"),
    (_state([("B", 1)], rows=0), ["A1", "B"], "0 ruled identities for 1 ruled"),
    (_state([("B", 1), ("C", 3)]), ["A1", "B", "C", "A1"], r"ruled rows at j \[3\]"),        # a leak onto A1's commit
    (_state([("A1", 0)]), ["A1"], r"ruled rows at j \[0\]"),
])
def test_a_leaked_or_broken_record_raises(state, order, msg):
    with pytest.raises(ValueError, match="ONE CATCHER RECORD BROKEN: .*" + msg):
        ur.one_catcher_close(state, order)


def test_mix_rows_runs_the_record_check(monkeypatch):
    called = []
    real = ur.one_catcher_close
    monkeypatch.setattr(ur, "one_catcher_close", lambda *a: (called.append(a), real(*a)))
    build(monkeypatch, 8)
    assert len(called) == 1
    called.clear(); build(monkeypatch, 0)
    assert called == []


# ---------------------------------------------------------------- the audit names the ruled rows by identity
def _audit_union(tmp, oc, book_rows, tags=None):
    TA = _load("tabl_oc", ROOT / "tests" / "test_audit_build_levers.py")
    lus = [TA._lineup("A", "B", "C"), TA._lineup("C", "D", "E"), TA._lineup("E", "F", "G"), TA._lineup("G", "H", "A"),
           TA._lineup("B", "A", "D"), TA._lineup("D", "C", "F")] if book_rows is None else book_rows
    tail = TA.CONTESTS + [{"name": "milly", "contest_id": "9", "entries": 1, "keep": 1, "track": "tail"}]
    base = {"selector": "mean", "operational_k": 5, "tail_sleeve": {"rows": 1, "selector_used": "mean"}}
    mix_meta = {"exposure_cap": 3, "max_exposure_used": 3, "dst_cap": 2, "max_dst_rows_used": 2,
                "mix": {"cells": {"B": {"rows": 5}}, **({"one_catcher": oc} if oc else {})}}
    r = TA._run_dir(tmp, lineups=lus, book=lus[:6], receipt={"written": 6, "config": {**base, "union": {"main": "mix", "mix": mix_meta}}})
    c = pd.read_parquet(r / "candidates.parquet"); c["source_run"] = ["mix"] * 5 + ["saturday"]
    c["tag"] = tags or ["mix_B"] * 5 + ["lev"]; c["book_rank"] = [1, 2, 3, 4, 5, None]
    c.to_parquet(r / "candidates.parquet")
    res = TA._audit(r, contests=tail, expect_selector="mean")
    return TA, res, next(x for x in res["checks"] if x["check"] == "one_catcher")


def test_the_audit_holds_the_ruled_rows_by_identity(tmp_path):
    TA = _load("tabl_oc0", ROOT / "tests" / "test_audit_build_levers.py")
    one = ["AQB", "AWR1", "BRB1", "CRB0", "DWR0", "CWR2", "GTE", "EWR1", "G_DST"]         # A's QB + 1; C, D, E, G: one catcher each
    two = ["AQB", "AWR1", "BRB1", "CRB0", "CWR0", "CWR2", "GTE", "EWR1", "G_DST"]         # two C receivers: a non-QB pair
    lus = [one, two, TA._lineup("E", "F", "G"), TA._lineup("G", "H", "A"), TA._lineup("B", "A", "D"), TA._lineup("D", "C", "F")]
    blk = lambda rows: {"rows_cap": 2, "ruled": [["B", j] for j, _ in enumerate(rows)], "plain": [],      # noqa: E731
                        "ruled_rows": [{"cell": "B", "commit_index": j, "row": sorted(r)} for j, r in enumerate(rows)]}
    _, res, c = _audit_union(tmp_path / "a", blk([one]), lus)
    assert c["ok"] and c["in_main"] == 1 and c["with_pair"] == 0 and "--mix-one-catcher-rows 2: ruled 1" in c["detail"]
    _, res, c = _audit_union(tmp_path / "b", blk([one, two]), lus)
    assert not c["ok"] and c["with_pair"] == 1 and "one_catcher" in res["failed"]          # a ruled row with a pair
    missing = ["AQB", "AWR1", "BRB1", "CRB0", "DWR0", "CWR2", "GTE", "EWR0", "G_DST"]     # not in the book
    _, res, c = _audit_union(tmp_path / "c", blk([one, missing]), lus)
    assert not c["ok"] and c["in_main"] == 1
    _, res, c = _audit_union(tmp_path / "d", None, lus)
    assert c["ok"] and c["detail"] == "--mix-one-catcher-rows off"


# ---------------------------------------------------------------- parity with the lab's OWN frozen one_catcher
S24, S18 = T71.S24, T71.S18
QB1_CELLS = ("B", "C")
ONE_CATCHER_TEXT_SHA256 = "f64b33545464b00101f288cc0f6f48cb90c4cfbce59ec7cfbf751cee2d436f3f"   # nfl2 a51d4238 s79_nopairs.py (d48790cf)


@contextmanager
def one_catcher(n_rows: int, k_book: int):
    """Wrap the current S24.CapBuilder (inside S37.built_with): the first n_rows solves of B / C (by StackRules identity) with
    j < k_book carry the lab optimizer's set_constraints [(team T's WR / TE ids, "<=", 1) for every team T]; infeasible -> the
    plain solve, recorded (the slot is used either way). Yields the class (`ruled` / `plain` lists of (cell, j); `ruled_ids`)."""
    orig_cls, orig_opt = S24.CapBuilder, S24.optimize
    target = {id(S18.CELLS[c][1]): c for c in QB1_CELLS}

    class OneCatcherBuilder(orig_cls):
        ruled: list = []
        plain: list = []
        ruled_ids: list = []
        used: list = []

        def solve_with(self, stack, qb_game_max, pair, extra_bans: set):
            cell = target.get(id(stack))
            j = len(self.prev)
            if cell is None or j >= k_book or len(type(self).used) >= n_rows:
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            type(self).used.append(j)
            by_team: dict = {}
            for p in self.recs:
                if str(p["pos"]) in ("WR", "TE"):
                    by_team.setdefault(str(p["team"]), []).append(str(p["id"]))
            S24.optimize = partial(orig_opt, set_constraints=[(ids, "<=", 1) for _, ids in sorted(by_team.items())])
            try:
                lu = super().solve_with(stack, qb_game_max, pair, extra_bans)
            finally:
                S24.optimize = orig_opt
            if lu is not None:
                type(self).ruled.append((cell, j)); type(self).ruled_ids.append(sorted(str(x) for x in lu.ids))
                return lu
            type(self).plain.append((cell, j))
            return super().solve_with(stack, qb_game_max, pair, extra_bans)

    OneCatcherBuilder.ruled, OneCatcherBuilder.plain, OneCatcherBuilder.ruled_ids, OneCatcherBuilder.used = [], [], [], []
    S24.CapBuilder = OneCatcherBuilder
    try:
        yield OneCatcherBuilder
    finally:
        S24.CapBuilder, S24.optimize = orig_cls, orig_opt


def _text_of(name: str) -> str:
    src = (ROOT / "tests" / "test_one_catcher_flag.py").read_text()
    lines = src.splitlines(keepends=True)
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    return "".join(lines[start - 1:node.end_lineno])


def test_the_vendored_one_catcher_text_is_the_labs():
    assert hashlib.sha256(_text_of("one_catcher").encode()).hexdigest() == ONE_CATCHER_TEXT_SHA256


class _HLU:
    def __init__(self, ids):
        self.ids = ids


class _OCHCap:
    """S24.CapBuilder's contract (solve_with commits a solved row) with the frame's records, so the lab's one_catcher can read
    each player's pos / team; no caps (production's run below has its caps off too)."""
    def __init__(self, fr, base, lam, main_cap, dst_cap):
        self.recs = fr.assign(obj=0.0).to_dict("records")
        self.prev, self.count, self.log = [], Counter(), []

    def solve_with(self, stack, qb_game_max, pair, extra_bans):
        lu = S24.optimize(self.recs, stack=stack, banned_lineups=self.prev)
        if lu is not None:
            self.prev.append(lu.ids); self.count.update(lu.ids); self.log.append((stack.cell, len(self.prev) - 1))
        return lu


def harness_opt(fail):
    def optimize(recs, stack, banned_lineups, set_constraints=None):
        per = None
        if set_constraints:
            assert {frozenset(ids) for ids, _, _ in set_constraints} == {frozenset(v) for v in _teams_of(recs).values()}
            senses = {(sense, k) for _, sense, k in set_constraints}
            assert len(senses) == 1 and next(iter(senses))[0] == "<="
            per = next(iter(senses))[1]
            if fail():
                return None
        return _HLU(tuple(str(p["id"]) for p in pick(recs, "obj", len(banned_lineups), None, per)))
    return optimize


def harness(monkeypatch, n, n_term=8, fail_every=None, wrapper=None):
    fr = frame()
    term = cheap_term(fr)
    monkeypatch.setattr(S24, "CapBuilder", _OCHCap)
    monkeypatch.setattr(S24, "optimize", harness_opt(Fail(fail_every)))
    base = fr.mean_projection.astype(float).tolist()
    with (wrapper or one_catcher)(n, 26) as T:
        book, cells, meta = T71.term_book(fr, base, [term.get(i, 0.0) for i in fr.id], (13, 6), W, 26, n_term, 41)
    return [sorted(lu.ids) for lu in book], cells, list(T.ruled), list(T.plain), [sorted(x) for x in T.ruled_ids]


def production(monkeypatch, n, term=True, fail_every=None):
    rows, cells, meta, spares, _ = build(monkeypatch, n, fail_every=fail_every, term=term, caps=False)
    oc = meta["one_catcher"]
    return ([sorted(r) for r in rows] + [sorted(ids) for ids, _ in spares], cells, [tuple(x) for x in oc["ruled"]],
            [tuple(x) for x in oc["plain"]], [b["row"] for b in oc["ruled_rows"]])


@pytest.mark.parametrize("n_h, n_p, term, fail_every", [(8, 8, True, None), (99, 14, True, None), (8, 8, True, 3),
                                                        (99, 14, True, 2), (3, 3, True, None), (8, 8, False, None),
                                                        (8, 8, False, 3)])
def test_parity_same_rows_ruled_and_the_same_lineups(monkeypatch, n_h, n_p, term, fail_every):
    """The lab's ONEPC_ALL is n 99 (every B / C book solve); production's largest N is the B + C book rows, 14 at K 26."""
    lineups_h, cells_h, ruled_h, plain_h, ids_h = harness(monkeypatch, n_h, n_term=8 if term else 0, fail_every=fail_every)
    lineups_p, cells_p, ruled_p, plain_p, ids_p = production(monkeypatch, n_p, term=term, fail_every=fail_every)
    assert ruled_p == ruled_h and plain_p == plain_h                                        # the same (cell, j)
    assert lineups_p == lineups_h and len(lineups_p) == 41                                  # the same 26 book rows + 15 spares
    assert cells_p == cells_h[:26] and ids_p == ids_h                                       # the same cells, the same ruled rows
    fr = frame()
    assert all(max_per_team(r, fr) <= 1 for r in ids_p)


def test_parity_detects_a_wrong_bound(monkeypatch):
    """The mutation check: the lab's wrapper with a bound of 2 gives other lineups."""
    text = _text_of("one_catcher")
    code = 'set_constraints=[(ids, "<=", 1)'                                               # the code, not the docstring
    assert text.count(code) == 1
    ns = dict(globals())
    exec(compile(text.replace(code, 'set_constraints=[(ids, "<=", 2)'), "mutated", "exec"), ns)
    lineups_h, _, ruled_h, _, _ = harness(monkeypatch, 8, wrapper=ns["one_catcher"])
    lineups_p, _, ruled_p, _, _ = production(monkeypatch, 8)
    assert ruled_p == ruled_h and lineups_p != lineups_h
