"""Default-off runtime adapter for the immutable pre-lock lineage contract.

This module observes existing generator, admission, and selector seams.  It
does not generate, select, score, persist to a graph, or read an outcome.  An
armed capture is completed synchronously before the engine's legacy
actual-score diagnostics execute; a capture callback may therefore publish
the returned canonical envelope create-once before allowing the build to
continue.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Final

import numpy as np

from .generation_exposure import validate_ledger
from .prelock_candidate_lineage_v1 import (
    ROSTER_IDENTITY_SCHEMA,
    PrelockCandidateLineageError,
    assert_outcome_free,
    build_prelock_candidate_lineage_v1,
    canonical_json_bytes,
    canonical_sha256,
    validate_prelock_candidate_lineage_v1,
)

RUNTIME_ENVELOPE_SCHEMA: Final = "prelock-lineage-runtime-envelope/v1"
PREPARED_SIDECAR_SCHEMA: Final = "prelock-prepared-entry-sidecar/v1"
TERMINAL_ROOT_SCHEMA: Final = "prelock-lineage-terminal-root/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PrelockLineageRuntimeError(ValueError):
    """Runtime evidence could not satisfy the immutable lineage contract."""


def _fail(message: str) -> None:
    raise PrelockLineageRuntimeError(message)


def _clone(value: object) -> Any:
    try:
        import json

        return json.loads(canonical_json_bytes(value))
    except PrelockCandidateLineageError as exc:
        raise PrelockLineageRuntimeError(str(exc)) from exc


def _ids(values: object, *, label: str) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        _fail(f"{label} must be an ID array")
    retained = sorted(str(value).strip() for value in values)
    if len(retained) != 9 or any(not value for value in retained):
        _fail(f"{label} must contain nine nonempty IDs")
    if len(set(retained)) != 9:
        _fail(f"{label} repeats an ID")
    return retained


def _roster_id(slate_id: str, internal_ids: Sequence[object]) -> str:
    payload = {
        "schema_version": ROSTER_IDENTITY_SCHEMA,
        "slate_id": slate_id,
        "internal_player_id_namespace": "production-lineup-id-v1",
        "internal_player_ids": _ids(list(internal_ids), label="internal roster"),
    }
    return "roster-v1-" + canonical_sha256(payload)


def _array_identity(value: object, *, label: str) -> dict[str, object]:
    retained = np.asarray(value)
    if retained.ndim != 2 or not np.isfinite(retained).all():
        _fail(f"{label} must be a finite two-dimensional array")
    contiguous = np.ascontiguousarray(retained)
    return {
        "dtype": contiguous.dtype.str,
        "shape": [int(size) for size in contiguous.shape],
        "sha256": sha256(contiguous.tobytes(order="C")).hexdigest(),
    }


def _validate_array_identity(value: object, *, label: str) -> dict[str, object]:
    item = _clone(value)
    if set(item) != {"dtype", "shape", "sha256"}:
        _fail(f"{label} identity fields differ")
    try:
        dtype = np.dtype(item["dtype"])
    except (TypeError, ValueError) as exc:
        raise PrelockLineageRuntimeError(f"{label} dtype differs") from exc
    shape = item["shape"]
    if (
        not isinstance(shape, list)
        or len(shape) != 2
        or any(
            not isinstance(size, int) or isinstance(size, bool) or size < 1
            for size in shape
        )
    ):
        _fail(f"{label} shape differs")
    digest = item["sha256"]
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        _fail(f"{label} SHA-256 differs")
    return {
        "dtype": dtype.str,
        "shape": list(shape),
        "sha256": digest,
    }


def _source_config(metadata: object) -> dict[str, object]:
    source = metadata if isinstance(metadata, Mapping) else {}
    allowed = (
        "model_version",
        "role_model_version",
        "candidate_input_receipt",
        "role_candidate_input_receipt",
        "construction_preset_receipt",
        "generation_allocation",
        "latent_scenario_receipt",
        "latent_optimization_receipt",
    )
    semantic = {
        key: _clone(source[key])
        for key in allowed
        if key in source and source[key] not in ({}, (), [], None, "")
    }
    assert_outcome_free(semantic)
    return semantic


def _source_config_sha256(metadata: object) -> str:
    return canonical_sha256(_source_config(metadata))


def _lineup_rosters(batch: object) -> list[list[str]]:
    try:
        candidates = batch.candidates
    except AttributeError as exc:
        raise PrelockLineageRuntimeError("candidate batch lacks candidates") from exc
    return [
        _ids(list(lineup.ids), label=f"candidate roster[{ordinal}]")
        for ordinal, lineup in enumerate(candidates)
    ]


class RuntimePrelockLineageRecorder:
    """Collect one canonical-CBWU run and synchronously seal its envelope."""

    def __init__(
        self,
        *,
        run_header: Mapping[str, object],
        internal_to_draftable: Mapping[object, object],
        salary_catalog_sha256: str,
        artifact_capture: Callable[[Mapping[str, object]], None] | None = None,
        matrix_artifact_capture: (
            Callable[[bytes, Mapping[str, object]], None] | None
        ) = None,
        frozen_at_utc_factory: Callable[[], str] | None = None,
        legacy_lineup_ids_by_internal_sha256: (
            Mapping[str, Sequence[str]] | None
        ) = None,
    ) -> None:
        header = _clone(run_header)
        if (
            header.get("paid_strategy_id") is not None
            or header.get("contest_id") is not None
        ):
            _fail("phase-1 candidate capture requires a non-paid shadow header")
        if (
            not isinstance(salary_catalog_sha256, str)
            or _SHA256.fullmatch(salary_catalog_sha256) is None
        ):
            _fail("salary catalog SHA-256 differs")
        bridge: dict[str, str] = {}
        for internal, draftable in internal_to_draftable.items():
            internal_id = str(internal).strip()
            draftable_id = str(draftable).strip()
            if not internal_id or not draftable_id or internal_id in bridge:
                _fail("player identity bridge is missing or ambiguous")
            bridge[internal_id] = draftable_id
        if not bridge or len(set(bridge.values())) != len(bridge):
            _fail("player identity bridge is empty or many-to-one")
        self._header = header
        self._bridge = bridge
        self._salary_catalog_sha256 = salary_catalog_sha256
        self._artifact_capture = artifact_capture
        self._matrix_artifact_capture = matrix_artifact_capture
        self._frozen_at_utc_factory = frozen_at_utc_factory
        if self._header.get("frozen_at_utc") is None and frozen_at_utc_factory is None:
            _fail("runtime lineage requires a freeze time or time factory")
        self._aliases = {
            str(key): sorted(str(value) for value in values)
            for key, values in (legacy_lineup_ids_by_internal_sha256 or {}).items()
        }
        self._pool_events: dict[str, dict[str, Any]] = {}
        self._native: dict[str, dict[str, Any]] = {}
        self._cbwu: dict[str, Any] | None = None
        self._artifact: dict[str, Any] | None = None

    @property
    def artifact(self) -> dict[str, Any] | None:
        return None if self._artifact is None else _clone(self._artifact)

    def __call__(self, stage: str, payload: Mapping[str, object]) -> None:
        if self._artifact is not None:
            _fail("runtime lineage envelope is already sealed")
        if stage == "pool_cap_admission":
            event = _clone(payload)
            assert_outcome_free(event)
            source = str(event.get("source_label") or "")
            if not source or source in self._pool_events:
                _fail("pool admission source is blank or repeated")
            self._pool_events[source] = event
            return
        if stage == "native_candidate_batch":
            self._capture_native(payload)
            return
        if stage == "cbwu_admission":
            if self._cbwu is not None:
                _fail("CBWU admission was captured more than once")
            event = _clone(payload)
            assert_outcome_free(event)
            self._cbwu = event
            return
        if stage == "effective_candidate_selection":
            self._capture_effective(payload)
            return
        _fail(f"unknown runtime lineage stage {stage!r}")

    def _capture_native(self, payload: Mapping[str, object]) -> None:
        if set(payload) != {"source_label", "batch"}:
            _fail("native candidate event fields differ")
        source = str(payload["source_label"])
        if not source or source in self._native:
            _fail("native source is blank or repeated")
        batch = payload["batch"]
        try:
            metadata = batch.metadata
            player_ids = [str(value) for value in batch.player_ids]
            ledger_value = metadata.get("generation_exposure_ledger")
        except AttributeError as exc:
            raise PrelockLineageRuntimeError(
                "native candidate batch is malformed"
            ) from exc
        if set(player_ids) - set(self._bridge):
            _fail("native player universe lacks draftable-ID mappings")
        if ledger_value is None:
            _fail("native candidate batch lacks its exposure ledger")
        try:
            ledger = validate_ledger(ledger_value)
        except ValueError as exc:
            raise PrelockLineageRuntimeError(
                "native solve exposure ledger is invalid"
            ) from exc
        if ledger["source_label"] != source:
            _fail("native source and solve ledger source differ")
        self._native[source] = {
            "source_label": source,
            "ledger": ledger,
            "candidate_rosters": _lineup_rosters(batch),
            "candidate_totals_identity": _array_identity(
                batch.candidate_totals, label="native candidate totals"
            ),
            "player_worlds_identity": _array_identity(
                batch.row_draws, label="native player worlds"
            ),
            "candidate_order_sha256": canonical_sha256(_lineup_rosters(batch)),
            "generator_config_sha256": _source_config_sha256(metadata),
            "generator_config": _source_config(metadata),
        }

    def _roster_raw(self, internal_ids: Sequence[object]) -> dict[str, object]:
        retained = _ids(list(internal_ids), label="lineage roster")
        try:
            pairs = [
                {
                    "internal_player_id": internal_id,
                    "draftable_player_id": self._bridge[internal_id],
                }
                for internal_id in retained
            ]
        except KeyError as exc:
            raise PrelockLineageRuntimeError(
                "generated roster lacks a draftable-ID bridge"
            ) from exc
        internal_sha = canonical_sha256(retained)
        return {
            "slate_id": self._header["slate_id"],
            "internal_player_id_namespace": "production-lineup-id-v1",
            "draftable_player_id_namespace": "draftkings-draftable-id-v1",
            "player_id_bridge": pairs,
            "salary_catalog_sha256": self._salary_catalog_sha256,
            "legacy_lineup_ids": self._aliases.get(internal_sha, []),
        }

    def _generation_records(self) -> dict[str, Any]:
        proposals: list[dict[str, object]] = []
        attempts: list[dict[str, object]] = []
        occurrences: list[dict[str, object]] = []
        dedupe: list[dict[str, object]] = []
        roster_raw_by_id: dict[str, dict[str, object]] = {}
        occurrence_ids_by_source_roster: dict[tuple[str, str], list[str]] = defaultdict(
            list
        )
        first_occurrence: dict[str, dict[str, object]] = {}
        request_meta: dict[str, tuple[str, str]] = {}
        new_rosters_by_source: dict[str, set[str]] = defaultdict(set)

        status = {
            "new": "PRODUCED",
            "dup": "PRODUCED",
            "infeasible": "INFEASIBLE",
            "error": "SOLVER_ERROR",
        }
        for source, native in self._native.items():
            ledger = native["ledger"]
            rows_by_request: dict[tuple[str, int], list[Mapping[str, object]]] = (
                defaultdict(list)
            )
            for row in ledger["rows"]:
                rows_by_request[
                    (str(row["family"]), int(row["requested_ordinal"]))
                ].append(row)
            for family, expected in sorted(
                ledger["expected_requests_by_family"].items()
            ):
                for requested in range(int(expected)):
                    chain = rows_by_request[(str(family), requested)]
                    exhausted = [row for row in chain if row["status"] == "exhausted"]
                    if exhausted:
                        if len(chain) != 1:
                            _fail("exhausted request also carries attempts")
                        terminal = "EXHAUSTED_NOT_ATTEMPTED"
                        attempted: list[Mapping[str, object]] = []
                    else:
                        terminal = status[str(chain[-1]["status"])]
                        attempted = chain
                    request_id = f"request-{len(proposals):06d}"
                    request_meta[request_id] = (source, str(family))
                    world_ids = {
                        int(row["world_id"])
                        for row in chain
                        if row["world_id"] is not None
                    }
                    if len(world_ids) > 1:
                        _fail("one proposal request spans multiple world IDs")
                    proposals.append(
                        {
                            "request_id": request_id,
                            "request_ordinal": len(proposals),
                            "source_label": source,
                            "family": str(family),
                            "requested_ordinal": requested,
                            "world_id": next(iter(world_ids), None),
                            "generator_config_sha256": native[
                                "generator_config_sha256"
                            ],
                            "terminal_status": terminal,
                        }
                    )
                    for row in attempted:
                        attempt_id = f"attempt-{len(attempts):06d}"
                        roster_id = None
                        if row["status"] in {"new", "dup"}:
                            internal_ids = _ids(row["player_ids"], label="solve roster")
                            roster_id = _roster_id(
                                str(self._header["slate_id"]), internal_ids
                            )
                            roster_raw_by_id.setdefault(
                                roster_id, self._roster_raw(internal_ids)
                            )
                            if row["status"] == "new":
                                new_rosters_by_source[source].add(roster_id)
                        attempts.append(
                            {
                                "attempt_id": attempt_id,
                                "attempt_ordinal": len(attempts),
                                "request_id": request_id,
                                "retry_ordinal": int(row["retry_ordinal"]),
                                "status": status[str(row["status"])],
                                "roster_id": roster_id,
                            }
                        )
                        if roster_id is None:
                            continue
                        occurrence_id = f"occurrence-{len(occurrences):06d}"
                        occurrence = {
                            "occurrence_id": occurrence_id,
                            "occurrence_ordinal": len(occurrences),
                            "attempt_id": attempt_id,
                            "request_id": request_id,
                            "roster_id": roster_id,
                        }
                        occurrences.append(occurrence)
                        occurrence_ids_by_source_roster[(source, roster_id)].append(
                            occurrence_id
                        )
                        prior = first_occurrence.get(roster_id)
                        if prior is None:
                            disposition = "FIRST_SEEN"
                            duplicate_of = None
                            first_occurrence[roster_id] = occurrence
                        else:
                            prior_source, prior_family = request_meta[
                                str(prior["request_id"])
                            ]
                            disposition = (
                                "DUPLICATE_CROSS_SEED"
                                if prior_source != source
                                else "DUPLICATE_CROSS_FAMILY"
                                if prior_family != str(family)
                                else "DUPLICATE_SAME_FAMILY"
                            )
                            duplicate_of = prior["occurrence_id"]
                        dedupe.append(
                            {
                                "decision_id": f"dedupe-{len(dedupe):06d}",
                                "occurrence_id": occurrence_id,
                                "roster_id": roster_id,
                                "disposition": disposition,
                                "duplicate_of_occurrence_id": duplicate_of,
                            }
                        )
        return {
            "roster_raw_by_id": roster_raw_by_id,
            "proposal_requests": proposals,
            "solve_attempts": attempts,
            "generated_occurrences": occurrences,
            "dedupe_decisions": dedupe,
            "occurrence_ids_by_source_roster": (occurrence_ids_by_source_roster),
            "new_rosters_by_source": new_rosters_by_source,
        }

    def _admission_records(
        self,
        generation: Mapping[str, Any],
        effective_rosters: Sequence[Sequence[str]],
    ) -> tuple[list[dict[str, object]], dict[int, str]]:
        if set(self._pool_events) != set(self._native):
            _fail("native and pool-admission source censuses differ")
        admissions: list[dict[str, object]] = []
        native_output_instance: dict[tuple[str, int], str] = {}
        stage_ordinal = 0
        for source, native in self._native.items():
            event = self._pool_events[source]
            rows = event.get("rows")
            if not isinstance(rows, list):
                _fail("pool-admission rows differ")
            event_rosters = {
                _roster_id(str(self._header["slate_id"]), row["internal_player_ids"])
                for row in rows
            }
            if event_rosters != generation["new_rosters_by_source"][source]:
                _fail("pool admission does not cover every new solve roster")
            retained_in_order: list[tuple[int, str]] = []
            for candidate_ordinal, row in enumerate(rows):
                if int(row["input_ordinal"]) != candidate_ordinal:
                    _fail("pool-admission input order differs")
                roster_id = _roster_id(
                    str(self._header["slate_id"]),
                    row["internal_player_ids"],
                )
                occurrence_ids = generation["occurrence_ids_by_source_roster"][
                    (source, roster_id)
                ]
                if not occurrence_ids:
                    _fail("native admission lacks a generated occurrence")
                instance_id = (
                    f"candidate-native-{stage_ordinal:02d}-{candidate_ordinal:06d}"
                )
                admissions.append(
                    {
                        "decision_id": f"admission-{len(admissions):06d}",
                        "stage_id": f"native-{source.lower()}",
                        "stage_ordinal": stage_ordinal,
                        "candidate_instance_id": instance_id,
                        "candidate_ordinal": candidate_ordinal,
                        "roster_id": roster_id,
                        "source_occurrence_ids": list(occurrence_ids),
                        "input_candidate_instance_ids": [],
                        "admission_preset_id": str(event["schema_version"]),
                        "disposition": ("RETAINED" if row["retained"] else "REJECTED"),
                        "reason": str(row["reason"]),
                    }
                )
                if row["retained"]:
                    output = int(row["output_ordinal"])
                    retained_in_order.append((output, roster_id))
                    native_output_instance[(source, output)] = instance_id
            retained_in_order.sort()
            if [roster for _, roster in retained_in_order] != [
                _roster_id(str(self._header["slate_id"]), roster)
                for roster in native["candidate_rosters"]
            ]:
                _fail("pool-admission retained order differs from native batch")
            stage_ordinal += 1

        effective_instance: dict[int, str] = {}
        if self._cbwu is not None:
            rows = self._cbwu.get("rows")
            if not isinstance(rows, list):
                _fail("CBWU admission rows differ")
            retained_by_output: list[tuple[int, str]] = []
            for candidate_ordinal, row in enumerate(rows):
                source_key = (str(row["source_seed"]), int(row["source_ordinal"]))
                source_instance = native_output_instance.get(source_key)
                if source_instance is None:
                    _fail("CBWU admission references an unknown native candidate")
                roster_id = _roster_id(
                    str(self._header["slate_id"]),
                    row["internal_player_ids"],
                )
                instance_id = f"candidate-effective-{candidate_ordinal:06d}"
                admissions.append(
                    {
                        "decision_id": f"admission-{len(admissions):06d}",
                        "stage_id": str(self._header["effective_candidate_stage_id"]),
                        "stage_ordinal": stage_ordinal,
                        "candidate_instance_id": instance_id,
                        "candidate_ordinal": candidate_ordinal,
                        "roster_id": roster_id,
                        "source_occurrence_ids": [],
                        "input_candidate_instance_ids": [source_instance],
                        "admission_preset_id": str(self._cbwu["schema_version"]),
                        "disposition": ("RETAINED" if row["retained"] else "REJECTED"),
                        "reason": str(row["reason"]),
                    }
                )
                if row["retained"]:
                    output = int(row["output_ordinal"])
                    retained_by_output.append((output, roster_id))
                    effective_instance[output] = instance_id
            retained_by_output.sort()
            expected = [
                _roster_id(str(self._header["slate_id"]), roster)
                for roster in effective_rosters
            ]
            if [roster for _, roster in retained_by_output] != expected:
                _fail("CBWU retained order differs from the effective batch")
        else:
            if len(self._native) != 1:
                _fail("multi-source lineage requires a CBWU admission trace")
            source = next(iter(self._native))
            native = self._native[source]
            native_ids = [
                _roster_id(str(self._header["slate_id"]), roster)
                for roster in native["candidate_rosters"]
            ]
            expected = [
                _roster_id(str(self._header["slate_id"]), roster)
                for roster in effective_rosters
            ]
            if native_ids != expected:
                _fail("phase-1 single-source transform changed candidates")
            for candidate_ordinal, roster_id in enumerate(expected):
                source_instance = native_output_instance[(source, candidate_ordinal)]
                instance_id = f"candidate-effective-{candidate_ordinal:06d}"
                admissions.append(
                    {
                        "decision_id": f"admission-{len(admissions):06d}",
                        "stage_id": str(self._header["effective_candidate_stage_id"]),
                        "stage_ordinal": stage_ordinal,
                        "candidate_instance_id": instance_id,
                        "candidate_ordinal": candidate_ordinal,
                        "roster_id": roster_id,
                        "source_occurrence_ids": [],
                        "input_candidate_instance_ids": [source_instance],
                        "admission_preset_id": "identity-transform-v1",
                        "disposition": "RETAINED",
                        "reason": "TRANSFORM_RETAINED",
                    }
                )
                effective_instance[candidate_ordinal] = instance_id
        return admissions, effective_instance

    def _capture_effective(self, payload: Mapping[str, object]) -> None:
        required = {
            "batch",
            "tail_line",
            "selector_trace",
            "raw_selected_indices",
            "final_selected_indices",
            "post_selector_peak_slice",
            "post_selector_thesis_count",
            "uses_realized_outcomes",
            "post_lock_data_read",
        }
        if set(payload) != required:
            _fail("effective selection event fields differ")
        if (
            payload["uses_realized_outcomes"] is not False
            or payload["post_lock_data_read"] is not False
        ):
            _fail("effective selection event is outcome-open")
        if not self._native:
            _fail("effective selection arrived before native candidates")
        if self._header.get("frozen_at_utc") is None:
            frozen_at = self._frozen_at_utc_factory()
            if not isinstance(frozen_at, str):
                _fail("freeze-time factory did not return UTC text")
            self._header["frozen_at_utc"] = frozen_at
        batch = payload["batch"]
        effective_rosters = _lineup_rosters(batch)
        trace = _clone(payload["selector_trace"])
        assert_outcome_free(trace)
        if trace.get("schema_version") != "binary-tail-selector-trace/v1":
            _fail("selector trace schema differs")
        decisions = trace.get("decisions")
        if not isinstance(decisions, list) or len(decisions) != len(effective_rosters):
            _fail("selector trace does not cover every effective candidate")
        raw = [int(index) for index in payload["raw_selected_indices"]]
        final = [int(index) for index in payload["final_selected_indices"]]
        candidate_count = len(effective_rosters)
        if (
            len(set(raw)) != len(raw)
            or len(set(final)) != len(final)
            or any(index < 0 or index >= candidate_count for index in raw)
            or any(index < 0 or index >= candidate_count for index in final)
        ):
            _fail("selector output contains repeated or out-of-range indices")
        if trace.get("selected_indices") != raw:
            _fail("selector trace and raw selection differ")
        if int(self._header["entry_budget"]) != len(raw) or len(final) != len(raw):
            _fail("selector output differs from the registered entry budget")
        try:
            tail_line = float(payload["tail_line"])
        except (TypeError, ValueError) as exc:
            raise PrelockLineageRuntimeError(
                "selector tail line is not numeric"
            ) from exc
        scaled_tail = tail_line * 1000.0
        if not np.isfinite(tail_line) or tail_line <= 0.0:
            _fail("selector tail line is not finite and positive")
        from ..optimizer.lineup import select_tail_entries

        replayed_traces: list[Mapping[str, object]] = []
        replayed = select_tail_entries(
            np.asarray(batch.candidate_totals),
            len(raw),
            tail_line,
            trace_capture=replayed_traces.append,
        )
        if replayed != raw or len(replayed_traces) != 1 or replayed_traces[0] != trace:
            _fail("selector trace does not exactly replay the frozen matrix")

        generation = self._generation_records()
        admissions, effective_instance = self._admission_records(
            generation, effective_rosters
        )
        if set(effective_instance) != set(range(len(effective_rosters))):
            _fail("effective candidate instance map is incomplete")
        strategy_ids = list(self._header["selector_ids"])
        if len(strategy_ids) != 1:
            _fail("phase-1 runtime capture supports one selector")
        strategy_id = str(strategy_ids[0])
        tail_micro = round(scaled_tail)
        objective_id = f"binary-tail-{tail_micro}-milli-v1"
        strategy: list[dict[str, object]] = []
        for candidate_ordinal, row in enumerate(decisions):
            if int(row["candidate_index"]) != candidate_ordinal:
                _fail("selector decision order differs")
            selected = row["selector_rank"] is not None
            phase = str(row["selection_phase"])
            if selected:
                decision_reason = (
                    "SELECTED_COVERAGE_PHASE"
                    if phase == "COVERAGE"
                    else "SELECTED_SATURATION_FILL"
                )
                marginal_context = "AT_SELECTION"
            else:
                decision_reason = "NOT_SELECTED_BOOK_FULL"
                marginal_context = "AT_TERMINAL_BOOK"
            roster_id = _roster_id(
                str(self._header["slate_id"]),
                effective_rosters[candidate_ordinal],
            )
            strategy.append(
                {
                    "decision_id": f"strategy-{candidate_ordinal:06d}",
                    "strategy_id": strategy_id,
                    "candidate_instance_id": effective_instance[candidate_ordinal],
                    "roster_id": roster_id,
                    "candidate_ordinal": candidate_ordinal,
                    "eligibility": "ELIGIBLE",
                    "eligibility_reason": "EFFECTIVE_CANDIDATE",
                    "decision": "SELECTED" if selected else "NOT_SELECTED",
                    "decision_reason": decision_reason,
                    "objective_id": objective_id,
                    "objective_unit": "WORLD_COUNT",
                    "individual_utility": int(row["individual_clear_count"]),
                    "marginal_utility": int(row["fresh_world_count"]),
                    "marginal_context": marginal_context,
                    "selector_rank": row["selector_rank"],
                    "selection_phase": phase,
                    "fresh_world_count": int(row["fresh_world_count"]),
                    "individual_clear_count": int(row["individual_clear_count"]),
                    "p_line": float(row["p_line"]),
                    "mean_simulated_total": float(row["mean_simulated_total"]),
                    "tiebreak_values": list(row["tiebreak_values"]),
                }
            )

        raw_rank = {index: rank for rank, index in enumerate(raw)}
        final_rank = {index: rank for rank, index in enumerate(final)}
        peak = int(payload["post_selector_peak_slice"])
        theses = int(payload["post_selector_thesis_count"])
        if peak and theses:
            _fail("phase-1 capture cannot attribute two replacement laws")
        books: list[dict[str, object]] = []
        for index in sorted(set(raw) | set(final)):
            in_raw = index in raw_rank
            in_final = index in final_rank
            if in_raw and in_final:
                disposition = "RETAINED"
                reason = (
                    "RETAINED_POSTSELECTOR"
                    if raw_rank[index] == final_rank[index]
                    else "EXPORT_REORDER_ONLY"
                )
            elif in_raw:
                disposition = "REMOVED"
                reason = "REPLACED_FOR_THESIS" if theses else "REPLACED_BY_PEAK_SLICE"
            else:
                disposition = "ADDED"
                reason = "ADDED_FOR_THESIS" if theses else "ADDED_BY_PEAK_SLICE"
            books.append(
                {
                    "transition_id": f"book-{index:06d}",
                    "strategy_id": strategy_id,
                    "candidate_instance_id": effective_instance[index],
                    "roster_id": _roster_id(
                        str(self._header["slate_id"]),
                        effective_rosters[index],
                    ),
                    "selector_rank": raw_rank.get(index),
                    "postselector_rank": final_rank.get(index),
                    "export_rank": final_rank.get(index),
                    "disposition": disposition,
                    "reason": reason,
                }
            )

        try:
            sidecar = build_prelock_candidate_lineage_v1(
                run_header=self._header,
                roster_identities=list(generation["roster_raw_by_id"].values()),
                proposal_requests=generation["proposal_requests"],
                solve_attempts=generation["solve_attempts"],
                generated_occurrences=generation["generated_occurrences"],
                dedupe_decisions=generation["dedupe_decisions"],
                admission_decisions=admissions,
                strategy_decisions=strategy,
                book_transitions=books,
            )
        except PrelockCandidateLineageError as exc:
            raise PrelockLineageRuntimeError(
                "runtime events violate the immutable lineage contract"
            ) from exc
        effective_matrix = _array_identity(
            batch.candidate_totals, label="effective candidate totals"
        )
        effective_worlds = _array_identity(
            batch.row_draws, label="effective player worlds"
        )
        body: dict[str, Any] = {
            "schema_version": RUNTIME_ENVELOPE_SCHEMA,
            "sidecar": sidecar,
            "selector_objective": {
                "strategy_id": strategy_id,
                "objective_id": objective_id,
                "tail_line": tail_line,
            },
            "matrix_identities": {
                "native_sources": [
                    {
                        "source_label": source,
                        "candidate_order_sha256": native["candidate_order_sha256"],
                        "candidate_totals": native["candidate_totals_identity"],
                        "player_worlds": native["player_worlds_identity"],
                        "generator_config": native["generator_config"],
                        "generator_config_sha256": native["generator_config_sha256"],
                    }
                    for source, native in self._native.items()
                ],
                "effective_candidate_order_sha256": canonical_sha256(effective_rosters),
                "effective_candidate_totals": effective_matrix,
                "effective_player_worlds": effective_worlds,
                "raw_selected_indices_sha256": canonical_sha256(raw),
                "final_selected_indices_sha256": canonical_sha256(final),
            },
            "capture_completed_before_legacy_diagnostics": True,
            "detailed_rows_projected_to_graph": False,
            "uses_realized_outcomes": False,
            "post_lock_data_read": False,
        }
        body["envelope_sha256"] = canonical_sha256(body)
        self._artifact = validate_runtime_envelope_v1(body)
        if self._matrix_artifact_capture is not None:
            matrix_bytes = np.ascontiguousarray(
                np.asarray(batch.candidate_totals)
            ).tobytes(order="C")
            if (
                len(matrix_bytes)
                != int(np.prod(effective_matrix["shape"]))
                * np.dtype(str(effective_matrix["dtype"])).itemsize
                or sha256(matrix_bytes).hexdigest() != effective_matrix["sha256"]
            ):
                _fail("selector matrix byte serialization differs")
            self._matrix_artifact_capture(
                matrix_bytes,
                {
                    "schema_version": "prelock-selector-matrix-raw/v1",
                    "dtype": effective_matrix["dtype"],
                    "shape": effective_matrix["shape"],
                    "sha256": effective_matrix["sha256"],
                    "bytes": len(matrix_bytes),
                    "uses_realized_outcomes": False,
                    "post_lock_data_read": False,
                },
            )
        if self._artifact_capture is not None:
            self._artifact_capture(_clone(self._artifact))


def validate_runtime_envelope_v1(value: object) -> dict[str, Any]:
    item = _clone(value)
    assert_outcome_free(item)
    fields = {
        "schema_version",
        "sidecar",
        "selector_objective",
        "matrix_identities",
        "capture_completed_before_legacy_diagnostics",
        "detailed_rows_projected_to_graph",
        "uses_realized_outcomes",
        "post_lock_data_read",
        "envelope_sha256",
    }
    if set(item) != fields or item["schema_version"] != RUNTIME_ENVELOPE_SCHEMA:
        _fail("runtime lineage envelope fields differ")
    retained = item.pop("envelope_sha256")
    if not isinstance(retained, str) or _SHA256.fullmatch(retained) is None:
        _fail("runtime lineage envelope hash differs")
    if canonical_sha256(item) != retained:
        _fail("runtime lineage envelope self-hash differs")
    item["envelope_sha256"] = retained
    try:
        item["sidecar"] = validate_prelock_candidate_lineage_v1(item["sidecar"])
    except PrelockCandidateLineageError as exc:
        raise PrelockLineageRuntimeError(
            "runtime envelope sidecar fails exact reopen"
        ) from exc
    if (
        item["capture_completed_before_legacy_diagnostics"] is not True
        or item["detailed_rows_projected_to_graph"] is not False
        or item["uses_realized_outcomes"] is not False
        or item["post_lock_data_read"] is not False
    ):
        _fail("runtime lineage authority boundary differs")
    selector_objective = item["selector_objective"]
    if not isinstance(selector_objective, Mapping) or set(selector_objective) != {
        "strategy_id",
        "objective_id",
        "tail_line",
    }:
        _fail("runtime selector objective fields differ")
    tail_line = selector_objective["tail_line"]
    if (
        isinstance(tail_line, bool)
        or not isinstance(tail_line, (int, float))
        or not np.isfinite(float(tail_line))
        or float(tail_line) <= 0.0
    ):
        _fail("runtime selector objective tail line differs")
    strategy_rows = item["sidecar"]["strategy_decisions"]
    if {str(row["strategy_id"]) for row in strategy_rows} != {
        str(selector_objective["strategy_id"])
    } or {str(row["objective_id"]) for row in strategy_rows} != {
        str(selector_objective["objective_id"])
    }:
        _fail("runtime selector objective differs from strategy decisions")
    matrices = item["matrix_identities"]
    matrix_fields = {
        "native_sources",
        "effective_candidate_order_sha256",
        "effective_candidate_totals",
        "effective_player_worlds",
        "raw_selected_indices_sha256",
        "final_selected_indices_sha256",
    }
    if not isinstance(matrices, Mapping) or set(matrices) != matrix_fields:
        _fail("runtime matrix identity fields differ")
    native_sources = matrices["native_sources"]
    if not isinstance(native_sources, list) or not native_sources:
        _fail("runtime native-source matrix identities are empty")
    source_labels: set[str] = set()
    for ordinal, source in enumerate(native_sources):
        if not isinstance(source, Mapping) or set(source) != {
            "source_label",
            "candidate_order_sha256",
            "candidate_totals",
            "player_worlds",
            "generator_config",
            "generator_config_sha256",
        }:
            _fail(f"runtime native source[{ordinal}] fields differ")
        source_label = str(source["source_label"])
        if not source_label or source_label in source_labels:
            _fail("runtime native source labels are blank or repeated")
        source_labels.add(source_label)
        for hash_field in (
            "candidate_order_sha256",
            "generator_config_sha256",
        ):
            digest = source[hash_field]
            if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
                _fail(f"runtime native source {hash_field} differs")
        assert_outcome_free(source["generator_config"])
        if (
            canonical_sha256(source["generator_config"])
            != source["generator_config_sha256"]
        ):
            _fail("runtime native generator configuration hash differs")
        _validate_array_identity(
            source["candidate_totals"],
            label=f"runtime native source[{ordinal}] candidate totals",
        )
        _validate_array_identity(
            source["player_worlds"],
            label=f"runtime native source[{ordinal}] player worlds",
        )
    proposal_sources = {
        str(row["source_label"]) for row in item["sidecar"]["proposal_requests"]
    }
    if source_labels != proposal_sources:
        _fail("runtime native sources do not cover proposal sources")
    effective_totals = _validate_array_identity(
        matrices["effective_candidate_totals"],
        label="runtime effective candidate totals",
    )
    effective_worlds = _validate_array_identity(
        matrices["effective_player_worlds"],
        label="runtime effective player worlds",
    )
    if (
        effective_totals["shape"][0]
        != item["sidecar"]["counts"]["effective_candidate_count"]
        or effective_totals["shape"][1] != effective_worlds["shape"][1]
    ):
        _fail("runtime effective matrix census differs from lineage")
    for hash_field in (
        "effective_candidate_order_sha256",
        "raw_selected_indices_sha256",
        "final_selected_indices_sha256",
    ):
        digest = matrices[hash_field]
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            _fail(f"runtime matrix {hash_field} differs")
    return item


def build_prepared_entry_sidecar_v1(
    candidate_envelope: Mapping[str, object],
    event: Mapping[str, object],
) -> dict[str, Any]:
    candidate = validate_runtime_envelope_v1(candidate_envelope)
    retained = _clone(event)
    assert_outcome_free(retained)
    fields = {
        "schema_version",
        "contest_id",
        "draft_group_id",
        "salary_catalog_sha256",
        "csv_sha256",
        "csv_bytes",
        "paid_export_receipt_sha256",
        "entries",
        "uses_realized_outcomes",
        "post_lock_data_read",
    }
    if set(retained) != fields or retained["schema_version"] != "paid-entry-capture/v1":
        _fail("prepared-entry capture fields differ")
    if (
        not isinstance(retained["contest_id"], str)
        or not retained["contest_id"].strip()
        or retained["contest_id"].strip() != retained["contest_id"]
        or not isinstance(retained["draft_group_id"], int)
        or isinstance(retained["draft_group_id"], bool)
        or retained["draft_group_id"] < 1
    ):
        _fail("prepared-entry contest or draft-group identity differs")
    for hash_field in (
        "salary_catalog_sha256",
        "csv_sha256",
        "paid_export_receipt_sha256",
    ):
        digest = retained[hash_field]
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            _fail(f"prepared-entry {hash_field} differs")
    if (
        not isinstance(retained["csv_bytes"], int)
        or isinstance(retained["csv_bytes"], bool)
        or retained["csv_bytes"] < 1
    ):
        _fail("prepared-entry CSV byte count differs")
    if (
        retained["uses_realized_outcomes"] is not False
        or retained["post_lock_data_read"] is not False
    ):
        _fail("prepared-entry event is outcome-open")
    header = candidate["sidecar"]["run_header"]
    if retained["draft_group_id"] != header["draft_group_id"]:
        _fail("prepared-entry draft group differs")
    catalog_hashes = {
        row["salary_catalog_sha256"]
        for row in candidate["sidecar"]["roster_identities"]
    }
    if (
        len(catalog_hashes) != 1
        or retained["salary_catalog_sha256"] not in catalog_hashes
    ):
        _fail("prepared-entry salary catalog differs")
    roster_by_internal = {
        tuple(row["internal_player_ids"]): row
        for row in candidate["sidecar"]["roster_identities"]
    }
    final_by_roster = {
        row["roster_id"]: row
        for row in candidate["sidecar"]["book_transitions"]
        if row["export_rank"] is not None
    }
    entries = retained["entries"]
    if not isinstance(entries, list) or len(entries) != header["entry_budget"]:
        _fail("prepared-entry count differs from the candidate book")
    prepared = []
    input_ordinals: set[int] = set()
    for row_ordinal, row in enumerate(entries):
        if not isinstance(row, Mapping) or set(row) != {
            "export_ordinal",
            "entry_id",
            "internal_player_ids",
            "dk_draftable_ids",
            "paid_input_book_ordinal",
            "slot_dk_draftable_ids",
        }:
            _fail("prepared-entry row fields differ")
        if int(row["export_ordinal"]) != row_ordinal:
            _fail("prepared-entry row order differs")
        entry_id = str(row["entry_id"])
        if not entry_id.strip() or entry_id.strip() != entry_id:
            _fail("prepared-entry EntryID differs")
        internal = tuple(
            _ids(row["internal_player_ids"], label="prepared internal roster")
        )
        roster = roster_by_internal.get(internal)
        if roster is None:
            _fail("prepared entry is outside the frozen candidate identities")
        transition = final_by_roster.get(roster["roster_id"])
        if transition is None:
            _fail("prepared entry is outside the frozen final book")
        draftable = _ids(row["dk_draftable_ids"], label="prepared draftable roster")
        slot_draftable = [str(value).strip() for value in row["slot_dk_draftable_ids"]]
        if (
            len(slot_draftable) != 9
            or any(not value for value in slot_draftable)
            or len(set(slot_draftable)) != 9
            or sorted(slot_draftable) != draftable
            or draftable != roster["draftable_player_ids"]
        ):
            _fail("prepared-entry draftable roster bridge differs")
        paid_input = int(row["paid_input_book_ordinal"])
        input_ordinals.add(paid_input)
        prepared.append(
            {
                "entry_row_ordinal": row_ordinal,
                "entry_id": entry_id,
                "contest_id": str(retained["contest_id"]),
                "candidate_instance_id": transition["candidate_instance_id"],
                "roster_id": transition["roster_id"],
                "raw_selector_rank": transition["selector_rank"],
                "postselector_rank": transition["postselector_rank"],
                "application_book_rank": paid_input,
                "slot_dk_draftable_ids": slot_draftable,
                "status": "PREPARED_NOT_CONFIRMED",
            }
        )
    if input_ordinals != set(range(len(entries))):
        _fail("paid input book ranks are not exact and contiguous")
    body: dict[str, Any] = {
        "schema_version": PREPARED_SIDECAR_SCHEMA,
        "candidate_envelope_sha256": candidate["envelope_sha256"],
        "candidate_sidecar_sha256": candidate["sidecar"]["sidecar_sha256"],
        "run_id": header["run_id"],
        "slate_id": header["slate_id"],
        "draft_group_id": header["draft_group_id"],
        "contest_id": str(retained["contest_id"]),
        "salary_catalog_sha256": retained["salary_catalog_sha256"],
        "filled_csv": {
            "sha256": retained["csv_sha256"],
            "bytes": retained["csv_bytes"],
        },
        "paid_export_receipt_sha256": retained["paid_export_receipt_sha256"],
        "prepared_entries": prepared,
        "submission_confirmed": False,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    body["sidecar_sha256"] = canonical_sha256(body)
    return validate_prepared_entry_sidecar_v1(body)


def validate_prepared_entry_sidecar_v1(value: object) -> dict[str, Any]:
    item = _clone(value)
    assert_outcome_free(item)
    retained = item.pop("sidecar_sha256", None)
    if not isinstance(retained, str) or _SHA256.fullmatch(retained) is None:
        _fail("prepared-entry sidecar hash differs")
    if canonical_sha256(item) != retained:
        _fail("prepared-entry sidecar self-hash differs")
    item["sidecar_sha256"] = retained
    fields = {
        "schema_version",
        "candidate_envelope_sha256",
        "candidate_sidecar_sha256",
        "run_id",
        "slate_id",
        "draft_group_id",
        "contest_id",
        "salary_catalog_sha256",
        "filled_csv",
        "paid_export_receipt_sha256",
        "prepared_entries",
        "submission_confirmed",
        "uses_realized_outcomes",
        "post_lock_data_read",
        "sidecar_sha256",
    }
    if set(item) != fields or (
        item.get("schema_version") != PREPARED_SIDECAR_SCHEMA
        or item.get("submission_confirmed") is not False
        or item.get("uses_realized_outcomes") is not False
        or item.get("post_lock_data_read") is not False
    ):
        _fail("prepared-entry sidecar boundary differs")
    for hash_field in (
        "candidate_envelope_sha256",
        "candidate_sidecar_sha256",
        "salary_catalog_sha256",
        "paid_export_receipt_sha256",
    ):
        digest = item.get(hash_field)
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            _fail(f"prepared-entry sidecar {hash_field} differs")
    filled_csv = item.get("filled_csv")
    if not isinstance(filled_csv, Mapping) or set(filled_csv) != {"sha256", "bytes"}:
        _fail("prepared-entry filled CSV identity fields differ")
    if (
        not isinstance(filled_csv["sha256"], str)
        or _SHA256.fullmatch(filled_csv["sha256"]) is None
        or not isinstance(filled_csv["bytes"], int)
        or isinstance(filled_csv["bytes"], bool)
        or filled_csv["bytes"] < 1
    ):
        _fail("prepared-entry filled CSV identity differs")
    entries = item.get("prepared_entries")
    if not isinstance(entries, list) or not entries:
        _fail("prepared-entry sidecar is empty")
    if [row["entry_row_ordinal"] for row in entries] != list(range(len(entries))):
        _fail("prepared-entry sidecar row order differs")
    if len({row["entry_id"] for row in entries}) != len(entries):
        _fail("prepared-entry EntryIDs repeat")
    expected_entry_fields = {
        "entry_row_ordinal",
        "entry_id",
        "contest_id",
        "candidate_instance_id",
        "roster_id",
        "raw_selector_rank",
        "postselector_rank",
        "application_book_rank",
        "slot_dk_draftable_ids",
        "status",
    }
    for row in entries:
        if not isinstance(row, Mapping) or set(row) != expected_entry_fields:
            _fail("prepared-entry sidecar row fields differ")
        if (
            row["status"] != "PREPARED_NOT_CONFIRMED"
            or row["contest_id"] != item["contest_id"]
            or not isinstance(row["entry_id"], str)
            or not row["entry_id"]
        ):
            _fail("prepared-entry sidecar row identity differs")
        _ids(
            row["slot_dk_draftable_ids"],
            label="prepared-entry slot roster",
        )
    if sorted(row["application_book_rank"] for row in entries) != list(
        range(len(entries))
    ):
        _fail("prepared-entry application book ranks differ")
    return item


def _object_identity(value: object, *, label: str) -> dict[str, Any]:
    item = _clone(value)
    fields = {"uri", "generation", "sha256", "bytes", "time_created"}
    if set(item) != fields:
        _fail(f"{label} object identity fields differ")
    generation = str(item["generation"])
    if not generation.isdigit() or int(generation) < 1:
        _fail(f"{label} generation differs")
    if not isinstance(item["sha256"], str) or _SHA256.fullmatch(item["sha256"]) is None:
        _fail(f"{label} SHA-256 differs")
    if (
        not isinstance(item["bytes"], int)
        or isinstance(item["bytes"], bool)
        or item["bytes"] < 1
    ):
        _fail(f"{label} byte count differs")
    try:
        created = datetime.fromisoformat(str(item["time_created"]))
    except ValueError as exc:
        raise PrelockLineageRuntimeError(f"{label} creation time differs") from exc
    if created.tzinfo is None or created.utcoffset() is None:
        _fail(f"{label} creation time differs")
    return {
        **item,
        "generation": generation,
        "time_created": created.astimezone(UTC).isoformat(),
    }


def build_terminal_root_v1(
    *,
    candidate_envelope: Mapping[str, object],
    candidate_object_identity: Mapping[str, object],
    selector_matrix_object_identity: Mapping[str, object],
    prepared_entry_sidecar: Mapping[str, object] | None = None,
    prepared_entry_object_identity: Mapping[str, object] | None = None,
    csv_object_identity: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    candidate = validate_runtime_envelope_v1(candidate_envelope)
    candidate_object = _object_identity(
        candidate_object_identity, label="candidate sidecar"
    )
    candidate_bytes = canonical_json_bytes(candidate)
    if candidate_object["sha256"] != sha256(
        candidate_bytes
    ).hexdigest() or candidate_object["bytes"] != len(candidate_bytes):
        _fail("candidate object does not bind exact envelope bytes")
    selector_matrix_object = _object_identity(
        selector_matrix_object_identity, label="selector matrix"
    )
    matrix_identity = candidate["matrix_identities"]["effective_candidate_totals"]
    matrix_bytes = (
        int(np.prod(matrix_identity["shape"]))
        * np.dtype(str(matrix_identity["dtype"])).itemsize
    )
    if (
        selector_matrix_object["sha256"] != matrix_identity["sha256"]
        or selector_matrix_object["bytes"] != matrix_bytes
    ):
        _fail("selector matrix object differs from the frozen matrix identity")
    header = candidate["sidecar"]["run_header"]
    lock = datetime.fromisoformat(header["slate_lock_at_utc"])
    for label, identity in (
        ("candidate sidecar", candidate_object),
        ("selector matrix", selector_matrix_object),
    ):
        created = datetime.fromisoformat(identity["time_created"])
        if created >= lock:
            _fail(f"{label} was not provider-created before lock")
    objects: dict[str, Any] = {
        "candidate_sidecar": candidate_object,
        "selector_matrix": selector_matrix_object,
    }
    scope = "SHADOW_CANDIDATE_ONLY"
    if any(
        value is not None
        for value in (
            prepared_entry_sidecar,
            prepared_entry_object_identity,
            csv_object_identity,
        )
    ):
        if any(
            value is None
            for value in (
                prepared_entry_sidecar,
                prepared_entry_object_identity,
                csv_object_identity,
            )
        ):
            _fail("paid terminal requires prepared sidecar and filled CSV")
        prepared = validate_prepared_entry_sidecar_v1(prepared_entry_sidecar)
        if prepared["candidate_envelope_sha256"] != candidate["envelope_sha256"]:
            _fail("prepared sidecar binds another candidate envelope")
        prepared_object = _object_identity(
            prepared_entry_object_identity, label="prepared-entry sidecar"
        )
        csv_object = _object_identity(csv_object_identity, label="filled CSV")
        if prepared_object["sha256"] != sha256(
            canonical_json_bytes(prepared)
        ).hexdigest() or prepared_object["bytes"] != len(
            canonical_json_bytes(prepared)
        ):
            _fail("prepared object does not bind exact sidecar bytes")
        if (
            csv_object["sha256"] != prepared["filled_csv"]["sha256"]
            or csv_object["bytes"] != prepared["filled_csv"]["bytes"]
        ):
            _fail("filled CSV object differs from prepared-entry sidecar")
        for label, identity in (
            ("prepared-entry sidecar", prepared_object),
            ("filled CSV", csv_object),
        ):
            object_created = datetime.fromisoformat(identity["time_created"])
            if object_created >= lock:
                _fail(f"{label} was not provider-created before lock")
        objects.update(
            {
                "prepared_entry_sidecar": prepared_object,
                "filled_csv": csv_object,
            }
        )
        scope = "PAID_PREPARED_NOT_CONFIRMED"
    body: dict[str, Any] = {
        "schema_version": TERMINAL_ROOT_SCHEMA,
        "scope": scope,
        "run_id": header["run_id"],
        "slate_id": header["slate_id"],
        "slate_lock_at_utc": header["slate_lock_at_utc"],
        "objects": objects,
        "all_objects_provider_created_before_lock": True,
        "create_once_required": True,
        "detailed_rows_projected_to_graph": False,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    body["terminal_sha256"] = canonical_sha256(body)
    return validate_terminal_root_v1(
        body,
        candidate_envelope=candidate,
        prepared_entry_sidecar=prepared_entry_sidecar,
    )


def validate_terminal_root_v1(
    value: object,
    *,
    candidate_envelope: Mapping[str, object],
    prepared_entry_sidecar: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    item = _clone(value)
    assert_outcome_free(item)
    fields = {
        "schema_version",
        "scope",
        "run_id",
        "slate_id",
        "slate_lock_at_utc",
        "objects",
        "all_objects_provider_created_before_lock",
        "create_once_required",
        "detailed_rows_projected_to_graph",
        "uses_realized_outcomes",
        "post_lock_data_read",
        "terminal_sha256",
    }
    if set(item) != fields or item.get("schema_version") != TERMINAL_ROOT_SCHEMA:
        _fail("pre-lock terminal root fields differ")
    terminal_hash = item.get("terminal_sha256")
    if not isinstance(terminal_hash, str) or _SHA256.fullmatch(terminal_hash) is None:
        _fail("pre-lock terminal root hash differs")
    unhashed = {key: nested for key, nested in item.items() if key != "terminal_sha256"}
    if canonical_sha256(unhashed) != terminal_hash:
        _fail("pre-lock terminal root self-hash differs")
    if (
        item["all_objects_provider_created_before_lock"] is not True
        or item["create_once_required"] is not True
        or item["detailed_rows_projected_to_graph"] is not False
        or item["uses_realized_outcomes"] is not False
        or item["post_lock_data_read"] is not False
    ):
        _fail("pre-lock terminal authority boundary differs")

    candidate = validate_runtime_envelope_v1(candidate_envelope)
    header = candidate["sidecar"]["run_header"]
    if (
        item["run_id"] != header["run_id"]
        or item["slate_id"] != header["slate_id"]
        or item["slate_lock_at_utc"] != header["slate_lock_at_utc"]
    ):
        _fail("pre-lock terminal run identity differs")
    scope = item["scope"]
    expected_object_keys = {"candidate_sidecar", "selector_matrix"}
    if scope == "PAID_PREPARED_NOT_CONFIRMED":
        expected_object_keys |= {"prepared_entry_sidecar", "filled_csv"}
    elif scope != "SHADOW_CANDIDATE_ONLY":
        _fail("pre-lock terminal scope differs")
    objects = item["objects"]
    if not isinstance(objects, Mapping) or set(objects) != expected_object_keys:
        _fail("pre-lock terminal object census differs")
    normalized_objects = {
        role: _object_identity(identity, label=role.replace("_", " "))
        for role, identity in objects.items()
    }
    if normalized_objects != objects:
        _fail("pre-lock terminal object identities are not canonical")
    lock = datetime.fromisoformat(str(header["slate_lock_at_utc"]))
    if any(
        datetime.fromisoformat(identity["time_created"]) >= lock
        for identity in normalized_objects.values()
    ):
        _fail("pre-lock terminal contains an object created at or after lock")

    candidate_bytes = canonical_json_bytes(candidate)
    candidate_object = normalized_objects["candidate_sidecar"]
    if candidate_object["sha256"] != sha256(
        candidate_bytes
    ).hexdigest() or candidate_object["bytes"] != len(candidate_bytes):
        _fail("pre-lock terminal candidate object binding differs")
    matrix_identity = candidate["matrix_identities"]["effective_candidate_totals"]
    selector_matrix = normalized_objects["selector_matrix"]
    expected_matrix_bytes = (
        int(np.prod(matrix_identity["shape"]))
        * np.dtype(str(matrix_identity["dtype"])).itemsize
    )
    if (
        selector_matrix["sha256"] != matrix_identity["sha256"]
        or selector_matrix["bytes"] != expected_matrix_bytes
    ):
        _fail("pre-lock terminal selector matrix binding differs")

    if scope == "PAID_PREPARED_NOT_CONFIRMED":
        if prepared_entry_sidecar is None:
            _fail("paid terminal exact reopen requires its prepared sidecar")
        prepared = validate_prepared_entry_sidecar_v1(prepared_entry_sidecar)
        if prepared["candidate_envelope_sha256"] != candidate["envelope_sha256"]:
            _fail("paid terminal prepared sidecar binds another candidate")
        prepared_bytes = canonical_json_bytes(prepared)
        prepared_object = normalized_objects["prepared_entry_sidecar"]
        if prepared_object["sha256"] != sha256(
            prepared_bytes
        ).hexdigest() or prepared_object["bytes"] != len(prepared_bytes):
            _fail("paid terminal prepared object binding differs")
        filled_csv = normalized_objects["filled_csv"]
        if (
            filled_csv["sha256"] != prepared["filled_csv"]["sha256"]
            or filled_csv["bytes"] != prepared["filled_csv"]["bytes"]
        ):
            _fail("paid terminal filled CSV binding differs")
    elif prepared_entry_sidecar is not None:
        _fail("candidate-only terminal cannot accept a prepared sidecar")
    return item


def publish_create_once_json(
    path: str | os.PathLike[str], value: Mapping[str, object]
) -> dict[str, object]:
    """Write canonical local test evidence once; exact retries are idempotent."""

    destination = Path(path)
    if not destination.is_absolute():
        _fail("create-once path must be absolute")
    payload = canonical_json_bytes(value)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        created = True
    except FileExistsError:
        if destination.is_symlink() or not destination.is_file():
            _fail("create-once destination is not a regular file")
        if destination.read_bytes() != payload:
            _fail("create-once destination already differs")
        created = False
    return {
        "path": str(destination),
        "created": created,
        "bytes": len(payload),
        "sha256": sha256(payload).hexdigest(),
    }


__all__ = [
    "PREPARED_SIDECAR_SCHEMA",
    "RUNTIME_ENVELOPE_SCHEMA",
    "PrelockLineageRuntimeError",
    "RuntimePrelockLineageRecorder",
    "build_prepared_entry_sidecar_v1",
    "build_terminal_root_v1",
    "publish_create_once_json",
    "validate_prepared_entry_sidecar_v1",
    "validate_runtime_envelope_v1",
    "validate_terminal_root_v1",
]
