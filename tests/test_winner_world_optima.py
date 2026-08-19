"""Offline tests for the winner-world optima audit (N1c)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis.winner_world_optima import (
    WinnerOptimaError,
    best_generating_world,
    solve_winner_world,
    winner_optima_report,
    world_player_frame,
)

OPP = {"AA": "BB", "BB": "AA", "CC": "DD", "DD": "CC"}
# Production-valid: QB_AA stacks WR_AA1/WR_AA2, RB_BB1 brings back, two
# games, no same-team RBs, DST_CC faces DD (no DD RBs), salary 49,600.
WINNER = [
    "QB_AA", "RB_BB1", "RB_CC1", "WR_AA1", "WR_AA2", "WR_BB1",
    "WR_DD1", "TE_AA1", "DST_CC",
]
# DK-legal but production-invalid: QB_AA has no BB bring-back.
WINNER_NO_BRING_BACK = [
    "QB_AA", "RB_CC1", "RB_DD1", "WR_AA1", "WR_AA2", "WR_CC1",
    "WR_DD1", "TE_AA1", "DST_BB",
]


def _slate() -> tuple[pd.DataFrame, list[str]]:
    rows = []
    for team in OPP:
        rows.append((f"QB_{team}", "QB", team, 5700))
        rows.extend((f"RB_{team}{i}", "RB", team, 5700) for i in (1, 2))
        rows.extend((f"WR_{team}{i}", "WR", team, 5700) for i in (1, 2, 3))
        rows.extend((f"TE_{team}{i}", "TE", team, 5700) for i in (1, 2))
        rows.append((f"DST_{team}", "DST", team, 4000))
    frame = pd.DataFrame(rows, columns=["id", "pos", "team", "salary"])
    return frame, frame.id.tolist()


def _world(ids: list[str], high: dict[str, float]) -> np.ndarray:
    return np.array([high.get(pid, 1.0) for pid in ids])


def test_best_generating_world_argmax_and_tie_break():
    winner = np.array([10.0, 20.0, 20.0, 1.0])
    cands = np.array([[5.0, 15.0, 25.0, 9.0]])
    best = best_generating_world(winner, cands)
    assert best["world_index"] == 0 and best["margin"] == 5.0
    winner_tie = np.array([10.0, 20.0])
    cands_tie = np.array([[5.0, 15.0]])
    assert best_generating_world(winner_tie, cands_tie)["world_index"] == 0
    assert best_generating_world(
        np.array([1.0, 1.0]), np.array([[2.0, 1.0]])) is None


def test_winner_is_the_unique_legal_and_production_optimum():
    slate, ids = _slate()
    high = {pid: 30.0 for pid in WINNER if not pid.startswith("DST")}
    high["DST_CC"] = 10.0
    frame = world_player_frame(slate, OPP, np.array(ids), _world(ids, high))
    solve = solve_winner_world(frame, WINNER)
    assert solve["winner_dk_legal_in_snapshot"]
    assert solve["winner_production_valid"]
    assert solve["is_legal_optimum_identity"]
    assert solve["is_legal_optimum_score"]
    assert solve["legal_overlap"] == 9
    assert solve["legal_gap"] == pytest.approx(0.0, abs=1e-6)
    assert solve["production_gap"] == pytest.approx(0.0, abs=1e-6)


def test_winner_dominated_by_a_different_build():
    slate, ids = _slate()
    alt = [
        "QB_CC", "WR_CC1", "WR_CC2", "RB_DD1", "TE_CC1", "RB_AA1",
        "WR_BB2", "WR_DD2", "DST_AA",
    ]
    high = {pid: 40.0 for pid in alt if not pid.startswith("DST")}
    high["DST_AA"] = 12.0
    high.update(
        {pid: 5.0 for pid in WINNER if not pid.startswith("DST")})
    high["DST_CC"] = 5.0
    frame = world_player_frame(slate, OPP, np.array(ids), _world(ids, high))
    solve = solve_winner_world(frame, WINNER)
    assert not solve["is_legal_optimum_score"]
    assert not solve["is_near_legal_optimum"]
    assert solve["legal_overlap"] == 0
    assert solve["legal_gap"] == pytest.approx(332.0 - 45.0, abs=1e-6)


def test_production_rules_can_exclude_a_better_winner():
    slate, ids = _slate()
    high = {
        pid: 50.0 for pid in WINNER_NO_BRING_BACK
        if not pid.startswith("DST")
    }
    high["DST_BB"] = 15.0
    frame = world_player_frame(slate, OPP, np.array(ids), _world(ids, high))
    solve = solve_winner_world(frame, WINNER_NO_BRING_BACK)
    assert solve["winner_dk_legal_in_snapshot"]
    assert not solve["winner_production_valid"]
    assert any(
        "bring-back" in failure
        for failure in solve["winner_production_failures"])
    assert solve["is_legal_optimum_score"]
    assert solve["production_gap"] == pytest.approx(-49.0, abs=1e-6)


def test_frame_fails_closed_on_missing_player_or_opponent():
    slate, ids = _slate()
    with pytest.raises(WinnerOptimaError, match="absent from slate"):
        world_player_frame(
            slate, OPP, np.array(ids + ["GHOST"]),
            np.ones(len(ids) + 1))
    with pytest.raises(WinnerOptimaError, match="opponent mapping"):
        world_player_frame(
            slate, {"AA": "BB", "BB": "AA"}, np.array(ids),
            np.ones(len(ids)))


def test_report_aggregates_and_flags():
    def entry(season, week, exact, gap, production_gap, valid):
        return {
            "season": season, "week": week, "roster_ids": list(WINNER),
            "world": {"world_index": 0, "margin": 1.0},
            "solve": {
                "legal_gap": gap, "legal_overlap": 9 if exact else 4,
                "is_legal_optimum_score": exact,
                "is_near_legal_optimum": gap <= 2.0,
                "production_gap": production_gap,
                "production_overlap": 5,
                "winner_production_valid": valid,
                "winner_dk_legal_in_snapshot": True,
            },
        }

    report = winner_optima_report([
        entry(2023, 1, True, 0.0, 0.0, True),
        entry(2023, 2, False, 12.5, -3.0, False),
    ])
    assert report["n_winners"] == 2
    assert report["n_exact_legal_optimum"] == 1
    assert report["n_near_legal_optimum"] == 1
    assert report["n_negative_production_gap"] == 1
    assert report["n_winner_production_valid"] == 1
    assert report["median_legal_gap"] == pytest.approx(6.25)
    assert report["uses_realized_outcomes"] is False
    assert report["winner_identities_outcome_derived"] is True
    assert report["gate_decision"] is None
    with pytest.raises(WinnerOptimaError, match="duplicate"):
        winner_optima_report([
            entry(2023, 1, True, 0.0, 0.0, True),
            entry(2023, 1, True, 0.0, 0.0, True),
        ])
