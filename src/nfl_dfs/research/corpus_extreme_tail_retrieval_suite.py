"""Fold-safe, separately versioned extreme-tail retrieval supplement.

This pure module runs four inclusive-tail laws over the canonical Foundry v12
cross-arm union.  It deliberately does not extend or reinterpret R6-v2's
seven-law registry.  Every held-out fold strips held-out candidate provenance
before selection, uses only its four training score blocks, and evaluates the
held-out block only after exact books are fixed.

The four greedy rankings are built once to rank 80 and materialized as exact
4-, 14-, and 80-entry prefixes.  This is exact because none of the registered
greedy laws depends on its terminal budget.  The retained traces and canonical
replay validator make that prefix law independently checkable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    _score_matrix_sha256,
    canonical_json_bytes,
    canonical_sha256,
)


SUITE_SCHEMA: Final = "extreme-tail-retrieval-suite/v1"
SCOPE_SCHEMA: Final = "extreme-tail-retrieval-fit-scope/v1"
BOOK_SCHEMA: Final = "extreme-tail-retrieval-book/v1"
STRATEGY_SCHEMA: Final = "extreme-tail-retrieval-strategy/v1"
SELECTOR_IMPLEMENTATION_SCHEMA: Final = (
    "extreme-tail-packed-selector-implementation/v1"
)
SELECTOR_IMPLEMENTATION_ID: Final = "packed-chunked-exact-t230-selectors-v1"
SUITE_LAW_ID: Final = "ordinary-r-inclusive-extreme-tail-retrieval/v1"
FULL_UNION_ADMISSION_LAW: Final = "fold-eligible-full-union-only/v1"
ENTRY_BUDGETS: Final = (4, 14, 80)
RANKING_DEPTH: Final = max(ENTRY_BUDGETS)
_CANDIDATE_CHUNK_ROWS: Final = 256
_SELECTOR_CANDIDATE_CHUNK_ROWS: Final = 64
_PACKED_BITORDER: Final = "little"
_PACKED_POPCOUNT: Final = np.asarray(
    [value.bit_count() for value in range(256)], dtype=np.uint8
)
_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
)
TAIL_RUNGS: Final = (
    (210.0, ">=", 1),
    (220.0, ">=", 2),
    (230.0, ">=", 4),
    (240.0, ">=", 8),
    (250.0, ">=", 16),
)
TAIL_THRESHOLDS: Final = tuple(
    (f"ge_{int(threshold)}", threshold, operator)
    for threshold, operator, _weight in TAIL_RUNGS
)


class CorpusExtremeTailRetrievalSuiteError(ValueError):
    """The T230 suite cannot be produced without violating its frozen law."""


def _fail(message: str) -> None:
    raise CorpusExtremeTailRetrievalSuiteError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    result[field] = canonical_sha256(result)
    return result


def _validate_self_hash(
    body: Mapping[str, object], field: str, *, label: str
) -> None:
    retained = body.get(field)
    if (
        type(retained) is not str
        or len(retained) != 64
        or any(character not in "0123456789abcdef" for character in retained)
    ):
        _fail(f"{label} lacks a canonical self-hash")
    remainder = {key: value for key, value in body.items() if key != field}
    if canonical_sha256(remainder) != retained:
        _fail(f"{label} self-hash differs")


def frozen_selector_implementation_contract_v1() -> dict[str, object]:
    """Freeze the bounded-memory kernels behind every T230 strategy hash."""
    body = {
        "schema_version": SELECTOR_IMPLEMENTATION_SCHEMA,
        "implementation_id": SELECTOR_IMPLEMENTATION_ID,
        "candidate_chunk_rows": _SELECTOR_CANDIDATE_CHUNK_ROWS,
        "event_mask_encoding": "numpy-packbits-uint8",
        "event_mask_bitorder": _PACKED_BITORDER,
        "padding_bit_law": "zero-pad-final-byte-and-mask-only-with-event-bits",
        "popcount_law": "exact-frozen-uint8-lookup-v1",
        "candidate_scan_law": (
            "ascending-local-index-in-bounded-chunks-with-frozen-tie-tuples"
        ),
        "coverage_zero_gain_law": (
            "stop-greedy-then-fill-by-individual-count-mean-and-lineup-id"
        ),
        "ladder_law": "packed-global-rung-masks-and-exact-rank-80",
        "blockmin_law": (
            "block-local-packed-rung-masks-and-dynamic-four-or-five-block-leximin"
        ),
        "individual_law": "packed-inclusive-230-count-rank",
        "dense_remaining_candidate_event_temporaries": False,
    }
    return _self_hash(body, "selector_implementation_sha256")


def _rungs() -> list[dict[str, object]]:
    return [
        {"threshold": threshold, "operator": operator, "weight": weight}
        for threshold, operator, weight in TAIL_RUNGS
    ]


def _strategy(
    *,
    ordinal: int,
    strategy_id: str,
    method: str,
    parameters: Mapping[str, object],
    tie_law: Sequence[str],
    role: str,
    description: str,
) -> dict[str, object]:
    implementation = frozen_selector_implementation_contract_v1()
    body = {
        "schema_version": STRATEGY_SCHEMA,
        "ordinal": ordinal,
        "strategy_id": strategy_id,
        "method": method,
        "parameters": dict(parameters),
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "selector_implementation_id": implementation["implementation_id"],
        "selector_implementation_sha256": implementation[
            "selector_implementation_sha256"
        ],
        "tie_law": list(tie_law),
        "selection_inputs": (
            "fold-eligible-full-union-training-block-simulated-scores-only"
        ),
        "role": role,
        "description": description,
    }
    return _self_hash(body, "strategy_sha256")


def frozen_extreme_tail_strategies_v1() -> list[dict[str, object]]:
    """Return the exact four-law T230 registry in canonical ordinal order."""
    return [
        _strategy(
            ordinal=0,
            strategy_id="coverage-ge-230-v1",
            method="greedy-threshold-coverage-v1",
            parameters={"threshold": 230.0, "operator": ">="},
            tie_law=[
                "largest-marginal-new-ge-230-world-count",
                "largest-individual-ge-230-world-count",
                "largest-training-mean-score",
                "ascending-lineup-id",
            ],
            role="literal-aggressive-target",
            description=(
                "Greedy distinct ordinary-R world coverage at inclusive "
                "score 230."
            ),
        ),
        _strategy(
            ordinal=1,
            strategy_id="bounded-tail-ladder-ge-210-250-v1",
            method="greedy-tail-ladder-v1",
            parameters={
                "rungs": _rungs(),
                "incremental_weight_law": "finite-nested-1-2-4-8-16",
                "maximum_new_world_utility": sum(
                    weight for _threshold, _operator, weight in TAIL_RUNGS
                ),
            },
            tie_law=[
                "largest-weighted-marginal-rung-utility",
                "largest-individual-strict-gt-200-count",
                "largest-training-mean-score",
                "ascending-lineup-id",
            ],
            role="bounded-aggressive-fallback",
            description=(
                "Greedy inclusive 210/220/230/240/250 nested coverage with "
                "finite incremental weights 1/2/4/8/16."
            ),
        ),
        _strategy(
            ordinal=2,
            strategy_id="block-robust-bounded-tail-ge-210-250-v1",
            method="greedy-blockmin-ladder-v1",
            parameters={
                "rungs": _rungs(),
                "incremental_weight_law": "finite-nested-1-2-4-8-16",
                "maximum_new_world_utility": sum(
                    weight for _threshold, _operator, weight in TAIL_RUNGS
                ),
                "block_objective": (
                    "leximin-ascending-per-training-block-weighted-coverage"
                ),
            },
            tie_law=[
                "greatest-post-addition-leximin-block-utility-profile",
                "largest-individual-strict-gt-200-count",
                "largest-training-mean-score",
                "ascending-lineup-id",
            ],
            role="block-robust-fallback",
            description=(
                "Leximin per-block form of the same finite inclusive tail "
                "ladder."
            ),
        ),
        _strategy(
            ordinal=3,
            strategy_id="individual-ge-230-rank-v1",
            method="rank-individual-threshold-count-v1",
            parameters={"threshold": 230.0, "operator": ">="},
            tie_law=[
                "largest-individual-ge-230-world-count",
                "largest-training-mean-score",
                "ascending-lineup-id",
            ],
            role="mechanism-ablation-not-negative-control",
            description=(
                "Rank individual inclusive p(score>=230) using its exact "
                "event-count numerator, without marginal set coverage."
            ),
        ),
    ]


def validate_extreme_tail_strategy_v1(
    value: object, *, expected_ordinal: int
) -> dict[str, object]:
    item = _mapping(value, label=f"extreme-tail strategy[{expected_ordinal}]")
    frozen = frozen_extreme_tail_strategies_v1()
    if type(expected_ordinal) is not int or not 0 <= expected_ordinal < len(frozen):
        _fail("extreme-tail v1 has exactly four registered strategies")
    expected = frozen[expected_ordinal]
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail(f"extreme-tail strategy[{expected_ordinal}] differs from registry")
    _validate_self_hash(
        expected,
        "strategy_sha256",
        label=f"extreme-tail strategy[{expected_ordinal}]",
    )
    return expected


def _validate_strategy_registry() -> list[dict[str, object]]:
    raw = frozen_extreme_tail_strategies_v1()
    if len(raw) != 4:
        _fail("four-law extreme-tail registry differs")
    strategies = [
        validate_extreme_tail_strategy_v1(value, expected_ordinal=ordinal)
        for ordinal, value in enumerate(raw)
    ]
    ids = [str(value["strategy_id"]) for value in strategies]
    hashes = [str(value["strategy_sha256"]) for value in strategies]
    if len(set(ids)) != 4 or len(set(hashes)) != 4:
        _fail("four-law extreme-tail registry identities are not unique")
    return strategies


def _validate_entry_budgets(value: Sequence[int]) -> tuple[int, ...]:
    budgets = tuple(value)
    if budgets != ENTRY_BUDGETS or any(type(budget) is not int for budget in budgets):
        _fail("extreme-tail v1 requires exact entry budgets 4/14/80")
    return budgets


def _all_finite_chunked(matrix: np.ndarray) -> bool:
    """Bound temporary validation memory for realistic accepted matrices."""
    for row_start in range(0, matrix.shape[0], _CANDIDATE_CHUNK_ROWS):
        row_stop = min(row_start + _CANDIDATE_CHUNK_ROWS, matrix.shape[0])
        if not np.isfinite(matrix[row_start:row_stop]).all():
            return False
    return True


def _selector_matrix(
    scores: np.ndarray, lineup_ids: Sequence[str]
) -> np.ndarray:
    matrix = np.asarray(scores)
    if (
        matrix.ndim != 2
        or matrix.shape[1] < 1
        or matrix.shape[0] != len(lineup_ids)
    ):
        _fail("packed selector score/lineup dimensions differ")
    return matrix


def _candidate_chunks(row_count: int):
    for row_start in range(0, row_count, _SELECTOR_CANDIDATE_CHUNK_ROWS):
        yield row_start, min(
            row_start + _SELECTOR_CANDIDATE_CHUNK_ROWS, row_count
        )


def _support_chunk(
    scores: np.ndarray, threshold: float, operator: str
) -> np.ndarray:
    """Match the inherited float32 threshold-boundary law exactly."""
    bound = np.float32(threshold)
    if operator == ">":
        return scores > bound
    if operator == ">=":
        return scores >= bound
    _fail(f"unsupported packed-selector threshold operator {operator!r}")


def _pack_support_mask(
    scores: np.ndarray, *, threshold: float, operator: str
) -> np.ndarray:
    """Build one 1-bit event matrix with bounded dense Boolean temporaries."""
    matrix = np.asarray(scores)
    if matrix.ndim != 2 or matrix.shape[1] < 1:
        _fail("packed support requires one nonempty world matrix")
    packed = np.empty(
        (matrix.shape[0], (matrix.shape[1] + 7) // 8), dtype=np.uint8
    )
    for row_start, row_stop in _candidate_chunks(matrix.shape[0]):
        event = _support_chunk(
            matrix[row_start:row_stop], threshold, operator
        )
        packed[row_start:row_stop] = np.packbits(
            event, axis=1, bitorder=_PACKED_BITORDER
        )
    return packed


def _packed_row_counts(packed: np.ndarray) -> np.ndarray:
    counts = np.empty(packed.shape[0], dtype=np.int64)
    for row_start, row_stop in _candidate_chunks(packed.shape[0]):
        counts[row_start:row_stop] = _PACKED_POPCOUNT[
            packed[row_start:row_stop]
        ].sum(axis=1, dtype=np.int64)
    return counts


def _packed_fresh_counts(
    packed: np.ndarray,
    *,
    row_start: int,
    row_stop: int,
    uncovered: np.ndarray,
) -> np.ndarray:
    fresh = np.bitwise_and(packed[row_start:row_stop], uncovered)
    return _PACKED_POPCOUNT[fresh].sum(axis=1, dtype=np.int64)


def _select_coverage_packed(
    scores: np.ndarray,
    *,
    budget: int,
    threshold: float,
    operator: str,
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    """Exact coverage selector over a 1-bit matrix and bounded row scans."""
    matrix = _selector_matrix(scores, lineup_ids)
    clears = _pack_support_mask(
        matrix, threshold=threshold, operator=operator
    )
    counts = _packed_row_counts(clears)
    means = matrix.mean(axis=1, dtype=np.float64)
    covered = np.zeros(clears.shape[1], dtype=np.uint8)
    remaining = np.ones(matrix.shape[0], dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < budget and np.any(remaining):
        uncovered = np.bitwise_not(covered)
        best: int | None = None
        best_gain = -1
        best_key: tuple[object, ...] | None = None
        for row_start, row_stop in _candidate_chunks(matrix.shape[0]):
            gains = _packed_fresh_counts(
                clears,
                row_start=row_start,
                row_stop=row_stop,
                uncovered=uncovered,
            )
            for position, gain_value in enumerate(gains):
                index = row_start + position
                if not remaining[index]:
                    continue
                gain = int(gain_value)
                key = (
                    -gain,
                    -int(counts[index]),
                    -float(means[index]),
                    lineup_ids[index],
                )
                if best_key is None or key < best_key:
                    best = index
                    best_gain = gain
                    best_key = key
        if best is None or best_gain == 0:
            break
        selected.append(best)
        trace.append({
            "selection_rank": len(selected) - 1,
            "lineup_index": best,
            "lineup_id": lineup_ids[best],
            "marginal_utility": best_gain,
            "discovery_primary_event_count": int(counts[best]),
            "discovery_mean_score": float(means[best]),
        })
        covered |= clears[best]
        remaining[best] = False
    fill = sorted(
        (index for index in range(matrix.shape[0]) if remaining[index]),
        key=lambda index: (
            -int(counts[index]),
            -float(means[index]),
            lineup_ids[index],
        ),
    )
    for best in fill[: budget - len(selected)]:
        selected.append(best)
        trace.append({
            "selection_rank": len(selected) - 1,
            "lineup_index": best,
            "lineup_id": lineup_ids[best],
            "marginal_utility": 0,
            "discovery_primary_event_count": int(counts[best]),
            "discovery_mean_score": float(means[best]),
        })
    return selected, trace


def _select_ladder_packed(
    scores: np.ndarray,
    *,
    budget: int,
    rungs: Sequence[Mapping[str, object]],
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    """Exact finite ladder using packed rung masks and bounded row scans."""
    matrix = _selector_matrix(scores, lineup_ids)
    rung_masks = [
        _pack_support_mask(
            matrix,
            threshold=float(rung["threshold"]),
            operator=str(rung["operator"]),
        )
        for rung in rungs
    ]
    weights = [int(rung["weight"]) for rung in rungs]
    if any(weight <= 0 for weight in weights):
        _fail("ladder weights must be positive integers")
    means = matrix.mean(axis=1, dtype=np.float64)
    primary_counts = _packed_row_counts(
        _pack_support_mask(matrix, threshold=200.0, operator=">")
    )
    covered = [
        np.zeros(mask.shape[1], dtype=np.uint8) for mask in rung_masks
    ]
    remaining = np.ones(matrix.shape[0], dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < budget and np.any(remaining):
        uncovered = [np.bitwise_not(seen) for seen in covered]
        best: int | None = None
        best_utility = -1
        best_key: tuple[object, ...] | None = None
        for row_start, row_stop in _candidate_chunks(matrix.shape[0]):
            utilities = np.zeros(row_stop - row_start, dtype=np.int64)
            for weight, mask, available in zip(
                weights, rung_masks, uncovered, strict=True
            ):
                utilities += weight * _packed_fresh_counts(
                    mask,
                    row_start=row_start,
                    row_stop=row_stop,
                    uncovered=available,
                )
            for position, utility_value in enumerate(utilities):
                index = row_start + position
                if not remaining[index]:
                    continue
                utility = int(utility_value)
                key = (
                    -utility,
                    -int(primary_counts[index]),
                    -float(means[index]),
                    lineup_ids[index],
                )
                if best_key is None or key < best_key:
                    best = index
                    best_utility = utility
                    best_key = key
        if best is None:
            break
        selected.append(best)
        trace.append({
            "selection_rank": len(selected) - 1,
            "lineup_index": best,
            "lineup_id": lineup_ids[best],
            "marginal_utility": best_utility,
            "discovery_primary_event_count": int(primary_counts[best]),
            "discovery_mean_score": float(means[best]),
        })
        for mask, seen in zip(rung_masks, covered, strict=True):
            seen |= mask[best]
        remaining[best] = False
    return selected, trace


def _block_view(scores: np.ndarray) -> tuple[int, int]:
    worlds_per_block = retrieval.WORLDS_PER_BLOCK
    if scores.ndim != 2 or scores.shape[1] % worlds_per_block != 0:
        _fail("discovery scores are not whole world blocks")
    blocks = scores.shape[1] // worlds_per_block
    if blocks < 2:
        _fail("block-aware selection requires at least two discovery blocks")
    return blocks, worlds_per_block


def _select_blockmin_ladder_packed(
    scores: np.ndarray,
    *,
    budget: int,
    rungs: Sequence[Mapping[str, object]],
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    """Exact dynamic-block leximin over block-local packed rung masks."""
    matrix = _selector_matrix(scores, lineup_ids)
    blocks, per_block = _block_view(matrix)
    weights = [int(rung["weight"]) for rung in rungs]
    if any(weight <= 0 for weight in weights):
        _fail("ladder weights must be positive integers")
    rung_block_masks = [
        [
            _pack_support_mask(
                matrix[:, block * per_block:(block + 1) * per_block],
                threshold=float(rung["threshold"]),
                operator=str(rung["operator"]),
            )
            for block in range(blocks)
        ]
        for rung in rungs
    ]
    means = matrix.mean(axis=1, dtype=np.float64)
    primary_counts = _packed_row_counts(
        _pack_support_mask(matrix, threshold=200.0, operator=">")
    )
    covered = [
        [np.zeros(mask.shape[1], dtype=np.uint8) for mask in rung_masks]
        for rung_masks in rung_block_masks
    ]
    block_utilities = np.zeros(blocks, dtype=np.int64)
    remaining = np.ones(matrix.shape[0], dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < budget and np.any(remaining):
        uncovered = [
            [np.bitwise_not(seen) for seen in rung_seen]
            for rung_seen in covered
        ]
        best: int | None = None
        best_added: np.ndarray | None = None
        best_key: tuple[object, ...] | None = None
        for row_start, row_stop in _candidate_chunks(matrix.shape[0]):
            added = np.zeros((row_stop - row_start, blocks), dtype=np.int64)
            for weight, rung_masks, rung_available in zip(
                weights, rung_block_masks, uncovered, strict=True
            ):
                for block, (mask, available) in enumerate(
                    zip(rung_masks, rung_available, strict=True)
                ):
                    added[:, block] += weight * _packed_fresh_counts(
                        mask,
                        row_start=row_start,
                        row_stop=row_stop,
                        uncovered=available,
                    )
            for position in range(row_stop - row_start):
                index = row_start + position
                if not remaining[index]:
                    continue
                after = block_utilities + added[position]
                key = (
                    tuple(-int(value) for value in np.sort(after)),
                    -int(primary_counts[index]),
                    -float(means[index]),
                    lineup_ids[index],
                )
                if best_key is None or key < best_key:
                    best = index
                    best_added = added[position].copy()
                    best_key = key
        if best is None or best_added is None:
            break
        best_after = block_utilities + best_added
        selected.append(best)
        trace.append({
            "selection_rank": len(selected) - 1,
            "lineup_index": best,
            "lineup_id": lineup_ids[best],
            "marginal_utility": int(best_added.sum()),
            "discovery_primary_event_count": int(primary_counts[best]),
            "discovery_mean_score": float(means[best]),
            "block_utilities_before": [
                int(value) for value in block_utilities
            ],
            "block_utilities_added": [int(value) for value in best_added],
            "block_utilities_after": [int(value) for value in best_after],
            "leximin_profile_after": [
                int(value) for value in np.sort(best_after)
            ],
        })
        block_utilities = best_after
        for rung_masks, rung_seen in zip(
            rung_block_masks, covered, strict=True
        ):
            for mask, seen in zip(rung_masks, rung_seen, strict=True):
                seen |= mask[best]
        remaining[best] = False
    return selected, trace


def _select_individual_ge_230(
    scores: np.ndarray,
    *,
    budget: int,
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    """Rank by the exact packed numerator of p(score>=230)."""
    matrix = _selector_matrix(scores, lineup_ids)
    counts = _packed_row_counts(
        _pack_support_mask(matrix, threshold=230.0, operator=">=")
    )
    means = matrix.mean(axis=1, dtype=np.float64)
    selected = sorted(
        range(matrix.shape[0]),
        key=lambda index: (
            -int(counts[index]),
            -float(means[index]),
            lineup_ids[index],
        ),
    )[:budget]
    world_count = int(matrix.shape[1])
    trace = [
        {
            "selection_rank": rank,
            "lineup_index": index,
            "lineup_id": lineup_ids[index],
            "marginal_utility": int(counts[index]),
            "individual_ge_230_event_count": int(counts[index]),
            "individual_ge_230_probability": {
                "numerator": int(counts[index]),
                "denominator": world_count,
            },
            "discovery_primary_event_count": int(counts[index]),
            "discovery_mean_score": float(means[index]),
        }
        for rank, index in enumerate(selected)
    ]
    return selected, trace


def _run_strategy_ranking(
    strategy: Mapping[str, object],
    *,
    training_scores: np.ndarray,
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    method = str(strategy["method"])
    parameters = _mapping(strategy["parameters"], label="strategy parameters")
    if method == "greedy-threshold-coverage-v1":
        selected, trace = _select_coverage_packed(
            training_scores,
            budget=RANKING_DEPTH,
            threshold=float(parameters["threshold"]),
            operator=str(parameters["operator"]),
            lineup_ids=lineup_ids,
        )
    elif method == "greedy-tail-ladder-v1":
        selected, trace = _select_ladder_packed(
            training_scores,
            budget=RANKING_DEPTH,
            rungs=_sequence(parameters["rungs"], label="strategy rungs"),
            lineup_ids=lineup_ids,
        )
    elif method == "greedy-blockmin-ladder-v1":
        selected, trace = _select_blockmin_ladder_packed(
            training_scores,
            budget=RANKING_DEPTH,
            rungs=_sequence(parameters["rungs"], label="strategy rungs"),
            lineup_ids=lineup_ids,
        )
    elif method == "rank-individual-threshold-count-v1":
        selected, trace = _select_individual_ge_230(
            training_scores,
            budget=RANKING_DEPTH,
            lineup_ids=lineup_ids,
        )
    else:
        _fail(f"unregistered extreme-tail method {method!r}")
    if (
        len(selected) != RANKING_DEPTH
        or len(set(selected)) != RANKING_DEPTH
        or len(trace) != RANKING_DEPTH
        or any(
            type(index) is not int
            or not 0 <= index < training_scores.shape[0]
            for index in selected
        )
    ):
        _fail("registered extreme-tail selector did not rank 80 unique entries")
    for rank, (index, raw_trace) in enumerate(zip(selected, trace, strict=True)):
        row = _mapping(raw_trace, label=f"selector trace[{rank}]")
        if (
            row.get("selection_rank") != rank
            or row.get("lineup_index") != index
            or row.get("lineup_id") != lineup_ids[index]
        ):
            _fail("extreme-tail selector trace identity differs")
    return selected, trace


def _score_summary(scores: np.ndarray) -> dict[str, object]:
    matrix = np.asarray(scores)
    if (
        matrix.dtype != np.dtype(np.float64)
        or matrix.ndim != 2
        or not matrix.shape[0]
        or not matrix.shape[1]
        or not _all_finite_chunked(matrix)
    ):
        _fail("tail score summary requires one finite float64 matrix")
    best = matrix.max(axis=0)
    body: dict[str, object] = {
        "lineup_count": int(matrix.shape[0]),
        "world_count": int(matrix.shape[1]),
        "expected_book_max": float(best.mean(dtype=np.float64)),
        "maximum_book_score": float(best.max()),
    }
    for label, threshold, operator in TAIL_THRESHOLDS:
        mask = runner._operator_mask(best, threshold, operator)
        body[f"worlds_{label}"] = int(np.count_nonzero(mask))
        body[f"hit_rate_{label}"] = {
            "numerator": int(np.count_nonzero(mask)),
            "denominator": int(best.size),
        }
    return body


def _metric_vector(
    scores: np.ndarray,
    *,
    blocks: Sequence[str],
    worlds_per_block: int,
) -> dict[str, object]:
    if scores.shape[1] != len(blocks) * worlds_per_block:
        _fail("tail metric score columns differ from named block scope")
    return {
        "aggregate": _score_summary(scores),
        "by_block": [
            {
                "block_id": block,
                **_score_summary(
                    scores[
                        :,
                        ordinal * worlds_per_block:(ordinal + 1)
                        * worlds_per_block,
                    ]
                ),
            }
            for ordinal, block in enumerate(blocks)
        ],
    }


def _opportunity_conversion_summary(
    *,
    book_scores: np.ndarray,
    admitted_pool_scores: np.ndarray,
) -> dict[str, object]:
    if (
        book_scores.ndim != 2
        or admitted_pool_scores.ndim != 2
        or book_scores.shape[1] != admitted_pool_scores.shape[1]
        or not book_scores.shape[0]
        or not admitted_pool_scores.shape[0]
    ):
        _fail("opportunity conversion requires aligned nonempty score matrices")
    book_best = book_scores.max(axis=0)
    pool_best = admitted_pool_scores.max(axis=0)
    if np.any(book_best > pool_best):
        _fail("selected book exceeds its admitted-pool opportunity ceiling")
    world_count = int(pool_best.size)
    thresholds: list[dict[str, object]] = []
    for label, threshold, operator in TAIL_THRESHOLDS:
        opportunity_mask = runner._operator_mask(
            pool_best, threshold, operator
        )
        book_hit_mask = runner._operator_mask(book_best, threshold, operator)
        individual_event_mask = runner._operator_mask(
            book_scores, threshold, operator
        )
        if np.any(book_hit_mask & ~opportunity_mask):
            _fail("book tail hit exists outside admitted-pool opportunity")
        opportunity_count = int(np.count_nonzero(opportunity_mask))
        hit_count = int(np.count_nonzero(book_hit_mask))
        summed_individual_event_count = int(
            np.count_nonzero(individual_event_mask)
        )
        if hit_count > summed_individual_event_count:
            _fail("book event union exceeds summed individual events")
        miss_count = opportunity_count - hit_count
        regret = np.where(
            opportunity_mask,
            pool_best - book_best,
            np.float64(0.0),
        )
        thresholds.append({
            "label": label,
            "threshold": threshold,
            "operator": operator,
            "opportunity_world_count": opportunity_count,
            "book_hit_world_count": hit_count,
            "missed_opportunity_world_count": miss_count,
            "summed_individual_event_count": summed_individual_event_count,
            "event_union_over_summed_individual_events": (
                None
                if summed_individual_event_count == 0
                else {
                    "numerator": hit_count,
                    "denominator": summed_individual_event_count,
                }
            ),
            "opportunity_rate": {
                "numerator": opportunity_count,
                "denominator": world_count,
            },
            "book_hit_rate": {
                "numerator": hit_count,
                "denominator": world_count,
            },
            "opportunity_conversion": (
                None
                if opportunity_count == 0
                else {
                    "numerator": hit_count,
                    "denominator": opportunity_count,
                }
            ),
            "conditional_regret_mean_over_all_worlds": float(
                regret.mean(dtype=np.float64)
            ),
            "conditional_regret_mean_given_opportunity": (
                None
                if opportunity_count == 0
                else float(regret[opportunity_mask].mean(dtype=np.float64))
            ),
        })
    return {"world_count": world_count, "thresholds": thresholds}


def _opportunity_conversion_vector(
    *,
    book_scores: np.ndarray,
    admitted_pool_scores: np.ndarray,
    blocks: Sequence[str],
    worlds_per_block: int,
) -> dict[str, object]:
    expected_columns = len(blocks) * worlds_per_block
    if (
        book_scores.shape[1] != expected_columns
        or admitted_pool_scores.shape[1] != expected_columns
    ):
        _fail("opportunity conversion columns differ from named block scope")
    return {
        "aggregate": _opportunity_conversion_summary(
            book_scores=book_scores,
            admitted_pool_scores=admitted_pool_scores,
        ),
        "by_block": [
            {
                "block_id": block,
                **_opportunity_conversion_summary(
                    book_scores=book_scores[
                        :,
                        ordinal * worlds_per_block:(ordinal + 1)
                        * worlds_per_block,
                    ],
                    admitted_pool_scores=admitted_pool_scores[
                        :,
                        ordinal * worlds_per_block:(ordinal + 1)
                        * worlds_per_block,
                    ],
                ),
            }
            for ordinal, block in enumerate(blocks)
        ],
    }


def _normalized_trace_prefix(
    *,
    selected: Sequence[int],
    base_trace: Sequence[Mapping[str, object]],
    admitted_ids: Sequence[str],
    admitted_global: np.ndarray,
    entry_budget: int,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for rank, (local_index, raw_row) in enumerate(
        zip(selected[:entry_budget], base_trace[:entry_budget], strict=True)
    ):
        row = dict(_mapping(raw_row, label=f"marginal trace[{rank}]"))
        if (
            row.pop("lineup_index", None) != local_index
            or row.get("selection_rank") != rank
            or row.get("lineup_id") != admitted_ids[local_index]
        ):
            _fail("marginal trace prefix identity differs")
        row["admitted_lineup_index"] = int(local_index)
        row["global_lineup_index"] = int(admitted_global[local_index])
        result.append(row)
    if len(result) != entry_budget:
        _fail("marginal trace does not satisfy exact entry budget")
    return result


def _build_book(
    *,
    strategy: Mapping[str, object],
    admission: Mapping[str, object],
    admitted_ids: Sequence[str],
    admitted_global: np.ndarray,
    selected: Sequence[int],
    base_trace: Sequence[Mapping[str, object]],
    entry_budget: int,
    training_scores: np.ndarray,
    training_score_matrix_sha256: str,
    scores: np.ndarray,
    roster_by_id: Mapping[str, Sequence[str]],
    training_blocks: Sequence[str],
    heldout_block: str | None,
    heldout_columns: np.ndarray | None,
    heldout_pool_scores: np.ndarray | None,
    worlds_per_block: int,
    fit_scope_id: str,
    reconstruction_sha256: str,
    dose_authority: str,
) -> dict[str, object]:
    selected_local = [int(value) for value in selected[:entry_budget]]
    if (
        len(selected_local) != entry_budget
        or len(set(selected_local)) != entry_budget
    ):
        _fail("extreme-tail book is not exact-N unique")
    selected_ids = [str(admitted_ids[index]) for index in selected_local]
    selected_global = [int(admitted_global[index]) for index in selected_local]
    selected_rosters = [list(roster_by_id[lineup_id]) for lineup_id in selected_ids]
    selected_training = np.ascontiguousarray(
        training_scores[np.asarray(selected_local, dtype=np.int64)],
        dtype=np.float64,
    )
    heldout_metrics = None
    heldout_opportunity_conversion = None
    heldout_score_matrix_sha256 = None
    if heldout_columns is not None:
        if heldout_pool_scores is None:
            _fail("held-out book lacks its admitted-pool opportunity matrix")
        heldout_scores = np.ascontiguousarray(
            scores[
                np.ix_(
                    np.asarray(selected_global, dtype=np.int64),
                    heldout_columns,
                )
            ],
            dtype=np.float64,
        )
        heldout_score_matrix_sha256 = _score_matrix_sha256(heldout_scores)
        heldout_metrics = _metric_vector(
            heldout_scores,
            blocks=[str(heldout_block)],
            worlds_per_block=worlds_per_block,
        )
        heldout_opportunity_conversion = _opportunity_conversion_vector(
            book_scores=heldout_scores,
            admitted_pool_scores=heldout_pool_scores,
            blocks=[str(heldout_block)],
            worlds_per_block=worlds_per_block,
        )
    elif heldout_pool_scores is not None:
        _fail("all-block fit unexpectedly carries held-out pool scores")
    body = {
        "schema_version": BOOK_SCHEMA,
        "book_id": (
            f"{fit_scope_id}:{admission['admission_id']}:"
            f"{strategy['strategy_id']}:exact-{entry_budget}"
        ),
        "fit_scope_id": fit_scope_id,
        "reconstruction_sha256": reconstruction_sha256,
        "training_blocks": list(training_blocks),
        "heldout_block": heldout_block,
        "admission_id": admission["admission_id"],
        "admission_sha256": admission["admission_sha256"],
        "strategy_id": strategy["strategy_id"],
        "strategy_sha256": strategy["strategy_sha256"],
        "entry_budget": entry_budget,
        "ranking_depth": RANKING_DEPTH,
        "ranking_prefix_law": "exact-prefix-of-one-deterministic-rank-80",
        "input_lineup_ids_sha256": canonical_sha256(list(admitted_ids)),
        "training_score_matrix_sha256": training_score_matrix_sha256,
        "training_score_shape": list(training_scores.shape),
        "selected_training_score_matrix_sha256": _score_matrix_sha256(
            selected_training
        ),
        "heldout_score_matrix_sha256": heldout_score_matrix_sha256,
        "worlds_per_block": worlds_per_block,
        "dose_authority": dose_authority,
        "selected_local_indices": selected_local,
        "selected_global_indices": selected_global,
        "selected_lineup_ids": selected_ids,
        "selected_rosters": selected_rosters,
        "entry_count": len(selected_ids),
        "marginal_trace": _normalized_trace_prefix(
            selected=selected,
            base_trace=base_trace,
            admitted_ids=admitted_ids,
            admitted_global=admitted_global,
            entry_budget=entry_budget,
        ),
        "training_metrics": _metric_vector(
            selected_training,
            blocks=training_blocks,
            worlds_per_block=worlds_per_block,
        ),
        "heldout_metrics_descriptive": heldout_metrics,
        "training_opportunity_conversion": _opportunity_conversion_vector(
            book_scores=selected_training,
            admitted_pool_scores=training_scores,
            blocks=training_blocks,
            worlds_per_block=worlds_per_block,
        ),
        "heldout_opportunity_conversion_descriptive": (
            heldout_opportunity_conversion
        ),
        "threshold_semantics": [
            {"label": label, "threshold": threshold, "operator": operator}
            for label, threshold, operator in TAIL_THRESHOLDS
        ],
        "ordinary_unweighted_r_worlds": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "book_sha256")


def _validated_inputs(
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    worlds_per_block: int | None,
    require_authoritative: bool,
) -> tuple[list[dict[str, object]], np.ndarray, str, str, int]:
    if worlds_per_block is None:
        worlds_per_block = retrieval.WORLDS_PER_BLOCK
    if type(worlds_per_block) is not int or worlds_per_block < 1:
        _fail("worlds_per_block must be a positive exact integer")
    if type(require_authoritative) is not bool:
        _fail("require_authoritative must be an exact boolean")
    if retrieval.WORLDS_PER_BLOCK != worlds_per_block:
        _fail("selector block width differs from worlds_per_block")
    try:
        candidates = runner._validate_provenance(provenance)
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusExtremeTailRetrievalSuiteError(str(exc)) from exc
    scores = np.asarray(union_scores)
    if (
        scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or scores.shape
        != (len(candidates), len(rw.WORLD_BLOCKS) * worlds_per_block)
        or not scores.flags.c_contiguous
    ):
        _fail(
            "canonical union scores must be finite, C-contiguous, exact-shape "
            "native float64"
        )
    if not _all_finite_chunked(scores):
        _fail("canonical union score matrix contains a non-finite value")
    try:
        reconstruction_sha256 = runner._validate_reconstruction_input(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=reconstruction_receipt,
        )
        dose_authority = runner._dose_authority(
            provenance=provenance,
            admission_m=runner.DEFAULT_ADMISSION_M,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
        )
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusExtremeTailRetrievalSuiteError(str(exc)) from exc
    return candidates, scores, reconstruction_sha256, dose_authority, worlds_per_block


def _run_fit_scope_impl(
    *,
    provenance: Mapping[str, object],
    scores: np.ndarray,
    candidates: Sequence[Mapping[str, object]],
    reconstruction_sha256: str,
    dose_authority: str,
    heldout_block: str | None,
    worlds_per_block: int,
    require_authoritative: bool,
) -> dict[str, object]:
    if heldout_block is not None and heldout_block not in rw.WORLD_BLOCKS:
        _fail("heldout block differs")
    try:
        view = runner.build_fit_candidate_view(
            provenance,
            heldout_block=heldout_block,
            dose_authority=dose_authority,
        )
        admission = runner._full_union_admission(view)
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusExtremeTailRetrievalSuiteError(str(exc)) from exc
    eligible_ids = [
        str(row["lineup_id"])
        for row in _sequence(
            view["eligible_candidates"], label="fold-eligible candidates"
        )
    ]
    try:
        runner._validate_admission_partition(admission, eligible_ids=eligible_ids)
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusExtremeTailRetrievalSuiteError(str(exc)) from exc
    admitted_ids = [
        str(value)
        for value in _sequence(
            admission["admitted_lineup_ids"], label="admitted lineup ids"
        )
    ]
    if (
        admitted_ids != sorted(set(admitted_ids))
        or len(admitted_ids) < RANKING_DEPTH
    ):
        _fail("fold-eligible full union cannot satisfy exact-80 ranking")
    candidate_ids = [str(row["lineup_id"]) for row in candidates]
    global_index_by_id = {
        lineup_id: index for index, lineup_id in enumerate(candidate_ids)
    }
    roster_by_id = {
        str(row["lineup_id"]): tuple(
            str(value) for value in row["roster_player_ids"]
        )
        for row in candidates
    }
    try:
        admitted_global = np.asarray(
            [global_index_by_id[lineup_id] for lineup_id in admitted_ids],
            dtype=np.int64,
        )
    except KeyError as exc:
        raise CorpusExtremeTailRetrievalSuiteError(
            "full-union admission contains a noncanonical lineup"
        ) from exc
    training_blocks = [
        block for block in rw.WORLD_BLOCKS if block != heldout_block
    ]
    training_columns = runner._block_columns(
        training_blocks, worlds_per_block=worlds_per_block
    )
    heldout_columns = (
        None
        if heldout_block is None
        else runner._block_columns(
            [heldout_block], worlds_per_block=worlds_per_block
        )
    )
    training_scores = np.ascontiguousarray(
        scores[np.ix_(admitted_global, training_columns)], dtype=np.float64
    )
    training_score_matrix_sha256 = _score_matrix_sha256(training_scores)
    heldout_pool_scores = (
        None
        if heldout_columns is None
        else np.ascontiguousarray(
            scores[np.ix_(admitted_global, heldout_columns)],
            dtype=np.float64,
        )
    )
    strategies = _validate_strategy_registry()
    books: list[dict[str, object]] = []
    for strategy in strategies:
        selected, base_trace = _run_strategy_ranking(
            strategy,
            training_scores=training_scores,
            lineup_ids=admitted_ids,
        )
        for entry_budget in ENTRY_BUDGETS:
            books.append(_build_book(
                strategy=strategy,
                admission=admission,
                admitted_ids=admitted_ids,
                admitted_global=admitted_global,
                selected=selected,
                base_trace=base_trace,
                entry_budget=entry_budget,
                training_scores=training_scores,
                training_score_matrix_sha256=training_score_matrix_sha256,
                scores=scores,
                roster_by_id=roster_by_id,
                training_blocks=training_blocks,
                heldout_block=heldout_block,
                heldout_columns=heldout_columns,
                heldout_pool_scores=heldout_pool_scores,
                worlds_per_block=worlds_per_block,
                fit_scope_id=str(view["fit_scope_id"]),
                reconstruction_sha256=reconstruction_sha256,
                dose_authority=dose_authority,
            ))
    if (
        len(books) != 4 * len(ENTRY_BUDGETS)
        or len({str(book["book_id"]) for book in books}) != len(books)
    ):
        _fail("extreme-tail fit-scope book lattice differs")
    heldout_pool_metrics = None
    if heldout_pool_scores is not None:
        heldout_pool_metrics = _metric_vector(
            heldout_pool_scores,
            blocks=[str(heldout_block)],
            worlds_per_block=worlds_per_block,
        )
    body = {
        "schema_version": SCOPE_SCHEMA,
        "fit_scope_id": view["fit_scope_id"],
        "reconstruction_sha256": reconstruction_sha256,
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "training_blocks": training_blocks,
        "heldout_block": heldout_block,
        "worlds_per_block": worlds_per_block,
        "dose_authority": dose_authority,
        "require_authoritative": require_authoritative,
        "candidate_view": view,
        "admission_law": FULL_UNION_ADMISSION_LAW,
        "admission": admission,
        "strategy_registry": strategies,
        "strategy_registry_sha256": canonical_sha256(strategies),
        "selector_implementation_sha256": (
            frozen_selector_implementation_contract_v1()[
                "selector_implementation_sha256"
            ]
        ),
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "training_score_matrix_sha256": training_score_matrix_sha256,
        "admitted_pool_training_metrics": _metric_vector(
            training_scores,
            blocks=training_blocks,
            worlds_per_block=worlds_per_block,
        ),
        "admitted_pool_heldout_metrics_descriptive": heldout_pool_metrics,
        "book_count": len(books),
        "books": books,
        "uses_matchup_admission": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "fit_scope_sha256")


def run_extreme_tail_fit_scope_v1(
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    heldout_block: str | None,
    entry_budgets: Sequence[int] = ENTRY_BUDGETS,
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Build the four rankings and exact 4/14/80 books for one fit scope."""
    _validate_entry_budgets(entry_budgets)
    candidates, scores, reconstruction_sha256, dose_authority, width = (
        _validated_inputs(
            provenance=provenance,
            union_scores=union_scores,
            reconstruction_receipt=reconstruction_receipt,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
        )
    )
    return _run_fit_scope_impl(
        provenance=provenance,
        scores=scores,
        candidates=candidates,
        reconstruction_sha256=reconstruction_sha256,
        dose_authority=dose_authority,
        heldout_block=heldout_block,
        worlds_per_block=width,
        require_authoritative=require_authoritative,
    )


def run_extreme_tail_retrieval_suite_v1(
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    entry_budgets: Sequence[int] = ENTRY_BUDGETS,
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Build five identity-safe held-out folds and one all-block final fit."""
    budgets = _validate_entry_budgets(entry_budgets)
    candidates, scores, reconstruction_sha256, dose_authority, width = (
        _validated_inputs(
            provenance=provenance,
            union_scores=union_scores,
            reconstruction_receipt=reconstruction_receipt,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
        )
    )
    folds = [
        _run_fit_scope_impl(
            provenance=provenance,
            scores=scores,
            candidates=candidates,
            reconstruction_sha256=reconstruction_sha256,
            dose_authority=dose_authority,
            heldout_block=heldout,
            worlds_per_block=width,
            require_authoritative=require_authoritative,
        )
        for heldout in rw.WORLD_BLOCKS
    ]
    final_fit = _run_fit_scope_impl(
        provenance=provenance,
        scores=scores,
        candidates=candidates,
        reconstruction_sha256=reconstruction_sha256,
        dose_authority=dose_authority,
        heldout_block=None,
        worlds_per_block=width,
        require_authoritative=require_authoritative,
    )
    strategies = _validate_strategy_registry()
    implementation = frozen_selector_implementation_contract_v1()
    books_per_scope = len(strategies) * len(budgets)
    binding = _mapping(
        reconstruction_receipt["matrix_binding"], label="matrix binding"
    )
    body = {
        "schema_version": SUITE_SCHEMA,
        "suite_law_id": SUITE_LAW_ID,
        "slate": provenance["slate"],
        "input_binding": {
            "reconstruction_sha256": reconstruction_sha256,
            "candidate_provenance_sha256": provenance[
                "candidate_provenance_sha256"
            ],
            "matrix_binding_sha256": binding["matrix_binding_sha256"],
            "score_matrix_sha256": binding["score_matrix_sha256"],
            "lineup_ids_sha256": binding["lineup_ids_sha256"],
            "world_ids_sha256": binding["world_ids_sha256"],
            "score_shape": binding["shape"],
        },
        "strategy_registry": strategies,
        "strategy_registry_sha256": canonical_sha256(strategies),
        "selector_implementation_binding": {
            "implementation_id": implementation["implementation_id"],
            "selector_implementation_sha256": implementation[
                "selector_implementation_sha256"
            ],
        },
        "selector_implementation_contract": implementation,
        "entry_budgets": list(budgets),
        "ranking_depth": RANKING_DEPTH,
        "folds": folds,
        "final_fit": final_fit,
        "fold_count": len(folds),
        "books_per_scope": books_per_scope,
        "cross_fit_book_count": len(folds) * books_per_scope,
        "final_fit_book_count": books_per_scope,
        "worlds_per_block": width,
        "dose_authority": dose_authority,
        "require_authoritative": require_authoritative,
        "full_union_admission_only": True,
        "final_fit_is_distinct_all_block_refit": True,
        "requires_separately_validated_support_census_before_effect_read": True,
        "nominated_book_pair_event_diagnostic_prerequisite": {
            "required_before_promotion": True,
            "must_be_separately_bound": True,
            "required_metrics": [
                "pair-event-intersection-jaccard",
                "duplicate-event-vector-groups",
            ],
        },
        "ordinary_unweighted_r_worlds": True,
        "evidence_tier": "outcome-blind-simulated-mechanism-research",
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "suite_sha256")


def validate_extreme_tail_fit_scope_v1(
    value: Mapping[str, object],
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    heldout_block: str | None,
    entry_budgets: Sequence[int] = ENTRY_BUDGETS,
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Replay one retained fit scope and require canonical byte identity."""
    retained = _mapping(value, label="retained extreme-tail fit scope")
    expected = run_extreme_tail_fit_scope_v1(
        provenance=provenance,
        union_scores=union_scores,
        reconstruction_receipt=reconstruction_receipt,
        heldout_block=heldout_block,
        entry_budgets=entry_budgets,
        worlds_per_block=worlds_per_block,
        require_authoritative=require_authoritative,
    )
    if canonical_json_bytes(retained) != canonical_json_bytes(expected):
        _fail("retained extreme-tail fit scope canonical replay differs")
    return expected


def validate_extreme_tail_retrieval_suite_v1(
    value: Mapping[str, object],
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    entry_budgets: Sequence[int] = ENTRY_BUDGETS,
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Replay all five folds and the final fit, requiring byte identity."""
    retained = _mapping(value, label="retained extreme-tail suite")
    expected = run_extreme_tail_retrieval_suite_v1(
        provenance=provenance,
        union_scores=union_scores,
        reconstruction_receipt=reconstruction_receipt,
        entry_budgets=entry_budgets,
        worlds_per_block=worlds_per_block,
        require_authoritative=require_authoritative,
    )
    if canonical_json_bytes(retained) != canonical_json_bytes(expected):
        _fail("retained extreme-tail suite canonical replay differs")
    return expected


__all__ = [
    "BOOK_SCHEMA",
    "CorpusExtremeTailRetrievalSuiteError",
    "ENTRY_BUDGETS",
    "FULL_UNION_ADMISSION_LAW",
    "RANKING_DEPTH",
    "SCOPE_SCHEMA",
    "SELECTOR_IMPLEMENTATION_ID",
    "SELECTOR_IMPLEMENTATION_SCHEMA",
    "STRATEGY_SCHEMA",
    "SUITE_LAW_ID",
    "SUITE_SCHEMA",
    "TAIL_RUNGS",
    "TAIL_THRESHOLDS",
    "frozen_selector_implementation_contract_v1",
    "frozen_extreme_tail_strategies_v1",
    "run_extreme_tail_fit_scope_v1",
    "run_extreme_tail_retrieval_suite_v1",
    "validate_extreme_tail_fit_scope_v1",
    "validate_extreme_tail_retrieval_suite_v1",
    "validate_extreme_tail_strategy_v1",
]
