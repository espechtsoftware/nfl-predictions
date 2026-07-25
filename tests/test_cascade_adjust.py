"""Late-inactive slate adjustment: out players zeroed, teammates bumped."""

import numpy as np
import pandas as pd

from nfl_dfs.inference.cascade_adjust import (
    adjust_for_inactives,
    find_out_players,
    zero_out_projections,
)


def slate(wr1_status=None, wr1_report=None):
    rows = [
        {"gsis_id": "WR1", "display_name": "Alpha Receiver", "dk_position": "WR",
         "team_abbr": "MIN", "status": wr1_status, "injury_status": wr1_report,
         "target_share_l4": 0.27, "wopr_l4": 0.45, "rz20_targets_smoothed": 2.0,
         "carry_share_l4": 0.0, "gl3_carries_smoothed": 0.0},
        {"gsis_id": "WR2", "display_name": "Beta Receiver", "dk_position": "WR",
         "team_abbr": "MIN", "status": None, "injury_status": None,
         "target_share_l4": 0.17, "wopr_l4": 0.28, "rz20_targets_smoothed": 1.0,
         "carry_share_l4": 0.0, "gl3_carries_smoothed": 0.0},
        {"gsis_id": "WR3", "display_name": "Gamma Receiver", "dk_position": "WR",
         "team_abbr": "MIN", "status": None, "injury_status": None,
         "target_share_l4": 0.09, "wopr_l4": 0.15, "rz20_targets_smoothed": 0.5,
         "carry_share_l4": 0.0, "gl3_carries_smoothed": 0.0},
        {"gsis_id": "RB1", "display_name": "Bell Cow", "dk_position": "RB",
         "team_abbr": "MIN", "status": None, "injury_status": None,
         "target_share_l4": 0.10, "wopr_l4": 0.16, "rz20_targets_smoothed": 0.8,
         "carry_share_l4": 0.62, "gl3_carries_smoothed": 1.8},
        {"gsis_id": "RB2", "display_name": "Handcuff", "dk_position": "RB",
         "team_abbr": "MIN", "status": None, "injury_status": None,
         "target_share_l4": 0.04, "wopr_l4": 0.07, "rz20_targets_smoothed": 0.2,
         "carry_share_l4": 0.15, "gl3_carries_smoothed": 0.3},
        {"gsis_id": "WRX", "display_name": "Other Team", "dk_position": "WR",
         "team_abbr": "GB", "status": None, "injury_status": None,
         "target_share_l4": 0.22, "wopr_l4": 0.36, "rz20_targets_smoothed": 1.5,
         "carry_share_l4": 0.0, "gl3_carries_smoothed": 0.0},
    ]
    return pd.DataFrame(rows)


def usage_rec(seed=61):
    rng = np.random.default_rng(seed)
    rows = []
    for week in range(1, 11):
        for gsis, share, tt, rz in (("WR1", 0.27, 9, 2), ("WR2", 0.17, 6, 1),
                                    ("WR3", 0.09, 3, 0), ("RB1", 0.10, 3, 1),
                                    ("RB2", 0.04, 1, 0)):
            rows.append({"gsis_id": gsis, "season": 2024, "week": week,
                         "total_targets": tt, "rz20_targets": rz,
                         "target_share": rng.normal(share, 0.01)})
    return pd.DataFrame(rows)


def usage_rush(seed=7):
    rng = np.random.default_rng(seed)
    rows = []
    for week in range(1, 11):
        for gsis, share, tc, gl in (("RB1", 0.62, 16, 2), ("RB2", 0.15, 4, 0)):
            rows.append({"gsis_id": gsis, "season": 2024, "week": week,
                         "total_carries": tc, "gl3_carries": gl,
                         "carry_share": rng.normal(share, 0.02)})
    return pd.DataFrame(rows)


def no_injuries():
    return pd.DataFrame(columns=["gsis_id", "season", "week", "game_status"])


def test_find_out_players_dk_status_and_report():
    assert find_out_players(slate(wr1_status="O")) == ["WR1"]
    assert find_out_players(slate(wr1_report="Out")) == ["WR1"]
    assert find_out_players(slate(wr1_status="IR")) == ["WR1"]
    assert find_out_players(slate(wr1_status="Q")) == []
    assert find_out_players(slate()) == []


def test_no_inactives_is_a_noop():
    feats = slate()
    adjusted, out_ids = adjust_for_inactives(
        feats, usage_rec(), usage_rush(), no_injuries())
    assert out_ids == []
    pd.testing.assert_frame_equal(adjusted, feats)


def test_out_wr_bumps_same_position_teammates_only():
    feats = slate(wr1_status="O")
    adjusted, out_ids = adjust_for_inactives(
        feats, usage_rec(), usage_rush(), no_injuries())
    assert out_ids == ["WR1"]

    def col(df, gsis, c):
        return float(df.loc[df.gsis_id == gsis, c].iloc[0])

    # Teammate receivers inherit target share; combined bump ~ the vacated share
    bump2 = col(adjusted, "WR2", "target_share_l4") - col(feats, "WR2", "target_share_l4")
    bump3 = col(adjusted, "WR3", "target_share_l4") - col(feats, "WR3", "target_share_l4")
    assert bump2 > bump3 > 0
    assert abs((bump2 + bump3) - 0.27) < 0.03
    # wopr and red zone opportunity move with the share
    assert col(adjusted, "WR2", "wopr_l4") > col(feats, "WR2", "wopr_l4")
    assert col(adjusted, "WR2", "rz20_targets_smoothed") > col(
        feats, "WR2", "rz20_targets_smoothed")
    # Other team and other position groups untouched
    for gsis in ("WRX", "RB1", "RB2"):
        assert col(adjusted, gsis, "target_share_l4") == col(feats, gsis, "target_share_l4")


def test_out_rb_bumps_carry_share_of_handcuff():
    feats = slate()
    feats.loc[feats.gsis_id == "RB1", "status"] = "O"
    adjusted, out_ids = adjust_for_inactives(
        feats, usage_rec(), usage_rush(), no_injuries())
    assert out_ids == ["RB1"]

    def col(df, gsis, c):
        return float(df.loc[df.gsis_id == gsis, c].iloc[0])

    carry_bump = col(adjusted, "RB2", "carry_share_l4") - col(feats, "RB2", "carry_share_l4")
    assert abs(carry_bump - 0.62) < 0.05        # sole candidate inherits it all
    assert col(adjusted, "RB2", "gl3_carries_smoothed") > col(
        feats, "RB2", "gl3_carries_smoothed")
    # RB1 also vacates targets -> RB2 target share rises too
    assert col(adjusted, "RB2", "target_share_l4") > col(feats, "RB2", "target_share_l4")


def test_history_beats_fallback_when_absences_exist():
    """With 3+ prior absences the measured with/without split drives deltas."""
    rng = np.random.default_rng(3)
    rows, out_weeks = [], {3, 6, 9}
    for week in range(1, 13):
        wr1_out = week in out_weeks
        if not wr1_out:
            rows.append({"gsis_id": "WR1", "season": 2024, "week": week,
                         "total_targets": 9, "rz20_targets": 2,
                         "target_share": rng.normal(0.27, 0.01)})
        rows.append({"gsis_id": "WR2", "season": 2024, "week": week,
                     "total_targets": 6, "rz20_targets": 1,
                     "target_share": rng.normal(0.35 if wr1_out else 0.17, 0.01)})
        rows.append({"gsis_id": "WR3", "season": 2024, "week": week,
                     "total_targets": 3, "rz20_targets": 0,
                     "target_share": rng.normal(0.10 if wr1_out else 0.09, 0.01)})
    rec = pd.DataFrame(rows)
    injuries = pd.DataFrame(
        [{"gsis_id": "WR1", "season": 2024, "week": w, "game_status": "Out"}
         for w in out_weeks]
    )
    feats = slate(wr1_status="O")
    adjusted, _ = adjust_for_inactives(feats, rec, usage_rush(), injuries)

    def col(df, gsis, c):
        return float(df.loc[df.gsis_id == gsis, c].iloc[0])

    bump2 = col(adjusted, "WR2", "target_share_l4") - 0.17
    bump3 = col(adjusted, "WR3", "target_share_l4") - 0.09
    assert bump2 > 0.12          # measured ~+0.18 with/without split
    assert bump3 < 0.05          # WR3 barely moved historically


def test_cold_start_backup_gets_bump_on_filled_features():
    """The adjuster runs after the cold-start fill; a NaN share is treated
    as zero so the bump still lands."""
    feats = slate()
    feats.loc[feats.gsis_id == "RB2", ["carry_share_l4", "gl3_carries_smoothed"]] = np.nan
    feats.loc[feats.gsis_id == "RB1", "status"] = "O"
    adjusted, _ = adjust_for_inactives(
        feats, usage_rec(), usage_rush(), no_injuries())
    got = float(adjusted.loc[adjusted.gsis_id == "RB2", "carry_share_l4"].iloc[0])
    assert got > 0.5


def test_zero_out_projections():
    out = pd.DataFrame({
        "gsis_id": ["WR1", "WR2"],
        "proj_points": [15.0, 11.0],
        "proj_p90": [28.0, 22.0],
        "p_20_plus": [0.3, 0.2],
        "value": [3.0, 2.5],
    })
    zeroed = zero_out_projections(out, ["WR1"])
    assert zeroed.loc[0, ["proj_points", "proj_p90", "p_20_plus", "value"]].eq(0).all()
    assert zeroed.loc[1, "proj_points"] == 11.0
    # untouched without out_ids
    pd.testing.assert_frame_equal(zero_out_projections(out, []), out)
