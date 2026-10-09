"""Study 71 (union_reselect --mix-bring-back-top-wr; production's agreed format with amendments a-d, 10-08): the top-receiver
definition (parity with study 70's top_wr), mix_rows' interaction floor and its fallback record, the shape check, the ONE
shared reader, vet_replace_v4's lenient house fallback and late-scratch rule, and the build audit. Study 71b
(--mix-bring-back-top-wr-rows N, 84's row choice): exactly N floored book rows, the rule binding only them everywhere, and
parity with the lab's OWN term_book and row-choice code, pasted byte for byte and sha-pinned. Offline: a stand-in
optimizer carrying the pinned lab's interaction-floor arguments (nfl2.core.lineup.optimize @ f69598b); no solver."""
import dataclasses
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.inference import mix_shapes as M

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


V = _load("vet_replace_v4")
ABL = _load("audit_build_levers")


# ---------------------------------------------------------------- the top receiver: parity with study 70's top_wr
def s70_top_wr(fr_pool: pd.DataFrame, proj: np.ndarray) -> np.ndarray:
    """study 70's top_wr, VERBATIM apart from the name (nfl2 experiments/s70_topwr.py @ d622a211)."""
    d = pd.DataFrame({"i": np.arange(len(fr_pool)), "pos": fr_pool.pos.astype(str).to_numpy(), "team": fr_pool.team.astype(str).to_numpy(),
                      "sal": pd.to_numeric(fr_pool.salary, errors="coerce").fillna(0.0).to_numpy(float),
                      "proj": np.asarray(proj, float), "id": fr_pool["id"].astype(str).to_numpy()})
    w = d[d.pos == "WR"].sort_values(["team", "sal", "proj", "id"], ascending=[True, False, False, True])
    out = np.zeros(len(fr_pool), bool)
    out[w.groupby("team").head(1).i.to_numpy()] = True
    return out


def test_top_receivers_equal_study_70s_top_wr_on_the_same_pool():
    rows = [("X", "x1", "WR", 7000, 15.0), ("X", "x2", "WR", 7000, 16.0),        # salary tie: the higher projection
            ("Y", "y2", "WR", 6800, 14.0), ("Y", "y1", "WR", 6800, 14.0),        # salary + projection tie: the lower id
            ("Z", "z1", "WR", None, 20.0), ("Z", "z2", "WR", 3000, 5.0),         # a missing salary counts 0
            ("W", "w1", "RB", 9000, 25.0), ("W", "w2", "WR", 4000, 6.0),         # a pricier RB is not a receiver
            ("V", "v1", "QB", 7000, 20.0)]                                       # a team without a WR has no top WR
    pool = pd.DataFrame(rows, columns=["team", "id", "pos", "salary", "proj"])
    ref = s70_top_wr(pool, pool.proj.to_numpy())
    want = {t: i for t, i, f in zip(pool.team, pool.id, ref) if f}
    assert M.top_receivers(pool.to_dict("records")) == want == {"W": "w2", "X": "x2", "Y": "y1", "Z": "z2"}


# ---------------------------------------------------------------- the shape check and the one reader
POS = {"q": "QB", "m1": "WR", "m2": "WR", "o1": "WR", "o2": "WR", "ob": "RB", "r1": "RB", "r2": "RB", "f": "WR", "d": "DST",
       "p1": "WR", "p2": "TE"}
TEAM = {"q": "T", "m1": "T", "m2": "T", "o1": "O", "o2": "O", "ob": "O", "r1": "G", "r2": "H", "f": "G", "d": "H", "p1": "J", "p2": "K"}
OPP = {"q": "O", "m1": "O", "m2": "O", "o1": "T", "o2": "T", "ob": "T", "r1": "H", "r2": "G", "f": "H", "d": "G", "p1": "K", "p2": "J"}
GAME = {k: ("g1" if TEAM[k] in ("T", "O") else "g2" if TEAM[k] in ("G", "H") else "g3") for k in TEAM}
TOP = {"O": "o1", "T": "m1"}
ROW_WITH = ["q", "m1", "m2", "o1", "r1", "r2", "f", "p1", "d"]             # A1: QB + 2 mates + the opponent's top WR
ROW_WITHOUT = ["q", "m1", "m2", "o2", "r1", "r2", "f", "p1", "d"]          # A1: the bring-back is NOT the top WR


def test_the_rule_message_and_where_it_applies():
    sv = lambda row, cell, **kw: M.shape_violations(row, cell, POS, TEAM, OPP, GAME, **kw)  # noqa: E731
    base = sv(ROW_WITHOUT, "A1")
    v = sv(ROW_WITHOUT, "A1", top_wr=TOP, top_wr_cells=("A1", "B"))
    assert "top-WR bring-back missing: O's top receiver o1" in v and [x for x in v if not x.startswith("top-WR")] == base
    assert sv(ROW_WITH, "A1", top_wr=TOP, top_wr_cells=("A1", "B")) == sv(ROW_WITH, "A1")
    assert sv(ROW_WITHOUT, "A1", top_wr=TOP, top_wr_cells=("B",)) == base               # A1 not designated
    assert sv(ROW_WITHOUT, None, top_wr=TOP, top_wr_cells=("A1", "B")) == sv(ROW_WITHOUT, None)   # the house shape: never
    assert sv(ROW_WITHOUT, "A1", top_wr={"T": "m1"}, top_wr_cells=("A1", "B")) == base   # no top WR for O: no rule
    # (a) a late scratch: the excluded top WR leaves the dict -> no message, and his team's next WR (o2) is NOT promoted
    assert sv(["q", "m1", "m2", "ob", "r1", "r2", "f", "p1", "d"], "A1", top_wr={t: i for t, i in TOP.items() if i != "o1"},
              top_wr_cells=("A1", "B")) == sv(["q", "m1", "m2", "ob", "r1", "r2", "f", "p1", "d"], "A1")


def _receipt(fallbacks=(), with_term_fallbacks=None):
    blk = {"cells": ["A1", "B"], "top_wr": {"O": {"id": "o1", "name": "O1", "salary": 8000}, "T": {"id": "m1", "name": "M1", "salary": 7000}},
           "fallbacks": [{"row": sorted(r), "cell": "A1"} for r in fallbacks]}
    mix = {"bring_back_top_wr": blk}
    if with_term_fallbacks is not None:
        mix["with_term"] = {"bring_back_top_wr": {**blk, "fallbacks": [{"row": sorted(r)} for r in with_term_fallbacks]}}
    return {"config": {"union": {"main": "mix", "mix": {"mix": mix}}}}


def test_the_one_reader():
    assert M.bring_back_top_wr_rule({}) == ({}, (), set(), None)
    assert M.bring_back_top_wr_rule({"config": {"union": {"mix": {"mix": {"cells": {}}}}}}) == ({}, (), set(), None)
    top, cells, ex, req = M.bring_back_top_wr_rule(_receipt([ROW_WITHOUT], with_term_fallbacks=[ROW_WITH]),
                                              vet_receipt={"bring_back_top_wr_exempt": [{"row": sorted(["a", "b"]), "reason": "house fallback"}]})
    assert top == TOP and cells == ("A1", "B") and req is None                      # no study-71b cap
    assert ex == {frozenset(ROW_WITHOUT), frozenset(ROW_WITH), frozenset({"a", "b"})}


# ---------------------------------------------------------------- mix_rows: the floor, the fallback record, off = as before
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


def _stand_in(calls):
    """Deterministic. Without a floor: the 9 best non-banned players (shifted by the number of earlier rows). With the
    interaction floor (the pinned lab's arguments): the first pair (QB, WR) in id order with both available, plus the 7
    best non-QB others; no such pair -> None (infeasible)."""
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None,
                 interaction_floor_weights=None, interaction_floor=None):
        calls.append({"bring_back_min": stack.bring_back_min, "bring_back_max": stack.bring_back_max, "floor": interaction_floor,
                      "pairs": None if interaction_floor_weights is None else dict(interaction_floor_weights)})
        avail = [p for p in pool if not bans or p["id"] not in bans]
        order = sorted(avail, key=lambda p: (-p[objective_col], str(p["id"])))
        off = len(banned_lineups)
        if interaction_floor_weights is not None:
            assert interaction_floor == 1.0 and set(interaction_floor_weights.values()) == {1.0}
            have = {p["id"]: p for p in avail}
            for a, b in sorted(interaction_floor_weights, key=str):
                if a in have and b in have:
                    rest = [p for p in order if p["id"] not in (a, b) and p["pos"] != "QB"]
                    return LU([have[a], have[b]] + [rest[(off + j) % len(rest)] for j in range(7)])
            return None
        return LU([order[(off + j) % len(order)] for j in range(9)]) if len(order) >= 9 else None
    return optimize


def _failing_floor(calls, every=3):
    """The stand-in, except every `every`-th FLOORED solve reports infeasible (as the pinned optimize returns None)."""
    inner = _stand_in(calls)
    n = [0]

    def optimize(*args, **kw):
        if kw.get("interaction_floor_weights") is not None:
            n[0] += 1
            if n[0] % every == 0:
                calls.append({"bring_back_min": kw["stack"].bring_back_min, "bring_back_max": kw["stack"].bring_back_max,
                              "floor": kw["interaction_floor"], "pairs": dict(kw["interaction_floor_weights"]), "forced_none": True})
                return None
        return inner(*args, **kw)
    return optimize


def _install(monkeypatch, calls, optimize=None):
    lineup = types.ModuleType("nfl2.core.lineup"); lineup.optimize = optimize or _stand_in(calls); lineup.StackRules = StackRules
    for name, mod in (("nfl2", types.ModuleType("nfl2")), ("nfl2.core", types.ModuleType("nfl2.core")), ("nfl2.core.lineup", lineup)):
        monkeypatch.setitem(sys.modules, name, mod)


def _frame(n=40):
    rows = []
    for k in range(n):
        rows.append({"id": f"p{k}", "name": f"P{k}", "pos": ["QB", "RB", "WR", "WR", "TE"][k % 5], "team": f"T{k % 8}",
                     "opp": f"T{(k % 8) ^ 1}", "salary": 5000 + 37 * k, "game_id": f"g{(k % 8) // 2}", "mean_projection": 30.0 - 0.5 * k})
    for t in range(8):
        rows.append({"id": f"d{t}", "name": f"D{t}", "pos": "DST", "team": f"T{t}", "opp": f"T{t ^ 1}", "salary": 3000,
                     "game_id": f"g{t // 2}", "mean_projection": 5.0 + 0.1 * t})
    return pd.DataFrame(rows)


W21 = [3, 3] + [1] * 15 + [0] * 4


def test_off_is_the_old_call_exactly(monkeypatch):
    fr = _frame(); c0, c1 = [], []
    _install(monkeypatch, c0)
    r0, cells0, m0, s0 = ur.mix_rows(fr, set(), 21, 7, 4, 49_000, W21, exposure_cap=10, dst_cap=5, fill="rr", spares=3)
    _install(monkeypatch, c1)
    r1, cells1, m1, s1 = ur.mix_rows(fr, set(), 21, 7, 4, 49_000, W21, exposure_cap=10, dst_cap=5, fill="rr", spares=3, bring_back_top_wr=())
    assert (r0, cells0, s0) == (r1, cells1, s1) and m0 == m1 and "bring_back_top_wr" not in m1
    assert c0 == c1 and {(c["floor"], c["pairs"] is None) for c in c1} == {(None, True)}     # no interaction argument at all


def test_on_every_designated_row_holds_its_qbs_opponents_top_wr(monkeypatch):
    fr = _frame(); calls = []
    _install(monkeypatch, calls)
    rows, cells, meta, spares = ur.mix_rows(fr, set(), 21, 7, 4, 49_000, W21, exposure_cap=10, dst_cap=5, fill="rr", spares=3,
                                            bring_back_top_wr=("A1", "B"))
    pool = list(ur.frame_players(fr).values())
    top = M.top_receivers(pool)
    bb = meta["bring_back_top_wr"]
    assert bb["cells"] == ["A1", "B"] and {t: v["id"] for t, v in bb["top_wr"].items()} == top
    qbs = [p for p in pool if p["pos"] == "QB"]
    assert bb["pairs"] == sum(1 for q in qbs if q["opp"] in top) and bb["fallbacks"] == []
    opp = {p["id"]: p["opp"] for p in pool}
    for r, c in list(zip(rows, cells)) + [(ids, c) for ids, c in spares]:
        if c in ("A1", "B"):
            q = next(i for i in r if i.startswith("p") and int(i[1:]) % 5 == 0)
            assert top[opp[q]] in r                                                   # the opponent's top receiver
    assert all(c["floor"] is None for c in calls if c["bring_back_max"] == 0)        # A2 / C never carry the floor
    assert bb["rows_floored"]["book"] == sum(1 for c in cells if c in ("A1", "B"))
    assert bb["rows_floored"]["spares"] == sum(1 for _, c in spares if c in ("A1", "B"))


def test_an_infeasible_floor_builds_without_it_and_records_the_row_by_identity(monkeypatch, capsys):
    fr = _frame(); calls = []
    _install(monkeypatch, calls, _failing_floor(calls))                            # every 3rd floored solve is infeasible
    rows, cells, meta, _ = ur.mix_rows(fr, set(), 21, 7, 4, 49_000, W21, exposure_cap=10, dst_cap=5, fill="rr",
                                       bring_back_top_wr=("A1", "B"))
    fb = meta["bring_back_top_wr"]["fallbacks"]
    assert fb and all(f["reason"] == "infeasible with the floor" and f["kind"] == "book" for f in fb)
    assert all(f["row_sha256"] == hashlib.sha256(",".join(f["row"]).encode()).hexdigest() for f in fb)
    built = {frozenset(r) for r in rows}
    assert {frozenset(f["row"]) for f in fb} <= built                               # each fallback is a real book row
    line = ur.bring_back_top_wr_line(meta["bring_back_top_wr"])
    assert line.startswith("BRING-BACK TOP WR: cells A1,B;") and "STUDY-71 ROW(S) BUILT WITHOUT THE TOP-WR FLOOR" in line
    _, _, exempt, required = M.bring_back_top_wr_rule({"config": {"union": {"mix": {"mix": meta}}}})
    assert required is None
    assert exempt == {frozenset(f["row"]) for f in fb}


@pytest.mark.parametrize("spec, main, portfolio, want", [
    ("", "mix", "mix", ()), ("A1,B", "mix", "mix", ("A1", "B")), (" B ", "mix", "mix", ("B",)),
    ("A2", "mix", "mix", None), ("C", "mix", "mix", None), ("A1,A1", "mix", "mix", None), ("Q", "mix", "mix", None),
    ("A1", "pmo_x50", "mix", None), ("A1", "mix", "ws", None)])
def test_the_switch_parses_and_refuses(spec, main, portfolio, want):
    if want is None:
        with pytest.raises(SystemExit, match="--mix-bring-back-top-wr"):
            ur.parse_bring_back_top_wr(spec, main, portfolio)
    else:
        assert ur.parse_bring_back_top_wr(spec, main, portfolio) == want


def test_mix_rows_refuses_a_non_designated_cell_list(monkeypatch):
    _install(monkeypatch, [])
    with pytest.raises(ValueError, match="bring_back_top_wr"):
        ur.mix_rows(_frame(), set(), 21, 7, 4, 49_000, W21, exposure_cap=10, dst_cap=5, bring_back_top_wr=("C",))


# ---------------------------------------------------------------- vet_replace_v4: house fallback, late scratch, exemption
def test_vet_cell_violations_off_is_shape_violations_exactly():
    for row in (ROW_WITH, ROW_WITHOUT):
        for cell in ("A1", "B", "C"):
            assert V.cell_violations(row, cell, POS, TEAM, OPP, GAME) == M.shape_violations(row, cell, POS, TEAM, OPP, GAME)


def test_vet_house_fallback_is_a1_without_the_rule_and_exemptions_hold():
    on = dict(top_wr=TOP, rule_cells=("A1", "B"))
    assert "top-WR bring-back missing: O's top receiver o1" in V.cell_violations(ROW_WITHOUT, "A1", POS, TEAM, OPP, GAME, **on)
    assert V.cell_violations(ROW_WITHOUT, "house", POS, TEAM, OPP, GAME, **on) == M.shape_violations(ROW_WITHOUT, "A1", POS, TEAM, OPP, GAME)
    assert V.cell_violations(ROW_WITHOUT, "A1", POS, TEAM, OPP, GAME, exempt={frozenset(ROW_WITHOUT)}, **on) == \
        M.shape_violations(ROW_WITHOUT, "A1", POS, TEAM, OPP, GAME)                  # a union fallback row, by identity
    # (a) the top WR excluded at vet: a replacement without him passes, and o2 is not promoted
    live = {t: i for t, i in TOP.items() if i != "o1"}
    assert V.cell_violations(ROW_WITHOUT, "A1", POS, TEAM, OPP, GAME, top_wr=live, rule_cells=("A1", "B")) == \
        M.shape_violations(ROW_WITHOUT, "A1", POS, TEAM, OPP, GAME)


def test_vet_picks_the_lenient_house_row_when_nothing_fits_the_cell():
    gain = np.array([5.0, 3.0, 1.0])
    assert V.pick_replacement(gain, [{"C"}, {"house"}, {"B", "house"}], "B", house="house") == (2, None)   # the cell fits first
    assert V.pick_replacement(gain, [{"C"}, {"house"}, {"C"}], "A1", house="house") == (1, "house")      # else the lenient house
    assert V.row_cell(0, {0: "A1"}, {0: "house"}) == "house"
    assert V.pick_replacement(gain, [{"C"}, {"A1"}, {"C"}], "B") == (1, "A1")         # the rule off: as before


def test_vet_script_wires_the_rule_record_and_the_reader():
    text = (ROOT / "scripts" / "vet_replace_v4.py").read_text()
    assert "bb_top, bb_cells, bb_exempt, bb_required = bring_back_top_wr_rule(src)" in text
    assert "_game_of_id, bb_live, bb_cells, bb_exempt, bb_required)" in text            # 71b: the cap reaches the cell check
    assert 'house_cell = "house" if bb_cells else "A1"' in text and 'fits.add("house")' in text
    assert "bb_live.clear(); bb_live.update({t: i for t, i in bb_top.items() if id_to_dk.get(i) not in E})" in text
    assert 'receipt["bring_back_top_wr_exempt"] = exempt_rows' in text and '"reason": "house fallback"' in text


# ---------------------------------------------------------------- the build audit: an exempt fallback passes, a violation fails
def _audit_run(tmp, row, tag, receipt_extra):
    spec = importlib.util.spec_from_file_location("tabl", ROOT / "tests" / "test_audit_build_levers.py")
    T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
    base = [T._lineup("A", "B", "C"), T._lineup("C", "D", "E"), T._lineup("E", "F", "G"), T._lineup("G", "H", "A"), T._lineup("B", "A", "D")]
    r = T._run_dir(tmp, lineups=base + [row], book=base, receipt=receipt_extra)
    c = pd.read_parquet(r / "candidates.parquet")
    c["tag"] = ["lev"] * len(base) + [tag]; c["source_run"] = ["t70"] * len(base) + ["mix"]
    c.to_parquet(r / "candidates.parquet")
    return T._audit(r)


def test_the_audit_holds_designated_rows_to_the_rule_and_exempts_fallbacks(tmp_path):
    b_row = ["AQB", "AWR1", "BRB1", "CRB0", "DWR0", "CWR2", "DTE", "EWR1", "G_DST"]   # B: QB + 1, the bring-back an RB
    b_top = ["AQB", "AWR1", "BWR0", "CRB0", "DWR0", "CWR2", "DTE", "EWR1", "G_DST"]   # the same with B's top WR (BWR0)

    def rec(fallbacks=(), top="BWR0"):
        blk = {"cells": ["A1", "B"], "top_wr": {"B": {"id": top, "name": "B top", "salary": 7000}}, "fallbacks": [{"row": sorted(r)} for r in fallbacks]}
        return {"config": {"union": {"main": "mix", "mix": {"mix": {"bring_back_top_wr": blk}}}}}

    assert "stack_rules" not in _audit_run(tmp_path / "off", b_row, "mix_B", {})["failed"]            # the rule off: as before
    on = _audit_run(tmp_path / "on", b_row, "mix_B", rec())
    detail = next(c["detail"] for c in on["checks"] if c["check"] == "stack_rules")
    assert "stack_rules" in on["failed"] and "top-WR bring-back missing" in detail and "top receiver BWR0" in detail
    assert "stack_rules" not in _audit_run(tmp_path / "top", b_top, "mix_B", rec())["failed"]
    assert "stack_rules" not in _audit_run(tmp_path / "exempt", b_row, "mix_B", rec([b_row]))["failed"]
    assert "stack_rules" not in _audit_run(tmp_path / "scratched", b_row, "mix_B", rec(top="BINJ"))["failed"]   # proj 0: excluded



# ================================================================ study 71b: the rows cap (84's definition, production's format)
CHEAP_TERM = {f"p{k}": 2.0 for k in range(40) if (5000 + 37 * k) < 6000}           # a cheap-style block term on the fixture


def _cap_run(monkeypatch, cap, optimize=None, term_rows=0, k=26, spares=15, weights=None):
    calls = []
    _install(monkeypatch, calls, optimize(calls) if optimize else None)
    w = weights or ([3, 3] + [1] * (k - 2))
    kw = dict(exposure_cap=13, dst_cap=6, fill="rr", spares=spares, bring_back_top_wr=("A1", "B"), bring_back_top_wr_rows=cap)
    if term_rows:
        kw.update(term_rows=term_rows, term_bonus=CHEAP_TERM)
    rows, cells, meta, sp = ur.mix_rows(_frame(), set(), k, 4, 4, 49_000, w, **kw)
    return rows, cells, meta, sp, calls


def test_cap_unset_is_the_merged_flag_exactly(monkeypatch):
    a = _cap_run(monkeypatch, None)
    calls = []
    _install(monkeypatch, calls)
    b = ur.mix_rows(_frame(), set(), 26, 4, 4, 49_000, [3, 3] + [1] * 24, exposure_cap=13, dst_cap=6, fill="rr", spares=15,
                    bring_back_top_wr=("A1", "B"))
    assert a[:4] == b and a[4] == calls
    assert not {"rows_cap", "floored_rows", "designated_unfloored"} & set(a[2]["bring_back_top_wr"])


@pytest.mark.parametrize("cap", [2, 4])
def test_cap_n_floors_exactly_n_book_rows_and_no_spare(monkeypatch, cap):
    rows, cells, meta, spares, calls = _cap_run(monkeypatch, cap)
    bb = meta["bring_back_top_wr"]
    designated_book = sum(1 for c in cells if c in ("A1", "B"))
    assert bb["rows_cap"] == cap and bb["rows_floored"] == {"book": cap, "spares": 0} and len(bb["floored_rows"]) == cap
    assert bb["designated_unfloored"] == designated_book - cap and bb["fallbacks"] == []
    assert sum(1 for c in calls if c["floor"] is not None) == cap                    # the floor reached the optimizer N times
    assert all(f["commit_index"] < 26 and f["kind"] == "book" for f in bb["floored_rows"])
    top = M.top_receivers(list(ur.frame_players(_frame()).values()))
    opp = {p["id"]: p["opp"] for p in ur.frame_players(_frame()).values()}
    for f in bb["floored_rows"]:
        q = next(i for i in f["row"] if int(i[1:]) % 5 == 0 and i.startswith("p"))
        assert top[opp[q]] in f["row"]
    assert "rows cap %d" % cap in ur.bring_back_top_wr_line(bb)


def test_cap_an_infeasible_floored_solve_does_not_count(monkeypatch):
    rows, cells, meta, spares, calls = _cap_run(monkeypatch, 4, optimize=lambda c: _failing_floor(c, every=2))
    bb = meta["bring_back_top_wr"]
    assert bb["rows_floored"]["book"] == 4 and len(bb["floored_rows"]) == 4             # still exactly N floored
    assert bb["fallbacks"] and all(f["reason"] == "infeasible with the floor" for f in bb["fallbacks"])
    assert sum(1 for c in calls if c["floor"] is not None) == 4 + len(bb["fallbacks"])   # the next designated solve got the floor
    fl = sorted(f["commit_index"] for f in bb["floored_rows"]); fb = sorted(f["commit_index"] for f in bb["fallbacks"])
    assert not set(fl) & set(fb) and max(fb) < max(fl)                                # fallbacks sit inside the cap's run


def test_cap_the_rule_binds_only_the_floored_rows_everywhere(monkeypatch, tmp_path):
    rows, cells, meta, spares, _ = _cap_run(monkeypatch, 2)
    top, cset, exempt, required = M.bring_back_top_wr_rule({"config": {"union": {"mix": {"mix": meta}}}})
    floored = {frozenset(f["row"]) for f in meta["bring_back_top_wr"]["floored_rows"]}
    assert required == floored and cset == ("A1", "B")
    unfloored = [r for r, c in zip(rows, cells) if c in ("A1", "B") and frozenset(r) not in floored]
    assert unfloored and all(not M.rule_applies(r, exempt, required) for r in unfloored)
    assert all(M.rule_applies(r, exempt, required) for r in floored)
    # vet: a replacement (a new row) is never "required"; a floored row that lost its top WR fails
    assert V.cell_violations(ROW_WITHOUT, "A1", POS, TEAM, OPP, GAME, top_wr=TOP, rule_cells=("A1", "B"), required={frozenset(ROW_WITH)}) == \
        M.shape_violations(ROW_WITHOUT, "A1", POS, TEAM, OPP, GAME)
    assert "top-WR bring-back missing: O's top receiver o1" in V.cell_violations(
        ROW_WITHOUT, "A1", POS, TEAM, OPP, GAME, top_wr=TOP, rule_cells=("A1", "B"), required={frozenset(ROW_WITHOUT)})


def test_cap_the_audit_binds_only_floored_rows(tmp_path):
    b_row = ["AQB", "AWR1", "BRB1", "CRB0", "DWR0", "CWR2", "DTE", "EWR1", "G_DST"]

    def rec(floored):
        blk = {"cells": ["A1", "B"], "top_wr": {"B": {"id": "BWR0", "name": "B top", "salary": 7000}}, "fallbacks": [],
               "rows_cap": 2, "floored_rows": [{"row": sorted(r)} for r in floored], "designated_unfloored": 1}
        return {"config": {"union": {"mix": {"mix": {"bring_back_top_wr": blk}}}}}
    assert "stack_rules" not in _audit_run(tmp_path / "unfloored", b_row, "mix_B", rec([]))["failed"]      # past the cap: plain
    assert "stack_rules" in _audit_run(tmp_path / "floored", b_row, "mix_B", rec([b_row]))["failed"]      # floored, lost its WR


@pytest.mark.parametrize("rows_, cells_, ok", [(None, (), True), (None, ("A1", "B"), True), (2, ("A1", "B"), True),
                                               (4, ("A1",), True), (0, ("A1", "B"), False), (2, (), False)])
def test_cap_parse_and_mix_rows_refusals(monkeypatch, rows_, cells_, ok):
    if ok:
        assert ur.parse_bring_back_top_wr_rows(rows_, cells_) == rows_
    else:
        with pytest.raises(SystemExit, match="--mix-bring-back-top-wr-rows"):
            ur.parse_bring_back_top_wr_rows(rows_, cells_)
    _install(monkeypatch, [])
    with pytest.raises(ValueError, match="bring_back_top_wr_rows"):
        ur.mix_rows(_frame(), set(), 21, 7, 4, 49_000, W21, exposure_cap=10, dst_cap=5, bring_back_top_wr_rows=2)


# ---- parity with the harness: the lab's OWN code (nfl2 c2f5638 = origin/production/s71b-topbb-n-20261008's code commit).
# term_book (experiments/term_book.py, file sha256 62c2306e..., study 49's, the Week-5 live book's build) and
# top_bring_back_n (experiments/s71b_topbb_n.py, file sha256 1592a9c8..., 84's row choice) are pasted below BYTE FOR BYTE
# (test_the_vendored_harness_text_is_the_labs pins each function's text by sha256). They run on stand-ins for the lab's
# S18 / S24 / S28 / S46: the same cells, quotas, allocate, interleave and block_positions production uses (mix_shapes'
# verbatim copies, tested in test_mix_shapes.py) and a CapBuilder with the lab's commit contract whose optimize is an
# OUTCOME ORACLE. Production's stand-in consults the same oracle rule, so when both builds make the same solves in the
# same order they see the same outcomes; the test compares the build order (block, cell, row index j), the ruled rows
# (cell, j) and the fallbacks (cell, j). A difference is a parity failure to report to production and 84, never to fix
# here by editing the vendored text.
from collections import Counter  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from functools import partial  # noqa: E402

HARNESS_TEXT_SHA256 = {"term_book": "36ba2e4016ff02b95f1764394658884297c5d00d397dc067d00cb0e65a1b9b42",
                       "top_bring_back_n": "4b4977c0971f87ae0d6cc3923ab582fcaf44f5ed025930ccd513e4b704bbfdd6"}


class _Oracle:
    """Which solves fail, call by call: with a1, every A1 solve (a short book); every floor_every-th FLOORED solve (as
    _failing_floor); every C solve after the first c_ok (C's quota passes to A1)."""

    def __init__(self, floor_every=None, c_ok=None, a1=False):
        self.floor_every, self.c_ok, self.a1 = floor_every, c_ok, a1
        self.n_floor = self.n_c = 0

    def fails(self, cell: str, floored: bool) -> bool:
        if self.a1 and cell == "A1":
            return True
        if floored:
            self.n_floor += 1
            if self.floor_every and self.n_floor % self.floor_every == 0:
                return True
        if cell == "C":
            self.n_c += 1
            if self.c_ok is not None and self.n_c > self.c_ok:
                return True
        return False


class _HStack:                                      # one object per cell: the wrapper finds A1 / B by identity, as the lab's
    def __init__(self, cell):
        self.cell = cell


class _HLU:
    def __init__(self, ids):
        self.ids = ids


class _HCapBuilder:
    """S24.CapBuilder's contract: solve_with calls the module's optimize and COMMITS a solved row (prev / count)."""
    last = None

    def __init__(self, fr, base, lam, main_cap, dst_cap):
        self.recs = [{"id": str(i), "obj": 0.0} for i in fr["id"]]
        self.prev, self.count, self.log = [], Counter(), []
        _HCapBuilder.last = self                    # the lab's wrapper subclasses this one: record on the base

    def solve_with(self, stack, qb_game_max, pair, extra_bans):
        lu = S24.optimize(self.recs, stack=stack, banned_lineups=self.prev)
        if lu is not None:
            self.prev.append(lu.ids); self.count.update(lu.ids); self.log.append((stack.cell, len(self.prev) - 1))
        return lu


def _h_optimize(oracle):
    def optimize(recs, stack, banned_lineups, interaction_floor_weights=None, interaction_floor=None):
        if oracle.fails(stack.cell, interaction_floor_weights is not None):
            return None
        return _HLU((f"h{len(banned_lineups)}",))
    return optimize


S18 = types.SimpleNamespace(CELLS={n: (q, _HStack(n), qmax, which) for n, (q, _, qmax, which) in M.MIX_CELLS.items()},
                            allocate=M.allocate, interleave=M.interleave, pair_games=lambda fr, which: None)
S28 = types.SimpleNamespace(NAMES=list(M.MIX_CELLS), QUOTAS=[M.MIX_CELLS[n][0] for n in M.MIX_CELLS])
S46 = types.SimpleNamespace(block_positions=M.block_positions)
S24 = types.SimpleNamespace(CapBuilder=_HCapBuilder, optimize=None)


def term_book(fr, base, term, caps, weights: list[int], k_book: int, n_term: int, k: int) -> tuple[list, list[str], dict]:
    """Production's term block (union_reselect mix_rows term_rows, 27b946b3) on study 46's block mechanics: one builder
    state; the live block (k_book - n_term rows) first, study 42's round-robin on the quotas at its size, on `base`;
    then the term block (n_term rows), the same at its size, on base + term (term: points per frame row, already capped);
    positions S46.block_positions(k_book, n_term) (the term block takes the first list); each block interleaved on the
    head weights of ITS positions; the spares after, study 28's, on `base`. Returns (book rows then spares, cells, meta
    with each row's block: "L", "T" or "S")."""
    names = S28.NAMES
    b = S24.CapBuilder(fr, base, 0.0, *caps)          # inside S37.built_with(QB_CAP, ...): the QB cap 5 on every row
    plain = [float(x) for x in base]
    termed = [float(x) + float(t) for x, t in zip(base, term)]

    def set_obj(vals):
        for p, v in zip(b.recs, vals):
            p["obj"] = v

    def solve(name):
        _, stack, qmax, which = S18.CELLS[name]
        return b.solve_with(stack, qmax, S18.pair_games(fr, which), set())

    def rollback(lu):                                  # undo solve_with's commit: the state is as before the peek
        b.prev.pop(); b.count.subtract(lu.ids); b.count += Counter()

    def commit(lu):
        b.prev.append(lu.ids); b.count.update(lu.ids)

    def fill_block(n_rows: int) -> tuple[dict, list[int], dict]:
        """Study 42's round-robin (mix_fill's "rr" loop) on the quotas at the block's own size, on the shared state."""
        target = S18.allocate(S28.QUOTAS, n_rows)
        order = [names[i] for i in sorted(range(len(names)), key=lambda i: (-target[i], i))]
        left = dict(zip(names, target)); rows: dict = {n: [] for n in names}
        m = {"passes": 0, "dropped": 0, "fill_steps": 0}; rr_at = 0
        while sum(left.values()) > 0:
            m["fill_steps"] += 1
            n = next(c for c in order[rr_at:] + order[:rr_at] if left[c] > 0)
            rr_at = (order.index(n) + 1) % len(order)
            lu = solve(n)
            if lu is None:                             # the cell cannot solve on this state: its quota passes to A1
                if n == "A1":
                    m["dropped"] += left["A1"]; left["A1"] = 0
                else:
                    m["passes"] += left[n]; left["A1"] += left[n]; left[n] = 0
                continue
            rollback(lu)
            commit(lu); rows[n].append(lu); left[n] -= 1
        return rows, target, m

    t_pos, live_pos = S46.block_positions(k_book, n_term)
    set_obj(plain)
    live_rows, live_t, live_m = fill_block(len(live_pos))            # the live block first, plain
    set_obj(termed)
    term_rows, term_t, term_m = fill_block(len(t_pos)) if t_pos else ({n: [] for n in names}, [0] * len(names), {})
    set_obj(plain)                                                    # the spares on the plain objective
    slots: dict = {}
    for P, rows, tag in ((live_pos, live_rows, "L"), (t_pos, term_rows, "T")):     # each block on its own positions
        got = [len(rows[n]) for n in names]
        seq = S18.interleave(got, S28.QUOTAS, [weights[p] for p in P])
        ptr = [0] * len(names)
        for p, j in zip(P, seq):
            slots[p] = (rows[names[j]][ptr[j]], names[j], tag); ptr[j] += 1
    book, cells, blocks = [], [], []
    for p in sorted(slots):                            # a short block leaves its last positions empty: the book closes up
        lu, c, t = slots[p]; book.append(lu); cells.append(c); blocks.append(t)
    spare_target = S18.allocate(S28.QUOTAS, max(0, k - len(book)))         # study 28's spares, unchanged
    for i in sorted(range(len(names)), key=lambda i: (-spare_target[i], i)):
        for _ in range(spare_target[i]):
            cell, lu = names[i], solve(names[i])
            if lu is None:
                cell, lu = "A1", solve("A1")
            if lu is None:
                break
            book.append(lu); cells.append(cell); blocks.append("S")
    return book, cells, {"blocks": blocks, "term_positions": t_pos,
                         "live_block": {"target_rows": dict(zip(names, live_t)), "cell_rows": {n: len(live_rows[n]) for n in names}, **live_m},
                         "term_block": {"target_rows": dict(zip(names, term_t)), "cell_rows": {n: len(term_rows[n]) for n in names}, **term_m},
                         "cell_rows": {n: len(live_rows[n]) + len(term_rows[n]) for n in names},
                         "passes": live_m.get("passes", 0) + term_m.get("passes", 0),
                         "dropped": live_m.get("dropped", 0) + term_m.get("dropped", 0)}


@contextmanager
def top_bring_back_n(cells: tuple[str, ...], qb_to_wr: dict[str, str], n_rows: int, k_book: int):
    """Study 71's wrapper with the row cap: a solve with one of `cells`' StackRules (by identity) carries the interaction
    floor only while j < k_book and fewer than n_rows book rows have been committed under the rule; infeasible -> the plain
    solve, recorded, not counted. Yields the class (`satisfied` / `unsatisfied` lists of (cell, j))."""
    orig_cls, orig_opt = S24.CapBuilder, S24.optimize
    target = {id(S18.CELLS[c][1]): c for c in cells}

    class TopBBNBuilder(orig_cls):
        satisfied: list = []
        unsatisfied: list = []

        def __init__(self, fr, base, lam, main_cap, dst_cap):
            super().__init__(fr, base, lam, main_cap, dst_cap)
            ids = {str(p["id"]) for p in self.recs}
            self.pairs = {(q, w): 1.0 for q, w in qb_to_wr.items() if q in ids and w in ids}

        def solve_with(self, stack, qb_game_max, pair, extra_bans: set):
            cell = target.get(id(stack))
            j = len(self.prev)
            if cell is None or j >= k_book or len(type(self).satisfied) >= n_rows:
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            lu = None
            if self.pairs:
                S24.optimize = partial(orig_opt, interaction_floor_weights=self.pairs, interaction_floor=1.0)
                try:
                    lu = super().solve_with(stack, qb_game_max, pair, extra_bans)
                finally:
                    S24.optimize = orig_opt
            if lu is not None:
                type(self).satisfied.append((cell, j))
                return lu
            type(self).unsatisfied.append((cell, j))
            return super().solve_with(stack, qb_game_max, pair, extra_bans)

    TopBBNBuilder.satisfied, TopBBNBuilder.unsatisfied = [], []
    S24.CapBuilder = TopBBNBuilder
    try:
        yield TopBBNBuilder
    finally:
        S24.CapBuilder, S24.optimize = orig_cls, orig_opt


def test_the_vendored_harness_text_is_the_labs():
    import ast
    src = (ROOT / "tests" / "test_s71_bring_back_top_wr.py").read_text()
    lines = src.splitlines(keepends=True)
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in HARNESS_TEXT_SHA256:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            text = "".join(lines[start - 1:node.end_lineno])
            assert hashlib.sha256(text.encode()).hexdigest() == HARNESS_TEXT_SHA256[node.name], node.name


def _harness_build(cap, n_term, oracle, k_book=26, k=41):
    fr = _frame()
    S24.optimize = _h_optimize(oracle)
    with top_bring_back_n(("A1", "B"), {"p0": "p2"}, cap, k_book) as TB:
        book, cells, meta = term_book(fr, [0.0] * len(fr), [0.0] * len(fr), (13, 6), [3, 3] + [1] * (k_book - 2), k_book, n_term, k)
        log = list(_HCapBuilder.last.log)
    n_live, n_t = sum(meta["live_block"]["cell_rows"].values()), sum(meta["term_block"]["cell_rows"].values())
    tags = ["L"] * n_live + ["T"] * n_t + ["S"] * (len(log) - n_live - n_t)
    committed = set(log)
    return ([(t, c, j) for t, (c, j) in zip(tags, log)], [tuple(x) for x in TB.satisfied],
            [tuple(x) for x in TB.unsatisfied if tuple(x) in committed], n_live + n_t)


def _cell_of(stack) -> str:
    return next(n for n, (_, rules, _, _) in M.MIX_CELLS.items() if all(getattr(stack, f) == v for f, v in rules.items()))


def _cheap_file_term(tmp_path, points=2.0):
    """A cheap-block file in cheap_block_file.py's columns for the fixture (every skill player; under $6,000 at +POINTS,
    pred_own = POINTS / 0.20), read through production's own_bonus and capped as the union does (tilt 0.20, cap POINTS)."""
    fr = _frame(); sk = fr[fr.pos != "DST"]
    b = np.where(sk.salary < 6000, points, 0.0)
    f = tmp_path / "cheap2.csv"
    pd.DataFrame({"dk_player_id": range(1, len(sk) + 1), "id": sk.id, "display_name": sk.name, "pos": sk.pos, "team": sk.team,
                  "opp": sk.opp, "pred_own": np.round(b / 0.20, 4), "bonus_points": b}).to_csv(f, index=False)
    raw, _ = ur.own_bonus(f, fr, set(), 0.20, 0.5)
    term = {i: min(v, points) for i, v in raw.items()}
    assert term and set(term.values()) == {points}
    return term


def _production_build(monkeypatch, tmp_path, cap, n_term, oracle):
    calls = []

    def optimize(*args, **kw):
        if oracle.fails(_cell_of(kw["stack"]), kw.get("interaction_floor_weights") is not None):
            return None
        return inner(*args, **kw)
    inner = _stand_in(calls)
    _install(monkeypatch, calls, optimize)
    kw = dict(exposure_cap=13, dst_cap=6, fill="rr", spares=15, bring_back_top_wr=("A1", "B"), bring_back_top_wr_rows=cap)
    if n_term:
        kw.update(term_rows=n_term, term_bonus=_cheap_file_term(tmp_path))
    rows, cells, meta, spares = ur.mix_rows(_frame(), set(), 26, 4, 4, 49_000, [3, 3] + [1] * 24, **kw)
    order = [tuple(c.split(":")) if ":" in c else ("L", c) for c in meta["commit_order"]]
    built = [(t, c, j) for j, (t, c) in enumerate(order)] + [("S", c, len(order) + s) for s, (_, c) in enumerate(spares)]
    bb = meta["bring_back_top_wr"]
    return (built, [(f["cell"], f["commit_index"]) for f in bb["floored_rows"]],
            [(f["cell"], f["commit_index"]) for f in bb["fallbacks"]], len(rows), meta)


@pytest.mark.parametrize("cap, n_term, oracle_kw", [
    (2, 8, {}),                                     # Week 5's configuration (the cheap +2 block on 8 rows), TOPBB_N2
    (4, 8, {}),                                     # TOPBB_N4
    (4, 8, {"floor_every": 2}),                     # infeasible floored solves: re-solved plain, not counted
    (4, 8, {"floor_every": 3, "c_ok": 3}),          # and C failing: its quota passes to A1 (both blocks, the spares)
    (3, 0, {"c_ok": 2}),                            # no block: production's plain round-robin fill
    (9, 8, {"a1": True}),                           # a SHORT book: the first spares sit at j < 26 (84's "book")
])
def test_cap_parity_with_the_labs_own_term_book_and_row_choice(monkeypatch, tmp_path, cap, n_term, oracle_kw):
    built_h, sat, unsat, n_book_h = _harness_build(cap, n_term, _Oracle(**oracle_kw))
    built_p, floored, fallbacks, n_book_p, meta = _production_build(monkeypatch, tmp_path, cap, n_term, _Oracle(**oracle_kw))
    assert n_book_p == n_book_h
    assert built_p[:n_book_p] == built_h[:n_book_h]                                # the same book, built in the same order
    if n_book_p == 26:
        assert built_p == built_h                                                  # and the same 15 spares
    assert floored == sat and fallbacks == unsat                                   # the same ruled rows and fallbacks, by j
    assert len(floored) == cap and all(j < 26 for _, j in floored)
    if oracle_kw.get("floor_every"):
        assert fallbacks and all(f["reason"] == "infeasible with the floor" for f in meta["bring_back_top_wr"]["fallbacks"])
    if oracle_kw.get("a1"):                                                        # 84's j < K_book, not the phase flag:
        kinds = {f["commit_index"]: f["kind"] for f in meta["bring_back_top_wr"]["floored_rows"]}
        assert n_book_p < 26 and any(kinds[j] == "spare" for _, j in floored)      # a spare at j < 26 took the rule


def test_cap_the_row_index_rule_with_a_full_book_floors_no_spare(monkeypatch, tmp_path):
    """With a full book the spares start at j = 26: under a cap no spare takes the rule, whatever the cap."""
    built, floored, _, n_book, meta = _production_build(monkeypatch, tmp_path, 40, 8, _Oracle())
    bb = meta["bring_back_top_wr"]
    designated = [j for _, c, j in built if c in ("A1", "B")]
    assert n_book == 26 and [j for _, j in floored] == [j for j in designated if j < 26]
    assert bb["rows_floored"]["spares"] == 0 and bb["designated_unfloored"] == 0
