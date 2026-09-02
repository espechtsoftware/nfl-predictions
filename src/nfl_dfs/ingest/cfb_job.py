"""CFB (college football) DK data-collection scaffold: issue #13 item 7.

Owner request (2026-07-31): DK now runs college football DFS (QB/2RB/3WR/
FLEX/Superflex, 8 slots). This is COLLECTION ONLY — no models, features, or
optimizer work reads its output. The goal is a backtestable dataset the
2026 CFB season accumulates, for a 2027 go/no-go decision on building the
rest of the pipeline (features, models, optimizer) for this sport.

Mirrors dk_job.py (slate/salary snapshot) and contest_job.py (fill-rate/
overlay poll) for CFB, reusing the same undocumented DK endpoints with the
CFB sportId (5) instead of NFL's (1) — see dk_client.CFB_SPORT_ID for how
that was verified live. Gated by INGEST_CFB_ENABLED, noop when unset
(contest_job's pattern) — CFB season doesn't start until late August, and
this must not touch the validated NFL ingest path in dk_job.py/
contest_job.py at all.
"""

from __future__ import annotations

import logging
import os

import pandas as pd
import requests

from ..bq import load_dataframe
from ..config import current_season
from . import dk_client

log = logging.getLogger(__name__)


def run() -> None:
    if not os.environ.get("INGEST_CFB_ENABLED"):
        log.info("INGEST_CFB_ENABLED not set; skipping CFB poll")
        return

    session = requests.Session()
    groups = dk_client.cfb_draft_groups(session)
    if not groups:
        log.info("No upcoming CFB draft groups")
        return

    season = current_season()
    frames = []
    stale_group_ids = []
    for g in groups:
        gid = g["draftGroupId"]
        slate_type = dk_client.classify_slate(g)
        try:
            payload = dk_client.fetch_draftables(gid, session)
        except requests.HTTPError as exc:
            response = exc.response
            if response is None or response.status_code != 404:
                raise
            stale_group_ids.append(gid)
            log.warning(
                "Skipping stale CFB draft group %s: draftables returned HTTP 404",
                gid,
            )
            continue
        df = dk_client.draftables_frame(gid, slate_type, payload)
        if df.empty:
            continue
        df["season"] = season
        df["week"] = None
        frames.append(df)
        log.info("CFB slate %s (%s): %d players", gid, slate_type, len(df))

    if groups and len(stale_group_ids) == len(groups):
        raise RuntimeError(
            "All advertised upcoming CFB draft groups returned HTTP 404 "
            "for draftables"
        )

    if frames:
        load_dataframe(
            pd.concat(frames, ignore_index=True),
            "cfb_dk_salaries",
            write_disposition="WRITE_APPEND",
            partition_field="pulled_at",
            clustering_fields=("draft_group_id", "dk_player_id"),
        )

    draft_group_ids = {g["draftGroupId"] for g in groups}
    contests = dk_client.cfb_contests(session)
    cdf = dk_client.contests_frame(contests, draft_group_ids=draft_group_ids, sport="CFB")
    if not cdf.empty:
        load_dataframe(
            cdf,
            "dk_contest_fills",
            write_disposition="WRITE_APPEND",
            partition_field="pulled_at",
            clustering_fields=("draft_group_id", "contest_id"),
        )
        log.info("Polled %d CFB contests across %d draft groups (%d guaranteed)",
                  len(cdf), len(draft_group_ids), int(cdf.is_guaranteed.sum()))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
