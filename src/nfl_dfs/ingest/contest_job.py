"""Overlay-detection scaffold: poll DK contest fill rates for upcoming NFL
slates into ``nfl_raw.dk_contest_fills``.

This is infrastructure, not a validated signal yet — a single poll can't
tell overlay from a GPP that simply fills late, the way real ones do. Land
enough polls close to lock (the production schedule would need this hourly
or denser, e.g. every 5-10 min in the last hour before kickoff) before
treating ``overlay_dollars`` as anything but a diagnostic.

Gated by ``INGEST_CONTESTS_ENABLED`` because this hits a second
undocumented DK endpoint (the lobby contest list) beyond the draftgroups
one ``dk_job.py`` already polls hourly — opt in explicitly rather than
silently doubling our request rate against DK once this lands in the
schedule. See ``dk_client``'s module docstring for the "be a good citizen"
rules this follows (real User-Agent, short timeout, one pass per run, no
retries).
"""

from __future__ import annotations

import logging
import os

import requests

from ..bq import load_dataframe
from . import dk_client

log = logging.getLogger(__name__)


def run() -> None:
    if not os.environ.get("INGEST_CONTESTS_ENABLED"):
        log.info("INGEST_CONTESTS_ENABLED not set; skipping contest poll")
        return

    session = requests.Session()
    groups = dk_client.nfl_draft_groups(session)
    if not groups:
        log.info("No upcoming NFL draft groups; nothing to match contests to")
        return
    draft_group_ids = {g["draftGroupId"] for g in groups}

    contests = dk_client.nfl_contests(session)
    df = dk_client.contests_frame(contests, draft_group_ids=draft_group_ids)
    if df.empty:
        log.info("Polled %d contests, none matched upcoming NFL draft groups",
                  len(contests))
        return

    load_dataframe(
        df,
        "dk_contest_fills",
        write_disposition="WRITE_APPEND",
        partition_field="pulled_at",
    )
    log.info("Polled %d contests across %d NFL draft groups (%d guaranteed)",
              len(df), len(draft_group_ids), int(df.is_guaranteed.sum()))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
