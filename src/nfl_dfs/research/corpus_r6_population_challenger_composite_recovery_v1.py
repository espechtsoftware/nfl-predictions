"""Outcome-blind composite collection for one failed population task.

This module does not execute population science.  It permits exactly one
pre-registered recovery shape: an already-successful task-0 smoke supplies
ordinal 0, while a later full-54 execution supplies ordinals 1 through 53
after failing only task 0.  The recovery intent must be published create-once
before any of the 53 not-yet-collected task-result bodies are opened.
"""

from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Final, Mapping, Sequence

from . import corpus_r6_population_challenger_authority_v1 as authority
from . import corpus_r6_population_challenger_cloud_v1 as population_cloud
from . import corpus_r6_population_challenger_runtime_v1 as runtime
from . import corpus_r6_population_profiles_v1 as profiles


class CorpusR6PopulationChallengerCompositeRecoveryV1Error(RuntimeError):
    """Raised when the fixed composite-recovery contract differs."""


RECOVERY_ID: Final = "20260829-f7-f8-f9-full54-task0-composite-v1"
AMENDMENT_REPORT_PATH: Final = (
    "reports/2026-08-29-r6-f7-f8-f9-full54-task0-composite-collection-"
    "recovery-amendment.md"
)
INTENT_SCHEMA: Final = (
    "corpus-r6-population-challenger-composite-recovery-intent/v1"
)
TASK_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-population-challenger-administrative-task-envelope/v1"
)
COMPOSITE_COLLECTION_SCHEMA: Final = (
    "corpus-r6-population-challenger-composite-task-result-collection/v1"
)
RECOVERY_RECEIPT_SCHEMA: Final = (
    "corpus-r6-population-challenger-composite-recovery-receipt/v1"
)
PREPARE_RESULT_SCHEMA: Final = (
    "corpus-r6-population-challenger-composite-recovery-prepare-result/v1"
)
COLLECT_RESULT_SCHEMA: Final = (
    "corpus-r6-population-challenger-composite-recovery-collect-result/v1"
)

MAXIMUM_INTENT_BYTES: Final = 512_000
MAXIMUM_COLLECTION_BYTES: Final = 512_000
MAXIMUM_CROSSED_REQUEST_BYTES: Final = 256_000
MAXIMUM_RECOVERY_RECEIPT_BYTES: Final = 256_000

_SHA_RE: Final = re.compile(r"[0-9a-f]{64}")
_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}")
_TASK_NAME_SUFFIX_RE: Final = re.compile(r"-task([0-9]+)\Z")
_SAFE_ROOT: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-current-bank-crossed-screens/"
)


def _fail(message: str) -> None:
    raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(message)


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
        raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(
            "recovery value is not canonical JSON"
        ) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_bytes_v1(value)).hexdigest()


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
    except CorpusR6PopulationChallengerCompositeRecoveryV1Error:
        raise
    except Exception as exc:
        raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(
            f"{label} is not strict UTF-8 JSON"
        ) from exc
    item = _mapping(value, label=label)
    if canonical_bytes_v1(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _integer(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail(f"{label} must be a nonnegative integer")
    return value


def _sha(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _SHA_RE.fullmatch(text) is None:
        _fail(f"{label} must be lowercase SHA-256")
    return text


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return authority.object_identity_v1(value, label=label)
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(str(exc)) from exc


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


def _safe_prefix(value: object, *, label: str) -> str:
    prefix = _string(value, label=label)
    if (
        not prefix.startswith(_SAFE_ROOT)
        or not prefix.endswith("/")
        or ".." in prefix
        or "?" in prefix
        or "#" in prefix
        or "//" in prefix.removeprefix("gs://")
    ):
        _fail(f"{label} escapes the fixed research root")
    return prefix


def _recovery_outputs(population_prefix: str) -> dict[str, str]:
    root = (
        f"{population_prefix}authorities/"
        "full54-task0-composite-recovery-v1/"
    )
    return {
        "intent_uri": f"{root}intent.json",
        "collection_uri": f"{root}collection.json",
        "crossed_prepare_request_uri": f"{root}crossed-prepare-request.json",
        "recovery_receipt_uri": f"{root}recovery-receipt.json",
    }


def _validate_status_v1(
    value: object,
    *,
    launch: Mapping[str, object],
    expected_terminal: str,
    expected_succeeded: int,
    expected_failed: int,
) -> dict[str, object]:
    item = _mapping(value, label="population execution status")
    expected = {
        "cancelled_count",
        "execution_generation",
        "execution_name",
        "execution_uid",
        "expected_task_count",
        "failed_count",
        "job_name",
        "job_uid",
        "location",
        "logs_read",
        "outcomes_read",
        "project_id",
        "schema_version",
        "scientific_outputs_read",
        "scope",
        "status_sha256",
        "succeeded_count",
        "terminal_state",
    }
    if set(item) != expected:
        _fail("population status fields differ")
    _require_hash(item, field="status_sha256", label="population status")
    if (
        item.get("schema_version") != population_cloud.STATUS_SCHEMA
        or item.get("scope") != launch["scope"]
        or item.get("project_id") != population_cloud.PROJECT
        or item.get("location") != population_cloud.REGION
        or item.get("job_name") != population_cloud.REUSED_JOB_NAME
        or item.get("job_uid") != population_cloud.REUSED_JOB_UID
        or item.get("execution_name") != launch["execution_name"]
        or item.get("expected_task_count") != launch["expected_task_count"]
        or item.get("terminal_state") != expected_terminal
        or item.get("succeeded_count") != expected_succeeded
        or item.get("failed_count") != expected_failed
        or item.get("cancelled_count") != 0
        or item.get("logs_read") is not False
        or item.get("scientific_outputs_read") is not False
        or item.get("outcomes_read") is not False
    ):
        _fail("population status is outside the fixed recovery state")
    _string(item.get("execution_uid"), label="execution UID")
    _string(item.get("execution_generation"), label="execution generation")
    return item


def _validate_task0_collection_v1(
    value: object,
    *,
    preparation: Mapping[str, object],
    launch: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="task0 population collection")
    expected = {
        "bucket_listing_performed",
        "collection_sha256",
        "crossed_prepare_ready",
        "deterministic_names_only",
        "execution_name",
        "outcomes_read",
        "population_task_manifest_identity",
        "population_task_manifest_sha256",
        "population_task_result_identities",
        "population_task_result_sha256s",
        "schema_version",
        "scope",
        "task_result_count",
    }
    if set(item) != expected:
        _fail("task0 population collection fields differ")
    _require_hash(item, field="collection_sha256", label="task0 collection")
    identities = _sequence(
        item.get("population_task_result_identities"),
        label="task0 result identities",
    )
    result_hashes = _sequence(
        item.get("population_task_result_sha256s"),
        label="task0 result self-hashes",
    )
    if (
        item.get("schema_version") != population_cloud.COLLECTION_SCHEMA
        or item.get("scope") != population_cloud.TASK0_SCOPE
        or item.get("execution_name") != launch["execution_name"]
        or item.get("task_result_count") != 1
        or len(identities) != 1
        or len(result_hashes) != 1
        or item.get("population_task_manifest_identity")
        != preparation["population_task_manifest_identity"]
        or item.get("population_task_manifest_sha256")
        != preparation["population_task_manifest_sha256"]
        or item.get("crossed_prepare_ready") is not False
        or item.get("deterministic_names_only") is not True
        or item.get("bucket_listing_performed") is not False
        or item.get("outcomes_read") is not False
    ):
        _fail("task0 collection does not bind the successful smoke")
    _identity(identities[0], label="task0 result identity")
    _sha(result_hashes[0], label="task0 result self-hash")
    return item


def _task_index_from_name(name: str) -> int:
    match = _TASK_NAME_SUFFIX_RE.search(name)
    if match is None:
        _fail("administrative task name lacks a canonical index")
    return int(match.group(1))


def _owner_uid(
    owner_references: object, *, kind: str, expected_name: str
) -> str:
    matches = []
    for raw in _sequence(owner_references, label="task owner references"):
        row = _mapping(raw, label="task owner reference")
        if row.get("kind") == kind and row.get("name") == expected_name:
            matches.append(row)
    if len(matches) != 1:
        _fail(f"administrative task lacks one exact {kind} owner")
    return _string(matches[0].get("uid"), label=f"{kind} owner UID")


def _normalize_task_spec_v1(
    value: object,
    *,
    expected_configuration: Mapping[str, object],
) -> dict[str, object]:
    spec = _mapping(value, label="administrative task spec")
    containers = _sequence(spec.get("containers"), label="task containers")
    if len(containers) != 1:
        _fail("administrative task must contain exactly one container")
    container = _mapping(containers[0], label="task container")
    env_rows = _sequence(container.get("env", []), label="task environment")
    environment: dict[str, str] = {}
    for raw in env_rows:
        row = _mapping(raw, label="task environment row")
        if set(row) != {"name", "value"}:
            _fail("task environment row fields differ")
        name = _string(row["name"], label="environment name")
        value_text = _string(row["value"], label=f"environment {name}")
        if name in environment:
            _fail("task environment repeats a name")
        environment[name] = value_text
    command = _sequence(container.get("command"), label="task command")
    args = _sequence(container.get("args"), label="task args")
    if any(type(row) is not str for row in command + args):
        _fail("task command/args must contain strings")
    resources = _mapping(container.get("resources"), label="task resources")
    limits = _mapping(resources.get("limits"), label="task resource limits")
    timeout_raw = spec.get("timeoutSeconds")
    if isinstance(timeout_raw, str) and timeout_raw.isdecimal():
        timeout = int(timeout_raw)
    elif type(timeout_raw) is int:
        timeout = timeout_raw
    else:
        _fail("task timeout is not canonical seconds")
    normalized = {
        "image": _string(container.get("image"), label="task image"),
        "command": command,
        "args": args,
        "environment": environment,
        "resources": limits,
        "max_retries": _integer(spec.get("maxRetries"), label="task retries"),
        "timeout_seconds": timeout,
        "service_account_name": _string(
            spec.get("serviceAccountName"), label="task service account"
        ),
    }
    if (
        normalized["image"] != expected_configuration["image_uri"]
        or normalized["command"] != expected_configuration["command"]
        or normalized["args"] != expected_configuration["args"]
        or normalized["environment"] != expected_configuration["environment"]
        or normalized["resources"] != expected_configuration["resources"]
        or normalized["max_retries"] != expected_configuration["max_retries"]
        or normalized["timeout_seconds"]
        != expected_configuration["timeout_seconds"]
    ):
        _fail("administrative task spec differs from frozen preparation")
    return normalized


def build_administrative_task_envelope_v1(
    value: object,
    *,
    preparation: object,
    launch_result: object,
    expected_outcome: str,
) -> dict[str, object]:
    """Project a Cloud Run Task description without opening its log URI."""
    prep = population_cloud.validate_preparation_v1(preparation)
    launch = population_cloud.validate_launch_result_v1(launch_result)
    if expected_outcome not in {"SUCCEEDED", "FAILED_NONZERO"}:
        _fail("administrative task outcome differs")
    item = _mapping(value, label="administrative task description")
    metadata = _mapping(item.get("metadata"), label="task metadata")
    labels = _mapping(metadata.get("labels"), label="task labels")
    status = _mapping(item.get("status"), label="task status")
    task_name = _string(metadata.get("name"), label="task name")
    task_index = _task_index_from_name(task_name)
    status_index = status.get("index")
    if status_index is not None and status_index != task_index:
        _fail("task status index differs from task name")
    execution_name = _string(launch["execution_name"], label="execution name")
    if (
        task_index != 0
        or labels.get("run.googleapis.com/execution") != execution_name
        or labels.get("run.googleapis.com/job") != population_cloud.REUSED_JOB_NAME
    ):
        _fail("administrative evidence is not exact task 0")
    job_uid = _owner_uid(
        metadata.get("ownerReferences"),
        kind="Job",
        expected_name=population_cloud.REUSED_JOB_NAME,
    )
    execution_uid = _owner_uid(
        metadata.get("ownerReferences"),
        kind="Execution",
        expected_name=execution_name,
    )
    if job_uid != population_cloud.REUSED_JOB_UID:
        _fail("administrative task job UID differs")
    configuration = population_cloud.job_configuration_v1(
        prep, scope=str(launch["scope"])
    )
    task_spec = _normalize_task_spec_v1(
        item.get("spec"), expected_configuration=configuration
    )
    conditions = {
        str(row.get("type")): _mapping(row, label="task condition")
        for row in (
            _mapping(raw, label="task condition")
            for raw in _sequence(status.get("conditions"), label="task conditions")
        )
    }
    completed = conditions.get("Completed", {})
    started = conditions.get("Started", {})
    last_attempt = _mapping(
        status.get("lastAttemptResult", {}), label="task last attempt"
    )
    last_status = _mapping(
        last_attempt.get("status", {}), label="task last-attempt status"
    )
    if started.get("status") not in {True, "True"}:
        _fail("administrative task was not started")
    if expected_outcome == "SUCCEEDED":
        if (
            completed.get("status") not in {True, "True"}
            or labels.get("run.googleapis.com/runningState") != "Succeeded"
            or "exitCode" in last_attempt
        ):
            _fail("task0 smoke is not administratively successful")
        provider_reason = None
        exit_code = None
        provider_status_code = None
    else:
        if (
            completed.get("status") not in {False, "False"}
            or completed.get("reason") != "NonZeroExitCode"
            or labels.get("run.googleapis.com/runningState") != "Failed"
            or last_attempt.get("exitCode") != 1
            or last_status.get("code") != 10
        ):
            _fail("full54 task0 is not the exact nonzero-exit failure")
        provider_reason = "NonZeroExitCode"
        exit_code = 1
        provider_status_code = 10
    body = {
        "schema_version": TASK_ENVELOPE_SCHEMA,
        "task_name": task_name,
        "task_index": task_index,
        "execution_name": execution_name,
        "execution_uid": execution_uid,
        "job_name": population_cloud.REUSED_JOB_NAME,
        "job_uid": job_uid,
        "task_spec": task_spec,
        "start_time": _string(status.get("startTime"), label="task start time"),
        "completion_time": _string(
            status.get("completionTime"), label="task completion time"
        ),
        "terminal_outcome": expected_outcome,
        "provider_reason": provider_reason,
        "exit_code": exit_code,
        "provider_status_code": provider_status_code,
        "logs_read": False,
        "scientific_outputs_read": False,
        "outcomes_read": False,
    }
    return _with_hash(body, field="task_envelope_sha256")


def validate_administrative_task_envelope_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="administrative task envelope")
    expected = {
        "schema_version",
        "task_name",
        "task_index",
        "execution_name",
        "execution_uid",
        "job_name",
        "job_uid",
        "task_spec",
        "start_time",
        "completion_time",
        "terminal_outcome",
        "provider_reason",
        "exit_code",
        "provider_status_code",
        "logs_read",
        "scientific_outputs_read",
        "outcomes_read",
        "task_envelope_sha256",
    }
    if set(item) != expected or item.get("schema_version") != TASK_ENVELOPE_SCHEMA:
        _fail("administrative task envelope fields/schema differ")
    _require_hash(item, field="task_envelope_sha256", label="task envelope")
    if (
        item.get("task_index") != 0
        or item.get("job_name") != population_cloud.REUSED_JOB_NAME
        or item.get("job_uid") != population_cloud.REUSED_JOB_UID
        or item.get("terminal_outcome") not in {"SUCCEEDED", "FAILED_NONZERO"}
        or item.get("logs_read") is not False
        or item.get("scientific_outputs_read") is not False
        or item.get("outcomes_read") is not False
    ):
        _fail("administrative task envelope safety differs")
    if item["terminal_outcome"] == "SUCCEEDED":
        if any(item.get(key) is not None for key in (
            "provider_reason", "exit_code", "provider_status_code"
        )):
            _fail("successful task envelope retains failure fields")
    elif (
        item.get("provider_reason") != "NonZeroExitCode"
        or item.get("exit_code") != 1
        or item.get("provider_status_code") != 10
    ):
        _fail("failed task envelope reason differs")
    _mapping(item.get("task_spec"), label="task envelope spec")
    return item


def build_recovery_intent_v1(
    *,
    preparation: object,
    population_manifest: object,
    smoke_launch_result: object,
    smoke_status: object,
    smoke_collection: object,
    full54_launch_result: object,
    full54_status: object,
    smoke_task_description: object,
    failed_task_description: object,
    crossed_output_prefix: str,
    recovery_code_commit: str,
    recovery_source_sha256s: object,
    amendment_report_sha256: str,
) -> dict[str, object]:
    """Build the create-once intent without opening any new result body."""
    prep = population_cloud.validate_preparation_v1(preparation)
    smoke_launch = population_cloud.validate_launch_result_v1(smoke_launch_result)
    full_launch = population_cloud.validate_launch_result_v1(full54_launch_result)
    if (
        smoke_launch["scope"] != population_cloud.TASK0_SCOPE
        or full_launch["scope"] != population_cloud.FULL54_SCOPE
    ):
        _fail("recovery launch scopes differ")
    smoke_terminal = _validate_status_v1(
        smoke_status,
        launch=smoke_launch,
        expected_terminal="SUCCEEDED",
        expected_succeeded=1,
        expected_failed=0,
    )
    full_terminal = _validate_status_v1(
        full54_status,
        launch=full_launch,
        expected_terminal="FAILED",
        expected_succeeded=53,
        expected_failed=1,
    )
    retained_smoke_collection = _validate_task0_collection_v1(
        smoke_collection, preparation=prep, launch=smoke_launch
    )
    try:
        manifest = authority.validate_task_manifest_v1(population_manifest)
        manifest_identity = authority.bind_body_to_identity_v1(
            manifest,
            prep["population_task_manifest_identity"],
            label="population task manifest",
        )
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(str(exc)) from exc
    if (
        manifest["task_manifest_sha256"]
        != prep["population_task_manifest_sha256"]
        or manifest["code_commit"] != prep["code_commit"]
        or manifest["image_digest"] != prep["image_digest"]
        or manifest["reused_job_name"] != prep["reused_job_name"]
    ):
        _fail("population manifest/preparation recovery binding differs")
    smoke_envelope = build_administrative_task_envelope_v1(
        smoke_task_description,
        preparation=prep,
        launch_result=smoke_launch,
        expected_outcome="SUCCEEDED",
    )
    failed_envelope = build_administrative_task_envelope_v1(
        failed_task_description,
        preparation=prep,
        launch_result=full_launch,
        expected_outcome="FAILED_NONZERO",
    )
    if (
        smoke_envelope["execution_uid"] != smoke_terminal["execution_uid"]
        or failed_envelope["execution_uid"] != full_terminal["execution_uid"]
        or smoke_envelope["task_spec"] != failed_envelope["task_spec"]
    ):
        _fail("smoke/full task0 administrative science surface differs")
    task0_request = manifest["task_bindings"][0]["request"]
    manifest_identity_text = canonical_bytes_v1(manifest_identity).decode("utf-8")
    task_environment = smoke_envelope["task_spec"]["environment"]
    if (
        task_environment.get(authority.MANIFEST_IDENTITY_ENV)
        != manifest_identity_text
        or task_environment.get("CODE_SHA") != prep["code_commit"]
        or task_environment.get("R6_RUNTIME_IMAGE_DIGEST") != prep["image_digest"]
        or task_environment.get(authority.ENABLE_ENV) != "1"
    ):
        _fail("task0 administrative environment differs from exact request authority")
    task0_identity = _identity(
        retained_smoke_collection["population_task_result_identities"][0],
        label="successful smoke task0 result",
    )
    expected_task0_uri = task0_request["expected_outputs"]["task_result_uri"]
    if task0_identity["uri"] != expected_task0_uri:
        _fail("successful smoke result URI differs from task0 request")
    source_hashes = _mapping(
        recovery_source_sha256s, label="recovery source SHA-256s"
    )
    if set(source_hashes) != {"core", "operator"}:
        _fail("recovery source inventory differs")
    for label, digest in source_hashes.items():
        _sha(digest, label=f"{label} source SHA-256")
    if _COMMIT_RE.fullmatch(recovery_code_commit) is None:
        _fail("recovery code commit must be lowercase 40-hex")
    report_sha = _sha(amendment_report_sha256, label="amendment report SHA-256")
    crossed_prefix = _safe_prefix(
        crossed_output_prefix, label="population-crossed output prefix"
    )
    population_prefix = _safe_prefix(
        prep["output_prefix"], label="population output prefix"
    )
    outputs = _recovery_outputs(population_prefix)
    body = {
        "schema_version": INTENT_SCHEMA,
        "recovery_id": RECOVERY_ID,
        "amendment_report_path": AMENDMENT_REPORT_PATH,
        "amendment_report_sha256": report_sha,
        "recovery_code_commit": recovery_code_commit,
        "recovery_source_sha256s": source_hashes,
        "original_science_code_commit": prep["code_commit"],
        "preparation": prep,
        "population_task_manifest_identity": manifest_identity,
        "population_task_manifest_sha256": manifest["task_manifest_sha256"],
        "task0_task_binding_sha256": manifest["task_bindings"][0][
            "task_binding_sha256"
        ],
        "task0_request_sha256": task0_request["request_sha256"],
        "task0_projection_bundle_identity": task0_request[
            "projection_bundle_identity"
        ],
        "task0_expected_outputs_sha256": canonical_sha256_v1(
            task0_request["expected_outputs"]
        ),
        "task0_smoke_result_identity": task0_identity,
        "task0_smoke_result_sha256": retained_smoke_collection[
            "population_task_result_sha256s"
        ][0],
        "smoke_launch_result": smoke_launch,
        "smoke_terminal_status": smoke_terminal,
        "smoke_task_envelope": smoke_envelope,
        "full54_launch_result": full_launch,
        "full54_terminal_status": full_terminal,
        "failed_task_envelope": failed_envelope,
        "task_result_provenance_plan": [
            {
                "first_task_index": 0,
                "last_task_index": 0,
                "execution_name": smoke_launch["execution_name"],
                "execution_uid": smoke_terminal["execution_uid"],
                "terminal_status_sha256": smoke_terminal["status_sha256"],
                "source": "successful-same-science-task0-smoke",
            },
            {
                "first_task_index": 1,
                "last_task_index": 53,
                "execution_name": full_launch["execution_name"],
                "execution_uid": full_terminal["execution_uid"],
                "terminal_status_sha256": full_terminal["status_sha256"],
                "source": "successful-complement-of-full54-execution",
            },
        ],
        "result_open_order": list(range(authority.TASK_COUNT)),
        "crossed_output_prefix": crossed_prefix,
        "outputs": outputs,
        "policy": {
            "intent_must_be_create_once_before_result_opens": True,
            "new_execution_allowed": False,
            "task_recompute_allowed": False,
            "worker_or_science_change_allowed": False,
            "bucket_listing_allowed": False,
            "cloud_logging_allowed": False,
            "historical_scoring_licensed": False,
            "uses_realized_outcomes": False,
            "production_change_performed": False,
        },
    }
    intent = _with_hash(body, field="recovery_intent_sha256")
    if len(canonical_bytes_v1(intent)) > MAXIMUM_INTENT_BYTES:
        _fail("recovery intent exceeds its byte ceiling")
    return validate_recovery_intent_v1(intent)


def validate_recovery_intent_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="composite recovery intent")
    expected = {
        "schema_version",
        "recovery_id",
        "amendment_report_path",
        "amendment_report_sha256",
        "recovery_code_commit",
        "recovery_source_sha256s",
        "original_science_code_commit",
        "preparation",
        "population_task_manifest_identity",
        "population_task_manifest_sha256",
        "task0_task_binding_sha256",
        "task0_request_sha256",
        "task0_projection_bundle_identity",
        "task0_expected_outputs_sha256",
        "task0_smoke_result_identity",
        "task0_smoke_result_sha256",
        "smoke_launch_result",
        "smoke_terminal_status",
        "smoke_task_envelope",
        "full54_launch_result",
        "full54_terminal_status",
        "failed_task_envelope",
        "task_result_provenance_plan",
        "result_open_order",
        "crossed_output_prefix",
        "outputs",
        "policy",
        "recovery_intent_sha256",
    }
    if set(item) != expected or item.get("schema_version") != INTENT_SCHEMA:
        _fail("composite recovery intent fields/schema differ")
    _require_hash(item, field="recovery_intent_sha256", label="recovery intent")
    prep = population_cloud.validate_preparation_v1(item["preparation"])
    smoke_launch = population_cloud.validate_launch_result_v1(
        item["smoke_launch_result"]
    )
    full_launch = population_cloud.validate_launch_result_v1(
        item["full54_launch_result"]
    )
    smoke_status = _validate_status_v1(
        item["smoke_terminal_status"],
        launch=smoke_launch,
        expected_terminal="SUCCEEDED",
        expected_succeeded=1,
        expected_failed=0,
    )
    full_status = _validate_status_v1(
        item["full54_terminal_status"],
        launch=full_launch,
        expected_terminal="FAILED",
        expected_succeeded=53,
        expected_failed=1,
    )
    smoke_envelope = validate_administrative_task_envelope_v1(
        item["smoke_task_envelope"]
    )
    failed_envelope = validate_administrative_task_envelope_v1(
        item["failed_task_envelope"]
    )
    smoke_task_spec = _mapping(
        smoke_envelope["task_spec"], label="smoke task spec"
    )
    task_environment = _mapping(
        smoke_task_spec["environment"], label="smoke task environment"
    )
    manifest_identity_text = canonical_bytes_v1(
        prep["population_task_manifest_identity"]
    ).decode("utf-8")
    outputs = _mapping(item["outputs"], label="recovery output topology")
    if (
        item.get("recovery_id") != RECOVERY_ID
        or item.get("amendment_report_path") != AMENDMENT_REPORT_PATH
        or _COMMIT_RE.fullmatch(str(item.get("recovery_code_commit"))) is None
        or item.get("original_science_code_commit") != prep["code_commit"]
        or item.get("population_task_manifest_identity")
        != prep["population_task_manifest_identity"]
        or item.get("population_task_manifest_sha256")
        != prep["population_task_manifest_sha256"]
        or smoke_launch["scope"] != population_cloud.TASK0_SCOPE
        or full_launch["scope"] != population_cloud.FULL54_SCOPE
        or smoke_envelope["terminal_outcome"] != "SUCCEEDED"
        or failed_envelope["terminal_outcome"] != "FAILED_NONZERO"
        or smoke_envelope["execution_name"] != smoke_launch["execution_name"]
        or failed_envelope["execution_name"] != full_launch["execution_name"]
        or smoke_envelope["execution_uid"] != smoke_status["execution_uid"]
        or failed_envelope["execution_uid"] != full_status["execution_uid"]
        or smoke_envelope["task_spec"] != failed_envelope["task_spec"]
        or task_environment.get(authority.MANIFEST_IDENTITY_ENV)
        != manifest_identity_text
        or task_environment.get("CODE_SHA") != prep["code_commit"]
        or task_environment.get("R6_RUNTIME_IMAGE_DIGEST")
        != prep["image_digest"]
        or task_environment.get(authority.ENABLE_ENV) != "1"
        or item.get("result_open_order") != list(range(authority.TASK_COUNT))
        or item.get("task_result_provenance_plan")
        != [
            {
                "first_task_index": 0,
                "last_task_index": 0,
                "execution_name": smoke_launch["execution_name"],
                "execution_uid": smoke_status["execution_uid"],
                "terminal_status_sha256": smoke_status["status_sha256"],
                "source": "successful-same-science-task0-smoke",
            },
            {
                "first_task_index": 1,
                "last_task_index": 53,
                "execution_name": full_launch["execution_name"],
                "execution_uid": full_status["execution_uid"],
                "terminal_status_sha256": full_status["status_sha256"],
                "source": "successful-complement-of-full54-execution",
            },
        ]
        or outputs != _recovery_outputs(
            _safe_prefix(prep["output_prefix"], label="population output prefix")
        )
        or item.get("policy")
        != {
            "intent_must_be_create_once_before_result_opens": True,
            "new_execution_allowed": False,
            "task_recompute_allowed": False,
            "worker_or_science_change_allowed": False,
            "bucket_listing_allowed": False,
            "cloud_logging_allowed": False,
            "historical_scoring_licensed": False,
            "uses_realized_outcomes": False,
            "production_change_performed": False,
        }
    ):
        _fail("composite recovery intent contract differs")
    _safe_prefix(item["crossed_output_prefix"], label="crossed output prefix")
    for field in (
        "amendment_report_sha256",
        "population_task_manifest_sha256",
        "task0_task_binding_sha256",
        "task0_request_sha256",
        "task0_expected_outputs_sha256",
        "task0_smoke_result_sha256",
    ):
        _sha(item[field], label=field)
    source_hashes = _mapping(
        item["recovery_source_sha256s"], label="recovery source hashes"
    )
    if set(source_hashes) != {"core", "operator"}:
        _fail("recovery source inventory differs")
    for field, digest in source_hashes.items():
        _sha(digest, label=f"{field} source hash")
    _identity(item["task0_projection_bundle_identity"], label="task0 projection")
    _identity(item["task0_smoke_result_identity"], label="task0 smoke result")
    return item


def _validate_result_against_request_v1(
    *,
    raw: bytes,
    identity_value: object,
    request: Mapping[str, object],
    index: int,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"task result[{index}]")
    expected_uri = request["expected_outputs"]["task_result_uri"]
    if (
        identity["uri"] != expected_uri
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
        raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(str(exc)) from exc
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
    return result, identity


def collect_composite_results_v1(
    *,
    recovery_intent: object,
    recovery_intent_identity: object,
    read_exact,
    open_known,
) -> tuple[dict[str, object], dict[str, object]]:
    """Open all 54 deterministic results only after exact intent publication."""
    intent = validate_recovery_intent_v1(recovery_intent)
    intent_identity = _identity(recovery_intent_identity, label="recovery intent")
    try:
        authority.bind_body_to_identity_v1(
            intent, intent_identity, label="recovery intent"
        )
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(str(exc)) from exc
    if intent_identity["uri"] != intent["outputs"]["intent_uri"]:
        _fail("recovery intent URI differs from fixed topology")
    try:
        intent_raw = read_exact(intent_identity)
    except Exception as exc:
        raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(
            "published recovery intent generation is unavailable"
        ) from exc
    if intent_raw != canonical_bytes_v1(intent):
        _fail("published recovery intent generation-exact bytes differ")
    manifest_identity = _identity(
        intent["population_task_manifest_identity"],
        label="population task manifest",
    )
    try:
        manifest_raw = read_exact(manifest_identity)
    except Exception as exc:
        raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(
            "population task manifest generation is unavailable"
        ) from exc
    try:
        manifest = authority.validate_task_manifest_v1(
            strict_json_bytes_v1(manifest_raw, label="population task manifest")
        )
        authority.bind_body_to_identity_v1(
            manifest, manifest_identity, label="population task manifest"
        )
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(str(exc)) from exc
    prep = intent["preparation"]
    if (
        manifest["task_manifest_sha256"]
        != intent["population_task_manifest_sha256"]
        or manifest["code_commit"] != prep["code_commit"]
        or manifest["image_digest"] != prep["image_digest"]
        or manifest["reused_job_name"] != prep["reused_job_name"]
    ):
        _fail("reopened population manifest differs from recovery intent")
    task0_request = manifest["task_bindings"][0]["request"]
    if (
        manifest["task_bindings"][0]["task_binding_sha256"]
        != intent["task0_task_binding_sha256"]
        or task0_request["request_sha256"] != intent["task0_request_sha256"]
        or task0_request["projection_bundle_identity"]
        != intent["task0_projection_bundle_identity"]
        or canonical_sha256_v1(task0_request["expected_outputs"])
        != intent["task0_expected_outputs_sha256"]
    ):
        _fail("reopened task0 request differs from pre-result intent")
    identities: list[dict[str, object]] = []
    result_hashes: list[str] = []
    provenance: list[dict[str, object]] = []
    smoke_result_identity = _identity(
        intent["task0_smoke_result_identity"], label="task0 smoke result"
    )
    for index in intent["result_open_order"]:
        request = manifest["task_bindings"][index]["request"]
        try:
            if index == 0:
                identity_value = smoke_result_identity
                raw = read_exact(smoke_result_identity)
                source = intent["task_result_provenance_plan"][0]
            else:
                raw, identity_value = open_known(
                    request["expected_outputs"]["task_result_uri"],
                    authority.MAXIMUM_TASK_RESULT_BYTES,
                )
                source = intent["task_result_provenance_plan"][1]
        except Exception as exc:
            raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(
                f"task result[{index}] is unavailable"
            ) from exc
        result, identity = _validate_result_against_request_v1(
            raw=raw,
            identity_value=identity_value,
            request=request,
            index=index,
        )
        if index == 0 and (
            identity != smoke_result_identity
            or result["task_result_sha256"]
            != intent["task0_smoke_result_sha256"]
        ):
            _fail("task0 result differs from successful smoke collection")
        identities.append(identity)
        result_hashes.append(result["task_result_sha256"])
        provenance.append({
            "task_index": index,
            "source_ordinal": index,
            "task_result_identity": identity,
            "task_result_sha256": result["task_result_sha256"],
            "execution_name": source["execution_name"],
            "execution_uid": source["execution_uid"],
            "terminal_status_sha256": source["terminal_status_sha256"],
            "source": source["source"],
        })
    collection = _with_hash({
        "schema_version": COMPOSITE_COLLECTION_SCHEMA,
        "recovery_id": RECOVERY_ID,
        "recovery_intent_identity": intent_identity,
        "population_task_manifest_identity": manifest_identity,
        "population_task_manifest_sha256": manifest["task_manifest_sha256"],
        "task_result_count": authority.TASK_COUNT,
        "population_task_result_identities": identities,
        "population_task_result_sha256s": result_hashes,
        "task_result_provenance": provenance,
        "task_result_provenance_sha256": canonical_sha256_v1(provenance),
        "crossed_prepare_ready": True,
        "deterministic_names_only": True,
        "bucket_listing_performed": False,
        "logs_read": False,
        "outcomes_read": False,
    }, field="collection_sha256")
    validate_composite_collection_v1(collection, intent=intent)
    crossed_request = {
        "population_task_manifest_identity": manifest_identity,
        "population_task_result_identities": identities,
        "output_prefix": intent["crossed_output_prefix"],
        "code_commit": prep["code_commit"],
        "image_digest": prep["image_digest"],
        "reused_job_name": prep["reused_job_name"],
    }
    if len(canonical_bytes_v1(crossed_request)) > MAXIMUM_CROSSED_REQUEST_BYTES:
        _fail("ordinary crossed prepare request exceeds its byte ceiling")
    return collection, crossed_request


def validate_composite_collection_v1(
    value: object, *, intent: object
) -> dict[str, object]:
    retained_intent = validate_recovery_intent_v1(intent)
    item = _mapping(value, label="composite population collection")
    expected = {
        "schema_version",
        "recovery_id",
        "recovery_intent_identity",
        "population_task_manifest_identity",
        "population_task_manifest_sha256",
        "task_result_count",
        "population_task_result_identities",
        "population_task_result_sha256s",
        "task_result_provenance",
        "task_result_provenance_sha256",
        "crossed_prepare_ready",
        "deterministic_names_only",
        "bucket_listing_performed",
        "logs_read",
        "outcomes_read",
        "collection_sha256",
    }
    if set(item) != expected or item.get("schema_version") != COMPOSITE_COLLECTION_SCHEMA:
        _fail("composite population collection fields/schema differ")
    _require_hash(item, field="collection_sha256", label="composite collection")
    intent_identity = _identity(
        item["recovery_intent_identity"], label="collection recovery intent"
    )
    try:
        authority.bind_body_to_identity_v1(
            retained_intent,
            intent_identity,
            label="collection recovery intent",
        )
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(
            str(exc)
        ) from exc
    identities = _sequence(
        item["population_task_result_identities"], label="result identities"
    )
    result_hashes = _sequence(
        item["population_task_result_sha256s"], label="result self-hashes"
    )
    provenance = _sequence(
        item["task_result_provenance"], label="task result provenance"
    )
    if (
        item.get("recovery_id") != RECOVERY_ID
        or intent_identity["uri"] != retained_intent["outputs"]["intent_uri"]
        or item.get("population_task_manifest_identity")
        != retained_intent["population_task_manifest_identity"]
        or item.get("population_task_manifest_sha256")
        != retained_intent["population_task_manifest_sha256"]
        or item.get("task_result_count") != authority.TASK_COUNT
        or len(identities) != authority.TASK_COUNT
        or len(result_hashes) != authority.TASK_COUNT
        or len(provenance) != authority.TASK_COUNT
        or item.get("task_result_provenance_sha256")
        != canonical_sha256_v1(provenance)
        or item.get("crossed_prepare_ready") is not True
        or item.get("deterministic_names_only") is not True
        or item.get("bucket_listing_performed") is not False
        or item.get("logs_read") is not False
        or item.get("outcomes_read") is not False
    ):
        _fail("composite population collection contract differs")
    smoke_result = _identity(
        retained_intent["task0_smoke_result_identity"], label="smoke result"
    )
    for index, (identity_value, result_sha, provenance_value) in enumerate(
        zip(identities, result_hashes, provenance, strict=True)
    ):
        identity = _identity(identity_value, label=f"result identity[{index}]")
        _sha(result_sha, label=f"result self-hash[{index}]")
        row = _mapping(provenance_value, label=f"result provenance[{index}]")
        expected_source = retained_intent["task_result_provenance_plan"][
            0 if index == 0 else 1
        ]
        if (
            row.get("task_index") != index
            or row.get("source_ordinal") != index
            or row.get("task_result_identity") != identity
            or row.get("task_result_sha256") != result_sha
            or row.get("execution_name") != expected_source["execution_name"]
            or row.get("execution_uid") != expected_source["execution_uid"]
            or row.get("terminal_status_sha256")
            != expected_source["terminal_status_sha256"]
            or row.get("source") != expected_source["source"]
            or (index == 0 and identity != smoke_result)
        ):
            _fail("per-task composite provenance differs")
    if len(canonical_bytes_v1(item)) > MAXIMUM_COLLECTION_BYTES:
        _fail("composite collection exceeds its byte ceiling")
    return item


def build_recovery_receipt_v1(
    *,
    recovery_intent: object,
    recovery_intent_identity: object,
    composite_collection: object,
    composite_collection_identity: object,
    crossed_prepare_request: object,
    crossed_prepare_request_identity: object,
) -> dict[str, object]:
    intent = validate_recovery_intent_v1(recovery_intent)
    intent_identity = _identity(recovery_intent_identity, label="recovery intent")
    try:
        authority.bind_body_to_identity_v1(
            intent, intent_identity, label="recovery intent"
        )
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(str(exc)) from exc
    collection = validate_composite_collection_v1(
        composite_collection, intent=intent
    )
    collection_identity = _identity(
        composite_collection_identity, label="composite collection"
    )
    request = _mapping(crossed_prepare_request, label="crossed prepare request")
    request_identity = _identity(
        crossed_prepare_request_identity, label="crossed prepare request"
    )
    expected_request = {
        "population_task_manifest_identity": intent[
            "population_task_manifest_identity"
        ],
        "population_task_result_identities": collection[
            "population_task_result_identities"
        ],
        "output_prefix": intent["crossed_output_prefix"],
        "code_commit": intent["preparation"]["code_commit"],
        "image_digest": intent["preparation"]["image_digest"],
        "reused_job_name": intent["preparation"]["reused_job_name"],
    }
    for value, identity, label, uri in (
        (
            collection,
            collection_identity,
            "composite collection",
            intent["outputs"]["collection_uri"],
        ),
        (
            request,
            request_identity,
            "crossed prepare request",
            intent["outputs"]["crossed_prepare_request_uri"],
        ),
    ):
        try:
            authority.bind_body_to_identity_v1(value, identity, label=label)
        except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
            raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(
                str(exc)
            ) from exc
        if identity["uri"] != uri:
            _fail(f"{label} URI differs from fixed topology")
    if request != expected_request or set(request) != set(expected_request):
        _fail("ordinary crossed prepare request differs")
    body = {
        "schema_version": RECOVERY_RECEIPT_SCHEMA,
        "recovery_id": RECOVERY_ID,
        "recovery_intent_identity": intent_identity,
        "recovery_intent_sha256": intent["recovery_intent_sha256"],
        "composite_collection_identity": collection_identity,
        "composite_collection_sha256": collection["collection_sha256"],
        "crossed_prepare_request_identity": request_identity,
        "crossed_prepare_request_sha256": canonical_sha256_v1(request),
        "population_task_manifest_identity": intent[
            "population_task_manifest_identity"
        ],
        "population_task_result_identities_sha256": canonical_sha256_v1(
            collection["population_task_result_identities"]
        ),
        "task_result_count": authority.TASK_COUNT,
        "task0_execution_name": intent["smoke_launch_result"]["execution_name"],
        "task0_execution_uid": intent["smoke_terminal_status"]["execution_uid"],
        "tasks_1_53_execution_name": intent["full54_launch_result"][
            "execution_name"
        ],
        "tasks_1_53_execution_uid": intent["full54_terminal_status"][
            "execution_uid"
        ],
        "ordinary_six_field_crossed_request": True,
        "new_execution_launched": False,
        "task_recomputed": False,
        "bucket_listing_performed": False,
        "logs_read": False,
        "outcomes_read": False,
    }
    receipt = _with_hash(body, field="recovery_receipt_sha256")
    if len(canonical_bytes_v1(receipt)) > MAXIMUM_RECOVERY_RECEIPT_BYTES:
        _fail("recovery receipt exceeds its byte ceiling")
    return validate_recovery_receipt_v1(receipt, intent=intent)


def validate_recovery_receipt_v1(
    value: object, *, intent: object
) -> dict[str, object]:
    retained_intent = validate_recovery_intent_v1(intent)
    item = _mapping(value, label="composite recovery receipt")
    expected = {
        "schema_version",
        "recovery_id",
        "recovery_intent_identity",
        "recovery_intent_sha256",
        "composite_collection_identity",
        "composite_collection_sha256",
        "crossed_prepare_request_identity",
        "crossed_prepare_request_sha256",
        "population_task_manifest_identity",
        "population_task_result_identities_sha256",
        "task_result_count",
        "task0_execution_name",
        "task0_execution_uid",
        "tasks_1_53_execution_name",
        "tasks_1_53_execution_uid",
        "ordinary_six_field_crossed_request",
        "new_execution_launched",
        "task_recomputed",
        "bucket_listing_performed",
        "logs_read",
        "outcomes_read",
        "recovery_receipt_sha256",
    }
    if set(item) != expected or item.get("schema_version") != RECOVERY_RECEIPT_SCHEMA:
        _fail("composite recovery receipt fields/schema differ")
    _require_hash(item, field="recovery_receipt_sha256", label="recovery receipt")
    intent_identity = _identity(
        item["recovery_intent_identity"], label="receipt recovery intent"
    )
    collection_identity = _identity(
        item["composite_collection_identity"], label="receipt collection"
    )
    crossed_identity = _identity(
        item["crossed_prepare_request_identity"], label="receipt crossed request"
    )
    try:
        authority.bind_body_to_identity_v1(
            retained_intent,
            intent_identity,
            label="receipt recovery intent",
        )
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise CorpusR6PopulationChallengerCompositeRecoveryV1Error(
            str(exc)
        ) from exc
    if (
        item.get("recovery_id") != RECOVERY_ID
        or intent_identity["uri"] != retained_intent["outputs"]["intent_uri"]
        or collection_identity["uri"]
        != retained_intent["outputs"]["collection_uri"]
        or crossed_identity["uri"]
        != retained_intent["outputs"]["crossed_prepare_request_uri"]
        or item.get("recovery_intent_sha256")
        != retained_intent["recovery_intent_sha256"]
        or item.get("population_task_manifest_identity")
        != retained_intent["population_task_manifest_identity"]
        or item.get("task_result_count") != authority.TASK_COUNT
        or item.get("task0_execution_name")
        != retained_intent["smoke_launch_result"]["execution_name"]
        or item.get("task0_execution_uid")
        != retained_intent["smoke_terminal_status"]["execution_uid"]
        or item.get("tasks_1_53_execution_name")
        != retained_intent["full54_launch_result"]["execution_name"]
        or item.get("tasks_1_53_execution_uid")
        != retained_intent["full54_terminal_status"]["execution_uid"]
        or item.get("ordinary_six_field_crossed_request") is not True
        or item.get("new_execution_launched") is not False
        or item.get("task_recomputed") is not False
        or item.get("bucket_listing_performed") is not False
        or item.get("logs_read") is not False
        or item.get("outcomes_read") is not False
    ):
        _fail("composite recovery receipt contract differs")
    for field in (
        "recovery_intent_sha256",
        "composite_collection_sha256",
        "crossed_prepare_request_sha256",
        "population_task_result_identities_sha256",
    ):
        _sha(item[field], label=field)
    return item


__all__ = [
    "AMENDMENT_REPORT_PATH",
    "COLLECT_RESULT_SCHEMA",
    "COMPOSITE_COLLECTION_SCHEMA",
    "CorpusR6PopulationChallengerCompositeRecoveryV1Error",
    "INTENT_SCHEMA",
    "MAXIMUM_COLLECTION_BYTES",
    "MAXIMUM_CROSSED_REQUEST_BYTES",
    "MAXIMUM_INTENT_BYTES",
    "MAXIMUM_RECOVERY_RECEIPT_BYTES",
    "PREPARE_RESULT_SCHEMA",
    "RECOVERY_ID",
    "RECOVERY_RECEIPT_SCHEMA",
    "TASK_ENVELOPE_SCHEMA",
    "build_administrative_task_envelope_v1",
    "build_recovery_intent_v1",
    "build_recovery_receipt_v1",
    "canonical_bytes_v1",
    "canonical_sha256_v1",
    "collect_composite_results_v1",
    "strict_json_bytes_v1",
    "validate_administrative_task_envelope_v1",
    "validate_composite_collection_v1",
    "validate_recovery_intent_v1",
    "validate_recovery_receipt_v1",
]
