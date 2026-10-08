"""Study 71 (union_reselect --mix-bring-back-top-wr; production's agreed format with amendments a-d, 10-08): the top-receiver
definition (parity with study 70's top_wr), mix_rows' interaction floor and its fallback record, the shape check, the ONE
shared reader, vet_replace_v4's lenient house fallback and late-scratch rule, and the build audit. Offline: a stand-in
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
    assert M.bring_back_top_wr_rule({}) == ({}, (), set())
    assert M.bring_back_top_wr_rule({"config": {"union": {"mix": {"mix": {"cells": {}}}}}}) == ({}, (), set())
    top, cells, ex = M.bring_back_top_wr_rule(_receipt([ROW_WITHOUT], with_term_fallbacks=[ROW_WITH]),
                                              vet_receipt={"bring_back_top_wr_exempt": [{"row": sorted(["a", "b"]), "reason": "house fallback"}]})
    assert top == TOP and cells == ("A1", "B")
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
    _, _, exempt = M.bring_back_top_wr_rule({"config": {"union": {"mix": {"mix": meta}}}})
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
    assert "bb_top, bb_cells, bb_exempt = bring_back_top_wr_rule(src)" in text
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
