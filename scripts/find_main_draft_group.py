#!/usr/bin/env python3
"""Print the DraftKings Sunday-main draft group id for a given Sunday from the latest salary pull.

Rule: among the draft groups in the most recent `nfl_raw.dk_salaries` pull on or before that Sunday that contains one, keep those whose earliest game starts at
the Sunday 12:00 CT kickoff (17:00Z) and whose latest game starts no later than 16:30 CT (21:30Z) — the classic main
slate, excluding Thursday/Monday and Sunday-night groups — and choose the one with the most players.  Week 1 (2026-09-13)
resolves to 151307 under this rule.  `--json` prints every candidate.

Usage: find_main_draft_group.py --season 2026 --sunday 2026-09-20 [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

SQL = """
SELECT CAST(pulled_at AS STRING) AS pulled_at, draft_group_id, ANY_VALUE(slate_type) AS slate_type,
       MIN(game_start) AS first_game, MAX(game_start) AS last_game,
       COUNT(DISTINCT dk_player_id) AS players, COUNT(DISTINCT team_abbr) AS teams
FROM `nfl-predictions-503414.nfl_raw.dk_salaries`
WHERE season = {season} AND pulled_at >= TIMESTAMP_SUB(TIMESTAMP('{sunday} 23:59:59+00'), INTERVAL 10 DAY)
  AND pulled_at <= TIMESTAMP('{sunday} 23:59:59+00')
GROUP BY pulled_at, draft_group_id
ORDER BY pulled_at DESC, first_game, players DESC
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--sunday", required=True, help="YYYY-MM-DD of the target Sunday")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    raw = subprocess.run(
        ["bq", "query", "--project_id", "nfl-predictions-503414", "--use_legacy_sql=false", "--format=json", "--max_rows=200", SQL.format(season=a.season, sunday=a.sunday)],
        capture_output=True, text=True, check=True,
    ).stdout
    rows = json.loads(raw) if raw.strip() else []
    first_ok = f"{a.sunday} 17:00:00"
    last_ok = f"{a.sunday} 21:30:00"
    # the most recent pull (on or before the Sunday) that contains a qualifying group wins; salaries for the next
    # Sunday appear mid-week, so early in the week there may be none yet
    # ingest-dk stamps each group's rows a second apart, so a "pull" is a minute bucket
    candidates = []
    for pull in sorted({r["pulled_at"][:16] for r in rows}, reverse=True):
        candidates = [r for r in rows if r["pulled_at"][:16] == pull and str(r.get("first_game", ""))[:19] == first_ok and str(r.get("last_game", ""))[:19] <= last_ok]
        if candidates:
            break
    candidates.sort(key=lambda r: -int(r["players"]))   # the main slate is the largest qualifying pool (Week 1: 746 vs 395)
    if a.json:
        print(json.dumps({"sunday": a.sunday, "candidates": candidates, "all_groups": rows}, indent=1))
        return 0
    if not candidates:
        latest = rows[0]["pulled_at"] if rows else "no rows"
        seen = {r["draft_group_id"]: r for r in rows if r["pulled_at"] == latest}
        print(f"no Sunday-main draft group for {a.sunday} in any pull up to that date (latest {latest}); groups in the latest pull: "
              + ", ".join(f"{g}[{str(r['first_game'])[:16]}..{str(r['last_game'])[:16]} {r['players']}p]" for g, r in seen.items()), file=sys.stderr)
        return 2
    print(candidates[0]["draft_group_id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
