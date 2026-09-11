#!/usr/bin/env python3
"""Crash-closed host finisher for the canonical R6 matchup source-v3 chain.

The source-v3 Cloud Run wrapper deliberately exposes one phase at a time.  This
host-only finisher keeps the shared job lane for the complete

    worker -> verifier -> publisher -> independent reopener

sequence.  Every phase has a create-once request, launch intent, exact
name/UID launch receipt, provider terminal, controller result, and exact
provider receipt.  An intent is consumed before the wrapper can mutate the
shared job.  A missing/invalid wrapper response is reconciled only against the
job's exact pre-launch latest execution and the exact post-launch latest
name/UID/provider envelope; it is never submitted a second time.

The default invocation is inert.  The executable path also requires the
canonical production ``launcher_registry.sh`` lane receipt.  Build submission
is intentionally outside this file so the job lane is not held while an
independent direct-Git Cloud Build runs.
"""

from __future__ import annotations

import argparse
import base64
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
import fcntl
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import threading
import time
from typing import Final


ROOT: Final = Path(__file__).resolve().parents[1]
SOURCE_ROOT: Final = (ROOT / "src").resolve()
sys.path.insert(0, str(SOURCE_ROOT))

from nfl_dfs.research import (  # noqa: E402
    corpus_r6_matchup_source_batch_outer_candidate_authority_v3 as batch_v3,
)
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_matchup_source_task0_v3 as task0_v3,
)

if Path(batch_v3.__file__).resolve() != (
    SOURCE_ROOT
    / "nfl_dfs/research/corpus_r6_matchup_source_batch_outer_candidate_authority_v3.py"
):
    raise RuntimeError("source-v3 batch module origin differs")
if Path(task0_v3.__file__).resolve() != (
    SOURCE_ROOT / "nfl_dfs/research/corpus_r6_matchup_source_task0_v3.py"
):
    raise RuntimeError("source-v3 task0 module origin differs")


LAUNCHER: Final = ROOT / "scripts/cloud_corpus_r6_matchup_source_task0_v3.sh"
PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
JOB: Final = "atlas-cbc-32g-full-2023-w8-v1"
JOB_UID: Final = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
SERVICE_ACCOUNT: Final = "817589974517-compute@developer.gserviceaccount.com"
SOURCE_REPOSITORY: Final = "https://github.com/espechtsoftware/nfl-predictions.git"
REGISTRY_STATE_ROOT: Final = Path(
    "/home/erich/.local/state/nfl-dfs/production-launcher-registry"
)
RUN_STATE_ROOT: Final = Path(
    "/home/erich/.local/state/nfl-dfs/corpus-r6-matchup-source-v3"
)
CONFIRMATION: Final = "I_UNDERSTAND_SOURCE_V3_COMPLETE_CHAIN"
PHASES: Final = ("worker", "verify", "publish", "reopen")

MODE_ENV: Final = "R6_MATCHUP_SOURCE_TASK0_MODE"
OUTCOMES_ENV: Final = "R6_MATCHUP_SOURCE_TASK0_OUTCOMES_ALLOWED"
PAYLOAD_B64_ENV: Final = "R6_MATCHUP_SOURCE_TASK0_PAYLOAD_B64"
PAYLOAD_SHA_ENV: Final = "R6_MATCHUP_SOURCE_TASK0_PAYLOAD_SHA256"
WORKER_ENV: Final = "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_WORKER_EXECUTION"
VERIFIER_ENV: Final = "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_VERIFIER_EXECUTION"
PUBLISHER_ENV: Final = "CORPUS_R6_MATCHUP_SOURCE_V3_PUBLISHER_EXECUTION"

_RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{7,80}\Z")
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


class SourceV3FinisherError(RuntimeError):
    """One immutable, provider, or local recovery fact differed."""


def _fail(message: str) -> None:
    raise SourceV3FinisherError(message)


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
        raise SourceV3FinisherError("canonical JSON differs") from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def _deterministic_gnu_gzip(payload: bytes) -> bytes:
    try:
        completed = subprocess.run(
            ("gzip", "-n", "-9", "-c"),
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise SourceV3FinisherError("deterministic gzip is unavailable") from exc
    if completed.returncode != 0 or not completed.stdout:
        _fail("deterministic gzip failed")
    return completed.stdout


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
        "uri": item["uri"],
        "generation": str(item["generation"]),
        "sha256": item["sha256"],
        "bytes": item["bytes"],
    }


def _parse_json(raw: bytes, *, label: str, canonical: bool = False) -> dict[str, object]:
    if not raw:
        _fail(f"{label} is empty")
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SourceV3FinisherError(f"{label} is not JSON") from exc
    item = _mapping(value, label=label)
    if canonical and raw not in {canonical_bytes(item), canonical_bytes(item)[:-1]}:
        _fail(f"{label} is not canonical JSON")
    return item


def _read_canonical(path: Path, *, label: str) -> dict[str, object]:
    if (
        not path.is_absolute()
        or path.is_symlink()
        or path.resolve(strict=False) != path
        or not _safe_local_file(path)
    ):
        _fail(f"{label} must be one absolute unaliased regular file")
    return _parse_json(path.read_bytes(), label=label, canonical=True)


def _read_private_raw(path: Path, *, label: str) -> bytes:
    if (
        not path.is_absolute()
        or path.is_symlink()
        or path.resolve(strict=False) != path
        or not _safe_local_file(path)
    ):
        _fail(f"{label} must be one absolute unaliased regular file")
    return path.read_bytes()


def _safe_local_file(path: Path) -> bool:
    try:
        details = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISREG(details.st_mode)
        and details.st_uid == os.getuid()
        and details.st_nlink == 1
        and stat.S_IMODE(details.st_mode) == 0o600
    )


def _safe_local_directory(path: Path) -> bool:
    try:
        details = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISDIR(details.st_mode)
        and details.st_uid == os.getuid()
        and stat.S_IMODE(details.st_mode) == 0o700
    )


def _ensure_private_directory(path: Path) -> None:
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        if cursor.is_symlink():
            _fail("local create-once directory may not be aliased")
        missing.append(cursor)
        cursor = cursor.parent
    if cursor.is_symlink() or not _safe_local_directory(cursor):
        _fail("local create-once ancestor permissions differ")
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            pass
        if directory.is_symlink() or not _safe_local_directory(directory):
            _fail("local create-once directory permissions differ")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_once(path: Path, raw: bytes) -> bool:
    if (
        not path.is_absolute()
        or path.is_symlink()
        or path.resolve(strict=False) != path
    ):
        _fail("local create-once target must be absolute and unaliased")
    _ensure_private_directory(path.parent)
    if path.parent.is_symlink() or path.parent.resolve() != path.parent:
        _fail("local create-once parent differs")
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except FileExistsError:
        if path.is_symlink() or not _safe_local_file(path) or path.read_bytes() != raw:
            _fail(f"local create-once collision: {path}")
        return False
    try:
        details = os.fstat(descriptor)
        if (
            not stat.S_ISREG(details.st_mode)
            or details.st_uid != os.getuid()
            or details.st_nlink != 1
            or stat.S_IMODE(details.st_mode) != 0o600
        ):
            _fail("local create-once file identity differs")
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
        _fail("source-v3 state directory must be absolute and unaliased")
    root = RUN_STATE_ROOT
    if root.is_symlink() or root.resolve(strict=False) != root:
        _fail("source-v3 canonical state root differs")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not _safe_local_directory(root):
        _fail("source-v3 canonical state root permissions differ")
    retained = path.resolve(strict=False)
    if retained != root / run_id:
        _fail("source-v3 state directory must be the canonical run-id directory")
    cursor = retained
    while cursor != root:
        if cursor.exists() and cursor.is_symlink():
            _fail("source-v3 state directory may not traverse a symlink")
        cursor = cursor.parent
    retained.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not _safe_local_directory(retained):
        _fail("source-v3 state directory permissions differ")
    return retained


def _next_observation_index(
    directory: Path, *, expression: re.Pattern[str], label: str
) -> int:
    """Return a restart-safe index without overwriting prior observations."""

    if not directory.exists():
        return 0
    if directory.is_symlink() or not directory.is_dir():
        _fail(f"{label} directory differs")
    indices: list[int] = []
    for entry in directory.iterdir():
        if entry.is_symlink() or not _safe_local_file(entry):
            _fail(f"{label} entry differs")
        matched = expression.fullmatch(entry.name)
        if matched is None:
            _fail(f"{label} filename differs")
        indices.append(int(matched.group(1)))
    return 0 if not indices else max(indices) + 1


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
            list(argv),
            cwd=None if cwd is None else str(cwd),
            env=None if env is None else dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _command_text(
    runner: CommandRunner, argv: Sequence[str], *, label: str, cwd: Path = ROOT
) -> str:
    result = runner.run(argv, cwd=cwd)
    if result.returncode != 0:
        _fail(f"{label} command failed")
    try:
        return result.stdout.decode("utf-8").strip()
    except UnicodeError as exc:
        raise SourceV3FinisherError(f"{label} output differs") from exc


def validate_exact_repository(*, code_sha: str, runner: CommandRunner) -> None:
    if _COMMIT.fullmatch(code_sha) is None:
        _fail("source-v3 code SHA differs")
    if (
        _command_text(runner, ("git", "rev-parse", "HEAD"), label="HEAD")
        != code_sha
        or _command_text(
            runner,
            ("git", "rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
            label="origin/main",
        )
        != code_sha
        or _command_text(
            runner, ("git", "remote", "get-url", "origin"), label="origin URL"
        )
        != SOURCE_REPOSITORY
    ):
        _fail("source-v3 checkout must equal fixed durable origin/main")
    status = runner.run(
        ("git", "status", "--porcelain=v1", "--untracked-files=all"), cwd=ROOT
    )
    if status.returncode != 0 or status.stdout != b"":
        _fail("source-v3 checkout must remain completely clean")
    for path in (LAUNCHER, Path(__file__).resolve()):
        relative = str(path.relative_to(ROOT))
        tracked = runner.run(("git", "cat-file", "-e", f"{code_sha}:{relative}"), cwd=ROOT)
        if tracked.returncode != 0:
            _fail(f"source-v3 host authority is not tracked: {relative}")


def validate_build_provider(
    value: object, *, code_sha: str, build_id: str, image: str
) -> dict[str, object]:
    item = _mapping(value, label="source-v3 provider build")
    digest = image.rsplit("@", 1)[-1]
    tag = (
        "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
        f"nfl-dfs:matchup-source-v3-{code_sha}"
    )
    provenance = _mapping(item.get("sourceProvenance"), label="build provenance")
    source = _mapping(item.get("source"), label="build source")
    images = _sequence(
        _mapping(item.get("results"), label="build results").get("images"),
        label="build result images",
    )
    matched = [
        row
        for row in images
        if isinstance(row, Mapping)
        and row.get("name") == tag
        and row.get("digest") == digest
    ]
    substitutions = _mapping(item.get("substitutions"), label="build substitutions")
    if (
        _UUID.fullmatch(build_id) is None
        or _IMAGE.fullmatch(image) is None
        or item.get("id") != build_id
        or item.get("status") != "SUCCESS"
        or source.get("gitSource")
        != {"url": SOURCE_REPOSITORY, "revision": code_sha}
        or provenance.get("resolvedGitSource")
        != {"url": SOURCE_REPOSITORY, "revision": code_sha}
        or substitutions.get("_CODE_SHA") != code_sha
        or substitutions.get("_BUILD_IMAGE") != tag
        or len(matched) != 1
    ):
        _fail("provider build/image/direct-Git binding differs")
    return item


def validate_controller_launch(
    value: object,
    *,
    phase: str,
    code_sha: str,
    build_id: str,
    image: str,
    payload_sha256: str,
) -> dict[str, object]:
    item = _mapping(value, label=f"{phase} controller launch")
    execution = _mapping(item.get("execution"), label=f"{phase} launch execution")
    expected = {
        "schema_version",
        "phase",
        "execution",
        "provider_resolved_image",
        "code_sha",
        "cloud_build_id",
        "payload_sha256",
        "outcomes_allowed",
        "complete",
    }
    if (
        set(item) != expected
        or item.get("schema_version")
        != "corpus-r6-matchup-source-task0-cloud-launch/v3"
        or item.get("phase") != phase
        or set(execution) != {"name", "task_count"}
        or type(execution.get("name")) is not str
        or _EXECUTION.fullmatch(str(execution["name"])) is None
        or execution.get("task_count") != 1
        or item.get("provider_resolved_image") != image
        or item.get("code_sha") != code_sha
        or item.get("cloud_build_id") != build_id
        or item.get("payload_sha256") != payload_sha256
        or item.get("outcomes_allowed") is not False
        or item.get("complete") is not True
    ):
        _fail(f"{phase} controller launch differs")
    return item


def validate_controller_result(
    value: object, *, phase: str, execution_name: str
) -> dict[str, object]:
    item = _mapping(value, label=f"{phase} controller result")
    expected = {
        "schema_version",
        "phase",
        "execution_name",
        "operator_stdout_identity",
        "provider_receipt_identity",
        "exact_provider_state_derived",
        "complete",
    }
    if (
        set(item) != expected
        or item.get("schema_version")
        != "corpus-r6-matchup-source-controller-result/v3"
        or item.get("phase") != phase
        or item.get("execution_name") != execution_name
        or item.get("exact_provider_state_derived") is not True
        or item.get("complete") is not True
    ):
        _fail(f"{phase} controller result differs")
    _identity(item.get("operator_stdout_identity"), label=f"{phase} stdout identity")
    _identity(item.get("provider_receipt_identity"), label=f"{phase} receipt identity")
    return item


def _environment(container: Mapping[str, object]) -> dict[str, str]:
    rows = _sequence(container.get("env"), label="provider environment")
    result: dict[str, str] = {}
    for row_value in rows:
        row = _mapping(row_value, label="provider environment row")
        if (
            set(row) != {"name", "value"}
            or type(row.get("name")) is not str
            or type(row.get("value")) is not str
            or str(row["name"]) in result
        ):
            _fail("provider environment row differs")
        result[str(row["name"])] = str(row["value"])
    return result


def _timeout_seconds(template: Mapping[str, object]) -> str:
    has_seconds = "timeoutSeconds" in template
    has_duration = "timeout" in template
    seconds = template.get("timeoutSeconds")
    duration = template.get("timeout")
    if (
        not (has_seconds or has_duration)
        or (has_seconds and seconds != "86400")
        or (
            has_duration
            and duration not in {"86400s", "86400.000000000s"}
        )
    ):
        _fail("provider execution timeout differs")
    return "86400s"


def validate_provider_execution(
    value: object,
    *,
    phase: str,
    execution_name: str,
    execution_uid: str | None,
    code_sha: str,
    build_id: str,
    image: str,
    run_id: str,
    payload: bytes,
    worker_execution: str,
    verifier_execution: str,
    publisher_execution: str,
) -> tuple[dict[str, object], str]:
    """Return the exact provider execution and Completed state.

    ``MISSING`` and ``Unknown`` admit any internally consistent one-task
    partial-success projection.  They are observations to poll again, never
    terminal success and never new launch authority.
    """

    item = _mapping(value, label=f"{phase} provider execution")
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
        label="provider resource limits",
    )
    env = _environment(container)
    digest = image.rsplit("@", 1)[-1]
    payload_sha = sha256(payload).hexdigest()
    expected_env = {
        "BUILD_ID": build_id,
        "CODE_SHA": code_sha,
        "CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_DIGEST": digest,
        "CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_REFERENCE": image,
        "CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_SOURCE_COMMIT": code_sha,
        PUBLISHER_ENV: publisher_execution,
        VERIFIER_ENV: verifier_execution,
        WORKER_ENV: worker_execution,
        "IMAGE_DIGEST": digest,
        "IMAGE_SOURCE_COMMIT_SHA": code_sha,
        "IMAGE_URI": image,
        MODE_ENV: phase,
        OUTCOMES_ENV: "false",
        PAYLOAD_SHA_ENV: payload_sha,
        "TASK0_RUN_ID": run_id,
    }
    encoded = env.get(PAYLOAD_B64_ENV, "")
    try:
        compressed = base64.b64decode(encoded, validate=True)
        decoded = gzip.decompress(compressed)
    except (ValueError, OSError) as exc:
        raise SourceV3FinisherError("provider payload transport differs") from exc
    expected_compressed = _deterministic_gnu_gzip(payload)
    expected_env[PAYLOAD_B64_ENV] = encoded
    if (
        decoded != payload
        or compressed != expected_compressed
        or base64.b64encode(compressed).decode("ascii") != encoded
        or env.get(PAYLOAD_SHA_ENV) != payload_sha
        or len(encoded) > 30_000
        or not 1 <= len(payload) <= 262_144
        or env != expected_env
        or metadata.get("name") != execution_name
        or _EXECUTION.fullmatch(execution_name) is None
        or type(metadata.get("uid")) is not str
        or _UUID.fullmatch(str(metadata["uid"])) is None
        or (execution_uid is not None and metadata.get("uid") != execution_uid)
        or labels.get("run.googleapis.com/job") != JOB
        or labels.get("run.googleapis.com/jobUid") != JOB_UID
        or type(labels.get("run.googleapis.com/jobGeneration")) is not str
        or re.fullmatch(
            r"[1-9][0-9]*",
            str(labels.get("run.googleapis.com/jobGeneration", "")),
        )
        is None
        or spec.get("taskCount") != 1
        or spec.get("parallelism") != 1
        or task_spec.get("maxRetries") != 0
        or _timeout_seconds(task_spec) != "86400s"
        or task_spec.get("serviceAccountName") != SERVICE_ACCOUNT
        or container.get("image") != image
        or container.get("command") != ["/bin/bash"]
        or container.get("args")
        != [
            "/app/scripts/cloud_corpus_r6_matchup_source_task0_v3.sh",
            "container-run",
            phase,
        ]
        or limits != {"cpu": "8", "memory": "32Gi"}
    ):
        _fail(f"{phase} provider envelope differs")

    status = _mapping(item.get("status", {}), label="provider status")
    conditions = status.get("conditions", [])
    if type(conditions) is not list:
        _fail("provider completion conditions differ")
    completed = [
        row.get("status")
        for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if len(completed) > 1 or (
        completed and completed[0] not in ("Unknown", "True", "False")
    ):
        _fail("provider Completed condition differs")
    completed_state = "MISSING" if not completed else str(completed[0])
    counts: dict[str, int] = {}
    for key in (
        "runningCount",
        "succeededCount",
        "failedCount",
        "cancelledCount",
        "retriedCount",
    ):
        raw = status.get(key, 0)
        if raw is None or raw == "":
            raw = 0
        if type(raw) is not int or raw < 0:
            _fail("provider execution counts differ")
        counts[key] = raw
    if completed_state == "True":
        if (
            counts
            != {
                "runningCount": 0,
                "succeededCount": 1,
                "failedCount": 0,
                "cancelledCount": 0,
                "retriedCount": 0,
            }
            or type(status.get("completionTime")) is not str
            or _RFC3339.fullmatch(str(status["completionTime"])) is None
        ):
            _fail("terminal provider success counts differ")
    elif completed_state == "False":
        if (
            counts["runningCount"] != 0
            or counts["succeededCount"] != 0
            or counts["failedCount"] + counts["cancelledCount"] != 1
            or counts["retriedCount"] != 0
            or type(status.get("completionTime")) is not str
            or _RFC3339.fullmatch(str(status["completionTime"])) is None
        ):
            _fail("terminal provider failure counts differ")
    else:
        completion = status.get("completionTime")
        completion_absent = completion is None or completion == ""
        completion_is_late_success = (
            type(completion) is str
            and _RFC3339.fullmatch(str(completion)) is not None
            and counts["succeededCount"] == 1
            and counts["runningCount"] == 0
        )
        if (
            counts["succeededCount"] not in {0, 1}
            or counts["failedCount"] != 0
            or counts["cancelledCount"] != 0
            or counts["retriedCount"] != 0
            or counts["runningCount"] not in {0, 1}
            or counts["succeededCount"] + counts["runningCount"] > 1
            or not (completion_absent or completion_is_late_success)
        ):
            _fail("nonterminal provider state differs")
    return item, completed_state


def _proc_identity(proc_root: Path, pid: int) -> tuple[int, int]:
    try:
        raw = (proc_root / str(pid) / "stat").read_text(encoding="ascii")
        suffix = raw.rsplit(") ", maxsplit=1)[1].split()
        return int(suffix[1]), int(suffix[19])
    except (OSError, ValueError, IndexError) as exc:
        raise SourceV3FinisherError("launcher process identity is unavailable") from exc


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
        or state_root != REGISTRY_STATE_ROOT
        or state_root.is_symlink()
        or state_root.resolve(strict=False) != REGISTRY_STATE_ROOT
        or receipt.parent != REGISTRY_STATE_ROOT / "launchers"
        or receipt.is_symlink()
        or not receipt.is_file()
    ):
        _fail("canonical production launcher_registry receipt is absent")
    expected_hash = environment.get("NFL_LAUNCHER_REGISTRY_RECEIPT_SHA256", "")
    if (
        _SHA.fullmatch(expected_hash) is None
        or sha256(receipt.read_bytes()).hexdigest() != expected_hash
    ):
        _fail("launcher_registry receipt hash differs")
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
        or item.get("script_path") != str(Path(__file__).resolve())
        or item.get("owner") != "production"
        or item.get("lane") != JOB
        or item.get("target_run_id_prefixes") != [run_id]
        or type(wrapper_pid) is not int
        or int(wrapper_pid) <= 1
        or type(wrapper_ticks) is not int
        or int(wrapper_ticks) <= 0
        or _RFC3339.fullmatch(str(item.get("acquired_at_utc", ""))) is None
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
    lock_path = REGISTRY_STATE_ROOT / "launcher-locks" / lock_name
    if lock_path.is_symlink() or not lock_path.is_file() or not lock_probe(lock_path):
        _fail("canonical production launcher_registry lane lock is not held")


def build_run_freeze_v1(*, run_id: str, code_sha: str) -> tuple[dict[str, object], list[str]]:
    closure = batch_v3._trusted_dependency_closure_v3()
    plan, binding, plan_raw = batch_v3._trusted_capture_plan_v3(
        dependency_closure=closure
    )
    tasks = _sequence(plan.get("source_task_bindings"), label="capture-plan tasks")
    if len(tasks) != 54:
        _fail("source-v3 capture plan does not contain exactly 54 tasks")
    first = _mapping(tasks[0], label="capture-plan task0")
    task0_inventory = task0_v3._output_inventory(
        run_id=run_id,
        slate=_mapping(first.get("slate"), label="capture-plan task0 slate"),
    )
    batch_inventory = batch_v3._output_uri_inventory_v3(
        run_id=run_id, plan_value=plan
    )
    task0_values = _sequence(task0_inventory["uris"], label="task0 URIs")
    batch_values = _sequence(batch_inventory["uris"], label="batch URIs")
    if any(type(value) is not str for value in [*task0_values, *batch_values]):
        _fail("source-v3 output inventory contains a non-string URI")
    task0_uris = list(task0_values)
    batch_uris = list(batch_values)
    all_uris = sorted(set(task0_uris) | set(batch_uris))
    if (
        closure.get("source_commit_sha") != code_sha
        or binding.get("commit_sha") != code_sha
        or task0_inventory.get("uri_count") != 54
        or batch_inventory.get("uri_count") != 2_811
        or set(task0_uris) & set(batch_uris)
        or len(all_uris) != 2_865
    ):
        _fail("source-v3 frozen output inventory differs")
    freeze = {
        "schema_version": "corpus-r6-matchup-source-v3-host-freeze/v1",
        "run_id": run_id,
        "code_sha": code_sha,
        "capture_plan_v3_binding": binding,
        "capture_plan_file_sha256": sha256(plan_raw).hexdigest(),
        "capture_plan_file_bytes": len(plan_raw),
        "dependency_closure_sha256": closure["dependency_closure_sha256"],
        "task0_namespace": task0_inventory["result_root_uri"].rsplit("/", 1)[0] + "/",
        "task0_output_uri_count": 54,
        "task0_output_uri_manifest_sha256": batch_v3.canonical_sha256(task0_uris),
        "task0_result_root_uri": task0_inventory["result_root_uri"],
        "batch_namespace": batch_inventory["namespace"],
        "batch_output_uri_count": 2_811,
        "batch_output_uri_manifest_sha256": batch_inventory["uri_manifest_sha256"],
        "source_release_v3_root_uri": batch_inventory["source_release_root_uri"],
        "batch_release_v3_root_uri": batch_inventory["terminal_batch_root_uri"],
        "all_output_uri_count": 2_865,
        "all_output_uri_manifest_sha256": batch_v3.canonical_sha256(all_uris),
        "phase_order": list(PHASES),
        "task_count_per_provider_execution": 1,
        "max_retries": 0,
        "outcomes_allowed": False,
        "automatic_relaunch_after_intent": False,
        "exact_output_head_preflight_required": True,
        "object_listing_allowed": False,
        "complete": True,
    }
    return freeze, all_uris


def validate_final_source_identities(
    phases: Mapping[str, Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    if set(phases) != set(PHASES):
        _fail("source-v3 terminal phase set differs")
    publish_receipt = _mapping(
        phases["publish"].get("provider_receipt"),
        label="publisher provider receipt",
    )
    reopen_receipt = _mapping(
        phases["reopen"].get("provider_receipt"),
        label="reopener provider receipt",
    )
    publish_output = _mapping(
        publish_receipt.get("operator_output"),
        label="publisher operator output",
    )
    reopen_output = _mapping(
        reopen_receipt.get("operator_output"),
        label="reopener operator output",
    )
    source_identity = _identity(
        reopen_output.get("source_release_v3_identity"),
        label="independently reopened source-release-v3 identity",
    )
    batch_identity = _identity(
        reopen_output.get("batch_release_identity"),
        label="independently reopened batch-v3 identity",
    )
    names_raw = [phases[phase].get("execution_name") for phase in PHASES]
    if any(
        type(name) is not str or _EXECUTION.fullmatch(str(name)) is None
        for name in names_raw
    ):
        _fail("source-v3 final execution name differs")
    names = [str(name) for name in names_raw]
    if (
        len(set(names)) != 4
        or source_identity == batch_identity
        or source_identity
        != _identity(
            publish_output.get("source_release_v3_identity"),
            label="published source-release-v3 identity",
        )
        or batch_identity
        != _identity(
            publish_output.get("batch_release_identity"),
            label="published batch-v3 identity",
        )
        or reopen_output.get("publisher_execution_name") != names[2]
        or reopen_output.get("reopen_execution_name") != names[3]
        or reopen_output.get("task0_worker_execution_name") != names[0]
        or reopen_output.get("task0_verifier_execution_name") != names[1]
        or reopen_output.get("write_disabled_public_reopen_complete") is not True
        or reopen_output.get("cloud_mutation_performed") is not False
    ):
        _fail("source-v3 final independent reopen binding differs")
    return source_identity, batch_identity


def _gcs_parts(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        _fail("source-v3 output URI is not GCS")
    bucket, separator, name = uri[5:].partition("/")
    if not separator or not bucket or not name or "//" in name or ".." in name.split("/"):
        _fail("source-v3 output URI differs")
    return bucket, name


def make_object_exists() -> Callable[[str], bool]:
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise SourceV3FinisherError("google-cloud-storage is required") from exc
    local = threading.local()

    def exists(uri: str) -> bool:
        client = getattr(local, "client", None)
        if client is None:
            client = storage.Client(project=PROJECT)
            local.client = client
        bucket, name = _gcs_parts(uri)
        return bool(client.bucket(bucket).blob(name).exists(client=client, timeout=30))

    return exists


class SourceV3Finisher:
    def __init__(
        self,
        *,
        run_id: str,
        code_sha: str,
        build_id: str,
        image: str,
        run_dir: Path,
        runner: CommandRunner,
        object_exists: Callable[[str], bool],
        provider_receipt_loader: Callable[
            [Mapping[str, object]], tuple[dict[str, object], dict[str, object]]
        ],
        poll_interval_seconds: int,
        max_polls: int,
        reconcile_polls: int,
        result_polls: int,
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
            _fail("source-v3 finisher immutable inputs differ")
        if (
            not 1 <= poll_interval_seconds <= 60
            or not 1 <= max_polls <= 5_000
            or not 1 <= reconcile_polls <= 120
            or not 1 <= result_polls <= 120
            or not 1 <= preflight_workers <= 32
        ):
            _fail("source-v3 finisher bounds differ")
        self.run_id = run_id
        self.code_sha = code_sha
        self.build_id = build_id
        self.image = image
        self.run_dir = _validated_run_dir(run_dir, run_id=run_id)
        self.runner = runner
        self.object_exists = object_exists
        self.provider_receipt_loader = provider_receipt_loader
        self.poll_interval_seconds = poll_interval_seconds
        self.max_polls = max_polls
        self.reconcile_polls = reconcile_polls
        self.result_polls = result_polls
        self.preflight_workers = preflight_workers
        self.sleeper = sleeper
        self.recovery_executions = dict(recovery_executions or {})
        for phase, pair in self.recovery_executions.items():
            if (
                phase not in PHASES
                or type(pair) is not tuple
                or len(pair) != 2
                or _EXECUTION.fullmatch(pair[0]) is None
                or _UUID.fullmatch(pair[1]) is None
            ):
                _fail("source-v3 recovery execution identity differs")

    @property
    def digest(self) -> str:
        return self.image.rsplit("@", 1)[-1]

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
                "gcloud",
                "builds",
                "describe",
                self.build_id,
                "--project",
                PROJECT,
                "--format=json",
            ),
            label="source-v3 provider build",
        )

    def _describe_execution(self, name: str) -> dict[str, object] | None:
        result = self.runner.run(
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
            cwd=ROOT,
        )
        if result.returncode != 0:
            return None
        return _parse_json(result.stdout, label=f"provider execution {name}")

    def _latest_name(self, *, required: bool = True) -> str | None:
        result = self.runner.run(
            (
                "gcloud",
                "run",
                "jobs",
                "describe",
                JOB,
                "--project",
                PROJECT,
                "--region",
                REGION,
                "--format=json",
            ),
            cwd=ROOT,
        )
        if result.returncode != 0:
            if required:
                _fail("source-v3 reused job command failed")
            return None
        job = _parse_json(result.stdout, label="source-v3 reused job")
        metadata = _mapping(job.get("metadata"), label="job metadata")
        status = _mapping(job.get("status"), label="job status")
        latest_value = status.get("latestCreatedExecution")
        if latest_value is None and not required:
            return None
        latest = _mapping(latest_value, label="job latest execution")
        name = latest.get("name")
        if (
            metadata.get("name") != JOB
            or metadata.get("uid") != JOB_UID
            or type(name) is not str
            or _EXECUTION.fullmatch(str(name)) is None
        ):
            _fail("reused job latest execution differs")
        return str(name)

    def _phase_payload(
        self, phase: str, prior: Mapping[str, Mapping[str, object]]
    ) -> tuple[bytes, str, str, str]:
        worker = "DISABLED"
        verifier = "DISABLED"
        publisher = "DISABLED"
        if phase == "worker":
            payload = b"{}"
        elif phase == "verify":
            worker_receipt = prior["worker"]["provider_receipt"]
            payload = task0_v3._provider_payload_bytes(worker_receipt)
            worker = str(prior["worker"]["execution_name"])
        elif phase == "publish":
            payload = task0_v3._provider_payload_bytes(
                prior["verify"]["controller_result"]["provider_receipt_identity"]
            )
            worker = str(prior["worker"]["execution_name"])
            verifier = str(prior["verify"]["execution_name"])
        elif phase == "reopen":
            payload = task0_v3._provider_payload_bytes(
                prior["publish"]["controller_result"]["provider_receipt_identity"]
            )
            worker = str(prior["worker"]["execution_name"])
            verifier = str(prior["verify"]["execution_name"])
            publisher = str(prior["publish"]["execution_name"])
        else:
            _fail("source-v3 phase differs")
        return payload, worker, verifier, publisher

    def _launcher_args(
        self, phase: str, prior: Mapping[str, Mapping[str, object]]
    ) -> tuple[str, ...]:
        prefix = (str(LAUNCHER), phase, self.image, self.code_sha, self.build_id)
        if phase == "worker":
            return (*prefix, self.run_id)
        if phase == "verify":
            return (*prefix, str(prior["worker"]["execution_name"]))
        if phase == "publish":
            return (
                *prefix,
                self.run_id,
                str(prior["verify"]["execution_name"]),
            )
        if phase == "reopen":
            return (
                *prefix,
                self.run_id,
                str(prior["publish"]["execution_name"]),
            )
        _fail("source-v3 launcher phase differs")

    def _validate_provider(
        self,
        value: object,
        *,
        phase: str,
        name: str,
        uid: str | None,
        payload: bytes,
        worker: str,
        verifier: str,
        publisher: str,
    ) -> tuple[dict[str, object], str]:
        return validate_provider_execution(
            value,
            phase=phase,
            execution_name=name,
            execution_uid=uid,
            code_sha=self.code_sha,
            build_id=self.build_id,
            image=self.image,
            run_id=self.run_id,
            payload=payload,
            worker_execution=worker,
            verifier_execution=verifier,
            publisher_execution=publisher,
        )

    def _record_failure(
        self,
        *,
        phase: str,
        category: str,
        intent_sha256: str,
        execution_name: str | None = None,
        execution_uid: str | None = None,
        provider_sha256: str | None = None,
    ) -> None:
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{2,80}", category) is None:
            _fail("source-v3 failure category differs")
        path = self._phase_path(phase, f"failures/{category}.json")
        if path.exists():
            existing = _read_canonical(path, label=f"persisted {phase} failure")
            if existing != {
                "schema_version": "corpus-r6-matchup-source-v3-host-failure/v1",
                "run_id": self.run_id,
                "phase": phase,
                "category": category,
                "intent_sha256": intent_sha256,
                "execution_name": execution_name,
                "execution_uid": execution_uid,
                "provider_sha256": provider_sha256,
                "automatic_relaunch": False,
                "manual_recovery_requires_exact_name_and_uid": True,
                "complete": True,
            }:
                _fail(f"persisted {phase} failure differs")
            return
        body = {
            "schema_version": "corpus-r6-matchup-source-v3-host-failure/v1",
            "run_id": self.run_id,
            "phase": phase,
            "category": category,
            "intent_sha256": intent_sha256,
            "execution_name": execution_name,
            "execution_uid": execution_uid,
            "provider_sha256": provider_sha256,
            "automatic_relaunch": False,
            "manual_recovery_requires_exact_name_and_uid": True,
            "complete": True,
        }
        _publish_once(path, canonical_bytes(body))

    def _wait_for_latest_change(
        self,
        *,
        phase: str,
        before_name: str,
        expected_name: str | None,
        payload: bytes,
        worker: str,
        verifier: str,
        publisher: str,
    ) -> tuple[str, str, dict[str, object]] | None:
        for index in range(self.reconcile_polls):
            latest = self._latest_name(required=False)
            if latest is None:
                if index + 1 < self.reconcile_polls:
                    self.sleeper(self.poll_interval_seconds)
                continue
            if expected_name is not None and latest != expected_name:
                if latest != before_name:
                    _fail(f"{phase} provider latest changed to an unexpected execution")
            elif latest != before_name:
                observed = self._describe_execution(latest)
                if observed is not None:
                    provider, _ = self._validate_provider(
                        observed,
                        phase=phase,
                        name=latest,
                        uid=None,
                        payload=payload,
                        worker=worker,
                        verifier=verifier,
                        publisher=publisher,
                    )
                    uid = str(_mapping(provider["metadata"], label="provider metadata")["uid"])
                    return latest, uid, provider
            if index + 1 < self.reconcile_polls:
                self.sleeper(self.poll_interval_seconds)
        return None

    def _validate_intent(
        self,
        value: object,
        *,
        phase: str,
        request: Mapping[str, object],
    ) -> dict[str, object]:
        intent = _mapping(value, label=f"persisted {phase} intent")
        before = _mapping(
            intent.get("provider_latest_before"),
            label=f"{phase} intent previous latest",
        )
        if (
            set(intent)
            != {
                "schema_version",
                "run_id",
                "phase",
                "request_sha256",
                "provider_latest_before",
                "automatic_relaunch",
                "ambiguous_return_recovery",
                "complete",
            }
            or intent.get("schema_version")
            != "corpus-r6-matchup-source-v3-host-launch-intent/v1"
            or intent.get("run_id") != self.run_id
            or intent.get("phase") != phase
            or intent.get("request_sha256") != canonical_sha256(dict(request))
            or set(before) != {"name", "uid"}
            or type(before.get("name")) is not str
            or _EXECUTION.fullmatch(str(before["name"])) is None
            or type(before.get("uid")) is not str
            or _UUID.fullmatch(str(before["uid"])) is None
            or intent.get("automatic_relaunch") is not False
            or intent.get("ambiguous_return_recovery")
            != "exact-provider-latest-name-uid-envelope-only"
            or intent.get("complete") is not True
        ):
            _fail(f"persisted {phase} intent differs")
        return intent

    def _validate_launch_recovery(
        self,
        value: object,
        *,
        phase: str,
        request: Mapping[str, object],
        intent: Mapping[str, object],
        payload: bytes,
        worker: str,
        verifier: str,
        publisher: str,
    ) -> tuple[dict[str, object], dict[str, object]]:
        item = _mapping(value, label=f"persisted {phase} launch recovery")
        execution = _mapping(
            item.get("execution"), label=f"persisted {phase} recovery execution"
        )
        provider_value = _mapping(
            item.get("provider_attribution"),
            label=f"persisted {phase} recovery provider attribution",
        )
        if (
            set(item)
            != {
                "schema_version",
                "run_id",
                "phase",
                "execution",
                "request_sha256",
                "intent_sha256",
                "provider_attribution_method",
                "provider_attribution",
                "provider_sha256_at_attribution",
                "controller_launch",
                "launch_repeated",
                "complete",
            }
            or item.get("schema_version")
            != "corpus-r6-matchup-source-v3-host-launch-recovery/v2"
            or item.get("run_id") != self.run_id
            or item.get("phase") != phase
            or set(execution) != {"name", "uid"}
            or type(execution.get("name")) is not str
            or _EXECUTION.fullmatch(str(execution["name"])) is None
            or type(execution.get("uid")) is not str
            or _UUID.fullmatch(str(execution["uid"])) is None
            or item.get("request_sha256") != canonical_sha256(dict(request))
            or item.get("intent_sha256") != canonical_sha256(dict(intent))
            or item.get("provider_attribution_method")
            not in {
                "provider-latest-after-consumed-intent",
                "operator-supplied-exact-name-and-uid",
            }
            or item.get("controller_launch") is not None
            or item.get("launch_repeated") is not False
            or item.get("complete") is not True
        ):
            _fail(f"persisted {phase} launch recovery differs")
        provider, _ = self._validate_provider(
            provider_value,
            phase=phase,
            name=str(execution["name"]),
            uid=str(execution["uid"]),
            payload=payload,
            worker=worker,
            verifier=verifier,
            publisher=publisher,
        )
        if item.get("provider_sha256_at_attribution") != canonical_sha256(provider):
            _fail(f"persisted {phase} launch recovery provider differs")
        supplied = self.recovery_executions.get(phase)
        if supplied is not None and supplied != (
            str(execution["name"]),
            str(execution["uid"]),
        ):
            _fail(f"persisted {phase} recovery identity differs from operator input")
        return item, provider

    def _launch_recovery_receipt(
        self,
        *,
        phase: str,
        request: Mapping[str, object],
        intent: Mapping[str, object],
        provider: Mapping[str, object],
        name: str,
        uid: str,
        method: str,
        payload: bytes,
        worker: str,
        verifier: str,
        publisher: str,
    ) -> dict[str, object]:
        receipt = {
            "schema_version": (
                "corpus-r6-matchup-source-v3-host-launch-recovery/v2"
            ),
            "run_id": self.run_id,
            "phase": phase,
            "execution": {"name": name, "uid": uid},
            "request_sha256": canonical_sha256(dict(request)),
            "intent_sha256": canonical_sha256(dict(intent)),
            "provider_attribution_method": method,
            "provider_attribution": dict(provider),
            "provider_sha256_at_attribution": canonical_sha256(dict(provider)),
            "controller_launch": None,
            "launch_repeated": False,
            "complete": True,
        }
        validated, _ = self._validate_launch_recovery(
            receipt,
            phase=phase,
            request=request,
            intent=intent,
            payload=payload,
            worker=worker,
            verifier=verifier,
            publisher=publisher,
        )
        return validated

    def _launcher_attribution_context(
        self,
        *,
        phase: str,
        request: Mapping[str, object],
    ) -> tuple[str, dict[str, object] | None]:
        """Recover the original fresh-call attribution from durable raw bytes."""

        return_path = self._phase_path(phase, "launcher-return.json")
        stdout_path = self._phase_path(phase, "launcher-stdout.raw")
        stderr_path = self._phase_path(phase, "launcher-stderr.raw")
        if (
            not return_path.exists()
            or not stdout_path.exists()
            or not stderr_path.exists()
        ):
            _fail(f"{phase} launcher attribution evidence is incomplete")
        item = _read_canonical(return_path, label=f"persisted {phase} launcher return")
        stdout = _read_private_raw(
            stdout_path, label=f"persisted {phase} launcher stdout"
        )
        stderr = _read_private_raw(
            stderr_path, label=f"persisted {phase} launcher stderr"
        )
        if (
            set(item)
            != {
                "schema_version",
                "run_id",
                "phase",
                "returncode",
                "stdout_sha256",
                "stdout_bytes",
                "stderr_sha256",
                "stderr_bytes",
                "valid_controller_launch",
                "controller_execution_name",
                "launch_intent_preceded_call",
                "complete",
            }
            or item.get("schema_version")
            != "corpus-r6-matchup-source-v3-host-launcher-return/v1"
            or item.get("run_id") != self.run_id
            or item.get("phase") != phase
            or type(item.get("returncode")) is not int
            or item.get("stdout_sha256") != sha256(stdout).hexdigest()
            or item.get("stdout_bytes") != len(stdout)
            or item.get("stderr_sha256") != sha256(stderr).hexdigest()
            or item.get("stderr_bytes") != len(stderr)
            or type(item.get("valid_controller_launch")) is not bool
            or item.get("launch_intent_preceded_call") is not True
            or item.get("complete") is not True
        ):
            _fail(f"persisted {phase} launcher return differs")
        if item["valid_controller_launch"] is True:
            if item["returncode"] != 0:
                _fail(f"persisted {phase} valid launcher return code differs")
            controller = validate_controller_launch(
                _parse_json(stdout, label=f"persisted {phase} launch stdout"),
                phase=phase,
                code_sha=self.code_sha,
                build_id=self.build_id,
                image=self.image,
                payload_sha256=str(request["payload_sha256"]),
            )
            name = _mapping(
                controller["execution"], label=f"persisted {phase} controller execution"
            )["name"]
            if item.get("controller_execution_name") != name:
                _fail(f"persisted {phase} controller execution name differs")
            return "controller-response-and-provider-latest", controller
        if item.get("controller_execution_name") is not None:
            _fail(f"persisted {phase} invalid controller execution name differs")
        return "provider-latest-after-ambiguous-controller-return", None

    def _attribution_receipt(
        self,
        *,
        phase: str,
        request: Mapping[str, object],
        intent: Mapping[str, object],
        provider: Mapping[str, object],
        name: str,
        uid: str,
        method: str,
        controller_launch: Mapping[str, object] | None,
    ) -> dict[str, object]:
        receipt = {
            "schema_version": (
                "corpus-r6-matchup-source-v3-host-provider-attribution/v1"
            ),
            "run_id": self.run_id,
            "phase": phase,
            "execution": {"name": name, "uid": uid},
            "request_sha256": canonical_sha256(dict(request)),
            "intent_sha256": canonical_sha256(dict(intent)),
            "provider_attribution_method": method,
            "provider_sha256_at_attribution": canonical_sha256(dict(provider)),
            "controller_launch": (
                None if controller_launch is None else dict(controller_launch)
            ),
            "launch_repeated": False,
            "complete": True,
        }
        return self._validate_attribution_receipt(
            receipt,
            phase=phase,
            request=request,
            intent=intent,
            provider=provider,
            name=name,
            uid=uid,
        )

    def _validate_attribution_receipt(
        self,
        value: object,
        *,
        phase: str,
        request: Mapping[str, object],
        intent: Mapping[str, object],
        provider: Mapping[str, object],
        name: str,
        uid: str,
    ) -> dict[str, object]:
        item = _mapping(value, label=f"persisted {phase} provider attribution receipt")
        execution = _mapping(
            item.get("execution"), label=f"persisted {phase} attributed execution"
        )
        controller = item.get("controller_launch")
        method = item.get("provider_attribution_method")
        if (
            set(item)
            != {
                "schema_version",
                "run_id",
                "phase",
                "execution",
                "request_sha256",
                "intent_sha256",
                "provider_attribution_method",
                "provider_sha256_at_attribution",
                "controller_launch",
                "launch_repeated",
                "complete",
            }
            or item.get("schema_version")
            != "corpus-r6-matchup-source-v3-host-provider-attribution/v1"
            or item.get("run_id") != self.run_id
            or item.get("phase") != phase
            or execution != {"name": name, "uid": uid}
            or _EXECUTION.fullmatch(name) is None
            or _UUID.fullmatch(uid) is None
            or item.get("request_sha256") != canonical_sha256(dict(request))
            or item.get("intent_sha256") != canonical_sha256(dict(intent))
            or method
            not in {
                "controller-response-and-provider-latest",
                "provider-latest-after-ambiguous-controller-return",
                "provider-latest-after-consumed-intent",
                "operator-supplied-exact-name-and-uid",
            }
            or item.get("provider_sha256_at_attribution")
            != canonical_sha256(dict(provider))
            or item.get("launch_repeated") is not False
            or item.get("complete") is not True
        ):
            _fail(f"persisted {phase} provider attribution receipt differs")
        if controller is not None:
            validated_controller = validate_controller_launch(
                controller,
                phase=phase,
                code_sha=self.code_sha,
                build_id=self.build_id,
                image=self.image,
                payload_sha256=str(request["payload_sha256"]),
            )
            if (
                method != "controller-response-and-provider-latest"
                or _mapping(
                    validated_controller["execution"],
                    label=f"persisted {phase} controller execution",
                )["name"]
                != name
            ):
                _fail(f"persisted {phase} controller attribution differs")
        elif method == "controller-response-and-provider-latest":
            _fail(f"persisted {phase} controller attribution is absent")
        return item

    def _revalidate_attributed_execution(
        self,
        *,
        phase: str,
        intent: Mapping[str, object],
        name: str,
        uid: str,
        payload: bytes,
        worker: str,
        verifier: str,
        publisher: str,
    ) -> dict[str, object]:
        before = _mapping(
            intent.get("provider_latest_before"),
            label=f"{phase} intent previous latest",
        )
        resolved = self._wait_for_latest_change(
            phase=phase,
            before_name=str(before["name"]),
            expected_name=name,
            payload=payload,
            worker=worker,
            verifier=verifier,
            publisher=publisher,
        )
        if resolved is None:
            _fail(f"{phase} attributed execution is not current provider latest")
        observed_name, observed_uid, current = resolved
        if observed_name != name or observed_uid != uid:
            _fail(f"{phase} attributed execution name/UID changed")
        return current

    def _load_launch(
        self,
        phase: str,
        *,
        request: Mapping[str, object],
        payload: bytes,
        worker: str,
        verifier: str,
        publisher: str,
    ) -> dict[str, object] | None:
        path = self._phase_path(phase, "launch.json")
        if not path.exists():
            return None
        item = _read_canonical(path, label=f"persisted {phase} launch")
        execution = _mapping(item.get("execution"), label=f"persisted {phase} execution")
        intent = self._validate_intent(
            _read_canonical(
                self._phase_path(phase, "launch-intent.json"),
                label=f"persisted {phase} intent",
            ),
            phase=phase,
            request=request,
        )
        controller_launch = item.get("controller_launch")
        expected_fields = {
            "schema_version",
            "run_id",
            "phase",
            "code_sha",
            "cloud_build_id",
            "provider_resolved_image",
            "execution",
            "request_sha256",
            "intent_sha256",
            "provider_attribution_method",
            "provider_sha256_at_attribution",
            "controller_launch",
            "automatic_relaunch",
            "complete",
        }
        if (
            set(item) != expected_fields
            or item.get("schema_version")
            != "corpus-r6-matchup-source-v3-host-launch/v1"
            or item.get("run_id") != self.run_id
            or item.get("phase") != phase
            or item.get("code_sha") != self.code_sha
            or item.get("cloud_build_id") != self.build_id
            or item.get("provider_resolved_image") != self.image
            or set(execution) != {"name", "uid", "task_count"}
            or type(execution.get("name")) is not str
            or _EXECUTION.fullmatch(str(execution["name"])) is None
            or type(execution.get("uid")) is not str
            or _UUID.fullmatch(str(execution["uid"])) is None
            or execution.get("task_count") != 1
            or item.get("request_sha256") != canonical_sha256(dict(request))
            or item.get("intent_sha256") != canonical_sha256(intent)
            or item.get("provider_attribution_method")
            not in {
                "controller-response-and-provider-latest",
                "provider-latest-after-ambiguous-controller-return",
                "provider-latest-after-consumed-intent",
                "operator-supplied-exact-name-and-uid",
            }
            or _SHA.fullmatch(str(item.get("provider_sha256_at_attribution", "")))
            is None
            or item.get("automatic_relaunch") is not False
            or item.get("complete") is not True
        ):
            _fail(f"persisted {phase} launch differs")
        attribution, _ = self._validate_provider(
            _read_canonical(
                self._phase_path(phase, "provider-attribution.json"),
                label=f"persisted {phase} provider attribution",
            ),
            phase=phase,
            name=str(execution["name"]),
            uid=str(execution["uid"]),
            payload=payload,
            worker=worker,
            verifier=verifier,
            publisher=publisher,
        )
        attribution_receipt = self._validate_attribution_receipt(
            _read_canonical(
                self._phase_path(phase, "provider-attribution-receipt.json"),
                label=f"persisted {phase} provider attribution receipt",
            ),
            phase=phase,
            request=request,
            intent=intent,
            provider=attribution,
            name=str(execution["name"]),
            uid=str(execution["uid"]),
        )
        recovery_path = self._phase_path(phase, "launch-recovery.json")
        if recovery_path.exists():
            recovery_receipt, recovery_provider = self._validate_launch_recovery(
                _read_canonical(
                    recovery_path,
                    label=f"persisted {phase} launch recovery",
                ),
                phase=phase,
                request=request,
                intent=intent,
                payload=payload,
                worker=worker,
                verifier=verifier,
                publisher=publisher,
            )
            if (
                recovery_provider != attribution
                or recovery_receipt["provider_attribution_method"]
                != attribution_receipt["provider_attribution_method"]
                or recovery_receipt["controller_launch"]
                != attribution_receipt["controller_launch"]
            ):
                _fail(f"persisted {phase} recovery attribution differs")
        if (
            canonical_sha256(attribution)
            != item["provider_sha256_at_attribution"]
            or item.get("provider_attribution_method")
            != attribution_receipt["provider_attribution_method"]
            or item.get("controller_launch")
            != attribution_receipt["controller_launch"]
        ):
            _fail(f"persisted {phase} provider attribution SHA differs")
        if controller_launch is not None:
            validated = validate_controller_launch(
                controller_launch,
                phase=phase,
                code_sha=self.code_sha,
                build_id=self.build_id,
                image=self.image,
                payload_sha256=str(request["payload_sha256"]),
            )
            if _mapping(validated["execution"], label="controller execution").get(
                "name"
            ) != execution["name"]:
                _fail(f"persisted {phase} controller execution differs")
        if (
            item.get("provider_attribution_method")
            == "controller-response-and-provider-latest"
        ) != (controller_launch is not None):
            _fail(f"persisted {phase} controller attribution differs")
        return item

    def _launch_or_recover(
        self,
        *,
        phase: str,
        prior: Mapping[str, Mapping[str, object]],
        payload: bytes,
        worker: str,
        verifier: str,
        publisher: str,
    ) -> dict[str, object]:
        phase_dir = self._phase_path(phase, "request.json").parent
        request = {
            "schema_version": "corpus-r6-matchup-source-v3-host-phase-request/v1",
            "run_id": self.run_id,
            "phase": phase,
            "code_sha": self.code_sha,
            "cloud_build_id": self.build_id,
            "provider_resolved_image": self.image,
            "payload_sha256": sha256(payload).hexdigest(),
            "payload_bytes": len(payload),
            "bound_worker_execution": worker,
            "bound_verifier_execution": verifier,
            "bound_publisher_execution": publisher,
            "outcomes_allowed": False,
            "complete": True,
        }
        _publish_once(phase_dir / "request.json", canonical_bytes(request))
        _publish_once(phase_dir / "request-payload.json", payload)

        persisted = self._load_launch(
            phase,
            request=request,
            payload=payload,
            worker=worker,
            verifier=verifier,
            publisher=publisher,
        )
        if persisted is not None:
            return persisted

        intent_path = phase_dir / "launch-intent.json"
        recovery_path = phase_dir / "launch-recovery.json"
        attribution_path = phase_dir / "provider-attribution.json"
        attribution_receipt_path = (
            phase_dir / "provider-attribution-receipt.json"
        )
        post_intent_paths = (
            recovery_path,
            attribution_path,
            attribution_receipt_path,
            phase_dir / "launcher-stdout.raw",
            phase_dir / "launcher-stderr.raw",
            phase_dir / "launcher-return.json",
        )
        if not intent_path.exists() and any(
            path.exists() for path in post_intent_paths
        ):
            _fail(f"{phase} post-intent evidence exists without its launch intent")
        if intent_path.exists():
            intent = self._validate_intent(
                _read_canonical(intent_path, label=f"persisted {phase} intent"),
                phase=phase,
                request=request,
            )
            before = _mapping(
                intent.get("provider_latest_before"),
                label="intent previous latest",
            )
            if attribution_receipt_path.exists() and not attribution_path.exists():
                _fail(f"{phase} provider attribution body is absent")

            if attribution_path.exists():
                attributed_value = _read_canonical(
                    attribution_path,
                    label=f"persisted {phase} provider attribution",
                )
                attributed_metadata = _mapping(
                    attributed_value.get("metadata"),
                    label=f"persisted {phase} attributed metadata",
                )
                name = str(attributed_metadata.get("name", ""))
                uid = str(attributed_metadata.get("uid", ""))
                provider, _ = self._validate_provider(
                    attributed_value,
                    phase=phase,
                    name=name,
                    uid=uid,
                    payload=payload,
                    worker=worker,
                    verifier=verifier,
                    publisher=publisher,
                )
                if recovery_path.exists():
                    recovery_receipt, recovery_provider = (
                        self._validate_launch_recovery(
                            _read_canonical(
                                recovery_path,
                                label=f"persisted {phase} launch recovery",
                            ),
                            phase=phase,
                            request=request,
                            intent=intent,
                            payload=payload,
                            worker=worker,
                            verifier=verifier,
                            publisher=publisher,
                        )
                    )
                    recovery_execution = _mapping(
                        recovery_receipt["execution"],
                        label=f"persisted {phase} recovery execution",
                    )
                    if (
                        recovery_execution != {"name": name, "uid": uid}
                        or recovery_provider != provider
                    ):
                        _fail(f"persisted {phase} recovery attribution differs")
                    method = str(
                        recovery_receipt["provider_attribution_method"]
                    )
                    controller_launch = recovery_receipt["controller_launch"]
                else:
                    if phase in self.recovery_executions:
                        _fail(
                            f"{phase} operator recovery differs from persisted "
                            "provider attribution"
                        )
                    method, controller_launch = (
                        self._launcher_attribution_context(
                            phase=phase,
                            request=request,
                        )
                    )

                if attribution_receipt_path.exists():
                    attribution_receipt = self._validate_attribution_receipt(
                        _read_canonical(
                            attribution_receipt_path,
                            label=(
                                f"persisted {phase} provider attribution receipt"
                            ),
                        ),
                        phase=phase,
                        request=request,
                        intent=intent,
                        provider=provider,
                        name=name,
                        uid=uid,
                    )
                    if (
                        attribution_receipt["provider_attribution_method"]
                        != method
                        or attribution_receipt["controller_launch"]
                        != controller_launch
                    ):
                        _fail(f"persisted {phase} attribution provenance differs")
                try:
                    self._revalidate_attributed_execution(
                        phase=phase,
                        intent=intent,
                        name=name,
                        uid=uid,
                        payload=payload,
                        worker=worker,
                        verifier=verifier,
                        publisher=publisher,
                    )
                except SourceV3FinisherError:
                    self._record_failure(
                        phase=phase,
                        category="launch-reconciliation-refused",
                        intent_sha256=canonical_sha256(intent),
                        execution_name=name,
                        execution_uid=uid,
                        provider_sha256=canonical_sha256(provider),
                    )
                    raise
            elif recovery_path.exists():
                recovery_receipt, provider = self._validate_launch_recovery(
                    _read_canonical(
                        recovery_path,
                        label=f"persisted {phase} launch recovery",
                    ),
                    phase=phase,
                    request=request,
                    intent=intent,
                    payload=payload,
                    worker=worker,
                    verifier=verifier,
                    publisher=publisher,
                )
                recovery_execution = _mapping(
                    recovery_receipt["execution"],
                    label=f"persisted {phase} recovery execution",
                )
                name = str(recovery_execution["name"])
                uid = str(recovery_execution["uid"])
                try:
                    self._revalidate_attributed_execution(
                        phase=phase,
                        intent=intent,
                        name=name,
                        uid=uid,
                        payload=payload,
                        worker=worker,
                        verifier=verifier,
                        publisher=publisher,
                    )
                except SourceV3FinisherError:
                    self._record_failure(
                        phase=phase,
                        category="launch-reconciliation-refused",
                        intent_sha256=canonical_sha256(intent),
                        execution_name=name,
                        execution_uid=uid,
                        provider_sha256=str(
                            recovery_receipt[
                                "provider_sha256_at_attribution"
                            ]
                        ),
                    )
                    raise
                method = str(recovery_receipt["provider_attribution_method"])
                controller_launch = recovery_receipt["controller_launch"]
            else:
                recovery = self.recovery_executions.get(phase)
                if recovery is not None:
                    try:
                        resolved = self._wait_for_latest_change(
                            phase=phase,
                            before_name=str(before["name"]),
                            expected_name=recovery[0],
                            payload=payload,
                            worker=worker,
                            verifier=verifier,
                            publisher=publisher,
                        )
                    except SourceV3FinisherError:
                        self._record_failure(
                            phase=phase,
                            category="launch-reconciliation-refused",
                            intent_sha256=canonical_sha256(intent),
                        )
                        raise
                    method = "operator-supplied-exact-name-and-uid"
                    if resolved is not None and resolved[1] != recovery[1]:
                        _fail(f"{phase} exact recovery execution UID differs")
                else:
                    try:
                        resolved = self._wait_for_latest_change(
                            phase=phase,
                            before_name=str(before["name"]),
                            expected_name=None,
                            payload=payload,
                            worker=worker,
                            verifier=verifier,
                            publisher=publisher,
                        )
                    except SourceV3FinisherError:
                        self._record_failure(
                            phase=phase,
                            category="launch-reconciliation-refused",
                            intent_sha256=canonical_sha256(intent),
                        )
                        raise
                    method = "provider-latest-after-consumed-intent"
                if resolved is None:
                    self._record_failure(
                        phase=phase,
                        category="launch-outcome-ambiguous-unresolved",
                        intent_sha256=canonical_sha256(intent),
                    )
                    _fail(
                        f"{phase} consumed intent remains ambiguous; never relaunch"
                    )
                name, uid, provider = resolved
                recovery_receipt = self._launch_recovery_receipt(
                    phase=phase,
                    request=request,
                    intent=intent,
                    provider=provider,
                    name=name,
                    uid=uid,
                    method=method,
                    payload=payload,
                    worker=worker,
                    verifier=verifier,
                    publisher=publisher,
                )
                _publish_once(recovery_path, canonical_bytes(recovery_receipt))
                controller_launch = None
        else:
            if phase in self.recovery_executions:
                _fail(f"{phase} recovery identity requires a consumed launch intent")
            before_name = self._latest_name()
            if before_name is None:
                _fail("prelaunch latest execution is unavailable")
            before_provider = self._describe_execution(before_name)
            if before_provider is None:
                _fail("prelaunch latest execution is unavailable")
            before_meta = _mapping(before_provider.get("metadata"), label="prelaunch metadata")
            before_labels = _mapping(
                before_meta.get("labels"), label="prelaunch labels"
            )
            before_status = _mapping(before_provider.get("status", {}), label="prelaunch status")
            completed = [
                row.get("status")
                for row in _sequence(
                    before_status.get("conditions", []),
                    label="prelaunch conditions",
                )
                if isinstance(row, Mapping) and row.get("type") == "Completed"
            ]
            before_counts: dict[str, int] = {}
            for key in ("runningCount", "succeededCount", "failedCount", "cancelledCount"):
                raw_count = before_status.get(key, 0)
                if type(raw_count) is not int or raw_count < 0:
                    _fail("reused job prelaunch execution counts differ")
                before_counts[key] = raw_count
            if (
                before_meta.get("name") != before_name
                or type(before_meta.get("uid")) is not str
                or _UUID.fullmatch(str(before_meta["uid"])) is None
                or before_labels.get("run.googleapis.com/job") != JOB
                or before_labels.get("run.googleapis.com/jobUid") != JOB_UID
                or completed not in (["True"], ["False"])
                or before_counts["runningCount"] != 0
                or before_counts["succeededCount"]
                + before_counts["failedCount"]
                + before_counts["cancelledCount"]
                < 1
                or type(before_status.get("completionTime")) is not str
                or _RFC3339.fullmatch(str(before_status["completionTime"])) is None
            ):
                _fail("reused job prelaunch latest is not terminal and idle")
            _publish_once(
                phase_dir / "provider-before-observation.json",
                canonical_bytes(before_provider),
            )
            if phase != "worker":
                expected_previous = str(prior[PHASES[PHASES.index(phase) - 1]]["execution_name"])
                if before_name != expected_previous:
                    _fail(f"{phase} previous phase is not the reused job latest")
            before_receipt = {
                "schema_version": "corpus-r6-matchup-source-v3-host-provider-before/v1",
                "run_id": self.run_id,
                "phase": phase,
                "latest_execution": {
                    "name": before_name,
                    "uid": before_meta["uid"],
                },
                "provider_sha256": canonical_sha256(before_provider),
                "terminal_and_idle": True,
                "complete": True,
            }
            _publish_once(phase_dir / "provider-before.json", canonical_bytes(before_receipt))
            intent = {
                "schema_version": "corpus-r6-matchup-source-v3-host-launch-intent/v1",
                "run_id": self.run_id,
                "phase": phase,
                "request_sha256": canonical_sha256(request),
                "provider_latest_before": {
                    "name": before_name,
                    "uid": before_meta["uid"],
                },
                "automatic_relaunch": False,
                "ambiguous_return_recovery": "exact-provider-latest-name-uid-envelope-only",
                "complete": True,
            }
            if not _publish_once(intent_path, canonical_bytes(intent)):
                _fail(f"{phase} launch intent create race")
            try:
                completed_call = self.runner.run(
                    self._launcher_args(phase, prior),
                    cwd=ROOT,
                    env={
                        **os.environ,
                        "CORPUS_R6_MATCHUP_SOURCE_TASK0_CLOUD_RELEASE": (
                            "I_UNDERSTAND_SOURCE_V3_TASK0_CHAIN"
                        ),
                    },
                )
            except OSError as exc:
                completed_call = CommandResult(
                    125,
                    b"",
                    f"launcher invocation raised {type(exc).__name__}\n".encode(
                        "ascii"
                    ),
                )
            _publish_once(phase_dir / "launcher-stdout.raw", completed_call.stdout)
            _publish_once(phase_dir / "launcher-stderr.raw", completed_call.stderr)
            controller_launch = None
            expected_name: str | None = None
            if completed_call.returncode == 0:
                try:
                    candidate = validate_controller_launch(
                        _parse_json(completed_call.stdout, label=f"{phase} launch stdout"),
                        phase=phase,
                        code_sha=self.code_sha,
                        build_id=self.build_id,
                        image=self.image,
                        payload_sha256=sha256(payload).hexdigest(),
                    )
                except SourceV3FinisherError:
                    candidate = None
                if candidate is not None:
                    controller_launch = candidate
                    launch_execution = _mapping(
                        candidate["execution"], label="launch execution"
                    )
                    expected_name = str(launch_execution["name"])
            launcher_return = {
                "schema_version": (
                    "corpus-r6-matchup-source-v3-host-launcher-return/v1"
                ),
                "run_id": self.run_id,
                "phase": phase,
                "returncode": completed_call.returncode,
                "stdout_sha256": sha256(completed_call.stdout).hexdigest(),
                "stdout_bytes": len(completed_call.stdout),
                "stderr_sha256": sha256(completed_call.stderr).hexdigest(),
                "stderr_bytes": len(completed_call.stderr),
                "valid_controller_launch": controller_launch is not None,
                "controller_execution_name": expected_name,
                "launch_intent_preceded_call": True,
                "complete": True,
            }
            _publish_once(
                phase_dir / "launcher-return.json",
                canonical_bytes(launcher_return),
            )
            try:
                resolved = self._wait_for_latest_change(
                    phase=phase,
                    before_name=before_name,
                    expected_name=expected_name,
                    payload=payload,
                    worker=worker,
                    verifier=verifier,
                    publisher=publisher,
                )
            except SourceV3FinisherError:
                self._record_failure(
                    phase=phase,
                    category="launch-reconciliation-refused",
                    intent_sha256=canonical_sha256(intent),
                )
                raise
            if resolved is None:
                self._record_failure(
                    phase=phase,
                    category="launch-outcome-ambiguous-unresolved",
                    intent_sha256=canonical_sha256(intent),
                )
                _fail(f"{phase} launch failed or is ambiguous; never relaunch")
            name, uid, provider = resolved
            method = (
                "controller-response-and-provider-latest"
                if controller_launch is not None
                else "provider-latest-after-ambiguous-controller-return"
            )

        _publish_once(attribution_path, canonical_bytes(provider))
        attribution_receipt = self._attribution_receipt(
            phase=phase,
            request=request,
            intent=intent,
            provider=provider,
            name=name,
            uid=uid,
            method=method,
            controller_launch=controller_launch,
        )
        _publish_once(
            attribution_receipt_path,
            canonical_bytes(attribution_receipt),
        )
        launch = {
            "schema_version": "corpus-r6-matchup-source-v3-host-launch/v1",
            "run_id": self.run_id,
            "phase": phase,
            "code_sha": self.code_sha,
            "cloud_build_id": self.build_id,
            "provider_resolved_image": self.image,
            "execution": {"name": name, "uid": uid, "task_count": 1},
            "request_sha256": canonical_sha256(request),
            "intent_sha256": canonical_sha256(intent),
            "provider_attribution_method": attribution_receipt[
                "provider_attribution_method"
            ],
            "provider_sha256_at_attribution": attribution_receipt[
                "provider_sha256_at_attribution"
            ],
            "controller_launch": attribution_receipt["controller_launch"],
            "automatic_relaunch": False,
            "complete": True,
        }
        _publish_once(phase_dir / "launch.json", canonical_bytes(launch))
        return launch

    def _poll_terminal(
        self,
        *,
        phase: str,
        name: str,
        uid: str,
        payload: bytes,
        worker: str,
        verifier: str,
        publisher: str,
        intent_sha256: str,
    ) -> dict[str, object]:
        terminal_path = self._phase_path(phase, "provider-terminal.json")
        if terminal_path.exists():
            provider, state = self._validate_provider(
                _read_canonical(terminal_path, label=f"persisted {phase} terminal"),
                phase=phase,
                name=name,
                uid=uid,
                payload=payload,
                worker=worker,
                verifier=verifier,
                publisher=publisher,
            )
            if state != "True":
                _fail(f"persisted {phase} provider is not successful")
            return provider
        poll_dir = self._phase_path(phase, "provider-polls")
        first_index = _next_observation_index(
            poll_dir,
            expression=re.compile(r"([0-9]{6})\.json"),
            label=f"{phase} provider polls",
        )
        for offset in range(self.max_polls):
            index = first_index + offset
            if index >= 1_000_000:
                _fail(f"{phase} provider poll receipt bound exceeded")
            observed = self._describe_execution(name)
            if observed is not None:
                try:
                    provider, state = self._validate_provider(
                        observed,
                        phase=phase,
                        name=name,
                        uid=uid,
                        payload=payload,
                        worker=worker,
                        verifier=verifier,
                        publisher=publisher,
                    )
                except SourceV3FinisherError:
                    self._record_failure(
                        phase=phase,
                        category="provider-envelope-refused",
                        intent_sha256=intent_sha256,
                        execution_name=name,
                        execution_uid=uid,
                    )
                    raise
                _publish_once(
                    poll_dir / f"{index:06d}.json",
                    canonical_bytes(provider),
                )
                if state == "True":
                    _publish_once(terminal_path, canonical_bytes(provider))
                    return provider
                if state == "False":
                    failure_path = self._phase_path(phase, "provider-failure.json")
                    _publish_once(failure_path, canonical_bytes(provider))
                    self._record_failure(
                        phase=phase,
                        category="provider-terminal-failure",
                        intent_sha256=intent_sha256,
                        execution_name=name,
                        execution_uid=uid,
                        provider_sha256=canonical_sha256(provider),
                    )
                    _fail(f"{phase} execution failed or was cancelled")
            if offset + 1 < self.max_polls:
                self.sleeper(self.poll_interval_seconds)
        self._record_failure(
            phase=phase,
            category="provider-poll-exhausted",
            intent_sha256=intent_sha256,
            execution_name=name,
            execution_uid=uid,
        )
        _fail(f"{phase} exact-name provider polling exhausted")

    def _collect_result(
        self, *, phase: str, name: str, uid: str
    ) -> tuple[dict[str, object], dict[str, object]]:
        phase_dir = self._phase_path(phase, "result.json").parent
        result_path = phase_dir / "result.json"
        receipt_path = phase_dir / "provider-receipt.json"
        if result_path.exists() and receipt_path.exists():
            result = validate_controller_result(
                _read_canonical(result_path, label=f"persisted {phase} result"),
                phase=phase,
                execution_name=name,
            )
            receipt = task0_v3.validate_task0_provider_receipt_v3(
                _read_canonical(receipt_path, label=f"persisted {phase} provider receipt")
            )
            spec = task0_v3.validate_provider_execution_spec_v3(
                receipt["provider_execution_spec"]
            )
            receipt_raw = task0_v3._provider_payload_bytes(receipt)
            identity = _identity(
                result["provider_receipt_identity"],
                label=f"persisted {phase} provider receipt identity",
            )
            if (
                identity["sha256"] != sha256(receipt_raw).hexdigest()
                or identity["bytes"] != len(receipt_raw)
                or spec["phase"] != phase
                or spec["execution_name"] != name
                or spec["execution_uid"] != uid
            ):
                _fail(f"persisted {phase} result/receipt binding differs")
            return result, receipt
        attempts_dir = phase_dir / "result-attempts"
        first_attempt = _next_observation_index(
            attempts_dir,
            expression=re.compile(
                r"([0-9]{6})\.(?:stdout\.raw|stderr\.raw|return\.json)"
            ),
            label=f"{phase} result attempts",
        )
        for offset in range(self.result_polls):
            attempt = first_attempt + offset
            if attempt >= 1_000_000:
                _fail(f"{phase} result attempt receipt bound exceeded")
            call = self.runner.run(
                (
                    str(LAUNCHER),
                    "result",
                    self.image,
                    self.code_sha,
                    self.build_id,
                    name,
                ),
                cwd=ROOT,
                env={
                    **os.environ,
                    "CORPUS_R6_MATCHUP_SOURCE_TASK0_CLOUD_RELEASE": (
                        "I_UNDERSTAND_SOURCE_V3_TASK0_CHAIN"
                    ),
                },
            )
            _publish_once(
                attempts_dir / f"{attempt:06d}.stdout.raw", call.stdout
            )
            _publish_once(
                attempts_dir / f"{attempt:06d}.stderr.raw", call.stderr
            )
            attempt_receipt = {
                "schema_version": (
                    "corpus-r6-matchup-source-v3-host-result-attempt/v1"
                ),
                "run_id": self.run_id,
                "phase": phase,
                "execution": {"name": name, "uid": uid},
                "attempt_index": attempt,
                "returncode": call.returncode,
                "stdout_sha256": sha256(call.stdout).hexdigest(),
                "stdout_bytes": len(call.stdout),
                "stderr_sha256": sha256(call.stderr).hexdigest(),
                "stderr_bytes": len(call.stderr),
                "launch_repeated": False,
                "complete": True,
            }
            _publish_once(
                attempts_dir / f"{attempt:06d}.return.json",
                canonical_bytes(attempt_receipt),
            )
            if call.returncode == 0:
                try:
                    result = validate_controller_result(
                        _parse_json(call.stdout, label=f"{phase} result stdout"),
                        phase=phase,
                        execution_name=name,
                    )
                    receipt, reopened_identity = self.provider_receipt_loader(
                        _identity(
                            result["provider_receipt_identity"],
                            label=f"{phase} provider receipt identity",
                        )
                    )
                    receipt = task0_v3.validate_task0_provider_receipt_v3(receipt)
                    spec = task0_v3.validate_provider_execution_spec_v3(
                        receipt["provider_execution_spec"]
                    )
                    receipt_raw = task0_v3._provider_payload_bytes(receipt)
                    identity = _identity(reopened_identity, label="reopened provider receipt")
                    if (
                        identity != result["provider_receipt_identity"]
                        or identity["sha256"] != sha256(receipt_raw).hexdigest()
                        or identity["bytes"] != len(receipt_raw)
                        or spec["phase"] != phase
                        or spec["execution_name"] != name
                        or spec["execution_uid"] != uid
                    ):
                        _fail(f"{phase} exact provider receipt binding differs")
                except Exception:
                    result = None
                if result is not None:
                    _publish_once(result_path, canonical_bytes(result))
                    _publish_once(receipt_path, canonical_bytes(receipt))
                    return result, receipt
            if offset + 1 < self.result_polls:
                self.sleeper(self.poll_interval_seconds)
        failure = {
            "schema_version": "corpus-r6-matchup-source-v3-host-result-failure/v1",
            "run_id": self.run_id,
            "phase": phase,
            "execution": {"name": name, "uid": uid},
            "attempt_index_first": first_attempt,
            "attempt_index_last": first_attempt + self.result_polls - 1,
            "attempt_count_this_invocation": self.result_polls,
            "launch_repeated": False,
            "exact_name_result_collection_may_be_resumed": True,
            "complete": True,
        }
        _publish_once(
            phase_dir
            / f"result-failures/{first_attempt + self.result_polls - 1:06d}.json",
            canonical_bytes(failure),
        )
        _fail(f"{phase} exact-name result collection exhausted")

    def _phase(
        self, phase: str, prior: Mapping[str, Mapping[str, object]]
    ) -> dict[str, object]:
        validate_exact_repository(code_sha=self.code_sha, runner=self.runner)
        payload, worker, verifier, publisher = self._phase_payload(phase, prior)
        launch = self._launch_or_recover(
            phase=phase,
            prior=prior,
            payload=payload,
            worker=worker,
            verifier=verifier,
            publisher=publisher,
        )
        execution = _mapping(launch["execution"], label=f"{phase} launch execution")
        name = str(execution["name"])
        uid = str(execution["uid"])
        self._poll_terminal(
            phase=phase,
            name=name,
            uid=uid,
            payload=payload,
            worker=worker,
            verifier=verifier,
            publisher=publisher,
            intent_sha256=str(launch["intent_sha256"]),
        )
        result, receipt = self._collect_result(phase=phase, name=name, uid=uid)
        return {
            "execution_name": name,
            "execution_uid": uid,
            "controller_result": result,
            "provider_receipt": receipt,
        }

    def _preflight(self, freeze: Mapping[str, object], output_uris: Sequence[str]) -> None:
        path = self._path("preflight.json")
        if path.exists():
            item = _read_canonical(path, label="persisted source-v3 preflight")
            if (
                item.get("schema_version")
                != "corpus-r6-matchup-source-v3-host-preflight/v1"
                or item.get("run_id") != self.run_id
                or item.get("code_sha") != self.code_sha
                or item.get("cloud_build_id") != self.build_id
                or item.get("provider_resolved_image") != self.image
                or item.get("freeze_sha256") != canonical_sha256(freeze)
                or item.get("checked_exact_output_uri_count") != 2_865
                or item.get("existing_output_uri_count") != 0
                or item.get("object_listing_used") is not False
                or item.get("complete") is not True
            ):
                _fail("persisted source-v3 preflight differs")
            return
        if any(self._phase_path(phase, "launch-intent.json").exists() for phase in PHASES):
            _fail("source-v3 preflight cannot be created after a launch intent")
        with ThreadPoolExecutor(max_workers=self.preflight_workers) as executor:
            existence = list(executor.map(self.object_exists, output_uris))
        existing = [uri for uri, present in zip(output_uris, existence, strict=True) if present]
        if existing:
            failure = {
                "schema_version": "corpus-r6-matchup-source-v3-host-preflight-failure/v1",
                "run_id": self.run_id,
                "freeze_sha256": canonical_sha256(freeze),
                "existing_output_uri_count": len(existing),
                "existing_output_uris": existing,
                "run_id_consumed": True,
                "complete": True,
            }
            _publish_once(self._path("preflight-failure.json"), canonical_bytes(failure))
            _fail("source-v3 output namespace is not fresh")
        receipt = {
            "schema_version": "corpus-r6-matchup-source-v3-host-preflight/v1",
            "run_id": self.run_id,
            "code_sha": self.code_sha,
            "cloud_build_id": self.build_id,
            "provider_resolved_image": self.image,
            "freeze_sha256": canonical_sha256(freeze),
            "checked_exact_output_uri_count": len(output_uris),
            "checked_exact_output_uri_manifest_sha256": batch_v3.canonical_sha256(
                list(output_uris)
            ),
            "existing_output_uri_count": 0,
            "object_listing_used": False,
            "direct_object_metadata_reads_only": True,
            "complete": True,
        }
        _publish_once(path, canonical_bytes(receipt))

    def finish(self) -> dict[str, object]:
        terminal_path = self._path("terminal.json")
        if terminal_path.exists():
            terminal = _read_canonical(terminal_path, label="persisted source-v3 terminal")
            freeze = _read_canonical(
                self._path("freeze.json"), label="persisted source-v3 freeze"
            )
            names = _mapping(
                terminal.get("phase_execution_names"),
                label="terminal execution names",
            )
            uids = _mapping(
                terminal.get("phase_execution_uids"),
                label="terminal execution UIDs",
            )
            receipt_identities = _mapping(
                terminal.get("phase_provider_receipt_identities"),
                label="terminal provider receipt identities",
            )
            if (
                set(terminal)
                != {
                    "schema_version",
                    "run_id",
                    "code_sha",
                    "cloud_build_id",
                    "provider_resolved_image",
                    "freeze_sha256",
                    "phase_execution_names",
                    "phase_execution_uids",
                    "phase_provider_receipt_identities",
                    "source_release_v3_identity",
                    "batch_release_v3_identity",
                    "terminal_batch_root_requested_last",
                    "same_process_deep_reopen_complete",
                    "independent_process_deep_reopen_complete",
                    "independent_reopen_write_disabled",
                    "automatic_relaunch",
                    "complete",
                }
                or terminal.get("schema_version")
                != "corpus-r6-matchup-source-v3-host-terminal/v1"
                or terminal.get("run_id") != self.run_id
                or terminal.get("code_sha") != self.code_sha
                or terminal.get("cloud_build_id") != self.build_id
                or terminal.get("provider_resolved_image") != self.image
                or terminal.get("freeze_sha256") != canonical_sha256(freeze)
                or set(names) != set(PHASES)
                or set(uids) != set(PHASES)
                or set(receipt_identities) != set(PHASES)
                or any(
                    type(names[phase]) is not str
                    or _EXECUTION.fullmatch(str(names[phase])) is None
                    or type(uids[phase]) is not str
                    or _UUID.fullmatch(str(uids[phase])) is None
                    for phase in PHASES
                )
                or len({str(names[phase]) for phase in PHASES}) != 4
                or any(
                    _identity(
                        receipt_identities[phase],
                        label=f"terminal {phase} provider receipt identity",
                    )
                    != receipt_identities[phase]
                    for phase in PHASES
                )
                or _identity(
                    terminal.get("source_release_v3_identity"),
                    label="terminal source-release-v3 identity",
                )
                != terminal.get("source_release_v3_identity")
                or _identity(
                    terminal.get("batch_release_v3_identity"),
                    label="terminal batch-release-v3 identity",
                )
                != terminal.get("batch_release_v3_identity")
                or terminal.get("terminal_batch_root_requested_last") is not True
                or terminal.get("same_process_deep_reopen_complete") is not True
                or terminal.get("independent_process_deep_reopen_complete") is not True
                or terminal.get("independent_reopen_write_disabled") is not True
                or terminal.get("automatic_relaunch") is not False
                or terminal.get("complete") is not True
            ):
                _fail("persisted source-v3 terminal differs")
            validate_exact_repository(code_sha=self.code_sha, runner=self.runner)
            return terminal

        validate_exact_repository(code_sha=self.code_sha, runner=self.runner)
        build = validate_build_provider(
            self._describe_build(),
            code_sha=self.code_sha,
            build_id=self.build_id,
            image=self.image,
        )
        _publish_once(
            self._path("build-provider.json"), canonical_bytes(build)
        )
        build_receipt = {
            "schema_version": "corpus-r6-matchup-source-v3-host-build/v1",
            "code_sha": self.code_sha,
            "cloud_build_id": self.build_id,
            "build_image_tag": (
                "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
                f"nfl-dfs:matchup-source-v3-{self.code_sha}"
            ),
            "provider_resolved_image": self.image,
            "provider_build_sha256": canonical_sha256(build),
            "provider_requested_and_resolved_git_source_exact": True,
            "complete": True,
        }
        _publish_once(self._path("build.json"), canonical_bytes(build_receipt))
        freeze, output_uris = build_run_freeze_v1(
            run_id=self.run_id, code_sha=self.code_sha
        )
        _publish_once(self._path("freeze.json"), canonical_bytes(freeze))
        output_manifest = {
            "schema_version": (
                "corpus-r6-matchup-source-v3-host-output-uri-manifest/v1"
            ),
            "run_id": self.run_id,
            "uris": list(output_uris),
            "uri_count": len(output_uris),
            "uri_manifest_sha256": batch_v3.canonical_sha256(
                list(output_uris)
            ),
            "derived_before_object_client_construction": True,
            "complete": True,
        }
        _publish_once(
            self._path("output-uri-manifest.json"),
            canonical_bytes(output_manifest),
        )
        self._preflight(freeze, output_uris)
        inputs = {
            "schema_version": "corpus-r6-matchup-source-v3-host-input/v1",
            "run_id": self.run_id,
            "code_sha": self.code_sha,
            "cloud_build_id": self.build_id,
            "provider_resolved_image": self.image,
            "freeze_sha256": canonical_sha256(freeze),
            "phase_order": list(PHASES),
            "one_continuous_launcher_registry_lease_required": True,
            "automatic_relaunch": False,
            "complete": True,
        }
        _publish_once(self._path("input.json"), canonical_bytes(inputs))

        phases: dict[str, dict[str, object]] = {}
        for phase in PHASES:
            phases[phase] = self._phase(phase, phases)
        source_identity, batch_identity = validate_final_source_identities(phases)
        _publish_once(
            self._path("source-release-v3-identity.json"), canonical_bytes(source_identity)
        )
        _publish_once(
            self._path("batch-release-v3-identity.json"), canonical_bytes(batch_identity)
        )
        terminal = {
            "schema_version": "corpus-r6-matchup-source-v3-host-terminal/v1",
            "run_id": self.run_id,
            "code_sha": self.code_sha,
            "cloud_build_id": self.build_id,
            "provider_resolved_image": self.image,
            "freeze_sha256": canonical_sha256(freeze),
            "phase_execution_names": {
                phase: phases[phase]["execution_name"] for phase in PHASES
            },
            "phase_execution_uids": {
                phase: phases[phase]["execution_uid"] for phase in PHASES
            },
            "phase_provider_receipt_identities": {
                phase: phases[phase]["controller_result"]["provider_receipt_identity"]
                for phase in PHASES
            },
            "source_release_v3_identity": source_identity,
            "batch_release_v3_identity": batch_identity,
            "terminal_batch_root_requested_last": True,
            "same_process_deep_reopen_complete": True,
            "independent_process_deep_reopen_complete": True,
            "independent_reopen_write_disabled": True,
            "automatic_relaunch": False,
            "complete": True,
        }
        _publish_once(terminal_path, canonical_bytes(terminal))
        return terminal


def _default_provider_receipt_loader(
    identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    return task0_v3._exact_reopen_provider_receipt_v3(identity)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--poll-interval-seconds", type=int, default=30)
    parser.add_argument("--max-polls", type=int, default=2_880)
    parser.add_argument("--reconcile-polls", type=int, default=20)
    parser.add_argument("--result-polls", type=int, default=20)
    parser.add_argument("--preflight-workers", type=int, default=8)
    for phase in PHASES:
        parser.add_argument(f"--{phase}-execution", default="")
        parser.add_argument(f"--{phase}-execution-uid", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.execute or args.confirmation != CONFIRMATION:
        _fail(
            "source-v3 finisher is default-off; require --execute --confirmation "
            + CONFIRMATION
        )
    if _RUN_ID.fullmatch(args.run_id) is None:
        _fail("source-v3 run ID differs")
    recovery: dict[str, tuple[str, str]] = {}
    for phase in PHASES:
        name = getattr(args, phase + "_execution")
        uid = getattr(args, phase + "_execution_uid")
        if bool(name) != bool(uid):
            _fail(f"{phase} recovery requires both exact execution name and UID")
        if name:
            recovery[phase] = (name, uid)
    verify_launcher_registry_lane(run_id=args.run_id, environment=os.environ)
    run_dir = args.run_dir or RUN_STATE_ROOT / args.run_id
    retained = _validated_run_dir(run_dir, run_id=args.run_id)
    lock_path = retained / "finisher.lock"
    try:
        lock_descriptor = os.open(
            lock_path,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except OSError as exc:
        raise SourceV3FinisherError("source-v3 local run lock differs") from exc
    lock_details = os.fstat(lock_descriptor)
    if (
        not stat.S_ISREG(lock_details.st_mode)
        or lock_details.st_uid != os.getuid()
        or lock_details.st_nlink != 1
        or stat.S_IMODE(lock_details.st_mode) != 0o600
    ):
        os.close(lock_descriptor)
        _fail("source-v3 local run lock identity differs")
    with os.fdopen(lock_descriptor, "a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SourceV3FinisherError(
                "another source-v3 finisher owns the local run lock"
            ) from exc
        finisher = SourceV3Finisher(
            run_id=args.run_id,
            code_sha=args.code_sha,
            build_id=args.build_id,
            image=args.image,
            run_dir=retained,
            runner=CommandRunner(),
            object_exists=make_object_exists(),
            provider_receipt_loader=_default_provider_receipt_loader,
            poll_interval_seconds=args.poll_interval_seconds,
            max_polls=args.max_polls,
            reconcile_polls=args.reconcile_polls,
            result_polls=args.result_polls,
            preflight_workers=args.preflight_workers,
            recovery_executions=recovery,
        )
        terminal = finisher.finish()
    sys.stdout.buffer.write(canonical_bytes(terminal))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SourceV3FinisherError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


__all__ = [
    "CommandResult",
    "CommandRunner",
    "CONFIRMATION",
    "PHASES",
    "SourceV3Finisher",
    "SourceV3FinisherError",
    "build_run_freeze_v1",
    "canonical_bytes",
    "canonical_sha256",
    "validate_build_provider",
    "validate_controller_launch",
    "validate_controller_result",
    "validate_exact_repository",
    "validate_final_source_identities",
    "validate_provider_execution",
    "verify_launcher_registry_lane",
]
