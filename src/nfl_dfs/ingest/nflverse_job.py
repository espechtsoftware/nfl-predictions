"""Nightly nflverse ingestion into nfl_raw.

Schedule: daily 06:00 CT in-season (nflverse updates overnight), weekly in the
offseason. Run once with --full to backfill 1999-present (~15 min, ~2 GB).
"""

from __future__ import annotations

import logging
import sys

from ..bq import load_dataframe
from ..config import current_season, settings

log = logging.getLogger(__name__)

FTN_FIRST_SEASON = 2022
NGS_FIRST_SEASON = 2016
SNAPS_FIRST_SEASON = 2012
INJURIES_FIRST_SEASON = 2009


def _load(df, table: str) -> None:
    # nflreadpy returns polars frames; the BQ client wants pandas.
    load_dataframe(df.to_pandas(), table)


def run(full_refresh: bool = False) -> None:
    import nflreadpy as nfl

    season = current_season()
    seasons = list(range(settings.first_season, season + 1)) if full_refresh else [season]

    _load(nfl.load_pbp(seasons), "pbp")
    _load(nfl.load_player_stats(seasons), "weekly_stats")
    _load(nfl.load_depth_charts([s for s in seasons if s >= 2001]), "depth_charts")
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run(full_refresh="--full" in sys.argv)
