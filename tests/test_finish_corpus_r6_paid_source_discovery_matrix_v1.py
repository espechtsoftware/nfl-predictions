from __future__ import annotations

import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts import finish_corpus_r6_paid_source_discovery_matrix_v1 as finisher
from nfl_dfs.research import corpus_r6_paid_source_discovery_matrix_freeze_v1 as freeze


RUN_ID = "20260911-fp-sis-discovery-matrix-successor-v1"
CODE_SHA = "1" * 40
BUILD_ID = "11111111-2222-3333-8444-555555555555"
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
    "nfl-dfs@sha256:" + "2" * 64
)
EXECUTION_UID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def _identity(uri: str, raw: bytes = b"fixture", generation: str = "1") -> dict[str, object]:
    return {
        "uri": uri, "generation": generation,
        "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
    }


def _prepare_request() -> dict[str, object]:
    return {
        "run_id": RUN_ID, "code_sha": CODE_SHA,
        "immutable_image": IMAGE, "build_id": BUILD_ID,
        "runtime_build_attestation_identity": _identity(
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            f"corpus-r6-paid-source-discovery-matrix-builds/{CODE_SHA}/{BUILD_ID}/"
            "runtime-build-attestation.json"
        ),
        "candidate_root_identity": freeze.CANDIDATE_ROOT_IDENTITY,
        "later_source_freeze_identity": freeze.LATER_SOURCE_FREEZE_IDENTITY,
    }


def _payload() -> tuple[dict[str, object], bytes]:
    identity = _identity("gs://fixture/manifest.json")
    return identity, finisher.canonical_bytes(identity)


def _execution(
    *,
    mode: str,
    payload: bytes,
    name: str | None = None,
    completed: str | None = None,
    succeeded: int = 0,
    running: int = 0,
    failed: int = 0,
    cancelled: int = 0,
    retried: int = 0,
) -> dict[str, object]:
    name = name or finisher.JOB + "-abc12"
    task_count = 1 if mode == "task0" else freeze.TASK_COUNT
    environment = {
        "CODE_SHA": CODE_SHA, "IMAGE_URI": IMAGE,
        "IMAGE_DIGEST": IMAGE.rsplit("@", 1)[-1], "BUILD_ID": BUILD_ID,
        finisher.ENABLE_ENV: finisher.ENABLE_VALUE,
        finisher.MODE_ENV: mode, finisher.OUTCOMES_ENV: "false",
        finisher.PAYLOAD_ENV: base64.b64encode(payload).decode("ascii"),
        finisher.PAYLOAD_SHA_ENV: sha256(payload).hexdigest(),
        finisher.TASK0_EXECUTION_ENV: "none",
        finisher.TASK0_GATE_SHA_ENV: "none",
        finisher.TASK0_GATE_B64_ENV: "none",
    }
    conditions = [] if completed is None else [
        {"type": "Completed", "status": completed}
    ]
    status: dict[str, object] = {
        "conditions": conditions, "succeededCount": succeeded,
        "runningCount": running, "failedCount": failed,
        "cancelledCount": cancelled, "retriedCount": retried,
    }
    if completed in {"True", "False"}:
        status["completionTime"] = "2026-09-11T12:00:00Z"
    return {
        "metadata": {
            "name": name, "uid": EXECUTION_UID,
            "labels": {
                "run.googleapis.com/job": finisher.JOB,
                "run.googleapis.com/jobUid": finisher.JOB_UID,
                "run.googleapis.com/jobGeneration": "9",
            },
        },
        "spec": {
            "taskCount": task_count, "parallelism": task_count,
            "template": {"spec": {
                "maxRetries": 0,
                "timeoutSeconds": freeze.TASK_TIMEOUT_SECONDS,
                "serviceAccountName": freeze.SERVICE_ACCOUNT,
                "containers": [{
                    "image": IMAGE, "command": list(freeze.CONTAINER_COMMAND),
                    "args": [freeze.CONTAINER_SCRIPT, "container-run", mode],
                    "resources": {"limits": {
                        "cpu": freeze.CPU_LIMIT, "memory": freeze.MEMORY_LIMIT,
                    }},
                    "env": [
                        {"name": key, "value": value}
                        for key, value in environment.items()
                    ],
                }],
            }},
        },
        "status": status,
    }


def _build_receipt() -> dict[str, object]:
    return {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-host-build/v1",
        "code_sha": CODE_SHA, "cloud_build_id": BUILD_ID,
        "provider_resolved_image": IMAGE, "provider_build_sha256": "3" * 64,
        "provider_requested_and_resolved_git_source_exact": True,
        "complete": True,
    }


class _Runner(finisher.CommandRunner):
    def __init__(self, callback):
        self.callback = callback
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv, *, cwd=None, env=None):
        retained = tuple(argv)
        self.calls.append(retained)
        return self.callback(retained)


def _controller(tmp_path: Path, runner: _Runner) -> finisher.DiscoveryMatrixFinisher:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "build.json").write_bytes(finisher.canonical_bytes(_build_receipt()))
    return finisher.DiscoveryMatrixFinisher(
        run_id=RUN_ID, code_sha=CODE_SHA, build_id=BUILD_ID, image=IMAGE,
        run_dir=tmp_path, prepare_request=_prepare_request(), runner=runner,
        object_exists=lambda uri: False, poll_interval_seconds=1,
        max_polls=5, reconcile_polls=2, collect_polls=2,
        preflight_workers=1, sleeper=lambda seconds: None,
    )


def test_output_inventory_is_exact_165_without_listing() -> None:
    inventory = finisher.output_uri_inventory(RUN_ID)
    assert len(inventory) == len(set(inventory)) == 165
    assert inventory[0].startswith(f"{freeze.OUTPUT_PREFIX}/{RUN_ID}/")
    assert f"{freeze.OUTPUT_PREFIX}/{RUN_ID}/manifest.json" in inventory
    assert f"{freeze.OUTPUT_PREFIX}/{RUN_ID}/terminal.json" in inventory
    assert f"{freeze.OUTPUT_PREFIX}/{RUN_ID}/reopen-terminal.json" in inventory
    assert sum(uri.endswith("candidate-discovery-matrix.bin") for uri in inventory) == 54
    assert sum(uri.endswith("/task-result.json") for uri in inventory) == 54
    assert sum(uri.endswith("reopen-task-result.json") for uri in inventory) == 54


def test_persisted_clean_preflight_is_reprobed_before_first_intent(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    controller = _controller(
        tmp_path,
        _Runner(lambda argv: (_ for _ in ()).throw(AssertionError(argv))),
    )

    def absent(uri: str) -> bool:
        calls.append(uri)
        return False

    controller.object_exists = absent
    controller._preflight()
    controller._preflight()
    assert len(calls) == 330
    assert calls[:165] == calls[165:]


def test_prepare_result_requires_two_exact_boolean_publication_flags() -> None:
    result = {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-prepare-result/v1",
        "manifest_identity": _identity(
            f"{freeze.OUTPUT_PREFIX}/{RUN_ID}/manifest.json"
        ),
        "manifest_sha256": "4" * 64, "task_count": freeze.TASK_COUNT,
        "publication_performed": False, "ambiguous_return_reconciled": True,
        "uses_realized_outcomes": False, "complete": True,
    }
    assert finisher.validate_prepare_result(result, run_id=RUN_ID) == result
    for invalid in (0, 1, None, "true"):
        changed = {**result, "ambiguous_return_reconciled": invalid}
        with pytest.raises(finisher.DiscoveryMatrixFinisherError):
            finisher.validate_prepare_result(changed, run_id=RUN_ID)


@pytest.mark.parametrize("condition", [None, "Unknown"])
def test_54_task_provider_wait_accepts_partial_success(
    condition: str | None,
) -> None:
    _, payload = _payload()
    value = _execution(
        mode="reopen-task", payload=payload, completed=condition,
        succeeded=17, running=5,
    )
    _, state = finisher.validate_provider_execution(
        value, mode="reopen-task", execution_name=finisher.JOB + "-abc12",
        execution_uid=EXECUTION_UID, code_sha=CODE_SHA, build_id=BUILD_ID,
        image=IMAGE, payload=payload, task0_execution="none",
    )
    assert state == ("MISSING" if condition is None else "Unknown")


def test_provider_wait_accepts_completion_time_before_completed_condition() -> None:
    _, payload = _payload()
    value = _execution(
        mode="reopen-task", payload=payload, completed=None,
        succeeded=freeze.TASK_COUNT,
    )
    value["status"]["completionTime"] = "2026-09-11T12:00:00Z"  # type: ignore[index]
    _, state = finisher.validate_provider_execution(
        value, mode="reopen-task", execution_name=finisher.JOB + "-abc12",
        execution_uid=EXECUTION_UID, code_sha=CODE_SHA, build_id=BUILD_ID,
        image=IMAGE, payload=payload, task0_execution="none",
    )
    assert state == "MISSING"


def test_provider_terminal_and_contradictory_states_fail_closed() -> None:
    _, payload = _payload()
    success = _execution(
        mode="reopen-task", payload=payload, completed="True",
        succeeded=freeze.TASK_COUNT,
    )
    _, state = finisher.validate_provider_execution(
        success, mode="reopen-task", execution_name=finisher.JOB + "-abc12",
        execution_uid=EXECUTION_UID, code_sha=CODE_SHA, build_id=BUILD_ID,
        image=IMAGE, payload=payload, task0_execution="none",
    )
    assert state == "True"

    failed = _execution(
        mode="reopen-task", payload=payload, completed="False",
        succeeded=17, failed=1,
    )
    _, state = finisher.validate_provider_execution(
        failed, mode="reopen-task", execution_name=finisher.JOB + "-abc12",
        execution_uid=EXECUTION_UID, code_sha=CODE_SHA, build_id=BUILD_ID,
        image=IMAGE, payload=payload, task0_execution="none",
    )
    assert state == "False"

    contradictory = deepcopy(success)
    contradictory["status"]["conditions"].append(  # type: ignore[index]
        {"type": "Completed", "status": "False"}
    )
    with pytest.raises(finisher.DiscoveryMatrixFinisherError):
        finisher.validate_provider_execution(
            contradictory, mode="reopen-task",
            execution_name=finisher.JOB + "-abc12",
            execution_uid=EXECUTION_UID, code_sha=CODE_SHA, build_id=BUILD_ID,
            image=IMAGE, payload=payload, task0_execution="none",
        )

    retried = deepcopy(success)
    retried["status"]["retriedCount"] = 1  # type: ignore[index]
    with pytest.raises(
        finisher.DiscoveryMatrixFinisherError,
        match="task census differs",
    ):
        finisher.validate_provider_execution(
            retried, mode="reopen-task", execution_name=finisher.JOB + "-abc12",
            execution_uid=EXECUTION_UID, code_sha=CODE_SHA, build_id=BUILD_ID,
            image=IMAGE, payload=payload, task0_execution="none",
        )


def test_transient_provider_describe_does_not_create_a_poll_index_gap(
    tmp_path: Path,
) -> None:
    _, payload = _payload()
    name = finisher.JOB + "-abc12"
    success = _execution(
        mode="task0", payload=payload, name=name,
        completed="True", succeeded=1,
    )
    observations = iter((
        finisher.CommandResult(1, stderr=b"transient"),
        finisher.CommandResult(0, json.dumps(success).encode()),
    ))

    def callback(argv):
        assert argv[:5] == ("gcloud", "run", "jobs", "executions", "describe")
        return next(observations)

    controller = _controller(tmp_path, _Runner(callback))
    terminal = controller._poll_terminal(
        phase="task0",
        launch={"execution": {"name": name, "uid": EXECUTION_UID}},
        payload=payload, task0_execution="none",
    )
    assert terminal == success
    polls = tmp_path / "phases/task0/provider-polls"
    assert [path.name for path in polls.iterdir()] == ["0000.json"]


def test_install_reconciliation_requires_exact_default_off_generation() -> None:
    previous = finisher.JOB + "-old12"
    environment = {
        "CODE_SHA": CODE_SHA, "IMAGE_URI": IMAGE,
        "IMAGE_DIGEST": IMAGE.rsplit("@", 1)[-1], "BUILD_ID": BUILD_ID,
        finisher.ENABLE_ENV: "DISABLED", finisher.MODE_ENV: "DISABLED",
        finisher.OUTCOMES_ENV: "false",
        finisher.TASK0_EXECUTION_ENV: "none",
        finisher.TASK0_GATE_SHA_ENV: "none",
        finisher.TASK0_GATE_B64_ENV: "none",
    }
    job = {
        "metadata": {
            "name": finisher.JOB, "uid": finisher.JOB_UID, "generation": 10,
        },
        "spec": {"template": {"spec": {
            "taskCount": freeze.TASK_COUNT,
            "parallelism": freeze.TASK_COUNT,
            "template": {"spec": {
                "maxRetries": 0,
                "timeoutSeconds": freeze.TASK_TIMEOUT_SECONDS,
                "serviceAccountName": freeze.SERVICE_ACCOUNT,
                "containers": [{
                    "image": IMAGE, "command": list(freeze.CONTAINER_COMMAND),
                    "args": [freeze.CONTAINER_SCRIPT, "container-help"],
                    "resources": {"limits": {
                        "cpu": freeze.CPU_LIMIT, "memory": freeze.MEMORY_LIMIT,
                    }},
                    "env": [
                        {"name": key, "value": value}
                        for key, value in environment.items()
                    ],
                }],
            }},
        }}},
        "status": {
            "observedGeneration": 10,
            "conditions": [{"type": "Ready", "status": "True"}],
            "latestCreatedExecution": {"name": previous},
        },
    }
    assert finisher.validate_installed_job(
        job, code_sha=CODE_SHA, build_id=BUILD_ID, image=IMAGE,
        previous_latest=previous, minimum_generation=9,
    ) == job
    stale = deepcopy(job)
    stale["metadata"]["generation"] = 9  # type: ignore[index]
    stale["status"]["observedGeneration"] = 9  # type: ignore[index]
    with pytest.raises(
        finisher.DiscoveryMatrixFinisherError,
        match="default-off job differs",
    ):
        finisher.validate_installed_job(
            stale, code_sha=CODE_SHA, build_id=BUILD_ID, image=IMAGE,
            previous_latest=previous, minimum_generation=9,
        )


def test_consumed_prepare_intent_uses_only_read_only_reconciliation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    manifest_identity = _identity(
        f"{freeze.OUTPUT_PREFIX}/{RUN_ID}/manifest.json", b"manifest", "7"
    )
    result = {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-prepare-result/v1",
        "manifest_identity": manifest_identity, "manifest_sha256": "4" * 64,
        "task_count": freeze.TASK_COUNT, "publication_performed": False,
        "ambiguous_return_reconciled": True, "uses_realized_outcomes": False,
        "complete": True,
    }

    def callback(argv):
        assert argv[1] == "reconcile-prepare"
        return finisher.CommandResult(0, finisher.canonical_bytes(result))

    runner = _Runner(callback)
    controller = _controller(tmp_path, runner)
    monkeypatch.setattr(finisher, "validate_exact_repository", lambda **kwargs: None)
    request = _prepare_request()
    (tmp_path / "prepare").mkdir()
    (tmp_path / "prepare/request.json").write_bytes(finisher.canonical_bytes(request))
    intent = {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-host-prepare-intent/v1",
        "run_id": RUN_ID, "code_sha": CODE_SHA, "cloud_build_id": BUILD_ID,
        "provider_resolved_image": IMAGE,
        "request_sha256": finisher.canonical_sha256(request),
        "target_uri": f"{freeze.OUTPUT_PREFIX}/{RUN_ID}/manifest.json",
        "automatic_republication": False,
        "ambiguous_return_recovery": "exact-known-uri-read-only",
        "complete": True,
    }
    (tmp_path / "prepare/intent.json").write_bytes(finisher.canonical_bytes(intent))

    assert controller.prepare()["manifest_identity"] == manifest_identity
    assert [call[1] for call in runner.calls] == ["reconcile-prepare"]


def test_consumed_launch_intent_never_invokes_wrapper(tmp_path: Path) -> None:
    identity, payload = _payload()
    new_name = finisher.JOB + "-new12"
    provider = _execution(
        mode="task0", payload=payload, name=new_name,
        completed="Unknown", running=1,
    )
    job = {
        "metadata": {"name": finisher.JOB, "uid": finisher.JOB_UID},
        "status": {"latestCreatedExecution": {"name": new_name}},
    }

    def callback(argv):
        if argv[:4] == ("gcloud", "run", "jobs", "describe"):
            return finisher.CommandResult(0, json.dumps(job).encode())
        if argv[:5] == ("gcloud", "run", "jobs", "executions", "describe"):
            return finisher.CommandResult(0, json.dumps(provider).encode())
        raise AssertionError(f"wrapper mutation unexpectedly invoked: {argv}")

    runner = _Runner(callback)
    controller = _controller(tmp_path, runner)
    (tmp_path / "manifest-identity.json").write_bytes(payload)
    phase = tmp_path / "phases/task0"
    phase.mkdir(parents=True)
    request = {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-host-phase-request/v1",
        "run_id": RUN_ID, "phase": "task0", "code_sha": CODE_SHA,
        "cloud_build_id": BUILD_ID, "provider_resolved_image": IMAGE,
        "payload_identity": identity, "payload_file_sha256": sha256(payload).hexdigest(),
        "payload_file_bytes": len(payload), "task_count": 1,
        "bound_task0_execution": "none", "outcomes_allowed": False,
        "complete": True,
    }
    (phase / "request.json").write_bytes(finisher.canonical_bytes(request))
    before = {
        "name": finisher.JOB + "-old12",
        "uid": "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
        "provider_sha256": "5" * 64,
    }
    (phase / "provider-before.json").write_bytes(finisher.canonical_bytes(before))
    intent = {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-host-launch-intent/v1",
        "run_id": RUN_ID, "phase": "task0",
        "request_sha256": finisher.canonical_sha256(request),
        "provider_latest_before": {"name": before["name"], "uid": before["uid"]},
        "automatic_relaunch": False,
        "ambiguous_return_recovery": "exact-provider-latest-name-uid-envelope-only",
        "complete": True,
    }
    (phase / "launch-intent.json").write_bytes(finisher.canonical_bytes(intent))

    launch = controller._launch_or_recover(
        phase="task0", prior={}, payload_path=tmp_path / "manifest-identity.json",
    )
    assert launch["execution"]["name"] == new_name  # type: ignore[index]
    assert all(call[0] == "gcloud" for call in runner.calls)


def test_recovery_identity_is_rejected_before_a_launch_intent_exists(
    tmp_path: Path,
) -> None:
    identity, payload = _payload()
    runner = _Runner(
        lambda argv: (_ for _ in ()).throw(
            AssertionError(f"provider/wrapper call unexpectedly reached: {argv}")
        )
    )
    controller = _controller(tmp_path, runner)
    controller.recovery_executions = {
        "task0": (finisher.JOB + "-new12", EXECUTION_UID),
    }
    (tmp_path / "manifest-identity.json").write_bytes(payload)
    with pytest.raises(
        finisher.DiscoveryMatrixFinisherError,
        match="recovery is forbidden before a launch intent is consumed",
    ):
        controller._launch_or_recover(
            phase="task0", prior={},
            payload_path=tmp_path / "manifest-identity.json",
        )
    assert identity["uri"] == "gs://fixture/manifest.json"
    assert runner.calls == []


def test_attribution_survives_provider_status_drift_before_launch_receipt(
    tmp_path: Path,
) -> None:
    identity, payload = _payload()
    name = finisher.JOB + "-new12"
    provider = _execution(
        mode="task0", payload=payload, name=name,
        completed="True", succeeded=1,
    )
    job = {
        "metadata": {"name": finisher.JOB, "uid": finisher.JOB_UID},
        "status": {"latestCreatedExecution": {"name": name}},
    }

    def callback(argv):
        if argv[:4] == ("gcloud", "run", "jobs", "describe"):
            return finisher.CommandResult(0, json.dumps(job).encode())
        if argv[:5] == ("gcloud", "run", "jobs", "executions", "describe"):
            return finisher.CommandResult(0, json.dumps(provider).encode())
        raise AssertionError(f"wrapper mutation unexpectedly invoked: {argv}")

    controller = _controller(tmp_path, _Runner(callback))
    (tmp_path / "manifest-identity.json").write_bytes(payload)
    phase = tmp_path / "phases/task0"
    phase.mkdir(parents=True)
    request = {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-host-phase-request/v1",
        "run_id": RUN_ID, "phase": "task0", "code_sha": CODE_SHA,
        "cloud_build_id": BUILD_ID, "provider_resolved_image": IMAGE,
        "payload_identity": identity,
        "payload_file_sha256": sha256(payload).hexdigest(),
        "payload_file_bytes": len(payload), "task_count": 1,
        "bound_task0_execution": "none", "outcomes_allowed": False,
        "complete": True,
    }
    before = {
        "name": finisher.JOB + "-old12",
        "uid": "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
        "provider_sha256": "5" * 64,
    }
    intent = {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-host-launch-intent/v1",
        "run_id": RUN_ID, "phase": "task0",
        "request_sha256": finisher.canonical_sha256(request),
        "provider_latest_before": {"name": before["name"], "uid": before["uid"]},
        "automatic_relaunch": False,
        "ambiguous_return_recovery": "exact-provider-latest-name-uid-envelope-only",
        "complete": True,
    }
    attribution = {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-host-provider-attribution/v1",
        "run_id": RUN_ID, "phase": "task0",
        "execution": {"name": name, "uid": EXECUTION_UID},
        "request_sha256": finisher.canonical_sha256(request),
        "intent_sha256": finisher.canonical_sha256(intent),
        "method": "provider-latest-after-ambiguous-wrapper-return",
        # This is the earlier nonterminal observation, deliberately different
        # from the now-terminal provider body returned above.
        "provider_sha256": "6" * 64,
        "automatic_relaunch": False, "complete": True,
    }
    (phase / "request.json").write_bytes(finisher.canonical_bytes(request))
    (phase / "provider-before.json").write_bytes(finisher.canonical_bytes(before))
    (phase / "launch-intent.json").write_bytes(finisher.canonical_bytes(intent))
    (phase / "provider-attribution.json").write_bytes(
        finisher.canonical_bytes(attribution)
    )

    launch = controller._launch_or_recover(
        phase="task0", prior={},
        payload_path=tmp_path / "manifest-identity.json",
    )
    assert launch["execution"] == {  # type: ignore[index]
        "name": name, "uid": EXECUTION_UID, "task_count": 1,
    }
    assert launch["provider_sha256_at_attribution"] == "6" * 64


def test_consumed_collect_intent_only_reconciles_known_terminal(tmp_path: Path) -> None:
    identity, payload = _payload()
    terminal_identity = _identity(
        f"{freeze.OUTPUT_PREFIX}/{RUN_ID}/terminal.json", b"terminal", "8"
    )
    result = {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-collect-result/v1",
        "terminal_identity": terminal_identity, "terminal_sha256": "6" * 64,
        "task_count": freeze.TASK_COUNT, "root_published_last": True,
        "publication_performed": False, "ambiguous_return_reconciled": True,
        "complete": True,
    }

    def callback(argv):
        assert argv[1] == "reconcile-collect"
        return finisher.CommandResult(0, finisher.canonical_bytes(result))

    runner = _Runner(callback)
    controller = _controller(tmp_path, runner)
    (tmp_path / "manifest-identity.json").write_bytes(payload)
    directory = tmp_path / "collect"
    directory.mkdir()
    execution = {
        "execution_name": finisher.JOB + "-abc12",
        "execution_uid": EXECUTION_UID,
    }
    request = {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-host-collect-request/v1",
        "run_id": RUN_ID, "phase": "collect",
        "execution": {"name": execution["execution_name"], "uid": EXECUTION_UID},
        "payload_identity": identity, "payload_file_sha256": sha256(payload).hexdigest(),
        "target_uri": f"{freeze.OUTPUT_PREFIX}/{RUN_ID}/terminal.json",
        "automatic_republication": False, "complete": True,
    }
    (directory / "request.json").write_bytes(finisher.canonical_bytes(request))
    intent = {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-host-collect-intent/v1",
        "run_id": RUN_ID, "phase": "collect",
        "request_sha256": finisher.canonical_sha256(request),
        "target_uri": request["target_uri"], "automatic_republication": False,
        "ambiguous_return_recovery": "exact-known-uri-read-only",
        "complete": True,
    }
    (directory / "intent.json").write_bytes(finisher.canonical_bytes(intent))

    assert controller._collect(reopen=False, execution=execution) == result
    assert [call[1] for call in runner.calls] == ["reconcile-collect"]


def test_chain_seal_retains_original_terminal_as_downstream_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    runner = _Runner(lambda argv: (_ for _ in ()).throw(AssertionError(argv)))
    controller = _controller(tmp_path, runner)
    request = _prepare_request()
    manifest = _identity(
        f"{freeze.OUTPUT_PREFIX}/{RUN_ID}/manifest.json", b"manifest", "7"
    )
    prepare = {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-prepare-result/v1",
        "manifest_identity": manifest, "manifest_sha256": "4" * 64,
        "task_count": freeze.TASK_COUNT, "publication_performed": True,
        "ambiguous_return_reconciled": False, "uses_realized_outcomes": False,
        "complete": True,
    }
    (tmp_path / "prepare").mkdir()
    (tmp_path / "prepare/request.json").write_bytes(finisher.canonical_bytes(request))
    (tmp_path / "prepare/result.json").write_bytes(finisher.canonical_bytes(prepare))
    (tmp_path / "manifest-identity.json").write_bytes(finisher.canonical_bytes(manifest))
    original = _identity(
        f"{freeze.OUTPUT_PREFIX}/{RUN_ID}/terminal.json", b"original", "8"
    )
    reopened = _identity(
        f"{freeze.OUTPUT_PREFIX}/{RUN_ID}/reopen-terminal.json", b"reopen", "9"
    )
    phase_index = {"task0": 0, "task": 1, "reopen-task": 2}

    def fake_phase(phase, prior):
        index = phase_index[phase]
        return {
            "execution_name": finisher.JOB + f"-p{index:04d}",
            "execution_uid": f"{index + 1:08d}-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            "provider_terminal_sha256": "5" * 64,
        }

    def fake_collect(*, reopen, execution):
        identity = reopened if reopen else original
        path = tmp_path / (
            "reopen-terminal-identity.json" if reopen else "terminal-identity.json"
        )
        path.write_bytes(finisher.canonical_bytes(identity))
        if reopen:
            return {"reopen_terminal_identity": identity}
        return {"terminal_identity": identity}

    monkeypatch.setattr(finisher, "validate_exact_repository", lambda **kwargs: None)
    monkeypatch.setattr(finisher, "verify_launcher_registry_lane", lambda **kwargs: None)
    monkeypatch.setattr(controller, "prepare", lambda: prepare)
    monkeypatch.setattr(controller, "_install", lambda: {"complete": True})
    monkeypatch.setattr(controller, "_phase", fake_phase)
    monkeypatch.setattr(controller, "_collect", fake_collect)
    monkeypatch.setattr(controller, "_validate_chain_terminal", lambda value: value)
    terminal = controller.chain()
    assert terminal["discovery_matrix_freeze_terminal_identity"] == original
    assert terminal["independent_reopen_terminal_identity"] == reopened
    assert terminal["downstream_consumes_original_terminal_identity"] is True
    assert terminal["independent_reopen_required_before_downstream"] is True
