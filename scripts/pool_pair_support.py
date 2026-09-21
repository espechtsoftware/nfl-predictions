#!/usr/bin/env python3
"""Measure how much of the pair space a candidate pool actually explores.

Runs BEFORE a slate, on the generated pool, with no outcomes. It answers the
question that the Week-2 post-mortem could only ask afterwards: which players are
individually admitted but never joined?

Week 2 of 2026 is the worked example. The Millionaire winner's roster shared 35
of its 36 pairs with the 12,555-candidate pool; the one it never contained was
Kittle + Schultz, two tight ends ranked 8th and 6th of 95 by our own projection.
The generator was not missing the players and not forbidding the shape — it built
1,735 two-TE lineups — but those held only 380 distinct TE pairs where 1,735 were
achievable, so pairs repeated 4.6x and an 8th-ranked TE never met a 6th-ranked
one. Winning lineups are made of players who overperform, which are not the
highest projected, so a generator allocating exploration by projection
systematically under-samples the combinations that win.

  python scripts/pool_pair_support.py --pool pool.csv --season 2026 --week 3 \\
      [--slate 153430] [--batch <generated_at>] [--top 20] [--out report.json]

Read-only. Needs a `names` column of pipe-separated player names.
"""

from __future__ import annotations

import argparse
import collections
import itertools
import json
import os
import pathlib
from datetime import UTC, datetime

PROJECT = os.environ.get("GCP_PROJECT", "nfl-predictions-503414")
POSITIONS = ("QB", "RB", "WR", "TE")


def player_info(season: int, week: int, slate: int | None, batch: str | None) -> dict:
    """position and projection per player, from the served batch."""
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT)
    where = [f"season = {season}", f"week = {week}"]
    if slate:
        where.append(f"slate_id = {slate}")
    if batch:
        where.append(f"generated_at = TIMESTAMP('{batch}')")
    q = (f"SELECT display_name, position, proj_points FROM "
         f"`{PROJECT}.nfl_predictions.player_projections` WHERE " + " AND ".join(where))
    out = {}
    for r in client.query(q).result():
        out[r.display_name] = (r.position, float(r.proj_points or 0.0))
    if not out:
        raise SystemExit(f"no projections for season {season} week {week}"
                         + (f" slate {slate}" if slate else ""))
    return out


def pair_support(rosters: list[list[str]], info: dict, position: str) -> dict:
    """Pair coverage for one position, with the repetition factor.

    `achievable` is the honest denominator: a pool of N lineups each holding two
    of a position can produce at most N distinct pairs, however many pairs exist
    in principle. Reporting only the theoretical denominator understates coverage
    whenever the shape is rare.
    """
    used = collections.Counter()
    pairs = collections.Counter()
    lineups_with_two = 0
    for roster in rosters:
        at_pos = sorted(p for p in roster if info.get(p, ("", 0))[0] == position)
        for p in at_pos:
            used[p] += 1
        if len(at_pos) >= 2:
            lineups_with_two += 1
            for a, b in itertools.combinations(at_pos, 2):
                pairs[(a, b)] += 1
    n = len(used)
    possible = n * (n - 1) // 2
    achievable = min(possible, lineups_with_two) or 0
    return {
        "position": position,
        "players_used": n,
        "lineups_with_two_or_more": lineups_with_two,
        "possible_pairs": possible,
        "achievable_pairs": achievable,
        "distinct_pairs": len(pairs),
        "share_of_possible": (len(pairs) / possible) if possible else None,
        "share_of_achievable": (len(pairs) / achievable) if achievable else None,
        "repetition_factor": (sum(pairs.values()) / len(pairs)) if pairs else None,
        "used": used,
        "pairs": pairs,
    }


def under_paired(stats: dict, info: dict, top: int) -> list[dict]:
    """Players well projected but rarely paired — the shape of the Week-2 miss."""
    used, pairs = stats["used"], stats["pairs"]
    partners = collections.Counter()
    for (a, b), n in pairs.items():
        partners[a] += 1
        partners[b] += 1
    ranked = sorted(used, key=lambda p: -info.get(p, ("", 0))[1])[:top]
    peers = max(1, len(used) - 1)
    out = []
    for i, p in enumerate(ranked, 1):
        # Share of possible partners, not the raw count. A raw count is
        # incomparable across positions: in Week 2 the top WRs paired with 90-127
        # peers and the top TEs with 19-52, purely because there are more WR
        # slots. As a share the gap is the real signal — WRs reached 66-93% of
        # their peers, TEs 20-55%, and Kittle, the pair the winner needed, 24%.
        out.append({"player": p, "projection_rank": i,
                    "projection": round(info.get(p, ("", 0))[1], 2),
                    "in_candidates": used[p],
                    "distinct_partners": partners.get(p, 0),
                    "partner_coverage": partners.get(p, 0) / peers})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pool", required=True)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--slate", type=int)
    ap.add_argument("--batch")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--min-coverage", type=float, default=0.50,
                    help="flag well-projected players meeting fewer than this "
                         "share of their positional peers (default 0.50)")
    ap.add_argument("--out", type=pathlib.Path)
    a = ap.parse_args(argv)

    import pandas as pd
    pool = pd.read_csv(a.pool)
    if "names" not in pool.columns:
        raise SystemExit(f"{a.pool} has no `names` column")
    rosters = [str(n).split("|") for n in pool.names]
    info = player_info(a.season, a.week, a.slate, a.batch)

    print(f"  pool: {len(rosters):,} candidates, {a.season} week {a.week}\n")
    print(f"  {'pos':<5}{'used':>6}{'lineups w/ 2+':>15}{'distinct pairs':>16}"
          f"{'of achievable':>15}{'repetition':>12}")
    report = {}
    for pos in POSITIONS:
        s = pair_support(rosters, info, pos)
        report[pos] = {k: v for k, v in s.items() if k not in ("used", "pairs")}
        if not s["distinct_pairs"]:
            print(f"  {pos:<5}{s['players_used']:>6}{s['lineups_with_two_or_more']:>15}"
                  f"{0:>16}{'—':>15}{'—':>12}")
            continue
        print(f"  {pos:<5}{s['players_used']:>6}{s['lineups_with_two_or_more']:>15}"
              f"{s['distinct_pairs']:>16,}{s['share_of_achievable']:>14.1%}"
              f"{s['repetition_factor']:>11.1f}x")
        report[pos]["under_paired"] = under_paired(s, info, a.top)

    print(f"\n  well-projected players that meet few of their peers "
          f"(partner coverage below {a.min_coverage:.0%}):")
    flagged = False
    for pos in POSITIONS:
        rows = report[pos].get("under_paired") or []
        thin = [r for r in rows if r["partner_coverage"] < a.min_coverage]
        if thin:
            flagged = True
            print(f"    {pos}:")
            for r in thin[:6]:
                print(f"      #{r['projection_rank']:<3} {r['player'][:22]:<23}"
                      f"proj {r['projection']:>6.2f}  in {r['in_candidates']:>6,} candidates"
                      f"  meets {r['partner_coverage']:>5.0%} of peers")
    if not flagged:
        print("    (none — every well-projected player meets a wide share of its peers)")
    if a.out:
        a.out.write_text(json.dumps(
            {"schema": "pool-pair-support/v1", "season": a.season, "week": a.week,
             "checked_utc": datetime.now(UTC).isoformat(),
             "candidates": len(rosters), "by_position": report}, indent=2, default=str) + "\n")
        print(f"\n  wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
