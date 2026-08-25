from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path

import pytest

from nfl_dfs.research import corpus_core_v1_catalog_materializer as catalog_store
from nfl_dfs.research import corpus_core_v1_grade_publisher as grade_store


ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    path = ROOT / "scripts/run_core_v1_grade_cloud.py"
    spec = importlib.util.spec_from_file_location(
        "run_core_v1_grade_cloud_test", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys_modules_before = set(__import__("sys").modules)
    __import__("sys").modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if spec.name not in sys_modules_before:
            __import__("sys").modules.pop(spec.name, None)
    return module


cli = _load_cli()


class _FakeBlob:
    def __init__(
        self,
        client: "_FakeGCSClient",
        bucket: str,
        name: str,
        generation: int | None,
    ) -> None:
        self._client = client
        self._bucket = bucket
        self.name = name
        self.generation = generation

    @property
    def _key(self) -> tuple[str, str]:
        return self._bucket, self.name

    def _current_generation(self) -> int:
        versions = self._client.objects.get(self._key, {})
        if not versions:
            raise RuntimeError("not found")
        return max(versions)

    def reload(self, *, if_generation_match: int | None = None) -> None:
        generation = (
            self._current_generation()
            if self.generation is None
            else int(self.generation)
        )
        if if_generation_match is not None and generation != if_generation_match:
            raise RuntimeError("generation precondition failed")
        if generation not in self._client.objects.get(self._key, {}):
            raise RuntimeError("generation not found")
        self.generation = generation
        self._client.reload_generations.append(generation)

    def download_as_bytes(
        self, *, if_generation_match: int | None = None,
    ) -> bytes:
        if self.generation is None:
            raise AssertionError("download was not generation-pinned")
        generation = int(self.generation)
        if if_generation_match != generation:
            raise AssertionError("download generation precondition differs")
        self._client.download_generations.append(generation)
        return self._client.objects[self._key][generation]

    def upload_from_string(
        self,
        raw: bytes,
        *,
        content_type: str,
        if_generation_match: int,
    ) -> None:
        assert content_type == "application/json"
        assert if_generation_match == 0
        if self._client.objects.get(self._key):
            raise RuntimeError("precondition failed")
        generation = self._client.next_generation
        self._client.next_generation += 1
        self._client.objects[self._key] = {generation: raw}
        self.generation = generation


class _FakeBucket:
    def __init__(self, client: "_FakeGCSClient", name: str) -> None:
        self._client = client
        self._name = name

    def blob(self, name: str, generation: int | None = None) -> _FakeBlob:
        return _FakeBlob(self._client, self._name, name, generation)


class _FakeGCSClient:
    """Known-name operations only; deliberately provides no list API."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[int, bytes]] = {}
        self.next_generation = 10_000
        self.reload_generations: list[int] = []
        self.download_generations: list[int] = []

    def bucket(self, name: str) -> _FakeBucket:
        return _FakeBucket(self, name)

    def seed_raw(
        self, uri: str, raw: bytes, *, generation: int,
    ) -> dict[str, object]:
        bucket, name = uri.removeprefix("gs://").split("/", 1)
        self.objects.setdefault((bucket, name), {})[generation] = raw
        return {
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    def seed_json(
        self, uri: str, value: object, *, generation: int,
    ) -> dict[str, object]:
        return self.seed_raw(
            uri,
            grade_store.canonical_json_bytes(value),
            generation=generation,
        )


def _identity(uri: str, *, generation: int = 1) -> dict[str, object]:
    raw = f"{uri}:{generation}".encode()
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _receipt(captured: str, *, schema: str) -> dict[str, object]:
    assert captured.count("\n") == 0
    value = json.loads(captured)
    assert value["schema_version"] == schema
    retained = value.pop("cli_receipt_sha256")
    assert retained == grade_store.canonical_sha256(value)
    value["cli_receipt_sha256"] = retained
    return value


def _outcome_key() -> dict[str, object]:
    return {
        "source_ordinal": 0,
        "season": 2023,
        "week": 1,
        "slate_id": "2023-w01",
        "source_kind": "skill",
        "source_key": "player-1",
        "player_id": "player-1",
    }


def _completed_outcome_objects(
    client: _FakeGCSClient, *, run_id: str,
) -> dict[str, object]:
    root = (
        f"gs://{cli.supply.OUTPUT_BUCKET}/"
        f"{cli.supply.OUTPUT_NAMESPACE}/{run_id}"
    )
    attempt = {
        "outcome_keys": [_outcome_key()],
        "historical_outcome_lease": {
            "body": {
                "job": "core-outcome-fixture",
                "code_sha": "1" * 40,
                "image": f"fixture@sha256:{'2' * 64}",
            }
        },
    }
    attempt_identity = client.seed_json(
        f"{root}/read-attempt.json", attempt, generation=101
    )
    player_source = {
        "attempt": attempt,
        "attempt_identity": attempt_identity,
    }
    source_identity = client.seed_json(
        f"{root}/player-score-source.json", player_source, generation=102
    )
    outcome_snapshot = {"source_identity": source_identity}
    snapshot_identity = client.seed_json(
        f"{root}/player-outcome-snapshot.json",
        outcome_snapshot,
        generation=103,
    )
    completion = {
        "run_id": run_id,
        "attempt_identity": attempt_identity,
        "player_source_identity": source_identity,
        "outcome_snapshot_identity": snapshot_identity,
        "one_historical_outcome_read": True,
    }
    completion_identity = client.seed_json(
        f"{root}/completion.json", completion, generation=104
    )
    return {
        "attempt": attempt,
        "attempt_identity": attempt_identity,
        "player_source": player_source,
        "player_source_identity": source_identity,
        "outcome_snapshot": outcome_snapshot,
        "outcome_snapshot_identity": snapshot_identity,
        "completion": completion,
        "completion_identity": completion_identity,
    }


def _coverage() -> dict[str, object]:
    return {
        "source_slate_count": 54,
        "book_cell_count": 1_944,
        "weekly_contrast_cell_count": 7_290,
        "contrast_summary_count": 135,
        "unique_union_roster_membership_count": 4_320,
        "union_roster_sum_operation_count": 4_320,
        "actual_player_outcome_row_count": 5_000,
        "every_unique_union_roster_scored_exactly_once_per_slate": True,
        "all_registered_contrasts_reported_regardless_of_sign": True,
        "complete": True,
    }


def _contest_metrics() -> dict[str, object]:
    return {
        "availability": "unavailable",
        "reason": "full_field_standings_and_payout_ladder_not_supplied",
        "full_field_standings_identity": None,
        "payout_ladder_identity": None,
        "rank": None,
        "roi_micro_usd": None,
    }


def test_known_name_gcs_resolves_current_then_reads_exact_without_listing() -> None:
    client = _FakeGCSClient()
    raw = b'{"known":true}'
    uri = "gs://fixture-bucket/known/completion.json"
    expected = client.seed_raw(uri, raw, generation=17)
    store = cli.GenerationPinnedGCS(client)

    identity, reopened = store.resolve_current_exact(uri)

    assert identity == expected
    assert reopened == raw
    assert client.reload_generations == [17, 17, 17]
    assert client.download_generations == [17, 17]
    assert not hasattr(client, "list_blobs")


def test_grade_cli_is_default_off_before_storage_access(capsys) -> None:
    argv = [
        "grade",
        "--grade-run-id",
        "core-grade-fixture",
        "--max-logical-grade-bytes",
        "1000",
        "--catalog-root-uri",
        "gs://fixture-bucket/catalog-root.json",
        "--outcome-completion-uri",
        "gs://fixture-bucket/completion.json",
    ]
    with pytest.raises(cli.CoreV1GradeCloudError, match="required explicitly"):
        cli.main(argv, environ={}, storage_client=object())
    assert capsys.readouterr().out == ""


def test_completed_outcome_reopen_binds_all_exact_predecessors(
    monkeypatch,
) -> None:
    client = _FakeGCSClient()
    objects = _completed_outcome_objects(
        client, run_id="core-outcome-fixture"
    )
    store = cli.GenerationPinnedGCS(client)
    catalog = {"catalog_sha256": "a" * 64}
    catalog_identity = _identity("gs://fixture-bucket/catalog.json")
    calls: list[str] = []

    def _validate_source(value, *, identity, **_kwargs):
        calls.append("source")
        return value, identity, []

    def _validate_snapshot(value, *, identity, **_kwargs):
        calls.append("snapshot")
        return value, identity, {}

    def _validate_completion(value, **_kwargs):
        calls.append("completion")
        return value

    monkeypatch.setattr(
        cli.outcome, "validate_core_player_source", _validate_source
    )
    monkeypatch.setattr(
        cli.outcome, "validate_core_outcome_snapshot", _validate_snapshot
    )
    monkeypatch.setattr(
        cli.supply, "validate_core_outcome_completion", _validate_completion
    )

    reopened = cli._reopen_completed_outcomes(  # noqa: SLF001
        completion_identity=objects["completion_identity"],
        catalog=catalog,
        catalog_identity=catalog_identity,
        store=store,
    )

    assert calls == ["source", "snapshot", "completion"]
    assert reopened.attempt_identity == objects["attempt_identity"]
    assert reopened.player_source_identity == objects["player_source_identity"]
    assert reopened.outcome_snapshot_identity == objects[
        "outcome_snapshot_identity"
    ]
    assert len(reopened.outcome_keys) == 1
    assert reopened.outcome_keys[0].player_id == "player-1"


def test_completed_outcome_reopen_rejects_external_attempt_drift(
    monkeypatch,
) -> None:
    client = _FakeGCSClient()
    objects = _completed_outcome_objects(
        client, run_id="core-outcome-drift"
    )
    source_identity = objects["player_source_identity"]
    bucket, name = str(source_identity["uri"]).removeprefix("gs://").split("/", 1)
    drifted = {
        "attempt": {"outcome_keys": [{**_outcome_key(), "player_id": "other"}]},
        "attempt_identity": objects["attempt_identity"],
    }
    client.objects[(bucket, name)][int(source_identity["generation"])] = (
        grade_store.canonical_json_bytes(drifted)
    )
    source_identity["sha256"] = sha256(
        grade_store.canonical_json_bytes(drifted)
    ).hexdigest()
    source_identity["bytes"] = len(grade_store.canonical_json_bytes(drifted))
    completion = objects["completion"]
    completion["player_source_identity"] = source_identity
    completion_identity = objects["completion_identity"]
    completion_bucket, completion_name = str(
        completion_identity["uri"]
    ).removeprefix("gs://").split("/", 1)
    completion_raw = grade_store.canonical_json_bytes(completion)
    client.objects[(completion_bucket, completion_name)][
        int(completion_identity["generation"])
    ] = completion_raw
    completion_identity["sha256"] = sha256(completion_raw).hexdigest()
    completion_identity["bytes"] = len(completion_raw)

    with pytest.raises(
        cli.CoreV1GradeCloudError,
        match="differs from its exact attempt",
    ):
        cli._reopen_completed_outcomes(  # noqa: SLF001
            completion_identity=completion_identity,
            catalog={"catalog_sha256": "a" * 64},
            catalog_identity=_identity("gs://fixture-bucket/catalog.json"),
            store=cli.GenerationPinnedGCS(client),
        )


def test_grade_and_reopen_commands_publish_fixed_completion_receipts(
    monkeypatch, capsys,
) -> None:
    client = _FakeGCSClient()
    grade_run_id = "core-grade-fixture"
    catalog_root_uri = "gs://fixture-bucket/catalog/catalog-root.json"
    outcome_completion_uri = (
        "gs://fixture-bucket/outcomes/completion.json"
    )
    catalog_root_identity = client.seed_raw(
        catalog_root_uri, b'{"root":true}', generation=201
    )
    input_completion_identity = client.seed_raw(
        outcome_completion_uri, b'{"completion":true}', generation=202
    )
    catalog_identity = _identity(
        "gs://fixture-bucket/catalog/catalog.json", generation=203
    )
    catalog_authority = catalog_store.ReopenedShardedCoreV1Catalog(
        root={},
        root_identity=catalog_root_identity,
        catalog_identity=catalog_identity,
        shard_identities=tuple(),
        logical_catalog={"catalog_sha256": "a" * 64},
    )
    outcome_identity = _identity(
        "gs://fixture-bucket/outcomes/player-outcome-snapshot.json",
        generation=204,
    )
    source_identity = _identity(
        "gs://fixture-bucket/outcomes/player-score-source.json",
        generation=205,
    )
    completed = cli.ReopenedCompletedOutcomes(
        completion={"one_historical_outcome_read": True},
        completion_identity=input_completion_identity,
        attempt_identity=_identity(
            "gs://fixture-bucket/outcomes/read-attempt.json", generation=206
        ),
        player_source={"source": True},
        player_source_identity=source_identity,
        outcome_snapshot={"snapshot": True},
        outcome_snapshot_identity=outcome_identity,
        outcome_keys=(),
    )
    output_prefix = cli._grade_output_prefix(grade_run_id)  # noqa: SLF001
    grade_root_identity = _identity(
        output_prefix + grade_store.ROOT_FILENAME, generation=207
    )
    summary_identity = _identity(
        output_prefix + grade_store.SUMMARY_FILENAME, generation=208
    )
    slate_identities = tuple(
        _identity(
            output_prefix + f"slate-grades/{ordinal:02d}.json",
            generation=300 + ordinal,
        )
        for ordinal in range(54)
    )
    published = grade_store.PublishedShardedCoreV1Grade(
        root={},
        root_identity=grade_root_identity,
        slate_shard_identities=slate_identities,
        summary_identity=summary_identity,
        created_slate_shard_count=54,
        recovered_slate_shard_count=0,
        summary_created=True,
        root_created=True,
    )
    reopened_grade = {
        "realized_grade_sha256": "d" * 64,
        "catalog_authority": {
            "catalog_sha256": "a" * 64,
            "catalog_identity": catalog_identity,
        },
        "actual_player_outcome_authority": {
            "outcome_snapshot_sha256": "b" * 64,
            "outcome_snapshot_identity": outcome_identity,
            "source_identity": source_identity,
        },
        "coverage": _coverage(),
        "contest_metrics": _contest_metrics(),
    }
    calls: list[str] = []

    def _catalog_reopen(**kwargs):
        calls.append("catalog")
        assert kwargs["root_identity"] == catalog_root_identity
        return catalog_authority

    def _outcome_reopen(**kwargs):
        calls.append("outcomes")
        assert kwargs["completion_identity"] == input_completion_identity
        return completed

    def _grade_publish(**kwargs):
        calls.append("grade")
        assert kwargs["output_prefix"] == output_prefix
        assert kwargs["max_logical_grade_bytes"] == 100_000_000
        return published

    def _grade_reopen(**_kwargs):
        calls.append("reopen")
        return reopened_grade

    monkeypatch.setattr(
        cli.catalog_store,
        "reopen_sharded_core_v1_catalog_authority",
        _catalog_reopen,
    )
    monkeypatch.setattr(cli, "_reopen_completed_outcomes", _outcome_reopen)
    monkeypatch.setattr(
        cli.grade_store, "grade_and_publish_sharded_core_v1", _grade_publish
    )
    monkeypatch.setattr(
        cli.grade_store,
        "reopen_sharded_core_v1_realized_grade",
        _grade_reopen,
    )
    grade_argv = [
        "grade",
        "--execute",
        "--grade-run-id",
        grade_run_id,
        "--max-logical-grade-bytes",
        "100000000",
        "--catalog-root-uri",
        catalog_root_uri,
        "--outcome-completion-uri",
        outcome_completion_uri,
    ]
    assert cli.main(
        grade_argv,
        environ={cli.ENABLED_ENV: "1"},
        storage_client=client,
    ) == 0
    receipt = _receipt(
        capsys.readouterr().out, schema=cli.GRADE_RECEIPT_SCHEMA
    )
    assert calls == ["catalog", "outcomes", "grade", "reopen"]
    assert receipt["grade_completion_identity"]["uri"] == (
        cli._grade_completion_uri(grade_run_id)  # noqa: SLF001
    )
    assert receipt["grade_completion_created"] is True
    assert "slate_grades" not in receipt
    assert "weekly_contrasts" not in receipt
    assert "player_source" not in receipt

    calls.clear()
    assert cli.main(
        grade_argv,
        environ={cli.ENABLED_ENV: "1"},
        storage_client=client,
    ) == 0
    recovered_receipt = _receipt(
        capsys.readouterr().out, schema=cli.GRADE_RECEIPT_SCHEMA
    )
    assert calls == ["catalog", "outcomes", "grade", "reopen"]
    assert recovered_receipt["grade_completion_created"] is False
    assert recovered_receipt["grade_completion_identity"] == receipt[
        "grade_completion_identity"
    ]

    calls.clear()
    assert cli.main(
        ["reopen", "--execute", "--grade-run-id", grade_run_id],
        environ={cli.ENABLED_ENV: "1"},
        storage_client=client,
    ) == 0
    reopened_receipt = _receipt(
        capsys.readouterr().out, schema=cli.REOPEN_RECEIPT_SCHEMA
    )
    assert calls == ["catalog", "outcomes", "reopen"]
    assert reopened_receipt["grade_completion_identity"] == receipt[
        "grade_completion_identity"
    ]
    assert reopened_receipt["grade_root_identity"] == grade_root_identity
