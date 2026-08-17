from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

from nfl_dfs.analysis.recourse_aware_initial import (
    PROTOCOL_SHA256,
    VERSION,
    aggregate_scorefree_folds,
    build_alternative_sets,
    is_late_swap_reachable,
    locked_slot_signature,
    scorefree_book_metrics,
    select_recourse_aware_initials,
)
from nfl_dfs.optimizer.lineup import Lineup


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = (
    ROOT / "reports/2026-08-17-recourse-aware-initial-book-scorefree-protocol.md"
)
DECISION = "2026-09-13T19:55:00Z"
EARLY = "2026-09-13T17:00:00Z"
LATE = "2026-09-13T20:05:00Z"
LATEST = "2026-09-13T20:25:00Z"


def _player(player_id: str, pos: str, kickoff: str, proj: float) -> dict:
    return {
        "id": player_id,
        "name": player_id,
        "pos": pos,
        "team": player_id[:2],
        "opp": "OPP",
        "game_id": f"game-{kickoff}",
        "salary": 5_000,
        "proj": proj,
        "kickoff": kickoff,
    }


def _lineup(
    suffix: str,
    *,
    qb: str = "q1",
    early_extra: bool = False,
) -> Lineup:
    extra_kickoff = EARLY if early_extra else LATEST
    return Lineup([
        _player(qb, "QB", EARLY, 20),
        _player("r1", "RB", EARLY, 18),
        _player(f"r2{suffix}", "RB", LATE, 17),
        _player(f"r3{suffix}", "RB", extra_kickoff, 16),
        _player(f"w1{suffix}", "WR", LATE, 19),
        _player(f"w2{suffix}", "WR", LATE, 15),
        _player(f"w3{suffix}", "WR", LATEST, 14),
        _player(f"t1{suffix}", "TE", LATEST, 13),
        _player("d1", "DST", EARLY, 8),
    ])


def _kickoffs(*lineups: Lineup) -> dict[str, str]:
    return {
        str(player["id"]): str(player["kickoff"])
        for lineup in lineups
        for player in lineup.players
    }


def test_protocol_is_frozen_before_implementation() -> None:
    assert sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256
    assert PROTOCOL_SHA256 == (
        "0085b5f77b4e859982fc4f664161cdafe2bb6ec07ea0351fb618ddf58319c077"
    )


def test_exact_slot_reachability_keeps_locked_players_and_rejects_new_early() -> None:
    initial = _lineup("a")
    reachable = _lineup("b")
    missing_locked = _lineup("c", qb="q2")
    new_early = _lineup("d", early_extra=True)
    kickoffs = _kickoffs(initial, reachable, missing_locked, new_early)
    signature = locked_slot_signature(initial, kickoffs, DECISION)
    assert {player for _, player in signature} == {"q1", "r1", "d1"}
    assert is_late_swap_reachable(initial, reachable, kickoffs, DECISION)
    assert not is_late_swap_reachable(
        initial, missing_locked, kickoffs, DECISION,
    )
    assert not is_late_swap_reachable(initial, new_early, kickoffs, DECISION)
    with pytest.raises(ValueError, match="timezone-aware"):
        locked_slot_signature(initial, kickoffs, "2026-09-13 15:55:00")


def test_alternative_ranking_is_capped_and_preserves_each_failsafe() -> None:
    lineups = [_lineup(value) for value in ("a", "b", "c")]
    totals = np.asarray([
        [190, 195, 200, 205],
        [230, 240, 250, 260],
        [210, 220, 230, 240],
    ], dtype=np.float32)
    alternatives = build_alternative_sets(
        lineups, totals, _kickoffs(*lineups), DECISION, cap=2,
    )
    assert all(len(row) == 2 for row in alternatives)
    assert all(index in row for index, row in enumerate(alternatives))
    assert alternatives[0] == (1, 0)


def test_option_selector_prefers_broader_high_tail_reach() -> None:
    lineups = [_lineup(value) for value in ("a", "b", "c")]
    totals = np.asarray([
        [245, 100, 100, 100],
        [100, 100, 100, 100],
        [100, 245, 245, 100],
    ], dtype=np.float32)
    alternatives = ((0,), (1, 2), (2,))
    selected = select_recourse_aware_initials(
        lineups, totals, alternatives, entries=1,
    )
    assert selected == [1]


def test_selector_is_deterministic_and_exact_when_coverage_saturates() -> None:
    lineups = [_lineup(value) for value in ("a", "b", "c")]
    totals = np.full((3, 5), 100.0, dtype=np.float32)
    alternatives = ((0,), (1,), (2,))
    first = select_recourse_aware_initials(
        lineups, totals, alternatives, entries=2,
    )
    second = select_recourse_aware_initials(
        lineups, totals, alternatives, entries=2,
    )
    assert first == second
    expected = sorted(range(3), key=lambda index: tuple(sorted(lineups[index].ids)))
    assert first == expected[:2]


def test_scorefree_metrics_separate_initial_and_reachable_union() -> None:
    totals = np.asarray([
        [195, 100, 100],
        [100, 235, 100],
        [100, 100, 245],
    ], dtype=np.float32)
    alternatives = ((0, 1), (1, 2), (2,))
    signatures = (
        ((0, "q1"),),
        ((0, "q1"),),
        ((0, "q2"),),
    )
    metrics = scorefree_book_metrics(
        [0, 1], totals, alternatives, signatures,
    )
    assert metrics["uses_realized_outcomes"] is False
    assert metrics["initial_coverage"]["240"]["events"] == 0
    assert metrics["reachable_union_coverage"]["240"]["events"] == 1
    assert metrics["reachable_alternatives"] == 3
    assert metrics["distinct_locked_slot_signatures"] == 1


def _coverage(events: dict[int, int]) -> dict[str, dict[str, float | int]]:
    return {
        str(threshold): {
            "events": value,
            "rate": value / 10_000,
        }
        for threshold, value in events.items()
    }


def _aggregate_fold(season: int, week: int, block: int) -> dict:
    control_events = {240: 1, 230: 10, 220: 20, 210: 30,
                      200: 50, 194: 100, 187: 200}
    treatment_initial = dict(control_events)
    treatment_initial[194] = 95
    treatment_reachable = dict(control_events)
    treatment_reachable[230] = 11
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "season": season,
        "week": week,
        "heldout_block": f"R{block}",
        "candidate_budget": 100,
        "alternative_cap": 24,
        "selected_identity_overlap": 70,
        "control": {
            "uses_realized_outcomes": False,
            "entries": 80,
            "worlds": 10_000,
            "initial_coverage": _coverage(control_events),
            "reachable_union_coverage": _coverage(control_events),
            "reachable_alternatives": 90,
            "distinct_locked_slot_signatures": 50,
        },
        "treatment": {
            "uses_realized_outcomes": False,
            "entries": 80,
            "worlds": 10_000,
            "initial_coverage": _coverage(treatment_initial),
            "reachable_union_coverage": _coverage(treatment_reachable),
            "reachable_alternatives": 91,
            "distinct_locked_slot_signatures": 50,
        },
    }


def _fold_grid() -> list[dict]:
    return [
        _aggregate_fold(season, week, block)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
        for block in range(5)
    ]


def test_frozen_aggregate_gate_passes_only_complete_positive_population() -> None:
    result = aggregate_scorefree_folds(_fold_grid())
    assert result["mechanical"] == {
        "slates": 54,
        "folds": 270,
        "worlds_per_fold": 10_000,
        "all_valid": True,
    }
    assert result["gate_diagnostics"]["reachable_p230_event_gain"] == 270
    assert result["gate_diagnostics"]["improving_p230_blocks"] == 5
    assert result["gate_diagnostics"]["initial_p194_retention_ratio"] == 0.95
    assert all(result["conditions"].values())
    assert result["passed"] is True
    assert result["historical_policy_diagnostic_licensed"] is True
    assert result["production_change_licensed"] is False
    assert result["disposition"] == \
        "recourse-aware-initial-book-premise-passes"


def test_frozen_aggregate_gate_rejects_high_tail_initial_decline() -> None:
    rows = _fold_grid()
    for row in rows:
        row["treatment"]["initial_coverage"]["230"] = {
            "events": 9,
            "rate": 0.0009,
        }
    result = aggregate_scorefree_folds(rows)
    assert result["conditions"]["initial_p240_p230_p220_nondecline"] is False
    assert result["passed"] is False
    assert result["historical_policy_diagnostic_licensed"] is False
    assert result["disposition"] == \
        "recourse-aware-candidate-union-selector-premise-fails"


def test_frozen_aggregate_rejects_incomplete_or_outcome_facing_grid() -> None:
    rows = _fold_grid()
    with pytest.raises(ValueError, match="fold grid differs"):
        aggregate_scorefree_folds(rows[:-1])
    rows[0]["treatment"]["uses_realized_outcomes"] = True
    with pytest.raises(ValueError, match="book contract differs"):
        aggregate_scorefree_folds(rows)


@pytest.mark.parametrize(
    "alternatives",
    [
        ((), (1,), (2,)),
        ((1,), (1,), (2,)),
        ((0, 3), (1,), (2,)),
        ((0, 0), (1,), (2,)),
    ],
)
def test_selector_rejects_invalid_alternative_contract(alternatives) -> None:
    lineups = [_lineup(value) for value in ("a", "b", "c")]
    totals = np.ones((3, 5), dtype=np.float32)
    with pytest.raises(ValueError, match="alternative set differs"):
        select_recourse_aware_initials(
            lineups, totals, alternatives, entries=2,
        )
