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
