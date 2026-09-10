from __future__ import annotations

import pytest

from nfl_dfs.research import corpus_r6_prefix_ranking_audit_v1 as audit


def _row(strategy: str, rank: int, score: int) -> dict[str, object]:
    return {
        "fit_scope_id": audit.FIT_SCOPE_ID,
        "strategy_id": strategy,
        "selection_rank": rank,
        "realized_score_micro": score,
        "marginal_trace": {
            "objective_gain": 80 - rank,
            "tie_break_values": {
                "training_mean_score": 80 - rank,
                "individual_selector_event_count": 80 - rank,
            },
            "base_trace": {
                "discovery_mean_score": 80 - rank,
                "discovery_primary_event_count": 80 - rank,
            },
        },
    }


def _shard(ordinal: int, *, hit_rank: int | None) -> dict[str, object]:
    strategy = "test-strategy"
    scores = [100_000_000 + rank for rank in range(80)]
    if hit_rank is not None:
        scores[hit_rank - 1] = 230_000_000
    selected = max(scores)
    eligible = 235_000_000 if ordinal < 2 else 180_000_000
    return {
        "source_ordinal": ordinal,
        "slate_id": f"slate-{ordinal}",
        "complete": True,
        "uses_realized_outcomes": True,
        "book_rows": [
            {
                "fit_scope_id": audit.FIT_SCOPE_ID,
                "strategy_id": strategy,
                "strategy_ordinal": 0,
                "selected_lineup_count": 80,
                "eligible_maximum_score_micro": eligible,
                "selected_maximum_score_micro": selected,
                "selector_regret_micro": eligible - selected,
            }
        ],
        "selection_rows": [
            _row(strategy, rank, score) for rank, score in enumerate(scores)
        ],
    }


def test_audit_separates_supply_selection_and_prefix_losses() -> None:
    result = audit.build_prefix_ranking_audit_v1(
        [_shard(0, hit_rank=57), _shard(1, hit_rank=None), _shard(2, hit_rank=None)],
        source_binding={"fixture": True},
        expected_slate_count=3,
        expected_strategy_count=1,
    )
    strategy = result["strategy_summaries"][0]
    row_230 = next(
        row for row in strategy["threshold_rows"] if row["threshold_dk"] == 230
    )
    assert row_230["eligible_supply_slate_count"] == 2
    assert row_230["full_book_capture_slate_count"] == 1
    prefix_40 = next(
        row for row in row_230["prefixes"] if row["entry_count"] == 40
    )
    assert prefix_40 == {
        "entry_count": 40,
        "no_eligible_supply_slate_count": 1,
        "eligible_but_full_book_miss_slate_count": 1,
        "full_book_hit_but_below_prefix_slate_count": 1,
        "prefix_capture_slate_count": 0,
    }
    prefix_57 = next(
        row for row in row_230["prefixes"] if row["entry_count"] == 57
    )
    assert prefix_57["prefix_capture_slate_count"] == 1
    assert prefix_57["full_book_hit_but_below_prefix_slate_count"] == 0
    assert row_230["first_hit_rank_1_based_mean"] == {
        "numerator": 57,
        "denominator": 1,
        "unit": "selected_capture_slates",
    }
    assert strategy["best_selected_lineup_rank_1_based_median"] == {
        "numerator": 80,
        "denominator": 1,
    }
    priority = next(
        row
        for row in strategy["metric_correlations"]
        if row["metric"] == "selection_priority"
    )
    assert priority["observed_slate_count"] == 3
    assert result["promotion_authority"] is False
    assert result["raw_outcome_query_performed"] is False


def test_audit_rejects_noncontiguous_source_grid() -> None:
    with pytest.raises(audit.CorpusR6PrefixRankingAuditV1Error, match="ordinal grid"):
        audit.build_prefix_ranking_audit_v1(
            [_shard(0, hit_rank=None), _shard(2, hit_rank=None)],
            source_binding={"fixture": True},
            expected_slate_count=2,
            expected_strategy_count=1,
        )


def test_audit_rejects_book_maximum_drift() -> None:
    shard = _shard(0, hit_rank=1)
    shard["book_rows"][0]["selected_maximum_score_micro"] += 1
    with pytest.raises(audit.CorpusR6PrefixRankingAuditV1Error, match="maximum/regret"):
        audit.build_prefix_ranking_audit_v1(
            [shard],
            source_binding={"fixture": True},
            expected_slate_count=1,
            expected_strategy_count=1,
        )
