from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from nfl_dfs.research import corpus_extreme_tail_panel_execution as execution
from nfl_dfs.research import corpus_extreme_tail_panel_transport as transport


ROOT = Path(__file__).resolve().parents[1]
IMAGE = {
    "uri": "us-central1-docker.pkg.dev/example/research/t230@sha256:"
    + "b" * 64,
    "digest": "sha256:" + "b" * 64,
}


def _load_cli():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    path = ROOT / "scripts/run_corpus_extreme_tail_panel_transport_v1.py"
    spec = importlib.util.spec_from_file_location("t230_transport_cli_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


class MemoryBackend:
    def __init__(self) -> None:
        self.current: dict[str, dict[str, object]] = {}
        self.versions: dict[tuple[str, str], bytes] = {}
        self.generation = 100
        self.fail_target_once: str | None = None
        self.fail_completion_once = False
        self.calls: list[tuple[str, str]] = []

    def create(self, uri: str, raw: bytes):
        self.calls.append(("create", uri))
        if self.fail_target_once == uri:
            self.fail_target_once = None
            raise OSError("fixture failed before target create")
        if self.fail_completion_once and uri.endswith(".completion.json"):
            self.fail_completion_once = False
            raise OSError("fixture lost completion create")
        if uri in self.current:
            raise transport.JournalObjectExists(uri)
        self.generation += 1
        identity = {
            "uri": uri,
            "generation": str(self.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.current[uri] = identity
        self.versions[(uri, str(self.generation))] = raw
        return identity

    def read(self, identity):
        self.calls.append(("read", str(identity["uri"])))
        return self.versions[(str(identity["uri"]), str(identity["generation"]))]

    def read_known_uri(self, uri: str):
        self.calls.append(("read-known", uri))
        if uri not in self.current:
            raise FileNotFoundError(uri)
        identity = self.current[uri]
        return identity, self.read(identity)

    def put(self, uri: str, raw: bytes):
        return self.create(uri, raw)


def _identity(uri: str, raw: bytes, generation: str = "7") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _time_v_raw(command: str) -> bytes:
    return (
        f'Command being timed: "{command}"\n'
        "User time (seconds): 1.00\n"
        "System time (seconds): 0.10\n"
        "Percent of CPU this job got: 90%\n"
        "Elapsed (wall clock) time (h:mm:ss or m:ss): 0:02.00\n"
        "Average shared text size (kbytes): 0\n"
        "Average unshared data size (kbytes): 0\n"
        "Average stack size (kbytes): 0\n"
        "Average total size (kbytes): 0\n"
        "Maximum resident set size (kbytes): 1048576\n"
        "Average resident set size (kbytes): 0\n"
        "Major (requiring I/O) page faults: 0\n"
        "Minor (reclaiming a frame) page faults: 1\n"
        "Voluntary context switches: 1\n"
        "Involuntary context switches: 0\n"
        "Swaps: 0\n"
        "File system inputs: 0\n"
        "File system outputs: 0\n"
        "Socket messages sent: 0\n"
        "Socket messages received: 0\n"
        "Signals delivered: 0\n"
        "Page size (bytes): 4096\n"
        "Exit status: 0\n"
    ).encode("utf-8")


def _prefreeze_fixture() -> tuple[dict[str, object], ...]:
    panel = {
        "uri": execution.FROZEN_G0_PANEL_URI,
        "generation": "11",
        "sha256": "1" * 64,
        "bytes": 100,
    }
    process = {
        "evidence_class": "linux-proc-pid-start-boot-v1",
        "pid": 10,
        "process_start_ticks": 20,
        "boot_id": "fixture-boot",
        "pid_namespace_inode": 30,
    }
    process["process_instance_sha256"] = sha256(
        transport.canonical_json(process)
    ).hexdigest()
    files = []
    for path in execution.PREFREEZE_SMOKE_IMPLEMENTATION_PATHS:
        raw = (ROOT / path).read_bytes()
        files.append({
            "path": path,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    runtime = {
        "schema_version": execution.PREFREEZE_SMOKE_RUNTIME_SCHEMA,
        "environment_class": "cloud-run-job-real-runtime-v1",
        "cloud_run_job": execution.PREFREEZE_SMOKE_CLOUD_RUN_JOB,
        "cloud_run_execution": "atlas-minimal-c-s2023-w1-v1-abcde",
        "cloud_run_task_index": 0,
        "cloud_run_task_attempt": 0,
        "cloud_run_task_count": 1,
        "source_commit_sha": "a" * 40,
        "immutable_candidate_image": IMAGE,
        "implementation_files": files,
        "implementation_files_sha256": execution.batch.canonical_sha256(files),
        "process_instance": process,
        "process_instance_sha256": process["process_instance_sha256"],
        "release_validation_eligible": True,
        **{
            field: False
            for field in execution._PREFREEZE_SMOKE_FALSE_AUTHORITY_FIELDS
        },
    }
    runtime["runtime_binding_sha256"] = execution.batch.canonical_sha256(runtime)
    hashes = {
        field: "2" * 64
        for field in execution._PREFREEZE_SMOKE_STRUCTURAL_HASH_KEYS
    }
    hashes["panel_object_identity_sha256"] = execution.batch.canonical_sha256(
        panel
    )
    receipt = execution.build_t230_prefreeze_smoke_receipt_v1(
        panel_object_identity=panel,
        source_commit_sha="a" * 40,
        immutable_candidate_image=IMAGE,
        runtime_binding=runtime,
        structural_hashes=hashes,
        require_release_runtime=True,
    )
    receipt_raw = transport.canonical_json(receipt)
    receipt_identity = _identity(
        transport.PREFREEZE_SMOKE_RECEIPT_URI, receipt_raw
    )
    launch = transport.build_prefreeze_smoke_launch_v1(
        panel_object_identity=panel,
        source_commit_sha="a" * 40,
        immutable_candidate_image=IMAGE,
        service_account="fixture@nfl-predictions-503414.iam.gserviceaccount.com",
    )
    launch_identity = _identity(
        transport.PREFREEZE_SMOKE_LAUNCH_URI,
        transport.canonical_json(launch),
    )
    time_raw = _time_v_raw(transport.PREFREEZE_SMOKE_TIMED_COMMAND)
    time_identity = _identity(transport.PREFREEZE_SMOKE_TIME_V_URI, time_raw)
    observed = _prefreeze_observed(receipt)
    projection = transport.build_prefreeze_smoke_execution_v1(
        smoke_launch_identity=launch_identity,
        smoke_launch=launch,
        smoke_receipt_identity=receipt_identity,
        smoke_receipt=receipt,
        smoke_time_v_identity=time_identity,
        smoke_time_v=time_raw,
        observed_execution=observed,
    )
    projection_raw = transport.canonical_json(projection)
    projection_identity = _identity(
        transport.PREFREEZE_SMOKE_EXECUTION_URI, projection_raw
    )
    gate = transport.build_prefreeze_release_gate_v1(
        expected_panel_object_identity=panel,
        expected_source_commit_sha="a" * 40,
        expected_immutable_candidate_image=IMAGE,
        smoke_launch_identity=launch_identity,
        smoke_launch=launch,
        smoke_receipt_identity=receipt_identity,
        smoke_receipt=receipt,
        smoke_time_v_identity=time_identity,
        smoke_time_v=time_raw,
        smoke_execution_identity=projection_identity,
        smoke_execution=projection,
    )
    return (
        gate,
        launch,
        launch_identity,
        receipt,
        receipt_identity,
        time_raw,
        time_identity,
        projection,
        projection_identity,
    )


def _prefreeze_observed(receipt: Mapping[str, object]) -> dict[str, object]:
    runtime = receipt["runtime_binding"]
    return {
        "job": execution.PREFREEZE_SMOKE_CLOUD_RUN_JOB,
        "image": receipt["immutable_candidate_image"]["uri"],
        "service_account": "fixture@nfl-predictions-503414.iam.gserviceaccount.com",
        "cpu": "8",
        "memory": "32Gi",
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "task_timeout_seconds": 21_600,
        "command": ["bash"],
        "args": ["scripts/run_t230_prefreeze_smoke_worker_v1.sh"],
        "configured_environment": {
            "FOUNDRY_T230_PREFREEZE_SMOKE_ENABLED": "1",
            "FOUNDRY_T230_PRODUCTION_TRANSPORT_ENABLED": "1",
            "T230_PREFREEZE_CANDIDATE_IMAGE": receipt[
                "immutable_candidate_image"
            ]["uri"],
        },
        "volumes": [],
        "secrets": [],
        "cloud_job_describe_exactly_validated": True,
        "execution_name": runtime["cloud_run_execution"],
        "completed_status": "True",
        "completion_time": "2026-08-25T12:00:00Z",
        "cloud_execution_describe_exactly_validated": True,
    }


def _prefreeze_gate() -> dict[str, object]:
    return _prefreeze_fixture()[0]


def _synthetic_publication_proof(
    target_identity: Mapping[str, object],
) -> dict[str, object]:
    target = dict(target_identity)
    return {
        "intent_identity": _identity(
            transport._journal_uri(
                str(target["uri"]), str(target["sha256"]), "intent"
            ),
            b"intent",
        ),
        "target_identity": target,
        "completion_identity": _identity(
            transport._journal_uri(
                str(target["uri"]), str(target["sha256"]), "completion"
            ),
            b"completion",
        ),
    }


def _observed_terminal(
    contract: Mapping[str, object],
    *,
    execution_name: str = "atlas-minimal-c-s2023-w1-v1-abcde",
) -> dict[str, object]:
    return {
        "job": transport.LANE_A_JOB,
        "image": contract["immutable_image"]["uri"],
        "service_account": "fixture@nfl-predictions-503414.iam.gserviceaccount.com",
        "cpu": "8",
        "memory": "32Gi",
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "task_timeout_seconds": 21_600,
        "runtime_evidence_volume": {
            "type": "in-memory",
            "name": "foundry-t230-runtime-evidence",
            "size_limit": "1Mi",
            "mount_path": "/etc/nfl-dfs",
        },
        "cloud_describe_exactly_validated": True,
        "execution_name": execution_name,
        "completed_status": "False",
        "completion_time": "2026-08-25T12:00:00Z",
        "cloud_execution_describe_exactly_validated": True,
    }


def _benchmark_contract(monkeypatch, backend: MemoryBackend):
    monkeypatch.setattr(
        transport, "SOURCE_SNAPSHOT_PATHS", execution._IMPLEMENTATION_PATHS
    )
    snapshot = transport.build_source_snapshot_v1(
        repository_root=ROOT, source_commit_sha="a" * 40
    )
    evidence = transport.build_image_evidence_v1(
        repository_root=ROOT,
        source_snapshot=snapshot,
        immutable_image=IMAGE,
    )
    evidence_raw = transport.canonical_json(evidence)
    evidence_identity = backend.put(
        execution.image_evidence_uri_for_output_prefix(transport.OUTPUT_PREFIX),
        evidence_raw,
    )
    contract = transport.build_transport_contract_v1(
        source_snapshot=snapshot,
        immutable_image=IMAGE,
        image_evidence_identity=evidence_identity,
        prefreeze_release_gate=_prefreeze_gate(),
    )
    contract_raw = transport.canonical_json(contract)
    contract_identity = backend.put(
        transport.TRANSPORT_CONTRACT_URI, contract_raw
    )
    return contract, contract_identity


def _job_config(
    backend: MemoryBackend,
    contract: Mapping[str, object],
    contract_identity: Mapping[str, object],
    *,
    job: str = transport.LANE_A_JOB,
) -> tuple[dict[str, object], dict[str, object]]:
    observed = {
        "job": job,
        "image": contract["immutable_image"]["uri"],
        "service_account": "fixture@nfl-predictions-503414.iam.gserviceaccount.com",
        "cpu": "8",
        "memory": "32Gi",
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "task_timeout_seconds": 21_600,
        "runtime_evidence_volume": {
            "type": "in-memory",
            "name": "foundry-t230-runtime-evidence",
            "size_limit": "1Mi",
            "mount_path": "/etc/nfl-dfs",
        },
        "cloud_describe_exactly_validated": True,
    }
    body = transport.build_job_config_v1(
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        observed_config=observed,
        job=job,
    )
    identity = backend.put(
        transport.job_config_uri(job), transport.canonical_json(body)
    )
    return body, identity


def _published_worker_runtime(
    backend: MemoryBackend, contract: dict[str, object]
) -> dict[str, object]:
    evidence = transport.strict_json(
        backend.read(contract["image_evidence_identity"]), label="test evidence"
    )
    process = {
        "evidence_class": "linux-proc-pid-start-boot-v1",
        "pid": 100,
        "process_start_ticks": 200,
        "boot_id": "fixture-boot",
        "pid_namespace_inode": 300,
    }
    process["process_instance_sha256"] = sha256(
        transport.canonical_json(process)
    ).hexdigest()
    g0 = {
        "path": str(execution.FROZEN_G0_AUTHORITY_LOCK_PATH),
        "relative_path": execution.FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH,
        "source_commit_sha": contract["source_commit_sha"],
        "sha256": "c" * 64,
        "bytes": 1,
        "owner_uid": 0,
        "mode_octal": "0400",
        "g0_authority_lock_sha256": "d" * 64,
        "tracked_at_head": True,
        "clean_at_head": True,
    }
    implementation = execution.frozen_t230_worker_implementation_v1()
    body = {
        "schema_version": execution.RUNTIME_MEASUREMENT_SCHEMA,
        "publication_mode": execution.PUBLICATION_MODE,
        "role": "worker",
        "runtime_attempt_ordinal": 0,
        "implementation_contract": implementation,
        "implementation_sha256": implementation["implementation_sha256"],
        "measured_source_commit_sha": contract["source_commit_sha"],
        "immutable_image": contract["immutable_image"],
        "image_evidence_identity": contract["image_evidence_identity"],
        "image_evidence_sha256": evidence["image_evidence_sha256"],
        "measured_files": evidence["implementation_files"],
        "measured_files_sha256": evidence["implementation_files_sha256"],
        "measured_callables": evidence["critical_callables"],
        "measured_callables_sha256": evidence["critical_callables_sha256"],
        "runtime_facts": evidence["runtime_facts"],
        "g0_authority_lock_git_binding": g0,
        "g0_authority_lock_git_binding_sha256": sha256(
            transport.canonical_json(g0)
        ).hexdigest(),
        "git_status_porcelain_sha256": sha256(b"").hexdigest(),
        "critical_paths_clean": True,
        "process_instance": process,
        "process_instance_sha256": process["process_instance_sha256"],
        "checkout_matches_git_blobs": True,
        "local_image_evidence_matches_pinned_bytes": True,
        "release_runtime_verified": True,
        **{field: False for field in execution._FALSE_AUTHORITY_FIELDS},
    }
    body["runtime_measurement_sha256"] = sha256(
        transport.canonical_json(body)
    ).hexdigest()
    raw = transport.canonical_json(body)
    return backend.put(
        execution.runtime_measurement_uri_for_output_prefix(
            transport.OUTPUT_PREFIX,
            role="worker",
            source_ordinal=0,
            runtime_attempt_ordinal=0,
        ),
        raw,
    )


def test_frozen_prefix_lanes_compute_gate_and_parser_contract() -> None:
    assert transport.OUTPUT_PREFIX.endswith(
        "/t230/20260825-foundry-t230-production-v2/"
    )
    assert transport.LANE_CONTRACT[0]["source_ordinals"] == list(range(28))
    assert transport.LANE_CONTRACT[1]["source_ordinals"] == list(range(28, 54))
    gate = transport.frozen_compute_gate_v1()
    assert gate["max_retries"] == 0
    assert gate["memory_limit_mib"] * 1024 - gate["max_peak_rss_kib"] == 8 * 1024 * 1024
    assert gate["task_timeout_seconds"] == 21_600
    assert gate["worker_science_invocation_count"] == 54
    assert gate["independent_verifier_science_invocation_count"] == 54
    assert gate["finalizer_science_invocation_count"] == 0
    assert gate["total_science_invocation_count"] == 108
    assert gate["additional_science_invocations_licensed"] is False
    assert gate["max_outer_worker_wall_delta_millis"] == 120_000
    assert gate["max_outer_worker_peak_rss_delta_kib"] == 2 * 1024 * 1024
    assert transport.frozen_time_v_parser_contract_v1()[
        "parser_implementation_sha256"
    ] == transport.EXPECTED_TIME_V_PARSER_SHA256
    assert transport.frozen_time_v_parser_contract_v1()[
        "unrecognized_lines_ignored"
    ] is False


def test_prefreeze_release_gate_binds_d_runtime_time_and_false_authority() -> None:
    gate = _prefreeze_gate()
    assert not transport.PREFREEZE_OUTPUT_PREFIX.startswith(
        transport.OUTPUT_PREFIX
    )
    assert gate["smoke_receipt_identity"]["uri"].startswith(
        transport.PREFREEZE_OUTPUT_PREFIX
    )
    assert transport.validate_prefreeze_release_gate_v1(gate) == gate
    assert gate["immutable_candidate_image"] == IMAGE
    assert gate["panel_object_identity"]["uri"] == execution.FROZEN_G0_PANEL_URI
    assert gate["numeric_gate"]["numeric_gate_passed"] is True
    assert gate["candidate_image_rebuild_after_smoke_allowed"] is False
    assert gate["exact_four_law_shared_call_chain_executed"] is True
    assert all(gate[field] is False for field in transport._FALSE_AUTHORITY_FIELDS)
    changed = deepcopy(gate)
    changed["candidate_image_rebuild_after_smoke_allowed"] = True
    changed.pop("prefreeze_release_gate_sha256")
    changed["prefreeze_release_gate_sha256"] = sha256(
        transport.canonical_json(changed)
    ).hexdigest()
    with pytest.raises(transport.T230TransportError):
        transport.validate_prefreeze_release_gate_v1(changed)


def test_prefreeze_release_gate_reopens_all_four_journals_without_listing() -> None:
    (
        _gate,
        launch,
        _fixture_launch_identity,
        receipt,
        _fixture_receipt_identity,
        time_raw,
        *_,
    ) = _prefreeze_fixture()
    backend = MemoryBackend()
    transport.RecoverablePublisher(
        backend, str(launch["prefreeze_smoke_launch_sha256"])
    ).publish(
        target_uri=transport.PREFREEZE_SMOKE_LAUNCH_URI,
        raw=transport.canonical_json(launch),
        transition_id="fixture-prefreeze-launch",
    )
    receipt_publication = transport.RecoverablePublisher(
        backend, str(receipt["prefreeze_smoke_receipt_sha256"])
    ).publish(
        target_uri=transport.PREFREEZE_SMOKE_RECEIPT_URI,
        raw=transport.canonical_json(receipt),
        transition_id="fixture-prefreeze-smoke",
    )
    receipt_identity = receipt_publication["target_identity"]
    time_binding = transport.build_prefreeze_smoke_time_binding_v1(
        smoke_receipt_identity=receipt_identity,
        smoke_receipt=receipt,
        raw_time_v=time_raw,
    )
    time_publication = transport.RecoverablePublisher(
        backend, str(time_binding["prefreeze_smoke_time_binding_sha256"])
    ).publish(
        target_uri=transport.PREFREEZE_SMOKE_TIME_V_URI,
        raw=time_raw,
        transition_id="fixture-prefreeze-time",
    )
    projection = transport.build_prefreeze_smoke_execution_v1(
        smoke_launch_identity=backend.current[
            transport.PREFREEZE_SMOKE_LAUNCH_URI
        ],
        smoke_launch=launch,
        smoke_receipt_identity=receipt_identity,
        smoke_receipt=receipt,
        smoke_time_v_identity=time_publication["target_identity"],
        smoke_time_v=time_raw,
        observed_execution=_prefreeze_observed(receipt),
    )
    transport.RecoverablePublisher(
        backend, str(projection["prefreeze_smoke_execution_sha256"])
    ).publish(
        target_uri=transport.PREFREEZE_SMOKE_EXECUTION_URI,
        raw=transport.canonical_json(projection),
        transition_id="fixture-prefreeze-execution",
    )
    resolved = transport.resolve_prefreeze_release_gate_v1(
        backend=backend,
        expected_panel_object_identity=receipt["panel_object_identity"],
        expected_source_commit_sha=str(receipt["source_commit_sha"]),
        expected_immutable_candidate_image=receipt["immutable_candidate_image"],
    )
    assert resolved["prefreeze_release_gate"][
        "prefreeze_smoke_execution_sha256"
    ] == projection["prefreeze_smoke_execution_sha256"]
    assert not hasattr(backend, "list")

    direct = MemoryBackend()
    direct.put(
        transport.PREFREEZE_SMOKE_RECEIPT_URI,
        transport.canonical_json(receipt),
    )
    with pytest.raises((FileNotFoundError, transport.T230TransportError)):
        transport.recover_prefreeze_smoke_receipt_v1(
            backend=direct,
            expected_panel_object_identity=receipt["panel_object_identity"],
            expected_source_commit_sha=str(receipt["source_commit_sha"]),
            expected_immutable_candidate_image=receipt[
                "immutable_candidate_image"
            ],
        )


def test_hash_addressed_journal_allows_new_attempt_after_intent_only_crash() -> None:
    backend = MemoryBackend()
    publisher = transport.RecoverablePublisher(backend, "c" * 64)
    target = transport.TRANSPORT_PREFIX + "fixture/terminal.json"
    backend.fail_target_once = target
    with pytest.raises(OSError):
        publisher.publish(
            target_uri=target, raw=b'{"attempt":0}', transition_id="attempt-0"
        )
    publication = publisher.publish(
        target_uri=target, raw=b'{"attempt":1}', transition_id="attempt-1"
    )
    assert publication["target_identity"]["sha256"] == sha256(
        b'{"attempt":1}'
    ).hexdigest()
    intent_creates = [uri for call, uri in backend.calls if call == "create" and uri.endswith(".intent.json")]
    assert len(set(intent_creates)) == 2
    assert not hasattr(backend, "list")

    deterministic = MemoryBackend()
    deterministic_publisher = transport.RecoverablePublisher(
        deterministic, "c" * 64
    )
    deterministic.fail_target_once = target
    with pytest.raises(OSError):
        deterministic_publisher.publish(
            target_uri=target, raw=b'{"same":true}', transition_id="attempt-0"
        )
    retained = deterministic_publisher.publish(
        target_uri=target, raw=b'{"same":true}', transition_id="attempt-1"
    )
    assert deterministic.read(retained["target_identity"]) == b'{"same":true}'
    assert retained["target_created"] is True
    repeated = deterministic_publisher.publish(
        target_uri=target, raw=b'{"same":true}', transition_id="attempt-2"
    )
    assert repeated["target_created"] is False


def test_target_created_before_completion_recovers_by_known_uri_and_pin() -> None:
    backend = MemoryBackend()
    publisher = transport.RecoverablePublisher(backend, "d" * 64)
    target = transport.TRANSPORT_PREFIX + "fixture/partial.json"
    raw = b'{"complete":true}'
    backend.fail_completion_once = True
    with pytest.raises(OSError):
        publisher.publish(target_uri=target, raw=raw, transition_id="partial")
    identity, recovered = transport.recover_or_complete_publication(
        backend=backend,
        target_uri=target,
        publication_binding_sha256="d" * 64,
    )
    assert recovered == raw
    assert backend.read(identity) == raw
    assert any(call == "read-known" and uri == target for call, uri in backend.calls)


def test_launch_authority_requires_the_completed_journal_not_only_target_bytes() -> None:
    target = transport.launch_request_uri("prepare", None)
    raw = b'{"fixture":"launch"}'
    direct = MemoryBackend()
    direct.put(target, raw)
    with pytest.raises(FileNotFoundError):
        transport.recover_publication_proof_v1(
            backend=direct,
            target_uri=target,
            publication_binding_sha256="e" * 64,
        )

    journaled = MemoryBackend()
    publication = transport.RecoverablePublisher(
        journaled, "e" * 64
    ).publish(
        target_uri=target,
        raw=raw,
        transition_id="fixture-journaled-launch",
    )
    proof, recovered = transport.recover_publication_proof_v1(
        backend=journaled,
        target_uri=target,
        publication_binding_sha256="e" * 64,
    )
    assert recovered == raw
    assert proof == {
        field: publication[field]
        for field in ("intent_identity", "target_identity", "completion_identity")
    }


def test_cloud_job_config_is_exact_and_mutation_fails_closed(
    monkeypatch,
) -> None:
    backend = MemoryBackend()
    contract, contract_identity = _benchmark_contract(monkeypatch, backend)
    config, config_identity = _job_config(backend, contract, contract_identity)
    assert transport.reopen_job_config_v1(
        job_config_identity=config_identity,
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        job=transport.LANE_A_JOB,
        read_exact=backend.read,
    ) == config
    forged = deepcopy(config["observed_config"])
    forged["max_retries"] = 1
    with pytest.raises(transport.T230TransportError, match="job config differs"):
        transport.build_job_config_v1(
            transport_contract_identity=contract_identity,
            transport_contract=contract,
            observed_config=forged,
            job=transport.LANE_A_JOB,
        )


def test_stage_start_fixed_attempt_cloud_envelope_and_receipt_are_exact() -> None:
    contract_hash = "e" * 64
    predecessor = _identity(
        transport._stage_uri("verify-slate", 2), b"predecessor"
    )
    launch_identity = _identity(
        transport.launch_request_uri("run-slate", 3), b"launch request"
    )
    start = transport.build_stage_start_v1(
        transport_contract_sha256=contract_hash,
        operation="run-slate",
        source_ordinal=3,
        runtime_attempt_ordinal=0,
        cloud_execution_name="atlas-minimal-c-s2023-w1-v1-abcde",
        cloud_job=transport.LANE_A_JOB,
        cloud_task_index=0,
        cloud_task_attempt=0,
        cloud_task_count=1,
        runtime_image=IMAGE,
        launch_request_identity=launch_identity,
        launch_publication_proof=_synthetic_publication_proof(launch_identity),
        predecessor_identities=[predecessor],
    )
    start_raw = transport.canonical_json(start)
    start_identity = _identity(str(start["stage_start_uri"]), start_raw)
    result_identity = _identity("gs://bucket/result.json", b"result")
    runtime_identity = _identity("gs://bucket/runtime.json", b"runtime")
    receipt = transport.build_stage_receipt_v1(
        transport_contract_sha256=contract_hash,
        operation="run-slate",
        source_ordinal=3,
        runtime_attempt_ordinal=0,
        cloud_execution_name="atlas-minimal-c-s2023-w1-v1-abcde",
        stage_start_identity=start_identity,
        core_workflow_receipt={"published": True},
        exposed_identities={
            "worker_runtime_measurement_identity": runtime_identity,
            "result_identity": result_identity,
        },
        wall_time_millis=None,
        peak_rss_kib=None,
    )
    assert receipt["compute_measurement_recorded"] is False
    assert receipt["support_rank_book_effect_fields_withheld"] is True
    assert start["predecessor_identities"] == [predecessor]
    assert start["launch_request_identity"] == launch_identity
    assert start["cloud_runtime_environment_attested"] is True
    assert transport.validate_stage_receipt_v1(
        receipt,
        transport_contract_sha256=contract_hash,
        operation="run-slate",
        source_ordinal=3,
    ) == receipt
    forged = deepcopy(receipt)
    forged["rank"] = 1
    forged.pop("stage_receipt_sha256")
    forged["stage_receipt_sha256"] = sha256(
        transport.canonical_json(forged)
    ).hexdigest()
    with pytest.raises(transport.T230TransportError, match="fields differ"):
        transport.validate_stage_receipt_v1(
            forged,
            transport_contract_sha256=contract_hash,
            operation="run-slate",
            source_ordinal=3,
        )
    with pytest.raises(transport.T230TransportError, match="mechanics inputs"):
        transport.build_stage_start_v1(
            transport_contract_sha256=contract_hash,
            operation="run-slate",
            source_ordinal=3,
            runtime_attempt_ordinal=1,
            cloud_execution_name="atlas-minimal-c-s2023-w1-v1-fghij",
            cloud_job=transport.LANE_A_JOB,
            cloud_task_index=0,
            cloud_task_attempt=0,
            cloud_task_count=1,
            runtime_image=IMAGE,
            launch_request_identity=launch_identity,
            launch_publication_proof=_synthetic_publication_proof(
                launch_identity
            ),
            predecessor_identities=[predecessor],
        )


def test_raw_gnu_time_contract_stage_result_binding_and_integer_gate(
    monkeypatch,
) -> None:
    backend = MemoryBackend()
    contract, contract_identity = _benchmark_contract(monkeypatch, backend)
    _config, config_identity = _job_config(
        backend, contract, contract_identity
    )
    prepare_identity = _identity(transport._stage_uri("prepare", None), b"prepare")
    launch = transport.build_launch_request_v1(
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        operation="run-slate",
        source_ordinal=0,
        predecessor_identities=[prepare_identity],
        job_config_identity=config_identity,
        read_exact=backend.read,
    )
    launch_publication = transport.RecoverablePublisher(
        backend, str(contract["transport_contract_sha256"])
    ).publish(
        target_uri=transport.launch_request_uri("run-slate", 0),
        raw=transport.canonical_json(launch),
        transition_id="fixture-launch-worker-zero",
    )
    launch_identity = launch_publication["target_identity"]
    assert transport.reopen_launch_request_v1(
        launch_request_identity=launch_identity,
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        operation="run-slate",
        source_ordinal=0,
        predecessor_identities=[prepare_identity],
        read_exact=backend.read,
    ) == launch
    start = transport.build_stage_start_v1(
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        operation="run-slate",
        source_ordinal=0,
        runtime_attempt_ordinal=0,
        cloud_execution_name="atlas-minimal-c-s2023-w1-v1-abcde",
        cloud_job=transport.LANE_A_JOB,
        cloud_task_index=0,
        cloud_task_attempt=0,
        cloud_task_count=1,
        runtime_image=IMAGE,
        launch_request_identity=launch_identity,
        launch_publication_proof={
            field: launch_publication[field]
            for field in (
                "intent_identity", "target_identity", "completion_identity"
            )
        },
        predecessor_identities=[prepare_identity],
    )
    start_raw = transport.canonical_json(start)
    start_identity = backend.put(str(start["stage_start_uri"]), start_raw)
    result_identity = backend.put("gs://bucket/result.json", b"result")
    runtime_identity = _published_worker_runtime(backend, contract)
    worker = transport.build_stage_receipt_v1(
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        operation="run-slate",
        source_ordinal=0,
        runtime_attempt_ordinal=0,
        cloud_execution_name="atlas-minimal-c-s2023-w1-v1-abcde",
        stage_start_identity=start_identity,
        core_workflow_receipt={"published": True},
        exposed_identities={
            "worker_runtime_measurement_identity": runtime_identity,
            "result_identity": result_identity,
        },
        wall_time_millis=17_999_000,
        peak_rss_kib=25_165_000,
    )
    worker_raw = transport.canonical_json(worker)
    worker_identity = backend.put(
        transport._stage_uri("run-slate", 0), worker_raw
    )
    raw = (
        b'Command being timed: "bash scripts/run_t230_benchmark_worker_v1.sh"\n'
        b"User time (seconds): 100.00\n"
        b"System time (seconds): 1.00\n"
        b"Percent of CPU this job got: 56%\n"
        b"Elapsed (wall clock) time (h:mm:ss or m:ss): 4:59:59.123\n"
        b"Average shared text size (kbytes): 0\n"
        b"Average unshared data size (kbytes): 0\n"
        b"Average stack size (kbytes): 0\n"
        b"Average total size (kbytes): 0\n"
        b"Maximum resident set size (kbytes): 25165824\n"
        b"Average resident set size (kbytes): 0\n"
        b"Major (requiring I/O) page faults: 1\n"
        b"Minor (reclaiming a frame) page faults: 2\n"
        b"Voluntary context switches: 3\n"
        b"Involuntary context switches: 4\n"
        b"Swaps: 0\n"
        b"File system inputs: 5\n"
        b"File system outputs: 6\n"
        b"Socket messages sent: 0\n"
        b"Socket messages received: 0\n"
        b"Signals delivered: 0\n"
        b"Page size (bytes): 4096\n"
        b"Exit status: 0\n"
    )
    raw_identity = backend.put(transport.RAW_TIME_V_URI, raw)
    raw_binding = {
        "uri": raw_identity["uri"],
        "sha256": raw_identity["sha256"],
        "bytes": raw_identity["bytes"],
    }
    disposition = transport.build_benchmark_disposition_v1(
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        worker_stage_receipt_identity=worker_identity,
        state="raw-ready",
        raw_time_v_binding=raw_binding,
        raw_time_v=raw,
        benchmark_execution_terminal_identity=None,
        read_exact=backend.read,
    )
    disposition_identity = backend.put(
        transport.BENCHMARK_DISPOSITION_URI,
        transport.canonical_json(disposition),
    )
    assert disposition["raw_time_v_utf8"].encode("utf-8") == raw
    assert disposition["decision_published_before_raw_time_v"] is True
    terminal = transport.build_benchmark_execution_terminal_v1(
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        worker_stage_receipt_identity=worker_identity,
        observed_terminal=_observed_terminal(contract),
        read_exact=backend.read,
    )
    terminal_identity = backend.put(
        transport.BENCHMARK_EXECUTION_TERMINAL_URI,
        transport.canonical_json(terminal),
    )
    terminal_disposition = transport.build_benchmark_disposition_v1(
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        worker_stage_receipt_identity=worker_identity,
        state="terminal-abort",
        raw_time_v_binding=None,
        raw_time_v=None,
        benchmark_execution_terminal_identity=terminal_identity,
        read_exact=backend.read,
    )
    with pytest.raises(transport.T230TransportError):
        transport.RecoverablePublisher(
            backend, str(contract["transport_contract_sha256"])
        ).publish(
            target_uri=transport.BENCHMARK_DISPOSITION_URI,
            raw=transport.canonical_json(terminal_disposition),
            transition_id="opposite-disposition",
        )
    benchmark = transport.build_benchmark_v1(
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        worker_stage_receipt_identity=worker_identity,
        benchmark_disposition_identity=disposition_identity,
        raw_time_v_identity=raw_identity,
        raw_time_v=raw,
        read_exact=backend.read,
    )
    assert benchmark["wall_time_millis"] == 17_999_123
    assert benchmark["peak_rss_kib"] == 25_165_824
    assert transport.validate_benchmark_v1(benchmark) == benchmark
    benchmark_raw = transport.canonical_json(benchmark)
    benchmark_identity = backend.put(transport.BENCHMARK_URI, benchmark_raw)
    release = transport.build_compute_release_v1(
        benchmark_identity=benchmark_identity,
        benchmark=benchmark,
        read_exact=backend.read,
    )
    assert release["scale_out_licensed"] is True
    assert release["raw_time_v_identity"] == raw_identity
    assert release["benchmark_disposition_identity"] == disposition_identity
    assert ("read", str(runtime_identity["uri"])) in backend.calls
    assert ("read", str(result_identity["uri"])) in backend.calls
    over_rss = deepcopy(benchmark)
    over_rss["peak_rss_kib"] += 1
    over_rss.pop("benchmark_sha256")
    over_rss["benchmark_sha256"] = sha256(
        transport.canonical_json(over_rss)
    ).hexdigest()
    with pytest.raises(transport.T230TransportError, match="numeric gate"):
        transport.validate_benchmark_v1(over_rss)
    forged_command = raw.replace(
        b"bash scripts/run_t230_benchmark_worker_v1.sh", b"true"
    )
    with pytest.raises(transport.T230TransportError, match="numeric fields"):
        transport.parse_gnu_time_v_v1(forged_command)
    with pytest.raises(transport.T230TransportError, match="unknown"):
        transport.parse_gnu_time_v_v1(raw + b"support_rank: 1\n")
    assert contract["transport_contract_sha256"] != contract_identity["sha256"]
    assert transport.validate_transport_contract_v1(contract) == contract
    evidence_raw = backend.read(contract["image_evidence_identity"])
    monkeypatch.setattr(execution, "_runtime_facts", lambda: {"controller": "different"})
    assert transport._validate_image_evidence_structural_v1(
        transport.strict_json(evidence_raw, label="controller evidence")
    )["source_commit_sha"] == contract["source_commit_sha"]
    with pytest.raises(execution.CorpusExtremeTailPanelExecutionError):
        execution._validate_image_evidence(
            transport.strict_json(evidence_raw, label="runtime evidence")
        )


def test_recovered_benchmark_worker_can_abort_but_cannot_claim_raw_ready(
    monkeypatch,
) -> None:
    backend = MemoryBackend()
    contract, contract_identity = _benchmark_contract(monkeypatch, backend)
    _config, config_identity = _job_config(
        backend, contract, contract_identity
    )
    prepare_identity = _identity(
        transport._stage_uri("prepare", None), b"prepare"
    )
    launch = transport.build_launch_request_v1(
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        operation="run-slate",
        source_ordinal=0,
        predecessor_identities=[prepare_identity],
        job_config_identity=config_identity,
        read_exact=backend.read,
    )
    launch_publication = transport.RecoverablePublisher(
        backend, str(contract["transport_contract_sha256"])
    ).publish(
        target_uri=transport.launch_request_uri("run-slate", 0),
        raw=transport.canonical_json(launch),
        transition_id="fixture-recovered-launch-worker-zero",
    )
    launch_identity = launch_publication["target_identity"]
    start = transport.build_stage_start_v1(
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        operation="run-slate",
        source_ordinal=0,
        runtime_attempt_ordinal=0,
        cloud_execution_name="atlas-minimal-c-s2023-w1-v1-abcde",
        cloud_job=transport.LANE_A_JOB,
        cloud_task_index=0,
        cloud_task_attempt=0,
        cloud_task_count=1,
        runtime_image=IMAGE,
        launch_request_identity=launch_identity,
        launch_publication_proof={
            field: launch_publication[field]
            for field in (
                "intent_identity", "target_identity", "completion_identity"
            )
        },
        predecessor_identities=[prepare_identity],
    )
    start_identity = backend.put(
        transport.stage_start_uri("run-slate", 0, 0),
        transport.canonical_json(start),
    )
    worker = transport.build_stage_receipt_v1(
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        operation="run-slate",
        source_ordinal=0,
        runtime_attempt_ordinal=0,
        cloud_execution_name="atlas-minimal-c-s2023-w1-v1-abcde",
        stage_start_identity=start_identity,
        core_workflow_receipt={"recovered": True},
        exposed_identities={
            "worker_runtime_measurement_identity": _identity(
                execution.runtime_measurement_uri_for_output_prefix(
                    transport.OUTPUT_PREFIX,
                    role="worker",
                    source_ordinal=0,
                    runtime_attempt_ordinal=0,
                ),
                b"runtime",
            ),
            "result_identity": _identity("gs://bucket/result.json", b"result"),
        },
        wall_time_millis=None,
        peak_rss_kib=None,
    )
    worker_identity = backend.put(
        transport._stage_uri("run-slate", 0), transport.canonical_json(worker)
    )
    terminal_projection = transport.build_benchmark_execution_terminal_v1(
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        worker_stage_receipt_identity=worker_identity,
        observed_terminal=_observed_terminal(contract),
        read_exact=backend.read,
    )
    terminal_identity = backend.put(
        transport.BENCHMARK_EXECUTION_TERMINAL_URI,
        transport.canonical_json(terminal_projection),
    )
    terminal = transport.build_benchmark_disposition_v1(
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        worker_stage_receipt_identity=worker_identity,
        state="terminal-abort",
        raw_time_v_binding=None,
        raw_time_v=None,
        benchmark_execution_terminal_identity=terminal_identity,
        read_exact=backend.read,
    )
    assert terminal["state"] == "terminal-abort"
    assert terminal["raw_time_v_utf8"] is None
    with pytest.raises(transport.T230TransportError, match="timed worker"):
        transport.build_benchmark_disposition_v1(
            transport_contract_identity=contract_identity,
            transport_contract=contract,
            worker_stage_receipt_identity=worker_identity,
            state="raw-ready",
            raw_time_v_binding={
                "uri": transport.RAW_TIME_V_URI,
                "sha256": sha256(b"raw").hexdigest(),
                "bytes": 3,
            },
            raw_time_v=b"raw",
            benchmark_execution_terminal_identity=None,
            read_exact=backend.read,
        )


def test_post_digest_evidence_materializes_as_exact_0400_regular_file(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        transport, "SOURCE_SNAPSHOT_PATHS", execution._IMPLEMENTATION_PATHS
    )
    snapshot = transport.build_source_snapshot_v1(
        repository_root=ROOT, source_commit_sha="a" * 40
    )
    evidence = transport.build_image_evidence_v1(
        repository_root=ROOT,
        source_snapshot=snapshot,
        immutable_image=IMAGE,
    )
    raw = transport.canonical_json(evidence)
    identity = _identity(
        execution.image_evidence_uri_for_output_prefix(transport.OUTPUT_PREFIX),
        raw,
    )
    target = tmp_path / "secure" / "foundry-t230-image-evidence-v1.json"
    monkeypatch.setattr(transport, "RUNTIME_EVIDENCE_PATH", target)
    binding = transport.materialize_image_evidence_v1(
        raw=raw, identity=identity
    )
    assert target.read_bytes() == raw
    assert binding["mode_octal"] == "0400"
    assert binding["owner_uid"] == target.stat().st_uid
    assert target.stat().st_nlink == 1


def test_cli_is_default_off_and_stage_identity_knobs_are_operation_optional() -> None:
    assert cli.run(["parked"]) == {
        "state": "parked",
        "default_off": True,
        "client_constructed": False,
        "output_prefix": transport.OUTPUT_PREFIX,
    }
    help_text = cli._parser()._subparsers._group_actions[0].choices[
        "run-stage"
    ].format_help()
    assert "--runtime-attempt-ordinal" in help_text
    assert "--cloud-task-attempt" in help_text
    assert "--runtime-image" in help_text
    assert "--predecessor-identity" in help_text
    assert "--execution-authority-uri" in help_text
    assert "--launch-request-uri" in help_text
    assert "--launch-request-intent-uri" in help_text
    assert "--launch-request-completion-uri" in help_text
    assert "recover-stage-after-core-terminal" in (
        cli._parser()._subparsers._group_actions[0].choices
    )
    assert "resolve-launch-request" in (
        cli._parser()._subparsers._group_actions[0].choices
    )
    with pytest.raises(SystemExit):
        cli.run([
            "run-stage", "--operation", "prepare",
            "--cloud-execution-name", "atlas-minimal-c-s2023-w1-v1-abcde",
        ])


def test_build_and_launcher_static_production_law() -> None:
    cloudbuild = (ROOT / "cloudbuild.foundry-t230.yaml").read_text()
    cloudbuild_config = yaml.safe_load(cloudbuild)
    smoke_step = next(
        step
        for step in cloudbuild_config["steps"]
        if step["id"] == "candidate-real-four-law-smoke-or-release-gate"
    )
    smoke_script = smoke_step["args"][1]
    dockerfile = (ROOT / "Dockerfile.foundry-t230").read_text()
    launcher = (
        ROOT / "scripts/cloud_corpus_extreme_tail_panel_v1_reuse.sh"
    ).read_text()
    benchmark_wrapper = (
        ROOT / "scripts/run_t230_benchmark_worker_v1.sh"
    ).read_text()
    prefreeze_wrapper = (
        ROOT / "scripts/run_t230_prefreeze_smoke_worker_v1.sh"
    ).read_text()
    assert (
        "20260823-foundry-production-v12-panel-index/"
        "panel-index-live/published.json"
    ) in cloudbuild
    assert "--add-volume type=in-memory,name=foundry-t230-runtime-evidence,size-limit=1Mi" in launcher
    assert "--add-volume-mount volume=foundry-t230-runtime-evidence,mount-path=/etc/nfl-dfs" in launcher
    assert "T230_RUNTIME_ATTEMPT_ORDINAL:-0" not in launcher
    assert "local attempt=0" in launcher
    assert "publish-launch-request" in launcher
    assert "resolve-launch-request" in launcher
    assert "recover-stage-after-core-terminal" in launcher
    assert "BENCHMARK_DISPOSITION_URI" in (
        ROOT / "src/nfl_dfs/research/corpus_extreme_tail_panel_transport.py"
    ).read_text()
    assert "publish-benchmark-terminal-abort" in launcher
    assert "gcloud run jobs executions describe" in launcher
    assert "LC_ALL=C" in launcher
    assert transport.BENCHMARK_COMMAND in launcher
    assert "gcloud storage ls" not in launcher
    assert "gcloud storage ls" not in cloudbuild
    helper_install = (
        "python3 -m pip install --break-system-packages --no-cache-dir '.[gcp]'"
    )
    assert helper_install in smoke_script
    assert cloudbuild.count(helper_install) == 1
    helper_transport = (
        "PYTHONPATH=src python3 "
        "scripts/run_corpus_extreme_tail_panel_transport_v1.py"
    )
    assert smoke_script.count(helper_transport) == 8
    assert "PYTHONPATH=src python " not in smoke_script
    assert all(
        "--break-system-packages" not in "\n".join(map(str, step.get("args", [])))
        for step in cloudbuild_config["steps"]
        if step["id"] != "candidate-real-four-law-smoke-or-release-gate"
    )
    assert "--max-retries 0" in launcher
    assert "COPY . /home/erich/projects/nfl-predictions" in dockerfile
    assert "COPY --chown" not in dockerfile
    assert "setpriv" not in launcher
    assert "preflight-g0" in cloudbuild
    assert "_T230_PHASE: candidate" in cloudbuild
    assert "candidate-real-four-law-smoke-or-release-gate" in cloudbuild
    focused_step = next(
        step for step in cloudbuild_config["steps"]
        if step["id"] == "focused-tests-and-semantic-g0-preflight"
    )
    assert "apt-get install -y --no-install-recommends git jq libgomp1" in (
        "\n".join(map(str, focused_step["args"]))
    )
    assert "publish-prefreeze-smoke-launch" in cloudbuild
    assert "target_created'" in cloudbuild
    assert "resolve-prefreeze-release-gate" in cloudbuild
    assert "candidate_image_rebuilt:false" in cloudbuild
    assert cloudbuild.index("resolve-prefreeze-release-gate") < cloudbuild.index(
        "release-only-generate-evidence-inside-d"
    )
    assert "run_corpus_extreme_tail_t230_prefreeze_smoke_v1.py" in prefreeze_wrapper
    assert '--execute --receipt-output "$receipt"' in prefreeze_wrapper
    assert "/usr/bin/time -v" in prefreeze_wrapper
    assert "publish-prefreeze-smoke-time-v" in prefreeze_wrapper
    assert "contract publication image evidence journal differs" in (
        ROOT / "scripts/run_corpus_extreme_tail_panel_transport_v1.py"
    ).read_text()
    assert "| jq -c '.target_identity'" in launcher
    assert '>|"$candidate"' in launcher
    assert '>|"$intent_candidate"' in launcher
    assert '>|"$raw"' in launcher
    assert '>|"$projection"' in launcher
    assert '>|"$publication_candidate"' in launcher
    assert '>"$intent_candidate"' not in launcher
    for option in (
        "--launch-request-uri",
        "--launch-request-generation",
        "--launch-request-sha256",
        "--launch-request-bytes",
        "--launch-request-intent-uri",
        "--launch-request-completion-uri",
    ):
        assert option in benchmark_wrapper
    assert "publish-benchmark-execution-terminal" in launcher
    assert "both_background_controllers_joined:true" in launcher
    assert 'if wait "$lane_a_pid"' in launcher
    assert 'if wait "$lane_b_pid"' in launcher
    assert (
        'lane-controller-status-${lane_a_status}-${lane_b_status}.json'
        in launcher
    )
    assert "foundry-t230-production-v2-${_SOURCE_COMMIT}-${BUILD_ID}" in cloudbuild
    assert "--env EXPECTED_SOURCE_COMMIT='${_SOURCE_COMMIT}'" in cloudbuild
    assert '"$$EXPECTED_SOURCE_COMMIT"' in cloudbuild
    assert "immutable-image.txt" in cloudbuild
    assert transport._runtime_mount_contract()["target_owner_uid"] == 0


def test_launcher_runtime_flags_file_preserves_args_and_environment(
    tmp_path: Path,
) -> None:
    launcher = (
        ROOT / "scripts/cloud_corpus_extreme_tail_panel_v1_reuse.sh"
    ).read_text()
    runtime = launcher.split("cat <<'RUNTIME'\n", 1)[1].split(
        "\nRUNTIME\n", 1
    )[0]
    env_items = [
        "FOUNDRY_T230_PRODUCTION_TRANSPORT_ENABLED=1",
        "T230_IMAGE=repo.example/image@sha256:" + "a" * 64,
        "HOSTILE=~,|,@sha256:abc,=tail\nnext-line",
        "EMPTY=",
    ]
    command = (
        'launcher="$1"; run_dir="$2"; shift 2; '
        'export T230_RUN_DIR="$run_dir"; '
        'source "$launcher" parked >/dev/null; '
        'runtime_payload="$(runtime_script)"; '
        'build_gcloud_execution_flags "$runtime_payload" "$@"'
    )
    completed = subprocess.run(
        [
            "bash", "-ceu", command, "t230-flags-test",
            str(ROOT / "scripts/cloud_corpus_extreme_tail_panel_v1_reuse.sh"),
            str(tmp_path), *env_items,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    flags_file = Path(completed.stdout.strip())
    flags = json.loads(flags_file.read_text())
    assert flags == {
        "--args": ["-ceu", runtime],
        "--update-env-vars": {
            item.split("=", 1)[0]: item.split("=", 1)[1]
            for item in env_items
        },
    }
    assert flags_file.stat().st_mode & 0o777 == 0o600
    flags_file.unlink()
    assert not flags_file.exists()

    failed = subprocess.run(
        [
            "bash", "-ceu",
            'launcher="$1"; run_dir="$2"; '
            'export T230_RUN_DIR="$run_dir"; '
            'source "$launcher" parked >/dev/null; '
            'jq() { return 1; }; '
            'runtime_payload="$(runtime_script)"; '
            'flags_file="$(build_gcloud_execution_flags '
            '"$runtime_payload" "A=1")"',
            "t230-flags-failure-test",
            str(ROOT / "scripts/cloud_corpus_extreme_tail_panel_v1_reuse.sh"),
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert failed.returncode == 2
    assert "cannot write the gcloud flags file" in failed.stderr
    assert list(tmp_path.glob(".gcloud-execution-flags.*")) == []

    def parse_gcloud_list(encoded: str) -> list[str]:
        assert encoded.startswith("^")
        delimiter_end = encoded.index("^", 1)
        selected_delimiter = encoded[1:delimiter_end]
        assert selected_delimiter
        return encoded[delimiter_end + 1 :].split(selected_delimiter)

    assert flags["--args"] == ["-ceu", runtime]
    assert '[[ "$T230_PRED_COUNT" =~ ^[0-2]$ ]]' in flags["--args"][1]
    assert len(parse_gcloud_list(f"^~^-ceu~{runtime}")) == 3

    launch_stage = launcher.split("launch_stage() {", 1)[1].split(
        "\nprepare_panel() {", 1
    )[0]
    payload_offset = launch_stage.index('runtime_payload="$(runtime_script)"')
    publication_offset = launch_stage.index("publish-launch-request")
    builder_offset = launch_stage.index(
        'flags_file="$(build_gcloud_execution_flags '
    )
    execute_offset = launch_stage.index("gcloud run jobs execute")
    cleanup_offset = launch_stage.index('command rm -f -- "$flags_file"')
    assert payload_offset < publication_offset < builder_offset < execute_offset
    assert execute_offset < cleanup_offset
    assert '--flags-file="$flags_file"' in launch_stage
    assert "--update-env-vars" not in launch_stage
    assert "--args=" not in launch_stage
