from dataclasses import replace

import pandas as pd
import pytest
import requests

from nfl_dfs.config import settings
from nfl_dfs.ingest import odds_api_audit


class _Response:
    def __init__(self, payload, status=200, headers=None):
        self._payload = payload
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        return self._payload


class _Session:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


def _context():
    return odds_api_audit.RequestContext(
        request_kind="live_event_props_shadow",
        endpoint="/sports/americanfootball_nfl/events/e1/odds",
        is_shadow=True,
        season=2026,
        week=1,
        event_id="e1",
        markets="player_rush_attempts",
        bookmakers="draftkings",
        regions="us",
    )


def test_request_audit_captures_quota_without_secret():
    secret = "top-secret-api-key"
    payload = {
        "id": "e1",
        "bookmakers": [{
            "key": "draftkings",
            "markets": [{"key": "player_rush_attempts", "outcomes": []}],
        }],
    }
    session = _Session(_Response(payload, headers={
        "x-requests-remaining": "19991",
        "x-requests-used": "10009",
        "x-requests-last": "9",
    }))
    audits = []

    result = odds_api_audit.request_json(
        _context().endpoint,
        api_key=secret,
        params={"regions": "us", "markets": "player_rush_attempts"},
        context=_context(),
        audit_rows=audits,
        session=session,
    )

    assert result == payload
    assert session.calls[0][1]["params"]["apiKey"] == secret
    assert len(audits) == 1
    row = audits[0]
    assert row["requests_remaining"] == 19991
    assert row["requests_used"] == 10009
    assert row["requests_last"] == 9
    assert row["response_event_count"] == 1
    assert row["response_market_count"] == 1
    assert row["response_market_keys"] == "player_rush_attempts"
    assert row["endpoint"] == _context().endpoint
    assert secret not in repr(row)


def test_http_failure_exception_and_audit_are_secret_safe():
    secret = "must-never-appear"
    session = _Session(_Response({}, status=401, headers={
        "x-requests-remaining": "0", "x-requests-last": "0",
    }))
    audits = []

    with pytest.raises(odds_api_audit.OddsApiRequestError) as caught:
        odds_api_audit.request_json(
            _context().endpoint,
            api_key=secret,
            params={},
            context=_context(),
            audit_rows=audits,
            session=session,
        )

    assert caught.value.status_code == 401
    assert caught.value.error_type == "HTTPError"
    assert secret not in str(caught.value)
    assert secret not in repr(audits)
    assert audits[0]["http_status"] == 401
    assert audits[0]["error_type"] == "HTTPError"


def test_transport_failure_discards_sensitive_exception_text():
    secret = "leaked-in-original-exception"
    session = _Session(error=requests.ConnectionError(secret))
    audits = []

    with pytest.raises(odds_api_audit.OddsApiRequestError) as caught:
        odds_api_audit.request_json(
            _context().endpoint,
            api_key=secret,
            params={},
            context=_context(),
            audit_rows=audits,
            session=session,
        )

    assert str(caught.value) == (
        "Odds API live_event_props_shadow failed: ConnectionError "
        "(status=none)"
    )
    assert secret not in repr(audits)
    assert audits[0]["error_type"] == "ConnectionError"


def test_persist_audits_uses_dedicated_partitioned_table(monkeypatch):
    loaded = []
    monkeypatch.setattr(
        odds_api_audit,
        "settings",
        replace(settings, project="test-project", raw_dataset="nfl_raw"),
    )
    monkeypatch.setattr(
        odds_api_audit,
        "load_dataframe",
        lambda df, table, **kwargs: loaded.append((df, table, kwargs)),
    )
    row = odds_api_audit._audit_row(
        _context(), pd.Timestamp("2026-09-13T15:00:00Z").to_pydatetime()
    )

    assert odds_api_audit.persist_request_audits([row]) is True

    df, table, kwargs = loaded[0]
    assert table == "test-project.nfl_raw.odds_api_requests"
    assert kwargs == {
        "write_disposition": "WRITE_APPEND", "partition_field": "requested_at",
    }
    assert str(df.http_status.dtype) == "Int64"
    assert str(df.error_type.dtype).startswith("string")
    assert str(df.historical.dtype) == "boolean"


def test_bad_audit_path_is_rejected_before_request():
    session = _Session(_Response([]))
    with pytest.raises(ValueError, match="without a query string"):
        odds_api_audit.request_json(
            "/sports/x?apiKey=bad",
            api_key="secret",
            params={},
            context=replace(_context(), endpoint="/sports/x?apiKey=bad"),
            audit_rows=[],
            session=session,
        )
    assert session.calls == []
