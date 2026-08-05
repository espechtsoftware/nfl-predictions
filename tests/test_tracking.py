"""Workstream C v0: tracking canonicalization, ID matcher, trait
accumulator (plan §7.2, §7.3, §7.6). Offline synthetic frames only."""

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.tracking_ids import (
    CONF_HIGH, CONF_MEDIUM, CONF_REVIEW, match_tracking_players)
from nfl_dfs.research.tracking_traits import (
    FIELD_LENGTH, FIELD_WIDTH, TraitAccumulator, canonicalize)

# ---------------------------------------------------------------- helpers

TRACK_COLS = ["game_id", "play_id", "nfl_id", "frame_id", "play_direction",
              "absolute_yardline_number", "player_name", "player_birth_date",
              "player_position", "player_role", "x", "y", "s", "a",
              "dir", "o"]


def _frame(rows):
    return pd.DataFrame(rows, columns=TRACK_COLS)


def _row(game_id, play_id, nfl_id, frame_id, role, x, y, s=1.0, a=0.5,
         direction="right", yardline=40.0, name="P", pos="WR",
         dob="2000-01-01", d=90.0, o=90.0):
    return [game_id, play_id, nfl_id, frame_id, direction, yardline,
            name, dob, pos, role, x, y, s, a, d, o]


def _mirror(df):
    """The same physical play recorded with play_direction='left'."""
    m = df.copy()
    m["play_direction"] = "left"
    m["x"] = FIELD_LENGTH - m["x"]
    m["y"] = FIELD_WIDTH - m["y"]
    m["dir"] = (m["dir"] + 180.0) % 360.0
    m["o"] = (m["o"] + 180.0) % 360.0
    m["absolute_yardline_number"] = FIELD_LENGTH - m["absolute_yardline_number"]
    return m


# ------------------------------------------------- coordinate invariants


def test_canonicalize_left_right_identical():
    right = _frame([
        _row(1, 1, 10, 1, "Targeted Receiver", x=42.0, y=10.5, d=45.0, o=200.0),
        _row(1, 1, 20, 1, "Defensive Coverage", x=47.0, y=12.0, d=310.0, o=10.0),
    ])
    got_r = canonicalize(right).reset_index(drop=True)
    got_l = canonicalize(_mirror(right)).reset_index(drop=True)
    pd.testing.assert_frame_equal(got_r, got_l, check_dtype=False,
                                  atol=1e-4, rtol=0)


def test_canonicalize_right_plays_untouched():
    right = _frame([_row(1, 1, 10, 1, "Targeted Receiver", x=42.0, y=10.5)])
    got = canonicalize(right)
    assert got.loc[0, "x"] == np.float32(42.0)
    assert got.loc[0, "y"] == np.float32(10.5)
    assert "play_direction" not in got.columns


def test_canonicalize_goal_distance_and_angle_range():
    df = _frame([
        _row(1, 1, 10, 1, "Targeted Receiver", x=30.0, y=20.0,
             direction="left", yardline=80.0, d=200.0, o=350.0),
    ])
    got = canonicalize(df)
    # LOS at absolute 80 moving left == canonical 40 -> 70 yards to goal
    assert got.loc[0, "absolute_yardline_number"] == np.float32(40.0)
    assert got.loc[0, "dist_to_goal"] == np.float32(70.0)
    assert 0.0 <= got.loc[0, "dir"] < 360.0
    assert 0.0 <= got.loc[0, "o"] < 360.0


# ------------------------------------------------------ ID matcher tiers


def _rosters(rows):
    return pd.DataFrame(rows, columns=["gsis_id", "display_name",
                                       "birth_date", "position"])


def _players(rows):
    return pd.DataFrame(rows, columns=["nfl_id", "player_name",
                                       "player_birth_date",
                                       "player_position"])


def test_matcher_exact_name_dob_is_high():
    got = match_tracking_players(
        _players([[1, "Justin Jefferson", "1999-06-16", "WR"]]),
        _rosters([["00-1", "Justin Jefferson", "1999-06-16", "WR"]]))
    assert got.loc[0, "confidence"] == CONF_HIGH
    assert got.loc[0, "gsis_id"] == "00-1"


def test_matcher_dob_disambiguates_name_collision():
    rosters = _rosters([["00-1", "Josh Jones", "1994-01-01", "S"],
                        ["00-2", "Josh Jones", "1997-05-05", "OT"]])
    got = match_tracking_players(
        _players([[1, "Josh Jones", "1997-05-05", "T"]]), rosters)
    assert got.loc[0, "confidence"] == CONF_HIGH
    assert got.loc[0, "gsis_id"] == "00-2"


def test_matcher_ambiguous_collision_flagged_never_guessed():
    rosters = _rosters([["00-1", "Josh Jones", None, "S"],
                        ["00-2", "Josh Jones", None, "OT"]])
    got = match_tracking_players(
        _players([[1, "Josh Jones", "1997-05-05", "T"]]), rosters)
    assert got.loc[0, "confidence"] == CONF_REVIEW
    assert got.loc[0, "gsis_id"] is None
    assert got.loc[0, "n_candidates"] == 2


def test_matcher_dob_conflict_is_review_not_medium():
    got = match_tracking_players(
        _players([[1, "Justin Jefferson", "1999-06-16", "WR"]]),
        _rosters([["00-1", "Justin Jefferson", "1998-01-01", "WR"]]))
    assert got.loc[0, "confidence"] == CONF_REVIEW
    assert got.loc[0, "gsis_id"] is None


def test_matcher_name_only_unambiguous_is_medium():
    got = match_tracking_players(
        _players([[1, "Justin Jefferson", None, "WR"]]),
        _rosters([["00-1", "Justin Jefferson", "1999-06-16", "WR"]]))
    assert got.loc[0, "confidence"] == CONF_MEDIUM
    assert got.loc[0, "gsis_id"] == "00-1"


def test_matcher_suffix_and_diminutive_variants():
    rosters = _rosters([["00-1", "Odell Beckham", "1992-11-05", "WR"],
                        ["00-2", "Cameron Ward", "2002-05-25", "QB"]])
    got = match_tracking_players(
        _players([[1, "Odell Beckham Jr.", "1992-11-05", "WR"],
                  [2, "Cam Ward", "2002-05-25", "QB"]]), rosters)
    assert list(got["confidence"]) == [CONF_HIGH, CONF_HIGH]
    assert list(got["gsis_id"]) == ["00-1", "00-2"]
    assert got.loc[1, "method"].startswith("initial_key")


def test_matcher_unmatched_is_review():
    got = match_tracking_players(
        _players([[1, "Totally Unknown", "1990-01-01", "WR"]]),
        _rosters([["00-1", "Justin Jefferson", "1999-06-16", "WR"]]))
    assert got.loc[0, "confidence"] == CONF_REVIEW
    assert got.loc[0, "gsis_id"] is None
    assert got.loc[0, "method"] == "unmatched"


# ------------------------------------------------------ trait aggregates


def _two_play_week():
    """Two plays; receiver 10 targeted in both, defender 20 covers.

    Play 1 (right): receiver runs x 40->48 (depth 8), speeds 2/4;
      final frame receiver at (48, 10), defenders at (51, 14) -> 5.0
      and (58, 10) -> 10.0; separation = 5.0.
    Play 2 (left, mirrored so canonical values are plain): depth 4,
      speeds 6/8; final separation = 3.0 (receiver (30,20) def (33,20)
      pre-mirror).
    """
    p1 = _frame([
        _row(1, 1, 10, 1, "Targeted Receiver", x=40.0, y=10.0, s=2.0, a=1.0),
        _row(1, 1, 10, 2, "Targeted Receiver", x=48.0, y=10.0, s=4.0, a=3.0),
        _row(1, 1, 20, 1, "Defensive Coverage", x=50.0, y=14.0, s=5.0, a=2.0),
        _row(1, 1, 20, 2, "Defensive Coverage", x=51.0, y=14.0, s=7.0, a=2.0),
        _row(1, 1, 30, 1, "Defensive Coverage", x=58.0, y=10.0, s=1.0, a=0.0),
        _row(1, 1, 30, 2, "Defensive Coverage", x=58.0, y=10.0, s=1.0, a=0.0),
    ])
    p2 = _mirror(_frame([
        _row(1, 2, 10, 1, "Targeted Receiver", x=26.0, y=20.0, s=6.0, a=5.0),
        _row(1, 2, 10, 2, "Targeted Receiver", x=30.0, y=20.0, s=8.0, a=7.0),
        _row(1, 2, 20, 1, "Defensive Coverage", x=33.0, y=20.0, s=9.0, a=1.0),
        _row(1, 2, 20, 2, "Defensive Coverage", x=33.0, y=20.0, s=11.0, a=1.0),
    ]))
    return pd.concat([p1, p2], ignore_index=True)


def test_accumulator_known_aggregates():
    acc = TraitAccumulator()
    stats = acc.update(canonicalize(_two_play_week()), week=1)
    assert stats == {"week": 1, "rows": 10, "plays": 2, "players": 3}

    traits = acc.finalize(2023).set_index("nfl_id")
    r = traits.loc[10]
    speeds = np.array([2.0, 4.0, 6.0, 8.0])
    assert r["recv_speed_mean"] == pytest.approx(np.mean(speeds))
    assert r["recv_speed_p90"] == pytest.approx(np.quantile(speeds, 0.9))
    assert r["recv_accel_p90"] == pytest.approx(np.quantile([1.0, 3.0, 5.0, 7.0], 0.9))
    assert r["route_depth_mean"] == pytest.approx(6.0)            # (8 + 4) / 2
    assert r["separation_mean"] == pytest.approx(4.0)             # (5 + 3) / 2
    assert (r["recv_plays"], r["targeted_plays"]) == (2, 2)
    assert r["separation_n"] == 2 and r["recv_speed_n"] == 4

    d = traits.loc[20]
    def_speeds = [5.0, 7.0, 9.0, 11.0]
    assert d["def_close_speed_p90"] == pytest.approx(np.quantile(def_speeds, 0.9))
    assert d["def_plays"] == 2
    assert np.isnan(d["recv_speed_mean"]) and d["separation_n"] == 0

    # coverage metadata (§7.6)
    assert r["play_type_coverage"] == "pass_pre_throw"
    assert r["weeks_seen"] == 1 and r["last_week"] == 1
    assert r["frames"] == 4 and traits.loc[30, "frames"] == 2


def test_streaming_equals_concatenated():
    week1 = _two_play_week()
    week2 = _two_play_week()
    week2["game_id"] = 2          # distinct games, same physics
    week2["s"] = week2["s"] + 1.0

    streamed = TraitAccumulator()
    streamed.update(canonicalize(week1), week=1)
    streamed.update(canonicalize(week2), week=2)

    combined = TraitAccumulator()
    combined.update(canonicalize(
        pd.concat([week1, week2], ignore_index=True)), week=1)

    drop = ["weeks_seen", "last_week"]     # week labels legitimately differ
    pd.testing.assert_frame_equal(
        streamed.finalize(2023).drop(columns=drop),
        combined.finalize(2023).drop(columns=drop))
