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
    """Lab review 2026-09-19: (a) a depth-2 + depth-3 team with NO depth-1 row is unknown, nothing gated;
    (b) blank-team rows are never grouped together; (c) a Questionable primary makes the team ambiguous."""
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
    assert "NYJ3" not in got and "NYJ2" not in got, "no depth-1 row: unknown, nothing gated"
    assert "BLANK2" not in got, "blank teams are not grouped"
    assert "CHI2" not in got and "CHI3" not in got, "Questionable primary: ambiguous, nothing gated"
    # MIA's Doubtful starter is gated under the 2026-09-22 refinement; Q is still ambiguous.
    assert got == ["ATL3", "MIA1"], got


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
