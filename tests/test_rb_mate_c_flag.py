"""Study 96's RB mate on the live MIX book (the operator 10-09: "Try live W5 if built"): union_reselect's mix_rows(row_bounds=[te1,
low1], one_catcher=True, rb_mate_c=4) against the lab's OWN code -- nfl2 experiments/s96_onecatch_rbmate.py @ 3cf3e8eb's
combo_rules and s94_rb_pairs.py @ 2eb7835b's rb_pairs pasted BELOW byte for byte (each text sha-pinned), entered before study
89's own_caps on the lab's term_book, with ONE stand-in optimizer that reads the lab's set_constraints / interaction floor and
production's member_bounds / interaction floor alike (a floored row seeds a pair, then fills), on the fixture where ONECATCH
binds (test_one_catcher_all_flag's). Forced infeasibles: a floored solve at some rows (the floor dropped, ONECATCH kept), a
one-catcher solve at another, every bound at a third. The same 26 book rows, 15 spares and records; off = the ONECATCH call;
three code mutations caught; the CLI refusals; the audit check. Production's pin takes the interaction floor itself (study 71's
floor uses it), so no member-bound substitute is needed."""
import ast
import hashlib
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


OCT = _load("one_catcher_helpers_rm", ROOT / "tests" / "test_one_catcher_all_flag.py")   # the binding fixture, stacks, builders
RR, OC, T71, ABL_T = OCT.RR, OCT.OC, OCT.T71, OCT.ABL_T
S18, S24 = OCT.S18, OCT.S24                         # the pasted lab code below reads these names (dataclass stacks)
QB1_CELLS = ("B", "C")
LAB_TEXT_SHA256 = {"rb_pairs": "5e961923c034f19b4c1745cced483a17592c8de4140cef396e2a4a7c438ffb76",
                   "combo_rules": "66ed0eff4a6018adcbb1d883adf07ceba64fef8780c9a7d070f01a1d00c93975"}


# ---- nfl2 experiments/s94_rb_pairs.py @ 2eb7835b (rb_pairs) and s96_onecatch_rbmate.py @ 3cf3e8eb (combo_rules), BYTE FOR BYTE ----
def rb_pairs(fr_pool: pd.DataFrame) -> dict[str, dict]:
    """(QB, an RB of the QB's team) and (DST, an RB of the DST's team) pairs over the pool, weight 1."""
    ids = fr_pool.id.astype(str).tolist(); pos = fr_pool.pos.astype(str).tolist(); team = fr_pool.team.astype(str).tolist()
    rbs: dict = {}
    for i, p, t in zip(ids, pos, team):
        if p == "RB":
            rbs.setdefault(t, []).append(i)
    qb_rb = {(i, r): 1.0 for i, p, t in zip(ids, pos, team) if p == "QB" for r in rbs.get(t, [])}
    dst_rb = {(i, r): 1.0 for i, p, t in zip(ids, pos, team) if p == "DST" for r in rbs.get(t, [])}
    return {"qb_rb": qb_rb, "dst_rb": dst_rb}


@contextmanager
def combo_rules(n_rbmate: int, row_cons: list, k_book: int, qb_rb: dict):
    """ONECATCH (study 93) and RBMATE (study 94) in ONE optimize patch per solve. On a solve with j = len(prev) < k_book:
    use_oc if its stack is B's or C's (by identity): [(team T's WR / TE ids, "<=", 1) for every team T in the records, sorted
    by team] (93's text); use_rm if its stack is C's and fewer than n_rbmate RBMATE slots are used -- the slot is taken at once,
    ruled or not (94's), so an ownership-cap re-solve takes another. Tiers: T1 row_cons + oc with the interaction floor over
    qb_rb (weight 1, floor 1) in the same call -> T2 row_cons + oc -> T3 row_cons -> T4 none. Recorded on THIS class by name
    (89's own_caps subclasses it): rm_used, rm_ruled, rm_plain, oc_ruled, oc_plain, ruled, plain, each (cell, j). Spares never."""
    orig_cls, orig_opt = S24.CapBuilder, S24.optimize
    c_stack = S18.CELLS["C"][1]
    target = {id(S18.CELLS[c][1]): c for c in S18.CELLS}
    qb1 = {id(S18.CELLS[c][1]) for c in QB1_CELLS}

    class ComboBuilder(orig_cls):
        rm_used: list = []
        rm_ruled: list = []
        rm_plain: list = []
        oc_ruled: list = []
        oc_plain: list = []
        ruled: list = []
        plain: list = []

        def _solve(self, stack, qb_game_max, pair, extra_bans, cons, floor):
            kw = {}
            if cons:
                kw["set_constraints"] = list(cons)
            if floor:
                kw.update(interaction_floor_weights=dict(floor), interaction_floor=1.0)
            if kw:
                S24.optimize = partial(orig_opt, **kw)
            try:
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            finally:
                S24.optimize = orig_opt

        def solve_with(self, stack, qb_game_max, pair, extra_bans: set):
            j = len(self.prev)
            if j >= k_book:
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            cell = target.get(id(stack), "?")
            use_oc = id(stack) in qb1
            use_rm = stack is c_stack and len(ComboBuilder.rm_used) < n_rbmate
            if use_rm:
                ComboBuilder.rm_used.append((cell, j))
            oc: list = []
            if use_oc:
                by_team: dict = {}
                for p in self.recs:
                    if str(p["pos"]) in ("WR", "TE"):
                        by_team.setdefault(str(p["team"]), []).append(str(p["id"]))
                oc = [(ids, "<=", 1) for _, ids in sorted(by_team.items())]
            if use_rm:
                lu = self._solve(stack, qb_game_max, pair, extra_bans, list(row_cons) + oc, qb_rb)
                if lu is not None:
                    ComboBuilder.rm_ruled.append((cell, j)); ComboBuilder.oc_ruled.append((cell, j)); ComboBuilder.ruled.append((cell, j))
                    return lu
                ComboBuilder.rm_plain.append((cell, j))
            if use_oc:
                lu = self._solve(stack, qb_game_max, pair, extra_bans, list(row_cons) + oc, None)
                if lu is not None:
                    ComboBuilder.oc_ruled.append((cell, j)); ComboBuilder.ruled.append((cell, j))
                    return lu
                ComboBuilder.oc_plain.append((cell, j))
            if row_cons:
                lu = self._solve(stack, qb_game_max, pair, extra_bans, row_cons, None)
                if lu is not None:
                    ComboBuilder.ruled.append((cell, j))
                    return lu
                ComboBuilder.plain.append((cell, j))
            return super().solve_with(stack, qb_game_max, pair, extra_bans)

    (ComboBuilder.rm_used, ComboBuilder.rm_ruled, ComboBuilder.rm_plain, ComboBuilder.oc_ruled, ComboBuilder.oc_plain,
     ComboBuilder.ruled, ComboBuilder.plain) = [], [], [], [], [], [], []
    S24.CapBuilder = ComboBuilder
    try:
        yield ComboBuilder
    finally:
        S24.CapBuilder, S24.optimize = orig_cls, orig_opt



# ---- one stand-in optimizer for both builds (floors honoured) ----
FORCE_ALL_AT = {12}                 # a solve carrying ANY bound at these row indices is infeasible
FORCE_OC_AT = {21}                  # a solve carrying more than the two row bounds is infeasible
FORCE_FLOOR_AT = set()              # a FLOORED solve at these row indices is infeasible (set per test)
TRIGGER_AT = set()                  # with TRIGGER_ID banned (his ownership cap reached) a solve at these rows is infeasible:
TRIGGER_ID = "p0"                   # every tier fails WITH the cap's bans, so 89's ownership cap re-peeks without them


def pick(pool, obj_col, prev, bans, bounds, floor=None):
    """6p's stand-in (the objective order rotated by the rows so far, banned players skipped, every bound held) and, with a
    floor, the first pool pair (sorted) whose two players seed a fillable row; 9 players or None."""
    j = len(prev)
    if j in TRIGGER_AT and TRIGGER_ID in set(bans or ()):
        return None
    if bounds and (j in FORCE_ALL_AT or (len(bounds) > 2 and j in FORCE_OC_AT)):
        return None
    if floor and j in FORCE_FLOOR_AT:
        return None
    avail = [p for p in pool if not bans or p["id"] not in bans]
    order = sorted(avail, key=lambda p: (-float(p[obj_col]), str(p["id"])))
    if len(order) < 9:
        return None
    off = j % len(order)
    rot = order[off:] + order[:off]
    sets = [(set(ids), hi) for ids, hi in (bounds or [])]

    def fill(seed):
        held, out, ids = [0] * len(sets), [], {p["id"] for p in seed}
        for p in seed + [q for q in rot if q["id"] not in ids]:
            hit = [k for k, (s, _) in enumerate(sets) if p["id"] in s]
            if any(held[k] >= sets[k][1] for k in hit):
                if p["id"] in ids:
                    return None
                continue
            out.append(p)
            for k in hit:
                held[k] += 1
            if len(out) == 9:
                return out
        return None
    if not floor:
        return fill([])
    by_id = {p["id"]: p for p in avail}
    for a, b in sorted(tuple(sorted(map(str, k))) for k in floor):
        if a in by_id and b in by_id:
            got = fill([by_id[a], by_id[b]])
            if got is not None:
                return got
    return None


def install_production(monkeypatch):
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None,
                 interaction_floor_weights=None, interaction_floor=None, member_bounds=None):
        assert all(lo == 0 for _, lo, _ in (member_bounds or ())) and (interaction_floor_weights is None) == (interaction_floor is None)
        assert interaction_floor in (None, 1.0)
        got = pick(pool, objective_col, banned_lineups, bans, [(ids, hi) for ids, _, hi in (member_bounds or ())],
                   interaction_floor_weights)
        return RR._PLU(got) if got is not None else None
    lineup = types.ModuleType("nfl2.core.lineup"); lineup.optimize = optimize; lineup.StackRules = T71.StackRules
    for name, mod in (("nfl2", types.ModuleType("nfl2")), ("nfl2.core", types.ModuleType("nfl2.core")), ("nfl2.core.lineup", lineup)):
        monkeypatch.setitem(sys.modules, name, mod)


def _lab_optimize(recs, stack, objective_col, banned_lineups, bans, set_constraints=None, interaction_floor_weights=None,
                  interaction_floor=None):
    assert all(op == "<=" for _, op, _ in (set_constraints or ())) and interaction_floor in (None, 1.0)
    got = pick(recs, objective_col, banned_lineups, bans, [(ids, hi) for ids, _, hi in (set_constraints or ())],
               interaction_floor_weights)
    return RR._LU(tuple(p["id"] for p in got)) if got is not None else None


W, TERM = OC.W, OC.TERM


def production_book(monkeypatch, fr, own_cap, bounds, rb_mate_c, mod=ur, one_catcher=True, k=26, spares=15):
    install_production(monkeypatch)
    rows, cells, meta, sp = mod.mix_rows(fr, set(), k, 9, None, 0, W, exposure_cap=13, dst_cap=6, fill="rr", spares=spares,
                                         term_rows=8, term_bonus=TERM, own_cap=own_cap, row_bounds=bounds, one_catcher=one_catcher,
                                         rb_mate_c=rb_mate_c)
    return [list(r) for r in rows], list(cells), meta, [list(r) for r, _ in sp]


def lab_book(monkeypatch, fr, cap_rows, cons, n_rbmate=4, k_book=26, k=41):
    monkeypatch.setattr(T71, "S18", S18); monkeypatch.setattr(OC, "S18", S18)
    base = fr.mean_projection.to_numpy(float)
    term = np.array([TERM.get(i, 0.0) for i in fr.id])
    S24.CapBuilder, S24.optimize = OCT._TCapBuilder, _lab_optimize
    try:
        with combo_rules(n_rbmate, cons, k_book, rb_pairs(fr)["qb_rb"]) as R, OC.own_caps(cap_rows, k_book) as T:
            book, cells, mt = T71.term_book(fr, base, term, (13, 6), W, k_book, 8, k=k)
            rec = {k_: list(getattr(R, k_)) for k_ in ("rm_used", "rm_ruled", "rm_plain", "oc_ruled", "oc_plain", "plain")}
            rec["own_plain"] = list(T.plain)
    finally:
        S24.CapBuilder, S24.optimize = T71._HCapBuilder, None
    rows = [list(lu.ids) for lu in book]
    return rows[:k_book], rows[k_book:], rec


def own_rb(r, fr) -> bool:
    team = dict(zip(fr.id.astype(str), fr.team.astype(str))); pos = dict(zip(fr.id.astype(str), fr.pos.astype(str)))
    qbs = [i for i in r if pos[i] == "QB"]
    return any(pos[i] == "RB" and team[i] == team[q] for q in qbs for i in r)


def mutant(old: str, new: str):
    return OCT.mutant(old, new)


# ---- the tests ----
def test_the_pasted_lab_text_is_the_labs():
    src = (ROOT / "tests" / "test_rb_mate_c_flag.py").read_text()
    lines = src.splitlines(keepends=True)
    seen = set()
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in LAB_TEXT_SHA256:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            assert hashlib.sha256("".join(lines[start - 1:node.end_lineno]).encode()).hexdigest() == LAB_TEXT_SHA256[node.name], node.name
            seen.add(node.name)
    assert seen == set(LAB_TEXT_SHA256)


def test_the_pairs_equal_94s(tmp_path):
    fr = OCT.frame()
    install = {(str(q), str(r)) for q, r in rb_pairs(fr)["qb_rb"]}
    team = dict(zip(fr.id.astype(str), fr.team.astype(str))); pos = dict(zip(fr.id.astype(str), fr.pos.astype(str)))
    assert install == {(q, r) for q in team for r in team if pos[q] == "QB" and pos[r] == "RB" and team[q] == team[r]} and install


@pytest.mark.parametrize("floor_at", [set(), "first_slot"])
def test_the_book_equals_96s_combo_inside_89s_own_caps(monkeypatch, tmp_path, floor_at):
    fr, caps, bounds, cons = OCT.inputs(tmp_path)
    if floor_at == "first_slot":                       # force the first floored solve infeasible: the floor dropped, the slot used
        _, _, meta0, _ = production_book(monkeypatch, fr, caps, bounds, 4)
        monkeypatch.setattr(sys.modules[__name__], "FORCE_FLOOR_AT", {meta0["rb_mate"]["slots"][0][1]})
    book_p, cells_p, meta, spares_p = production_book(monkeypatch, fr, caps, bounds, 4)
    book_l, spares_l, rec = lab_book(monkeypatch, fr, caps, cons)
    assert book_p == book_l and spares_p == spares_l
    rm, oc = meta["rb_mate"], meta["one_catcher"]
    assert [tuple(x) for x in rm["slots"]] == rec["rm_used"] and [tuple(x) for x in rm["ruled"]] == rec["rm_ruled"]
    assert [tuple(x) for x in rm["resolved_without"]] == rec["rm_plain"]
    assert [tuple(x) for x in oc["ruled"]] == rec["oc_ruled"] and [tuple(x) for x in oc["resolved_without"]] == rec["oc_plain"]
    assert [tuple(x) for x in meta["row_rules"]["resolved_without"]] == rec["plain"]
    assert [tuple(x) for x in meta["own_cap"]["resolved_without"]] == rec["own_plain"]
    assert len(rm["slots"]) == 4 and {c for c, _ in rm["slots"]} == {"C"} and all(j < 26 for _, j in rm["slots"])
    assert rm["pairs"] == len(rb_pairs(fr)["qb_rb"]) and rm["cell"] == "C" and rm["rows_cap"] == 4
    assert len(rm["ruled"]) == len(rm["ruled_rows"]) and all(own_rb(f["row"], fr) for f in rm["ruled_rows"])
    sets = {frozenset(r) for r in book_p}
    assert all(frozenset(f["row"]) in sets for f in rm["ruled_rows"])
    if floor_at == "first_slot":
        assert len(rm["resolved_without"]) == 1 and len(rm["ruled"]) == 3              # the slot is used either way
    else:
        assert rm["resolved_without"] == [] and len(rm["ruled"]) == 4
    assert {j for _, j in rec["oc_plain"]} <= FORCE_OC_AT | FORCE_ALL_AT and {j for _, j in rec["plain"]} <= FORCE_ALL_AT


def test_the_floor_changes_the_book_and_off_is_the_onecatch_call(monkeypatch, tmp_path):
    fr, caps, bounds, _ = OCT.inputs(tmp_path)
    off = production_book(monkeypatch, fr, caps, bounds, 0)
    on = production_book(monkeypatch, fr, caps, bounds, 4)
    assert off[0] != on[0] and "rb_mate" not in off[2] and "rb_mate" in on[2]
    install_production(monkeypatch)
    a = ur.mix_rows(fr, set(), 26, 9, None, 0, W, exposure_cap=13, dst_cap=6, fill="rr", spares=15, term_rows=8, term_bonus=TERM,
                    own_cap=caps, row_bounds=bounds, one_catcher=True)
    assert [list(r) for r in a[0]] == off[0] and list(a[1]) == off[1] and [list(r) for r, _ in a[3]] == off[3]
    with pytest.raises(ValueError, match="rb_mate_c 4 needs one_catcher"):
        production_book(monkeypatch, fr, caps, bounds, 4, one_catcher=False)


@pytest.mark.parametrize("old,new", [
    ('if rb_mate_c and name == "C" and len(rm_state["used"]) < int(rb_mate_c):',
     'if rb_mate_c and name == "B" and len(rm_state["used"]) < int(rb_mate_c):'),                # the wrong cell
    ('if rb_mate_c and name == "C" and len(rm_state["used"]) < int(rb_mate_c):',
     'if rb_mate_c and name == "C" and len(rm_state["ruled"]) < int(rb_mate_c):'),               # a dropped floor frees its slot
    ("got = _solve(name, extra_bans, use_term, rbx + oc_bounds, rm_pairs)  # no pair",
     "got = _solve(name, extra_bans, use_term, rbx, rm_pairs)  # no pair"),                                     # ONECATCH left out of the floor tier
])
def test_a_mutated_rule_is_caught(monkeypatch, tmp_path, old, new):
    fr, caps, bounds, cons = OCT.inputs(tmp_path)
    _, _, meta0, _ = production_book(monkeypatch, fr, caps, bounds, 4)
    monkeypatch.setattr(sys.modules[__name__], "FORCE_FLOOR_AT", {meta0["rb_mate"]["slots"][0][1]})
    book_m, _, _, spares_m = production_book(monkeypatch, fr, caps, bounds, 4, mod=mutant(old, new))
    book_l, spares_l, _ = lab_book(monkeypatch, fr, caps, cons)
    assert (book_m, spares_m) != (book_l, spares_l)


def test_the_cli_refuses_it_off_onecatch():
    base = ["--saturday-run", "x", "--t70-run", "y", "--live-dir", "z", "--entries", "26", "--main", "mix"]
    own = ["--main-own-cap-delta", "15", "--main-own-cap-source", "f.csv", "--main-own-cap-fallback-share", "0.5"]
    armed = ["--mix-portfolio", "mix", "--mix-fill", "rr", "--mix-max-te", "1", "--mix-max-low-own", "1"]
    for extra in (own + armed + ["--mix-rb-mate-c", "4"], own + armed + ["--mix-one-catcher-all", "--mix-rb-mate-c", "3"],
                  own + armed + ["--mix-one-catcher-all", "--mix-rb-mate-c", "8"]):
        with pytest.raises(SystemExit, match="--mix-rb-mate-c takes 0 or 4"):
            ur.main(base + extra)
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert "!!! RB MATE NOT APPLIED" in src and '"ONECATCH is not applied"' in src
    assert src.count("one_catcher=oc_on, rb_mate_c=rm_c,") == 2 and 'mix_meta["rb_mate_source"] = rm_meta' in src


def test_the_audit_reads_the_ruled_rows(tmp_path):
    """audit_build_levers' rb_mate check: every ruled row (by identity) a main row holding its QB and an RB of the QB's team."""
    good = ["AQB", "AWR1", "ARB0", "CRB0", "CWR0", "DTE", "EWR2", "FRB0", "G_DST"]          # A's QB with A's RB0
    bad = ["AQB", "AWR1", "BRB1", "CRB0", "CWR0", "DTE", "EWR2", "FRB0", "G_DST"]           # no A RB
    L = ABL_T._lineup
    lus = [good, bad, L("C", "D", "E"), L("E", "F", "G"), L("G", "H", "A"), L("B", "A", "D")]
    tail = ABL_T.CONTESTS + [{"name": "milly", "contest_id": "9", "entries": 1, "keep": 1, "track": "tail"}]
    base = {"selector": "mean", "operational_k": 5, "tail_sleeve": {"rows": 1, "selector_used": "mean"}}

    def run(tmp, inner):
        mix_meta = {"exposure_cap": 3, "max_exposure_used": 3, "dst_cap": 2, "max_dst_rows_used": 2, "mix": {"cells": {"A1": {"rows": 5}}, **inner}}
        r = ABL_T._run_dir(tmp, lineups=lus, book=lus[:6], receipt={"written": 6, "config": {**base, "union": {"main": "mix", "mix": mix_meta}}})
        c = pd.read_parquet(r / "candidates.parquet"); c["source_run"] = ["mix"] * 5 + ["saturday"]; c["tag"] = ["mix_C"] * 5 + ["lev"]
        c["book_rank"] = [1, 2, 3, 4, 5, None]; c.to_parquet(r / "candidates.parquet")
        out = ABL_T._audit(r, contests=tail, expect_selector="mean")
        return "rb_mate" in out["failed"], next(x for x in out["checks"] if x["check"] == "rb_mate")

    block = lambda rows: {"rb_mate": {"rows_cap": 4, "slots": [["C", 0]] * len(rows), "ruled": [["C", 0]] * len(rows),  # noqa: E731
                                      "resolved_without": [], "ruled_rows": [{"row": sorted(r)} for r in rows]}}
    assert run(tmp_path / "a", block([good]))[0] is False
    assert run(tmp_path / "b", block([bad]))[0] is True                                    # no RB of the QB's team
    assert run(tmp_path / "c", {})[0] is False                                             # off
    failed, rec = run(tmp_path / "d", {"rb_mate_source": {"applied": False, "not_applied": "ONECATCH is not applied"}})
    assert failed is False and "NOT APPLIED" in rec["detail"]


def test_an_own_cap_re_peek_takes_another_slot_as_the_lab(monkeypatch, tmp_path):
    """89's ownership cap falls back (every tier infeasible WITH its bans) on the FIRST RBMATE slot, so the solve is re-run
    without the bans: the lab's OwnCapBuilder calls combo_rules' solve_with again, which takes ANOTHER slot (94 / 96);
    production's peek re-runs _peek, which does the same. TRIGGER_ID gets an ownership cap of one row, so from his first row on
    every solve bans him. Rows, spares and every record agree, and the re-peek used two slots on one (cell, j)."""
    fr, caps, bounds, cons = OCT.inputs(tmp_path)
    caps = dict(caps, **{TRIGGER_ID: 1})
    _, _, meta0, _ = production_book(monkeypatch, fr, caps, bounds, 4)
    j0 = meta0["rb_mate"]["slots"][0][1]
    monkeypatch.setattr(sys.modules[__name__], "TRIGGER_AT", {j0})
    book_p, _, meta, spares_p = production_book(monkeypatch, fr, caps, bounds, 4)
    book_l, spares_l, rec = lab_book(monkeypatch, fr, caps, cons)
    assert book_p == book_l and spares_p == spares_l and ("C", j0) in rec["own_plain"]       # the re-peek happened at the slot
    assert [tuple(x) for x in meta["own_cap"]["resolved_without"]] == rec["own_plain"]
    slots = [tuple(x) for x in meta["rb_mate"]["slots"]]
    assert slots == rec["rm_used"] and slots[:2] == [("C", j0), ("C", j0)] and len(slots) == 4    # two slots on one (cell, j)
    assert [tuple(x) for x in meta["rb_mate"]["ruled"]] == rec["rm_ruled"] and [tuple(x) for x in meta["rb_mate"]["resolved_without"]] == rec["rm_plain"]
    assert ("C", j0) in rec["rm_plain"] and ("C", j0) in rec["rm_ruled"]                         # dropped with the bans, ruled without


def test_no_pair_in_the_pool_takes_the_slots_without_a_floor_as_the_lab(monkeypatch, tmp_path):
    """A pool with no (QB, own RB) pair: the lab's T1 carries no floor (an empty dict) and takes the slot; production the same,
    its receipt saying pairs 0 (the audit then fails closed on rows without the pair)."""
    fr, caps, bounds, cons = OCT.inputs(tmp_path)
    fr = fr[fr.pos != "RB"].reset_index(drop=True)
    book_p, _, meta, spares_p = production_book(monkeypatch, fr, caps, bounds, 4)
    book_l, spares_l, rec = lab_book(monkeypatch, fr, caps, cons)
    assert book_p == book_l and spares_p == spares_l and meta["rb_mate"]["pairs"] == 0 == len(rb_pairs(fr)["qb_rb"])
    assert [tuple(x) for x in meta["rb_mate"]["slots"]] == rec["rm_used"] and len(rec["rm_used"]) == 4
