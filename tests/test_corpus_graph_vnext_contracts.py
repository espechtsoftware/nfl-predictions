"""Adversarial offline tests for strict graph-vNext contracts."""

from __future__ import annotations

from collections.abc import Sequence
import math

import pytest

from nfl_dfs.research import corpus_graph_vnext_contracts as contracts


def _source(
    uri: str = "gs://fixture/panel-index.json",
    generation: str = "1788000000000201",
    digest: str = "ab" * 32,
    byte_count: int = 2_048,
) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": byte_count,
    }


def _manifest(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": contracts.LOAD_MANIFEST_SCHEMA,
        "graph_schema_version": contracts.GRAPH_SCHEMA_VERSION,
        "graph_release_id": "graph-release-0001",
        "predecessor_graph_release_id": None,
        "allowed_namespaces": ["identity", "membership", "trait"],
        "source_releases": [_source()],
        "authorized_outcome_release_id": None,
        "created_at_utc": "2026-08-25T12:00:00Z",
    }
    base.update(overrides)
    return base


def _node(
    node_id: str,
    kind: str = "Lineup",
    namespace: str = "identity",
    **properties: object,
) -> dict[str, object]:
    return {
        "kind": kind,
        "node_id": node_id,
        "namespace": namespace,
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


def _plan(
    nodes: Sequence[dict[str, object]],
    edges: Sequence[dict[str, object]],
) -> dict[str, object]:
    return contracts.build_load_plan(
        manifest=_manifest(), node_rows=nodes, edge_rows=edges
    )


class _TooLargeSequence(Sequence[dict[str, object]]):
    def __init__(self, size: int) -> None:
        self._size = size

    def __len__(self) -> int:
        return self._size

    def __getitem__(self, index: int) -> dict[str, object]:
        raise AssertionError(f"oversized input was traversed at {index}")


def test_positive_registries_cover_exact_vocabulary() -> None:
    assert set(contracts.NODE_PROPERTY_SCHEMA) == set(contracts.NODE_KINDS)
    assert set(contracts.NODE_NAMESPACE_SCHEMA) == set(contracts.NODE_KINDS)
    assert set(contracts.RELATIONSHIP_PROPERTY_SCHEMA) == set(
        contracts.RELATIONSHIP_TYPES
    )
    assert set(contracts.RELATIONSHIP_NAMESPACE_SCHEMA) == set(
        contracts.RELATIONSHIP_TYPES
    )


def test_identical_content_in_any_order_yields_one_compact_plan_hash() -> None:
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
    assert "rows" not in str(forward)
    census = forward["terminal_census"]
    assert census["node_count"] == 2
    assert census["edge_count"] == 1
    assert census["node_kinds"] == {"Lineup": 1, "PlayerSlate": 1}
    assert census["relationship_types"] == {"CONTAINS_PLAYER": 1}


def test_compact_index_matches_separate_bounded_batch_iterator() -> None:
    nodes = [
        _node(f"lineup:{index:04d}", salary=40_000 + index)
        for index in range(contracts.BATCH_SIZE + 25)
    ]
    plan = _plan(nodes, [])
    batches = list(
        contracts.iter_load_batches(
            manifest=_manifest(), node_rows=nodes, edge_rows=[]
        )
    )
    assert [batch["row_count"] for batch in batches] == [
        contracts.BATCH_SIZE,
        25,
    ]
    assert [
        {key: value for key, value in batch.items() if key != "rows"}
        for batch in batches
    ] == plan["node_batch_index"]
    assert all(len(batch["rows"]) <= contracts.BATCH_SIZE for batch in batches)
    assert plan["edge_batch_index"] == []
    assert plan["terminal_census"]["property_count"] == len(nodes)


def test_conflicting_node_and_edge_identities_fail_closed() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="conflicting"):
        _plan(
            [_node("lineup:a", salary=49_500), _node("lineup:a", salary=1)],
            [],
        )
    nodes = [_node("lineup:a"), _node("player:p1", kind="PlayerSlate")]
    with pytest.raises(contracts.CorpusGraphVNextError, match="conflicting"):
        _plan(
            nodes,
            [
                _edge("lineup:a", "player:p1", ordinal=1),
                _edge("lineup:a", "player:p1", ordinal=2),
            ],
        )


def test_exact_top_level_schemas_reject_missing_and_extra_fields() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="keys differ"):
        contracts.validate_node_row({**_node("lineup:a"), "extra": True})
    edge = _edge("lineup:a", "player:p1")
    del edge["properties"]
    with pytest.raises(contracts.CorpusGraphVNextError, match="keys differ"):
        contracts.validate_edge_row(edge)
    with pytest.raises(contracts.CorpusGraphVNextError, match="keys differ"):
        contracts.validate_load_manifest({**_manifest(), "unexpected": 1})


def test_forbidden_unknown_and_wrong_namespace_vocabulary_fail() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="COVERED_BY"):
        contracts.validate_edge_row(
            _edge("a1", "b1", relationship="COVERED_BY")
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="not registered"):
        contracts.validate_node_row(_node("x1", kind="WorldMatrix"))
    with pytest.raises(contracts.CorpusGraphVNextError, match="does not allow"):
        contracts.validate_node_row(
            _node("trait:x", kind="Trait", namespace="identity")
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="does not allow"):
        contracts.validate_edge_row(
            _edge("a1", "b1", relationship="HAS_TRAIT", namespace="membership")
        )


def test_inferred_exposure_is_trait_scoped_and_explicitly_qualified() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="qualified"):
        contracts.validate_edge_row(
            _edge(
                "player:p1",
                "defender:d1",
                relationship="HAS_INFERRED_DEFENDER_EXPOSURE",
                namespace="trait",
            )
        )
    edge = contracts.validate_edge_row(
        _edge(
            "player:p1",
            "defender:d1",
            relationship="HAS_INFERRED_DEFENDER_EXPOSURE",
            namespace="trait",
            qualified_inferred=True,
            method_id="fp-coverage-map-v1",
            confidence=0.6,
        )
    )
    assert edge["properties"]["qualified_inferred"] is True


@pytest.mark.parametrize(
    "kind", ["WinnerRelease", "WinnerObservation", "OutcomeRelease", "OutcomeGrade"]
)
def test_every_outcome_node_kind_is_closed_offline(kind: str) -> None:
    for namespace in ("identity", "realized"):
        with pytest.raises(contracts.CorpusGraphVNextError, match="closed"):
            contracts.validate_node_row(_node("outcome:x", kind, namespace))


@pytest.mark.parametrize(
    "relationship",
    ["GRADED_IN_CONTEST", "DERIVED_FROM_OUTCOME", "OBSERVED_IN_WINNER_RELEASE"],
)
def test_every_outcome_relationship_is_closed_offline(relationship: str) -> None:
    for namespace in ("lineage", "realized"):
        with pytest.raises(contracts.CorpusGraphVNextError, match="closed"):
            contracts.validate_edge_row(
                _edge("a1", "b1", relationship, namespace)
            )


def test_realized_cannot_be_opened_by_a_caller_supplied_name() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="closed"):
        contracts.validate_load_manifest(
            _manifest(allowed_namespaces=["identity", "realized"])
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="cannot open"):
        contracts.validate_load_manifest(
            _manifest(authorized_outcome_release_id="outcome-release-0001")
        )


@pytest.mark.parametrize(
    "key",
    [
        "actual_points", "dk_points", "lineup_score", "tournament_rank",
        "winner_membership", "payout_amount", "contest_place",
        "realizedScore",
    ],
)
def test_outcome_like_property_spellings_fail_closed(key: str) -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="outcome-like"):
        contracts.validate_node_row(_node("lineup:a", **{key: 1}))


@pytest.mark.parametrize(
    "key",
    [
        "access_token", "apiKey", "client_secret", "private_key",
        "credential_value", "refreshToken", "password_hash",
    ],
)
def test_secret_like_property_spellings_fail_closed(key: str) -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="secret-like"):
        contracts.validate_node_row(_node("lineup:a", **{key: "x"}))


def test_unknown_properties_and_noncanonical_keys_fail_positive_schema() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="positive schema"):
        contracts.validate_node_row(_node("lineup:a", arbitrary_metadata="x"))
    with pytest.raises(contracts.CorpusGraphVNextError, match="canonical"):
        contracts.validate_node_row(_node("lineup:a", **{"Bad-Key": "x"}))
    with pytest.raises(contracts.CorpusGraphVNextError, match="canonical"):
        contracts.validate_node_row(_node("lineup:a", **{"x" * 65: "x"}))


def test_null_and_nonfinite_values_fail_before_hashing() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="null"):
        contracts.validate_node_row(_node("lineup:a", salary=None))
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(contracts.CorpusGraphVNextError, match="finite"):
            contracts.validate_node_row(
                _node(
                    "metric:x", kind="MetricSet", namespace="metric",
                    scope="outcome_blind", value=value,
                )
            )
    with pytest.raises(contracts.CorpusGraphVNextError, match="finite JSON"):
        contracts.canonical_sha256({"x": math.nan})


def test_metric_nodes_require_a_closed_nonrealized_scope() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="explicit offline"):
        contracts.validate_node_row(
            _node("metric:x", kind="MetricSet", namespace="metric", value=1.0)
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="closed value"):
        contracts.validate_node_row(
            _node(
                "metric:x", kind="MetricSet", namespace="metric",
                scope="realized", value=1.0,
            )
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="outcome closed"):
        contracts.validate_node_row(
            _node(
                "metric:x", kind="MetricSet", namespace="metric",
                scope="outcome_blind", definition_id="actual-points", value=1.0,
            )
        )


def test_scalar_and_utf8_byte_bounds_are_enforced() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="Neo4j integer"):
        contracts.validate_node_row(
            _node("lineup:a", salary=contracts.MAX_NEO4J_INTEGER + 1)
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="UTF-8"):
        contracts.validate_node_row(
            _node("player:p1", kind="PlayerSlate", display_name="é" * 65)
        )
    properties = {f"p{index}": index for index in range(contracts.MAX_PROPERTIES + 1)}
    with pytest.raises(contracts.CorpusGraphVNextError, match="property count"):
        contracts.validate_node_row(_node("lineup:a", **properties))


def test_list_item_type_item_bytes_and_aggregate_bytes_are_bounded() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="item bound"):
        contracts.validate_node_row(
            _node(
                "world:x", kind="WorldRelease",
                source_release_ids=[f"source:{index}" for index in range(17)],
            )
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="not a string"):
        contracts.validate_node_row(
            _node(
                "world:x", kind="WorldRelease",
                source_release_ids=["source:a", 1],
            )
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="UTF-8"):
        contracts.validate_node_row(
            _node(
                "world:x", kind="WorldRelease",
                source_release_ids=["x" * (contracts.MAX_PROPERTY_LIST_ITEM_BYTES + 1)],
            )
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="aggregate byte"):
        contracts.validate_node_row(
            _node(
                "world:x", kind="WorldRelease",
                source_release_ids=[
                    "x" * contracts.MAX_PROPERTY_LIST_ITEM_BYTES for _ in range(16)
                ],
            )
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="properties exceed"):
        contracts.validate_node_row(
            _node(
                "world:x", kind="WorldRelease",
                release_id="r" * 200,
                schema_version="s" * 128,
                source_release_ids=["x" * 245 for _ in range(16)],
            )
        )


def test_input_row_counts_fail_before_oversized_sequences_are_traversed() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="node_rows exceeds"):
        _plan(_TooLargeSequence(contracts.MAX_NODE_ROWS + 1), [])
    with pytest.raises(contracts.CorpusGraphVNextError, match="edge_rows exceeds"):
        _plan([], _TooLargeSequence(contracts.MAX_EDGE_ROWS + 1))


def test_edges_require_loaded_endpoints() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="endpoint"):
        _plan([_node("lineup:a")], [_edge("lineup:a", "player:absent")])


def test_sources_are_sorted_unique_bounded_and_order_independent() -> None:
    first = _source("gs://fixture/a.json", "10", "ab" * 32, 10)
    second = _source("gs://fixture/b.json", "11", "cd" * 32, 20)
    forward = contracts.validate_load_manifest(
        _manifest(source_releases=[first, second])
    )
    reverse = contracts.validate_load_manifest(
        _manifest(source_releases=[second, first])
    )
    assert forward == reverse
    assert forward["source_releases"] == [first, second]
    with pytest.raises(contracts.CorpusGraphVNextError, match="duplicate"):
        contracts.validate_load_manifest(
            _manifest(source_releases=[first, dict(first)])
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="conflicting"):
        contracts.validate_load_manifest(
            _manifest(
                source_releases=[first, {**first, "sha256": "ef" * 32}]
            )
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="item bound"):
        contracts.validate_load_manifest(
            _manifest(
                source_releases=[
                    _source(
                        f"gs://fixture/{index}.json", str(index + 1),
                        f"{index:064x}", 1,
                    )
                    for index in range(contracts.MAX_SOURCE_RELEASES + 1)
                ]
            )
        )


def test_source_identity_fields_are_individually_bounded() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="uri"):
        contracts.validate_load_manifest(
            _manifest(source_releases=[_source(uri="https://not-gcs")])
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="uri"):
        contracts.validate_load_manifest(
            _manifest(
                source_releases=[
                    _source(uri="gs://fixture/" + "x" * contracts.MAX_SOURCE_URI_BYTES)
                ]
            )
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="generation"):
        contracts.validate_load_manifest(
            _manifest(source_releases=[_source(generation="0")])
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="bytes"):
        contracts.validate_load_manifest(
            _manifest(
                source_releases=[
                    _source(byte_count=contracts.MAX_SOURCE_OBJECT_BYTES + 1)
                ]
            )
        )
    large_sources = [
        _source(
            uri=f"gs://fixture/{index:02d}/" + "x" * 2_000,
            generation=str(index + 1),
            digest=f"{index:064x}",
            byte_count=1,
        )
        for index in range(contracts.MAX_SOURCE_RELEASES)
    ]
    with pytest.raises(contracts.CorpusGraphVNextError, match="aggregate byte"):
        contracts.validate_load_manifest(
            _manifest(source_releases=large_sources)
        )


def test_manifest_timestamp_namespace_and_hash_laws_fail_closed() -> None:
    with pytest.raises(contracts.CorpusGraphVNextError, match="valid UTC"):
        contracts.validate_load_manifest(
            _manifest(created_at_utc="2026-02-30T12:00:00Z")
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="duplicate"):
        contracts.validate_load_manifest(
            _manifest(allowed_namespaces=["identity", "identity"])
        )
    with pytest.raises(contracts.CorpusGraphVNextError, match="closed"):
        contracts.validate_load_manifest(
            _manifest(allowed_namespaces=["identity", "wild"])
        )
    manifest = contracts.validate_load_manifest(_manifest())
    tampered = {**manifest, "graph_release_id": "graph-release-0002"}
    with pytest.raises(contracts.CorpusGraphVNextError, match="manifest_sha256"):
        contracts.validate_load_manifest(tampered)
