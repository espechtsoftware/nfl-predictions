"""Fixed real-artifact smoke for the accepted-G0 R6 full-union fast lane.

This operator performs one outcome-blind production read.  It exact-opens the
accepted 54-slate G0 panel, selects only source ordinal zero (2023-W01), runs
the authoritative five-by-10,000-world full-union lane, validates all 48
exact-80 books, and writes one local create-once receipt.  It never invokes a
catalog projection and has no realized-outcome, graph, or promotion seam.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import os
from pathlib import Path
from typing import Final

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_fast_lane_v1 as lane
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter
from nfl_dfs.research import corpus_v12_panel_index as panel_index
from nfl_dfs.research import residual_world_columns as rw


RECEIPT_SCHEMA: Final = "corpus-r6-full-union-task0-production-smoke-receipt/v1"
SMOKE_ID: Final = "accepted-g0-task0-2023-w01-full-union-48-book-v1"
PRODUCTION_ENABLE_ENV: Final = "R6_FULL_UNION_TASK0_SMOKE_PRODUCTION_ENABLED"
TASK0_SOURCE_ORDINAL: Final = 0
TASK0_SLATE_ID: Final = "2023-w01"
FIXED_TASK0_MEMBERSHIP_SHA256: Final = (
    "ddcb8909d8eb6600345facd5c54fad64f8db3ac15f6b86eb7c348d3802f49105"
)
WORLD_COUNT: Final = len(rw.WORLD_BLOCKS) * rw.WORLDS_PER_BLOCK
EXPECTED_WORLD_ROLES: Final = tuple(
    f"world_artifact_{block.lower()}" for block in rw.WORLD_BLOCKS
)
_FALSE_FIELDS: Final = (
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
_RECEIPT_VERIFICATION_FIELDS: Final = frozenset({
    "fixed_panel_generation_exact",
    "complete_54_slate_panel_verified",
    "task0_membership_verified",
    "authoritative_world_dose_verified",
    "all_48_exact_80_books_verified",
    "catalog_projection_not_used",
    "matchup_source_not_read",
    "realized_outcomes_not_read",
})
_RESULT_VERIFICATION_FIELDS: Final = frozenset({
    "panel_exact_reopen_verified",
    "accepted_membership_binding_verified",
    "task_acceptance_exact_reopen_verified",
    "carrier_exact_reopen_verified",
    "world_artifact_exact_reopen_verified",
    "all_seven_arm_score_hashes_verified",
    "complete_cross_arm_union_reconstructed",
    "all_48_books_materialized",
    "matchup_source_not_read",
    "realized_outcomes_not_read",
})
_RESULT_FIELDS: Final = frozenset({
    "schema_version",
    "slate_id",
    "panel_index_identity",
    "panel_index_sha256",
    "accepted_slate_membership",
    "accepted_slate_membership_sha256",
    "task_acceptance_identity",
    "carrier_identity",
    "later_source_freeze_identity",
    "world_artifact_identities",
    "world_artifact_identity_set_sha256",
    "compatibility_import_sha256",
    "candidate_provenance_sha256",
    "reconstruction_sha256",
    "full_union_surface",
    "full_union_surface_sha256",
    "verification",
    "task_result_sha256",
    *_FALSE_FIELDS,
})
_RECEIPT_FIELDS: Final = frozenset({
    "schema_version",
    "smoke_id",
    "mode",
    "source_commit_sha",
    "panel_index_identity",
    "panel_index_sha256",
    "accepted_slate_membership_sha256",
    "production_dose",
    "execution_result",
    "execution_result_sha256",
    "verification",
    "receipt_sha256",
    *_FALSE_FIELDS,
})
_SURFACE_FIELDS: Final = frozenset({
    "schema_version",
    "slate",
    "candidate_provenance_sha256",
    "reconstruction_sha256",
    "strategy_registry",
    "strategy_registry_sha256",
    "scope_count",
    "books_per_scope",
    "book_count",
    "prefix_sizes",
    "scopes",
    "rotated_simulated_fold_count",
    "final_fit_is_distinct_all_block_refit",
    "full_union_only",
    "matchup_source_read",
    "uses_realized_outcomes",
    "evidence_tier",
    "promotion_authority",
    "full_union_surface_sha256",
})
_SCOPE_FIELDS: Final = frozenset({
    "schema_version",
    "fit_scope_id",
    "reconstruction_sha256",
    "training_blocks",
    "heldout_block",
    "worlds_per_block",
    "dose_authority",
    "require_authoritative",
    "candidate_view",
    "admission",
    "admission_mode",
    "matchup_source_read",
    "matchup_admission_read",
    "neutral_control_read",
    "strategy_registry",
    "strategy_count",
    "book_count",
    "books",
    "uses_realized_outcomes",
    "promotion_authority",
    "fit_scope_sha256",
})
_CANDIDATE_VIEW_FIELDS: Final = frozenset({
    "schema_version",
    "slate",
    "fit_scope_id",
    "training_blocks",
    "heldout_block",
    "eligible_candidates",
    "excluded_candidates_audit",
    "eligible_count",
    "excluded_count",
    "dose_authority",
    "selection_inputs_exclude_heldout_occurrences",
    "uses_realized_outcomes",
    "fit_candidate_view_sha256",
    "selection_provenance_sha256",
})
_ELIGIBLE_CANDIDATE_FIELDS: Final = frozenset({
    "lineup_id",
    "roster_player_ids",
    "training_origin_blocks",
    "training_source_arms",
    "training_occurrence_counts_by_block",
    "training_source_arms_by_block",
    "training_occurrence_count",
})
_EXCLUDED_CANDIDATE_FIELDS: Final = frozenset({
    "lineup_id",
    "reason_code",
    "heldout_origin_present",
})
_ADMISSION_FIELDS: Final = frozenset({
    "schema_version",
    "admission_id",
    "fit_scope_id",
    "selection_provenance_sha256",
    "admitted_lineup_ids",
    "admitted_count",
    "excluded_eligible_candidates",
    "dose_authority",
    "admission_inputs",
    "uses_simulated_scores",
    "uses_matchup_values",
    "uses_realized_outcomes",
    "admission_sha256",
})
_BOOK_FIELDS: Final = frozenset({
    "schema_version",
    "book_id",
    "fit_scope_id",
    "reconstruction_sha256",
    "training_blocks",
    "heldout_block",
    "admission_id",
    "admission_sha256",
    "strategy_id",
    "strategy_sha256",
    "strategy_application_scope",
    "input_lineup_ids_sha256",
    "training_score_matrix_sha256",
    "training_score_shape",
    "worlds_per_block",
    "dose_authority",
    "selected_local_indices",
    "selected_global_indices",
    "selected_lineup_ids",
    "selected_rosters",
    "entry_count",
    "marginal_trace",
    "training_metrics",
    "redundancy_diagnostics",
    "heldout_metrics_descriptive",
    "threshold_semantics",
    "uses_realized_outcomes",
    "promotion_authority",
    "book_sha256",
})


class CorpusR6FullUnionTask0SmokeV1Error(ValueError):
    """The fixed real-artifact smoke cannot preserve its closed contract."""


def _fail(message: str) -> None:
    raise CorpusR6FullUnionTask0SmokeV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _sha(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be lowercase SHA-256")
    return value


def _commit(value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail("source commit must be lowercase 40-hex")
    return value


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if batch.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = batch.canonical_sha256(result)
    return result


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionTask0SmokeV1Error(str(exc)) from exc


def _false_fields(value: Mapping[str, object], *, label: str) -> None:
    if any(value.get(field) is not False for field in _FALSE_FIELDS):
        _fail(f"{label} carries forbidden outcome or decision authority")


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if set(value) != set(expected):
        _fail(f"{label} field set differs")


def _reject_nested_outcome_or_authority(value: object, *, label: str) -> None:
    """Reject added realized-result or authority seams at every depth."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                _fail(f"{label} contains a non-string key")
            if key == "uses_realized_outcomes" and item is not False:
                _fail(f"{label}.{key} must be false")
            if key in _FALSE_FIELDS and item is not False:
                _fail(f"{label}.{key} must be false")
            if key == "realized_outcomes_not_read" and item is not True:
                _fail(f"{label}.{key} must be true")
            if (
                "outcome" in key
                and key not in {"uses_realized_outcomes", "realized_outcomes_not_read"}
                and not key.startswith("simulated_outcome")
            ):
                _fail(f"{label} contains an unregistered outcome field")
            if (
                "realized" in key
                and key not in {"uses_realized_outcomes", "realized_outcomes_not_read"}
            ):
                _fail(f"{label} contains an unregistered realized-result field")
            if (
                "actual" in key
                or "contest" in key
                or "payout" in key
                or "points" in key
            ):
                _fail(f"{label} contains an unregistered result field")
            if (
                "authority" in key
                and key not in {*_FALSE_FIELDS, "dose_authority"}
                and not key.endswith("_authority_sha256")
            ):
                _fail(f"{label} contains an unregistered authority field")
            _reject_nested_outcome_or_authority(item, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, item in enumerate(value):
            _reject_nested_outcome_or_authority(
                item, label=f"{label}[{ordinal}]"
            )


def _parse_panel(raw: bytes) -> dict[str, object]:
    try:
        panel = _mapping(
            batch.parse_canonical_json_bytes(raw, label="fixed G0 panel"),
            label="fixed G0 panel",
        )
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionTask0SmokeV1Error(str(exc)) from exc
    _validate_self_hash(panel, field="panel_index_sha256", label="fixed G0 panel")
    members = _sequence(panel.get("accepted_slates"), label="accepted slates")
    coverage = _mapping(panel.get("coverage"), label="panel coverage")
    if (
        panel.get("schema_version") != panel_index.PANEL_INDEX_SCHEMA
        or panel.get("publication_mode") != panel_index.PUBLICATION_MODE
        or panel.get("panel_id") != adapter.FIXED_PANEL_ID
        or panel.get("panel_index_sha256") != adapter.FIXED_PANEL_INDEX_SHA256
        or panel.get("accepted_slate_count") != panel_index.V12_SOURCE_TASK_COUNT
        or len(members) != panel_index.V12_SOURCE_TASK_COUNT
        or panel.get("exclusions") != []
        or panel.get("failures") != []
        or panel.get("missing_tasks") != []
        or coverage.get("complete") is not True
        or coverage.get("expected_task_count") != panel_index.V12_SOURCE_TASK_COUNT
        or coverage.get("accepted_task_count") != panel_index.V12_SOURCE_TASK_COUNT
        or [
            _mapping(member, label=f"accepted member[{ordinal}]").get(
                "source_task_ordinal"
            )
            for ordinal, member in enumerate(members)
        ]
        != list(range(panel_index.V12_SOURCE_TASK_COUNT))
    ):
        _fail("fixed G0 panel identity or complete coverage differs")
    return panel


def _task0_member(panel: Mapping[str, object]) -> dict[str, object]:
    members = _sequence(panel.get("accepted_slates"), label="accepted slates")
    member = _mapping(members[TASK0_SOURCE_ORDINAL], label="task0 panel member")
    if (
        member.get("source_task_ordinal") != TASK0_SOURCE_ORDINAL
        or member.get("slate_id") != TASK0_SLATE_ID
        or batch.canonical_sha256(member) != FIXED_TASK0_MEMBERSHIP_SHA256
        or len(_sequence(member.get("arms"), label="task0 member arms"))
        != len(batch.PARAMETER_SET_ORDER)
    ):
        _fail("fixed task0 panel membership differs")
    _identity(member.get("task_acceptance_identity"), label="task0 acceptance")
    _identity(member.get("carrier_identity"), label="task0 carrier")
    return member


def _validate_candidate_admission(
    *,
    candidate_view: Mapping[str, object],
    admission: Mapping[str, object],
    fit_scope_id: str,
    training_blocks: Sequence[str],
    heldout_block: str | None,
) -> tuple[list[str], dict[str, list[str]]]:
    _exact_keys(
        candidate_view, _CANDIDATE_VIEW_FIELDS, label="fold candidate view"
    )
    _exact_keys(admission, _ADMISSION_FIELDS, label="full-union admission")
    eligible_rows = _sequence(
        candidate_view.get("eligible_candidates"), label="eligible candidates"
    )
    excluded_rows = _sequence(
        candidate_view.get("excluded_candidates_audit"),
        label="excluded candidates",
    )
    eligible_ids: list[str] = []
    roster_by_id: dict[str, list[str]] = {}
    for ordinal, raw_row in enumerate(eligible_rows):
        row = _mapping(raw_row, label=f"eligible candidate[{ordinal}]")
        _exact_keys(
            row,
            _ELIGIBLE_CANDIDATE_FIELDS,
            label=f"eligible candidate[{ordinal}]",
        )
        lineup_id = row.get("lineup_id")
        roster = _sequence(
            row.get("roster_player_ids"), label=f"eligible roster[{ordinal}]"
        )
        origin_blocks = _sequence(
            row.get("training_origin_blocks"),
            label=f"eligible origin blocks[{ordinal}]",
        )
        occurrence_counts = _mapping(
            row.get("training_occurrence_counts_by_block"),
            label=f"eligible occurrence counts[{ordinal}]",
        )
        source_arms_by_block = _mapping(
            row.get("training_source_arms_by_block"),
            label=f"eligible source arms by block[{ordinal}]",
        )
        source_arms = _sequence(
            row.get("training_source_arms"),
            label=f"eligible source arms[{ordinal}]",
        )
        if any(
            type(value) is not int or value < 0
            for value in occurrence_counts.values()
        ):
            _fail("eligible occurrence count differs")
        if (
            type(lineup_id) is not str
            or not lineup_id
            or lineup_id in roster_by_id
            or len(roster) != rw.ROSTER_SIZE
            or len(set(roster)) != rw.ROSTER_SIZE
            or any(type(player_id) is not str or not player_id for player_id in roster)
            or origin_blocks
            != [block for block in training_blocks if occurrence_counts.get(block)]
            or set(occurrence_counts) != set(training_blocks)
            or set(source_arms_by_block) != set(training_blocks)
            or source_arms != sorted(set(source_arms))
            or any(arm not in batch.PARAMETER_SET_ORDER for arm in source_arms)
            or any(
                _sequence(arms, label="eligible block source arms")
                != sorted(set(_sequence(arms, label="eligible block source arms")))
                for arms in source_arms_by_block.values()
            )
            or row.get("training_occurrence_count")
            != sum(int(value) for value in occurrence_counts.values())
        ):
            _fail("eligible full-union candidate differs")
        eligible_ids.append(lineup_id)
        roster_by_id[lineup_id] = [str(value) for value in roster]
    for ordinal, raw_row in enumerate(excluded_rows):
        row = _mapping(raw_row, label=f"excluded candidate[{ordinal}]")
        _exact_keys(
            row,
            _EXCLUDED_CANDIDATE_FIELDS,
            label=f"excluded candidate[{ordinal}]",
        )
        if (
            type(row.get("lineup_id")) is not str
            or row.get("reason_code") != "heldout-only-origin"
            or heldout_block is None
            or row.get("heldout_origin_present") is not True
        ):
            _fail("excluded candidate audit differs")
    selection_projection = {
        "schema_version": "corpus-fold-selection-provenance/v2",
        "slate": candidate_view.get("slate"),
        "fit_scope_id": fit_scope_id,
        "training_blocks": list(training_blocks),
        "eligible_candidates": eligible_rows,
        "dose_authority": runner.AUTHORITATIVE_DOSE,
        "uses_realized_outcomes": False,
    }
    admitted_ids = _sequence(
        admission.get("admitted_lineup_ids"), label="admitted lineup IDs"
    )
    if (
        candidate_view.get("schema_version") != "corpus-fold-candidate-view/v2"
        or admission.get("schema_version") != runner.ADMISSION_SCHEMA
        or admission.get("admission_inputs")
        != "fold-local-provenance-and-stable-lineup-id-only"
        or eligible_ids != sorted(set(eligible_ids))
        or len(eligible_ids) < lane.ENTRY_BUDGET
        or candidate_view.get("eligible_count") != len(eligible_ids)
        or candidate_view.get("excluded_count") != len(excluded_rows)
        or _mapping(candidate_view.get("slate"), label="candidate-view slate").get(
            "slate_id"
        )
        != TASK0_SLATE_ID
        or candidate_view.get("selection_provenance_sha256")
        != batch.canonical_sha256(selection_projection)
        or admission.get("selection_provenance_sha256")
        != candidate_view.get("selection_provenance_sha256")
        or admitted_ids != eligible_ids
        or admission.get("admitted_count") != len(eligible_ids)
        or admission.get("excluded_eligible_candidates") != []
    ):
        _fail("complete fold-eligible union admission differs")
    try:
        runner._validate_admission_partition(admission, eligible_ids=eligible_ids)
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusR6FullUnionTask0SmokeV1Error(str(exc)) from exc
    return eligible_ids, roster_by_id


def _validate_book(
    value: object,
    *,
    strategy: Mapping[str, object],
    heldout_block: str | None,
    training_blocks: Sequence[str],
    fit_scope_id: str,
    reconstruction_sha256: str,
    admission: Mapping[str, object],
    admitted_ids: Sequence[str],
    roster_by_id: Mapping[str, Sequence[str]],
    seen_book_ids: set[str],
) -> None:
    book = _mapping(value, label="full-union book")
    _exact_keys(book, _BOOK_FIELDS, label="full-union book")
    _validate_self_hash(book, field="book_sha256", label="full-union book")
    lineup_ids = _sequence(book.get("selected_lineup_ids"), label="selected IDs")
    rosters = _sequence(book.get("selected_rosters"), label="selected rosters")
    selected_local = _sequence(
        book.get("selected_local_indices"), label="selected local indices"
    )
    selected_global = _sequence(
        book.get("selected_global_indices"), label="selected global indices"
    )
    book_id = book.get("book_id")
    if (
        type(book_id) is not str
        or not book_id
        or book_id in seen_book_ids
        or book.get("schema_version") != runner.BOOK_SCHEMA
        or book.get("fit_scope_id") != fit_scope_id
        or book.get("reconstruction_sha256") != reconstruction_sha256
        or book.get("training_blocks") != list(training_blocks)
        or book.get("strategy_id") != strategy.get("strategy_id")
        or book.get("strategy_sha256") != strategy.get("strategy_sha256")
        or book.get("admission_id") != admission.get("admission_id")
        or book.get("admission_sha256") != admission.get("admission_sha256")
        or book.get("input_lineup_ids_sha256")
        != batch.canonical_sha256(list(admitted_ids))
        or book.get("heldout_block") != heldout_block
        or book.get("worlds_per_block") != rw.WORLDS_PER_BLOCK
        or book.get("dose_authority") != runner.AUTHORITATIVE_DOSE
        or book.get("entry_count") != lane.ENTRY_BUDGET
        or len(lineup_ids) != lane.ENTRY_BUDGET
        or len(set(lineup_ids)) != lane.ENTRY_BUDGET
        or len(rosters) != lane.ENTRY_BUDGET
        or len(selected_local) != lane.ENTRY_BUDGET
        or len(set(selected_local)) != lane.ENTRY_BUDGET
        or any(
            type(index) is not int or not 0 <= index < len(admitted_ids)
            for index in selected_local
        )
        or lineup_ids != [admitted_ids[int(index)] for index in selected_local]
        or len(selected_global) != lane.ENTRY_BUDGET
        or len(set(selected_global)) != lane.ENTRY_BUDGET
        or book.get("uses_realized_outcomes") is not False
        or book.get("promotion_authority") is not False
    ):
        _fail("full-union exact-80 book differs")
    _reject_nested_outcome_or_authority(book, label="full-union book")
    for ordinal, raw_roster in enumerate(rosters):
        roster = _sequence(raw_roster, label=f"selected roster[{ordinal}]")
        if (
            len(roster) != rw.ROSTER_SIZE
            or len(set(roster)) != rw.ROSTER_SIZE
            or any(type(player_id) is not str or not player_id for player_id in roster)
            or lineup_ids[ordinal] not in roster_by_id
            or roster != list(roster_by_id[str(lineup_ids[ordinal])])
        ):
            _fail("selected roster differs")
    seen_book_ids.add(book_id)


def _validate_execution_result(
    value: object, *, member: Mapping[str, object],
) -> dict[str, object]:
    result = _mapping(value, label="fast-lane execution result")
    _exact_keys(result, _RESULT_FIELDS, label="fast-lane execution result")
    _validate_self_hash(result, field="task_result_sha256", label="execution result")
    _false_fields(result, label="execution result")
    _reject_nested_outcome_or_authority(result, label="execution result")
    expected_panel_identity = _identity(
        adapter.FIXED_PANEL_IDENTITY, label="fixed panel identity"
    )
    membership = _mapping(
        result.get("accepted_slate_membership"), label="execution membership"
    )
    worlds = _mapping(
        result.get("world_artifact_identities"), label="execution worlds"
    )
    verification = _mapping(result.get("verification"), label="verification")
    if (
        result.get("schema_version") != lane.EXECUTION_SCHEMA
        or result.get("slate_id") != TASK0_SLATE_ID
        or _identity(result.get("panel_index_identity"), label="result panel")
        != expected_panel_identity
        or result.get("panel_index_sha256") != adapter.FIXED_PANEL_INDEX_SHA256
        or batch.canonical_json_bytes(membership)
        != batch.canonical_json_bytes(dict(member))
        or result.get("accepted_slate_membership_sha256")
        != batch.canonical_sha256(membership)
        or _identity(result.get("task_acceptance_identity"), label="result acceptance")
        != _identity(member.get("task_acceptance_identity"), label="member acceptance")
        or _identity(result.get("carrier_identity"), label="result carrier")
        != _identity(member.get("carrier_identity"), label="member carrier")
        or set(worlds) != set(EXPECTED_WORLD_ROLES)
        or {
            key: _identity(item, label=f"result world {key}")
            for key, item in worlds.items()
        }
        != worlds
        or result.get("world_artifact_identity_set_sha256")
        != batch.canonical_sha256(worlds)
        or any(value is not True for value in verification.values())
        or set(verification) != set(_RESULT_VERIFICATION_FIELDS)
    ):
        _fail("fast-lane execution lineage or verification differs")
    _identity(result.get("later_source_freeze_identity"), label="later source")

    surface = _mapping(result.get("full_union_surface"), label="full-union surface")
    _exact_keys(surface, _SURFACE_FIELDS, label="full-union surface")
    surface_sha = _validate_self_hash(
        surface, field="full_union_surface_sha256", label="full-union surface"
    )
    strategies = lane.frozen_full_union_strategies_v1()
    scopes = _sequence(surface.get("scopes"), label="full-union scopes")
    if (
        result.get("full_union_surface_sha256") != surface_sha
        or surface.get("schema_version") != lane.SURFACE_SCHEMA
        or surface.get("scope_count") != lane.SCOPE_COUNT
        or surface.get("books_per_scope") != lane.BOOKS_PER_SCOPE
        or surface.get("book_count") != lane.BOOKS_PER_SLATE
        or surface.get("prefix_sizes") != list(lane.PREFIX_SIZES)
        or surface.get("strategy_registry") != strategies
        or surface.get("strategy_registry_sha256")
        != batch.canonical_sha256(strategies)
        or len(scopes) != lane.SCOPE_COUNT
        or surface.get("rotated_simulated_fold_count") != len(rw.WORLD_BLOCKS)
        or surface.get("final_fit_is_distinct_all_block_refit") is not True
        or surface.get("full_union_only") is not True
        or _mapping(surface.get("slate"), label="surface slate").get("slate_id")
        != TASK0_SLATE_ID
        or surface.get("candidate_provenance_sha256")
        != result.get("candidate_provenance_sha256")
        or surface.get("reconstruction_sha256")
        != result.get("reconstruction_sha256")
        or surface.get("matchup_source_read") is not False
        or surface.get("uses_realized_outcomes") is not False
        or surface.get("promotion_authority") is not False
    ):
        _fail("full-union surface lattice differs")
    seen_book_ids: set[str] = set()
    expected_holdouts: list[str | None] = [*rw.WORLD_BLOCKS, None]
    for scope_ordinal, raw_scope in enumerate(scopes):
        scope = _mapping(raw_scope, label=f"full-union scope[{scope_ordinal}]")
        _exact_keys(scope, _SCOPE_FIELDS, label=f"scope[{scope_ordinal}]")
        _validate_self_hash(
            scope, field="fit_scope_sha256", label=f"scope[{scope_ordinal}]"
        )
        books = _sequence(scope.get("books"), label="scope books")
        heldout = expected_holdouts[scope_ordinal]
        training_blocks = [block for block in rw.WORLD_BLOCKS if block != heldout]
        candidate_view = _mapping(
            scope.get("candidate_view"), label=f"scope[{scope_ordinal}] candidate view"
        )
        admission = _mapping(
            scope.get("admission"), label=f"scope[{scope_ordinal}] admission"
        )
        _validate_self_hash(
            candidate_view,
            field="fit_candidate_view_sha256",
            label=f"scope[{scope_ordinal}] candidate view",
        )
        _validate_self_hash(
            admission,
            field="admission_sha256",
            label=f"scope[{scope_ordinal}] admission",
        )
        fit_scope_id = scope.get("fit_scope_id")
        if (
            scope.get("schema_version") != lane.SCOPE_SCHEMA
            or type(fit_scope_id) is not str
            or not fit_scope_id
            or scope.get("heldout_block") != heldout
            or scope.get("training_blocks") != training_blocks
            or scope.get("reconstruction_sha256")
            != result.get("reconstruction_sha256")
            or candidate_view.get("fit_scope_id") != fit_scope_id
            or candidate_view.get("training_blocks") != training_blocks
            or candidate_view.get("heldout_block") != heldout
            or candidate_view.get("dose_authority") != runner.AUTHORITATIVE_DOSE
            or candidate_view.get("selection_inputs_exclude_heldout_occurrences")
            is not True
            or admission.get("admission_id") != runner.FULL_UNION_ADMISSION_ID
            or admission.get("fit_scope_id") != fit_scope_id
            or admission.get("dose_authority") != runner.AUTHORITATIVE_DOSE
            or admission.get("uses_simulated_scores") is not False
            or admission.get("uses_matchup_values") is not False
            or scope.get("admission_mode")
            != "complete-fold-eligible-cross-arm-union"
            or scope.get("worlds_per_block") != rw.WORLDS_PER_BLOCK
            or scope.get("dose_authority") != runner.AUTHORITATIVE_DOSE
            or scope.get("require_authoritative") is not True
            or scope.get("strategy_registry") != strategies
            or scope.get("strategy_count") != lane.STRATEGY_COUNT
            or scope.get("book_count") != lane.BOOKS_PER_SCOPE
            or len(books) != lane.BOOKS_PER_SCOPE
            or scope.get("matchup_source_read") is not False
            or scope.get("matchup_admission_read") is not False
            or scope.get("neutral_control_read") is not False
            or scope.get("uses_realized_outcomes") is not False
            or scope.get("promotion_authority") is not False
        ):
            _fail("full-union scope differs")
        admitted_ids, roster_by_id = _validate_candidate_admission(
            candidate_view=candidate_view,
            admission=admission,
            fit_scope_id=fit_scope_id,
            training_blocks=training_blocks,
            heldout_block=heldout,
        )
        for strategy, book in zip(strategies, books, strict=True):
            _validate_book(
                book,
                strategy=strategy,
                heldout_block=heldout,
                training_blocks=training_blocks,
                fit_scope_id=fit_scope_id,
                reconstruction_sha256=str(result["reconstruction_sha256"]),
                admission=admission,
                admitted_ids=admitted_ids,
                roster_by_id=roster_by_id,
                seen_book_ids=seen_book_ids,
            )
    if len(seen_book_ids) != lane.BOOKS_PER_SLATE:
        _fail("full-union book identity count differs")
    return result


def build_receipt_v1(
    *, source_commit_sha: str, panel: Mapping[str, object], execution_result: object,
) -> dict[str, object]:
    commit = _commit(source_commit_sha)
    normalized_panel = _parse_panel(batch.canonical_json_bytes(dict(panel)))
    member = _task0_member(normalized_panel)
    result = _validate_execution_result(execution_result, member=member)
    body = {
        "schema_version": RECEIPT_SCHEMA,
        "smoke_id": SMOKE_ID,
        "mode": "create-once-real-artifact-outcome-blind",
        "source_commit_sha": commit,
        "panel_index_identity": _identity(
            adapter.FIXED_PANEL_IDENTITY, label="fixed panel identity"
        ),
        "panel_index_sha256": adapter.FIXED_PANEL_INDEX_SHA256,
        "accepted_slate_membership_sha256": batch.canonical_sha256(member),
        "production_dose": {
            "blocks": list(rw.WORLD_BLOCKS),
            "worlds_per_block": rw.WORLDS_PER_BLOCK,
            "world_count": WORLD_COUNT,
            "scope_count": lane.SCOPE_COUNT,
            "strategy_count": lane.STRATEGY_COUNT,
            "book_count": lane.BOOKS_PER_SLATE,
            "entry_count": lane.ENTRY_BUDGET,
            "prefix_sizes": list(lane.PREFIX_SIZES),
        },
        "execution_result": result,
        "execution_result_sha256": result["task_result_sha256"],
        "verification": {
            "fixed_panel_generation_exact": True,
            "complete_54_slate_panel_verified": True,
            "task0_membership_verified": True,
            "authoritative_world_dose_verified": True,
            "all_48_exact_80_books_verified": True,
            "catalog_projection_not_used": True,
            "matchup_source_not_read": True,
            "realized_outcomes_not_read": True,
        },
        **{field: False for field in _FALSE_FIELDS},
    }
    return _with_hash(body, field="receipt_sha256")


def validate_receipt_v1(value: object) -> dict[str, object]:
    receipt = _mapping(value, label="task0 smoke receipt")
    _exact_keys(receipt, _RECEIPT_FIELDS, label="task0 smoke receipt")
    _validate_self_hash(receipt, field="receipt_sha256", label="task0 smoke receipt")
    _false_fields(receipt, label="task0 smoke receipt")
    _reject_nested_outcome_or_authority(receipt, label="task0 smoke receipt")
    dose = _mapping(receipt.get("production_dose"), label="production dose")
    verification = _mapping(receipt.get("verification"), label="receipt verification")
    result = _mapping(receipt.get("execution_result"), label="execution result")
    member = _mapping(
        result.get("accepted_slate_membership"), label="execution membership"
    )
    if (
        receipt.get("schema_version") != RECEIPT_SCHEMA
        or receipt.get("smoke_id") != SMOKE_ID
        or receipt.get("mode") != "create-once-real-artifact-outcome-blind"
        or _identity(receipt.get("panel_index_identity"), label="receipt panel")
        != _identity(adapter.FIXED_PANEL_IDENTITY, label="fixed panel")
        or receipt.get("panel_index_sha256") != adapter.FIXED_PANEL_INDEX_SHA256
        or receipt.get("accepted_slate_membership_sha256")
        != batch.canonical_sha256(member)
        or receipt.get("accepted_slate_membership_sha256")
        != FIXED_TASK0_MEMBERSHIP_SHA256
        or dose
        != {
            "blocks": list(rw.WORLD_BLOCKS),
            "worlds_per_block": rw.WORLDS_PER_BLOCK,
            "world_count": WORLD_COUNT,
            "scope_count": lane.SCOPE_COUNT,
            "strategy_count": lane.STRATEGY_COUNT,
            "book_count": lane.BOOKS_PER_SLATE,
            "entry_count": lane.ENTRY_BUDGET,
            "prefix_sizes": list(lane.PREFIX_SIZES),
        }
        or set(verification) != set(_RECEIPT_VERIFICATION_FIELDS)
        or any(value is not True for value in verification.values())
        or receipt.get("execution_result_sha256") != result.get("task_result_sha256")
    ):
        _fail("task0 smoke receipt contract differs")
    _commit(receipt.get("source_commit_sha"))
    _validate_execution_result(result, member=member)
    return receipt


def _preflight_output_path(path: Path) -> None:
    if not path.is_absolute():
        _fail("result output must be an absolute path")
    if path.exists() or path.is_symlink():
        _fail("result output already exists")
    parent = path.parent
    if not parent.is_dir() or parent.resolve() != parent:
        _fail("result output parent must be one existing canonical directory")


def _write_create_once(path: Path, value: Mapping[str, object]) -> None:
    _preflight_output_path(path)
    raw = batch.canonical_json_bytes(dict(value))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise CorpusR6FullUnionTask0SmokeV1Error(
            "result output create-once failed"
        ) from exc
    try:
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written < 1:
                _fail("result output write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def run_production_smoke_v1(
    *,
    result_output: Path,
    repository_factory: Callable[[], object] = adapter.SubprocessGitRepositoryV1,
    backend_factory: Callable[[], object] = adapter.GCSGenerationBackendV1.from_default_client,
    read_generation_exact: Callable[..., bytes] = adapter.read_generation_exact_v1,
    execute: Callable[..., dict[str, object]] = lane.execute_one_accepted_slate_full_union_v1,
) -> dict[str, object]:
    if os.environ.get(PRODUCTION_ENABLE_ENV) != "1":
        _fail(f"production smoke requires {PRODUCTION_ENABLE_ENV}=1")
    _preflight_output_path(result_output)
    repository = repository_factory()
    require_clean = getattr(repository, "require_current_clean_head", None)
    if not callable(require_clean):
        _fail("production repository gate is unavailable")
    source_commit = _commit(require_clean())
    backend = backend_factory()
    transport_method = getattr(backend, "transport", None)
    if not callable(transport_method):
        _fail("generation backend transport is unavailable")
    transport = transport_method()

    def read_exact(identity: Mapping[str, object]) -> bytes:
        return read_generation_exact(identity, transport=transport)

    panel_raw = read_exact(adapter.FIXED_PANEL_IDENTITY)
    if (
        len(panel_raw) != adapter.FIXED_PANEL_IDENTITY["bytes"]
        or sha256(panel_raw).hexdigest() != adapter.FIXED_PANEL_IDENTITY["sha256"]
    ):
        _fail("fixed panel exact-read bytes differ")
    panel = _parse_panel(panel_raw)
    member = _task0_member(panel)
    result = execute(
        validated_panel_index=panel,
        panel_index_identity=adapter.FIXED_PANEL_IDENTITY,
        accepted_slate_membership=member,
        task_acceptance_identity=member["task_acceptance_identity"],
        carrier_identity=member["carrier_identity"],
        read_exact=read_exact,
        worlds_per_block=rw.WORLDS_PER_BLOCK,
        require_authoritative=True,
    )
    receipt = validate_receipt_v1(build_receipt_v1(
        source_commit_sha=source_commit,
        panel=panel,
        execution_result=result,
    ))
    _write_create_once(result_output, receipt)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--result-output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("--execute is required")
    receipt = run_production_smoke_v1(result_output=args.result_output)
    print(batch.canonical_json_bytes(receipt).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
