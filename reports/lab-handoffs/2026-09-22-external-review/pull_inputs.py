"""Pull every input the external-review analyses read, into a directory OUTSIDE the repo.

    python pull_inputs.py <out_dir> [--no-linestar]

Read-only BigQuery (project from `nfl_dfs.config` defaults / gcloud) plus, unless
--no-linestar, one polite pass over LineStar's public GetSalariesV5 endpoint (the same
endpoint and User-Agent as src/nfl_dfs/ingest/linestar_backfill.py, 1.2 s between calls,
72 calls).  The outputs contain DraftKings contest ownership and vendor projections:
never commit them (this repo is public).
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from google.cloud import bigquery

PROJECT = "nfl-predictions-503414"
PANEL = "20260811-pitclean-e80-k1-a12ab31"   # point-in-time K=1 replay projections, 2019/2021-2025
MILLY = {(2026, 1): "193028206", (2026, 2): "195648007"}

Q = {
    # the Sunday-main Millionaire of every 2022-2025 week (Thursday/MEGA/$555 variants excluded)
    "milly_own": f"""
        WITH c AS (
          SELECT season, week, contest_id, ANY_VALUE(contest_name) nm,
                 SAFE_CAST(REGEXP_EXTRACT(ANY_VALUE(contest_name), r"\\[(\\d+) entries") AS INT64) ent
          FROM `{PROJECT}.nfl_raw.contest_ownership` WHERE season BETWEEN 2022 AND 2025 GROUP BY 1,2,3),
        pick AS (
          SELECT season, week, ARRAY_AGG(STRUCT(contest_id, nm, ent) ORDER BY ent DESC LIMIT 1)[OFFSET(0)] AS p
          FROM c WHERE REGEXP_CONTAINS(nm, r"Fantasy Football Millionaire")
            AND NOT REGEXP_CONTAINS(nm, r"\\(Thu\\)|MEGA|\\$555") GROUP BY 1,2)
        SELECT o.season, o.week, pick.p.nm AS contest, o.display_name, o.roster_position, o.pct_drafted
        FROM `{PROJECT}.nfl_raw.contest_ownership` o
        JOIN pick ON o.season = pick.season AND o.week = pick.week AND o.contest_id = pick.p.contest_id""",
    "spf": f"""
        SELECT season, week, gsis_id, name, pos, team, salary, mean_projection, market_points,
               model_points_pre, proj_p90, own_est, actual, implied_team_total
        FROM `{PROJECT}.nfl_predictions.slate_player_features`
        WHERE panel_run_id = "{PANEL}" AND season BETWEEN 2022 AND 2025""",
    "played": f"""
        SELECT season, week, player_id FROM `{PROJECT}.nfl_raw.weekly_stats`
        WHERE season BETWEEN 2022 AND 2026 AND season_type = "REG" """,
    "injuries": f"""
        SELECT CAST(season AS INT64) season, CAST(week AS INT64) week, gsis_id,
               ANY_VALUE(report_status) report_status, ANY_VALUE(practice_status) practice_status
        FROM `{PROJECT}.nfl_raw.injuries` WHERE season BETWEEN 2022 AND 2025 AND game_type = "REG"
        GROUP BY 1, 2, 3""",
    "schedules": f"""
        SELECT season, week, home_team, away_team, gametime, weekday FROM `{PROJECT}.nfl_raw.schedules`
        WHERE season BETWEEN 2022 AND 2026 AND game_type = "REG" """,
    "replay_books": f"""
        SELECT season, week, entry_ix, tag, player, pos, team, salary, proj, actual
        FROM `{PROJECT}.nfl_features.replay_lineups_pitk1_*` WHERE season BETWEEN 2022 AND 2025""",
    # DK points from box scores for 2026 weeks 1-2 (players nobody drafted are missing from standings)
    "dk_points_2026": f"""
        SELECT player_id, player_display_name, position, team, week,
          0.04*IFNULL(passing_yards,0)+4*IFNULL(passing_tds,0)-IFNULL(passing_interceptions,0)
          +IF(IFNULL(passing_yards,0)>=300,3,0)+0.1*IFNULL(rushing_yards,0)+6*IFNULL(rushing_tds,0)
          +IF(IFNULL(rushing_yards,0)>=100,3,0)+IFNULL(receptions,0)+0.1*IFNULL(receiving_yards,0)
          +6*IFNULL(receiving_tds,0)+IF(IFNULL(receiving_yards,0)>=100,3,0)-IFNULL(fumbles_lost_total,0)
          +2*(IFNULL(passing_2pt_conversions,0)+IFNULL(rushing_2pt_conversions,0)+IFNULL(receiving_2pt_conversions,0))
          +6*IFNULL(special_teams_tds,0)+6*IFNULL(fumble_recovery_tds,0) AS dk
        FROM `{PROJECT}.nfl_raw.weekly_stats` WHERE season = 2026 AND week IN (1, 2) AND season_type = "REG" """,
    # 2026 standings carry one row per player per roster slot (WR and FLEX rows): dedupe per slot, then SUM.
    # (2022-25 rows are one per player, so MAX is correct there.)  Corrected 2026-09-22 after the laptop's grain find.
    "milly_own_2026": f"""
        WITH d AS (SELECT DISTINCT week, display_name, roster_position, pct_drafted, fpts
                   FROM `{PROJECT}.nfl_raw.contest_ownership`
                   WHERE season = 2026 AND ((week = 1 AND contest_id = "{MILLY[(2026, 1)]}")
                                         OR (week = 2 AND contest_id = "{MILLY[(2026, 2)]}")))
        SELECT week, display_name, SUM(pct_drafted) own, MAX(fpts) fpts FROM d GROUP BY 1, 2""",
    # the last served projection before each 2026 lock (the Sunday 11:0x CT run, after the 10:30 inactives)
    "live_proj_2026": f"""
        SELECT week, gsis_id, display_name, position, team, salary, proj_points
        FROM `{PROJECT}.nfl_predictions.player_projections`
        WHERE season = 2026 AND (
          (week = 1 AND generated_at BETWEEN TIMESTAMP("2026-09-13 16:03:00") AND TIMESTAMP("2026-09-13 16:05:00"))
       OR (week = 2 AND generated_at BETWEEN TIMESTAMP("2026-09-20 16:02:00") AND TIMESTAMP("2026-09-20 16:03:00")))""",
}

LINESTAR = ("https://www.linestarapp.com/DesktopModules/DailyFantasyApi/API/"
            "Fantasy/GetSalariesV5?sport=1&site=1&periodId={pid}")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) nfl-dfs-personal-research"}


def pull_linestar(out: Path) -> None:
    s = requests.Session()
    periods = {}
    for p in s.get(LINESTAR.format(pid=0), headers=UA, timeout=30).json().get("Periods", []):
        m = re.match(r"^Week (\d+), (\d{4})$", p.get("Name", ""))
        if m and 2022 <= int(m.group(2)) <= 2025:
            periods[int(p["Id"])] = (int(m.group(2)), int(m.group(1)))
    rows = []
    for pid, (season, week) in sorted(periods.items()):
        time.sleep(1.2)
        raw = s.get(LINESTAR.format(pid=pid), headers=UA, timeout=45).json()
        sc = json.loads(raw["SalaryContainerJson"])
        main = [sl for sl in sc.get("Slates", []) if sl.get("SlateName") == "Main"]
        proj_own = {}
        if main:
            for o in ((raw.get("Ownership") or {}).get("Projected") or {}).get(str(main[0]["Id"]), []):
                proj_own[o.get("PlayerId")] = o.get("Owned")
        for r in sc.get("Salaries", []):
            rows.append({"season": season, "week": week, "pid": r.get("PID"), "name": r.get("Name"),
                         "pos": r.get("POS"), "team": r.get("PTEAM"), "sal": r.get("SAL"),
                         "ls_pp": r.get("PP"), "ls_ceil": r.get("Ceil"), "ls_floor": r.get("Floor"),
                         "ls_proj_own": proj_own.get(r.get("PID")), "main_slate": bool(main)})
        print(f"linestar {season} w{week}: {len(proj_own)} projected-ownership rows", flush=True)
    pd.DataFrame(rows).to_csv(out / "linestar.csv", index=False)


def main() -> None:
    out = Path(sys.argv[1]).expanduser().resolve()
    if Path(__file__).resolve().parents[3] in out.parents:
        raise SystemExit("refusing to write DK/vendor data inside the repository")
    out.mkdir(parents=True, exist_ok=True)
    client = bigquery.Client(project=PROJECT)
    for name, sql in Q.items():
        df = client.query(sql).to_dataframe()
        df.to_csv(out / f"{name}.csv", index=False)
        print(f"{name}: {len(df)} rows", flush=True)
    if "--no-linestar" not in sys.argv:
        pull_linestar(out)


if __name__ == "__main__":
    main()
