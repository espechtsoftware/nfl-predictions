from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.tail_portfolio import (
    combine_slate_portfolios,
    decode_clear_bits,
    evaluate_portfolio,
    evaluate_hybrid_portfolio,
    evaluate_ranked_portfolio,
    high_unselected_candidates,
    missed_oracles,
    portfolio_summary,
    refine_one_swap,
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
    assert slates.closest_selected_support_jaccard.eq(0).all()
    assert slates.closest_selected_roster_overlap.eq(0).all()
    assert slates.selected_support_superset_count.eq(2).all()
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


def test_ranked_portfolio_is_stable_and_outcome_blind():
    panel = _panel()
    # All three p_line values are 0.5, 0.5, 0.0. Stable cand_ix tie-breaking
    # therefore takes candidate zero first and never sees the realized score.
    slates, membership = evaluate_ranked_portfolio(panel, 1, "p_line")
    assert slates.selected_best.tolist() == [190.0, 190.0]
    assert not slates.oracle_selected.any()
    picked = membership[membership.portfolio_selected]
    assert picked.cand_ix.eq(0).all()
    assert portfolio_summary(slates)["ge_200"] == 0

    with pytest.raises(ValueError, match="candidate panel missing"):
        evaluate_ranked_portfolio(panel, 1, "does_not_exist")


def test_hybrid_portfolio_keeps_exact_budget_and_excludes_duplicates():
    panel = _panel()
    # Coverage takes candidate 0. The rank hedge skips it and takes candidate
    # 1, preserving two distinct entries even though the ranking is tied.
    slates, membership = evaluate_hybrid_portfolio(
        panel, coverage_entries=1, ranked_entries=1, rank_column="p_line")
    assert slates.entry_count.eq(2).all()
    assert slates.coverage_entries.eq(1).all()
    assert slates.ranked_entries.eq(1).all()
    assert slates.selected_best.tolist() == [195.0, 195.0]
    for _, slate in membership.groupby(["season", "week"]):
        assert slate[slate.portfolio_selected].cand_ix.tolist() == [0, 1]

    pure_ranked, _ = evaluate_hybrid_portfolio(
        panel, coverage_entries=0, ranked_entries=1, rank_column="p_line")
    assert pure_ranked.selected_best.tolist() == [190.0, 190.0]
    with pytest.raises(ValueError, match="at least one"):
        evaluate_hybrid_portfolio(panel, 0, 0, "p_line")


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


def test_one_swap_refinement_improves_coverage_then_tiebreaks():
    support = np.asarray([
        [1, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 1, 1],  # adds one covered world in place of candidate 1
        [1, 1, 0, 0],  # equal support but higher p_line than candidate 0
    ], dtype=bool)
    refined, trace = refine_one_swap(
        support,
        p_line=np.asarray([0.2, 0.2, 0.1, 0.3]),
        mean_total=np.asarray([150.0, 150.0, 149.0, 151.0]),
        picked=np.asarray([0, 1]),
    )
    assert refined.tolist() == [3, 2]
    assert [step["coverage_delta"] for step in trace] == [1, 0]
    assert np.any(support[refined], axis=0).sum() == 4


def _slate_summary(best: list[float], oracle: list[float], entries: int = 40
                   ) -> pd.DataFrame:
    return pd.DataFrame({
        "season": [2024, 2025],
        "week": [1, 2],
        "selected_best": best,
        "oracle": oracle,
        "select_line": [194.0, 194.0],
        "entry_count": [entries, entries],
    })


def test_combine_slate_portfolios_scores_union_without_reselection():
    left = _slate_summary([205.0, 180.0], [210.0, 190.0])
    right = _slate_summary([190.0, 215.0], [208.0, 220.0])
    mixed = combine_slate_portfolios(left, right, 40, 40)
    assert mixed.selected_best.tolist() == [205.0, 215.0]
    assert mixed.oracle.tolist() == [210.0, 220.0]
    assert mixed.regret.tolist() == [5.0, 5.0]
    assert mixed.entry_count.eq(80).all()
    assert mixed.left_entries.eq(40).all()
    assert mixed.right_entries.eq(40).all()


def test_combine_slate_portfolios_validates_allocation_and_slate_keys():
    left = _slate_summary([205.0, 180.0], [210.0, 190.0], entries=80)
    pure = combine_slate_portfolios(left, pd.DataFrame(), 80, 0)
    assert pure.selected_best.tolist() == left.selected_best.tolist()
    assert pure.right_best.isna().all()

    right = _slate_summary([190.0, 215.0], [208.0, 220.0])
    right.loc[1, "week"] = 3
    with pytest.raises(ValueError, match="same slates"):
        combine_slate_portfolios(
            _slate_summary([205.0, 180.0], [210.0, 190.0]),
            right, 40, 40)
    with pytest.raises(ValueError, match="at least one"):
        combine_slate_portfolios(pd.DataFrame(), pd.DataFrame(), 0, 0)
