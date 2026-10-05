"""union_reselect: the pure parts (survivor filtering, the game cap, projected sums, the Saturday-run picker) on synthetic
frames; the pinned lab clone is not needed. The Week-3 rehearsal on real run dirs is the integration test (HANDOFF)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import union_reselect as ur  # noqa: E402


def _frame():
    rows = []
    for k in range(12):
        rows.append({"id": f"p{k}", "name": f"P{k}", "pos": ["QB", "RB", "WR", "TE"][k % 4], "team": "A" if k < 6 else "B",
                     "opp": "B" if k < 6 else "A", "salary": 5000, "game_id": "g1" if k < 8 else "g2",
                     "mean_projection": 10.0 if k != 5 else 0.4, "status": "OUT" if k == 7 else "", "dk_player_id": 100 + k})
    rows.append({"id": "A_DST", "name": "A", "pos": "DST", "team": "A", "opp": "B", "salary": 3000, "game_id": "g1",
                 "mean_projection": 7.0, "status": "", "dk_player_id": 999})
    return pd.DataFrame(rows)


def _cands(*rosters):
    return pd.DataFrame({"players": [",".join(r) for r in rosters], "tag": ["lev"] * len(rosters)})


def test_survivors_apply_every_t70_rule_and_count_each():
    fr = _frame()
    ok = ["p0", "p1", "p2", "p3", "p4", "p6", "p8", "p9", "A_DST"]
    missing = ok[:-1] + ["zz"]
    out = ok[:-2] + ["p7", "A_DST"]                     # p7 is OUT by status
    low = ok[:-2] + ["p5", "A_DST"]                     # p5 projects 0.4 < 1.0
    dup = list(ok)
    sat = _cands(ok, missing, out, low, dup)
    rosters, idx, counts = ur.survivors(sat, fr, {frozenset(dup)}, 1.0, None, None)
    assert rosters == [] and idx == []                  # ok == dup, so the only clean roster is a duplicate of the T-70 pool
    assert counts["dropped_missing_from_t70"] == 1 and counts["dropped_unavailable"] == 1
    assert counts["dropped_below_min_proj"] == 1 and counts["dropped_duplicate_of_t70"] == 2 and counts["saturday_pool"] == 5
    assert counts["unavailable_players"] == ["p7"]
    rosters, idx, counts = ur.survivors(sat, fr, set(), 1.0, None, None)
    assert [sorted(r) for r in rosters] == [sorted(ok), sorted(ok)] and idx == [0, 4] and counts["survivors"] == 2


def test_game_cap_drops_rosters_over_the_cap():
    fr = _frame()
    heavy = ["p0", "p1", "p2", "p3", "p4", "p6", "p8", "p9", "A_DST"]     # g1: p0-p4,p6,A_DST = 7
    rosters, idx, counts = ur.survivors(_cands(heavy), fr, set(), 1.0, 4, None)
    assert rosters == [] and counts["dropped_game_cap"] == 1
    rosters, _, _ = ur.survivors(_cands(heavy), fr, set(), 1.0, 7, None)
    assert len(rosters) == 1


def test_projected_sum_fails_closed_on_an_unprojected_id():
    proj = {"a": 1.5, "b": 2.0}
    assert ur.projected_sum([["a", "b"], ["b"]], proj).tolist() == [3.5, 2.0]
    with pytest.raises(SystemExit, match="does not project"):
        ur.projected_sum([["a", "zz"]], proj)


def test_pick_saturday_run_takes_the_newest_matching_dose_built_before_the_t70_run(tmp_path):
    def mk(name, lev, boom, built, banks=True):
        d = tmp_path / name; d.mkdir()
        (d / "receipt.json").write_text(json.dumps({"built_utc": built, "config": {"lev": lev, "boom": boom}}))
        if banks:
            for b in ur.BANKS:
                (d / b).write_bytes(b"x")
    mk("20260926T150000Z-a", 2560, 10240, "2026-09-26 15:00:00+00:00")
    mk("20260926T160000Z-b", 2560, 10240, "2026-09-26 16:00:00+00:00")
    mk("20260926T170000Z-c", 2560, 10240, "2026-09-26 17:00:00+00:00", banks=False)   # no sidecars
    mk("20260927T140000Z-d", 640, 2560, "2026-09-27 14:00:00+00:00")                   # the wrong dose
    mk("20260927T160000Z-e", 2560, 10240, "2026-09-27 16:00:00+00:00")                 # after the T-70 run
    got = ur.pick_saturday_run(tmp_path, 2560, 10240, "2026-09-27 15:50:00+00:00")
    assert got.name == "20260926T160000Z-b"
    with pytest.raises(SystemExit, match="no Saturday run dir"):
        ur.pick_saturday_run(tmp_path, 1280, 5120, "2026-09-27 15:50:00+00:00")


def test_frame_players_carry_the_lab_shape():
    fr = _frame()
    p = ur.frame_players(fr)
    assert set(p["p0"]) == {"id", "name", "pos", "team", "opp", "salary", "game_id", "proj"} and p["p0"]["proj"] == 10.0
    assert ur._LU([p["p0"], p["A_DST"]], "t").salary == 8000


def test_pick_saturday_run_filters_group_window_unions_and_superseded(tmp_path):
    def mk(name, lev, boom, built, group=154078, union=False, superseded=False):
        d = tmp_path / name; d.mkdir()
        cfg = {"lev": lev, "boom": boom}
        if union:
            cfg["union"] = {"t70_run": "x"}
        (d / "receipt.json").write_text(json.dumps({"built_utc": built, "draft_group": group, "config": cfg}))
        for b in ur.BANKS:
            (d / b).write_bytes(b"x")
        if superseded:
            (d / "superseded").touch()
    mk("20260930T150000Z-smoke", 2560, 10240, "2026-09-30 15:00:00+00:00")                 # Wednesday's smoke: before the window
    mk("20261003T150000Z-sat", 2560, 10240, "2026-10-03 15:00:00+00:00")
    mk("20261003T160000Z-sat-other", 2560, 10240, "2026-10-03 16:00:00+00:00", group=154077)  # another slate
    mk("20261003T170000Z-union", 2560, 10240, "2026-10-03 17:00:00+00:00", union=True)        # a union dir, never the supply
    mk("20261003T180000Z-sup", 2560, 10240, "2026-10-03 18:00:00+00:00", superseded=True)
    got = ur.pick_saturday_run(tmp_path, 2560, 10240, "2026-10-04 15:50:00+00:00", group="154078", after="2026-10-03T05:00:00")
    assert got.name == "20261003T150000Z-sat"
    with pytest.raises(SystemExit, match="no Saturday run dir"):
        ur.pick_saturday_run(tmp_path, 2560, 10240, "2026-10-04 15:50:00+00:00", group="154078", after="2026-10-03T15:30:00")


def test_main_exposure_cap_rows_at_the_week4_shape():
    assert ur.main_exposure_cap(0.5, 36) == 18                 # as entered (L13's PMO_X50); the old hard-coded int(0.5 * K)
    assert [ur.main_exposure_cap(s, 36) for s in (0.4, 0.34, 0.25, 1.0)] == [14, 12, 9, 36]
    assert ur.main_exposure_cap(0.5, 1) == 1
    for bad in (0, -0.1, 1.01):
        with pytest.raises(ValueError):
            ur.main_exposure_cap(bad, 36)


def _rows(*rs):
    return [frozenset(r) for r in rs]


def test_sleeve_player_cap_skips_rows_over_the_cap():
    rosters = _rows("ab", "ac", "ad", "bc", "bd")
    scores = [5.0, 4.0, 3.0, 2.0, 1.0]
    assert ur.select_top_mean_player_cap(scores, rosters, 3, None, player_cap=2) == [0, 1, 3]   # a in 2 rows: "ad" skipped
    assert ur.select_top_mean_player_cap(scores, rosters, 3, None, player_cap=3) == [0, 1, 2]   # the cap does not bind


def test_sleeve_player_cap_keeps_ties_repeats_and_overlap_like_the_lab():
    rosters = _rows("abc", "abc", "abd", "xyz", "abe")
    scores = [1.0, 1.0, 1.0, 0.5, 1.0]
    # ties by index; the repeated roster (1) skipped; "abd" shares 2 > max_shared 1 with "abc"; "abe" likewise
    assert ur.select_top_mean_player_cap(scores, rosters, 2, 1, player_cap=5) == [0, 3]
    with pytest.raises(RuntimeError, match="only 2 rows"):
        ur.select_top_mean_player_cap(scores, rosters, 3, 1, player_cap=5)
    with pytest.raises(ValueError):
        ur.select_top_mean_player_cap(scores, rosters, 2, 1, player_cap=0)


def test_sleeve_player_cap_equals_the_pinned_lab_selector_when_it_never_binds():
    two_track = pytest.importorskip("nfl2.two_track")      # the pinned lab clone on PYTHONPATH (the live build's form)
    rng = np.random.default_rng(7)
    rosters = [frozenset(rng.choice(40, 9, replace=False).tolist()) for _ in range(400)]
    scores = np.round(rng.normal(120, 8, 400), 1)          # rounded: real ties
    for max_shared in (None, 5, 7):
        assert ur.select_top_mean_player_cap(scores, rosters, 60, max_shared, player_cap=60) == \
            two_track.select_top_mean(scores, rosters, 60, max_shared=max_shared)


def test_sleeve_exposure_reads_the_slice():
    fr = pd.DataFrame({"id": ["a", "b", "c"], "name": ["A", "B", "C"]})
    ex = ur.sleeve_exposure([0, 1], _rows("ab", "ac"), fr)
    assert ex["max_rows_per_player"] == 2 and ex["distinct_players"] == 3 and ex["top5"][0] == {"id": "a", "name": "A", "rows": 2}


# ---- the ownership term in the main's objective (reviewer 2026-09-29) ----

def _own_file(tmp_path, rows, name="own.csv"):
    p = tmp_path / name
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def _own_rows(fr, values=None, by="dk_player_id"):
    sk = fr[fr.pos != "DST"]
    v = values or {}
    return [{by: (r.dk_player_id if by == "dk_player_id" else r.id), "display_name": r["name"], "pos": r.pos,
             "pred_own": v.get(r.id, 4.0)} for _, r in sk.iterrows()]


def test_own_bonus_is_tilt_times_percent_for_skill_players_only(tmp_path):
    fr = _frame()
    rows = _own_rows(fr, {"p0": 30.0, "p1": -0.2, "p2": 0.0}) + [{"dk_player_id": 999, "display_name": "A", "pos": "DST", "pred_own": 50.0}]
    bonus, meta = ur.own_bonus(_own_file(tmp_path, rows), fr, {"p7"}, 0.2, 0.9)
    assert bonus["p0"] == pytest.approx(6.0) and bonus["p3"] == pytest.approx(0.8)
    assert "A_DST" not in bonus                                   # a DST never carries the term
    assert "p1" not in bonus and "p2" not in bonus                # a clipped negative and a zero add nothing
    assert "p7" not in bonus                                      # excluded from the pool (OUT)
    assert meta["negatives_clipped"] == 1 and meta["matched_by"] == {"dk_player_id": 12} and meta["coverage_projected_5"] == 1.0
    assert meta["tilt"] == 0.2 and len(meta["source_sha256"]) == 64 and meta["largest_terms"][0]["name"] == "P0"


def test_own_bonus_matches_float_spelled_ids_and_falls_to_gsis(tmp_path):
    fr = _frame()
    rows = _own_rows(fr)
    for r in rows:
        r["dk_player_id"] = f"{r['dk_player_id']}.0"              # a csv round trip through a float column
    bonus, meta = ur.own_bonus(_own_file(tmp_path, rows), fr, set(), 0.1, 0.9)
    assert len(bonus) == 12 and meta["matched_by"] == {"dk_player_id": 12}
    bonus, meta = ur.own_bonus(_own_file(tmp_path, _own_rows(fr, by="gsis_id"), "g.csv"), fr, set(), 0.1, 0.9)
    assert len(bonus) == 12 and meta["matched_by"] == {"gsis_id": 12}


def test_own_bonus_refuses_by_name(tmp_path):
    fr = _frame()
    good = _own_rows(fr)
    with pytest.raises(SystemExit, match="OWN TERM REFUSED.*does not exist"):
        ur.own_bonus(tmp_path / "absent.csv", fr, set(), 0.2, 0.9)
    with pytest.raises(SystemExit, match="OWN TERM REFUSED.*outside"):
        ur.own_bonus(_own_file(tmp_path, good), fr, set(), 2.0, 0.9)            # 2.0 points per ownership point: a typo
    with pytest.raises(SystemExit, match="OWN TERM REFUSED.*needs pred_own"):
        ur.own_bonus(_own_file(tmp_path, [{"dk_player_id": 100, "own": 3.0}], "cols.csv"), fr, set(), 0.2, 0.9)
    with pytest.raises(SystemExit, match="OWN TERM REFUSED.*not numbers"):
        ur.own_bonus(_own_file(tmp_path, good[:-1] + [dict(good[-1], pred_own="n/a")], "nan.csv"), fr, set(), 0.2, 0.9)
    with pytest.raises(SystemExit, match="OWN TERM REFUSED.*below -0.5"):
        ur.own_bonus(_own_file(tmp_path, good[:-1] + [dict(good[-1], pred_own=-3.0)], "neg.csv"), fr, set(), 0.2, 0.9)
    with pytest.raises(SystemExit, match="OWN TERM REFUSED.*fractions"):
        ur.own_bonus(_own_file(tmp_path, [dict(r, pred_own=0.2) for r in good], "frac.csv"), fr, set(), 0.2, 0.9)
    # p5 projects 0.4 (below the coverage floor) and p7 is excluded, so 10 players count; 8 named = 80% < 90%
    short = [r for r in good if r["dk_player_id"] not in (100, 101)]
    with pytest.raises(SystemExit, match=r"OWN TERM REFUSED.*8 of the pool's 10 .*missing e.g. \['P0', 'P1'\]"):
        ur.own_bonus(_own_file(tmp_path, short, "short.csv"), fr, {"p7"}, 0.2, 0.9)
    assert len(ur.own_bonus(_own_file(tmp_path, short, "short2.csv"), fr, {"p7"}, 0.2, 0.8)[0]) == 9


def _fake_lab(monkeypatch, seen):
    """The pinned lab clone is not needed: a stand-in optimize records what it is asked to maximize."""
    import types

    class LU:
        def __init__(self, players):
            self.players = players

    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env):
        seen.append({"objective_col": objective_col, "values": {p["id"]: p[objective_col] for p in pool}, "keys": set(pool[0])})
        best = sorted((p for p in pool if not bans or p["id"] not in bans), key=lambda p: (-p[objective_col], p["id"]))[:9]
        return None if len(seen) > 1 else LU(best)
    lineup = types.ModuleType("nfl2.core.lineup"); lineup.optimize = optimize
    pipeline = types.ModuleType("nfl2.pipeline"); pipeline.PRODUCTION_STACK = "stack"
    for name, mod in (("nfl2", types.ModuleType("nfl2")), ("nfl2.core", types.ModuleType("nfl2.core")),
                      ("nfl2.core.lineup", lineup), ("nfl2.pipeline", pipeline)):
        monkeypatch.setitem(sys.modules, name, mod)


def test_pmo_rows_without_a_term_is_the_call_entered_in_week4(monkeypatch):
    seen = []
    _fake_lab(monkeypatch, seen)
    rows = ur.pmo_rows(_frame(), {"p7"}, 1, 7, 4, 49_000, set())
    assert len(rows) == 1 and seen[0]["objective_col"] == "proj" and "obj" not in seen[0]["keys"]
    seen.clear()
    ur.pmo_rows(_frame(), {"p7"}, 1, 7, 4, 49_000, set(), bonus={})             # an empty term is no term
    assert seen[0]["objective_col"] == "proj" and "obj" not in seen[0]["keys"]


def test_pmo_rows_with_a_term_maximizes_projection_plus_the_term(monkeypatch):
    seen = []
    _fake_lab(monkeypatch, seen)
    rows = ur.pmo_rows(_frame(), {"p7"}, 1, 7, 4, 49_000, set(), bonus={"p0": 6.0, "p9": 0.5})
    v = seen[0]["values"]
    assert seen[0]["objective_col"] == "obj"
    assert v["p0"] == pytest.approx(16.0) and v["p9"] == pytest.approx(10.5) and v["p1"] == pytest.approx(10.0)
    assert v["A_DST"] == pytest.approx(7.0) and "p7" not in v
    assert rows[0][0] == "p0"                                                   # the term moved the first pick


def test_resolve_saturday_run_auto_returns_the_picked_dir_not_auto(tmp_path):
    """Week-4 smoke 2026-10-01: an if/else mis-nesting overwrote the auto-picked dir with Path('auto') ('auto: missing'),
    so every armed union (UNION_SATURDAY_RUN=auto) failed. Resolution is now one function, tested on all three paths."""
    d = tmp_path / "20261003T153000Z-sat"; d.mkdir()
    (d / "receipt.json").write_text(json.dumps({"built_utc": "2026-10-03 15:30:00+00:00", "config": {"lev": 2560, "boom": 10240}}))
    for b in ur.BANKS:
        (d / b).write_bytes(b"x")
    t70 = {"built_utc": "2026-10-04 15:50:00+00:00", "config": {"lev": 0, "boom": 4800}}
    got = ur.resolve_saturday_run("auto", "2560/10240", tmp_path, t70, "t70", None, None)
    assert got == d and got.name != "auto"
    assert ur.resolve_saturday_run(str(d), "2560/10240", tmp_path, t70, "t70", None, None) == d          # an explicit dir
    with pytest.raises(SystemExit, match="IS a 2560/10240 build"):
        ur.resolve_saturday_run("auto", "2560/10240", tmp_path, {**t70, "config": {"lev": 2560, "boom": 10240}}, "t70", None, None)


def test_resolve_saturday_run_takes_the_first_listed_dose_with_a_run_else_the_next(tmp_path, capsys):
    """Operator 2026-10-01 (cracks audit B): UNION_SAT_DOSE is an ordered list; a missing D12800 falls back to the D6400,
    loudly; a T-70 run equal to ANY listed dose gets no union; no listed dose at all refuses with every reason."""
    def mk(name, lev, boom):
        d = tmp_path / name; d.mkdir()
        (d / "receipt.json").write_text(json.dumps({"built_utc": "2026-10-03 16:00:00+00:00", "config": {"lev": lev, "boom": boom}}))
        for b in ur.BANKS:
            (d / b).write_bytes(b"x")
        return d
    d6400 = mk("20261003T160000Z-d6400", 1280, 5120)
    t70 = {"built_utc": "2026-10-04 15:50:00+00:00", "config": {"lev": 0, "boom": 4800}}
    got = ur.resolve_saturday_run("auto", "2560/10240,1280/5120", tmp_path, t70, "t70", None, None)
    assert got == d6400 and "!!! SATURDAY SUPPLY FALLBACK: 2560/10240" in capsys.readouterr().out
    d12800 = mk("20261003T170000Z-d12800", 2560, 10240)
    assert ur.resolve_saturday_run("auto", "2560/10240,1280/5120", tmp_path, t70, "t70", None, None) == d12800
    assert "FALLBACK" not in capsys.readouterr().out
    with pytest.raises(SystemExit, match="IS a 1280/5120 build"):
        ur.resolve_saturday_run("auto", "2560/10240,1280/5120", tmp_path, {**t70, "config": {"lev": 1280, "boom": 5120}}, "t70", None, None)
    with pytest.raises(SystemExit, match="no Saturday supply for any listed dose"):
        ur.resolve_saturday_run("auto", "640/2560,160/640", tmp_path, t70, "t70", None, None)


def test_build_host_skips_the_union_for_any_listed_supply_dose():
    host = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_build_host.sh").read_text()
    line = next(l for l in host.splitlines() if "IS the Saturday supply" in l or "any listed supply dose" in l)
    import subprocess
    for dose, expect in (("1280/5120", "skip"), ("2560/10240", "skip"), ("0/4800", "union")):
        lev, boom = dose.split("/")
        script = (f'UNION_SATURDAY_RUN=auto; UNION_SAT_DOSE=2560/10240,1280/5120; PAID_LEV={lev}; PAID_BOOM={boom}\n'
                  'if [[ -n "${UNION_SATURDAY_RUN:-}" && ",${UNION_SAT_DOSE:-2560/10240}," == *",$PAID_LEV/$PAID_BOOM,"* ]]; then echo skip; else echo union; fi')
        assert subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout.strip() == expect
    assert '",${UNION_SAT_DOSE:-2560/10240}," == *",$PAID_LEV/$PAID_BOOM,"*' in host


def test_game_row_caps_rank_by_total_with_the_frozen_p3():
    fr = pd.DataFrame({"game_id": ["g1", "g2", "g3", "g1"], "game_total": [44.5, 51.5, 48.5, 44.5]})
    caps = ur.game_row_caps(fr, 105)
    assert caps == {"g2": 42, "g3": 35, "g1": 24}                   # ranks 1,2,3: floor(.409/.336/.234 x 105)
    assert ur.GAME_CAP_P3[1] == 0.409 and ur.GAME_CAP_P3[14] == 0.080 and ur.GAME_CAP_P3_TAIL == 0.08


def test_pmo_rows_game_cap_limits_a_used_up_game_to_two_players(monkeypatch):
    """Study 1: once game g has its budget of rows with >= 3 of its players, later solves get (g's ids, '<=', 2)."""
    import types
    seen = []

    class LU:
        def __init__(self, players):
            self.players = players

    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, set_constraints=None):
        seen.append(set_constraints)
        avail = [p for p in pool if frozenset([p["id"]]) and (not bans or p["id"] not in bans)]
        pick = sorted(avail, key=lambda p: p["id"])[len(seen) - 1:len(seen) + 8]
        return LU(pick) if len(pick) == 9 else None
    lineup = types.ModuleType("nfl2.core.lineup"); lineup.optimize = optimize
    pipeline = types.ModuleType("nfl2.pipeline"); pipeline.PRODUCTION_STACK = "stack"
    for name, mod in (("nfl2", types.ModuleType("nfl2")), ("nfl2.core", types.ModuleType("nfl2.core")),
                      ("nfl2.core.lineup", lineup), ("nfl2.pipeline", pipeline)):
        monkeypatch.setitem(sys.modules, name, mod)
    rows = ur.pmo_rows(_frame(), {"p7"}, 3, 7, 4, 49_000, set(), game_caps={"g1": 1, "g2": 5})
    assert len(rows) >= 2
    assert seen[0] is None                                          # nothing used up before the first row
    g1_ids = sorted(seen[1][0][0])
    assert seen[1][0][1:] == ("<=", 2) and "A_DST" in g1_ids and "p0" in g1_ids and "p8" not in g1_ids
    seen.clear()
    ur.pmo_rows(_frame(), {"p7"}, 2, 7, 4, 49_000, set())             # no game_caps: never a set constraint
    assert all(s is None for s in seen)


def test_heavy_games_counts_three_or_more_from_one_game():
    row = [{"game_id": "a"}] * 3 + [{"game_id": "b"}] * 2 + [{"game_id": "c"}] * 4
    assert ur.heavy_games(row) == {"a", "c"}
    assert ur.heavy_games([{"game_id": "a"}] * 2) == set()


def test_game_row_caps_gives_a_game_without_a_total_the_tail_cap(capsys):
    fr = pd.DataFrame({"game_id": ["g1", "g2", "g3"], "game_total": [44.5, None, 51.5]})
    caps = ur.game_row_caps(fr, 105)
    assert caps == {"g3": 42, "g1": 35, "g2": 8}                    # g2 ranked last: floor(0.08 x 105)
    assert "GAME CAP WARNING" in capsys.readouterr().err and "g2" in caps


def test_main_rows_refusal_is_named_for_the_cap_with_or_without_the_term():
    ur.check_main_rows([1] * 5, 5, {"g": 1}, {"p": 1.0})             # enough rows: no refusal
    with pytest.raises(SystemExit, match=r"GAME CAP REFUSED: 4 of 5 .*\(with the ownership term\)"):
        ur.check_main_rows([1] * 4, 5, {"g": 1}, {"p": 1.0})
    with pytest.raises(SystemExit, match="GAME CAP REFUSED: 4 of 5 rows solved under the per-game cap$"):
        ur.check_main_rows([1] * 4, 5, {"g": 1}, None)
    with pytest.raises(SystemExit, match="OWN TERM REFUSED: 4 of 5"):
        ur.check_main_rows([1] * 4, 5, None, {"p": 1.0})
