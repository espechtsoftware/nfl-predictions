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

--with-facts (study list item 44; the operator and the outside reviewer, 10-06: "all the data points that could help it
look like a winner … red zone … touchdowns … attempts"; reports/2026-10-06-neo4j-winner-likeness-inputs.md): ALSO load
the player, team, game and lineup facts of nfl_dfs.dashboard.milly_graph_facts -- pre_* (known before lock: each week's
archived T-70 frame, plus lagged touchdowns / attempts over PRIOR games, with provenance) and out_* (that week's results).
--facts-frames names a PRIVATE JSON {week: T-70 run dir} (default: the money gate's ~/moneygate/weeks.json t70_run). A
week without a frame loads no facts (said loudly). Fantasy Points columns of the frame only with --include-fp.
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from nfl_dfs.dashboard import data
from nfl_dfs.dashboard import milly_graph as mg
from nfl_dfs.dashboard import milly_graph_facts as mgf


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
    ap.add_argument("--with-facts", action="store_true",
                    help="also load pre_ / out_ player, team, game and lineup facts (study list item 44)")
    ap.add_argument("--facts-only", action="store_true",
                    help="with --with-facts and --apply: write ONLY the fact batches (the base graph of the same "
                         "selection must already be loaded; its lineups are rebuilt in memory for the labels)")
    ap.add_argument("--facts-frames", default=None,
                    help="a PRIVATE JSON {week: T-70 run dir} for --with-facts (default: ~/moneygate/weeks.json t70_run)")
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
    facts = build_facts(a, query_df, batches, weeks, games) if a.with_facts else None
    if facts is not None:
        for name, rows in facts.items():
            print(f"{name:14s} {len(rows):7d} rows (facts)")
    if not a.apply:
        print("dry run: nothing written (pass --apply)")
        return 0
    cfg = mg.GraphConfig.from_env()
    if cfg is None:
        print(f"REFUSED: set {mg.URI_ENV}, {mg.USERNAME_ENV}, {mg.PASSWORD_ENV} "
              f"(and optionally {mg.DATABASE_ENV})", file=sys.stderr)
        return 3
    if a.facts_only and facts is None:
        ap.error("--facts-only needs --with-facts")
    if not a.facts_only:
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
    if facts is not None:
        driver = mg.connect(cfg)
        try:
            n0, r0 = mg.count_graph(driver, cfg.database)
            dn = len(facts["player_weeks"]) + len(facts["team_weeks"])
            dr = 2 * dn
            mg.check_capacity((n0, r0), (dn, dr), a.node_limit, a.rel_limit)
            print(f"facts loaded: {mgf.apply_fact_batches(driver, cfg.database, facts)}")
        except mg.CapacityError as exc:
            print(f"REFUSED (facts): {exc}", file=sys.stderr)
            return 4
        finally:
            driver.close()
    return 0


def build_facts(a, query_df, batches, weeks, games) -> dict:
    """The fact batches for each loaded week with an archived T-70 frame (milly_graph_facts)."""
    import hashlib
    import json
    from pathlib import Path

    from nfl_dfs.config import settings
    src = Path(a.facts_frames) if a.facts_frames else Path.home() / "moneygate" / "weeks.json"
    cfg = json.loads(src.read_text())
    runs = {str(k): (v["t70_run"] if isinstance(v, dict) else v) for k, v in (cfg.get("weeks", cfg)).items()}
    out = {k: [] for k in mgf.STATEMENTS}
    n_entries = {d["contest_id"]: d.get("n_entries") for d in batches.get("contests", [])}
    win_pts = {d["contest_id"]: d.get("winning_score") for d in batches.get("contests", [])}
    for w in weeks:
        run = runs.get(str(w))
        if not run or not (Path(run) / "frame.parquet").is_file():
            print(f"FACTS: week {w} has no archived T-70 frame in {src}; no facts loaded for it")
            continue
        fpath = Path(run) / "frame.parquet"
        frame = pd.read_parquet(fpath)
        rec = Path(run) / "receipt.json"
        as_of = str(json.loads(rec.read_text()).get("built_utc")) if rec.is_file() else "unknown"
        source = f"{Path(run).name} frame sha256 {hashlib.sha256(fpath.read_bytes()).hexdigest()[:16]}"
        wk = mg.week_key(a.season, w)
        prm = {"season": a.season, "week": int(w)}
        lag = query_df(mgf.LAG_SQL.format(features=settings.features), prm)
        outs = query_df(mgf.OUT_SQL.format(features=settings.features, cols=", ".join(mgf.OUT_ACTUAL_COLUMNS)), prm)
        pbp = query_df(mgf.PBP_SQL.format(raw=settings.raw), prm)
        td = mgf.td_probabilities(query_df(mgf.TD_SQL.format(raw=settings.raw), prm))
        pt_file = Path(__file__).resolve().parents[1] / "reports" / "2026-10-07-prior-top-term" / f"priortop-w{int(w)}.csv"
        prior_top, pt_src = None, None
        if pt_file.is_file():                                   # the prior REAL weeks' top-1% shares (weeks < w)
            prior_top = pd.read_csv(pt_file)
            pt_src = f"{pt_file.name} sha256 {hashlib.sha256(pt_file.read_bytes()).hexdigest()[:16]}"
        starters = None
        if as_of not in ("unknown", "None", ""):
            starters = query_df(mgf.DEPTH_SQL.format(raw=settings.raw), {"as_of": pd.Timestamp(as_of).tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S")
                                if pd.Timestamp(as_of).tzinfo else pd.Timestamp(as_of).strftime("%Y-%m-%d %H:%M:%S")})
        pw = mgf.player_week_rows(frame, wk, source, as_of, lag, outs, pbp, include_vendor=a.include_fp,
                                  td=td, prior_top=prior_top, prior_top_source=pt_src)
        if not a.include_fp:
            vendor = {f"pre_{c}" for c in mgf.VENDOR_PRE_COLUMNS}       # the explicit licensed columns ("fp_allowed" is ours)
            bad = sorted({k for r in pw for k in r["props"] if k in vendor})
            if bad:
                raise SystemExit(f"FACTS REFUSED: vendor fields {bad[:5]} without --include-fp")
        out["player_weeks"] += pw
        out["team_weeks"] += mgf.team_week_rows(frame, wk, source, as_of, starters=starters)
        out["game_facts"] += mgf.game_fact_rows(frame, games[games.week == int(w)], source, as_of)
        lw = [d for d in batches.get("lineups", []) if d.get("week_key") == wk]
        keys = {d["key"] for d in lw}
        cw = [c for c in batches.get("contains", []) if c["lineup_key"] in keys]
        cids = {d["contest_id"] for d in lw}
        own = {(str(o["contest_id"]), int(o["dk_player_id"])): float(o["own"]) for o in batches.get("owned_in", [])
               if o["contest_id"] in cids and o.get("own") is not None}      # REALIZED: goes to out_ only
        out["lineup_labels"] += mgf.lineup_label_rows(lw, cw, frame, own, n_entries, win_pts)
        print(f"FACTS week {w}: {len(pw)} player-weeks from {source} (as of {as_of}); TD prices {len(td)}; "
              f"prior-top {'none' if prior_top is None else len(prior_top)}; starters {0 if starters is None else len(starters)}")
    return out


if __name__ == "__main__":
    sys.exit(main())
