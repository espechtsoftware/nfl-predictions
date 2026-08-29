"""Outcome-free overlap-cap and evil-twin selectors for R6 score matrices.

The four challengers in this module operate on the same sorted candidate rows
and four-fit-block score matrix accepted by the current-bank selector
successor.  They extend the frozen ``tail-ladder-200-210-220-v1`` objective in
only two ways:

* three greedy orders admit a candidate only when it shares at most
  ``gamma in {3, 4, 5}`` players with every previously selected roster; and
* one order alternates an ordinary tail-ladder anchor with the best remaining
  tail-ladder candidate whose strict-200 event vector is negatively correlated
  with that anchor.  If no such active candidate exists, it records an exact
  unconstrained fallback for that partner slot.

The overlap-cap variants never silently relax their cap.  A greedy order may
therefore end before 80, 100, or 150; only reached entry budgets are emitted as
books.  This is a greedy feasibility result, not a proof that no differently
ordered feasible subset exists.

Every emitted book carries training-bank effective-tail-shot diagnostics at
strict thresholds 200, 210, 220, and 230.  Held-out evaluation remains the
responsibility of the existing rotated-block evaluator.  Public functions do
no I/O and accept no realized outcomes, held-out columns, graph client, or
production mutation capability.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Final

import numpy as np

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as current_contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)


CONTRACT_SCHEMA: Final = "corpus-r6-selector-diversity-challengers-contract/v1"
RESULT_SCHEMA: Final = "corpus-r6-selector-diversity-challengers-result/v1"
SELECTOR_SCHEMA: Final = "corpus-r6-selector-diversity-challenger/v1"
BOOK_SCHEMA: Final = "corpus-r6-selector-diversity-book/v1"
TAIL_DIAGNOSTIC_SCHEMA: Final = "corpus-r6-effective-tail-shots-fit/v1"

BASE_STRATEGY_ID: Final = "tail-ladder-200-210-220-v1"
BASE_STRATEGY_SHA256: Final = (
    "5561d663cdc2ec8f928ddf5a44889f16e3c23cdd264f4c8fef7925547aa527ea"
)
TAIL_RUNGS: Final = (
    (200.0, ">", 1),
    (210.0, ">", 4),
    (220.0, ">", 12),
)
OVERLAP_CAPS: Final = (3, 4, 5)
ENTRY_BUDGETS: Final = (80, 100, 150)
RANKING_DEPTH: Final = ENTRY_BUDGETS[-1]
PAIR_THRESHOLD_DK: Final = 200.0
EFFECTIVE_SHOT_THRESHOLDS: Final = (200.0, 210.0, 220.0, 230.0)
PACKED_BITORDER: Final = "little"
CANDIDATE_CHUNK_ROWS: Final = 64
ROSTER_SIZE: Final = 9
MICRO_SCALE: Final = 1_000_000
NUMERICAL_EIGENVALUE_FLOOR: Final = -1e-12

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


class CorpusR6SelectorDiversityChallengersV1Error(ValueError):
    """The pure diversity challenger cannot be constructed or replayed."""


def _fail(message: str) -> None:
    raise CorpusR6SelectorDiversityChallengersV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return current_contract.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise CorpusR6SelectorDiversityChallengersV1Error(
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


def _micro(value: float, *, label: str) -> int:
    retained = np.float64(value)
    scaled = np.rint(retained * np.float64(MICRO_SCALE))
    limits = np.iinfo(np.int64)
    if not np.isfinite(scaled) or scaled < limits.min or scaled > limits.max:
        _fail(f"{label} is not one finite int64 micro-unit value")
    return int(np.int64(scaled))


def diversity_challenger_contract_v1() -> dict[str, object]:
    """Return the bounded score-free four-selector contract."""
    strategies = current_contract.frozen_strategies_v1()
    base = [row for row in strategies if row["strategy_id"] == BASE_STRATEGY_ID]
    if (
        len(base) != 1
        or base[0]["strategy_sha256"] != BASE_STRATEGY_SHA256
        or base[0]["method"] != "greedy-tail-ladder-v1"
        or base[0]["parameters"]["rungs"]
        != [
            {"operator": operator, "threshold": threshold, "weight": weight}
            for threshold, operator, weight in TAIL_RUNGS
        ]
    ):
        _fail("frozen tail-ladder base strategy drifted")
    body: dict[str, object] = {
        "schema_version": CONTRACT_SCHEMA,
        "base_strategy_id": BASE_STRATEGY_ID,
        "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "base_method": "greedy-tail-ladder-v1",
        "tail_rungs": [
            {"threshold": threshold, "operator": operator, "weight": weight}
            for threshold, operator, weight in TAIL_RUNGS
        ],
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "overlap_cap_variants": list(OVERLAP_CAPS),
        "overlap_cap_law": (
            "candidate-roster-intersection-with-every-selected-roster-le-gamma"
        ),
        "overlap_cap_failure_law": (
            "stop-with-partial-greedy-prefix-never-relax-and-emit-only-reached-books"
        ),
        "overlap_cap_optimality_claimed": False,
        "evil_twin_law": {
            "pair_event": {"threshold": PAIR_THRESHOLD_DK, "operator": ">"},
            "anchor": "ordinary-frozen-tail-ladder-greedy-pick",
            "partner_eligibility": (
                "active-binary-tail-vector-with-exact-negative-pearson-sign-"
                "against-immediately-preceding-anchor"
            ),
            "partner_objective": (
                "largest-frozen-tail-ladder-marginal-utility-within-negative-set"
            ),
            "partner_ties": [
                "most-negative-tail-correlation",
                "largest-individual-strict-gt-200-count",
                "largest-fit-mean-score",
                "ascending-lineup-id",
            ],
            "fallback": (
                "ordinary-frozen-tail-ladder-pick-when-negative-set-empty"
            ),
        },
        "effective_tail_shot_thresholds": list(EFFECTIVE_SHOT_THRESHOLDS),
        "effective_tail_shot_law": (
            "active-row-tail-event-correlation-participation-and-entropy-rank"
        ),
        "input_law": {
            "candidate_count": [RANKING_DEPTH, successor.MAX_CANDIDATES],
            "candidate_order": "ascending-lineup-id",
            "candidate_rosters": "exactly-nine-unique-players-and-unique-rosters",
            "training_block_count": successor.FIT_BLOCK_COUNT,
            "score_matrix_dtype": "native-little-endian-float64",
            "heldout_columns_present": False,
            "production_authority_validated": False,
        },
        "policy": dict(_FALSE_POLICY),
    }
    return _with_hash(body, field="contract_sha256")


def _pack_strict_masks(scores: np.ndarray) -> tuple[np.ndarray, ...]:
    masks: list[np.ndarray] = []
    for threshold, operator, _weight in TAIL_RUNGS:
        if operator != ">":
            _fail("only strict tail-rung masks are registered")
        masks.append(
            np.packbits(
                scores > threshold, axis=1, bitorder=PACKED_BITORDER
            )
        )
    return tuple(masks)


def _row_counts(packed: np.ndarray) -> np.ndarray:
    return _POPCOUNT[packed].sum(axis=1, dtype=np.int64)


def _fresh_utilities(
    *, masks: Sequence[np.ndarray], covered: Sequence[np.ndarray]
) -> np.ndarray:
    if len(masks) != len(TAIL_RUNGS) or len(covered) != len(TAIL_RUNGS):
        _fail("tail-ladder mask count differs")
    utilities = np.zeros(masks[0].shape[0], dtype=np.int64)
    for (_threshold, _operator, weight), mask, seen in zip(
        TAIL_RUNGS, masks, covered, strict=True
    ):
        for start in range(0, mask.shape[0], CANDIDATE_CHUNK_ROWS):
            stop = min(start + CANDIDATE_CHUNK_ROWS, mask.shape[0])
            fresh = np.bitwise_and(mask[start:stop], np.bitwise_not(seen))
            utilities[start:stop] += weight * _POPCOUNT[fresh].sum(
                axis=1, dtype=np.int64
            )
    return utilities


def _best_ladder_candidate(
    *,
    eligible: np.ndarray,
    utilities: np.ndarray,
    primary_counts: np.ndarray,
    means: np.ndarray,
    lineup_ids: Sequence[str],
    correlation_by_index: Mapping[int, float] | None = None,
) -> int | None:
    candidates = np.flatnonzero(eligible).tolist()
    if not candidates:
        return None
    correlations = correlation_by_index or {}
    return min(
        candidates,
        key=lambda index: (
            -int(utilities[index]),
            float(correlations.get(index, 0.0)),
            -int(primary_counts[index]),
            -float(means[index]),
            lineup_ids[index],
        ),
    )


def _roster_overlap_matrix(
    candidates: Sequence[Mapping[str, object]],
) -> np.ndarray:
    rosters = [set(row["roster_player_ids"]) for row in candidates]
    overlaps = np.empty((len(rosters), len(rosters)), dtype=np.uint8)
    for left, roster in enumerate(rosters):
        overlaps[left, left] = ROSTER_SIZE
        for right in range(left + 1, len(rosters)):
            count = len(roster & rosters[right])
            overlaps[left, right] = count
            overlaps[right, left] = count
    return overlaps


def _append_selection(
    *,
    candidate: int,
    selected: list[int],
    remaining: np.ndarray,
    masks: Sequence[np.ndarray],
    covered: Sequence[np.ndarray],
) -> None:
    selected.append(candidate)
    remaining[candidate] = False
    for mask, seen in zip(masks, covered, strict=True):
        seen |= mask[candidate]


def _run_overlap_cap_order(
    *,
    gamma: int,
    lineup_ids: Sequence[str],
    masks: Sequence[np.ndarray],
    primary_counts: np.ndarray,
    means: np.ndarray,
    roster_overlaps: np.ndarray,
) -> tuple[list[int], list[dict[str, object]], dict[str, object]]:
    covered = [np.zeros(mask.shape[1], dtype=np.uint8) for mask in masks]
    remaining = np.ones(len(lineup_ids), dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < RANKING_DEPTH:
        eligible = remaining.copy()
        if selected:
            eligible &= np.all(roster_overlaps[:, selected] <= gamma, axis=1)
        utilities = _fresh_utilities(masks=masks, covered=covered)
        best = _best_ladder_candidate(
            eligible=eligible,
            utilities=utilities,
            primary_counts=primary_counts,
            means=means,
            lineup_ids=lineup_ids,
        )
        if best is None:
            break
        max_prior_overlap = (
            0
            if not selected
            else int(roster_overlaps[best, selected].max())
        )
        trace.append({
            "selection_rank": len(selected),
            "canonical_lineup_index": best,
            "lineup_id": lineup_ids[best],
            "marginal_weighted_tail_ladder_utility": int(utilities[best]),
            "individual_strict_gt_200_world_count": int(primary_counts[best]),
            "fit_world_mean_score_micro": _micro(
                float(means[best]), label="fit world mean score"
            ),
            "maximum_overlap_with_prior_roster": max_prior_overlap,
            "overlap_cap": gamma,
        })
        _append_selection(
            candidate=best,
            selected=selected,
            remaining=remaining,
            masks=masks,
            covered=covered,
        )
    feasible_at_stop = remaining.copy()
    if selected:
        feasible_at_stop &= np.all(
            roster_overlaps[:, selected] <= gamma, axis=1
        )
    summary = {
        "overlap_cap": gamma,
        "greedy_prefix_count": len(selected),
        "ranking_depth_reached": len(selected) == RANKING_DEPTH,
        "unselected_feasible_candidate_count_at_stop": int(
            np.count_nonzero(feasible_at_stop)
        ),
        "global_maximum_feasible_cardinality_claimed": False,
        "cap_relaxed": False,
    }
    return selected, trace, summary


def _negative_partner_correlations(
    *,
    anchor: int,
    remaining: np.ndarray,
    pair_mask: np.ndarray,
    pair_counts: np.ndarray,
    world_count: int,
) -> dict[int, float]:
    anchor_count = int(pair_counts[anchor])
    if not 0 < anchor_count < world_count:
        return {}
    both = _POPCOUNT[np.bitwise_and(pair_mask, pair_mask[anchor])].sum(
        axis=1, dtype=np.int64
    )
    numerator = (
        np.int64(world_count) * both
        - np.int64(anchor_count) * pair_counts
    )
    eligible = (
        remaining
        & (pair_counts > 0)
        & (pair_counts < world_count)
        & (numerator < 0)
    )
    result: dict[int, float] = {}
    for index in np.flatnonzero(eligible).tolist():
        count = int(pair_counts[index])
        denominator = np.sqrt(
            float(anchor_count)
            * float(world_count - anchor_count)
            * float(count)
            * float(world_count - count)
        )
        correlation = float(numerator[index]) / denominator
        if not np.isfinite(correlation) or correlation >= 0.0:
            _fail("negative partner correlation arithmetic differs")
        result[index] = correlation
    return result


def _run_evil_twin_order(
    *,
    lineup_ids: Sequence[str],
    masks: Sequence[np.ndarray],
    primary_counts: np.ndarray,
    means: np.ndarray,
    world_count: int,
) -> tuple[list[int], list[dict[str, object]], dict[str, object]]:
    covered = [np.zeros(mask.shape[1], dtype=np.uint8) for mask in masks]
    remaining = np.ones(len(lineup_ids), dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    negative_partner_count = 0
    fallback_partner_count = 0
    active_anchor_count = 0
    while len(selected) < RANKING_DEPTH:
        utilities = _fresh_utilities(masks=masks, covered=covered)
        anchor = _best_ladder_candidate(
            eligible=remaining,
            utilities=utilities,
            primary_counts=primary_counts,
            means=means,
            lineup_ids=lineup_ids,
        )
        if anchor is None:
            break
        trace.append({
            "selection_rank": len(selected),
            "canonical_lineup_index": anchor,
            "lineup_id": lineup_ids[anchor],
            "selection_role": "tail-ladder-anchor",
            "paired_anchor_lineup_id": None,
            "anchor_tail_correlation_micro": None,
            "marginal_weighted_tail_ladder_utility": int(utilities[anchor]),
            "individual_strict_gt_200_world_count": int(primary_counts[anchor]),
            "fit_world_mean_score_micro": _micro(
                float(means[anchor]), label="fit world mean score"
            ),
        })
        _append_selection(
            candidate=anchor,
            selected=selected,
            remaining=remaining,
            masks=masks,
            covered=covered,
        )
        if len(selected) == RANKING_DEPTH:
            break

        if 0 < int(primary_counts[anchor]) < world_count:
            active_anchor_count += 1
        utilities = _fresh_utilities(masks=masks, covered=covered)
        negative = _negative_partner_correlations(
            anchor=anchor,
            remaining=remaining,
            pair_mask=masks[0],
            pair_counts=primary_counts,
            world_count=world_count,
        )
        if negative:
            partner_eligible = np.zeros(len(lineup_ids), dtype=bool)
            partner_eligible[list(negative)] = True
            role = "negative-tail-evil-twin"
            negative_partner_count += 1
        else:
            partner_eligible = remaining
            role = "tail-ladder-fallback-no-negative-twin"
            fallback_partner_count += 1
        partner = _best_ladder_candidate(
            eligible=partner_eligible,
            utilities=utilities,
            primary_counts=primary_counts,
            means=means,
            lineup_ids=lineup_ids,
            correlation_by_index=negative,
        )
        if partner is None:
            _fail("evil-twin order ended without one required partner")
        trace.append({
            "selection_rank": len(selected),
            "canonical_lineup_index": partner,
            "lineup_id": lineup_ids[partner],
            "selection_role": role,
            "paired_anchor_lineup_id": lineup_ids[anchor],
            "anchor_tail_correlation_micro": (
                None
                if partner not in negative
                else _micro(
                    negative[partner], label="anchor tail correlation"
                )
            ),
            "marginal_weighted_tail_ladder_utility": int(utilities[partner]),
            "individual_strict_gt_200_world_count": int(primary_counts[partner]),
            "fit_world_mean_score_micro": _micro(
                float(means[partner]), label="fit world mean score"
            ),
        })
        _append_selection(
            candidate=partner,
            selected=selected,
            remaining=remaining,
            masks=masks,
            covered=covered,
        )
    summary = {
        "pair_count": len(selected) // 2,
        "active_anchor_count": active_anchor_count,
        "negative_tail_partner_count": negative_partner_count,
        "fallback_partner_count": fallback_partner_count,
        "negative_partner_rate_micro": _micro(
            negative_partner_count / max(1, len(selected) // 2),
            label="negative partner rate",
        ),
        "ranking_depth_reached": len(selected) == RANKING_DEPTH,
    }
    return selected, trace, summary


def _effective_tail_shots(
    selected_scores: np.ndarray, *, threshold: float
) -> dict[str, object]:
    if (
        selected_scores.dtype != np.dtype(np.float64)
        or selected_scores.ndim != 2
        or selected_scores.shape[0] < 1
        or selected_scores.shape[1] < 2
        or not np.isfinite(selected_scores).all()
    ):
        _fail("effective-tail-shot matrix differs")
    events = selected_scores > threshold
    counts = np.count_nonzero(events, axis=1)
    zero_count = int(np.count_nonzero(counts == 0))
    all_count = int(np.count_nonzero(counts == selected_scores.shape[1]))
    active = np.asarray(
        events[(counts > 0) & (counts < selected_scores.shape[1])],
        dtype=np.float64,
    )
    active_count = int(active.shape[0])
    pair_count = 0
    pair_mean: float | None = None
    pair_minimum: float | None = None
    pair_maximum: float | None = None
    if active_count == 0:
        participation = 0.0
        entropy_rank = 0.0
    elif active_count == 1:
        participation = 1.0
        entropy_rank = 1.0
    else:
        centered = active - active.mean(axis=1, keepdims=True, dtype=np.float64)
        norms = np.sqrt(np.sum(centered * centered, axis=1, dtype=np.float64))
        if not np.isfinite(norms).all() or np.any(norms <= 0.0):
            _fail("active tail rows have invalid variance")
        correlations = (centered @ centered.T) / np.outer(norms, norms)
        correlations = (correlations + correlations.T) / 2.0
        np.fill_diagonal(correlations, 1.0)
        triangle = correlations[np.triu_indices(active_count, k=1)]
        pair_count = int(triangle.size)
        pair_mean = float(triangle.mean(dtype=np.float64))
        pair_minimum = float(triangle.min())
        pair_maximum = float(triangle.max())
        eigenvalues = np.linalg.eigvalsh(correlations)
        if float(eigenvalues.min()) < NUMERICAL_EIGENVALUE_FLOOR:
            _fail("tail-event correlation matrix is not positive semidefinite")
        clipped = np.maximum(eigenvalues, 0.0)
        eigen_sum = float(clipped.sum(dtype=np.float64))
        squared_sum = float((clipped * clipped).sum(dtype=np.float64))
        if eigen_sum <= 0.0 or squared_sum <= 0.0:
            _fail("tail-event eigenvalue mass differs")
        participation = eigen_sum * eigen_sum / squared_sum
        probabilities = clipped / eigen_sum
        positive = probabilities[probabilities > 0.0]
        entropy_rank = float(
            np.exp(-(positive * np.log(positive)).sum(dtype=np.float64))
        )
    book_events = np.any(events, axis=0)
    body: dict[str, object] = {
        "schema_version": TAIL_DIAGNOSTIC_SCHEMA,
        "threshold": threshold,
        "operator": ">",
        "selected_lineup_count": int(selected_scores.shape[0]),
        "fit_world_count": int(selected_scores.shape[1]),
        "book_tail_union_event_count": int(np.count_nonzero(book_events)),
        "book_tail_union_probability_micro": _micro(
            float(book_events.mean(dtype=np.float64)),
            label="book tail union probability",
        ),
        "selected_lineup_tail_event_count_sum": int(counts.sum(dtype=np.int64)),
        "active_tail_lineup_count": active_count,
        "zero_event_lineup_count": zero_count,
        "all_event_lineup_count": all_count,
        "active_pair_count": pair_count,
        "pairwise_active_correlation_mean_micro": (
            None if pair_mean is None else _micro(pair_mean, label="pair mean")
        ),
        "pairwise_active_correlation_minimum_micro": (
            None
            if pair_minimum is None
            else _micro(pair_minimum, label="pair minimum")
        ),
        "pairwise_active_correlation_maximum_micro": (
            None
            if pair_maximum is None
            else _micro(pair_maximum, label="pair maximum")
        ),
        "participation_ratio_micro": _micro(
            participation, label="participation ratio"
        ),
        "entropy_effective_rank_micro": _micro(
            entropy_rank, label="entropy effective rank"
        ),
        "participation_ratio_per_entry_micro": _micro(
            participation / selected_scores.shape[0],
            label="participation ratio per entry",
        ),
        "uses_realized_outcomes": False,
    }
    return _with_hash(body, field="diagnostics_sha256")


def _roster_overlap_diagnostics(
    *, selected: Sequence[int], roster_overlaps: np.ndarray
) -> dict[str, object]:
    indices = np.asarray(selected, dtype=np.int64)
    matrix = roster_overlaps[np.ix_(indices, indices)]
    triangle = matrix[np.triu_indices(len(indices), k=1)]
    histogram = np.bincount(triangle, minlength=ROSTER_SIZE + 1)
    return {
        "unordered_pair_count": int(triangle.size),
        "mean_shared_player_count_micro": _micro(
            float(triangle.mean(dtype=np.float64)) if triangle.size else 0.0,
            label="mean shared player count",
        ),
        "maximum_shared_player_count": (
            int(triangle.max()) if triangle.size else 0
        ),
        "shared_player_count_histogram": [
            int(value) for value in histogram.tolist()
        ],
    }


def _entry_books(
    *,
    selected: Sequence[int],
    lineup_ids: Sequence[str],
    candidates: Sequence[Mapping[str, object]],
    scores: np.ndarray,
    roster_overlaps: np.ndarray,
) -> list[dict[str, object]]:
    books: list[dict[str, object]] = []
    for budget in ENTRY_BUDGETS:
        if len(selected) < budget:
            continue
        indices = list(selected[:budget])
        ids = [lineup_ids[index] for index in indices]
        rosters = [list(candidates[index]["roster_player_ids"]) for index in indices]
        selected_scores = np.ascontiguousarray(
            scores[np.asarray(indices, dtype=np.int64)], dtype=np.float64
        )
        tail_diagnostics = [
            _effective_tail_shots(selected_scores, threshold=threshold)
            for threshold in EFFECTIVE_SHOT_THRESHOLDS
        ]
        score_maximum = selected_scores.max(axis=0)
        body: dict[str, object] = {
            "schema_version": BOOK_SCHEMA,
            "entry_budget": budget,
            "selected_lineup_ids": ids,
            "selected_lineup_ids_sha256": _sha(ids),
            "selected_rosters_sha256": _sha(rosters),
            "fit_book_maximum_mean_micro": _micro(
                float(score_maximum.mean(dtype=np.float64)),
                label="fit book maximum mean",
            ),
            "roster_overlap_diagnostics": _roster_overlap_diagnostics(
                selected=indices, roster_overlaps=roster_overlaps
            ),
            "effective_tail_shots": tail_diagnostics,
            "effective_tail_shots_sha256": _sha(tail_diagnostics),
            "heldout_evaluation_performed": False,
            "uses_realized_outcomes": False,
        }
        books.append(_with_hash(body, field="book_sha256"))
    return books


def _selector_result(
    *,
    ordinal: int,
    strategy_id: str,
    kind: str,
    selected: Sequence[int],
    trace: Sequence[Mapping[str, object]],
    summary: Mapping[str, object],
    lineup_ids: Sequence[str],
    candidates: Sequence[Mapping[str, object]],
    scores: np.ndarray,
    roster_overlaps: np.ndarray,
) -> dict[str, object]:
    selected_ids = [lineup_ids[index] for index in selected]
    books = _entry_books(
        selected=selected,
        lineup_ids=lineup_ids,
        candidates=candidates,
        scores=scores,
        roster_overlaps=roster_overlaps,
    )
    available = [int(book["entry_budget"]) for book in books]
    if len(selected) >= RANKING_DEPTH:
        status = "exact-rank-150"
    elif len(selected) >= ENTRY_BUDGETS[1]:
        status = "partial-after-exact-100"
    elif len(selected) >= ENTRY_BUDGETS[0]:
        status = "partial-after-exact-80"
    else:
        status = "infeasible-before-exact-80"
    body: dict[str, object] = {
        "schema_version": SELECTOR_SCHEMA,
        "ordinal": ordinal,
        "strategy_id": strategy_id,
        "selector_kind": kind,
        "base_strategy_id": BASE_STRATEGY_ID,
        "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "status": status,
        "greedy_prefix_count": len(selected),
        "ranked_canonical_indices": [int(index) for index in selected],
        "ranked_lineup_ids": selected_ids,
        "ranked_lineup_ids_sha256": _sha(selected_ids),
        "selection_trace_sha256": _sha(list(trace)),
        "selector_summary": dict(summary),
        "entry_budgets_available": available,
        "entry_books": books,
        "entry_book_sha256s": [book["book_sha256"] for book in books],
        "exact_prefix_consistency_verified": all(
            book["selected_lineup_ids"] == selected_ids[: book["entry_budget"]]
            for book in books
        ),
        "policy": dict(_FALSE_POLICY),
    }
    return _with_hash(body, field="selector_result_sha256")


def run_diversity_challengers_v1(
    *,
    sampled_lineup_ids: object,
    training_score_matrix: object,
    candidate_rows: object,
    training_blocks: object,
    worlds_per_block: object,
    source_arm_registry: object | None = None,
) -> dict[str, object]:
    """Run all three gamma caps and the evil-twin order without external I/O."""
    contract = diversity_challenger_contract_v1()
    try:
        (
            lineup_ids,
            scores,
            candidates,
            blocks,
            heldout_block,
            retained_worlds_per_block,
        ) = successor._validated_inputs(
            sampled_lineup_ids=sampled_lineup_ids,
            training_score_matrix=training_score_matrix,
            candidate_rows=candidate_rows,
            training_blocks=training_blocks,
            worlds_per_block=worlds_per_block,
            source_arm_registry=source_arm_registry,
        )
    except successor.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
        raise CorpusR6SelectorDiversityChallengersV1Error(str(exc)) from exc
    if len(lineup_ids) < RANKING_DEPTH:
        _fail("diversity challengers require at least 150 sampled candidates")
    roster_keys = [
        tuple(str(value) for value in row["roster_player_ids"])
        for row in candidates
    ]
    if len(set(roster_keys)) != len(roster_keys):
        _fail("diversity challengers require unique candidate rosters")

    masks = _pack_strict_masks(scores)
    primary_counts = _row_counts(masks[0])
    means = scores.mean(axis=1, dtype=np.float64)
    roster_overlaps = _roster_overlap_matrix(candidates)
    selectors: list[dict[str, object]] = []
    for ordinal, gamma in enumerate(OVERLAP_CAPS):
        selected, trace, summary = _run_overlap_cap_order(
            gamma=gamma,
            lineup_ids=lineup_ids,
            masks=masks,
            primary_counts=primary_counts,
            means=means,
            roster_overlaps=roster_overlaps,
        )
        selectors.append(_selector_result(
            ordinal=ordinal,
            strategy_id=f"tail-ladder-roster-overlap-cap-{gamma}-v1",
            kind="hard-roster-overlap-cap",
            selected=selected,
            trace=trace,
            summary=summary,
            lineup_ids=lineup_ids,
            candidates=candidates,
            scores=scores,
            roster_overlaps=roster_overlaps,
        ))

    selected, trace, summary = _run_evil_twin_order(
        lineup_ids=lineup_ids,
        masks=masks,
        primary_counts=primary_counts,
        means=means,
        world_count=scores.shape[1],
    )
    selectors.append(_selector_result(
        ordinal=len(selectors),
        strategy_id="tail-ladder-evil-twin-strict-200-v1",
        kind="negative-tail-event-pairing",
        selected=selected,
        trace=trace,
        summary=summary,
        lineup_ids=lineup_ids,
        candidates=candidates,
        scores=scores,
        roster_overlaps=roster_overlaps,
    ))

    input_binding = _with_hash({
        "ordered_sampled_lineup_ids_sha256": _sha(lineup_ids),
        "sampled_candidate_rows_sha256": _sha(candidates),
        "candidate_count": len(lineup_ids),
        "training_blocks": list(blocks),
        "heldout_block_label_only": heldout_block,
        "worlds_per_block": retained_worlds_per_block,
        "training_score_shape": list(scores.shape),
        "training_score_matrix_sha256": successor._matrix_sha(scores),
        "heldout_score_columns_present": False,
        "uses_realized_outcomes": False,
        "production_authority_validated": False,
    }, field="input_binding_sha256")
    body: dict[str, object] = {
        "schema_version": RESULT_SCHEMA,
        "contract": contract,
        "contract_sha256": contract["contract_sha256"],
        "input_binding": input_binding,
        "input_binding_sha256": input_binding["input_binding_sha256"],
        "selector_count": len(selectors),
        "selectors": selectors,
        "selector_result_sha256s": [
            selector["selector_result_sha256"] for selector in selectors
        ],
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "heldout_evaluation_performed": False,
        "policy": dict(_FALSE_POLICY),
    }
    return _with_hash(body, field="result_sha256")


def validate_diversity_challengers_v1(
    value: object,
    *,
    sampled_lineup_ids: object,
    training_score_matrix: object,
    candidate_rows: object,
    training_blocks: object,
    worlds_per_block: object,
    source_arm_registry: object | None = None,
) -> dict[str, object]:
    """Pure-replay the complete result and reject any canonical-byte drift."""
    if not isinstance(value, Mapping):
        _fail("diversity challenger result must be one mapping")
    retained = dict(value)
    _canonical(retained)
    expected = run_diversity_challengers_v1(
        sampled_lineup_ids=sampled_lineup_ids,
        training_score_matrix=training_score_matrix,
        candidate_rows=candidate_rows,
        training_blocks=training_blocks,
        worlds_per_block=worlds_per_block,
        source_arm_registry=source_arm_registry,
    )
    if _canonical(retained) != _canonical(expected):
        _fail("diversity challenger result differs from exact pure replay")
    return expected


__all__ = [
    "BASE_STRATEGY_ID",
    "BASE_STRATEGY_SHA256",
    "CorpusR6SelectorDiversityChallengersV1Error",
    "EFFECTIVE_SHOT_THRESHOLDS",
    "ENTRY_BUDGETS",
    "OVERLAP_CAPS",
    "PAIR_THRESHOLD_DK",
    "RANKING_DEPTH",
    "RESULT_SCHEMA",
    "diversity_challenger_contract_v1",
    "run_diversity_challengers_v1",
    "validate_diversity_challengers_v1",
]
