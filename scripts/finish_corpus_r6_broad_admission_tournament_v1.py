#!/usr/bin/env python3
"""Crash-closed host finisher for the R6 broad-admission tournament.

This driver contains no scientific implementation.  It accepts the exact
build receipt emitted by ``cloud_corpus_r6_broad_admission_tournament_v1.sh
build``, constructs the one frozen prepare request, and then invokes that
reviewed launcher through this fixed chain::

    install -> prepare/result -> task0/result -> task[54] ->
    collect/result -> reopen/result -> grade/result -> grade-reopen/result

Every provider observation names one exact execution.  No job, execution, or
object prefix is ever listed.  Local launch intent is written before a
mutating call; an intent without either the launch receipt or an explicitly
supplied exact recovery execution fails closed instead of relaunching.

The default invocation is inert.  Cloud access requires both ``--execute``
and the literal confirmation exposed by ``--help``.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
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


ROOT: Final = Path(__file__).resolve().parents[1]
LAUNCHER: Final = ROOT / "scripts" / "cloud_corpus_r6_broad_admission_tournament_v1.sh"
LOCAL_STATE_ROOT: Final = ROOT / ".tmp"
DEFAULT_RUN_DIR: Final = LOCAL_STATE_ROOT / "corpus-r6-broad-admission-finisher-v1"

PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
JOB: Final = "atlas-cbc-32g-full-2023-w8-v1"
JOB_UID: Final = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
SOURCE_REPOSITORY: Final = "https://github.com/espechtsoftware/nfl-predictions.git"
CONFIRMATION: Final = "I_UNDERSTAND_R6_BROAD_ADMISSION_FINISHER_V1"

OUTPUT_ROOT: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-broad-admission/"
)
FROZEN_COMBINED_TERMINAL_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-combined-population-all-block/"
        "20260829-score-sprint-170b7b4e-v2/full54/full-54/"
        "descriptive-terminal-v2.json"
    ),
    "generation": "1787999967997744",
    "sha256": "f6f2679f44032246508ac5905b51d53d4a3f1f178d15103a203d488017a796d1",
    "bytes": 35_870,
}
FROZEN_FRONTIER_MANIFEST_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-combined-frontier-reportfolio/"
        "20260829-score-sprint-28db339e-v1/full54/manifest.json"
    ),
    "generation": "1788029467812121",
    "sha256": "206a4dde7203bbd62b1ff6c6beee10ece26580c51650732132a0a7f8df08f114",
    "bytes": 55_096,
}
OUTCOME_AUTHORITY_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-catalog-wide-realized/"
        "20260829-score-sprint-c9f12ed7-catalog-outcomes-v1/completion.json"
    ),
    "generation": "1787987567275104",
    "sha256": "15852361756ef0fe76d3a299617ebc2c2531e6821a73f04c8f862bf7229f4df3",
    "bytes": 2_521,
}

ONE_TASK_PHASES: Final = (
    "prepare",
    "task0",
    "collect",
    "reopen",
    "grade",
    "grade-reopen",
)
EXECUTION_PHASES: Final = ("prepare", "task0", "task", "collect", "reopen", "grade", "grade-reopen")

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_EXECUTION = re.compile(re.escape(JOB) + r"-[a-z0-9]{5}\Z")
_IMAGE = re.compile(
    r"us-central1-docker\.pkg\.dev/nfl-predictions-503414/"
    r"nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}\Z"
)


class BroadAdmissionFinisherError(RuntimeError):
    """One immutable input, provider fact, or local resume fact differed."""


def _fail(message: str) -> None:
    raise BroadAdmissionFinisherError(message)


def canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
            + b"\n"
        )
    except (TypeError, ValueError, UnicodeError) as exc:
        raise BroadAdmissionFinisherError("canonical JSON differs") from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) not in (
        {"uri", "generation", "sha256", "bytes"},
        {"uri", "generation", "sha256", "bytes", "create_once"},
    ):
        _fail(f"{label} fields differ")
    if (
        type(item.get("uri")) is not str
        or not str(item["uri"]).startswith("gs://")
        or type(item.get("generation")) not in {str, int}
        or not str(item["generation"]).isdigit()
        or int(str(item["generation"])) <= 0
        or type(item.get("sha256")) is not str
        or _SHA.fullmatch(str(item["sha256"])) is None
        or type(item.get("bytes")) is not int
        or int(item["bytes"]) <= 0
        or ("create_once" in item and item["create_once"] is not True)
    ):
        _fail(f"{label} differs")
    result: dict[str, object] = {
        "uri": item["uri"],
        "generation": str(item["generation"]),
        "sha256": item["sha256"],
        "bytes": item["bytes"],
    }
    if item.get("create_once") is True:
        result["create_once"] = True
    return result


def _parse_canonical(raw: bytes, *, label: str) -> dict[str, object]:
    if not raw or raw.endswith(b"\n\n"):
        _fail(f"{label} bytes differ")
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BroadAdmissionFinisherError(f"{label} is not JSON") from exc
    item = _mapping(value, label=label)
    if raw not in {canonical_bytes(item), canonical_bytes(item)[:-1]}:
        _fail(f"{label} must be canonical JSON")
    return item


def _parse_json(raw: bytes, *, label: str) -> dict[str, object]:
    if not raw:
        _fail(f"{label} bytes are empty")
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BroadAdmissionFinisherError(f"{label} is not JSON") from exc
    return _mapping(value, label=label)


def _read_canonical(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        _fail(f"{label} must be one absolute unaliased regular file")
    return _parse_canonical(path.read_bytes(), label=label)


def _read_json(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        _fail(f"{label} must be one absolute unaliased regular file")
    return _parse_json(path.read_bytes(), label=label)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
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


def _replace(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    if temporary.exists() or temporary.is_symlink():
        _fail(f"temporary local state exists: {temporary}")
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


def _validated_run_dir(path: Path) -> Path:
    if not path.is_absolute():
        _fail("run directory must be absolute")
    base = LOCAL_STATE_ROOT.resolve()
    retained = path.resolve(strict=False)
    if retained == base or base not in retained.parents:
        _fail("run directory must remain below repository .tmp")
    cursor = retained
    while cursor != base:
        if cursor.exists() and cursor.is_symlink():
            _fail("run directory may not traverse a symlink")
        cursor = cursor.parent
    retained.mkdir(parents=True, exist_ok=True, mode=0o700)
    return retained


class CommandResult:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class CommandRunner:
    """Injectable argv-only process boundary."""

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


def validate_build_receipt_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="broad-admission build receipt")
    expected = {
        "schema_version",
        "code_sha",
        "cloud_build_id",
        "build_image_tag",
        "provider_resolved_image",
        "image_digest",
        "source_repository",
        "runtime_build_attestation_identity",
        "provider_requested_and_resolved_git_source_exact",
        "outcome_artifacts_read_by_build_steps",
        "outcome_artifacts_in_runtime_image_context",
        "complete",
    }
    code_sha = item.get("code_sha")
    build_id = item.get("cloud_build_id")
    image = item.get("provider_resolved_image")
    digest = item.get("image_digest")
    expected_tag = (
        "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
        f"nfl-dfs:broad-admission-{code_sha}"
    )
    if (
        set(item) != expected
        or item.get("schema_version") != "corpus-r6-broad-admission-cloud-build/v1"
        or type(code_sha) is not str
        or _COMMIT.fullmatch(code_sha) is None
        or type(build_id) is not str
        or _UUID.fullmatch(build_id) is None
        or item.get("build_image_tag") != expected_tag
        or type(image) is not str
        or _IMAGE.fullmatch(image) is None
        or type(digest) is not str
        or not image.endswith("@" + digest)
        or item.get("source_repository") != SOURCE_REPOSITORY
        or item.get("provider_requested_and_resolved_git_source_exact") is not True
        or item.get("outcome_artifacts_read_by_build_steps") is not False
        or item.get("outcome_artifacts_in_runtime_image_context") is not False
        or item.get("complete") is not True
    ):
        _fail("broad-admission build receipt differs")
    _identity(
        item.get("runtime_build_attestation_identity"),
        label="runtime build attestation",
    )
    return item


def prepare_request_v1(
    *, build_receipt: Mapping[str, object], output_prefix: str
) -> dict[str, object]:
    build = validate_build_receipt_v1(build_receipt)
    if (
        type(output_prefix) is not str
        or not output_prefix.startswith(OUTPUT_ROOT)
        or output_prefix == OUTPUT_ROOT
        or not output_prefix.endswith("/")
        or ".." in output_prefix
        or "//" in output_prefix.removeprefix("gs://")
    ):
        _fail("broad-admission output prefix differs")
    return {
        "code_sha": build["code_sha"],
        "combined_terminal_identity": dict(FROZEN_COMBINED_TERMINAL_IDENTITY),
        "frontier_manifest_identity": dict(FROZEN_FRONTIER_MANIFEST_IDENTITY),
        "immutable_image": build["provider_resolved_image"],
        "output_prefix": output_prefix,
        "runtime_build_attestation_identity": _identity(
            build["runtime_build_attestation_identity"],
            label="runtime build attestation",
        ),
    }


def _phase_bound_identity(
    phase: str, request: Mapping[str, object]
) -> dict[str, object]:
    key = {
        "prepare": "combined_terminal_identity",
        "task0": "manifest_identity",
        "task": "manifest_identity",
        "collect": "manifest_identity",
        "reopen": "terminal_identity",
        "grade": "terminal_identity",
        "grade-reopen": "grade_terminal_identity",
    }[phase]
    return _identity(request[key], label=f"{phase} bound identity")


def _expected_request_sha(
    phase: str, request: Mapping[str, object], *, task_execution: str | None
) -> str:
    effective: Mapping[str, object] = request
    if phase == "collect":
        if task_execution is None or _EXECUTION.fullmatch(task_execution) is None:
            _fail("collect task execution differs")
        effective = {
            "execution_id": task_execution,
            "manifest_identity": request["manifest_identity"],
        }
    return canonical_sha256(effective)


def validate_install_receipt_v1(
    value: object, *, build_receipt: Mapping[str, object]
) -> dict[str, object]:
    item = _mapping(value, label="install receipt")
    build = validate_build_receipt_v1(build_receipt)
    expected = {
        "schema_version",
        "code_sha",
        "cloud_build_id",
        "provider_resolved_image",
        "image_digest",
        "reused_job",
        "prior_terminal_execution",
        "install_only",
        "execution_launched",
        "outcomes_allowed",
        "complete",
    }
    reused = _mapping(item.get("reused_job"), label="installed reused job")
    if (
        set(item) != expected
        or item.get("schema_version") != "corpus-r6-broad-admission-cloud-install/v1"
        or item.get("code_sha") != build["code_sha"]
        or item.get("cloud_build_id") != build["cloud_build_id"]
        or item.get("provider_resolved_image") != build["provider_resolved_image"]
        or item.get("image_digest") != build["image_digest"]
        or set(reused) != {"name", "uid", "generation"}
        or reused.get("name") != JOB
        or reused.get("uid") != JOB_UID
        or type(reused.get("generation")) is not int
        or int(reused["generation"]) <= 0
        or item.get("install_only") is not True
        or item.get("execution_launched") is not False
        or item.get("outcomes_allowed") is not False
        or item.get("complete") is not True
    ):
        _fail("broad-admission install receipt differs")
    return item


def validate_launch_receipt_v1(
    value: object,
    *,
    phase: str,
    request: Mapping[str, object],
    build_receipt: Mapping[str, object],
    task0_result: Mapping[str, object] | None = None,
    task_execution: str | None = None,
) -> dict[str, object]:
    if phase not in EXECUTION_PHASES:
        _fail("launch phase differs")
    item = _mapping(value, label=f"{phase} launch receipt")
    build = validate_build_receipt_v1(build_receipt)
    expected = {
        "schema_version",
        "phase",
        "code_sha",
        "cloud_build_id",
        "provider_resolved_image",
        "image_digest",
        "reused_job",
        "execution",
        "bound_input_authority_identity",
        "source_task_execution",
        "task0_gate_result",
        "request_sha256",
        "outcomes_allowed",
        "task0_nonpublishing_smoke",
        "execution_provider_reopened",
        "complete",
    }
    execution = _mapping(item.get("execution"), label="launched execution")
    reused = _mapping(item.get("reused_job"), label="launch reused job")
    expected_tasks = 54 if phase == "task" else 1
    if (
        set(item) != expected
        or item.get("schema_version") != "corpus-r6-broad-admission-cloud-launch/v1"
        or item.get("phase") != phase
        or item.get("code_sha") != build["code_sha"]
        or item.get("cloud_build_id") != build["cloud_build_id"]
        or item.get("provider_resolved_image") != build["provider_resolved_image"]
        or item.get("image_digest") != build["image_digest"]
        or set(reused) != {"name", "uid", "generation"}
        or reused.get("name") != JOB
        or reused.get("uid") != JOB_UID
        or type(reused.get("generation")) is not int
        or int(reused["generation"]) <= 0
        or set(execution) != {"name", "uid", "task_count"}
        or _EXECUTION.fullmatch(str(execution.get("name", ""))) is None
        or _UUID.fullmatch(str(execution.get("uid", ""))) is None
        or type(execution.get("task_count")) is not int
        or execution.get("task_count") != expected_tasks
        or item.get("bound_input_authority_identity")
        != _phase_bound_identity(phase, request)
        or item.get("request_sha256")
        != _expected_request_sha(
            phase, request, task_execution=task_execution
        )
        or item.get("outcomes_allowed") is not (phase == "grade")
        or item.get("task0_nonpublishing_smoke") is not (phase == "task0")
        or item.get("execution_provider_reopened") is not True
        or item.get("complete") is not True
    ):
        _fail(f"{phase} launch receipt differs")
    if phase == "collect":
        source = _mapping(
            item.get("source_task_execution"), label="collect source execution"
        )
        if (
            set(source) != {"name", "uid", "task_count"}
            or source.get("name") != task_execution
            or _UUID.fullmatch(str(source.get("uid", ""))) is None
            or source.get("task_count") != 54
            or item.get("task0_gate_result") is not None
        ):
            _fail("collect source execution differs")
    elif phase == "task":
        if (
            item.get("source_task_execution") is not None
            or task0_result is None
            or item.get("task0_gate_result") != task0_result
        ):
            _fail("full task launch lacks the exact task0 gate")
    elif (
        item.get("source_task_execution") is not None
        or item.get("task0_gate_result") is not None
    ):
        _fail(f"{phase} launch carries an unexpected predecessor receipt")
    return item


def validate_result_receipt_v1(
    value: object,
    *,
    phase: str,
    execution_name: str,
    build_receipt: Mapping[str, object],
) -> dict[str, object]:
    if phase not in ONE_TASK_PHASES:
        _fail("result phase differs")
    item = _mapping(value, label=f"{phase} result receipt")
    build = validate_build_receipt_v1(build_receipt)
    expected = {
        "schema_version",
        "phase",
        "code_sha",
        "cloud_build_id",
        "provider_resolved_image",
        "execution",
        "operator_receipt",
        "exact_execution_stdout_only",
        "complete",
    }
    execution = _mapping(item.get("execution"), label="result execution")
    operator = _mapping(item.get("operator_receipt"), label="operator receipt")
    expected_uses_outcomes = phase in {"grade", "grade-reopen"}
    if (
        set(item) != expected
        or item.get("schema_version") != "corpus-r6-broad-admission-cloud-result/v1"
        or item.get("phase") != phase
        or item.get("code_sha") != build["code_sha"]
        or item.get("cloud_build_id") != build["cloud_build_id"]
        or item.get("provider_resolved_image") != build["provider_resolved_image"]
        or set(execution)
        != {
            "name",
            "uid",
            "task_count",
            "succeeded_count",
            "failed_count",
            "cancelled_count",
            "completion_time",
        }
        or execution.get("name") != execution_name
        or _UUID.fullmatch(str(execution.get("uid", ""))) is None
        or type(execution.get("task_count")) is not int
        or execution.get("task_count") != 1
        or type(execution.get("succeeded_count")) is not int
        or execution.get("succeeded_count") != 1
        or type(execution.get("failed_count")) is not int
        or execution.get("failed_count") != 0
        or type(execution.get("cancelled_count")) is not int
        or execution.get("cancelled_count") != 0
        or type(execution.get("completion_time")) is not str
        or set(operator)
        != {
            "command",
            "complete",
            "result",
            "schema_version",
            "task0_nonpublishing_smoke",
            "uses_realized_outcomes",
        }
        or operator.get("schema_version")
        != "corpus-r6-broad-admission-cli-receipt/v1"
        or operator.get("command") != ("task" if phase == "task0" else phase)
        or operator.get("task0_nonpublishing_smoke") is not (phase == "task0")
        or operator.get("uses_realized_outcomes") is not expected_uses_outcomes
        or operator.get("complete") is not True
        or item.get("exact_execution_stdout_only") is not True
        or item.get("complete") is not True
    ):
        _fail(f"{phase} result receipt differs")
    result = _mapping(operator.get("result"), label=f"{phase} operator result")
    schemas = {
        "prepare": "corpus-r6-broad-admission-prepare-result/v1",
        "task0": "corpus-r6-broad-admission-task0-smoke/v1",
        "collect": "corpus-r6-broad-admission-collect-result/v1",
        "reopen": "corpus-r6-broad-admission-reopen-result/v1",
        "grade": "corpus-r6-broad-admission-grade-result/v1",
        "grade-reopen": "corpus-r6-broad-admission-grade-reopen-result/v1",
    }
    result_fields = {
        "prepare": {
            "all_nonpublication_authorities_validated_before_first_write",
            "build_id",
            "complete",
            "deployment_mutation_performed",
            "execution_launched",
            "manifest_identity",
            "manifest_sha256",
            "prepare_result_sha256",
            "schema_version",
            "task_count",
            "uses_realized_outcomes",
        },
        "task0": {
            "complete",
            "manifest_identity",
            "package_sha256",
            "publication_performed",
            "schema_version",
            "slate_id",
            "smoke_result_sha256",
            "source_ordinal",
            "task_result_sha256",
            "union_lineups_sha256",
            "uses_realized_outcomes",
        },
        "collect": {
            "collect_result_sha256",
            "complete",
            "root_published_last",
            "schema_version",
            "task_count",
            "terminal_identity",
            "terminal_sha256",
            "uses_realized_outcomes",
        },
        "reopen": {
            "all_packages_independently_recomputed",
            "all_tasks_and_parents_generation_exact_reopened",
            "catalog_reread",
            "complete",
            "outcome_reread",
            "package_lattice_sha256",
            "reopen_result_sha256",
            "schema_version",
            "task_count",
            "terminal_identity",
            "uses_realized_outcomes",
        },
        "grade": {
            "complete",
            "descriptive_only",
            "grade_result_sha256",
            "grade_root_published_last",
            "grade_terminal_identity",
            "grade_terminal_sha256",
            "program_grade_sha256",
            "schema_version",
        },
        "grade-reopen": {
            "catalog_reread",
            "complete",
            "grade_reopen_result_sha256",
            "grade_terminal_identity",
            "historical_outcome_lease_reread",
            "outcome_snapshot_reread",
            "persisted_derived_scores_replayed",
            "program_grade_independently_recomputed",
            "program_grade_sha256",
            "schema_version",
            "score_free_lattice_and_parents_replayed",
            "uses_realized_outcomes",
        },
    }
    if (
        set(result) != result_fields[phase]
        or result.get("schema_version") != schemas[phase]
        or result.get("complete") is not True
    ):
        _fail(f"{phase} operator result differs")
    identity_fields = {
        "prepare": "manifest_identity",
        "task0": "manifest_identity",
        "collect": "terminal_identity",
        "reopen": "terminal_identity",
        "grade": "grade_terminal_identity",
        "grade-reopen": "grade_terminal_identity",
    }
    _identity(result.get(identity_fields[phase]), label=f"{phase} result identity")
    for key, value in result.items():
        if key.endswith("_sha256") and (
            type(value) is not str or _SHA.fullmatch(value) is None
        ):
            _fail(f"{phase} result hash differs")
    if phase == "prepare" and (
        result.get("task_count") != 54
        or result.get("build_id") != build["cloud_build_id"]
        or result.get("all_nonpublication_authorities_validated_before_first_write")
        is not True
        or result.get("execution_launched") is not False
        or result.get("deployment_mutation_performed") is not False
        or result.get("uses_realized_outcomes") is not False
    ):
        _fail("prepare result differs")
    if phase == "task0" and (
        type(result.get("source_ordinal")) is not int
        or result.get("source_ordinal") != 0
        or type(result.get("slate_id")) is not str
        or re.fullmatch(r"20[0-9]{2}-w(?:0[1-9]|1[0-8])", result["slate_id"])
        is None
        or result.get("publication_performed") is not False
        or result.get("uses_realized_outcomes") is not False
    ):
        _fail("task0 mechanical gate differs")
    if phase == "collect" and (
        result.get("task_count") != 54
        or result.get("root_published_last") is not True
        or result.get("uses_realized_outcomes") is not False
    ):
        _fail("collect terminal differs")
    if phase == "reopen" and (
        result.get("task_count") != 54
        or result.get("all_tasks_and_parents_generation_exact_reopened") is not True
        or result.get("all_packages_independently_recomputed") is not True
        or result.get("catalog_reread") is not False
        or result.get("outcome_reread") is not False
        or result.get("uses_realized_outcomes") is not False
    ):
        _fail("score-free reopen differs")
    if phase == "grade" and (
        result.get("grade_root_published_last") is not True
        or result.get("descriptive_only") is not True
    ):
        _fail("grade terminal differs")
    if phase == "grade-reopen" and (
        result.get("score_free_lattice_and_parents_replayed") is not True
        or result.get("persisted_derived_scores_replayed") is not True
        or result.get("program_grade_independently_recomputed") is not True
        or result.get("catalog_reread") is not False
        or result.get("outcome_snapshot_reread") is not False
        or result.get("historical_outcome_lease_reread") is not False
        or result.get("uses_realized_outcomes") is not True
    ):
        _fail("grade independent reopen differs")
    return item


def _result_body(receipt: Mapping[str, object]) -> dict[str, object]:
    return _mapping(
        _mapping(receipt["operator_receipt"], label="operator receipt")["result"],
        label="operator result",
    )


def _timestamp(value: object, *, label: str) -> datetime:
    if type(value) is not str:
        _fail(f"{label} timestamp differs")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BroadAdmissionFinisherError(f"{label} timestamp differs") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        _fail(f"{label} timestamp is not UTC")
    return parsed


class BroadAdmissionFinisher:
    def __init__(
        self,
        *,
        run_dir: Path,
        build_receipt: Mapping[str, object],
        output_prefix: str,
        runner: CommandRunner,
        already_installed: bool,
        resume_executions: Mapping[str, str],
        poll_interval_seconds: int,
        max_polls: int,
    ) -> None:
        self.run_dir = _validated_run_dir(run_dir)
        self.build = validate_build_receipt_v1(build_receipt)
        self.prepare_request = prepare_request_v1(
            build_receipt=self.build, output_prefix=output_prefix
        )
        self.runner = runner
        self.already_installed = already_installed
        if not 1 <= poll_interval_seconds <= 60 or not 1 <= max_polls <= 2_000:
            _fail("poll bounds differ")
        self.poll_interval_seconds = poll_interval_seconds
        self.max_polls = max_polls
        self.resume_executions: dict[str, str] = {}
        for phase, name in resume_executions.items():
            if phase not in EXECUTION_PHASES or _EXECUTION.fullmatch(name) is None:
                _fail("resume execution name differs")
            self.resume_executions[phase] = name
        if not LAUNCHER.is_file() or LAUNCHER.is_symlink():
            _fail("broad-admission launcher is absent or aliased")
        inputs = {
            "schema_version": "corpus-r6-broad-admission-finisher-input/v1",
            "build_receipt": self.build,
            "prepare_request": self.prepare_request,
            "automatic_relaunch": False,
            "execution_listing_allowed": False,
            "object_listing_allowed": False,
            "complete": True,
        }
        _publish_once(self.run_dir / "input.json", canonical_bytes(inputs))

    @property
    def code_sha(self) -> str:
        return str(self.build["code_sha"])

    @property
    def build_id(self) -> str:
        return str(self.build["cloud_build_id"])

    @property
    def image(self) -> str:
        return str(self.build["provider_resolved_image"])

    def _phase_dir(self, phase: str) -> Path:
        return self.run_dir / phase

    def _request(self, phase: str, value: Mapping[str, object]) -> Path:
        path = self._phase_dir(phase) / "request.json"
        _publish_once(path, canonical_bytes(value))
        return path

    def _launcher(
        self,
        args: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        return self.runner.run((str(LAUNCHER), *args), cwd=ROOT, env=env)

    def ensure_installed(self) -> None:
        directory = self._phase_dir("install")
        receipt_path = directory / "receipt.json"
        if receipt_path.exists():
            validate_install_receipt_v1(
                _read_canonical(receipt_path, label="persisted install receipt"),
                build_receipt=self.build,
            )
            return
        if self.already_installed:
            reconciliation = {
                "schema_version": "corpus-r6-broad-admission-external-install/v1",
                "code_sha": self.code_sha,
                "build_id": self.build_id,
                "immutable_image": self.image,
                "caller_asserted_installed": True,
                "next_launcher_must_revalidate_exact_job": True,
                "install_relaunched": False,
                "complete": True,
            }
            _publish_once(directory / "external-install.json", canonical_bytes(reconciliation))
            return
        intent = {
            "schema_version": "corpus-r6-broad-admission-finisher-launch-intent/v1",
            "phase": "install",
            "code_sha": self.code_sha,
            "build_id": self.build_id,
            "immutable_image": self.image,
            "automatic_relaunch": False,
            "complete": True,
        }
        intent_path = directory / "launch-intent.json"
        if intent_path.exists():
            _publish_once(intent_path, canonical_bytes(intent))
            _fail("install has an ambiguous launch intent; use --already-installed only after exact reconciliation")
        _publish_once(intent_path, canonical_bytes(intent))
        completed = self._launcher(("install", self.image, self.code_sha, self.build_id))
        _publish_once(directory / "launcher-stdout.raw", completed.stdout)
        _publish_once(directory / "launcher-stderr.raw", completed.stderr)
        if completed.returncode != 0:
            _fail("install launcher failed or is ambiguous; do not relaunch")
        receipt = validate_install_receipt_v1(
            _parse_json(completed.stdout, label="install launcher stdout"),
            build_receipt=self.build,
        )
        _publish_once(receipt_path, canonical_bytes(receipt))

    def _launch_or_resume(
        self,
        *,
        phase: str,
        request: Mapping[str, object],
        request_path: Path,
        task0_result: Mapping[str, object] | None = None,
        task_execution: str | None = None,
    ) -> str:
        directory = self._phase_dir(phase)
        launch_path = directory / "launch.json"
        external_path = directory / "external-execution.json"
        if launch_path.exists():
            launch = validate_launch_receipt_v1(
                _read_canonical(launch_path, label=f"persisted {phase} launch"),
                phase=phase,
                request=request,
                build_receipt=self.build,
                task0_result=task0_result,
                task_execution=task_execution,
            )
            name = str(_mapping(launch["execution"], label="launch execution")["name"])
            seeded = self.resume_executions.get(phase)
            if seeded is not None and seeded != name:
                _fail(f"{phase} resume execution differs from persisted launch")
            return name
        if external_path.exists():
            external = _read_canonical(external_path, label=f"{phase} external execution")
            name = external.get("execution_name")
            if (
                set(external) != {"schema_version", "phase", "execution_name", "exact_name_only", "complete"}
                or external.get("schema_version") != "corpus-r6-broad-admission-finisher-external-execution/v1"
                or external.get("phase") != phase
                or type(name) is not str
                or _EXECUTION.fullmatch(name) is None
                or external.get("exact_name_only") is not True
                or external.get("complete") is not True
                or self.resume_executions.get(phase, name) != name
            ):
                _fail(f"{phase} external execution receipt differs")
            return name
        seeded = self.resume_executions.get(phase)
        intent_path = directory / "launch-intent.json"
        if seeded is not None:
            external = {
                "schema_version": "corpus-r6-broad-admission-finisher-external-execution/v1",
                "phase": phase,
                "execution_name": seeded,
                "exact_name_only": True,
                "complete": True,
            }
            _publish_once(external_path, canonical_bytes(external))
            return seeded
        intent = {
            "schema_version": "corpus-r6-broad-admission-finisher-launch-intent/v1",
            "phase": phase,
            "code_sha": self.code_sha,
            "build_id": self.build_id,
            "immutable_image": self.image,
            "request_sha256": canonical_sha256(request),
            "automatic_relaunch": False,
            "complete": True,
        }
        if intent_path.exists():
            _publish_once(intent_path, canonical_bytes(intent))
            _fail(f"{phase} has an ambiguous launch intent without an exact recovery execution")
        _publish_once(intent_path, canonical_bytes(intent))
        args: list[str] = [phase, self.image, self.code_sha, self.build_id, str(request_path)]
        if phase == "task":
            if task0_result is None:
                _fail("full task launch lacks task0 result")
            task0_name = str(_mapping(task0_result["execution"], label="task0 execution")["name"])
            args.append(task0_name)
        environment = dict(os.environ)
        if phase == "collect":
            if task_execution is None:
                _fail("collect lacks full task execution")
            environment["R6_BROAD_ADMISSION_TASK_EXECUTION_NAME"] = task_execution
        completed = self._launcher(args, env=environment)
        _publish_once(directory / "launcher-stdout.raw", completed.stdout)
        _publish_once(directory / "launcher-stderr.raw", completed.stderr)
        if completed.returncode != 0:
            _fail(f"{phase} launcher failed or is ambiguous; do not relaunch")
        launch = validate_launch_receipt_v1(
            _parse_json(completed.stdout, label=f"{phase} launcher stdout"),
            phase=phase,
            request=request,
            build_receipt=self.build,
            task0_result=task0_result,
            task_execution=task_execution,
        )
        _publish_once(launch_path, canonical_bytes(launch))
        return str(_mapping(launch["execution"], label="launch execution")["name"])

    def _describe(self, execution_name: str) -> dict[str, object]:
        completed = self.runner.run(
            (
                "gcloud",
                "run",
                "jobs",
                "executions",
                "describe",
                execution_name,
                "--project",
                PROJECT,
                "--region",
                REGION,
                "--format=json",
            )
        )
        if completed.returncode != 0:
            _fail(f"exact execution describe failed: {execution_name}")
        return _parse_json(completed.stdout, label=f"provider execution {execution_name}")

    def _validate_provider(
        self, value: object, *, execution_name: str, task_count: int
    ) -> tuple[dict[str, object], bool]:
        item = _mapping(value, label="provider execution")
        metadata = _mapping(item.get("metadata"), label="provider metadata")
        labels = _mapping(metadata.get("labels"), label="provider labels")
        spec = _mapping(item.get("spec"), label="provider spec")
        status = _mapping(item.get("status", {}), label="provider status")
        conditions = status.get("conditions", [])
        if type(conditions) is not list:
            _fail("provider execution conditions differ")
        completed = [
            row.get("status")
            for row in conditions
            if isinstance(row, Mapping) and row.get("type") == "Completed"
        ]
        if (
            metadata.get("name") != execution_name
            or _EXECUTION.fullmatch(execution_name) is None
            or _UUID.fullmatch(str(metadata.get("uid", ""))) is None
            or labels.get("run.googleapis.com/job") != JOB
            or labels.get("run.googleapis.com/jobUid") != JOB_UID
            or not str(labels.get("run.googleapis.com/jobGeneration", "")).isdigit()
            or int(str(labels.get("run.googleapis.com/jobGeneration", "0"))) <= 0
            or type(spec.get("taskCount")) is not int
            or spec.get("taskCount") != task_count
            or len(completed) > 1
        ):
            _fail("provider execution identity differs")
        counts: dict[str, int] = {}
        for key in ("succeededCount", "failedCount", "cancelledCount", "runningCount"):
            raw = status.get(key, 0)
            if raw in {None, ""}:
                raw = 0
            if type(raw) is not int or raw < 0:
                _fail("provider execution counts differ")
            counts[key] = raw
        if completed == ["False"] or counts["failedCount"] or counts["cancelledCount"]:
            _fail(f"execution failed or was cancelled: {execution_name}")
        terminal = completed == ["True"]
        if terminal and (
            counts["succeededCount"] != task_count
            or counts["failedCount"] != 0
            or counts["cancelledCount"] != 0
            or counts["runningCount"] != 0
            or type(status.get("completionTime")) is not str
        ):
            _fail("terminal provider counts differ")
        return item, terminal

    def _poll(self, *, phase: str, execution_name: str, task_count: int) -> dict[str, object]:
        directory = self._phase_dir(phase)
        terminal_path = directory / "provider-terminal.json"
        if terminal_path.exists():
            item, terminal = self._validate_provider(
                _read_canonical(terminal_path, label=f"persisted {phase} provider"),
                execution_name=execution_name,
                task_count=task_count,
            )
            if not terminal:
                _fail(f"persisted {phase} provider is not terminal")
            return item
        for _ in range(self.max_polls):
            item = self._describe(execution_name)
            validated, terminal = self._validate_provider(
                item, execution_name=execution_name, task_count=task_count
            )
            _replace(directory / "provider-latest.json", canonical_bytes(validated))
            if terminal:
                _publish_once(terminal_path, canonical_bytes(validated))
                return validated
            time.sleep(self.poll_interval_seconds)
        _fail(f"{phase} exact execution polling exhausted")

    def _result(
        self, *, phase: str, execution_name: str
    ) -> dict[str, object]:
        directory = self._phase_dir(phase)
        path = directory / "result.json"
        if path.exists():
            result = validate_result_receipt_v1(
                _read_canonical(path, label=f"persisted {phase} result"),
                phase=phase,
                execution_name=execution_name,
                build_receipt=self.build,
            )
            seeded = self.resume_executions.get(phase)
            if seeded is not None and seeded != execution_name:
                _fail(f"{phase} result differs from resume execution")
            return result
        self._poll(phase=phase, execution_name=execution_name, task_count=1)
        completed = self._launcher(("result", self.image, self.code_sha, self.build_id, execution_name))
        _publish_once(directory / "result-stdout.raw", completed.stdout)
        _publish_once(directory / "result-stderr.raw", completed.stderr)
        if completed.returncode != 0:
            _fail(f"{phase} exact-name result collection failed")
        result = validate_result_receipt_v1(
            _parse_json(completed.stdout, label=f"{phase} result stdout"),
            phase=phase,
            execution_name=execution_name,
            build_receipt=self.build,
        )
        _publish_once(path, canonical_bytes(result))
        return result

    def _one_task_phase(
        self,
        *,
        phase: str,
        request: Mapping[str, object],
        task0_result: Mapping[str, object] | None = None,
        task_execution: str | None = None,
    ) -> dict[str, object]:
        request_path = self._request(phase, request)
        name = self._launch_or_resume(
            phase=phase,
            request=request,
            request_path=request_path,
            task0_result=task0_result,
            task_execution=task_execution,
        )
        return self._result(phase=phase, execution_name=name)

    def finish(self) -> dict[str, object]:
        self.ensure_installed()

        prepare = self._one_task_phase(phase="prepare", request=self.prepare_request)
        manifest = _identity(
            _result_body(prepare)["manifest_identity"], label="prepared manifest"
        )
        manifest_request = {"manifest_identity": manifest}

        task0 = self._one_task_phase(phase="task0", request=manifest_request)
        if _identity(_result_body(task0)["manifest_identity"], label="task0 manifest") != manifest:
            _fail("task0 manifest differs from prepare")

        task_request_path = self._request("task", manifest_request)
        task_name = self._launch_or_resume(
            phase="task",
            request=manifest_request,
            request_path=task_request_path,
            task0_result=task0,
        )
        task_provider = self._poll(phase="task", execution_name=task_name, task_count=54)
        task_created = _timestamp(
            _mapping(task_provider["metadata"], label="task metadata").get("creationTimestamp"),
            label="full task creation",
        )
        task0_completed = _timestamp(
            _mapping(task0["execution"], label="task0 result execution").get("completion_time"),
            label="task0 completion",
        )
        if task_created <= task0_completed:
            _fail("full task did not begin strictly after the exact task0 gate")

        collect = self._one_task_phase(
            phase="collect", request=manifest_request, task_execution=task_name
        )
        terminal = _identity(
            _result_body(collect)["terminal_identity"], label="collect terminal"
        )
        reopen = self._one_task_phase(
            phase="reopen", request={"terminal_identity": terminal}
        )
        if _identity(_result_body(reopen)["terminal_identity"], label="reopen terminal") != terminal:
            _fail("independent score-free reopen differs from collect")

        grade = self._one_task_phase(
            phase="grade",
            request={
                "outcome_authority_identity": dict(OUTCOME_AUTHORITY_IDENTITY),
                "terminal_identity": terminal,
            },
        )
        grade_terminal = _identity(
            _result_body(grade)["grade_terminal_identity"], label="grade terminal"
        )
        grade_reopen = self._one_task_phase(
            phase="grade-reopen",
            request={"grade_terminal_identity": grade_terminal},
        )
        if _identity(
            _result_body(grade_reopen)["grade_terminal_identity"],
            label="grade reopen terminal",
        ) != grade_terminal:
            _fail("independent grade reopen differs from grade")

        results = {
            "prepare": prepare,
            "task0": task0,
            "collect": collect,
            "reopen": reopen,
            "grade": grade,
            "grade-reopen": grade_reopen,
        }
        final = {
            "schema_version": "corpus-r6-broad-admission-finisher-terminal/v1",
            "code_sha": self.code_sha,
            "cloud_build_id": self.build_id,
            "provider_resolved_image": self.image,
            "output_prefix": self.prepare_request["output_prefix"],
            "full_task_execution": task_name,
            "manifest_identity": manifest,
            "terminal_identity": terminal,
            "grade_terminal_identity": grade_terminal,
            "phase_execution_names": {
                phase: _mapping(receipt["execution"], label=f"{phase} execution")["name"]
                for phase, receipt in results.items()
            },
            "phase_result_sha256": {
                phase: canonical_sha256(receipt) for phase, receipt in results.items()
            },
            "exact_execution_names_only": True,
            "execution_listing_used": False,
            "automatic_relaunch": False,
            "complete": True,
        }
        _publish_once(self.run_dir / "finisher-terminal.json", canonical_bytes(final))
        return final


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-receipt", required=True, type=Path)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--already-installed", action="store_true")
    for phase in EXECUTION_PHASES:
        parser.add_argument(f"--{phase}-execution", default="")
    parser.add_argument("--poll-interval-seconds", type=int, default=30)
    parser.add_argument("--max-polls", type=int, default=720)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.execute or args.confirmation != CONFIRMATION:
        _fail(
            "finisher is default-off; require --execute --confirmation "
            + CONFIRMATION
        )
    build_path = args.build_receipt.resolve()
    build = validate_build_receipt_v1(
        _read_json(build_path, label="build receipt")
    )
    run_dir = _validated_run_dir(args.run_dir)
    resume = {
        phase: getattr(args, phase.replace("-", "_") + "_execution")
        for phase in EXECUTION_PHASES
        if getattr(args, phase.replace("-", "_") + "_execution")
    }
    lock_path = run_dir / "finisher.lock"
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BroadAdmissionFinisherError(
                "another broad-admission finisher owns the local run lock"
            ) from exc
        finisher = BroadAdmissionFinisher(
            run_dir=run_dir,
            build_receipt=build,
            output_prefix=args.output_prefix,
            runner=CommandRunner(),
            already_installed=args.already_installed,
            resume_executions=resume,
            poll_interval_seconds=args.poll_interval_seconds,
            max_polls=args.max_polls,
        )
        result = finisher.finish()
    sys.stdout.buffer.write(canonical_bytes(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BroadAdmissionFinisherError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


__all__ = [
    "BroadAdmissionFinisher",
    "BroadAdmissionFinisherError",
    "CommandResult",
    "CONFIRMATION",
    "FROZEN_COMBINED_TERMINAL_IDENTITY",
    "FROZEN_FRONTIER_MANIFEST_IDENTITY",
    "OUTCOME_AUTHORITY_IDENTITY",
    "canonical_bytes",
    "canonical_sha256",
    "prepare_request_v1",
    "validate_build_receipt_v1",
    "validate_install_receipt_v1",
    "validate_launch_receipt_v1",
    "validate_result_receipt_v1",
]
