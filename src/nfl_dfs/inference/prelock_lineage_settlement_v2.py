"""Keyed, source-bound post-lock readers for pre-lock lineage v2.

The readers are physically separate from capture and are intentionally
descriptive.  They exact-bind every supplied byte source, but do not claim
that a standings, entry bridge, or winner-registry adapter is official.  An
adoption or promotion process must replace the false authority flags only in a
separate reviewed adapter.  Candidate scores are joined by both immutable
``candidate_instance_id`` and ``roster_id``; list position has no meaning.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Final

import numpy as np

from .prelock_candidate_lineage_v1 import (
    canonical_json_bytes,
    canonical_sha256,
    validate_prelock_candidate_lineage_v1,
)
from .prelock_lineage_runtime_v2 import (
    build_sidecar_from_capture_v2,
    canonical_selector_matrix_bytes,
    validate_capture_authority_v2,
)

OUTCOME_BINDING_SCHEMA: Final = "prelock-lineage-descriptive-outcome-binding/v2"
CANDIDATE_SCORE_SCHEMA: Final = "prelock-lineage-keyed-candidate-scores/v2"
OPPORTUNITY_SCHEMA: Final = "prelock-lineage-keyed-opportunity-rosters/v2"
RESCUE_SCHEMA: Final = "prelock-lineage-individual-rescue/v2"
FIRST_LOSS_SCHEMA: Final = "prelock-lineage-first-loss-settlement/v2"
SOURCE_ROLES: Final = (
    "candidate-scores",
    "opportunity-rosters",
    "complete-standings",
    "entries-field-bridge",
    "standings-access-receipt",
    "winner-score",
    "winner-registry-v2",
)
FIRST_LOSS_STATES: Final = frozenset(
    {
        "NOT_PRODUCED_IN_OBSERVED_REQUEST_UNIVERSE",
        "NOT_ADMITTED",
        "ELIGIBLE_NOT_SELECTED",
        "FINAL_BOOK",
    }
)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


class PrelockLineageSettlementV2Error(ValueError):
    """Post-lock evidence does not exactly join the frozen pre-lock root."""


def _fail(message: str) -> None:
    raise PrelockLineageSettlementV2Error(message)


def _aware(value: object, *, label: str) -> datetime:
    if type(value) is not str:
        _fail(f"{label} is not ISO timestamp text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PrelockLineageSettlementV2Error(f"{label} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(f"{label} is not timezone-aware")
    return parsed.astimezone(UTC)


def _score(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail(f"{label} is not a nonnegative milli-point integer")
    return value


def _roster(values: object, *, label: str) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        _fail(f"{label} is not an ID array")
    retained = sorted(str(value).strip() for value in values)
    if len(retained) != 9 or any(not value for value in retained):
        _fail(f"{label} must contain nine nonempty IDs")
    if len(set(retained)) != 9:
        _fail(f"{label} repeats an ID")
    return retained


def _identity(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a provider identity")
    item = dict(value)
    fields = {"uri", "generation", "sha256", "bytes", "time_created_utc"}
    if set(item) != fields:
        _fail(f"{label} identity fields differ")
    if (
        type(item["uri"]) is not str
        or not item["uri"].startswith("gs://")
        or type(item["generation"]) is not str
        or not item["generation"].isdigit()
        or int(item["generation"]) < 1
        or type(item["sha256"]) is not str
        or _SHA256.fullmatch(item["sha256"]) is None
        or type(item["bytes"]) is not int
        or item["bytes"] < 1
    ):
        _fail(f"{label} identity is invalid")
    _aware(item["time_created_utc"], label=f"{label} creation time")
    return item


def _keyed_score_rows(value: object) -> list[dict[str, object]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail("candidate score rows are not an array")
    rows: list[dict[str, object]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping) or set(raw) != {
            "candidate_instance_id",
            "roster_id",
            "realized_score_milli",
        }:
            _fail(f"candidate score row {index} fields differ")
        candidate_id = raw["candidate_instance_id"]
        roster_id = raw["roster_id"]
        if type(candidate_id) is not str or not candidate_id:
            _fail(f"candidate score row {index} candidate ID differs")
        if type(roster_id) is not str or not roster_id:
            _fail(f"candidate score row {index} roster ID differs")
        rows.append(
            {
                "candidate_instance_id": candidate_id,
                "roster_id": roster_id,
                "realized_score_milli": _score(
                    raw["realized_score_milli"],
                    label=f"candidate score row {index}",
                ),
            }
        )
    rows.sort(key=lambda row: str(row["candidate_instance_id"]))
    keys = [(str(row["candidate_instance_id"]), str(row["roster_id"])) for row in rows]
    if (
        len(keys) != len(set(keys))
        or len({row["candidate_instance_id"] for row in rows}) != len(rows)
        or len({row["roster_id"] for row in rows}) != len(rows)
    ):
        _fail("candidate score rows contain duplicate join keys")
    return rows


def build_candidate_score_document_v2(
    *, slate_id: str, rows: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    normalized = _keyed_score_rows(rows)
    body: dict[str, object] = {
        "schema_version": CANDIDATE_SCORE_SCHEMA,
        "slate_id": slate_id,
        "rows": normalized,
        "row_count": len(normalized),
        "join_key": ["candidate_instance_id", "roster_id"],
    }
    body["document_sha256"] = canonical_sha256(body)
    return body


def _opportunity_rows(value: object) -> list[dict[str, object]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail("opportunity rows are not an array")
    rows: list[dict[str, object]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping) or set(raw) != {
            "opportunity_id",
            "internal_player_ids",
            "realized_score_milli",
        }:
            _fail(f"opportunity row {index} fields differ")
        opportunity_id = raw["opportunity_id"]
        if type(opportunity_id) is not str or not opportunity_id:
            _fail(f"opportunity row {index} ID differs")
        rows.append(
            {
                "opportunity_id": opportunity_id,
                "internal_player_ids": _roster(
                    raw["internal_player_ids"],
                    label=f"opportunity row {index} roster",
                ),
                "realized_score_milli": _score(
                    raw["realized_score_milli"],
                    label=f"opportunity row {index} score",
                ),
            }
        )
    rows.sort(key=lambda row: str(row["opportunity_id"]))
    if len({row["opportunity_id"] for row in rows}) != len(rows):
        _fail("opportunity IDs repeat")
    return rows


def build_opportunity_document_v2(
    *, slate_id: str, rows: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    normalized = _opportunity_rows(rows)
    body: dict[str, object] = {
        "schema_version": OPPORTUNITY_SCHEMA,
        "slate_id": slate_id,
        "rows": normalized,
        "row_count": len(normalized),
        "universe_scope": "SOURCE_SUPPLIED_VALUABLE_ROSTERS_NOT_FULL_LEGAL_SPACE",
    }
    body["document_sha256"] = canonical_sha256(body)
    return body


def _document(value: object, *, schema: str, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a mapping")
    item = json.loads(canonical_json_bytes(value))
    retained = item.pop("document_sha256", None)
    if (
        item.get("schema_version") != schema
        or type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or retained != canonical_sha256(item)
    ):
        _fail(f"{label} schema or self-hash differs")
    if schema == CANDIDATE_SCORE_SCHEMA:
        rows = _keyed_score_rows(item.get("rows"))
        if (
            rows != item["rows"]
            or item.get("row_count") != len(rows)
            or item.get("join_key") != ["candidate_instance_id", "roster_id"]
        ):
            _fail("candidate score document row contract differs")
    else:
        rows = _opportunity_rows(item.get("rows"))
        if rows != item["rows"] or item.get("row_count") != len(rows):
            _fail("opportunity document row contract differs")
    return {**item, "document_sha256": retained}


def build_descriptive_outcome_binding_v2(
    *,
    season: int,
    week: int,
    slate_id: str,
    lock_at_utc: str,
    settled_at_utc: str,
    candidate_score_document: Mapping[str, object],
    opportunity_document: Mapping[str, object],
    winner_score_milli: int,
    source_payloads: Mapping[str, bytes],
    source_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Bind all descriptive outcome inputs to exact reopened provider bytes."""

    lock = _aware(lock_at_utc, label="slate lock")
    settled = _aware(settled_at_utc, label="settlement time")
    if settled <= lock:
        _fail("settlement time is not after lock")
    if set(source_payloads) != set(SOURCE_ROLES) or set(source_identities) != set(
        SOURCE_ROLES
    ):
        _fail("outcome source role set differs")
    candidate = _document(
        candidate_score_document,
        schema=CANDIDATE_SCORE_SCHEMA,
        label="candidate score document",
    )
    opportunity = _document(
        opportunity_document,
        schema=OPPORTUNITY_SCHEMA,
        label="opportunity document",
    )
    if candidate["slate_id"] != slate_id or opportunity["slate_id"] != slate_id:
        _fail("outcome document slate differs")
    expected_documents = {
        "candidate-scores": canonical_json_bytes(candidate),
        "opportunity-rosters": canonical_json_bytes(opportunity),
    }
    identities: dict[str, dict[str, object]] = {}
    for role in SOURCE_ROLES:
        payload = source_payloads[role]
        if not isinstance(payload, bytes) or not payload:
            _fail(f"outcome source {role} payload is empty")
        identity = _identity(source_identities[role], label=role)
        if identity["sha256"] != sha256(payload).hexdigest() or identity[
            "bytes"
        ] != len(payload):
            _fail(f"outcome source {role} bytes differ from provider identity")
        created = _aware(identity["time_created_utc"], label=f"{role} creation")
        if created <= lock or created > settled:
            _fail(f"outcome source {role} creation is outside post-lock settlement")
        if role in expected_documents and payload != expected_documents[role]:
            _fail(f"outcome source {role} is not the exact keyed document")
        identities[role] = identity
    winner = _score(winner_score_milli, label="winner score")
    body: dict[str, object] = {
        "schema_version": OUTCOME_BINDING_SCHEMA,
        "season": int(season),
        "week": int(week),
        "slate_id": slate_id,
        "lock_at_utc": lock_at_utc,
        "settled_at_utc": settled_at_utc,
        "candidate_score_document": candidate,
        "opportunity_document": opportunity,
        "winner_score_milli": winner,
        "winner_record_sha256": canonical_sha256(
            {
                "season": int(season),
                "week": int(week),
                "slate_id": slate_id,
                "winner_score_milli": winner,
                "winner_source_identity": identities["winner-score"],
                "winner_registry_identity": identities["winner-registry-v2"],
            }
        ),
        "source_identities": identities,
        "exact_source_bytes_verified_at_build": True,
        "accepted_winner_registry_v2_verified": False,
        "official_standings_adapter_verified": False,
        "official_entries_bridge_adapter_verified": False,
        "settlement_authority": False,
        "decision_authority": False,
        "promotion_authority": False,
        "graph_mutation_authority": False,
        "uses_realized_outcomes": True,
        "post_lock_data_read": True,
    }
    body["binding_sha256"] = canonical_sha256(body)
    return validate_descriptive_outcome_binding_v2(body)


def validate_descriptive_outcome_binding_v2(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("outcome binding is not a mapping")
    item = json.loads(canonical_json_bytes(value))
    retained = item.pop("binding_sha256", None)
    if (
        item.get("schema_version") != OUTCOME_BINDING_SCHEMA
        or type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or retained != canonical_sha256(item)
    ):
        _fail("outcome binding schema or self-hash differs")
    for key, expected in {
        "exact_source_bytes_verified_at_build": True,
        "accepted_winner_registry_v2_verified": False,
        "official_standings_adapter_verified": False,
        "official_entries_bridge_adapter_verified": False,
        "settlement_authority": False,
        "decision_authority": False,
        "promotion_authority": False,
        "graph_mutation_authority": False,
        "uses_realized_outcomes": True,
        "post_lock_data_read": True,
    }.items():
        if item.get(key) is not expected:
            _fail("outcome binding authority boundary differs")
    lock = _aware(item.get("lock_at_utc"), label="binding lock")
    settled = _aware(item.get("settled_at_utc"), label="binding settlement")
    if settled <= lock:
        _fail("outcome binding settlement is not post-lock")
    candidate = _document(
        item.get("candidate_score_document"),
        schema=CANDIDATE_SCORE_SCHEMA,
        label="bound candidate scores",
    )
    opportunity = _document(
        item.get("opportunity_document"),
        schema=OPPORTUNITY_SCHEMA,
        label="bound opportunities",
    )
    if candidate["slate_id"] != item.get("slate_id") or opportunity[
        "slate_id"
    ] != item.get("slate_id"):
        _fail("bound outcome document slate differs")
    sources = item.get("source_identities")
    if not isinstance(sources, Mapping) or set(sources) != set(SOURCE_ROLES):
        _fail("bound outcome source roles differ")
    identities = {role: _identity(sources[role], label=role) for role in SOURCE_ROLES}
    if item.get("winner_record_sha256") != canonical_sha256(
        {
            "season": item["season"],
            "week": item["week"],
            "slate_id": item["slate_id"],
            "winner_score_milli": item["winner_score_milli"],
            "winner_source_identity": identities["winner-score"],
            "winner_registry_identity": identities["winner-registry-v2"],
        }
    ):
        _fail("winner score/provider binding differs")
    return {
        **item,
        "candidate_score_document": candidate,
        "opportunity_document": opportunity,
        "source_identities": identities,
        "binding_sha256": retained,
    }


def _lineage_indexes(sidecar: Mapping[str, object]) -> dict[str, Any]:
    header = sidecar["run_header"]
    effective_stage = header["effective_candidate_stage_id"]
    effective = sorted(
        [
            row
            for row in sidecar["admission_decisions"]
            if row["stage_id"] == effective_stage and row["disposition"] == "RETAINED"
        ],
        key=lambda row: int(row["candidate_ordinal"]),
    )
    strategy = sorted(
        sidecar["strategy_decisions"],
        key=lambda row: int(row["candidate_ordinal"]),
    )
    if len(effective) != len(strategy):
        _fail("effective/strategy candidate census differs")
    return {
        "effective": effective,
        "strategy": strategy,
        "strategy_by_candidate": {
            str(row["candidate_instance_id"]): row for row in strategy
        },
        "roster_by_internal": {
            tuple(row["internal_player_ids"]): row
            for row in sidecar["roster_identities"]
        },
        "admissions_by_roster": {
            roster_id: [
                row
                for row in sidecar["admission_decisions"]
                if row["roster_id"] == roster_id
            ]
            for roster_id in {
                str(row["roster_id"]) for row in sidecar["admission_decisions"]
            }
        },
        "final_by_roster": {
            str(row["roster_id"]): row
            for row in sidecar["book_transitions"]
            if row["export_rank"] is not None
        },
    }


def _joined_scores(
    sidecar: Mapping[str, object], binding: Mapping[str, object]
) -> list[int]:
    indexes = _lineage_indexes(sidecar)
    expected = {
        (str(row["candidate_instance_id"]), str(row["roster_id"]))
        for row in indexes["strategy"]
    }
    rows = binding["candidate_score_document"]["rows"]
    observed = {
        (str(row["candidate_instance_id"]), str(row["roster_id"])) for row in rows
    }
    if len(rows) != len(expected) or observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        _fail(
            f"candidate score join is not one-to-one (missing={missing}, extra={extra})"
        )
    by_key = {
        (str(row["candidate_instance_id"]), str(row["roster_id"])): int(
            row["realized_score_milli"]
        )
        for row in rows
    }
    return [
        by_key[(str(row["candidate_instance_id"]), str(row["roster_id"]))]
        for row in indexes["strategy"]
    ]


def _forced_binary_book(
    totals: np.ndarray,
    *,
    forced_index: int,
    n_entries: int,
    tail_line: float,
) -> list[int]:
    clears = totals >= tail_line
    p_line = clears.mean(axis=1)
    mean_total = totals.mean(axis=1)
    selected = [forced_index]
    covered = clears[forced_index].copy()
    remaining = set(range(len(totals))) - {forced_index}
    while len(selected) < n_entries and remaining:
        best = max(
            remaining,
            key=lambda index: (
                int(np.count_nonzero(clears[index] & ~covered)),
                p_line[index],
                mean_total[index],
            ),
        )
        if not np.count_nonzero(clears[best] & ~covered):
            break
        selected.append(best)
        covered |= clears[best]
        remaining.discard(best)
    fill = sorted(
        remaining,
        key=lambda index: (p_line[index], mean_total[index]),
        reverse=True,
    )
    selected += fill[: n_entries - len(selected)]
    return selected


def build_individual_rescue_v2(
    *,
    capture: Mapping[str, object],
    sidecar: Mapping[str, object],
    selector_matrix_bytes: bytes,
    outcome_binding: Mapping[str, object],
) -> dict[str, object]:
    """Force each omitted candidate separately using an exact keyed score join."""

    retained_capture = validate_capture_authority_v2(capture)
    retained_sidecar = validate_prelock_candidate_lineage_v1(sidecar)
    binding = validate_descriptive_outcome_binding_v2(outcome_binding)
    header = retained_sidecar["run_header"]
    sources = header["input_source_identities"]
    if (
        not isinstance(sources, list)
        or len(sources) != 1
        or sources[0].get("role") != "frozen-prelock-input-snapshot"
    ):
        _fail("rescue sidecar does not bind one capture authority")
    capture_identity = {
        key: sources[0][key] for key in ("uri", "generation", "sha256", "bytes")
    }
    try:
        expected_sidecar = build_sidecar_from_capture_v2(
            capture=retained_capture,
            capture_identity=capture_identity,
            frozen_at_utc=str(header["frozen_at_utc"]),
        )
    except ValueError as exc:
        raise PrelockLineageSettlementV2Error(
            "rescue capture cannot reproduce the bound sidecar"
        ) from exc
    if expected_sidecar != retained_sidecar:
        _fail("rescue capture and sidecar do not share one exact pre-lock root")
    if retained_sidecar["run_header"]["slate_id"] != binding["slate_id"]:
        _fail("settlement slate differs from pre-lock sidecar")
    expected_matrix = canonical_selector_matrix_bytes(
        retained_capture["effective_candidates"]["selector_matrix_archive"]
    )
    if not isinstance(selector_matrix_bytes, bytes) or selector_matrix_bytes != (
        expected_matrix
    ):
        _fail("settlement selector matrix differs from frozen bytes")
    archive = retained_capture["effective_candidates"]["selector_matrix_archive"]
    totals = np.frombuffer(selector_matrix_bytes, dtype=np.dtype(archive["dtype"]))
    totals = totals.reshape(tuple(archive["shape"])).copy()
    if not np.isfinite(totals).all():
        _fail("settlement selector matrix is nonfinite")
    indexes = _lineage_indexes(retained_sidecar)
    strategy = indexes["strategy"]
    scores = _joined_scores(retained_sidecar, binding)
    n_entries = int(retained_sidecar["run_header"]["entry_budget"])
    final_rows = sorted(
        [
            row
            for row in retained_sidecar["book_transitions"]
            if row["export_rank"] is not None
        ],
        key=lambda row: int(row["export_rank"]),
    )
    ordinal_by_candidate = {
        str(row["candidate_instance_id"]): int(row["candidate_ordinal"])
        for row in strategy
    }
    final_indices = [
        ordinal_by_candidate[str(row["candidate_instance_id"])] for row in final_rows
    ]
    if len(final_indices) != n_entries:
        _fail("settlement baseline book is not exact K")
    baseline_max = max(scores[index] for index in final_indices)
    tail_line = float(retained_capture["selector_configuration"]["tail_line"])
    if not math.isfinite(tail_line) or tail_line <= 0:
        _fail("frozen selector tail line differs")
    rows: list[dict[str, object]] = []
    for forced_index, decision in enumerate(strategy):
        if forced_index in final_indices:
            continue
        rescued = _forced_binary_book(
            totals,
            forced_index=forced_index,
            n_entries=n_entries,
            tail_line=tail_line,
        )
        rescued_max = max(scores[index] for index in rescued)
        rows.append(
            {
                "forced_candidate_ordinal": forced_index,
                "candidate_instance_id": decision["candidate_instance_id"],
                "roster_id": decision["roster_id"],
                "rescued_book_candidate_ordinals": rescued,
                "rescued_book_realized_max_milli": rescued_max,
                "individual_counterfactual_delta_milli": (rescued_max - baseline_max),
                "rescued_book_beat_bound_winner": (
                    rescued_max > binding["winner_score_milli"]
                ),
            }
        )
    body: dict[str, object] = {
        "schema_version": RESCUE_SCHEMA,
        "run_id": retained_sidecar["run_header"]["run_id"],
        "slate_id": binding["slate_id"],
        "sidecar_sha256": retained_sidecar["sidecar_sha256"],
        "capture_sha256": retained_capture["capture_sha256"],
        "outcome_binding_sha256": binding["binding_sha256"],
        "entry_budget": n_entries,
        "tail_line": tail_line,
        "baseline_final_candidate_ordinals": final_indices,
        "baseline_realized_max_milli": baseline_max,
        "winner_score_milli": binding["winner_score_milli"],
        "rows": rows,
        "sum_individual_counterfactual_delta_milli": sum(
            int(row["individual_counterfactual_delta_milli"]) for row in rows
        ),
        "sum_is_jointly_achievable": False,
        "counterfactual_scope": (
            "ONE_FORCED_CANDIDATE_AT_A_TIME_UNDER_EXACT_K_AND_FROZEN_WORLDS"
        ),
        "candidate_scores_joined_by_position": False,
        "candidate_scores_complete_one_to_one_join": True,
        "settlement_authority": False,
        "decision_authority": False,
        "promotion_authority": False,
        "graph_mutation_authority": False,
        "uses_realized_outcomes": True,
        "post_lock_data_read": True,
    }
    body["rescue_sha256"] = canonical_sha256(body)
    return body


def build_first_loss_settlement_v2(
    *, sidecar: Mapping[str, object], outcome_binding: Mapping[str, object]
) -> dict[str, object]:
    """Classify each source-bound valuable roster at its earliest known loss."""

    retained = validate_prelock_candidate_lineage_v1(sidecar)
    binding = validate_descriptive_outcome_binding_v2(outcome_binding)
    if retained["run_header"]["slate_id"] != binding["slate_id"]:
        _fail("first-loss slate differs")
    indexes = _lineage_indexes(retained)
    strategy_by_roster = {str(row["roster_id"]): row for row in indexes["strategy"]}
    rows: list[dict[str, object]] = []
    for ordinal, opportunity in enumerate(binding["opportunity_document"]["rows"]):
        internal = tuple(opportunity["internal_player_ids"])
        roster = indexes["roster_by_internal"].get(internal)
        roster_id = None if roster is None else str(roster["roster_id"])
        detail = None
        if roster_id is None:
            state = "NOT_PRODUCED_IN_OBSERVED_REQUEST_UNIVERSE"
        elif roster_id not in strategy_by_roster:
            state = "NOT_ADMITTED"
            rejected = [
                row
                for row in indexes["admissions_by_roster"].get(roster_id, [])
                if row["disposition"] == "REJECTED"
            ]
            if rejected:
                earliest = min(rejected, key=lambda row: int(row["stage_ordinal"]))
                detail = {
                    "stage_id": earliest["stage_id"],
                    "reason": earliest["reason"],
                }
        elif roster_id not in indexes["final_by_roster"]:
            state = "ELIGIBLE_NOT_SELECTED"
            detail = {"reason": strategy_by_roster[roster_id]["decision_reason"]}
        else:
            state = "FINAL_BOOK"
        if state not in FIRST_LOSS_STATES:
            _fail("first-loss classifier emitted an unknown state")
        score = int(opportunity["realized_score_milli"])
        rows.append(
            {
                "opportunity_id": opportunity["opportunity_id"],
                "opportunity_ordinal": ordinal,
                "internal_player_ids": list(internal),
                "roster_id": roster_id,
                "realized_score_milli": score,
                "gap_to_bound_winner_milli": score - int(binding["winner_score_milli"]),
                "beat_bound_winner": score > binding["winner_score_milli"],
                "first_observed_state": state,
                "state_detail": detail,
            }
        )
    counts = {
        state: sum(row["first_observed_state"] == state for row in rows)
        for state in sorted(FIRST_LOSS_STATES)
    }
    body: dict[str, object] = {
        "schema_version": FIRST_LOSS_SCHEMA,
        "run_id": retained["run_header"]["run_id"],
        "slate_id": binding["slate_id"],
        "sidecar_sha256": retained["sidecar_sha256"],
        "outcome_binding_sha256": binding["binding_sha256"],
        "winner_score_milli": binding["winner_score_milli"],
        "rows": rows,
        "state_counts": counts,
        "opportunity_universe_scope": binding["opportunity_document"]["universe_scope"],
        "causal_first_loss_claim": False,
        "settlement_authority": False,
        "decision_authority": False,
        "promotion_authority": False,
        "graph_mutation_authority": False,
        "uses_realized_outcomes": True,
        "post_lock_data_read": True,
    }
    body["settlement_sha256"] = canonical_sha256(body)
    return body


__all__ = [
    "CANDIDATE_SCORE_SCHEMA",
    "FIRST_LOSS_SCHEMA",
    "FIRST_LOSS_STATES",
    "OPPORTUNITY_SCHEMA",
    "OUTCOME_BINDING_SCHEMA",
    "RESCUE_SCHEMA",
    "SOURCE_ROLES",
    "PrelockLineageSettlementV2Error",
    "build_candidate_score_document_v2",
    "build_descriptive_outcome_binding_v2",
    "build_first_loss_settlement_v2",
    "build_individual_rescue_v2",
    "build_opportunity_document_v2",
    "validate_descriptive_outcome_binding_v2",
]
