"""Adversarial contract tests for the offline, GET-only Foundry API.

The live application does not mount this router.  Successful tests explicitly
inject the unmistakably synthetic fixture repository; the unoverridden
production dependency must remain safely unavailable.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from nfl_dfs.app import foundry_api
from nfl_dfs.app.foundry_read_models import (
    API_SCHEMA,
    AuthorityContext,
    DEFAULT_QUERY_DEADLINE_MS,
    Denominator,
    Evaluation,
    FixtureFoundryRepository,
    FoundryStatus,
    MAX_PAGE_SIZE,
    MAX_QUERY_DEADLINE_MS,
    MetricDefinition,
    MetricValue,
    PageRequest,
    Preset,
    Provenance,
    RepositoryPage,
    Run,
    release_sha256,
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


def _client(repository: object | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(foundry_api.router)
    if repository is not None:
        app.dependency_overrides[foundry_api.get_foundry_repository] = lambda: repository
    return TestClient(app)


@pytest.fixture()
def repository() -> FixtureFoundryRepository:
    return FixtureFoundryRepository()


@pytest.fixture()
def client(repository: FixtureFoundryRepository) -> TestClient:
    return _client(repository)


def test_router_is_get_only_and_path_frozen() -> None:
    paths = set()
    for route in foundry_api.router.routes:
        assert route.methods == {"GET"}, route.path
        paths.add(route.path)
    assert paths == EXPECTED_PATHS


def test_router_is_not_wired_into_live_application() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "nfl_dfs"
        / "app"
        / "main.py"
    ).read_text(encoding="utf-8")
    assert "foundry_api" not in source


def test_production_default_is_safely_unavailable_and_never_serves_fixture() -> None:
    client = _client()
    for path in ("/api/v1/foundry/status", "/api/v1/foundry/presets"):
        response = client.get(path)
        assert response.status_code == 503
        body = response.json()
        assert body["reason_code"] == "backend-unavailable"
        assert body["response_type"] == "degraded"
        assert "54" not in response.text
        assert "fixture-data-release" not in response.text
        assert "not configured" not in response.text


def test_fixture_status_envelope_is_explicitly_synthetic(client: TestClient) -> None:
    response = client.get("/api/v1/foundry/status")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == API_SCHEMA
    assert body["api_version"] == "v1"
    assert body["read_only"] is True
    assert body["release"]["data_release"] == "fixture-data-release-001"
    assert body["authority"] == {
        "evidence_tier": "synthetic-fixture",
        "scope": "identity-only",
        "authority": "synthetic-fixture",
        "outcome_authorized": False,
        "note": body["evidence_note"],
    }
    assert body["payload"]["accepted_slates"] == 54
    assert body["payload"]["evidence_tier"] == "synthetic-fixture"
    assert response.headers["Cache-Control"] == "private, no-cache"
    assert int(response.headers["X-Foundry-Age-Seconds"]) >= 0


def test_envelope_authority_note_is_repository_derived() -> None:
    class ExplicitAuthorityRepository(FixtureFoundryRepository):
        def authority(self):  # type: ignore[override]
            return AuthorityContext(
                evidence_tier="exploratory",
                scope="simulated",
                authority="release-bound-read",
                outcome_authorized=False,
                note="adapter-supplied release-bound authority note",
            )

        def status(self, request):  # type: ignore[override]
            return super().status(request).model_copy(
                update={"evidence_tier": "exploratory", "scope": "simulated"}
            )

    body = _client(ExplicitAuthorityRepository()).get(
        "/api/v1/foundry/status"
    ).json()
    assert body["evidence_note"] == "adapter-supplied release-bound authority note"
    assert body["authority"]["authority"] == "release-bound-read"


def test_cursor_pagination_walks_presets_with_query_side_caps(
    client: TestClient,
) -> None:
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
    assert len(seen) == len(set(seen)) == 13
    assert {item.split(":", 1)[0] for item in seen} == {
        "fill",
        "admission",
        "retrieval",
    }


def test_repository_receives_exact_release_bound_cap_and_deadline() -> None:
    class RecordingRepository(FixtureFoundryRepository):
        def __init__(self) -> None:
            super().__init__()
            self.requests: list[PageRequest] = []

        def presets(self, request: PageRequest):  # type: ignore[override]
            self.requests.append(request)
            return super().presets(request)

    repository = RecordingRepository()
    response = _client(repository).get(
        "/api/v1/foundry/presets", params={"page_size": "7"}
    )
    assert response.status_code == 200
    assert len(repository.requests) == 1
    request = repository.requests[0]
    assert request.query_id == "presets"
    assert request.offset == 0
    assert request.limit == request.hard_row_cap == 7
    assert request.deadline_ms == DEFAULT_QUERY_DEADLINE_MS
    assert request.deadline_ms <= MAX_QUERY_DEADLINE_MS
    assert request.release_sha256 == release_sha256(repository.release_identity())


def test_bad_and_cross_bound_cursors_are_rejected(client: TestClient) -> None:
    invalid = client.get(
        "/api/v1/foundry/presets", params={"cursor": "!!not-base64!!"}
    )
    assert invalid.status_code == 422
    assert invalid.json()["reason_code"] == "invalid-request"

    first = client.get("/api/v1/foundry/presets", params={"page_size": "5"}).json()
    cursor = first["next_cursor"]
    assert cursor
    cross_query = client.get(
        "/api/v1/foundry/releases",
        params={"page_size": "1", "cursor": cursor},
    )
    assert cross_query.status_code == 422

    trait = client.get(
        "/api/v1/foundry/traits/enrichment",
        params={"cohort": "winners", "page_size": "1"},
    ).json()
    cross_filter = client.get(
        "/api/v1/foundry/traits/enrichment",
        params={
            "cohort": "matched-controls",
            "page_size": "1",
            "cursor": trait["next_cursor"],
        },
    )
    assert cross_filter.status_code == 422


def test_cursor_is_rejected_after_release_changes() -> None:
    class DriftingReleaseRepository(FixtureFoundryRepository):
        drift = False

        def release_identity(self):  # type: ignore[override]
            release = super().release_identity()
            if not self.drift:
                return release
            return release.model_copy(update={"data_release": "fixture-data-release-002"})

    repository = DriftingReleaseRepository()
    client = _client(repository)
    first = client.get(
        "/api/v1/foundry/presets", params={"page_size": "5"}
    ).json()
    repository.drift = True
    response = client.get(
        "/api/v1/foundry/presets",
        params={"page_size": "5", "cursor": first["next_cursor"]},
    )
    assert response.status_code == 422
    assert response.json()["reason_code"] == "invalid-request"


def test_page_and_path_bounds_are_enforced(client: TestClient) -> None:
    oversized_page = client.get(
        "/api/v1/foundry/presets", params={"page_size": str(MAX_PAGE_SIZE + 1)}
    )
    oversized_path = client.get("/api/v1/foundry/books/" + "x" * 129)
    invalid_path = client.get("/api/v1/foundry/receipts/receipt;DROP")
    for response in (oversized_page, oversized_path, invalid_path):
        assert response.status_code == 422
        assert response.json()["reason_code"] == "invalid-request"
        assert set(response.json()) == {
            "schema_version",
            "api_version",
            "response_type",
            "reason_code",
            "detail",
            "read_only",
        }


def test_openapi_freezes_bounded_parameters_and_typed_payloads(client: TestClient) -> None:
    schema = client.app.openapi()  # type: ignore[attr-defined]
    assert set(schema["paths"]) == EXPECTED_PATHS
    for path, operations in schema["paths"].items():
        assert set(operations) == {"get"}, path
        success = operations["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert success, path
        assert success != {"type": "object"}, path

    path_parameter_names = {
        "experiment_id",
        "book_id",
        "slate_id",
        "lineup_id",
        "receipt_id",
    }
    observed: set[str] = set()
    for operations in schema["paths"].values():
        for parameter in operations["get"].get("parameters", []):
            if parameter["in"] != "path":
                continue
            observed.add(parameter["name"])
            assert parameter["schema"]["maxLength"] == 128
            assert parameter["schema"]["pattern"] == foundry_api.ID_PATTERN
    assert observed == path_parameter_names

    page_schema = schema["components"]["schemas"]["PagePayload_Preset_"]
    assert page_schema["properties"]["rows"]["maxItems"] == MAX_PAGE_SIZE


def test_etag_changes_at_stale_transition_and_age_is_separate(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(foundry_api, "_utc_now", lambda: "2026-08-25T13:00:00Z")
    fresh = client.get("/api/v1/foundry/status")
    assert fresh.status_code == 200
    assert fresh.headers["X-Foundry-Stale"] == "false"

    monkeypatch.setattr(foundry_api, "_utc_now", lambda: "2026-08-25T19:00:01Z")
    stale = client.get(
        "/api/v1/foundry/status",
        headers={"If-None-Match": fresh.headers["ETag"]},
    )
    assert stale.status_code == 200
    assert stale.headers["ETag"] != fresh.headers["ETag"]
    assert stale.headers["X-Foundry-Stale"] == "true"
    assert stale.json()["staleness"]["stale"] is True

    monkeypatch.setattr(foundry_api, "_utc_now", lambda: "2026-08-25T19:00:02Z")
    same_state = client.get(
        "/api/v1/foundry/status",
        headers={"If-None-Match": stale.headers["ETag"]},
    )
    assert same_state.status_code == 304
    assert same_state.headers["X-Foundry-Age-Seconds"] == str(7 * 3600 + 2)


def test_non_status_backend_failure_is_sanitized() -> None:
    class BrokenRepository(FixtureFoundryRepository):
        def presets(self, request: PageRequest):  # type: ignore[override]
            del request
            raise RuntimeError(
                "bolt+s://internal.example password=hunter2 access_token=private"
            )

    response = _client(BrokenRepository()).get("/api/v1/foundry/presets")
    assert response.status_code == 503
    body = response.json()
    assert body["reason_code"] == "backend-unavailable"
    assert "internal.example" not in response.text
    assert "hunter2" not in response.text
    assert "access_token" not in response.text


@pytest.mark.parametrize("failure_method", ["release_identity", "staleness", "authority"])
def test_context_failures_are_sanitized(failure_method: str) -> None:
    class BrokenContextRepository(FixtureFoundryRepository):
        pass

    def fail(*_args: object, **_kwargs: object):
        raise RuntimeError("gs://private-evidence password=do-not-return")

    setattr(BrokenContextRepository, failure_method, fail)
    response = _client(BrokenContextRepository()).get("/api/v1/foundry/status")
    assert response.status_code == 503
    assert response.json()["reason_code"] == "backend-unavailable"
    assert "gs://" not in response.text
    assert "do-not-return" not in response.text


def test_malformed_and_nonfinite_repository_rows_degrade_as_contract_failure() -> None:
    class MalformedRepository(FixtureFoundryRepository):
        def presets(self, request: PageRequest):  # type: ignore[override]
            del request
            return {"rows": "not-a-bounded-page"}

    malformed = _client(MalformedRepository()).get("/api/v1/foundry/presets")
    assert malformed.status_code == 503
    assert malformed.json()["reason_code"] == "projection-contract-invalid"

    class NonfiniteRepository(FixtureFoundryRepository):
        def experiment_metrics(self, experiment_id: str, request: PageRequest):  # type: ignore[override]
            del experiment_id
            bad_metric = MetricValue.model_construct(
                metric=MetricDefinition(
                    metric_id="bad-metric",
                    definition="malformed adapter value",
                    unit="dk_points",
                ),
                value=float("nan"),
                uncertainty_note=None,
                denominator=Denominator(unit="slates", total=1, missing=0),
                fold="R0",
                scope="simulated",
                outcome_release_id=None,
                evidence_tier="synthetic-fixture",
                provenance=Provenance(
                    receipt_id="receipt-fixture-bad-metric",
                    receipt_route="/api/v1/foundry/receipts/receipt-fixture-bad-metric",
                ),
            )
            return RepositoryPage.model_construct(
                rows=(bad_metric,), total=1, offset=request.offset, next_offset=None
            )

    nonfinite = _client(NonfiniteRepository()).get(
        "/api/v1/foundry/experiments/experiment:fixture-core-v1/metrics"
    )
    assert nonfinite.status_code == 503
    assert nonfinite.json()["reason_code"] == "projection-contract-invalid"


def test_oversized_real_route_response_is_safely_refused() -> None:
    class OversizedRepository(FixtureFoundryRepository):
        def presets(self, request: PageRequest):  # type: ignore[override]
            self._check(request, "presets")
            rows = tuple(
                Preset(
                    preset_id=f"fill:fixture:oversized:{index:03d}",
                    kind="fill",
                    version="v1-fixture",
                    parameters_note="x" * 1_024,
                    evidence_tier="synthetic-fixture",
                    scope="simulated",
                    provenance=Provenance(
                        receipt_id=f"receipt-fixture-oversized-{index:03d}",
                        receipt_route=(
                            "/api/v1/foundry/receipts/"
                            f"receipt-fixture-oversized-{index:03d}"
                        ),
                    ),
                )
                for index in range(MAX_PAGE_SIZE)
            )
            return self._page(rows, request)

    response = _client(OversizedRepository()).get(
        "/api/v1/foundry/presets", params={"page_size": str(MAX_PAGE_SIZE)}
    )
    assert response.status_code == 503
    assert response.json()["reason_code"] == "response-budget-exceeded"


def test_raw_provenance_in_non_receipt_payload_is_rejected() -> None:
    class RawProvenanceRepository(FixtureFoundryRepository):
        def status(self, request):  # type: ignore[override]
            self._check(request, "status")
            return FoundryStatus(
                graph_available=True,
                accepted_slates=54,
                registered_presets=13,
                registered_bundles=6,
                open_experiments=1,
                authority_note="source=gs://private-bucket/raw-receipt.json",
                evidence_tier="synthetic-fixture",
                scope="identity-only",
            )

    response = _client(RawProvenanceRepository()).get("/api/v1/foundry/status")
    assert response.status_code == 503
    assert response.json()["reason_code"] == "projection-contract-invalid"
    assert "gs://" not in response.text


def test_adapter_facing_models_fail_closed_on_false_scientific_states() -> None:
    with pytest.raises(ValidationError, match="missing exceeds total"):
        Denominator(unit="slates", total=2, missing=3)

    run = dict(
        run_id="run:bad",
        experiment_id="experiment:bad",
        status="accepted",
        accepted_task_count=2,
        task_count=1,
        evidence_tier="synthetic-fixture",
        scope="simulated",
        provenance=Provenance(
            receipt_id="receipt-fixture-bad-run",
            receipt_route="/api/v1/foundry/receipts/receipt-fixture-bad-run",
        ),
    )
    with pytest.raises(ValidationError, match="accepted tasks exceed"):
        Run(**run)

    with pytest.raises(ValidationError):
        MetricValue(
            metric=MetricDefinition(metric_id="bad", definition="bad", unit="fraction"),
            value=float("inf"),
            uncertainty_note=None,
            denominator=Denominator(unit="slates", total=1, missing=0),
            fold="R0",
            scope="simulated",
            evidence_tier="synthetic-fixture",
            provenance=Provenance(
                receipt_id="receipt-fixture-bad-value",
                receipt_route="/api/v1/foundry/receipts/receipt-fixture-bad-value",
            ),
        )

    with pytest.raises(ValidationError, match="graded evaluation lacks"):
        Evaluation(
            evaluation_id="evaluation:bad",
            experiment_id="experiment:bad",
            disposition="graded",
            outcome_release_id=None,
            evidence_tier="synthetic-fixture",
            scope="simulated",
            provenance=Provenance(
                receipt_id="receipt-fixture-bad-evaluation",
                receipt_route=(
                    "/api/v1/foundry/receipts/receipt-fixture-bad-evaluation"
                ),
            ),
        )

    with pytest.raises(ValidationError, match="Extra inputs"):
        Denominator.model_validate(
            {"unit": "slates", "total": 1, "missing": 0, "invented": True}
        )
    with pytest.raises(ValidationError, match="receipt route"):
        Provenance(
            receipt_id="receipt-fixture-safe",
            receipt_route="gs://private-bucket/raw-receipt-body.json",
        )


def test_receipt_metadata_is_allowlisted_exact_identity(client: TestClient) -> None:
    response = client.get(
        "/api/v1/foundry/receipts/receipt-fixture-fill-0"
    )
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert set(payload) == {
        "receipt_id",
        "receipt_type",
        "status",
        "sha256",
        "generation",
        "bytes",
        "generated_at_utc",
    }
    assert payload["generation"].isdigit()
    assert payload["bytes"] > 0
    assert "gs://" not in response.text


def test_unknown_resources_return_sanitized_404(client: TestClient) -> None:
    for url in (
        "/api/v1/foundry/receipts/unknown",
        "/api/v1/foundry/books/book:missing",
        "/api/v1/foundry/slates/slate:none/lineups/lineup:none",
        "/api/v1/foundry/experiments/experiment:none/metrics",
    ):
        response = client.get(url)
        assert response.status_code == 404, url
        assert response.json()["reason_code"] == "not-found"
        assert "unknown" not in response.json()["detail"]


def test_winner_and_trait_fixture_evidence_is_unmistakably_synthetic(
    client: TestClient,
) -> None:
    comparison = client.get(
        "/api/v1/foundry/cohorts/compare",
        params={"cohort_a": "winners", "cohort_b": "matched-controls"},
    ).json()["payload"]
    assert comparison["winner_release_id"] == "fixture-winner-release-51"
    assert comparison["evidence_tier"] == "synthetic-fixture"
    assert comparison["metrics"][0]["denominator"]["total"] == 51

    rows = client.get(
        "/api/v1/foundry/traits/enrichment", params={"cohort": "winners"}
    ).json()["payload"]["rows"]
    coverage = next(row for row in rows if row["trait_id"] == "coverage-matchup")
    assert coverage["lift"] is None
    assert coverage["support"]["missing"] == 17


def test_lineup_detail_and_network_are_outcome_free_and_qualified(
    client: TestClient,
) -> None:
    detail = client.get(
        "/api/v1/foundry/slates/slate:2023-w1/lineups/lineup:fixture-001"
    ).json()["payload"]
    assert detail["realized_note"] == "unavailable-not-authorized"
    assert detail["outcome_release_id"] is None
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
    assert inferred["evidence_tier"] == "synthetic-fixture"
