"""Offline Phase 4 fixture adapter for the Foundry graph-vNext contract.

This module deliberately has no Neo4j driver, filesystem reader, cloud
client, API router, or outcome adapter.  It accepts only exact four-part
object identities through an injected source protocol, validates explicitly
synthetic terminal receipts, projects them through the positive Phase 3 graph
schema, and emits bounded deterministic transaction descriptors.

The in-memory state machine is a contract oracle, not a database substitute.
It proves idempotent reload, conflict rejection, terminal census, and
canonical read-query hashes before any live graph or router seam is allowed.
The ``realized`` namespace remains completely closed.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import heapq
import json
import re
from typing import Final, Protocol

from nfl_dfs.research import corpus_graph_vnext_contracts as graph


FIXTURE_RECEIPT_SCHEMA: Final = "foundry-terminal-fixture-receipt/v1"
FIXTURE_ADAPTER_SCHEMA: Final = "foundry-graph-fixture-adapter/v1"
SCHEMA_CONTRACT_SCHEMA: Final = "foundry-graph-schema-contract/v1"
LOADER_CATALOG_SCHEMA: Final = "foundry-graph-loader-catalog/v1"
READ_QUERY_CATALOG_SCHEMA: Final = "foundry-graph-read-query-catalog/v1"
PROJECTION_MANIFEST_SCHEMA: Final = "foundry-graph-fixture-manifest/v1"
LOAD_TRANSACTION_SCHEMA: Final = "foundry-graph-load-transaction/v1"
STREAM_LOAD_PLAN_SCHEMA: Final = "foundry-graph-stream-load-plan/v1"
CHECKPOINT_RECEIPT_SCHEMA: Final = "foundry-graph-checkpoint-receipt/v1"
QUERY_RESULT_SCHEMA: Final = "foundry-graph-canonical-query-result/v1"
REBUILD_RECEIPT_SCHEMA: Final = "foundry-graph-zero-state-rebuild/v1"

FIXTURE_PUBLICATION_MODE: Final = "synthetic-fixture"
FIXTURE_GRAPH_RELEASE_ID: Final = "graph-release:fixture-phase4-001"
FIXTURE_CREATED_AT_UTC: Final = "2026-08-25T22:00:00Z"
FIXTURE_CHAINS: Final = ("t230", "core", "r6")

MAX_FIXTURE_RECEIPTS: Final = 8
MAX_RECEIPT_BYTES: Final = 64 * 1024
MAX_QUERY_ROWS: Final = 100
MAX_QUERY_DEADLINE_MS: Final = 2_000
MAX_QUERY_RESULT_BYTES: Final = 128 * 1024
MAX_TRANSACTION_BYTES: Final = 4 * 1024 * 1024
MAX_ADAPTER_SOURCE_URI_BYTES: Final = 512
MAX_NODE_ROWS_PER_RECEIPT: Final = 32
MAX_EDGE_ROWS_PER_RECEIPT: Final = 32
MAX_LOAD_DEADLINE_MS: Final = 2_000
SYNTHETIC_RECEIPT_URI_PREFIX: Final = "gs://synthetic-fixture.invalid/"

_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$")
_SHA: Final = re.compile(r"^[0-9a-f]{64}$")
_UTC: Final = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_PARAMETER: Final = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_WRITE_TOKEN: Final = re.compile(
    r"\b(?:CREATE|MERGE|SET|DELETE|DETACH|REMOVE|DROP|LOAD\s+CSV|FOREACH|CALL|APOC)\b",
    re.IGNORECASE,
)
_OUTCOME_TOKEN: Final = re.compile(
    r"(?:^|[:._/-])(?:actual|realized|outcome|winner|winning|payout|rank|"
    r"score|points)(?:$|[:._/-])",
    re.IGNORECASE,
)


class CorpusGraphFixtureAdapterError(ValueError):
    """Raised when the offline fixture adapter fails closed."""


def _fail(message: str) -> None:
    raise CorpusGraphFixtureAdapterError(message)


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusGraphFixtureAdapterError(
            "value is not finite canonical JSON"
        ) from exc


def _canonical_copy(value: object) -> object:
    return json.loads(_canonical_bytes(value).decode("utf-8"))


def _with_self_hash(body: Mapping[str, object], *, field: str) -> dict[str, object]:
    retained = dict(body)
    retained[field] = graph.canonical_sha256(retained)
    return retained


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> None:
    retained = dict(value)
    digest = retained.pop(field, None)
    if not isinstance(digest, str) or _SHA.fullmatch(digest) is None:
        _fail(f"{label} {field} is not 64-hex")
    if digest != graph.canonical_sha256(retained):
        _fail(f"{label} {field} differs from its canonical body")


def _exact_keys(
    value: Mapping[str, object], *, expected: set[str], label: str
) -> None:
    actual = set(value)
    if actual != expected:
        _fail(
            f"{label} keys differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _require_id(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        _fail(f"{label} is not a bounded canonical id")
    return value


def _require_utc(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        _fail(f"{label} is not second-precision UTC")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise CorpusGraphFixtureAdapterError(
            f"{label} is not a valid UTC timestamp"
        ) from exc
    return value


def _contains_outcome_semantics(value: str) -> bool:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    compact = re.sub(r"[^A-Za-z0-9]+", "", expanded).lower()
    return _OUTCOME_TOKEN.search(value) is not None or any(
        token in compact
        for token in (
            "actual", "realized", "outcome", "winner", "winning",
            "payout", "rank", "score", "points",
        )
    )


def _identity_key(identity: Mapping[str, object]) -> tuple[str, str, str, int]:
    retained = validate_object_identity(identity)
    return (
        str(retained["uri"]),
        str(retained["generation"]),
        str(retained["sha256"]),
        int(retained["bytes"]),
    )


def validate_object_identity(value: object) -> dict[str, object]:
    """Validate the exact immutable object identity used by fixture sources."""

    if not isinstance(value, Mapping):
        _fail("object identity is not a mapping")
    identity = dict(value)
    _exact_keys(
        identity, expected={"uri", "generation", "sha256", "bytes"},
        label="object identity",
    )
    uri = identity["uri"]
    if (
        not isinstance(uri, str)
        or not uri.startswith(SYNTHETIC_RECEIPT_URI_PREFIX)
        or len(uri.encode("utf-8")) > MAX_ADAPTER_SOURCE_URI_BYTES
        or any(character.isspace() or ord(character) < 32 for character in uri)
    ):
        _fail("object identity uri is not a bounded synthetic fixture uri")
    bucket, separator, object_name = uri[5:].partition("/")
    if not separator or not bucket or not object_name:
        _fail("object identity uri lacks a bucket or object path")
    generation = identity["generation"]
    if (
        not isinstance(generation, str)
        or not generation.isdigit()
        or len(generation) > 32
        or int(generation) <= 0
        or str(int(generation)) != generation
    ):
        _fail("object identity generation is not bounded positive digits")
    digest = identity["sha256"]
    if not isinstance(digest, str) or _SHA.fullmatch(digest) is None:
        _fail("object identity sha256 is not 64-hex")
    byte_count = identity["bytes"]
    if (
        not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or not 0 < byte_count <= MAX_RECEIPT_BYTES
    ):
        _fail("object identity bytes exceeds the fixture receipt bound")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": byte_count,
    }


@dataclass(frozen=True)
class ExactFixtureArtifact:
    identity: dict[str, object]
    raw: bytes


class ExactArtifactSource(Protocol):
    """Injected read seam; callers must request an exact four-part identity."""

    def read_exact(self, identity: Mapping[str, object]) -> bytes: ...


class InMemoryExactArtifactSource:
    """Deterministic synthetic source with no URI-only or latest fallback."""

    def __init__(self, artifacts: Sequence[ExactFixtureArtifact]) -> None:
        if not 0 < len(artifacts) <= MAX_FIXTURE_RECEIPTS:
            _fail("fixture source artifact count is outside its bound")
        retained: dict[tuple[str, str, str, int], bytes] = {}
        uri_generation: dict[tuple[str, str], tuple[str, str, str, int]] = {}
        for artifact in artifacts:
            identity = validate_object_identity(artifact.identity)
            if not isinstance(artifact.raw, (bytes, bytearray)):
                _fail("fixture artifact raw value is not bytes")
            raw = bytes(artifact.raw)
            if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
                _fail("fixture artifact raw bytes differ from exact identity")
            key = _identity_key(identity)
            locator = key[:2]
            if key in retained:
                _fail(f"duplicate fixture object identity {locator}")
            if locator in uri_generation:
                _fail(f"conflicting fixture object identity {locator}")
            retained[key] = raw
            uri_generation[locator] = key
        self._objects = retained

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        key = _identity_key(identity)
        raw = self._objects.get(key)
        if raw is None:
            _fail("exact fixture object identity is unavailable")
        if len(raw) != key[3] or sha256(raw).hexdigest() != key[2]:
            _fail("fixture source changed after registration")
        return bytes(raw)


def _read_exact_canonical_mapping(
    identity: Mapping[str, object], source: ExactArtifactSource, *, label: str,
) -> tuple[dict[str, object], dict[str, object], bytes]:
    """Read one bounded exact fixture artifact without URI/latest fallback."""

    retained_identity = validate_object_identity(identity)
    # ``validate_object_identity`` enforces MAX_RECEIPT_BYTES before this
    # injected seam is called.  Keep the explicit guard here so a future
    # refactor cannot accidentally move the bound after I/O.
    if int(retained_identity["bytes"]) > MAX_RECEIPT_BYTES:
        _fail(f"{label} identity exceeds the receipt bound before exact read")
    raw = source.read_exact(retained_identity)
    if not isinstance(raw, bytes):
        _fail(f"{label} exact source did not return immutable bytes")
    if (
        len(raw) != retained_identity["bytes"]
        or sha256(raw).hexdigest() != retained_identity["sha256"]
    ):
        _fail(f"{label} bytes differ from exact identity")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusGraphFixtureAdapterError(
            f"{label} is not canonical JSON"
        ) from exc
    if not isinstance(parsed, Mapping):
        _fail(f"{label} is not a mapping")
    retained = dict(parsed)
    if _canonical_bytes(retained) != raw:
        _fail(f"{label} bytes are not canonical JSON")
    return retained_identity, retained, raw


def _fixture_terminal_receipt(chain: str, ordinal: int) -> dict[str, object]:
    if chain not in FIXTURE_CHAINS:
        _fail("fixture chain is not registered")
    prefix = f"fixture:{chain}:v1"
    task_count = {"t230": 54, "core": 12, "r6": 6}[chain]
    entry_budget = {"t230": 80, "core": 14, "r6": 4}[chain]
    body: dict[str, object] = {
        "schema_version": FIXTURE_RECEIPT_SCHEMA,
        "publication_mode": FIXTURE_PUBLICATION_MODE,
        "receipt_id": f"receipt:{prefix}:terminal",
        "chain": chain,
        "terminal_state": "accepted-terminal",
        "accepted": True,
        "completed_at_utc": f"2026-08-25T22:0{ordinal}:00Z",
        "science_release_id": f"science:{prefix}",
        "verifier_release_id": f"verifier:{prefix}",
        "fill_preset_id": f"fill:{prefix}",
        "admission_preset_id": f"admission:{prefix}",
        "retrieval_preset_id": f"retrieval:{prefix}",
        "strategy_bundle_id": f"bundle:{prefix}",
        "experiment_run_id": f"run:{prefix}",
        "selected_book_id": f"book:{prefix}",
        "evaluation_id": f"evaluation:{prefix}",
        "promotion_decision_id": f"decision:{prefix}",
        "task_count": task_count,
        "accepted_task_count": task_count,
        "entry_budget": entry_budget,
        "uses_realized_outcomes": False,
        "outcome_release_id": None,
    }
    return _with_self_hash(body, field="terminal_payload_sha256")


def fixture_terminal_artifacts() -> tuple[ExactFixtureArtifact, ...]:
    """Return three unmistakably synthetic, exact terminal objects."""

    artifacts: list[ExactFixtureArtifact] = []
    for ordinal, chain in enumerate(FIXTURE_CHAINS, start=1):
        raw = _canonical_bytes(_fixture_terminal_receipt(chain, ordinal))
        artifacts.append(ExactFixtureArtifact(
            identity={
                "uri": (
                    f"gs://synthetic-fixture.invalid/foundry/terminal/"
                    f"{chain}-v1.json"
                ),
                "generation": str(1_788_000_000_000_000 + ordinal),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
            raw=raw,
        ))
    return tuple(artifacts)


_TERMINAL_KEYS: Final = {
    "schema_version", "publication_mode", "receipt_id", "chain",
    "terminal_state", "accepted", "completed_at_utc",
    "science_release_id", "verifier_release_id", "fill_preset_id",
    "admission_preset_id", "retrieval_preset_id", "strategy_bundle_id",
    "experiment_run_id", "selected_book_id", "evaluation_id",
    "promotion_decision_id", "task_count", "accepted_task_count",
    "entry_budget", "uses_realized_outcomes", "outcome_release_id",
    "terminal_payload_sha256",
}


def validate_terminal_fixture_receipt(
    raw: bytes, identity: Mapping[str, object]
) -> dict[str, object]:
    """Bind canonical synthetic receipt bytes to one exact object identity."""

    retained_identity = validate_object_identity(identity)
    if not isinstance(raw, bytes):
        _fail("terminal fixture raw value is not immutable bytes")
    if (
        not 0 < len(raw) <= MAX_RECEIPT_BYTES
        or len(raw) != retained_identity["bytes"]
        or sha256(raw).hexdigest() != retained_identity["sha256"]
    ):
        _fail("terminal fixture bytes differ from exact identity")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusGraphFixtureAdapterError(
            "terminal fixture is not canonical JSON"
        ) from exc
    if not isinstance(parsed, Mapping):
        _fail("terminal fixture is not a mapping")
    receipt = dict(parsed)
    if _canonical_bytes(receipt) != raw:
        _fail("terminal fixture bytes are not canonical JSON")
    _exact_keys(receipt, expected=_TERMINAL_KEYS, label="terminal fixture")
    _validate_self_hash(
        receipt, field="terminal_payload_sha256", label="terminal fixture"
    )
    if receipt["schema_version"] != FIXTURE_RECEIPT_SCHEMA:
        _fail("terminal fixture schema differs")
    if receipt["publication_mode"] != FIXTURE_PUBLICATION_MODE:
        _fail("terminal fixture is not explicitly synthetic")
    chain = receipt["chain"]
    if chain not in FIXTURE_CHAINS:
        _fail("terminal fixture chain is not registered")
    if receipt["terminal_state"] != "accepted-terminal" or receipt["accepted"] is not True:
        _fail("terminal fixture is not accepted and terminal")
    _require_utc(receipt["completed_at_utc"], label="completed_at_utc")
    id_fields = (
        "receipt_id", "science_release_id", "verifier_release_id",
        "fill_preset_id", "admission_preset_id", "retrieval_preset_id",
        "strategy_bundle_id", "experiment_run_id", "selected_book_id",
        "evaluation_id", "promotion_decision_id",
    )
    for field in id_fields:
        retained_id = _require_id(receipt[field], label=field)
        if "fixture" not in retained_id:
            _fail(f"{field} is not unmistakably fixture-named")
        if f":{chain}:" not in retained_id:
            _fail(f"{field} is not bound to terminal fixture chain {chain}")
        if _contains_outcome_semantics(retained_id):
            _fail(f"{field} contains outcome semantics closed offline")
    task_count = receipt["task_count"]
    accepted_count = receipt["accepted_task_count"]
    entry_budget = receipt["entry_budget"]
    for label, value, maximum in (
        ("task_count", task_count, 10_000),
        ("accepted_task_count", accepted_count, 10_000),
        ("entry_budget", entry_budget, 500),
    ):
        if (
            not isinstance(value, int) or isinstance(value, bool)
            or not 1 <= value <= maximum
        ):
            _fail(f"{label} is not a bounded positive integer")
    if accepted_count != task_count:
        _fail("terminal fixture accepted task count is incomplete")
    expected_task_count = {"t230": 54, "core": 12, "r6": 6}[str(chain)]
    expected_entry_budget = {"t230": 80, "core": 14, "r6": 4}[str(chain)]
    if task_count != expected_task_count or entry_budget != expected_entry_budget:
        _fail("terminal fixture chain-specific synthetic contract differs")
    if (
        receipt["uses_realized_outcomes"] is not False
        or receipt["outcome_release_id"] is not None
    ):
        _fail("terminal fixture attempts to open realized outcomes")
    return receipt


def _catalog_row(
    *, item_id: str, item_type: str, cypher: str
) -> dict[str, object]:
    body: dict[str, object] = {
        "item_id": item_id,
        "item_type": item_type,
        "cypher": " ".join(cypher.split()),
    }
    return {**body, "statement_sha256": graph.canonical_sha256(body)}


def schema_contract() -> dict[str, object]:
    """Return the frozen physical-label constraint/index migration catalog."""

    migrations = [
        _catalog_row(
            item_id="constraint-foundry-node-key-v1",
            item_type="constraint",
            cypher=(
                "CREATE CONSTRAINT foundry_node_key_v1 IF NOT EXISTS "
                "FOR (n:FoundryNode) REQUIRE n.node_key IS UNIQUE"
            ),
        ),
        _catalog_row(
            item_id="index-foundry-node-release-kind-v1",
            item_type="index",
            cypher=(
                "CREATE INDEX foundry_node_release_kind_v1 IF NOT EXISTS "
                "FOR (n:FoundryNode) ON (n.graph_release_id, n.kind)"
            ),
        ),
        _catalog_row(
            item_id="constraint-foundry-edge-key-v1",
            item_type="constraint",
            cypher=(
                "CREATE CONSTRAINT foundry_edge_key_v1 IF NOT EXISTS "
                "FOR ()-[r:FoundryRelation]-() REQUIRE r.edge_key IS UNIQUE"
            ),
        ),
        _catalog_row(
            item_id="index-foundry-edge-release-type-v1",
            item_type="index",
            cypher=(
                "CREATE INDEX foundry_edge_release_type_v1 IF NOT EXISTS "
                "FOR ()-[r:FoundryRelation]-() "
                "ON (r.graph_release_id, r.relationship)"
            ),
        ),
    ]
    body: dict[str, object] = {
        "schema_version": SCHEMA_CONTRACT_SCHEMA,
        "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
        "node_label": "FoundryNode",
        "relationship_type": "FoundryRelation",
        "migrations": migrations,
    }
    return _with_self_hash(body, field="schema_contract_sha256")


def validate_schema_contract(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("schema contract is not a mapping")
    retained = dict(value)
    _exact_keys(
        retained,
        expected={
            "schema_version", "graph_schema_version", "node_label",
            "relationship_type", "migrations", "schema_contract_sha256",
        },
        label="schema contract",
    )
    if retained != schema_contract():
        _fail("schema contract differs from the frozen migration catalog")
    return retained


def _loader_query(
    *, item_id: str, preflight_cypher: str, write_cypher: str,
    identity_constraint_id: str,
) -> dict[str, object]:
    """Freeze one rollback-capable future loader transaction contract."""

    body: dict[str, object] = {
        "item_id": item_id,
        "item_type": "loader-query",
        "parameters": ["rows"],
        "result_fields": [
            "input_count", "matched_count", "conflict_count",
            "missing_endpoint_count",
        ],
        "deadline_ms": MAX_LOAD_DEADLINE_MS,
        "identity_constraint_id": identity_constraint_id,
        "preflight_cypher": " ".join(preflight_cypher.split()),
        "write_cypher": " ".join(write_cypher.split()),
        "execution_contract": {
            "mode": "explicit-single-batch-write-transaction",
            "driver_deadline_required": True,
            "preflight_before_write_required": True,
            "exact_result_shape_required": True,
            "commit_only_after_exact_counts": True,
            "rollback_on_conflict_timeout_or_error": True,
            "transaction_identity": "loader_query_id+ordinal",
        },
    }
    return {**body, "statement_sha256": graph.canonical_sha256(body)}


def loader_query_catalog() -> dict[str, object]:
    """Return the only rollback-capable write protocols a loader may use.

    A future driver must run preflight and write inside one explicit
    transaction, compare the exact aggregate fields to its input, and commit
    only when both conflict counts and the edge missing-endpoint count are
    zero.  A timeout, Neo4j constraint error, result-shape difference, or
    count difference requires rollback.  The module intentionally does not
    include a live driver in Phase 4.
    """

    rows = [
        _loader_query(
            item_id="load-nodes-v1",
            identity_constraint_id="constraint-foundry-node-key-v1",
            preflight_cypher=(
                "UNWIND $rows AS row "
                "OPTIONAL MATCH (existing:FoundryNode {node_key: row.node_key}) "
                "WITH row, collect(existing) AS matches "
                "RETURN count(row) AS input_count, "
                "sum(size(matches)) AS matched_count, "
                "sum(CASE WHEN size(matches) > 1 OR any(n IN matches WHERE "
                "n.node_key IS NULL OR n.node_key <> row.node_key OR "
                "n.graph_release_id IS NULL OR "
                "n.graph_release_id <> row.graph_release_id OR "
                "n.node_id IS NULL OR n.node_id <> row.node_id OR "
                "n.kind IS NULL OR n.kind <> row.kind OR "
                "n.namespace IS NULL OR n.namespace <> row.namespace OR "
                "n.row_sha256 IS NULL OR "
                "n.row_sha256 <> row.row_sha256 OR "
                "size(keys(n)) <> 6 + size(keys(row.properties)) OR "
                "any(key IN keys(row.properties) WHERE n[key] IS NULL OR "
                "n[key] <> row.properties[key])) THEN 1 ELSE 0 END) "
                "AS conflict_count, 0 AS missing_endpoint_count"
            ),
            write_cypher=(
                "UNWIND $rows AS row "
                "MERGE (n:FoundryNode {node_key: row.node_key}) "
                "ON CREATE SET n.graph_release_id = row.graph_release_id, "
                "n.node_id = row.node_id, n.kind = row.kind, "
                "n.namespace = row.namespace, n.row_sha256 = row.row_sha256, "
                "n += row.properties "
                "WITH row, n "
                "RETURN count(row) AS input_count, count(n) AS matched_count, "
                "sum(CASE WHEN n.node_key IS NULL OR "
                "n.node_key <> row.node_key OR n.graph_release_id IS NULL OR "
                "n.graph_release_id <> row.graph_release_id OR "
                "n.node_id IS NULL OR n.node_id <> row.node_id OR "
                "n.kind IS NULL OR n.kind <> row.kind OR "
                "n.namespace IS NULL OR n.namespace <> row.namespace OR "
                "n.row_sha256 IS NULL OR "
                "n.row_sha256 <> row.row_sha256 OR "
                "size(keys(n)) <> 6 + size(keys(row.properties)) OR "
                "any(key IN keys(row.properties) WHERE n[key] IS NULL OR "
                "n[key] <> row.properties[key]) THEN 1 ELSE 0 END) "
                "AS conflict_count, 0 AS missing_endpoint_count"
            ),
        ),
        _loader_query(
            item_id="load-edges-v1",
            identity_constraint_id="constraint-foundry-edge-key-v1",
            preflight_cypher=(
                "UNWIND $rows AS row "
                "OPTIONAL MATCH ()-[existing:FoundryRelation "
                "{edge_key: row.edge_key}]->() "
                "OPTIONAL MATCH (s:FoundryNode {node_key: row.source_key}) "
                "OPTIONAL MATCH (t:FoundryNode {node_key: row.target_key}) "
                "WITH row, collect(DISTINCT existing) AS matches, "
                "collect(DISTINCT s) AS sources, collect(DISTINCT t) AS targets "
                "RETURN count(row) AS input_count, "
                "sum(size(matches)) AS matched_count, "
                "sum(CASE WHEN size(matches) > 1 OR any(r IN matches WHERE "
                "r.edge_key IS NULL OR r.edge_key <> row.edge_key OR "
                "startNode(r).node_key IS NULL OR "
                "startNode(r).node_key <> row.source_key OR "
                "endNode(r).node_key IS NULL OR "
                "endNode(r).node_key <> row.target_key OR "
                "r.graph_release_id IS NULL OR "
                "r.graph_release_id <> row.graph_release_id OR "
                "r.relationship IS NULL OR "
                "r.relationship <> row.relationship OR "
                "r.namespace IS NULL OR r.namespace <> row.namespace OR "
                "r.row_sha256 IS NULL OR "
                "r.row_sha256 <> row.row_sha256 OR "
                "size(keys(r)) <> 5 + size(keys(row.properties)) OR "
                "any(key IN keys(row.properties) WHERE r[key] IS NULL OR "
                "r[key] <> row.properties[key])) THEN 1 ELSE 0 END) "
                "AS conflict_count, "
                "sum(CASE WHEN size(sources) <> 1 OR size(targets) <> 1 "
                "THEN 1 ELSE 0 END) AS missing_endpoint_count"
            ),
            write_cypher=(
                "UNWIND $rows AS row "
                "MATCH (s:FoundryNode {node_key: row.source_key}) "
                "MATCH (t:FoundryNode {node_key: row.target_key}) "
                "MERGE (s)-[r:FoundryRelation {edge_key: row.edge_key}]->(t) "
                "ON CREATE SET r.graph_release_id = row.graph_release_id, "
                "r.relationship = row.relationship, "
                "r.namespace = row.namespace, r.row_sha256 = row.row_sha256, "
                "r += row.properties "
                "WITH row, s, t, r "
                "RETURN count(row) AS input_count, count(r) AS matched_count, "
                "sum(CASE WHEN r.edge_key IS NULL OR "
                "r.edge_key <> row.edge_key OR startNode(r).node_key IS NULL OR "
                "startNode(r).node_key <> row.source_key OR "
                "endNode(r).node_key IS NULL OR "
                "endNode(r).node_key <> row.target_key OR "
                "r.graph_release_id IS NULL OR "
                "r.graph_release_id <> row.graph_release_id OR "
                "r.relationship IS NULL OR "
                "r.relationship <> row.relationship OR "
                "r.namespace IS NULL OR r.namespace <> row.namespace OR "
                "r.row_sha256 IS NULL OR "
                "r.row_sha256 <> row.row_sha256 OR "
                "size(keys(r)) <> 5 + size(keys(row.properties)) OR "
                "any(key IN keys(row.properties) WHERE r[key] IS NULL OR "
                "r[key] <> row.properties[key]) THEN 1 ELSE 0 END) "
                "AS conflict_count, 0 AS missing_endpoint_count"
            ),
        ),
    ]
    body: dict[str, object] = {
        "schema_version": LOADER_CATALOG_SCHEMA,
        "queries": rows,
    }
    return _with_self_hash(body, field="loader_catalog_sha256")


def validate_loader_query_catalog(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("loader catalog is not a mapping")
    retained = dict(value)
    _exact_keys(
        retained,
        expected={"schema_version", "queries", "loader_catalog_sha256"},
        label="loader catalog",
    )
    _validate_self_hash(
        retained, field="loader_catalog_sha256", label="loader catalog"
    )
    queries = retained["queries"]
    if (
        isinstance(queries, (str, bytes))
        or not isinstance(queries, Sequence)
        or len(queries) != 2
    ):
        _fail("loader catalog queries differ from the bounded contract")
    for raw in queries:
        if not isinstance(raw, Mapping):
            _fail("loader query definition is not a mapping")
        item = dict(raw)
        _exact_keys(
            item,
            expected={
                "item_id", "item_type", "parameters", "result_fields",
                "deadline_ms", "identity_constraint_id",
                "preflight_cypher", "write_cypher", "execution_contract",
                "statement_sha256",
            },
            label="loader query definition",
        )
        _validate_self_hash(
            item, field="statement_sha256",
            label=f"loader query {item.get('item_id')}",
        )
        if (
            item["item_type"] != "loader-query"
            or item["parameters"] != ["rows"]
            or item["result_fields"] != [
                "input_count", "matched_count", "conflict_count",
                "missing_endpoint_count",
            ]
            or item["deadline_ms"] != MAX_LOAD_DEADLINE_MS
            or item["execution_contract"] != {
                "mode": "explicit-single-batch-write-transaction",
                "driver_deadline_required": True,
                "preflight_before_write_required": True,
                "exact_result_shape_required": True,
                "commit_only_after_exact_counts": True,
                "rollback_on_conflict_timeout_or_error": True,
                "transaction_identity": "loader_query_id+ordinal",
            }
        ):
            _fail("loader query execution contract differs")
        for field in ("preflight_cypher", "write_cypher"):
            cypher = item[field]
            if (
                not isinstance(cypher, str)
                or len(cypher.encode("utf-8")) > 8_192
                or not cypher.startswith("UNWIND $rows AS row ")
                or ";" in cypher
                or "conflict_count" not in cypher
                or "missing_endpoint_count" not in cypher
            ):
                _fail(f"loader query {field} is not bounded and observable")
            required_null_checks = (
                (
                    "n.node_key IS NULL OR",
                    "n.graph_release_id IS NULL OR",
                    "n.node_id IS NULL OR",
                    "n.kind IS NULL OR",
                    "n.namespace IS NULL OR",
                    "n.row_sha256 IS NULL OR",
                    "n[key] IS NULL OR",
                )
                if item["item_id"] == "load-nodes-v1"
                else (
                    "r.edge_key IS NULL OR",
                    "startNode(r).node_key IS NULL OR",
                    "endNode(r).node_key IS NULL OR",
                    "r.graph_release_id IS NULL OR",
                    "r.relationship IS NULL OR",
                    "r.namespace IS NULL OR",
                    "r.row_sha256 IS NULL OR",
                    "r[key] IS NULL OR",
                )
            )
            if any(fragment not in cypher for fragment in required_null_checks):
                _fail(f"loader query {field} conflict predicate is not null-safe")
    if retained != loader_query_catalog():
        _fail("loader catalog differs from its frozen allowlist")
    return retained


def _read_query(
    *, query_id: str, purpose: str, cypher: str,
    parameters: Sequence[str], result_fields: Sequence[str],
    max_rows: int = 50, deadline_ms: int = 1_000,
) -> dict[str, object]:
    body: dict[str, object] = {
        "query_id": query_id,
        "purpose": purpose,
        "cypher": " ".join(cypher.split()),
        "parameters": list(parameters),
        "result_fields": list(result_fields),
        "max_rows": max_rows,
        "deadline_ms": deadline_ms,
        "execution_contract": {
            "mode": "explicit-read-transaction",
            "driver_deadline_required": True,
            "deadline_ms": deadline_ms,
            "exact_parameter_set_required": True,
            "exact_result_fields_required": True,
            "rollback_on_timeout_or_schema_mismatch": True,
        },
    }
    return {**body, "query_sha256": graph.canonical_sha256(body)}


def _read_query_rows() -> list[dict[str, object]]:
    common = ("graph_release_id", "limit")
    return [
        _read_query(
            query_id="strategy-decomposition-v1",
            purpose="decompose one strategy bundle into fill, admission, and retrieval presets",
            parameters=(*common, "bundle_id"),
            result_fields=("bundle_id", "preset_id", "preset_kind", "relationship"),
            cypher=(
                "MATCH (b:FoundryNode {graph_release_id: $graph_release_id, "
                "node_id: $bundle_id, kind: 'StrategyBundle'})"
                "-[r:FoundryRelation {graph_release_id: $graph_release_id}]->"
                "(p:FoundryNode {graph_release_id: $graph_release_id}) "
                "WHERE p.kind IN ['FillPreset','AdmissionPreset','RetrievalPreset'] "
                "AND r.relationship IN ['DERIVED_FROM','ADMITTED_BY','SELECTED_BY'] "
                "RETURN b.node_id AS bundle_id, p.node_id AS preset_id, "
                "p.kind AS preset_kind, r.relationship AS relationship "
                "ORDER BY preset_kind, preset_id LIMIT $limit"
            ),
        ),
        _read_query(
            query_id="lineup-funnel-v1",
            purpose="trace one terminal run through its strategy bundle and selected book",
            parameters=(*common, "run_id"),
            result_fields=("run_id", "bundle_id", "book_id", "entry_budget"),
            cypher=(
                "MATCH (run:FoundryNode {graph_release_id: $graph_release_id, "
                "node_id: $run_id, kind: 'ExperimentRun'})"
                "-[e:FoundryRelation {graph_release_id: $graph_release_id}]->"
                "(bundle:FoundryNode {graph_release_id: $graph_release_id, "
                "kind: 'StrategyBundle'}) "
                "MATCH (book:FoundryNode {graph_release_id: $graph_release_id, "
                "kind: 'SelectedBook'})"
                "-[g:FoundryRelation {graph_release_id: $graph_release_id}]->"
                "(bundle) "
                "WHERE e.relationship = 'EVALUATES_BUNDLE' "
                "AND g.relationship = 'GENERATED_BY' "
                "RETURN run.node_id AS run_id, bundle.node_id AS bundle_id, "
                "book.node_id AS book_id, book.entry_budget AS entry_budget "
                "ORDER BY book_id LIMIT $limit"
            ),
        ),
        _read_query(
            query_id="release-lineage-v1",
            purpose="show bounded immediate lineage neighbors for one canonical identity",
            parameters=(*common, "anchor_id"),
            result_fields=("anchor_id", "neighbor_id", "neighbor_kind", "relationship", "direction"),
            cypher=(
                "MATCH (anchor:FoundryNode {graph_release_id: $graph_release_id, "
                "node_id: $anchor_id})-[r:FoundryRelation "
                "{graph_release_id: $graph_release_id}]-"
                "(neighbor:FoundryNode {graph_release_id: $graph_release_id}) "
                "WHERE r.namespace = 'lineage' "
                "RETURN anchor.node_id AS anchor_id, neighbor.node_id AS neighbor_id, "
                "neighbor.kind AS neighbor_kind, r.relationship AS relationship, "
                "CASE WHEN startNode(r) = anchor THEN 'out' ELSE 'in' END AS direction "
                "ORDER BY relationship, neighbor_id LIMIT $limit"
            ),
        ),
        _read_query(
            query_id="trait-enrichment-v1",
            purpose="list bounded structural traits attached to one fixture lineup",
            parameters=(*common, "lineup_id"),
            result_fields=("lineup_id", "trait_id", "trait_name", "trait_value"),
            cypher=(
                "MATCH (lineup:FoundryNode {graph_release_id: $graph_release_id, "
                "node_id: $lineup_id, kind: 'Lineup'})"
                "-[r:FoundryRelation {graph_release_id: $graph_release_id}]->"
                "(trait:FoundryNode {graph_release_id: $graph_release_id, "
                "kind: 'Trait'}) "
                "WHERE r.relationship = 'HAS_TRAIT' "
                "RETURN lineup.node_id AS lineup_id, trait.node_id AS trait_id, "
                "trait.name AS trait_name, r.trait_value AS trait_value "
                "ORDER BY trait_id LIMIT $limit"
            ),
        ),
        _read_query(
            query_id="cohort-compare-v1",
            purpose="list bounded prospective cohort membership for one fixture lineup",
            parameters=(*common, "lineup_id"),
            result_fields=("lineup_id", "cohort_id", "cohort_name", "membership_reason"),
            cypher=(
                "MATCH (lineup:FoundryNode {graph_release_id: $graph_release_id, "
                "node_id: $lineup_id, kind: 'Lineup'})"
                "-[r:FoundryRelation {graph_release_id: $graph_release_id}]->"
                "(cohort:FoundryNode {graph_release_id: $graph_release_id, "
                "kind: 'Cohort'}) "
                "WHERE r.relationship = 'MEMBER_OF_COHORT' "
                "RETURN lineup.node_id AS lineup_id, cohort.node_id AS cohort_id, "
                "cohort.name AS cohort_name, r.membership_reason AS membership_reason "
                "ORDER BY cohort_id LIMIT $limit"
            ),
        ),
        _read_query(
            query_id="matchup-exposure-v1",
            purpose="list qualified inferred defender exposure for one fixture player",
            parameters=(*common, "player_id"),
            result_fields=("player_id", "defender_id", "method_id", "confidence", "qualified_inferred"),
            cypher=(
                "MATCH (player:FoundryNode {graph_release_id: $graph_release_id, "
                "node_id: $player_id, kind: 'PlayerSlate'})"
                "-[r:FoundryRelation {graph_release_id: $graph_release_id}]->"
                "(defender:FoundryNode {graph_release_id: $graph_release_id, "
                "kind: 'PlayerSlate'}) "
                "WHERE r.relationship = 'HAS_INFERRED_DEFENDER_EXPOSURE' "
                "AND r.qualified_inferred = true "
                "RETURN player.node_id AS player_id, defender.node_id AS defender_id, "
                "r.method_id AS method_id, r.confidence AS confidence, "
                "r.qualified_inferred AS qualified_inferred "
                "ORDER BY defender_id LIMIT $limit"
            ),
        ),
        _read_query(
            query_id="lineup-network-v1",
            purpose="show a bounded one-hop lineup network without quadratic expansion",
            parameters=(*common, "lineup_id"),
            result_fields=("lineup_id", "neighbor_id", "neighbor_kind", "relationship", "direction"),
            cypher=(
                "MATCH (lineup:FoundryNode {graph_release_id: $graph_release_id, "
                "node_id: $lineup_id, kind: 'Lineup'})"
                "-[r:FoundryRelation {graph_release_id: $graph_release_id}]-"
                "(neighbor:FoundryNode {graph_release_id: $graph_release_id}) "
                "RETURN lineup.node_id AS lineup_id, neighbor.node_id AS neighbor_id, "
                "neighbor.kind AS neighbor_kind, r.relationship AS relationship, "
                "CASE WHEN startNode(r) = lineup THEN 'out' ELSE 'in' END AS direction "
                "ORDER BY relationship, neighbor_id LIMIT $limit"
            ),
        ),
        _read_query(
            query_id="source-quality-v1",
            purpose="project exact source identity and its accepted fixture receipt",
            parameters=common,
            result_fields=("artifact_id", "generation", "sha256", "bytes", "receipt_id"),
            cypher=(
                "MATCH (receipt:FoundryNode {graph_release_id: $graph_release_id, "
                "kind: 'VerificationReceipt'})"
                "-[r:FoundryRelation {graph_release_id: $graph_release_id}]->"
                "(artifact:FoundryNode {graph_release_id: $graph_release_id, "
                "kind: 'SourceArtifact'}) "
                "WHERE r.relationship = 'DERIVED_FROM' "
                "RETURN artifact.node_id AS artifact_id, "
                "artifact.generation AS generation, artifact.sha256 AS sha256, "
                "artifact.byte_count AS bytes, receipt.node_id AS receipt_id "
                "ORDER BY artifact_id LIMIT $limit"
            ),
        ),
        _read_query(
            query_id="promotion-evidence-gaps-v1",
            purpose="list fixture promotion decisions still withheld for evidence gaps",
            parameters=common,
            result_fields=("decision_id", "bundle_id", "disposition", "evidence_tier"),
            cypher=(
                "MATCH (decision:FoundryNode {graph_release_id: $graph_release_id, "
                "kind: 'PromotionDecision'})"
                "-[r:FoundryRelation {graph_release_id: $graph_release_id}]->"
                "(bundle:FoundryNode {graph_release_id: $graph_release_id, "
                "kind: 'StrategyBundle'}) "
                "WHERE r.relationship = 'DECIDES_ON_BUNDLE' "
                "AND decision.disposition <> 'approved' "
                "RETURN decision.node_id AS decision_id, bundle.node_id AS bundle_id, "
                "decision.disposition AS disposition, decision.evidence_tier AS evidence_tier "
                "ORDER BY decision_id LIMIT $limit"
            ),
        ),
        _read_query(
            query_id="terminal-census-v1",
            purpose="reconcile the bounded release census and expose any realized namespace contamination",
            parameters=common,
            result_fields=(
                "node_count", "edge_count", "property_count",
                "realized_node_count", "realized_edge_count",
            ),
            cypher=(
                "OPTIONAL MATCH (n:FoundryNode "
                "{graph_release_id: $graph_release_id}) "
                "WITH [item IN collect(n) WHERE item IS NOT NULL] AS nodes "
                "OPTIONAL MATCH (:FoundryNode "
                "{graph_release_id: $graph_release_id})"
                "-[r:FoundryRelation {graph_release_id: $graph_release_id}]->"
                "(:FoundryNode {graph_release_id: $graph_release_id}) "
                "WITH nodes, [item IN collect(r) WHERE item IS NOT NULL] "
                "AS relationships "
                "RETURN size(nodes) AS node_count, "
                "size(relationships) AS edge_count, "
                "reduce(total = 0, item IN nodes | total + size(keys(item)) - 6) + "
                "reduce(total = 0, item IN relationships | "
                "total + size(keys(item)) - 5) AS property_count, "
                "size([item IN nodes WHERE item.namespace = 'realized']) "
                "AS realized_node_count, "
                "size([item IN relationships WHERE item.namespace = 'realized']) "
                "AS realized_edge_count "
                "ORDER BY node_count LIMIT $limit"
            ),
        ),
    ]


def read_query_catalog() -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": READ_QUERY_CATALOG_SCHEMA,
        "queries": _read_query_rows(),
    }
    return _with_self_hash(body, field="query_catalog_sha256")


def validate_read_query_catalog(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("read query catalog is not a mapping")
    retained = dict(value)
    _exact_keys(
        retained,
        expected={"schema_version", "queries", "query_catalog_sha256"},
        label="read query catalog",
    )
    _validate_self_hash(
        retained, field="query_catalog_sha256", label="read query catalog"
    )
    queries = retained["queries"]
    if isinstance(queries, (str, bytes)) or not isinstance(queries, Sequence):
        _fail("read query catalog queries is not a bounded sequence")
    expected_ids = {row["query_id"] for row in _read_query_rows()}
    seen: set[str] = set()
    for raw in queries:
        if not isinstance(raw, Mapping):
            _fail("read query definition is not a mapping")
        item = dict(raw)
        _exact_keys(
            item,
            expected={
                "query_id", "purpose", "cypher", "parameters",
                "result_fields", "max_rows", "deadline_ms",
                "execution_contract", "query_sha256",
            },
            label="read query definition",
        )
        query_id = _require_id(item["query_id"], label="query_id")
        if query_id in seen:
            _fail("read query catalog contains a duplicate id")
        seen.add(query_id)
        cypher = item["cypher"]
        if (
            not isinstance(cypher, str)
            or len(cypher.encode("utf-8")) > 8_192
            or not cypher.startswith(("MATCH ", "OPTIONAL MATCH "))
            or " RETURN " not in cypher
            or " ORDER BY " not in cypher
            or not cypher.endswith("LIMIT $limit")
            or ";" in cypher
            or _WRITE_TOKEN.search(cypher) is not None
        ):
            _fail(f"read query {query_id} is not bounded and read-only")
        parameters = item["parameters"]
        fields = item["result_fields"]
        for label, values in (("parameters", parameters), ("result_fields", fields)):
            if (
                isinstance(values, (str, bytes))
                or not isinstance(values, Sequence)
                or not values
                or len(values) > 16
                or any(
                    not isinstance(value, str)
                    or _PARAMETER.fullmatch(value) is None
                    for value in values
                )
                or len(set(values)) != len(values)
            ):
                _fail(f"read query {query_id} {label} is not canonical")
        if set(parameters) < {"graph_release_id", "limit"}:
            _fail(f"read query {query_id} lacks release/limit parameters")
        for parameter in parameters:
            if f"${parameter}" not in cypher:
                _fail(f"read query {query_id} does not bind ${parameter}")
        max_rows = item["max_rows"]
        deadline = item["deadline_ms"]
        if (
            not isinstance(max_rows, int) or isinstance(max_rows, bool)
            or not 1 <= max_rows <= MAX_QUERY_ROWS
            or not isinstance(deadline, int) or isinstance(deadline, bool)
            or not 1 <= deadline <= MAX_QUERY_DEADLINE_MS
        ):
            _fail(f"read query {query_id} bounds are invalid")
        execution_contract = item["execution_contract"]
        if execution_contract != {
            "mode": "explicit-read-transaction",
            "driver_deadline_required": True,
            "deadline_ms": deadline,
            "exact_parameter_set_required": True,
            "exact_result_fields_required": True,
            "rollback_on_timeout_or_schema_mismatch": True,
        }:
            _fail(f"read query {query_id} execution contract differs")
        _validate_self_hash(item, field="query_sha256", label=f"query {query_id}")
    if seen != expected_ids or retained != read_query_catalog():
        _fail("read query catalog differs from its frozen allowlist")
    return retained


def validate_predecessor_identity(
    value: object,
) -> dict[str, object] | None:
    """Validate the exact four-part object identity of a rebuild receipt."""

    if value is None:
        return None
    return validate_object_identity(value)


def prepare_projection_manifest(
    *, terminal_receipts: Sequence[Mapping[str, object]],
    graph_release_id: str = FIXTURE_GRAPH_RELEASE_ID,
    predecessor_receipt_identity: Mapping[str, object] | None = None,
    predecessor_source: ExactArtifactSource | None = None,
    created_at_utc: str = FIXTURE_CREATED_AT_UTC,
) -> dict[str, object]:
    """Bind exact terminal objects to all versioned offline graph contracts."""

    if not 0 < len(terminal_receipts) <= MAX_FIXTURE_RECEIPTS:
        _fail("projection terminal receipt count is outside its bound")
    identities = [validate_object_identity(item) for item in terminal_receipts]
    identities.sort(key=_identity_key)
    if len({_identity_key(item) for item in identities}) != len(identities):
        _fail("projection contains a duplicate terminal identity")
    predecessor = validate_predecessor_identity(predecessor_receipt_identity)
    if (predecessor is None) != (predecessor_source is None):
        _fail("predecessor exact identity and source must be supplied together")
    predecessor_receipt = (
        read_rebuild_receipt(predecessor, predecessor_source)
        if predecessor is not None and predecessor_source is not None
        else None
    )
    retained_release_id = _require_id(
        graph_release_id, label="graph_release_id"
    )
    predecessor_release_id = (
        str(predecessor_receipt["graph_release_id"])
        if predecessor_receipt is not None else None
    )
    if predecessor_release_id == retained_release_id:
        _fail("predecessor graph release cannot equal the new release")
    manifest = graph.validate_load_manifest({
        "schema_version": graph.LOAD_MANIFEST_SCHEMA,
        "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
        "graph_release_id": retained_release_id,
        "predecessor_graph_release_id": predecessor_release_id,
        "allowed_namespaces": sorted(graph.OFFLINE_ALLOWED_NAMESPACES),
        "source_releases": identities,
        "authorized_outcome_release_id": None,
        "created_at_utc": _require_utc(created_at_utc, label="created_at_utc"),
    })
    body: dict[str, object] = {
        "schema_version": PROJECTION_MANIFEST_SCHEMA,
        "publication_mode": FIXTURE_PUBLICATION_MODE,
        "adapter_schema_version": FIXTURE_ADAPTER_SCHEMA,
        "graph_load_manifest": manifest,
        "predecessor_receipt_identity": predecessor,
        "schema_contract_sha256": schema_contract()["schema_contract_sha256"],
        "loader_catalog_sha256": loader_query_catalog()["loader_catalog_sha256"],
        "query_catalog_sha256": read_query_catalog()["query_catalog_sha256"],
        "terminal_receipts": identities,
        "outcome_scope": "closed",
    }
    return _with_self_hash(body, field="projection_manifest_sha256")


def validate_projection_manifest(
    value: object, *, predecessor_source: ExactArtifactSource | None = None,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("projection manifest is not a mapping")
    retained = dict(value)
    _exact_keys(
        retained,
        expected={
            "schema_version", "publication_mode", "adapter_schema_version",
            "graph_load_manifest", "predecessor_receipt_identity",
            "schema_contract_sha256",
            "loader_catalog_sha256", "query_catalog_sha256",
            "terminal_receipts", "outcome_scope", "projection_manifest_sha256",
        },
        label="projection manifest",
    )
    _validate_self_hash(
        retained, field="projection_manifest_sha256", label="projection manifest"
    )
    if (
        retained["schema_version"] != PROJECTION_MANIFEST_SCHEMA
        or retained["publication_mode"] != FIXTURE_PUBLICATION_MODE
        or retained["adapter_schema_version"] != FIXTURE_ADAPTER_SCHEMA
        or retained["outcome_scope"] != "closed"
    ):
        _fail("projection manifest schema, mode, or outcome scope differs")
    if retained["schema_contract_sha256"] != schema_contract()["schema_contract_sha256"]:
        _fail("projection manifest schema contract differs")
    if retained["loader_catalog_sha256"] != loader_query_catalog()["loader_catalog_sha256"]:
        _fail("projection manifest loader catalog differs")
    if retained["query_catalog_sha256"] != read_query_catalog()["query_catalog_sha256"]:
        _fail("projection manifest read query catalog differs")
    graph_manifest = graph.validate_load_manifest(retained["graph_load_manifest"])
    if retained["graph_load_manifest"] != graph_manifest:
        _fail("projection graph load manifest is not canonical")
    predecessor = validate_predecessor_identity(
        retained["predecessor_receipt_identity"]
    )
    if retained["predecessor_receipt_identity"] != predecessor:
        _fail("projection predecessor identity is not canonical")
    if predecessor is not None and predecessor_source is None:
        _fail("predecessor receipt requires its exact-read source")
    if predecessor is None and predecessor_source is not None:
        _fail("predecessor source was supplied without an exact identity")
    predecessor_receipt = (
        read_rebuild_receipt(predecessor, predecessor_source)
        if predecessor is not None and predecessor_source is not None
        else None
    )
    predecessor_release_id = (
        predecessor_receipt["graph_release_id"]
        if predecessor_receipt is not None else None
    )
    if graph_manifest["predecessor_graph_release_id"] != predecessor_release_id:
        _fail("projection predecessor identity differs from graph manifest")
    if predecessor_release_id == graph_manifest["graph_release_id"]:
        _fail("projection predecessor release equals the new release")
    terminal = retained["terminal_receipts"]
    if isinstance(terminal, (str, bytes)) or not isinstance(terminal, Sequence):
        _fail("projection terminal receipts is not a sequence")
    identities = [validate_object_identity(item) for item in terminal]
    if identities != sorted(identities, key=_identity_key):
        _fail("projection terminal receipts are not canonical")
    if identities != graph_manifest["source_releases"]:
        _fail("projection terminal receipts differ from graph source releases")
    if graph_manifest["authorized_outcome_release_id"] is not None:
        _fail("projection manifest attempts to authorize outcomes")
    return retained


def canonical_fixture_projection() -> tuple[
    dict[str, object], InMemoryExactArtifactSource
]:
    artifacts = fixture_terminal_artifacts()
    source = InMemoryExactArtifactSource(artifacts)
    manifest = prepare_projection_manifest(
        terminal_receipts=[artifact.identity for artifact in reversed(artifacts)]
    )
    return manifest, source


def read_terminal_fixtures(
    manifest: Mapping[str, object], source: ExactArtifactSource, *,
    predecessor_source: ExactArtifactSource | None = None,
) -> tuple[tuple[dict[str, object], dict[str, object]], ...]:
    retained = validate_projection_manifest(
        manifest, predecessor_source=predecessor_source
    )
    rows: list[tuple[dict[str, object], dict[str, object]]] = []
    chains: set[str] = set()
    receipt_ids: set[str] = set()
    for raw_identity in retained["terminal_receipts"]:
        identity, _, raw = _read_exact_canonical_mapping(
            raw_identity, source, label="terminal fixture"
        )
        receipt = validate_terminal_fixture_receipt(raw, identity)
        chain = str(receipt["chain"])
        receipt_id = str(receipt["receipt_id"])
        if chain in chains or receipt_id in receipt_ids:
            _fail("terminal fixture chain or receipt identity is duplicated")
        chains.add(chain)
        receipt_ids.add(receipt_id)
        rows.append((identity, receipt))
    rows.sort(key=lambda item: (str(item[1]["chain"]), _identity_key(item[0])))
    return tuple(rows)


def _node(
    kind: str, node_id: str, namespace: str, properties: Mapping[str, object]
) -> dict[str, object]:
    return graph.validate_node_row({
        "kind": kind,
        "node_id": node_id,
        "namespace": namespace,
        "properties": dict(properties),
    })


def _edge(
    relationship: str, source_id: str, target_id: str, namespace: str,
    properties: Mapping[str, object] | None = None,
) -> dict[str, object]:
    validated = graph.validate_edge_row({
        "relationship": relationship,
        "source_id": source_id,
        "target_id": target_id,
        "namespace": namespace,
        "properties": dict(properties or {}),
    })
    return {
        "relationship": validated["relationship"],
        "source_id": validated["source_id"],
        "target_id": validated["target_id"],
        "namespace": validated["namespace"],
        "properties": validated["properties"],
    }


def _logical_edge_key(row: Mapping[str, object]) -> str:
    return (
        f"{row['namespace']}|{row['source_id']}|"
        f"{row['relationship']}|{row['target_id']}"
    )


def _receipt_graph_rows(
    identity: Mapping[str, object], receipt: Mapping[str, object]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    chain = str(receipt["chain"])
    source_id = f"source:fixture:{chain}:terminal"
    receipt_id = str(receipt["receipt_id"])
    science_id = str(receipt["science_release_id"])
    verifier_id = str(receipt["verifier_release_id"])
    fill_id = str(receipt["fill_preset_id"])
    admission_id = str(receipt["admission_preset_id"])
    retrieval_id = str(receipt["retrieval_preset_id"])
    bundle_id = str(receipt["strategy_bundle_id"])
    run_id = str(receipt["experiment_run_id"])
    book_id = str(receipt["selected_book_id"])
    evaluation_id = str(receipt["evaluation_id"])
    decision_id = str(receipt["promotion_decision_id"])
    fold_id = f"fold:fixture:{chain}:heldout"
    metric_id = f"metric:fixture:{chain}:simulated-tail-index"
    trait_id = f"trait:fixture:{chain}:structural-stack"
    cohort_id = f"cohort:fixture:{chain}:prospective-structure"
    lineup_id = f"lineup:fixture:{chain}:001"
    player_id = f"player:fixture:{chain}:wr1"
    defender_id = f"player:fixture:{chain}:cb1"
    completed = str(receipt["completed_at_utc"])
    code_hash = sha256(f"fixture-code:{chain}:v1".encode()).hexdigest()
    roster_hash = sha256(f"fixture-roster:{chain}:001".encode()).hexdigest()
    task_count = int(receipt["task_count"])
    entry_budget = int(receipt["entry_budget"])

    nodes = [
        _node("SourceArtifact", source_id, "lineage", {
            "artifact_id": source_id, "uri": identity["uri"],
            "generation": identity["generation"], "sha256": identity["sha256"],
            "byte_count": identity["bytes"], "schema_version": FIXTURE_RECEIPT_SCHEMA,
        }),
        _node("VerificationReceipt", receipt_id, "lineage", {
            "receipt_id": receipt_id, "schema_version": FIXTURE_RECEIPT_SCHEMA,
            "sha256": receipt["terminal_payload_sha256"], "accepted": True,
            "verified_at_utc": completed,
        }),
        _node("ScienceRelease", science_id, "lineage", {
            "release_id": science_id, "schema_version": "fixture-science/v1",
            "code_sha256": code_hash, "accepted": True,
        }),
        _node("VerifierRelease", verifier_id, "lineage", {
            "release_id": verifier_id, "schema_version": "fixture-verifier/v1",
            "code_sha256": code_hash, "accepted": True,
        }),
        _node("FillPreset", fill_id, "identity", {
            "preset_id": fill_id, "version": "v1-fixture",
            "name": f"{chain} synthetic fill",
            "description": "offline terminal fixture; no governed lineup was read",
        }),
        _node("AdmissionPreset", admission_id, "identity", {
            "preset_id": admission_id, "version": "v1-fixture",
            "name": f"{chain} synthetic admission",
            "description": "offline terminal fixture admission contract",
        }),
        _node("RetrievalPreset", retrieval_id, "identity", {
            "preset_id": retrieval_id, "version": "v1-fixture",
            "name": f"{chain} synthetic retrieval",
            "description": "offline prospective retrieval fixture without outcomes",
        }),
        _node("StrategyBundle", bundle_id, "identity", {
            "bundle_id": bundle_id, "version": "v1-fixture",
            "entry_budget": entry_budget, "fill_preset_id": fill_id,
            "admission_preset_id": admission_id,
            "retrieval_preset_id": retrieval_id,
        }),
        _node("ExperimentRun", run_id, "identity", {
            "run_id": run_id, "status": "accepted",
            "started_at_utc": completed, "completed_at_utc": completed,
            "task_count": task_count, "accepted_task_count": task_count,
        }),
        _node("SelectedBook", book_id, "membership", {
            "book_id": book_id, "entry_budget": entry_budget,
            "selected_count": 1, "retrieval_preset_id": retrieval_id,
        }),
        _node("Evaluation", evaluation_id, "metric", {
            "evaluation_id": evaluation_id, "scope": "simulated",
            "evidence_tier": FIXTURE_PUBLICATION_MODE, "fold_id": fold_id,
            "denominator": task_count, "missing": 0,
        }),
        _node("Fold", fold_id, "identity", {
            "fold_id": fold_id, "training_blocks": ["fixture-prior-block"],
            "heldout_block": "fixture-heldout-block",
        }),
        _node("MetricSet", metric_id, "metric", {
            "metric_set_id": metric_id, "definition_id": "simulated-tail-index",
            "scope": "simulated", "value": 0.5, "support": task_count,
            "missing": 0, "uncertainty_lower": 0.4, "uncertainty_upper": 0.6,
        }),
        _node("Trait", trait_id, "trait", {
            "trait_id": trait_id, "definition_version": "v1-fixture",
            "name": "synthetic structural stack", "evidence_class": "inferred-fixture",
        }),
        _node("Cohort", cohort_id, "trait", {
            "cohort_id": cohort_id, "definition_version": "v1-fixture",
            "name": "synthetic prospective structure", "denominator": 1,
            "missing": 0,
        }),
        _node("Lineup", lineup_id, "membership", {
            "roster_hash": roster_hash, "salary": 49_500,
            "legal": True, "ordinal": 0,
        }),
        _node("PlayerSlate", player_id, "identity", {
            "player_id": player_id, "display_name": "Fixture Receiver",
            "position": "WR", "team": "FXA", "opponent": "FXB",
            "salary": 7_000, "status": "synthetic", "role": "primary",
            "alignment": "wide", "source_release_id": science_id,
        }),
        _node("PlayerSlate", defender_id, "identity", {
            "player_id": defender_id, "display_name": "Fixture Defender",
            "position": "CB", "team": "FXB", "opponent": "FXA",
            "salary": 3_000, "status": "synthetic", "role": "coverage",
            "alignment": "wide", "source_release_id": science_id,
        }),
        _node("PromotionDecision", decision_id, "identity", {
            "decision_id": decision_id, "disposition": "withheld-evidence-gap",
            "decided_at_utc": completed, "evidence_tier": FIXTURE_PUBLICATION_MODE,
        }),
    ]
    edges = [
        _edge("DERIVED_FROM", receipt_id, source_id, "lineage"),
        _edge("USES_SOURCE", science_id, source_id, "lineage"),
        _edge("USES_SOURCE", verifier_id, source_id, "lineage"),
        _edge("DERIVED_FROM", bundle_id, fill_id, "lineage"),
        _edge("ADMITTED_BY", bundle_id, admission_id, "membership"),
        _edge("SELECTED_BY", bundle_id, retrieval_id, "membership"),
        _edge("EVALUATES_BUNDLE", run_id, bundle_id, "metric"),
        _edge("HAS_METRIC", run_id, metric_id, "metric", {
            "definition_id": "simulated-tail-index",
        }),
        _edge("EVALUATED_IN", evaluation_id, run_id, "metric"),
        _edge("EVALUATED_IN", evaluation_id, fold_id, "metric"),
        _edge("GENERATED_BY", book_id, bundle_id, "lineage"),
        _edge("SELECTED_BY", book_id, retrieval_id, "membership"),
        _edge("MEMBER_OF_BOOK", lineup_id, book_id, "membership", {"ordinal": 0}),
        _edge("CONTAINS_PLAYER", lineup_id, player_id, "membership", {
            "roster_slot": "WR1", "ordinal": 0,
        }),
        _edge("HAS_TRAIT", lineup_id, trait_id, "trait", {
            "trait_value": 1.0, "definition_version": "v1-fixture",
            "evidence_class": "inferred-fixture",
        }),
        _edge("MEMBER_OF_COHORT", lineup_id, cohort_id, "trait", {
            "membership_reason": "synthetic prospective structural fixture",
        }),
        _edge("HAS_INFERRED_DEFENDER_EXPOSURE", player_id, defender_id, "trait", {
            "qualified_inferred": True, "method_id": "fixture-coverage-map-v1",
            "confidence": 0.6, "exposure_share": 0.5,
            "source_release_id": science_id,
        }),
        _edge("DECIDES_ON_BUNDLE", decision_id, bundle_id, "lineage"),
    ]
    if (
        len(nodes) > MAX_NODE_ROWS_PER_RECEIPT
        or len(edges) > MAX_EDGE_ROWS_PER_RECEIPT
    ):
        _fail("terminal adapter shard exceeds its fixed summary-only bound")
    return nodes, edges


def _revalidate_bound_terminal(
    identity: Mapping[str, object], receipt: Mapping[str, object]
) -> tuple[dict[str, object], dict[str, object]]:
    retained_identity = validate_object_identity(identity)
    retained_receipt = validate_terminal_fixture_receipt(
        _canonical_bytes(dict(receipt)), retained_identity
    )
    return retained_identity, retained_receipt


def project_fixture_rows(
    terminal: Sequence[tuple[Mapping[str, object], Mapping[str, object]]]
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    if not 0 < len(terminal) <= MAX_FIXTURE_RECEIPTS:
        _fail("terminal fixture projection count is outside its bound")
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    for identity, receipt in terminal:
        if not isinstance(receipt, Mapping):
            _fail("terminal fixture projection receipt is not a mapping")
        retained_identity, retained_receipt = _revalidate_bound_terminal(
            identity, receipt
        )
        receipt_nodes, receipt_edges = _receipt_graph_rows(
            retained_identity, retained_receipt
        )
        nodes.extend(receipt_nodes)
        edges.extend(receipt_edges)
    return tuple(nodes), tuple(edges)


def _fixture_row_shard(
    identity: Mapping[str, object], receipt: Mapping[str, object], *, unwind: str
) -> Iterator[dict[str, object]]:
    """Yield one exact terminal receipt's small, declared sorted shard."""

    retained_identity, retained_receipt = _revalidate_bound_terminal(
        identity, receipt
    )
    nodes, edges = _receipt_graph_rows(retained_identity, retained_receipt)
    if unwind == "nodes":
        rows = sorted(
            nodes, key=lambda row: (str(row["kind"]), str(row["node_id"]))
        )
    elif unwind == "edges":
        rows = sorted(edges, key=_logical_edge_key)
    else:  # pragma: no cover - module-owned call sites use two literals.
        _fail("fixture row shard kind is unknown")
    yield from rows


def _iter_sorted_fixture_rows(
    terminal: Sequence[tuple[Mapping[str, object], Mapping[str, object]]],
    *, unwind: str,
) -> Iterator[dict[str, object]]:
    """Merge bounded receipt shards without sorting/materializing the full graph."""

    if not 0 < len(terminal) <= MAX_FIXTURE_RECEIPTS:
        _fail("fixture row stream terminal count is outside its bound")
    if unwind == "nodes":
        key = lambda row: (str(row["kind"]), str(row["node_id"]))
    elif unwind == "edges":
        key = _logical_edge_key
    else:
        _fail("fixture row stream kind is unknown")
    shards = (
        _fixture_row_shard(identity, receipt, unwind=unwind)
        for identity, receipt in terminal
    )
    previous: object | None = None
    first = True
    for row in heapq.merge(*shards, key=key):
        retained_key = key(row)
        if not first and retained_key <= previous:  # type: ignore[operator]
            _fail("fixture row stream is duplicate or nonmonotonic")
        first = False
        previous = retained_key
        yield row


def _bounded_batches(
    rows: Iterator[dict[str, object]],
) -> Iterator[tuple[dict[str, object], ...]]:
    batch: list[dict[str, object]] = []
    for row in rows:
        batch.append(row)
        if len(batch) == graph.BATCH_SIZE:
            yield tuple(batch)
            batch = []
    if batch:
        yield tuple(batch)


def _physical_node(row: Mapping[str, object], graph_release_id: str) -> dict[str, object]:
    logical = graph.validate_node_row(row)
    node_id = str(logical["node_id"])
    body = {
        "graph_release_id": graph_release_id,
        "node_key": f"{graph_release_id}|{node_id}",
        "kind": logical["kind"], "node_id": node_id,
        "namespace": logical["namespace"], "properties": logical["properties"],
        "row_sha256": graph.canonical_sha256(logical),
    }
    return body


def _physical_edge(row: Mapping[str, object], graph_release_id: str) -> dict[str, object]:
    logical = graph.validate_edge_row(row)
    source = str(logical["source_id"])
    target = str(logical["target_id"])
    logical_edge_key = str(logical["edge_key"])
    return {
        "graph_release_id": graph_release_id,
        "edge_key": f"{graph_release_id}|{logical_edge_key}",
        "source_key": f"{graph_release_id}|{source}",
        "target_key": f"{graph_release_id}|{target}",
        "relationship": logical["relationship"],
        "source_id": source, "target_id": target,
        "namespace": logical["namespace"], "properties": logical["properties"],
        "row_sha256": graph.canonical_sha256(logical),
    }


def build_load_transaction(
    *, projection_manifest: Mapping[str, object], loader_query_id: str,
    ordinal: int, logical_rows: Sequence[Mapping[str, object]],
    predecessor_source: ExactArtifactSource | None = None,
) -> dict[str, object]:
    """Build one bounded transaction descriptor from validated logical rows."""

    manifest = validate_projection_manifest(
        projection_manifest, predecessor_source=predecessor_source
    )
    graph_manifest = manifest["graph_load_manifest"]
    graph_release_id = str(graph_manifest["graph_release_id"])
    allowed_namespaces = set(graph_manifest["allowed_namespaces"])
    if loader_query_id not in {"load-nodes-v1", "load-edges-v1"}:
        _fail("load transaction query is not allowlisted")
    if (
        not isinstance(ordinal, int) or isinstance(ordinal, bool)
        or not 0 <= ordinal < graph.MAX_TOTAL_BATCHES
    ):
        _fail("load transaction ordinal is outside its bound")
    if (
        isinstance(logical_rows, (str, bytes))
        or not isinstance(logical_rows, Sequence)
        or not 0 < len(logical_rows) <= graph.BATCH_SIZE
    ):
        _fail("load transaction rows exceed the batch bound")
    if loader_query_id == "load-nodes-v1":
        rows = [_physical_node(row, graph_release_id) for row in logical_rows]
        rows.sort(key=lambda row: (str(row["kind"]), str(row["node_id"])))
        identity_keys = [str(row["node_key"]) for row in rows]
    else:
        rows = [_physical_edge(row, graph_release_id) for row in logical_rows]
        rows.sort(key=lambda row: str(row["edge_key"]))
        identity_keys = [str(row["edge_key"]) for row in rows]
    for row in rows:
        if row["namespace"] not in allowed_namespaces:
            _fail(
                f"load transaction namespace {row['namespace']!r} is outside "
                "the projection manifest"
            )
    if len(identity_keys) != len(set(identity_keys)):
        _fail("load transaction contains a duplicate logical identity")
    batch_sha = graph.canonical_sha256(rows)
    body: dict[str, object] = {
        "schema_version": LOAD_TRANSACTION_SCHEMA,
        "graph_release_id": graph_release_id,
        "projection_manifest_sha256": manifest["projection_manifest_sha256"],
        "schema_contract_sha256": manifest["schema_contract_sha256"],
        "loader_catalog_sha256": manifest["loader_catalog_sha256"],
        "loader_query_id": loader_query_id,
        "ordinal": ordinal,
        "row_count": len(rows),
        "batch_sha256": batch_sha,
        # Stable across content: a changed batch at the same query/ordinal
        # must collide with the prior transaction identity and fail closed.
        "batch_id": f"{loader_query_id}:{ordinal}",
        "rows": rows,
    }
    retained = _with_self_hash(body, field="transaction_sha256")
    if len(_canonical_bytes(retained)) > MAX_TRANSACTION_BYTES:
        _fail("load transaction exceeds its serialized byte bound")
    return retained


def validate_load_transaction(
    value: object, projection_manifest: Mapping[str, object], *,
    predecessor_source: ExactArtifactSource | None = None,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("load transaction is not a mapping")
    item = dict(value)
    _exact_keys(
        item,
        expected={
            "schema_version", "graph_release_id", "projection_manifest_sha256",
            "schema_contract_sha256", "loader_catalog_sha256",
            "loader_query_id", "ordinal", "row_count", "batch_sha256",
            "batch_id", "rows", "transaction_sha256",
        },
        label="load transaction",
    )
    _validate_self_hash(item, field="transaction_sha256", label="load transaction")
    manifest = validate_projection_manifest(
        projection_manifest, predecessor_source=predecessor_source
    )
    if (
        item["schema_version"] != LOAD_TRANSACTION_SCHEMA
        or item["graph_release_id"]
        != manifest["graph_load_manifest"]["graph_release_id"]
        or item["projection_manifest_sha256"]
        != manifest["projection_manifest_sha256"]
        or item["schema_contract_sha256"] != manifest["schema_contract_sha256"]
        or item["loader_catalog_sha256"] != manifest["loader_catalog_sha256"]
    ):
        _fail("load transaction release or contract binding differs")
    query_id = item["loader_query_id"]
    rows = item["rows"]
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        _fail("load transaction rows is not a sequence")
    rebuilt = build_load_transaction(
        projection_manifest=manifest,
        loader_query_id=str(query_id),
        ordinal=int(item["ordinal"]),
        logical_rows=[_logical_row_from_physical(row, str(query_id)) for row in rows],
        predecessor_source=predecessor_source,
    )
    if rebuilt != item:
        _fail("load transaction differs from its deterministic reconstruction")
    return item


def _logical_row_from_physical(row: object, query_id: str) -> dict[str, object]:
    if not isinstance(row, Mapping):
        _fail("physical load row is not a mapping")
    item = dict(row)
    if query_id == "load-nodes-v1":
        _exact_keys(
            item,
            expected={
                "graph_release_id", "node_key", "kind", "node_id",
                "namespace", "properties", "row_sha256",
            },
            label="physical node row",
        )
        logical = graph.validate_node_row({
            "kind": item["kind"], "node_id": item["node_id"],
            "namespace": item["namespace"], "properties": item["properties"],
        })
    elif query_id == "load-edges-v1":
        _exact_keys(
            item,
            expected={
                "graph_release_id", "edge_key", "source_key", "target_key",
                "relationship", "source_id", "target_id", "namespace",
                "properties", "row_sha256",
            },
            label="physical edge row",
        )
        logical = graph.validate_edge_row({
            "relationship": item["relationship"],
            "source_id": item["source_id"], "target_id": item["target_id"],
            "namespace": item["namespace"], "properties": item["properties"],
        })
    else:
        _fail("physical load row query is not allowlisted")
    if item["row_sha256"] != graph.canonical_sha256(logical):
        _fail("physical load row hash differs")
    if query_id == "load-edges-v1":
        return {
            "relationship": logical["relationship"],
            "source_id": logical["source_id"],
            "target_id": logical["target_id"],
            "namespace": logical["namespace"],
            "properties": logical["properties"],
        }
    return logical


def iter_fixture_load_transactions(
    *, projection_manifest: Mapping[str, object],
    terminal: Sequence[tuple[Mapping[str, object], Mapping[str, object]]],
    predecessor_source: ExactArtifactSource | None = None,
) -> Iterator[dict[str, object]]:
    """Emit nodes then edges from sorted bounded shards, one batch at a time."""

    manifest = validate_projection_manifest(
        projection_manifest, predecessor_source=predecessor_source
    )
    for loader_query_id, unwind in (
        ("load-nodes-v1", "nodes"), ("load-edges-v1", "edges")
    ):
        for ordinal, batch in enumerate(_bounded_batches(
            _iter_sorted_fixture_rows(terminal, unwind=unwind)
        )):
            yield build_load_transaction(
                projection_manifest=manifest, loader_query_id=loader_query_id,
                ordinal=ordinal, logical_rows=batch,
                predecessor_source=predecessor_source,
            )


class OfflineGraphState:
    """Pure idempotence/conflict oracle for a single graph release."""

    def __init__(
        self, projection_manifest: Mapping[str, object], *,
        predecessor_source: ExactArtifactSource | None = None,
    ) -> None:
        self._predecessor_source = predecessor_source
        self._manifest = validate_projection_manifest(
            projection_manifest, predecessor_source=predecessor_source
        )
        self._release_id = str(
            self._manifest["graph_load_manifest"]["graph_release_id"]
        )
        self._nodes: dict[str, dict[str, object]] = {}
        self._edges: dict[str, dict[str, object]] = {}
        self._transactions: dict[str, str] = {}

    @property
    def graph_release_id(self) -> str:
        return self._release_id

    def node_rows(self) -> tuple[dict[str, object], ...]:
        return tuple(
            _canonical_copy(self._nodes[key])  # type: ignore[arg-type]
            for key in sorted(self._nodes)
        )

    def edge_rows(self) -> tuple[dict[str, object], ...]:
        return tuple(
            _canonical_copy(self._edges[key])  # type: ignore[arg-type]
            for key in sorted(self._edges)
        )

    def census(self) -> dict[str, object]:
        nodes = list(self._nodes.values())
        edges = list(self._edges.values())
        realized_nodes = sum(
            1 for row in nodes if row.get("namespace") == "realized"
        )
        realized_edges = sum(
            1 for row in edges if row.get("namespace") == "realized"
        )
        node_kinds = {
            kind: sum(1 for row in nodes if row["kind"] == kind)
            for kind in sorted({str(row["kind"]) for row in nodes})
        }
        relationships = {
            relationship: sum(
                1 for row in edges if row["relationship"] == relationship
            )
            for relationship in sorted(
                {str(row["relationship"]) for row in edges}
            )
        }
        return {
            "node_count": len(nodes), "edge_count": len(edges),
            "property_count": sum(len(row["properties"]) for row in nodes)
            + sum(len(row["properties"]) for row in edges),
            "node_kinds": node_kinds,
            "relationship_types": relationships,
            "namespaces": sorted(
                {str(row["namespace"]) for row in nodes}
                | {str(row["namespace"]) for row in edges}
            ),
            "realized_node_count": realized_nodes,
            "realized_edge_count": realized_edges,
        }

    def state_sha256(self) -> str:
        return graph.canonical_sha256({
            "graph_release_id": self._release_id,
            "nodes": list(self.node_rows()), "edges": list(self.edge_rows()),
        })

    def apply(self, transaction: Mapping[str, object]) -> dict[str, object]:
        item = validate_load_transaction(
            transaction, self._manifest,
            predecessor_source=self._predecessor_source,
        )
        transaction_id = str(item["batch_id"])
        transaction_hash = str(item["transaction_sha256"])
        existing_transaction = self._transactions.get(transaction_id)
        before = self.census()
        if existing_transaction is not None:
            if existing_transaction != transaction_hash:
                _fail("load transaction identity conflicts with prior application")
            return self._checkpoint(
                item=item, disposition="replayed", inserted=0,
                before=before, after=before,
            )

        query_id = str(item["loader_query_id"])
        pending_nodes = dict(self._nodes)
        pending_edges = dict(self._edges)
        inserted = 0
        if query_id == "load-nodes-v1":
            for physical in item["rows"]:
                logical = _logical_row_from_physical(physical, query_id)
                key = str(physical["node_key"])
                existing = pending_nodes.get(key)
                if existing is not None and existing != logical:
                    _fail(f"conflicting persisted node identity {key}")
                if existing is None:
                    pending_nodes[key] = logical
                    inserted += 1
        else:
            for physical in item["rows"]:
                logical = _logical_row_from_physical(physical, query_id)
                source_key = str(physical["source_key"])
                target_key = str(physical["target_key"])
                if source_key not in pending_nodes or target_key not in pending_nodes:
                    _fail("load edge endpoint is absent from the release")
                key = str(physical["edge_key"])
                existing = pending_edges.get(key)
                if existing is not None and existing != logical:
                    _fail(f"conflicting persisted edge identity {key}")
                if existing is None:
                    pending_edges[key] = logical
                    inserted += 1
        self._nodes = pending_nodes
        self._edges = pending_edges
        self._transactions[transaction_id] = transaction_hash
        after = self.census()
        return self._checkpoint(
            item=item, disposition="applied", inserted=inserted,
            before=before, after=after,
        )

    def _checkpoint(
        self, *, item: Mapping[str, object], disposition: str, inserted: int,
        before: Mapping[str, object], after: Mapping[str, object],
    ) -> dict[str, object]:
        body: dict[str, object] = {
            "schema_version": CHECKPOINT_RECEIPT_SCHEMA,
            "graph_release_id": self._release_id,
            "projection_manifest_sha256": self._manifest["projection_manifest_sha256"],
            "batch_id": item["batch_id"],
            "loader_query_id": item["loader_query_id"],
            "ordinal": item["ordinal"],
            "row_count": item["row_count"],
            "batch_sha256": item["batch_sha256"],
            "transaction_sha256": item["transaction_sha256"],
            "disposition": disposition, "inserted_count": inserted,
            "before_census": dict(before), "after_census": dict(after),
            "state_sha256": self.state_sha256(),
            "uses_realized_outcomes": False,
        }
        return validate_checkpoint_receipt(
            _with_self_hash(body, field="checkpoint_sha256"),
            self._manifest,
            transaction=item,
            predecessor_source=self._predecessor_source,
        )


def _validate_census(
    value: object, *, label: str, require_outcome_closed: bool,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a mapping")
    census = dict(value)
    _exact_keys(
        census,
        expected={
            "node_count", "edge_count", "property_count", "node_kinds",
            "relationship_types", "namespaces", "realized_node_count",
            "realized_edge_count",
        },
        label=label,
    )
    for field in (
        "node_count", "edge_count", "property_count",
        "realized_node_count", "realized_edge_count",
    ):
        count = census[field]
        if (
            not isinstance(count, int) or isinstance(count, bool)
            or count < 0 or count > graph.MAX_NEO4J_INTEGER
        ):
            _fail(f"{label} {field} is not a bounded nonnegative integer")
    if census["realized_node_count"] > census["node_count"]:
        _fail(f"{label} realized node count exceeds total nodes")
    if census["realized_edge_count"] > census["edge_count"]:
        _fail(f"{label} realized edge count exceeds total edges")
    maximum_properties = (
        (int(census["node_count"]) + int(census["edge_count"]))
        * graph.MAX_PROPERTIES
    )
    if int(census["property_count"]) > maximum_properties:
        _fail(f"{label} property count exceeds the positive-schema bound")

    def validate_breakdown(
        raw: object, *, field: str, allowed: frozenset[str], expected: int,
    ) -> dict[str, int]:
        if not isinstance(raw, Mapping):
            _fail(f"{label} {field} is not a mapping")
        retained: dict[str, int] = {}
        for key in sorted(raw, key=lambda item: str(item)):
            count = raw[key]
            if (
                not isinstance(key, str) or key not in allowed
                or not isinstance(count, int) or isinstance(count, bool)
                or count <= 0
            ):
                _fail(f"{label} {field} contains an invalid census entry")
            retained[key] = count
        if sum(retained.values()) != expected:
            _fail(f"{label} {field} does not sum to its total")
        return retained

    node_kinds = validate_breakdown(
        census["node_kinds"], field="node_kinds", allowed=graph.NODE_KINDS,
        expected=int(census["node_count"]),
    )
    relationships = validate_breakdown(
        census["relationship_types"], field="relationship_types",
        allowed=graph.RELATIONSHIP_TYPES, expected=int(census["edge_count"]),
    )
    raw_namespaces = census["namespaces"]
    if (
        isinstance(raw_namespaces, (str, bytes))
        or not isinstance(raw_namespaces, Sequence)
        or any(
            not isinstance(namespace, str)
            or namespace not in graph.ALLOWED_NAMESPACES
            for namespace in raw_namespaces
        )
        or list(raw_namespaces) != sorted(set(raw_namespaces))
    ):
        _fail(f"{label} namespaces are not canonical")
    namespaces = list(raw_namespaces)
    if require_outcome_closed and (
        "realized" in namespaces
        or census["realized_node_count"] != 0
        or census["realized_edge_count"] != 0
        or set(node_kinds) & graph.OUTCOME_NODE_KINDS
        or set(relationships) & graph.OUTCOME_RELATIONSHIP_TYPES
    ):
        _fail(f"{label} contains realized namespace contamination")
    return {
        "node_count": census["node_count"],
        "edge_count": census["edge_count"],
        "property_count": census["property_count"],
        "node_kinds": node_kinds,
        "relationship_types": relationships,
        "namespaces": namespaces,
        "realized_node_count": census["realized_node_count"],
        "realized_edge_count": census["realized_edge_count"],
    }


def validate_checkpoint_receipt(
    value: object, projection_manifest: Mapping[str, object], *,
    transaction: Mapping[str, object] | None = None,
    predecessor_source: ExactArtifactSource | None = None,
) -> dict[str, object]:
    """Validate one descriptor-only applied/replayed transaction receipt."""

    if not isinstance(value, Mapping):
        _fail("checkpoint receipt is not a mapping")
    receipt = dict(value)
    _exact_keys(
        receipt,
        expected={
            "schema_version", "graph_release_id",
            "projection_manifest_sha256", "batch_id", "loader_query_id",
            "ordinal", "row_count", "batch_sha256", "transaction_sha256",
            "disposition", "inserted_count", "before_census",
            "after_census", "state_sha256", "uses_realized_outcomes",
            "checkpoint_sha256",
        },
        label="checkpoint receipt",
    )
    _validate_self_hash(
        receipt, field="checkpoint_sha256", label="checkpoint receipt"
    )
    manifest = validate_projection_manifest(
        projection_manifest, predecessor_source=predecessor_source
    )
    if (
        receipt["schema_version"] != CHECKPOINT_RECEIPT_SCHEMA
        or receipt["graph_release_id"]
        != manifest["graph_load_manifest"]["graph_release_id"]
        or receipt["projection_manifest_sha256"]
        != manifest["projection_manifest_sha256"]
        or receipt["uses_realized_outcomes"] is not False
    ):
        _fail("checkpoint receipt release, schema, or outcome binding differs")
    query_id = receipt["loader_query_id"]
    if query_id not in {"load-nodes-v1", "load-edges-v1"}:
        _fail("checkpoint receipt loader query is not allowlisted")
    ordinal = receipt["ordinal"]
    row_count = receipt["row_count"]
    inserted = receipt["inserted_count"]
    if (
        not isinstance(ordinal, int) or isinstance(ordinal, bool)
        or not 0 <= ordinal < graph.MAX_TOTAL_BATCHES
        or not isinstance(row_count, int) or isinstance(row_count, bool)
        or not 1 <= row_count <= graph.BATCH_SIZE
        or not isinstance(inserted, int) or isinstance(inserted, bool)
        or not 0 <= inserted <= row_count
    ):
        _fail("checkpoint receipt counts are outside their bounds")
    if receipt["batch_id"] != f"{query_id}:{ordinal}":
        _fail("checkpoint receipt transaction identity is not query+ordinal")
    for field in ("batch_sha256", "transaction_sha256", "state_sha256"):
        if not isinstance(receipt[field], str) or _SHA.fullmatch(receipt[field]) is None:
            _fail(f"checkpoint receipt {field} is not 64-hex")
    disposition = receipt["disposition"]
    if disposition not in {"applied", "replayed"}:
        _fail("checkpoint receipt disposition is not registered")
    before = _validate_census(
        receipt["before_census"], label="checkpoint before census",
        require_outcome_closed=True,
    )
    after = _validate_census(
        receipt["after_census"], label="checkpoint after census",
        require_outcome_closed=True,
    )
    if disposition == "replayed":
        if inserted != 0 or before != after:
            _fail("replayed checkpoint changed graph state")
    else:
        changed_field = "node_count" if query_id == "load-nodes-v1" else "edge_count"
        unchanged_field = "edge_count" if query_id == "load-nodes-v1" else "node_count"
        if (
            int(after[changed_field]) - int(before[changed_field]) != inserted
            or after[unchanged_field] != before[unchanged_field]
        ):
            _fail("applied checkpoint census delta differs from insert count")
    if transaction is not None:
        item = validate_load_transaction(
            transaction, manifest, predecessor_source=predecessor_source
        )
        for field in (
            "batch_id", "loader_query_id", "ordinal", "row_count",
            "batch_sha256", "transaction_sha256",
        ):
            if receipt[field] != item[field]:
                _fail(f"checkpoint receipt differs from transaction {field}")
    return receipt


def _query_definition(query_id: str) -> dict[str, object]:
    for item in validate_read_query_catalog(read_query_catalog())["queries"]:
        if item["query_id"] == query_id:
            return dict(item)
    _fail("query id is not in the frozen read catalog")


def canonical_query_parameters(
    terminal: Sequence[tuple[Mapping[str, object], Mapping[str, object]]],
    *, graph_release_id: str,
) -> dict[str, dict[str, object]]:
    if not terminal:
        _fail("canonical query fixtures require terminal receipts")
    first_identity, first_receipt = sorted(
        terminal, key=lambda item: str(item[1]["chain"])
    )[0]
    _, first = _revalidate_bound_terminal(first_identity, first_receipt)
    chain = str(first["chain"])
    lineup_id = f"lineup:fixture:{chain}:001"
    common: dict[str, object] = {
        "graph_release_id": graph_release_id, "limit": 50,
    }
    return {
        "strategy-decomposition-v1": {
            **common, "bundle_id": first["strategy_bundle_id"],
        },
        "lineup-funnel-v1": {
            **common, "run_id": first["experiment_run_id"],
        },
        "release-lineage-v1": {
            **common, "anchor_id": first["science_release_id"],
        },
        "trait-enrichment-v1": {**common, "lineup_id": lineup_id},
        "cohort-compare-v1": {**common, "lineup_id": lineup_id},
        "matchup-exposure-v1": {
            **common, "player_id": f"player:fixture:{chain}:wr1",
        },
        "lineup-network-v1": {**common, "lineup_id": lineup_id},
        "source-quality-v1": dict(common),
        "promotion-evidence-gaps-v1": dict(common),
        "terminal-census-v1": dict(common),
    }


def _node_by_id(state: OfflineGraphState) -> dict[str, dict[str, object]]:
    return {str(row["node_id"]): row for row in state.node_rows()}


_QUERY_ORDER_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "strategy-decomposition-v1": ("preset_kind", "preset_id"),
    "lineup-funnel-v1": ("book_id",),
    "release-lineage-v1": ("relationship", "neighbor_id"),
    "trait-enrichment-v1": ("trait_id",),
    "cohort-compare-v1": ("cohort_id",),
    "matchup-exposure-v1": ("defender_id",),
    "lineup-network-v1": ("relationship", "neighbor_id"),
    "source-quality-v1": ("artifact_id",),
    "promotion-evidence-gaps-v1": ("decision_id",),
    "terminal-census-v1": ("node_count",),
}


def validate_query_result(
    value: object, *, graph_release_id: str,
    expected_parameters: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate one canonical read result independently of its evaluator."""

    if not isinstance(value, Mapping):
        _fail("canonical query result is not a mapping")
    result = dict(value)
    _exact_keys(
        result,
        expected={
            "schema_version", "query_catalog_schema",
            "query_catalog_sha256", "graph_release_id", "query_id",
            "query_sha256", "parameters", "row_count", "rows",
            "result_sha256",
        },
        label="canonical query result",
    )
    _validate_self_hash(
        result, field="result_sha256", label="canonical query result"
    )
    retained_release_id = _require_id(
        graph_release_id, label="expected query graph_release_id"
    )
    catalog = validate_read_query_catalog(read_query_catalog())
    if (
        result["schema_version"] != QUERY_RESULT_SCHEMA
        or result["query_catalog_schema"] != READ_QUERY_CATALOG_SCHEMA
        or result["query_catalog_sha256"] != catalog["query_catalog_sha256"]
        or result["graph_release_id"] != retained_release_id
    ):
        _fail("canonical query result catalog or release binding differs")
    query_id = result["query_id"]
    definition = next(
        (
            dict(item) for item in catalog["queries"]
            if item["query_id"] == query_id
        ),
        None,
    )
    if definition is None or result["query_sha256"] != definition["query_sha256"]:
        _fail("canonical query result query identity differs from catalog")
    parameters = result["parameters"]
    if not isinstance(parameters, Mapping):
        _fail("canonical query result parameters is not a mapping")
    retained_parameters = dict(parameters)
    if set(retained_parameters) != set(definition["parameters"]):
        _fail("canonical query result parameters differ from catalog")
    if retained_parameters.get("graph_release_id") != retained_release_id:
        _fail("canonical query result parameter release differs")
    limit = retained_parameters.get("limit")
    if (
        not isinstance(limit, int) or isinstance(limit, bool)
        or not 1 <= limit <= int(definition["max_rows"])
    ):
        _fail("canonical query result limit exceeds its catalog bound")
    for name, parameter in retained_parameters.items():
        if name not in {"limit", "graph_release_id"}:
            _require_id(parameter, label=f"canonical query result parameter {name}")
    if expected_parameters is not None and retained_parameters != dict(
        expected_parameters
    ):
        _fail("canonical query result parameters differ from expected fixture")
    raw_rows = result["rows"]
    if isinstance(raw_rows, (str, bytes)) or not isinstance(raw_rows, Sequence):
        _fail("canonical query result rows is not a sequence")
    if len(raw_rows) > limit:
        _fail("canonical query result row count exceeds its limit")
    row_count = result["row_count"]
    if (
        not isinstance(row_count, int) or isinstance(row_count, bool)
        or row_count != len(raw_rows)
    ):
        _fail("canonical query result row count differs from rows")
    expected_fields = set(definition["result_fields"])
    rows: list[dict[str, object]] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping) or set(raw_row) != expected_fields:
            _fail("canonical query result fields differ from catalog")
        row = dict(raw_row)
        _canonical_bytes(row)
        rows.append(row)
    order_fields = _QUERY_ORDER_FIELDS[str(query_id)]
    expected_order = sorted(
        rows,
        key=lambda row: tuple(
            _canonical_bytes(row[field]) for field in order_fields
        ),
    )
    if rows != expected_order:
        _fail("canonical query result rows differ from catalog ordering")
    if len(_canonical_bytes(result)) > MAX_QUERY_RESULT_BYTES:
        _fail("canonical query result exceeds its byte bound")
    return result


def run_canonical_query(
    state: OfflineGraphState, *, query_id: str, parameters: Mapping[str, object]
) -> dict[str, object]:
    """Evaluate one frozen fixture query without accepting arbitrary Cypher."""

    definition = _query_definition(query_id)
    expected_parameters = set(definition["parameters"])
    if set(parameters) != expected_parameters:
        _fail("canonical query parameters differ from the catalog")
    if parameters["graph_release_id"] != state.graph_release_id:
        _fail("canonical query graph release differs")
    limit = parameters["limit"]
    if (
        not isinstance(limit, int) or isinstance(limit, bool)
        or not 1 <= limit <= int(definition["max_rows"])
    ):
        _fail("canonical query limit exceeds its catalog bound")
    for name, value in parameters.items():
        if name not in {"limit", "graph_release_id"}:
            _require_id(value, label=f"query parameter {name}")
    nodes = _node_by_id(state)
    edges = list(state.edge_rows())
    rows: list[dict[str, object]] = []

    if query_id == "strategy-decomposition-v1":
        bundle = str(parameters["bundle_id"])
        bundle_node = nodes.get(bundle)
        if bundle_node and bundle_node["kind"] == "StrategyBundle":
            for edge in edges:
                target = nodes.get(str(edge["target_id"]))
                if (
                    edge["source_id"] == bundle
                    and edge["relationship"]
                    in {"DERIVED_FROM", "ADMITTED_BY", "SELECTED_BY"}
                    and target
                    and target["kind"]
                    in {"FillPreset", "AdmissionPreset", "RetrievalPreset"}
                ):
                    rows.append({
                        "bundle_id": bundle, "preset_id": target["node_id"],
                        "preset_kind": target["kind"],
                        "relationship": edge["relationship"],
                    })
    elif query_id == "lineup-funnel-v1":
        run_id = str(parameters["run_id"])
        run = nodes.get(run_id)
        bundle_ids = {
            str(edge["target_id"]) for edge in edges
            if run and run["kind"] == "ExperimentRun"
            and edge["source_id"] == run_id
            and edge["relationship"] == "EVALUATES_BUNDLE"
            and nodes.get(str(edge["target_id"]), {}).get("kind")
            == "StrategyBundle"
        }
        for bundle_id in bundle_ids:
            for edge in edges:
                book = nodes.get(str(edge["source_id"]))
                if (
                    edge["target_id"] == bundle_id
                    and edge["relationship"] == "GENERATED_BY"
                    and book and book["kind"] == "SelectedBook"
                ):
                    rows.append({
                        "run_id": run_id, "bundle_id": bundle_id,
                        "book_id": book["node_id"],
                        "entry_budget": book["properties"]["entry_budget"],
                    })
    elif query_id in {"release-lineage-v1", "lineup-network-v1"}:
        parameter_name = (
            "anchor_id" if query_id == "release-lineage-v1" else "lineup_id"
        )
        anchor = str(parameters[parameter_name])
        anchor_node = nodes.get(anchor)
        required_anchor_kind = (
            None if query_id == "release-lineage-v1" else "Lineup"
        )
        if anchor_node is None or (
            required_anchor_kind is not None
            and anchor_node["kind"] != required_anchor_kind
        ):
            edges = []
        for edge in edges:
            direction: str | None = None
            neighbor_id: str | None = None
            if edge["source_id"] == anchor:
                direction, neighbor_id = "out", str(edge["target_id"])
            elif edge["target_id"] == anchor:
                direction, neighbor_id = "in", str(edge["source_id"])
            if direction is None or neighbor_id is None:
                continue
            if query_id == "release-lineage-v1" and edge["namespace"] != "lineage":
                continue
            neighbor = nodes[neighbor_id]
            rows.append({
                "anchor_id" if query_id == "release-lineage-v1" else "lineup_id": anchor,
                "neighbor_id": neighbor_id, "neighbor_kind": neighbor["kind"],
                "relationship": edge["relationship"], "direction": direction,
            })
    elif query_id == "trait-enrichment-v1":
        lineup = str(parameters["lineup_id"])
        candidate_edges = (
            edges
            if nodes.get(lineup, {}).get("kind") == "Lineup"
            else []
        )
        for edge in candidate_edges:
            trait = nodes.get(str(edge["target_id"]))
            if (
                edge["source_id"] == lineup and edge["relationship"] == "HAS_TRAIT"
                and trait and trait["kind"] == "Trait"
            ):
                rows.append({
                    "lineup_id": lineup, "trait_id": trait["node_id"],
                    "trait_name": trait["properties"]["name"],
                    "trait_value": edge["properties"]["trait_value"],
                })
    elif query_id == "cohort-compare-v1":
        lineup = str(parameters["lineup_id"])
        candidate_edges = (
            edges
            if nodes.get(lineup, {}).get("kind") == "Lineup"
            else []
        )
        for edge in candidate_edges:
            cohort = nodes.get(str(edge["target_id"]))
            if (
                edge["source_id"] == lineup
                and edge["relationship"] == "MEMBER_OF_COHORT"
                and cohort and cohort["kind"] == "Cohort"
            ):
                rows.append({
                    "lineup_id": lineup, "cohort_id": cohort["node_id"],
                    "cohort_name": cohort["properties"]["name"],
                    "membership_reason": edge["properties"]["membership_reason"],
                })
    elif query_id == "matchup-exposure-v1":
        player = str(parameters["player_id"])
        candidate_edges = (
            edges
            if nodes.get(player, {}).get("kind") == "PlayerSlate"
            else []
        )
        for edge in candidate_edges:
            defender = nodes.get(str(edge["target_id"]))
            if (
                edge["source_id"] == player
                and edge["relationship"] == "HAS_INFERRED_DEFENDER_EXPOSURE"
                and edge["properties"].get("qualified_inferred") is True
                and defender is not None
                and defender["kind"] == "PlayerSlate"
            ):
                rows.append({
                    "player_id": player, "defender_id": edge["target_id"],
                    "method_id": edge["properties"]["method_id"],
                    "confidence": edge["properties"]["confidence"],
                    "qualified_inferred": edge["properties"]["qualified_inferred"],
                })
    elif query_id == "source-quality-v1":
        for edge in edges:
            receipt = nodes.get(str(edge["source_id"]))
            artifact = nodes.get(str(edge["target_id"]))
            if (
                edge["relationship"] == "DERIVED_FROM" and receipt and artifact
                and receipt["kind"] == "VerificationReceipt"
                and artifact["kind"] == "SourceArtifact"
            ):
                props = artifact["properties"]
                rows.append({
                    "artifact_id": artifact["node_id"],
                    "generation": props["generation"], "sha256": props["sha256"],
                    "bytes": props["byte_count"], "receipt_id": receipt["node_id"],
                })
    elif query_id == "promotion-evidence-gaps-v1":
        for edge in edges:
            decision = nodes.get(str(edge["source_id"]))
            bundle = nodes.get(str(edge["target_id"]))
            if (
                edge["relationship"] == "DECIDES_ON_BUNDLE" and decision and bundle
                and decision["kind"] == "PromotionDecision"
                and bundle["kind"] == "StrategyBundle"
                and decision["properties"]["disposition"] != "approved"
            ):
                rows.append({
                    "decision_id": decision["node_id"],
                    "bundle_id": bundle["node_id"],
                    "disposition": decision["properties"]["disposition"],
                    "evidence_tier": decision["properties"]["evidence_tier"],
                })
    elif query_id == "terminal-census-v1":
        census = state.census()
        rows.append({
            "node_count": census["node_count"],
            "edge_count": census["edge_count"],
            "property_count": census["property_count"],
            "realized_node_count": census["realized_node_count"],
            "realized_edge_count": census["realized_edge_count"],
        })
    else:  # pragma: no cover - catalog and evaluator are closed together.
        _fail("canonical query evaluator is missing")

    order_fields = _QUERY_ORDER_FIELDS[query_id]
    rows.sort(key=lambda row: tuple(
        _canonical_bytes(row[field]) for field in order_fields
    ))
    rows = rows[:limit]
    result_fields = set(definition["result_fields"])
    if any(set(row) != result_fields for row in rows):
        _fail("canonical query result fields differ from catalog")
    body: dict[str, object] = {
        "schema_version": QUERY_RESULT_SCHEMA,
        "query_catalog_schema": READ_QUERY_CATALOG_SCHEMA,
        "query_catalog_sha256": read_query_catalog()["query_catalog_sha256"],
        "graph_release_id": state.graph_release_id,
        "query_id": query_id, "query_sha256": definition["query_sha256"],
        "parameters": dict(parameters), "row_count": len(rows), "rows": rows,
    }
    retained = _with_self_hash(body, field="result_sha256")
    return validate_query_result(
        retained,
        graph_release_id=state.graph_release_id,
        expected_parameters=parameters,
    )


@dataclass(frozen=True)
class OfflineFixtureRebuild:
    projection_manifest: dict[str, object]
    load_plan: dict[str, object]
    state: OfflineGraphState
    checkpoints: tuple[dict[str, object], ...]
    query_results: tuple[dict[str, object], ...]
    terminal_receipt: dict[str, object]


def _stream_load_plan(
    manifest: Mapping[str, object], state: OfflineGraphState,
    checkpoints: Sequence[Mapping[str, object]],
    *, predecessor_source: ExactArtifactSource | None = None,
) -> dict[str, object]:
    """Build a descriptor-only index from checkpoint receipts, never rows."""

    if len(checkpoints) > graph.MAX_TOTAL_BATCHES:
        _fail("stream load plan exceeds the total batch bound")
    node_index: list[dict[str, object]] = []
    edge_index: list[dict[str, object]] = []
    seen_edge = False
    retained_checkpoints = [
        validate_checkpoint_receipt(
            checkpoint, manifest, predecessor_source=predecessor_source
        )
        for checkpoint in checkpoints
    ]
    for checkpoint in retained_checkpoints:
        query_id = checkpoint["loader_query_id"]
        if query_id == "load-edges-v1":
            seen_edge = True
        elif query_id == "load-nodes-v1":
            if seen_edge:
                _fail("node checkpoint appears after edge loading began")
        else:
            _fail("checkpoint loader query is not allowlisted")
        row = {
            "loader_query_id": query_id,
            "ordinal": checkpoint["ordinal"],
            "row_count": checkpoint["row_count"],
            "batch_sha256": checkpoint["batch_sha256"],
            "batch_id": checkpoint["batch_id"],
            "transaction_sha256": checkpoint["transaction_sha256"],
        }
        (node_index if query_id == "load-nodes-v1" else edge_index).append(row)
    body: dict[str, object] = {
        "schema_version": STREAM_LOAD_PLAN_SCHEMA,
        "projection_manifest_sha256": manifest["projection_manifest_sha256"],
        "loader_catalog_sha256": manifest["loader_catalog_sha256"],
        "batch_size": graph.BATCH_SIZE,
        "node_batch_index": node_index,
        "edge_batch_index": edge_index,
        "terminal_census": state.census(),
    }
    return validate_stream_load_plan(
        _with_self_hash(body, field="plan_sha256"), manifest,
        checkpoints=retained_checkpoints,
        predecessor_source=predecessor_source,
    )


def validate_stream_load_plan(
    value: object, projection_manifest: Mapping[str, object], *,
    checkpoints: Sequence[Mapping[str, object]] | None = None,
    predecessor_source: ExactArtifactSource | None = None,
) -> dict[str, object]:
    """Validate a descriptor-only node-first/edge-second load plan."""

    if not isinstance(value, Mapping):
        _fail("stream load plan is not a mapping")
    plan = dict(value)
    _exact_keys(
        plan,
        expected={
            "schema_version", "projection_manifest_sha256",
            "loader_catalog_sha256", "batch_size", "node_batch_index",
            "edge_batch_index", "terminal_census", "plan_sha256",
        },
        label="stream load plan",
    )
    _validate_self_hash(plan, field="plan_sha256", label="stream load plan")
    manifest = validate_projection_manifest(
        projection_manifest, predecessor_source=predecessor_source
    )
    if (
        plan["schema_version"] != STREAM_LOAD_PLAN_SCHEMA
        or plan["projection_manifest_sha256"]
        != manifest["projection_manifest_sha256"]
        or plan["loader_catalog_sha256"] != manifest["loader_catalog_sha256"]
        or plan["batch_size"] != graph.BATCH_SIZE
    ):
        _fail("stream load plan schema or contract binding differs")

    retained_indexes: dict[str, list[dict[str, object]]] = {}
    total_batches = 0
    for field, query_id in (
        ("node_batch_index", "load-nodes-v1"),
        ("edge_batch_index", "load-edges-v1"),
    ):
        raw_index = plan[field]
        if isinstance(raw_index, (str, bytes)) or not isinstance(raw_index, Sequence):
            _fail(f"stream load plan {field} is not a sequence")
        if len(raw_index) > graph.MAX_TOTAL_BATCHES:
            _fail(f"stream load plan {field} exceeds the batch bound")
        rows: list[dict[str, object]] = []
        for expected_ordinal, raw in enumerate(raw_index):
            if not isinstance(raw, Mapping):
                _fail(f"stream load plan {field} row is not a mapping")
            row = dict(raw)
            _exact_keys(
                row,
                expected={
                    "loader_query_id", "ordinal", "row_count",
                    "batch_sha256", "batch_id", "transaction_sha256",
                },
                label=f"stream load plan {field} row",
            )
            if (
                row["loader_query_id"] != query_id
                or row["ordinal"] != expected_ordinal
                or row["batch_id"] != f"{query_id}:{expected_ordinal}"
                or not isinstance(row["row_count"], int)
                or isinstance(row["row_count"], bool)
                or not 1 <= row["row_count"] <= graph.BATCH_SIZE
            ):
                _fail(f"stream load plan {field} row identity or count differs")
            for digest_field in ("batch_sha256", "transaction_sha256"):
                digest = row[digest_field]
                if not isinstance(digest, str) or _SHA.fullmatch(digest) is None:
                    _fail(
                        f"stream load plan {field} {digest_field} is not 64-hex"
                    )
            rows.append(row)
        retained_indexes[field] = rows
        total_batches += len(rows)
    if total_batches > graph.MAX_TOTAL_BATCHES:
        _fail("stream load plan exceeds the total batch bound")
    census = _validate_census(
        plan["terminal_census"], label="stream load plan terminal census",
        require_outcome_closed=True,
    )
    if sum(row["row_count"] for row in retained_indexes["node_batch_index"]) != census["node_count"]:
        _fail("stream load plan node rows differ from terminal census")
    if sum(row["row_count"] for row in retained_indexes["edge_batch_index"]) != census["edge_count"]:
        _fail("stream load plan edge rows differ from terminal census")
    if checkpoints is not None:
        expected_node: list[dict[str, object]] = []
        expected_edge: list[dict[str, object]] = []
        for raw_checkpoint in checkpoints:
            checkpoint = validate_checkpoint_receipt(
                raw_checkpoint, manifest,
                predecessor_source=predecessor_source,
            )
            row = {
                "loader_query_id": checkpoint["loader_query_id"],
                "ordinal": checkpoint["ordinal"],
                "row_count": checkpoint["row_count"],
                "batch_sha256": checkpoint["batch_sha256"],
                "batch_id": checkpoint["batch_id"],
                "transaction_sha256": checkpoint["transaction_sha256"],
            }
            (
                expected_node
                if checkpoint["loader_query_id"] == "load-nodes-v1"
                else expected_edge
            ).append(row)
        if (
            retained_indexes["node_batch_index"] != expected_node
            or retained_indexes["edge_batch_index"] != expected_edge
        ):
            _fail("stream load plan differs from checkpoint receipts")
    return plan


def validate_rebuild_receipt(
    value: object, *,
    projection_manifest: Mapping[str, object] | None = None,
    load_plan: Mapping[str, object] | None = None,
    checkpoints: Sequence[Mapping[str, object]] | None = None,
    query_results: Sequence[Mapping[str, object]] | None = None,
    predecessor_source: ExactArtifactSource | None = None,
) -> dict[str, object]:
    """Validate one terminal, outcome-closed zero-state rebuild receipt."""

    if not isinstance(value, Mapping):
        _fail("rebuild receipt is not a mapping")
    receipt = dict(value)
    _exact_keys(
        receipt,
        expected={
            "schema_version", "publication_mode", "graph_release_id",
            "projection_manifest_sha256", "plan_sha256",
            "schema_contract_sha256", "loader_catalog_sha256",
            "query_catalog_sha256", "checkpoint_sha256s",
            "terminal_census", "terminal_census_sha256", "state_sha256",
            "query_result_sha256s", "query_bundle_sha256", "source_count",
            "batch_count", "outcome_scope", "uses_realized_outcomes",
            "rebuild_receipt_sha256",
        },
        label="rebuild receipt",
    )
    _validate_self_hash(
        receipt, field="rebuild_receipt_sha256", label="rebuild receipt"
    )
    if (
        receipt["schema_version"] != REBUILD_RECEIPT_SCHEMA
        or receipt["publication_mode"] != FIXTURE_PUBLICATION_MODE
        or receipt["outcome_scope"] != "closed"
        or receipt["uses_realized_outcomes"] is not False
    ):
        _fail("rebuild receipt schema, mode, or outcome binding differs")
    _require_id(receipt["graph_release_id"], label="rebuild graph_release_id")
    for field in (
        "projection_manifest_sha256", "plan_sha256",
        "schema_contract_sha256", "loader_catalog_sha256",
        "query_catalog_sha256", "terminal_census_sha256", "state_sha256",
        "query_bundle_sha256",
    ):
        digest = receipt[field]
        if not isinstance(digest, str) or _SHA.fullmatch(digest) is None:
            _fail(f"rebuild receipt {field} is not 64-hex")
    source_count = receipt["source_count"]
    batch_count = receipt["batch_count"]
    if (
        not isinstance(source_count, int) or isinstance(source_count, bool)
        or not 1 <= source_count <= MAX_FIXTURE_RECEIPTS
        or not isinstance(batch_count, int) or isinstance(batch_count, bool)
        or not 1 <= batch_count <= graph.MAX_TOTAL_BATCHES
    ):
        _fail("rebuild receipt source or batch count is outside its bound")
    raw_checkpoint_hashes = receipt["checkpoint_sha256s"]
    if (
        isinstance(raw_checkpoint_hashes, (str, bytes))
        or not isinstance(raw_checkpoint_hashes, Sequence)
        or len(raw_checkpoint_hashes) != batch_count
        or any(
            not isinstance(digest, str) or _SHA.fullmatch(digest) is None
            for digest in raw_checkpoint_hashes
        )
    ):
        _fail("rebuild receipt checkpoint hashes differ from its batch count")
    census = _validate_census(
        receipt["terminal_census"], label="rebuild terminal census",
        require_outcome_closed=True,
    )
    if receipt["terminal_census_sha256"] != graph.canonical_sha256(census):
        _fail("rebuild receipt terminal census hash differs")
    raw_query_hashes = receipt["query_result_sha256s"]
    if not isinstance(raw_query_hashes, Mapping):
        _fail("rebuild receipt query result hashes is not a mapping")
    query_hashes = dict(raw_query_hashes)
    expected_query_ids = {
        row["query_id"] for row in read_query_catalog()["queries"]
    }
    if set(query_hashes) != expected_query_ids or any(
        not isinstance(digest, str) or _SHA.fullmatch(digest) is None
        for digest in query_hashes.values()
    ):
        _fail("rebuild receipt query result hashes differ from the catalog")
    expected_bundle_hash = graph.canonical_sha256({
        "query_catalog_sha256": receipt["query_catalog_sha256"],
        "query_result_sha256s": query_hashes,
    })
    if receipt["query_bundle_sha256"] != expected_bundle_hash:
        _fail("rebuild receipt query bundle hash differs")

    manifest: dict[str, object] | None = None
    if projection_manifest is not None:
        manifest = validate_projection_manifest(
            projection_manifest, predecessor_source=predecessor_source
        )
        if (
            receipt["graph_release_id"]
            != manifest["graph_load_manifest"]["graph_release_id"]
            or receipt["projection_manifest_sha256"]
            != manifest["projection_manifest_sha256"]
            or receipt["schema_contract_sha256"]
            != manifest["schema_contract_sha256"]
            or receipt["loader_catalog_sha256"]
            != manifest["loader_catalog_sha256"]
            or receipt["query_catalog_sha256"]
            != manifest["query_catalog_sha256"]
            or source_count != len(manifest["terminal_receipts"])
        ):
            _fail("rebuild receipt differs from its projection manifest")
    if load_plan is not None:
        if manifest is None:
            _fail("rebuild load-plan validation requires the projection manifest")
        retained_plan = validate_stream_load_plan(
            load_plan, manifest, checkpoints=checkpoints,
            predecessor_source=predecessor_source,
        )
        if (
            receipt["plan_sha256"] != retained_plan["plan_sha256"]
            or receipt["terminal_census"] != retained_plan["terminal_census"]
            or batch_count
            != len(retained_plan["node_batch_index"])
            + len(retained_plan["edge_batch_index"])
        ):
            _fail("rebuild receipt differs from its stream load plan")
    if checkpoints is not None:
        if manifest is None:
            _fail("rebuild checkpoint validation requires the projection manifest")
        retained_checkpoints = [
            validate_checkpoint_receipt(
                checkpoint, manifest, predecessor_source=predecessor_source
            )
            for checkpoint in checkpoints
        ]
        if [row["checkpoint_sha256"] for row in retained_checkpoints] != list(
            raw_checkpoint_hashes
        ):
            _fail("rebuild receipt differs from its checkpoint receipts")
    if query_results is not None:
        retained_result_hashes: dict[str, str] = {}
        for raw_result in query_results:
            result = validate_query_result(
                raw_result,
                graph_release_id=str(receipt["graph_release_id"]),
            )
            query_id = str(result["query_id"])
            digest = str(result["result_sha256"])
            if query_id in retained_result_hashes:
                _fail("rebuild query result identity differs")
            retained_result_hashes[query_id] = digest
        if retained_result_hashes != query_hashes:
            _fail("rebuild receipt differs from canonical query results")
    return receipt


def read_rebuild_receipt(
    identity: Mapping[str, object], source: ExactArtifactSource,
) -> dict[str, object]:
    """Exact-read and validate one terminal rebuild receipt by four-part id."""

    _, retained, _ = _read_exact_canonical_mapping(
        identity, source, label="predecessor rebuild receipt"
    )
    return validate_rebuild_receipt(retained)


def rebuild_fixture_projection(
    projection_manifest: Mapping[str, object], source: ExactArtifactSource, *,
    predecessor_source: ExactArtifactSource | None = None,
) -> OfflineFixtureRebuild:
    """Perform a deterministic zero-state fixture rebuild with no I/O side effect."""

    manifest = validate_projection_manifest(
        projection_manifest, predecessor_source=predecessor_source
    )
    terminal = read_terminal_fixtures(
        manifest, source, predecessor_source=predecessor_source
    )
    state = OfflineGraphState(
        manifest, predecessor_source=predecessor_source
    )
    checkpoints = tuple(
        state.apply(transaction)
        for transaction in iter_fixture_load_transactions(
            projection_manifest=manifest, terminal=terminal,
            predecessor_source=predecessor_source,
        )
    )
    load_plan = _stream_load_plan(
        manifest, state, checkpoints,
        predecessor_source=predecessor_source,
    )
    fixture_parameters = canonical_query_parameters(
        terminal, graph_release_id=state.graph_release_id
    )
    query_results = tuple(
        run_canonical_query(
            state, query_id=query_id, parameters=fixture_parameters[query_id]
        )
        for query_id in sorted(fixture_parameters)
    )
    query_result_sha256s = {
        row["query_id"]: row["result_sha256"] for row in query_results
    }
    query_bundle_sha256 = graph.canonical_sha256({
        "query_catalog_sha256": manifest["query_catalog_sha256"],
        "query_result_sha256s": query_result_sha256s,
    })
    terminal_census = state.census()
    body: dict[str, object] = {
        "schema_version": REBUILD_RECEIPT_SCHEMA,
        "publication_mode": FIXTURE_PUBLICATION_MODE,
        "graph_release_id": state.graph_release_id,
        "projection_manifest_sha256": manifest["projection_manifest_sha256"],
        "plan_sha256": load_plan["plan_sha256"],
        "schema_contract_sha256": manifest["schema_contract_sha256"],
        "loader_catalog_sha256": manifest["loader_catalog_sha256"],
        "query_catalog_sha256": manifest["query_catalog_sha256"],
        "checkpoint_sha256s": [row["checkpoint_sha256"] for row in checkpoints],
        "terminal_census": terminal_census,
        "terminal_census_sha256": graph.canonical_sha256(terminal_census),
        "state_sha256": state.state_sha256(),
        "query_result_sha256s": query_result_sha256s,
        "query_bundle_sha256": query_bundle_sha256,
        "source_count": len(terminal),
        "batch_count": len(checkpoints),
        "outcome_scope": "closed",
        "uses_realized_outcomes": False,
    }
    terminal_receipt = validate_rebuild_receipt(
        _with_self_hash(body, field="rebuild_receipt_sha256"),
        projection_manifest=manifest,
        load_plan=load_plan,
        checkpoints=checkpoints,
        query_results=query_results,
        predecessor_source=predecessor_source,
    )
    return OfflineFixtureRebuild(
        projection_manifest=manifest,
        load_plan=load_plan,
        state=state,
        checkpoints=checkpoints,
        query_results=query_results,
        terminal_receipt=terminal_receipt,
    )


__all__ = [
    "CHECKPOINT_RECEIPT_SCHEMA",
    "CorpusGraphFixtureAdapterError",
    "ExactArtifactSource",
    "ExactFixtureArtifact",
    "FIXTURE_ADAPTER_SCHEMA",
    "FIXTURE_CHAINS",
    "FIXTURE_GRAPH_RELEASE_ID",
    "FIXTURE_RECEIPT_SCHEMA",
    "InMemoryExactArtifactSource",
    "LOAD_TRANSACTION_SCHEMA",
    "MAX_LOAD_DEADLINE_MS",
    "MAX_QUERY_DEADLINE_MS",
    "MAX_QUERY_ROWS",
    "MAX_RECEIPT_BYTES",
    "OfflineFixtureRebuild",
    "OfflineGraphState",
    "PROJECTION_MANIFEST_SCHEMA",
    "QUERY_RESULT_SCHEMA",
    "READ_QUERY_CATALOG_SCHEMA",
    "REBUILD_RECEIPT_SCHEMA",
    "SCHEMA_CONTRACT_SCHEMA",
    "build_load_transaction",
    "canonical_fixture_projection",
    "canonical_query_parameters",
    "fixture_terminal_artifacts",
    "iter_fixture_load_transactions",
    "loader_query_catalog",
    "prepare_projection_manifest",
    "project_fixture_rows",
    "read_query_catalog",
    "read_rebuild_receipt",
    "read_terminal_fixtures",
    "rebuild_fixture_projection",
    "run_canonical_query",
    "schema_contract",
    "validate_load_transaction",
    "validate_loader_query_catalog",
    "validate_object_identity",
    "validate_predecessor_identity",
    "validate_projection_manifest",
    "validate_query_result",
    "validate_read_query_catalog",
    "validate_rebuild_receipt",
    "validate_schema_contract",
    "validate_checkpoint_receipt",
    "validate_stream_load_plan",
    "validate_terminal_fixture_receipt",
]
