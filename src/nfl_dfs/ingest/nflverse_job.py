"""Nightly nflverse ingestion into nfl_raw.

Schedule: daily 06:00 CT in-season (nflverse updates overnight), weekly in the
offseason. Run once with --full to backfill FIRST_SEASON (default 2014) to
the latest completed-or-active season.
"""

from __future__ import annotations

import logging
import sys

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


def _load(df, table: str) -> None:
    # nflreadpy returns polars frames; the BQ client wants pandas.
    load_dataframe(df.to_pandas(), table)


def run(full_refresh: bool = False) -> None:
    import nflreadpy as nfl

    # config's season rolls over in March (we prepare for the coming season),
    # but nflverse has no data for it until games are played — clamp to the
    # latest season the loaders actually serve, or offseason runs crash.
    season = min(current_season(), nfl.get_current_season())
    seasons = list(range(settings.first_season, season + 1)) if full_refresh else [season]

    _load(nfl.load_pbp(seasons), "pbp")
    _load(nfl.load_player_stats(seasons), "weekly_stats")
    legacy_dc = [s for s in seasons
                 if DEPTH_CHARTS_FIRST_SEASON <= s < DEPTH_SNAPSHOTS_FIRST_SEASON]
    if legacy_dc:
        _load(nfl.load_depth_charts(legacy_dc), "depth_charts")
    if snap_dc := [s for s in seasons if s >= DEPTH_SNAPSHOTS_FIRST_SEASON]:
        _load(nfl.load_depth_charts(snap_dc), "depth_charts_snapshots")
    _load(nfl.load_rosters_weekly(seasons), "rosters_weekly")
    _load(nfl.load_schedules(), "schedules")
    _load(nfl.load_ff_playerids(), "player_ids")
    _load(nfl.load_draft_picks(), "draft_picks")
    _load(nfl.load_combine(), "combine")

    if snaps := [s for s in seasons if s >= SNAPS_FIRST_SEASON]:
        _load(nfl.load_snap_counts(snaps), "snap_counts")
    if inj := [s for s in seasons if s >= INJURIES_FIRST_SEASON]:
        _load(nfl.load_injuries(inj), "injuries")
    if ngs := [s for s in seasons if s >= NGS_FIRST_SEASON]:
        for stat_type in ("receiving", "rushing", "passing"):
            _load(nfl.load_nextgen_stats(ngs, stat_type=stat_type), f"ngs_{stat_type}")
    if ftn := [s for s in seasons if s >= FTN_FIRST_SEASON]:
        _load(nfl.load_ftn_charting(ftn), "ftn_charting")
    # Per-defender coverage stats (targets, completions/yards allowed as the
    # nearest defender). PFR-keyed like snap_counts; teams already in
    # nflverse abbreviations. Feeds 017a_defense_week_coverage.
    if pfr := [s for s in seasons if s >= PFR_ADVSTATS_FIRST_SEASON]:
        _load(nfl.load_pfr_advstats(pfr, stat_type="def", summary_level="week"),
              "pfr_advstats_def")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run(full_refresh="--full" in sys.argv)
