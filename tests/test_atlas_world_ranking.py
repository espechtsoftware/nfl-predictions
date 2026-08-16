import numpy as np
import pytest

from nfl_dfs.analysis import atlas_world_ranking as atlas
from nfl_dfs.optimizer.lineup import Lineup, StackRules


def _positions():
    return [
        "QB", "QB", "RB", "RB", "RB", "WR", "WR", "WR", "WR", "TE",
        "TE", "DST", "DST",
    ]


def test_roster_slot_bound_uses_best_valid_position_shape():
    positions = _positions()
    # One world. The top 1 QB, 1 DST, 2 RB, 4 WR and 1 TE is the best
    # slot-count shape here: 20 + 4 + (9+8) + (7+6+5+4) + 3 = 66.
    draws = np.array([
        [20], [10], [9], [8], [1], [7], [6], [5], [4], [3], [2], [4], [1],
    ], dtype=float)
    result = atlas.roster_slot_upper_bound(draws, positions)
    assert result.tolist() == [66.0]


def test_attainable_rank_can_disagree_with_whole_slate_rank_score_free():
    positions = _positions()
    draws = np.zeros((len(positions), 3), dtype=float)
    # World 0 has diffuse points on every player and wins the whole-slate
    # sum. World 1 concentrates points into one roster and wins the bound.
    draws[:, 0] = 10.0
    draws[[0, 2, 3, 5, 6, 7, 8, 9, 11], 1] = 13.0
    draws[:, 2] = 1.0

    result = atlas.compare_world_rankings(draws, positions, n_worlds=1)

    assert result["incumbent_world_ids"] == [0]
    assert result["attainable_world_ids"] == [1]
    assert result["shared_worlds"] == 0
    assert result["uses_realized_outcomes"] is False


def test_world_rank_is_stable_on_ties_and_inputs_fail_closed():
    assert atlas.rank_worlds(np.array([2.0, 3.0, 3.0]), 2).tolist() == [1, 2]
    with pytest.raises(ValueError, match="finite"):
        atlas.rank_worlds(np.array([1.0, np.nan]), 1)
    with pytest.raises(ValueError, match="at least 4"):
        atlas.roster_slot_upper_bound(
            np.ones((8, 2)), ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "DST"]
        )


def test_complete_diagnostic_exactly_solves_only_ranking_union(monkeypatch):
    positions = _positions()
    draws = np.zeros((len(positions), 3), dtype=float)
    draws[:, 0] = 10.0
    roster_rows = [0, 2, 3, 5, 6, 7, 8, 9, 11]
    draws[roster_rows, 1] = 13.0
    draws[:, 2] = 1.0
    players = []
    for index, pos in enumerate(positions):
        team = "A" if index in {0, 2, 5, 6, 9} else "B"
        players.append({
            "id": index,
            "pos": pos,
            "team": team,
            "opp": "B" if team == "A" else "A",
            "game_id": "A@B",
            "salary": 5_000,
            "proj": 10.0,
        })
    calls = []

    def fake_optimize(world_players, **kwargs):
        calls.append(kwargs["objective_col"])
        chosen = sorted(
            world_players,
            key=lambda player: player["atlas_world_score"],
            reverse=True,
        )[:9]
        # Preserve exactly one QB for the structure receipt.
        if sum(player["pos"] == "QB" for player in chosen) != 1:
            chosen = [world_players[0], *[
                player for player in chosen if player["pos"] != "QB"
            ][:8]]
        return Lineup(chosen)

    monkeypatch.setattr(atlas, "optimize", fake_optimize)
    report = atlas.complete_world_ranking_diagnostic(
        players,
        draws,
        stack=StackRules(qb_stack_min=2, bring_back_min=1),
        env={"MIN_LINEUP_SALARY": "49000"},
        n_worlds=1,
    )

    assert report["exact_union_worlds"] == 2
    assert calls == ["atlas_world_score", "atlas_world_score"]
    assert report["attainable_exact"]["mean_exact_legal_optimum"] > (
        report["incumbent_exact"]["mean_exact_legal_optimum"]
    )
    assert report["uses_realized_outcomes"] is False


def test_frozen_scorefree_gate_requires_five_stable_seeds():
    rows = []
    for seed in range(5):
        rows.append({
            "seed": seed, "season": 2025, "week": 1,
            "uses_realized_outcomes": False,
            "incumbent_exact": {
                "mean_exact_legal_optimum": 200.0,
                "q25_exact_legal_optimum": 190.0,
                "unique_exact_rosters": 20,
                "unique_qb_stack_cores": 10,
                "unique_dominant_games": 8,
            },
            "attainable_exact": {
                "mean_exact_legal_optimum": 201.0,
                "q25_exact_legal_optimum": 190.5,
                "unique_exact_rosters": 18,
                "unique_qb_stack_cores": 9,
                "unique_dominant_games": 7,
            },
        })
    result = atlas.aggregate_scorefree_gate(rows)
    assert result["passes_scorefree_falsifier"]
    assert result["rows"] == 5
    rows[0]["uses_realized_outcomes"] = True
    with pytest.raises(ValueError, match="outcome-facing"):
        atlas.aggregate_scorefree_gate(rows)


def _gate_rows():
    return [{
        "seed": seed, "season": 2025, "week": 1,
        "uses_realized_outcomes": False,
        "incumbent_exact": {
            "mean_exact_legal_optimum": 200.0,
            "q25_exact_legal_optimum": 190.0,
            "unique_exact_rosters": 20,
            "unique_qb_stack_cores": 10,
            "unique_dominant_games": 8,
        },
        "attainable_exact": {
            "mean_exact_legal_optimum": 201.0,
            "q25_exact_legal_optimum": 190.5,
            "unique_exact_rosters": 18,
            "unique_qb_stack_cores": 9,
            "unique_dominant_games": 7,
        },
    } for seed in range(5)]


@pytest.mark.parametrize("condition", [
    "aggregate_mean_improves",
    "at_least_three_seed_means_improve",
    "aggregate_q25_nonworse",
    "roster_diversity_at_least_80pct",
    "stack_core_diversity_at_least_80pct",
    "dominant_game_diversity_at_least_80pct",
])
def test_each_frozen_gate_condition_can_fail(condition):
    rows = _gate_rows()
    if condition == "aggregate_mean_improves":
        for index, row in enumerate(rows):
            row["attainable_exact"]["mean_exact_legal_optimum"] = (
                201.0 if index < 3 else 198.0
            )
    elif condition == "at_least_three_seed_means_improve":
        for index, row in enumerate(rows):
            row["attainable_exact"]["mean_exact_legal_optimum"] = (
                203.0 if index < 2 else 200.0
            )
    elif condition == "aggregate_q25_nonworse":
        for row in rows:
            row["attainable_exact"]["q25_exact_legal_optimum"] = 189.5
    elif condition == "roster_diversity_at_least_80pct":
        for row in rows:
            row["attainable_exact"]["unique_exact_rosters"] = 15
    elif condition == "stack_core_diversity_at_least_80pct":
        for row in rows:
            row["attainable_exact"]["unique_qb_stack_cores"] = 7
    else:
        for row in rows:
            row["attainable_exact"]["unique_dominant_games"] = 6
    result = atlas.aggregate_scorefree_gate(rows)
    assert result["conditions"][condition] is False
    assert not result["passes_scorefree_falsifier"]


def test_gate_rejects_nonfinite_aggregate_metric():
    rows = _gate_rows()
    rows[0]["attainable_exact"]["mean_exact_legal_optimum"] = float("nan")
    with pytest.raises(ValueError, match="must be finite"):
        atlas.aggregate_scorefree_gate(rows)
