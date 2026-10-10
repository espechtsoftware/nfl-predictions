"""Study 93's ONECATCH on the live MIX book (the operator 10-09: "Live W5 if built in time"): union_reselect's
mix_rows(row_bounds=[te1, low1], one_catcher=True) against the lab's OWN code -- nfl2 experiments/s93_leads.py @ 5f4e1fb9's
lead_rules pasted BELOW byte for byte (its text sha-pinned) with onepc=True, n_c0=0, n_flex=0 and 6p's row cons, entered before
study 89's own_caps (pasted in test_own_cap_flag.py) on the lab's term_book (vendored in test_s71_bring_back_top_wr.py), with
ONE stand-in optimizer that reads the lab's set_constraints and production's member_bounds alike, on a fixture where the rule
BINDS (each team's players adjacent in the objective order). Forced infeasibles: a solve carrying the one-catcher bounds at
some rows (the one-catcher dropped first, the row rules kept), any bound at others (then none). The same 26 book rows, 15
spares and records; the B / C term rows ruled too; A1 / A2 and the spares never; off = the row-rules call; two code mutations
caught; the CLI refusals; the audit check."""
import ast
import dataclasses
import hashlib
import importlib.util
import json
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


RR = _load("row_rules_helpers_oc", ROOT / "tests" / "test_row_rules_flag.py")    # 6p's fixture, OC (89's own_caps), T71
OC, T71 = RR.OC, RR.T71
ABL_T = _load("audit_helpers_oc", ROOT / "tests" / "test_audit_build_levers.py")
LAB_TEXT_SHA256 = {"lead_rules": "3c90a7560e9e4af33062c5b1cf5d963d58f2fe92121ede86a1bdfbeff605bb82"}   # c5bcac30 without the last newline


@dataclasses.dataclass(eq=False)
class _DStack:                                      # one object per cell (found by identity); a dataclass, as the pasted
    cell: str                                       # lead_rules replaces C's stack for its (unused here) naked C0 stack
    qb_stack_min: int = 1
    qb_stack_max: int = 1


S18 = types.SimpleNamespace(CELLS={n: (q, _DStack(n), qmax, which) for n, (q, _, qmax, which) in T71.M.MIX_CELLS.items()},
                            allocate=T71.S18.allocate, interleave=T71.S18.interleave, pair_games=T71.S18.pair_games)
S24 = T71.S24                                       # the pasted lab code below reads these names
QB1_CELLS = ("B", "C")                              # s93_leads.py's constant


# ---- nfl2 experiments/s93_leads.py @ 5f4e1fb9, BYTE FOR BYTE (test_the_pasted_lab_text_is_the_labs) ----
@contextmanager
def lead_rules(n_c0: int, onepc: bool, n_flex: int, row_cons: list, k_book: int):
    """Study 83's combo rules (s83_combo.combo, re-stated) MERGED with study 38 6p's row rules in ONE optimize patch. On a solve with
    j = len(prev) < k_book: C0 if its stack is C's (by identity) and fewer than n_c0 C0 slots are used (the slot is used either way);
    ONEPC if onepc and its stack is B's or C's ([(team T's WR / TE, "<=", 1)] for every team T in the records); FLEX if j < n_flex
    ([(the WR ids, ">=", 4)]). A solve with a lead rule: ONE call with row_cons + the lead constraints (the naked stack for C0);
    infeasible -> the solve at the cell's own stack with row_cons only, recorded in lead_plain; every solve then follows 6p's
    row_rules: row_cons, infeasible -> no constraint, recorded in plain. Spares (j >= k_book) never. Recorded on THIS class by name
    (89's own_caps subclasses it with its own lists)."""
    orig_cls, orig_opt = S24.CapBuilder, S24.optimize
    c_stack = S18.CELLS["C"][1]
    naked = dataclasses.replace(c_stack, qb_stack_min=0, qb_stack_max=0)
    target = {id(S18.CELLS[c][1]): c for c in S18.CELLS}
    qb1 = {id(S18.CELLS[c][1]) for c in QB1_CELLS}

    class LeadBuilder(orig_cls):
        ruled: list = []
        plain: list = []
        lead_ruled: list = []
        lead_plain: list = []
        c0_used: list = []

        def _solve(self, stack, qb_game_max, pair, extra_bans, cons):
            if cons:
                S24.optimize = partial(orig_opt, set_constraints=list(cons))
            try:
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            finally:
                S24.optimize = orig_opt

        def solve_with(self, stack, qb_game_max, pair, extra_bans: set):
            j = len(self.prev)
            if j >= k_book:
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            cell = target.get(id(stack), "?")
            use_c0 = stack is c_stack and len(LeadBuilder.c0_used) < n_c0
            use_oc = bool(onepc) and id(stack) in qb1
            use_fx = j < n_flex
            if use_c0:
                LeadBuilder.c0_used.append(j)
            lead: list = []
            if use_oc:
                by_team: dict = {}
                for p in self.recs:
                    if str(p["pos"]) in ("WR", "TE"):
                        by_team.setdefault(str(p["team"]), []).append(str(p["id"]))
                lead += [(ids, "<=", 1) for _, ids in sorted(by_team.items())]
            if use_fx:
                lead.append(([str(p["id"]) for p in self.recs if str(p["pos"]) == "WR"], ">=", 4))
            rules = tuple(r for r, u in (("c0", use_c0), ("onepc", use_oc), ("flex", use_fx)) if u)
            if use_c0 or lead:
                lu = self._solve(naked if use_c0 else stack, qb_game_max, pair, extra_bans, list(row_cons) + lead)
                if lu is not None:
                    LeadBuilder.lead_ruled.append((cell, j, rules)); LeadBuilder.ruled.append((cell, j))
                    return lu
                LeadBuilder.lead_plain.append((cell, j, rules))
            if row_cons:
                lu = self._solve(stack, qb_game_max, pair, extra_bans, row_cons)
                if lu is not None:
                    if not (use_c0 or lead):
                        LeadBuilder.ruled.append((cell, j))
                    return lu
                LeadBuilder.plain.append((cell, j))
            return super().solve_with(stack, qb_game_max, pair, extra_bans)

    LeadBuilder.ruled, LeadBuilder.plain, LeadBuilder.lead_ruled, LeadBuilder.lead_plain, LeadBuilder.c0_used = [], [], [], [], []
    S24.CapBuilder = LeadBuilder
    try:
        yield LeadBuilder
    finally:
        S24.CapBuilder, S24.optimize = orig_cls, orig_opt


# ---- one stand-in optimizer for both builds ----
FORCE_ALL_AT = {12}                 # a solve carrying ANY bound at these row indices is infeasible (-> no rule)
FORCE_OC_AT = {4, 5, 6, 21}         # a solve carrying MORE than the two row bounds (the one-catcher's) is infeasible (-> the row rules)


def pick(pool, obj_col, prev, bans, bounds):
    """The objective order (ties: id) rotated by the rows so far, skipping banned players and any player that would push a
    bounded set over its upper bound; 9 players or None. bounds: [(ids, hi)]."""
    j = len(prev)
    if bounds and (j in FORCE_ALL_AT or (len(bounds) > 2 and j in FORCE_OC_AT)):
        return None
    avail = [p for p in pool if not bans or p["id"] not in bans]
    order = sorted(avail, key=lambda p: (-float(p[obj_col]), str(p["id"])))
    if len(order) < 9:
        return None
    off = j % len(order)
    rot = order[off:] + order[:off]
    sets = [(set(ids), hi) for ids, hi in (bounds or [])]
    held = [0] * len(sets)
    out = []
    for p in rot:
        hit = [k for k, (ids, _) in enumerate(sets) if p["id"] in ids]
        if any(held[k] >= sets[k][1] for k in hit):
            continue
        out.append(p)
        for k in hit:
            held[k] += 1
        if len(out) == 9:
            return out
    return None


def install_production(monkeypatch):
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None,
                 interaction_floor_weights=None, interaction_floor=None, member_bounds=None):
        assert all(lo == 0 for _, lo, _ in (member_bounds or ()))
        got = pick(pool, objective_col, banned_lineups, bans, [(ids, hi) for ids, _, hi in (member_bounds or ())])
        return RR._PLU(got) if got is not None else None
    lineup = types.ModuleType("nfl2.core.lineup"); lineup.optimize = optimize; lineup.StackRules = T71.StackRules
    for name, mod in (("nfl2", types.ModuleType("nfl2")), ("nfl2.core", types.ModuleType("nfl2.core")), ("nfl2.core.lineup", lineup)):
        monkeypatch.setitem(sys.modules, name, mod)


def _lab_optimize(recs, stack, objective_col, banned_lineups, bans, set_constraints=None):
    assert all(op == "<=" for _, op, _ in (set_constraints or ()))
    got = pick(recs, objective_col, banned_lineups, bans, [(ids, hi) for ids, _, hi in (set_constraints or ())])
    return RR._LU(tuple(p["id"] for p in got)) if got is not None else None


class _TCapBuilder(RR._SCapBuilder):
    """6p's stand-in CapBuilder with the records' pos / team (the pasted lead_rules groups the WR / TE by team)."""

    def __init__(self, fr, base, lam, main_cap, dst_cap):
        super().__init__(fr, base, lam, main_cap, dst_cap)
        self.recs = [{"id": str(i), "obj": 0.0, "pos": str(p), "team": str(t)} for i, p, t in zip(fr["id"], fr["pos"], fr["team"])]


W, TERM = OC.W, OC.TERM


def frame() -> pd.DataFrame:
    """6p's fixture with each team's eight skill players ADJACENT in the objective order (team k // 8), so a stand-in row of
    nine neighbours holds two WR / TE of one team unless the rule binds."""
    fr = OC.frame()
    k = np.arange(len(fr))
    skill = fr.pos != "DST"
    t = (k // 8) % 12
    fr.loc[skill, "team"] = [f"T{x}" for x in t[skill.to_numpy()]]
    fr.loc[skill, "opp"] = [f"T{x ^ 1}" for x in t[skill.to_numpy()]]
    fr.loc[skill, "game_id"] = [f"g{x // 2}" for x in t[skill.to_numpy()]]
    return fr


def inputs(tmp_path):
    fr = frame()
    p = OC.fp_file(tmp_path, fr)
    caps, _ = ur.own_cap_rows(p, fr, set(), 15.0, 26, 0.9)
    te, low, _ = ur.row_rule_sets(p, fr, set(), 3.0)
    return fr, caps, [(te, 0, 1), (low, 0, 1)], [(sorted(te), "<=", 1), (sorted(low), "<=", 1)]


def production_book(monkeypatch, fr, own_cap, bounds, one_catcher, mod=ur, k=26, spares=15):
    install_production(monkeypatch)
    rows, cells, meta, sp = mod.mix_rows(fr, set(), k, 9, None, 0, W, exposure_cap=13, dst_cap=6, fill="rr", spares=spares,
                                         term_rows=8, term_bonus=TERM, own_cap=own_cap, row_bounds=bounds, one_catcher=one_catcher)
    return [list(r) for r in rows], list(cells), meta, [list(r) for r, _ in sp]


def lab_book(monkeypatch, fr, cap_rows, cons, k_book=26, k=41):
    monkeypatch.setattr(T71, "S18", S18); monkeypatch.setattr(OC, "S18", S18)     # the term_book and own_caps find these stacks
    base = fr.mean_projection.to_numpy(float)
    term = np.array([TERM.get(i, 0.0) for i in fr.id])
    S24.CapBuilder, S24.optimize = _TCapBuilder, _lab_optimize
    try:
        with lead_rules(0, True, 0, cons, k_book) as R, OC.own_caps(cap_rows, k_book) as T:
            book, cells, mt = T71.term_book(fr, base, term, (13, 6), W, k_book, 8, k=k)
            rec = {"lead_ruled": [(c, j) for c, j, _ in R.lead_ruled], "lead_plain": [(c, j) for c, j, _ in R.lead_plain],
                   "plain": list(R.plain), "own_plain": list(T.plain), "rules": {r for _, _, r in R.lead_ruled + R.lead_plain}}
    finally:
        S24.CapBuilder, S24.optimize = T71._HCapBuilder, None
    rows = [list(lu.ids) for lu in book]
    return rows[:k_book], rows[k_book:], rec


def paired(r, fr) -> bool:
    team = dict(zip(fr.id.astype(str), fr.team.astype(str))); pos = dict(zip(fr.id.astype(str), fr.pos.astype(str)))
    return max(Counter(team[i] for i in r if pos[i] in ("WR", "TE")).values(), default=0) > 1


def mutant(old: str, new: str):
    """union_reselect with ONE code change (the text must occur exactly once), loaded as its own module."""
    path = ROOT / "scripts" / "union_reselect.py"
    src = path.read_text()
    assert src.count(old) == 1, old
    mod = types.ModuleType("union_reselect_mutant"); mod.__file__ = str(path)
    exec(compile(src.replace(old, new), str(path), "exec"), mod.__dict__)
    return mod


# ---- the tests ----
def test_the_pasted_lab_text_is_the_labs():
    src = (ROOT / "tests" / "test_one_catcher_all_flag.py").read_text()
    lines = src.splitlines(keepends=True)
    seen = set()
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in LAB_TEXT_SHA256:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            assert hashlib.sha256("".join(lines[start - 1:node.end_lineno]).encode()).hexdigest() == LAB_TEXT_SHA256[node.name], node.name
            seen.add(node.name)
    assert seen == set(LAB_TEXT_SHA256)


def test_the_book_equals_93s_onecatch_inside_89s_own_caps(monkeypatch, tmp_path):
    fr, caps, bounds, cons = inputs(tmp_path)
    book_p, cells_p, meta, spares_p = production_book(monkeypatch, fr, caps, bounds, True)
    book_l, spares_l, rec = lab_book(monkeypatch, fr, caps, cons)
    assert book_p == book_l and spares_p == spares_l
    oc = meta["one_catcher"]
    assert [tuple(x) for x in oc["ruled"]] == rec["lead_ruled"] and [tuple(x) for x in oc["resolved_without"]] == rec["lead_plain"]
    assert [tuple(x) for x in meta["row_rules"]["resolved_without"]] == rec["plain"]
    assert [tuple(x) for x in meta["own_cap"]["resolved_without"]] == rec["own_plain"] and rec["rules"] == {("onepc",)}
    # both forced paths were exercised: the one-catcher dropped with the row rules kept, and every bound dropped
    assert rec["lead_plain"] and {j for _, j in rec["lead_plain"]} <= FORCE_OC_AT | FORCE_ALL_AT
    assert rec["plain"] and {j for _, j in rec["plain"]} <= FORCE_ALL_AT
    # B / C only (A1 / A2 never), the live AND the term block (j 18..25), never a spare
    assert {c for c, _ in oc["ruled"] + oc["resolved_without"]} <= {"B", "C"}
    assert any(j < 18 for _, j in oc["ruled"]) and any(18 <= j < 26 for _, j in oc["ruled"]) and all(j < 26 for _, j in oc["ruled"])
    # the receipt: one identity per ruled row, each in the book and holding at most one WR / TE of every team
    assert oc["ruled_solves"] == len(oc["ruled"]) == len(oc["ruled_rows"]) and oc["cells"] == ["B", "C"]
    assert oc["teams"] == fr[fr.pos.isin(["WR", "TE"])].team.nunique() == 11          # T11 holds only a QB and an RB
    sets = {frozenset(r) for r in book_p}
    assert all(frozenset(f["row"]) in sets and not paired(f["row"], fr) for f in oc["ruled_rows"])
    assert oc["pair_rows_bc"] == sum(1 for r, c in zip(book_p, cells_p) if c in ("B", "C") and paired(r, fr))
    assert oc["pair_rows_bc"] <= len(oc["resolved_without"])


def test_the_rule_binds_on_this_fixture(monkeypatch, tmp_path):
    fr, caps, bounds, _ = inputs(tmp_path)
    off, cells_off, meta_off, sp_off = production_book(monkeypatch, fr, caps, bounds, False)
    on, cells_on, meta_on, sp_on = production_book(monkeypatch, fr, caps, bounds, True)
    off_bc = sum(1 for r, c in zip(off, cells_off) if c in ("B", "C") and paired(r, fr))
    assert off_bc >= 3 and off != on                                    # without it, B / C rows hold same-team catcher pairs
    assert meta_on["one_catcher"]["pair_rows_bc"] < off_bc
    ruled_a = {(c, j) for c, j in meta_on["own_cap"]["resolved_without"]}
    assert not ruled_a                                                  # the ownership cap never fell back here


def test_off_is_the_row_rules_call_exactly(monkeypatch, tmp_path):
    fr, caps, bounds, _ = inputs(tmp_path)
    install_production(monkeypatch)
    a = ur.mix_rows(fr, set(), 26, 9, None, 0, W, exposure_cap=13, dst_cap=6, fill="rr", spares=15, term_rows=8, term_bonus=TERM,
                    own_cap=caps, row_bounds=bounds)
    b = production_book(monkeypatch, fr, caps, bounds, False)
    assert [list(r) for r in a[0]] == b[0] and list(a[1]) == b[1] and [list(r) for r, _ in a[3]] == b[3]
    assert "one_catcher" not in a[2] and "one_catcher" not in b[2]
    with pytest.raises(ValueError, match="one_catcher needs row_bounds"):
        production_book(monkeypatch, fr, caps, None, True)


@pytest.mark.parametrize("old,new", [
    ("oc_bounds = [(sorted(ids), 0, 1) for _, ids in sorted(oc_team.items())]",
     "oc_bounds = [(sorted(ids), 0, 2) for _, ids in sorted(oc_team.items())]"),           # two catchers a team allowed
    ("if oc_bounds and name in ONE_CATCHER_CELLS:", "if oc_bounds:"),                       # A1 / A2 ruled too
    ("if oc_bounds and name in ONE_CATCHER_CELLS:",
     "if oc_bounds and name in ONE_CATCHER_CELLS and not use_term:"),                       # the term block's B / C left out
])
def test_a_mutated_rule_is_caught(monkeypatch, tmp_path, old, new):
    fr, caps, bounds, cons = inputs(tmp_path)
    book_m, _, _, spares_m = production_book(monkeypatch, fr, caps, bounds, True, mod=mutant(old, new))
    book_l, spares_l, _ = lab_book(monkeypatch, fr, caps, cons)
    assert (book_m, spares_m) != (book_l, spares_l)


def test_the_cli_refuses_it_off_the_armed_version():
    base = ["--saturday-run", "x", "--t70-run", "y", "--live-dir", "z", "--entries", "26", "--main", "mix"]
    own = ["--main-own-cap-delta", "15", "--main-own-cap-source", "f.csv", "--main-own-cap-fallback-share", "0.5"]
    armed = ["--mix-portfolio", "mix", "--mix-fill", "rr", "--mix-max-te", "1", "--mix-max-low-own", "1"]
    for extra in ([], ["--mix-max-te", "1"], own + ["--mix-max-te", "1", "--mix-portfolio", "mix", "--mix-fill", "rr"],
                  own + ["--mix-portfolio", "mix", "--mix-fill", "group", "--mix-max-te", "1", "--mix-max-low-own", "1"],
                  own + ["--mix-fill", "rr", "--mix-max-te", "1", "--mix-max-low-own", "1"],                    # no portfolio
                  own + armed + ["--mix-cover-games", "2"], own + armed + ["--mix-rs-rows", "8"]):
        with pytest.raises(SystemExit, match="defined on his armed version only|defined for --main mix with the ownership cap"):
            ur.main(base + extra + ["--mix-one-catcher-all"])
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert "!!! ONE CATCHER NOT APPLIED" in src and '"the row rules are not applied"' in src
    assert src.count("one_catcher=oc_on, rb_mate_c=rm_c)") == 2 and 'mix_meta["one_catcher_source"] = oc_meta' in src


def test_the_audit_reads_the_ruled_rows(tmp_path):
    """audit_build_levers' one_catcher check: every ruled row (by identity) a main row with at most one WR / TE per team."""
    clean = ["AQB", "AWR1", "BRB1", "CRB0", "CWR0", "DTE", "EWR2", "FRB0", "G_DST"]
    L = ABL_T._lineup
    lus = [clean, L("A", "B", "C"), L("C", "D", "E"), L("E", "F", "G"), L("G", "H", "A"), L("B", "A", "D")]
    tail = ABL_T.CONTESTS + [{"name": "milly", "contest_id": "9", "entries": 1, "keep": 1, "track": "tail"}]
    base = {"selector": "mean", "operational_k": 5, "tail_sleeve": {"rows": 1, "selector_used": "mean"}}

    def run(tmp, inner):
        mix_meta = {"exposure_cap": 3, "max_exposure_used": 3, "dst_cap": 2, "max_dst_rows_used": 2, "mix": {"cells": {"A1": {"rows": 5}}, **inner}}
        r = ABL_T._run_dir(tmp, lineups=lus, book=lus[:6], receipt={"written": 6, "config": {**base, "union": {"main": "mix", "mix": mix_meta}}})
        c = pd.read_parquet(r / "candidates.parquet"); c["source_run"] = ["mix"] * 5 + ["saturday"]; c["tag"] = ["mix_B"] * 5 + ["lev"]
        c["book_rank"] = [1, 2, 3, 4, 5, None]; c.to_parquet(r / "candidates.parquet")
        out = ABL_T._audit(r, contests=tail, expect_selector="mean")
        return "one_catcher" in out["failed"], next(x for x in out["checks"] if x["check"] == "one_catcher")

    block = lambda rows, n=None: {"one_catcher": {"ruled_solves": len(rows) if n is None else n, "resolved_without": [],  # noqa: E731
                                                  "ruled_rows": [{"row": sorted(r)} for r in rows]}}
    assert run(tmp_path / "a", block([clean]))[0] is False                                  # clean, in the main book
    assert run(tmp_path / "b", block([lus[1]]))[0] is True                                  # two WR of one team
    assert run(tmp_path / "c", block([clean], n=2))[0] is True                              # a ruled solve without its row
    assert run(tmp_path / "d", {})[0] is False                                              # off
    failed, rec = run(tmp_path / "e", {"one_catcher_source": {"applied": False, "not_applied": "the row rules are not applied"}})
    assert failed is False and "NOT APPLIED" in rec["detail"]
