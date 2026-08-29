from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import corpus_r6_combined_frontier_reportfolio_v1 as subject


def _base(count: int = 300, worlds: int = 80):
    rows = [{
        "lineup_id": f"L{index:03d}",
        "roster_player_ids": [f"P{index:03d}-{slot}" for slot in range(9)],
    } for index in range(count)]
    # Eight exact K80 books whose union covers every row for count <= 250.
    books = []
    for ordinal in range(8):
        start = (ordinal * 32) % count
        ids = [rows[(start + offset) % count]["lineup_id"] for offset in range(80)]
        books.append({
            "strategy_id": f"S{ordinal}", "book_sha256": "a" * 64,
            "entry_count": 80, "selected_lineup_ids": ids,
        })
    scores = np.random.default_rng(7).normal(205.0, 25.0, (count, worlds))
    scores = np.ascontiguousarray(scores, dtype=np.float64)
    result = {
        "result_sha256": "b" * 64,
        "slate": {"slate_id": "2023-w01"},
        "union": {
            "union_sha256": "c" * 64,
            "later_source_identity": {"uri": "gs://example/freeze", "generation": "1"},
            "union_lineups": rows,
        },
        "books": books,
        "matrix_binding": {
            "shape": list(scores.shape),
            "score_matrix_sha256": subject.combined._score_matrix_sha256(scores),
        },
    }
    return result, scores


def test_complete_union_sieve_is_exact_and_canonical(monkeypatch):
    result, scores = _base()
    monkeypatch.setattr(subject.combined, "normalized_slate_for_grader_v1", lambda *a, **k: {})
    frontier = subject.derive_frontier_shortlist_v1(
        result, all_block_score_matrix=scores, source_ordinal=0
    )
    assert frontier["complete_union_lineup_count"] == 300
    assert frontier["candidate_count"] == subject.SIEVE_LIMIT == 250
    assert frontier["candidate_lineup_ids"] == sorted(
        frontier["candidate_lineup_ids"]
    )
    assert frontier["shortlist_law"] == subject.SIEVE_LAW
    assert frontier["old_book_membership_used_for_sieve"] is False


@pytest.mark.parametrize("count", [149, 250])
def test_shortlist_requires_more_than_exact_sieve_size(monkeypatch, count):
    result, scores = _base(count)
    monkeypatch.setattr(subject.combined, "normalized_slate_for_grader_v1", lambda *a, **k: {})
    with pytest.raises(
        subject.CorpusR6CombinedFrontierReportfolioV1Error,
        match="exceed exact 250-row sieve",
    ):
        subject.derive_frontier_shortlist_v1(
            result, all_block_score_matrix=scores, source_ordinal=0
        )


def test_high_tail_candidate_absent_from_every_old_book_remains_eligible(monkeypatch):
    result, scores = _base()
    first_eighty = [f"L{index:03d}" for index in range(80)]
    for book in result["books"]:
        book["selected_lineup_ids"] = list(first_eighty)
    scores[299, :] = 300.0
    result["matrix_binding"]["score_matrix_sha256"] = (
        subject.combined._score_matrix_sha256(scores)
    )
    monkeypatch.setattr(
        subject.combined, "normalized_slate_for_grader_v1", lambda *a, **k: {}
    )
    frontier = subject.derive_frontier_shortlist_v1(
        result, all_block_score_matrix=scores, source_ordinal=0
    )
    assert "L299" in frontier["candidate_lineup_ids"]
    assert frontier["prior_eight_book_union_count"] == 80
    assert frontier["candidate_absent_from_prior_eight_books_count"] > 0


def test_exact_float64_mean_breaks_micro_rounded_cutoff_tie(monkeypatch):
    result, scores = _base()
    scores.fill(100.0)
    scores[299, :] = 100.0000004
    result["matrix_binding"]["score_matrix_sha256"] = (
        subject.combined._score_matrix_sha256(scores)
    )
    monkeypatch.setattr(
        subject.combined, "normalized_slate_for_grader_v1", lambda *a, **k: {}
    )
    frontier = subject.derive_frontier_shortlist_v1(
        result, all_block_score_matrix=scores, source_ordinal=0
    )
    assert "L299" in frontier["candidate_lineup_ids"]
    assert "L249" not in frontier["candidate_lineup_ids"]
    by_id = {
        item["lineup_id"]: item for item in frontier["candidate_sieve_evidence"]
    }
    assert by_id["L299"]["modeled_world_mean_micro"] == (
        by_id["L000"]["modeled_world_mean_micro"]
    )
    assert by_id["L299"]["modeled_world_mean_float64_hex"] != (
        by_id["L000"]["modeled_world_mean_float64_hex"]
    )


@pytest.mark.parametrize("prefix_count", [60, 90, 120])
def test_gamma_exhaustion_completion_is_exact_nested_and_truthful(
    monkeypatch, prefix_count
):
    candidates = [{
        "lineup_id": f"X{index:03d}",
        "roster_player_ids": [
            f"PX{index:03d}-{slot}" for slot in range(9)
        ],
    } for index in range(160)]
    scores = np.ascontiguousarray(
        np.random.default_rng(19).normal(205.0, 25.0, (160, 80)),
        dtype=np.float64,
    )

    def _exhausted_prefix(**kwargs):
        selected = list(range(prefix_count))
        trace = [{
            "selection_rank": rank,
            "canonical_lineup_index": rank,
            "lineup_id": kwargs["lineup_ids"][rank],
            "marginal_weighted_tail_ladder_utility": 0,
            "individual_strict_gt_200_world_count": int(
                kwargs["primary_counts"][rank]
            ),
            "fit_world_mean_score_micro": subject.diversity._micro(
                float(kwargs["means"][rank]), label="fit world mean score"
            ),
            "maximum_overlap_with_prior_roster": 0,
            "overlap_cap": kwargs["gamma"],
        } for rank in selected]
        return selected, trace, {
            "unselected_feasible_candidate_count_at_stop": 0,
        }

    monkeypatch.setattr(
        subject.diversity, "_run_overlap_cap_order", _exhausted_prefix
    )
    selectors, _contract = subject._frontier_gamma_and_evil_orders_v1(
        scores=scores, candidates=candidates
    )
    assert [selector["strategy_id"] for selector in selectors[:2]] == list(
        subject.FRONTIER_GAMMA_SELECTOR_IDS
    )
    expected_flags = [
        prefix_count >= budget for budget in subject.ENTRY_BUDGETS
    ]
    for gamma, selector in zip((4, 5), selectors[:2], strict=True):
        ranked = selector["ranked_lineup_ids"]
        summary = selector["selector_summary"]
        assert len(ranked) == 150
        assert len(set(ranked)) == 150
        assert [book["entry_budget"] for book in selector["entry_books"]] == [
            80, 100, 150
        ]
        assert all(
            book["selected_lineup_ids"] == ranked[: book["entry_budget"]]
            for book in selector["entry_books"]
        )
        assert summary["hard_cap_greedy_prefix_count"] == prefix_count
        assert summary["hard_cap_prefix_rank_range"] == [0, prefix_count - 1]
        assert summary["hard_cap_prefix_lineup_ids"] == [
            f"X{index:03d}" for index in range(prefix_count)
        ]
        assert summary["hard_cap_relaxed_within_prefix"] is False
        assert summary["no_relax_within_hard_cap_prefix"] is True
        assert summary["completion_count"] == 150 - prefix_count
        assert summary["completion_rank_range"] == [prefix_count, 149]
        assert summary["completion_overlap_cap_enforced"] is False
        assert summary[
            "completed_book_global_cap_compliance_claimed"
        ] is False
        assert [
            row["hard_cap_enforced_for_every_rank"]
            for row in summary["entry_budget_cap_compliance"]
        ] == expected_flags
        assert [
            row["hard_cap_compliance_claimed"]
            for row in summary["entry_budget_cap_compliance"]
        ] == expected_flags
        assert all(
            row["observed_maximum_pairwise_roster_overlap"] == 0
            and row["observed_pairwise_overlap_le_gamma"] is True
            for row in summary["entry_budget_cap_compliance"]
        )
        assert summary[
            "hard_cap_prefix_maximum_pairwise_roster_overlap"
        ] <= gamma


def test_core_emits_four_nested_exact_selectors_and_rejects_matrix_tamper(monkeypatch):
    result, scores = _base()
    monkeypatch.setattr(subject.combined, "normalized_slate_for_grader_v1", lambda *a, **k: {})
    built = subject.run_combined_frontier_reportfolio_v1(
        combined_result=result, all_block_score_matrix=scores, source_ordinal=0
    )
    assert len(built["selectors"]) == 4
    assert built["gamma_hard_cap_prefix_relaxed"] is False
    assert built["gamma_uncapped_tail_completion_disclosed"] is True
    assert all(
        [book["entry_budget"] for book in selector["entry_books"]] == [80, 100, 150]
        for selector in built["selectors"]
    )
    normalized = subject.normalized_slate_for_grader_v1(built, source_ordinal=0)
    assert len(normalized["books"]) == 12
    licensed = deepcopy(built)
    licensed["selectors"][0]["policy"]["production_change_licensed"] = True
    selector_body = {
        key: value for key, value in licensed["selectors"][0].items()
        if key != "selector_result_sha256"
    }
    licensed["selectors"][0]["selector_result_sha256"] = subject._hash(
        selector_body
    )
    licensed["selectors_sha256"] = subject._hash(licensed["selectors"])
    result_body = {
        key: value for key, value in licensed.items() if key != "result_sha256"
    }
    licensed["result_sha256"] = subject._hash(result_body)
    with pytest.raises(
        subject.CorpusR6CombinedFrontierReportfolioV1Error,
        match="selector result hash differs",
    ):
        subject.normalized_slate_for_grader_v1(licensed, source_ordinal=0)
    top_level_licensed = deepcopy(built)
    top_level_licensed["production_change_licensed"] = True
    result_body = {
        key: value for key, value in top_level_licensed.items()
        if key != "result_sha256"
    }
    top_level_licensed["result_sha256"] = subject._hash(result_body)
    with pytest.raises(
        subject.CorpusR6CombinedFrontierReportfolioV1Error,
        match="frontier result authority differs",
    ):
        subject.normalized_slate_for_grader_v1(
            top_level_licensed, source_ordinal=0
        )
    outcome_licensed = deepcopy(built)
    outcome_licensed["selectors"][0]["policy"][
        "uses_realized_outcomes"
    ] = True
    selector_body = {
        key: value for key, value in outcome_licensed["selectors"][0].items()
        if key != "selector_result_sha256"
    }
    outcome_licensed["selectors"][0]["selector_result_sha256"] = (
        subject._hash(selector_body)
    )
    outcome_licensed["selectors_sha256"] = subject._hash(
        outcome_licensed["selectors"]
    )
    result_body = {
        key: value for key, value in outcome_licensed.items()
        if key != "result_sha256"
    }
    outcome_licensed["result_sha256"] = subject._hash(result_body)
    with pytest.raises(
        subject.CorpusR6CombinedFrontierReportfolioV1Error,
        match="selector result hash differs",
    ):
        subject.normalized_slate_for_grader_v1(
            outcome_licensed, source_ordinal=0
        )
    false_global_claim = deepcopy(built)
    false_global_claim["selectors"][1]["selector_summary"][
        "hard_cap_global_maximum_feasible_cardinality_claimed"
    ] = True
    selector_body = {
        key: value for key, value in false_global_claim["selectors"][1].items()
        if key != "selector_result_sha256"
    }
    false_global_claim["selectors"][1]["selector_result_sha256"] = (
        subject._hash(selector_body)
    )
    false_global_claim["selectors_sha256"] = subject._hash(
        false_global_claim["selectors"]
    )
    result_body = {
        key: value for key, value in false_global_claim.items()
        if key != "result_sha256"
    }
    false_global_claim["result_sha256"] = subject._hash(result_body)
    with pytest.raises(
        subject.CorpusR6CombinedFrontierReportfolioV1Error,
        match="frontier gamma completion summary differs",
    ):
        subject.normalized_slate_for_grader_v1(
            false_global_claim, source_ordinal=0
        )
    tampered = scores.copy()
    tampered[0, 0] += 1.0
    with pytest.raises(subject.CorpusR6CombinedFrontierReportfolioV1Error, match="matrix identity"):
        subject.run_combined_frontier_reportfolio_v1(
            combined_result=result, all_block_score_matrix=tampered, source_ordinal=0
        )
