"""Daily snapshots of the irreplaceable tables (safety net beyond
BigQuery's 7-day time travel).

Everything nflverse/odds/DK-API-shaped can be re-ingested from source;
these tables cannot: hand-imported contest standings and the LineStar
ownership backfill (the API stopped serving projections historically and
DK deletes standings after 30 days), licensed Fantasy Points imports whose
subscription/download access may lapse, user-authored notes/watchlist, the
entered-lineups journal, and hand-curated ID overrides.

CREATE SNAPSHOT TABLE bills only for storage DELTA vs the base table, so
30 daily snapshots of small tables cost effectively nothing. Snapshots
land in the `nfl_backups` dataset as <table>_YYYYMMDD with a 30-day
expiry — restore is `CREATE TABLE ds.t CLONE nfl_backups.t_YYYYMMDD`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..config import settings

log = logging.getLogger(__name__)

BACKUP_DATASET = "nfl_backups"
RETENTION_DAYS = 30

# (dataset_attr, table) — dataset resolved from settings so this follows
# env config. Append here when a new irreplaceable table appears (same
# discipline as status.FEEDS).
TABLES: list[tuple[str, str]] = [
    ("raw", "contest_ownership"),
    ("raw", "contest_entries"),  # per-entry lineups; source purges in ~4 days
    ("raw", "dk_salaries_historical"),
    ("raw", "showdown_salaries_historical"),
    ("raw", "dk_contest_fills"),  # dk_contest_fills_nfl is a VIEW — skip
    ("raw", "fantasy_points_route_share"),
    ("raw", "fantasy_points_advanced_prior"),
    ("raw", "fantasy_points_receiver_coverage_l4"),
    ("raw", "fantasy_points_defense_coverage_l4"),
    ("raw", "fantasy_points_advanced_passing_l4"),
    ("features", "manual_notes"),
    ("features", "player_watch_notes"),
    ("features", "lineup_prefs"),
    ("features", "season_results"),
    ("features", "entered_lineups"),
    ("features", "player_id_overrides"),
    ("features", "external_projections"),  # user-uploaded; source CSVs expire
]

# Licensed Fantasy Points importers use this namespace. Discovering base
# tables in addition to the explicit current list makes future adopted data
# durable on its first daily backup without relying on a second manual edit.
# Views/external tables are excluded because CREATE SNAPSHOT supports base
# tables only.
DISCOVER_PREFIXES: tuple[tuple[str, str], ...] = (
    ("raw", "fantasy_points_"),
)


def _tables_to_backup(c: object) -> list[tuple[str, str]]:
    tables = set(TABLES)
    for attr, prefix in DISCOVER_PREFIXES:
        dataset = getattr(settings, attr)
        for item in c.list_tables(dataset):
            if (item.table_id.startswith(prefix)
                    and getattr(item, "table_type", "TABLE") == "TABLE"):
                tables.add((attr, item.table_id))
    return sorted(tables)


def run() -> None:
    from google.api_core.exceptions import NotFound

    from ..bq import client

    c = client()
    project = settings.raw.split(".")[0]
    ds = f"{project}.{BACKUP_DATASET}"
    try:
        c.get_dataset(ds)
    except NotFound:
        c.create_dataset(ds)
        log.info("created backup dataset %s", ds)

    tables = _tables_to_backup(c)

    import os

    # NOTE: never reuse a snapshot name deleted <7 days ago — BigQuery
    # treats same-name recreation inside the time-travel window as a
    # replace and demands deleteSnapshot, which the job SA lacks by
    # design. Daily date stamps make this a non-issue in production;
    # BACKUP_SUFFIX exists so a fresh-name run can be tested on demand.
    stamp = (datetime.now(timezone.utc).strftime("%Y%m%d")
             + os.environ.get("BACKUP_SUFFIX", ""))
    ok = missing = 0
    for attr, table in tables:
        src = f"{getattr(settings, attr)}.{table}"
        dst = f"{ds}.{table}_{stamp}"
        try:
            # Explicit existence check instead of IF NOT EXISTS: on an
            # existing snapshot the DDL path demands deleteSnapshot,
            # which the job's service account deliberately lacks
            # (dataEditor has createSnapshot only — backups are
            # append-only from the job's point of view).
            try:
                c.get_table(dst)
                log.info("backup: %s already exists, kept", dst)
                ok += 1
                continue
            except NotFound:
                pass
            # Retention comes from the DATASET default expiration (30d),
            # not an OPTIONS clause: an explicit expiration_timestamp on
            # CREATE SNAPSHOT demands bigquery.tables.deleteSnapshot
            # (the expiry is a scheduled delete), which the job SA
            # deliberately lacks. Inherited default dodges the check.
            c.query(f"CREATE SNAPSHOT TABLE `{dst}` CLONE `{src}`").result()
            ok += 1
        except NotFound:
            # Tables like dk_contest_fills only exist once the season
            # starts; a missing base table is expected, not an error.
            log.info("backup: %s absent, skipped", src)
            missing += 1
        except Exception:
            log.exception("backup FAILED for %s", src)
    print(f"backup {stamp}: {ok} snapshotted, {missing} absent, "
          f"{len(tables) - ok - missing} failed")
    if ok + missing < len(tables):
        raise SystemExit(1)  # surface failure to the job-alert pipeline
