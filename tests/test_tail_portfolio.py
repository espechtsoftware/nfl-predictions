from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.tail_portfolio import (
    decode_clear_bits,
    evaluate_portfolio,
    high_unselected_candidates,
    missed_oracles,
    portfolio_summary,
    select_slate,
    swap_frontier,
)


def _hex(bits: list[int]) -> str:
    return np.packbits(np.asarray(bits, dtype=np.uint8),
                       bitorder="big").tobytes().hex()


def _panel() -> pd.DataFrame:
    rows = []
    # Candidate 2 is the hindsight winner but has no simulated 194 clears.
    supports = ([1, 1, 0, 0], [0, 0, 1, 1], [0, 0, 0, 0])
    actuals = (190.0, 195.0, 220.0)
    for season, week in ((2024, 1), (2025, 2)):
        for cand_ix, (support, actual) in enumerate(zip(supports, actuals)):
            rows.append({
                "season": season,
                "week": week,
                "cand_ix": cand_ix,
                "tag": ("boom", "lev", "dark")[cand_ix],
                "players": ",".join(
                    [f"p{cand_ix}_{i}" for i in range(9)]),
                "selected": cand_ix < 2,
                "selected_rank": cand_ix if cand_ix < 2 else -1,
                "salary": 49_000 + cand_ix * 100,
                "p_line": sum(support) / 4,
                "sim_mean": 150.0 - cand_ix,
                "sim_q99": 205.0 - cand_ix,
                "actual_score": actual,
                "n_worlds": 4,
                "clear_bits_187": _hex(support),
                "clear_bits_194": _hex(support),
                "clear_bits_200": _hex(support),
            })
    return pd.DataFrame(rows)


def test_decode_clear_bits_checks_length():
    assert decode_clear_bits(_hex([1, 0, 1, 0]), 4).tolist() == [1, 0, 1, 0]
    with pytest.raises(ValueError, match="fewer"):
        decode_clear_bits(_hex([1] * 8), 9)


def test_select_and_evaluate_frozen_portfolio():
    panel = _panel()
    ordered, support, picked = select_slate(
        panel[(panel.season == 2024) & (panel.week == 1)], 2, 194.0)
    assert ordered.cand_ix.tolist() == [0, 1, 2]
    assert support.shape == (3, 4)
    assert picked.tolist() == [0, 1]

    slates, membership = evaluate_portfolio(panel, 2, 194.0)
    assert len(slates) == 2
    assert slates.selected_best.tolist() == [195.0, 195.0]
    assert slates.oracle.tolist() == [220.0, 220.0]
    assert not slates.oracle_selected.any()
    assert slates.oracle_new_worlds_after_portfolio.eq(0).all()
    assert slates.best_oracle_swap_coverage_delta.eq(-2).all()
    assert membership.portfolio_selected.sum() == 4

    summary = portfolio_summary(slates)
    assert summary["ge_194"] == 2
    assert summary["ge_200"] == 0
    assert summary["oracle_ge_200"] == 2
    assert summary["recoverable_ge_200"] == 2
    assert summary["mean_weekly_max"] == pytest.approx(195.0)
    assert len(missed_oracles(slates, 200.0)) == 2

    high = high_unselected_candidates(panel, membership, 200.0)
    assert len(high) == 2
    assert high.p_line_rank.eq(3).all()


def test_entry_count_caps_at_candidate_pool():
    panel = _panel()
    slates, membership = evaluate_portfolio(panel, 80, 194.0)
    assert slates.entry_count.eq(3).all()
    assert slates.oracle_selected.all()
    assert membership.portfolio_selected.all()


def test_swap_frontier_identifies_equivalent_and_costly_candidates():
    support = np.asarray([
        [1, 1, 0, 0],
        [0, 0, 1, 1],
        [1, 1, 0, 0],  # exact support substitute for selected candidate 0
        [1, 0, 0, 0],  # loses one uniquely covered world on its best swap
    ], dtype=bool)
    best, free = swap_frontier(support, np.asarray([0, 1]))
    assert best.tolist() == [0, 0, 0, -1]
    assert free.tolist() == [1, 1, 1, 0]
