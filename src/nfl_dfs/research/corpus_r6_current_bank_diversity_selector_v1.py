"""One bounded effective-independent-shots selector for the R6 current bank.

The selector ranks 150 of at most 250 candidates from the same four-block
training score matrix used by the grouped current-bank selectors.  It builds a
quality-weighted determinantal point-process (DPP) kernel whose two equally
weighted redundancy features are:

* cosine similarity of inclusive-230 training-world hit signatures; and
* cosine similarity of the nine-player roster incidence vectors.

Candidate quality is ``1 + inclusive_230_hit_count``.  A deterministic greedy
MAP order then maximizes the exact conditional determinant gain at each step.
That greedy order is an approximation to the globally optimal size-k maximum
determinant subset (an NP-hard problem); this module makes no global-optimality
or production-authority claim.  Its value as a challenger is precisely that it
trades a small amount of individual tail frequency for less redundant tail
shots and roster constructions.

No realized outcomes, held-out score columns, object-store reader, graph
client, or production mutation capability is accepted by any public function.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Final

import numpy as np

from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as grouped_source,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as current_contract,
)


RESULT_SCHEMA: Final = "corpus-r6-current-bank-diversity-selector-result/v1"
CONTRACT_SCHEMA: Final = "corpus-r6-current-bank-diversity-selector-contract/v1"
STRATEGY_ID: Final = "effective-independent-tail-shots-dpp-ge-230-v1"
EXPECTED_CONTRACT_SHA256: Final = (
    "747416eb96d7a51eb1846ab08deac3e6d99f65b083b09b2dfd4860245d2c3869"
)
ENTRY_BUDGET: Final = 150
PREFIX_SIZES: Final = (80, 100, 150)
MIN_CANDIDATES: Final = ENTRY_BUDGET
MAX_CANDIDATES: Final = 250
MAX_WORLDS_PER_BLOCK: Final = 10_000
TAIL_THRESHOLD_DK: Final = 230.0
ROSTER_SIZE: Final = 9
TAIL_SIMILARITY_WEIGHT_NUMERATOR: Final = 1
ROSTER_SIMILARITY_WEIGHT_NUMERATOR: Final = 1
SIMILARITY_WEIGHT_DENOMINATOR: Final = 2
DIAGONAL_FLOOR_FRACTION: Final = 1e-9
DECISION_LOG_DECIMALS: Final = 12
CANDIDATE_CHUNK_ROWS: Final = 64
PAIR_CHUNK_ROWS: Final = 64
PACKED_BITORDER: Final = "little"

_POPCOUNT: Final = np.asarray(
    [value.bit_count() for value in range(256)], dtype=np.uint8
)
_FALSE_POLICY: Final = {
    "uses_realized_outcomes": False,
    "historical_scoring_performed": False,
    "historical_scoring_licensed": False,
    "heldout_score_columns_present": False,
    "heldout_artifact_identity_present": False,
    "corpus_regeneration_performed": False,
    "graph_mutation_performed": False,
    "production_change_performed": False,
    "promotion_authority": False,
    "decision_authority": False,
    "publication_authority": False,
}


class CorpusR6CurrentBankDiversitySelectorV1Error(ValueError):
    """The current-bank diversity selector cannot execute exactly."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankDiversitySelectorV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return current_contract.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise CorpusR6CurrentBankDiversitySelectorV1Error(
            "value is not canonical finite JSON"
        ) from exc


def _sha(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(body: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(body)
    if field in result:
        _fail(f"{field} cannot already be present")
    result[field] = _sha(result)
    return result


def _stable_float(value: float) -> float:
    """Return a finite, compact diagnostic float; never a decision input."""
    if not np.isfinite(value):
        _fail("diagnostic float is not finite")
    return float(f"{value:.12g}")


def frozen_diversity_selector_contract_v1() -> dict[str, object]:
    """Return the one preregistered mechanism; there is intentionally no grid."""
    body: dict[str, object] = {
        "schema_version": CONTRACT_SCHEMA,
        "strategy_id": STRATEGY_ID,
        "entry_budget": ENTRY_BUDGET,
        "prefix_sizes": list(PREFIX_SIZES),
        "input_law": {
            "candidate_count_min": MIN_CANDIDATES,
            "candidate_count_max": MAX_CANDIDATES,
            "training_block_count": grouped_source.FIT_BLOCK_COUNT,
            "worlds_per_block_max": MAX_WORLDS_PER_BLOCK,
            "score_matrix_dtype": "float64-le",
            "candidate_order": "ascending-lineup-id",
            "heldout_columns_present": False,
        },
        "quality_law": {
            "tail_threshold_dk": TAIL_THRESHOLD_DK,
            "inclusive": True,
            "candidate_quality_mass": "1-plus-training-tail-hit-count",
            "dpp_quality_amplitude": "sqrt-candidate-quality-mass",
        },
        "redundancy_kernel": {
            "tail_component": (
                "cosine-of-inclusive-230-binary-training-world-signatures"
            ),
            "roster_component": "cosine-of-nine-player-incidence-vectors",
            "tail_weight_numerator": TAIL_SIMILARITY_WEIGHT_NUMERATOR,
            "roster_weight_numerator": ROSTER_SIMILARITY_WEIGHT_NUMERATOR,
            "weight_denominator": SIMILARITY_WEIGHT_DENOMINATOR,
            "quality_weighting": "diag-sqrt-quality-times-similarity-times-diag",
            "diagonal_floor_fraction": DIAGONAL_FLOOR_FRACTION,
        },
        "ordering_law": {
            "objective": "quality-weighted-dpp-log-determinant",
            "algorithm": "deterministic-greedy-map-cholesky-v1",
            "decision_value": "conditional-determinant-gain",
            "decision_log_quantization_decimals": DECISION_LOG_DECIMALS,
            "tie_break": "ascending-lineup-id",
            "one_ranked_order_for_all_prefixes": True,
        },
        "approximation_disclosure": {
            "global_size-k_maximum_determinant_solved_exactly": False,
            "reason": "global-cardinality-constrained-dpp-map-is-np-hard",
            "greedy_conditional_gain_computed_exactly_for_current_prefix": True,
            "floating_decision_quantization_is_part_of_law": True,
            "promotion_requires_heldout-realized-comparison": True,
        },
        "resource_law": {
            "tail_mask_storage": "packed-little-endian-bits",
            "persistent-full-boolean-world-matrix": False,
            "persistent-full-float64-matrix-clone": False,
            "time_bound": "O(N^2*W/8-plus-K*N^2)",
            "working_memory_bound": "O(N*W/8-plus-N^2-plus-K*N)",
            "N_max": MAX_CANDIDATES,
            "W_max": grouped_source.FIT_BLOCK_COUNT * MAX_WORLDS_PER_BLOCK,
            "K": ENTRY_BUDGET,
        },
        "policy": dict(_FALSE_POLICY),
    }
    contract = _with_hash(body, field="contract_sha256")
    if contract["contract_sha256"] != EXPECTED_CONTRACT_SHA256:
        _fail("frozen diversity selector contract drifted")
    return contract


def _validated_inputs(
    *,
    sampled_lineup_ids: object,
    training_score_matrix: object,
    candidate_rows: object,
    training_blocks: object,
    worlds_per_block: object,
) -> tuple[
    list[str], np.ndarray, list[dict[str, object]], tuple[str, ...], str, int
]:
    try:
        retained = grouped_source._validated_inputs(
            sampled_lineup_ids=sampled_lineup_ids,
            training_score_matrix=training_score_matrix,
            candidate_rows=candidate_rows,
            training_blocks=training_blocks,
            worlds_per_block=worlds_per_block,
        )
    except grouped_source.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
        raise CorpusR6CurrentBankDiversitySelectorV1Error(str(exc)) from exc
    ids, scores, candidates, blocks, heldout, retained_worlds = retained
    if not MIN_CANDIDATES <= len(ids) <= MAX_CANDIDATES:
        _fail("diversity selector requires 150..250 sampled candidates")
    if retained_worlds > MAX_WORLDS_PER_BLOCK:
        _fail("worlds_per_block exceeds the frozen 10,000-world resource cap")
    return ids, scores, candidates, blocks, heldout, retained_worlds


def _packed_tail_signatures_v1(
    scores: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    candidate_count, world_count = scores.shape
    if world_count % 8 != 0:
        _fail("training world count must be divisible by eight")
    packed = np.empty((candidate_count, world_count // 8), dtype=np.uint8)
    counts = np.empty(candidate_count, dtype=np.int64)
    for start in range(0, candidate_count, CANDIDATE_CHUNK_ROWS):
        stop = min(start + CANDIDATE_CHUNK_ROWS, candidate_count)
        tail = scores[start:stop] >= TAIL_THRESHOLD_DK
        counts[start:stop] = np.count_nonzero(tail, axis=1)
        packed[start:stop] = np.packbits(
            tail, axis=1, bitorder=PACKED_BITORDER
        )
    return packed, counts


def _tail_intersection_counts_v1(packed: np.ndarray) -> np.ndarray:
    candidate_count = packed.shape[0]
    intersections = np.zeros(
        (candidate_count, candidate_count), dtype=np.int32
    )
    diagonal = _POPCOUNT[packed].sum(axis=1, dtype=np.int64)
    if np.any(diagonal > np.iinfo(np.int32).max):
        _fail("tail intersection count exceeds int32 resource law")
    np.fill_diagonal(intersections, diagonal.astype(np.int32, copy=False))
    for left in range(candidate_count - 1):
        for start in range(left + 1, candidate_count, PAIR_CHUNK_ROWS):
            stop = min(start + PAIR_CHUNK_ROWS, candidate_count)
            both = np.bitwise_and(packed[start:stop], packed[left])
            counts = _POPCOUNT[both].sum(axis=1, dtype=np.int64)
            intersections[left, start:stop] = counts
            intersections[start:stop, left] = counts
    return intersections


def _roster_overlap_counts_v1(
    candidates: Sequence[Mapping[str, object]],
) -> np.ndarray:
    rosters = [set(row["roster_player_ids"]) for row in candidates]
    candidate_count = len(rosters)
    overlaps = np.empty((candidate_count, candidate_count), dtype=np.uint8)
    for left in range(candidate_count):
        overlaps[left, left] = ROSTER_SIZE
        for right in range(left + 1, candidate_count):
            overlap = len(rosters[left] & rosters[right])
            overlaps[left, right] = overlap
            overlaps[right, left] = overlap
    return overlaps


def _build_quality_weighted_kernel_v1(
    *,
    packed: np.ndarray,
    tail_counts: np.ndarray,
    roster_overlaps: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    intersections = _tail_intersection_counts_v1(packed)
    tail_denominator = np.sqrt(
        np.multiply.outer(tail_counts, tail_counts).astype(np.float64)
    )
    tail_similarity = np.zeros(intersections.shape, dtype=np.float64)
    np.divide(
        intersections,
        tail_denominator,
        out=tail_similarity,
        where=tail_denominator > 0.0,
    )
    roster_similarity = roster_overlaps.astype(np.float64) / float(ROSTER_SIZE)
    similarity = (
        TAIL_SIMILARITY_WEIGHT_NUMERATOR * tail_similarity
        + ROSTER_SIMILARITY_WEIGHT_NUMERATOR * roster_similarity
    ) / float(SIMILARITY_WEIGHT_DENOMINATOR)
    quality_mass = tail_counts.astype(np.float64) + 1.0
    quality_amplitude = np.sqrt(quality_mass)
    kernel = similarity * np.multiply.outer(
        quality_amplitude, quality_amplitude
    )
    diagonal_indices = np.diag_indices_from(kernel)
    kernel[diagonal_indices] += DIAGONAL_FLOOR_FRACTION * quality_mass
    # Guard against an accidental asymmetric kernel before Cholesky updates.
    if not np.array_equal(kernel, kernel.T):
        _fail("quality-weighted diversity kernel is not exactly symmetric")
    return kernel, tail_similarity, intersections


def _greedy_dpp_order_v1(
    *,
    kernel: np.ndarray,
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    candidate_count = kernel.shape[0]
    if kernel.shape != (candidate_count, candidate_count):
        _fail("DPP kernel must be square")
    residual = np.diag(kernel).copy()
    if not np.isfinite(residual).all() or np.any(residual <= 0.0):
        _fail("DPP kernel diagonal must be finite and positive")
    basis = np.zeros((ENTRY_BUDGET, candidate_count), dtype=np.float64)
    selected_mask = np.zeros(candidate_count, dtype=np.bool_)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    cumulative_logdet = 0.0
    negative_tolerance = float(np.max(residual)) * 1e-10

    for ordinal in range(ENTRY_BUDGET):
        eligible = np.flatnonzero(~selected_mask)
        eligible_residual = residual[eligible]
        if np.any(eligible_residual <= 0.0):
            _fail("DPP conditional determinant gain became nonpositive")
        decision_logs = np.round(
            np.log(eligible_residual), decimals=DECISION_LOG_DECIMALS
        )
        best_log = float(np.max(decision_logs))
        tied = eligible[decision_logs == best_log]
        # Inputs are required to be in ascending lineup-ID order; the first
        # tied index therefore implements the frozen canonical tie break.
        chosen = int(tied[0])
        pivot = float(residual[chosen])
        raw_log_gain = float(np.log(pivot))
        cumulative_logdet += raw_log_gain
        trace.append({
            "ordinal": ordinal,
            "canonical_index": chosen,
            "lineup_id": lineup_ids[chosen],
            "conditional_determinant_gain": _stable_float(pivot),
            "conditional_logdet_gain": _stable_float(raw_log_gain),
            "decision_logdet_gain": _stable_float(best_log),
            "cumulative_logdet": _stable_float(cumulative_logdet),
        })
        selected.append(chosen)
        selected_mask[chosen] = True

        prior_projection = (
            np.zeros(candidate_count, dtype=np.float64)
            if ordinal == 0
            else basis[:ordinal, chosen] @ basis[:ordinal]
        )
        basis_row = (kernel[chosen] - prior_projection) / np.sqrt(pivot)
        basis[ordinal] = basis_row
        residual -= np.square(basis_row)
        minimum = float(np.min(residual[~selected_mask])) if ordinal < ENTRY_BUDGET - 1 else 0.0
        if minimum < -negative_tolerance:
            _fail("DPP Cholesky residual violated the numerical PSD guard")
        residual[~selected_mask] = np.maximum(
            residual[~selected_mask], np.finfo(np.float64).tiny
        )
        residual[selected_mask] = -np.inf

    return selected, trace


def _prefix_diagnostics_v1(
    *,
    selected: Sequence[int],
    scores: np.ndarray,
    packed: np.ndarray,
    tail_counts: np.ndarray,
    tail_similarity: np.ndarray,
    roster_overlaps: np.ndarray,
    candidates: Sequence[Mapping[str, object]],
    trace: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    indices = np.asarray(selected, dtype=np.int64)
    current_max: np.ndarray | None = None
    tail_union = np.zeros(packed.shape[1], dtype=np.uint8)
    player_counts: Counter[str] = Counter()
    for index in selected:
        current_max = (
            scores[index].copy()
            if current_max is None
            else np.maximum(current_max, scores[index])
        )
        tail_union |= packed[index]
        player_counts.update(candidates[index]["roster_player_ids"])
    if current_max is None:
        _fail("prefix cannot be empty")
    upper = np.triu_indices(len(selected), k=1)
    prefix_roster = roster_overlaps[np.ix_(indices, indices)][upper]
    prefix_tail = tail_similarity[np.ix_(indices, indices)][upper]
    return {
        "fit_book_expected_max_dk": _stable_float(
            float(current_max.mean(dtype=np.float64))
        ),
        "fit_book_inclusive_ge_230_union_count": int(
            _POPCOUNT[tail_union].sum(dtype=np.int64)
        ),
        "selected_individual_inclusive_ge_230_count_sum": int(
            tail_counts[indices].sum(dtype=np.int64)
        ),
        "pair_count": int(prefix_roster.size),
        "maximum_pair_roster_overlap": int(prefix_roster.max(initial=0)),
        "mean_pair_roster_overlap": _stable_float(
            float(prefix_roster.mean(dtype=np.float64))
        ),
        "maximum_pair_tail_cosine_similarity": _stable_float(
            float(prefix_tail.max(initial=0.0))
        ),
        "mean_pair_tail_cosine_similarity": _stable_float(
            float(prefix_tail.mean(dtype=np.float64))
        ),
        "unique_player_count": len(player_counts),
        "maximum_player_exposure_count": max(player_counts.values()),
        "greedy_cumulative_logdet": trace[len(selected) - 1][
            "cumulative_logdet"
        ],
    }


def run_effective_independent_shots_selector_v1(
    *,
    sampled_lineup_ids: object,
    training_score_matrix: object,
    candidate_rows: object,
    training_blocks: object,
    worlds_per_block: object,
) -> dict[str, object]:
    """Return one deterministic 150-lineup order and its 80/100/150 prefixes."""
    contract = frozen_diversity_selector_contract_v1()
    (
        lineup_ids,
        scores,
        candidates,
        blocks,
        heldout_block,
        retained_worlds_per_block,
    ) = _validated_inputs(
        sampled_lineup_ids=sampled_lineup_ids,
        training_score_matrix=training_score_matrix,
        candidate_rows=candidate_rows,
        training_blocks=training_blocks,
        worlds_per_block=worlds_per_block,
    )
    packed, tail_counts = _packed_tail_signatures_v1(scores)
    roster_overlaps = _roster_overlap_counts_v1(candidates)
    kernel, tail_similarity, intersections = _build_quality_weighted_kernel_v1(
        packed=packed,
        tail_counts=tail_counts,
        roster_overlaps=roster_overlaps,
    )
    selected, trace = _greedy_dpp_order_v1(
        kernel=kernel, lineup_ids=lineup_ids
    )
    if len(selected) != ENTRY_BUDGET or len(set(selected)) != ENTRY_BUDGET:
        _fail("diversity selector did not return exact-150 unique candidates")
    selected_ids = [lineup_ids[index] for index in selected]

    prefixes: list[dict[str, object]] = []
    for prefix_size in PREFIX_SIZES:
        prefix_indices = selected[:prefix_size]
        prefix_ids = selected_ids[:prefix_size]
        prefix_rosters = [
            candidates[index]["roster_player_ids"] for index in prefix_indices
        ]
        diagnostics = _prefix_diagnostics_v1(
            selected=prefix_indices,
            scores=scores,
            packed=packed,
            tail_counts=tail_counts,
            tail_similarity=tail_similarity,
            roster_overlaps=roster_overlaps,
            candidates=candidates,
            trace=trace,
        )
        prefixes.append(_with_hash({
            "prefix_size": prefix_size,
            "selected_lineup_ids": prefix_ids,
            "selected_lineup_ids_sha256": _sha(prefix_ids),
            "selected_rosters_sha256": _sha(prefix_rosters),
            "compact_diagnostics": diagnostics,
            "compact_diagnostics_sha256": _sha(diagnostics),
        }, field="prefix_sha256"))

    input_binding = _with_hash({
        "ordered_sampled_lineup_ids_sha256": _sha(lineup_ids),
        "sampled_candidate_rows_sha256": _sha(candidates),
        "candidate_count": len(lineup_ids),
        "training_blocks": list(blocks),
        "heldout_block_label_only": heldout_block,
        "worlds_per_block": retained_worlds_per_block,
        "training_score_shape": list(scores.shape),
        "training_score_matrix_sha256": grouped_source._matrix_sha(scores),
        "input_score_matrix_object_reused": True,
        "persistent_full_boolean_world_matrix_created": False,
        "persistent_full_float64_matrix_clone_created": False,
        "score_matrix_mutated": False,
        "heldout_score_columns_present": False,
        "uses_realized_outcomes": False,
        "caller_supplied_inputs_only": True,
        "production_authority_validated": False,
    }, field="input_binding_sha256")
    preprocessing = _with_hash({
        "tail_threshold_dk": TAIL_THRESHOLD_DK,
        "tail_threshold_inclusive": True,
        "packed_bitorder": PACKED_BITORDER,
        "packed_tail_shape": list(packed.shape),
        "packed_tail_sha256": grouped_source._array_sha(
            packed, label="diversity-packed-inclusive-ge-230", dtype=np.uint8
        ),
        "tail_counts_sha256": grouped_source._array_sha(
            tail_counts, label="diversity-inclusive-ge-230-counts", dtype=np.int64
        ),
        "tail_intersection_counts_sha256": grouped_source._array_sha(
            intersections,
            label="diversity-inclusive-ge-230-intersections",
            dtype=np.int32,
        ),
        "roster_overlap_counts_sha256": grouped_source._array_sha(
            roster_overlaps, label="diversity-roster-overlaps", dtype=np.uint8
        ),
        "kernel_shape": list(kernel.shape),
        "kernel_sha256": grouped_source._array_sha(
            kernel, label="diversity-quality-weighted-dpp-kernel", dtype=np.float64
        ),
        "quality_mass_min": int(tail_counts.min()) + 1,
        "quality_mass_max": int(tail_counts.max()) + 1,
        "pairwise_tail_intersections_exact_integer": True,
        "pairwise_roster_overlaps_exact_integer": True,
        "shared_score_matrix_preprocessing_pass_count": 1,
    }, field="preprocessing_sha256")
    body: dict[str, object] = {
        "schema_version": RESULT_SCHEMA,
        "strategy_contract": contract,
        "strategy_contract_sha256": contract["contract_sha256"],
        "input_binding": input_binding,
        "input_binding_sha256": input_binding["input_binding_sha256"],
        "preprocessing": preprocessing,
        "preprocessing_sha256": preprocessing["preprocessing_sha256"],
        "selected_canonical_indices": selected,
        "selected_lineup_ids": selected_ids,
        "selected_lineup_ids_sha256": _sha(selected_ids),
        "selected_rosters_sha256": _sha([
            candidates[index]["roster_player_ids"] for index in selected
        ]),
        "selection_trace": trace,
        "selection_trace_sha256": _sha(trace),
        "entry_budget": ENTRY_BUDGET,
        "prefix_sizes": list(PREFIX_SIZES),
        "prefixes": prefixes,
        "prefix_sha256s": [row["prefix_sha256"] for row in prefixes],
        "policy": dict(_FALSE_POLICY),
    }
    return _with_hash(body, field="result_sha256")


def validate_effective_independent_shots_result_v1(
    value: object,
    *,
    sampled_lineup_ids: object,
    training_score_matrix: object,
    candidate_rows: object,
    training_blocks: object,
    worlds_per_block: object,
) -> dict[str, object]:
    """Replay the pure selector and require byte-exact canonical equality."""
    if not isinstance(value, Mapping):
        _fail("diversity selector result must be one mapping")
    retained = dict(value)
    _canonical(retained)
    expected = run_effective_independent_shots_selector_v1(
        sampled_lineup_ids=sampled_lineup_ids,
        training_score_matrix=training_score_matrix,
        candidate_rows=candidate_rows,
        training_blocks=training_blocks,
        worlds_per_block=worlds_per_block,
    )
    if _canonical(retained) != _canonical(expected):
        _fail("diversity selector result differs from exact pure replay")
    return expected


__all__ = [
    "CONTRACT_SCHEMA",
    "CorpusR6CurrentBankDiversitySelectorV1Error",
    "ENTRY_BUDGET",
    "EXPECTED_CONTRACT_SHA256",
    "PREFIX_SIZES",
    "RESULT_SCHEMA",
    "STRATEGY_ID",
    "frozen_diversity_selector_contract_v1",
    "run_effective_independent_shots_selector_v1",
    "validate_effective_independent_shots_result_v1",
]
