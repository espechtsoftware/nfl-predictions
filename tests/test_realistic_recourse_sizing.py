import json

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.realistic_recourse_sizing import (
    combine_seed_player_worlds,
    decision_instant,
    derive_game_statuses,
    freeze_proposals,
    roster_swap_distance,
    validate_forensic_parity,
)


def test_decision_instant_is_frozen_eastern_wall_clock():
    stamp = decision_instant("2024-11-03")
    assert stamp.isoformat() == "2024-11-03T15:55:00-05:00"


def test_game_status_uses_latest_visible_terminal_row_and_preserves_tie():
    schedules = pd.DataFrame([
        {"game_id": "final", "kickoff_utc": "2024-09-08T17:00:00Z"},
        {"game_id": "tie", "kickoff_utc": "2024-09-08T17:00:00Z"},
        {"game_id": "late", "kickoff_utc": "2024-09-08T20:25:00Z"},
    ])
    pbp = pd.DataFrame([
        {
            "game_id": "final", "time_of_day": "2024-09-08T19:50:00Z",
            "play_id": 1, "qtr": 4, "game_seconds_remaining": 0,
            "total_home_score": 20, "total_away_score": 17, "desc": "kneel",
        },
        {
            "game_id": "tie", "time_of_day": "2024-09-08T19:51:00Z",
            "play_id": 2, "qtr": 4, "game_seconds_remaining": 0,
            "total_home_score": 20, "total_away_score": 20, "desc": "end quarter",
        },
    ])
    statuses, receipt = derive_game_statuses(
        schedules, pbp, as_of="2024-09-08T15:55:00-04:00",
    )
    by_game = statuses.set_index("game_id").game_status.to_dict()
    assert by_game == {
        "final": "final", "late": "not_started", "tie": "in_progress",
    }
    assert receipt["uses_schedule_final_score"] is False


def test_overtime_zero_is_terminal():
    schedules = pd.DataFrame([
        {"game_id": "ot", "kickoff_utc": "2024-09-08T17:00:00Z"},
    ])
    pbp = pd.DataFrame([{
        "game_id": "ot", "time_of_day": "2024-09-08T19:54:00Z",
        "play_id": 9, "qtr": 5, "game_seconds_remaining": 0,
        "total_home_score": 20, "total_away_score": 20, "desc": "end overtime",
    }])
    statuses, _ = derive_game_statuses(
        schedules, pbp, as_of="2024-09-08T15:55:00-04:00",
    )
    assert statuses.iloc[0].game_status == "final"


def test_untimed_end_game_is_excluded_not_treated_as_terminal():
    schedules = pd.DataFrame([
        {"game_id": "tie", "kickoff_utc": "2024-09-08T17:00:00Z"},
    ])
    pbp = pd.DataFrame([
        {
            "game_id": "tie", "time_of_day": "2024-09-08T19:51:00Z",
            "play_id": 1, "qtr": 4, "game_seconds_remaining": 0,
            "total_home_score": 20, "total_away_score": 20, "desc": "end quarter",
        },
        {
            "game_id": "tie", "time_of_day": None,
            "play_id": 2, "qtr": 5, "game_seconds_remaining": 0,
            "total_home_score": 20, "total_away_score": 20, "desc": "END GAME",
        },
    ])
    statuses, receipt = derive_game_statuses(
        schedules, pbp, as_of="2024-09-08T15:55:00-04:00",
    )
    assert statuses.iloc[0].game_status == "in_progress"
    assert receipt["untimed_rows_excluded"] == 1
    assert receipt["untimed_terminal_text_rows_excluded"] == 1
    assert receipt["untimed_rows_never_used_as_terminal"] is True


def test_combined_seed_worlds_aligns_player_order_and_records_assumption():
    artifacts = {}
    receipts = {}
    for seed in range(5):
        ids = np.array(["b", "a"] if seed % 2 else ["a", "b"])
        first = np.full(10_000, seed + 1, dtype=np.float32)
        second = np.full(10_000, seed + 11, dtype=np.float32)
        draws = np.vstack([first, second])
        artifacts[seed] = {"player_ids": ids, "player_draws": draws}
        receipts[seed] = {
            "uri": f"gs://bucket/r{seed}.npz", "sha256": str(seed) * 64,
            "generation": str(seed + 1),
            "updated": "2026-08-15T00:00:00Z",
            "size": 123,
            "panel_run_id": f"panel-r{seed}",
        }
    artifact, receipt = combine_seed_player_worlds(
        artifacts, receipts,
        counterfactual_generated_at="2024-09-08T12:55:00-04:00",
    )
    assert artifact["player_ids"].tolist() == ["a", "b"]
    assert artifact["player_draws"].shape == (2, 50_000)
    assert receipt["historical_counterfactual_availability"] is True
    assert len(receipt["combined_sha256"]) == 64
    assert receipt["sources"][0]["generation"] == "1"
    assert receipt["sources"][0]["panel_run_id"] == "panel-r0"


def test_freeze_proposals_requires_54_and_rejects_outcomes():
    proposals = [
        {"season": 2023 + index // 18, "week": index % 18 + 1, "assignments": {}}
        for index in range(54)
    ]
    frozen = freeze_proposals(proposals)
    assert frozen["slates"] == 54
    assert frozen["outcomes_opened"] is False
    contaminated = [dict(row) for row in proposals]
    contaminated[0]["actual_score"] = 1
    with pytest.raises(ValueError, match="forbidden outcome"):
        freeze_proposals(contaminated)


def test_freeze_proposals_normalizes_numpy_scalars_before_upload():
    proposals = [
        {
            "season": np.int64(2023 + index // 18),
            "week": np.int64(index % 18 + 1),
            "receipt": {
                "rows": np.int64(index),
                "score": np.float64(index / 10),
                "valid": np.bool_(True),
            },
        }
        for index in range(54)
    ]
    frozen = freeze_proposals(proposals)
    first = frozen["proposals"][0]
    assert type(first["season"]) is int
    assert type(first["receipt"]["rows"]) is int
    assert type(first["receipt"]["score"]) is float
    assert type(first["receipt"]["valid"]) is bool
    assert len(frozen["proposal_set_sha256"]) == 64
    json.dumps(frozen, allow_nan=False)


def test_swap_distance_counts_player_replacements():
    assert roster_swap_distance(range(9), [0, 1, 2, 3, 4, 5, 6, 20, 21]) == 2


def test_forensic_parity_receipt_hashes_candidate_and_selected_identities():
    rosters = [",".join(f"p{index}-{slot}" for slot in range(9)) for index in range(80)]
    reconstructed = pd.DataFrame({
        "players": rosters,
        "selected": [True] * 80,
        "selected_rank": list(range(80)),
    })
    forensic = pd.DataFrame({
        "roster_key": [",".join(sorted(value.split(","))) for value in rosters],
        "selected": [True] * 80,
        "selected_rank": list(range(80)),
    })
    receipt = validate_forensic_parity(reconstructed, forensic)
    assert len(receipt["candidate_identity_sha256"]) == 64
    assert len(receipt["selected_order_sha256"]) == 64
    assert receipt["candidate_identity_parity"] is True
