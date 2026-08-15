from __future__ import annotations

import json

import pandas as pd

from nfl_dfs.research.final_forensic_corpus import (
    corpus_understanding_diagnostics,
)


def _players() -> pd.DataFrame:
    rows = []
    positions = ["QB", *(["WR"] * 16)]
    for week in range(1, 11):
        for index, position in enumerate(positions):
            rows.append({
                "season": 2025,
                "week": week,
                "id": f"p{index}",
                "name": f"Player {index}",
                "pos": position,
                "team": "A" if index < 9 else "B",
                "opp": "B" if index < 9 else "A",
                "game_id": "B@A",
                "salary": 4_000 + index * 100,
                "own_est": 5.0 + index,
            })
    return pd.DataFrame(rows)


def _candidates() -> pd.DataFrame:
    rows = []
    for week in range(1, 11):
        for index in range(30):
            second = [f"p{value}" for value in range(1, 9)] \
                if index % 2 == 0 else [f"p{value}" for value in range(9, 17)]
            actual = 215.0 if index % 10 == 0 else 150.0 + index
            rows.append({
                "panel_run_id": "panel",
                "season": 2025,
                "week": week,
                "cand_ix": index,
                "players": ",".join(["p0", *second]),
                "selected": index < 5,
                "selected_rank": index + 1 if index < 5 else None,
                "actual_score": actual,
                "salary": 46_000 if index % 2 == 0 else 49_000,
                "tag": "boom" if index % 2 == 0 else "base",
                "p_line": index / 30,
                "sim_mean": 130.0 + index,
                "sim_sd": 20.0,
                "sim_q50": 130.0 + index,
                "sim_q90": 160.0 + index,
                "sim_q99": 190.0 + index,
                "sim_rank_p_line": 30 - index,
            })
    return pd.DataFrame(rows)


def test_corpus_understanding_runs_all_five_descriptive_views():
    report = corpus_understanding_diagnostics(_candidates(), _players())

    assert report["contract"]["candidate_rows"] == 300
    assert "may not promote" in report["contract"]["use_restriction"]
    assert report["subgroup_discovery"]["unselected_ge200"]["positive_rows"] > 0
    assert report["weak_interpretable_model"]["holdout_rows"] == 60
    assert report["weak_interpretable_model"]["tree_shap_feature_importance"]
    assert report["co_selection_graphs"]["high_score_pair_lift"]
    assert report["lineup_space_embedding"]["sample_rows"] == 300
    assert report["lineup_space_embedding"]["points"]
    assert "selection_regret" in report["changepoints"]["metrics"]
    json.dumps(report, allow_nan=False)
