"""Focused offline tests for the realized Cloud Run and lease lifecycle."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sys
from typing import Mapping

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_realized_cloud_transport as transport
from nfl_dfs.research import corpus_realized_outcome_transport as outcomes
from nfl_dfs.research import lr8_label_fit_adapter as lease_adapter


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
import run_corpus_realized_outcomes as worker  # noqa: E402


RUN_ID = "20260821-corpus-realized-suite-v1"
BUILD_ID = "11111111-1111-1111-1111-111111111111"
CODE_SHA = "a" * 40
IMAGE = "us-central1-docker.pkg.dev/p/r/i@sha256:" + "b" * 64
JOB = "corpus-realized-job"
JOB_UID = "fixture-job-uid"
SERVICE_ACCOUNT = "corpus-realized@nfl-predictions-503414.iam.gserviceaccount.com"


class MemoryStore:
    def __init__(self) -> None:
        self.values: dict[str, tuple[dict[str, object], bytes]] = {}
        self.next_generation = 1000
        self.deleted: list[dict[str, object]] = []

    def read(self, identity: Mapping[str, object]) -> bytes:
        retained, raw = self.values[str(identity["uri"])]
        assert all(retained[key] == identity[key] for key in (
            "uri", "generation", "sha256", "bytes"
        ))
        return raw

    def resolve(self, uri: str) -> tuple[dict[str, object], bytes] | None:
        value = self.values.get(uri)
        if value is None:
            return None
        return deepcopy(value[0]), value[1]

    def publish_or_reopen(self, uri: str, raw: bytes) -> dict[str, object]:
        existing = self.values.get(uri)
        if existing is not None:
            if existing[1] != raw:
                raise RuntimeError("create-once collision")
            return deepcopy(existing[0])
        self.next_generation += 1
        identity = {
            "uri": uri,
            "generation": str(self.next_generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.values[uri] = (identity, raw)
        return deepcopy(identity)

    def delete_exact(self, identity: Mapping[str, object]) -> None:
        retained, _ = self.values[str(identity["uri"])]
        assert retained == identity
        self.deleted.append(dict(identity))
        del self.values[str(identity["uri"])]


def _identity(uri: str, seed: str) -> transport.ObjectIdentity:
    raw = seed.encode()
    return transport.ObjectIdentity(
        uri=uri,
        generation="11",
        sha256=sha256(raw).hexdigest(),
        bytes=len(raw),
    )


def _config(*, run_id: str = RUN_ID) -> transport.RunConfig:
    return transport.RunConfig(
        run_id=run_id,
        build_id=BUILD_ID,
        code_sha=CODE_SHA,
        image=IMAGE,
        job_name=JOB,
        job_uid=JOB_UID,
        service_account=SERVICE_ACCOUNT,
        batch_acceptance=_identity(
            "gs://fixture-batch/governance/batch-acceptance.json",
            "accepted-batch",
        ),
    )


def _task_spec(config: transport.RunConfig) -> dict[str, object]:
    return {
        "containers": [{
            "args": list(transport.PARKED_ARGS),
            "command": list(transport.PARKED_COMMAND),
            "env": [{"name": name, "value": value} for name, value in {
                transport.ENABLE_ENV: "1",
                transport.WORKER_ENABLE_ENV: "1",
                transport.IMAGE_ENV: config.image,
                transport.BUILD_ENV: config.build_id,
                transport.CODE_ENV: config.code_sha,
            }.items()],
            "image": config.image,
            "resources": {"limits": dict(transport.EXPECTED_RESOURCES)},
        }],
        "maxRetries": 0,
        "serviceAccountName": config.service_account,
        "timeoutSeconds": transport.EXPECTED_TIMEOUT_SECONDS,
    }


def _job(config: transport.RunConfig) -> dict[str, object]:
    return {
        "metadata": {
            "name": config.job_name,
            "uid": config.job_uid,
            "generation": 7,
        },
        "spec": {"template": {"spec": {
            "parallelism": 1,
            "taskCount": 1,
            "template": {"spec": _task_spec(config)},
        }}},
        "status": {
            "observedGeneration": 7,
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }


def _execution(
    config: transport.RunConfig,
    *,
    execution_id: str,
    terminal: bool,
    worker_args: list[str] | None = None,
) -> dict[str, object]:
    task = _task_spec(config)
    task["containers"][0]["args"] = worker_args or list(transport.PARKED_ARGS)
    status: dict[str, object] = {
        "conditions": [{
            "type": "Completed", "status": "True" if terminal else "Unknown",
        }],
    }
    if terminal:
        status.update({
            "succeededCount": 1,
            "failedCount": 0,
            "cancelledCount": 0,
            "retriedCount": 0,
            "completionTime": "2026-08-21T21:00:00Z",
        })
    return {
        "metadata": {
            "name": execution_id,
            "uid": f"uid-{execution_id}",
            "labels": {
                "run.googleapis.com/job": config.job_name,
                "run.googleapis.com/jobUid": config.job_uid,
                "run.googleapis.com/jobGeneration": "7",
            },
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": task},
        },
        "status": status,
    }


def _census_row(execution: Mapping[str, object]) -> dict[str, object]:
    return {
        "metadata": deepcopy(execution["metadata"]),
        "status": deepcopy(execution["status"]),
    }


def _graph(config: transport.RunConfig) -> outcomes.AcceptedBatchGraph:
    manifest_identity = _identity(
        "gs://fixture-batch/governance/batch-manifest.json", "manifest"
    ).as_dict()
    return outcomes.AcceptedBatchGraph(
        manifest={
            "batch_manifest_sha256": "c" * 64,
            "output_prefix": "gs://fixture-batch/",
        },
        manifest_identity=manifest_identity,
        completion={},
        completion_identity={},
        acceptance={},
        acceptance_identity=config.batch_acceptance.as_dict(),
        accepted_tasks=(),
        source_freeze={},
        source_freeze_identity={},
        outcome_keys=(),
        generated_unique_membership_count=0,
        distinct_task_roster_count=0,
    )


def _build() -> dict[str, str]:
    return {
        "build_id": BUILD_ID,
        "code_repository": "https://github.com/espechtsoftware/nfl-predictions.git",
        "code_sha": CODE_SHA,
        "image": IMAGE,
    }


def _seed_launch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    store: MemoryStore,
    config: transport.RunConfig,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    transport.acquire_historical_lease(
        storage=store,
        config=config,
        acquired_at_utc="2026-08-21T20:00:00+00:00",
    )
    old = _execution(
        config, execution_id=f"{config.job_name}-aaaaa", terminal=True
    )
    baseline = [_census_row(old)]
    monkeypatch.setattr(
        transport,
        "validate_build_metadata",
        lambda _value, *, config: _build(),
    )
    prepared = transport.prepare_launch(
        storage=store,
        config=config,
        build_metadata={},
        parked_job=_job(config),
        executions=baseline,
        schedulers=[],
        all_regions_complete=True,
        unused_proof=transport.query_unused_proof(
            config=config, observed_at_utc="2026-08-21T20:01:00Z"
        ),
        created_at_utc="2026-08-21T20:01:01+00:00",
        batch_reopener=lambda _storage, _config: _graph(config),
    )
    transport.confirm_query_unused(
        storage=store,
        config=config,
        unused_proof=transport.query_unused_proof(
            config=config, observed_at_utc="2026-08-21T20:01:02Z"
        ),
        created_at_utc="2026-08-21T20:01:03+00:00",
    )
    return prepared, baseline


def test_run_id_is_bounded_to_shared_lease_limit() -> None:
    valid = "a" + "b" * 80
    assert len(valid) == 81
    assert transport.validate_run_config(_config(run_id=valid)).run_id == valid
    with pytest.raises(
        transport.CorpusRealizedCloudTransportError, match="identity differs"
    ):
        transport.validate_run_config(_config(run_id=valid + "c"))


def test_lease_acquisition_is_create_once_pinned_and_collision_closed() -> None:
    store = MemoryStore()
    config = _config()
    first = transport.acquire_historical_lease(
        storage=store,
        config=config,
        acquired_at_utc="2026-08-21T20:00:00Z",
    )
    second = transport.acquire_historical_lease(
        storage=store,
        config=config,
        acquired_at_utc="2026-08-21T20:00:00+00:00",
    )
    assert first == second
    assert first["active_lease"]["uri"] == (
        lease_adapter.HISTORICAL_OUTCOME_LEASE_URI
    )
    with pytest.raises(transport.CorpusRealizedCloudTransportError):
        transport.acquire_historical_lease(
            storage=store,
            config=config,
            acquired_at_utc="2026-08-21T20:00:01Z",
        )


def test_launch_claim_intent_and_second_query_absence_are_durable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    config = _config()
    prepared, baseline = _seed_launch(monkeypatch, store=store, config=config)
    assert prepared["launch_request_count_remaining"] == 1
    intent_identity = prepared["launch_intent"]
    intent = batch.parse_canonical_json_bytes(
        store.read(intent_identity), label="intent"
    )
    assert intent["run"]["batch_acceptance"] == (
        config.batch_acceptance.as_dict()
    )
    assert intent["query_job_id"] == config.query_job_id
    assert intent["worker_args"][-8::2] == [
        "--historical-lease-receipt-uri",
        "--historical-lease-receipt-generation",
        "--historical-lease-receipt-sha256",
        "--historical-lease-receipt-bytes",
    ]
    assert intent["execution_names_before"] == transport.execution_names(baseline)
    assert store.resolve(
        f"{config.governance_root}/launch-claim.json"
    ) is not None
    assert store.resolve(
        f"{config.governance_root}/pre-execution-query-confirmation.json"
    ) is not None


def test_execution_binding_is_census_only_exactly_one_and_zero_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    config = _config()
    prepared, baseline = _seed_launch(monkeypatch, store=store, config=config)
    lease_identity = transport.ObjectIdentity.from_value(
        prepared["historical_lease_receipt"], label="lease receipt"
    )
    args = transport.worker_args(
        config=config, lease_receipt=lease_identity
    )
    execution = _execution(
        config,
        execution_id=f"{config.job_name}-bbbbb",
        terminal=False,
        worker_args=args,
    )
    after = [*baseline, _census_row(execution)]
    bound = transport.bind_execution(
        storage=store,
        config=config,
        execution=execution,
        parked_job=_job(config),
        executions=after,
        schedulers=[],
        all_regions_complete=True,
        created_at_utc="2026-08-21T20:02:00Z",
    )
    assert bound["execution_id"] == f"{config.job_name}-bbbbb"
    assert bound["automatic_retry_licensed"] is False
    with pytest.raises(
        transport.CorpusRealizedCloudTransportError, match="ambiguous"
    ):
        transport.bind_execution(
            storage=store,
            config=config,
            execution=execution,
            parked_job=_job(config),
            executions=[*after, {
                **_census_row(execution),
                "metadata": {
                    **execution["metadata"],
                    "name": f"{config.job_name}-ccccc",
                },
            }],
            schedulers=[],
            all_regions_complete=True,
            created_at_utc="2026-08-21T20:02:00Z",
        )


def _bind_for_terminal(
    monkeypatch: pytest.MonkeyPatch,
    *,
    store: MemoryStore,
    config: transport.RunConfig,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    prepared, baseline = _seed_launch(monkeypatch, store=store, config=config)
    lease_identity = transport.ObjectIdentity.from_value(
        prepared["historical_lease_receipt"], label="lease receipt"
    )
    execution = _execution(
        config,
        execution_id=f"{config.job_name}-bbbbb",
        terminal=False,
        worker_args=transport.worker_args(
            config=config, lease_receipt=lease_identity
        ),
    )
    after = [*baseline, _census_row(execution)]
    transport.bind_execution(
        storage=store,
        config=config,
        execution=execution,
        parked_job=_job(config),
        executions=after,
        schedulers=[],
        all_regions_complete=True,
        created_at_utc="2026-08-21T20:02:00Z",
    )
    return execution, baseline


def test_terminal_acceptance_releases_generation_exactly_and_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    config = _config()
    running, baseline = _bind_for_terminal(
        monkeypatch, store=store, config=config
    )
    terminal_execution = deepcopy(running)
    terminal_execution["status"] = _execution(
        config,
        execution_id=f"{config.job_name}-bbbbb",
        terminal=True,
        worker_args=running["spec"]["template"]["spec"]["containers"][0]["args"],
    )["status"]
    census = [*baseline, _census_row(terminal_execution)]
    completion = {
        "run_id": config.run_id,
        "batch_acceptance": config.batch_acceptance.as_dict(),
        "one_historical_outcome_read": True,
        "independent_replay_complete": True,
        "historical_outcome_lease_release_required": True,
        "historical_retry_licensed": False,
        "decision_authority": False,
        "realized_grade_sha256": "d" * 64,
    }
    completion_raw = batch.canonical_json_bytes(completion)
    completion_identity = transport.ObjectIdentity.from_value(
        store.publish_or_reopen(
            f"{config.output_root}/realized-completion.json", completion_raw
        ),
        label="completion",
    )
    accepted = transport.finish_execution(
        storage=store,
        config=config,
        execution=terminal_execution,
        parked_job=_job(config),
        executions=census,
        schedulers=[],
        all_regions_complete=True,
        created_at_utc="2026-08-21T21:00:01Z",
        completion_validator=lambda _store, _config: (
            completion_identity, completion
        ),
    )
    assert accepted["historical_lease_release_required"] is True
    closed = transport.release_historical_lease(
        storage=store,
        config=config,
        created_at_utc="2026-08-21T21:00:02Z",
    )
    assert closed["disposition"] == "terminal-success-lease-released"
    assert store.resolve(lease_adapter.HISTORICAL_OUTCOME_LEASE_URI) is None
    assert len(store.deleted) == 1
    # Recovery after a successful delete reopens the same create-once receipt.
    assert transport.release_historical_lease(
        storage=store,
        config=config,
        created_at_utc="2026-08-21T21:00:02+00:00",
    ) == closed


def test_failure_archives_and_abandons_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    config = _config()
    _seed_launch(monkeypatch, store=store, config=config)
    abandoned = transport.abandon_historical_lease(
        storage=store,
        config=config,
        reason="terminal-execution-failed",
        created_at_utc="2026-08-21T21:10:00Z",
    )
    assert abandoned["disposition"] == "failed-closed-lease-abandoned"
    assert abandoned["automatic_retry_licensed"] is False
    assert store.resolve(lease_adapter.HISTORICAL_OUTCOME_LEASE_URI) is None
    assert store.resolve(
        f"{config.governance_root}/abandoned-historical-lease.json"
    ) is not None
    assert transport.abandon_historical_lease(
        storage=store,
        config=config,
        reason="terminal-execution-failed",
        created_at_utc="2026-08-21T21:10:00+00:00",
    ) == abandoned


class _Blob:
    def __init__(self, raw: bytes, generation: str) -> None:
        self.raw = raw
        self.generation = generation

    def reload(self, *, if_generation_match: int) -> None:
        assert str(if_generation_match) == self.generation

    def download_as_bytes(self, *, if_generation_match: int) -> bytes:
        assert str(if_generation_match) == self.generation
        return self.raw


class _Bucket:
    def __init__(self, raw: bytes, generation: str) -> None:
        self.raw = raw
        self.generation = generation

    def blob(self, _name: str, *, generation: int) -> _Blob:
        assert str(generation) == self.generation
        return _Blob(self.raw, self.generation)


class _StorageClient:
    def __init__(self, raw: bytes, generation: str) -> None:
        self.raw = raw
        self.generation = generation

    def bucket(self, _name: str) -> _Bucket:
        return _Bucket(self.raw, self.generation)


def test_worker_receives_nonsecret_lease_by_exact_gcs_identity() -> None:
    store = MemoryStore()
    config = _config()
    transport.acquire_historical_lease(
        storage=store,
        config=config,
        acquired_at_utc="2026-08-21T20:00:00Z",
    )
    identity = transport.lease_receipt_identity(store, config=config)
    raw = store.read(identity.as_dict())
    pin = worker.LeaseReceiptPin(
        uri=identity.uri,
        generation=identity.generation,
        sha256=identity.sha256,
        bytes=identity.bytes,
    )
    lease = worker._load_remote_lease_receipt(  # noqa: SLF001
        _StorageClient(raw, identity.generation), pin
    )
    supplier_config = outcomes.SupplierConfig(
        run_id=config.run_id,
        job=config.job_name,
        code_sha=config.code_sha,
        image=config.image,
        expected_batch_acceptance_object_sha256=config.batch_acceptance.sha256,
        enabled=True,
    )
    validated = worker._validate_lease_for_config(  # noqa: SLF001
        lease, config=supplier_config
    )
    assert validated["body"]["run_id"] == config.run_id
    bad = worker.LeaseReceiptPin(
        uri=pin.uri,
        generation=pin.generation,
        sha256="0" * 64,
        bytes=pin.bytes,
    )
    with pytest.raises(
        worker.CorpusRealizedOutcomeRunnerError, match="identity differs"
    ):
        worker._load_remote_lease_receipt(  # noqa: SLF001
            _StorageClient(raw, identity.generation), bad
        )


def test_worker_cloud_adapter_still_delegates_the_one_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()
    supplier_config = outcomes.SupplierConfig(
        run_id=config.run_id,
        job=config.job_name,
        code_sha=config.code_sha,
        image=config.image,
        expected_batch_acceptance_object_sha256=config.batch_acceptance.sha256,
        enabled=True,
    )
    captured: dict[str, object] = {}
    expected = object()
    monkeypatch.setattr(
        worker.cloud_boundary,
        "_LiveLeaseVerifier",
        lambda storage, lease: ("verifier", storage, lease),
    )
    monkeypatch.setattr(
        worker,
        "_CreateOncePublisher",
        lambda storage: ("publisher", storage),
    )

    def supply(**kwargs: object) -> object:
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(worker.supplier, "supply_realized_outcomes", supply)
    storage_client = object()
    lease = {"lease": "fixture"}
    result = worker.run_cloud(
        config=supplier_config,
        batch_pin=worker.BatchAcceptancePin(
            uri=config.batch_acceptance.uri,
            generation=config.batch_acceptance.generation,
            sha256=config.batch_acceptance.sha256,
            bytes=config.batch_acceptance.bytes,
        ),
        lease_contract=lease,
        bq_client=object(),
        storage_client=storage_client,
    )
    assert result is expected
    assert captured["config"] is supplier_config
    assert captured["batch_acceptance_identity"] == (
        config.batch_acceptance.as_dict()
    )
    assert captured["verify_lease"] == ("verifier", storage_client, lease)
    assert captured["publish"] == ("publisher", storage_client)


def test_reuse_shell_has_no_create_retry_or_secret_lease_delivery() -> None:
    shell = (ROOT / "scripts/cloud_corpus_realized_v1_reuse.sh").read_text()
    assert "resourceVersion" in shell
    assert "put_existing_job" in shell
    assert "--request PUT" in shell
    assert "CORPUS_REALIZED_ROLLBACK_ARMED=1" in shell
    assert "gcloud run jobs deploy" not in shell
    assert "gcloud run jobs create" not in shell
    assert "gcloud run jobs update" not in shell
    assert shell.count("gcloud run jobs execute") == 1
    assert "maxRetries: 0" in shell
    assert "capture_all_region_schedulers" in shell
    assert "launch outcome remained ambiguous; never relaunch" in shell
    assert "--historical-lease-receipt-uri" not in shell
    assert "worker_args" in shell
    assert "Secret Manager alias" in shell
    assert "release-lease" in shell and "abandon-lease" in shell
