#!/usr/bin/env python3
"""Launch, inspect, and finalize one hard-230 smoke or full score run.

This host-only adapter can update one existing UID-bound Cloud Run job, submit
one async execution, inspect only the execution and its manifest-known tasks,
and collect only manifest-known create-once task roots.  It never reads logs,
lists storage, creates a job, or reads outcomes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Final

from nfl_dfs.research import corpus_extreme_tail_hard230_r6_cloud_entrypoint_v1 as entrypoint
from nfl_dfs.research import corpus_extreme_tail_hard230_r6_run_controller_v1 as controller
from nfl_dfs.research import corpus_legal_feasibility as legal
from scripts import run_corpus_extreme_tail_hard230_r6_cloud_v1 as runtime


PROJECT: Final = entrypoint.FIXED_GCP_PROJECT
REGION: Final = "us-central1"
MAXIMUM_PROVIDER_JSON_BYTES: Final = 8_000_000
MAXIMUM_PROVIDER_STDERR_BYTES: Final = 256_000
MAXIMUM_EXECUTION_NAME_BYTES: Final = 4_096
ENV_DELIMITER: Final = "|"

LAUNCH_RESULT_SCHEMA: Final = "hard230-r6-score-run-launch-result/v1"
STATUS_SCHEMA: Final = "hard230-r6-score-run-status/v1"
FINALIZE_RESULT_SCHEMA: Final = "hard230-r6-score-run-operator-finalization/v1"

_JOB = re.compile(r"[a-z][a-z0-9-]{0,62}\Z")
_RESOURCE = re.compile(r"[a-z][a-z0-9-]{0,127}\Z")
_UID = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,127}\Z")
_DIGEST_IMAGE = re.compile(
    r"[a-z0-9][a-z0-9._/-]{0,511}@sha256:[0-9a-f]{64}\Z"
)


class Hard230R6ScoreRunV1Error(RuntimeError):
    """The hard-230 Cloud Run operation failed closed."""


def _fail(message: str) -> None:
    raise Hard230R6ScoreRunV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return legal.canonical_json_bytes(value)
    except (TypeError, ValueError, legal.CorpusLegalFeasibilityError) as exc:
        raise Hard230R6ScoreRunV1Error("value is not finite canonical JSON") from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _strict_local_json(path: Path, *, label: str) -> dict[str, object]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Hard230R6ScoreRunV1Error(f"{label} is not UTF-8 JSON") from exc
    item = _mapping(value, label=label)
    if _canonical(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _write_local(path: Path, value: Mapping[str, object]) -> None:
    if path.exists() or path.is_symlink():
        _fail("local output must be one absent path")
    raw = _canonical(value)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        0o600,
    )
    try:
        written = 0
        while written < len(raw):
            count = os.write(descriptor, raw[written:])
            if count < 1:
                _fail("local output write made no progress")
            written += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return entrypoint._identity(value, label=label)
    except entrypoint.Hard230R6CloudEntrypointV1Error as exc:
        raise Hard230R6ScoreRunV1Error(str(exc)) from exc


def _with_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    retained = dict(body)
    if field in retained:
        _fail(f"{field} cannot already be present")
    retained[field] = _hash(retained)
    return retained


def _short_name(value: object, *, label: str, pattern: re.Pattern[str]) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} differs")
    retained = value.rstrip("/").rsplit("/", 1)[-1]
    if pattern.fullmatch(retained) is None:
        _fail(f"{label} differs")
    return retained


def job_describe_argv_v1(job: str) -> list[str]:
    if _JOB.fullmatch(job) is None:
        _fail("described job differs")
    return [
        "gcloud", "run", "jobs", "describe", job,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ]


def execution_describe_argv_v1(execution: str) -> list[str]:
    retained = _short_name(execution, label="described execution", pattern=_RESOURCE)
    return [
        "gcloud", "run", "jobs", "executions", "describe", retained,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ]


def task_describe_argv_v1(*, execution: str, task_index: int) -> list[str]:
    retained = _short_name(execution, label="task execution", pattern=_RESOURCE)
    if type(task_index) is not int or not 0 <= task_index < entrypoint.TASK_COUNT:
        _fail("task index differs")
    resource = f"{retained}-task{task_index}"
    if _RESOURCE.fullmatch(resource) is None:
        _fail("derived task resource differs")
    return [
        "gcloud", "run", "jobs", "executions", "tasks", "describe",
        resource, "--project", PROJECT, "--region", REGION, "--format=json",
    ]


def execute_argv_v1(job: str) -> list[str]:
    if _JOB.fullmatch(job) is None:
        _fail("executed job differs")
    return [
        "gcloud", "run", "jobs", "execute", job,
        "--project", PROJECT, "--region", REGION,
        "--async", "--format=value(metadata.name)",
    ]


def configure_argv_v1(job: str, *, flags_path: str) -> list[str]:
    path = Path(flags_path)
    if _JOB.fullmatch(job) is None or not path.is_absolute():
        _fail("configured job or flags path differs")
    return [
        "gcloud", "run", "jobs", "update", job,
        "--project", PROJECT, "--region", REGION, "--quiet",
        f"--flags-file={path}", "--format=json",
    ]


def _default_runner(argv: Sequence[str]) -> dict[str, object]:
    completed = subprocess.run(
        list(argv), check=False, capture_output=True, stdin=subprocess.DEVNULL
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _run_checked(
    runner, argv: Sequence[str], *, label: str, stdout_ceiling: int
) -> bytes:
    try:
        result = _mapping(runner(list(argv)), label=f"{label} subprocess")
    except Exception as exc:
        raise Hard230R6ScoreRunV1Error(f"{label} subprocess is ambiguous") from exc
    stdout = result.get("stdout")
    stderr = result.get("stderr")
    if (
        set(result) != {"returncode", "stdout", "stderr"}
        or type(result.get("returncode")) is not int
        or type(stdout) is not bytes
        or type(stderr) is not bytes
        or len(stdout) > stdout_ceiling
        or len(stderr) > MAXIMUM_PROVIDER_STDERR_BYTES
        or result["returncode"] != 0
    ):
        _fail(f"{label} subprocess failed or is ambiguous")
    return stdout


def _run_json(runner, argv: Sequence[str], *, label: str) -> dict[str, object]:
    raw = _run_checked(
        runner, argv, label=label, stdout_ceiling=MAXIMUM_PROVIDER_JSON_BYTES
    )
    try:
        return _mapping(json.loads(raw.decode("utf-8")), label=f"{label} JSON")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Hard230R6ScoreRunV1Error(f"{label} did not return JSON") from exc


def _metadata(value: Mapping[str, object], *, label: str) -> tuple[str, str, str]:
    metadata = _mapping(value.get("metadata"), label=f"{label} metadata")
    name = _short_name(metadata.get("name"), label=f"{label} name", pattern=_RESOURCE)
    uid = str(metadata.get("uid", ""))
    generation = str(metadata.get("generation", ""))
    if _UID.fullmatch(uid) is None or not generation.isdigit() or int(generation) < 1:
        _fail(f"{label} UID/generation differs")
    return name, uid, generation


def _provider_state(status_value: object, *, expected_count: int | None = None) -> str:
    status = _mapping(status_value, label="provider status")
    conditions = _sequence(status.get("conditions", []), label="provider conditions")
    completed = any(
        isinstance(row, Mapping)
        and row.get("type") == "Completed"
        and (
            row.get("state") == "CONDITION_SUCCEEDED"
            or row.get("status") in (True, "True")
        )
        for row in conditions
    )
    completion = status.get("completionTime")
    failed = int(status.get("failedCount", 0) or 0)
    cancelled = int(status.get("cancelledCount", 0) or 0)
    succeeded = int(status.get("succeededCount", 0) or 0)
    if completed and completion and failed == 0 and cancelled == 0:
        if expected_count is None or succeeded == expected_count:
            return "SUCCEEDED"
    if completed or completion:
        return "FAILED"
    return "ACTIVE"


def _job_identity(value: object, *, job: str, expected_uid: str) -> dict[str, object]:
    item = _mapping(value, label="job description")
    name, uid, generation = _metadata(item, label="job")
    if name != job or uid != expected_uid or _UID.fullmatch(expected_uid) is None:
        _fail("reused job name/UID differs")
    status = _mapping(item.get("status", {}), label="job status")
    latest = status.get("latestCreatedExecution")
    latest_name = None
    if latest not in (None, {}):
        latest_name = _short_name(
            _mapping(latest, label="job latest execution").get("name"),
            label="job latest execution",
            pattern=_RESOURCE,
        )
    return {
        "job_name": name,
        "job_uid": uid,
        "job_generation": generation,
        "latest_execution_name": latest_name,
    }


def _container(value: Mapping[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    spec = _mapping(value.get("spec"), label="job spec")
    outer_template = _mapping(spec.get("template"), label="job outer template")
    outer = _mapping(outer_template.get("spec"), label="job outer spec")
    template = _mapping(outer.get("template"), label="job task template")
    task = _mapping(template.get("spec"), label="job task spec")
    containers = _sequence(task.get("containers"), label="job containers")
    if len(containers) != 1:
        _fail("job container count differs")
    return outer, task, _mapping(containers[0], label="job container")


def _environment(value: object) -> dict[str, str]:
    rows = _sequence(value, label="job environment")
    retained: dict[str, str] = {}
    for raw in rows:
        row = _mapping(raw, label="job environment row")
        if set(row) != {"name", "value"} or type(row["value"]) is not str:
            _fail("job environment row differs")
        name = str(row["name"])
        if name in retained:
            _fail("job environment name repeats")
        retained[name] = row["value"]
    return retained


def _network_present(value: object) -> bool:
    if not isinstance(value, Mapping):
        return bool(value)
    for key, item in value.items():
        normalized = str(key).lower().replace("-", "").replace("_", "")
        if any(token in normalized for token in ("network", "vpc", "cloudsql")):
            if item not in (None, "", [], {}):
                return True
        if isinstance(item, Mapping) and _network_present(item):
            return True
    return False


def _validate_job_projection(
    value: object,
    *,
    manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object],
    expected_uid: str,
    image_uri: str,
) -> dict[str, object]:
    item = _mapping(value, label="configured job description")
    identity = _job_identity(
        item, job=str(manifest["reused_job_name"]), expected_uid=expected_uid
    )
    outer, task, container = _container(item)
    config = controller.build_controller_job_configuration_v1(
        controller_manifest=manifest,
        controller_manifest_identity=manifest_identity,
    )
    timeout = str(task.get("timeoutSeconds", "")).removesuffix("s")
    limits = _mapping(
        _mapping(container.get("resources", {}), label="job resources").get(
            "limits", {}
        ),
        label="job resource limits",
    )
    if (
        outer.get("taskCount") != config["task_count"]
        or outer.get("parallelism") != config["parallelism"]
        or task.get("maxRetries") != 0
        or not timeout.isdigit()
        or int(timeout) != config["timeout_seconds"]
        or container.get("image") != image_uri
        or container.get("command", []) != config["container_command"]
        or container.get("args", []) != config["container_args"]
        or _environment(container.get("env", [])) != config["container_environment"]
        or limits != {"cpu": config["cpu"], "memory": config["memory"]}
        or container.get("workingDir", "") != ""
        or container.get("volumeMounts", []) != []
        or task.get("volumes", []) != []
        or _network_present(item)
    ):
        _fail("configured job projection differs")
    return identity


def _environment_flag(environment: Mapping[str, object]) -> str:
    retained = _mapping(environment, label="configured environment")
    if any(
        type(value) is not str
        or ENV_DELIMITER in key
        or ENV_DELIMITER in value
        or "=" in key
        for key, value in retained.items()
    ):
        _fail("configured environment cannot use the delimiter")
    return (
        f"^{ENV_DELIMITER}^"
        + ENV_DELIMITER.join(f"{key}={retained[key]}" for key in sorted(retained))
    )


def configure_flags_v1(
    *,
    manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object],
    image_uri: str,
) -> dict[str, object]:
    if (
        _DIGEST_IMAGE.fullmatch(image_uri) is None
        or not image_uri.endswith(f"@{manifest['immutable_image_digest']}")
    ):
        _fail("immutable image URI differs from the controller manifest")
    config = controller.build_controller_job_configuration_v1(
        controller_manifest=manifest,
        controller_manifest_identity=manifest_identity,
    )
    args = list(config["container_args"])
    return {
        "--args": f"^{ENV_DELIMITER}^" + ENV_DELIMITER.join(args),
        "--clear-cloudsql-instances": True,
        "--clear-network": True,
        "--clear-secrets": True,
        "--clear-volume-mounts": True,
        "--clear-volumes": True,
        "--clear-vpc-connector": True,
        "--command": config["container_command"][0],
        "--cpu": config["cpu"],
        "--image": image_uri,
        "--max-retries": 0,
        "--memory": config["memory"],
        "--parallelism": config["parallelism"],
        "--set-env-vars": _environment_flag(config["container_environment"]),
        "--task-timeout": f"{config['timeout_seconds']}s",
        "--tasks": config["task_count"],
        "--workdir": "",
    }


def _assert_no_active_latest(
    job_identity: Mapping[str, object], *, runner, expected_uid: str, job: str
) -> None:
    latest = job_identity.get("latest_execution_name")
    if latest is None:
        return
    value = _run_json(
        runner, execution_describe_argv_v1(str(latest)),
        label="latest execution describe",
    )
    item = _mapping(value, label="latest execution")
    name, _, _ = _metadata(item, label="latest execution")
    labels = _mapping(
        _mapping(item.get("metadata"), label="latest execution metadata").get(
            "labels", {}
        ),
        label="latest execution labels",
    )
    if (
        name != latest
        or labels.get("run.googleapis.com/job") != job
        or labels.get("run.googleapis.com/jobUid") != expected_uid
        or _provider_state(item.get("status", {})) == "ACTIVE"
    ):
        _fail("reused job has an active or foreign latest execution")


def launch_controller_run_v1(
    *,
    controller_manifest_identity: Mapping[str, object],
    image_uri: str,
    store: runtime.GCSExactTransportV1,
    runner=_default_runner,
) -> dict[str, object]:
    manifest, manifest_identity, _ = controller.open_controller_manifest_v1(
        controller_manifest_identity=controller_manifest_identity,
        read_exact=store.read_exact,
    )
    job = str(manifest["reused_job_name"])
    expected_job_uid = str(manifest["reused_job_uid"])
    pre = _run_json(runner, job_describe_argv_v1(job), label="prelaunch job describe")
    pre_identity = _job_identity(pre, job=job, expected_uid=expected_job_uid)
    _assert_no_active_latest(
        pre_identity, runner=runner, expected_uid=expected_job_uid, job=job
    )
    flags = configure_flags_v1(
        manifest=manifest, manifest_identity=manifest_identity, image_uri=image_uri
    )
    with tempfile.TemporaryDirectory(prefix="hard230-r6-score-run-") as directory:
        flags_path = Path(directory) / "configure-flags.json"
        flags_path.write_bytes(_canonical(flags) + b"\n")
        _run_checked(
            runner,
            configure_argv_v1(job, flags_path=str(flags_path)),
            label="job update",
            stdout_ceiling=MAXIMUM_PROVIDER_JSON_BYTES,
        )
    post = _run_json(runner, job_describe_argv_v1(job), label="postlaunch job describe")
    post_identity = _validate_job_projection(
        post,
        manifest=manifest,
        manifest_identity=manifest_identity,
        expected_uid=expected_job_uid,
        image_uri=image_uri,
    )
    raw_name = _run_checked(
        runner,
        execute_argv_v1(job),
        label="async job execution",
        stdout_ceiling=MAXIMUM_EXECUTION_NAME_BYTES,
    )
    try:
        execution_name = _short_name(
            raw_name.decode("utf-8").strip(),
            label="submitted execution",
            pattern=_RESOURCE,
        )
    except UnicodeDecodeError as exc:
        raise Hard230R6ScoreRunV1Error("submitted execution is not UTF-8") from exc
    launch_receipt = controller.build_launch_receipt_v1(
        controller_manifest=manifest,
        controller_manifest_identity=manifest_identity,
        job_uid=expected_job_uid,
        execution_name=execution_name,
    )
    launch_identity = store.publish_create_once(
        str(manifest["launch_receipt_uri"]), _canonical(launch_receipt)
    )
    if store.read_exact(launch_identity) != _canonical(launch_receipt):
        _fail("launch receipt exact reopen differs")
    return _with_hash({
        "schema_version": LAUNCH_RESULT_SCHEMA,
        "scope_id": manifest["scope_id"],
        "controller_manifest_identity": manifest_identity,
        "launch_receipt_identity": launch_identity,
        "launch_receipt_sha256": launch_receipt["launch_receipt_sha256"],
        "job_name": job,
        "job_uid": expected_job_uid,
        "configured_job_generation": post_identity["job_generation"],
        "image_uri": image_uri,
        "execution_name": execution_name,
        "cloud_task_count": manifest["cloud_task_count"],
        "single_async_submission": True,
        "logs_read": False,
        "outcome_columns_read": [],
    }, "launch_result_sha256")


def _validate_launch_result(value: object) -> dict[str, object]:
    item = _mapping(value, label="launch result")
    retained = item.pop("launch_result_sha256", None)
    if retained != _hash(item) or item.get("schema_version") != LAUNCH_RESULT_SCHEMA:
        _fail("launch result self-hash or schema differs")
    return {**item, "launch_result_sha256": retained}


def status_controller_run_v1(
    *, launch_result: Mapping[str, object], store: runtime.GCSExactTransportV1,
    runner=_default_runner,
) -> dict[str, object]:
    launch_result = _validate_launch_result(launch_result)
    manifest, manifest_identity, _ = controller.open_controller_manifest_v1(
        controller_manifest_identity=launch_result["controller_manifest_identity"],
        read_exact=store.read_exact,
    )
    launch_raw = store.read_exact(
        _identity(launch_result["launch_receipt_identity"], label="launch receipt")
    )
    launch = controller.validate_launch_receipt_v1(
        json.loads(launch_raw.decode("utf-8")),
        controller_manifest=manifest,
        controller_manifest_identity=manifest_identity,
    )
    if (
        launch["execution_name"] != launch_result["execution_name"]
        or launch["job_uid"] != launch_result["job_uid"]
    ):
        _fail("launch result and exact launch receipt differ")
    execution = str(launch["execution_name"])
    execution_value = _run_json(
        runner, execution_describe_argv_v1(execution), label="execution describe"
    )
    execution_item = _mapping(execution_value, label="execution")
    name, execution_uid, generation = _metadata(execution_item, label="execution")
    labels = _mapping(
        _mapping(execution_item.get("metadata"), label="execution metadata").get(
            "labels", {}
        ),
        label="execution labels",
    )
    count = int(manifest["cloud_task_count"])
    execution_state = _provider_state(
        execution_item.get("status", {}), expected_count=count
    )
    if (
        name != execution
        or labels.get("run.googleapis.com/job") != manifest["reused_job_name"]
        or labels.get("run.googleapis.com/jobUid") != launch["job_uid"]
    ):
        _fail("execution job ownership differs")
    tasks: list[dict[str, object]] = []
    for index in range(count):
        task = _run_json(
            runner,
            task_describe_argv_v1(execution=execution, task_index=index),
            label=f"task[{index}] describe",
        )
        metadata = _mapping(task.get("metadata"), label=f"task[{index}] metadata")
        task_name = _short_name(
            metadata.get("name"), label=f"task[{index}] name", pattern=_RESOURCE
        )
        task_labels = _mapping(
            metadata.get("labels", {}), label=f"task[{index}] labels"
        )
        task_status = _mapping(task.get("status", {}), label=f"task[{index}] status")
        state = _provider_state(task_status)
        raw_index = task_status.get("index", index)
        attempt = task_status.get("retried", 0)
        last = _mapping(
            task_status.get("lastAttemptResult", {}),
            label=f"task[{index}] last attempt",
        )
        exit_code = int(last.get("exitCode", 0 if state == "SUCCEEDED" else 255))
        if (
            task_name != f"{execution}-task{index}"
            or task_labels.get("run.googleapis.com/execution") != execution
            or raw_index != index
            or attempt != 0
            or not 0 <= exit_code <= 255
        ):
            _fail(f"task[{index}] provider binding differs")
        tasks.append({
            "cloud_task_index": index,
            "scientific_task_index": manifest["scientific_task_indices"][index],
            "slate_id": manifest["expected_task_results"][index]["slate_id"],
            "terminal_state": state,
            "exit_code": exit_code,
        })
    all_terminal = execution_state != "ACTIVE" and all(
        row["terminal_state"] != "ACTIVE" for row in tasks
    )
    all_succeeded = (
        execution_state == "SUCCEEDED"
        and all(row["terminal_state"] == "SUCCEEDED" for row in tasks)
        and all(row["exit_code"] == 0 for row in tasks)
    )
    return _with_hash({
        "schema_version": STATUS_SCHEMA,
        "scope_id": manifest["scope_id"],
        "controller_manifest_identity": manifest_identity,
        "launch_receipt_identity": launch_result["launch_receipt_identity"],
        "job_name": manifest["reused_job_name"],
        "job_uid": launch["job_uid"],
        "execution_name": execution,
        "execution_uid": execution_uid,
        "execution_generation": generation,
        "execution_terminal_state": execution_state,
        "cloud_task_count": count,
        "task_statuses": tasks,
        "task_statuses_sha256": _hash(tasks),
        "all_tasks_terminal": all_terminal,
        "all_tasks_succeeded": all_succeeded,
        "logs_read": False,
        "scientific_outputs_read": False,
        "outcome_columns_read": [],
    }, "status_sha256")


def finalize_controller_run_v1(
    *, launch_result: Mapping[str, object], store: runtime.GCSExactTransportV1,
    runner=_default_runner,
) -> dict[str, object]:
    launch_result = _validate_launch_result(launch_result)
    status = status_controller_run_v1(
        launch_result=launch_result, store=store, runner=runner
    )
    if status["all_tasks_succeeded"] is not True:
        _fail("hard230 finalization requires every Cloud Run task to succeed")
    finalized = controller.collect_and_publish_final_root_v1(
        controller_manifest_identity=launch_result["controller_manifest_identity"],
        launch_receipt_identity=launch_result["launch_receipt_identity"],
        read_exact=store.read_exact,
        open_known=store.open_known,
        publish_create_once=store.publish_create_once,
    )
    return _with_hash({
        "schema_version": FINALIZE_RESULT_SCHEMA,
        "scope_id": finalized["scope_id"],
        "complete": True,
        "launch_result_sha256": launch_result["launch_result_sha256"],
        "provider_status_sha256": status["status_sha256"],
        "controller_manifest_identity": finalized["controller_manifest_identity"],
        "launch_receipt_identity": finalized["launch_receipt_identity"],
        "final_root_identity": finalized["final_root_identity"],
        "final_root_sha256": finalized["final_root_sha256"],
        "scientific_task_count": finalized["scientific_task_count"],
        "population_descriptor_count": finalized["population_descriptor_count"],
        "logs_read": False,
        "outcome_columns_read": [],
    }, "operator_finalization_sha256")


def _preparation_identity(path: Path) -> dict[str, object]:
    prepared = _strict_local_json(path, label="controller preparation")
    if prepared.get("schema_version") != controller.CONTROLLER_PREPARATION_SCHEMA:
        _fail("controller preparation schema differs")
    return _identity(
        prepared.get("controller_manifest_identity"),
        label="prepared controller manifest",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate one hard230 score run")
    sub = parser.add_subparsers(dest="command", required=True)
    launch = sub.add_parser("launch")
    launch.add_argument("--preparation-file", type=Path, required=True)
    launch.add_argument("--image-uri", required=True)
    launch.add_argument("--output-file", type=Path, required=True)
    for name in ("status", "finalize"):
        command = sub.add_parser(name)
        command.add_argument("--launch-result-file", type=Path, required=True)
        command.add_argument("--output-file", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    store = runtime.GCSExactTransportV1()
    if args.command == "launch":
        result = launch_controller_run_v1(
            controller_manifest_identity=_preparation_identity(args.preparation_file),
            image_uri=args.image_uri,
            store=store,
        )
    else:
        launch_result = _strict_local_json(
            args.launch_result_file, label="launch result"
        )
        result = (
            status_controller_run_v1(launch_result=launch_result, store=store)
            if args.command == "status"
            else finalize_controller_run_v1(
                launch_result=launch_result, store=store
            )
        )
    _write_local(args.output_file, result)
    sys.stdout.buffer.write(_canonical(result) + b"\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        Hard230R6ScoreRunV1Error,
        runtime.RunHard230R6CloudV1Error,
        entrypoint.Hard230R6CloudEntrypointV1Error,
        controller.Hard230R6RunControllerV1Error,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


__all__ = [
    "Hard230R6ScoreRunV1Error",
    "configure_flags_v1",
    "execute_argv_v1",
    "finalize_controller_run_v1",
    "launch_controller_run_v1",
    "status_controller_run_v1",
    "task_describe_argv_v1",
]
