#!/usr/bin/env python3
"""Answer two questions about a week before anyone argues about selection.

  1. CEILING  — was this week winnable with the pool we built?
     Every applied contest entry carries per-entry `points`, so a lineup's score
     converts to a field placement. If the pool's best candidate is below the
     winning score, no ordering, selector or promotion rule could have produced a
     winner, because the pool did not contain one.

  2. COVERAGE — how close did the pool come to the lineup that actually won?
     Entries also carry a full roster, so the winning lineup can be compared
     player-by-player against every candidate. In Week 2 of 2026 the winning
     roster matched NONE of 12,555 candidates; the closest shared five of nine.
     A lineup fully buildable from players we had priced was never explored, and
     nothing was measuring that.

Both are read-only and cost one query each. Run after standings are applied, and
only after the operator has released the week's outcomes.

  python scripts/week_ceiling_and_coverage.py --season 2026 --week 2 \\
      --pool pool-realized-12555.csv [--contest '%Millionaire%'] [--out report.json]

The pool CSV needs a `names` column of pipe-separated player names and a
`realized` column. `--contest` is a LIKE pattern; omit it to report every
contest's ceiling and use the largest for coverage.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
from datetime import UTC, datetime

PROJECT = os.environ.get("GCP_PROJECT", "nfl-predictions-503414")


def _client():
    from google.cloud import bigquery
    return bigquery.Client(project=PROJECT)


def contest_ceilings(client, season: int, week: int) -> list[dict]:
    """Winning, median and p99 score for every contest with applied entries."""
    q = f"""
    SELECT contest_name, COUNT(*) AS entries, MAX(points) AS winning,
           APPROX_QUANTILES(points, 100)[OFFSET(50)] AS median_pts,
           APPROX_QUANTILES(points, 100)[OFFSET(99)] AS p99
    FROM `{PROJECT}.nfl_raw.contest_entries`
    WHERE season = {season} AND week = {week} AND points IS NOT NULL
    GROUP BY contest_name ORDER BY entries DESC
    """
    return [dict(r) for r in client.query(q).result()]


def winning_roster(client, season: int, week: int, contest_like: str) -> tuple[set, float, str]:
    """The roster, score and entry name of the top finisher in one contest."""
    q = f"""
    SELECT entry_name, points, lineup_slots_json
    FROM `{PROJECT}.nfl_raw.contest_entries`
    WHERE season = {season} AND week = {week}
      AND contest_name LIKE @c AND points IS NOT NULL
    ORDER BY points DESC LIMIT 1
    """
    from google.cloud import bigquery
    job = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("c", "STRING", contest_like)])
    rows = list(client.query(q, job_config=job).result())
    if not rows:
        raise SystemExit(f"no applied entries match contest LIKE {contest_like!r} "
                         f"for {season} week {week}")
    r = rows[0]
    roster = {s["player"] for s in json.loads(r.lineup_slots_json)}
    return roster, float(r.points), str(r.entry_name)


def coverage(pool_names: list[set], roster: set) -> dict:
    """How close the pool came, by shared-player count. Exact match is 9 of 9."""
    hist = {}
    for s in pool_names:
        hist[len(s & roster)] = hist.get(len(s & roster), 0) + 1
    return {"roster_size": len(roster),
            "exact_matches": hist.get(len(roster), 0),
            "by_shared_players": {str(k): hist[k] for k in sorted(hist, reverse=True)}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--pool", required=True, help="CSV with `names` and `realized`")
    ap.add_argument("--contest", default=None, help="LIKE pattern; default = largest field")
    ap.add_argument("--out", type=pathlib.Path)
    a = ap.parse_args(argv)

    import pandas as pd
    pool = pd.read_csv(a.pool)
    for col in ("names", "realized"):
        if col not in pool.columns:
            raise SystemExit(f"{a.pool} has no `{col}` column")
    names = [set(str(n).split("|")) for n in pool.names]
    best = float(pool.realized.max())

    client = _client()
    ceilings = contest_ceilings(client, a.season, a.week)
    if not ceilings:
        raise SystemExit(f"no applied contest entries for {a.season} week {a.week}")

    print(f"  pool: {len(pool):,} candidates, best realized {best:.2f}\n")
    print(f"  {'contest':<38}{'entries':>9}{'winning':>9}{'median':>8}{'pool best?':>13}")
    winnable = []
    for c in ceilings:
        w = float(c["winning"])
        verdict = "WINNABLE" if best >= w else f"no (-{w - best:.1f})"
        if best >= w:
            winnable.append(c["contest_name"])
        print(f"  {str(c['contest_name'])[:36]:<38}{c['entries']:>9,}{w:>9.1f}"
              f"{float(c['median_pts']):>8.1f}{verdict:>13}")
    print(f"\n  contests the pool could have won: {len(winnable)} of {len(ceilings)}")

    pattern = a.contest or f"%{str(ceilings[0]['contest_name'])[:20]}%"
    roster, wpts, wname = winning_roster(client, a.season, a.week, pattern)
    cov = coverage(names, roster)
    print(f"\n  coverage against the winner of {pattern}")
    print(f"    {wname} scored {wpts:.2f}")
    print(f"    exact matches in the pool: {cov['exact_matches']}")
    for k, n in cov["by_shared_players"].items():
        if int(k) >= max(1, cov["roster_size"] - 5):
            print(f"      {k} of {cov['roster_size']} shared: {n:,} candidates")
    if cov["exact_matches"] == 0:
        print("    -> the winning lineup was never explored by the generator")

    if a.out:
        a.out.write_text(json.dumps({
            "schema": "week-ceiling-coverage/v1", "season": a.season, "week": a.week,
            "checked_utc": datetime.now(UTC).isoformat(),
            "pool_candidates": int(len(pool)), "pool_best": best,
            "contests": [{k: (float(v) if k in ("winning", "median_pts", "p99") else v)
                          for k, v in c.items()} for c in ceilings],
            "winnable_contests": winnable,
            "coverage": {**cov, "contest": pattern, "winner": wname, "winning_points": wpts},
        }, indent=2, default=str) + "\n")
        print(f"\n  wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
