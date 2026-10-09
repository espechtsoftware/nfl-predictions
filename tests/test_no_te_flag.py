"""The TE ban (union_reselect --mix-no-te-above SALARY; study 81's NOTE5K_ALL in study 84's sets; the laptop's agreed format
10-09): every pool TE priced >= SALARY banned on every BOOK solve inside the ONE combined row-rule solve; infeasible -> the
cell's own rules with no bound and no ban, recorded; spares never; the tested sets only (TE alone, TE + C0 / one catcher /
flex, COMBO + TE); OFF identical; PARITY with the lab's OWN frozen study-84 wrapper (nfl2 experiments/s84_combo81.py combo81,
pasted byte for byte, its text sha-pinned) on the lab's term_book for EACH tested set with a TE, with and without infeasible
solves; mutations (the ban dropped, each 83 bound) fail it; the audit check."""
import ast
import dataclasses
import hashlib
import importlib.util
import sys
import types
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


T71 = _load("t71_helpers_te", ROOT / "tests" / "test_s71_bring_back_top_wr.py")       # the lab's term_book, stand-ins
TC = _load("tcombo_helpers_te", ROOT / "tests" / "test_combo_flag.py")                  # frame, cheap_term, pick, Fail
W, Q, frame, cheap_term, pick, Fail = TC.W, TC.Q, TC.frame, TC.cheap_term, TC.pick, TC.Fail
TE_PRICE = 5000
SETS = {"COMBO81": (3, 14, 3, TE_PRICE), "TE_C0": (3, 0, 0, TE_PRICE), "TE_ONEPC": (0, 14, 0, TE_PRICE),
        "TE_FLEX": (0, 0, 3, TE_PRICE), "TE_ONLY": (0, 0, 0, TE_PRICE)}
HARNESS_ARGS = {"COMBO81": (3, True, 3), "TE_C0": (3, False, 0), "TE_ONEPC": (0, True, 0), "TE_FLEX": (0, False, 3),
                "TE_ONLY": (0, False, 0)}


def pricey():
    fr = frame()
    return {str(i) for i, p, s in zip(fr.id, fr.pos, fr.salary) if p == "TE" and s >= TE_PRICE}


def production_opt(calls, fail):
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None,
                 member_bounds=None, interaction_floor_weights=None, interaction_floor=None):
        naked = stack.qb_stack_max == 0
        per_team = wr_exact = None
        wr_ids = {p["id"] for p in pool if p["pos"] == "WR"}
        for ids, lo, hi in member_bounds or []:
            if set(ids) == wr_ids:
                wr_exact = lo
            else:
                per_team = hi
        calls.append({"j": len(banned_lineups), "naked": naked, "per_team": per_team, "wr": wr_exact,
                      "bans": frozenset(bans or ())})
        if (naked or member_bounds or bans) and fail():
            return None
        return T71.LU(pick(pool, objective_col, len(banned_lineups), bans, naked, per_team, wr_exact))
    return optimize


def build(monkeypatch, qa=0, oc=0, fx=0, te=0, fail_every=None, term=True, **extra):
    calls = []
    T71._install(monkeypatch, calls, production_opt(calls, Fail(fail_every)))
    fr = frame()
    kw = dict(exposure_cap=None, dst_cap=None, fill="rr", spares=15, qb_alone_rows=qa, one_catcher_rows=oc, flex_wr_rows=fx,
              no_te_above=te)
    if term:
        kw.update(term_rows=8, term_bonus=cheap_term(fr))
    kw.update(extra)
    rows, cells, meta, sp = ur.mix_rows(fr, set(), 26, 4, 4, 49_000, W, **kw)
    return rows, cells, meta, sp, calls


def te_count(row):
    p = pricey()
    return sum(1 for i in row if i in p)


# ---------------------------------------------------------------- production behaviour
def test_off_is_the_old_call_exactly(monkeypatch):
    a = build(monkeypatch)
    calls = []
    T71._install(monkeypatch, calls, production_opt(calls, Fail()))
    fr = frame()
    b = ur.mix_rows(fr, set(), 26, 4, 4, 49_000, W, exposure_cap=None, dst_cap=None, fill="rr", spares=15, term_rows=8,
                    term_bonus=cheap_term(fr))
    assert a[:4] == b and a[4] == calls and "no_te_above" not in a[2] and all(not c["bans"] for c in calls)


@pytest.mark.parametrize("term", [True, False])
def test_te_alone_bans_on_every_book_solve_and_never_on_a_spare(monkeypatch, term):
    rows, cells, meta, spares, calls = build(monkeypatch, te=TE_PRICE, term=term)
    nt = meta["no_te_above"]
    assert nt["salary"] == TE_PRICE and set(nt["banned_ids"]) == pricey() and nt["plain"] == []
    assert [j for _, j in nt["ruled"]] == list(range(26))                                     # every book solve
    assert all(c["bans"] == frozenset(pricey()) for c in calls if c["j"] < 26)
    assert all(not c["bans"] for c in calls if c["j"] >= 26)                                  # spares never
    assert all(te_count(r) == 0 for r in rows)
    off = build(monkeypatch, term=term)[0]
    assert sum(te_count(r) for r in off) > 0 and [sorted(r) for r in rows] != [sorted(r) for r in off]   # it binds here
    assert ur.no_te_above_line(nt).startswith(f"NO TE ABOVE: ${TE_PRICE} (")


def test_an_infeasible_te_solve_is_built_plain_and_recorded(monkeypatch):
    rows, cells, meta, spares, calls = build(monkeypatch, te=TE_PRICE, fail_every=4)
    nt = meta["no_te_above"]
    assert len(nt["plain"]) == 6 and len(nt["ruled"]) == 20                                  # the 4th, 8th, ... of 26 attempts
    assert sorted(j for _, j in nt["ruled"] + nt["plain"]) == list(range(26))


@pytest.mark.parametrize("qa, oc, fx, te, ok", [(0, 0, 0, 5000, True), (0, 0, 0, 6000, True), (3, 0, 0, 5000, True), (0, 14, 0, 5000, True),
                                                (0, 0, 3, 5000, True), (3, 14, 3, 5000, True), (3, 14, 3, 0, True),
                                                (3, 0, 0, 6000, False), (3, 14, 0, 5000, False), (0, 14, 3, 5000, False),
                                                (3, 0, 3, 5000, False), (2, 0, 0, 5000, False), (0, 8, 0, 5000, False)])
def test_the_tested_sets_only(qa, oc, fx, te, ok):
    assert (ur.row_rules_problem(qa, oc, fx, Q, 26, 8, (), te) is None) == ok


def test_the_te_ban_never_with_study_71s_floor():
    assert "untested together" in ur.row_rules_problem(0, 0, 0, Q, 26, 8, ("A1", "B"), 5000)


def test_the_cli_parses_the_flag():
    assert ur.parse_no_te_above(0, "pmo_x50", None, "group", 0, 0) == 0
    assert ur.parse_no_te_above(5000, "mix", "mix", "rr", 0, 0) == 5000
    for args in ((5000, "pmo_x50", None, "rr", 0, 0), (5000, "mix", "mix", "value", 0, 0), (5000, "mix", "mix", "rr", 3, 0), (-1, "mix", "mix", "rr", 0, 0)):
        with pytest.raises(SystemExit, match="--mix-no-te-above"):
            ur.parse_no_te_above(*args)
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert src.count("no_te_above=te_g)") == 2 and "on his W4 book it changed 24 of 26 rows" in src


def test_the_audit_holds_main_rows_below_the_price(tmp_path):
    TA = _load("tabl_te", ROOT / "tests" / "test_audit_build_levers.py")
    lus = [TA._lineup("A", "B", "C"), TA._lineup("C", "D", "E"), TA._lineup("E", "F", "G"), TA._lineup("G", "H", "A"),
           TA._lineup("B", "A", "D"), TA._lineup("D", "C", "F")]
    tail = TA.CONTESTS + [{"name": "milly", "contest_id": "9", "entries": 1, "keep": 1, "track": "tail"}]
    base = {"selector": "mean", "operational_k": 5, "tail_sleeve": {"rows": 1, "selector_used": "mean"}}

    def run(tmp, nt):
        mix_meta = {"exposure_cap": 3, "max_exposure_used": 3, "dst_cap": 2, "max_dst_rows_used": 2,
                    "mix": {"cells": {"A1": {"rows": 5}}, **({"no_te_above": nt} if nt else {})}}
        r = TA._run_dir(tmp, lineups=lus, book=lus[:6], receipt={"written": 6, "config": {**base, "union": {"main": "mix", "mix": mix_meta}}})
        c = pd.read_parquet(r / "candidates.parquet"); c["source_run"] = ["mix"] * 5 + ["saturday"]; c["tag"] = ["mix_A1"] * 5 + ["lev"]
        c["book_rank"] = [1, 2, 3, 4, 5, None]
        c.to_parquet(r / "candidates.parquet")
        res = TA._audit(r, contests=tail, expect_selector="mean")
        return next(x for x in res["checks"] if x["check"] == "no_te_above")

    # every _lineup holds its `other` team's TE at $4,200: below 5000, at or above 4000
    assert run(tmp_path / "a", {"salary": 5000, "ruled": [["A1", 0]] * 5, "plain": []})["ok"]
    hit = run(tmp_path / "b", {"salary": 4000, "ruled": [["A1", 0]] * 5, "plain": []})
    assert not hit["ok"] and hit["rows_with_te"] == 5
    assert run(tmp_path / "c", {"salary": 4000, "ruled": [], "plain": [["A1", j] for j in range(5)]})["ok"]
    off = run(tmp_path / "d", None)
    assert off["ok"] and off["detail"] == "--mix-no-te-above off"


# ---------------------------------------------------------------- parity with the lab's OWN frozen study-84 wrapper
S24 = T71.S24
COMBO81_TEXT_SHA256 = "c38f27a743555b062fae5e8bd0e88f6be309cae9d513daf08131f34aaa815971"   # nfl2 s84_combo81.py (study 84)
QB1_CELLS = ("B", "C")
S18 = TC.S18                                       # dataclass stacks per cell (the wrapper replaces C's)


@contextmanager
def combo81(n_c0: int, onepc: bool, n_flex: int, banned: set[str], k_book: int):
    """Study 83's combo with study 81's ban set: for a solve with j = len(prev) < k_book, C0 / ONEPC / FLEX exactly as study 83's
    combo, and NOTE5K (every solve, when `banned` is not empty) adds `banned` to its extra bans; the rules that apply are ONE
    solve; infeasible -> the solve at the cell's own stack with no constraint and no ban, recorded. Yields the class
    (`ruled` / `plain` lists of (cell, j, rules); `ruled_ids`; `c0_ids`)."""
    orig_cls, orig_opt = S24.CapBuilder, S24.optimize
    c_stack = S18.CELLS["C"][1]
    naked = dataclasses.replace(c_stack, qb_stack_min=0, qb_stack_max=0)
    target = {id(S18.CELLS[c][1]): c for c in S18.CELLS}
    qb1 = {id(S18.CELLS[c][1]) for c in QB1_CELLS}
    ban = set(banned)

    class Combo81Builder(orig_cls):
        ruled: list = []
        plain: list = []
        ruled_ids: list = []
        c0_ids: list = []
        c0_used: list = []

        def solve_with(self, stack, qb_game_max, pair, extra_bans: set):
            j = len(self.prev)
            if j >= k_book:
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            use_c0 = stack is c_stack and len(type(self).c0_used) < n_c0
            use_oc = bool(onepc) and id(stack) in qb1
            use_fx = j < n_flex
            use_te = bool(ban)
            if not (use_c0 or use_oc or use_fx or use_te):
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            cell = target.get(id(stack), "?")
            rules = tuple(r for r, u in (("c0", use_c0), ("onepc", use_oc), ("flex", use_fx), ("note5k", use_te)) if u)
            if use_c0:
                type(self).c0_used.append(j)
            cons: list = []
            if use_oc:
                by_team: dict = {}
                for p in self.recs:
                    if str(p["pos"]) in ("WR", "TE"):
                        by_team.setdefault(str(p["team"]), []).append(str(p["id"]))
                cons += [(ids, "<=", 1) for _, ids in sorted(by_team.items())]
            if use_fx:
                cons.append(([str(p["id"]) for p in self.recs if str(p["pos"]) == "WR"], ">=", 4))
            if cons:
                S24.optimize = partial(orig_opt, set_constraints=cons)
            try:
                lu = super().solve_with(naked if use_c0 else stack, qb_game_max, pair,
                                        (set(extra_bans) | ban) if use_te else extra_bans)
            finally:
                S24.optimize = orig_opt
            if lu is not None:
                ids = sorted(str(x) for x in lu.ids)
                type(self).ruled.append((cell, j, rules)); type(self).ruled_ids.append(ids)
                if use_c0:
                    type(self).c0_ids.append(ids)
                return lu
            type(self).plain.append((cell, j, rules))
            return super().solve_with(stack, qb_game_max, pair, extra_bans)

    Combo81Builder.ruled, Combo81Builder.plain, Combo81Builder.ruled_ids, Combo81Builder.c0_ids, Combo81Builder.c0_used = [], [], [], [], []
    S24.CapBuilder = Combo81Builder
    try:
        yield Combo81Builder
    finally:
        S24.CapBuilder, S24.optimize = orig_cls, orig_opt


def _text_of(name: str) -> str:
    src = (ROOT / "tests" / "test_no_te_flag.py").read_text()
    lines = src.splitlines(keepends=True)
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    return "".join(lines[start - 1:node.end_lineno])


def test_the_vendored_combo81_text_is_the_labs():
    assert hashlib.sha256(_text_of("combo81").encode()).hexdigest() == COMBO81_TEXT_SHA256


class _HLU:
    def __init__(self, ids):
        self.ids = ids


class _BHCap:
    """S24.CapBuilder's contract (solve_with commits a solved row) with the frame's records; the extra bans reach the
    optimizer (as the lab's CapBuilder passes them); no caps."""
    def __init__(self, fr, base, lam, main_cap, dst_cap):
        self.recs = fr.assign(obj=0.0).to_dict("records")
        self.prev, self.count = [], Counter()

    def solve_with(self, stack, qb_game_max, pair, extra_bans):
        lu = S24.optimize(self.recs, stack=stack, banned_lineups=self.prev, bans=set(extra_bans or ()))
        if lu is not None:
            self.prev.append(lu.ids); self.count.update(lu.ids)
        return lu


def harness_opt(fail):
    def optimize(recs, stack, banned_lineups, bans=None, set_constraints=None):
        naked = stack.qb_stack_max == 0
        per_team = wr_exact = None
        for ids, sense, k in set_constraints or []:
            if sense == ">=":
                wr_exact = k
            else:
                per_team = k
        if (naked or set_constraints or bans) and fail():
            return None
        return _HLU(tuple(str(p["id"]) for p in pick(recs, "obj", len(banned_lineups), bans or None, naked, per_team, wr_exact)))
    return optimize


def harness(monkeypatch, arm, fail_every=None, n_term=8, wrapper=None):
    fr = frame()
    term = cheap_term(fr)
    monkeypatch.setattr(T71, "S18", S18)
    monkeypatch.setattr(S24, "CapBuilder", _BHCap)
    monkeypatch.setattr(S24, "optimize", harness_opt(Fail(fail_every)))
    base = fr.mean_projection.astype(float).tolist()
    with (wrapper or combo81)(*HARNESS_ARGS[arm], pricey(), 26) as T:
        book, cells, meta = T71.term_book(fr, base, [term.get(i, 0.0) for i in fr.id], (13, 6), W, 26, n_term, 41)
    lineups = [sorted(lu.ids) for lu in book]
    c0_at = sorted(next(k for k in range(26) if lineups[k] == r) for r in T.c0_ids)
    per_rule = {r: ([(c, j) for c, j, rs in T.ruled if r in rs], [(c, j) for c, j, rs in T.plain if r in rs])
                for r in ("c0", "onepc", "flex", "note5k")}
    return lineups, cells, per_rule, c0_at


def production(monkeypatch, arm, fail_every=None, term=True):
    rows, cells, meta, spares, _ = build(monkeypatch, *SETS[arm], fail_every=fail_every, term=term)
    names = {"c0": "qb_alone", "onepc": "one_catcher", "flex": "flex_wr", "note5k": "no_te_above"}
    per_rule = {}
    for r, key in names.items():
        b = meta.get(key) or {"ruled": [], "plain": []}
        per_rule[r] = ([tuple(x) for x in b["ruled"]], [tuple(x) for x in b["plain"]])
    per_rule["c0"] = ([("C", j) for _, j in per_rule["c0"][0]], [("C", j) for _, j in per_rule["c0"][1]])
    return [sorted(r) for r in rows] + [sorted(ids) for ids, _ in spares], cells, per_rule


@pytest.mark.parametrize("arm", list(SETS))
@pytest.mark.parametrize("fail_every, term", [(None, True), (3, True), (None, False)])
def test_parity_with_the_labs_study_84_wrapper(monkeypatch, arm, fail_every, term):
    lineups_h, cells_h, rules_h, c0_at = harness(monkeypatch, arm, fail_every, n_term=8 if term else 0)
    lineups_p, cells_p, rules_p = production(monkeypatch, arm, fail_every, term)
    assert rules_p == rules_h                                                          # the same (cell, j) per rule, ruled and plain
    assert lineups_p == lineups_h and len(lineups_p) == 41
    assert [("C" if c == "C0" else c) for c in cells_p] == cells_h[:26]
    assert [k for k, c in enumerate(cells_p) if c == "C0"] == c0_at
    if fail_every:
        assert rules_p["note5k"][1]                                                    # some combined solves were infeasible


@pytest.mark.parametrize("code, mutant", [("(set(extra_bans) | ban) if use_te else extra_bans", "extra_bans"),
                                          ("qb_stack_min=0, qb_stack_max=0)", "qb_stack_min=0, qb_stack_max=1)"),
                                          ('cons += [(ids, "<=", 1) for _, ids', 'cons += [(ids, "<=", 2) for _, ids'),
                                          ('== "WR"], ">=", 4))', '== "WR"], ">=", 3))')])
def test_parity_detects_each_mutation(monkeypatch, code, mutant):
    text = _text_of("combo81")
    assert text.count(code) == 1                                                       # the code, never the docstring
    ns = dict(globals())
    exec(compile(text.replace(code, mutant), "mutated", "exec"), ns)
    lineups_h, _, _, _ = harness(monkeypatch, "COMBO81", wrapper=ns["combo81"])
    lineups_p, _, _ = production(monkeypatch, "COMBO81")
    assert lineups_p != lineups_h
