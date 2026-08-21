from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import sys
from types import SimpleNamespace

from google.api_core.exceptions import PreconditionFailed
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_lr8_label_score_map as runner  # noqa: E402


RUN_ID = "20260821-lr8-label-score-map-v1"
JOB = "lr8-label-score-map"
CODE_SHA = "a" * 40
IMAGE = "us-central1-docker.pkg.dev/p/r/i@sha256:" + "b" * 64
MANIFEST_SHA = "c" * 64
SOURCE_URI = "gs://fixture/lr8/full-source-freeze.json"
NOW = datetime(2026, 8, 21, tzinfo=timezone.utc)


@dataclass
class _Object:
    raw: bytes
    generation: str
    created: datetime = NOW


class _Blob:
    def __init__(
        self, store: "_Storage", bucket: str, name: str,
        generation: int | None,
    ):
        self.store = store
        self.uri = f"gs://{bucket}/{name}"
        self.requested_generation = generation
        current = store.objects.get(self.uri)
        self.generation = current.generation if current else None
        self.time_created = current.created if current else None

    def _object(self) -> _Object:
        value = self.store.objects.get(self.uri)
        if value is None or (
            self.requested_generation is not None
            and str(self.requested_generation) != value.generation
        ):
            raise PreconditionFailed("generation differs")
        return value

    def reload(self, *, if_generation_match: int | None = None) -> None:
        value = self._object()
        if (
            if_generation_match is not None
            and str(if_generation_match) != value.generation
        ):
            raise PreconditionFailed("generation differs")
        self.store.events.append((
            "reload", self.uri, self.requested_generation, if_generation_match,
        ))
        self.generation = value.generation
        self.time_created = value.created

    def download_as_bytes(self, *, if_generation_match: int) -> bytes:
        value = self._object()
        if str(if_generation_match) != value.generation:
            raise PreconditionFailed("generation differs")
        self.store.events.append((
            "download", self.uri, self.requested_generation,
            if_generation_match,
        ))
        self.generation = value.generation
        self.time_created = value.created
        return value.raw

    def upload_from_string(
        self, raw: bytes, *, content_type: str, if_generation_match: int,
    ) -> None:
        self.store.events.append((
            "upload", self.uri, content_type, if_generation_match,
        ))
        if if_generation_match != 0 or self.uri in self.store.objects:
            raise PreconditionFailed("create-only collision")
        generation = str(self.store.next_generation)
        self.store.next_generation += 1
        value = _Object(raw=raw, generation=generation)
        self.store.objects[self.uri] = value
        self.generation = generation
        self.time_created = value.created


class _Bucket:
    def __init__(self, store: "_Storage", name: str):
        self.store = store
        self.name = name

    def blob(self, name: str, generation: int | None = None) -> _Blob:
        return _Blob(self.store, self.name, name, generation)


class _Storage:
    def __init__(self):
        self.objects: dict[str, _Object] = {}
        self.events: list[tuple[object, ...]] = []
        self.next_generation = 100

    def bucket(self, name: str) -> _Bucket:
        return _Bucket(self, name)

    def add(self, uri: str, raw: bytes, generation: str) -> None:
        self.objects[uri] = _Object(raw=raw, generation=generation)


class _BQ:
    def __init__(self, events: list[tuple[object, ...]]):
        self.events = events

    def get_table(self, table_id: str) -> object:
        self.events.append(("metadata", table_id))
        field = SimpleNamespace(
            name="season", field_type="INTEGER", mode="NULLABLE", fields=(),
        )
        return SimpleNamespace(
            etag=f"etag/{table_id}", modified=NOW, num_rows=10,
            schema=(field,),
        )

    def query(self, sql: str, **kwargs: object) -> object:
        self.events.append(("query", kwargs["job_id"], kwargs))
        return _Job(str(kwargs["job_id"]), str(kwargs["location"]))


class _Job:
    def __init__(self, job_id: str, location: str):
        self.job_id = job_id
        self.location = location
        self.created = NOW
        self.started = NOW
        self.ended = NOW
        self.total_bytes_processed = 123
        self.cache_hit = False
        self.error_result = None

    def result(self) -> tuple[dict[str, object], ...]:
        return ({"realized_score": Decimal("10.250000")},)


def _config(*, enabled: bool = True) -> runner.supplier.SupplierConfig:
    return runner.supplier.SupplierConfig(
        run_id=RUN_ID,
        job=JOB,
        code_sha=CODE_SHA,
        image=IMAGE,
        expected_source_manifest_sha256=MANIFEST_SHA,
        enabled=enabled,
    )


def _fixture(tmp_path: Path) -> tuple[
    _Storage, runner.SourcePin, dict[str, object], Path,
]:
    storage = _Storage()
    source_body = {"manifest_sha256": MANIFEST_SHA, "slates": []}
    source_raw = runner.supplier.canonical_json(source_body)
    storage.add(SOURCE_URI, source_raw, "11")
    pin = runner.SourcePin(
        uri=SOURCE_URI,
        generation="11",
        sha256=sha256(source_raw).hexdigest(),
        manifest_sha256=MANIFEST_SHA,
    )
    lease_body = {
        "version": runner.adapter.HISTORICAL_OUTCOME_LEASE_VERSION,
        "run_id": RUN_ID,
        "job": JOB,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "acquired_at": NOW.isoformat(),
    }
    lease_raw = runner.supplier.canonical_json(lease_body)
    lease_uri = runner.adapter.HISTORICAL_OUTCOME_LEASE_URI
    storage.add(lease_uri, lease_raw, "7")
    lease_object = {
        "uri": lease_uri,
        "generation": "7",
        "sha256": sha256(lease_raw).hexdigest(),
        "bytes": len(lease_raw),
        "create_only": True,
    }
    path = tmp_path / "historical-outcome-lease.json"
    path.write_bytes(runner.supplier.canonical_json({
        "lease": lease_body, "object": lease_object,
    }))
    return storage, pin, {
        "body": lease_body, "object_receipt": lease_object,
    }, path


def _mock_supplier(
    captured: dict[str, object],
):
    def supply(**kwargs: object) -> runner.supplier.ScoreMapSupply:
        config = kwargs["config"]
        verify = kwargs["verify_lease"]
        metadata = kwargs["read_table_metadata"]
        execute = kwargs["execute_query"]
        publish = kwargs["publish"]
        captured["source"] = kwargs["training_source_freeze"]
        captured["source_receipt"] = kwargs["training_source_receipt"]
        captured["lease_before"] = verify()
        attempt_uri = f"{config.output_root}/label-read-attempt.json"
        attempt = publish(
            attempt_uri, runner.supplier.canonical_json({"kind": "attempt"})
        )
        catalog = (
            runner.supplier.CatalogPlayer(2019, 1, "p", "QB", "skill", "p"),
            runner.supplier.CatalogPlayer(2019, 1, "D", "DST", "dst", "D"),
        )
        spec = runner.supplier.build_query_spec(
            config=config,
            catalog=catalog,
            source_snapshot_at=NOW.isoformat(),
        )
        for table in (runner.supplier.SKILL_TABLE, runner.supplier.DST_TABLE):
            metadata(table)
        captured["query_result"] = execute(spec)
        for table in (runner.supplier.SKILL_TABLE, runner.supplier.DST_TABLE):
            metadata(table)
        captured["lease_after"] = verify()
        extract = publish(
            f"{config.output_root}/authoritative-score-source.json",
            runner.supplier.canonical_json({"kind": "extract"}),
        )
        score_map = publish(
            f"{config.output_root}/authoritative-score-map.json",
            runner.supplier.canonical_json({"kind": "map"}),
        )
        return runner.supplier.ScoreMapSupply(
            attempt={},
            attempt_receipt=attempt.receipt,
            source_extract={},
            source_extract_receipt=extract.receipt,
            score_map={},
            score_map_receipt=score_map.receipt,
        )

    return supply


def test_default_off_precedes_receipt_or_cloud_access(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.delenv(runner.ENABLED_ENV, raising=False)
    missing = tmp_path / "must-not-be-read.json"
    args = runner._parser().parse_args([  # noqa: SLF001
        "--execute", "--run-id", RUN_ID, "--job", JOB,
        "--code-sha", CODE_SHA, "--image", IMAGE,
        "--training-source-uri", SOURCE_URI,
        "--training-source-generation", "11",
        "--training-source-sha256", "d" * 64,
        "--training-source-manifest-sha256", MANIFEST_SHA,
        "--historical-lease-receipt", str(missing),
    ])
    with pytest.raises(runner.LR8ScoreMapRunnerError, match="required explicitly"):
        runner._validated_cli(args)  # noqa: SLF001
    assert not missing.exists()


def test_mocked_runner_is_pinned_one_query_create_once_and_receipt_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    storage, pin, lease, _ = _fixture(tmp_path)
    bq = _BQ(storage.events)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        runner.supplier, "supply_authoritative_score_map",
        _mock_supplier(captured),
    )
    result = runner.run_cloud(
        config=_config(), source_pin=pin, lease_contract=lease,
        bq_client=bq, storage_client=storage,
    )

    queries = [event for event in storage.events if event[0] == "query"]
    assert len(queries) == 1
    _, job_id, query_kwargs = queries[0]
    assert job_id == (
        "lr8_label_score_map_20260821_lr8_label_score_map_v1_" +
        MANIFEST_SHA[:12]
    )
    assert query_kwargs["job_retry"] is None
    assert query_kwargs["location"] == "US"
    assert query_kwargs["job_config"].use_query_cache is False
    assert [p.name for p in query_kwargs["job_config"].query_parameters] == [
        "source_snapshot_at", "target_seasons", "skill_keys", "dst_keys",
    ]
    query_result = captured["query_result"]
    assert query_result.rows[0]["realized_score"] == Decimal("10.250000")
    assert captured["lease_before"] == captured["lease_after"]
    lease_downloads = [
        i for i, event in enumerate(storage.events)
        if event[:2] == ("download", runner.adapter.HISTORICAL_OUTCOME_LEASE_URI)
    ]
    query_index = next(
        i for i, event in enumerate(storage.events) if event[0] == "query"
    )
    assert len(lease_downloads) == 2
    assert lease_downloads[0] < query_index < lease_downloads[1]
    uploads = [event for event in storage.events if event[0] == "upload"]
    assert len(uploads) == 3
    assert all(event[2:] == ("application/json", 0) for event in uploads)
    output_downloads = [
        event for event in storage.events
        if event[0] == "download" and "/lr8-authoritative-label-score-map/" in event[1]
    ]
    assert len(output_downloads) == 3
    assert all(event[2] == event[3] for event in output_downloads)
    closed = runner._receipt_only(result)  # noqa: SLF001
    assert set(closed) == {
        "status", "attempt_object", "source_extract_object", "score_map_object",
    }
    public = runner.supplier.canonical_json(closed)
    assert b"realized_score" not in public and b'"rows"' not in public
    assert b"total_bytes_processed" not in public


def test_pin_lease_and_collision_fail_without_query_or_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    storage, pin, lease, _ = _fixture(tmp_path)
    monkeypatch.setattr(
        runner.supplier, "supply_authoritative_score_map",
        _mock_supplier({}),
    )
    bq = _BQ(storage.events)
    bad_pin = runner.SourcePin(
        uri=pin.uri, generation=pin.generation, sha256="0" * 64,
        manifest_sha256=pin.manifest_sha256,
    )
    with pytest.raises(runner.LR8ScoreMapRunnerError, match="identity differs"):
        runner.run_cloud(
            config=_config(), source_pin=bad_pin, lease_contract=lease,
            bq_client=bq, storage_client=storage,
        )
    assert not any(event[0] == "query" for event in storage.events)

    storage.events.clear()
    stale = {
        "body": lease["body"],
        "object_receipt": {**lease["object_receipt"], "generation": "6"},
    }
    with pytest.raises(
        runner.LR8ScoreMapRunnerError, match="live-generation verification failed",
    ):
        runner.run_cloud(
            config=_config(), source_pin=pin, lease_contract=stale,
            bq_client=bq, storage_client=storage,
        )
    assert not any(event[0] == "query" for event in storage.events)

    storage.events.clear()
    attempt_uri = f"{_config().output_root}/label-read-attempt.json"
    storage.add(attempt_uri, b"already exists\n", "50")
    with pytest.raises(runner.LR8ScoreMapRunnerError, match="create-once refused"):
        runner.run_cloud(
            config=_config(), source_pin=pin, lease_contract=lease,
            bq_client=bq, storage_client=storage,
        )
    assert not any(event[0] == "query" for event in storage.events)
