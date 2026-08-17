from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import md5, sha256
import json
from pathlib import Path
import sys
from typing import Any

from google.api_core.exceptions import NotFound, PreconditionFailed
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


import heavy_experiment_lease as lease  # noqa: E402


NOW = datetime(2026, 8, 17, 20, 0, tzinfo=timezone.utc)
CODE_SHA = "a" * 40
IMAGE = "us-central1-docker.pkg.dev/p/r/i@sha256:" + "b" * 64
PROTOCOL_SHA = "c" * 64
RUN_ID = "20260817-heavy-lease-test-v1"
JOB_FAMILY = "heavy-lease-test"
COMPLETION_URI = "gs://nfl-predictions-503414-raw/test/completion.json"


class FakeStore:
    def __init__(self) -> None:
        self.next_generation = 1
        self.current: dict[tuple[str, str], int] = {}
        self.versions: dict[tuple[str, str, int], dict[str, Any]] = {}
        self.events: list[tuple[Any, ...]] = []
        self.fail_next_delete = False
        self.fail_upload_name_contains_once: str | None = None
        self.replace_current_after_reload = False


class FakeClient:
    def __init__(self) -> None:
        self.store = FakeStore()

    def bucket(self, name: str) -> "FakeBucket":
        return FakeBucket(self.store, name)


class FakeBucket:
    def __init__(self, store: FakeStore, name: str) -> None:
        self.store = store
        self.name = name

    def blob(self, name: str, generation: int | None = None) -> "FakeBlob":
        return FakeBlob(self.store, self.name, name, generation)


class FakeBlob:
    def __init__(
        self, store: FakeStore, bucket: str, name: str,
        generation: int | None,
    ) -> None:
        self.store = store
        self.bucket = bucket
        self.name = name
        self._requested_generation = generation
        self.generation: int | None = generation
        self.md5_hash: str | None = None
        self.crc32c: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        return self.bucket, self.name

    def _version(self) -> dict[str, Any]:
        generation = self._requested_generation
        if generation is None:
            generation = self.store.current.get(self.key)
        if generation is None:
            raise NotFound("object absent")
        value = self.store.versions.get((*self.key, int(generation)))
        if value is None or value.get("deleted"):
            raise NotFound("generation absent")
        return value

    def upload_from_string(self, raw: bytes, **kwargs: Any) -> None:
        self.store.events.append(("upload", self.key, kwargs.copy()))
        needle = self.store.fail_upload_name_contains_once
        if needle is not None and needle in self.name:
            self.store.fail_upload_name_contains_once = None
            raise RuntimeError("injected upload interruption")
        if kwargs.get("if_generation_match") != 0:
            raise AssertionError("fake requires create-only upload")
        if self.key in self.store.current:
            raise PreconditionFailed("occupied")
        generation = self.store.next_generation
        self.store.next_generation += 1
        digest = base64.b64encode(md5(raw).digest()).decode("ascii")  # noqa: S324
        value = {
            "raw": bytes(raw),
            "generation": generation,
            "md5_hash": digest,
            "crc32c": f"crc-{generation}",
            "deleted": False,
        }
        self.store.current[self.key] = generation
        self.store.versions[(*self.key, generation)] = value
        self._requested_generation = generation
        self.generation = generation
        self.md5_hash = value["md5_hash"]
        self.crc32c = value["crc32c"]

    def reload(self, **kwargs: Any) -> None:
        value = self._version()
        expected = kwargs.get("if_generation_match")
        if expected is not None and int(expected) != int(value["generation"]):
            raise PreconditionFailed("generation changed")
        self.generation = int(value["generation"])
        self.md5_hash = str(value["md5_hash"])
        self.crc32c = str(value["crc32c"])
        self.store.events.append(("reload", self.key, self.generation, kwargs.copy()))
        if (
            self._requested_generation is None
            and self.store.replace_current_after_reload
            and self.key == _active_key()
        ):
            self.store.replace_current_after_reload = False
            value["deleted"] = True
            successor_generation = self.store.next_generation
            self.store.next_generation += 1
            successor = {
                **value,
                "generation": successor_generation,
                "crc32c": f"crc-{successor_generation}",
                "deleted": False,
            }
            self.store.versions[
                (*self.key, successor_generation)
            ] = successor
            self.store.current[self.key] = successor_generation

    def download_as_bytes(self, **kwargs: Any) -> bytes:
        value = self._version()
        expected = kwargs.get("if_generation_match")
        if expected is not None and int(expected) != int(value["generation"]):
            raise PreconditionFailed("generation changed")
        self.store.events.append(
            ("download", self.key, int(value["generation"]), kwargs.copy()),
        )
        return bytes(value["raw"])

    def delete(self, **kwargs: Any) -> None:
        value = self._version()
        expected = kwargs.get("if_generation_match")
        self.store.events.append(
            ("delete", self.key, int(value["generation"]), kwargs.copy()),
        )
        if self.store.fail_next_delete:
            self.store.fail_next_delete = False
            raise RuntimeError("injected delete interruption")
        if expected is None or int(expected) != int(value["generation"]):
            raise PreconditionFailed("generation changed")
        value["deleted"] = True
        if self.store.current.get(self.key) == int(value["generation"]):
            del self.store.current[self.key]


def _now() -> datetime:
    return NOW


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _active_key() -> tuple[str, str]:
    return lease._parse_gcs(lease.LEASE_URI)


def _acquire(tmp_path: Path, client: FakeClient,
             *, now=_now) -> tuple[Path, dict[str, Any]]:
    receipt_path = tmp_path / "acquisition.json"
    value = lease.acquire(
        run_id=RUN_ID,
        job_family=JOB_FAMILY,
        code_sha=CODE_SHA,
        image=IMAGE,
        protocol_sha256=PROTOCOL_SHA,
        receipt_path=receipt_path,
        client=client,
        now=now,
    )
    return receipt_path, value


def _completion(
    acquisition: dict[str, Any], *, release_class: str = "terminal-success",
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "version": lease.COMPLETION_VERSION,
        "run_id": RUN_ID,
        "job_family": JOB_FAMILY,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "protocol_sha256": PROTOCOL_SHA,
        "lease": {
            "uri": lease.LEASE_URI,
            "generation": acquisition["object"]["generation"],
            "sha256": acquisition["object"]["sha256"],
        },
        "release_class": release_class,
        "full_population_terminal": True,
        "strict_harvest_complete": True,
        "expected_executions": 3,
        "terminal_executions": 3,
        "succeeded_executions": 3,
        "failed_executions": 0,
        "cancelled_executions": 0,
        "nonterminal_executions": 0,
        "uses_realized_outcomes": False,
        "completed_at": "2026-08-17T20:30:00+00:00",
    }
    if release_class == "terminal-fail-closed":
        value["fail_closed_reason"] = "strict population validation failed"
    return value


def _put_completion(
    tmp_path: Path, client: FakeClient, value: dict[str, Any],
    *, uri: str = COMPLETION_URI,
) -> Path:
    identity = {
        "run_id": RUN_ID,
        "job_family": JOB_FAMILY,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "protocol_sha256": PROTOCOL_SHA,
    }
    lease_binding = dict(value["lease"])
    execution_rows = [
        {
            "job": f"heavy-lease-cell-{index}",
            "execution": f"heavy-lease-cell-{index}-abc",
        }
        for index in range(1, 4)
    ]
    population = {
        "version": lease.REGISTERED_POPULATION_VERSION,
        **identity,
        "lease": lease_binding,
        "expected_executions": 3,
        "executions": execution_rows,
        "registered_at": "2026-08-17T20:10:00+00:00",
    }
    population_reference = lease._upload_create_only(
        client, "gs://nfl-predictions-503414-raw/test/population.json",
        lease._canonical_json(population),
    )
    census_rows = []
    receipt_rows = []
    for index, row in enumerate(execution_rows, 1):
        completion_time = "2026-08-17T20:20:00+00:00"
        execution_receipt = {
            "version": lease.TERMINAL_EXECUTION_VERSION,
            **identity,
            "lease": lease_binding,
            **row,
            "terminal_state": "succeeded",
            "completion_time": completion_time,
            "cloud_run_execution": {
                "metadata": {"name": row["execution"]},
                "spec": {"taskCount": 1},
                "status": {
                    "conditions": [{"type": "Completed", "status": "True"}],
                    "succeededCount": 1,
                    "failedCount": 0,
                    "completionTime": completion_time,
                },
            },
        }
        execution_reference = lease._upload_create_only(
            client,
            f"gs://nfl-predictions-503414-raw/test/execution-{index}.json",
            lease._canonical_json(execution_receipt),
        )
        census_rows.append({
            **row,
            "terminal_state": "succeeded",
            "completion_time": completion_time,
            "execution_receipt_object": execution_reference,
        })
        receipt_rows.append({
            "job": row["job"], "execution": row["execution"],
            "object": execution_reference,
        })
    receipt_sha = sha256(lease._canonical_json({
        "execution_receipts": receipt_rows,
    })).hexdigest()
    census = {
        "version": lease.TERMINAL_CENSUS_VERSION,
        **identity,
        "lease": lease_binding,
        "registered_population_object": lease._object_binding(
            population_reference,
        ),
        "executions": census_rows,
        "execution_receipts_sha256": receipt_sha,
        "censused_at": "2026-08-17T20:25:00+00:00",
    }
    census_reference = lease._upload_create_only(
        client, "gs://nfl-predictions-503414-raw/test/census.json",
        lease._canonical_json(census),
    )
    harvest = {
        "version": lease.STRICT_HARVEST_VERSION,
        **identity,
        "lease": lease_binding,
        "registered_population_object": lease._object_binding(
            population_reference,
        ),
        "terminal_census_object": lease._object_binding(census_reference),
        "release_class": value["release_class"],
        "full_population_terminal": True,
        "strict_harvest_complete": True,
        "disposition": "valid-terminal-closure",
        "artifact_receipts_sha256": "f" * 64,
        "uses_realized_outcomes": False,
        "harvested_at": "2026-08-17T20:28:00+00:00",
    }
    if value["release_class"] == "terminal-fail-closed":
        harvest["fail_closed_reason"] = "strict population validation failed"
    harvest_reference = lease._upload_create_only(
        client, "gs://nfl-predictions-503414-raw/test/harvest.json",
        lease._canonical_json(harvest),
    )
    value.update({
        "registered_population_object": population_reference,
        "terminal_census_object": census_reference,
        "strict_harvest_object": harvest_reference,
        "terminal_execution_receipts_sha256": receipt_sha,
        "strict_harvest_sha256": harvest_reference["sha256"],
    })
    raw = lease._canonical_json(value)
    reference = lease._upload_create_only(client, uri, raw)
    path = tmp_path / "completion-reference.json"
    _write_json(path, {
        "version": lease.COMPLETION_REFERENCE_VERSION,
        "object": reference,
    })
    return path


def _recovery_authorization(
    audit_path: Path, audit_value: dict[str, Any],
) -> dict[str, Any]:
    obj = audit_value["object"]
    return {
        "version": lease.RECOVERY_AUTH_VERSION,
        "lease_uri": lease.LEASE_URI,
        "lease_generation": obj["generation"],
        "lease_sha256": obj["sha256"],
        "audit_sha256": sha256(audit_path.read_bytes()).hexdigest(),
        "run_id": RUN_ID,
        "job_family": JOB_FAMILY,
        "operator": "test-operator",
        "reason": "durable evidence proves the abandoned test run is terminal",
        "authorized_at": "2026-08-17T21:00:00+00:00",
        "confirmed_run_abandoned": True,
        "confirmed_no_live_cloud_executions": True,
        "confirmed_no_live_local_launchers": True,
        "permit_exact_generation_delete": True,
        "evidence": ["cloud execution census terminal", "local watcher census empty"],
    }


def _upload_names(client: FakeClient) -> list[str]:
    return [event[1][1] for event in client.store.events if event[0] == "upload"]


def test_acquire_is_atomic_generation_zero_and_content_verified(tmp_path):
    client = FakeClient()
    receipt_path, value = _acquire(tmp_path, client)

    assert receipt_path.exists()
    assert value["lease"] == {
        "version": lease.LEASE_VERSION,
        "run_id": RUN_ID,
        "job_family": JOB_FAMILY,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "protocol_sha256": PROTOCOL_SHA,
        "acquired_at": NOW.isoformat(),
    }
    assert value["object"]["uri"] == lease.LEASE_URI
    assert value["object"]["generation"].isdigit()
    assert value["object"]["create_only"] is True
    upload = next(event for event in client.store.events if event[0] == "upload")
    assert upload[2]["if_generation_match"] == 0
    assert any(event[0] == "download" for event in client.store.events)


def test_acquire_refuses_occupied_lease_without_overwrite_or_delete(tmp_path):
    client = FakeClient()
    _receipt, first = _acquire(tmp_path, client)
    active_key = _active_key()
    original_generation = client.store.current[active_key]

    with pytest.raises(RuntimeError, match="occupied.*never expire"):
        lease.acquire(
            run_id="20260817-another-heavy-run",
            job_family="another-heavy-job",
            code_sha="f" * 40,
            image="x@sha256:" + "1" * 64,
            protocol_sha256="2" * 64,
            receipt_path=tmp_path / "second.json",
            client=client,
            now=_now,
        )

    assert client.store.current[active_key] == original_generation
    assert first["object"]["generation"] == str(original_generation)
    assert not any(event[0] == "delete" for event in client.store.events)


def test_acquire_refuses_preexisting_local_receipt_before_cloud_write(tmp_path):
    client = FakeClient()
    receipt_path = tmp_path / "existing.json"
    receipt_path.write_text("operator-owned\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="receipt already exists"):
        lease.acquire(
            run_id=RUN_ID,
            job_family=JOB_FAMILY,
            code_sha=CODE_SHA,
            image=IMAGE,
            protocol_sha256=PROTOCOL_SHA,
            receipt_path=receipt_path,
            client=client,
            now=_now,
        )

    assert client.store.events == []
    assert receipt_path.read_text(encoding="utf-8") == "operator-owned\n"


def test_audit_never_expires_or_deletes_an_old_lease(tmp_path):
    client = FakeClient()
    old = lambda: datetime(2018, 1, 1, tzinfo=timezone.utc)
    receipt_path, _value = _acquire(tmp_path, client, now=old)
    audit_path = tmp_path / "audit.json"

    report = lease.audit(
        receipt_path=receipt_path,
        output_path=audit_path,
        client=client,
        now=_now,
    )

    assert report["status"] == "occupied-valid"
    assert report["lease"]["acquired_at"].startswith("2018-")
    assert report["age_evaluated"] is False
    assert report["automatic_expiry_permitted"] is False
    assert report["delete_attempted"] is False
    assert _active_key() in client.store.current
    assert not any(event[0] == "delete" for event in client.store.events)


def test_audit_reports_malformed_occupied_object_without_deleting(tmp_path):
    client = FakeClient()
    lease._upload_create_only(client, lease.LEASE_URI, b"not-json\n")

    report = lease.audit(
        output_path=tmp_path / "malformed-audit.json",
        client=client,
        now=_now,
    )

    assert report["status"] == "occupied-invalid"
    assert report["lease"] is None
    assert report["validation_errors"]
    assert _active_key() in client.store.current
    assert not any(event[0] == "delete" for event in client.store.events)


def test_audit_retries_generation_change_instead_of_reporting_absent(tmp_path):
    client = FakeClient()
    _receipt_path, first = _acquire(tmp_path, client)
    client.store.replace_current_after_reload = True

    report = lease.audit(client=client, now=_now)

    assert report["status"] == "occupied-valid"
    assert int(report["object"]["generation"]) > int(
        first["object"]["generation"],
    )
    assert report["delete_attempted"] is False


def test_normal_release_requires_durable_terminal_receipt_and_orders_records(
    tmp_path,
):
    client = FakeClient()
    receipt_path, acquisition = _acquire(tmp_path, client)
    completion_reference = _put_completion(
        tmp_path, client, _completion(acquisition),
    )
    output = tmp_path / "released.json"

    result = lease.release(
        receipt_path=receipt_path,
        completion_reference_path=completion_reference,
        release_receipt_path=output,
        client=client,
        now=_now,
    )

    assert result["exact_generation_delete_completed"] is True
    assert _active_key() not in client.store.current
    assert output.exists()
    uploads = [
        (index, event[1][1]) for index, event in enumerate(client.store.events)
        if event[0] == "upload"
    ]
    deletes = [
        (index, event) for index, event in enumerate(client.store.events)
        if event[0] == "delete"
    ]
    intent_index = next(
        index for index, name in uploads
        if "heavy-experiment-release-intents-v1" in name
    )
    completion_index = next(
        index for index, name in uploads
        if "heavy-experiment-release-completions-v1" in name
    )
    delete_index, delete_event = deletes[-1]
    assert intent_index < delete_index < completion_index
    assert delete_event[2] == int(acquisition["object"]["generation"])
    assert delete_event[3]["if_generation_match"] == delete_event[2]


def test_self_declared_terminal_envelope_without_evidence_cannot_release(tmp_path):
    client = FakeClient()
    receipt_path, acquisition = _acquire(tmp_path, client)
    raw = lease._canonical_json(_completion(acquisition))
    envelope_reference = lease._upload_create_only(
        client, COMPLETION_URI, raw,
    )
    reference_path = tmp_path / "completion-reference.json"
    _write_json(reference_path, {
        "version": lease.COMPLETION_REFERENCE_VERSION,
        "object": envelope_reference,
    })

    with pytest.raises(RuntimeError, match="object receipt schema differs"):
        lease.release(
            receipt_path=receipt_path,
            completion_reference_path=reference_path,
            release_receipt_path=tmp_path / "release.json",
            client=client,
            now=_now,
        )

    assert _active_key() in client.store.current
    assert not any(event[0] == "delete" for event in client.store.events)


def test_terminal_execution_receipt_requires_real_terminal_cloud_metadata(tmp_path):
    client = FakeClient()
    _receipt_path, acquisition = _acquire(tmp_path, client)
    completion_time = "2026-08-17T20:20:00+00:00"
    execution = "heavy-lease-cell-1-abc"
    value = {
        "version": lease.TERMINAL_EXECUTION_VERSION,
        "run_id": RUN_ID,
        "job_family": JOB_FAMILY,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "protocol_sha256": PROTOCOL_SHA,
        "lease": {
            "uri": lease.LEASE_URI,
            "generation": acquisition["object"]["generation"],
            "sha256": acquisition["object"]["sha256"],
        },
        "job": "heavy-lease-cell-1",
        "execution": execution,
        "terminal_state": "succeeded",
        "completion_time": completion_time,
        "cloud_run_execution": {
            "metadata": {"name": execution},
            "spec": {"taskCount": 1},
            "status": {
                "conditions": [{"type": "Completed", "status": "Unknown"}],
                "completionTime": completion_time,
                "succeededCount": 1,
            },
        },
    }

    with pytest.raises(RuntimeError, match="not terminal"):
        lease._validate_terminal_execution_receipt(
            value,
            lease=acquisition["lease"],
            lease_binding=value["lease"],
            job="heavy-lease-cell-1",
            execution=execution,
            expected_state="succeeded",
            expected_completion_time=completion_time,
        )
    assert _active_key() in client.store.current
    assert not any(event[0] == "delete" for event in client.store.events)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(full_population_terminal=False), "full-population"),
        (lambda value: value.update(strict_harvest_complete=False), "strict"),
        (lambda value: value.update(nonterminal_executions=1), "population counts"),
        (
            lambda value: value.update(
                succeeded_executions=2, failed_executions=1,
            ),
            "immutable census",
        ),
        (
            lambda value: value.update(
                release_class="terminal-fail-closed",
            ),
            "lacks a reason",
        ),
    ],
)
def test_release_rejects_nonterminal_or_unstrict_completion_without_deletion(
    tmp_path, mutation, message,
):
    client = FakeClient()
    receipt_path, acquisition = _acquire(tmp_path, client)
    completion = _completion(acquisition)
    mutation(completion)
    reference = _put_completion(tmp_path, client, completion)

    with pytest.raises(RuntimeError, match=message):
        lease.release(
            receipt_path=receipt_path,
            completion_reference_path=reference,
            release_receipt_path=tmp_path / "release.json",
            client=client,
            now=_now,
        )

    assert _active_key() in client.store.current
    assert not any(event[0] == "delete" for event in client.store.events)
    assert not any("release-intents" in name for name in _upload_names(client))


def test_release_rejects_completion_hash_or_generation_mismatch(tmp_path):
    client = FakeClient()
    receipt_path, acquisition = _acquire(tmp_path, client)
    reference_path = _put_completion(tmp_path, client, _completion(acquisition))
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    reference["object"]["sha256"] = "9" * 64
    _write_json(reference_path, reference)

    with pytest.raises(RuntimeError, match="sha256 differs"):
        lease.release(
            receipt_path=receipt_path,
            completion_reference_path=reference_path,
            release_receipt_path=tmp_path / "release.json",
            client=client,
            now=_now,
        )
    assert _active_key() in client.store.current
    assert not any(event[0] == "delete" for event in client.store.events)


def test_release_rehashes_active_exact_generation_before_delete(tmp_path):
    client = FakeClient()
    receipt_path, acquisition = _acquire(tmp_path, client)
    reference = _put_completion(tmp_path, client, _completion(acquisition))
    generation = int(acquisition["object"]["generation"])
    stored = client.store.versions[(*_active_key(), generation)]
    stored["raw"] = b'{"tampered":true}\n'

    with pytest.raises(RuntimeError, match="active heavy-experiment lease.*differs"):
        lease.release(
            receipt_path=receipt_path,
            completion_reference_path=reference,
            release_receipt_path=tmp_path / "release.json",
            client=client,
            now=_now,
        )

    assert _active_key() in client.store.current
    assert not any(event[0] == "delete" for event in client.store.events)


def test_release_refuses_old_retained_generation_when_successor_is_current(
    tmp_path,
):
    client = FakeClient()
    first_receipt, first = _acquire(tmp_path, client)
    reference = _put_completion(tmp_path, client, _completion(first))
    # Model a versioned bucket: the old generation remains readable, but a
    # successor becomes the current active object.
    del client.store.current[_active_key()]
    second = lease.acquire(
        run_id="20260817-successor-heavy-run",
        job_family="successor-heavy-job",
        code_sha="1" * 40,
        image="x@sha256:" + "2" * 64,
        protocol_sha256="3" * 64,
        receipt_path=tmp_path / "successor.json",
        client=client,
        now=_now,
    )

    with pytest.raises(RuntimeError, match="not the current active lease"):
        lease.release(
            receipt_path=first_receipt,
            completion_reference_path=reference,
            release_receipt_path=tmp_path / "release.json",
            client=client,
            now=_now,
        )

    assert client.store.current[_active_key()] == int(
        second["object"]["generation"],
    )
    assert not any(event[0] == "delete" for event in client.store.events)


def test_fail_closed_terminal_population_can_release(tmp_path):
    client = FakeClient()
    receipt_path, acquisition = _acquire(tmp_path, client)
    reference = _put_completion(
        tmp_path, client,
        _completion(acquisition, release_class="terminal-fail-closed"),
    )

    lease.release(
        receipt_path=receipt_path,
        completion_reference_path=reference,
        release_receipt_path=tmp_path / "fail-closed-release.json",
        client=client,
        now=_now,
    )

    assert _active_key() not in client.store.current


def test_release_without_active_generation_requires_preexisting_intent(tmp_path):
    client = FakeClient()
    receipt_path, acquisition = _acquire(tmp_path, client)
    reference = _put_completion(tmp_path, client, _completion(acquisition))
    active = client.bucket(_active_key()[0]).blob(
        _active_key()[1], generation=int(acquisition["object"]["generation"]),
    )
    active.delete(if_generation_match=int(acquisition["object"]["generation"]))
    before = list(_upload_names(client))

    with pytest.raises(RuntimeError, match="absent without.*durable release intent"):
        lease.release(
            receipt_path=receipt_path,
            completion_reference_path=reference,
            release_receipt_path=tmp_path / "release.json",
            client=client,
            now=_now,
        )

    assert _upload_names(client) == before


def test_interrupted_exact_delete_resumes_only_from_matching_durable_intent(
    tmp_path,
):
    client = FakeClient()
    receipt_path, acquisition = _acquire(tmp_path, client)
    reference = _put_completion(tmp_path, client, _completion(acquisition))
    client.store.fail_next_delete = True

    with pytest.raises(RuntimeError, match="injected delete interruption"):
        lease.release(
            receipt_path=receipt_path,
            completion_reference_path=reference,
            release_receipt_path=tmp_path / "first.json",
            client=client,
            now=_now,
        )
    assert _active_key() in client.store.current
    assert sum("release-intents" in name for name in _upload_names(client)) == 1

    lease.release(
        receipt_path=receipt_path,
        completion_reference_path=reference,
        release_receipt_path=tmp_path / "second.json",
        client=client,
        now=_now,
    )
    assert _active_key() not in client.store.current
    # The second create-only attempt conflicts, verifies the first intent, and
    # does not create a second durable intent generation.
    intent_current = [
        key for key in client.store.current
        if "heavy-experiment-release-intents-v1" in key[1]
    ]
    assert len(intent_current) == 1


def test_release_resumes_after_delete_before_completion_record(tmp_path):
    client = FakeClient()
    receipt_path, acquisition = _acquire(tmp_path, client)
    reference = _put_completion(tmp_path, client, _completion(acquisition))
    client.store.fail_upload_name_contains_once = "release-completions-v1"

    with pytest.raises(RuntimeError, match="injected upload interruption"):
        lease.release(
            receipt_path=receipt_path,
            completion_reference_path=reference,
            release_receipt_path=tmp_path / "first.json",
            client=client,
            now=_now,
        )
    assert _active_key() not in client.store.current
    assert sum("release-intents" in name for name in _upload_names(client)) == 1

    result = lease.release(
        receipt_path=receipt_path,
        completion_reference_path=reference,
        release_receipt_path=tmp_path / "second.json",
        client=client,
        now=_now,
    )
    assert result["active_state_after_target_release"]["status"] == (
        "globally-absent"
    )
    assert _active_key() not in client.store.current


def test_operator_recovery_is_explicit_audited_and_exact_generation_only(
    tmp_path,
):
    client = FakeClient()
    _receipt_path, acquisition = _acquire(tmp_path, client)
    audit_path = tmp_path / "audit.json"
    audit_value = lease.audit(output_path=audit_path, client=client, now=_now)
    authorization = _recovery_authorization(audit_path, audit_value)
    authorization_path = tmp_path / "authorization.json"
    _write_json(authorization_path, authorization)

    result = lease.recover(
        audit_path=audit_path,
        authorization_path=authorization_path,
        recovery_receipt_path=tmp_path / "recovery.json",
        confirm_generation=acquisition["object"]["generation"],
        confirm_sha256=acquisition["object"]["sha256"],
        confirm_run_id=RUN_ID,
        client=client,
        now=_now,
    )

    assert result["exact_generation_delete_completed"] is True
    assert result["operator"] == "test-operator"
    assert _active_key() not in client.store.current
    assert any("recovery-inputs-v1/audit-" in name for name in _upload_names(client))
    assert any(
        "recovery-inputs-v1/authorization-" in name
        for name in _upload_names(client)
    )
    uploads = [
        (i, event[1][1]) for i, event in enumerate(client.store.events)
        if event[0] == "upload"
    ]
    delete_index = max(
        i for i, event in enumerate(client.store.events) if event[0] == "delete"
    )
    intent_index = next(i for i, name in uploads if "recovery-intents" in name)
    completion_index = next(
        i for i, name in uploads if "recovery-completions" in name
    )
    assert intent_index < delete_index < completion_index


def test_operator_recovery_resumes_after_delete_before_completion_record(
    tmp_path,
):
    client = FakeClient()
    _receipt_path, acquisition = _acquire(tmp_path, client)
    audit_path = tmp_path / "audit.json"
    audit_value = lease.audit(output_path=audit_path, client=client, now=_now)
    authorization_path = tmp_path / "authorization.json"
    _write_json(
        authorization_path, _recovery_authorization(audit_path, audit_value),
    )
    client.store.fail_upload_name_contains_once = "recovery-completions-v1"

    kwargs = {
        "audit_path": audit_path,
        "authorization_path": authorization_path,
        "confirm_generation": acquisition["object"]["generation"],
        "confirm_sha256": acquisition["object"]["sha256"],
        "confirm_run_id": RUN_ID,
        "client": client,
        "now": _now,
    }
    with pytest.raises(RuntimeError, match="injected upload interruption"):
        lease.recover(
            **kwargs,
            recovery_receipt_path=tmp_path / "first-recovery.json",
        )
    assert _active_key() not in client.store.current

    result = lease.recover(
        **kwargs,
        recovery_receipt_path=tmp_path / "second-recovery.json",
    )
    assert result["active_state_after_target_release"]["status"] == (
        "globally-absent"
    )


@pytest.mark.parametrize(
    "field",
    [
        "confirmed_run_abandoned",
        "confirmed_no_live_cloud_executions",
        "confirmed_no_live_local_launchers",
        "permit_exact_generation_delete",
    ],
)
def test_operator_recovery_refuses_missing_confirmation_without_delete(
    tmp_path, field,
):
    client = FakeClient()
    _receipt_path, acquisition = _acquire(tmp_path, client)
    audit_path = tmp_path / "audit.json"
    audit_value = lease.audit(output_path=audit_path, client=client, now=_now)
    authorization = _recovery_authorization(audit_path, audit_value)
    authorization[field] = False
    authorization_path = tmp_path / "authorization.json"
    _write_json(authorization_path, authorization)

    with pytest.raises(RuntimeError, match="confirmation"):
        lease.recover(
            audit_path=audit_path,
            authorization_path=authorization_path,
            recovery_receipt_path=tmp_path / "recovery.json",
            confirm_generation=acquisition["object"]["generation"],
            confirm_sha256=acquisition["object"]["sha256"],
            confirm_run_id=RUN_ID,
            client=client,
            now=_now,
        )
    assert _active_key() in client.store.current
    assert not any(event[0] == "delete" for event in client.store.events)


def test_recovery_audit_cannot_delete_a_reacquired_generation(tmp_path):
    client = FakeClient()
    first_receipt, first = _acquire(tmp_path, client)
    audit_path = tmp_path / "audit.json"
    audit_value = lease.audit(output_path=audit_path, client=client, now=_now)
    authorization_path = tmp_path / "authorization.json"
    _write_json(
        authorization_path, _recovery_authorization(audit_path, audit_value),
    )
    active = client.bucket(_active_key()[0]).blob(
        _active_key()[1], generation=int(first["object"]["generation"]),
    )
    active.delete(if_generation_match=int(first["object"]["generation"]))
    second_receipt = tmp_path / "second-acquisition.json"
    second = lease.acquire(
        run_id="20260817-second-heavy-run",
        job_family="second-heavy-job",
        code_sha="1" * 40,
        image="x@sha256:" + "2" * 64,
        protocol_sha256="3" * 64,
        receipt_path=second_receipt,
        client=client,
        now=_now,
    )
    before_deletes = sum(event[0] == "delete" for event in client.store.events)

    with pytest.raises(RuntimeError, match="absent without.*recovery intent"):
        lease.recover(
            audit_path=audit_path,
            authorization_path=authorization_path,
            recovery_receipt_path=tmp_path / "recovery.json",
            confirm_generation=first["object"]["generation"],
            confirm_sha256=first["object"]["sha256"],
            confirm_run_id=RUN_ID,
            client=client,
            now=_now,
        )

    assert client.store.current[_active_key()] == int(
        second["object"]["generation"],
    )
    assert sum(event[0] == "delete" for event in client.store.events) == before_deletes
    assert first_receipt.exists()


def test_operator_recovery_requires_independent_exact_cli_confirmation(tmp_path):
    client = FakeClient()
    _receipt_path, acquisition = _acquire(tmp_path, client)
    audit_path = tmp_path / "audit.json"
    audit_value = lease.audit(output_path=audit_path, client=client, now=_now)
    authorization_path = tmp_path / "authorization.json"
    _write_json(
        authorization_path, _recovery_authorization(audit_path, audit_value),
    )

    with pytest.raises(RuntimeError, match="exact identity differs"):
        lease.recover(
            audit_path=audit_path,
            authorization_path=authorization_path,
            recovery_receipt_path=tmp_path / "recovery.json",
            confirm_generation=acquisition["object"]["generation"],
            confirm_sha256="0" * 64,
            confirm_run_id=RUN_ID,
            client=client,
            now=_now,
        )

    assert _active_key() in client.store.current
    assert not any(event[0] == "delete" for event in client.store.events)


def test_duplicate_json_keys_fail_closed_before_recovery_delete(tmp_path):
    client = FakeClient()
    _receipt_path, acquisition = _acquire(tmp_path, client)
    audit_path = tmp_path / "audit.json"
    audit_value = lease.audit(output_path=audit_path, client=client, now=_now)
    authorization = _recovery_authorization(audit_path, audit_value)
    raw = json.dumps(authorization, separators=(",", ":"))
    raw = raw[:-1] + ',"operator":"duplicate"}'
    authorization_path = tmp_path / "duplicate-authorization.json"
    authorization_path.write_text(raw, encoding="utf-8")

    with pytest.raises(RuntimeError, match="not strict JSON"):
        lease.recover(
            audit_path=audit_path,
            authorization_path=authorization_path,
            recovery_receipt_path=tmp_path / "recovery.json",
            confirm_generation=acquisition["object"]["generation"],
            confirm_sha256=acquisition["object"]["sha256"],
            confirm_run_id=RUN_ID,
            client=client,
            now=_now,
        )
    assert _active_key() in client.store.current
    assert not any(event[0] == "delete" for event in client.store.events)
