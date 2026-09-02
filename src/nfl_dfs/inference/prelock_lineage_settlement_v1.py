"""Post-lock first-loss and one-at-a-time rescue readers for lineage v1.

Unlike the pre-lock capture modules, this module is explicitly
outcome-bearing.  It has no production, promotion, graph-mutation, or scoring
policy authority.  The rescue reader replays the frozen binary selector with
one candidate forced at a time; the resulting deltas are individual
counterfactuals and their sum is never represented as jointly achievable.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from hashlib import sha256
from typing import Any, Final

import numpy as np

from .prelock_candidate_lineage_v1 import canonical_sha256
from .prelock_lineage_runtime_v1 import (
    validate_prepared_entry_sidecar_v1,
    validate_runtime_envelope_v1,
)

FIRST_LOSS_SCHEMA: Final = "prelock-lineage-first-loss-settlement/v1"
RESCUE_SCHEMA: Final = "prelock-lineage-individual-rescue/v1"
FIRST_LOSS_STATES: Final = frozenset(
    {
        "NOT_PRODUCED_IN_OBSERVED_REQUEST_UNIVERSE",
        "NOT_ADMITTED",
        "SELECTOR_INELIGIBLE",
        "ELIGIBLE_NOT_SELECTED",
        "SELECTED_THEN_REPLACED",
        "FINAL_BOOK_NOT_PREPARED",
        "PREPARED_NOT_CONFIRMED",
        "PREPARED_CONFIRMED",
    }
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PrelockLineageSettlementError(ValueError):
    """Post-lock evidence did not match the exact pre-lock lineage root."""


def _fail(message: str) -> None:
    raise PrelockLineageSettlementError(message)


def _ids(values: object, *, label: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        _fail(f"{label} must be an ID array")
    retained = tuple(sorted(str(value).strip() for value in values))
    if len(retained) != 9 or any(not value for value in retained):
        _fail(f"{label} must contain nine nonempty IDs")
    if len(set(retained)) != 9:
        _fail(f"{label} repeats an ID")
    return retained


def _score_milli(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"{label} must be a nonnegative integer milli-point score")
    return value


def _settled_at(value: object, *, lock_at: str) -> str:
    if not isinstance(value, str):
        _fail("settled_at_utc must be timezone-aware ISO text")
    try:
        settled = datetime.fromisoformat(value)
        lock = datetime.fromisoformat(lock_at)
    except ValueError as exc:
        raise PrelockLineageSettlementError("settlement timestamp is invalid") from exc
    if settled.tzinfo is None or settled.utcoffset() is None or settled <= lock:
        _fail("settlement must occur after slate lock")
    return settled.isoformat()


def _lineage_indexes(candidate: Mapping[str, object]) -> dict[str, Any]:
    sidecar = candidate["sidecar"]
    roster_by_internal = {
        tuple(row["internal_player_ids"]): row for row in sidecar["roster_identities"]
    }
    effective_stage = sidecar["run_header"]["effective_candidate_stage_id"]
    effective = {
        row["roster_id"]: row
        for row in sidecar["admission_decisions"]
        if row["stage_id"] == effective_stage and row["disposition"] == "RETAINED"
    }
    strategy_by_roster = {
        row["roster_id"]: row for row in sidecar["strategy_decisions"]
    }
    book_by_roster = {row["roster_id"]: row for row in sidecar["book_transitions"]}
    admission_by_roster: dict[str, list[Mapping[str, object]]] = {}
    for row in sidecar["admission_decisions"]:
        admission_by_roster.setdefault(str(row["roster_id"]), []).append(row)
    return {
        "roster_by_internal": roster_by_internal,
        "effective": effective,
        "strategy_by_roster": strategy_by_roster,
        "book_by_roster": book_by_roster,
        "admission_by_roster": admission_by_roster,
    }


def reopen_frozen_selector_matrix_v1(
    *,
    candidate_envelope: Mapping[str, object],
    raw_bytes: bytes | bytearray | memoryview,
) -> np.ndarray:
    """Exact-reopen the create-once raw selector matrix named by the envelope."""

    candidate = validate_runtime_envelope_v1(candidate_envelope)
    if not isinstance(raw_bytes, (bytes, bytearray, memoryview)):
        _fail("frozen selector matrix payload is not bytes")
    payload = bytes(raw_bytes)
    identity = candidate["matrix_identities"]["effective_candidate_totals"]
    try:
        dtype = np.dtype(str(identity["dtype"]))
    except (TypeError, ValueError) as exc:  # validated upstream; defensive seam.
        raise PrelockLineageSettlementError(
            "frozen selector matrix dtype differs"
        ) from exc
    expected_bytes = int(np.prod(identity["shape"])) * dtype.itemsize
    if (
        len(payload) != expected_bytes
        or sha256(payload).hexdigest() != identity["sha256"]
    ):
        _fail("frozen selector matrix bytes differ from the pre-lock envelope")
    matrix = np.frombuffer(payload, dtype=dtype).reshape(identity["shape"]).copy()
    if not np.isfinite(matrix).all():
        _fail("frozen selector matrix contains a nonfinite value")
    matrix.flags.writeable = False
    return matrix


def build_first_loss_settlement_v1(
    *,
    candidate_envelope: Mapping[str, object],
    opportunity_rosters: Sequence[Mapping[str, object]],
    winner_score_milli: int,
    settled_at_utc: str,
    prepared_entry_sidecar: Mapping[str, object] | None = None,
    confirmed_entries: Sequence[Mapping[str, object]] = (),
) -> dict[str, Any]:
    """Assign every supplied valuable roster to one earliest observed state."""

    candidate = validate_runtime_envelope_v1(candidate_envelope)
    sidecar = candidate["sidecar"]
    header = sidecar["run_header"]
    winner = _score_milli(winner_score_milli, label="winner score")
    settlement_time = _settled_at(
        settled_at_utc, lock_at=str(header["slate_lock_at_utc"])
    )
    indexes = _lineage_indexes(candidate)
    prepared_by_roster: dict[str, Mapping[str, object]] = {}
    prepared_sha = None
    if prepared_entry_sidecar is not None:
        prepared = validate_prepared_entry_sidecar_v1(prepared_entry_sidecar)
        if prepared["candidate_envelope_sha256"] != candidate["envelope_sha256"]:
            _fail("prepared sidecar binds another candidate envelope")
        prepared_sha = prepared["sidecar_sha256"]
        prepared_by_roster = {
            str(row["roster_id"]): row for row in prepared["prepared_entries"]
        }
    if confirmed_entries and prepared_entry_sidecar is None:
        _fail("confirmed entries require an exact prepared-entry sidecar")
    confirmed: set[tuple[str, str, tuple[str, ...]]] = set()
    for row in confirmed_entries:
        contest_id = str(row.get("contest_id") or "")
        entry_id = str(row.get("entry_id") or "")
        if not contest_id or not entry_id:
            _fail("confirmed entry lacks contest or EntryID")
        confirmed.add(
            (
                contest_id,
                entry_id,
                _ids(
                    row.get("dk_draftable_ids"),
                    label="confirmed draftable roster",
                ),
            )
        )
    expected_confirmations = {
        (
            str(row["contest_id"]),
            str(row["entry_id"]),
            _ids(
                row["slot_dk_draftable_ids"],
                label="prepared confirmation roster",
            ),
        )
        for row in prepared_by_roster.values()
    }
    if not confirmed <= expected_confirmations:
        _fail("confirmed entry does not match an exact prepared EntryID and roster")

    rows: list[dict[str, Any]] = []
    seen_opportunity_ids: set[str] = set()
    for ordinal, opportunity in enumerate(opportunity_rosters):
        opportunity_id = str(opportunity.get("opportunity_id") or "")
        if not opportunity_id or opportunity_id in seen_opportunity_ids:
            _fail("opportunity IDs are blank or repeated")
        seen_opportunity_ids.add(opportunity_id)
        internal = _ids(
            opportunity.get("internal_player_ids"),
            label="opportunity roster",
        )
        score = _score_milli(
            opportunity.get("realized_score_milli"),
            label="opportunity realized score",
        )
        roster = indexes["roster_by_internal"].get(internal)
        roster_id = None if roster is None else str(roster["roster_id"])
        detail = None
        if roster_id is None:
            state = "NOT_PRODUCED_IN_OBSERVED_REQUEST_UNIVERSE"
        elif roster_id not in indexes["effective"]:
            state = "NOT_ADMITTED"
            admissions = indexes["admission_by_roster"].get(roster_id, [])
            rejected = [row for row in admissions if row["disposition"] == "REJECTED"]
            if rejected:
                earliest = min(rejected, key=lambda row: int(row["stage_ordinal"]))
                detail = {
                    "stage_id": earliest["stage_id"],
                    "reason": earliest["reason"],
                }
        else:
            strategy = indexes["strategy_by_roster"].get(roster_id)
            if strategy is None:
                _fail("effective roster lacks its selector decision")
            if strategy["eligibility"] == "INELIGIBLE":
                state = "SELECTOR_INELIGIBLE"
                detail = {"reason": strategy["eligibility_reason"]}
            elif strategy["decision"] == "NOT_SELECTED":
                state = "ELIGIBLE_NOT_SELECTED"
                detail = {"reason": strategy["decision_reason"]}
            else:
                transition = indexes["book_by_roster"].get(roster_id)
                if transition is None:
                    _fail("selected roster lacks its book transition")
                if transition["postselector_rank"] is None:
                    state = "SELECTED_THEN_REPLACED"
                    detail = {"reason": transition["reason"]}
                elif roster_id not in prepared_by_roster:
                    state = "FINAL_BOOK_NOT_PREPARED"
                else:
                    prepared_row = prepared_by_roster[roster_id]
                    confirmation_key = (
                        str(prepared_row["contest_id"]),
                        str(prepared_row["entry_id"]),
                        _ids(
                            prepared_row["slot_dk_draftable_ids"],
                            label="prepared confirmation roster",
                        ),
                    )
                    state = (
                        "PREPARED_CONFIRMED"
                        if confirmation_key in confirmed
                        else "PREPARED_NOT_CONFIRMED"
                    )
        if state not in FIRST_LOSS_STATES:
            _fail("first-loss classifier emitted an unknown state")
        rows.append(
            {
                "opportunity_id": opportunity_id,
                "opportunity_ordinal": ordinal,
                "internal_player_ids": list(internal),
                "roster_id": roster_id,
                "realized_score_milli": score,
                "gap_to_recorded_winner_milli": score - winner,
                "beat_recorded_winner": score > winner,
                "first_observed_state": state,
                "state_detail": detail,
            }
        )
    state_counts = {
        state: sum(row["first_observed_state"] == state for row in rows)
        for state in sorted(FIRST_LOSS_STATES)
    }
    body: dict[str, Any] = {
        "schema_version": FIRST_LOSS_SCHEMA,
        "candidate_envelope_sha256": candidate["envelope_sha256"],
        "prepared_entry_sidecar_sha256": prepared_sha,
        "run_id": header["run_id"],
        "slate_id": header["slate_id"],
        "settled_at_utc": settlement_time,
        "winner_score_milli": winner,
        "opportunity_universe_scope": (
            "CALLER_SUPPLIED_VALUABLE_ROSTERS; NOT_THE_FULL_LEGAL_UNIVERSE"
        ),
        "rows": rows,
        "state_counts": state_counts,
        "decision_authority": False,
        "promotion_authority": False,
        "graph_mutation_authority": False,
        "uses_realized_outcomes": True,
        "post_lock_data_read": True,
    }
    body["settlement_sha256"] = canonical_sha256(body)
    return body


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


def build_individual_rescue_v1(
    *,
    candidate_envelope: Mapping[str, object],
    candidate_totals: np.ndarray,
    realized_scores_milli: Sequence[int],
    winner_score_milli: int,
    tail_line: float,
    settled_at_utc: str,
) -> dict[str, Any]:
    """Force each omitted effective candidate separately under exact K."""

    candidate = validate_runtime_envelope_v1(candidate_envelope)
    sidecar = candidate["sidecar"]
    header = sidecar["run_header"]
    settlement_time = _settled_at(
        settled_at_utc, lock_at=str(header["slate_lock_at_utc"])
    )
    totals = np.asarray(candidate_totals)
    matrix_identity = candidate["matrix_identities"]["effective_candidate_totals"]
    if (
        totals.ndim != 2
        or not np.isfinite(totals).all()
        or list(totals.shape) != matrix_identity["shape"]
        or totals.dtype.str != matrix_identity["dtype"]
        or sha256(np.ascontiguousarray(totals).tobytes()).hexdigest()
        != matrix_identity["sha256"]
    ):
        _fail("rescue candidate matrix differs from the frozen pre-lock matrix")
    strategy = sorted(
        sidecar["strategy_decisions"],
        key=lambda row: int(row["candidate_ordinal"]),
    )
    if len(strategy) != len(totals):
        _fail("rescue strategy and matrix candidate counts differ")
    try:
        retained_tail = float(tail_line)
    except (TypeError, ValueError) as exc:
        raise PrelockLineageSettlementError("rescue tail line is not numeric") from exc
    if not np.isfinite(retained_tail) or retained_tail <= 0.0:
        _fail("rescue tail line is not finite and positive")
    frozen_objective = candidate["selector_objective"]
    if retained_tail != float(frozen_objective["tail_line"]):
        _fail("rescue tail line differs from the exact frozen line")
    expected_objective = str(frozen_objective["objective_id"])
    if {str(row["objective_id"]) for row in strategy} != {expected_objective}:
        _fail("rescue tail line differs from the frozen selector objective")
    scores = [
        _score_milli(value, label=f"candidate score[{index}]")
        for index, value in enumerate(realized_scores_milli)
    ]
    if len(scores) != len(totals):
        _fail("rescue realized-score census differs")
    n_entries = int(header["entry_budget"])
    final_rows = sorted(
        (row for row in sidecar["book_transitions"] if row["export_rank"] is not None),
        key=lambda row: int(row["export_rank"]),
    )
    candidate_index_by_instance = {
        str(row["candidate_instance_id"]): int(row["candidate_ordinal"])
        for row in strategy
    }
    final_indices = [
        candidate_index_by_instance[str(row["candidate_instance_id"])]
        for row in final_rows
    ]
    if len(final_indices) != n_entries:
        _fail("rescue baseline final book is not exact K")
    baseline_max = max(scores[index] for index in final_indices)
    winner = _score_milli(winner_score_milli, label="winner score")
    rows = []
    for forced_index, decision in enumerate(strategy):
        if forced_index in final_indices or decision["eligibility"] != "ELIGIBLE":
            continue
        rescued = _forced_binary_book(
            totals,
            forced_index=forced_index,
            n_entries=n_entries,
            tail_line=retained_tail,
        )
        if len(rescued) != n_entries:
            _fail("individual rescue did not preserve exact K")
        rescued_max = max(scores[index] for index in rescued)
        rows.append(
            {
                "forced_candidate_ordinal": forced_index,
                "candidate_instance_id": decision["candidate_instance_id"],
                "roster_id": decision["roster_id"],
                "original_decision": decision["decision_reason"],
                "rescued_book_candidate_ordinals": rescued,
                "rescued_book_realized_max_milli": rescued_max,
                "individual_counterfactual_delta_milli": (rescued_max - baseline_max),
                "rescued_book_beat_recorded_winner": rescued_max > winner,
            }
        )
    body: dict[str, Any] = {
        "schema_version": RESCUE_SCHEMA,
        "candidate_envelope_sha256": candidate["envelope_sha256"],
        "run_id": header["run_id"],
        "slate_id": header["slate_id"],
        "settled_at_utc": settlement_time,
        "tail_line": retained_tail,
        "entry_budget": n_entries,
        "baseline_final_candidate_ordinals": final_indices,
        "baseline_realized_max_milli": baseline_max,
        "winner_score_milli": winner,
        "rows": rows,
        "sum_individual_counterfactual_delta_milli": sum(
            row["individual_counterfactual_delta_milli"] for row in rows
        ),
        "sum_is_jointly_achievable": False,
        "counterfactual_scope": (
            "ONE_FORCED_CANDIDATE_AT_A_TIME_UNDER_EXACT_K_AND_FROZEN_WORLDS"
        ),
        "decision_authority": False,
        "promotion_authority": False,
        "graph_mutation_authority": False,
        "uses_realized_outcomes": True,
        "post_lock_data_read": True,
    }
    body["rescue_sha256"] = canonical_sha256(body)
    return body


__all__ = [
    "FIRST_LOSS_SCHEMA",
    "FIRST_LOSS_STATES",
    "RESCUE_SCHEMA",
    "PrelockLineageSettlementError",
    "build_first_loss_settlement_v1",
    "build_individual_rescue_v1",
    "reopen_frozen_selector_matrix_v1",
]
