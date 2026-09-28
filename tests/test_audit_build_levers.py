"""The fail-loud build audit (operator 2026-09-27): every check passes on a clean synthetic run dir and each one fails
when its defect is planted. Offline; no BigQuery."""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("audit_build_levers", ROOT / "scripts" / "audit_build_levers.py")
ABL = importlib.util.module_from_spec(spec); spec.loader.exec_module(ABL)

GAMES = [("A", "B", "g1"), ("C", "D", "g2"), ("E", "F", "g3"), ("G", "H", "g4")]


def _frame() -> pd.DataFrame:
    rows = []
    for home, away, g in GAMES:
        for t, o in ((home, away), (away, home)):
            rows.append(dict(id=f"{t}QB", name=f"{t} QB", pos="QB", team=t, opp=o, game_id=g, salary=6000, proj=18.0))
            for j in range(2):
                rows.append(dict(id=f"{t}RB{j}", name=f"{t} RB{j}", pos="RB", team=t, opp=o, game_id=g, salary=6500 - 800 * j, proj=14.0 - 3 * j))
            for j in range(3):
                rows.append(dict(id=f"{t}WR{j}", name=f"{t} WR{j}", pos="WR", team=t, opp=o, game_id=g, salary=7000 - 1200 * j, proj=15.0 - 3 * j))
            rows.append(dict(id=f"{t}TE", name=f"{t} TE", pos="TE", team=t, opp=o, game_id=g, salary=4200, proj=9.0))
            rows.append(dict(id=f"{t}_DST", name=f"{t} DST", pos="DST", team=t, opp=o, game_id=g, salary=2800, proj=7.0))
            rows.append(dict(id=f"{t}PUNT", name=f"{t} punt", pos="WR", team=t, opp=o, game_id=g, salary=3500, proj=4.0))
            rows.append(dict(id=f"{t}BACKUP", name=f"{t} backup", pos="QB", team=t, opp=o, game_id=g, salary=4000, proj=0.0))
            rows.append(dict(id=f"{t}INJ", name=f"{t} injured WR", pos="WR", team=t, opp=o, game_id=g, salary=5000, proj=0.0))
    fr = pd.DataFrame(rows)
    fr["proj_tourney"] = fr["proj"]
    fr.loc[fr["id"].str.endswith("PUNT"), "proj_tourney"] = 11.0          # legal punt upside: playable, <= $4,000
    fr["status"] = "None"; fr["dk_player_id"] = range(1000, 1000 + len(fr))
    fr["market_points"] = fr["proj"] * 0.98; fr.loc[fr["proj"] < 5, "market_points"] = None
    fr["dk_ppg"] = fr["proj"]
    return fr


THIRD = {"A": "E", "B": "E", "C": "G", "D": "G", "E": "A", "F": "A", "G": "C", "H": "C"}   # a team from a third game


def _lineup(t: str, o: str, other: str) -> list[str]:
    """QB + 2 same-team WR + 1 bring-back RB (4 from the QB's game) + RB/WR/TE/WR from `other` (4) + a DST from a third
    game: legal under the 4-per-game cap, salary 49,300."""
    return [f"{t}QB", f"{t}WR1", f"{t}WR2", f"{o}RB1", f"{other}RB0", f"{other}WR0", f"{other}TE", f"{other}WR2", f"{THIRD[other]}_DST"]


def _run_dir(tmp: Path, fr: pd.DataFrame | None = None, lineups: list[list[str]] | None = None, receipt: dict | None = None,
             book: list[list[str]] | None = None) -> Path:
    run = tmp / "run"; run.mkdir(parents=True, exist_ok=True)
    fr = _frame() if fr is None else fr
    fr.to_parquet(run / "frame.parquet")
    if lineups is None:
        lineups = [_lineup("A", "B", "C"), _lineup("C", "D", "E"), _lineup("E", "F", "G"), _lineup("G", "H", "A"), _lineup("B", "A", "D")]
    cands = pd.DataFrame({"cand": range(len(lineups)), "players": [",".join(l) for l in lineups], "tag": "lev"})
    cands.to_parquet(run / "candidates.parquet")
    book = lineups[:5] if book is None else book                     # the CONTESTS layout below needs 5 mean rows
    with (run / "book.csv").open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]); w.writerows(book)
    r = {"written": len(book), "config": {"selector": "dual_emax", "operational_k": len(book), "arm": {"max_per_game": 4}}}
    if receipt: r["config"].update(receipt.get("config", {})); r.update({k: v for k, v in receipt.items() if k != "config"})
    (run / "receipt.json").write_text(json.dumps(r))
    return run


CONTESTS = [{"name": "sat", "contest_id": "1", "entries": 1, "keep": 1}, {"name": "sat", "contest_id": "2", "entries": 1, "keep": 1},
            {"name": "big", "contest_id": "3", "entries": 3, "keep": 3}]


def _audit(run, contests=CONTESTS, **kw):
    args = dict(layout="head", expect_selector="dual_emax", expect_max_per_game=4, min_salary=40000, punt_max=4000,
                market_floor=0.3, sources={"market_points": 0.3, "dk_ppg": 0.9}, fade="off")
    args.update(kw)
    return ABL.audit(run, contests, **args)


def test_clean_run_passes_every_check(tmp_path):
    res = _audit(_run_dir(tmp_path))
    assert res["ok"], [c for c in res["checks"] if not c["ok"]]
    assert {c["check"] for c in res["checks"]} >= {"candidates_no_nonplayers", "punt_valuation_availability", "fade_effect", "max_per_game",
                                                    "stack_rules", "salary_bounds", "market_sources", "declared_sources_present",
                                                    "selector_and_tracks", "book_rows_legal"}


def test_non_player_in_a_candidate_fails(tmp_path):
    bad = _lineup("A", "B", "C"); bad[5] = "CINJ"                          # a receiver projected 0.0 (not playing)
    res = _audit(_run_dir(tmp_path, lineups=[bad, _lineup("C", "D", "E"), _lineup("E", "F", "G"), _lineup("G", "H", "A"), _lineup("B", "A", "D")]))
    assert "candidates_no_nonplayers" in res["failed"]


def test_punt_upside_on_a_non_player_or_an_expensive_player_fails(tmp_path):
    fr = _frame(); fr.loc[fr["id"] == "ABACKUP", "proj_tourney"] = 10.9    # the Week-3 Winston/Kyle Allen defect
    assert "punt_valuation_availability" in _audit(_run_dir(tmp_path, fr=fr))["failed"]
    fr = _frame(); fr.loc[fr["id"] == "AWR0", "proj_tourney"] = 25.0       # upside applied above the punt price
    assert "punt_valuation_availability" in _audit(_run_dir(tmp_path / "b", fr=fr))["failed"]


def test_fade_declared_on_but_absent_fails_and_undeclared_fade_fails(tmp_path):
    fr = _frame(); fr["own_est"] = fr["proj"]                              # ownership present, objective untouched
    res = _audit(_run_dir(tmp_path, fr=fr), fade="on")
    assert "fade_effect" in res["failed"]                                  # the 2026 no-op: fade "on", nothing moved
    fr2 = _frame(); fr2["own_est"] = fr2["proj"]; top = fr2.sort_values("own_est", ascending=False).head(20).index
    fr2.loc[top, "proj_tourney"] = fr2.loc[top, "proj"] - 1.0
    assert _audit(_run_dir(tmp_path / "b", fr=fr2), fade="on")["ok"]      # a real fade passes
    assert "fade_effect" in _audit(_run_dir(tmp_path / "c", fr=fr2), fade="off")["failed"]   # ...and is an undeclared lever if OFF


def test_construction_rules_are_checked_on_every_candidate(tmp_path):
    over = _lineup("A", "B", "C"); over[4] = "BRB0"                        # a 5th player from game g1
    five = [over, _lineup("C", "D", "E"), _lineup("E", "F", "G"), _lineup("G", "H", "A"), _lineup("B", "A", "D")]
    assert "max_per_game" in _audit(_run_dir(tmp_path, lineups=five))["failed"]
    nostack = _lineup("A", "B", "C"); nostack[2] = "DWR1"                  # one same-team receiver only (D is in game g2 with C)
    five2 = [nostack, _lineup("C", "D", "E"), _lineup("E", "F", "G"), _lineup("G", "H", "A"), _lineup("B", "A", "D")]
    assert "stack_rules" in _audit(_run_dir(tmp_path / "b", lineups=five2))["failed"]
    assert "salary_bounds" in _audit(_run_dir(tmp_path / "c"), min_salary=60000)["failed"]


def test_market_and_declared_sources_fail_closed(tmp_path):
    fr = _frame(); fr["market_points"] = None
    assert "market_sources" in _audit(_run_dir(tmp_path, fr=fr))["failed"]
    res = _audit(_run_dir(tmp_path / "b"), sources={"market_points": 0.3, "fp_route_share_l4": 0.5})
    assert "declared_sources_present" in res["failed"] and "fp_route_share_l4: column absent" in res["checks"][7]["detail"]


def test_selector_tracks_and_book_are_checked(tmp_path):
    assert "selector_and_tracks" in _audit(_run_dir(tmp_path), expect_selector="mean")["failed"]
    tail = CONTESTS + [{"name": "milly", "contest_id": "9", "entries": 1, "keep": 1, "track": "tail"}]
    lus = [_lineup("A", "B", "C"), _lineup("C", "D", "E"), _lineup("E", "F", "G"), _lineup("G", "H", "A"), _lineup("B", "A", "D"), _lineup("D", "C", "F")]
    # the layout needs 5 mean rows (sat x2 -> rows 1, 2; big x3 -> head 1-2 + unique 3..) + 1 sleeve row = a book of 6
    run = _run_dir(tmp_path / "b", lineups=lus, book=lus[:6], receipt={"written": 6, "config": {"selector": "mean", "operational_k": 5, "tail_sleeve": {"rows": 1, "line": 210}}})
    res = _audit(run, contests=tail, expect_selector="mean")
    assert "selector_and_tracks" not in res["failed"], res["checks"][8]
    run2 = _run_dir(tmp_path / "c", lineups=lus, book=lus[:6], receipt={"written": 6, "config": {"selector": "mean", "operational_k": 6}})
    assert "selector_and_tracks" in _audit(run2, contests=tail, expect_selector="mean")["failed"]   # sleeve not recorded
    dup = _run_dir(tmp_path / "d", book=[_lineup("A", "B", "C"), _lineup("A", "B", "C"), _lineup("C", "D", "E"), _lineup("E", "F", "G"), _lineup("G", "H", "A")])
    assert "book_rows_legal" in _audit(dup)["failed"]


def test_cli_exits_2_and_writes_a_receipt_on_failure(tmp_path):
    bad = _lineup("A", "B", "C"); bad[5] = "CINJ"
    run = _run_dir(tmp_path, lineups=[bad, _lineup("C", "D", "E"), _lineup("E", "F", "G"), _lineup("G", "H", "A"), _lineup("B", "A", "D")])
    contests = tmp_path / "contests.json"; contests.write_text(json.dumps(CONTESTS))
    rc = ABL.main([str(run), "--contests", str(contests), "--layout", "head", "--min-salary", "40000", "--out", str(tmp_path / "a.json")])
    assert rc == 2 and json.loads((tmp_path / "a.json").read_text())["failed"] == ["candidates_no_nonplayers"]
