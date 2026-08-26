"""Offline Phase 4 tests for exact fixture graph loading and rebuild proof."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from nfl_dfs.research import corpus_graph_vnext_contracts as graph
from nfl_dfs.research import corpus_graph_vnext_fixture_adapter as adapter


ERRORS = (adapter.CorpusGraphFixtureAdapterError, graph.CorpusGraphVNextError)

EXPECTED_CONTRACT_HASHES = {
    "schema": "d877456d630069406c58a90a7adb9930bab4873e01da352ad9ccf1b393a081c1",
    "loader": "9c661dc18a0654e7e6808fa6a6b22da2ea9e3b184488a9d6c25603ce6e2eb0b5",
    "query_catalog": "b785d83ed75877e895ddacc3d1319110bd82c6ab86c10ea04ff5c0e9a12f4604",
    "manifest": "29b73af190e8a42015140ac57882bdb348b23da509d5d40056ba665511d9eaa8",
    "plan": "985bba935115216a9fba4ee84ba9f8808cafdc7bc7ae846cb3449ae23975afc1",
    "state": "7c9f18bc9f54ed37efedf10ffebc81cd0ba5f2787139ccd1edecdaff72d7a215",
    "query_bundle": "7fce74e299a543f2b31cc2b96c461710a017eeb0d5324185ccabd46d5a50a909",
    "terminal": "bf55ae3f68696a6dccfc22e16bc3a91728b7aa6091a29670877e4e018b83efb6",
}

EXPECTED_QUERY_HASHES = {
    "cohort-compare-v1": "6d6660d7ff8e9425bec39beeba8754685208e8f2845c9014d33ba9afee2d1a88",
    "lineup-funnel-v1": "94699b74051cdbfaa27646f6a4ceab3e18fd75839b2a6dcef029e6747942f787",
    "lineup-network-v1": "6226546e8e9f2b0fdccb86b19a866225595ae54fba5333f5dd1506e67f9c9962",
    "matchup-exposure-v1": "997f910361837ffb87d8904aa666ec2c3d67ecae49a649ad8e15c1ef789176fa",
    "promotion-evidence-gaps-v1": "1a54fe9bc46ace268e3c1ae5fb329c32b96198d5b1a3af2db1f9475d98574e60",
    "release-lineage-v1": "b838d74be2f9b61ec91d65cc36e69e0f9595c5cab01a5bfa32f1d7b0869460ec",
    "source-quality-v1": "f8fd23531067f3443bed1dd394be123ebb69e5be3c2bc05ee790fb3ad2d657cf",
    "strategy-decomposition-v1": "0811609bccfa34c02c98cec672f2830daea9ebc6f7f7fd1cc801c7de37e04f74",
    "terminal-census-v1": "a824da3ce8b8d6006aa979f8e64d3c9d0a0b268219934b84a3c76cf0d340b8b0",
    "trait-enrichment-v1": "662706e7e91dc96dbe50d0006eddd460275c0241d40f90d4982ba04816a87ac1",
}

# Independent literals: neither mapping is derived from the catalog or the
# Python evaluator under test.
EXPECTED_QUERY_CYPHER: dict[str, str] = {
    "strategy-decomposition-v1": (
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
    "lineup-funnel-v1": (
        "MATCH (run:FoundryNode {graph_release_id: $graph_release_id, "
        "node_id: $run_id, kind: 'ExperimentRun'})"
        "-[e:FoundryRelation {graph_release_id: $graph_release_id}]->"
        "(bundle:FoundryNode {graph_release_id: $graph_release_id, "
        "kind: 'StrategyBundle'}) "
        "MATCH (book:FoundryNode {graph_release_id: $graph_release_id, "
        "kind: 'SelectedBook'})"
        "-[g:FoundryRelation {graph_release_id: $graph_release_id}]->"
        "(bundle) WHERE e.relationship = 'EVALUATES_BUNDLE' "
        "AND g.relationship = 'GENERATED_BY' "
        "RETURN run.node_id AS run_id, bundle.node_id AS bundle_id, "
        "book.node_id AS book_id, book.entry_budget AS entry_budget "
        "ORDER BY book_id LIMIT $limit"
    ),
    "release-lineage-v1": (
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
    "trait-enrichment-v1": (
        "MATCH (lineup:FoundryNode {graph_release_id: $graph_release_id, "
        "node_id: $lineup_id, kind: 'Lineup'})"
        "-[r:FoundryRelation {graph_release_id: $graph_release_id}]->"
        "(trait:FoundryNode {graph_release_id: $graph_release_id, "
        "kind: 'Trait'}) WHERE r.relationship = 'HAS_TRAIT' "
        "RETURN lineup.node_id AS lineup_id, trait.node_id AS trait_id, "
        "trait.name AS trait_name, r.trait_value AS trait_value "
        "ORDER BY trait_id LIMIT $limit"
    ),
    "cohort-compare-v1": (
        "MATCH (lineup:FoundryNode {graph_release_id: $graph_release_id, "
        "node_id: $lineup_id, kind: 'Lineup'})"
        "-[r:FoundryRelation {graph_release_id: $graph_release_id}]->"
        "(cohort:FoundryNode {graph_release_id: $graph_release_id, "
        "kind: 'Cohort'}) WHERE r.relationship = 'MEMBER_OF_COHORT' "
        "RETURN lineup.node_id AS lineup_id, cohort.node_id AS cohort_id, "
        "cohort.name AS cohort_name, r.membership_reason AS membership_reason "
        "ORDER BY cohort_id LIMIT $limit"
    ),
    "matchup-exposure-v1": (
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
    "lineup-network-v1": (
        "MATCH (lineup:FoundryNode {graph_release_id: $graph_release_id, "
        "node_id: $lineup_id, kind: 'Lineup'})"
        "-[r:FoundryRelation {graph_release_id: $graph_release_id}]-"
        "(neighbor:FoundryNode {graph_release_id: $graph_release_id}) "
        "RETURN lineup.node_id AS lineup_id, neighbor.node_id AS neighbor_id, "
        "neighbor.kind AS neighbor_kind, r.relationship AS relationship, "
        "CASE WHEN startNode(r) = lineup THEN 'out' ELSE 'in' END AS direction "
        "ORDER BY relationship, neighbor_id LIMIT $limit"
    ),
    "source-quality-v1": (
        "MATCH (receipt:FoundryNode {graph_release_id: $graph_release_id, "
        "kind: 'VerificationReceipt'})"
        "-[r:FoundryRelation {graph_release_id: $graph_release_id}]->"
        "(artifact:FoundryNode {graph_release_id: $graph_release_id, "
        "kind: 'SourceArtifact'}) WHERE r.relationship = 'DERIVED_FROM' "
        "RETURN artifact.node_id AS artifact_id, "
        "artifact.generation AS generation, artifact.sha256 AS sha256, "
        "artifact.byte_count AS bytes, receipt.node_id AS receipt_id "
        "ORDER BY artifact_id LIMIT $limit"
    ),
    "promotion-evidence-gaps-v1": (
        "MATCH (decision:FoundryNode {graph_release_id: $graph_release_id, "
        "kind: 'PromotionDecision'})"
        "-[r:FoundryRelation {graph_release_id: $graph_release_id}]->"
        "(bundle:FoundryNode {graph_release_id: $graph_release_id, "
        "kind: 'StrategyBundle'}) WHERE r.relationship = 'DECIDES_ON_BUNDLE' "
        "AND decision.disposition <> 'approved' "
        "RETURN decision.node_id AS decision_id, bundle.node_id AS bundle_id, "
        "decision.disposition AS disposition, "
        "decision.evidence_tier AS evidence_tier "
        "ORDER BY decision_id LIMIT $limit"
    ),
    "terminal-census-v1": (
        "OPTIONAL MATCH (n:FoundryNode "
        "{graph_release_id: $graph_release_id}) "
        "WITH [item IN collect(n) WHERE item IS NOT NULL] AS nodes "
        "OPTIONAL MATCH (:FoundryNode "
        "{graph_release_id: $graph_release_id})"
        "-[r:FoundryRelation {graph_release_id: $graph_release_id}]->"
        "(:FoundryNode {graph_release_id: $graph_release_id}) "
        "WITH nodes, [item IN collect(r) WHERE item IS NOT NULL] "
        "AS relationships RETURN size(nodes) AS node_count, "
        "size(relationships) AS edge_count, "
        "reduce(total = 0, item IN nodes | total + size(keys(item)) - 6) + "
        "reduce(total = 0, item IN relationships | "
        "total + size(keys(item)) - 5) AS property_count, "
        "size([item IN nodes WHERE item.namespace = 'realized']) "
        "AS realized_node_count, "
        "size([item IN relationships WHERE item.namespace = 'realized']) "
        "AS realized_edge_count ORDER BY node_count LIMIT $limit"
    ),
}

EXPECTED_QUERY_ROWS: dict[str, list[dict[str, object]]] = {
    "strategy-decomposition-v1": [
        {
            "bundle_id": "bundle:fixture:core:v1",
            "preset_id": "admission:fixture:core:v1",
            "preset_kind": "AdmissionPreset",
            "relationship": "ADMITTED_BY",
        },
        {
            "bundle_id": "bundle:fixture:core:v1",
            "preset_id": "fill:fixture:core:v1",
            "preset_kind": "FillPreset",
            "relationship": "DERIVED_FROM",
        },
        {
            "bundle_id": "bundle:fixture:core:v1",
            "preset_id": "retrieval:fixture:core:v1",
            "preset_kind": "RetrievalPreset",
            "relationship": "SELECTED_BY",
        },
    ],
    "lineup-funnel-v1": [
        {
            "run_id": "run:fixture:core:v1",
            "bundle_id": "bundle:fixture:core:v1",
            "book_id": "book:fixture:core:v1",
            "entry_budget": 14,
        },
    ],
    "release-lineage-v1": [
        {
            "anchor_id": "science:fixture:core:v1",
            "neighbor_id": "source:fixture:core:terminal",
            "neighbor_kind": "SourceArtifact",
            "relationship": "USES_SOURCE",
            "direction": "out",
        },
    ],
    "trait-enrichment-v1": [
        {
            "lineup_id": "lineup:fixture:core:001",
            "trait_id": "trait:fixture:core:structural-stack",
            "trait_name": "synthetic structural stack",
            "trait_value": 1.0,
        },
    ],
    "cohort-compare-v1": [
        {
            "lineup_id": "lineup:fixture:core:001",
            "cohort_id": "cohort:fixture:core:prospective-structure",
            "cohort_name": "synthetic prospective structure",
            "membership_reason": "synthetic prospective structural fixture",
        },
    ],
    "matchup-exposure-v1": [
        {
            "player_id": "player:fixture:core:wr1",
            "defender_id": "player:fixture:core:cb1",
            "method_id": "fixture-coverage-map-v1",
            "confidence": 0.6,
            "qualified_inferred": True,
        },
    ],
    "lineup-network-v1": [
        {
            "lineup_id": "lineup:fixture:core:001",
            "neighbor_id": "player:fixture:core:wr1",
            "neighbor_kind": "PlayerSlate",
            "relationship": "CONTAINS_PLAYER",
            "direction": "out",
        },
        {
            "lineup_id": "lineup:fixture:core:001",
            "neighbor_id": "trait:fixture:core:structural-stack",
            "neighbor_kind": "Trait",
            "relationship": "HAS_TRAIT",
            "direction": "out",
        },
        {
            "lineup_id": "lineup:fixture:core:001",
            "neighbor_id": "book:fixture:core:v1",
            "neighbor_kind": "SelectedBook",
            "relationship": "MEMBER_OF_BOOK",
            "direction": "out",
        },
        {
            "lineup_id": "lineup:fixture:core:001",
            "neighbor_id": "cohort:fixture:core:prospective-structure",
            "neighbor_kind": "Cohort",
            "relationship": "MEMBER_OF_COHORT",
            "direction": "out",
        },
    ],
    "source-quality-v1": [
        {
            "artifact_id": "source:fixture:core:terminal",
            "generation": "1788000000000002",
            "sha256": "4c34671e222357bcd3693b05b1dca20c7116d499d30dc08bfd365031c25655d9",
            "bytes": 924,
            "receipt_id": "receipt:fixture:core:v1:terminal",
        },
        {
            "artifact_id": "source:fixture:r6:terminal",
            "generation": "1788000000000003",
            "sha256": "28cf1cbc1d27aa462ff3ad212be6336f96980c9c55da0b7ddb8d6b8da8546eec",
            "bytes": 897,
            "receipt_id": "receipt:fixture:r6:v1:terminal",
        },
        {
            "artifact_id": "source:fixture:t230:terminal",
            "generation": "1788000000000001",
            "sha256": "3bce75a17782a3946cc4954c02e91d2751d48d6ac2b988bd567ecb6bfb527021",
            "bytes": 924,
            "receipt_id": "receipt:fixture:t230:v1:terminal",
        },
    ],
    "promotion-evidence-gaps-v1": [
        {
            "decision_id": "decision:fixture:core:v1",
            "bundle_id": "bundle:fixture:core:v1",
            "disposition": "withheld-evidence-gap",
            "evidence_tier": "synthetic-fixture",
        },
        {
            "decision_id": "decision:fixture:r6:v1",
            "bundle_id": "bundle:fixture:r6:v1",
            "disposition": "withheld-evidence-gap",
            "evidence_tier": "synthetic-fixture",
        },
        {
            "decision_id": "decision:fixture:t230:v1",
            "bundle_id": "bundle:fixture:t230:v1",
            "disposition": "withheld-evidence-gap",
            "evidence_tier": "synthetic-fixture",
        },
    ],
    "terminal-census-v1": [
        {
            "node_count": 57,
            "edge_count": 54,
            "property_count": 342,
            "realized_node_count": 0,
            "realized_edge_count": 0,
        },
    ],
}


def _bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _rehash(value: dict[str, object], field: str) -> dict[str, object]:
    body = dict(value)
    body.pop(field, None)
    body[field] = graph.canonical_sha256(body)
    return body


def _recoded_terminal(
    artifact: adapter.ExactFixtureArtifact, **changes: object
) -> tuple[bytes, dict[str, object]]:
    receipt = json.loads(artifact.raw)
    receipt.update(changes)
    receipt = _rehash(receipt, "terminal_payload_sha256")
    raw = _bytes(receipt)
    identity = {
        **artifact.identity,
        "generation": str(int(str(artifact.identity["generation"])) + 100),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    return raw, identity


def _projection() -> tuple[
    dict[str, object], adapter.InMemoryExactArtifactSource
]:
    return adapter.canonical_fixture_projection()


def _terminal(
    manifest: dict[str, object], source: adapter.ExactArtifactSource
) -> tuple[tuple[dict[str, object], dict[str, object]], ...]:
    return adapter.read_terminal_fixtures(manifest, source)


def _artifact_identity(
    *, uri: str, generation: str, raw: bytes,
) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _predecessor_artifact() -> adapter.ExactFixtureArtifact:
    terminals = adapter.fixture_terminal_artifacts()
    source = adapter.InMemoryExactArtifactSource(terminals)
    manifest = adapter.prepare_projection_manifest(
        terminal_receipts=[item.identity for item in terminals],
        graph_release_id="graph-release:fixture-phase4-predecessor",
    )
    rebuild = adapter.rebuild_fixture_projection(manifest, source)
    raw = _bytes(rebuild.terminal_receipt)
    return adapter.ExactFixtureArtifact(
        identity=_artifact_identity(
            uri=(
                "gs://synthetic-fixture.invalid/foundry/rebuild/"
                "phase4-predecessor.json"
            ),
            generation="1788000000000100",
            raw=raw,
        ),
        raw=raw,
    )


def test_exact_synthetic_terminal_source_binds_all_three_chains() -> None:
    artifacts = adapter.fixture_terminal_artifacts()
    assert len(artifacts) == 3
    assert {json.loads(item.raw)["chain"] for item in artifacts} == {
        "t230", "core", "r6",
    }
    source = adapter.InMemoryExactArtifactSource(artifacts)
    for artifact in artifacts:
        assert str(artifact.identity["uri"]).startswith(
            "gs://synthetic-fixture.invalid/"
        )
        assert source.read_exact(artifact.identity) == artifact.raw
        receipt = adapter.validate_terminal_fixture_receipt(
            artifact.raw, artifact.identity
        )
        assert receipt["publication_mode"] == "synthetic-fixture"
        assert receipt["terminal_state"] == "accepted-terminal"
        assert receipt["accepted_task_count"] == receipt["task_count"]
        assert receipt["uses_realized_outcomes"] is False
        assert receipt["outcome_release_id"] is None


def test_source_has_no_uri_only_latest_or_conflicting_fallback() -> None:
    artifact = adapter.fixture_terminal_artifacts()[0]
    bad_raw = artifact.raw + b" "
    with pytest.raises(ERRORS, match="differ"):
        adapter.InMemoryExactArtifactSource((
            adapter.ExactFixtureArtifact(artifact.identity, bad_raw),
        ))
    duplicate = adapter.ExactFixtureArtifact(dict(artifact.identity), artifact.raw)
    with pytest.raises(ERRORS, match="duplicate"):
        adapter.InMemoryExactArtifactSource((artifact, duplicate))
    source = adapter.InMemoryExactArtifactSource((artifact,))
    wrong_generation = {
        **artifact.identity,
        "generation": str(int(str(artifact.identity["generation"])) + 1),
    }
    with pytest.raises(ERRORS, match="unavailable"):
        source.read_exact(wrong_generation)


def test_terminal_semantic_tampering_fails_even_with_rehashed_exact_bytes() -> None:
    artifact = adapter.fixture_terminal_artifacts()[0]
    cases = (
        ({"terminal_state": "working"}, "terminal"),
        ({"accepted_task_count": 1}, "incomplete"),
        ({"uses_realized_outcomes": True}, "outcomes"),
        ({"outcome_release_id": "outcome:fixture:t230:v1"}, "outcomes"),
        ({"strategy_bundle_id": "bundle:fixture:t230:winner"}, "outcome"),
    )
    for changes, message in cases:
        raw, identity = _recoded_terminal(artifact, **changes)
        with pytest.raises(ERRORS, match=message):
            adapter.validate_terminal_fixture_receipt(raw, identity)


def test_noncanonical_receipt_bytes_and_object_identity_shapes_fail() -> None:
    artifact = adapter.fixture_terminal_artifacts()[0]
    noncanonical = json.dumps(json.loads(artifact.raw), indent=2).encode()
    identity = {
        **artifact.identity,
        "generation": "999",
        "sha256": sha256(noncanonical).hexdigest(),
        "bytes": len(noncanonical),
    }
    with pytest.raises(ERRORS, match="canonical"):
        adapter.validate_terminal_fixture_receipt(noncanonical, identity)
    with pytest.raises(ERRORS, match="synthetic fixture"):
        adapter.validate_object_identity({
            **artifact.identity, "uri": "gs:///missing-bucket",
        })
    with pytest.raises(ERRORS, match="synthetic fixture"):
        adapter.validate_object_identity({
            **artifact.identity, "uri": "gs://production-bucket/receipt.json",
        })
    with pytest.raises(ERRORS, match="keys differ"):
        adapter.validate_object_identity({**artifact.identity, "latest": True})


def test_receipt_byte_bound_is_enforced_before_exact_source_read() -> None:
    artifact = adapter.fixture_terminal_artifacts()[0]

    class SpySource:
        def __init__(self) -> None:
            self.calls = 0

        def read_exact(self, _identity: object) -> bytes:
            self.calls += 1
            raise AssertionError("oversized identity reached exact source")

    source = SpySource()
    oversized = {
        **artifact.identity,
        "bytes": adapter.MAX_RECEIPT_BYTES + 1,
    }
    with pytest.raises(ERRORS, match="receipt bound"):
        adapter.read_rebuild_receipt(oversized, source)
    assert source.calls == 0


def test_schema_and_loader_catalogs_are_exact_versioned_contracts() -> None:
    schema = adapter.schema_contract()
    loader = adapter.loader_query_catalog()
    assert adapter.validate_schema_contract(schema) == schema
    assert adapter.validate_loader_query_catalog(loader) == loader
    assert len(schema["migrations"]) == 4
    edge_constraint = next(
        row for row in schema["migrations"]
        if row["item_id"] == "constraint-foundry-edge-key-v1"
    )
    assert "REQUIRE r.edge_key IS UNIQUE" in edge_constraint["cypher"]
    assert [row["item_id"] for row in loader["queries"]] == [
        "load-nodes-v1", "load-edges-v1",
    ]
    for row in loader["queries"]:
        assert "row_sha256" in row["preflight_cypher"]
        assert "row_sha256" in row["write_cypher"]
        assert "conflict_count" in row["preflight_cypher"]
        assert "conflict_count" in row["write_cypher"]
        assert row["deadline_ms"] == adapter.MAX_LOAD_DEADLINE_MS
        assert row["execution_contract"] == {
            "mode": "explicit-single-batch-write-transaction",
            "driver_deadline_required": True,
            "preflight_before_write_required": True,
            "exact_result_shape_required": True,
            "commit_only_after_exact_counts": True,
            "rollback_on_conflict_timeout_or_error": True,
            "transaction_identity": "loader_query_id+ordinal",
        }
    edge_loader = next(
        row for row in loader["queries"] if row["item_id"] == "load-edges-v1"
    )
    assert "OPTIONAL MATCH ()-[existing:FoundryRelation" in edge_loader[
        "preflight_cypher"
    ]
    assert edge_loader["identity_constraint_id"] == (
        "constraint-foundry-edge-key-v1"
    )
    node_loader = next(
        row for row in loader["queries"] if row["item_id"] == "load-nodes-v1"
    )
    expected_null_fragments = {
        "load-nodes-v1": (
            "n.node_key IS NULL OR", "n.graph_release_id IS NULL OR",
            "n.node_id IS NULL OR", "n.kind IS NULL OR",
            "n.namespace IS NULL OR", "n.row_sha256 IS NULL OR",
            "n[key] IS NULL OR",
        ),
        "load-edges-v1": (
            "r.edge_key IS NULL OR", "startNode(r).node_key IS NULL OR",
            "endNode(r).node_key IS NULL OR",
            "r.graph_release_id IS NULL OR",
            "r.relationship IS NULL OR", "r.namespace IS NULL OR",
            "r.row_sha256 IS NULL OR", "r[key] IS NULL OR",
        ),
    }
    for item in (node_loader, edge_loader):
        for field in ("preflight_cypher", "write_cypher"):
            assert all(
                fragment in item[field]
                for fragment in expected_null_fragments[item["item_id"]]
            )
    tampered = json.loads(_bytes(schema))
    tampered["migrations"][0]["cypher"] += " DROP DATABASE neo4j"
    tampered = _rehash(tampered, "schema_contract_sha256")
    with pytest.raises(ERRORS, match="frozen"):
        adapter.validate_schema_contract(tampered)


def test_loader_catalog_rejects_null_unsafe_conflict_predicate() -> None:
    catalog = json.loads(_bytes(adapter.loader_query_catalog()))
    node = catalog["queries"][0]
    node["preflight_cypher"] = node["preflight_cypher"].replace(
        "n.row_sha256 IS NULL OR ", "", 1
    )
    node = _rehash(node, "statement_sha256")
    catalog["queries"][0] = node
    catalog = _rehash(catalog, "loader_catalog_sha256")
    with pytest.raises(ERRORS, match="not null-safe"):
        adapter.validate_loader_query_catalog(catalog)


def test_read_query_catalog_is_bounded_parameterized_and_read_only() -> None:
    catalog = adapter.read_query_catalog()
    assert adapter.validate_read_query_catalog(catalog) == catalog
    assert {row["query_id"] for row in catalog["queries"]} == {
        "strategy-decomposition-v1", "lineup-funnel-v1",
        "release-lineage-v1", "trait-enrichment-v1", "cohort-compare-v1",
        "matchup-exposure-v1", "lineup-network-v1", "source-quality-v1",
        "promotion-evidence-gaps-v1", "terminal-census-v1",
    }
    for query in catalog["queries"]:
        assert query["max_rows"] <= adapter.MAX_QUERY_ROWS
        assert query["deadline_ms"] <= adapter.MAX_QUERY_DEADLINE_MS
        assert query["execution_contract"] == {
            "mode": "explicit-read-transaction",
            "driver_deadline_required": True,
            "deadline_ms": query["deadline_ms"],
            "exact_parameter_set_required": True,
            "exact_result_fields_required": True,
            "rollback_on_timeout_or_schema_mismatch": True,
        }
        assert "$graph_release_id" in query["cypher"]
        assert query["cypher"].endswith("LIMIT $limit")
    source_query = next(
        row for row in catalog["queries"] if row["query_id"] == "source-quality-v1"
    )
    assert "artifact.uri AS uri" not in source_query["cypher"]


def test_read_catalog_rejects_rehashed_write_query_and_arbitrary_id() -> None:
    catalog = json.loads(_bytes(adapter.read_query_catalog()))
    catalog["queries"][0]["cypher"] = (
        "MATCH (n:FoundryNode) CALL db.labels() RETURN n.node_id AS bundle_id "
        "ORDER BY bundle_id LIMIT $limit"
    )
    catalog["queries"][0] = _rehash(catalog["queries"][0], "query_sha256")
    catalog = _rehash(catalog, "query_catalog_sha256")
    with pytest.raises(ERRORS, match="read-only"):
        adapter.validate_read_query_catalog(catalog)
    manifest, source = _projection()
    rebuild = adapter.rebuild_fixture_projection(manifest, source)
    with pytest.raises(ERRORS, match="not in"):
        adapter.run_canonical_query(
            rebuild.state,
            query_id="arbitrary-cypher-v1",
            parameters={"graph_release_id": rebuild.state.graph_release_id, "limit": 1},
        )


def test_projection_manifest_binds_sorted_sources_catalogs_and_closed_scope() -> None:
    artifacts = adapter.fixture_terminal_artifacts()
    forward = adapter.prepare_projection_manifest(
        terminal_receipts=[item.identity for item in artifacts]
    )
    reverse = adapter.prepare_projection_manifest(
        terminal_receipts=[item.identity for item in reversed(artifacts)]
    )
    assert forward == reverse
    assert forward["outcome_scope"] == "closed"
    assert forward["predecessor_receipt_identity"] is None
    assert forward["graph_load_manifest"]["authorized_outcome_release_id"] is None
    assert forward["schema_contract_sha256"] == adapter.schema_contract()[
        "schema_contract_sha256"
    ]
    assert forward["query_catalog_sha256"] == adapter.read_query_catalog()[
        "query_catalog_sha256"
    ]
    assert adapter.validate_projection_manifest(forward) == forward


def test_exact_predecessor_identity_is_cross_bound_to_graph_manifest() -> None:
    terminals = adapter.fixture_terminal_artifacts()
    identities = [item.identity for item in terminals]
    predecessor = _predecessor_artifact()
    source = adapter.InMemoryExactArtifactSource((*terminals, predecessor))
    predecessor_receipt = adapter.read_rebuild_receipt(
        predecessor.identity, source
    )
    manifest = adapter.prepare_projection_manifest(
        terminal_receipts=identities,
        predecessor_receipt_identity=predecessor.identity,
        predecessor_source=source,
    )
    assert manifest["predecessor_receipt_identity"] == predecessor.identity
    assert manifest["graph_load_manifest"]["predecessor_graph_release_id"] == (
        predecessor_receipt["graph_release_id"]
    )
    assert adapter.validate_projection_manifest(
        manifest, predecessor_source=source
    ) == manifest
    with pytest.raises(ERRORS, match="exact-read source"):
        adapter.validate_projection_manifest(manifest)
    with pytest.raises(ERRORS, match="supplied together"):
        adapter.prepare_projection_manifest(
            terminal_receipts=identities,
            predecessor_receipt_identity=predecessor.identity,
        )
    with pytest.raises(ERRORS, match="keys differ"):
        adapter.prepare_projection_manifest(
            terminal_receipts=identities,
            predecessor_receipt_identity={
                "graph_release_id": "graph-release:caller-assertion",
                "rebuild_receipt_sha256": "ab" * 32,
                "terminal_census_sha256": "cd" * 32,
                "query_bundle_sha256": "ef" * 32,
            },
            predecessor_source=source,
        )
    tampered = json.loads(_bytes(manifest))
    tampered["graph_load_manifest"]["predecessor_graph_release_id"] = (
        "graph-release:other"
    )
    tampered["graph_load_manifest"] = _rehash(
        tampered["graph_load_manifest"], "manifest_sha256"
    )
    tampered = _rehash(tampered, "projection_manifest_sha256")
    with pytest.raises(ERRORS, match="predecessor"):
        adapter.validate_projection_manifest(tampered, predecessor_source=source)


def test_predecessor_manifest_rebuilds_end_to_end_and_reopens_exact_receipt() -> None:
    terminals = adapter.fixture_terminal_artifacts()
    predecessor = _predecessor_artifact()
    exact_source = adapter.InMemoryExactArtifactSource((*terminals, predecessor))
    manifest = adapter.prepare_projection_manifest(
        terminal_receipts=[item.identity for item in terminals],
        predecessor_receipt_identity=predecessor.identity,
        predecessor_source=exact_source,
    )
    rebuild = adapter.rebuild_fixture_projection(
        manifest,
        exact_source,
        predecessor_source=exact_source,
    )
    assert rebuild.state.census()["node_count"] == 57
    assert rebuild.terminal_receipt["uses_realized_outcomes"] is False
    assert adapter.validate_rebuild_receipt(
        rebuild.terminal_receipt,
        projection_manifest=manifest,
        load_plan=rebuild.load_plan,
        checkpoints=rebuild.checkpoints,
        query_results=rebuild.query_results,
        predecessor_source=exact_source,
    ) == rebuild.terminal_receipt

    with pytest.raises(ERRORS, match="exact-read source"):
        adapter.rebuild_fixture_projection(manifest, exact_source)

    class SubstitutingSource:
        def read_exact(self, _identity: object) -> bytes:
            return terminals[0].raw

    with pytest.raises(ERRORS, match="bytes differ from exact identity"):
        adapter.rebuild_fixture_projection(
            manifest,
            exact_source,
            predecessor_source=SubstitutingSource(),
        )


def test_projection_manifest_cannot_open_realized_with_a_rehashed_flag() -> None:
    manifest, _ = _projection()
    tampered = json.loads(_bytes(manifest))
    tampered["outcome_scope"] = "realized"
    tampered = _rehash(tampered, "projection_manifest_sha256")
    with pytest.raises(ERRORS, match="outcome scope"):
        adapter.validate_projection_manifest(tampered)


def test_terminal_adapter_emits_only_positive_outcome_free_rows() -> None:
    manifest, source = _projection()
    terminal = _terminal(manifest, source)
    nodes, edges = adapter.project_fixture_rows(terminal)
    assert len(nodes) == 57
    assert len(edges) == 54
    assert not {row["kind"] for row in nodes} & graph.OUTCOME_NODE_KINDS
    assert not {row["relationship"] for row in edges} & graph.OUTCOME_RELATIONSHIP_TYPES
    assert all(row["namespace"] != "realized" for row in (*nodes, *edges))
    for row in nodes:
        graph.validate_node_row(row)
    for row in edges:
        graph.validate_edge_row(row)


def test_streaming_loader_does_not_call_phase3_full_plan_materializers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, source = _projection()

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Phase 4 loader called a full-plan materializer")

    monkeypatch.setattr(graph, "iter_load_batches", forbidden)
    monkeypatch.setattr(graph, "build_load_plan", forbidden)
    rebuild = adapter.rebuild_fixture_projection(manifest, source)
    assert rebuild.state.census()["node_count"] == 57
    assert "rows" not in str(rebuild.load_plan)


def test_transactions_are_release_bound_nodes_first_and_strictly_bounded() -> None:
    manifest, source = _projection()
    terminal = _terminal(manifest, source)
    transactions = list(adapter.iter_fixture_load_transactions(
        projection_manifest=manifest, terminal=terminal
    ))
    assert [row["loader_query_id"] for row in transactions] == [
        "load-nodes-v1", "load-edges-v1",
    ]
    assert [row["row_count"] for row in transactions] == [57, 54]
    for transaction in transactions:
        assert transaction["row_count"] <= graph.BATCH_SIZE
        assert adapter.validate_load_transaction(transaction, manifest) == transaction
        assert all(
            row["graph_release_id"] == adapter.FIXTURE_GRAPH_RELEASE_ID
            for row in transaction["rows"]
        )
        assert all(
            str(row.get("node_key", row.get("edge_key"))).startswith(
                adapter.FIXTURE_GRAPH_RELEASE_ID + "|"
            )
            for row in transaction["rows"]
        )


def test_duplicate_identity_inside_one_transaction_is_rejected() -> None:
    manifest, source = _projection()
    terminal = _terminal(manifest, source)
    nodes, _ = adapter.project_fixture_rows(terminal)
    with pytest.raises(ERRORS, match="duplicate"):
        adapter.build_load_transaction(
            projection_manifest=manifest,
            loader_query_id="load-nodes-v1",
            ordinal=0,
            logical_rows=(nodes[0], nodes[0]),
        )


def test_transaction_cannot_cross_release_even_after_rehashing() -> None:
    manifest, source = _projection()
    terminal = _terminal(manifest, source)
    transaction = next(adapter.iter_fixture_load_transactions(
        projection_manifest=manifest, terminal=terminal
    ))
    tampered = json.loads(_bytes(transaction))
    tampered["graph_release_id"] = "graph-release:other"
    tampered = _rehash(tampered, "transaction_sha256")
    with pytest.raises(ERRORS, match="release or contract"):
        adapter.validate_load_transaction(tampered, manifest)


def test_manifest_namespace_allowlist_governs_every_transaction_row() -> None:
    manifest, source = _projection()
    terminal = _terminal(manifest, source)
    nodes, _ = adapter.project_fixture_rows(terminal)
    narrowed = json.loads(_bytes(manifest))
    narrowed["graph_load_manifest"]["allowed_namespaces"].remove("trait")
    narrowed["graph_load_manifest"] = _rehash(
        narrowed["graph_load_manifest"], "manifest_sha256"
    )
    narrowed = _rehash(narrowed, "projection_manifest_sha256")
    assert adapter.validate_projection_manifest(narrowed) == narrowed
    with pytest.raises(ERRORS, match="outside the projection manifest"):
        adapter.build_load_transaction(
            projection_manifest=narrowed,
            loader_query_id="load-nodes-v1",
            ordinal=0,
            logical_rows=nodes,
        )


def test_same_query_ordinal_changed_content_is_a_transaction_conflict() -> None:
    manifest, source = _projection()
    terminal = _terminal(manifest, source)
    original = next(adapter.iter_fixture_load_transactions(
        projection_manifest=manifest, terminal=terminal
    ))
    state = adapter.OfflineGraphState(manifest)
    state.apply(original)
    logical = adapter.project_fixture_rows(terminal)[0][0]
    changed = json.loads(_bytes(logical))
    changed["properties"]["byte_count"] += 1
    replacement = adapter.build_load_transaction(
        projection_manifest=manifest,
        loader_query_id="load-nodes-v1",
        ordinal=0,
        logical_rows=(changed,),
    )
    assert original["batch_id"] == replacement["batch_id"] == "load-nodes-v1:0"
    assert original["transaction_sha256"] != replacement["transaction_sha256"]
    before = state.state_sha256()
    with pytest.raises(ERRORS, match="transaction identity conflicts"):
        state.apply(replacement)
    assert state.state_sha256() == before


def test_identical_reload_creates_zero_rows_and_preserves_all_hashes() -> None:
    manifest, source = _projection()
    terminal = _terminal(manifest, source)
    rebuild = adapter.rebuild_fixture_projection(manifest, source)
    census = rebuild.state.census()
    state_hash = rebuild.state.state_sha256()
    query_hashes = {
        row["query_id"]: row["result_sha256"] for row in rebuild.query_results
    }
    replay = tuple(
        rebuild.state.apply(transaction)
        for transaction in adapter.iter_fixture_load_transactions(
            projection_manifest=manifest, terminal=terminal
        )
    )
    assert all(row["disposition"] == "replayed" for row in replay)
    assert all(row["inserted_count"] == 0 for row in replay)
    assert rebuild.state.census() == census
    assert rebuild.state.state_sha256() == state_hash
    parameters = adapter.canonical_query_parameters(
        terminal, graph_release_id=rebuild.state.graph_release_id
    )
    assert {
        query_id: adapter.run_canonical_query(
            rebuild.state, query_id=query_id, parameters=params
        )["result_sha256"]
        for query_id, params in parameters.items()
    } == query_hashes


def test_checkpoint_and_terminal_receipts_are_bounded_descriptor_only_evidence() -> None:
    manifest, source = _projection()
    rebuild = adapter.rebuild_fixture_projection(manifest, source)
    assert len(rebuild.checkpoints) == 2
    assert [row["loader_query_id"] for row in rebuild.checkpoints] == [
        "load-nodes-v1", "load-edges-v1",
    ]
    assert all(row["disposition"] == "applied" for row in rebuild.checkpoints)
    assert all(row["uses_realized_outcomes"] is False for row in rebuild.checkpoints)
    assert all(
        adapter.validate_checkpoint_receipt(row, manifest) == row
        for row in rebuild.checkpoints
    )
    assert "rows" not in json.dumps(rebuild.load_plan)
    assert adapter.validate_stream_load_plan(
        rebuild.load_plan, manifest, checkpoints=rebuild.checkpoints
    ) == rebuild.load_plan
    terminal = rebuild.terminal_receipt
    assert terminal["source_count"] == 3
    assert terminal["batch_count"] == 2
    assert terminal["outcome_scope"] == "closed"
    assert terminal["uses_realized_outcomes"] is False
    assert terminal["terminal_census_sha256"] == graph.canonical_sha256(
        terminal["terminal_census"]
    )
    assert adapter.validate_rebuild_receipt(
        terminal,
        projection_manifest=manifest,
        load_plan=rebuild.load_plan,
        checkpoints=rebuild.checkpoints,
        query_results=rebuild.query_results,
    ) == terminal


def test_receipt_validators_reject_semantic_tampering_after_rehash() -> None:
    manifest, source = _projection()
    rebuild = adapter.rebuild_fixture_projection(manifest, source)

    checkpoint = json.loads(_bytes(rebuild.checkpoints[0]))
    checkpoint["uses_realized_outcomes"] = True
    checkpoint = _rehash(checkpoint, "checkpoint_sha256")
    with pytest.raises(ERRORS, match="outcome binding"):
        adapter.validate_checkpoint_receipt(checkpoint, manifest)

    plan = json.loads(_bytes(rebuild.load_plan))
    plan["node_batch_index"][0]["batch_id"] = "load-nodes-v1:99"
    plan = _rehash(plan, "plan_sha256")
    with pytest.raises(ERRORS, match="identity or count"):
        adapter.validate_stream_load_plan(plan, manifest)

    terminal = json.loads(_bytes(rebuild.terminal_receipt))
    terminal["uses_realized_outcomes"] = True
    terminal = _rehash(terminal, "rebuild_receipt_sha256")
    with pytest.raises(ERRORS, match="outcome binding"):
        adapter.validate_rebuild_receipt(terminal)


def test_query_result_validator_rejects_coherently_rehashed_bad_bodies() -> None:
    manifest, source = _projection()
    terminal = _terminal(manifest, source)
    rebuild = adapter.rebuild_fixture_projection(manifest, source)
    parameters = adapter.canonical_query_parameters(
        terminal, graph_release_id=rebuild.state.graph_release_id
    )
    network = next(
        row for row in rebuild.query_results
        if row["query_id"] == "lineup-network-v1"
    )
    assert adapter.validate_query_result(
        network,
        graph_release_id=rebuild.state.graph_release_id,
        expected_parameters=parameters["lineup-network-v1"],
    ) == network

    out_of_order = json.loads(_bytes(network))
    out_of_order["rows"] = list(reversed(out_of_order["rows"]))
    out_of_order = _rehash(out_of_order, "result_sha256")
    with pytest.raises(ERRORS, match="ordering"):
        adapter.validate_query_result(
            out_of_order,
            graph_release_id=rebuild.state.graph_release_id,
            expected_parameters=parameters["lineup-network-v1"],
        )

    rebound = json.loads(_bytes(network))
    rebound["parameters"]["lineup_id"] = "lineup:fixture:r6:001"
    rebound = _rehash(rebound, "result_sha256")
    with pytest.raises(ERRORS, match="expected fixture"):
        adapter.validate_query_result(
            rebound,
            graph_release_id=rebuild.state.graph_release_id,
            expected_parameters=parameters["lineup-network-v1"],
        )

    wrong_count = json.loads(_bytes(network))
    wrong_count["row_count"] += 1
    wrong_count = _rehash(wrong_count, "result_sha256")
    with pytest.raises(ERRORS, match="count differs"):
        adapter.validate_query_result(
            wrong_count, graph_release_id=rebuild.state.graph_release_id
        )

    oversized = json.loads(_bytes(network))
    oversized["rows"][0]["neighbor_id"] = "x" * (128 * 1024)
    oversized = _rehash(oversized, "result_sha256")
    with pytest.raises(ERRORS, match="byte bound"):
        adapter.validate_query_result(
            oversized, graph_release_id=rebuild.state.graph_release_id
        )


def test_rebuild_validator_rejects_coherent_bad_query_result_digest_bundle() -> None:
    manifest, source = _projection()
    rebuild = adapter.rebuild_fixture_projection(manifest, source)
    altered_results = [json.loads(_bytes(row)) for row in rebuild.query_results]
    network = next(
        row for row in altered_results if row["query_id"] == "lineup-network-v1"
    )
    network["rows"] = list(reversed(network["rows"]))
    network.update(_rehash(network, "result_sha256"))

    terminal = json.loads(_bytes(rebuild.terminal_receipt))
    terminal["query_result_sha256s"]["lineup-network-v1"] = network[
        "result_sha256"
    ]
    terminal["query_bundle_sha256"] = graph.canonical_sha256({
        "query_catalog_sha256": terminal["query_catalog_sha256"],
        "query_result_sha256s": terminal["query_result_sha256s"],
    })
    terminal = _rehash(terminal, "rebuild_receipt_sha256")
    with pytest.raises(ERRORS, match="ordering"):
        adapter.validate_rebuild_receipt(
            terminal,
            projection_manifest=manifest,
            load_plan=rebuild.load_plan,
            checkpoints=rebuild.checkpoints,
            query_results=altered_results,
        )


def test_node_conflict_rejects_atomically_without_state_change() -> None:
    manifest, source = _projection()
    rebuild = adapter.rebuild_fixture_projection(manifest, source)
    before_census = rebuild.state.census()
    before_hash = rebuild.state.state_sha256()
    lineup = next(
        row for row in rebuild.state.node_rows() if row["kind"] == "Lineup"
    )
    conflicting = json.loads(_bytes(lineup))
    conflicting["properties"]["salary"] = 40_000
    transaction = adapter.build_load_transaction(
        projection_manifest=manifest, loader_query_id="load-nodes-v1",
        ordinal=1, logical_rows=(conflicting,),
    )
    with pytest.raises(ERRORS, match="conflicting persisted node"):
        rebuild.state.apply(transaction)
    assert rebuild.state.census() == before_census
    assert rebuild.state.state_sha256() == before_hash


def test_edge_conflict_and_edge_before_nodes_are_atomic_failures() -> None:
    manifest, source = _projection()
    terminal = _terminal(manifest, source)
    transactions = list(adapter.iter_fixture_load_transactions(
        projection_manifest=manifest, terminal=terminal
    ))
    fresh = adapter.OfflineGraphState(manifest)
    with pytest.raises(ERRORS, match="endpoint"):
        fresh.apply(transactions[1])
    assert fresh.census()["node_count"] == 0
    rebuild = adapter.rebuild_fixture_projection(manifest, source)
    before = rebuild.state.state_sha256()
    membership = next(
        row for row in rebuild.state.edge_rows()
        if row["relationship"] == "MEMBER_OF_BOOK"
    )
    conflicting = json.loads(_bytes(membership))
    conflicting["properties"]["ordinal"] = 1
    transaction = adapter.build_load_transaction(
        projection_manifest=manifest, loader_query_id="load-edges-v1",
        ordinal=1, logical_rows=(conflicting,),
    )
    with pytest.raises(ERRORS, match="conflicting persisted edge"):
        rebuild.state.apply(transaction)
    assert rebuild.state.state_sha256() == before


def test_canonical_queries_are_catalog_bound_bounded_and_sanitized() -> None:
    manifest, source = _projection()
    terminal = _terminal(manifest, source)
    rebuild = adapter.rebuild_fixture_projection(manifest, source)
    parameters = adapter.canonical_query_parameters(
        terminal, graph_release_id=rebuild.state.graph_release_id
    )
    results = {
        query_id: adapter.run_canonical_query(
            rebuild.state, query_id=query_id, parameters=params
        )
        for query_id, params in parameters.items()
    }
    assert set(results) == {
        row["query_id"] for row in adapter.read_query_catalog()["queries"]
    }
    assert {
        row["query_id"]: row["cypher"]
        for row in adapter.read_query_catalog()["queries"]
    } == EXPECTED_QUERY_CYPHER
    assert {
        query_id: result["rows"] for query_id, result in results.items()
    } == EXPECTED_QUERY_ROWS
    assert all(result["row_count"] > 0 for result in results.values())
    assert all(
        result["query_catalog_sha256"]
        == adapter.read_query_catalog()["query_catalog_sha256"]
        for result in results.values()
    )
    assert "gs://" not in json.dumps(results["source-quality-v1"])
    census_row = results["terminal-census-v1"]["rows"][0]
    assert census_row["realized_node_count"] == 0
    assert census_row["realized_edge_count"] == 0
    assert results["matchup-exposure-v1"]["rows"][0][
        "qualified_inferred"
    ] is True


def test_terminal_census_reports_injected_realized_namespace_contamination() -> None:
    manifest, source = _projection()
    terminal = _terminal(manifest, source)
    rebuild = adapter.rebuild_fixture_projection(manifest, source)
    outcome_id = "outcome-grade:fixture:contamination"
    outcome_key = f"{rebuild.state.graph_release_id}|{outcome_id}"
    rebuild.state._nodes[outcome_key] = {  # noqa: SLF001 - corruption oracle.
        "kind": "OutcomeGrade",
        "node_id": outcome_id,
        "namespace": "realized",
        "properties": {},
    }
    lineup_id = "lineup:fixture:core:001"
    edge_key = (
        f"{rebuild.state.graph_release_id}|realized|{lineup_id}|"
        f"GRADED_IN_CONTEST|{outcome_id}"
    )
    rebuild.state._edges[edge_key] = {  # noqa: SLF001 - corruption oracle.
        "relationship": "GRADED_IN_CONTEST",
        "source_id": lineup_id,
        "target_id": outcome_id,
        "namespace": "realized",
        "properties": {},
    }
    census = rebuild.state.census()
    assert census["realized_node_count"] == 1
    assert census["realized_edge_count"] == 1
    parameters = adapter.canonical_query_parameters(
        terminal, graph_release_id=rebuild.state.graph_release_id
    )["terminal-census-v1"]
    row = adapter.run_canonical_query(
        rebuild.state,
        query_id="terminal-census-v1",
        parameters=parameters,
    )["rows"][0]
    assert row["realized_node_count"] == 1
    assert row["realized_edge_count"] == 1


def test_promotion_evaluator_rejects_wrong_target_kind_like_frozen_cypher() -> None:
    manifest, source = _projection()
    terminal = _terminal(manifest, source)
    rebuild = adapter.rebuild_fixture_projection(manifest, source)
    decision_id = "decision:fixture:core:v1"
    wrong_target_id = "fill:fixture:core:v1"
    edge_key = (
        f"{rebuild.state.graph_release_id}|lineage|{decision_id}|"
        f"DECIDES_ON_BUNDLE|{wrong_target_id}"
    )
    rebuild.state._edges[edge_key] = {  # noqa: SLF001 - query parity oracle.
        "relationship": "DECIDES_ON_BUNDLE",
        "source_id": decision_id,
        "target_id": wrong_target_id,
        "namespace": "lineage",
        "properties": {},
    }
    parameters = adapter.canonical_query_parameters(
        terminal, graph_release_id=rebuild.state.graph_release_id
    )["promotion-evidence-gaps-v1"]
    result = adapter.run_canonical_query(
        rebuild.state,
        query_id="promotion-evidence-gaps-v1",
        parameters=parameters,
    )
    assert result["rows"] == EXPECTED_QUERY_ROWS["promotion-evidence-gaps-v1"]


def test_query_parameter_release_extra_and_limit_laws_fail_closed() -> None:
    manifest, source = _projection()
    terminal = _terminal(manifest, source)
    rebuild = adapter.rebuild_fixture_projection(manifest, source)
    params = adapter.canonical_query_parameters(
        terminal, graph_release_id=rebuild.state.graph_release_id
    )["lineup-network-v1"]
    with pytest.raises(ERRORS, match="parameters"):
        adapter.run_canonical_query(
            rebuild.state, query_id="lineup-network-v1",
            parameters={**params, "cypher": "MATCH (n) RETURN n"},
        )
    with pytest.raises(ERRORS, match="release"):
        adapter.run_canonical_query(
            rebuild.state, query_id="lineup-network-v1",
            parameters={**params, "graph_release_id": "graph-release:other"},
        )
    with pytest.raises(ERRORS, match="limit"):
        adapter.run_canonical_query(
            rebuild.state, query_id="lineup-network-v1",
            parameters={**params, "limit": adapter.MAX_QUERY_ROWS + 1},
        )


def test_zero_state_rebuilds_are_byte_stable_and_match_frozen_evidence() -> None:
    artifacts = adapter.fixture_terminal_artifacts()
    source_a = adapter.InMemoryExactArtifactSource(artifacts)
    source_b = adapter.InMemoryExactArtifactSource(tuple(reversed(artifacts)))
    manifest_a = adapter.prepare_projection_manifest(
        terminal_receipts=[item.identity for item in artifacts]
    )
    manifest_b = adapter.prepare_projection_manifest(
        terminal_receipts=[item.identity for item in reversed(artifacts)]
    )
    first = adapter.rebuild_fixture_projection(manifest_a, source_a)
    second = adapter.rebuild_fixture_projection(manifest_b, source_b)
    assert manifest_a == manifest_b
    assert first.state.census() == second.state.census()
    assert first.state.state_sha256() == second.state.state_sha256()
    assert first.load_plan == second.load_plan
    assert first.terminal_receipt == second.terminal_receipt
    assert adapter.schema_contract()["schema_contract_sha256"] == (
        EXPECTED_CONTRACT_HASHES["schema"]
    )
    assert adapter.loader_query_catalog()["loader_catalog_sha256"] == (
        EXPECTED_CONTRACT_HASHES["loader"]
    )
    assert adapter.read_query_catalog()["query_catalog_sha256"] == (
        EXPECTED_CONTRACT_HASHES["query_catalog"]
    )
    assert manifest_a["projection_manifest_sha256"] == (
        EXPECTED_CONTRACT_HASHES["manifest"]
    )
    assert first.load_plan["plan_sha256"] == EXPECTED_CONTRACT_HASHES["plan"]
    assert first.state.state_sha256() == EXPECTED_CONTRACT_HASHES["state"]
    assert first.terminal_receipt["query_bundle_sha256"] == (
        EXPECTED_CONTRACT_HASHES["query_bundle"]
    )
    assert first.terminal_receipt["rebuild_receipt_sha256"] == (
        EXPECTED_CONTRACT_HASHES["terminal"]
    )
    assert first.terminal_receipt["query_result_sha256s"] == EXPECTED_QUERY_HASHES
    assert first.state.census() == {
        "node_count": 57,
        "edge_count": 54,
        "property_count": 342,
        "node_kinds": {
            "AdmissionPreset": 3, "Cohort": 3, "Evaluation": 3,
            "ExperimentRun": 3, "FillPreset": 3, "Fold": 3,
            "Lineup": 3, "MetricSet": 3, "PlayerSlate": 6,
            "PromotionDecision": 3, "RetrievalPreset": 3,
            "ScienceRelease": 3, "SelectedBook": 3,
            "SourceArtifact": 3, "StrategyBundle": 3, "Trait": 3,
            "VerificationReceipt": 3, "VerifierRelease": 3,
        },
        "relationship_types": {
            "ADMITTED_BY": 3, "CONTAINS_PLAYER": 3,
            "DECIDES_ON_BUNDLE": 3, "DERIVED_FROM": 6,
            "EVALUATED_IN": 6, "EVALUATES_BUNDLE": 3,
            "GENERATED_BY": 3, "HAS_INFERRED_DEFENDER_EXPOSURE": 3,
            "HAS_METRIC": 3, "HAS_TRAIT": 3, "MEMBER_OF_BOOK": 3,
            "MEMBER_OF_COHORT": 3, "SELECTED_BY": 6, "USES_SOURCE": 6,
        },
        "namespaces": ["identity", "lineage", "membership", "metric", "trait"],
        "realized_node_count": 0,
        "realized_edge_count": 0,
    }


def test_router_main_frontend_and_live_transports_remain_outside_phase4() -> None:
    root = Path(__file__).resolve().parents[1]
    main_source = (root / "src/nfl_dfs/app/main.py").read_text()
    assert "corpus_graph_vnext_fixture_adapter" not in main_source
    module_source = (
        root / "src/nfl_dfs/research/corpus_graph_vnext_fixture_adapter.py"
    ).read_text()
    assert "neo4j.GraphDatabase" not in module_source
    assert "google.cloud" not in module_source
    assert "FixtureFoundryRepository" not in module_source
