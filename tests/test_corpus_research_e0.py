from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nfl_dfs.app import corpus_research_e0 as api

SUMMARY = {
    "schema_version": "fixture-summary/v1",
    "summary_sha256": "a" * 64,
    "outcome_funnel_summary": {"high_score_lineup_count": 279},
}


class _UnavailableReader:
    def read(self) -> dict[str, object]:
        raise api.HistoricalE0SummaryUnavailable(
            "fixture-not-ready", "fixture is not ready"
        )


class _ReadyReader:
    def read(self) -> dict[str, object]:
        return deepcopy(SUMMARY)


def _client(reader: object) -> TestClient:
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_historical_e0_summary_reader] = lambda: reader
    return TestClient(app)


def test_router_has_exactly_one_get_only_aggregate_route() -> None:
    routes = [route for route in api.router.routes if hasattr(route, "methods")]
    assert len(routes) == 1
    assert routes[0].path == ("/api/corpus-research/e0/historical-realized-summary")
    assert routes[0].methods == {"GET"}


def test_unconfigured_aggregate_fails_closed() -> None:
    response = _client(_UnavailableReader()).get(
        "/api/corpus-research/e0/historical-realized-summary"
    )

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "schema_version": api.ENDPOINT_SCHEMA,
        "ready": False,
        "reason_code": "fixture-not-ready",
        "message": "fixture is not ready",
        "read_only": True,
        "summary_only": True,
        "descriptive_development_only": True,
        "neo4j_access": False,
        "promotion_authority": False,
        "decision_authority": False,
    }


def test_get_returns_only_an_api_boundary_validated_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def validate(value: object) -> dict[str, object]:
        calls.append(value)
        assert value == SUMMARY
        return deepcopy(SUMMARY)

    monkeypatch.setattr(
        api.summary_v1, "validate_historical_realized_summary_v1", validate
    )
    response = _client(_ReadyReader()).get(
        "/api/corpus-research/e0/historical-realized-summary"
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["ready"] is True
    assert body["read_only"] is True
    assert body["summary_only"] is True
    assert body["neo4j_access"] is False
    assert body["promotion_authority"] is False
    assert body["summary"] == SUMMARY
    assert len(calls) == 1


def test_file_reader_requires_canonical_regular_file_and_revalidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validated: list[object] = []

    def validate(value: object) -> dict[str, object]:
        validated.append(value)
        return deepcopy(SUMMARY)

    monkeypatch.setattr(
        api.summary_v1, "validate_historical_realized_summary_v1", validate
    )
    path = tmp_path / "summary.json"
    raw = api.summary_v1.canonical_json_bytes(SUMMARY) + b"\n"
    path.write_bytes(raw)
    reader = api.FileHistoricalE0SummaryReader(path)

    assert reader.read() == SUMMARY
    assert validated == [SUMMARY]

    path.write_bytes(api.summary_v1.canonical_json_bytes(SUMMARY))
    with pytest.raises(
        api.HistoricalE0SummaryUnavailable,
        match="failed closed",
    ):
        reader.read()


def test_file_reader_rejects_missing_symlink_and_oversize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = api.FileHistoricalE0SummaryReader(tmp_path / "missing.json")
    with pytest.raises(api.HistoricalE0SummaryUnavailable):
        missing.read()

    target = tmp_path / "target.json"
    target.write_bytes(api.summary_v1.canonical_json_bytes(SUMMARY) + b"\n")
    link = tmp_path / "summary-link.json"
    link.symlink_to(target)
    with pytest.raises(api.HistoricalE0SummaryUnavailable):
        api.FileHistoricalE0SummaryReader(link).read()

    monkeypatch.setattr(api, "MAX_SUMMARY_BYTES", 2)
    with pytest.raises(api.HistoricalE0SummaryUnavailable):
        api.FileHistoricalE0SummaryReader(target).read()


def test_unexpected_reader_or_validator_failure_returns_no_partial_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject(_value: object) -> dict[str, object]:
        raise RuntimeError("fixture validation failure")

    monkeypatch.setattr(
        api.summary_v1, "validate_historical_realized_summary_v1", reject
    )
    response = _client(_ReadyReader()).get(
        "/api/corpus-research/e0/historical-realized-summary"
    )

    assert response.status_code == 503
    assert "summary" not in response.json()
    assert response.json()["reason_code"] == (
        "historical-e0-summary-reader-boundary-failed"
    )
