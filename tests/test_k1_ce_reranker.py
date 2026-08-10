from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import numpy as np
import pandas as pd


SPEC = spec_from_file_location(
    "evaluate_k1_ce_reranker",
    Path(__file__).parents[1] / "scripts" / "evaluate_k1_ce_reranker.py")
assert SPEC and SPEC.loader
reranker = module_from_spec(SPEC)
SPEC.loader.exec_module(reranker)


def test_structure_features_include_ce_and_stack_shape():
    candidates = pd.DataFrame([{
        "season": 2025, "week": 1, "cand_ix": 0,
        "players": "q,w,o", "all_tags": '["ce","lev"]',
        "actual_score": 200.0, "sim_mean": 150.0, "sim_sd": 20.0,
        "sim_q50": 149.0, "sim_q90": 178.0, "sim_q99": 205.0,
        "p_line": 0.04, "salary": 49_500,
    }])
    players = pd.DataFrame([
        {"season": 2025, "week": 1, "id": "q", "pos": "QB",
         "team": "A", "opp": "B", "game_id": "A@B"},
        {"season": 2025, "week": 1, "id": "w", "pos": "WR",
         "team": "A", "opp": "B", "game_id": "A@B"},
        {"season": 2025, "week": 1, "id": "o", "pos": "WR",
         "team": "B", "opp": "A", "game_id": "A@B"},
    ])
    frame = reranker.build_structure_features(candidates, players)
    assert frame.loc[0, "tag_ce"] == 1
    assert frame.loc[0, "n_tags"] == 2
    assert frame.loc[0, "stack_mates"] == 1
    assert frame.loc[0, "bring_back"] == 1
    assert frame.loc[0, "max_from_game"] == 3
    assert frame.loc[0, "salary_left"] == 500


def test_walk_forward_shifts_never_train_on_served_or_future_season():
    rows = []
    for season in (2019, 2021, 2022):
        for ix in range(6):
            row = {name: float(ix + 1) for name in reranker.FEATURES}
            row.update({
                "season": season, "week": 1, "cand_ix": ix,
                "actual_score": 100.0 + ix + season % 10,
                "sim_mean": 90.0 + ix,
            })
            rows.append(row)
    frame = pd.DataFrame(rows)
    shifts, manifest = reranker.walk_forward_shifts(frame)
    assert shifts[frame.season.eq(2019)].eq(0).all()
    for served in manifest:
        assert all(year < served["season"] for year in served["train_seasons"])
    assert shifts.abs().max() <= reranker.SHIFT_CAP


def test_shifted_selector_changes_world_support_before_selection():
    totals = np.array([
        [195.0, 180.0, 180.0],
        [180.0, 195.0, 180.0],
        [193.0, 193.0, 193.0],
    ])
    baseline = reranker.select_shifted(totals, np.zeros(3), n_entries=1)
    shifted = reranker.select_shifted(totals, np.array([0.0, 0.0, 2.0]),
                                       n_entries=1)
    assert baseline == [0]
    assert shifted == [2]


def _book(scores):
    scores = list(scores) + [180.0] * (107 - len(scores))
    return pd.DataFrame({
        "season": list(range(107)),
        "week": [1] * 107,
        "selected_best": scores,
        "oracle": [230.0] * 107,
        "n_candidates": [240] * 107,
        "n_selected": [80] * 107,
    })


def test_reranker_gate_is_tail_first_and_requires_negative_control_win():
    source = _book([199.0, 199.0, 211.0, 180.0])
    primary = _book([201.0, 202.0, 211.0, 180.0])
    shuffled = _book([201.0, 199.0, 211.0, 180.0])
    gate = reranker.reranker_gate(source, primary, shuffled, [])
    assert gate["clear_200_lift_at_least_2"]
    assert gate["clear_210_not_worse"]
    assert gate["beats_shuffled_control"]
    assert gate["passes"]


def test_reranker_gate_rejects_shuffled_tie():
    source = _book([199.0, 199.0, 211.0, 180.0])
    primary = _book([201.0, 202.0, 211.0, 180.0])
    gate = reranker.reranker_gate(source, primary, primary.copy(), [])
    assert not gate["beats_shuffled_control"]
    assert not gate["passes"]
