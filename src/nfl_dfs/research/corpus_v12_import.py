"""Outcome-blind compatibility import for accepted Foundry v12 tasks.

The v12 producer is immutable evidence.  This module does not repair, copy,
or relabel it.  It exact-reads one independently accepted task, delegates the
two supported carrier dialects to :mod:`corpus_parametric_snapshot`, replays
the retained roster/book structure, and reconstructs one canonical cross-arm
lineup surface for successor analysis.

Task acceptance is verified here; membership in a terminal combined panel is
deliberately a later Gate-G0 concern and is never claimed by this receipt.
No realized outcome source is accepted by any public function in this module.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_parametric_snapshot as snapshot
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    VISITS_PER_BLOCK,
    _score_matrix_sha256,
    canonical_sha256,
    canonical_visit_schedule,
    cross_score_full_union,
    first_occurrence_unique,
)
from nfl_dfs.research.corpus_parametric_batch import (
    PARAMETER_SET_ORDER,
)
from nfl_dfs.research.lr8_later_period_source import prepare_later_slate


IMPORT_RECEIPT_SCHEMA: Final = "foundry-v12-task-compatibility-import/v1"
PROVENANCE_SCHEMA: Final = "foundry-v12-candidate-provenance/v1"
MATRIX_BINDING_SCHEMA: Final = "foundry-v12-canonical-score-matrix/v1"
RECONSTRUCTION_SCHEMA: Final = "foundry-v12-task-reconstruction/v1"
LINEUP_ID_SCHEMA: Final = "foundry-slate-lineup-identity/v1"
TASK_ACCEPTANCE_SCHEMA: Final = "corpus-parametric-task-acceptance/v1"
AUTHORITATIVE_ACCEPTANCE_DIALECT: Final = "transport-accepted-terminal-v1"
LOCAL_ACCEPTANCE_DIALECT: Final = "local-independent-gate-compatibility"

_SHA256 = re.compile(r"[0-9a-f]{64}")
_GENERATION = re.compile(r"[1-9][0-9]*")
_RUNTIME_ID = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,126}[a-z0-9])?")

_TASK_ACCEPTANCE_FIELDS: Final = frozenset({
    "schema_version",
    "accepted_at_utc",
    "transport_contract",
    "retrieval_task0_prerequisite_identity",
    "task_index",
    "task_sha256",
    "producer_close",
    "science_terminal",
    "task_result",
    "verifier_worker_completion",
    "independent_verification",
    "independent_verification_sha256",
    "verifier_terminal_execution",
    "terminal_governance_census",
    "evidence_object_count",
    "complete_evidence_receipt",
    "independent_verification_complete",
    "strict_verifier_terminal_success",
    "accepted",
    "partial_result",
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "decision_authority",
    "task_acceptance_sha256",
})
_TERMINAL_EXECUTION_FIELDS: Final = frozenset({
    "execution_id",
    "execution_name",
    "execution_uid",
    "task_index",
    "phase",
    "state",
    "counters",
    "metadata_sha256",
})
_TERMINAL_CENSUS_FIELDS: Final = frozenset({
    "job",
    "phase",
    "task_index",
    "execution_id",
    "execution_uid",
    "execution_names",
    "execution_census_sha256",
    "scheduler_census_sha256",
    "all_regions_complete",
    "exactly_one_new_execution",
    "no_active_executions",
    "job_remains_parked",
})
_TERMINAL_CENSUS_V2_FIELDS: Final = _TERMINAL_CENSUS_FIELDS | frozenset({
    "launch_governance_authorization_sha256",
    "terminal_scheduler_census_sha256",
})
_GOVERNANCE_AUTHORIZATION_FIELDS: Final = frozenset({
    "governance_mode",
    "deployment_attestation_sha256",
    "governance_observed_at_utc",
    "attestation_created_at_utc",
    "attestation_expires_at_utc",
    "scheduler_census_sha256",
})


class CorpusV12ImportError(ValueError):
    """A v12 task cannot be imported without weakening its evidence."""


def _fail(message: str) -> None:
    raise CorpusV12ImportError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _nonempty_string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _utc_timestamp(value: object, *, label: str) -> datetime:
    retained = _nonempty_string(value, label=label)
    try:
        parsed = datetime.strptime(retained, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise CorpusV12ImportError(
            f"{label} must be a UTC second-precision timestamp"
        ) from exc
    if len(retained) != 20:
        _fail(f"{label} must be a UTC second-precision timestamp")
    return parsed


def _transport_canonical_json_bytes(value: object) -> bytes:
    """Match the transport's newline-terminated canonical JSON law."""
    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusV12ImportError(
            "task acceptance is not canonical JSON"
        ) from exc


def _transport_canonical_sha256(value: object) -> str:
    return sha256(_transport_canonical_json_bytes(value)).hexdigest()


def _normalize_identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return snapshot.normalize_object_identity(value, label=label)
    except snapshot.CorpusParametricSnapshotError as exc:
        raise CorpusV12ImportError(str(exc)) from exc


def _exact_read(
    identity: Mapping[str, object],
    read_exact: Callable[[Mapping[str, object]], bytes],
    *,
    label: str,
) -> tuple[dict[str, object], bytes]:
    normalized = _normalize_identity(identity, label=label)
    raw = read_exact(normalized)
    if (
        type(raw) is not bytes
        or len(raw) != normalized["bytes"]
        or sha256(raw).hexdigest() != normalized["sha256"]
    ):
        _fail(f"{label} content identity differs")
    return normalized, raw


def _parse_json(raw: bytes, *, label: str) -> dict[str, object]:
    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        body: dict[str, object] = {}
        for key, value in rows:
            if key in body:
                _fail(f"{label} contains duplicate key {key!r}")
            body[key] = value
        return body

    def reject_constant(value: str) -> object:
        _fail(f"{label} contains non-finite value {value}")

    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusV12ImportError(f"{label} is not valid JSON") from exc
    return dict(_mapping(parsed, label=label))


def _same_identity(left: object, right: object, *, label: str) -> dict[str, object]:
    normalized_left = _normalize_identity(left, label=f"{label} left")
    normalized_right = _normalize_identity(right, label=f"{label} right")
    if normalized_left != normalized_right:
        _fail(f"{label} identities differ")
    return normalized_left


def canonical_lineup_id(
    slate: Mapping[str, object], roster: Sequence[object]
) -> str:
    """Return a stable per-slate ID; source order is never part of a tie."""
    roster_ids = [str(value) for value in roster]
    if (
        len(roster_ids) != rw.ROSTER_SIZE
        or len(set(roster_ids)) != rw.ROSTER_SIZE
        or roster_ids != sorted(roster_ids)
    ):
        _fail("lineup identity requires nine unique canonical player IDs")
    payload = {
        "schema_version": LINEUP_ID_SCHEMA,
        "slate": dict(_mapping(slate, label="lineup slate")),
        "roster_player_ids": roster_ids,
    }
    return f"lineup:{canonical_sha256(payload)}"


def _carrier_result_rows(
    carrier: Mapping[str, object],
) -> tuple[str, list[dict[str, object]]]:
    """Normalize result identities and reconcile a dual-row carrier."""

    def rows_for(field: str) -> list[dict[str, object]]:
        raw_rows = _sequence(carrier.get(field), label=f"carrier {field}")
        if len(raw_rows) != len(PARAMETER_SET_ORDER):
            _fail(f"carrier {field} does not contain exactly seven arms")
        identity_field = (
            "object_identity" if field == "variant_result_objects" else "result_object"
        )
        expected_fields = (
            {"ordinal", "parameter_set_id", "object_identity"}
            if field == "variant_result_objects"
            else {
                "ordinal",
                "parameter_set_id",
                "parameter_set_sha256",
                "effective_policy_receipt",
                "result_object",
            }
        )
        normalized: list[dict[str, object]] = []
        for ordinal, raw_row in enumerate(raw_rows):
            row = _mapping(raw_row, label=f"{field}[{ordinal}]")
            if set(row) != expected_fields:
                _fail(f"carrier {field}[{ordinal}] fields differ")
            if (
                row["ordinal"] != ordinal
                or row["parameter_set_id"] != PARAMETER_SET_ORDER[ordinal]
            ):
                _fail(f"carrier {field}[{ordinal}] ordering differs")
            normalized.append({
                "ordinal": ordinal,
                "parameter_set_id": PARAMETER_SET_ORDER[ordinal],
                "result_object": snapshot.normalize_object_identity(
                    row[identity_field], label=f"{field}[{ordinal}] result"
                ),
            })
        return normalized

    has_objects = "variant_result_objects" in carrier
    has_results = "variant_results" in carrier
    if not has_objects and not has_results:
        _fail("carrier has no supported variant-result rows")
    object_rows = rows_for("variant_result_objects") if has_objects else None
    result_rows = rows_for("variant_results") if has_results else None
    if object_rows is not None and result_rows is not None:
        if object_rows != result_rows:
            _fail("dual carrier result bindings differ")
        return "dual-consistent", object_rows
    if object_rows is not None:
        return "variant-result-objects", object_rows
    assert result_rows is not None
    return "variant-results", result_rows


def _validate_retained_books(
    variants: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    arms: list[dict[str, object]] = []
    for ordinal, body_raw in enumerate(variants):
        body = _mapping(body_raw, label=f"variant[{ordinal}]")
        visit_rosters = _sequence(
            body["visit_rosters"], label=f"variant[{ordinal}] visit rosters"
        )
        replay_unique, replay_first = first_occurrence_unique(visit_rosters)
        retained_unique = tuple(
            tuple(str(player_id) for player_id in _sequence(
                roster, label=f"variant[{ordinal}] unique roster"
            ))
            for roster in _sequence(
                body["unique_rosters"], label=f"variant[{ordinal}] unique rosters"
            )
        )
        retained_first_raw = _sequence(
            body["first_occurrence_visit_indices"],
            label=f"variant[{ordinal}] first occurrence indices",
        )
        if any(type(value) is not int for value in retained_first_raw):
            _fail(f"variant[{ordinal}] first occurrence indices are not exact integers")
        retained_first = tuple(int(value) for value in retained_first_raw)
        if replay_unique != retained_unique or replay_first != retained_first:
            _fail(f"variant[{ordinal}] retained deduplication does not replay")

        selected_raw = _sequence(
            _mapping(body["selector"], label=f"variant[{ordinal}] selector")[
                "selected_indices"
            ],
            label=f"variant[{ordinal}] selected indices",
        )
        if any(type(value) is not int for value in selected_raw):
            _fail(f"variant[{ordinal}] selected indices are not exact integers")
        selected_indices = tuple(int(value) for value in selected_raw)
        if (
            len(set(selected_indices)) != len(selected_indices)
            or any(index < 0 or index >= len(retained_unique) for index in selected_indices)
        ):
            _fail(f"variant[{ordinal}] selected indices are not unique and in range")
        selected_rosters = tuple(
            tuple(str(player_id) for player_id in _sequence(
                roster, label=f"variant[{ordinal}] selected roster"
            ))
            for roster in _sequence(
                body["selected_rosters"], label=f"variant[{ordinal}] selected rosters"
            )
        )
        replay_selected = tuple(retained_unique[index] for index in selected_indices)
        if selected_rosters != replay_selected:
            _fail(f"variant[{ordinal}] retained selected book does not replay")
        profile = _mapping(body["profile"], label=f"variant[{ordinal}] profile")
        arms.append({
            "ordinal": ordinal,
            "parameter_set_id": str(profile["parameter_set_id"]),
            "result_sha256": str(body["result_sha256"]),
            "unique_count": len(retained_unique),
            "selected_count": len(selected_rosters),
            "candidate_score_sha256": str(body["candidate_score_sha256"]),
            "selected_score_sha256": str(body["selected_score_sha256"]),
            "selected_rosters_sha256": canonical_sha256([
                list(roster) for roster in selected_rosters
            ]),
        })
    return arms


def _validate_governance_authorization(value: object) -> dict[str, object]:
    authorization = dict(_mapping(value, label="governance authorization"))
    if frozenset(authorization) != _GOVERNANCE_AUTHORIZATION_FIELDS:
        _fail("governance authorization fields differ")
    observed = _utc_timestamp(
        authorization["governance_observed_at_utc"],
        label="governance observed timestamp",
    )
    _sha(
        authorization["scheduler_census_sha256"],
        label="governance scheduler census SHA",
    )
    mode = authorization["governance_mode"]
    attestation_fields = (
        "deployment_attestation_sha256",
        "attestation_created_at_utc",
        "attestation_expires_at_utc",
    )
    if mode == "live-all-region-census":
        if any(authorization[field] is not None for field in attestation_fields):
            _fail("live-census governance authorization fields differ")
    elif mode == "bounded-deployment-attestation":
        _sha(
            authorization["deployment_attestation_sha256"],
            label="deployment attestation SHA",
        )
        created = _utc_timestamp(
            authorization["attestation_created_at_utc"],
            label="attestation created timestamp",
        )
        expires = _utc_timestamp(
            authorization["attestation_expires_at_utc"],
            label="attestation expiry timestamp",
        )
        if not created <= observed < expires:
            _fail("deployment attestation was not valid at governance observation")
    else:
        _fail("governance authorization mode differs")
    return authorization


def _validate_terminal_execution(
    value: object, *, task_index: int
) -> dict[str, object]:
    terminal = dict(_mapping(value, label="verifier terminal execution"))
    if frozenset(terminal) != _TERMINAL_EXECUTION_FIELDS:
        _fail("verifier terminal execution fields differ")
    execution_id = _nonempty_string(
        terminal["execution_id"], label="verifier execution ID"
    )
    execution_name = _nonempty_string(
        terminal["execution_name"], label="verifier execution name"
    )
    if (
        _RUNTIME_ID.fullmatch(execution_id) is None
        or execution_name.rsplit("/", 1)[-1] != execution_id
        or not _nonempty_string(
            terminal["execution_uid"], label="verifier execution UID"
        )
        or terminal["task_index"] != task_index
        or terminal["phase"] != "verifier"
        or terminal["state"] != "True"
    ):
        _fail("verifier terminal execution binding differs")
    counters = _mapping(terminal["counters"], label="verifier terminal counters")
    if set(counters) != {"succeeded", "failed", "cancelled", "retried"} or counters != {
        "succeeded": 1,
        "failed": 0,
        "cancelled": 0,
        "retried": 0,
    }:
        _fail("verifier terminal execution is not strict success")
    _sha(terminal["metadata_sha256"], label="verifier execution metadata SHA")
    return terminal


def _validate_terminal_census(
    value: object,
    *,
    task_index: int,
    terminal: Mapping[str, object],
) -> None:
    census = dict(_mapping(value, label="terminal governance census"))
    allowed_fields = {
        _TERMINAL_CENSUS_FIELDS,
        _TERMINAL_CENSUS_FIELDS | {"governance_authorization"},
        _TERMINAL_CENSUS_V2_FIELDS,
        _TERMINAL_CENSUS_V2_FIELDS | {"governance_authorization"},
    }
    if frozenset(census) not in allowed_fields:
        _fail("terminal governance census fields differ")
    job = _mapping(census["job"], label="terminal census job")
    if set(job) != {
        "name",
        "uid",
        "generation",
        "observed_generation",
        "spec_sha256",
    }:
        _fail("terminal census job fields differ")
    generation = job["generation"]
    if (
        type(generation) is not str
        or _GENERATION.fullmatch(generation) is None
        or job["observed_generation"] != generation
        or _RUNTIME_ID.fullmatch(
            _nonempty_string(job["name"], label="terminal census job name")
        )
        is None
    ):
        _fail("terminal census job binding differs")
    _nonempty_string(job["uid"], label="terminal census job UID")
    _sha(job["spec_sha256"], label="terminal census job spec SHA")

    raw_names = _sequence(
        census["execution_names"], label="terminal census execution names"
    )
    names = [
        _nonempty_string(value, label="terminal census execution name")
        for value in raw_names
    ]
    if (
        names != sorted(names)
        or len(names) != len(set(names))
        or any(_RUNTIME_ID.fullmatch(name) is None for name in names)
        or terminal["execution_id"] not in names
        or census["phase"] != "verifier"
        or census["task_index"] != task_index
        or census["execution_id"] != terminal["execution_id"]
        or census["execution_uid"] != terminal["execution_uid"]
        or any(census[field] is not True for field in (
            "all_regions_complete",
            "exactly_one_new_execution",
            "no_active_executions",
            "job_remains_parked",
        ))
    ):
        _fail("terminal governance census binding differs")
    _sha(census["execution_census_sha256"], label="execution census SHA")
    scheduler_sha = _sha(
        census["scheduler_census_sha256"], label="scheduler census SHA"
    )

    authorization_raw = census.get("governance_authorization")
    authorization = (
        _validate_governance_authorization(authorization_raw)
        if authorization_raw is not None
        else None
    )
    is_v2 = "terminal_scheduler_census_sha256" in census
    if not is_v2:
        if (
            authorization is not None
            and authorization["scheduler_census_sha256"] != scheduler_sha
        ):
            _fail("legacy terminal governance scheduler binding differs")
        return

    launch_sha = census["launch_governance_authorization_sha256"]
    terminal_scheduler_sha = census["terminal_scheduler_census_sha256"]
    if authorization is None:
        if launch_sha is not None or terminal_scheduler_sha != scheduler_sha:
            _fail("legacy terminal governance fingerprints differ")
        _sha(terminal_scheduler_sha, label="terminal scheduler census SHA")
        return
    if launch_sha != _transport_canonical_sha256(authorization):
        _fail("terminal launch governance fingerprint differs")
    _sha(launch_sha, label="terminal launch governance SHA")
    if authorization["governance_mode"] == "live-all-region-census":
        if (
            terminal_scheduler_sha != scheduler_sha
            or authorization["scheduler_census_sha256"] != scheduler_sha
        ):
            _fail("live terminal scheduler fingerprint differs")
        _sha(terminal_scheduler_sha, label="terminal scheduler census SHA")
    elif (
        terminal_scheduler_sha is not None
        or authorization["scheduler_census_sha256"] != scheduler_sha
    ):
        _fail("attested terminal scheduler fingerprint differs")


def _validate_transport_task_acceptance(
    receipt: Mapping[str, object],
    *,
    raw: bytes,
    carrier_identity: Mapping[str, object],
) -> dict[str, object]:
    if frozenset(receipt) != _TASK_ACCEPTANCE_FIELDS:
        _fail("authoritative task acceptance fields differ")
    if _transport_canonical_json_bytes(receipt) != raw:
        _fail("authoritative task acceptance is not canonical transport JSON")
    retained_self_hash = _sha(
        receipt["task_acceptance_sha256"], label="task acceptance SHA"
    )
    unhashed = {
        key: receipt[key] for key in receipt if key != "task_acceptance_sha256"
    }
    if retained_self_hash != _transport_canonical_sha256(unhashed):
        _fail("authoritative task acceptance self-hash differs")
    if receipt["schema_version"] != TASK_ACCEPTANCE_SCHEMA:
        _fail("authoritative task acceptance schema differs")
    _utc_timestamp(receipt["accepted_at_utc"], label="task acceptance timestamp")
    task_index = receipt["task_index"]
    if type(task_index) is not int or task_index < 0:
        _fail("task acceptance index differs")
    _sha(receipt["task_sha256"], label="accepted task SHA")
    for field in (
        "transport_contract",
        "retrieval_task0_prerequisite_identity",
        "producer_close",
        "science_terminal",
        "verifier_worker_completion",
        "independent_verification",
    ):
        _normalize_identity(receipt[field], label=f"task acceptance {field}")
    _same_identity(
        receipt["task_result"],
        carrier_identity,
        label="accepted task result",
    )
    _sha(
        receipt["independent_verification_sha256"],
        label="independent verification SHA",
    )
    if (
        receipt["evidence_object_count"] != 140
        or receipt["complete_evidence_receipt"] is not True
        or receipt["independent_verification_complete"] is not True
        or receipt["strict_verifier_terminal_success"] is not True
        or receipt["accepted"] is not True
        or receipt["partial_result"] is not False
        or any(receipt[field] is not False for field in (
            "automatic_retry_licensed",
            "uses_realized_outcomes",
            "historical_scoring_licensed",
            "corpus_fill_licensed",
            "graph_mutation_licensed",
            "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("authoritative task acceptance/license law differs")
    terminal = _validate_terminal_execution(
        receipt["verifier_terminal_execution"], task_index=task_index
    )
    _validate_terminal_census(
        receipt["terminal_governance_census"],
        task_index=task_index,
        terminal=terminal,
    )
    return {
        "acceptance_dialect": AUTHORITATIVE_ACCEPTANCE_DIALECT,
        "acceptance_schema": TASK_ACCEPTANCE_SCHEMA,
        "task_index": task_index,
        "task_acceptance_sha256": retained_self_hash,
        "authoritative_task_acceptance_verified": True,
        "accepted_task_result_binding_verified": True,
    }


def _validate_local_acceptance_receipt(
    receipt: Mapping[str, object],
    *,
    carrier_identity: Mapping[str, object],
    science_projection_sha256: str,
) -> dict[str, object]:
    expected_fields = {
        "arm_census",
        "carrier_identity",
        "defects",
        "gate",
        "passed",
        "science_projection_sha256",
        "solver_all_optimal",
        "uses_realized_outcomes",
        "verifier_accepted",
    }
    if set(receipt) != expected_fields or type(receipt["gate"]) is not str:
        _fail("task acceptance receipt fields differ")
    _same_identity(
        receipt["carrier_identity"], carrier_identity, label="accepted carrier"
    )
    if (
        receipt["passed"] is not True
        or receipt["verifier_accepted"] is not True
        or receipt["uses_realized_outcomes"] is not False
        or receipt["defects"] != []
        or receipt["science_projection_sha256"] != science_projection_sha256
    ):
        _fail("task acceptance receipt did not accept this outcome-blind science")
    census = _sequence(receipt["arm_census"], label="task acceptance arm census")
    if len(census) != len(PARAMETER_SET_ORDER):
        _fail("task acceptance census does not contain seven arms")
    for ordinal, raw_row in enumerate(census):
        row = _mapping(raw_row, label=f"task acceptance arm[{ordinal}]")
        if set(row) != {
            "attempted_visits",
            "optimal_visits",
            "ordinal",
            "parameter_set_id",
            "scheduled_visits",
            "selected_entries",
            "unique_candidates",
            "visit_roster_rows",
        } or any(
            type(row[field]) is not int or row[field] < 0
            for field in (
                "attempted_visits",
                "optimal_visits",
                "ordinal",
                "scheduled_visits",
                "selected_entries",
                "unique_candidates",
                "visit_roster_rows",
            )
        ):
            _fail(f"task acceptance arm[{ordinal}] fields differ")
        if (
            row.get("ordinal") != ordinal
            or row.get("parameter_set_id") != PARAMETER_SET_ORDER[ordinal]
        ):
            _fail("task acceptance arm ordering differs")
    return {
        "acceptance_dialect": LOCAL_ACCEPTANCE_DIALECT,
        "acceptance_schema": None,
        "task_index": None,
        "task_acceptance_sha256": None,
        "authoritative_task_acceptance_verified": False,
        "accepted_task_result_binding_verified": True,
    }


def _validate_acceptance_receipt(
    receipt: Mapping[str, object],
    *,
    raw: bytes,
    carrier_identity: Mapping[str, object],
    science_projection_sha256: str,
    require_authoritative: bool,
) -> dict[str, object]:
    if receipt.get("schema_version") == TASK_ACCEPTANCE_SCHEMA:
        return _validate_transport_task_acceptance(
            receipt,
            raw=raw,
            carrier_identity=carrier_identity,
        )
    if require_authoritative:
        _fail(
            "authoritative corpus-parametric-task-acceptance/v1 is required; "
            "the local independent-gate receipt is compatibility-only"
        )
    return _validate_local_acceptance_receipt(
        receipt,
        carrier_identity=carrier_identity,
        science_projection_sha256=science_projection_sha256,
    )


@dataclass(frozen=True)
class V12ImportedTask:
    carrier: Mapping[str, object]
    variant_results: tuple[Mapping[str, object], ...]
    compatibility_receipt: Mapping[str, object]


def reopen_v12_task(
    *,
    acceptance_receipt_identity: Mapping[str, object],
    carrier_identity: Mapping[str, object],
    read_exact: Callable[[Mapping[str, object]], bytes],
    require_authoritative: bool = True,
) -> V12ImportedTask:
    """Exact-read and structurally replay one independently accepted task."""
    accepted_identity, accepted_raw = _exact_read(
        acceptance_receipt_identity, read_exact, label="task acceptance receipt"
    )
    normalized_carrier, carrier_raw = _exact_read(
        carrier_identity, read_exact, label="accepted task carrier"
    )
    try:
        carrier, variants_raw = snapshot.read_task_variant_results(
            carrier_raw,
            carrier_identity=normalized_carrier,
            read_exact=read_exact,
            require_authoritative=require_authoritative,
        )
    except snapshot.CorpusParametricSnapshotError as exc:
        raise CorpusV12ImportError(str(exc)) from exc
    variants = tuple(variants_raw)
    dialect, result_rows = _carrier_result_rows(carrier)
    arms = _validate_retained_books(variants)
    science = snapshot.extract_task_science(variants)
    acceptance = _parse_json(accepted_raw, label="task acceptance receipt")
    acceptance_validation = _validate_acceptance_receipt(
        acceptance,
        raw=accepted_raw,
        carrier_identity=normalized_carrier,
        science_projection_sha256=str(science["science_projection_sha256"]),
        require_authoritative=require_authoritative,
    )
    hash_fields = [
        field for field in snapshot.CARRIER_HASH_FIELDS if field in carrier
    ]
    receipt: dict[str, object] = {
        "schema_version": IMPORT_RECEIPT_SCHEMA,
        "acceptance_receipt_identity": accepted_identity,
        "carrier_identity": normalized_carrier,
        "carrier_schema": carrier.get("schema", carrier.get("schema_version")),
        "carrier_hash_field": hash_fields[0],
        "carrier_dialect": dialect,
        "result_objects": result_rows,
        "slate": dict(variants[0]["slate"]),
        "later_source_freeze_manifest_sha256": variants[0][
            "later_source_freeze_manifest_sha256"
        ],
        "visit_schedule_sha256": variants[0]["visit_schedule_sha256"],
        "science_projection_sha256": science["science_projection_sha256"],
        "arms": arms,
        "acceptance_dialect": acceptance_validation["acceptance_dialect"],
        "acceptance_schema": acceptance_validation["acceptance_schema"],
        "accepted_task_index": acceptance_validation["task_index"],
        "accepted_task_acceptance_sha256": acceptance_validation[
            "task_acceptance_sha256"
        ],
        "acceptance_receipt_content_checks_passed": True,
        "authoritative_task_acceptance_verified": acceptance_validation[
            "authoritative_task_acceptance_verified"
        ],
        "accepted_task_result_binding_verified": acceptance_validation[
            "accepted_task_result_binding_verified"
        ],
        "independent_acceptance_authority_verified": acceptance_validation[
            "authoritative_task_acceptance_verified"
        ],
        "terminal_panel_membership_verified": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "promotion_authority": False,
    }
    receipt["compatibility_import_sha256"] = canonical_sha256(receipt)
    return V12ImportedTask(
        carrier=carrier,
        variant_results=variants,
        compatibility_receipt=receipt,
    )


def _world_row(value: object, *, label: str) -> dict[str, object]:
    if isinstance(value, Mapping):
        block = value.get("block")
        index = value.get("index")
    else:
        block = getattr(value, "block", None)
        index = getattr(value, "index", None)
    if block not in rw.WORLD_BLOCKS or type(index) is not int or index < 0:
        _fail(f"{label} is not a canonical world identity")
    return {"block": str(block), "index": index}


def build_candidate_provenance(
    variant_results: Sequence[Mapping[str, object]],
    *,
    visit_schedule: Sequence[object],
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Derive arm/block lineage from every visit occurrence, never first-only."""
    if len(variant_results) != len(PARAMETER_SET_ORDER):
        _fail("candidate provenance requires exactly seven ordered arms")
    schedule = [
        _world_row(value, label=f"visit schedule[{index}]")
        for index, value in enumerate(visit_schedule)
    ]
    if not schedule or len({(row["block"], row["index"]) for row in schedule}) != len(
        schedule
    ):
        _fail("visit schedule is empty or repeats a world")
    block_counts = Counter(str(row["block"]) for row in schedule)
    if set(block_counts) != set(rw.WORLD_BLOCKS) or len(set(block_counts.values())) != 1:
        _fail("visit schedule does not contain one balanced five-block dose")
    visits_per_block = next(iter(block_counts.values()))
    expected_block_order = [
        block for block in rw.WORLD_BLOCKS for _ in range(visits_per_block)
    ]
    if [row["block"] for row in schedule] != expected_block_order:
        _fail("visit schedule block order differs")
    if require_authoritative and visits_per_block != VISITS_PER_BLOCK:
        _fail("authoritative visit schedule dose differs")
    schedule_sha = canonical_sha256(schedule)
    slate = dict(_mapping(variant_results[0]["slate"], label="variant slate"))
    occurrence_by_id: dict[str, list[dict[str, object]]] = defaultdict(list)
    roster_by_id: dict[str, tuple[str, ...]] = {}
    for ordinal, raw_body in enumerate(variant_results):
        body = _mapping(raw_body, label=f"variant[{ordinal}]")
        profile = _mapping(body["profile"], label=f"variant[{ordinal}] profile")
        arm_id = PARAMETER_SET_ORDER[ordinal]
        if (
            profile.get("ordinal") != ordinal
            or profile.get("parameter_set_id") != arm_id
            or body["slate"] != slate
            or body["visit_schedule_sha256"] != schedule_sha
        ):
            _fail(f"variant[{ordinal}] schedule/slate/profile differs")
        visits = _sequence(
            body["visit_rosters"], label=f"variant[{ordinal}] visit rosters"
        )
        if len(visits) != len(schedule):
            _fail(f"variant[{ordinal}] visit coverage differs from schedule")
        replay_unique, replay_first = first_occurrence_unique(visits)
        retained_unique = tuple(
            tuple(str(player) for player in _sequence(
                roster, label=f"variant[{ordinal}] retained unique roster"
            ))
            for roster in _sequence(
                body["unique_rosters"],
                label=f"variant[{ordinal}] retained unique rosters",
            )
        )
        retained_first_raw = _sequence(
            body["first_occurrence_visit_indices"],
            label=f"variant[{ordinal}] first occurrence indices",
        )
        if any(type(value) is not int for value in retained_first_raw):
            _fail(f"variant[{ordinal}] first occurrence indices differ")
        retained_first = tuple(int(value) for value in retained_first_raw)
        if replay_unique != retained_unique or replay_first != retained_first:
            _fail(f"variant[{ordinal}] first-occurrence replay differs")
        for visit_ordinal, (roster_raw, world) in enumerate(
            zip(visits, schedule, strict=True)
        ):
            roster = tuple(str(player_id) for player_id in roster_raw)
            lineup_id = canonical_lineup_id(slate, roster)
            prior = roster_by_id.setdefault(lineup_id, roster)
            if prior != roster:
                _fail("lineup identity collision")
            occurrence_by_id[lineup_id].append({
                "arm_ordinal": ordinal,
                "parameter_set_id": arm_id,
                "visit_ordinal": visit_ordinal,
                "block_id": world["block"],
                "objective_world_index": world["index"],
            })

    candidates: list[dict[str, object]] = []
    for lineup_id in sorted(roster_by_id):
        occurrences = occurrence_by_id[lineup_id]
        by_block = Counter(str(row["block_id"]) for row in occurrences)
        arms_by_block = {
            block: sorted({
                str(row["parameter_set_id"])
                for row in occurrences
                if row["block_id"] == block
            })
            for block in rw.WORLD_BLOCKS
        }
        candidates.append({
            "lineup_id": lineup_id,
            "roster_player_ids": list(roster_by_id[lineup_id]),
            "origin_blocks": [block for block in rw.WORLD_BLOCKS if by_block[block]],
            "source_arms": sorted({
                str(row["parameter_set_id"]) for row in occurrences
            }),
            "occurrence_counts_by_block": {
                block: int(by_block[block]) for block in rw.WORLD_BLOCKS
            },
            "source_arms_by_block": arms_by_block,
            "occurrence_count": len(occurrences),
            "occurrences": occurrences,
        })
    body: dict[str, object] = {
        "schema_version": PROVENANCE_SCHEMA,
        "slate": slate,
        "visit_schedule_sha256": schedule_sha,
        "visits_per_block": visits_per_block,
        "arm_count": len(variant_results),
        "visit_occurrence_count": sum(
            len(row["visit_rosters"]) for row in variant_results
        ),
        "candidate_count": len(candidates),
        "lineup_order_law": "ascending-stable-per-slate-lineup-id",
        "candidates": candidates,
        "uses_realized_outcomes": False,
    }
    body["candidate_provenance_sha256"] = canonical_sha256(body)
    return body


@dataclass(frozen=True)
class V12ReconstructedTask:
    imported: V12ImportedTask
    prepared: object
    provenance: Mapping[str, object]
    union_rosters: tuple[tuple[str, ...], ...]
    union_scores: np.ndarray
    incumbent_books: Mapping[str, Sequence[tuple[str, ...]]]
    reconstruction_receipt: Mapping[str, object]


def reconstruct_v12_task(
    imported: V12ImportedTask,
    *,
    source_freeze: Mapping[str, object],
    artifact_bodies: Mapping[str, bytes],
) -> V12ReconstructedTask:
    """Verify retained score hashes and expose one canonical union matrix."""
    variants = imported.variant_results
    if len(variants) != len(PARAMETER_SET_ORDER):
        _fail("v12 reconstruction requires seven arms")
    slate = _mapping(variants[0]["slate"], label="v12 reconstruction slate")
    season = int(slate["season"])
    week = int(slate["week"])
    freeze_sha = str(variants[0]["later_source_freeze_manifest_sha256"])
    expected_blocks = dict(variants[0]["artifact_sha256_by_block"])
    if set(expected_blocks) != set(artifact_bodies):
        _fail("artifact bodies differ from the retained block set")
    for block, raw in artifact_bodies.items():
        if type(raw) is not bytes or sha256(raw).hexdigest() != expected_blocks[block]:
            _fail(f"artifact body for block {block!r} differs")
    prepared = prepare_later_slate(
        source_freeze,
        expected_source_freeze_sha256=freeze_sha,
        season=season,
        week=week,
        artifact_bodies=artifact_bodies,
    )
    schedule = canonical_visit_schedule(prepared)
    provenance = build_candidate_provenance(
        variants,
        visit_schedule=schedule,
        require_authoritative=True,
    )
    arm_receipts: list[dict[str, object]] = []
    incumbent_books: dict[str, list[tuple[str, ...]]] = {}
    for ordinal, body in enumerate(variants):
        if (
            body["slate"] != slate
            or body["later_source_freeze_manifest_sha256"] != freeze_sha
            or dict(body["artifact_sha256_by_block"]) != expected_blocks
        ):
            _fail(f"variant[{ordinal}] source/slate identity differs")
        unique = tuple(
            tuple(str(player) for player in roster)
            for roster in body["unique_rosters"]
        )
        arm_scores = cross_score_full_union(
            prepared.players, prepared.player_draws, unique
        )
        if _score_matrix_sha256(arm_scores) != body["candidate_score_sha256"]:
            _fail(f"variant[{ordinal}] candidate score reconstruction differs")
        selected_indices = [
            int(value) for value in body["selector"]["selected_indices"]
        ]
        selected_scores = np.ascontiguousarray(
            arm_scores[np.asarray(selected_indices, dtype=np.int64)],
            dtype=np.float64,
        )
        selected_scores.flags.writeable = False
        if _score_matrix_sha256(selected_scores) != body["selected_score_sha256"]:
            _fail(f"variant[{ordinal}] selected score reconstruction differs")
        arm_id = PARAMETER_SET_ORDER[ordinal]
        incumbent_books[arm_id] = [unique[index] for index in selected_indices]
        arm_receipts.append({
            "ordinal": ordinal,
            "parameter_set_id": arm_id,
            "candidate_score_sha256": body["candidate_score_sha256"],
            "selected_score_sha256": body["selected_score_sha256"],
            "unique_count": len(unique),
            "selected_count": len(selected_indices),
            "verified": True,
        })
        del arm_scores, selected_scores
    candidates = provenance["candidates"]
    canonical_rosters = tuple(
        tuple(str(player) for player in row["roster_player_ids"])
        for row in candidates
    )
    canonical_scores = cross_score_full_union(
        prepared.players, prepared.player_draws, canonical_rosters
    )
    canonical_scores.flags.writeable = False
    lineup_ids = [str(row["lineup_id"]) for row in candidates]
    world_ids = [
        {"block": world.block, "index": world.index}
        for world in prepared.world_ids
    ]
    matrix_binding: dict[str, object] = {
        "schema_version": MATRIX_BINDING_SCHEMA,
        "slate": provenance["slate"],
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "lineup_ids_sha256": canonical_sha256(lineup_ids),
        "world_ids_sha256": canonical_sha256(world_ids),
        "shape": list(canonical_scores.shape),
        "score_matrix_sha256": _score_matrix_sha256(canonical_scores),
        "uses_realized_outcomes": False,
    }
    matrix_binding["matrix_binding_sha256"] = canonical_sha256(matrix_binding)
    receipt: dict[str, object] = {
        "schema_version": RECONSTRUCTION_SCHEMA,
        "compatibility_import_sha256": imported.compatibility_receipt[
            "compatibility_import_sha256"
        ],
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "matrix_binding": matrix_binding,
        "verified_arm_score_hashes": arm_receipts,
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    receipt["reconstruction_sha256"] = canonical_sha256(receipt)
    return V12ReconstructedTask(
        imported=imported,
        prepared=prepared,
        provenance=provenance,
        union_rosters=canonical_rosters,
        union_scores=canonical_scores,
        incumbent_books=incumbent_books,
        reconstruction_receipt=receipt,
    )


__all__ = [
    "CorpusV12ImportError",
    "IMPORT_RECEIPT_SCHEMA",
    "LINEUP_ID_SCHEMA",
    "MATRIX_BINDING_SCHEMA",
    "PROVENANCE_SCHEMA",
    "RECONSTRUCTION_SCHEMA",
    "V12ImportedTask",
    "V12ReconstructedTask",
    "build_candidate_provenance",
    "canonical_lineup_id",
    "reconstruct_v12_task",
    "reopen_v12_task",
]
