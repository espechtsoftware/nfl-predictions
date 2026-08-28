"""Thin Cloud Run operator contract for the F7/F8/F9 population bank.

The scientific population authority already owns the 54 task requests.  This
module adds only the score-path seams that were missing around it: pin the
frozen broad-selection manifest, publish the derived manifest once, describe
the two permitted Cloud Run shapes (task-0 smoke or full 54), validate one
known execution, and exact-open the deterministic task-result names.

No function in this module lists a bucket, reads a realized outcome, creates a
Cloud Run job, or changes a production default.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
import re
from typing import Final

from nfl_dfs.research import (
    corpus_r6_population_challenger_authority_v1 as authority,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_runtime_v1 as runtime,
)
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles


PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
REUSED_JOB_NAME: Final = "atlas-minimal-c-s2023-w1-v1"
REUSED_JOB_UID: Final = "d6e4b8c1-5950-46b7-8869-7e34dbf29ad2"

FROZEN_BROAD_SELECTION_TASK_MANIFEST_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-current-bank-crossed-screens/"
        "20260828-r6-current-bank-crossed-screen-v7/authorities/"
        "task-manifests/01-broad-selection-receipt.json"
    ),
    "generation": "1787949078843910",
    "sha256": "daba17d22c019450bf90031271d6399e6ab5f227ab88e45bc9b07247d8e715fb",
    "bytes": 295_788,
}

TASK0_SCOPE: Final = "task0"
FULL54_SCOPE: Final = "full54"
SCOPES: Final = (TASK0_SCOPE, FULL54_SCOPE)

DISPATCHER_PYTHON: Final = "/usr/local/bin/python3.11"
DISPATCHER_SCRIPT: Final = authority.DISPATCHER_IMAGE_PATH
DISPATCHER_ARGS: Final = ("-I", DISPATCHER_SCRIPT, "task")
TASK_TIMEOUT_SECONDS: Final = 21_600
CPU: Final = "8"
MEMORY: Final = "32Gi"
ENV_DELIMITER: Final = "|"

PREPARE_REQUEST_SCHEMA: Final = (
    "corpus-r6-population-challenger-cloud-prepare-request/v1"
)
PREPARATION_SCHEMA: Final = (
    "corpus-r6-population-challenger-cloud-preparation/v1"
)
JOB_CONFIGURATION_SCHEMA: Final = (
    "corpus-r6-population-challenger-cloud-job-configuration/v1"
)
LAUNCH_RESULT_SCHEMA: Final = (
    "corpus-r6-population-challenger-cloud-launch/v1"
)
STATUS_SCHEMA: Final = "corpus-r6-population-challenger-cloud-status/v1"
COLLECTION_SCHEMA: Final = (
    "corpus-r6-population-challenger-task-result-collection/v1"
)

MAXIMUM_PROVIDER_JSON_BYTES: Final = 8_000_000
MAXIMUM_PROVIDER_STDERR_BYTES: Final = 256_000

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]
OpenKnown = Callable[[str, int], tuple[bytes, Mapping[str, object]]]

_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE_RE: Final = re.compile(
    r"[a-z0-9][a-z0-9._/-]{0,511}@sha256:[0-9a-f]{64}\Z"
)
_EXECUTION_RE: Final = re.compile(r"[a-z][a-z0-9-]{0,127}\Z")
_UID_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,127}\Z")


class CorpusR6PopulationChallengerCloudV1Error(RuntimeError):
    """The thin population Cloud Run operator failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6PopulationChallengerCloudV1Error(message)


def canonical_bytes_v1(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusR6PopulationChallengerCloudV1Error(
            "operator value is not canonical JSON"
        ) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_bytes_v1(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    return {**body, field: canonical_sha256_v1(body)}


def _require_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    observed = value.get(field)
    body = dict(value)
    body.pop(field, None)
    if (
        type(observed) is not str
        or _SHA_RE.fullmatch(observed) is None
        or observed != canonical_sha256_v1(body)
    ):
        _fail(f"{label} self-hash differs")


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
        return authority.object_identity_v1(value, label=label)
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationChallengerCloudV1Error(str(exc)) from exc


def strict_json_bytes_v1(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")

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
    except CorpusR6PopulationChallengerCloudV1Error:
        raise
    except Exception as exc:
        raise CorpusR6PopulationChallengerCloudV1Error(
            f"{label} is not strict UTF-8 JSON"
        ) from exc
    item = _mapping(value, label=label)
    if canonical_bytes_v1(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _scope_count(scope: object) -> int:
    if scope == TASK0_SCOPE:
        return 1
    if scope == FULL54_SCOPE:
        return authority.TASK_COUNT
    _fail("population launch scope must be task0 or full54")


def _validate_image_uri(value: object) -> str:
    if type(value) is not str or _IMAGE_RE.fullmatch(value) is None:
        _fail("immutable image URI must be digest-pinned")
    return value


def _validate_output_prefix(value: object) -> str:
    if type(value) is not str:
        _fail("population output prefix differs")
    try:
        return authority._safe_output_prefix(value)
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationChallengerCloudV1Error(str(exc)) from exc


def validate_prepare_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="population prepare request")
    expected = {"schema_version", "output_prefix", "code_commit", "image_uri"}
    if set(item) != expected or item.get("schema_version") != PREPARE_REQUEST_SCHEMA:
        _fail("population prepare request fields/schema differ")
    prefix = _validate_output_prefix(item["output_prefix"])
    commit = item["code_commit"]
    if type(commit) is not str or _COMMIT_RE.fullmatch(commit) is None:
        _fail("population prepare code commit differs")
    image = _validate_image_uri(item["image_uri"])
    return {
        "schema_version": PREPARE_REQUEST_SCHEMA,
        "output_prefix": prefix,
        "code_commit": commit,
        "image_uri": image,
    }


def _job_environment_v1(
    *, manifest_identity: Mapping[str, object], code_commit: str,
    image_digest: str,
) -> dict[str, str]:
    identity_text = canonical_bytes_v1(
        _identity(manifest_identity, label="population task manifest")
    ).decode("utf-8")
    if len(identity_text.encode("utf-8")) > 2_048:
        _fail("population manifest identity exceeds environment ceiling")
    environment = {
        "CODE_SHA": code_commit,
        "GOOGLE_CLOUD_PROJECT": PROJECT,
        "R6_RUNTIME_IMAGE_DIGEST": image_digest,
        authority.ENABLE_ENV: "1",
        authority.MANIFEST_IDENTITY_ENV: identity_text,
    }
    if (
        _COMMIT_RE.fullmatch(code_commit) is None
        or not image_digest.startswith("sha256:")
        or _SHA_RE.fullmatch(image_digest[7:]) is None
        or any(
            ENV_DELIMITER in key or ENV_DELIMITER in value or "=" in key
            for key, value in environment.items()
        )
    ):
        _fail("population job environment differs")
    return environment


def _environment_flag_v1(environment: Mapping[str, str]) -> str:
    pairs = [f"{key}={environment[key]}" for key in sorted(environment)]
    return f"^{ENV_DELIMITER}^" + ENV_DELIMITER.join(pairs)


def build_job_configuration_v1(
    *, manifest_identity: Mapping[str, object], code_commit: str,
    image_uri: str, scope: str,
) -> dict[str, object]:
    count = _scope_count(scope)
    image = _validate_image_uri(image_uri)
    digest = image.rsplit("@", 1)[1]
    environment = _job_environment_v1(
        manifest_identity=manifest_identity,
        code_commit=code_commit,
        image_digest=digest,
    )
    flags = {
        "--args": (
            f"^{ENV_DELIMITER}^"
            + ENV_DELIMITER.join(DISPATCHER_ARGS)
        ),
        "--clear-cloudsql-instances": True,
        "--clear-network": True,
        "--clear-secrets": True,
        "--clear-volume-mounts": True,
        "--clear-volumes": True,
        "--clear-vpc-connector": True,
        "--command": DISPATCHER_PYTHON,
        "--cpu": CPU,
        "--image": image,
        "--max-retries": 0,
        "--memory": MEMORY,
        "--parallelism": count,
        "--set-env-vars": _environment_flag_v1(environment),
        "--task-timeout": f"{TASK_TIMEOUT_SECONDS}s",
        "--tasks": count,
        "--workdir": "",
    }
    return _with_hash({
        "schema_version": JOB_CONFIGURATION_SCHEMA,
        "scope": scope,
        "project_id": PROJECT,
        "location": REGION,
        "reused_job_name": REUSED_JOB_NAME,
        "expected_job_uid": REUSED_JOB_UID,
        "image_uri": image,
        "image_digest": digest,
        "command": [DISPATCHER_PYTHON],
        "args": list(DISPATCHER_ARGS),
        "environment": environment,
        "task_count": count,
        "parallelism": count,
        "max_retries": 0,
        "timeout_seconds": TASK_TIMEOUT_SECONDS,
        "resources": {"cpu": CPU, "memory": MEMORY},
        "gcloud_update_flags": flags,
        "new_job_creation_allowed": False,
        "outcomes_read": False,
    }, field="job_configuration_sha256")


def prepare_population_manifest_v1(
    *, request: object, read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    retained = validate_prepare_request_v1(request)
    source_identity = _identity(
        FROZEN_BROAD_SELECTION_TASK_MANIFEST_IDENTITY,
        label="frozen broad-selection task manifest",
    )
    image_digest = str(retained["image_uri"]).rsplit("@", 1)[1]
    try:
        manifest = authority.build_task_manifest_v1(
            source_task_manifest_identity=source_identity,
            output_prefix=str(retained["output_prefix"]),
            code_commit=str(retained["code_commit"]),
            image_digest=image_digest,
            reused_job_name=REUSED_JOB_NAME,
            read_exact=read_exact,
        )
        manifest_uri = (
            f"{retained['output_prefix']}authorities/task-manifest.json"
        )
        manifest_identity = authority.publish_canonical_create_once_v1(
            uri=manifest_uri,
            value=manifest,
            maximum_bytes=authority.MAXIMUM_TASK_MANIFEST_BYTES,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationChallengerCloudV1Error(str(exc)) from exc
    smoke = build_job_configuration_v1(
        manifest_identity=manifest_identity,
        code_commit=str(retained["code_commit"]),
        image_uri=str(retained["image_uri"]),
        scope=TASK0_SCOPE,
    )
    full = build_job_configuration_v1(
        manifest_identity=manifest_identity,
        code_commit=str(retained["code_commit"]),
        image_uri=str(retained["image_uri"]),
        scope=FULL54_SCOPE,
    )
    return _with_hash({
        "schema_version": PREPARATION_SCHEMA,
        "source_task_manifest_identity": source_identity,
        "population_task_manifest_identity": manifest_identity,
        "population_task_manifest_sha256": manifest["task_manifest_sha256"],
        "output_prefix": retained["output_prefix"],
        "code_commit": retained["code_commit"],
        "image_uri": retained["image_uri"],
        "image_digest": image_digest,
        "project_id": PROJECT,
        "location": REGION,
        "reused_job_name": REUSED_JOB_NAME,
        "expected_job_uid": REUSED_JOB_UID,
        "task_count": authority.TASK_COUNT,
        "profile_order": list(profiles.PROFILE_ORDER),
        "solves_per_task": authority.SOLVES_PER_TASK,
        "job_configurations": {
            TASK0_SCOPE: smoke,
            FULL54_SCOPE: full,
        },
        "outcomes_read": False,
    }, field="preparation_sha256")


def validate_preparation_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="population preparation")
    expected = {
        "schema_version", "source_task_manifest_identity",
        "population_task_manifest_identity", "population_task_manifest_sha256",
        "output_prefix", "code_commit", "image_uri", "image_digest",
        "project_id", "location", "reused_job_name", "expected_job_uid",
        "task_count", "profile_order", "solves_per_task",
        "job_configurations", "outcomes_read", "preparation_sha256",
    }
    if set(item) != expected or item.get("schema_version") != PREPARATION_SCHEMA:
        _fail("population preparation fields/schema differ")
    _require_hash(item, field="preparation_sha256", label="population preparation")
    source = _identity(item["source_task_manifest_identity"], label="source manifest")
    manifest_identity = _identity(
        item["population_task_manifest_identity"], label="population manifest"
    )
    image = _validate_image_uri(item["image_uri"])
    commit = item["code_commit"]
    manifest_sha = item["population_task_manifest_sha256"]
    if (
        source != FROZEN_BROAD_SELECTION_TASK_MANIFEST_IDENTITY
        or type(commit) is not str
        or _COMMIT_RE.fullmatch(commit) is None
        or type(manifest_sha) is not str
        or _SHA_RE.fullmatch(manifest_sha) is None
        or item["image_digest"] != image.rsplit("@", 1)[1]
        or item["project_id"] != PROJECT
        or item["location"] != REGION
        or item["reused_job_name"] != REUSED_JOB_NAME
        or item["expected_job_uid"] != REUSED_JOB_UID
        or item["task_count"] != authority.TASK_COUNT
        or item["profile_order"] != list(profiles.PROFILE_ORDER)
        or item["solves_per_task"] != authority.SOLVES_PER_TASK
        or item["outcomes_read"] is not False
        or manifest_identity["uri"]
        != f"{_validate_output_prefix(item['output_prefix'])}authorities/task-manifest.json"
    ):
        _fail("population preparation fixed authority differs")
    configs = _mapping(item["job_configurations"], label="job configurations")
    expected_configs = {
        scope: build_job_configuration_v1(
            manifest_identity=manifest_identity,
            code_commit=commit,
            image_uri=image,
            scope=scope,
        )
        for scope in SCOPES
    }
    if configs != expected_configs:
        _fail("population preparation job configurations differ")
    return item


def job_configuration_v1(
    preparation: object, *, scope: str,
) -> dict[str, object]:
    retained = validate_preparation_v1(preparation)
    _scope_count(scope)
    return dict(retained["job_configurations"][scope])


def configure_argv_v1(*, flags_path: str) -> list[str]:
    if type(flags_path) is not str or not flags_path.startswith("/") or "\x00" in flags_path:
        _fail("configuration flags path must be absolute")
    return [
        "gcloud", "run", "jobs", "update", REUSED_JOB_NAME,
        "--project", PROJECT,
        "--region", REGION,
        "--quiet",
        f"--flags-file={flags_path}",
        "--format=json",
    ]


def job_describe_argv_v1() -> list[str]:
    return [
        "gcloud", "run", "jobs", "describe", REUSED_JOB_NAME,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ]


def execution_describe_argv_v1(execution_name: str) -> list[str]:
    execution = _execution_name(execution_name)
    return [
        "gcloud", "run", "jobs", "executions", "describe", execution,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ]


def execute_argv_v1() -> list[str]:
    return [
        "gcloud", "run", "jobs", "execute", REUSED_JOB_NAME,
        "--project", PROJECT, "--region", REGION,
        "--async", "--format=value(metadata.name)",
    ]


def _resource_tail(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} differs")
    return value.rstrip("/").rsplit("/", 1)[-1]


def _execution_name(value: object) -> str:
    name = _resource_tail(value, label="execution name")
    if (
        _EXECUTION_RE.fullmatch(name) is None
        or not name.startswith(REUSED_JOB_NAME + "-")
    ):
        _fail("execution name is not owned by the reused job")
    return name


def _metadata_identity(
    value: Mapping[str, object], *, expected_name: str | None = None,
) -> dict[str, str]:
    metadata = _mapping(value.get("metadata"), label="provider metadata")
    name = _resource_tail(metadata.get("name"), label="provider name")
    uid = metadata.get("uid")
    generation = str(metadata.get("generation", ""))
    if (
        expected_name is not None and name != expected_name
        or type(uid) is not str
        or _UID_RE.fullmatch(uid) is None
        or not generation.isdigit()
        or int(generation) < 1
    ):
        _fail("provider name/UID/generation differs")
    return {"name": name, "uid": uid, "generation": generation}


def validate_job_identity_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="reused job description")
    identity = _metadata_identity(item, expected_name=REUSED_JOB_NAME)
    if identity["uid"] != REUSED_JOB_UID:
        _fail("reused job UID differs")
    status = _mapping(item.get("status", {}), label="reused job status")
    latest = status.get("latestCreatedExecution")
    latest_name: str | None = None
    if latest not in (None, {}):
        latest_row = _mapping(latest, label="latest execution reference")
        latest_name = _execution_name(latest_row.get("name"))
    return {
        "job_name": REUSED_JOB_NAME,
        "job_uid": REUSED_JOB_UID,
        "job_generation": identity["generation"],
        "latest_execution_name": latest_name,
    }


def _environment_rows(value: object) -> dict[str, str]:
    rows = _sequence(value, label="job environment")
    result: dict[str, str] = {}
    for raw in rows:
        row = _mapping(raw, label="job environment row")
        if set(row) != {"name", "value"}:
            _fail("secret-backed or malformed job environment is forbidden")
        name, value = row["name"], row["value"]
        if type(name) is not str or type(value) is not str or name in result:
            _fail("job environment name/value differs")
        result[name] = value
    return result


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


def validate_exact_job_configuration_v1(
    value: object, *, preparation: object, scope: str,
) -> dict[str, object]:
    item = _mapping(value, label="configured reused job")
    identity = validate_job_identity_v1(item)
    configuration = job_configuration_v1(preparation, scope=scope)
    spec = _mapping(item.get("spec"), label="job spec")
    outer = _mapping(
        _mapping(spec.get("template"), label="job outer template").get("spec"),
        label="job outer template spec",
    )
    task = _mapping(
        _mapping(outer.get("template"), label="job task template").get("spec"),
        label="job task template spec",
    )
    containers = _sequence(task.get("containers"), label="job containers")
    if len(containers) != 1:
        _fail("reused job must contain exactly one container")
    container = _mapping(containers[0], label="job container")
    resources = _mapping(container.get("resources", {}), label="job resources")
    timeout = str(task.get("timeoutSeconds", "")).removesuffix("s")
    if (
        outer.get("taskCount") != configuration["task_count"]
        or outer.get("parallelism") != configuration["parallelism"]
        or task.get("maxRetries") != 0
        or not timeout.isdigit()
        or int(timeout) != TASK_TIMEOUT_SECONDS
        or container.get("image") != configuration["image_uri"]
        or container.get("command", []) != configuration["command"]
        or container.get("args", []) != configuration["args"]
        or _environment_rows(container.get("env", []))
        != configuration["environment"]
        or _mapping(resources.get("limits", {}), label="resource limits")
        != configuration["resources"]
        or container.get("workingDir", "") != ""
        or container.get("volumeMounts", []) != []
        or task.get("volumes", []) != []
        or _network_present(item.get("spec", {}))
    ):
        _fail("configured reused job does not equal the requested scope")
    return {**identity, "scope": scope, "exact_configuration_validated": True}


def _completed(status: Mapping[str, object]) -> bool:
    conditions = status.get("conditions", [])
    if not isinstance(conditions, Sequence):
        return False
    for raw in conditions:
        if isinstance(raw, Mapping) and raw.get("type") == "Completed" and (
            raw.get("state") == "CONDITION_SUCCEEDED"
            or raw.get("status") is True
            or raw.get("status") == "True"
        ):
            return True
    return False


def build_execution_status_v1(
    value: object, *, execution_name: str, scope: str,
) -> dict[str, object]:
    item = _mapping(value, label="population execution description")
    execution = _execution_name(execution_name)
    identity = _metadata_identity(item, expected_name=execution)
    metadata = _mapping(item.get("metadata"), label="execution metadata")
    labels = _mapping(metadata.get("labels", {}), label="execution labels")
    job_label = _resource_tail(
        labels.get("run.googleapis.com/job"), label="execution job label"
    )
    job_uid = labels.get("run.googleapis.com/jobUid")
    spec = _mapping(item.get("spec"), label="execution spec")
    expected_count = _scope_count(scope)
    status = _mapping(item.get("status", {}), label="execution status")
    succeeded = int(status.get("succeededCount", 0) or 0)
    failed = int(status.get("failedCount", 0) or 0)
    cancelled = int(status.get("cancelledCount", 0) or 0)
    if (
        job_label != REUSED_JOB_NAME
        or job_uid != REUSED_JOB_UID
        or spec.get("taskCount") != expected_count
        or min(succeeded, failed, cancelled) < 0
        or succeeded + failed + cancelled > expected_count
    ):
        _fail("population execution job/task identity differs")
    completion_time = status.get("completionTime")
    completed = _completed(status)
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
        "job_name": REUSED_JOB_NAME,
        "job_uid": REUSED_JOB_UID,
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
    execution = _execution_name(execution_name)
    return _with_hash({
        "schema_version": LAUNCH_RESULT_SCHEMA,
        "scope": scope,
        "project_id": PROJECT,
        "location": REGION,
        "job_name": REUSED_JOB_NAME,
        "job_uid": REUSED_JOB_UID,
        "execution_name": execution,
        "expected_task_count": _scope_count(scope),
        "outcomes_read": False,
    }, field="launch_result_sha256")


def validate_launch_result_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="population launch result")
    expected = {
        "schema_version", "scope", "project_id", "location", "job_name",
        "job_uid", "execution_name", "expected_task_count", "outcomes_read",
        "launch_result_sha256",
    }
    if set(item) != expected or item.get("schema_version") != LAUNCH_RESULT_SCHEMA:
        _fail("population launch result fields/schema differ")
    _require_hash(item, field="launch_result_sha256", label="population launch")
    count = _scope_count(item["scope"])
    if (
        item["project_id"] != PROJECT
        or item["location"] != REGION
        or item["job_name"] != REUSED_JOB_NAME
        or item["job_uid"] != REUSED_JOB_UID
        or _execution_name(item["execution_name"]) != item["execution_name"]
        or item["expected_task_count"] != count
        or item["outcomes_read"] is not False
    ):
        _fail("population launch result authority differs")
    return item


def _open_manifest_v1(
    preparation: Mapping[str, object], *, read_exact: ReadExact,
) -> dict[str, object]:
    identity = _identity(
        preparation["population_task_manifest_identity"],
        label="population task manifest",
    )
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail("population task manifest generation-exact bytes differ")
    try:
        manifest = authority.validate_task_manifest_v1(
            strict_json_bytes_v1(raw, label="population task manifest")
        )
        authority.bind_body_to_identity_v1(
            manifest, identity, label="population task manifest"
        )
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationChallengerCloudV1Error(str(exc)) from exc
    if (
        manifest["task_manifest_sha256"]
        != preparation["population_task_manifest_sha256"]
        or manifest["source_task_manifest_identity"]
        != preparation["source_task_manifest_identity"]
        or manifest["code_commit"] != preparation["code_commit"]
        or manifest["image_digest"] != preparation["image_digest"]
        or manifest["reused_job_name"] != REUSED_JOB_NAME
    ):
        _fail("population manifest/preparation binding differs")
    return manifest


def collect_task_results_v1(
    *, preparation: object, launch_result: object, execution_status: object,
    read_exact: ReadExact, open_known: OpenKnown,
) -> dict[str, object]:
    prep = validate_preparation_v1(preparation)
    launch = validate_launch_result_v1(launch_result)
    status = _mapping(execution_status, label="population execution status")
    _require_hash(status, field="status_sha256", label="population status")
    if (
        status.get("schema_version") != STATUS_SCHEMA
        or status.get("scope") != launch["scope"]
        or status.get("execution_name") != launch["execution_name"]
        or status.get("job_uid") != REUSED_JOB_UID
        or status.get("terminal_state") != "SUCCEEDED"
        or status.get("succeeded_count") != launch["expected_task_count"]
        or status.get("failed_count") != 0
        or status.get("cancelled_count") != 0
        or status.get("scientific_outputs_read") is not False
        or status.get("outcomes_read") is not False
    ):
        _fail("population results cannot open before exact execution success")
    manifest = _open_manifest_v1(prep, read_exact=read_exact)
    count = _scope_count(launch["scope"])
    identities: list[dict[str, object]] = []
    result_hashes: list[str] = []
    for index in range(count):
        binding = manifest["task_bindings"][index]
        request = binding["request"]
        uri = request["expected_outputs"]["task_result_uri"]
        raw, identity_value = open_known(uri, authority.MAXIMUM_TASK_RESULT_BYTES)
        identity = _identity(identity_value, label=f"task result[{index}]")
        if (
            identity["uri"] != uri
            or type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("known task result generation-exact bytes differ")
        try:
            result = runtime.validate_task_result_v1(
                strict_json_bytes_v1(raw, label=f"task result[{index}]")
            )
            authority.bind_body_to_identity_v1(
                result, identity, label=f"task result[{index}]"
            )
        except (
            runtime.CorpusR6PopulationChallengerRuntimeV1Error,
            authority.CorpusR6PopulationChallengerAuthorityV1Error,
        ) as exc:
            raise CorpusR6PopulationChallengerCloudV1Error(str(exc)) from exc
        profile_rows = result["profile_results"]
        expected_profile_uris = request["expected_outputs"]["profile_lineup_uris"]
        if (
            result["task_index"] != index
            or result["source_ordinal"] != index
            or result["request_sha256"] != request["request_sha256"]
            or result["source_authority"].get("projection_bundle_identity")
            != request["projection_bundle_identity"]
            or [row["profile_id"] for row in profile_rows]
            != list(profiles.PROFILE_ORDER)
            or any(
                row["lineups_identity"]["uri"]
                != expected_profile_uris[row["profile_id"]]
                for row in profile_rows
            )
        ):
            _fail("task result does not bind its deterministic manifest request")
        identities.append(identity)
        result_hashes.append(result["task_result_sha256"])
    return _with_hash({
        "schema_version": COLLECTION_SCHEMA,
        "scope": launch["scope"],
        "population_task_manifest_identity": prep[
            "population_task_manifest_identity"
        ],
        "population_task_manifest_sha256": prep[
            "population_task_manifest_sha256"
        ],
        "execution_name": launch["execution_name"],
        "task_result_count": count,
        "population_task_result_identities": identities,
        "population_task_result_sha256s": result_hashes,
        "crossed_prepare_ready": launch["scope"] == FULL54_SCOPE,
        "deterministic_names_only": True,
        "bucket_listing_performed": False,
        "outcomes_read": False,
    }, field="collection_sha256")


def build_crossed_prepare_request_v1(
    *, preparation: object, collection: object, output_prefix: str,
) -> dict[str, object]:
    prep = validate_preparation_v1(preparation)
    item = _mapping(collection, label="population result collection")
    _require_hash(item, field="collection_sha256", label="population collection")
    if (
        item.get("schema_version") != COLLECTION_SCHEMA
        or item.get("scope") != FULL54_SCOPE
        or item.get("crossed_prepare_ready") is not True
        or item.get("task_result_count") != authority.TASK_COUNT
        or item.get("population_task_manifest_identity")
        != prep["population_task_manifest_identity"]
        or len(_sequence(
            item.get("population_task_result_identities"),
            label="population result identities",
        )) != authority.TASK_COUNT
    ):
        _fail("population collection is not ready for crossed prepare")
    prefix = _validate_output_prefix(output_prefix)
    return {
        "population_task_manifest_identity": prep[
            "population_task_manifest_identity"
        ],
        "population_task_result_identities": item[
            "population_task_result_identities"
        ],
        "output_prefix": prefix,
        "code_commit": prep["code_commit"],
        "image_digest": prep["image_digest"],
        "reused_job_name": REUSED_JOB_NAME,
    }


__all__ = [
    "COLLECTION_SCHEMA",
    "CorpusR6PopulationChallengerCloudV1Error",
    "FROZEN_BROAD_SELECTION_TASK_MANIFEST_IDENTITY",
    "FULL54_SCOPE",
    "JOB_CONFIGURATION_SCHEMA",
    "LAUNCH_RESULT_SCHEMA",
    "PREPARATION_SCHEMA",
    "PREPARE_REQUEST_SCHEMA",
    "PROJECT",
    "REGION",
    "REUSED_JOB_NAME",
    "REUSED_JOB_UID",
    "SCOPES",
    "STATUS_SCHEMA",
    "TASK0_SCOPE",
    "build_crossed_prepare_request_v1",
    "build_execution_status_v1",
    "build_job_configuration_v1",
    "build_launch_result_v1",
    "canonical_bytes_v1",
    "collect_task_results_v1",
    "configure_argv_v1",
    "execute_argv_v1",
    "execution_describe_argv_v1",
    "job_configuration_v1",
    "job_describe_argv_v1",
    "prepare_population_manifest_v1",
    "strict_json_bytes_v1",
    "validate_exact_job_configuration_v1",
    "validate_job_identity_v1",
    "validate_launch_result_v1",
    "validate_preparation_v1",
    "validate_prepare_request_v1",
]
