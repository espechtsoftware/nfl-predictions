"""Focused offline tests for the graph-vNext contracts."""

from __future__ import annotations

import pytest

from nfl_dfs.research import corpus_graph_vnext_contracts as contracts


def _manifest(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": contracts.LOAD_MANIFEST_SCHEMA,
        "graph_schema_version": contracts.GRAPH_SCHEMA_VERSION,
        "graph_release_id": "graph-release-0001",
        "predecessor_graph_release_id": None,
        "allowed_namespaces": ["identity", "membership", "trait"],
        "source_releases": [
            {
                "uri": "gs://fixture/panel-index.json",
                "generation": "1788000000000201",
                "sha256": "ab" * 32,
                "bytes": 2_048,
            }
        ],
        "authorized_outcome_release_id": None,
        "created_at_utc": "2026-08-25T12:00:00Z",
    }
    base.update(overrides)
    return base


def _node(node_id: str, kind: str = "Lineup", **properties: object) -> dict[str, object]:
    return {
        "kind": kind,
        "node_id": node_id,
        "namespace": "identity",
        "properties": properties,
    }


def _edge(
    source: str,
    target: str,
    relationship: str = "CONTAINS_PLAYER",
    namespace: str = "membership",
    **properties: object,
) -> dict[str, object]:
    return {
        "relationship": relationship,
        "source_id": source,
        "target_id": target,
        "namespace": namespace,
        "properties": properties,
    }


def _plan(nodes: list[dict[str, object]], edges: list[dict[str, object]]):
    return contracts.build_load_plan(
        manifest=_manifest(), node_rows=nodes, edge_rows=edges
    )


def test_identical_content_in_any_order_yields_one_plan_hash() -> None:
    nodes = [
        _node("lineup:a", salary=49_500),
        _node("player:p1", kind="PlayerSlate", team="KC"),
    ]
    edges = [_edge("lineup:a", "player:p1")]
    forward = _plan(list(nodes), list(edges))
    reversed_plan = _plan(list(reversed(nodes)), list(edges))
    duplicated = _plan(nodes + [dict(nodes[0])], edges + [dict(edges[0])])
    assert forward["plan_sha256"] == reversed_plan["plan_sha256"]
    assert forward["plan_sha256"] == duplicated["plan_sha256"]
    census = forward["terminal_census"]
    assert census["node_count"] == 2
    assert census["edge_count"] == 1
    assert census["node_kinds"] == {"Lineup": 1, "PlayerSlate": 1}
    assert census["relationship_types"] == {"CONTAINS_PLAYER": 1}


def test_conflicting_identity_fails_closed() -> None:
    nodes = [_node("lineup:a", salary=49_500), _node("lineup:a", salary=1)]
    with pytest.raises(contracts.CorpusGraphVNextError, match="conflicting"):
        _plan(nodes, [])


def test_forbidden_and_unknown_vocabulary_fail() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="COVERED_BY"):
        contracts.validate_edge_row(
            _edge("a1", "b1", relationship="COVERED_BY")
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="not registered"):
        contracts.validate_node_row(_node("x1", kind="WorldMatrix"))
    with pytest.raises(contracts.CorpusGraphVNextError, match="allowlisted"):
        contracts.validate_node_row({**_node("x1"), "namespace": "wild"})


def test_inferred_exposure_must_stay_qualified() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="qualified"):
        contracts.validate_edge_row(
            _edge(
                "player:p1",
                "defender:d1",
                relationship="HAS_INFERRED_DEFENDER_EXPOSURE",
            )
        )
    edge = contracts.validate_edge_row(
        _edge(
            "player:p1",
            "defender:d1",
            relationship="HAS_INFERRED_DEFENDER_EXPOSURE",
            qualified_inferred=True,
        )
    )
    assert edge["properties"]["qualified_inferred"] is True


def test_realized_namespace_requires_authorized_outcome_release() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="OutcomeRelease"):
        contracts.validate_load_manifest(
            _manifest(allowed_namespaces=["identity", "realized"])
        )
    manifest = contracts.validate_load_manifest(
        _manifest(
            allowed_namespaces=["identity", "realized"],
            authorized_outcome_release_id="outcome-release-0001",
        )
    )
    assert manifest["authorized_outcome_release_id"] == "outcome-release-0001"


def test_outcome_properties_stay_inside_the_realized_namespace() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="realized"):
        contracts.validate_node_row(_node("lineup:a", realized_score=201))


def test_world_scale_arrays_and_secrets_never_enter_the_graph() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="elements"):
        contracts.validate_node_row(
            _node("lineup:a", scores=list(range(1000)))
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="forbidden"):
        contracts.validate_node_row(_node("lineup:a", api_key="value"))


def test_edges_require_loaded_endpoints() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="endpoint"):
        _plan([_node("lineup:a")], [_edge("lineup:a", "player:absent")])


def test_batches_stay_bounded_with_exact_census() -> None:
    nodes = [
        _node(f"lineup:{index:04d}", salary=40_000 + index)
        for index in range(contracts.BATCH_SIZE + 25)
    ]
    plan = _plan(nodes, [])
    node_batches = plan["node_batches"]
    assert [batch["row_count"] for batch in node_batches] == [
        contracts.BATCH_SIZE,
        25,
    ]
    assert plan["terminal_census"]["node_count"] == contracts.BATCH_SIZE + 25
    assert plan["terminal_census"]["property_count"] == contracts.BATCH_SIZE + 25


def test_manifest_hash_binding_fails_on_drift() -> None:
    manifest = contracts.validate_load_manifest(_manifest())
    tampered = {**manifest, "graph_release_id": "graph-release-0002"}
    with pytest.raises(contracts.CorpusGraphVNextError, match="manifest_sha256"):
        contracts.validate_load_manifest(tampered)


def test_manifest_rejects_bad_source_identity() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="uri"):
        contracts.validate_load_manifest(
            _manifest(
                source_releases=[
                    {
                        "uri": "https://not-gcs",
                        "generation": "1",
                        "sha256": "ab" * 32,
                        "bytes": 10,
                    }
                ]
            )
        )
