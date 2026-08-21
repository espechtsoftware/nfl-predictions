from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from google.api_core.exceptions import NotFound, PreconditionFailed
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import close_a7_select_ladder_failed_preflight_v1 as close_v1  # noqa: E402


SOURCE_OUT = (
    ROOT / "reports/a7-select-ladder-preflight-runs" / close_v1.RUN_ID
)
TERMINAL_SNAPSHOT = (
    ROOT / "reports/a2a-production-law-dependence-runs"
    / "20260820-a2a-production-law-dependence-remeasurement-v1"
    / "job-executions-before.json"
)


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()


def _terminal() -> dict[str, Any]:
    rows = json.loads(TERMINAL_SNAPSHOT.read_text(encoding="utf-8"))
    matches = [
        row for row in rows
        if row.get("metadata", {}).get("name") == close_v1.EXECUTION
    ]
    assert len(matches) == 1
    return matches[0]


class FakeBlob:
    def __init__(
        self, client: "FakeStorage", name: str, generation: int | None = None,
    ) -> None:
        self.client = client
        self.name = name
        self.requested_generation = generation
        self.generation: int | None = generation
        self.metageneration: int | None = None
        self.size: int | None = None
        self.md5_hash: str | None = None
        self.crc32c: str | None = None
        self.etag: str | None = None
        self.time_created: datetime | None = None
        self.updated: datetime | None = None

    def _row(self) -> dict[str, Any]:
        failure = self.client.reload_failures.get(self.name)
        if failure is not None:
            raise failure
        if self.name not in self.client.objects:
            raise NotFound("missing")
        row = self.client.objects[self.name]
        if self.requested_generation is not None and \
                row["generation"] != self.requested_generation:
            raise NotFound("generation missing")
        return row

    def reload(self, **_kwargs: Any) -> None:
        self.client.events.append(("reload", self.name, self.requested_generation))
        row = self._row()
        self.generation = row["generation"]
        self.metageneration = row["metageneration"]
        self.size = len(row["raw"])
        self.md5_hash = "md5"
        self.crc32c = "crc"
        self.etag = "etag"
        self.time_created = row["time_created"]
        self.updated = row["time_created"]

    def download_as_bytes(self, *, if_generation_match: int) -> bytes:
        self.client.events.append(("download", self.name, if_generation_match))
        row = self._row()
        if row["generation"] != if_generation_match:
            raise RuntimeError("generation mismatch")
        return row["raw"]

    def upload_from_string(
        self, raw: bytes, *, content_type: str, if_generation_match: int,
    ) -> None:
        self.client.events.append((
            "upload", self.name, content_type, if_generation_match,
        ))
        if self.client.collision or self.name in self.client.objects or \
                if_generation_match != 0:
            raise PreconditionFailed("occupied")
        self.client.objects[self.name] = {
            "raw": bytes(raw),
            "generation": self.client.next_generation,
            "metageneration": 1,
            "time_created": datetime(2026, 8, 20, 20, 1, tzinfo=timezone.utc),
        }
        self.generation = self.client.next_generation


class FakeBucket:
    def __init__(self, client: "FakeStorage", name: str) -> None:
        self.client = client
        self.name = name

    def blob(self, name: str, generation: int | None = None) -> FakeBlob:
        return FakeBlob(self.client, name, generation)


class FakeStorage:
    def __init__(self, claim_raw: bytes) -> None:
        _, claim_name = close_v1._gcs_parts(close_v1.JOB_CLAIM_URI)
        self.objects: dict[str, dict[str, Any]] = {
            claim_name: {
                "raw": claim_raw,
                "generation": 1787237723143509,
                "metageneration": 1,
                "time_created": datetime(
                    2026, 8, 20, 14, 55, 23, tzinfo=timezone.utc,
                ),
            },
        }
        self.reload_failures: dict[str, Exception] = {}
        self.events: list[tuple[Any, ...]] = []
        self.next_generation = 1787274000000000
        self.collision = False
        self.list_override: list[str] | None = None

    def bucket(self, name: str) -> FakeBucket:
        assert name == "nfl-predictions-503414-raw"
        return FakeBucket(self, name)

    def list_blobs(self, bucket: str, *, prefix: str) -> list[FakeBlob]:
        assert bucket == "nfl-predictions-503414-raw"
        self.events.append(("list", prefix))
        names = self.list_override
        if names is None:
            names = sorted(name for name in self.objects if name.startswith(prefix))
        return [
            FakeBlob(self, name, self.objects[name]["generation"])
            for name in names
        ]


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "repo"
        self.out = (
            self.root / "reports/a7-select-ladder-preflight-runs"
            / close_v1.RUN_ID
        )
        shutil.copytree(SOURCE_OUT, self.out)
        for name in (
            close_v1.TERMINAL_RECEIPT_NAME,
            close_v1.INVENTORY_RECEIPT_NAME,
            close_v1.ABSENCE_RECEIPT_NAME,
            close_v1.DEFAULT_RELEASE.name,
            close_v1.DEFAULT_RELEASE_OBJECT.name,
        ):
            (self.out / name).unlink(missing_ok=True)
        for relative in (
            close_v1.PROTOCOL_PATH,
            close_v1.CLOSURE_PROTOCOL_PATH,
            close_v1.DISPOSITION_REPORT_PATH,
        ):
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        claim = json.loads(
            (self.out / "job-claim-receipt.json").read_text(encoding="utf-8")
        )["claim"]
        self.storage = FakeStorage(_canonical(claim))
        self.source_blobs = {
            relative: close_v1._git_blob(ROOT, close_v1.CODE_SHA, relative)
            for relative in close_v1.V1_SOURCE_SHA256
        }

    def git_loader(self, _root: Path, code_sha: str, relative: str) -> bytes:
        assert code_sha == close_v1.CODE_SHA
        return self.source_blobs[relative]

    def close(self, **kwargs: Any) -> dict[str, Any]:
        options = {
            "root": self.root,
            "out": self.out,
            "client": self.storage,
            "execution_loader": _terminal,
            "now": lambda: datetime(
                2026, 8, 20, 20, 0, tzinfo=timezone.utc,
            ),
            "git_loader": self.git_loader,
        }
        options.update(kwargs)
        return close_v1.close(**options)


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


def test_real_retained_local_evidence_is_exact() -> None:
    evidence = close_v1._validate_local_evidence(SOURCE_OUT)
    assert evidence["build"]["id"] == close_v1.BUILD_ID
    future_execution_spec = (
        evidence["job_after"]["spec"]["template"]["spec"]
    )
    assert future_execution_spec == close_v1._expected_execution_contract()
    assert evidence["claim_receipt"]["object"]["generation"] == \
        "1787237723143509"


def test_close_is_exact_create_once_and_idempotent(harness: Harness) -> None:
    result = harness.close()
    assert result["status"] == "released"
    release, receipt = close_v1.validate_failure_release_files(
        harness.out / close_v1.DEFAULT_RELEASE.name,
        harness.out / close_v1.DEFAULT_RELEASE_OBJECT.name,
    )
    assert release["next_run_id"] == close_v1.NEXT_RUN_ID
    assert release["terminal_execution"]["counters"] == {
        "succeeded": 0, "failed": 1, "cancelled": 0, "retried": 0,
    }
    assert release["outcome_boundary"]["historical_look_consumed"] is False
    assert all(value is False for value in release["licenses"].values())
    assert receipt["object"]["create_only"] is True
    assert receipt["object"]["uri"] == close_v1.RELEASE_URI
    upload_events = [row for row in harness.storage.events if row[0] == "upload"]
    assert len(upload_events) == 1

    downloaded = [row[1] for row in harness.storage.events if row[0] == "download"]
    assert set(downloaded) == {
        close_v1._gcs_parts(close_v1.JOB_CLAIM_URI)[1],
        close_v1._gcs_parts(close_v1.RELEASE_URI)[1],
    }
    second = harness.close()
    assert second["status"] == "already-released"
    assert len([row for row in harness.storage.events if row[0] == "upload"]) == 1


@pytest.mark.parametrize(
    "mutator",
    [
        lambda row: row["status"]["conditions"].__setitem__(
            0, {**row["status"]["conditions"][0], "status": "True"},
        ),
        lambda row: row["status"].__setitem__("failedCount", 0),
        lambda row: row["status"].__setitem__("succeededCount", 1),
        lambda row: row["status"].__setitem__("retriedCount", 1),
        lambda row: row["spec"]["template"]["spec"].__setitem__("maxRetries", 1),
    ],
)
def test_terminal_poison_fails_before_cloud_body_or_write(
    harness: Harness, mutator: Any,
) -> None:
    terminal = copy.deepcopy(_terminal())
    mutator(terminal)
    with pytest.raises(RuntimeError):
        harness.close(execution_loader=lambda: terminal)
    assert not [row for row in harness.storage.events if row[0] in {"download", "upload"}]


def test_prefix_extra_object_fails_before_publication(harness: Harness) -> None:
    bucket, extra = close_v1._gcs_parts(close_v1.SMOKE_URI)
    assert bucket == "nfl-predictions-503414-raw"
    harness.storage.objects[extra] = {
        "raw": b"forbidden",
        "generation": 2,
        "metageneration": 1,
        "time_created": datetime.now(timezone.utc),
    }
    with pytest.raises(RuntimeError, match="not singleton"):
        harness.close()
    assert not [row for row in harness.storage.events if row[0] == "upload"]


def test_generation_pinned_claim_body_mismatch_fails(harness: Harness) -> None:
    _, name = close_v1._gcs_parts(close_v1.JOB_CLAIM_URI)
    harness.storage.objects[name]["raw"] = b"{}\n"
    with pytest.raises(RuntimeError, match="job claim differs"):
        harness.close()
    assert not [row for row in harness.storage.events if row[0] == "upload"]


def test_lease_transport_error_is_not_absence(harness: Harness) -> None:
    _, lease_name = close_v1._gcs_parts(close_v1.LEASE_URI)
    harness.storage.reload_failures[lease_name] = ConnectionError("network down")
    with pytest.raises(ConnectionError, match="network down"):
        harness.close()
    assert not [row for row in harness.storage.events if row[0] == "upload"]


def test_explicit_absence_probe_rejects_inconsistent_present_artifact(
    harness: Harness,
) -> None:
    _, smoke_name = close_v1._gcs_parts(close_v1.SMOKE_URI)
    harness.storage.objects[smoke_name] = {
        "raw": b"must-not-read",
        "generation": 4,
        "metageneration": 1,
        "time_created": datetime.now(timezone.utc),
    }
    claim_name = close_v1._gcs_parts(close_v1.JOB_CLAIM_URI)[1]
    harness.storage.list_override = [claim_name]
    with pytest.raises(RuntimeError, match="required absent is present"):
        harness.close()
    downloads = [row[1] for row in harness.storage.events if row[0] == "download"]
    assert smoke_name not in downloads


def test_create_only_collision_cannot_be_adopted(harness: Harness) -> None:
    harness.storage.collision = True
    with pytest.raises(RuntimeError, match="already occupied"):
        harness.close()
    assert not (harness.out / close_v1.DEFAULT_RELEASE_OBJECT.name).exists()


def test_release_validator_rejects_license_or_successor_poison(
    harness: Harness,
) -> None:
    harness.close()
    release_path = harness.out / close_v1.DEFAULT_RELEASE.name
    release = json.loads(release_path.read_text(encoding="utf-8"))
    poison = copy.deepcopy(release)
    poison["licenses"]["production_change_licensed"] = True
    with pytest.raises(RuntimeError, match="licenses differ"):
        close_v1.validate_failure_logical_release(poison)
    poison = copy.deepcopy(release)
    poison["next_run_id"] = close_v1.RUN_ID
    with pytest.raises(RuntimeError, match="fields differ"):
        close_v1.validate_failure_logical_release(poison)


def test_module_has_no_job_mutation_or_outcome_client_surface() -> None:
    source = (ROOT / "scripts/close_a7_select_ladder_failed_preflight_v1.py").read_text(
        encoding="utf-8",
    )
    assert "from google.cloud import bigquery" not in source
    assert "jobs\", \"execute" not in source
    assert "jobs\", \"deploy" not in source
    assert ".delete(" not in source
    assert "acquire(" not in source
    assert source.count("upload_from_string(") == 1
