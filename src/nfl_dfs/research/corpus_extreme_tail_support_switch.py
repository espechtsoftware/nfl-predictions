"""Frozen support switch over the separately versioned T230 raw suite.

This module is a projection layer.  It independently replays an exact support
census and an exact extreme-tail retrieval suite for one reconstructed slate,
then chooses only between two already-materialized suite strategies.  It does
not register or run a selector and it does not modify R6-v2.

Literal inclusive-230 coverage is selected in a held-out fold only when all
four training blocks have nonzero inclusive-230 opportunity and their total is
at least 100.  The all-block final fit uses the same nonzero requirement and a
minimum total of 125.  Otherwise the already-built block-robust bounded ladder
is selected.  The panel summary uses exact integer cross-products for its
frozen 80-percent rule.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_extreme_tail_census as census
from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as suite
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    canonical_json_bytes,
    canonical_sha256,
)


POLICY_SCHEMA: Final = "extreme-tail-support-switched-policy/v1"
SCOPE_SCHEMA: Final = "extreme-tail-support-switched-scope/v1"
BOOK_SELECTION_SCHEMA: Final = "extreme-tail-support-switched-book/v1"
PANEL_SUMMARY_SCHEMA: Final = "extreme-tail-support-nomination-summary/v1"
POLICY_LAW_ID: Final = "frozen-census-support-switch-ge-230/v1"
PANEL_SUMMARY_LAW_ID: Final = "literal-coverage-ge-230-panel-support/v1"

LITERAL_COVERAGE_STRATEGY_ID: Final = "coverage-ge-230-v1"
FALLBACK_STRATEGY_ID: Final = (
    "block-robust-bounded-tail-ge-210-250-v1"
)
FOLD_MINIMUM_OPPORTUNITY_WORLDS: Final = 100
FINAL_MINIMUM_OPPORTUNITY_WORLDS: Final = 125
GENERAL_SUPPORT_NUMERATOR: Final = 4
GENERAL_SUPPORT_DENOMINATOR: Final = 5
AUTHORITATIVE_SLATE_COUNT: Final = 54
AUTHORITATIVE_FOLD_GATE_COUNT: Final = 270
AUTHORITATIVE_FINAL_GATE_COUNT: Final = 54

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
_INPUT_BINDING_KEYS: Final = {
    "reconstruction_sha256",
    "candidate_provenance_sha256",
    "matrix_binding_sha256",
    "score_matrix_sha256",
    "lineup_ids_sha256",
    "world_ids_sha256",
    "score_shape",
}


class CorpusExtremeTailSupportSwitchError(ValueError):
    """A support switch cannot be formed without weakening its frozen law."""


def _fail(message: str) -> None:
    raise CorpusExtremeTailSupportSwitchError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return canonical_json_bytes(value)
    except ValueError as exc:
        raise CorpusExtremeTailSupportSwitchError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _sha(value: object, *, label: str) -> str:
    try:
        return canonical_sha256(value)
    except ValueError as exc:
        raise CorpusExtremeTailSupportSwitchError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_sha256(value: object, *, label: str) -> str:
    if not _is_sha256(value):
        _fail(f"{label} must be one lowercase SHA-256")
    return str(value)


def _exact_keys(
    value: Mapping[str, object], expected: set[str], *, label: str
) -> None:
    if set(value) != expected:
        _fail(f"{label} fields differ")


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    retained = dict(body)
    retained[field] = _sha(retained, label=field)
    return retained


def _validate_self_hash(
    value: Mapping[str, object], field: str, *, label: str
) -> None:
    retained = _require_sha256(value.get(field), label=f"{label} self-hash")
    remainder = {key: item for key, item in value.items() if key != field}
    if _sha(remainder, label=label) != retained:
        _fail(f"{label} self-hash differs")


def _false_authorities(value: Mapping[str, object], *, label: str) -> None:
    for field in _FALSE_AUTHORITY_FIELDS:
        if value.get(field) is not False:
            _fail(f"{label} {field} must be false")


def _gate_law() -> dict[str, object]:
    return {
        "threshold_id": "ge_230",
        "score": 230.0,
        "operator": ">=",
        "requires_every_training_block_nonzero": True,
        "fold_training_block_count": 4,
        "fold_minimum_opportunity_world_count": (
            FOLD_MINIMUM_OPPORTUNITY_WORLDS
        ),
        "final_training_block_count": 5,
        "final_minimum_opportunity_world_count": (
            FINAL_MINIMUM_OPPORTUNITY_WORLDS
        ),
    }


def _switch_law(strategy_hash_by_id: Mapping[str, str]) -> dict[str, object]:
    return {
        "passed_strategy_id": LITERAL_COVERAGE_STRATEGY_ID,
        "passed_strategy_sha256": strategy_hash_by_id[
            LITERAL_COVERAGE_STRATEGY_ID
        ],
        "failed_strategy_id": FALLBACK_STRATEGY_ID,
        "failed_strategy_sha256": strategy_hash_by_id[FALLBACK_STRATEGY_ID],
        "selection_law": (
            "support-gate-pass-selects-literal-coverage-otherwise-selects-"
            "block-robust-bounded-tail"
        ),
        "raw_strategy_registry_is_unchanged": True,
        "raw_selectors_are_not_recomputed_by_this_layer": True,
    }


def _validated_strategy_hashes(
    raw_registry: object,
) -> dict[str, str]:
    registry = _sequence(raw_registry, label="suite strategy registry")
    expected = suite.frozen_extreme_tail_strategies_v1()
    if _canonical(registry, label="suite strategy registry") != _canonical(
        expected, label="frozen suite strategy registry"
    ):
        _fail("suite strategy registry is not the exact frozen four-law registry")
    result = {
        str(row["strategy_id"]): str(row["strategy_sha256"])
        for row in expected
    }
    if set(result) != {
        "coverage-ge-230-v1",
        "bounded-tail-ladder-ge-210-250-v1",
        "block-robust-bounded-tail-ge-210-250-v1",
        "individual-ge-230-rank-v1",
    }:
        _fail("frozen four-law strategy identities differ")
    return result


def _threshold_ge_230(metrics_value: object) -> Mapping[str, object]:
    metrics = _mapping(metrics_value, label="training opportunity metrics")
    matches = [
        _mapping(item, label="training threshold metric")
        for item in _sequence(metrics.get("thresholds"), label="threshold metrics")
        if _mapping(item, label="training threshold metric").get("label")
        == "ge_230"
    ]
    if len(matches) != 1:
        _fail("training metrics lack exactly one ge_230 threshold")
    threshold = matches[0]
    if (
        threshold.get("label") != "ge_230"
        or type(threshold.get("threshold")) is not float
        or threshold.get("threshold") != 230.0
        or threshold.get("operator") != ">="
    ):
        _fail("ge_230 threshold/operator differs from the frozen inclusive law")
    return threshold


def _gate_from_metrics(
    metrics_value: object,
    *,
    training_blocks: Sequence[str],
    minimum: int,
    scope_kind: str,
) -> dict[str, object]:
    metrics = _mapping(metrics_value, label="training opportunity metrics")
    blocks = list(training_blocks)
    if (
        metrics.get("blocks") != blocks
        or type(metrics.get("worlds_per_block")) is not int
        or int(metrics["worlds_per_block"]) < 1
        or metrics.get("world_count")
        != len(blocks) * int(metrics["worlds_per_block"])
        or metrics.get("ordinary_unweighted_r_worlds") is not True
        or metrics.get("uses_realized_outcomes") is not False
    ):
        _fail("training opportunity metric block/world law differs")
    threshold = _threshold_ge_230(metrics)
    raw_by_block = _sequence(
        threshold.get("by_block"), label="ge_230 metrics by block"
    )
    if len(raw_by_block) != len(blocks):
        _fail("ge_230 block metric count differs")
    counts: list[dict[str, object]] = []
    width = int(metrics["worlds_per_block"])
    for block, raw in zip(blocks, raw_by_block, strict=True):
        row = _mapping(raw, label=f"ge_230 metric for {block}")
        count = row.get("opportunity_world_count")
        if (
            row.get("block_id") != block
            or row.get("label") != "ge_230"
            or type(row.get("threshold")) is not float
            or row.get("threshold") != 230.0
            or row.get("operator") != ">="
            or row.get("world_count") != width
            or type(count) is not int
            or not 0 <= count <= width
        ):
            _fail("ge_230 per-block opportunity fact differs")
        counts.append({"block_id": block, "opportunity_world_count": count})
    total = threshold.get("opportunity_world_count")
    if (
        type(total) is not int
        or total < 0
        or total != sum(int(row["opportunity_world_count"]) for row in counts)
    ):
        _fail("aggregate ge_230 opportunity count differs from its blocks")
    zero_blocks = [
        str(row["block_id"])
        for row in counts
        if row["opportunity_world_count"] == 0
    ]
    every_nonzero = not zero_blocks
    passed = every_nonzero and total >= minimum
    failure_reasons: list[str] = []
    if not every_nonzero:
        failure_reasons.append(
            "one-or-more-training-blocks-have-zero-ge-230-opportunity"
        )
    if total < minimum:
        failure_reasons.append(
            "aggregate-training-ge-230-opportunity-below-frozen-minimum"
        )
    return {
        "scope_kind": scope_kind,
        "threshold_id": "ge_230",
        "threshold": 230.0,
        "operator": ">=",
        "training_blocks": blocks,
        "per_block_opportunity_world_counts": counts,
        "zero_opportunity_training_blocks": zero_blocks,
        "every_training_block_nonzero": every_nonzero,
        "training_opportunity_world_count": total,
        "minimum_training_opportunity_world_count": minimum,
        "aggregate_comparison_operator": ">=",
        "passed": passed,
        "failure_reasons": failure_reasons,
        "decision_reason": (
            "support-gate-passed-select-literal-coverage"
            if passed
            else "support-gate-failed-select-block-robust-bounded-tail"
        ),
    }


def _one_by(
    values: object, *, key: str, expected: object, label: str
) -> Mapping[str, object]:
    matches = [
        _mapping(item, label=label)
        for item in _sequence(values, label=f"{label}s")
        if _mapping(item, label=label).get(key) == expected
    ]
    if len(matches) != 1:
        _fail(f"expected exactly one {label} with {key}={expected!r}")
    return matches[0]


def _source_membership(
    *,
    universe: Mapping[str, object],
    fit_scope: Mapping[str, object],
    heldout_block: str | None,
    training_blocks: Sequence[str],
    reconstruction_sha256: str,
    candidate_provenance_sha256: str,
) -> dict[str, object]:
    expected_scope_id = (
        "all-block-final-fit"
        if heldout_block is None
        else f"holdout-{heldout_block}"
    )
    view = _mapping(fit_scope.get("candidate_view"), label="suite candidate view")
    admission = _mapping(fit_scope.get("admission"), label="suite admission")
    admitted_ids = [
        str(item)
        for item in _sequence(
            admission.get("admitted_lineup_ids"), label="admitted lineup IDs"
        )
    ]
    lineup_hash = _sha(admitted_ids, label="admitted lineup IDs")
    metrics = _mapping(
        universe.get("training_metrics"), label="census training metrics"
    )
    if (
        fit_scope.get("fit_scope_id") != expected_scope_id
        or view.get("fit_scope_id") != expected_scope_id
        or admission.get("fit_scope_id") != expected_scope_id
        or universe.get("heldout_block") != heldout_block
        or fit_scope.get("heldout_block") != heldout_block
        or view.get("heldout_block") != heldout_block
        or universe.get("training_blocks") != list(training_blocks)
        or fit_scope.get("training_blocks") != list(training_blocks)
        or view.get("training_blocks") != list(training_blocks)
        or universe.get("lineup_count") != len(admitted_ids)
        or admission.get("admitted_count") != len(admitted_ids)
        or view.get("eligible_count") != len(admitted_ids)
        or universe.get("lineup_ids_sha256") != lineup_hash
        or metrics.get("lineup_ids_sha256") != lineup_hash
        or fit_scope.get("reconstruction_sha256") != reconstruction_sha256
        or fit_scope.get("candidate_provenance_sha256")
        != candidate_provenance_sha256
        or admission.get("selection_provenance_sha256")
        != view.get("selection_provenance_sha256")
        or admitted_ids != sorted(set(admitted_ids))
        or len(admitted_ids) < suite.RANKING_DEPTH
    ):
        _fail("census/suite fold membership or input identity differs")
    if heldout_block is None:
        if (
            universe.get("fit_candidate_view_sha256") is not None
            or universe.get("selection_provenance_sha256") is not None
        ):
            _fail("all-block census unexpectedly claims a fold-local view")
    elif (
        universe.get("fit_candidate_view_sha256")
        != view.get("fit_candidate_view_sha256")
        or universe.get("selection_provenance_sha256")
        != view.get("selection_provenance_sha256")
    ):
        _fail("held-out fold candidate-view/provenance identity differs")
    return {
        "lineup_count": len(admitted_ids),
        "lineup_ids_sha256": lineup_hash,
        "census_fit_candidate_view_sha256": universe.get(
            "fit_candidate_view_sha256"
        ),
        "census_selection_provenance_sha256": universe.get(
            "selection_provenance_sha256"
        ),
        "suite_fit_candidate_view_sha256": view.get(
            "fit_candidate_view_sha256"
        ),
        "suite_selection_provenance_sha256": view.get(
            "selection_provenance_sha256"
        ),
        "admission_id": admission.get("admission_id"),
        "admission_sha256": admission.get("admission_sha256"),
        "training_score_matrix_sha256": fit_scope.get(
            "training_score_matrix_sha256"
        ),
    }


def _project_book(
    *,
    fit_scope: Mapping[str, object],
    strategy_id: str,
    strategy_sha256: str,
    entry_budget: int,
    heldout_block: str | None,
    training_blocks: Sequence[str],
    reconstruction_sha256: str,
    lineup_ids_sha256: str,
) -> dict[str, object]:
    raw_books = _sequence(fit_scope.get("books"), label="suite books")
    matches = [
        _mapping(item, label="suite book")
        for item in raw_books
        if _mapping(item, label="suite book").get("strategy_id") == strategy_id
        and _mapping(item, label="suite book").get("entry_budget") == entry_budget
    ]
    if len(matches) != 1:
        _fail("selected strategy lacks one exact 4/14/80 suite book")
    book = matches[0]
    expected_semantics = [
        {"label": label, "threshold": threshold, "operator": operator}
        for label, threshold, operator in suite.TAIL_THRESHOLDS
    ]
    selected_ids = list(
        _sequence(book.get("selected_lineup_ids"), label="selected lineup IDs")
    )
    selected_local = list(
        _sequence(book.get("selected_local_indices"), label="selected local indices")
    )
    selected_global = list(
        _sequence(
            book.get("selected_global_indices"), label="selected global indices"
        )
    )
    trace = list(_sequence(book.get("marginal_trace"), label="marginal trace"))
    if (
        book.get("fit_scope_id") != fit_scope.get("fit_scope_id")
        or book.get("reconstruction_sha256") != reconstruction_sha256
        or book.get("training_blocks") != list(training_blocks)
        or book.get("heldout_block") != heldout_block
        or book.get("strategy_sha256") != strategy_sha256
        or book.get("ranking_depth") != suite.RANKING_DEPTH
        or book.get("ranking_prefix_law")
        != "exact-prefix-of-one-deterministic-rank-80"
        or book.get("input_lineup_ids_sha256") != lineup_ids_sha256
        or book.get("entry_count") != entry_budget
        or len(selected_ids) != entry_budget
        or len(set(selected_ids)) != entry_budget
        or len(selected_local) != entry_budget
        or len(set(selected_local)) != entry_budget
        or len(selected_global) != entry_budget
        or len(set(selected_global)) != entry_budget
        or any(type(item) is not int or item < 0 for item in selected_local)
        or any(type(item) is not int or item < 0 for item in selected_global)
        or len(trace) != entry_budget
        or book.get("threshold_semantics") != expected_semantics
    ):
        _fail("selected suite book identity/exact-N/threshold law differs")
    for rank, (lineup_id, raw_trace) in enumerate(
        zip(selected_ids, trace, strict=True)
    ):
        trace_row = _mapping(raw_trace, label=f"marginal trace[{rank}]")
        if (
            trace_row.get("selection_rank") != rank
            or trace_row.get("lineup_id") != lineup_id
            or trace_row.get("admitted_lineup_index") != selected_local[rank]
            or trace_row.get("global_lineup_index") != selected_global[rank]
        ):
            _fail("selected suite book marginal trace identity differs")
    _require_sha256(book.get("book_sha256"), label="source book SHA-256")
    body = {
        "schema_version": BOOK_SELECTION_SCHEMA,
        "source_book_id": book.get("book_id"),
        "source_book_sha256": book.get("book_sha256"),
        "strategy_id": strategy_id,
        "strategy_sha256": strategy_sha256,
        "entry_budget": entry_budget,
        "entry_count": entry_budget,
        "selected_local_indices": selected_local,
        "selected_global_indices": selected_global,
        "selected_lineup_ids": selected_ids,
        "selected_lineup_ids_sha256": _sha(
            selected_ids, label="selected lineup IDs"
        ),
        "marginal_trace": trace,
        "marginal_trace_sha256": _sha(trace, label="marginal trace"),
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "book_selection_sha256")


def _build_scope(
    *,
    universe: Mapping[str, object],
    fit_scope: Mapping[str, object],
    heldout_block: str | None,
    training_blocks: Sequence[str],
    minimum: int,
    scope_kind: str,
    reconstruction_sha256: str,
    candidate_provenance_sha256: str,
    strategy_hash_by_id: Mapping[str, str],
    fold_observation: Mapping[str, object] | None,
) -> dict[str, object]:
    membership = _source_membership(
        universe=universe,
        fit_scope=fit_scope,
        heldout_block=heldout_block,
        training_blocks=training_blocks,
        reconstruction_sha256=reconstruction_sha256,
        candidate_provenance_sha256=candidate_provenance_sha256,
    )
    gate = _gate_from_metrics(
        universe.get("training_metrics"),
        training_blocks=training_blocks,
        minimum=minimum,
        scope_kind=scope_kind,
    )
    if fold_observation is not None:
        expected_observation = {
            "heldout_block": heldout_block,
            "training_blocks": list(training_blocks),
            "every_training_block_nonzero": gate[
                "every_training_block_nonzero"
            ],
            "training_opportunity_world_count": gate[
                "training_opportunity_world_count"
            ],
            "nomination_support_passed": gate["passed"],
        }
        if _canonical(
            fold_observation, label="census fold gate observation"
        ) != _canonical(expected_observation, label="replayed fold observation"):
            _fail("census fold gate observation differs from exact metrics")
    strategy_id = (
        LITERAL_COVERAGE_STRATEGY_ID if gate["passed"] else FALLBACK_STRATEGY_ID
    )
    strategy_sha256 = strategy_hash_by_id[strategy_id]
    books = [
        _project_book(
            fit_scope=fit_scope,
            strategy_id=strategy_id,
            strategy_sha256=strategy_sha256,
            entry_budget=budget,
            heldout_block=heldout_block,
            training_blocks=training_blocks,
            reconstruction_sha256=reconstruction_sha256,
            lineup_ids_sha256=str(membership["lineup_ids_sha256"]),
        )
        for budget in suite.ENTRY_BUDGETS
    ]
    body = {
        "schema_version": SCOPE_SCHEMA,
        "scope_kind": scope_kind,
        "fit_scope_id": fit_scope.get("fit_scope_id"),
        "heldout_block": heldout_block,
        "training_blocks": list(training_blocks),
        "source_universe_id": universe.get("universe_id"),
        "source_universe_sha256": universe.get("universe_sha256"),
        "source_fit_scope_sha256": fit_scope.get("fit_scope_sha256"),
        "membership_binding": membership,
        "support_gate": gate,
        "selected_strategy_id": strategy_id,
        "selected_strategy_sha256": strategy_sha256,
        "entry_budgets": list(suite.ENTRY_BUDGETS),
        "selected_book_count": len(books),
        "selected_books": books,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "support_switch_scope_sha256")


def _validated_source_pair(
    *,
    support_census: Mapping[str, object],
    extreme_tail_suite: Mapping[str, object],
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    world_ids: Sequence[Mapping[str, object]],
    worlds_per_block: int | None,
    require_authoritative: bool,
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        validated_census = census.validate_extreme_tail_support_census(
            support_census,
            provenance=provenance,
            union_scores=union_scores,
            reconstruction_receipt=reconstruction_receipt,
            world_ids=world_ids,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
        )
    except census.CorpusExtremeTailCensusError as exc:
        raise CorpusExtremeTailSupportSwitchError(
            f"support census replay failed: {exc}"
        ) from exc
    try:
        validated_suite = suite.validate_extreme_tail_retrieval_suite_v1(
            extreme_tail_suite,
            provenance=provenance,
            union_scores=union_scores,
            reconstruction_receipt=reconstruction_receipt,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
        )
    except suite.CorpusExtremeTailRetrievalSuiteError as exc:
        raise CorpusExtremeTailSupportSwitchError(
            f"extreme-tail suite replay failed: {exc}"
        ) from exc
    census_binding = _mapping(
        validated_census.get("input_binding"), label="census input binding"
    )
    suite_binding = _mapping(
        validated_suite.get("input_binding"), label="suite input binding"
    )
    if (
        set(census_binding) != _INPUT_BINDING_KEYS
        or set(suite_binding) != _INPUT_BINDING_KEYS
        or _canonical(census_binding, label="census input binding")
        != _canonical(suite_binding, label="suite input binding")
        or _canonical(validated_census.get("slate"), label="census slate")
        != _canonical(validated_suite.get("slate"), label="suite slate")
        or validated_census.get("world_basis", {}).get("worlds_per_block")
        != validated_suite.get("worlds_per_block")
        or validated_census.get("dose_authority")
        != validated_suite.get("dose_authority")
        or validated_census.get("require_authoritative")
        is not require_authoritative
        or validated_suite.get("require_authoritative")
        is not require_authoritative
    ):
        _fail("support census and extreme-tail suite input bindings differ")
    expected_thresholds = [
        {"threshold_id": label, "score": threshold, "operator": operator}
        for label, threshold, operator in census.THRESHOLDS
    ]
    if validated_census.get("threshold_registry") != expected_thresholds:
        _fail("support census threshold registry differs")
    _require_sha256(
        validated_census.get("support_census_sha256"),
        label="support census SHA-256",
    )
    _require_sha256(
        validated_suite.get("suite_sha256"), label="extreme-tail suite SHA-256"
    )
    return validated_census, validated_suite


def build_extreme_tail_support_switched_policy_v1(
    *,
    support_census: Mapping[str, object],
    extreme_tail_suite: Mapping[str, object],
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    world_ids: Sequence[Mapping[str, object]],
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Replay both source receipts and project the frozen switched books."""
    if type(require_authoritative) is not bool:
        _fail("require_authoritative must be an exact boolean")
    validated_census, validated_suite = _validated_source_pair(
        support_census=support_census,
        extreme_tail_suite=extreme_tail_suite,
        provenance=provenance,
        union_scores=union_scores,
        reconstruction_receipt=reconstruction_receipt,
        world_ids=world_ids,
        worlds_per_block=worlds_per_block,
        require_authoritative=require_authoritative,
    )
    strategy_hash_by_id = _validated_strategy_hashes(
        validated_suite.get("strategy_registry")
    )
    census_gate = _mapping(
        validated_census.get("coverage_ge_230_support_gate"),
        label="census coverage gate",
    )
    if (
        census_gate.get("requires_every_training_block_nonzero") is not True
        or census_gate.get("minimum_training_opportunity_world_count")
        != FOLD_MINIMUM_OPPORTUNITY_WORLDS
    ):
        _fail("census fold support law differs from the frozen switch")
    observations = _sequence(
        census_gate.get("fold_observations"), label="census fold observations"
    )
    if len(observations) != len(rw.WORLD_BLOCKS):
        _fail("census does not contain the exact five fold gates")
    folds: list[dict[str, object]] = []
    suite_folds = _sequence(validated_suite.get("folds"), label="suite folds")
    if len(suite_folds) != len(rw.WORLD_BLOCKS):
        _fail("suite does not contain the exact five folds")
    input_binding = dict(
        _mapping(validated_census["input_binding"], label="input binding")
    )
    reconstruction_sha256 = str(input_binding["reconstruction_sha256"])
    candidate_provenance_sha256 = str(
        input_binding["candidate_provenance_sha256"]
    )
    for ordinal, heldout in enumerate(rw.WORLD_BLOCKS):
        training_blocks = [block for block in rw.WORLD_BLOCKS if block != heldout]
        universe = _one_by(
            validated_census.get("universes"),
            key="universe_id",
            expected=f"cross-arm-fold-eligible:holdout-{heldout}",
            label="census universe",
        )
        fit_scope = _mapping(suite_folds[ordinal], label=f"suite fold[{ordinal}]")
        observation = _mapping(
            observations[ordinal], label=f"census fold observation[{ordinal}]"
        )
        folds.append(_build_scope(
            universe=universe,
            fit_scope=fit_scope,
            heldout_block=heldout,
            training_blocks=training_blocks,
            minimum=FOLD_MINIMUM_OPPORTUNITY_WORLDS,
            scope_kind="cross-fit",
            reconstruction_sha256=reconstruction_sha256,
            candidate_provenance_sha256=candidate_provenance_sha256,
            strategy_hash_by_id=strategy_hash_by_id,
            fold_observation=observation,
        ))
    final_universe = _one_by(
        validated_census.get("universes"),
        key="universe_id",
        expected="cross-arm-all-block-union",
        label="census universe",
    )
    final_scope = _mapping(
        validated_suite.get("final_fit"), label="suite final fit"
    )
    final_fit = _build_scope(
        universe=final_universe,
        fit_scope=final_scope,
        heldout_block=None,
        training_blocks=list(rw.WORLD_BLOCKS),
        minimum=FINAL_MINIMUM_OPPORTUNITY_WORLDS,
        scope_kind="final-fit",
        reconstruction_sha256=reconstruction_sha256,
        candidate_provenance_sha256=candidate_provenance_sha256,
        strategy_hash_by_id=strategy_hash_by_id,
        fold_observation=None,
    )
    source_receipts = {
        "support_census_schema_version": census.CENSUS_SCHEMA,
        "support_census_sha256": validated_census["support_census_sha256"],
        "support_census_input_binding_sha256": _sha(
            validated_census["input_binding"], label="census input binding"
        ),
        "extreme_tail_suite_schema_version": suite.SUITE_SCHEMA,
        "extreme_tail_suite_sha256": validated_suite["suite_sha256"],
        "extreme_tail_suite_input_binding_sha256": _sha(
            validated_suite["input_binding"], label="suite input binding"
        ),
    }
    source_receipts["source_pair_sha256"] = _sha(
        source_receipts, label="source receipt pair"
    )
    width = int(validated_suite["worlds_per_block"])
    body = {
        "schema_version": POLICY_SCHEMA,
        "policy_law_id": POLICY_LAW_ID,
        "slate": validated_census["slate"],
        "input_binding": input_binding,
        "source_receipts": source_receipts,
        "gate_law": _gate_law(),
        "strategy_switch_law": _switch_law(strategy_hash_by_id),
        "strategy_registry_sha256": validated_suite[
            "strategy_registry_sha256"
        ],
        "entry_budgets": list(suite.ENTRY_BUDGETS),
        "ranking_depth": suite.RANKING_DEPTH,
        "folds": folds,
        "final_fit": final_fit,
        "fold_gate_count": len(folds),
        "final_fit_gate_count": 1,
        "selected_book_count": sum(
            int(scope["selected_book_count"]) for scope in [*folds, final_fit]
        ),
        "worlds_per_block": width,
        "dose_authority": validated_suite["dose_authority"],
        "require_authoritative": require_authoritative,
        "selection_is_projection_of_validated_suite_books": True,
        "final_fit_is_distinct_all_block_refit": True,
        "ordinary_unweighted_r_worlds": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "support_switched_policy_sha256")


def validate_extreme_tail_support_switched_policy_v1(
    value: Mapping[str, object],
    *,
    support_census: Mapping[str, object],
    extreme_tail_suite: Mapping[str, object],
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    world_ids: Sequence[Mapping[str, object]],
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Replay sources and the complete switched receipt byte-for-byte."""
    retained = _mapping(value, label="retained support-switched policy")
    expected = build_extreme_tail_support_switched_policy_v1(
        support_census=support_census,
        extreme_tail_suite=extreme_tail_suite,
        provenance=provenance,
        union_scores=union_scores,
        reconstruction_receipt=reconstruction_receipt,
        world_ids=world_ids,
        worlds_per_block=worlds_per_block,
        require_authoritative=require_authoritative,
    )
    if _canonical(retained, label="retained support-switched policy") != _canonical(
        expected, label="replayed support-switched policy"
    ):
        _fail("retained support-switched policy canonical replay differs")
    return expected


def _validate_book_selection_structure(
    value: object,
    *,
    expected_strategy_id: str,
    expected_strategy_sha256: str,
    expected_budget: int,
) -> Mapping[str, object]:
    book = _mapping(value, label="selected book projection")
    expected_keys = {
        "schema_version",
        "source_book_id",
        "source_book_sha256",
        "strategy_id",
        "strategy_sha256",
        "entry_budget",
        "entry_count",
        "selected_local_indices",
        "selected_global_indices",
        "selected_lineup_ids",
        "selected_lineup_ids_sha256",
        "marginal_trace",
        "marginal_trace_sha256",
        *_FALSE_AUTHORITY_FIELDS,
        "book_selection_sha256",
    }
    _exact_keys(book, expected_keys, label="selected book projection")
    selected_ids = list(
        _sequence(book.get("selected_lineup_ids"), label="selected lineup IDs")
    )
    local = list(
        _sequence(book.get("selected_local_indices"), label="selected local indices")
    )
    global_indices = list(
        _sequence(
            book.get("selected_global_indices"), label="selected global indices"
        )
    )
    trace = list(_sequence(book.get("marginal_trace"), label="marginal trace"))
    if (
        book.get("schema_version") != BOOK_SELECTION_SCHEMA
        or book.get("strategy_id") != expected_strategy_id
        or book.get("strategy_sha256") != expected_strategy_sha256
        or book.get("entry_budget") != expected_budget
        or book.get("entry_count") != expected_budget
        or len(selected_ids) != expected_budget
        or len(set(selected_ids)) != expected_budget
        or len(local) != expected_budget
        or len(set(local)) != expected_budget
        or len(global_indices) != expected_budget
        or len(set(global_indices)) != expected_budget
        or any(type(item) is not int or item < 0 for item in local)
        or any(type(item) is not int or item < 0 for item in global_indices)
        or len(trace) != expected_budget
        or book.get("selected_lineup_ids_sha256")
        != _sha(selected_ids, label="selected lineup IDs")
        or book.get("marginal_trace_sha256") != _sha(trace, label="marginal trace")
    ):
        _fail("selected book projection identity/exact-N binding differs")
    _require_sha256(book.get("source_book_sha256"), label="source book SHA-256")
    for rank, (lineup_id, raw_trace) in enumerate(
        zip(selected_ids, trace, strict=True)
    ):
        row = _mapping(raw_trace, label=f"marginal trace[{rank}]")
        if (
            row.get("selection_rank") != rank
            or row.get("lineup_id") != lineup_id
            or row.get("admitted_lineup_index") != local[rank]
            or row.get("global_lineup_index") != global_indices[rank]
        ):
            _fail("selected book projection trace differs")
    _false_authorities(book, label="selected book projection")
    _validate_self_hash(book, "book_selection_sha256", label="book projection")
    return book


def _validate_gate_structure(
    value: object,
    *,
    expected_blocks: Sequence[str],
    expected_minimum: int,
    expected_kind: str,
    worlds_per_block: int,
) -> Mapping[str, object]:
    gate = _mapping(value, label="support gate")
    rows = _sequence(
        gate.get("per_block_opportunity_world_counts"),
        label="per-block opportunity counts",
    )
    if len(rows) != len(expected_blocks):
        _fail("support gate block count differs")
    counts: list[dict[str, object]] = []
    for block, raw in zip(expected_blocks, rows, strict=True):
        row = _mapping(raw, label="per-block opportunity count")
        _exact_keys(
            row,
            {"block_id", "opportunity_world_count"},
            label="per-block opportunity count",
        )
        count = row.get("opportunity_world_count")
        if (
            row.get("block_id") != block
            or type(count) is not int
            or not 0 <= count <= worlds_per_block
        ):
            _fail("support gate per-block count differs")
        counts.append({"block_id": block, "opportunity_world_count": count})
    total = sum(int(row["opportunity_world_count"]) for row in counts)
    zero = [
        str(row["block_id"])
        for row in counts
        if row["opportunity_world_count"] == 0
    ]
    passed = not zero and total >= expected_minimum
    expected_reasons = []
    if zero:
        expected_reasons.append(
            "one-or-more-training-blocks-have-zero-ge-230-opportunity"
        )
    if total < expected_minimum:
        expected_reasons.append(
            "aggregate-training-ge-230-opportunity-below-frozen-minimum"
        )
    expected = {
        "scope_kind": expected_kind,
        "threshold_id": "ge_230",
        "threshold": 230.0,
        "operator": ">=",
        "training_blocks": list(expected_blocks),
        "per_block_opportunity_world_counts": counts,
        "zero_opportunity_training_blocks": zero,
        "every_training_block_nonzero": not zero,
        "training_opportunity_world_count": total,
        "minimum_training_opportunity_world_count": expected_minimum,
        "aggregate_comparison_operator": ">=",
        "passed": passed,
        "failure_reasons": expected_reasons,
        "decision_reason": (
            "support-gate-passed-select-literal-coverage"
            if passed
            else "support-gate-failed-select-block-robust-bounded-tail"
        ),
    }
    if _canonical(gate, label="support gate") != _canonical(
        expected, label="replayed support gate"
    ):
        _fail("support gate threshold/operator/facts differ")
    return gate


def _validate_scope_structure(
    value: object,
    *,
    heldout_block: str | None,
    strategy_hash_by_id: Mapping[str, str],
    worlds_per_block: int,
) -> Mapping[str, object]:
    scope = _mapping(value, label="support-switched scope")
    expected_keys = {
        "schema_version",
        "scope_kind",
        "fit_scope_id",
        "heldout_block",
        "training_blocks",
        "source_universe_id",
        "source_universe_sha256",
        "source_fit_scope_sha256",
        "membership_binding",
        "support_gate",
        "selected_strategy_id",
        "selected_strategy_sha256",
        "entry_budgets",
        "selected_book_count",
        "selected_books",
        *_FALSE_AUTHORITY_FIELDS,
        "support_switch_scope_sha256",
    }
    _exact_keys(scope, expected_keys, label="support-switched scope")
    expected_blocks = [block for block in rw.WORLD_BLOCKS if block != heldout_block]
    kind = "final-fit" if heldout_block is None else "cross-fit"
    minimum = (
        FINAL_MINIMUM_OPPORTUNITY_WORLDS
        if heldout_block is None
        else FOLD_MINIMUM_OPPORTUNITY_WORLDS
    )
    expected_scope_id = (
        "all-block-final-fit"
        if heldout_block is None
        else f"holdout-{heldout_block}"
    )
    expected_universe_id = (
        "cross-arm-all-block-union"
        if heldout_block is None
        else f"cross-arm-fold-eligible:holdout-{heldout_block}"
    )
    gate = _validate_gate_structure(
        scope.get("support_gate"),
        expected_blocks=expected_blocks,
        expected_minimum=minimum,
        expected_kind=kind,
        worlds_per_block=worlds_per_block,
    )
    selected_strategy_id = (
        LITERAL_COVERAGE_STRATEGY_ID if gate["passed"] else FALLBACK_STRATEGY_ID
    )
    selected_strategy_sha256 = strategy_hash_by_id[selected_strategy_id]
    membership = _mapping(
        scope.get("membership_binding"), label="scope membership binding"
    )
    _exact_keys(
        membership,
        {
            "lineup_count",
            "lineup_ids_sha256",
            "census_fit_candidate_view_sha256",
            "census_selection_provenance_sha256",
            "suite_fit_candidate_view_sha256",
            "suite_selection_provenance_sha256",
            "admission_id",
            "admission_sha256",
            "training_score_matrix_sha256",
        },
        label="scope membership binding",
    )
    if (
        scope.get("schema_version") != SCOPE_SCHEMA
        or scope.get("scope_kind") != kind
        or scope.get("fit_scope_id") != expected_scope_id
        or scope.get("heldout_block") != heldout_block
        or scope.get("training_blocks") != expected_blocks
        or scope.get("source_universe_id") != expected_universe_id
        or scope.get("selected_strategy_id") != selected_strategy_id
        or scope.get("selected_strategy_sha256") != selected_strategy_sha256
        or scope.get("entry_budgets") != list(suite.ENTRY_BUDGETS)
        or scope.get("selected_book_count") != len(suite.ENTRY_BUDGETS)
        or type(membership.get("lineup_count")) is not int
        or int(membership["lineup_count"]) < suite.RANKING_DEPTH
    ):
        _fail("support-switched scope identity/choice differs")
    for field in (
        "lineup_ids_sha256",
        "suite_fit_candidate_view_sha256",
        "suite_selection_provenance_sha256",
        "admission_sha256",
        "training_score_matrix_sha256",
    ):
        _require_sha256(membership.get(field), label=f"membership {field}")
    if heldout_block is None:
        if (
            membership.get("census_fit_candidate_view_sha256") is not None
            or membership.get("census_selection_provenance_sha256") is not None
        ):
            _fail("final-fit census fold identity must be null")
    else:
        if (
            membership.get("census_fit_candidate_view_sha256")
            != membership.get("suite_fit_candidate_view_sha256")
            or membership.get("census_selection_provenance_sha256")
            != membership.get("suite_selection_provenance_sha256")
        ):
            _fail("fold census/suite membership identity differs")
    _require_sha256(scope.get("source_universe_sha256"), label="universe SHA-256")
    _require_sha256(scope.get("source_fit_scope_sha256"), label="scope SHA-256")
    books = _sequence(scope.get("selected_books"), label="selected books")
    if len(books) != len(suite.ENTRY_BUDGETS):
        _fail("scope lacks exact 4/14/80 selected books")
    for raw_book, budget in zip(books, suite.ENTRY_BUDGETS, strict=True):
        _validate_book_selection_structure(
            raw_book,
            expected_strategy_id=selected_strategy_id,
            expected_strategy_sha256=selected_strategy_sha256,
            expected_budget=budget,
        )
    _false_authorities(scope, label="support-switched scope")
    _validate_self_hash(
        scope, "support_switch_scope_sha256", label="support-switched scope"
    )
    return scope


def _validate_policy_structure(value: object) -> Mapping[str, object]:
    policy = _mapping(value, label="support-switched policy")
    expected_keys = {
        "schema_version",
        "policy_law_id",
        "slate",
        "input_binding",
        "source_receipts",
        "gate_law",
        "strategy_switch_law",
        "strategy_registry_sha256",
        "entry_budgets",
        "ranking_depth",
        "folds",
        "final_fit",
        "fold_gate_count",
        "final_fit_gate_count",
        "selected_book_count",
        "worlds_per_block",
        "dose_authority",
        "require_authoritative",
        "selection_is_projection_of_validated_suite_books",
        "final_fit_is_distinct_all_block_refit",
        "ordinary_unweighted_r_worlds",
        *_FALSE_AUTHORITY_FIELDS,
        "support_switched_policy_sha256",
    }
    _exact_keys(policy, expected_keys, label="support-switched policy")
    _canonical(policy, label="support-switched policy")
    input_binding = _mapping(policy.get("input_binding"), label="input binding")
    _exact_keys(input_binding, _INPUT_BINDING_KEYS, label="input binding")
    for field in _INPUT_BINDING_KEYS - {"score_shape"}:
        _require_sha256(input_binding.get(field), label=f"input binding {field}")
    score_shape = _sequence(input_binding.get("score_shape"), label="score shape")
    if (
        len(score_shape) != 2
        or any(type(item) is not int or item < 1 for item in score_shape)
    ):
        _fail("input score shape differs")
    worlds_per_block = policy.get("worlds_per_block")
    require_authoritative = policy.get("require_authoritative")
    if (
        type(worlds_per_block) is not int
        or worlds_per_block < 1
        or type(require_authoritative) is not bool
        or score_shape[1] != len(rw.WORLD_BLOCKS) * worlds_per_block
        or (
            require_authoritative
            and worlds_per_block != rw.WORLDS_PER_BLOCK
        )
        or policy.get("dose_authority")
        != (
            runner.AUTHORITATIVE_DOSE
            if require_authoritative
            else runner.FIXTURE_DOSE
        )
    ):
        _fail("policy dose authority/world width/score shape differs")
    strategy_hash_by_id = _validated_strategy_hashes(
        suite.frozen_extreme_tail_strategies_v1()
    )
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("policy_law_id") != POLICY_LAW_ID
        or policy.get("gate_law") != _gate_law()
        or policy.get("strategy_switch_law")
        != _switch_law(strategy_hash_by_id)
        or policy.get("strategy_registry_sha256")
        != _sha(
            suite.frozen_extreme_tail_strategies_v1(),
            label="frozen strategy registry",
        )
        or policy.get("entry_budgets") != list(suite.ENTRY_BUDGETS)
        or policy.get("ranking_depth") != suite.RANKING_DEPTH
        or policy.get("fold_gate_count") != len(rw.WORLD_BLOCKS)
        or policy.get("final_fit_gate_count") != 1
        or policy.get("selected_book_count")
        != (len(rw.WORLD_BLOCKS) + 1) * len(suite.ENTRY_BUDGETS)
        or policy.get("selection_is_projection_of_validated_suite_books")
        is not True
        or policy.get("final_fit_is_distinct_all_block_refit") is not True
        or policy.get("ordinary_unweighted_r_worlds") is not True
    ):
        _fail("support-switched policy frozen law differs")
    slate = _mapping(policy.get("slate"), label="policy slate")
    if type(slate.get("slate_id")) is not str or not slate.get("slate_id"):
        _fail("policy slate identity differs")
    sources = _mapping(policy.get("source_receipts"), label="source receipts")
    _exact_keys(
        sources,
        {
            "support_census_schema_version",
            "support_census_sha256",
            "support_census_input_binding_sha256",
            "extreme_tail_suite_schema_version",
            "extreme_tail_suite_sha256",
            "extreme_tail_suite_input_binding_sha256",
            "source_pair_sha256",
        },
        label="source receipts",
    )
    if (
        sources.get("support_census_schema_version") != census.CENSUS_SCHEMA
        or sources.get("extreme_tail_suite_schema_version") != suite.SUITE_SCHEMA
        or sources.get("support_census_input_binding_sha256")
        != _sha(input_binding, label="input binding")
        or sources.get("extreme_tail_suite_input_binding_sha256")
        != _sha(input_binding, label="input binding")
    ):
        _fail("source receipt schema/input binding differs")
    for field in (
        "support_census_sha256",
        "support_census_input_binding_sha256",
        "extreme_tail_suite_sha256",
        "extreme_tail_suite_input_binding_sha256",
    ):
        _require_sha256(sources.get(field), label=f"source receipts {field}")
    source_remainder = {
        key: item for key, item in sources.items() if key != "source_pair_sha256"
    }
    if sources.get("source_pair_sha256") != _sha(
        source_remainder, label="source receipt pair"
    ):
        _fail("source receipt pair self-hash differs")
    folds = _sequence(policy.get("folds"), label="policy folds")
    if len(folds) != len(rw.WORLD_BLOCKS):
        _fail("policy does not retain five folds")
    for heldout, raw_scope in zip(rw.WORLD_BLOCKS, folds, strict=True):
        _validate_scope_structure(
            raw_scope,
            heldout_block=heldout,
            strategy_hash_by_id=strategy_hash_by_id,
            worlds_per_block=worlds_per_block,
        )
    _validate_scope_structure(
        policy.get("final_fit"),
        heldout_block=None,
        strategy_hash_by_id=strategy_hash_by_id,
        worlds_per_block=worlds_per_block,
    )
    _false_authorities(policy, label="support-switched policy")
    _validate_self_hash(
        policy,
        "support_switched_policy_sha256",
        label="support-switched policy",
    )
    return policy


def build_extreme_tail_panel_nomination_summary_v1(
    policy_receipts: Sequence[Mapping[str, object]],
    *,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Build a diagnostic 4/5 summary; authoritative mode is not licensed."""
    if type(require_authoritative) is not bool:
        _fail("require_authoritative must be an exact boolean")
    if require_authoritative:
        _fail(
            "authoritative panel aggregation is unavailable until this "
            "contract consumes the frozen panel and generation/content-bound "
            "panel replay receipts"
        )
    raw = _sequence(policy_receipts, label="support-switched policy receipts")
    if not raw:
        _fail("panel nomination summary requires at least one slate policy")
    policies = [_validate_policy_structure(item) for item in raw]
    slate_ids = [str(_mapping(item["slate"], label="policy slate")["slate_id"])
                 for item in policies]
    if len(set(slate_ids)) != len(slate_ids):
        _fail("panel policy slate identities are not unique")
    if any(item.get("require_authoritative") is not require_authoritative
           for item in policies):
        _fail("panel policy dose authority mode differs")
    fold_passed = sum(
        scope["support_gate"]["passed"] is True
        for item in policies for scope in item["folds"]
    )
    fold_total = sum(len(item["folds"]) for item in policies)
    final_passed = sum(
        item["final_fit"]["support_gate"]["passed"] is True
        for item in policies
    )
    final_total = len(policies)
    fold_left = fold_passed * GENERAL_SUPPORT_DENOMINATOR
    fold_right = fold_total * GENERAL_SUPPORT_NUMERATOR
    final_left = final_passed * GENERAL_SUPPORT_DENOMINATOR
    final_right = final_total * GENERAL_SUPPORT_NUMERATOR
    fold_supported = fold_left >= fold_right
    final_supported = final_left >= final_right
    arithmetic_supported = fold_supported and final_supported
    policy_bindings = [
        {
            "slate": item["slate"],
            "support_switched_policy_sha256": item[
                "support_switched_policy_sha256"
            ],
            "support_census_sha256": item["source_receipts"][
                "support_census_sha256"
            ],
            "extreme_tail_suite_sha256": item["source_receipts"][
                "extreme_tail_suite_sha256"
            ],
        }
        for item in policies
    ]
    body = {
        "schema_version": PANEL_SUMMARY_SCHEMA,
        "summary_law_id": PANEL_SUMMARY_LAW_ID,
        "policy_schema_version": POLICY_SCHEMA,
        "support_fraction": {
            "numerator": GENERAL_SUPPORT_NUMERATOR,
            "denominator": GENERAL_SUPPORT_DENOMINATOR,
            "comparison_operator": ">=",
            "decision_uses_integer_cross_products_only": True,
        },
        "authoritative_expected_counts": {
            "slates": AUTHORITATIVE_SLATE_COUNT,
            "fold_gates": AUTHORITATIVE_FOLD_GATE_COUNT,
            "final_fit_gates": AUTHORITATIVE_FINAL_GATE_COUNT,
        },
        "require_authoritative": require_authoritative,
        "evidence_role": "non-authoritative-structural-diagnostic-only",
        "authoritative_panel_certification": False,
        "slate_count": len(policies),
        "slate_ids": slate_ids,
        "policy_bindings": policy_bindings,
        "policy_bindings_sha256": _sha(
            policy_bindings, label="panel policy bindings"
        ),
        "fold_gates": {
            "passed": fold_passed,
            "total": fold_total,
            "passed_times_denominator": fold_left,
            "total_times_numerator": fold_right,
            "meets_support_fraction": fold_supported,
        },
        "final_fit_gates": {
            "passed": final_passed,
            "total": final_total,
            "passed_times_denominator": final_left,
            "total_times_numerator": final_right,
            "meets_support_fraction": final_supported,
        },
        "joint_support_fraction_arithmetic_passed": arithmetic_supported,
        "literal_coverage_ge_230_generally_supported": False,
        "nomination_role": "literal-coverage-ge-230-diagnostic-only",
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "panel_nomination_summary_sha256")


def validate_extreme_tail_panel_nomination_summary_v1(
    value: Mapping[str, object],
    policy_receipts: Sequence[Mapping[str, object]],
    *,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Replay the pure panel summary and require canonical byte identity."""
    retained = _mapping(value, label="retained panel nomination summary")
    expected = build_extreme_tail_panel_nomination_summary_v1(
        policy_receipts,
        require_authoritative=require_authoritative,
    )
    if _canonical(retained, label="retained panel nomination summary") != _canonical(
        expected, label="replayed panel nomination summary"
    ):
        _fail("retained panel nomination summary canonical replay differs")
    return expected


__all__ = [
    "AUTHORITATIVE_FINAL_GATE_COUNT",
    "AUTHORITATIVE_FOLD_GATE_COUNT",
    "AUTHORITATIVE_SLATE_COUNT",
    "BOOK_SELECTION_SCHEMA",
    "CorpusExtremeTailSupportSwitchError",
    "FALLBACK_STRATEGY_ID",
    "FINAL_MINIMUM_OPPORTUNITY_WORLDS",
    "FOLD_MINIMUM_OPPORTUNITY_WORLDS",
    "GENERAL_SUPPORT_DENOMINATOR",
    "GENERAL_SUPPORT_NUMERATOR",
    "LITERAL_COVERAGE_STRATEGY_ID",
    "PANEL_SUMMARY_LAW_ID",
    "PANEL_SUMMARY_SCHEMA",
    "POLICY_LAW_ID",
    "POLICY_SCHEMA",
    "SCOPE_SCHEMA",
    "build_extreme_tail_panel_nomination_summary_v1",
    "build_extreme_tail_support_switched_policy_v1",
    "validate_extreme_tail_panel_nomination_summary_v1",
    "validate_extreme_tail_support_switched_policy_v1",
]
