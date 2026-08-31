from __future__ import annotations

import pytest
from fastapi import HTTPException

from nfl_dfs.app import main
from nfl_dfs.app import week1_operating_book_api as api


ENV = {
    "WEEK1_OPERATING_BOOK_URI": "gs://test/prelock/week1-book.json",
    "WEEK1_OPERATING_BOOK_GENERATION": "123",
    "WEEK1_OPERATING_BOOK_SHA256": "a" * 64,
    "WEEK1_OPERATING_BOOK_BYTES": "456",
}


class ProjectionStore:
    def __init__(self) -> None:
        self.gids: list[int] = []

    def classic_salaries(self, draft_group_id: int):
        self.gids.append(draft_group_id)
        return [{"salary": "authority"}]


def test_deployment_identity_is_all_or_nothing_and_generation_pinned() -> None:
    assert api.materialization_identity_from_environment(ENV) == {
        "uri": ENV["WEEK1_OPERATING_BOOK_URI"],
        "generation": "123",
        "sha256": "a" * 64,
        "bytes": 456,
    }
    for missing in ENV:
        broken = dict(ENV)
        broken.pop(missing)
        with pytest.raises(api.Week1OperatingBookAPIError, match="not configured"):
            api.materialization_identity_from_environment(broken)


@pytest.mark.parametrize("value", ("", "x", "-1"))
def test_invalid_byte_identity_fails_closed(value: str) -> None:
    broken = {**ENV, "WEEK1_OPERATING_BOOK_BYTES": value}
    with pytest.raises(api.Week1OperatingBookAPIError):
        api.materialization_identity_from_environment(broken)


def test_load_uses_only_deployment_identity_and_fixed_week1_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    exact = {"identity": "exact", "materialization": "book"}
    payload = {"complete": True, "dk_csv": "QB\r\n"}

    def read(*, store, materialization_identity):
        calls.append((store, materialization_identity))
        return exact

    def build(*, exact_book, salary_rows):
        assert exact_book == exact
        assert salary_rows == [{"salary": "authority"}]
        return payload

    monkeypatch.setattr(api, "read_week1_operating_book_v1", read)
    monkeypatch.setattr(api, "build_week1_operating_book_export_v1", build)
    projection_store = ProjectionStore()
    object_store = object()
    assert api.load_week1_operating_book_export(
        projection_store=projection_store,
        object_store=object_store,
        environment=ENV,
    ) == payload
    assert projection_store.gids == [151307]
    assert calls == [(object_store, api.materialization_identity_from_environment(ENV))]


def test_canonical_routes_accept_no_build_request_and_share_one_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "complete": True,
        "dk_csv": "QB,RB\r\nA (1),B (2)\r\n",
        "materialization_sha256": "a" * 64,
        "export_sha256": "b" * 64,
    }
    monkeypatch.setattr(
        main,
        "load_week1_operating_book_export",
        lambda *, projection_store: payload,
    )
    store = object()
    assert main.week1_operating_book(store=store) == payload
    response = main.week1_operating_book_csv(store=store)
    assert bytes(response.body).decode() == payload["dk_csv"]
    assert response.headers["x-week1-book-sha256"] == "a" * 64
    assert response.headers["x-week1-export-sha256"] == "b" * 64


def test_canonical_route_fails_503_instead_of_using_generic_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*, projection_store):
        raise api.Week1OperatingBookAPIError("not configured")

    monkeypatch.setattr(main, "load_week1_operating_book_export", fail)
    with pytest.raises(HTTPException) as caught:
        main.week1_operating_book(store=object())
    assert caught.value.status_code == 503


def test_lineup_page_exposes_canonical_book_visuals_separately() -> None:
    page = main.lineups_page()
    assert "Week 1 canonical operating book" in page
    assert "id='week1sources'" in page
    assert "id='week1exposure'" in page
    assert "href='/week1/operating-book.csv'" in page
    assert "fetch('/week1/operating-book')" in page
