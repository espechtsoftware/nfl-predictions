from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest

from nfl_dfs.research import (
    corpus_extreme_tail_panel_platform_replacement_terminal_v1 as closure,
)
from nfl_dfs.research import corpus_extreme_tail_panel_platform_replacement_v1 as replacement
from nfl_dfs.research import corpus_extreme_tail_panel_transport as transport
from nfl_dfs.research import corpus_parametric_batch as batch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import run_corpus_extreme_tail_panel_platform_replacement_terminal_v1 as controller


def _json_raw(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _task_spec(
    *, args: list[str], configured_environment: dict[str, str]
) -> dict[str, object]:
    return {
        "containers": [
            {
                "image": replacement.FROZEN_D2_URI,
                "command": ["bash"],
                "args": args,
                "env": [
                    {"name": key, "value": value}
                    for key, value in sorted(configured_environment.items())
                ],
                "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
                "volumeMounts": [
                    {
                        "name": "foundry-t230-runtime-evidence",
                        "mountPath": "/etc/nfl-dfs",
                    }
                ],
            }
        ],
        "maxRetries": 0,
        "serviceAccountName": replacement.SERVICE_ACCOUNT,
        "timeoutSeconds": "21600",
        "volumes": [
            {
                "name": "foundry-t230-runtime-evidence",
                "emptyDir": {"medium": "Memory", "sizeLimit": "1Mi"},
            }
        ],
    }


def _submitted_projection() -> dict[str, object]:
    environment = {
        "CLOUD_RUN_EXECUTION": closure.REPLACEMENT_EXECUTION,
        "T230_SOURCE_ORDINAL": "6",
    }
    args = ["-ceu", "frozen replacement payload"]
    return {
        "schema_version": (
            "foundry-t230-ordinal-6-replacement-submitted-execution-projection/v1"
        ),
        "execution_name": closure.REPLACEMENT_EXECUTION,
        "job": replacement.REUSE_JOB,
        "image": replacement.FROZEN_D2_URI,
        "service_account": replacement.SERVICE_ACCOUNT,
        "cpu": "8",
        "memory": "32Gi",
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "task_timeout_seconds": transport.TASK_TIMEOUT_SECONDS,
        "command": ["bash"],
        "args": args,
        "configured_environment": environment,
        "runtime_evidence_volume": {
            "type": "in-memory",
            "name": "foundry-t230-runtime-evidence",
            "size_limit": "1Mi",
            "mount_path": "/etc/nfl-dfs",
        },
        "full_execution_envelope_exactly_validated": True,
        "worker_launch_plan_sha256": "a" * 64,
        "execution_flags_sha256": "b" * 64,
        "describe_argv": ["gcloud", "fixture"],
        "describe_stdout_sha256": "c" * 64,
        "describe_stdout_bytes": 100,
    }


def _ownership() -> dict[str, object]:
    return {"submitted_execution_projection": _submitted_projection()}


def _execution_body() -> dict[str, object]:
    submitted = _submitted_projection()
    return {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Execution",
        "metadata": {
            "name": closure.REPLACEMENT_EXECUTION,
            "labels": {"run.googleapis.com/job": replacement.REUSE_JOB},
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {
                "spec": _task_spec(
                    args=deepcopy(submitted["args"]),
                    configured_environment=deepcopy(
                        submitted["configured_environment"]
                    ),
                )
            },
        },
        "status": {
            "completionTime": closure.REPLACEMENT_COMPLETION_TIME,
            "conditions": deepcopy(closure.EXECUTION_CONDITIONS),
            "failedCount": 1,
            "observedGeneration": 1,
            "startTime": closure.REPLACEMENT_STARTED_TIME,
            "logUri": "https://console.cloud.google.com/run/jobs/executions/details/test",
        },
    }


def _task_body() -> dict[str, object]:
    return {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Task",
        "metadata": {
            "annotations": {
                "run.googleapis.com/scheduled-time": closure.REPLACEMENT_STARTED_TIME
            },
            "creationTimestamp": closure.TASK_CREATION_TIME,
            "generation": 1,
            "labels": {
                "cloud.googleapis.com/location": transport.REGION,
                "run.googleapis.com/execution": closure.REPLACEMENT_EXECUTION,
                "run.googleapis.com/job": replacement.REUSE_JOB,
                "run.googleapis.com/runningState": "Failed",
            },
            "name": closure.REPLACEMENT_TASK,
            "namespace": "817589974517",
            "resourceVersion": "AAZZ7FoYxOc",
            "selfLink": (
                "/apis/run.googleapis.com/v1/namespaces/817589974517/tasks/"
                "atlas-minimal-c-s2023-w1-v1-67669-task0"
            ),
        },
        "spec": {},
        "status": {
            "completionTime": closure.TASK_COMPLETION_TIME,
            "conditions": [
                {
                    "message": closure.TASK_MESSAGE,
                    "reason": closure.TASK_REASON,
                    "status": "False",
                    "type": "Completed",
                },
                {"status": "True", "type": "Started"},
            ],
            "lastAttemptResult": {
                "exitCode": 1,
                "status": {"code": 10, "message": closure.TASK_MESSAGE},
            },
            "observedGeneration": 1,
            "startTime": closure.TASK_START_TIME,
        },
    }


def _install_describes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    execution: object | None = None,
    tasks: object | None = None,
) -> list[list[str]]:
    responses = iter(
        [
            _json_raw(_execution_body() if execution is None else execution),
            _json_raw([_task_body()] if tasks is None else tasks),
        ]
    )
    calls: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        calls.append(list(argv))
        return subprocess.CompletedProcess(
            args=list(argv), returncode=0, stdout=next(responses), stderr=b""
        )

    monkeypatch.setattr(controller.subprocess, "run", fake_run)
    return calls


def test_terminal_observer_accepts_exact_failed_task_and_makes_two_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_describes(monkeypatch)
    value = controller.TerminalCloudObserver().observe(ownership=_ownership())
    assert closure.validate_replacement_failure_projection_v1(value) == value
    assert value["completed_message"] == closure.EXECUTION_COMPLETED_MESSAGE
    assert value["task_last_attempt_result"]["exitCode"] == 1
    assert value["log_content_read"] is False
    assert calls == [
        list(closure.EXECUTION_DESCRIBE_ARGV),
        list(closure.TASK_DESCRIBE_ARGV),
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        "zero-tasks",
        "two-tasks",
        "task-extra-key",
        "task-name",
        "task-condition-message",
        "task-exit-code",
        "task-status-extra-key",
        "execution-condition",
        "execution-status-extra-key",
        "succeeded-count-present",
        "cancelled-count-present",
        "execution-envelope",
    ],
)
def test_terminal_observer_rejects_task_terminal_and_envelope_drift(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    execution = _execution_body()
    task = _task_body()
    tasks: list[dict[str, object]] = [task]
    if mutation == "zero-tasks":
        tasks = []
    elif mutation == "two-tasks":
        tasks.append(deepcopy(task))
    elif mutation == "task-extra-key":
        task["unexpected"] = False
    elif mutation == "task-name":
        task["metadata"]["name"] = closure.REPLACEMENT_TASK + "-near-miss"
    elif mutation == "task-condition-message":
        task["status"]["conditions"][0]["message"] = "near miss"
    elif mutation == "task-exit-code":
        task["status"]["lastAttemptResult"]["exitCode"] = 0
    elif mutation == "task-status-extra-key":
        task["status"]["retried"] = 0
    elif mutation == "execution-condition":
        execution["status"]["conditions"][0]["message"] = "near miss"
    elif mutation == "execution-status-extra-key":
        execution["status"]["runningCount"] = 0
    elif mutation == "succeeded-count-present":
        execution["status"]["succeededCount"] = 0
    elif mutation == "cancelled-count-present":
        execution["status"]["cancelledCount"] = 0
    elif mutation == "execution-envelope":
        execution["spec"]["template"]["spec"]["containers"][0]["image"] = (
            "mutable:latest"
        )
    _install_describes(monkeypatch, execution=execution, tasks=tasks)
    with pytest.raises(controller.T230TerminalClosureControllerError):
        controller.TerminalCloudObserver().observe(ownership=_ownership())


class MetadataOnlyBackend:
    def __init__(self) -> None:
        self.probed: list[str] = []
        self.read_calls: list[str] = []
        self.objects: dict[str, tuple[dict[str, object], bytes]] = {}
        self.generation = 100

    def probe_known_uri_metadata(self, uri: str):
        self.probed.append(uri)
        return None

    def read(self, identity):
        self.read_calls.append(str(identity["uri"]))
        return self.objects[str(identity["uri"])][1]

    def read_known_uri(self, uri: str):
        if uri not in self.objects:
            raise FileNotFoundError(uri)
        identity, raw = self.objects[uri]
        return dict(identity), raw

    def create(self, uri: str, raw: bytes):
        if uri in self.objects:
            raise transport.JournalObjectExists(uri)
        self.generation += 1
        identity = {
            "uri": uri,
            "generation": str(self.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[uri] = (identity, raw)
        return dict(identity)


def _lineage() -> dict[str, object]:
    semantic = {
        key: value
        for key, value in _submitted_projection().items()
        if key
        not in {
            "schema_version",
            "full_execution_envelope_exactly_validated",
            "worker_launch_plan_sha256",
            "execution_flags_sha256",
            "describe_argv",
            "describe_stdout_sha256",
            "describe_stdout_bytes",
        }
    }
    return {
        "replacement_intent_identity": dict(closure.REPLACEMENT_INTENT_IDENTITY),
        "platform_replacement_intent_sha256": "d" * 64,
        "replacement_launch_ownership_identity": dict(
            closure.REPLACEMENT_OWNERSHIP_IDENTITY
        ),
        "launch_ownership_sha256": "e" * 64,
        "replacement_stage_start_identity": dict(
            closure.REPLACEMENT_STAGE_START_IDENTITY
        ),
        "replacement_stage_start_sha256": "f" * 64,
        "replacement_execution": closure.REPLACEMENT_EXECUTION,
        "replacement_submitted_execution_semantic_sha256": (
            batch.canonical_sha256(semantic)
        ),
        "lineage_exactly_replayed": True,
        "result_or_effect_content_inspected": False,
        "realized_outcomes_read": False,
    }


def _preflight_marker() -> dict[str, object]:
    return closure.build_preflight_attempt_marker_v1(
        implementation_source_commit_sha="a" * 40,
        reviewed_implementation_measurements=(
            closure.terminal_closure_implementation_measurements_v1()
        ),
    )


def _preflight_marker_measurement() -> dict[str, object]:
    raw = batch.canonical_json_bytes(_preflight_marker()) + b"\n"
    return {
        "relative_path": closure.PREFLIGHT_ATTEMPT_RELATIVE_PATH,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def test_preflight_uses_metadata_only_for_every_effect_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = MetadataOnlyBackend()
    terminal = controller.TerminalCloudObserver.__new__(
        controller.TerminalCloudObserver
    )
    monkeypatch.setattr(
        closure, "reopen_replacement_launch_lineage_v1", lambda **_kwargs: _lineage()
    )
    monkeypatch.setattr(
        closure,
        "_exact_read_json",
        lambda *_args, **_kwargs: (
            dict(closure.REPLACEMENT_OWNERSHIP_IDENTITY),
            _ownership(),
            b"fixture",
        ),
    )
    monkeypatch.setattr(terminal, "observe", lambda **_kwargs: _terminal_projection())
    value = controller.build_real_artifact_preflight_v1(
        backend=backend,
        observer=terminal,
        preflight_attempt_marker_measurement=_preflight_marker_measurement(),
        preflight_attempt_marker=_preflight_marker(),
    )
    assert value["preflight_passed"] is True
    assert value["result_body_read"] is False
    assert value["acceptance_body_read"] is False
    assert backend.read_calls == []
    assert backend.probed == closure.terminal_surface_uris_v1() * 2


def test_lane_a_boundary_census_is_full_and_metadata_only() -> None:
    backend = MetadataOnlyBackend()
    uris = closure.lane_a_terminal_surface_uris_v1()
    rows = controller._surface_rows_for_uris(backend, uris)
    value = closure.build_lane_a_surface_census_v1(
        rows=rows, pass_ordinal=1
    )
    assert value["all_post_terminal_effect_and_incomplete_surfaces_absent"] is True
    assert backend.probed == uris
    assert backend.read_calls == []


def _terminal_projection() -> dict[str, object]:
    submitted = _submitted_projection()
    semantic = {
        key: value
        for key, value in submitted.items()
        if key
        not in {
            "schema_version",
            "full_execution_envelope_exactly_validated",
            "worker_launch_plan_sha256",
            "execution_flags_sha256",
            "describe_argv",
            "describe_stdout_sha256",
            "describe_stdout_bytes",
        }
    }
    return {
        "schema_version": closure.TERMINAL_PROJECTION_SCHEMA,
        "execution_name": closure.REPLACEMENT_EXECUTION,
        "task_name": closure.REPLACEMENT_TASK,
        "job": replacement.REUSE_JOB,
        "completed_status": "False",
        "completed_reason": closure.TASK_REASON,
        "completed_message": closure.EXECUTION_COMPLETED_MESSAGE,
        "execution_status_keys": [
            "completionTime",
            "conditions",
            "failedCount",
            "logUri",
            "observedGeneration",
            "startTime",
        ],
        "execution_conditions": deepcopy(closure.EXECUTION_CONDITIONS),
        "start_time": closure.REPLACEMENT_STARTED_TIME,
        "completion_time": closure.REPLACEMENT_COMPLETION_TIME,
        "failed_count": 1,
        "succeeded_count_present": False,
        "succeeded_count": 0,
        "cancelled_count_present": False,
        "cancelled_count": 0,
        "execution_observed_generation": 1,
        "log_uri": "https://console.cloud.google.com/run/test",
        "log_content_read": False,
        "task_api_version": "run.googleapis.com/v1",
        "task_kind": "Task",
        "task_namespace": "817589974517",
        "task_resource_version": "AAZZ7FoYxOc",
        "task_self_link": (
            "/apis/run.googleapis.com/v1/namespaces/817589974517/tasks/"
            "atlas-minimal-c-s2023-w1-v1-67669-task0"
        ),
        "task_creation_time": closure.TASK_CREATION_TIME,
        "task_scheduled_time": closure.REPLACEMENT_STARTED_TIME,
        "task_start_time": closure.TASK_START_TIME,
        "task_completion_time": closure.TASK_COMPLETION_TIME,
        "task_running_state": "Failed",
        "task_spec": {},
        "task_completed_condition": {
            "message": closure.TASK_MESSAGE,
            "reason": closure.TASK_REASON,
            "status": "False",
            "type": "Completed",
        },
        "task_started_condition": {"status": "True", "type": "Started"},
        "task_last_attempt_result": {
            "exitCode": 1,
            "status": {"code": 10, "message": closure.TASK_MESSAGE},
        },
        "task_observed_generation": 1,
        "execution_envelope": semantic,
        "execution_describe_argv": list(closure.EXECUTION_DESCRIBE_ARGV),
        "execution_describe_stdout_sha256": "1" * 64,
        "execution_describe_stdout_bytes": 1,
        "task_describe_argv": list(closure.TASK_DESCRIBE_ARGV),
        "task_describe_stdout_sha256": "2" * 64,
        "task_describe_stdout_bytes": 1,
        "terminal_exactly_validated": True,
        "result_or_effect_content_inspected": False,
        "realized_outcomes_read": False,
    }


def test_create_once_equal_is_resolve_only_and_unequal_is_terminal() -> None:
    backend = MetadataOnlyBackend()
    value = {"schema_version": "fixture/v1", "terminal": True}
    first, created = controller._create_once_or_equal(
        backend, uri="gs://bucket/closure.json", value=value
    )
    second, created_again = controller._create_once_or_equal(
        backend, uri="gs://bucket/closure.json", value=value
    )
    assert created is True
    assert created_again is False
    assert second == first
    with pytest.raises(controller.T230TerminalClosureControllerError):
        controller._create_once_or_equal(
            backend,
            uri="gs://bucket/closure.json",
            value={"schema_version": "fixture/v1", "terminal": False},
        )


def test_public_cli_gate_precedes_backend_or_cloud_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(controller.ENABLE_ENV, raising=False)
    monkeypatch.setattr(
        controller,
        "_backend",
        lambda: (_ for _ in ()).throw(AssertionError("backend must stay unopened")),
    )
    with pytest.raises(controller.T230TerminalClosureControllerError):
        controller.main(["preflight", "--preflight"])


def test_controller_has_no_cloud_run_submit_or_result_body_reader() -> None:
    source = (
        ROOT
        / "scripts/run_corpus_extreme_tail_panel_platform_replacement_terminal_v1.py"
    ).read_text(encoding="utf-8")
    assert "gcloud run jobs execute" not in source
    assert "def submit(" not in source
    assert "download_as_bytes" not in source
    assert "bucket.list_blobs" not in source
    assert "gcloud storage ls" not in source
    assert "publish-lane-a-closure" in source
    assert "cloud_run_submission_count\": 0" in source


def test_fixed_preflight_path_rejects_existing_or_symlink(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(transport, "REPOSITORY_ROOT", tmp_path)
    target = reports / Path(closure.PREFLIGHT_RELATIVE_PATH).name
    assert controller._fixed_local_path(
        closure.PREFLIGHT_RELATIVE_PATH, must_be_absent=True
    ) == target
    target.write_text("occupied", encoding="utf-8")
    with pytest.raises(controller.T230TerminalClosureControllerError):
        controller._fixed_local_path(
            closure.PREFLIGHT_RELATIVE_PATH, must_be_absent=True
        )
    target.unlink()
    target.symlink_to(tmp_path / "missing-target")
    with pytest.raises(controller.T230TerminalClosureControllerError):
        controller._fixed_local_path(
            closure.PREFLIGHT_RELATIVE_PATH, must_be_absent=True
        )


def test_preflight_collision_fails_before_backend_or_cloud_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    receipt = reports / Path(closure.PREFLIGHT_RELATIVE_PATH).name
    receipt.write_text("occupied", encoding="utf-8")
    monkeypatch.setattr(transport, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setenv(controller.ENABLE_ENV, "1")
    backend_calls = 0

    def forbidden_backend():
        nonlocal backend_calls
        backend_calls += 1
        raise AssertionError("backend construction must not occur")

    monkeypatch.setattr(controller, "_backend", forbidden_backend)
    with pytest.raises(controller.T230TerminalClosureControllerError):
        controller.main(["preflight", "--preflight"])
    assert backend_calls == 0


def _install_preflight_marker_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    reports = tmp_path / "reports"
    reports.mkdir(exist_ok=True)
    monkeypatch.setattr(transport, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setenv(controller.ENABLE_ENV, "1")
    monkeypatch.setenv(closure.IMPLEMENTATION_COMMIT_ENV, "a" * 40)
    measurements = [
        {
            "relative_path": path,
            "sha256": marker * 64,
            "bytes": 1,
        }
        for path, marker in zip(
            (
                closure.IMPLEMENTATION_RELATIVE_PATH,
                closure.TEST_RELATIVE_PATH,
                closure.CONTROLLER_RELATIVE_PATH,
                closure.CONTROLLER_TEST_RELATIVE_PATH,
            ),
            ("1", "2", "3", "4"),
            strict=True,
        )
    ]
    monkeypatch.setattr(
        closure,
        "terminal_closure_implementation_measurements_v1",
        lambda: measurements,
    )
    monkeypatch.setattr(
        closure,
        "verify_terminal_closure_implementation_commit_v1",
        lambda **_kwargs: "a" * 40,
    )
    return reports / Path(closure.PREFLIGHT_ATTEMPT_RELATIVE_PATH).name


def test_preflight_backend_crash_consumes_marker_and_second_attempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker_path = _install_preflight_marker_fixture(monkeypatch, tmp_path)
    backend_calls = 0

    def crashing_backend():
        nonlocal backend_calls
        backend_calls += 1
        raise RuntimeError("simulated backend-construction crash")

    monkeypatch.setattr(controller, "_backend", crashing_backend)
    with pytest.raises(RuntimeError, match="simulated"):
        controller.main(["preflight", "--preflight"])
    assert backend_calls == 1
    marker = closure.validate_preflight_attempt_marker_v1(
        controller._load_local_canonical(
            marker_path, label="preflight-attempt marker"
        )
    )
    assert marker["attempt_consumed_even_if_read_or_process_fails"] is True
    with pytest.raises(controller.T230TerminalClosureControllerError):
        controller.main(["preflight", "--preflight"])
    assert backend_calls == 1


def test_preflight_read_failure_leaves_consumed_marker_without_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker_path = _install_preflight_marker_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(controller, "_backend", lambda: MetadataOnlyBackend())
    monkeypatch.setattr(
        controller,
        "build_real_artifact_preflight_v1",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("read failed")),
    )
    with pytest.raises(RuntimeError, match="read failed"):
        controller.main(["preflight", "--preflight"])
    assert marker_path.is_file()
    assert not (
        tmp_path / "reports" / Path(closure.PREFLIGHT_RELATIVE_PATH).name
    ).exists()


def test_preflight_dangling_marker_symlink_fails_before_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker_path = _install_preflight_marker_fixture(monkeypatch, tmp_path)
    marker_path.symlink_to(tmp_path / "missing-target")
    backend_calls = 0

    def forbidden_backend():
        nonlocal backend_calls
        backend_calls += 1
        raise AssertionError("backend construction must not occur")

    monkeypatch.setattr(controller, "_backend", forbidden_backend)
    with pytest.raises(controller.T230TerminalClosureControllerError):
        controller.main(["preflight", "--preflight"])
    assert backend_calls == 0
    assert not (tmp_path / "missing-target").exists()


def test_review_lock_cli_is_fixed_path_deterministic_and_cloud_free(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(transport, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setenv(controller.ENABLE_ENV, "1")
    expected = {
        "schema_version": closure.REVIEW_LOCK_SCHEMA,
        "terminal_closure_review_lock_sha256": "a" * 64,
    }
    builder_calls = 0
    backend_calls = 0

    def build():
        nonlocal builder_calls
        builder_calls += 1
        return expected

    def forbidden_backend():
        nonlocal backend_calls
        backend_calls += 1
        raise AssertionError("review-lock builder must not construct backend")

    monkeypatch.setattr(controller, "build_review_lock_v1", build)
    monkeypatch.setattr(controller, "_backend", forbidden_backend)
    assert controller.main(["build-review-lock", "--execute"]) == 0
    lock_path = reports / Path(closure.REVIEW_LOCK_RELATIVE_PATH).name
    assert lock_path.read_bytes() == batch.canonical_json_bytes(expected) + b"\n"
    assert builder_calls == 1
    assert backend_calls == 0
    with pytest.raises(controller.T230TerminalClosureControllerError):
        controller.main(["build-review-lock", "--execute"])
    assert builder_calls == 1


@pytest.mark.parametrize(
    ("text", "accepted"),
    [
        ("...\n12 passed in 1.23s\n", 12),
        ("." * 51 + " " * 22 + "[100%]\n", 51),
        (
            "." * 72
            + " [ 79%]\n"
            + "." * 19
            + " " * 54
            + "[100%]\n",
            91,
        ),
        ("...\n11 passed, 1 skipped in 1.23s\n", None),
        ("...\n1 failed, 11 passed in 1.23s\n", None),
        ("F [100%]\n", None),
        (". [100%]\nextra\n", None),
        (". [100%]", None),
        (". [99%]\n", None),
        (".\t[100%]\n", None),
        (".[100%]\n", None),
        (" [100%]\n", None),
        (". [ 79%]\n. [ 79%]\n. [100%]\n", None),
        (". [ 79%]\n. [ 50%]\n. [100%]\n", None),
        (". [100%]\n. [100%]\n", None),
        (". [ 79%]\n. [ 99%]\n", None),
        (". [ 01%]\n. [100%]\n", None),
    ],
)
def test_review_lock_builder_derives_clean_pass_count_from_output(
    tmp_path: Path, text: str, accepted: int | None
) -> None:
    output = tmp_path / "focused.txt"
    output.write_text(text, encoding="utf-8")
    if accepted is None:
        with pytest.raises(controller.T230TerminalClosureControllerError):
            controller._focused_test_pass_count(output)
    else:
        assert controller._focused_test_pass_count(output) == accepted
