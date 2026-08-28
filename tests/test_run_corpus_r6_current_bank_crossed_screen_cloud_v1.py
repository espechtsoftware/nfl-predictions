"""Offline tests for the thin current-bank Cloud Run operator."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace
from typing import Mapping, Sequence
import inspect

import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_projection_preparation_v1 as preparation,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_layer_preparation_v1 as layer_preparation,
)
from scripts import run_corpus_r6_current_bank_crossed_screen_cloud_v1 as cloud


JOB = "r6-current-bank"
JOB_UID = "job-uid-123"
EXECUTION = f"{JOB}-abc12"
COMMIT = "a" * 40
DIGEST = "sha256:" + "b" * 64
IMAGE = f"us-central1-docker.pkg.dev/{cloud.PROJECT}/nfl-dfs/nfl-dfs@{DIGEST}"
OUTPUT_PREFIX = contract.OUTPUT_NAMESPACE + "operator-fixture/"
MANIFEST_IDENTITY = {
    "uri": OUTPUT_PREFIX + "authorities/task-manifests/00-projection.json",
    "generation": "7",
    "sha256": "c" * 64,
    "bytes": 10_000,
}


def _manifest(task_count: int = 2) -> dict[str, object]:
    return {
        "task_manifest_sha256": "d" * 64,
        "layer_ordinal": 0,
        "layer_id": "projection",
        "output_prefix": OUTPUT_PREFIX,
        "code_commit": COMMIT,
        "image_digest": DIGEST,
        "reused_job_name": JOB,
        "task_count": task_count,
        "task_bindings": [
            {
                "task_terminal_evidence_uri": (
                    OUTPUT_PREFIX
                    + f"authorities/task-terminal-evidence/projection/{index:03d}.json"
                )
            }
            for index in range(task_count)
        ],
    }


def _manifest_opener(manifest: Mapping[str, object]):
    def open_manifest(
        identity: Mapping[str, object], *, read_exact: object,
    ) -> Mapping[str, object]:
        del read_exact
        assert dict(identity) == MANIFEST_IDENTITY
        return {
            "manifest": dict(manifest),
            "manifest_identity": dict(MANIFEST_IDENTITY),
        }

    return open_manifest


@pytest.fixture(autouse=True)
def _synthetic_manifest_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cloud.task_manifest,
        "validate_task_manifest_v1",
        lambda value: dict(value),
    )


def _common_environment(manifest: Mapping[str, object]) -> dict[str, str]:
    return cloud.common_job_environment_v1(
        manifest=manifest, manifest_identity=MANIFEST_IDENTITY
    )


def _configured_environment(manifest: Mapping[str, object]) -> dict[str, str]:
    return cloud.configured_job_environment_v1(
        manifest=manifest, manifest_identity=MANIFEST_IDENTITY
    )


def _task_template(manifest: Mapping[str, object]) -> dict[str, object]:
    environment = _configured_environment(manifest)
    return {
        "containers": [
            {
                "image": IMAGE,
                "command": [cloud.DISPATCHER_PYTHON],
                "args": ["-I", cloud.DISPATCHER_SCRIPT],
                "env": [
                    {"name": key, "value": value}
                    for key, value in sorted(environment.items())
                ],
                "resources": {
                    "limits": {"cpu": cloud.CPU, "memory": cloud.MEMORY}
                },
                "workingDir": "",
                "volumeMounts": [],
            }
        ],
        "maxRetries": 0,
        "timeoutSeconds": f"{cloud.TASK_TIMEOUT_SECONDS}s",
        "volumes": [],
    }


def _job_description(
    manifest: Mapping[str, object], *, uid: str = JOB_UID,
    latest: str | None = None, execution_count: int | None = None,
    latest_terminal: bool = True,
) -> dict[str, object]:
    status: dict[str, object] = {
        "executionCount": (
            execution_count
            if execution_count is not None
            else (1 if latest is not None else 0)
        )
    }
    if latest is not None:
        status["latestCreatedExecution"] = {
            "name": latest,
            "creationTimestamp": "2026-08-28T01:00:00Z",
            **(
                {
                    "completionTimestamp": "2026-08-28T01:02:03Z",
                    "completionStatus": "EXECUTION_SUCCEEDED",
                }
                if latest_terminal else {}
            ),
        }
    return {
        "metadata": {
            "name": f"projects/{cloud.PROJECT}/locations/{cloud.REGION}/jobs/{JOB}",
            "uid": uid,
            "generation": "9",
            "annotations": {},
        },
        "spec": {
            "template": {
                "spec": {
                    "taskCount": manifest["task_count"],
                    "parallelism": manifest["task_count"],
                    "template": {"spec": _task_template(manifest)},
                }
            }
        },
        "status": status,
    }


def _execution_description(
    manifest: Mapping[str, object], *, terminal: bool = True,
) -> dict[str, object]:
    status = (
        {
            "completionTime": "2026-08-28T01:02:03Z",
            "succeededCount": manifest["task_count"],
            "failedCount": 0,
            "cancelledCount": 0,
            "conditions": [
                {"type": "Completed", "state": "CONDITION_SUCCEEDED"}
            ],
        }
        if terminal
        else {"conditions": []}
    )
    return {
        "metadata": {
            "name": (
                f"projects/{cloud.PROJECT}/locations/{cloud.REGION}/jobs/{JOB}/"
                f"executions/{EXECUTION}"
            ),
            "uid": "execution-uid-1",
            "generation": "3",
            "labels": {
                "run.googleapis.com/job": JOB,
                "run.googleapis.com/jobUid": JOB_UID,
            },
        },
        "spec": {
            "taskCount": manifest["task_count"],
            "parallelism": manifest["task_count"],
            "template": {"spec": _task_template(manifest)},
        },
        "status": status,
    }


def _task_description(index: int, *, terminal: bool = True) -> dict[str, object]:
    status = (
        {
            "completionTime": "2026-08-28T01:02:03Z",
            "conditions": [
                {"type": "Completed", "state": "CONDITION_SUCCEEDED"}
            ],
        }
        if terminal
        else {"conditions": []}
    )
    return {
        "metadata": {
            "name": f"{EXECUTION}-task{index}",
            "labels": {
                "run.googleapis.com/execution": EXECUTION,
                "run.googleapis.com/runningState": (
                    "Succeeded" if terminal else "Running"
                ),
            },
        },
        "status": status,
    }


class ProviderRunner:
    def __init__(
        self, manifest: Mapping[str, object], *, latest: str | None = None,
        active_execution: bool = False, active_task_index: int | None = None,
        submission_fails: bool = False,
    ) -> None:
        self.manifest = manifest
        self.latest = latest
        self.active_execution = active_execution
        self.active_task_index = active_task_index
        self.submission_fails = submission_fails
        self.calls: list[list[str]] = []

    def __call__(self, argv: Sequence[str]) -> Mapping[str, object]:
        call = list(argv)
        self.calls.append(call)
        if call[0:4] == ["gcloud", "run", "jobs", "update"]:
            return {"returncode": 0, "stdout": b"{}\n", "stderr": b""}
        if call[0:4] == ["gcloud", "run", "jobs", "execute"]:
            return {
                "returncode": 1 if self.submission_fails else 0,
                "stdout": b"" if self.submission_fails else (EXECUTION + "\n").encode(),
                "stderr": b"submission uncertain" if self.submission_fails else b"",
            }
        if "tasks" in call:
            task_name = call[call.index("describe") + 1]
            index = int(task_name.rsplit("task", 1)[-1])
            value = _task_description(
                index, terminal=index != self.active_task_index
            )
        elif "executions" in call:
            value = _execution_description(
                self.manifest, terminal=not self.active_execution
            )
        else:
            value = _job_description(
                self.manifest,
                latest=self.latest,
                latest_terminal=not self.active_execution,
            )
        return {
            "returncode": 0,
            "stdout": cloud._canonical_bytes(value),
            "stderr": b"",
        }


class LaunchStateRunner:
    def __init__(
        self, manifest: Mapping[str, object], *, fail_after_accept: bool = False,
    ) -> None:
        self.manifest = manifest
        self.fail_after_accept = fail_after_accept
        self.execution_count = 0
        self.latest: str | None = None
        self.calls: list[list[str]] = []

    def __call__(self, argv: Sequence[str]) -> Mapping[str, object]:
        call = list(argv)
        self.calls.append(call)
        if call[0:4] == ["gcloud", "run", "jobs", "execute"]:
            self.execution_count = 1
            self.latest = EXECUTION
            return {
                "returncode": 1 if self.fail_after_accept else 0,
                "stdout": b"" if self.fail_after_accept else (EXECUTION + "\n").encode(),
                "stderr": b"submission uncertain" if self.fail_after_accept else b"",
            }
        if "executions" in call:
            value = _execution_description(self.manifest, terminal=False)
        else:
            value = _job_description(
                self.manifest,
                latest=self.latest,
                execution_count=self.execution_count,
                latest_terminal=False,
            )
        return {
            "returncode": 0,
            "stdout": cloud._canonical_bytes(value),
            "stderr": b"",
        }


class ExactStore:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, dict[str, object]]] = {}

    def publish(self, uri: str, raw: bytes) -> Mapping[str, object]:
        if uri in self.objects:
            raise RuntimeError("create-once collision")
        identity = {
            "uri": uri,
            "generation": str(len(self.objects) + 1),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[uri] = (raw, identity)
        return identity

    def read(self, identity: Mapping[str, object]) -> bytes:
        raw, retained = self.objects[str(identity["uri"])]
        assert dict(identity) == retained
        return raw


def test_configure_uses_exact_flags_file_and_validates_post_projection() -> None:
    manifest = _manifest()
    runner = ProviderRunner(manifest)
    written: list[tuple[str, dict[str, object]]] = []
    result = cloud.configure_layer_v1(
        manifest_identity=MANIFEST_IDENTITY,
        expected_job_uid=JOB_UID,
        image_uri=IMAGE,
        flags_path="/tmp/r6-configure-flags.json",
        read_exact=lambda _identity: b"",
        runner=runner,
        flags_writer=lambda path, value: written.append((path, dict(value))),
        manifest_opener=_manifest_opener(manifest),
    )
    assert result["job_created"] is False
    assert result["exact_post_update_projection_validated"] is True
    assert result["job_projection"]["environment"] == _common_environment(manifest)
    assert _configured_environment(manifest) == {
        key: value
        for key, value in _common_environment(manifest).items()
        if key != "CLOUD_RUN_JOB"
    }
    assert len(written) == 1
    path, flags = written[0]
    assert path == "/tmp/r6-configure-flags.json"
    assert set(flags) == {
        "--args", "--clear-cloudsql-instances", "--clear-network",
        "--clear-secrets", "--clear-volume-mounts", "--clear-volumes",
        "--clear-vpc-connector", "--command", "--cpu", "--image",
        "--max-retries", "--memory", "--parallelism", "--set-env-vars",
        "--task-timeout", "--tasks", "--workdir",
    }
    assert flags["--set-env-vars"].startswith("^|^")
    assert cloud._canonical_bytes(MANIFEST_IDENTITY).decode() in flags["--set-env-vars"]
    assert "CLOUD_RUN_JOB=" not in flags["--set-env-vars"]
    assert flags["--tasks"] == flags["--parallelism"] == 2
    assert flags["--max-retries"] == 0
    assert flags["--task-timeout"] == "7260s"
    update = runner.calls[1]
    assert update == cloud.configure_argv_v1(JOB, flags_path=path)
    joined = " ".join(token for call in runner.calls for token in call)
    assert " jobs create " not in f" {joined} "
    assert " jobs deploy " not in f" {joined} "


def test_wrong_uid_non_digest_and_active_execution_fail_before_mutation() -> None:
    manifest = _manifest()
    with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="name/UID"):
        cloud.validate_job_identity_v1(
            _job_description(manifest),
            manifest=manifest,
            expected_job_uid="wrong-uid",
        )
    with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="image"):
        cloud.configure_flags_v1(
            manifest=manifest,
            manifest_identity=MANIFEST_IDENTITY,
            image_uri="us-central1-docker.pkg.dev/repo/image:latest",
        )
    runner = ProviderRunner(
        manifest, latest=EXECUTION, active_execution=True
    )
    store = ExactStore()
    with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="active"):
        cloud.arm_launch_v1(
            manifest_identity=MANIFEST_IDENTITY,
            expected_job_uid=JOB_UID,
            image_uri=IMAGE,
            read_exact=store.read,
            publish_create_once=store.publish,
            runner=runner,
            manifest_opener=_manifest_opener(manifest),
        )
    assert store.objects == {}
    assert not any(call[0:4] == ["gcloud", "run", "jobs", "execute"] for call in runner.calls)


def test_ambiguous_submission_consumes_intent_and_forbids_blind_relaunch() -> None:
    manifest = _manifest()
    runner = ProviderRunner(manifest, submission_fails=True)
    store = ExactStore()
    kwargs = {
        "manifest_identity": MANIFEST_IDENTITY,
        "expected_job_uid": JOB_UID,
        "image_uri": IMAGE,
        "read_exact": store.read,
        "publish_create_once": store.publish,
        "runner": runner,
        "manifest_opener": _manifest_opener(manifest),
    }
    armed = cloud.arm_launch_v1(**kwargs)
    intent_identity = armed["launch_intent_identity"]
    assert armed["submission_call_count"] == 0
    with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="ambiguous"):
        cloud.launch_layer_v1(
            **kwargs, launch_intent_identity=intent_identity
        )
    assert list(store.objects) == [
        cloud.launch_intent_uri_v1(manifest),
        cloud.launch_submission_marker_uri_v1(manifest),
    ]
    with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="consumed"):
        cloud.launch_layer_v1(
            **kwargs, launch_intent_identity=intent_identity
        )
    submissions = [
        call for call in runner.calls
        if call[0:4] == ["gcloud", "run", "jobs", "execute"]
    ]
    assert len(submissions) == 1
    assert submissions[0] == cloud.execute_argv_v1(JOB)
    assert not any("--update-env-vars" in token for token in submissions[0])
    assert not any("--tasks" in token for token in submissions[0])


def test_arm_launch_fsync_boundary_and_successful_launch_are_two_phase() -> None:
    manifest = _manifest()
    runner = LaunchStateRunner(manifest)
    store = ExactStore()
    common = {
        "manifest_identity": MANIFEST_IDENTITY,
        "expected_job_uid": JOB_UID,
        "image_uri": IMAGE,
        "read_exact": store.read,
        "publish_create_once": store.publish,
        "runner": runner,
        "manifest_opener": _manifest_opener(manifest),
    }
    armed = cloud.arm_launch_v1(**common)
    assert armed["submission_call_count"] == 0
    assert not any(
        call[0:4] == ["gcloud", "run", "jobs", "execute"]
        for call in runner.calls
    )
    result = cloud.launch_layer_v1(
        **common, launch_intent_identity=armed["launch_intent_identity"]
    )
    assert result["recovered_without_resubmission"] is False
    assert result["launch_result"]["cloud_execution_name"] == EXECUTION
    assert result["launch_result"]["postlaunch_job_execution_count"] == 1
    assert list(store.objects) == [
        cloud.launch_intent_uri_v1(manifest),
        cloud.launch_submission_marker_uri_v1(manifest),
    ]
    submissions = [
        call for call in runner.calls
        if call[0:4] == ["gcloud", "run", "jobs", "execute"]
    ]
    assert submissions == [cloud.execute_argv_v1(JOB)]


def test_recover_launch_uses_preserved_intent_and_never_resubmits() -> None:
    manifest = _manifest()
    runner = LaunchStateRunner(manifest, fail_after_accept=True)
    store = ExactStore()
    common = {
        "manifest_identity": MANIFEST_IDENTITY,
        "expected_job_uid": JOB_UID,
        "image_uri": IMAGE,
        "read_exact": store.read,
        "publish_create_once": store.publish,
        "runner": runner,
        "manifest_opener": _manifest_opener(manifest),
    }
    armed = cloud.arm_launch_v1(**common)
    intent_identity = armed["launch_intent_identity"]
    with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="ambiguous"):
        cloud.launch_layer_v1(
            **common, launch_intent_identity=intent_identity
        )
    submission_count = sum(
        call[0:4] == ["gcloud", "run", "jobs", "execute"]
        for call in runner.calls
    )
    recovered = cloud.recover_launch_v1(
        manifest_identity=MANIFEST_IDENTITY,
        expected_job_uid=JOB_UID,
        image_uri=IMAGE,
        launch_intent_identity=intent_identity,
        read_exact=store.read,
        runner=runner,
        manifest_opener=_manifest_opener(manifest),
    )
    assert recovered["recovered_without_resubmission"] is True
    assert recovered["launch_result"]["cloud_execution_name"] == EXECUTION
    assert sum(
        call[0:4] == ["gcloud", "run", "jobs", "execute"]
        for call in runner.calls
    ) == submission_count == 1

    replay = cloud.recover_launch_v1(
        manifest_identity=MANIFEST_IDENTITY,
        expected_job_uid=JOB_UID,
        image_uri=IMAGE,
        launch_intent_identity=intent_identity,
        read_exact=store.read,
        runner=runner,
        manifest_opener=_manifest_opener(manifest),
    )
    assert replay["launch_result"] == recovered["launch_result"]
    assert replay["recovered_without_resubmission"] is True
    recovery_source = inspect.getsource(cloud.recover_launch_v1)
    for forbidden in (
        "publish_create_once", "open_known", "metadata.reload", "execute_argv_v1"
    ):
        assert forbidden not in recovery_source


def test_recover_launch_rejects_unchanged_or_spliced_provider_state() -> None:
    manifest = _manifest()
    arm_runner = ProviderRunner(manifest)
    store = ExactStore()
    armed = cloud.arm_launch_v1(
        manifest_identity=MANIFEST_IDENTITY,
        expected_job_uid=JOB_UID,
        image_uri=IMAGE,
        read_exact=store.read,
        publish_create_once=store.publish,
        runner=arm_runner,
        manifest_opener=_manifest_opener(manifest),
    )
    for runner in (
        ProviderRunner(manifest),
        ProviderRunner(manifest, latest=f"other-job-abc12"),
    ):
        with pytest.raises(
            cloud.CurrentBankCloudOperatorV1Error,
            match="exactly one changed",
        ):
            cloud.recover_launch_v1(
                manifest_identity=MANIFEST_IDENTITY,
                expected_job_uid=JOB_UID,
                image_uri=IMAGE,
                launch_intent_identity=armed["launch_intent_identity"],
                read_exact=store.read,
                runner=runner,
                manifest_opener=_manifest_opener(manifest),
            )


def test_crash_after_marker_before_execute_is_fail_closed_and_requires_rearm() -> None:
    manifest = _manifest()
    runner = ProviderRunner(manifest)
    store = ExactStore()
    armed = cloud.arm_launch_v1(
        manifest_identity=MANIFEST_IDENTITY,
        expected_job_uid=JOB_UID,
        image_uri=IMAGE,
        read_exact=store.read,
        publish_create_once=store.publish,
        runner=runner,
        manifest_opener=_manifest_opener(manifest),
    )
    intent_raw = store.read(armed["launch_intent_identity"])
    intent = cloud.validate_launch_intent_v1(
        json.loads(intent_raw),
        manifest=manifest,
        manifest_identity=MANIFEST_IDENTITY,
        expected_job_uid=JOB_UID,
        image_uri=IMAGE,
    )
    cloud._consume_launch_submission_v1(
        manifest=manifest,
        manifest_identity=MANIFEST_IDENTITY,
        launch_intent=intent,
        launch_intent_identity=armed["launch_intent_identity"],
        publish_create_once=store.publish,
    )
    with pytest.raises(
        cloud.CurrentBankCloudOperatorV1Error,
        match="fresh output prefix",
    ):
        cloud.recover_launch_v1(
            manifest_identity=MANIFEST_IDENTITY,
            expected_job_uid=JOB_UID,
            image_uri=IMAGE,
            launch_intent_identity=armed["launch_intent_identity"],
            read_exact=store.read,
            runner=runner,
            manifest_opener=_manifest_opener(manifest),
        )
    with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="consumed"):
        cloud.launch_layer_v1(
            manifest_identity=MANIFEST_IDENTITY,
            expected_job_uid=JOB_UID,
            image_uri=IMAGE,
            launch_intent_identity=armed["launch_intent_identity"],
            read_exact=store.read,
            publish_create_once=store.publish,
            runner=runner,
            manifest_opener=_manifest_opener(manifest),
        )
    assert not any(
        call[0:4] == ["gcloud", "run", "jobs", "execute"]
        for call in runner.calls
    )


def test_status_describes_exact_execution_and_tasks_without_logs_or_results() -> None:
    manifest = _manifest()
    runner = ProviderRunner(manifest)
    status = cloud.collect_status_v1(
        manifest_identity=MANIFEST_IDENTITY,
        expected_job_uid=JOB_UID,
        image_uri=IMAGE,
        execution_name=EXECUTION,
        read_exact=lambda _identity: b"",
        runner=runner,
        manifest_opener=_manifest_opener(manifest),
    )
    assert status["all_tasks_terminal"] is True
    assert status["all_tasks_succeeded"] is True
    assert status["logs_read"] is False
    assert status["scientific_outputs_read"] is False
    assert status["realized_outcomes_read"] is False
    assert runner.calls[0] == cloud.execution_describe_argv_v1(EXECUTION)
    assert runner.calls[1:] == [
        cloud.task_describe_argv_v1(job=JOB, execution=EXECUTION, task_index=index)
        for index in range(2)
    ]
    joined = " ".join(token.lower() for call in runner.calls for token in call)
    for forbidden in (" logs ", " list ", " result", "outcome"):
        assert forbidden not in f" {joined} "


def test_real_v1_task_shape_omits_index_and_retried_but_rejects_wrong_values() -> None:
    retained = _task_description(1)
    assert "index" not in retained["status"]
    assert "retried" not in retained["status"]
    assert cloud._task_status_v1(
        retained, execution=EXECUTION, task_index=1
    )["task_index"] == 1
    for field, value in (("index", 0), ("retried", 1), ("index", "1")):
        changed = json.loads(json.dumps(retained))
        changed["status"][field] = value
        with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="index/attempt"):
            cloud._task_status_v1(
                changed, execution=EXECUTION, task_index=1
            )


def test_partial_terminal_set_blocks_finalize_before_terminal_object_reads() -> None:
    manifest = _manifest()
    runner = ProviderRunner(manifest, active_task_index=1)
    opened: list[str] = []

    def forbidden_open(uri: str, maximum: int):
        opened.append(uri)
        raise AssertionError((uri, maximum))

    with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="every task"):
        cloud.finalize_layer_v1(
            manifest_identity=MANIFEST_IDENTITY,
            expected_job_uid=JOB_UID,
            image_uri=IMAGE,
            execution_name=EXECUTION,
            read_exact=lambda _identity: b"",
            open_known=forbidden_open,
            publish_create_once=lambda _uri, _raw: {},
            runner=runner,
            manifest_opener=_manifest_opener(manifest),
        )
    assert opened == []


def test_finalize_reads_only_manifest_terminal_uris_and_calls_public_derivers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest()
    runner = ProviderRunner(manifest)
    terminal_objects: dict[str, tuple[bytes, dict[str, object]]] = {}
    for index, binding in enumerate(manifest["task_bindings"]):
        environment = {
            **_common_environment(manifest),
            "CLOUD_RUN_EXECUTION": EXECUTION,
            "CLOUD_RUN_TASK_INDEX": str(index),
            "CLOUD_RUN_TASK_COUNT": "2",
            "CLOUD_RUN_TASK_ATTEMPT": "0",
        }
        evidence = {
            "task_index": index,
            "task_terminal_evidence_sha256": chr(ord("e") + index) * 64,
            "dispatcher_runtime_evidence": {
                "kernel_observed_command": list(cloud.DISPATCHER_COMMAND),
                "selected_environment": environment,
            },
        }
        raw = cloud._canonical_bytes(evidence)
        uri = binding["task_terminal_evidence_uri"]
        terminal_objects[str(uri)] = (
            raw,
            {
                "uri": uri,
                "generation": str(index + 20),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
        )
    opened: list[str] = []

    def open_known(uri: str, maximum: int):
        assert maximum == cloud.task_manifest.MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES
        opened.append(uri)
        return terminal_objects[uri]

    monkeypatch.setattr(
        cloud.task_manifest,
        "validate_task_terminal_evidence_v1",
        lambda value, **_kwargs: dict(value),
    )
    calls: list[str] = []
    captured_source: dict[str, object] = {}

    def publish_source(source: Mapping[str, object], **_kwargs: object):
        calls.append("publish-source")
        captured_source.update(source)
        raw = cloud._canonical_bytes(source)
        return {
            "uri": OUTPUT_PREFIX + "authorities/cloud-run/projection-source.json",
            "generation": "30",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    def build_observed(**_kwargs: object):
        calls.append("build-observed")
        return {"observed_cloud_run_execution_sha256": "1" * 64}

    def build_receipt(**_kwargs: object):
        calls.append("build-receipt")
        return {"layer_execution_receipt_sha256": "2" * 64}

    def publish_receipt(_receipt: object, **_kwargs: object):
        calls.append("publish-receipt")
        return {
            "uri": OUTPUT_PREFIX + "authorities/layer-receipt.json",
            "generation": "31",
            "sha256": "3" * 64,
            "bytes": 1_000,
        }

    monkeypatch.setattr(
        cloud.task_manifest,
        "publish_cloud_run_execution_observation_source_v1",
        publish_source,
    )
    monkeypatch.setattr(
        cloud.task_manifest,
        "build_observed_cloud_run_execution_authority_v1",
        build_observed,
    )
    monkeypatch.setattr(
        cloud.task_manifest,
        "build_layer_execution_receipt_v1",
        build_receipt,
    )
    monkeypatch.setattr(
        cloud.task_manifest,
        "publish_layer_execution_receipt_v1",
        publish_receipt,
    )
    result = cloud.finalize_layer_v1(
        manifest_identity=MANIFEST_IDENTITY,
        expected_job_uid=JOB_UID,
        image_uri=IMAGE,
        execution_name=EXECUTION,
        read_exact=lambda _identity: b"",
        open_known=open_known,
        publish_create_once=lambda _uri, _raw: {},
        runner=runner,
        manifest_opener=_manifest_opener(manifest),
    )
    assert opened == [
        row["task_terminal_evidence_uri"] for row in manifest["task_bindings"]
    ]
    assert calls == [
        "publish-source", "build-observed", "build-receipt", "publish-receipt"
    ]
    expected_scope = cloud.task_manifest._task_terminal_generation_resolution_scope_v1(
        manifest["task_bindings"]
    )
    assert captured_source["task_terminal_generation_resolution_scope"] == expected_scope
    assert captured_source[
        "task_terminal_generation_resolution_scope_sha256"
    ] == cloud._canonical_sha(expected_scope)
    assert result["all_tasks_terminal"] is True
    assert result["scientific_outputs_read"] is False
    assert result["realized_outcomes_read"] is False
    assert result["logs_read"] is False


def test_prepare_has_no_caller_source_identity_slots_and_uses_fixed_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = {
        "schema_version": cloud.PREPARE_REQUEST_SCHEMA,
        "output_prefix": OUTPUT_PREFIX,
        "code_commit": COMMIT,
        "image_digest": DIGEST,
        "reused_job_name": JOB,
    }
    poison = dict(request)
    poison["panel_root_identity"] = {
        "uri": "gs://attacker/fabricated.json",
        "generation": "1",
        "sha256": "0" * 64,
        "bytes": 2,
    }
    with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="fields"):
        cloud.validate_prepare_request_v1(poison)

    local_paths: list[Path] = []

    def local_reader(path: Path, **_kwargs: object) -> bytes:
        local_paths.append(path)
        return b"frozen"

    exact_identities: list[dict[str, object]] = []

    def exact_reader(identity: object, **_kwargs: object):
        exact_identities.append(dict(identity))
        return b"{}", dict(identity)

    captured: dict[str, object] = {}

    def prepare_stub(**kwargs: object):
        captured.update(kwargs)
        return {"manifest_identity": dict(MANIFEST_IDENTITY)}

    monkeypatch.setattr(cloud, "_read_frozen_local_source_v1", local_reader)
    monkeypatch.setattr(cloud, "_read_exact_identity_bytes_v1", exact_reader)
    monkeypatch.setattr(preparation, "prepare_projection_first_layer_v1", prepare_stub)
    result = cloud.prepare_first_layer_v1(
        request=request,
        read_exact=lambda _identity: b"",
        publish_create_once=lambda _uri, _raw: {},
    )
    repository = Path(cloud.__file__).resolve().parents[1]
    assert local_paths == [
        repository / contract.MODULE_PATH,
        repository / contract.CONTRACT_REPORT_PATH,
    ]
    assert exact_identities == [contract.PANEL_IDENTITY]
    assert captured["panel_root_identity"] == contract.PANEL_IDENTITY
    assert captured["output_prefix"] == OUTPUT_PREFIX
    assert result == {"manifest_identity": MANIFEST_IDENTITY}


def _published_identity(uri: str, value: object) -> tuple[bytes, dict[str, object]]:
    raw = cloud._canonical_bytes(value)
    return raw, {
        "uri": uri,
        "generation": "41",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


@pytest.mark.parametrize(
    ("target_layer_id", "expected_predecessor_count"),
    [
        ("broad-selection-receipt", 1),
        ("broad-evaluation-result", 2),
        ("nomination", 3),
        ("confirmation-selection-receipt", 4),
        ("confirmation-evaluation-result", 5),
        ("aggregate-finalists", 6),
        ("terminal-root", 7),
    ],
)
def test_prepare_layer_derives_each_registered_ordinal_and_predecessor_order(
    target_layer_id: str, expected_predecessor_count: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = cloud.task_manifest.layer_registry_v1(OUTPUT_PREFIX)
    target = next(row for row in registry if row["layer_id"] == target_layer_id)
    projection_body = {"output_prefix": OUTPUT_PREFIX, "fixture": "projection"}
    projection_uri = preparation.projection_preparation_uri_lattice_v1(
        OUTPUT_PREFIX
    )["projection-preparation-receipt"]
    projection_raw, projection_identity = _published_identity(
        projection_uri, projection_body
    )
    objects = {projection_uri: projection_raw}
    predecessor_identities: list[dict[str, object]] = []
    predecessor_bodies: list[dict[str, object]] = []
    registry_by_layer = {str(row["layer_id"]): row for row in registry}
    for expected_layer in target["predecessor_layers"]:
        uri = registry_by_layer[str(expected_layer)][
            "layer_execution_receipt_uri"
        ]
        body = {"layer_id": expected_layer, "fixture": "receipt"}
        raw, identity = _published_identity(str(uri), body)
        objects[str(uri)] = raw
        predecessor_identities.append(identity)
        predecessor_bodies.append(body)
    request = {
        "schema_version": cloud.PREPARE_LAYER_REQUEST_SCHEMA,
        "projection_preparation_receipt_identity": projection_identity,
        "target_layer_id": target_layer_id,
        "predecessor_layer_receipt_identities": predecessor_identities,
    }
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        preparation,
        "validate_projection_preparation_receipt_v1",
        lambda value: dict(value),
    )

    def prepare_stub(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "layer_id": kwargs["target_layer_id"],
            "layer_ordinal": kwargs["target_layer_ordinal"],
        }

    monkeypatch.setattr(
        layer_preparation, "prepare_registered_layer_v1", prepare_stub
    )
    result = cloud.prepare_later_layer_v1(
        request=request,
        read_exact=lambda identity: objects[str(identity["uri"])],
        publish_create_once=lambda _uri, _raw: {},
    )
    assert expected_predecessor_count == int(target["layer_ordinal"])
    assert result == {
        "layer_id": target_layer_id,
        "layer_ordinal": target["layer_ordinal"],
    }
    assert captured["projection_preparation_receipt"] == projection_body
    assert captured["projection_preparation_receipt_identity"] == projection_identity
    assert captured["target_layer_ordinal"] == target["layer_ordinal"]
    assert [
        row["receipt"] for row in captured["predecessor_layer_receipts"]
    ] == predecessor_bodies
    assert [
        row["identity"] for row in captured["predecessor_layer_receipts"]
    ] == predecessor_identities


def test_prepare_layer_rejects_missing_extra_wrong_order_and_caller_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = cloud.task_manifest.layer_registry_v1(OUTPUT_PREFIX)
    target = next(
        row for row in registry if row["layer_id"] == "broad-evaluation-result"
    )
    projection_body = {"output_prefix": OUTPUT_PREFIX}
    projection_uri = preparation.projection_preparation_uri_lattice_v1(
        OUTPUT_PREFIX
    )["projection-preparation-receipt"]
    projection_raw, projection_identity = _published_identity(
        projection_uri, projection_body
    )
    registry_by_layer = {str(row["layer_id"]): row for row in registry}
    identities: list[dict[str, object]] = []
    objects = {projection_uri: projection_raw}
    for layer_id in target["predecessor_layers"]:
        uri = str(registry_by_layer[str(layer_id)]["layer_execution_receipt_uri"])
        raw, identity = _published_identity(uri, {"layer_id": layer_id})
        objects[uri] = raw
        identities.append(identity)
    base = {
        "schema_version": cloud.PREPARE_LAYER_REQUEST_SCHEMA,
        "projection_preparation_receipt_identity": projection_identity,
        "target_layer_id": target["layer_id"],
        "predecessor_layer_receipt_identities": identities,
    }
    for changed in (
        {**base, "predecessor_layer_receipt_identities": identities[:-1]},
        {**base, "predecessor_layer_receipt_identities": identities + [identities[0]]},
    ):
        with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="count"):
            cloud.validate_prepare_layer_request_v1(changed)
    for forbidden_field in ("output_prefix", "realized_outcome_metrics"):
        with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="fields"):
            cloud.validate_prepare_layer_request_v1(
                {**base, forbidden_field: OUTPUT_PREFIX}
            )
    monkeypatch.setattr(
        preparation,
        "validate_projection_preparation_receipt_v1",
        lambda value: dict(value),
    )
    with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="order/URI"):
        cloud.prepare_later_layer_v1(
            request={
                **base,
                "predecessor_layer_receipt_identities": list(reversed(identities)),
            },
            read_exact=lambda identity: objects[str(identity["uri"])],
            publish_create_once=lambda _uri, _raw: {},
        )
    source = inspect.getsource(cloud.prepare_later_layer_v1)
    assert "open_known" not in source
    assert "reload" not in source
    assert "list_" not in source
    assert "logs" not in source


def test_prepare_layer_cli_writes_only_the_exclusive_local_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection_raw, projection_identity = _published_identity(
        OUTPUT_PREFIX + "authorities/projection-preparation/receipt.json",
        {"fixture": "projection"},
    )
    del projection_raw
    predecessor_raw, predecessor_identity = _published_identity(
        OUTPUT_PREFIX + "authorities/layer-execution-receipts/00-projection.json",
        {"fixture": "projection-layer"},
    )
    del predecessor_raw
    request = {
        "schema_version": cloud.PREPARE_LAYER_REQUEST_SCHEMA,
        "projection_preparation_receipt_identity": projection_identity,
        "target_layer_id": "broad-selection-receipt",
        "predecessor_layer_receipt_identities": [predecessor_identity],
    }
    request_path = tmp_path / "prepare-layer-request.json"
    request_path.write_bytes(cloud._canonical_bytes(request))
    request_path.chmod(0o600)
    output_path = tmp_path / "prepare-layer-result.json"
    monkeypatch.setattr(cloud, "_storage_client_v1", lambda: object())
    monkeypatch.setattr(
        cloud,
        "GCSExactOperatorStoreV1",
        lambda _client: SimpleNamespace(
            read_exact=lambda _identity: b"",
            publish_create_once=lambda _uri, _raw: {},
        ),
    )
    monkeypatch.setattr(
        cloud,
        "prepare_later_layer_v1",
        lambda **_kwargs: {
            "layer_id": "broad-selection-receipt",
            "layer_ordinal": 1,
        },
    )
    assert cloud.main([
        "prepare-layer", "--request-file", str(request_path.resolve()),
        "--output-file", str(output_path.resolve()),
    ]) == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "layer_id": "broad-selection-receipt",
        "layer_ordinal": 1,
    }
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o600


def test_cli_reads_owned_bounded_request_and_exclusively_creates_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = {
        "schema_version": cloud.OPERATOR_REQUEST_SCHEMA,
        "manifest_identity": MANIFEST_IDENTITY,
        "expected_job_uid": JOB_UID,
        "image_uri": IMAGE,
    }
    request_path = tmp_path / "request.json"
    request_path.write_bytes(cloud._canonical_bytes(request))
    request_path.chmod(0o600)
    output_path = tmp_path / "result.json"
    monkeypatch.setattr(cloud, "_storage_client_v1", lambda: object())
    monkeypatch.setattr(
        cloud,
        "GCSExactOperatorStoreV1",
        lambda _client: SimpleNamespace(
            read_exact=lambda _identity: b"",
            open_known=lambda _uri, _maximum: None,
            publish_create_once=lambda _uri, _raw: {},
        ),
    )
    monkeypatch.setattr(cloud, "SubprocessRunnerV1", lambda: object())
    monkeypatch.setattr(
        cloud,
        "configure_layer_v1",
        lambda **_kwargs: {
            "schema_version": cloud.CONFIGURATION_RESULT_SCHEMA,
            "configuration_result_sha256": "4" * 64,
        },
    )
    assert cloud.main([
        "configure", "--request-file", str(request_path.resolve()),
        "--output-file", str(output_path.resolve()),
    ]) == 0
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o600
    assert json.loads(output_path.read_text(encoding="utf-8"))[
        "configuration_result_sha256"
    ] == "4" * 64
    with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="exclusive"):
        cloud.main([
            "configure", "--request-file", str(request_path.resolve()),
            "--output-file", str(output_path.resolve()),
        ])


def test_launch_operator_requests_require_exact_two_phase_identities() -> None:
    common = {
        "schema_version": cloud.OPERATOR_REQUEST_SCHEMA,
        "manifest_identity": MANIFEST_IDENTITY,
        "expected_job_uid": JOB_UID,
        "image_uri": IMAGE,
    }
    intent_identity = {
        "uri": OUTPUT_PREFIX + "authorities/cloud-run-launch-intents/00-projection.json",
        "generation": "8",
        "sha256": "8" * 64,
        "bytes": 1_000,
    }
    assert cloud.validate_operator_request_v1(
        common, mode="arm-launch"
    ) == common
    with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="fields"):
        cloud.validate_operator_request_v1(common, mode="launch")
    launch_request = {**common, "launch_intent_identity": intent_identity}
    assert cloud.validate_operator_request_v1(
        launch_request, mode="launch"
    )["launch_intent_identity"] == intent_identity
    recovery = cloud.validate_operator_request_v1(
        launch_request, mode="recover-launch",
    )
    assert recovery["launch_intent_identity"] == intent_identity
    for poison in (
        {**launch_request, "realized_score": 300.0},
        {**launch_request, "launch_result_identity": None},
    ):
        with pytest.raises(cloud.CurrentBankCloudOperatorV1Error, match="fields"):
            cloud.validate_operator_request_v1(
                poison,
                mode=("recover-launch" if "launch_result_identity" in poison else "launch"),
            )


def test_arm_launch_cli_fsyncs_exclusive_result_without_submitting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = {
        "schema_version": cloud.OPERATOR_REQUEST_SCHEMA,
        "manifest_identity": MANIFEST_IDENTITY,
        "expected_job_uid": JOB_UID,
        "image_uri": IMAGE,
    }
    request_path = tmp_path / "arm-request.json"
    request_path.write_bytes(cloud._canonical_bytes(request))
    request_path.chmod(0o600)
    output_path = tmp_path / "arm-result.json"
    monkeypatch.setattr(cloud, "_storage_client_v1", lambda: object())
    monkeypatch.setattr(
        cloud,
        "GCSExactOperatorStoreV1",
        lambda _client: SimpleNamespace(
            read_exact=lambda _identity: b"",
            publish_create_once=lambda _uri, _raw: {},
        ),
    )
    monkeypatch.setattr(cloud, "SubprocessRunnerV1", lambda: object())
    monkeypatch.setattr(
        cloud,
        "arm_launch_v1",
        lambda **_kwargs: {
            "schema_version": cloud.ARM_LAUNCH_RESULT_SCHEMA,
            "launch_intent_identity": {
                "uri": OUTPUT_PREFIX + "intent.json",
                "generation": "1",
                "sha256": "a" * 64,
                "bytes": 100,
            },
            "submission_call_count": 0,
        },
    )
    monkeypatch.setattr(
        cloud,
        "launch_layer_v1",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not submit")),
    )
    assert cloud.main([
        "arm-launch", "--request-file", str(request_path.resolve()),
        "--output-file", str(output_path.resolve()),
    ]) == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))[
        "submission_call_count"
    ] == 0
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o600


def test_operator_source_has_bounded_capture_and_no_forbidden_discovery() -> None:
    source = Path(cloud.__file__).read_text(encoding="utf-8")
    assert "stdout=subprocess.PIPE" not in source
    assert "stderr=subprocess.PIPE" not in source
    assert "TemporaryFile" in source
    assert "self._cache" not in source
    assert "open_optional" not in source
    assert "cloud-run-launch-results" not in source
    for forbidden in (
        '"create"', '"deploy"', '"list"', '"logs"', "list_blobs",
        "selector_v1", "evaluation_v1", "aggregate_v1",
    ):
        assert forbidden not in source
