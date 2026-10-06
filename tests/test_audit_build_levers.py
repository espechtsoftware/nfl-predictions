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


def test_selector_tracks_and_book_are_checked(tmp_path, monkeypatch):
    import sys as _sys; _sys.path.insert(0, str(ROOT / "src"))
    from nfl_dfs.inference import enter_layout as _el
    monkeypatch.setattr(_el, "MEAN_ROWS_FLOOR", 5)                     # the chain's 90-row floor, shrunk for a 6-row fixture
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
    # the adopted mean sleeve repeats mean rows: a sleeve row may equal a mean row, but sleeve rows stay distinct among themselves
    rep = _run_dir(tmp_path / "e", lineups=lus, book=lus[:5] + [lus[0]], receipt={"written": 6, "config": {"selector": "mean", "operational_k": 5, "tail_sleeve": {"rows": 1, "selector_used": "mean"}}})
    res = _audit(rep, contests=tail, expect_selector="mean")
    assert "book_rows_legal" not in res["failed"], res["checks"][-1]
    rep2 = _run_dir(tmp_path / "f", lineups=lus, book=lus[:4] + [lus[0], lus[0]], receipt={"written": 6, "config": {"selector": "mean", "operational_k": 4, "tail_sleeve": {"rows": 2, "selector_used": "mean"}}})
    assert "book_rows_legal" in _audit(rep2, contests=tail, expect_selector="mean")["failed"]      # a sleeve row twice


def test_cli_exits_2_and_writes_a_receipt_on_failure(tmp_path):
    bad = _lineup("A", "B", "C"); bad[5] = "CINJ"
    run = _run_dir(tmp_path, lineups=[bad, _lineup("C", "D", "E"), _lineup("E", "F", "G"), _lineup("G", "H", "A"), _lineup("B", "A", "D")])
    contests = tmp_path / "contests.json"; contests.write_text(json.dumps(CONTESTS))
    rc = ABL.main([str(run), "--contests", str(contests), "--layout", "head", "--min-salary", "40000", "--out", str(tmp_path / "a.json")])
    assert rc == 2 and json.loads((tmp_path / "a.json").read_text())["failed"] == ["candidates_no_nonplayers"]


def test_t70_rules_effect_is_checked_both_ways(tmp_path):
    fr = _frame(); fr["depth_rank"] = 1; fr["game_start"] = "2026-09-27T17:00:00Z"
    fr.loc[fr["id"] == "ARB0", "status"] = "OUT"                                  # an absent depth-1 starter
    fr.loc[fr["id"] == "ARB1", "depth_rank"] = 2
    fr.loc[fr["id"] == "BWR0", "status"] = "Q"                                    # an early-game Questionable
    base = fr.copy()
    assert "t70_rules_effect" in _audit(_run_dir(tmp_path, fr=base), t70="on")["failed"]           # ON but no trace columns
    traced = base.copy(); traced["t70_active_q"] = traced["id"] == "BWR0"; traced["t70_vacated_net"] = (traced["id"] == "ARB1") * 1.15
    assert "t70_rules_effect" not in _audit(_run_dir(tmp_path / "b", fr=traced), t70="on")["failed"]
    assert "t70_rules_effect" in _audit(_run_dir(tmp_path / "c", fr=traced), t70="off")["failed"]   # OFF with a trace: undeclared
    half = base.copy(); half["t70_active_q"] = False; half["t70_vacated_net"] = (half["id"] == "ARB1") * 1.15
    assert "t70_rules_effect" in _audit(_run_dir(tmp_path / "d", fr=half), t70="on")["failed"]     # bump but no activation


def test_union_main_check_reads_the_declared_form(tmp_path):
    """A union receipt declaring pmo_x50 must have every main row from pmo_x50 rows, the exposure cap and the DST cap held."""
    import pandas as pd
    lus = [_lineup("A", "B", "C"), _lineup("C", "D", "E"), _lineup("E", "F", "G"), _lineup("G", "H", "A"), _lineup("B", "A", "D"), _lineup("D", "C", "F")]
    tail = CONTESTS + [{"name": "milly", "contest_id": "9", "entries": 1, "keep": 1, "track": "tail"}]
    good = {"written": 6, "config": {"selector": "mean", "operational_k": 5, "tail_sleeve": {"rows": 1, "selector_used": "mean"},
                                     "union": {"main": "pmo_x50", "pmo_x50": {"exposure_cap": 3, "max_exposure_used": 3, "dst_cap": 2, "max_dst_rows_used": 2}}}}
    run = _run_dir(tmp_path / "u", lineups=lus, book=lus[:6], receipt=good)
    c = pd.read_parquet(run / "candidates.parquet"); c["source_run"] = ["pmo_x50"] * 5 + ["saturday"]; c["book_rank"] = [1, 2, 3, 4, 5, None]
    c.to_parquet(run / "candidates.parquet")
    assert "union_main" not in _audit(run, contests=tail, expect_selector="mean")["failed"]
    bad = {"written": 6, "config": {**good["config"], "union": {"main": "pmo_x50", "pmo_x50": {"exposure_cap": 3, "max_exposure_used": 3, "dst_cap": 2, "max_dst_rows_used": 3}}}}
    run2 = _run_dir(tmp_path / "v", lineups=lus, book=lus[:6], receipt=bad)
    c.to_parquet(run2 / "candidates.parquet")
    assert "union_main" in _audit(run2, contests=tail, expect_selector="mean")["failed"]          # the DST cap was breached
    mean_rec = {"written": 6, "config": {**good["config"], "union": {"main": "mean"}}}
    run3 = _run_dir(tmp_path / "w", lineups=lus, book=lus[:6], receipt=mean_rec)
    c.to_parquet(run3 / "candidates.parquet")
    assert "union_main" in _audit(run3, contests=tail, expect_selector="mean")["failed"]          # mean main holding pmo rows


def test_t70_trace_is_read_from_player_projections_when_the_frame_lacks_it(tmp_path):
    """Sweep 2026-09-29 item 1: the lab frame never carries the t70_* columns; with --t70 on the audit reads the build's
    own batch from player_projections (by the receipt's production_generated_at) and fails by name without it."""
    import pandas as pd
    lus = [_lineup("A", "B", "C"), _lineup("C", "D", "E"), _lineup("E", "F", "G"), _lineup("G", "H", "A"), _lineup("B", "A", "D")]
    rec = {"written": 5, "season": 2026, "week": 4, "config": {"selector": "mean", "operational_k": 5, "production_generated_at": "2026-10-04 15:36:00+00:00"}}
    run = _run_dir(tmp_path / "t", lineups=lus, book=lus[:5], receipt=rec)
    calls = []
    def reader(sql):
        calls.append(sql)
        return pd.DataFrame({"gsis_id": ["x", "y"], "t70_active_q": [True, False], "t70_vacated_net": [0.0, 1.6]})
    res = _audit(run, expect_selector="mean", t70="on", t70_reader=reader)
    chk = [c for c in res["checks"] if c["check"] == "t70_rules_effect"][0]
    assert chk["ok"] and chk["trace_source"] == "player_projections" and chk["activated"] == 1 and chk["bumped"] == 1
    assert "generated_at = TIMESTAMP('2026-10-04 15:36:00+00:00')" in calls[0] and "week = 4" in calls[0]
    # the table lacks the columns (the deployed image predates the rules): the check FAILS by name
    def broken(sql):
        raise RuntimeError("Unrecognized name: t70_active_q")
    res2 = _audit(run, expect_selector="mean", t70="on", t70_reader=broken)
    chk2 = [c for c in res2["checks"] if c["check"] == "t70_rules_effect"][0]
    assert not chk2["ok"] and "ABSENT" in chk2["detail"]
    # declared OFF on a frame without the columns: no trace, passes
    res3 = _audit(run, expect_selector="mean", t70="off")
    assert [c for c in res3["checks"] if c["check"] == "t70_rules_effect"][0]["ok"]


def test_main_own_term_check_reads_the_declared_term(tmp_path):
    """A declared ownership term must have its source file (sha256 matching), coverage above the floor and a control main
    that differs from the entered main; without a term there must be no control book (reviewer 2026-09-29 gate 3)."""
    import hashlib
    import pandas as pd
    lus = [_lineup("A", "B", "C"), _lineup("C", "D", "E"), _lineup("E", "F", "G"), _lineup("G", "H", "A"), _lineup("B", "A", "D"), _lineup("D", "C", "F")]
    tail = CONTESTS + [{"name": "milly", "contest_id": "9", "entries": 1, "keep": 1, "track": "tail"}]
    src = tmp_path / "ownership_blend.csv"
    src.write_text("id,pred_own\nAQB,22.5\nCQB,15.0\nEQB,9.0\n")
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    term = {"tilt": 0.2, "source": str(src), "source_sha256": sha, "coverage_projected_5": 0.97, "min_coverage": 0.9}
    pmo = {"exposure_cap": 3, "max_exposure_used": 3, "dst_cap": 2, "max_dst_rows_used": 2, "own_term": term}
    cfg = {"selector": "mean", "operational_k": 5, "tail_sleeve": {"rows": 1, "selector_used": "mean"}, "union": {"main": "pmo_x50", "pmo_x50": pmo}}

    def make(sub, own_term=None, control=None):
        rec = {"written": 6, "config": {**cfg, "union": {"main": "pmo_x50", "pmo_x50": {**pmo, "own_term": own_term if own_term is not None else term}}}}
        run = _run_dir(tmp_path / sub, lineups=lus, book=lus[:6], receipt=rec)
        c = pd.read_parquet(run / "candidates.parquet"); c["source_run"] = ["pmo_x50"] * 5 + ["saturday"]; c["book_rank"] = [1, 2, 3, 4, 5, None]
        c.to_parquet(run / "candidates.parquet")
        if control is not None:
            with (run / "book_main_control.csv").open("w", newline="") as f:
                w = csv.writer(f); w.writerow(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]); w.writerows(control)
        return run

    ctrl = [lus[1], lus[2], lus[3], lus[4], lus[5]]                      # differs from the main (lus[0..4]) in two rows
    assert "main_own_term" not in _audit(make("ok", control=ctrl), contests=tail, expect_selector="mean")["failed"]
    assert "main_own_term" in _audit(make("nocontrol"), contests=tail, expect_selector="mean")["failed"]                    # control missing
    assert "main_own_term" in _audit(make("same", control=lus[:5]), contests=tail, expect_selector="mean")["failed"]        # identical: dead term
    assert "main_own_term" in _audit(make("sha", own_term={**term, "source_sha256": "0" * 64}, control=ctrl), contests=tail, expect_selector="mean")["failed"]
    assert "main_own_term" in _audit(make("cov", own_term={**term, "coverage_projected_5": 0.5}, control=ctrl), contests=tail, expect_selector="mean")["failed"]
    assert "main_own_term" in _audit(make("gone", own_term={**term, "source": str(tmp_path / "missing.csv")}, control=ctrl), contests=tail, expect_selector="mean")["failed"]
    assert "main_own_term" in _audit(make("short", control=ctrl[:4]), contests=tail, expect_selector="mean")["failed"]      # control not K rows
    assert "main_own_term" not in _audit(make("off", own_term={"tilt": 0.0}), contests=tail, expect_selector="mean")["failed"]
    assert "main_own_term" in _audit(make("undeclared", own_term={"tilt": 0.0}, control=ctrl), contests=tail, expect_selector="mean")["failed"]  # control without a term


def test_field_sleeve_rows_are_held_to_their_declared_limits(tmp_path):
    """union_reselect --sleeve-source field (operator 2026-10-02): its rows may carry 5 from one game (and, in `free` mode,
    no house stack); every other candidate keeps the build's cap. Without this the union's audit refuses the Sunday book."""
    five = _lineup("A", "B", "C"); five[4] = "BRB0"                        # 5 from game g1, stack and bring-back intact
    six = list(five); six[5] = "BWR0"                                     # 6 from g1
    nostack = _lineup("A", "B", "C"); nostack[2] = "DWR1"
    base = [_lineup("A", "B", "C"), _lineup("C", "D", "E"), _lineup("E", "F", "G"), _lineup("G", "H", "A"), _lineup("B", "A", "D")]
    def run(tmp, extra, src, field):
        r = _run_dir(tmp, lineups=base + extra, book=base, receipt={"config": {"tail_sleeve": {"field": field}}})
        c = pd.read_parquet(r / "candidates.parquet"); c["source_run"] = ["t70"] * len(base) + src; c.to_parquet(r / "candidates.parquet")
        return _audit(r)["failed"]
    top = {"used": True, "max_game": 5, "house_rules_applied": True}
    assert "max_per_game" not in run(tmp_path / "a", [five], ["field"], top)
    assert "max_per_game" in run(tmp_path / "b", [six], ["field"], top)               # over the field's own limit
    assert "max_per_game" in run(tmp_path / "c", [five], ["saturday"], top)            # a supply row keeps the cap of 4
    assert "max_per_game" in run(tmp_path / "d", [five], ["field"], {})                # no declared field sleeve: the cap
    assert "stack_rules" in run(tmp_path / "e", [nostack], ["field"], top)             # top mode keeps the house stack
    free = {"used": True, "max_game": 5, "house_rules_applied": False}
    assert "stack_rules" not in run(tmp_path / "f", [nostack], ["field"], free)


def test_mix_rows_are_held_to_their_own_cell(tmp_path):
    """--main mix (study 18): a row tagged mix_<cell> is checked against THAT cell's shape; a mix-main row without a known
    cell tag fails; an untagged row keeps the house check. Without this the union's audit refuses every MIX book."""
    b_row = ["AQB", "AWR1", "BRB1", "CRB0", "DWR0", "CWR2", "DTE", "EWR1", "G_DST"]     # QB+1, bb 1, 3 from g1, pair in g2
    base = [_lineup("A", "B", "C"), _lineup("C", "D", "E"), _lineup("E", "F", "G"), _lineup("G", "H", "A"), _lineup("B", "A", "D")]

    def run(tmp, tag, src):
        r = _run_dir(tmp, lineups=base + [b_row], book=base)
        c = pd.read_parquet(r / "candidates.parquet")
        c["tag"] = ["lev"] * len(base) + [tag]; c["source_run"] = ["t70"] * len(base) + [src]
        c.to_parquet(r / "candidates.parquet")
        return _audit(r)

    ok = run(tmp_path / "a", "mix_B", "mix")
    assert "stack_rules" not in ok["failed"]
    assert next(c for c in ok["checks"] if c["check"] == "stack_rules")["mix_rows"] == 1
    assert "stack_rules" in run(tmp_path / "b", "mix_A1", "mix")["failed"]          # the wrong cell: 1 mate < 2
    assert "stack_rules" in run(tmp_path / "c", "pmo_x50", "mix")["failed"]         # a mix-main row with no cell tag
    assert "stack_rules" in run(tmp_path / "d", "mix_Q", "mix")["failed"]           # an unknown cell
    assert "stack_rules" in run(tmp_path / "e", "lev", "t70")["failed"]             # untagged: the house rule, as before
