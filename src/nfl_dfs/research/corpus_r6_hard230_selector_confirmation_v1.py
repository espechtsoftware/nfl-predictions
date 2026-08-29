"""Pure 42-cell selector confirmation for the sealed hard-230 populations.

The predecessor bridge owns population and score reconstruction.  This module
adds three already-registered diversity orders to its native+DPP books while
preserving the honest R1--R4 out-of-R0-origin fitting law.  It has no I/O and
cannot regenerate candidates, read outcomes, or relax an overlap cap.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_r6_hard230_selector_bridge_v1 as bridge
from nfl_dfs.research import corpus_r6_selector_diversity_challengers_v1 as diversity
from nfl_dfs.research import corpus_r6_current_bank_selector_successor_v1 as successor


SCHEMA_VERSION: Final = "corpus-r6-hard230-selector-confirmation/v1"
ADAPTER_ID: Final = "hard230-seven-selector-confirmation-v1"
ENTRY_BUDGETS: Final = (80, 100, 150)
DIVERSITY_IDS: Final = (
    "tail-ladder-roster-overlap-cap-4-v1",
    "tail-ladder-roster-overlap-cap-5-v1",
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
        selected, trace, summary = diversity._run_overlap_cap_order(
            gamma=gamma,
            lineup_ids=lineup_ids,
            masks=masks,
            primary_counts=primary_counts,
            means=means,
            roster_overlaps=overlaps,
        )
        selectors.append(diversity._selector_result(
            ordinal=ordinal,
            strategy_id=f"tail-ladder-roster-overlap-cap-{gamma}-v1",
            kind="hard-roster-overlap-cap",
            selected=selected,
            trace=trace,
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

        selected_results, diversity_contract_sha256 = _hard230_diversity_orders(
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
        diversity_hashes.append({
            "population_role": role,
            "population_id": population_id,
            "diversity_contract_sha256": diversity_contract_sha256,
            "diversity_selector_results_sha256": _hash(selected_results),
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
    "build_from_sealed_hard230_bridge_v1",
    "build_hard230_selector_confirmation_v1",
    "validate_sealed_hard230_bridge_confirmation_v1",
    "validate_hard230_selector_confirmation_v1",
]
