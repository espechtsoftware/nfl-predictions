import csv

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import sis_asoe_allocation as allocation
from nfl_dfs.analysis.usage_dirichlet_calibration import UsageGroup
from nfl_dfs.ingest import fantasy_points_alignment_l4 as alignment
from nfl_dfs.ingest import sis_asoe


def _write_alignment(path, season):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "Player Details", "", "", "", "", "", "Overall",
            "Wide", "Slot", "Inline", "Backfield",
        ])
        writer.writerow([
            "Rank", "Name", "Team", "POS", "G", "Season", "RTE",
            "RTE", "RTE", "RTE", "RTE",
        ])
        writer.writerow([
            1, "Wide Receiver", "HST", "WR", 4, season, 100,
            70, 20, 10, "",
        ])
        writer.writerow([
            2, "Slot Receiver", "HST", "WR", 4, season, 80,
            10, 60, 10, "",
        ])


def test_alignment_parser_builds_player_and_team_profiles(tmp_path):
    artifacts = {}
    for season in alignment.SEASONS:
        path = tmp_path / f"alignment-{season}.csv"
        _write_alignment(path, season)
        for target_week in alignment.TARGET_WEEKS:
            artifacts[(season, target_week)] = {
                "local_path": path,
                "path": path.name,
                "sha256": f"hash-{season}",
            }
    snapshots = pd.DataFrame([
        {"season": season, "gsis_id": "wr-wide", "name": "Wide Receiver",
         "pos": "WR", "team": "HOU"}
        for season in alignment.SEASONS
    ] + [
        {"season": season, "gsis_id": "wr-slot", "name": "Slot Receiver",
         "pos": "WR", "team": "HOU"}
        for season in alignment.SEASONS
    ])
    players, teams, audit = alignment.read_windows(
        {"run_id": "alignment-run"}, artifacts, snapshots,
    )
    assert len(players) == 112
    assert audit["supported_player_rows"] == 112
    first = players[players.gsis_id.eq("wr-wide")].iloc[0]
    assert first.player_wide_share == 70 / 90
    team = teams.iloc[0]
    assert team.wide_slot_routes == 160
    assert team.offense_wide_share == 80 / 160
    assert team.offense_alignment_supported


def test_defense_asoe_reconstructs_zero_alignment_cells_from_schedule():
    schedule = pd.DataFrame([
        {"season": 2025, "week": week, "team": "ARI", "opponent": "HOU"}
        for week in range(1, 5)
    ])
    attempts = pd.DataFrame([
        {"season": 2025, "week": week, "defense": "ARI",
         "offense": "HOU", "alignment": "wide", "attempts": 12}
        for week in range(1, 5)
    ] + [
        {"season": 2025, "week": week, "defense": "ARI",
         "offense": "HOU", "alignment": "slot", "attempts": 8}
        for week in range(1, 4)
    ])
    offense = pd.DataFrame([{
        "season": 2025, "target_week": 5, "team": "HOU",
        "offense_wide_share": 0.50, "offense_alignment_supported": True,
    }])
    output, audit = sis_asoe.build_defense_asoe(attempts, offense, schedule)
    row = output.iloc[0]
    assert row.combined_attempts == 72
    assert row.observed_wide_share == 48 / 72
    assert row.expected_wide_share == 0.50
    assert row.defense_asoe == (48 / 72 - 0.50) * 72 / 112
    assert audit["structural_zero_cells_reconstructed"] == 1


def test_sis_attempt_reader_accepts_vendor_zero_even_with_minimum_one(tmp_path):
    # The site can return a displayed zero after applying its serialized
    # minimum-attempt value of one; zero remains a valid opportunity count.
    assert sis_asoe.MIN_DEFENSE_ATTEMPTS == 40.0


def test_allocation_tilt_preserves_simplex_and_favors_positive_score():
    p = np.array([0.6, 0.3, 0.1])
    score = np.array([0.2, -0.1, 0.0])
    q = allocation.tilt_probabilities(p, score, 3.0, valid=True)
    assert q.sum() == pytest.approx(1.0)
    assert (q > 0).all()
    assert q[0] > p[0]
    assert q[1] < p[1]
    np.testing.assert_array_equal(
        allocation.tilt_probabilities(p, score, 3.0, valid=False), p)


def test_group_geometry_uses_opponent_asoe_and_player_alignment():
    group = UsageGroup(
        season=2025, week=5, team="HOU", kind="targets",
        players=("wide", "slot", "rb"),
        probabilities=np.array([0.45, 0.35, 0.20]),
        observed=np.array([8, 5, 3]),
    )
    players = pd.DataFrame([
        {"season": 2025, "target_week": 5, "team": "HOU",
         "gsis_id": "wide", "alignment_supported": True,
         "player_wide_share": 0.8},
        {"season": 2025, "target_week": 5, "team": "HOU",
         "gsis_id": "slot", "alignment_supported": True,
         "player_wide_share": 0.2},
    ])
    offense = pd.DataFrame([{
        "season": 2025, "target_week": 5, "team": "HOU",
        "offense_alignment_supported": True, "offense_wide_share": 0.5,
    }])
    defense = pd.DataFrame([{
        "season": 2025, "target_week": 5, "defense": "ARI",
        "asoe_supported": True, "defense_asoe": 0.1,
    }])
    result = allocation.group_geometry(
        group, players, offense, defense, "ARI")
    assert result.valid
    assert result.supported_probability_mass == 0.8
    np.testing.assert_allclose(result.scores, [0.03, -0.03, 0.0])
