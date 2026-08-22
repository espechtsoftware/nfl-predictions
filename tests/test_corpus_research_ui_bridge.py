from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from nfl_dfs.app import corpus_research as ui
from nfl_dfs.research import corpus_neo4j_transport as transport
from nfl_dfs.research import corpus_research_ui_bridge as bridge
from nfl_dfs.research import corpus_strategy_registry as registry


ROOT = Path(__file__).resolve().parents[1]


def _fixture_module() -> ModuleType:
    path = ROOT / "tests/test_corpus_neo4j_transport.py"
    spec = importlib.util.spec_from_file_location(
        "_corpus_ui_bridge_fixture_source", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURES = _fixture_module()


def _loaded_registry() -> tuple[object, object, object]:
    storage = FIXTURES.FakeStorage()
    deployment, bundle, _ = FIXTURES._prepare_task0(storage)
    graph = FIXTURES.FakeGraph(deployment)
    transport.bootstrap_schema(storage=storage, graph=graph, bundle=bundle)
    transport.load_plan(
        storage=storage, graph=graph, bundle=bundle, task_index=None
    )
    transport.load_strategy_registry(
        storage=storage, graph=graph, bundle=bundle
    )
    transport.query_strategy_registry(
        storage=storage, graph=graph, bundle=bundle
    )
    return storage, graph, bundle


def test_exact_registry_queries_materialize_create_once_ui_projection() -> None:
    storage, graph, bundle = _loaded_registry()
    first = bridge.materialize_ui_projection(
        storage=storage,
        graph=graph,
        bundle=bundle,
        generated_at_utc="2026-08-21T23:30:00Z",
    )
    second = bridge.materialize_ui_projection(
        storage=storage,
        graph=graph,
        bundle=bundle,
        generated_at_utc="2026-08-21T23:30:00Z",
    )

    assert first.projection_identity == second.projection_identity
    assert first.receipt_identity == second.receipt_identity
    assert ui.validate_read_only_projection(first.projection) == first.projection
    assert list(first.projection["views"]) == [
        query.name for query in registry.READ_ONLY_QUERIES
    ]
    assert first.receipt["view_names"] == [
        query.name for query in registry.READ_ONLY_QUERIES
    ]
    assert first.receipt["combined_row_count"] == 7
    assert first.receipt["maximum_combined_row_count"] == 100_000
    assert first.receipt["source_projection_schema"] == (
        "corpus-strategy-registry-projection/v2"
    )
    assert first.receipt["ui_projection_schema"] == (
        "corpus-research-ui-projection/v1"
    )
    assert first.receipt["realized_namespace_reserved"] is True
    assert first.receipt["uses_realized_outcomes"] is False
    assert storage.list_calls == 0


def test_bridge_rejects_rows_that_drift_after_retained_query_receipt() -> None:
    storage, graph, bundle = _loaded_registry()
    original = graph.run_read_only_query

    def drifted(database: str, cypher: str, parameters: dict[str, object]):
        rows = original(database, cypher, parameters)
        return [*rows, {"unexpected": "post-receipt-row"}]

    graph.run_read_only_query = drifted
    with pytest.raises(bridge.CorpusResearchUIBridgeError, match="drifted"):
        bridge.materialize_ui_projection(
            storage=storage,
            graph=graph,
            bundle=bundle,
            generated_at_utc="2026-08-21T23:30:00Z",
        )


def test_bridge_rejects_a_populated_realized_outcome_namespace() -> None:
    storage, graph, bundle = _loaded_registry()
    graph.nodes["realized-outcome-fixture"] = {
        "id": "realized-outcome-fixture",
        "workstream_namespace": transport.REALIZED_OUTCOME_NAMESPACE,
    }
    with pytest.raises(
        bridge.CorpusResearchUIBridgeError,
        match="component/census authority differs",
    ):
        bridge.materialize_ui_projection(
            storage=storage,
            graph=graph,
            bundle=bundle,
            generated_at_utc="2026-08-21T23:30:00Z",
        )


def test_bridge_recensuses_after_queries_before_publication() -> None:
    storage, graph, bundle = _loaded_registry()
    original = graph.run_read_only_query
    calls = 0

    def populate_after_last_query(
        database: str, cypher: str, parameters: dict[str, object],
    ):
        nonlocal calls
        rows = original(database, cypher, parameters)
        calls += 1
        if calls == len(registry.READ_ONLY_QUERIES):
            graph.nodes["realized-outcome-race"] = {
                "id": "realized-outcome-race",
                "workstream_namespace": transport.REALIZED_OUTCOME_NAMESPACE,
            }
        return rows

    graph.run_read_only_query = populate_after_last_query
    with pytest.raises(
        bridge.CorpusResearchUIBridgeError,
        match="during UI reads",
    ):
        bridge.materialize_ui_projection(
            storage=storage,
            graph=graph,
            bundle=bundle,
            generated_at_utc="2026-08-21T23:30:00Z",
        )


def test_bridge_enforces_the_combined_row_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage, graph, bundle = _loaded_registry()
    monkeypatch.setattr(ui, "MAX_QUERY_ROWS", 5)
    with pytest.raises(
        bridge.CorpusResearchUIBridgeError,
        match="combined query results exceed",
    ):
        bridge.materialize_ui_projection(
            storage=storage,
            graph=graph,
            bundle=bundle,
            generated_at_utc="2026-08-21T23:30:00Z",
        )


def test_bridge_enforces_the_application_projection_byte_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage, graph, bundle = _loaded_registry()
    monkeypatch.setattr(ui, "MAX_PROJECTION_BYTES", 1)
    with pytest.raises(
        bridge.CorpusResearchUIBridgeError,
        match="byte limit",
    ):
        bridge.materialize_ui_projection(
            storage=storage,
            graph=graph,
            bundle=bundle,
            generated_at_utc="2026-08-21T23:30:00Z",
        )
