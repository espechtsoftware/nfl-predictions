#!/usr/bin/env python3
"""Load the season's Millionaire lineups into the Milly Neo4j graph.

    python scripts/load_milly_neo4j.py --season 2026            # dry run: counts only
    python scripts/load_milly_neo4j.py --season 2026 --week 4 --apply

Reads BigQuery (read-only): the resolved Millionaire per week, its lines,
the top --top-n lineups (plus up to --cash-rows entries on the cash line
when payouts are known), the draft group's salaries and the schedule.
Writes only with --apply, and only to the graph named by MILLY_NEO4J_URI /
MILLY_NEO4J_USERNAME / MILLY_NEO4J_PASSWORD / MILLY_NEO4J_DATABASE -- a local
Neo4j instance (operator 2026-10-04: the graph is local only, not part of the
dashboard UI). DraftKings user names are loaded as (:User)-[:ENTERED]->(:Lineup).
Every write is a MERGE, so reloading a week is idempotent. Before writing it
counts the graph and refuses if this load could take it past 90% of the sizing
limits (milly_graph.FREE_TIER_NODES / FREE_TIER_RELS, the Aura Free numbers;
raise them with --node-limit / --rel-limit on a local instance); it prints the
counts after the load. Fantasy Points projection/ownership is loaded only with
--include-fp (opt-in).

--users-file (operator 2026-10-06: "look closely at how the winners do it"): ALSO load EVERY Millionaire lineup of
the users listed in a PRIVATE file (one DraftKings name per line; chosen by entry count, never by results), so a
user's whole portfolio -- core players, pivots, stacks -- can be explored, not only their top finishes. Those lineups
are tagged source='users_file' (the top-N set keeps 'top'); STACKED_WITH, the share of the field and Lineup.top_1pct
come from the top set only, so the panel's figures do not change (rank_top_1pct is the plain fact for every lineup).
Use the 117-regular cohort plus any user he names, not every user. The file stays outside the repository.
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from nfl_dfs.dashboard import data
from nfl_dfs.dashboard import milly_graph as mg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, action="append", help="repeatable; default every week")
    ap.add_argument("--top-n", type=int, default=1000,
                    help=f"top lineups per contest-week (at most {mg.MAX_TOP_N})")
    ap.add_argument("--node-limit", type=int, default=mg.FREE_TIER_NODES)
    ap.add_argument("--rel-limit", type=int, default=mg.FREE_TIER_RELS)
    ap.add_argument("--cash-rows", type=int, default=50)
    ap.add_argument("--include-fp", action="store_true",
                    help="also load Fantasy Points pre-lock projection/ownership per player-week "
                         "(licensed data; local graph only; opt-in)")
    ap.add_argument("--users-file", help="a PRIVATE file of DraftKings user names (one per line): also load ALL their "
                    "Millionaire lineups (chosen by entry count, never results); never a tracked file")
    ap.add_argument("--apply", action="store_true", help="write to Neo4j (default: dry run)")
    a = ap.parse_args(argv)
    if not 1 <= a.top_n <= mg.MAX_TOP_N:
        ap.error(f"--top-n must be between 1 and {mg.MAX_TOP_N} (graph sizing)")

    from nfl_dfs.bq import query_df

    contests = data.fetch_milly_contests(query_df, a.season)
    if a.week:
        contests = contests[contests.week.isin(a.week)]
    if contests.empty:
        print("no Millionaire contests resolved for that selection")
        return 1
    lines = data.fetch_milly_lines(query_df, a.season)
    games = data.fetch_schedule(query_df, a.season)
    weeks = sorted(int(w) for w in contests.week)
    tops, slates, owns = [], [], []
    for w in weeks:
        tops.append(data.fetch_milly_top(query_df, a.season, w, top_n=a.top_n, top_share=1.0,
                                         cash_rows=a.cash_rows))
        slates.append(data.fetch_milly_slate(query_df, a.season, w))
        owns.append(data.fetch_field_ownership(query_df, a.season, w))
    top = pd.concat(tops, ignore_index=True)
    if a.users_file:
        from pathlib import Path
        users = [u.strip() for u in Path(a.users_file).read_text().splitlines() if u.strip() and not u.startswith("#")]
        ul = pd.concat([data.fetch_milly_user_lineups(query_df, a.season, w, users) for w in weeks], ignore_index=True)
        n_top = len(top)
        # the top set keeps source 'top' (first wins in the dedupe); the rest are 'users_file' and never change the
        # panel's figures (milly_graph.build_graph_batches)
        top = pd.concat([top.assign(source="top"), ul.assign(source="users_file")], ignore_index=True).drop_duplicates("lineup_key")
        print(f"users file: {len(users)} users, {len(ul):,} of their lineups ({len(top) - n_top:,} new beyond the top-N set)")
    slate = pd.concat(slates, ignore_index=True)
    own = pd.concat(owns, ignore_index=True)
    batches = mg.build_graph_batches(contests, lines, top, slate, games, own)
    for _, c in contests.iterrows():
        if pd.notna(c.get("lobby_contest_id")) and str(c.lobby_contest_id) != str(c.contest_id):
            print(f"MISMATCH week {c.week}: lobby Millionaire {c.lobby_contest_id}, standings "
                  f"{c.contest_id}; loading the standings")
    top_set = top[top.source == "top"] if "source" in top else top    # the share line counts the top-N set only
    for cid, (n, share) in sorted(mg.loaded_share(top_set).items()):
        wk_ = contests[contests.contest_id.astype(str) == cid].week
        label = f"{share:.2%} of the field" if share is not None else "share unknown"
        print(f"week {int(wk_.iloc[0]) if len(wk_) else '?'} contest {cid}: top {n:,} lineups loaded = {label}")
    rep = mg.resolution_report(top, slate)
    coll = rep["collisions"]
    print(f"name resolution: {rep['slots'] - rep['unresolved_slots']}/{rep['slots']} lineup slots resolved "
          f"to a DraftKings id; {rep['unresolved_slots']} not loaded")
    if len(coll):
        print(f"COLLISIONS (never merged; {coll.k.nunique()} name(s), {len(coll)} slate rows):")
        print(coll.to_string(index=False))
    if rep["unresolved_names"]:
        print(f"unresolved names: {rep['unresolved_names'][:30]}")
    fp_rows = None
    if a.include_fp:
        fp_proj = query_df(data.render("fp_projections_season", season=a.season))
        fp_own = query_df(data.render("fp_ownership_season", season=a.season))
        fp_rows = mg.fp_batch(batches["players"], fp_proj, fp_own, a.season)
        print(f"{'fp_projected':14s} {len(fp_rows):7d} rows (opt-in)")
    for name, rows in batches.items():
        print(f"{name:14s} {len(rows):7d} rows")
    if not a.apply:
        print("dry run: nothing written (pass --apply)")
        return 0
    cfg = mg.GraphConfig.from_env()
    if cfg is None:
        print(f"REFUSED: set {mg.URI_ENV}, {mg.USERNAME_ENV}, {mg.PASSWORD_ENV} "
              f"(and optionally {mg.DATABASE_ENV})", file=sys.stderr)
        return 3
    driver = mg.connect(cfg)
    try:
        res = mg.guarded_load(driver, cfg.database, batches, fp_rows=fp_rows,
                              node_limit=a.node_limit, rel_limit=a.rel_limit)
    except mg.CapacityError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 4
    finally:
        driver.close()
    print(f"loaded: {res['sent']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
