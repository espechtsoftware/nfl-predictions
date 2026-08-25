from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from nfl_dfs.research import corpus_core_v1_catalog_materializer as catalog_store
from nfl_dfs.research import corpus_core_v1_outcome_supply as supply
from nfl_dfs.research import corpus_realized_outcome_transport as registered
from nfl_dfs.research import lr8_label_score_map as shared


ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    path = ROOT / "scripts/run_core_v1_outcome_supply.py"
    spec = importlib.util.spec_from_file_location(
        "run_core_v1_outcome_supply_test", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


class NotFound(Exception):
    pass


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
        self.time_created: datetime | None = None

    @property
    def _key(self) -> tuple[str, str]:
        return self._bucket, self.name

    def _current_generation(self) -> int:
        versions = self._client.objects.get(self._key, {})
        if not versions:
            raise NotFound("object is absent")
        return max(versions)

    def reload(self, *, if_generation_match: int | None = None) -> None:
        if self.generation is None:
            generation = self._current_generation()
            self._client.current_resolutions.append(self._key)
        else:
            generation = int(self.generation)
        if if_generation_match is not None and generation != if_generation_match:
            raise RuntimeError("generation precondition failed")
        if generation not in self._client.objects.get(self._key, {}):
            raise NotFound("generation is absent")
        self.generation = generation
        self.time_created = datetime(2026, 8, 25, tzinfo=timezone.utc) + timedelta(
            microseconds=generation
        )
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
        if self._client.ambiguous_upload:
            self._client.ambiguous_upload = False
            raise RuntimeError("response lost after upload")


class _FakeBucket:
    def __init__(self, client: "_FakeGCSClient", name: str) -> None:
        self._client = client
        self._name = name

    def blob(self, name: str, generation: int | None = None) -> _FakeBlob:
        return _FakeBlob(self._client, self._name, name, generation)


class _FakeGCSClient:
    """Known-name and generation-only fake; deliberately has no list API."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[int, bytes]] = {}
        self.next_generation = 100
        self.reload_generations: list[int] = []
        self.download_generations: list[int] = []
        self.current_resolutions: list[tuple[str, str]] = []
        self.ambiguous_upload = False

    def bucket(self, name: str) -> _FakeBucket:
        return _FakeBucket(self, name)

    def seed(self, uri: str, raw: bytes, *, generation: int) -> dict[str, object]:
        bucket, name = uri.removeprefix("gs://").split("/", 1)
        self.objects.setdefault((bucket, name), {})[generation] = raw
        return _identity(uri, generation, raw)


def _identity(uri: str, generation: int, raw: bytes | None = None) -> dict[str, object]:
    body = raw if raw is not None else f"{uri}:{generation}".encode()
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(body).hexdigest(),
        "bytes": len(body),
    }


def _config() -> supply.CoreOutcomeSupplyConfig:
    return supply.CoreOutcomeSupplyConfig(
        run_id="core-v1-fixture",
        job="outcome-job",
        code_sha="a" * 40,
        image=f"fixture@sha256:{'b' * 64}",
        enabled=True,
    )


def _argv() -> list[str]:
    return [
        "--run-id",
        "core-v1-fixture",
        "--job",
        "outcome-job",
        "--code-sha",
        "a" * 40,
        "--image",
        f"fixture@sha256:{'b' * 64}",
        "--catalog-root-uri",
        (
            f"gs://{supply.OUTPUT_BUCKET}/research/core-v1-fixture/"
            f"{catalog_store.ROOT_FILENAME}"
        ),
    ]


def test_known_name_resolution_and_publication_are_generation_pinned() -> None:
    client = _FakeGCSClient()
    store = cli.GenerationPinnedGCS(client)
    known_uri = "gs://fixture-bucket/known.json"
    known_raw = b'{"known":true}'
    identity = client.seed(known_uri, known_raw, generation=17)

    resolved = store.resolve_required(known_uri)
    assert {
        key: resolved.receipt[key]
        for key in ("uri", "generation", "sha256", "bytes")
    } == identity
    assert resolved.reopened_raw == known_raw
    assert client.download_generations == [17]
    assert store.read_known("gs://fixture-bucket/absent.json") is None

    output_uri = "gs://fixture-bucket/output.json"
    output_raw = b'{"output":true}'
    client.ambiguous_upload = True
    ambiguous = store.publish(output_uri, output_raw)
    recovered = store.publish(output_uri, output_raw)
    assert ambiguous.created is False
    assert recovered.created is False
    assert ambiguous.receipt == recovered.receipt
    with pytest.raises(cli.CoreV1OutcomeRunnerError, match="object differs"):
        store.publish(output_uri, b'{"output":false}')


def test_cloud_reopens_catalog_root_outputs_without_touching_released_lease(
    monkeypatch,
) -> None:
    client = _FakeGCSClient()
    config = _config()
    root_uri = (
        f"gs://{supply.OUTPUT_BUCKET}/research/core-v1-fixture/"
        f"{catalog_store.ROOT_FILENAME}"
    )
    root_raw = b'{"root":true}'
    root_identity = client.seed(root_uri, root_raw, generation=11)
    catalog_uri = root_uri.removesuffix(catalog_store.ROOT_FILENAME) + "catalog.json"
    catalog_raw = b'{"catalog":true}'
    catalog_identity = client.seed(catalog_uri, catalog_raw, generation=12)
    freeze_uri = "gs://fixture-bucket/later-source-freeze.json"
    freeze_raw = b'{"source":"frozen"}'
    freeze_identity = client.seed(freeze_uri, freeze_raw, generation=13)
    catalog = {"later_source_freeze_identity": freeze_identity}
    authority = catalog_store.ReopenedShardedCoreV1Catalog(
        root={},
        root_identity=root_identity,
        catalog_identity=catalog_identity,
        shard_identities=tuple(),
        logical_catalog=catalog,
    )

    def reopen_catalog(*, root_identity, read_exact):
        assert root_identity == authority.root_identity
        assert read_exact(root_identity) == root_raw
        assert read_exact(catalog_identity) == catalog_raw
        return authority

    monkeypatch.setattr(
        cli.catalog_store,
        "reopen_sharded_core_v1_catalog_authority",
        reopen_catalog,
    )
    names = {
        "attempt": f"{config.output_root}/read-attempt.json",
        "source": f"{config.output_root}/player-score-source.json",
        "snapshot": f"{config.output_root}/player-outcome-snapshot.json",
        "completion": f"{config.output_root}/completion.json",
    }
    output_identities = {
        label: client.seed(uri, b'{"closed":true}', generation=20 + ordinal)
        for ordinal, (label, uri) in enumerate(names.items())
    }
    lease_identity = _identity(
        shared.adapter.HISTORICAL_OUTCOME_LEASE_URI, 99
    )

    def completed_supply(**kwargs):
        assert kwargs["catalog"] == catalog
        assert kwargs["catalog_identity"] == catalog_identity
        assert kwargs["source_freeze"] == {"source": "frozen"}
        assert kwargs["source_freeze_identity"] == freeze_identity
        for label, uri in names.items():
            reopened = kwargs["read_known"](uri)
            assert reopened is not None
            assert {
                key: reopened.receipt[key]
                for key in ("uri", "generation", "sha256", "bytes")
            } == output_identities[label]
        return supply.CoreOutcomeSupply(
            attempt={
                "historical_outcome_lease": {
                    "object_receipt": {**lease_identity, "create_only": True}
                }
            },
            attempt_identity=output_identities["attempt"],
            player_source={
                "query_job_id": "fixed-job",
                "query_job_disposition": "created",
            },
            player_source_identity=output_identities["source"],
            outcome_snapshot={},
            outcome_snapshot_identity=output_identities["snapshot"],
            completion={"outcome_key_count": 7},
            completion_identity=output_identities["completion"],
        )

    monkeypatch.setattr(
        cli.supply, "supply_core_v1_outcome_snapshot", completed_supply
    )
    result = cli.run_cloud(
        config=config,
        catalog_root_uri=root_uri,
        storage_client=client,
        bq_client=object(),
    )

    assert result.catalog_root_identity == root_identity
    assert result.catalog_identity == catalog_identity
    assert result.source_freeze_identity == freeze_identity
    assert result.historical_lease_identity == lease_identity
    lease_parts = shared.adapter.HISTORICAL_OUTCOME_LEASE_URI.removeprefix(
        "gs://"
    ).split("/", 1)
    assert tuple(lease_parts) not in client.current_resolutions


class _FakeJob:
    def __init__(self, spec: registered.QuerySpec, parameters: list[object]) -> None:
        self.job_id = spec.job_id
        self.location = spec.location
        self.query = spec.sql
        self.query_parameters = parameters
        self.use_legacy_sql = False
        self.use_query_cache = False
        self.cache_hit = False
        self.error_result = None
        self.total_bytes_processed = 123
        self.created = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)
        self.started = self.created + timedelta(seconds=1)
        self.ended = self.started + timedelta(seconds=1)
        self._rows = ({"value": 1},)

    def result(self):
        return self._rows


class _FakeBQClient:
    def __init__(self, *, ambiguous: bool = False) -> None:
        self.job: _FakeJob | None = None
        self.ambiguous = ambiguous
        self.query_calls = 0
        self.query_kwargs: dict[str, object] | None = None

    def get_job(self, job_id: str, *, location: str):
        if self.job is None:
            raise NotFound("job is absent")
        assert self.job.job_id == job_id
        assert self.job.location == location
        return self.job

    def query(self, sql: str, **kwargs):
        self.query_calls += 1
        self.query_kwargs = dict(kwargs)
        config = kwargs["job_config"]
        spec = _query_spec()
        assert sql == spec.sql
        self.job = _FakeJob(spec, list(config.query_parameters))
        if self.ambiguous:
            raise RuntimeError("query response lost after create")
        return self.job


def _query_spec() -> registered.QuerySpec:
    parameters = (
        shared.QueryParameter(
            "source_snapshot_at",
            "TIMESTAMP",
            datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
        ),
        shared.QueryParameter("target_seasons", "INT64", [2023], True),
    )
    return registered.QuerySpec(
        sql="SELECT @source_snapshot_at, season FROM fixture",
        parameters=parameters,
        job_id="corpus_realized_core_v1_fixture_deadbeef1234",
        location="US",
        sql_sha256=sha256(b"fixture sql").hexdigest(),
        parameters_sha256=sha256(b"fixture parameters").hexdigest(),
        union_keys_sha256=sha256(b"fixture keys").hexdigest(),
    )


def test_bigquery_fixed_job_is_created_once_and_exactly_recovered() -> None:
    spec = _query_spec()
    client = _FakeBQClient()

    created = cli._get_or_create_query(client, spec)
    recovered = cli._get_or_create_query(client, spec)

    assert created.disposition == "created"
    assert recovered.disposition == "recovered"
    assert created.result.rows == recovered.result.rows == ({"value": 1},)
    assert client.query_calls == 1
    assert client.query_kwargs is not None
    assert client.query_kwargs["job_id"] == spec.job_id
    assert client.query_kwargs["location"] == spec.location
    assert client.query_kwargs["job_retry"] is None
    job_config = client.query_kwargs["job_config"]
    assert job_config.use_query_cache is False
    assert job_config.use_legacy_sql is False

    assert client.job is not None
    client.job.query = "SELECT forged"
    with pytest.raises(
        cli.CoreV1OutcomeRunnerError,
        match="job configuration differs",
    ):
        cli._get_or_create_query(client, spec)


def test_ambiguous_bigquery_create_recovers_without_second_query() -> None:
    client = _FakeBQClient(ambiguous=True)

    recovered = cli._get_or_create_query(client, _query_spec())

    assert recovered.disposition == "recovered"
    assert client.query_calls == 1


def test_cli_is_default_off_and_success_stdout_is_receipt_only(
    monkeypatch, capsys,
) -> None:
    argv = _argv()
    with pytest.raises(cli.CoreV1OutcomeRunnerError, match="required explicitly"):
        cli.main(argv, environ={}, storage_client=object(), bq_client=object())
    assert capsys.readouterr().out == ""

    identities = {
        label: _identity(f"gs://fixture-bucket/{label}.json", index)
        for index, label in enumerate(
            ("root", "catalog", "freeze", "lease", "attempt", "source", "snapshot", "completion"),
            start=1,
        )
    }
    supplied = supply.CoreOutcomeSupply(
        attempt={"rows": ["must-not-reach-stdout"]},
        attempt_identity=identities["attempt"],
        player_source={
            "query_job_id": "fixed-job",
            "query_job_disposition": "recovered",
            "rows": ["must-not-reach-stdout"],
        },
        player_source_identity=identities["source"],
        outcome_snapshot={"rows": ["must-not-reach-stdout"]},
        outcome_snapshot_identity=identities["snapshot"],
        completion={"outcome_key_count": 123},
        completion_identity=identities["completion"],
    )
    cloud = cli.CoreOutcomeCloudResult(
        supply=supplied,
        catalog_root_identity=identities["root"],
        catalog_identity=identities["catalog"],
        source_freeze_identity=identities["freeze"],
        historical_lease_identity=identities["lease"],
    )
    monkeypatch.setattr(cli, "run_cloud", lambda **_kwargs: cloud)

    assert cli.main(
        ["--execute", *_argv()],
        environ={cli.ENABLED_ENV: "1"},
        storage_client=object(),
        bq_client=object(),
    ) == 0
    raw = capsys.readouterr().out
    assert raw.count("\n") == 0
    receipt = json.loads(raw)
    retained = receipt.pop("cli_receipt_sha256")
    assert retained == supply.canonical_sha256(receipt)
    assert receipt["schema_version"] == cli.RECEIPT_SCHEMA
    assert receipt["outcome_key_count"] == 123
    assert "rows" not in receipt
    assert "outcome_snapshot" not in receipt
    assert receipt["decision_authority"] is False
