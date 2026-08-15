from __future__ import annotations

import pandas as pd

from nfl_dfs.analysis import overtime_fantasy_odds as overtime


def _schedules() -> pd.DataFrame:
    rows = []
    for season in (2021, 2022, 2023, 2024, 2025):
        for week in range(1, 9):
            for game in range(4):
                close = game == 0
                rows.append({
                    "game_id": f"{season}_{week}_{game}",
                    "season": season,
                    "week": week,
                    "game_type": "REG",
                    "overtime": int(close and week % 2 == 0),
                    "spread_line": 1.0 if close else 8.0 + game,
                    "total_line": 43.0 + game,
                })
    return pd.DataFrame(rows)


def test_predictor_uses_only_frozen_post_2021_split_and_is_deterministic():
    first = overtime.evaluate_predictability(_schedules(), bootstrap_replicates=100)
    second = overtime.evaluate_predictability(_schedules(), bootstrap_replicates=100)

    assert first == second
    assert first["train"]["seasons"] == [2022, 2023, 2024]
    assert first["train"]["games"] == 3 * 8 * 4
    assert first["heldout"]["season"] == 2025
    assert first["heldout"]["games"] == 8 * 4
    assert set(first["models"]) == {"m0", "m1", "m2"}
    assert [row["quartile"] for row in first["m2_risk_quartiles"]] == [1, 2, 3, 4]
    assert first["paired_week_bootstrap"]["replicates"] == 100


def test_predictor_reports_market_line_exclusions():
    frame = _schedules()
    frame.loc[frame.game_id.eq("2025_1_0"), "total_line"] = None
    result = overtime.evaluate_predictability(frame, bootstrap_replicates=20)

    assert result["heldout"]["games"] == 31
    assert result["excluded_missing_market"] == [
        {"game_id": "2025_1_0", "season": 2025, "week": 1},
    ]


def _pbp() -> pd.DataFrame:
    common = {
        "game_id": "2025_01_A_B",
        "season": 2025,
        "week": 1,
        "season_type": "REG",
        "home_team": "A",
        "away_team": "B",
        "posteam": "A",
        "defteam": "B",
        "drive": 10,
        "passer_player_id": "qb",
        "receiver_player_id": "wr",
        "rusher_player_id": None,
        "lateral_receiver_player_id": None,
        "lateral_rusher_player_id": None,
        "td_player_id": None,
        "interception": 0,
        "rushing_yards": 0,
        "lateral_rushing_yards": 0,
        "rush_touchdown": 0,
        "lateral_receiving_yards": 0,
        "two_point_attempt": 0,
        "two_point_conv_result": None,
        "fumble_lost": 0,
        "sack": 0,
        "safety": 0,
        "punt_blocked": 0,
        "field_goal_result": None,
        "extra_point_result": None,
        "defensive_two_point_conv": 0,
        "return_touchdown": 0,
        "touchdown": 0,
        "td_team": None,
        "fumbled_1_team": None,
        "fumbled_2_team": None,
        "fumble_recovery_1_team": None,
        "fumble_recovery_2_team": None,
        "play_type": "pass",
    }
    regulation = {
        **common,
        "play_id": 1,
        "qtr": 4,
        "quarter_seconds_remaining": 0,
        "time_of_day": "2025-09-07T20:00:00Z",
        "passing_yards": 280,
        "receiving_yards": 280,
        "complete_pass": 1,
        "pass_touchdown": 0,
        "total_home_score": 20,
        "total_away_score": 20,
    }
    ot = {
        **common,
        "play_id": 2,
        "qtr": 5,
        "quarter_seconds_remaining": 500,
        "time_of_day": "2025-09-07T20:10:00Z",
        "passing_yards": 25,
        "receiving_yards": 25,
        "complete_pass": 1,
        "pass_touchdown": 1,
        "touchdown": 1,
        "td_player_id": "wr",
        "td_team": "A",
        "total_home_score": 26,
        "total_away_score": 20,
    }
    return pd.DataFrame([regulation, ot])


def test_game_delta_rescores_bonuses_and_overtime_period():
    game, players = overtime._score_game_delta(_pbp())

    assert game["skill_delta"] == 17.5
    assert game["bonus_crossings"]["passing_300"] == 1
    assert game["ot_offensive_plays"] == 1
    assert game["ot_possessions"] == 1
    assert game["ot_elapsed_seconds"] == 100.0
    assert max(row["delta"] for row in players) == 9.5
