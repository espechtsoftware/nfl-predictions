"""Outcome-blind re-portfolioing from the complete combined union.

Quadratic DPP/diversity kernels are bounded to 250 candidates.  The complete
persisted combined union is therefore screened first using only modeled tail
evidence from its already-bound 50,000-world matrix.  Membership in the eight
old K80 books is diagnostic only and never an eligibility input.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_r6_combined_population_all_block_v1 as combined
from nfl_dfs.research import corpus_r6_hard230_selector_bridge_v1 as hard_bridge
from nfl_dfs.research import corpus_r6_hard230_selector_confirmation_v1 as confirmation
from nfl_dfs.research import corpus_r6_selector_diversity_challengers_v1 as diversity


SCHEMA: Final = "corpus-r6-combined-frontier-reportfolio/v3"
MINIMUM_CANDIDATES: Final = 150
MAXIMUM_CANDIDATES: Final = 250
SOURCE_BOOK_COUNT: Final = 8
ENTRY_BUDGETS: Final = (80, 100, 150)
FRONTIER_GAMMA_SELECTOR_IDS: Final = (
    "frontier-tail-ladder-overlap-cap-4-exhaustive-prefix-then-fill-v1",
    "frontier-tail-ladder-overlap-cap-5-exhaustive-prefix-then-fill-v1",
)
FRONTIER_GAMMA_COMPLETION_LAW_ID: Final = (
    "frontier-hard-cap-prefix-until-exhaustion-then-unconstrained-fill-v1"
)
FRONTIER_GAMMA_COMPLETION_LAW_SCHEMA: Final = (
    "corpus-r6-combined-frontier-gamma-completion-law/v1"
)
FRONTIER_GAMMA_SUMMARY_SCHEMA: Final = (
    "corpus-r6-combined-frontier-gamma-completion-summary/v1"
)
FRONTIER_GAMMA_SUMMARY_FIELDS: Final = frozenset({
    "schema_version", "completion_law_id", "overlap_cap",
    "hard_cap_greedy_prefix_count", "hard_cap_prefix_rank_range",
    "hard_cap_prefix_lineup_ids", "hard_cap_prefix_lineup_ids_sha256",
    "hard_cap_relaxed_within_prefix", "no_relax_within_hard_cap_prefix",
    "hard_cap_unselected_feasible_candidate_count_at_stop",
    "hard_cap_global_maximum_feasible_cardinality_claimed",
    "completion_performed", "completion_count", "completion_rank_range",
    "completion_lineup_ids", "completion_lineup_ids_sha256",
    "completion_overlap_cap_enforced",
    "completed_book_global_cap_compliance_claimed",
    "entry_budget_cap_compliance",
    "hard_cap_prefix_maximum_pairwise_roster_overlap",
    "completed_order_maximum_pairwise_roster_overlap",
    "final_ranking_depth_reached",
})
SELECTOR_IDS: Final = (
    hard_bridge.DPP_SELECTOR_ID,
    *FRONTIER_GAMMA_SELECTOR_IDS,
    confirmation.DIVERSITY_IDS[2],
)
SIEVE_LIMIT: Final = MAXIMUM_CANDIDATES
SIEVE_CHUNK_ROWS: Final = 64
SIEVE_THRESHOLDS: Final = (230.0, 220.0, 210.0, 200.0)
SIEVE_LAW: Final = (
    "complete-union-modeled-tail-lexicographic-top250-float64-v2"
)
MEAN_VECTOR_SCHEMA: Final = "modeled-world-mean-float64-vector-binding/v1"


class CorpusR6CombinedFrontierReportfolioV1Error(ValueError):
    pass


def _fail(message: str) -> None:
    raise CorpusR6CombinedFrontierReportfolioV1Error(message)


def _canonical(value: object) -> bytes:
    return combined.batch.canonical_json_bytes(value)


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _digest(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def frontier_gamma_completion_law_v1() -> dict[str, object]:
    body = {
        "schema_version": FRONTIER_GAMMA_COMPLETION_LAW_SCHEMA,
        "law_id": FRONTIER_GAMMA_COMPLETION_LAW_ID,
        "base_kernel_contract_sha256": diversity.diversity_challenger_contract_v1()[
            "contract_sha256"
        ],
        "selector_ids": list(FRONTIER_GAMMA_SELECTOR_IDS),
        "overlap_caps": [4, 5],
        "hard_cap_prefix_law": (
            "registered-greedy-overlap-cap-prefix-preserved-until-exhaustion"
        ),
        "hard_cap_prefix_minimum_count": None,
        "completion_law": (
            "frozen-tail-ladder-over-remaining-candidates-from-prefix-coverage"
        ),
        "completion_overlap_cap_enforced": False,
        "completed_book_global_cap_compliance_claimed": False,
        "entry_budgets": list(ENTRY_BUDGETS),
        "uses_realized_outcomes": False,
    }
    return {**body, "law_sha256": _hash(body)}


def _maximum_pairwise_overlap_v1(
    *, selected: Sequence[int], roster_overlaps: np.ndarray
) -> int:
    indices = list(selected)
    if len(indices) < 2:
        return 0
    subset = roster_overlaps[np.ix_(indices, indices)]
    return int(subset[np.triu_indices(len(indices), k=1)].max())


def _validated_parent_v1(
    *, combined_result: object, all_block_score_matrix: object,
    source_ordinal: int,
) -> tuple[dict[str, object], list[dict[str, object]], np.ndarray]:
    combined.normalized_slate_for_grader_v1(
        combined_result, source_ordinal=source_ordinal
    )
    if not isinstance(combined_result, Mapping):
        _fail("combined result must be one object")
    result = dict(combined_result)
    union = dict(result["union"])
    rows = [dict(row) for row in union["union_lineups"]]
    matrix_binding = dict(result["matrix_binding"])
    scores = np.asarray(all_block_score_matrix)
    expected_shape = tuple(matrix_binding["shape"])
    if (
        scores is not all_block_score_matrix
        or scores.dtype != np.dtype(np.float64)
        or not scores.flags.c_contiguous
        or scores.shape != expected_shape
        or scores.shape[0] != len(rows)
        or not np.isfinite(scores).all()
        or combined._score_matrix_sha256(scores)
        != matrix_binding["score_matrix_sha256"]
    ):
        _fail("combined all-block score matrix identity differs")
    return result, rows, scores


def derive_frontier_shortlist_v1(
    combined_result: object, *, all_block_score_matrix: object,
    source_ordinal: int,
) -> dict[str, object]:
    """Screen the complete union by a fixed modeled-tail quality tuple."""
    result, rows, scores = _validated_parent_v1(
        combined_result=combined_result,
        all_block_score_matrix=all_block_score_matrix,
        source_ordinal=source_ordinal,
    )
    union = dict(result["union"])
    if len(rows) <= SIEVE_LIMIT:
        _fail("complete combined union must exceed exact 250-row sieve")

    threshold_counts = [
        np.empty(len(rows), dtype=np.int64) for _threshold in SIEVE_THRESHOLDS
    ]
    mean_float64 = np.empty(len(rows), dtype=np.float64)
    mean_micro = np.empty(len(rows), dtype=np.int64)
    for start in range(0, len(rows), SIEVE_CHUNK_ROWS):
        stop = min(start + SIEVE_CHUNK_ROWS, len(rows))
        chunk = scores[start:stop]
        for counts, threshold in zip(
            threshold_counts, SIEVE_THRESHOLDS, strict=True
        ):
            counts[start:stop] = np.count_nonzero(
                chunk > threshold, axis=1
            )
        chunk_means = chunk.mean(axis=1, dtype=np.float64)
        scaled = np.rint(chunk_means * np.float64(1_000_000))
        if not np.isfinite(chunk_means).all() or not np.isfinite(scaled).all():
            _fail("complete-union sieve mean is not finite")
        mean_float64[start:stop] = chunk_means
        mean_micro[start:stop] = scaled.astype(np.int64)

    mean_little_endian = np.ascontiguousarray(mean_float64, dtype=np.dtype("<f8"))
    mean_vector_metadata = {
        "schema_version": MEAN_VECTOR_SCHEMA,
        "dtype": "<f8",
        "shape": [len(rows)],
        "order": "C",
        "reduction": "numpy-mean-axis-1-dtype-float64",
    }
    mean_vector_payload_sha256 = sha256(
        mean_little_endian.tobytes(order="C")
    ).hexdigest()
    mean_vector_binding_sha256 = _hash({
        "metadata": mean_vector_metadata,
        "payload_sha256": mean_vector_payload_sha256,
    })

    evidence = [{
        "lineup_id": str(row["lineup_id"]),
        "strict_gt_230_world_count": int(threshold_counts[0][index]),
        "strict_gt_220_world_count": int(threshold_counts[1][index]),
        "strict_gt_210_world_count": int(threshold_counts[2][index]),
        "strict_gt_200_world_count": int(threshold_counts[3][index]),
        "modeled_world_mean_float64_hex": float(mean_float64[index]).hex(),
        "modeled_world_mean_micro": int(mean_micro[index]),
    } for index, row in enumerate(rows)]
    ranked = sorted(
        range(len(rows)),
        key=lambda index: (
            -int(threshold_counts[0][index]),
            -int(threshold_counts[1][index]),
            -int(threshold_counts[2][index]),
            -int(threshold_counts[3][index]),
            -float(mean_float64[index]),
            str(rows[index]["lineup_id"]),
        ),
    )
    selected_ranked = ranked[:SIEVE_LIMIT]
    selected_set = set(selected_ranked)
    selected_indices = [
        index for index in range(len(rows)) if index in selected_set
    ]
    rank_by_index = {
        index: rank for rank, index in enumerate(selected_ranked)
    }
    ordered_rows = [rows[index] for index in selected_indices]
    candidate_ids = [str(row["lineup_id"]) for row in ordered_rows]
    selected_evidence = [{
        **evidence[index], "sieve_rank": rank_by_index[index]
    } for index in selected_indices]

    books = list(result["books"])
    if len(books) != SOURCE_BOOK_COUNT:
        _fail("complete-union sieve requires exactly eight predecessor books")
    prior_selected: set[str] = set()
    source_books: list[dict[str, object]] = []
    for book in books:
        if not isinstance(book, Mapping):
            _fail("source book must be one object")
        book_ids = [str(value) for value in book.get("selected_lineup_ids", [])]
        if (
            book.get("entry_count") != 80
            or len(book_ids) != 80
            or len(set(book_ids)) != 80
        ):
            _fail("frontier source book is not exact K80")
        prior_selected.update(book_ids)
        source_books.append({
            "strategy_id": book["strategy_id"],
            "book_sha256": book["book_sha256"],
            "selected_lineup_ids_sha256": _hash(book_ids),
        })
    if (
        len(candidate_ids) != SIEVE_LIMIT
        or candidate_ids
        != [str(rows[index]["lineup_id"]) for index in selected_indices]
        or len(set(candidate_ids)) != len(candidate_ids)
    ):
        _fail("complete-union modeled-tail sieve differs")
    prior_selected_in_union = {
        str(row["lineup_id"])
        for row in rows
        if str(row["lineup_id"]) in prior_selected
    }
    if prior_selected_in_union != prior_selected:
        _fail("predecessor book refers outside complete union")
    selected_from_prior = sum(
        lineup_id in prior_selected for lineup_id in candidate_ids
    )
    return {
        "shortlist_law": SIEVE_LAW,
        "sieve_ranking_tuple": [
            "descending-strict-gt-230-world-count",
            "descending-strict-gt-220-world-count",
            "descending-strict-gt-210-world-count",
            "descending-strict-gt-200-world-count",
            "descending-modeled-world-mean-float64",
            "ascending-lineup-id",
        ],
        "sieve_threshold_operators": [
            {"threshold_dk": threshold, "operator": ">"}
            for threshold in SIEVE_THRESHOLDS
        ],
        "sieve_limit": SIEVE_LIMIT,
        "combined_result_sha256": result["result_sha256"],
        "union_sha256": union["union_sha256"],
        "later_source_identity": union["later_source_identity"],
        "complete_union_lineup_count": len(rows),
        "complete_union_lineup_ids_sha256": _hash([
            row["lineup_id"] for row in rows
        ]),
        "complete_union_sieve_evidence_sha256": _hash(evidence),
        "complete_union_modeled_world_mean_vector_metadata": (
            mean_vector_metadata
        ),
        "complete_union_modeled_world_mean_vector_payload_sha256": (
            mean_vector_payload_sha256
        ),
        "complete_union_modeled_world_mean_vector_binding_sha256": (
            mean_vector_binding_sha256
        ),
        "complete_union_score_matrix_sha256": result["matrix_binding"][
            "score_matrix_sha256"
        ],
        "source_books": source_books,
        "source_books_sha256": _hash(source_books),
        "old_book_membership_used_for_sieve": False,
        "prior_eight_book_union_count": len(prior_selected),
        "prior_eight_book_union_lineup_ids_sha256": _hash(sorted(prior_selected)),
        "candidate_count": len(candidate_ids),
        "candidate_lineup_ids": candidate_ids,
        "candidate_lineup_ids_sha256": _hash(candidate_ids),
        "candidate_rows": ordered_rows,
        "candidate_rows_sha256": _hash(ordered_rows),
        "candidate_sieve_evidence": selected_evidence,
        "candidate_sieve_evidence_sha256": _hash(selected_evidence),
        "candidate_in_prior_eight_books_count": selected_from_prior,
        "candidate_absent_from_prior_eight_books_count": (
            len(candidate_ids) - selected_from_prior
        ),
    }


def _frontier_gamma_and_evil_orders_v1(
    *, scores: np.ndarray, candidates: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], str]:
    """Preserve each frozen gamma prefix, then truthfully complete to K150."""
    lineup_ids = [str(row["lineup_id"]) for row in candidates]
    masks = diversity._pack_strict_masks(scores)
    primary_counts = diversity._row_counts(masks[0])
    means = scores.mean(axis=1, dtype=np.float64)
    overlaps = diversity._roster_overlap_matrix(candidates)
    selectors: list[dict[str, object]] = []
    for ordinal, gamma in enumerate((4, 5)):
        selected, trace, hard_cap_summary = diversity._run_overlap_cap_order(
            gamma=gamma,
            lineup_ids=lineup_ids,
            masks=masks,
            primary_counts=primary_counts,
            means=means,
            roster_overlaps=overlaps,
        )
        prefix = list(selected)
        prefix_count = len(prefix)
        if not 0 < prefix_count <= ENTRY_BUDGETS[-1]:
            _fail("frontier gamma hard-cap prefix count differs")
        retained_trace = [{
            **dict(row),
            "selection_role": "hard-roster-overlap-cap-prefix",
            "overlap_cap_enforced": True,
        } for row in trace]
        if prefix_count < ENTRY_BUDGETS[-1]:
            covered = [
                np.zeros(mask.shape[1], dtype=np.uint8) for mask in masks
            ]
            remaining = np.ones(len(lineup_ids), dtype=bool)
            for candidate in selected:
                remaining[candidate] = False
                for mask, seen in zip(masks, covered, strict=True):
                    seen |= mask[candidate]
            while len(selected) < ENTRY_BUDGETS[-1]:
                utilities = diversity._fresh_utilities(
                    masks=masks, covered=covered
                )
                best = diversity._best_ladder_candidate(
                    eligible=remaining,
                    utilities=utilities,
                    primary_counts=primary_counts,
                    means=means,
                    lineup_ids=lineup_ids,
                )
                if best is None:
                    _fail("frontier gamma completion lacks exact K150")
                maximum_prior_overlap = int(
                    overlaps[best, selected].max()
                ) if selected else 0
                retained_trace.append({
                    "selection_rank": len(selected),
                    "canonical_lineup_index": best,
                    "lineup_id": lineup_ids[best],
                    "selection_role": "unconstrained-tail-ladder-completion",
                    "marginal_weighted_tail_ladder_utility": int(
                        utilities[best]
                    ),
                    "individual_strict_gt_200_world_count": int(
                        primary_counts[best]
                    ),
                    "fit_world_mean_score_micro": diversity._micro(
                        float(means[best]), label="fit world mean score"
                    ),
                    "maximum_overlap_with_prior_roster": maximum_prior_overlap,
                    "overlap_cap": gamma,
                    "overlap_cap_enforced": False,
                })
                diversity._append_selection(
                    candidate=best,
                    selected=selected,
                    remaining=remaining,
                    masks=masks,
                    covered=covered,
                )
        completion_count = len(selected) - prefix_count
        prefix_ids = [lineup_ids[index] for index in prefix]
        completion_ids = [
            lineup_ids[index] for index in selected[prefix_count:]
        ]
        budget_compliance = []
        for budget in ENTRY_BUDGETS:
            budget_selected = selected[:budget]
            maximum_overlap = _maximum_pairwise_overlap_v1(
                selected=budget_selected, roster_overlaps=overlaps
            )
            cap_enforced = prefix_count >= budget
            budget_compliance.append({
                "entry_budget": budget,
                "hard_cap_enforced_for_every_rank": cap_enforced,
                "hard_cap_compliance_claimed": cap_enforced,
                "observed_maximum_pairwise_roster_overlap": maximum_overlap,
                "observed_pairwise_overlap_le_gamma": maximum_overlap <= gamma,
            })
        summary = {
            "schema_version": FRONTIER_GAMMA_SUMMARY_SCHEMA,
            "completion_law_id": FRONTIER_GAMMA_COMPLETION_LAW_ID,
            "overlap_cap": gamma,
            "hard_cap_greedy_prefix_count": prefix_count,
            "hard_cap_prefix_rank_range": [0, prefix_count - 1],
            "hard_cap_prefix_lineup_ids": prefix_ids,
            "hard_cap_prefix_lineup_ids_sha256": _hash(prefix_ids),
            "hard_cap_relaxed_within_prefix": False,
            "no_relax_within_hard_cap_prefix": True,
            "hard_cap_unselected_feasible_candidate_count_at_stop": int(
                hard_cap_summary["unselected_feasible_candidate_count_at_stop"]
            ),
            "hard_cap_global_maximum_feasible_cardinality_claimed": False,
            "completion_performed": completion_count > 0,
            "completion_count": completion_count,
            "completion_rank_range": (
                [prefix_count, ENTRY_BUDGETS[-1] - 1]
                if completion_count else None
            ),
            "completion_lineup_ids": completion_ids,
            "completion_lineup_ids_sha256": _hash(completion_ids),
            "completion_overlap_cap_enforced": (
                False if completion_count else None
            ),
            "completed_book_global_cap_compliance_claimed": False,
            "entry_budget_cap_compliance": budget_compliance,
            "hard_cap_prefix_maximum_pairwise_roster_overlap": (
                _maximum_pairwise_overlap_v1(
                    selected=prefix, roster_overlaps=overlaps
                )
            ),
            "completed_order_maximum_pairwise_roster_overlap": (
                _maximum_pairwise_overlap_v1(
                    selected=selected, roster_overlaps=overlaps
                )
            ),
            "final_ranking_depth_reached": len(selected) == ENTRY_BUDGETS[-1],
        }
        selectors.append(diversity._selector_result(
            ordinal=ordinal,
            strategy_id=FRONTIER_GAMMA_SELECTOR_IDS[ordinal],
            kind=(
                "frontier-hard-cap-prefix-until-exhaustion-then-"
                "unconstrained-tail-ladder-fill"
            ),
            selected=selected,
            trace=retained_trace,
            summary=summary,
            lineup_ids=lineup_ids,
            candidates=candidates,
            scores=scores,
            roster_overlaps=overlaps,
        ))
    selected, trace, summary = diversity._run_evil_twin_order(
        lineup_ids=lineup_ids,
        masks=masks,
        primary_counts=primary_counts,
        means=means,
        world_count=scores.shape[1],
    )
    selectors.append(diversity._selector_result(
        ordinal=2,
        strategy_id=confirmation.DIVERSITY_IDS[2],
        kind="negative-tail-event-pairing",
        selected=selected,
        trace=trace,
        summary=summary,
        lineup_ids=lineup_ids,
        candidates=candidates,
        scores=scores,
        roster_overlaps=overlaps,
    ))
    return selectors, diversity.diversity_challenger_contract_v1()[
        "contract_sha256"
    ]


def run_combined_frontier_reportfolio_v1(
    *, combined_result: object, all_block_score_matrix: object,
    source_ordinal: int,
) -> dict[str, object]:
    """Run DPP, strict gamma-4/5, and strict-200 evil twin on one frontier."""
    frontier = derive_frontier_shortlist_v1(
        combined_result,
        all_block_score_matrix=all_block_score_matrix,
        source_ordinal=source_ordinal,
    )
    # The public derivation above deep-validates the parent and matrix identity.
    result = dict(combined_result)
    union_rows = [dict(row) for row in result["union"]["union_lineups"]]
    scores = np.asarray(all_block_score_matrix)
    matrix_binding = dict(result["matrix_binding"])
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
    completed, diversity_contract_sha256 = _frontier_gamma_and_evil_orders_v1(
        scores=subset, candidates=candidates
    )
    selectors.extend(completed)
    licensed_false_selectors: list[dict[str, object]] = []
    for raw_selector in selectors:
        selector_body = {
            key: item for key, item in raw_selector.items()
            if key != "selector_result_sha256"
        }
        policy = dict(selector_body["policy"])
        policy["production_change_licensed"] = False
        selector_body["policy"] = policy
        licensed_false_selectors.append({
            **selector_body,
            "selector_result_sha256": _hash(selector_body),
        })
    selectors = licensed_false_selectors
    completion_law = frontier_gamma_completion_law_v1()
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
        "frontier_gamma_completion_law": completion_law,
        "frontier_gamma_completion_law_sha256": completion_law["law_sha256"],
        "gamma_hard_cap_prefix_relaxed": False,
        "gamma_uncapped_tail_completion_disclosed": True,
        "gamma_completion_overlap_cap_enforced": False,
        "gamma_completed_books_global_cap_compliance_claimed": False,
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
    expected_result_fields = {
        "schema_version", "source_ordinal", "slate_id", "frontier",
        "frontier_sha256", "parent_score_matrix_sha256",
        "frontier_score_matrix_sha256", "frontier_score_shape", "selectors",
        "selectors_sha256", "diversity_contract_sha256",
        "frontier_gamma_completion_law",
        "frontier_gamma_completion_law_sha256",
        "gamma_hard_cap_prefix_relaxed",
        "gamma_uncapped_tail_completion_disclosed",
        "gamma_completion_overlap_cap_enforced",
        "gamma_completed_books_global_cap_compliance_claimed",
        "population_regeneration_performed", "outcome_columns_read",
        "uses_realized_outcomes", "promotion_authority",
        "production_change_licensed", "result_sha256",
    }
    body = {key: item for key, item in result.items() if key != "result_sha256"}
    if (
        set(result) != expected_result_fields
        or result.get("schema_version") != SCHEMA
        or result.get("source_ordinal") != source_ordinal
        or result.get("result_sha256") != _hash(body)
        or result.get("uses_realized_outcomes") is not False
        or result.get("outcome_columns_read") != []
        or result.get("population_regeneration_performed") is not False
        or result.get("promotion_authority") is not False
        or result.get("production_change_licensed") is not False
        or result.get("gamma_hard_cap_prefix_relaxed") is not False
        or result.get("gamma_uncapped_tail_completion_disclosed") is not True
        or result.get("gamma_completion_overlap_cap_enforced") is not False
        or result.get(
            "gamma_completed_books_global_cap_compliance_claimed"
        ) is not False
    ):
        _fail("frontier result authority differs")
    for field in (
        "frontier_sha256", "parent_score_matrix_sha256",
        "frontier_score_matrix_sha256", "selectors_sha256",
        "diversity_contract_sha256",
        "frontier_gamma_completion_law_sha256", "result_sha256",
    ):
        _digest(result[field], label=field)
    completion_law = frontier_gamma_completion_law_v1()
    if (
        result.get("frontier_gamma_completion_law") != completion_law
        or result.get("frontier_gamma_completion_law_sha256")
        != completion_law["law_sha256"]
    ):
        _fail("frontier gamma completion law differs")
    frontier = dict(result["frontier"])
    expected_frontier_fields = {
        "shortlist_law", "sieve_ranking_tuple", "sieve_threshold_operators",
        "sieve_limit", "combined_result_sha256", "union_sha256",
        "later_source_identity", "complete_union_lineup_count",
        "complete_union_lineup_ids_sha256",
        "complete_union_sieve_evidence_sha256",
        "complete_union_modeled_world_mean_vector_metadata",
        "complete_union_modeled_world_mean_vector_payload_sha256",
        "complete_union_modeled_world_mean_vector_binding_sha256",
        "complete_union_score_matrix_sha256", "source_books",
        "source_books_sha256", "old_book_membership_used_for_sieve",
        "prior_eight_book_union_count",
        "prior_eight_book_union_lineup_ids_sha256", "candidate_count",
        "candidate_lineup_ids", "candidate_lineup_ids_sha256",
        "candidate_rows", "candidate_rows_sha256", "candidate_sieve_evidence",
        "candidate_sieve_evidence_sha256",
        "candidate_in_prior_eight_books_count",
        "candidate_absent_from_prior_eight_books_count",
    }
    rows = list(frontier["candidate_rows"])
    if any(not isinstance(row, Mapping) for row in rows):
        _fail("frontier candidate row differs")
    ids = [str(row["lineup_id"]) for row in rows]
    evidence = list(frontier.get("candidate_sieve_evidence", []))
    source_books = list(frontier.get("source_books", []))
    if (
        any(not isinstance(item, Mapping) for item in evidence)
        or any(not isinstance(item, Mapping) for item in source_books)
    ):
        _fail("frontier result sieve evidence differs")
    prior_count = frontier.get("prior_eight_book_union_count")
    overlap_count = frontier.get("candidate_in_prior_eight_books_count")
    novel_count = frontier.get("candidate_absent_from_prior_eight_books_count")
    frontier_shape = result.get("frontier_score_shape")
    mean_metadata = frontier.get(
        "complete_union_modeled_world_mean_vector_metadata"
    )
    if (
        set(frontier) != expected_frontier_fields
        or frontier.get("shortlist_law") != SIEVE_LAW
        or frontier.get("sieve_ranking_tuple") != [
            "descending-strict-gt-230-world-count",
            "descending-strict-gt-220-world-count",
            "descending-strict-gt-210-world-count",
            "descending-strict-gt-200-world-count",
            "descending-modeled-world-mean-float64",
            "ascending-lineup-id",
        ]
        or frontier.get("sieve_threshold_operators") != [
            {"threshold_dk": threshold, "operator": ">"}
            for threshold in SIEVE_THRESHOLDS
        ]
        or frontier.get("sieve_limit") != SIEVE_LIMIT
        or frontier.get("old_book_membership_used_for_sieve") is not False
        or type(frontier.get("complete_union_lineup_count")) is not int
        or frontier["complete_union_lineup_count"] <= SIEVE_LIMIT
        or mean_metadata != {
            "schema_version": MEAN_VECTOR_SCHEMA,
            "dtype": "<f8",
            "shape": [frontier["complete_union_lineup_count"]],
            "order": "C",
            "reduction": "numpy-mean-axis-1-dtype-float64",
        }
        or frontier.get(
            "complete_union_modeled_world_mean_vector_binding_sha256"
        ) != _hash({
            "metadata": mean_metadata,
            "payload_sha256": frontier.get(
                "complete_union_modeled_world_mean_vector_payload_sha256"
            ),
        })
        or frontier.get("complete_union_score_matrix_sha256")
        != result.get("parent_score_matrix_sha256")
        or len(source_books) != SOURCE_BOOK_COUNT
        or frontier.get("source_books_sha256") != _hash(source_books)
        or type(prior_count) is not int
        or not 80 <= prior_count <= SOURCE_BOOK_COUNT * 80
        or type(overlap_count) is not int
        or type(novel_count) is not int
        or overlap_count + novel_count != SIEVE_LIMIT
        or not 0 <= overlap_count <= SIEVE_LIMIT
        or not 0 <= novel_count <= SIEVE_LIMIT
        or frontier.get("candidate_count") != SIEVE_LIMIT
        or len(rows) != SIEVE_LIMIT
        or frontier.get("candidate_lineup_ids") != ids
        or ids != sorted(ids)
        or len(set(ids)) != SIEVE_LIMIT
        or frontier.get("candidate_lineup_ids_sha256") != _hash(ids)
        or frontier.get("candidate_rows_sha256") != _hash(rows)
        or len(evidence) != SIEVE_LIMIT
        or [item.get("lineup_id") for item in evidence] != ids
        or sorted(item.get("sieve_rank") for item in evidence)
        != list(range(SIEVE_LIMIT))
        or frontier.get("candidate_sieve_evidence_sha256") != _hash(evidence)
        or result.get("frontier_sha256") != _hash(frontier)
        or type(frontier_shape) is not list
        or len(frontier_shape) != 2
        or frontier_shape[0] != SIEVE_LIMIT
        or type(frontier_shape[1]) is not int
        or frontier_shape[1] <= 0
    ):
        _fail("frontier result shortlist binding differs")
    for field in (
        "combined_result_sha256", "union_sha256",
        "complete_union_lineup_ids_sha256",
        "complete_union_sieve_evidence_sha256",
        "complete_union_modeled_world_mean_vector_payload_sha256",
        "complete_union_modeled_world_mean_vector_binding_sha256",
        "complete_union_score_matrix_sha256", "source_books_sha256",
        "prior_eight_book_union_lineup_ids_sha256",
        "candidate_lineup_ids_sha256", "candidate_rows_sha256",
        "candidate_sieve_evidence_sha256",
    ):
        _digest(frontier[field], label=field)
    if any(
        set(item) != {
            "lineup_id", "strict_gt_230_world_count",
            "strict_gt_220_world_count", "strict_gt_210_world_count",
            "strict_gt_200_world_count", "modeled_world_mean_float64_hex",
            "modeled_world_mean_micro",
            "sieve_rank",
        }
        or any(
            type(item[field]) is not int
            or not 0 <= item[field] <= frontier_shape[1]
            for field in (
                "strict_gt_230_world_count", "strict_gt_220_world_count",
                "strict_gt_210_world_count", "strict_gt_200_world_count",
            )
        )
        or type(item["modeled_world_mean_float64_hex"]) is not str
        or type(item["modeled_world_mean_micro"]) is not int
        or type(item["sieve_rank"]) is not int
        for item in evidence
    ):
        _fail("frontier result sieve evidence differs")
    try:
        evidence_means = [
            float.fromhex(item["modeled_world_mean_float64_hex"])
            for item in evidence
        ]
    except ValueError as exc:
        raise CorpusR6CombinedFrontierReportfolioV1Error(
            "frontier result exact mean differs"
        ) from exc
    if (
        not np.isfinite(np.asarray(evidence_means, dtype=np.float64)).all()
        or any(
            mean.hex() != item["modeled_world_mean_float64_hex"]
            or int(np.rint(mean * 1_000_000))
            != item["modeled_world_mean_micro"]
            for mean, item in zip(evidence_means, evidence, strict=True)
        )
    ):
        _fail("frontier result exact mean differs")
    ranked_evidence = sorted(evidence, key=lambda item: item["sieve_rank"])
    replay_ranked = sorted(
        evidence,
        key=lambda item: (
            -item["strict_gt_230_world_count"],
            -item["strict_gt_220_world_count"],
            -item["strict_gt_210_world_count"],
            -item["strict_gt_200_world_count"],
            -float.fromhex(item["modeled_world_mean_float64_hex"]),
            item["lineup_id"],
        ),
    )
    if ranked_evidence != replay_ranked:
        _fail("frontier result exact mean ranking differs")
    candidate_index = {lineup_id: index for index, lineup_id in enumerate(ids)}
    candidate_overlaps = diversity._roster_overlap_matrix(rows)
    selectors = list(result["selectors"])
    if (
        len(selectors) != 4
        or [selector.get("strategy_id") for selector in selectors]
        != list(SELECTOR_IDS)
        or result.get("selectors_sha256") != _hash(selectors)
    ):
        _fail("frontier selector census differs")
    books: list[dict[str, object]] = []
    for selector_index, selector in enumerate(selectors):
        selector_body = {
            key: item for key, item in selector.items()
            if key != "selector_result_sha256"
        }
        policy = selector.get("policy")
        expected_policy = {
            **diversity._FALSE_POLICY,
            "production_change_licensed": False,
        }
        if (
            selector.get("selector_result_sha256") != _hash(selector_body)
            or not isinstance(policy, Mapping)
            or dict(policy) != expected_policy
        ):
            _fail("frontier selector result hash differs")
        entry_books = list(selector["entry_books"])
        ranked_ids = [str(item) for item in selector.get("ranked_lineup_ids", [])]
        if selector_index in (1, 2):
            gamma = selector_index + 3
            summary = selector.get("selector_summary")
            if not isinstance(summary, Mapping):
                _fail("frontier gamma completion summary differs")
            summary = dict(summary)
            prefix_count = summary.get("hard_cap_greedy_prefix_count")
            completion_count = summary.get("completion_count")
            prefix_ids = summary.get("hard_cap_prefix_lineup_ids")
            completion_ids = summary.get("completion_lineup_ids")
            compliance = summary.get("entry_budget_cap_compliance")
            feasible_at_stop = summary.get(
                "hard_cap_unselected_feasible_candidate_count_at_stop"
            )
            if (
                selector.get("strategy_id")
                != FRONTIER_GAMMA_SELECTOR_IDS[selector_index - 1]
                or selector.get("selector_kind")
                != (
                    "frontier-hard-cap-prefix-until-exhaustion-then-"
                    "unconstrained-tail-ladder-fill"
                )
                or summary.get("schema_version")
                != FRONTIER_GAMMA_SUMMARY_SCHEMA
                or set(summary) != FRONTIER_GAMMA_SUMMARY_FIELDS
                or summary.get("completion_law_id")
                != FRONTIER_GAMMA_COMPLETION_LAW_ID
                or summary.get("overlap_cap") != gamma
                or type(prefix_count) is not int
                or not 0 < prefix_count <= ENTRY_BUDGETS[-1]
                or summary.get("hard_cap_prefix_rank_range")
                != [0, prefix_count - 1]
                or prefix_ids != ranked_ids[:prefix_count]
                or summary.get("hard_cap_prefix_lineup_ids_sha256")
                != _hash(prefix_ids)
                or summary.get("hard_cap_relaxed_within_prefix") is not False
                or summary.get("no_relax_within_hard_cap_prefix") is not True
                or type(feasible_at_stop) is not int
                or feasible_at_stop < 0
                or (
                    prefix_count < ENTRY_BUDGETS[-1]
                    and feasible_at_stop != 0
                )
                or summary.get(
                    "hard_cap_global_maximum_feasible_cardinality_claimed"
                ) is not False
                or type(completion_count) is not int
                or completion_count != ENTRY_BUDGETS[-1] - prefix_count
                or summary.get("completion_performed")
                is not (completion_count > 0)
                or summary.get("completion_rank_range")
                != (
                    [prefix_count, ENTRY_BUDGETS[-1] - 1]
                    if completion_count else None
                )
                or completion_ids != ranked_ids[prefix_count:]
                or summary.get("completion_lineup_ids_sha256")
                != _hash(completion_ids)
                or summary.get("completion_overlap_cap_enforced")
                != (False if completion_count else None)
                or summary.get(
                    "completed_book_global_cap_compliance_claimed"
                ) is not False
                or type(summary.get(
                    "hard_cap_prefix_maximum_pairwise_roster_overlap"
                )) is not int
                or not 0 <= summary[
                    "hard_cap_prefix_maximum_pairwise_roster_overlap"
                ] <= gamma
                or type(summary.get(
                    "completed_order_maximum_pairwise_roster_overlap"
                )) is not int
                or not 0 <= summary[
                    "completed_order_maximum_pairwise_roster_overlap"
                ] <= 9
                or summary.get("final_ranking_depth_reached") is not True
                or not isinstance(compliance, Sequence)
                or isinstance(compliance, (str, bytes))
                or len(compliance) != len(ENTRY_BUDGETS)
            ):
                _fail("frontier gamma completion summary differs")
            ranked_indices = [
                candidate_index.get(lineup_id) for lineup_id in ranked_ids
            ]
            if any(index is None for index in ranked_indices):
                _fail("frontier gamma ranked candidate differs")
            retained_indices = [int(index) for index in ranked_indices]
            expected_prefix_maximum = _maximum_pairwise_overlap_v1(
                selected=retained_indices[:prefix_count],
                roster_overlaps=candidate_overlaps,
            )
            expected_full_maximum = _maximum_pairwise_overlap_v1(
                selected=retained_indices[:ENTRY_BUDGETS[-1]],
                roster_overlaps=candidate_overlaps,
            )
            if (
                summary["hard_cap_prefix_maximum_pairwise_roster_overlap"]
                != expected_prefix_maximum
                or summary[
                    "completed_order_maximum_pairwise_roster_overlap"
                ] != expected_full_maximum
            ):
                _fail("frontier gamma maximum overlap differs")
            for budget, raw_compliance in zip(
                ENTRY_BUDGETS, compliance, strict=True
            ):
                if not isinstance(raw_compliance, Mapping):
                    _fail("frontier gamma budget compliance differs")
                row = dict(raw_compliance)
                enforced = prefix_count >= budget
                maximum = row.get("observed_maximum_pairwise_roster_overlap")
                expected_maximum = _maximum_pairwise_overlap_v1(
                    selected=retained_indices[:budget],
                    roster_overlaps=candidate_overlaps,
                )
                if (
                    row.get("entry_budget") != budget
                    or row.get("hard_cap_enforced_for_every_rank") is not enforced
                    or row.get("hard_cap_compliance_claimed") is not enforced
                    or type(maximum) is not int
                    or maximum != expected_maximum
                    or row.get("observed_pairwise_overlap_le_gamma")
                    is not (maximum <= gamma)
                ):
                    _fail("frontier gamma budget compliance differs")
        if (
            [book.get("entry_budget") for book in entry_books]
            != list(ENTRY_BUDGETS)
            or selector.get("entry_budgets_available") != list(ENTRY_BUDGETS)
            or selector.get("exact_prefix_consistency_verified") is not True
            or selector.get("greedy_prefix_count") != len(ranked_ids)
            or len(ranked_ids) < ENTRY_BUDGETS[-1]
            or len(set(ranked_ids)) != len(ranked_ids)
            or not set(ranked_ids) <= set(ids)
            or selector.get("ranked_lineup_ids_sha256") != _hash(ranked_ids)
        ):
            _fail("frontier selector does not expose exact K80/K100/K150")
        for book in entry_books:
            book_body = {
                key: item for key, item in book.items() if key != "book_sha256"
            }
            if book.get("book_sha256") != _hash(book_body):
                _fail("frontier entry book hash differs")
            selected = [str(item) for item in book["selected_lineup_ids"]]
            if (
                len(selected) != book["entry_budget"]
                or len(set(selected)) != book["entry_budget"]
                or not set(selected) <= set(ids)
                or selected != ranked_ids[: book["entry_budget"]]
                or book.get("selected_lineup_ids_sha256") != _hash(selected)
                or book.get("uses_realized_outcomes") is not False
                or book.get("heldout_evaluation_performed") is not False
            ):
                _fail("frontier selected book differs")
            coordinate = {
                "adapter_id": "combined-complete-union-sieve-reportfolio-v1",
                "metric_kind": "selected-book",
                "fit_scope_id": combined.FIT_SCOPE_ID,
                "selector_family": "combined-complete-union-sieve-reportfolio-v1",
                "selector_id": selector["strategy_id"],
                "entry_budget": book["entry_budget"],
            }
            books.append({
                "coordinate": coordinate,
                "coordinate_sha256": _hash(coordinate),
                "population_id": "combined-complete-union-sieve-top250-v1",
                "selected_lineup_ids": selected,
            })
    return {
        "source_ordinal": source_ordinal,
        "slate_id": result["slate_id"],
        "populations": [{
            "population_id": "combined-complete-union-sieve-top250-v1",
            "dimensions": {
                "candidate_count": len(rows),
                "complete_union_lineup_count": frontier[
                    "complete_union_lineup_count"
                ],
                "prior_eight_book_union_count": prior_count,
                "novel_to_prior_eight_book_union_count": novel_count,
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
