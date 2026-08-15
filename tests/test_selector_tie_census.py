import numpy as np
import pytest

from nfl_dfs.analysis.selector_tie_census import stable_identity_tail_selection


def test_stable_identity_tie_break_is_row_permutation_invariant():
    totals = np.asarray([
        [200.0, 180.0, 180.0, 180.0],
        [200.0, 180.0, 180.0, 180.0],
        [180.0, 200.0, 180.0, 180.0],
    ])
    keys = ["b", "a", "c"]
    first = stable_identity_tail_selection(totals, keys, 2, 194.0)
    order = np.asarray([2, 0, 1])
    second = stable_identity_tail_selection(
        totals[order], [keys[index] for index in order], 2, 194.0,
    )

    assert first["selected_keys"] == second["selected_keys"] == ["a", "c"]
    assert first["steps_with_full_numeric_ties"] == 1
    assert first["covered_worlds"] == 2
    assert first["uses_realized_outcomes"] is False


def test_tie_census_distinguishes_marginal_from_full_numeric_ties():
    totals = np.asarray([
        [205.0, 180.0],
        [210.0, 180.0],
        [180.0, 205.0],
    ])
    result = stable_identity_tail_selection(totals, ["a", "b", "c"], 2, 194)

    assert result["trace"][0]["marginal_tie_candidates"] == 3
    assert result["trace"][0]["marginal_and_p_line_tie_candidates"] == 3
    assert result["trace"][0]["full_numeric_tie_candidates"] == 1
    assert result["selected_keys"] == ["b", "c"]


def test_tie_census_rejects_ambiguous_or_nonfinite_inputs():
    totals = np.ones((2, 3))
    with pytest.raises(ValueError, match="inputs are invalid"):
        stable_identity_tail_selection(totals, ["x", "x"], 1, 194)
    totals[0, 0] = np.nan
    with pytest.raises(ValueError, match="inputs are invalid"):
        stable_identity_tail_selection(totals, ["x", "y"], 1, 194)
