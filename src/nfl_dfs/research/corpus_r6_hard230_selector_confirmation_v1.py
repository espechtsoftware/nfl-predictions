"""Pure 42-cell selector confirmation for the sealed hard-230 populations.

The predecessor bridge owns population and score reconstruction.  This module
adds three diversity orders to its native+DPP books while preserving the
honest R1--R4 out-of-R0-origin fitting law.  The overlap variants retain the
registered non-relaxing hard-cap greedy prefix through K100, then, only when
that prefix cannot reach K150, complete the nested order with the same frozen
tail-ladder objective without claiming the added entries satisfy the cap.
It has no I/O and cannot regenerate candidates or read outcomes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_r6_hard230_selector_bridge_v1 as bridge
from nfl_dfs.research import corpus_r6_selector_diversity_challengers_v1 as diversity
from nfl_dfs.research import corpus_r6_current_bank_selector_successor_v1 as successor


SCHEMA_VERSION: Final = "corpus-r6-hard230-selector-confirmation/v2"
ADAPTER_ID: Final = "hard230-seven-selector-confirmation-v2"
ENTRY_BUDGETS: Final = (80, 100, 150)
OVERLAP_COMPLETION_LAW_ID: Final = (
    "hard-cap-greedy-prefix-through-k100-then-unconstrained-tail-ladder-fill-v1"
)
OVERLAP_COMPLETION_LAW_SCHEMA: Final = (
    "corpus-r6-hard230-overlap-completion-law/v2"
)
OVERLAP_COMPLETION_EVIDENCE_SCHEMA: Final = (
    "corpus-r6-hard230-overlap-completion-evidence/v2"
)
BASE_OVERLAP_SELECTOR_IDS: Final = (
    "tail-ladder-roster-overlap-cap-4-v1",
    "tail-ladder-roster-overlap-cap-5-v1",
)
DIVERSITY_IDS: Final = (
    "tail-ladder-roster-overlap-cap-4-prefix-then-tail-fill-v1",
    "tail-ladder-roster-overlap-cap-5-prefix-then-tail-fill-v1",
    "tail-ladder-evil-twin-strict-200-v1",
)
SELECTOR_COUNT: Final = 7
POPULATION_COUNT: Final = 2
BOOK_COUNT: Final = SELECTOR_COUNT * POPULATION_COUNT * len(ENTRY_BUDGETS)


class CorpusR6Hard230SelectorConfirmationV1Error(ValueError):
    pass


def _fail(message: str) -> None:
    raise CorpusR6Hard230SelectorConfirmationV1Error(message)


def _canonical(value: object) -> bytes:
    return bridge._canonical(value)


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(value)
    if field in result:
        _fail(f"{field} already exists")
    result[field] = _hash(result)
    return result


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be one mapping")
    return dict(value)


def _book(
    *, role: str, population_id: str, family: str, selector_id: str,
    budget: int, selected: Sequence[str],
) -> dict[str, object]:
    lineup_ids = [str(value) for value in selected[:budget]]
    if len(lineup_ids) != budget or len(set(lineup_ids)) != budget:
        _fail("confirmation book is not exact and unique")
    coordinate = {
        "adapter_id": ADAPTER_ID,
        "metric_kind": "selected-book",
        "population_role": role,
        "population_id": population_id,
        "selector_family": family,
        "selector_id": selector_id,
        "entry_budget": budget,
    }
    return _with_hash({
        "coordinate": coordinate,
        "coordinate_sha256": _hash(coordinate),
        "selected_lineup_ids": lineup_ids,
        "selected_lineup_ids_sha256": _hash(lineup_ids),
    }, field="book_sha256")


def overlap_completion_law_v2() -> dict[str, object]:
    """Describe the v2 completion layered over the immutable base kernel."""
    base_contract = diversity.diversity_challenger_contract_v1()
    return _with_hash({
        "schema_version": OVERLAP_COMPLETION_LAW_SCHEMA,
        "law_id": OVERLAP_COMPLETION_LAW_ID,
        "base_kernel_contract_sha256": base_contract["contract_sha256"],
        "base_kernel_overlap_selector_ids": list(BASE_OVERLAP_SELECTOR_IDS),
        "completed_overlap_selector_ids": list(DIVERSITY_IDS[:2]),
        "entry_budgets": list(ENTRY_BUDGETS),
        "hard_cap_prefix_minimum_count": ENTRY_BUDGETS[1],
        "hard_cap_prefix_law": (
            "registered-greedy-overlap-cap-prefix-is-byte-preserved-and-never-relaxed"
        ),
        "completion_trigger": "hard-cap-prefix-count-is-less-than-150",
        "completion_law": (
            "continue-frozen-tail-ladder-over-remaining-candidates-from-prefix-coverage"
        ),
        "completion_overlap_cap_enforced": False,
        "completion_global_cap_compliance_claimed": False,
        "nested_prefixes": list(ENTRY_BUDGETS),
        "uses_realized_outcomes": False,
        "heldout_scores_used": False,
    }, field="completion_law_sha256")


def _completion_evidence_v2(
    selector: Mapping[str, object], *, ordinal: int,
) -> dict[str, object]:
    item = _mapping(selector, label="completed overlap selector")
    summary = _mapping(
        item.get("selector_summary"), label="completed overlap selector summary"
    )
    ranked = [str(value) for value in item.get("ranked_lineup_ids", [])]
    prefix = [
        str(value) for value in summary.get("hard_cap_prefix_lineup_ids", [])
    ]
    completion = [
        str(value) for value in summary.get("completion_lineup_ids", [])
    ]
    prefix_count = summary.get("hard_cap_greedy_prefix_count")
    completion_count = summary.get("completion_count")
    completion_performed = summary.get("completion_performed")
    completion_start = summary.get("completion_start_rank")
    completion_cap = summary.get("completion_overlap_cap_enforced")
    expected_completion = len(prefix) < ENTRY_BUDGETS[-1]
    if (
        ordinal not in (0, 1)
        or item.get("strategy_id") != DIVERSITY_IDS[ordinal]
        or type(prefix_count) is not int
        or type(completion_count) is not int
        or type(completion_performed) is not bool
        or len(ranked) != ENTRY_BUDGETS[-1]
        or len(set(ranked)) != len(ranked)
        or len(prefix) != prefix_count
        or not ENTRY_BUDGETS[1] <= prefix_count <= ENTRY_BUDGETS[-1]
        or len(completion) != completion_count
        or prefix + completion != ranked
        or completion_performed is not expected_completion
        or completion_count != ENTRY_BUDGETS[-1] - prefix_count
        or completion_start != (prefix_count if expected_completion else None)
        or completion_cap != (False if expected_completion else None)
        or summary.get("hard_cap_relaxed_within_prefix") is not False
        or summary.get("completion_law_id") != OVERLAP_COMPLETION_LAW_ID
        or summary.get("final_ranking_depth_reached") is not True
        or item.get("exact_prefix_consistency_verified") is not True
        or item.get("entry_budgets_available") != list(ENTRY_BUDGETS)
    ):
        _fail("confirmation overlap completion evidence differs")
    books = item.get("entry_books")
    if not isinstance(books, Sequence) or isinstance(books, (str, bytes)):
        _fail("confirmation overlap completion books differ")
    if (
        len(books) != len(ENTRY_BUDGETS)
        or any(not isinstance(book, Mapping) for book in books)
        or [book.get("entry_budget") for book in books]
        != list(ENTRY_BUDGETS)
        or any(
            book.get("selected_lineup_ids") != ranked[: int(book["entry_budget"])]
            for book in books
        )
    ):
        _fail("confirmation overlap completion nesting differs")
    return _with_hash({
        "schema_version": OVERLAP_COMPLETION_EVIDENCE_SCHEMA,
        "base_kernel_selector_id": BASE_OVERLAP_SELECTOR_IDS[ordinal],
        "completed_selector_id": DIVERSITY_IDS[ordinal],
        "overlap_cap": ordinal + 4,
        "hard_cap_prefix_count": prefix_count,
        "hard_cap_prefix_lineup_ids": prefix,
        "hard_cap_prefix_lineup_ids_sha256": _hash(prefix),
        "hard_cap_enforced_rank_range": [0, prefix_count - 1],
        "hard_cap_relaxed_within_prefix": False,
        "completion_performed": completion_performed,
        "completion_start_rank": completion_start,
        "completion_count": completion_count,
        "completion_lineup_ids": completion,
        "completion_lineup_ids_sha256": _hash(completion),
        "completion_rank_range": (
            [prefix_count, ENTRY_BUDGETS[-1] - 1]
            if expected_completion
            else None
        ),
        "completion_overlap_cap_enforced": completion_cap,
        "completion_global_cap_compliance_claimed": False,
        "completed_ranked_lineup_ids_sha256": _hash(ranked),
        "exact_hard_cap_prefix_preserved": True,
        "exact_nested_k80_k100_k150_verified": True,
    }, field="completion_evidence_sha256")


def _hard230_diversity_orders(
    *, scores: np.ndarray, candidates: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], str]:
    """Reuse the registered kernels without inventing current-bank provenance."""
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
        hard_cap_prefix_count = len(selected)
        if hard_cap_prefix_count < ENTRY_BUDGETS[1]:
            _fail("confirmation hard-cap prefix lacks exact K100")
        if hard_cap_prefix_count > ENTRY_BUDGETS[-1]:
            _fail("confirmation hard-cap prefix exceeds K150")

        hard_cap_prefix = list(selected)
        retained_trace = [
            {
                **dict(row),
                "selection_role": "hard-roster-overlap-cap-prefix",
                "overlap_cap_enforced": True,
            }
            for row in trace
        ]
        if hard_cap_prefix_count < ENTRY_BUDGETS[-1]:
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
                    _fail("confirmation tail-ladder completion lacks exact K150")
                maximum_prior_overlap = (
                    0
                    if not selected
                    else int(overlaps[best, selected].max())
                )
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

        completion_count = len(selected) - hard_cap_prefix_count
        hard_cap_prefix_lineup_ids = [lineup_ids[index] for index in hard_cap_prefix]
        completion_lineup_ids = [
            lineup_ids[index] for index in selected[hard_cap_prefix_count:]
        ]
        summary = {
            "overlap_cap": gamma,
            "hard_cap_greedy_prefix_count": hard_cap_prefix_count,
            "hard_cap_prefix_lineup_ids": hard_cap_prefix_lineup_ids,
            "hard_cap_prefix_lineup_ids_sha256": _hash(
                hard_cap_prefix_lineup_ids
            ),
            "hard_cap_ranking_depth_reached": (
                hard_cap_prefix_count == ENTRY_BUDGETS[-1]
            ),
            "hard_cap_unselected_feasible_candidate_count_at_stop": int(
                hard_cap_summary["unselected_feasible_candidate_count_at_stop"]
            ),
            "hard_cap_global_maximum_feasible_cardinality_claimed": False,
            "hard_cap_relaxed_within_prefix": False,
            "completion_law_id": OVERLAP_COMPLETION_LAW_ID,
            "completion_performed": completion_count > 0,
            "completion_start_rank": (
                hard_cap_prefix_count if completion_count > 0 else None
            ),
            "completion_count": completion_count,
            "completion_lineup_ids": completion_lineup_ids,
            "completion_lineup_ids_sha256": _hash(completion_lineup_ids),
            "completion_overlap_cap_enforced": (
                False if completion_count > 0 else None
            ),
            "completion_global_cap_compliance_claimed": False,
            "final_ranking_depth_reached": len(selected) == ENTRY_BUDGETS[-1],
        }
        selectors.append(diversity._selector_result(
            ordinal=ordinal,
            strategy_id=DIVERSITY_IDS[ordinal],
            kind="hard-roster-overlap-cap-prefix-then-tail-ladder-fill",
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
        strategy_id=DIVERSITY_IDS[2],
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


def _build_from_retained_bridge_v1(
    *,
    retained: Mapping[str, object],
    training_score_matrices: Mapping[str, np.ndarray],
) -> dict[str, object]:
    if (
        retained["selector_fit_blocks"] != list(bridge.SELECTOR_BLOCKS)
        or retained["generator_origin_block"] != bridge.GENERATOR_ORIGIN_BLOCK
        or set(training_score_matrices)
        != {spec[0] for spec in bridge.POPULATION_SPECS}
    ):
        _fail("confirmation source or R1--R4 fit law differs")

    books: list[dict[str, object]] = []
    diversity_hashes: list[dict[str, object]] = []
    for population in retained["population_results"]:
        role = str(population["population_role"])
        population_id = str(population["population_id"])
        sampled = [str(value) for value in population["sampled_lineup_ids"]]
        by_id = {
            str(row["lineup_id"]): row
            for row in population["full_population_lineups"]
        }
        candidates = [by_id[lineup_id] for lineup_id in sampled]
        scores = training_score_matrices[role]
        if (
            not isinstance(scores, np.ndarray)
            or scores.dtype != np.dtype(np.float64)
            or scores.ndim != 2
            or not scores.flags.c_contiguous
            or list(scores.shape) != population["selector_fit_score_shape"]
            or successor._matrix_sha(scores)
            != population["selector_fit_score_matrix_sha256"]
        ):
            _fail("confirmation training matrix binding differs")

        for source_book in population["books"]:
            coordinate = source_book["coordinate"]
            books.append(_book(
                role=role,
                population_id=population_id,
                family=str(coordinate["selector_family"]),
                selector_id=str(coordinate["selector_id"]),
                budget=int(coordinate["entry_budget"]),
                selected=source_book["selected_lineup_ids"],
            ))

        selected_results, base_kernel_contract_sha256 = _hard230_diversity_orders(
            scores=scores, candidates=candidates
        )
        if [row["strategy_id"] for row in selected_results] != list(DIVERSITY_IDS):
            _fail("confirmation diversity selector registry differs")
        for selector in selected_results:
            ranked = selector["ranked_lineup_ids"]
            if len(ranked) != 150 or selector["entry_budgets_available"] != [80, 100, 150]:
                _fail("confirmation diversity selector lacks exact K150")
            for budget in ENTRY_BUDGETS:
                books.append(_book(
                    role=role,
                    population_id=population_id,
                    family="tail-ladder-diversity-challengers",
                    selector_id=str(selector["strategy_id"]),
                    budget=budget,
                    selected=ranked,
                ))
        completion_law = overlap_completion_law_v2()
        completion_evidence = [
            _completion_evidence_v2(selector, ordinal=ordinal)
            for ordinal, selector in enumerate(selected_results[:2])
        ]
        diversity_hashes.append({
            "population_role": role,
            "population_id": population_id,
            "base_diversity_kernel_contract_sha256": (
                base_kernel_contract_sha256
            ),
            "overlap_completion_law": completion_law,
            "overlap_completion_law_sha256": completion_law[
                "completion_law_sha256"
            ],
            "completed_diversity_selector_results_sha256": _hash(
                selected_results
            ),
            "overlap_completion_evidence": completion_evidence,
            "overlap_completion_evidence_sha256": _hash(completion_evidence),
            "training_score_matrix_sha256": population[
                "selector_fit_score_matrix_sha256"
            ],
        })

    if len(books) != BOOK_COUNT:
        _fail("confirmation does not contain exactly 42 books")
    body = {
        "schema_version": SCHEMA_VERSION,
        "adapter_id": ADAPTER_ID,
        "source_ordinal": retained["source_ordinal"],
        "slate_id": retained["slate_id"],
        "bridge_slate_sha256": retained["slate_result_sha256"],
        "generator_origin_block": bridge.GENERATOR_ORIGIN_BLOCK,
        "selector_fit_blocks": list(bridge.SELECTOR_BLOCKS),
        "selector_fit_law": "fixed-r1-through-r4-out-of-r0-origin-simulated-bank",
        "population_count": POPULATION_COUNT,
        "selector_count_per_population": SELECTOR_COUNT,
        "entry_budgets": list(ENTRY_BUDGETS),
        "book_count": BOOK_COUNT,
        "diversity_bindings": diversity_hashes,
        "diversity_bindings_sha256": _hash(diversity_hashes),
        "books": books,
        "books_sha256": _hash(books),
        "corpus_regeneration_performed": False,
        "uses_realized_outcomes": False,
        "heldout_scores_used": False,
    }
    return _with_hash(body, field="confirmation_sha256")


def build_hard230_selector_confirmation_v1(
    *, bridge_slate: object, bridge_replay_inputs: Mapping[str, object],
    training_score_matrices: Mapping[str, np.ndarray],
) -> dict[str, object]:
    """Replay the bridge and add exact gamma-4/gamma-5/evil-twin books."""
    try:
        retained = bridge.validate_hard230_selector_slate_v1(
            bridge_slate, **dict(bridge_replay_inputs)
        )
    except Exception as exc:
        raise CorpusR6Hard230SelectorConfirmationV1Error(
            "hard230 bridge replay failed"
        ) from exc
    return _build_from_retained_bridge_v1(
        retained=retained, training_score_matrices=training_score_matrices
    )


def build_from_sealed_hard230_bridge_v1(
    *, bridge_slate: object,
    training_score_matrices: Mapping[str, np.ndarray],
) -> dict[str, object]:
    """Replay only new selectors from one create-last sealed bridge slate."""
    try:
        # This validates every bridge self-hash, population, source book, and
        # nested prefix.  The create-last bridge terminal owns the earlier
        # native-selector replay; the exact matrix hashes below bind only the
        # three new confirmation orders that still need recomputation.
        bridge.normalized_slate_for_grader_v1(bridge_slate)
        retained = _mapping(bridge_slate, label="sealed hard230 bridge slate")
    except Exception as exc:
        raise CorpusR6Hard230SelectorConfirmationV1Error(
            "sealed hard230 bridge validation failed"
        ) from exc
    return _build_from_retained_bridge_v1(
        retained=retained, training_score_matrices=training_score_matrices
    )


def validate_hard230_selector_confirmation_v1(
    value: object, **replay_inputs: object,
) -> dict[str, object]:
    expected = build_hard230_selector_confirmation_v1(**replay_inputs)
    if _canonical(value) != _canonical(expected):
        _fail("hard230 selector confirmation differs from exact replay")
    return expected


def validate_sealed_hard230_bridge_confirmation_v1(
    value: object,
    *,
    bridge_slate: object,
    training_score_matrices: Mapping[str, np.ndarray],
) -> dict[str, object]:
    expected = build_from_sealed_hard230_bridge_v1(
        bridge_slate=bridge_slate,
        training_score_matrices=training_score_matrices,
    )
    if _canonical(value) != _canonical(expected):
        _fail("hard230 selector confirmation differs from sealed exact replay")
    return expected


__all__ = [
    "ADAPTER_ID", "BOOK_COUNT", "DIVERSITY_IDS", "ENTRY_BUDGETS",
    "OVERLAP_COMPLETION_LAW_ID", "overlap_completion_law_v2",
    "build_from_sealed_hard230_bridge_v1",
    "build_hard230_selector_confirmation_v1",
    "validate_sealed_hard230_bridge_confirmation_v1",
    "validate_hard230_selector_confirmation_v1",
]
