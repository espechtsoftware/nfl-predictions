"""Adversarial tests for the authoritative paid Classic v3 successor."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi import HTTPException

from nfl_dfs.app import main as app_main
from nfl_dfs.app.store import BigQueryStore
from nfl_dfs.config import settings
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.optimizer.construction_presets import LEGALITY_ONLY_PRESET_ID
from nfl_dfs.optimizer.lineup import Lineup
from nfl_dfs.optimizer.paid_classic_book_v2 import (
    PAID_CLASSIC_BOUNDARY_ID as PAID_CLASSIC_BOUNDARY_ID_V2,
)
from nfl_dfs.optimizer.paid_classic_book_v3 import (
    _ENGINE_RECEIPT_ISSUER,
    PAID_CLASSIC_BOUNDARY_ID,
    PAID_CLASSIC_BUILD_ID_ENV,
    PAID_CLASSIC_GAME_CATALOG_SCHEMA,
    PAID_CLASSIC_IMAGE_DIGEST_ENV,
    PAID_CLASSIC_IMAGE_URI_ENV,
    PAID_CLASSIC_REVISION_ENV,
    PAID_CLASSIC_SOURCE_COMMIT_ENV,
    PaidClassicEngineReceiptV3,
    _canonical_sha256,
    _issue_paid_classic_engine_receipt_v3,
    build_paid_classic_catalog_v3,
    fill_paid_entries_csv_v3,
    paid_classic_projection_authority_v3,
    paid_classic_projection_derivation_receipt_v3,
    to_paid_dk_csv_v3,
    validate_paid_classic_book_v3,
)

_PULLED_AT = pd.Timestamp("2026-09-01T15:00:00Z")
_GENERATED_AT = pd.Timestamp("2026-09-01T15:30:00Z")
_VALIDATED_AT = pd.Timestamp("2026-09-01T16:00:00Z")
_SOURCE_COMMIT = "a" * 40
_IMAGE_DIGEST = "sha256:" + "b" * 64
_BUILD_ID = "12345678-1234-1234-1234-123456789abc"
_IMAGE_URI = "us-central1-docker.pkg.dev/project/repo/app@" + _IMAGE_DIGEST
_REVISION = "nfl-dfs-app-paidv3-aaaaaaaa-12345678"


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
                "proj_p50": 17.0,
                "proj_p90": 28.0,
                "proj_std": 7.0,
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
        cloud_build_id=_BUILD_ID,
        immutable_image_uri=_IMAGE_URI,
        running_revision=_REVISION,
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


def _engine_receipt(catalog, book: list[Lineup]):
    pairs = [
        {
            "label": f"R{index}",
            "projection_seed": pair[0],
            "role_seed": pair[1],
        }
        for index, pair in enumerate(
            ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs
        )
    ]
    def artifact(version: str, component: str, digest: str) -> dict:
        value = {
            "schema_version": "loaded-component-model-artifacts/v1",
            "model_version": version,
            "components": [{
                "component": component,
                "member_count": 1,
                "member_sha256": [digest],
            }],
        }
        value["artifact_sha256"] = hashlib.sha256(json.dumps(
            value, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        return value

    artifacts = {
        row["label"]: {
            "projection": artifact(
                "pooled/components__tail_k1/2026-W35", "receiving", "c" * 64
            ),
            "role": artifact(
                "pooled/components__tail_k1_role/2026-W35",
                "receiving", "d" * 64,
            ),
        }
        for row in pairs
    }
    features = {
        row["label"]: {
            "projection": {
                "sha256": "e" * 64, "rows": 13, "columns": ["id"]
            },
            "role": {
                "sha256": "e" * 64, "rows": 13, "columns": ["id"]
            },
        }
        for row in pairs
    }
    notes = {
        row["label"]: {
            "projection_component_notes": {
                "state": "disabled",
                "before_sha256": "1" * 64,
                "effective_sha256": "1" * 64,
                "changed": False,
            },
            "role_component_notes": {
                "state": "disabled",
                "before_sha256": "2" * 64,
                "effective_sha256": "2" * 64,
                "changed": False,
            },
            "preferences": {
                "state": "disabled",
                "source_rows_sha256": None,
                "applied_ban_player_ids": [],
                "applied_boost_player_ids": [],
            },
        }
        for row in pairs
    }
    construction = ADOPTED_CLASSIC_POLICY.construction_preset()
    allowed = sorted(catalog.by_player_id)
    salary_items = sorted(
        (int(player_id), int(row["salary"]))
        for player_id, row in catalog.by_player_id.items()
    )

    def digest(value: object) -> str:
        return hashlib.sha256(json.dumps(
            value, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
    return _issue_paid_classic_engine_receipt_v3(
        paid_classic_projection_authority_v3(catalog),
        mode="simulation",
        lineups=book,
        seed_pairs=pairs,
        worlds_per_block=10_000,
        selection_world_count=50_000,
        model_artifacts=artifacts,
        feature_snapshots=features,
        notes_preferences=notes,
        locks=[],
        bans=[],
        theses=[],
        construction_policy=construction.receipt(),
        request_inputs={
            "season": 2026,
            "week": 1,
            "draft_group_id": 9001,
            "n_entries": len(book),
            "contest_max_entries": 150,
            "objective": "proj_points",
            "field_size": None,
            "requested_tail_line": None,
            "requested_leverage_scale": 1.0,
            "apply_notes": False,
            "construction_preset_id": construction.preset_id,
            "tail_line": ADOPTED_CLASSIC_POLICY.tail_line,
            "leverage_scale": 1.0,
            "allowed_player_count": len(allowed),
            "allowed_player_ids_sha256": digest(allowed),
            "salary_override_count": len(salary_items),
            "salary_overrides_sha256": digest(salary_items),
        },
        policy_environment=ADOPTED_CLASSIC_POLICY.engine_environment(
            construction_preset=construction
        ),
    )


def _attach_engine_receipt(catalog, book: list[Lineup]) -> list[Lineup]:
    receipt = _engine_receipt(catalog, book)
    for lineup in book:
        lineup.paid_projection_derivation_receipt = receipt
    return book


def _mutated_engine_receipt(receipt, mutation) -> PaidClassicEngineReceiptV3:
    payload = receipt.as_dict()
    payload.pop("receipt_sha256")
    mutation(payload)
    payload["receipt_sha256"] = _canonical_sha256(payload)
    return PaidClassicEngineReceiptV3(
        payload, _issuer=_ENGINE_RECEIPT_ISSUER
    )


def _mutate_projection_model_version(body: dict) -> None:
    artifact = body["model_artifacts"]["R0"]["projection"]
    artifact["model_version"] = "pooled/components__wrong/2026-W35"
    artifact["artifact_sha256"] = _canonical_sha256({
        key: value for key, value in artifact.items()
        if key != "artifact_sha256"
    })


def _entries() -> str:
    return (
        "Entry ID,Contest Name,Contest ID,Entry Fee,"
        "QB,RB,RB,WR,WR,WR,TE,FLEX,DST,,Instructions\n"
        "1,Milly,77,$20,,,,,,,,,,,Keep this\n"
        "2,Milly,77,$20\n"
    )


def test_v3_uses_joined_authorities_and_accepts_real_team_aliases() -> None:
    catalog = _catalog()
    book = _attach_engine_receipt(catalog, _book())
    exported = to_paid_dk_csv_v3(book, expected_entries=2, catalog=catalog)

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
    catalog = _catalog()
    book = _attach_engine_receipt(catalog, _book(schedule_ids=True))
    receipt = validate_paid_classic_book_v3(
        book, expected_entries=2, catalog=catalog
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
            cloud_build_id=_BUILD_ID,
            immutable_image_uri=_IMAGE_URI,
            running_revision=_REVISION,
            validated_at=_VALIDATED_AT,
        )


@pytest.mark.parametrize(
    ("deployment", "message"),
    [
        ({"cloud_build_id": ""}, "Cloud Build ID"),
        (
            {"immutable_image_uri": "registry.example/app:latest"},
            "runtime image URI must be immutable",
        ),
        (
            {
                "immutable_image_uri": (
                    "registry.example/app@sha256:" + "c" * 64
                )
            },
            "match IMAGE_DIGEST",
        ),
        ({"running_revision": ""}, "running Cloud Run revision"),
    ],
)
def test_catalog_requires_complete_runtime_deployment_identity(
    deployment: dict[str, str], message: str,
) -> None:
    values = {
        "cloud_build_id": _BUILD_ID,
        "immutable_image_uri": _IMAGE_URI,
        "running_revision": _REVISION,
        **deployment,
    }
    with pytest.raises(ValueError, match=message):
        build_paid_classic_catalog_v3(
            _salary_rows(),
            _projection_rows(),
            _schedule_rows(),
            draft_group_id=9001,
            season=2026,
            week=1,
            source_commit_sha=_SOURCE_COMMIT,
            immutable_image_digest=_IMAGE_DIGEST,
            validated_at=_VALIDATED_AT,
            **values,
        )


def test_v3_entries_fill_retains_exact_book_and_upgrades_capture() -> None:
    captures: list[dict] = []
    catalog = _catalog()
    book = _attach_engine_receipt(catalog, _book())
    exported = fill_paid_entries_csv_v3(
        _entries(),
        book,
        catalog=catalog,
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
    catalog = _catalog()
    book = _attach_engine_receipt(catalog, _book())
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
    monkeypatch.setenv(PAID_CLASSIC_BUILD_ID_ENV, _BUILD_ID)
    monkeypatch.setenv(PAID_CLASSIC_IMAGE_URI_ENV, _IMAGE_URI)
    monkeypatch.setenv(PAID_CLASSIC_REVISION_ENV, _REVISION)
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
    assert response.headers["x-paid-book-cloud-build"] == _BUILD_ID
    assert response.headers["x-paid-book-image-uri"] == _IMAGE_URI
    assert response.headers["x-paid-book-revision"] == _REVISION

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
    assert catalog.projection_distribution_columns == (
        "proj_p50", "proj_p90", "proj_std"
    )
    assert {"proj_p50", "proj_p90", "proj_std"} <= set(frame.columns)


@pytest.mark.parametrize("objective", ["proj_points", "proj_p50", "proj_p90"])
def test_paid_milp_issues_post_execution_receipt_and_reopens_objectives(
    objective: str,
) -> None:
    catalog = _catalog()
    request = app_main.LineupRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        n_lineups=2,
        sim=False,
        apply_notes=False,
        objective=objective,
        construction_preset_id=LEGALITY_ONLY_PRESET_ID,
    )
    lineups, ranked = app_main._build_classic(
        request, _AuthoritativeStore(), paid_catalog=catalog
    )
    assert len(lineups) == len(ranked) == 2
    assert all(
        isinstance(
            getattr(lineup, "paid_projection_derivation_receipt", None),
            PaidClassicEngineReceiptV3,
        )
        for lineup in lineups
    )
    receipt = validate_paid_classic_book_v3(
        lineups, expected_entries=2, catalog=catalog
    )
    derivation = receipt["projection_derivation_receipt"]
    assert derivation["mode"] == "milp"
    assert derivation["request_inputs"]["objective"] == objective


def test_paid_milp_rejects_unimplemented_thesis_floor() -> None:
    request = app_main.LineupRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        n_lineups=2,
        sim=False,
        apply_notes=False,
        construction_preset_id=LEGALITY_ONLY_PRESET_ID,
        theses=[{"players": [101, 301], "min": 1}],
    )
    with pytest.raises(HTTPException, match="does not implement portfolio thesis"):
        app_main._build_classic(
            request, _AuthoritativeStore(), paid_catalog=_catalog()
        )


def test_paid_generation_rejects_unsupported_distribution_objectives_cleanly() -> None:
    projections = _projection_rows().drop(
        columns=["proj_p50", "proj_p90", "proj_std"]
    )
    catalog = _catalog(projections=projections)
    request = app_main.LineupRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        n_lineups=2,
        sim=False,
        objective="proj_p90",
    )
    with pytest.raises(HTTPException, match="objective proj_p90 is unsupported"):
        app_main._build_classic(
            request, _AuthoritativeStore(), paid_catalog=catalog
        )


def test_paid_sim_rejects_uncertified_distribution_objective_cleanly() -> None:
    request = app_main.LineupRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        n_lineups=2,
        sim=True,
        objective="proj_p90",
    )
    with pytest.raises(
        HTTPException, match="simulation objective proj_p90 is unsupported"
    ):
        app_main._build_classic(
            request, _AuthoritativeStore(), paid_catalog=_catalog()
        )


def test_paid_generation_rejects_missing_sigma_instead_of_degenerate_confidence() -> None:
    projections = _projection_rows().drop(
        columns=["proj_p50", "proj_p90", "proj_std"]
    )
    catalog = _catalog(projections=projections)
    request = app_main.LineupRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        n_lineups=2,
        sim=False,
    )
    with pytest.raises(HTTPException, match="requires certified positive proj_std"):
        app_main._build_classic(
            request, _AuthoritativeStore(), paid_catalog=catalog
        )


def test_catalog_rejects_partial_distribution_authority() -> None:
    projections = _projection_rows().drop(columns=["proj_std"])
    with pytest.raises(ValueError, match="must provide proj_p50, proj_p90"):
        _catalog(projections=projections)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("proj_std", 0.0, "proj_std must be positive"),
        ("proj_std", float("nan"), "proj_std is invalid"),
        ("proj_p50", 29.0, "proj_p50 above proj_p90"),
    ],
)
def test_catalog_rejects_invalid_distribution_authority(
    column: str, value: float, message: str,
) -> None:
    projections = _projection_rows()
    projections.loc[0, column] = value
    with pytest.raises(ValueError, match=message):
        _catalog(projections=projections)


def test_paid_sim_generation_receives_exact_batch_and_bound_transform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    book = _book()
    catalog = _catalog()

    def build_sim(*args, **kwargs):
        captured.update(kwargs)
        receipt = _engine_receipt(catalog, book)
        for lineup in book:
            lineup.paid_projection_derivation_receipt = receipt
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
    lineups, _ = app_main._build_classic(
        request, _AuthoritativeStore(), paid_catalog=catalog
    )
    assert len(lineups) == 2
    assert captured["projection_authority"] == {
        player_id: float(row["projection"])
        for player_id, row in catalog.by_player_id.items()
    }
    authority = captured["projection_authority_receipt"]
    assert authority.as_dict()["projection_batch_sha256"] == (
        catalog.projection_batch_sha256
    )
    assert "transformation" not in authority.as_dict()
    assert captured["paid_request_inputs"]["objective"] == "proj_points"


def test_paid_sim_generation_rejects_missing_engine_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups",
        lambda *args, **kwargs: _book(),
    )
    request = app_main.LineupRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        n_lineups=2,
        sim=True,
        apply_notes=False,
    )
    with pytest.raises(HTTPException, match="engine-produced post-execution"):
        app_main._build_classic(
            request, _AuthoritativeStore(), paid_catalog=_catalog()
        )


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


def test_exact_catalog_objectives_use_validator_created_deterministic_receipt() -> None:
    receipt = validate_paid_classic_book_v3(
        _book(), expected_entries=2, catalog=_catalog()
    )
    derivation = receipt["projection_derivation_receipt"]
    assert derivation["mode"] == "deterministic-exact"
    assert derivation["schema_version"] == (
        "paid-classic-deterministic-projection/v2"
    )
    assert derivation["receipt_sha256"] == _canonical_sha256(
        {key: value for key, value in derivation.items() if key != "receipt_sha256"}
    )


def test_transformed_projection_requires_exact_certified_batch_receipt() -> None:
    catalog = _catalog()
    book = _book()
    book[0].players[0]["proj"] = 19.0
    with pytest.raises(ValueError, match="not bound to the certified"):
        validate_paid_classic_book_v3(book, expected_entries=2, catalog=catalog)
    with pytest.raises(ValueError, match="caller-supplied"):
        paid_classic_projection_derivation_receipt_v3(
            catalog,
            transformation={"mode": "simulation", "seed": 42},
        )
    forged = paid_classic_projection_authority_v3(catalog).as_dict()
    for lineup in book:
        lineup.paid_projection_derivation_receipt = forged
    with pytest.raises(ValueError, match="not engine-produced"):
        validate_paid_classic_book_v3(
            book, expected_entries=2, catalog=catalog
        )
    derivation = _engine_receipt(catalog, book)
    for lineup in book:
        lineup.paid_projection_derivation_receipt = derivation
    receipt = validate_paid_classic_book_v3(
        book, expected_entries=2, catalog=catalog
    )
    assert receipt["projection_batch_sha256"] == catalog.projection_batch_sha256


def test_paid_v3_rejects_mixed_engine_and_deterministic_derivations() -> None:
    catalog = _catalog()
    book = _book()
    book[0].players[0]["proj"] = 19.0
    book[0].paid_projection_derivation_receipt = _engine_receipt(catalog, book)
    with pytest.raises(ValueError, match="mix projection transformations"):
        validate_paid_classic_book_v3(
            book, expected_entries=2, catalog=catalog
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda body: body["seed_pairs"][0].update(role_seed=999),
            "exact five production seeds",
        ),
        (
            lambda body: body.update(selection_world_count=49_999),
            "50,000 selection worlds",
        ),
        (
            lambda body: body["model_artifacts"]["R0"]["projection"]
            ["components"][0]["member_sha256"].__setitem__(0, "z" * 64),
            "model artifact is invalid",
        ),
        (_mutate_projection_model_version, "model version differs"),
        (
            lambda body: body["feature_snapshots"]["R0"]["role"].update(rows=0),
            "feature snapshot is invalid",
        ),
        (
            lambda body: body["feature_snapshots"]["R0"]["role"].update(
                sha256="f" * 64
            ),
            "mixes feature snapshots",
        ),
        (
            lambda body: body["notes_preferences"]["R0"]
            ["projection_component_notes"].update(changed=True),
            "component-notes state is invalid",
        ),
        (
            lambda body: body["construction_policy"].update(min_salary=0),
            "construction policy receipt is invalid",
        ),
        (
            lambda body: body["request_inputs"].update(draft_group_id=42),
            "request context differs",
        ),
        (
            lambda body: body["request_inputs"].pop("field_size"),
            "request schema differs",
        ),
        (
            lambda body: body["request_inputs"].update(
                requested_leverage_scale=0.5
            ),
            "effective request inputs differ",
        ),
        (
            lambda body: body["request_inputs"].update(
                allowed_player_ids_sha256="0" * 64
            ),
            "slate inputs differ",
        ),
        (
            lambda body: body["policy_environment"].update(N_BOOM="159"),
            "policy environment differs",
        ),
        (
            lambda body: body.update(locks=[101]),
            "locks/bans differ from the book",
        ),
        (
            lambda body: body.update(
                theses=[{"players": [101, 102], "min": 1}]
            ),
            "thesis differs from the book",
        ),
        (
            lambda body: body.update(
                selected_projection_objectives_sha256="0" * 64
            ),
            "selected objectives differ",
        ),
    ],
)
def test_engine_receipt_semantic_claims_fail_closed(mutation, message: str) -> None:
    catalog = _catalog()
    book = _book()
    receipt = _mutated_engine_receipt(_engine_receipt(catalog, book), mutation)
    for lineup in book:
        lineup.paid_projection_derivation_receipt = receipt
    with pytest.raises(ValueError, match=message):
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
