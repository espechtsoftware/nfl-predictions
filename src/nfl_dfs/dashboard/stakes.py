"""The week's stake plan, read at runtime from private storage.

contests.json lives only in the project's private bucket
(scripts/week_inputs.py: gs://<bucket>/week-inputs/<season>/wNN/); it is
never committed. The IAP-protected dashboard reads it on request
(operator decision 2026-10-03) and shows entries, fees and stakes.
"""
from __future__ import annotations

import json
import os
from typing import Callable

import pandas as pd

from ..config import settings

Reader = Callable[[int, int], "str | None"]


def object_name(season: int, week: int) -> str:
    return f"week-inputs/{int(season)}/w{int(week):02d}/contests.json"


def gcs_reader(season: int, week: int) -> str | None:
    """contests.json text, or None when the week has no reviewed inputs."""
    from google.api_core.exceptions import NotFound  # noqa: PLC0415
    from google.cloud import storage  # noqa: PLC0415

    bucket = os.environ.get("DASHBOARD_WEEK_INPUTS_BUCKET", settings.gcs_bucket)
    blob = storage.Client(project=settings.project).bucket(bucket).blob(object_name(season, week))
    try:
        return blob.download_as_text()
    except NotFound:
        return None


def stake_rows(text: str | None) -> pd.DataFrame:
    """One row per contest: label, DraftKings name, id, entries, keep, fee,
    stake (= fee x entries, as week_inputs.summarise totals it)."""
    cols = ["name", "dk_name", "contest_id", "entries", "keep", "fee", "stake"]
    if not text:
        return pd.DataFrame(columns=cols)
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("contests") or []
    rows = []
    for c in data:
        entries = int(c.get("entries", 0) or 0)
        fee = float(c.get("fee", 0) or 0)
        rows.append({"name": c.get("name"), "dk_name": c.get("dk_name"),
                     "contest_id": str(c.get("contest_id", "")), "entries": entries,
                     "keep": int(c.get("keep", entries) or 0), "fee": fee,
                     "stake": round(fee * entries, 2)})
    return pd.DataFrame(rows, columns=cols).sort_values("stake", ascending=False).reset_index(drop=True)
