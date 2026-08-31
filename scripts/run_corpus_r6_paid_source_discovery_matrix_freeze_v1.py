#!/usr/bin/env python3
"""Guarded score-free cloud runner for Experiment-5 discovery matrices.

The runner exposes separate prepare, task-0, 54-way materialization, collect,
54-way matrix reopen, and reopen-collect phases.  Every mutation is create-once;
large matrix bodies stream file-to-file and are never materialized as Python
bytes.  No command lists objects, reads R4, reads outcomes, grades, promotes,
or changes a Cloud Run job.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Final, Protocol


ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from nfl_dfs.research import (  # noqa: E402
    corpus_r6_paid_source_discovery_matrix_freeze_v1 as freeze,
)


PROJECT: Final = freeze.PROJECT_ID
REGION: Final = freeze.REGION
JOB: Final = freeze.JOB_NAME
JOB_UID: Final = freeze.JOB_UID
SERVICE_ACCOUNT: Final = freeze.SERVICE_ACCOUNT
ENABLE_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_ENABLE"
ENABLE_VALUE: Final = "I_UNDERSTAND_SCORE_FREE_DISCOVERY_MATRIX_FREEZE_V1"
MODE_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_MODE"
OUTCOMES_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_OUTCOMES_ALLOWED"
CODE_SHA_ENV: Final = "CODE_SHA"
IMAGE_ENV: Final = "IMAGE_URI"
BUILD_ID_ENV: Final = "BUILD_ID"
TASK0_EXECUTION_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_TASK0_EXECUTION"
TASK0_GATE_SHA_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_TASK0_GATE_SHA256"
TASK0_GATE_B64_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_TASK0_GATE_B64"
PAYLOAD_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_PAYLOAD_B64"
PAYLOAD_SHA_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_PAYLOAD_SHA256"
MAX_JSON_BYTES: Final = 16 * 1024 * 1024

_EXECUTION = re.compile(r"[a-z][a-z0-9-]{2,100}\Z")


class DiscoveryMatrixRunnerV1Error(RuntimeError):
    """A guard, exact identity, provider fact, or publication differed."""


class Store(Protocol):
    def read_exact(self, identity: Mapping[str, object]) -> bytes: ...
    def open_known(self, uri: str, maximum_bytes: int) -> tuple[bytes, Mapping[str, object]]: ...
    def publish_bytes_create_once(self, uri: str, raw: bytes) -> Mapping[str, object]: ...
    def publish_file_create_once(self, uri: str, path: Path) -> Mapping[str, object]: ...
    def fetch_exact_to_file(self, identity: Mapping[str, object], path: Path) -> None: ...


class ReadOnlyStore(Protocol):
    def read_exact(self, identity: Mapping[str, object]) -> bytes: ...


class Provider(Protocol):
    def completed(self, execution_id: str) -> Mapping[str, object]: ...


def _fail(message: str) -> None:
    raise DiscoveryMatrixRunnerV1Error(message)


def _canonical(value: object) -> bytes:
    return freeze.canonical_json_bytes(value)


def _read_file(path: Path, *, label: str) -> dict[str, object]:
    try:
        raw = Path(path).read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DiscoveryMatrixRunnerV1Error(f"{label} bytes differ") from exc
    if not isinstance(value, Mapping) or raw not in {_canonical(value), _canonical(value) + b"\n"}:
        _fail(f"{label} canonical JSON differs")
    return dict(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return freeze._identity(value, label=label)
    except Exception as exc:
        raise DiscoveryMatrixRunnerV1Error(str(exc)) from exc


def _read_json_exact(
    identity_value: object, *, store: Store, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if identity["bytes"] > MAX_JSON_BYTES:
        _fail(f"{label} exceeds JSON byte ceiling")
    raw = store.read_exact(identity)
    if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
        _fail(f"{label} exact bytes differ")
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DiscoveryMatrixRunnerV1Error(f"{label} JSON differs") from exc
    if not isinstance(value, Mapping) or raw != _canonical(value):
        _fail(f"{label} canonical bytes differ")
    return dict(value), identity


def _publish_json(uri: str, value: Mapping[str, object], *, store: Store) -> dict[str, object]:
    raw = _canonical(value)
    if len(raw) > MAX_JSON_BYTES:
        _fail("JSON publication exceeds byte ceiling")
    identity = _identity(
        store.publish_bytes_create_once(uri, raw), label="JSON publication"
    )
    if (
        identity["uri"] != uri
        or identity["sha256"] != sha256(raw).hexdigest()
        or identity["bytes"] != len(raw)
        or store.read_exact(identity) != raw
    ):
        _fail("JSON create-once exact reopen differs")
    return identity


def _runtime(
    manifest: Mapping[str, object],
    ordinal: int,
    env: Mapping[str, str],
    *,
    mode: str,
) -> dict[str, object]:
    try:
        task_index = int(env.get("CLOUD_RUN_TASK_INDEX", ""))
    except ValueError as exc:
        raise DiscoveryMatrixRunnerV1Error("runtime task index differs") from exc
    expected_count = 1 if mode == "task0" else freeze.TASK_COUNT
    task0_execution = env.get(TASK0_EXECUTION_ENV, "")
    task0_gate_sha = env.get(TASK0_GATE_SHA_ENV, "")
    task0_gate_b64 = env.get(TASK0_GATE_B64_ENV, "")
    if mode not in {"task0", "task", "reopen-task"}:
        _fail("matrix runtime mode differs")
    if (
        env.get(ENABLE_ENV) != ENABLE_VALUE
        or env.get(OUTCOMES_ENV) != "false"
        or env.get(CODE_SHA_ENV) != manifest["code_sha"]
        or env.get(IMAGE_ENV) != manifest["immutable_image"]
        or env.get(BUILD_ID_ENV) != manifest["build_id"]
        or env.get("CLOUD_RUN_JOB") != JOB
        or task_index != ordinal
        or env.get("CLOUD_RUN_TASK_INDEX") != str(ordinal)
        or env.get("CLOUD_RUN_TASK_COUNT") != str(expected_count)
        or env.get("CLOUD_RUN_TASK_ATTEMPT") != "0"
        or _EXECUTION.fullmatch(env.get("CLOUD_RUN_EXECUTION", "")) is None
        or (
            mode == "task"
            and (
                _EXECUTION.fullmatch(task0_execution) is None
                or freeze._SHA.fullmatch(task0_gate_sha) is None
                or type(task0_gate_b64) is not str
                or not task0_gate_b64
                or task0_gate_b64 == "none"
            )
        )
        or (
            mode != "task"
            and (
                task0_execution != "none"
                or task0_gate_sha != "none"
                or task0_gate_b64 != "none"
            )
        )
    ):
        _fail("matrix runtime authority differs")
    return freeze._with_hash({
        "schema_version": freeze.RUNTIME_AUTHORITY_SCHEMA,
        "runtime_mode": mode,
        "project_id": PROJECT,
        "region": REGION,
        "job_name": JOB,
        "execution_id": env["CLOUD_RUN_EXECUTION"],
        "source_task_ordinal": ordinal,
        "task_count": expected_count,
        "scientific_task_count": freeze.TASK_COUNT,
        "task_attempt": 0,
        "manifest_sha256": manifest["manifest_sha256"],
        "code_sha": manifest["code_sha"],
        "immutable_image": manifest["immutable_image"],
        "build_id": manifest["build_id"],
        "task0_execution_id": task0_execution,
        "task0_gate_sha256": task0_gate_sha,
        "outcomes_allowed": False,
    }, field="runtime_authority_sha256")


def _open_manifest(identity: object, *, store: Store) -> tuple[dict, dict]:
    value, retained_identity = _read_json_exact(identity, store=store, label="matrix manifest")
    manifest = freeze.validate_manifest_v1(value)
    return manifest, retained_identity


def prepare(request: Mapping[str, object], *, store: Store) -> dict[str, object]:
    if set(request) != {
        "run_id", "code_sha", "immutable_image", "build_id",
        "runtime_build_attestation_identity", "candidate_root_identity",
        "later_source_freeze_identity",
    }:
        _fail("matrix prepare request fields differ")
    manifest = freeze.prepare_manifest_v1(
        run_id=request["run_id"], code_sha=request["code_sha"],
        immutable_image=request["immutable_image"], build_id=request["build_id"],
        runtime_build_attestation_identity=request["runtime_build_attestation_identity"],
        candidate_root_identity=request["candidate_root_identity"],
        later_source_freeze_identity=request["later_source_freeze_identity"],
        read_exact=store.read_exact,
    )
    identity = _publish_json(
        f"{manifest['output_prefix']}manifest.json", manifest, store=store
    )
    reopened, reopened_identity = _open_manifest(identity, store=store)
    if reopened != manifest or reopened_identity != identity:
        _fail("matrix manifest exact reopen differs")
    return {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-prepare-result/v1",
        "manifest_identity": identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "task_count": freeze.TASK_COUNT,
        "uses_realized_outcomes": False,
        "complete": True,
    }


def task(
    manifest_identity: object, *, store: Store | ReadOnlyStore,
    environment: Mapping[str, str],
    smoke: bool, workspace: Path,
) -> dict[str, object]:
    manifest, retained_identity = _open_manifest(manifest_identity, store=store)
    ordinal = 0 if smoke else int(environment.get("CLOUD_RUN_TASK_INDEX", "-1"))
    if smoke and any(
        hasattr(store, name)
        for name in ("publish_bytes_create_once", "publish_file_create_once")
    ):
        _fail("task0 storage adapter exposes a write API")
    if not smoke:
        _task0_gate_from_environment(
            environment,
            manifest=manifest,
            manifest_identity=retained_identity,
        )
    runtime = _runtime(
        manifest, ordinal, dict(environment), mode="task0" if smoke else "task"
    )
    matrix_path = workspace / f"matrix-{ordinal:02d}.bin"
    local = freeze.build_task_matrix_file_v1(
        manifest_value=manifest, source_task_ordinal=ordinal,
        read_exact=store.read_exact, destination=matrix_path,
    )
    if smoke:
        receipt = freeze.build_task0_receipt_v1(
            manifest_value=manifest,
            manifest_identity=retained_identity,
            local_materialization_value=local,
            runtime_authority=runtime,
        )
        matrix_path.unlink()
        return receipt
    if not all(
        hasattr(store, name)
        for name in (
            "publish_bytes_create_once",
            "publish_file_create_once",
            "fetch_exact_to_file",
        )
    ):
        _fail("matrix task storage adapter lacks its create-once file API")
    matrix_identity = _identity(
        store.publish_file_create_once(manifest["tasks"][ordinal]["matrix_uri"], matrix_path),
        label="matrix publication",
    )
    exact_path = workspace / f"matrix-{ordinal:02d}.exact.bin"
    store.fetch_exact_to_file(matrix_identity, exact_path)
    candidate_raw = store.read_exact(manifest["tasks"][ordinal]["candidate_artifact_identity"])
    candidate = freeze.source.validate_accepted_candidate_artifact_v1(
        freeze._parse_canonical(candidate_raw, label="task candidate artifact")
    )
    freeze.validate_matrix_file_v1(
        path=exact_path, identity_value=matrix_identity,
        candidate_ids=[str(row["candidate_id"]) for row in candidate["rows"]],
        task_binding_value=manifest["tasks"][ordinal],
    )
    exact_path.unlink()
    matrix_path.unlink()
    result = freeze.build_task_result_v1(
        manifest_value=manifest, local_materialization_value=local,
        matrix_identity=matrix_identity, runtime_authority=runtime,
    )
    result_identity = _publish_json(
        manifest["tasks"][ordinal]["task_result_uri"], result, store=store
    )
    return {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-task-publication/v1",
        "task_result_identity": result_identity,
        "matrix_identity": matrix_identity,
        "source_task_ordinal": ordinal,
        "matrix_exact_reopened_after_publication": True,
        "uses_realized_outcomes": False,
        "complete": True,
    }


def _payload_identity_from_environment(
    environment: Mapping[str, object], *, expected_identity: object,
) -> tuple[dict[str, object], str]:
    encoded = environment.get(PAYLOAD_ENV)
    expected_sha = environment.get(PAYLOAD_SHA_ENV)
    if type(encoded) is not str or type(expected_sha) is not str:
        _fail("matrix provider payload environment differs")
    try:
        raw = base64.b64decode(encoded, validate=True)
        value = json.loads(raw)
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise DiscoveryMatrixRunnerV1Error(
            "matrix provider payload environment differs"
        ) from exc
    if (
        sha256(raw).hexdigest() != expected_sha
        or not isinstance(value, Mapping)
        or raw not in {_canonical(value), _canonical(value) + b"\n"}
    ):
        _fail("matrix provider payload environment differs")
    identity = _identity(value, label="matrix provider payload identity")
    if identity != _identity(expected_identity, label="expected matrix payload"):
        _fail("matrix provider payload identity differs")
    return identity, expected_sha


def _task0_gate_from_environment(
    environment: Mapping[str, object],
    *,
    manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    encoded = environment.get(TASK0_GATE_B64_ENV)
    expected_sha = environment.get(TASK0_GATE_SHA_ENV)
    execution_id = environment.get(TASK0_EXECUTION_ENV)
    if (
        type(encoded) is not str
        or not encoded
        or encoded == "none"
        or type(expected_sha) is not str
        or freeze._SHA.fullmatch(expected_sha) is None
        or type(execution_id) is not str
        or _EXECUTION.fullmatch(execution_id) is None
    ):
        _fail("matrix task0 gate environment differs")
    try:
        raw = base64.b64decode(encoded, validate=True)
        value = json.loads(raw)
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise DiscoveryMatrixRunnerV1Error(
            "matrix task0 gate environment differs"
        ) from exc
    if (
        len(raw) > MAX_JSON_BYTES
        or not isinstance(value, Mapping)
        or raw not in {_canonical(value), _canonical(value) + b"\n"}
    ):
        _fail("matrix task0 gate environment differs")
    gate = freeze.validate_task0_gate_v1(
        value,
        manifest_value=manifest,
        manifest_identity=manifest_identity,
        expected_execution_id=execution_id,
    )
    if gate["task0_gate_sha256"] != expected_sha:
        _fail("matrix task0 gate environment differs")
    return gate


def _execution(
    value: Mapping[str, object],
    *,
    execution_id: str,
    task_count: int,
    mode: str,
    payload_identity: object,
    manifest: Mapping[str, object],
) -> dict[str, object]:
    item = dict(value)
    if (
        mode not in {"task0", "task", "reopen-task"}
        or task_count != (1 if mode == "task0" else freeze.TASK_COUNT)
    ):
        _fail("matrix provider execution mode/task census differs")
    environment = item.get("environment")
    if not isinstance(environment, Mapping):
        _fail("matrix provider execution environment differs")
    retained_environment = dict(environment)
    exact_environment = {
        CODE_SHA_ENV: manifest["code_sha"],
        IMAGE_ENV: manifest["immutable_image"],
        "IMAGE_DIGEST": manifest["image_digest"],
        BUILD_ID_ENV: manifest["build_id"],
        ENABLE_ENV: ENABLE_VALUE,
        MODE_ENV: mode,
        OUTCOMES_ENV: "false",
    }
    if any(retained_environment.get(key) != expected for key, expected in exact_environment.items()):
        _fail("matrix provider execution environment differs")
    if "IMAGE_SOURCE_COMMIT_SHA" in retained_environment:
        _fail("caller environment must not substitute for baked source proof")
    expected_environment_keys = set(exact_environment) | {
        PAYLOAD_ENV,
        PAYLOAD_SHA_ENV,
        TASK0_EXECUTION_ENV,
        TASK0_GATE_SHA_ENV,
        TASK0_GATE_B64_ENV,
    }
    if set(retained_environment) != expected_environment_keys:
        _fail("matrix provider execution environment census differs")
    task0_execution = retained_environment.get(TASK0_EXECUTION_ENV)
    task0_gate_sha = retained_environment.get(TASK0_GATE_SHA_ENV)
    if (
        mode == "task"
        and (
            type(task0_execution) is not str
            or _EXECUTION.fullmatch(task0_execution) is None
            or type(task0_gate_sha) is not str
            or freeze._SHA.fullmatch(task0_gate_sha) is None
        )
    ) or (
        mode != "task"
        and (task0_execution != "none" or task0_gate_sha != "none")
    ):
        _fail("matrix provider task0 predecessor binding differs")
    retained_payload_identity, payload_sha = _payload_identity_from_environment(
        retained_environment, expected_identity=payload_identity
    )
    task0_gate = None
    if mode == "task":
        task0_gate = _task0_gate_from_environment(
            retained_environment,
            manifest=manifest,
            manifest_identity=retained_payload_identity,
        )
    elif retained_environment.get(TASK0_GATE_B64_ENV) != "none":
        _fail("matrix provider task0 predecessor binding differs")
    if (
        item.get("execution_id") != execution_id
        or item.get("job_name") != JOB
        or item.get("job_uid") != JOB_UID
        or type(item.get("execution_uid")) is not str
        or not item["execution_uid"]
        or item.get("task_count") != task_count
        or item.get("parallelism") != (1 if mode == "task0" else freeze.TASK_COUNT)
        or item.get("succeeded_count") != task_count
        or item.get("failed_count") != 0
        or item.get("cancelled_count") != 0
        or item.get("running_count") != 0
        or item.get("terminal") is not True
        or item.get("max_retries") != 0
        or item.get("timeout_seconds") != freeze.TASK_TIMEOUT_SECONDS
        or item.get("service_account") != SERVICE_ACCOUNT
        or item.get("immutable_image") != manifest["immutable_image"]
        or item.get("command") != list(freeze.CONTAINER_COMMAND)
        or item.get("args") != [freeze.CONTAINER_SCRIPT, "container-run", mode]
        or item.get("resources")
        != {"cpu": freeze.CPU_LIMIT, "memory": freeze.MEMORY_LIMIT}
    ):
        _fail("matrix provider execution differs")
    body = {
        "schema_version": freeze.PROVIDER_EXECUTION_SCHEMA,
        "execution_id": execution_id,
        "execution_uid": item["execution_uid"],
        "job_name": JOB,
        "job_uid": JOB_UID,
        "mode": mode,
        "payload_identity": retained_payload_identity,
        "payload_sha256": payload_sha,
        "task_count": task_count,
        "parallelism": item["parallelism"],
        "succeeded_count": item["succeeded_count"],
        "failed_count": item["failed_count"],
        "cancelled_count": item["cancelled_count"],
        "running_count": item["running_count"],
        "max_retries": item["max_retries"],
        "timeout_seconds": item["timeout_seconds"],
        "service_account": item["service_account"],
        "immutable_image": item["immutable_image"],
        "command": item["command"],
        "args": item["args"],
        "resources": item["resources"],
        "environment_sha256": freeze.canonical_sha256(retained_environment),
        "code_sha": retained_environment[CODE_SHA_ENV],
        "build_id": retained_environment[BUILD_ID_ENV],
        "task0_execution_id": task0_execution,
        "task0_gate_sha256": task0_gate_sha,
        "task0_gate_receipt": task0_gate,
        "outcomes_allowed": False,
        "terminal": True,
        "complete": True,
    }
    return freeze._with_hash(body, field="provider_execution_sha256")


def validate_task0_gate(
    *,
    manifest_identity: object,
    task0_receipt_value: object,
    execution_id: str,
    store: ReadOnlyStore,
    provider: Provider,
) -> dict[str, object]:
    """Require one canonical task0 stdout receipt and its exact provider spec."""

    if type(execution_id) is not str or _EXECUTION.fullmatch(execution_id) is None:
        _fail("matrix task0 execution differs")
    manifest, retained_identity = _open_manifest(manifest_identity, store=store)
    receipt = freeze.validate_task0_receipt_v1(
        task0_receipt_value,
        manifest_value=manifest,
        manifest_identity=retained_identity,
        expected_execution_id=execution_id,
    )
    provider_receipt = _execution(
        provider.completed(execution_id),
        execution_id=execution_id,
        task_count=1,
        mode="task0",
        payload_identity=retained_identity,
        manifest=manifest,
    )
    if (
        receipt["runtime_authority"]["execution_id"]
        != provider_receipt["execution_id"]
        or receipt["runtime_authority"]["code_sha"]
        != provider_receipt["code_sha"]
        or receipt["runtime_authority"]["immutable_image"]
        != provider_receipt["immutable_image"]
        or receipt["runtime_authority"]["build_id"]
        != provider_receipt["build_id"]
    ):
        _fail("matrix task0 stdout/provider binding differs")
    body = {
        "schema_version": freeze.TASK0_GATE_SCHEMA,
        "manifest_identity": retained_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "execution_id": execution_id,
        "task0_receipt": receipt,
        "task0_receipt_sha256": receipt["task0_receipt_sha256"],
        "provider_execution_receipt": provider_receipt,
        "provider_execution_sha256": provider_receipt[
            "provider_execution_sha256"
        ],
        "exactly_one_canonical_stdout_receipt": True,
        "full_cohort_execution_launched": False,
        "complete": True,
    }
    gate = freeze._with_hash(body, field="task0_gate_sha256")
    return freeze.validate_task0_gate_v1(
        gate,
        manifest_value=manifest,
        manifest_identity=retained_identity,
        expected_execution_id=execution_id,
    )


def collect(request: Mapping[str, object], *, store: Store, provider: Provider) -> dict:
    if set(request) != {"manifest_identity", "execution_id"}:
        _fail("matrix collect request fields differ")
    execution_id = request["execution_id"]
    if type(execution_id) is not str or _EXECUTION.fullmatch(execution_id) is None:
        _fail("matrix collect execution differs")
    manifest, manifest_identity = _open_manifest(request["manifest_identity"], store=store)
    provider_receipt = _execution(
        provider.completed(execution_id),
        execution_id=execution_id,
        task_count=freeze.TASK_COUNT,
        mode="task",
        payload_identity=manifest_identity,
        manifest=manifest,
    )
    results, identities = [], []
    for ordinal, binding in enumerate(manifest["tasks"]):
        raw, raw_identity = store.open_known(binding["task_result_uri"], MAX_JSON_BYTES)
        identity = _identity(raw_identity, label=f"task result[{ordinal}]")
        if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
            _fail(f"task result[{ordinal}] bytes differ")
        result = json.loads(raw)
        retained = freeze.validate_task_result_v1(
            result, manifest_value=manifest, expected_ordinal=ordinal
        )
        if retained["runtime_authority"]["execution_id"] != execution_id:
            _fail(f"task result[{ordinal}] execution differs")
        results.append(retained)
        identities.append(identity)
    terminal = freeze.build_terminal_v1(
        manifest_value=manifest, manifest_identity=manifest_identity,
        task_results=results, task_result_identities=identities,
        provider_execution_receipt=provider_receipt,
    )
    terminal_identity = _publish_json(manifest["terminal_uri"], terminal, store=store)
    return {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-collect-result/v1",
        "terminal_identity": terminal_identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "task_count": freeze.TASK_COUNT,
        "root_published_last": True,
        "complete": True,
    }


def reopen_task(
    terminal_identity: object, *, store: Store, environment: Mapping[str, str],
    workspace: Path,
) -> dict:
    ordinal = int(environment.get("CLOUD_RUN_TASK_INDEX", "-1"))
    if (
        environment.get(ENABLE_ENV) != ENABLE_VALUE
        or environment.get(MODE_ENV) != "reopen-task"
        or environment.get(OUTCOMES_ENV) != "false"
        or environment.get("CLOUD_RUN_TASK_COUNT") != str(freeze.TASK_COUNT)
        or environment.get("CLOUD_RUN_TASK_ATTEMPT") != "0"
        or not 0 <= ordinal < freeze.TASK_COUNT
    ):
        _fail("matrix reopen runtime differs")
    root = freeze.reopen_terminal_registry_v1(
        terminal_identity=terminal_identity, read_exact=store.read_exact
    )
    runtime = _runtime(
        root.manifest, ordinal, dict(environment), mode="reopen-task"
    )
    receipt = freeze.reopen_matrix_task_v1(
        reopened_root=root, source_task_ordinal=ordinal,
        read_exact=store.read_exact, fetch_exact_to_file=store.fetch_exact_to_file,
        destination=workspace / f"reopen-{ordinal:02d}.bin",
        runtime_authority=runtime,
    )
    identity = _publish_json(
        root.manifest["tasks"][ordinal]["reopen_task_uri"], receipt, store=store
    )
    return {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-reopen-task-publication/v1",
        "source_task_ordinal": ordinal,
        "reopen_task_identity": identity,
        "complete": True,
    }


def reopen_collect(request: Mapping[str, object], *, store: Store, provider: Provider) -> dict:
    if set(request) != {"terminal_identity", "execution_id"}:
        _fail("matrix reopen collect request differs")
    execution_id = request["execution_id"]
    if type(execution_id) is not str or _EXECUTION.fullmatch(execution_id) is None:
        _fail("matrix reopen execution differs")
    root = freeze.reopen_terminal_registry_v1(
        terminal_identity=request["terminal_identity"], read_exact=store.read_exact
    )
    provider_receipt = _execution(
        provider.completed(execution_id),
        execution_id=execution_id,
        task_count=freeze.TASK_COUNT,
        mode="reopen-task",
        payload_identity=root.terminal_identity,
        manifest=root.manifest,
    )
    receipts, identities = [], []
    for ordinal, task_binding in enumerate(root.manifest["tasks"]):
        raw, raw_identity = store.open_known(task_binding["reopen_task_uri"], MAX_JSON_BYTES)
        identity = _identity(raw_identity, label=f"reopen receipt[{ordinal}]")
        if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
            _fail(f"reopen receipt[{ordinal}] bytes differ")
        receipts.append(json.loads(raw))
        identities.append(identity)
    terminal = freeze.collect_reopen_tasks_v1(
        reopened_root=root, task_receipts=receipts,
        task_receipt_identities=identities,
        provider_execution_receipt=provider_receipt,
    )
    identity = _publish_json(root.manifest["reopen_terminal_uri"], terminal, store=store)
    return {
        "schema_version": "corpus-r6-paid-source-discovery-matrix-reopen-collect-result/v1",
        "reopen_terminal_identity": identity,
        "reopen_sha256": terminal["reopen_sha256"],
        "task_count": freeze.TASK_COUNT,
        "complete": True,
    }


class ReadOnlyStoreAdapterV1:
    """Expose exactly one generation-exact read method to task0 code."""

    __slots__ = ("_read",)

    def __init__(self, read_exact) -> None:
        if not callable(read_exact):
            _fail("task0 exact reader differs")
        self._read = read_exact

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        return self._read(identity)


class GCSStoreV1:
    def __init__(self) -> None:
        try:
            from google.cloud import storage
        except ImportError as exc:
            raise DiscoveryMatrixRunnerV1Error("google storage dependency absent") from exc
        self._client = storage.Client(project=PROJECT)

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://") or "/" not in uri[5:]:
            _fail("GCS URI differs")
        return tuple(uri[5:].split("/", 1))  # type: ignore[return-value]

    def _blob(self, identity: Mapping[str, object]):
        retained = _identity(identity, label="GCS object")
        bucket, name = self._parts(retained["uri"])
        return self._client.bucket(bucket).blob(name, generation=int(retained["generation"])), retained

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        blob, retained = self._blob(identity)
        raw = blob.download_as_bytes(timeout=600, checksum="auto")
        if len(raw) != retained["bytes"] or sha256(raw).hexdigest() != retained["sha256"]:
            _fail("GCS exact bytes differ")
        return raw

    def fetch_exact_to_file(self, identity: Mapping[str, object], path: Path) -> None:
        blob, retained = self._blob(identity)
        path = Path(path)
        if not path.is_absolute() or path.exists() or path.is_symlink():
            _fail("GCS destination differs")
        blob.download_to_filename(str(path), timeout=3600, checksum="auto")
        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        if path.stat().st_size != retained["bytes"] or digest.hexdigest() != retained["sha256"]:
            _fail("GCS streamed exact file differs")

    def _receipt(self, uri: str, blob, digest: str, size: int) -> dict:
        blob.reload()
        identity = {"uri": uri, "generation": str(blob.generation), "sha256": digest, "bytes": size}
        return _identity(identity, label="GCS publication receipt")

    def publish_bytes_create_once(self, uri: str, raw: bytes) -> Mapping[str, object]:
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        blob.upload_from_string(raw, if_generation_match=0, checksum="auto", timeout=600)
        return self._receipt(uri, blob, sha256(raw).hexdigest(), len(raw))

    def publish_file_create_once(self, uri: str, path: Path) -> Mapping[str, object]:
        path = Path(path)
        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        size = path.stat().st_size
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        blob.upload_from_filename(str(path), if_generation_match=0, checksum="auto", timeout=3600)
        return self._receipt(uri, blob, digest.hexdigest(), size)

    def open_known(self, uri: str, maximum_bytes: int) -> tuple[bytes, Mapping[str, object]]:
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        blob.reload()
        if type(blob.size) is not int or not 0 < blob.size <= maximum_bytes:
            _fail("known object byte size differs")
        generation = str(blob.generation)
        exact = self._client.bucket(bucket).blob(name, generation=int(generation))
        raw = exact.download_as_bytes(timeout=600, checksum="auto")
        identity = _identity({
            "uri": uri, "generation": generation,
            "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
        }, label="known object")
        return raw, identity


class GCloudProviderV1:
    def completed(self, execution_id: str) -> Mapping[str, object]:
        if _EXECUTION.fullmatch(execution_id) is None:
            _fail("provider execution name differs")
        completed = subprocess.run(
            ["gcloud", "run", "jobs", "executions", "describe", execution_id,
             "--project", PROJECT, "--region", REGION, "--format=json"],
            check=True, capture_output=True, text=True,
        )
        value = json.loads(completed.stdout)
        metadata = value.get("metadata", {})
        spec = value.get("spec", {})
        template = spec.get("template", {}).get("spec", {})
        containers = template.get("containers", [])
        if not isinstance(containers, list) or len(containers) != 1:
            _fail("provider execution container census differs")
        container = containers[0]
        raw_environment = container.get("env", [])
        if not isinstance(raw_environment, list):
            _fail("provider execution environment differs")
        environment: dict[str, str] = {}
        for row in raw_environment:
            if (
                not isinstance(row, Mapping)
                or type(row.get("name")) is not str
                or type(row.get("value")) is not str
                or row["name"] in environment
            ):
                _fail("provider execution environment differs")
            environment[row["name"]] = row["value"]
        limits = container.get("resources", {}).get("limits", {})
        if not isinstance(limits, Mapping):
            _fail("provider execution resource limits differ")
        status = value.get("status", {})
        labels = metadata.get("labels", {})
        annotations = metadata.get("annotations", {})
        terminal = any(
            row.get("type") == "Completed" and row.get("status") == "True"
            for row in status.get("conditions", [])
        )
        return {
            "execution_id": value.get("metadata", {}).get("name"),
            "execution_uid": metadata.get("uid"),
            "job_name": labels.get("run.googleapis.com/job"),
            "job_uid": (
                labels.get("run.googleapis.com/jobUid")
                or annotations.get("run.googleapis.com/jobUid")
            ),
            "task_count": spec.get("taskCount"),
            "parallelism": spec.get("parallelism"),
            "succeeded_count": status.get("succeededCount", 0),
            "failed_count": status.get("failedCount", 0),
            "cancelled_count": status.get("cancelledCount", 0),
            "running_count": status.get("runningCount", 0),
            "max_retries": template.get("maxRetries"),
            "timeout_seconds": template.get("timeoutSeconds"),
            "service_account": template.get("serviceAccountName"),
            "immutable_image": container.get("image"),
            "command": container.get("command", []),
            "args": container.get("args", []),
            "resources": {
                "cpu": limits.get("cpu"),
                "memory": limits.get("memory"),
            },
            "environment": environment,
            "terminal": terminal,
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    for mode in ("prepare", "collect", "reopen-collect"):
        command = commands.add_parser(mode)
        command.add_argument("--request", type=Path, required=True)
        command.add_argument("--execute", action="store_true")
    for mode in ("task0", "task"):
        command = commands.add_parser(mode)
        command.add_argument("--manifest-identity", type=Path, required=True)
        command.add_argument("--execute", action="store_true")
    reopen = commands.add_parser("reopen-task")
    reopen.add_argument("--terminal-identity", type=Path, required=True)
    reopen.add_argument("--execute", action="store_true")
    gate = commands.add_parser("task0-gate")
    gate.add_argument("--manifest-identity", type=Path, required=True)
    gate.add_argument("--task0-receipt", type=Path, required=True)
    gate.add_argument("--execution-id", required=True)
    gate.add_argument("--execute", action="store_true")
    return parser


def run(
    argv: Sequence[str] | None = None, *, environment: Mapping[str, str] | None = None,
    store: Store | None = None, provider: Provider | None = None,
) -> dict[str, object]:
    args = _parser().parse_args(argv)
    env = dict(os.environ if environment is None else environment)
    if args.execute is not True or env.get(ENABLE_ENV) != ENABLE_VALUE:
        _fail("discovery matrix execution is disabled")
    if env.get(MODE_ENV) != args.mode or env.get(OUTCOMES_ENV) != "false":
        _fail("discovery matrix mode/outcome boundary differs")
    retained_store = store or GCSStoreV1()
    if args.mode == "prepare":
        return prepare(_read_file(args.request, label="prepare request"), store=retained_store)
    if args.mode in {"task0", "task"}:
        identity = _read_file(args.manifest_identity, label="manifest identity")
        task_store: Store | ReadOnlyStore = retained_store
        if args.mode == "task0":
            task_store = ReadOnlyStoreAdapterV1(retained_store.read_exact)
        with tempfile.TemporaryDirectory(prefix="r6-discovery-matrix-") as directory:
            return task(
                identity, store=task_store, environment=env,
                smoke=args.mode == "task0", workspace=Path(directory),
            )
    if args.mode == "task0-gate":
        return validate_task0_gate(
            manifest_identity=_read_file(
                args.manifest_identity, label="task0 gate manifest identity"
            ),
            task0_receipt_value=_read_file(
                args.task0_receipt, label="task0 stdout receipt"
            ),
            execution_id=args.execution_id,
            store=ReadOnlyStoreAdapterV1(retained_store.read_exact),
            provider=provider or GCloudProviderV1(),
        )
    if args.mode == "collect":
        return collect(
            _read_file(args.request, label="collect request"), store=retained_store,
            provider=provider or GCloudProviderV1(),
        )
    if args.mode == "reopen-task":
        with tempfile.TemporaryDirectory(prefix="r6-discovery-matrix-reopen-") as directory:
            return reopen_task(
                _read_file(args.terminal_identity, label="terminal identity"),
                store=retained_store, environment=env, workspace=Path(directory),
            )
    return reopen_collect(
        _read_file(args.request, label="reopen collect request"),
        store=retained_store, provider=provider or GCloudProviderV1(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        value = run(argv)
    except (
        DiscoveryMatrixRunnerV1Error,
        freeze.CorpusR6PaidSourceDiscoveryMatrixFreezeV1Error,
        OSError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    sys.stdout.buffer.write(_canonical(value) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
