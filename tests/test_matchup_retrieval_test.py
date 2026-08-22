from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research import matchup_retrieval_test as harness


def _slate(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    frame = pd.DataFrame({
        "cand_ix": np.arange(n),
        "selected": [True] * harness.BOOK_SIZE + [False] * (n - 80),
        "p_line": np.linspace(0.9, 0.1, n),
        "oof_score": rng.uniform(size=n),
        "matchup_supported_count": [6] * n,
        "actual_score": rng.uniform(100, 190, size=n),
    })
    return frame


def test_sleeve_swaps_lowest_pline_for_top_scores():
    slate = _slate()
    # Make the best unselected scores unambiguous.
    slate.loc[100:107, "oof_score"] = 2.0
    books = harness.build_books(slate)
    assert int(books["incumbent"].sum()) == 80
    assert int(books["sleeve"].sum()) == 80
    swapped_in = np.flatnonzero(books["sleeve"] & ~books["incumbent"])
    assert list(swapped_in) == list(range(100, 108))
    swapped_out = np.flatnonzero(books["incumbent"] & ~books["sleeve"])
    # Incumbent's K lowest p_line rows are indices 72..79.
    assert list(swapped_out) == list(range(72, 80))
    assert int(books["blend"].sum()) == 80


def test_sleeve_respects_support_gate_and_book_size_law():
    slate = _slate()
    slate["matchup_supported_count"] = 0
    books = harness.build_books(slate)
    # No eligible candidates -> sleeve equals incumbent.
    assert (books["sleeve"] == books["incumbent"]).all()
    broken = _slate()
    broken.loc[0, "selected"] = False
    with pytest.raises(
        harness.MatchupRetrievalTestError, match="incumbent book"
    ):
        harness.build_books(broken)
