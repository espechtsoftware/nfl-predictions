"""Offline graph-vNext contracts: vocabulary, load manifest, batch plan.

Pure, offline building blocks for the future Neo4j release projection.
Nothing here opens a connection or reads cloud state: callers supply
identity-bound rows; these functions validate vocabulary and manifests,
build deterministic bounded UNWIND batch plans, and produce an exact
terminal census. Identical inputs — in any order — produce byte-identical
plans; conflicting identities, forbidden vocabulary, oversized properties,
outcome-bearing fields, and unauthorized realized namespaces fail closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import re
from typing import Final

GRAPH_SCHEMA_VERSION: Final = "corpus-graph-vnext/v1"
LOAD_MANIFEST_SCHEMA: Final = "foundry-graph-load-manifest/v1"
BATCH_SIZE: Final = 500
MAX_PROPERTY_LIST_LENGTH: Final = 32
MAX_PROPERTY_STRING_LENGTH: Final = 512

NODE_KINDS: Final = frozenset({
    "Slate", "Contest", "SlateSnapshot", "PlayerSlate", "TeamSlate", "Game",
    "WorldRelease", "CorpusSnapshot", "CandidateSnapshot", "Lineup",
    "SelectedBook", "ScienceRelease", "VerifierRelease",
    "DeploymentAttestation", "FillPreset", "AdmissionPreset",
    "RetrievalPreset", "StrategyBundle", "ExperimentRun", "ExperimentCell",
    "Evaluation", "Fold", "MetricSet", "Trait", "Cohort", "WinnerRelease",
    "WinnerObservation", "OutcomeRelease", "OutcomeGrade", "SourceArtifact",
    "VerificationReceipt", "Attempt", "PromotionDecision",
})

RELATIONSHIP_TYPES: Final = frozenset({
    "DERIVED_FROM", "USES_SOURCE", "USES_WORLD_RELEASE", "GENERATED_BY",
    "SUPPLIED_BY_ARM", "MEMBER_OF_CORPUS", "CONTAINS_PLAYER", "PLAYS_FOR",
    "IN_GAME", "HAS_TRAIT", "MEMBER_OF_COHORT", "ADMITTED_BY",
    "SELECTED_BY", "MEMBER_OF_BOOK", "EVALUATED_IN", "HAS_METRIC",
    "PAIRED_AGAINST", "GRADED_IN_CONTEST", "DERIVED_FROM_OUTCOME",
    "OBSERVED_IN_WINNER_RELEASE", "EVALUATES_BUNDLE", "RETRIED_AS",
    "VERIFIED_BY", "DECIDES_ON_BUNDLE", "HAS_INFERRED_DEFENDER_EXPOSURE",
})

# A factual coverage claim may never be created from an inferred matchup.
FORBIDDEN_RELATIONSHIP_TYPES: Final = frozenset({"COVERED_BY"})

QUALIFIED_INFERRED_TYPES: Final = frozenset({
    "HAS_INFERRED_DEFENDER_EXPOSURE",
})

ALLOWED_NAMESPACES: Final = frozenset({
    "identity", "membership", "trait", "metric", "lineage", "realized",
})

# Outcome-bearing property names may only ever appear in the realized
# namespace, which itself opens only with an authorized OutcomeRelease.
OUTCOME_PROPERTY_NAMES: Final = frozenset({
    "actual_score", "realized_score", "realized_score_micro", "payout",
    "winnings", "contest_rank", "roi", "field_rank",
})

FORBIDDEN_PROPERTY_NAMES: Final = frozenset({
    "credential", "secret", "token", "password", "api_key",
})

_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$")
_SHA: Final = re.compile(r"^[0-9a-f]{64}$")


class CorpusGraphVNextError(ValueError):
    """Raised when a contract, row, or manifest fails closed."""


def _fail(message: str) -> None:
    raise CorpusGraphVNextError(message)


def canonical_sha256(value: object) -> str:
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def _require_identity(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a mapping")
    row = dict(value)
    if set(row) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} does not carry exactly uri/generation/sha256/bytes")
    if not isinstance(row["uri"], str) or not row["uri"].startswith("gs://"):
        _fail(f"{label}.uri is not a gs:// uri")
    if not isinstance(row["generation"], str) or not row["generation"].isdigit():
        _fail(f"{label}.generation is not digits")
    if not isinstance(row["sha256"], str) or _SHA.fullmatch(row["sha256"]) is None:
        _fail(f"{label}.sha256 is not 64-hex")
    if (
        not isinstance(row["bytes"], int)
        or isinstance(row["bytes"], bool)
        or row["bytes"] <= 0
    ):
        _fail(f"{label}.bytes is not positive")
    return row


def _validate_property(
    key: str, value: object, *, namespace: str, label: str
) -> None:
    if key.lower() in FORBIDDEN_PROPERTY_NAMES:
        _fail(f"{label} property {key} is forbidden in graph content")
    if key in OUTCOME_PROPERTY_NAMES and namespace != "realized":
        _fail(
            f"{label} outcome property {key} outside the realized namespace"
        )
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_PROPERTY_LIST_LENGTH:
            _fail(
                f"{label} property {key} carries {len(value)} elements; "
                "world-scale arrays never enter the graph"
            )
        for item in value:
            if not isinstance(item, (str, int, float, bool)):
                _fail(f"{label} property {key} has a non-scalar element")
    elif isinstance(value, str):
        if len(value) > MAX_PROPERTY_STRING_LENGTH:
            _fail(f"{label} property {key} string exceeds the bound")
    elif not isinstance(value, (int, float, bool)) and value is not None:
        _fail(f"{label} property {key} is not a bounded scalar")


def validate_node_row(row: Mapping[str, object]) -> dict[str, object]:
    kind = row.get("kind")
    node_id = row.get("node_id")
    namespace = row.get("namespace")
    properties = row.get("properties")
    if kind not in NODE_KINDS:
        _fail(f"node kind {kind!r} is not registered")
    if not isinstance(node_id, str) or _ID.fullmatch(node_id) is None:
        _fail("node_id is not canonical")
    if namespace not in ALLOWED_NAMESPACES:
        _fail(f"node namespace {namespace!r} is not allowlisted")
    if not isinstance(properties, Mapping):
        _fail("node properties is not a mapping")
    for key, value in properties.items():
        if not isinstance(key, str):
            _fail("node property key is not a string")
        _validate_property(
            key, value, namespace=str(namespace), label=f"node {node_id}"
        )
    return {
        "kind": kind,
        "node_id": node_id,
        "namespace": namespace,
        "properties": {key: properties[key] for key in sorted(properties)},
    }


def validate_edge_row(row: Mapping[str, object]) -> dict[str, object]:
    relationship = row.get("relationship")
    source = row.get("source_id")
    target = row.get("target_id")
    namespace = row.get("namespace")
    properties = row.get("properties", {})
    if relationship in FORBIDDEN_RELATIONSHIP_TYPES:
        _fail(
            f"relationship {relationship} is forbidden: a factual coverage "
            "claim may not be created from an inferred matchup"
        )
    if relationship not in RELATIONSHIP_TYPES:
        _fail(f"relationship {relationship!r} is not registered")
    for label, value in (("source_id", source), ("target_id", target)):
        if not isinstance(value, str) or _ID.fullmatch(value) is None:
            _fail(f"edge {label} is not canonical")
    if namespace not in ALLOWED_NAMESPACES:
        _fail(f"edge namespace {namespace!r} is not allowlisted")
    if not isinstance(properties, Mapping):
        _fail("edge properties is not a mapping")
    retained = {key: properties[key] for key in sorted(properties)}
    for key, value in retained.items():
        _validate_property(
            key, value, namespace=str(namespace),
            label=f"edge {source}->{target}",
        )
    if relationship in QUALIFIED_INFERRED_TYPES and retained.get(
        "qualified_inferred"
    ) is not True:
        _fail(
            f"relationship {relationship} must carry "
            "qualified_inferred=true"
        )
    edge_key = f"{source}|{relationship}|{target}"
    return {
        "relationship": relationship,
        "source_id": source,
        "target_id": target,
        "namespace": namespace,
        "edge_key": edge_key,
        "properties": retained,
    }


def validate_load_manifest(value: Mapping[str, object]) -> dict[str, object]:
    manifest = dict(value)
    if manifest.get("schema_version") != LOAD_MANIFEST_SCHEMA:
        _fail("load manifest schema differs")
    if manifest.get("graph_schema_version") != GRAPH_SCHEMA_VERSION:
        _fail("load manifest graph schema version differs")
    release = manifest.get("graph_release_id")
    if not isinstance(release, str) or _ID.fullmatch(release) is None:
        _fail("graph_release_id is not canonical")
    predecessor = manifest.get("predecessor_graph_release_id")
    if predecessor is not None and (
        not isinstance(predecessor, str) or _ID.fullmatch(predecessor) is None
    ):
        _fail("predecessor_graph_release_id is not canonical")
    namespaces = manifest.get("allowed_namespaces")
    if (
        not isinstance(namespaces, Sequence)
        or isinstance(namespaces, (str, bytes))
        or not namespaces
        or len(set(namespaces)) != len(namespaces)
        or not set(namespaces) <= ALLOWED_NAMESPACES
    ):
        _fail("allowed_namespaces is not a nonempty allowlisted subset")
    sources = manifest.get("source_releases")
    if (
        not isinstance(sources, Sequence)
        or isinstance(sources, (str, bytes))
        or not sources
    ):
        _fail("source_releases is not a nonempty sequence")
    retained_sources = [
        _require_identity(source, label=f"source_releases[{index}]")
        for index, source in enumerate(sources)
    ]
    outcome_release = manifest.get("authorized_outcome_release_id")
    if outcome_release is not None and (
        not isinstance(outcome_release, str)
        or _ID.fullmatch(outcome_release) is None
    ):
        _fail("authorized_outcome_release_id is not canonical")
    if "realized" in set(namespaces) and outcome_release is None:
        _fail(
            "realized namespace requires an authorized OutcomeRelease; "
            "it stays closed otherwise"
        )
    created = manifest.get("created_at_utc")
    if not isinstance(created, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", created
    ):
        _fail("created_at_utc is not second-precision UTC")
    body = {
        "schema_version": LOAD_MANIFEST_SCHEMA,
        "graph_schema_version": GRAPH_SCHEMA_VERSION,
        "graph_release_id": release,
        "predecessor_graph_release_id": predecessor,
        "allowed_namespaces": sorted(set(namespaces)),
        "source_releases": retained_sources,
        "authorized_outcome_release_id": outcome_release,
        "created_at_utc": created,
    }
    retained_hash = manifest.get("manifest_sha256")
    expected_hash = canonical_sha256(body)
    if retained_hash is None:
        return {**body, "manifest_sha256": expected_hash}
    if retained_hash != expected_hash:
        _fail("manifest_sha256 differs from the canonical body")
    return {**body, "manifest_sha256": expected_hash}


def build_load_plan(
    *,
    manifest: Mapping[str, object],
    node_rows: Sequence[Mapping[str, object]],
    edge_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Deterministic bounded batch plan with an exact terminal census.

    Input order never matters; identical content yields an identical plan
    hash, and a repeated identity with different content fails closed.
    """

    retained_manifest = validate_load_manifest(manifest)
    allowed = set(retained_manifest["allowed_namespaces"])

    nodes_by_id: dict[str, dict[str, object]] = {}
    for row in node_rows:
        node = validate_node_row(row)
        if node["namespace"] not in allowed:
            _fail(
                f"node namespace {node['namespace']} is outside this "
                "manifest's allowed namespaces"
            )
        existing = nodes_by_id.get(str(node["node_id"]))
        if existing is not None:
            if existing != node:
                _fail(
                    f"conflicting identity for node {node['node_id']}: "
                    "same id with different content fails closed"
                )
            continue
        nodes_by_id[str(node["node_id"])] = node

    edges_by_key: dict[str, dict[str, object]] = {}
    for row in edge_rows:
        edge = validate_edge_row(row)
        if edge["namespace"] not in allowed:
            _fail(
                f"edge namespace {edge['namespace']} is outside this "
                "manifest's allowed namespaces"
            )
        for endpoint in (edge["source_id"], edge["target_id"]):
            if str(endpoint) not in nodes_by_id:
                _fail(f"edge endpoint {endpoint} is not a loaded node")
        existing = edges_by_key.get(str(edge["edge_key"]))
        if existing is not None:
            if existing != edge:
                _fail(
                    f"conflicting identity for edge {edge['edge_key']}: "
                    "same key with different content fails closed"
                )
            continue
        edges_by_key[str(edge["edge_key"])] = edge

    ordered_nodes = sorted(
        nodes_by_id.values(),
        key=lambda node: (str(node["kind"]), str(node["node_id"])),
    )
    ordered_edges = sorted(
        edges_by_key.values(), key=lambda edge: str(edge["edge_key"])
    )

    def batches(rows: list[dict[str, object]], unwind: str) -> list[dict[str, object]]:
        output = []
        for start in range(0, len(rows), BATCH_SIZE):
            window = rows[start : start + BATCH_SIZE]
            output.append({
                "unwind": unwind,
                "ordinal": len(output),
                "row_count": len(window),
                "rows": window,
                "batch_sha256": canonical_sha256(window),
            })
        return output

    node_kind_census = {
        kind: sum(1 for node in ordered_nodes if node["kind"] == kind)
        for kind in sorted({str(node["kind"]) for node in ordered_nodes})
    }
    edge_type_census = {
        relationship: sum(
            1 for edge in ordered_edges if edge["relationship"] == relationship
        )
        for relationship in sorted(
            {str(edge["relationship"]) for edge in ordered_edges}
        )
    }
    property_count = sum(
        len(node["properties"]) for node in ordered_nodes  # type: ignore[arg-type]
    ) + sum(len(edge["properties"]) for edge in ordered_edges)  # type: ignore[arg-type]

    plan_body = {
        "schema_version": GRAPH_SCHEMA_VERSION,
        "manifest_sha256": retained_manifest["manifest_sha256"],
        "node_batches": batches(ordered_nodes, "nodes"),
        "edge_batches": batches(ordered_edges, "edges"),
        "terminal_census": {
            "node_count": len(ordered_nodes),
            "edge_count": len(ordered_edges),
            "property_count": property_count,
            "node_kinds": node_kind_census,
            "relationship_types": edge_type_census,
            "namespaces": sorted(
                {str(node["namespace"]) for node in ordered_nodes}
                | {str(edge["namespace"]) for edge in ordered_edges}
            ),
        },
    }
    return {**plan_body, "plan_sha256": canonical_sha256(plan_body)}
