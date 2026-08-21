from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sys
from types import SimpleNamespace

from google.api_core.exceptions import PreconditionFailed
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_lr8_later_period_evaluation as runner  # noqa: E402


RUN_ID = "20260821-lr8-later-period-v1"
JOB = "lr8-later-period"
CODE_SHA = "a" * 40
IMAGE = "us-central1-docker.pkg.dev/p/r/i@sha256:" + "b" * 64
FREEZE_SHA = "c" * 64
FREEZE_URI = "gs://fixture/lr8/later-period-books.json"
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
        value = store.objects.get(self.uri)
        self.generation = value.generation if value else None
        self.time_created = value.created if value else None

    def _value(self) -> _Object:
        value = self.store.objects.get(self.uri)
        if value is None or (
            self.requested_generation is not None
            and str(self.requested_generation) != value.generation
        ):
            raise PreconditionFailed("generation differs")
        return value

    def reload(self, *, if_generation_match: int) -> None:
        value = self._value()
        if str(if_generation_match) != value.generation:
            raise PreconditionFailed("generation differs")
        self.store.events.append((
            "reload", self.uri, self.requested_generation, if_generation_match,
        ))
        self.generation = value.generation
        self.time_created = value.created

    def download_as_bytes(self, *, if_generation_match: int) -> bytes:
        value = self._value()
        if str(if_generation_match) != value.generation:
            raise PreconditionFailed("generation differs")
        self.store.events.append((
            "download", self.uri, self.requested_generation,
            if_generation_match,
        ))
        return value.raw

    def upload_from_string(
        self, raw: bytes, *, content_type: str, if_generation_match: int,
    ) -> None:
        self.store.events.append((
            "upload", self.uri, content_type, if_generation_match,
        ))
        if if_generation_match != 0 or self.uri in self.store.objects:
            raise PreconditionFailed("create-only collision")
        value = _Object(raw, str(self.store.next_generation))
        self.store.next_generation += 1
        self.store.objects[self.uri] = value
        self.generation = value.generation
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
        self.objects[uri] = _Object(raw, generation)


class _Job:
    job_id = "lr8_later_eval_fixture"
    location = "US"
    created = NOW
    started = NOW
    ended = NOW
    total_bytes_processed = 1
    cache_hit = False
    error_result = None

    def result(self) -> tuple[()]:
        return ()


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

    def query(self, _sql: str, **kwargs: object) -> _Job:
        self.events.append(("query", kwargs))
        job = _Job()
        job.job_id = str(kwargs["job_id"])
        job.location = str(kwargs["location"])
        return job


def _fixture(tmp_path: Path) -> tuple[
    _Storage, runner.BookFreezePin, dict[str, object], Path,
]:
    storage = _Storage()
    freeze = {"freeze_sha256": FREEZE_SHA}
    freeze_raw = runner.supplier.canonical_json(freeze)
    storage.add(FREEZE_URI, freeze_raw, "11")
    pin = runner.BookFreezePin(
        FREEZE_URI, "11", sha256(freeze_raw).hexdigest(), FREEZE_SHA
    )
    body = {
        "version": runner.lease_identity.HISTORICAL_OUTCOME_LEASE_VERSION,
        "run_id": RUN_ID,
        "job": JOB,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "acquired_at": NOW.isoformat(),
    }
    raw = runner.supplier.canonical_json(body)
    receipt = {
        "uri": runner.lease_identity.HISTORICAL_OUTCOME_LEASE_URI,
        "generation": "7",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "create_only": True,
    }
    storage.add(str(receipt["uri"]), raw, "7")
    path = tmp_path / "historical-outcome-lease.json"
    path.write_bytes(runner.supplier.canonical_json({
        "lease": body, "object": receipt,
    }))
    return storage, pin, {"body": body, "object_receipt": receipt}, path


def _config() -> runner.supplier.SupplierConfig:
    return runner.supplier.SupplierConfig(
        RUN_ID, JOB, CODE_SHA, IMAGE, FREEZE_SHA, True
    )


def _mock_supply(captured: dict[str, object]):
    def supply(**kwargs: object) -> runner.supplier.EvaluationSupply:
        config = kwargs["config"]
        verify = kwargs["verify_lease"]
        metadata = kwargs["read_table_metadata"]
        execute = kwargs["execute_query"]
        publish = kwargs["publish"]
        captured["freeze"] = kwargs["book_freeze"]
        captured["freeze_receipt"] = kwargs["book_freeze_receipt"]
        captured["lease_before"] = verify()
        attempt = publish(
            f"{config.output_root}/later-period-read-attempt.json",
            runner.supplier.canonical_json({"kind": "attempt"}),
        )
        parameters = (
            runner.lease_boundary.QueryParameter(
                "source_snapshot_at", "TIMESTAMP", NOW.isoformat()
            ),
            runner.lease_boundary.QueryParameter(
                "target_seasons", "INT64", [2023, 2024, 2025], True
            ),
            runner.lease_boundary.QueryParameter(
                "skill_keys", "STRING", ["2023|01|p"], True
            ),
            runner.lease_boundary.QueryParameter(
                "dst_keys", "STRING", ["2023|01|D"], True
            ),
        )
        spec = runner.supplier.QuerySpec(
            "SELECT 1", parameters, "lr8_later_eval_fixture", "US",
            "d" * 64, "e" * 64, "f" * 64,
        )
        for table in (runner.supplier.SKILL_TABLE, runner.supplier.DST_TABLE):
            metadata(table)
        captured["query"] = execute(spec)
        for table in (runner.supplier.SKILL_TABLE, runner.supplier.DST_TABLE):
            metadata(table)
        captured["lease_after"] = verify()
        source = publish(
            f"{config.output_root}/later-period-player-score-source.json",
            runner.supplier.canonical_json({"kind": "source"}),
        )
        evaluation = publish(
            f"{config.output_root}/later-period-evaluation.json",
            runner.supplier.canonical_json({"kind": "evaluation"}),
        )
        return runner.supplier.EvaluationSupply(
            {}, attempt.receipt, {}, source.receipt, {}, evaluation.receipt
        )

    return supply


def test_default_off_precedes_lease_receipt_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    monkeypatch.delenv(runner.ENABLED_ENV, raising=False)
    missing = tmp_path / "must-not-be-read.json"
    args = runner._parser().parse_args([  # noqa: SLF001
        "--execute", "--run-id", RUN_ID, "--job", JOB,
        "--code-sha", CODE_SHA, "--image", IMAGE,
        "--book-freeze-uri", FREEZE_URI,
        "--book-freeze-generation", "11",
        "--book-freeze-sha256", "d" * 64,
        "--book-freeze-manifest-sha256", FREEZE_SHA,
        "--historical-lease-receipt", str(missing),
    ])
    with pytest.raises(runner.LR8LaterPeriodRunnerError, match="required explicitly"):
        runner._validated_cli(args)  # noqa: SLF001
    assert not missing.exists()


def test_runner_reopens_pins_queries_once_and_returns_receipts_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    storage, pin, lease, _ = _fixture(tmp_path)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        runner.supplier, "supply_later_period_evaluation",
        _mock_supply(captured),
    )
    result = runner.run_cloud(
        config=_config(), book_pin=pin, lease_contract=lease,
        bq_client=_BQ(storage.events), storage_client=storage,
    )
    assert captured["freeze"] == {"freeze_sha256": FREEZE_SHA}
    assert captured["lease_before"] == captured["lease_after"]
    query_events = [row for row in storage.events if row[0] == "query"]
    assert len(query_events) == 1
    kwargs = query_events[0][1]
    assert kwargs["job_retry"] is None
    assert kwargs["job_config"].use_query_cache is False
    freeze_download = next(
        row for row in storage.events
        if row[:2] == ("download", FREEZE_URI)
    )
    assert freeze_download[2:] == (11, 11)
    lease_downloads = [
        index for index, row in enumerate(storage.events)
        if row[:2] == (
            "download", runner.lease_identity.HISTORICAL_OUTCOME_LEASE_URI
        )
    ]
    query_index = next(
        index for index, row in enumerate(storage.events) if row[0] == "query"
    )
    assert len(lease_downloads) == 2
    assert lease_downloads[0] < query_index < lease_downloads[1]
    uploads = [row for row in storage.events if row[0] == "upload"]
    assert len(uploads) == 3
    assert all(row[2:] == ("application/json", 0) for row in uploads)
    closed = runner._receipt_only(result)  # noqa: SLF001
    assert closed["historical_outcome_lease_release_required"] is True
    assert closed["lease_release_owner"] == "external-launcher-watcher"
    public = runner.supplier.canonical_json(closed)
    assert b"score_rows" not in public and b"evaluation_report" not in public


def test_transport_leaves_lease_lifecycle_to_external_owner():
    source = (ROOT / "scripts/run_lr8_later_period_evaluation.py").read_text()
    assert "historical_outcome_lease.py" not in source
    assert "LEASE_OWNER" in source
    assert "external-launcher-watcher" in runner.supplier.LEASE_OWNER
