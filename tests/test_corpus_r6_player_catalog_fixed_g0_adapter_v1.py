from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import inspect
from itertools import combinations, islice
from pathlib import Path
import subprocess
from typing import Mapping

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog


def _hash(value: object) -> str:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        raw = value.encode("utf-8")
    else:
        raw = batch.canonical_json_bytes(value)
    return sha256(raw).hexdigest()


def _with_hash(
    body: Mapping[str, object], field: str, *, transport: bool = False,
) -> dict[str, object]:
    retained = deepcopy(dict(body))
    raw = batch.canonical_json_bytes(retained) + (b"\n" if transport else b"")
    retained[field] = sha256(raw).hexdigest()
    return retained


def _file_binding(path: str, raw: bytes) -> dict[str, object]:
    return {
        "relative_path": path,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _opaque(label: str, ordinal: int) -> dict[str, object]:
    raw = f"opaque:{label}:{ordinal}".encode("utf-8")
    return {
        "uri": f"gs://fixture-authority/{label}/{ordinal:04d}.json",
        "generation": str(1_000_000 + ordinal),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _fixture_world_receipts(
    source_artifacts: list[list[Mapping[str, object]]], source_ordinal: int,
) -> dict[str, dict[str, object]]:
    return {
        role: {
            key: source_artifacts[source_ordinal][block_ordinal][key]
            for key in ("uri", "generation", "sha256", "bytes")
        }
        for block_ordinal, role in enumerate(batch.TASK_WORLD_SOURCE_ROLES)
    }


class FakeGenerationStore:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.identities: dict[tuple[str, str], dict[str, object]] = {}
        self.latest: dict[str, str] = {}
        self.reload_calls: list[tuple[str, str]] = []
        self.download_calls: list[tuple[str, str]] = []
        self.resolve_calls: list[str] = []
        self.create_calls: list[tuple[str, bytes, int]] = []
        self.next_generation = 9_000_000
        self.reload_override: Mapping[str, object] | None = None
        self.download_override: bytes | None = None
        self.race_body: bytes | None = None
        self.fail_create_number: int | None = None
        self._failed_once = False

    def seed_raw(
        self, uri: str, raw: bytes, *, generation: str | None = None,
    ) -> dict[str, object]:
        retained_generation = generation or str(self.next_generation)
        self.next_generation += 1
        identity = {
            "uri": uri,
            "generation": retained_generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        key = (uri, retained_generation)
        self.objects[key] = raw
        self.identities[key] = identity
        self.latest[uri] = retained_generation
        return identity

    def seed_json(
        self,
        uri: str,
        body: Mapping[str, object],
        *,
        transport: bool = False,
        generation: str | None = None,
    ) -> dict[str, object]:
        raw = batch.canonical_json_bytes(body) + (b"\n" if transport else b"")
        return self.seed_raw(uri, raw, generation=generation)

    def reload_generation(self, uri: str, generation: str) -> Mapping[str, object]:
        self.reload_calls.append((uri, generation))
        if self.reload_override is not None:
            return self.reload_override
        try:
            return dict(self.identities[(uri, generation)])
        except KeyError as exc:
            raise adapter.ObjectNotFoundV1Error((uri, generation)) from exc

    def download_generation(self, uri: str, generation: str) -> bytes:
        self.download_calls.append((uri, generation))
        if self.download_override is not None:
            return self.download_override
        try:
            return self.objects[(uri, generation)]
        except KeyError as exc:
            raise adapter.ObjectNotFoundV1Error((uri, generation)) from exc

    def resolve_current(self, uri: str) -> Mapping[str, object]:
        self.resolve_calls.append(uri)
        try:
            generation = self.latest[uri]
        except KeyError as exc:
            raise adapter.ObjectNotFoundV1Error(uri) from exc
        return dict(self.identities[(uri, generation)])

    def create_if_absent(
        self, uri: str, raw: bytes, precondition: int,
    ) -> Mapping[str, object]:
        self.create_calls.append((uri, raw, precondition))
        if (
            self.fail_create_number is not None
            and len(self.create_calls) == self.fail_create_number
            and not self._failed_once
        ):
            self._failed_once = True
            raise RuntimeError("injected one-time create failure")
        if self.race_body is not None:
            body = self.race_body
            self.race_body = None
            self.seed_raw(uri, body)
            raise adapter.ObjectAlreadyExistsV1Error(uri)
        if uri in self.latest:
            raise adapter.ObjectAlreadyExistsV1Error(uri)
        return self.seed_raw(uri, raw)

    def transport(self) -> adapter.GenerationTransportV1:
        return adapter.GenerationTransportV1(
            reload_generation=self.reload_generation,
            download_generation=self.download_generation,
            resolve_current=self.resolve_current,
            create_if_absent=self.create_if_absent,
        )


class _ProductionNotFound(Exception):
    pass


class _ProductionPreconditionFailed(Exception):
    pass


class _ProductionGCSClient:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str, str], bytes] = {}
        self.latest: dict[tuple[str, str], str] = {}
        self.next_generation = 1_000
        self.reload_calls: list[tuple[str, str | None, object]] = []
        self.download_calls: list[tuple[str, str | None, object]] = []
        self.upload_preconditions: list[int] = []
        self.race_body: bytes | None = None

    def bucket(self, name: str) -> "_ProductionBucket":
        return _ProductionBucket(self, name)

    def seed(
        self, uri: str, raw: bytes, *, generation: str | None = None
    ) -> dict[str, object]:
        bucket, name = adapter._split_gcs_uri_v1(uri)
        retained = generation or str(self.next_generation)
        self.next_generation += 1
        self.objects[(bucket, name, retained)] = raw
        self.latest[(bucket, name)] = retained
        return {
            "uri": uri,
            "generation": retained,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }


class _ProductionBucket:
    def __init__(self, client: _ProductionGCSClient, name: str) -> None:
        self.client = client
        self.name = name

    def blob(
        self, name: str, generation: int | None = None
    ) -> "_ProductionBlob":
        return _ProductionBlob(
            self.client,
            self.name,
            name,
            None if generation is None else str(generation),
        )


class _ProductionBlob:
    def __init__(
        self,
        client: _ProductionGCSClient,
        bucket: str,
        name: str,
        requested_generation: str | None,
    ) -> None:
        self.client = client
        self.bucket = bucket
        self.name = name
        self.requested_generation = requested_generation
        self.generation: str | None = requested_generation

    def reload(self, **_kwargs) -> None:
        self.client.reload_calls.append((
            f"gs://{self.bucket}/{self.name}",
            self.requested_generation,
            _kwargs.get("if_generation_match"),
        ))
        generation = self.requested_generation or self.client.latest.get(
            (self.bucket, self.name)
        )
        if generation is None or (
            self.bucket, self.name, generation
        ) not in self.client.objects:
            raise _ProductionNotFound(self.name)
        self.generation = generation

    def download_as_bytes(self, **_kwargs) -> bytes:
        self.client.download_calls.append((
            f"gs://{self.bucket}/{self.name}",
            self.requested_generation or self.generation,
            _kwargs.get("if_generation_match"),
        ))
        generation = self.requested_generation or self.generation
        if generation is None:
            raise _ProductionNotFound(self.name)
        try:
            return self.client.objects[(self.bucket, self.name, generation)]
        except KeyError as exc:
            raise _ProductionNotFound(self.name) from exc

    def upload_from_string(
        self, raw: bytes, *, if_generation_match: int, **_kwargs
    ) -> None:
        self.client.upload_preconditions.append(if_generation_match)
        if self.client.race_body is not None:
            race = self.client.race_body
            self.client.race_body = None
            uri = f"gs://{self.bucket}/{self.name}"
            self.client.seed(uri, race)
            raise _ProductionPreconditionFailed(self.name)
        if (self.bucket, self.name) in self.client.latest:
            raise _ProductionPreconditionFailed(self.name)
        generation = str(self.client.next_generation)
        self.client.next_generation += 1
        self.client.objects[(self.bucket, self.name, generation)] = raw
        self.client.latest[(self.bucket, self.name)] = generation
        self.generation = generation


def _production_gcs_backend(
    client: _ProductionGCSClient,
) -> adapter.GCSGenerationBackendV1:
    return adapter.GCSGenerationBackendV1(
        client,
        not_found_error=_ProductionNotFound,
        precondition_failed_error=_ProductionPreconditionFailed,
    )


def test_production_gcs_backend_404_and_generation_pinned_replay() -> None:
    client = _ProductionGCSClient()
    backend = _production_gcs_backend(client)
    uri = "gs://fixture-production/exact/object.json"
    assert not hasattr(backend, "list")
    assert not hasattr(backend, "list_blobs")
    with pytest.raises(adapter.ObjectNotFoundV1Error):
        backend.resolve_current(uri)
    assert client.reload_calls == [(uri, None, None)]

    identity = client.seed(uri, b"exact-generation", generation="17")
    assert adapter.read_generation_exact_v1(
        identity, transport=backend.transport()
    ) == b"exact-generation"
    assert client.reload_calls[-1] == (uri, "17", 17)
    assert client.download_calls[-1] == (uri, "17", 17)

    missing = {**identity, "generation": "18"}
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.read_generation_exact_v1(
            missing, transport=backend.transport()
        )


def test_production_gcs_backend_generation_match_zero_and_412() -> None:
    client = _ProductionGCSClient()
    backend = _production_gcs_backend(client)
    uri = "gs://fixture-production/exact/create.json"
    created = backend.create_if_absent(uri, b"created", 0)
    assert client.upload_preconditions == [0]
    assert backend.download_generation(
        str(created["uri"]), str(created["generation"])
    ) == b"created"

    with pytest.raises(adapter.ObjectAlreadyExistsV1Error):
        backend.create_if_absent(uri, b"different", 0)
    assert client.upload_preconditions == [0, 0]
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        backend.create_if_absent(
            "gs://fixture-production/exact/invalid.json", b"body", 1
        )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        backend.create_if_absent(
            "gs://fixture-production/exact/bool.json", b"body", False
        )
    assert client.upload_preconditions == [0, 0]


@pytest.mark.parametrize("winner,accepted", [(b"body", True), (b"other", False)])
def test_production_gcs_412_race_reopens_exact_winner(
    winner: bytes, accepted: bool,
) -> None:
    client = _ProductionGCSClient()
    client.race_body = winner
    backend = _production_gcs_backend(client)
    uri = "gs://fixture-production/exact/race.json"
    if accepted:
        identity = adapter.publish_create_once_resumable_v1(
            uri, b"body", transport=backend.transport()
        )
        assert backend.download_generation(
            str(identity["uri"]), str(identity["generation"])
        ) == b"body"
    else:
        with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
            adapter.publish_create_once_resumable_v1(
                uri, b"body", transport=backend.transport()
            )
    assert client.upload_preconditions == [0]


def test_subprocess_git_repository_exact_current_clean_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls: list[tuple[list[str], str]] = []
    head = "a" * 40
    tracked = b"reviewed tracked bytes\n"
    responses = {
        ("git", "rev-parse", "--show-toplevel"): (
            str(tmp_path).encode("utf-8") + b"\n"
        ),
        ("git", "status", "--porcelain=v1", "--untracked-files=all"): b"",
        ("git", "rev-parse", "--verify", "HEAD"): head.encode("ascii") + b"\n",
        ("git", "cat-file", "-p", f"{head}:reports/review.json"): tracked,
    }

    def fake_run(argv, **kwargs):
        retained = list(argv)
        calls.append((retained, kwargs["cwd"]))
        key = tuple(retained)
        if key not in responses:
            return subprocess.CompletedProcess(
                retained, returncode=1, stdout=b"", stderr=b"unexpected"
            )
        return subprocess.CompletedProcess(
            retained, returncode=0, stdout=responses[key], stderr=b""
        )

    monkeypatch.setattr(adapter.subprocess, "run", fake_run)
    repository = adapter.SubprocessGitRepositoryV1(tmp_path)
    assert repository.require_current_clean_head() == head
    assert repository.read_tracked(head, "reports/review.json") == tracked
    assert [row[0] for row in calls] == [list(key) for key in responses]
    assert {row[1] for row in calls} == {str(tmp_path.resolve())}


def test_subprocess_git_repository_rejects_dirty_before_head(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        retained = list(argv)
        calls.append(retained)
        if retained[1:] == ["rev-parse", "--show-toplevel"]:
            stdout = str(tmp_path).encode("utf-8") + b"\n"
        elif retained[1:] == [
            "status", "--porcelain=v1", "--untracked-files=all",
        ]:
            stdout = b"?? unreviewed-file\n"
        else:
            raise AssertionError(f"unexpected post-dirty Git call: {retained}")
        return subprocess.CompletedProcess(
            retained, returncode=0, stdout=stdout, stderr=b""
        )

    monkeypatch.setattr(adapter.subprocess, "run", fake_run)
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.SubprocessGitRepositoryV1(tmp_path).require_current_clean_head()
    assert len(calls) == 2


@dataclass
class FixtureGraph:
    store: FakeGenerationStore
    pins: adapter.ReplayPinsV1
    review: adapter.AdapterReviewBindingV1
    tracked: dict[tuple[str, str], bytes]
    bodies: dict[str, object]

    def read_tracked(self, commit: str, path: str) -> bytes:
        return self.tracked[(commit, path)]


def _fixture_graph() -> FixtureGraph:
    store = FakeGenerationStore()
    bodies: dict[str, object] = {}
    structural: list[list[dict[str, object]]] = []
    source_artifacts: list[list[dict[str, object]]] = []
    source_slates: list[dict[str, object]] = []
    for source_ordinal in range(catalog.TASK_COUNT):
        slate = catalog.expected_slate_for_source_task(source_ordinal)
        position_order = ("QB", "RB", "WR", "TE", "DST")
        players = [
            {
                "id": f"{source_ordinal:02d}-p{player_ordinal:02d}",
                "pos": position_order[player_ordinal % len(position_order)],
                "team": "AAA" if player_ordinal < 10 else "BBB",
                "opp": "BBB" if player_ordinal < 10 else "AAA",
                "game_id": f"game-{source_ordinal:02d}",
                "salary": 3000 + player_ordinal * 100,
            }
            for player_ordinal in range(20)
        ]
        structural.append(players)
        artifacts: list[dict[str, object]] = []
        for block_ordinal, block in enumerate(("R0", "R1", "R2", "R3", "R4")):
            identity = _opaque(
                f"world-{source_ordinal:02d}-{block.lower()}",
                20_000 + source_ordinal * 5 + block_ordinal,
            )
            if source_ordinal == 36 and block_ordinal == 3:
                identity["sha256"] = (
                    "7eaef50c890150f6cdc329e80e4d68f08b4a8d2aac402fa5a51ba9ce4f860805"
                )
            artifacts.append({
                "season": slate["season"],
                "week": slate["week"],
                "block": block,
                "panel_run_id": (
                    f"20260815-atlas-money-worlds-r{block_ordinal}-v1"
                ),
                "candidate_rows": 10,
                **identity,
                "updated": "2026-08-21T00:00:00Z",
            })
        source_artifacts.append(artifacts)
        incumbents = [
            [players[index]["id"] for index in roster]
            for roster in islice(combinations(range(len(players)), 9), 88)
        ]
        source_slates.append({
            **slate,
            "catalog": players,
            "catalog_sha256": _hash(players),
            "incumbent_candidates": incumbents,
            "incumbent_candidates_sha256": _hash(incumbents),
            "artifact_receipts": artifacts,
            "artifact_receipts_sha256": _hash(artifacts),
        })

    query_receipt = {
        "job_id": "fixture-job",
        "location": "US",
        "sql_sha256": _hash("fixture sql"),
        "parameters_sha256": _hash("fixture parameters"),
        "created": "2026-08-21T00:00:00Z",
        "started": "2026-08-21T00:00:01Z",
        "ended": "2026-08-21T00:00:02Z",
        "total_bytes_processed": 1,
        "cache_hit": False,
        "error_result": None,
    }
    base_identity = {
        "uri": (
            "gs://nfl-predictions-503414-raw/research/"
            "production-law-dependence-runs/"
            "20260817-production-law-dependence-source-lock-v1/"
            "source-lock.json"
        ),
        "generation": "1786950155692968",
        "sha256": (
            "7ede34b6d13dacb6645836a85ff35dc82f757331423e49f84537d710c500346c"
        ),
        "bytes": 1_341_911,
    }
    later_body = {
        "schema": "lr8-later-period-source-freeze-v1",
        "protocol_id": "20260820-lr8-historical-residual-columns-v1",
        "runtime_identity": {
            "run_id": "fixture-run",
            "code_sha": "fixture-code",
            "image": "fixture-image",
            "job": "fixture-job",
        },
        "base_source_lock_sha256": base_identity["sha256"],
        "base_source_lock_object": base_identity,
        "base_source_version": "production-law-dependence-source-lock-v1",
        "base_source_run_id": "20260817-production-law-dependence-source-lock-v1",
        "source_panels": [
            f"20260815-atlas-money-worlds-r{index}-v1" for index in range(5)
        ],
        "canonical_incumbent_panel": "20260815-atlas-money-worlds-r0-v1",
        "seasons": [2023, 2024, 2025],
        "weeks": list(range(1, 19)),
        "slate_count": catalog.TASK_COUNT,
        "artifact_count": catalog.TASK_COUNT * 5,
        "world_blocks": ["R0", "R1", "R2", "R3", "R4"],
        "worlds_per_block": 10_000,
        "source_query": {
            "candidate_table": (
                "nfl-predictions-503414.nfl_predictions."
                "replay_candidates_staging"
            ),
            "catalog_table": (
                "nfl-predictions-503414.nfl_predictions.slate_player_features"
            ),
            "source_snapshot_at": "2026-08-21T23:53:22Z",
            "candidate_query": {
                **query_receipt, "job_id": "fixture-run-r0-candidates",
            },
            "catalog_query": {
                **query_receipt, "job_id": "fixture-run-full-catalog",
            },
            "selected_columns": {
                "candidates": sorted({
                    "panel_run_id", "season", "week", "cand_ix", "players",
                    "score_artifact_uri", "score_artifact_sha256",
                }),
                "catalog": sorted({
                    "season", "week", *catalog.PLAYER_FIELD_ORDER,
                }),
            },
            "realized_columns_selected": [],
        },
        "slates": source_slates,
        "repaired_2025_w1_r3_sha256": (
            "7eaef50c890150f6cdc329e80e4d68f08b4a8d2aac402fa5a51ba9ce4f860805"
        ),
        "hard_constraints": "dk_nfl_classic_only",
        **{field: False for field in adapter._LATER_SOURCE_FALSE_FIELDS},
    }
    later_body = _with_hash(later_body, "freeze_sha256")
    later_identity = store.seed_json(
        "gs://fixture-source/fixed/later-source-freeze.json", later_body
    )
    bodies["later_source"] = later_body

    registration_identity = _opaque("registration", 41_000)
    salary_identity = _opaque("salary-diagnostic", 41_001)
    completion_tasks: list[dict[str, object]] = []
    for source_ordinal, (slate, players, artifacts) in enumerate(
        zip(source_slates, structural, source_artifacts, strict=True)
    ):
        player_ids_sha = _hash([player["id"] for player in players])
        receipts = {
            role: {
                key: artifacts[role_ordinal][key]
                for key in ("uri", "generation", "sha256", "bytes")
            }
            for role_ordinal, role in enumerate(adapter._WORLD_ROLES)
        }
        validations = {
            role: {
                "artifact_ordinal": source_ordinal * 5 + role_ordinal,
                "role": role,
                "object": receipts[role],
                "candidate_rows": artifacts[role_ordinal]["candidate_rows"],
                "player_count": len(players),
                "ordered_player_ids_sha256": player_ids_sha,
                "player_set_sha256": player_ids_sha,
                "npz_fields": sorted({
                    "cand_ix", "totals", "tail_line", "player_ids",
                    "player_draws",
                }),
                "player_draws_dtype": "float32",
                "player_draws_shape": [len(players), 10_000],
                "world_count": 10_000,
                "player_set_matches_catalog": True,
                "uses_realized_outcomes": False,
            }
            for role_ordinal, role in enumerate(adapter._WORLD_ROLES)
        }
        coverage = {
            "salary_player_count": len(players),
            "salary_player_ids_sha256": player_ids_sha,
            "artifact_supported_player_count": len(players),
            "artifact_supported_player_ids_sha256": player_ids_sha,
            "artifact_supported_in_salary_count": len(players),
            "salary_only_player_count": 0,
            "salary_only_player_ids_sha256": _hash([]),
            "artifact_only_player_count": 0,
            "artifact_only_player_ids_sha256": _hash([]),
            "artifact_equals_salary_diagnostic": True,
            "salary_only_players_have_world_draws": False,
            "coverage_is_predeclared_query_relative": True,
            "query_result_independently_verified": False,
            "complete_dk_salary_coverage_claimed": False,
        }
        task_body = {
            "task_index": source_ordinal,
            "season": slate["season"],
            "week": slate["week"],
            "slate_id": slate["slate_id"],
            "universe_scope": catalog.UNIVERSE_SCOPE,
            "registration_sha256": _hash("registration internal"),
            "later_source_freeze_manifest_sha256": later_body["freeze_sha256"],
            "salary_diagnostic_sha256": _hash("salary internal"),
            "catalog_sha256": slate["catalog_sha256"],
            "catalog_player_count": len(players),
            "catalog_player_ids_sha256": player_ids_sha,
            "incumbent_candidates_sha256": slate[
                "incumbent_candidates_sha256"
            ],
            "world_artifact_receipts": receipts,
            "world_artifact_receipt_set_sha256": _hash(receipts),
            "world_artifact_validations": validations,
            "world_artifact_validation_set_sha256": _hash(validations),
            "salary_coverage": coverage,
            "complete_dk_salary_universe_claimed": False,
        }
        completion_tasks.append(
            _with_hash(task_body, "task_source_authority_sha256")
        )
    player_slate_count = sum(len(players) for players in structural)
    receipt_manifest = [
        {
            "artifact_ordinal": source_ordinal * 5 + role_ordinal,
            "task_index": source_ordinal,
            "role": role,
            "object": completion_tasks[source_ordinal][
                "world_artifact_receipts"
            ][role],
        }
        for source_ordinal in range(catalog.TASK_COUNT)
        for role_ordinal, role in enumerate(adapter._WORLD_ROLES)
    ]
    validation_manifest = [
        completion_tasks[source_ordinal]["world_artifact_validations"][role]
        for source_ordinal in range(catalog.TASK_COUNT)
        for role in adapter._WORLD_ROLES
    ]
    completion_body = {
        "schema": "corpus-artifact-supported-source-authority-completion/v1",
        "authority_scope": catalog.UNIVERSE_SCOPE,
        "registration_object": registration_identity,
        "registration_sha256": _hash("registration internal"),
        "later_source_freeze_object": later_identity,
        "later_source_freeze_manifest_sha256": later_body["freeze_sha256"],
        "salary_diagnostic_object": salary_identity,
        "salary_diagnostic_sha256": _hash("salary internal"),
        "task_count": catalog.TASK_COUNT,
        "world_blocks": ["R0", "R1", "R2", "R3", "R4"],
        "worlds_per_block": 10_000,
        "artifact_count": catalog.TASK_COUNT * 5,
        "artifact_stream_order": "task-index-major_then-r0-r1-r2-r3-r4",
        "artifact_receipt_manifest_sha256": _hash(receipt_manifest),
        "artifact_validation_manifest_sha256": _hash(validation_manifest),
        "tasks": completion_tasks,
        "task_manifest_sha256": _hash(completion_tasks),
        "salary_coverage_summary": {
            "task_count": catalog.TASK_COUNT,
            "exact_match_task_count": catalog.TASK_COUNT,
            "artifact_player_slate_count": player_slate_count,
            "salary_player_slate_count": player_slate_count,
            "salary_only_player_slate_count": 0,
            "coverage_numerator_artifact_player_slates": player_slate_count,
            "coverage_denominator_salary_player_slates": player_slate_count,
            "diagnostic_required": True,
            "diagnostic_grants_world_draws": False,
            "coverage_is_predeclared_query_relative": True,
            "query_result_independently_verified": False,
            "complete_dk_salary_coverage_claimed": False,
        },
        "artifact_supported_universe_complete": True,
        "complete_dk_salary_universe_claimed": False,
        "salary_coverage_is_predeclared_query_relative": True,
        "salary_query_result_independently_verified": False,
        "salary_only_players_have_world_draws": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in adapter._SOURCE_COMPLETION_FALSE_FIELDS},
    }
    completion_body = _with_hash(completion_body, "completion_sha256")
    completion_identity = store.seed_json(
        "gs://fixture-source/fixed/artifact-source-authority-completion.json",
        completion_body,
    )
    bodies["source_completion"] = completion_body

    members: list[dict[str, object]] = []
    for source_ordinal, task in enumerate(completion_tasks):
        lane = catalog.expected_lane_for_source_task(source_ordinal)
        slate = catalog.expected_slate_for_source_task(source_ordinal)
        members.append({
            "slate_id": slate["slate_id"],
            **lane,
            "source_task_ordinal": source_ordinal,
            "source_task_authority_sha256": task[
                "task_source_authority_sha256"
            ],
            "task_acceptance_identity": _opaque(
                "task-acceptance", 50_000 + source_ordinal
            ),
            "carrier_identity": _opaque("task-carrier", 51_000 + source_ordinal),
            "arms": [
                {
                    "arm_ordinal": arm_ordinal,
                    "parameter_set_id": parameter_set_id,
                    "result_identity": _opaque(
                        "arm-result",
                        60_000 + source_ordinal * len(batch.PARAMETER_SET_ORDER)
                        + arm_ordinal,
                    ),
                }
                for arm_ordinal, parameter_set_id in enumerate(
                    batch.PARAMETER_SET_ORDER
                )
            ],
        })

    completion_identities: list[dict[str, object]] = []
    completion_bodies: list[dict[str, object]] = []
    for lane_ordinal, (start, count) in enumerate(((0, 28), (28, 26))):
        lane_members = members[start:start + count]
        task_results = [
            {
                "task_index": task_ordinal,
                "task_sha256": _hash(f"task {source_ordinal}"),
                "artifact_source_authority_task_sha256": member[
                    "source_task_authority_sha256"
                ],
                "world_artifact_receipt_set_sha256": _hash(
                    _fixture_world_receipts(source_artifacts, source_ordinal)
                ),
                "task_result_sha256": _hash(f"carrier {source_ordinal}"),
                "task_result_object": member["carrier_identity"],
            }
            for task_ordinal, (source_ordinal, member) in enumerate(
                zip(range(start, start + count), lane_members, strict=True)
            )
        ]
        body = {
            "schema_version": "corpus-parametric-batch-completion-v2",
            "publication_mode": "create_once",
            "batch_manifest_identity": _opaque(
                f"lane-{lane_ordinal}-manifest", 70_000 + lane_ordinal
            ),
            "batch_id": f"fixture-lane-{lane_ordinal}",
            "batch_manifest_sha256": _hash(f"manifest {lane_ordinal}"),
            "parameter_schema_sha256": _hash("parameter schema"),
            "common_law_sha256": _hash("common law"),
            "later_source_freeze_manifest_sha256": later_body["freeze_sha256"],
            "artifact_source_authority_completion": completion_identity,
            "artifact_source_authority_completion_sha256": completion_body[
                "completion_sha256"
            ],
            "effective_policy_classified_input_projection_sha256": _hash(
                "policy projection"
            ),
            "coverage": {
                "task_count": count,
                "parameter_set_count": len(batch.PARAMETER_SET_ORDER),
                "matrix_cell_count": count * len(batch.PARAMETER_SET_ORDER),
                "complete": True,
            },
            "task_results": task_results,
        }
        body = _with_hash(body, "batch_completion_sha256")
        identity = store.seed_json(
            f"gs://fixture-parametric/lane-{lane_ordinal}/batch-completion.json",
            body,
        )
        completion_bodies.append(body)
        completion_identities.append(identity)
    bodies["lane_completions"] = completion_bodies

    terminal_identities: list[dict[str, object]] = []
    terminal_bodies: list[dict[str, object]] = []
    for lane_ordinal, (start, count) in enumerate(((0, 28), (28, 26))):
        lane_members = members[start:start + count]
        required = [
            completion_identities[lane_ordinal],
            *(member["task_acceptance_identity"] for member in lane_members),
            *(member["carrier_identity"] for member in lane_members),
        ]
        inventory = sorted(
            [
                {
                    "uri": identity["uri"],
                    "generation": identity["generation"],
                    "bytes": identity["bytes"],
                }
                for identity in required
            ],
            key=lambda row: (row["uri"], row["generation"]),
        )
        body = {
            "schema_version": "corpus-parametric-batch-acceptance/v1",
            "accepted_at_utc": "2026-08-23T00:00:00Z",
            "transport_contract": _opaque("transport-contract", 80_000),
            "retrieval_task0_prerequisite_identity": _opaque(
                "retrieval-prerequisite", 80_001
            ),
            "batch_mode": (
                "lane-a-28-task" if lane_ordinal == 0 else "lane-b-26-task"
            ),
            "batch_completion": completion_identities[lane_ordinal],
            "task_acceptances": [
                member["task_acceptance_identity"] for member in lane_members
            ],
            "task_count": count,
            "parameter_set_count": len(batch.PARAMETER_SET_ORDER),
            "matrix_cell_count": count * len(batch.PARAMETER_SET_ORDER),
            "output_inventory_before_batch_acceptance": inventory,
            "output_inventory_before_batch_acceptance_sha256": sha256(
                batch.canonical_json_bytes(inventory) + b"\n"
            ).hexdigest(),
            "output_object_count_before_batch_acceptance": len(inventory),
            "complete": True,
            "accepted": True,
            "partial_result": False,
            "independent_verification_complete_for_every_task": True,
            **{field: False for field in adapter._LANE_TERMINAL_FALSE_FIELDS},
        }
        body = _with_hash(body, "batch_acceptance_sha256", transport=True)
        identity = store.seed_json(
            f"gs://fixture-parametric/lane-{lane_ordinal}/batch-acceptance.json",
            body,
            transport=True,
        )
        terminal_bodies.append(body)
        terminal_identities.append(identity)
    bodies["lane_terminals"] = terminal_bodies

    carrier_bodies: list[dict[str, object]] = []
    acceptance_bodies: list[dict[str, object]] = []
    for source_ordinal, member in enumerate(members):
        lane = catalog.expected_lane_for_source_task(source_ordinal)
        lane_ordinal = int(lane["lane_ordinal"])
        task_ordinal = int(lane["task_ordinal"])
        completion = completion_bodies[lane_ordinal]
        result_row = completion["task_results"][task_ordinal]
        worlds = _fixture_world_receipts(source_artifacts, source_ordinal)
        sources = {"later_source_freeze": later_identity}
        carrier = {
            "schema_version": batch.TASK_RESULT_SCHEMA,
            "publication_mode": "create_once",
            "batch_manifest_identity": completion["batch_manifest_identity"],
            "batch_id": completion["batch_id"],
            "batch_manifest_sha256": completion["batch_manifest_sha256"],
            "parameter_schema_sha256": completion["parameter_schema_sha256"],
            "common_law_sha256": completion["common_law_sha256"],
            "task_index": task_ordinal,
            "task_sha256": result_row["task_sha256"],
            "slate_id": catalog.expected_slate_for_source_task(source_ordinal)[
                "slate_id"
            ],
            "world_artifact_receipts": worlds,
            "world_artifact_receipt_set_sha256": _hash(worlds),
            "artifact_source_authority_task_sha256": member[
                "source_task_authority_sha256"
            ],
            "code_source": {"fixture": True},
            "immutable_image": {"fixture": True},
            "source_receipts": sources,
            "source_receipt_set_sha256": _hash(sources),
            "later_source_freeze_manifest_sha256": later_body["freeze_sha256"],
            "artifact_source_authority_completion": completion_identity,
            "artifact_source_authority_completion_sha256": completion_body[
                "completion_sha256"
            ],
            "effective_policy_inventory_identity": _opaque(
                "policy-inventory", 90_000 + source_ordinal
            ),
            "effective_policy_inventory_sha256": _hash("policy inventory"),
            "effective_policy_rule_universe_sha256": _hash("rule universe"),
            "effective_policy_inventory_source_set_sha256": _hash(
                "inventory sources"
            ),
            "effective_policy_classified_input_projection_sha256": completion[
                "effective_policy_classified_input_projection_sha256"
            ],
            "world_schedule": [],
            "world_seed": 100_000 + source_ordinal,
            "solver": {"fixture": True},
            "execution": {"fixture": True},
            "variant_results": [
                {
                    "ordinal": arm["arm_ordinal"],
                    "parameter_set_id": arm["parameter_set_id"],
                    "parameter_set_sha256": _hash(
                        f"parameter {source_ordinal} {arm['arm_ordinal']}"
                    ),
                    "effective_policy_receipt": _opaque(
                        "policy-receipt",
                        100_000 + source_ordinal * len(batch.PARAMETER_SET_ORDER)
                        + int(arm["arm_ordinal"]),
                    ),
                    "result_object": arm["result_identity"],
                }
                for arm in member["arms"]
            ],
        }
        carrier = _with_hash(carrier, "task_result_sha256")
        carrier_identity = store.seed_json(
            f"gs://fixture-parametric/tasks/{source_ordinal}/task-result.json",
            carrier,
        )
        terminal = terminal_bodies[lane_ordinal]
        acceptance = {
            "schema_version": "corpus-parametric-task-acceptance/v1",
            "accepted_at_utc": "2026-08-23T00:00:00Z",
            "transport_contract": terminal["transport_contract"],
            "retrieval_task0_prerequisite_identity": terminal[
                "retrieval_task0_prerequisite_identity"
            ],
            "task_index": task_ordinal,
            "task_sha256": result_row["task_sha256"],
            "producer_close": _opaque("producer-close", 110_000 + source_ordinal),
            "science_terminal": _opaque(
                "science-terminal", 120_000 + source_ordinal
            ),
            "task_result": carrier_identity,
            "verifier_worker_completion": _opaque(
                "verifier-completion", 130_000 + source_ordinal
            ),
            "independent_verification": _opaque(
                "independent-verification", 140_000 + source_ordinal
            ),
            "independent_verification_sha256": _hash(
                f"verification {source_ordinal}"
            ),
            "verifier_terminal_execution": {"fixture": True},
            "terminal_governance_census": {"fixture": True},
            "evidence_object_count": 140,
            "complete_evidence_receipt": True,
            "independent_verification_complete": True,
            "strict_verifier_terminal_success": True,
            "accepted": True,
            "partial_result": False,
            **{
                field: False
                for field in adapter._TASK_ACCEPTANCE_FALSE_FIELDS
            },
        }
        acceptance = _with_hash(
            acceptance, "task_acceptance_sha256", transport=True
        )
        acceptance_identity = store.seed_json(
            f"gs://fixture-parametric/tasks/{source_ordinal}/acceptance.json",
            acceptance,
            transport=True,
        )
        member["carrier_identity"] = carrier_identity
        member["task_acceptance_identity"] = acceptance_identity
        carrier_bodies.append(carrier)
        acceptance_bodies.append(acceptance)

    for lane_ordinal, (start, count) in enumerate(((0, 28), (28, 26))):
        lane_members = members[start:start + count]
        completion = deepcopy(completion_bodies[lane_ordinal])
        for task_ordinal, member in enumerate(lane_members):
            source_ordinal = start + task_ordinal
            completion["task_results"][task_ordinal]["task_result_object"] = (
                member["carrier_identity"]
            )
            completion["task_results"][task_ordinal]["task_result_sha256"] = (
                carrier_bodies[source_ordinal]["task_result_sha256"]
            )
        completion = _with_hash(
            {
                key: value
                for key, value in completion.items()
                if key != "batch_completion_sha256"
            },
            "batch_completion_sha256",
        )
        completion_identity_new = store.seed_json(
            f"gs://fixture-parametric/lane-{lane_ordinal}/batch-completion.json",
            completion,
        )
        completion_bodies[lane_ordinal] = completion
        completion_identities[lane_ordinal] = completion_identity_new

        terminal = deepcopy(terminal_bodies[lane_ordinal])
        terminal["batch_completion"] = completion_identity_new
        terminal["task_acceptances"] = [
            member["task_acceptance_identity"] for member in lane_members
        ]
        required = [
            completion_identity_new,
            *(member["task_acceptance_identity"] for member in lane_members),
            *(member["carrier_identity"] for member in lane_members),
        ]
        inventory = sorted(
            [
                {
                    "uri": identity["uri"],
                    "generation": identity["generation"],
                    "bytes": identity["bytes"],
                }
                for identity in required
            ],
            key=lambda row: (row["uri"], row["generation"]),
        )
        terminal["output_inventory_before_batch_acceptance"] = inventory
        terminal["output_inventory_before_batch_acceptance_sha256"] = sha256(
            batch.canonical_json_bytes(inventory) + b"\n"
        ).hexdigest()
        terminal["output_object_count_before_batch_acceptance"] = len(inventory)
        terminal = _with_hash(
            {
                key: value
                for key, value in terminal.items()
                if key != "batch_acceptance_sha256"
            },
            "batch_acceptance_sha256",
            transport=True,
        )
        terminal_identity_new = store.seed_json(
            f"gs://fixture-parametric/lane-{lane_ordinal}/batch-acceptance.json",
            terminal,
            transport=True,
        )
        terminal_bodies[lane_ordinal] = terminal
        terminal_identities[lane_ordinal] = terminal_identity_new
    bodies["lane_completions"] = completion_bodies
    bodies["lane_terminals"] = terminal_bodies
    bodies["task_acceptances"] = acceptance_bodies
    bodies["task_carriers"] = carrier_bodies

    panel_lanes: list[dict[str, object]] = []
    for lane_ordinal, (start, count) in enumerate(((0, 28), (28, 26))):
        lane_members = members[start:start + count]
        panel_lanes.append({
            "lane_ordinal": lane_ordinal,
            "lane_id": "v12a" if lane_ordinal == 0 else "v12b",
            "terminal_receipt_identity": terminal_identities[lane_ordinal],
            "batch_completion_identity": completion_identities[lane_ordinal],
            "batch_id": f"fixture-lane-{lane_ordinal}",
            "batch_mode": (
                "lane-a-28-task" if lane_ordinal == 0 else "lane-b-26-task"
            ),
            "artifact_source_authority_completion": completion_identity,
            "artifact_source_authority_completion_sha256": completion_body[
                "completion_sha256"
            ],
            "source_task_offset": start,
            "expected_task_count": count,
            "accepted_task_count": count,
            "accepted_task_ordinals": list(range(count)),
            "task_acceptance_identities_sha256": _hash([
                member["task_acceptance_identity"] for member in lane_members
            ]),
            "carrier_identities_sha256": _hash([
                member["carrier_identity"] for member in lane_members
            ]),
            "complete": True,
        })
    panel_id = f"v12:{_hash(terminal_identities)}"
    panel_body = {
        "schema_version": "foundry-v12-combined-panel-index/v1",
        "publication_mode": "create_once",
        "panel_id": panel_id,
        "artifact_source_authority_completion": completion_identity,
        "artifact_source_authority_completion_sha256": completion_body[
            "completion_sha256"
        ],
        "lane_count": 2,
        "lanes": panel_lanes,
        "accepted_slate_count": catalog.TASK_COUNT,
        "accepted_slates": members,
        "exclusions": [],
        "failures": [],
        "missing_tasks": [],
        "coverage": {
            "expected_task_count": catalog.TASK_COUNT,
            "accepted_task_count": catalog.TASK_COUNT,
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        },
        **{field: False for field in adapter._PANEL_FALSE_FIELDS},
    }
    panel_body = _with_hash(panel_body, "panel_index_sha256")
    panel_identity = store.seed_json(
        "gs://fixture-parametric/panel/foundry-v12-panel.json", panel_body
    )
    bodies["panel"] = panel_body

    publication_body = {
        "schema_version": "foundry-v12-panel-publication-receipt/v1",
        "mode": "create_once",
        "panel_uri": panel_identity["uri"],
        "panel_object_identity": panel_identity,
        "panel_content_sha256": panel_identity["sha256"],
        "panel_content_bytes": panel_identity["bytes"],
        "panel_id": panel_id,
        "panel_index_sha256": panel_body["panel_index_sha256"],
        "lane_count": 2,
        "accepted_slate_count": catalog.TASK_COUNT,
        "published": True,
        "exact_input_replay_verified": True,
        **{field: False for field in adapter._PUBLICATION_FALSE_FIELDS},
    }
    publication_body = _with_hash(
        publication_body, "publication_receipt_sha256"
    )
    publication_raw = batch.canonical_json_bytes(publication_body) + b"\n"
    publication_path = "fixture/g0/published.json"

    lane_local_bodies: list[dict[str, object]] = []
    lane_local_raw: list[bytes] = []
    lane_local_paths: list[str] = []
    for lane_ordinal, count in enumerate((28, 26)):
        body = {
            "schema_version": "corpus-parametric-batch-accepted/v1",
            "batch_mode": (
                "lane-a-28-task" if lane_ordinal == 0 else "lane-b-26-task"
            ),
            "task_count": count,
            "matrix_cell_count": count * len(batch.PARAMETER_SET_ORDER),
            "batch_completion": completion_identities[lane_ordinal],
            "batch_acceptance": terminal_identities[lane_ordinal],
            "final_output_inventory_sha256": _hash(
                f"lane inventory {lane_ordinal}"
            ),
            "final_output_object_count": 1,
            "complete": True,
            "accepted": True,
        }
        lane_local_bodies.append(body)
        lane_local_raw.append(batch.canonical_json_bytes(body) + b"\n")
        lane_local_paths.append(f"fixture/g0/lane-{lane_ordinal}.json")

    def file_binding(path: str, raw: bytes) -> dict[str, object]:
        return {
            "relative_path": path,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    lock_body = {
        "schema_version": catalog.G0_AUTHORITY_LOCK_SCHEMA,
        "lock_id": "fixture-fixed-g0",
        "official_publication_receipt_file": file_binding(
            publication_path, publication_raw
        ),
        "publication_receipt_sha256": publication_body[
            "publication_receipt_sha256"
        ],
        "lane_terminal_receipts": [
            {
                "lane_ordinal": lane_ordinal,
                "lane_id": "v12a" if lane_ordinal == 0 else "v12b",
                "terminal_receipt_file": file_binding(
                    lane_local_paths[lane_ordinal], lane_local_raw[lane_ordinal]
                ),
                "terminal_receipt_identity": terminal_identities[lane_ordinal],
            }
            for lane_ordinal in range(2)
        ],
        "ordered_terminal_receipt_identities_sha256": _hash(
            terminal_identities
        ),
        "panel_uri": panel_identity["uri"],
        "panel_object_identity": panel_identity,
        "panel_id": panel_id,
        "panel_index_sha256": panel_body["panel_index_sha256"],
        "accepted_slate_count": catalog.TASK_COUNT,
        "review_and_git_commit_required_before_prepare": True,
        **{field: False for field in adapter._G0_FALSE_FIELDS},
    }
    lock_body = _with_hash(lock_body, "g0_authority_lock_sha256")
    lock_raw = batch.canonical_json_bytes(lock_body) + b"\n"
    lock_path = "fixture/g0/g0-authority-lock-v1.json"
    code_path = "src/fixture/catalog_projection.py"
    code_raw = b"fixture committed catalog projection\n"
    commit = adapter.FIXED_SOURCE_COMMIT_SHA
    implementation_commit = "b" * 40
    review_lock_commit = "c" * 40
    adapter_source_raw = b"reviewed fixture adapter source\n"
    adapter_test_raw = b"reviewed fixture adapter test\n"
    catalog_runtime_raw = (
        Path(adapter.REPOSITORY_ROOT) / adapter.FIXED_CATALOG_MODULE_PATH
    ).read_bytes()
    batch_runtime_raw = (
        Path(adapter.REPOSITORY_ROOT) / adapter.FIXED_BATCH_MODULE_PATH
    ).read_bytes()
    measurements = [
        file_binding(adapter.FIXED_ADAPTER_MODULE_PATH, adapter_source_raw),
        file_binding(adapter.FIXED_ADAPTER_TEST_PATH, adapter_test_raw),
        file_binding(adapter.FIXED_CATALOG_MODULE_PATH, catalog_runtime_raw),
        file_binding(adapter.FIXED_BATCH_MODULE_PATH, batch_runtime_raw),
    ]
    failure_summary_raw = b"reviewed fixture focused-test failure summary\n"
    correction_addendum_raw = b"reviewed fixture correction addendum\n"
    second_correction_raw = b"reviewed fixture second correction\n"
    final_corrective_output_raw = b"fixture final corrective test passed\n"
    failure_summary_file = file_binding(
        adapter.FIXED_FOCUSED_TEST_FAILURE_SUMMARY_PATH, failure_summary_raw
    )
    correction_addendum_file = file_binding(
        adapter.FIXED_FOCUSED_TEST_CORRECTION_ADDENDUM_PATH,
        correction_addendum_raw,
    )
    second_correction_file = file_binding(
        adapter.FIXED_SECOND_FOCUSED_TEST_CORRECTION_PATH,
        second_correction_raw,
    )
    final_corrective_output_file = file_binding(
        adapter.FIXED_FINAL_CORRECTIVE_FOCUSED_TEST_OUTPUT_PATH,
        final_corrective_output_raw,
    )
    review_lock_body = adapter.build_preliminary_adapter_review_lock_v1(
        implementation_commit_sha=implementation_commit,
        implementation_measurements=measurements,
        first_focused_test_failure_summary_file=failure_summary_file,
        first_focused_test_correction_addendum_file=correction_addendum_file,
        second_focused_test_correction_file=second_correction_file,
        final_corrective_focused_test_output_file=final_corrective_output_file,
        focused_test_passed=True,
        independent_static_review_passed=True,
    )
    review_lock_raw = batch.canonical_json_bytes(review_lock_body) + b"\n"
    tracked = {
        (commit, lock_path): lock_raw,
        (commit, publication_path): publication_raw,
        **{
            (commit, lane_local_paths[ordinal]): lane_local_raw[ordinal]
            for ordinal in range(2)
        },
        (commit, code_path): code_raw,
        (implementation_commit, adapter.FIXED_ADAPTER_MODULE_PATH): (
            adapter_source_raw
        ),
        (implementation_commit, adapter.FIXED_ADAPTER_TEST_PATH): adapter_test_raw,
        (implementation_commit, adapter.FIXED_CATALOG_MODULE_PATH): (
            catalog_runtime_raw
        ),
        (implementation_commit, adapter.FIXED_BATCH_MODULE_PATH): batch_runtime_raw,
        (
            implementation_commit,
            adapter.FIXED_FOCUSED_TEST_FAILURE_SUMMARY_PATH,
        ): failure_summary_raw,
        (
            implementation_commit,
            adapter.FIXED_FOCUSED_TEST_CORRECTION_ADDENDUM_PATH,
        ): correction_addendum_raw,
        (
            implementation_commit,
            adapter.FIXED_SECOND_FOCUSED_TEST_CORRECTION_PATH,
        ): second_correction_raw,
        (
            implementation_commit,
            adapter.FIXED_FINAL_CORRECTIVE_FOCUSED_TEST_OUTPUT_PATH,
        ): final_corrective_output_raw,
        (review_lock_commit, adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH): (
            review_lock_raw
        ),
        (review_lock_commit, adapter.FIXED_ADAPTER_MODULE_PATH): (
            adapter_source_raw
        ),
        (review_lock_commit, adapter.FIXED_ADAPTER_TEST_PATH): adapter_test_raw,
        (review_lock_commit, adapter.FIXED_CATALOG_MODULE_PATH): (
            catalog_runtime_raw
        ),
        (review_lock_commit, adapter.FIXED_BATCH_MODULE_PATH): batch_runtime_raw,
    }
    pins = adapter.ReplayPinsV1(
        source_commit_sha=commit,
        g0_lock_path=lock_path,
        g0_lock_sha256=sha256(lock_raw).hexdigest(),
        g0_lock_bytes=len(lock_raw),
        g0_lock_internal_sha256=lock_body["g0_authority_lock_sha256"],
        g0_lock_id=lock_body["lock_id"],
        catalog_module_path=code_path,
        catalog_module_sha256=sha256(code_raw).hexdigest(),
        catalog_module_bytes=len(code_raw),
        panel_id=panel_id,
        panel_index_sha256=panel_body["panel_index_sha256"],
        panel_identity=panel_identity,
        lane_terminal_identities=terminal_identities,
        lane_completion_identities=completion_identities,
        source_completion_identity=completion_identity,
        later_source_identity=later_identity,
        catalog_namespace="gs://fixture-output/fixed-g0-v1/",
    )
    review = adapter.AdapterReviewBindingV1(
        review_lock_commit_sha=review_lock_commit,
        implementation_commit_sha=implementation_commit,
        review_lock_relative_path=adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH,
        review_lock_file_sha256=sha256(review_lock_raw).hexdigest(),
        review_lock_file_bytes=len(review_lock_raw),
        review_lock_internal_sha256=review_lock_body[
            "adapter_review_lock_sha256"
        ],
        implementation_measurements=measurements,
    )
    bodies.update({
        "lock": lock_body,
        "publication": publication_body,
        "lane_local": lane_local_bodies,
        "members": members,
        "later_slates": source_slates,
        "completion_tasks": completion_tasks,
    })
    return FixtureGraph(
        store=store,
        pins=pins,
        review=review,
        tracked=tracked,
        bodies=bodies,
    )


@pytest.fixture
def graph() -> FixtureGraph:
    return _fixture_graph()


def _fixture_focused_test_evidence(
    graph: FixtureGraph,
) -> dict[str, Mapping[str, object]]:
    lock = batch.parse_canonical_json_bytes(
        graph.tracked[
            (
                graph.review.review_lock_commit_sha,
                adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH,
            )
        ][:-1],
        label="fixture preliminary lock evidence",
    )
    return {
        "first_focused_test_failure_summary_file": lock[
            "first_focused_test_failure_summary_file"
        ],
        "first_focused_test_correction_addendum_file": lock[
            "first_focused_test_correction_addendum_file"
        ],
        "second_focused_test_correction_file": lock[
            "second_focused_test_correction_file"
        ],
        "final_corrective_focused_test_output_file": lock[
            "final_corrective_focused_test_output_file"
        ],
    }


def _reopen_fixture_task_zero(
    graph: FixtureGraph,
    *,
    member: Mapping[str, object] | None = None,
    terminal: Mapping[str, object] | None = None,
    completion: Mapping[str, object] | None = None,
) -> dict[str, object]:
    retained_member = deepcopy(
        member if member is not None else graph.bodies["members"][0]
    )
    retained_terminal = deepcopy(
        terminal if terminal is not None else graph.bodies["lane_terminals"][0]
    )
    retained_completion = deepcopy(
        completion if completion is not None else graph.bodies["lane_completions"][0]
    )
    artifacts = graph.bodies["later_source"]["slates"][0]["artifact_receipts"]
    expected_worlds = [
        {
            key: artifact[key]
            for key in ("uri", "generation", "sha256", "bytes")
        }
        for artifact in artifacts
    ]
    return adapter._reopen_task_acceptance_and_carrier_v1(
        source_ordinal=0,
        member=retained_member,
        terminal=retained_terminal,
        completion=retained_completion,
        completion_task=retained_completion["task_results"][0],
        source_completion_task=graph.bodies["completion_tasks"][0],
        expected_world_identities=expected_worlds,
        normalized_pins=adapter._normalize_pins(graph.pins),
        transport=graph.store.transport(),
    )


def _fixture_task0_smoke_receipt(
    graph: FixtureGraph,
) -> dict[str, object]:
    return adapter._run_task0_real_artifact_smoke_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
    )


def _fixture_task0_smoke_inputs(
    graph: FixtureGraph,
) -> adapter.ReplayedProjectionInputsV1:
    return adapter._derive_pinned_projection_inputs_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
        task_evidence_ordinals=(0,),
    )


def _install_fixture_final_release_lock(
    graph: FixtureGraph,
) -> tuple[
    str,
    dict[str, object],
    dict[str, object],
    adapter.ReplayedProjectionInputsV1,
]:
    smoke_inputs = _fixture_task0_smoke_inputs(graph)
    smoke = adapter._validate_task0_real_artifact_smoke_receipt_v1(
        adapter._build_task0_real_artifact_smoke_receipt_v1(inputs=smoke_inputs),
        expected_adapter_review_binding=smoke_inputs.adapter_review_binding,
        expected_inputs=smoke_inputs,
    )
    attempt = adapter._validate_task0_smoke_attempt_v1(
        adapter._build_task0_smoke_attempt_v1(
            adapter_review_binding=smoke_inputs.adapter_review_binding
        ),
        expected_adapter_review_binding=smoke_inputs.adapter_review_binding,
    )
    attempt_raw = batch.canonical_json_bytes(attempt) + b"\n"
    smoke_raw = batch.canonical_json_bytes(smoke) + b"\n"
    preliminary_commit = graph.review.review_lock_commit_sha
    preliminary_raw = graph.tracked[
        (preliminary_commit, adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH)
    ]
    head = "d" * 40
    body = adapter._build_final_release_lock_with_expected_smoke_inputs_v1(
        preliminary_review=graph.review,
        preliminary_review_raw=preliminary_raw,
        smoke_attempt_raw=attempt_raw,
        smoke_receipt_raw=smoke_raw,
        independent_static_review_passed=True,
        publication_approved=True,
        expected_smoke_inputs=smoke_inputs,
    )
    final_raw = batch.canonical_json_bytes(body) + b"\n"
    graph.tracked[(head, adapter.FIXED_FINAL_RELEASE_LOCK_PATH)] = final_raw
    graph.tracked[(head, adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH)] = preliminary_raw
    graph.tracked[(head, adapter.FIXED_TASK0_SMOKE_RECEIPT_PATH)] = smoke_raw
    graph.tracked[(head, adapter.FIXED_TASK0_SMOKE_ATTEMPT_PATH)] = attempt_raw
    for measurement in graph.review.implementation_measurements:
        path = str(measurement["relative_path"])
        graph.tracked[(head, path)] = graph.tracked[
            (graph.review.implementation_commit_sha, path)
        ]
    return head, body, smoke, smoke_inputs


def test_fixed_public_surface_has_no_caller_selected_pins() -> None:
    for function in (
        adapter.derive_fixed_g0_projection_inputs_v1,
        adapter.publish_fixed_g0_projection_release_v1,
        adapter.reopen_fixed_g0_replay_receipt_v1,
    ):
        assert "pins" not in inspect.signature(function).parameters
    for function in (
        adapter.build_final_release_lock_v1,
        adapter.validate_final_release_lock_candidate_v1,
    ):
        assert "expected_smoke_inputs" not in inspect.signature(function).parameters


def test_public_entry_point_rejects_coherent_fixture_root(
    graph: FixtureGraph,
) -> None:
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.publish_fixed_g0_projection_release_v1(
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
        )
    assert graph.store.reload_calls == []
    assert graph.store.create_calls == []


def test_fixed_constants_pin_reviewed_identities() -> None:
    assert adapter.FIXED_PINS.source_commit_sha == (
        "168bc70a9793dce729d7e7e0a5d809b046a7a254"
    )
    assert adapter.FIXED_PANEL_IDENTITY["generation"] == "1787663639938214"
    assert adapter.FIXED_SOURCE_COMPLETION_IDENTITY["generation"] == (
        "1787367915631771"
    )
    assert adapter.FIXED_LATER_SOURCE_IDENTITY["generation"] == (
        "1787367678830738"
    )
    assert tuple(
        identity["generation"]
        for identity in adapter.FIXED_LANE_TERMINAL_IDENTITIES
    ) == ("1787656756640443", "1787663188263409")


def test_fixed_identity_maps_cannot_be_mutated_by_caller() -> None:
    with pytest.raises(TypeError):
        adapter.FIXED_PANEL_IDENTITY["uri"] = "gs://alternate/panel.json"
    with pytest.raises(TypeError):
        adapter.FIXED_LATER_SOURCE_IDENTITY["generation"] = "999"


def test_preliminary_lock_builder_is_deterministic_and_self_validating(
    graph: FixtureGraph,
) -> None:
    expected = batch.parse_canonical_json_bytes(
        graph.tracked[
            (
                graph.review.review_lock_commit_sha,
                adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH,
            )
        ][:-1],
        label="fixture preliminary review lock",
    )
    first = adapter.build_preliminary_adapter_review_lock_v1(
        implementation_commit_sha=graph.review.implementation_commit_sha,
        implementation_measurements=graph.review.implementation_measurements,
        focused_test_passed=True,
        independent_static_review_passed=True,
        **_fixture_focused_test_evidence(graph),
    )
    second = adapter.build_preliminary_adapter_review_lock_v1(
        implementation_commit_sha=graph.review.implementation_commit_sha,
        implementation_measurements=graph.review.implementation_measurements,
        focused_test_passed=True,
        independent_static_review_passed=True,
        **_fixture_focused_test_evidence(graph),
    )
    assert first == second == expected
    assert first["focused_test_invocation_count"] == 3
    assert first["focused_test_first_failed_invocation_count"] == 1
    assert first["focused_test_second_failed_invocation_count"] == 1
    assert first["focused_test_final_corrective_invocation_count"] == 1
    assert first["focused_test_total_invocation_count"] == 3
    assert first["focused_test_total_invocation_count_max"] == 3
    assert first["first_failed_pytest_exit_code"] == 1
    assert first["first_failed_failure_count"] == 27
    assert first["second_failed_pytest_exit_code"] == 1
    assert first["second_failed_failure_count"] == 13
    assert first["final_corrective_pytest_exit_code"] == 0
    assert adapter.validate_preliminary_adapter_review_lock_candidate_v1(
        first,
        expected_implementation_commit_sha=(
            graph.review.implementation_commit_sha
        ),
        expected_implementation_measurements=(
            graph.review.implementation_measurements
        ),
    ) == first


@pytest.mark.parametrize(
    ("focused_test_passed", "static_review_passed"),
    [(False, True), (True, False)],
)
def test_preliminary_lock_builder_rejects_missing_approval(
    graph: FixtureGraph,
    focused_test_passed: bool,
    static_review_passed: bool,
) -> None:
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.build_preliminary_adapter_review_lock_v1(
            implementation_commit_sha=graph.review.implementation_commit_sha,
            implementation_measurements=graph.review.implementation_measurements,
            focused_test_passed=focused_test_passed,
            independent_static_review_passed=static_review_passed,
            **_fixture_focused_test_evidence(graph),
        )


def test_preliminary_lock_candidate_rejects_coherent_tamper(
    graph: FixtureGraph,
) -> None:
    lock = adapter.build_preliminary_adapter_review_lock_v1(
        implementation_commit_sha=graph.review.implementation_commit_sha,
        implementation_measurements=graph.review.implementation_measurements,
        focused_test_passed=True,
        independent_static_review_passed=True,
        **_fixture_focused_test_evidence(graph),
    )
    changed = {
        key: value
        for key, value in lock.items()
        if key != "adapter_review_lock_sha256"
    }
    changed["projection_only_publication_reviewed"] = True
    changed = _with_hash(changed, "adapter_review_lock_sha256")
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.validate_preliminary_adapter_review_lock_candidate_v1(
            changed,
            expected_implementation_commit_sha=(
                graph.review.implementation_commit_sha
            ),
            expected_implementation_measurements=(
                graph.review.implementation_measurements
            ),
        )


def test_preliminary_lock_rejects_coherently_rehashed_invocation_erasure(
    graph: FixtureGraph,
) -> None:
    lock = adapter.build_preliminary_adapter_review_lock_v1(
        implementation_commit_sha=graph.review.implementation_commit_sha,
        implementation_measurements=graph.review.implementation_measurements,
        focused_test_passed=True,
        independent_static_review_passed=True,
        **_fixture_focused_test_evidence(graph),
    )
    changed = {
        key: value
        for key, value in lock.items()
        if key != "adapter_review_lock_sha256"
    }
    changed["focused_test_second_failed_invocation_count"] = 0
    changed["focused_test_total_invocation_count"] = 2
    changed["focused_test_total_invocation_count_max"] = 2
    changed = _with_hash(changed, "adapter_review_lock_sha256")
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.validate_preliminary_adapter_review_lock_candidate_v1(
            changed,
            expected_implementation_commit_sha=(
                graph.review.implementation_commit_sha
            ),
            expected_implementation_measurements=(
                graph.review.implementation_measurements
            ),
        )


def test_adapter_review_lock_reopens_separate_code_commit_before_cloud(
    graph: FixtureGraph,
) -> None:
    normalized = adapter._reopen_adapter_review_binding_v1(
        review=graph.review, read_tracked=graph.read_tracked
    )
    assert normalized["implementation_commit_sha"] == "b" * 40
    assert normalized["review_lock_commit_sha"] == "c" * 40
    assert [
        row["relative_path"]
        for row in normalized["implementation_measurements"]
    ] == list(adapter.FIXED_ADAPTER_IMPLEMENTATION_PATHS)
    assert graph.store.reload_calls == []


def test_adapter_review_lock_rejects_changed_implementation_before_cloud(
    graph: FixtureGraph,
) -> None:
    key = (
        graph.review.implementation_commit_sha,
        adapter.FIXED_ADAPTER_MODULE_PATH,
    )
    graph.tracked[key] += b"drift"
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._derive_pinned_projection_inputs_v1(
            pins=graph.pins,
            adapter_review=graph.review,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
        )
    assert graph.store.reload_calls == []


@pytest.mark.parametrize(
    "relative_path",
    [
        adapter.FIXED_FOCUSED_TEST_FAILURE_SUMMARY_PATH,
        adapter.FIXED_FOCUSED_TEST_CORRECTION_ADDENDUM_PATH,
        adapter.FIXED_SECOND_FOCUSED_TEST_CORRECTION_PATH,
        adapter.FIXED_FINAL_CORRECTIVE_FOCUSED_TEST_OUTPUT_PATH,
    ],
)
def test_adapter_review_lock_rejects_correction_evidence_drift_before_cloud(
    graph: FixtureGraph, relative_path: str,
) -> None:
    graph.tracked[
        (graph.review.implementation_commit_sha, relative_path)
    ] += b"drift"
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._derive_pinned_projection_inputs_v1(
            pins=graph.pins,
            adapter_review=graph.review,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
        )
    assert graph.store.reload_calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("focused_test_invocation_count", True),
        ("p0_open_count", False),
    ],
)
def test_adapter_review_lock_rejects_boolean_integer_substitution(
    graph: FixtureGraph, field: str, value: object,
) -> None:
    key = (
        graph.review.review_lock_commit_sha,
        adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH,
    )
    lock = batch.parse_canonical_json_bytes(
        graph.tracked[key][:-1], label="adapter review lock fixture"
    )
    lock[field] = value
    lock = _with_hash(
        {
            name: retained
            for name, retained in lock.items()
            if name != "adapter_review_lock_sha256"
        },
        "adapter_review_lock_sha256",
    )
    normalized_review = adapter._normalize_adapter_review_binding(graph.review)
    normalized_review["review_lock_internal_sha256"] = lock[
        "adapter_review_lock_sha256"
    ]
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._validate_adapter_review_lock_v1(
            lock,
            normalized_review=normalized_review,
            read_tracked=graph.read_tracked,
        )


@pytest.mark.parametrize(
    "field",
    [
        "projection_only_publication_reviewed",
        "full_projection_release_licensed",
        "gcs_mutation_licensed",
    ],
)
def test_preliminary_review_lock_cannot_license_54_task_publication(
    graph: FixtureGraph, field: str,
) -> None:
    key = (
        graph.review.review_lock_commit_sha,
        adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH,
    )
    lock = batch.parse_canonical_json_bytes(
        graph.tracked[key][:-1], label="preliminary review lock fixture"
    )
    lock[field] = True
    lock = _with_hash(
        {
            name: retained
            for name, retained in lock.items()
            if name != "adapter_review_lock_sha256"
        },
        "adapter_review_lock_sha256",
    )
    normalized_review = adapter._normalize_adapter_review_binding(graph.review)
    normalized_review["review_lock_internal_sha256"] = lock[
        "adapter_review_lock_sha256"
    ]
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._validate_adapter_review_lock_v1(
            lock,
            normalized_review=normalized_review,
            read_tracked=graph.read_tracked,
        )


def test_production_review_resolver_replays_current_clean_head(
    graph: FixtureGraph,
) -> None:
    class FixtureRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return graph.review.review_lock_commit_sha

        @staticmethod
        def read_tracked(commit: str, path: str) -> bytes:
            return graph.read_tracked(commit, path)

    head, review = adapter._resolve_current_adapter_review_v1(
        FixtureRepository()
    )
    assert head == graph.review.review_lock_commit_sha
    assert review.review_lock_file_sha256 == graph.review.review_lock_file_sha256
    assert list(review.implementation_measurements) == list(
        graph.review.implementation_measurements
    )
    assert graph.store.reload_calls == []


@pytest.mark.parametrize(
    "relative_path",
    [
        adapter.FIXED_ADAPTER_MODULE_PATH,
        adapter.FIXED_ADAPTER_TEST_PATH,
        adapter.FIXED_CATALOG_MODULE_PATH,
        adapter.FIXED_BATCH_MODULE_PATH,
    ],
)
def test_production_review_resolver_rejects_current_runtime_code_drift(
    graph: FixtureGraph, relative_path: str,
) -> None:
    graph.tracked[
        (
            graph.review.review_lock_commit_sha,
            relative_path,
        )
    ] += b"current-head-drift"

    class FixtureRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return graph.review.review_lock_commit_sha

        @staticmethod
        def read_tracked(commit: str, path: str) -> bytes:
            return graph.read_tracked(commit, path)

    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._resolve_current_adapter_review_v1(FixtureRepository())
    assert graph.store.reload_calls == []


def test_preliminary_lock_production_builder_measures_git_and_writes_once(
    graph: FixtureGraph,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "reports").mkdir()
    head = graph.review.implementation_commit_sha

    class FixtureRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return head

        @staticmethod
        def read_tracked(commit: str, path: str) -> bytes:
            return graph.read_tracked(commit, path)

    monkeypatch.setattr(adapter, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(
        adapter, "SubprocessGitRepositoryV1", lambda: FixtureRepository()
    )
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1,
        "from_default_client",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected cloud client")),
    )
    lock = adapter.write_preliminary_adapter_review_lock_production_v1(
        output_relative_path=adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH,
        focused_test_passed=True,
        independent_static_review_passed=True,
    )
    output = tmp_path / adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH
    assert output.read_bytes() == batch.canonical_json_bytes(lock) + b"\n"
    assert lock["implementation_commit_sha"] == head
    assert [
        row["relative_path"] for row in lock["implementation_measurements"]
    ] == list(adapter.FIXED_ADAPTER_IMPLEMENTATION_PATHS)

    monkeypatch.setattr(
        adapter,
        "SubprocessGitRepositoryV1",
        lambda: (_ for _ in ()).throw(AssertionError("Git after collision")),
    )
    with pytest.raises(
        adapter.CorpusR6FixedG0AdapterV1Error, match="already exists"
    ):
        adapter.write_preliminary_adapter_review_lock_production_v1(
            output_relative_path=adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH,
            focused_test_passed=True,
            independent_static_review_passed=True,
        )


def test_preliminary_lock_wrong_output_or_dirty_git_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "reports").mkdir()
    monkeypatch.setattr(adapter, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(
        adapter,
        "SubprocessGitRepositoryV1",
        lambda: (_ for _ in ()).throw(
            adapter.CorpusR6FixedG0AdapterV1Error("repository is dirty")
        ),
    )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.write_preliminary_adapter_review_lock_production_v1(
            output_relative_path="reports/wrong-preliminary.json",
            focused_test_passed=True,
            independent_static_review_passed=True,
        )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error, match="dirty"):
        adapter.write_preliminary_adapter_review_lock_production_v1(
            output_relative_path=adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH,
            focused_test_passed=True,
            independent_static_review_passed=True,
        )
    assert not (tmp_path / adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH).exists()


def test_production_entry_missing_final_lock_constructs_no_cloud_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud_calls = 0

    class MissingLockRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return "d" * 40

        @staticmethod
        def read_tracked(_commit: str, _path: str) -> bytes:
            raise FileNotFoundError("final lock absent")

    def forbidden_cloud_client():
        nonlocal cloud_calls
        cloud_calls += 1
        raise AssertionError("cloud client constructed before final lock")

    monkeypatch.setenv(adapter.PRODUCTION_ENABLE_ENV, "1")
    monkeypatch.setattr(
        adapter, "SubprocessGitRepositoryV1", lambda: MissingLockRepository()
    )
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1,
        "from_default_client",
        forbidden_cloud_client,
    )
    with pytest.raises(
        adapter.CorpusR6FixedG0AdapterV1Error,
        match="final release lock is absent",
    ):
        adapter.run_reviewed_fixed_g0_projection_release_production_v1()
    assert cloud_calls == 0


def test_production_entry_parked_before_git_or_cloud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(adapter.PRODUCTION_ENABLE_ENV, raising=False)
    monkeypatch.setattr(
        adapter,
        "SubprocessGitRepositoryV1",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected Git access")),
    )
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1,
        "from_default_client",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected cloud access")),
    )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error, match="parked"):
        adapter.run_reviewed_fixed_g0_projection_release_production_v1()


def test_task0_smoke_reopens_only_exact_task0_evidence(
    graph: FixtureGraph,
) -> None:
    receipt = _fixture_task0_smoke_receipt(graph)
    expected_uris = [
        graph.pins.panel_identity["uri"],
        graph.pins.lane_terminal_identities[0]["uri"],
        graph.pins.lane_completion_identities[0]["uri"],
        graph.pins.later_source_identity["uri"],
        graph.pins.source_completion_identity["uri"],
        graph.bodies["members"][0]["task_acceptance_identity"]["uri"],
        graph.bodies["members"][0]["carrier_identity"]["uri"],
    ]
    assert [uri for uri, _ in graph.store.reload_calls] == expected_uris
    assert [uri for uri, _ in graph.store.download_calls] == expected_uris
    assert graph.store.create_calls == []
    assert receipt["source_task_ordinals"] == [0]
    assert receipt["generation_pinned_input_count"] == 7
    assert receipt["task_acceptance_body_count"] == 1
    assert receipt["carrier_body_count"] == 1
    assert receipt["gcs_publication_count"] == 0
    assert receipt["full_projection_release_licensed"] is False
    assert receipt["world_matrix_bodies_reopened"] is False
    assert receipt["result_object_bodies_reopened"] is False
    assert receipt["outcome_columns_read"] == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reserved_before_cloud_contact", False),
        ("gcs_publication_count", True),
        ("full_projection_release_licensed", True),
    ],
)
def test_task0_attempt_marker_rejects_coherently_rehashed_widening(
    graph: FixtureGraph, field: str, value: object,
) -> None:
    review = adapter._normalize_adapter_review_binding(graph.review)
    attempt = adapter._build_task0_smoke_attempt_v1(
        adapter_review_binding=review
    )
    changed = {
        key: retained
        for key, retained in attempt.items()
        if key != "task0_real_artifact_smoke_attempt_sha256"
    }
    changed[field] = value
    changed = _with_hash(
        changed, "task0_real_artifact_smoke_attempt_sha256"
    )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._validate_task0_smoke_attempt_v1(
            changed, expected_adapter_review_binding=review
        )


@pytest.mark.parametrize("ordinals", [(1,), (0, 1), (False,)])
def test_restricted_smoke_cannot_select_a_caller_shaped_task_set(
    graph: FixtureGraph, ordinals: tuple[object, ...],
) -> None:
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._derive_pinned_projection_inputs_v1(
            pins=graph.pins,
            adapter_review=graph.review,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
            task_evidence_ordinals=ordinals,
        )
    assert graph.store.reload_calls == []
    assert graph.store.create_calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("full_projection_release_licensed", True),
        ("gcs_publication_count", 1),
        ("invocation_count", True),
    ],
)
def test_task0_smoke_receipt_rejects_coherently_rehashed_authority_widening(
    graph: FixtureGraph, field: str, value: object,
) -> None:
    inputs = _fixture_task0_smoke_inputs(graph)
    receipt = adapter._build_task0_real_artifact_smoke_receipt_v1(inputs=inputs)
    changed = {
        key: retained
        for key, retained in receipt.items()
        if key != "task0_real_artifact_smoke_sha256"
    }
    changed[field] = value
    changed = _with_hash(changed, "task0_real_artifact_smoke_sha256")
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._validate_task0_real_artifact_smoke_receipt_v1(
            changed,
            expected_adapter_review_binding=inputs.adapter_review_binding,
            expected_inputs=inputs,
        )


def test_final_release_lock_reopens_smoke_and_runtime_closure_before_cloud(
    graph: FixtureGraph,
) -> None:
    head, expected, _, smoke_inputs = _install_fixture_final_release_lock(graph)

    class FixtureRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return head

        @staticmethod
        def read_tracked(commit: str, path: str) -> bytes:
            return graph.read_tracked(commit, path)

    observed_head, review, final_lock = (
        adapter._resolve_current_final_release_lock_v1(
            FixtureRepository(), expected_smoke_inputs=smoke_inputs
        )
    )
    assert observed_head == head
    assert review.review_lock_commit_sha == graph.review.review_lock_commit_sha
    assert final_lock == expected
    assert graph.store.create_calls == []


def test_final_release_lock_builder_is_deterministic_and_requires_approval(
    graph: FixtureGraph,
) -> None:
    head, expected, _, smoke_inputs = _install_fixture_final_release_lock(graph)
    preliminary_raw = graph.tracked[
        (
            graph.review.review_lock_commit_sha,
            adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH,
        )
    ]
    attempt_raw = graph.tracked[(head, adapter.FIXED_TASK0_SMOKE_ATTEMPT_PATH)]
    smoke_raw = graph.tracked[(head, adapter.FIXED_TASK0_SMOKE_RECEIPT_PATH)]
    rebuilt = adapter._build_final_release_lock_with_expected_smoke_inputs_v1(
        preliminary_review=graph.review,
        preliminary_review_raw=preliminary_raw,
        smoke_attempt_raw=attempt_raw,
        smoke_receipt_raw=smoke_raw,
        independent_static_review_passed=True,
        publication_approved=True,
        expected_smoke_inputs=smoke_inputs,
    )
    assert rebuilt == expected
    assert adapter._validate_final_release_lock_v1(
        rebuilt,
        preliminary_review=graph.review,
        preliminary_review_raw=preliminary_raw,
        smoke_attempt_raw=attempt_raw,
        smoke_receipt_raw=smoke_raw,
        expected_smoke_inputs=smoke_inputs,
    ) == rebuilt
    for static_approved, publication_approved in ((False, True), (True, False)):
        with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
            adapter._build_final_release_lock_with_expected_smoke_inputs_v1(
                preliminary_review=graph.review,
                preliminary_review_raw=preliminary_raw,
                smoke_attempt_raw=attempt_raw,
                smoke_receipt_raw=smoke_raw,
                independent_static_review_passed=static_approved,
                publication_approved=publication_approved,
                expected_smoke_inputs=smoke_inputs,
            )


def test_final_lock_production_builder_replays_tracked_inputs_and_writes_once(
    graph: FixtureGraph,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "reports").mkdir()
    head, expected, _, _ = _install_fixture_final_release_lock(graph)
    del graph.tracked[(head, adapter.FIXED_FINAL_RELEASE_LOCK_PATH)]

    class FixtureRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return head

        @staticmethod
        def read_tracked(commit: str, path: str) -> bytes:
            return graph.read_tracked(commit, path)

    monkeypatch.setattr(adapter, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(adapter, "FIXED_PINS", graph.pins)
    monkeypatch.setattr(
        adapter, "SubprocessGitRepositoryV1", lambda: FixtureRepository()
    )
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1,
        "from_default_client",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected cloud client")),
    )
    lock = adapter.write_final_release_lock_production_v1(
        output_relative_path=adapter.FIXED_FINAL_RELEASE_LOCK_PATH,
        independent_static_review_passed=True,
        publication_approved=True,
    )
    assert lock == expected
    output = tmp_path / adapter.FIXED_FINAL_RELEASE_LOCK_PATH
    assert output.read_bytes() == batch.canonical_json_bytes(lock) + b"\n"

    monkeypatch.setattr(
        adapter,
        "SubprocessGitRepositoryV1",
        lambda: (_ for _ in ()).throw(AssertionError("Git after collision")),
    )
    with pytest.raises(
        adapter.CorpusR6FixedG0AdapterV1Error, match="already exists"
    ):
        adapter.write_final_release_lock_production_v1(
            output_relative_path=adapter.FIXED_FINAL_RELEASE_LOCK_PATH,
            independent_static_review_passed=True,
            publication_approved=True,
        )


def test_final_lock_production_builder_rejects_current_code_drift_before_write(
    graph: FixtureGraph,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "reports").mkdir()
    head, _, _, _ = _install_fixture_final_release_lock(graph)
    del graph.tracked[(head, adapter.FIXED_FINAL_RELEASE_LOCK_PATH)]
    graph.tracked[(head, adapter.FIXED_BATCH_MODULE_PATH)] += b"drift"

    class FixtureRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return head

        @staticmethod
        def read_tracked(commit: str, path: str) -> bytes:
            return graph.read_tracked(commit, path)

    monkeypatch.setattr(adapter, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(adapter, "FIXED_PINS", graph.pins)
    monkeypatch.setattr(
        adapter, "SubprocessGitRepositoryV1", lambda: FixtureRepository()
    )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.write_final_release_lock_production_v1(
            output_relative_path=adapter.FIXED_FINAL_RELEASE_LOCK_PATH,
            independent_static_review_passed=True,
            publication_approved=True,
        )
    assert not (tmp_path / adapter.FIXED_FINAL_RELEASE_LOCK_PATH).exists()


@pytest.mark.parametrize(
    ("relative_path", "builder"),
    [
        (adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH, "preliminary"),
        (adapter.FIXED_FINAL_RELEASE_LOCK_PATH, "final"),
    ],
)
def test_lock_builder_dangling_symlink_blocks_before_git_or_cloud(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    relative_path: str,
    builder: str,
) -> None:
    (tmp_path / "reports").mkdir()
    target = tmp_path / "outside-lock.json"
    (tmp_path / relative_path).symlink_to(target)
    monkeypatch.setattr(adapter, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(
        adapter,
        "SubprocessGitRepositoryV1",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected Git access")),
    )
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1,
        "from_default_client",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected cloud client")),
    )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        if builder == "preliminary":
            adapter.write_preliminary_adapter_review_lock_production_v1(
                output_relative_path=relative_path,
                focused_test_passed=True,
                independent_static_review_passed=True,
            )
        else:
            adapter.write_final_release_lock_production_v1(
                output_relative_path=relative_path,
                independent_static_review_passed=True,
                publication_approved=True,
            )
    assert not target.exists()


def test_final_release_lock_rejects_tracked_smoke_drift(
    graph: FixtureGraph,
) -> None:
    head, final_lock, _, smoke_inputs = _install_fixture_final_release_lock(graph)
    smoke_key = (head, adapter.FIXED_TASK0_SMOKE_RECEIPT_PATH)
    graph.tracked[smoke_key] += b"drift"

    class FixtureRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return head

        @staticmethod
        def read_tracked(commit: str, path: str) -> bytes:
            return graph.read_tracked(commit, path)

    assert final_lock["task0_smoke_passed"] is True
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._resolve_current_final_release_lock_v1(
            FixtureRepository(), expected_smoke_inputs=smoke_inputs
        )
    assert graph.store.create_calls == []


def test_final_release_lock_rejects_tracked_attempt_marker_drift(
    graph: FixtureGraph,
) -> None:
    head, _, _, smoke_inputs = _install_fixture_final_release_lock(graph)
    attempt_key = (head, adapter.FIXED_TASK0_SMOKE_ATTEMPT_PATH)
    graph.tracked[attempt_key] += b"drift"

    class FixtureRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return head

        @staticmethod
        def read_tracked(commit: str, path: str) -> bytes:
            return graph.read_tracked(commit, path)

    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._resolve_current_final_release_lock_v1(
            FixtureRepository(), expected_smoke_inputs=smoke_inputs
        )
    assert graph.store.create_calls == []


def test_final_release_lock_rejects_current_batch_dependency_drift(
    graph: FixtureGraph,
) -> None:
    head, _, _, smoke_inputs = _install_fixture_final_release_lock(graph)
    graph.tracked[(head, adapter.FIXED_BATCH_MODULE_PATH)] += b"drift"

    class FixtureRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return head

        @staticmethod
        def read_tracked(commit: str, path: str) -> bytes:
            return graph.read_tracked(commit, path)

    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._resolve_current_final_release_lock_v1(
            FixtureRepository(), expected_smoke_inputs=smoke_inputs
        )
    assert graph.store.create_calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("gcs_overwrite_licensed", True),
        ("required_source_task_count", True),
        ("unexpected_authority", True),
    ],
)
def test_final_release_lock_rejects_coherently_rehashed_widening(
    graph: FixtureGraph, field: str, value: object,
) -> None:
    head, final_lock, _, smoke_inputs = _install_fixture_final_release_lock(graph)
    changed = {
        key: retained
        for key, retained in final_lock.items()
        if key != "final_release_lock_sha256"
    }
    changed[field] = value
    changed = _with_hash(changed, "final_release_lock_sha256")
    preliminary_raw = graph.tracked[
        (
            graph.review.review_lock_commit_sha,
            adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH,
        )
    ]
    smoke_raw = graph.tracked[(head, adapter.FIXED_TASK0_SMOKE_RECEIPT_PATH)]
    attempt_raw = graph.tracked[(head, adapter.FIXED_TASK0_SMOKE_ATTEMPT_PATH)]
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._validate_final_release_lock_v1(
            changed,
            preliminary_review=graph.review,
            preliminary_review_raw=preliminary_raw,
            smoke_attempt_raw=attempt_raw,
            smoke_receipt_raw=smoke_raw,
            expected_smoke_inputs=smoke_inputs,
        )


def test_task0_smoke_production_writes_one_fixed_local_receipt(
    graph: FixtureGraph,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "reports").mkdir()

    class FixtureRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return graph.review.review_lock_commit_sha

        @staticmethod
        def read_tracked(commit: str, path: str) -> bytes:
            return graph.read_tracked(commit, path)

    class FixtureBackend:
        @staticmethod
        def transport() -> adapter.GenerationTransportV1:
            return graph.store.transport()

    monkeypatch.setattr(adapter, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(adapter, "FIXED_PINS", graph.pins)
    monkeypatch.setattr(
        adapter, "SubprocessGitRepositoryV1", lambda: FixtureRepository()
    )
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1,
        "from_default_client",
        lambda: FixtureBackend(),
    )
    receipt = adapter.run_task0_real_artifact_smoke_production_v1()
    output = tmp_path / adapter.FIXED_TASK0_SMOKE_RECEIPT_PATH
    attempt_output = tmp_path / adapter.FIXED_TASK0_SMOKE_ATTEMPT_PATH
    assert output.read_bytes() == batch.canonical_json_bytes(receipt) + b"\n"
    assert attempt_output.read_bytes() == (
        batch.canonical_json_bytes(adapter._build_task0_smoke_attempt_v1(
            adapter_review_binding=receipt["adapter_review_binding"]
        ))
        + b"\n"
    )
    assert graph.store.create_calls == []

    monkeypatch.setattr(
        adapter,
        "SubprocessGitRepositoryV1",
        lambda: (_ for _ in ()).throw(AssertionError("second Git invocation")),
    )
    with pytest.raises(
        adapter.CorpusR6FixedG0AdapterV1Error, match="already exists"
    ):
        adapter.run_task0_real_artifact_smoke_production_v1()


def test_task0_smoke_missing_review_writes_no_marker_and_contacts_no_cloud(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "reports").mkdir()
    cloud_calls = 0

    class MissingReviewRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return "d" * 40

        @staticmethod
        def read_tracked(_commit: str, _path: str) -> bytes:
            raise FileNotFoundError("preliminary review absent")

    def forbidden_cloud_client():
        nonlocal cloud_calls
        cloud_calls += 1
        raise AssertionError("cloud client constructed before review")

    monkeypatch.setattr(adapter, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(
        adapter,
        "SubprocessGitRepositoryV1",
        lambda: MissingReviewRepository(),
    )
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1,
        "from_default_client",
        forbidden_cloud_client,
    )
    with pytest.raises(
        adapter.CorpusR6FixedG0AdapterV1Error,
        match="adapter review lock is absent",
    ):
        adapter.run_task0_real_artifact_smoke_production_v1()
    assert cloud_calls == 0
    assert not (tmp_path / adapter.FIXED_TASK0_SMOKE_ATTEMPT_PATH).exists()
    assert not (tmp_path / adapter.FIXED_TASK0_SMOKE_RECEIPT_PATH).exists()


def test_task0_smoke_failed_first_read_consumes_attempt_before_retry(
    graph: FixtureGraph,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "reports").mkdir()
    read_attempts = 0

    class FixtureRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return graph.review.review_lock_commit_sha

        @staticmethod
        def read_tracked(commit: str, path: str) -> bytes:
            return graph.read_tracked(commit, path)

    def failing_reload(_uri: str, _generation: str) -> Mapping[str, object]:
        nonlocal read_attempts
        read_attempts += 1
        raise adapter.ObjectNotFoundV1Error("injected first read failure")

    class FailingBackend:
        @staticmethod
        def transport() -> adapter.GenerationTransportV1:
            return adapter.GenerationTransportV1(
                reload_generation=failing_reload,
                download_generation=lambda _uri, _generation: (_ for _ in ()).throw(
                    AssertionError("download after failed reload")
                ),
                resolve_current=lambda _uri: (_ for _ in ()).throw(
                    AssertionError("output resolution during smoke")
                ),
                create_if_absent=lambda _uri, _raw, _precondition: (
                    (_ for _ in ()).throw(AssertionError("GCS create during smoke"))
                ),
            )

    monkeypatch.setattr(adapter, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(adapter, "FIXED_PINS", graph.pins)
    monkeypatch.setattr(
        adapter, "SubprocessGitRepositoryV1", lambda: FixtureRepository()
    )
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1,
        "from_default_client",
        lambda: FailingBackend(),
    )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.run_task0_real_artifact_smoke_production_v1()
    assert read_attempts == 1
    assert (tmp_path / adapter.FIXED_TASK0_SMOKE_ATTEMPT_PATH).is_file()
    assert not (tmp_path / adapter.FIXED_TASK0_SMOKE_RECEIPT_PATH).exists()

    monkeypatch.setattr(
        adapter,
        "SubprocessGitRepositoryV1",
        lambda: (_ for _ in ()).throw(AssertionError("retry reached Git")),
    )
    with pytest.raises(
        adapter.CorpusR6FixedG0AdapterV1Error, match="attempt already exists"
    ):
        adapter.run_task0_real_artifact_smoke_production_v1()
    assert read_attempts == 1


def test_task0_smoke_post_read_crash_window_cannot_contact_gcs_twice(
    graph: FixtureGraph,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "reports").mkdir()

    class FixtureRepository:
        @staticmethod
        def require_current_clean_head() -> str:
            return graph.review.review_lock_commit_sha

        @staticmethod
        def read_tracked(commit: str, path: str) -> bytes:
            return graph.read_tracked(commit, path)

    class FixtureBackend:
        @staticmethod
        def transport() -> adapter.GenerationTransportV1:
            return graph.store.transport()

    monkeypatch.setattr(adapter, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(adapter, "FIXED_PINS", graph.pins)
    monkeypatch.setattr(
        adapter, "SubprocessGitRepositoryV1", lambda: FixtureRepository()
    )
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1,
        "from_default_client",
        lambda: FixtureBackend(),
    )
    monkeypatch.setattr(
        adapter,
        "_write_task0_smoke_receipt_once_v1",
        lambda _path, _receipt: (_ for _ in ()).throw(
            RuntimeError("injected crash after real reads")
        ),
    )
    with pytest.raises(RuntimeError, match="injected crash"):
        adapter.run_task0_real_artifact_smoke_production_v1()
    first_read_count = len(graph.store.reload_calls)
    assert first_read_count == 7
    assert (tmp_path / adapter.FIXED_TASK0_SMOKE_ATTEMPT_PATH).is_file()
    assert not (tmp_path / adapter.FIXED_TASK0_SMOKE_RECEIPT_PATH).exists()

    with pytest.raises(
        adapter.CorpusR6FixedG0AdapterV1Error, match="attempt already exists"
    ):
        adapter.run_task0_real_artifact_smoke_production_v1()
    assert len(graph.store.reload_calls) == first_read_count


@pytest.mark.parametrize(
    "relative_path",
    [
        adapter.FIXED_TASK0_SMOKE_ATTEMPT_PATH,
        adapter.FIXED_TASK0_SMOKE_RECEIPT_PATH,
    ],
)
def test_task0_smoke_dangling_local_symlink_blocks_before_git_or_cloud(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, relative_path: str,
) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    target = tmp_path / "outside.json"
    (tmp_path / relative_path).symlink_to(target)
    monkeypatch.setattr(adapter, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(
        adapter,
        "SubprocessGitRepositoryV1",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected Git access")),
    )
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1,
        "from_default_client",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected cloud access")),
    )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.run_task0_real_artifact_smoke_production_v1()
    assert not target.exists()


def test_generation_exact_reader_ignores_newer_latest() -> None:
    store = FakeGenerationStore()
    old = store.seed_raw("gs://fixture/read/object.json", b"old", generation="11")
    store.seed_raw("gs://fixture/read/object.json", b"new", generation="12")
    assert adapter.read_generation_exact_v1(
        old, transport=store.transport()
    ) == b"old"
    assert store.reload_calls == [(old["uri"], "11")]
    assert store.download_calls == [(old["uri"], "11")]


@pytest.mark.parametrize("drift_field", ["uri", "generation", "sha256", "bytes"])
def test_generation_exact_reader_rejects_identity_drift(drift_field: str) -> None:
    store = FakeGenerationStore()
    identity = store.seed_raw("gs://fixture/read/object.json", b"old")
    changed = dict(identity)
    changed[drift_field] = {
        "uri": "gs://fixture/read/other.json",
        "generation": "999999",
        "sha256": _hash("different"),
        "bytes": 999,
    }[drift_field]
    store.reload_override = changed
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.read_generation_exact_v1(identity, transport=store.transport())


def test_generation_exact_reader_rejects_body_drift() -> None:
    store = FakeGenerationStore()
    identity = store.seed_raw("gs://fixture/read/object.json", b"old")
    store.download_override = b"bad"
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.read_generation_exact_v1(identity, transport=store.transport())


def test_create_once_new_object_uses_literal_zero_and_exact_reopens() -> None:
    store = FakeGenerationStore()
    identity = adapter.publish_create_once_resumable_v1(
        "gs://fixture/output/object.json", b"body", transport=store.transport()
    )
    assert store.create_calls == [
        ("gs://fixture/output/object.json", b"body", 0)
    ]
    assert adapter.read_generation_exact_v1(
        identity, transport=store.transport()
    ) == b"body"


def test_create_once_identical_occupied_object_is_resumable() -> None:
    store = FakeGenerationStore()
    expected = store.seed_raw("gs://fixture/output/object.json", b"body")
    observed = adapter.publish_create_once_resumable_v1(
        expected["uri"], b"body", transport=store.transport()
    )
    assert observed == expected
    assert store.create_calls == []


def test_create_once_different_occupied_object_fails_without_overwrite() -> None:
    store = FakeGenerationStore()
    identity = store.seed_raw("gs://fixture/output/object.json", b"old")
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.publish_create_once_resumable_v1(
            identity["uri"], b"new", transport=store.transport()
        )
    assert store.create_calls == []
    assert store.objects[(identity["uri"], identity["generation"])] == b"old"


@pytest.mark.parametrize("race_body, succeeds", [(b"body", True), (b"other", False)])
def test_create_once_collision_reopens_winner(
    race_body: bytes, succeeds: bool,
) -> None:
    store = FakeGenerationStore()
    store.race_body = race_body
    if succeeds:
        identity = adapter.publish_create_once_resumable_v1(
            "gs://fixture/output/race.json", b"body", transport=store.transport()
        )
        assert store.objects[(identity["uri"], identity["generation"])] == b"body"
    else:
        with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
            adapter.publish_create_once_resumable_v1(
                "gs://fixture/output/race.json",
                b"body",
                transport=store.transport(),
            )
    assert store.create_calls[0][2] == 0


def test_fixture_replay_derives_exact_54_projection_chain(
    graph: FixtureGraph,
) -> None:
    inputs = adapter._derive_pinned_projection_inputs_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
    )
    assert len(inputs.member_bindings) == catalog.TASK_COUNT
    assert len(inputs.source_catalog_bindings) == catalog.TASK_COUNT
    assert len(inputs.completion_bindings) == catalog.TASK_COUNT
    assert len(inputs.structural_players) == catalog.TASK_COUNT
    assert inputs.task_acceptance_body_count == catalog.TASK_COUNT
    assert inputs.carrier_body_count == catalog.TASK_COUNT
    assert [
        (
            inputs.member_bindings[index]["lane_id"],
            inputs.member_bindings[index]["task_ordinal"],
        )
        for index in (0, 27, 28, 53)
    ] == [("v12a", 0), ("v12a", 27), ("v12b", 0), ("v12b", 25)]
    assert all(len(players) == 20 for players in inputs.structural_players)
    assert graph.store.create_calls == []
    expected_read_uris = {
        graph.pins.panel_identity["uri"],
        *(identity["uri"] for identity in graph.pins.lane_terminal_identities),
        *(identity["uri"] for identity in graph.pins.lane_completion_identities),
        graph.pins.later_source_identity["uri"],
        graph.pins.source_completion_identity["uri"],
        *(
            member["task_acceptance_identity"]["uri"]
            for member in graph.bodies["members"]
        ),
        *(
            member["carrier_identity"]["uri"]
            for member in graph.bodies["members"]
        ),
    }
    assert {uri for uri, _ in graph.store.download_calls} == expected_read_uris
    assert sum("/acceptance.json" in uri for uri, _ in graph.store.download_calls) == 54
    assert sum("/task-result.json" in uri for uri, _ in graph.store.download_calls) == 54
    assert not any("world-" in uri for uri, _ in graph.store.download_calls)
    assert not any("arm-result" in uri for uri, _ in graph.store.download_calls)


def test_fixture_all_54_carrier_world_hashes_match_completion_rows(
    graph: FixtureGraph,
) -> None:
    for source_ordinal, carrier in enumerate(graph.bodies["task_carriers"]):
        lane = catalog.expected_lane_for_source_task(source_ordinal)
        completion = graph.bodies["lane_completions"][int(lane["lane_ordinal"])]
        completion_task = completion["task_results"][int(lane["task_ordinal"])]
        expected = _hash(carrier["world_artifact_receipts"])
        assert carrier["world_artifact_receipt_set_sha256"] == expected
        assert completion_task["world_artifact_receipt_set_sha256"] == expected


def test_task_carrier_rejects_completion_world_hash_substitution(
    graph: FixtureGraph,
) -> None:
    completion = deepcopy(graph.bodies["lane_completions"][0])
    completion["task_results"][0]["world_artifact_receipt_set_sha256"] = _hash(
        "coherent but wrong completion world set"
    )
    with pytest.raises(
        adapter.CorpusR6FixedG0AdapterV1Error,
        match="world receipt set hash differs",
    ):
        _reopen_fixture_task_zero(graph, completion=completion)


def test_task_acceptance_exact_reopen_rejects_invalid_embedded_self_hash(
    graph: FixtureGraph,
) -> None:
    body = deepcopy(graph.bodies["task_acceptances"][0])
    body["accepted"] = False
    old_identity = graph.bodies["members"][0]["task_acceptance_identity"]
    identity = graph.store.seed_json(
        str(old_identity["uri"]), body, transport=True
    )
    member = deepcopy(graph.bodies["members"][0])
    member["task_acceptance_identity"] = identity
    terminal = deepcopy(graph.bodies["lane_terminals"][0])
    terminal["task_acceptances"][0] = identity

    with pytest.raises(
        adapter.CorpusR6FixedG0AdapterV1Error,
        match="transport self-hash differs",
    ):
        _reopen_fixture_task_zero(
            graph, member=member, terminal=terminal
        )


def test_task_carrier_exact_reopen_rejects_invalid_embedded_self_hash(
    graph: FixtureGraph,
) -> None:
    carrier = deepcopy(graph.bodies["task_carriers"][0])
    carrier["world_seed"] += 1
    old_carrier = graph.bodies["members"][0]["carrier_identity"]
    carrier_identity = graph.store.seed_json(
        str(old_carrier["uri"]), carrier
    )

    acceptance = deepcopy(graph.bodies["task_acceptances"][0])
    acceptance["task_result"] = carrier_identity
    acceptance = _with_hash(
        {
            key: value
            for key, value in acceptance.items()
            if key != "task_acceptance_sha256"
        },
        "task_acceptance_sha256",
        transport=True,
    )
    old_acceptance = graph.bodies["members"][0]["task_acceptance_identity"]
    acceptance_identity = graph.store.seed_json(
        str(old_acceptance["uri"]), acceptance, transport=True
    )
    member = deepcopy(graph.bodies["members"][0])
    member["carrier_identity"] = carrier_identity
    member["task_acceptance_identity"] = acceptance_identity
    terminal = deepcopy(graph.bodies["lane_terminals"][0])
    terminal["task_acceptances"][0] = acceptance_identity
    completion = deepcopy(graph.bodies["lane_completions"][0])
    completion["task_results"][0]["task_result_object"] = carrier_identity

    with pytest.raises(
        adapter.CorpusR6FixedG0AdapterV1Error,
        match="self-hash differs",
    ):
        _reopen_fixture_task_zero(
            graph,
            member=member,
            terminal=terminal,
            completion=completion,
        )


def test_fixture_replay_is_stable_across_latest_generation_drift(
    graph: FixtureGraph,
) -> None:
    panel_identity = graph.pins.panel_identity
    graph.store.seed_raw(str(panel_identity["uri"]), b"newer unrelated panel")
    inputs = adapter._derive_pinned_projection_inputs_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
    )
    assert inputs.tracked_root_binding["panel_object_identity"] == panel_identity


def test_fixture_replay_missing_pinned_generation_fails(
    graph: FixtureGraph,
) -> None:
    identity = graph.pins.panel_identity
    key = (str(identity["uri"]), str(identity["generation"]))
    del graph.store.objects[key]
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._derive_pinned_projection_inputs_v1(
            pins=graph.pins,
            adapter_review=graph.review,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
        )


def test_fixture_replay_rejects_committed_code_mutation(
    graph: FixtureGraph,
) -> None:
    key = (graph.pins.source_commit_sha, graph.pins.catalog_module_path)
    graph.tracked[key] = b"different committed code\n"
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._derive_pinned_projection_inputs_v1(
            pins=graph.pins,
            adapter_review=graph.review,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
        )
    assert graph.store.create_calls == []


def test_fixture_replay_rejects_tracked_g0_mutation(
    graph: FixtureGraph,
) -> None:
    key = (graph.pins.source_commit_sha, graph.pins.g0_lock_path)
    graph.tracked[key] += b" "
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._derive_pinned_projection_inputs_v1(
            pins=graph.pins,
            adapter_review=graph.review,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
        )
    assert graph.store.create_calls == []


def test_panel_member_reorder_fails_even_when_panel_is_rehashed(
    graph: FixtureGraph,
) -> None:
    panel = deepcopy(graph.bodies["panel"])
    panel["accepted_slates"][27], panel["accepted_slates"][28] = (
        panel["accepted_slates"][28],
        panel["accepted_slates"][27],
    )
    panel = _with_hash(
        {key: value for key, value in panel.items() if key != "panel_index_sha256"},
        "panel_index_sha256",
    )
    pins = adapter._normalize_pins(graph.pins)
    pins["panel_index_sha256"] = panel["panel_index_sha256"]
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._validate_panel(panel, normalized_pins=pins)


def test_panel_lane_mapping_mutation_fails_when_rehashed(
    graph: FixtureGraph,
) -> None:
    panel = deepcopy(graph.bodies["panel"])
    panel["lanes"][1]["lane_id"] = "v12a"
    panel = _with_hash(
        {key: value for key, value in panel.items() if key != "panel_index_sha256"},
        "panel_index_sha256",
    )
    pins = adapter._normalize_pins(graph.pins)
    pins["panel_index_sha256"] = panel["panel_index_sha256"]
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._validate_panel(panel, normalized_pins=pins)


def test_later_source_realized_column_mutation_fails_when_rehashed(
    graph: FixtureGraph,
) -> None:
    source = deepcopy(graph.bodies["later_source"])
    source["source_query"]["realized_columns_selected"] = ["actual_points"]
    source = _with_hash(
        {key: value for key, value in source.items() if key != "freeze_sha256"},
        "freeze_sha256",
    )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._validate_later_source(
            source, normalized_pins=adapter._normalize_pins(graph.pins)
        )


def test_completion_task_catalog_mutation_fails_against_later_source(
    graph: FixtureGraph,
) -> None:
    pins = adapter._normalize_pins(graph.pins)
    later, slates, _, artifacts = adapter._validate_later_source(
        graph.bodies["later_source"], normalized_pins=pins
    )
    completion = deepcopy(graph.bodies["source_completion"])
    task = completion["tasks"][53]
    task["catalog_sha256"] = _hash("substituted catalog")
    completion["tasks"][53] = _with_hash(
        {
            key: value
            for key, value in task.items()
            if key != "task_source_authority_sha256"
        },
        "task_source_authority_sha256",
    )
    completion["task_manifest_sha256"] = _hash(completion["tasks"])
    completion = _with_hash(
        {
            key: value
            for key, value in completion.items()
            if key != "completion_sha256"
        },
        "completion_sha256",
    )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._validate_source_completion(
            completion,
            normalized_pins=pins,
            later_source=later,
            later_slates=slates,
            source_artifacts=artifacts,
        )


def test_namespace_overlap_with_frozen_input_fails(graph: FixtureGraph) -> None:
    pins = deepcopy(graph.pins)
    pins = adapter.ReplayPinsV1(
        **{
            **{
                field: getattr(pins, field)
                for field in adapter.ReplayPinsV1.__dataclass_fields__
            },
            "catalog_namespace": "gs://fixture-source/fixed/",
        }
    )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._derive_pinned_projection_inputs_v1(
            pins=pins,
            adapter_review=graph.review,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
        )


def test_reordered_lane_pins_fail_against_tracked_g0(graph: FixtureGraph) -> None:
    values = {
        field: getattr(graph.pins, field)
        for field in adapter.ReplayPinsV1.__dataclass_fields__
    }
    values["lane_terminal_identities"] = tuple(
        reversed(graph.pins.lane_terminal_identities)
    )
    pins = adapter.ReplayPinsV1(**values)
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._derive_pinned_projection_inputs_v1(
            pins=pins,
            adapter_review=graph.review,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
        )


def test_authoritative_publication_request_fails_before_any_io(
    graph: FixtureGraph,
) -> None:
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._publish_pinned_projection_release_v1(
            pins=graph.pins,
            adapter_review=graph.review,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
            request_authoritative_publication=True,
        )
    assert graph.store.reload_calls == []
    assert graph.store.create_calls == []


def test_projection_publication_creates_54_pairs_release_and_receipt(
    graph: FixtureGraph,
) -> None:
    result = adapter._publish_pinned_projection_release_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
    )
    assert len(graph.store.create_calls) == catalog.TASK_COUNT * 2 + 2
    assert all(call[2] == 0 for call in graph.store.create_calls)
    receipt = result["replay_receipt"]
    assert receipt["task_count"] == catalog.TASK_COUNT
    assert receipt["accepted_panel_index_projection_only"] is True
    assert receipt["fresh_task_or_arm_body_revalidation_performed"] is True
    assert receipt["task_acceptance_bodies_reopened"] is True
    assert receipt["carrier_bodies_reopened"] is True
    assert receipt["task_acceptance_body_count"] == catalog.TASK_COUNT
    assert receipt["carrier_body_count"] == catalog.TASK_COUNT
    assert receipt["world_matrix_bodies_reopened"] is False
    assert receipt["result_object_bodies_reopened"] is False
    assert receipt["execution_manifest_pin_required"] is True
    assert receipt["self_authorizing"] is False
    assert receipt["outcome_columns_read"] == []
    assert all(receipt[field] is False for field in catalog.FALSE_AUTHORITY_FIELDS)


def test_projection_publication_second_run_is_byte_identical_resume(
    graph: FixtureGraph,
) -> None:
    first = adapter._publish_pinned_projection_release_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
    )
    create_count = len(graph.store.create_calls)
    second = adapter._publish_pinned_projection_release_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
    )
    assert len(graph.store.create_calls) == create_count
    assert second["catalog_release_identity"] == first["catalog_release_identity"]
    assert second["replay_receipt_identity"] == first["replay_receipt_identity"]


def test_projection_publication_resumes_after_partial_create_failure(
    graph: FixtureGraph,
) -> None:
    graph.store.fail_create_number = 13
    with pytest.raises(catalog.CorpusR6PlayerCatalogV1Error):
        adapter._publish_pinned_projection_release_v1(
            pins=graph.pins,
            adapter_review=graph.review,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
        )
    assert len(graph.store.create_calls) == 13
    result = adapter._publish_pinned_projection_release_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
    )
    assert result["replay_receipt"]["task_count"] == catalog.TASK_COUNT
    assert len(graph.store.create_calls) == catalog.TASK_COUNT * 2 + 3


def test_projection_publication_rejects_occupied_mutated_child(
    graph: FixtureGraph,
) -> None:
    uri = (
        f"{graph.pins.catalog_namespace}tasks/0000-2023-w01/"
        "catalog-derivation-receipt.json"
    )
    graph.store.seed_raw(uri, b"mutated retained child")
    with pytest.raises(catalog.CorpusR6PlayerCatalogV1Error):
        adapter._publish_pinned_projection_release_v1(
            pins=graph.pins,
            adapter_review=graph.review,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
        )
    assert graph.store.create_calls == []


def test_projection_semantic_failure_occurs_before_first_write(
    graph: FixtureGraph,
) -> None:
    identity = graph.pins.later_source_identity
    graph.store.objects[(str(identity["uri"]), str(identity["generation"]))] = b"{}"
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._publish_pinned_projection_release_v1(
            pins=graph.pins,
            adapter_review=graph.review,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
        )
    assert graph.store.create_calls == []


def test_reopen_receipt_replays_all_54_catalogs(graph: FixtureGraph) -> None:
    published = adapter._publish_pinned_projection_release_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
    )
    reopened = adapter._reopen_pinned_replay_receipt_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        replay_receipt_identity=published["replay_receipt_identity"],
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
    )
    assert reopened["replay_receipt"] == published["replay_receipt"]
    assert len(reopened["catalog_release"]["entries"]) == catalog.TASK_COUNT
    assert reopened["catalog_release"]["publication_authority"] is False


def test_reopen_rejects_receipt_uri_substitution(graph: FixtureGraph) -> None:
    published = adapter._publish_pinned_projection_release_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
    )
    identity = dict(published["replay_receipt_identity"])
    identity["uri"] = "gs://fixture-output/alternate/receipt.json"
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._reopen_pinned_replay_receipt_v1(
            pins=graph.pins,
            adapter_review=graph.review,
            replay_receipt_identity=identity,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
        )


def test_reopen_rejects_coherent_alternate_final_release(
    graph: FixtureGraph,
) -> None:
    published = adapter._publish_pinned_projection_release_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
    )
    release_identity = published["catalog_release_identity"]
    release_raw = graph.store.objects[
        (str(release_identity["uri"]), str(release_identity["generation"]))
    ]
    release = batch.parse_canonical_json_bytes(release_raw, label="release")
    release["release_id"] = "coherent-alternate-release"
    release = _with_hash(
        {key: value for key, value in release.items() if key != "release_sha256"},
        "release_sha256",
    )
    alternate_release_identity = graph.store.seed_json(
        str(release_identity["uri"]), release
    )
    receipt = deepcopy(published["replay_receipt"])
    receipt["catalog_release_identity"] = alternate_release_identity
    receipt["catalog_release_sha256"] = release["release_sha256"]
    receipt = _with_hash(
        {
            key: value
            for key, value in receipt.items()
            if key != "replay_receipt_sha256"
        },
        "replay_receipt_sha256",
    )
    alternate_receipt_identity = graph.store.seed_json(
        f"{graph.pins.catalog_namespace}{adapter.REPLAY_RECEIPT_FILENAME}",
        receipt,
    )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter._reopen_pinned_replay_receipt_v1(
            pins=graph.pins,
            adapter_review=graph.review,
            replay_receipt_identity=alternate_receipt_identity,
            read_tracked=graph.read_tracked,
            transport=graph.store.transport(),
        )


def test_reopen_pinned_old_receipt_ignores_new_latest_receipt(
    graph: FixtureGraph,
) -> None:
    published = adapter._publish_pinned_projection_release_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
    )
    graph.store.seed_raw(
        str(published["replay_receipt_identity"]["uri"]), b"new latest"
    )
    reopened = adapter._reopen_pinned_replay_receipt_v1(
        pins=graph.pins,
        adapter_review=graph.review,
        replay_receipt_identity=published["replay_receipt_identity"],
        read_tracked=graph.read_tracked,
        transport=graph.store.transport(),
    )
    assert reopened["replay_receipt"] == published["replay_receipt"]


def test_production_cli_status_is_closed_and_outcome_blind(capsys) -> None:
    assert adapter.main(["status"]) == 0
    assert capsys.readouterr().out == (
        '{"adapter_review_lock_path":"'
        + adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH
        + '","default_state":"parked","explicit_execute_gate_required":true,'
        '"final_release_lock_path":"'
        + adapter.FIXED_FINAL_RELEASE_LOCK_PATH
        + '","final_release_lock_required":true,"r6_source_authority":false,'
        '"task0_smoke_attempt_path":"'
        + adapter.FIXED_TASK0_SMOKE_ATTEMPT_PATH
        + '",'
        '"task0_smoke_receipt_path":"'
        + adapter.FIXED_TASK0_SMOKE_RECEIPT_PATH
        + '","uses_realized_outcomes":false}\n'
    )


@pytest.mark.parametrize(
    "argv",
    [
        [
            "build-preliminary-lock",
            "--output",
            adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH,
            "--focused-test-passed",
            "--static-review-approved",
        ],
        [
            "build-final-lock",
            "--output",
            adapter.FIXED_FINAL_RELEASE_LOCK_PATH,
            "--static-review-approved",
            "--publication-approved",
        ],
    ],
)
def test_lock_builder_cli_is_parked_without_explicit_build(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        adapter.main(argv)


def test_preliminary_lock_cli_uses_fixed_noncloud_builder(
    monkeypatch: pytest.MonkeyPatch, capsys,
) -> None:
    calls: list[dict[str, object]] = []

    def reviewed_builder(**kwargs) -> dict[str, object]:
        calls.append(kwargs)
        return {"lock": "preliminary", "uses_realized_outcomes": False}

    monkeypatch.setattr(
        adapter,
        "write_preliminary_adapter_review_lock_production_v1",
        reviewed_builder,
    )
    assert adapter.main(list(adapter.FIXED_PRELIMINARY_LOCK_BUILD_COMMAND[3:])) == 0
    assert calls == [{
        "output_relative_path": adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH,
        "focused_test_passed": True,
        "independent_static_review_passed": True,
    }]
    assert capsys.readouterr().out == (
        '{"lock":"preliminary","uses_realized_outcomes":false}\n'
    )


def test_final_lock_cli_uses_fixed_noncloud_builder(
    monkeypatch: pytest.MonkeyPatch, capsys,
) -> None:
    calls: list[dict[str, object]] = []

    def reviewed_builder(**kwargs) -> dict[str, object]:
        calls.append(kwargs)
        return {"lock": "final", "uses_realized_outcomes": False}

    monkeypatch.setattr(
        adapter, "write_final_release_lock_production_v1", reviewed_builder
    )
    assert adapter.main(list(adapter.FIXED_FINAL_LOCK_BUILD_COMMAND[3:])) == 0
    assert calls == [{
        "output_relative_path": adapter.FIXED_FINAL_RELEASE_LOCK_PATH,
        "independent_static_review_passed": True,
        "publication_approved": True,
    }]
    assert capsys.readouterr().out == (
        '{"lock":"final","uses_realized_outcomes":false}\n'
    )


def test_production_cli_requires_explicit_execute_before_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def forbidden_entry() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"unexpected": True}

    monkeypatch.setattr(
        adapter,
        "run_reviewed_fixed_g0_projection_release_production_v1",
        forbidden_entry,
    )
    with pytest.raises(adapter.CorpusR6FixedG0AdapterV1Error):
        adapter.main(["publish-projection"])
    assert calls == 0


def test_task0_smoke_cli_requires_exact_preflight_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def forbidden_entry() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"unexpected": True}

    monkeypatch.setattr(
        adapter, "run_task0_real_artifact_smoke_production_v1", forbidden_entry
    )
    with pytest.raises(SystemExit):
        adapter.main(["preflight-task0"])
    assert calls == 0


def test_task0_smoke_cli_uses_only_fixed_production_entry(
    monkeypatch: pytest.MonkeyPatch, capsys,
) -> None:
    calls = 0

    def reviewed_entry() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "passed": True,
            "gcs_publication_count": 0,
            "uses_realized_outcomes": False,
        }

    monkeypatch.setattr(
        adapter, "run_task0_real_artifact_smoke_production_v1", reviewed_entry
    )
    assert adapter.main(["preflight-task0", "--preflight"]) == 0
    assert calls == 1
    assert capsys.readouterr().out == (
        '{"gcs_publication_count":0,"passed":true,'
        '"uses_realized_outcomes":false}\n'
    )


def test_production_cli_execute_uses_only_closed_reviewed_entry(
    monkeypatch: pytest.MonkeyPatch, capsys,
) -> None:
    calls = 0

    def reviewed_entry() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "projection_only": True,
            "uses_realized_outcomes": False,
        }

    monkeypatch.setattr(
        adapter,
        "run_reviewed_fixed_g0_projection_release_production_v1",
        reviewed_entry,
    )
    assert adapter.main(["publish-projection", "--execute"]) == 0
    assert calls == 1
    assert capsys.readouterr().out == (
        '{"projection_only":true,"uses_realized_outcomes":false}\n'
    )
