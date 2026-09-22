#!/usr/bin/env python3
"""Is the MarketMatchError question testable yet, and what is the feed state?

    PYTHONPATH=<worktree>/src <venv>/python \
        reports/lab-handoffs/prop_match_preflight.py --season 2026 --week 3

WHAT THIS ANSWERS, and only this. Every guard in `resolve_live_market` is gated
on `feed_present`, so with no prop feed for the week the MarketMatchError cannot
fire and the question cannot be tested -- regardless of the roster guard in front
of it. This reports the feed state directly, using the same prop_market functions
the money path calls, and so can be run days before project-slate is reachable.

WHAT IT DELIBERATELY DOES NOT DO: name the at-risk players. The real run maps DK
players to gsis through `rosters_weekly` for the target week. An earlier version
of this script substituted a normalised-name lookup through nfl_raw.player_ids;
validated against 2026 week 2 -- where the real run reported 19 unmatched names --
it produced far more, because the crosswalk misses players the roster join
resolves. The count was wrong, so the list is not reported. Reproducing the names
requires the roster mapping and therefore waits for rosters, exactly as
production said.
"""
import argparse

from nfl_dfs.models.prop_market import market_points, prop_feed_player_names

ap = argparse.ArgumentParser()
ap.add_argument("--season", type=int, required=True)
ap.add_argument("--week", type=int, required=True)
ap.add_argument("--minimum-markets", type=int, default=2)
a = ap.parse_args()

feed = prop_feed_player_names(a.season, a.week)
print(f"prop feed names for {a.season} W{a.week}: {len(feed)}")

if not feed:
    print("VERDICT: not testable yet -- no prop feed for this week.")
    print("  * MarketMatchError CANNOT fire: resolve_live_market's unmatched and")
    print("    coverage guards are both gated on feed_present.")
    print("  * A project-slate run now would SUCCEED and write a 100%-model batch:")
    print("    blend() falls back to the model wherever market is NaN.")
    print("  * check_market_monitor.py would then FAIL that batch on props-share")
    print("    (0% < 30%), so the money path is gated -- but the batch is written.")
    raise SystemExit(0)

pm = market_points((a.season,), minimum_markets=a.minimum_markets)
pm = pm[pm.week == a.week]
print(f"priced gsis (>= {a.minimum_markets} markets): {pm.gsis_id.nunique()}")
print("VERDICT: feed present -- the question is now testable, and the definitive")
print("  answer comes from project-slate itself once the roster guard clears.")
