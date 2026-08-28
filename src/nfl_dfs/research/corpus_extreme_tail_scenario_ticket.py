"""Outcome-blind event-component ticket selector for the T230 supplement.

This module implements section 8 of the frozen pre-Week-1 experiment matrix.
It consumes only an eligible lineup identity vector and its ordinary-R fit
score matrix.  Inclusive-230 events define exact connected components in the
candidate/world bipartite graph.  One breadth ticket per component is followed
by an exact integer D'Hondt continuation.  The frozen block-robust ladder is
used verbatim when support fails and as an exhaustion suffix.

The implementation is deliberately pure.  It has no outcome, held-out,
storage, graph-database, promotion, or production-policy interface.  Candidate
event masks are bit-packed and all dense candidate scans are chunked, bounding
the selector's added memory for the intended roughly 1,000 by 40,000 fit-event
surface.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as suite
from nfl_dfs.research import corpus_extreme_tail_support_switch as support_switch
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    _score_matrix_sha256,
    canonical_json_bytes,
    canonical_sha256,
)


SCENARIO_TICKET_SCHEMA: Final = "extreme-tail-scenario-ticket-selection/v1"
CONTRACT_SCHEMA: Final = "extreme-tail-scenario-ticket-contract/v1"
STRATEGY_ID: Final = "support-switched-event-component-tickets-ge-230-v1"
IMPLEMENTATION_ID: Final = "packed-exact-event-components-dhondt-v1"
CANONICAL_WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
ENTRY_BUDGETS: Final = (4, 14, 80)
RANKING_DEPTH: Final = 80
EVENT_THRESHOLD: Final = 230.0
EVENT_OPERATOR: Final = ">="
FOLD_MINIMUM_OPPORTUNITY_WORLDS: Final = 100
FINAL_MINIMUM_OPPORTUNITY_WORLDS: Final = 125
FALLBACK_STRATEGY_ID: Final = (
    "block-robust-bounded-tail-ge-210-250-v1"
)
FALLBACK_STRATEGY_SHA256: Final = (
    "b3c4bf6ea5e09446e0fff6b901412c7e9370a1b0e1ac0053d864eaef36f958d9"
)
FALLBACK_IMPLEMENTATION_SHA256: Final = (
    "0ede95f034186bdf382af8a9c87c311b83799c5e9609ec11d2cffb3c2114ce4b"
)
LITERAL_COVERAGE_STRATEGY_ID: Final = "coverage-ge-230-v1"
LITERAL_COVERAGE_STRATEGY_SHA256: Final = (
    "c43598db8dc2b081158f0660f8edc1ccae4ce1c58ff6a468036c6dbc089fa965"
)
FALLBACK_RUNGS: Final = (
    (210.0, ">=", 1),
    (220.0, ">=", 2),
    (230.0, ">=", 4),
    (240.0, ">=", 8),
    (250.0, ">=", 16),
)
_PACKED_BITORDER: Final = "little"
_CANDIDATE_CHUNK_ROWS: Final = 64
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


class CorpusExtremeTailScenarioTicketError(ValueError):
    """The frozen scenario-ticket law cannot be executed or replayed."""


def _fail(message: str) -> None:
    raise CorpusExtremeTailScenarioTicketError(message)


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return canonical_json_bytes(value)
    except (TypeError, ValueError) as exc:
        raise CorpusExtremeTailScenarioTicketError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _sha(value: object, *, label: str) -> str:
    try:
        return canonical_sha256(value)
    except (TypeError, ValueError) as exc:
        raise CorpusExtremeTailScenarioTicketError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    result[field] = _sha(result, label=field)
    return result


def _expected_fallback_strategy() -> dict[str, object]:
    return {
        "schema_version": "extreme-tail-retrieval-strategy/v1",
        "ordinal": 2,
        "strategy_id": FALLBACK_STRATEGY_ID,
        "method": "greedy-blockmin-ladder-v1",
        "parameters": {
            "rungs": [
                {"threshold": threshold, "operator": operator, "weight": weight}
                for threshold, operator, weight in FALLBACK_RUNGS
            ],
            "incremental_weight_law": "finite-nested-1-2-4-8-16",
            "maximum_new_world_utility": 31,
            "block_objective": (
                "leximin-ascending-per-training-block-weighted-coverage"
            ),
        },
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "selector_implementation_id": (
            "packed-chunked-exact-t230-selectors-v1"
        ),
        "selector_implementation_sha256": FALLBACK_IMPLEMENTATION_SHA256,
        "tie_law": [
            "greatest-post-addition-leximin-block-utility-profile",
            "largest-individual-strict-gt-200-count",
            "largest-training-mean-score",
            "ascending-lineup-id",
        ],
        "selection_inputs": (
            "fold-eligible-full-union-training-block-simulated-scores-only"
        ),
        "role": "block-robust-fallback",
        "description": (
            "Leximin per-block form of the same finite inclusive tail ladder."
        ),
        "strategy_sha256": FALLBACK_STRATEGY_SHA256,
    }


def _assert_frozen_dependency_contract() -> None:
    """Fail closed on local, raw-suite, world, or policy contract drift."""
    if (
        STRATEGY_ID
        != "support-switched-event-component-tickets-ge-230-v1"
        or IMPLEMENTATION_ID != "packed-exact-event-components-dhondt-v1"
        or CANONICAL_WORLD_BLOCKS != ("R0", "R1", "R2", "R3", "R4")
        or ENTRY_BUDGETS != (4, 14, 80)
        or RANKING_DEPTH != 80
        or EVENT_THRESHOLD != 230.0
        or EVENT_OPERATOR != ">="
        or FOLD_MINIMUM_OPPORTUNITY_WORLDS != 100
        or FINAL_MINIMUM_OPPORTUNITY_WORLDS != 125
        or FALLBACK_STRATEGY_ID
        != "block-robust-bounded-tail-ge-210-250-v1"
        or FALLBACK_STRATEGY_SHA256
        != "b3c4bf6ea5e09446e0fff6b901412c7e9370a1b0e1ac0053d864eaef36f958d9"
        or FALLBACK_IMPLEMENTATION_SHA256
        != "0ede95f034186bdf382af8a9c87c311b83799c5e9609ec11d2cffb3c2114ce4b"
        or LITERAL_COVERAGE_STRATEGY_ID != "coverage-ge-230-v1"
        or LITERAL_COVERAGE_STRATEGY_SHA256
        != "c43598db8dc2b081158f0660f8edc1ccae4ce1c58ff6a468036c6dbc089fa965"
        or FALLBACK_RUNGS
        != (
            (210.0, ">=", 1),
            (220.0, ">=", 2),
            (230.0, ">=", 4),
            (240.0, ">=", 8),
            (250.0, ">=", 16),
        )
    ):
        _fail("scenario-ticket literal constants differ from frozen v1")
    if (
        tuple(suite.ENTRY_BUDGETS) != ENTRY_BUDGETS
        or suite.RANKING_DEPTH != RANKING_DEPTH
        or tuple(suite.TAIL_RUNGS) != FALLBACK_RUNGS
        or tuple(rw.WORLD_BLOCKS) != CANONICAL_WORLD_BLOCKS
    ):
        _fail("frozen T230 suite constants differ from scenario-ticket contract")
    registry = suite.frozen_extreme_tail_strategies_v1()
    if (
        len(registry) != 4
        or registry[0].get("strategy_id") != LITERAL_COVERAGE_STRATEGY_ID
        or registry[0].get("strategy_sha256")
        != LITERAL_COVERAGE_STRATEGY_SHA256
        or registry[0].get("method") != "greedy-threshold-coverage-v1"
        or registry[0].get("parameters")
        != {"threshold": 230.0, "operator": ">="}
        or _canonical(registry[2], label="raw-suite fallback strategy")
        != _canonical(
            _expected_fallback_strategy(), label="scenario fallback strategy"
        )
    ):
        _fail("frozen block-robust fallback strategy differs")
    implementation = suite.frozen_selector_implementation_contract_v1()
    if (
        implementation.get("selector_implementation_sha256")
        != FALLBACK_IMPLEMENTATION_SHA256
    ):
        _fail("frozen block-robust fallback implementation differs")
    expected_neighbor_gate = {
        "threshold_id": "ge_230",
        "score": 230.0,
        "operator": ">=",
        "requires_every_training_block_nonzero": True,
        "fold_training_block_count": 4,
        "fold_minimum_opportunity_world_count": 100,
        "final_training_block_count": 5,
        "final_minimum_opportunity_world_count": 125,
    }
    if (
        support_switch.LITERAL_COVERAGE_STRATEGY_ID
        != LITERAL_COVERAGE_STRATEGY_ID
        or support_switch.FALLBACK_STRATEGY_ID != FALLBACK_STRATEGY_ID
        or support_switch.FOLD_MINIMUM_OPPORTUNITY_WORLDS != 100
        or support_switch.FINAL_MINIMUM_OPPORTUNITY_WORLDS != 125
        or _canonical(
            support_switch._gate_law(), label="neighboring support-switch gate"
        )
        != _canonical(
            expected_neighbor_gate, label="scenario support-switch gate"
        )
    ):
        _fail("neighboring support-switch policy differs from scenario contract")


def frozen_scenario_ticket_contract_v1() -> dict[str, object]:
    """Return the literal, outcome-blind selector contract and its self-hash."""
    _assert_frozen_dependency_contract()
    body = {
        "schema_version": CONTRACT_SCHEMA,
        "strategy_id": STRATEGY_ID,
        "implementation_id": IMPLEMENTATION_ID,
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "world_block_registry": list(CANONICAL_WORLD_BLOCKS),
        "scope_law": {
            "cross_fit": "registry-order-minus-exact-heldout-block",
            "final_fit": "exact-five-block-registry-order-with-null-heldout",
        },
        "event_law": {
            "threshold": EVENT_THRESHOLD,
            "operator": EVENT_OPERATOR,
            "world_identity": ["fit-block-ordinal", "zero-based-world-column"],
            "retained_world_law": "at-least-one-eligible-candidate-event",
            "retained_candidate_law": "at-least-one-retained-world-event",
        },
        "component_law": {
            "graph": "exact-undirected-candidate-world-bipartite-graph",
            "partition": "unique-maximal-connected-components",
            "component_key_payload": [
                "sorted-world-identity-pairs",
                "sorted-canonical-lineup-ids",
            ],
            "component_key_hash": "canonical-json-sha256",
            "no-distance-cutoff": True,
            "no-caller-selected-cluster-count": True,
            "no-random-seed": True,
        },
        "allocation_law": {
            "breadth_order": [
                "descending-distinct-fit-block-count",
                "descending-opportunity-world-count",
                "descending-component-candidate-count",
                "ascending-component-key",
            ],
            "breadth_visits": "one-per-initially-active-component",
            "continuation": "dhondt-q-over-tickets-plus-one",
            "quotient_comparison": "exact-integer-cross-multiplication",
            "dhondt_ties": [
                "descending-distinct-fit-block-count",
                "descending-opportunity-world-count",
                "descending-component-candidate-count",
                "ascending-component-key",
            ],
            "inactive_law": "no-unselected-candidate-has-new-component-world",
        },
        "within_component_ties": [
            "largest-new-component-world-count",
            "largest-individual-component-ge-230-count",
            "largest-individual-complete-fit-ge-230-count",
            "largest-fit-world-mean-score",
            "ascending-lineup-id",
        ],
        "support_gate": {
            "requires_every_fit_block_nonzero": True,
            "cross_fit_block_count": 4,
            "cross_fit_minimum_opportunity_world_count": (
                FOLD_MINIMUM_OPPORTUNITY_WORLDS
            ),
            "final_fit_block_count": 5,
            "final_fit_minimum_opportunity_world_count": (
                FINAL_MINIMUM_OPPORTUNITY_WORLDS
            ),
        },
        "fallback": {
            "strategy_id": FALLBACK_STRATEGY_ID,
            "strategy_sha256": FALLBACK_STRATEGY_SHA256,
            "selector_implementation_sha256": FALLBACK_IMPLEMENTATION_SHA256,
            "rungs": [
                {"threshold": threshold, "operator": operator, "weight": weight}
                for threshold, operator, weight in FALLBACK_RUNGS
            ],
            "source_ranking_depth": 80,
            "support_failure_law": "use-exact-block-robust-rank80-verbatim",
            "component_exhaustion_law": (
                "filter-selected-ids-from-exact-block-robust-rank80-then-append"
            ),
            "relative_order_preserved": True,
        },
        "selection_inputs": (
            "eligible-lineup-ids-and-ordinary-r-fit-simulated-scores-only"
        ),
        "forbidden_inputs": [
            "held-out-scores",
            "realized-outcomes",
            "player-traits",
            "ownership",
            "field-data",
            "learned-embeddings",
            "caller-selected-cluster-count",
            "similarity-threshold",
        ],
        "memory_law": {
            "event_masks": "numpy-packbits-uint8",
            "bitorder": _PACKED_BITORDER,
            "candidate_chunk_rows": _CANDIDATE_CHUNK_ROWS,
            "dense-candidate-by-world-boolean-retained": False,
        },
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "contract_sha256")


def _candidate_chunks(row_count: int):
    for start in range(0, row_count, _CANDIDATE_CHUNK_ROWS):
        yield start, min(start + _CANDIDATE_CHUNK_ROWS, row_count)


def _packed_counts(packed: np.ndarray) -> np.ndarray:
    result = np.empty(packed.shape[0], dtype=np.int64)
    for start, stop in _candidate_chunks(packed.shape[0]):
        result[start:stop] = _PACKED_POPCOUNT[
            packed[start:stop]
        ].sum(axis=1, dtype=np.int64)
    return result


def _packed_count(row: np.ndarray) -> int:
    return int(_PACKED_POPCOUNT[row].sum(dtype=np.int64))


def _pack_threshold(matrix: np.ndarray, threshold: float) -> np.ndarray:
    packed = np.empty(
        (matrix.shape[0], (matrix.shape[1] + 7) // 8), dtype=np.uint8
    )
    bound = np.float32(threshold)
    for start, stop in _candidate_chunks(matrix.shape[0]):
        packed[start:stop] = np.packbits(
            matrix[start:stop] >= bound,
            axis=1,
            bitorder=_PACKED_BITORDER,
        )
    return packed


def _pack_strict_threshold(matrix: np.ndarray, threshold: float) -> np.ndarray:
    packed = np.empty(
        (matrix.shape[0], (matrix.shape[1] + 7) // 8), dtype=np.uint8
    )
    bound = np.float32(threshold)
    for start, stop in _candidate_chunks(matrix.shape[0]):
        packed[start:stop] = np.packbits(
            matrix[start:stop] > bound,
            axis=1,
            bitorder=_PACKED_BITORDER,
        )
    return packed


def _validated_inputs(
    *,
    lineup_ids: Sequence[str],
    fit_scores: np.ndarray,
    world_block_registry: Sequence[str],
    worlds_per_block: int,
    scope_kind: str,
    heldout_block: str | None,
) -> tuple[list[str], np.ndarray, list[str], int]:
    if isinstance(lineup_ids, (str, bytes)) or not isinstance(
        lineup_ids, Sequence
    ):
        _fail("lineup_ids must be an array")
    ids = list(lineup_ids)
    if (
        len(ids) < RANKING_DEPTH
        or any(type(lineup_id) is not str or not lineup_id for lineup_id in ids)
        or len(set(ids)) != len(ids)
    ):
        _fail("lineup_ids must contain at least 80 unique nonempty strings")
    if ids != sorted(ids):
        _fail("lineup_ids must already be in ascending canonical order")
    if isinstance(world_block_registry, (str, bytes)) or not isinstance(
        world_block_registry, Sequence
    ):
        _fail("world_block_registry must be an array")
    registry = list(world_block_registry)
    if registry != list(CANONICAL_WORLD_BLOCKS):
        _fail("world block registry differs from canonical R0..R4 order")
    if scope_kind not in {"cross-fit", "final-fit"}:
        _fail("scope_kind must be cross-fit or final-fit")
    if scope_kind == "cross-fit":
        if type(heldout_block) is not str or heldout_block not in registry:
            _fail("cross-fit scope requires one exact canonical heldout block")
        blocks = [block for block in registry if block != heldout_block]
    else:
        if heldout_block is not None:
            _fail("final-fit scope requires null heldout block")
        blocks = registry
    expected_block_count = len(blocks)
    if type(worlds_per_block) is not int or worlds_per_block < 1:
        _fail("worlds_per_block must be a positive exact integer")
    raw = np.asarray(fit_scores)
    if (
        raw.dtype != np.dtype(np.float64)
        or raw.ndim != 2
        or not raw.flags.c_contiguous
        or raw.shape != (len(ids), len(blocks) * worlds_per_block)
    ):
        _fail("fit scores must be C-contiguous native float64 at exact shape")
    for start, stop in _candidate_chunks(raw.shape[0]):
        if not np.isfinite(raw[start:stop]).all():
            _fail("fit score matrix contains a non-finite value")
    return ids, raw, blocks, expected_block_count


class _DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = np.arange(size, dtype=np.int64)

    def find(self, value: int) -> int:
        parent = self.parent
        root = value
        while int(parent[root]) != root:
            root = int(parent[root])
        while int(parent[value]) != value:
            next_value = int(parent[value])
            parent[value] = root
            value = next_value
        return root

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        smaller = min(left_root, right_root)
        larger = max(left_root, right_root)
        self.parent[larger] = smaller


@dataclass
class _Component:
    key: str
    candidates: list[int]
    worlds: np.ndarray
    q: int
    breadth: int
    block_counts: list[int]
    covered_count: int = 0
    tickets: int = 0
    selected: list[int] | None = None

    def __post_init__(self) -> None:
        if self.selected is None:
            self.selected = []


def _event_graph(
    *,
    packed: np.ndarray,
    event_counts: np.ndarray,
    lineup_ids: Sequence[str],
    block_count: int,
    worlds_per_block: int,
) -> tuple[list[_Component], np.ndarray]:
    candidate_count = packed.shape[0]
    world_count = block_count * worlds_per_block
    owner = np.full(world_count, -1, dtype=np.int64)
    dsu = _DisjointSet(candidate_count)
    for candidate in range(candidate_count):
        if not event_counts[candidate]:
            continue
        event = np.unpackbits(
            packed[candidate], bitorder=_PACKED_BITORDER, count=world_count
        ).astype(bool, copy=False)
        worlds = np.flatnonzero(event)
        prior = owner[worlds]
        for prior_candidate in np.unique(prior[prior >= 0]):
            dsu.union(candidate, int(prior_candidate))
        unseen = prior < 0
        owner[worlds[unseen]] = candidate
    candidates_by_root: dict[int, list[int]] = {}
    for candidate, count in enumerate(event_counts):
        if count:
            root = dsu.find(candidate)
            candidates_by_root.setdefault(root, []).append(candidate)
    worlds_by_root: dict[int, list[int]] = {}
    for world, candidate in enumerate(owner):
        if candidate >= 0:
            root = dsu.find(int(candidate))
            worlds_by_root.setdefault(root, []).append(world)
    components: list[_Component] = []
    for root, candidate_indices in candidates_by_root.items():
        worlds = np.asarray(worlds_by_root[root], dtype=np.int64)
        candidate_indices.sort(key=lambda index: lineup_ids[index])
        world_identities = [
            {
                "block_ordinal": int(world // worlds_per_block),
                "world_column": int(world % worlds_per_block),
            }
            for world in worlds
        ]
        key = _sha(
            {
                "world_ids": world_identities,
                "candidate_ids": [lineup_ids[index] for index in candidate_indices],
            },
            label="component key payload",
        )
        block_counts = [
            int(
                np.count_nonzero(
                    (worlds // worlds_per_block) == block_ordinal
                )
            )
            for block_ordinal in range(block_count)
        ]
        components.append(_Component(
            key=key,
            candidates=candidate_indices,
            worlds=worlds,
            q=len(worlds),
            breadth=sum(count > 0 for count in block_counts),
            block_counts=block_counts,
        ))
    components.sort(key=lambda item: item.key)
    return components, owner


def _support_gate(
    *,
    owner: np.ndarray,
    blocks: Sequence[str],
    worlds_per_block: int,
    scope_kind: str,
) -> dict[str, object]:
    per_block = [
        int(
            np.count_nonzero(
                owner[ordinal * worlds_per_block:(ordinal + 1) * worlds_per_block]
                >= 0
            )
        )
        for ordinal in range(len(blocks))
    ]
    total = sum(per_block)
    minimum = (
        FOLD_MINIMUM_OPPORTUNITY_WORLDS
        if scope_kind == "cross-fit"
        else FINAL_MINIMUM_OPPORTUNITY_WORLDS
    )
    zero_blocks = [
        block for block, count in zip(blocks, per_block, strict=True) if count == 0
    ]
    passed = not zero_blocks and total >= minimum
    reasons: list[str] = []
    if zero_blocks:
        reasons.append("one-or-more-fit-blocks-have-zero-ge-230-opportunity")
    if total < minimum:
        reasons.append("aggregate-fit-ge-230-opportunity-below-frozen-minimum")
    return {
        "scope_kind": scope_kind,
        "threshold": EVENT_THRESHOLD,
        "operator": EVENT_OPERATOR,
        "fit_blocks": list(blocks),
        "per_block_opportunity_world_counts": [
            {"block_id": block, "opportunity_world_count": count}
            for block, count in zip(blocks, per_block, strict=True)
        ],
        "zero_opportunity_fit_blocks": zero_blocks,
        "every_fit_block_nonzero": not zero_blocks,
        "opportunity_world_count": total,
        "minimum_opportunity_world_count": minimum,
        "aggregate_comparison_operator": ">=",
        "passed": passed,
        "failure_reasons": reasons,
    }


def _fresh_count(packed_row: np.ndarray, covered: np.ndarray) -> int:
    return _packed_count(np.bitwise_and(packed_row, np.bitwise_not(covered)))


def _choose_within_component(
    component: _Component,
    *,
    packed: np.ndarray,
    event_counts: np.ndarray,
    means: np.ndarray,
    lineup_ids: Sequence[str],
    covered: np.ndarray,
    already_selected: np.ndarray,
) -> tuple[int, int] | None:
    best: int | None = None
    best_gain = 0
    best_key: tuple[object, ...] | None = None
    for candidate in component.candidates:
        if already_selected[candidate]:
            continue
        gain = _fresh_count(packed[candidate], covered)
        if not gain:
            continue
        within_count = int(event_counts[candidate])
        key = (
            -gain,
            -within_count,
            -int(event_counts[candidate]),
            -float(means[candidate]),
            lineup_ids[candidate],
        )
        if best_key is None or key < best_key:
            best = candidate
            best_gain = gain
            best_key = key
    if best is None:
        return None
    return best, best_gain


def _component_order_key(component: _Component) -> tuple[object, ...]:
    return (-component.breadth, -component.q, -len(component.candidates), component.key)


def _dhondt_better(candidate: _Component, incumbent: _Component) -> bool:
    left = candidate.q * (incumbent.tickets + 1)
    right = incumbent.q * (candidate.tickets + 1)
    if left != right:
        return left > right
    return _component_order_key(candidate) < _component_order_key(incumbent)


def _scenario_rank(
    *,
    components: Sequence[_Component],
    packed: np.ndarray,
    event_counts: np.ndarray,
    means: np.ndarray,
    lineup_ids: Sequence[str],
    ranking_depth: int = RANKING_DEPTH,
) -> tuple[list[int], list[dict[str, object]]]:
    if (
        type(ranking_depth) is not int
        or ranking_depth < 1
        or ranking_depth > len(lineup_ids)
    ):
        _fail("scenario-ticket ranking depth is infeasible")
    covered = np.zeros(packed.shape[1], dtype=np.uint8)
    already_selected = np.zeros(packed.shape[0], dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    active = {component.key: component for component in components}

    def visit(component: _Component, phase: str) -> bool:
        choice = _choose_within_component(
            component,
            packed=packed,
            event_counts=event_counts,
            means=means,
            lineup_ids=lineup_ids,
            covered=covered,
            already_selected=already_selected,
        )
        if choice is None:
            active.pop(component.key, None)
            return False
        candidate, gain = choice
        before = component.covered_count
        quotient = (
            None
            if phase == "breadth"
            else {"numerator": component.q, "denominator": component.tickets + 1}
        )
        component.tickets += 1
        component.covered_count += gain
        assert component.selected is not None
        component.selected.append(candidate)
        selected.append(candidate)
        already_selected[candidate] = True
        covered[:] |= packed[candidate]
        trace.append({
            "selection_rank": len(selected) - 1,
            "lineup_id": lineup_ids[candidate],
            "canonical_lineup_index": candidate,
            "selection_source": "scenario-ticket",
            "allocation_phase": phase,
            "component_key": component.key,
            "component_ticket_ordinal": component.tickets,
            "component_opportunity_world_count": component.q,
            "component_distinct_fit_block_count": component.breadth,
            "component_candidate_count": len(component.candidates),
            "dhondt_quotient": quotient,
            "marginal_new_component_world_count": gain,
            "individual_component_ge_230_event_count": int(
                event_counts[candidate]
            ),
            "individual_complete_fit_ge_230_event_count": int(
                event_counts[candidate]
            ),
            "fit_world_mean_score": float(means[candidate]),
            "component_covered_world_count_before": before,
            "component_covered_world_count_after": component.covered_count,
        })
        if _choose_within_component(
            component,
            packed=packed,
            event_counts=event_counts,
            means=means,
            lineup_ids=lineup_ids,
            covered=covered,
            already_selected=already_selected,
        ) is None:
            active.pop(component.key, None)
        return True

    breadth_order = sorted(components, key=_component_order_key)
    for component in breadth_order:
        if len(selected) == ranking_depth:
            break
        if component.key in active:
            visit(component, "breadth")
    while len(selected) < ranking_depth and active:
        best: _Component | None = None
        for component in active.values():
            if best is None or _dhondt_better(component, best):
                best = component
        if best is None:
            break
        visit(best, "dhondt")
    return selected, trace


def _pack_block_thresholds(
    matrix: np.ndarray, *, block_count: int, worlds_per_block: int
) -> list[list[np.ndarray]]:
    result: list[list[np.ndarray]] = []
    for threshold, _operator, _weight in FALLBACK_RUNGS:
        by_block: list[np.ndarray] = []
        bound = np.float32(threshold)
        for block in range(block_count):
            start_column = block * worlds_per_block
            stop_column = start_column + worlds_per_block
            packed = np.empty(
                (matrix.shape[0], (worlds_per_block + 7) // 8),
                dtype=np.uint8,
            )
            for start, stop in _candidate_chunks(matrix.shape[0]):
                packed[start:stop] = np.packbits(
                    matrix[start:stop, start_column:stop_column] >= bound,
                    axis=1,
                    bitorder=_PACKED_BITORDER,
                )
            by_block.append(packed)
        result.append(by_block)
    return result


def _fresh_counts_chunk(
    packed: np.ndarray,
    *,
    start: int,
    stop: int,
    covered: np.ndarray,
) -> np.ndarray:
    fresh = np.bitwise_and(packed[start:stop], np.bitwise_not(covered))
    return _PACKED_POPCOUNT[fresh].sum(axis=1, dtype=np.int64)


def _block_robust_rank(
    *,
    matrix: np.ndarray,
    lineup_ids: Sequence[str],
    block_count: int,
    worlds_per_block: int,
    depth: int,
) -> tuple[list[int], list[dict[str, object]]]:
    rung_masks = _pack_block_thresholds(
        matrix, block_count=block_count, worlds_per_block=worlds_per_block
    )
    weights = [weight for _threshold, _operator, weight in FALLBACK_RUNGS]
    primary_counts = _packed_counts(_pack_strict_threshold(matrix, 200.0))
    means = matrix.mean(axis=1, dtype=np.float64)
    covered = [
        [np.zeros(mask.shape[1], dtype=np.uint8) for mask in by_block]
        for by_block in rung_masks
    ]
    block_utilities = np.zeros(block_count, dtype=np.int64)
    remaining = np.ones(matrix.shape[0], dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < depth and np.any(remaining):
        best: int | None = None
        best_added: np.ndarray | None = None
        best_key: tuple[object, ...] | None = None
        for start, stop in _candidate_chunks(matrix.shape[0]):
            added = np.zeros((stop - start, block_count), dtype=np.int64)
            for weight, by_block, seen_by_block in zip(
                weights, rung_masks, covered, strict=True
            ):
                for block, (mask, seen) in enumerate(
                    zip(by_block, seen_by_block, strict=True)
                ):
                    added[:, block] += weight * _fresh_counts_chunk(
                        mask, start=start, stop=stop, covered=seen
                    )
            for position in range(stop - start):
                candidate = start + position
                if not remaining[candidate]:
                    continue
                after = block_utilities + added[position]
                key = (
                    tuple(-int(value) for value in np.sort(after)),
                    -int(primary_counts[candidate]),
                    -float(means[candidate]),
                    lineup_ids[candidate],
                )
                if best_key is None or key < best_key:
                    best = candidate
                    best_added = added[position].copy()
                    best_key = key
        if best is None or best_added is None:
            break
        if not np.any(best_added):
            fill = sorted(
                np.flatnonzero(remaining).tolist(),
                key=lambda candidate: (
                    -int(primary_counts[candidate]),
                    -float(means[candidate]),
                    lineup_ids[candidate],
                ),
            )[: depth - len(selected)]
            for candidate in fill:
                selected.append(candidate)
                trace.append({
                    "source_rank": len(selected) - 1,
                    "lineup_id": lineup_ids[candidate],
                    "canonical_lineup_index": candidate,
                    "marginal_utility": 0,
                    "individual_strict_gt_200_count": int(
                        primary_counts[candidate]
                    ),
                    "fit_world_mean_score": float(means[candidate]),
                    "leximin_profile_after": [
                        int(value) for value in np.sort(block_utilities)
                    ],
                })
            break
        after = block_utilities + best_added
        selected.append(best)
        trace.append({
            "source_rank": len(selected) - 1,
            "lineup_id": lineup_ids[best],
            "canonical_lineup_index": best,
            "marginal_utility": int(best_added.sum()),
            "individual_strict_gt_200_count": int(primary_counts[best]),
            "fit_world_mean_score": float(means[best]),
            "leximin_profile_after": [int(value) for value in np.sort(after)],
        })
        block_utilities = after
        for by_block, seen_by_block in zip(rung_masks, covered, strict=True):
            for mask, seen in zip(by_block, seen_by_block, strict=True):
                seen |= mask[best]
        remaining[best] = False
    if len(selected) != depth or len(set(selected)) != depth:
        _fail("block-robust fallback could not form its required ranking prefix")
    return selected, trace


def _literal_coverage_rank(
    *,
    packed: np.ndarray,
    event_counts: np.ndarray,
    means: np.ndarray,
    lineup_ids: Sequence[str],
) -> list[int]:
    covered = np.zeros(packed.shape[1], dtype=np.uint8)
    remaining = np.ones(packed.shape[0], dtype=bool)
    selected: list[int] = []
    while len(selected) < RANKING_DEPTH:
        best: int | None = None
        best_gain = 0
        best_key: tuple[object, ...] | None = None
        for start, stop in _candidate_chunks(packed.shape[0]):
            fresh = np.bitwise_and(
                packed[start:stop], np.bitwise_not(covered)
            )
            gains = _PACKED_POPCOUNT[fresh].sum(axis=1, dtype=np.int64)
            for position, raw_gain in enumerate(gains):
                candidate = start + position
                if not remaining[candidate]:
                    continue
                gain = int(raw_gain)
                key = (
                    -gain,
                    -int(event_counts[candidate]),
                    -float(means[candidate]),
                    lineup_ids[candidate],
                )
                if best_key is None or key < best_key:
                    best = candidate
                    best_gain = gain
                    best_key = key
        if best is None or not best_gain:
            break
        selected.append(best)
        remaining[best] = False
        covered |= packed[best]
    fill = sorted(
        np.flatnonzero(remaining).tolist(),
        key=lambda candidate: (
            -int(event_counts[candidate]),
            -float(means[candidate]),
            lineup_ids[candidate],
        ),
    )
    selected.extend(fill[: RANKING_DEPTH - len(selected)])
    return selected


def _event_diagnostics(
    *,
    selected: Sequence[int],
    literal: Sequence[int],
    packed: np.ndarray,
) -> dict[str, object]:
    selected_rows = packed[np.asarray(selected, dtype=np.int64)]
    vector_counts = Counter(bytes(row) for row in selected_rows)
    duplicate_pairs = sum(count * (count - 1) // 2 for count in vector_counts.values())
    jaccard_histogram: Counter[tuple[int, int]] = Counter()
    for left in range(len(selected_rows)):
        for right in range(left + 1, len(selected_rows)):
            intersection = _packed_count(
                np.bitwise_and(selected_rows[left], selected_rows[right])
            )
            union = _packed_count(
                np.bitwise_or(selected_rows[left], selected_rows[right])
            )
            jaccard_histogram[(intersection, union)] += 1
    return {
        "selected_event_vector_unique_count": len(vector_counts),
        "selected_event_vector_duplicate_pair_count": duplicate_pairs,
        "pairwise_event_jaccard_exact_histogram": [
            {
                "intersection_world_count": intersection,
                "union_world_count": union,
                "pair_count": count,
            }
            for (intersection, union), count in sorted(jaccard_histogram.items())
        ],
        "literal_coverage_comparison": [
            {
                "entry_budget": budget,
                "selected_id_overlap_count": len(
                    set(selected[:budget]) & set(literal[:budget])
                ),
                "scenario_covered_world_count": _packed_count(
                    np.bitwise_or.reduce(selected_rows[:budget], axis=0)
                ),
                "literal_covered_world_count": _packed_count(
                    np.bitwise_or.reduce(
                        packed[np.asarray(literal[:budget], dtype=np.int64)],
                        axis=0,
                    )
                ),
            }
            for budget in ENTRY_BUDGETS
        ],
    }


def _component_diagnostics(
    *, components: Sequence[_Component], blocks: Sequence[str]
) -> dict[str, object]:
    total = sum(component.q for component in components)
    largest = max((component.q for component in components), default=0)
    breadth_counts = Counter(component.breadth for component in components)
    return {
        "component_count": len(components),
        "opportunity_world_count": total,
        "one_giant_component": len(components) == 1,
        "largest_component_opportunity_share": {
            "numerator": largest,
            "denominator": total,
        },
        "component_block_breadth_distribution": [
            {"distinct_fit_block_count": breadth, "component_count": count}
            for breadth, count in sorted(breadth_counts.items())
        ],
        "components": [
            {
                "component_key": component.key,
                "opportunity_world_count": component.q,
                "distinct_fit_block_count": component.breadth,
                "candidate_count": len(component.candidates),
                "opportunity_world_counts_by_block": [
                    {"block_id": block, "opportunity_world_count": count}
                    for block, count in zip(
                        blocks, component.block_counts, strict=True
                    )
                ],
                "tickets_assigned": component.tickets,
                "selected_lineup_ids": [],
                "covered_opportunity_world_count": component.covered_count,
            }
            for component in sorted(components, key=lambda item: item.key)
        ],
    }


def build_scenario_ticket_selection_v1(
    *,
    lineup_ids: Sequence[str],
    fit_scores: np.ndarray,
    world_block_registry: Sequence[str],
    worlds_per_block: int,
    scope_kind: str,
    heldout_block: str | None,
) -> dict[str, object]:
    """Build one exact rank-80 scenario-ticket receipt and 4/14/80 books."""
    _assert_frozen_dependency_contract()
    ids, matrix, blocks, block_count = _validated_inputs(
        lineup_ids=lineup_ids,
        fit_scores=fit_scores,
        world_block_registry=world_block_registry,
        worlds_per_block=worlds_per_block,
        scope_kind=scope_kind,
        heldout_block=heldout_block,
    )
    packed = _pack_threshold(matrix, EVENT_THRESHOLD)
    event_counts = _packed_counts(packed)
    means = matrix.mean(axis=1, dtype=np.float64)
    components, owner = _event_graph(
        packed=packed,
        event_counts=event_counts,
        lineup_ids=ids,
        block_count=block_count,
        worlds_per_block=worlds_per_block,
    )
    gate = _support_gate(
        owner=owner,
        blocks=blocks,
        worlds_per_block=worlds_per_block,
        scope_kind=scope_kind,
    )
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    if gate["passed"]:
        selected, trace = _scenario_rank(
            components=components,
            packed=packed,
            event_counts=event_counts,
            means=means,
            lineup_ids=ids,
        )
    fallback_start: int | None = None
    fallback_rank: list[int] = []
    fallback_trace: list[dict[str, object]] = []
    if not gate["passed"] or len(selected) < RANKING_DEPTH:
        fallback_start = len(selected)
        fallback_rank, fallback_trace = _block_robust_rank(
            matrix=matrix,
            lineup_ids=ids,
            block_count=block_count,
            worlds_per_block=worlds_per_block,
            depth=RANKING_DEPTH,
        )
        selected_set = set(selected)
        for source_rank, candidate in enumerate(fallback_rank):
            if candidate in selected_set:
                continue
            selected.append(candidate)
            selected_set.add(candidate)
            source = fallback_trace[source_rank]
            trace.append({
                "selection_rank": len(selected) - 1,
                "lineup_id": ids[candidate],
                "canonical_lineup_index": candidate,
                "selection_source": "block-robust-fallback",
                "source_fallback_rank": source_rank,
                "source_marginal_utility": source["marginal_utility"],
                "source_leximin_profile_after": source[
                    "leximin_profile_after"
                ],
            })
            if len(selected) == RANKING_DEPTH:
                break
        if len(selected) != RANKING_DEPTH:
            _fail(
                "exact rank-80 fallback is insufficient after removing "
                "scenario-selected IDs"
            )
    if (
        len(selected) != RANKING_DEPTH
        or len(set(selected)) != RANKING_DEPTH
        or len(trace) != RANKING_DEPTH
    ):
        _fail("scenario ticket selector did not produce exact rank 80")
    literal = _literal_coverage_rank(
        packed=packed,
        event_counts=event_counts,
        means=means,
        lineup_ids=ids,
    )
    selected_ids = [ids[index] for index in selected]
    component_diagnostics = _component_diagnostics(
        components=components, blocks=blocks
    )
    selected_by_component: dict[str, list[str]] = {}
    for row in trace:
        component_key = row.get("component_key")
        if type(component_key) is str:
            selected_by_component.setdefault(component_key, []).append(
                str(row["lineup_id"])
            )
    for row in component_diagnostics["components"]:
        row["selected_lineup_ids"] = selected_by_component.get(
            row["component_key"], []
        )
    contract = frozen_scenario_ticket_contract_v1()
    input_binding = {
        "lineup_order_law": "input-must-be-ascending-canonical-lineup-id",
        "lineup_count": len(ids),
        "lineup_ids_sha256": _sha(ids, label="canonical lineup IDs"),
        "world_block_registry": list(CANONICAL_WORLD_BLOCKS),
        "heldout_block": heldout_block,
        "fit_block_ids": blocks,
        "worlds_per_block": worlds_per_block,
        "score_shape": list(matrix.shape),
        "fit_score_matrix_sha256": _score_matrix_sha256(matrix),
        "fallback_strategy_id": FALLBACK_STRATEGY_ID,
        "fallback_strategy_sha256": FALLBACK_STRATEGY_SHA256,
        "fallback_implementation_sha256": FALLBACK_IMPLEMENTATION_SHA256,
    }
    books = [
        _self_hash({
            "entry_budget": budget,
            "entry_count": budget,
            "selected_lineup_ids": selected_ids[:budget],
            "selected_lineup_ids_sha256": _sha(
                selected_ids[:budget], label=f"rank-{budget} lineup IDs"
            ),
            **{field: False for field in _FALSE_AUTHORITY_FIELDS},
        }, "book_sha256")
        for budget in ENTRY_BUDGETS
    ]
    body = {
        "schema_version": SCENARIO_TICKET_SCHEMA,
        "strategy_id": STRATEGY_ID,
        "implementation_id": IMPLEMENTATION_ID,
        "contract_sha256": contract["contract_sha256"],
        "scope_kind": scope_kind,
        "heldout_block": heldout_block,
        "input_binding": input_binding,
        "support_gate": gate,
        "selection_mode": (
            "block-robust-fallback-support-failure"
            if not gate["passed"]
            else (
                "scenario-tickets-with-block-robust-exhaustion-suffix"
                if fallback_start is not None
                else "scenario-tickets"
            )
        ),
        "fallback_rank_start": fallback_start,
        "fallback_rank_considered_lineup_ids": [
            ids[index] for index in fallback_rank
        ],
        "fallback_rank_considered_sha256": _sha(
            [ids[index] for index in fallback_rank],
            label="fallback rank considered",
        ),
        "fallback_trace_sha256": _sha(
            fallback_trace, label="fallback trace"
        ),
        "component_diagnostics": component_diagnostics,
        "event_diagnostics": _event_diagnostics(
            selected=selected,
            literal=literal,
            packed=packed,
        ),
        "ranking_depth": RANKING_DEPTH,
        "selected_canonical_indices": selected,
        "selected_lineup_ids": selected_ids,
        "selected_lineup_ids_sha256": _sha(
            selected_ids, label="scenario selected lineup IDs"
        ),
        "selection_trace": trace,
        "selection_trace_sha256": _sha(trace, label="scenario selection trace"),
        "entry_budgets": list(ENTRY_BUDGETS),
        "book_count": len(books),
        "books": books,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "scenario_ticket_sha256")


def validate_scenario_ticket_selection_v1(
    value: object,
    *,
    lineup_ids: Sequence[str],
    fit_scores: np.ndarray,
    world_block_registry: Sequence[str],
    worlds_per_block: int,
    scope_kind: str,
    heldout_block: str | None,
) -> dict[str, object]:
    """Rebuild the graph, schedule, fallback, diagnostics, and all prefixes."""
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        _fail("scenario-ticket receipt must be a string-keyed object")
    expected = build_scenario_ticket_selection_v1(
        lineup_ids=lineup_ids,
        fit_scores=fit_scores,
        world_block_registry=world_block_registry,
        worlds_per_block=worlds_per_block,
        scope_kind=scope_kind,
        heldout_block=heldout_block,
    )
    if _canonical(value, label="retained scenario-ticket receipt") != _canonical(
        expected, label="replayed scenario-ticket receipt"
    ):
        _fail("scenario-ticket receipt canonical replay differs")
    return expected
