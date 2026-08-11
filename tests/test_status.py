"""Offline coverage for the system-status/freshness module and endpoint.

_table_info is the single GCP seam in nfl_dfs/status.py — everything here
monkeypatches it, so no BigQuery access."""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from nfl_dfs import status
from nfl_dfs.app import main as app_main

IN_SEASON = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
OFF_SEASON = datetime(2026, 4, 15, 12, tzinfo=timezone.utc)


def _info_all_fresh(now):
    return lambda dataset, table: (now - timedelta(hours=1), 1000)


def test_active_windows():
    assert status._active("always", date(2026, 4, 1))
    assert status._active("nfl", date(2026, 10, 1))
    assert not status._active("nfl", date(2026, 4, 1))
    assert status._active("cfb", date(2026, 8, 23))
    assert not status._active("cfb", date(2026, 8, 1))


def test_all_fresh_in_season(monkeypatch):
    monkeypatch.setattr(status, "_table_info", _info_all_fresh(IN_SEASON))
    comps = status.system_status(now=IN_SEASON)
    assert len(comps) == len(status.FEEDS)
    assert {c["state"] for c in comps} == {"ok"}
    status.check_freshness(now=IN_SEASON)  # must not raise


def test_stale_feed_fails_check_in_season(monkeypatch):
    def info(dataset, table):
        if table == "dk_salaries":
            return IN_SEASON - timedelta(days=5), 1000
        return IN_SEASON - timedelta(hours=1), 1000

    monkeypatch.setattr(status, "_table_info", info)
    by_key = {c["key"]: c for c in status.system_status(now=IN_SEASON)}
    assert by_key["dk_salaries"]["state"] == "stale"
    with pytest.raises(RuntimeError, match="DK slates/salaries"):
        status.check_freshness(now=IN_SEASON)


def test_stale_seasonal_feed_is_idle_off_season(monkeypatch):
    def info(dataset, table):
        if table in ("dk_salaries", "player_projections"):
            return OFF_SEASON - timedelta(days=90), 1000
        return OFF_SEASON - timedelta(hours=1), 1000

    monkeypatch.setattr(status, "_table_info", info)
    by_key = {c["key"]: c for c in status.system_status(now=OFF_SEASON)}
    assert by_key["dk_salaries"]["state"] == "idle"
    status.check_freshness(now=OFF_SEASON)  # seasonal staleness is fine in April


def test_always_feed_must_stay_fresh_off_season(monkeypatch):
    """odds_snapshots is the one remaining year-round feed (its scheduler
    runs through the off-season); it must alert even in April."""
    def info(dataset, table):
        if table == "odds_snapshots":
            return OFF_SEASON - timedelta(days=10), 1000
        return OFF_SEASON - timedelta(hours=1), 1000

    monkeypatch.setattr(status, "_table_info", info)
    with pytest.raises(RuntimeError, match="Game lines"):
        status.check_freshness(now=OFF_SEASON)


def test_non_alerting_feed_never_fails_check(monkeypatch):
    def info(dataset, table):
        if table == "dk_contest_fills":
            return None  # table missing entirely
        return IN_SEASON - timedelta(hours=1), 1000

    monkeypatch.setattr(status, "_table_info", info)
    by_key = {c["key"]: c for c in status.system_status(now=IN_SEASON)}
    assert by_key["dk_contest_fills"]["state"] == "missing"
    status.check_freshness(now=IN_SEASON)  # informational feed, must not raise


def test_empty_active_feed_fails_check(monkeypatch):
    def info(dataset, table):
        if table == "odds_snapshots":
            return IN_SEASON - timedelta(hours=1), 0
        return IN_SEASON - timedelta(hours=1), 1000

    monkeypatch.setattr(status, "_table_info", info)
    with pytest.raises(RuntimeError, match="Game lines"):
        status.check_freshness(now=IN_SEASON)


def test_api_system_status_endpoint(monkeypatch):
    monkeypatch.setattr(
        status, "_table_info",
        lambda dataset, table: (datetime.now(timezone.utc) - timedelta(hours=1), 42),
    )
    client = TestClient(app_main.app)
    r = client.get("/api/system-status")
    assert r.status_code == 200
    body = r.json()
    assert body["generated_at"]
    assert len(body["components"]) == len(status.FEEDS)
    assert all(c["state"] in ("ok", "stale", "empty", "idle", "missing")
               for c in body["components"])


def test_nav_html_has_status_button():
    assert "System status" in app_main._NAV_HTML
    assert "openStatus()" in app_main._NAV_HTML
    assert "statusmodal" in app_main._NAV_HTML


def test_nav_html_defers_paid_downloads_until_adoption():
    assert "No recurring Fantasy" in app_main._NAV_HTML
    assert (
        "Never upload data produced by the games being predicted"
        in app_main._NAV_HTML
    )


def test_nav_html_requires_ephemeral_gpp_standings_capture():
    assert "full contest standings CSV" in app_main._NAV_HTML
    assert "exact\nplacement and ROI analysis" in app_main._NAV_HTML


def test_candidate_features_env_gate(monkeypatch):
    """EXTRA_FEATURES adds only registered candidates; unset = baseline."""
    from nfl_dfs.models import featureset

    monkeypatch.delenv("EXTRA_FEATURES", raising=False)
    assert featureset._active_numeric_features() == featureset.NUMERIC_FEATURES

    monkeypatch.setenv("EXTRA_FEATURES", "pace_env_l6, not_a_feature")
    active = featureset._active_numeric_features()
    assert active == featureset.NUMERIC_FEATURES + ["pace_env_l6"]


def test_drop_features_env(monkeypatch):
    from nfl_dfs.models import featureset

    monkeypatch.setenv("DROP_FEATURES", "salary, salary_delta_wow")
    monkeypatch.delenv("EXTRA_FEATURES", raising=False)
    active = featureset._active_numeric_features()
    assert "salary" not in active and "salary_delta_wow" not in active
    assert len(active) == len(featureset.NUMERIC_FEATURES) - 2
