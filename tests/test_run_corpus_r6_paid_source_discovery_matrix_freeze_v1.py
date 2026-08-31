from __future__ import annotations

import base64
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_corpus_r6_paid_source_discovery_matrix_freeze_v1 as runner
from nfl_dfs.research import corpus_r6_paid_source_discovery_matrix_freeze_v1 as freeze


def test_every_mutating_cli_phase_is_default_off(tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")
    invocations = [
        ["prepare", "--request", str(payload), "--execute"],
        ["task0", "--manifest-identity", str(payload), "--execute"],
        ["task", "--manifest-identity", str(payload), "--execute"],
        ["collect", "--request", str(payload), "--execute"],
        ["reopen-task", "--terminal-identity", str(payload), "--execute"],
        ["reopen-collect", "--request", str(payload), "--execute"],
    ]
    for argv in invocations:
        with pytest.raises(runner.DiscoveryMatrixRunnerV1Error, match="disabled"):
            runner.run(argv, environment={})


def test_runtime_authority_binds_exact_54_task_execution() -> None:
    manifest = {
        "manifest_sha256": "1" * 64,
        "code_sha": "2" * 40,
        "immutable_image": (
            "us-central1-docker.pkg.dev/nfl-predictions-503414/"
            "nfl-dfs/nfl-dfs@sha256:" + "3" * 64
        ),
        "build_id": "12345678-1234-1234-1234-123456789abc",
    }
    env = {
        runner.ENABLE_ENV: runner.ENABLE_VALUE,
        runner.OUTCOMES_ENV: "false",
        runner.CODE_SHA_ENV: manifest["code_sha"],
        runner.IMAGE_ENV: manifest["immutable_image"],
        runner.BUILD_ID_ENV: manifest["build_id"],
        "CLOUD_RUN_JOB": runner.JOB,
        "CLOUD_RUN_EXECUTION": runner.JOB + "-abc12",
        "CLOUD_RUN_TASK_INDEX": "7",
        "CLOUD_RUN_TASK_COUNT": "54",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
        runner.TASK0_EXECUTION_ENV: runner.JOB + "-smk12",
        runner.TASK0_GATE_SHA_ENV: "4" * 64,
        runner.TASK0_GATE_B64_ENV: "ZHVtbXk=",
    }
    authority = runner._runtime(manifest, 7, env, mode="task")
    assert authority["source_task_ordinal"] == 7
    assert authority["task_count"] == 54
    assert authority["outcomes_allowed"] is False
    tampered = dict(env, CLOUD_RUN_TASK_ATTEMPT="1")
    with pytest.raises(runner.DiscoveryMatrixRunnerV1Error):
        runner._runtime(manifest, 7, tampered, mode="task")


def test_provider_uses_one_exact_execution_and_requires_job_uid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = runner.JOB + "-abc12"
    manifest = {
        "manifest_sha256": "1" * 64,
        "code_sha": "2" * 40,
        "immutable_image": (
            "us-central1-docker.pkg.dev/nfl-predictions-503414/"
            "nfl-dfs/nfl-dfs@sha256:" + "3" * 64
        ),
        "image_digest": "sha256:" + "3" * 64,
        "build_id": "12345678-1234-1234-1234-123456789abc",
    }
    payload_identity = {
        "uri": "gs://test/manifest.json",
        "generation": "1",
        "sha256": "5" * 64,
        "bytes": 10,
    }
    payload = freeze.canonical_json_bytes(payload_identity)
    environment = {
        runner.CODE_SHA_ENV: manifest["code_sha"],
        runner.IMAGE_ENV: manifest["immutable_image"],
        "IMAGE_DIGEST": manifest["image_digest"],
        runner.BUILD_ID_ENV: manifest["build_id"],
        runner.ENABLE_ENV: runner.ENABLE_VALUE,
        runner.MODE_ENV: "task0",
        runner.OUTCOMES_ENV: "false",
        runner.PAYLOAD_ENV: base64.b64encode(payload).decode("ascii"),
        runner.PAYLOAD_SHA_ENV: sha256(payload).hexdigest(),
        runner.TASK0_EXECUTION_ENV: "none",
        runner.TASK0_GATE_SHA_ENV: "none",
        runner.TASK0_GATE_B64_ENV: "none",
    }
    document = {
        "metadata": {
            "name": execution,
            "uid": "execution-uid",
            "labels": {
                "run.googleapis.com/job": runner.JOB,
                "run.googleapis.com/jobUid": runner.JOB_UID,
            },
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "maxRetries": 0,
                "timeoutSeconds": freeze.TASK_TIMEOUT_SECONDS,
                "serviceAccountName": freeze.SERVICE_ACCOUNT,
                "containers": [{
                    "image": manifest["immutable_image"],
                    "command": list(freeze.CONTAINER_COMMAND),
                    "args": [freeze.CONTAINER_SCRIPT, "container-run", "task0"],
                    "resources": {"limits": {
                        "cpu": freeze.CPU_LIMIT,
                        "memory": freeze.MEMORY_LIMIT,
                    }},
                    "env": [
                        {"name": key, "value": value}
                        for key, value in environment.items()
                    ],
                }],
            }},
        },
        "status": {
            "succeededCount": 1,
            "conditions": [{"type": "Completed", "status": "True"}],
        },
    }
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=json.dumps(document))

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    observed = runner.GCloudProviderV1().completed(execution)
    assert calls[0][5] == execution
    assert "list" not in calls[0]
    assert observed["job_uid"] == runner.JOB_UID
    receipt = runner._execution(
        observed,
        execution_id=execution,
        task_count=1,
        mode="task0",
        payload_identity=payload_identity,
        manifest=manifest,
    )
    assert receipt["provider_execution_sha256"]
    assert receipt["task_count"] == 1
    assert receipt["max_retries"] == 0
    invented = dict(observed, task_count=2)
    with pytest.raises(runner.DiscoveryMatrixRunnerV1Error):
        runner._execution(
            invented,
            execution_id=execution,
            task_count=1,
            mode="task0",
            payload_identity=payload_identity,
            manifest=manifest,
        )
    caller_spoofed = dict(observed, environment={
        **observed["environment"],
        "IMAGE_SOURCE_COMMIT_SHA": manifest["code_sha"],
    })
    with pytest.raises(
        runner.DiscoveryMatrixRunnerV1Error,
        match="caller environment must not substitute",
    ):
        runner._execution(
            caller_spoofed,
            execution_id=execution,
            task_count=1,
            mode="task0",
            payload_identity=payload_identity,
            manifest=manifest,
        )


def test_task0_adapter_exposes_no_publication_api() -> None:
    adapter = runner.ReadOnlyStoreAdapterV1(lambda identity: b"exact")
    assert adapter.read_exact({}) == b"exact"
    assert not hasattr(adapter, "publish_bytes_create_once")
    assert not hasattr(adapter, "publish_file_create_once")


def test_large_matrix_transport_is_streamed_from_files() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "upload_from_filename" in source
    assert "download_to_filename" in source
    assert "publish_file_create_once" in source
    assert "for chunk in iter(lambda: handle.read(4 * 1024 * 1024)" in source
    assert freeze.MATRIX_DTYPE.str == "<f8"
    assert freeze.MAX_MATRIX_BYTES == 2 * 1024 * 1024 * 1024
