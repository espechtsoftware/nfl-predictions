"""Minimal task0/full54 operator seam for the fixed L2b panel job.

The operator only updates and executes the already-existing UID-pinned Cloud
Run job.  It knows the 54 deterministic task-result names from the manifest,
never lists storage, and never reads realized outcomes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_l2b_panel_cloud_v1 as panel


PROJECT: Final = panel.FIXED_GCP_PROJECT
REGION: Final = "us-central1"
TASK0_SCOPE: Final = panel.TASK0_SCOPE
FULL54_SCOPE: Final = panel.FULL54_SCOPE
SCOPES: Final = (TASK0_SCOPE, FULL54_SCOPE)
ENV_DELIMITER: Final = "|"

JOB_CONFIGURATION_SCHEMA: Final = "corpus-r6-l2b-operator-job-configuration/v1"
LAUNCH_RESULT_SCHEMA: Final = "corpus-r6-l2b-operator-launch/v1"
STATUS_SCHEMA: Final = "corpus-r6-l2b-operator-status/v1"
COLLECTION_SCHEMA: Final = "corpus-r6-l2b-operator-collection/v1"

MAXIMUM_PROVIDER_JSON_BYTES: Final = 8_000_000
MAXIMUM_PROVIDER_STDERR_BYTES: Final = 256_000

ReadExact = Callable[[Mapping[str, object]], bytes]
OpenKnown = Callable[[str, int], tuple[bytes, Mapping[str, object]]]

_EXECUTION = re.compile(r"[a-z][a-z0-9-]{0,127}\Z")
_UID = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,127}\Z")


class CorpusR6L2BPanelOperatorV1Error(RuntimeError):
    """The fixed-job L2b operator failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6L2BPanelOperatorV1Error(message)


def canonical_bytes_v1(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6L2BPanelOperatorV1Error(str(exc)) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_bytes_v1(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6L2BPanelOperatorV1Error(str(exc)) from exc


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    return {**body, field: canonical_sha256_v1(body)}


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    retained = value.get(field)
    body = {key: row for key, row in value.items() if key != field}
    if (
        type(retained) is not str
        or len(retained) != 64
        or retained != canonical_sha256_v1(body)
    ):
        _fail(f"{label} self-hash differs")


def strict_json_bytes_v1(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6L2BPanelOperatorV1Error(
            f"{label} is not UTF-8 JSON"
        ) from exc
    item = _mapping(value, label=label)
    if canonical_bytes_v1(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _scope_count(scope: object) -> int:
    if scope == TASK0_SCOPE:
        return 1
    if scope == FULL54_SCOPE:
        return panel.TASK_COUNT
    _fail("L2b operator scope must be task0 or full54")


def validate_preparation_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="L2b preparation")
    expected = {
        "schema_version", "contract_id", "task_count", "task_manifest_identity",
        "task_manifest_sha256", "cloud_run_job_configuration",
        "real_artifact_smoke_required_before_fanout", "fanout_launched",
        *panel._FALSE_AUTHORITY_FIELDS,
    }
    if set(item) != expected:
        _fail("L2b preparation fields differ")
    config = _mapping(
        item.get("cloud_run_job_configuration"), label="L2b base job configuration"
    )
    expected_config = {
        "schema_version", "contract_id", "reused_job_name", "reused_job_uid",
        "task_count", "parallelism", "max_retries", "timeout_seconds", "cpu",
        "memory", "immutable_image_digest", "container_command",
        "container_args", "environment", "new_job_creation_allowed",
        "iam_mutation_required", "launch_submission_authority",
    }
    environment = _mapping(config.get("environment"), label="L2b base environment")
    manifest_identity = _identity(
        item.get("task_manifest_identity"), label="L2b manifest identity"
    )
    if (
        item.get("schema_version") != panel.PREPARATION_RESULT_SCHEMA
        or item.get("contract_id") != panel.CONTRACT_ID
        or item.get("task_count") != panel.TASK_COUNT
        or type(item.get("task_manifest_sha256")) is not str
        or len(str(item["task_manifest_sha256"])) != 64
        or item.get("real_artifact_smoke_required_before_fanout") is not True
        or item.get("fanout_launched") is not False
        or any(item.get(field) is not False for field in panel._FALSE_AUTHORITY_FIELDS)
        or set(config) != expected_config
        or config.get("schema_version") != panel.JOB_CONFIGURATION_SCHEMA
        or config.get("contract_id") != panel.CONTRACT_ID
        or config.get("reused_job_name") != panel.REUSED_JOB_NAME
        or config.get("reused_job_uid") != panel.REUSED_JOB_UID
        or config.get("task_count") != panel.TASK_COUNT
        or config.get("parallelism") != panel.TASK_COUNT
        or config.get("max_retries") != 0
        or config.get("timeout_seconds") != panel.TASK_TIMEOUT_SECONDS
        or config.get("cpu") != panel.REUSED_JOB_CPU
        or config.get("memory") != panel.REUSED_JOB_MEMORY
        or config.get("container_command") + config.get("container_args")
        != list(panel.ENTRYPOINT_COMMAND)
        or config.get("new_job_creation_allowed") is not False
        or config.get("iam_mutation_required") is not False
        or config.get("launch_submission_authority") is not False
        or environment.get(panel.ENABLE_ENV) != "1"
        or environment.get(panel.EXECUTION_SCOPE_ENV) != FULL54_SCOPE
        or environment.get(panel.REUSED_JOB_UID_ENV) != panel.REUSED_JOB_UID
        or environment.get(panel.MANIFEST_IDENTITY_ENV)
        != canonical_bytes_v1(manifest_identity).decode("utf-8")
    ):
        _fail("L2b preparation/base configuration authority differs")
    return item


def _open_manifest_and_image_v1(
    preparation: Mapping[str, object], *, read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object], str]:
    try:
        manifest, manifest_identity = panel._open_manifest(
            manifest_identity=preparation["task_manifest_identity"],
            read_exact=read_exact,
        )
    except panel.CorpusR6L2BPanelCloudV1Error as exc:
        raise CorpusR6L2BPanelOperatorV1Error(str(exc)) from exc
    if (
        manifest["task_manifest_sha256"] != preparation["task_manifest_sha256"]
        or manifest["reused_job_name"] != panel.REUSED_JOB_NAME
        or manifest["reused_job_uid"] != panel.REUSED_JOB_UID
    ):
        _fail("L2b preparation/manifest binding differs")
    try:
        build, _ = panel._read_terminal_build_receipt(
            manifest["terminal_build_receipt_identity"],
            source_commit_sha=str(manifest["source_commit_sha"]),
            immutable_image_digest=str(manifest["immutable_image_digest"]),
            read_exact=read_exact,
            label="L2b terminal build receipt",
        )
    except panel.CorpusR6L2BPanelCloudV1Error as exc:
        raise CorpusR6L2BPanelOperatorV1Error(str(exc)) from exc
    image_tag = str(build["image_tag"])
    image_repository = image_tag.rsplit(":", 1)[0]
    image_uri = f"{image_repository}@{manifest['immutable_image_digest']}"
    return manifest, manifest_identity, image_uri


def _environment_flag(environment: Mapping[str, str]) -> str:
    if any(
        ENV_DELIMITER in key or ENV_DELIMITER in value or "=" in key
        for key, value in environment.items()
    ):
        _fail("L2b operator environment cannot be encoded exactly")
    return f"^{ENV_DELIMITER}^" + ENV_DELIMITER.join(
        f"{key}={environment[key]}" for key in sorted(environment)
    )


def build_job_configuration_v1(
    *, preparation: object, scope: str, read_exact: ReadExact,
) -> dict[str, object]:
    prep = validate_preparation_v1(preparation)
    count = _scope_count(scope)
    manifest, manifest_identity, image_uri = _open_manifest_and_image_v1(
        prep, read_exact=read_exact
    )
    base = prep["cloud_run_job_configuration"]
    environment = dict(base["environment"])
    environment[panel.EXECUTION_SCOPE_ENV] = scope
    command = [panel.ENTRYPOINT_COMMAND[0]]
    args = list(panel.ENTRYPOINT_COMMAND[1:])
    flags = {
        "--args": f"^{ENV_DELIMITER}^" + ENV_DELIMITER.join(args),
        "--clear-cloudsql-instances": True,
        "--clear-network": True,
        "--clear-secrets": True,
        "--clear-volume-mounts": True,
        "--clear-volumes": True,
        "--clear-vpc-connector": True,
        "--command": command[0],
        "--cpu": str(base["cpu"]),
        "--image": image_uri,
        "--max-retries": 0,
        "--memory": str(base["memory"]),
        "--parallelism": count,
        "--set-env-vars": _environment_flag(environment),
        "--task-timeout": f"{base['timeout_seconds']}s",
        "--tasks": count,
        "--workdir": "",
    }
    body = {
        "schema_version": JOB_CONFIGURATION_SCHEMA,
        "scope": scope,
        "project_id": PROJECT,
        "location": REGION,
        "reused_job_name": panel.REUSED_JOB_NAME,
        "expected_job_uid": panel.REUSED_JOB_UID,
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["task_manifest_sha256"],
        "image_uri": image_uri,
        "image_digest": manifest["immutable_image_digest"],
        "command": command,
        "args": args,
        "environment": environment,
        "task_count": count,
        "parallelism": count,
        "max_retries": 0,
        "timeout_seconds": int(base["timeout_seconds"]),
        "resources": {"cpu": str(base["cpu"]), "memory": str(base["memory"])},
        "gcloud_update_flags": flags,
        "new_job_creation_allowed": False,
        "outcomes_read": False,
    }
    return _with_hash(body, field="job_configuration_sha256")


def configure_argv_v1(*, flags_path: str) -> list[str]:
    if type(flags_path) is not str or not flags_path.startswith("/") or "\x00" in flags_path:
        _fail("configuration flags path must be absolute")
    return [
        "gcloud", "run", "jobs", "update", panel.REUSED_JOB_NAME,
        "--project", PROJECT, "--region", REGION, "--quiet",
        f"--flags-file={flags_path}", "--format=json",
    ]


def job_describe_argv_v1() -> list[str]:
    return [
        "gcloud", "run", "jobs", "describe", panel.REUSED_JOB_NAME,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ]


def execute_argv_v1() -> list[str]:
    return [
        "gcloud", "run", "jobs", "execute", panel.REUSED_JOB_NAME,
        "--project", PROJECT, "--region", REGION,
        "--async", "--format=value(metadata.name)",
    ]


def execution_describe_argv_v1(execution_name: str) -> list[str]:
    execution = _execution_name(execution_name)
    return [
        "gcloud", "run", "jobs", "executions", "describe", execution,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ]


def _tail(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} differs")
    return value.rstrip("/").rsplit("/", 1)[-1]


def _execution_name(value: object) -> str:
    name = _tail(value, label="execution name")
    if _EXECUTION.fullmatch(name) is None or not name.startswith(
        panel.REUSED_JOB_NAME + "-"
    ):
        _fail("execution name is not owned by the reused L2b job")
    return name


def _metadata(value: Mapping[str, object], *, expected_name: str) -> dict[str, str]:
    metadata = _mapping(value.get("metadata"), label="provider metadata")
    name = _tail(metadata.get("name"), label="provider resource name")
    uid = metadata.get("uid")
    generation = str(metadata.get("generation", ""))
    if (
        name != expected_name
        or type(uid) is not str
        or _UID.fullmatch(uid) is None
        or not generation.isdigit()
        or int(generation) < 1
    ):
        _fail("provider resource identity differs")
    return {"name": name, "uid": uid, "generation": generation}


def validate_job_identity_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="L2b reused job")
    identity = _metadata(item, expected_name=panel.REUSED_JOB_NAME)
    if identity["uid"] != panel.REUSED_JOB_UID:
        _fail("L2b reused job UID differs")
    status = _mapping(item.get("status", {}), label="L2b job status")
    latest = status.get("latestCreatedExecution")
    latest_name = None
    if latest not in (None, {}):
        latest_name = _execution_name(
            _mapping(latest, label="latest execution").get("name")
        )
    return {
        "job_name": panel.REUSED_JOB_NAME,
        "job_uid": panel.REUSED_JOB_UID,
        "job_generation": identity["generation"],
        "latest_execution_name": latest_name,
    }


def _environment(value: object) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in _sequence(value, label="job environment"):
        row = _mapping(raw, label="job environment row")
        if set(row) != {"name", "value"}:
            _fail("secret-backed or malformed job environment is forbidden")
        name, item = row["name"], row["value"]
        if type(name) is not str or type(item) is not str or name in result:
            _fail("job environment name/value differs")
        result[name] = item
    return result


def validate_exact_job_configuration_v1(
    value: object, *, configuration: object,
) -> dict[str, object]:
    item = _mapping(value, label="configured L2b job")
    config = _mapping(configuration, label="requested L2b job configuration")
    _self_hash(config, field="job_configuration_sha256", label="job configuration")
    identity = validate_job_identity_v1(item)
    outer = _mapping(
        _mapping(
            _mapping(item.get("spec"), label="job spec").get("template"),
            label="job outer template",
        ).get("spec"),
        label="job outer template spec",
    )
    task = _mapping(
        _mapping(outer.get("template"), label="job task template").get("spec"),
        label="job task template spec",
    )
    containers = _sequence(task.get("containers"), label="job containers")
    if len(containers) != 1:
        _fail("L2b reused job must contain exactly one container")
    container = _mapping(containers[0], label="job container")
    resources = _mapping(container.get("resources", {}), label="job resources")
    timeout = str(task.get("timeoutSeconds", "")).removesuffix("s")
    if (
        outer.get("taskCount") != config["task_count"]
        or outer.get("parallelism") != config["parallelism"]
        or task.get("maxRetries") != 0
        or not timeout.isdigit()
        or int(timeout) != config["timeout_seconds"]
        or container.get("image") != config["image_uri"]
        or container.get("command", []) != config["command"]
        or container.get("args", []) != config["args"]
        or _environment(container.get("env", [])) != config["environment"]
        or _mapping(resources.get("limits", {}), label="resource limits")
        != config["resources"]
        or container.get("workingDir", "") != ""
        or container.get("volumeMounts", []) != []
        or task.get("volumes", []) != []
    ):
        _fail("configured L2b job does not equal the requested scope")
    return {**identity, "scope": config["scope"], "exact_configuration_validated": True}


def _completed(status: Mapping[str, object]) -> bool:
    conditions = status.get("conditions", [])
    if not isinstance(conditions, Sequence):
        return False
    return any(
        isinstance(row, Mapping)
        and row.get("type") == "Completed"
        and (
            row.get("state") == "CONDITION_SUCCEEDED"
            or row.get("status") is True
            or row.get("status") == "True"
        )
        for row in conditions
    )


def build_execution_status_v1(
    value: object, *, execution_name: str, scope: str,
) -> dict[str, object]:
    item = _mapping(value, label="L2b execution")
    execution = _execution_name(execution_name)
    identity = _metadata(item, expected_name=execution)
    metadata = _mapping(item.get("metadata"), label="execution metadata")
    labels = _mapping(metadata.get("labels", {}), label="execution labels")
    job_name = _tail(labels.get("run.googleapis.com/job"), label="execution job")
    expected_count = _scope_count(scope)
    spec = _mapping(item.get("spec"), label="execution spec")
    status = _mapping(item.get("status", {}), label="execution status")
    succeeded = int(status.get("succeededCount", 0) or 0)
    failed = int(status.get("failedCount", 0) or 0)
    cancelled = int(status.get("cancelledCount", 0) or 0)
    if (
        job_name != panel.REUSED_JOB_NAME
        or labels.get("run.googleapis.com/jobUid") != panel.REUSED_JOB_UID
        or spec.get("taskCount") != expected_count
        or min(succeeded, failed, cancelled) < 0
        or succeeded + failed + cancelled > expected_count
    ):
        _fail("L2b execution job/task identity differs")
    completed = _completed(status)
    completion_time = status.get("completionTime")
    if completed and completion_time and succeeded == expected_count and not (
        failed or cancelled
    ):
        state = "SUCCEEDED"
    elif completion_time or completed or failed or cancelled:
        state = "FAILED"
    else:
        state = "ACTIVE"
    return _with_hash({
        "schema_version": STATUS_SCHEMA,
        "scope": scope,
        "project_id": PROJECT,
        "location": REGION,
        "job_name": panel.REUSED_JOB_NAME,
        "job_uid": panel.REUSED_JOB_UID,
        "execution_name": execution,
        "execution_uid": identity["uid"],
        "execution_generation": identity["generation"],
        "expected_task_count": expected_count,
        "succeeded_count": succeeded,
        "failed_count": failed,
        "cancelled_count": cancelled,
        "terminal_state": state,
        "logs_read": False,
        "scientific_outputs_read": False,
        "outcomes_read": False,
    }, field="status_sha256")


def build_launch_result_v1(*, execution_name: str, scope: str) -> dict[str, object]:
    return _with_hash({
        "schema_version": LAUNCH_RESULT_SCHEMA,
        "scope": scope,
        "project_id": PROJECT,
        "location": REGION,
        "job_name": panel.REUSED_JOB_NAME,
        "job_uid": panel.REUSED_JOB_UID,
        "execution_name": _execution_name(execution_name),
        "expected_task_count": _scope_count(scope),
        "outcomes_read": False,
    }, field="launch_result_sha256")


def validate_launch_result_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="L2b launch result")
    expected = {
        "schema_version", "scope", "project_id", "location", "job_name",
        "job_uid", "execution_name", "expected_task_count", "outcomes_read",
        "launch_result_sha256",
    }
    if set(item) != expected or item.get("schema_version") != LAUNCH_RESULT_SCHEMA:
        _fail("L2b launch result fields differ")
    _self_hash(item, field="launch_result_sha256", label="L2b launch result")
    if (
        item.get("project_id") != PROJECT
        or item.get("location") != REGION
        or item.get("job_name") != panel.REUSED_JOB_NAME
        or item.get("job_uid") != panel.REUSED_JOB_UID
        or _execution_name(item.get("execution_name")) != item.get("execution_name")
        or item.get("expected_task_count") != _scope_count(item.get("scope"))
        or item.get("outcomes_read") is not False
    ):
        _fail("L2b launch result authority differs")
    return item


def collect_task_results_v1(
    *, preparation: object, launch_result: object, execution_status: object,
    read_exact: ReadExact, open_known: OpenKnown,
) -> dict[str, object]:
    prep = validate_preparation_v1(preparation)
    launch = validate_launch_result_v1(launch_result)
    status = _mapping(execution_status, label="L2b execution status")
    _self_hash(status, field="status_sha256", label="L2b execution status")
    if (
        status.get("schema_version") != STATUS_SCHEMA
        or status.get("scope") != launch["scope"]
        or status.get("execution_name") != launch["execution_name"]
        or status.get("job_uid") != panel.REUSED_JOB_UID
        or status.get("terminal_state") != "SUCCEEDED"
        or status.get("succeeded_count") != launch["expected_task_count"]
        or status.get("failed_count") != 0
        or status.get("cancelled_count") != 0
        or status.get("scientific_outputs_read") is not False
        or status.get("outcomes_read") is not False
    ):
        _fail("L2b results cannot open before exact execution success")
    try:
        manifest, manifest_identity = panel._open_manifest(
            manifest_identity=prep["task_manifest_identity"],
            read_exact=read_exact,
        )
    except panel.CorpusR6L2BPanelCloudV1Error as exc:
        raise CorpusR6L2BPanelOperatorV1Error(str(exc)) from exc
    count = _scope_count(launch["scope"])
    identities: list[dict[str, object]] = []
    result_hashes: list[str] = []
    for index in range(count):
        task_row = manifest["task_rows"][index]
        uri = str(task_row["task_result_uri"])
        raw, identity_value = open_known(uri, panel.MAXIMUM_TASK_RESULT_BYTES)
        identity = _identity(identity_value, label=f"L2b task result[{index}]")
        if (
            identity["uri"] != uri
            or type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("known L2b task-result bytes differ")
        try:
            result = panel._validate_task_result_v1(
                panel._strict_json(raw, label=f"L2b task result[{index}]")
            )
            panel._validate_task_result_lineage_v1(
                manifest=manifest,
                retained_manifest_identity=manifest_identity,
                task_index=index,
                task_result_identity=identity,
                result=result,
                read_exact=read_exact,
            )
        except panel.CorpusR6L2BPanelCloudV1Error as exc:
            raise CorpusR6L2BPanelOperatorV1Error(str(exc)) from exc
        identities.append(identity)
        result_hashes.append(str(result["task_result_sha256"]))
    return _with_hash({
        "schema_version": COLLECTION_SCHEMA,
        "scope": launch["scope"],
        "task_manifest_identity": manifest_identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "execution_name": launch["execution_name"],
        "task_result_count": count,
        "task_result_identities": identities,
        "task_result_sha256s": result_hashes,
        "real_artifact_smoke_complete": launch["scope"] == TASK0_SCOPE,
        "panel_finalization_ready": launch["scope"] == FULL54_SCOPE,
        "deterministic_names_only": True,
        "bucket_listing_performed": False,
        "outcomes_read": False,
    }, field="collection_sha256")


__all__ = [
    "COLLECTION_SCHEMA", "CorpusR6L2BPanelOperatorV1Error", "FULL54_SCOPE",
    "JOB_CONFIGURATION_SCHEMA", "LAUNCH_RESULT_SCHEMA", "SCOPES",
    "STATUS_SCHEMA", "TASK0_SCOPE", "build_execution_status_v1",
    "build_job_configuration_v1", "build_launch_result_v1",
    "canonical_bytes_v1", "canonical_sha256_v1", "collect_task_results_v1",
    "configure_argv_v1", "execute_argv_v1", "execution_describe_argv_v1",
    "job_describe_argv_v1", "strict_json_bytes_v1",
    "validate_exact_job_configuration_v1", "validate_job_identity_v1",
    "validate_launch_result_v1", "validate_preparation_v1",
]
