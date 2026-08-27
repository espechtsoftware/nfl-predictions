from __future__ import annotations

import numpy as np
import pytest

from nfl_dfs.optimizer.lineup import (
    select_from_support,
    select_ladder_entries,
)
from nfl_dfs.research import weighted_belief_selection_v1 as weighted


def test_uniform_tail_weights_delegate_and_match_production(monkeypatch) -> None:
    totals = np.array([
        [12.0, 4.0, 11.0, 2.0],
        [10.0, 10.0, 3.0, 2.0],
        [4.0, 1.0, 9.0, 14.0],
        [8.0, 8.0, 8.0, 8.0],
    ])
    line = 10.0
    expected = select_from_support(
        totals >= line,
        (totals >= line).mean(axis=1),
        totals.mean(axis=1),
        3,
    )
    original = weighted.production_lineup.select_from_support
    calls = []

    def spy(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(weighted.production_lineup, "select_from_support", spy)
    observed = weighted.select_weighted_tail_entries(
        totals, 3, line, [5.0, 5.0, 5.0, 5.0]
    )
    assert calls == [True]
    assert observed == expected


def test_weighted_tail_can_reverse_unweighted_choice() -> None:
    totals = np.array([
        [0.0, 10.0, 10.0],   # two low-mass worlds
        [10.0, 0.0, 0.0],    # one high-mass world
    ])
    unweighted = weighted.select_weighted_tail_entries(
        totals, 1, 10.0, [1.0, 1.0, 1.0]
    )
    importance_weighted = weighted.select_weighted_tail_entries(
        totals, 1, 10.0, [0.8, 0.1, 0.1]
    )
    assert unweighted == [0]
    assert importance_weighted == [1]


def test_weighted_tail_is_deterministic_on_ties_and_world_order() -> None:
    totals = np.array([
        [11.0, 0.0, 11.0, 0.0],
        [11.0, 0.0, 11.0, 0.0],
        [0.0, 12.0, 0.0, 12.0],
    ])
    weights = np.array([0.50, 0.20, 0.20, 0.10])
    first = weighted.select_weighted_tail_entries(totals, 3, 10.0, weights)
    second = weighted.select_weighted_tail_entries(totals, 3, 10.0, weights)
    assert first == second == [0, 2, 1]

    permutation = np.array([2, 0, 3, 1])
    reordered = weighted.select_weighted_tail_entries(
        totals[:, permutation], 3, 10.0, weights[permutation]
    )
    assert reordered == first


def test_candidate_reordering_preserves_non_tied_weighted_choice() -> None:
    totals = np.array([
        [0.0, 10.0, 10.0],
        [10.0, 0.0, 0.0],
        [0.0, 0.0, 10.0],
    ])
    weights = [0.75, 0.20, 0.05]
    original = weighted.select_weighted_tail_entries(totals, 2, 10.0, weights)
    permutation = np.array([2, 0, 1])
    permuted = weighted.select_weighted_tail_entries(
        totals[permutation], 2, 10.0, weights
    )
    mapped = [int(permutation[index]) for index in permuted]
    assert mapped == original


def test_uniform_ladder_delegates_and_matches_production(monkeypatch) -> None:
    totals = np.array([
        [25.0, 0.0, 10.0],
        [20.0, 20.0, 0.0],
        [0.0, 15.0, 25.0],
    ])
    ladder = {10.0: 1.0, 20.0: 4.0}
    expected = select_ladder_entries(
        totals, 2, ladder, mean_weight=0.25
    )
    original = weighted.production_lineup.select_ladder_entries
    calls = []

    def spy(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(weighted.production_lineup, "select_ladder_entries", spy)
    observed = weighted.select_weighted_ladder_entries(
        totals,
        2,
        ladder,
        [2.0, 2.0, 2.0],
        mean_weight=0.25,
    )
    assert calls == [True]
    assert observed == expected


def test_weighted_ladder_uses_probability_mass_and_is_order_stable() -> None:
    totals = np.array([
        [0.0, 20.0, 20.0],
        [20.0, 0.0, 0.0],
        [0.0, 12.0, 0.0],
    ])
    ladder = {10.0: 1.0, 20.0: 3.0}
    unweighted = weighted.select_weighted_ladder_entries(
        totals, 1, ladder, [1.0, 1.0, 1.0]
    )
    weights = np.array([0.8, 0.1, 0.1])
    importance_weighted = weighted.select_weighted_ladder_entries(
        totals, 1, ladder, weights
    )
    assert unweighted == [0]
    assert importance_weighted == [1]

    permutation = np.array([2, 0, 1])
    reordered = weighted.select_weighted_ladder_entries(
        totals[:, permutation], 1, ladder, weights[permutation]
    )
    assert reordered == importance_weighted


def test_weighted_ladder_mean_term_is_world_weighted() -> None:
    totals = np.array([
        [0.0, 100.0],
        [30.0, 30.0],
    ])
    # With most probability on world zero, weighted expected maximum prefers
    # the steady candidate even though the unweighted mean prefers candidate 0.
    unweighted = weighted.select_weighted_ladder_entries(
        totals, 1, {}, [1.0, 1.0], mean_weight=1.0
    )
    importance_weighted = weighted.select_weighted_ladder_entries(
        totals, 1, {}, [0.9, 0.1], mean_weight=1.0
    )
    assert unweighted == [0]
    assert importance_weighted == [1]


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        ([1.0, 1.0], "align"),
        ([1.0, -1.0, 1.0], "nonnegative"),
        ([0.0, 0.0, 0.0], "no positive mass"),
        ([1.0, np.nan, 1.0], "finite"),
    ],
)
def test_weighted_tail_rejects_invalid_world_weights(weights, message) -> None:
    totals = np.ones((2, 3))
    with pytest.raises(weighted.WeightedBeliefSelectionError, match=message):
        weighted.select_weighted_tail_entries(totals, 1, 1.0, weights)


def test_world_weight_normalization_is_overflow_safe() -> None:
    observed = weighted.normalize_world_weights(
        [1e308, 1e308, 5e307], expected_worlds=3
    )
    assert observed == pytest.approx([0.4, 0.4, 0.2])
    assert observed.sum() == pytest.approx(1.0)


def test_weighted_selectors_reject_invalid_totals_or_utility() -> None:
    with pytest.raises(
        weighted.WeightedBeliefSelectionError, match="finite 2-D"
    ):
        weighted.select_weighted_tail_entries(
            np.array([[np.nan]]), 1, 1.0, [1.0]
        )
    with pytest.raises(
        weighted.WeightedBeliefSelectionError, match="no positive utility"
    ):
        weighted.select_weighted_ladder_entries(
            np.ones((2, 2)), 1, {10.0: 0.0}, [0.7, 0.3]
        )
