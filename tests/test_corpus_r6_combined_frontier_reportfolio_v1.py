from __future__ import annotations

import numpy as np
import pytest

from nfl_dfs.research import corpus_r6_combined_frontier_reportfolio_v1 as subject


def _base(count: int = 160, worlds: int = 80):
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


def test_shortlist_is_deduplicated_in_canonical_union_order(monkeypatch):
    result, _ = _base()
    monkeypatch.setattr(subject.combined, "normalized_slate_for_grader_v1", lambda *a, **k: {})
    frontier = subject.derive_frontier_shortlist_v1(result, source_ordinal=0)
    assert frontier["candidate_count"] == 160
    assert frontier["candidate_lineup_ids"] == [f"L{i:03d}" for i in range(160)]
    assert frontier["shortlist_law"].startswith("union-of-eight-precomputed-k80")


@pytest.mark.parametrize("count", [149, 251])
def test_shortlist_fails_outside_dpp_candidate_envelope(monkeypatch, count):
    result, _ = _base(count)
    monkeypatch.setattr(subject.combined, "normalized_slate_for_grader_v1", lambda *a, **k: {})
    with pytest.raises(subject.CorpusR6CombinedFrontierReportfolioV1Error, match="150 through 250"):
        subject.derive_frontier_shortlist_v1(result, source_ordinal=0)


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
    tampered = scores.copy()
    tampered[0, 0] += 1.0
    with pytest.raises(subject.CorpusR6CombinedFrontierReportfolioV1Error, match="matrix identity"):
        subject.run_combined_frontier_reportfolio_v1(
            combined_result=result, all_block_score_matrix=tampered, source_ordinal=0
        )
