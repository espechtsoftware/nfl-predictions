"""De-vig / implied-curve mechanics (Addendum 45)."""
import numpy as np
import pandas as pd

from nfl_dfs.inference.market_implied import (
    american_implied, curve_quantile, implied_curve, market_quantiles)


def _ladder():
    # A realistic DK alt ladder: P(over) falls as the line rises.
    rows = []
    for pt, over, under in [(29.5, -650, 475), (39.5, -270, 210),
                            (46.5, -165, 130), (59.5, 135, -165),
                            (67.5, 210, -265), (85.5, 500, -700)]:
        rows.append({"point": pt, "outcome_name": "Over", "price": over})
        rows.append({"point": pt, "outcome_name": "Under", "price": under})
    return pd.DataFrame(rows)


def test_american_implied_symmetry():
    assert abs(american_implied(100) - 0.5) < 1e-9
    assert abs(american_implied(-110) + american_implied(110) - 1.0) < 0.03


def test_curve_monotone_and_devigged():
    x, y = implied_curve(_ladder())
    assert (np.diff(x) > 0).all() and (np.diff(y) <= 1e-12).all()
    assert 0.8 < y[0] < 1.0 and 0.0 < y[-1] < 0.25


def test_quantiles_ordered_and_in_range():
    x, y = implied_curve(_ladder())
    med, q90 = curve_quantile(x, y, 0.5), curve_quantile(x, y, 0.9)
    assert med < q90
    assert 39.5 <= med <= 67.5 and q90 >= 67.5


def test_market_quantiles_frame():
    d = _ladder()
    d["season"], d["week"], d["market"], d["player"] = 2025, 1, "m", "A B"
    out = market_quantiles(d)
    assert len(out) == 1 and out.q50.iloc[0] < out.q90.iloc[0]


def test_prop_market_accepts_td_only_snapshot(monkeypatch):
    """A season with no two-way prices must not suppress its TD market."""
    from nfl_dfs.models import prop_market

    props = pd.DataFrame([{
        "season": 2019, "week": 1, "bookmaker": "book",
        "market": "player_anytime_td", "outcome_name": "Yes",
        "player": "A Player", "price": 150, "point": np.nan,
        "snapshot_ts": "2019-09-08T15:00:00Z",
    }])
    schedules = pd.DataFrame([{
        "season": 2019, "week": 1, "gameday": "2019-09-08",
        "gametime": "13:00", "game_type": "REG", "weekday": "Sunday",
    }])
    names = pd.DataFrame([{"gsis_id": "p1", "display_name": "A Player"}])
    replies = iter([props, schedules, names])
    monkeypatch.setattr(prop_market, "query_df", lambda _sql: next(replies))

    out = prop_market.market_points((2019,))
    assert len(out) == 1
    assert out.gsis_id.iloc[0] == "p1"
    assert out.market_points.iloc[0] > 0

    # Historical source analysis can retain the component, while the live
    # whole-player blend must be able to reject it as incomplete.
    replies = iter([props, schedules, names])
    monkeypatch.setattr(prop_market, "query_df", lambda _sql: next(replies))
    live_complete = prop_market.market_points((2019,), minimum_markets=2)
    assert live_complete.empty


def test_prop_market_name_authority_includes_preseason_sources(monkeypatch):
    """Live Week 1 must not depend on weekly stats that do not exist yet."""
    from nfl_dfs.models import prop_market

    props = pd.DataFrame([{
        "season": 2026, "week": 1, "bookmaker": "book",
        "market": "player_anytime_td", "outcome_name": "Yes",
        "player": "Cameron Ward", "price": 150, "point": np.nan,
        "snapshot_ts": "2026-09-04T10:00:00Z",
    }])
    schedules = pd.DataFrame([{
        "season": 2026, "week": 1, "gameday": "2026-09-13",
        "gametime": "13:00", "game_type": "REG", "weekday": "Sunday",
    }])
    names = pd.DataFrame([
        {"gsis_id": "p1", "display_name": "Cam Ward"},
    ])
    replies = iter([props, schedules, names])
    queries = []

    def query(sql):
        queries.append(sql)
        return next(replies)

    monkeypatch.setattr(prop_market, "query_df", query)
    out = prop_market.market_points((2026,))

    assert len(out) == 1
    assert out.gsis_id.iloc[0] == "p1"
    assert "rosters_weekly" in queries[2]
    assert "football_name" in queries[2]
    assert "player_id_map" in queries[2]


def test_prop_market_accepts_no_props_snapshot(monkeypatch):
    """Pre-coverage seasons are a normal model-only fallback, not an
    exception path with a column-less groupby."""
    from nfl_dfs.models import prop_market

    props = pd.DataFrame(columns=["season", "week", "bookmaker", "market",
                                  "outcome_name", "player", "price", "point"])
    names = pd.DataFrame(columns=["gsis_id", "display_name"])
    replies = iter([props, names])
    monkeypatch.setattr(prop_market, "query_df", lambda _sql: next(replies))

    out = prop_market.market_points((2019,))
    assert out.empty
    assert list(out.columns) == ["season", "week", "gsis_id", "market_points"]


def test_prop_market_uses_latest_snapshot_before_common_main_lock():
    from nfl_dfs.models.prop_market import latest_pre_main_lock

    schedules = pd.DataFrame([
        {"season": 2025, "week": 1, "gameday": "2025-09-07",
         "gametime": "09:30", "game_type": "REG", "weekday": "Sunday"},
        {"season": 2025, "week": 1, "gameday": "2025-09-07",
         "gametime": "13:00", "game_type": "REG", "weekday": "Sunday"},
        {"season": 2025, "week": 1, "gameday": "2025-09-07",
         "gametime": "16:25", "game_type": "REG", "weekday": "Sunday"},
        {"season": 2025, "week": 1, "gameday": "2025-09-07",
         "gametime": "20:20", "game_type": "REG", "weekday": "Sunday"},
    ])
    base = {
        "season": 2025, "week": 1, "bookmaker": "draftkings",
        "market": "player_reception_yds", "player": "Late Player",
        "point": 50.5, "outcome_name": "Over",
    }
    props = pd.DataFrame([
        {**base, "snapshot_ts": "2025-09-02T18:00:00Z", "price": -105},
        {**base, "snapshot_ts": "2025-09-07T16:30:00Z", "price": -110},
        {**base, "snapshot_ts": "2025-09-07T17:00:00Z", "price": -115},
        {**base, "snapshot_ts": "2025-09-07T18:25:00Z", "price": -120},
    ])
    out, audit = latest_pre_main_lock(props, schedules)
    assert len(out) == 1
    assert out.snapshot_ts.iloc[0] == "2025-09-07T16:30:00Z"
    assert out.price.iloc[0] == -110
    assert audit == {
        "input_rows": 4,
        "main_slate_weeks": 1,
        "prelock_rows": 1,
        "postlock_rows_excluded": 2,
    }


def test_prop_market_consolidates_aliases_to_one_player_week(monkeypatch):
    from nfl_dfs.models import prop_market

    props = pd.DataFrame([
        {"season": 2025, "week": 1, "bookmaker": "draftkings",
         "market": "player_anytime_td", "outcome_name": "Yes",
         "player": name, "price": price, "point": np.nan,
         "snapshot_ts": "2025-09-07T16:00:00Z"}
        for name, price in (("Gabe Davis", 150), ("Gabriel Davis", 160))
    ])
    schedules = pd.DataFrame([{
        "season": 2025, "week": 1, "gameday": "2025-09-07",
        "gametime": "13:00", "game_type": "REG", "weekday": "Sunday",
    }])
    names = pd.DataFrame([
        {"gsis_id": "p1", "display_name": "Gabe Davis"},
        {"gsis_id": "p1", "display_name": "Gabriel Davis"},
    ])
    replies = iter([props, schedules, names])
    monkeypatch.setattr(prop_market, "query_df", lambda _sql: next(replies))
    out = prop_market.market_points((2025,))
    assert len(out) == 1
    assert out.gsis_id.iloc[0] == "p1"
    assert out.market_points.iloc[0] > 0
