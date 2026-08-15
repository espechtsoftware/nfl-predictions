"""Nightly nflverse ingestion into nfl_raw.

Schedule: daily 06:00 CT in-season (nflverse updates overnight), weekly in the
offseason. Run once with --full to backfill FIRST_SEASON (default 2014) to
the latest completed-or-active season.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from hashlib import sha256

import pandas as pd

from ..bq import load_dataframe
from ..config import current_season, settings

log = logging.getLogger(__name__)

FTN_FIRST_SEASON = 2022
PFR_ADVSTATS_FIRST_SEASON = 2018
NGS_FIRST_SEASON = 2016
SNAPS_FIRST_SEASON = 2012
INJURIES_FIRST_SEASON = 2009
DEPTH_CHARTS_FIRST_SEASON = 2001
# nflverse replaced the weekly depth chart format in 2025: season/week rows
# with depth_team ranks became dated snapshots (dt) with pos_rank, and the
# two schemas share almost no columns. Land them as separate raw tables so
# feature SQL can normalize each on its own terms (003_player_week_role).
DEPTH_SNAPSHOTS_FIRST_SEASON = 2025
INJURY_SNAPSHOT_TABLE = "injury_snapshots"
INJURY_SOURCE_COLUMNS = (
    "season", "game_type", "team", "week", "gsis_id", "position",
    "full_name", "first_name", "last_name", "report_primary_injury",
    "report_secondary_injury", "report_status", "practice_primary_injury",
    "practice_secondary_injury", "practice_status", "date_modified",
    "season_type",
)


def _delete_seasons(table: str, seasons: list[int]) -> None:
    from google.api_core.exceptions import NotFound

    from ..bq import client

    sql = (f"DELETE FROM `{settings.raw}.{table}` "
           f"WHERE season IN ({','.join(str(s) for s in seasons)})")
    try:
        client().query(sql).result()
    except NotFound:  # first-ever run: nothing to delete
        pass


def _load(df, table: str, replace_seasons: list[int] | None = None) -> None:
    """Land a nflreadpy frame (polars) in nfl_raw.

    replace_seasons=None -> WRITE_TRUNCATE: correct for full-snapshot pulls
    (schedules, player_ids, ...) and for --full backfills.

    replace_seasons=[...] -> delete those seasons, then append. This is the
    incremental path. It MUST NOT truncate: the scheduled job loads only the
    current season, and on 2026-07-28 its truncate silently destroyed the
    2014-2024 backfill in every season-scoped table (deficiency log,
    2026-07-31). A frame without a `season` column falls back to truncate
    loudly, since delete-by-season is impossible."""
    pdf = df.to_pandas()
    if replace_seasons is not None:
        if "season" not in pdf.columns:
            log.warning("%s has no season column; falling back to full truncate", table)
        else:
            _delete_seasons(table, replace_seasons)
            load_dataframe(pdf, table, write_disposition="WRITE_APPEND")
            return
    load_dataframe(pdf, table)


def _json_value(value):
    """Canonical JSON scalar for one raw injury cell."""
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    return value


def prepare_injury_snapshot(
    frame,
    *,
    planning_season: int,
    pulled_at: datetime,
) -> pd.DataFrame:
    """Attach collector-time provenance to the current planning season.

    A pull made after an old week's lock cannot make that old row PIT-safe;
    downstream SQL enforces ``pulled_at <= slate_lock_at``.  Filtering here
    prevents an offseason/full refresh from pretending that final historical
    files were observed before their games.
    """
    stamp = pd.Timestamp(pulled_at)
    if stamp.tzinfo is None:
        raise ValueError("injury snapshot pulled_at must be timezone-aware")
    stamp = stamp.tz_convert("UTC")
    pdf = frame.to_pandas().copy()
    missing = set(INJURY_SOURCE_COLUMNS) - set(pdf.columns)
    if missing:
        raise ValueError(
            f"nflverse injuries missing snapshot columns {sorted(missing)}"
        )
    season = pd.to_numeric(pdf["season"], errors="coerce")
    pdf = pdf[season.eq(int(planning_season))].copy()
    if pdf.empty:
        return pd.DataFrame(columns=(
            "pulled_at", "capture_id", *INJURY_SOURCE_COLUMNS,
            "source_row_sha256",
        ))
    pdf = pdf.loc[:, list(INJURY_SOURCE_COLUMNS)]
    pdf["season"] = pd.to_numeric(pdf["season"], errors="raise").astype(
        "Int64"
    )
    pdf["week"] = pd.to_numeric(pdf["week"], errors="raise").astype("Int64")
    pdf["date_modified"] = pd.to_datetime(
        pdf["date_modified"], utc=True, errors="coerce"
    )
    capture_id = sha256(
        f"injury-snapshot-v1|{planning_season}|{stamp.isoformat()}".encode()
    ).hexdigest()
    row_hashes: list[str] = []
    for values in pdf.itertuples(index=False, name=None):
        payload = {
            key: _json_value(value)
            for key, value in zip(INJURY_SOURCE_COLUMNS, values, strict=True)
        }
        row_hashes.append(sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest())
    pdf.insert(0, "capture_id", capture_id)
    pdf.insert(0, "pulled_at", stamp)
    pdf["source_row_sha256"] = row_hashes
    return pdf


def append_injury_snapshot(
    frame,
    *,
    planning_season: int,
    pulled_at: datetime,
) -> int:
    """Append one live-season injury snapshot; return the stored row count."""
    payload = prepare_injury_snapshot(
        frame, planning_season=planning_season, pulled_at=pulled_at,
    )
    if payload.empty:
        log.info(
            "injury snapshot skipped: no rows for planning season %d",
            planning_season,
        )
        return 0
    load_dataframe(
        payload,
        INJURY_SNAPSHOT_TABLE,
        write_disposition="WRITE_APPEND",
        partition_field="pulled_at",
        clustering_fields=("season", "week", "gsis_id"),
    )
    log.info(
        "injury snapshot: %d rows for planning season %d capture %s",
        len(payload), planning_season, payload.capture_id.iloc[0][:12],
    )
    return int(len(payload))


def run(full_refresh: bool = False) -> None:
    import nflreadpy as nfl

    # config's season rolls over in March (we prepare for the coming season),
    # but nflverse has no data for it until games are played — clamp to the
    # latest season the loaders actually serve, or offseason runs crash.
    planning_season = current_season()
    season = min(planning_season, nfl.get_current_season())
    pulled_at = datetime.now(timezone.utc)
    seasons = list(range(settings.first_season, season + 1)) if full_refresh else [season]
    # Incremental runs replace just-loaded seasons in place; --full rebuilds
    # the whole table, where truncate is the correct disposition.
    inc = None if full_refresh else seasons

    _load(nfl.load_pbp(seasons), "pbp", replace_seasons=inc)
    _load(nfl.load_player_stats(seasons), "weekly_stats", replace_seasons=inc)
    legacy_dc = [s for s in seasons
                 if DEPTH_CHARTS_FIRST_SEASON <= s < DEPTH_SNAPSHOTS_FIRST_SEASON]
    if legacy_dc:
        _load(nfl.load_depth_charts(legacy_dc), "depth_charts",
              replace_seasons=None if full_refresh else legacy_dc)
    # Snapshot-format depth charts carry no season column, so they can't use
    # the delete+append path — always pull the full snapshot era (2025+,
    # small) so the truncate stays lossless.
    snap_dc = list(range(DEPTH_SNAPSHOTS_FIRST_SEASON, season + 1))
    if snap_dc:
        _load(nfl.load_depth_charts(snap_dc), "depth_charts_snapshots")
    _load(nfl.load_rosters_weekly(seasons), "rosters_weekly", replace_seasons=inc)
    _load(nfl.load_schedules(), "schedules")
    _load(nfl.load_officials(), "officials")  # full snapshot, 2015+; refs feature
    _load(nfl.load_ff_playerids(), "player_ids")
    _load(nfl.load_draft_picks(), "draft_picks")
    _load(nfl.load_combine(), "combine")

    if snaps := [s for s in seasons if s >= SNAPS_FIRST_SEASON]:
        _load(nfl.load_snap_counts(snaps), "snap_counts",
              replace_seasons=None if full_refresh else snaps)
    if inj := [s for s in seasons if s >= INJURIES_FIRST_SEASON]:
        injury_frame = nfl.load_injuries(inj)
        _load(injury_frame, "injuries",
              replace_seasons=None if full_refresh else inj)
        # Do not stamp the completed prior season during the offseason.  Only
        # a pull of the active planning season can become a future pre-lock
        # source; all historical final files remain timestamp-untrusted.
        if season == planning_season:
            append_injury_snapshot(
                injury_frame,
                planning_season=planning_season,
                pulled_at=pulled_at,
            )
    if ngs := [s for s in seasons if s >= NGS_FIRST_SEASON]:
        for stat_type in ("receiving", "rushing", "passing"):
            _load(nfl.load_nextgen_stats(ngs, stat_type=stat_type), f"ngs_{stat_type}",
                  replace_seasons=None if full_refresh else ngs)
    if ftn := [s for s in seasons if s >= FTN_FIRST_SEASON]:
        _load(nfl.load_ftn_charting(ftn), "ftn_charting",
              replace_seasons=None if full_refresh else ftn)
    # Per-defender coverage stats (targets, completions/yards allowed as the
    # nearest defender). PFR-keyed like snap_counts; teams already in
    # nflverse abbreviations. Feeds 017a_defense_week_coverage.
    if pfr := [s for s in seasons if s >= PFR_ADVSTATS_FIRST_SEASON]:
        _load(nfl.load_pfr_advstats(pfr, stat_type="def", summary_level="week"),
              "pfr_advstats_def", replace_seasons=None if full_refresh else pfr)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run(full_refresh="--full" in sys.argv)
