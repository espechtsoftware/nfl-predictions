"""Pre-lock phantom scan of one served projection batch (read-only).

Lists main-slate skill players projected >= --min-proj whose DraftKings status (latest pull of the main draft group) is
O / OUT / IR / D(oubtful) or whose rosters_weekly status for the week is not ACT. A clean batch prints no rows.
Also reports the market source of named players from market_source_log for the same batch (e.g. --watch "Justin Jefferson").

  python week3_phantom_scan.py --season 2026 --week 3 --group 153769 [--generated-at '2026-09-26 15:00:00'] [--watch NAME ...]
Exit 0 = clean, 1 = at least one phantom (or a watched player without a props source), 2 = no batch found.
"""
from __future__ import annotations

import argparse
import sys

from nfl_dfs.bq import query_df
from nfl_dfs.config import settings

BAD_DK = ("O", "OUT", "IR", "D", "DOUBTFUL")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--group", type=int, required=True); ap.add_argument("--generated-at")
    ap.add_argument("--min-proj", type=float, default=5.0); ap.add_argument("--watch", nargs="*", default=[])
    a = ap.parse_args()
    gen = f"TIMESTAMP('{a.generated_at}')" if a.generated_at else (
        f"(SELECT MAX(generated_at) FROM `{settings.predictions}.player_projections` WHERE season = {a.season} AND week = {a.week})")
    rows = query_df(f"""
        WITH latest AS (SELECT MAX(pulled_at) ts FROM `{settings.raw}.dk_salaries` WHERE draft_group_id = {a.group}),
        dk AS (SELECT CAST(dk_player_id AS STRING) dk, ANY_VALUE(UPPER(TRIM(IFNULL(status, '')))) dk_status
               FROM `{settings.raw}.dk_salaries`, latest WHERE draft_group_id = {a.group} AND pulled_at = latest.ts GROUP BY 1),
        ro AS (SELECT gsis_id, ANY_VALUE(status) roster_status FROM `{settings.raw}.rosters_weekly`
               WHERE season = {a.season} AND week = {a.week} GROUP BY 1)
        SELECT p.generated_at, p.display_name, p.position, p.team, p.proj_points, dk.dk_status, ro.roster_status
        FROM `{settings.predictions}.player_projections` p
        JOIN dk ON dk.dk = CAST(p.dk_player_id AS STRING)
        LEFT JOIN ro ON ro.gsis_id = p.gsis_id
        WHERE p.season = {a.season} AND p.week = {a.week} AND p.generated_at = {gen}
          AND p.position IN ('QB', 'RB', 'WR', 'TE')""")
    if rows.empty:
        print("no projection batch on this main group"); return 2
    batch = rows.generated_at.iloc[0]
    bad = rows[(rows.proj_points >= a.min_proj) & (rows.dk_status.isin(BAD_DK) | rows.roster_status.fillna("?").ne("ACT"))]
    print(f"batch {batch}: {len(rows)} main-slate skill rows; projected >= {a.min_proj}: {int((rows.proj_points >= a.min_proj).sum())}; "
          f"phantoms: {len(bad)}")
    if len(bad):
        print(bad.sort_values("proj_points", ascending=False).to_string(index=False))
    fails = len(bad)
    if a.watch:
        src = query_df(f"""SELECT display_name, source, market_points, proj_points FROM `{settings.predictions}.market_source_log`
                           WHERE season = {a.season} AND week = {a.week} AND path = 'project-slate'
                             AND generated_at = (SELECT MAX(generated_at) FROM `{settings.predictions}.market_source_log`
                                                 WHERE season = {a.season} AND week = {a.week} AND path = 'project-slate')""")
        for name in a.watch:
            hit = src[src.display_name == name]
            print(f"watch {name}: " + ("NOT IN market_source_log" if hit.empty else hit.to_string(index=False, header=False)))
            fails += int(hit.empty or (hit.source != "props").any())
    print("CLEAN" if not fails else "FLAGGED")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
