"""The three row rules TOGETHER (study 83's COMBO; the operator 10-09: "Let's do a test now of all 3 and if it isn't negative
use it in week 5"; the laptop's agreed format): --mix-qb-alone-rows 3 + --mix-one-catcher-rows <the B + C book rows> +
--mix-flex-wr-rows 3, and nothing else together; ONE combined optimize call per ruled solve (the C0 stack + every
member_bounds that applies); PARITY with the lab's OWN frozen combined wrapper (nfl2 experiments/s83_combo.py combo, pasted
byte for byte, its text sha-pinned) on the lab's term_book: one stand-in optimizer reading production's StackRules /
member_bounds and the lab's stack / set_constraints alike, the same (cell, j) per rule, the same 41 lineups, C0 at the
harness's C0 positions, with and without infeasible solves; three mutations (each rule's bound) fail it. Each rule alone stays
covered by its own module (test_qb_alone_flag, test_one_catcher_flag, test_flex_wr_flag)."""
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


T71 = _load("t71_helpers_combo", ROOT / "tests" / "test_s71_bring_back_top_wr.py")      # the lab's term_book, stand-ins
W = [3, 3] + [1] * 24
Q = [c[0] for c in M.MIX_CELLS.values()]
OFFSET = {0: 1.5, 1: 0.3, 2: 1.2, 3: 1.1, 4: 1.0, 5: -4.0}


def frame() -> pd.DataFrame:
    """12 teams (QB, RB, WR, WR, TE, DST), each team's players together in the objective order, so the one-catcher bound,
    the QB-alone stack and the WR flex all bind."""
    rows = []
    for t in range(12):
        team, opp, g = f"T{t}", f"T{t ^ 1}", f"g{t // 2}"
        for j, pos in enumerate(("QB", "RB", "WR", "WR", "TE", "DST")):
            pid = f"{team}.{pos}{j}"
            rows.append({"id": pid, "name": pid, "pos": pos, "team": team, "opp": opp, "game_id": g,
                         "salary": 4000 + 100 * ((7 * t + 3 * j) % 40),
                         "mean_projection": 5.0 + 2.0 * ((7 * t) % 12) + OFFSET[j]})
    return pd.DataFrame(rows)


def cheap_term(fr):
    return {i: 2.0 for i, s, p in zip(fr.id, fr.salary, fr.pos) if s < 5500 and p != "DST"}


def pick(pool, obj, n_prev, bans, naked, per_team, wr_exact):
    """THE shared stand-in solve: the objective order (ties: id) rotated by the rows committed so far; naked: the first QB, no
    WR / TE of his team and no other QB; per_team: at most that many WR / TE of one team; wr_exact: exactly that many WRs
    (taken first, in order); then the rest in order up to 9."""
    avail = [p for p in pool if not bans or p["id"] not in bans]
    order = sorted(avail, key=lambda p: (-float(p[obj]), str(p["id"])))
    off = n_prev % len(order)
    rot = order[off:] + order[:off]
    out, held = [], Counter()
    q = next(p for p in rot if p["pos"] == "QB") if naked else None
    if q is not None:
        out.append(q)

    def ok(p):
        if any(p["id"] == x["id"] for x in out):
            return False
        if naked and (p["pos"] == "QB" or (p["pos"] in ("WR", "TE") and p["team"] == q["team"])):
            return False
        return not (per_team is not None and p["pos"] in ("WR", "TE") and held[p["team"]] >= per_team)

    def take(p):
        out.append(p)
        if p["pos"] in ("WR", "TE"):
            held[p["team"]] += 1

    if wr_exact is not None:
        for p in rot:
            if sum(1 for x in out if x["pos"] == "WR") >= wr_exact:
                break
            if p["pos"] == "WR" and ok(p):
                take(p)
    for p in rot:
        if len(out) == 9:
            break
        if (wr_exact is None or p["pos"] != "WR") and ok(p):
            take(p)
    return out


class Fail:
    """Which ruled solves report infeasible: every `every`-th (None = never)."""
    def __init__(self, every=None):
        self.every, self.n = every, 0

    def __call__(self) -> bool:
        self.n += 1
        return bool(self.every) and self.n % self.every == 0


def production_opt(calls, fail):
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None,
                 member_bounds=None, interaction_floor_weights=None, interaction_floor=None):
        naked = stack.qb_stack_max == 0
        per_team = wr_exact = None
        for ids, lo, hi in member_bounds or []:
            wr_ids = {p["id"] for p in pool if p["pos"] == "WR"}
            if set(ids) == wr_ids:
                assert lo == hi
                wr_exact = lo
            else:
                assert lo == 0
                per_team = hi
        calls.append({"j": len(banned_lineups), "naked": naked, "per_team": per_team, "wr": wr_exact})
        if (naked or member_bounds) and fail():
            return None
        return T71.LU(pick(pool, objective_col, len(banned_lineups), bans, naked, per_team, wr_exact))
    return optimize


def build(monkeypatch, qa=3, oc=14, fx=3, fail_every=None, caps=False, term=True):
    calls = []
    T71._install(monkeypatch, calls, production_opt(calls, Fail(fail_every)))
    fr = frame()
    kw = dict(exposure_cap=13 if caps else None, dst_cap=6 if caps else None, fill="rr", spares=15,
              qb_alone_rows=qa, one_catcher_rows=oc, flex_wr_rows=fx)
    if term:
        kw.update(term_rows=8, term_bonus=cheap_term(fr))
    rows, cells, meta, sp = ur.mix_rows(fr, set(), 26, 4, 4, 49_000, W, **kw)
    return rows, cells, meta, sp, calls


# ---------------------------------------------------------------- the combination rule
@pytest.mark.parametrize("qa, oc, fx, ok", [(0, 0, 0, True), (3, 0, 0, True), (0, 14, 0, True), (0, 0, 3, True), (0, 8, 0, True),
                                            (3, 14, 3, True), (3, 14, 0, False), (3, 0, 3, False), (0, 14, 3, False),
                                            (2, 14, 3, False), (3, 13, 3, False), (3, 14, 8, False)])
def test_the_rules_together_only_as_study_83s_combination(qa, oc, fx, ok):
    got = ur.row_rules_problem(qa, oc, fx, Q, 26, 8)
    assert (got is None) == ok
    if not ok:
        assert "allowed only as a tested set" in got and "COMBO = 3 / 14 / 3 / 0" in got


def test_the_flex_never_with_study_71s_floor():
    assert "untested together" in ur.row_rules_problem(0, 0, 3, Q, 26, 8, ("A1", "B"))
    assert ur.row_rules_problem(3, 0, 0, Q, 26, 8, ("A1", "B")) is None                   # C0 alone with 71: as before


def test_mix_rows_refuses_another_combination(monkeypatch):
    T71._install(monkeypatch, [])
    with pytest.raises(ValueError, match="allowed only as a tested set"):
        ur.mix_rows(frame(), set(), 26, 4, 4, 49_000, W, fill="rr", spares=0, qb_alone_rows=3, flex_wr_rows=3)


def test_the_cli_checks_the_combination():
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert "bad_rules = row_rules_problem(qa_g, oc_g, fx_g," in src and "raise SystemExit(bad_rules)" in src
    assert src.count("qb_alone_rows=qa_g,") == 2 and src.count("one_catcher_rows=oc_g, flex_wr_rows=fx_g, no_te_above=te_g)") == 2


def test_the_combined_solve_is_one_call(monkeypatch):
    rows, cells, meta, spares, calls = build(monkeypatch)
    ruled = [c for c in calls if c["naked"] or c["per_team"] or c["wr"]]
    assert all(c["j"] < 26 for c in ruled)                                                # spares never
    allthree = [c for c in ruled if c["naked"] and c["per_team"] == 1 and c["wr"] == 4]
    assert len(allthree) == 1 and allthree[0]["j"] < 3                                    # the first C solve, inside the flex rows
    assert len(meta["qb_alone"]["ruled"]) == 3 and len(meta["flex_wr"]["ruled"]) == 3
    assert len(meta["one_catcher"]["ruled"]) == 14 and cells.count("C0") == 3


# ---------------------------------------------------------------- parity with the lab's OWN frozen combined wrapper
S24 = T71.S24
COMBO_TEXT_SHA256 = "2a7cf7c2ff1c222bf1589dfd213ec9306db31cb9ddeee50f82bdb93d051aac90"   # nfl2 a7a1f60c s83_combo.py (19d9a77c)
QB1_CELLS = ("B", "C")


@dataclasses.dataclass
class _QStack:                                     # one dataclass per cell: the wrapper finds C by identity and replaces it
    cell: str
    qb_stack_min: int = 1
    bring_back_min: int = 0
    qb_stack_max: int | None = None
    bring_back_max: int | None = None


S18 = types.SimpleNamespace(CELLS={n: (q, _QStack(n, **r), qmax, which) for n, (q, r, qmax, which) in M.MIX_CELLS.items()},
                            allocate=M.allocate, interleave=M.interleave, pair_games=lambda fr, which: None)


@contextmanager
def combo(n_c0: int, onepc: bool, n_flex: int, k_book: int):
    """Wrap the current S24.CapBuilder (inside S37.built_with). For a solve with j = len(prev) < k_book: C0 if its stack is C's
    (by identity) and fewer than n_c0 C0 slots are used (the slot is used either way; study 77); ONEPC if onepc and its stack
    is B's or C's (study 79's set_constraints [(team T's WR / TE, "<=", 1)] for every team T in the builder's records); FLEX
    if j < n_flex (study 75's set_constraints [(the WR ids, ">=", 4)]). The applicable rules are ONE solve (the C0 stack, the
    union of the constraints); infeasible -> the solve at the cell's own stack with no constraint, recorded. Yields the
    class (`ruled` / `plain` lists of (cell, j, rules); `ruled_ids` lineups; `c0_ids` the C0-ruled lineups)."""
    orig_cls, orig_opt = S24.CapBuilder, S24.optimize
    c_stack = S18.CELLS["C"][1]
    naked = dataclasses.replace(c_stack, qb_stack_min=0, qb_stack_max=0)
    target = {id(S18.CELLS[c][1]): c for c in S18.CELLS}
    qb1 = {id(S18.CELLS[c][1]) for c in QB1_CELLS}

    class ComboBuilder(orig_cls):
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
            if not (use_c0 or use_oc or use_fx):
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            cell = target.get(id(stack), "?")
            rules = tuple(r for r, u in (("c0", use_c0), ("onepc", use_oc), ("flex", use_fx)) if u)
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
                lu = super().solve_with(naked if use_c0 else stack, qb_game_max, pair, extra_bans)
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

    ComboBuilder.ruled, ComboBuilder.plain, ComboBuilder.ruled_ids, ComboBuilder.c0_ids, ComboBuilder.c0_used = [], [], [], [], []
    S24.CapBuilder = ComboBuilder
    try:
        yield ComboBuilder
    finally:
        S24.CapBuilder, S24.optimize = orig_cls, orig_opt


def _text_of(name: str) -> str:
    src = (ROOT / "tests" / "test_combo_flag.py").read_text()
    lines = src.splitlines(keepends=True)
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    return "".join(lines[start - 1:node.end_lineno])


def test_the_vendored_combo_text_is_the_labs():
    assert hashlib.sha256(_text_of("combo").encode()).hexdigest() == COMBO_TEXT_SHA256


class _HLU:
    def __init__(self, ids):
        self.ids = ids


class _CHCap:
    """S24.CapBuilder's contract (solve_with commits a solved row) with the frame's records; no caps (production's run below
    has its caps off too)."""
    def __init__(self, fr, base, lam, main_cap, dst_cap):
        self.recs = fr.assign(obj=0.0).to_dict("records")
        self.prev, self.count = [], Counter()

    def solve_with(self, stack, qb_game_max, pair, extra_bans):
        lu = S24.optimize(self.recs, stack=stack, banned_lineups=self.prev)
        if lu is not None:
            self.prev.append(lu.ids); self.count.update(lu.ids)
        return lu


def harness_opt(fail):
    def optimize(recs, stack, banned_lineups, set_constraints=None):
        naked = stack.qb_stack_max == 0
        per_team = wr_exact = None
        for ids, sense, k in set_constraints or []:
            if sense == ">=":
                assert set(ids) == {str(p["id"]) for p in recs if p["pos"] == "WR"}
                wr_exact = k                                     # the lab optimizer's own WR <= 4 makes ">= 4" exactly 4
            else:
                per_team = k
        if (naked or set_constraints) and fail():
            return None
        return _HLU(tuple(str(p["id"]) for p in pick(recs, "obj", len(banned_lineups), None, naked, per_team, wr_exact)))
    return optimize


def harness(monkeypatch, fail_every=None, n_term=8, wrapper=None):
    fr = frame()
    term = cheap_term(fr)
    monkeypatch.setattr(T71, "S18", S18)
    monkeypatch.setattr(S24, "CapBuilder", _CHCap)
    monkeypatch.setattr(S24, "optimize", harness_opt(Fail(fail_every)))
    base = fr.mean_projection.astype(float).tolist()
    with (wrapper or combo)(3, True, 3, 26) as T:
        book, cells, meta = T71.term_book(fr, base, [term.get(i, 0.0) for i in fr.id], (13, 6), W, 26, n_term, 41)
    lineups = [sorted(lu.ids) for lu in book]
    c0_at = sorted(next(k for k in range(26) if lineups[k] == r) for r in T.c0_ids)
    per_rule = {r: ([(c, j) for c, j, rs in T.ruled if r in rs], [(c, j) for c, j, rs in T.plain if r in rs])
                for r in ("c0", "onepc", "flex")}
    return lineups, cells, per_rule, c0_at


def production(monkeypatch, fail_every=None, term=True):
    rows, cells, meta, spares, _ = build(monkeypatch, fail_every=fail_every, term=term)
    blk = {"c0": meta["qb_alone"], "onepc": meta["one_catcher"], "flex": meta["flex_wr"]}
    per_rule = {r: ([tuple(x) for x in b["ruled"]], [tuple(x) for x in b["plain"]]) for r, b in blk.items()}
    per_rule["c0"] = ([("C", j) for _, j in per_rule["c0"][0]], [("C", j) for _, j in per_rule["c0"][1]])
    return [sorted(r) for r in rows] + [sorted(ids) for ids, _ in spares], cells, per_rule


@pytest.mark.parametrize("fail_every, term", [(None, True), (3, True), (2, True), (None, False), (4, False)])
def test_parity_with_the_labs_combined_wrapper(monkeypatch, fail_every, term):
    lineups_h, cells_h, rules_h, c0_at = harness(monkeypatch, fail_every, n_term=8 if term else 0)
    lineups_p, cells_p, rules_p = production(monkeypatch, fail_every, term)
    assert rules_p == rules_h                                                          # the same (cell, j) per rule, ruled and plain
    assert lineups_p == lineups_h and len(lineups_p) == 41                             # the same 26 book rows + 15 spares
    assert [("C" if c == "C0" else c) for c in cells_p] == cells_h[:26]
    assert [k for k, c in enumerate(cells_p) if c == "C0"] == c0_at
    if fail_every:
        assert any(rules_p[r][1] for r in rules_p)                                    # some combined solves were infeasible


def test_the_combination_binds_here(monkeypatch):
    """Non-vacuity: the combined book differs from OFF, and from each rule's book alone."""
    on = [sorted(r) for r in build(monkeypatch)[0]]
    off = [sorted(r) for r in build(monkeypatch, 0, 0, 0)[0]]
    singles = [[sorted(r) for r in build(monkeypatch, *x)[0]] for x in ((3, 0, 0), (0, 14, 0), (0, 0, 3))]
    assert on != off and all(on != s for s in singles)


@pytest.mark.parametrize("code, mutant", [("qb_stack_min=0, qb_stack_max=0)", "qb_stack_min=0, qb_stack_max=1)"),
                                          ('cons += [(ids, "<=", 1) for _, ids', 'cons += [(ids, "<=", 2) for _, ids'),
                                          ('== "WR"], ">=", 4))', '== "WR"], ">=", 3))')])
def test_parity_detects_each_wrong_bound(monkeypatch, code, mutant):
    """The mutation checks: each rule's bound changed in the lab's wrapper gives other lineups."""
    text = _text_of("combo")
    assert text.count(code) == 1                                                       # the code, never the docstring
    ns = dict(globals())
    exec(compile(text.replace(code, mutant), "mutated", "exec"), ns)
    lineups_h, _, _, _ = harness(monkeypatch, wrapper=ns["combo"])
    lineups_p, _, _ = production(monkeypatch)
    assert lineups_p != lineups_h
