"""Outcome-blind re-portfolioing of the combined eight-book K80 frontier."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_r6_combined_population_all_block_v1 as combined
from nfl_dfs.research import corpus_r6_hard230_selector_bridge_v1 as hard_bridge
from nfl_dfs.research import corpus_r6_hard230_selector_confirmation_v1 as confirmation
from nfl_dfs.research import corpus_r6_selector_diversity_challengers_v1 as diversity


SCHEMA: Final = "corpus-r6-combined-frontier-reportfolio/v1"
MINIMUM_CANDIDATES: Final = 150
MAXIMUM_CANDIDATES: Final = 250
SOURCE_BOOK_COUNT: Final = 8
ENTRY_BUDGETS: Final = (80, 100, 150)


class CorpusR6CombinedFrontierReportfolioV1Error(ValueError):
    pass


def _fail(message: str) -> None:
    raise CorpusR6CombinedFrontierReportfolioV1Error(message)


def _canonical(value: object) -> bytes:
    return combined.batch.canonical_json_bytes(value)


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def derive_frontier_shortlist_v1(
    combined_result: object, *, source_ordinal: int
) -> dict[str, object]:
    """Replay the source result and derive its score-blind eight-K80 union."""
    combined.normalized_slate_for_grader_v1(
        combined_result, source_ordinal=source_ordinal
    )
    if not isinstance(combined_result, Mapping):
        _fail("combined result must be one object")
    result = dict(combined_result)
    union = dict(result["union"])
    rows = list(union["union_lineups"])
    books = list(result["books"])
    if len(books) != SOURCE_BOOK_COUNT:
        _fail("frontier requires exactly eight source K80 books")
    selected: set[str] = set()
    source_books: list[dict[str, object]] = []
    for book in books:
        if not isinstance(book, Mapping):
            _fail("source book must be one object")
        ids = [str(value) for value in book.get("selected_lineup_ids", [])]
        if book.get("entry_count") != 80 or len(ids) != 80 or len(set(ids)) != 80:
            _fail("frontier source book is not exact K80")
        selected.update(ids)
        source_books.append({
            "strategy_id": book["strategy_id"],
            "book_sha256": book["book_sha256"],
            "selected_lineup_ids_sha256": _hash(ids),
        })
    ordered_rows = [dict(row) for row in rows if str(row["lineup_id"]) in selected]
    ids = [str(row["lineup_id"]) for row in ordered_rows]
    if set(ids) != selected or ids != sorted(ids) or len(set(ids)) != len(ids):
        _fail("frontier shortlist does not preserve canonical union order")
    if not MINIMUM_CANDIDATES <= len(ids) <= MAXIMUM_CANDIDATES:
        _fail("frontier shortlist candidate count is outside 150 through 250")
    return {
        "shortlist_law": (
            "union-of-eight-precomputed-k80-books-filtered-by-ascending-"
            "canonical-union-lineup-order"
        ),
        "combined_result_sha256": result["result_sha256"],
        "union_sha256": union["union_sha256"],
        "later_source_identity": union["later_source_identity"],
        "source_books": source_books,
        "source_books_sha256": _hash(source_books),
        "candidate_count": len(ids),
        "candidate_lineup_ids": ids,
        "candidate_lineup_ids_sha256": _hash(ids),
        "candidate_rows": ordered_rows,
        "candidate_rows_sha256": _hash(ordered_rows),
    }


def run_combined_frontier_reportfolio_v1(
    *, combined_result: object, all_block_score_matrix: object,
    source_ordinal: int,
) -> dict[str, object]:
    """Run DPP, strict gamma-4/5, and strict-200 evil twin on one frontier."""
    frontier = derive_frontier_shortlist_v1(
        combined_result, source_ordinal=source_ordinal
    )
    result = dict(combined_result)  # validated above
    union_rows = list(result["union"]["union_lineups"])
    matrix_binding = dict(result["matrix_binding"])
    scores = np.asarray(all_block_score_matrix)
    expected_shape = tuple(matrix_binding["shape"])
    if (
        scores is not all_block_score_matrix
        or scores.dtype != np.dtype(np.float64)
        or not scores.flags.c_contiguous
        or scores.shape != expected_shape
        or scores.shape[0] != len(union_rows)
        or not np.isfinite(scores).all()
        or combined._score_matrix_sha256(scores)
        != matrix_binding["score_matrix_sha256"]
    ):
        _fail("combined all-block score matrix identity differs")
    union_index = {
        str(row["lineup_id"]): index for index, row in enumerate(union_rows)
    }
    ids = list(frontier["candidate_lineup_ids"])
    indices = np.asarray([union_index[lineup_id] for lineup_id in ids], dtype=np.int64)
    subset = np.ascontiguousarray(scores[indices], dtype=np.float64)
    candidates = list(frontier["candidate_rows"])
    by_id = {str(row["lineup_id"]): row for row in candidates}

    dpp_ids, dpp_diagnostics = hard_bridge._dpp_order(
        scores=subset, lineup_ids=ids, lineups_by_id=by_id
    )
    overlaps = diversity._roster_overlap_matrix(candidates)
    selectors: list[dict[str, object]] = []
    dpp_indices = [ids.index(lineup_id) for lineup_id in dpp_ids]
    selectors.append(diversity._selector_result(
        ordinal=3, strategy_id=hard_bridge.DPP_SELECTOR_ID,
        kind="effective-independent-tail-shots-dpp", selected=dpp_indices,
        trace=[], summary=dpp_diagnostics, lineup_ids=ids,
        candidates=candidates, scores=subset, roster_overlaps=overlaps,
    ))
    completed, diversity_contract_sha256 = confirmation._hard230_diversity_orders(
        scores=subset, candidates=candidates
    )
    selectors.extend(completed)
    body = {
        "schema_version": SCHEMA,
        "source_ordinal": source_ordinal,
        "slate_id": result["slate"]["slate_id"],
        "frontier": frontier,
        "frontier_sha256": _hash(frontier),
        "parent_score_matrix_sha256": matrix_binding["score_matrix_sha256"],
        "frontier_score_matrix_sha256": combined._score_matrix_sha256(subset),
        "frontier_score_shape": list(subset.shape),
        "selectors": selectors,
        "selectors_sha256": _hash(selectors),
        "diversity_contract_sha256": diversity_contract_sha256,
        "gamma_hard_cap_prefix_relaxed": False,
        "gamma_uncapped_tail_completion_disclosed": True,
        "population_regeneration_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "promotion_authority": False,
        "production_change_licensed": False,
    }
    return {**body, "result_sha256": _hash(body)}


def normalized_slate_for_grader_v1(
    value: object, *, source_ordinal: int
) -> dict[str, object]:
    """Validate and expose one shortlist population and twelve exact books."""
    if not isinstance(value, Mapping):
        _fail("frontier result must be one object")
    result = dict(value)
    body = {key: item for key, item in result.items() if key != "result_sha256"}
    if (
        result.get("schema_version") != SCHEMA
        or result.get("source_ordinal") != source_ordinal
        or result.get("result_sha256") != _hash(body)
        or result.get("uses_realized_outcomes") is not False
        or result.get("outcome_columns_read") != []
        or result.get("population_regeneration_performed") is not False
        or result.get("promotion_authority") is not False
        or result.get("gamma_hard_cap_prefix_relaxed") is not False
        or result.get("gamma_uncapped_tail_completion_disclosed") is not True
    ):
        _fail("frontier result authority differs")
    frontier = dict(result["frontier"])
    rows = list(frontier["candidate_rows"])
    ids = [str(row["lineup_id"]) for row in rows]
    if (
        frontier.get("candidate_count") != len(rows)
        or frontier.get("candidate_lineup_ids") != ids
        or frontier.get("candidate_lineup_ids_sha256") != _hash(ids)
        or frontier.get("candidate_rows_sha256") != _hash(rows)
        or result.get("frontier_sha256") != _hash(frontier)
    ):
        _fail("frontier result shortlist binding differs")
    selectors = list(result["selectors"])
    if len(selectors) != 4 or result.get("selectors_sha256") != _hash(selectors):
        _fail("frontier selector census differs")
    books: list[dict[str, object]] = []
    for selector in selectors:
        selector_body = {
            key: item for key, item in selector.items()
            if key != "selector_result_sha256"
        }
        if selector.get("selector_result_sha256") != _hash(selector_body):
            _fail("frontier selector result hash differs")
        entry_books = list(selector["entry_books"])
        if [book.get("entry_budget") for book in entry_books] != list(ENTRY_BUDGETS):
            _fail("frontier selector does not expose exact K80/K100/K150")
        for book in entry_books:
            book_body = {
                key: item for key, item in book.items() if key != "book_sha256"
            }
            if book.get("book_sha256") != _hash(book_body):
                _fail("frontier entry book hash differs")
            selected = [str(item) for item in book["selected_lineup_ids"]]
            if len(selected) != book["entry_budget"] or not set(selected) <= set(ids):
                _fail("frontier selected book differs")
            coordinate = {
                "adapter_id": "combined-frontier-reportfolio-v1",
                "metric_kind": "selected-book",
                "fit_scope_id": combined.FIT_SCOPE_ID,
                "selector_family": "combined-eight-k80-frontier-reportfolio-v1",
                "selector_id": selector["strategy_id"],
                "entry_budget": book["entry_budget"],
            }
            books.append({
                "coordinate": coordinate,
                "coordinate_sha256": _hash(coordinate),
                "population_id": "combined-eight-k80-frontier-shortlist-v1",
                "selected_lineup_ids": selected,
            })
    return {
        "source_ordinal": source_ordinal,
        "slate_id": result["slate_id"],
        "populations": [{
            "population_id": "combined-eight-k80-frontier-shortlist-v1",
            "dimensions": {
                "candidate_count": len(rows),
                "source_book_count": SOURCE_BOOK_COUNT,
                "fit_scope_id": combined.FIT_SCOPE_ID,
            },
            "lineups": [{
                "lineup_id": row["lineup_id"],
                "roster_player_ids": row["roster_player_ids"],
                "roster_sha256": _hash(row["roster_player_ids"]),
            } for row in rows],
        }],
        "books": books,
        "later_source_identity": result["frontier"].get("later_source_identity"),
    }
