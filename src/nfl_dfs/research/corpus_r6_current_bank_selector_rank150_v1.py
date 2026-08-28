"""Exact rank-150 continuation for the grouped R6 current-bank selectors.

The frozen successor ranks exactly 80 lineups.  This adjacent, outcome-blind
contract runs the same three deterministic native ranking laws to depth 150
and exposes exact 80-, 100-, and 150-entry prefixes of that one order.  It
does not extrapolate a score or synthesize entries beyond the ranked rows.

The original successor remains the authority for its rank-80 semantics.  Its
public function, schemas, constants, and default native-kernel calls are not
changed by this module.  The native private kernels accept an explicit depth
only for this continuation; their default remains the frozen depth of 80.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Final

import numpy as np

from nfl_dfs.research import (
    corpus_extreme_tail_preweek_additions as convex_source,
)
from nfl_dfs.research import (
    corpus_extreme_tail_roadmap_retrieval as roadmap_source,
)
from nfl_dfs.research import (
    corpus_extreme_tail_scenario_ticket as scenario_source,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)


RESULT_SCHEMA: Final = "corpus-r6-current-bank-selector-rank150-result/v1"
IMPLEMENTATION_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-rank150-implementation/v1"
)
IMPLEMENTATION_ID: Final = "exact-same-order-rank150-continuation-v1"
EXPECTED_IMPLEMENTATION_SHA256: Final = (
    "44d3edc2b74b752fccf688c603075ca4631a22744dea5e64f4e9f318c87260dd"
)
ENTRY_BUDGETS: Final = (80, 100, 150)
RANKING_DEPTH: Final = ENTRY_BUDGETS[-1]


class CorpusR6CurrentBankSelectorRank150V1Error(ValueError):
    """The exact rank-150 continuation cannot be constructed or replayed."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankSelectorRank150V1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return successor._canonical(value)
    except successor.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
        raise CorpusR6CurrentBankSelectorRank150V1Error(str(exc)) from exc


def _sha(value: object) -> str:
    try:
        return successor._sha(value)
    except successor.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
        raise CorpusR6CurrentBankSelectorRank150V1Error(str(exc)) from exc


def _with_hash(
    body: Mapping[str, object], *, field: str
) -> dict[str, object]:
    result = dict(body)
    if field in result:
        _fail(f"{field} cannot already be present")
    result[field] = _sha(result)
    return result


def frozen_rank150_implementation_v1() -> dict[str, object]:
    """Bind the continuation to the exact frozen rank-80 successor."""
    base = successor.frozen_successor_implementation_v1()
    registry = successor.frozen_native_preset_registry_v1()
    result = _with_hash({
        "schema_version": IMPLEMENTATION_SCHEMA,
        "implementation_id": IMPLEMENTATION_ID,
        "base_successor_implementation_id": base["implementation_id"],
        "base_successor_implementation_sha256": base[
            "implementation_sha256"
        ],
        "base_preset_registry_sha256": _sha(registry),
        "ranking_law": (
            "same-native-greedy-trajectory-with-stop-depth-raised-from-80-to-150"
        ),
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "exact_prefixes_only": True,
        "score_extrapolation_performed": False,
        "candidate_count_required": [RANKING_DEPTH, successor.MAX_CANDIDATES],
        "legacy_rank_80_public_contract_changed": False,
        "policy": dict(successor._FALSE_POLICY),
    }, field="implementation_sha256")
    if result["implementation_sha256"] != EXPECTED_IMPLEMENTATION_SHA256:
        _fail("rank-150 semantic implementation contract drifted")
    return result


def _run_convex_rank150_v1(
    *,
    scores: np.ndarray,
    lineup_ids: Sequence[str],
    shared: successor._SharedPreprocessingV1,
) -> tuple[list[int], dict[str, object]]:
    try:
        selected, trace = convex_source._select_convex_expected_max(
            scores=scores,
            canonical_source_rows=np.arange(len(lineup_ids), dtype=np.int64),
            lineup_ids=lineup_ids,
            means=shared.means,
            primary_counts=shared.strict_gt_200_counts,
            ranking_depth=RANKING_DEPTH,
        )
    except convex_source.CorpusExtremeTailPreweekAdditionsError as exc:
        raise CorpusR6CurrentBankSelectorRank150V1Error(str(exc)) from exc
    return selected, {
        "ranking_trace_sha256": _sha(trace),
        "rank_80_trace_prefix_sha256": _sha(trace[:80]),
        "rank_100_trace_prefix_sha256": _sha(trace[:100]),
        "rank_150_trace_prefix_sha256": _sha(trace),
    }


def _run_correlation_rank150_v1(
    *,
    scores: np.ndarray,
    lineup_ids: Sequence[str],
    training_blocks: Sequence[str],
    worlds_per_block: int,
    shared: successor._SharedPreprocessingV1,
) -> tuple[list[int], dict[str, object]]:
    try:
        selected, trace = (
            roadmap_source._select_correlation_aware_expected_max(
                scores=scores,
                canonical_source_rows=np.arange(
                    len(lineup_ids), dtype=np.int64
                ),
                packed_by_block=shared.packed_by_threshold[230.0],
                training_blocks=training_blocks,
                worlds_per_block=worlds_per_block,
                lineup_ids=lineup_ids,
                means=shared.means,
                ranking_depth=RANKING_DEPTH,
            )
        )
    except roadmap_source.CorpusExtremeTailRoadmapRetrievalError as exc:
        raise CorpusR6CurrentBankSelectorRank150V1Error(str(exc)) from exc
    return selected, {
        "ranking_trace_sha256": _sha(trace),
        "rank_80_trace_prefix_sha256": _sha(trace[:80]),
        "rank_100_trace_prefix_sha256": _sha(trace[:100]),
        "rank_150_trace_prefix_sha256": _sha(trace),
    }


def _run_scenario_rank150_v1(
    *,
    lineup_ids: Sequence[str],
    training_blocks: Sequence[str],
    worlds_per_block: int,
    shared: successor._SharedPreprocessingV1,
) -> tuple[list[int], dict[str, object]]:
    try:
        scenario_source._assert_frozen_dependency_contract()
        components, owner = scenario_source._event_graph(
            packed=shared.packed_full_230,
            event_counts=shared.inclusive_ge_230_counts,
            lineup_ids=lineup_ids,
            block_count=len(training_blocks),
            worlds_per_block=worlds_per_block,
        )
        gate = scenario_source._support_gate(
            owner=owner,
            blocks=training_blocks,
            worlds_per_block=worlds_per_block,
            scope_kind="cross-fit",
        )
        selected: list[int] = []
        trace: list[dict[str, object]] = []
        if gate["passed"]:
            selected, trace = scenario_source._scenario_rank(
                components=components,
                packed=shared.packed_full_230,
                event_counts=shared.inclusive_ge_230_counts,
                means=shared.means,
                lineup_ids=lineup_ids,
                ranking_depth=RANKING_DEPTH,
            )
        fallback_start: int | None = None
        fallback_trace: list[dict[str, object]] = []
        if not gate["passed"] or len(selected) < RANKING_DEPTH:
            fallback_start = len(selected)
            fallback_rank, fallback_trace = (
                successor._block_robust_rank_from_shared_v1(
                    shared=shared,
                    lineup_ids=lineup_ids,
                    training_blocks=training_blocks,
                    depth=RANKING_DEPTH,
                )
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
                    "lineup_id": lineup_ids[candidate],
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
        if (
            len(selected) != RANKING_DEPTH
            or len(set(selected)) != RANKING_DEPTH
            or len(trace) != RANKING_DEPTH
        ):
            _fail("scenario continuation did not produce exact rank 150")
    except scenario_source.CorpusExtremeTailScenarioTicketError as exc:
        raise CorpusR6CurrentBankSelectorRank150V1Error(str(exc)) from exc
    opportunity_counts = [component.q for component in components]
    breadth = Counter(component.breadth for component in components)
    return selected, {
        "ranking_trace_sha256": _sha(trace),
        "rank_80_trace_prefix_sha256": _sha(trace[:80]),
        "rank_100_trace_prefix_sha256": _sha(trace[:100]),
        "rank_150_trace_prefix_sha256": _sha(trace),
        "support_gate": gate,
        "fallback_rank_start": fallback_start,
        "fallback_trace_sha256": _sha(fallback_trace),
        "component_count": len(components),
        "opportunity_world_count": int(sum(opportunity_counts)),
        "component_block_breadth_distribution": [
            {"distinct_fit_block_count": key, "component_count": value}
            for key, value in sorted(breadth.items())
        ],
    }


def _exact_entry_books_v1(
    *,
    ranked_ids: Sequence[str],
    candidate_by_id: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for budget in ENTRY_BUDGETS:
        selected_ids = list(ranked_ids[:budget])
        selected_rosters = [
            list(candidate_by_id[lineup_id]["roster_player_ids"])
            for lineup_id in selected_ids
        ]
        # This is intentionally the exact field/hash law used by the frozen
        # successor's prefix rows.  Consequently the 80 row is byte-identical
        # whenever the deterministic order is unchanged.
        rows.append(_with_hash({
            "prefix_size": budget,
            "selected_lineup_ids": selected_ids,
            "selected_lineup_ids_sha256": _sha(selected_ids),
            "selected_rosters_sha256": _sha(selected_rosters),
        }, field="prefix_sha256"))
    return rows


def run_exact_rank150_continuation_v1(
    *,
    sampled_lineup_ids: object,
    training_score_matrix: object,
    candidate_rows: object,
    training_blocks: object,
    worlds_per_block: object,
    preset_registry: object,
) -> dict[str, object]:
    """Rank once to 150 and return exact 80/100/150 prefix books."""
    try:
        presets = successor.validate_frozen_native_preset_registry_v1(
            preset_registry
        )
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
        )
        if len(lineup_ids) < RANKING_DEPTH:
            _fail("exact rank 150 requires at least 150 sampled lineups")
        shared = successor._build_shared_preprocessing_v1(
            scores=scores,
            training_blocks=blocks,
            worlds_per_block=retained_worlds_per_block,
        )
    except successor.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
        raise CorpusR6CurrentBankSelectorRank150V1Error(str(exc)) from exc

    candidate_by_id = {
        str(candidate["lineup_id"]): candidate for candidate in candidates
    }
    dispatch = {
        "native-convex-excess-expected-max-v1": lambda: (
            _run_convex_rank150_v1(
                scores=scores, lineup_ids=lineup_ids, shared=shared
            )
        ),
        "native-correlation-aware-expected-max-v1": lambda: (
            _run_correlation_rank150_v1(
                scores=scores,
                lineup_ids=lineup_ids,
                training_blocks=blocks,
                worlds_per_block=retained_worlds_per_block,
                shared=shared,
            )
        ),
        "native-support-switched-scenario-ticket-v1": lambda: (
            _run_scenario_rank150_v1(
                lineup_ids=lineup_ids,
                training_blocks=blocks,
                worlds_per_block=retained_worlds_per_block,
                shared=shared,
            )
        ),
    }
    selectors: list[dict[str, object]] = []
    for preset in presets:
        adapter_id = str(preset["adapter_id"])
        if adapter_id not in dispatch:
            _fail("frozen preset adapter is absent from rank-150 dispatcher")
        selected, diagnostics = dispatch[adapter_id]()
        if (
            len(selected) != RANKING_DEPTH
            or len(set(selected)) != RANKING_DEPTH
            or any(index < 0 or index >= len(lineup_ids) for index in selected)
        ):
            _fail(f"{preset['preset_id']} did not return exact rank 150")
        ranked_ids = [lineup_ids[index] for index in selected]
        books = _exact_entry_books_v1(
            ranked_ids=ranked_ids, candidate_by_id=candidate_by_id
        )
        budget_diagnostics = [
            _with_hash({
                "entry_count": budget,
                **successor._common_selected_diagnostics(
                    selected=selected[:budget], scores=scores, shared=shared
                ),
            }, field="diagnostics_sha256")
            for budget in ENTRY_BUDGETS
        ]
        selectors.append(_with_hash({
            "ordinal": preset["ordinal"],
            "preset_id": preset["preset_id"],
            "preset_sha256": preset["preset_sha256"],
            "adapter_id": adapter_id,
            "executable_fingerprint_sha256": preset[
                "executable_fingerprint_sha256"
            ],
            "ranked_canonical_indices": [int(index) for index in selected],
            "ranked_lineup_ids": ranked_ids,
            "ranked_lineup_ids_sha256": _sha(ranked_ids),
            "entry_books": books,
            "entry_book_sha256s": [row["prefix_sha256"] for row in books],
            "budget_diagnostics": budget_diagnostics,
            "continuation_diagnostics": diagnostics,
            "continuation_diagnostics_sha256": _sha(diagnostics),
        }, field="selector_result_sha256"))

    implementation = frozen_rank150_implementation_v1()
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
    return _with_hash({
        "schema_version": RESULT_SCHEMA,
        "implementation": implementation,
        "implementation_sha256": implementation["implementation_sha256"],
        "preset_registry": presets,
        "preset_registry_sha256": _sha(presets),
        "input_binding": input_binding,
        "input_binding_sha256": input_binding["input_binding_sha256"],
        "shared_preprocessing": dict(shared.diagnostics),
        "shared_preprocessing_sha256": _sha(shared.diagnostics),
        "selector_count": len(selectors),
        "selectors": selectors,
        "selector_result_sha256s": [
            selector["selector_result_sha256"] for selector in selectors
        ],
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "exact_prefix_consistency_verified": True,
        "score_extrapolation_performed": False,
        "policy": dict(successor._FALSE_POLICY),
    }, field="result_sha256")


def validate_exact_rank150_continuation_v1(
    value: object,
    *,
    sampled_lineup_ids: object,
    training_score_matrix: object,
    candidate_rows: object,
    training_blocks: object,
    worlds_per_block: object,
    preset_registry: object,
) -> dict[str, object]:
    """Recompute the exact continuation and reject any canonical-byte drift."""
    if not isinstance(value, Mapping):
        _fail("rank-150 result must be one mapping")
    retained = dict(value)
    _canonical(retained)
    expected = run_exact_rank150_continuation_v1(
        sampled_lineup_ids=sampled_lineup_ids,
        training_score_matrix=training_score_matrix,
        candidate_rows=candidate_rows,
        training_blocks=training_blocks,
        worlds_per_block=worlds_per_block,
        preset_registry=preset_registry,
    )
    if _canonical(retained) != _canonical(expected):
        _fail("rank-150 result differs from exact pure replay")
    return expected


__all__ = [
    "CorpusR6CurrentBankSelectorRank150V1Error",
    "ENTRY_BUDGETS",
    "EXPECTED_IMPLEMENTATION_SHA256",
    "IMPLEMENTATION_ID",
    "RANKING_DEPTH",
    "RESULT_SCHEMA",
    "frozen_rank150_implementation_v1",
    "run_exact_rank150_continuation_v1",
    "validate_exact_rank150_continuation_v1",
]
