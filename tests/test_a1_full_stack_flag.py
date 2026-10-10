"""Study 102's TAIL_STACK8 on the live MIX book (the operator 10-09: "It sounds like you're giving up on the high scores. That's
not what I want."): union_reselect's mix_rows(row_bounds=[te1, low1], one_catcher=True, a1_full_stack=True) against the lab's OWN
code -- nfl2 experiments/s102_ceiling_build.py @ 4bdfafd4's tail_rules and arm_rules and s73_topg_qb1.py's game_order pasted
BELOW byte for byte (each text sha-pinned), with study 93's lead_rules (test_one_catcher_all_flag's paste) and study 89's
own_caps on the lab's term_book, and ONE stand-in optimizer that reads both builds' bans, bounds, stack and env: a FULL solve
(bring_back_min 2) must carry MAX_PER_GAME 5 and takes a different row; forced infeasibles drop the full stack first. The same
26 book rows, 15 spares and records; the top games equal 73's game_order; off = the ONECATCH call exactly; three code
mutations caught; the refusals; the CLI's loud-off path."""
import ast
import dataclasses
import hashlib
import importlib.util
import sys
import types
from contextlib import contextmanager
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


OCT = _load("one_catcher_helpers_fs", ROOT / "tests" / "test_one_catcher_all_flag.py")   # 93's lead_rules, the fixture, builders
RR, OC, T71 = OCT.RR, OCT.OC, OCT.T71
LAB_TEXT_SHA256 = {"game_order": "78f30ce0ede1edda75929cb341bf204670fcf0ba372e61cb95c602ddaca4f69a",
                   "tail_rules": "20bbf437119796a87f3502731de407eb4261cda20f3411310b8cffb173884890",
                   "arm_rules": "11e994ba98175c5d82a06bab8d660c02b7379babeffcaed0923179e70c5d14fb"}


@dataclasses.dataclass(eq=False)
class _FStack:                                      # one object per cell (found by identity); a dataclass with the fields the
    cell: str                                       # pasted code replaces (93's naked C0; 102's bring_back_min 2)
    qb_stack_min: int = 1
    qb_stack_max: int = 1
    bring_back_min: int = 0


S18 = types.SimpleNamespace(CELLS={n: (q, _FStack(n, bring_back_min=int(r.get("bring_back_min", 0))), qmax, which)
                                   for n, (q, r, qmax, which) in T71.M.MIX_CELLS.items()},
                            allocate=T71.S18.allocate, interleave=T71.S18.interleave, pair_games=T71.S18.pair_games)
S24 = T71.S24                                       # the pasted lab code below reads these names
TAIL_MPG = "5"                                      # s102_ceiling_build.py's constant
lead_rules = OCT.lead_rules                         # 93's, pasted and sha-pinned in test_one_catcher_all_flag.py


# ---- nfl2 experiments/s73_topg_qb1.py (game_order) and s102_ceiling_build.py @ 4bdfafd4 (tail_rules, arm_rules), BYTE FOR BYTE ----
def game_order(fr_pool: pd.DataFrame) -> list[str]:
    """game_ids by game_total desc, game_id asc, over the games with a QB in the pool."""
    q = fr_pool[fr_pool.pos.astype(str) == "QB"]
    g = (fr_pool[fr_pool.game_id.astype(str).isin(set(q.game_id.astype(str)))]
         .assign(_t=lambda d: pd.to_numeric(d.game_total, errors="coerce"), _g=lambda d: d.game_id.astype(str))
         .groupby("_g")._t.median().reset_index().sort_values(["_t", "_g"], ascending=[False, True]))
    return list(g._g)


@contextmanager
def tail_rules(ban_qbs: set, k_book: int):
    """Every A1 book solve (j = len(prev) < k_book) as a FULL GAME STACK: the A1 stack with bring_back_min 2, MAX_PER_GAME 5 for
    that solve (the optimizer's env, overridden around the solve), and the QBs outside the slate's top-4 total games banned too
    -- ONE solve; infeasible -> the plain A1 solve, recorded. Entered BEFORE 93's lead_rules, so a failing solve drops the full
    stack first: [row + full] -> [row] -> [full] -> [none]. Spares never. Recorded on THIS class by name."""
    orig_cls = S24.CapBuilder
    a1 = S18.CELLS["A1"][1]
    full = dataclasses.replace(a1, bring_back_min=2)

    class TailBuilder(orig_cls):
        ruled: list = []
        plain: list = []

        def solve_with(self, stack, qb_game_max, pair, extra_bans: set):
            j = len(self.prev)
            if j >= k_book or stack is not a1:
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            cur = S24.optimize

            def mpg5(*a, **kw):
                kw["env"] = {**(kw.get("env") or {}), "MAX_PER_GAME": TAIL_MPG}
                return cur(*a, **kw)
            S24.optimize = mpg5
            try:
                lu = super().solve_with(full, qb_game_max, pair, set(extra_bans) | set(ban_qbs))
            finally:
                S24.optimize = cur
            if lu is not None:
                TailBuilder.ruled.append(("A1", j))
                return lu
            TailBuilder.plain.append(("A1", j))
            return super().solve_with(stack, qb_game_max, pair, extra_bans)

    TailBuilder.ruled, TailBuilder.plain = [], []
    S24.CapBuilder = TailBuilder
    try:
        yield TailBuilder
    finally:
        S24.CapBuilder = orig_cls


@contextmanager
def arm_rules(arm: str, row_cons: list, k_book: int, tail_bans: set):
    """(the lead class, the tail class or None): TAIL_STACK8 enters tail_rules first, then 93's lead_rules; the others 93's
    lead_rules alone (their change is the objective, passed to term_book)."""
    if arm == "TAIL_STACK8":
        with tail_rules(tail_bans, k_book) as Q, lead_rules(0, True, 0, row_cons, k_book) as R:
            yield R, Q
    else:
        with lead_rules(0, True, 0, row_cons, k_book) as R:
            yield R, None



# ---- one stand-in optimizer for both builds ----
FORCE_ALL_AT = {12}                 # a solve carrying ANY bound at these row indices is infeasible (-> no rule)
FORCE_OC_AT = {4, 5, 6, 21}         # a solve carrying MORE than the two row bounds (the one-catcher's) is infeasible
FORCE_FULL_AT: set = set()          # a FULL solve at these row indices is infeasible (set per test)
FORCE_FULL_BOUNDS_AT: set = set()   # a FULL solve carrying bounds at these row indices is infeasible (set per test)
CALLS: list = []                    # (build, j, full, MAX_PER_GAME, banned QBs)


def pick(pool, obj_col, prev, bans, bounds, full):
    """OCT's stand-in (the objective order rotated by the rows so far, banned players skipped, every bound held); a FULL solve
    rotates differently, so a full-stack row differs from the plain one."""
    j = len(prev)
    if bounds and (j in FORCE_ALL_AT or (len(bounds) > 2 and j in FORCE_OC_AT)):
        return None
    if full and (j in FORCE_FULL_AT or (bounds and j in FORCE_FULL_BOUNDS_AT)):
        return None
    avail = [p for p in pool if not bans or p["id"] not in bans]
    order = sorted(avail, key=lambda p: (-float(p[obj_col]), str(p["id"])))
    if len(order) < 9:
        return None
    off = ((3 * j + 5) if full else j) % len(order)
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


def _full(stack, env, build, j, bans) -> bool:
    full = int(getattr(stack, "bring_back_min", 0) or 0) == 2
    mpg = (env or {}).get("MAX_PER_GAME")
    CALLS.append((build, j, full, mpg, frozenset(b for b in (bans or ()) if str(b) in QB_IDS)))
    assert full == (mpg == "5"), (build, j, full, mpg)               # MAX_PER_GAME 5 exactly on the full solves
    return full


def install_production(monkeypatch):
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None,
                 interaction_floor_weights=None, interaction_floor=None, member_bounds=None):
        assert all(lo == 0 for _, lo, _ in (member_bounds or ()))
        full = _full(stack, env, "prod", len(banned_lineups), bans)
        got = pick(pool, objective_col, banned_lineups, bans, [(ids, hi) for ids, _, hi in (member_bounds or ())], full)
        return RR._PLU(got) if got is not None else None
    lineup = types.ModuleType("nfl2.core.lineup"); lineup.optimize = optimize; lineup.StackRules = T71.StackRules
    for name, mod in (("nfl2", types.ModuleType("nfl2")), ("nfl2.core", types.ModuleType("nfl2.core")), ("nfl2.core.lineup", lineup)):
        monkeypatch.setitem(sys.modules, name, mod)


def _lab_optimize(recs, stack, objective_col, banned_lineups, bans, set_constraints=None, env=None):
    assert all(op == "<=" for _, op, _ in (set_constraints or ()))
    full = _full(stack, env, "lab", len(banned_lineups), bans)
    got = pick(recs, objective_col, banned_lineups, bans, [(ids, hi) for ids, _, hi in (set_constraints or ())], full)
    return RR._LU(tuple(p["id"] for p in got)) if got is not None else None


W, TERM = OC.W, OC.TERM
TOTALS = {"g0": 47.5, "g1": 51.0, "g2": 44.0, "g3": 51.0, "g4": 49.5, "g5": 42.0}     # top 4: g1, g3 (a tie: by id), g4, g0


def frame() -> pd.DataFrame:
    fr = OCT.frame()
    fr["game_total"] = fr.game_id.map(TOTALS)
    return fr


QB_IDS = set(frame().query("pos == 'QB'").id.astype(str))


def inputs(tmp_path):
    fr = frame()
    p = OC.fp_file(tmp_path, fr)
    caps, _ = ur.own_cap_rows(p, fr, set(), 15.0, 26, 0.9)
    te, low, _ = ur.row_rule_sets(p, fr, set(), 3.0)
    return fr, caps, [(te, 0, 1), (low, 0, 1)], [(sorted(te), "<=", 1), (sorted(low), "<=", 1)]


def production_book(monkeypatch, fr, own_cap, bounds, full, mod=ur, k=26, spares=15, **kw):
    install_production(monkeypatch)
    extra = {"a1_full_stack": True} if full else {}
    rows, cells, meta, sp = mod.mix_rows(fr, set(), k, 9, None, 0, W, exposure_cap=13, dst_cap=6, fill="rr", spares=spares,
                                         term_rows=8, term_bonus=TERM, own_cap=own_cap, row_bounds=bounds, one_catcher=True,
                                         **extra, **kw)
    return [list(r) for r in rows], list(cells), meta, [list(r) for r, _ in sp]


def lab_book(monkeypatch, fr, cap_rows, cons, k_book=26, k=41):
    monkeypatch.setattr(T71, "S18", S18); monkeypatch.setattr(OC, "S18", S18); monkeypatch.setattr(OCT, "S18", S18)
    base = fr.mean_projection.to_numpy(float)
    term = np.array([TERM.get(i, 0.0) for i in fr.id])
    fr_pool = fr                                                   # the lab's run(): the pool, its top games, the banned QBs
    top = game_order(fr_pool)[:4]
    tail_bans = {str(i) for i, p, g in zip(fr_pool.id, fr_pool.pos, fr_pool.game_id) if str(p) == "QB" and str(g) not in top}
    S24.CapBuilder, S24.optimize = OCT._TCapBuilder, _lab_optimize
    try:
        with arm_rules("TAIL_STACK8", cons, k_book, tail_bans) as (R, Q), OC.own_caps(cap_rows, k_book) as T:
            book, cells, mt = T71.term_book(fr, base, term, (13, 6), W, k_book, 8, k=k)
            rec = {"tail_ruled": list(Q.ruled), "tail_plain": list(Q.plain), "plain": list(R.plain), "own_plain": list(T.plain),
                   "lead_ruled": [(c, j) for c, j, _ in R.lead_ruled], "lead_plain": [(c, j) for c, j, _ in R.lead_plain],
                   "top": list(top), "bans": tail_bans}
    finally:
        S24.CapBuilder, S24.optimize = T71._HCapBuilder, None
    rows = [list(lu.ids) for lu in book]
    return rows[:k_book], rows[k_book:], rec


def mutant(old: str, new: str):
    return OCT.mutant(old, new)


# ---- the tests ----
def test_the_pasted_lab_text_is_the_labs():
    src = (ROOT / "tests" / "test_a1_full_stack_flag.py").read_text()
    lines = src.splitlines(keepends=True)
    seen = set()
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in LAB_TEXT_SHA256:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            assert hashlib.sha256("".join(lines[start - 1:node.end_lineno]).encode()).hexdigest() == LAB_TEXT_SHA256[node.name], node.name
            seen.add(node.name)
    assert seen == set(LAB_TEXT_SHA256)


@pytest.mark.parametrize("variant", ["fixture", "nan", "median", "no_qb_game", "excluded"])
def test_the_top_games_are_73s_game_order(variant):
    fr = frame()
    pool_ids = set(fr.id.astype(str))
    if variant == "nan":
        fr.loc[fr.game_id == "g1", "game_total"] = np.nan
    elif variant == "median":                                      # a game's rows disagree: the median decides
        idx = fr.index[fr.game_id == "g5"]
        fr.loc[idx[: len(idx) // 2 + 1], "game_total"] = 60.0
    elif variant == "no_qb_game":                                  # g1 has no QB in the pool: never a top game
        pool_ids -= set(fr[(fr.game_id == "g1") & (fr.pos == "QB")].id.astype(str))
    elif variant == "excluded":
        pool_ids -= set(fr[fr.game_id == "g3"].id.astype(str))
    fr_pool = fr[fr.id.astype(str).isin(pool_ids)].reset_index(drop=True)
    assert ur.full_stack_games(fr, pool_ids, 4) == game_order(fr_pool)[:4]
    if variant == "fixture":
        assert ur.full_stack_games(fr, pool_ids, 4) == ["g1", "g3", "g4", "g0"]


@pytest.mark.parametrize("force", ["none", "full", "full_with_bounds", "every_bound"])
def test_the_book_equals_102s_tail_inside_93_and_89(monkeypatch, tmp_path, force):
    """At j0 (the first A1 book solve): "full" -- any full solve infeasible: [rules + full] -> [rules]; "full_with_bounds" --
    a full solve WITH the row bounds infeasible: [rules + full] -> [rules] (the full stack drops first, never [full] alone);
    "every_bound" -- any solve with a bound infeasible: [rules + full] -> [rules] -> [full] (ruled without the row rules)."""
    fr, caps, bounds, cons = inputs(tmp_path)
    j0 = None
    if force != "none":
        _, _, meta0, _ = production_book(monkeypatch, fr, caps, bounds, True)
        j0 = meta0["a1_full_stack"]["ruled"][0][1]
        name, val = {"full": ("FORCE_FULL_AT", {j0}), "full_with_bounds": ("FORCE_FULL_BOUNDS_AT", {j0}),
                     "every_bound": ("FORCE_ALL_AT", FORCE_ALL_AT | {j0})}[force]
        monkeypatch.setattr(sys.modules[__name__], name, val)
    CALLS.clear()
    book_p, cells_p, meta, spares_p = production_book(monkeypatch, fr, caps, bounds, True)
    book_l, spares_l, rec = lab_book(monkeypatch, fr, caps, cons)
    assert book_p == book_l and spares_p == spares_l
    fs = meta["a1_full_stack"]
    assert fs["games"] == rec["top"] == ["g1", "g3", "g4", "g0"] and fs["banned_qbs"] == len(rec["bans"]) > 0
    assert [tuple(x) for x in fs["ruled"]] == rec["tail_ruled"] and [tuple(x) for x in fs["resolved_without"]] == rec["tail_plain"]
    assert [tuple(x) for x in meta["row_rules"]["resolved_without"]] == rec["plain"]
    assert [tuple(x) for x in meta["own_cap"]["resolved_without"]] == rec["own_plain"]
    assert [tuple(x) for x in meta["one_catcher"]["ruled"]] == rec["lead_ruled"]
    assert {c for c, _ in rec["tail_ruled"] + rec["tail_plain"]} == {"A1"} and all(j < 26 for _, j in rec["tail_ruled"] + rec["tail_plain"])
    assert fs["a1_rows_book"] == sum(1 for c in cells_p if c == "A1") > 0
    full_calls = [c for c in CALLS if c[2]]
    assert full_calls and all(c[4] >= frozenset(rec["bans"]) for c in full_calls)               # every full solve bans them
    assert all(c[1] < 26 for c in full_calls) and {c[0] for c in full_calls} == {"prod", "lab"}  # spares never; both builds
    forced = {j for _, j in rec["tail_plain"]}
    if force == "none":
        assert forced <= FORCE_ALL_AT and len({j for _, j in rec["tail_ruled"]}) == fs["a1_rows_book"]
    else:
        assert ("A1", j0) in rec["tail_plain"]
        assert (("A1", j0) in rec["tail_ruled"]) == (force == "every_bound")
        assert (("A1", j0) in rec["plain"]) == (force == "every_bound")                            # the row rules dropped only then


def test_off_is_the_onecatch_call_exactly(monkeypatch, tmp_path):
    fr, caps, bounds, _ = inputs(tmp_path)
    off = production_book(monkeypatch, fr, caps, bounds, False)
    on = production_book(monkeypatch, fr, caps, bounds, True)
    explicit = production_book(monkeypatch, fr, caps, bounds, False, a1_full_stack=False)
    assert off[0] != on[0] and "a1_full_stack" not in off[2] and "a1_full_stack" in on[2]
    assert explicit[0] == off[0] and explicit[1] == off[1] and explicit[3] == off[3] and "a1_full_stack" not in explicit[2]
    CALLS.clear()
    production_book(monkeypatch, fr, caps, bounds, False)
    assert CALLS and not any(c[2] or c[3] == "5" for c in CALLS)                                  # no full solve when off


@pytest.mark.parametrize("old,new", [
    ("if a1_full_stack and name == FULL_STACK_CELL and len(prev) < k:", "if a1_full_stack and name == FULL_STACK_CELL:"),   # spares too
    ("bans=(set(bans) | fs_bans) or None)", "bans=set(bans) or None)"),                                                    # no game bans
    ('if a1_full_stack and name == FULL_STACK_CELL and len(prev) < k:', 'if a1_full_stack and name in ("A1", "A2") and len(prev) < k:'),
])
def test_a_mutated_rule_is_caught(monkeypatch, tmp_path, old, new):
    fr, caps, bounds, cons = inputs(tmp_path)
    try:
        book_m, _, _, spares_m = production_book(monkeypatch, fr, caps, bounds, True, mod=mutant(old, new))
    except AssertionError:
        return                                                                                   # the stand-in's own check caught it
    book_l, spares_l, _ = lab_book(monkeypatch, fr, caps, cons)
    assert (book_m, spares_m) != (book_l, spares_l)


def test_mix_rows_refuses_it_off_the_tested_version(monkeypatch, tmp_path):
    fr, caps, bounds, _ = inputs(tmp_path)
    install_production(monkeypatch)
    with pytest.raises(ValueError, match="a1_full_stack needs"):
        ur.mix_rows(fr.drop(columns=["game_total"]), set(), 26, 9, None, 0, W, exposure_cap=13, dst_cap=6, fill="rr", spares=15,
                    term_rows=8, term_bonus=TERM, own_cap=caps, row_bounds=bounds, one_catcher=True, a1_full_stack=True)
    with pytest.raises(ValueError, match="a1_full_stack needs"):
        ur.mix_rows(fr, set(), 26, 9, None, 0, W, exposure_cap=13, dst_cap=6, fill="group", spares=15, own_cap=caps,
                    a1_full_stack=True)


def test_the_cli_refuses_it_off_the_armed_version_and_is_loudly_off():
    base = ["--saturday-run", "x", "--t70-run", "y", "--live-dir", "z", "--entries", "26", "--main", "mix"]
    own = ["--main-own-cap-delta", "15", "--main-own-cap-source", "f.csv", "--main-own-cap-fallback-share", "0.5"]
    armed = ["--mix-portfolio", "mix", "--mix-fill", "rr", "--mix-max-te", "1", "--mix-max-low-own", "1"]
    for extra in (own + armed + ["--mix-a1-full-stack"], own + armed + ["--mix-one-catcher-all", "--mix-a1-full-stack", "--max-per-game", "5"]):
        with pytest.raises(SystemExit, match="--mix-a1-full-stack is defined on his armed version only"):
            ur.main(base + extra)
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert "!!! A1 FULL STACK NOT APPLIED" in src and '"ONECATCH is not applied" if not oc_on else' in src
    assert src.count("a1_full_stack=fs_on)") == 2 and 'mix_meta["a1_full_stack_source"] = fs_meta' in src
    assert src.count("full_stack_line(") == 3                                                    # the def, the book, the term book


def test_the_audit_holds_only_the_named_full_stack_rows_to_five(tmp_path):
    """audit_build_levers: a row with 5 from one game passes max_per_game (cap 4) ONLY when the receipt names it as a full-stack
    row; the a1_full_stack check holds each named row to QB + 2 + >= 2 opponents in a declared top game, a main row."""
    ABL_T = OCT.ABL_T
    L = ABL_T._lineup
    full = ["AQB", "AWR1", "AWR2", "BRB1", "BWR0", "CRB0", "CWR0", "CTE", f"{ABL_T.THIRD['C']}_DST"]        # 5 from g1
    lus = [full, L("C", "D", "E"), L("E", "F", "G"), L("G", "H", "A"), L("B", "A", "D"), L("A", "B", "C")]
    tail = ABL_T.CONTESTS + [{"name": "milly", "contest_id": "9", "entries": 1, "keep": 1, "track": "tail"}]
    base = {"selector": "mean", "operational_k": 5, "tail_sleeve": {"rows": 1, "selector_used": "mean"}}

    def run(tmp, inner):
        mix_meta = {"exposure_cap": 3, "max_exposure_used": 3, "dst_cap": 2, "max_dst_rows_used": 2, "mix": {"cells": {"A1": {"rows": 5}}, **inner}}
        r = ABL_T._run_dir(tmp, lineups=lus, book=lus[:6], receipt={"written": 6, "config": {**base, "union": {"main": "mix", "mix": mix_meta}}})
        c = pd.read_parquet(r / "candidates.parquet"); c["source_run"] = ["mix"] * 5 + ["saturday"]; c["tag"] = ["mix_A1"] * 5 + ["lev"]
        c["book_rank"] = [1, 2, 3, 4, 5, None]; c.to_parquet(r / "candidates.parquet")
        out = ABL_T._audit(r, contests=tail, expect_selector="mean")
        return ("max_per_game" in out["failed"], "a1_full_stack" in out["failed"],
                next(x for x in out["checks"] if x["check"] == "a1_full_stack"))

    block = lambda rows, games: {"a1_full_stack": {"cell": "A1", "games": games, "bring_back_min": 2, "max_per_game": 5,  # noqa: E731
                                                   "ruled": [["A1", 0]] * len(rows), "resolved_without": [],
                                                   "ruled_rows": [{"row": sorted(r)} for r in rows]}}
    assert run(tmp_path / "a", block([full], ["g1", "g2"]))[:2] == (False, False)          # named: held to 5, a full stack
    assert run(tmp_path / "b", {})[:2] == (True, False)                                    # not named: 5 > the cap 4
    assert run(tmp_path / "c", block([full], ["g2"]))[:2] == (False, True)                # not in a declared top game
    assert run(tmp_path / "d", block([full, lus[1]], ["g1", "g2"]))[:2] == (False, True)  # a named row with one opponent
    mpg, bad, rec = run(tmp_path / "e", {"a1_full_stack_source": {"applied": False, "not_applied": "ONECATCH is not applied"}})
    assert bad is False and "NOT APPLIED" in rec["detail"]
