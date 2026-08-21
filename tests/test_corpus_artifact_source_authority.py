from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from itertools import combinations, product
import json

import numpy as np
import pytest

from nfl_dfs.research import corpus_artifact_source_authority as authority
from nfl_dfs.research import lr8_historical_arm as lr8
from nfl_dfs.research import lr8_later_period_source as later
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_parametric_batch import TASK_WORLD_SOURCE_ROLES


SNAPSHOT = "2026-08-21T12:00:00+00:00"
REGISTERED = "2026-08-21T11:00:00+00:00"


@dataclass(frozen=True)
class AuthorityFixture:
    artifact_raw: bytes
    source: dict[str, object]
    source_raw: bytes
    source_object: dict[str, object]
    registration: dict[str, object]
    registration_raw: bytes
    registration_object: dict[str, object]
    salary: dict[str, object]
    salary_raw: bytes
    salary_object: dict[str, object]
    completion_raw: bytes


def _players() -> tuple[rw.PlayerSpec, ...]:
    rows = (
        ("q-a", "QB", "A", "B", "g1"),
        ("q-c", "QB", "C", "D", "g2"),
        ("rb-a1", "RB", "A", "B", "g1"),
        ("rb-a2", "RB", "A", "B", "g1"),
        ("rb-b", "RB", "B", "A", "g1"),
        ("rb-c", "RB", "C", "D", "g2"),
        ("rb-d", "RB", "D", "C", "g2"),
        ("rb-e", "RB", "E", "F", "g3"),
        ("wr-a1", "WR", "A", "B", "g1"),
        ("wr-a2", "WR", "A", "B", "g1"),
        ("wr-b", "WR", "B", "A", "g1"),
        ("wr-c1", "WR", "C", "D", "g2"),
        ("wr-c2", "WR", "C", "D", "g2"),
        ("wr-d", "WR", "D", "C", "g2"),
        ("wr-e", "WR", "E", "F", "g3"),
        ("wr-f", "WR", "F", "E", "g3"),
        ("te-a", "TE", "A", "B", "g1"),
        ("te-b", "TE", "B", "A", "g1"),
        ("te-c", "TE", "C", "D", "g2"),
        ("te-d", "TE", "D", "C", "g2"),
        ("te-e", "TE", "E", "F", "g3"),
        ("dst-b", "DST", "B", "A", "g1"),
        ("dst-c", "DST", "C", "D", "g2"),
        ("dst-e", "DST", "E", "F", "g3"),
    )
    return tuple(sorted(
        (
            rw.PlayerSpec(player_id, position, team, opponent, game, 5_000)
            for player_id, position, team, opponent, game in rows
        ),
        key=lambda player: player.player_id,
    ))


def _legal_rosters(count: int = 88) -> tuple[tuple[str, ...], ...]:
    players = _players()
    positions = {
        position: [
            player.player_id
            for player in players
            if player.position == position
        ]
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    result: list[tuple[str, ...]] = []
    for qb, rbs, wrs, te, dst in product(
        positions["QB"],
        combinations(positions["RB"], 2),
        combinations(positions["WR"], 4),
        positions["TE"],
        positions["DST"],
    ):
        roster = tuple(sorted((qb, *rbs, *wrs, te, dst)))
        try:
            lr8.audit_dk_classic_identity(players, roster)
        except lr8.LR8Error:
            continue
        if roster not in result:
            result.append(roster)
        if len(result) == count:
            return tuple(result)
    raise AssertionError("test catalog lacks 88 legal incumbents")


def _npz_body(
    *,
    player_ids: tuple[str, ...] | None = None,
    draws_dtype: np.dtype = np.dtype(np.float32),
    worlds: int = rw.WORLDS_PER_BLOCK,
    outcome_member: bool = False,
) -> bytes:
    ids = player_ids or tuple(player.player_id for player in _players())
    arrays: dict[str, np.ndarray] = {
        "cand_ix": np.arange(1, dtype=np.int64),
        "totals": np.zeros((1, worlds), dtype=np.float32),
        "tail_line": np.asarray([194.0], dtype=np.float32),
        "player_ids": np.asarray(ids),
        "player_draws": np.zeros((len(ids), worlds), dtype=draws_dtype),
    }
    if outcome_member:
        arrays["actual_score"] = np.asarray([1.0], dtype=np.float32)
    buffer = BytesIO()
    np.savez_compressed(buffer, **arrays)
    return buffer.getvalue()


def _object(raw: bytes, name: str, generation: int) -> dict[str, object]:
    return {
        "uri": f"gs://corpus-source-test/{name}",
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _query_receipt(
    *,
    job_id: str,
    sql_sha256: str,
    parameters_sha256: str,
    minute: int,
) -> dict[str, object]:
    prefix = f"2026-08-21T12:{minute:02d}:"
    return {
        "job_id": job_id,
        "location": later.LOCATION,
        "sql_sha256": sql_sha256,
        "parameters_sha256": parameters_sha256,
        "created": f"{prefix}00+00:00",
        "started": f"{prefix}01+00:00",
        "ended": f"{prefix}02+00:00",
        "total_bytes_processed": 1,
        "cache_hit": False,
        "error_result": None,
    }


def _query_identity(
    *,
    job_id: str,
    table: str,
    sql_sha256: str,
    parameters_sha256: str,
    selected_columns: list[str],
) -> dict[str, object]:
    return {
        "job_id": job_id,
        "location": later.LOCATION,
        "table": table,
        "sql_sha256": sql_sha256,
        "parameters_sha256": parameters_sha256,
        "selected_columns": selected_columns,
        "realized_columns_selected": [],
    }


def _registration() -> dict[str, object]:
    run_id = "corpus-source-authority-test"
    source_parameters = later.canonical_sha256(
        later.source_parameter_payload(SNAPSHOT)
    )
    body: dict[str, object] = {
        "schema": authority.REGISTRATION_SCHEMA,
        "authority_id": "corpus-source-authority-test-v1",
        "registered_at": REGISTERED,
        "source_snapshot_at": SNAPSHOT,
        "source_run_id": run_id,
        "source_queries": {
            "r0_candidates": _query_identity(
                job_id=f"{run_id}-r0-candidates",
                table=later.CANDIDATE_TABLE,
                sql_sha256=later.CANDIDATE_SQL_SHA256,
                parameters_sha256=source_parameters,
                selected_columns=sorted(later.R0_CANDIDATE_FIELDS),
            ),
            "artifact_catalog": _query_identity(
                job_id=f"{run_id}-full-catalog",
                table=later.CATALOG_TABLE,
                sql_sha256=later.CATALOG_SQL_SHA256,
                parameters_sha256=source_parameters,
                selected_columns=sorted(later.CATALOG_FIELDS),
            ),
        },
        "salary_universe_query": _query_identity(
            job_id=f"{run_id}-salary-universe",
            table="nfl-predictions-503414.nfl_predictions.dk_salary_ids",
            sql_sha256="d" * 64,
            parameters_sha256="e" * 64,
            selected_columns=["id", "season", "week"],
        ),
        "universe_scope": authority.UNIVERSE_SCOPE,
        "uses_realized_outcomes": False,
    }
    body["registration_sha256"] = authority.canonical_sha256(body)
    return body


def _source_freeze(artifact_raw: bytes) -> dict[str, object]:
    players = _players()
    catalog = [
        {
            "id": player.player_id,
            "pos": player.position,
            "team": player.team,
            "opp": player.opponent,
            "game_id": player.game_id,
            "salary": player.salary,
        }
        for player in players
    ]
    incumbents = [list(roster) for roster in _legal_rosters()]
    artifact_sha = sha256(artifact_raw).hexdigest()
    artifact_size = len(artifact_raw)
    slates: list[dict[str, object]] = []
    artifact_ordinal = 0
    for season, week in later.EXPECTED_SLATE_KEYS:
        receipts = []
        for seed, block in enumerate(rw.WORLD_BLOCKS):
            receipts.append({
                "season": season,
                "week": week,
                "block": block,
                "panel_run_id": later.SOURCE_PANELS[seed],
                "candidate_rows": 1,
                "uri": (
                    "gs://corpus-source-test/worlds/"
                    f"{season}/w{week:02d}/{block}.npz"
                ),
                "generation": str(1_000 + artifact_ordinal),
                "sha256": artifact_sha,
                "bytes": artifact_size,
                "updated": "2026-08-20T00:00:00+00:00",
            })
            artifact_ordinal += 1
        slates.append({
            "season": season,
            "week": week,
            "slate_id": f"{season}-w{week:02d}",
            "catalog": catalog,
            "catalog_sha256": later.canonical_sha256(catalog),
            "incumbent_candidates": incumbents,
            "incumbent_candidates_sha256": later.canonical_sha256(incumbents),
            "artifact_receipts": receipts,
            "artifact_receipts_sha256": later.canonical_sha256(receipts),
        })
    run_id = "corpus-source-authority-test"
    parameter_sha = later.canonical_sha256(later.source_parameter_payload(SNAPSHOT))
    body: dict[str, object] = {
        "schema": later.SOURCE_FREEZE_VERSION,
        "protocol_id": lr8.PROTOCOL_ID,
        "runtime_identity": {
            "run_id": run_id,
            "code_sha": "b" * 40,
            "image": f"image@sha256:{'c' * 64}",
            "job": "corpus-source-authority-test-job",
        },
        "base_source_lock_sha256": later.BASE_SOURCE_SHA256,
        "base_source_lock_object": {
            "uri": later.BASE_SOURCE_URI,
            "generation": later.BASE_SOURCE_GENERATION,
            "sha256": later.BASE_SOURCE_SHA256,
            "bytes": later.BASE_SOURCE_BYTES,
        },
        "base_source_version": later.BASE_SOURCE_VERSION,
        "base_source_run_id": later.BASE_SOURCE_RUN_ID,
        "source_panels": list(later.SOURCE_PANELS),
        "canonical_incumbent_panel": later.R0_PANEL,
        "seasons": list(lr8.EVALUATION_SEASONS),
        "weeks": list(lr8.EVALUATION_WEEKS),
        "slate_count": len(later.EXPECTED_SLATE_KEYS),
        "artifact_count": later.EXPECTED_ARTIFACTS,
        "world_blocks": list(rw.WORLD_BLOCKS),
        "worlds_per_block": rw.WORLDS_PER_BLOCK,
        "source_query": {
            "candidate_table": later.CANDIDATE_TABLE,
            "catalog_table": later.CATALOG_TABLE,
            "source_snapshot_at": SNAPSHOT,
            "candidate_query": _query_receipt(
                job_id=f"{run_id}-r0-candidates",
                sql_sha256=later.CANDIDATE_SQL_SHA256,
                parameters_sha256=parameter_sha,
                minute=1,
            ),
            "catalog_query": _query_receipt(
                job_id=f"{run_id}-full-catalog",
                sql_sha256=later.CATALOG_SQL_SHA256,
                parameters_sha256=parameter_sha,
                minute=2,
            ),
            "selected_columns": {
                "candidates": sorted(later.R0_CANDIDATE_FIELDS),
                "catalog": sorted(later.CATALOG_FIELDS),
            },
            "realized_columns_selected": [],
        },
        "slates": slates,
        "repaired_2025_w1_r3_sha256": artifact_sha,
        "hard_constraints": "dk_nfl_classic_only",
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "production_inputs_used": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["freeze_sha256"] = later.canonical_sha256(body)
    return body


def _salary_diagnostic(
    registration: dict[str, object], source: dict[str, object],
) -> dict[str, object]:
    registered_query = registration["salary_universe_query"]
    slates = []
    for task_index, source_slate in enumerate(source["slates"]):
        ids = sorted([
            *(row["id"] for row in source_slate["catalog"]),
            f"salary-only-{source_slate['season']}-{source_slate['week']:02d}",
        ])
        slates.append({
            "task_index": task_index,
            "season": source_slate["season"],
            "week": source_slate["week"],
            "slate_id": source_slate["slate_id"],
            "salary_player_ids": ids,
            "salary_player_ids_sha256": authority.canonical_sha256(ids),
        })
    body: dict[str, object] = {
        "schema": authority.SALARY_DIAGNOSTIC_SCHEMA,
        "registration_sha256": registration["registration_sha256"],
        "universe_scope": authority.SALARY_DIAGNOSTIC_SCOPE,
        "query": {
            "source_snapshot_at": SNAPSHOT,
            "table": registered_query["table"],
            "query_receipt": _query_receipt(
                job_id=registered_query["job_id"],
                sql_sha256=registered_query["sql_sha256"],
                parameters_sha256=registered_query["parameters_sha256"],
                minute=3,
            ),
            "selected_columns": registered_query["selected_columns"],
            "realized_columns_selected": [],
        },
        "slate_count": len(slates),
        "slates": slates,
        "coverage_only": True,
        "world_draws_attached": False,
        "coverage_is_predeclared_query_relative": True,
        "query_result_independently_verified": False,
        "complete_dk_salary_coverage_claimed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    body["diagnostic_sha256"] = authority.canonical_sha256(body)
    return body


def _stream(
    source: dict[str, object],
    default_raw: bytes,
    *,
    replacements: dict[int, bytes] | None = None,
    counter: list[int] | None = None,
):
    artifact_ordinal = 0
    for task_index, slate in enumerate(source["slates"]):
        for role, receipt in zip(
            TASK_WORLD_SOURCE_ROLES,
            slate["artifact_receipts"],
            strict=True,
        ):
            if counter is not None:
                counter[0] += 1
            raw = (replacements or {}).get(artifact_ordinal, default_raw)
            yield authority.RetainedArtifactBody(
                task_index=task_index,
                role=role,
                identity={
                    key: receipt[key]
                    for key in ("uri", "generation", "sha256", "bytes")
                },
                raw=raw,
            )
            artifact_ordinal += 1


def _verify(
    fixture: AuthorityFixture,
    *,
    source: dict[str, object] | None = None,
    source_raw: bytes | None = None,
    source_object: dict[str, object] | None = None,
    registration_raw: bytes | None = None,
    registration_object: dict[str, object] | None = None,
    salary_raw: bytes | None = None,
    salary_object: dict[str, object] | None = None,
    artifact_bodies=None,
) -> bytes:
    selected_source = source or fixture.source
    return authority.verify_artifact_supported_source_authority(
        later_source_freeze_bytes=source_raw or fixture.source_raw,
        later_source_freeze_object=source_object or fixture.source_object,
        registration_bytes=registration_raw or fixture.registration_raw,
        registration_object=registration_object or fixture.registration_object,
        salary_diagnostic_bytes=salary_raw or fixture.salary_raw,
        salary_diagnostic_object=salary_object or fixture.salary_object,
        artifact_bodies=(
            artifact_bodies
            if artifact_bodies is not None
            else _stream(selected_source, fixture.artifact_raw)
        ),
    )


def _replace_first_artifact(
    fixture: AuthorityFixture, replacement: bytes,
) -> tuple[dict[str, object], bytes, dict[str, object]]:
    source = deepcopy(fixture.source)
    receipt = source["slates"][0]["artifact_receipts"][0]
    receipt["sha256"] = sha256(replacement).hexdigest()
    receipt["bytes"] = len(replacement)
    source["slates"][0]["artifact_receipts_sha256"] = later.canonical_sha256(
        source["slates"][0]["artifact_receipts"]
    )
    source.pop("freeze_sha256")
    source["freeze_sha256"] = later.canonical_sha256(source)
    raw = later.canonical_json(source)
    return source, raw, _object(raw, "later-source-poison.json", 902)


def _rehash_self_hashed(
    value: dict[str, object], hash_name: str,
) -> bytes:
    body = deepcopy(value)
    body.pop(hash_name, None)
    body[hash_name] = authority.canonical_sha256(body)
    return authority.canonical_json_bytes(body)


def _rehash_completion(value: dict[str, object]) -> bytes:
    body = deepcopy(value)
    body["task_manifest_sha256"] = authority.canonical_sha256(body["tasks"])
    body.pop("completion_sha256", None)
    body["completion_sha256"] = authority.canonical_sha256(body)
    return authority.canonical_json_bytes(body)


@pytest.fixture(scope="module")
def authority_fixture():
    artifact_raw = _npz_body()
    synthetic_repaired_sha = sha256(artifact_raw).hexdigest()
    original_repaired_sha = later.REPAIRED_R3_SHA256
    later.REPAIRED_R3_SHA256 = synthetic_repaired_sha
    try:
        registration = _registration()
        registration_raw = authority.canonical_json_bytes(registration)
        source = _source_freeze(artifact_raw)
        source_raw = later.canonical_json(source)
        salary = _salary_diagnostic(registration, source)
        salary_raw = authority.canonical_json_bytes(salary)
        provisional = AuthorityFixture(
            artifact_raw=artifact_raw,
            source=source,
            source_raw=source_raw,
            source_object=_object(source_raw, "later-source-freeze.json", 900),
            registration=registration,
            registration_raw=registration_raw,
            registration_object=_object(
                registration_raw, "source-registration.json", 899
            ),
            salary=salary,
            salary_raw=salary_raw,
            salary_object=_object(
                salary_raw, "salary-diagnostic.json", 901
            ),
            completion_raw=b"",
        )
        counter = [0]
        completion_raw = _verify(
            provisional,
            artifact_bodies=_stream(source, artifact_raw, counter=counter),
        )
        assert counter == [authority.EXPECTED_ARTIFACT_COUNT]
        yield AuthorityFixture(
            **{
                **provisional.__dict__,
                "completion_raw": completion_raw,
            }
        )
    finally:
        later.REPAIRED_R3_SHA256 = original_repaired_sha


def test_streamed_completion_proves_exact_artifact_supported_scope(
    authority_fixture,
):
    completion = authority.validate_completion_bytes(
        authority_fixture.completion_raw
    )
    assert completion["authority_scope"] == (
        "exact-artifact-supported-r0-r4-player-universe"
    )
    assert completion["task_count"] == 54
    assert completion["artifact_count"] == 270
    assert len(completion["tasks"]) == 54
    assert all(
        len(task["world_artifact_validations"]) == 5
        and all(
            validation["player_set_matches_catalog"] is True
            and validation["player_draws_dtype"] == "float32"
            and validation["world_count"] == 10_000
            for validation in task["world_artifact_validations"].values()
        )
        for task in completion["tasks"]
    )
    assert completion["artifact_supported_universe_complete"] is True
    assert completion["complete_dk_salary_universe_claimed"] is False
    assert completion["salary_coverage_is_predeclared_query_relative"] is True
    assert completion["salary_query_result_independently_verified"] is False
    assert completion["complete_dk_salary_coverage_claimed"] is False
    assert completion["salary_only_players_have_world_draws"] is False
    assert completion["salary_coverage_summary"][
        "salary_only_player_slate_count"
    ] == 54
    assert completion["outcome_columns_read"] == []
    assert completion["uses_realized_outcomes"] is False


def test_internal_hashes_are_distinct_from_retained_object_hashes(
    authority_fixture,
):
    completion = authority.validate_completion_bytes(
        authority_fixture.completion_raw
    )
    assert completion["registration_sha256"] != (
        completion["registration_object"]["sha256"]
    )
    assert completion["later_source_freeze_manifest_sha256"] != (
        completion["later_source_freeze_object"]["sha256"]
    )
    assert completion["salary_diagnostic_sha256"] != (
        completion["salary_diagnostic_object"]["sha256"]
    )


def test_stream_must_be_closed_exact_order_and_fail_fast(authority_fixture):
    counter = [0]

    def wrong_order():
        stream = _stream(
            authority_fixture.source,
            authority_fixture.artifact_raw,
            counter=counter,
        )
        first = next(stream)
        yield authority.RetainedArtifactBody(
            task_index=first.task_index,
            role="world_artifact_r1",
            identity=first.identity,
            raw=first.raw,
        )
        yield from stream

    with pytest.raises(authority.CorpusArtifactSourceAuthorityError, match="order"):
        _verify(authority_fixture, artifact_bodies=wrong_order())
    assert counter == [1]
    with pytest.raises(authority.CorpusArtifactSourceAuthorityError, match="ended"):
        _verify(authority_fixture, artifact_bodies=iter(()))
    with pytest.raises(authority.CorpusArtifactSourceAuthorityError, match="iterator"):
        _verify(authority_fixture, artifact_bodies=[])


def test_reopened_body_must_match_generation_pinned_identity(authority_fixture):
    first = next(_stream(authority_fixture.source, authority_fixture.artifact_raw))
    poison = authority.RetainedArtifactBody(
        task_index=first.task_index,
        role=first.role,
        identity={**first.identity, "generation": "999999"},
        raw=first.raw,
    )
    with pytest.raises(authority.CorpusArtifactSourceAuthorityError, match="identity"):
        _verify(authority_fixture, artifact_bodies=iter((poison,)))


@pytest.mark.parametrize(
    "replacement",
    [
        pytest.param(_npz_body(outcome_member=True), id="unknown-outcome-member"),
        pytest.param(_npz_body(draws_dtype=np.dtype(np.float64)), id="float64"),
        pytest.param(_npz_body(worlds=9_999), id="wrong-world-count"),
        pytest.param(
            _npz_body(
                player_ids=tuple(player.player_id for player in _players())[1:]
            ),
            id="catalog-player-missing",
        ),
    ],
)
def test_npz_schema_dtype_shape_and_catalog_player_set_fail_closed(
    authority_fixture, replacement,
):
    source, source_raw, source_object = _replace_first_artifact(
        authority_fixture, replacement
    )
    with pytest.raises(authority.CorpusArtifactSourceAuthorityError, match="NPZ|player"):
        _verify(
            authority_fixture,
            source=source,
            source_raw=source_raw,
            source_object=source_object,
            artifact_bodies=_stream(
                source,
                authority_fixture.artifact_raw,
                replacements={0: replacement},
            ),
        )


def test_predeclared_source_query_identity_cannot_drift(authority_fixture):
    source = deepcopy(authority_fixture.source)
    source["runtime_identity"]["run_id"] = "another-predeclared-run"
    source["source_query"]["candidate_query"]["job_id"] = (
        "another-predeclared-run-r0-candidates"
    )
    source["source_query"]["catalog_query"]["job_id"] = (
        "another-predeclared-run-full-catalog"
    )
    source.pop("freeze_sha256")
    source["freeze_sha256"] = later.canonical_sha256(source)
    source_raw = later.canonical_json(source)
    with pytest.raises(authority.CorpusArtifactSourceAuthorityError, match="predeclared"):
        _verify(
            authority_fixture,
            source=source,
            source_raw=source_raw,
            source_object=_object(source_raw, "drifted-source.json", 903),
        )


def test_salary_diagnostic_must_cover_every_artifact_player(authority_fixture):
    salary = deepcopy(authority_fixture.salary)
    first = salary["slates"][0]
    first["salary_player_ids"] = first["salary_player_ids"][1:]
    first["salary_player_ids_sha256"] = authority.canonical_sha256(
        first["salary_player_ids"]
    )
    salary_raw = _rehash_self_hashed(salary, "diagnostic_sha256")
    with pytest.raises(authority.CorpusArtifactSourceAuthorityError, match="absent"):
        _verify(
            authority_fixture,
            salary_raw=salary_raw,
            salary_object=_object(
                salary_raw, "incomplete-salary-diagnostic.json", 904
            ),
        )


def test_salary_diagnostic_cannot_claim_draws_or_outcomes(authority_fixture):
    for field, value in (
        ("world_draws_attached", True),
        ("uses_realized_outcomes", True),
        ("outcome_columns_read", ["actual_points"]),
        ("coverage_is_predeclared_query_relative", False),
        ("query_result_independently_verified", True),
        ("complete_dk_salary_coverage_claimed", True),
    ):
        salary = deepcopy(authority_fixture.salary)
        salary[field] = value
        salary_raw = _rehash_self_hashed(salary, "diagnostic_sha256")
        with pytest.raises(
            authority.CorpusArtifactSourceAuthorityError,
            match="license",
        ):
            _verify(
                authority_fixture,
                salary_raw=salary_raw,
                salary_object=_object(
                    salary_raw, f"salary-{field}.json", 905
                ),
            )


def test_completion_rejects_hash_conflation_and_task_binding_drift(
    authority_fixture,
):
    completion = json.loads(authority_fixture.completion_raw)
    conflated = deepcopy(completion)
    conflated["later_source_freeze_manifest_sha256"] = conflated[
        "later_source_freeze_object"
    ]["sha256"]
    with pytest.raises(authority.CorpusArtifactSourceAuthorityError, match="conflated"):
        authority.validate_completion_bytes(_rehash_completion(conflated))

    drifted = deepcopy(completion)
    task = drifted["tasks"][0]
    task["later_source_freeze_manifest_sha256"] = "f" * 64
    task.pop("task_source_authority_sha256")
    task["task_source_authority_sha256"] = authority.canonical_sha256(task)
    with pytest.raises(authority.CorpusArtifactSourceAuthorityError, match=r"task\[0\]"):
        authority.validate_completion_bytes(_rehash_completion(drifted))


def test_completion_rejects_bool_as_task_integer(authority_fixture):
    completion = json.loads(authority_fixture.completion_raw)
    task = completion["tasks"][1]
    task["task_index"] = True
    task.pop("task_source_authority_sha256")
    task["task_source_authority_sha256"] = authority.canonical_sha256(task)
    with pytest.raises(authority.CorpusArtifactSourceAuthorityError, match=r"task\[1\]"):
        authority.validate_completion_bytes(_rehash_completion(completion))


def test_completion_requires_canonical_self_hashed_bytes(authority_fixture):
    noncanonical = json.dumps(
        json.loads(authority_fixture.completion_raw), indent=2
    ).encode("utf-8")
    with pytest.raises(authority.CorpusArtifactSourceAuthorityError, match="canonical"):
        authority.validate_completion_bytes(noncanonical)
