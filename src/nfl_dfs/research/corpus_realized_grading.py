"""Pure post-acceptance realized grading for the corpus parameter batch.

This module is deliberately downstream of the outcome-blind batch.  It does
not read a warehouse, object storage, process environment, or Neo4j, and it
cannot launch, retry, select, or mutate a corpus run.  Its only input is an
exact, already-accepted 54-task batch evidence graph plus a separately
content-addressed player-outcome bundle.

Scores use signed integer micro-DK points.  Every generated-unique roster is
visited once per task/parameter-set population, and every roster total is the
exact sum of its nine task-keyed player outcomes.  Contest rank and ROI are
intentionally unavailable in v1: player outcomes alone cannot reconstruct a
full field or a payout ladder.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research.corpus_batch_evidence_contract import (
    MICRO_DK_PER_POINT,
    THRESHOLDS_DK,
)


OUTCOME_SCHEMA: Final = "corpus-parametric-actual-player-outcomes/v1"
RESULT_SCHEMA: Final = "corpus-parametric-realized-grade/v1"
VARIANT_RESULT_SCHEMA: Final = "corpus-legal-feasibility-variant-result/v2"
TASK_ACCEPTANCE_SCHEMA: Final = "corpus-parametric-task-acceptance/v1"
BATCH_ACCEPTANCE_SCHEMA: Final = "corpus-parametric-batch-acceptance/v1"
EXPECTED_TASK_COUNT: Final = 54
EXPECTED_PARAMETER_SET_COUNT: Final = 7
EXPECTED_TASK_ARM_COUNT: Final = (
    EXPECTED_TASK_COUNT * EXPECTED_PARAMETER_SET_COUNT
)
EXPECTED_SELECTED_COUNT: Final = 80
MAX_ABS_PLAYER_SCORE_MICRO: Final = ((1 << 63) - 1) // 9

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_UTC_TIMESTAMP: Final = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
)

_ACCEPTED_TASK_KEYS: Final = frozenset({
    "task_result",
    "task_result_identity",
    "task_acceptance",
    "task_acceptance_identity",
    "variant_results",
})
_RETAINED_VARIANT_KEYS: Final = frozenset({"result", "object_identity"})
_OUTCOME_ROW_KEYS: Final = frozenset({
    "task_index", "season", "week", "slate_id", "player_id",
    "realized_score_micro",
})
_OUTCOME_KEYS: Final = frozenset({
    "schema_version", "batch_manifest_sha256", "score_unit",
    "micro_dk_per_point", "source_identity", "row_count", "row_keys_sha256",
    "rows_sha256", "rows", "full_field_standings_included",
    "payout_ladder_included", "outcome_bundle_sha256",
})
_TASK_ACCEPTANCE_KEYS: Final = frozenset({
    "schema_version", "accepted_at_utc", "transport_contract",
    "retrieval_task0_prerequisite_identity", "task_index", "task_sha256",
    "producer_close", "science_terminal", "task_result",
    "verifier_worker_completion", "independent_verification",
    "independent_verification_sha256", "verifier_terminal_execution",
    "terminal_governance_census", "evidence_object_count",
    "complete_evidence_receipt", "independent_verification_complete",
    "strict_verifier_terminal_success", "accepted", "partial_result",
    "automatic_retry_licensed", "uses_realized_outcomes",
    "historical_scoring_licensed", "corpus_fill_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority", "task_acceptance_sha256",
})
_BATCH_ACCEPTANCE_KEYS: Final = frozenset({
    "schema_version", "accepted_at_utc", "transport_contract",
    "retrieval_task0_prerequisite_identity", "batch_mode", "batch_completion",
    "task_acceptances", "task_count", "parameter_set_count",
    "matrix_cell_count", "output_inventory_before_batch_acceptance",
    "output_inventory_before_batch_acceptance_sha256",
    "output_object_count_before_batch_acceptance", "complete", "accepted",
    "partial_result", "independent_verification_complete_for_every_task",
    "automatic_retry_licensed", "uses_realized_outcomes",
    "historical_scoring_licensed", "corpus_fill_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority", "batch_acceptance_sha256",
})
_VARIANT_KEYS: Final = frozenset({
    "schema", "slate", "later_source_freeze_manifest_sha256",
    "artifact_sha256_by_block", "task_source_binding",
    "visit_schedule_sha256", "attempt_ledger_sha256",
    "matrix_authority_sha256", "solver_evidence_task_root_sha256", "profile",
    "runtime_effective_policy", "coverage", "variant_attempt_rows_sha256",
    "visit_rosters", "unique_rosters", "first_occurrence_visit_indices",
    "candidate_score_sha256", "selector", "selected_rosters",
    "selected_score_sha256", "house_rule_violation_census",
    "outcome_columns_read", "uses_realized_outcomes",
    "historical_scoring_licensed", "production_change_licensed",
    "result_sha256",
})
_RESULT_KEYS: Final = frozenset({
    "schema_version", "phase", "batch_id", "accepted_batch_authority",
    "actual_player_outcome_authority", "score_unit", "micro_dk_per_point",
    "thresholds_micro", "coverage", "task_arm_metrics", "contest_metrics",
    "outcome_blind_batch_mutated", "uses_realized_outcomes",
    "historical_retune_licensed", "historical_retry_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority", "realized_grade_sha256",
})


class CorpusRealizedGradingError(ValueError):
    """The post-acceptance grading contract failed closed."""


def canonical_json_bytes(value: object) -> bytes:
    """Return the shared canonical JSON representation."""
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusRealizedGradingError(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusRealizedGradingError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CorpusRealizedGradingError(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise CorpusRealizedGradingError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise CorpusRealizedGradingError(f"{label} must be a canonical string")
    return value


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CorpusRealizedGradingError(f"{label} must be a lowercase SHA-256")
    return value


def _exact_int(
    value: object, *, label: str, minimum: int | None = None,
) -> int:
    if type(value) is not int:
        raise CorpusRealizedGradingError(f"{label} must be an exact integer")
    if minimum is not None and value < minimum:
        raise CorpusRealizedGradingError(f"{label} must be >= {minimum}")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusRealizedGradingError(str(exc)) from exc


def _json_identity(
    value: object, identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return batch.validate_json_identity(value, identity, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusRealizedGradingError(str(exc)) from exc


def _self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if canonical_sha256(body) != retained:
        raise CorpusRealizedGradingError(f"{label} self-hash differs")
    return retained


def _identity_key(value: object, *, label: str) -> tuple[object, ...]:
    identity = _identity(value, label=label)
    return tuple(identity[key] for key in ("uri", "generation", "sha256", "bytes"))


def _canonical_roster(value: object, *, label: str) -> tuple[str, ...]:
    rows = _sequence(value, label=label)
    roster = tuple(_string(player, label=f"{label} player") for player in rows)
    if len(roster) != 9 or len(set(roster)) != 9 or roster != tuple(sorted(roster)):
        raise CorpusRealizedGradingError(
            f"{label} must be one sorted nine-player unique identity"
        )
    return roster


def _validate_task_acceptance(
    value: object,
    *,
    identity: object,
    task: Mapping[str, object],
    task_result_identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    item = dict(_mapping(value, label="task acceptance"))
    _exact_keys(item, _TASK_ACCEPTANCE_KEYS, label="task acceptance")
    retained_identity = _json_identity(
        item, identity, label="task acceptance identity"
    )
    _self_hash(
        item, field="task_acceptance_sha256", label="task acceptance"
    )
    timestamp = item.get("accepted_at_utc")
    false_fields = (
        "automatic_retry_licensed", "uses_realized_outcomes",
        "historical_scoring_licensed", "corpus_fill_licensed",
        "graph_mutation_licensed", "production_change_licensed",
        "decision_authority",
    )
    if (
        item.get("schema_version") != TASK_ACCEPTANCE_SCHEMA
        or type(timestamp) is not str
        or _UTC_TIMESTAMP.fullmatch(timestamp) is None
        or item.get("task_index") != task["task_index"]
        or item.get("task_sha256") != task["task_sha256"]
        or item.get("task_result") != task_result_identity
        or item.get("evidence_object_count") != 140
        or item.get("complete_evidence_receipt") is not True
        or item.get("independent_verification_complete") is not True
        or item.get("strict_verifier_terminal_success") is not True
        or item.get("accepted") is not True
        or item.get("partial_result") is not False
        or any(item.get(field) is not False for field in false_fields)
    ):
        raise CorpusRealizedGradingError("task acceptance law differs")
    for field in (
        "transport_contract", "retrieval_task0_prerequisite_identity",
        "producer_close", "science_terminal", "task_result",
        "verifier_worker_completion", "independent_verification",
    ):
        _identity(item[field], label=f"task acceptance {field}")
    _sha(
        item.get("independent_verification_sha256"),
        label="task acceptance independent verification SHA",
    )
    return item, retained_identity


def _validate_variant_result(
    value: object,
    *,
    identity: object,
    expected_identity: Mapping[str, object],
    task: Mapping[str, object],
    parameter_set: Mapping[str, object],
) -> dict[str, object]:
    item = dict(_mapping(value, label="variant result"))
    _exact_keys(item, _VARIANT_KEYS, label="variant result")
    retained_identity = _json_identity(item, identity, label="variant result identity")
    if retained_identity != expected_identity:
        raise CorpusRealizedGradingError(
            "variant result identity differs from accepted task result"
        )
    _self_hash(item, field="result_sha256", label="variant result")
    slate = _mapping(item.get("slate"), label="variant slate")
    profile = _mapping(item.get("profile"), label="variant profile")
    source_binding = _mapping(
        item.get("task_source_binding"), label="variant task source binding"
    )
    coverage = _mapping(item.get("coverage"), label="variant coverage")
    selector = _mapping(item.get("selector"), label="variant selector")
    if (
        item.get("schema") != VARIANT_RESULT_SCHEMA
        or slate != {
            "season": task["season"],
            "week": task["week"],
            "slate_id": task["slate_id"],
        }
        or source_binding.get("task_index") != task["task_index"]
        or source_binding.get("task_sha256") != task["task_sha256"]
        or profile.get("ordinal") != parameter_set["ordinal"]
        or profile.get("parameter_set_id") != parameter_set["parameter_set_id"]
        or profile.get("parameter_set_sha256")
        != parameter_set["parameter_set_sha256"]
        or profile.get("parameter_values") != parameter_set["values"]
        or item.get("outcome_columns_read") != []
        or item.get("uses_realized_outcomes") is not False
        or item.get("historical_scoring_licensed") is not False
        or item.get("production_change_licensed") is not False
    ):
        raise CorpusRealizedGradingError("variant result task/arm law differs")

    unique = tuple(
        _canonical_roster(raw, label="generated-unique roster")
        for raw in _sequence(item.get("unique_rosters"), label="unique rosters")
    )
    selected = tuple(
        _canonical_roster(raw, label="selected exact-80 roster")
        for raw in _sequence(item.get("selected_rosters"), label="selected rosters")
    )
    if not unique or len(set(unique)) != len(unique):
        raise CorpusRealizedGradingError(
            "generated-unique roster population is empty or duplicated"
        )
    if len(selected) != EXPECTED_SELECTED_COUNT or len(set(selected)) != len(selected):
        raise CorpusRealizedGradingError("selected population is not exact-80 unique")
    selected_indices_raw = _sequence(
        selector.get("selected_indices"), label="selector indices"
    )
    selected_indices = tuple(
        _exact_int(raw, label="selector index", minimum=0)
        for raw in selected_indices_raw
    )
    if (
        len(selected_indices) != EXPECTED_SELECTED_COUNT
        or len(set(selected_indices)) != len(selected_indices)
        or any(index >= len(unique) for index in selected_indices)
        or selected != tuple(unique[index] for index in selected_indices)
        or selector.get("candidate_count") != len(unique)
        or selector.get("entry_count") != EXPECTED_SELECTED_COUNT
        or coverage.get("unique_candidates") != len(unique)
        or coverage.get("selected_entries") != EXPECTED_SELECTED_COUNT
    ):
        raise CorpusRealizedGradingError(
            "selected exact-80 does not replay from generated-unique identities"
        )
    return {
        "item": item,
        "identity": retained_identity,
        "unique_rosters": unique,
        "selected_rosters": selected,
        "selected_indices": selected_indices,
    }


def _validate_batch_acceptance(
    value: object,
    *,
    identity: object,
    completion_identity: Mapping[str, object],
    task_acceptance_identities: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    item = dict(_mapping(value, label="batch acceptance"))
    _exact_keys(item, _BATCH_ACCEPTANCE_KEYS, label="batch acceptance")
    retained_identity = _json_identity(
        item, identity, label="batch acceptance identity"
    )
    _self_hash(item, field="batch_acceptance_sha256", label="batch acceptance")
    timestamp = item.get("accepted_at_utc")
    inventory = _sequence(
        item.get("output_inventory_before_batch_acceptance"),
        label="batch acceptance inventory",
    )
    false_fields = (
        "automatic_retry_licensed", "uses_realized_outcomes",
        "historical_scoring_licensed", "corpus_fill_licensed",
        "graph_mutation_licensed", "production_change_licensed",
        "decision_authority",
    )
    if (
        item.get("schema_version") != BATCH_ACCEPTANCE_SCHEMA
        or type(timestamp) is not str
        or _UTC_TIMESTAMP.fullmatch(timestamp) is None
        or item.get("batch_mode") != "complete-54-task"
        or item.get("batch_completion") != completion_identity
        or item.get("task_acceptances") != list(task_acceptance_identities)
        or item.get("task_count") != EXPECTED_TASK_COUNT
        or item.get("parameter_set_count") != EXPECTED_PARAMETER_SET_COUNT
        or item.get("matrix_cell_count") != EXPECTED_TASK_ARM_COUNT
        or item.get("complete") is not True
        or item.get("accepted") is not True
        or item.get("partial_result") is not False
        or item.get("independent_verification_complete_for_every_task") is not True
        or any(item.get(field) is not False for field in false_fields)
        or item.get("output_object_count_before_batch_acceptance") != len(inventory)
        or item.get("output_inventory_before_batch_acceptance_sha256")
        != canonical_sha256(inventory)
    ):
        raise CorpusRealizedGradingError("batch acceptance law differs")
    if len({_identity_key(row, label="task acceptance identity") for row in (
        task_acceptance_identities
    )}) != EXPECTED_TASK_COUNT:
        raise CorpusRealizedGradingError("task acceptance identities repeat")
    return item, retained_identity


def _normalize_outcome_row(
    value: object,
    *,
    manifest: Mapping[str, object],
    label: str,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, _OUTCOME_ROW_KEYS, label=label)
    task_index = _exact_int(item.get("task_index"), label=f"{label}.task_index", minimum=0)
    tasks = manifest["tasks"]
    if task_index >= len(tasks):
        raise CorpusRealizedGradingError(f"{label} task index is outside the batch")
    task = tasks[task_index]
    player_id = _string(item.get("player_id"), label=f"{label}.player_id")
    score = _exact_int(item.get("realized_score_micro"), label=f"{label}.score")
    if abs(score) > MAX_ABS_PLAYER_SCORE_MICRO:
        raise CorpusRealizedGradingError(f"{label} score exceeds exact sum range")
    normalized = {
        "task_index": task_index,
        "season": _exact_int(item.get("season"), label=f"{label}.season"),
        "week": _exact_int(item.get("week"), label=f"{label}.week"),
        "slate_id": _string(item.get("slate_id"), label=f"{label}.slate_id"),
        "player_id": player_id,
        "realized_score_micro": score,
    }
    if (
        normalized["season"] != task["season"]
        or normalized["week"] != task["week"]
        or normalized["slate_id"] != task["slate_id"]
    ):
        raise CorpusRealizedGradingError(
            f"{label} task/slate identity differs from the accepted batch"
        )
    return normalized


def build_actual_player_outcomes(
    *,
    batch_manifest: Mapping[str, object],
    source_identity: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build a canonical, self-hashed exact-micro-DK outcome bundle.

    This helper performs no read.  ``source_identity`` identifies the retained
    upstream extract/query authority from which the caller constructed the
    rows; the eventual outcome-bundle identity is supplied separately to the
    grader.
    """
    try:
        manifest = batch.validate_batch_manifest(batch_manifest)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusRealizedGradingError(str(exc)) from exc
    if len(manifest["tasks"]) != EXPECTED_TASK_COUNT:
        raise CorpusRealizedGradingError("actual outcomes require the complete 54-task batch")
    source = _identity(source_identity, label="actual outcome source identity")
    normalized = [
        _normalize_outcome_row(raw, manifest=manifest, label=f"outcome row[{ordinal}]")
        for ordinal, raw in enumerate(rows)
    ]
    normalized.sort(key=lambda row: (row["task_index"], row["player_id"]))
    keys = [(row["task_index"], row["player_id"]) for row in normalized]
    if not normalized or len(keys) != len(set(keys)):
        raise CorpusRealizedGradingError("actual outcome task/player keys repeat or are empty")
    row_keys = [{
        "task_index": row["task_index"],
        "season": row["season"],
        "week": row["week"],
        "slate_id": row["slate_id"],
        "player_id": row["player_id"],
    } for row in normalized]
    body: dict[str, object] = {
        "schema_version": OUTCOME_SCHEMA,
        "batch_manifest_sha256": manifest["batch_manifest_sha256"],
        "score_unit": "micro_dk",
        "micro_dk_per_point": MICRO_DK_PER_POINT,
        "source_identity": source,
        "row_count": len(normalized),
        "row_keys_sha256": canonical_sha256(row_keys),
        "rows_sha256": canonical_sha256(normalized),
        "rows": normalized,
        "full_field_standings_included": False,
        "payout_ladder_included": False,
    }
    body["outcome_bundle_sha256"] = canonical_sha256(body)
    return body


def _validate_actual_player_outcomes(
    value: object,
    *,
    identity: object,
    manifest: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[tuple[int, str], int]]:
    item = dict(_mapping(value, label="actual player outcomes"))
    _exact_keys(item, _OUTCOME_KEYS, label="actual player outcomes")
    retained_identity = _json_identity(
        item, identity, label="actual player outcomes identity"
    )
    _self_hash(
        item, field="outcome_bundle_sha256", label="actual player outcomes"
    )
    raw_rows = _sequence(item.get("rows"), label="actual outcome rows")
    normalized = [
        _normalize_outcome_row(raw, manifest=manifest, label=f"outcome row[{ordinal}]")
        for ordinal, raw in enumerate(raw_rows)
    ]
    expected_order = sorted(
        normalized, key=lambda row: (row["task_index"], row["player_id"])
    )
    keys = [(row["task_index"], row["player_id"]) for row in normalized]
    row_keys = [{
        "task_index": row["task_index"],
        "season": row["season"],
        "week": row["week"],
        "slate_id": row["slate_id"],
        "player_id": row["player_id"],
    } for row in normalized]
    if (
        item.get("schema_version") != OUTCOME_SCHEMA
        or item.get("batch_manifest_sha256") != manifest["batch_manifest_sha256"]
        or item.get("score_unit") != "micro_dk"
        or item.get("micro_dk_per_point") != MICRO_DK_PER_POINT
        or item.get("source_identity")
        != _identity(item.get("source_identity"), label="actual outcome source identity")
        or item.get("row_count") != len(normalized)
        or normalized != expected_order
        or len(keys) != len(set(keys))
        or item.get("row_keys_sha256") != canonical_sha256(row_keys)
        or item.get("rows_sha256") != canonical_sha256(normalized)
        or item.get("full_field_standings_included") is not False
        or item.get("payout_ladder_included") is not False
    ):
        raise CorpusRealizedGradingError("actual player outcome bundle law differs")
    return item, retained_identity, {
        key: row["realized_score_micro"] for key, row in zip(keys, normalized, strict=True)
    }


def _score_rosters(
    rosters: Sequence[tuple[str, ...]],
    *,
    task_index: int,
    player_scores: Mapping[tuple[int, str], int],
) -> tuple[list[int], list[dict[str, object]]]:
    scores: list[int] = []
    rows: list[dict[str, object]] = []
    for roster in rosters:
        try:
            score = sum(player_scores[(task_index, player)] for player in roster)
        except KeyError as exc:
            raise CorpusRealizedGradingError(
                "a generated-unique roster lacks an exact task-keyed player outcome"
            ) from exc
        scores.append(score)
        rows.append({
            "roster_identity_sha256": canonical_sha256(list(roster)),
            "realized_score_micro": score,
        })
    if len(rows) != len(rosters):
        raise AssertionError("roster scoring coverage is internally inconsistent")
    return scores, rows


def grade_accepted_batch(
    *,
    batch_manifest: Mapping[str, object],
    batch_manifest_identity: Mapping[str, object],
    batch_completion: Mapping[str, object],
    batch_completion_identity: Mapping[str, object],
    batch_acceptance: Mapping[str, object],
    batch_acceptance_identity: Mapping[str, object],
    accepted_tasks: Sequence[Mapping[str, object]],
    actual_player_outcomes: Mapping[str, object],
    actual_player_outcomes_identity: Mapping[str, object],
    contest_outcomes: object | None = None,
) -> dict[str, object]:
    """Grade every accepted task/arm roster without mutating its source batch.

    ``contest_outcomes`` is reserved.  V1 rejects any supplied value because a
    safe rank/ROI implementation needs independently validated full-field
    standings, settlement, duplicate-entry, tie, and payout-ladder semantics.
    """
    if contest_outcomes is not None:
        raise CorpusRealizedGradingError(
            "contest rank/ROI requires a separately validated full-field "
            "standings and payout-ladder schema"
        )
    try:
        manifest = batch.validate_batch_manifest(batch_manifest)
        manifest_identity = batch.validate_json_identity(
            manifest, batch_manifest_identity, label="batch manifest identity"
        )
    except batch.CorpusParametricBatchError as exc:
        raise CorpusRealizedGradingError(str(exc)) from exc
    if len(manifest["tasks"]) != EXPECTED_TASK_COUNT:
        raise CorpusRealizedGradingError(
            "realized grading requires exact complete 54-task batch coverage"
        )
    normalized_outcome_identity = _identity(
        actual_player_outcomes_identity,
        label="actual player outcomes identity",
    )
    if normalized_outcome_identity["uri"].startswith(manifest["output_prefix"]):
        raise CorpusRealizedGradingError(
            "realized outcomes must be outside the immutable outcome-blind batch prefix"
        )
    raw_accepted_tasks = _sequence(accepted_tasks, label="accepted tasks")
    if len(raw_accepted_tasks) != EXPECTED_TASK_COUNT:
        raise CorpusRealizedGradingError(
            "accepted task evidence does not cover all 54 tasks"
        )

    retained_results: list[dict[str, object]] = []
    task_acceptance_identities: list[dict[str, object]] = []
    variant_populations: list[dict[str, object]] = []
    for task_index, (raw_task, task) in enumerate(
        zip(raw_accepted_tasks, manifest["tasks"], strict=True)
    ):
        retained = _mapping(raw_task, label=f"accepted task[{task_index}]")
        _exact_keys(retained, _ACCEPTED_TASK_KEYS, label=f"accepted task[{task_index}]")
        try:
            task_result = batch.validate_task_result_receipt(
                retained["task_result"],
                batch_manifest=manifest,
                batch_manifest_identity=manifest_identity,
            )
            task_result_identity = batch.validate_json_identity(
                task_result,
                retained["task_result_identity"],
                label=f"task[{task_index}] result identity",
            )
        except batch.CorpusParametricBatchError as exc:
            raise CorpusRealizedGradingError(str(exc)) from exc
        if task_result["task_index"] != task_index:
            raise CorpusRealizedGradingError("accepted task results are reordered")
        task_acceptance, task_acceptance_identity = _validate_task_acceptance(
            retained["task_acceptance"],
            identity=retained["task_acceptance_identity"],
            task=task,
            task_result_identity=task_result_identity,
        )
        del task_acceptance
        task_acceptance_identities.append(task_acceptance_identity)
        retained_results.append({
            "receipt": task_result,
            "object_identity": task_result_identity,
        })
        raw_variants = _sequence(
            retained["variant_results"], label=f"task[{task_index}] variant results"
        )
        if len(raw_variants) != EXPECTED_PARAMETER_SET_COUNT:
            raise CorpusRealizedGradingError(
                "accepted task does not contain all seven variant results"
            )
        for ordinal, (raw_variant, parameter_set, result_binding) in enumerate(
            zip(
                raw_variants,
                manifest["parameter_sets"],
                task_result["variant_results"],
                strict=True,
            )
        ):
            variant_row = _mapping(
                raw_variant, label=f"task[{task_index}] variant[{ordinal}]"
            )
            _exact_keys(
                variant_row,
                _RETAINED_VARIANT_KEYS,
                label=f"task[{task_index}] variant[{ordinal}]",
            )
            variant = _validate_variant_result(
                variant_row["result"],
                identity=variant_row["object_identity"],
                expected_identity=result_binding["result_object"],
                task=task,
                parameter_set=parameter_set,
            )
            variant_populations.append({
                "task_index": task_index,
                "task": task,
                "parameter_set": parameter_set,
                **variant,
            })

    try:
        completion = batch.validate_batch_completion_receipt(
            batch_completion,
            batch_manifest=manifest,
            batch_manifest_identity=manifest_identity,
            retained_task_results=retained_results,
        )
        completion_identity = batch.validate_json_identity(
            completion,
            batch_completion_identity,
            label="batch completion identity",
        )
    except batch.CorpusParametricBatchError as exc:
        raise CorpusRealizedGradingError(str(exc)) from exc
    acceptance, acceptance_identity = _validate_batch_acceptance(
        batch_acceptance,
        identity=batch_acceptance_identity,
        completion_identity=completion_identity,
        task_acceptance_identities=task_acceptance_identities,
    )
    if acceptance["transport_contract"] != raw_accepted_tasks[0][
        "task_acceptance"
    ]["transport_contract"] or any(
        raw["task_acceptance"]["transport_contract"]
        != acceptance["transport_contract"]
        or raw["task_acceptance"]["retrieval_task0_prerequisite_identity"]
        != acceptance["retrieval_task0_prerequisite_identity"]
        for raw in raw_accepted_tasks
    ):
        raise CorpusRealizedGradingError(
            "task and batch acceptances do not share one transport/prerequisite"
        )

    outcome_bundle, outcome_identity, player_scores = (
        _validate_actual_player_outcomes(
            actual_player_outcomes,
            identity=normalized_outcome_identity,
            manifest=manifest,
        )
    )
    required_player_keys = {
        (int(population["task_index"]), player)
        for population in variant_populations
        for roster in population["unique_rosters"]
        for player in roster
    }
    observed_player_keys = set(player_scores)
    if observed_player_keys != required_player_keys:
        raise CorpusRealizedGradingError(
            "actual player outcome keys do not exactly equal the complete "
            "generated-unique player union"
        )

    thresholds_micro = [value * MICRO_DK_PER_POINT for value in THRESHOLDS_DK]
    metric_rows: list[dict[str, object]] = []
    generated_memberships = 0
    selected_memberships = 0
    task_distinct_rosters: dict[int, set[tuple[str, ...]]] = {
        task_index: set() for task_index in range(EXPECTED_TASK_COUNT)
    }
    for population in variant_populations:
        task_index = int(population["task_index"])
        task = population["task"]
        parameter_set = population["parameter_set"]
        unique = population["unique_rosters"]
        selected = population["selected_rosters"]
        candidate_scores, candidate_rows = _score_rosters(
            unique, task_index=task_index, player_scores=player_scores
        )
        # Project exact-80 from the one complete generated-unique scoring pass;
        # never sum any selected roster a second time.
        selected_indices = population["selected_indices"]
        selected_scores = [candidate_scores[index] for index in selected_indices]
        selected_rows = [candidate_rows[index] for index in selected_indices]
        candidate_ceiling = max(candidate_scores)
        selected_maximum = max(selected_scores)
        gap = candidate_ceiling - selected_maximum
        if gap < 0:
            raise AssertionError("exact-80 maximum exceeded its candidate superset")
        generated_memberships += len(unique)
        selected_memberships += len(selected)
        task_distinct_rosters[task_index].update(unique)
        threshold_counts = [{
            "threshold_micro": threshold,
            "generated_unique_at_or_above_count": sum(
                score >= threshold for score in candidate_scores
            ),
            "selected_exact80_at_or_above_count": sum(
                score >= threshold for score in selected_scores
            ),
        } for threshold in thresholds_micro]
        endpoints = [
            {
                "endpoint_id": "endpoint:corpus:realized-scored-generated-unique-count",
                "population_stage": "generated_unique",
                "unit": "lineups",
                "value": len(unique),
            },
            {
                "endpoint_id": "endpoint:corpus:realized-candidate-ceiling-c",
                "population_stage": "generated_unique",
                "unit": "micro_dk",
                "value": candidate_ceiling,
            },
            {
                "endpoint_id": "endpoint:corpus:realized-exact80-maximum-s",
                "population_stage": "selected_exact80",
                "unit": "micro_dk",
                "value": selected_maximum,
            },
            {
                "endpoint_id": "endpoint:corpus:realized-conversion-gap-c-minus-s",
                "population_stage": "selected_exact80",
                "unit": "micro_dk",
                "value": gap,
            },
        ]
        metric_body: dict[str, object] = {
            "metric_key": (
                f"{manifest['batch_id']}:task-{task_index:04d}:"
                f"{parameter_set['parameter_set_id']}"
            ),
            "task_index": task_index,
            "season": task["season"],
            "week": task["week"],
            "slate_id": task["slate_id"],
            "parameter_set_ordinal": parameter_set["ordinal"],
            "parameter_set_id": parameter_set["parameter_set_id"],
            "parameter_set_sha256": parameter_set["parameter_set_sha256"],
            "variant_result_identity": population["identity"],
            "variant_result_sha256": population["item"]["result_sha256"],
            "generated_unique_roster_count": len(unique),
            "realized_scored_generated_unique_count": len(candidate_rows),
            "selected_exact80_roster_count": len(selected),
            "realized_scored_selected_exact80_count": len(selected_rows),
            "generated_unique_roster_identity_sha256": canonical_sha256(
                [list(roster) for roster in unique]
            ),
            "selected_exact80_roster_identity_sha256": canonical_sha256(
                [list(roster) for roster in selected]
            ),
            "generated_unique_realized_score_rows_sha256": canonical_sha256(
                candidate_rows
            ),
            "selected_exact80_realized_score_rows_sha256": canonical_sha256(
                selected_rows
            ),
            "threshold_counts": threshold_counts,
            "endpoints": endpoints,
            "complete_generated_unique_roster_coverage": True,
            "complete_selected_exact80_roster_coverage": True,
        }
        metric_body["task_arm_metric_sha256"] = canonical_sha256(metric_body)
        metric_rows.append(metric_body)

    distinct_task_roster_count = sum(len(rows) for rows in task_distinct_rosters.values())
    coverage = {
        "task_count": EXPECTED_TASK_COUNT,
        "parameter_set_count": EXPECTED_PARAMETER_SET_COUNT,
        "task_arm_count": EXPECTED_TASK_ARM_COUNT,
        "generated_unique_membership_count": generated_memberships,
        "realized_scored_generated_unique_membership_count": generated_memberships,
        "selected_exact80_membership_count": selected_memberships,
        "realized_scored_selected_exact80_membership_count": selected_memberships,
        "distinct_task_roster_count": distinct_task_roster_count,
        "actual_player_outcome_row_count": len(player_scores),
        "endpoint_measurement_count": EXPECTED_TASK_ARM_COUNT * 4,
        "all_tasks_accepted": True,
        "all_task_arms_present": True,
        "every_generated_unique_roster_scored_exactly_once_per_task_arm": True,
        "every_selected_exact80_roster_scored_exactly_once_per_task_arm": True,
        "actual_player_outcome_keys_exact": True,
        "complete": True,
    }
    result: dict[str, object] = {
        "schema_version": RESULT_SCHEMA,
        "phase": "post_acceptance_realized_historical",
        "batch_id": manifest["batch_id"],
        "accepted_batch_authority": {
            "batch_manifest": manifest_identity,
            "batch_manifest_sha256": manifest["batch_manifest_sha256"],
            "batch_completion": completion_identity,
            "batch_completion_sha256": completion["batch_completion_sha256"],
            "batch_acceptance": acceptance_identity,
            "batch_acceptance_sha256": acceptance["batch_acceptance_sha256"],
            "task_acceptance_identity_set_sha256": canonical_sha256(
                task_acceptance_identities
            ),
        },
        "actual_player_outcome_authority": {
            "outcome_bundle": outcome_identity,
            "outcome_bundle_sha256": outcome_bundle["outcome_bundle_sha256"],
            "source_identity": outcome_bundle["source_identity"],
            "row_count": outcome_bundle["row_count"],
            "row_keys_sha256": outcome_bundle["row_keys_sha256"],
            "rows_sha256": outcome_bundle["rows_sha256"],
        },
        "score_unit": "micro_dk",
        "micro_dk_per_point": MICRO_DK_PER_POINT,
        "thresholds_micro": thresholds_micro,
        "coverage": coverage,
        "task_arm_metrics": metric_rows,
        "contest_metrics": {
            "availability": "unavailable",
            "reason": "full_field_standings_and_payout_ladder_not_supplied",
            "full_field_standings_identity": None,
            "payout_ladder_identity": None,
            "rank": None,
            "roi_micro_usd": None,
        },
        "outcome_blind_batch_mutated": False,
        "uses_realized_outcomes": True,
        "historical_retune_licensed": False,
        "historical_retry_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    result["realized_grade_sha256"] = canonical_sha256(result)
    return validate_realized_grade(result)


def validate_realized_grade(value: object) -> dict[str, object]:
    """Validate the canonical result envelope and graph-facing row coverage."""
    item = dict(_mapping(value, label="realized grade"))
    _exact_keys(item, _RESULT_KEYS, label="realized grade")
    _self_hash(item, field="realized_grade_sha256", label="realized grade")
    coverage = _mapping(item.get("coverage"), label="realized grade coverage")
    metrics = _sequence(item.get("task_arm_metrics"), label="task-arm metrics")
    contest = _mapping(item.get("contest_metrics"), label="contest metrics")
    if (
        item.get("schema_version") != RESULT_SCHEMA
        or item.get("phase") != "post_acceptance_realized_historical"
        or item.get("score_unit") != "micro_dk"
        or item.get("micro_dk_per_point") != MICRO_DK_PER_POINT
        or item.get("thresholds_micro")
        != [value * MICRO_DK_PER_POINT for value in THRESHOLDS_DK]
        or len(metrics) != EXPECTED_TASK_ARM_COUNT
        or coverage.get("task_count") != EXPECTED_TASK_COUNT
        or coverage.get("parameter_set_count") != EXPECTED_PARAMETER_SET_COUNT
        or coverage.get("task_arm_count") != EXPECTED_TASK_ARM_COUNT
        or coverage.get("endpoint_measurement_count") != EXPECTED_TASK_ARM_COUNT * 4
        or coverage.get("complete") is not True
        or contest != {
            "availability": "unavailable",
            "reason": "full_field_standings_and_payout_ladder_not_supplied",
            "full_field_standings_identity": None,
            "payout_ladder_identity": None,
            "rank": None,
            "roi_micro_usd": None,
        }
        or item.get("outcome_blind_batch_mutated") is not False
        or item.get("uses_realized_outcomes") is not True
        or any(item.get(field) is not False for field in (
            "historical_retune_licensed", "historical_retry_licensed",
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
    ):
        raise CorpusRealizedGradingError("realized grade law differs")
    expected_order = [
        (task_index, ordinal)
        for task_index in range(EXPECTED_TASK_COUNT)
        for ordinal in range(EXPECTED_PARAMETER_SET_COUNT)
    ]
    observed_order: list[tuple[int, int]] = []
    for row_index, raw in enumerate(metrics):
        row = _mapping(raw, label=f"task-arm metric[{row_index}]")
        _self_hash(
            row, field="task_arm_metric_sha256",
            label=f"task-arm metric[{row_index}]",
        )
        observed_order.append((
            _exact_int(row.get("task_index"), label="metric task index", minimum=0),
            _exact_int(
                row.get("parameter_set_ordinal"), label="metric arm ordinal", minimum=0
            ),
        ))
        endpoints = _sequence(row.get("endpoints"), label="metric endpoints")
        if (
            len(endpoints) != 4
            or row.get("generated_unique_roster_count")
            != row.get("realized_scored_generated_unique_count")
            or row.get("selected_exact80_roster_count") != EXPECTED_SELECTED_COUNT
            or row.get("realized_scored_selected_exact80_count")
            != EXPECTED_SELECTED_COUNT
            or row.get("complete_generated_unique_roster_coverage") is not True
            or row.get("complete_selected_exact80_roster_coverage") is not True
        ):
            raise CorpusRealizedGradingError("task-arm metric coverage differs")
        endpoint_map = {
            endpoint["endpoint_id"]: endpoint["value"]
            for endpoint in endpoints
        }
        candidate = endpoint_map.get(
            "endpoint:corpus:realized-candidate-ceiling-c"
        )
        selected = endpoint_map.get(
            "endpoint:corpus:realized-exact80-maximum-s"
        )
        gap = endpoint_map.get(
            "endpoint:corpus:realized-conversion-gap-c-minus-s"
        )
        if (
            len(endpoint_map) != 4
            or type(candidate) is not int
            or type(selected) is not int
            or type(gap) is not int
            or gap != candidate - selected
            or gap < 0
        ):
            raise CorpusRealizedGradingError("task-arm endpoint values differ")
    if observed_order != expected_order:
        raise CorpusRealizedGradingError("task-arm metric order/coverage differs")
    return item


__all__ = [
    "CorpusRealizedGradingError",
    "EXPECTED_PARAMETER_SET_COUNT",
    "EXPECTED_TASK_ARM_COUNT",
    "EXPECTED_TASK_COUNT",
    "OUTCOME_SCHEMA",
    "RESULT_SCHEMA",
    "build_actual_player_outcomes",
    "canonical_json_bytes",
    "canonical_sha256",
    "grade_accepted_batch",
    "validate_realized_grade",
]
