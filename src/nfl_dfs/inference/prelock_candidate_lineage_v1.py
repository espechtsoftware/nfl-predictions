"""Outcome-free immutable contract for complete pre-lock lineup lineage.

This module is deliberately pure: it performs no I/O, scoring, generation,
selection, graph access, or application work.  It validates and self-hashes a
caller-supplied trace after those pre-lock mechanics have completed.

The contract keeps solve-request yield separate from roster-localized lineage.
An error, infeasible solve, or exhausted request has no roster identity.  A
roster enters the trace only through a successful generated occurrence, and an
exact duplicate normally contributes provenance rather than a lineup loss.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from math import isfinite
from typing import Final

SIDECAR_SCHEMA: Final = "prelock-candidate-lineage-sidecar/v1"
RUN_HEADER_SCHEMA: Final = "prelock-lineage-run-header/v1"
ROSTER_IDENTITY_SCHEMA: Final = "prelock-cross-namespace-roster/v1"
PROPOSAL_REQUEST_SCHEMA: Final = "prelock-proposal-request/v1"
SOLVE_ATTEMPT_SCHEMA: Final = "prelock-solve-attempt/v1"
GENERATED_OCCURRENCE_SCHEMA: Final = "prelock-generated-occurrence/v1"
DEDUPE_DECISION_SCHEMA: Final = "prelock-dedupe-decision/v1"
ADMISSION_DECISION_SCHEMA: Final = "prelock-admission-decision/v1"
STRATEGY_DECISION_SCHEMA: Final = "prelock-strategy-decision/v1"
BOOK_TRANSITION_SCHEMA: Final = "prelock-book-transition/v1"
PREPARED_ENTRY_SCHEMA: Final = "prelock-prepared-entry/v1"

CANDIDATE_UNIVERSE_SCOPE: Final = "OBSERVED_GENERATED_ROSTERS_ONLY"
ROSTER_CANONICALIZATION: Final = "sorted-string-id-array-canonical-json-v1"
HASH_ALGORITHM: Final = "sha256"

REQUEST_STATUSES: Final = frozenset(
    {
        "PRODUCED",
        "INFEASIBLE",
        "SOLVER_ERROR",
        "EXHAUSTED_NOT_ATTEMPTED",
    }
)
SOLVE_STATUSES: Final = frozenset(
    {
        "PRODUCED",
        "INFEASIBLE",
        "SOLVER_ERROR",
    }
)
DEDUPE_DISPOSITIONS: Final = frozenset(
    {
        "FIRST_SEEN",
        "DUPLICATE_SAME_FAMILY",
        "DUPLICATE_CROSS_FAMILY",
        "DUPLICATE_CROSS_SEED",
    }
)
ADMISSION_REASONS: Final = {
    "RETAINED_NATIVE": "RETAINED",
    "DROPPED_POOL_CAP": "REJECTED",
    "RETAINED_FIRST_SOURCE_QUOTA": "RETAINED",
    "RETAINED_DEFICIT_FILL": "RETAINED",
    "DROPPED_EARLIER_SEED_DUPLICATE": "REJECTED",
    "DROPPED_FIXED_BUDGET": "REJECTED",
    "TRANSFORM_RETAINED": "RETAINED",
    "TRANSFORM_EXCLUDED": "REJECTED",
}
ELIGIBILITY_REASONS: Final = frozenset({"EFFECTIVE_CANDIDATE"})
STRATEGY_DECISION_REASONS: Final = {
    "SELECTED_COVERAGE_PHASE": "SELECTED",
    "SELECTED_SATURATION_FILL": "SELECTED",
    "NOT_SELECTED_BOOK_FULL": "NOT_SELECTED",
    "NOT_SELECTED_FILL_ORDER": "NOT_SELECTED",
}
SELECTION_PHASES: Final = frozenset(
    {
        "COVERAGE",
        "SATURATION_FILL",
        "TERMINAL",
    }
)
BOOK_TRANSITION_REASONS: Final = {
    "RETAINED_POSTSELECTOR": "RETAINED",
    "EXPORT_REORDER_ONLY": "RETAINED",
    "REPLACED_BY_PEAK_SLICE": "REMOVED",
    "REPLACED_FOR_THESIS": "REMOVED",
    "ADDED_BY_PEAK_SLICE": "ADDED",
    "ADDED_FOR_THESIS": "ADDED",
}
PREPARED_ENTRY_STATUSES: Final = frozenset({"PREPARED_NOT_CONFIRMED"})

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

# These names are intentionally broader than the exact record schemas.  The
# recursive check protects future wrappers from placing an outcome inside a
# nested metadata object that an older validator did not anticipate.
_FORBIDDEN_OUTCOME_KEYS = frozenset(
    {
        "actual",
        "actual_points",
        "actual_rank",
        "actual_score",
        "field_ownership",
        "field_rank",
        "final_points",
        "final_rank",
        "outcome",
        "outcome_fields",
        "outcome_release",
        "outcomes",
        "ownership",
        "payout",
        "payout_micro",
        "prize",
        "profit",
        "realized",
        "realized_points",
        "realized_rank",
        "realized_score",
        "realized_score_micro",
        "roi",
        "winner",
        "winner_score",
        "winning_score",
    }
)
_ALLOWED_BOUNDARY_KEYS = frozenset(
    {
        "outcome_authority",
        "post_lock_data_read",
        "uses_realized_outcomes",
    }
)
_FORBIDDEN_OUTCOME_TOKENS = frozenset(
    {
        "actual",
        "outcome",
        "outcomes",
        "ownership",
        "payout",
        "prize",
        "profit",
        "realized",
        "roi",
        "winner",
        "winning",
    }
)

_RUN_HEADER_FIELDS = frozenset(
    {
        "run_id",
        "run_type",
        "season",
        "week",
        "slate_id",
        "draft_group_id",
        "contest_id",
        "slate_lock_at_utc",
        "frozen_at_utc",
        "entry_budget",
        "policy_id",
        "selector_ids",
        "effective_candidate_stage_id",
        "paid_strategy_id",
        "code_sha256",
        "input_source_identities",
    }
)
_ROSTER_FIELDS = frozenset(
    {
        "slate_id",
        "internal_player_id_namespace",
        "draftable_player_id_namespace",
        "player_id_bridge",
        "salary_catalog_sha256",
        "legacy_lineup_ids",
    }
)
_PROPOSAL_FIELDS = frozenset(
    {
        "request_id",
        "request_ordinal",
        "source_label",
        "family",
        "requested_ordinal",
        "world_id",
        "generator_config_sha256",
        "terminal_status",
    }
)
_SOLVE_FIELDS = frozenset(
    {
        "attempt_id",
        "attempt_ordinal",
        "request_id",
        "retry_ordinal",
        "status",
        "roster_id",
    }
)
_OCCURRENCE_FIELDS = frozenset(
    {
        "occurrence_id",
        "occurrence_ordinal",
        "attempt_id",
        "request_id",
        "roster_id",
    }
)
_DEDUPE_FIELDS = frozenset(
    {
        "decision_id",
        "occurrence_id",
        "roster_id",
        "disposition",
        "duplicate_of_occurrence_id",
    }
)
_ADMISSION_FIELDS = frozenset(
    {
        "decision_id",
        "stage_id",
        "stage_ordinal",
        "candidate_instance_id",
        "candidate_ordinal",
        "roster_id",
        "source_occurrence_ids",
        "input_candidate_instance_ids",
        "admission_preset_id",
        "disposition",
        "reason",
    }
)
_STRATEGY_FIELDS = frozenset(
    {
        "decision_id",
        "strategy_id",
        "candidate_instance_id",
        "roster_id",
        "candidate_ordinal",
        "eligibility",
        "eligibility_reason",
        "decision",
        "decision_reason",
        "selector_rank",
        "selection_phase",
        "fresh_world_count",
        "individual_clear_count",
        "p_line",
        "mean_simulated_total",
        "tiebreak_values",
    }
)
_BOOK_FIELDS = frozenset(
    {
        "transition_id",
        "strategy_id",
        "candidate_instance_id",
        "roster_id",
        "selector_rank",
        "postselector_rank",
        "export_rank",
        "disposition",
        "reason",
    }
)
_PREPARED_FIELDS = frozenset(
    {
        "prepared_entry_id",
        "strategy_id",
        "candidate_instance_id",
        "roster_id",
        "contest_id",
        "entry_id",
        "entry_row_ordinal",
        "export_rank",
        "filled_csv_sha256",
        "paid_export_receipt_sha256",
        "status",
    }
)


class PrelockCandidateLineageError(ValueError):
    """A pre-lock lineage sidecar violated its closed contract."""


def _fail(message: str) -> None:
    raise PrelockCandidateLineageError(message)


def canonical_json_bytes(value: object) -> bytes:
    """Return deterministic JSON bytes for hashing and create-once storage."""

    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise PrelockCandidateLineageError(
            "pre-lock lineage value is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def assert_outcome_free(value: object, *, path: str = "root") -> None:
    """Recursively reject outcome-bearing field names at any nesting depth."""

    if isinstance(value, Mapping):
        for key, nested in value.items():
            if type(key) is not str:
                _fail(f"{path} contains a non-string key")
            normalized = key.strip().lower().replace("-", "_")
            tokens = frozenset(normalized.split("_"))
            if (
                normalized in _FORBIDDEN_OUTCOME_KEYS
                or bool(tokens & _FORBIDDEN_OUTCOME_TOKENS)
                or normalized in {"final_score", "final_rank", "final_points"}
            ) and normalized not in _ALLOWED_BOUNDARY_KEYS:
                _fail(f"{path}.{key} is an outcome-bearing field")
            assert_outcome_free(nested, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, nested in enumerate(value):
            assert_outcome_free(nested, path=f"{path}[{index}]")


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed mapping")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _exact_fields(value: object, fields: frozenset[str], *, label: str) -> dict:
    item = _mapping(value, label=label)
    if set(item) != fields:
        _fail(
            f"{label} fields differ: missing={sorted(fields - set(item))}, "
            f"extra={sorted(set(item) - fields)}"
        )
    return item


def _identifier(value: object, *, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        _fail(f"{label} is not a canonical identifier")
    return value


def _text(value: object, *, label: str, maximum: int = 512) -> str:
    if (
        type(value) is not str
        or not value
        or value.strip() != value
        or len(value.encode("utf-8")) > maximum
    ):
        _fail(f"{label} is not canonical text")
    return value


def _optional_text(value: object, *, label: str, maximum: int = 512) -> str | None:
    if value is None:
        return None
    return _text(value, label=label, maximum=maximum)


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _optional_integer(value: object, *, label: str, minimum: int = 0) -> int | None:
    if value is None:
        return None
    return _integer(value, label=label, minimum=minimum)


def _optional_number(
    value: object,
    *,
    label: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{label} must be a finite number or null")
    normalized = float(value)
    if not isfinite(normalized):
        _fail(f"{label} must be a finite number or null")
    if normalized == 0:
        normalized = 0.0
    if minimum is not None and normalized < minimum:
        _fail(f"{label} must be >= {minimum}")
    if maximum is not None and normalized > maximum:
        _fail(f"{label} must be <= {maximum}")
    return normalized


def _optional_number_list(value: object, *, label: str) -> list[float] | None:
    if value is None:
        return None
    values = _sequence(value, label=label)
    if not values:
        _fail(f"{label} must not be empty when present")
    normalized: list[float] = []
    for index, nested in enumerate(values):
        number = _optional_number(nested, label=f"{label}[{index}]")
        if number is None:
            _fail(f"{label}[{index}] must not be null")
        normalized.append(number)
    return normalized


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return value


def _timestamp(value: object, *, label: str) -> tuple[str, datetime]:
    if type(value) is not str or _UTC_TIMESTAMP.fullmatch(value) is None:
        _fail(f"{label} must be UTC seconds in YYYY-MM-DDTHH:MM:SSZ form")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise PrelockCandidateLineageError(f"{label} is invalid") from exc
    return value, parsed


def _enum(value: object, allowed: set | frozenset, *, label: str) -> str:
    if type(value) is not str or value not in allowed:
        _fail(f"{label} is outside the closed enum")
    return value


def _identifier_list(value: object, *, label: str, nonempty: bool = True) -> list[str]:
    values = [
        _identifier(item, label=f"{label} item")
        for item in _sequence(value, label=label)
    ]
    if nonempty and not values:
        _fail(f"{label} must not be empty")
    if len(set(values)) != len(values):
        _fail(f"{label} contains a duplicate")
    return sorted(values)


def _source_identity(value: object, *, label: str) -> dict[str, object]:
    item = _exact_fields(
        value,
        frozenset({"role", "uri", "generation", "sha256", "bytes"}),
        label=label,
    )
    generation = _text(item["generation"], label=f"{label} generation", maximum=32)
    if not generation.isdigit() or int(generation) < 1:
        _fail(f"{label} generation must be one positive provider generation")
    return {
        "role": _identifier(item["role"], label=f"{label} role"),
        "uri": _text(item["uri"], label=f"{label} URI", maximum=2048),
        "generation": generation,
        "sha256": _sha(item["sha256"], label=f"{label} SHA-256"),
        "bytes": _integer(item["bytes"], label=f"{label} bytes", minimum=1),
    }


def _normalize_run_header(value: object) -> dict[str, object]:
    item = _exact_fields(value, _RUN_HEADER_FIELDS, label="run header")
    lock_text, lock = _timestamp(item["slate_lock_at_utc"], label="slate lock")
    frozen_text, frozen = _timestamp(item["frozen_at_utc"], label="freeze time")
    if frozen >= lock:
        _fail("lineage sidecar was not frozen before slate lock")
    selectors = _identifier_list(item["selector_ids"], label="selector IDs")
    paid = item["paid_strategy_id"]
    if paid is not None:
        paid = _identifier(paid, label="paid strategy ID")
        if paid not in selectors:
            _fail("paid strategy is not one of the run selectors")
    sources = [
        _source_identity(source, label=f"input source[{index}]")
        for index, source in enumerate(
            _sequence(item["input_source_identities"], label="input sources")
        )
    ]
    if not sources:
        _fail("run header requires at least one exact input source")
    sources.sort(key=lambda source: str(source["role"]))
    if len({source["role"] for source in sources}) != len(sources):
        _fail("input source roles repeat")
    week = _integer(item["week"], label="week", minimum=1)
    if week > 18:
        _fail("week must be <= 18")
    return {
        "run_id": _identifier(item["run_id"], label="run ID"),
        "run_type": _identifier(item["run_type"], label="run type"),
        "season": _integer(item["season"], label="season", minimum=2000),
        "week": week,
        "slate_id": _identifier(item["slate_id"], label="slate ID"),
        "draft_group_id": _integer(
            item["draft_group_id"], label="draft group ID", minimum=1
        ),
        "contest_id": _optional_text(
            item["contest_id"], label="contest ID", maximum=200
        ),
        "slate_lock_at_utc": lock_text,
        "frozen_at_utc": frozen_text,
        "entry_budget": _integer(item["entry_budget"], label="entry budget", minimum=1),
        "policy_id": _identifier(item["policy_id"], label="policy ID"),
        "selector_ids": selectors,
        "effective_candidate_stage_id": _identifier(
            item["effective_candidate_stage_id"],
            label="effective candidate stage ID",
        ),
        "paid_strategy_id": paid,
        "code_sha256": _sha(item["code_sha256"], label="code SHA-256"),
        "input_source_identities": sources,
    }


def _normalize_roster(value: object) -> dict[str, object]:
    item = _exact_fields(value, _ROSTER_FIELDS, label="roster identity")
    pairs = []
    for index, raw_pair in enumerate(
        _sequence(item["player_id_bridge"], label="player ID bridge")
    ):
        pair = _exact_fields(
            raw_pair,
            frozenset({"internal_player_id", "draftable_player_id"}),
            label=f"player ID bridge[{index}]",
        )
        pairs.append(
            {
                "internal_player_id": _text(
                    pair["internal_player_id"],
                    label=f"player ID bridge[{index}] internal ID",
                    maximum=200,
                ),
                "draftable_player_id": _text(
                    pair["draftable_player_id"],
                    label=f"player ID bridge[{index}] draftable ID",
                    maximum=200,
                ),
            }
        )
    pairs.sort(key=lambda pair: str(pair["internal_player_id"]))
    internal_ids = [str(pair["internal_player_id"]) for pair in pairs]
    draftable_ids = sorted(str(pair["draftable_player_id"]) for pair in pairs)
    if len(pairs) != 9 or len(set(internal_ids)) != 9 or len(set(draftable_ids)) != 9:
        _fail("roster identity requires nine one-to-one player ID pairs")
    slate_id = _identifier(item["slate_id"], label="roster slate ID")
    internal_namespace = _identifier(
        item["internal_player_id_namespace"], label="internal player namespace"
    )
    draftable_namespace = _identifier(
        item["draftable_player_id_namespace"], label="draftable player namespace"
    )
    identity_payload = {
        "schema_version": ROSTER_IDENTITY_SCHEMA,
        "slate_id": slate_id,
        "internal_player_id_namespace": internal_namespace,
        "internal_player_ids": internal_ids,
    }
    return {
        "roster_id": f"roster-v1-{canonical_sha256(identity_payload)}",
        "slate_id": slate_id,
        "hash_algorithm": HASH_ALGORITHM,
        "canonicalization": ROSTER_CANONICALIZATION,
        "internal_player_id_namespace": internal_namespace,
        "draftable_player_id_namespace": draftable_namespace,
        "player_id_bridge": pairs,
        "internal_player_ids": internal_ids,
        "draftable_player_ids": draftable_ids,
        "internal_roster_sha256": canonical_sha256(internal_ids),
        "draftable_roster_sha256": canonical_sha256(draftable_ids),
        "salary_catalog_sha256": _sha(
            item["salary_catalog_sha256"], label="salary catalog SHA-256"
        ),
        "legacy_lineup_ids": _identifier_list(
            item["legacy_lineup_ids"],
            label="legacy lineup IDs",
            nonempty=False,
        ),
    }


def _normalize_proposal(value: object) -> dict[str, object]:
    item = _exact_fields(value, _PROPOSAL_FIELDS, label="proposal request")
    return {
        "request_id": _identifier(item["request_id"], label="request ID"),
        "request_ordinal": _integer(item["request_ordinal"], label="request ordinal"),
        "source_label": _identifier(item["source_label"], label="source label"),
        "family": _identifier(item["family"], label="generator family"),
        "requested_ordinal": _integer(
            item["requested_ordinal"], label="family request ordinal"
        ),
        "world_id": _optional_integer(item["world_id"], label="world ID"),
        "generator_config_sha256": _sha(
            item["generator_config_sha256"], label="generator config SHA-256"
        ),
        "terminal_status": _enum(
            item["terminal_status"], REQUEST_STATUSES, label="request status"
        ),
    }


def _normalize_solve(value: object) -> dict[str, object]:
    item = _exact_fields(value, _SOLVE_FIELDS, label="solve attempt")
    status = _enum(item["status"], SOLVE_STATUSES, label="solve status")
    roster_id = item["roster_id"]
    if status == "PRODUCED":
        roster_id = _identifier(roster_id, label="produced roster ID")
    elif roster_id is not None:
        _fail("failed or infeasible solve attempt must not carry a roster")
    return {
        "attempt_id": _identifier(item["attempt_id"], label="attempt ID"),
        "attempt_ordinal": _integer(item["attempt_ordinal"], label="attempt ordinal"),
        "request_id": _identifier(item["request_id"], label="attempt request ID"),
        "retry_ordinal": _integer(item["retry_ordinal"], label="retry ordinal"),
        "status": status,
        "roster_id": roster_id,
    }


def _normalize_occurrence(value: object) -> dict[str, object]:
    item = _exact_fields(value, _OCCURRENCE_FIELDS, label="generated occurrence")
    return {
        "occurrence_id": _identifier(item["occurrence_id"], label="occurrence ID"),
        "occurrence_ordinal": _integer(
            item["occurrence_ordinal"], label="occurrence ordinal"
        ),
        "attempt_id": _identifier(item["attempt_id"], label="occurrence attempt ID"),
        "request_id": _identifier(item["request_id"], label="occurrence request ID"),
        "roster_id": _identifier(item["roster_id"], label="occurrence roster ID"),
    }


def _normalize_dedupe(value: object) -> dict[str, object]:
    item = _exact_fields(value, _DEDUPE_FIELDS, label="dedupe decision")
    disposition = _enum(
        item["disposition"], DEDUPE_DISPOSITIONS, label="dedupe disposition"
    )
    duplicate = item["duplicate_of_occurrence_id"]
    if disposition == "FIRST_SEEN":
        if duplicate is not None:
            _fail("first-seen dedupe decision carries a duplicate pointer")
    else:
        duplicate = _identifier(duplicate, label="duplicate occurrence pointer")
    return {
        "decision_id": _identifier(item["decision_id"], label="dedupe decision ID"),
        "occurrence_id": _identifier(
            item["occurrence_id"], label="dedupe occurrence ID"
        ),
        "roster_id": _identifier(item["roster_id"], label="dedupe roster ID"),
        "disposition": disposition,
        "duplicate_of_occurrence_id": duplicate,
    }


def _normalize_admission(value: object) -> dict[str, object]:
    item = _exact_fields(value, _ADMISSION_FIELDS, label="admission decision")
    reason = _enum(item["reason"], set(ADMISSION_REASONS), label="admission reason")
    disposition = _enum(
        item["disposition"],
        {"RETAINED", "REJECTED"},
        label="admission disposition",
    )
    if ADMISSION_REASONS[reason] != disposition:
        _fail("admission reason and disposition disagree")
    occurrences = _identifier_list(
        item["source_occurrence_ids"],
        label="admission source occurrences",
        nonempty=False,
    )
    inputs = _identifier_list(
        item["input_candidate_instance_ids"],
        label="admission input candidates",
        nonempty=False,
    )
    if bool(occurrences) == bool(inputs):
        _fail("admission must name exactly one occurrence or candidate input mode")
    return {
        "decision_id": _identifier(item["decision_id"], label="admission decision ID"),
        "stage_id": _identifier(item["stage_id"], label="admission stage ID"),
        "stage_ordinal": _integer(item["stage_ordinal"], label="stage ordinal"),
        "candidate_instance_id": _identifier(
            item["candidate_instance_id"], label="candidate instance ID"
        ),
        "candidate_ordinal": _integer(
            item["candidate_ordinal"], label="candidate ordinal"
        ),
        "roster_id": _identifier(item["roster_id"], label="admission roster ID"),
        "source_occurrence_ids": occurrences,
        "input_candidate_instance_ids": inputs,
        "admission_preset_id": _identifier(
            item["admission_preset_id"], label="admission preset ID"
        ),
        "disposition": disposition,
        "reason": reason,
    }


def _normalize_strategy(value: object) -> dict[str, object]:
    item = _exact_fields(value, _STRATEGY_FIELDS, label="strategy decision")
    eligibility_reason = _enum(
        item["eligibility_reason"], ELIGIBILITY_REASONS, label="eligibility reason"
    )
    eligibility = _enum(item["eligibility"], {"ELIGIBLE"}, label="eligibility")
    decision_reason = _enum(
        item["decision_reason"],
        set(STRATEGY_DECISION_REASONS),
        label="strategy decision reason",
    )
    decision = _enum(
        item["decision"],
        {"SELECTED", "NOT_SELECTED"},
        label="strategy decision",
    )
    if STRATEGY_DECISION_REASONS[decision_reason] != decision:
        _fail("strategy reason and decision disagree")
    phase = _enum(item["selection_phase"], SELECTION_PHASES, label="selection phase")
    rank = _optional_integer(item["selector_rank"], label="selector rank")
    fresh = _integer(item["fresh_world_count"], label="fresh-world count")
    clear = _integer(item["individual_clear_count"], label="individual clear count")
    p_line = _optional_number(item["p_line"], label="p-line", minimum=0.0, maximum=1.0)
    if p_line is None:
        _fail("p-line must not be null")
    mean_total = _optional_number(item["mean_simulated_total"], label="mean total")
    if mean_total is None:
        _fail("mean simulated total must not be null")
    tiebreak = _optional_number_list(item["tiebreak_values"], label="tiebreak values")
    if tiebreak != [p_line, mean_total]:
        _fail("binary-tail tiebreak must equal [p_line, mean_simulated_total]")
    expected_phase = {
        "SELECTED_COVERAGE_PHASE": "COVERAGE",
        "SELECTED_SATURATION_FILL": "SATURATION_FILL",
        "NOT_SELECTED_BOOK_FULL": "TERMINAL",
        "NOT_SELECTED_FILL_ORDER": "TERMINAL",
    }[decision_reason]
    if phase != expected_phase:
        _fail("strategy decision reason and selection phase disagree")
    if (decision == "SELECTED") != (rank is not None):
        _fail("selected status and selector rank disagree")
    return {
        "decision_id": _identifier(item["decision_id"], label="strategy decision ID"),
        "strategy_id": _identifier(item["strategy_id"], label="strategy ID"),
        "candidate_instance_id": _identifier(
            item["candidate_instance_id"], label="strategy candidate instance ID"
        ),
        "roster_id": _identifier(item["roster_id"], label="strategy roster ID"),
        "candidate_ordinal": _integer(
            item["candidate_ordinal"], label="strategy candidate ordinal"
        ),
        "eligibility": eligibility,
        "eligibility_reason": eligibility_reason,
        "decision": decision,
        "decision_reason": decision_reason,
        "selector_rank": rank,
        "selection_phase": phase,
        "fresh_world_count": fresh,
        "individual_clear_count": clear,
        "p_line": p_line,
        "mean_simulated_total": mean_total,
        "tiebreak_values": tiebreak,
    }


def _normalize_book(value: object) -> dict[str, object]:
    item = _exact_fields(value, _BOOK_FIELDS, label="book transition")
    reason = _enum(item["reason"], set(BOOK_TRANSITION_REASONS), label="book reason")
    disposition = _enum(
        item["disposition"],
        {"RETAINED", "REMOVED", "ADDED"},
        label="book disposition",
    )
    if BOOK_TRANSITION_REASONS[reason] != disposition:
        _fail("book reason and disposition disagree")
    selector_rank = _optional_integer(item["selector_rank"], label="book selector rank")
    postselector_rank = _optional_integer(
        item["postselector_rank"], label="postselector rank"
    )
    export_rank = _optional_integer(item["export_rank"], label="export rank")
    if disposition == "RETAINED" and (
        selector_rank is None or postselector_rank is None or export_rank is None
    ):
        _fail("retained book row lacks one of its ranks")
    if disposition == "REMOVED" and (
        selector_rank is None
        or postselector_rank is not None
        or export_rank is not None
    ):
        _fail("removed book row has invalid rank transitions")
    if disposition == "ADDED" and (
        selector_rank is not None or postselector_rank is None or export_rank is None
    ):
        _fail("added book row has invalid rank transitions")
    return {
        "transition_id": _identifier(item["transition_id"], label="transition ID"),
        "strategy_id": _identifier(item["strategy_id"], label="book strategy ID"),
        "candidate_instance_id": _identifier(
            item["candidate_instance_id"], label="book candidate instance ID"
        ),
        "roster_id": _identifier(item["roster_id"], label="book roster ID"),
        "selector_rank": selector_rank,
        "postselector_rank": postselector_rank,
        "export_rank": export_rank,
        "disposition": disposition,
        "reason": reason,
    }


def _normalize_prepared(value: object) -> dict[str, object]:
    item = _exact_fields(value, _PREPARED_FIELDS, label="prepared entry")
    return {
        "prepared_entry_id": _identifier(
            item["prepared_entry_id"], label="prepared-entry record ID"
        ),
        "strategy_id": _identifier(item["strategy_id"], label="prepared strategy ID"),
        "candidate_instance_id": _identifier(
            item["candidate_instance_id"], label="prepared candidate instance ID"
        ),
        "roster_id": _identifier(item["roster_id"], label="prepared roster ID"),
        "contest_id": _text(
            item["contest_id"], label="prepared contest ID", maximum=200
        ),
        "entry_id": _text(item["entry_id"], label="DraftKings Entry ID", maximum=200),
        "entry_row_ordinal": _integer(
            item["entry_row_ordinal"], label="entry row ordinal"
        ),
        "export_rank": _integer(item["export_rank"], label="prepared export rank"),
        "filled_csv_sha256": _sha(
            item["filled_csv_sha256"], label="filled CSV SHA-256"
        ),
        "paid_export_receipt_sha256": _sha(
            item["paid_export_receipt_sha256"],
            label="paid export receipt SHA-256",
        ),
        "status": _enum(
            item["status"], PREPARED_ENTRY_STATUSES, label="prepared status"
        ),
    }


def _make_record(
    value: object,
    *,
    schema: str,
    normalizer,
) -> dict[str, object]:
    body = normalizer(value)
    record = {"schema_version": schema, **body}
    record["record_sha256"] = canonical_sha256(record)
    return record


def _reopen_record(
    value: object,
    *,
    schema: str,
    body_fields: frozenset[str],
    normalizer,
    label: str,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    expected_fields = body_fields | {"schema_version", "record_sha256"}
    if set(item) != expected_fields or item.get("schema_version") != schema:
        _fail(f"{label} envelope differs")
    retained_hash = _sha(item["record_sha256"], label=f"{label} record SHA-256")
    raw = {key: item[key] for key in body_fields}
    expected = _make_record(raw, schema=schema, normalizer=normalizer)
    if retained_hash != expected["record_sha256"] or item != expected:
        _fail(f"{label} is not canonical or its self-hash differs")
    return expected


def _build_roster_record(value: object) -> dict[str, object]:
    body = _normalize_roster(value)
    record = {"schema_version": ROSTER_IDENTITY_SCHEMA, **body}
    record["record_sha256"] = canonical_sha256(record)
    return record


def _reopen_roster(value: object) -> dict[str, object]:
    item = _mapping(value, label="roster identity record")
    derived_fields = frozenset(
        {
            "roster_id",
            "hash_algorithm",
            "canonicalization",
            "internal_player_ids",
            "draftable_player_ids",
            "internal_roster_sha256",
            "draftable_roster_sha256",
        }
    )
    expected_fields = (
        _ROSTER_FIELDS
        | derived_fields
        | {
            "schema_version",
            "record_sha256",
        }
    )
    if (
        set(item) != expected_fields
        or item.get("schema_version") != ROSTER_IDENTITY_SCHEMA
    ):
        _fail("roster identity record envelope differs")
    raw = {key: item[key] for key in _ROSTER_FIELDS}
    expected = _build_roster_record(raw)
    if item != expected:
        _fail("roster identity is not canonical or its self-hash differs")
    return expected


def _records(
    values: Sequence[Mapping[str, object]], *, schema: str, normalizer
) -> list[dict[str, object]]:
    return [
        _make_record(value, schema=schema, normalizer=normalizer) for value in values
    ]


def _unique(values: Sequence[Mapping[str, object]], field: str, *, label: str) -> None:
    items = [str(value[field]) for value in values]
    if len(set(items)) != len(items):
        _fail(f"{label} {field} values repeat")


def _contiguous(values: Sequence[int], *, label: str) -> None:
    if sorted(values) != list(range(len(values))):
        _fail(f"{label} ordinals are not exact zero-based contiguous values")


def _validate_reconciliation(sidecar: Mapping[str, object]) -> dict[str, int]:
    header = sidecar["run_header"]
    rosters = sidecar["roster_identities"]
    proposals = sidecar["proposal_requests"]
    attempts = sidecar["solve_attempts"]
    occurrences = sidecar["generated_occurrences"]
    dedupe = sidecar["dedupe_decisions"]
    admissions = sidecar["admission_decisions"]
    strategies = sidecar["strategy_decisions"]
    books = sidecar["book_transitions"]
    prepared = sidecar["prepared_entries"]

    _unique(rosters, "roster_id", label="roster")
    roster_by_id = {str(row["roster_id"]): row for row in rosters}
    if any(row["slate_id"] != header["slate_id"] for row in rosters):
        _fail("roster identity slate differs from the run header")
    _unique(proposals, "request_id", label="proposal")
    _contiguous(
        [int(row["request_ordinal"]) for row in proposals], label="proposal request"
    )
    if len(
        {
            (row["source_label"], row["family"], row["requested_ordinal"])
            for row in proposals
        }
    ) != len(proposals):
        _fail("proposal source/family/request ordinals repeat")
    request_by_id = {str(row["request_id"]): row for row in proposals}

    _unique(attempts, "attempt_id", label="solve attempt")
    _contiguous(
        [int(row["attempt_ordinal"]) for row in attempts], label="solve attempt"
    )
    attempts_by_request: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for attempt in attempts:
        request_id = str(attempt["request_id"])
        if request_id not in request_by_id:
            _fail("solve attempt references an unknown proposal request")
        if (
            attempt["roster_id"] is not None
            and attempt["roster_id"] not in roster_by_id
        ):
            _fail("produced solve attempt references an unknown roster")
        attempts_by_request[request_id].append(attempt)
    for request_id, request in request_by_id.items():
        rows = sorted(
            attempts_by_request.get(request_id, []),
            key=lambda row: int(row["retry_ordinal"]),
        )
        status = str(request["terminal_status"])
        if status == "EXHAUSTED_NOT_ATTEMPTED":
            if rows:
                _fail("exhausted-not-attempted request has solve attempts")
            continue
        if not rows:
            _fail("attempted request lacks a solve-attempt record")
        _contiguous([int(row["retry_ordinal"]) for row in rows], label=request_id)
        if rows[-1]["status"] != status:
            _fail("proposal terminal status differs from its last solve attempt")
        produced = [row for row in rows if row["status"] == "PRODUCED"]
        if (status == "PRODUCED") != (len(produced) == 1):
            _fail("proposal produced status differs from its attempt yield")
        if produced and produced[0] is not rows[-1]:
            _fail("proposal contains a solve attempt after producing a roster")

    _unique(occurrences, "occurrence_id", label="generated occurrence")
    _contiguous(
        [int(row["occurrence_ordinal"]) for row in occurrences],
        label="generated occurrence",
    )
    attempt_by_id = {str(row["attempt_id"]): row for row in attempts}
    produced_attempt_ids = {
        str(row["attempt_id"]) for row in attempts if row["status"] == "PRODUCED"
    }
    occurrence_attempt_ids = [str(row["attempt_id"]) for row in occurrences]
    if (
        len(occurrence_attempt_ids) != len(set(occurrence_attempt_ids))
        or set(occurrence_attempt_ids) != produced_attempt_ids
    ):
        _fail("produced attempts and generated occurrences are not one-to-one")
    occurrence_by_id = {str(row["occurrence_id"]): row for row in occurrences}
    for occurrence in occurrences:
        attempt = attempt_by_id.get(str(occurrence["attempt_id"]))
        if (
            attempt is None
            or attempt["status"] != "PRODUCED"
            or occurrence["request_id"] != attempt["request_id"]
            or occurrence["roster_id"] != attempt["roster_id"]
            or occurrence["roster_id"] not in roster_by_id
        ):
            _fail("generated occurrence differs from its produced attempt")
    if set(roster_by_id) != {str(row["roster_id"]) for row in occurrences}:
        _fail("roster bridge and generated-occurrence roster population differ")

    _unique(dedupe, "decision_id", label="dedupe decision")
    dedupe_occurrence_ids = [str(row["occurrence_id"]) for row in dedupe]
    if len(dedupe_occurrence_ids) != len(set(dedupe_occurrence_ids)) or set(
        dedupe_occurrence_ids
    ) != set(occurrence_by_id):
        _fail("generated occurrences and dedupe decisions are not one-to-one")
    first_occurrence_by_roster: dict[str, Mapping[str, object]] = {}
    dedupe_by_occurrence = {str(row["occurrence_id"]): row for row in dedupe}
    for occurrence in sorted(
        occurrences, key=lambda row: int(row["occurrence_ordinal"])
    ):
        decision = dedupe_by_occurrence[str(occurrence["occurrence_id"])]
        roster_id = str(occurrence["roster_id"])
        if decision["roster_id"] != roster_id:
            _fail("dedupe decision roster differs from its occurrence")
        prior = first_occurrence_by_roster.get(roster_id)
        if prior is None:
            if (
                decision["disposition"] != "FIRST_SEEN"
                or decision["duplicate_of_occurrence_id"] is not None
            ):
                _fail("first generated roster occurrence is not FIRST_SEEN")
            first_occurrence_by_roster[roster_id] = occurrence
            continue
        prior_request = request_by_id[str(prior["request_id"])]
        request = request_by_id[str(occurrence["request_id"])]
        expected = (
            "DUPLICATE_CROSS_SEED"
            if request["source_label"] != prior_request["source_label"]
            else "DUPLICATE_CROSS_FAMILY"
            if request["family"] != prior_request["family"]
            else "DUPLICATE_SAME_FAMILY"
        )
        if (
            decision["disposition"] != expected
            or decision["duplicate_of_occurrence_id"] != prior["occurrence_id"]
        ):
            _fail("duplicate decision does not point to the first matching occurrence")

    _unique(admissions, "decision_id", label="admission decision")
    _unique(admissions, "candidate_instance_id", label="candidate instance")
    candidate_by_id = {str(row["candidate_instance_id"]): row for row in admissions}
    stages: dict[int, str] = {}
    stage_rows: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in admissions:
        ordinal = int(row["stage_ordinal"])
        prior_stage = stages.setdefault(ordinal, str(row["stage_id"]))
        if prior_stage != row["stage_id"]:
            _fail("one admission stage ordinal names multiple stages")
        if row["roster_id"] not in roster_by_id:
            _fail("admission decision references an unknown roster")
        stage_rows[str(row["stage_id"])].append(row)
    _contiguous(list(stages), label="admission stage")
    if header["effective_candidate_stage_id"] not in stage_rows:
        _fail("effective candidate stage is absent")
    for stage_id, rows in stage_rows.items():
        _contiguous([int(row["candidate_ordinal"]) for row in rows], label=stage_id)
        if len({row["roster_id"] for row in rows}) != len(rows):
            _fail(f"{stage_id} contains more than one candidate for one roster")
    for row in admissions:
        occurrence_inputs = list(row["source_occurrence_ids"])
        candidate_inputs = list(row["input_candidate_instance_ids"])
        for occurrence_id in occurrence_inputs:
            occurrence = occurrence_by_id.get(str(occurrence_id))
            if occurrence is None or occurrence["roster_id"] != row["roster_id"]:
                _fail("admission occurrence input is unknown or has another roster")
        for candidate_id in candidate_inputs:
            source = candidate_by_id.get(str(candidate_id))
            if (
                source is None
                or source["roster_id"] != row["roster_id"]
                or source["disposition"] != "RETAINED"
                or int(source["stage_ordinal"]) >= int(row["stage_ordinal"])
            ):
                _fail("admission candidate input is not an earlier retained instance")

    ordered_stage_ids = [stages[ordinal] for ordinal in range(len(stages))]
    initial_rows = stage_rows[ordered_stage_ids[0]]
    initial_occurrence_ids = [
        str(occurrence_id)
        for row in initial_rows
        for occurrence_id in row["source_occurrence_ids"]
    ]
    if any(row["input_candidate_instance_ids"] for row in initial_rows):
        _fail("initial admission stage must consume generated occurrences")
    if len(initial_occurrence_ids) != len(set(initial_occurrence_ids)) or set(
        initial_occurrence_ids
    ) != set(occurrence_by_id):
        _fail("every generated occurrence must feed exactly one initial candidate")
    for stage_ordinal in range(1, len(ordered_stage_ids)):
        prior_rows = stage_rows[ordered_stage_ids[stage_ordinal - 1]]
        current_rows = stage_rows[ordered_stage_ids[stage_ordinal]]
        expected_inputs = {
            str(row["candidate_instance_id"])
            for row in prior_rows
            if row["disposition"] == "RETAINED"
        }
        observed_inputs = [
            str(candidate_id)
            for row in current_rows
            for candidate_id in row["input_candidate_instance_ids"]
        ]
        if any(
            row["source_occurrence_ids"]
            or len(row["input_candidate_instance_ids"]) != 1
            for row in current_rows
        ):
            _fail("later admission stage must consume one prior candidate per row")
        if (
            len(observed_inputs) != len(set(observed_inputs))
            or set(observed_inputs) != expected_inputs
        ):
            _fail("retained candidates must flow exactly once to the next stage")
        if any(
            int(candidate_by_id[candidate_id]["stage_ordinal"]) != stage_ordinal - 1
            for candidate_id in observed_inputs
        ):
            _fail("admission stage bypasses its immediate predecessor")

    effective_rows = [
        row
        for row in stage_rows[str(header["effective_candidate_stage_id"])]
        if row["disposition"] == "RETAINED"
    ]
    if not effective_rows:
        _fail("effective candidate population is empty")
    if len({row["roster_id"] for row in effective_rows}) != len(effective_rows):
        _fail("effective candidate population repeats an exact roster")
    effective_by_id = {str(row["candidate_instance_id"]): row for row in effective_rows}

    _unique(strategies, "decision_id", label="strategy decision")
    strategy_candidate_keys = [
        (str(row["strategy_id"]), str(row["candidate_instance_id"]))
        for row in strategies
    ]
    if len(strategy_candidate_keys) != len(set(strategy_candidate_keys)):
        _fail("strategy has more than one decision for one candidate")
    expected_strategy_ids = set(header["selector_ids"])
    decisions_by_strategy: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in strategies:
        if row["strategy_id"] not in expected_strategy_ids:
            _fail("strategy decision names an undeclared selector")
        candidate = effective_by_id.get(str(row["candidate_instance_id"]))
        if candidate is None or candidate["roster_id"] != row["roster_id"]:
            _fail("strategy decision is outside the effective candidate population")
        if candidate["candidate_ordinal"] != row["candidate_ordinal"]:
            _fail("strategy candidate ordinal differs from the effective stage")
        decisions_by_strategy[str(row["strategy_id"])].append(row)
    if set(decisions_by_strategy) != expected_strategy_ids:
        _fail("one or more declared selectors lack strategy decisions")
    effective_ids = set(effective_by_id)
    selected_by_strategy: dict[str, dict[str, Mapping[str, object]]] = {}
    for strategy_id, rows in decisions_by_strategy.items():
        if (
            len(rows) != len(effective_ids)
            or {str(row["candidate_instance_id"]) for row in rows} != effective_ids
        ):
            _fail("selector does not decide on every effective candidate exactly once")
        _contiguous([int(row["candidate_ordinal"]) for row in rows], label=strategy_id)
        selected = [row for row in rows if row["decision"] == "SELECTED"]
        if len(selected) != int(header["entry_budget"]):
            _fail("selector does not produce exact K")
        _contiguous(
            [int(row["selector_rank"]) for row in selected],
            label=f"{strategy_id} selector",
        )
        selected_by_strategy[strategy_id] = {
            str(row["candidate_instance_id"]): row for row in selected
        }

    _unique(books, "transition_id", label="book transition")
    book_candidate_keys = [
        (str(row["strategy_id"]), str(row["candidate_instance_id"])) for row in books
    ]
    if len(book_candidate_keys) != len(set(book_candidate_keys)):
        _fail("strategy has more than one book transition for one candidate")
    books_by_strategy: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    decision_lookup = {
        (str(row["strategy_id"]), str(row["candidate_instance_id"])): row
        for row in strategies
    }
    for row in books:
        strategy_id = str(row["strategy_id"])
        candidate_id = str(row["candidate_instance_id"])
        decision = decision_lookup.get((strategy_id, candidate_id))
        if decision is None or decision["roster_id"] != row["roster_id"]:
            _fail("book transition lacks a matching strategy decision")
        if row["selector_rank"] != decision["selector_rank"]:
            _fail("book transition selector rank differs")
        if row["disposition"] in {"RETAINED", "REMOVED"}:
            if decision["decision"] != "SELECTED":
                _fail("retained or removed book row was not raw-selected")
        elif decision["decision"] != "NOT_SELECTED":
            _fail("added book row was already selected")
        books_by_strategy[strategy_id].append(row)
    if set(books_by_strategy) != expected_strategy_ids:
        _fail("one or more declared selectors lack book transitions")
    for strategy_id, rows in books_by_strategy.items():
        raw_ids = {
            str(row["candidate_instance_id"])
            for row in rows
            if row["selector_rank"] is not None
        }
        if raw_ids != set(selected_by_strategy[strategy_id]):
            _fail("book transitions do not cover the exact raw-selected book")
        post = [row for row in rows if row["postselector_rank"] is not None]
        exported = [row for row in rows if row["export_rank"] is not None]
        if len(post) != int(header["entry_budget"]) or len(exported) != len(post):
            _fail("postselector/export book is not exact K")
        if {row["candidate_instance_id"] for row in post} != {
            row["candidate_instance_id"] for row in exported
        }:
            _fail("export order changed final book membership")
        if len({row["candidate_instance_id"] for row in exported}) != len(
            exported
        ) or len({row["roster_id"] for row in exported}) != len(exported):
            _fail("final book repeats a candidate or exact roster")
        _contiguous(
            [int(row["postselector_rank"]) for row in post],
            label=f"{strategy_id} postselector",
        )
        _contiguous(
            [int(row["export_rank"]) for row in exported],
            label=f"{strategy_id} export",
        )

    _unique(prepared, "prepared_entry_id", label="prepared entry")
    if len({row["candidate_instance_id"] for row in prepared}) != len(prepared):
        _fail("prepared entry population repeats a candidate")
    if len({row["roster_id"] for row in prepared}) != len(prepared):
        _fail("prepared entry population repeats an exact roster")
    paid_strategy = header["paid_strategy_id"]
    if paid_strategy is None:
        if prepared:
            _fail("prepared entries exist without a declared paid strategy")
    else:
        if header["contest_id"] is None:
            _fail("paid preparation requires a contest ID")
        if len(prepared) != int(header["entry_budget"]):
            _fail("prepared entry population is not exact K")
        _contiguous(
            [int(row["entry_row_ordinal"]) for row in prepared],
            label="prepared entry row",
        )
        _contiguous(
            [int(row["export_rank"]) for row in prepared],
            label="prepared export",
        )
        if len({row["entry_id"] for row in prepared}) != len(prepared):
            _fail("prepared DraftKings Entry IDs repeat")
        csv_hashes = {row["filled_csv_sha256"] for row in prepared}
        receipt_hashes = {row["paid_export_receipt_sha256"] for row in prepared}
        if len(csv_hashes) != 1 or len(receipt_hashes) != 1:
            _fail("prepared rows do not bind one filled CSV and paid receipt")
        paid_exports = {
            int(row["export_rank"]): row
            for row in books_by_strategy[str(paid_strategy)]
            if row["export_rank"] is not None
        }
        for row in prepared:
            exported = paid_exports.get(int(row["export_rank"]))
            if (
                row["strategy_id"] != paid_strategy
                or row["contest_id"] != header["contest_id"]
                or exported is None
                or row["candidate_instance_id"] != exported["candidate_instance_id"]
                or row["roster_id"] != exported["roster_id"]
            ):
                _fail("prepared entry differs from its exact paid export row")

    return {
        "proposal_request_count": len(proposals),
        "solve_attempt_count": len(attempts),
        "generated_occurrence_count": len(occurrences),
        "unique_generated_roster_count": len(rosters),
        "dedupe_decision_count": len(dedupe),
        "admission_decision_count": len(admissions),
        "effective_candidate_count": len(effective_rows),
        "strategy_decision_count": len(strategies),
        "raw_selected_count": sum(row["decision"] == "SELECTED" for row in strategies),
        "final_book_lineup_count": sum(row["export_rank"] is not None for row in books),
        "prepared_entry_count": len(prepared),
    }


def _sort_records(sidecar: dict[str, object]) -> None:
    sidecar["roster_identities"].sort(key=lambda row: str(row["roster_id"]))
    sidecar["proposal_requests"].sort(key=lambda row: int(row["request_ordinal"]))
    sidecar["solve_attempts"].sort(key=lambda row: int(row["attempt_ordinal"]))
    sidecar["generated_occurrences"].sort(
        key=lambda row: int(row["occurrence_ordinal"])
    )
    occurrence_order = {
        str(row["occurrence_id"]): int(row["occurrence_ordinal"])
        for row in sidecar["generated_occurrences"]
    }
    sidecar["dedupe_decisions"].sort(
        key=lambda row: occurrence_order[str(row["occurrence_id"])]
    )
    sidecar["admission_decisions"].sort(
        key=lambda row: (
            int(row["stage_ordinal"]),
            int(row["candidate_ordinal"]),
            str(row["decision_id"]),
        )
    )
    sidecar["strategy_decisions"].sort(
        key=lambda row: (str(row["strategy_id"]), int(row["candidate_ordinal"]))
    )
    sidecar["book_transitions"].sort(
        key=lambda row: (
            str(row["strategy_id"]),
            row["export_rank"] is None,
            int(row["export_rank"] or 0),
            str(row["candidate_instance_id"]),
        )
    )
    sidecar["prepared_entries"].sort(key=lambda row: int(row["entry_row_ordinal"]))


def build_prelock_candidate_lineage_v1(
    *,
    run_header: Mapping[str, object],
    roster_identities: Sequence[Mapping[str, object]],
    proposal_requests: Sequence[Mapping[str, object]],
    solve_attempts: Sequence[Mapping[str, object]],
    generated_occurrences: Sequence[Mapping[str, object]],
    dedupe_decisions: Sequence[Mapping[str, object]],
    admission_decisions: Sequence[Mapping[str, object]],
    strategy_decisions: Sequence[Mapping[str, object]],
    book_transitions: Sequence[Mapping[str, object]],
    prepared_entries: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Build and validate one canonical, outcome-free pre-lock sidecar."""

    supplied = {
        "run_header": run_header,
        "roster_identities": roster_identities,
        "proposal_requests": proposal_requests,
        "solve_attempts": solve_attempts,
        "generated_occurrences": generated_occurrences,
        "dedupe_decisions": dedupe_decisions,
        "admission_decisions": admission_decisions,
        "strategy_decisions": strategy_decisions,
        "book_transitions": book_transitions,
        "prepared_entries": prepared_entries,
    }
    assert_outcome_free(supplied)
    sidecar: dict[str, object] = {
        "schema_version": SIDECAR_SCHEMA,
        "run_header": _make_record(
            run_header, schema=RUN_HEADER_SCHEMA, normalizer=_normalize_run_header
        ),
        "roster_identities": [_build_roster_record(row) for row in roster_identities],
        "proposal_requests": _records(
            proposal_requests,
            schema=PROPOSAL_REQUEST_SCHEMA,
            normalizer=_normalize_proposal,
        ),
        "solve_attempts": _records(
            solve_attempts, schema=SOLVE_ATTEMPT_SCHEMA, normalizer=_normalize_solve
        ),
        "generated_occurrences": _records(
            generated_occurrences,
            schema=GENERATED_OCCURRENCE_SCHEMA,
            normalizer=_normalize_occurrence,
        ),
        "dedupe_decisions": _records(
            dedupe_decisions,
            schema=DEDUPE_DECISION_SCHEMA,
            normalizer=_normalize_dedupe,
        ),
        "admission_decisions": _records(
            admission_decisions,
            schema=ADMISSION_DECISION_SCHEMA,
            normalizer=_normalize_admission,
        ),
        "strategy_decisions": _records(
            strategy_decisions,
            schema=STRATEGY_DECISION_SCHEMA,
            normalizer=_normalize_strategy,
        ),
        "book_transitions": _records(
            book_transitions,
            schema=BOOK_TRANSITION_SCHEMA,
            normalizer=_normalize_book,
        ),
        "prepared_entries": _records(
            prepared_entries,
            schema=PREPARED_ENTRY_SCHEMA,
            normalizer=_normalize_prepared,
        ),
        "candidate_universe_scope": CANDIDATE_UNIVERSE_SCOPE,
        "authority": {
            "decision_authority": False,
            "graph_decision_authority": False,
            "outcome_authority": False,
            "promotion_authority": False,
            "scoring_authority": False,
        },
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    _sort_records(sidecar)
    sidecar["counts"] = _validate_reconciliation(sidecar)
    sidecar["sidecar_sha256"] = canonical_sha256(sidecar)
    return validate_prelock_candidate_lineage_v1(sidecar)


def validate_prelock_candidate_lineage_v1(value: object) -> dict[str, object]:
    """Exact-reopen and reconcile a pre-lock candidate-lineage sidecar."""

    assert_outcome_free(value)
    item = _mapping(value, label="pre-lock lineage sidecar")
    fields = {
        "schema_version",
        "run_header",
        "roster_identities",
        "proposal_requests",
        "solve_attempts",
        "generated_occurrences",
        "dedupe_decisions",
        "admission_decisions",
        "strategy_decisions",
        "book_transitions",
        "prepared_entries",
        "candidate_universe_scope",
        "counts",
        "authority",
        "uses_realized_outcomes",
        "post_lock_data_read",
        "sidecar_sha256",
    }
    if set(item) != fields or item.get("schema_version") != SIDECAR_SCHEMA:
        _fail("pre-lock lineage sidecar envelope differs")
    retained_hash = _sha(item["sidecar_sha256"], label="sidecar SHA-256")
    unhashed = {key: nested for key, nested in item.items() if key != "sidecar_sha256"}
    if retained_hash != canonical_sha256(unhashed):
        _fail("pre-lock lineage sidecar self-hash differs")
    if (
        item["candidate_universe_scope"] != CANDIDATE_UNIVERSE_SCOPE
        or item["uses_realized_outcomes"] is not False
        or item["post_lock_data_read"] is not False
        or item["authority"]
        != {
            "decision_authority": False,
            "graph_decision_authority": False,
            "outcome_authority": False,
            "promotion_authority": False,
            "scoring_authority": False,
        }
    ):
        _fail("pre-lock lineage scope or authority differs")

    reopened: dict[str, object] = {
        **item,
        "run_header": _reopen_record(
            item["run_header"],
            schema=RUN_HEADER_SCHEMA,
            body_fields=_RUN_HEADER_FIELDS,
            normalizer=_normalize_run_header,
            label="run header record",
        ),
        "roster_identities": [
            _reopen_roster(row)
            for row in _sequence(item["roster_identities"], label="roster records")
        ],
        "proposal_requests": [
            _reopen_record(
                row,
                schema=PROPOSAL_REQUEST_SCHEMA,
                body_fields=_PROPOSAL_FIELDS,
                normalizer=_normalize_proposal,
                label="proposal request record",
            )
            for row in _sequence(item["proposal_requests"], label="proposal records")
        ],
        "solve_attempts": [
            _reopen_record(
                row,
                schema=SOLVE_ATTEMPT_SCHEMA,
                body_fields=_SOLVE_FIELDS,
                normalizer=_normalize_solve,
                label="solve attempt record",
            )
            for row in _sequence(item["solve_attempts"], label="solve records")
        ],
        "generated_occurrences": [
            _reopen_record(
                row,
                schema=GENERATED_OCCURRENCE_SCHEMA,
                body_fields=_OCCURRENCE_FIELDS,
                normalizer=_normalize_occurrence,
                label="generated occurrence record",
            )
            for row in _sequence(
                item["generated_occurrences"], label="occurrence records"
            )
        ],
        "dedupe_decisions": [
            _reopen_record(
                row,
                schema=DEDUPE_DECISION_SCHEMA,
                body_fields=_DEDUPE_FIELDS,
                normalizer=_normalize_dedupe,
                label="dedupe decision record",
            )
            for row in _sequence(item["dedupe_decisions"], label="dedupe records")
        ],
        "admission_decisions": [
            _reopen_record(
                row,
                schema=ADMISSION_DECISION_SCHEMA,
                body_fields=_ADMISSION_FIELDS,
                normalizer=_normalize_admission,
                label="admission decision record",
            )
            for row in _sequence(item["admission_decisions"], label="admission records")
        ],
        "strategy_decisions": [
            _reopen_record(
                row,
                schema=STRATEGY_DECISION_SCHEMA,
                body_fields=_STRATEGY_FIELDS,
                normalizer=_normalize_strategy,
                label="strategy decision record",
            )
            for row in _sequence(item["strategy_decisions"], label="strategy records")
        ],
        "book_transitions": [
            _reopen_record(
                row,
                schema=BOOK_TRANSITION_SCHEMA,
                body_fields=_BOOK_FIELDS,
                normalizer=_normalize_book,
                label="book transition record",
            )
            for row in _sequence(item["book_transitions"], label="book records")
        ],
        "prepared_entries": [
            _reopen_record(
                row,
                schema=PREPARED_ENTRY_SCHEMA,
                body_fields=_PREPARED_FIELDS,
                normalizer=_normalize_prepared,
                label="prepared entry record",
            )
            for row in _sequence(item["prepared_entries"], label="prepared records")
        ],
    }
    canonical_order = deepcopy(reopened)
    _sort_records(canonical_order)
    for field in (
        "roster_identities",
        "proposal_requests",
        "solve_attempts",
        "generated_occurrences",
        "dedupe_decisions",
        "admission_decisions",
        "strategy_decisions",
        "book_transitions",
        "prepared_entries",
    ):
        if canonical_order[field] != reopened[field]:
            _fail(f"{field} are not in canonical order")
    expected_counts = _validate_reconciliation(reopened)
    counts = _mapping(item["counts"], label="lineage counts")
    if counts != expected_counts:
        _fail("lineage counts do not reconcile")
    return reopened


__all__ = [
    "ADMISSION_REASONS",
    "BOOK_TRANSITION_REASONS",
    "CANDIDATE_UNIVERSE_SCOPE",
    "DEDUPE_DISPOSITIONS",
    "ELIGIBILITY_REASONS",
    "REQUEST_STATUSES",
    "SIDECAR_SCHEMA",
    "STRATEGY_DECISION_REASONS",
    "PrelockCandidateLineageError",
    "assert_outcome_free",
    "build_prelock_candidate_lineage_v1",
    "canonical_json_bytes",
    "canonical_sha256",
    "validate_prelock_candidate_lineage_v1",
]
