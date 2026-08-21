"""Default-off Neo4j projection for accepted corpus-retrieval evidence.

The create-once GCS objects remain authoritative.  This module validates one
terminal receipt -> batch completion -> task result -> graph projection chain
and turns it into a storage-neutral load plan.  The plan stores compact JSON
properties and exact object pointers; it never stores world matrices, grants a
research license, or changes a production policy.

All Cypher values are passed through ``$rows``.  Semantic labels and
relationship types from evidence are properties, not interpolated query text.
Existing rows are immutable: ``MERGE`` sets values only on creation and a
conflicting repeat makes the enclosing transaction fail.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Final


LOAD_SCHEMA: Final = "corpus-retrieval-neo4j-load-plan/v1"
LOAD_RESULT_SCHEMA: Final = "corpus-retrieval-neo4j-load-result/v2"
TASK_RESULT_SCHEMA: Final = "corpus-retrieval-task-result/v1"
COMPLETION_SCHEMA: Final = "corpus-retrieval-batch-completion/v1"
GRAPH_SCHEMA: Final = "corpus-retrieval-graph-projection/v1"
TERMINAL_SCHEMA: Final = "corpus-retrieval-transport-terminal/v1"
ENABLE_ENV: Final = "CORPUS_RETRIEVAL_NEO4J_ENABLED"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GENERATION = re.compile(r"^[1-9][0-9]*$")


class CorpusRetrievalNeo4jError(ValueError):
    """Raised when retained evidence or an immutable load differs."""


@dataclass(frozen=True, slots=True)
class CypherStatement:
    """One parameterized Cypher statement and its immutable rows."""

    name: str
    query: str
    rows: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class Neo4jLoadPlan:
    """Validated, storage-neutral representation of one graph load."""

    schema_version: str
    run_id: str
    task_id: str
    terminal_receipt_identity: dict[str, object]
    batch_completion_identity: dict[str, object]
    task_result_identity: dict[str, object]
    graph_projection_identity: dict[str, object]
    nodes: tuple[dict[str, object], ...]
    relationships: tuple[dict[str, object], ...]
    plan_sha256: str

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "terminal_receipt_identity": self.terminal_receipt_identity,
            "batch_completion_identity": self.batch_completion_identity,
            "task_result_identity": self.task_result_identity,
            "graph_projection_identity": self.graph_projection_identity,
            "node_count": len(self.nodes),
            "relationship_count": len(self.relationships),
            "large_world_bodies_stored": False,
            "production_policy_mutation": False,
            "plan_sha256": self.plan_sha256,
        }


SCHEMA_STATEMENTS: Final[tuple[str, ...]] = (
    "CREATE CONSTRAINT corpus_retrieval_entity_id IF NOT EXISTS "
    "FOR (n:CorpusRetrievalEntity) REQUIRE n.id IS UNIQUE",
    "CREATE INDEX corpus_retrieval_entity_kind IF NOT EXISTS "
    "FOR (n:CorpusRetrievalEntity) ON (n.kind)",
    "CREATE INDEX corpus_retrieval_entity_logical_id IF NOT EXISTS "
    "FOR (n:CorpusRetrievalEntity) ON (n.logical_id)",
    "CREATE INDEX corpus_retrieval_entity_run_id IF NOT EXISTS "
    "FOR (n:CorpusRetrievalEntity) ON (n.run_id)",
    "CREATE INDEX corpus_retrieval_entity_task_id IF NOT EXISTS "
    "FOR (n:CorpusRetrievalEntity) ON (n.task_id)",
    "CREATE INDEX corpus_retrieval_entity_task_index IF NOT EXISTS "
    "FOR (n:CorpusRetrievalEntity) ON (n.task_index)",
    "CREATE INDEX corpus_retrieval_entity_slate_id IF NOT EXISTS "
    "FOR (n:CorpusRetrievalEntity) ON (n.slate_id)",
    "CREATE INDEX corpus_retrieval_entity_payload_sha256 IF NOT EXISTS "
    "FOR (n:CorpusRetrievalEntity) ON (n.payload_sha256)",
    "CREATE INDEX corpus_retrieval_entity_namespace IF NOT EXISTS "
    "FOR (n:CorpusRetrievalEntity) ON (n.workstream_namespace)",
    "CREATE INDEX corpus_retrieval_entity_parameter_set IF NOT EXISTS "
    "FOR (n:CorpusRetrievalEntity) ON (n.parameter_set_id)",
    "CREATE INDEX corpus_retrieval_entity_strategy IF NOT EXISTS "
    "FOR (n:CorpusRetrievalEntity) ON (n.strategy_id)",
    "CREATE INDEX corpus_retrieval_entity_metric IF NOT EXISTS "
    "FOR (n:CorpusRetrievalEntity) ON (n.metric_name)",
    "CREATE INDEX corpus_retrieval_relation_key IF NOT EXISTS "
    "FOR ()-[r:CORPUS_RELATION]-() ON (r.edge_key)",
    "CREATE INDEX corpus_retrieval_relation_type IF NOT EXISTS "
    "FOR ()-[r:CORPUS_RELATION]-() ON (r.relationship_type)",
)


NODE_UPSERT_CYPHER: Final = """
UNWIND $rows AS row
OPTIONAL MATCH (source_alias:CorpusRetrievalEntity)
WHERE row.task_index_present = true AND
  source_alias.task_index_present = true AND
  source_alias.task_index <> row.task_index AND
  source_alias.source_uri = row.source_uri AND
  source_alias.source_generation = row.source_generation AND
  source_alias.source_sha256 = row.source_sha256 AND
  source_alias.source_bytes = row.source_bytes
WITH row, count(source_alias) = 0 AS source_task_unaliased
MERGE (node:CorpusRetrievalEntity {id: row.id})
ON CREATE SET
  node.kind = row.kind,
  node.logical_id = row.logical_id,
  node.run_id = row.run_id,
  node.task_id = row.task_id,
  node.payload_sha256 = row.payload_sha256,
  node.properties_json = row.properties_json,
  node.source_uri = row.source_uri,
  node.source_generation = row.source_generation,
  node.source_sha256 = row.source_sha256,
  node.source_bytes = row.source_bytes,
  node.workstream_namespace = row.workstream_namespace,
  node.task_index = row.task_index,
  node.task_index_present = row.task_index_present,
  node.slate_id = row.slate_id,
  node.parameter_set_id = row.parameter_set_id,
  node.strategy_id = row.strategy_id,
  node.analysis_scope = row.analysis_scope,
  node.metric_name = row.metric_name,
  node.metric_value = row.metric_value,
  node.metric_value_present = row.metric_value_present
WITH node, row,
  source_task_unaliased AND
  node.kind = row.kind AND
  node.logical_id = row.logical_id AND
  node.run_id = row.run_id AND
  node.task_id = row.task_id AND
  node.payload_sha256 = row.payload_sha256 AND
  node.properties_json = row.properties_json AND
  node.source_uri = row.source_uri AND
  node.source_generation = row.source_generation AND
  node.source_sha256 = row.source_sha256 AND
  node.source_bytes = row.source_bytes AND
  node.workstream_namespace = row.workstream_namespace AND
  node.task_index = row.task_index AND
  node.task_index_present = row.task_index_present AND
  node.slate_id = row.slate_id AND
  node.parameter_set_id = row.parameter_set_id AND
  node.strategy_id = row.strategy_id AND
  node.analysis_scope = row.analysis_scope AND
  node.metric_name = row.metric_name AND
  node.metric_value = row.metric_value AND
  node.metric_value_present = row.metric_value_present AS accepted
RETURN count(row) AS row_count,
       sum(CASE WHEN accepted THEN 1 ELSE 0 END) AS accepted_count
""".strip()


RELATIONSHIP_UPSERT_CYPHER: Final = """
UNWIND $rows AS row
MATCH (source:CorpusRetrievalEntity {id: row.from_id})
MATCH (target:CorpusRetrievalEntity {id: row.to_id})
MERGE (source)-[rel:CORPUS_RELATION {edge_key: row.edge_key}]->(target)
ON CREATE SET
  rel.relationship_type = row.relationship_type,
  rel.properties_json = row.properties_json,
  rel.payload_sha256 = row.payload_sha256,
  rel.selection_rank = row.selection_rank,
  rel.selection_rank_present = row.selection_rank_present,
  rel.task_index = row.task_index,
  rel.task_index_present = row.task_index_present,
  rel.slate_id = row.slate_id
WITH rel, row,
  rel.relationship_type = row.relationship_type AND
  rel.properties_json = row.properties_json AND
  rel.payload_sha256 = row.payload_sha256 AND
  rel.selection_rank = row.selection_rank AND
  rel.selection_rank_present = row.selection_rank_present AND
  rel.task_index = row.task_index AND
  rel.task_index_present = row.task_index_present AND
  rel.slate_id = row.slate_id AS accepted
RETURN count(row) AS row_count,
       sum(CASE WHEN accepted THEN 1 ELSE 0 END) AS accepted_count
""".strip()


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusRetrievalNeo4jError("value is not canonical JSON") from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def parse_canonical_json_bytes(raw: bytes, *, label: str) -> object:
    """Parse exact canonical bytes, rejecting duplicate keys and NaN."""

    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise CorpusRetrievalNeo4jError(
                    f"{label} contains duplicate key {key!r}"
                )
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise CorpusRetrievalNeo4jError(f"{label} contains {value}")

    if type(raw) is not bytes:
        raise CorpusRetrievalNeo4jError(f"{label} must be bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except CorpusRetrievalNeo4jError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusRetrievalNeo4jError(
            f"{label} is not valid UTF-8 JSON"
        ) from exc
    if canonical_json_bytes(value) != raw:
        raise CorpusRetrievalNeo4jError(f"{label} is not canonical JSON")
    return value


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusRetrievalNeo4jError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise CorpusRetrievalNeo4jError(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: set[str], *, label: str,
) -> None:
    if set(value) != expected:
        raise CorpusRetrievalNeo4jError(f"{label} schema differs")


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CorpusRetrievalNeo4jError(f"{label} must be a nonempty string")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise CorpusRetrievalNeo4jError(
            f"{label} must be an integer >= {minimum}"
        )
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, {"uri", "generation", "sha256", "bytes"}, label=label)
    uri = _string(item["uri"], label=f"{label}.uri")
    if not uri.startswith("gs://") or uri.endswith("/") or ".." in uri.split("/"):
        raise CorpusRetrievalNeo4jError(f"{label}.uri is not a GCS object URI")
    generation = _string(item["generation"], label=f"{label}.generation")
    digest = _string(item["sha256"], label=f"{label}.sha256")
    if _GENERATION.fullmatch(generation) is None:
        raise CorpusRetrievalNeo4jError(f"{label}.generation must be positive")
    if _SHA256.fullmatch(digest) is None:
        raise CorpusRetrievalNeo4jError(f"{label}.sha256 differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": _integer(item["bytes"], label=f"{label}.bytes", minimum=1),
    }


def _bind_body(raw: bytes, identity: object, *, label: str) -> dict[str, object]:
    normalized = _identity(identity, label=f"{label} identity")
    if (
        len(raw) != normalized["bytes"]
        or sha256(raw).hexdigest() != normalized["sha256"]
    ):
        raise CorpusRetrievalNeo4jError(f"{label} content identity differs")
    return normalized


def _validate_self_hash(
    value: Mapping[str, object], field: str, *, label: str,
) -> str:
    digest = _string(value.get(field), label=f"{label}.{field}")
    if _SHA256.fullmatch(digest) is None:
        raise CorpusRetrievalNeo4jError(f"{label}.{field} differs")
    body = {key: item for key, item in value.items() if key != field}
    if digest != canonical_sha256(body):
        raise CorpusRetrievalNeo4jError(f"{label} self-hash differs")
    return digest


def _require_license_values(
    value: object, *, expected: Mapping[str, bool], label: str,
) -> dict[str, bool]:
    item = _mapping(value, label=label)
    _exact_keys(item, set(expected), label=label)
    for key, expected_value in expected.items():
        if item[key] is not expected_value:
            raise CorpusRetrievalNeo4jError(f"{label}.{key} is not accepted")
    return dict(expected)


def _validate_completion(
    raw: bytes, identity: object,
) -> tuple[dict[str, object], dict[str, object]]:
    retained = _bind_body(raw, identity, label="batch completion")
    item = dict(_mapping(
        parse_canonical_json_bytes(raw, label="batch completion"),
        label="batch completion",
    ))
    _exact_keys(item, {
        "schema_version", "publication_mode", "suite_manifest_identity",
        "suite_manifest_sha256", "snapshot_manifest_identity",
        "snapshot_manifest_sha256", "run_id", "snapshot_id", "coverage",
        "task_results", "licenses", "batch_completion_sha256",
    }, label="batch completion")
    if item["schema_version"] != COMPLETION_SCHEMA:
        raise CorpusRetrievalNeo4jError("batch completion schema differs")
    _validate_self_hash(item, "batch_completion_sha256", label="batch completion")
    coverage = _mapping(item["coverage"], label="batch completion coverage")
    _exact_keys(coverage, {
        "task_count", "strategy_count", "task_strategy_cell_count",
        "all_tasks_complete", "all_strategies_equal_budget",
    }, label="batch completion coverage")
    tasks = _sequence(item["task_results"], label="batch task results")
    task_count = _integer(coverage["task_count"], label="completion task count", minimum=1)
    strategy_count = _integer(
        coverage["strategy_count"], label="completion strategy count", minimum=1
    )
    if (
        len(tasks) != task_count
        or coverage["task_strategy_cell_count"] != task_count * strategy_count
        or coverage["all_tasks_complete"] is not True
        or coverage["all_strategies_equal_budget"] is not True
    ):
        raise CorpusRetrievalNeo4jError("batch completion is incomplete")
    _require_license_values(item["licenses"], expected={
        "analytical_graph_projection_ready": True,
        "corpus_fill_authority": False,
        "historical_outcome_read_authority": False,
        "live_money_policy_authority": False,
        "production_default_change_authority": False,
    }, label="batch completion licenses")
    return item, retained


def _validate_task_result(
    raw: bytes, identity: object,
) -> tuple[dict[str, object], dict[str, object]]:
    retained = _bind_body(raw, identity, label="task result")
    item = dict(_mapping(
        parse_canonical_json_bytes(raw, label="task result"), label="task result"
    ))
    _exact_keys(item, {
        "schema_version", "publication_mode", "suite_manifest_identity",
        "suite_manifest_sha256", "snapshot_manifest_identity",
        "snapshot_manifest_sha256", "run_id", "snapshot_id", "task_index",
        "task_id", "snapshot_task_sha256", "execution", "coverage",
        "primary_event_summary", "source_receipts", "sidecars",
        "strategy_results", "graph_projection_object", "fill_insight_object",
        "licenses", "task_result_sha256",
    }, label="task result")
    if item["schema_version"] != TASK_RESULT_SCHEMA:
        raise CorpusRetrievalNeo4jError("task result schema differs")
    _validate_self_hash(item, "task_result_sha256", label="task result")
    coverage = _mapping(item["coverage"], label="task result coverage")
    _exact_keys(coverage, {
        "source_block_count", "source_candidate_rows", "unique_lineup_count",
        "discovery_eligible_lineup_count", "heldout_only_lineup_count",
        "world_count", "lineup_world_score_count",
        "every_unique_lineup_scored_in_every_world", "strategy_count",
        "exact_budget_per_strategy", "all_strategies_exact_budget",
    }, label="task result coverage")
    lineup_count = _integer(
        coverage["unique_lineup_count"], label="unique lineup count", minimum=80
    )
    world_count = _integer(coverage["world_count"], label="world count", minimum=1)
    strategy_count = _integer(
        coverage["strategy_count"], label="strategy count", minimum=1
    )
    if (
        coverage["source_block_count"] != 5
        or world_count != 50_000
        or coverage["lineup_world_score_count"] != lineup_count * world_count
        or coverage["every_unique_lineup_scored_in_every_world"] is not True
        or strategy_count != 4
        or coverage["exact_budget_per_strategy"] != 80
        or coverage["all_strategies_exact_budget"] is not True
    ):
        raise CorpusRetrievalNeo4jError("task result score coverage is incomplete")
    if len(_sequence(item["strategy_results"], label="strategy results")) != 4:
        raise CorpusRetrievalNeo4jError("task result strategy coverage is incomplete")
    _require_license_values(item["licenses"], expected={
        "analytics_authority": True,
        "corpus_fill_authority": False,
        "historical_outcome_read_authority": False,
        "live_money_policy_authority": False,
        "production_default_change_authority": False,
    }, label="task result licenses")
    return item, retained


def _validate_graph(
    raw: bytes,
    identity: object,
    *,
    task_result: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    retained = _bind_body(raw, identity, label="graph projection")
    item = dict(_mapping(
        parse_canonical_json_bytes(raw, label="graph projection"),
        label="graph projection",
    ))
    _exact_keys(item, {
        "schema_version", "dedicated_analytical_graph_only",
        "authoritative_source", "large_bodies_are_pointers",
        "analytic_artifact_pointers", "nodes", "edges", "licenses",
        "graph_projection_sha256",
    }, label="graph projection")
    if (
        item["schema_version"] != GRAPH_SCHEMA
        or item["dedicated_analytical_graph_only"] is not True
        or item["authoritative_source"] != "create-once-sidecars-and-task-result"
        or item["large_bodies_are_pointers"] is not True
    ):
        raise CorpusRetrievalNeo4jError("graph projection authority differs")
    _validate_self_hash(item, "graph_projection_sha256", label="graph projection")
    _require_license_values(item["licenses"], expected={
        "decision_authority": False,
        "corpus_fill_authority": False,
        "corpus_producer_input_authority": False,
        "fill_insight_uses_discovery_blocks_only": True,
        "heldout_content_is_descriptive_only": True,
        "live_money_policy_authority": False,
    }, label="graph projection licenses")

    pointers = _sequence(
        item["analytic_artifact_pointers"], label="graph artifact pointers"
    )
    sidecars = _sequence(task_result["sidecars"], label="task result sidecars")
    graph_sidecars = []
    non_graph_sidecars = []
    for index, raw_sidecar in enumerate(sidecars):
        sidecar = dict(_mapping(raw_sidecar, label=f"task sidecar[{index}]"))
        _exact_keys(sidecar, {
            "role", "strategy_id", "format", "object_identity", "semantic",
        }, label=f"task sidecar[{index}]")
        _identity(sidecar["object_identity"], label=f"task sidecar[{index}] identity")
        if sidecar["role"] == "graph-projection":
            graph_sidecars.append(sidecar)
        else:
            non_graph_sidecars.append(sidecar)
    if len(graph_sidecars) != 1 or graph_sidecars[0]["object_identity"] != retained:
        raise CorpusRetrievalNeo4jError("task result graph object binding differs")
    if task_result["graph_projection_object"] != retained:
        raise CorpusRetrievalNeo4jError("named graph projection binding differs")
    if canonical_json_bytes(pointers) != canonical_json_bytes(non_graph_sidecars):
        raise CorpusRetrievalNeo4jError("graph artifact pointer coverage differs")

    nodes = _sequence(item["nodes"], label="graph nodes")
    edges = _sequence(item["edges"], label="graph edges")
    node_ids: set[str] = set()
    kind_counts: dict[str, int] = {}
    normalized_nodes: list[dict[str, object]] = []
    for index, raw_node in enumerate(nodes):
        node = dict(_mapping(raw_node, label=f"graph node[{index}]"))
        _exact_keys(node, {"id", "kind", "properties"}, label=f"graph node[{index}]")
        logical_id = _string(node["id"], label=f"graph node[{index}].id")
        kind = _string(node["kind"], label=f"graph node[{index}].kind")
        _mapping(node["properties"], label=f"graph node[{index}].properties")
        if logical_id in node_ids:
            raise CorpusRetrievalNeo4jError("graph node IDs repeat")
        node_ids.add(logical_id)
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        normalized_nodes.append(node)
    if (
        kind_counts.get("RetrievalTask") != 1
        or kind_counts.get("LineupCandidate")
        != task_result["coverage"]["unique_lineup_count"]
        or kind_counts.get("RetrievalStrategyResult") != 4
    ):
        raise CorpusRetrievalNeo4jError("graph node coverage differs from task result")
    normalized_edges: list[dict[str, object]] = []
    edge_keys: set[str] = set()
    for index, raw_edge in enumerate(edges):
        edge = dict(_mapping(raw_edge, label=f"graph edge[{index}]"))
        _exact_keys(
            edge, {"from", "type", "to", "properties"}, label=f"graph edge[{index}]"
        )
        source = _string(edge["from"], label=f"graph edge[{index}].from")
        target = _string(edge["to"], label=f"graph edge[{index}].to")
        _string(edge["type"], label=f"graph edge[{index}].type")
        _mapping(edge["properties"], label=f"graph edge[{index}].properties")
        if source not in node_ids or target not in node_ids:
            raise CorpusRetrievalNeo4jError("graph edge has an absent endpoint")
        edge_key = canonical_sha256(edge)
        if edge_key in edge_keys:
            raise CorpusRetrievalNeo4jError("graph edges repeat")
        edge_keys.add(edge_key)
        normalized_edges.append(edge)
    return {
        **item,
        "nodes": normalized_nodes,
        "edges": normalized_edges,
    }, retained


def _validate_terminal(
    raw: bytes,
    identity: object,
    *,
    completion: Mapping[str, object],
    completion_identity: Mapping[str, object],
    task_result: Mapping[str, object],
    task_result_identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    retained = _bind_body(raw, identity, label="terminal receipt")
    if not str(retained["uri"]).endswith("/governance/terminal-receipt.json"):
        raise CorpusRetrievalNeo4jError("terminal receipt URI differs")
    item = dict(_mapping(
        parse_canonical_json_bytes(raw, label="terminal receipt"),
        label="terminal receipt",
    ))
    _exact_keys(item, {
        "schema_version", "finished_at_utc", "execution_contract",
        "prefix_claim", "runtime_iam_evidence", "launch_intent",
        "launch_ledger", "execution_name_ledger", "execution",
        "suite_manifest_identity", "snapshot_manifest_identity", "task_index",
        "task_id", "result_object", "task_result_sha256", "batch_completion",
        "batch_completion_sha256", "post_terminal_job",
        "output_inventory_before_terminal",
        "output_inventory_before_terminal_sha256", "one_execution",
        "attempt_zero", "retry_count", "generation_pinned_replay",
        "successful_deployment_remains_parked", "uses_realized_outcomes",
        "bigquery_access_licensed", "corpus_fill_licensed",
        "live_policy_access_licensed", "production_change_licensed",
        "terminal_receipt_sha256",
    }, label="terminal receipt")
    if item["schema_version"] != TERMINAL_SCHEMA:
        raise CorpusRetrievalNeo4jError("terminal receipt schema differs")
    _validate_self_hash(item, "terminal_receipt_sha256", label="terminal receipt")
    accepted = {
        "one_execution": True,
        "attempt_zero": True,
        "generation_pinned_replay": True,
        "successful_deployment_remains_parked": True,
        "uses_realized_outcomes": False,
        "bigquery_access_licensed": False,
        "corpus_fill_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
    }
    for key, expected in accepted.items():
        if item[key] is not expected:
            raise CorpusRetrievalNeo4jError(f"terminal receipt {key} is not accepted")
    if item["retry_count"] != 0:
        raise CorpusRetrievalNeo4jError("terminal receipt is not attempt zero")
    if (
        item["result_object"] != task_result_identity
        or item["task_result_sha256"] != task_result["task_result_sha256"]
        or item["batch_completion"] != completion_identity
        or item["batch_completion_sha256"]
        != completion["batch_completion_sha256"]
        or item["task_index"] != task_result["task_index"]
        or item["task_id"] != task_result["task_id"]
    ):
        raise CorpusRetrievalNeo4jError("terminal receipt evidence binding differs")
    execution = _mapping(item["execution"], label="terminal execution")
    result_execution = _mapping(task_result["execution"], label="task execution")
    if (
        result_execution.get("execution_id") != execution.get("execution_id")
        or result_execution.get("execution_name") != execution.get("execution_name")
        or result_execution.get("attempt") != 0
        or result_execution.get("retry_count") != 0
        or result_execution.get("mode") != "cloud-run-task"
    ):
        raise CorpusRetrievalNeo4jError("terminal execution binding differs")

    inventory = _sequence(
        item["output_inventory_before_terminal"], label="terminal inventory"
    )
    if item["output_inventory_before_terminal_sha256"] != canonical_sha256(inventory):
        raise CorpusRetrievalNeo4jError("terminal inventory SHA differs")
    inventory_keys: set[tuple[object, object, object]] = set()
    for index, raw_row in enumerate(inventory):
        row = _mapping(raw_row, label=f"terminal inventory[{index}]")
        _exact_keys(row, {"uri", "generation", "bytes"}, label=f"terminal inventory[{index}]")
        inventory_keys.add((row["uri"], row["generation"], row["bytes"]))
    required = [completion_identity, task_result_identity]
    required.extend(
        _identity(row["object_identity"], label="retained sidecar identity")
        for row in _sequence(task_result["sidecars"], label="task result sidecars")
        if isinstance(row, Mapping)
    )
    if any(
        (row["uri"], row["generation"], row["bytes"]) not in inventory_keys
        for row in required
    ):
        raise CorpusRetrievalNeo4jError("terminal inventory omits accepted objects")
    return item, retained


def _authority_node(
    *, kind: str, logical_id: str, run_id: str, task_id: str,
    identity: Mapping[str, object], payload: Mapping[str, object],
    workstream_namespace: str = "corpus-retrieval-research",
    task_index: int = 0, task_index_present: bool = True,
    slate_id: str = "",
    parameter_set_id: str = "", strategy_id: str = "",
    analysis_scope: str = "authority",
    metric_name: str = "", metric_value: float = 0.0,
    metric_value_present: bool = False,
) -> dict[str, object]:
    physical = canonical_sha256({"kind": kind, "identity": identity})
    return {
        "id": f"corpus-authority:{kind}:{physical}",
        "kind": kind,
        "logical_id": logical_id,
        "run_id": run_id,
        "task_id": task_id,
        "payload_sha256": canonical_sha256(payload),
        "properties_json": canonical_json_bytes(payload).decode("utf-8"),
        "source_uri": identity["uri"],
        "source_generation": identity["generation"],
        "source_sha256": identity["sha256"],
        "source_bytes": identity["bytes"],
        "workstream_namespace": workstream_namespace,
        "task_index": task_index,
        "task_index_present": task_index_present,
        "slate_id": slate_id or task_id,
        "parameter_set_id": parameter_set_id,
        "strategy_id": strategy_id,
        "analysis_scope": analysis_scope,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "metric_value_present": metric_value_present,
    }


def _relationship(
    source: str, relationship_type: str, target: str,
    properties: Mapping[str, object] | None = None,
    *, task_index: int = 0, task_index_present: bool = True,
    slate_id: str = "",
) -> dict[str, object]:
    props = {} if properties is None else dict(properties)
    payload = {
        "from_id": source,
        "relationship_type": relationship_type,
        "to_id": target,
        "properties": props,
    }
    digest = canonical_sha256(payload)
    rank = props.get("selection_rank")
    rank_present = type(rank) is int and rank >= 0
    return {
        "from_id": source,
        "to_id": target,
        "edge_key": digest,
        "relationship_type": relationship_type,
        "properties_json": canonical_json_bytes(props).decode("utf-8"),
        "payload_sha256": digest,
        "selection_rank": rank if rank_present else 0,
        "selection_rank_present": rank_present,
        "task_index": task_index,
        "task_index_present": task_index_present,
        "slate_id": slate_id,
    }


def build_load_plan(
    *,
    terminal_receipt_raw: bytes,
    terminal_receipt_identity: Mapping[str, object],
    batch_completion_raw: bytes,
    task_result_raw: bytes,
    graph_projection_raw: bytes,
) -> Neo4jLoadPlan:
    """Validate an accepted evidence chain and construct an immutable plan."""
    completion_identity_hint = _mapping(
        parse_canonical_json_bytes(
            terminal_receipt_raw, label="terminal receipt preflight"
        ),
        label="terminal receipt preflight",
    ).get("batch_completion")
    result_identity_hint = _mapping(
        parse_canonical_json_bytes(
            terminal_receipt_raw, label="terminal receipt preflight"
        ),
        label="terminal receipt preflight",
    ).get("result_object")
    completion, completion_identity = _validate_completion(
        batch_completion_raw, completion_identity_hint
    )
    task_result, task_result_identity = _validate_task_result(
        task_result_raw, result_identity_hint
    )
    graph, graph_identity = _validate_graph(
        graph_projection_raw,
        task_result["graph_projection_object"],
        task_result=task_result,
    )
    terminal, terminal_identity = _validate_terminal(
        terminal_receipt_raw,
        terminal_receipt_identity,
        completion=completion,
        completion_identity=completion_identity,
        task_result=task_result,
        task_result_identity=task_result_identity,
    )

    task_rows = _sequence(completion["task_results"], label="completion task rows")
    matching = [
        _mapping(row, label="completion task row")
        for row in task_rows
        if isinstance(row, Mapping)
        and row.get("task_index") == task_result["task_index"]
    ]
    if len(matching) != 1:
        raise CorpusRetrievalNeo4jError("completion does not accept this task result")
    binding = matching[0]
    if (
        binding.get("task_id") != task_result["task_id"]
        or binding.get("snapshot_task_sha256") != task_result["snapshot_task_sha256"]
        or binding.get("task_result_sha256") != task_result["task_result_sha256"]
        or binding.get("task_result_object") != task_result_identity
        or binding.get("unique_lineup_count")
        != task_result["coverage"]["unique_lineup_count"]
        or binding.get("lineup_world_score_count")
        != task_result["coverage"]["lineup_world_score_count"]
        or binding.get("strategy_count") != task_result["coverage"]["strategy_count"]
        or binding.get("exact_budget_per_strategy")
        != task_result["coverage"]["exact_budget_per_strategy"]
    ):
        raise CorpusRetrievalNeo4jError("completion task binding differs")
    if any(
        completion[key] != task_result[key]
        for key in (
            "publication_mode", "suite_manifest_identity", "suite_manifest_sha256",
            "snapshot_manifest_identity", "snapshot_manifest_sha256", "run_id",
            "snapshot_id",
        )
    ):
        raise CorpusRetrievalNeo4jError("completion/result manifest binding differs")

    run_id = _string(task_result["run_id"], label="run id")
    task_id = _string(task_result["task_id"], label="task id")
    nodes: list[dict[str, object]] = []
    authority_specs = [
        (
            "CorpusTerminalReceipt",
            f"terminal:{terminal['terminal_receipt_sha256']}",
            terminal_identity,
            terminal,
        ),
        (
            "CorpusBatchCompletion",
            f"completion:{completion['batch_completion_sha256']}",
            completion_identity,
            completion,
        ),
        (
            "CorpusTaskResult",
            f"task-result:{task_result['task_result_sha256']}",
            task_result_identity,
            task_result,
        ),
        (
            "CorpusGraphProjection",
            f"graph-projection:{graph['graph_projection_sha256']}",
            graph_identity,
            {
                "graph_projection_sha256": graph["graph_projection_sha256"],
                "schema_version": graph["schema_version"],
                "dedicated_analytical_graph_only": True,
                "large_bodies_are_pointers": True,
            },
        ),
    ]
    authority_ids: dict[str, str] = {}
    for kind, logical_id, identity, payload in authority_specs:
        row = _authority_node(
            kind=kind,
            logical_id=logical_id,
            run_id=run_id,
            task_id=task_id,
            identity=identity,
            payload=payload,
        )
        nodes.append(row)
        authority_ids[kind] = str(row["id"])

    graph_entity_ids: dict[str, str] = {}
    for raw_node in graph["nodes"]:
        node = _mapping(raw_node, label="validated graph node")
        logical_id = str(node["id"])
        properties = _mapping(node["properties"], label="validated node properties")
        kind = str(node["kind"])
        metric_name = ""
        metric_value = 0.0
        metric_present = False
        if (
            kind == "LineupCandidate"
            and type(properties.get(
                "strict_gt_200_event_count_all_r0_r4_descriptive"
            )) is int
        ):
            metric_name = "strict_gt_200_event_count_all_r0_r4_descriptive"
            metric_value = float(properties[metric_name])
            metric_present = True
        physical_id = (
            f"corpus-graph-entity:{graph_identity['sha256']}:"
            f"{canonical_sha256(logical_id)}"
        )
        graph_entity_ids[logical_id] = physical_id
        payload_digest = canonical_sha256(node)
        nodes.append({
            "id": physical_id,
            "kind": kind,
            "logical_id": logical_id,
            "run_id": run_id,
            "task_id": task_id,
            "payload_sha256": payload_digest,
            "properties_json": canonical_json_bytes(properties).decode("utf-8"),
            "source_uri": graph_identity["uri"],
            "source_generation": graph_identity["generation"],
            "source_sha256": graph_identity["sha256"],
            "source_bytes": graph_identity["bytes"],
            "workstream_namespace": "corpus-retrieval-research",
            "task_index": 0,
            "task_index_present": True,
            "slate_id": task_id,
            "parameter_set_id": "",
            "strategy_id": str(properties.get("strategy_id", "")),
            "analysis_scope": (
                "all-r0-r4-descriptive" if kind == "LineupCandidate" else "graph"
            ),
            "metric_name": metric_name,
            "metric_value": metric_value,
            "metric_value_present": metric_present,
        })

    artifact_ids: dict[tuple[object, ...], str] = {}
    for pointer in graph["analytic_artifact_pointers"]:
        row = _mapping(pointer, label="validated artifact pointer")
        identity = _identity(row["object_identity"], label="artifact pointer identity")
        key = tuple(identity[name] for name in ("uri", "generation", "sha256", "bytes"))
        artifact_id = f"corpus-artifact:{canonical_sha256(identity)}"
        artifact_ids[key] = artifact_id
        nodes.append(_authority_node(
            kind="CorpusArtifactPointer",
            logical_id=f"artifact:{row['role']}:{row['strategy_id'] or 'task'}",
            run_id=run_id,
            task_id=task_id,
            identity=identity,
            payload=dict(row),
            strategy_id=str(row["strategy_id"]),
            analysis_scope="pointer-only-large-bodies-remain-in-gcs",
        ) | {"id": artifact_id})

    relationships = [
        _relationship(
            authority_ids["CorpusTerminalReceipt"],
            "ACCEPTS_COMPLETION",
            authority_ids["CorpusBatchCompletion"],
            task_index=0, slate_id=task_id,
        ),
        _relationship(
            authority_ids["CorpusTerminalReceipt"],
            "ACCEPTS_TASK_RESULT",
            authority_ids["CorpusTaskResult"],
            task_index=0, slate_id=task_id,
        ),
        _relationship(
            authority_ids["CorpusBatchCompletion"],
            "INCLUDES_TASK_RESULT",
            authority_ids["CorpusTaskResult"],
            task_index=0, slate_id=task_id,
        ),
        _relationship(
            authority_ids["CorpusTaskResult"],
            "HAS_GRAPH_PROJECTION",
            authority_ids["CorpusGraphProjection"],
            task_index=0, slate_id=task_id,
        ),
    ]
    relationships.extend(
        _relationship(
            authority_ids["CorpusGraphProjection"],
            "PROJECTS_ENTITY",
            physical_id,
            {"logical_id": logical_id},
            task_index=0,
            slate_id=task_id,
        )
        for logical_id, physical_id in sorted(graph_entity_ids.items())
    )
    for pointer in graph["analytic_artifact_pointers"]:
        identity = _identity(
            _mapping(pointer, label="artifact pointer")["object_identity"],
            label="artifact pointer identity",
        )
        key = tuple(identity[name] for name in ("uri", "generation", "sha256", "bytes"))
        relationships.append(_relationship(
            authority_ids["CorpusTaskResult"],
            "REFERENCES_ARTIFACT",
            artifact_ids[key],
            {
                "role": pointer["role"],
                "strategy_id": pointer["strategy_id"],
            },
            task_index=0,
            slate_id=task_id,
        ))
    relationships.extend(
        _relationship(
            graph_entity_ids[str(edge["from"])],
            str(edge["type"]),
            graph_entity_ids[str(edge["to"])],
            _mapping(edge["properties"], label="validated graph edge properties"),
            task_index=0,
            slate_id=task_id,
        )
        for edge in graph["edges"]
    )

    nodes.sort(key=lambda row: str(row["id"]))
    relationships.sort(key=lambda row: str(row["edge_key"]))
    if len({str(row["id"]) for row in nodes}) != len(nodes):
        raise CorpusRetrievalNeo4jError("physical Neo4j node IDs repeat")
    if len({str(row["edge_key"]) for row in relationships}) != len(relationships):
        raise CorpusRetrievalNeo4jError("physical Neo4j relationship keys repeat")
    plan_body = {
        "schema_version": LOAD_SCHEMA,
        "run_id": run_id,
        "task_id": task_id,
        "terminal_receipt_identity": terminal_identity,
        "batch_completion_identity": completion_identity,
        "task_result_identity": task_result_identity,
        "graph_projection_identity": graph_identity,
        "nodes": nodes,
        "relationships": relationships,
    }
    return Neo4jLoadPlan(
        schema_version=LOAD_SCHEMA,
        run_id=run_id,
        task_id=task_id,
        terminal_receipt_identity=terminal_identity,
        batch_completion_identity=completion_identity,
        task_result_identity=task_result_identity,
        graph_projection_identity=graph_identity,
        nodes=tuple(nodes),
        relationships=tuple(relationships),
        plan_sha256=canonical_sha256(plan_body),
    )


def load_statements(plan: Neo4jLoadPlan) -> tuple[CypherStatement, ...]:
    """Return the two deterministic parameterized writes for ``plan``."""
    if not isinstance(plan, Neo4jLoadPlan) or plan.schema_version != LOAD_SCHEMA:
        raise CorpusRetrievalNeo4jError("load plan schema differs")
    return (
        CypherStatement("merge-nodes", NODE_UPSERT_CYPHER, plan.nodes),
        CypherStatement(
            "merge-relationships", RELATIONSHIP_UPSERT_CYPHER, plan.relationships
        ),
    )


def append_load_plan(
    plan: Neo4jLoadPlan,
    *,
    nodes: Sequence[Mapping[str, object]],
    relationships: Sequence[Mapping[str, object]],
) -> Neo4jLoadPlan:
    """Append a separately validated research namespace to a base plan.

    This is intentionally a structural combiner, not an evidence validator.
    Extension modules must validate their receipts before calling it.
    """
    if not isinstance(plan, Neo4jLoadPlan) or plan.schema_version != LOAD_SCHEMA:
        raise CorpusRetrievalNeo4jError("parent load plan schema differs")
    by_node_id: dict[str, dict[str, object]] = {}
    for raw_row in (*plan.nodes, *nodes):
        row = dict(raw_row)
        node_id = str(row.get("id", ""))
        if not node_id:
            raise CorpusRetrievalNeo4jError("appended plan node ID is empty")
        if type(row.get("source_bytes")) is not int or row["source_bytes"] < 1:
            raise CorpusRetrievalNeo4jError("appended node source bytes differ")
        task_present = row.get("task_index_present")
        task_index = row.get("task_index")
        slate_id = row.get("slate_id")
        if (
            type(task_present) is not bool
            or type(task_index) is not int
            or not isinstance(slate_id, str)
            or (
                task_present
                and (task_index < 0 or not slate_id)
            )
            or (
                not task_present
                and (task_index != -1 or slate_id)
            )
        ):
            raise CorpusRetrievalNeo4jError("appended node task grain differs")
        prior = by_node_id.get(node_id)
        if prior is not None and canonical_json_bytes(prior) != canonical_json_bytes(row):
            raise CorpusRetrievalNeo4jError("appended node identity conflicts")
        by_node_id[node_id] = row
    source_task_indexes: dict[tuple[object, ...], set[int]] = {}
    for row in by_node_id.values():
        if row["task_index_present"] is True:
            source_key = tuple(row[key] for key in (
                "source_uri", "source_generation", "source_sha256", "source_bytes"
            ))
            source_task_indexes.setdefault(source_key, set()).add(int(row["task_index"]))
    if any(len(indexes) > 1 for indexes in source_task_indexes.values()):
        raise CorpusRetrievalNeo4jError("retained object aliases across task indexes")

    by_edge_key: dict[str, dict[str, object]] = {}
    for raw_row in (*plan.relationships, *relationships):
        row = dict(raw_row)
        edge_key = str(row.get("edge_key", ""))
        if not edge_key:
            raise CorpusRetrievalNeo4jError("appended relationship key is empty")
        task_present = row.get("task_index_present")
        task_index = row.get("task_index")
        slate_id = row.get("slate_id")
        if (
            type(task_present) is not bool
            or type(task_index) is not int
            or not isinstance(slate_id, str)
            or (task_present and (task_index < 0 or not slate_id))
            or (not task_present and (task_index != -1 or slate_id))
        ):
            raise CorpusRetrievalNeo4jError("appended relationship task grain differs")
        prior = by_edge_key.get(edge_key)
        if prior is not None and canonical_json_bytes(prior) != canonical_json_bytes(row):
            raise CorpusRetrievalNeo4jError("appended relationship identity conflicts")
        by_edge_key[edge_key] = row
    combined_nodes = list(by_node_id.values())
    combined_relationships = list(by_edge_key.values())
    node_id_set = set(by_node_id)
    if any(
        row.get("from_id") not in node_id_set or row.get("to_id") not in node_id_set
        for row in combined_relationships
    ):
        raise CorpusRetrievalNeo4jError("appended relationship endpoint is absent")
    combined_nodes.sort(key=lambda row: str(row["id"]))
    combined_relationships.sort(key=lambda row: str(row["edge_key"]))
    body = {
        "schema_version": LOAD_SCHEMA,
        "run_id": plan.run_id,
        "task_id": plan.task_id,
        "terminal_receipt_identity": plan.terminal_receipt_identity,
        "batch_completion_identity": plan.batch_completion_identity,
        "task_result_identity": plan.task_result_identity,
        "graph_projection_identity": plan.graph_projection_identity,
        "nodes": combined_nodes,
        "relationships": combined_relationships,
    }
    return Neo4jLoadPlan(
        schema_version=LOAD_SCHEMA,
        run_id=plan.run_id,
        task_id=plan.task_id,
        terminal_receipt_identity=plan.terminal_receipt_identity,
        batch_completion_identity=plan.batch_completion_identity,
        task_result_identity=plan.task_result_identity,
        graph_projection_identity=plan.graph_projection_identity,
        nodes=tuple(combined_nodes),
        relationships=tuple(combined_relationships),
        plan_sha256=canonical_sha256(body),
    )


StatementRunner = Callable[[str, Mapping[str, object]], Mapping[str, object]]


def build_load_result_receipt(
    plan: Neo4jLoadPlan,
    *,
    database: str,
    node_count: int,
    relationship_count: int,
) -> dict[str, object]:
    """Build a deterministic, self-hashed receipt for an accepted graph load.

    Connection endpoints and credentials are deliberately outside this
    contract.  The receipt is canonical JSON suitable for a later create-once,
    generation-pinned GCS publication.
    """
    if not isinstance(plan, Neo4jLoadPlan) or plan.schema_version != LOAD_SCHEMA:
        raise CorpusRetrievalNeo4jError("load plan schema differs")
    database_name = _string(database, label="Neo4j database")
    if (
        type(node_count) is not int
        or type(relationship_count) is not int
        or node_count != len(plan.nodes)
        or relationship_count != len(plan.relationships)
    ):
        raise CorpusRetrievalNeo4jError("load-result counts differ from the plan")

    namespaces = sorted({
        str(row["workstream_namespace"]) for row in plan.nodes
    })
    namespace_node_counts = {
        namespace: sum(
            row["workstream_namespace"] == namespace for row in plan.nodes
        )
        for namespace in namespaces
    }
    task_indexes = sorted({
        int(row["task_index"])
        for row in plan.nodes
        if row["task_index_present"] is True
    })
    slate_ids = sorted({
        str(row["slate_id"])
        for row in plan.nodes
        if row["task_index_present"] is True
    })
    schema_hashes = [
        {
            "ordinal": ordinal,
            "sha256": sha256(statement.encode("utf-8")).hexdigest(),
        }
        for ordinal, statement in enumerate(SCHEMA_STATEMENTS)
    ]
    query_hashes = [
        {
            "name": statement.name,
            "sha256": sha256(statement.query.encode("utf-8")).hexdigest(),
        }
        for statement in load_statements(plan)
    ]
    body: dict[str, object] = {
        "schema_version": LOAD_RESULT_SCHEMA,
        "publication_mode": "create_once",
        "canonical_format": "canonical-json-v1",
        "generation_pinned_publication_required": True,
        "run_id": plan.run_id,
        "retrieval_task0_id": plan.task_id,
        "database": database_name,
        "plan_sha256": plan.plan_sha256,
        "schema_statement_sha256s": schema_hashes,
        "schema_catalog_sha256": canonical_sha256(schema_hashes),
        "load_query_sha256s": query_hashes,
        "load_query_catalog_sha256": canonical_sha256(query_hashes),
        "node_count": node_count,
        "relationship_count": relationship_count,
        "node_kind_counts": {
            kind: sum(row["kind"] == kind for row in plan.nodes)
            for kind in sorted({str(row["kind"]) for row in plan.nodes})
        },
        "relationship_type_counts": {
            relationship_type: sum(
                row["relationship_type"] == relationship_type
                for row in plan.relationships
            )
            for relationship_type in sorted({
                str(row["relationship_type"]) for row in plan.relationships
            })
        },
        "workstream_namespaces": namespaces,
        "namespace_node_counts": namespace_node_counts,
        "task_indexes": task_indexes,
        "slate_ids": slate_ids,
        "suite_scoped_node_count": sum(
            row["task_index_present"] is False for row in plan.nodes
        ),
        "idempotent": True,
        "authoritative_evidence_remains_generation_pinned_gcs": True,
        "world_matrices_stored_in_graph": False,
        "raw_outcomes_stored_in_graph": False,
        "authority_flags": {
            "automatic_policy_feedback": False,
            "corpus_fill_authority": False,
            "corpus_population_mutation_authority": False,
            "decision_authority": False,
            "historical_outcome_read_authority": False,
            "live_money_policy_authority": False,
            "production_default_change_authority": False,
            "production_policy_authority": False,
        },
    }
    body["load_result_sha256"] = canonical_sha256(body)
    return body


def apply_load_plan(
    plan: Neo4jLoadPlan,
    *,
    run_statement: StatementRunner,
    database: str,
) -> dict[str, object]:
    """Apply a plan through an injected transaction-bound statement runner."""
    counts: dict[str, int] = {}
    for statement in load_statements(plan):
        result = _mapping(
            run_statement(statement.query, {"rows": list(statement.rows)}),
            label=f"{statement.name} result",
        )
        expected = len(statement.rows)
        if (
            type(result.get("row_count")) is not int
            or type(result.get("accepted_count")) is not int
            or result["row_count"] != expected
            or result["accepted_count"] != expected
        ):
            raise CorpusRetrievalNeo4jError(
                f"{statement.name} immutable merge conflict or missing endpoint"
            )
        counts[statement.name] = expected
    return build_load_result_receipt(
        plan,
        database=database,
        node_count=counts["merge-nodes"],
        relationship_count=counts["merge-relationships"],
    )


def require_execute_gate(*, execute: bool, environ: Mapping[str, str]) -> None:
    if execute is not True or environ.get(ENABLE_ENV) != "1":
        raise CorpusRetrievalNeo4jError(
            f"live Neo4j execution requires literal --execute and {ENABLE_ENV}=1"
        )


__all__ = [
    "CorpusRetrievalNeo4jError",
    "CypherStatement",
    "ENABLE_ENV",
    "LOAD_SCHEMA",
    "LOAD_RESULT_SCHEMA",
    "NODE_UPSERT_CYPHER",
    "Neo4jLoadPlan",
    "RELATIONSHIP_UPSERT_CYPHER",
    "SCHEMA_STATEMENTS",
    "apply_load_plan",
    "append_load_plan",
    "build_load_plan",
    "build_load_result_receipt",
    "canonical_json_bytes",
    "canonical_sha256",
    "load_statements",
    "parse_canonical_json_bytes",
    "require_execute_gate",
]
