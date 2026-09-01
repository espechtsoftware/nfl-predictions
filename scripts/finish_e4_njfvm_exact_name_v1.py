#!/usr/bin/env python3
"""Crash-closed continuation for the sole E4 grade-timeout recovery.

This host-only driver is intentionally narrower than the general E4 finisher.
It may observe only the frozen recovery execution named below.  After that
exact execution reaches terminal success it uses the reviewed recovery-aware
host launcher to collect the grade receipt, then uses the byte-pinned f2 source
clone to launch and collect the ordinary ``grade-reopen`` phase.

The driver never lists executions and has no code path that launches another
grade recovery.  It must run beneath ``scripts/launcher_registry.sh`` for the
complete lifetime of the chain.  The default invocation is inert.
"""

from __future__ import annotations

import argparse
import base64
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from types import ModuleType
from typing import Final


ROOT: Final = Path(__file__).resolve().parents[1]
HOST_LAUNCHER: Final = ROOT / "scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh"
EXACT_ROOT: Final = ROOT / ".build-contexts/e4-finisher-f2aad-exact-oupZof/source"
EXACT_LAUNCHER: Final = EXACT_ROOT / "scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh"
EXACT_FINISHER: Final = EXACT_ROOT / "scripts/finish_corpus_r6_broad_admission_tournament_v1.py"
RUN_DIR: Final = ROOT / ".tmp/e4-njfvm-exact-name-continuation-v1"

PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
JOB: Final = "atlas-cbc-32g-full-2023-w8-v1"
JOB_UID: Final = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
RECOVERY_EXECUTION: Final = f"{JOB}-njfvm"
RECOVERY_UID: Final = "202c982e-efbe-4700-b5ab-929845aa3701"
FAILED_EXECUTION: Final = f"{JOB}-bqkw5"
CODE_SHA: Final = "f2aad14e6bed0a2f0267e3a5f45c149173f9f1a4"
BUILD_ID: Final = "889a1f25-2d9c-41e9-802a-fcfb3b327375"
IMAGE: Final = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
    "sha256:d65aec970cb6c075124a767ae0082fe699bb7426289a2da96ea2a23f27f954d6"
)
IMAGE_DIGEST: Final = IMAGE.split("@", maxsplit=1)[1]
SERVICE_ACCOUNT: Final = "817589974517-compute@developer.gserviceaccount.com"
SOURCE_REPOSITORY: Final = "https://github.com/espechtsoftware/nfl-predictions.git"

HOST_LAUNCHER_SHA256: Final = "e5bde454568aeec4a075eb5c061a04cb0b0a6e7f3d9afbbae39d9001b3542c77"
EXACT_LAUNCHER_SHA256: Final = "f1c5f9f0c72ff6c61716623e09efdfd43ba8c0d4251d4e80dd026eeda2ab07a1"
EXACT_FINISHER_SHA256: Final = "0ce5b61063d8efb10dca201d5a8599a336aab429dacf15bec00df9ea04412491"
CONFIRMATION: Final = "I_UNDERSTAND_E4_NJFVM_EXACT_NAME_CONTINUATION_V1"
TARGET_PREFIXES: Final = [RECOVERY_EXECUTION, "e4-grade-reopen-from-njfvm"]

GRADE_REQUEST: Final = {
    "outcome_authority_identity": {
        "uri": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-catalog-wide-realized/"
            "20260829-score-sprint-c9f12ed7-catalog-outcomes-v1/completion.json"
        ),
        "generation": "1787987567275104",
        "sha256": "15852361756ef0fe76d3a299617ebc2c2531e6821a73f04c8f862bf7229f4df3",
        "bytes": 2521,
    },
    "terminal_identity": {
        "uri": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-broad-admission/"
            "20260831-fixed-budget-retention-f2aad14e-v5/full-54/terminal.json"
        ),
        "generation": "1788191106908789",
        "sha256": "b6159521b96d6ec8f0eade323a28d382ed4dac4c8f82165bcf1ae606e6f3d5c0",
        "bytes": 41553,
    },
}
GRADE_REQUEST_SHA256: Final = "37c19cd58c0d9da617bc91f6e8d152c31ecf43fe706abd4505b541032a128a75"
BUILD_RECEIPT: Final = {
    "schema_version": "corpus-r6-broad-admission-cloud-build/v1",
    "code_sha": CODE_SHA,
    "cloud_build_id": BUILD_ID,
    "build_image_tag": (
        "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
        f"nfl-dfs:broad-admission-{CODE_SHA}"
    ),
    "provider_resolved_image": IMAGE,
    "image_digest": IMAGE_DIGEST,
    "source_repository": SOURCE_REPOSITORY,
    "runtime_build_attestation_identity": {
        "uri": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            f"corpus-r6-broad-admission-builds/{CODE_SHA}/{BUILD_ID}/"
            "runtime-build-attestation.json"
        ),
        "generation": "1788181939990108",
        "sha256": "b60d0d701ad8015c80e2dc8a6b8bb8502ed46c78ffdbd091c539d41917da296c",
        "bytes": 846,
    },
    "provider_requested_and_resolved_git_source_exact": True,
    "outcome_artifacts_read_by_build_steps": False,
    "outcome_artifacts_in_runtime_image_context": False,
    "complete": True,
}

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_EXECUTION = re.compile(re.escape(JOB) + r"-[a-z0-9]{5}\Z")


class E4ContinuationError(RuntimeError):
    """One frozen input, provider fact, or resume fact differed."""


def _fail(message: str) -> None:
    raise E4ContinuationError(message)


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
        raise E4ContinuationError("canonical JSON differs") from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} fields differ")
    if (
        type(item["uri"]) is not str
        or not str(item["uri"]).startswith("gs://")
        or type(item["generation"]) not in {str, int}
        or not str(item["generation"]).isdigit()
        or int(str(item["generation"])) <= 0
        or type(item["sha256"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", str(item["sha256"])) is None
        or type(item["bytes"]) is not int
        or int(item["bytes"]) <= 0
    ):
        _fail(f"{label} identity differs")
    return item


class CommandResult:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class CommandRunner:
    """Injectable argv-only process boundary."""

    def run(self, argv: Sequence[str], *, cwd: Path | None = None) -> CommandResult:
        completed = subprocess.run(
            list(argv),
            cwd=None if cwd is None else str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


@dataclass(frozen=True)
class ContinuationPaths:
    root: Path
    host_launcher: Path
    exact_root: Path
    exact_launcher: Path
    run_dir: Path


def _json_bytes(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        return _mapping(json.loads(raw), label=label)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise E4ContinuationError(f"{label} is not one JSON object") from exc


def _read_canonical(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        _fail(f"{label} is absent or aliased")
    raw = path.read_bytes()
    value = _json_bytes(raw, label=label)
    if raw != canonical_bytes(value):
        _fail(f"{label} is not canonical")
    return value


def _safe_parent(run_dir: Path, path: Path) -> None:
    if not path.is_absolute() or run_dir not in path.parents:
        _fail("local continuation path escaped its run directory")
    relative = path.relative_to(run_dir)
    cursor = run_dir
    for part in relative.parts[:-1]:
        cursor /= part
        if cursor.exists() and (cursor.is_symlink() or not cursor.is_dir()):
            _fail("local continuation directory is unsafe")
        cursor.mkdir(mode=0o700, exist_ok=True)


def _publish_once(run_dir: Path, path: Path, payload: bytes) -> bool:
    _safe_parent(run_dir, path)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
            _fail(f"create-once local state differs: {path.name}")
        return False
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
            _fail(f"create-once local state raced: {path.name}")
        return False
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return True


def _replace(run_dir: Path, path: Path, payload: bytes) -> None:
    _safe_parent(run_dir, path)
    if path.is_symlink():
        _fail(f"replaceable local state is aliased: {path.name}")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        os.chmod(temp, 0o600)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _file_sha256(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        _fail(f"authority file is absent or aliased: {path}")
    return sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        _fail("exact source Git authority is unavailable")
    return completed.stdout.strip()


def validate_static_authority(paths: ContinuationPaths) -> ModuleType:
    if paths.root.is_symlink() or paths.exact_root.is_symlink():
        _fail("continuation roots may not be symlinks")
    if _git(paths.root, "rev-parse", "--show-toplevel") != str(paths.root):
        _fail("continuation repository root differs")
    if _git(paths.root, "rev-parse", "HEAD") != _git(
        paths.root, "rev-parse", "refs/remotes/origin/main"
    ):
        _fail("host HEAD must equal durable origin/main")
    dirty = _git(
        paths.root,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        str(Path(__file__).resolve().relative_to(paths.root)),
        str(paths.host_launcher.relative_to(paths.root)),
    )
    if dirty:
        _fail("tracked continuation authorities are not durable and clean")
    if _file_sha256(paths.host_launcher) != HOST_LAUNCHER_SHA256:
        _fail("recovery-aware host result launcher bytes differ")
    if not paths.exact_root.is_dir():
        _fail("exact f2 source clone is absent")
    if (
        _git(paths.exact_root, "rev-parse", "HEAD") != CODE_SHA
        or _git(paths.exact_root, "rev-parse", "refs/remotes/origin/main") != CODE_SHA
        or _git(paths.exact_root, "remote", "get-url", "origin") != SOURCE_REPOSITORY
    ):
        _fail("exact f2 source clone identity differs")
    if _git(
        paths.exact_root,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        "scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh",
        "scripts/finish_corpus_r6_broad_admission_tournament_v1.py",
    ):
        _fail("exact f2 source clone is dirty")
    if _file_sha256(paths.exact_launcher) != EXACT_LAUNCHER_SHA256:
        _fail("exact f2 launcher bytes differ")
    if _file_sha256(EXACT_FINISHER) != EXACT_FINISHER_SHA256:
        _fail("exact f2 finisher bytes differ")
    spec = importlib.util.spec_from_file_location("e4_njfvm_frozen_finisher", EXACT_FINISHER)
    if spec is None or spec.loader is None:
        _fail("exact f2 finisher import is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if module.JOB != JOB or module.JOB_UID != JOB_UID:
        _fail("exact f2 finisher job authority differs")
    module.validate_build_receipt_v1(BUILD_RECEIPT)
    return module


def _proc_identity(proc_root: Path, pid: int) -> tuple[int, int]:
    try:
        raw = (proc_root / str(pid) / "stat").read_text(encoding="ascii")
        suffix = raw.rsplit(") ", maxsplit=1)[1].split()
        return int(suffix[1]), int(suffix[19])
    except (OSError, ValueError, IndexError) as exc:
        raise E4ContinuationError("launcher process identity is unavailable") from exc


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
    root: Path,
    script_path: Path,
    environment: Mapping[str, str],
    proc_root: Path = Path("/proc"),
    current_pid: int | None = None,
    lock_probe: Callable[[Path], bool] = _lock_is_held,
) -> None:
    receipt_text = environment.get("NFL_LAUNCHER_REGISTRY_RECEIPT", "")
    receipt = Path(receipt_text)
    expected_parent = root / ".tmp/launchers"
    if not receipt.is_absolute() or receipt.parent != expected_parent:
        _fail("launcher_registry receipt path differs")
    expected_hash = environment.get("NFL_LAUNCHER_REGISTRY_RECEIPT_SHA256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        _fail("launcher_registry receipt hash differs")
    if _file_sha256(receipt) != expected_hash:
        _fail("launcher_registry receipt bytes differ")
    item = _read_canonical(receipt, label="launcher_registry receipt")
    expected_keys = {
        "schema_version",
        "script_path",
        "pid",
        "process_start_ticks",
        "owner",
        "lane",
        "target_run_id_prefixes",
        "acquired_at_utc",
    }
    wrapper_pid = item.get("pid")
    wrapper_ticks = item.get("process_start_ticks")
    if (
        set(item) != expected_keys
        or item.get("schema_version") != "shared-launcher-registry/v1"
        or item.get("script_path") != str(script_path.resolve())
        or item.get("owner") != "production"
        or item.get("lane") != JOB
        or item.get("target_run_id_prefixes") != TARGET_PREFIXES
        or type(wrapper_pid) is not int
        or int(wrapper_pid) <= 1
        or type(wrapper_ticks) is not int
        or int(wrapper_ticks) <= 0
    ):
        _fail("launcher_registry receipt authority differs")
    if (
        environment.get("NFL_LAUNCHER_REGISTRY_LANE") != JOB
        or environment.get("NFL_LAUNCHER_REGISTRY_WRAPPER_PID") != str(wrapper_pid)
        or environment.get("NFL_LAUNCHER_REGISTRY_WRAPPER_START_TICKS")
        != str(wrapper_ticks)
    ):
        _fail("launcher_registry environment authority differs")
    _, live_ticks = _proc_identity(proc_root, int(wrapper_pid))
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
    lock_name = sha256(JOB.encode("ascii")).hexdigest() + ".lock"
    lock_path = root / ".tmp/launcher-locks" / lock_name
    if lock_path.is_symlink() or not lock_path.is_file() or not lock_probe(lock_path):
        _fail("launcher_registry lane lock is not held")


def _env_map(container: Mapping[str, object]) -> dict[str, str]:
    raw = container.get("env")
    if type(raw) is not list:
        _fail("provider environment differs")
    result: dict[str, str] = {}
    for row in raw:
        item = _mapping(row, label="provider environment row")
        if set(item) != {"name", "value"} or any(type(value) is not str for value in item.values()):
            _fail("provider environment row differs")
        name = str(item["name"])
        if name in result:
            _fail("provider environment names are not unique")
        result[name] = str(item["value"])
    return result


def _timeout_seconds(template: Mapping[str, object]) -> str:
    if "timeoutSeconds" in template:
        return str(template["timeoutSeconds"])
    return str(template.get("timeout", "")).removesuffix(".000000000s").removesuffix("s")


def validate_provider_execution(
    value: object,
    *,
    execution_name: str,
    execution_uid: str,
    phase: str,
    request: Mapping[str, object],
    timeout_seconds: str,
    job_generation: str,
) -> tuple[dict[str, object], bool]:
    if phase not in {"grade", "grade-reopen"}:
        _fail("continuation provider phase differs")
    item = _mapping(value, label=f"{phase} provider execution")
    metadata = _mapping(item.get("metadata"), label="provider metadata")
    labels = _mapping(metadata.get("labels"), label="provider labels")
    spec = _mapping(item.get("spec"), label="provider spec")
    template = _mapping(spec.get("template"), label="provider task template")
    template_spec = _mapping(template.get("spec"), label="provider task template spec")
    containers = template_spec.get("containers")
    if type(containers) is not list or len(containers) != 1:
        _fail("provider container count differs")
    container = _mapping(containers[0], label="provider container")
    resources = _mapping(container.get("resources"), label="provider resources")
    limits = _mapping(resources.get("limits"), label="provider resource limits")
    expected_request = dict(request)
    request_bytes = canonical_bytes(expected_request)
    request_sha = sha256(request_bytes).hexdigest()
    expected_bound = expected_request[
        "terminal_identity" if phase == "grade" else "grade_terminal_identity"
    ]
    expected_env = {
        "CODE_SHA": CODE_SHA,
        "IMAGE_DIGEST": IMAGE_DIGEST,
        "BUILD_ID": BUILD_ID,
        "IMAGE_URI": IMAGE,
        "R6_BROAD_ADMISSION_ENABLE": "I_UNDERSTAND_FIXED_CORPUS_ADMISSION_TOURNAMENT_V1",
        "R6_BROAD_ADMISSION_REQUEST_SHA256": request_sha,
        "R6_BROAD_ADMISSION_REQUEST_B64": base64.b64encode(request_bytes).decode("ascii"),
        "R6_BROAD_ADMISSION_BOUND_IDENTITY": json.dumps(
            expected_bound, sort_keys=True, separators=(",", ":")
        ),
        "R6_BROAD_ADMISSION_OUTCOMES_ALLOWED": "true" if phase == "grade" else "false",
        "R6_BROAD_ADMISSION_TASK0_SMOKE": "false",
    }
    if phase == "grade":
        expected_env["R6_BROAD_ADMISSION_TIMEOUT_RECOVERY_FROM"] = FAILED_EXECUTION
    if (
        metadata.get("name") != execution_name
        or metadata.get("uid") != execution_uid
        or str(metadata.get("generation")) != "1"
        or labels.get("run.googleapis.com/job") != JOB
        or labels.get("run.googleapis.com/jobUid") != JOB_UID
        or str(labels.get("run.googleapis.com/jobGeneration")) != job_generation
        or spec.get("taskCount") != 1
        or spec.get("parallelism") not in ({54} if phase == "grade" else {1, 54})
        or template_spec.get("maxRetries") != 0
        or _timeout_seconds(template_spec) != timeout_seconds
        or template_spec.get("serviceAccountName") != SERVICE_ACCOUNT
        or container.get("image") != IMAGE
        or container.get("command") != ["/bin/bash"]
        or container.get("args")
        != [
            "/app/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh",
            "container-run",
            phase,
        ]
        or limits != {"cpu": "8", "memory": "32Gi"}
        or _env_map(container) != expected_env
    ):
        _fail(f"{phase} provider envelope differs")
    status = _mapping(item.get("status", {}), label="provider status")
    conditions = status.get("conditions")
    if type(conditions) is not list:
        _fail("provider completion conditions differ")
    completed = [
        row.get("status")
        for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if len(completed) != 1 or completed[0] not in {"Unknown", "True", "False"}:
        _fail("provider completion condition differs")
    counts: dict[str, int] = {}
    for key in ("runningCount", "succeededCount", "failedCount", "cancelledCount", "retriedCount"):
        raw = status.get(key, 0)
        if raw in {None, ""}:
            raw = 0
        if type(raw) is not int or raw < 0:
            _fail("provider execution counts differ")
        counts[key] = raw
    if (
        completed[0] == "False"
        or counts["failedCount"]
        or counts["cancelledCount"]
        or counts["retriedCount"]
    ):
        _fail(f"{phase} execution failed, cancelled, or retried")
    terminal = completed[0] == "True"
    if terminal:
        if (
            counts != {
                "runningCount": 0,
                "succeededCount": 1,
                "failedCount": 0,
                "cancelledCount": 0,
                "retriedCount": 0,
            }
            or type(status.get("completionTime")) is not str
            or not str(status["completionTime"])
        ):
            _fail("terminal provider success counts differ")
    elif (
        counts["succeededCount"] != 0
        or counts["runningCount"] not in {0, 1}
        or status.get("completionTime") not in {None, ""}
    ):
        _fail("nonterminal provider state differs")
    return item, terminal


class E4ExactNameContinuation:
    def __init__(
        self,
        *,
        paths: ContinuationPaths,
        frozen: ModuleType,
        runner: CommandRunner,
        poll_interval_seconds: int,
        max_polls: int,
        sleeper: Callable[[float], None] = time.sleep,
        resume_execution: str = "",
        resume_uid: str = "",
    ) -> None:
        if not 1 <= poll_interval_seconds <= 60 or not 1 <= max_polls <= 2_000:
            _fail("continuation poll bounds differ")
        if (bool(resume_execution) != bool(resume_uid)) or (
            resume_execution
            and (
                _EXECUTION.fullmatch(resume_execution) is None
                or _UUID.fullmatch(resume_uid) is None
            )
        ):
            _fail("grade-reopen resume identity differs")
        self.paths = paths
        self.frozen = frozen
        self.runner = runner
        self.poll_interval_seconds = poll_interval_seconds
        self.max_polls = max_polls
        self.sleeper = sleeper
        self.resume_execution = resume_execution
        self.resume_uid = resume_uid
        self.run_dir = paths.run_dir
        base = paths.root / ".tmp"
        if (
            self.run_dir.is_symlink()
            or not self.run_dir.is_absolute()
            or base not in self.run_dir.parents
        ):
            _fail("continuation run directory differs")
        self.run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.build = frozen.validate_build_receipt_v1(BUILD_RECEIPT)
        if canonical_sha256(GRADE_REQUEST) != GRADE_REQUEST_SHA256:
            _fail("frozen grade request identity differs")

    def _path(self, relative: str) -> Path:
        return self.run_dir / relative

    def _describe(self, name: str) -> dict[str, object]:
        completed = self.runner.run(
            [
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
            ]
        )
        if completed.returncode != 0:
            _fail(f"exact execution describe failed: {name}")
        return _json_bytes(completed.stdout, label=f"provider execution {name}")

    def _poll(
        self,
        *,
        directory: str,
        name: str,
        uid: str,
        phase: str,
        request: Mapping[str, object],
        timeout: str,
        generation: str,
    ) -> dict[str, object]:
        terminal_path = self._path(f"{directory}/provider-terminal.json")
        if terminal_path.exists():
            value, terminal = validate_provider_execution(
                _read_canonical(terminal_path, label=f"persisted {phase} provider"),
                execution_name=name,
                execution_uid=uid,
                phase=phase,
                request=request,
                timeout_seconds=timeout,
                job_generation=generation,
            )
            if not terminal:
                _fail(f"persisted {phase} provider is not terminal")
            return value
        for index in range(self.max_polls):
            value, terminal = validate_provider_execution(
                self._describe(name),
                execution_name=name,
                execution_uid=uid,
                phase=phase,
                request=request,
                timeout_seconds=timeout,
                job_generation=generation,
            )
            _replace(
                self.run_dir,
                self._path(f"{directory}/provider-latest.json"),
                canonical_bytes(value),
            )
            if terminal:
                _publish_once(self.run_dir, terminal_path, canonical_bytes(value))
                return value
            if index + 1 < self.max_polls:
                self.sleeper(self.poll_interval_seconds)
        _fail(f"{phase} exact execution polling exhausted")

    def _validated_result(
        self, *, path: Path, phase: str, name: str, uid: str
    ) -> dict[str, object]:
        try:
            value = self.frozen.validate_result_receipt_v1(
                _read_canonical(path, label=f"persisted {phase} result"),
                phase=phase,
                execution_name=name,
                build_receipt=self.build,
            )
        except Exception as exc:
            raise E4ContinuationError(f"{phase} frozen result validation failed") from exc
        execution = _mapping(value["execution"], label=f"{phase} result execution")
        if execution.get("uid") != uid:
            _fail(f"{phase} result UID differs")
        return value

    def _collect_result(
        self,
        *,
        directory: str,
        phase: str,
        name: str,
        uid: str,
        launcher: Path,
        cwd: Path,
    ) -> dict[str, object]:
        result_path = self._path(f"{directory}/result.json")
        if result_path.exists():
            return self._validated_result(path=result_path, phase=phase, name=name, uid=uid)
        raw_path = self._path(f"{directory}/result-stdout.raw.json")
        if raw_path.exists():
            raw_value = _read_canonical(raw_path, label=f"persisted {phase} raw result")
        else:
            completed = self.runner.run(
                [str(launcher), "result", IMAGE, CODE_SHA, BUILD_ID, name], cwd=cwd
            )
            if completed.returncode != 0:
                _fail(f"{phase} exact-name result collection failed")
            raw_value = _json_bytes(completed.stdout, label=f"{phase} result stdout")
            _publish_once(self.run_dir, raw_path, canonical_bytes(raw_value))
        _publish_once(self.run_dir, result_path, canonical_bytes(raw_value))
        return self._validated_result(path=result_path, phase=phase, name=name, uid=uid)

    def _grade_terminal(self, grade: Mapping[str, object]) -> dict[str, object]:
        operator = _mapping(grade["operator_receipt"], label="grade operator receipt")
        result = _mapping(operator["result"], label="grade operator result")
        return _identity(result["grade_terminal_identity"], label="grade terminal")

    def _validated_launch(self, path: Path, request: Mapping[str, object]) -> dict[str, object]:
        try:
            value = self.frozen.validate_launch_receipt_v1(
                _read_canonical(path, label="persisted grade-reopen launch"),
                phase="grade-reopen",
                request=request,
                build_receipt=self.build,
            )
        except Exception as exc:
            raise E4ContinuationError("grade-reopen frozen launch validation failed") from exc
        return value

    def _reconciled_launch(
        self, *, request: Mapping[str, object], provider: Mapping[str, object]
    ) -> dict[str, object]:
        labels = _mapping(
            _mapping(provider["metadata"], label="metadata")["labels"],
            label="labels",
        )
        generation = int(str(labels["run.googleapis.com/jobGeneration"]))
        value = {
            "schema_version": "corpus-r6-broad-admission-cloud-launch/v1",
            "phase": "grade-reopen",
            "code_sha": CODE_SHA,
            "cloud_build_id": BUILD_ID,
            "provider_resolved_image": IMAGE,
            "image_digest": IMAGE_DIGEST,
            "reused_job": {"name": JOB, "uid": JOB_UID, "generation": generation},
            "execution": {"name": self.resume_execution, "uid": self.resume_uid, "task_count": 1},
            "bound_input_authority_identity": request["grade_terminal_identity"],
            "source_task_execution": None,
            "task0_gate_result": None,
            "request_sha256": canonical_sha256(request),
            "outcomes_allowed": False,
            "task0_nonpublishing_smoke": False,
            "execution_provider_reopened": True,
            "complete": True,
        }
        self.frozen.validate_launch_receipt_v1(
            value, phase="grade-reopen", request=request, build_receipt=self.build
        )
        return value

    def _launch_or_resume(self, request: Mapping[str, object]) -> dict[str, object]:
        request_path = self._path("grade-reopen/request.json")
        _publish_once(self.run_dir, request_path, canonical_bytes(request))
        intent = {
            "schema_version": "e4-njfvm-grade-reopen-launch-intent/v1",
            "source_execution": {"name": RECOVERY_EXECUTION, "uid": RECOVERY_UID},
            "grade_terminal_identity": request["grade_terminal_identity"],
            "request_sha256": canonical_sha256(request),
            "runtime": {"code_sha": CODE_SHA, "cloud_build_id": BUILD_ID, "image": IMAGE},
            "exact_f2_launcher_sha256": EXACT_LAUNCHER_SHA256,
            "automatic_relaunch": False,
            "complete": True,
        }
        intent_created = _publish_once(
            self.run_dir,
            self._path("grade-reopen/launch-intent.json"),
            canonical_bytes(intent),
        )
        launch_path = self._path("grade-reopen/launch.json")
        raw_path = self._path("grade-reopen/launcher-stdout.raw.json")
        if launch_path.exists():
            launch = self._validated_launch(launch_path, request)
        elif raw_path.exists():
            raw = _read_canonical(raw_path, label="persisted grade-reopen launcher stdout")
            _publish_once(self.run_dir, launch_path, canonical_bytes(raw))
            launch = self._validated_launch(launch_path, request)
        elif not intent_created:
            if not self.resume_execution:
                _fail("ambiguous grade-reopen launch intent; exact name and UID required")
            observed = self._describe(self.resume_execution)
            observed_labels = _mapping(
                _mapping(observed["metadata"], label="metadata")["labels"],
                label="labels",
            )
            observed_generation = str(
                observed_labels["run.googleapis.com/jobGeneration"]
            )
            provider, _ = validate_provider_execution(
                observed,
                execution_name=self.resume_execution,
                execution_uid=self.resume_uid,
                phase="grade-reopen",
                request=request,
                timeout_seconds="21600",
                job_generation=observed_generation,
            )
            launch = self._reconciled_launch(request=request, provider=provider)
            _publish_once(self.run_dir, launch_path, canonical_bytes(launch))
        else:
            if self.resume_execution:
                _fail("fresh grade-reopen intent cannot consume a preexisting execution")
            completed = self.runner.run(
                [
                    str(self.paths.exact_launcher),
                    "grade-reopen",
                    IMAGE,
                    CODE_SHA,
                    BUILD_ID,
                    str(request_path),
                ],
                cwd=self.paths.exact_root,
            )
            if completed.returncode != 0:
                _fail("grade-reopen launch failed or is provider-ambiguous")
            raw = _json_bytes(completed.stdout, label="grade-reopen launcher stdout")
            _publish_once(self.run_dir, raw_path, canonical_bytes(raw))
            _publish_once(self.run_dir, launch_path, canonical_bytes(raw))
            launch = self._validated_launch(launch_path, request)
        execution = _mapping(launch["execution"], label="grade-reopen launch execution")
        if self.resume_execution and (
            execution.get("name") != self.resume_execution
            or execution.get("uid") != self.resume_uid
        ):
            _fail("grade-reopen resume identity differs from persisted launch")
        return launch

    def finish(self) -> dict[str, object]:
        terminal_path = self._path("continuation-terminal.json")
        if terminal_path.exists():
            value = _read_canonical(terminal_path, label="continuation terminal")
            if (
                value.get("schema_version")
                != "e4-njfvm-exact-name-continuation-terminal/v1"
                or value.get("complete") is not True
            ):
                _fail("continuation terminal differs")
            return value
        self._poll(
            directory="recovery-grade",
            name=RECOVERY_EXECUTION,
            uid=RECOVERY_UID,
            phase="grade",
            request=GRADE_REQUEST,
            timeout="43200",
            generation="50",
        )
        grade = self._collect_result(
            directory="recovery-grade",
            phase="grade",
            name=RECOVERY_EXECUTION,
            uid=RECOVERY_UID,
            launcher=self.paths.host_launcher,
            cwd=self.paths.root,
        )
        grade_terminal = self._grade_terminal(grade)
        request = {"grade_terminal_identity": grade_terminal}
        launch = self._launch_or_resume(request)
        execution = _mapping(launch["execution"], label="grade-reopen execution")
        generation = str(_mapping(launch["reused_job"], label="reused job")["generation"])
        reopen_name = str(execution["name"])
        reopen_uid = str(execution["uid"])
        self._poll(
            directory="grade-reopen",
            name=reopen_name,
            uid=reopen_uid,
            phase="grade-reopen",
            request=request,
            timeout="21600",
            generation=generation,
        )
        reopened = self._collect_result(
            directory="grade-reopen",
            phase="grade-reopen",
            name=reopen_name,
            uid=reopen_uid,
            launcher=self.paths.exact_launcher,
            cwd=self.paths.exact_root,
        )
        if self._grade_terminal(reopened) != grade_terminal:
            _fail("independent grade-reopen terminal differs from recovery grade")
        terminal = {
            "schema_version": "e4-njfvm-exact-name-continuation-terminal/v1",
            "recovery_execution": {"name": RECOVERY_EXECUTION, "uid": RECOVERY_UID},
            "grade_reopen_execution": {"name": reopen_name, "uid": reopen_uid},
            "grade_terminal_identity": grade_terminal,
            "recovery_grade_receipt_sha256": canonical_sha256(grade),
            "grade_reopen_receipt_sha256": canonical_sha256(reopened),
            "exact_source_commit": CODE_SHA,
            "exact_f2_launcher_sha256": EXACT_LAUNCHER_SHA256,
            "execution_listing_used": False,
            "automatic_relaunch": False,
            "new_grade_recovery_launched": False,
            "complete": True,
        }
        _publish_once(self.run_dir, terminal_path, canonical_bytes(terminal))
        return terminal


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll-interval-seconds", type=int, default=30)
    parser.add_argument("--max-polls", type=int, default=2_000)
    parser.add_argument("--grade-reopen-execution", default="")
    parser.add_argument("--grade-reopen-uid", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.execute or args.confirmation != CONFIRMATION:
        _fail(f"continuation is default-off; require --execute --confirmation {CONFIRMATION}")
    paths = ContinuationPaths(ROOT, HOST_LAUNCHER, EXACT_ROOT, EXACT_LAUNCHER, RUN_DIR)
    frozen = validate_static_authority(paths)
    verify_launcher_registry_lane(
        root=ROOT,
        script_path=Path(__file__).resolve(),
        environment=os.environ,
    )
    RUN_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = RUN_DIR / "continuation.lock"
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise E4ContinuationError(
                "another exact-name E4 continuation owns the local lock"
            ) from exc
        continuation = E4ExactNameContinuation(
            paths=paths,
            frozen=frozen,
            runner=CommandRunner(),
            poll_interval_seconds=args.poll_interval_seconds,
            max_polls=args.max_polls,
            resume_execution=args.grade_reopen_execution,
            resume_uid=args.grade_reopen_uid,
        )
        result = continuation.finish()
    sys.stdout.buffer.write(canonical_bytes(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except E4ContinuationError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


__all__ = [
    "BUILD_RECEIPT",
    "CODE_SHA",
    "CONFIRMATION",
    "ContinuationPaths",
    "E4ContinuationError",
    "E4ExactNameContinuation",
    "GRADE_REQUEST",
    "IMAGE",
    "RECOVERY_EXECUTION",
    "RECOVERY_UID",
    "TARGET_PREFIXES",
    "canonical_bytes",
    "validate_provider_execution",
    "verify_launcher_registry_lane",
]
