from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from aggregate_stack_core_shell_production_locks import validate_lock  # noqa: E402

from nfl_dfs.analysis.stack_core_shell import (
    BEAM_LIMIT,
    CORE_LIMIT,
    PROPOSAL_LIMIT,
    SHELL_LIMIT,
    VERSION,
    admit_and_select_treatment,
    aggregate_gate,
    build_component_library,
    build_production_form,
    construct_recombinant_proposals,
    enumerate_core_shells,
    production_form_receipt,
)
from nfl_dfs.optimizer.lineup import Lineup
from nfl_dfs.backtest.engine import CandidateBatch


def _player(
    player_id: str,
    pos: str,
    salary: int,
    team: str,
    opp: str,
    game: str,
) -> dict:
    return {
        "id": player_id,
        "name": player_id,
        "pos": pos,
        "salary": salary,
        "team": team,
        "opp": opp,
        "game_id": game,
    }


def _strict_lineup(index: int) -> Lineup:
    prefix = f"P{index:03d}"
    players = [
        _player(f"{prefix}-QB", "QB", 7000, f"A{index}", f"B{index}", f"AB{index}"),
        _player(f"{prefix}-A1", "WR", 6000, f"A{index}", f"B{index}", f"AB{index}"),
        _player(f"{prefix}-A2", "WR", 5500, f"A{index}", f"B{index}", f"AB{index}"),
        _player(f"{prefix}-B1", "WR", 5500, f"B{index}", f"A{index}", f"AB{index}"),
        _player(f"{prefix}-RB1", "RB", 6000, f"C{index}", f"D{index}", f"CD{index}"),
        _player(f"{prefix}-RB2", "RB", 5500, f"E{index}", f"F{index}", f"EF{index}"),
        _player(f"{prefix}-WR", "WR", 5000, f"G{index}", f"H{index}", f"GH{index}"),
        _player(f"{prefix}-TE", "TE", 4500, f"I{index}", f"J{index}", f"IJ{index}"),
        _player(f"{prefix}-DST", "DST", 4000, f"K{index}", f"L{index}", f"KL{index}"),
    ]
    return Lineup(players, tag="lev")


def _library_fixture() -> tuple[
    list[Lineup], tuple[str, ...], dict[str, np.ndarray], list[dict]
]:
    lineups = [_strict_lineup(index) for index in range(SHELL_LIMIT)]
    blocks = ("R0", "R1", "R2", "R3")
    totals = {
        block: np.asarray([
            np.linspace(180 + index / 100, 240 + index / 100, 10)
            for index in range(len(lineups))
        ], dtype=np.float32)
        for block in blocks
    }
    players = [row for lineup in lineups for row in lineup.players]
    return lineups, blocks, totals, players


def test_enumerates_strict_core_and_complementary_shell() -> None:
    decomposition = enumerate_core_shells(_strict_lineup(0))
    assert len(decomposition) == 1
    assert len(decomposition[0]["core"]) == 4
    assert len(decomposition[0]["shell"]) == 5
    assert not set(decomposition[0]["core"]) & set(decomposition[0]["shell"])


def test_component_library_enforces_frozen_counts_and_caps() -> None:
    lineups, blocks, totals, _ = _library_fixture()
    result = build_component_library(lineups, totals, blocks)
    assert result["version"] == VERSION
    assert result["uses_realized_outcomes"] is False
    assert len(result["cores"]) == CORE_LIMIT
    assert len(result["shells"]) == SHELL_LIMIT
    assert max(result["core_qb_counts"].values()) <= 4
    assert max(result["core_game_counts"].values()) <= 8


def test_recombination_builds_fixed_beam_and_budget_neutral_admission() -> None:
    lineups, blocks, totals, players = _library_fixture()
    library = build_component_library(lineups, totals, blocks)
    player_ids = [row["id"] for row in players]
    draws = np.asarray([
        np.linspace(18.0 + index / 10000, 32.0 + index / 10000, 10)
        for index in range(len(players))
    ], dtype=np.float32)
    worlds = {block: draws + offset for offset, block in enumerate(blocks)}
    proposals = construct_recombinant_proposals(
        player_rows=players,
        player_ids=player_ids,
        row_draws_by_block=worlds,
        blocks=blocks,
        control_lineups=lineups,
        library=library,
    )
    assert len(proposals["beam"]) == BEAM_LIMIT
    assert len(proposals["proposals"]) == PROPOSAL_LIMIT
    assert proposals["covered_core_shell_pairs"] >= 20
    assert all(
        set(row.core).isdisjoint(row.shell) and len(row.lineup.ids) == 9
        for row in proposals["proposals"]
    )

    treatment = admit_and_select_treatment(
        control_lineups=lineups,
        control_totals_by_block=totals,
        proposals=proposals["proposals"],
        blocks=blocks,
    )
    assert treatment["candidate_budget"] == len(lineups)
    assert len(treatment["candidate_lineups"]) == len(lineups)
    assert len(treatment["selected_lineups"]) == 80


def test_production_form_uses_all_five_blocks_and_exact_80() -> None:
    lineups, _blocks, _totals, players = _library_fixture()
    player_ids = tuple(row["id"] for row in players)
    base_draws = np.asarray([
        np.linspace(18.0 + index / 10000, 32.0 + index / 10000, 10)
        for index in range(len(players))
    ], dtype=np.float32)
    roster_rows = np.asarray([
        [player_ids.index(str(value)) for value in lineup.ids]
        for lineup in lineups
    ], dtype=np.int64)
    books = {}
    for index, block in enumerate(("R0", "R1", "R2", "R3", "R4")):
        draws = base_draws + index
        books[block] = CandidateBatch(
            candidates=tuple(lineups),
            candidate_totals=draws[roster_rows].sum(axis=1),
            player_ids=player_ids,
            player_rows=tuple(players),
            row_draws=draws,
            all_tags={lineup.ids: ("lev",) for lineup in lineups},
            metadata={"block": block},
        )
    result = build_production_form(books, expected_worlds_per_block=10)
    assert result["blocks"] == ["R0", "R1", "R2", "R3", "R4"]
    assert result["worlds_per_block"] == 10
    assert result["candidate_budget"] == SHELL_LIMIT
    assert len(result["control_selected_lineups"]) == 80
    assert len(result["component_library"]["cores"]) == CORE_LIMIT
    assert len(result["component_library"]["shells"]) == SHELL_LIMIT
    assert len(result["proposal_receipt"]["beam"]) == BEAM_LIMIT
    assert len(result["proposal_receipt"]["proposals"]) == PROPOSAL_LIMIT
    assert len(result["treatment"]["candidate_lineups"]) == SHELL_LIMIT
    assert len(result["treatment"]["selected_lineups"]) == 80
    receipt = production_form_receipt(result, season=2023, week=1)
    receipt["proposal_components"] = [{
        "roster": sorted(str(player) for player in proposal.lineup.ids),
        "core": list(proposal.core),
        "shell": list(proposal.shell),
        "rank": list(proposal.rank),
    } for proposal in result["proposal_receipt"]["proposals"]]
    assert receipt["version"] == "stack-core-shell-production-form-lock-v1"
    assert receipt["uses_realized_outcomes"] is False
    assert receipt["actual_scores_queried"] is False
    assert receipt["candidate_budget"] == SHELL_LIMIT
    assert len(receipt["candidate_rosters"]["control"]) == SHELL_LIMIT
    assert len(receipt["candidate_rosters"]["treatment"]) == SHELL_LIMIT
    assert len(receipt["selected_rosters"]["control"]) == 80
    assert len(receipt["selected_rosters"]["treatment"]) == 80
    assert receipt["beam_candidates"] == BEAM_LIMIT
    assert receipt["proposal_candidates"] == PROPOSAL_LIMIT
    assert len(receipt["proposal_rosters"]) == PROPOSAL_LIMIT
    receipt["worlds_per_block"] = 10_000
    validate_lock(receipt, 2023, 1)
    receipt["proposal_counts"]["covered_core_shell_pairs"] = 58
    try:
        validate_lock(receipt, 2023, 1)
    except ValueError as exc:
        assert "proposal counts differ" in str(exc)
    else:
        raise AssertionError("under-covered production-form lock was accepted")


def _fold(season: int, week: int, block: str, *, treatment_gain: int = 1) -> dict:
    thresholds = (187, 194, 200, 210, 220, 230, 240)
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "mechanical_valid": True,
        "season": season,
        "week": week,
        "heldout_block": block,
        "threshold_counts": {
            "candidate": {
                "control": {str(line): 100 for line in thresholds},
                "treatment": {
                    str(line): 100 + (treatment_gain if line == 230 else 0)
                    for line in thresholds
                },
            },
            "selected": {
                "control": {str(line): 100 for line in thresholds},
                "treatment": {
                    str(line): (
                        95 if line == 194 else
                        100 + (treatment_gain if line == 230 else 0)
                    )
                    for line in thresholds
                },
            },
        },
        "structure": {
            "candidate": {
                "control": {"unique_player_pairs": 100},
                "treatment": {"unique_player_pairs": 90},
            },
            "selected": {
                "control": {
                    "unique_qb_stack_cores": 100,
                    "unique_dominant_games": 100,
                },
                "treatment": {
                    "unique_qb_stack_cores": 90,
                    "unique_dominant_games": 90,
                },
            },
        },
    }


def test_aggregate_gate_uses_supported_anchor_and_full_grid() -> None:
    rows = [
        _fold(season, week, block)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
        for block in ("R0", "R1", "R2", "R3", "R4")
    ]
    result = aggregate_gate(rows, selected_anchor=230)
    assert result["folds"] == 270
    assert result["slates"] == 54
    assert result["selected_anchor"] == 230
    assert result["passes_scorefree_gate"] is True
    assert result["disposition"] == "stack-core-shell-shadow-licensed"
    assert len(result["leave_one_slate_out"]) == 54
    assert all(
        row["passes_nonstructure_conditions_without_slate"]
        for row in result["leave_one_slate_out"]
    )


def test_aggregate_gate_rejects_unsupported_anchor_or_incomplete_grid() -> None:
    rows = [
        _fold(season, week, block)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
        for block in ("R0", "R1", "R2", "R3", "R4")
    ]
    try:
        aggregate_gate(rows, selected_anchor=194)
    except ValueError as exc:
        assert "support anchor" in str(exc)
    else:
        raise AssertionError("unsupported anchor was accepted")
    try:
        aggregate_gate(rows[:-1], selected_anchor=230)
    except ValueError as exc:
        assert "fold population" in str(exc)
    else:
        raise AssertionError("incomplete grid was accepted")
