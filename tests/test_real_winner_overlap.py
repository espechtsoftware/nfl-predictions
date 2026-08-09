import numpy as np
import pandas as pd

from nfl_dfs.research.real_winner_overlap import (
    evaluate_known_winner_overlap,
    match_known_winner_players,
)


def test_match_known_winners_handles_initial_flex_dst_and_bad_first_name():
    winners = pd.DataFrame([
        {"season": 2023, "week": 1, "winner_name": "C. Runner",
         "winner_pos": "FLEX", "salary": 5000, "winner_actual": 20.0},
        {"season": 2023, "week": 1, "winner_name": "Vikings",
         "winner_pos": "DST", "salary": 3000, "winner_actual": 12.0},
        # Source has the wrong first name; salary/actual resolve Brian.
        {"season": 2023, "week": 1, "winner_name": "Bijan Robinson",
         "winner_pos": "RB", "salary": 5800, "winner_actual": 20.1},
    ])
    features = pd.DataFrame([
        {"season": 2023, "week": 1, "id": "rb1", "name": "Chris Runner",
         "pos": "RB", "team": "X", "salary": 5000, "actual": 20.0,
         "proj": 10.0, "mean_projection": 11.0},
        {"season": 2023, "week": 1, "id": "dst1", "name": "MIN DST",
         "pos": "DST", "team": "MIN", "salary": 3000, "actual": 12.0,
         "proj": 6.0, "mean_projection": np.nan},
        {"season": 2023, "week": 1, "id": "rb2", "name": "Brian Robinson",
         "pos": "RB", "team": "WAS", "salary": 5800, "actual": 20.2,
         "proj": 12.0, "mean_projection": 13.0},
    ])
    # The production contract validates nine IDs; repeat six unrelated rows
    # to exercise resolution separately while retaining a legal roster size.
    extras = []
    for ix in range(6):
        extras.append({
            "season": 2023, "week": 1, "winner_name": f"Extra {ix}",
            "winner_pos": "WR", "salary": 4000 + ix,
            "winner_actual": float(ix),
        })
        features.loc[len(features)] = {
            "season": 2023, "week": 1, "id": f"wr{ix}",
            "name": f"Extra {ix}", "pos": "WR", "team": "Y",
            "salary": 4000 + ix, "actual": float(ix), "proj": 5.0,
            "mean_projection": 5.5,
        }
    matched = match_known_winner_players(
        pd.concat([winners, pd.DataFrame(extras)], ignore_index=True), features)
    assert matched.id.head(3).tolist() == ["rb1", "dst1", "rb2"]
    assert matched.projection.head(3).tolist() == [11.0, 6.0, 13.0]


def test_winner_overlap_is_deterministic_and_reports_missing_player():
    winner_ids = [f"p{ix}" for ix in range(9)]
    winners = pd.DataFrame({
        "season": [2025] * 9, "week": [1] * 9, "id": winner_ids,
        "name": winner_ids, "pos": ["WR"] * 9,
        "snapshot_actual": np.arange(9, dtype=float),
        "projection": np.ones(9),
    })
    candidates = pd.DataFrame([
        {"season": 2025, "week": 1, "cand_ix": 0,
         "players": "p0,p1,p2,x0,x1,x2,x3,x4,x5", "selected": True,
         "actual_score": 100.0},
        {"season": 2025, "week": 1, "cand_ix": 1,
         "players": "p3,p4,p5,x0,x1,x2,x3,x4,x5", "selected": True,
         "actual_score": 110.0},
        {"season": 2025, "week": 1, "cand_ix": 2,
         "players": "p0,p3,p6,x0,x1,x2,x3,x4,x5", "selected": False,
         "actual_score": 120.0},
        # p7 is exposed, while p8 is absent from the entire pool.
        {"season": 2025, "week": 1, "cand_ix": 3,
         "players": "p1,p4,p7,x0,x1,x2,x3,x4,x5", "selected": False,
         "actual_score": 90.0},
    ])
    report, missing = evaluate_known_winner_overlap(
        candidates, winners, seed=7, null_reps=100)
    again, _ = evaluate_known_winner_overlap(
        candidates, winners, seed=7, null_reps=100)
    pd.testing.assert_frame_equal(report, again)
    pool = report[report.book == "pool"].iloc[0]
    selected = report[report.book == "selected"].iloc[0]
    assert pool.winner_player_coverage == 8
    assert pool.max_overlap == 3
    assert selected.winner_player_coverage == 6
    assert selected.selected_best_overlap == 3
    assert pool.oracle_overlap == 3
    assert not pool.exact_winner_in_pool
    assert missing[["id", "actual", "projection"]].to_dict("records") == [
        {"id": "p8", "actual": 8.0, "projection": 1.0}]
