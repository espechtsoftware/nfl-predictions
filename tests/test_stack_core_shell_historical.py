from __future__ import annotations

from copy import deepcopy

from nfl_dfs.analysis.stack_core_shell_historical import (
    ROW_VERSION,
    aggregate_historical,
    compare_locked_slate,
)


def _roster(prefix: str) -> list[str]:
    return sorted(f"{prefix}-{index}" for index in range(9))


def _lock(season: int = 2023, week: int = 1) -> tuple[dict, dict[str, float]]:
    shared = [_roster(f"shared-{index}") for index in range(79)]
    control_only = _roster("control-only")
    treatment_only = _roster("treatment-only")
    proposals = [treatment_only] + [_roster(f"proposal-{index}") for index in range(39)]
    actual = {}
    for roster in [*shared, control_only, *proposals]:
        score = 205.0 if roster == treatment_only else 190.0
        for player in roster:
            actual[player] = score / 9.0
    lock = {
        "version": "stack-core-shell-production-form-lock-v1",
        "uses_realized_outcomes": False,
        "actual_scores_queried": False,
        "mechanical_valid": True,
        "season": season,
        "week": week,
        "blocks": ["R0", "R1", "R2", "R3", "R4"],
        "candidate_budget": 80,
        "selected_entries": 80,
        "proposal_candidates": 40,
        "candidate_rosters": {
            "control": [*shared, control_only],
            "treatment": [*shared, treatment_only],
        },
        "selected_rosters": {
            "control": [*shared, control_only],
            "treatment": [*shared, treatment_only],
        },
        "proposal_rosters": proposals,
        "admitted_proposal_rosters": [treatment_only],
        "admitted_proposals": 1,
        "structure": {"locked": True},
        "score_effective_rank": {"locked": True},
    }
    return lock, actual


def test_scores_only_an_outcome_free_locked_exact80_book() -> None:
    lock, actual = _lock()
    row = compare_locked_slate(lock, actual)
    assert row["version"] == ROW_VERSION
    assert row["books"]["selected"]["control"]["maximum"] == 190.0
    assert row["books"]["selected"]["treatment"]["maximum"] == 205.0
    assert row["proposal_conversion"]["generated"] == 40
    assert row["proposal_conversion"]["admitted"] == 1
    assert row["proposal_conversion"]["selected"] == 1

    bad = deepcopy(lock)
    bad["actual_scores_queried"] = True
    try:
        compare_locked_slate(bad, actual)
    except ValueError as exc:
        assert "lock identity differs" in str(exc)
    else:
        raise AssertionError("outcome-bearing construction lock was accepted")


def test_aggregate_applies_frozen_tail_first_conditions() -> None:
    rows = []
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            lock, actual = _lock(season, week)
            rows.append(compare_locked_slate(lock, actual))
    result = aggregate_historical(rows)
    assert result["population"] == {"seasons": [2023, 2024, 2025], "slates": 54}
    assert result["gate"]["threshold_net"]["selected"]["200"] == 54
    assert result["gate"]["threshold_net"]["selected"]["210"] == 0
    assert result["gate"]["threshold_net"]["candidate"]["200"] == 54
    assert result["gate"]["historical_tail_first_positive"] is True
    assert result["gate"]["disposition"] == "historical-tail-first-positive"
    assert result["by_season"]["2023"]["gate"][
        "historical_tail_first_positive"
    ] is True
    assert result["proposal_conversion"]["threshold_counts"]["200"] == {
        "generated": 54, "admitted": 54, "selected": 54,
    }
    assert result["identity_overlap"]["selected"]["treatment_only"] == 54
    assert len(result["leave_one_slate_out"]) == 54
    assert len(result["paired"]["selected"]["weeks"]) == 54
    assert all(
        row["classification"] == "gained"
        for row in result["paired"]["selected"]["weeks"]
    )
    transitions = result["threshold_transitions"]["selected"]["200"]
    assert len(transitions["gained"]) == 54
    assert transitions["lost"] == []
    assert transitions["tied"] == []
    assert transitions["gained"][0]["treatment_winning_rosters"]
    assert result["production_change_licensed"] is False
