from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

import scripts.run_corpus_extreme_tail_hard230_r6_cloud_v1 as runtime
import scripts.run_corpus_extreme_tail_hard230_r6_score_run_v1 as operator
from nfl_dfs.research import corpus_extreme_tail_hard230_r6_cloud_entrypoint_v1 as entrypoint
from nfl_dfs.research import corpus_extreme_tail_hard230_r6_run_controller_v1 as controller
from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import corpus_r6_novel_roster_realized_grader_v1 as grader


PREFIX = f"{entrypoint.OUTPUT_NAMESPACE}hard230-score-run-test/"
IMAGE_URI = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/research/runtime@"
    "sha256:" + "2" * 64
)


class _Store:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, dict[str, object]]] = {}

    def seed(self, uri: str, value: object) -> dict[str, object]:
        raw = value if type(value) is bytes else legal.canonical_json_bytes(value)
        identity = {
            "uri": uri,
            "generation": str(len(self.objects) + 1),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[uri] = (raw, identity)
        return dict(identity)

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if uri in self.objects:
            prior, identity = self.objects[uri]
            if prior != raw:
                raise RuntimeError("create-once collision differs")
            return dict(identity)
        return self.seed(uri, raw)

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        raw, retained = self.objects[str(identity["uri"])]
        if dict(identity) != retained:
            raise RuntimeError("exact identity differs")
        return raw

    def open_known(
        self, uri: str, maximum_bytes: int
    ) -> tuple[bytes, dict[str, object]]:
        raw, identity = self.objects[uri]
        if len(raw) > maximum_bytes:
            raise RuntimeError("known object oversized")
        return raw, dict(identity)


def _opaque_identity(name: str) -> dict[str, object]:
    raw = legal.canonical_json_bytes({"name": name})
    return {
        "uri": f"gs://hard230-score-run-test/opaque/{name}.json",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _source_manifest(
    store: _Store, *, reused_job_name: str = controller.REUSED_JOB_NAME
):
    authorization = entrypoint.build_run_authorization_v1(
        panel_index_identity=_opaque_identity("panel"),
        later_source_freeze_identity=_opaque_identity("source"),
        optimizer_source_identity=_opaque_identity("optimizer"),
        terminal_build_receipt_identity=_opaque_identity("build"),
        output_prefix=PREFIX,
        source_commit_sha="1" * 40,
        immutable_image_digest="sha256:" + "2" * 64,
        reused_job_name=reused_job_name,
    )
    authorization_identity = store.seed(
        f"{PREFIX}authorities/run-authorization.json", authorization
    )
    task_rows = [
        {
            "task_index": index,
            "slate_id": f"2023-w{index + 1:02d}",
            "p0_population_receipt_identity": _opaque_identity(f"p0-{index}"),
        }
        for index in range(entrypoint.TASK_COUNT)
    ]
    manifest = entrypoint.build_task_manifest_v1(
        run_authorization=authorization,
        run_authorization_identity=authorization_identity,
        panel_index_sha256="3" * 64,
        later_source_freeze_sha256="4" * 64,
        task_rows=task_rows,
    )
    identity = store.seed(f"{PREFIX}authorities/task-manifest.json", manifest)
    return manifest, identity


def _prepare_smoke(store: _Store, source_identity: Mapping[str, object]):
    prepared = controller.prepare_controller_manifest_v1(
        source_task_manifest_identity=source_identity,
        scope_id=controller.TASK0_SMOKE_SCOPE,
        required_smoke_final_root_identity=None,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    raw = store.read_exact(prepared["controller_manifest_identity"])
    return prepared, json.loads(raw.decode("utf-8"))


def _population(role: str, *, marker: str) -> dict[str, object]:
    population_id = (
        controller.successor.CONTROL_POPULATION_ID
        if role == "control"
        else controller.successor.CHALLENGER_POPULATION_ID
    )
    players = [f"player-{marker}-{index}" for index in range(9)]
    roster_sha = controller._hash(players, label="fixture roster players")
    rosters = [{
        "lineup_id": f"lineup-v1-{roster_sha}",
        "roster_player_ids": players,
        "roster_sha256": roster_sha,
        "first_occurrence_ordinal": 0,
        "fit_world_score_vector_sha256": "b" * 64,
    }]
    return {
        "population_id": population_id,
        "population_lineup_count": 1,
        "population_rosters": rosters,
        "population_rosters_sha256": controller._hash(
            rosters, label="fixture population rosters"
        ),
        "uses_heldout_scores": False,
        "uses_realized_outcomes": False,
    }


def _seed_task_result(
    store: _Store,
    *,
    source_manifest: Mapping[str, object],
    source_identity: Mapping[str, object],
    task_index: int,
) -> None:
    task = source_manifest["task_rows"][task_index]
    control = _population("control", marker=f"c-{task_index}")
    challenger = _population("challenger", marker=f"h-{task_index}")
    scientific_receipt = controller.successor._self_hash({
        "schema_version": controller.successor.RECEIPT_SCHEMA,
        "target_retained_count": 1,
        "equal_solver_call_budget": True,
        "control_solver_call_budget": 1,
        "challenger_solver_call_budget": 1,
        "equal_observed_solver_call_count": True,
        "control_observed_solver_call_count": 1,
        "challenger_observed_solver_call_count": 1,
        "actual_shared_solver_call_count": 1,
        "solver_occurrences_shared_not_reexecuted": True,
        "does_not_use_frozen_stop_at_control_target_companion_law": True,
        "threshold_was_not_lowered": True,
        "score_blind_control_population": control,
        "hard230_challenger_population": challenger,
        **controller.successor._false_authorities(),
    }, "successor_receipt_sha256")
    process_receipt = controller.process._self_hash({
        "schema_version": controller.process.PROCESS_RECEIPT_SCHEMA,
        "process_contract_id": controller.process.PROCESS_CONTRACT_ID,
        "scientific_contract_id": controller.successor.CONTRACT_ID,
        "task_index": task_index,
        "slate_id": task["slate_id"],
        "scientific_receipt": scientific_receipt,
        "scientific_receipt_sha256": scientific_receipt[
            "successor_receipt_sha256"
        ],
        "publication_order_completed": "evidence-shards-then-index-then-root",
        "create_once_exact_reopen_completed": True,
        "terminal_execution_attestation_present": False,
        "outcome_columns_read": [],
        **controller.process._false_authorities(),
    }, "process_receipt_sha256")
    process_identity = store.seed(
        f"{task['task_output_prefix']}process/process-receipt.json",
        process_receipt,
    )
    fake = lambda name: _opaque_identity(f"task-{task_index}-{name}")
    body = {
        "schema_version": entrypoint.TASK_RESULT_SCHEMA,
        "contract_id": entrypoint.CONTRACT_ID,
        "mode_id": entrypoint.MODE_ID,
        "complete": True,
        "task_index": task_index,
        "slate_id": task["slate_id"],
        "task_manifest_identity": dict(source_identity),
        "task_manifest_sha256": source_manifest["task_manifest_sha256"],
        "p0_population_receipt_identity": task[
            "p0_population_receipt_identity"
        ],
        "p0_population_result_sha256": "5" * 64,
        "p0_target_authority_identity": fake("p0-target"),
        "p0_target_authority_sha256": "6" * 64,
        "p0_target_count": 1,
        "world_permutation_derivation_identity": fake("derivation"),
        "world_permutation_authority_identity": fake("permutation"),
        "world_permutation_authority_sha256": "7" * 64,
        "source_member_identity": fake("source-member"),
        "score_matrix_identity": fake("score-matrix"),
        "process_budget_identity": fake("budget"),
        "runtime_authority_identity": fake("runtime"),
        "process_request_identity": fake("request"),
        "process_receipt_identity": process_identity,
        "process_receipt_sha256": process_receipt["process_receipt_sha256"],
        "evidence_index_identity": fake("evidence"),
        "evidence_index_sha256": "8" * 64,
        "actual_shared_solver_call_count": 1,
        "hard230_exact_target_reached": True,
        "hard230_shortfall": 0,
        "score_blind_control_population_count": 1,
        "score_blind_control_population_sha256": control[
            "population_rosters_sha256"
        ],
        "hard230_challenger_population_count": 1,
        "hard230_challenger_population_sha256": challenger[
            "population_rosters_sha256"
        ],
        "terminal_execution_attestation_present": False,
        "outcome_columns_read": [],
        **entrypoint._false_authorities(),
    }
    task_result = entrypoint._self_hash(body, "task_result_sha256")
    store.seed(f"{task['task_output_prefix']}task-result.json", task_result)


def _launch_receipt(
    store: _Store,
    *,
    manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object],
    suffix: str = "abc12",
) -> tuple[dict[str, object], dict[str, object]]:
    value = controller.build_launch_receipt_v1(
        controller_manifest=manifest,
        controller_manifest_identity=manifest_identity,
        job_uid=controller.REUSED_JOB_UID,
        execution_name=f"{controller.REUSED_JOB_NAME}-{suffix}",
    )
    identity = store.seed(str(manifest["launch_receipt_uri"]), value)
    return value, identity


def _collect_smoke(monkeypatch: pytest.MonkeyPatch):
    store = _Store()
    source, source_identity = _source_manifest(store)
    prepared, manifest = _prepare_smoke(store, source_identity)
    _, launch_identity = _launch_receipt(
        store,
        manifest=manifest,
        manifest_identity=prepared["controller_manifest_identity"],
    )
    _seed_task_result(
        store,
        source_manifest=source,
        source_identity=source_identity,
        task_index=0,
    )
    finalized = controller.collect_and_publish_final_root_v1(
        controller_manifest_identity=prepared["controller_manifest_identity"],
        launch_receipt_identity=launch_identity,
        read_exact=store.read_exact,
        open_known=store.open_known,
        publish_create_once=store.publish_create_once,
    )
    return store, source, source_identity, prepared, manifest, finalized


def test_smoke_then_full_manifests_pin_idle_job_and_exact_fanout(monkeypatch) -> None:
    store, _, source_identity, smoke, _, finalized = _collect_smoke(monkeypatch)
    smoke_config = smoke["cloud_run_job_configuration"]
    assert smoke_config["task_count"] == smoke_config["parallelism"] == 1
    assert smoke_config["reused_job_name"] == controller.REUSED_JOB_NAME
    assert smoke_config["reused_job_uid"] == controller.REUSED_JOB_UID
    assert smoke_config["container_args"][-1] == "execute-controller-task"

    full = controller.prepare_controller_manifest_v1(
        source_task_manifest_identity=source_identity,
        scope_id=controller.FULL_54_SCOPE,
        required_smoke_final_root_identity=finalized["final_root_identity"],
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    full_raw = store.read_exact(full["controller_manifest_identity"])
    full_manifest = json.loads(full_raw.decode("utf-8"))
    assert full_manifest["source_reused_job_name"] == controller.REUSED_JOB_NAME
    assert full_manifest["reused_job_name"] == controller.REUSED_JOB_NAME
    assert full_manifest["reused_job_uid"] == controller.REUSED_JOB_UID
    assert full_manifest["scientific_task_indices"] == list(range(54))
    assert full["cloud_run_job_configuration"]["task_count"] == 54
    assert full["cloud_run_job_configuration"]["parallelism"] == 54


def test_controller_rejects_source_manifest_pinned_to_active_job() -> None:
    store = _Store()
    _, source_identity = _source_manifest(
        store, reused_job_name="atlas-cbc-32g-full-2023-w8-v1"
    )
    with pytest.raises(
        controller.Hard230R6RunControllerV1Error,
        match="fixed idle job differs",
    ):
        controller.prepare_controller_manifest_v1(
            source_task_manifest_identity=source_identity,
            scope_id=controller.TASK0_SMOKE_SCOPE,
            required_smoke_final_root_identity=None,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )


def test_final_root_exposes_exact_process_population_paths_for_generic_grader(
    monkeypatch,
) -> None:
    store, _, _, _, manifest, finalized = _collect_smoke(monkeypatch)
    raw = store.read_exact(finalized["final_root_identity"])
    root = json.loads(raw.decode("utf-8"))
    assert root["complete"] is True
    assert root["scientific_task_count"] == 1
    assert root["population_descriptor_count"] == 2
    roles = root["task_records"][0]["populations"]
    assert [row["population_role"] for row in roles] == [
        "score-blind-control",
        "hard230-challenger",
    ]
    assert roles[0]["population_rosters_json_pointer"].endswith(
        "/score_blind_control_population/population_rosters"
    )
    assert roles[1]["population_rosters_json_pointer"].endswith(
        "/hard230_challenger_population/population_rosters"
    )
    controller.validate_final_root_v1(
        root,
        controller_manifest=manifest,
        controller_manifest_identity=root["controller_manifest_identity"],
    )


def test_collection_rejects_task_result_population_hash_drift(monkeypatch) -> None:
    store = _Store()
    source, source_identity = _source_manifest(store)
    prepared, manifest = _prepare_smoke(store, source_identity)
    _, launch_identity = _launch_receipt(
        store,
        manifest=manifest,
        manifest_identity=prepared["controller_manifest_identity"],
    )
    _seed_task_result(
        store,
        source_manifest=source,
        source_identity=source_identity,
        task_index=0,
    )
    uri = source["task_rows"][0]["task_output_prefix"] + "task-result.json"
    raw, _ = store.objects[uri]
    forged = json.loads(raw.decode("utf-8"))
    forged["score_blind_control_population_sha256"] = "f" * 64
    forged.pop("task_result_sha256")
    forged = entrypoint._self_hash(forged, "task_result_sha256")
    store.objects.pop(uri)
    store.seed(uri, forged)
    with pytest.raises(
        controller.Hard230R6RunControllerV1Error,
        match="population count/hash binding differs",
    ):
        controller.collect_and_publish_final_root_v1(
            controller_manifest_identity=prepared["controller_manifest_identity"],
            launch_receipt_identity=launch_identity,
            read_exact=store.read_exact,
            open_known=store.open_known,
            publish_create_once=store.publish_create_once,
        )


def test_controller_cloud_task_maps_smoke_zero_without_changing_science(
    monkeypatch,
) -> None:
    store = _Store()
    source, source_identity = _source_manifest(store)
    prepared, manifest = _prepare_smoke(store, source_identity)
    observed: dict[str, object] = {}

    def execute(**kwargs):
        observed.update(kwargs)
        task_result = {
            "slate_id": source["task_rows"][0]["slate_id"],
            "task_result_sha256": "9" * 64,
        }
        return SimpleNamespace(
            task_result=task_result,
            task_result_identity=_opaque_identity("task-result"),
        )

    monkeypatch.setattr(entrypoint, "execute_manifest_task_v1", execute)
    monkeypatch.setenv(entrypoint.ENABLE_ENV, "1")
    monkeypatch.setenv(
        controller.CONTROLLER_MANIFEST_IDENTITY_ENV,
        legal.canonical_json_bytes(
            prepared["controller_manifest_identity"]
        ).decode("utf-8"),
    )
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "0")
    monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", "1")
    monkeypatch.setenv("CLOUD_RUN_TASK_ATTEMPT", "0")
    monkeypatch.setenv("CODE_SHA", manifest["source_commit_sha"])
    monkeypatch.setenv(
        "R6_RUNTIME_IMAGE_DIGEST", manifest["immutable_image_digest"]
    )
    monkeypatch.setenv("CLOUD_RUN_JOB", controller.REUSED_JOB_NAME)
    completion = runtime._execute_controller_cloud_task(store)
    assert completion["cloud_task_index"] == 0
    assert completion["scientific_task_index"] == 0
    assert observed["manifest_identity"] == source_identity
    assert observed["task_index"] == 0


def test_full_controller_task0_reuses_accepted_smoke_without_recomputing(
    monkeypatch,
) -> None:
    store, _, source_identity, _, _, finalized = _collect_smoke(monkeypatch)
    full = controller.prepare_controller_manifest_v1(
        source_task_manifest_identity=source_identity,
        scope_id=controller.FULL_54_SCOPE,
        required_smoke_final_root_identity=finalized["final_root_identity"],
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    manifest = json.loads(
        store.read_exact(full["controller_manifest_identity"]).decode("utf-8")
    )
    monkeypatch.setattr(
        entrypoint,
        "execute_manifest_task_v1",
        lambda **_: pytest.fail("full task0 must reuse the accepted smoke result"),
    )
    monkeypatch.setenv(entrypoint.ENABLE_ENV, "1")
    monkeypatch.setenv(
        controller.CONTROLLER_MANIFEST_IDENTITY_ENV,
        legal.canonical_json_bytes(
            full["controller_manifest_identity"]
        ).decode("utf-8"),
    )
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "0")
    monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", "54")
    monkeypatch.setenv("CLOUD_RUN_TASK_ATTEMPT", "0")
    monkeypatch.setenv("CODE_SHA", manifest["source_commit_sha"])
    monkeypatch.setenv(
        "R6_RUNTIME_IMAGE_DIGEST", manifest["immutable_image_digest"]
    )
    monkeypatch.setenv("CLOUD_RUN_JOB", controller.REUSED_JOB_NAME)
    completion = runtime._execute_controller_cloud_task(store)
    assert completion["scientific_task_index"] == 0
    assert completion["reused_required_smoke_task0_result"] is True


def _job_description(
    manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object],
    *,
    image_uri: str,
) -> dict[str, object]:
    config = controller.build_controller_job_configuration_v1(
        controller_manifest=manifest,
        controller_manifest_identity=manifest_identity,
    )
    return {
        "metadata": {
            "name": manifest["reused_job_name"],
            "uid": manifest["reused_job_uid"],
            "generation": "7",
        },
        "spec": {
            "template": {
                "spec": {
                    "taskCount": config["task_count"],
                    "parallelism": config["parallelism"],
                    "template": {
                        "spec": {
                            "maxRetries": 0,
                            "timeoutSeconds": f"{config['timeout_seconds']}s",
                            "containers": [{
                                "image": image_uri,
                                "command": config["container_command"],
                                "args": config["container_args"],
                                "env": [
                                    {"name": key, "value": value}
                                    for key, value in config[
                                        "container_environment"
                                    ].items()
                                ],
                                "resources": {
                                    "limits": {
                                        "cpu": config["cpu"],
                                        "memory": config["memory"],
                                    }
                                },
                            }],
                        }
                    },
                }
            }
        },
        "status": {},
    }


class _LaunchRunner:
    def __init__(
        self,
        manifest: Mapping[str, object],
        manifest_identity: Mapping[str, object],
    ) -> None:
        self.job = _job_description(
            manifest, manifest_identity, image_uri=IMAGE_URI
        )
        self.execution = f"{controller.REUSED_JOB_NAME}-abc12"
        self.calls: list[list[str]] = []

    def __call__(self, argv: Sequence[str]) -> dict[str, object]:
        command = list(argv)
        self.calls.append(command)
        if command[:4] == ["gcloud", "run", "jobs", "describe"]:
            raw = json.dumps(self.job).encode("utf-8")
        elif command[:4] == ["gcloud", "run", "jobs", "update"]:
            raw = b"{}"
        elif command[:4] == ["gcloud", "run", "jobs", "execute"]:
            raw = self.execution.encode("utf-8") + b"\n"
        else:
            raise AssertionError(command)
        return {"returncode": 0, "stdout": raw, "stderr": b""}


class _StatusRunner:
    def __init__(self, *, execution: str, task_count: int) -> None:
        self.execution = execution
        self.task_count = task_count
        self.task_calls = 0

    def __call__(self, argv: Sequence[str]) -> dict[str, object]:
        command = list(argv)
        if command[2:5] == ["jobs", "executions", "describe"]:
            value = {
                "metadata": {
                    "name": self.execution,
                    "uid": "execution-uid",
                    "generation": "3",
                    "labels": {
                        "run.googleapis.com/job": controller.REUSED_JOB_NAME,
                        "run.googleapis.com/jobUid": controller.REUSED_JOB_UID,
                    },
                },
                "status": {
                    "conditions": [{
                        "type": "Completed",
                        "state": "CONDITION_SUCCEEDED",
                    }],
                    "completionTime": "2026-08-28T18:00:00Z",
                    "succeededCount": self.task_count,
                },
            }
        elif command[2:6] == ["jobs", "executions", "tasks", "describe"]:
            index = self.task_calls
            self.task_calls += 1
            value = {
                "metadata": {
                    "name": f"{self.execution}-task{index}",
                    "labels": {
                        "run.googleapis.com/execution": self.execution,
                    },
                },
                "status": {
                    "index": index,
                    "retried": 0,
                    "conditions": [{
                        "type": "Completed",
                        "state": "CONDITION_SUCCEEDED",
                    }],
                    "completionTime": "2026-08-28T18:00:00Z",
                    "succeededCount": 1,
                    "lastAttemptResult": {"exitCode": 0},
                },
            }
        else:
            raise AssertionError(command)
        return {
            "returncode": 0,
            "stdout": json.dumps(value).encode("utf-8"),
            "stderr": b"",
        }


def test_launch_and_status_use_fixed_job_and_manifest_task_count() -> None:
    store = _Store()
    _, source_identity = _source_manifest(store)
    prepared, manifest = _prepare_smoke(store, source_identity)
    launch_runner = _LaunchRunner(
        manifest, prepared["controller_manifest_identity"]
    )
    launched = operator.launch_controller_run_v1(
        controller_manifest_identity=prepared["controller_manifest_identity"],
        image_uri=IMAGE_URI,
        store=store,
        runner=launch_runner,
    )
    assert launched["job_name"] == controller.REUSED_JOB_NAME
    assert launched["job_uid"] == controller.REUSED_JOB_UID
    assert launched["cloud_task_count"] == 1
    assert sum("update" in call for call in launch_runner.calls) == 1
    assert sum("execute" in call for call in launch_runner.calls) == 1

    status_runner = _StatusRunner(
        execution=launched["execution_name"], task_count=1
    )
    status = operator.status_controller_run_v1(
        launch_result=launched, store=store, runner=status_runner
    )
    assert status["all_tasks_succeeded"] is True
    assert status_runner.task_calls == 1
    assert status["task_statuses"][0]["scientific_task_index"] == 0


def test_full_status_describes_exactly_54_known_tasks(monkeypatch) -> None:
    store, _, source_identity, _, _, finalized = _collect_smoke(monkeypatch)
    full = controller.prepare_controller_manifest_v1(
        source_task_manifest_identity=source_identity,
        scope_id=controller.FULL_54_SCOPE,
        required_smoke_final_root_identity=finalized["final_root_identity"],
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    manifest = json.loads(
        store.read_exact(full["controller_manifest_identity"]).decode("utf-8")
    )
    launch_runner = _LaunchRunner(manifest, full["controller_manifest_identity"])
    launched = operator.launch_controller_run_v1(
        controller_manifest_identity=full["controller_manifest_identity"],
        image_uri=IMAGE_URI,
        store=store,
        runner=launch_runner,
    )
    status_runner = _StatusRunner(
        execution=launched["execution_name"], task_count=54
    )
    status = operator.status_controller_run_v1(
        launch_result=launched, store=store, runner=status_runner
    )
    assert status["cloud_task_count"] == 54
    assert status_runner.task_calls == 54
    assert [row["scientific_task_index"] for row in status["task_statuses"]] == list(
        range(54)
    )


def test_full_final_root_is_accepted_by_generic_hard230_grader_adapter(
    monkeypatch,
) -> None:
    store, source, source_identity, _, _, smoke_finalized = _collect_smoke(
        monkeypatch
    )
    full = controller.prepare_controller_manifest_v1(
        source_task_manifest_identity=source_identity,
        scope_id=controller.FULL_54_SCOPE,
        required_smoke_final_root_identity=smoke_finalized["final_root_identity"],
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    full_manifest = json.loads(
        store.read_exact(full["controller_manifest_identity"]).decode("utf-8")
    )
    _, full_launch_identity = _launch_receipt(
        store,
        manifest=full_manifest,
        manifest_identity=full["controller_manifest_identity"],
        suffix="full54",
    )
    for task_index in range(1, 54):
        _seed_task_result(
            store,
            source_manifest=source,
            source_identity=source_identity,
            task_index=task_index,
        )
    full_finalized = controller.collect_and_publish_final_root_v1(
        controller_manifest_identity=full["controller_manifest_identity"],
        launch_receipt_identity=full_launch_identity,
        read_exact=store.read_exact,
        open_known=store.open_known,
        publish_create_once=store.publish_create_once,
    )
    final_root = json.loads(
        store.read_exact(full_finalized["final_root_identity"]).decode("utf-8")
    )
    grader_inputs = controller.novel_roster_grader_inputs_from_final_root_v1(
        final_root=final_root,
        controller_manifest=full_manifest,
        controller_manifest_identity=full["controller_manifest_identity"],
    )
    generic_root, generic_identity = grader.publish_terminal_experiment_root_v1(
        **grader_inputs,
        target_uri=f"{PREFIX}generic-grader/terminal-root.json",
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    assert generic_root["adapter_id"] == grader.HARD230_ADAPTER
    assert generic_root["source_slate_count"] == 54
    assert generic_root["complete"] is True
    reopened, identity, opened = grader.reopen_terminal_experiment_v1(
        terminal_root_identity=generic_identity,
        read_terminal_exact=store.read_exact,
    )
    assert reopened == generic_root
    assert identity == generic_identity
    assert len(opened.slates) == 54


def test_full_prepare_requires_completed_matching_smoke_root() -> None:
    store = _Store()
    _, source_identity = _source_manifest(store)
    with pytest.raises(
        (controller.Hard230R6RunControllerV1Error, TypeError),
    ):
        controller.prepare_controller_manifest_v1(
            source_task_manifest_identity=source_identity,
            scope_id=controller.FULL_54_SCOPE,
            required_smoke_final_root_identity=None,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
