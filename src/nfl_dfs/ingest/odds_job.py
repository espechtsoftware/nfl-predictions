"""Hourly odds snapshot into nfl_raw.odds_snapshots.

v1 strategy per the guide: nflverse closing lines cover training; for live
in-week game lines we hit the DK sportsbook's public event group endpoint
(we're already a DK consumer). A paid props provider slots in behind the
same interface later, keyed by PROPS_PROVIDER env.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from ..bq import load_dataframe

log = logging.getLogger(__name__)

# DK sportsbook public eventgroup for NFL
DK_SB_NFL = "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/88808"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)", "Accept": "application/json"}


def _rows_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    pulled_at = datetime.now(timezone.utc)
    events = {e["id"]: e for e in payload.get("events", [])}
    rows = []
    markets = {m["id"]: m for m in payload.get("markets", [])}
    for sel in payload.get("selections", []):
        market = markets.get(sel.get("marketId"), {})
        event = events.get(market.get("eventId"), {})
        rows.append(
            {
                "pulled_at": pulled_at,
                "event_id": market.get("eventId"),
                "event_name": event.get("name"),
                "start_time": event.get("startEventDate"),
                "market_type": market.get("marketType", {}).get("name"),
                "selection": sel.get("label"),
                "line": sel.get("points"),
                "odds_american": (sel.get("displayOdds") or {}).get("american"),
            }
        )
    return rows


def run() -> None:
    r = requests.get(DK_SB_NFL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    rows = _rows_from_payload(r.json())
    if not rows:
        log.info("No odds rows")
        return
    df = pd.DataFrame(rows)
    keep = df["market_type"].isin(["Moneyline", "Spread", "Total"])
    df = df[keep | df["market_type"].isna()]
    load_dataframe(df, "odds_snapshots", write_disposition="WRITE_APPEND",
                   partition_field="pulled_at")
    log.info("Wrote %d odds rows", len(df))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
