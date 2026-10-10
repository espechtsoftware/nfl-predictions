"""Study 97's RBMATE4_FAVHI scope on the live MIX book (the operator 10-09: "Try live W5 if built"; study 97's pick by its
pre-fixed rule): union_reselect's mix_rows(rb_mate_c=4, rb_mate_qb_teams=rb_mate_scope_teams("favhi", ...)) against the lab's OWN
code -- nfl2 experiments/s97_game_script.py @ af07583e (module 7df6f324) rm_pairs_for pasted BELOW byte for byte (its text
sha-pinned), with 97's scenarios (pasted and pinned in test_game_script_sets.py) and 96's combo_rules + 94's rb_pairs (pasted
and pinned in test_rb_mate_c_flag.py) inside 89's own_caps on the vendored term_book: the same 26 rows, 15 spares and records,
unforced and with the first floored solve forced infeasible; the floor's pairs only for the FAVHI QBs; the scope's refusals
(no lines; no FAVHI pair) turn the RB mate OFF; the CLI; the house fallback. Offline; no private data."""
import ast
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402

RM = None


def _load(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


RM = _load("rb_mate_helpers_scope", ROOT / "tests" / "test_rb_mate_c_flag.py")         # 96's combo_rules, 94's rb_pairs, stand-ins
GS = _load("game_script_helpers_scope", ROOT / "tests" / "test_game_script_sets.py")   # 97's scenarios
OCT, OC, T71, S18, S24 = RM.OCT, RM.OC, RM.T71, RM.S18, RM.S24
LAB_TEXT_SHA256 = {"rm_pairs_for": "fb2142c71524c807b6251cb92e99a1b6d50356a9dceaf600022d6ecfe7c2b3fe"}


# ---- nfl2 experiments/s97_game_script.py @ af07583e, BYTE FOR BYTE ----
def rm_pairs_for(arm: str, qb_rb: dict, scen: dict, fr_pool: pd.DataFrame) -> dict:
    """The arm's floor pairs: every (QB, own RB) pair (RBMATE4); only those whose QB's team is FAV / FAVHI; or, for FAVRB_NAKED4,
    every (QB, RB) pair with the RB on a FAV team and the QB on ANOTHER team (a lineup holds one QB, so the floor means: an
    expected winner's RB, without his own QB)."""
    if arm == "RBMATE4":
        return dict(qb_rb)
    if arm == "FAVRB_OPPQB4":                                  # the FAV RB with his opponent's (the trailing team's) QB
        fav = scen["teams"]["FAV"]
        game = dict(zip(fr_pool.team.astype(str), fr_pool.game_id.astype(str)))
        qbs = [(str(i), str(t)) for i, p, t in zip(fr_pool.id, fr_pool.pos, fr_pool.team) if str(p) == "QB"]
        rbs = [(str(i), str(t)) for i, p, t in zip(fr_pool.id, fr_pool.pos, fr_pool.team) if str(p) == "RB" and str(t) in fav]
        return {(q, r): 1.0 for q, qt in qbs for r, rt in rbs if qt != rt and game.get(qt) == game.get(rt)}
    if arm == "FAVRB_NAKED4":
        fav = scen["teams"]["FAV"]
        qbs = [(str(i), str(t)) for i, p, t in zip(fr_pool.id, fr_pool.pos, fr_pool.team) if str(p) == "QB"]
        rbs = [(str(i), str(t)) for i, p, t in zip(fr_pool.id, fr_pool.pos, fr_pool.team) if str(p) == "RB" and str(t) in fav]
        return {(q, r): 1.0 for q, qt in qbs for r, rt in rbs if qt != rt}
    keep = scen["teams"]["FAV" if arm == "RBMATE4_FAV" else "FAVHI"]
    team = dict(zip(fr_pool.id.astype(str), fr_pool.team.astype(str)))
    return {k: v for k, v in qb_rb.items() if team.get(k[0]) in keep}


def frame_with_lines() -> pd.DataFrame:
    """test_one_catcher_all_flag's binding fixture (each team's eight skill players adjacent; teams T0..T11 in games g0..g5) with
    pre-lock lines: the totals g0 44, g1 55, g2 52, g3 41, g4 43, g5 40; in each game the even team is favored by 4 (margin + 4),
    the odd by - 4. The slate's upper-third cut is 46.67, so g1 and g2 are high and FAVHI = {T2, T4}: near the top of the
    projections and above 3% ownership, so their (QB, own RB) pairs are feasible and the floor BINDS; and not T0, whose pair
    the unscoped floor seeds first, so the scope changes the book."""
    fr = OCT.frame()
    tot = {"g0": 44.0, "g1": 55.0, "g2": 52.0, "g3": 41.0, "g4": 43.0, "g5": 40.0}
    t = fr.team.astype(str).str[1:].astype(int)
    g = fr.game_id.astype(str)
    fr["game_total"] = g.map(tot)
    fr["implied_team_total"] = np.where(t % 2 == 0, (fr.game_total + 4.0) / 2.0, (fr.game_total - 4.0) / 2.0)
    return fr


def lab_book(monkeypatch, fr, cap_rows, cons, k_book=26, k=41):
    monkeypatch.setattr(T71, "S18", S18); monkeypatch.setattr(OC, "S18", S18)
    base = fr.mean_projection.to_numpy(float)
    term = np.array([RM.TERM.get(i, 0.0) for i in fr.id])
    scen = GS.scenarios(fr)
    pairs = rm_pairs_for("RBMATE4_FAVHI", RM.rb_pairs(fr)["qb_rb"], scen, fr)
    S24.CapBuilder, S24.optimize = OCT._TCapBuilder, RM._lab_optimize
    try:
        with RM.combo_rules(4, cons, k_book, pairs) as R, OC.own_caps(cap_rows, k_book) as T:
            book, cells, mt = T71.term_book(fr, base, term, (13, 6), RM.W, k_book, 8, k=k)
            rec = {k_: list(getattr(R, k_)) for k_ in ("rm_used", "rm_ruled", "rm_plain", "oc_ruled", "oc_plain", "plain")}
            rec["own_plain"] = list(T.plain)
    finally:
        S24.CapBuilder, S24.optimize = T71._HCapBuilder, None
    rows = [list(lu.ids) for lu in book]
    return rows[:k_book], rows[k_book:], rec, pairs


def production_book(monkeypatch, fr, own_cap, bounds, teams):
    RM.install_production(monkeypatch)
    rows, cells, meta, sp = ur.mix_rows(fr, set(), 26, 9, None, 0, RM.W, exposure_cap=13, dst_cap=6, fill="rr", spares=15,
                                        term_rows=8, term_bonus=RM.TERM, own_cap=own_cap, row_bounds=bounds, one_catcher=True,
                                        rb_mate_c=4, rb_mate_qb_teams=teams)
    return [list(r) for r in rows], list(cells), meta, [list(r) for r, _ in sp]


def inputs(tmp_path):
    fr = frame_with_lines()
    p = OC.fp_file(tmp_path, fr)
    caps, _ = ur.own_cap_rows(p, fr, set(), 15.0, 26, 0.9)
    te, low, _ = ur.row_rule_sets(p, fr, set(), 3.0)
    return fr, caps, [(te, 0, 1), (low, 0, 1)], [(sorted(te), "<=", 1), (sorted(low), "<=", 1)]


# ---- the tests ----
def test_the_pasted_lab_text_is_the_labs():
    src = (ROOT / "tests" / "test_rb_mate_scope_flag.py").read_text()
    lines = src.splitlines(keepends=True)
    seen = set()
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in LAB_TEXT_SHA256:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            assert hashlib.sha256("".join(lines[start - 1:node.end_lineno]).encode()).hexdigest() == LAB_TEXT_SHA256[node.name], node.name
            seen.add(node.name)
    assert seen == set(LAB_TEXT_SHA256) and ur.RB_MATE_SCOPES == ("all", "favhi")


def test_the_scope_teams():
    fr = frame_with_lines()
    ids = set(fr.id.astype(str))
    teams, why = ur.rb_mate_scope_teams("favhi", fr, ids)
    assert why is None and teams == GS.scenarios(fr)["teams"]["FAVHI"] == {"T2", "T4"}
    assert ur.rb_mate_scope_teams("all", fr, ids) == (None, None)
    t, why = ur.rb_mate_scope_teams("favhi", fr.drop(columns=["implied_team_total"]), ids)          # no lines -> refused
    assert t is None and "GAME SCRIPT REFUSED" in why
    no_rb = set(fr.id[~((fr.team.isin(["T2", "T4"])) & (fr.pos == "RB"))].astype(str))          # the FAVHI RBs out of the pool
    t, why = ur.rb_mate_scope_teams("favhi", fr, no_rb)
    assert t is None and "no (QB, own RB) pair" in why
    with pytest.raises(ValueError, match="not built"):
        ur.rb_mate_scope_teams("fav", fr, ids)


@pytest.mark.parametrize("force_first", [False, True])
def test_the_book_equals_97s_favhi(monkeypatch, tmp_path, force_first):
    fr, caps, bounds, cons = inputs(tmp_path)
    teams, why = ur.rb_mate_scope_teams("favhi", fr, set(fr.id.astype(str)))
    if force_first:                                    # the first floored solve infeasible: the floor dropped, the slot used
        _, _, meta0, _ = production_book(monkeypatch, fr, caps, bounds, teams)
        monkeypatch.setattr(RM, "FORCE_FLOOR_AT", {meta0["rb_mate"]["slots"][0][1]})
    book_p, cells_p, meta, spares_p = production_book(monkeypatch, fr, caps, bounds, teams)
    book_l, spares_l, rec, pairs = lab_book(monkeypatch, fr, caps, cons)
    assert book_p == book_l and spares_p == spares_l
    rm = meta["rb_mate"]
    assert rm["scope"] == "favhi" and rm["qb_teams"] == ["T2", "T4"] and rm["pairs"] == len(pairs) > 0
    assert [tuple(x) for x in rm["slots"]] == rec["rm_used"] and [tuple(x) for x in rm["ruled"]] == rec["rm_ruled"]
    assert [tuple(x) for x in rm["resolved_without"]] == rec["rm_plain"]
    team = dict(zip(fr.id.astype(str), fr.team.astype(str))); pos = dict(zip(fr.id.astype(str), fr.pos.astype(str)))
    for f in rm["ruled_rows"]:                                          # every ruled row holds a FAVHI QB with his own RB (the
        r = f["row"]                                                    # stand-in rows ignore positions, so may hold two QBs)
        assert any(pos[q] == "QB" and team[q] in teams and any(pos[i] == "RB" and team[i] == team[q] for i in r) for q in r)
    assert len(rm["resolved_without"]) == (1 if force_first else 0)


def test_the_scope_changes_the_book_and_all_is_todays(monkeypatch, tmp_path):
    fr, caps, bounds, _ = inputs(tmp_path)
    teams, _ = ur.rb_mate_scope_teams("favhi", fr, set(fr.id.astype(str)))
    favhi = production_book(monkeypatch, fr, caps, bounds, teams)
    every = production_book(monkeypatch, fr, caps, bounds, None)
    RM.install_production(monkeypatch)
    today = ur.mix_rows(fr, set(), 26, 9, None, 0, RM.W, exposure_cap=13, dst_cap=6, fill="rr", spares=15, term_rows=8,
                        term_bonus=RM.TERM, own_cap=caps, row_bounds=bounds, one_catcher=True, rb_mate_c=4)
    assert [list(r) for r in today[0]] == every[0] and every[2]["rb_mate"]["scope"] == "all"   # no scope = today's 4caff46d book
    assert favhi[0] != every[0] and favhi[2]["rb_mate"]["pairs"] < every[2]["rb_mate"]["pairs"]


def test_the_cli_and_the_refusal_text():
    base = ["--saturday-run", "x", "--t70-run", "y", "--live-dir", "z", "--entries", "26", "--main", "mix"]
    own = ["--main-own-cap-delta", "15", "--main-own-cap-source", "f.csv", "--main-own-cap-fallback-share", "0.5"]
    armed = ["--mix-portfolio", "mix", "--mix-fill", "rr", "--mix-max-te", "1", "--mix-max-low-own", "1", "--mix-one-catcher-all"]
    with pytest.raises(SystemExit, match="--mix-rb-mate-scope favhi needs --mix-rb-mate-c 4"):
        ur.main(base + own + armed + ["--mix-rb-mate-scope", "favhi"])
    with pytest.raises(SystemExit):                                      # an unbuilt scope is not a choice
        ur.main(base + own + armed + ["--mix-rb-mate-c", "4", "--mix-rb-mate-scope", "fav"])
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert "!!! RB MATE SCOPE NOT APPLIED: {why} -- the book is built without the RB mate" in src
    assert src.count("rb_mate_qb_teams=rm_teams)") == 2 and 'rm_c, rm_teams = 0, None' in src


def test_a_house_fallback_drops_the_scope_and_its_value():
    lib = ROOT / "scripts" / "union_fallbacks.sh"
    args = ("--main mix --main-cap-share 0.35 --main-own-cap-delta 15 --main-own-cap-source s --main-own-cap-fallback-share 0.5 "
            "--mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3 --mix-one-catcher-all --mix-rb-mate-c 4 --mix-rb-mate-scope favhi --y")
    script = f'source "{lib}"; mix_to_house_args {args}; printf "%s|" "${{OUT_ARGS[@]}}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert r.stdout == "--main|pmo_x50|--main-cap-share|0.5|--y|"


def test_a_mutated_scope_filter_is_caught(monkeypatch, tmp_path):
    """The scope filter dropped (every pair kept): the book differs from the lab's FAVHI book."""
    fr, caps, bounds, cons = inputs(tmp_path)
    teams, _ = ur.rb_mate_scope_teams("favhi", fr, set(fr.id.astype(str)))
    mod = OCT.mutant("rm_pairs = {(q, r): w for (q, r), w in rm_pairs.items() if team_of.get(q) in rb_mate_qb_teams}",
                     "rm_pairs = {(q, r): w for (q, r), w in rm_pairs.items() if True}")
    RM.install_production(monkeypatch)
    rows, _, _, sp = mod.mix_rows(fr, set(), 26, 9, None, 0, RM.W, exposure_cap=13, dst_cap=6, fill="rr", spares=15, term_rows=8,
                                  term_bonus=RM.TERM, own_cap=caps, row_bounds=bounds, one_catcher=True, rb_mate_c=4,
                                  rb_mate_qb_teams=teams)
    book_l, spares_l, _, _ = lab_book(monkeypatch, fr, caps, cons)
    assert ([list(r) for r in rows], [list(r) for r, _ in sp]) != (book_l, spares_l)
