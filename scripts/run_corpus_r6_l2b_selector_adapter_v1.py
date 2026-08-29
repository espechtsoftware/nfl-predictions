#!/usr/bin/env python3
"""Prepare, execute, seal, or grade the fixed R6 L2b selector adapter."""

from __future__ import annotations

from collections.abc import Mapping
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from nfl_dfs.research import corpus_r6_l2b_selector_adapter_v1 as adapter
from nfl_dfs.research import corpus_r6_l2b_panel_operator_v1 as panel_operator


ENABLE_ENV = "CORPUS_R6_L2B_SELECTOR_ENABLE"
MANIFEST_IDENTITY_ENV = "CORPUS_R6_L2B_SELECTOR_MANIFEST_IDENTITY"
EXECUTION_SCOPE_ENV = "CORPUS_R6_L2B_SELECTOR_EXECUTION_SCOPE"
REUSED_JOB_UID_ENV = "CORPUS_R6_L2B_SELECTOR_REUSED_JOB_UID"
SOURCE_COMMIT_ENV = "CODE_SHA"
IMAGE_DIGEST_ENV = "R6_RUNTIME_IMAGE_DIGEST"
ENTRYPOINT_COMMAND = (
    "/usr/local/bin/python3.11", "-I",
    "/app/scripts/run_corpus_r6_l2b_selector_adapter_v1.py", "dispatch-task",
)


class RunCorpusR6L2BSelectorAdapterV1Error(RuntimeError):
    """The guarded L2b selector command failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6L2BSelectorAdapterV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6L2BSelectorAdapterV1Error(
            f"{label} is not UTF-8 JSON"
        ) from exc
    item = _mapping(value, label=label)
    if adapter.canonical_json_bytes_v1(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return adapter._identity(value, label=label)
    except adapter.CorpusR6L2BSelectorAdapterV1Error as exc:
        raise RunCorpusR6L2BSelectorAdapterV1Error(str(exc)) from exc


class GCSExactTransportV1:
    """Generation-exact reads and create-once equal-byte recovery."""

    def __init__(self) -> None:
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - cloud dependency
            raise RunCorpusR6L2BSelectorAdapterV1Error(
                "google-cloud-storage is required"
            ) from exc
        self._client = storage.Client(
            project=adapter.FIXED_GCP_PROJECT,
            client_options=ClientOptions(
                api_endpoint=adapter.FIXED_STORAGE_ENDPOINT
            ),
        )
        self._cache: dict[tuple[str, str, str, int], bytes] = {}

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if type(uri) is not str or not uri.startswith("gs://"):
            _fail("GCS URI must use gs://")
        bucket, separator, name = uri[5:].partition("/")
        if not separator or not bucket or not name or "//" in name:
            _fail("GCS URI is malformed")
        return bucket, name

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _identity(identity_value, label="GCS exact read")
        key = (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )
        if key in self._cache:
            return self._cache[key]
        bucket_name, object_name = self._parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        raw = blob.download_as_bytes(if_generation_match=generation, retry=None)
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("generation-exact GCS bytes differ")
        self._cache[key] = raw
        return raw

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("create-once publication bytes differ")
        bucket_name, object_name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
                retry=None,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise
            current = self._client.bucket(bucket_name).blob(object_name)
            current.reload(retry=None)
            if current.generation is None:
                _fail("create-once collision lacks an existing generation")
            identity = {
                "uri": uri,
                "generation": str(current.generation),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
            if self.read_exact(identity) != raw:
                _fail("create-once collision bytes differ")
            return identity
        if blob.generation is None:
            _fail("create-once publication lacks a generation")
        identity = {
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if self.read_exact(identity) != raw:
            _fail("create-once publication exact reopen differs")
        return identity

    def open_known(
        self, uri: str, maximum_bytes: int,
    ) -> tuple[bytes, dict[str, object]]:
        bucket_name, object_name = self._parts(uri)
        metadata = self._client.bucket(bucket_name).blob(object_name)
        metadata.reload(retry=None)
        if metadata.generation is None or metadata.size is None:
            _fail("known selector result lacks generation or size")
        size = int(metadata.size)
        if size < 1 or size > maximum_bytes:
            _fail("known selector result exceeds its byte ceiling")
        generation = int(metadata.generation)
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        raw = blob.download_as_bytes(if_generation_match=generation, retry=None)
        identity = _identity({
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }, label="known selector result")
        if len(raw) != size:
            _fail("known selector result size differs")
        self._cache[(
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )] = raw
        return raw, identity


class SubprocessRunnerV1:
    """Bounded argv-only provider runner; no shell or log command exists."""

    def __call__(self, argv: list[str]) -> dict[str, object]:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=300,
        )
        return {
            "returncode": int(completed.returncode),
            "stdout": bytes(completed.stdout),
            "stderr": bytes(completed.stderr),
        }


def _run_checked(
    runner: object, argv: list[str], *, label: str, maximum_stdout: int,
) -> bytes:
    result = _mapping(runner(argv), label=f"{label} subprocess result")
    if (
        set(result) != {"returncode", "stdout", "stderr"}
        or type(result["returncode"]) is not int
        or type(result["stdout"]) is not bytes
        or type(result["stderr"]) is not bytes
        or result["returncode"] != 0
        or len(result["stdout"]) > maximum_stdout
        or len(result["stderr"]) > panel_operator.MAXIMUM_PROVIDER_STDERR_BYTES
    ):
        _fail(f"{label} subprocess failed or exceeded its framing")
    return result["stdout"]


def _run_json(runner: object, argv: list[str], *, label: str) -> dict[str, object]:
    raw = _run_checked(
        runner, argv, label=label,
        maximum_stdout=panel_operator.MAXIMUM_PROVIDER_JSON_BYTES,
    )
    try:
        return _mapping(json.loads(raw.decode("utf-8")), label=f"{label} JSON")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6L2BSelectorAdapterV1Error(
            f"{label} is not provider JSON"
        ) from exc


def prepare_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    item = _mapping(request, label="prepare request")
    if set(item) != {
        "l2b_panel_root_identity", "control_projection_receipt_identity",
        "terminal_build_receipt_identity", "source_commit_sha",
        "immutable_image_digest", "reused_job_name", "reused_job_uid",
        "execution_scope", "task0_smoke_receipt_identity", "output_prefix",
    }:
        _fail("prepare request fields differ")
    return adapter.prepare_selector_manifest_v1(
        l2b_panel_root_identity=item["l2b_panel_root_identity"],
        control_projection_receipt_identity=item[
            "control_projection_receipt_identity"
        ],
        terminal_build_receipt_identity=item["terminal_build_receipt_identity"],
        source_commit_sha=str(item["source_commit_sha"]),
        immutable_image_digest=str(item["immutable_image_digest"]),
        reused_job_name=str(item["reused_job_name"]),
        reused_job_uid=str(item["reused_job_uid"]),
        execution_scope=str(item["execution_scope"]),
        task0_smoke_receipt_identity=item["task0_smoke_receipt_identity"],
        output_prefix=str(item["output_prefix"]),
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )


def build_job_configuration_v1(
    *, manifest: object, manifest_identity: object,
) -> dict[str, object]:
    retained = adapter.validate_selector_manifest_v1(manifest)
    identity = adapter._identity(manifest_identity, label="selector manifest")
    scope = str(retained["execution_scope"])
    task_count = int(retained["execution_task_count"])
    environment = {
        ENABLE_ENV: "1",
        MANIFEST_IDENTITY_ENV: adapter.canonical_json_bytes_v1(identity).decode(
            "utf-8"
        ),
        EXECUTION_SCOPE_ENV: scope,
        REUSED_JOB_UID_ENV: retained["reused_job_uid"],
        SOURCE_COMMIT_ENV: retained["source_commit_sha"],
        IMAGE_DIGEST_ENV: retained["immutable_image_digest"],
    }
    delimiter = panel_operator.ENV_DELIMITER
    encoded_environment = f"^{delimiter}^" + delimiter.join(
        f"{key}={environment[key]}" for key in sorted(environment)
    )
    args = list(ENTRYPOINT_COMMAND[1:])
    flags = {
        "--args": f"^{delimiter}^" + delimiter.join(args),
        "--clear-cloudsql-instances": True,
        "--clear-network": True,
        "--clear-secrets": True,
        "--clear-volume-mounts": True,
        "--clear-volumes": True,
        "--clear-vpc-connector": True,
        "--command": ENTRYPOINT_COMMAND[0],
        "--cpu": "8",
        "--image": retained["immutable_image_uri"],
        "--max-retries": 0,
        "--memory": "32Gi",
        "--parallelism": task_count,
        "--set-env-vars": encoded_environment,
        "--task-timeout": "86400s",
        "--tasks": task_count,
        "--workdir": "",
    }
    body = {
        "schema_version": panel_operator.JOB_CONFIGURATION_SCHEMA,
        "scope": scope,
        "project_id": panel_operator.PROJECT,
        "location": panel_operator.REGION,
        "reused_job_name": adapter.REUSED_JOB_NAME,
        "expected_job_uid": adapter.REUSED_JOB_UID,
        "manifest_identity": identity,
        "manifest_sha256": retained["task_manifest_sha256"],
        "image_uri": retained["immutable_image_uri"],
        "image_digest": retained["immutable_image_digest"],
        "command": [ENTRYPOINT_COMMAND[0]],
        "args": args,
        "environment": environment,
        "task_count": task_count,
        "parallelism": task_count,
        "max_retries": 0,
        "timeout_seconds": 86_400,
        "resources": {"cpu": "8", "memory": "32Gi"},
        "gcloud_update_flags": flags,
        "new_job_creation_allowed": False,
        "outcomes_read": False,
    }
    return adapter._with_hash(body, field="job_configuration_sha256")


def _latest_status_v1(job: Mapping[str, object], *, runner: object) -> object:
    identity = panel_operator.validate_job_identity_v1(job)
    latest = identity["latest_execution_name"]
    if latest is None:
        return None
    raw = _run_json(
        runner,
        panel_operator.execution_describe_argv_v1(str(latest)),
        label="latest selector execution describe",
    )
    count = _mapping(raw.get("spec"), label="latest execution spec").get(
        "taskCount"
    )
    scope = (
        adapter.TASK0_SCOPE if count == 1
        else adapter.FULL54_SCOPE if count == adapter.TASK_COUNT
        else ""
    )
    if not scope:
        _fail("latest selector execution scope differs")
    status = panel_operator.build_execution_status_v1(
        raw, execution_name=str(latest), scope=scope
    )
    if status["terminal_state"] == "ACTIVE":
        _fail("reused selector job has an active execution")
    return status


def configure_operator_v1(
    *, manifest_identity: object, store: object, runner: object,
) -> dict[str, object]:
    manifest, identity = adapter._open_selector_manifest_v1(
        manifest_identity=manifest_identity, read_exact=store.read_exact
    )
    configuration = build_job_configuration_v1(
        manifest=manifest, manifest_identity=identity
    )
    before_raw = _run_json(
        runner, panel_operator.job_describe_argv_v1(),
        label="preconfigure selector job describe",
    )
    before = panel_operator.validate_job_identity_v1(before_raw)
    latest = _latest_status_v1(before_raw, runner=runner)
    with tempfile.TemporaryDirectory(
        prefix="r6-l2b-selector-flags-", dir="/tmp"
    ) as directory:
        flags_path = Path(directory) / "configure-flags.json"
        flags_path.write_bytes(
            adapter.canonical_json_bytes_v1(configuration["gcloud_update_flags"])
        )
        os.chmod(flags_path, 0o600)
        updated = _run_json(
            runner,
            panel_operator.configure_argv_v1(flags_path=str(flags_path)),
            label="selector job update",
        )
    after = panel_operator.validate_exact_job_configuration_v1(
        updated, configuration=configuration
    )
    if before["job_uid"] != after["job_uid"]:
        _fail("reused selector job UID changed during configuration")
    return adapter._with_hash({
        "schema_version": "corpus-r6-l2b-selector-configure/v1",
        "execution_scope": manifest["execution_scope"],
        "task_manifest_identity": identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "job_configuration_sha256": configuration["job_configuration_sha256"],
        "job_identity_before": before,
        "latest_execution_before": latest,
        "job_identity_after": after,
        "job_created": False,
        "outcomes_read": False,
    }, field="configure_result_sha256")


def launch_operator_v1(
    *, manifest_identity: object, store: object, runner: object,
) -> dict[str, object]:
    manifest, identity = adapter._open_selector_manifest_v1(
        manifest_identity=manifest_identity, read_exact=store.read_exact
    )
    configuration = build_job_configuration_v1(
        manifest=manifest, manifest_identity=identity
    )
    job = _run_json(
        runner, panel_operator.job_describe_argv_v1(),
        label="prelaunch selector job describe",
    )
    panel_operator.validate_exact_job_configuration_v1(
        job, configuration=configuration
    )
    _latest_status_v1(job, runner=runner)
    raw = _run_checked(
        runner, panel_operator.execute_argv_v1(),
        label="selector asynchronous launch", maximum_stdout=4_096,
    )
    try:
        execution_name = raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise RunCorpusR6L2BSelectorAdapterV1Error(
            "selector launch name is not UTF-8"
        ) from exc
    return panel_operator.build_launch_result_v1(
        execution_name=execution_name, scope=str(manifest["execution_scope"])
    )


def status_operator_v1(*, launch: object, runner: object) -> dict[str, object]:
    retained = panel_operator.validate_launch_result_v1(launch)
    raw = _run_json(
        runner,
        panel_operator.execution_describe_argv_v1(
            str(retained["execution_name"])
        ),
        label="selector execution describe",
    )
    return panel_operator.build_execution_status_v1(
        raw,
        execution_name=str(retained["execution_name"]),
        scope=str(retained["scope"]),
    )


def collect_operator_v1(
    *, manifest_identity: object, launch: object, store: object, runner: object,
) -> dict[str, object]:
    retained_launch = panel_operator.validate_launch_result_v1(launch)
    status = status_operator_v1(launch=retained_launch, runner=runner)
    manifest, identity = adapter._open_selector_manifest_v1(
        manifest_identity=manifest_identity, read_exact=store.read_exact
    )
    if retained_launch["scope"] != manifest["execution_scope"]:
        _fail("selector launch/manifest scope differs")
    if (
        status.get("scope") != manifest["execution_scope"]
        or status.get("execution_name") != retained_launch["execution_name"]
        or status.get("job_uid") != adapter.REUSED_JOB_UID
        or status.get("expected_task_count") != manifest["execution_task_count"]
        or status.get("succeeded_count") != manifest["execution_task_count"]
        or status.get("failed_count") != 0
        or status.get("cancelled_count") != 0
        or status.get("terminal_state") != "SUCCEEDED"
        or status.get("logs_read") is not False
        or status.get("scientific_outputs_read") is not False
        or status.get("outcomes_read") is not False
    ):
        _fail("selector outputs cannot resolve before terminal success")
    identities: list[dict[str, object]] = []
    for task_row in manifest["task_rows"][:manifest["execution_task_count"]]:
        _raw, result_identity = store.open_known(
            str(task_row["result_uri"]), adapter.MAXIMUM_TASK_RESULT_BYTES
        )
        identities.append(result_identity)
    return collect_from_request_v1({
        "manifest_identity": identity,
        "launch_result": retained_launch,
        "execution_status": status,
        "task_result_identities": identities,
    }, store=store)


def execute_task_from_request_v1(
    request: object, *, store: object,
) -> dict[str, object]:
    item = _mapping(request, label="execute-task request")
    if set(item) != {"manifest_identity", "task_index"}:
        _fail("execute-task request fields differ")
    execution = adapter.execute_selector_task_v1(
        manifest_identity=item["manifest_identity"],
        task_index=int(item["task_index"]),
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    return {
        "schema_version": "corpus-r6-l2b-selector-task-cli-result/v1",
        "source_ordinal": execution.result["source_ordinal"],
        "slate_id": execution.result["slate_id"],
        "task_result_identity": execution.result_identity,
        "task_result_sha256": execution.result["slate_result_sha256"],
        "complete": True,
        "uses_realized_outcomes": False,
    }


def dispatch_task_from_environment_v1(*, store: object) -> dict[str, object]:
    if os.environ.get(ENABLE_ENV) != "1":
        _fail("L2b selector dispatcher is default-off")
    raw_identity = os.environ.get(MANIFEST_IDENTITY_ENV, "").encode("utf-8")
    manifest_identity = _strict_json(raw_identity, label="manifest identity env")
    manifest, retained_identity = adapter._open_selector_manifest_v1(
        manifest_identity=manifest_identity, read_exact=store.read_exact
    )
    try:
        task_index = int(os.environ.get("CLOUD_RUN_TASK_INDEX", ""))
        task_count = int(os.environ.get("CLOUD_RUN_TASK_COUNT", ""))
        task_attempt = int(os.environ.get("CLOUD_RUN_TASK_ATTEMPT", ""))
    except ValueError as exc:
        raise RunCorpusR6L2BSelectorAdapterV1Error(
            "Cloud Run task environment differs"
        ) from exc
    scope = os.environ.get(EXECUTION_SCOPE_ENV)
    expected_count = (
        1 if scope == adapter.TASK0_SCOPE
        else adapter.TASK_COUNT if scope == adapter.FULL54_SCOPE
        else None
    )
    if (
        retained_identity != manifest_identity
        or scope != manifest["execution_scope"]
        or expected_count != manifest["execution_task_count"]
        or task_count != expected_count
        or task_attempt != 0
        or (scope == adapter.TASK0_SCOPE and task_index != 0)
        or os.environ.get(SOURCE_COMMIT_ENV) != manifest["source_commit_sha"]
        or os.environ.get(IMAGE_DIGEST_ENV) != manifest["immutable_image_digest"]
        or os.environ.get(REUSED_JOB_UID_ENV) != manifest["reused_job_uid"]
    ):
        _fail("L2b selector code/image/job/scope task authority differs")
    return execute_task_from_request_v1(
        {"manifest_identity": manifest_identity, "task_index": task_index},
        store=store,
    )


def finalize_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    item = _mapping(request, label="finalize request")
    if set(item) != {"manifest_identity", "task_result_identities"}:
        _fail("finalize request fields differ")
    identities = item["task_result_identities"]
    if not isinstance(identities, list) or len(identities) != adapter.TASK_COUNT:
        _fail("finalize request requires 54 task-result identities")
    root, identity = adapter.finalize_terminal_root_v1(
        manifest_identity=item["manifest_identity"],
        task_result_identities=identities,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    return {
        "schema_version": "corpus-r6-l2b-selector-finalization/v1",
        "terminal_root_identity": identity,
        "terminal_root_sha256": root["terminal_root_sha256"],
        "source_slate_count": root["source_slate_count"],
        "complete": True,
        "uses_realized_outcomes": False,
    }


def collect_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    """Collect only after an exact terminal task0/full54 execution status."""
    item = _mapping(request, label="collect request")
    if set(item) != {
        "manifest_identity", "launch_result", "execution_status",
        "task_result_identities",
    }:
        _fail("collect request fields differ")
    manifest, manifest_identity = adapter._open_selector_manifest_v1(
        manifest_identity=item["manifest_identity"], read_exact=store.read_exact
    )
    status = _mapping(item["execution_status"], label="execution status")
    try:
        launch = panel_operator.validate_launch_result_v1(item["launch_result"])
        panel_operator._self_hash(
            status, field="status_sha256", label="selector execution status"
        )
    except Exception as exc:
        raise RunCorpusR6L2BSelectorAdapterV1Error(
            "selector execution status validation failed"
        ) from exc
    expected_count = int(manifest["execution_task_count"])
    if (
        status.get("schema_version") != panel_operator.STATUS_SCHEMA
        or status.get("scope") != manifest["execution_scope"]
        or launch.get("scope") != manifest["execution_scope"]
        or launch.get("expected_task_count") != expected_count
        or status.get("execution_name") != launch.get("execution_name")
        or status.get("job_name") != adapter.REUSED_JOB_NAME
        or status.get("job_uid") != adapter.REUSED_JOB_UID
        or status.get("expected_task_count") != expected_count
        or status.get("succeeded_count") != expected_count
        or status.get("failed_count") != 0
        or status.get("cancelled_count") != 0
        or status.get("terminal_state") != "SUCCEEDED"
        or status.get("logs_read") is not False
        or status.get("scientific_outputs_read") is not False
        or status.get("outcomes_read") is not False
    ):
        _fail("selector results cannot open before exact execution success")
    identities = item["task_result_identities"]
    if not isinstance(identities, list) or len(identities) != expected_count:
        _fail("collect task-result identity count differs from execution scope")
    if manifest["execution_scope"] == adapter.FULL54_SCOPE:
        return finalize_from_request_v1({
            "manifest_identity": manifest_identity,
            "task_result_identities": identities,
        }, store=store)
    adapter._validate_task0_execution_status_v1(status)
    result, retained_identity = adapter._open_and_replay_task0_result_v1(
        task0_manifest=manifest,
        task0_manifest_identity=manifest_identity,
        task_result_identity=identities[0],
        read_exact=store.read_exact,
    )
    receipt = adapter._with_hash({
        "schema_version": adapter.TASK0_SMOKE_SCHEMA,
        "adapter_id": adapter.ADAPTER_ID,
        "execution_scope": adapter.TASK0_SCOPE,
        "task0_manifest_identity": manifest_identity,
        "task0_manifest_sha256": manifest["task_manifest_sha256"],
        "l2b_panel_root_identity": manifest["l2b_panel_root_identity"],
        "control_projection_receipt_identity": manifest[
            "control_projection_receipt_identity"
        ],
        "terminal_build_receipt_identity": manifest[
            "terminal_build_receipt_identity"
        ],
        "reused_job_uid": adapter.REUSED_JOB_UID,
        "task0_launch_result": launch,
        "task0_execution_status": status,
        "task_result_identity": retained_identity,
        "task_result_sha256": result["slate_result_sha256"],
        "source_commit_sha": manifest["source_commit_sha"],
        "immutable_image_digest": manifest["immutable_image_digest"],
        "uses_realized_outcomes": False,
        "complete": True,
    }, field="smoke_receipt_sha256")
    adapter._validate_task0_smoke_receipt_shape_v1(receipt)
    receipt_identity = adapter._publish_json(
        uri=f"{manifest['output_prefix']}task0-selector-smoke-receipt.json",
        value=receipt,
        maximum_bytes=1_000_000,
        publish_create_once=store.publish_create_once,
        read_exact=store.read_exact,
        label="L2b selector task0 smoke receipt",
    )
    return {
        "schema_version": "corpus-r6-l2b-selector-task0-collection/v1",
        "smoke_receipt_identity": receipt_identity,
        "smoke_receipt_sha256": receipt["smoke_receipt_sha256"],
        "complete": True,
        "uses_realized_outcomes": False,
    }


def grade_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    item = _mapping(request, label="grade request")
    if set(item) != {
        "terminal_root_identity", "outcome_snapshot_identity", "output_uri",
    }:
        _fail("grade request fields differ")
    grade, identity = (
        adapter.grade_and_publish_l2b_selector_experiment_realized_v1(
            terminal_root_identity=item["terminal_root_identity"],
            outcome_snapshot_identity=item["outcome_snapshot_identity"],
            target_uri=str(item["output_uri"]),
            read_terminal_exact=store.read_exact,
            read_outcome_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
    )
    return {
        "schema_version": "corpus-r6-l2b-selector-realized-grade-cli-result/v1",
        "adapter_id": grade["adapter_id"],
        "realized_scorecard_identity": identity,
        "realized_grade_sha256": grade["realized_grade_sha256"],
        "aggregate_cell_count": grade["aggregate_cell_count"],
        "terminal_before_first_outcome_read": grade[
            "terminal_before_first_outcome_read"
        ],
        "complete": True,
    }


def _request_file(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute() or not path.is_file():
        _fail(f"{label} must be an existing absolute file")
    return _strict_json(path.read_bytes(), label=label)


def _write_create_once(path: Path, value: Mapping[str, object]) -> None:
    raw = adapter.canonical_json_bytes_v1(value)
    if not path.is_absolute() or not path.parent.is_dir():
        _fail("local result must be a new file in an existing directory")
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError as exc:
        raise RunCorpusR6L2BSelectorAdapterV1Error(
            "local result already exists; create-once write refused"
        ) from exc
    sys.stdout.buffer.write(raw + b"\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in (
        "prepare", "execute-task", "finalize", "grade", "configure",
        "launch", "status", "collect",
    ):
        child = commands.add_parser(command)
        child.add_argument("--request-file", type=Path, required=True)
        child.add_argument("--output-file", type=Path, required=True)
    dispatch = commands.add_parser("dispatch-task")
    dispatch.add_argument("--output-file", type=Path, required=False)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    store = GCSExactTransportV1()
    if args.command == "dispatch-task":
        result = dispatch_task_from_environment_v1(store=store)
    else:
        request = _request_file(
            args.request_file, label=f"{args.command} request"
        )
        if args.command == "prepare":
            result = prepare_from_request_v1(request, store=store)
        elif args.command == "execute-task":
            result = execute_task_from_request_v1(request, store=store)
        elif args.command == "finalize":
            result = finalize_from_request_v1(request, store=store)
        elif args.command == "grade":
            result = grade_from_request_v1(request, store=store)
        elif args.command in {"configure", "launch"}:
            if set(request) != {"manifest_identity"}:
                _fail(f"{args.command} request fields differ")
            runner = SubprocessRunnerV1()
            function = (
                configure_operator_v1
                if args.command == "configure"
                else launch_operator_v1
            )
            result = function(
                manifest_identity=request["manifest_identity"],
                store=store,
                runner=runner,
            )
        elif args.command == "status":
            if set(request) != {"launch_result"}:
                _fail("status request fields differ")
            result = status_operator_v1(
                launch=request["launch_result"], runner=SubprocessRunnerV1()
            )
        elif args.command == "collect":
            if set(request) != {"manifest_identity", "launch_result"}:
                _fail("operator collect request fields differ")
            result = collect_operator_v1(
                manifest_identity=request["manifest_identity"],
                launch=request["launch_result"],
                store=store,
                runner=SubprocessRunnerV1(),
            )
        else:  # pragma: no cover - argparse owns the registry
            _fail("unknown command")
    if args.output_file is None:
        sys.stdout.buffer.write(adapter.canonical_json_bytes_v1(result) + b"\n")
    else:
        _write_create_once(args.output_file, result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        RunCorpusR6L2BSelectorAdapterV1Error,
        adapter.CorpusR6L2BSelectorAdapterV1Error,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
