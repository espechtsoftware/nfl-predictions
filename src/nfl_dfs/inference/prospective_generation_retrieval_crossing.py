"""Outcome-blind generation x retrieval crossing for the 2026 shadows.

The primary generation experiment already pays for and freezes two candidate
populations: the incumbent 160-leverage/40-boom population and the matched
40-leverage/160-boom population.  This module reuses those exact populations
and their common 50,000-world CBWU selection bank to freeze a 2 x 2:

* each population under the incumbent coverage-194 K80 retrieval; and
* each population under the production cap-4-prefix-then-fill K80 retrieval.

The cap selector is the production law, not the lab analog: strict
``>200/>210/>220`` world masks with weights ``1/4/12``; ties use strict-200
count, simulated mean, then canonical lineup ID.  The pairwise roster-overlap
cap is enforced without relaxation until the greedy feasible set is empty;
the remainder is filled by the same unconstrained ladder.  No candidate solve
is requested here and no realized score or post-lock field is accepted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import perf_counter
from typing import Final

import numpy as np

from ..backtest.engine import CandidateBatch, _validate_candidate_batch
from ..optimizer.lineup import Lineup, select_tail_entries
from .generation_exposure import canonical_sha256
from .prospective_boom_first import _array_receipt
from .prospective_shadow import _canonical_dk_roster


SCHEMA_VERSION: Final = "prospective-generation-retrieval-crossing/v1"
POPULATION_ORDER: Final = (
    "incumbent-160-40",
    "boom-first-40-160",
)
RETRIEVAL_ORDER: Final = (
    "incumbent-cbwu-coverage-194-k80",
    "cap4-production-ladder-prefix-then-fill-k80",
)
INCUMBENT_RETRIEVAL_ID: Final = RETRIEVAL_ORDER[0]
CAP4_RETRIEVAL_ID: Final = RETRIEVAL_ORDER[1]
UNCAPPED_LADDER_DIAGNOSTIC_ID: Final = (
    "production-ladder-uncapped-k80-score-free-diagnostic"
)
ENTRIES: Final = 80
INCUMBENT_LINE: Final = 194.0
OVERLAP_CAP: Final = 4
SELECTION_RUNGS: Final = (
    (200.0, 1),
    (210.0, 4),
    (220.0, 12),
)
REPORT_THRESHOLDS: Final = (194, 200, 210, 220, 230, 240)
PREFIXES: Final = (20, 40, 80)
WORLD_COUNT: Final = 50_000
AUDIT_WORLD_COUNT: Final = 10_000
_CHUNK_ROWS: Final = 64
_POPCOUNT: Final = np.asarray(
    [value.bit_count() for value in range(256)], dtype=np.uint8
)


class ProspectiveGenerationRetrievalCrossingError(ValueError):
    """The score-free generation x retrieval crossing differed."""


def _fail(message: str) -> None:
    raise ProspectiveGenerationRetrievalCrossingError(message)


def _without_runtime(value: object) -> object:
    """Return the science payload with all wall-clock observations removed."""

    if isinstance(value, Mapping):
        return {
            str(key): _without_runtime(item)
            for key, item in value.items()
            if key != "selector_runtime_seconds"
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_without_runtime(item) for item in value]
    return value


def _lineup_id(roster: Sequence[str]) -> str:
    """Match the production bridge's content-only canonical lineup ID law."""

    retained = list(roster)
    if len(retained) != 9 or len(set(retained)) != 9 or retained != sorted(
        retained
    ):
        _fail("retrieval lineup identity requires nine sorted DK player IDs")
    return f"lineup-v1-{canonical_sha256(retained)}"


def _candidate_identity(
    batch: CandidateBatch,
    dk_id_by_player_id: Mapping[object, str | int],
) -> tuple[list[list[str]], list[str], list[frozenset[str]]]:
    rosters = [
        _canonical_dk_roster(lineup, dict(dk_id_by_player_id))
        for lineup in batch.candidates
    ]
    lineup_ids = [_lineup_id(roster) for roster in rosters]
    if len(set(lineup_ids)) != len(lineup_ids):
        _fail("retrieval candidate population repeats a canonical roster")
    return rosters, lineup_ids, [frozenset(roster) for roster in rosters]


def _validate_base_scoring(batch: CandidateBatch) -> None:
    """Prove every candidate score row is from the persisted player bank."""

    totals = np.asarray(batch.candidate_totals)
    rows = np.asarray(batch.row_draws)
    if totals.dtype != np.dtype(np.float32) or rows.dtype != np.dtype(
        np.float32
    ):
        _fail("retrieval crossing requires native float32 CBWU worlds")
    if totals.shape[1] != WORLD_COUNT or rows.shape[1] != WORLD_COUNT:
        _fail("retrieval crossing requires the exact 50,000-world bank")
    if not np.isfinite(totals).all() or not np.isfinite(rows).all():
        _fail("retrieval crossing requires finite CBWU worlds")
    row_by_id = {
        player_id: index for index, player_id in enumerate(batch.player_ids)
    }
    for ordinal, lineup in enumerate(batch.candidates):
        try:
            player_rows = [row_by_id[player_id] for player_id in lineup.ids]
        except KeyError as exc:
            raise ProspectiveGenerationRetrievalCrossingError(
                "retrieval roster escapes the common player-world bank"
            ) from exc
        recomputed = rows[player_rows].sum(axis=0).astype(np.float32)
        if not np.array_equal(recomputed, totals[ordinal]):
            _fail("retrieval candidate score row differs from common bank")


def _packed_masks(scores: np.ndarray) -> tuple[np.ndarray, ...]:
    return tuple(
        np.packbits(scores > threshold, axis=1, bitorder="little")
        for threshold, _weight in SELECTION_RUNGS
    )


def _row_counts(mask: np.ndarray) -> np.ndarray:
    return _POPCOUNT[mask].sum(axis=1, dtype=np.int64)


def _fresh_utilities(
    masks: Sequence[np.ndarray], covered: Sequence[np.ndarray]
) -> np.ndarray:
    if len(masks) != len(SELECTION_RUNGS) or len(covered) != len(
        SELECTION_RUNGS
    ):
        _fail("production ladder rung count differs")
    utilities = np.zeros(masks[0].shape[0], dtype=np.int64)
    for (_threshold, weight), mask, seen in zip(
        SELECTION_RUNGS, masks, covered, strict=True
    ):
        for start in range(0, mask.shape[0], _CHUNK_ROWS):
            stop = min(start + _CHUNK_ROWS, mask.shape[0])
            fresh = np.bitwise_and(mask[start:stop], np.bitwise_not(seen))
            utilities[start:stop] += weight * _POPCOUNT[fresh].sum(
                axis=1, dtype=np.int64
            )
    return utilities


def _best_candidate(
    *,
    eligible: np.ndarray,
    utilities: np.ndarray,
    primary_counts: np.ndarray,
    means: np.ndarray,
    lineup_ids: Sequence[str],
) -> int | None:
    indices = np.flatnonzero(eligible).tolist()
    if not indices:
        return None
    return min(
        indices,
        key=lambda index: (
            -int(utilities[index]),
            -int(primary_counts[index]),
            -float(means[index]),
            lineup_ids[index],
        ),
    )


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


def _maximum_overlap(
    selected: Sequence[int], rosters: Sequence[frozenset[str]]
) -> int:
    maximum = 0
    for left, left_index in enumerate(selected):
        for right_index in selected[left + 1 :]:
            maximum = max(
                maximum, len(rosters[left_index] & rosters[right_index])
            )
    return maximum


def _trace_row(
    *,
    rank: int,
    index: int,
    lineup_ids: Sequence[str],
    utilities: np.ndarray,
    primary_counts: np.ndarray,
    means: np.ndarray,
    selection_role: str,
    maximum_prior_overlap: int,
    cap_excluded_before_pick: int,
    unconstrained_best: int | None,
    cap_enforced: bool,
) -> dict[str, object]:
    return {
        "selection_rank": rank,
        "canonical_candidate_index": index,
        "lineup_id": lineup_ids[index],
        "selection_role": selection_role,
        "weighted_strict_tail_fresh_utility": int(utilities[index]),
        "individual_strict_gt_200_world_count": int(primary_counts[index]),
        "fit_world_mean_score_micro": int(
            np.rint(float(means[index]) * 1_000_000.0)
        ),
        "maximum_overlap_with_prior_roster": maximum_prior_overlap,
        "overlap_cap": OVERLAP_CAP,
        "overlap_cap_enforced": cap_enforced,
        "cap_excluded_candidate_count_before_pick": (
            cap_excluded_before_pick
        ),
        "cap_engaged_before_pick": cap_excluded_before_pick > 0,
        "unconstrained_best_on_same_path_lineup_id": (
            lineup_ids[unconstrained_best]
            if unconstrained_best is not None
            else None
        ),
        "choice_changed_by_cap_on_same_path": (
            cap_enforced
            and unconstrained_best is not None
            and index != unconstrained_best
        ),
    }


def _production_ladder_order(
    *,
    scores: np.ndarray,
    lineup_ids: Sequence[str],
    entry_budget: int,
) -> tuple[list[int], list[dict[str, object]]]:
    masks = _packed_masks(scores)
    primary_counts = _row_counts(masks[0])
    means = scores.mean(axis=1, dtype=np.float64)
    covered = [np.zeros(mask.shape[1], dtype=np.uint8) for mask in masks]
    remaining = np.ones(scores.shape[0], dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < entry_budget:
        utilities = _fresh_utilities(masks, covered)
        best = _best_candidate(
            eligible=remaining,
            utilities=utilities,
            primary_counts=primary_counts,
            means=means,
            lineup_ids=lineup_ids,
        )
        if best is None:
            _fail("unconstrained production ladder lacks exact K80")
        trace.append(
            _trace_row(
                rank=len(selected),
                index=best,
                lineup_ids=lineup_ids,
                utilities=utilities,
                primary_counts=primary_counts,
                means=means,
                selection_role="unconstrained-production-tail-ladder",
                maximum_prior_overlap=0,
                cap_excluded_before_pick=0,
                unconstrained_best=best,
                cap_enforced=False,
            )
        )
        _append_selection(
            candidate=best,
            selected=selected,
            remaining=remaining,
            masks=masks,
            covered=covered,
        )
    return selected, trace


def _cap4_prefix_then_fill(
    *,
    scores: np.ndarray,
    lineup_ids: Sequence[str],
    rosters: Sequence[frozenset[str]],
    entry_budget: int,
) -> tuple[list[int], dict[str, object], list[dict[str, object]]]:
    masks = _packed_masks(scores)
    primary_counts = _row_counts(masks[0])
    means = scores.mean(axis=1, dtype=np.float64)
    covered = [np.zeros(mask.shape[1], dtype=np.uint8) for mask in masks]
    remaining = np.ones(scores.shape[0], dtype=bool)
    cap_feasible = np.ones(scores.shape[0], dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    ever_excluded: set[int] = set()

    while len(selected) < entry_budget:
        eligible = remaining & cap_feasible
        utilities = _fresh_utilities(masks, covered)
        unconstrained = _best_candidate(
            eligible=remaining,
            utilities=utilities,
            primary_counts=primary_counts,
            means=means,
            lineup_ids=lineup_ids,
        )
        best = _best_candidate(
            eligible=eligible,
            utilities=utilities,
            primary_counts=primary_counts,
            means=means,
            lineup_ids=lineup_ids,
        )
        if best is None:
            break
        excluded_indices = np.flatnonzero(remaining & ~cap_feasible).tolist()
        ever_excluded.update(excluded_indices)
        max_prior = max(
            (len(rosters[best] & rosters[index]) for index in selected),
            default=0,
        )
        trace.append(
            _trace_row(
                rank=len(selected),
                index=best,
                lineup_ids=lineup_ids,
                utilities=utilities,
                primary_counts=primary_counts,
                means=means,
                selection_role="hard-cap-4-greedy-prefix",
                maximum_prior_overlap=max_prior,
                cap_excluded_before_pick=len(excluded_indices),
                unconstrained_best=unconstrained,
                cap_enforced=True,
            )
        )
        _append_selection(
            candidate=best,
            selected=selected,
            remaining=remaining,
            masks=masks,
            covered=covered,
        )
        for candidate in np.flatnonzero(remaining & cap_feasible).tolist():
            if len(rosters[candidate] & rosters[best]) > OVERLAP_CAP:
                cap_feasible[candidate] = False

    prefix_count = len(selected)
    prefix = list(selected)
    cap_excluded_at_stop = int(np.count_nonzero(remaining & ~cap_feasible))
    cap_feasible_at_stop = int(np.count_nonzero(remaining & cap_feasible))
    ever_excluded.update(np.flatnonzero(remaining & ~cap_feasible).tolist())
    while len(selected) < entry_budget:
        utilities = _fresh_utilities(masks, covered)
        best = _best_candidate(
            eligible=remaining,
            utilities=utilities,
            primary_counts=primary_counts,
            means=means,
            lineup_ids=lineup_ids,
        )
        if best is None:
            _fail("cap-4 unconstrained completion lacks exact K80")
        max_prior = max(
            (len(rosters[best] & rosters[index]) for index in selected),
            default=0,
        )
        trace.append(
            _trace_row(
                rank=len(selected),
                index=best,
                lineup_ids=lineup_ids,
                utilities=utilities,
                primary_counts=primary_counts,
                means=means,
                selection_role="unconstrained-production-ladder-completion",
                maximum_prior_overlap=max_prior,
                cap_excluded_before_pick=0,
                unconstrained_best=best,
                cap_enforced=False,
            )
        )
        _append_selection(
            candidate=best,
            selected=selected,
            remaining=remaining,
            masks=masks,
            covered=covered,
        )

    engagement_rows = [
        row for row in trace[:prefix_count] if row["cap_engaged_before_pick"]
    ]
    choice_change_rows = [
        row
        for row in trace[:prefix_count]
        if row["choice_changed_by_cap_on_same_path"]
    ]
    prefix_ids = [lineup_ids[index] for index in prefix]
    completion_ids = [lineup_ids[index] for index in selected[prefix_count:]]
    summary = {
        "overlap_cap": OVERLAP_CAP,
        "hard_cap_prefix_count": prefix_count,
        "hard_cap_prefix_reached_k80": prefix_count == entry_budget,
        "hard_cap_prefix_exhausted_before_k80": prefix_count < entry_budget,
        "hard_cap_prefix_lineup_ids": prefix_ids,
        "hard_cap_prefix_lineup_ids_sha256": canonical_sha256(prefix_ids),
        "hard_cap_prefix_maximum_pairwise_overlap": _maximum_overlap(
            prefix, rosters
        ),
        "cap_relaxed_within_hard_cap_prefix": False,
        "cap_engaged_rank_count": len(engagement_rows),
        "cap_engaged_ranks": [
            int(row["selection_rank"]) for row in engagement_rows
        ],
        "cap_changed_same_path_choice_rank_count": len(choice_change_rows),
        "cap_changed_same_path_choice_ranks": [
            int(row["selection_rank"]) for row in choice_change_rows
        ],
        "cap_excluded_candidate_instances_across_prefix": sum(
            int(row["cap_excluded_candidate_count_before_pick"])
            for row in trace[:prefix_count]
        ),
        "maximum_cap_excluded_candidate_count_before_one_pick": max(
            (
                int(row["cap_excluded_candidate_count_before_pick"])
                for row in trace[:prefix_count]
            ),
            default=0,
        ),
        "unique_candidates_excluded_by_cap_count": len(ever_excluded),
        "cap_excluded_candidate_count_at_prefix_stop": cap_excluded_at_stop,
        "unselected_cap_feasible_candidate_count_at_stop": int(
            cap_feasible_at_stop
        )
        if prefix_count < entry_budget
        else None,
        "global_maximum_feasible_cardinality_claimed": False,
        "completion_performed": prefix_count < entry_budget,
        "completion_count": entry_budget - prefix_count,
        "completion_lineup_ids": completion_ids,
        "completion_lineup_ids_sha256": canonical_sha256(completion_ids),
        "completion_overlap_cap_enforced": (
            False if prefix_count < entry_budget else None
        ),
        "completed_book_global_cap_compliance_claimed": False,
        "completed_book_maximum_pairwise_overlap": _maximum_overlap(
            selected, rosters
        ),
        "prefix_exhaustion_is_not_cap_engagement": True,
    }
    return selected, summary, trace


def _membership_comparison(
    left: Sequence[str], right: Sequence[str]
) -> dict[str, object]:
    left_set = set(left)
    right_set = set(right)
    if len(left_set) != len(left) or len(right_set) != len(right):
        _fail("retrieval comparison book repeats a lineup")
    union = left_set | right_set
    shared = left_set & right_set
    return {
        "shared_lineup_count": len(shared),
        "union_lineup_count": len(union),
        "jaccard": len(shared) / len(union),
        "membership_choices_changed_per_side": ENTRIES - len(shared),
        "ordered_position_change_count": sum(
            left_id != right_id
            for left_id, right_id in zip(left, right, strict=True)
        ),
        "identical_membership": left_set == right_set,
        "identical_order": list(left) == list(right),
        "prefix_shared_lineup_count": {
            str(prefix): len(set(left[:prefix]) & set(right[:prefix]))
            for prefix in PREFIXES
        },
    }


def _simulated_diagnostics(
    scores: np.ndarray, selected: Sequence[int]
) -> dict[str, object]:
    maxima = scores[np.asarray(selected, dtype=np.int64)].max(axis=0)
    return {
        "probabilities_are_in_sample_descriptive_not_calibrated": True,
        "simulated_mean_book_max": float(maxima.mean(dtype=np.float64)),
        "simulated_p_book_max_at_least": {
            str(threshold): float((maxima >= threshold).mean())
            for threshold in REPORT_THRESHOLDS
        },
    }


def _independent_audit_diagnostics(
    scores: np.ndarray, selected: Sequence[int]
) -> dict[str, object]:
    """Score a frozen order on the distinct score-only audit bank."""

    if scores.ndim != 2 or scores.shape[1] != AUDIT_WORLD_COUNT:
        _fail("independent audit candidate-score matrix differs")
    selected_rows = scores[np.asarray(selected, dtype=np.int64)]
    prefixes: dict[str, object] = {}
    for prefix in PREFIXES:
        maxima = selected_rows[:prefix].max(axis=0)
        prefixes[str(prefix)] = {
            "simulated_mean_max": float(maxima.mean(dtype=np.float64)),
            "simulated_p_max_at_least": {
                str(threshold): float((maxima >= threshold).mean())
                for threshold in REPORT_THRESHOLDS
            },
        }
    return {
        "probabilities_are_out_of_selection_sample_audit_estimates": True,
        "audit_world_count": AUDIT_WORLD_COUNT,
        "used_for_selection": False,
        "prefixes": prefixes,
    }


def _book_receipt(
    *,
    selector_id: str,
    selected: Sequence[int],
    lineup_ids: Sequence[str],
    rosters: Sequence[Sequence[str]],
    scores: np.ndarray,
    independent_audit_scores: np.ndarray,
    runtime_seconds: float,
    selection_trace: Sequence[Mapping[str, object]] | None = None,
    cap_engagement: Mapping[str, object] | None = None,
) -> dict[str, object]:
    ids = [lineup_ids[index] for index in selected]
    membership = [list(rosters[index]) for index in selected]
    prefixes = {
        str(prefix): {
            "lineup_ids": ids[:prefix],
            "lineup_ids_sha256": canonical_sha256(ids[:prefix]),
            "rosters": membership[:prefix],
            "rosters_sha256": canonical_sha256(membership[:prefix]),
        }
        for prefix in PREFIXES
    }
    body: dict[str, object] = {
        "selector_id": selector_id,
        "entry_budget": ENTRIES,
        "selected_candidate_indices": list(selected),
        "selected_lineup_ids": ids,
        "selected_lineup_ids_sha256": canonical_sha256(ids),
        "selected_membership_sha256": canonical_sha256(sorted(ids)),
        "selected_rosters": membership,
        "selected_rosters_sha256": canonical_sha256(membership),
        "prefixes": prefixes,
        "simulated_diagnostics": _simulated_diagnostics(scores, selected),
        "independent_audit_diagnostics": _independent_audit_diagnostics(
            independent_audit_scores, selected
        ),
        "selector_runtime_seconds": float(runtime_seconds),
        "selection_trace": (
            [dict(row) for row in selection_trace]
            if selection_trace is not None
            else None
        ),
        "selection_trace_sha256": (
            canonical_sha256([dict(row) for row in selection_trace])
            if selection_trace is not None
            else None
        ),
        "cap_engagement": dict(cap_engagement) if cap_engagement else None,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    body["science_sha256_excluding_runtime"] = canonical_sha256(
        _without_runtime(body)
    )
    return body


def build_generation_retrieval_crossing(
    populations: Mapping[str, CandidateBatch],
    incumbent_books: Mapping[str, Sequence[Lineup]],
    dk_id_by_player_id: Mapping[object, str | int],
    *,
    independent_audit_row_draws: np.ndarray,
) -> tuple[dict[str, list[Lineup]], dict[str, object]]:
    """Freeze the score-free 2 x 2 without requesting candidate work."""

    if set(populations) != set(POPULATION_ORDER) or set(
        incumbent_books
    ) != set(POPULATION_ORDER):
        _fail("generation x retrieval population grid differs")
    base = populations[POPULATION_ORDER[0]]
    _validate_candidate_batch(base)
    if len(base.candidates) < ENTRIES:
        _fail("retrieval crossing incumbent pool is below exact K80")
    if (
        base.metadata.get("portfolio") != "CBWU"
        or base.metadata.get("world_blocks") != 5
        or base.metadata.get("worlds_per_block") != [10_000] * 5
    ):
        _fail("retrieval crossing incumbent pool is not exact CBWU")
    shared_world_receipt = _array_receipt(base.row_draws)
    audit_draws = np.asarray(independent_audit_row_draws, dtype=np.float32)
    if (
        audit_draws.shape != (len(base.player_ids), AUDIT_WORLD_COUNT)
        or not np.isfinite(audit_draws).all()
        or any(
            np.array_equal(
                audit_draws,
                np.asarray(base.row_draws)[
                    :, block * AUDIT_WORLD_COUNT:(block + 1) * AUDIT_WORLD_COUNT
                ],
            )
            for block in range(5)
        )
    ):
        _fail("retrieval crossing independent audit bank differs or is reused")
    audit_world_receipt = _array_receipt(audit_draws)
    shared_player_ids = [str(value) for value in base.player_ids]
    if len(set(shared_player_ids)) != len(shared_player_ids):
        _fail("retrieval common player identities collide after normalization")
    try:
        shared_dk_player_ids = [
            str(dk_id_by_player_id[player_id]) for player_id in base.player_ids
        ]
    except KeyError as exc:
        raise ProspectiveGenerationRetrievalCrossingError(
            "retrieval common player bank lacks a DK identity"
        ) from exc
    if len(set(shared_dk_player_ids)) != len(shared_dk_player_ids):
        _fail("retrieval common player bank repeats a DK identity")

    cap_books: dict[str, list[Lineup]] = {}
    population_receipts: dict[str, object] = {}
    selector_runtime_total = 0.0
    for population_id in POPULATION_ORDER:
        batch = populations[population_id]
        _validate_candidate_batch(batch)
        if len(batch.candidates) < ENTRIES:
            _fail(f"{population_id} pool is below exact K80")
        if (
            batch.metadata.get("portfolio") != "CBWU"
            or batch.metadata.get("world_blocks") != 5
            or batch.metadata.get("worlds_per_block") != [10_000] * 5
            or batch.player_ids != base.player_ids
            or not np.array_equal(batch.row_draws, base.row_draws)
            or _array_receipt(batch.row_draws) != shared_world_receipt
        ):
            _fail(f"{population_id} does not use the common selection bank")
        _validate_base_scoring(batch)
        rosters, lineup_ids, roster_sets = _candidate_identity(
            batch, dk_id_by_player_id
        )
        scores = np.asarray(batch.candidate_totals, dtype=np.float32)
        row_by_player = {
            player_id: ordinal for ordinal, player_id in enumerate(batch.player_ids)
        }
        audit_scores = np.stack([
            audit_draws[[row_by_player[player_id] for player_id in lineup.ids]].sum(
                axis=0, dtype=np.float32
            )
            for lineup in batch.candidates
        ]).astype(np.float32, copy=False)

        incumbent_started = perf_counter()
        incumbent_indices = select_tail_entries(
            scores, ENTRIES, INCUMBENT_LINE, env={}
        )
        incumbent_runtime = perf_counter() - incumbent_started
        expected_incumbent = [
            batch.candidates[index] for index in incumbent_indices
        ]
        supplied_incumbent = list(incumbent_books[population_id])
        if (
            len(incumbent_indices) != ENTRIES
            or len(supplied_incumbent) != ENTRIES
            or len({lineup.ids for lineup in supplied_incumbent}) != ENTRIES
            or [lineup.ids for lineup in expected_incumbent]
            != [lineup.ids for lineup in supplied_incumbent]
        ):
            _fail(f"{population_id} incumbent CBWU book differs")

        cap_started = perf_counter()
        cap_indices, cap_summary, cap_trace = _cap4_prefix_then_fill(
            scores=scores,
            lineup_ids=lineup_ids,
            rosters=roster_sets,
            entry_budget=ENTRIES,
        )
        cap_runtime = perf_counter() - cap_started
        if len(cap_indices) != ENTRIES or len(set(cap_indices)) != ENTRIES:
            _fail(f"{population_id} cap-4 selector lacks exact K80")
        cap_books[population_id] = [
            batch.candidates[index] for index in cap_indices
        ]

        ladder_started = perf_counter()
        ladder_indices, ladder_trace = _production_ladder_order(
            scores=scores,
            lineup_ids=lineup_ids,
            entry_budget=ENTRIES,
        )
        ladder_runtime = perf_counter() - ladder_started
        selector_runtime_total += (
            incumbent_runtime + cap_runtime + ladder_runtime
        )

        incumbent_receipt = _book_receipt(
            selector_id=INCUMBENT_RETRIEVAL_ID,
            selected=incumbent_indices,
            lineup_ids=lineup_ids,
            rosters=rosters,
            scores=scores,
            independent_audit_scores=audit_scores,
            runtime_seconds=incumbent_runtime,
        )
        cap_receipt = _book_receipt(
            selector_id=CAP4_RETRIEVAL_ID,
            selected=cap_indices,
            lineup_ids=lineup_ids,
            rosters=rosters,
            scores=scores,
            independent_audit_scores=audit_scores,
            runtime_seconds=cap_runtime,
            selection_trace=cap_trace,
            cap_engagement=cap_summary,
        )
        ladder_ids = [lineup_ids[index] for index in ladder_indices]
        ladder_rosters = [rosters[index] for index in ladder_indices]
        ladder_diagnostic = {
            "selector_id": UNCAPPED_LADDER_DIAGNOSTIC_ID,
            "official_crossing_cell": False,
            "selected_lineup_ids": ladder_ids,
            "selected_lineup_ids_sha256": canonical_sha256(ladder_ids),
            "selected_rosters": ladder_rosters,
            "selected_rosters_sha256": canonical_sha256(ladder_rosters),
            "selection_trace_sha256": canonical_sha256(ladder_trace),
            "selector_runtime_seconds": float(ladder_runtime),
            "simulated_diagnostics": _simulated_diagnostics(
                scores, ladder_indices
            ),
            "uses_realized_outcomes": False,
        }
        candidate_payload = {
            "lineup_ids": lineup_ids,
            "rosters": rosters,
        }
        population_receipts[population_id] = {
            "population_id": population_id,
            "candidate_count": len(batch.candidates),
            "candidate_lineup_ids": lineup_ids,
            "candidate_lineup_ids_sha256": canonical_sha256(lineup_ids),
            "candidate_rosters_sha256": canonical_sha256(rosters),
            "candidate_population_sha256": canonical_sha256(
                candidate_payload
            ),
            "candidate_score_matrix_receipt": _array_receipt(scores),
            "retrievals": {
                INCUMBENT_RETRIEVAL_ID: incumbent_receipt,
                CAP4_RETRIEVAL_ID: cap_receipt,
            },
            "incumbent_vs_cap4": _membership_comparison(
                incumbent_receipt["selected_lineup_ids"],
                cap_receipt["selected_lineup_ids"],
            ),
            "cap4_vs_uncapped_ladder": _membership_comparison(
                cap_receipt["selected_lineup_ids"], ladder_ids
            ),
            "uncapped_ladder_mechanism_diagnostic": ladder_diagnostic,
            "same_candidate_pool_for_both_official_retrievals": True,
            "candidate_solves_requested_by_crossing": 0,
        }

    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "population_order": list(POPULATION_ORDER),
        "retrieval_order": list(RETRIEVAL_ORDER),
        "cell_order": [
            {
                "population_id": population_id,
                "retrieval_id": retrieval_id,
            }
            for population_id in POPULATION_ORDER
            for retrieval_id in RETRIEVAL_ORDER
        ],
        "entry_budget": ENTRIES,
        "shared_selection_bank": {
            "player_ids_sha256": canonical_sha256(shared_player_ids),
            "dk_player_ids_sha256": canonical_sha256(shared_dk_player_ids),
            "player_world_matrix_receipt": shared_world_receipt,
            "world_count": WORLD_COUNT,
            "world_blocks": 5,
            "worlds_per_block": [10_000] * 5,
            "identical_across_both_populations": True,
        },
        "independent_score_only_audit_bank": {
            "player_world_matrix_receipt": audit_world_receipt,
            "world_count": AUDIT_WORLD_COUNT,
            "used_for_selection": False,
            "distinct_from_every_selection_block": True,
        },
        "selection_laws": {
            INCUMBENT_RETRIEVAL_ID: {
                "method": "greedy-max-coverage-then-p-line-mean-fill",
                "coverage_operator": ">=",
                "coverage_line": INCUMBENT_LINE,
            },
            CAP4_RETRIEVAL_ID: {
                "method": "hard-cap-prefix-until-exhaustion-then-fill",
                "overlap_cap": OVERLAP_CAP,
                "strict_tail_rungs": [
                    {"operator": ">", "threshold": threshold, "weight": weight}
                    for threshold, weight in SELECTION_RUNGS
                ],
                "ties": [
                    "largest-individual-strict-gt-200-count",
                    "largest-fit-world-mean",
                    "ascending-canonical-lineup-id",
                ],
                "cap_relaxed_within_prefix": False,
                "completion_uses_same-unconstrained-production-ladder": True,
            },
        },
        "report_thresholds": list(REPORT_THRESHOLDS),
        "populations": population_receipts,
        "candidate_generation_reused": True,
        "candidate_solves_requested_by_crossing": 0,
        "shared_generation_exposure_ledger_modified": False,
        "selector_runtime_seconds": float(selector_runtime_total),
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
        "historical_scoring_performed": False,
        "production_enabled": False,
    }
    body["science_sha256_excluding_runtime"] = canonical_sha256(
        _without_runtime(body)
    )
    body["receipt_sha256"] = canonical_sha256(body)
    return cap_books, body


__all__ = [
    "CAP4_RETRIEVAL_ID",
    "ENTRIES",
    "INCUMBENT_RETRIEVAL_ID",
    "POPULATION_ORDER",
    "PREFIXES",
    "ProspectiveGenerationRetrievalCrossingError",
    "REPORT_THRESHOLDS",
    "RETRIEVAL_ORDER",
    "SCHEMA_VERSION",
    "SELECTION_RUNGS",
    "build_generation_retrieval_crossing",
]
