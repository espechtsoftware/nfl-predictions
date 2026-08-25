"""Outcome-blind Core v1 lineup-book catalog normalization.

The module is deliberately an offline projection over payloads that have
already passed the Foundry source-panel and T230 terminal validators.  It
does not reopen objects, reconstruct matrices, run a selector, or access an
outcome.  Its job is smaller and mechanical: normalize the seven R194 ranks,
four final-fit T230 ranks, and one final-fit support-switched rank onto one
deterministic per-slate roster union and freeze their exact 4/14/80 prefixes.

The public builder accepts retained payload bodies together with their exact
content identities.  It validates the relevant retained structure and hashes,
but intentionally never calls the T230 science validator: catalog extraction
must not become a 109th science execution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research.corpus_v12_import import canonical_lineup_id


CATALOG_SCHEMA: Final = "corpus-core-v1-book-catalog/v1"
SLATE_SCHEMA: Final = "corpus-core-v1-book-catalog-slate/v1"
RANK_SCHEMA: Final = "corpus-core-v1-immutable-rank/v1"
BOOK_SCHEMA: Final = "corpus-core-v1-prefix-book/v1"
POPULATION_SCHEMA: Final = "corpus-core-v1-source-population/v1"
EVIDENCE_CLASS: Final = "core-v1-prespecified"
SOURCE_PANEL_SCHEMA: Final = "foundry-v12-combined-panel-index/v1"
T230_PANEL_RELEASE_SCHEMA: Final = "foundry-t230-panel-release/v1"

EXPECTED_SOURCE_SLATE_COUNT: Final = 54
EXPECTED_STRATEGY_COUNT: Final = 12
EXPECTED_BOOK_BUDGETS: Final = (4, 14, 80)
EXPECTED_RANK_DEPTH: Final = 80
EXPECTED_BOOK_CELL_COUNT: Final = (
    EXPECTED_SOURCE_SLATE_COUNT
    * EXPECTED_STRATEGY_COUNT
    * len(EXPECTED_BOOK_BUDGETS)
)
THRESHOLDS_DK: Final = (180, 194, 200, 210, 220, 230, 240, 250)

SOURCE_PARAMETER_SET_IDS: Final = (
    "incumbent",
    "remove-salary-floor",
    "remove-qb-stack",
    "remove-bring-back",
    "allow-rb-vs-dst",
    "allow-two-rb",
    "remove-all-five-shared-constraints",
)
SOURCE_STRATEGY_IDS: Final = tuple(
    f"r194:{value}" for value in SOURCE_PARAMETER_SET_IDS
)
RAW_T230_SOURCE_STRATEGY_IDS: Final = (
    "coverage-ge-230-v1",
    "bounded-tail-ladder-ge-210-250-v1",
    "block-robust-bounded-tail-ge-210-250-v1",
    "individual-ge-230-rank-v1",
)
RAW_T230_STRATEGY_IDS: Final = tuple(
    f"t230:{value}" for value in RAW_T230_SOURCE_STRATEGY_IDS
)
SUPPORT_SWITCH_STRATEGY_ID: Final = "t230:support-switched-policy-v1"
T230_STRATEGY_IDS: Final = (*RAW_T230_STRATEGY_IDS, SUPPORT_SWITCH_STRATEGY_ID)
STRATEGY_IDS: Final = (*SOURCE_STRATEGY_IDS, *T230_STRATEGY_IDS)

VARIANT_RESULT_SCHEMA: Final = "corpus-legal-feasibility-variant-result/v2"
T230_RESULT_SCHEMA: Final = "foundry-t230-slate-analysis/v1"
T230_SUITE_SCHEMA: Final = "extreme-tail-retrieval-suite/v1"
T230_BOOK_SCHEMA: Final = "extreme-tail-retrieval-book/v1"
SUPPORT_POLICY_SCHEMA: Final = "extreme-tail-support-switched-policy/v1"
SUPPORT_BOOK_SCHEMA: Final = "extreme-tail-support-switched-book/v1"

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_FALSE_AUTHORITY_FIELDS: Final = (
    "publication_authority",
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "historical_retune_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "promotion_authority",
    "decision_authority",
)
_NESTED_FALSE_FIELDS: Final = frozenset({
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
})

_SOURCE_INPUT_KEYS: Final = frozenset({
    "source_ordinal",
    "panel_member",
    "later_source_freeze_identity",
    "compatibility_import_sha256",
    "candidate_provenance_sha256",
    "reconstruction_sha256",
    "variant_results",
})
_RETAINED_RESULT_KEYS: Final = frozenset({"result", "result_identity"})
_PANEL_MEMBER_KEYS: Final = frozenset({
    "slate_id",
    "lane_ordinal",
    "lane_id",
    "task_ordinal",
    "source_task_ordinal",
    "source_task_authority_sha256",
    "task_acceptance_identity",
    "carrier_identity",
    "arms",
})
_PANEL_ARM_KEYS: Final = frozenset({
    "arm_ordinal", "parameter_set_id", "result_identity",
})
_SLATE_KEYS: Final = frozenset({"season", "week", "slate_id"})
_CATALOG_KEYS: Final = frozenset({
    "schema_version",
    "catalog_id",
    "phase",
    "evidence_class",
    "source_panel_identity",
    "source_panel_sha256",
    "t230_panel_release_identity",
    "t230_panel_release_sha256",
    "later_source_freeze_identity",
    "later_source_freeze_sha256",
    "strategy_count",
    "strategy_registry",
    "strategy_registry_sha256",
    "entry_budgets",
    "thresholds_dk",
    "contrast_count",
    "contrast_registry",
    "contrast_registry_sha256",
    "source_slate_count",
    "slates",
    "slate_catalog_set_sha256",
    "book_cell_count",
    "contrast_cell_count",
    "final_fit_only_for_realized_comparison",
    "cross_fit_books_excluded_from_realized_comparison",
    "complete_shared_union_retained",
    "every_book_is_exact_rank_prefix",
    "contest_rank_roi_available",
    "outcome_fields_read",
    *_FALSE_AUTHORITY_FIELDS,
    "catalog_sha256",
})
_SLATE_OUTPUT_KEYS: Final = frozenset({
    "schema_version",
    "source_ordinal",
    "slate",
    "source_authority",
    "t230_authority",
    "union_population",
    "source_populations",
    "rank_count",
    "ranks",
    "book_count",
    "books",
    "support_switch_selected_source_strategy_id",
    "upstream_dk_legality_verified_for_complete_union",
    "outcome_fields_read",
    *_FALSE_AUTHORITY_FIELDS,
    "slate_catalog_sha256",
})
_SOURCE_AUTHORITY_KEYS: Final = frozenset({
    "panel_member_sha256",
    "source_task_authority_sha256",
    "task_acceptance_identity",
    "carrier_identity",
    "source_arm_result_identities",
    "later_source_freeze_identity",
    "later_source_freeze_sha256",
    "compatibility_import_sha256",
    "candidate_provenance_sha256",
    "reconstruction_sha256",
})
_T230_AUTHORITY_KEYS: Final = frozenset({
    "result_identity",
    "t230_slate_result_sha256",
    "support_switched_policy_sha256",
    "selected_source_strategy_id",
})
_UNION_KEYS: Final = frozenset({
    "lineup_count",
    "lineup_order_law",
    "lineup_ids",
    "rosters",
    "lineup_ids_sha256",
    "rosters_sha256",
    "population_sha256",
})
_POPULATION_KEYS: Final = frozenset({
    "schema_version",
    "source_ordinal",
    "strategy_id",
    "implementation_sha256",
    "variant_result_identity",
    "variant_result_sha256",
    "generated_unique_count",
    "generated_unique_union_indices",
    "generated_unique_union_indices_sha256",
    "visit_roster_count",
    "visit_rosters_sha256",
    "first_occurrence_visit_indices_sha256",
    "upstream_dk_legality_verified",
    *_FALSE_AUTHORITY_FIELDS,
    "source_population_sha256",
})
_RANK_KEYS: Final = frozenset({
    "schema_version",
    "rank_id",
    "source_ordinal",
    "strategy_id",
    "implementation_sha256",
    "population_sha256",
    "rank_depth",
    "rank_union_indices",
    "rank_lineup_ids",
    "rank_union_indices_sha256",
    "rank_lineup_ids_sha256",
    "source_binding",
    "ranking_prefix_law",
    *_FALSE_AUTHORITY_FIELDS,
    "rank_sha256",
})
_BOOK_KEYS: Final = frozenset({
    "schema_version",
    "book_id",
    "source_ordinal",
    "strategy_id",
    "implementation_sha256",
    "population_sha256",
    "rank_id",
    "rank_sha256",
    "entry_budget",
    "entry_count",
    "selected_union_indices",
    "selected_lineup_ids",
    "selected_union_indices_sha256",
    "selected_lineup_ids_sha256",
    "ranking_prefix_law",
    *_FALSE_AUTHORITY_FIELDS,
    "book_sha256",
})
_STRATEGY_KEYS: Final = frozenset({
    "ordinal",
    "strategy_id",
    "family",
    "source_strategy_id",
    "implementation_sha256",
    "rank_depth",
    "entry_budgets",
    "selection_scope",
    "fit_scope",
    "evidence_class",
    "strategy_sha256",
})
_CONTRAST_KEYS: Final = frozenset({
    "ordinal",
    "contrast_id",
    "family",
    "challenger_strategy_id",
    "comparator_strategy_id",
    "direction",
    "required_budgets",
    "required_on_every_slate",
    "report_regardless_of_sign",
    "evidence_class",
    "contrast_sha256",
})


class CorpusCoreV1CatalogError(ValueError):
    """The Core v1 catalog cannot be formed without changing its law."""


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1CatalogError(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _fail(message: str) -> None:
    raise CorpusCoreV1CatalogError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return value


def _canonical_string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be a nonempty canonical string")
    return value


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1CatalogError(str(exc)) from exc


def _json_identity(
    value: object, identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return batch.validate_json_identity(value, identity, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1CatalogError(str(exc)) from exc


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _self_hash(value: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = canonical_sha256(result)
    return result


def _canonical_slate(value: object, *, label: str) -> dict[str, object]:
    raw = _mapping(value, label=label)
    _exact_keys(raw, _SLATE_KEYS, label=label)
    return {
        "season": _exact_int(raw.get("season"), label=f"{label}.season", minimum=2000),
        "week": _exact_int(raw.get("week"), label=f"{label}.week", minimum=1),
        "slate_id": _canonical_string(raw.get("slate_id"), label=f"{label}.slate_id"),
    }


def _canonical_roster(value: object, *, label: str) -> tuple[str, ...]:
    raw = _sequence(value, label=label)
    roster = tuple(
        _canonical_string(player, label=f"{label} player") for player in raw
    )
    if len(roster) != 9 or len(set(roster)) != 9 or roster != tuple(sorted(roster)):
        _fail(f"{label} must be one sorted, unique nine-player roster")
    return roster


def _assert_nested_outcome_blind(value: object, *, label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _NESTED_FALSE_FIELDS and item is not False:
                _fail(f"{label}.{key} must be false")
            if key == "outcome_columns_read" and item != []:
                _fail(f"{label}.outcome_columns_read must be empty")
            _assert_nested_outcome_blind(item, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, item in enumerate(value):
            _assert_nested_outcome_blind(item, label=f"{label}[{ordinal}]")


def _normalize_panel_member(
    value: object, *, source_ordinal: int,
) -> dict[str, object]:
    raw = _mapping(value, label=f"panel member[{source_ordinal}]")
    _exact_keys(raw, _PANEL_MEMBER_KEYS, label=f"panel member[{source_ordinal}]")
    arms_raw = _sequence(raw.get("arms"), label="panel member arms")
    if len(arms_raw) != len(SOURCE_PARAMETER_SET_IDS):
        _fail("panel member must retain exactly seven source arms")
    arms: list[dict[str, object]] = []
    for arm_ordinal, (arm_raw, expected_id) in enumerate(
        zip(arms_raw, SOURCE_PARAMETER_SET_IDS, strict=True)
    ):
        arm = _mapping(arm_raw, label=f"panel arm[{arm_ordinal}]")
        _exact_keys(arm, _PANEL_ARM_KEYS, label=f"panel arm[{arm_ordinal}]")
        if (
            arm.get("arm_ordinal") != arm_ordinal
            or arm.get("parameter_set_id") != expected_id
        ):
            _fail("panel source-arm order differs")
        arms.append({
            "arm_ordinal": arm_ordinal,
            "parameter_set_id": expected_id,
            "result_identity": _identity(
                arm.get("result_identity"), label=f"panel arm[{arm_ordinal}] result"
            ),
        })
    if raw.get("source_task_ordinal") != source_ordinal:
        _fail("panel member source ordinals are not exactly ordered")
    return {
        "slate_id": _canonical_string(raw.get("slate_id"), label="panel slate id"),
        "lane_ordinal": _exact_int(raw.get("lane_ordinal"), label="lane ordinal"),
        "lane_id": _canonical_string(raw.get("lane_id"), label="lane id"),
        "task_ordinal": _exact_int(raw.get("task_ordinal"), label="task ordinal"),
        "source_task_ordinal": source_ordinal,
        "source_task_authority_sha256": _sha(
            raw.get("source_task_authority_sha256"), label="source task authority"
        ),
        "task_acceptance_identity": _identity(
            raw.get("task_acceptance_identity"), label="task acceptance"
        ),
        "carrier_identity": _identity(raw.get("carrier_identity"), label="carrier"),
        "arms": arms,
    }


def _normalize_source_variant(
    value: object,
    *,
    arm_ordinal: int,
    panel_arm: Mapping[str, object],
    expected_slate_id: str,
) -> dict[str, object]:
    retained = _mapping(value, label=f"source variant[{arm_ordinal}]")
    _exact_keys(retained, _RETAINED_RESULT_KEYS, label=f"source variant[{arm_ordinal}]")
    result = dict(_mapping(retained.get("result"), label="source variant result"))
    identity = _json_identity(
        result, retained.get("result_identity"), label="source variant result identity"
    )
    if identity != panel_arm["result_identity"]:
        _fail("source variant result identity differs from the accepted panel")
    _validate_self_hash(result, field="result_sha256", label="source variant result")
    _assert_nested_outcome_blind(result, label="source variant result")
    slate = _canonical_slate(result.get("slate"), label="source variant slate")
    profile = _mapping(result.get("profile"), label="source variant profile")
    expected_parameter = SOURCE_PARAMETER_SET_IDS[arm_ordinal]
    if (
        result.get("schema") != VARIANT_RESULT_SCHEMA
        or slate["slate_id"] != expected_slate_id
        or profile.get("ordinal") != arm_ordinal
        or profile.get("parameter_set_id") != expected_parameter
    ):
        _fail("source variant schema/slate/profile differs")
    implementation_sha256 = _sha(
        profile.get("parameter_set_sha256"), label="source parameter-set SHA"
    )
    unique = tuple(
        _canonical_roster(row, label="source generated-unique roster")
        for row in _sequence(result.get("unique_rosters"), label="source unique rosters")
    )
    selected = tuple(
        _canonical_roster(row, label="source selected roster")
        for row in _sequence(result.get("selected_rosters"), label="source selected rosters")
    )
    selector = _mapping(result.get("selector"), label="source selector")
    selected_indices = tuple(
        _exact_int(value, label="source selected index")
        for value in _sequence(
            selector.get("selected_indices"), label="source selected indices"
        )
    )
    if (
        not unique
        or len(set(unique)) != len(unique)
        or len(selected) != EXPECTED_RANK_DEPTH
        or len(set(selected)) != EXPECTED_RANK_DEPTH
        or len(selected_indices) != EXPECTED_RANK_DEPTH
        or len(set(selected_indices)) != EXPECTED_RANK_DEPTH
        or any(index >= len(unique) for index in selected_indices)
        or selected != tuple(unique[index] for index in selected_indices)
    ):
        _fail("source generated population or exact-80 rank differs")
    visit_rosters = _sequence(result.get("visit_rosters"), label="source visit rosters")
    first_occurrence = _sequence(
        result.get("first_occurrence_visit_indices"),
        label="source first-occurrence indices",
    )
    if len(first_occurrence) != len(unique) or any(
        type(value) is not int or value < 0 for value in first_occurrence
    ):
        _fail("source occurrence lineage summary differs")
    return {
        "parameter_set_id": expected_parameter,
        "strategy_id": SOURCE_STRATEGY_IDS[arm_ordinal],
        "implementation_sha256": implementation_sha256,
        "result_identity": identity,
        "result_sha256": result["result_sha256"],
        "slate": slate,
        "later_source_freeze_manifest_sha256": _sha(
            result.get("later_source_freeze_manifest_sha256"),
            label="later source freeze manifest SHA",
        ),
        "unique_rosters": unique,
        "selected_rosters": selected,
        "visit_roster_count": len(visit_rosters),
        "visit_rosters_sha256": canonical_sha256(visit_rosters),
        "first_occurrence_visit_indices_sha256": canonical_sha256(first_occurrence),
    }


def _rank(
    *,
    source_ordinal: int,
    strategy_id: str,
    implementation_sha256: str,
    population_sha256: str,
    union_indices: Sequence[int],
    lineup_ids: Sequence[str],
    source_binding: Mapping[str, object],
) -> dict[str, object]:
    indices = list(union_indices)
    ids = list(lineup_ids)
    if (
        len(indices) != EXPECTED_RANK_DEPTH
        or len(set(indices)) != EXPECTED_RANK_DEPTH
        or len(ids) != EXPECTED_RANK_DEPTH
        or len(set(ids)) != EXPECTED_RANK_DEPTH
    ):
        _fail("Core v1 requires one exact unique rank-80 per strategy")
    body = {
        "schema_version": RANK_SCHEMA,
        "rank_id": f"core-v1:{source_ordinal:02d}:{strategy_id}:rank-80",
        "source_ordinal": source_ordinal,
        "strategy_id": strategy_id,
        "implementation_sha256": implementation_sha256,
        "population_sha256": population_sha256,
        "rank_depth": EXPECTED_RANK_DEPTH,
        "rank_union_indices": indices,
        "rank_lineup_ids": ids,
        "rank_union_indices_sha256": canonical_sha256(indices),
        "rank_lineup_ids_sha256": canonical_sha256(ids),
        "source_binding": dict(source_binding),
        "ranking_prefix_law": "exact-prefix-of-one-immutable-rank-80",
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "rank_sha256")


def _book(
    *, source_ordinal: int, rank: Mapping[str, object], entry_budget: int,
) -> dict[str, object]:
    indices = list(rank["rank_union_indices"][:entry_budget])
    lineup_ids = list(rank["rank_lineup_ids"][:entry_budget])
    body = {
        "schema_version": BOOK_SCHEMA,
        "book_id": (
            f"core-v1:{source_ordinal:02d}:{rank['strategy_id']}:exact-{entry_budget}"
        ),
        "source_ordinal": source_ordinal,
        "strategy_id": rank["strategy_id"],
        "implementation_sha256": rank["implementation_sha256"],
        "population_sha256": rank["population_sha256"],
        "rank_id": rank["rank_id"],
        "rank_sha256": rank["rank_sha256"],
        "entry_budget": entry_budget,
        "entry_count": entry_budget,
        "selected_union_indices": indices,
        "selected_lineup_ids": lineup_ids,
        "selected_union_indices_sha256": canonical_sha256(indices),
        "selected_lineup_ids_sha256": canonical_sha256(lineup_ids),
        "ranking_prefix_law": "exact-prefix-of-one-immutable-rank-80",
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "book_sha256")


def _validate_t230_book_self_hash(value: Mapping[str, object], *, label: str) -> None:
    schema = value.get("schema_version")
    if schema == T230_BOOK_SCHEMA:
        _validate_self_hash(value, field="book_sha256", label=label)
    elif schema == SUPPORT_BOOK_SCHEMA:
        _validate_self_hash(value, field="book_selection_sha256", label=label)
    else:
        _fail(f"{label} schema differs")
    _assert_nested_outcome_blind(value, label=label)


def _extract_t230_ranks(
    *,
    retained_t230: object,
    source_ordinal: int,
    panel_member: Mapping[str, object],
    slate: Mapping[str, object],
    union_lineup_ids: Sequence[str],
    union_rosters: Sequence[tuple[str, ...]],
    later_source_freeze_identity: Mapping[str, object],
    compatibility_import_sha256: str,
    candidate_provenance_sha256: str,
    reconstruction_sha256: str,
    population_sha256: str,
) -> tuple[list[dict[str, object]], dict[str, object], dict[str, object]]:
    retained = _mapping(retained_t230, label=f"T230 retained result[{source_ordinal}]")
    _exact_keys(retained, _RETAINED_RESULT_KEYS, label="T230 retained result")
    result = dict(_mapping(retained.get("result"), label="T230 result"))
    identity = _json_identity(
        result, retained.get("result_identity"), label="T230 result identity"
    )
    _validate_self_hash(result, field="t230_slate_result_sha256", label="T230 result")
    _assert_nested_outcome_blind(result, label="T230 result")
    if (
        result.get("schema_version") != T230_RESULT_SCHEMA
        or result.get("source_ordinal") != source_ordinal
        or result.get("slate_id") != slate["slate_id"]
        or result.get("source_member_sha256") != canonical_sha256(panel_member)
        or result.get("source_task_authority_sha256")
        != panel_member["source_task_authority_sha256"]
    ):
        _fail("T230 result source/slate binding differs")
    inputs = _mapping(result.get("input_artifact_bindings"), label="T230 inputs")
    if (
        inputs.get("task_acceptance_identity")
        != panel_member["task_acceptance_identity"]
        or inputs.get("carrier_identity") != panel_member["carrier_identity"]
        or inputs.get("later_source_freeze_identity")
        != later_source_freeze_identity
        or inputs.get("compatibility_import_sha256") != compatibility_import_sha256
        or inputs.get("candidate_provenance_sha256") != candidate_provenance_sha256
        or inputs.get("reconstruction_sha256") != reconstruction_sha256
        or inputs.get("lineup_ids_sha256") != canonical_sha256(list(union_lineup_ids))
    ):
        _fail("T230 result differs from its already-validated source payload")
    reconstruction = _mapping(
        result.get("reconstruction_receipt"), label="T230 reconstruction receipt"
    )
    if (
        reconstruction.get("reconstruction_sha256") != reconstruction_sha256
        or reconstruction.get("candidate_provenance_sha256")
        != candidate_provenance_sha256
    ):
        _fail("T230 reconstruction binding differs")

    union_index_by_lineup = {
        lineup_id: ordinal for ordinal, lineup_id in enumerate(union_lineup_ids)
    }
    roster_by_lineup = {
        lineup_id: roster
        for lineup_id, roster in zip(union_lineup_ids, union_rosters, strict=True)
    }
    suite = _mapping(result.get("extreme_tail_suite"), label="T230 suite")
    _validate_self_hash(suite, field="suite_sha256", label="T230 suite")
    final_fit = _mapping(suite.get("final_fit"), label="T230 final fit")
    if (
        suite.get("schema_version") != T230_SUITE_SCHEMA
        or suite.get("entry_budgets") != list(EXPECTED_BOOK_BUDGETS)
        or suite.get("ranking_depth") != EXPECTED_RANK_DEPTH
        or suite.get("final_fit_is_distinct_all_block_refit") is not True
        or final_fit.get("heldout_block") is not None
    ):
        _fail("T230 suite is not the frozen final-fit 4/14/80 lattice")
    registry = _sequence(suite.get("strategy_registry"), label="T230 registry")
    if [row.get("strategy_id") for row in registry] != list(
        RAW_T230_SOURCE_STRATEGY_IDS
    ):
        _fail("T230 raw strategy registry order differs")
    implementation_by_source_id = {
        source_id: _sha(row.get("strategy_sha256"), label="T230 strategy SHA")
        for source_id, row in zip(
            RAW_T230_SOURCE_STRATEGY_IDS, registry, strict=True
        )
    }
    raw_books = [
        _mapping(value, label="T230 final-fit book")
        for value in _sequence(final_fit.get("books"), label="T230 final-fit books")
    ]
    ranks: list[dict[str, object]] = []
    raw_book_by_key: dict[tuple[str, int], Mapping[str, object]] = {}
    for raw_book in raw_books:
        _validate_t230_book_self_hash(raw_book, label="T230 final-fit book")
        key = (str(raw_book.get("strategy_id")), raw_book.get("entry_budget"))
        if key in raw_book_by_key:
            _fail("T230 final-fit books repeat")
        raw_book_by_key[key] = raw_book
    if set(raw_book_by_key) != {
        (source_id, budget)
        for source_id in RAW_T230_SOURCE_STRATEGY_IDS
        for budget in EXPECTED_BOOK_BUDGETS
    }:
        _fail("T230 final-fit book lattice differs")
    for strategy_id, source_id in zip(
        RAW_T230_STRATEGY_IDS, RAW_T230_SOURCE_STRATEGY_IDS, strict=True
    ):
        source_books = [raw_book_by_key[(source_id, budget)] for budget in EXPECTED_BOOK_BUDGETS]
        ids_by_budget: list[list[str]] = []
        for budget, raw_book in zip(EXPECTED_BOOK_BUDGETS, source_books, strict=True):
            ids = [
                _canonical_string(value, label="T230 selected lineup id")
                for value in _sequence(
                    raw_book.get("selected_lineup_ids"),
                    label="T230 selected lineup ids",
                )
            ]
            rosters = [
                _canonical_roster(value, label="T230 selected roster")
                for value in _sequence(
                    raw_book.get("selected_rosters"), label="T230 selected rosters"
                )
            ]
            if (
                len(ids) != budget
                or len(set(ids)) != budget
                or len(rosters) != budget
                or any(lineup_id not in union_index_by_lineup for lineup_id in ids)
                or any(
                    roster_by_lineup[lineup_id] != roster
                    for lineup_id, roster in zip(ids, rosters, strict=True)
                )
            ):
                _fail("T230 selected book is not an exact source-union projection")
            ids_by_budget.append(ids)
        if any(
            ids_by_budget[index] != ids_by_budget[-1][:budget]
            for index, budget in enumerate(EXPECTED_BOOK_BUDGETS[:-1])
        ):
            _fail("T230 raw books are not exact prefixes of one rank-80")
        rank_ids = ids_by_budget[-1]
        ranks.append(_rank(
            source_ordinal=source_ordinal,
            strategy_id=strategy_id,
            implementation_sha256=implementation_by_source_id[source_id],
            population_sha256=population_sha256,
            union_indices=[union_index_by_lineup[value] for value in rank_ids],
            lineup_ids=rank_ids,
            source_binding={
                "source_kind": "t230-raw-final-fit",
                "source_strategy_id": source_id,
                "source_strategy_sha256": implementation_by_source_id[source_id],
                "source_book_sha256": source_books[-1]["book_sha256"],
                "t230_result_identity": identity,
                "t230_slate_result_sha256": result["t230_slate_result_sha256"],
            },
        ))

    policy = _mapping(
        result.get("support_switched_policy"), label="support-switched policy"
    )
    _validate_self_hash(
        policy,
        field="support_switched_policy_sha256",
        label="support-switched policy",
    )
    final_switch = _mapping(policy.get("final_fit"), label="support final fit")
    support_books = [
        _mapping(value, label="support-switched book")
        for value in _sequence(
            final_switch.get("selected_books"), label="support-switched books"
        )
    ]
    if (
        policy.get("schema_version") != SUPPORT_POLICY_SCHEMA
        or policy.get("entry_budgets") != list(EXPECTED_BOOK_BUDGETS)
        or policy.get("ranking_depth") != EXPECTED_RANK_DEPTH
        or final_switch.get("scope_kind") != "final-fit"
        or final_switch.get("heldout_block") is not None
        or final_switch.get("selected_book_count") != 3
        or len(support_books) != 3
    ):
        _fail("support-switched final-fit lattice differs")
    selected_source_id = _canonical_string(
        final_switch.get("selected_strategy_id"), label="support selected strategy"
    )
    if selected_source_id not in {
        "coverage-ge-230-v1",
        "block-robust-bounded-tail-ge-210-250-v1",
    }:
        _fail("support switch selected an unregistered source strategy")
    support_ids_by_budget: list[list[str]] = []
    for budget, support_book in zip(
        EXPECTED_BOOK_BUDGETS, support_books, strict=True
    ):
        _validate_t230_book_self_hash(support_book, label="support-switched book")
        ids = [
            _canonical_string(value, label="support selected lineup id")
            for value in _sequence(
                support_book.get("selected_lineup_ids"),
                label="support selected lineup ids",
            )
        ]
        if (
            support_book.get("strategy_id") != selected_source_id
            or support_book.get("entry_budget") != budget
            or support_book.get("entry_count") != budget
            or len(ids) != budget
            or len(set(ids)) != budget
            or any(value not in union_index_by_lineup for value in ids)
        ):
            _fail("support-switched book differs from its source union")
        support_ids_by_budget.append(ids)
    if any(
        support_ids_by_budget[index] != support_ids_by_budget[-1][:budget]
        for index, budget in enumerate(EXPECTED_BOOK_BUDGETS[:-1])
    ):
        _fail("support-switched books are not prefixes of one rank-80")
    science_contract = _mapping(
        result.get("science_contract_bindings"), label="T230 science contracts"
    )
    support_contract_sha256 = _sha(
        science_contract.get("support_contract_sha256"),
        label="support contract SHA",
    )
    support_rank_ids = support_ids_by_budget[-1]
    ranks.append(_rank(
        source_ordinal=source_ordinal,
        strategy_id=SUPPORT_SWITCH_STRATEGY_ID,
        implementation_sha256=support_contract_sha256,
        population_sha256=population_sha256,
        union_indices=[union_index_by_lineup[value] for value in support_rank_ids],
        lineup_ids=support_rank_ids,
        source_binding={
            "source_kind": "t230-support-switched-final-fit",
            "selected_source_strategy_id": selected_source_id,
            "support_contract_sha256": support_contract_sha256,
            "support_switch_scope_sha256": final_switch[
                "support_switch_scope_sha256"
            ],
            "source_book_selection_sha256": support_books[-1][
                "book_selection_sha256"
            ],
            "t230_result_identity": identity,
            "t230_slate_result_sha256": result["t230_slate_result_sha256"],
        },
    ))
    return ranks, {
        "result_identity": identity,
        "t230_slate_result_sha256": result["t230_slate_result_sha256"],
        "support_switched_policy_sha256": policy[
            "support_switched_policy_sha256"
        ],
        "selected_source_strategy_id": selected_source_id,
    }, {
        RAW_T230_STRATEGY_IDS[index]: implementation_by_source_id[source_id]
        for index, source_id in enumerate(RAW_T230_SOURCE_STRATEGY_IDS)
    } | {SUPPORT_SWITCH_STRATEGY_ID: support_contract_sha256}


def _build_slate(
    *, source_input: object, retained_t230: object,
) -> tuple[dict[str, object], dict[str, str]]:
    source = _mapping(source_input, label="Core v1 source input")
    _exact_keys(source, _SOURCE_INPUT_KEYS, label="Core v1 source input")
    source_ordinal = _exact_int(
        source.get("source_ordinal"), label="source ordinal"
    )
    if source_ordinal >= EXPECTED_SOURCE_SLATE_COUNT:
        _fail("source ordinal is outside the Core v1 54-slate lattice")
    panel_member = _normalize_panel_member(
        source.get("panel_member"), source_ordinal=source_ordinal
    )
    later_source_freeze_identity = _identity(
        source.get("later_source_freeze_identity"), label="later source freeze"
    )
    compatibility_import_sha256 = _sha(
        source.get("compatibility_import_sha256"), label="compatibility import SHA"
    )
    candidate_provenance_sha256 = _sha(
        source.get("candidate_provenance_sha256"), label="candidate provenance SHA"
    )
    reconstruction_sha256 = _sha(
        source.get("reconstruction_sha256"), label="reconstruction SHA"
    )
    variants_raw = _sequence(
        source.get("variant_results"), label="source variant results"
    )
    if len(variants_raw) != len(SOURCE_PARAMETER_SET_IDS):
        _fail("Core v1 source input must retain exactly seven variants")
    variants = [
        _normalize_source_variant(
            raw,
            arm_ordinal=ordinal,
            panel_arm=panel_member["arms"][ordinal],
            expected_slate_id=str(panel_member["slate_id"]),
        )
        for ordinal, raw in enumerate(variants_raw)
    ]
    slate = variants[0]["slate"]
    if any(value["slate"] != slate for value in variants):
        _fail("source variants do not share one slate")
    if len({value["later_source_freeze_manifest_sha256"] for value in variants}) != 1:
        _fail("source variants do not share one later-source freeze")

    roster_set = {
        roster for variant in variants for roster in variant["unique_rosters"]
    }
    lineup_by_roster = {
        roster: canonical_lineup_id(slate, roster) for roster in roster_set
    }
    roster_by_lineup = {lineup_id: roster for roster, lineup_id in lineup_by_roster.items()}
    if len(roster_by_lineup) != len(roster_set):
        _fail("source lineup identity collision")
    union_lineup_ids = sorted(roster_by_lineup)
    union_rosters = [roster_by_lineup[value] for value in union_lineup_ids]
    union_index_by_roster = {
        roster: ordinal for ordinal, roster in enumerate(union_rosters)
    }
    union_population = {
        "lineup_count": len(union_lineup_ids),
        "lineup_order_law": "ascending-stable-per-slate-lineup-id",
        "lineup_ids": union_lineup_ids,
        "rosters": [list(roster) for roster in union_rosters],
        "lineup_ids_sha256": canonical_sha256(union_lineup_ids),
        "rosters_sha256": canonical_sha256([list(roster) for roster in union_rosters]),
    }
    union_population["population_sha256"] = canonical_sha256(union_population)

    populations: list[dict[str, object]] = []
    ranks: list[dict[str, object]] = []
    implementation_by_strategy: dict[str, str] = {}
    for variant in variants:
        population_indices = [
            union_index_by_roster[roster] for roster in variant["unique_rosters"]
        ]
        population_body = {
            "schema_version": POPULATION_SCHEMA,
            "source_ordinal": source_ordinal,
            "strategy_id": variant["strategy_id"],
            "implementation_sha256": variant["implementation_sha256"],
            "variant_result_identity": variant["result_identity"],
            "variant_result_sha256": variant["result_sha256"],
            "generated_unique_count": len(population_indices),
            "generated_unique_union_indices": population_indices,
            "generated_unique_union_indices_sha256": canonical_sha256(
                population_indices
            ),
            "visit_roster_count": variant["visit_roster_count"],
            "visit_rosters_sha256": variant["visit_rosters_sha256"],
            "first_occurrence_visit_indices_sha256": variant[
                "first_occurrence_visit_indices_sha256"
            ],
            "upstream_dk_legality_verified": True,
            **{field: False for field in _FALSE_AUTHORITY_FIELDS},
        }
        population = _self_hash(population_body, "source_population_sha256")
        populations.append(population)
        rank_rosters = variant["selected_rosters"]
        rank_ids = [lineup_by_roster[roster] for roster in rank_rosters]
        rank = _rank(
            source_ordinal=source_ordinal,
            strategy_id=str(variant["strategy_id"]),
            implementation_sha256=str(variant["implementation_sha256"]),
            population_sha256=str(population["source_population_sha256"]),
            union_indices=[union_index_by_roster[roster] for roster in rank_rosters],
            lineup_ids=rank_ids,
            source_binding={
                "source_kind": "source-arm-r194-final-rank",
                "variant_result_identity": variant["result_identity"],
                "variant_result_sha256": variant["result_sha256"],
            },
        )
        ranks.append(rank)
        implementation_by_strategy[str(variant["strategy_id"])] = str(
            variant["implementation_sha256"]
        )

    t230_ranks, t230_binding, t230_implementations = _extract_t230_ranks(
        retained_t230=retained_t230,
        source_ordinal=source_ordinal,
        panel_member=panel_member,
        slate=slate,
        union_lineup_ids=union_lineup_ids,
        union_rosters=union_rosters,
        later_source_freeze_identity=later_source_freeze_identity,
        compatibility_import_sha256=compatibility_import_sha256,
        candidate_provenance_sha256=candidate_provenance_sha256,
        reconstruction_sha256=reconstruction_sha256,
        population_sha256=str(union_population["population_sha256"]),
    )
    ranks.extend(t230_ranks)
    implementation_by_strategy.update(t230_implementations)
    if [rank["strategy_id"] for rank in ranks] != list(STRATEGY_IDS):
        _fail("Core v1 rank strategy order differs")
    books = [
        _book(source_ordinal=source_ordinal, rank=rank, entry_budget=budget)
        for rank in ranks
        for budget in EXPECTED_BOOK_BUDGETS
    ]
    body = {
        "schema_version": SLATE_SCHEMA,
        "source_ordinal": source_ordinal,
        "slate": slate,
        "source_authority": {
            "panel_member_sha256": canonical_sha256(panel_member),
            "source_task_authority_sha256": panel_member[
                "source_task_authority_sha256"
            ],
            "task_acceptance_identity": panel_member["task_acceptance_identity"],
            "carrier_identity": panel_member["carrier_identity"],
            "source_arm_result_identities": [
                arm["result_identity"] for arm in panel_member["arms"]
            ],
            "later_source_freeze_identity": later_source_freeze_identity,
            "later_source_freeze_sha256": variants[0][
                "later_source_freeze_manifest_sha256"
            ],
            "compatibility_import_sha256": compatibility_import_sha256,
            "candidate_provenance_sha256": candidate_provenance_sha256,
            "reconstruction_sha256": reconstruction_sha256,
        },
        "t230_authority": t230_binding,
        "union_population": union_population,
        "source_populations": populations,
        "rank_count": len(ranks),
        "ranks": ranks,
        "book_count": len(books),
        "books": books,
        "support_switch_selected_source_strategy_id": t230_binding[
            "selected_source_strategy_id"
        ],
        "upstream_dk_legality_verified_for_complete_union": True,
        "outcome_fields_read": [],
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "slate_catalog_sha256"), implementation_by_strategy


def frozen_contrast_registry() -> list[dict[str, object]]:
    """Return the exact 45-direction Core v1 contrast registry."""
    rows: list[dict[str, object]] = []

    def append(family: str, challenger: str, comparator: str) -> None:
        ordinal = len(rows)
        body = {
            "ordinal": ordinal,
            "contrast_id": f"core-v1:{family}:{challenger}:minus:{comparator}",
            "family": family,
            "challenger_strategy_id": challenger,
            "comparator_strategy_id": comparator,
            "direction": "challenger-minus-comparator",
            "required_budgets": list(EXPECTED_BOOK_BUDGETS),
            "required_on_every_slate": True,
            "report_regardless_of_sign": True,
            "evidence_class": EVIDENCE_CLASS,
        }
        rows.append(_self_hash(body, "contrast_sha256"))

    incumbent = SOURCE_STRATEGY_IDS[0]
    for challenger in T230_STRATEGY_IDS:
        append("primary-headline", challenger, incumbent)
    for challenger in T230_STRATEGY_IDS:
        for comparator in SOURCE_STRATEGY_IDS[1:]:
            append("mandatory-secondary-fill-arm", challenger, comparator)
    for comparator in RAW_T230_STRATEGY_IDS:
        append("support-switch-mechanism", SUPPORT_SWITCH_STRATEGY_ID, comparator)
    for challenger in SOURCE_STRATEGY_IDS[1:]:
        append("source-arm-diagnostic", challenger, incumbent)
    if len(rows) != 45 or len({row["contrast_id"] for row in rows}) != 45:
        raise AssertionError("Core v1 contrast registry construction drifted")
    return rows


def _strategy_registry(
    implementation_by_strategy: Mapping[str, str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for ordinal, strategy_id in enumerate(STRATEGY_IDS):
        if strategy_id in SOURCE_STRATEGY_IDS:
            family = "source-arm-r194"
            source_strategy_id = strategy_id.removeprefix("r194:")
            selection_scope = "source-arm-generated-unique"
        elif strategy_id in RAW_T230_STRATEGY_IDS:
            family = "raw-t230-final-fit"
            source_strategy_id = strategy_id.removeprefix("t230:")
            selection_scope = "cross-arm-all-block-final-fit"
        else:
            family = "support-switched-t230-final-fit"
            source_strategy_id = "support-switched-policy-v1"
            selection_scope = "cross-arm-all-block-final-fit"
        body = {
            "ordinal": ordinal,
            "strategy_id": strategy_id,
            "family": family,
            "source_strategy_id": source_strategy_id,
            "implementation_sha256": _sha(
                implementation_by_strategy.get(strategy_id),
                label=f"strategy {strategy_id} implementation SHA",
            ),
            "rank_depth": EXPECTED_RANK_DEPTH,
            "entry_budgets": list(EXPECTED_BOOK_BUDGETS),
            "selection_scope": selection_scope,
            "fit_scope": "final-fit",
            "evidence_class": EVIDENCE_CLASS,
        }
        rows.append(_self_hash(body, "strategy_sha256"))
    return rows


def _validate_structural_roots(
    *,
    source_panel: object,
    source_panel_identity: object,
    t230_panel_release: object,
    t230_panel_release_identity: object,
    source_slates: Sequence[object],
    t230_results: Sequence[object],
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    """Bind terminal roots without calling either science replay path."""
    panel = dict(_mapping(source_panel, label="validated source panel"))
    panel_identity = _json_identity(
        panel, source_panel_identity, label="validated source panel identity"
    )
    _validate_self_hash(panel, field="panel_index_sha256", label="source panel")
    accepted_slates = list(
        _sequence(panel.get("accepted_slates"), label="panel accepted slates")
    )
    supplied_members = [
        _mapping(value, label=f"source input[{ordinal}]").get("panel_member")
        for ordinal, value in enumerate(source_slates)
    ]
    panel_false_fields = (
        "automatic_retry_licensed",
        "uses_realized_outcomes",
        "historical_scoring_licensed",
        "corpus_fill_licensed",
        "graph_mutation_licensed",
        "live_policy_access_licensed",
        "production_change_licensed",
        "analytical_authority",
        "promotion_authority",
        "decision_authority",
    )
    if (
        panel.get("schema_version") != SOURCE_PANEL_SCHEMA
        or panel.get("accepted_slate_count") != EXPECTED_SOURCE_SLATE_COUNT
        or len(accepted_slates) != EXPECTED_SOURCE_SLATE_COUNT
        or canonical_json_bytes(accepted_slates) != canonical_json_bytes(supplied_members)
        or panel.get("exclusions") != []
        or panel.get("failures") != []
        or panel.get("missing_tasks") != []
        or any(panel.get(field) is not False for field in panel_false_fields)
    ):
        _fail("source panel structural root differs from the supplied 54 members")

    release = dict(_mapping(t230_panel_release, label="validated T230 release"))
    release_identity = _json_identity(
        release,
        t230_panel_release_identity,
        label="validated T230 panel release identity",
    )
    _validate_self_hash(
        release, field="t230_panel_release_sha256", label="T230 panel release"
    )
    release_rows = list(
        _sequence(
            release.get("ordered_slate_acceptances"),
            label="T230 ordered slate acceptances",
        )
    )
    supplied_t230 = [
        _mapping(value, label=f"T230 result[{ordinal}]")
        for ordinal, value in enumerate(t230_results)
    ]
    result_identities = [
        _identity(value.get("result_identity"), label="T230 result identity")
        for value in supplied_t230
    ]
    release_false_fields = (
        "automatic_retry_licensed",
        "uses_realized_outcomes",
        "historical_scoring_licensed",
        "corpus_fill_licensed",
        "graph_mutation_licensed",
        "live_policy_access_licensed",
        "production_change_licensed",
        "analytical_authority",
        "promotion_authority",
        "decision_authority",
    )
    verification = _mapping(
        release.get("verification"), label="T230 release verification"
    )
    if (
        release.get("schema_version") != T230_PANEL_RELEASE_SCHEMA
        or release.get("panel_object_identity") != panel_identity
        or release.get("panel_index_sha256") != panel.get("panel_index_sha256")
        or release.get("source_member_count") != EXPECTED_SOURCE_SLATE_COUNT
        or release.get("accepted_slate_count") != EXPECTED_SOURCE_SLATE_COUNT
        or len(release_rows) != EXPECTED_SOURCE_SLATE_COUNT
        or release.get("ordered_slate_acceptances_sha256")
        != canonical_sha256(release_rows)
        or release.get("ordered_result_identities_sha256")
        != canonical_sha256(result_identities)
        or verification.get("all_54_result_identities_replayed") is not True
        or verification.get("all_source_ordinals_complete_and_ordered") is not True
        or verification.get("finalizer_science_recomputation_performed") is not False
        or verification.get("realized_outcomes_read") is not False
        or any(release.get(field) is not False for field in release_false_fields)
    ):
        _fail("T230 terminal structural release differs")
    for source_ordinal, (raw_row, member, retained_t230) in enumerate(
        zip(release_rows, accepted_slates, supplied_t230, strict=True)
    ):
        row = _mapping(raw_row, label=f"T230 release row[{source_ordinal}]")
        result = _mapping(retained_t230.get("result"), label="T230 result")
        if (
            row.get("source_ordinal") != source_ordinal
            or row.get("slate_id") != member.get("slate_id")
            or row.get("source_member_sha256") != canonical_sha256(member)
            or row.get("result_identity") != result_identities[source_ordinal]
            or row.get("t230_slate_result_sha256")
            != result.get("t230_slate_result_sha256")
        ):
            _fail("T230 release ordered result/member binding differs")
    return panel, panel_identity, release, release_identity


def build_core_v1_catalog(
    *,
    catalog_id: str,
    source_panel: Mapping[str, object],
    source_panel_identity: Mapping[str, object],
    t230_panel_release: Mapping[str, object],
    t230_panel_release_identity: Mapping[str, object],
    source_slates: Sequence[Mapping[str, object]],
    t230_results: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Normalize all 54 already-validated source/T230 payload pairs.

    This function has no reader callback by design.  The caller performs the
    terminal structural reopen and supplies the exact retained payloads.  The
    builder validates content identities and projects retained books only.
    """
    retained_catalog_id = _canonical_string(catalog_id, label="catalog id")
    sources = _sequence(source_slates, label="Core v1 source slates")
    t230 = _sequence(t230_results, label="Core v1 T230 results")
    if len(sources) != EXPECTED_SOURCE_SLATE_COUNT or len(t230) != len(sources):
        _fail("Core v1 requires exactly 54 paired source/T230 slates")
    (
        retained_panel,
        panel_identity,
        retained_t230_release,
        t230_release_identity,
    ) = _validate_structural_roots(
        source_panel=source_panel,
        source_panel_identity=source_panel_identity,
        t230_panel_release=t230_panel_release,
        t230_panel_release_identity=t230_panel_release_identity,
        source_slates=sources,
        t230_results=t230,
    )
    slates: list[dict[str, object]] = []
    retained_implementations: dict[str, str] | None = None
    for source_ordinal, (source_input, retained_t230) in enumerate(
        zip(sources, t230, strict=True)
    ):
        source_map = _mapping(source_input, label=f"source input[{source_ordinal}]")
        if source_map.get("source_ordinal") != source_ordinal:
            _fail("Core v1 source inputs are not ordered 0..53")
        slate, implementations = _build_slate(
            source_input=source_input, retained_t230=retained_t230
        )
        if retained_implementations is None:
            retained_implementations = implementations
        elif implementations != retained_implementations:
            _fail("strategy implementation identities drift across slates")
        slates.append(slate)
    if retained_implementations is None:
        raise AssertionError("exact 54-slate guard failed internally")
    slate_keys = [
        (row["slate"]["season"], row["slate"]["week"], row["slate"]["slate_id"])
        for row in slates
    ]
    if len(set(slate_keys)) != EXPECTED_SOURCE_SLATE_COUNT:
        _fail("Core v1 source slate identities repeat")
    source_freezes = [
        row["source_authority"]["later_source_freeze_identity"] for row in slates
    ]
    if any(value != source_freezes[0] for value in source_freezes[1:]):
        _fail("Core v1 slates do not share one later-source freeze identity")
    source_freeze_hashes = [
        row["source_authority"]["later_source_freeze_sha256"] for row in slates
    ]
    if any(value != source_freeze_hashes[0] for value in source_freeze_hashes[1:]):
        _fail("Core v1 slates do not share one later-source freeze SHA")
    strategies = _strategy_registry(retained_implementations)
    contrasts = frozen_contrast_registry()
    body = {
        "schema_version": CATALOG_SCHEMA,
        "catalog_id": retained_catalog_id,
        "phase": "outcome-blind-frozen-books",
        "evidence_class": EVIDENCE_CLASS,
        "source_panel_identity": panel_identity,
        "source_panel_sha256": retained_panel["panel_index_sha256"],
        "t230_panel_release_identity": t230_release_identity,
        "t230_panel_release_sha256": retained_t230_release[
            "t230_panel_release_sha256"
        ],
        "later_source_freeze_identity": source_freezes[0],
        "later_source_freeze_sha256": source_freeze_hashes[0],
        "strategy_count": len(strategies),
        "strategy_registry": strategies,
        "strategy_registry_sha256": canonical_sha256(strategies),
        "entry_budgets": list(EXPECTED_BOOK_BUDGETS),
        "thresholds_dk": list(THRESHOLDS_DK),
        "contrast_count": len(contrasts),
        "contrast_registry": contrasts,
        "contrast_registry_sha256": canonical_sha256(contrasts),
        "source_slate_count": len(slates),
        "slates": slates,
        "slate_catalog_set_sha256": canonical_sha256([
            row["slate_catalog_sha256"] for row in slates
        ]),
        "book_cell_count": sum(int(row["book_count"]) for row in slates),
        "contrast_cell_count": (
            len(slates) * len(contrasts) * len(EXPECTED_BOOK_BUDGETS)
        ),
        "final_fit_only_for_realized_comparison": True,
        "cross_fit_books_excluded_from_realized_comparison": True,
        "complete_shared_union_retained": True,
        "every_book_is_exact_rank_prefix": True,
        "contest_rank_roi_available": False,
        "outcome_fields_read": [],
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return validate_core_v1_catalog(_self_hash(body, "catalog_sha256"))


def validate_core_v1_catalog(value: object) -> dict[str, object]:
    """Replay the complete internal Core v1 census and prefix law."""
    item = dict(_mapping(value, label="Core v1 catalog"))
    _exact_keys(item, _CATALOG_KEYS, label="Core v1 catalog")
    _validate_self_hash(item, field="catalog_sha256", label="Core v1 catalog")
    _assert_nested_outcome_blind(item, label="Core v1 catalog")
    strategies = list(
        _sequence(item.get("strategy_registry"), label="strategy registry")
    )
    contrasts = list(
        _sequence(item.get("contrast_registry"), label="contrast registry")
    )
    slates = list(_sequence(item.get("slates"), label="catalog slates"))
    if (
        item.get("schema_version") != CATALOG_SCHEMA
        or item.get("phase") != "outcome-blind-frozen-books"
        or item.get("evidence_class") != EVIDENCE_CLASS
        or item.get("strategy_count") != EXPECTED_STRATEGY_COUNT
        or len(strategies) != EXPECTED_STRATEGY_COUNT
        or [row.get("strategy_id") for row in strategies] != list(STRATEGY_IDS)
        or item.get("strategy_registry_sha256") != canonical_sha256(strategies)
        or item.get("entry_budgets") != list(EXPECTED_BOOK_BUDGETS)
        or item.get("thresholds_dk") != list(THRESHOLDS_DK)
        or item.get("contrast_count") != 45
        or len(contrasts) != 45
        or contrasts != frozen_contrast_registry()
        or item.get("contrast_registry_sha256") != canonical_sha256(contrasts)
        or item.get("source_slate_count") != EXPECTED_SOURCE_SLATE_COUNT
        or len(slates) != EXPECTED_SOURCE_SLATE_COUNT
        or item.get("book_cell_count") != EXPECTED_BOOK_CELL_COUNT
        or item.get("contrast_cell_count")
        != EXPECTED_SOURCE_SLATE_COUNT * 45 * len(EXPECTED_BOOK_BUDGETS)
        or item.get("final_fit_only_for_realized_comparison") is not True
        or item.get("cross_fit_books_excluded_from_realized_comparison") is not True
        or item.get("complete_shared_union_retained") is not True
        or item.get("every_book_is_exact_rank_prefix") is not True
        or item.get("contest_rank_roi_available") is not False
        or item.get("outcome_fields_read") != []
        or any(item.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("Core v1 catalog root law differs")
    _identity(item.get("source_panel_identity"), label="source panel identity")
    _sha(item.get("source_panel_sha256"), label="source panel SHA")
    _identity(item.get("t230_panel_release_identity"), label="T230 release identity")
    _sha(item.get("t230_panel_release_sha256"), label="T230 panel release SHA")
    _identity(item.get("later_source_freeze_identity"), label="later source freeze")
    _sha(item.get("later_source_freeze_sha256"), label="later source freeze SHA")
    for ordinal, strategy in enumerate(strategies):
        _exact_keys(
            strategy, _STRATEGY_KEYS, label=f"strategy[{ordinal}]"
        )
        _validate_self_hash(
            strategy, field="strategy_sha256", label=f"strategy[{ordinal}]"
        )
        if (
            strategy.get("ordinal") != ordinal
            or strategy.get("rank_depth") != EXPECTED_RANK_DEPTH
            or strategy.get("entry_budgets") != list(EXPECTED_BOOK_BUDGETS)
            or strategy.get("fit_scope") != "final-fit"
            or strategy.get("evidence_class") != EVIDENCE_CLASS
        ):
            _fail("Core v1 strategy registry row differs")
        _sha(strategy.get("implementation_sha256"), label="strategy implementation")
    observed_slate_keys: list[tuple[object, ...]] = []
    observed_slate_hashes: list[str] = []
    for source_ordinal, slate_raw in enumerate(slates):
        slate_row = _mapping(slate_raw, label=f"catalog slate[{source_ordinal}]")
        _exact_keys(slate_row, _SLATE_OUTPUT_KEYS, label="catalog slate")
        _validate_self_hash(
            slate_row, field="slate_catalog_sha256", label="catalog slate"
        )
        if (
            slate_row.get("schema_version") != SLATE_SCHEMA
            or slate_row.get("source_ordinal") != source_ordinal
            or slate_row.get("rank_count") != EXPECTED_STRATEGY_COUNT
            or slate_row.get("book_count")
            != EXPECTED_STRATEGY_COUNT * len(EXPECTED_BOOK_BUDGETS)
            or slate_row.get("upstream_dk_legality_verified_for_complete_union")
            is not True
            or slate_row.get("outcome_fields_read") != []
            or any(
                slate_row.get(field) is not False
                for field in _FALSE_AUTHORITY_FIELDS
            )
        ):
            _fail("Core v1 slate root law differs")
        slate = _canonical_slate(slate_row.get("slate"), label="catalog slate")
        source_authority = _mapping(
            slate_row.get("source_authority"), label="slate source authority"
        )
        _exact_keys(
            source_authority,
            _SOURCE_AUTHORITY_KEYS,
            label="slate source authority",
        )
        t230_authority = _mapping(
            slate_row.get("t230_authority"), label="slate T230 authority"
        )
        _exact_keys(
            t230_authority, _T230_AUTHORITY_KEYS, label="slate T230 authority"
        )
        _identity(
            t230_authority.get("result_identity"), label="slate T230 result"
        )
        _sha(
            t230_authority.get("t230_slate_result_sha256"),
            label="slate T230 result SHA",
        )
        _sha(
            t230_authority.get("support_switched_policy_sha256"),
            label="slate support-switch SHA",
        )
        if (
            _identity(
                source_authority.get("later_source_freeze_identity"),
                label="slate later source freeze",
            )
            != item["later_source_freeze_identity"]
            or _sha(
                source_authority.get("later_source_freeze_sha256"),
                label="slate later source freeze SHA",
            )
            != item["later_source_freeze_sha256"]
        ):
            _fail("slate later-source freeze identity/SHA differs from catalog root")
        for field in (
            "panel_member_sha256",
            "source_task_authority_sha256",
            "compatibility_import_sha256",
            "candidate_provenance_sha256",
            "reconstruction_sha256",
        ):
            _sha(source_authority.get(field), label=f"slate source authority.{field}")
        _identity(
            source_authority.get("task_acceptance_identity"),
            label="slate task acceptance",
        )
        _identity(
            source_authority.get("carrier_identity"), label="slate carrier"
        )
        source_arm_identities = list(
            _sequence(
                source_authority.get("source_arm_result_identities"),
                label="slate source-arm identities",
            )
        )
        if len(source_arm_identities) != len(SOURCE_STRATEGY_IDS):
            _fail("slate source-arm identity census differs")
        for identity in source_arm_identities:
            _identity(identity, label="slate source-arm result")
        selected_support_source = t230_authority.get("selected_source_strategy_id")
        if (
            selected_support_source
            not in {
                "coverage-ge-230-v1",
                "block-robust-bounded-tail-ge-210-250-v1",
            }
            or slate_row.get("support_switch_selected_source_strategy_id")
            != selected_support_source
        ):
            _fail("slate support-switch source strategy differs")
        observed_slate_keys.append(
            (slate["season"], slate["week"], slate["slate_id"])
        )
        observed_slate_hashes.append(str(slate_row["slate_catalog_sha256"]))
        union = _mapping(slate_row.get("union_population"), label="union population")
        _exact_keys(union, _UNION_KEYS, label="union population")
        lineup_ids = list(_sequence(union.get("lineup_ids"), label="union lineup ids"))
        rosters = [
            _canonical_roster(value, label="union roster")
            for value in _sequence(union.get("rosters"), label="union rosters")
        ]
        if (
            not lineup_ids
            or len(lineup_ids) != len(rosters)
            or len(set(lineup_ids)) != len(lineup_ids)
            or lineup_ids != sorted(lineup_ids)
            or union.get("lineup_count") != len(lineup_ids)
            or union.get("lineup_ids_sha256") != canonical_sha256(lineup_ids)
            or union.get("rosters_sha256")
            != canonical_sha256([list(roster) for roster in rosters])
            or union.get("population_sha256")
            != canonical_sha256({
                key: value for key, value in union.items()
                if key != "population_sha256"
            })
            or any(
                canonical_lineup_id(slate, roster) != lineup_id
                for lineup_id, roster in zip(lineup_ids, rosters, strict=True)
            )
        ):
            _fail("Core v1 union population differs")
        populations = list(
            _sequence(
                slate_row.get("source_populations"),
                label="source populations",
            )
        )
        if (
            len(populations) != len(SOURCE_STRATEGY_IDS)
            or [row.get("strategy_id") for row in populations]
            != list(SOURCE_STRATEGY_IDS)
        ):
            _fail("Core v1 source-population census differs")
        strategy_impl = {
            row["strategy_id"]: row["implementation_sha256"] for row in strategies
        }
        for population in populations:
            _exact_keys(
                population, _POPULATION_KEYS, label="source population"
            )
            _validate_self_hash(
                population,
                field="source_population_sha256",
                label="source population",
            )
            population_indices = list(
                _sequence(
                    population.get("generated_unique_union_indices"),
                    label="source population indices",
                )
            )
            if (
                population.get("schema_version") != POPULATION_SCHEMA
                or population.get("source_ordinal") != source_ordinal
                or population.get("implementation_sha256")
                != strategy_impl[population["strategy_id"]]
                or population.get("generated_unique_count")
                != len(population_indices)
                or not population_indices
                or len(set(population_indices)) != len(population_indices)
                or any(
                    type(index) is not int or not 0 <= index < len(lineup_ids)
                    for index in population_indices
                )
                or population.get("generated_unique_union_indices_sha256")
                != canonical_sha256(population_indices)
                or population.get("upstream_dk_legality_verified") is not True
                or any(
                    population.get(field) is not False
                    for field in _FALSE_AUTHORITY_FIELDS
                )
            ):
                _fail("Core v1 source population differs")
            _identity(
                population.get("variant_result_identity"),
                label="source population variant result",
            )
            for field in (
                "variant_result_sha256",
                "visit_rosters_sha256",
                "first_occurrence_visit_indices_sha256",
            ):
                _sha(population.get(field), label=f"source population.{field}")
        ranks = list(_sequence(slate_row.get("ranks"), label="slate ranks"))
        books = list(_sequence(slate_row.get("books"), label="slate books"))
        if (
            len(ranks) != EXPECTED_STRATEGY_COUNT
            or [row.get("strategy_id") for row in ranks] != list(STRATEGY_IDS)
            or len(books) != EXPECTED_STRATEGY_COUNT * 3
        ):
            _fail("Core v1 slate rank/book census differs")
        rank_by_strategy: dict[str, Mapping[str, object]] = {}
        for rank in ranks:
            _exact_keys(rank, _RANK_KEYS, label="Core v1 rank")
            _validate_self_hash(rank, field="rank_sha256", label="Core v1 rank")
            strategy_id = str(rank.get("strategy_id"))
            indices = list(
                _sequence(rank.get("rank_union_indices"), label="rank union indices")
            )
            ids = list(_sequence(rank.get("rank_lineup_ids"), label="rank lineup ids"))
            if (
                rank.get("schema_version") != RANK_SCHEMA
                or rank.get("source_ordinal") != source_ordinal
                or rank.get("implementation_sha256") != strategy_impl[strategy_id]
                or rank.get("rank_depth") != EXPECTED_RANK_DEPTH
                or len(indices) != EXPECTED_RANK_DEPTH
                or len(set(indices)) != EXPECTED_RANK_DEPTH
                or any(type(index) is not int or not 0 <= index < len(lineup_ids) for index in indices)
                or ids != [lineup_ids[index] for index in indices]
                or rank.get("rank_union_indices_sha256") != canonical_sha256(indices)
                or rank.get("rank_lineup_ids_sha256") != canonical_sha256(ids)
            ):
                _fail("Core v1 rank projection differs")
            rank_by_strategy[strategy_id] = rank
        expected_book_order = [
            (strategy_id, budget)
            for strategy_id in STRATEGY_IDS
            for budget in EXPECTED_BOOK_BUDGETS
        ]
        observed_book_order: list[tuple[object, object]] = []
        for book in books:
            _exact_keys(book, _BOOK_KEYS, label="Core v1 book")
            _validate_self_hash(book, field="book_sha256", label="Core v1 book")
            strategy_id = str(book.get("strategy_id"))
            budget = book.get("entry_budget")
            observed_book_order.append((strategy_id, budget))
            rank = rank_by_strategy[strategy_id]
            indices = list(
                _sequence(book.get("selected_union_indices"), label="book indices")
            )
            ids = list(
                _sequence(book.get("selected_lineup_ids"), label="book lineup ids")
            )
            if (
                book.get("schema_version") != BOOK_SCHEMA
                or book.get("source_ordinal") != source_ordinal
                or budget not in EXPECTED_BOOK_BUDGETS
                or book.get("entry_count") != budget
                or book.get("rank_sha256") != rank["rank_sha256"]
                or indices != list(rank["rank_union_indices"][:budget])
                or ids != list(rank["rank_lineup_ids"][:budget])
                or book.get("selected_union_indices_sha256")
                != canonical_sha256(indices)
                or book.get("selected_lineup_ids_sha256")
                != canonical_sha256(ids)
            ):
                _fail("Core v1 book is not an exact rank prefix")
        if observed_book_order != expected_book_order:
            _fail("Core v1 book order differs")
    if len(set(observed_slate_keys)) != EXPECTED_SOURCE_SLATE_COUNT:
        _fail("Core v1 catalog slate identities repeat")
    if item.get("slate_catalog_set_sha256") != canonical_sha256(observed_slate_hashes):
        _fail("Core v1 slate catalog set hash differs")
    return item


__all__ = [
    "BOOK_SCHEMA",
    "CATALOG_SCHEMA",
    "CorpusCoreV1CatalogError",
    "EVIDENCE_CLASS",
    "EXPECTED_BOOK_BUDGETS",
    "EXPECTED_BOOK_CELL_COUNT",
    "EXPECTED_RANK_DEPTH",
    "EXPECTED_SOURCE_SLATE_COUNT",
    "EXPECTED_STRATEGY_COUNT",
    "RAW_T230_STRATEGY_IDS",
    "SLATE_SCHEMA",
    "SOURCE_STRATEGY_IDS",
    "STRATEGY_IDS",
    "SUPPORT_SWITCH_STRATEGY_ID",
    "T230_STRATEGY_IDS",
    "THRESHOLDS_DK",
    "build_core_v1_catalog",
    "canonical_json_bytes",
    "canonical_sha256",
    "frozen_contrast_registry",
    "validate_core_v1_catalog",
]
