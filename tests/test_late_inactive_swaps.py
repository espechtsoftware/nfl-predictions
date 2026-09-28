"""R4 late-inactive replacement planner (operator 2026-09-28): best legal same-slot replacement from the served frame;
locked cells and impossible rows are UNREPAIRED (exit 2), never skipped quietly."""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("late_inactive_swaps", ROOT / "scripts" / "late_inactive_swaps.py")
LIS = importlib.util.module_from_spec(spec); spec.loader.exec_module(LIS)

EARLY, LATE = "2026-09-27T17:00:00Z", "2026-09-27T20:25:00Z"


def _frame():
    rows = [
        # dd, pid, name, pos, team, salary, proj, game, start
        ("1", "p1", "QB A", "QB", "A", 6000, 20, "g1", EARLY), ("2", "p2", "RB A", "RB", "A", 6000, 14, "g1", EARLY),
        ("3", "p3", "RB B", "RB", "B", 5000, 12, "g1", EARLY), ("4", "p4", "WR A", "WR", "A", 7000, 15, "g1", EARLY),
        ("5", "p5", "WR B", "WR", "B", 6000, 13, "g1", EARLY), ("6", "p6", "WR C late", "WR", "C", 5500, 12, "g2", LATE),
        ("7", "p7", "TE A", "TE", "A", 4000, 9, "g1", EARLY), ("8", "p8", "RB C late", "RB", "C", 5000, 11, "g2", LATE),
        ("9", "p9", "DST D", "DST", "D", 3000, 7, "g2", LATE),
        # replacement candidates, all late game
        ("10", "p10", "WR D best", "WR", "D", 5500, 14, "g2", LATE), ("11", "p11", "WR D cheap", "WR", "D", 4000, 10, "g2", LATE),
        ("12", "p12", "WR D rich", "WR", "D", 8500, 16, "g2", LATE), ("13", "p13", "RB D", "RB", "D", 5000, 12, "g2", LATE),
        ("14", "p14", "TE D late", "TE", "D", 4000, 8, "g2", LATE), ("15", "p15", "WR D out", "WR", "D", 5500, 15, "g2", LATE),
    ]
    return pd.DataFrame(rows, columns=["dk_draftable_id", "dk_player_id", "name", "pos", "team", "salary", "proj", "game_id", "game_start"])


def _snapshot(out: set[str]):
    fr = _frame(); out = set(out) | {"p15"}                       # "WR D out" is always out
    return [{"id": pid, "status": ("OUT" if pid in out else ""), "game_start": start} for pid, start in zip(fr.dk_player_id, fr.game_start)]


ROW = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]          # salary 47,500 -> a floor of 40,000 in tests
NOW = datetime(2026, 9, 27, 18, 40, tzinfo=timezone.utc)      # 13:40 CT: early games started, late ones not


def test_best_legal_same_slot_replacement_is_chosen():
    swaps, rec = LIS.plan_swaps([ROW], _frame(), _snapshot({"p6"}), NOW, min_salary=40000)
    assert swaps == ["1:6:10"]                                  # WR slot; p15 (higher proj) is out; p12 breaks the cap
    assert rec["rows"][0]["in_name"] == "WR D best" and rec["unrepaired"] == []


def test_started_game_is_locked_and_reported():
    swaps, rec = LIS.plan_swaps([ROW], _frame(), _snapshot({"p4"}), NOW, min_salary=40000)   # an early-game WR
    assert swaps == [] and rec["unrepaired"][0]["why"].startswith("game already started")


def test_salary_floor_and_second_out_in_the_same_row():
    swaps, rec = LIS.plan_swaps([ROW], _frame(), _snapshot({"p6", "p8"}), NOW, min_salary=47000)
    assert swaps == ["1:6:10", "1:8:13"] and rec["unrepaired"] == []
    swaps, rec = LIS.plan_swaps([ROW], _frame(), _snapshot({"p6"}), NOW, min_salary=47600)     # only the $8,500 WR reaches the floor... and breaks the cap: unrepaired
    assert swaps == [] and rec["unrepaired"][0]["why"] == "no legal replacement"


def test_absent_from_the_feed_is_out_and_cli_exits_2_when_unrepaired(tmp_path):
    fr = _frame(); snap = [s for s in _snapshot(set()) if s["id"] != "p6"]      # p6 missing from the fresh feed
    swaps, rec = LIS.plan_swaps([ROW], fr, snap, NOW, min_salary=40000)
    assert swaps == ["1:6:10"]
    up = tmp_path / "up.csv"; up.write_text("QB,RB,RB,WR,WR,WR,TE,FLEX,DST\n" + ",".join(["1", "2", "3", "4", "5", "6", "7", "8", "9"]) + "\n")
    fr.to_parquet(tmp_path / "frame.parquet")
    sp = tmp_path / "snap.csv"; sp.write_text("id,status,game_start\n" + "\n".join(f"{s['id']},{s['status']},{s['game_start']}" for s in _snapshot({"p4"})) + "\n")
    rc = LIS.main(["--upload", str(up), "--frame", str(tmp_path / "frame.parquet"), "--snapshot", str(sp), "--now", NOW.isoformat(), "--min-salary", "40000", "--out", str(tmp_path / "r.json")])
    assert rc == 2 and json.loads((tmp_path / "r.json").read_text())["unrepaired"]
