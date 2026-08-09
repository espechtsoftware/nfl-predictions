"""Secret-safe request and quota telemetry for The Odds API.

The API key is deliberately accepted separately from the audit context and
is never copied into a row or a log message.  ``requests`` includes the full
query string in its normal HTTP exception text, so callers receive a small
sanitized exception instead of the original one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd
import requests

from ..bq import load_dataframe
from ..config import settings

log = logging.getLogger(__name__)

BASE = "https://api.the-odds-api.com/v4"
AUDIT_TABLE = "odds_api_requests"


@dataclass(frozen=True)
class RequestContext:
    """Non-secret identity persisted for one API request."""

    request_kind: str
    endpoint: str
    historical: bool = False
    is_shadow: bool = False
    season: int | None = None
    week: int | None = None
    event_id: str | None = None
    markets: str | None = None
    bookmakers: str | None = None
    regions: str | None = None


class OddsApiRequestError(RuntimeError):
    """An Odds API failure whose text cannot disclose request parameters."""

    def __init__(self, request_kind: str, error_type: str,
                 status_code: int | None = None) -> None:
        self.request_kind = request_kind
        self.error_type = error_type
        self.status_code = status_code
        status = str(status_code) if status_code is not None else "none"
        super().__init__(
            f"Odds API {request_kind} failed: {error_type} (status={status})"
        )


def _header_int(headers: Mapping[str, Any], name: str) -> int | None:
    value = headers.get(name)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _payload_summary(payload: Any) -> tuple[int, int, str | None]:
    """Return event count, market occurrence count, and unique market keys."""
    data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
    if isinstance(data, list):
        events = data
    elif isinstance(data, dict):
        events = [data]
    else:
        events = []
    market_keys: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        for bookmaker in event.get("bookmakers") or []:
            for market in bookmaker.get("markets") or []:
                key = market.get("key")
                if key:
                    market_keys.append(str(key))
    unique_keys = ",".join(sorted(set(market_keys))) or None
    return len(events), len(market_keys), unique_keys


def _audit_row(
    context: RequestContext,
    requested_at: datetime,
    *,
    response: Any = None,
    payload: Any = None,
    error_type: str | None = None,
) -> dict[str, Any]:
    status = getattr(response, "status_code", None)
    headers = getattr(response, "headers", {}) or {}
    event_count, market_count, market_keys = _payload_summary(payload)
    return {
        "requested_at": requested_at,
        "request_kind": context.request_kind,
        "endpoint": context.endpoint,
        "historical": context.historical,
        "is_shadow": context.is_shadow,
        "season": context.season,
        "week": context.week,
        "event_id": context.event_id,
        "markets": context.markets,
        "bookmakers": context.bookmakers,
        "regions": context.regions,
        "http_status": status,
        "requests_remaining": _header_int(headers, "x-requests-remaining"),
        "requests_used": _header_int(headers, "x-requests-used"),
        "requests_last": _header_int(headers, "x-requests-last"),
        "response_event_count": event_count,
        "response_market_count": market_count,
        "response_market_keys": market_keys,
        "error_type": error_type,
    }


def request_json(
    path: str,
    *,
    api_key: str,
    params: Mapping[str, Any],
    context: RequestContext,
    audit_rows: list[dict[str, Any]],
    session: Any = None,
) -> Any:
    """Request JSON and append exactly one secret-free audit record."""
    if not path.startswith("/") or "?" in path:
        raise ValueError("Odds API path must be an absolute path without a query string")
    if context.endpoint != path:
        raise ValueError("audit endpoint must exactly match the request path")

    requested_at = datetime.now(timezone.utc)
    request_params = dict(params)
    request_params["apiKey"] = api_key
    requester = session or requests
    try:
        response = requester.get(
            f"{BASE}{path}", params=request_params, timeout=30
        )
    except requests.RequestException as exc:
        error_type = type(exc).__name__
        audit_rows.append(
            _audit_row(context, requested_at, error_type=error_type)
        )
        raise OddsApiRequestError(context.request_kind, error_type) from None

    status = int(response.status_code)
    if not 200 <= status < 300:
        audit_rows.append(
            _audit_row(
                context, requested_at, response=response, error_type="HTTPError"
            )
        )
        raise OddsApiRequestError(
            context.request_kind, "HTTPError", status_code=status
        ) from None
    try:
        payload = response.json()
    except (TypeError, ValueError):
        audit_rows.append(
            _audit_row(
                context, requested_at, response=response, error_type="InvalidJSON"
            )
        )
        raise OddsApiRequestError(
            context.request_kind, "InvalidJSON", status_code=status
        ) from None
    audit_rows.append(
        _audit_row(context, requested_at, response=response, payload=payload)
    )
    return payload


def persist_request_audits(rows: list[dict[str, Any]]) -> bool:
    """Append request audits without causing credit-consuming job retries.

    A warehouse outage after successful API requests must not fail the Cloud
    Run job and automatically repeat those paid requests.  The failure is
    reported using only its exception class, never exception text.
    """
    if not rows:
        return True
    df = pd.DataFrame(rows)
    integer_columns = (
        "season", "week", "http_status", "requests_remaining",
        "requests_used", "requests_last", "response_event_count",
        "response_market_count",
    )
    for column in integer_columns:
        df[column] = pd.array(df[column], dtype="Int64")
    string_columns = (
        "request_kind", "endpoint", "event_id", "markets", "bookmakers",
        "regions", "response_market_keys", "error_type",
    )
    for column in string_columns:
        df[column] = pd.array(df[column], dtype="string")
    for column in ("historical", "is_shadow"):
        df[column] = pd.array(df[column], dtype="boolean")
    df["requested_at"] = pd.to_datetime(df["requested_at"], utc=True)
    try:
        load_dataframe(
            df,
            f"{settings.raw}.{AUDIT_TABLE}",
            write_disposition="WRITE_APPEND",
            partition_field="requested_at",
            clustering_fields=("request_kind", "is_shadow", "http_status"),
        )
    except Exception as exc:  # telemetry must not trigger paid retries
        log.error(
            "Could not persist %d Odds API request audits (%s)",
            len(rows), type(exc).__name__,
        )
        return False
    return True
