import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import g1_archetype_topology as g1


def test_terminal_rows_and_worlds_are_canonical_across_source_order():
    frame = pd.DataFrame({
        "season": [2025, 2024, 2025],
        "week": [2, 18, 1],
        "gsis_id": ["c", "a", "b"],
        "position": ["WR", "QB", "RB"],
        "value": [30, 10, 20],
    })
    draws = np.asarray([[30, 31], [10, 11], [20, 21]], dtype=np.float32)
    ordered, aligned = g1._canonicalize_terminal_rows(frame, draws)

    assert ordered.gsis_id.tolist() == ["a", "b", "c"]
    assert aligned.tolist() == [[10, 11], [20, 21], [30, 31]]
    shuffled = frame.iloc[[2, 0, 1]].reset_index(drop=True)
    shuffled_draws = draws[[2, 0, 1]]
    repeated, repeated_draws = g1._canonicalize_terminal_rows(
        shuffled, shuffled_draws
    )
    pd.testing.assert_frame_equal(ordered, repeated)
    np.testing.assert_array_equal(aligned, repeated_draws)


def test_terminal_order_rejects_duplicate_keys_and_misaligned_worlds():
    frame = pd.DataFrame({
        "season": [2025, 2025], "week": [1, 1],
        "gsis_id": ["a", "a"], "position": ["WR", "WR"],
    })
    with pytest.raises(ValueError, match="keys repeat"):
        g1._canonicalize_terminal_rows(frame, np.ones((2, 3)))
    with pytest.raises(ValueError, match="cannot be canonically aligned"):
        g1._canonicalize_terminal_rows(frame.iloc[:1], np.ones((2, 3)))
