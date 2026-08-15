import numpy as np
import pytest

from nfl_dfs.analysis import exact_n_portfolio as exact_n


def _totals(candidates=85, block_worlds=10):
    totals = np.full((candidates, 5 * block_worlds), 180.0)
    # Incumbent first choice covers many 194 worlds but no 230 worlds.
    totals[0, :10] = 205.0
    # Robust high-tail choice covers two worlds in each seed block and also
    # clears 194, so it is the frozen single-entry treatment.
    for block in range(5):
        start = block * block_worlds
        totals[1, start:start + 2] = 235.0
    for candidate in range(2, candidates):
        totals[candidate] += candidate / 1000.0
    return totals


def test_single_entry_is_robust_tail_not_incumbent_80_prefix():
    totals = _totals()
    result = exact_n.exact_n_scorefree_diagnostic(
        totals, list(range(80)), 1,
    )
    assert result["uses_realized_outcomes"] is False
    assert result["control"]["selected"] == [0]
    assert result["treatment"]["selected"] == [1]
    assert result["primary_target"] == 230.0
    assert result["conditions"]["primary_improves_at_least_three_blocks"]
    assert result["passes_scorefree_falsifier"]


def test_selector_is_exact_size_deterministic_and_cardinality_scoped():
    totals = _totals()
    first = exact_n.select_cardinality_tail_book(totals, 3)
    second = exact_n.select_cardinality_tail_book(totals, 3)
    assert first == second
    assert len(first) == len(set(first)) == 3
    assert first[0] == 1
    with pytest.raises(ValueError, match="only 1/3/20/40"):
        exact_n.select_cardinality_tail_book(totals, 2)


def test_diagnostic_rejects_bad_world_blocks_and_incumbent_order():
    totals = _totals()
    with pytest.raises(ValueError, match="candidate worlds are invalid"):
        exact_n.select_cardinality_tail_book(totals[:, :-1], 1)
    with pytest.raises(ValueError, match="lacks 80 unique"):
        exact_n.exact_n_scorefree_diagnostic(totals, [0] * 80, 1)


def test_book_metrics_supports_separate_production_context():
    totals = _totals()
    metrics = exact_n.book_scorefree_metrics(totals, [0, 1, 2])

    assert metrics["entries"] == 3
    assert metrics["selected"] == [0, 1, 2]
    assert set(metrics["tail"]) == {"194", "200", "210", "230"}
    with pytest.raises(ValueError, match="selected book is invalid"):
        exact_n.book_scorefree_metrics(totals, [0, 0])
