#!/usr/bin/env python3
"""Publish one week's pool exposure and arm results to the dashboard tables.

    # after the week's Sunday window (15:30 CT) or on Monday, on the laptop:
    python scripts/publish_dashboard_week.py --season 2026 --week 4 --snapshot
    # re-parse an existing snapshot at any time:
    python scripts/publish_dashboard_week.py --season 2026 --week 4 \\
        --inputs ~/.cache/laptop-agent/dashboard-snapshots/2026-w04/<utc>
    # write (only after reading the dry run):
    python scripts/publish_dashboard_week.py ... --apply

Dry run is the default: rows are printed, nothing is written. --apply
appends to `${project}.nfl_dashboard.pool_exposure` / `.arms_weekly` /
`.contest_lines` (create them first with sql/dashboard/ddl.sql); a re-publish
of the same run replaces that run's pool_exposure rows, and the readers of the
other two take the newest publication per week.

Arms "book" (the pre-R4 union book.csv) and "played" (the enter bundle that
<week dir>/ENTER resolves to at snapshot time, after R4/swap; the resolved
bundle name is in source_file) are published side by side, each labelled;
--exposure-book names which one pool_exposure describes. Cash lines come from
the snapshotted contest-details payout ladders and the imported standings.

Never parses the live week directories in place: --snapshot copies an
allow-listed set of files first (see nfl_dfs.dashboard.publisher), and the
live directories are not touched before the week's Sunday window closes.
Reads BigQuery (read-only) to score arms once the week is played; --no-bq
publishes counts only.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from nfl_dfs.dashboard import publisher as pub
from nfl_dfs.dashboard.guards import live_window_close, week_is_live


def _args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--inputs", type=Path, help="an existing snapshot directory to parse")
    src.add_argument("--snapshot", action="store_true",
                     help="copy the live inputs into a new snapshot first, then parse the copy")
    ap.add_argument("--run-id", help="lab live run id (default: the week's LATEST)")
    ap.add_argument("--tag", help="week-dir build tag (default: the run's newest vetted tag)")
    ap.add_argument("--lab-live", type=Path, default=pub.LAB_LIVE)
    ap.add_argument("--week-dir", type=Path, help="default ~/week<N>-sunday")
    ap.add_argument("--snapshot-root", type=Path, default=pub.SNAPSHOT_ROOT)
    ap.add_argument("--exposure-book", choices=("played", "book"), default="played",
                    help="which book pool_exposure.book_share describes; never substituted")
    ap.add_argument("--no-bq", action="store_true", help="skip scoring (counts only)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True, help="print rows (default)")
    mode.add_argument("--apply", action="store_true", help="write the rows to BigQuery")
    return ap.parse_args(argv)


def resolve_snapshot(a: argparse.Namespace, now: datetime) -> Path:
    if a.inputs:
        man = pub.read_manifest(a.inputs)
        if (man["season"], man["week"]) != (a.season, a.week):
            raise pub.PublishError(f"{a.inputs} is {man['season']} week {man['week']}, "
                                   f"not {a.season} week {a.week}")
        return a.inputs
    if week_is_live(a.season, a.week, now):
        raise pub.PublishError(
            f"{a.season} week {a.week} is live until "
            f"{live_window_close(a.season, a.week).isoformat()} (Sunday 15:30 CT): its directories "
            f"may be mid-build or mid-swap. Wait, or pass --inputs <existing snapshot>.")
    if not a.snapshot:
        raise pub.PublishError("reading the live directories requires --snapshot "
                               "(copy first, parse the copy) or --inputs <snapshot>")
    lab_week = a.lab_live / f"{a.season}-w{a.week:02d}"
    run = pub.find_run(lab_week, a.run_id)
    week_dir = a.week_dir or Path.home() / f"week{a.week}-sunday"
    tag = a.tag
    if not tag:
        tags = pub.tags_for_run(week_dir, run.name)
        if not tags:
            raise pub.PublishError(f"no vetted-<tag> directory in {week_dir} for run {run.name}; "
                                   f"pass --tag")
        tag = tags[-1]
        if len(tags) > 1:
            print(f"several tags for {run.name}: {tags}; using {tag} (pass --tag to choose)")
    snap = pub.make_snapshot(a.season, a.week, run, week_dir, tag, root=a.snapshot_root, now=now)
    print(f"snapshot: {snap}")
    return snap


def write(pool: pd.DataFrame, arms: pd.DataFrame, lines: pd.DataFrame, run_id: str,
          season: int, week: int) -> None:
    from google.cloud import bigquery

    from nfl_dfs.bq import client
    from nfl_dfs.dashboard.data import dashboard_dataset

    c = client()
    ds = dashboard_dataset()
    c.query(f"DELETE FROM `{ds}.pool_exposure` WHERE season = @s AND week = @w AND run_id = @r",
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("s", "INT64", season),
                bigquery.ScalarQueryParameter("w", "INT64", week),
                bigquery.ScalarQueryParameter("r", "STRING", run_id)])).result()
    for name, df in (("pool_exposure", pool), ("arms_weekly", arms), ("contest_lines", lines)):
        if df.empty:
            continue
        table = c.get_table(f"{ds}.{name}")
        cfg = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND", schema=table.schema)
        c.load_table_from_dataframe(df[[f.name for f in table.schema]], table, job_config=cfg).result()
        print(f"wrote {len(df)} rows to {ds}.{name}")


def main(argv=None) -> int:
    a = _args(argv)
    now = datetime.now(timezone.utc)
    if a.apply and a.no_bq:
        print("REFUSED: --apply with --no-bq would publish unscored rows; score first", file=sys.stderr)
        return 3
    try:
        snap = resolve_snapshot(a, now)
        parsed = pub.parse_snapshot(snap, exposure_book=a.exposure_book)
    except pub.PublishError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    for s in parsed.skipped:
        print(f"skipped: {s}")
    print(f"ENTER: {parsed.manifest.get('enter_status')} -> bundle {parsed.manifest.get('enter_bundle')}")
    print(f"run {parsed.manifest['run_id']} tag {parsed.manifest['tag']}: pool {len(parsed.pool)} "
          f"lineups, book {len(parsed.book)} ({parsed.book_source})")
    outcomes, points = pub.Outcomes(None, None, None), {}
    if not a.no_bq:
        from nfl_dfs.bq import query_df

        try:
            outcomes, points = pub.fetch_outcomes(query_df, a.season, a.week, parsed.frame, parsed.details)
        except pub.PublishError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 3
        print("scored" if outcomes.player_points is not None else "not scored yet (no points)")
    if not parsed.details:
        print("no contest-details in the snapshot: cash lines and cash rates stay NULL")
    pool = pub.pool_exposure_rows(parsed, now)
    arms = pub.arms_rows(parsed, outcomes, now)
    lines = pub.contest_lines_rows(parsed, points, now)
    pd.set_option("display.width", 200)
    print(f"\npool_exposure: {len(pool)} rows (top 25)")
    print(pool.head(25).to_string(index=False))
    print(f"\narms_weekly: {len(arms)} rows")
    print(arms.drop(columns=["source_sha256", "published_utc", "source_file"]).to_string(index=False))
    print(f"\ncontest_lines: {len(lines)} rows")
    if len(lines):
        print(lines[["contest_id", "field_size", "paid_places", "cash_line"]].to_string(index=False))
    if a.apply:
        write(pool, arms, lines, parsed.manifest["run_id"], a.season, a.week)
    else:
        print("\ndry run: nothing written (pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
