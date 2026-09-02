"""Outcome-free summary projection of validated pre-lock lineage into graph v2.

This module is deliberately an offline, pure adapter.  It emits only aggregate
logical rows accepted by ``corpus-graph-vnext/v2``; it has no Neo4j driver,
filesystem, application, scoring, generation, selection, or cloud behavior.
The detailed sidecar remains the drill-down authority and is represented here
only by its exact content identity.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Final

from nfl_dfs.inference import prelock_candidate_lineage_v1 as lineage
from nfl_dfs.research import corpus_graph_vnext_contracts as graph

PROJECTION_SCHEMA: Final = "prelock-lineage-graph-summary/v1"
RECEIPT_SCHEMA: Final = "prelock-lineage-graph-summary-receipt/v1"
MAPPING_TRANSFORM_SCHEMA: Final = (
    "prelock-lineage-graph-summary-mapping-transform/v1"
)
SIDECAR_PROVIDER_RECEIPT_SCHEMA: Final = (
    "prelock-lineage-sidecar-provider-receipt/v1"
)
INACTIVE_OFFLINE_MODE: Final = "inactive-offline"
CREATE_ONCE_PUBLICATION_MODE: Final = "create-once-exact-reopen"

_IDENTIFIER: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_UTC_TIMESTAMP: Final = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)

AUTHORITY_FLAGS: Final[Mapping[str, bool]] = MappingProxyType(
    {
        "database_load_authority": False,
        "decision_authority": False,
        "graph_mutation_authority": False,
        "historical_outcome_read_authority": False,
        "lineup_population_authority": False,
        "live_money_policy_authority": False,
        "production_default_change_authority": False,
        "promotion_authority": False,
        "scoring_authority": False,
    }
)

_MAPPING_TRANSFORM_BODY: Final[dict[str, object]] = {
    "schema_version": MAPPING_TRANSFORM_SCHEMA,
    "transform_id": "prelock-lineage-summary-to-corpus-graph-vnext-v2",
    "source_schema_version": lineage.SIDECAR_SCHEMA,
    "projection_schema_version": PROJECTION_SCHEMA,
    "target_graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
    "projection_scope": "aggregate-only",
    "selector_retrieval_binding_contract": "explicit-total-map/v1",
    "emitted_node_kinds": [
        "CandidateSnapshot",
        "MetricSet",
        "ScienceRelease",
        "SelectedBook",
        "Slate",
        "SourceArtifact",
    ],
    "emitted_relationship_types": [
        "DERIVED_FROM",
        "FOR_SLATE",
        "HAS_METRIC",
        "USES_SOURCE",
    ],
    "individual_rows_emitted": False,
    "outcome_rows_emitted": False,
}
MAPPING_TRANSFORM_IDENTITY: Final[Mapping[str, str]] = MappingProxyType(
    {
        "schema_version": MAPPING_TRANSFORM_SCHEMA,
        "transform_id": str(_MAPPING_TRANSFORM_BODY["transform_id"]),
        "sha256": graph.canonical_sha256(_MAPPING_TRANSFORM_BODY),
    }
)

_REQUEST_STATUSES: Final = tuple(sorted(lineage.REQUEST_STATUSES))
_SOLVE_STATUSES: Final = ("INFEASIBLE", "PRODUCED", "SOLVER_ERROR")
_DEDUPE_DISPOSITIONS: Final = tuple(sorted(lineage.DEDUPE_DISPOSITIONS))
_ADMISSION_REASONS: Final = tuple(sorted(lineage.ADMISSION_REASONS))
_STRATEGY_REASONS: Final = tuple(sorted(lineage.STRATEGY_DECISION_REASONS))
_BOOK_DISPOSITIONS: Final = ("ADDED", "REMOVED", "RETAINED")


class PrelockLineageGraphV2Error(ValueError):
    """A sidecar could not be represented by the bounded v2 summary."""


@dataclass(frozen=True, slots=True)
class PrelockLineageGraphV2Projection:
    """Validated aggregate logical rows and their deterministic receipt."""

    mapping_transform_identity: dict[str, object]
    selector_retrieval_preset_bindings: dict[str, str]
    governed_manifest: dict[str, object]
    nodes: tuple[dict[str, object], ...]
    relationships: tuple[dict[str, object], ...]
    load_plan: dict[str, object]
    receipt: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        """Return the closed canonical publication envelope."""

        return {
            "schema_version": PROJECTION_SCHEMA,
            "mapping_transform_identity": self.mapping_transform_identity,
            "selector_retrieval_preset_bindings": (
                self.selector_retrieval_preset_bindings
            ),
            "governed_manifest": self.governed_manifest,
            "nodes": list(self.nodes),
            "relationships": list(self.relationships),
            "load_plan": self.load_plan,
            "receipt": self.receipt,
        }


def _fail(message: str) -> None:
    raise PrelockLineageGraphV2Error(message)


def _canonical_sha256(value: object) -> str:
    return graph.canonical_sha256(value)


def _logical_id(kind: str, *parts: object) -> str:
    return f"prelock-summary:{kind}:{_canonical_sha256(list(parts))}"


def _graph_node(value: Mapping[str, object]) -> dict[str, object]:
    try:
        return graph.validate_node_row(value)
    except graph.CorpusGraphVNextError as exc:
        raise PrelockLineageGraphV2Error(
            f"v2 cannot represent a summary node without schema expansion: {exc}"
        ) from exc


def _graph_edge(value: Mapping[str, object]) -> dict[str, object]:
    try:
        return graph.validate_edge_row(value)
    except graph.CorpusGraphVNextError as exc:
        raise PrelockLineageGraphV2Error(
            f"v2 cannot represent a summary edge without schema expansion: {exc}"
        ) from exc


def _identity(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not an identity mapping")
    retained = dict(value)
    expected = {"uri", "generation", "sha256", "bytes"}
    if set(retained) != expected:
        _fail(
            f"{label} keys differ: missing={sorted(expected - set(retained))}, "
            f"extra={sorted(set(retained) - expected)}"
        )
    uri = retained["uri"]
    generation = retained["generation"]
    digest = retained["sha256"]
    byte_count = retained["bytes"]
    if type(uri) is not str or not uri:
        _fail(f"{label} URI is invalid")
    if (
        type(generation) is not str
        or not generation.isdigit()
        or int(generation) < 1
    ):
        _fail(f"{label} generation is invalid")
    if type(digest) is not str or _SHA256.fullmatch(digest) is None:
        _fail(f"{label} SHA-256 is invalid")
    if type(byte_count) is not int or byte_count < 1:
        _fail(f"{label} byte count is invalid")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": byte_count,
    }


def _utc_timestamp(value: object, *, label: str) -> tuple[str, datetime]:
    if type(value) is not str or _UTC_TIMESTAMP.fullmatch(value) is None:
        _fail(f"{label} must be UTC seconds in YYYY-MM-DDTHH:MM:SSZ form")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise PrelockLineageGraphV2Error(f"{label} is invalid") from exc
    return value, parsed


def _selector_retrieval_bindings(
    value: object, *, selector_ids: Sequence[str]
) -> dict[str, str]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        _fail("selector-to-retrieval-preset bindings are not a string-keyed map")
    item = dict(value)
    expected = set(selector_ids)
    if set(item) != expected:
        _fail(
            "selector-to-retrieval-preset binding keys differ: "
            f"missing={sorted(expected - set(item))}, "
            f"extra={sorted(set(item) - expected)}"
        )
    normalized: dict[str, str] = {}
    for selector_id in sorted(expected):
        preset_id = item[selector_id]
        if type(preset_id) is not str or _IDENTIFIER.fullmatch(preset_id) is None:
            _fail(f"retrieval preset for selector {selector_id!r} is invalid")
        normalized[selector_id] = preset_id
    return normalized


def _sidecar_provider_receipt(
    value: object,
    *,
    sidecar_identity: Mapping[str, object],
    frozen_at_utc: str,
    slate_lock_at_utc: str,
    projection_created_at_utc: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("sidecar provider receipt is not a mapping")
    item = dict(value)
    expected = {
        "schema_version",
        "publication_mode",
        "create_once",
        "create_once_precondition",
        "sidecar_identity",
        "storage_created_at_utc",
        "storage_metadata_authority",
        "exact_generation_reopened",
        "canonical_sidecar_bytes_reopened",
        "receipt_sha256",
    }
    if set(item) != expected:
        _fail(
            "sidecar provider receipt keys differ: "
            f"missing={sorted(expected - set(item))}, "
            f"extra={sorted(set(item) - expected)}"
        )
    retained_hash = item.pop("receipt_sha256")
    if (
        item.get("schema_version") != SIDECAR_PROVIDER_RECEIPT_SCHEMA
        or item.get("publication_mode") != CREATE_ONCE_PUBLICATION_MODE
        or item.get("create_once") is not True
        or item.get("create_once_precondition") != "if_generation_match=0"
        or item.get("storage_metadata_authority")
        != "google-cloud-storage-object-metadata"
        or item.get("exact_generation_reopened") is not True
        or item.get("canonical_sidecar_bytes_reopened") is not True
        or type(retained_hash) is not str
        or _SHA256.fullmatch(retained_hash) is None
        or retained_hash != _canonical_sha256(item)
    ):
        _fail("sidecar provider receipt contract or self-hash differs")
    retained_identity = _identity(
        item.get("sidecar_identity"), label="provider-receipt sidecar identity"
    )
    if retained_identity != sidecar_identity:
        _fail("provider receipt does not bind the exact sidecar identity")
    _, frozen = _utc_timestamp(frozen_at_utc, label="sidecar freeze time")
    created_text, created = _utc_timestamp(
        item.get("storage_created_at_utc"), label="provider creation time"
    )
    _, lock = _utc_timestamp(slate_lock_at_utc, label="slate lock")
    _, projected = _utc_timestamp(
        projection_created_at_utc, label="projection creation time"
    )
    if created < frozen:
        _fail("provider creation time precedes the sidecar freeze")
    if created >= lock:
        _fail("sidecar provider object was not created before slate lock")
    if projected < created:
        _fail("graph projection creation time precedes provider publication")
    return {
        **item,
        "sidecar_identity": retained_identity,
        "storage_created_at_utc": created_text,
        "receipt_sha256": retained_hash,
    }


def _validated_publication_evidence(
    *,
    publication_mode: str,
    provider_receipt: Mapping[str, object] | None,
    sidecar_identity: Mapping[str, object],
    header: Mapping[str, object],
    projection_created_at_utc: str,
) -> dict[str, object] | None:
    if publication_mode == INACTIVE_OFFLINE_MODE:
        if provider_receipt is not None:
            _fail("inactive offline mode cannot claim a provider receipt")
        return None
    if publication_mode != CREATE_ONCE_PUBLICATION_MODE:
        _fail("publication mode is outside the closed contract")
    if provider_receipt is None:
        _fail("publication mode requires a create-once provider receipt")
    return _sidecar_provider_receipt(
        provider_receipt,
        sidecar_identity=sidecar_identity,
        frozen_at_utc=str(header["frozen_at_utc"]),
        slate_lock_at_utc=str(header["slate_lock_at_utc"]),
        projection_created_at_utc=projection_created_at_utc,
    )


def _without_edge_key(edge: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in edge.items() if key != "edge_key"}


def _count_by(
    rows: Sequence[Mapping[str, object]], field: str, values: Sequence[str]
) -> dict[str, int]:
    counts = Counter(str(row[field]) for row in rows)
    unknown = set(counts) - set(values)
    if unknown:
        _fail(f"{field} contains values outside the closed sidecar vocabulary")
    return {value: counts[value] for value in values}


def _add_metric(
    *,
    nodes: list[dict[str, object]],
    relationships: list[dict[str, object]],
    parent_id: str,
    definition_id: str,
    value: int,
    support: int,
) -> None:
    if value < 0 or support < 0 or value > support:
        _fail(f"metric {definition_id} does not fit its declared support")
    metric_id = _logical_id("metric", parent_id, definition_id)
    nodes.append(
        _graph_node(
            {
                "kind": "MetricSet",
                "node_id": metric_id,
                "namespace": "metric",
                "properties": {
                    "metric_set_id": definition_id,
                    "definition_id": definition_id,
                    "scope": "structural",
                    "value": value,
                    "support": support,
                    "missing": 0,
                },
            }
        )
    )
    relationships.append(
        _graph_edge(
            {
                "relationship": "HAS_METRIC",
                "source_id": parent_id,
                "target_id": metric_id,
                "namespace": "metric",
                "properties": {"definition_id": definition_id},
            }
        )
    )


def _request_and_dedupe_summary(
    *,
    sidecar: Mapping[str, object],
    release_id: str,
    nodes: list[dict[str, object]],
    relationships: list[dict[str, object]],
) -> dict[str, object]:
    proposals = sidecar["proposal_requests"]
    attempts = sidecar["solve_attempts"]
    occurrences = sidecar["generated_occurrences"]
    rosters = sidecar["roster_identities"]
    dedupe = sidecar["dedupe_decisions"]
    if not all(
        isinstance(rows, Sequence)
        for rows in (proposals, attempts, occurrences, rosters, dedupe)
    ):
        _fail("validated sidecar record arrays are unavailable")

    request_statuses = _count_by(proposals, "terminal_status", _REQUEST_STATUSES)
    solve_statuses = _count_by(attempts, "status", _SOLVE_STATUSES)
    dedupe_dispositions = _count_by(dedupe, "disposition", _DEDUPE_DISPOSITIONS)
    request_total = len(proposals)
    attempt_total = len(attempts)
    dedupe_total = len(dedupe)
    metrics = {
        "proposal_request_count": (request_total, request_total),
        "solve_attempt_count": (attempt_total, attempt_total),
        "generated_occurrence_count": (len(occurrences), request_total),
        "unique_generated_roster_count": (len(rosters), len(occurrences)),
        "dedupe_decision_count": (dedupe_total, dedupe_total),
    }
    metrics.update(
        {
            f"proposal_status_{status.lower()}": (count, request_total)
            for status, count in request_statuses.items()
        }
    )
    metrics.update(
        {
            f"solve_status_{status.lower()}": (count, attempt_total)
            for status, count in solve_statuses.items()
        }
    )
    metrics.update(
        {
            f"dedupe_disposition_{disposition.lower()}": (
                count,
                dedupe_total,
            )
            for disposition, count in dedupe_dispositions.items()
        }
    )
    for definition_id, (value, support) in sorted(metrics.items()):
        _add_metric(
            nodes=nodes,
            relationships=relationships,
            parent_id=release_id,
            definition_id=definition_id,
            value=value,
            support=support,
        )
    return {
        "proposal_request_count": request_total,
        "solve_attempt_count": attempt_total,
        "generated_occurrence_count": len(occurrences),
        "unique_generated_roster_count": len(rosters),
        "dedupe_decision_count": dedupe_total,
        "request_statuses": request_statuses,
        "solve_statuses": solve_statuses,
        "dedupe_dispositions": dedupe_dispositions,
    }


def _admission_summary(
    *,
    sidecar: Mapping[str, object],
    release_id: str,
    nodes: list[dict[str, object]],
    relationships: list[dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, str]]:
    rows = sidecar["admission_decisions"]
    if not isinstance(rows, Sequence):
        _fail("validated admission decision array is unavailable")
    grouped: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["stage_ordinal"])].append(row)

    summaries: list[dict[str, object]] = []
    stage_node_ids: dict[str, str] = {}
    predecessor_id = release_id
    for stage_ordinal in sorted(grouped):
        stage_rows = grouped[stage_ordinal]
        stage_ids = {str(row["stage_id"]) for row in stage_rows}
        preset_ids = {str(row["admission_preset_id"]) for row in stage_rows}
        if len(stage_ids) != 1 or len(preset_ids) != 1:
            _fail(
                "v2 CandidateSnapshot cannot represent a stage with mixed "
                "stage or admission-preset identities"
            )
        stage_id = next(iter(stage_ids))
        preset_id = next(iter(preset_ids))
        dispositions = _count_by(stage_rows, "disposition", ("REJECTED", "RETAINED"))
        reasons = _count_by(stage_rows, "reason", _ADMISSION_REASONS)
        input_count = sum(
            len(row["source_occurrence_ids"]) + len(row["input_candidate_instance_ids"])
            for row in stage_rows
        )
        decision_count = len(stage_rows)
        retained_count = dispositions["RETAINED"]
        snapshot_id = _logical_id(
            "admission-stage", sidecar["run_header"]["run_id"], stage_ordinal
        )
        stage_node_ids[stage_id] = snapshot_id
        nodes.append(
            _graph_node(
                {
                    "kind": "CandidateSnapshot",
                    "node_id": snapshot_id,
                    "namespace": "membership",
                    "properties": {
                        "snapshot_id": stage_id,
                        "lineup_count": retained_count,
                        "schema_version": PROJECTION_SCHEMA,
                        "admission_preset_id": preset_id,
                    },
                }
            )
        )
        relationships.append(
            _graph_edge(
                {
                    "relationship": "DERIVED_FROM",
                    "source_id": snapshot_id,
                    "target_id": predecessor_id,
                    "namespace": "lineage",
                    "properties": {},
                }
            )
        )
        predecessor_id = snapshot_id
        metrics = {
            "admission_input_count": (input_count, input_count),
            "admission_decision_count": (decision_count, decision_count),
            "admission_retained_count": (retained_count, decision_count),
            "admission_rejected_count": (
                dispositions["REJECTED"],
                decision_count,
            ),
        }
        metrics.update(
            {
                f"admission_reason_{reason.lower()}": (count, decision_count)
                for reason, count in reasons.items()
            }
        )
        for definition_id, (value, support) in sorted(metrics.items()):
            _add_metric(
                nodes=nodes,
                relationships=relationships,
                parent_id=snapshot_id,
                definition_id=definition_id,
                value=value,
                support=support,
            )
        summaries.append(
            {
                "stage_id": stage_id,
                "stage_ordinal": stage_ordinal,
                "admission_preset_id": preset_id,
                "input_count": input_count,
                "decision_count": decision_count,
                "retained_count": retained_count,
                "rejected_count": dispositions["REJECTED"],
                "reason_counts": reasons,
            }
        )
    return summaries, stage_node_ids


def _strategy_summary(
    *,
    sidecar: Mapping[str, object],
    selector_retrieval_preset_bindings: Mapping[str, str],
    effective_snapshot_id: str,
    nodes: list[dict[str, object]],
    relationships: list[dict[str, object]],
) -> list[dict[str, object]]:
    header = sidecar["run_header"]
    strategy_rows = sidecar["strategy_decisions"]
    book_rows = sidecar["book_transitions"]
    prepared_rows = sidecar["prepared_entries"]
    if not all(
        isinstance(rows, Sequence) for rows in (strategy_rows, book_rows, prepared_rows)
    ):
        _fail("validated strategy arrays are unavailable")
    decisions: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    books: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    prepared: Counter[str] = Counter()
    for row in strategy_rows:
        decisions[str(row["strategy_id"])].append(row)
    for row in book_rows:
        books[str(row["strategy_id"])].append(row)
    for row in prepared_rows:
        prepared[str(row["strategy_id"])] += 1

    summaries: list[dict[str, object]] = []
    for strategy_id in header["selector_ids"]:
        rows = decisions[str(strategy_id)]
        transitions = books[str(strategy_id)]
        decisions_by_disposition = _count_by(
            rows, "decision", ("NOT_SELECTED", "SELECTED")
        )
        decision_reasons = _count_by(rows, "decision_reason", _STRATEGY_REASONS)
        book_dispositions = _count_by(transitions, "disposition", _BOOK_DISPOSITIONS)
        raw_selected = decisions_by_disposition["SELECTED"]
        postselector_count = sum(
            row["postselector_rank"] is not None for row in transitions
        )
        final_book_count = sum(row["export_rank"] is not None for row in transitions)
        prepared_count = prepared[str(strategy_id)]
        book_id = _logical_id("selected-book", header["run_id"], strategy_id)
        nodes.append(
            _graph_node(
                {
                    "kind": "SelectedBook",
                    "node_id": book_id,
                    "namespace": "membership",
                    "properties": {
                        "book_id": strategy_id,
                        "entry_budget": int(header["entry_budget"]),
                        "selected_count": final_book_count,
                        "retrieval_preset_id": (
                            selector_retrieval_preset_bindings[str(strategy_id)]
                        ),
                    },
                }
            )
        )
        relationships.append(
            _graph_edge(
                {
                    "relationship": "DERIVED_FROM",
                    "source_id": book_id,
                    "target_id": effective_snapshot_id,
                    "namespace": "lineage",
                    "properties": {},
                }
            )
        )
        decision_count = len(rows)
        transition_count = len(transitions)
        metrics = {
            "strategy_decision_count": (decision_count, decision_count),
            "strategy_selected_count": (raw_selected, decision_count),
            "strategy_not_selected_count": (
                decisions_by_disposition["NOT_SELECTED"],
                decision_count,
            ),
            "book_transition_count": (transition_count, transition_count),
            "postselector_book_count": (
                postselector_count,
                int(header["entry_budget"]),
            ),
            "final_book_count": (final_book_count, int(header["entry_budget"])),
            "prepared_entry_count": (prepared_count, int(header["entry_budget"])),
        }
        metrics.update(
            {
                f"strategy_reason_{reason.lower()}": (count, decision_count)
                for reason, count in decision_reasons.items()
            }
        )
        metrics.update(
            {
                f"book_disposition_{disposition.lower()}": (
                    count,
                    transition_count,
                )
                for disposition, count in book_dispositions.items()
            }
        )
        for definition_id, (value, support) in sorted(metrics.items()):
            _add_metric(
                nodes=nodes,
                relationships=relationships,
                parent_id=book_id,
                definition_id=definition_id,
                value=value,
                support=support,
            )
        summaries.append(
            {
                "strategy_id": strategy_id,
                "decision_count": decision_count,
                "selected_count": raw_selected,
                "not_selected_count": decisions_by_disposition["NOT_SELECTED"],
                "decision_reason_counts": decision_reasons,
                "book_transition_count": transition_count,
                "book_disposition_counts": book_dispositions,
                "postselector_book_count": postselector_count,
                "final_book_count": final_book_count,
                "prepared_entry_count": prepared_count,
            }
        )
    return summaries


def _reconcile_summary(
    *,
    sidecar: Mapping[str, object],
    request_dedupe: Mapping[str, object],
    admission: Sequence[Mapping[str, object]],
    strategies: Sequence[Mapping[str, object]],
) -> None:
    counts = sidecar["counts"]
    if not isinstance(counts, Mapping):
        _fail("validated sidecar count ledger is unavailable")
    for field in (
        "proposal_request_count",
        "solve_attempt_count",
        "generated_occurrence_count",
        "unique_generated_roster_count",
        "dedupe_decision_count",
    ):
        if request_dedupe[field] != counts[field]:
            _fail(f"{field} summary does not reconcile")
    if (
        sum(request_dedupe["request_statuses"].values())
        != counts["proposal_request_count"]
    ):
        _fail("proposal-request status summary does not reconcile")
    if sum(request_dedupe["solve_statuses"].values()) != counts["solve_attempt_count"]:
        _fail("solve-attempt status summary does not reconcile")
    if (
        sum(request_dedupe["dedupe_dispositions"].values())
        != counts["dedupe_decision_count"]
    ):
        _fail("dedupe summary does not reconcile")
    if (
        sum(int(row["decision_count"]) for row in admission)
        != counts["admission_decision_count"]
    ):
        _fail("admission-stage summary does not reconcile")
    for row in admission:
        if int(row["retained_count"]) + int(row["rejected_count"]) != int(
            row["decision_count"]
        ) or sum(row["reason_counts"].values()) != int(row["decision_count"]):
            _fail("admission-stage partition does not reconcile")
    for stage_ordinal, row in enumerate(admission):
        expected_input = (
            counts["generated_occurrence_count"]
            if stage_ordinal == 0
            else admission[stage_ordinal - 1]["retained_count"]
        )
        if (
            row["stage_ordinal"] != stage_ordinal
            or row["input_count"] != expected_input
        ):
            _fail("admission-stage transition does not reconcile")
    effective_stage = str(sidecar["run_header"]["effective_candidate_stage_id"])
    effective = next(
        (row for row in admission if row["stage_id"] == effective_stage), None
    )
    if (
        effective is None
        or effective["retained_count"] != counts["effective_candidate_count"]
    ):
        _fail("effective-candidate stage summary does not reconcile")
    if (
        sum(int(row["decision_count"]) for row in strategies)
        != counts["strategy_decision_count"]
    ):
        _fail("strategy-decision summary does not reconcile")
    if (
        sum(int(row["selected_count"]) for row in strategies)
        != counts["raw_selected_count"]
    ):
        _fail("raw-selected summary does not reconcile")
    if (
        sum(int(row["final_book_count"]) for row in strategies)
        != counts["final_book_lineup_count"]
    ):
        _fail("final-book summary does not reconcile")
    if (
        sum(int(row["prepared_entry_count"]) for row in strategies)
        != counts["prepared_entry_count"]
    ):
        _fail("prepared-entry summary does not reconcile")
    for row in strategies:
        if (
            int(row["decision_count"]) != counts["effective_candidate_count"]
            or int(row["selected_count"]) != sidecar["run_header"]["entry_budget"]
            or int(row["final_book_count"]) != sidecar["run_header"]["entry_budget"]
            or int(row["selected_count"]) + int(row["not_selected_count"])
            != int(row["decision_count"])
            or sum(row["decision_reason_counts"].values()) != int(row["decision_count"])
            or sum(row["book_disposition_counts"].values())
            != int(row["book_transition_count"])
        ):
            _fail("per-strategy partition does not reconcile")


def project_prelock_lineage_summary_v2(
    *,
    sidecar: Mapping[str, object],
    sidecar_identity: Mapping[str, object],
    selector_retrieval_preset_bindings: Mapping[str, str],
    graph_release_id: str,
    projection_created_at_utc: str,
    predecessor_graph_release_id: str | None = None,
    publication_mode: str = INACTIVE_OFFLINE_MODE,
    sidecar_provider_receipt: Mapping[str, object] | None = None,
) -> PrelockLineageGraphV2Projection:
    """Validate one sidecar and project only its aggregate pre-lock census."""

    try:
        retained = lineage.validate_prelock_candidate_lineage_v1(sidecar)
    except lineage.PrelockCandidateLineageError as exc:
        raise PrelockLineageGraphV2Error(
            f"pre-lock lineage sidecar validation failed: {exc}"
        ) from exc
    canonical_sidecar = lineage.canonical_json_bytes(retained)
    normalized_sidecar_identity = _identity(sidecar_identity, label="sidecar identity")
    if normalized_sidecar_identity["bytes"] != len(
        canonical_sidecar
    ) or normalized_sidecar_identity["sha256"] != _canonical_sha256(retained):
        _fail("sidecar content identity differs from its canonical bytes")

    header = retained["run_header"]
    normalized_bindings = _selector_retrieval_bindings(
        selector_retrieval_preset_bindings,
        selector_ids=header["selector_ids"],
    )
    normalized_provider_receipt = _validated_publication_evidence(
        publication_mode=publication_mode,
        provider_receipt=sidecar_provider_receipt,
        sidecar_identity=normalized_sidecar_identity,
        header=header,
        projection_created_at_utc=projection_created_at_utc,
    )
    source_rows = header["input_source_identities"]
    if not isinstance(source_rows, Sequence):
        _fail("validated input source identities are unavailable")
    source_identities = [
        {
            "uri": source["uri"],
            "generation": source["generation"],
            "sha256": source["sha256"],
            "bytes": source["bytes"],
        }
        for source in source_rows
    ]
    try:
        governed_manifest = graph.validate_load_manifest(
            {
                "schema_version": graph.LOAD_MANIFEST_SCHEMA,
                "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
                "graph_release_id": graph_release_id,
                "predecessor_graph_release_id": predecessor_graph_release_id,
                "allowed_namespaces": [
                    "identity",
                    "lineage",
                    "membership",
                    "metric",
                ],
                "source_releases": [
                    normalized_sidecar_identity,
                    *source_identities,
                ],
                "authorized_outcome_release_id": None,
                "created_at_utc": projection_created_at_utc,
            }
        )
    except graph.CorpusGraphVNextError as exc:
        raise PrelockLineageGraphV2Error(
            f"v2 source/manifest contract rejected the sidecar: {exc}"
        ) from exc
    if governed_manifest["created_at_utc"] < header["frozen_at_utc"]:
        _fail("graph projection creation time precedes the sidecar freeze")

    nodes: list[dict[str, object]] = []
    relationships: list[dict[str, object]] = []
    release_id = _logical_id("release", header["run_id"])
    nodes.append(
        _graph_node(
            {
                "kind": "ScienceRelease",
                "node_id": release_id,
                "namespace": "lineage",
                "properties": {
                    "release_id": header["run_id"],
                    "schema_version": lineage.SIDECAR_SCHEMA,
                    "code_sha256": header["code_sha256"],
                    "accepted": False,
                },
            }
        )
    )
    slate_node_id = _logical_id("slate", header["slate_id"])
    nodes.append(
        _graph_node(
            {
                "kind": "Slate",
                "node_id": slate_node_id,
                "namespace": "identity",
                "properties": {
                    "source_id": header["slate_id"],
                    "season": header["season"],
                    "week": header["week"],
                    "lock_at_utc": header["slate_lock_at_utc"],
                },
            }
        )
    )
    relationships.append(
        _graph_edge(
            {
                "relationship": "FOR_SLATE",
                "source_id": release_id,
                "target_id": slate_node_id,
                "namespace": "lineage",
                "properties": {},
            }
        )
    )

    artifact_specs = [
        ("lineage-sidecar", normalized_sidecar_identity, lineage.SIDECAR_SCHEMA),
        *[
            (str(source["role"]), identity, None)
            for source, identity in zip(source_rows, source_identities, strict=True)
        ],
    ]
    for artifact_role, identity, schema_version in artifact_specs:
        artifact_node_id = _logical_id(
            "source", header["run_id"], artifact_role, identity
        )
        properties: dict[str, object] = {
            "artifact_id": artifact_role,
            "uri": identity["uri"],
            "generation": identity["generation"],
            "sha256": identity["sha256"],
            "byte_count": identity["bytes"],
        }
        if schema_version is not None:
            properties["schema_version"] = schema_version
        nodes.append(
            _graph_node(
                {
                    "kind": "SourceArtifact",
                    "node_id": artifact_node_id,
                    "namespace": "lineage",
                    "properties": properties,
                }
            )
        )
        relationships.append(
            _graph_edge(
                {
                    "relationship": "USES_SOURCE",
                    "source_id": release_id,
                    "target_id": artifact_node_id,
                    "namespace": "lineage",
                    "properties": {},
                }
            )
        )

    request_dedupe = _request_and_dedupe_summary(
        sidecar=retained,
        release_id=release_id,
        nodes=nodes,
        relationships=relationships,
    )
    admission, stage_node_ids = _admission_summary(
        sidecar=retained,
        release_id=release_id,
        nodes=nodes,
        relationships=relationships,
    )
    effective_stage_id = str(header["effective_candidate_stage_id"])
    strategies = _strategy_summary(
        sidecar=retained,
        selector_retrieval_preset_bindings=normalized_bindings,
        effective_snapshot_id=stage_node_ids[effective_stage_id],
        nodes=nodes,
        relationships=relationships,
    )
    _reconcile_summary(
        sidecar=retained,
        request_dedupe=request_dedupe,
        admission=admission,
        strategies=strategies,
    )

    nodes.sort(key=lambda row: (str(row["kind"]), str(row["node_id"])))
    relationships.sort(key=lambda row: str(row["edge_key"]))
    try:
        load_plan = graph.build_load_plan(
            manifest=governed_manifest,
            node_rows=nodes,
            edge_rows=[_without_edge_key(edge) for edge in relationships],
        )
    except graph.CorpusGraphVNextError as exc:
        raise PrelockLineageGraphV2Error(
            f"v2 capacity or load-plan validation failed: {exc}"
        ) from exc

    node_kind_counts = dict(sorted(Counter(row["kind"] for row in nodes).items()))
    relationship_counts = dict(
        sorted(Counter(row["relationship"] for row in relationships).items())
    )
    logical_rows_sha256 = _canonical_sha256(
        {"nodes": nodes, "relationships": relationships}
    )
    mapping_transform_identity = dict(MAPPING_TRANSFORM_IDENTITY)
    projection_body: dict[str, object] = {
        "schema_version": PROJECTION_SCHEMA,
        "mapping_transform_identity": mapping_transform_identity,
        "selector_retrieval_preset_bindings": normalized_bindings,
        "governed_manifest": governed_manifest,
        "nodes": nodes,
        "relationships": relationships,
        "load_plan": load_plan,
    }
    receipt_body: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "projection_schema_version": PROJECTION_SCHEMA,
        "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
        "graph_release_id": governed_manifest["graph_release_id"],
        "projection_created_at_utc": governed_manifest["created_at_utc"],
        "run_id": header["run_id"],
        "publication_mode": publication_mode,
        "mapping_transform_identity": mapping_transform_identity,
        "selector_retrieval_preset_binding_sha256": _canonical_sha256(
            normalized_bindings
        ),
        "sidecar_schema_version": lineage.SIDECAR_SCHEMA,
        "sidecar_contract_sha256": retained["sidecar_sha256"],
        "sidecar_identity": normalized_sidecar_identity,
        "sidecar_provider_receipt": normalized_provider_receipt,
        "sidecar_provider_receipt_sha256": (
            None
            if normalized_provider_receipt is None
            else normalized_provider_receipt["receipt_sha256"]
        ),
        "input_source_identity_count": len(source_identities),
        "input_source_identity_set_sha256": _canonical_sha256(
            [
                {"role": source["role"], "identity": identity}
                for source, identity in zip(source_rows, source_identities, strict=True)
            ]
        ),
        "governed_manifest_sha256": governed_manifest["manifest_sha256"],
        "load_plan_sha256": load_plan["plan_sha256"],
        "logical_rows_sha256": logical_rows_sha256,
        "projection_sha256": _canonical_sha256(projection_body),
        "node_count": len(nodes),
        "relationship_count": len(relationships),
        "metric_count": node_kind_counts.get("MetricSet", 0),
        "admission_stage_count": len(admission),
        "strategy_count": len(strategies),
        "node_kind_counts": node_kind_counts,
        "relationship_type_counts": relationship_counts,
        "sidecar_content_verified": True,
        "sidecar_create_once_prelock_verified": (
            normalized_provider_receipt is not None
        ),
        "input_source_bodies_verified": False,
        "aggregate_reconciliation_verified": True,
        "individual_candidate_row_count": 0,
        "individual_roster_row_count": 0,
        "individual_player_row_count": 0,
        "outcome_namespace_row_count": 0,
        "database_load_performed": False,
        "authority_flags": dict(AUTHORITY_FLAGS),
    }
    receipt = {
        **receipt_body,
        "receipt_sha256": _canonical_sha256(receipt_body),
    }
    return PrelockLineageGraphV2Projection(
        mapping_transform_identity=mapping_transform_identity,
        selector_retrieval_preset_bindings=normalized_bindings,
        governed_manifest=governed_manifest,
        nodes=tuple(nodes),
        relationships=tuple(relationships),
        load_plan=load_plan,
        receipt=receipt,
    )


def canonical_projection_json_bytes(
    projection: PrelockLineageGraphV2Projection,
) -> bytes:
    """Serialize a validated projection in its sole publication encoding."""

    if not isinstance(projection, PrelockLineageGraphV2Projection):
        _fail("projection is not a validated pre-lock graph projection")
    try:
        return lineage.canonical_json_bytes(projection.as_dict())
    except lineage.PrelockCandidateLineageError as exc:
        raise PrelockLineageGraphV2Error(
            f"projection is not canonical JSON: {exc}"
        ) from exc


def _closed_json_object(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes:
        _fail("projection reopen input is not bytes")

    def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                _fail(f"projection JSON repeats key {key!r}")
            result[key] = value
        return result

    try:
        parsed = json.loads(raw.decode("ascii"), object_pairs_hook=_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, PrelockLineageGraphV2Error):
            raise
        raise PrelockLineageGraphV2Error(
            "projection is not a canonical JSON object"
        ) from exc
    if not isinstance(parsed, Mapping):
        _fail("projection canonical JSON root is not an object")
    document = dict(parsed)
    try:
        canonical = lineage.canonical_json_bytes(document)
    except lineage.PrelockCandidateLineageError as exc:
        raise PrelockLineageGraphV2Error(
            f"projection is not canonical JSON: {exc}"
        ) from exc
    if raw != canonical:
        _fail("projection bytes are not the exact canonical JSON encoding")
    return document


def reopen_prelock_lineage_summary_v2(
    *,
    projection_bytes: bytes,
    sidecar: Mapping[str, object],
    sidecar_identity: Mapping[str, object],
    selector_retrieval_preset_bindings: Mapping[str, str],
    graph_release_id: str,
    projection_created_at_utc: str,
    predecessor_graph_release_id: str | None = None,
    publication_mode: str = INACTIVE_OFFLINE_MODE,
    sidecar_provider_receipt: Mapping[str, object] | None = None,
) -> PrelockLineageGraphV2Projection:
    """Fail closed unless canonical bytes exactly replay from their authorities."""

    reopened = _closed_json_object(projection_bytes)
    expected = project_prelock_lineage_summary_v2(
        sidecar=sidecar,
        sidecar_identity=sidecar_identity,
        selector_retrieval_preset_bindings=selector_retrieval_preset_bindings,
        graph_release_id=graph_release_id,
        projection_created_at_utc=projection_created_at_utc,
        predecessor_graph_release_id=predecessor_graph_release_id,
        publication_mode=publication_mode,
        sidecar_provider_receipt=sidecar_provider_receipt,
    )
    expected_document = expected.as_dict()
    if reopened != expected_document:
        _fail("projection differs from canonical replay of its exact authorities")
    if projection_bytes != canonical_projection_json_bytes(expected):
        _fail("projection canonical bytes differ from deterministic replay")
    return expected


__all__ = [
    "AUTHORITY_FLAGS",
    "CREATE_ONCE_PUBLICATION_MODE",
    "INACTIVE_OFFLINE_MODE",
    "MAPPING_TRANSFORM_IDENTITY",
    "MAPPING_TRANSFORM_SCHEMA",
    "PROJECTION_SCHEMA",
    "RECEIPT_SCHEMA",
    "SIDECAR_PROVIDER_RECEIPT_SCHEMA",
    "PrelockLineageGraphV2Error",
    "PrelockLineageGraphV2Projection",
    "canonical_projection_json_bytes",
    "project_prelock_lineage_summary_v2",
    "reopen_prelock_lineage_summary_v2",
]
