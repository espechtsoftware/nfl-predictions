import pytest
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


def _qb_slate(**over):
    """Four teams: CHI healthy starter + two backups; ATL starter OUT (DK
    'O') so the depth-2 QB is primary; MIA starter Doubtful; NYJ has no
    depth-1 QB on file. A WR with depth_rank 2 must never be touched."""
    rows = [
        {"gsis_id": "CHI1", "display_name": "Chi Starter", "dk_position": "QB", "team_abbr": "CHI", "status": None, "injury_status": None, "depth_rank": 1},
        {"gsis_id": "CHI2", "display_name": "Chi Backup", "dk_position": "QB", "team_abbr": "CHI", "status": None, "injury_status": None, "depth_rank": 2},
        {"gsis_id": "CHI3", "display_name": "Chi Third", "dk_position": "QB", "team_abbr": "CHI", "status": None, "injury_status": None, "depth_rank": 3},
        {"gsis_id": "ATL1", "display_name": "Atl Starter", "dk_position": "QB", "team_abbr": "ATL", "status": "O", "injury_status": None, "depth_rank": 1},
        {"gsis_id": "ATL2", "display_name": "Atl Backup", "dk_position": "QB", "team_abbr": "ATL", "status": None, "injury_status": None, "depth_rank": 2},
        {"gsis_id": "ATL3", "display_name": "Atl Third", "dk_position": "QB", "team_abbr": "ATL", "status": None, "injury_status": None, "depth_rank": 3},
        {"gsis_id": "MIA1", "display_name": "Mia Starter", "dk_position": "QB", "team_abbr": "MIA", "status": None, "injury_status": "Doubtful", "depth_rank": 1},
        {"gsis_id": "MIA2", "display_name": "Mia Backup", "dk_position": "QB", "team_abbr": "MIA", "status": None, "injury_status": None, "depth_rank": 2},
        {"gsis_id": "NYJ2", "display_name": "Jet Backup", "dk_position": "QB", "team_abbr": "NYJ", "status": None, "injury_status": None, "depth_rank": 2},
        {"gsis_id": "CHIWR", "display_name": "Chi Receiver", "dk_position": "WR", "team_abbr": "CHI", "status": None, "injury_status": None, "depth_rank": 2},
    ]
    df = pd.DataFrame(rows)
    for k, v in over.items():
        df.loc[df.gsis_id == k[0], k[1]] = v
    return df


def test_backup_qb_gate_zeroes_backups_behind_a_healthy_primary(monkeypatch):
    monkeypatch.delenv("QB_BACKUP_GATE", raising=False)
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs
    got = find_backup_qbs(_qb_slate())
    # CHI: both backups behind a healthy starter. ATL: starter OUT, so the
    # depth-2 QB is primary and only the third-stringer is gated. MIA: the
    # Doubtful starter is UNAVAILABLE (refinement 2026-09-22 -- 13/13 Doubtful
    # player-weeks took zero snaps), so he is gated himself and MIA2 is promoted
    # rather than the team being skipped. NYJ: no depth-1 on file, left alone.
    assert got == ["ATL3", "CHI2", "CHI3", "MIA1"]
    assert "CHIWR" not in got and "ATL2" not in got and "MIA2" not in got and "NYJ2" not in got


def test_backup_qb_gate_report_out_promotes_the_next_qb(monkeypatch):
    monkeypatch.delenv("QB_BACKUP_GATE", raising=False)
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs
    feats = _qb_slate()
    feats.loc[feats.gsis_id == "CHI1", "injury_status"] = "Out"   # report, not DK feed
    feats.loc[feats.gsis_id == "CHI2", "status"] = "O"            # depth 2 also out
    got = find_backup_qbs(feats)
    assert "CHI3" not in got, "the third-stringer is the primary once 1 and 2 are out"
    assert "CHI2" not in got, "already out; zeroed by find_out_players, not by the gate"


def test_backup_qb_gate_lab_review_cases(monkeypatch):
    """Lab review 2026-09-19, amended 2026-09-22: (a) a depth-2 + depth-3 team with no depth-1 row now
    PROMOTES the shallowest QB present and gates the rest -- the original "unknown, nothing gated" rule was
    the actual cause of the Week-2 Atlanta miss and left 8.5% of that pool ungated; (b) blank-team rows are
    still never grouped together; (c) a Questionable primary still makes the team ambiguous."""
    monkeypatch.delenv("QB_BACKUP_GATE", raising=False)
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs
    feats = _qb_slate()
    feats.loc[feats.gsis_id == "NYJ2", "team_abbr"] = "NYJ"
    feats = pd.concat([feats, pd.DataFrame([
        {"gsis_id": "NYJ3", "display_name": "Jet Third", "dk_position": "QB", "team_abbr": "NYJ", "status": None, "injury_status": None, "depth_rank": 3},
        {"gsis_id": "BLANK1", "display_name": "No Team A", "dk_position": "QB", "team_abbr": "", "status": None, "injury_status": None, "depth_rank": 1},
        {"gsis_id": "BLANK2", "display_name": "No Team B", "dk_position": "QB", "team_abbr": "", "status": None, "injury_status": None, "depth_rank": 2},
    ])], ignore_index=True)
    feats.loc[feats.gsis_id == "CHI1", "injury_status"] = "Questionable"
    got = find_backup_qbs(feats)
    assert "NYJ3" in got, "no depth-1 row: the shallowest present QB is promoted and deeper ones gated"
    assert "NYJ2" not in got, "the promoted shallowest QB is not gated"
    assert "BLANK2" not in got, "blank teams are not grouped"
    assert "CHI2" not in got and "CHI3" not in got, "Questionable primary: ambiguous, nothing gated"
    # MIA's Doubtful starter is gated (2026-09-22 refinement); NYJ3 by the no-depth-1 promotion;
    # Q is still ambiguous so CHI is untouched; blank teams are never grouped.
    assert got == ["ATL3", "MIA1", "NYJ3"], got


def test_backup_qb_gate_tied_primaries_are_order_independent(monkeypatch):
    """Lab v4 boundary: two depth-1 rows, one Doubtful — permuting their ids must not change the gating.
    Since 2026-09-22 a Doubtful row is UNAVAILABLE rather than ambiguous, so the healthy co-starter is
    the primary, the Doubtful one is gated, and the deeper QBs are gated. Order must not matter.
    A Questionable tied row still makes the team ambiguous (Q plays 77.4% of the time)."""
    monkeypatch.delenv("QB_BACKUP_GATE", raising=False)
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs
    base = _qb_slate()
    for a, b in (("CHI1", "CHI9"), ("CHI9", "CHI1")):          # the two lexical orders of the tied pair
        feats = pd.concat([base, pd.DataFrame([{"gsis_id": "CHI9", "display_name": "Chi Co-Starter", "dk_position": "QB",
                                               "team_abbr": "CHI", "status": None, "injury_status": "Doubtful", "depth_rank": 1}])], ignore_index=True)
        feats.loc[feats.gsis_id == "CHI1", "gsis_id"] = "TMP"; feats.loc[feats.gsis_id == "CHI9", "gsis_id"] = a
        feats.loc[feats.gsis_id == "TMP", "gsis_id"] = b
        got = find_backup_qbs(feats)
        assert "CHI2" in got and "CHI3" in got, f"order {a},{b}: the healthy co-starter is primary, deeper QBs gated"
        # the fixture gives the Doubtful row id `a` and the healthy one `b`
        assert a in got, f"order {a},{b}: the Doubtful tied row is gated itself"
        assert b not in got, f"order {a},{b}: the healthy co-starter is the primary"
    # a Questionable tied primary is still ambiguous
    feats = pd.concat([base, pd.DataFrame([{"gsis_id": "CHI9", "display_name": "Chi Co-Starter", "dk_position": "QB",
                                           "team_abbr": "CHI", "status": None, "injury_status": "Questionable", "depth_rank": 1}])], ignore_index=True)
    got = find_backup_qbs(feats)
    assert "CHI2" not in got and "CHI3" not in got, "a Questionable tied primary must still make CHI ambiguous"
    feats = pd.concat([base, pd.DataFrame([{"gsis_id": "CHI0", "display_name": "Chi Co-Starter", "dk_position": "QB",
                                           "team_abbr": "CHI", "status": None, "injury_status": None, "depth_rank": 1}])], ignore_index=True)
    got = find_backup_qbs(feats)
    assert "CHI2" in got and "CHI3" in got and "CHI0" not in got, "an all-healthy tie still gates the deeper QBs"


def test_backup_qb_gate_is_a_noop_without_depth_or_when_disabled(monkeypatch):
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs
    monkeypatch.delenv("QB_BACKUP_GATE", raising=False)
    assert find_backup_qbs(_qb_slate().drop(columns=["depth_rank"])) == []
    monkeypatch.setenv("QB_BACKUP_GATE", "0")
    assert find_backup_qbs(_qb_slate()) == []


def test_backup_qb_gate_zeroes_only_the_gated_rows_in_the_output(monkeypatch):
    monkeypatch.delenv("QB_BACKUP_GATE", raising=False)
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs
    feats = _qb_slate()
    out = pd.DataFrame({"gsis_id": feats.gsis_id, "proj_points": 12.0, "proj_p90": 30.0, "value": 3.0})
    zeroed = zero_out_projections(out, find_backup_qbs(feats))
    gated = zeroed.gsis_id.isin(["ATL3", "CHI2", "CHI3", "MIA1"])
    assert zeroed.loc[gated, ["proj_points", "proj_p90", "value"]].eq(0).all().all()
    pd.testing.assert_frame_equal(zeroed.loc[~gated].reset_index(drop=True), out.loc[~gated].reset_index(drop=True))


def test_doubtful_primary_is_absence_not_ambiguity(monkeypatch):
    """Refinement 2026-09-22 (laptop review, 13/13 Doubtful player-weeks at zero snaps).

    A Doubtful QB cannot be the primary: he is gated himself and the next
    available QB is promoted, so his backups stop carrying inflated projections.
    This is the ATL/Tua case from Week 2 -- depth-1 Out, a Doubtful depth-2
    promoted, the team declared ambiguous, and a 17.47 projection that scored 0.
    """
    monkeypatch.delenv("QB_BACKUP_GATE", raising=False)
    monkeypatch.delenv("QB_DOUBTFUL_ABSENT", raising=False)
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs
    feats = pd.DataFrame([
        {"gsis_id": "T1", "display_name": "Starter", "dk_position": "QB", "team_abbr": "ATL", "status": "O", "injury_status": None, "depth_rank": 1},
        {"gsis_id": "T2", "display_name": "Doubtful Two", "dk_position": "QB", "team_abbr": "ATL", "status": "D", "injury_status": None, "depth_rank": 2},
        {"gsis_id": "T3", "display_name": "Healthy Three", "dk_position": "QB", "team_abbr": "ATL", "status": None, "injury_status": None, "depth_rank": 3},
        {"gsis_id": "T4", "display_name": "Fourth", "dk_position": "QB", "team_abbr": "ATL", "status": None, "injury_status": None, "depth_rank": 4},
    ])
    got = find_backup_qbs(feats)
    assert "T2" in got, "the Doubtful QB is gated himself"
    assert "T4" in got, "QBs behind the promoted primary are gated"
    assert "T3" not in got, "the promoted primary is not gated"
    assert "T1" not in got, "an Out QB is left to the existing out-player path"


def test_doubtful_absent_kill_switch_restores_the_old_rule(monkeypatch):
    """QB_DOUBTFUL_ABSENT=0 reverts to ambiguous-on-Doubtful, without a redeploy."""
    monkeypatch.delenv("QB_BACKUP_GATE", raising=False)
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs
    monkeypatch.setenv("QB_DOUBTFUL_ABSENT", "0")
    got = find_backup_qbs(_qb_slate())
    assert got == ["ATL3", "CHI2", "CHI3"], got
    assert "MIA1" not in got, "with the switch off a Doubtful primary makes MIA ambiguous again"


def test_no_depth1_team_promotes_the_shallowest_qb_present(monkeypatch):
    """2026-09-22: teams with no depth-1 row on the DK slate were ungated entirely.

    That -- not the ambiguity rule -- is why Week-2 Atlanta kept a 17.47 projection on a
    Doubtful QB who scored zero. ATL, MIN and SEA together covered 8.5% of the Week-2
    pool. A QB absent from the slate cannot be rostered, so the shallowest present QB is
    promoted. Measured 4 of 4 correct across both released weeks.
    """
    monkeypatch.delenv("QB_BACKUP_GATE", raising=False)
    monkeypatch.delenv("QB_DOUBTFUL_ABSENT", raising=False)
    monkeypatch.delenv("QB_NO_DEPTH1_PROMOTE", raising=False)
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs
    # the real Week-2 ATL shape: no depth-1 row, a Doubtful depth-2, two deeper QBs
    feats = pd.DataFrame([
        {"gsis_id": "TUA", "display_name": "Doubtful Two", "dk_position": "QB", "team_abbr": "ATL", "status": "D", "injury_status": None, "depth_rank": 2},
        {"gsis_id": "RUSH", "display_name": "Third", "dk_position": "QB", "team_abbr": "ATL", "status": None, "injury_status": None, "depth_rank": 3},
        {"gsis_id": "STRAND", "display_name": "Fourth", "dk_position": "QB", "team_abbr": "ATL", "status": None, "injury_status": None, "depth_rank": 4},
    ])
    got = find_backup_qbs(feats)
    assert "TUA" in got, "the Doubtful QB is gated even with no depth-1 row on file"
    assert "STRAND" in got, "QBs behind the promoted primary are gated"
    assert "RUSH" not in got, "the shallowest available QB is promoted, not gated"


def test_no_depth1_promotion_kill_switch(monkeypatch):
    """QB_NO_DEPTH1_PROMOTE=0 restores leaving a no-depth-1 team entirely alone."""
    monkeypatch.delenv("QB_BACKUP_GATE", raising=False)
    monkeypatch.setenv("QB_NO_DEPTH1_PROMOTE", "0")
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs
    feats = pd.DataFrame([
        {"gsis_id": "A2", "display_name": "Two", "dk_position": "QB", "team_abbr": "ATL", "status": None, "injury_status": None, "depth_rank": 2},
        {"gsis_id": "A3", "display_name": "Three", "dk_position": "QB", "team_abbr": "ATL", "status": None, "injury_status": None, "depth_rank": 3},
    ])
    assert find_backup_qbs(feats) == [], "with the switch off the team is left alone"


def _q_frame():
    feats = pd.DataFrame([
        {"gsis_id": "Q1", "status": "Q", "injury_status": None},
        {"gsis_id": "Q2", "status": None, "injury_status": "Questionable"},
        {"gsis_id": "H1", "status": None, "injury_status": None},
        {"gsis_id": "D1", "status": "D", "injury_status": "Doubtful"},
    ])
    out = pd.DataFrame({"gsis_id": feats.gsis_id, "proj_points": 10.0, "proj_p90": 20.0, "value": 2.0})
    return feats, out


def test_questionable_haircut_defaults_to_a_no_op(monkeypatch):
    monkeypatch.delenv("Q_HAIRCUT", raising=False)
    from nfl_dfs.inference import cascade_adjust as C
    feats, out = _q_frame()
    h = C.questionable_haircut(feats)
    assert h == 1.0
    pd.testing.assert_frame_equal(C.apply_questionable_haircut(out, C.find_questionable_players(feats), h), out)


def test_questionable_haircut_scales_only_q_players_and_only_mean_columns(monkeypatch):
    monkeypatch.setenv("Q_HAIRCUT", "0.85")
    from nfl_dfs.inference import cascade_adjust as C
    feats, out = _q_frame()
    ids = C.find_questionable_players(feats)
    assert ids == ["Q1", "Q2"], "DK status Q and report Questionable both count; Doubtful and healthy do not"
    got = C.apply_questionable_haircut(out, ids, C.questionable_haircut(feats)).set_index("gsis_id")
    assert got.loc["Q1", "proj_points"] == 8.5 and got.loc["Q2", "value"] == 1.7
    assert got.loc["H1", "proj_points"] == 10.0 and got.loc["D1", "proj_points"] == 10.0
    assert (got.proj_p90 == 20.0).all(), "quantiles are not scaled"


def test_questionable_haircut_fails_closed_on_a_bad_value(monkeypatch):
    from nfl_dfs.inference import cascade_adjust as C
    feats, _ = _q_frame()
    for bad in ("0", "1.2", "-0.5", "abc"):
        monkeypatch.setenv("Q_HAIRCUT", bad)
        with pytest.raises(ValueError):
            C.questionable_haircut(feats)


def _dbt_slate():
    return pd.DataFrame([
        {"gsis_id": "WR_D", "position": "WR", "status": "D", "injury_status": "Doubtful"},
        {"gsis_id": "TE_D", "position": "TE", "status": None, "injury_status": "Doubtful"},
        {"gsis_id": "QB_D", "position": "QB", "status": "D", "injury_status": "Doubtful"},
        {"gsis_id": "RB_O", "position": "RB", "status": "O", "injury_status": "Out"},
        {"gsis_id": "WR_Q", "position": "WR", "status": "Q", "injury_status": "Questionable"},
        {"gsis_id": "WR_H", "position": "WR", "status": None, "injury_status": None},
    ])


def test_cascade_doubtful_defaults_off(monkeypatch):
    monkeypatch.delenv("CASCADE_DOUBTFUL", raising=False)
    from nfl_dfs.inference.cascade_adjust import find_out_players
    assert find_out_players(_dbt_slate()) == ["RB_O"], "default: only Out triggers the cascade"


def test_cascade_doubtful_on_adds_non_qb_doubtful_only(monkeypatch):
    monkeypatch.setenv("CASCADE_DOUBTFUL", "1")
    from nfl_dfs.inference.cascade_adjust import find_out_players
    got = find_out_players(_dbt_slate())
    assert got == ["RB_O", "TE_D", "WR_D"], got
    assert "QB_D" not in got, "Doubtful QBs stay with the QB gate"
    assert "WR_Q" not in got and "WR_H" not in got


def test_skip_priced_carries_defaults_off(monkeypatch):
    monkeypatch.delenv("CASCADE_SKIP_PRICED_CARRIES", raising=False)
    feats = slate()
    feats.loc[feats.gsis_id == "RB1", "injury_status"] = "Out"
    adjusted, _ = adjust_for_inactives(feats, usage_rec(), usage_rush(), no_injuries())
    rb2 = lambda df, c: float(df.loc[df.gsis_id == "RB2", c].iloc[0])
    assert rb2(adjusted, "carry_share_l4") > rb2(feats, "carry_share_l4")


def test_skip_priced_carries_on_skips_only_report_out_carry_side(monkeypatch):
    monkeypatch.setenv("CASCADE_SKIP_PRICED_CARRIES", "1")
    rb2 = lambda df, c: float(df.loc[df.gsis_id == "RB2", c].iloc[0])
    # Report-Out: carries already priced by team_vacated_carry_share -> no carry bump,
    # but the target side still redistributes.
    feats = slate()
    feats.loc[feats.gsis_id == "RB1", "injury_status"] = "Out"
    adjusted, out_ids = adjust_for_inactives(feats, usage_rec(), usage_rush(), no_injuries())
    assert out_ids == ["RB1"]
    assert rb2(adjusted, "carry_share_l4") == rb2(feats, "carry_share_l4")
    assert rb2(adjusted, "gl3_carries_smoothed") == rb2(feats, "gl3_carries_smoothed")
    assert rb2(adjusted, "target_share_l4") > rb2(feats, "target_share_l4")
    # DK-only late flip (not on the report, so not in the features) keeps the carry side.
    feats = slate()
    feats.loc[feats.gsis_id == "RB1", "status"] = "O"
    adjusted, _ = adjust_for_inactives(feats, usage_rec(), usage_rush(), no_injuries())
    assert rb2(adjusted, "carry_share_l4") > rb2(feats, "carry_share_l4")


def test_q_primary_backups_are_found_and_scaled_only_when_enabled(monkeypatch):
    """2026-09-23 (operator): backups behind a Questionable primary keep a full as-if-starting projection
    under find_backup_qbs (team ambiguous). They are returned here and scaled by QB_Q_PRIMARY_BACKUP_SCALE."""
    for k in ("QB_BACKUP_GATE", "QB_DOUBTFUL_ABSENT", "QB_NO_DEPTH1_PROMOTE", "QB_Q_PRIMARY_BACKUP_SCALE"):
        monkeypatch.delenv(k, raising=False)
    from nfl_dfs.inference.cascade_adjust import (apply_scale, find_backup_qbs, find_q_primary_backups,
                                                  q_primary_backup_scale)
    feats = _qb_slate()
    feats.loc[feats.gsis_id == "CHI1", "status"] = "Q"                       # SEA-like: primary Questionable
    # MIA-like with CHI's week-3 shape: Doubtful starter, promoted primary Questionable, a third behind him
    feats.loc[feats.gsis_id == "MIA2", "status"] = "Q"
    feats = pd.concat([feats, pd.DataFrame([{"gsis_id": "MIA3", "display_name": "Mia Third", "dk_position": "QB",
                                             "team_abbr": "MIA", "status": None, "injury_status": None,
                                             "depth_rank": 3}])], ignore_index=True)
    got = find_q_primary_backups(feats)
    assert got == ["CHI2", "CHI3", "MIA3"]                                    # never the Q primary, never Doubtful
    assert not set(got) & set(find_backup_qbs(feats)), "disjoint from the zeroing gate"
    assert "ATL3" not in got                                                  # healthy promoted primary: gate's job
    assert q_primary_backup_scale() == 1.0                                    # default is a no-op
    out = pd.DataFrame({"gsis_id": ["CHI1", "CHI2", "MIA3"], "proj_points": [20.0, 12.0, 8.0], "value": [3.0, 2.0, 1.5]})
    pd.testing.assert_frame_equal(apply_scale(out, got, 1.0), out)
    monkeypatch.setenv("QB_Q_PRIMARY_BACKUP_SCALE", "0.2")
    s = apply_scale(out, got, q_primary_backup_scale())
    assert s.proj_points.tolist() == pytest.approx([20.0, 2.4, 1.6]) and s.value.tolist() == pytest.approx([3.0, 0.4, 0.3])
    monkeypatch.setenv("QB_Q_PRIMARY_BACKUP_SCALE", "1.5")
    with pytest.raises(ValueError):
        q_primary_backup_scale()


def _ret_slate():
    """BAL: Flowers (top WR) missed last week and is back; Bateman spiked; a TE played normally; a RB also
    played. KC: bye last week (no absence). NYG: returner is Out now (no adjustment)."""
    rows = [
        ("FLOW", "WR", "BAL", None, None, 0.25, 0.00),
        ("BATE", "WR", "BAL", None, None, 0.18, 0.27),
        ("ANDR", "TE", "BAL", None, None, 0.15, 0.00),
        ("HENR", "RB", "BAL", None, None, 0.05, 0.01),
        ("KCWR", "WR", "KC", None, None, 0.30, 0.00),
        ("KCTE", "TE", "KC", None, None, 0.20, 0.10),
        ("NYWR", "WR", "NYG", "O", None, 0.28, 0.00),
        ("NYTE", "TE", "NYG", None, None, 0.12, 0.08),
    ]
    return pd.DataFrame(rows, columns=["gsis_id", "dk_position", "team_abbr", "status", "injury_status",
                                       "target_share_l4", "target_share_jump"])


def test_returning_teammate_deltas(monkeypatch):
    from nfl_dfs.inference.cascade_adjust import (RETURN_DELTA_OTHER, RETURN_DELTA_SPIKED, RETURN_Q_FACTOR,
                                                  returning_teammate_deltas, returning_teammate_enabled)
    feats = _ret_slate()
    prev = {"BATE", "ANDR", "HENR", "NYTE"}                 # Flowers did not play W-1; KC was on bye
    teams = {"BAL", "NYG"}
    d, rids = returning_teammate_deltas(feats, prev, teams)
    by = dict(zip(feats.gsis_id, d))
    assert rids == ["FLOW"]
    assert by["BATE"] == pytest.approx(RETURN_DELTA_SPIKED)             # spiked teammate
    assert by["ANDR"] == pytest.approx(RETURN_DELTA_OTHER) and by["HENR"] == pytest.approx(RETURN_DELTA_OTHER)
    assert by["FLOW"] == 0 and by["KCWR"] == 0 and by["KCTE"] == 0     # returner untouched; a bye is not an absence
    assert by["NYTE"] == 0                                             # an Out returner is not returning
    feats.loc[feats.gsis_id == "FLOW", "status"] = "Q"
    d, _ = returning_teammate_deltas(feats, prev, teams)
    assert dict(zip(feats.gsis_id, d))["BATE"] == pytest.approx(RETURN_DELTA_SPIKED * RETURN_Q_FACTOR)
    feats.loc[feats.gsis_id == "FLOW", "status"] = "D"
    d, rids = returning_teammate_deltas(feats, prev, teams)
    assert rids == [] and not d.any()                                  # Doubtful returner: no adjustment
    assert returning_teammate_deltas(feats.iloc[0:0], prev, teams)[0].size == 0
    monkeypatch.delenv("RETURNING_TEAMMATE_ADJ", raising=False)
    assert returning_teammate_enabled() is False                       # default off
    monkeypatch.setenv("RETURNING_TEAMMATE_ADJ", "yes")
    with pytest.raises(ValueError):
        returning_teammate_enabled()


def test_returning_lead_rb_lowers_backup_rbs_only_when_enabled(monkeypatch):
    from nfl_dfs.inference.cascade_adjust import (RETURN_RB_DELTA_OTHER, RETURN_RB_DELTA_SPIKED, RETURN_Q_FACTOR,
                                                  returning_teammate_deltas)
    rows = [  # gsis, pos, team, status, target_share_l4, target_share_jump, carry_share_l4, carry_share_jump
        ("LEAD", "RB", "DET", None, 0.08, 0.00, 0.62, 0.00),
        ("BACK", "RB", "DET", None, 0.06, 0.02, 0.35, 0.30),
        ("THRD", "RB", "DET", None, 0.02, 0.00, 0.05, 0.02),
        ("DETW", "WR", "DET", None, 0.22, 0.01, 0.00, 0.00),
    ]
    feats = pd.DataFrame(rows, columns=["gsis_id", "dk_position", "team_abbr", "status", "target_share_l4",
                                        "target_share_jump", "carry_share_l4", "carry_share_jump"])
    feats["injury_status"] = None
    prev, teams = {"BACK", "THRD", "DETW"}, {"DET"}
    monkeypatch.delenv("RETURNING_RB_ADJ", raising=False)
    d, rids = returning_teammate_deltas(feats, prev, teams)
    assert rids == [] and not d.any()                                  # off by default: lead RB (8% targets) ignored
    monkeypatch.setenv("RETURNING_RB_ADJ", "1")
    d, rids = returning_teammate_deltas(feats, prev, teams)
    by = dict(zip(feats.gsis_id, d))
    assert rids == ["LEAD"]
    assert by["BACK"] == pytest.approx(RETURN_RB_DELTA_SPIKED) and by["THRD"] == pytest.approx(RETURN_RB_DELTA_OTHER)
    assert by["DETW"] == 0 and by["LEAD"] == 0                         # carry side touches RBs only
    feats.loc[feats.gsis_id == "LEAD", "status"] = "Q"
    d, _ = returning_teammate_deltas(feats, prev, teams)
    assert dict(zip(feats.gsis_id, d))["BACK"] == pytest.approx(RETURN_RB_DELTA_SPIKED * RETURN_Q_FACTOR)
    monkeypatch.setenv("RETURNING_RB_ADJ", "2")
    with pytest.raises(ValueError):
        returning_teammate_deltas(feats, prev, teams)
