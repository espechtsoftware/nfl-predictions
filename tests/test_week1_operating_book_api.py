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
V2_ENV = {
    **ENV,
    "IMAGE_SOURCE_COMMIT_SHA": "c" * 40,
    "IMAGE_DIGEST": "sha256:" + "d" * 64,
    "IMAGE_URI": (
        "us-central1-docker.pkg.dev/project/repo/app@sha256:" + "d" * 64
    ),
    "PAID_V3_CLOUD_BUILD_ID": "12345678-1234-1234-1234-123456789abc",
    "K_REVISION": "app-paidv3-cccccccc-12345678",
}


class ProjectionStore:
    def __init__(self) -> None:
        self.gids: list[int] = []
        self.projection_calls: list[tuple[int, int]] = []
        self.schedule_calls: list[tuple[int, int]] = []

    def classic_salaries(self, draft_group_id: int):
        self.gids.append(draft_group_id)
        return [{"salary": "authority"}]

    def projections(self, season: int, week: int):
        self.projection_calls.append((season, week))
        return [{"projection": "authority"}]

    def projection_batch(self, season: int, week: int, *, as_of):
        self.projection_calls.append((season, week))
        return [{"projection": "authority", "as_of": as_of}]

    def schedule_games(self, season: int, week: int):
        self.schedule_calls.append((season, week))
        return [{"schedule": "authority"}]


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
    assert projection_store.projection_calls == []
    assert calls == [(object_store, api.materialization_identity_from_environment(ENV))]


def test_v2_load_adds_the_fixed_projection_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exact = {"identity": "exact", "materialization": "book"}
    payload = {"complete": True, "dk_csv": "QB\r\n"}
    monkeypatch.setattr(
        api,
        "read_week1_operating_book_v1",
        lambda **_kwargs: exact,
    )

    marker = object()
    monkeypatch.setattr(api, "_week1_paid_validation_time_v2", lambda: marker)

    def build(
        *, exact_book, salary_rows, projection_rows, schedule_rows,
        validated_at, source_commit_sha, immutable_image_digest,
        cloud_build_id, immutable_image_uri, running_revision,
    ):
        assert exact_book == exact
        assert salary_rows == [{"salary": "authority"}]
        assert projection_rows == [{"projection": "authority", "as_of": marker}]
        assert schedule_rows == [{"schedule": "authority"}]
        assert validated_at is marker
        assert source_commit_sha == "c" * 40
        assert immutable_image_digest == "sha256:" + "d" * 64
        assert cloud_build_id == V2_ENV["PAID_V3_CLOUD_BUILD_ID"]
        assert immutable_image_uri == V2_ENV["IMAGE_URI"]
        assert running_revision == V2_ENV["K_REVISION"]
        return payload

    monkeypatch.setattr(api, "build_week1_operating_book_export_v2", build)
    projection_store = ProjectionStore()
    assert api.load_week1_operating_book_export_v2(
        projection_store=projection_store,
        object_store=object(),
        environment=V2_ENV,
    ) == payload
    assert projection_store.gids == [151307]
    assert projection_store.projection_calls == [(2026, 1)]
    assert projection_store.schedule_calls == [(2026, 1)]


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


def test_v2_routes_use_only_the_versioned_semantic_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "dk_csv": "QB\r\n",
        "materialization_sha256": "a" * 64,
        "export_sha256": "b" * 64,
        "canonical_game_policy_id": "unordered-normalized-team-opponent-v2",
    }
    monkeypatch.setattr(
        main,
        "load_week1_operating_book_export_v2",
        lambda *, projection_store: payload,
    )
    assert main.week1_operating_book_v2(store=object()) == payload
    response = main.week1_operating_book_csv_v2(store=object())
    assert bytes(response.body).decode() == payload["dk_csv"]
    assert response.headers["x-week1-canonical-game-policy"] == (
        payload["canonical_game_policy_id"]
    )


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
    assert "href='/week1/operating-book-v2.csv'" in page
    assert "fetch('/week1/operating-book-v2')" in page
