from dataclasses import replace

import pandas as pd

from nfl_dfs.config import settings
from nfl_dfs.ingest import oddsapi_import


def _event(event_id, commence_time, market):
    return {
        "id": event_id,
        "commence_time": commence_time,
        "home_team": "Chicago Bears",
        "away_team": "Detroit Lions",
        "bookmakers": [{
            "key": "draftkings",
            "markets": [{
                "key": market,
                "outcomes": [{
                    "name": "Over",
                    "description": "Player One",
                    "price": -110,
                    "point": 20.5,
                }],
            }],
        }],
    }


def test_event_window_uses_nfl_local_date():
    # This is Monday in UTC but still the Sunday main slate in the US.
    event = {"commence_time": "2026-09-14T00:20:00Z"}
    assert oddsapi_import._event_is_in_window(
        event, "2026-09-10", "2026-09-14"
    )
    assert not oddsapi_import._event_is_in_window(
        {"commence_time": "2026-08-09T17:00:00Z"},
        "2026-09-10", "2026-09-14",
    )


def test_shadow_guard_requires_header_and_protects_reserve(monkeypatch):
    monkeypatch.setattr(
        oddsapi_import,
        "settings",
        replace(
            settings,
            odds_shadow_markets_enabled=True,
            odds_shadow_min_remaining=5000,
        ),
    )
    cost = len(oddsapi_import.SHADOW_MARKET_KEYS)
    assert not oddsapi_import._shadow_request_allowed([])
    assert not oddsapi_import._shadow_request_allowed([
        {"requests_remaining": None}
    ])
    assert oddsapi_import._shadow_request_allowed([
        {"requests_remaining": 5000 + cost}
    ])
    assert not oddsapi_import._shadow_request_allowed([
        {"requests_remaining": 4999 + cost}
    ])


def test_live_shadow_isolated_and_preseason_event_filtered(monkeypatch):
    monkeypatch.setattr(
        oddsapi_import,
        "settings",
        replace(
            settings,
            odds_api_key="set",
            odds_shadow_markets_enabled=True,
            odds_shadow_min_remaining=5000,
        ),
    )
    monkeypatch.setattr(oddsapi_import.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        oddsapi_import,
        "query_df",
        lambda _: pd.DataFrame([{
            "wk": 1, "first_day": "2026-09-10", "last_day": "2026-09-14",
        }]),
    )
    calls = []

    def fake_get(path, *, audit_rows, request_kind, **kwargs):
        calls.append((path, request_kind, kwargs))
        if request_kind == "live_events":
            audit_rows.append({"requests_remaining": 6000})
            return [
                _event("preseason", "2026-08-09T17:00:00Z", "ignored"),
                _event("regular", "2026-09-13T17:00:00Z", "ignored"),
            ]
        if request_kind == "live_event_props":
            audit_rows.append({"requests_remaining": 5994})
            return _event(
                "regular", "2026-09-13T17:00:00Z", "player_pass_yds"
            )
        audit_rows.append({"requests_remaining": 5985})
        return _event(
            "regular", "2026-09-13T17:00:00Z", "player_rush_attempts"
        )

    monkeypatch.setattr(oddsapi_import, "_get", fake_get)
    loaded = []
    monkeypatch.setattr(
        oddsapi_import,
        "load_dataframe",
        lambda df, table, **kwargs: loaded.append((df, table, kwargs)),
    )

    audits = []
    oddsapi_import._run_live(audits)

    assert [kind for _, kind, _ in calls] == [
        "live_events", "live_event_props", "live_event_props_shadow",
    ]
    assert all("preseason" not in path for path, _, _ in calls[1:])
    assert calls[2][2]["markets"] == oddsapi_import.SHADOW_MARKETS
    assert len(loaded) == 2
    base, shadow = loaded
    assert base[1].endswith(".prop_lines")
    assert set(base[0].market) == {"player_pass_yds"}
    assert base[2]["partition_field"] is None
    assert shadow[1].endswith(".prop_lines_shadow")
    assert set(shadow[0].market) == {"player_rush_attempts"}
    assert shadow[2]["partition_field"] == "pulled_at"


def test_live_shadow_fails_closed_without_quota_header(monkeypatch):
    monkeypatch.setattr(
        oddsapi_import,
        "settings",
        replace(
            settings,
            odds_api_key="set",
            odds_shadow_markets_enabled=True,
            odds_shadow_min_remaining=5000,
        ),
    )
    monkeypatch.setattr(oddsapi_import.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        oddsapi_import,
        "query_df",
        lambda _: pd.DataFrame([{
            "wk": 1, "first_day": "2026-09-10", "last_day": "2026-09-14",
        }]),
    )
    calls = []

    def fake_get(path, *, audit_rows, request_kind, **kwargs):
        calls.append(request_kind)
        if request_kind == "live_events":
            audit_rows.append({"requests_remaining": None})
            return [_event("regular", "2026-09-13T17:00:00Z", "ignored")]
        audit_rows.append({"requests_remaining": None})
        return _event(
            "regular", "2026-09-13T17:00:00Z", "player_pass_yds"
        )

    monkeypatch.setattr(oddsapi_import, "_get", fake_get)
    loaded = []
    monkeypatch.setattr(
        oddsapi_import,
        "load_dataframe",
        lambda df, table, **kwargs: loaded.append(table),
    )

    oddsapi_import._run_live([])

    assert calls == ["live_events", "live_event_props"]
    assert loaded == [f"{oddsapi_import.settings.raw}.prop_lines"]


def test_no_upcoming_regular_week_makes_no_api_request(monkeypatch):
    monkeypatch.setattr(
        oddsapi_import,
        "settings",
        replace(settings, odds_api_key="set"),
    )
    monkeypatch.setattr(oddsapi_import, "query_df", lambda _: pd.DataFrame())
    monkeypatch.setattr(
        oddsapi_import,
        "_get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("must not call the API")
        ),
    )

    oddsapi_import._run_live([])


def test_quota_check_uses_free_endpoint_and_requires_persistence(monkeypatch):
    monkeypatch.setattr(
        oddsapi_import,
        "settings",
        replace(settings, odds_api_key="set"),
    )
    calls = []

    def fake_get(path, *, audit_rows, request_kind, **kwargs):
        calls.append((path, request_kind, kwargs))
        audit_rows.append({
            "requests_remaining": 19991,
            "requests_used": 10009,
            "requests_last": 0,
        })
        return []

    monkeypatch.setattr(oddsapi_import, "_get", fake_get)
    persisted = []
    monkeypatch.setattr(
        oddsapi_import,
        "persist_request_audits",
        lambda rows: persisted.extend(rows) or True,
    )

    oddsapi_import.check_quota()

    assert calls == [("/sports", "quota_check", {})]
    assert persisted[0]["requests_last"] == 0
