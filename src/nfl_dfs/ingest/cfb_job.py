"""CFB DFS collection-only scaffold (issue #13 item 7, owner request
2026-07-31): DraftKings started running college football DFS slates. This
polls the same undocumented endpoints dk_job/contest_job already use, sport
switched to CFB, landing salaries in ``nfl_raw.cfb_dk_salaries`` and
contest fill rates in ``nfl_raw.cfb_dk_contest_fills`` — twin tables to
dk_salaries/dk_contest_fills so the validated NFL ingest path and its
schema stay untouched.

Collection only: no season/week resolution, no features, no optimizer
support. The point is a backtestable 2026-season dataset for a 2027
go/no-go on whether CFB DFS is worth building out further.

Gated by ``INGEST_CFB_ENABLED``, noop when unset (mirrors
``contest_job.py``). See ``dk_client``'s module docstring for the "be a
good citizen" rules this follows (real User-Agent, short timeout, one pass
per run, no retries).
"""

from __future__ import annotations

import logging
import os

import pandas as pd
import requests

from ..bq import load_dataframe
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

    frames = []
    for g in groups:
        gid = g["draftGroupId"]
        slate_type = dk_client.classify_slate(g)
        payload = dk_client.fetch_draftables(gid, session)
        df = dk_client.draftables_frame(gid, slate_type, payload)
        if df.empty:
            continue
        frames.append(df)
        log.info("CFB slate %s (%s): %d players", gid, slate_type, len(df))

    if frames:
        load_dataframe(
            pd.concat(frames, ignore_index=True),
            "cfb_dk_salaries",
            write_disposition="WRITE_APPEND",
            partition_field="pulled_at",
        )

    draft_group_ids = {g["draftGroupId"] for g in groups}
    contests = dk_client.cfb_contests(session)
    contests_df = dk_client.contests_frame(contests, draft_group_ids=draft_group_ids)
    if contests_df.empty:
        log.info("Polled %d CFB contests, none matched upcoming draft groups",
                  len(contests))
        return

    load_dataframe(
        contests_df,
        "cfb_dk_contest_fills",
        write_disposition="WRITE_APPEND",
        partition_field="pulled_at",
    )
    log.info("Polled %d CFB contests across %d draft groups (%d guaranteed)",
              len(contests_df), len(draft_group_ids), int(contests_df.is_guaranteed.sum()))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
