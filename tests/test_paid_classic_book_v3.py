"""Adversarial tests for the authoritative paid Classic v3 successor."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pandas as pd
import pytest
from fastapi import HTTPException

from nfl_dfs.app import main as app_main
from nfl_dfs.app.store import BigQueryStore
from nfl_dfs.config import settings
from nfl_dfs.optimizer.lineup import Lineup
from nfl_dfs.optimizer.paid_classic_book_v2 import (
    PAID_CLASSIC_BOUNDARY_ID as PAID_CLASSIC_BOUNDARY_ID_V2,
)
from nfl_dfs.optimizer.paid_classic_book_v3 import (
    PAID_CLASSIC_IMAGE_DIGEST_ENV,
    PAID_CLASSIC_BOUNDARY_ID,
    PAID_CLASSIC_GAME_CATALOG_SCHEMA,
    PAID_CLASSIC_SOURCE_COMMIT_ENV,
    build_paid_classic_catalog_v3,
    fill_paid_entries_csv_v3,
    paid_classic_projection_derivation_receipt_v3,
    to_paid_dk_csv_v3,
    validate_paid_classic_book_v3,
)

_PULLED_AT = pd.Timestamp("2026-09-01T15:00:00Z")
_GENERATED_AT = pd.Timestamp("2026-09-01T15:30:00Z")
_VALIDATED_AT = pd.Timestamp("2026-09-01T16:00:00Z")
_SOURCE_COMMIT = "a" * 40
_IMAGE_DIGEST = "sha256:" + "b" * 64


def _salary_rows() -> pd.DataFrame:
    # Real provider aliases are intentional: JAC->JAX, SD->LAC, OAK->LV.
    specs = [
        (101, "QB", "JAC", 7000),
        (102, "QB", "IND", 7000),
        (201, "RB", "JAC", 6500),
        (202, "RB", "IND", 6000),
        (203, "RB", "SD", 5000),
        (301, "WR", "JAC", 6000),
        (302, "WR", "IND", 5500),
        (303, "WR", "SD", 5000),
        (304, "WR", "OAK", 4500),
        (401, "TE", "IND", 4000),
        (402, "TE", "OAK", 3500),
        (501, "DST", "SD", 3000),
        (502, "DST", "OAK", 3000),
    ]
    return pd.DataFrame(
        [
            {
                "pulled_at": _PULLED_AT,
                "draft_group_id": 9001,
                "dk_player_id": player_id,
                "dk_draftable_id": player_id + 50_000_000,
                "display_name": f"Salary Player {player_id}",
                "team_abbr": team,
                "position": position,
                "salary": salary,
                "game_start": pd.Timestamp("2026-09-06T17:00:00Z"),
                "status": "",
            }
            for player_id, position, team, salary in specs
        ]
    )


def _projection_rows() -> pd.DataFrame:
    canonical = {"JAC": "JAX", "SD": "LAC", "OAK": "LV"}
    opponents = {"JAX": "IND", "IND": "JAX", "LAC": "LV", "LV": "LAC"}
    rows = []
    for salary in _salary_rows().to_dict("records"):
        team = canonical.get(salary["team_abbr"], salary["team_abbr"])
        rows.append(
            {
                "generated_at": _GENERATED_AT,
                "season": 2026,
                "week": 1,
                "dk_player_id": salary["dk_player_id"],
                "display_name": f"Projection Player {salary['dk_player_id']}",
                "position": salary["position"],
                "team": team,
                "opponent": opponents[team],
                "proj_points": 18.0,
            }
        )
    return pd.DataFrame(rows)


def _schedule_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": "2026_01_IND_JAX",
                "season": 2026,
                "week": 1,
                "game_type": "REG",
                "home_team": "JAX",
                "away_team": "IND",
            },
            {
                "game_id": "2026_01_LV_LAC",
                "season": 2026,
                "week": 1,
                "game_type": "REG",
                "home_team": "LAC",
                "away_team": "LV",
            },
        ]
    )


def _catalog(
    *,
    salaries: pd.DataFrame | None = None,
    projections: pd.DataFrame | None = None,
    schedules: pd.DataFrame | None = None,
):
    return build_paid_classic_catalog_v3(
        _salary_rows() if salaries is None else salaries,
        _projection_rows() if projections is None else projections,
        _schedule_rows() if schedules is None else schedules,
        draft_group_id=9001,
        season=2026,
        week=1,
        source_commit_sha=_SOURCE_COMMIT,
        immutable_image_digest=_IMAGE_DIGEST,
        validated_at=_VALIDATED_AT,
    )


def _lineup(ids: list[int], *, schedule_ids: bool = False) -> Lineup:
    salaries = _salary_rows().set_index("dk_player_id").to_dict("index")
    opponents = {"JAC": "IND", "IND": "JAC", "SD": "OAK", "OAK": "SD"}
    game_ids = {
        "JAC": "2026_01_IND_JAX",
        "IND": "2026_01_IND_JAX",
        "SD": "2026_01_LV_LAC",
        "OAK": "2026_01_LV_LAC",
    }
    players = []
    for player_id in ids:
        row = salaries[player_id]
        team = str(row["team_abbr"])
        opponent = opponents[team]
        players.append(
            {
                "id": player_id,
                "dk_id": int(row["dk_draftable_id"]),
                "name": f"Lineup Player {player_id}",
                "pos": row["position"],
                "team": team,
                "opp": opponent,
                "game_id": game_ids[team] if schedule_ids else f"{team}@{opponent}",
                "salary": int(row["salary"]),
                "proj": 18.0,
            }
        )
    return Lineup(players=players)


def _book(*, schedule_ids: bool = False) -> list[Lineup]:
    return [
        _lineup(
            [101, 201, 202, 301, 302, 303, 401, 304, 501],
            schedule_ids=schedule_ids,
        ),
        _lineup(
            [102, 201, 203, 301, 302, 304, 402, 303, 502],
            schedule_ids=schedule_ids,
        ),
    ]


def _ranked(book: list[Lineup]) -> list[dict]:
    return [
        {"lineup": lineup, "confidence": 1.0, "proj_mean": lineup.proj}
        for lineup in book
    ]


def _entries() -> str:
    return (
        "Entry ID,Contest Name,Contest ID,Entry Fee,"
        "QB,RB,RB,WR,WR,WR,TE,FLEX,DST,,Instructions\n"
        "1,Milly,77,$20,,,,,,,,,,,Keep this\n"
        "2,Milly,77,$20\n"
    )


def test_v3_uses_joined_authorities_and_accepts_real_team_aliases() -> None:
    catalog = _catalog()
    exported = to_paid_dk_csv_v3(_book(), expected_entries=2, catalog=catalog)

    assert PAID_CLASSIC_BOUNDARY_ID_V2 == "paid-classic-book-boundary-v2"
    assert exported.receipt["boundary_id"] == PAID_CLASSIC_BOUNDARY_ID
    assert exported.receipt["v2_compatibility_boundary_id"] == (
        PAID_CLASSIC_BOUNDARY_ID_V2
    )
    assert exported.receipt["authoritative_game_catalog_schema"] == (
        PAID_CLASSIC_GAME_CATALOG_SCHEMA
    )
    assert exported.receipt["authoritative_game_facts"] is True
    assert exported.receipt["game_claims_match_authority"] is True
    assert exported.receipt["canonical_game_policy_id"] == (
        "unordered-normalized-team-opponent-v2"
    )
    assert exported.receipt["semantic_draftkings_legal"] is True
    assert exported.receipt["source_commit_sha"] == _SOURCE_COMMIT
    assert exported.receipt["immutable_image_digest"] == _IMAGE_DIGEST
    assert len(exported.receipt["projection_batch_sha256"]) == 64
    audits = exported.receipt["semantic_roster_audits"]
    assert audits[0]["canonical_game_player_counts"] == {
        "IND|JAX": 6,
        "LAC|LV": 3,
    }
    reopened = list(csv.reader(io.StringIO(exported.csv_text)))
    assert reopened[1][0].startswith("Salary Player ")


def test_v3_accepts_exact_authoritative_schedule_game_ids() -> None:
    receipt = validate_paid_classic_book_v3(
        _book(schedule_ids=True), expected_entries=2, catalog=_catalog()
    )
    assert receipt["game_claims_match_authority"] is True


def test_fabricated_lineup_opponent_cannot_replace_joined_authority() -> None:
    book = _book()
    # Make every JAC claim self-consistent with a fabricated opponent/game.
    # A payload-only audit can accept this restatement; the joined authority
    # must reject it before auditing the roster.
    for player in book[0].players:
        if player["team"] == "JAC":
            player["opp"] = "OAK"
            player["game_id"] = "JAC@OAK"
    with pytest.raises(ValueError, match="opponent differs from the joined catalog"):
        validate_paid_classic_book_v3(
            book, expected_entries=2, catalog=_catalog()
        )


def test_fabricated_lineup_game_id_cannot_pass_with_real_team_and_opp() -> None:
    book = _book()
    book[0].players[0]["game_id"] = "fabricated-provider-game"
    with pytest.raises(ValueError, match="game_id differs from the joined catalog"):
        validate_paid_classic_book_v3(
            book, expected_entries=2, catalog=_catalog()
        )


def test_join_fails_on_projection_schedule_disagreement_and_mixed_batches() -> None:
    projections = _projection_rows()
    projections.loc[projections.dk_player_id == 101, "opponent"] = "NE"
    with pytest.raises(ValueError, match="projection game is absent"):
        _catalog(projections=projections)

    projections = _projection_rows()
    projections.loc[projections.dk_player_id == 101, "generated_at"] = (
        _GENERATED_AT + pd.Timedelta(minutes=1)
    )
    with pytest.raises(ValueError, match="mixes generated_at batches"):
        _catalog(projections=projections)


@pytest.mark.parametrize(
    ("commit", "digest", "message"),
    [
        ("a" * 39, _IMAGE_DIGEST, "full 40-character"),
        (_SOURCE_COMMIT, "b" * 64, "immutable sha256"),
    ],
)
def test_catalog_requires_full_commit_and_immutable_image_digest(
    commit: str, digest: str, message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_paid_classic_catalog_v3(
            _salary_rows(),
            _projection_rows(),
            _schedule_rows(),
            draft_group_id=9001,
            season=2026,
            week=1,
            source_commit_sha=commit,
            immutable_image_digest=digest,
            validated_at=_VALIDATED_AT,
        )


def test_v3_entries_fill_retains_exact_book_and_upgrades_capture() -> None:
    captures: list[dict] = []
    exported = fill_paid_entries_csv_v3(
        _entries(),
        _book(),
        catalog=_catalog(),
        contest_id="77",
        prepared_entry_capture=captures.append,
    )
    assert exported.receipt["boundary_id"] == PAID_CLASSIC_BOUNDARY_ID
    assert exported.receipt["targeted_entries"] == 2
    assert len(captures) == 1
    assert captures[0]["schema_version"] == (
        "paid-entry-capture/v2-canonical-game"
    )
    assert captures[0]["paid_export_receipt_sha256"] == (
        exported.receipt["export_receipt_sha256"]
    )


class _AuthoritativeStore:
    def classic_salaries(self, draft_group_id: int) -> pd.DataFrame:
        rows = _salary_rows()
        return rows[rows.draft_group_id == draft_group_id].copy()

    def projections(self, season: int, week: int) -> pd.DataFrame:
        rows = _projection_rows()
        return rows[(rows.season == season) & (rows.week == week)].copy()

    def projection_batch(self, season: int, week: int, *, as_of) -> pd.DataFrame:
        assert pd.Timestamp(as_of) == _VALIDATED_AT
        return self.projections(season, week)

    def schedule_games(self, season: int, week: int) -> pd.DataFrame:
        rows = _schedule_rows()
        return rows[(rows.season == season) & (rows.week == week)].copy()


def test_paid_v3_routes_bind_game_authority_and_v2_routes_still_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    book = _book()
    build_calls = []

    def build_once(req, store, **kwargs):
        build_calls.append((req, store, kwargs))
        return book, _ranked(book)

    monkeypatch.setattr(app_main, "_build_classic", build_once)
    monkeypatch.setattr(
        app_main, "_paid_classic_now_v3", lambda: _VALIDATED_AT.to_pydatetime()
    )
    monkeypatch.setenv(PAID_CLASSIC_SOURCE_COMMIT_ENV, _SOURCE_COMMIT)
    monkeypatch.setenv(PAID_CLASSIC_IMAGE_DIGEST_ENV, _IMAGE_DIGEST)
    monkeypatch.setattr(app_main, "_with_watch_notes", lambda players: players)
    monkeypatch.setattr(
        "nfl_dfs.notes.record_entered_lineups", lambda *args, **kwargs: None
    )
    store = _AuthoritativeStore()
    request = app_main.LineupRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        n_lineups=2,
        sim=False,
    )

    preview = app_main.build_paid_lineups_v3(request, store=store)
    assert preview["paid_export"]["boundary_id"] == PAID_CLASSIC_BOUNDARY_ID
    assert preview["paid_export"]["authoritative_game_facts"] is True
    response = app_main.build_paid_lineups_csv_v3(request, store=store)
    assert response.status_code == 200
    assert response.headers["x-paid-book-boundary"] == PAID_CLASSIC_BOUNDARY_ID
    assert response.headers["x-paid-book-game-authority"] == "true"
    assert len(response.headers["x-paid-book-game-catalog-sha256"]) == 64
    assert response.headers["x-paid-book-source-commit"] == _SOURCE_COMMIT
    assert response.headers["x-paid-book-image-digest"] == _IMAGE_DIGEST

    entries_request = app_main.FillEntriesRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        entries_csv=_entries(),
        contest_id="77",
        sim=False,
    )
    entries = app_main.fill_paid_classic_entries_v3(entries_request, store=store)
    assert entries.status_code == 200
    assert entries.headers["x-paid-book-boundary"] == PAID_CLASSIC_BOUNDARY_ID
    assert len(build_calls) == 3

    paths = {getattr(route, "path", None) for route in app_main.app.routes}
    assert {
        "/lineups/paid-v2",
        "/lineups/paid-v2.csv",
        "/lineups/entries/paid-v2.csv",
        "/lineups/paid-v3",
        "/lineups/paid-v3.csv",
        "/lineups/entries/paid-v3.csv",
    } <= paths


def test_paid_v3_route_requires_an_exact_slate_before_any_authority_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    book = _book()
    monkeypatch.setattr(
        app_main, "_build_classic", lambda req, store, **kwargs: (book, _ranked(book))
    )
    request = app_main.LineupRequest(season=2026, week=1, n_lineups=2, sim=False)
    with pytest.raises(HTTPException, match="v3 requires draft_group_id"):
        app_main.build_paid_lineups_csv_v3(request, store=_AuthoritativeStore())


def test_schedule_store_reads_only_authoritative_regular_season_week(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def query(sql, *, params):
        calls.append((sql, params))
        return pd.DataFrame()

    monkeypatch.setattr("nfl_dfs.bq.query_df", query)
    BigQueryStore().schedule_games(2026, 1)
    assert f"FROM `{settings.raw}.schedules`" in calls[0][0]
    assert "game_type = 'REG'" in calls[0][0]
    assert calls[0][1] == {"season": 2026, "week": 1}


def test_projection_batch_store_reads_one_global_asof_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def query(sql, *, params):
        calls.append((sql, params))
        return pd.DataFrame()

    monkeypatch.setattr("nfl_dfs.bq.query_df", query)
    BigQueryStore().projection_batch(2026, 1, as_of=_VALIDATED_AT)
    sql, params = calls[0]
    assert "MAX(generated_at)" in sql
    assert "generated_at <= TIMESTAMP(@as_of)" in sql
    assert "ROW_NUMBER" not in sql
    assert params == {"season": 2026, "week": 1, "as_of": _VALIDATED_AT}


def test_paid_generation_frame_uses_catalog_batch_not_latest_projection_read() -> None:
    class NoLatestStore(_AuthoritativeStore):
        def projections(self, season: int, week: int) -> pd.DataFrame:
            raise AssertionError("per-player-latest projection path was used")

    request = app_main.LineupRequest(
        season=2026, week=1, draft_group_id=9001, n_lineups=2, sim=False
    )
    catalog = _catalog()
    frame, ids = app_main._classic_projections(
        request, NoLatestStore(), paid_catalog=catalog
    )
    assert set(frame.dk_player_id.astype(int)) == set(catalog.by_player_id)
    assert frame.set_index("dk_player_id").proj_points.to_dict() == {
        player_id: float(row["projection"])
        for player_id, row in catalog.by_player_id.items()
    }
    assert ids == {
        player_id: int(row["draftable_id"])
        for player_id, row in catalog.by_player_id.items()
    }


def test_paid_sim_generation_receives_exact_batch_and_bound_transform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    book = _book()

    def build_sim(*args, **kwargs):
        captured.update(kwargs)
        receipt = kwargs["projection_authority_receipt"]
        for lineup in book:
            lineup.paid_projection_derivation_receipt = dict(receipt)
        return book

    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups", build_sim
    )
    request = app_main.LineupRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        n_lineups=2,
        sim=True,
        apply_notes=False,
    )
    catalog = _catalog()
    lineups, _ = app_main._build_classic(
        request, _AuthoritativeStore(), paid_catalog=catalog
    )
    assert len(lineups) == 2
    assert captured["projection_authority"] == {
        player_id: float(row["projection"])
        for player_id, row in catalog.by_player_id.items()
    }
    derivation = captured["projection_authority_receipt"]
    assert derivation["projection_batch_sha256"] == catalog.projection_batch_sha256
    assert derivation["transformation"]["mode"] == "simulation"
    assert derivation["transformation"]["world_count"] == 30_000


def test_paid_v3_rejects_nonfinite_and_non_prelock_projection_authority() -> None:
    projections = _projection_rows()
    projections.loc[0, "proj_points"] = float("nan")
    with pytest.raises(ValueError, match="proj_points is invalid"):
        _catalog(projections=projections)

    projections = _projection_rows()
    projections["generated_at"] = _VALIDATED_AT + pd.Timedelta(seconds=1)
    with pytest.raises(ValueError, match="later than validation"):
        _catalog(projections=projections)

    salaries = _salary_rows()
    salaries["game_start"] = _VALIDATED_AT
    with pytest.raises(ValueError, match="reaches or follows slate lock"):
        _catalog(salaries=salaries)


def test_paid_v3_rejects_nonfinite_selected_lineup_projection() -> None:
    book = _book()
    book[0].players[0]["proj"] = float("inf")
    with pytest.raises(ValueError, match="projection is invalid"):
        validate_paid_classic_book_v3(
            book, expected_entries=2, catalog=_catalog()
        )


def test_transformed_projection_requires_exact_certified_batch_receipt() -> None:
    catalog = _catalog()
    book = _book()
    book[0].players[0]["proj"] = 19.0
    with pytest.raises(ValueError, match="not bound to the certified"):
        validate_paid_classic_book_v3(book, expected_entries=2, catalog=catalog)
    derivation = paid_classic_projection_derivation_receipt_v3(
        catalog,
        transformation={"mode": "simulation", "seed": 42},
    )
    for lineup in book:
        lineup.paid_projection_derivation_receipt = dict(derivation)
    receipt = validate_paid_classic_book_v3(
        book, expected_entries=2, catalog=catalog
    )
    assert receipt["projection_batch_sha256"] == catalog.projection_batch_sha256


def test_paid_v3_rejects_mixed_deterministic_and_transformed_derivations() -> None:
    catalog = _catalog()
    book = _book()
    book[0].players[0]["proj"] = 19.0
    book[0].paid_projection_derivation_receipt = (
        paid_classic_projection_derivation_receipt_v3(
            catalog,
            transformation={"mode": "simulation", "seed": 42},
        )
    )
    with pytest.raises(ValueError, match="mix projection transformations"):
        validate_paid_classic_book_v3(
            book, expected_entries=2, catalog=catalog
        )


def test_classic_web_ui_uses_paid_v3_successor() -> None:
    html = app_main.lineups_page()
    assert "sd?'/showdown/lineups':'/lineups/paid-v3'" in html
    assert "paid v3 exact K" in html


def test_paid_v3_cloud_build_authenticates_commit_and_resolves_digest() -> None:
    source = Path("cloudbuild.paid-boundary-v3.yaml").read_text()
    assert "_CODE_SHA: unknown" in source
    assert "^[0-9a-f]{40}$" in source
    assert "git -C release fetch --no-tags origin '${_CODE_SHA}'" in source
    assert "git -C release checkout --detach '${_CODE_SHA}'" in source
    assert "dir: release" in source
    assert 'IMAGE_SOURCE_COMMIT_SHA"] == os.environ["EXPECTED_SOURCE_COMMIT' in source
    helper = Path("scripts/build_paid_boundary_v3_image.sh").read_text()
    assert "FULL_PUSHED_CODE_SHA must equal local origin/main" in helper
    assert "results.images[0].digest" in helper
    assert "IMAGE_DIGEST" in helper
