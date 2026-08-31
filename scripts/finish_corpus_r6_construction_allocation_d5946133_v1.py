#!/usr/bin/env python3
"""Crash-closed host finisher for the frozen d5946133 construction chain.

This driver does not implement scientific work.  It invokes the immutable
``d5946133`` launcher from its clean checkout, follows only exact Cloud Run
execution names, reads only those executions' stdout receipts, and derives
each next canonical request from a validated predecessor receipt.  It never
lists jobs, executions, storage prefixes, or scientific objects.

The default action is inert.  A mutating phase requires both ``--execute`` and
the literal confirmation printed by ``--help``.  Local state is create-once
where it carries authority; an ambiguous launch intent without a launch
receipt fails closed for manual reconciliation rather than relaunching.
"""

from __future__ import annotations

import argparse
import base64
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Final


REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
CLEAN_ROOT: Final = (
    REPOSITORY_ROOT / ".build-contexts" / "construction-d5946133"
)
IMMUTABLE_LAUNCHER: Final = (
    CLEAN_ROOT
    / "scripts"
    / "cloud_corpus_r6_construction_allocation_snapshot_v1.sh"
)
DEFAULT_RUN_DIR: Final = (
    REPOSITORY_ROOT
    / ".tmp"
    / "construction-allocation-d5946133-post54-finisher-v1"
)

PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
JOB: Final = "atlas-cbc-32g-full-2023-w8-v1"
JOB_UID: Final = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
JOB_GENERATION: Final = "42"
SERVICE_ACCOUNT: Final = "817589974517-compute@developer.gserviceaccount.com"
CODE_SHA: Final = "d5946133ebba0955586816c15905065c3ec71a0f"
BUILD_ID: Final = "aeb293f7-6e95-47c2-b6fe-3df7141c2fcd"
IMAGE_DIGEST: Final = (
    "sha256:e8959e94cf41f0a0f63bf97d4631e0c7c799af7594675a0f037ed7625a2280a7"
)
IMMUTABLE_IMAGE: Final = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
    f"nfl-dfs@{IMAGE_DIGEST}"
)
SOURCE_EXECUTION_NAME: Final = "atlas-cbc-32g-full-2023-w8-v1-nsvkd"
SOURCE_EXECUTION_UID: Final = "cde282a2-2a02-464a-84f4-70b822e9aac0"
SOURCE_TASK_COUNT: Final = 54

ENABLE_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_SNAPSHOT_SHARD_ENABLE"
ENABLE_VALUE: Final = "I_UNDERSTAND_SCORE_BLIND_CONSTRUCTION_CROSS_V1"
MANIFEST_ENV: Final = (
    "R6_CONSTRUCTION_ALLOCATION_SNAPSHOT_SHARD_MANIFEST_IDENTITY"
)
REQUEST_B64_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_CLOUD_REQUEST_B64"
REQUEST_SHA_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_CLOUD_REQUEST_SHA256"
TASK_EXECUTION_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_TASK_EXECUTION_NAME"
GRADE_ENABLE_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_GRADE_ENABLED"
GRADE_CODE_SHA_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_GRADE_CODE_SHA"
GRADE_IMAGE_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_GRADE_RUNTIME_IMAGE"

CONFIRMATION: Final = "I_UNDERSTAND_D5946133_POST54_FINISHER_V1"
GRADE_RUN_ID: Final = "20260830-construction-allocation-d5946133-grade-v1"
GRADE_ID: Final = "construction-allocation-cross-realized-v1"
GRADE_OUTPUT_PREFIX: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-construction-allocation-grades"
)
GRADE_MANIFEST_URI: Final = (
    f"{GRADE_OUTPUT_PREFIX}/{GRADE_RUN_ID}/grade-manifest.json"
)

SOURCE_MANIFEST_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-construction-allocation-snapshot-shards/"
        "20260830-construction-allocation-d5946133-v1/input-manifest.json"
    ),
    "generation": "1788111932751802",
    "sha256": "bbe47919f0dd753f8f7278f5f3d3e022bd70c2879c3f826dcd31e207ab1d4536",
    "bytes": 60_541,
}
OUTCOME_COMPLETION_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-catalog-wide-realized/"
        "20260829-score-sprint-c9f12ed7-catalog-outcomes-v1/completion.json"
    ),
    "generation": "1787987567275104",
    "sha256": "15852361756ef0fe76d3a299617ebc2c2531e6821a73f04c8f862bf7229f4df3",
    "bytes": 2_521,
}
OUTCOME_SNAPSHOT_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-catalog-wide-realized/"
        "20260829-score-sprint-c9f12ed7-catalog-outcomes-v1/"
        "outcome-snapshot.json"
    ),
    "generation": "1787987566557209",
    "sha256": "96c88d27cfa356794e250431dbcaa638fe7df2ec8dc1a9ead8538f0608c32f88",
    "bytes": 3_547_704,
}
HISTORICAL_OUTCOME_LEASE_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-raw/research-governance/"
        "historical-outcome-active-v1.json"
    ),
    "generation": "1787987508020795",
    "sha256": "22b513c5e6824677d0b4feb6037c27b5b6e00f210a986beab2ea626df6012ee7",
    "bytes": 392,
}

COLLECT_SCHEMA: Final = (
    "corpus-r6-construction-allocation-snapshot-shard-collect/v1"
)
GRADE_PREPARED_SCHEMA: Final = (
    "corpus-r6-construction-allocation-grade-prepared/v1"
)
GRADE_PUBLISHED_SCHEMA: Final = (
    "corpus-r6-construction-allocation-grade-published/v1"
)
GRADE_REOPEN_SCHEMA: Final = (
    "corpus-r6-construction-allocation-grade-independent-reopen/v1"
)
LAUNCH_SCHEMA: Final = "corpus-r6-construction-allocation-cloud-launch/v1"

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_EXECUTION = re.compile(re.escape(JOB) + r"-[a-z0-9]{5}\Z")


class FinisherError(RuntimeError):
    """A frozen authority, provider receipt, or local state differed."""


def _fail(message: str) -> None:
    raise FinisherError(message)


def canonical_bytes(value: object, *, newline: bool = True) -> bytes:
    try:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise FinisherError("canonical JSON differs") from exc
    return raw + (b"\n" if newline else b"")


def canonical_sha256(value: object) -> str:
    return sha256(canonical_bytes(value, newline=False)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} is not one string-keyed object")
    return dict(value)


def _identity(
    value: object,
    *,
    label: str,
    allow_create_once: bool = True,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    allowed = {"uri", "generation", "sha256", "bytes"}
    if allow_create_once:
        allowed.add("create_once")
    if set(item) not in ({"uri", "generation", "sha256", "bytes"}, allowed):
        _fail(f"{label} fields differ")
    if (
        type(item.get("uri")) is not str
        or not str(item["uri"]).startswith("gs://")
        or type(item.get("generation")) not in {str, int}
        or not str(item["generation"])
        or type(item.get("sha256")) is not str
        or _SHA.fullmatch(str(item["sha256"])) is None
        or type(item.get("bytes")) is not int
        or int(item["bytes"]) <= 0
        or ("create_once" in item and item["create_once"] is not True)
    ):
        _fail(f"{label} differs")
    retained = {
        "uri": item["uri"],
        "generation": str(item["generation"]),
        "sha256": item["sha256"],
        "bytes": item["bytes"],
    }
    if item.get("create_once") is True:
        retained["create_once"] = True
    return retained


def _parse_canonical_value(raw: bytes, *, label: str) -> object:
    if not raw or raw.endswith(b"\n\n"):
        _fail(f"{label} bytes differ")
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FinisherError(f"{label} is not JSON") from exc
    if raw not in {
        canonical_bytes(value, newline=False),
        canonical_bytes(value, newline=True),
    }:
        _fail(f"{label} is not canonical JSON")
    return value


def _parse_canonical(raw: bytes, *, label: str) -> dict[str, object]:
    return _mapping(_parse_canonical_value(raw, label=label), label=label)


def _parse_launcher_json(raw: bytes, *, label: str) -> dict[str, object]:
    """Parse the launcher's single JSON object before canonical persistence.

    The immutable shell launcher emits its receipt with ``jq``'s default
    pretty formatting.  Provider/result documents remain canonical-only; this
    boundary accepts formatting variance only for that one launcher receipt,
    rejects any prefix/suffix or second document, and immediately persists the
    validated value as canonical JSON.
    """
    if not raw:
        _fail(f"{label} bytes differ")
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FinisherError(f"{label} is not one JSON document") from exc
    return _mapping(value, label=label)


def _read_canonical(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        _fail(f"{label} is not one absolute regular file")
    return _parse_canonical(path.read_bytes(), label=label)


def _read_canonical_value(path: Path, *, label: str) -> object:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        _fail(f"{label} is not one absolute regular file")
    return _parse_canonical_value(path.read_bytes(), label=label)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_local_once(path: Path, raw: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != raw:
            _fail(f"local create-once collision: {path}")
        return
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    _fsync_directory(path.parent)


def _replace_local(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    if temporary.exists() or temporary.is_symlink():
        _fail(f"temporary local state already exists: {temporary}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def _validated_run_dir(value: Path) -> Path:
    if not value.is_absolute():
        _fail("run directory must be absolute")
    base = (REPOSITORY_ROOT / ".tmp").resolve()
    retained = value.resolve(strict=False)
    if retained == base or base not in retained.parents:
        _fail("run directory must remain below the disk-backed repository .tmp")
    clean = CLEAN_ROOT.resolve()
    if retained == clean or clean in retained.parents:
        _fail("run directory must remain outside the clean d5946133 checkout")
    cursor = retained
    while cursor != base:
        if cursor.exists() and cursor.is_symlink():
            _fail("run directory may not traverse a symlink")
        cursor = cursor.parent
    retained.mkdir(parents=True, exist_ok=True, mode=0o700)
    return retained


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class CommandRunner:
    """Small injectable command boundary; never invokes a shell."""

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        completed = subprocess.run(
            list(argv),
            cwd=None if cwd is None else str(cwd),
            env=None if env is None else dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _json_command(
    runner: CommandRunner,
    argv: Sequence[str],
    *,
    label: str,
) -> tuple[dict[str, object], bytes]:
    result = runner.run(argv)
    if result.returncode != 0:
        _fail(f"{label} failed")
    try:
        parsed = json.loads(result.stdout)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FinisherError(f"{label} output is not JSON") from exc
    return _mapping(parsed, label=label), canonical_bytes(parsed)


def _condition_status(execution: Mapping[str, object]) -> str | None:
    status = _mapping(execution.get("status", {}), label="execution status")
    conditions = status.get("conditions", [])
    if not isinstance(conditions, list):
        _fail("execution conditions differ")
    values = [
        str(row.get("status"))
        for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if len(values) > 1:
        _fail("execution completion condition differs")
    return values[0] if values else None


def _count(execution: Mapping[str, object], field: str) -> int:
    status = _mapping(execution.get("status", {}), label="execution status")
    value = status.get(field, 0)
    if value in {None, ""}:
        return 0
    if type(value) is not int or value < 0:
        _fail(f"execution {field} differs")
    return value


def _container(execution: Mapping[str, object]) -> dict[str, object]:
    spec = _mapping(execution.get("spec"), label="execution spec")
    template = _mapping(spec.get("template"), label="execution template")
    task_spec = _mapping(template.get("spec"), label="execution task spec")
    containers = task_spec.get("containers")
    if not isinstance(containers, list) or len(containers) != 1:
        _fail("execution container count differs")
    return _mapping(containers[0], label="execution container")


def _task_spec(execution: Mapping[str, object]) -> dict[str, object]:
    spec = _mapping(execution.get("spec"), label="execution spec")
    template = _mapping(spec.get("template"), label="execution template")
    return _mapping(template.get("spec"), label="execution task spec")


def _env_map(container: Mapping[str, object]) -> dict[str, str]:
    raw = container.get("env")
    if not isinstance(raw, list):
        _fail("execution environment differs")
    result: dict[str, str] = {}
    for row in raw:
        item = _mapping(row, label="execution environment row")
        name, value = item.get("name"), item.get("value")
        if type(name) is not str or type(value) is not str or name in result:
            _fail("execution environment row differs")
        result[name] = value
    return result


def _validate_execution_identity(
    execution: object,
    *,
    name: str,
    uid: str,
    task_count: int,
) -> dict[str, object]:
    item = _mapping(execution, label="provider execution")
    metadata = _mapping(item.get("metadata"), label="execution metadata")
    labels = _mapping(metadata.get("labels"), label="execution labels")
    spec = _mapping(item.get("spec"), label="execution spec")
    task_spec = _task_spec(item)
    container = _container(item)
    timeout = task_spec.get("timeout", task_spec.get("timeoutSeconds"))
    if (
        metadata.get("name") != name
        or metadata.get("uid") != uid
        or _EXECUTION.fullmatch(name) is None
        or _UUID.fullmatch(uid) is None
        or labels.get("run.googleapis.com/job") != JOB
        or labels.get("run.googleapis.com/jobUid") != JOB_UID
        or spec.get("taskCount") != task_count
        or spec.get("parallelism") not in {1, 4}
        or task_spec.get("maxRetries") != 0
        or task_spec.get("serviceAccountName") != SERVICE_ACCOUNT
        or timeout not in {"21600", "21600s", "21600.000000000s"}
        or container.get("image") != IMMUTABLE_IMAGE
        or container.get("command") != ["/bin/bash"]
        or _mapping(container.get("resources"), label="container resources")
        .get("limits")
        != {"cpu": "8", "memory": "32Gi"}
    ):
        _fail("provider execution immutable authority differs")
    return item


def source_request_v1() -> dict[str, object]:
    return {"manifest_identity": dict(SOURCE_MANIFEST_IDENTITY)}


def validate_source_execution_v1(execution: object) -> dict[str, object]:
    item = _validate_execution_identity(
        execution,
        name=SOURCE_EXECUTION_NAME,
        uid=SOURCE_EXECUTION_UID,
        task_count=SOURCE_TASK_COUNT,
    )
    metadata = _mapping(item["metadata"], label="source execution metadata")
    labels = _mapping(metadata["labels"], label="source execution labels")
    container = _container(item)
    environment = _env_map(container)
    request_raw = canonical_bytes(source_request_v1())
    expected = {
        "CODE_SHA": CODE_SHA,
        "IMAGE_DIGEST": IMAGE_DIGEST,
        "BUILD_ID": BUILD_ID,
        ENABLE_ENV: ENABLE_VALUE,
        MANIFEST_ENV: canonical_bytes(
            SOURCE_MANIFEST_IDENTITY, newline=False
        ).decode("ascii"),
        REQUEST_SHA_ENV: sha256(request_raw).hexdigest(),
        REQUEST_B64_ENV: base64.b64encode(request_raw).decode("ascii"),
        "R6_CONSTRUCTION_ALLOCATION_JOB_NAME": JOB,
        "R6_CONSTRUCTION_ALLOCATION_FULL_IMAGE": IMMUTABLE_IMAGE,
        "R6_CONSTRUCTION_ALLOCATION_NO_OUTCOME_SMOKE": "false",
        "R6_CONSTRUCTION_ALLOCATION_TARGET_OUTCOMES_ALLOWED": "false",
    }
    if (
        labels.get("run.googleapis.com/jobGeneration") != JOB_GENERATION
        or container.get("args")
        != [str(IMMUTABLE_LAUNCHER).replace(str(CLEAN_ROOT), "/app"), "container-task"]
        or any(environment.get(key) != value for key, value in expected.items())
    ):
        _fail("source 54-task execution authority differs")
    return item


PHASES: Final = (
    "collect",
    "reopen",
    "grade-prepare",
    "grade",
    "grade-reopen",
)


def _phase_schema(phase: str) -> str:
    return {
        "collect": COLLECT_SCHEMA,
        "reopen": COLLECT_SCHEMA,
        "grade-prepare": GRADE_PREPARED_SCHEMA,
        "grade": GRADE_PUBLISHED_SCHEMA,
        "grade-reopen": GRADE_REOPEN_SCHEMA,
    }[phase]


def _phase_args(phase: str) -> list[str]:
    base = "/app/scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh"
    if phase in {"collect", "reopen"}:
        return [base, "container-request", phase]
    return [base, "container-grade", phase]


def _phase_uses_outcomes(phase: str) -> bool:
    return phase in {"grade", "grade-reopen"}


def _phase_is_grade(phase: str) -> bool:
    return phase in {"grade-prepare", "grade", "grade-reopen"}


def _request_bound_identity(phase: str, request: Mapping[str, object]) -> dict[str, object]:
    if phase in {"collect", "reopen"}:
        return _identity(request["manifest_identity"], label="selection manifest")
    if phase == "grade-prepare":
        envelope = _mapping(
            request["selection_terminal_envelope"],
            label="selection terminal envelope",
        )
        return _identity(envelope["terminal_identity"], label="selection terminal")
    if phase == "grade":
        return _identity(request["manifest_identity"], label="grade manifest")
    envelope = _mapping(request["terminal_envelope"], label="grade terminal envelope")
    return _identity(envelope["manifest_identity"], label="grade manifest")


def transport_request_v1(
    *,
    phase: str,
    request: Mapping[str, object],
    launch_receipt: Mapping[str, object],
) -> dict[str, object]:
    """Reconstruct the exact request bytes embedded in the execution.

    The immutable d594 launcher expands the manifest-only host request for
    collect/reopen with the newly published runtime-execution attestation.
    All grade phases transport the caller request unchanged.
    """

    if phase not in {"collect", "reopen"}:
        return dict(request)
    return {
        "manifest_identity": _identity(
            request["manifest_identity"], label="selection manifest"
        ),
        "runtime_execution_attestation_identity": _identity(
            launch_receipt["runtime_execution_attestation_identity"],
            label="runtime execution attestation",
        ),
    }


def validate_launch_receipt_v1(
    value: object,
    *,
    phase: str,
    request: Mapping[str, object],
    request_raw: bytes,
) -> dict[str, object]:
    item = _mapping(value, label=f"{phase} launch receipt")
    expected_fields = {
        "schema_version",
        "phase",
        "code_sha",
        "cloud_build_id",
        "provider_resolved_image",
        "image_digest",
        "reused_job",
        "execution",
        "bound_input_authority_identity",
        "manifest_identity",
        "runtime_execution_attestation_identity",
        "source_task_execution",
        "request_sha256",
        "no_outcome_smoke_mode",
        "target_slate_outcomes_allowed",
        "execution_provider_reopened",
        "complete",
    }
    bound = _request_bound_identity(phase, request)
    reused = _mapping(item.get("reused_job"), label="launch reused job")
    execution = _mapping(item.get("execution"), label="launch execution")
    if (
        set(item) != expected_fields
        or item.get("schema_version") != LAUNCH_SCHEMA
        or item.get("phase") != phase
        or item.get("code_sha") != CODE_SHA
        or item.get("cloud_build_id") != BUILD_ID
        or item.get("provider_resolved_image") != IMMUTABLE_IMAGE
        or item.get("image_digest") != IMAGE_DIGEST
        or reused
        != {"name": JOB, "uid": JOB_UID, "generation": int(JOB_GENERATION)}
        or set(execution) != {"name", "uid", "task_count"}
        or _EXECUTION.fullmatch(str(execution.get("name", ""))) is None
        or _UUID.fullmatch(str(execution.get("uid", ""))) is None
        or execution.get("task_count") != 1
        or item.get("bound_input_authority_identity") != bound
        or item.get("manifest_identity") != bound
        or item.get("no_outcome_smoke_mode") is not False
        or item.get("target_slate_outcomes_allowed")
        is not _phase_uses_outcomes(phase)
        or item.get("execution_provider_reopened") is not True
        or item.get("complete") is not True
    ):
        _fail(f"{phase} launch receipt differs")
    if phase in {"collect", "reopen"}:
        source = _mapping(
            item.get("source_task_execution"), label="source task execution"
        )
        attestation = _identity(
            item.get("runtime_execution_attestation_identity"),
            label="runtime execution attestation",
        )
        expected_suffix = (
            "/authorities/runtime-execution-attestation-"
            f"{SOURCE_EXECUTION_NAME}.json"
        )
        if (
            source
            != {
                "name": SOURCE_EXECUTION_NAME,
                "uid": SOURCE_EXECUTION_UID,
                "task_count": SOURCE_TASK_COUNT,
            }
            or not str(attestation["uri"]).endswith(expected_suffix)
        ):
            _fail(f"{phase} source execution authority differs")
    elif (
        item.get("source_task_execution") is not None
        or item.get("runtime_execution_attestation_identity") is not None
    ):
        _fail(f"{phase} unexpectedly carries source execution authority")
    if request_raw != canonical_bytes(request):
        _fail(f"{phase} host request bytes differ")
    transported_raw = canonical_bytes(
        transport_request_v1(
            phase=phase, request=request, launch_receipt=item
        )
    )
    if item.get("request_sha256") != sha256(transported_raw).hexdigest():
        _fail(f"{phase} transported request hash differs")
    return item


def validate_phase_execution_v1(
    execution_value: object,
    *,
    phase: str,
    execution_name: str,
    execution_uid: str,
    request: Mapping[str, object],
    request_raw: bytes,
    launch_receipt: Mapping[str, object],
) -> dict[str, object]:
    item = _validate_execution_identity(
        execution_value,
        name=execution_name,
        uid=execution_uid,
        task_count=1,
    )
    metadata = _mapping(item["metadata"], label="phase execution metadata")
    labels = _mapping(metadata["labels"], label="phase execution labels")
    container = _container(item)
    environment = _env_map(container)
    bound = _request_bound_identity(phase, request)
    if request_raw != canonical_bytes(request):
        _fail(f"{phase} host request bytes differ")
    transported_raw = canonical_bytes(
        transport_request_v1(
            phase=phase, request=request, launch_receipt=launch_receipt
        )
    )
    expected = {
        "CODE_SHA": CODE_SHA,
        "IMAGE_DIGEST": IMAGE_DIGEST,
        "BUILD_ID": BUILD_ID,
        ENABLE_ENV: ENABLE_VALUE,
        MANIFEST_ENV: canonical_bytes(bound, newline=False).decode("ascii"),
        REQUEST_SHA_ENV: sha256(transported_raw).hexdigest(),
        REQUEST_B64_ENV: base64.b64encode(transported_raw).decode("ascii"),
        "R6_CONSTRUCTION_ALLOCATION_JOB_NAME": JOB,
        "R6_CONSTRUCTION_ALLOCATION_FULL_IMAGE": IMMUTABLE_IMAGE,
        "R6_CONSTRUCTION_ALLOCATION_NO_OUTCOME_SMOKE": "false",
        "R6_CONSTRUCTION_ALLOCATION_TARGET_OUTCOMES_ALLOWED": (
            "true" if _phase_uses_outcomes(phase) else "false"
        ),
    }
    if _phase_is_grade(phase):
        expected.update(
            {
                GRADE_ENABLE_ENV: "1",
                GRADE_CODE_SHA_ENV: CODE_SHA,
                GRADE_IMAGE_ENV: IMMUTABLE_IMAGE,
            }
        )
    launch_job = _mapping(launch_receipt["reused_job"], label="launch job")
    if (
        labels.get("run.googleapis.com/jobGeneration")
        != str(launch_job["generation"])
        or container.get("args") != _phase_args(phase)
        or any(environment.get(key) != value for key, value in expected.items())
    ):
        _fail(f"{phase} provider execution contract differs")
    return item


def _validate_self_hash(value: Mapping[str, object], field: str, *, label: str) -> None:
    body = dict(value)
    retained = body.pop(field, None)
    if type(retained) is not str or _SHA.fullmatch(retained) is None:
        _fail(f"{label} hash differs")
    if canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")


_SELECTION_ENVELOPE_FIELDS: Final = {
    "schema_version",
    "terminal_identity",
    "terminal_sha256",
    "selection_identity",
    "selection_receipt_sha256",
    "runtime_build_attestation_identity",
    "execution_authority_sha256",
    "execution_reopen_receipt_sha256",
    "runtime_execution_attestation_identity",
    "multiplicity_family_sha256",
    "independent_audit_evaluation_authority_available",
    "unconsumed_audit_placeholder_count",
    "upstream_reopen_receipt_sha256",
    "complete",
    "create_once",
    "uses_target_slate_outcomes",
    "envelope_sha256",
}


def validate_selection_envelope_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="selection terminal envelope")
    if (
        set(item) != _SELECTION_ENVELOPE_FIELDS
        or item.get("schema_version")
        != "corpus-r6-construction-allocation-terminal-envelope/v1"
        or item.get("complete") is not True
        or item.get("create_once") is not True
        or item.get("uses_target_slate_outcomes") is not False
        or item.get("independent_audit_evaluation_authority_available") is not False
        or item.get("unconsumed_audit_placeholder_count") != SOURCE_TASK_COUNT
    ):
        _fail("selection terminal envelope differs")
    _identity(item["terminal_identity"], label="selection terminal identity")
    _identity(item["selection_identity"], label="selection identity")
    _identity(
        item["runtime_build_attestation_identity"], label="runtime build identity"
    )
    _identity(
        item["runtime_execution_attestation_identity"],
        label="runtime execution identity",
    )
    for field in (
        "terminal_sha256",
        "selection_receipt_sha256",
        "execution_authority_sha256",
        "execution_reopen_receipt_sha256",
        "multiplicity_family_sha256",
        "upstream_reopen_receipt_sha256",
    ):
        if type(item.get(field)) is not str or _SHA.fullmatch(str(item[field])) is None:
            _fail(f"selection envelope {field} differs")
    _validate_self_hash(item, "envelope_sha256", label="selection envelope")
    return item


_COLLECT_FIELDS: Final = {
    "schema_version",
    "manifest_identity",
    "manifest_sha256",
    "provider_build_receipt",
    "provider_execution_receipt",
    "shard_count",
    "shard_identities_sha256",
    "selection_receipt_sha256",
    "terminal_envelope",
    "terminal_reopen_complete",
    "all_shards_resolved_by_deterministic_name_without_listing",
    "all_shards_generation_exact_reopened",
    "selection_published_before_terminal_root",
    "selection_upstream_authorities_generation_exact_reopened",
    "input_manifest_and_ordered_shards_generation_exact_reopened",
    "runtime_execution_provider_attestation_exact_reopened",
    "audit_placeholders_have_evaluation_authority",
    "outcome_data_accessed",
    "grading_performed",
    "deployment_mutation_performed",
    "execution_launched",
    "automatic_relaunch",
    "complete",
    "collect_sha256",
}


def validate_collect_result_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="selection collect result")
    positive = (
        "terminal_reopen_complete",
        "all_shards_resolved_by_deterministic_name_without_listing",
        "all_shards_generation_exact_reopened",
        "selection_published_before_terminal_root",
        "selection_upstream_authorities_generation_exact_reopened",
        "input_manifest_and_ordered_shards_generation_exact_reopened",
        "runtime_execution_provider_attestation_exact_reopened",
        "complete",
    )
    negative = (
        "audit_placeholders_have_evaluation_authority",
        "outcome_data_accessed",
        "grading_performed",
        "deployment_mutation_performed",
        "execution_launched",
        "automatic_relaunch",
    )
    provider = _mapping(
        item.get("provider_execution_receipt"), label="provider execution receipt"
    )
    if (
        set(item) != _COLLECT_FIELDS
        or item.get("schema_version") != COLLECT_SCHEMA
        or item.get("manifest_identity") != SOURCE_MANIFEST_IDENTITY
        or item.get("shard_count") != SOURCE_TASK_COUNT
        or any(item.get(field) is not True for field in positive)
        or any(item.get(field) is not False for field in negative)
        or provider.get("execution_name") != SOURCE_EXECUTION_NAME
        or provider.get("execution_uid") != SOURCE_EXECUTION_UID
        or provider.get("task_count") != SOURCE_TASK_COUNT
        or provider.get("succeeded_count") != SOURCE_TASK_COUNT
        or provider.get("code_sha") != CODE_SHA
        or provider.get("image_digest") != IMAGE_DIGEST
        or provider.get("provider_observed") is not True
    ):
        _fail("selection collect result authority differs")
    for field in (
        "manifest_sha256",
        "shard_identities_sha256",
        "selection_receipt_sha256",
    ):
        if type(item.get(field)) is not str or _SHA.fullmatch(str(item[field])) is None:
            _fail(f"selection collect {field} differs")
    validate_selection_envelope_v1(item["terminal_envelope"])
    _validate_self_hash(item, "collect_sha256", label="selection collect")
    return item


_GRADE_ENVELOPE_FIELDS: Final = {
    "schema_version",
    "terminal_identity",
    "terminal_sha256",
    "manifest_identity",
    "manifest_sha256",
    "historical_outcome_lease_identity",
    "terminal_root_was_last_scientific_publication",
    "historical_outcome_lease_release_required",
    "lease_release_owner",
    "complete",
    "envelope_sha256",
}


def validate_grade_envelope_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="grade terminal envelope")
    if (
        set(item) != _GRADE_ENVELOPE_FIELDS
        or item.get("schema_version")
        != "corpus-r6-construction-allocation-grade-terminal-envelope/v1"
        or item.get("historical_outcome_lease_identity")
        != HISTORICAL_OUTCOME_LEASE_IDENTITY
        or item.get("terminal_root_was_last_scientific_publication") is not True
        or item.get("historical_outcome_lease_release_required") is not True
        or item.get("lease_release_owner") != "external-launcher-watcher"
        or item.get("complete") is not True
    ):
        _fail("grade terminal envelope differs")
    _identity(item["terminal_identity"], label="grade terminal identity")
    _identity(item["manifest_identity"], label="grade manifest identity")
    for field in ("terminal_sha256", "manifest_sha256"):
        if type(item.get(field)) is not str or _SHA.fullmatch(str(item[field])) is None:
            _fail(f"grade envelope {field} differs")
    _validate_self_hash(item, "envelope_sha256", label="grade envelope")
    return item


def validate_result_v1(value: object, *, phase: str) -> dict[str, object]:
    item = _mapping(value, label=f"{phase} operator result")
    if item.get("schema_version") != _phase_schema(phase):
        _fail(f"{phase} result schema differs")
    if phase in {"collect", "reopen"}:
        return validate_collect_result_v1(item)
    if phase == "grade-prepare":
        expected = {
            "schema_version",
            "manifest_identity",
            "manifest_sha256",
            "selection_terminal_identity",
            "outcome_authority_identity",
            "outcome_authority_opened",
            "uses_realized_outcomes",
            "complete",
        }
        if (
            set(item) != expected
            or item.get("outcome_authority_identity") != OUTCOME_COMPLETION_IDENTITY
            or item.get("outcome_authority_opened") is not False
            or item.get("uses_realized_outcomes") is not False
            or item.get("complete") is not True
        ):
            _fail("grade-prepare result differs")
        _identity(item["manifest_identity"], label="grade manifest identity")
        _identity(
            item["selection_terminal_identity"], label="selection terminal identity"
        )
        if type(item.get("manifest_sha256")) is not str or _SHA.fullmatch(
            str(item["manifest_sha256"])
        ) is None:
            _fail("grade-prepare manifest hash differs")
        return item
    if phase == "grade":
        expected = {
            "schema_version",
            "terminal_envelope",
            "terminal_identity",
            "grade_report_identity",
            "historical_outcome_lease_identity",
            "historical_outcome_lease_release_required",
            "lease_release_owner",
            "historical_outcome_lease_released",
            "terminal_reopen_receipt_sha256",
            "uses_realized_outcomes",
            "automatic_retry_licensed",
            "complete",
        }
        envelope = validate_grade_envelope_v1(item.get("terminal_envelope"))
        if (
            set(item) != expected
            or item.get("terminal_identity") != envelope["terminal_identity"]
            or item.get("historical_outcome_lease_identity")
            != HISTORICAL_OUTCOME_LEASE_IDENTITY
            or item.get("historical_outcome_lease_release_required") is not True
            or item.get("lease_release_owner") != "external-launcher-watcher"
            or item.get("historical_outcome_lease_released") is not False
            or item.get("uses_realized_outcomes") is not True
            or item.get("automatic_retry_licensed") is not False
            or item.get("complete") is not True
        ):
            _fail("grade result differs")
        _identity(item["grade_report_identity"], label="grade report identity")
        if type(item.get("terminal_reopen_receipt_sha256")) is not str or _SHA.fullmatch(
            str(item["terminal_reopen_receipt_sha256"])
        ) is None:
            _fail("grade reopen receipt hash differs")
        return item
    expected = {
        "schema_version",
        "reopen_receipt",
        "historical_outcome_lease_identity",
        "historical_outcome_lease_release_required",
        "lease_release_owner",
        "historical_outcome_lease_released",
        "uses_realized_outcomes",
        "complete",
    }
    receipt = _mapping(item.get("reopen_receipt"), label="grade reopen receipt")
    if (
        set(item) != expected
        or item.get("historical_outcome_lease_identity")
        != HISTORICAL_OUTCOME_LEASE_IDENTITY
        or item.get("historical_outcome_lease_release_required") is not True
        or item.get("lease_release_owner") != "external-launcher-watcher"
        or item.get("historical_outcome_lease_released") is not False
        or item.get("uses_realized_outcomes") is not True
        or item.get("complete") is not True
        or receipt.get("outcome_authority_identity") != OUTCOME_COMPLETION_IDENTITY
        or receipt.get("outcome_snapshot_identity") != OUTCOME_SNAPSHOT_IDENTITY
        or receipt.get("historical_outcome_lease_identity")
        != HISTORICAL_OUTCOME_LEASE_IDENTITY
        or receipt.get("historical_outcome_lease_unchanged_during_reopen") is not True
        or receipt.get("selection_predecessor_closure_replayed") is not True
        or receipt.get("outcome_predecessor_closure_replayed") is not True
        or receipt.get("all_grade_children_generation_exact_reopened") is not True
        or receipt.get("grade_independently_recomputed") is not True
        or receipt.get("object_listing_used") is not False
        or receipt.get("overwrite_used") is not False
        or receipt.get("scientific_object_delete_used") is not False
        or receipt.get("uses_realized_outcomes") is not True
        or receipt.get("complete") is not True
    ):
        _fail("grade-reopen result differs")
    _validate_self_hash(receipt, "reopen_sha256", label="grade reopen receipt")
    return item


def result_from_exact_stdout_logs_v1(
    logs_value: object,
    *,
    phase: str,
) -> dict[str, object]:
    if not isinstance(logs_value, list):
        _fail("stdout log result is not an array")
    payloads: list[str] = []
    for row in logs_value:
        item = _mapping(row, label="stdout log entry")
        payload = item.get("textPayload")
        if type(payload) is not str:
            _fail("stdout log entry lacks textPayload")
        payloads.append(payload)
    if len(payloads) != 1:
        _fail("exact execution stdout document count differs")
    raw = payloads[0].encode("utf-8")
    result = _parse_canonical(raw, label=f"{phase} stdout result")
    return validate_result_v1(result, phase=phase)


def grade_prepare_request_v1(
    *,
    reopen_result: Mapping[str, object],
    frozen_at: str,
) -> dict[str, object]:
    reopened = validate_collect_result_v1(reopen_result)
    if type(frozen_at) is not str or not frozen_at.endswith("Z"):
        _fail("grade frozen_at differs")
    try:
        parsed = datetime.fromisoformat(frozen_at[:-1] + "+00:00")
    except ValueError as exc:
        raise FinisherError("grade frozen_at differs") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        _fail("grade frozen_at is not UTC")
    return {
        "schema_version": (
            "corpus-r6-construction-allocation-grade-prepare-request/v1"
        ),
        "run_id": GRADE_RUN_ID,
        "grade_id": GRADE_ID,
        "frozen_at": frozen_at,
        "code_sha": CODE_SHA,
        "immutable_image": IMMUTABLE_IMAGE,
        "output_prefix": GRADE_OUTPUT_PREFIX,
        "selection_terminal_envelope": reopened["terminal_envelope"],
        "outcome_authority_identity": dict(OUTCOME_COMPLETION_IDENTITY),
    }


def grade_request_v1(*, grade_prepare_result: Mapping[str, object]) -> dict[str, object]:
    prepared = validate_result_v1(grade_prepare_result, phase="grade-prepare")
    return {
        "schema_version": (
            "corpus-r6-construction-allocation-grade-execute-request/v1"
        ),
        "manifest_identity": prepared["manifest_identity"],
    }


def grade_reopen_request_v1(*, grade_result: Mapping[str, object]) -> dict[str, object]:
    graded = validate_result_v1(grade_result, phase="grade")
    return {
        "schema_version": (
            "corpus-r6-construction-allocation-grade-reopen-request/v1"
        ),
        "terminal_envelope": graded["terminal_envelope"],
        "code_sha": CODE_SHA,
        "immutable_image": IMMUTABLE_IMAGE,
    }


def _is_not_found(result: CommandResult) -> bool:
    message = (result.stdout + b"\n" + result.stderr).decode("utf-8", "replace").lower()
    return result.returncode != 0 and any(
        token in message
        for token in (
            "not found",
            "no urls matched",
            "status=[404]",
            "httperror 404",
            "notfoundexception: 404",
        )
    )


class Finisher:
    def __init__(
        self,
        *,
        run_dir: Path,
        runner: CommandRunner,
        poll_interval_seconds: int,
        max_polls: int,
    ) -> None:
        self.run_dir = _validated_run_dir(run_dir)
        self.runner = runner
        if not 1 <= poll_interval_seconds <= 60 or not 1 <= max_polls <= 2_000:
            _fail("poll bounds differ")
        self.poll_interval_seconds = poll_interval_seconds
        self.max_polls = max_polls
        if (
            not CLEAN_ROOT.is_dir()
            or not IMMUTABLE_LAUNCHER.is_file()
            or IMMUTABLE_LAUNCHER.is_symlink()
        ):
            _fail("clean d5946133 launcher is unavailable")

    def _phase_dir(self, phase: str) -> Path:
        return self.run_dir / phase

    def _request_path(self, phase: str) -> Path:
        return self._phase_dir(phase) / "request.json"

    def _result_path(self, phase: str) -> Path:
        return self._phase_dir(phase) / "result.json"

    def _load_validated_result(self, phase: str) -> dict[str, object]:
        return validate_result_v1(
            _read_canonical(self._result_path(phase), label=f"{phase} result"),
            phase=phase,
        )

    def _describe_execution(self, name: str) -> tuple[dict[str, object], bytes]:
        return _json_command(
            self.runner,
            (
                "gcloud",
                "run",
                "jobs",
                "executions",
                "describe",
                name,
                "--project",
                PROJECT,
                "--region",
                REGION,
                "--format=json",
            ),
            label=f"execution describe {name}",
        )

    def _poll_source(self) -> dict[str, object]:
        directory = self.run_dir / "source-54"
        for _ in range(self.max_polls):
            execution, raw = self._describe_execution(SOURCE_EXECUTION_NAME)
            validated = validate_source_execution_v1(execution)
            _replace_local(directory / "provider-latest.json", raw)
            condition = _condition_status(validated)
            if condition == "True":
                if (
                    _count(validated, "succeededCount") != SOURCE_TASK_COUNT
                    or _count(validated, "failedCount") != 0
                    or _count(validated, "cancelledCount") != 0
                    or _count(validated, "runningCount") != 0
                    or type(_mapping(validated["status"], label="source status").get(
                        "completionTime"
                    ))
                    is not str
                ):
                    _publish_local_once(directory / "provider-invalid.json", raw)
                    _fail("source execution terminal counts differ")
                _publish_local_once(directory / "provider-terminal.json", raw)
                return validated
            if (
                condition == "False"
                or _count(validated, "failedCount")
                or _count(validated, "cancelledCount")
            ):
                _publish_local_once(directory / "provider-invalid.json", raw)
                _fail("source execution failed or was cancelled")
            time.sleep(self.poll_interval_seconds)
        _fail("source execution polling exhausted")

    def _poll_phase(
        self,
        *,
        phase: str,
        launch: Mapping[str, object],
        request: Mapping[str, object],
        request_raw: bytes,
    ) -> dict[str, object]:
        directory = self._phase_dir(phase)
        launch_execution = _mapping(launch["execution"], label="launch execution")
        name = str(launch_execution["name"])
        uid = str(launch_execution["uid"])
        for _ in range(self.max_polls):
            execution, raw = self._describe_execution(name)
            validated = validate_phase_execution_v1(
                execution,
                phase=phase,
                execution_name=name,
                execution_uid=uid,
                request=request,
                request_raw=request_raw,
                launch_receipt=launch,
            )
            _replace_local(directory / "provider-latest.json", raw)
            condition = _condition_status(validated)
            if condition == "True":
                status = _mapping(validated["status"], label="phase status")
                if (
                    _count(validated, "succeededCount") != 1
                    or _count(validated, "failedCount") != 0
                    or _count(validated, "cancelledCount") != 0
                    or _count(validated, "runningCount") != 0
                    or type(status.get("completionTime")) is not str
                    or not str(status["completionTime"]).endswith("Z")
                ):
                    _publish_local_once(directory / "provider-invalid.json", raw)
                    _fail(f"{phase} terminal counts differ")
                _publish_local_once(directory / "provider-terminal.json", raw)
                return validated
            if (
                condition == "False"
                or _count(validated, "failedCount")
                or _count(validated, "cancelledCount")
            ):
                _publish_local_once(directory / "provider-invalid.json", raw)
                _fail(f"{phase} failed or was cancelled")
            time.sleep(self.poll_interval_seconds)
        _fail(f"{phase} polling exhausted")

    def _read_stdout_array(
        self,
        *,
        phase: str,
        launch: Mapping[str, object],
    ) -> dict[str, object]:
        directory = self._phase_dir(phase)
        execution = _mapping(launch["execution"], label="launch execution")
        name = str(execution["name"])
        log_filter = (
            'resource.type="cloud_run_job" AND '
            f'labels."run.googleapis.com/execution_name"="{name}" AND '
            f'logName="projects/{PROJECT}/logs/run.googleapis.com%2Fstdout" AND '
            "textPayload:*"
        )
        command = (
            "gcloud",
            "logging",
            "read",
            log_filter,
            "--project",
            PROJECT,
            "--limit=100",
            "--order=asc",
            "--format=json",
        )
        for _ in range(min(self.max_polls, 20)):
            completed = self.runner.run(command)
            if completed.returncode != 0:
                _fail(f"{phase} exact stdout log read failed")
            try:
                logs = json.loads(completed.stdout)
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise FinisherError(f"{phase} stdout logs are not JSON") from exc
            logs_raw = canonical_bytes(logs)
            _replace_local(directory / "stdout-logs-latest.json", logs_raw)
            if logs == []:
                time.sleep(self.poll_interval_seconds)
                continue
            result = result_from_exact_stdout_logs_v1(logs, phase=phase)
            _publish_local_once(directory / "stdout-logs.json", logs_raw)
            _publish_local_once(self._result_path(phase), canonical_bytes(result))
            return result
        _fail(f"{phase} stdout receipt polling exhausted")

    def _assert_grade_manifest_absent(self) -> None:
        directory = self._phase_dir("grade-prepare")
        result = self.runner.run(
            (
                "gcloud",
                "storage",
                "objects",
                "describe",
                GRADE_MANIFEST_URI,
                "--project",
                PROJECT,
                "--format=json(name,generation,size,timeCreated)",
            )
        )
        if result.returncode == 0:
            try:
                value = json.loads(result.stdout)
            except (UnicodeError, json.JSONDecodeError):
                value = {"raw_sha256": sha256(result.stdout).hexdigest()}
            _publish_local_once(
                directory / "grade-manifest-collision.json",
                canonical_bytes(value),
            )
            _fail("deterministic grade-manifest name already exists")
        if not _is_not_found(result):
            _fail("grade-manifest exact-name absence check was inconclusive")
        absence = {
            "schema_version": (
                "corpus-r6-construction-allocation-grade-manifest-absence/v1"
            ),
            "uri": GRADE_MANIFEST_URI,
            "exact_known_name_only": True,
            "prefix_listing_used": False,
            "absent": True,
            "complete": True,
        }
        _publish_local_once(
            directory / "grade-manifest-absence.json", canonical_bytes(absence)
        )

    def _materialize_request(self, phase: str) -> tuple[dict[str, object], bytes, Path]:
        if phase == "collect":
            request = source_request_v1()
        elif phase == "reopen":
            collect = self._load_validated_result("collect")
            validate_selection_envelope_v1(collect["terminal_envelope"])
            request = source_request_v1()
        elif phase == "grade-prepare":
            collect = self._load_validated_result("collect")
            reopen = self._load_validated_result("reopen")
            if reopen["terminal_envelope"] != collect["terminal_envelope"]:
                _fail("independent selection reopen differs from collect")
            provider = _read_canonical(
                self._phase_dir("reopen") / "provider-terminal.json",
                label="reopen terminal provider receipt",
            )
            status = _mapping(provider.get("status"), label="reopen provider status")
            frozen_at = status.get("completionTime")
            if type(frozen_at) is not str:
                _fail("reopen provider completionTime is absent")
            request = grade_prepare_request_v1(
                reopen_result=reopen, frozen_at=frozen_at
            )
        elif phase == "grade":
            request = grade_request_v1(
                grade_prepare_result=self._load_validated_result("grade-prepare")
            )
        else:
            request = grade_reopen_request_v1(
                grade_result=self._load_validated_result("grade")
            )
        raw = canonical_bytes(request)
        path = self._request_path(phase)
        _publish_local_once(path, raw)
        return request, raw, path

    def _launch_or_resume(
        self,
        *,
        phase: str,
        request: Mapping[str, object],
        request_raw: bytes,
        request_path: Path,
    ) -> dict[str, object]:
        directory = self._phase_dir(phase)
        launch_path = directory / "launch.json"
        if launch_path.exists():
            launch = validate_launch_receipt_v1(
                _read_canonical(launch_path, label=f"{phase} launch receipt"),
                phase=phase,
                request=request,
                request_raw=request_raw,
            )
            _publish_local_once(
                directory / "transport-request.json",
                canonical_bytes(
                    transport_request_v1(
                        phase=phase, request=request, launch_receipt=launch
                    )
                ),
            )
            return launch
        intent_path = directory / "launch-intent.json"
        intent = {
            "schema_version": (
                "corpus-r6-construction-allocation-finisher-launch-intent/v1"
            ),
            "phase": phase,
            "code_sha": CODE_SHA,
            "build_id": BUILD_ID,
            "immutable_image": IMMUTABLE_IMAGE,
            "request_sha256": sha256(request_raw).hexdigest(),
            "source_execution_name": (
                SOURCE_EXECUTION_NAME if phase in {"collect", "reopen"} else None
            ),
            "automatic_relaunch": False,
            "complete": True,
        }
        created = not intent_path.exists()
        _publish_local_once(intent_path, canonical_bytes(intent))
        if not created:
            _fail(f"{phase} has an ambiguous launch intent without a receipt")
        environment = dict(os.environ)
        if phase in {"collect", "reopen"}:
            environment[TASK_EXECUTION_ENV] = SOURCE_EXECUTION_NAME
        argv = (
            str(IMMUTABLE_LAUNCHER),
            phase,
            IMMUTABLE_IMAGE,
            CODE_SHA,
            BUILD_ID,
            str(request_path),
        )
        completed = self.runner.run(argv, cwd=CLEAN_ROOT, env=environment)
        _publish_local_once(directory / "launcher-stdout.raw", completed.stdout)
        _publish_local_once(directory / "launcher-stderr.raw", completed.stderr)
        if completed.returncode != 0:
            _fail(f"{phase} launcher failed or is ambiguous; do not relaunch")
        launch = validate_launch_receipt_v1(
            _parse_launcher_json(
                completed.stdout, label=f"{phase} launcher stdout"
            ),
            phase=phase,
            request=request,
            request_raw=request_raw,
        )
        _publish_local_once(launch_path, canonical_bytes(launch))
        _publish_local_once(
            directory / "transport-request.json",
            canonical_bytes(
                transport_request_v1(
                    phase=phase, request=request, launch_receipt=launch
                )
            ),
        )
        return launch

    def _reopen_local_completed_phase(
        self,
        *,
        phase: str,
        request: Mapping[str, object],
        request_raw: bytes,
    ) -> dict[str, object]:
        directory = self._phase_dir(phase)
        launch = validate_launch_receipt_v1(
            _read_canonical(directory / "launch.json", label=f"{phase} launch"),
            phase=phase,
            request=request,
            request_raw=request_raw,
        )
        launch_execution = _mapping(launch["execution"], label="launch execution")
        provider = validate_phase_execution_v1(
            _read_canonical(
                directory / "provider-terminal.json",
                label=f"{phase} terminal provider receipt",
            ),
            phase=phase,
            execution_name=str(launch_execution["name"]),
            execution_uid=str(launch_execution["uid"]),
            request=request,
            request_raw=request_raw,
            launch_receipt=launch,
        )
        if (
            _condition_status(provider) != "True"
            or _count(provider, "succeededCount") != 1
            or _count(provider, "failedCount") != 0
            or _count(provider, "cancelledCount") != 0
            or _count(provider, "runningCount") != 0
        ):
            _fail(f"persisted {phase} provider terminal differs")
        logs = _read_canonical_value(
            directory / "stdout-logs.json", label=f"{phase} stdout logs"
        )
        from_logs = result_from_exact_stdout_logs_v1(logs, phase=phase)
        result = self._load_validated_result(phase)
        if from_logs != result:
            _fail(f"persisted {phase} stdout/result differ")
        return result

    def run_phase(self, phase: str) -> dict[str, object]:
        if phase not in PHASES:
            _fail("unknown finisher phase")
        if phase == "collect":
            source_terminal = self.run_dir / "source-54" / "provider-terminal.json"
            if self._result_path(phase).exists():
                source = validate_source_execution_v1(
                    _read_canonical(
                        source_terminal, label="source terminal provider receipt"
                    )
                )
                if (
                    _condition_status(source) != "True"
                    or _count(source, "succeededCount") != SOURCE_TASK_COUNT
                    or _count(source, "failedCount") != 0
                    or _count(source, "cancelledCount") != 0
                    or _count(source, "runningCount") != 0
                ):
                    _fail("persisted source terminal differs")
            else:
                self._poll_source()
        request, request_raw, request_path = self._materialize_request(phase)
        if self._result_path(phase).exists():
            return self._reopen_local_completed_phase(
                phase=phase, request=request, request_raw=request_raw
            )
        if phase == "grade-prepare" and not (
            self._phase_dir(phase) / "launch.json"
        ).exists():
            self._assert_grade_manifest_absent()
        launch = self._launch_or_resume(
            phase=phase,
            request=request,
            request_raw=request_raw,
            request_path=request_path,
        )
        self._poll_phase(
            phase=phase,
            launch=launch,
            request=request,
            request_raw=request_raw,
        )
        return self._read_stdout_array(phase=phase, launch=launch)

    def finish(self) -> dict[str, object]:
        results: dict[str, object] = {}
        for phase in PHASES:
            results[phase] = self.run_phase(phase)
        final = {
            "schema_version": (
                "corpus-r6-construction-allocation-d5946133-finisher/v1"
            ),
            "source_execution": {
                "name": SOURCE_EXECUTION_NAME,
                "uid": SOURCE_EXECUTION_UID,
                "task_count": SOURCE_TASK_COUNT,
            },
            "grade_run_id": GRADE_RUN_ID,
            "grade_id": GRADE_ID,
            "grade_manifest_uri": GRADE_MANIFEST_URI,
            "phase_result_sha256": {
                phase: canonical_sha256(results[phase]) for phase in PHASES
            },
            "historical_outcome_lease_release_required": True,
            "historical_outcome_lease_released": False,
            "complete": True,
        }
        _publish_local_once(self.run_dir / "finisher-terminal.json", canonical_bytes(final))
        return final


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=(*PHASES, "finish"), help="one exact phase or full chain"
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--poll-interval-seconds", type=int, default=30)
    parser.add_argument("--max-polls", type=int, default=720)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.execute or args.confirmation != CONFIRMATION:
        _fail(
            "finisher is default-off; require --execute --confirmation "
            + CONFIRMATION
        )
    run_dir = _validated_run_dir(args.run_dir)
    lock_path = run_dir / "finisher.lock"
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise FinisherError("another finisher owns the local run lock") from exc
        finisher = Finisher(
            run_dir=run_dir,
            runner=CommandRunner(),
            poll_interval_seconds=args.poll_interval_seconds,
            max_polls=args.max_polls,
        )
        result = (
            finisher.finish()
            if args.action == "finish"
            else finisher.run_phase(args.action)
        )
    sys.stdout.buffer.write(canonical_bytes(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FinisherError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


__all__ = [
    "BUILD_ID",
    "CODE_SHA",
    "COLLECT_SCHEMA",
    "CommandResult",
    "Finisher",
    "FinisherError",
    "GRADE_ID",
    "GRADE_MANIFEST_URI",
    "GRADE_OUTPUT_PREFIX",
    "GRADE_RUN_ID",
    "HISTORICAL_OUTCOME_LEASE_IDENTITY",
    "IMMUTABLE_IMAGE",
    "OUTCOME_COMPLETION_IDENTITY",
    "OUTCOME_SNAPSHOT_IDENTITY",
    "SOURCE_EXECUTION_NAME",
    "SOURCE_EXECUTION_UID",
    "SOURCE_MANIFEST_IDENTITY",
    "canonical_bytes",
    "canonical_sha256",
    "grade_prepare_request_v1",
    "grade_reopen_request_v1",
    "grade_request_v1",
    "result_from_exact_stdout_logs_v1",
    "source_request_v1",
    "transport_request_v1",
    "validate_collect_result_v1",
    "validate_grade_envelope_v1",
    "validate_launch_receipt_v1",
    "validate_phase_execution_v1",
    "validate_result_v1",
    "validate_selection_envelope_v1",
    "validate_source_execution_v1",
]
