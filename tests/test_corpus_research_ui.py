from __future__ import annotations

from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from nfl_dfs.app import corpus_research as ui
from nfl_dfs.research import corpus_strategy_registry as registry


def test_ui_projection_schema_matches_registry_authority() -> None:
    assert ui.SOURCE_PROJECTION_SCHEMA == registry.PROJECTION_RECEIPT_SCHEMA


def _source_receipt() -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": ui.SOURCE_PROJECTION_SCHEMA,
        "publication_mode": "create_once",
        "registry_release": {
            "uri": "gs://fixture/registry-release.json",
            "generation": "1",
            "sha256": "1" * 64,
            "bytes": 100,
        },
        "registry_id": "strategy-registry-fixture-v1",
        "plan_sha256": "2" * 64,
        "registry_node_count": 2,
        "registry_relationship_count": 1,
        "kind_counts": {"FillPreset": 1, "RetrievalPreset": 1},
        "winner_imported": False,
        "winner_count": 0,
        "registry_namespace": ui.REGISTRY_NAMESPACE,
        "manifest_namespace_v2_authorized": True,
        "gcs_remains_authoritative": True,
        "world_matrices_stored_in_graph": False,
        "automatic_promotion": False,
        "application_config_mutation": False,
        "production_policy_authority": False,
    }
    return {
        **body,
        "projection_receipt_sha256": ui._canonical_sha256(body),
    }


def _queries() -> list[ui.ReadOnlyQuery]:
    return [
        ui.ReadOnlyQuery(name, f"MATCH (node) RETURN '{name}' AS view")
        for name in sorted(ui.REQUIRED_VIEW_NAMES)
    ]


def _fixture_rows() -> dict[str, list[dict[str, object]]]:
    baseline = "experiment:baseline"
    challenger = "experiment:challenger"
    return {
        "preset-registry": [
            {
                "preset_kind": "FillPreset",
                "preset_id": "fill:baseline:v1",
                "preset_version": "fill:baseline:v1",
                "preset_record": (
                    '{"description":"Baseline fill","parameters":'
                    '[{"name":"worlds","type":"integer","value":200}],'
                    '"version":1}'
                ),
            },
            {
                "preset_kind": "RetrievalPreset",
                "preset_id": "retrieval:coverage:v1",
                "preset_version": "retrieval:coverage:v1",
                "preset_record": (
                    '{"description":"Coverage selector","parameters":'
                    '[{"name":"budget","type":"integer","value":80}],'
                    '"version":1}'
                ),
            },
        ],
        "strategy-lineage": [
            {
                "fill_preset": "fill:baseline:v1",
                "fill_preset_record": '{"version":1}',
                "snapshot_id": "snapshot:2023-w1",
                "snapshot_record": '{"created_at_utc":"2026-08-21T13:00:00Z"}',
                "retrieval_preset": "retrieval:coverage:v1",
                "retrieval_preset_record": '{"version":1}',
                "experiment_id": challenger,
                "experiment_record": '{"task_index":0}',
                "slate_id": "2023-w1-main",
            }
        ],
        "paired-heldout-fill-retrieval-comparison": [
            {
                "experiment_id": experiment,
                "slate_id": "2023-w1-main",
                "fill_preset": "fill:baseline:v1",
                "retrieval_preset": retrieval,
                "metric_name": metric,
                "split": split,
                "value": value,
                "paired_baseline": paired,
                "pairing_law": None,
            }
            for experiment, retrieval, metric, split, value, paired in [
                (baseline, "retrieval:baseline:v1", "strict_gt_200_coverage", "discovery", 0.18, None),
                (baseline, "retrieval:baseline:v1", "strict_gt_200_coverage", "heldout", 0.16, None),
                (baseline, "retrieval:baseline:v1", "roster_diversity", "heldout", 0.55, None),
                (challenger, "retrieval:coverage:v1", "strict_gt_200_coverage", "discovery", 0.24, baseline),
                (challenger, "retrieval:coverage:v1", "strict_gt_200_coverage", "heldout", 0.20, baseline),
                (challenger, "retrieval:coverage:v1", "roster_diversity", "heldout", 0.61, baseline),
            ]
        ],
        "active-pointer-promotion-traversal": [
            {
                "active_pointer": "active:research:v1",
                "active_pointer_record": '{"version":1}',
                "decision": "decision:coverage:v1",
                "decision_record": (
                    '{"decision":"promote","review":'
                    '{"reviewed_at_utc":"2026-08-21T13:00:00Z"},'
                    '"version":1}'
                ),
                "experiment": challenger,
                "fill_preset": "fill:baseline:v1",
                "retrieval_preset": "retrieval:coverage:v1",
                "gate_metric": "strict_gt_200_coverage",
                "gate_scope": "heldout",
                "observed_value": 0.20,
            }
        ],
        "lineup-player-team-game-traversal": [
            {
                "lineup": "winner:fixture",
                "lineup_kind": "WinningLineup",
                "is_winner": True,
                "score_present": True,
                "score": 218.4,
                "lineup_record": '{"winner_id":"fixture"}',
                "slate_id": "2023-w1-main",
                "player": "player:p01",
                "player_record": '{"display_name":"Fixture Player"}',
                "team_slate": "team:KC:2023-w1-main",
                "game": "game:KC-DET:2023-w1-main",
                "corpus_snapshot": None,
                "producing_fill_preset": None,
            }
        ],
        "registry-firewall-census": [
            {"kind": "FillPreset", "node_count": 1},
            {"kind": "RetrievalPreset", "node_count": 1},
        ],
    }


def _projection() -> tuple[dict[str, object], list[tuple[object, ...]]]:
    fixture_rows = _fixture_rows()
    calls: list[tuple[object, ...]] = []

    def run_query(
        database: str, cypher: str, parameters: dict[str, object]
    ) -> list[dict[str, object]]:
        name = next(name for name in fixture_rows if f"'{name}'" in cypher)
        calls.append((database, cypher, dict(parameters)))
        return fixture_rows[name]

    projection = ui.build_read_only_projection(
        source_projection_receipt=_source_receipt(),
        database="corpusresearch",
        queries=_queries(),
        query_runner=run_query,
        generated_at_utc="2026-08-21T14:00:00Z",
    )
    return projection, calls


def test_query_projection_is_receipt_bound_and_read_only() -> None:
    projection, calls = _projection()
    validated = ui.validate_read_only_projection(projection)

    assert len(calls) == len(ui.REQUIRED_VIEW_NAMES)
    assert all(call[0] == "corpusresearch" for call in calls)
    assert all(call[2] == {
        "namespace": ui.REGISTRY_NAMESPACE,
        "registry_id": "strategy-registry-fixture-v1",
    } for call in calls)
    assert validated["read_only"] is True
    assert validated["graph_mutation"] is False
    assert validated["automatic_promotion"] is False
    assert validated["application_config_mutation"] is False
    assert validated["production_policy_authority"] is False
    assert validated["query_receipt"]["world_matrices_stored_in_graph"] is False
    assert set(validated["views"]) == ui.REQUIRED_VIEW_NAMES


def test_query_catalog_rejects_mutation_before_runner_contact() -> None:
    calls: list[object] = []
    queries = _queries()
    queries[0] = ui.ReadOnlyQuery(queries[0].name, "MATCH (n) DELETE n")

    with pytest.raises(ui.CorpusResearchProjectionError, match="mutation"):
        ui.build_read_only_projection(
            source_projection_receipt=_source_receipt(),
            database="corpusresearch",
            queries=queries,
            query_runner=lambda *args: calls.append(args),
            generated_at_utc="2026-08-21T14:00:00Z",
        )
    assert calls == []


def test_materialized_projection_rejects_row_tampering() -> None:
    projection, _ = _projection()
    changed = deepcopy(projection)
    changed["views"]["registry-firewall-census"][0]["node_count"] = 999
    body = {
        key: value for key, value in changed.items()
        if key != "projection_sha256"
    }
    changed["projection_sha256"] = ui._canonical_sha256(body)

    with pytest.raises(ui.CorpusResearchProjectionError, match="row receipt"):
        ui.validate_read_only_projection(changed)


class _UnavailableReader:
    def read(self) -> ui.ProjectionAvailability:
        return ui.ProjectionAvailability(
            ready=False,
            projection=None,
            reason_code="projection-not-configured",
            message="Projection is intentionally not configured.",
        )


class _ReadyReader:
    def __init__(self, projection: dict[str, object]) -> None:
        self._projection = projection

    def read(self) -> ui.ProjectionAvailability:
        return ui.ProjectionAvailability(
            ready=True,
            projection=self._projection,
            reason_code="ready",
            message="ready",
        )


def _client(reader: object) -> TestClient:
    app = FastAPI()
    app.include_router(ui.router)
    app.dependency_overrides[ui.get_corpus_research_reader] = lambda: reader
    return TestClient(app)


def test_routes_have_clear_not_ready_state_and_visualization_shell() -> None:
    client = _client(_UnavailableReader())
    status = client.get("/api/corpus-research/status")
    projection = client.get("/api/corpus-research/projection")
    page = client.get("/corpus-research")

    assert status.status_code == 200
    assert status.json()["ready"] is False
    assert status.json()["automatic_promotion"] is False
    assert projection.status_code == 503
    assert projection.json()["reason_code"] == "projection-not-configured"
    assert page.status_code == 200
    for element_id in (
        "lineage-chart", "heatmap-chart", "paired-chart", "scatter-chart",
        "promotion-chart", "network-chart", "preset-catalog",
    ):
        assert f'id="{element_id}"' in page.text


def test_projection_route_returns_only_validated_ready_snapshot() -> None:
    projection, _ = _projection()
    response = _client(_ReadyReader(projection)).get(
        "/api/corpus-research/projection"
    )

    assert response.status_code == 200
    assert response.json()["status"]["ready"] is True
    assert response.json()["projection"]["projection_sha256"] == (
        projection["projection_sha256"]
    )
    assert response.headers["cache-control"] == "no-store"


def test_react_shell_serves_pinned_vendor_runtime() -> None:
    from hashlib import sha256
    from pathlib import Path

    client = _client(_UnavailableReader())
    page = client.get("/corpus-research")
    for script in (
        "/static/vendor/react.production.min.js",
        "/static/vendor/react-dom.production.min.js",
        "/static/vendor/htm.min.js",
        "/static/corpus_research.js",
    ):
        assert f'src="{script}"' in page.text
    static = Path(__file__).resolve().parents[1] / "src/nfl_dfs/app/static"
    pinned = {
        "vendor/react.production.min.js":
            "d949f1c3687aedadcedac85261865f29b17cd273997e7f6b2bfc53b2f9d4c4dd",
        "vendor/react-dom.production.min.js":
            "35f4f974f4b2bcd44da73963347f8952e341f83909e4498227d4e26b98f66f0d",
        "vendor/htm.min.js":
            "80e39afe20fd61183412eda89efa10532d57945e6364642aceacd50eb2384b4b",
    }
    for name, expected in pinned.items():
        assert sha256((static / name).read_bytes()).hexdigest() == expected
    app_js = (static / "corpus_research.js").read_text()
    assert "createRoot" in app_js and "createPortal" in app_js
    assert "htm.bind" in app_js
