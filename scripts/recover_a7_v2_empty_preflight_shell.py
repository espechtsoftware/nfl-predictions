#!/usr/bin/env python3
"""Archive the exact empty A7-v2 local preflight shell, and nothing else.

This is an operator-side, local-only administrative recovery.  It has no
Cloud Run mutation, BigQuery, log API, object upload/delete, lease acquire, or
science/result read path.  Every cloud operation is a metadata read used to
prove that the interrupted local launcher created no attempt.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any, Final

from google.api_core.exceptions import NotFound
from google.cloud import storage


ROOT: Final = Path(__file__).resolve().parents[1]
PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
RUN_ID: Final = "20260820-a7-select-ladder-phase-s-incumbent-v2"
RECOVERY_ID: Final = "20260821-a7-v2-empty-preflight-shell-recovery-v1"
JOB: Final = "atlas-minimal-c-s2023-w1-v1"
JOB_UID: Final = "d6e4b8c1-5950-46b7-8869-7e34dbf29ad2"
JOB_GENERATION: Final = "12"
JOB_SPEC_SHA256: Final = (
    "c0e4b6985f79265373d8ada306575470a794f38426e25fbc9188daf551331f94"
)
CODE_SHA: Final = "7057554eb2d930be29e882745e52d271fde09339"
BUILD_ID: Final = "063251e8-888b-4d64-9c78-1346af5b12bf"
IMAGE: Final = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
    "sha256:f9ecbcc6a45046b4155bb22e0497e7b7c1c618655bad2a7852bfc8fb04c2370f"
)
INCIDENT_PID: Final = 2693633

PROTOCOL_PATH: Final = (
    "reports/2026-08-21-a7-v2-empty-preflight-shell-recovery-protocol.md"
)
PROTOCOL_SHA256: Final = (
    "94cd0eaf6a5501d491dad0d51061c3c46edffa1b91d77938f67f6f603c0a0aec"
)
FROZEN_SOURCE_SHA256: Final = {
    "reports/2026-08-20-a7-select-ladder-incumbent-pool-protocol-v2.md": (
        "dd85acbd48a40530b59a7e8e6e5a4c769cf039e55d23be3000320a29d8e434f2"
    ),
    "src/nfl_dfs/research/a7_select_ladder.py": (
        "f992cab6d0c9e6d84dc0a3c708acf5c268fc3954370ff6341f05f0f3ef7a782e"
    ),
    "scripts/run_a7_select_ladder.py": (
        "12958ac062c266f130235296e1145518f2c1d039aea8f39d2588b8f9bed61bb0"
    ),
    "scripts/cloud_a7_select_ladder.sh": (
        "7207dabf8dd0da56e51835fc20e3ad88333e17bd892f5c28803e7cc7eb53bd46"
    ),
    "scripts/watch_a7_select_ladder_queue.sh": (
        "af7a1f88e617c1d330c01f07b1d04e2a548d982daaf7ab6dd7dbc41bae858c48"
    ),
    "scripts/finish_a7_select_ladder.py": (
        "f9963fead2b4cccca035b03e09f0b17519c8e12e02273c2f93cad960982030d8"
    ),
}

PREFIX: Final = (
    "gs://nfl-predictions-503414-raw/research/a7-select-ladder-runs/"
    f"{RUN_ID}"
)
JOB_CLAIM_URI: Final = f"{PREFIX}/preflight/job-claim.json"
SMOKE_URI: Final = f"{PREFIX}/preflight/real-artifact-smoke.json"
SMOKE_TERMINAL_URI: Final = (
    f"{PREFIX}/preflight/real-artifact-smoke-terminal.json"
)
SUPPORT_URI: Final = f"{PREFIX}/preflight/support-census.json"
SUPPORT_TERMINAL_URI: Final = f"{PREFIX}/preflight/support-census-terminal.json"
FREEZE_URI: Final = f"{PREFIX}/preflight/freeze-manifest.json"
RESULT_URI: Final = f"{PREFIX}/result.json"
LEASE_URI: Final = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    "historical-outcome-active-v1.json"
)
REQUIRED_ABSENT_URIS: Final = (
    JOB_CLAIM_URI,
    SMOKE_URI,
    SMOKE_TERMINAL_URI,
    SUPPORT_URI,
    SUPPORT_TERMINAL_URI,
    FREEZE_URI,
    RESULT_URI,
)

DEFAULT_SHELL: Final = (
    ROOT / "reports/a7-select-ladder-preflight-runs" / RUN_ID
)
DEFAULT_HISTORICAL_OUT: Final = (
    ROOT / "reports/a7-select-ladder-runs" / RUN_ID
)
DEFAULT_HISTORICAL_PENDING: Final = (
    ROOT / "reports/a7-select-ladder-runs" / f".{RUN_ID}.prepare.pending"
)
DEFAULT_ARCHIVE: Final = (
    ROOT / "reports/a7-select-ladder-preflight-recovery-runs" / RECOVERY_ID
)
DEFAULT_LOG: Final = Path(
    "/home/erich/nfl-panels/a7-select-ladder-v2-chain.log"
)
ARCHIVED_SHELL_NAME: Final = "empty-preflight-shell"

EXPECTED_SHELL_STAT: Final = {
    "device": 2096,
    "inode": 360672,
    "mode": stat.S_IFDIR | 0o755,
    "links": 2,
    "uid": 1000,
    "gid": 1000,
    "size": 4096,
    "mtime_ns": 1787288151209315898,
    "ctime_ns": 1787288151209315898,
}
EXPECTED_LOG_STAT: Final = {
    "device": 2096,
    "inode": 360670,
    "mode": stat.S_IFREG | 0o644,
    "links": 1,
    "uid": 1000,
    "gid": 1000,
    "size": 0,
    "mtime_ns": 1787288149625316848,
    "ctime_ns": 1787288149625316848,
}

ANCHOR_JOB_PATH: Final = (
    "reports/b1-corpus-tail-runs/20260820-b1-corpus-tail-model-v1/"
    "job-after.json"
)
ANCHOR_JOB_SHA256: Final = (
    "dc9082f20a5d885b3aed722075617ce3830a6725d968295dd8f27f64dcac39c4"
)
ANCHOR_EXECUTIONS_PATH: Final = (
    "reports/b1-corpus-tail-runs/20260820-b1-corpus-tail-model-v1/"
    "job-executions-after.json"
)
ANCHOR_EXECUTIONS_SHA256: Final = (
    "4279fd1cb0df3903a460f698c25208470ccdbcb4b4809a38df6a095a4a1fc547"
)
ANCHOR_LAST_EXECUTION_PATH: Final = (
    "reports/b1-corpus-tail-runs/20260820-b1-corpus-tail-model-v1/"
    "harvest/execution.json"
)
ANCHOR_LAST_EXECUTION_SHA256: Final = (
    "4b43673aedb987b8c071bd1fc27820940bdbdb75b0e15440fe54e6919602ad3e"
)
LAST_EXECUTION: Final = "atlas-minimal-c-s2023-w1-v1-sm64k"
LAST_EXECUTION_UID: Final = "88cf04a0-79af-4a6f-bc7e-416a39717212"

RECEIPT_FILES: Final = (
    "job-metadata.json",
    "job-executions.json",
    "schedulers.json",
    "cloud-absence.json",
    "process-census.json",
    "incident.json",
)


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key is forbidden: {key}")
        value[key] = item
    return value


def _strict_json_bytes(raw: bytes, *, label: str) -> Any:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"A7-v2 empty-shell {label} is not strict JSON") from exc

    def walk(item: Any) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise RuntimeError(f"A7-v2 empty-shell {label} is non-finite")
        if isinstance(item, dict):
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return value


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _load_json(path: Path, *, label: str) -> Any:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"A7-v2 empty-shell {label} is absent")
    return _strict_json_bytes(path.read_bytes(), label=label)


def _git_blob(root: Path, code_sha: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), "show", f"{code_sha}:{relative}"],
        check=True,
        capture_output=True,
    ).stdout


GitLoader = Callable[[Path, str, str], bytes]
JsonLoader = Callable[[], Any]
ProcessLoader = Callable[[], list[dict[str, Any]]]


def _gcloud_json(arguments: Sequence[str], *, label: str) -> Any:
    process = subprocess.run(
        ["gcloud", *arguments, "--format=json"],
        check=True,
        capture_output=True,
    )
    return _strict_json_bytes(process.stdout, label=label)


def _describe_job() -> Any:
    return _gcloud_json(
        [
            "run", "jobs", "describe", JOB,
            "--project", PROJECT, "--region", REGION,
        ],
        label="live job metadata",
    )


def _list_executions() -> Any:
    return _gcloud_json(
        [
            "run", "jobs", "executions", "list", "--job", JOB,
            "--project", PROJECT, "--region", REGION,
        ],
        label="live execution census",
    )


def _list_schedulers() -> Any:
    return _gcloud_json(
        [
            "scheduler", "jobs", "list", "--project", PROJECT,
            "--location", REGION,
        ],
        label="live scheduler census",
    )


def _matching_processes() -> list[dict[str, Any]]:
    markers = (
        "watch_a7_select_ladder_queue.sh",
        "cloud_a7_select_ladder.sh",
        "run_a7_select_ladder.py",
        "finish_a7_select_ladder.py",
    )
    rows: list[dict[str, Any]] = []
    for entry in sorted(Path("/proc").glob("[0-9]*"), key=lambda p: int(p.name)):
        pid = int(entry.name)
        try:
            raw = (entry / "cmdline").read_bytes()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        command = raw.replace(b"\0", b" ").decode("utf-8", errors="replace").strip()
        if pid == INCIDENT_PID or any(marker in command for marker in markers):
            rows.append({"pid": pid, "command": command})
    return rows


def _stat_receipt(path: Path) -> dict[str, int]:
    value = path.lstat()
    return {
        "device": value.st_dev,
        "inode": value.st_ino,
        "mode": value.st_mode,
        "links": value.st_nlink,
        "uid": value.st_uid,
        "gid": value.st_gid,
        "size": value.st_size,
        "mtime_ns": value.st_mtime_ns,
        "ctime_ns": value.st_ctime_ns,
    }


def _validate_stat(
    path: Path, expected: Mapping[str, int], *, kind: str,
) -> dict[str, int]:
    if path.is_symlink() or not path.exists():
        raise RuntimeError(f"A7-v2 exact {kind} is absent or linked")
    actual = _stat_receipt(path)
    if actual != dict(expected):
        raise RuntimeError(f"A7-v2 exact {kind} identity differs")
    if kind == "empty preflight shell" and not stat.S_ISDIR(actual["mode"]):
        raise RuntimeError("A7-v2 empty preflight shell is not a directory")
    if kind == "watcher log" and not stat.S_ISREG(actual["mode"]):
        raise RuntimeError("A7-v2 watcher log is not a regular file")
    return actual


def _validate_sources(root: Path, *, git_loader: GitLoader) -> None:
    protocol = root / PROTOCOL_PATH
    if protocol.is_symlink() or not protocol.is_file() or \
            _sha(protocol) != PROTOCOL_SHA256:
        raise RuntimeError("A7-v2 empty-shell recovery protocol differs")
    for relative, expected in FROZEN_SOURCE_SHA256.items():
        local = root / relative
        if local.is_symlink() or not local.is_file() or _sha(local) != expected:
            raise RuntimeError(f"A7-v2 frozen local source differs: {relative}")
        if _sha_bytes(git_loader(root, CODE_SHA, relative)) != expected:
            raise RuntimeError(f"A7-v2 frozen committed source differs: {relative}")


def _anchor(
    root: Path, relative: str, expected_sha: str, *, label: str,
) -> Any:
    path = root / relative
    if path.is_symlink() or not path.is_file() or _sha(path) != expected_sha:
        raise RuntimeError(f"A7-v2 {label} anchor differs")
    return _load_json(path, label=label)


def _spec_sha(value: Mapping[str, Any]) -> str:
    spec = value.get("spec")
    if not isinstance(spec, dict) or not spec:
        raise RuntimeError("A7-v2 reused-job spec is absent")
    return _sha_bytes(_canonical_json(spec))


def _validate_job(value: Any, *, anchor: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("A7-v2 live job metadata differs")
    metadata = value.get("metadata")
    anchor_metadata = anchor.get("metadata")
    if not isinstance(metadata, dict) or not isinstance(anchor_metadata, dict) or \
            metadata.get("name") != JOB or metadata.get("uid") != JOB_UID or \
            str(metadata.get("generation")) != JOB_GENERATION or \
            _spec_sha(value) != JOB_SPEC_SHA256 or \
            _canonical_json(value.get("spec")) != _canonical_json(anchor.get("spec")):
        raise RuntimeError("A7-v2 reused job identity/spec changed")
    latest = value.get("status", {}).get("latestCreatedExecution", {})
    if not isinstance(latest, dict) or latest.get("name") != LAST_EXECUTION or \
            latest.get("completionStatus") != "EXECUTION_SUCCEEDED" or \
            latest.get("completionTimestamp") != "2026-08-21T00:17:24.845961Z":
        raise RuntimeError("A7-v2 reused job latest execution changed")
    return value


def _completed_status(value: Mapping[str, Any], *, label: str) -> str:
    status = value.get("status")
    if not isinstance(status, dict):
        raise RuntimeError(f"A7-v2 {label} status differs")
    rows = [
        item for item in status.get("conditions", [])
        if isinstance(item, dict) and item.get("type") == "Completed"
    ]
    if len(rows) != 1 or rows[0].get("status") not in {"True", "False"}:
        raise RuntimeError(f"A7-v2 {label} is not strictly terminal")
    return str(rows[0]["status"])


def _last_execution_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    metadata = value.get("metadata")
    status = value.get("status")
    if not isinstance(metadata, dict) or not isinstance(status, dict):
        raise RuntimeError("A7-v2 last execution envelope differs")
    conditions = [
        item for item in status.get("conditions", [])
        if isinstance(item, dict) and item.get("type") == "Completed"
    ]
    labels = metadata.get("labels")
    return {
        "name": metadata.get("name"),
        "uid": metadata.get("uid"),
        "generation": metadata.get("generation"),
        "creation_timestamp": metadata.get("creationTimestamp"),
        "job": labels.get("run.googleapis.com/job")
        if isinstance(labels, dict) else None,
        "job_uid": labels.get("run.googleapis.com/jobUid")
        if isinstance(labels, dict) else None,
        "job_generation": labels.get("run.googleapis.com/jobGeneration")
        if isinstance(labels, dict) else None,
        "spec": value.get("spec"),
        "completion_time": status.get("completionTime"),
        "completed": conditions[0].get("status") if len(conditions) == 1 else None,
        "succeeded": status.get("succeededCount", 0),
        "failed": status.get("failedCount", 0),
        "cancelled": status.get("cancelledCount", 0),
        "retried": status.get("retriedCount", 0),
    }


def _validate_executions(
    value: Any, *, prior_anchor: Any, last_anchor: Any,
) -> list[dict[str, Any]]:
    if not isinstance(prior_anchor, list) or len(prior_anchor) != 261 or \
            not isinstance(last_anchor, dict):
        raise RuntimeError("A7-v2 retained execution anchors differ")
    expected_names: list[str] = []
    for row in prior_anchor:
        if not isinstance(row, dict):
            raise RuntimeError("A7-v2 retained execution anchor row differs")
        name = row.get("metadata", {}).get("name")
        if not isinstance(name, str):
            raise RuntimeError("A7-v2 retained execution anchor name differs")
        _completed_status(row, label=f"retained execution {name}")
        expected_names.append(name)
    if len(set(expected_names)) != 261 or LAST_EXECUTION in expected_names:
        raise RuntimeError("A7-v2 retained execution anchor population differs")
    if _last_execution_identity(last_anchor) != {
        "name": LAST_EXECUTION,
        "uid": LAST_EXECUTION_UID,
        "generation": 1,
        "creation_timestamp": "2026-08-21T00:04:13.549125Z",
        "job": JOB,
        "job_uid": JOB_UID,
        "job_generation": JOB_GENERATION,
        "spec": last_anchor.get("spec"),
        "completion_time": "2026-08-21T00:17:24.845961Z",
        "completed": "True",
        "succeeded": 1,
        "failed": 0,
        "cancelled": 0,
        "retried": 0,
    }:
        raise RuntimeError("A7-v2 retained last execution identity differs")
    if not isinstance(value, list) or len(value) != 262:
        raise RuntimeError("A7-v2 live execution census population changed")
    live: dict[str, dict[str, Any]] = {}
    for row in value:
        if not isinstance(row, dict):
            raise RuntimeError("A7-v2 live execution census row differs")
        name = row.get("metadata", {}).get("name")
        if not isinstance(name, str) or name in live:
            raise RuntimeError("A7-v2 live execution census name differs")
        _completed_status(row, label=f"live execution {name}")
        live[name] = row
    if set(live) != {*expected_names, LAST_EXECUTION}:
        raise RuntimeError("A7-v2 live execution set changed")
    if _last_execution_identity(live[LAST_EXECUTION]) != \
            _last_execution_identity(last_anchor):
        raise RuntimeError("A7-v2 live last execution changed")
    return value


def _validate_schedulers(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise RuntimeError("A7-v2 scheduler census differs")
    marker = f"/jobs/{JOB}"
    for row in value:
        if not isinstance(row, dict):
            raise RuntimeError("A7-v2 scheduler row differs")
        target = row.get("httpTarget", {})
        uri = target.get("uri", "") if isinstance(target, dict) else ""
        if not isinstance(uri, str) or marker in uri:
            raise RuntimeError("A7-v2 reused job is scheduled")
    return value


def _gcs_parts(uri: str) -> tuple[str, str]:
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if match is None or ".." in match.group(2).split("/"):
        raise RuntimeError("A7-v2 empty-shell GCS URI differs")
    return match.group(1), match.group(2)


def _require_not_found(client: storage.Client, uri: str) -> None:
    bucket_name, name = _gcs_parts(uri)
    try:
        client.bucket(bucket_name).blob(name).reload()
    except NotFound:
        return
    raise RuntimeError(f"A7-v2 required-absent object exists: {uri}")


def _validate_cloud_absence(client: storage.Client) -> dict[str, Any]:
    bucket_name, prefix_name = _gcs_parts(PREFIX + "/")
    objects = list(client.list_blobs(bucket_name, prefix=prefix_name))
    if objects:
        raise RuntimeError("A7-v2 cloud prefix is not empty")
    for uri in REQUIRED_ABSENT_URIS:
        _require_not_found(client, uri)
    _require_not_found(client, LEASE_URI)
    return {
        "version": "a7-v2-empty-shell-cloud-absence-v1",
        "run_id": RUN_ID,
        "prefix": PREFIX,
        "prefix_objects": [],
        "direct_not_found_uris": list(REQUIRED_ABSENT_URIS),
        "historical_outcome_lease": {"uri": LEASE_URI, "state": "absent"},
        "authentication_or_network_errors_count_as_absent": False,
    }


def _reference(path: Path, root: Path) -> dict[str, str]:
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise RuntimeError("A7-v2 recovery receipt escaped repository") from exc
    return {"path": relative, "sha256": _sha(path)}


def _write_durable(path: Path, raw: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_dir(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ledger(path: Path, names: Sequence[str]) -> bytes:
    return "".join(f"{_sha(path / name)}  {name}\n" for name in names).encode()


def _default_now() -> datetime:
    return datetime.now(timezone.utc)


def recover(
    *,
    execute: bool,
    root: Path = ROOT,
    shell: Path = DEFAULT_SHELL,
    historical_out: Path = DEFAULT_HISTORICAL_OUT,
    historical_pending: Path = DEFAULT_HISTORICAL_PENDING,
    archive: Path = DEFAULT_ARCHIVE,
    log_path: Path = DEFAULT_LOG,
    expected_shell_stat: Mapping[str, int] = EXPECTED_SHELL_STAT,
    expected_log_stat: Mapping[str, int] = EXPECTED_LOG_STAT,
    client: storage.Client | None = None,
    job_loader: JsonLoader = _describe_job,
    executions_loader: JsonLoader = _list_executions,
    schedulers_loader: JsonLoader = _list_schedulers,
    process_loader: ProcessLoader = _matching_processes,
    git_loader: GitLoader = _git_blob,
    now: Callable[[], datetime] = _default_now,
) -> dict[str, Any]:
    if not execute:
        raise RuntimeError("A7-v2 empty-shell recovery requires explicit execute")
    if archive.exists() or archive.is_symlink():
        raise RuntimeError("A7-v2 empty-shell recovery archive already exists")
    for target, label in (
        (historical_out, "historical run"),
        (historical_pending, "historical pending run"),
    ):
        if target.exists() or target.is_symlink():
            raise RuntimeError(f"A7-v2 local {label} unexpectedly exists")

    _validate_sources(root, git_loader=git_loader)
    shell_stat = _validate_stat(
        shell, expected_shell_stat, kind="empty preflight shell",
    )
    if any(True for _entry in os.scandir(shell)):
        raise RuntimeError("A7-v2 preflight shell is not exactly empty")
    log_stat = _validate_stat(log_path, expected_log_stat, kind="watcher log")
    log_raw = log_path.read_bytes()
    if log_raw or _sha_bytes(log_raw) != sha256(b"").hexdigest():
        raise RuntimeError("A7-v2 watcher log is not exactly empty")
    processes = process_loader()
    if processes:
        raise RuntimeError("A7-v2 local watcher/launcher process still exists")

    anchor_job = _anchor(
        root, ANCHOR_JOB_PATH, ANCHOR_JOB_SHA256, label="job",
    )
    prior_executions = _anchor(
        root, ANCHOR_EXECUTIONS_PATH, ANCHOR_EXECUTIONS_SHA256,
        label="execution-census",
    )
    last_execution = _anchor(
        root, ANCHOR_LAST_EXECUTION_PATH, ANCHOR_LAST_EXECUTION_SHA256,
        label="last-execution",
    )
    if not isinstance(anchor_job, dict) or _spec_sha(anchor_job) != \
            JOB_SPEC_SHA256:
        raise RuntimeError("A7-v2 retained job anchor spec differs")

    job = _validate_job(job_loader(), anchor=anchor_job)
    executions = _validate_executions(
        executions_loader(), prior_anchor=prior_executions,
        last_anchor=last_execution,
    )
    schedulers = _validate_schedulers(schedulers_loader())
    storage_client = client or storage.Client(project=PROJECT)
    cloud_absence = _validate_cloud_absence(storage_client)

    captured = now()
    if captured.tzinfo is None or captured.utcoffset() != timezone.utc.utcoffset(captured):
        raise RuntimeError("A7-v2 recovery capture time is not UTC")
    captured_at = captured.isoformat()
    process_receipt = {
        "version": "a7-v2-empty-shell-process-census-v1",
        "run_id": RUN_ID,
        "incident_pid": INCIDENT_PID,
        "matching_processes": [],
        "captured_at": captured_at,
    }
    incident = {
        "version": "a7-v2-empty-preflight-shell-incident-v1",
        "recovery_id": RECOVERY_ID,
        "run_id": RUN_ID,
        "captured_at": captured_at,
        "source": {
            "code_sha": CODE_SHA,
            "build_id": BUILD_ID,
            "image": IMAGE,
            "frozen_source_sha256": dict(FROZEN_SOURCE_SHA256),
        },
        "protocol": {"path": PROTOCOL_PATH, "sha256": PROTOCOL_SHA256},
        "interrupted_watcher": {
            "pid": INCIDENT_PID,
            "repair_environment_set": False,
            "outer_detach_wrapper_recorded": False,
            "likely_external_tool_session_termination": True,
            "cause_proven": False,
        },
        "local_boundary": {
            "empty_shell_path": shell.relative_to(root).as_posix(),
            "empty_shell_stat": shell_stat,
            "entry_count": 0,
            "watcher_log_path": str(log_path),
            "watcher_log_stat": log_stat,
            "watcher_log_sha256": _sha_bytes(log_raw),
            "historical_run_absent": True,
            "historical_pending_absent": True,
        },
        "cloud_boundary": {
            "prefix_empty": True,
            "required_objects_not_found": True,
            "historical_outcome_lease_absent": True,
            "job_uid": JOB_UID,
            "job_generation": JOB_GENERATION,
            "job_spec_sha256": JOB_SPEC_SHA256,
            "execution_count": len(executions),
            "execution_names_equal_retained_terminal_set": True,
            "reused_job_idle": True,
            "reused_job_unscheduled": True,
        },
        "outcome_boundary": {
            "preflight_attempt_created": False,
            "job_claim_created": False,
            "job_updated": False,
            "execution_created": False,
            "historical_outcome_lease_acquired": False,
            "scientific_artifact_body_read": False,
            "actual_score_query_executed": False,
            "historical_look_consumed": False,
        },
    }

    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.parent.is_symlink():
        raise RuntimeError("A7-v2 recovery archive parent is linked")
    archive.mkdir()
    if archive.stat().st_dev != shell_stat["device"]:
        raise RuntimeError("A7-v2 recovery archive is not on the shell filesystem")

    values = {
        "job-metadata.json": job,
        "job-executions.json": executions,
        "schedulers.json": schedulers,
        "cloud-absence.json": cloud_absence,
        "process-census.json": process_receipt,
        "incident.json": incident,
    }
    for name in RECEIPT_FILES:
        _write_durable(archive / name, _canonical_json(values[name]))
    evidence_raw = _ledger(archive, RECEIPT_FILES)
    _write_durable(archive / "evidence.sha256", evidence_raw)

    # Recheck the complete boundary after the potentially slow evidence writes
    # and immediately before arming the final rename.  Any concurrent change
    # leaves the original shell in place and therefore keeps the watcher
    # blocked.  The second values must reproduce the retained first captures.
    if _canonical_json(_validate_job(job_loader(), anchor=anchor_job)) != \
            _canonical_json(job) or _canonical_json(_validate_executions(
                executions_loader(), prior_anchor=prior_executions,
                last_anchor=last_execution,
            )) != _canonical_json(executions) or _canonical_json(
                _validate_schedulers(schedulers_loader())
            ) != _canonical_json(schedulers) or _canonical_json(
                _validate_cloud_absence(storage_client)
            ) != _canonical_json(cloud_absence):
        raise RuntimeError("A7-v2 recovery boundary changed before archive")
    if process_loader() or _validate_stat(
        shell, expected_shell_stat, kind="empty preflight shell",
    ) != shell_stat or any(True for _entry in os.scandir(shell)) or \
            _validate_stat(
                log_path, expected_log_stat, kind="watcher log",
            ) != log_stat or log_path.read_bytes() != log_raw or \
            historical_out.exists() or historical_out.is_symlink() or \
            historical_pending.exists() or historical_pending.is_symlink():
        raise RuntimeError("A7-v2 local boundary changed before archive")

    recovery = {
        "version": "a7-v2-empty-preflight-shell-recovery-v1",
        "recovery_id": RECOVERY_ID,
        "run_id": RUN_ID,
        "status": "complete-upon-final-atomic-rename",
        "captured_at": captured_at,
        "protocol": {"path": PROTOCOL_PATH, "sha256": PROTOCOL_SHA256},
        "incident": _reference(archive / "incident.json", root),
        "evidence_ledger": _reference(archive / "evidence.sha256", root),
        "archive": {
            "source_path": shell.relative_to(root).as_posix(),
            "destination_path": (
                archive.relative_to(root) / ARCHIVED_SHELL_NAME
            ).as_posix(),
            "preserved_stat_before_move": shell_stat,
            "same_filesystem": True,
            "atomic_rename_is_final_state_change": True,
            "final_revalidation_equal_to_captured_evidence": True,
            "recursive_delete_used": False,
        },
        "licenses": {
            "same_v2_first_preflight_prepare_licensed": True,
            "preflight_retry_licensed": False,
            "historical_scoring_licensed": False,
            "prospective_shadow_licensed": False,
            "production_law_scorefree_transfer_licensed": False,
            "production_change_licensed": False,
        },
    }
    _write_durable(archive / "recovery.json", _canonical_json(recovery))
    recovery_ledger_names = ("evidence.sha256", "recovery.json")
    _write_durable(
        archive / "recovery.sha256", _ledger(archive, recovery_ledger_names),
    )
    _fsync_dir(archive)
    _fsync_dir(archive.parent)

    destination = archive / ARCHIVED_SHELL_NAME
    os.rename(shell, destination)
    _fsync_dir(archive)
    _fsync_dir(shell.parent)
    archived_stat = _stat_receipt(destination)
    for key in ("device", "inode", "mode", "links", "uid", "gid", "size", "mtime_ns"):
        if archived_stat[key] != shell_stat[key]:
            raise RuntimeError("A7-v2 archived empty-shell identity changed")
    if any(True for _entry in os.scandir(destination)) or shell.exists() or \
            shell.is_symlink():
        raise RuntimeError("A7-v2 empty-shell atomic archive did not complete")
    return recovery


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute-empty-shell-recovery",
        action="store_true",
        help="perform the one exact local-only atomic archive operation",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = recover(execute=args.execute_empty_shell_recovery)
    print(
        "A7_V2_EMPTY_PREFLIGHT_SHELL_RECOVERED "
        f"run_id={result['run_id']} recovery_id={result['recovery_id']} "
        "same_v2_first_preflight_prepare_licensed=true"
    )


if __name__ == "__main__":
    main()
