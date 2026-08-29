"""Nightly nflverse ingestion into nfl_raw.

Schedule: daily 06:00 CT in-season (nflverse updates overnight), weekly in the
offseason. Run once with --full to backfill FIRST_SEASON (default 2014) to
the latest completed-or-active season.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import datetime, timezone
from hashlib import sha256
from numbers import Integral, Real

import numpy as np
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
WEEKLY_ROSTER_REQUIRED_COLUMNS = frozenset({
    "season", "week", "gsis_id", "team", "position", "full_name",
    "football_name", "last_name", "jersey_number", "game_type",
})
DEPTH_SNAPSHOT_REQUIRED_COLUMNS = frozenset({
    "dt", "team", "gsis_id", "player_name", "pos_abb", "pos_rank",
})
NFL_TEAM_COUNT = 32
MIN_WEEKLY_ROSTER_GSIS_IDS = 1_000
MIN_DEPTH_SNAPSHOT_GSIS_IDS = 1_000
MAX_DEPTH_SNAPSHOT_AGE_DAYS = 14
WEEKLY_ROSTER_STRING_COLUMNS = frozenset({
    "team", "position", "depth_chart_position", "jersey_number", "status",
    "full_name", "first_name", "last_name", "college", "gsis_id",
    "espn_id", "sportradar_id", "yahoo_id", "rotowire_id", "pff_id",
    "pfr_id", "fantasy_data_id", "sleeper_id", "headshot_url",
    "ngs_position", "game_type", "status_description_abbr",
    "football_name", "esb_id", "gsis_it_id", "smart_id", "draft_club",
    "draft_number", "nflverse_source_path", "nflverse_source_mode",
})


def _delete_seasons(table: str, seasons: list[int]) -> None:
    from google.api_core.exceptions import NotFound

    from ..bq import client

    sql = (f"DELETE FROM `{settings.raw}.{table}` "
           f"WHERE season IN ({','.join(str(s) for s in seasons)})")
    try:
        client().query(sql).result()
    except NotFound:  # first-ever run: nothing to delete
        pass


def _normalize_destination_frame(
    pdf: pd.DataFrame,
    table: str,
) -> pd.DataFrame:
    """Normalize source dtypes that have a stricter landed-table contract.

    nflverse may infer nullable identifier-like fields as floats when a source
    release contains only numeric/null values.  The established BigQuery
    roster table intentionally stores those and all categorical/text fields
    as STRING. Normalize the complete destination string contract before the
    incremental path deletes the seasons being replaced. Numeric values must
    be finite and integral; silently truncating an identifier or draft number
    would weaken the source contract.
    """
    if table != "rosters_weekly":
        return pdf

    out = pdf.copy()
    for column in sorted(WEEKLY_ROSTER_STRING_COLUMNS & set(out.columns)):
        normalized: list[object] = []
        for value in out[column]:
            if pd.isna(value):
                normalized.append(pd.NA)
            elif isinstance(value, (bool, np.bool_)):
                raise ValueError(f"rosters_weekly {column} is boolean")
            elif isinstance(value, Integral):
                normalized.append(str(int(value)))
            elif isinstance(value, Real):
                numeric = float(value)
                if not math.isfinite(numeric) or not numeric.is_integer():
                    raise ValueError(
                        f"rosters_weekly {column} is not an integer"
                    )
                normalized.append(str(int(numeric)))
            else:
                normalized.append(str(value).strip())
        out[column] = pd.array(normalized, dtype="string")
    return out


def _weekly_roster_downloader():
    """Return nflreadpy's downloader through one monkeypatchable seam."""
    from nflreadpy.downloader import get_downloader

    return get_downloader()


def _prospective_source_seasons(
    base_seasons: list[int],
    *,
    planning_season: int,
    roster_year: int,
) -> tuple[list[int], list[int]]:
    """Resolve complete weekly-roster and snapshot-depth refresh years."""
    roster_seasons = list(dict.fromkeys(int(value) for value in base_seasons))
    if roster_year == planning_season and roster_year not in roster_seasons:
        roster_seasons.append(int(roster_year))
    snapshot_end = (
        int(roster_year)
        if int(roster_year) == int(planning_season)
        else max(roster_seasons)
    )
    snapshot_seasons = list(range(
        DEPTH_SNAPSHOTS_FIRST_SEASON, snapshot_end + 1,
    ))
    return roster_seasons, snapshot_seasons


def _weekly_roster_frame(
    nfl,
    *,
    season: int,
    pulled_at: datetime,
) -> pd.DataFrame:
    """Load one exact roster season, including the supported preseason year.

    nflreadpy 0.1.5 deliberately treats the NFL season as starting on the
    Thursday after Labor Day, but nflverse publishes the new roster-year
    weekly file months earlier.  During that bounded preseason interval the
    public ``load_rosters_weekly`` validator rejects the already-published
    planning-year path.  Bypass only that stale date guard while retaining
    nflreadpy's own downloader, repository, path, cache and parquet parser.

    The bypass is legal only for the exact current roster year returned by
    nflreadpy's separate ``roster=True`` calendar.  Content is then checked
    for a nonempty, single exact season and minimally complete GSIS roster
    league coverage before it can reach the raw table.
    """
    stamp = pd.Timestamp(pulled_at)
    if stamp.tzinfo is None:
        raise ValueError("weekly roster pulled_at must be timezone-aware")
    stamp = stamp.tz_convert("UTC")
    data_season = int(nfl.get_current_season())
    roster_season = int(nfl.get_current_season(roster=True))
    source_path = f"weekly_rosters/roster_weekly_{int(season)}"
    if int(season) <= data_season:
        frame = nfl.load_rosters_weekly([int(season)])
        source_mode = "nflreadpy-public-weekly-roster"
    elif int(season) == roster_season == data_season + 1:
        frame = _weekly_roster_downloader().download(
            "nflverse-data", source_path, season=int(season),
        )
        source_mode = "nflreadpy-preseason-weekly-roster-path"
    else:
        raise ValueError(
            f"weekly roster season {season} is outside nflreadpy data/roster "
            f"years {data_season}/{roster_season}"
        )

    pdf = frame.copy() if isinstance(frame, pd.DataFrame) else frame.to_pandas()
    missing = WEEKLY_ROSTER_REQUIRED_COLUMNS - set(pdf.columns)
    if missing:
        raise ValueError(
            f"weekly roster {season} missing columns {sorted(missing)}"
        )
    observed_seasons = set(
        pd.to_numeric(pdf["season"], errors="raise").astype(int).unique()
    )
    if pdf.empty or observed_seasons != {int(season)}:
        raise ValueError(
            f"weekly roster {season} has seasons {sorted(observed_seasons)}"
        )
    distinct_gsis = int(pdf["gsis_id"].dropna().nunique())
    distinct_teams = int(pdf["team"].dropna().nunique())
    observed_weeks = set(
        pd.to_numeric(pdf["week"], errors="raise").dropna().astype(int)
    )
    if distinct_gsis < MIN_WEEKLY_ROSTER_GSIS_IDS:
        raise ValueError(
            f"weekly roster {season} has only {distinct_gsis} distinct "
            "GSIS identities"
        )
    if distinct_teams != NFL_TEAM_COUNT:
        raise ValueError(
            f"weekly roster {season} has {distinct_teams} teams, "
            f"expected {NFL_TEAM_COUNT}"
        )
    if not observed_weeks or 1 not in observed_weeks:
        raise ValueError(
            f"weekly roster {season} has weeks {sorted(observed_weeks)}; "
            "week 1 is required"
        )

    out = pdf.copy()
    out["nflverse_source_path"] = source_path
    out["nflverse_source_mode"] = source_mode
    out["nflverse_pulled_at"] = stamp
    return out


def _depth_snapshot_frame(
    nfl,
    *,
    seasons: list[int],
    pulled_at: datetime,
) -> pd.DataFrame:
    """Load and validate the current snapshot-era depth-chart artifact.

    The raw snapshot table is replaced as one unit because it has no season
    column.  Validate realistic league and identity coverage, and require a
    recent latest snapshot for every team, before that replacement can occur.
    Capture time is landed with every row so the feature build can reject a
    stale table rather than silently treating it as current.
    """
    stamp = pd.Timestamp(pulled_at)
    if stamp.tzinfo is None:
        raise ValueError("depth snapshot pulled_at must be timezone-aware")
    stamp = stamp.tz_convert("UTC")
    frame = nfl.load_depth_charts([int(value) for value in seasons])
    pdf = frame.copy() if isinstance(frame, pd.DataFrame) else frame.to_pandas()
    missing = DEPTH_SNAPSHOT_REQUIRED_COLUMNS - set(pdf.columns)
    if missing:
        raise ValueError(
            f"depth snapshots missing columns {sorted(missing)}"
        )
    if pdf.empty:
        raise ValueError("depth snapshots are empty")

    parsed_dt = pd.to_datetime(pdf["dt"], utc=True, errors="coerce")
    valid = pdf.loc[
        pdf["team"].notna() & pdf["gsis_id"].notna() & parsed_dt.notna()
    ].copy()
    valid["_parsed_dt"] = parsed_dt.loc[valid.index]
    latest_by_team = valid.groupby("team", observed=True)["_parsed_dt"].max()
    if len(latest_by_team) != NFL_TEAM_COUNT:
        raise ValueError(
            f"depth snapshots have {len(latest_by_team)} teams, "
            f"expected {NFL_TEAM_COUNT}"
        )
    oldest_latest = latest_by_team.min()
    newest_latest = latest_by_team.max()
    if oldest_latest < stamp - pd.Timedelta(days=MAX_DEPTH_SNAPSHOT_AGE_DAYS):
        raise ValueError(
            "depth snapshots are stale for at least one team: oldest latest "
            f"snapshot is {oldest_latest.isoformat()}"
        )
    if newest_latest > stamp + pd.Timedelta(days=1):
        raise ValueError(
            f"depth snapshots contain a future timestamp {newest_latest.isoformat()}"
        )
    recent = valid.loc[
        valid["_parsed_dt"] >=
        stamp - pd.Timedelta(days=MAX_DEPTH_SNAPSHOT_AGE_DAYS)
    ]
    distinct_gsis = int(recent["gsis_id"].nunique())
    if distinct_gsis < MIN_DEPTH_SNAPSHOT_GSIS_IDS:
        raise ValueError(
            f"recent depth snapshots have only {distinct_gsis} distinct "
            "GSIS identities"
        )

    out = pdf.copy()
    out["nflverse_source_seasons"] = ",".join(str(value) for value in seasons)
    out["nflverse_source_mode"] = "nflreadpy-public-depth-snapshots"
    out["nflverse_pulled_at"] = stamp
    return out


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
    source = df.copy() if isinstance(df, pd.DataFrame) else df.to_pandas()
    pdf = _normalize_destination_frame(source, table)
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
    roster_year = int(nfl.get_current_season(roster=True))
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
    roster_seasons, snap_dc = _prospective_source_seasons(
        seasons,
        planning_season=planning_season,
        roster_year=roster_year,
    )
    if snap_dc:
        _load(
            _depth_snapshot_frame(
                nfl, seasons=snap_dc, pulled_at=pulled_at,
            ),
            "depth_charts_snapshots",
        )
    # Before opening week the ordinary season clock still points at the
    # completed season. Restore that raw partition and also land the exact
    # current roster-year weekly source needed for upcoming inference.
    roster_frames = [
        _weekly_roster_frame(nfl, season=value, pulled_at=pulled_at)
        for value in roster_seasons
    ]
    _load(
        pd.concat(roster_frames, ignore_index=True, sort=False),
        "rosters_weekly",
        replace_seasons=None if full_refresh else roster_seasons,
    )
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
