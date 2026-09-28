#!/usr/bin/env python3
"""Fail-loud audit of a completed live build (operator, 2026-09-27: "I'm getting sick of being told after the week that
wrong code paths existed ... implement safeguards and fail loudly when something isn't working as it should. I don't
want fallbacks").

Reads ONE run dir (frame.parquet, candidates.parquet, receipt.json, book.csv) and the week's contests.json, and checks
that every lever the build claims to use left a measurable trace, that no lever left an undeclared trace, that every
candidate is legal, that the declared data sources reached the frame, and that the selector and book match the
contests' tracks. Any failed check exits 2 with the check named; the Sunday chain refuses the run dir. Nothing here
reads outcomes. A JSON receipt of every check and its numbers is written next to the run's own receipt.

  python scripts/audit_build_levers.py RUN_DIR --contests contests.json [--layout head] [--expect-selector dual_emax]
      [--expect-max-per-game 4] [--min-salary 49000] [--punt-max 4000] [--market-floor 0.30]
      [--sources market_points:0.30,dk_ppg:0.90,report_status:0.0] [--fade on|off] [--out audit.json]

The checks (each named in the output):
  candidates_no_nonplayers   no candidate holds a player projected under 1 point or listed OUT/IR/D at build time
  punt_valuation_availability the tournament objective exceeds the projection only for playable players at or under the
                             punt price (a non-player valued at his "upside" is exactly the Week-3 Winston defect)
  fade_effect                --fade on: the objective must sit BELOW the projection for the most-owned players (a fade
                             that leaves them untouched is the 2026 no-op); --fade off: no player above the punt price
                             may differ (an undeclared lever)
  max_per_game               every candidate respects the declared cap (QB and DST count), or the receipt declares none
  stack_rules                every candidate holds QB + >=2 same-team WR/TE + >=1 opponent skill player
  salary_bounds              every candidate's salary in [min-salary, 50000]
  market_sources             the share of projected skill players carrying a market number meets the floor
  declared_sources_present   each declared frame column meets its non-null coverage floor
  selector_and_tracks        receipt selector == expected; tail contests => the receipt's sleeve size and the book's row
                             count equal the layout's mean rows + sleeve rows
  t70_rules_effect           --t70 on: an absent depth-1 starter must have produced a bumped backup and an early-game
                             Questionable an activation (the t70_* receipt columns); --t70 off: no trace at all
  book_rows_legal            book rows are unique, complete, and every id is in the frame
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import pandas as pd

OUT_STATUSES = {"OUT", "IR", "D", "O", "DOUBTFUL", "INJURED RESERVE", "SUSPENDED", "NA", "PUP"}
SKILL = ("QB", "RB", "WR", "TE")


class AuditFailure(Exception):
    pass


def _players_of(cell: str) -> list[str]:
    return [x.strip() for x in str(cell).split(",") if x.strip()]


def audit(run: Path, contests: list[dict], *, layout: str, expect_selector: str | None, expect_max_per_game: int | None,
          min_salary: int, punt_max: int, market_floor: float, sources: dict[str, float], fade: str,
          top_owned: int = 20, t70: str = "off") -> dict:
    fr = pd.read_parquet(run / "frame.parquet")
    cands = pd.read_parquet(run / "candidates.parquet")
    receipt = json.loads((run / "receipt.json").read_text())
    book = [r for r in csv.reader((run / "book.csv").open())][1:]
    by_id = fr.set_index(fr["id"].astype(str))
    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str, **numbers):
        checks.append({"check": name, "ok": bool(ok), "detail": detail, **numbers})

    # ---- candidates_no_nonplayers
    proj = by_id["proj"].fillna(0.0).to_dict()
    status = by_id["status"].astype(str).str.upper().to_dict() if "status" in by_id else {}
    bad_rows = 0; examples: list[str] = []
    for cell in cands["players"]:
        offenders = [p for p in _players_of(cell)
                     if (p in proj and proj[p] < 1.0) or status.get(p, "") in OUT_STATUSES]
        if offenders:
            bad_rows += 1
            if len(examples) < 5:
                examples.append(",".join(by_id["name"].get(p, p) for p in offenders))
    record("candidates_no_nonplayers", bad_rows == 0,
           f"{bad_rows} of {len(cands)} candidates hold a non-player (proj < 1 or OUT/IR/D); e.g. {examples[:3]}",
           offending_candidates=bad_rows, candidates=int(len(cands)))

    # ---- punt_valuation_availability
    if "proj_tourney" in fr:
        lifted = fr[(fr["proj_tourney"] - fr["proj"]) > 0.01]
        illegal = lifted[(lifted["salary"] > punt_max) | (lifted["proj"] < 1.0)]
        record("punt_valuation_availability", len(illegal) == 0,
               f"{len(illegal)} players valued above projection while over ${punt_max} or projected under 1 point; "
               f"e.g. {illegal['name'].head(5).tolist()}", lifted=int(len(lifted)), illegal=int(len(illegal)))
    else:
        record("punt_valuation_availability", False, "frame has no proj_tourney column", lifted=0, illegal=0)

    # ---- fade_effect
    if "proj_tourney" in fr:
        above = fr[fr["salary"] > punt_max]
        moved = above[(above["proj_tourney"] - above["proj"]).abs() > 0.01]
        if fade == "on":
            own_col = next((c for c in ("own_est", "field_own", "ownership") if c in fr), None)
            if own_col is None:
                record("fade_effect", False, "--fade on but the frame carries no ownership column to fade on", moved=int(len(moved)))
            else:
                top = fr.sort_values(own_col, ascending=False).head(top_owned)
                faded = int(((top["proj_tourney"] - top["proj"]) < -0.01).sum())
                record("fade_effect", faded >= max(1, top_owned // 2),
                       f"fade declared ON: {faded} of the {top_owned} most-owned players sit below projection", faded=faded)
        else:
            record("fade_effect", len(moved) == 0,
                   f"fade declared OFF: {len(moved)} players above ${punt_max} differ from projection (undeclared lever); "
                   f"e.g. {moved['name'].head(5).tolist()}", moved=int(len(moved)))

    # ---- max_per_game, stack_rules, salary_bounds
    game = by_id["game_id"].astype(str).to_dict(); pos = by_id["pos"].astype(str).to_dict()
    team = by_id["team"].astype(str).to_dict(); opp = by_id["opp"].astype(str).to_dict() if "opp" in by_id else {}
    sal = by_id["salary"].to_dict()
    cap = expect_max_per_game if expect_max_per_game is not None else (receipt.get("config", {}).get("arm", {}) or {}).get("max_per_game")
    over_cap = 0; max_seen = 0; bad_stack = 0; bad_salary = 0; stack_examples: list[str] = []
    for cell in cands["players"]:
        ps = _players_of(cell)
        counts: dict[str, int] = {}
        for p in ps:
            counts[game.get(p, "?")] = counts.get(game.get(p, "?"), 0) + 1
        m = max(counts.values()) if counts else 0
        max_seen = max(max_seen, m)
        if cap is not None and m > int(cap):
            over_cap += 1
        qbs = [p for p in ps if pos.get(p) == "QB"]
        if len(qbs) != 1:
            bad_stack += 1
        else:
            q = qbs[0]
            mates = sum(1 for p in ps if p != q and team.get(p) == team.get(q) and pos.get(p) in ("WR", "TE"))
            bring = sum(1 for p in ps if p != q and pos.get(p) in SKILL and team.get(p) == opp.get(q))
            if mates < 2 or bring < 1:
                bad_stack += 1
                if len(stack_examples) < 3:
                    stack_examples.append(f"{by_id['name'].get(q, q)}: {mates} mates, {bring} bring-back")
        s = sum(sal.get(p, 0) for p in ps)
        if not (min_salary <= s <= 50000):
            bad_salary += 1
    record("max_per_game", (cap is None) or over_cap == 0,
           f"cap {cap}: {over_cap} candidates over it; max players from one game seen {max_seen}",
           cap=cap, over_cap=over_cap, max_seen=max_seen)
    record("stack_rules", bad_stack == 0, f"{bad_stack} candidates without QB + 2 same-team WR/TE + 1 bring-back; e.g. {stack_examples}",
           bad_stack=bad_stack)
    record("salary_bounds", bad_salary == 0, f"{bad_salary} candidates outside [{min_salary}, 50000]", bad_salary=bad_salary)

    # ---- market_sources
    skill = fr[(fr["pos"].isin(SKILL)) & (fr["proj"] >= 5)]
    share = float(skill["market_points"].notna().mean()) if "market_points" in fr and len(skill) else 0.0
    record("market_sources", share >= market_floor,
           f"{share:.1%} of projected skill players carry a market number (floor {market_floor:.0%})", market_share=round(share, 4))

    # ---- declared_sources_present
    missing = []
    coverage = {}
    for col, floor in sources.items():
        if col not in fr:
            missing.append(f"{col}: column absent"); coverage[col] = None; continue
        cov = float(fr[col].notna().mean())
        coverage[col] = round(cov, 4)
        if cov < floor:
            missing.append(f"{col}: {cov:.1%} < {floor:.0%}")
    record("declared_sources_present", not missing, f"absent or thin declared sources: {missing}" if missing else
           f"all {len(sources)} declared sources present", coverage=coverage)

    # ---- selector_and_tracks
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from nfl_dfs.inference.enter_layout import rows_needed, sleeve_size  # noqa: E402
    t = sleeve_size(contests, layout); need = rows_needed(contests, layout); k_mean = need - t
    cfg = receipt.get("config", {})
    sel_ok = expect_selector is None or cfg.get("selector") == expect_selector
    sleeve_cfg = cfg.get("tail_sleeve") or {}
    sleeve_rows = int(sleeve_cfg.get("rows", 0)) if isinstance(sleeve_cfg, dict) else int(sleeve_cfg or 0)
    written = int(receipt.get("written", 0)); opk = int(cfg.get("operational_k", 0) or 0)
    if t:
        # k_mean already carries the chain's 90-row floor (enter_layout.MEAN_ROWS_FLOOR), so the equality is exact
        tracks_ok = sleeve_rows == t and opk == k_mean and written == k_mean + t and len(book) == written
    else:
        tracks_ok = sleeve_rows == 0 and written == len(book) and written >= k_mean
    record("selector_and_tracks", sel_ok and tracks_ok,
           f"selector {cfg.get('selector')!r} (expected {expect_selector!r}); layout needs {k_mean} mean + {t} sleeve rows; "
           f"receipt written {written}, operational_k {opk}, sleeve {sleeve_rows}; book rows {len(book)}",
           selector=cfg.get("selector"), mean_rows=k_mean, sleeve=t, written=written, operational_k=opk, book_rows=len(book))

    # ---- t70_rules_effect (operator 2026-09-28): declared ON must leave a trace when there was something to act on;
    # declared OFF must leave none. The trace is the t70_* receipt columns the projection step writes.
    has_cols = {"t70_active_q", "t70_vacated_net"} <= set(fr.columns)
    n_active = int(fr["t70_active_q"].fillna(False).astype(bool).sum()) if has_cols else 0
    n_bumped = int((pd.to_numeric(fr["t70_vacated_net"], errors="coerce").fillna(0) > 0).sum()) if has_cols else 0
    st_up = fr["status"].astype(str).str.upper() if "status" in fr else pd.Series("", index=fr.index)
    absent_starters = int(((pd.to_numeric(fr.get("depth_rank"), errors="coerce") == 1) & st_up.isin(OUT_STATUSES)).sum()) if "depth_rank" in fr else 0
    early_q = 0
    if "game_start" in fr and "status" in fr:
        starts = pd.to_datetime(fr["game_start"], errors="coerce", utc=True)
        first = starts.min()
        early_q = int((st_up.isin({"Q", "QUESTIONABLE"}) & (starts == first)).sum())
    if t70 == "on":
        ok = has_cols and ((absent_starters == 0 or n_bumped > 0) and (early_q == 0 or n_active > 0))
        record("t70_rules_effect", ok,
               f"T-70 rules declared ON: receipt columns {'present' if has_cols else 'ABSENT'}; {absent_starters} absent depth-1 "
               f"starter(s) -> {n_bumped} bumped backup(s); {early_q} early-game Questionable(s) -> {n_active} activated",
               absent_starters=absent_starters, bumped=n_bumped, early_q=early_q, activated=n_active)
    else:
        record("t70_rules_effect", n_active == 0 and n_bumped == 0,
               f"T-70 rules declared OFF: {n_active} activated, {n_bumped} bumped (undeclared lever if nonzero)",
               activated=n_active, bumped=n_bumped)

    # ---- book_rows_legal
    frame_ids = set(fr["id"].astype(str)) | set(fr["dk_player_id"].astype(str)) if "dk_player_id" in fr else set(fr["id"].astype(str))
    dup = len(book) - len({tuple(sorted(r)) for r in book})
    unknown = sum(1 for r in book for x in r if x.strip() not in frame_ids)
    short = sum(1 for r in book if len(r) != 9)
    record("book_rows_legal", dup == 0 and unknown == 0 and short == 0,
           f"{dup} duplicate rows, {unknown} ids not in the frame, {short} rows without 9 slots", duplicates=dup, unknown_ids=unknown, short_rows=short)

    failed = [c["check"] for c in checks if not c["ok"]]
    return {"run": str(run), "layout": layout, "checks": checks, "failed": failed, "ok": not failed}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run", type=Path)
    ap.add_argument("--contests", type=Path, required=True)
    ap.add_argument("--layout", default="head")
    ap.add_argument("--expect-selector", default=None)
    ap.add_argument("--expect-max-per-game", type=int, default=None)
    ap.add_argument("--min-salary", type=int, default=49000)
    ap.add_argument("--punt-max", type=int, default=4000)
    ap.add_argument("--market-floor", type=float, default=0.30)
    ap.add_argument("--sources", default="market_points:0.30,dk_ppg:0.80",
                    help="comma list of frame_column:min_nonnull_share that must be present")
    ap.add_argument("--fade", choices=["on", "off"], default="off",
                    help="whether an ownership fade is declared ON for this build (the audit checks its trace either way)")
    ap.add_argument("--t70", choices=["on", "off"], default="off",
                    help="whether the T-70 rules (T70_ACTIVE_Q / T70_VACATED_BUMP) are declared ON for this build")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    contests = json.loads(a.contests.read_text()); contests = contests if isinstance(contests, list) else contests["contests"]
    sources = {}
    for item in [x for x in a.sources.split(",") if x.strip()]:
        col, floor = item.split(":"); sources[col.strip()] = float(floor)
    result = audit(a.run, contests, layout=a.layout, expect_selector=a.expect_selector, expect_max_per_game=a.expect_max_per_game,
                   min_salary=a.min_salary, punt_max=a.punt_max, market_floor=a.market_floor, sources=sources, fade=a.fade,
                   t70=a.t70)
    out = a.out or (a.run / "lever_audit.json")
    out.write_text(json.dumps(result, indent=2) + "\n")
    for c in result["checks"]:
        print(f"{'PASS' if c['ok'] else 'FAIL'} {c['check']}: {c['detail']}")
    if result["failed"]:
        print(f"BUILD AUDIT FAILED: {result['failed']} (receipt {out})", file=sys.stderr)
        return 2
    print(f"build audit OK: {len(result['checks'])} checks (receipt {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
