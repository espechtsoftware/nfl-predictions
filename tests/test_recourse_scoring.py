import pandas as pd
import pytest

from nfl_dfs.models.dst_scoring import DST_SCORING_LAW_ID
from nfl_dfs.research.recourse_scoring import (
    points_information_as_of,
    score_skill_players,
    score_team_defenses,
)


def _row(play_id, event_time, **values):
    row = {
        "game_id": "2025_01_A_B",
        "season": 2025,
        "week": 1,
        "play_id": play_id,
        "time_of_day": event_time,
        "home_team": "B",
        "away_team": "A",
        "total_home_score": 0,
        "total_away_score": 0,
        "posteam": "A",
        "defteam": "B",
        "play_type": "pass",
    }
    row.update(values)
    return row


def test_skill_scorer_stops_at_as_of_and_handles_lateral_and_two_point():
    pbp = pd.DataFrame([
        _row(
            1,
            "2025-09-07T17:10:00Z",
            passer_player_id="qb",
            receiver_player_id="wr",
            lateral_receiver_player_id="rb",
            passing_yards=25,
            receiving_yards=10,
            lateral_receiving_yards=15,
            complete_pass=1,
        ),
        _row(
            2,
            "2025-09-07T17:11:00Z",
            passer_player_id="qb",
            receiver_player_id="wr",
            fantasy_player_id="wr",
            two_point_attempt=1,
            two_point_conv_result="success",
        ),
        _row(
            3,
            "2025-09-07T17:12:00Z",
            rusher_player_id="rb",
            rushing_yards=100,
            rush_touchdown=1,
            touchdown=1,
            td_player_id="rb",
            play_type="run",
        ),
        _row(
            4,
            "2025-09-07T18:00:00Z",
            passer_player_id="qb",
            pass_touchdown=1,
            receiver_player_id="wr",
            td_player_id="wr",
            touchdown=1,
        ),
    ])
    scored, receipt = score_skill_players(
        pbp, as_of="2025-09-07T17:30:00Z",
    )
    by_id = scored.set_index("player_id")
    assert by_id.loc["qb", "dk_points"] == pytest.approx(3.0)
    assert by_id.loc["wr", "dk_points"] == pytest.approx(4.0)
    assert by_id.loc["rb", "dk_points"] == pytest.approx(20.5)
    assert by_id.loc["wr", "receptions"] == 1
    assert by_id.loc["rb", "receptions"] == 0
    assert receipt["excluded_after_as_of"] == 1


def test_skill_scorer_reconciles_checksum_bound_multi_lateral_description():
    description = (
        "(:02) (Shotgun) 10-J.Herbert pass short left to 1-Q.Johnston to CLE "
        "33 for 26 yards. Lateral to 5-J.Palmer to CLE 24 for 9 yards. "
        "Lateral to 15-L.McConkey to CLE 30 for -6 yards. Lateral to "
        "27-J.Dobbins to CLE 20 for 10 yards (23-M.Emerson)."
    )
    pbp = pd.DataFrame([_row(
        2105,
        "2024-11-03T19:28:29.350Z",
        game_id="2024_09_LAC_CLE",
        season=2024,
        week=9,
        desc=description,
        receiver_player_id="00-0038544",
        lateral_receiver_player_id="00-0036158",
        receiving_yards=26,
        lateral_receiving_yards=10,
        complete_pass=1,
    )])
    scored, receipt = score_skill_players(
        pbp, as_of="2024-11-03T19:30:00Z",
    )
    by_id = scored.set_index("player_id")
    assert by_id.loc["00-0036988", "rec_yards"] == 9
    assert by_id.loc["00-0039915", "rec_yards"] == -6
    assert by_id.loc["00-0036158", "rec_yards"] == 10
    assert receipt["multi_lateral_plays_adjusted"] == 1
    assert receipt["multi_lateral_players_adjusted"] == 2


def test_skill_scorer_aborts_if_registered_multi_lateral_description_drifts():
    pbp = pd.DataFrame([_row(
        2105,
        "2024-11-03T19:28:29.350Z",
        game_id="2024_09_LAC_CLE",
        season=2024,
        week=9,
        desc="changed description",
    )])
    with pytest.raises(ValueError, match="description checksum differs"):
        score_skill_players(pbp)


def test_skill_scorer_attributes_lost_fumbles_and_special_team_td():
    pbp = pd.DataFrame([
        _row(
            1,
            "2025-09-07T17:10:00Z",
            fumble_lost=1,
            fumbled_1_player_id="qb",
            fumbled_1_team="A",
            fumble_recovery_1_team="A",
            fumbled_2_player_id="rb",
            fumbled_2_team="A",
            fumble_recovery_2_team="B",
            rusher_player_id="rb",
        ),
        _row(
            2,
            "2025-09-07T17:11:00Z",
            fumble_lost=1,
            fumbled_1_player_id="wr",
            fumbled_1_team="A",
            fumble_recovery_1_team=None,
            receiver_player_id="wr",
        ),
        _row(
            3,
            "2025-09-07T17:12:00Z",
            touchdown=1,
            return_touchdown=1,
            td_player_id="returner",
            punt_returner_player_id="returner",
            td_team="A",
            play_type="punt",
        ),
    ])
    scored, receipt = score_skill_players(pbp)
    by_id = scored.set_index("player_id")
    assert "qb" not in by_id.index
    assert by_id.loc["rb", "dk_points"] == -1
    assert by_id.loc["wr", "dk_points"] == -1
    assert by_id.loc["returner", "dk_points"] == 6
    assert receipt["touchback_fumbles"] == 1


def test_skill_scorer_excludes_return_and_lateral_only_fumbles_from_boxscore():
    pbp = pd.DataFrame([
        _row(
            1,
            "2025-09-07T17:10:00Z",
            fumble_lost=1,
            fumbled_1_player_id="returner",
            fumbled_1_team="A",
            fumble_recovery_1_team="B",
            play_type="kickoff",
        ),
        _row(
            2,
            "2025-09-07T17:11:00Z",
            receiver_player_id="wr",
            lateral_receiver_player_id="lateral",
            receiving_yards=2,
            lateral_receiving_yards=8,
            complete_pass=1,
            fumble_lost=1,
            fumbled_1_player_id="lateral",
            fumbled_1_team="A",
            fumble_recovery_1_team="B",
        ),
    ])
    scored, receipt = score_skill_players(pbp)
    by_id = scored.set_index("player_id")
    assert "returner" not in by_id.index
    assert by_id.loc["lateral", "dk_points"] == pytest.approx(0.8)
    assert receipt["non_boxscore_fumbles"] == 2


def test_skill_scorer_does_not_charge_original_qb_for_later_lost_fumble():
    pbp = pd.DataFrame([
        _row(
            1,
            "2025-09-07T17:10:00Z",
            passer_player_id="qb",
            fumble_lost=1,
            fumbled_1_player_id="qb",
            fumbled_1_team="A",
            fumble_recovery_1_team="A",
            fumbled_2_player_id="other",
            fumbled_2_team="A",
            fumble_recovery_2_team="B",
        ),
    ])
    scored, receipt = score_skill_players(pbp)
    assert scored.empty
    assert receipt["non_boxscore_fumbles"] == 1


def test_skill_scorer_counts_block_and_own_kick_recovery_tds_only():
    pbp = pd.DataFrame([
        _row(
            1,
            "2025-09-07T17:10:00Z",
            touchdown=1,
            td_player_id="blocker",
            td_team="A",
            field_goal_result="blocked",
            play_type="field_goal",
        ),
        _row(
            2,
            "2025-09-07T17:11:00Z",
            touchdown=1,
            td_player_id="onside",
            td_team="A",
            own_kickoff_recovery_td=1,
            own_kickoff_recovery_player_id="onside",
            play_type="kickoff",
        ),
        _row(
            3,
            "2025-09-07T17:12:00Z",
            touchdown=1,
            return_touchdown=1,
            td_player_id="muff_recovery",
            td_team="A",
            punt_returner_player_id="other_player",
            play_type="punt",
        ),
    ])
    scored, _ = score_skill_players(pbp)
    by_id = scored.set_index("player_id")
    assert by_id.loc["blocker", "dk_points"] == 6
    assert by_id.loc["onside", "dk_points"] == 6
    assert "muff_recovery" not in by_id.index


def test_dst_scorer_mirrors_event_and_points_allowed_rules():
    pbp = pd.DataFrame([
        _row(
            1,
            "2025-09-07T17:10:00Z",
            sack=1,
        ),
        _row(
            2,
            "2025-09-07T17:11:00Z",
            interception=1,
            touchdown=1,
            return_touchdown=1,
            td_team="B",
            total_home_score=6,
            play_type="pass",
        ),
        _row(
            3,
            "2025-09-07T17:12:00Z",
            extra_point_result="good",
            total_home_score=7,
            play_type="extra_point",
        ),
        _row(
            4,
            "2025-09-07T17:13:00Z",
            fumbled_1_team="A",
            fumble_recovery_1_team="B",
            total_home_score=7,
            play_type="run",
        ),
        _row(
            5,
            "2025-09-07T17:14:00Z",
            total_home_score=7,
            total_away_score=14,
            posteam="A",
            defteam="B",
            play_type="extra_point",
        ),
    ])
    scored, receipt = score_team_defenses(pbp)
    by_team = scored.set_index("team")
    # B: sack 1 + INT 2 + defensive TD 6 + fumble recovery 2 +
    # points-allowed tier 1 (14 points) = 12. The pick-six is subtracted from
    # A's points surrendered, but its PAT remains charged to A's DST, not B.
    assert by_team.loc["B", "points_allowed"] == 14
    assert by_team.loc["B", "dk_points"] == 12
    # A allowed seven points, but six came from A's own offensive turnover;
    # only the PAT remains in its points-allowed tier.
    assert by_team.loc["A", "points_allowed"] == 1
    assert by_team.loc["A", "dk_points"] == 7
    assert receipt["defenses_scored"] == 2
    assert receipt["scoring_law_id"] == DST_SCORING_LAW_ID


def test_dst_scorer_charges_conversion_return_to_reciprocal_points_allowed():
    pbp = pd.DataFrame([_row(
        1,
        "2025-09-07T17:10:00Z",
        defensive_two_point_conv=1,
        total_home_score=2,
        total_away_score=0,
        play_type="extra_point",
    )])
    scored, _ = score_team_defenses(pbp)
    by_team = scored.set_index("team")

    # B returned A's conversion: B receives +2 plus the shutout tier.
    assert by_team.loc["B", "defensive_conversions"] == 1
    assert by_team.loc["B", "points_allowed"] == 0
    assert by_team.loc["B", "dk_points"] == 12
    # Those two return points were surrendered while A's special teams was on
    # the field, so current DK rules include them in A DST's PA tier.
    assert by_team.loc["A", "points_allowed"] == 2
    assert by_team.loc["A", "dk_points"] == 7


@pytest.mark.parametrize("play_type", ["pass", "run", "qb_kneel", "qb_spike"])
def test_dst_scorer_excludes_safety_only_on_offensive_play(play_type):
    pbp = pd.DataFrame([_row(
        1,
        "2025-09-07T17:10:00Z",
        safety=1,
        total_home_score=2,
        total_away_score=0,
        play_type=play_type,
    )])
    scored, _ = score_team_defenses(pbp)
    by_team = scored.set_index("team")
    # B earns the safety and shutout. A's offense surrendered the scoreboard
    # points, so A's reciprocal DST remains in the zero-PA tier.
    assert by_team.loc["B", "safeties"] == 1
    assert by_team.loc["B", "points_allowed"] == 0
    assert by_team.loc["B", "dk_points"] == 12
    assert by_team.loc["A", "points_allowed"] == 0
    assert by_team.loc["A", "dk_points"] == 10


def test_dst_scorer_charges_punt_safety_to_reciprocal_points_allowed():
    pbp = pd.DataFrame([_row(
        1,
        "2025-09-07T17:10:00Z",
        safety=1,
        total_home_score=2,
        total_away_score=0,
        play_type="punt",
    )])
    scored, _ = score_team_defenses(pbp)
    by_team = scored.set_index("team")
    assert by_team.loc["B", "safeties"] == 1
    assert by_team.loc["B", "dk_points"] == 12
    assert by_team.loc["A", "points_allowed"] == 2
    assert by_team.loc["A", "dk_points"] == 7


def test_dst_scorer_rejects_negative_points_allowed_accounting():
    pbp = pd.DataFrame([_row(
        1,
        "2025-09-07T17:10:00Z",
        safety=1,
        total_home_score=0,
        total_away_score=0,
        play_type="pass",
    )])
    with pytest.raises(ValueError, match="points-allowed accounting is negative"):
        score_team_defenses(pbp)


def test_scorer_rejects_naive_or_missing_scoring_timestamps():
    pbp = pd.DataFrame([
        _row(1, None, passing_yards=10, passer_player_id="qb"),
    ])
    with pytest.raises(ValueError, match="lack event time"):
        score_skill_players(pbp)
    pbp.loc[0, "time_of_day"] = "2025-09-07T17:00:00Z"
    with pytest.raises(ValueError, match="timezone-aware"):
        score_skill_players(pbp, as_of="2025-09-07 17:30:00")


def test_skill_scorer_rejects_multiple_slates():
    pbp = pd.DataFrame([
        _row(1, "2025-09-07T17:00:00Z", passer_player_id="qb"),
        {
            **_row(1, "2025-09-14T17:00:00Z", passer_player_id="qb"),
            "week": 2,
            "game_id": "2025_02_A_B",
        },
    ])
    with pytest.raises(ValueError, match="one season-week"):
        score_skill_players(pbp)


def test_points_information_uses_final_labels_only_for_declared_final_games():
    pbp = pd.DataFrame([
        _row(
            1,
            "2025-09-07T17:10:00Z",
            passer_player_id="early_qb",
            passing_yards=100,
        ),
        {
            **_row(
                1,
                "2025-09-07T20:10:00Z",
                passer_player_id="late_qb",
                passing_yards=200,
            ),
            "game_id": "2025_01_C_D",
            "home_team": "D",
            "away_team": "C",
            "posteam": "C",
            "defteam": "D",
        },
    ])
    catalog = pd.DataFrame([
        {
            "player_id": "early_qb", "dk_id": "1", "position": "QB",
            "team": "A", "game_id": "2025_01_A_B",
            "kickoff_time": "2025-09-07T17:00:00Z",
        },
        {
            "player_id": "DST_B", "dk_id": "2", "position": "DST",
            "team": "B", "game_id": "2025_01_A_B",
            "kickoff_time": "2025-09-07T17:00:00Z",
        },
        {
            "player_id": "late_qb", "dk_id": "3", "position": "QB",
            "team": "C", "game_id": "2025_01_C_D",
            "kickoff_time": "2025-09-07T20:00:00Z",
        },
        {
            "player_id": "bench", "dk_id": "4", "position": "WR",
            "team": "C", "game_id": "2025_01_C_D",
            "kickoff_time": "2025-09-07T20:00:00Z",
        },
    ])
    result, receipt = points_information_as_of(
        pbp,
        catalog,
        pd.DataFrame([
            {"player_id": "early_qb", "dk_points": 30},
            {"player_id": "late_qb", "dk_points": 99},
            {"player_id": "bench", "dk_points": 88},
        ]),
        pd.DataFrame([
            {"team": "B", "dk_points": 12},
            {"team": "D", "dk_points": 20},
        ]),
        as_of="2025-09-07T19:30:00Z",
        final_game_ids=["2025_01_A_B"],
    )
    by_id = result.set_index("dk_id")
    assert by_id.loc["1", "points_to_date"] == 30
    assert by_id.loc["2", "points_to_date"] == 12
    assert by_id.loc["3", "points_to_date"] == 0
    assert by_id.loc["4", "points_to_date"] == 0
    assert by_id.loc["1", "game_status"] == "final"
    assert by_id.loc["3", "game_status"] == "not_started"
    assert receipt["uses_unstarted_or_in_progress_final_outcomes"] is False


def test_points_information_uses_pbp_for_in_progress_game():
    pbp = pd.DataFrame([
        _row(
            1,
            "2025-09-07T17:10:00Z",
            passer_player_id="qb",
            passing_yards=100,
        ),
        _row(
            2,
            "2025-09-07T18:10:00Z",
            passer_player_id="qb",
            pass_touchdown=1,
            receiver_player_id="wr",
            td_player_id="wr",
            touchdown=1,
            total_away_score=7,
        ),
    ])
    catalog = pd.DataFrame([
        {
            "player_id": "qb", "position": "QB", "team": "A",
            "game_id": "2025_01_A_B",
            "kickoff_time": "2025-09-07T17:00:00Z",
        },
        {
            "player_id": "DST_B", "position": "DST", "team": "B",
            "game_id": "2025_01_A_B",
            "kickoff_time": "2025-09-07T17:00:00Z",
        },
    ])
    result, receipt = points_information_as_of(
        pbp,
        catalog,
        pd.DataFrame([{"player_id": "qb", "dk_points": 99}]),
        pd.DataFrame([{"team": "B", "dk_points": 99}]),
        as_of="2025-09-07T17:30:00Z",
        final_game_ids=[],
    )
    by_id = result.set_index("dk_id")
    assert by_id.loc["qb", "points_to_date"] == 4
    assert by_id.loc["DST_B", "points_to_date"] == 10
    assert set(result.game_status) == {"in_progress"}
    assert receipt["status_counts"]["in_progress"] == 2
