from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from coherent_market_state_sources import (  # noqa: E402
    FORBIDDEN_QUERY_TOKENS,
    PLAYER_SQL,
    PROTOCOL,
    PROTOCOL_SHA256,
    SOURCE_SQL,
    SUPPORT,
    SUPPORT_SHA256,
    validate_local_sources,
)
from aggregate_coherent_market_state_scorefree import (  # noqa: E402
    _assert_no_outcomes,
    _validate_fold,
)
from nfl_dfs.analysis.coherent_market_state import (  # noqa: E402
    ADDITION_COUNT,
    ANCHOR_LIMIT,
    STATE_ORDER,
    VERSION,
    aggregate_heldout_gate,
    build_treatment_pool,
    evaluate_heldout_fold,
    generate_state_candidates,
    protocol_receipt,
    rank_eligible_teams,
)
from nfl_dfs.optimizer.lineup import Lineup, StackRules, optimize_many  # noqa: E402


def _pool() -> list[dict]:
    players = []
    opponents = {
        "A": "B", "B": "A", "C": "D",
        "D": "C", "E": "F", "F": "E",
    }
    player_index = 0
    for team_index, (team, opponent) in enumerate(opponents.items()):
        game = f"G{team_index // 2}"
        for pos, count in (
            ("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1), ("DST", 1),
        ):
            for position_index in range(count):
                projection = float(
                    30 - team_index - position_index
                    + {"QB": 5, "RB": 4, "WR": 3, "TE": 2, "DST": 1}[pos]
                )
                magnitude = float(6 - team_index) if pos != "DST" else 0.0
                players.append({
                    "id": f"p{player_index:02d}",
                    "name": f"{team}-{pos}-{position_index}",
                    "pos": pos,
                    "team": team,
                    "opp": opponent,
                    "game_id": game,
                    "salary": 5_500,
                    "proj": projection,
                    "mean_projection": projection,
                    "market_points": (
                        projection + magnitude if pos != "DST" else None
                    ),
                    "model_points_pre": (
                        projection - magnitude if pos != "DST" else None
                    ),
                })
                player_index += 1
    return players


def _native_candidate_universe(players: list[dict]) -> list[Lineup]:
    return [Lineup(players, tag="universe")]


def _draws(players: list[dict], worlds: int = 20):
    rng = np.random.default_rng(901)
    means = np.asarray([row["proj"] for row in players], dtype=np.float64)
    return {
        block: rng.normal(
            means[:, None], 7.0, size=(len(players), worlds),
        ).astype(np.float32)
        for block in ("R0", "R1", "R2", "R3")
    }


def test_team_ranking_is_covered_candidate_universe_and_stable() -> None:
    players = _pool()
    ranked = rank_eligible_teams(players, _native_candidate_universe(players))
    assert [row.team for row in ranked] == ["A", "B", "C"]
    assert [row.disagreement for row in ranked] == [36.0, 30.0, 24.0]
    assert all(len(row.covered_player_ids) == 7 for row in ranked)
    assert all(row.qb_id for row in ranked)


def test_generator_produces_frozen_six_by_two_novel_strict_candidates() -> None:
    players = _pool()
    player_ids = tuple(row["id"] for row in players)
    draws = _draws(players)
    teams = rank_eligible_teams(players, _native_candidate_universe(players))
    additions, receipts = generate_state_candidates(
        player_rows=players,
        player_ids=player_ids,
        row_draws_by_block=draws,
        training_blocks=("R0", "R1", "R2", "R3"),
        team_states=teams,
        forbidden_rosters=set(),
    )
    assert len(additions) == ADDITION_COUNT == 12
    assert len({tuple(sorted(row.lineup.ids)) for row in additions}) == 12
    assert [row.state for row in additions] == [
        state for _team in range(3) for state in STATE_ORDER for _ in range(2)
    ]
    assert all(1 <= row["anchor_rank"] <= ANCHOR_LIMIT for row in receipts)
    assert sum(row["accepted"] for row in receipts) == 12
    assert all(row.lineup.salary == 49_500 for row in additions)


def test_fixed_budget_removes_exactly_lowest_twelve_and_reselects_80() -> None:
    players = _pool()
    lineups = optimize_many(
        players,
        n_lineups=80,
        max_overlap=8,
        stack=StackRules(qb_stack_min=2, bring_back_min=1),
    )
    assert len(lineups) == 80
    player_ids = tuple(row["id"] for row in players)
    index = {value: row for row, value in enumerate(player_ids)}
    draws = _draws(players)
    totals = {
        block: np.asarray([
            matrix[[index[str(value)] for value in lineup.ids]].sum(axis=0)
            for lineup in lineups
        ], dtype=np.float32)
        for block, matrix in draws.items()
    }
    control = {
        "candidate_lineups": lineups,
        "candidate_totals_by_block": totals,
        "training_blocks": ["R0", "R1", "R2", "R3"],
        "candidate_source_aggregation": [{
            "sources": ["R0"], "tags": ["lev"],
        } for _ in lineups],
    }
    teams = rank_eligible_teams(players, _native_candidate_universe(players))
    additions, _ = generate_state_candidates(
        player_rows=players,
        player_ids=player_ids,
        row_draws_by_block=draws,
        training_blocks=("R0", "R1", "R2", "R3"),
        team_states=teams,
        forbidden_rosters={tuple(sorted(row.ids)) for row in lineups},
    )
    treatment = build_treatment_pool(control, additions)
    assert treatment["candidate_budget"] == 80
    assert len(treatment["removed"]) == 12
    assert treatment["addition_count"] == 12
    assert len(treatment["candidate_lineups"]) == 80
    assert len(treatment["selected_lineups"]) == 80
    ranks = [tuple(row["training_tail_rank"]) for row in treatment["removed"]]
    assert ranks == sorted(ranks)


def _fold(block: str, *, selected_gain: int = 2) -> dict:
    thresholds = (187, 194, 200, 210, 220, 230, 240)
    counts = {}
    for scope in ("candidate", "selected"):
        counts[scope] = {
            "control": {str(line): 100 for line in thresholds},
            "treatment": {
                str(line): (
                    95 if line == 194 else
                    100 + (selected_gain if line == 210 else 0)
                )
                for line in thresholds
            },
        }
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "mechanical_valid": True,
        "season": 2023,
        "week": 1,
        "heldout_block": block,
        "threshold_counts": counts,
        "structure": {
            "candidate": {},
            "selected": {
                "control": {
                    "unique_player_pairs": 100,
                    "unique_qb_stack_cores": 10,
                },
                "treatment": {
                    "unique_player_pairs": 90,
                    "unique_qb_stack_cores": 9,
                },
            },
        },
    }


def test_frozen_aggregate_gate_is_p210_first_and_structure_safe() -> None:
    result = aggregate_heldout_gate([_fold(block) for block in (
        "R0", "R1", "R2", "R3", "R4",
    )])
    assert result["passes_scorefree_gate"] is True
    assert result["disposition"] == "coherent-market-state-shadow-licensed"
    failed = [_fold(block, selected_gain=(2 if block in {"R0", "R1"} else 0))
              for block in ("R0", "R1", "R2", "R3", "R4")]
    assert aggregate_heldout_gate(failed)["passes_scorefree_gate"] is False


def test_protocol_and_source_queries_are_hash_bound_and_outcome_free() -> None:
    assert protocol_receipt() == {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "team_limit": 3,
        "state_order": ["model", "market"],
        "lineups_per_state": 2,
        "addition_count": 12,
        "anchor_limit": 64,
        "control_entries": 80,
        "heldout_folds": 5,
    }
    hashes = validate_local_sources()
    assert hashes[str(PROTOCOL)] == PROTOCOL_SHA256
    assert hashes[str(SUPPORT)] == SUPPORT_SHA256
    combined = f"{SOURCE_SQL}\n{PLAYER_SQL}".lower()
    assert not [token for token in FORBIDDEN_QUERY_TOKENS if token in combined]


def test_strict_fold_validator_accepts_complete_receipt_and_rejects_outcome() -> None:
    players = _pool()
    lineups = optimize_many(
        players,
        n_lineups=80,
        max_overlap=8,
        stack=StackRules(qb_stack_min=2, bring_back_min=1),
    )
    player_ids = tuple(row["id"] for row in players)
    index = {value: row for row, value in enumerate(player_ids)}
    rng = np.random.default_rng(1901)
    means = np.asarray([row["proj"] for row in players], dtype=np.float64)
    all_draws = {
        block: rng.normal(
            means[:, None], 7.0, size=(len(players), 10_000),
        ).astype(np.float32)
        for block in ("R0", "R1", "R2", "R3", "R4")
    }
    totals = {
        block: np.asarray([
            matrix[[index[str(value)] for value in lineup.ids]].sum(axis=0)
            for lineup in lineups
        ], dtype=np.float32)
        for block, matrix in all_draws.items() if block != "R4"
    }
    control = {
        "candidate_lineups": lineups,
        "candidate_totals_by_block": totals,
        "control_lineups": lineups,
        "training_blocks": ["R0", "R1", "R2", "R3"],
        "candidate_source_aggregation": [{
            "sources": ["R0"], "tags": ["lev"],
        } for _ in lineups],
        "player_ids": player_ids,
        "heldout_row_draws": all_draws["R4"],
    }
    teams = rank_eligible_teams(players, _native_candidate_universe(players))
    additions, generation = generate_state_candidates(
        player_rows=players,
        player_ids=player_ids,
        row_draws_by_block={
            block: all_draws[block] for block in ("R0", "R1", "R2", "R3")
        },
        training_blocks=("R0", "R1", "R2", "R3"),
        team_states=teams,
        forbidden_rosters={tuple(sorted(row.ids)) for row in lineups},
    )
    treatment = build_treatment_pool(control, additions)
    fold = evaluate_heldout_fold(
        control=control,
        treatment=treatment,
        additions=additions,
        heldout_block="R4",
        season=2023,
        week=1,
    )
    fold.update({
        "training_blocks": ["R0", "R1", "R2", "R3"],
        "team_states": [{
            "team": row.team,
            "disagreement": row.disagreement,
            "qb_id": row.qb_id,
            "covered_player_ids": list(row.covered_player_ids),
        } for row in teams],
        "generation": generation,
        "removed": treatment["removed"],
        "added": [{
            "team": row.team,
            "state": row.state,
            "state_index": row.state_index,
            "anchor_block": row.anchor_block,
            "anchor_world": row.anchor_world,
            "roster": sorted(row.lineup.ids),
        } for row in additions],
        "control_candidate_rosters": [sorted(row.ids) for row in lineups],
        "treatment_candidate_rosters": [
            sorted(row.ids) for row in treatment["candidate_lineups"]
        ],
        "control_selected_rosters": [sorted(row.ids) for row in lineups],
        "treatment_selected_rosters": [
            sorted(row.ids) for row in treatment["selected_lineups"]
        ],
    })
    _validate_fold(fold, 2023, 1, "R4")
    _assert_no_outcomes(fold)
    try:
        _assert_no_outcomes({**fold, "actual_score": 200.0})
    except ValueError as exc:
        assert "outcome field" in str(exc)
    else:
        raise AssertionError("coherent-state aggregate accepted an outcome")
