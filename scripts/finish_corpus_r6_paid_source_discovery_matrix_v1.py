#!/usr/bin/env python3
"""Crash-closed host finisher for the paid-source discovery-matrix chain.

``prepare`` freezes the exact manifest behind a local create-once intent.
``chain`` must be the direct child command of the canonical production
``launcher_registry.sh`` lease and keeps that one lease for

    install -> task0 -> 54 construction tasks -> collect
            -> 54 independent reopen tasks -> reopen-collect

Every provider or GCS mutation consumes a durable local intent before the
wrapper is invoked.  Once an intent exists, the mutation path is unreachable:
re-entry can only reconcile the exact provider execution or exact known GCS
object.  An ambiguous return is therefore never automatic relaunch authority.
"""

from __future__ import annotations

import argparse
import base64
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from typing import Final


ROOT: Final = Path(__file__).resolve().parents[1]
SOURCE_ROOT: Final = (ROOT / "src").resolve()
sys.path.insert(0, str(SOURCE_ROOT))

from nfl_dfs.research import (  # noqa: E402
    corpus_r6_paid_source_discovery_matrix_freeze_v1 as freeze,
)

if Path(freeze.__file__).resolve() != (
    SOURCE_ROOT
    / "nfl_dfs/research/corpus_r6_paid_source_discovery_matrix_freeze_v1.py"
):
    raise RuntimeError("discovery-matrix finisher module origin differs")


LAUNCHER: Final = ROOT / "scripts/cloud_corpus_r6_paid_source_discovery_matrix_freeze_v1.sh"
PROJECT: Final = freeze.PROJECT_ID
REGION: Final = freeze.REGION
JOB: Final = freeze.JOB_NAME
JOB_UID: Final = freeze.JOB_UID
SERVICE_ACCOUNT: Final = freeze.SERVICE_ACCOUNT
SOURCE_REPOSITORY: Final = "https://github.com/espechtsoftware/nfl-predictions.git"
REGISTRY_STATE_ROOT: Final = Path(
    "/home/erich/.local/state/nfl-dfs/production-launcher-registry"
)
RUN_STATE_ROOT: Final = Path(
    "/home/erich/.local/state/nfl-dfs/fp-sis-retrieval"
)
CONFIRMATION: Final = "I_UNDERSTAND_DISCOVERY_MATRIX_COMPLETE_CHAIN_V1"
PHASES: Final = ("task0", "task", "reopen-task")
ATTRIBUTION_METHODS: Final = frozenset({
    "wrapper-response-and-provider-latest",
    "provider-latest-after-ambiguous-wrapper-return",
    "provider-latest-after-consumed-intent",
    "operator-supplied-exact-name-and-uid",
})

ENABLE_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_ENABLE"
ENABLE_VALUE: Final = "I_UNDERSTAND_SCORE_FREE_DISCOVERY_MATRIX_FREEZE_V1"
MODE_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_MODE"
OUTCOMES_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_OUTCOMES_ALLOWED"
PAYLOAD_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_PAYLOAD_B64"
PAYLOAD_SHA_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_PAYLOAD_SHA256"
TASK0_EXECUTION_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_TASK0_EXECUTION"
TASK0_GATE_SHA_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_TASK0_GATE_SHA256"
TASK0_GATE_B64_ENV: Final = "R6_PAID_SOURCE_DISCOVERY_MATRIX_TASK0_GATE_B64"

_RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{7,96}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)
_EXECUTION = re.compile(re.escape(JOB) + r"-[a-z0-9]{5}\Z")
_IMAGE = re.compile(
    r"us-central1-docker\.pkg\.dev/nfl-predictions-503414/"
    r"nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}\Z"
)
_RFC3339 = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:"
    r"[0-9]{2}(?:\.[0-9]+)?Z\Z"
)


class DiscoveryMatrixFinisherError(RuntimeError):
    """An immutable input, provider fact, or recovery fact differed."""


def _fail(message: str) -> None:
    raise DiscoveryMatrixFinisherError(message)


def canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value, sort_keys=True, separators=(",", ":"),
                ensure_ascii=True, allow_nan=False,
            ).encode("ascii")
            + b"\n"
        )
    except (TypeError, ValueError, UnicodeError) as exc:
        raise DiscoveryMatrixFinisherError("canonical JSON differs") from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if type(value) is not list:
        _fail(f"{label} must be one list")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if (
        set(item) != {"uri", "generation", "sha256", "bytes"}
        or type(item.get("uri")) is not str
        or not str(item["uri"]).startswith("gs://")
        or type(item.get("generation")) not in {str, int}
        or not str(item["generation"]).isdigit()
        or int(str(item["generation"])) <= 0
        or type(item.get("sha256")) is not str
        or _SHA.fullmatch(str(item["sha256"])) is None
        or type(item.get("bytes")) is not int
        or int(item["bytes"]) <= 0
    ):
        _fail(f"{label} differs")
    return {
        "uri": item["uri"], "generation": str(item["generation"]),
        "sha256": item["sha256"], "bytes": item["bytes"],
    }


def _parse_json(raw: bytes, *, label: str, canonical: bool = False) -> dict[str, object]:
    if not raw:
        _fail(f"{label} is empty")
    try:
        item = _mapping(json.loads(raw), label=label)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DiscoveryMatrixFinisherError(f"{label} is not JSON") from exc
    if canonical and raw not in {canonical_bytes(item), canonical_bytes(item)[:-1]}:
        _fail(f"{label} is not canonical JSON")
    return item


def _read_canonical(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        _fail(f"{label} must be one absolute unaliased regular file")
    return _parse_json(path.read_bytes(), label=label, canonical=True)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_once(path: Path, raw: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            _fail(f"local create-once collision: {path}")
        return False
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    _fsync_directory(path.parent)
    return True


def _validated_run_dir(path: Path, *, run_id: str) -> Path:
    if not path.is_absolute() or path.is_symlink():
        _fail("discovery-matrix state directory must be absolute and unaliased")
    root = RUN_STATE_ROOT.resolve(strict=False)
    retained = path.resolve(strict=False)
    if retained != root / run_id:
        _fail("discovery-matrix state must be the canonical run-id directory")
    cursor = retained
    while cursor != root:
        if cursor.exists() and cursor.is_symlink():
            _fail("discovery-matrix state may not traverse a symlink")
        cursor = cursor.parent
    retained.mkdir(parents=True, exist_ok=True, mode=0o700)
    return retained


class CommandResult:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class CommandRunner:
    """Injectable argv-only subprocess boundary."""

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        completed = subprocess.run(
            list(argv), cwd=None if cwd is None else str(cwd),
            env=None if env is None else dict(env), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _git_text(runner: CommandRunner, argv: Sequence[str], *, label: str) -> str:
    result = runner.run(argv, cwd=ROOT)
    if result.returncode != 0:
        _fail(f"{label} command failed")
    try:
        return result.stdout.decode("utf-8").strip()
    except UnicodeError as exc:
        raise DiscoveryMatrixFinisherError(f"{label} output differs") from exc


def validate_exact_repository(*, code_sha: str, runner: CommandRunner) -> None:
    if (
        _git_text(runner, ("git", "rev-parse", "HEAD"), label="Git HEAD")
        != code_sha
        or _git_text(
            runner,
            ("git", "rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
            label="origin/main",
        )
        != code_sha
    ):
        _fail("discovery-matrix host must equal exact durable origin/main")
    status = runner.run(
        ("git", "status", "--porcelain", "--untracked-files=all"), cwd=ROOT,
    )
    if status.returncode != 0:
        _fail("discovery-matrix Git status is unavailable")
    if status.stdout:
        _fail("discovery-matrix host checkout is not exact-clean")


def validate_build_provider(
    value: object, *, code_sha: str, build_id: str, image: str,
) -> dict[str, object]:
    item = _mapping(value, label="Cloud Build")
    source = _mapping(item.get("source"), label="Cloud Build source")
    requested = _mapping(source.get("gitSource"), label="requested Git source")
    provenance = _mapping(
        item.get("sourceProvenance"), label="Cloud Build source provenance"
    )
    resolved = _mapping(
        provenance.get("resolvedGitSource"), label="resolved Git source"
    )
    substitutions = _mapping(
        item.get("substitutions"), label="Cloud Build substitutions"
    )
    results = _mapping(item.get("results"), label="Cloud Build results")
    images = _sequence(results.get("images"), label="Cloud Build images")
    tag = (
        f"{REGION}-docker.pkg.dev/{PROJECT}/nfl-dfs/"
        f"nfl-dfs:paid-source-discovery-matrix-{code_sha}"
    )
    digest = image.rsplit("@", 1)[-1]
    matches = [
        row for row in images
        if isinstance(row, Mapping)
        and row.get("name") == tag and row.get("digest") == digest
    ]
    if (
        item.get("id") != build_id
        or item.get("status") != "SUCCESS"
        or requested != {"url": SOURCE_REPOSITORY, "revision": code_sha}
        or resolved != {"url": SOURCE_REPOSITORY, "revision": code_sha}
        or substitutions.get("_CODE_SHA") != code_sha
        or substitutions.get("_BUILD_IMAGE") != tag
        or len(matches) != 1
    ):
        _fail("Cloud Build/image/exact Git source differs")
    return item


def _environment(container: Mapping[str, object]) -> dict[str, str]:
    rows = _sequence(container.get("env"), label="provider environment")
    result: dict[str, str] = {}
    for value in rows:
        row = _mapping(value, label="provider environment row")
        if (
            set(row) != {"name", "value"}
            or type(row.get("name")) is not str
            or type(row.get("value")) is not str
            or str(row["name"]) in result
        ):
            _fail("provider environment row differs")
        result[str(row["name"])] = str(row["value"])
    return result


def _timeout_seconds(task_spec: Mapping[str, object]) -> str:
    has_seconds = "timeoutSeconds" in task_spec
    has_duration = "timeout" in task_spec
    seconds = task_spec.get("timeoutSeconds")
    duration = task_spec.get("timeout")
    if (
        not (has_seconds or has_duration)
        or (has_seconds and seconds != freeze.TASK_TIMEOUT_SECONDS)
        or (
            has_duration
            and duration not in {
                f"{freeze.TASK_TIMEOUT_SECONDS}s",
                f"{freeze.TASK_TIMEOUT_SECONDS}.000000000s",
            }
        )
    ):
        _fail("provider execution timeout differs")
    return freeze.TASK_TIMEOUT_SECONDS


def _payload_identity(raw: bytes) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DiscoveryMatrixFinisherError("provider payload is not JSON") from exc
    if raw not in {freeze.canonical_json_bytes(value), freeze.canonical_json_bytes(value) + b"\n"}:
        _fail("provider payload is not canonical JSON")
    return _identity(value, label="provider payload identity")


def validate_provider_execution(
    value: object,
    *,
    mode: str,
    execution_name: str,
    execution_uid: str | None,
    code_sha: str,
    build_id: str,
    image: str,
    payload: bytes,
    task0_execution: str,
) -> tuple[dict[str, object], str]:
    """Validate one exact execution and classify its Completed state.

    MISSING and Unknown are retryable observations.  Unlike a one-task
    controller, the 54-task phases explicitly admit partial succeeded counts
    while still nonterminal.
    """

    if mode not in PHASES:
        _fail("discovery-matrix provider mode differs")
    task_count = 1 if mode == "task0" else freeze.TASK_COUNT
    item = _mapping(value, label=f"{mode} provider execution")
    metadata = _mapping(item.get("metadata"), label="provider metadata")
    labels = _mapping(metadata.get("labels"), label="provider labels")
    spec = _mapping(item.get("spec"), label="provider spec")
    template = _mapping(spec.get("template"), label="provider template")
    task_spec = _mapping(template.get("spec"), label="provider task spec")
    containers = _sequence(task_spec.get("containers"), label="provider containers")
    if len(containers) != 1:
        _fail("provider container count differs")
    container = _mapping(containers[0], label="provider container")
    limits = _mapping(
        _mapping(container.get("resources"), label="provider resources").get("limits"),
        label="provider limits",
    )
    environment = _environment(container)
    encoded = environment.get(PAYLOAD_ENV, "")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise DiscoveryMatrixFinisherError("provider payload transport differs") from exc
    retained_identity = _payload_identity(payload)
    task0_gate_sha = environment.get(TASK0_GATE_SHA_ENV)
    task0_gate_b64 = environment.get(TASK0_GATE_B64_ENV)
    expected = {
        "CODE_SHA": code_sha,
        "IMAGE_URI": image,
        "IMAGE_DIGEST": image.rsplit("@", 1)[-1],
        "BUILD_ID": build_id,
        ENABLE_ENV: ENABLE_VALUE,
        MODE_ENV: mode,
        OUTCOMES_ENV: "false",
        PAYLOAD_ENV: encoded,
        PAYLOAD_SHA_ENV: sha256(payload).hexdigest(),
        TASK0_EXECUTION_ENV: "none" if mode != "task" else task0_execution,
        TASK0_GATE_SHA_ENV: "none" if mode != "task" else str(task0_gate_sha),
        TASK0_GATE_B64_ENV: "none" if mode != "task" else str(task0_gate_b64),
    }
    if mode == "task":
        try:
            gate_raw = base64.b64decode(str(task0_gate_b64), validate=True)
            gate = _parse_json(gate_raw, label="task0 gate", canonical=True)
        except (ValueError, DiscoveryMatrixFinisherError) as exc:
            raise DiscoveryMatrixFinisherError("provider task0 gate differs") from exc
        if (
            _EXECUTION.fullmatch(task0_execution) is None
            or _SHA.fullmatch(str(task0_gate_sha)) is None
            or gate.get("schema_version") != freeze.TASK0_GATE_SCHEMA
            or gate.get("execution_id") != task0_execution
            or gate.get("task0_gate_sha256") != task0_gate_sha
            or gate.get("manifest_identity") != retained_identity
            or gate.get("complete") is not True
        ):
            _fail("provider task0 gate differs")
    if (
        decoded != payload
        or environment != expected
        or metadata.get("name") != execution_name
        or _EXECUTION.fullmatch(execution_name) is None
        or type(metadata.get("uid")) is not str
        or _UUID.fullmatch(str(metadata["uid"])) is None
        or (execution_uid is not None and metadata.get("uid") != execution_uid)
        or labels.get("run.googleapis.com/job") != JOB
        or labels.get("run.googleapis.com/jobUid") != JOB_UID
        or not str(labels.get("run.googleapis.com/jobGeneration", "")).isdigit()
        or int(str(labels.get("run.googleapis.com/jobGeneration", "0"))) <= 0
        or spec.get("taskCount") != task_count
        or spec.get("parallelism") != task_count
        or task_spec.get("maxRetries") != 0
        or _timeout_seconds(task_spec) != freeze.TASK_TIMEOUT_SECONDS
        or task_spec.get("serviceAccountName") != SERVICE_ACCOUNT
        or container.get("image") != image
        or container.get("command") != list(freeze.CONTAINER_COMMAND)
        or container.get("args")
        != [freeze.CONTAINER_SCRIPT, "container-run", mode]
        or limits != {"cpu": freeze.CPU_LIMIT, "memory": freeze.MEMORY_LIMIT}
    ):
        _fail(f"{mode} provider envelope differs")

    status = _mapping(item.get("status", {}), label="provider status")
    conditions = _sequence(status.get("conditions", []), label="provider conditions")
    completed = [
        row.get("status") for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if len(completed) > 1 or (completed and completed[0] not in {"Unknown", "True", "False"}):
        _fail("provider Completed condition differs")
    state = "MISSING" if not completed else str(completed[0])
    counts: dict[str, int] = {}
    for key in (
        "runningCount", "succeededCount", "failedCount", "cancelledCount",
        "retriedCount",
    ):
        raw = status.get(key, 0)
        if raw in {None, ""}:
            raw = 0
        if type(raw) is not int or raw < 0:
            _fail("provider execution counts differ")
        counts[key] = raw
    census = sum(counts[key] for key in (
        "runningCount", "succeededCount", "failedCount", "cancelledCount",
    ))
    if census > task_count or counts["retriedCount"] != 0:
        _fail("provider execution task census differs")
    completion = status.get("completionTime")
    if state == "True":
        if (
            counts != {
                "runningCount": 0, "succeededCount": task_count,
                "failedCount": 0, "cancelledCount": 0, "retriedCount": 0,
            }
            or type(completion) is not str
            or _RFC3339.fullmatch(completion) is None
        ):
            _fail("terminal provider success counts differ")
    elif state == "False":
        if (
            counts["runningCount"] != 0
            or counts["failedCount"] + counts["cancelledCount"] < 1
            or type(completion) is not str
            or _RFC3339.fullmatch(completion) is None
        ):
            _fail("terminal provider failure counts differ")
    else:
        if counts["failedCount"] != 0 or counts["cancelledCount"] != 0:
            _fail("nonterminal provider state differs")
        if completion not in {None, ""} and (
            type(completion) is not str
            or _RFC3339.fullmatch(completion) is None
            or counts["succeededCount"] != task_count
            or counts["runningCount"] != 0
        ):
            _fail("nonterminal provider completion lag differs")
    return item, state


def _job_task_spec(value: Mapping[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    spec = _mapping(value.get("spec"), label="job spec")
    outer = _mapping(
        _mapping(spec.get("template"), label="job template").get("spec"),
        label="job execution template",
    )
    inner_template = _mapping(outer.get("template"), label="job task template")
    inner = _mapping(inner_template.get("spec"), label="job task spec")
    return outer, inner


def validate_installed_job(
    value: object,
    *,
    code_sha: str,
    build_id: str,
    image: str,
    previous_latest: str,
    minimum_generation: int,
) -> dict[str, object]:
    item = _mapping(value, label="installed job")
    metadata = _mapping(item.get("metadata"), label="job metadata")
    status = _mapping(item.get("status"), label="job status")
    outer, task_spec = _job_task_spec(item)
    containers = _sequence(task_spec.get("containers"), label="job containers")
    if len(containers) != 1:
        _fail("installed job container count differs")
    container = _mapping(containers[0], label="installed job container")
    limits = _mapping(
        _mapping(container.get("resources"), label="job resources").get("limits"),
        label="job limits",
    )
    env = _environment(container)
    generation = metadata.get("generation")
    ready = [
        row.get("status") for row in _sequence(status.get("conditions", []), label="job conditions")
        if isinstance(row, Mapping) and row.get("type") == "Ready"
    ]
    expected_env = {
        "CODE_SHA": code_sha, "IMAGE_URI": image,
        "IMAGE_DIGEST": image.rsplit("@", 1)[-1], "BUILD_ID": build_id,
        ENABLE_ENV: "DISABLED", MODE_ENV: "DISABLED", OUTCOMES_ENV: "false",
        TASK0_EXECUTION_ENV: "none", TASK0_GATE_SHA_ENV: "none",
        TASK0_GATE_B64_ENV: "none",
    }
    latest = _mapping(
        status.get("latestCreatedExecution"), label="job latest execution"
    ).get("name")
    if (
        metadata.get("name") != JOB or metadata.get("uid") != JOB_UID
        or type(generation) is not int or generation <= minimum_generation
        or status.get("observedGeneration") != generation
        or ready != ["True"]
        or latest != previous_latest
        or outer.get("taskCount") != freeze.TASK_COUNT
        or outer.get("parallelism") != freeze.TASK_COUNT
        or task_spec.get("maxRetries") != 0
        or _timeout_seconds(task_spec) != freeze.TASK_TIMEOUT_SECONDS
        or task_spec.get("serviceAccountName") != SERVICE_ACCOUNT
        or container.get("image") != image
        or container.get("command") != list(freeze.CONTAINER_COMMAND)
        or container.get("args") != [freeze.CONTAINER_SCRIPT, "container-help"]
        or limits != {"cpu": freeze.CPU_LIMIT, "memory": freeze.MEMORY_LIMIT}
        or env != expected_env
    ):
        _fail("installed default-off job differs")
    return item


def _terminal_predecessor(value: object, *, expected_name: str | None = None) -> tuple[str, str]:
    item = _mapping(value, label="latest predecessor execution")
    metadata = _mapping(item.get("metadata"), label="predecessor metadata")
    labels = _mapping(metadata.get("labels"), label="predecessor labels")
    status = _mapping(item.get("status", {}), label="predecessor status")
    completed = [
        row.get("status") for row in _sequence(status.get("conditions", []), label="predecessor conditions")
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    name = metadata.get("name")
    uid = metadata.get("uid")
    counts = []
    for key in ("succeededCount", "failedCount", "cancelledCount"):
        raw = status.get(key, 0) or 0
        if type(raw) is not int or raw < 0:
            _fail("predecessor task counts differ")
        counts.append(raw)
    if (
        type(name) is not str or _EXECUTION.fullmatch(name) is None
        or (expected_name is not None and name != expected_name)
        or type(uid) is not str or _UUID.fullmatch(uid) is None
        or labels.get("run.googleapis.com/job") != JOB
        or labels.get("run.googleapis.com/jobUid") != JOB_UID
        or completed not in (["True"], ["False"])
        or (status.get("runningCount", 0) or 0) != 0
        or sum(counts) <= 0
        or type(status.get("completionTime")) is not str
        or _RFC3339.fullmatch(str(status["completionTime"])) is None
    ):
        _fail("reused job latest execution is not terminal and idle")
    return name, uid


def _proc_identity(proc_root: Path, pid: int) -> tuple[int, int]:
    try:
        raw = (proc_root / str(pid) / "stat").read_text(encoding="ascii")
        suffix = raw.rsplit(") ", maxsplit=1)[1].split()
        return int(suffix[1]), int(suffix[19])
    except (OSError, ValueError, IndexError) as exc:
        raise DiscoveryMatrixFinisherError("launcher process identity unavailable") from exc


def _lock_is_held(path: Path) -> bool:
    with path.open("a+b") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    return False


def verify_launcher_registry_lane(
    *,
    run_id: str,
    environment: Mapping[str, str],
    proc_root: Path = Path("/proc"),
    current_pid: int | None = None,
    lock_probe: Callable[[Path], bool] = _lock_is_held,
) -> None:
    state_root = Path(environment.get("NFL_LAUNCHER_REGISTRY_STATE_ROOT", ""))
    receipt = Path(environment.get("NFL_LAUNCHER_REGISTRY_RECEIPT", ""))
    if (
        not state_root.is_absolute()
        or state_root.resolve(strict=False) != REGISTRY_STATE_ROOT
        or receipt.parent != REGISTRY_STATE_ROOT / "launchers"
        or receipt.is_symlink() or not receipt.is_file()
    ):
        _fail("canonical production launcher_registry receipt is absent")
    expected_hash = environment.get("NFL_LAUNCHER_REGISTRY_RECEIPT_SHA256", "")
    if _SHA.fullmatch(expected_hash) is None or sha256(receipt.read_bytes()).hexdigest() != expected_hash:
        _fail("launcher_registry receipt hash differs")
    item = _read_canonical(receipt, label="launcher_registry receipt")
    wrapper_pid = item.get("pid")
    wrapper_ticks = item.get("process_start_ticks")
    if (
        set(item) != {
            "schema_version", "script_path", "pid", "process_start_ticks",
            "owner", "lane", "target_run_id_prefixes", "acquired_at_utc",
        }
        or item.get("schema_version") != "shared-launcher-registry/v1"
        or item.get("script_path") != str(Path(__file__).resolve())
        or item.get("owner") != "production" or item.get("lane") != JOB
        or item.get("target_run_id_prefixes") != [run_id]
        or type(wrapper_pid) is not int or wrapper_pid <= 1
        or type(wrapper_ticks) is not int or wrapper_ticks <= 0
        or _RFC3339.fullmatch(str(item.get("acquired_at_utc", ""))) is None
    ):
        _fail("launcher_registry receipt authority differs")
    if (
        environment.get("NFL_LAUNCHER_REGISTRY_LANE") != JOB
        or environment.get("NFL_LAUNCHER_REGISTRY_WRAPPER_PID") != str(wrapper_pid)
        or environment.get("NFL_LAUNCHER_REGISTRY_WRAPPER_START_TICKS") != str(wrapper_ticks)
    ):
        _fail("launcher_registry environment authority differs")
    _, live_ticks = _proc_identity(proc_root, wrapper_pid)
    if live_ticks != wrapper_ticks:
        _fail("launcher_registry wrapper process was reused")
    cursor = os.getpid() if current_pid is None else current_pid
    seen: set[int] = set()
    for _ in range(64):
        if cursor == wrapper_pid:
            break
        if cursor <= 1 or cursor in seen:
            _fail("launcher_registry wrapper is not an ancestor")
        seen.add(cursor)
        cursor, _ = _proc_identity(proc_root, cursor)
    else:
        _fail("launcher_registry ancestor chain is unbounded")
    lock_path = REGISTRY_STATE_ROOT / "launcher-locks" / (
        sha256(JOB.encode("ascii")).hexdigest() + ".lock"
    )
    if lock_path.is_symlink() or not lock_path.is_file() or not lock_probe(lock_path):
        _fail("canonical production launcher_registry lane lock is not held")


def output_uri_inventory(run_id: str) -> list[str]:
    if _RUN_ID.fullmatch(run_id) is None:
        _fail("discovery-matrix run ID differs")
    prefix = f"{freeze.OUTPUT_PREFIX}/{run_id}/"
    uris = [f"{prefix}manifest.json", f"{prefix}terminal.json", f"{prefix}reopen-terminal.json"]
    ordinal = 0
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            base = f"{prefix}source-task-{ordinal:02d}-{season}-w{week:02d}/"
            uris.extend((
                f"{base}candidate-discovery-matrix.bin",
                f"{base}task-result.json",
                f"{base}reopen-task-result.json",
            ))
            ordinal += 1
    if ordinal != freeze.TASK_COUNT or len(uris) != 165 or len(set(uris)) != 165:
        _fail("discovery-matrix output inventory differs")
    return sorted(uris)


def make_object_exists() -> Callable[[str], bool]:
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise DiscoveryMatrixFinisherError("google-cloud-storage is required") from exc

    local = threading.local()

    def exists(uri: str) -> bool:
        if not uri.startswith("gs://") or "/" not in uri[5:]:
            _fail("discovery-matrix output URI differs")
        client = getattr(local, "client", None)
        if client is None:
            client = storage.Client(project=PROJECT)
            local.client = client
        bucket, name = uri[5:].split("/", 1)
        return bool(client.bucket(bucket).blob(name).exists(client=client, timeout=30))

    return exists


def validate_prepare_request(
    value: object,
    *,
    run_id: str,
    code_sha: str,
    build_id: str,
    image: str,
) -> dict[str, object]:
    item = _mapping(value, label="discovery-matrix prepare request")
    if (
        set(item) != {
            "run_id", "code_sha", "immutable_image", "build_id",
            "runtime_build_attestation_identity", "candidate_root_identity",
            "later_source_freeze_identity",
        }
        or item.get("run_id") != run_id or item.get("code_sha") != code_sha
        or item.get("build_id") != build_id or item.get("immutable_image") != image
        or _identity(item.get("candidate_root_identity"), label="candidate root")
        != freeze.CANDIDATE_ROOT_IDENTITY
        or _identity(item.get("later_source_freeze_identity"), label="source freeze")
        != freeze.LATER_SOURCE_FREEZE_IDENTITY
    ):
        _fail("discovery-matrix prepare request differs")
    attestation = _identity(
        item.get("runtime_build_attestation_identity"), label="build attestation"
    )
    expected_uri = (
        f"gs://{PROJECT}-corpus-retrieval/research/"
        f"corpus-r6-paid-source-discovery-matrix-builds/{code_sha}/{build_id}/"
        "runtime-build-attestation.json"
    )
    if attestation["uri"] != expected_uri:
        _fail("runtime build attestation URI differs")
    return item


def validate_prepare_result(
    value: object, *, run_id: str, reconciliation: bool | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="discovery-matrix prepare result")
    identity = _identity(item.get("manifest_identity"), label="matrix manifest")
    expected_uri = f"{freeze.OUTPUT_PREFIX}/{run_id}/manifest.json"
    if (
        set(item) != {
            "schema_version", "manifest_identity", "manifest_sha256",
            "task_count", "publication_performed",
            "ambiguous_return_reconciled", "uses_realized_outcomes", "complete",
        }
        or item.get("schema_version")
        != "corpus-r6-paid-source-discovery-matrix-prepare-result/v1"
        or identity["uri"] != expected_uri
        or type(item.get("manifest_sha256")) is not str
        or _SHA.fullmatch(str(item["manifest_sha256"])) is None
        or item.get("task_count") != freeze.TASK_COUNT
        or item.get("uses_realized_outcomes") is not False
        or item.get("complete") is not True
        or type(item.get("publication_performed")) is not bool
        or type(item.get("ambiguous_return_reconciled")) is not bool
        or item.get("ambiguous_return_reconciled")
        == item.get("publication_performed")
        or (
            reconciliation is not None
            and item.get("ambiguous_return_reconciled") is not reconciliation
        )
    ):
        _fail("discovery-matrix prepare result differs")
    return item


def validate_collect_result(
    value: object,
    *,
    run_id: str,
    reopen: bool,
    reconciliation: bool | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="discovery-matrix collect result")
    identity_key = "reopen_terminal_identity" if reopen else "terminal_identity"
    hash_key = "reopen_sha256" if reopen else "terminal_sha256"
    schema = (
        "corpus-r6-paid-source-discovery-matrix-reopen-collect-result/v1"
        if reopen else "corpus-r6-paid-source-discovery-matrix-collect-result/v1"
    )
    filename = "reopen-terminal.json" if reopen else "terminal.json"
    expected_keys = {
        "schema_version", identity_key, hash_key, "task_count",
        "publication_performed", "ambiguous_return_reconciled", "complete",
    }
    if not reopen:
        expected_keys.add("root_published_last")
    identity = _identity(item.get(identity_key), label=identity_key)
    if (
        set(item) != expected_keys or item.get("schema_version") != schema
        or identity["uri"] != f"{freeze.OUTPUT_PREFIX}/{run_id}/{filename}"
        or type(item.get(hash_key)) is not str
        or _SHA.fullmatch(str(item[hash_key])) is None
        or item.get("task_count") != freeze.TASK_COUNT
        or (not reopen and item.get("root_published_last") is not True)
        or type(item.get("publication_performed")) is not bool
        or type(item.get("ambiguous_return_reconciled")) is not bool
        or item.get("ambiguous_return_reconciled")
        == item.get("publication_performed")
        or (
            reconciliation is not None
            and item.get("ambiguous_return_reconciled") is not reconciliation
        )
        or item.get("complete") is not True
    ):
        _fail("discovery-matrix collect result differs")
    return item


class DiscoveryMatrixFinisher:
    def __init__(
        self,
        *,
        run_id: str,
        code_sha: str,
        build_id: str,
        image: str,
        run_dir: Path,
        prepare_request: Mapping[str, object],
        runner: CommandRunner,
        object_exists: Callable[[str], bool],
        poll_interval_seconds: int,
        max_polls: int,
        reconcile_polls: int,
        collect_polls: int,
        preflight_workers: int,
        sleeper: Callable[[float], None] = time.sleep,
        recovery_executions: Mapping[str, tuple[str, str]] | None = None,
    ) -> None:
        if (
            _RUN_ID.fullmatch(run_id) is None
            or _COMMIT.fullmatch(code_sha) is None
            or _UUID.fullmatch(build_id) is None
            or _IMAGE.fullmatch(image) is None
        ):
            _fail("discovery-matrix finisher immutable inputs differ")
        if (
            not 1 <= poll_interval_seconds <= 60
            or not 1 <= max_polls <= 10_000
            or not 1 <= reconcile_polls <= 120
            or not 1 <= collect_polls <= 120
            or not 1 <= preflight_workers <= 32
        ):
            _fail("discovery-matrix finisher bounds differ")
        self.run_id = run_id
        self.code_sha = code_sha
        self.build_id = build_id
        self.image = image
        self.run_dir = run_dir
        self.prepare_request = validate_prepare_request(
            prepare_request, run_id=run_id, code_sha=code_sha,
            build_id=build_id, image=image,
        )
        self.runner = runner
        self.object_exists = object_exists
        self.poll_interval_seconds = poll_interval_seconds
        self.max_polls = max_polls
        self.reconcile_polls = reconcile_polls
        self.collect_polls = collect_polls
        self.preflight_workers = preflight_workers
        self.sleeper = sleeper
        self.recovery_executions = dict(recovery_executions or {})
        for phase, pair in self.recovery_executions.items():
            if (
                phase not in PHASES or type(pair) is not tuple or len(pair) != 2
                or _EXECUTION.fullmatch(pair[0]) is None
                or _UUID.fullmatch(pair[1]) is None
            ):
                _fail("discovery-matrix recovery execution differs")

    def _path(self, relative: str) -> Path:
        return self.run_dir / relative

    def _phase_path(self, phase: str, name: str) -> Path:
        return self._path(f"phases/{phase}/{name}")

    def _run_json(self, argv: Sequence[str], *, label: str) -> dict[str, object]:
        result = self.runner.run(argv, cwd=ROOT)
        if result.returncode != 0:
            _fail(f"{label} command failed")
        return _parse_json(result.stdout, label=label)

    def _describe_build(self) -> dict[str, object]:
        return self._run_json(
            (
                "gcloud", "builds", "describe", self.build_id,
                "--project", PROJECT, "--format=json",
            ),
            label="discovery-matrix Cloud Build",
        )

    def _describe_job(self) -> dict[str, object] | None:
        result = self.runner.run(
            (
                "gcloud", "run", "jobs", "describe", JOB,
                "--project", PROJECT, "--region", REGION, "--format=json",
            ),
            cwd=ROOT,
        )
        if result.returncode != 0:
            return None
        return _parse_json(result.stdout, label="provider job")

    def _describe_execution(self, name: str) -> dict[str, object] | None:
        if _EXECUTION.fullmatch(name) is None:
            _fail("provider execution name differs")
        result = self.runner.run(
            (
                "gcloud", "run", "jobs", "executions", "describe", name,
                "--project", PROJECT, "--region", REGION, "--format=json",
            ),
            cwd=ROOT,
        )
        if result.returncode != 0:
            return None
        return _parse_json(result.stdout, label=f"provider execution {name}")

    def _job_latest(self) -> tuple[dict[str, object], str]:
        item = self._describe_job()
        if item is None:
            _fail("provider job description is unavailable")
        metadata = _mapping(item.get("metadata"), label="job metadata")
        status = _mapping(item.get("status"), label="job status")
        latest = _mapping(
            status.get("latestCreatedExecution"), label="job latest execution"
        ).get("name")
        if (
            metadata.get("name") != JOB or metadata.get("uid") != JOB_UID
            or type(latest) is not str or _EXECUTION.fullmatch(latest) is None
        ):
            _fail("reused job identity/latest execution differs")
        return item, latest

    def _build_receipt(self) -> dict[str, object]:
        path = self._path("build.json")
        if path.exists():
            item = _read_canonical(path, label="persisted build receipt")
            if (
                set(item) != {
                    "schema_version", "code_sha", "cloud_build_id",
                    "provider_resolved_image", "provider_build_sha256",
                    "provider_requested_and_resolved_git_source_exact",
                    "complete",
                }
                or
                item.get("schema_version")
                != "corpus-r6-paid-source-discovery-matrix-host-build/v1"
                or item.get("code_sha") != self.code_sha
                or item.get("cloud_build_id") != self.build_id
                or item.get("provider_resolved_image") != self.image
                or type(item.get("provider_build_sha256")) is not str
                or _SHA.fullmatch(str(item["provider_build_sha256"])) is None
                or item.get("provider_requested_and_resolved_git_source_exact")
                is not True
                or item.get("complete") is not True
            ):
                _fail("persisted discovery-matrix build receipt differs")
            return item
        build = validate_build_provider(
            self._describe_build(), code_sha=self.code_sha,
            build_id=self.build_id, image=self.image,
        )
        body = {
            "schema_version": "corpus-r6-paid-source-discovery-matrix-host-build/v1",
            "code_sha": self.code_sha, "cloud_build_id": self.build_id,
            "provider_resolved_image": self.image,
            "provider_build_sha256": canonical_sha256(build),
            "provider_requested_and_resolved_git_source_exact": True,
            "complete": True,
        }
        _publish_once(path, canonical_bytes(body))
        return body

    def _preflight(self) -> dict[str, object]:
        path = self._path("preflight.json")
        inventory = output_uri_inventory(self.run_id)
        if self._path("preflight-failure.json").exists():
            _fail("discovery-matrix run ID was already consumed by preflight")
        if path.exists():
            item = _read_canonical(path, label="persisted namespace preflight")
            if (
                set(item) != {
                    "schema_version", "run_id",
                    "checked_exact_output_uri_count",
                    "checked_exact_output_uri_manifest_sha256",
                    "existing_output_uri_count", "object_listing_used",
                    "direct_object_metadata_reads_only", "complete",
                }
                or
                item.get("schema_version")
                != "corpus-r6-paid-source-discovery-matrix-host-preflight/v1"
                or item.get("run_id") != self.run_id
                or item.get("checked_exact_output_uri_count") != 165
                or item.get("checked_exact_output_uri_manifest_sha256")
                != canonical_sha256(inventory)
                or item.get("existing_output_uri_count") != 0
                or item.get("object_listing_used") is not False
                or item.get("direct_object_metadata_reads_only") is not True
                or item.get("complete") is not True
            ):
                _fail("persisted discovery-matrix preflight differs")
        if self._path("prepare/intent.json").exists():
            _fail("namespace preflight cannot be created after prepare intent")
        # Even when an earlier clean receipt exists, repeat every direct probe
        # immediately before the first intent. A crash between those two local
        # writes must not turn an hours-old absence observation into authority.
        with ThreadPoolExecutor(max_workers=self.preflight_workers) as executor:
            existence = list(executor.map(self.object_exists, inventory))
        existing = [
            uri for uri, present in zip(inventory, existence, strict=True) if present
        ]
        if existing:
            body = {
                "schema_version": "corpus-r6-paid-source-discovery-matrix-host-preflight-failure/v1",
                "run_id": self.run_id, "existing_output_uri_count": len(existing),
                "existing_output_uris": existing, "run_id_consumed": True,
                "complete": True,
            }
            _publish_once(self._path("preflight-failure.json"), canonical_bytes(body))
            _fail("discovery-matrix output namespace is not fresh")
        body = {
            "schema_version": "corpus-r6-paid-source-discovery-matrix-host-preflight/v1",
            "run_id": self.run_id,
            "checked_exact_output_uri_count": 165,
            "checked_exact_output_uri_manifest_sha256": canonical_sha256(inventory),
            "existing_output_uri_count": 0, "object_listing_used": False,
            "direct_object_metadata_reads_only": True, "complete": True,
        }
        _publish_once(path, canonical_bytes(body))
        return body

    def _record_call(
        self, directory: Path, *, label: str, call: CommandResult,
    ) -> None:
        body = {
            "schema_version": "corpus-r6-paid-source-discovery-matrix-host-call/v1",
            "label": label, "returncode": call.returncode,
            "stdout_sha256": sha256(call.stdout).hexdigest(),
            "stdout_bytes": len(call.stdout),
            "stderr_sha256": sha256(call.stderr).hexdigest(),
            "stderr_bytes": len(call.stderr), "complete": True,
        }
        _publish_once(directory / "call.json", canonical_bytes(body))

    @staticmethod
    def _attempt_start(root: Path) -> int:
        existing = sorted(path for path in root.glob("*") if path.is_dir()) \
            if root.is_dir() else []
        if [path.name for path in existing] != [
            f"{index:03d}" for index in range(len(existing))
        ] or any(not (path / "call.json").is_file() for path in existing):
            _fail("persisted reconciliation attempt census differs")
        return len(existing)

    def _wrapper_call(self, argv: Sequence[str]) -> CommandResult:
        return self.runner.run(tuple(argv), cwd=ROOT, env=dict(os.environ))

    def prepare(self) -> dict[str, object]:
        result_path = self._path("prepare/result.json")
        identity_path = self._path("manifest-identity.json")
        request_path = self._path("prepare/request.json")
        intent_path = self._path("prepare/intent.json")
        intent = {
            "schema_version": "corpus-r6-paid-source-discovery-matrix-host-prepare-intent/v1",
            "run_id": self.run_id, "code_sha": self.code_sha,
            "cloud_build_id": self.build_id, "provider_resolved_image": self.image,
            "request_sha256": canonical_sha256(self.prepare_request),
            "target_uri": f"{freeze.OUTPUT_PREFIX}/{self.run_id}/manifest.json",
            "automatic_republication": False,
            "ambiguous_return_recovery": "exact-known-uri-read-only",
            "complete": True,
        }
        if result_path.exists() != identity_path.exists():
            _fail("persisted prepare result/identity census differs")
        if result_path.exists():
            if _read_canonical(
                request_path,
                label="persisted prepare request",
            ) != self.prepare_request:
                _fail("persisted prepare request differs")
            if _read_canonical(
                intent_path, label="persisted prepare intent"
            ) != intent:
                _fail("persisted prepare intent differs")
            result = validate_prepare_result(
                _read_canonical(result_path, label="persisted prepare result"),
                run_id=self.run_id,
            )
            if _read_canonical(identity_path, label="persisted manifest identity") != result["manifest_identity"]:
                _fail("persisted manifest identity differs")
            return result

        validate_exact_repository(code_sha=self.code_sha, runner=self.runner)
        self._build_receipt()
        _publish_once(request_path, canonical_bytes(self.prepare_request))
        fresh = not intent_path.exists()
        if fresh:
            self._preflight()
        if not _publish_once(intent_path, canonical_bytes(intent)) and fresh:
            _fail("prepare intent create race")

        result: dict[str, object] | None = None
        if fresh:
            call = self._wrapper_call((
                str(LAUNCHER), "prepare", self.image, self.code_sha,
                self.build_id, str(request_path),
            ))
            self._record_call(self._path("prepare"), label="prepare", call=call)
            if call.returncode == 0:
                try:
                    result = validate_prepare_result(
                        _parse_json(call.stdout, label="prepare stdout"),
                        run_id=self.run_id, reconciliation=False,
                    )
                except DiscoveryMatrixFinisherError:
                    result = None

        if result is None:
            attempt_root = self._path("prepare/reconcile-attempts")
            for attempt in range(
                self._attempt_start(attempt_root), self.collect_polls
            ):
                call = self._wrapper_call((
                    str(LAUNCHER), "reconcile-prepare", self.image,
                    self.code_sha, self.build_id, str(request_path),
                ))
                self._record_call(
                    attempt_root / f"{attempt:03d}",
                    label="reconcile-prepare", call=call,
                )
                if call.returncode == 0:
                    try:
                        result = validate_prepare_result(
                            _parse_json(call.stdout, label="prepare reconciliation"),
                            run_id=self.run_id, reconciliation=True,
                        )
                    except DiscoveryMatrixFinisherError:
                        result = None
                    if result is not None:
                        break
                if attempt + 1 < self.collect_polls:
                    self.sleeper(self.poll_interval_seconds)
        if result is None:
            failure = {
                "schema_version": "corpus-r6-paid-source-discovery-matrix-host-failure/v1",
                "run_id": self.run_id, "phase": "prepare",
                "category": "consumed-intent-ambiguous-unresolved",
                "intent_sha256": canonical_sha256(intent),
                "automatic_republication": False, "complete": True,
            }
            _publish_once(self._path("prepare/failure.json"), canonical_bytes(failure))
            _fail("prepare intent is consumed and unresolved; never republish")
        _publish_once(result_path, canonical_bytes(result))
        _publish_once(identity_path, canonical_bytes(result["manifest_identity"]))
        return result

    def _install(self) -> dict[str, object]:
        directory = self._path("install")
        receipt_path = directory / "receipt.json"
        intent_path = directory / "intent.json"
        fresh = not intent_path.exists()
        if receipt_path.exists() and fresh:
            _fail("persisted install receipt lacks its consumed intent")
        if fresh:
            job_before, latest = self._job_latest()
            metadata = _mapping(job_before.get("metadata"), label="job metadata")
            generation = metadata.get("generation")
            if type(generation) is not int or generation <= 0:
                _fail("preinstall job generation differs")
            predecessor = self._describe_execution(latest)
            if predecessor is None:
                _fail("preinstall latest execution is unavailable")
            _, latest_uid = _terminal_predecessor(predecessor, expected_name=latest)
            before = {
                "name": latest, "uid": latest_uid, "job_generation": generation,
                "provider_sha256": canonical_sha256(job_before),
            }
            _publish_once(directory / "provider-before.json", canonical_bytes(before))
        else:
            before = _read_canonical(
                directory / "provider-before.json", label="persisted preinstall provider"
            )
            if (
                set(before) != {
                    "name", "uid", "job_generation", "provider_sha256",
                }
                or type(before.get("name")) is not str
                or _EXECUTION.fullmatch(str(before["name"])) is None
                or type(before.get("uid")) is not str
                or _UUID.fullmatch(str(before["uid"])) is None
                or type(before.get("job_generation")) is not int
                or int(before["job_generation"]) <= 0
                or type(before.get("provider_sha256")) is not str
                or _SHA.fullmatch(str(before["provider_sha256"])) is None
            ):
                _fail("persisted preinstall provider differs")
        intent = {
            "schema_version": "corpus-r6-paid-source-discovery-matrix-host-install-intent/v1",
            "run_id": self.run_id, "code_sha": self.code_sha,
            "cloud_build_id": self.build_id, "provider_resolved_image": self.image,
            "provider_latest_before": {
                "name": before["name"], "uid": before["uid"],
                "job_generation": before["job_generation"],
            },
            "automatic_reinstall": False,
            "ambiguous_return_recovery": "exact-job-generation-and-template-only",
            "complete": True,
        }
        if not _publish_once(intent_path, canonical_bytes(intent)) and fresh:
            _fail("install intent create race")
        if receipt_path.exists():
            item = _read_canonical(receipt_path, label="persisted install receipt")
            if (
                set(item) != {
                    "schema_version", "run_id", "code_sha", "cloud_build_id",
                    "provider_resolved_image", "job_name", "job_uid",
                    "job_generation", "previous_latest_execution",
                    "provider_before_sha256", "intent_sha256",
                    "provider_sha256", "default_off", "automatic_reinstall",
                    "complete",
                }
                or item.get("schema_version")
                != "corpus-r6-paid-source-discovery-matrix-host-install/v1"
                or item.get("run_id") != self.run_id
                or item.get("code_sha") != self.code_sha
                or item.get("cloud_build_id") != self.build_id
                or item.get("provider_resolved_image") != self.image
                or item.get("job_name") != JOB or item.get("job_uid") != JOB_UID
                or type(item.get("job_generation")) is not int
                or int(item["job_generation"]) <= int(before["job_generation"])
                or item.get("previous_latest_execution") != before["name"]
                or item.get("provider_before_sha256")
                != before["provider_sha256"]
                or item.get("intent_sha256") != canonical_sha256(intent)
                or type(item.get("provider_sha256")) is not str
                or _SHA.fullmatch(str(item["provider_sha256"])) is None
                or item.get("default_off") is not True
                or item.get("automatic_reinstall") is not False
                or item.get("complete") is not True
            ):
                _fail("persisted install receipt differs")
            return item
        if fresh:
            verify_launcher_registry_lane(run_id=self.run_id, environment=os.environ)
            call = self._wrapper_call((
                str(LAUNCHER), "install", self.image, self.code_sha, self.build_id,
            ))
            self._record_call(directory, label="install", call=call)

        installed: dict[str, object] | None = None
        for attempt in range(self.reconcile_polls):
            observed = self._describe_job()
            if observed is not None:
                try:
                    installed = validate_installed_job(
                        observed, code_sha=self.code_sha, build_id=self.build_id,
                        image=self.image, previous_latest=str(before["name"]),
                        minimum_generation=int(before["job_generation"]),
                    )
                except DiscoveryMatrixFinisherError:
                    installed = None
                if installed is not None:
                    break
            if attempt + 1 < self.reconcile_polls:
                self.sleeper(self.poll_interval_seconds)
        if installed is None:
            failure = {
                "schema_version": "corpus-r6-paid-source-discovery-matrix-host-failure/v1",
                "run_id": self.run_id, "phase": "install",
                "category": "consumed-install-intent-ambiguous-unresolved",
                "intent_sha256": canonical_sha256(intent),
                "automatic_reinstall": False, "complete": True,
            }
            _publish_once(directory / "failure.json", canonical_bytes(failure))
            _fail("install intent is consumed and unresolved; never reinstall")
        metadata = _mapping(installed["metadata"], label="installed metadata")
        body = {
            "schema_version": "corpus-r6-paid-source-discovery-matrix-host-install/v1",
            "run_id": self.run_id, "code_sha": self.code_sha,
            "cloud_build_id": self.build_id, "provider_resolved_image": self.image,
            "job_name": JOB, "job_uid": JOB_UID,
            "job_generation": metadata["generation"],
            "previous_latest_execution": before["name"],
            "provider_before_sha256": before["provider_sha256"],
            "intent_sha256": canonical_sha256(intent),
            "provider_sha256": canonical_sha256(installed),
            "default_off": True, "automatic_reinstall": False, "complete": True,
        }
        _publish_once(receipt_path, canonical_bytes(body))
        return body

    def _phase_payload_path(
        self, phase: str, prior: Mapping[str, Mapping[str, object]],
    ) -> Path:
        if phase in {"task0", "task"}:
            return self._path("manifest-identity.json")
        if phase == "reopen-task":
            return self._path("terminal-identity.json")
        _fail("discovery-matrix phase differs")

    def _launcher_args(
        self,
        phase: str,
        prior: Mapping[str, Mapping[str, object]],
        payload_path: Path,
    ) -> tuple[str, ...]:
        prefix = (str(LAUNCHER), phase, self.image, self.code_sha, self.build_id)
        if phase == "task0":
            return (*prefix, str(payload_path))
        if phase == "task":
            return (*prefix, str(payload_path), str(prior["task0"]["execution_name"]))
        if phase == "reopen-task":
            return (*prefix, str(payload_path), str(prior["task"]["execution_name"]))
        _fail("discovery-matrix phase differs")

    def _wait_for_latest_change(
        self,
        *,
        phase: str,
        before_name: str,
        expected_name: str | None,
        payload: bytes,
        task0_execution: str,
        expected_uid: str | None = None,
    ) -> tuple[str, str, dict[str, object]] | None:
        for index in range(self.reconcile_polls):
            try:
                _, latest = self._job_latest()
            except DiscoveryMatrixFinisherError:
                latest = before_name
            if expected_name is not None and latest != expected_name:
                if latest != before_name:
                    _fail(f"{phase} provider latest changed unexpectedly")
            elif latest != before_name:
                observed = self._describe_execution(latest)
                if observed is not None:
                    provider, _ = validate_provider_execution(
                        observed, mode=phase, execution_name=latest,
                        execution_uid=expected_uid, code_sha=self.code_sha,
                        build_id=self.build_id, image=self.image, payload=payload,
                        task0_execution=task0_execution,
                    )
                    uid = str(_mapping(provider["metadata"], label="execution metadata")["uid"])
                    return latest, uid, provider
            if index + 1 < self.reconcile_polls:
                self.sleeper(self.poll_interval_seconds)
        return None

    def _load_launch(self, phase: str) -> dict[str, object] | None:
        path = self._phase_path(phase, "launch.json")
        if not path.exists():
            return None
        item = _read_canonical(path, label=f"persisted {phase} launch")
        execution = _mapping(item.get("execution"), label=f"persisted {phase} execution")
        wrapper_stdout = item.get("wrapper_stdout")
        if wrapper_stdout is not None:
            wrapper_stdout = _mapping(
                wrapper_stdout, label=f"persisted {phase} wrapper stdout"
            )
        if (
            set(item) != {
                "schema_version", "run_id", "phase", "code_sha",
                "cloud_build_id", "provider_resolved_image", "execution",
                "request_sha256", "intent_sha256",
                "provider_attribution_method",
                "provider_sha256_at_attribution", "wrapper_stdout",
                "automatic_relaunch", "complete",
            }
            or item.get("schema_version")
            != "corpus-r6-paid-source-discovery-matrix-host-launch/v1"
            or item.get("run_id") != self.run_id or item.get("phase") != phase
            or item.get("code_sha") != self.code_sha
            or item.get("cloud_build_id") != self.build_id
            or item.get("provider_resolved_image") != self.image
            or type(execution.get("name")) is not str
            or _EXECUTION.fullmatch(str(execution["name"])) is None
            or type(execution.get("uid")) is not str
            or _UUID.fullmatch(str(execution["uid"])) is None
            or set(execution) != {"name", "uid", "task_count"}
            or execution.get("task_count")
            != (1 if phase == "task0" else freeze.TASK_COUNT)
            or type(item.get("request_sha256")) is not str
            or _SHA.fullmatch(str(item["request_sha256"])) is None
            or type(item.get("intent_sha256")) is not str
            or _SHA.fullmatch(str(item["intent_sha256"])) is None
            or item.get("provider_attribution_method") not in ATTRIBUTION_METHODS
            or type(item.get("provider_sha256_at_attribution")) is not str
            or _SHA.fullmatch(str(item["provider_sha256_at_attribution"])) is None
            or (
                wrapper_stdout is not None
                and (
                    set(wrapper_stdout)
                    != {"execution_name", "stdout_sha256", "complete"}
                    or wrapper_stdout.get("execution_name") != execution["name"]
                    or type(wrapper_stdout.get("stdout_sha256")) is not str
                    or _SHA.fullmatch(str(wrapper_stdout["stdout_sha256"])) is None
                    or wrapper_stdout.get("complete") is not True
                )
            )
            or item.get("automatic_relaunch") is not False
            or item.get("complete") is not True
        ):
            _fail(f"persisted {phase} launch differs")
        return item

    def _launch_or_recover(
        self,
        *,
        phase: str,
        prior: Mapping[str, Mapping[str, object]],
        payload_path: Path,
    ) -> dict[str, object]:
        phase_dir = self._phase_path(phase, "request.json").parent
        if payload_path.is_symlink() or not payload_path.is_file():
            _fail(f"{phase} payload path differs")
        payload = payload_path.read_bytes()
        _payload_identity(payload)
        task0_execution = (
            str(prior["task0"]["execution_name"]) if phase == "task" else "none"
        )
        request = {
            "schema_version": "corpus-r6-paid-source-discovery-matrix-host-phase-request/v1",
            "run_id": self.run_id, "phase": phase,
            "code_sha": self.code_sha, "cloud_build_id": self.build_id,
            "provider_resolved_image": self.image,
            "payload_identity": _payload_identity(payload),
            "payload_file_sha256": sha256(payload).hexdigest(),
            "payload_file_bytes": len(payload),
            "task_count": 1 if phase == "task0" else freeze.TASK_COUNT,
            "bound_task0_execution": task0_execution,
            "outcomes_allowed": False, "complete": True,
        }
        _publish_once(phase_dir / "request.json", canonical_bytes(request))
        persisted = self._load_launch(phase)
        intent_path = phase_dir / "launch-intent.json"
        fresh = not intent_path.exists()
        recovery = self.recovery_executions.get(phase)
        if persisted is not None and fresh:
            _fail(f"persisted {phase} launch lacks its consumed intent")
        if fresh and recovery is not None:
            _fail(
                f"{phase} recovery is forbidden before a launch intent is consumed"
            )
        if fresh:
            _, before_name = self._job_latest()
            before_provider = self._describe_execution(before_name)
            if before_provider is None:
                _fail(f"{phase} prelaunch latest execution is unavailable")
            expected_previous = None
            if phase == "task":
                expected_previous = str(prior["task0"]["execution_name"])
            elif phase == "reopen-task":
                expected_previous = str(prior["task"]["execution_name"])
            before_name, before_uid = _terminal_predecessor(
                before_provider, expected_name=expected_previous or before_name,
            )
            if expected_previous is not None:
                prior_phase = "task0" if phase == "task" else "task"
                if before_uid != prior[prior_phase].get("execution_uid"):
                    _fail(f"{phase} provider predecessor UID differs")
            before = {
                "name": before_name, "uid": before_uid,
                "provider_sha256": canonical_sha256(before_provider),
            }
            _publish_once(phase_dir / "provider-before.json", canonical_bytes(before))
        else:
            before = _read_canonical(
                phase_dir / "provider-before.json", label=f"persisted {phase} provider-before"
            )
            if (
                set(before) != {"name", "uid", "provider_sha256"}
                or type(before.get("name")) is not str
                or _EXECUTION.fullmatch(str(before["name"])) is None
                or type(before.get("uid")) is not str
                or _UUID.fullmatch(str(before["uid"])) is None
                or type(before.get("provider_sha256")) is not str
                or _SHA.fullmatch(str(before["provider_sha256"])) is None
            ):
                _fail(f"persisted {phase} provider-before differs")
            expected_prior: Mapping[str, object] | None = None
            if phase == "task":
                expected_prior = prior.get("task0")
            elif phase == "reopen-task":
                expected_prior = prior.get("task")
            if phase in {"task", "reopen-task"}:
                if expected_prior is None or (
                    before["name"] != expected_prior.get("execution_name")
                    or before["uid"] != expected_prior.get("execution_uid")
                ):
                    _fail(f"persisted {phase} provider predecessor lineage differs")
        intent = {
            "schema_version": "corpus-r6-paid-source-discovery-matrix-host-launch-intent/v1",
            "run_id": self.run_id, "phase": phase,
            "request_sha256": canonical_sha256(request),
            "provider_latest_before": {"name": before["name"], "uid": before["uid"]},
            "automatic_relaunch": False,
            "ambiguous_return_recovery": "exact-provider-latest-name-uid-envelope-only",
            "complete": True,
        }
        if not _publish_once(intent_path, canonical_bytes(intent)) and fresh:
            _fail(f"{phase} launch intent create race")
        attribution_path = phase_dir / "provider-attribution.json"
        if persisted is not None:
            attribution = _read_canonical(
                attribution_path, label=f"persisted {phase} provider attribution"
            )
            attributed_execution = _mapping(
                attribution.get("execution"),
                label=f"persisted {phase} attribution execution",
            )
            launched_execution = _mapping(
                persisted["execution"], label=f"persisted {phase} launch execution"
            )
            if (
                persisted.get("request_sha256") != canonical_sha256(request)
                or persisted.get("intent_sha256") != canonical_sha256(intent)
                or set(attribution) != {
                    "schema_version", "run_id", "phase", "execution",
                    "request_sha256", "intent_sha256", "method",
                    "provider_sha256", "automatic_relaunch", "complete",
                }
                or attribution.get("schema_version")
                != "corpus-r6-paid-source-discovery-matrix-host-provider-attribution/v1"
                or attribution.get("run_id") != self.run_id
                or attribution.get("phase") != phase
                or attributed_execution != {
                    "name": launched_execution["name"],
                    "uid": launched_execution["uid"],
                }
                or attribution.get("request_sha256") != canonical_sha256(request)
                or attribution.get("intent_sha256") != canonical_sha256(intent)
                or attribution.get("method")
                != persisted.get("provider_attribution_method")
                or attribution.get("provider_sha256")
                != persisted.get("provider_sha256_at_attribution")
                or attribution.get("automatic_relaunch") is not False
                or attribution.get("complete") is not True
                or (
                    recovery is not None
                    and recovery
                    != (
                        str(launched_execution["name"]),
                        str(launched_execution["uid"]),
                    )
                )
            ):
                _fail(f"persisted {phase} launch lineage differs")
            return persisted

        expected_name: str | None = None
        controller_stdout: dict[str, object] | None = None
        resolved: tuple[str, str, dict[str, object]] | None = None
        retained_attribution: dict[str, object] | None = None
        method = ""
        if fresh and attribution_path.exists():
            _fail(f"{phase} provider attribution exists before its intent")
        if attribution_path.exists():
            attribution = _read_canonical(
                attribution_path, label=f"persisted {phase} provider attribution"
            )
            execution = _mapping(
                attribution.get("execution"), label=f"persisted {phase} attribution execution"
            )
            if (
                set(attribution) != {
                    "schema_version", "run_id", "phase", "execution",
                    "request_sha256", "intent_sha256", "method",
                    "provider_sha256", "automatic_relaunch", "complete",
                }
                or set(execution) != {"name", "uid"}
                or attribution.get("schema_version")
                != "corpus-r6-paid-source-discovery-matrix-host-provider-attribution/v1"
                or attribution.get("run_id") != self.run_id
                or attribution.get("phase") != phase
                or attribution.get("intent_sha256") != canonical_sha256(intent)
                or attribution.get("request_sha256") != canonical_sha256(request)
                or type(execution.get("name")) is not str
                or _EXECUTION.fullmatch(str(execution["name"])) is None
                or type(execution.get("uid")) is not str
                or _UUID.fullmatch(str(execution["uid"])) is None
                or attribution.get("method") not in ATTRIBUTION_METHODS
                or type(attribution.get("provider_sha256")) is not str
                or _SHA.fullmatch(str(attribution["provider_sha256"])) is None
                or attribution.get("automatic_relaunch") is not False
                or attribution.get("complete") is not True
            ):
                _fail(f"persisted {phase} provider attribution differs")
            observed = self._describe_execution(str(execution["name"]))
            if observed is None:
                _fail(f"persisted {phase} attributed execution is unavailable")
            provider, _ = validate_provider_execution(
                observed, mode=phase, execution_name=str(execution["name"]),
                execution_uid=str(execution["uid"]), code_sha=self.code_sha,
                build_id=self.build_id, image=self.image, payload=payload,
                task0_execution=task0_execution,
            )
            _, latest = self._job_latest()
            if latest != execution["name"] or latest == before["name"]:
                _fail(f"persisted {phase} attribution is not the changed latest")
            resolved = (str(execution["name"]), str(execution["uid"]), provider)
            retained_attribution = attribution
            method = str(attribution["method"])
        elif fresh:
            verify_launcher_registry_lane(run_id=self.run_id, environment=os.environ)
            call = self._wrapper_call(
                self._launcher_args(phase, prior, payload_path)
            )
            self._record_call(phase_dir, label=phase, call=call)
            if call.returncode == 0:
                try:
                    text = call.stdout.decode("ascii").strip()
                except UnicodeError:
                    text = ""
                if _EXECUTION.fullmatch(text) is not None:
                    expected_name = text
                    controller_stdout = {
                        "execution_name": text,
                        "stdout_sha256": sha256(call.stdout).hexdigest(),
                        "complete": True,
                    }
        elif recovery is not None:
            observed = self._describe_execution(recovery[0])
            if observed is None:
                _fail(f"{phase} exact recovery execution is unavailable")
            provider, _ = validate_provider_execution(
                observed, mode=phase, execution_name=recovery[0],
                execution_uid=recovery[1], code_sha=self.code_sha,
                build_id=self.build_id, image=self.image, payload=payload,
                task0_execution=task0_execution,
            )
            # Manual recovery is exact-name/UID only, but it must still be the
            # changed latest execution attributable to this consumed intent.
            _, latest = self._job_latest()
            if latest != recovery[0] or latest == before["name"]:
                _fail(f"{phase} exact recovery is not the changed provider latest")
            resolved = (recovery[0], recovery[1], provider)
            method = "operator-supplied-exact-name-and-uid"
        if resolved is None and not fresh and recovery is None:
            resolved = self._wait_for_latest_change(
                phase=phase, before_name=str(before["name"]), expected_name=None,
                payload=payload, task0_execution=task0_execution,
            )
            method = "provider-latest-after-consumed-intent"
        elif resolved is None and fresh:
            resolved = self._wait_for_latest_change(
                phase=phase, before_name=str(before["name"]),
                expected_name=expected_name, payload=payload,
                task0_execution=task0_execution,
            )
            method = (
                "wrapper-response-and-provider-latest"
                if expected_name is not None
                else "provider-latest-after-ambiguous-wrapper-return"
            )
        if resolved is None:
            failure = {
                "schema_version": "corpus-r6-paid-source-discovery-matrix-host-failure/v1",
                "run_id": self.run_id, "phase": phase,
                "category": "consumed-launch-intent-ambiguous-unresolved",
                "intent_sha256": canonical_sha256(intent),
                "automatic_relaunch": False,
                "manual_recovery_requires_exact_name_and_uid": True,
                "complete": True,
            }
            _publish_once(phase_dir / "failure.json", canonical_bytes(failure))
            _fail(f"{phase} intent is consumed and unresolved; never relaunch")
        name, uid, provider = resolved
        if retained_attribution is None:
            attribution = {
                "schema_version": "corpus-r6-paid-source-discovery-matrix-host-provider-attribution/v1",
                "run_id": self.run_id, "phase": phase,
                "execution": {"name": name, "uid": uid},
                "request_sha256": canonical_sha256(request),
                "intent_sha256": canonical_sha256(intent),
                "method": method,
                "provider_sha256": canonical_sha256(provider),
                "automatic_relaunch": False, "complete": True,
            }
            _publish_once(attribution_path, canonical_bytes(attribution))
        else:
            attribution = retained_attribution
        launch = {
            "schema_version": "corpus-r6-paid-source-discovery-matrix-host-launch/v1",
            "run_id": self.run_id, "phase": phase,
            "code_sha": self.code_sha, "cloud_build_id": self.build_id,
            "provider_resolved_image": self.image,
            "execution": {
                "name": name, "uid": uid,
                "task_count": 1 if phase == "task0" else freeze.TASK_COUNT,
            },
            "request_sha256": canonical_sha256(request),
            "intent_sha256": canonical_sha256(intent),
            "provider_attribution_method": method,
            "provider_sha256_at_attribution": attribution["provider_sha256"],
            "wrapper_stdout": controller_stdout,
            "automatic_relaunch": False, "complete": True,
        }
        _publish_once(phase_dir / "launch.json", canonical_bytes(launch))
        return launch

    def _poll_terminal(
        self,
        *,
        phase: str,
        launch: Mapping[str, object],
        payload: bytes,
        task0_execution: str,
    ) -> dict[str, object]:
        terminal_path = self._phase_path(phase, "provider-terminal.json")
        execution = _mapping(launch.get("execution"), label=f"{phase} launch execution")
        name = str(execution["name"])
        uid = str(execution["uid"])
        if terminal_path.exists():
            provider, state = validate_provider_execution(
                _read_canonical(terminal_path, label=f"persisted {phase} terminal"),
                mode=phase, execution_name=name, execution_uid=uid,
                code_sha=self.code_sha, build_id=self.build_id, image=self.image,
                payload=payload, task0_execution=task0_execution,
            )
            if state != "True":
                _fail(f"persisted {phase} provider terminal is not success")
            return provider
        polls = self._phase_path(phase, "provider-polls")
        existing = sorted(polls.glob("*.json")) if polls.is_dir() else []
        if [path.name for path in existing] != [f"{index:04d}.json" for index in range(len(existing))]:
            _fail(f"persisted {phase} provider poll census differs")
        for index, path in enumerate(existing):
            provider, state = validate_provider_execution(
                _read_canonical(path, label=f"persisted {phase} provider poll"),
                mode=phase, execution_name=name, execution_uid=uid,
                code_sha=self.code_sha, build_id=self.build_id,
                image=self.image, payload=payload,
                task0_execution=task0_execution,
            )
            if state == "False":
                _fail(f"persisted {phase} provider poll is terminal failure")
            if state == "True":
                if index != len(existing) - 1:
                    _fail(f"persisted {phase} polls continue after terminal success")
                _publish_once(terminal_path, canonical_bytes(provider))
                return provider
        index = len(existing)
        attempts = 0
        while attempts < self.max_polls and index < self.max_polls:
            attempts += 1
            observed = self._describe_execution(name)
            if observed is not None:
                provider, state = validate_provider_execution(
                    observed, mode=phase, execution_name=name, execution_uid=uid,
                    code_sha=self.code_sha, build_id=self.build_id,
                    image=self.image, payload=payload,
                    task0_execution=task0_execution,
                )
                _publish_once(
                    polls / f"{index:04d}.json", canonical_bytes(provider)
                )
                index += 1
                if state == "True":
                    _publish_once(terminal_path, canonical_bytes(provider))
                    return provider
                if state == "False":
                    _publish_once(
                        self._phase_path(phase, "provider-failure.json"),
                        canonical_bytes(provider),
                    )
                    _fail(f"{phase} execution failed or was cancelled")
            if attempts < self.max_polls and index < self.max_polls:
                self.sleeper(self.poll_interval_seconds)
        _fail(f"{phase} exact-name provider polling exhausted")

    def _phase(
        self, phase: str, prior: Mapping[str, Mapping[str, object]],
    ) -> dict[str, object]:
        validate_exact_repository(code_sha=self.code_sha, runner=self.runner)
        verify_launcher_registry_lane(run_id=self.run_id, environment=os.environ)
        payload_path = self._phase_payload_path(phase, prior)
        launch = self._launch_or_recover(
            phase=phase, prior=prior, payload_path=payload_path,
        )
        payload = payload_path.read_bytes()
        task0_execution = (
            str(prior["task0"]["execution_name"]) if phase == "task" else "none"
        )
        provider = self._poll_terminal(
            phase=phase, launch=launch, payload=payload,
            task0_execution=task0_execution,
        )
        execution = _mapping(launch["execution"], label=f"{phase} execution")
        return {
            "execution_name": execution["name"],
            "execution_uid": execution["uid"],
            "provider_terminal_sha256": canonical_sha256(provider),
        }

    def _collect(
        self,
        *,
        reopen: bool,
        execution: Mapping[str, object],
    ) -> dict[str, object]:
        phase = "reopen-collect" if reopen else "collect"
        directory = self._path(phase)
        result_path = directory / "result.json"
        identity_path = self._path(
            "reopen-terminal-identity.json" if reopen else "terminal-identity.json"
        )
        payload_path = self._path(
            "terminal-identity.json" if reopen else "manifest-identity.json"
        )
        payload = payload_path.read_bytes()
        payload_identity = _payload_identity(payload)
        name = str(execution["execution_name"])
        uid = str(execution["execution_uid"])
        request = {
            "schema_version": "corpus-r6-paid-source-discovery-matrix-host-collect-request/v1",
            "run_id": self.run_id, "phase": phase,
            "execution": {"name": name, "uid": uid},
            "payload_identity": payload_identity,
            "payload_file_sha256": sha256(payload).hexdigest(),
            "target_uri": (
                f"{freeze.OUTPUT_PREFIX}/{self.run_id}/"
                + ("reopen-terminal.json" if reopen else "terminal.json")
            ),
            "automatic_republication": False, "complete": True,
        }
        _publish_once(directory / "request.json", canonical_bytes(request))
        intent = {
            "schema_version": "corpus-r6-paid-source-discovery-matrix-host-collect-intent/v1",
            "run_id": self.run_id, "phase": phase,
            "request_sha256": canonical_sha256(request),
            "target_uri": request["target_uri"],
            "automatic_republication": False,
            "ambiguous_return_recovery": "exact-known-uri-read-only",
            "complete": True,
        }
        intent_path = directory / "intent.json"
        if result_path.exists() != identity_path.exists():
            _fail(f"persisted {phase} result/identity census differs")
        if result_path.exists():
            if _read_canonical(
                intent_path, label=f"persisted {phase} intent"
            ) != intent:
                _fail(f"persisted {phase} intent differs")
            result = validate_collect_result(
                _read_canonical(result_path, label=f"persisted {phase} result"),
                run_id=self.run_id, reopen=reopen,
            )
            key = "reopen_terminal_identity" if reopen else "terminal_identity"
            if _read_canonical(identity_path, label=f"persisted {phase} identity") != result[key]:
                _fail(f"persisted {phase} identity differs")
            return result
        fresh = not intent_path.exists()
        if not _publish_once(intent_path, canonical_bytes(intent)) and fresh:
            _fail(f"{phase} intent create race")
        result: dict[str, object] | None = None
        if fresh:
            verify_launcher_registry_lane(run_id=self.run_id, environment=os.environ)
            call = self._wrapper_call((
                str(LAUNCHER), phase, self.image, self.code_sha, self.build_id,
                str(payload_path), name,
            ))
            self._record_call(directory, label=phase, call=call)
            if call.returncode == 0:
                try:
                    result = validate_collect_result(
                        _parse_json(call.stdout, label=f"{phase} stdout"),
                        run_id=self.run_id, reopen=reopen, reconciliation=False,
                    )
                except DiscoveryMatrixFinisherError:
                    result = None
        if result is None:
            reconcile_action = "reconcile-" + phase
            attempt_root = self._path(f"{phase}/reconcile-attempts")
            for attempt in range(
                self._attempt_start(attempt_root), self.collect_polls
            ):
                call = self._wrapper_call((
                    str(LAUNCHER), reconcile_action, self.image, self.code_sha,
                    self.build_id, str(payload_path), name,
                ))
                self._record_call(
                    attempt_root / f"{attempt:03d}",
                    label=reconcile_action, call=call,
                )
                if call.returncode == 0:
                    try:
                        result = validate_collect_result(
                            _parse_json(call.stdout, label=f"{phase} reconciliation"),
                            run_id=self.run_id, reopen=reopen, reconciliation=True,
                        )
                    except DiscoveryMatrixFinisherError:
                        result = None
                    if result is not None:
                        break
                if attempt + 1 < self.collect_polls:
                    self.sleeper(self.poll_interval_seconds)
        if result is None:
            failure = {
                "schema_version": "corpus-r6-paid-source-discovery-matrix-host-failure/v1",
                "run_id": self.run_id, "phase": phase,
                "category": "consumed-collect-intent-ambiguous-unresolved",
                "intent_sha256": canonical_sha256(intent),
                "automatic_republication": False, "complete": True,
            }
            _publish_once(directory / "failure.json", canonical_bytes(failure))
            _fail(f"{phase} intent is consumed and unresolved; never republish")
        key = "reopen_terminal_identity" if reopen else "terminal_identity"
        _publish_once(result_path, canonical_bytes(result))
        _publish_once(identity_path, canonical_bytes(result[key]))
        return result

    def _validate_chain_terminal(self, value: object) -> dict[str, object]:
        item = _mapping(value, label="persisted chain terminal")
        order = [
            "install", "task0", "task", "collect", "reopen-task",
            "reopen-collect",
        ]
        names = _mapping(
            item.get("phase_execution_names"), label="chain execution names"
        )
        uids = _mapping(
            item.get("phase_execution_uids"), label="chain execution UIDs"
        )
        provider_hashes = _mapping(
            item.get("phase_provider_terminal_sha256"),
            label="chain provider terminal hashes",
        )
        manifest_identity = _identity(
            item.get("manifest_identity"), label="chain manifest identity"
        )
        original_identity = _identity(
            item.get("discovery_matrix_freeze_terminal_identity"),
            label="chain original terminal identity",
        )
        reopen_identity = _identity(
            item.get("independent_reopen_terminal_identity"),
            label="chain independent reopen identity",
        )
        if (
            set(item) != {
                "schema_version", "run_id", "code_sha", "cloud_build_id",
                "provider_resolved_image", "manifest_identity", "phase_order",
                "phase_execution_names", "phase_execution_uids",
                "phase_provider_terminal_sha256", "install_receipt_sha256",
                "prepare_result_sha256", "collect_result_sha256",
                "reopen_collect_result_sha256",
                "discovery_matrix_freeze_terminal_identity",
                "independent_reopen_terminal_identity",
                "downstream_consumes_original_terminal_identity",
                "independent_reopen_required_before_downstream",
                "one_continuous_production_registry_lease",
                "automatic_relaunch", "uses_realized_outcomes", "complete",
            }
            or item.get("schema_version")
            != "corpus-r6-paid-source-discovery-matrix-host-terminal/v1"
            or item.get("run_id") != self.run_id
            or item.get("code_sha") != self.code_sha
            or item.get("cloud_build_id") != self.build_id
            or item.get("provider_resolved_image") != self.image
            or item.get("phase_order") != order
            or set(names) != set(PHASES) or set(uids) != set(PHASES)
            or set(provider_hashes) != set(PHASES)
            or any(
                type(names[phase]) is not str
                or _EXECUTION.fullmatch(str(names[phase])) is None
                or type(uids[phase]) is not str
                or _UUID.fullmatch(str(uids[phase])) is None
                or type(provider_hashes[phase]) is not str
                or _SHA.fullmatch(str(provider_hashes[phase])) is None
                for phase in PHASES
            )
            or len(set(names.values())) != len(PHASES)
            or len(set(uids.values())) != len(PHASES)
            or any(
                type(item.get(key)) is not str
                or _SHA.fullmatch(str(item[key])) is None
                for key in (
                    "install_receipt_sha256", "prepare_result_sha256",
                    "collect_result_sha256", "reopen_collect_result_sha256",
                )
            )
            or original_identity["uri"]
            != f"{freeze.OUTPUT_PREFIX}/{self.run_id}/terminal.json"
            or reopen_identity["uri"]
            != f"{freeze.OUTPUT_PREFIX}/{self.run_id}/reopen-terminal.json"
            or original_identity["uri"] == reopen_identity["uri"]
            or item.get("downstream_consumes_original_terminal_identity") is not True
            or item.get("independent_reopen_required_before_downstream") is not True
            or item.get("one_continuous_production_registry_lease") is not True
            or item.get("automatic_relaunch") is not False
            or item.get("uses_realized_outcomes") is not False
            or item.get("complete") is not True
        ):
            _fail("persisted discovery-matrix chain terminal differs")

        required = [
            self._path("prepare/result.json"),
            self._path("prepare/intent.json"),
            self._path("manifest-identity.json"),
            self._path("install/receipt.json"),
            self._path("collect/result.json"),
            self._path("collect/intent.json"),
            self._path("terminal-identity.json"),
            self._path("reopen-collect/result.json"),
            self._path("reopen-collect/intent.json"),
            self._path("reopen-terminal-identity.json"),
        ]
        if any(not path.is_file() or path.is_symlink() for path in required):
            _fail("persisted chain terminal local lineage is incomplete")
        prepare = self.prepare()
        install = self._install()
        collect = self._collect(
            reopen=False,
            execution={
                "execution_name": names["task"],
                "execution_uid": uids["task"],
            },
        )
        reopen_collect = self._collect(
            reopen=True,
            execution={
                "execution_name": names["reopen-task"],
                "execution_uid": uids["reopen-task"],
            },
        )
        if (
            prepare["manifest_identity"] != manifest_identity
            or _read_canonical(
                self._path("manifest-identity.json"),
                label="chain retained manifest identity",
            ) != manifest_identity
            or collect["terminal_identity"] != original_identity
            or reopen_collect["reopen_terminal_identity"] != reopen_identity
            or item["prepare_result_sha256"] != canonical_sha256(prepare)
            or item["install_receipt_sha256"] != canonical_sha256(install)
            or item["collect_result_sha256"] != canonical_sha256(collect)
            or item["reopen_collect_result_sha256"]
            != canonical_sha256(reopen_collect)
        ):
            _fail("persisted chain terminal receipt lineage differs")
        retained_phases: dict[str, dict[str, object]] = {}
        for phase in PHASES:
            payload_path = self._phase_payload_path(phase, retained_phases)
            launch = self._launch_or_recover(
                phase=phase, prior=retained_phases, payload_path=payload_path,
            )
            execution = _mapping(
                launch["execution"], label=f"chain {phase} launch execution"
            )
            payload = payload_path.read_bytes()
            provider, state = validate_provider_execution(
                _read_canonical(
                    self._phase_path(phase, "provider-terminal.json"),
                    label=f"chain {phase} provider terminal",
                ),
                mode=phase, execution_name=str(names[phase]),
                execution_uid=str(uids[phase]), code_sha=self.code_sha,
                build_id=self.build_id, image=self.image, payload=payload,
                task0_execution=(str(names["task0"]) if phase == "task" else "none"),
            )
            if (
                execution["name"] != names[phase]
                or execution["uid"] != uids[phase]
                or state != "True"
                or canonical_sha256(provider) != provider_hashes[phase]
            ):
                _fail(f"persisted chain {phase} provider lineage differs")
            retained_phases[phase] = {
                "execution_name": execution["name"],
                "execution_uid": execution["uid"],
            }
        return item

    def chain(self) -> dict[str, object]:
        validate_exact_repository(code_sha=self.code_sha, runner=self.runner)
        verify_launcher_registry_lane(run_id=self.run_id, environment=os.environ)
        terminal_path = self._path("chain-terminal.json")
        if terminal_path.exists():
            return self._validate_chain_terminal(
                _read_canonical(terminal_path, label="persisted chain terminal")
            )
        self._build_receipt()
        if not (
            self._path("prepare/result.json").is_file()
            and self._path("manifest-identity.json").is_file()
        ):
            _fail("prepare must complete before acquiring the shared-job chain lease")
        prepare = self.prepare()
        install = self._install()
        phases: dict[str, dict[str, object]] = {}
        phases["task0"] = self._phase("task0", phases)
        phases["task"] = self._phase("task", phases)
        collected = self._collect(reopen=False, execution=phases["task"])
        phases["reopen-task"] = self._phase("reopen-task", phases)
        reopened = self._collect(
            reopen=True, execution=phases["reopen-task"],
        )
        original_identity = _identity(
            collected["terminal_identity"], label="original matrix terminal"
        )
        reopen_identity = _identity(
            reopened["reopen_terminal_identity"], label="independent reopen terminal"
        )
        if (
            original_identity["uri"] == reopen_identity["uri"]
            or _read_canonical(
                self._path("terminal-identity.json"),
                label="retained original terminal identity",
            )
            != original_identity
            or _read_canonical(
                self._path("reopen-terminal-identity.json"),
                label="retained reopen terminal identity",
            )
            != reopen_identity
        ):
            _fail("original/reopen terminal identity separation differs")
        names = [str(phases[phase]["execution_name"]) for phase in PHASES]
        if len(set(names)) != len(PHASES):
            _fail("discovery-matrix phase execution identities repeat")
        terminal = {
            "schema_version": "corpus-r6-paid-source-discovery-matrix-host-terminal/v1",
            "run_id": self.run_id, "code_sha": self.code_sha,
            "cloud_build_id": self.build_id,
            "provider_resolved_image": self.image,
            "manifest_identity": prepare["manifest_identity"],
            "phase_order": [
                "install", "task0", "task", "collect", "reopen-task",
                "reopen-collect",
            ],
            "phase_execution_names": {
                phase: phases[phase]["execution_name"] for phase in PHASES
            },
            "phase_execution_uids": {
                phase: phases[phase]["execution_uid"] for phase in PHASES
            },
            "phase_provider_terminal_sha256": {
                phase: phases[phase]["provider_terminal_sha256"]
                for phase in PHASES
            },
            "install_receipt_sha256": canonical_sha256(install),
            "prepare_result_sha256": canonical_sha256(prepare),
            "collect_result_sha256": canonical_sha256(collected),
            "reopen_collect_result_sha256": canonical_sha256(reopened),
            # This is the scientific input consumed downstream.
            "discovery_matrix_freeze_terminal_identity": original_identity,
            # This is proof of an independent full-body reopen, not a
            # substitute scientific input identity.
            "independent_reopen_terminal_identity": reopen_identity,
            "downstream_consumes_original_terminal_identity": True,
            "independent_reopen_required_before_downstream": True,
            "one_continuous_production_registry_lease": True,
            "automatic_relaunch": False,
            "uses_realized_outcomes": False,
            "complete": True,
        }
        terminal = self._validate_chain_terminal(terminal)
        verify_launcher_registry_lane(run_id=self.run_id, environment=os.environ)
        _publish_once(terminal_path, canonical_bytes(terminal))
        return terminal


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--prepare-request", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--poll-interval-seconds", type=int, default=30)
    parser.add_argument("--max-polls", type=int, default=2_880)
    parser.add_argument("--reconcile-polls", type=int, default=20)
    parser.add_argument("--collect-polls", type=int, default=20)
    parser.add_argument("--preflight-workers", type=int, default=8)
    for phase in PHASES:
        option = phase.replace("-", "_")
        parser.add_argument(f"--{phase}-execution", dest=f"{option}_execution", default="")
        parser.add_argument(
            f"--{phase}-execution-uid", dest=f"{option}_execution_uid", default=""
        )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation", default="")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("prepare")
    commands.add_parser("chain")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.execute or args.confirmation != CONFIRMATION:
        _fail(
            "discovery-matrix finisher is default-off; require --execute "
            f"--confirmation {CONFIRMATION}"
        )
    if _RUN_ID.fullmatch(args.run_id) is None:
        _fail("discovery-matrix run ID differs")
    request = _read_canonical(
        args.prepare_request.resolve(), label="prepare request"
    )
    run_dir = args.run_dir or RUN_STATE_ROOT / args.run_id
    retained = _validated_run_dir(run_dir, run_id=args.run_id)
    recovery: dict[str, tuple[str, str]] = {}
    for phase in PHASES:
        option = phase.replace("-", "_")
        name = getattr(args, f"{option}_execution")
        uid = getattr(args, f"{option}_execution_uid")
        if bool(name) != bool(uid):
            _fail(f"{phase} recovery requires exact execution name and UID")
        if name:
            recovery[phase] = (name, uid)
    if args.action == "chain":
        verify_launcher_registry_lane(run_id=args.run_id, environment=os.environ)
    lock_path = retained / "finisher.lock"
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DiscoveryMatrixFinisherError(
                "another discovery-matrix finisher owns the local run lock"
            ) from exc
        finisher = DiscoveryMatrixFinisher(
            run_id=args.run_id, code_sha=args.code_sha, build_id=args.build_id,
            image=args.image, run_dir=retained, prepare_request=request,
            runner=CommandRunner(), object_exists=make_object_exists(),
            poll_interval_seconds=args.poll_interval_seconds,
            max_polls=args.max_polls, reconcile_polls=args.reconcile_polls,
            collect_polls=args.collect_polls,
            preflight_workers=args.preflight_workers,
            recovery_executions=recovery,
        )
        result = finisher.prepare() if args.action == "prepare" else finisher.chain()
    sys.stdout.buffer.write(canonical_bytes(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DiscoveryMatrixFinisherError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


__all__ = [
    "CONFIRMATION", "CommandResult", "CommandRunner", "DiscoveryMatrixFinisher",
    "DiscoveryMatrixFinisherError", "PHASES", "canonical_bytes",
    "canonical_sha256", "output_uri_inventory", "validate_build_provider",
    "validate_collect_result", "validate_exact_repository",
    "validate_installed_job", "validate_prepare_request", "validate_prepare_result",
    "validate_provider_execution", "verify_launcher_registry_lane",
]
