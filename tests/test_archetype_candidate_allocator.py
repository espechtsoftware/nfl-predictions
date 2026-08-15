from __future__ import annotations

import pandas as pd
import pytest

from nfl_dfs.inference.archetype_candidate_allocator import (
    ALLOCATION_VERSION,
    ARCHETYPE_ORDER,
    allocate_archetype_budget,
    classify_archetypes,
)


def _frame(rows_per_source: int = 30) -> pd.DataFrame:
    rows = []
    for source_index, source in enumerate(("R0", "R1", "R2", "R3", "R4")):
        for index in range(rows_per_source):
            overall = source_index * rows_per_source + index
            rows.append({
                "candidate_key": f"roster-{overall:04d}",
                "source_seed": source,
                "sim_q99": 260.0 - overall / 10,
                "p_line": 0.90 - ((overall * 17) % 149) / 200,
                "largest_team_block": 3 if overall % 5 else 2,
                "qb_stack_count": 2 if overall % 4 else 1,
                "bring_back_count": 1 if overall % 3 else 0,
                "salary": 49_000 + overall % 11 * 100,
            })
    return pd.DataFrame(rows)


def test_classification_is_complete_deterministic_and_outcome_blind():
    frame = _frame()
    first = classify_archetypes(frame)
    second = classify_archetypes(frame.sample(frac=1, random_state=7))
    first_labels = first.set_index("candidate_key").archetype.sort_index()
    second_labels = second.set_index("candidate_key").archetype.sort_index()
    pd.testing.assert_series_equal(first_labels, second_labels)
    assert set(first.archetype) <= set(ARCHETYPE_ORDER)
    assert first.archetype_allocation_version.eq(ALLOCATION_VERSION).all()
    assert first.sim_q99_rank.between(1, len(first)).all()
    assert first.p_line_rank.between(1, len(first)).all()


@pytest.mark.parametrize("column", ["actual", "actual_score", "actual_rank", "roi"])
def test_classification_rejects_any_outcome_column(column):
    frame = _frame()
    frame[column] = 0
    with pytest.raises(ValueError, match="post-lock outcomes"):
        classify_archetypes(frame)


def test_allocator_is_exact_deterministic_and_source_balanced():
    frame = _frame()
    order = ("R0", "R1", "R2", "R3", "R4")
    first, receipt = allocate_archetype_budget(frame, 80, order)
    second, second_receipt = allocate_archetype_budget(
        frame.sample(frac=1, random_state=11), 80, order
    )
    assert len(first) == first.candidate_key.nunique() == 80
    assert first.candidate_key.tolist() == second.candidate_key.tolist()
    assert receipt == second_receipt
    assert receipt["source_targets"] == {
        "R0": 16,
        "R1": 16,
        "R2": 16,
        "R3": 16,
        "R4": 16,
    }
    assert receipt["source_selected"] == receipt["source_targets"]
    assert receipt["source_quota_relaxed"] is False
    assert receipt["candidate_budget"] == 80
    assert receipt["uses_realized_outcomes"] is False
    assert sorted(first.allocation_rank) == list(range(1, 81))


def test_allocator_uses_frozen_largest_remainder_archetype_targets():
    _, receipt = allocate_archetype_budget(
        _frame(), 80, ("R0", "R1", "R2", "R3", "R4")
    )
    assert receipt["archetype_targets"] == {
        "block3_joint_tail": 24,
        "block3_q99_tail": 20,
        "other_high_tail": 20,
        "structural_diversity": 16,
    }
    assert sum(receipt["archetype_selected"].values()) == 80


def test_allocator_discloses_source_relaxation_when_one_source_is_too_small():
    frame = _frame(rows_per_source=20)
    retained_r4 = frame[frame.source_seed.eq("R4")].head(4).candidate_key
    frame = frame[~(
        frame.source_seed.eq("R4")
        & ~frame.candidate_key.isin(retained_r4)
    )].copy()
    chosen, receipt = allocate_archetype_budget(
        frame, 50, ("R0", "R1", "R2", "R3", "R4")
    )
    assert len(chosen) == 50
    assert receipt["source_available"]["R4"] == 4
    assert receipt["source_selected"]["R4"] == 4
    assert receipt["source_quota_relaxed"] is True


def test_allocator_fails_closed_on_duplicate_or_insufficient_union():
    frame = _frame(rows_per_source=2)
    duplicate = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="unique"):
        allocate_archetype_budget(
            duplicate, 5, ("R0", "R1", "R2", "R3", "R4")
        )
    with pytest.raises(ValueError, match="for budget"):
        allocate_archetype_budget(
            frame, 11, ("R0", "R1", "R2", "R3", "R4")
        )
