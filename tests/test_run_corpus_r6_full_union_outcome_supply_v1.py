"""Focused offline tests for the R6 full-union cloud transport wrapper."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_outcome_supply_v1 as supply
from nfl_dfs.research import corpus_realized_outcome_transport as registered
from nfl_dfs.research import lr8_label_score_map as shared


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_MODULE_SHA = "5" * 64
SNAPSHOT_CLI_SHA = "6" * 64
SNAPSHOT_TEST_SHA = "7" * 64
SNAPSHOT_CLI_TEST_SHA = "8" * 64


def _load_cli():
    path = ROOT / "scripts/run_corpus_r6_full_union_outcome_supply_v1.py"
    spec = importlib.util.spec_from_file_location(
        "run_corpus_r6_full_union_outcome_supply_v1_test", path
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
        self.time_created = datetime(2026, 8, 26, tzinfo=timezone.utc) + timedelta(
            microseconds=generation
        )

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
        self.download_generations: list[int] = []
        self.current_resolutions: list[tuple[str, str]] = []
        self.ambiguous_upload = False

    def bucket(self, name: str) -> _FakeBucket:
        return _FakeBucket(self, name)

    def seed(self, uri: str, raw: bytes, *, generation: int) -> dict[str, object]:
        bucket, name = uri.removeprefix("gs://").split("/", 1)
        self.objects.setdefault((bucket, name), {})[generation] = raw
        return _identity(uri, generation, raw)


def _identity(
    uri: str, generation: int, raw: bytes | None = None,
) -> dict[str, object]:
    body = raw if raw is not None else f"{uri}:{generation}".encode()
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(body).hexdigest(),
        "bytes": len(body),
    }


def _root_identity(raw: bytes | None = None) -> dict[str, object]:
    return _identity(
        (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-full-union-freezes/fixture/panel-freeze.json"
        ),
        11,
        raw,
    )


def _lease_identity(
    generation: int = 99, raw: bytes | None = None,
) -> dict[str, object]:
    return _identity(
        shared.adapter.HISTORICAL_OUTCOME_LEASE_URI, generation, raw
    )


def _config() -> supply.FullUnionOutcomeSupplyConfigV1:
    return supply.FullUnionOutcomeSupplyConfigV1(
        run_id="r6-full-union-fixture",
        job="r6-outcome-job",
        code_sha="a" * 40,
        image=f"fixture@sha256:{'b' * 64}",
        enabled=True,
    )


def _code_identities():
    return cli.SnapshotCodeIdentitiesV1(
        snapshot_module_sha256=SNAPSHOT_MODULE_SHA,
        snapshot_cli_sha256=SNAPSHOT_CLI_SHA,
        snapshot_test_sha256=SNAPSHOT_TEST_SHA,
        snapshot_cli_test_sha256=SNAPSHOT_CLI_TEST_SHA,
    )


def _common_argv(operation: str) -> list[str]:
    root = _root_identity()
    return [
        operation,
        "--run-id", "r6-full-union-fixture",
        "--job", "r6-outcome-job",
        "--code-sha", "a" * 40,
        "--image", f"fixture@sha256:{'b' * 64}",
        "--panel-freeze-uri", str(root["uri"]),
        "--panel-freeze-generation", str(root["generation"]),
        "--panel-freeze-sha256", str(root["sha256"]),
        "--panel-freeze-bytes", str(root["bytes"]),
        "--snapshot-module-sha256", SNAPSHOT_MODULE_SHA,
        "--snapshot-cli-sha256", SNAPSHOT_CLI_SHA,
        "--snapshot-test-sha256", SNAPSHOT_TEST_SHA,
        "--snapshot-cli-test-sha256", SNAPSHOT_CLI_TEST_SHA,
    ]


def _supply_argv(smoke_identity: dict[str, object]) -> list[str]:
    lease = _lease_identity()
    return [
        *_common_argv("supply"),
        "--actual-root-smoke-uri", str(smoke_identity["uri"]),
        "--actual-root-smoke-generation", str(smoke_identity["generation"]),
        "--actual-root-smoke-sha256", str(smoke_identity["sha256"]),
        "--actual-root-smoke-bytes", str(smoke_identity["bytes"]),
        "--expected-lease-uri", str(lease["uri"]),
        "--expected-lease-generation", str(lease["generation"]),
        "--expected-lease-sha256", str(lease["sha256"]),
        "--expected-lease-bytes", str(lease["bytes"]),
    ]


def _snapshot_boundary(
    monkeypatch: pytest.MonkeyPatch,
    *,
    root_identity: dict[str, object],
    root_raw: bytes,
) -> dict[str, object]:
    later_identity = _identity("gs://fixture-bucket/later.json", 9)
    projection = {
        "schema_version": cli.snapshot.OUTCOME_KEY_PROJECTION_SCHEMA,
        "panel_freeze_identity": root_identity,
        "panel_freeze_sha256": "3" * 64,
        "later_source_freeze_identity": later_identity,
        "later_source_freeze_sha256": "4" * 64,
        "source_slate_count": 54,
        "outcome_key_count": 7,
        "complete": True,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
    }
    projection["outcome_key_projection_sha256"] = supply.canonical_sha256(
        projection
    )

    def project(*, panel_freeze_identity, read_exact):
        assert panel_freeze_identity == root_identity
        assert read_exact(root_identity) == root_raw
        return dict(projection)

    def validate_projection(value, *, identity, read_exact):
        assert read_exact(root_identity) == root_raw
        normalized = batch.validate_json_identity(
            value, identity, label="fixture outcome-key projection"
        )
        assert value == projection
        return dict(value), normalized, ()

    def build_smoke(
        *,
        panel_freeze_identity,
        outcome_key_projection,
        outcome_key_projection_identity,
        expected_reviewed_source_commit_sha,
        expected_runtime_immutable_image,
        snapshot_module_sha256,
        snapshot_cli_sha256,
        snapshot_test_sha256,
        snapshot_cli_test_sha256,
        read_exact,
    ):
        assert panel_freeze_identity == root_identity
        assert outcome_key_projection == projection
        assert read_exact(root_identity) == root_raw
        assert batch.validate_json_identity(
            outcome_key_projection,
            outcome_key_projection_identity,
            label="fixture smoke-bound outcome-key projection",
        ) == outcome_key_projection_identity
        body = {
            "schema_version": (
                cli.snapshot.ACTUAL_ROOT_SMOKE_RECEIPT_SCHEMA
            ),
            "panel_freeze_identity": root_identity,
            "panel_freeze_sha256": projection["panel_freeze_sha256"],
            "outcome_key_projection_identity": (
                outcome_key_projection_identity
            ),
            "outcome_key_projection_sha256": projection[
                "outcome_key_projection_sha256"
            ],
            "reviewed_source_commit_sha": (
                expected_reviewed_source_commit_sha
            ),
            "runtime_immutable_image": expected_runtime_immutable_image,
            "snapshot_module_sha256": snapshot_module_sha256,
            "snapshot_cli_sha256": snapshot_cli_sha256,
            "snapshot_test_sha256": snapshot_test_sha256,
            "snapshot_cli_test_sha256": snapshot_cli_test_sha256,
            "source_slate_count": 54,
            "root_leaf_result_replay_count": 54,
            "r0_r4_book_count": 270,
            "final_fit_book_count": 54,
            "outcome_key_count": projection["outcome_key_count"],
            "uses_realized_outcomes": False,
            "historical_outcome_lease_acquired": False,
            "bigquery_client_constructed": False,
            "query_executed": False,
            "lineup_scoring_performed": False,
            "graph_mutation_licensed": False,
            "production_change_licensed": False,
            "decision_authority": False,
        }
        body["actual_root_smoke_receipt_sha256"] = (
            supply.canonical_sha256(body)
        )
        return body

    def validate_smoke(
        value,
        *,
        identity,
        expected_panel_freeze_identity,
        outcome_key_projection,
        expected_outcome_key_projection_identity,
        expected_reviewed_source_commit_sha,
        expected_runtime_immutable_image,
        expected_snapshot_module_sha256,
        expected_snapshot_cli_sha256,
        expected_snapshot_test_sha256,
        expected_snapshot_cli_test_sha256,
        read_exact,
    ):
        expected = build_smoke(
            panel_freeze_identity=expected_panel_freeze_identity,
            outcome_key_projection=outcome_key_projection,
            outcome_key_projection_identity=(
                expected_outcome_key_projection_identity
            ),
            expected_reviewed_source_commit_sha=(
                expected_reviewed_source_commit_sha
            ),
            expected_runtime_immutable_image=expected_runtime_immutable_image,
            snapshot_module_sha256=expected_snapshot_module_sha256,
            snapshot_cli_sha256=expected_snapshot_cli_sha256,
            snapshot_test_sha256=expected_snapshot_test_sha256,
            snapshot_cli_test_sha256=expected_snapshot_cli_test_sha256,
            read_exact=read_exact,
        )
        assert value == expected
        normalized = batch.validate_json_identity(
            value, identity, label="fixture actual-root smoke receipt"
        )
        return dict(value), normalized

    monkeypatch.setattr(
        cli.snapshot, "project_required_outcome_keys_v1", project
    )
    monkeypatch.setattr(
        cli.snapshot,
        "validate_outcome_key_projection_v1",
        validate_projection,
    )
    monkeypatch.setattr(
        cli.snapshot, "build_actual_root_smoke_receipt_v1", build_smoke
    )
    monkeypatch.setattr(
        cli.snapshot,
        "validate_actual_root_smoke_receipt_v1",
        validate_smoke,
    )
    return projection


def _create_smoke(
    monkeypatch: pytest.MonkeyPatch,
    client: _FakeGCSClient,
) -> tuple[
    dict[str, object], cli.ActualRootSmokeCloudResultV1,
]:
    root_raw = b'{"root":true}'
    root_identity = client.seed(
        str(_root_identity()["uri"]), root_raw, generation=11
    )
    _snapshot_boundary(
        monkeypatch, root_identity=root_identity, root_raw=root_raw
    )
    result = cli.run_actual_root_smoke_v1(
        config=_config(),
        panel_freeze_identity=root_identity,
        code_identities=_code_identities(),
        store=cli.GenerationPinnedGCSV1(client),
    )
    return root_identity, result


def test_known_name_reads_and_publication_are_generation_pinned() -> None:
    client = _FakeGCSClient()
    store = cli.GenerationPinnedGCSV1(client)
    known_uri = "gs://fixture-bucket/known.json"
    known_raw = b'{"known":true}'
    identity = client.seed(known_uri, known_raw, generation=17)

    assert store.read_exact(identity) == known_raw
    assert store.read_exact(identity) == known_raw
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
    with pytest.raises(
        cli.R6FullUnionOutcomeRunnerV1Error, match="object differs"
    ):
        store.publish(output_uri, b'{"output":false}')


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
        self.created = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
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
            datetime(2026, 8, 26, 12, tzinfo=timezone.utc),
        ),
        shared.QueryParameter("target_seasons", "INT64", [2023], True),
    )
    return registered.QuerySpec(
        sql="SELECT @source_snapshot_at, season FROM fixture",
        parameters=parameters,
        job_id="corpus_realized_r6_full_union_fixture_deadbeef1234",
        location="US",
        sql_sha256=sha256(b"fixture sql").hexdigest(),
        parameters_sha256=sha256(b"fixture parameters").hexdigest(),
        union_keys_sha256=sha256(b"fixture keys").hexdigest(),
    )


def test_fixed_job_is_created_once_and_ambiguous_success_is_recovered() -> None:
    spec = _query_spec()
    client = _FakeBQClient()

    created = cli._get_or_create_query(client, spec)
    recovered = cli._get_or_create_query(client, spec)

    assert created.disposition == "created"
    assert recovered.disposition == "recovered"
    assert client.query_calls == 1
    assert client.query_kwargs is not None
    assert client.query_kwargs["job_id"] == spec.job_id
    assert client.query_kwargs["job_retry"] is None
    assert client.query_kwargs["job_config"].use_query_cache is False

    ambiguous_client = _FakeBQClient(ambiguous=True)
    ambiguous = cli._get_or_create_query(ambiguous_client, spec)
    assert ambiguous.disposition == "recovered"
    assert ambiguous_client.query_calls == 1

    assert client.job is not None
    client.job.query = "SELECT forged"
    with pytest.raises(
        cli.R6FullUnionOutcomeRunnerV1Error,
        match="job configuration differs",
    ):
        cli._get_or_create_query(client, spec)


def _lease_raw() -> bytes:
    config = _config()
    body = {
        "version": shared.adapter.HISTORICAL_OUTCOME_LEASE_VERSION,
        "run_id": config.run_id,
        "job": config.job,
        "code_sha": config.code_sha,
        "image": config.image,
        "acquired_at": "2026-08-26T00:00:00+00:00",
    }
    return batch.canonical_json_bytes(body) + b"\n"


def _supplied_result(
    *, lease_identity: dict[str, object],
) -> supply.FullUnionOutcomeSupplyV1:
    identities = {
        label: _identity(f"gs://fixture-bucket/{label}.json", index)
        for index, label in enumerate(
            ("projection", "attempt", "query", "source", "snapshot", "completion"),
            start=20,
        )
    }
    later_identity = _identity("gs://fixture-bucket/later.json", 19)
    return supply.FullUnionOutcomeSupplyV1(
        outcome_key_projection={"later_source_freeze_identity": later_identity},
        outcome_key_projection_identity=identities["projection"],
        attempt={
            "historical_outcome_lease": {
                "object_receipt": {**lease_identity, "create_only": True}
            }
        },
        attempt_identity=identities["attempt"],
        query_evidence={"query_job_disposition": "recovered"},
        query_evidence_identity=identities["query"],
        realized_source={},
        realized_source_identity=identities["source"],
        outcome_snapshot={},
        outcome_snapshot_identity=identities["snapshot"],
        completion={"query_job_id": "fixed-job", "outcome_key_count": 7},
        completion_identity=identities["completion"],
    )


def test_actual_root_smoke_precedes_bq_lease_and_supply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeGCSClient()
    root_identity, smoke_result = _create_smoke(monkeypatch, client)
    smoke_identity = dict(
        smoke_result.authority.actual_root_smoke_receipt_identity
    )
    client.current_resolutions.clear()
    lease_identity = client.seed(
        shared.adapter.HISTORICAL_OUTCOME_LEASE_URI,
        _lease_raw(),
        generation=99,
    )
    supplied = _supplied_result(lease_identity=lease_identity)
    events: list[str] = []

    def fake_supply(**kwargs):
        assert kwargs["panel_freeze_identity"] == root_identity
        assert kwargs["actual_root_smoke_receipt_identity"] == smoke_identity
        assert kwargs["outcome_key_projection_identity"] == (
            smoke_result.authority.outcome_key_projection_identity
        )
        observed_lease = kwargs["verify_lease"]()
        assert observed_lease["object_receipt"]["generation"] == "99"
        events.append("supply")
        return supplied

    monkeypatch.setattr(
        cli.supply, "supply_full_union_outcome_snapshot_v1", fake_supply
    )

    def bq_factory():
        resolved_names = {name for _, name in client.current_resolutions}
        assert any(
            name.endswith("actual-root-smoke-receipt.json")
            for name in resolved_names
        )
        assert any(
            name.endswith("outcome-key-projection.json")
            for name in resolved_names
        )
        events.append("bq")
        return object()

    result = cli.run_supply_cloud_v1(
        config=_config(),
        panel_freeze_identity=root_identity,
        expected_actual_root_smoke_receipt_identity=smoke_identity,
        code_identities=_code_identities(),
        expected_lease_identity=lease_identity,
        storage_client=client,
        bq_client_factory=bq_factory,
    )

    assert result.panel_freeze_identity == root_identity
    assert result.actual_root_smoke_receipt_identity == smoke_identity
    assert result.historical_lease_identity == lease_identity
    assert events == ["bq", "supply"]


@pytest.mark.parametrize("failure_kind", ("optional", "absent", "wrong"))
def test_smoke_adversaries_block_before_bq_lease_metadata_or_query(
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
) -> None:
    client = _FakeGCSClient()
    root_raw = b'{"root":true}'
    root_identity = client.seed(
        str(_root_identity()["uri"]), root_raw, generation=11
    )
    smoke_uri = f"{_config().output_root}/actual-root-smoke-receipt.json"
    expected_smoke: object
    if failure_kind == "optional":
        expected_smoke = None
    elif failure_kind == "absent":
        expected_smoke = _identity(smoke_uri, 100, b'{"absent":true}')
    else:
        client.seed(smoke_uri, b'{"wrong":true}', generation=100)
        expected_smoke = _identity(smoke_uri, 101, b'{"expected":true}')
    calls = {"bq": 0, "lease": 0, "metadata": 0, "query": 0}

    def forbidden_bq():
        calls["bq"] += 1
        raise AssertionError("smoke failure constructed BigQuery")

    def forbidden_lease(*args, **kwargs):
        calls["lease"] += 1
        raise AssertionError("smoke failure constructed lease verifier")

    def forbidden_metadata(*args, **kwargs):
        calls["metadata"] += 1
        raise AssertionError("smoke failure read table metadata")

    def forbidden_query(*args, **kwargs):
        calls["query"] += 1
        raise AssertionError("smoke failure reached fixed query")

    monkeypatch.setattr(cli, "LiveLeaseVerifierV1", forbidden_lease)
    monkeypatch.setattr(cli, "_table_metadata", forbidden_metadata)
    monkeypatch.setattr(cli, "_get_or_create_query", forbidden_query)
    with pytest.raises(cli.R6FullUnionOutcomeRunnerV1Error):
        cli.run_supply_cloud_v1(
            config=_config(),
            panel_freeze_identity=root_identity,
            expected_actual_root_smoke_receipt_identity=expected_smoke,
            code_identities=_code_identities(),
            expected_lease_identity=_lease_identity(),
            storage_client=client,
            bq_client_factory=forbidden_bq,
        )
    assert calls == {"bq": 0, "lease": 0, "metadata": 0, "query": 0}


def test_cli_is_default_off_and_stdout_is_receipt_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    smoke_uri = f"{_config().output_root}/actual-root-smoke-receipt.json"
    smoke_identity = _identity(smoke_uri, 100, b'{"smoke":true}')
    argv = _supply_argv(smoke_identity)
    with pytest.raises(
        cli.R6FullUnionOutcomeRunnerV1Error, match="required explicitly"
    ):
        cli.main(argv, environ={}, storage_client=object())
    assert capsys.readouterr().out == ""

    root_identity = _root_identity()
    lease_identity = _lease_identity()
    later_identity = _identity("gs://fixture-bucket/later.json", 9)
    identities = {
        label: _identity(f"gs://fixture-bucket/{label}.json", index)
        for index, label in enumerate(
            ("projection", "attempt", "query", "source", "snapshot", "completion"),
            start=1,
        )
    }
    supplied = supply.FullUnionOutcomeSupplyV1(
        outcome_key_projection={"later_source_freeze_identity": later_identity},
        outcome_key_projection_identity=identities["projection"],
        attempt={"rows": ["must-not-reach-stdout"]},
        attempt_identity=identities["attempt"],
        query_evidence={
            "query_job_disposition": "recovered",
            "rows": ["must-not-reach-stdout"],
        },
        query_evidence_identity=identities["query"],
        realized_source={"rows": ["must-not-reach-stdout"]},
        realized_source_identity=identities["source"],
        outcome_snapshot={"rows": ["must-not-reach-stdout"]},
        outcome_snapshot_identity=identities["snapshot"],
        completion={"query_job_id": "fixed-job", "outcome_key_count": 123},
        completion_identity=identities["completion"],
    )
    cloud = cli.FullUnionOutcomeCloudResultV1(
        supply=supplied,
        panel_freeze_identity=root_identity,
        actual_root_smoke_receipt_identity=smoke_identity,
        historical_lease_identity=lease_identity,
    )

    monkeypatch.setattr(cli, "run_supply_cloud_v1", lambda **kwargs: cloud)
    assert cli.main(
        [argv[0], "--execute", *argv[1:]],
        environ={cli.ENABLED_ENV: "1"},
        storage_client=object(),
        bq_client_factory=lambda: object(),
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
    assert receipt["rank_available"] is False
    assert receipt["roi_available"] is False
    assert receipt["decision_authority"] is False


def test_smoke_cli_never_constructs_bigquery_and_prints_only_receipt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    root_identity = _root_identity()
    projection_identity = _identity(
        f"{_config().output_root}/outcome-key-projection.json",
        100,
        b'{"projection":true}',
    )
    smoke_identity = _identity(
        f"{_config().output_root}/actual-root-smoke-receipt.json",
        101,
        b'{"smoke":true}',
    )
    authority = cli.ActualRootSmokeAuthorityV1(
        panel_freeze_identity=root_identity,
        outcome_key_projection={
            "later_source_freeze_identity": _identity(
                "gs://fixture-bucket/later.json", 9
            )
        },
        outcome_key_projection_identity=projection_identity,
        actual_root_smoke_receipt={
            "source_slate_count": 54,
            "root_leaf_result_replay_count": 54,
            "r0_r4_book_count": 270,
            "final_fit_book_count": 54,
            "outcome_key_count": 7,
        },
        actual_root_smoke_receipt_identity=smoke_identity,
        code_identities=_code_identities(),
    )
    monkeypatch.setattr(
        cli,
        "run_actual_root_smoke_v1",
        lambda **kwargs: cli.ActualRootSmokeCloudResultV1(authority=authority),
    )
    bq_calls = 0

    def forbidden_bq():
        nonlocal bq_calls
        bq_calls += 1
        raise AssertionError("smoke operation constructed BigQuery")

    argv = _common_argv("smoke")
    assert cli.main(
        [argv[0], "--execute", *argv[1:]],
        environ={cli.SMOKE_ENABLED_ENV: "1"},
        storage_client=object(),
        bq_client_factory=forbidden_bq,
    ) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert bq_calls == 0
    assert receipt["schema_version"] == cli.SMOKE_RECEIPT_SCHEMA
    assert receipt["bigquery_client_constructed"] is False
    assert receipt["query_executed"] is False
    assert "slate_replays" not in receipt
