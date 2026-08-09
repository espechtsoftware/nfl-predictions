"""Hourly odds snapshot into nfl_raw.odds_snapshots.

Source: The Odds API's live game-odds endpoint (`americanfootball_nfl`),
restricted to DraftKings' book so lines stay aligned with the DK slates the
rest of the pipeline prices. This replaced the original DK-sportsbook
eventgroup scrape on 2026-07-31: that endpoint 403s (Akamai bot blocking)
from both Cloud Run and residential IPs, and `odds_snapshots` never
received a single row from it — see the README's Data deficiency log.

Cost: one call per run = 1 credit per market per region (3 total with
h2h/spreads/totals), independent of event count — a few hundred credits per
season at the hourly Thu-Sun cadence, negligible next to the props history
(`oddsapi_import.py`), which shares the same ODDS_API_KEY quota.

nflverse closing lines still cover training; this feed exists for live
in-week line movement.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from ..bq import load_dataframe
from ..config import settings
from .odds_api_audit import (
    RequestContext,
    persist_request_audits,
    request_json,
)

log = logging.getLogger(__name__)

ODDS_API_PATH = "/sports/americanfootball_nfl/odds"
MARKETS = "h2h,spreads,totals"
BOOKMAKER = "draftkings"

# The Odds API market keys -> the market_type values odds_snapshots has
# used since its DDL was written (003_misc.sql), so any future reader works
# unchanged against rows from either source era (not that the old era
# produced any rows).
_MARKET_TYPE = {"h2h": "Moneyline", "spreads": "Spread", "totals": "Total"}


def _fetch(session: requests.Session | None = None,
           audit_rows: list[dict] | None = None) -> list[dict[str, Any]]:
    if not settings.odds_api_key:
        raise RuntimeError("ODDS_API_KEY is not set (add it to .env)")
    audits = audit_rows if audit_rows is not None else []
    return request_json(
        ODDS_API_PATH,
        api_key=settings.odds_api_key,
        params={
            "regions": "us",
            "markets": MARKETS,
            "oddsFormat": "american",
            "bookmakers": BOOKMAKER,
        },
        context=RequestContext(
            request_kind="live_game_odds",
            endpoint=ODDS_API_PATH,
            markets=MARKETS,
            bookmakers=BOOKMAKER,
            regions="us",
        ),
        audit_rows=audits,
        session=session,
    )


def _american_str(price: Any) -> str | None:
    """Format The Odds API's numeric american odds the way DK displayed
    them ('+120' / '-110'), matching the STRING column's existing intent."""
    if price is None:
        return None
    return f"{int(price):+d}"


def _rows_from_payload(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pulled_at = datetime.now(timezone.utc)
    rows = []
    for event in payload:
        name = f"{event.get('away_team')} @ {event.get('home_team')}"
        for bk in event.get("bookmakers") or []:
            if bk.get("key") != BOOKMAKER:
                continue
            for market in bk.get("markets") or []:
                market_type = _MARKET_TYPE.get(market.get("key"))
                if market_type is None:
                    continue
                for outcome in market.get("outcomes") or []:
                    rows.append(
                        {
                            "pulled_at": pulled_at,
                            "event_id": event.get("id"),
                            "event_name": name,
                            "start_time": event.get("commence_time"),
                            "market_type": market_type,
                            "selection": outcome.get("name"),
                            "line": outcome.get("point"),
                            "odds_american": _american_str(outcome.get("price")),
                        }
                    )
    return rows


def run() -> None:
    audit_rows: list[dict] = []
    try:
        rows = _rows_from_payload(_fetch(audit_rows=audit_rows))
        if not rows:
            log.info("No odds rows")
            return
        df = pd.DataFrame(rows)
        load_dataframe(df, "odds_snapshots", write_disposition="WRITE_APPEND",
                       partition_field="pulled_at")
        log.info("Wrote %d odds rows across %d events",
                 len(df), df.event_id.nunique())
    finally:
        persist_request_audits(audit_rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
