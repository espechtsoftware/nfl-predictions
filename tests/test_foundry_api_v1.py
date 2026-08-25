"""Contract tests for the bounded, GET-only /api/v1/foundry read surface.

Fixture-backed only: the router is mounted on a test-local FastAPI app and
is deliberately NOT integrated into the live application (integration is a
separately reviewed step). No test reaches a graph, cloud resource, or
governed outcome.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from nfl_dfs.app import foundry_api
from nfl_dfs.app.foundry_read_models import (
    API_SCHEMA,
    FixtureFoundryRepository,
    FoundryReadError,
    MAX_RESPONSE_BYTES,
    enforce_response_budget,
)


EXPECTED_PATHS = {
    "/api/v1/foundry/status",
    "/api/v1/foundry/releases",
    "/api/v1/foundry/presets",
    "/api/v1/foundry/strategy-bundles",
    "/api/v1/foundry/experiments",
    "/api/v1/foundry/experiments/{experiment_id}/metrics",
    "/api/v1/foundry/runs",
    "/api/v1/foundry/evaluations",
    "/api/v1/foundry/books/{book_id}",
    "/api/v1/foundry/cohorts/compare",
    "/api/v1/foundry/traits/enrichment",
    "/api/v1/foundry/slates/{slate_id}/lineups/{lineup_id}",
    "/api/v1/foundry/lineup-network",
    "/api/v1/foundry/source-coverage",
    "/api/v1/foundry/receipts/{receipt_id}",
}


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(foundry_api.router)
    return TestClient(app)


def test_router_is_get_only_and_path_frozen() -> None:
    paths = set()
    for route in foundry_api.router.routes:
        assert route.methods == {"GET"}, route.path
        paths.add(route.path)
    assert paths == EXPECTED_PATHS


def test_router_is_not_wired_into_the_live_application() -> None:
    main_source = (
        Path(__file__).resolve().parents[1]
        / "src" / "nfl_dfs" / "app" / "main.py"
    ).read_text(encoding="utf-8")
    assert "foundry_api" not in main_source


def test_envelope_contract_on_status(client: TestClient) -> None:
    response = client.get("/api/v1/foundry/status")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == API_SCHEMA
    assert body["api_version"] == "v1"
    assert body["response_type"] == "foundry-status"
    assert body["read_only"] is True
    assert body["release"]["data_release"] == "fixture-data-release-001"
    staleness = body["staleness"]
    assert staleness["generated_at_utc"] == "2026-08-25T12:00:00Z"
    assert isinstance(staleness["age_seconds"], int)
    assert body["payload"]["accepted_slates"] == 54
    assert body["payload"]["graph_available"] is False
    assert "no run, promotion, or outcome" in body["payload"]["authority_note"]
    assert response.headers["Cache-Control"] == "no-store"


def test_cursor_pagination_walks_all_presets(client: TestClient) -> None:
    seen: list[str] = []
    cursor: str | None = None
    pages = 0
    while True:
        params = {"page_size": "5"}
        if cursor is not None:
            params["cursor"] = cursor
        response = client.get("/api/v1/foundry/presets", params=params)
        assert response.status_code == 200
        body = response.json()
        seen.extend(row["preset_id"] for row in body["payload"]["rows"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert pages == 3
    assert len(seen) == 13
    assert len(set(seen)) == 13
    kinds = {preset.split(":", 1)[0] for preset in seen}
    assert kinds == {"fill", "admission", "retrieval"}


def test_invalid_cursor_and_oversized_page_are_rejected(
    client: TestClient,
) -> None:
    bad_cursor = client.get(
        "/api/v1/foundry/presets", params={"cursor": "!!not-base64!!"}
    )
    assert bad_cursor.status_code == 422
    assert bad_cursor.json()["response_type"] == "invalid-request"
    oversized = client.get(
        "/api/v1/foundry/presets", params={"page_size": "201"}
    )
    assert oversized.status_code == 422


def test_etag_revalidation_returns_304(client: TestClient) -> None:
    first = client.get("/api/v1/foundry/presets")
    etag = first.headers["ETag"]
    second = client.get(
        "/api/v1/foundry/presets", headers={"If-None-Match": etag}
    )
    assert second.status_code == 304


def test_response_budget_enforced() -> None:
    oversized = {"rows": ["x" * 1024] * (MAX_RESPONSE_BYTES // 1024 + 8)}
    with pytest.raises(FoundryReadError):
        enforce_response_budget(oversized)


def test_degraded_backend_stays_healthy() -> None:
    class BrokenRepository(FixtureFoundryRepository):
        def status(self):  # type: ignore[override]
            raise RuntimeError("neo4j endpoint absent")

    app = FastAPI()
    app.include_router(foundry_api.router)
    app.dependency_overrides[foundry_api.get_foundry_repository] = (
        lambda: BrokenRepository()
    )
    response = TestClient(app).get("/api/v1/foundry/status")
    assert response.status_code == 503
    body = response.json()
    assert body["response_type"] == "degraded"
    assert "neo4j endpoint absent" in body["detail"]
    assert body["read_only"] is True


def test_receipt_metadata_is_allowlisted_only(client: TestClient) -> None:
    response = client.get("/api/v1/foundry/receipts/receipt-fill-0")
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert set(payload) == {
        "receipt_id",
        "receipt_type",
        "status",
        "sha256",
        "generated_at_utc",
    }
    assert "gs://" not in response.text


def test_unknown_resources_return_404(client: TestClient) -> None:
    for url in (
        "/api/v1/foundry/receipts/unknown",
        "/api/v1/foundry/books/book:missing",
        "/api/v1/foundry/slates/slate:none/lineups/lineup:none",
        "/api/v1/foundry/experiments/experiment:none/metrics",
    ):
        response = client.get(url)
        assert response.status_code == 404, url
        assert response.json()["response_type"] == "not-found"


def test_cohort_compare_carries_winner_release_and_denominator(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/foundry/cohorts/compare",
        params={"cohort_a": "winners", "cohort_b": "matched-controls"},
    )
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert payload["winner_release_id"] == "winner-release-governed-51"
    metric = payload["metrics"][0]
    assert metric["denominator"]["total"] == 51
    assert metric["metric"]["definition"]
    without_winner = client.get(
        "/api/v1/foundry/cohorts/compare",
        params={"cohort_a": "simulated-tail", "cohort_b": "corpus"},
    ).json()["payload"]
    assert without_winner["winner_release_id"] is None


def test_bounded_filters_reject_bad_identifiers(client: TestClient) -> None:
    response = client.get(
        "/api/v1/foundry/cohorts/compare",
        params={"cohort_a": "winners;DROP", "cohort_b": "x"},
    )
    assert response.status_code == 422


def test_trait_enrichment_keeps_missing_as_missing(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/foundry/traits/enrichment", params={"cohort": "winners"}
    )
    rows = response.json()["payload"]["rows"]
    coverage = next(
        row for row in rows if row["trait_id"] == "coverage-matchup"
    )
    assert coverage["lift"] is None
    assert coverage["support"]["missing"] == 17


def test_lineup_detail_and_network_stay_outcome_free(
    client: TestClient,
) -> None:
    detail = client.get(
        "/api/v1/foundry/slates/slate:2023-w1/lineups/lineup:fixture-001"
    ).json()["payload"]
    assert detail["realized_note"] == "unavailable-not-authorized"
    network = client.get(
        "/api/v1/foundry/lineup-network",
        params={"lineup_id": "lineup:fixture-001"},
    ).json()["payload"]["rows"]
    inferred = next(
        row
        for row in network
        if row["relationship"] == "HAS_INFERRED_DEFENDER_EXPOSURE"
    )
    assert inferred["qualified_inferred"] is True


def test_openapi_schema_freezes_the_surface(client: TestClient) -> None:
    schema = client.app.openapi()  # type: ignore[attr-defined]
    assert set(schema["paths"]) == EXPECTED_PATHS
    for path, operations in schema["paths"].items():
        assert set(operations) == {"get"}, path
