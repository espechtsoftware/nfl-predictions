#!/usr/bin/env python3
"""Operate one fresh current-bank crossed-screen Cloud Run layer.

This is deliberately a thin provider adapter.  It can update one already
existing UID-bound job, submit one asynchronous execution, describe only the
execution and its known task resources, and publish the manifest contract's
observation/receipt authorities.  It cannot create jobs, read logs, list
objects, inspect scientific publications, or relaunch a consumed request.
Launch is deliberately two phase: ``arm-launch`` durably publishes the exact
intent before ``launch`` may create its one-shot submission marker.  A crash
after marker creation but before provider submission is fail-closed and needs
a fresh output prefix; a consumed provider submission is safely reconstructed
by ``recover-launch`` without another submission or a current-head lookup.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from typing import Final

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)


PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
DISPATCHER_PYTHON: Final = "/usr/local/bin/python3.11"
DISPATCHER_SCRIPT: Final = (
    "/app/scripts/"
    "run_corpus_r6_current_bank_crossed_screen_task_dispatcher_v1.py"
)
DISPATCHER_COMMAND: Final = (DISPATCHER_PYTHON, "-I", DISPATCHER_SCRIPT)
TASK_TIMEOUT_SECONDS: Final = 7_260
CPU: Final = "8"
MEMORY: Final = "32Gi"
ENV_DELIMITER: Final = "|"
ABSENT_RESUME: Final = task_manifest.ABSENT_RESUME_AUTHORITY_ENV_VALUE
MAXIMUM_REQUEST_BYTES: Final = 64_000
MAXIMUM_LOCAL_RESULT_BYTES: Final = 8_000_000
MAXIMUM_PROVIDER_JSON_BYTES: Final = 8_000_000
MAXIMUM_SUBMISSION_STDOUT_BYTES: Final = 4_096
MAXIMUM_SUBPROCESS_STDERR_BYTES: Final = 256_000
MAXIMUM_LAUNCH_INTENT_BYTES: Final = 256_000
MAXIMUM_LAUNCH_SUBMISSION_MARKER_BYTES: Final = 256_000
FLAGS_FILE_MODE: Final = 0o600
LOCAL_INPUT_MODE_MASK: Final = 0o022
LOCAL_OUTPUT_MODE: Final = 0o600

OPERATOR_REQUEST_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-cloud-operator-request/v1"
)
JOB_PROJECTION_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-cloud-job-projection/v1"
)
CONFIGURATION_RESULT_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-cloud-configuration/v1"
)
LAUNCH_INTENT_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-cloud-launch-intent/v1"
)
ARM_LAUNCH_RESULT_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-cloud-arm-launch-result/v1"
)
LAUNCH_SUBMISSION_MARKER_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-cloud-launch-submission-marker/v1"
)
LAUNCH_RESULT_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-cloud-launch-result/v1"
)
LAUNCH_OPERATION_RESULT_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-cloud-launch-operation-result/v1"
)
STATUS_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-cloud-status/v1"
)
FINALIZE_RESULT_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-cloud-finalize-result/v1"
)
PREPARE_REQUEST_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-cloud-prepare-request/v1"
)
PREPARE_LAYER_REQUEST_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-cloud-prepare-layer-request/v1"
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_JOB = re.compile(r"[a-z][a-z0-9-]{0,62}\Z")
_UID = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,127}\Z")
_EXECUTION = re.compile(r"[a-z][a-z0-9-]{0,62}\Z")
_TASK = re.compile(r"[a-z][a-z0-9-]{0,127}\Z")
_DIGEST_IMAGE = re.compile(
    r"[a-z0-9][a-z0-9._/-]{0,511}@sha256:[0-9a-f]{64}\Z"
)

ReadExact = Callable[[Mapping[str, object]], bytes]
OpenKnown = Callable[[str, int], tuple[bytes, Mapping[str, object]]]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]
CommandRunner = Callable[[Sequence[str]], Mapping[str, object]]


class CurrentBankCloudOperatorV1Error(RuntimeError):
    """The fresh-run Cloud Run operator failed closed."""


def _fail(message: str) -> None:
    raise CurrentBankCloudOperatorV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _string(value: object, *, label: str, maximum: int = 2_048) -> str:
    if type(value) is not str or not value or len(value.encode("utf-8")) > maximum:
        _fail(f"{label} must be a bounded nonempty string")
    return value


def _integer(value: object, *, label: str, minimum: int = 0, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _fail(f"{label} must be an exact bounded integer")
    return value


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CurrentBankCloudOperatorV1Error(
            "operator value is not canonical JSON"
        ) from exc


def _canonical_sha(value: object) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    retained = dict(value)
    retained[field] = _canonical_sha(retained)
    return retained


def _require_self_hash_v1(
    value: Mapping[str, object], *, field: str, label: str,
) -> None:
    observed = value.get(field)
    body = dict(value)
    body.pop(field, None)
    if (
        type(observed) is not str
        or _SHA.fullmatch(observed) is None
        or observed != _canonical_sha(body)
    ):
        _fail(f"{label} self-hash differs")


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes:
        _fail(f"{label} must be bytes")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                _fail(f"{label} repeats JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: _fail(
                f"{label} contains non-finite constant {token}"
            ),
        )
    except CurrentBankCloudOperatorV1Error:
        raise
    except Exception as exc:
        raise CurrentBankCloudOperatorV1Error(
            f"{label} is not strict UTF-8 JSON"
        ) from exc
    return _mapping(value, label=label)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return contract._safe_object_identity(value, label=label)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CurrentBankCloudOperatorV1Error(str(exc)) from exc


def _image_uri(value: object, *, manifest: Mapping[str, object]) -> str:
    image = _string(value, label="immutable image URI", maximum=600)
    if (
        _DIGEST_IMAGE.fullmatch(image) is None
        or image.rsplit("@", 1)[1] != manifest.get("image_digest")
    ):
        _fail("immutable image URI/digest differs from manifest")
    return image


def _short_resource_name(value: object, *, label: str, pattern: re.Pattern[str]) -> str:
    raw = _string(value, label=label, maximum=1_024)
    retained = raw.rstrip("/").rsplit("/", 1)[-1]
    if pattern.fullmatch(retained) is None:
        _fail(f"{label} differs")
    return retained


def _environment_rows(value: object, *, label: str) -> dict[str, str]:
    rows = _sequence(value, label=label)
    retained: dict[str, str] = {}
    for index, raw in enumerate(rows):
        row = _mapping(raw, label=f"{label}[{index}]")
        if set(row) != {"name", "value"}:
            _fail(f"{label}[{index}] is secret-backed or malformed")
        name = _string(row.get("name"), label=f"{label}[{index}] name", maximum=256)
        item = row.get("value")
        if type(item) is not str or name in retained:
            _fail(f"{label}[{index}] name/value differs")
        retained[name] = item
    return retained


def common_job_environment_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
) -> dict[str, str]:
    identity = _identity(manifest_identity, label="job manifest identity")
    raw_identity = _canonical_bytes(identity).decode("utf-8")
    if len(raw_identity.encode("utf-8")) > task_manifest.MAXIMUM_IDENTITY_ENV_BYTES:
        _fail("manifest identity exceeds its environment ceiling")
    retained = {
        "R6_CURRENT_BANK_TASK_DISPATCH_ENABLED": "1",
        task_manifest.DISPATCH_MANIFEST_IDENTITY_ENV: raw_identity,
        task_manifest.DISPATCH_RESUME_AUTHORITY_IDENTITY_ENV: ABSENT_RESUME,
        "GOOGLE_CLOUD_PROJECT": PROJECT,
        "CODE_SHA": _string(
            manifest.get("code_commit"), label="manifest code commit", maximum=40
        ),
        "R6_RUNTIME_IMAGE_DIGEST": _string(
            manifest.get("image_digest"), label="manifest image digest", maximum=71
        ),
        "CLOUD_RUN_JOB": _string(
            manifest.get("reused_job_name"), label="manifest reused job", maximum=63
        ),
    }
    if (
        len(retained) != 7
        or _COMMIT.fullmatch(retained["CODE_SHA"]) is None
        or not retained["R6_RUNTIME_IMAGE_DIGEST"].startswith("sha256:")
        or _SHA.fullmatch(retained["R6_RUNTIME_IMAGE_DIGEST"][7:]) is None
        or _JOB.fullmatch(retained["CLOUD_RUN_JOB"]) is None
        or any(ENV_DELIMITER in key or ENV_DELIMITER in value for key, value in retained.items())
    ):
        _fail("exact seven-entry job environment differs")
    return retained


def configured_job_environment_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
) -> dict[str, str]:
    """Return only caller-configurable env; Cloud Run injects its job name."""
    retained = common_job_environment_v1(
        manifest=manifest, manifest_identity=manifest_identity
    )
    injected_job = retained.pop("CLOUD_RUN_JOB", None)
    if injected_job != manifest.get("reused_job_name") or len(retained) != 6:
        _fail("configured job environment differs from provider injection law")
    return retained


def environment_flag_v1(environment: Mapping[str, str]) -> str:
    retained = _mapping(environment, label="job environment flag")
    if (
        len(retained) != 6
        or "CLOUD_RUN_JOB" in retained
        or any(type(value) is not str for value in retained.values())
        or any(
            ENV_DELIMITER in key
            or ENV_DELIMITER in str(value)
            or "=" in key
            for key, value in retained.items()
        )
    ):
        _fail("job environment cannot use the frozen custom delimiter")
    pairs = [f"{key}={retained[key]}" for key in sorted(retained)]
    return f"^{ENV_DELIMITER}^" + ENV_DELIMITER.join(pairs)


def configure_flags_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    image_uri: str,
) -> dict[str, object]:
    count = _integer(
        manifest.get("task_count"), label="manifest task count", minimum=1,
        maximum=220,
    )
    environment = configured_job_environment_v1(
        manifest=manifest, manifest_identity=manifest_identity
    )
    retained_image = _image_uri(image_uri, manifest=manifest)
    return {
        "--args": f"^{ENV_DELIMITER}^-I{ENV_DELIMITER}{DISPATCHER_SCRIPT}",
        "--clear-cloudsql-instances": True,
        "--clear-network": True,
        "--clear-secrets": True,
        "--clear-volume-mounts": True,
        "--clear-volumes": True,
        "--clear-vpc-connector": True,
        "--command": DISPATCHER_PYTHON,
        "--cpu": CPU,
        "--image": retained_image,
        "--max-retries": 0,
        "--memory": MEMORY,
        "--parallelism": count,
        "--set-env-vars": environment_flag_v1(environment),
        "--task-timeout": f"{TASK_TIMEOUT_SECONDS}s",
        "--tasks": count,
        "--workdir": "",
    }


def configure_argv_v1(job: str, *, flags_path: str) -> list[str]:
    retained_job = _string(job, label="configured job", maximum=63)
    path = Path(flags_path)
    if (
        _JOB.fullmatch(retained_job) is None
        or not path.is_absolute()
        or path.name in {"", ".", ".."}
        or "\x00" in flags_path
    ):
        _fail("configure job or flags path differs")
    return [
        "gcloud", "run", "jobs", "update", retained_job,
        "--project", PROJECT,
        "--region", REGION,
        "--quiet",
        f"--flags-file={path}",
        "--format=json",
    ]


def job_describe_argv_v1(job: str) -> list[str]:
    retained = _string(job, label="described job", maximum=63)
    if _JOB.fullmatch(retained) is None:
        _fail("described job differs")
    return [
        "gcloud", "run", "jobs", "describe", retained,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ]


def execution_describe_argv_v1(execution: str) -> list[str]:
    retained = _short_resource_name(
        execution, label="described execution", pattern=_EXECUTION
    )
    return [
        "gcloud", "run", "jobs", "executions", "describe", retained,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ]


def task_describe_argv_v1(
    *, job: str, execution: str, task_index: int,
) -> list[str]:
    retained_job = _string(job, label="task job", maximum=63)
    retained_execution = _short_resource_name(
        execution, label="task execution", pattern=_EXECUTION
    )
    index = _integer(task_index, label="task index", maximum=219)
    if _JOB.fullmatch(retained_job) is None:
        _fail("task job differs")
    # The GA gcloud command is bound to Cloud Run v1.  Its exact Task ID is
    # deterministically named by Cloud Run; passing a v2 projects/.../tasks
    # URI to this v1 command does not resolve the intended resource.
    resource = f"{retained_execution}-task{index}"
    if _TASK.fullmatch(resource) is None:
        _fail("derived Cloud Run task resource differs")
    return [
        "gcloud", "run", "jobs", "executions", "tasks", "describe",
        resource, "--project", PROJECT, "--region", REGION, "--format=json",
    ]


def execute_argv_v1(job: str) -> list[str]:
    retained = _string(job, label="executed job", maximum=63)
    if _JOB.fullmatch(retained) is None:
        _fail("executed job differs")
    return [
        "gcloud", "run", "jobs", "execute", retained,
        "--project", PROJECT, "--region", REGION,
        "--async", "--format=value(metadata.name)",
    ]


def _container_from_job_description(
    value: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    spec = _mapping(value.get("spec"), label="job spec")
    outer_template = _mapping(spec.get("template"), label="job outer template")
    outer = _mapping(outer_template.get("spec"), label="job outer template spec")
    task_template = _mapping(outer.get("template"), label="job task template")
    task = _mapping(task_template.get("spec"), label="job task template spec")
    containers = _sequence(task.get("containers"), label="job containers")
    if len(containers) != 1:
        _fail("reused job must retain exactly one container")
    return outer, task, _mapping(containers[0], label="job container")


def _metadata_name_uid_generation(
    value: Mapping[str, object], *, kind: str, pattern: re.Pattern[str],
) -> tuple[str, str, str, dict[str, object]]:
    metadata = _mapping(value.get("metadata"), label=f"{kind} metadata")
    name = _short_resource_name(
        metadata.get("name"), label=f"{kind} name", pattern=pattern
    )
    uid = _string(metadata.get("uid"), label=f"{kind} UID", maximum=128)
    generation = str(metadata.get("generation", ""))
    if _UID.fullmatch(uid) is None or not generation.isdigit() or int(generation) < 1:
        _fail(f"{kind} UID/generation differs")
    return name, uid, generation, metadata


def _network_attachment_present(value: object) -> bool:
    if not isinstance(value, Mapping):
        return bool(value)
    for key, item in value.items():
        normalized = str(key).lower().replace("-", "").replace("_", "")
        if any(token in normalized for token in ("network", "vpc", "cloudsql")):
            if item not in (None, "", [], {}):
                return True
        if isinstance(item, Mapping) and _network_attachment_present(item):
            return True
    return False


def _latest_execution_reference_v1(
    value: Mapping[str, object],
) -> dict[str, object] | None:
    status = value.get("status", {})
    if not isinstance(status, Mapping):
        _fail("job status differs")
    latest = status.get("latestCreatedExecution")
    if latest in (None, {}):
        return None
    if not isinstance(latest, Mapping):
        _fail("job latest execution differs")
    retained = {
        "execution_name": _short_resource_name(
            latest.get("name"), label="job latest execution", pattern=_EXECUTION
        ),
        "creation_timestamp": latest.get("creationTimestamp"),
        "completion_timestamp": latest.get("completionTimestamp"),
        "completion_status": latest.get("completionStatus"),
    }
    for field in (
        "creation_timestamp", "completion_timestamp", "completion_status"
    ):
        if retained[field] is not None:
            _string(
                retained[field], label=f"job latest {field}", maximum=128
            )
    return retained


def _latest_execution_name(value: Mapping[str, object]) -> str | None:
    reference = _latest_execution_reference_v1(value)
    return None if reference is None else str(reference["execution_name"])


def validate_job_identity_v1(
    value: object, *, manifest: Mapping[str, object], expected_job_uid: str,
) -> dict[str, object]:
    item = _mapping(value, label="reused job description")
    name, uid, generation, _ = _metadata_name_uid_generation(
        item, kind="job", pattern=_JOB
    )
    expected_uid = _string(expected_job_uid, label="expected job UID", maximum=128)
    if (
        name != manifest.get("reused_job_name")
        or uid != expected_uid
        or _UID.fullmatch(expected_uid) is None
    ):
        _fail("reused job name/UID differs")
    status = _mapping(item.get("status", {}), label="reused job status")
    raw_execution_count = status.get("executionCount", 0)
    if type(raw_execution_count) is not int or raw_execution_count < 0:
        _fail("reused job execution count differs")
    return {
        "job_name": name,
        "job_uid": uid,
        "job_generation": generation,
        "latest_execution_name": _latest_execution_name(item),
        "latest_execution_reference": _latest_execution_reference_v1(item),
        "execution_count": raw_execution_count,
    }


def validate_exact_job_projection_v1(
    value: object, *, manifest: Mapping[str, object], manifest_identity: object,
    expected_job_uid: str, image_uri: str,
) -> dict[str, object]:
    item = _mapping(value, label="configured job description")
    identity = validate_job_identity_v1(
        item, manifest=manifest, expected_job_uid=expected_job_uid
    )
    outer, task, container = _container_from_job_description(item)
    environment = _environment_rows(container.get("env", []), label="job environment")
    resources = _mapping(container.get("resources", {}), label="job resources")
    limits = _mapping(resources.get("limits", {}), label="job resource limits")
    command = _sequence(container.get("command", []), label="job command")
    arguments = _sequence(container.get("args", []), label="job arguments")
    volume_mounts = _sequence(
        container.get("volumeMounts", []), label="job volume mounts"
    )
    volumes = _sequence(task.get("volumes", []), label="job volumes")
    annotations = _mapping(
        _mapping(item.get("metadata"), label="job metadata").get("annotations", {}),
        label="job annotations",
    )
    configured_environment = configured_job_environment_v1(
        manifest=manifest, manifest_identity=manifest_identity
    )
    expected_environment = common_job_environment_v1(
        manifest=manifest, manifest_identity=manifest_identity
    )
    count = _integer(
        manifest.get("task_count"), label="manifest task count", minimum=1,
        maximum=220,
    )
    image = _image_uri(image_uri, manifest=manifest)
    timeout = str(task.get("timeoutSeconds", "")).removesuffix("s")
    if (
        outer.get("taskCount") != count
        or outer.get("parallelism") != count
        or task.get("maxRetries") != 0
        or not timeout.isdigit()
        or int(timeout) != TASK_TIMEOUT_SECONDS
        or container.get("image") != image
        or command != [DISPATCHER_PYTHON]
        or arguments != ["-I", DISPATCHER_SCRIPT]
        or environment != configured_environment
        or limits != {"cpu": CPU, "memory": MEMORY}
        or container.get("workingDir", "") != ""
        or volume_mounts
        or volumes
        or _network_attachment_present(item.get("spec", {}))
        or _network_attachment_present(annotations)
    ):
        _fail("configured reused-job projection differs")
    projection = {
        "schema_version": JOB_PROJECTION_SCHEMA,
        "project_id": PROJECT,
        "location": REGION,
        **identity,
        "image_uri": image,
        "image_digest": manifest["image_digest"],
        "command": [DISPATCHER_PYTHON],
        "args": ["-I", DISPATCHER_SCRIPT],
        "environment": expected_environment,
        "working_dir": "",
        "volume_mounts": [],
        "volumes": [],
        "secret_environment_count": 0,
        "network_attachment_count": 0,
        "cloudsql_instance_count": 0,
        "task_count": count,
        "parallelism": count,
        "maximum_task_retries": 0,
        "timeout_seconds": TASK_TIMEOUT_SECONDS,
        "resource_limits": {"cpu": CPU, "memory": MEMORY},
        "exact_projection_validated": True,
    }
    return _with_hash(projection, field="job_projection_sha256")


def _run_checked(
    runner: CommandRunner, argv: Sequence[str], *, label: str,
    stdout_ceiling: int,
) -> bytes:
    retained_argv = [
        _string(token, label=f"{label} argv[{index}]", maximum=8_192)
        for index, token in enumerate(_sequence(argv, label=f"{label} argv"))
    ]
    try:
        result = _mapping(runner(retained_argv), label=f"{label} result")
    except CurrentBankCloudOperatorV1Error:
        raise
    except Exception as exc:
        raise CurrentBankCloudOperatorV1Error(f"{label} subprocess is ambiguous") from exc
    if set(result) != {"returncode", "stdout", "stderr"}:
        _fail(f"{label} subprocess result fields differ")
    returncode = result.get("returncode")
    stdout = result.get("stdout")
    stderr = result.get("stderr")
    if (
        type(returncode) is not int
        or type(stdout) is not bytes
        or type(stderr) is not bytes
        or len(stdout) > stdout_ceiling
        or len(stderr) > MAXIMUM_SUBPROCESS_STDERR_BYTES
    ):
        _fail(f"{label} subprocess framing differs")
    if returncode != 0:
        _fail(f"{label} subprocess failed or is ambiguous")
    return stdout


def _run_json(
    runner: CommandRunner, argv: Sequence[str], *, label: str,
) -> dict[str, object]:
    raw = _run_checked(
        runner, argv, label=label, stdout_ceiling=MAXIMUM_PROVIDER_JSON_BYTES
    )
    return _strict_json(raw, label=f"{label} JSON")


def _condition_is_success(value: object) -> bool:
    if not isinstance(value, Mapping) or value.get("type") != "Completed":
        return False
    return (
        value.get("state") == "CONDITION_SUCCEEDED"
        or value.get("status") is True
        or value.get("status") == "True"
    )


def _provider_terminal_state(
    status_value: object, *, expected_count: int | None = None,
) -> str:
    status = _mapping(status_value, label="provider status")
    conditions = _sequence(status.get("conditions", []), label="provider conditions")
    completed = any(_condition_is_success(row) for row in conditions)
    completion_time = status.get("completionTime")
    failed = int(status.get("failedCount", 0) or 0)
    cancelled = int(status.get("cancelledCount", 0) or 0)
    succeeded = int(status.get("succeededCount", 0) or 0)
    if completed and completion_time and failed == 0 and cancelled == 0:
        if expected_count is None or succeeded == expected_count:
            return "SUCCEEDED"
    if completion_time or completed:
        return "FAILED"
    return "ACTIVE"


def _execution_identity_and_status(
    value: object, *, manifest: Mapping[str, object], expected_job_uid: str,
    expected_execution: str,
) -> dict[str, object]:
    item = _mapping(value, label="execution description")
    name, uid, generation, metadata = _metadata_name_uid_generation(
        item, kind="execution", pattern=_EXECUTION
    )
    labels = _mapping(metadata.get("labels", {}), label="execution labels")
    job = _short_resource_name(
        labels.get("run.googleapis.com/job"), label="execution job", pattern=_JOB
    )
    job_uid = _string(
        labels.get("run.googleapis.com/jobUid"),
        label="execution job UID", maximum=128,
    )
    count = _integer(
        manifest.get("task_count"), label="manifest task count", minimum=1,
        maximum=220,
    )
    if (
        name != expected_execution
        or job != manifest.get("reused_job_name")
        or job_uid != expected_job_uid
    ):
        _fail("execution name/job/UID differs")
    return {
        "execution_name": name,
        "execution_uid": uid,
        "execution_generation": generation,
        "terminal_state": _provider_terminal_state(
            item.get("status", {}), expected_count=count
        ),
        "raw": item,
    }


def _execution_task_template_v1(
    value: Mapping[str, object], *, manifest: Mapping[str, object],
    manifest_identity: object, image_uri: str,
) -> dict[str, object]:
    spec = _mapping(value.get("spec"), label="execution spec")
    count = _integer(
        manifest.get("task_count"), label="manifest task count", minimum=1,
        maximum=220,
    )
    template = _mapping(spec.get("template"), label="execution template")
    task = _mapping(template.get("spec"), label="execution task template")
    containers = _sequence(task.get("containers"), label="execution containers")
    if len(containers) != 1:
        _fail("execution container count differs")
    container = _mapping(containers[0], label="execution container")
    environment = _environment_rows(
        container.get("env", []), label="execution environment"
    )
    resources = _mapping(
        container.get("resources", {}), label="execution resources"
    )
    limits = _mapping(
        resources.get("limits", {}), label="execution resource limits"
    )
    timeout = str(task.get("timeoutSeconds", "")).removesuffix("s")
    configured_environment = configured_job_environment_v1(
        manifest=manifest, manifest_identity=manifest_identity
    )
    expected_environment = common_job_environment_v1(
        manifest=manifest, manifest_identity=manifest_identity
    )
    image = _image_uri(image_uri, manifest=manifest)
    if (
        spec.get("taskCount") != count
        or spec.get("parallelism") != count
        or task.get("maxRetries") != 0
        or not timeout.isdigit()
        or int(timeout) != TASK_TIMEOUT_SECONDS
        or container.get("image") != image
        or container.get("command", []) != [DISPATCHER_PYTHON]
        or container.get("args", []) != ["-I", DISPATCHER_SCRIPT]
        or environment != configured_environment
        or limits != {"cpu": CPU, "memory": MEMORY}
        or container.get("workingDir", "") != ""
        or container.get("volumeMounts", []) != []
        or task.get("volumes", []) != []
        or _network_attachment_present(value)
    ):
        _fail("execution inherited TaskTemplate differs from exact job projection")
    provider_container = {
        "image": manifest["image_digest"],
        "command": [DISPATCHER_PYTHON],
        "args": ["-I", DISPATCHER_SCRIPT],
        "environment": expected_environment,
        "working_dir": "",
        "volume_mounts": [],
        "resource_limits": {"cpu": CPU, "memory": MEMORY},
    }
    return {
        "containers": [provider_container],
        "maximum_task_retries": 0,
        "timeout_seconds": TASK_TIMEOUT_SECONDS,
        "volumes": [],
    }


def _task_status_v1(
    value: object, *, execution: str, task_index: int,
) -> dict[str, object]:
    item = _mapping(value, label=f"task[{task_index}] description")
    metadata = _mapping(item.get("metadata"), label=f"task[{task_index}] metadata")
    raw_name = _short_resource_name(
        metadata.get("name"), label=f"task[{task_index}] name", pattern=_TASK
    )
    expected_name = f"{execution}-task{task_index}"
    labels = _mapping(metadata.get("labels", {}), label=f"task[{task_index}] labels")
    raw_execution = labels.get("run.googleapis.com/execution")
    running_state = labels.get("run.googleapis.com/runningState")
    status = _mapping(item.get("status", {}), label=f"task[{task_index}] status")
    raw_index = status.get("index")
    raw_attempt = status.get("retried")
    if (
        raw_index is not None and type(raw_index) is not int
        or raw_attempt is not None and type(raw_attempt) is not int
    ):
        _fail("task index/attempt differs")
    index = task_index if raw_index is None else raw_index
    attempt = 0 if raw_attempt is None else raw_attempt
    state = _provider_terminal_state(status)
    last_attempt = status.get("lastAttemptResult", {})
    if not isinstance(last_attempt, Mapping):
        _fail("task last-attempt result differs")
    exit_code_raw = last_attempt.get(
        "exitCode", 0 if state == "SUCCEEDED" else 255
    )
    try:
        exit_code = int(exit_code_raw)
    except (TypeError, ValueError) as exc:
        raise CurrentBankCloudOperatorV1Error("task exit code differs") from exc
    allowed_running_states = {
        "SUCCEEDED": {None, "Succeeded"},
        "FAILED": {None, "Failed", "Cancelled", "Abandoned"},
        "ACTIVE": {None, "Pending", "Running"},
    }[state]
    if (
        raw_name != expected_name
        or raw_execution != execution
        or running_state not in allowed_running_states
        or index != task_index
        or attempt != 0
        or not 0 <= exit_code <= 255
    ):
        _fail("task index/attempt/exit code differs")
    return {
        "task_index": task_index,
        "task_name": f"{execution}/tasks/{task_index}",
        "attempt": 0,
        "terminal_state": state,
        "exit_code": exit_code,
        "condition": (
            {"type": "Completed", "state": "CONDITION_SUCCEEDED"}
            if state == "SUCCEEDED" else None
        ),
    }


def _open_manifest(
    manifest_identity: object, *, read_exact: ReadExact,
    manifest_opener: Callable[..., Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(manifest_identity, label="operator manifest identity")
    try:
        authority = _mapping(
            manifest_opener(identity, read_exact=read_exact),
            label="operator manifest authority",
        )
    except CurrentBankCloudOperatorV1Error:
        raise
    except Exception as exc:
        raise CurrentBankCloudOperatorV1Error(
            "operator manifest exact reopen failed"
        ) from exc
    manifest = _mapping(authority.get("manifest"), label="operator manifest")
    returned_identity = _identity(
        authority.get("manifest_identity"), label="reopened manifest identity"
    )
    if returned_identity != identity:
        _fail("reopened manifest identity differs")
    try:
        task_manifest.validate_task_manifest_v1(manifest)
    except task_manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error as exc:
        raise CurrentBankCloudOperatorV1Error(str(exc)) from exc
    return manifest, identity


def _assert_latest_not_active(
    job_identity: Mapping[str, object], *, runner: CommandRunner,
    manifest: Mapping[str, object], expected_job_uid: str,
) -> dict[str, object]:
    latest = job_identity.get("latest_execution_name")
    if latest is None:
        return _with_hash({
            "execution_name": None,
            "execution_uid": None,
            "execution_generation": None,
            "terminal_state": None,
            "reference_creation_timestamp": None,
            "reference_completion_timestamp": None,
            "reference_completion_status": None,
            "job_execution_count": job_identity.get("execution_count"),
        }, field="prelaunch_latest_execution_snapshot_sha256")
    execution = _run_json(
        runner, execution_describe_argv_v1(str(latest)),
        label="latest execution describe",
    )
    status = _execution_identity_and_status(
        execution,
        manifest=manifest,
        expected_job_uid=expected_job_uid,
        expected_execution=str(latest),
    )
    if status["terminal_state"] == "ACTIVE":
        _fail("reused job has an active execution")
    return _with_hash({
        "execution_name": status["execution_name"],
        "execution_uid": status["execution_uid"],
        "execution_generation": status["execution_generation"],
        "terminal_state": status["terminal_state"],
        "reference_creation_timestamp": job_identity[
            "latest_execution_reference"
        ]["creation_timestamp"],
        "reference_completion_timestamp": job_identity[
            "latest_execution_reference"
        ]["completion_timestamp"],
        "reference_completion_status": job_identity[
            "latest_execution_reference"
        ]["completion_status"],
        "job_execution_count": job_identity.get("execution_count"),
    }, field="prelaunch_latest_execution_snapshot_sha256")


def _write_flags_file_v1(path_value: str, flags: Mapping[str, object]) -> None:
    path = Path(path_value)
    if not path.is_absolute() or path.exists() or path.is_symlink():
        _fail("configuration flags path must be absent and absolute")
    raw = _canonical_bytes(flags) + b"\n"
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        FLAGS_FILE_MODE,
    )
    try:
        written = 0
        while written < len(raw):
            count = os.write(descriptor, raw[written:])
            if count < 1:
                _fail("configuration flags write made no progress")
            written += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    metadata = path.stat(follow_symlinks=False)
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != FLAGS_FILE_MODE
        or metadata.st_uid != os.geteuid()
        or path.read_bytes() != raw
    ):
        _fail("configuration flags file ownership/content differs")


def configure_layer_v1(
    *, manifest_identity: object, expected_job_uid: str, image_uri: str,
    flags_path: str, read_exact: ReadExact, runner: CommandRunner,
    flags_writer: Callable[[str, Mapping[str, object]], None] = _write_flags_file_v1,
    manifest_opener: Callable[..., Mapping[str, object]] = (
        task_manifest.reopen_task_manifest_authority_v1
    ),
) -> dict[str, object]:
    manifest, identity = _open_manifest(
        manifest_identity, read_exact=read_exact, manifest_opener=manifest_opener
    )
    image = _image_uri(image_uri, manifest=manifest)
    job = str(manifest["reused_job_name"])
    pre_description = _run_json(
        runner, job_describe_argv_v1(job), label="preconfigure job describe"
    )
    pre_identity = validate_job_identity_v1(
        pre_description, manifest=manifest, expected_job_uid=expected_job_uid
    )
    _assert_latest_not_active(
        pre_identity,
        runner=runner,
        manifest=manifest,
        expected_job_uid=expected_job_uid,
    )
    flags = configure_flags_v1(
        manifest=manifest, manifest_identity=identity, image_uri=image
    )
    flags_writer(flags_path, flags)
    argv = configure_argv_v1(job, flags_path=flags_path)
    _run_checked(
        runner, argv, label="job update", stdout_ceiling=MAXIMUM_PROVIDER_JSON_BYTES
    )
    post_description = _run_json(
        runner, job_describe_argv_v1(job), label="postconfigure job describe"
    )
    projection = validate_exact_job_projection_v1(
        post_description,
        manifest=manifest,
        manifest_identity=identity,
        expected_job_uid=expected_job_uid,
        image_uri=image,
    )
    body = {
        "schema_version": CONFIGURATION_RESULT_SCHEMA,
        "manifest_identity": identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "layer_id": manifest["layer_id"],
        "project_id": PROJECT,
        "location": REGION,
        "job_name": job,
        "job_uid": expected_job_uid,
        "configure_argv": argv,
        "configure_argv_sha256": _canonical_sha(argv),
        "configuration_flags_sha256": _canonical_sha(flags),
        "job_projection": projection,
        "job_projection_sha256": projection["job_projection_sha256"],
        "job_created": False,
        "exact_post_update_projection_validated": True,
    }
    return _with_hash(body, field="configuration_result_sha256")


def launch_intent_uri_v1(manifest: Mapping[str, object]) -> str:
    prefix = _string(
        manifest.get("output_prefix"), label="manifest output prefix", maximum=1_024
    )
    if not prefix.endswith("/"):
        _fail("manifest output prefix differs")
    ordinal = _integer(
        manifest.get("layer_ordinal"), label="manifest layer ordinal", maximum=99
    )
    layer = _string(manifest.get("layer_id"), label="manifest layer ID", maximum=64)
    return (
        f"{prefix}authorities/cloud-run-launch-intents/"
        f"{ordinal:02d}-{layer}.json"
    )


def launch_submission_marker_uri_v1(manifest: Mapping[str, object]) -> str:
    prefix = _string(
        manifest.get("output_prefix"), label="manifest output prefix", maximum=1_024
    )
    if not prefix.endswith("/"):
        _fail("manifest output prefix differs")
    ordinal = _integer(
        manifest.get("layer_ordinal"), label="manifest layer ordinal", maximum=99
    )
    layer = _string(manifest.get("layer_id"), label="manifest layer ID", maximum=64)
    return (
        f"{prefix}authorities/cloud-run-launch-submission-markers/"
        f"{ordinal:02d}-{layer}.json"
    )


def build_launch_intent_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    expected_job_uid: str, image_uri: str,
    job_projection: Mapping[str, object],
    prelaunch_latest_execution_snapshot: Mapping[str, object],
) -> dict[str, object]:
    identity = _identity(manifest_identity, label="launch manifest identity")
    image = _image_uri(image_uri, manifest=manifest)
    projection = _mapping(job_projection, label="launch job projection")
    snapshot = _mapping(
        prelaunch_latest_execution_snapshot,
        label="prelaunch latest-execution snapshot",
    )
    _require_self_hash_v1(
        snapshot,
        field="prelaunch_latest_execution_snapshot_sha256",
        label="prelaunch latest-execution snapshot",
    )
    if snapshot.get("job_execution_count") != projection.get("execution_count"):
        _fail("prelaunch latest-execution count differs from job projection")
    body = {
        "schema_version": LAUNCH_INTENT_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "manifest_identity": identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "layer_ordinal": manifest["layer_ordinal"],
        "layer_id": manifest["layer_id"],
        "project_id": PROJECT,
        "location": REGION,
        "job_name": manifest["reused_job_name"],
        "job_uid": expected_job_uid,
        "image_uri": image,
        "image_digest": manifest["image_digest"],
        "prelaunch_job_generation": projection.get("job_generation"),
        "job_projection_sha256": projection.get("job_projection_sha256"),
        "prelaunch_latest_execution_snapshot": snapshot,
        "prelaunch_latest_execution_snapshot_sha256": snapshot[
            "prelaunch_latest_execution_snapshot_sha256"
        ],
        "launch_submission_marker_uri": launch_submission_marker_uri_v1(manifest),
        "execute_argv": execute_argv_v1(str(manifest["reused_job_name"])),
        "execute_has_no_run_job_overrides": True,
        "submission_mode": "async-single-request",
        "maximum_submission_calls": 1,
        "request_consumed_on_ambiguous_submission": True,
        "blind_relaunch_allowed": False,
        "recovery_allowed": True,
        "crash_after_marker_before_execute_requires_fresh_prefix": True,
        "uses_realized_outcomes": False,
        "scientific_output_inspection_allowed": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _with_hash(body, field="launch_intent_sha256")


def _validate_prelaunch_snapshot_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="prelaunch latest-execution snapshot")
    expected = {
        "execution_name", "execution_uid", "execution_generation",
        "terminal_state", "reference_creation_timestamp",
        "reference_completion_timestamp", "reference_completion_status",
        "job_execution_count",
        "prelaunch_latest_execution_snapshot_sha256",
    }
    if set(item) != expected:
        _fail("prelaunch latest-execution snapshot fields differ")
    _require_self_hash_v1(
        item,
        field="prelaunch_latest_execution_snapshot_sha256",
        label="prelaunch latest-execution snapshot",
    )
    count = item.get("job_execution_count")
    if type(count) is not int or count < 0:
        _fail("prelaunch latest-execution count differs")
    name = item.get("execution_name")
    if name is None:
        if any(item[field] is not None for field in (
            "execution_uid", "execution_generation", "terminal_state",
            "reference_creation_timestamp", "reference_completion_timestamp",
            "reference_completion_status",
        )):
            _fail("absent prelaunch latest-execution snapshot differs")
    else:
        _short_resource_name(
            name, label="prelaunch execution name", pattern=_EXECUTION
        )
        _string(item.get("execution_uid"), label="prelaunch execution UID", maximum=128)
        generation = _string(
            item.get("execution_generation"),
            label="prelaunch execution generation",
            maximum=31,
        )
        if not generation.isdigit() or int(generation) < 1:
            _fail("prelaunch execution generation differs")
        if item.get("terminal_state") not in {"SUCCEEDED", "FAILED"}:
            _fail("prelaunch execution was not terminal")
        for field in (
            "reference_creation_timestamp", "reference_completion_timestamp",
            "reference_completion_status",
        ):
            if item.get(field) is not None:
                _string(item[field], label=f"prelaunch {field}", maximum=128)
    return item


def validate_launch_intent_v1(
    value: object, *, manifest: Mapping[str, object],
    manifest_identity: object, expected_job_uid: str, image_uri: str,
) -> dict[str, object]:
    item = _mapping(value, label="launch intent")
    expected = {
        "schema_version", "contract_id", "manifest_identity",
        "task_manifest_sha256", "layer_ordinal", "layer_id", "project_id",
        "location", "job_name", "job_uid", "image_uri", "image_digest",
        "prelaunch_job_generation", "job_projection_sha256",
        "prelaunch_latest_execution_snapshot",
        "prelaunch_latest_execution_snapshot_sha256",
        "launch_submission_marker_uri",
        "execute_argv", "execute_has_no_run_job_overrides", "submission_mode",
        "maximum_submission_calls", "request_consumed_on_ambiguous_submission",
        "blind_relaunch_allowed", "recovery_allowed",
        "crash_after_marker_before_execute_requires_fresh_prefix",
        "uses_realized_outcomes",
        "scientific_output_inspection_allowed", "policy", "launch_intent_sha256",
    }
    if set(item) != expected:
        _fail("launch intent fields differ")
    _require_self_hash_v1(item, field="launch_intent_sha256", label="launch intent")
    identity = _identity(manifest_identity, label="launch intent manifest identity")
    image = _image_uri(image_uri, manifest=manifest)
    snapshot = _validate_prelaunch_snapshot_v1(
        item.get("prelaunch_latest_execution_snapshot")
    )
    if (
        item.get("schema_version") != LAUNCH_INTENT_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("manifest_identity") != identity
        or item.get("task_manifest_sha256") != manifest.get("task_manifest_sha256")
        or item.get("layer_ordinal") != manifest.get("layer_ordinal")
        or item.get("layer_id") != manifest.get("layer_id")
        or item.get("project_id") != PROJECT
        or item.get("location") != REGION
        or item.get("job_name") != manifest.get("reused_job_name")
        or item.get("job_uid") != expected_job_uid
        or item.get("image_uri") != image
        or item.get("image_digest") != manifest.get("image_digest")
        or type(item.get("prelaunch_job_generation")) is not str
        or not str(item.get("prelaunch_job_generation")).isdigit()
        or type(item.get("job_projection_sha256")) is not str
        or _SHA.fullmatch(str(item.get("job_projection_sha256"))) is None
        or item.get("prelaunch_latest_execution_snapshot_sha256")
        != snapshot["prelaunch_latest_execution_snapshot_sha256"]
        or item.get("launch_submission_marker_uri")
        != launch_submission_marker_uri_v1(manifest)
        or item.get("execute_argv")
        != execute_argv_v1(str(manifest["reused_job_name"]))
        or item.get("execute_has_no_run_job_overrides") is not True
        or item.get("submission_mode") != "async-single-request"
        or item.get("maximum_submission_calls") != 1
        or item.get("request_consumed_on_ambiguous_submission") is not True
        or item.get("blind_relaunch_allowed") is not False
        or item.get("recovery_allowed") is not True
        or item.get("crash_after_marker_before_execute_requires_fresh_prefix")
        is not True
        or item.get("uses_realized_outcomes") is not False
        or item.get("scientific_output_inspection_allowed") is not False
        or item.get("policy") != contract.POLICY_CLAIMS
    ):
        _fail("launch intent fixed authority differs")
    return item


def _build_launch_result_body_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    launch_intent: Mapping[str, object], launch_intent_identity: object,
    postlaunch_job_projection: Mapping[str, object],
    execution_identity: Mapping[str, object],
    provider_execution_task_template: Mapping[str, object],
) -> dict[str, object]:
    identity = _identity(manifest_identity, label="launch-result manifest identity")
    intent_identity = _identity(
        launch_intent_identity, label="launch-result intent identity"
    )
    snapshot = _validate_prelaunch_snapshot_v1(
        launch_intent.get("prelaunch_latest_execution_snapshot")
    )
    projection = _mapping(
        postlaunch_job_projection, label="postlaunch job projection"
    )
    execution = _mapping(execution_identity, label="launched execution identity")
    template = _mapping(
        provider_execution_task_template,
        label="launched execution inherited TaskTemplate",
    )
    marker = _build_launch_submission_marker_v1(
        manifest=manifest,
        manifest_identity=identity,
        launch_intent=launch_intent,
        launch_intent_identity=intent_identity,
    )
    expected_count = int(snapshot["job_execution_count"]) + 1
    if (
        projection.get("execution_count") != expected_count
        or projection.get("latest_execution_name") != execution.get("execution_name")
        or execution.get("terminal_state") not in {"ACTIVE", "SUCCEEDED", "FAILED"}
    ):
        _fail("postlaunch execution is not the sole changed job execution")
    body = {
        "schema_version": LAUNCH_RESULT_SCHEMA,
        "manifest_identity": identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "layer_id": manifest["layer_id"],
        "launch_intent_identity": intent_identity,
        "launch_intent_sha256": launch_intent["launch_intent_sha256"],
        "launch_submission_marker_uri": launch_submission_marker_uri_v1(manifest),
        "launch_submission_marker_sha256": marker[
            "launch_submission_marker_sha256"
        ],
        "prelaunch_latest_execution_snapshot": snapshot,
        "prelaunch_latest_execution_snapshot_sha256": snapshot[
            "prelaunch_latest_execution_snapshot_sha256"
        ],
        "postlaunch_job_generation": projection["job_generation"],
        "postlaunch_job_execution_count": projection["execution_count"],
        "postlaunch_latest_execution_name": projection["latest_execution_name"],
        "cloud_execution_name": execution["execution_name"],
        "cloud_execution_uid": execution["execution_uid"],
        "cloud_execution_generation": execution["execution_generation"],
        "cloud_execution_state_at_capture": execution["terminal_state"],
        "provider_execution_task_template": template,
        "provider_execution_task_template_sha256": _canonical_sha(template),
        "execute_argv": execute_argv_v1(str(manifest["reused_job_name"])),
        "execute_argv_sha256": _canonical_sha(
            execute_argv_v1(str(manifest["reused_job_name"]))
        ),
        "submission_async": True,
        "run_job_overrides_present": False,
        "submission_call_count": 1,
        "launch_request_consumed": True,
        "blind_relaunch_allowed": False,
        "canonical_result_independent_of_capture_path": True,
        "persistent_launch_result_object_created": False,
    }
    return _with_hash(body, field="launch_result_sha256")


def validate_launch_result_v1(
    value: object, *, manifest: Mapping[str, object], manifest_identity: object,
    launch_intent: Mapping[str, object], launch_intent_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="launch result")
    expected = {
        "schema_version", "manifest_identity", "task_manifest_sha256", "layer_id",
        "launch_intent_identity", "launch_intent_sha256",
        "launch_submission_marker_uri", "launch_submission_marker_sha256",
        "prelaunch_latest_execution_snapshot",
        "prelaunch_latest_execution_snapshot_sha256",
        "postlaunch_job_generation", "postlaunch_job_execution_count",
        "postlaunch_latest_execution_name", "cloud_execution_name",
        "cloud_execution_uid", "cloud_execution_generation",
        "cloud_execution_state_at_capture", "provider_execution_task_template",
        "provider_execution_task_template_sha256", "execute_argv",
        "execute_argv_sha256", "submission_async", "run_job_overrides_present",
        "submission_call_count", "launch_request_consumed",
        "blind_relaunch_allowed", "canonical_result_independent_of_capture_path",
        "persistent_launch_result_object_created",
        "launch_result_sha256",
    }
    if set(item) != expected:
        _fail("launch result fields differ")
    _require_self_hash_v1(item, field="launch_result_sha256", label="launch result")
    identity = _identity(manifest_identity, label="launch-result manifest identity")
    intent_identity = _identity(
        launch_intent_identity, label="launch-result intent identity"
    )
    snapshot = _validate_prelaunch_snapshot_v1(
        item.get("prelaunch_latest_execution_snapshot")
    )
    marker = _build_launch_submission_marker_v1(
        manifest=manifest,
        manifest_identity=identity,
        launch_intent=launch_intent,
        launch_intent_identity=intent_identity,
    )
    execution_name = _short_resource_name(
        item.get("cloud_execution_name"),
        label="launch-result execution name",
        pattern=_EXECUTION,
    )
    execution_uid = _string(
        item.get("cloud_execution_uid"), label="launch-result execution UID",
        maximum=128,
    )
    execution_generation = _string(
        item.get("cloud_execution_generation"),
        label="launch-result execution generation",
        maximum=31,
    )
    expected_template = {
        "containers": [{
            "image": manifest["image_digest"],
            "command": [DISPATCHER_PYTHON],
            "args": ["-I", DISPATCHER_SCRIPT],
            "environment": common_job_environment_v1(
                manifest=manifest, manifest_identity=identity
            ),
            "working_dir": "",
            "volume_mounts": [],
            "resource_limits": {"cpu": CPU, "memory": MEMORY},
        }],
        "maximum_task_retries": 0,
        "timeout_seconds": TASK_TIMEOUT_SECONDS,
        "volumes": [],
    }
    template = _mapping(
        item.get("provider_execution_task_template"),
        label="launch-result provider template",
    )
    expected_count = int(snapshot["job_execution_count"]) + 1
    previous_name = snapshot["execution_name"]
    if (
        item.get("schema_version") != LAUNCH_RESULT_SCHEMA
        or item.get("manifest_identity") != identity
        or item.get("task_manifest_sha256") != manifest.get("task_manifest_sha256")
        or item.get("layer_id") != manifest.get("layer_id")
        or item.get("launch_intent_identity") != intent_identity
        or item.get("launch_intent_sha256")
        != launch_intent.get("launch_intent_sha256")
        or item.get("launch_submission_marker_uri")
        != launch_submission_marker_uri_v1(manifest)
        or item.get("launch_submission_marker_sha256")
        != marker["launch_submission_marker_sha256"]
        or item.get("prelaunch_latest_execution_snapshot_sha256")
        != snapshot["prelaunch_latest_execution_snapshot_sha256"]
        or item.get("postlaunch_job_generation")
        != launch_intent.get("prelaunch_job_generation")
        or item.get("postlaunch_job_execution_count") != expected_count
        or item.get("postlaunch_latest_execution_name") != execution_name
        or execution_name == previous_name
        or not execution_name.startswith(str(manifest["reused_job_name"]) + "-")
        or _UID.fullmatch(execution_uid) is None
        or not execution_generation.isdigit()
        or int(execution_generation) < 1
        or item.get("cloud_execution_state_at_capture")
        not in {"ACTIVE", "SUCCEEDED", "FAILED"}
        or template != expected_template
        or item.get("provider_execution_task_template_sha256")
        != _canonical_sha(template)
        or item.get("execute_argv")
        != execute_argv_v1(str(manifest["reused_job_name"]))
        or item.get("execute_argv_sha256") != _canonical_sha(item["execute_argv"])
        or item.get("submission_async") is not True
        or item.get("run_job_overrides_present") is not False
        or item.get("submission_call_count") != 1
        or item.get("launch_request_consumed") is not True
        or item.get("blind_relaunch_allowed") is not False
        or item.get("canonical_result_independent_of_capture_path") is not True
        or item.get("persistent_launch_result_object_created") is not False
    ):
        _fail("launch result authority differs")
    return item


def _launch_operation_envelope_v1(
    *, launch_result: Mapping[str, object], recovered: bool,
) -> dict[str, object]:
    result = _mapping(launch_result, label="launch operation result")
    body = {
        "schema_version": LAUNCH_OPERATION_RESULT_SCHEMA,
        "launch_result": result,
        "launch_result_sha256": result["launch_result_sha256"],
        "recovered_without_resubmission": recovered,
        "persistence": "exclusive-local-fsync-only",
        "persistent_cloud_result_created": False,
    }
    return _with_hash(body, field="launch_operation_result_sha256")


def _capture_launch_job_state_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    expected_job_uid: str, image_uri: str, runner: CommandRunner,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    job = str(manifest["reused_job_name"])
    description = _run_json(
        runner, job_describe_argv_v1(job), label=f"{label} job describe"
    )
    projection = validate_exact_job_projection_v1(
        description,
        manifest=manifest,
        manifest_identity=manifest_identity,
        expected_job_uid=expected_job_uid,
        image_uri=image_uri,
    )
    snapshot = _assert_latest_not_active(
        projection,
        runner=runner,
        manifest=manifest,
        expected_job_uid=expected_job_uid,
    )
    return projection, snapshot


def _capture_current_job_projection_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    expected_job_uid: str, image_uri: str, runner: CommandRunner, label: str,
) -> dict[str, object]:
    description = _run_json(
        runner,
        job_describe_argv_v1(str(manifest["reused_job_name"])),
        label=f"{label} job describe",
    )
    return validate_exact_job_projection_v1(
        description,
        manifest=manifest,
        manifest_identity=manifest_identity,
        expected_job_uid=expected_job_uid,
        image_uri=image_uri,
    )


def arm_launch_v1(
    *, manifest_identity: object, expected_job_uid: str, image_uri: str,
    read_exact: ReadExact, publish_create_once: PublishCreateOnce,
    runner: CommandRunner,
    manifest_opener: Callable[..., Mapping[str, object]] = (
        task_manifest.reopen_task_manifest_authority_v1
    ),
) -> dict[str, object]:
    """Publish and return the exact launch intent without submitting a job."""
    manifest, identity = _open_manifest(
        manifest_identity, read_exact=read_exact, manifest_opener=manifest_opener
    )
    image = _image_uri(image_uri, manifest=manifest)
    projection, snapshot = _capture_launch_job_state_v1(
        manifest=manifest,
        manifest_identity=identity,
        expected_job_uid=expected_job_uid,
        image_uri=image,
        runner=runner,
        label="arm-launch",
    )
    intent = build_launch_intent_v1(
        manifest=manifest,
        manifest_identity=identity,
        expected_job_uid=expected_job_uid,
        image_uri=image,
        job_projection=projection,
        prelaunch_latest_execution_snapshot=snapshot,
    )
    try:
        intent_identity = task_manifest.publish_create_once_or_exact_prior_v1(
            uri=launch_intent_uri_v1(manifest),
            value=intent,
            prior_identity=None,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
            maximum_bytes=MAXIMUM_LAUNCH_INTENT_BYTES,
        )
    except Exception as exc:
        raise CurrentBankCloudOperatorV1Error(
            "arm-launch intent create/reopen is ambiguous or already exists"
        ) from exc
    body = {
        "schema_version": ARM_LAUNCH_RESULT_SCHEMA,
        "manifest_identity": identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "layer_id": manifest["layer_id"],
        "launch_intent_identity": intent_identity,
        "launch_intent_sha256": intent["launch_intent_sha256"],
        "submission_call_count": 0,
        "launch_armed": True,
        "caller_must_preserve_exact_intent_identity_before_submission": True,
    }
    return _with_hash(body, field="arm_launch_result_sha256")


def _reopen_launch_intent_v1(
    *, launch_intent_identity: object, read_exact: ReadExact,
    manifest: Mapping[str, object], manifest_identity: object,
    expected_job_uid: str, image_uri: str,
) -> tuple[dict[str, object], dict[str, object]]:
    raw, identity = _read_exact_identity_bytes_v1(
        launch_intent_identity,
        read_exact=read_exact,
        maximum_bytes=MAXIMUM_LAUNCH_INTENT_BYTES,
        label="exact launch intent",
    )
    if identity["uri"] != launch_intent_uri_v1(manifest):
        _fail("exact launch intent URI differs")
    intent = validate_launch_intent_v1(
        _strict_json(raw, label="exact launch intent"),
        manifest=manifest,
        manifest_identity=manifest_identity,
        expected_job_uid=expected_job_uid,
        image_uri=image_uri,
    )
    return intent, identity


def _build_launch_submission_marker_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    launch_intent: Mapping[str, object], launch_intent_identity: object,
) -> dict[str, object]:
    identity = _identity(manifest_identity, label="submission-marker manifest identity")
    intent_identity = _identity(
        launch_intent_identity, label="submission-marker intent identity"
    )
    argv = execute_argv_v1(str(manifest["reused_job_name"]))
    body = {
        "schema_version": LAUNCH_SUBMISSION_MARKER_SCHEMA,
        "manifest_identity": identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "layer_id": manifest["layer_id"],
        "launch_intent_identity": intent_identity,
        "launch_intent_sha256": launch_intent["launch_intent_sha256"],
        "launch_submission_marker_uri": launch_submission_marker_uri_v1(manifest),
        "execute_argv": argv,
        "execute_argv_sha256": _canonical_sha(argv),
        "submission_call_ordinal": 1,
        "maximum_submission_calls": 1,
        "marker_created_before_execute": True,
        "run_job_overrides_present": False,
        "blind_relaunch_allowed": False,
        "uses_realized_outcomes": False,
        "scientific_output_inspection_allowed": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    return _with_hash(body, field="launch_submission_marker_sha256")


def _validate_launch_submission_marker_v1(
    value: object, *, manifest: Mapping[str, object], manifest_identity: object,
    launch_intent: Mapping[str, object], launch_intent_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="launch submission marker")
    expected = {
        "schema_version", "manifest_identity", "task_manifest_sha256", "layer_id",
        "launch_intent_identity", "launch_intent_sha256",
        "launch_submission_marker_uri", "execute_argv", "execute_argv_sha256",
        "submission_call_ordinal", "maximum_submission_calls",
        "marker_created_before_execute", "run_job_overrides_present",
        "blind_relaunch_allowed", "uses_realized_outcomes",
        "scientific_output_inspection_allowed", "policy",
        "launch_submission_marker_sha256",
    }
    if set(item) != expected:
        _fail("launch submission marker fields differ")
    _require_self_hash_v1(
        item,
        field="launch_submission_marker_sha256",
        label="launch submission marker",
    )
    expected_marker = _build_launch_submission_marker_v1(
        manifest=manifest,
        manifest_identity=manifest_identity,
        launch_intent=launch_intent,
        launch_intent_identity=launch_intent_identity,
    )
    if item != expected_marker:
        _fail("launch submission marker authority differs")
    return item


def _consume_launch_submission_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    launch_intent: Mapping[str, object], launch_intent_identity: object,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    marker = _build_launch_submission_marker_v1(
        manifest=manifest,
        manifest_identity=manifest_identity,
        launch_intent=launch_intent,
        launch_intent_identity=launch_intent_identity,
    )
    raw = _canonical_bytes(marker)
    if len(raw) > MAXIMUM_LAUNCH_SUBMISSION_MARKER_BYTES:
        _fail("launch submission marker exceeds byte ceiling")
    try:
        supplied_identity = publish_create_once(
            launch_submission_marker_uri_v1(manifest), raw
        )
    except Exception as exc:
        raise CurrentBankCloudOperatorV1Error(
            "launch submission is already consumed or marker publication is ambiguous; "
            "blind relaunch is forbidden"
        ) from exc
    marker_identity = _identity(
        supplied_identity, label="launch submission marker identity"
    )
    if (
        marker_identity["uri"] != launch_submission_marker_uri_v1(manifest)
        or marker_identity["bytes"] != len(raw)
        or marker_identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail("launch submission marker publication differs")
    _validate_launch_submission_marker_v1(
        marker,
        manifest=manifest,
        manifest_identity=manifest_identity,
        launch_intent=launch_intent,
        launch_intent_identity=launch_intent_identity,
    )
    return marker


def _capture_launched_execution_v1(
    *, execution_name: str, manifest: Mapping[str, object],
    manifest_identity: object, expected_job_uid: str, image_uri: str,
    runner: CommandRunner,
) -> tuple[dict[str, object], dict[str, object]]:
    raw_execution = _run_json(
        runner,
        execution_describe_argv_v1(execution_name),
        label="launched execution describe",
    )
    execution = _execution_identity_and_status(
        raw_execution,
        manifest=manifest,
        expected_job_uid=expected_job_uid,
        expected_execution=execution_name,
    )
    template = _execution_task_template_v1(
        raw_execution,
        manifest=manifest,
        manifest_identity=manifest_identity,
        image_uri=image_uri,
    )
    return execution, template


def launch_layer_v1(
    *, manifest_identity: object, expected_job_uid: str, image_uri: str,
    launch_intent_identity: object, read_exact: ReadExact,
    publish_create_once: PublishCreateOnce, runner: CommandRunner,
    manifest_opener: Callable[..., Mapping[str, object]] = (
        task_manifest.reopen_task_manifest_authority_v1
    ),
) -> dict[str, object]:
    """Submit exactly once from a caller-preserved, generation-pinned intent."""
    manifest, identity = _open_manifest(
        manifest_identity, read_exact=read_exact, manifest_opener=manifest_opener
    )
    image = _image_uri(image_uri, manifest=manifest)
    intent, intent_identity = _reopen_launch_intent_v1(
        launch_intent_identity=launch_intent_identity,
        read_exact=read_exact,
        manifest=manifest,
        manifest_identity=identity,
        expected_job_uid=expected_job_uid,
        image_uri=image,
    )
    projection, snapshot = _capture_launch_job_state_v1(
        manifest=manifest,
        manifest_identity=identity,
        expected_job_uid=expected_job_uid,
        image_uri=image,
        runner=runner,
        label="submit-launch preflight",
    )
    if (
        projection["job_projection_sha256"] != intent["job_projection_sha256"]
        or snapshot != intent["prelaunch_latest_execution_snapshot"]
    ):
        _fail("armed launch state changed before submission")
    job = str(manifest["reused_job_name"])
    argv = execute_argv_v1(job)
    _consume_launch_submission_v1(
        manifest=manifest,
        manifest_identity=identity,
        launch_intent=intent,
        launch_intent_identity=intent_identity,
        publish_create_once=publish_create_once,
    )
    try:
        raw_execution = _run_checked(
            runner,
            argv,
            label="async execution submission",
            stdout_ceiling=MAXIMUM_SUBMISSION_STDOUT_BYTES,
        )
        decoded = raw_execution.decode("utf-8", errors="strict").strip()
        if not decoded or "\n" in decoded or "\r" in decoded:
            _fail("async execution response framing differs")
        execution = _short_resource_name(
            decoded, label="submitted execution", pattern=_EXECUTION
        )
        if not execution.startswith(job + "-"):
            _fail("submitted execution is not owned by the reused job")
    except Exception as exc:
        raise CurrentBankCloudOperatorV1Error(
            "async submission is ambiguous; the preserved launch-intent "
            "identity is consumed and blind relaunch is forbidden"
        ) from exc
    try:
        post_projection = _capture_current_job_projection_v1(
            manifest=manifest,
            manifest_identity=identity,
            expected_job_uid=expected_job_uid,
            image_uri=image,
            runner=runner,
            label="submit-launch postflight",
        )
        if (
            post_projection["job_generation"]
            != intent["prelaunch_job_generation"]
            or post_projection["latest_execution_name"] != execution
        ):
            _fail("submitted execution is not the exact changed latest execution")
        execution_identity, template = _capture_launched_execution_v1(
            execution_name=execution,
            manifest=manifest,
            manifest_identity=identity,
            expected_job_uid=expected_job_uid,
            image_uri=image,
            runner=runner,
        )
        result = _build_launch_result_body_v1(
            manifest=manifest,
            manifest_identity=identity,
            launch_intent=intent,
            launch_intent_identity=intent_identity,
            postlaunch_job_projection=post_projection,
            execution_identity=execution_identity,
            provider_execution_task_template=template,
        )
        validate_launch_result_v1(
            result,
            manifest=manifest,
            manifest_identity=identity,
            launch_intent=intent,
            launch_intent_identity=intent_identity,
        )
        return _launch_operation_envelope_v1(
            launch_result=result,
            recovered=False,
        )
    except Exception as exc:
        if isinstance(exc, CurrentBankCloudOperatorV1Error):
            message = str(exc)
        else:
            message = "provider/postpublication boundary failed"
        raise CurrentBankCloudOperatorV1Error(
            "submission was consumed after provider acceptance; recover-launch "
            f"must use the preserved intent identity ({message})"
        ) from exc


def recover_launch_v1(
    *, manifest_identity: object, expected_job_uid: str, image_uri: str,
    launch_intent_identity: object, read_exact: ReadExact, runner: CommandRunner,
    manifest_opener: Callable[..., Mapping[str, object]] = (
        task_manifest.reopen_task_manifest_authority_v1
    ),
) -> dict[str, object]:
    """Recover one consumed launch without submitting or resolving control heads."""
    manifest, identity = _open_manifest(
        manifest_identity, read_exact=read_exact, manifest_opener=manifest_opener
    )
    image = _image_uri(image_uri, manifest=manifest)
    intent, intent_identity = _reopen_launch_intent_v1(
        launch_intent_identity=launch_intent_identity,
        read_exact=read_exact,
        manifest=manifest,
        manifest_identity=identity,
        expected_job_uid=expected_job_uid,
        image_uri=image,
    )
    projection = _capture_current_job_projection_v1(
        manifest=manifest,
        manifest_identity=identity,
        expected_job_uid=expected_job_uid,
        image_uri=image,
        runner=runner,
        label="recover-launch",
    )
    snapshot = _validate_prelaunch_snapshot_v1(
        intent["prelaunch_latest_execution_snapshot"]
    )
    expected_count = int(snapshot["job_execution_count"]) + 1
    execution = projection.get("latest_execution_name")
    if (
        projection.get("job_generation") != intent.get("prelaunch_job_generation")
        or projection.get("execution_count") != expected_count
        or type(execution) is not str
        or execution == snapshot.get("execution_name")
        or not execution.startswith(str(manifest["reused_job_name"]) + "-")
    ):
        _fail(
            "recover-launch cannot prove exactly one changed job execution; "
            "if the host stopped after marker creation but before execute, a fresh "
            "output prefix and newly armed run are required"
        )
    execution_identity, template = _capture_launched_execution_v1(
        execution_name=execution,
        manifest=manifest,
        manifest_identity=identity,
        expected_job_uid=expected_job_uid,
        image_uri=image,
        runner=runner,
    )
    result = _build_launch_result_body_v1(
        manifest=manifest,
        manifest_identity=identity,
        launch_intent=intent,
        launch_intent_identity=intent_identity,
        postlaunch_job_projection=projection,
        execution_identity=execution_identity,
        provider_execution_task_template=template,
    )
    validate_launch_result_v1(
        result,
        manifest=manifest,
        manifest_identity=identity,
        launch_intent=intent,
        launch_intent_identity=intent_identity,
    )
    return _launch_operation_envelope_v1(
        launch_result=result,
        recovered=True,
    )


def collect_status_v1(
    *, manifest_identity: object, expected_job_uid: str, image_uri: str,
    execution_name: str, read_exact: ReadExact, runner: CommandRunner,
    manifest_opener: Callable[..., Mapping[str, object]] = (
        task_manifest.reopen_task_manifest_authority_v1
    ),
) -> dict[str, object]:
    """Describe exactly one execution and its manifest-known task resources."""
    manifest, identity = _open_manifest(
        manifest_identity, read_exact=read_exact, manifest_opener=manifest_opener
    )
    image = _image_uri(image_uri, manifest=manifest)
    execution = _short_resource_name(
        execution_name, label="status execution", pattern=_EXECUTION
    )
    if not execution.startswith(str(manifest["reused_job_name"]) + "-"):
        _fail("status execution is not owned by the reused job")
    raw_execution = _run_json(
        runner,
        execution_describe_argv_v1(execution),
        label="status execution describe",
    )
    execution_identity = _execution_identity_and_status(
        raw_execution,
        manifest=manifest,
        expected_job_uid=expected_job_uid,
        expected_execution=execution,
    )
    provider_template = _execution_task_template_v1(
        raw_execution,
        manifest=manifest,
        manifest_identity=identity,
        image_uri=image,
    )
    task_count = int(manifest["task_count"])
    tasks: list[dict[str, object]] = []
    for index in range(task_count):
        raw_task = _run_json(
            runner,
            task_describe_argv_v1(
                job=str(manifest["reused_job_name"]),
                execution=execution,
                task_index=index,
            ),
            label=f"status task[{index}] describe",
        )
        tasks.append(
            _task_status_v1(raw_task, execution=execution, task_index=index)
        )
    all_terminal = all(row["terminal_state"] != "ACTIVE" for row in tasks)
    all_succeeded = (
        execution_identity["terminal_state"] == "SUCCEEDED"
        and all(row["terminal_state"] == "SUCCEEDED" for row in tasks)
        and all(row["exit_code"] == 0 for row in tasks)
    )
    body = {
        "schema_version": STATUS_SCHEMA,
        "manifest_identity": identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "layer_id": manifest["layer_id"],
        "project_id": PROJECT,
        "location": REGION,
        "job_name": manifest["reused_job_name"],
        "job_uid": expected_job_uid,
        "image_uri": image,
        "execution_name": execution,
        "execution_uid": execution_identity["execution_uid"],
        "execution_generation": execution_identity["execution_generation"],
        "execution_terminal_state": execution_identity["terminal_state"],
        "provider_execution_task_template": provider_template,
        "provider_execution_task_template_sha256": _canonical_sha(
            provider_template
        ),
        "provider_run_job_overrides": {
            "container_overrides": [],
            "task_count": None,
            "timeout_seconds": None,
        },
        "task_count": task_count,
        "task_statuses": tasks,
        "task_statuses_sha256": _canonical_sha(tasks),
        "all_tasks_terminal": all_terminal,
        "all_tasks_succeeded": all_succeeded,
        "logs_read": False,
        "scientific_outputs_read": False,
        "realized_outcomes_read": False,
    }
    return _with_hash(body, field="status_sha256")


def _terminal_records_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    open_known: OpenKnown,
) -> list[dict[str, object]]:
    identity = _identity(manifest_identity, label="terminal manifest identity")
    records: list[dict[str, object]] = []
    bindings = _sequence(
        manifest.get("task_bindings"), label="manifest task bindings"
    )
    if len(bindings) != manifest.get("task_count"):
        _fail("manifest task binding count differs")
    for index, raw_binding in enumerate(bindings):
        binding = _mapping(raw_binding, label=f"manifest task binding[{index}]")
        uri = _string(
            binding.get("task_terminal_evidence_uri"),
            label=f"task[{index}] terminal URI",
            maximum=1_024,
        )
        opened = open_known(uri, task_manifest.MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES)
        if (
            not isinstance(opened, tuple)
            or len(opened) != 2
            or type(opened[0]) is not bytes
        ):
            _fail(f"task[{index}] exact known opener differs")
        raw, supplied_identity = opened
        evidence_identity = _identity(
            supplied_identity, label=f"task[{index}] terminal identity"
        )
        if (
            evidence_identity["uri"] != uri
            or evidence_identity["bytes"] != len(raw)
            or evidence_identity["sha256"] != sha256(raw).hexdigest()
            or len(raw) > task_manifest.MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES
        ):
            _fail(f"task[{index}] terminal exact-open identity differs")
        evidence = _strict_json(raw, label=f"task[{index}] terminal evidence")
        try:
            retained = task_manifest.validate_task_terminal_evidence_v1(
                evidence,
                manifest=manifest,
                manifest_identity=identity,
            )
        except task_manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error as exc:
            raise CurrentBankCloudOperatorV1Error(str(exc)) from exc
        if retained.get("task_index") != index:
            _fail(f"task[{index}] terminal evidence index differs")
        records.append({"identity": evidence_identity, "evidence": retained})
    return records


def _task_terminal_generation_resolution_scope_v1(
    manifest: Mapping[str, object],
) -> dict[str, object]:
    bindings = _sequence(
        manifest.get("task_bindings"),
        label="terminal generation-resolution task bindings",
    )
    uris = [
        _string(
            _mapping(
                row, label=f"terminal generation binding[{index}]"
            ).get("task_terminal_evidence_uri"),
            label=f"terminal generation URI[{index}]",
            maximum=2_048,
        )
        for index, row in enumerate(bindings)
    ]
    if (
        not uris
        or len(set(uris)) != len(uris)
        or len(uris) != manifest.get("task_count")
    ):
        _fail("terminal generation-resolution URI ledger differs")
    return {
        "resolver_role": "host-finalizer-only",
        "uri_source": "exact-manifest-task-terminal-evidence-uris",
        "resolved_uri_count": len(uris),
        "resolved_uris_sha256": _canonical_sha(uris),
        "current_generation_metadata_lookup_per_uri": 1,
        "immediate_generation_pin_required": True,
        "generation_exact_hash_read_required": True,
        "listing_allowed": False,
        "logs_allowed": False,
        "scientific_output_resolution_allowed": False,
        "current_generation_resolution_performed": True,
    }


def build_observation_source_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    expected_job_uid: str, job_projection: Mapping[str, object],
    status: Mapping[str, object], terminal_records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    identity = _identity(manifest_identity, label="observation manifest identity")
    projection = _mapping(job_projection, label="observation job projection")
    retained_status = _mapping(status, label="observation status")
    records = [
        _mapping(row, label=f"observation terminal record[{index}]")
        for index, row in enumerate(terminal_records)
    ]
    if (
        retained_status.get("all_tasks_terminal") is not True
        or retained_status.get("all_tasks_succeeded") is not True
        or len(records) != manifest.get("task_count")
        or projection.get("job_uid") != expected_job_uid
    ):
        _fail("observation source requires one complete successful layer")
    common_environment = common_job_environment_v1(
        manifest=manifest, manifest_identity=identity
    )
    command = list(DISPATCHER_COMMAND)
    task_observations: list[dict[str, object]] = []
    statuses = _sequence(
        retained_status.get("task_statuses"), label="observation task statuses"
    )
    execution = str(retained_status["execution_name"])
    for index, (status_row, record) in enumerate(
        zip(statuses, records, strict=True)
    ):
        task_status = _mapping(status_row, label=f"observation task[{index}] status")
        evidence = _mapping(
            record.get("evidence"), label=f"observation task[{index}] evidence"
        )
        runtime = _mapping(
            evidence.get("dispatcher_runtime_evidence"),
            label=f"observation task[{index}] runtime",
        )
        expected_kernel_environment = {
            **common_environment,
            "CLOUD_RUN_EXECUTION": execution,
            "CLOUD_RUN_TASK_INDEX": str(index),
            "CLOUD_RUN_TASK_COUNT": str(manifest["task_count"]),
            "CLOUD_RUN_TASK_ATTEMPT": "0",
        }
        kernel_command = runtime.get("kernel_observed_command")
        kernel_environment = runtime.get("selected_environment")
        if (
            task_status.get("terminal_state") != "SUCCEEDED"
            or task_status.get("exit_code") != 0
            or kernel_command != command
            or kernel_environment != expected_kernel_environment
        ):
            _fail(f"observation task[{index}] provider/kernel binding differs")
        task_observations.append({
            "task_index": index,
            "task_name": f"{execution}/tasks/{index}",
            "attempt": 0,
            "terminal_state": "SUCCEEDED",
            "exit_code": 0,
            "task_terminal_evidence_sha256": evidence[
                "task_terminal_evidence_sha256"
            ],
            "conditions": [
                {"type": "Completed", "state": "CONDITION_SUCCEEDED"}
            ],
            "kernel_dispatcher_command": command,
            "kernel_dispatcher_command_sha256": _canonical_sha(command),
            "kernel_dispatcher_environment": expected_kernel_environment,
            "kernel_dispatcher_environment_sha256": _canonical_sha(
                expected_kernel_environment
            ),
        })
    provider_container = {
        "image": manifest["image_digest"],
        "command": [DISPATCHER_PYTHON],
        "args": ["-I", DISPATCHER_SCRIPT],
        "environment": common_environment,
        "working_dir": "",
        "volume_mounts": [],
        "resource_limits": {"cpu": CPU, "memory": MEMORY},
    }
    provider_template = retained_status["provider_execution_task_template"]
    overrides = retained_status["provider_run_job_overrides"]
    execution_conditions = [
        {"type": "Completed", "state": "CONDITION_SUCCEEDED"}
    ]
    terminal_generation_scope = _task_terminal_generation_resolution_scope_v1(
        manifest
    )
    body = {
        "schema_version": task_manifest.CLOUD_RUN_EXECUTION_OBSERVATION_SOURCE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "collection_semantics": (
            "cloud-run-v2-api-plus-dispatcher-kernel-observation"
        ),
        "manifest_identity": identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "project_id": PROJECT,
        "location": REGION,
        "job_name": manifest["reused_job_name"],
        "job_uid": expected_job_uid,
        "job_generation": projection["job_generation"],
        "execution_name": execution,
        "execution_uid": retained_status["execution_uid"],
        "execution_generation": retained_status["execution_generation"],
        "code_commit": manifest["code_commit"],
        "image_digest": manifest["image_digest"],
        "job_dispatcher_command": command,
        "job_dispatcher_command_sha256": _canonical_sha(command),
        "job_dispatcher_environment": common_environment,
        "job_dispatcher_environment_sha256": _canonical_sha(common_environment),
        "job_dispatcher_environment_semantics": (
            "complete-cloud-run-v2-provider-job-container-environment"
        ),
        "job_dispatcher_environment_complete_provider_spec": True,
        "job_dispatcher_environment_redirect_keys_absent": True,
        "provider_job_container_spec": provider_container,
        "provider_job_container_spec_sha256": _canonical_sha(provider_container),
        "provider_execution_task_template": provider_template,
        "provider_execution_task_template_sha256": _canonical_sha(
            provider_template
        ),
        "provider_run_job_overrides": overrides,
        "provider_run_job_overrides_sha256": _canonical_sha(overrides),
        "task_terminal_generation_resolution_scope": terminal_generation_scope,
        "task_terminal_generation_resolution_scope_sha256": _canonical_sha(
            terminal_generation_scope
        ),
        "task_count": manifest["task_count"],
        "parallelism": manifest["task_count"],
        "maximum_task_retries": 0,
        "task_observations": task_observations,
        "task_observations_sha256": _canonical_sha(task_observations),
        "execution_conditions": execution_conditions,
        "execution_conditions_sha256": _canonical_sha(execution_conditions),
        "source_capture_complete": True,
        "provider_attestation_claimed": False,
    }
    return _with_hash(
        body, field="cloud_run_execution_observation_source_sha256"
    )


def finalize_layer_v1(
    *, manifest_identity: object, expected_job_uid: str, image_uri: str,
    execution_name: str, read_exact: ReadExact, open_known: OpenKnown,
    publish_create_once: PublishCreateOnce, runner: CommandRunner,
    manifest_opener: Callable[..., Mapping[str, object]] = (
        task_manifest.reopen_task_manifest_authority_v1
    ),
) -> dict[str, object]:
    manifest, identity = _open_manifest(
        manifest_identity, read_exact=read_exact, manifest_opener=manifest_opener
    )
    image = _image_uri(image_uri, manifest=manifest)
    status = collect_status_v1(
        manifest_identity=identity,
        expected_job_uid=expected_job_uid,
        image_uri=image,
        execution_name=execution_name,
        read_exact=read_exact,
        runner=runner,
        manifest_opener=manifest_opener,
    )
    if (
        status["all_tasks_terminal"] is not True
        or status["all_tasks_succeeded"] is not True
    ):
        _fail("layer cannot finalize before every task succeeds terminally")
    job_description = _run_json(
        runner,
        job_describe_argv_v1(str(manifest["reused_job_name"])),
        label="finalize job describe",
    )
    projection = validate_exact_job_projection_v1(
        job_description,
        manifest=manifest,
        manifest_identity=identity,
        expected_job_uid=expected_job_uid,
        image_uri=image,
    )
    records = _terminal_records_v1(
        manifest=manifest,
        manifest_identity=identity,
        open_known=open_known,
    )
    source = build_observation_source_v1(
        manifest=manifest,
        manifest_identity=identity,
        expected_job_uid=expected_job_uid,
        job_projection=projection,
        status=status,
        terminal_records=records,
    )
    try:
        source_identity = task_manifest.publish_cloud_run_execution_observation_source_v1(
            source,
            manifest=manifest,
            manifest_identity=identity,
            task_terminal_records=records,
            prior_identity=None,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
        observed = task_manifest.build_observed_cloud_run_execution_authority_v1(
            manifest=manifest,
            manifest_identity=identity,
            observation_source=source,
            observation_source_identity=source_identity,
            task_terminal_records=records,
        )
        receipt = task_manifest.build_layer_execution_receipt_v1(
            manifest=manifest,
            manifest_identity=identity,
            observed_execution_authority=observed,
            task_terminal_records=records,
            read_exact=read_exact,
        )
        receipt_identity = task_manifest.publish_layer_execution_receipt_v1(
            receipt,
            output_prefix=str(manifest["output_prefix"]),
            manifest=manifest,
            manifest_identity=identity,
            prior_identity=None,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
    except task_manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error as exc:
        raise CurrentBankCloudOperatorV1Error(str(exc)) from exc
    body = {
        "schema_version": FINALIZE_RESULT_SCHEMA,
        "manifest_identity": identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "layer_id": manifest["layer_id"],
        "cloud_execution_name": status["execution_name"],
        "task_count": manifest["task_count"],
        "cloud_run_observation_source_identity": source_identity,
        "cloud_run_observation_source_sha256": source[
            "cloud_run_execution_observation_source_sha256"
        ],
        "observed_execution_authority_sha256": observed[
            "observed_cloud_run_execution_sha256"
        ],
        "layer_execution_receipt_identity": receipt_identity,
        "layer_execution_receipt_sha256": receipt[
            "layer_execution_receipt_sha256"
        ],
        "all_tasks_terminal": True,
        "all_tasks_succeeded": True,
        "terminal_evidence_exact_opened": True,
        "scientific_outputs_read": False,
        "realized_outcomes_read": False,
        "logs_read": False,
    }
    return _with_hash(body, field="finalize_result_sha256")


class SubprocessRunnerV1:
    """Bounded-memory argv-only gcloud runner with no shell invocation."""

    def __call__(self, argv: Sequence[str]) -> Mapping[str, object]:
        # Temporary files avoid the unbounded in-memory capture performed by
        # subprocess.PIPE/communicate.  Only cap+1 bytes are ever retained in
        # Python; _run_checked applies the narrower command-specific ceiling.
        with tempfile.TemporaryFile(mode="w+b") as stdout_file, tempfile.TemporaryFile(
            mode="w+b"
        ) as stderr_file:
            completed = subprocess.run(
                list(argv),
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                check=False,
                timeout=300,
            )
            stdout_file.flush()
            stderr_file.flush()
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout = stdout_file.read(MAXIMUM_PROVIDER_JSON_BYTES + 1)
            stderr = stderr_file.read(MAXIMUM_SUBPROCESS_STDERR_BYTES + 1)
        return {
            "returncode": int(completed.returncode),
            "stdout": bytes(stdout),
            "stderr": bytes(stderr),
        }


class GCSExactOperatorStoreV1:
    """Known-name/GCS exact transport with no bucket listing capability."""

    def __init__(self, client: object) -> None:
        self._client = client

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            _fail("operator object URI is not gs://")
        bucket, separator, name = uri[5:].partition("/")
        if (
            not separator
            or not bucket
            or not name
            or name.endswith("/")
            or "//" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))
        ):
            _fail("operator object URI differs")
        return bucket, name

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _identity(identity_value, label="operator exact read")
        bucket, name = self._parts(str(identity["uri"]))
        blob = self._client.bucket(bucket).blob(
            name, generation=int(identity["generation"])
        )
        raw = blob.download_as_bytes(
            if_generation_match=int(identity["generation"]), timeout=300
        )
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("operator generation-exact read content differs")
        return raw

    def open_known(self, uri: str, maximum_bytes: int) -> tuple[bytes, Mapping[str, object]]:
        ceiling = _integer(
            maximum_bytes, label="known-object byte ceiling", minimum=1,
            maximum=1_000_000_000,
        )
        bucket, name = self._parts(uri)
        metadata = self._client.bucket(bucket).blob(name)
        metadata.reload(timeout=120)
        if metadata.generation is None or metadata.size is None:
            _fail("known-object metadata lacks generation/size")
        size = int(metadata.size)
        generation = int(metadata.generation)
        if size < 1 or size > ceiling:
            _fail("known-object metadata exceeds byte ceiling")
        pinned = self._client.bucket(bucket).blob(name, generation=generation)
        raw = pinned.download_as_bytes(
            if_generation_match=generation, start=0, end=size, timeout=300
        )
        if type(raw) is not bytes or len(raw) != size:
            _fail("known-object generation-exact bytes differ")
        identity = {
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": size,
        }
        retained = _identity(identity, label="known-object identity")
        return raw, retained

    def publish_create_once(self, uri: str, raw: bytes) -> Mapping[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("operator create-once bytes differ")
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        blob.upload_from_string(
            raw,
            content_type="application/json",
            if_generation_match=0,
            timeout=300,
        )
        if blob.generation is None:
            _fail("operator create-once result lacks generation")
        identity = _identity({
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }, label="operator create-once result")
        return identity


def validate_prepare_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="prepare request")
    expected_fields = {
        "schema_version",
        "output_prefix",
        "code_commit",
        "image_digest",
        "reused_job_name",
    }
    if set(item) != expected_fields or item.get("schema_version") != PREPARE_REQUEST_SCHEMA:
        _fail("prepare request fields/schema differ")
    prefix = _string(
        item.get("output_prefix"), label="prepare output prefix", maximum=1_024
    )
    commit = _string(item.get("code_commit"), label="prepare commit", maximum=40)
    digest = _string(
        item.get("image_digest"), label="prepare image digest", maximum=71
    )
    job = _string(item.get("reused_job_name"), label="prepare job", maximum=63)
    if (
        not prefix.startswith("gs://")
        or not prefix.endswith("/")
        or "//" in prefix[5:]
        or _COMMIT.fullmatch(commit) is None
        or not digest.startswith("sha256:")
        or _SHA.fullmatch(digest[7:]) is None
        or _JOB.fullmatch(job) is None
    ):
        _fail("prepare prefix/commit/image/job differs")
    return {
        "schema_version": PREPARE_REQUEST_SCHEMA,
        "output_prefix": prefix,
        "code_commit": commit,
        "image_digest": digest,
        "reused_job_name": job,
    }


def _read_exact_identity_bytes_v1(
    identity_value: object, *, read_exact: ReadExact, maximum_bytes: int,
    label: str,
) -> tuple[bytes, dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if identity["bytes"] > maximum_bytes:
        _fail(f"{label} exceeds its exact-read byte ceiling")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} generation-exact bytes differ")
    return raw, identity


def _read_frozen_local_source_v1(
    path: Path, *, expected_bytes: int, expected_sha256: str,
    maximum_bytes: int, label: str,
) -> bytes:
    if not path.is_absolute() or expected_bytes > maximum_bytes:
        _fail(f"{label} local path/ceiling differs")
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise CurrentBankCloudOperatorV1Error(
            f"{label} fixed local open failed"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != expected_bytes:
            _fail(f"{label} fixed local metadata differs")
        raw = os.read(descriptor, maximum_bytes + 1)
        if len(raw) != expected_bytes or os.read(descriptor, 1):
            _fail(f"{label} fixed local bounded read differs")
    finally:
        os.close(descriptor)
    if sha256(raw).hexdigest() != expected_sha256:
        _fail(f"{label} fixed local SHA-256 differs")
    return raw


def prepare_first_layer_v1(
    *, request: object, read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    """Publish the fresh projection authority chain from exact named inputs."""
    item = validate_prepare_request_v1(request)
    # Preparation is deliberately absent from configure/status processes; its
    # wider pure authority-building dependency closure is imported only here.
    from nfl_dfs.research import (  # noqa: PLC0415
        corpus_r6_current_bank_crossed_screen_projection_preparation_v1
        as preparation,
    )

    repository = Path(__file__).resolve().parents[1]
    contract_bytes = _read_frozen_local_source_v1(
        repository / contract.MODULE_PATH,
        expected_bytes=preparation.FROZEN_CONTRACT_MODULE_BYTES,
        expected_sha256=preparation.FROZEN_CONTRACT_MODULE_SHA256,
        maximum_bytes=preparation.MAXIMUM_CODE_INPUT_BYTES,
        label="prepare contract module",
    )
    report_bytes = _read_frozen_local_source_v1(
        repository / contract.CONTRACT_REPORT_PATH,
        expected_bytes=preparation.FROZEN_PREOUTPUT_REPORT_BYTES,
        expected_sha256=preparation.FROZEN_PREOUTPUT_REPORT_SHA256,
        maximum_bytes=preparation.MAXIMUM_REPORT_INPUT_BYTES,
        label="prepare preoutput report",
    )
    panel_identity = _identity(
        contract.PANEL_IDENTITY, label="fixed prepare panel-root identity"
    )
    panel_raw, _ = _read_exact_identity_bytes_v1(
        panel_identity,
        read_exact=read_exact,
        maximum_bytes=int(contract.PANEL_IDENTITY["bytes"]),
        label="prepare panel root",
    )
    panel = _strict_json(panel_raw, label="prepare panel root")
    try:
        return preparation.prepare_projection_first_layer_v1(
            output_prefix=str(item["output_prefix"]),
            contract_module_bytes=contract_bytes,
            preoutput_report_bytes=report_bytes,
            code_commit=str(item["code_commit"]),
            image_digest=str(item["image_digest"]),
            reused_job_name=str(item["reused_job_name"]),
            panel_root_body=panel,
            panel_root_identity=panel_identity,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
    except preparation.CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error as exc:
        raise CurrentBankCloudOperatorV1Error(str(exc)) from exc


def _later_layer_descriptor_by_id_v1(layer_id: str) -> dict[str, object]:
    # Registry shape is independent of the output namespace.  The actual URI
    # binding is rederived below from the exact projection receipt's prefix.
    registry = task_manifest.layer_registry_v1(
        contract.OUTPUT_NAMESPACE + "operator-request-shape/"
    )
    rows = [
        dict(row) for row in registry
        if row.get("layer_id") == layer_id
        and type(row.get("layer_ordinal")) is int
        and 1 <= int(row["layer_ordinal"]) <= 7
    ]
    if len(rows) != 1:
        _fail("prepare-layer target is not one registered later layer")
    return rows[0]


def validate_prepare_layer_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="prepare-layer request")
    expected_fields = {
        "schema_version",
        "projection_preparation_receipt_identity",
        "target_layer_id",
        "predecessor_layer_receipt_identities",
    }
    if (
        set(item) != expected_fields
        or item.get("schema_version") != PREPARE_LAYER_REQUEST_SCHEMA
    ):
        _fail("prepare-layer request fields/schema differ")
    layer = _string(
        item.get("target_layer_id"), label="prepare-layer target", maximum=64
    )
    descriptor = _later_layer_descriptor_by_id_v1(layer)
    raw_predecessors = _sequence(
        item.get("predecessor_layer_receipt_identities"),
        label="prepare-layer predecessor identities",
    )
    expected_count = len(descriptor["predecessor_layers"])
    if len(raw_predecessors) != expected_count:
        _fail("prepare-layer predecessor identity count differs from registry")
    predecessors = [
        _identity(
            identity,
            label=f"prepare-layer predecessor identity[{index}]",
        )
        for index, identity in enumerate(raw_predecessors)
    ]
    if len({str(row["uri"]) for row in predecessors}) != len(predecessors):
        _fail("prepare-layer predecessor identities repeat")
    return {
        "schema_version": PREPARE_LAYER_REQUEST_SCHEMA,
        "projection_preparation_receipt_identity": _identity(
            item.get("projection_preparation_receipt_identity"),
            label="prepare-layer projection preparation receipt identity",
        ),
        "target_layer_id": layer,
        "predecessor_layer_receipt_identities": predecessors,
    }


def prepare_later_layer_v1(
    *, request: object, read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    """Prepare one registered later layer from identities, never caller bodies."""
    item = validate_prepare_layer_request_v1(request)
    from nfl_dfs.research import (  # noqa: PLC0415
        corpus_r6_current_bank_crossed_screen_layer_preparation_v1
        as layer_preparation,
    )
    from nfl_dfs.research import (  # noqa: PLC0415
        corpus_r6_current_bank_crossed_screen_projection_preparation_v1
        as projection_preparation,
    )

    projection_raw, projection_identity = _read_exact_identity_bytes_v1(
        item["projection_preparation_receipt_identity"],
        read_exact=read_exact,
        maximum_bytes=(
            projection_preparation.MAXIMUM_PROJECTION_PREPARATION_RECEIPT_BYTES
        ),
        label="prepare-layer projection preparation receipt",
    )
    projection_receipt = _strict_json(
        projection_raw, label="prepare-layer projection preparation receipt"
    )
    try:
        projection_receipt = (
            projection_preparation.validate_projection_preparation_receipt_v1(
                projection_receipt
            )
        )
    except projection_preparation.CorpusR6CurrentBankCrossedScreenProjectionPreparationV1Error as exc:
        raise CurrentBankCloudOperatorV1Error(str(exc)) from exc
    prefix = str(projection_receipt["output_prefix"])
    expected_projection_uri = (
        projection_preparation.projection_preparation_uri_lattice_v1(prefix)[
            "projection-preparation-receipt"
        ]
    )
    if projection_identity["uri"] != expected_projection_uri:
        _fail("prepare-layer projection receipt identity URI differs")
    target = str(item["target_layer_id"])
    rows = [
        dict(row) for row in task_manifest.layer_registry_v1(prefix)
        if row.get("layer_id") == target
    ]
    if len(rows) != 1 or not 1 <= int(rows[0]["layer_ordinal"]) <= 7:
        _fail("prepare-layer target registry derivation differs")
    descriptor = rows[0]
    registry_by_layer = {
        str(row["layer_id"]): dict(row)
        for row in task_manifest.layer_registry_v1(prefix)
    }
    identities = item["predecessor_layer_receipt_identities"]
    records: list[dict[str, object]] = []
    for index, (expected_layer, identity) in enumerate(zip(
        descriptor["predecessor_layers"], identities, strict=True
    )):
        expected_uri = registry_by_layer[str(expected_layer)][
            "layer_execution_receipt_uri"
        ]
        if identity["uri"] != expected_uri:
            _fail(f"prepare-layer predecessor identity[{index}] order/URI differs")
        raw, retained_identity = _read_exact_identity_bytes_v1(
            identity,
            read_exact=read_exact,
            maximum_bytes=task_manifest.MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES,
            label=f"prepare-layer predecessor receipt[{index}]",
        )
        records.append({
            "identity": retained_identity,
            "receipt": _strict_json(
                raw, label=f"prepare-layer predecessor receipt[{index}]"
            ),
        })
    try:
        return layer_preparation.prepare_registered_layer_v1(
            projection_preparation_receipt=projection_receipt,
            projection_preparation_receipt_identity=projection_identity,
            target_layer_id=target,
            target_layer_ordinal=int(descriptor["layer_ordinal"]),
            predecessor_layer_receipts=records,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
    except layer_preparation.CorpusR6CurrentBankCrossedScreenLayerPreparationV1Error as exc:
        raise CurrentBankCloudOperatorV1Error(str(exc)) from exc


def validate_operator_request_v1(value: object, *, mode: str) -> dict[str, object]:
    item = _mapping(value, label="operator request")
    common_fields = {
        "schema_version", "manifest_identity", "expected_job_uid", "image_uri"
    }
    if mode in {"configure", "arm-launch"}:
        expected_fields = common_fields
    elif mode == "launch":
        expected_fields = common_fields | {"launch_intent_identity"}
    elif mode == "recover-launch":
        expected_fields = common_fields | {"launch_intent_identity"}
    elif mode in {"status", "finalize"}:
        expected_fields = common_fields | {"execution_name"}
    else:
        _fail("operator request mode differs")
    if set(item) != expected_fields or item.get("schema_version") != OPERATOR_REQUEST_SCHEMA:
        _fail("operator request fields/schema differ")
    identity = _identity(item.get("manifest_identity"), label="request manifest identity")
    uid = _string(item.get("expected_job_uid"), label="request job UID", maximum=128)
    image = _string(item.get("image_uri"), label="request image URI", maximum=600)
    if _UID.fullmatch(uid) is None or _DIGEST_IMAGE.fullmatch(image) is None:
        _fail("operator request job UID/image differs")
    retained = {
        "schema_version": OPERATOR_REQUEST_SCHEMA,
        "manifest_identity": identity,
        "expected_job_uid": uid,
        "image_uri": image,
    }
    if mode in {"launch", "recover-launch"}:
        retained["launch_intent_identity"] = _identity(
            item.get("launch_intent_identity"),
            label="request launch intent identity",
        )
    if mode in {"status", "finalize"}:
        retained["execution_name"] = _short_resource_name(
            item.get("execution_name"),
            label="request execution",
            pattern=_EXECUTION,
        )
    return retained


def _read_local_request_v1(path_value: str) -> dict[str, object]:
    path = Path(path_value)
    if not path.is_absolute() or path.name in {"", ".", ".."}:
        _fail("operator request path must be absolute")
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise CurrentBankCloudOperatorV1Error(
            "operator request exact local open failed"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & LOCAL_INPUT_MODE_MASK
            or metadata.st_size < 2
            or metadata.st_size > MAXIMUM_REQUEST_BYTES
        ):
            _fail("operator request local file authority differs")
        raw = os.read(descriptor, MAXIMUM_REQUEST_BYTES + 1)
        if len(raw) != metadata.st_size or os.read(descriptor, 1):
            _fail("operator request changed during bounded read")
    finally:
        os.close(descriptor)
    return _strict_json(raw, label="operator request")


def _write_local_result_v1(path_value: str, value: Mapping[str, object]) -> None:
    path = Path(path_value)
    if not path.is_absolute() or path.name in {"", ".", ".."}:
        _fail("operator result path must be absolute")
    raw = _canonical_bytes(_mapping(value, label="operator result")) + b"\n"
    if len(raw) > MAXIMUM_LOCAL_RESULT_BYTES:
        _fail("operator result exceeds its local byte ceiling")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, LOCAL_OUTPUT_MODE)
    except OSError as exc:
        raise CurrentBankCloudOperatorV1Error(
            "operator result exclusive local create failed"
        ) from exc
    try:
        written = 0
        while written < len(raw):
            count = os.write(descriptor, raw[written:])
            if count < 1:
                _fail("operator result write made no progress")
            written += count
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != LOCAL_OUTPUT_MODE
            or metadata.st_size != len(raw)
        ):
            _fail("operator result local authority differs")
    finally:
        os.close(descriptor)


def _storage_client_v1() -> object:
    for key in (
        "STORAGE_EMULATOR_HOST",
        "CLOUDSDK_API_ENDPOINT_OVERRIDES_STORAGE",
        "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ):
        if os.environ.get(key):
            _fail("operator ambient storage/auth redirect is forbidden")
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise CurrentBankCloudOperatorV1Error(
            "google-cloud-storage is required"
        ) from exc
    return storage.Client(project=PROJECT)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operate one immutable current-bank Cloud Run layer."
    )
    parser.add_argument(
        "mode",
        choices=(
            "prepare", "prepare-layer", "configure", "arm-launch", "launch",
            "recover-launch", "status", "finalize",
        ),
    )
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--output-file", required=True)
    args = parser.parse_args(argv)
    request_value = _read_local_request_v1(str(args.request_file))
    request = (
        validate_prepare_request_v1(request_value)
        if args.mode == "prepare"
        else validate_prepare_layer_request_v1(request_value)
        if args.mode == "prepare-layer"
        else validate_operator_request_v1(request_value, mode=str(args.mode))
    )
    store = GCSExactOperatorStoreV1(_storage_client_v1())
    runner = SubprocessRunnerV1()
    if args.mode == "prepare":
        result = prepare_first_layer_v1(
            request=request,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
        _write_local_result_v1(str(args.output_file), result)
        return 0
    if args.mode == "prepare-layer":
        result = prepare_later_layer_v1(
            request=request,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
        _write_local_result_v1(str(args.output_file), result)
        return 0
    common = {
        "manifest_identity": request["manifest_identity"],
        "expected_job_uid": str(request["expected_job_uid"]),
        "image_uri": str(request["image_uri"]),
        "read_exact": store.read_exact,
        "runner": runner,
    }
    if args.mode == "configure":
        with tempfile.TemporaryDirectory(
            prefix="r6-current-bank-cloud-flags-", dir="/tmp"
        ) as directory:
            result = configure_layer_v1(
                **common,
                flags_path=str(Path(directory) / "configure-flags.json"),
            )
    elif args.mode == "arm-launch":
        result = arm_launch_v1(
            **common, publish_create_once=store.publish_create_once
        )
    elif args.mode == "launch":
        result = launch_layer_v1(
            **common,
            launch_intent_identity=request["launch_intent_identity"],
            publish_create_once=store.publish_create_once,
        )
    elif args.mode == "recover-launch":
        result = recover_launch_v1(
            **common,
            launch_intent_identity=request["launch_intent_identity"],
        )
    elif args.mode == "status":
        result = collect_status_v1(
            **common, execution_name=str(request["execution_name"])
        )
    else:
        result = finalize_layer_v1(
            **common,
            execution_name=str(request["execution_name"]),
            open_known=store.open_known,
            publish_create_once=store.publish_create_once,
        )
    _write_local_result_v1(str(args.output_file), result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except CurrentBankCloudOperatorV1Error as exc:
        sys.stderr.write(f"current-bank cloud operator failed closed: {exc}\n")
        raise SystemExit(1) from exc


__all__ = [
    "ARM_LAUNCH_RESULT_SCHEMA",
    "CONFIGURATION_RESULT_SCHEMA",
    "CurrentBankCloudOperatorV1Error",
    "DISPATCHER_COMMAND",
    "FINALIZE_RESULT_SCHEMA",
    "GCSExactOperatorStoreV1",
    "JOB_PROJECTION_SCHEMA",
    "LAUNCH_INTENT_SCHEMA",
    "LAUNCH_OPERATION_RESULT_SCHEMA",
    "LAUNCH_RESULT_SCHEMA",
    "LAUNCH_SUBMISSION_MARKER_SCHEMA",
    "OPERATOR_REQUEST_SCHEMA",
    "PREPARE_REQUEST_SCHEMA",
    "PREPARE_LAYER_REQUEST_SCHEMA",
    "PROJECT",
    "REGION",
    "STATUS_SCHEMA",
    "SubprocessRunnerV1",
    "arm_launch_v1",
    "build_launch_intent_v1",
    "build_observation_source_v1",
    "collect_status_v1",
    "common_job_environment_v1",
    "configure_argv_v1",
    "configure_flags_v1",
    "configure_layer_v1",
    "environment_flag_v1",
    "execute_argv_v1",
    "execution_describe_argv_v1",
    "finalize_layer_v1",
    "job_describe_argv_v1",
    "launch_intent_uri_v1",
    "launch_layer_v1",
    "launch_submission_marker_uri_v1",
    "main",
    "prepare_first_layer_v1",
    "prepare_later_layer_v1",
    "recover_launch_v1",
    "task_describe_argv_v1",
    "validate_exact_job_projection_v1",
    "validate_job_identity_v1",
    "validate_operator_request_v1",
    "validate_launch_intent_v1",
    "validate_launch_result_v1",
    "validate_prepare_request_v1",
    "validate_prepare_layer_request_v1",
]
