from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from scripts import (
    run_corpus_r6_v2_matchup_candidate_analysis_controller_v1 as operator,
)
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_v2_matchup_candidate_analysis_controller_v1 as controller,
)
from nfl_dfs.research import (
    corpus_r6_v2_matchup_candidate_analysis_release_v2 as release,
)
from nfl_dfs.research.corpus_neo4j_transport import ObjectIdentity


SOURCE_COMMIT = "a" * 40
IMAGE = f"fixture/r6@sha256:{'b' * 64}"
JOB = "r6-shared-worker"
JOB_UID = "fixture-job-uid-001"
PROJECT = "fixture-project"
REGION = "us-central1"
SERVICE_ACCOUNT = "r6-worker@fixture-project.iam.gserviceaccount.com"
CONTROLLER_PREFIX = "gs://fixture/controller/run-001/"
ANALYSIS_PREFIX = "gs://fixture/analysis/run-001/"


class _MemoryStore:
    def __init__(self, *, events: list[str] | None = None) -> None:
        self.current: dict[str, tuple[ObjectIdentity, bytes]] = {}
        self.by_key: dict[tuple[str, str, str, int], bytes] = {}
        self.generation = 0
        self.events = [] if events is None else events

    @staticmethod
    def _key(value: object) -> tuple[str, str, str, int]:
        if isinstance(value, ObjectIdentity):
            row = value.as_dict()
        else:
            row = batch.normalize_object_identity(value, label="memory identity")
        return (
            str(row["uri"]), str(row["generation"]), str(row["sha256"]),
            int(row["bytes"]),
        )

    def read_exact(self, identity: ObjectIdentity) -> bytes:
        return self.by_key[self._key(identity)]

    def resolve_optional(self, uri: str):
        return self.current.get(uri)

    def publish_create_once(self, uri: str, raw: bytes) -> ObjectIdentity:
        retained = self.current.get(uri)
        if retained is not None:
            if retained[1] != raw:
                raise RuntimeError("create-once collision differs")
            return retained[0]
        self.generation += 1
        identity = ObjectIdentity(
            uri=uri, generation=str(self.generation),
            sha256=sha256(raw).hexdigest(), bytes=len(raw),
        )
        self.current[uri] = (identity, bytes(raw))
        self.by_key[self._key(identity)] = bytes(raw)
        return identity

    def claim_create_once(self, uri: str, raw: bytes) -> ObjectIdentity:
        self.events.append(f"claim:{uri.rsplit('/', 1)[-1]}")
        if uri in self.current:
            raise RuntimeError("fresh claim already exists")
        return self.publish_create_once(uri, raw)

    def add_json(self, uri: str, value: object) -> dict[str, object]:
        return self.publish_create_once(
            uri, batch.canonical_json_bytes(value)
        ).as_dict()

    def add_raw(self, uri: str, raw: bytes) -> dict[str, object]:
        return self.publish_create_once(uri, raw).as_dict()


def _embedded_runtime_authority() -> dict[str, object]:
    measurements = [
        {"relative_path": path, "sha256": sha256(path.encode()).hexdigest(), "bytes": 1}
        for path in release.CRITICAL_RUNTIME_PATHS
    ]
    body = {
        "schema_version": release.EMBEDDED_RUNTIME_AUTHORITY_SCHEMA,
        "source_commit_sha": SOURCE_COMMIT,
        "critical_runtime_paths": list(release.CRITICAL_RUNTIME_PATHS),
        "critical_runtime_paths_sha256": batch.canonical_sha256(
            list(release.CRITICAL_RUNTIME_PATHS)
        ),
        "file_count": len(measurements),
        "file_measurements": measurements,
        "critical_runtime_files_sha256": batch.canonical_sha256(measurements),
        "clean_git_head_verified_at_build": True,
        "clean_git_status_verified_at_build": True,
        "working_tree_equals_commit_blobs_verified_at_build": True,
    }
    body["runtime_authority_sha256"] = batch.canonical_sha256(body)
    return release.validate_embedded_runtime_authority_v1(body)


def _provider_authority(embedded: dict[str, object]) -> dict[str, object]:
    return release.build_provider_runtime_image_authority_v1(
        provider_observation={
            "schema_version": release.PROVIDER_IMAGE_OBSERVATION_SCHEMA,
            "provider": "google-cloud-run-v2",
            "observation_kind": "cloud-run-job",
            "resource_name": f"projects/{PROJECT}/locations/{REGION}/jobs/{JOB}",
            "build_id": "fixture-build-001",
            "job_name": JOB,
            "job_uid": JOB_UID,
            "execution_id": None,
            "source_commit_sha": SOURCE_COMMIT,
            "immutable_image": IMAGE,
            "provider_observed": True,
        },
        embedded_runtime_authority=embedded,
    )


def _job_from_projection(
    projection: dict[str, object] | None = None, *, generation: int = 1,
) -> dict[str, object]:
    if projection is None:
        projection = {
            "immutable_image": "fixture/parked@sha256:" + "c" * 64,
            "command": ["python"], "args": ["-c", "pass"],
            "environment": {"PARKED": "1"}, "task_count": 1,
            "parallelism": 1, "maximum_task_retries": 0,
            "timeout_seconds": 900, "cpu": "1", "memory": "1Gi",
            "service_account": SERVICE_ACCOUNT,
        }
    return {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Job",
        "metadata": {
            "name": JOB, "uid": JOB_UID, "generation": generation,
            "annotations": {}, "labels": {},
        },
        "spec": {"template": {"spec": {
            "taskCount": projection["task_count"],
            "parallelism": projection["parallelism"],
            "template": {"spec": {
                "maxRetries": projection["maximum_task_retries"],
                "timeoutSeconds": f"{projection['timeout_seconds']}s",
                "serviceAccountName": projection["service_account"],
                "volumes": [],
                "containers": [{
                    "image": projection["immutable_image"],
                    "command": projection["command"],
                    "args": projection["args"],
                    "env": [
                        {"name": key, "value": value}
                        for key, value in projection["environment"].items()
                    ],
                    "resources": {"limits": {
                        "cpu": projection["cpu"], "memory": projection["memory"],
                    }},
                    "workingDir": "", "volumeMounts": [],
                }],
            }},
        }}},
        "status": {
            "observedGeneration": generation,
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }


def _execution(
    projection: dict[str, object], *, name: str = f"{JOB}-abcde",
    terminal: bool = False, job_generation: str = "2",
) -> dict[str, object]:
    status: dict[str, object] = {
        "conditions": [] if not terminal else [{"type": "Completed", "status": "True"}],
        "succeededCount": 0 if not terminal else projection["task_count"],
        "failedCount": 0, "cancelledCount": 0, "retriedCount": 0,
    }
    if terminal:
        status["completionTime"] = "2026-08-29T12:00:00Z"
    return {
        "metadata": {
            "name": name, "uid": f"uid-{name}", "generation": 1,
            "labels": {
                "run.googleapis.com/job": JOB,
                "run.googleapis.com/jobUid": JOB_UID,
                "run.googleapis.com/jobGeneration": job_generation,
            },
        },
        "spec": {
            "taskCount": projection["task_count"],
            "parallelism": projection["parallelism"],
            "template": {"spec": {
                "maxRetries": 0,
                "timeoutSeconds": f"{projection['timeout_seconds']}s",
                "serviceAccountName": SERVICE_ACCOUNT,
                "volumes": [],
                "containers": [{
                    "image": projection["immutable_image"],
                    "command": projection["command"],
                    "args": projection["args"],
                    "env": [
                        {"name": key, "value": value}
                        for key, value in projection["environment"].items()
                    ],
                    "resources": {"limits": {
                        "cpu": projection["cpu"], "memory": projection["memory"],
                    }},
                    "workingDir": "", "volumeMounts": [],
                }],
            }},
        },
        "status": status,
    }


def _task(execution: str, index: int, *, retried: int = 0) -> dict[str, object]:
    return {
        "metadata": {
            "name": f"{execution}-task{index}",
            "labels": {"run.googleapis.com/execution": execution},
        },
        "status": {
            "index": index, "retried": retried,
            "conditions": [{"type": "Completed", "status": "True"}],
            "lastAttemptResult": {"exitCode": 0},
            "completionTime": "2026-08-29T12:00:00Z",
        },
    }


def _dummy_identity(tag: str) -> dict[str, object]:
    raw = tag.encode()
    return {
        "uri": f"gs://fixture/{tag}.json", "generation": "1",
        "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
    }


def _prepared() -> tuple[
    _MemoryStore, dict[str, object], dict[str, object], dict[str, object], bytes,
]:
    store = _MemoryStore()
    exported = b"apiVersion: run.googleapis.com/v1\nkind: Job\nmetadata:\n  name: r6-shared-worker\n"
    parked = _job_from_projection()
    snapshot = controller.build_job_snapshot_v1(
        job=parked, exported_job=exported, executions=[], schedulers=[],
        all_regions_complete=True, job_name=JOB, job_uid=JOB_UID,
    )
    snapshot_identity = store.add_json(
        f"{CONTROLLER_PREFIX}job-before.json", snapshot
    )
    export_identity = store.add_raw(
        f"{CONTROLLER_PREFIX}job-before.export.yaml", exported
    )
    embedded = _embedded_runtime_authority()
    embedded_identity = store.add_json(
        f"{CONTROLLER_PREFIX}runtime/embedded-runtime-authority.json", embedded
    )
    image = _provider_authority(embedded)
    image_identity = store.add_json(
        f"{CONTROLLER_PREFIX}runtime/provider-image-authority.json", image
    )
    manifest = controller.build_controller_manifest_v1(
        run_id="run-001", controller_output_prefix=CONTROLLER_PREFIX,
        analysis_output_prefix=ANALYSIS_PREFIX,
        project_id=PROJECT, region=REGION,
        job_snapshot_identity=snapshot_identity, job_snapshot=snapshot,
        job_export_identity=export_identity,
        panel_index_identity=_dummy_identity("panel"),
        lane_terminal_identities=[_dummy_identity("lane-a"), _dummy_identity("lane-b")],
        matchup_source_release_identity=_dummy_identity("source"),
        runtime_image_authority_identity=image_identity,
        runtime_image_authority=image,
        embedded_runtime_authority_identity=embedded_identity,
        embedded_runtime_authority=embedded,
    )
    manifest_identity = store.add_json(
        f"{CONTROLLER_PREFIX}controller-manifest.json", manifest
    )
    return store, manifest_identity, manifest, parked, exported


class _Provider:
    def __init__(self, manifest: dict[str, object], identity: dict[str, object], events: list[str]) -> None:
        self.project = PROJECT
        self.region = REGION
        self.manifest = manifest
        self.identity = identity
        self.events = events
        self.projection: dict[str, object] | None = None
        self.execution_name = f"{JOB}-abcde"
        self.terminal = False

    def list_executions(self, job_name: str) -> list[object]:
        return []

    def update_job(self, projection: Mapping[str, object]) -> dict[str, object]:
        self.events.append("provider:update")
        self.projection = dict(projection)
        return _job_from_projection(self.projection, generation=2)

    def execute_job(self, job_name: str) -> str:
        self.events.append("provider:execute")
        return self.execution_name

    def describe_execution(self, execution: str) -> dict[str, object]:
        assert self.projection is not None
        return _execution(self.projection, name=execution, terminal=self.terminal)

    def describe_task(self, execution: str, task_index: int) -> dict[str, object]:
        return _task(execution, task_index)


def test_phase_lattice_is_exact_and_cli_has_read_only_commands() -> None:
    assert controller.PHASES == (
        "prepare", "task0-worker", "task0-verifier", "full-workers",
        "full-verifiers", "finish",
    )
    assert [controller.PHASE_TASK_COUNTS[value] for value in controller.PHASES] == [
        1, 1, 1, 54, 54, 1,
    ]
    parser = operator._parser()
    status = parser.parse_args([
        "--project", PROJECT, "--region", REGION, "status",
        "--controller-manifest-identity", "/tmp/identity.json",
        "--phase", "full-workers",
    ])
    reopen = parser.parse_args([
        "--project", PROJECT, "--region", REGION, "reopen",
        "--controller-manifest-identity", "/tmp/identity.json",
    ])
    assert not hasattr(status, "execute")
    assert not hasattr(reopen, "execute")


def test_outcome_carrier_denial_allows_only_explicit_false_policy() -> None:
    controller.reject_outcome_carriers_v1(
        {"uses_realized_outcomes": False, "outcome_columns_read": []},
        label="fixture",
    )
    with pytest.raises(
        controller.CorpusR6V2MatchupCandidateAnalysisControllerV1Error,
        match="forbidden outcome",
    ):
        controller.reject_outcome_carriers_v1(
            {"nested": {"RealizedScore": [1]}}, label="fixture"
        )
    with pytest.raises(
        controller.CorpusR6V2MatchupCandidateAnalysisControllerV1Error,
        match="environment name",
    ):
        controller.reject_outcome_carriers_v1(
            [{"name": "OUTCOME_READER", "value": "x"}], label="fixture"
        )


def test_manifest_exact_reopen_binds_snapshot_export_and_provider_authority() -> None:
    store, identity, manifest, _, _ = _prepared()
    retained_identity, retained = controller.reopen_controller_manifest_v1(
        storage=store, manifest_identity=identity,
    )
    assert retained_identity == identity
    assert retained == manifest
    assert retained["immutable_image"] == IMAGE
    assert retained["task_count_law"] == [1, 1, 1, 54, 54, 1]
    assert retained["maximum_task_retries"] == 0


def test_manifest_rejects_provider_authority_substitution() -> None:
    store, identity, _, _, _ = _prepared()
    manifest_raw = store.current[identity["uri"]][1]
    value = batch.parse_canonical_json_bytes(manifest_raw, label="manifest")
    value["immutable_image"] = "fixture/evil@sha256:" + "d" * 64
    value.pop("controller_manifest_sha256")
    value["controller_manifest_sha256"] = batch.canonical_sha256(value)
    raw = batch.canonical_json_bytes(value)
    store.current[identity["uri"]] = (
        ObjectIdentity(
            uri=identity["uri"], generation=identity["generation"],
            sha256=sha256(raw).hexdigest(), bytes=len(raw),
        ), raw,
    )
    substituted = store.current[identity["uri"]][0]
    store.by_key[store._key(substituted)] = raw
    with pytest.raises(
        controller.CorpusR6V2MatchupCandidateAnalysisControllerV1Error,
        match="provider coordinates|runtime authority replay",
    ):
        controller.reopen_controller_manifest_v1(
            storage=store, manifest_identity=substituted.as_dict(),
        )


def test_phase_job_and_execution_require_provider_observed_digest_and_zero_retries() -> None:
    _, identity, manifest, _, _ = _prepared()
    encoded = operator._encode_identity(identity)
    projection = controller.phase_job_projection_v1(
        manifest=manifest, manifest_identity_b64=encoded, phase="full-workers",
    )
    job = _job_from_projection(projection)
    observed = controller.validate_phase_job_observation_v1(
        job, manifest=manifest, manifest_identity_b64=encoded,
        phase="full-workers",
    )
    assert observed["task_count"] == 54
    execution = _execution(projection, terminal=True)
    terminal = controller.validate_phase_execution_v1(
        execution, manifest=manifest, manifest_identity_b64=encoded,
        phase="full-workers", expected_execution=f"{JOB}-abcde",
        expected_job_generation="2", require_terminal=True,
    )
    assert terminal["succeeded_count"] == 54
    bad = deepcopy(execution)
    bad["spec"]["template"]["spec"]["maxRetries"] = 1
    with pytest.raises(
        controller.CorpusR6V2MatchupCandidateAnalysisControllerV1Error,
        match="execution template differs",
    ):
        controller.validate_phase_execution_v1(
            bad, manifest=manifest, manifest_identity_b64=encoded,
            phase="full-workers", expected_execution=f"{JOB}-abcde",
            expected_job_generation="2", require_terminal=True,
        )
    retried = deepcopy(execution)
    retried["status"]["retriedCount"] = 1
    with pytest.raises(
        controller.CorpusR6V2MatchupCandidateAnalysisControllerV1Error,
        match="terminal success",
    ):
        controller.validate_phase_execution_v1(
            retried, manifest=manifest, manifest_identity_b64=encoded,
            phase="full-workers", expected_execution=f"{JOB}-abcde",
            expected_job_generation="2", require_terminal=True,
        )


def test_status_proves_every_exact_task_index_and_rejects_retry() -> None:
    store, identity, manifest, _, _ = _prepared()
    encoded = operator._encode_identity(identity)
    projection = controller.phase_job_projection_v1(
        manifest=manifest, manifest_identity_b64=encoded, phase="full-verifiers",
    )
    execution = _execution(projection, terminal=True)
    claim = _dummy_identity("claim")
    binding = controller.build_execution_binding_v1(
        manifest=manifest, manifest_identity=identity, phase="full-verifiers",
        configure_claim_identity=claim, launch_claim_identity=claim,
        configured_job=_job_from_projection(projection, generation=2),
        execution=_execution(projection), manifest_identity_b64=encoded,
    )
    binding_identity = store.add_json(
        f"{CONTROLLER_PREFIX}phases/full-verifiers/execution-binding.json",
        binding,
    )
    tasks = [_task(f"{JOB}-abcde", index) for index in range(54)]
    status = controller.build_phase_status_v1(
        manifest=manifest, manifest_identity=identity,
        phase="full-verifiers", binding_identity=binding_identity,
        binding=binding, execution=execution, task_observations=tasks,
        manifest_identity_b64=encoded,
    )
    assert status["expected_task_indices"] == list(range(54))
    assert status["zero_retries_verified"] is True
    tasks[17] = _task(f"{JOB}-abcde", 17, retried=1)
    with pytest.raises(
        controller.CorpusR6V2MatchupCandidateAnalysisControllerV1Error,
        match="index/attempt/status",
    ):
        controller.build_phase_status_v1(
            manifest=manifest, manifest_identity=identity,
            phase="full-verifiers", binding_identity=binding_identity,
            binding=binding, execution=execution, task_observations=tasks,
            manifest_identity_b64=encoded,
        )


def test_launch_claims_precede_each_provider_mutation_and_relaunch_fails() -> None:
    events: list[str] = []
    store, identity, manifest, _, _ = _prepared()
    store.events = events
    provider = _Provider(manifest, identity, events)
    result = operator.launch_phase_v1(
        storage=store, provider=provider, manifest_identity=identity,
        phase="prepare",
    )
    assert result["task_count"] == 1
    assert events == [
        "claim:configure-claim.json", "provider:update",
        "claim:launch-claim.json", "provider:execute",
    ]
    with pytest.raises(
        operator.RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error,
        match="relaunch is forbidden",
    ):
        operator.launch_phase_v1(
            storage=store, provider=provider, manifest_identity=identity,
            phase="prepare",
        )


def test_status_path_is_storage_read_only_after_launch() -> None:
    events: list[str] = []
    store, identity, manifest, _, _ = _prepared()
    store.events = events
    provider = _Provider(manifest, identity, events)
    operator.launch_phase_v1(
        storage=store, provider=provider, manifest_identity=identity,
        phase="prepare",
    )
    provider.terminal = True
    before = set(store.current)
    status = operator.phase_status_v1(
        storage=store, provider=provider, manifest_identity=identity,
        phase="prepare",
    )
    assert status["strict_terminal_success"] is True
    assert set(store.current) == before


def test_dispatch_maps_full_fanout_bijectively_without_caller_ordinal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    store, identity, manifest, _, _ = _prepared()
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        operator, "_analysis_manifest",
        lambda *_args, **_kwargs: (
            _dummy_identity("analysis"), {}, {}, {},
        ),
    )
    monkeypatch.setattr(
        release, "run_worker_v2",
        lambda **kwargs: captured.update(kwargs) or {"ok": True},
    )
    environment = {
        controller.MANIFEST_IDENTITY_ENV: operator._encode_identity(identity),
        controller.PHASE_ENV: "full-workers",
        operator.CLOUD_RUN_TASK_INDEX: "53",
    }
    receipt_path = tmp_path / controller.ON_IMAGE_RUNTIME_AUTHORITY_RELATIVE_PATH
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_bytes(
        batch.canonical_json_bytes(_embedded_runtime_authority())
    )
    result = operator.dispatch_v1(
        storage=store, environment=environment, repository_root=tmp_path,
    )
    assert result == {"ok": True}
    assert captured["source_ordinal"] == 53
    assert "runtime_source_commit_sha" not in captured
    assert "runtime_immutable_image" not in captured
    assert "embedded_runtime_authority" not in captured
    environment[operator.CLOUD_RUN_TASK_INDEX] = "54"
    with pytest.raises(
        operator.RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error,
        match="outside the exact phase task lattice",
    ):
        operator.dispatch_v1(
            storage=store, environment=environment, repository_root=tmp_path,
        )


def test_dispatch_rejects_gcs_valid_but_on_image_substituted_runtime_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    store, identity, _, _, _ = _prepared()
    substituted = deepcopy(_embedded_runtime_authority())
    substituted.pop("runtime_authority_sha256")
    substituted["source_commit_sha"] = "d" * 40
    substituted["runtime_authority_sha256"] = batch.canonical_sha256(substituted)
    path = tmp_path / controller.ON_IMAGE_RUNTIME_AUTHORITY_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(batch.canonical_json_bytes(substituted))
    environment = {
        controller.MANIFEST_IDENTITY_ENV: operator._encode_identity(identity),
        controller.PHASE_ENV: "full-workers",
        operator.CLOUD_RUN_TASK_INDEX: "0",
    }
    with pytest.raises(
        operator.RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error,
        match="on-image runtime authority differs",
    ):
        operator.dispatch_v1(
            storage=store, environment=environment, repository_root=tmp_path,
        )


def test_authenticated_build_observation_rejects_forged_provider_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedded = _embedded_runtime_authority()
    authority = release.build_provider_runtime_image_authority_v1(
        provider_observation={
            "schema_version": release.PROVIDER_IMAGE_OBSERVATION_SCHEMA,
            "provider": "google-cloud-build",
            "observation_kind": "cloud-build-image",
            "resource_name": f"projects/{PROJECT}/builds/build-001",
            "build_id": "build-001",
            "job_name": None,
            "job_uid": None,
            "execution_id": None,
            "source_commit_sha": SOURCE_COMMIT,
            "immutable_image": IMAGE,
            "provider_observed": True,
        },
        embedded_runtime_authority=embedded,
    )
    provider = operator.GCloudRunOneJobProviderV1(
        project=PROJECT, region=REGION,
    )
    build = {
        "id": "build-001", "status": "SUCCESS",
        "substitutions": {"_SOURCE_COMMIT_SHA": SOURCE_COMMIT},
        "results": {"images": [{
            "name": IMAGE.rsplit("@", 1)[0],
            "digest": IMAGE.rsplit("@", 1)[1],
        }]},
    }
    monkeypatch.setattr(provider, "_json", lambda _argv: deepcopy(build))
    assert provider.authenticate_runtime_image_authority(authority) == authority[
        "provider_observation"
    ]
    forged = deepcopy(build)
    forged["results"]["images"][0]["digest"] = "sha256:" + "e" * 64
    monkeypatch.setattr(provider, "_json", lambda _argv: deepcopy(forged))
    with pytest.raises(
        operator.RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error,
        match="authenticated Cloud Build",
    ):
        provider.authenticate_runtime_image_authority(authority)


def test_controller_constructs_authority_in_controlled_namespace_from_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _MemoryStore()
    embedded = _embedded_runtime_authority()
    source_identity = store.add_json(
        "gs://fixture/build/embedded.json", embedded
    )
    provider = operator.GCloudRunOneJobProviderV1(
        project=PROJECT, region=REGION,
    )
    build = {
        "id": "build-001", "status": "SUCCESS",
        "name": f"projects/{PROJECT}/builds/build-001",
        "substitutions": {"_SOURCE_COMMIT_SHA": SOURCE_COMMIT},
        "results": {"images": [{
            "name": IMAGE.rsplit("@", 1)[0],
            "digest": IMAGE.rsplit("@", 1)[1],
        }]},
    }
    monkeypatch.setattr(provider, "_json", lambda _argv: deepcopy(build))
    result = operator.publish_runtime_authority_v1(
        storage=store, provider=provider,
        controller_output_prefix=CONTROLLER_PREFIX,
        source_embedded_identity=source_identity,
        build_id="build-001", immutable_image=IMAGE,
        source_commit_sha=SOURCE_COMMIT,
    )
    assert result["provider_observation_constructed_by_controller"] is True
    assert result["caller_provider_observation_accepted"] is False
    assert result["provider_runtime_image_authority_identity"]["uri"] == (
        f"{CONTROLLER_PREFIX}runtime/provider-image-authority.json"
    )
    assert result["embedded_runtime_authority_identity"]["uri"] == (
        f"{CONTROLLER_PREFIX}runtime/embedded-runtime-authority.json"
    )


def test_restore_validation_requires_exact_uid_and_stable_configuration() -> None:
    _, _, _, parked, exported = _prepared()
    snapshot = controller.build_job_snapshot_v1(
        job=parked, exported_job=exported, executions=[], schedulers=[],
        all_regions_complete=True, job_name=JOB, job_uid=JOB_UID,
    )
    proof = controller.validate_restored_job_v1(
        snapshot=snapshot, restored_job=parked,
    )
    assert proof["exact_snapshot_restored"] is True
    changed = deepcopy(parked)
    changed["spec"]["template"]["spec"]["parallelism"] = 2
    with pytest.raises(
        controller.CorpusR6V2MatchupCandidateAnalysisControllerV1Error,
        match="restoration differs",
    ):
        controller.validate_restored_job_v1(
            snapshot=snapshot, restored_job=changed,
        )


def test_independent_reopen_exact_replays_all_six_claim_and_provider_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, manifest_identity, manifest, _, _ = _prepared()
    encoded = operator._encode_identity(manifest_identity)
    predecessor: dict[str, object] | None = None
    gates: dict[str, dict[str, object]] = {}
    for phase_ordinal, phase in enumerate(controller.PHASES):
        projection = controller.phase_job_projection_v1(
            manifest=manifest, manifest_identity_b64=encoded, phase=phase,
        )
        generation = str(10 + phase_ordinal)
        execution_name = f"{JOB}-phase{phase_ordinal}"
        for operation in ("configure", "launch"):
            claim = controller.build_mutation_claim_v1(
                manifest=manifest, manifest_identity=manifest_identity,
                phase=phase, operation=operation,
                predecessor_acceptance_identity=predecessor,
            )
            claim_identity = store.add_json(
                controller.phase_uri_v1(
                    manifest, phase, f"{operation}-claim.json"
                ),
                claim,
            )
            if operation == "configure":
                configure_identity = claim_identity
            else:
                launch_identity = claim_identity
        binding = controller.build_execution_binding_v1(
            manifest=manifest, manifest_identity=manifest_identity,
            phase=phase, configure_claim_identity=configure_identity,
            launch_claim_identity=launch_identity,
            configured_job=_job_from_projection(
                projection, generation=int(generation)
            ),
            execution=_execution(
                projection, name=execution_name,
                job_generation=generation,
            ),
            manifest_identity_b64=encoded,
        )
        binding_identity = store.add_json(
            controller.phase_uri_v1(
                manifest, phase, "execution-binding.json"
            ),
            binding,
        )
        terminal = _execution(
            projection, name=execution_name, terminal=True,
            job_generation=generation,
        )
        tasks = [
            _task(execution_name, index)
            for index in range(controller.PHASE_TASK_COUNTS[phase])
        ]
        status = controller.build_phase_status_v1(
            manifest=manifest, manifest_identity=manifest_identity,
            phase=phase, binding_identity=binding_identity, binding=binding,
            execution=terminal, task_observations=tasks,
            manifest_identity_b64=encoded,
        )
        gate: dict[str, object] = {
            "schema_version": "fixture-science-gate/v1",
            "phase": phase, "passed": True,
            "outcome_columns_read": [], "uses_realized_outcomes": False,
            "historical_scoring_licensed": False,
            "automatic_retry_licensed": False,
        }
        if phase == "finish":
            gate.update({
                "terminal_root_identity": _dummy_identity("terminal-root"),
                "accepted_root_sha256": "d" * 64,
                "accepted_slate_count": 54,
                "rank_80_book_count": 14_904,
                "prefix_count": 44_712,
            })
        gate["science_gate_sha256"] = batch.canonical_sha256(gate)
        gates[phase] = gate
        acceptance = controller.build_phase_acceptance_v1(
            manifest=manifest, manifest_identity=manifest_identity,
            phase_status=status, predecessor_identity=predecessor,
            science_gate=gate,
        )
        predecessor = store.add_json(
            controller.phase_uri_v1(manifest, phase, "acceptance.json"),
            acceptance,
        )
    monkeypatch.setattr(
        operator, "science_gate_v1",
        lambda *, phase, **_kwargs: deepcopy(gates[phase]),
    )
    reopened = operator.independent_reopen_v1(
        storage=store, manifest_identity=manifest_identity,
    )
    assert reopened["complete"] is True
    assert reopened["phase_count"] == 6
    assert [
        row["phase"] for row in reopened["ordered_phase_acceptances"]
    ] == list(controller.PHASES)


def test_mutating_commands_require_explicit_execute_before_client_use() -> None:
    with pytest.raises(
        operator.RunCorpusR6V2MatchupCandidateAnalysisControllerV1Error,
        match="requires explicit --execute",
    ):
        operator.run([
            "--project", PROJECT, "--region", REGION, "snapshot",
            "--run-id", "run-001",
            "--controller-output-prefix", CONTROLLER_PREFIX,
            "--analysis-output-prefix", ANALYSIS_PREFIX,
            "--job-name", JOB, "--job-uid", JOB_UID,
            "--panel-index-identity", "/missing/panel.json",
            "--lane-terminal-identity", "/missing/a.json",
            "--lane-terminal-identity", "/missing/b.json",
            "--matchup-source-release-identity", "/missing/source.json",
            "--runtime-image-authority-identity", "/missing/image.json",
            "--embedded-runtime-authority-identity", "/missing/embedded.json",
        ], storage=object(), provider=object())
