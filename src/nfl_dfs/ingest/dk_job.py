"""Hourly DraftKings slate/salary snapshot into nfl_raw.dk_salaries.

Append-only by design: the history of how a player's status changed before
lock is itself a valuable feature. Never overwrite.

Schedule: hourly Thu 00:00 - Mon 04:00 CT.
"""

from __future__ import annotations

import logging

import pandas as pd
import requests

from ..bq import load_dataframe
from ..config import current_season
from . import dk_client

log = logging.getLogger(__name__)


def season_week_for(groups: list[dict]) -> tuple[int, int | None]:
    season = current_season()
    # DK draft groups carry a minStartTime; week resolution happens downstream
    # by joining game_start against nfl_raw.schedules. Kept nullable here.
    return season, None


def run() -> None:
    session = requests.Session()
    groups = dk_client.nfl_draft_groups(session)
    if not groups:
        log.info("No upcoming NFL draft groups")
        return

    season, week = season_week_for(groups)
    frames = []
    for g in groups:
        gid = g["draftGroupId"]
        slate_type = dk_client.classify_slate(g)
        payload = dk_client.fetch_draftables(gid, session)
        df = dk_client.draftables_frame(gid, slate_type, payload)
        if df.empty:
            continue
        df["season"] = season
        df["week"] = week
        frames.append(df)
        log.info("Slate %s (%s): %d players", gid, slate_type, len(df))

    if not frames:
        return
    load_dataframe(
        pd.concat(frames, ignore_index=True),
        "dk_salaries",
        write_disposition="WRITE_APPEND",
        partition_field="pulled_at",
        # The live table is clustered; a load job that omits the clustering
        # spec is rejected outright ("Incompatible table partitioning
        # specification"), which killed the ingest even after the draft-group
        # filter was repaired (found 2026-08-20 running the real job).
        clustering_fields=("season", "week", "dk_player_id"),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
