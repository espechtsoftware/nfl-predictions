import numpy as np
import pandas as pd

from nfl_dfs.analysis.prereg064_market_extract import build_market_extract


def _schedules():
    return pd.DataFrame([
        {"season": 2024, "week": 1, "game_id": "early",
         "gameday": "2024-09-08", "gametime": "13:00",
         "game_type": "REG", "weekday": "Sunday",
         "home_team": "A", "away_team": "B"},
        {"season": 2024, "week": 1, "game_id": "late",
         "gameday": "2024-09-08", "gametime": "16:25",
         "game_type": "REG", "weekday": "Sunday",
         "home_team": "C", "away_team": "D"},
    ])


def _snapshot():
    return pd.DataFrame([{
        "season": 2024, "week": 1, "id": "p1", "gsis_id": "p1",
        "name": "Cameron Player", "pos": "WR", "team": "C", "opp": "D",
        "game_id": "late", "salary": 5000, "actual": 23.4,
        "mean_projection": 14.2, "model_points_pre": 13.0,
        "market_points": 15.18,
    }])


def _actuals():
    return pd.DataFrame([{
        "season": 2024, "week": 1, "gsis_id": "p1", "was_active": True,
        "y_targets": 9.0, "y_receptions": 6.0, "y_rec_yards": 90.0,
        "y_rec_tds": 1.0, "y_carries": 0.0, "y_rush_yards": 0.0,
        "y_rush_tds": 0.0, "y_pass_attempts": 0.0, "y_pass_yards": 0.0,
        "y_pass_tds": 0.0, "y_interceptions": 0.0, "y_dk_points": 23.4,
    }])


def test_build_extract_is_strictly_common_lock_and_pairs_sides():
    base = {
        "season": 2024, "week": 1, "event_id": "event",
        "commence_time": "2024-09-08T20:25:00Z", "home_team": "C",
        "away_team": "D", "bookmaker": "draftkings",
        "market": "player_reception_yds", "player": "Cam Player",
        "point": 59.5, "pulled_at": "2024-09-08T00:00:00Z",
    }
    props = pd.DataFrame([
        {**base, "outcome_name": "Over", "price": -105,
         "snapshot_ts": "2024-09-08T16:30:00Z"},
        {**base, "outcome_name": "Under", "price": -115,
         "snapshot_ts": "2024-09-08T16:30:00Z"},
        {**base, "outcome_name": "Over", "price": -125,
         "snapshot_ts": "2024-09-08T18:25:00Z"},
    ])
    out, audit = build_market_extract(
        props, _schedules(), _snapshot(), _actuals()
    )
    assert len(out) == 1
    row = out.iloc[0]
    assert row.gsis_id == "p1"
    assert row.identity_resolution_method == "initial"
    assert row.over_price == -105
    assert row.under_price == -115
    assert row.actual_market_value == 90.0
    assert row.snapshot_ts < row.common_lock_utc
    assert audit["cutoff"]["postlock_rows_excluded"] == 1
    assert audit["strictly_prelock"] is True


def test_anytime_td_null_line_survives_and_uses_one_way_hold():
    props = pd.DataFrame([{
        "season": 2024, "week": 1, "event_id": "event",
        "commence_time": "2024-09-08T20:25:00Z", "home_team": "C",
        "away_team": "D", "bookmaker": "fanduel",
        "market": "player_anytime_td", "player": "Cameron Player",
        "point": np.nan, "outcome_name": "Yes", "price": 150,
        "snapshot_ts": "2024-09-08T16:00:00Z",
        "pulled_at": "2024-09-08T00:00:00Z",
    }])
    out, _ = build_market_extract(props, _schedules(), _snapshot(), _actuals())
    assert len(out) == 1
    row = out.iloc[0]
    assert pd.isna(row.line)
    assert row.over_price == 150
    assert pd.isna(row.under_price)
    assert row.actual_market_value == 1.0
    assert 0 < row.devig_over_probability < 1
    assert row.forecast_dk_component_points > 0
