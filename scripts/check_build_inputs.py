#!/usr/bin/env python3
"""Money-build input gate (read-only; laptop plan Phase 0 item 1). Exit 0 only when every input is present and fresh.

  python scripts/check_build_inputs.py --season 2026 --week 3 --chosen-dose $OUT/chosen-dose.env --contests $OUT/contests.json
        [--receipt PATH] [--max-age-minutes 120] [--tabpfn-table nfl_features.tabpfn_projections]

Checks: the latest production projection batch (rows, skill rows, age), the market-source monitor (latest batch age,
props share, unmatched rows; FAIL when the table is absent), the TabPFN cache for the target week, the chosen-dose
file and contests.json. Writes a JSON receipt of every identity it read when --receipt is given. Nothing is
substituted on failure; the reasons are printed and the exit code is 1. Your preflight calls this and stops on 1.
"""
import argparse, hashlib, json, pathlib, sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.inference.build_inputs import assess_files, assess_projections, assess_tabpfn, verdict  # noqa: E402
from nfl_dfs.inference.market_monitor import assess_batch  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
ap.add_argument("--chosen-dose"); ap.add_argument("--contests"); ap.add_argument("--receipt")
ap.add_argument("--max-age-minutes", type=float, default=120.0); ap.add_argument("--min-props-share", type=float, default=0.30)
ap.add_argument("--tabpfn-table", default="tabpfn_projections")
ap.add_argument("--draft-group", type=int, default=None,
                help="DK draft group of the target slate. The TabPFN sufficiency floor is derived from its "
                     "skill-player count; without it sufficiency cannot be checked and the gate fails closed. "
                     "(dk_salaries.week is NULL on every row, so the slate cannot be found by week.)")
a = ap.parse_args()
from google.api_core.exceptions import NotFound
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
now = datetime.now(timezone.utc)

proj = query_df(f"""SELECT generated_at, gsis_id, position, proj_points FROM `{settings.predictions}.player_projections`
                    WHERE season = {a.season} AND week = {a.week} QUALIFY generated_at = MAX(generated_at) OVER ()""")
p = assess_projections(proj, now=now, max_age_minutes=a.max_age_minutes)
try:
    ms = query_df(f"""SELECT generated_at, gsis_id, display_name, position, source, market_points, proj_points
                      FROM `{settings.predictions}.market_source_log` WHERE season = {a.season} AND week = {a.week} AND path = 'project-slate'
                      QUALIFY generated_at = MAX(generated_at) OVER ()""")
    m = assess_batch(ms, now=now, max_age_minutes=a.max_age_minutes, min_props_share=a.min_props_share)
except NotFound:
    m = {"ok": False, "line": "market-source monitor not deployed (nfl_predictions.market_source_log absent)", "counts": {}}
tab = query_df(f"""SELECT week, COUNT(*) n FROM `{settings.features}.{a.tabpfn_table}` WHERE season = {a.season} GROUP BY week""")
rows_for_week = int(tab.loc[tab.week == a.week, "n"].sum()) if len(tab) else 0
# The sufficiency denominator is the slate itself, read from the newest pull of the named
# draft group. Absent a draft group this stays None and assess_tabpfn fails closed rather
# than passing an unchecked cache.
expected_rows = None
if a.draft_group:
    slate = query_df(f"""WITH newest AS (
                           SELECT position FROM `{settings.raw}.dk_salaries`
                           WHERE draft_group_id = {a.draft_group}
                           QUALIFY pulled_at = MAX(pulled_at) OVER ())
                         SELECT COUNTIF(position IN ('QB','RB','WR','TE')) skill, COUNT(*) all_rows
                         FROM newest""")
    expected_rows = int(slate.skill.iloc[0]) if len(slate) else 0
t = assess_tabpfn(rows_for_week, tab.week.tolist() if len(tab) else [], target_week=a.week,
                  expected_rows=expected_rows)
dose = None
if a.chosen_dose and pathlib.Path(a.chosen_dose).exists():
    dose = dict(line.strip().split("=", 1) for line in open(a.chosen_dose) if "=" in line and not line.startswith("#"))
contests = json.load(open(a.contests)) if a.contests and pathlib.Path(a.contests).exists() else None
contests = contests if isinstance(contests, list) or contests is None else contests.get("contests")
f = assess_files(dose, contests)
v = verdict(p, m, t, f)
tab_line = (f"tabpfn rows {rows_for_week} (weeks {t['weeks_present']}, slate {t['expected_rows']}, "
            f"floor {t['sufficiency_floor']})")
print(f"{v['status']} build inputs for {a.season} week {a.week}: "
      f"projections {p.get('rows')} rows (skill {p.get('skill_rows')}, {p.get('age_minutes', float('nan')):.0f} min old); "
      f"market {m.get('line', '')[:160]}; {tab_line}; "
      f"files {'ok' if f['ok'] else f['reason']}")
for r in v["reasons"]: print(f"  FAIL: {r}")
if a.receipt:
    sha = lambda path: hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() if path and pathlib.Path(path).exists() else None
    pathlib.Path(a.receipt).write_text(json.dumps({"schema": "build-inputs-gate/v1", "checked_utc": now.isoformat(), "season": a.season, "week": a.week,
        "verdict": v, "chosen_dose": dose, "chosen_dose_sha256": sha(a.chosen_dose), "contests_sha256": sha(a.contests), "tabpfn_table": a.tabpfn_table, "draft_group": a.draft_group}, indent=2, default=str) + "\n")
sys.exit(0 if v["ok"] else 1)
