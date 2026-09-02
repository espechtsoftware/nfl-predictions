"""Bounded outcome-free graph-v2 projection of one pre-lock lineage root.

Detailed requests, rosters, candidates, selector rows, and matrices remain in
their immutable provider objects.  This adapter emits only source receipts,
stage censuses, aggregate transitions, and a governed ``corpus-graph-vnext/v2``
load plan.  It performs no Neo4j I/O and grants no decision authority.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Final

from nfl_dfs.inference.prelock_candidate_lineage_v1 import (
    canonical_json_bytes,
    canonical_sha256,
)
from nfl_dfs.inference.prelock_lineage_runtime_v1 import (
    validate_runtime_envelope_v1,
    validate_terminal_root_v1,
)
from nfl_dfs.research import corpus_graph_vnext_contracts as graph

SUMMARY_SCHEMA: Final = "prelock-lineage-graph-summary/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UTC_SECONDS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class PrelockLineageGraphSummaryError(ValueError):
    """A detailed lineage root could not produce its bounded v2 summary."""


def _fail(message: str) -> None:
    raise PrelockLineageGraphSummaryError(message)


def _provider_identity(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "uri",
        "generation",
        "sha256",
        "bytes",
        "time_created",
    }:
        _fail(f"{label} provider identity fields differ")
    item = dict(value)
    generation = str(item["generation"])
    digest = item["sha256"]
    byte_count = item["bytes"]
    if (
        not isinstance(item["uri"], str)
        or not item["uri"].startswith("gs://")
        or not generation.isdigit()
        or int(generation) < 1
        or not isinstance(digest, str)
        or _SHA256.fullmatch(digest) is None
        or not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or byte_count < 1
    ):
        _fail(f"{label} provider identity differs")
    try:
        created = datetime.fromisoformat(str(item["time_created"]))
    except ValueError as exc:
        raise PrelockLineageGraphSummaryError(f"{label} creation time differs") from exc
    if created.tzinfo is None or created.utcoffset() is None:
        _fail(f"{label} creation time is not timezone-aware")
    return {
        "uri": item["uri"],
        "generation": generation,
        "sha256": digest,
        "bytes": byte_count,
        "time_created": created.astimezone(UTC).isoformat(),
    }


def _utc_seconds(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _UTC_SECONDS.fullmatch(value) is None:
        _fail(f"{label} must be second-precision UTC")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise PrelockLineageGraphSummaryError(f"{label} is invalid") from exc
    return value


def _node(
    kind: str,
    node_id: str,
    namespace: str,
    properties: Mapping[str, object],
) -> dict[str, object]:
    try:
        return graph.validate_node_row(
            {
                "kind": kind,
                "node_id": node_id,
                "namespace": namespace,
                "properties": dict(properties),
            }
        )
    except graph.CorpusGraphVNextError as exc:
        raise PrelockLineageGraphSummaryError(
            f"graph summary node {node_id} is invalid: {exc}"
        ) from exc


def _edge(
    relationship: str,
    source_id: str,
    target_id: str,
    namespace: str,
    properties: Mapping[str, object] | None = None,
) -> dict[str, object]:
    try:
        return graph.validate_edge_row(
            {
                "relationship": relationship,
                "source_id": source_id,
                "target_id": target_id,
                "namespace": namespace,
                "properties": dict(properties or {}),
            }
        )
    except graph.CorpusGraphVNextError as exc:
        raise PrelockLineageGraphSummaryError(
            "graph summary relationship is invalid: " + str(exc)
        ) from exc


def _metric_rows(
    *,
    prefix: str,
    run_node_id: str,
    source_node_id: str,
    definitions: Sequence[tuple[str, int, int]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    for ordinal, (definition, count, support) in enumerate(definitions):
        definition_id = f"prelock-lineage-v1:{definition}"
        metric_id = f"{prefix}:metric:{ordinal:03d}"
        nodes.append(
            _node(
                "MetricSet",
                metric_id,
                "metric",
                {
                    "metric_set_id": metric_id,
                    "definition_id": definition_id,
                    "scope": "structural",
                    "value": count,
                    "support": support,
                    "missing": 0,
                },
            )
        )
        edges.extend(
            (
                _edge(
                    "HAS_METRIC",
                    run_node_id,
                    metric_id,
                    "metric",
                    {"definition_id": definition_id},
                ),
                _edge(
                    "DERIVED_FROM",
                    metric_id,
                    source_node_id,
                    "lineage",
                ),
            )
        )
    return nodes, edges


def _aggregate_definitions(
    sidecar: Mapping[str, object],
) -> list[tuple[str, int, int]]:
    definitions: list[tuple[str, int, int]] = []
    counts = sidecar["counts"]
    for name, count in sorted(counts.items()):
        definitions.append((f"census:{name}", int(count), int(count)))

    record_groups = (
        ("proposal-terminal", "proposal_requests", "terminal_status"),
        ("solve-status", "solve_attempts", "status"),
        ("dedupe-disposition", "dedupe_decisions", "disposition"),
        ("strategy-decision", "strategy_decisions", "decision_reason"),
        ("book-transition", "book_transitions", "reason"),
    )
    for label, collection, field in record_groups:
        records = sidecar[collection]
        counter = Counter(str(row[field]).lower() for row in records)
        for value, count in sorted(counter.items()):
            definitions.append((f"{label}:{value}", int(count), len(records)))

    by_stage: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in sidecar["admission_decisions"]:
        by_stage[str(row["stage_id"])].append(row)
    for stage_id, records in sorted(by_stage.items()):
        stage_digest = canonical_sha256(stage_id)[:12]
        counter = Counter(str(row["reason"]).lower() for row in records)
        for reason, count in sorted(counter.items()):
            definitions.append(
                (
                    f"admission:{stage_digest}:{reason}",
                    int(count),
                    len(records),
                )
            )
    return definitions


def _assemble_summary(
    *,
    candidate_envelope: Mapping[str, object],
    terminal_root: Mapping[str, object],
    terminal_object_identity: Mapping[str, object],
    graph_release_id: str,
    created_at_utc: str,
) -> dict[str, Any]:
    candidate = validate_runtime_envelope_v1(candidate_envelope)
    terminal = validate_terminal_root_v1(terminal_root, candidate_envelope=candidate)
    if terminal["scope"] != "SHADOW_CANDIDATE_ONLY":
        _fail("graph summary v1 accepts the candidate-only shadow scope")
    terminal_object = _provider_identity(
        terminal_object_identity, label="terminal root"
    )
    terminal_bytes = canonical_json_bytes(terminal)
    if terminal_object["sha256"] != sha256(
        terminal_bytes
    ).hexdigest() or terminal_object["bytes"] != len(terminal_bytes):
        _fail("terminal provider object does not bind the exact root bytes")
    created = _utc_seconds(created_at_utc, label="graph summary creation")
    created_time = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    terminal_created = datetime.fromisoformat(str(terminal_object["time_created"]))
    if created_time < terminal_created:
        _fail("graph summary creation predates its terminal provider object")
    header = candidate["sidecar"]["run_header"]
    run_digest = candidate["envelope_sha256"][:24]
    prefix = f"prelock:{run_digest}"
    run_node_id = f"{prefix}:run"
    slate_node_id = f"{prefix}:slate"
    science_node_id = f"{prefix}:science"

    source_objects = {
        "candidate": terminal["objects"]["candidate_sidecar"],
        "matrix": terminal["objects"]["selector_matrix"],
        "terminal": terminal_object,
    }
    source_schemas = {
        "candidate": candidate["schema_version"],
        "matrix": "prelock-selector-matrix-raw/v1",
        "terminal": terminal["schema_version"],
    }
    source_node_ids = {role: f"{prefix}:source:{role}" for role in source_objects}

    nodes = [
        _node(
            "ExperimentRun",
            run_node_id,
            "identity",
            {
                "run_id": str(header["run_id"]),
                "status": "frozen_prelock_shadow",
                "completed_at_utc": str(header["frozen_at_utc"]),
                "task_count": 1,
                "accepted_task_count": 1,
            },
        ),
        _node(
            "Slate",
            slate_node_id,
            "identity",
            {
                "season": int(header["season"]),
                "week": int(header["week"]),
                "slate_type": "draftkings-classic",
                "lock_at_utc": str(header["slate_lock_at_utc"]),
            },
        ),
        _node(
            "ScienceRelease",
            science_node_id,
            "lineage",
            {
                "release_id": f"prelock-code:{header['code_sha256']}",
                "schema_version": candidate["schema_version"],
                "code_sha256": str(header["code_sha256"]),
                "accepted": False,
            },
        ),
    ]
    edges = [
        _edge("FOR_SLATE", run_node_id, slate_node_id, "lineage"),
        _edge("GENERATED_BY", run_node_id, science_node_id, "lineage"),
    ]
    for role in sorted(source_objects):
        identity = source_objects[role]
        source_node_id = source_node_ids[role]
        nodes.append(
            _node(
                "SourceArtifact",
                source_node_id,
                "lineage",
                {
                    "artifact_id": f"prelock-{role}:{identity['sha256']}",
                    "uri": str(identity["uri"]),
                    "generation": str(identity["generation"]),
                    "sha256": str(identity["sha256"]),
                    "byte_count": int(identity["bytes"]),
                    "schema_version": source_schemas[role],
                },
            )
        )
        edges.append(_edge("USES_SOURCE", run_node_id, source_node_id, "lineage"))

    by_stage: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in candidate["sidecar"]["admission_decisions"]:
        by_stage[str(row["stage_id"])].append(row)
    stage_node_ids: dict[str, str] = {}
    for ordinal, (stage_id, records) in enumerate(
        sorted(
            by_stage.items(),
            key=lambda item: min(int(row["stage_ordinal"]) for row in item[1]),
        )
    ):
        presets = {str(row["admission_preset_id"]) for row in records}
        if len(presets) != 1:
            _fail("one lineage stage names multiple admission presets")
        stage_node_id = f"{prefix}:stage:{ordinal:02d}"
        stage_node_ids[stage_id] = stage_node_id
        nodes.append(
            _node(
                "CandidateSnapshot",
                stage_node_id,
                "membership",
                {
                    "snapshot_id": stage_id,
                    "lineup_count": sum(
                        row["disposition"] == "RETAINED" for row in records
                    ),
                    "schema_version": candidate["sidecar"]["schema_version"],
                    "admission_preset_id": next(iter(presets)),
                },
            )
        )
        edges.append(
            _edge(
                "DERIVED_FROM",
                stage_node_id,
                source_node_ids["candidate"],
                "lineage",
            )
        )

    effective_stage = str(header["effective_candidate_stage_id"])
    if effective_stage not in stage_node_ids:
        _fail("effective candidate stage is absent from graph summary")
    strategy_ids = list(header["selector_ids"])
    for ordinal, strategy_id in enumerate(strategy_ids):
        decisions = [
            row
            for row in candidate["sidecar"]["strategy_decisions"]
            if row["strategy_id"] == strategy_id
        ]
        objectives = {str(row["objective_id"]) for row in decisions}
        if len(objectives) != 1:
            _fail("one selector names multiple frozen objectives")
        strategy_node_id = f"{prefix}:strategy:{ordinal:02d}"
        book_node_id = f"{prefix}:book:{ordinal:02d}"
        nodes.extend(
            (
                _node(
                    "StrategyBundle",
                    strategy_node_id,
                    "identity",
                    {
                        "bundle_id": str(strategy_id),
                        "version": "prelock-lineage-phase1",
                        "entry_budget": int(header["entry_budget"]),
                        "admission_preset_id": effective_stage,
                        "retrieval_preset_id": next(iter(objectives)),
                    },
                ),
                _node(
                    "SelectedBook",
                    book_node_id,
                    "membership",
                    {
                        "book_id": f"{header['run_id']}:{strategy_id}",
                        "entry_budget": int(header["entry_budget"]),
                        "selected_count": sum(
                            row["decision"] == "SELECTED" for row in decisions
                        ),
                        "retrieval_preset_id": next(iter(objectives)),
                    },
                ),
            )
        )
        edges.extend(
            (
                _edge(
                    "DERIVED_FROM",
                    strategy_node_id,
                    source_node_ids["candidate"],
                    "lineage",
                ),
                _edge(
                    "DERIVED_FROM",
                    book_node_id,
                    stage_node_ids[effective_stage],
                    "lineage",
                ),
                _edge(
                    "SELECTED_BY",
                    book_node_id,
                    strategy_node_id,
                    "membership",
                ),
            )
        )

    metric_nodes, metric_edges = _metric_rows(
        prefix=prefix,
        run_node_id=run_node_id,
        source_node_id=source_node_ids["candidate"],
        definitions=_aggregate_definitions(candidate["sidecar"]),
    )
    nodes.extend(metric_nodes)
    edges.extend(metric_edges)
    nodes.sort(key=lambda row: (str(row["kind"]), str(row["node_id"])))
    edges.sort(key=lambda row: str(row["edge_key"]))

    manifest_sources = [
        {key: identity[key] for key in ("uri", "generation", "sha256", "bytes")}
        for identity in source_objects.values()
    ]
    try:
        manifest = graph.validate_load_manifest(
            {
                "schema_version": graph.LOAD_MANIFEST_SCHEMA,
                "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
                "graph_release_id": graph_release_id,
                "predecessor_graph_release_id": None,
                "allowed_namespaces": ["identity", "lineage", "membership", "metric"],
                "source_releases": manifest_sources,
                "authorized_outcome_release_id": None,
                "created_at_utc": created,
            }
        )
        load_plan = graph.build_load_plan(
            manifest=manifest,
            node_rows=nodes,
            edge_rows=[
                {key: nested for key, nested in edge.items() if key != "edge_key"}
                for edge in edges
            ],
        )
    except graph.CorpusGraphVNextError as exc:
        raise PrelockLineageGraphSummaryError(
            f"governed graph-v2 projection failed: {exc}"
        ) from exc

    body: dict[str, Any] = {
        "schema_version": SUMMARY_SCHEMA,
        "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
        "candidate_envelope_sha256": candidate["envelope_sha256"],
        "terminal_root_sha256": terminal["terminal_sha256"],
        "graph_release_id": graph_release_id,
        "created_at_utc": created,
        "coverage": {
            "candidate_universe_scope": candidate["sidecar"][
                "candidate_universe_scope"
            ],
            "proposal_requests_complete": True,
            "solve_attempts_complete": True,
            "generated_occurrences_complete": True,
            "dedupe_decisions_complete": True,
            "admission_decisions_complete": True,
            "strategy_decisions_complete": True,
            "book_transitions_complete": True,
            "detailed_candidate_rows_included": False,
            "matrix_bytes_included": False,
        },
        "summary_counts": dict(candidate["sidecar"]["counts"]),
        "governed_manifest": manifest,
        "node_rows": nodes,
        "edge_rows": edges,
        "load_plan": load_plan,
        "decision_authority": False,
        "promotion_authority": False,
        "graph_mutation_authority": False,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    body["summary_sha256"] = canonical_sha256(body)
    return body


def build_prelock_lineage_graph_summary_v1(
    *,
    candidate_envelope: Mapping[str, object],
    terminal_root: Mapping[str, object],
    terminal_object_identity: Mapping[str, object],
    graph_release_id: str,
    created_at_utc: str,
) -> dict[str, Any]:
    """Build one deterministic, summary-only graph-v2 projection packet."""

    return _assemble_summary(
        candidate_envelope=candidate_envelope,
        terminal_root=terminal_root,
        terminal_object_identity=terminal_object_identity,
        graph_release_id=graph_release_id,
        created_at_utc=created_at_utc,
    )


def validate_prelock_lineage_graph_summary_v1(
    value: object,
    *,
    candidate_envelope: Mapping[str, object],
    terminal_root: Mapping[str, object],
    terminal_object_identity: Mapping[str, object],
) -> dict[str, Any]:
    """Exact-rebuild a summary packet from its immutable detailed sources."""

    if not isinstance(value, Mapping):
        _fail("pre-lock graph summary is not a mapping")
    item = dict(value)
    required = {
        "schema_version",
        "graph_schema_version",
        "candidate_envelope_sha256",
        "terminal_root_sha256",
        "graph_release_id",
        "created_at_utc",
        "coverage",
        "summary_counts",
        "governed_manifest",
        "node_rows",
        "edge_rows",
        "load_plan",
        "decision_authority",
        "promotion_authority",
        "graph_mutation_authority",
        "uses_realized_outcomes",
        "post_lock_data_read",
        "summary_sha256",
    }
    if set(item) != required or item.get("schema_version") != SUMMARY_SCHEMA:
        _fail("pre-lock graph summary fields differ")
    digest = item.get("summary_sha256")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        _fail("pre-lock graph summary hash differs")
    unhashed = {key: nested for key, nested in item.items() if key != "summary_sha256"}
    if canonical_sha256(unhashed) != digest:
        _fail("pre-lock graph summary self-hash differs")
    expected = _assemble_summary(
        candidate_envelope=candidate_envelope,
        terminal_root=terminal_root,
        terminal_object_identity=terminal_object_identity,
        graph_release_id=str(item["graph_release_id"]),
        created_at_utc=str(item["created_at_utc"]),
    )
    if item != expected:
        _fail("pre-lock graph summary differs from its immutable lineage root")
    return expected


__all__ = [
    "SUMMARY_SCHEMA",
    "PrelockLineageGraphSummaryError",
    "build_prelock_lineage_graph_summary_v1",
    "validate_prelock_lineage_graph_summary_v1",
]
