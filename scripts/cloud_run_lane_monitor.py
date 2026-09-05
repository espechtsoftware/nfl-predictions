#!/usr/bin/env python3
"""Durable, read-only Cloud Run lane monitor for a systemd user service.

Each poll atomically replaces one JSON status file and appends transition
records to an fsynced JSONL ledger.  Actionable transitions are latched in an
attention file and can be delivered through a bounded Windows toast hook.
Every gcloud call is an execution list/describe; this process has no mutation
command path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


STATUS_SCHEMA = "cloud-run-lane-monitor-status/v3"
LEGACY_STATUS_SCHEMAS = frozenset(
    ("cloud-run-lane-monitor-status/v1", "cloud-run-lane-monitor-status/v2")
)
EVENT_SCHEMA = "cloud-run-lane-monitor-event/v2"
ATTENTION_SCHEMA = "cloud-run-lane-monitor-attention/v1"
REGISTRY_SCHEMA = "shared-launcher-registry/v1"
COMPLETION_SCHEMA = "shared-launcher-completion/v1"
ALERT_POLICY = "expected-execution-retry-capacity-and-coordinator/v3"
DEFAULT_PROJECT = "nfl-2-506823"
DEFAULT_REGION = "us-central1"
DEFAULT_JOBS = ("lab-run", "lab-run-slow")
DEFAULT_E4_PROJECT = "nfl-predictions-503414"
NONTERMINAL = frozenset(("pending", "running", "unknown"))
FAILED = frozenset(("failed", "cancelled", "unknown_terminal"))


class MonitorError(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class Config:
    state_file: Path
    events_file: Path | None = None
    attention_file: Path | None = None
    project: str = DEFAULT_PROJECT
    region: str = DEFAULT_REGION
    jobs: tuple[str, ...] = DEFAULT_JOBS
    expected_prefixes: tuple[str, ...] = ()
    launcher_registry_dirs: tuple[Path, ...] = ()
    launcher_lane: str | None = None
    queue_grace_seconds: float = 120.0
    stall_seconds: float = 3_600.0
    coordinator_post_provider_grace_seconds: float = 180.0
    e4_execution: str | None = None
    e4_project: str = DEFAULT_E4_PROJECT
    e4_stall_seconds: float = 25_200.0
    command_timeout_seconds: float = 45.0
    windows_toast_command: str | None = None
    notification_timeout_seconds: float = 10.0
    notification_retry_seconds: float = 300.0
    gcloud: str = "gcloud"

    def identity(self) -> dict[str, object]:
        return {
            "project": self.project,
            "region": self.region,
            "jobs": list(self.jobs),
            "expected_prefixes": list(self.expected_prefixes),
            "launcher_registry_dirs": [str(path) for path in self.launcher_registry_dirs],
            "launcher_lane": self.launcher_lane,
            "queue_grace_seconds": self.queue_grace_seconds,
            "stall_seconds": self.stall_seconds,
            "coordinator_post_provider_grace_seconds": (
                self.coordinator_post_provider_grace_seconds
            ),
            "e4_execution": self.e4_execution,
            "e4_project": self.e4_project if self.e4_execution else None,
            "e4_stall_seconds": self.e4_stall_seconds if self.e4_execution else None,
            "alert_policy": ALERT_POLICY,
        }


def _utc(epoch: float) -> str:
    return (
        datetime.fromtimestamp(epoch, timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _epoch(value: object) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.timestamp() if parsed.tzinfo else None


def _count(value: object, label: str) -> int:
    if value is None:
        return 0
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise ProviderError(f"{label} is not a nonnegative integer")


def _strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def _positive_integer(value: object) -> bool:
    return type(value) is int and value > 0


def _process_start_ticks(pid: int) -> int | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    try:
        suffix = raw.rsplit(") ", 1)[1].split()
        value = int(suffix[19])
    except (IndexError, ValueError):
        return None
    return value if value > 0 else None


def _validated_registry_receipt(path: Path) -> Mapping[str, object]:
    if path.is_symlink() or not path.is_file():
        raise MonitorError(f"launcher receipt is unsafe: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MonitorError(f"launcher receipt is unreadable: {path}: {exc}") from exc
    required = {
        "acquired_at_utc",
        "lane",
        "owner",
        "pid",
        "process_start_ticks",
        "schema_version",
        "script_path",
        "target_run_id_prefixes",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise MonitorError(f"launcher receipt has the wrong shape: {path}")
    prefixes = value["target_run_id_prefixes"]
    valid = (
        value["schema_version"] == REGISTRY_SCHEMA
        and isinstance(value["script_path"], str)
        and bool(value["script_path"])
        and Path(value["script_path"]).is_absolute()
        and _positive_integer(value["pid"])
        and _positive_integer(value["process_start_ticks"])
        and value["owner"] in ("lab", "production")
        and isinstance(value["lane"], str)
        and bool(value["lane"])
        and isinstance(prefixes, list)
        and bool(prefixes)
        and all(isinstance(item, str) and bool(item) for item in prefixes)
        and len(prefixes) == len(set(prefixes))
        and isinstance(value["acquired_at_utc"], str)
        and re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
            value["acquired_at_utc"],
        )
        is not None
    )
    if not valid:
        raise MonitorError(f"launcher receipt is malformed: {path}")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise MonitorError(f"cannot hash launcher evidence {path}: {exc}") from exc
    return digest.hexdigest()


def _validated_completion(path: Path) -> Mapping[str, object]:
    if path.is_symlink() or not path.is_file():
        raise MonitorError(f"launcher completion is unsafe: {path}")
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        raise MonitorError(f"launcher completion metadata is unreadable: {path}") from exc
    if mode != 0o600:
        raise MonitorError(f"launcher completion mode differs from 0600: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MonitorError(f"launcher completion is unreadable: {path}: {exc}") from exc
    required = {
        "acquired_at_utc",
        "completed_at_utc",
        "exit_status",
        "lane",
        "owner",
        "pid",
        "process_start_ticks",
        "receipt_sha256",
        "schema_version",
        "script_path",
        "target_run_id_prefixes",
    }
    prefixes = value.get("target_run_id_prefixes") if isinstance(value, Mapping) else None
    valid = (
        isinstance(value, Mapping)
        and set(value) == required
        and value["schema_version"] == COMPLETION_SCHEMA
        and value["owner"] in ("lab", "production")
        and isinstance(value["lane"], str)
        and bool(value["lane"])
        and isinstance(value["script_path"], str)
        and Path(value["script_path"]).is_absolute()
        and _positive_integer(value["pid"])
        and _positive_integer(value["process_start_ticks"])
        and type(value["exit_status"]) is int
        and 0 <= value["exit_status"] <= 255
        and isinstance(value["receipt_sha256"], str)
        and re.fullmatch(r"[0-9a-f]{64}", value["receipt_sha256"]) is not None
        and path.name == f"{value['receipt_sha256']}.json"
        and isinstance(prefixes, list)
        and bool(prefixes)
        and all(isinstance(item, str) and bool(item) for item in prefixes)
        and len(prefixes) == len(set(prefixes))
        and all(
            isinstance(value[key], str)
            and re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
                value[key],
            )
            is not None
            for key in ("acquired_at_utc", "completed_at_utc")
        )
        and str(value["completed_at_utc"]) >= str(value["acquired_at_utc"])
    )
    if not valid:
        raise MonitorError(f"launcher completion is malformed: {path}")
    receipt = {
        "acquired_at_utc": value["acquired_at_utc"],
        "lane": value["lane"],
        "owner": value["owner"],
        "pid": value["pid"],
        "process_start_ticks": value["process_start_ticks"],
        "schema_version": REGISTRY_SCHEMA,
        "script_path": value["script_path"],
        "target_run_id_prefixes": value["target_run_id_prefixes"],
    }
    canonical = (
        json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != value["receipt_sha256"]:
        raise MonitorError(
            f"launcher completion does not reconstruct its bound receipt: {path}"
        )
    return value


def _live_registry_targets(config: Config) -> dict[str, object]:
    """Return one live receipt plus the latest durable terminal record."""
    if not config.launcher_registry_dirs:
        return {
            "state": "disabled",
            "lane": config.launcher_lane,
            "receipt": None,
            "registration_key": None,
            "prefixes": [],
            "completions": [],
            "latest_completion": None,
            "error": None,
        }
    matches: list[tuple[Path, Mapping[str, object]]] = []
    orphans: list[tuple[Path, Mapping[str, object]]] = []
    completions: list[tuple[str, Path, Mapping[str, object]]] = []
    try:
        for directory in config.launcher_registry_dirs:
            if directory.is_symlink() or not directory.is_dir():
                raise MonitorError(f"launcher registry is absent or unsafe: {directory}")
            for path in sorted(directory.glob("*.json")):
                receipt = _validated_registry_receipt(path)
                if config.launcher_lane and receipt["lane"] != config.launcher_lane:
                    continue
                pid = int(receipt["pid"])
                if _process_start_ticks(pid) != int(receipt["process_start_ticks"]):
                    orphans.append((path, receipt))
                    continue
                matches.append((path, receipt))
            completion_dir = directory.parent / "launcher-completions"
            if completion_dir.exists() or completion_dir.is_symlink():
                if completion_dir.is_symlink() or not completion_dir.is_dir():
                    raise MonitorError(
                        f"launcher completion directory is unsafe: {completion_dir}"
                    )
                for path in sorted(completion_dir.glob("*.json")):
                    completion = _validated_completion(path)
                    if config.launcher_lane and completion["lane"] != config.launcher_lane:
                        continue
                    completions.append(
                        (str(completion["completed_at_utc"]), path, completion)
                    )
        if len(matches) > 1:
            names = ", ".join(str(path) for path, _ in matches)
            raise MonitorError(f"multiple live launcher receipts own the lane: {names}")
        if matches and orphans:
            raise MonitorError("live and orphaned launcher receipts coexist")
        if len(orphans) > 1:
            names = ", ".join(str(path) for path, _ in orphans)
            raise MonitorError(f"multiple orphaned launcher receipts own the lane: {names}")
    except MonitorError as exc:
        return {
            "state": "error",
            "lane": config.launcher_lane,
            "receipt": None,
            "registration_key": None,
            "prefixes": [],
            "completions": [],
            "latest_completion": None,
            "error": str(exc),
        }
    completion_records = [
        {
            **completion,
            "path": str(completion_path),
            "record_sha256": _file_sha256(completion_path),
        }
        for _, completion_path, completion in sorted(
            completions,
            key=lambda item: (
                item[0],
                str(item[2]["acquired_at_utc"]),
                int(item[2]["process_start_ticks"]),
                int(item[2]["pid"]),
                str(item[1]),
            ),
        )
    ]
    latest_completion = completion_records[-1] if completion_records else None
    if orphans:
        path, receipt = orphans[0]
        receipt_sha256 = _file_sha256(path)
        has_completion = receipt_sha256 in {
            item["receipt_sha256"] for item in completion_records
        }
        return {
            "state": "terminalized_orphan" if has_completion else "orphaned",
            "lane": receipt["lane"],
            "receipt": str(path),
            "registration_key": receipt_sha256,
            "prefixes": list(receipt["target_run_id_prefixes"]),
            "script_path": receipt["script_path"],
            "pid": receipt["pid"],
            "process_start_ticks": receipt["process_start_ticks"],
            "acquired_at_utc": receipt["acquired_at_utc"],
            "completions": completion_records,
            "latest_completion": latest_completion,
            "error": (
                "launcher receipt owner died after terminal publication; cleanup required"
                if has_completion
                else "launcher receipt owner is dead without terminal completion"
            ),
        }
    if not matches:
        return {
            "state": "no_live_receipt",
            "lane": config.launcher_lane,
            "receipt": None,
            "registration_key": None,
            "prefixes": [],
            "completions": completion_records,
            "latest_completion": latest_completion,
            "error": None,
        }
    path, receipt = matches[0]
    receipt_sha256 = _file_sha256(path)
    if (
        latest_completion is not None
        and latest_completion["receipt_sha256"] == receipt_sha256
    ):
        return {
            "state": "terminalizing",
            "lane": receipt["lane"],
            "receipt": str(path),
            "owner": receipt["owner"],
            "pid": receipt["pid"],
            "process_start_ticks": receipt["process_start_ticks"],
            "acquired_at_utc": receipt["acquired_at_utc"],
            "script_path": receipt["script_path"],
            "registration_key": receipt_sha256,
            "prefixes": list(receipt["target_run_id_prefixes"]),
            "completions": completion_records,
            "latest_completion": latest_completion,
            "error": None,
        }
    return {
        "state": "live",
        "lane": receipt["lane"],
        "receipt": str(path),
        "owner": receipt["owner"],
        "pid": receipt["pid"],
        "process_start_ticks": receipt["process_start_ticks"],
        "acquired_at_utc": receipt["acquired_at_utc"],
        "script_path": receipt["script_path"],
        "registration_key": receipt_sha256,
        "prefixes": list(receipt["target_run_id_prefixes"]),
        "completions": completion_records,
        "latest_completion": latest_completion,
        "error": None,
    }


def _summary(
    row: Mapping[str, object], job: str, prefixes: tuple[str, ...]
) -> dict[str, object]:
    metadata = row.get("metadata", {})
    status = row.get("status", {})
    spec = row.get("spec", {})
    if not all(isinstance(item, Mapping) for item in (metadata, status, spec)):
        raise ProviderError("execution metadata/status/spec is malformed")
    name = metadata.get("name")
    if not isinstance(name, str) or not name:
        raise ProviderError("execution metadata.name is missing")
    conditions = status.get("conditions", [])
    if not isinstance(conditions, list):
        raise ProviderError(f"{name} status.conditions is malformed")
    completed = [
        item
        for item in conditions
        if isinstance(item, Mapping) and item.get("type") == "Completed"
    ]
    if len(completed) > 1:
        raise ProviderError(f"{name} has duplicate Completed conditions")
    condition = completed[0] if completed else {}
    completed_value = condition.get("status")
    reason = str(condition.get("reason", ""))
    message = str(condition.get("message", ""))
    counts = {
        key.removesuffix("Count"): _count(status.get(key), f"{name}.{key}")
        for key in (
            "runningCount",
            "succeededCount",
            "failedCount",
            "cancelledCount",
            "retriedCount",
        )
    }
    completion = status.get("completionTime")
    started = status.get("startTime")
    if counts["cancelled"] or (
        completed_value == "False" and "cancel" in f"{reason} {message}".lower()
    ):
        state = "cancelled"
    elif counts["failed"] or completed_value == "False":
        state = "failed"
    elif completed_value == "True":
        state = "succeeded"
    elif completion:
        state = "unknown_terminal"
    elif started or counts["running"]:
        state = "running"
    elif completed_value == "Unknown":
        state = "pending"
    else:
        state = "unknown"
    provider_times = [
        value
        for value in (
            metadata.get("creationTimestamp"),
            started,
            *(
                item.get("lastTransitionTime")
                for item in conditions
                if isinstance(item, Mapping)
            ),
        )
        if isinstance(value, str) and _epoch(value) is not None
    ]
    run_id: str | None = None
    if prefixes:
        template = spec.get("template", {})
        task_spec = template.get("spec", {}) if isinstance(template, Mapping) else {}
        containers = (
            task_spec.get("containers", []) if isinstance(task_spec, Mapping) else []
        )
        if not isinstance(containers, list):
            raise ProviderError(f"{name} execution containers are malformed")
        run_id_values: list[object] = []
        for container in containers:
            if not isinstance(container, Mapping):
                raise ProviderError(f"{name} execution container is malformed")
            env = container.get("env", [])
            if not isinstance(env, list):
                raise ProviderError(f"{name} execution environment is malformed")
            for entry in env:
                if not isinstance(entry, Mapping):
                    raise ProviderError(f"{name} execution environment entry is malformed")
                if entry.get("name") == "RUN_ID":
                    run_id_values.append(entry.get("value"))
        if len(run_id_values) > 1:
            raise ProviderError(f"{name} has duplicate RUN_ID environment entries")
        if run_id_values:
            value = run_id_values[0]
            if not isinstance(value, str) or not value:
                raise ProviderError(f"{name} RUN_ID is malformed")
            run_id = value

    def matches_prefix(prefix: str) -> bool:
        if run_id is None:
            return False
        return run_id.startswith(f"{prefix}-")
    return {
        "name": name,
        "uid": metadata.get("uid"),
        "job": job,
        "state": state,
        "created_at": metadata.get("creationTimestamp"),
        "started_at": started,
        "completed_at": completion,
        "completed_condition": completed_value,
        "reason": reason or None,
        "counts": counts,
        "task_count": _count(spec.get("taskCount"), f"{name}.taskCount"),
        "last_provider_transition_at": max(provider_times, key=_epoch, default=None),
        "run_id": run_id,
        "matched_expected_prefixes": [
            prefix for prefix in prefixes if matches_prefix(prefix)
        ],
        "stale": False,
    }


def _signature(summary: Mapping[str, object]) -> str:
    fields = {
        key: summary.get(key)
        for key in (
            "state",
            "counts",
            "completed_condition",
            "reason",
            "started_at",
            "completed_at",
            "last_provider_transition_at",
        )
    }
    return json.dumps(fields, sort_keys=True, separators=(",", ":"))


def _query_json(
    args: list[str], timeout: float, runner: Runner | None
) -> object:
    call = runner or subprocess.run
    try:
        result = call(
            args, check=False, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProviderError(f"provider query failed: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "no detail").strip()[:800]
        raise ProviderError(f"provider query exited {result.returncode}: {detail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProviderError("provider query returned invalid JSON") from exc


def _list(config: Config, job: str, runner: Runner | None) -> list[Mapping[str, object]]:
    value = _query_json(
        [
            config.gcloud,
            "run",
            "jobs",
            "executions",
            "list",
            "--job",
            job,
            "--project",
            config.project,
            "--region",
            config.region,
            "--sort-by=~metadata.creationTimestamp",
            "--format=json",
        ],
        config.command_timeout_seconds,
        runner,
    )
    if not isinstance(value, list) or not all(isinstance(row, Mapping) for row in value):
        raise ProviderError(f"{job} execution list is not an array of objects")
    return value


def _describe_e4(config: Config, runner: Runner | None) -> Mapping[str, object]:
    assert config.e4_execution
    value = _query_json(
        [
            config.gcloud,
            "run",
            "jobs",
            "executions",
            "describe",
            config.e4_execution,
            "--project",
            config.e4_project,
            "--region",
            config.region,
            "--format=json",
        ],
        config.command_timeout_seconds,
        runner,
    )
    if not isinstance(value, Mapping):
        raise ProviderError("E4 execution description is not an object")
    metadata = value.get("metadata", {})
    if not isinstance(metadata, Mapping) or metadata.get("name") != config.e4_execution:
        raise ProviderError("E4 response differs from the exact requested execution")
    return value


def _old_mapping(previous: Mapping[str, object] | None, key: str) -> Mapping[str, object]:
    value = previous.get(key, {}) if previous else {}
    return value if isinstance(value, Mapping) else {}


def _track(
    key: str,
    summary: Mapping[str, object],
    prior: Mapping[str, object],
    now: float,
) -> dict[str, object]:
    signature = _signature(summary)
    old = prior.get(key, {})
    if isinstance(old, Mapping) and old.get("signature") == signature:
        last_progress = float(old.get("last_progress_at_epoch", now))
    elif old:
        last_progress = now
    else:
        provider_epoch = _epoch(summary.get("last_provider_transition_at"))
        last_progress = min(now, provider_epoch) if provider_epoch is not None else now
    return {"signature": signature, "last_progress_at_epoch": last_progress}


def _alert(kind: str, severity: str, **details: object) -> dict[str, object]:
    return {"kind": kind, "severity": severity, **details}


def _alert_signature(alert: Mapping[str, object]) -> str:
    fields = {
        key: alert.get(key)
        for key in ("kind", "severity", "escalation", "state", "reason")
    }
    return json.dumps(fields, sort_keys=True, separators=(",", ":"))


def _registered_coordinator_status(
    config: Config,
    registry: Mapping[str, object],
    previous: Mapping[str, object] | None,
    *,
    retained_prefixes: tuple[str, ...],
    provider_cohort_state: str,
    observed: float,
) -> dict[str, object]:
    """Follow a live receipt into its immutable terminal completion record."""
    prior = _old_mapping(previous, "registered_coordinator")
    completion_by_key = {
        str(item["receipt_sha256"]): item
        for item in registry.get("completions", [])
        if isinstance(item, Mapping)
        and isinstance(item.get("receipt_sha256"), str)
    }
    latest_completion = registry.get("latest_completion")
    newer_than_prior_terminal = bool(
        isinstance(latest_completion, Mapping)
        and prior.get("state") in ("succeeded", "failed")
        and latest_completion.get("receipt_sha256") != prior.get("registration_key")
        and prior.get("registration_key") in completion_by_key
    )
    if registry.get("state") == "live":
        registration_key = registry.get("registration_key")
        prefixes = tuple(str(value) for value in registry.get("prefixes", []))
        coordinator = {
            "state": "running",
            "exit_status": None,
            "acquired_at_utc": registry.get("acquired_at_utc"),
            "script_path": registry.get("script_path"),
            "pid": registry.get("pid"),
            "process_start_ticks": registry.get("process_start_ticks"),
            "completion_path": None,
            "completion_record_sha256": None,
            "error": None,
        }
        source = "live_launcher_receipt"
    elif registry.get("state") in ("terminalizing", "terminalized_orphan"):
        completion = completion_by_key[str(registry["registration_key"])]
        registration_key = completion.get("receipt_sha256")
        prefixes = tuple(completion.get("target_run_id_prefixes", []))
        exit_status = int(completion["exit_status"])
        coordinator = {
            "state": "succeeded" if exit_status == 0 else "failed",
            "exit_status": exit_status,
            "acquired_at_utc": completion.get("acquired_at_utc"),
            "script_path": completion.get("script_path"),
            "pid": completion.get("pid"),
            "process_start_ticks": completion.get("process_start_ticks"),
            "completion_path": completion.get("path"),
            "completion_record_sha256": completion.get("record_sha256"),
            "completed_at_utc": completion.get("completed_at_utc"),
            "error": None,
        }
        source = (
            "terminalizing_launcher_receipt"
            if registry.get("state") == "terminalizing"
            else "terminalized_orphan_receipt"
        )
    elif registry.get("state") == "orphaned":
        registration_key = registry.get("registration_key")
        prefixes = tuple(str(value) for value in registry.get("prefixes", []))
        coordinator = {
            "state": "orphaned",
            "exit_status": None,
            "acquired_at_utc": registry.get("acquired_at_utc"),
            "script_path": registry.get("script_path"),
            "pid": registry.get("pid"),
            "process_start_ticks": registry.get("process_start_ticks"),
            "completion_path": None,
            "completion_record_sha256": None,
            "error": registry.get("error"),
        }
        source = "orphaned_launcher_receipt"
    elif (
        isinstance(prior.get("registration_key"), str)
        and prior["registration_key"] in completion_by_key
        and (
            prior.get("state") in ("running", "terminal_record_missing")
            or (
                prior.get("state") in ("succeeded", "failed")
                and not newer_than_prior_terminal
            )
        )
    ):
        completion = completion_by_key[str(prior["registration_key"])]
        registration_key = completion.get("receipt_sha256")
        prefixes = tuple(completion.get("target_run_id_prefixes", []))
        exit_status = int(completion["exit_status"])
        coordinator = {
            "state": "succeeded" if exit_status == 0 else "failed",
            "exit_status": exit_status,
            "acquired_at_utc": completion.get("acquired_at_utc"),
            "script_path": completion.get("script_path"),
            "pid": completion.get("pid"),
            "process_start_ticks": completion.get("process_start_ticks"),
            "completion_path": completion.get("path"),
            "completion_record_sha256": completion.get("record_sha256"),
            "completed_at_utc": completion.get("completed_at_utc"),
            "error": None,
        }
        if (
            isinstance(prior.get("completion_record_sha256"), str)
            and prior["completion_record_sha256"]
            != completion.get("record_sha256")
        ):
            coordinator["state"] = "failed"
            coordinator["error"] = "immutable completion record changed after observation"
        source = "terminal_launcher_record"
    elif isinstance(latest_completion, Mapping) and (
        not prior or newer_than_prior_terminal
    ):
        # Recency is only a safe selector on cold start. After observing a live
        # receipt, its exact hash is the only record allowed to settle it.
        completion = latest_completion
        registration_key = completion.get("receipt_sha256")
        prefixes = tuple(completion.get("target_run_id_prefixes", []))
        exit_status = int(completion["exit_status"])
        coordinator = {
            "state": "succeeded" if exit_status == 0 else "failed",
            "exit_status": exit_status,
            "acquired_at_utc": completion.get("acquired_at_utc"),
            "script_path": completion.get("script_path"),
            "pid": completion.get("pid"),
            "process_start_ticks": completion.get("process_start_ticks"),
            "completion_path": completion.get("path"),
            "completion_record_sha256": completion.get("record_sha256"),
            "completed_at_utc": completion.get("completed_at_utc"),
            "error": None,
        }
        source = "terminal_launcher_record_cold_start"
    elif (
        isinstance(prior.get("registration_key"), str)
        and prior.get("registration_key")
        and tuple(prior.get("prefixes", [])) == retained_prefixes
        and retained_prefixes
    ):
        registration_key = prior["registration_key"]
        prefixes = retained_prefixes
        coordinator = {
            "state": "terminal_record_missing",
            "exit_status": None,
            "acquired_at_utc": prior.get("acquired_at_utc"),
            "script_path": prior.get("script_path"),
            "pid": prior.get("pid"),
            "process_start_ticks": prior.get("process_start_ticks"),
            "completion_path": None,
            "completion_record_sha256": None,
            "error": "live receipt disappeared without a terminal completion",
        }
        source = "retained_after_launcher_exit"
    else:
        registration_key = None
        prefixes = ()
        coordinator = {
            "state": "untracked",
            "exit_status": None,
            "acquired_at_utc": None,
            "script_path": None,
            "pid": None,
            "process_start_ticks": None,
            "completion_path": None,
            "completion_record_sha256": None,
            "error": None,
        }
        source = "none"

    same_registration = prior.get("registration_key") == registration_key
    if provider_cohort_state == "succeeded":
        prior_since = (
            prior.get("provider_succeeded_since_epoch")
            if same_registration
            else None
        )
        provider_since = (
            float(prior_since)
            if isinstance(prior_since, (int, float))
            else observed
        )
        post_provider_seconds: int | None = max(0, int(observed - provider_since))
    else:
        provider_since = None
        post_provider_seconds = None

    state = str(coordinator["state"])
    if state in ("failed", "orphaned"):
        acceptance_state = "failed"
    elif provider_cohort_state != "succeeded":
        acceptance_state = "waiting_for_provider"
    elif state == "succeeded":
        acceptance_state = "succeeded"
    elif state == "running":
        acceptance_state = "post_provider_pending"
    elif state == "untracked":
        acceptance_state = "provider_only"
    else:
        acceptance_state = "unverifiable"
    return {
        **coordinator,
        "acceptance_state": acceptance_state,
        "registration_key": registration_key,
        "prefixes": list(prefixes),
        "source": source,
        "provider_succeeded_since_epoch": provider_since,
        "post_provider_seconds": post_provider_seconds,
    }


def collect_status(
    config: Config,
    previous: Mapping[str, object] | None,
    *,
    now: float | None = None,
    runner: Runner | None = None,
) -> dict[str, object]:
    """Poll only provider metadata and derive the next durable snapshot."""
    observed = time.time() if now is None else now
    if not math.isfinite(observed):
        raise MonitorError("clock returned a nonfinite value")
    if previous is not None and previous.get("monitor") != config.identity():
        previous = None
    registry = _live_registry_targets(config)
    previous_queue = _old_mapping(previous, "authorized_queue")
    previous_coordinator = _old_mapping(previous, "registered_coordinator")
    prior_completions = _old_mapping(previous, "launcher_completions")
    registry_error = registry.get("state") == "error"
    if registry_error:
        # A fail-closed registry read says nothing about whether previously
        # observed immutable records disappeared. Retain the last valid
        # ledger until the directory can be validated again; otherwise one
        # transient unsafe-mode or partial-publication observation falsely
        # marks every historical completion as missing and then changed.
        completion_by_key = {
            str(key): dict(value)
            for key, value in prior_completions.items()
            if isinstance(key, str) and isinstance(value, Mapping)
        }
        completion_records = list(completion_by_key.values())
    else:
        completion_records = [
            item
            for item in registry.get("completions", [])
            if isinstance(item, Mapping)
        ]
        completion_by_key = {
            str(item["receipt_sha256"]): item
            for item in completion_records
            if isinstance(item.get("receipt_sha256"), str)
        }
    prior_seen = {
        str(value) for value in (previous or {}).get("seen_completion_keys", [])
    }
    current_keys = set(completion_by_key)
    changed_completion_keys = sorted(
        key
        for key in current_keys & set(prior_completions)
        if isinstance(prior_completions.get(key), Mapping)
        and prior_completions[key].get("record_sha256")
        != completion_by_key[key].get("record_sha256")
    )
    new_completion_keys = sorted(current_keys - prior_seen)
    new_failure_keys = {
        key
        for key in new_completion_keys
        if int(completion_by_key[key]["exit_status"]) != 0
    }
    missing_completion_keys = sorted(prior_seen - current_keys)
    completion_integrity_failure_keys = {
        str(value)
        for value in (previous or {}).get("completion_integrity_failure_keys", [])
    }
    completion_integrity_failure_keys.update(changed_completion_keys)
    completion_integrity_failure_keys.update(missing_completion_keys)
    prior_blockers = {
        str(value)
        for value in (previous or {}).get("blocking_completion_failure_keys", [])
    }
    latest_for_tracking = registry.get("latest_completion")
    advance_to_latest_terminal = bool(
        isinstance(latest_for_tracking, Mapping)
        and previous_coordinator.get("state") in ("succeeded", "failed")
        and latest_for_tracking.get("receipt_sha256")
        != previous_coordinator.get("registration_key")
        and previous_coordinator.get("registration_key") in completion_by_key
    )
    if registry.get("state") in (
        "live", "orphaned", "terminalizing", "terminalized_orphan"
    ):
        tracked_registration_key = registry.get("registration_key")
    elif advance_to_latest_terminal:
        tracked_registration_key = latest_for_tracking.get("receipt_sha256")
    elif isinstance(previous_coordinator.get("registration_key"), str):
        tracked_registration_key = previous_coordinator["registration_key"]
    elif isinstance(latest_for_tracking, Mapping):
        tracked_registration_key = latest_for_tracking.get("receipt_sha256")
    else:
        tracked_registration_key = None
    # A new live receipt explicitly rearms the lane. Historical failures stay
    # in the attention ledger, but no longer determine the new cohort.
    rearmed_live_receipt = registry.get("state") == "live" and (
        registry.get("registration_key")
        != previous_coordinator.get("registration_key")
    )
    if rearmed_live_receipt:
        prior_blockers.clear()
    # A replacement live receipt starts a new effective cohort, but it must
    # not erase newly discovered terminal failures from the prior cohort.
    # Those failures still emit and latch below; they simply do not poison B.
    blocking_failure_keys = {
        key for key in prior_blockers if key == tracked_registration_key
    } | (
        set()
        if rearmed_live_receipt
        else {key for key in new_failure_keys if key == tracked_registration_key}
    )
    latest_completion = registry.get("latest_completion")
    completion_follows_previous = bool(
        isinstance(latest_completion, Mapping)
        and (
            not isinstance(previous_coordinator.get("acquired_at_utc"), str)
            or str(latest_completion.get("acquired_at_utc", ""))
            >= str(previous_coordinator["acquired_at_utc"])
        )
    )
    if registry["state"] in (
        "live", "orphaned", "terminalizing", "terminalized_orphan"
    ):
        registry_prefixes = tuple(str(value) for value in registry["prefixes"])
        queue_source = (
            "live_launcher_receipt"
            if registry["state"] in ("live", "terminalizing", "terminalized_orphan")
            else "orphaned_launcher_receipt"
        )
    elif (
        previous_coordinator.get("state")
        in ("running", "terminal_record_missing")
        and isinstance(previous_queue.get("prefixes"), list)
        and previous_queue.get("prefixes")
    ):
        registry_prefixes = tuple(str(value) for value in previous_queue["prefixes"])
        queue_source = "retained_for_exact_coordinator"
    elif isinstance(latest_completion, Mapping) and completion_follows_previous:
        registry_prefixes = tuple(
            str(value)
            for value in latest_completion["target_run_id_prefixes"]
        )
        queue_source = "terminal_launcher_record"
    elif isinstance(previous_queue.get("prefixes"), list) and previous_queue.get(
        "prefixes"
    ):
        registry_prefixes = tuple(
            str(value) for value in previous_queue["prefixes"]
        )
        queue_source = "retained_after_launcher_exit"
    else:
        registry_prefixes = ()
        queue_source = "none"
    expected_prefixes = tuple(
        dict.fromkeys((*config.expected_prefixes, *registry_prefixes))
    )
    old_exec = _old_mapping(previous, "executions")
    old_progress = _old_mapping(previous, "progress")
    executions: dict[str, dict[str, object]] = {}
    fresh: dict[str, dict[str, object]] = {}
    queries: dict[str, dict[str, object]] = {}
    errors: list[tuple[str, str]] = []

    for job in config.jobs:
        try:
            rows = _list(config, job, runner)
            for row in rows:
                item = _summary(row, job, expected_prefixes)
                key = f"lab:{job}:{item['name']}"
                executions[key] = item
                fresh[key] = item
            queries[job] = {"ok": True, "error": None}
        except ProviderError as exc:
            error = str(exc)
            queries[job] = {"ok": False, "error": error}
            errors.append((job, error))
            stem = f"lab:{job}:"
            for key, item in old_exec.items():
                if key.startswith(stem) and isinstance(item, Mapping):
                    executions[key] = {**item, "stale": True}

    lab_ok = not errors
    active = sorted(
        item["name"]
        for key, item in fresh.items()
        if key.startswith("lab:") and item["state"] in NONTERMINAL
    )
    occupied_jobs = sorted(
        {
            str(item["job"])
            for key, item in fresh.items()
            if key.startswith("lab:") and item["state"] in NONTERMINAL
        }
    )
    available_jobs = (
        [] if not lab_ok else sorted(set(config.jobs) - set(occupied_jobs))
    )
    lane_state = "unknown" if not lab_ok else ("active" if active else "idle")
    prefix_status: dict[str, dict[str, object]] = {}
    for prefix in expected_prefixes:
        matched_items = sorted(
            (
                item
                for key, item in fresh.items()
                if key.startswith("lab:")
                and prefix in item["matched_expected_prefixes"]
            ),
            key=lambda item: str(item["name"]),
        )
        matches = [str(item["name"]) for item in matched_items]
        states = {str(item["name"]): str(item["state"]) for item in matched_items}
        state = (
            "duplicate"
            if len(matches) > 1
            else "claimed"
            if matches
            else "unclaimed"
            if lab_ok
            else "unknown"
        )
        prefix_status[prefix] = {
            "state": state,
            "execution_names": matches,
            "execution_states": states,
        }

    if not lab_ok:
        cohort_state = "unknown"
    elif any(item["state"] == "duplicate" for item in prefix_status.values()):
        cohort_state = "failed"
    elif not expected_prefixes or any(
        item["state"] == "unclaimed" for item in prefix_status.values()
    ):
        cohort_state = "waiting"
    else:
        matched_states = [
            state
            for item in prefix_status.values()
            for state in item["execution_states"].values()
        ]
        if any(state in FAILED for state in matched_states):
            cohort_state = "failed"
        elif any(state in NONTERMINAL for state in matched_states):
            cohort_state = "running"
        elif matched_states and all(state == "succeeded" for state in matched_states):
            cohort_state = "succeeded"
        else:
            cohort_state = "unknown"

    if registry_error and previous_coordinator:
        prior_state = str(previous_coordinator.get("state", "untracked"))
        registered_coordinator = {
            **previous_coordinator,
            "acceptance_state": (
                "failed" if prior_state in ("failed", "orphaned") else "unverifiable"
            ),
            "source": "retained_during_registry_error",
            "post_provider_seconds": None,
            "error": registry.get("error"),
        }
    else:
        registered_coordinator = _registered_coordinator_status(
            config,
            registry,
            previous,
            retained_prefixes=registry_prefixes,
            provider_cohort_state=cohort_state,
            observed=observed,
        )
    if (
        registered_coordinator.get("registration_key")
        in completion_integrity_failure_keys
    ):
        registered_coordinator = {
            **registered_coordinator,
            "state": "failed",
            "acceptance_state": "failed",
            "error": "registered completion evidence failed immutable-ledger integrity",
        }

    acceptance_state = str(registered_coordinator["acceptance_state"])
    if cohort_state == "failed" or blocking_failure_keys or acceptance_state == "failed":
        effective_cohort_state = "failed"
    elif cohort_state == "succeeded" and acceptance_state == "succeeded":
        effective_cohort_state = "succeeded"
    elif cohort_state == "succeeded" and config.launcher_registry_dirs:
        effective_cohort_state = "pending_acceptance"
    else:
        effective_cohort_state = cohort_state

    progress: dict[str, object] = {}
    for key, item in fresh.items():
        if item["state"] in NONTERMINAL:
            progress[key] = _track(key, item, old_progress, observed)
    for job, query in queries.items():
        if not query["ok"]:
            stem = f"lab:{job}:"
            progress.update(
                (key, value)
                for key, value in old_progress.items()
                if key.startswith(stem)
            )

    alerts: dict[str, dict[str, object]] = {}
    if registry["state"] == "error":
        alerts["launcher-registry"] = _alert(
            "launcher_registry_invalid",
            "error",
            lane=config.launcher_lane,
            error=registry["error"],
        )
    elif registry["state"] == "orphaned":
        key = registry.get("registration_key")
        alerts[f"registered-coordinator-orphaned:{key}"] = _alert(
            "registered_coordinator_orphaned",
            "error",
            coordinator=registry.get("script_path"),
            registration_key=key,
            state="orphaned",
            reason="launcher receipt owner died without terminal completion",
            prefixes=registry.get("prefixes", []),
        )
    elif registry["state"] == "terminalized_orphan":
        key = registry.get("registration_key")
        alerts[f"registered-coordinator-cleanup-required:{key}"] = _alert(
            "registered_coordinator_cleanup_required",
            "error",
            coordinator=registry.get("script_path"),
            registration_key=key,
            state="terminalized_orphan",
            reason="terminal completion exists but orphan receipt blocks reacquisition",
            prefixes=registry.get("prefixes", []),
        )
    for key in sorted(completion_integrity_failure_keys):
        if key not in missing_completion_keys:
            continue
        alerts[f"launcher-completion-missing:{key}"] = _alert(
            "launcher_completion_record_missing",
            "error",
            registration_key=key,
            reason="previously observed immutable completion disappeared",
        )
    for key in sorted(completion_integrity_failure_keys):
        if key not in current_keys:
            continue
        alerts[f"launcher-completion-changed:{key}"] = _alert(
            "launcher_completion_record_changed",
            "error",
            registration_key=key,
            reason="previously observed immutable completion changed",
            previous_record_sha256=(
                prior_completions[key].get("record_sha256")
                if isinstance(prior_completions.get(key), Mapping)
                else None
            ),
            current_record_sha256=completion_by_key[key].get("record_sha256"),
        )
    for key in sorted(blocking_failure_keys | new_failure_keys):
        completion = completion_by_key.get(key)
        if completion is None:
            continue
        alerts[f"registered-coordinator-failure:{key}"] = _alert(
            "registered_coordinator_failed",
            "error",
            coordinator=completion.get("script_path"),
            registration_key=key,
            state="failed",
            reason="nonzero coordinator exit",
            exit_status=completion.get("exit_status"),
            completion_path=completion.get("path"),
            prefixes=completion.get("target_run_id_prefixes", []),
            provider_cohort_state=cohort_state,
        )
    coordinator_state = registered_coordinator["state"]
    coordinator_identity = registered_coordinator["registration_key"]
    if coordinator_state == "failed" and not blocking_failure_keys:
        coordinator_error = registered_coordinator.get("error")
        coordinator_exit_status = registered_coordinator.get("exit_status")
        alerts[f"registered-coordinator-failure:{coordinator_identity}"] = _alert(
            "registered_coordinator_failed",
            "error",
            coordinator=registered_coordinator.get("script_path"),
            registration_key=coordinator_identity,
            state=coordinator_state,
            reason=(
                coordinator_error
                if isinstance(coordinator_error, str) and coordinator_error
                else "nonzero coordinator exit"
                if coordinator_exit_status not in (None, 0)
                else "coordinator acceptance failed"
            ),
            exit_status=coordinator_exit_status,
            completion_path=registered_coordinator.get("completion_path"),
            prefixes=registered_coordinator["prefixes"],
            provider_cohort_state=cohort_state,
        )
    elif (
        registered_coordinator["acceptance_state"]
        in ("post_provider_pending", "unverifiable")
        and isinstance(registered_coordinator.get("post_provider_seconds"), int)
        and registered_coordinator["post_provider_seconds"]
        >= config.coordinator_post_provider_grace_seconds
    ):
        alerts[f"registered-coordinator-post-provider:{coordinator_identity}"] = _alert(
            "registered_coordinator_post_provider_pending",
            "error",
            coordinator=registered_coordinator.get("script_path"),
            registration_key=coordinator_identity,
            state=coordinator_state,
            reason="provider_succeeded_but_coordinator_did_not_confirm_acceptance",
            prefixes=registered_coordinator["prefixes"],
            provider_cohort_state=cohort_state,
            post_provider_seconds=registered_coordinator["post_provider_seconds"],
            grace_seconds=config.coordinator_post_provider_grace_seconds,
        )
    for job, error in errors:
        alerts[f"provider-query:{job}"] = _alert(
            "provider_query_failed", "error", job=job, error=error
        )
    for prefix, item in prefix_status.items():
        if item["state"] != "duplicate":
            continue
        alerts[f"duplicate-prefix-claim:{prefix}"] = _alert(
            "duplicate_prefix_claim",
            "error",
            prefix=prefix,
            state="duplicate",
            reason="authorized prefix matched more than one provider execution",
            execution_names=item["execution_names"],
        )
    if lab_ok:
        for job in config.jobs:
            rows = [
                item for key, item in fresh.items() if key.startswith(f"lab:{job}:")
            ]
            latest = max(
                rows,
                key=lambda item: (str(item.get("created_at") or ""), item["name"]),
                default=None,
            )
            monitored = {
                str(item["name"]): item
                for item in rows
                if item["matched_expected_prefixes"]
            }
            if latest is not None:
                monitored[str(latest["name"])] = latest
            for item in monitored.values():
                if item["state"] in FAILED:
                    alerts[f"execution-failure:{job}:{item['name']}"] = _alert(
                        "execution_failed",
                        "error",
                        job=job,
                        execution=item["name"],
                        state=item["state"],
                        reason=item["reason"],
                        counts=item["counts"],
                    )
                retried = int(item["counts"]["retried"])
                if retried:
                    task_count = int(item["task_count"])
                    exhausted = bool(task_count and retried >= task_count)
                    alerts[f"execution-retried:{job}:{item['name']}"] = _alert(
                        "execution_retried",
                        "error" if exhausted else "warning",
                        escalation=(
                            "all_tasks_retried" if exhausted else "retry_observed"
                        ),
                        job=job,
                        execution=item["name"],
                        retried_count=retried,
                        task_count=task_count,
                        state=item["state"],
                    )
        for key, item in fresh.items():
            if not key.startswith("lab:") or item["state"] not in NONTERMINAL:
                continue
            age = observed - float(progress[key]["last_progress_at_epoch"])
            if age >= config.stall_seconds:
                alerts[f"execution-stalled:{item['job']}:{item['name']}"] = _alert(
                    "execution_metadata_stalled",
                    "warning",
                    job=item["job"],
                    execution=item["name"],
                    unchanged_seconds=int(age),
                    threshold_seconds=config.stall_seconds,
                )
        old_capacity = _old_mapping(previous, "capacity_unclaimed_since_epoch")
        capacity_unclaimed_since: dict[str, float] = {}
        if available_jobs:
            for prefix, item in prefix_status.items():
                if item["state"] != "unclaimed":
                    continue
                since = float(old_capacity.get(prefix, observed))
                capacity_unclaimed_since[prefix] = since
                age = observed - since
                if age >= config.queue_grace_seconds:
                    alerts[f"lane-capacity-unclaimed:{prefix}"] = _alert(
                        "lane_capacity_with_unclaimed_prefix",
                        "error",
                        prefix=prefix,
                        available_jobs=available_jobs,
                        unchanged_seconds=int(age),
                        grace_seconds=config.queue_grace_seconds,
                    )
    else:
        capacity_unclaimed_since = dict(
            _old_mapping(previous, "capacity_unclaimed_since_epoch")
        )

    e4_key = f"e4:{config.e4_execution}" if config.e4_execution else None
    if e4_key is not None:
        query_key = e4_key
        try:
            item = _summary(_describe_e4(config, runner), "exact-production-e4", ())
            executions[e4_key] = item
            fresh[e4_key] = item
            queries[query_key] = {"ok": True, "error": None}
            if item["state"] in NONTERMINAL:
                progress[e4_key] = _track(e4_key, item, old_progress, observed)
                age = observed - float(progress[e4_key]["last_progress_at_epoch"])
                if age >= config.e4_stall_seconds:
                    alerts[f"e4-stalled:{item['name']}"] = _alert(
                        "exact_e4_metadata_stalled",
                        "warning",
                        execution=item["name"],
                        unchanged_seconds=int(age),
                        threshold_seconds=config.e4_stall_seconds,
                    )
            elif item["state"] in FAILED:
                alerts[f"e4-failure:{item['name']}"] = _alert(
                    "exact_e4_failed",
                    "error",
                    execution=item["name"],
                    state=item["state"],
                    reason=item["reason"],
                    counts=item["counts"],
                )
            retried = int(item["counts"]["retried"])
            if retried:
                task_count = int(item["task_count"])
                exhausted = bool(task_count and retried >= task_count)
                alerts[f"e4-retried:{item['name']}"] = _alert(
                    "exact_e4_retried",
                    "error" if exhausted else "warning",
                    escalation=("all_tasks_retried" if exhausted else "retry_observed"),
                    execution=item["name"],
                    retried_count=retried,
                    task_count=task_count,
                    state=item["state"],
                )
        except ProviderError as exc:
            error = str(exc)
            queries[query_key] = {"ok": False, "error": error}
            old_item = old_exec.get(query_key)
            if isinstance(old_item, Mapping):
                executions[query_key] = {**old_item, "stale": True}
            if query_key in old_progress:
                progress[query_key] = old_progress[query_key]
            alerts[f"e4-query:{config.e4_execution}"] = _alert(
                "exact_e4_query_failed",
                "error",
                execution=config.e4_execution,
                error=error,
            )

    sequence = int(previous.get("sequence", 0)) + 1 if previous else 1
    return {
        "schema_version": STATUS_SCHEMA,
        "sequence": sequence,
        "observed_at": _utc(observed),
        "observed_at_epoch": observed,
        "monitor": config.identity(),
        "authorized_queue": {
            **registry,
            "source": queue_source,
            "prefixes": list(registry_prefixes),
            "effective_prefixes": list(expected_prefixes),
        },
        "queries": queries,
        "lane": {
            "state": lane_state,
            "active_executions": active,
            "occupied_jobs": occupied_jobs,
            "available_jobs": available_jobs,
        },
        "expected_prefixes": prefix_status,
        "cohort": {
            "state": effective_cohort_state,
            "provider_state": cohort_state,
            "acceptance_state": acceptance_state,
        },
        "registered_coordinator": registered_coordinator,
        "seen_completion_keys": sorted(current_keys),
        "new_completion_keys": new_completion_keys,
        "changed_completion_keys": changed_completion_keys,
        "completion_integrity_failure_keys": sorted(
            completion_integrity_failure_keys
        ),
        "blocking_completion_failure_keys": sorted(blocking_failure_keys),
        "launcher_completions": completion_by_key,
        "executions": executions,
        "e4_execution_key": e4_key,
        "progress": progress,
        "capacity_unclaimed_since_epoch": capacity_unclaimed_since,
        "alerts": alerts,
    }


def transition_events(
    previous: Mapping[str, object] | None, current: Mapping[str, object]
) -> list[dict[str, object]]:
    """Build transition-only event records for stdout/journald."""
    base = {"schema_version": EVENT_SCHEMA, "at": current["observed_at"]}
    alerts = _old_mapping(current, "alerts")
    completions = _old_mapping(current, "launcher_completions")
    completion_events: list[dict[str, object]] = []
    for key in current.get("new_completion_keys", []):
        item = completions.get(key)
        if not isinstance(key, str) or not isinstance(item, Mapping):
            continue
        exit_status = item.get("exit_status")
        completion_events.append(
            {
                **base,
                "event": (
                    "registered_coordinator_accepted"
                    if exit_status == 0
                    else "registered_coordinator_failed"
                ),
                "registration_key": key,
                "coordinator": item.get("script_path"),
                "prefixes": item.get("target_run_id_prefixes", []),
                "exit_status": exit_status,
                "effective_state": _old_mapping(current, "cohort").get("state"),
                "recovered": previous is None,
            }
        )
    if (
        previous is None
        or previous.get("monitor") != current.get("monitor")
        or previous.get("schema_version") != STATUS_SCHEMA
    ):
        return [
            {**base, "event": "monitor_started", "lane_state": current["lane"]["state"]},
            *completion_events,
            *(
                {**base, "event": "alert_raised", "key": key, "alert": alert}
                for key, alert in sorted(alerts.items())
            ),
        ]
    events: list[dict[str, object]] = list(completion_events)
    before_exec = _old_mapping(previous, "executions")
    after_exec = _old_mapping(current, "executions")
    for key, item in sorted(after_exec.items()):
        if not isinstance(item, Mapping) or item.get("stale"):
            continue
        prior = before_exec.get(key)
        if not isinstance(prior, Mapping):
            events.append(
                {
                    **base,
                    "event": "execution_observed",
                    "execution": item.get("name"),
                    "job": item.get("job"),
                    "state": item.get("state"),
                    "counts": item.get("counts"),
                }
            )
        elif _signature(prior) != _signature(item):
            events.append(
                {
                    **base,
                    "event": "execution_transition",
                    "execution": item.get("name"),
                    "job": item.get("job"),
                    "before": {"state": prior.get("state"), "counts": prior.get("counts")},
                    "after": {"state": item.get("state"), "counts": item.get("counts")},
                }
            )
    old_lane = _old_mapping(previous, "lane").get("state")
    new_lane = _old_mapping(current, "lane").get("state")
    if old_lane != new_lane:
        events.append(
            {**base, "event": "lane_transition", "before": old_lane, "after": new_lane}
        )
    old_cohort = _old_mapping(previous, "cohort").get("state")
    new_cohort = _old_mapping(current, "cohort").get("state")
    if old_cohort != new_cohort:
        events.append(
            {
                **base,
                "event": "cohort_transition",
                "before": old_cohort,
                "after": new_cohort,
            }
        )
    old_provider_cohort = _old_mapping(previous, "cohort").get("provider_state")
    new_provider_cohort = _old_mapping(current, "cohort").get("provider_state")
    if (
        old_provider_cohort != new_provider_cohort
        and new_provider_cohort == "succeeded"
        and new_cohort != "succeeded"
    ):
        coordinator = _old_mapping(current, "registered_coordinator")
        events.append(
            {
                **base,
                "event": "provider_cohort_completed_without_acceptance",
                "effective_state": new_cohort,
                "coordinator_state": coordinator.get("state"),
                "registration_key": coordinator.get("registration_key"),
            }
        )
    old_coordinator = _old_mapping(previous, "registered_coordinator")
    new_coordinator = _old_mapping(current, "registered_coordinator")
    coordinator_fields = (
        "registration_key",
        "exit_status",
        "state",
        "acceptance_state",
    )
    before_coordinator = {
        key: old_coordinator.get(key) for key in coordinator_fields
    }
    after_coordinator = {
        key: new_coordinator.get(key) for key in coordinator_fields
    }
    if before_coordinator != after_coordinator:
        events.append(
            {
                **base,
                "event": "registered_coordinator_transition",
                "coordinator": new_coordinator.get("script_path")
                or old_coordinator.get("script_path"),
                "before": before_coordinator,
                "after": after_coordinator,
            }
        )
    old_prefixes = _old_mapping(previous, "expected_prefixes")
    new_prefixes = _old_mapping(current, "expected_prefixes")
    for prefix, item in sorted(new_prefixes.items()):
        old_item = old_prefixes.get(prefix, {})
        old_state = old_item.get("state") if isinstance(old_item, Mapping) else None
        new_state = item.get("state") if isinstance(item, Mapping) else None
        if old_state != new_state:
            events.append(
                {
                    **base,
                    "event": "prefix_transition",
                    "prefix": prefix,
                    "before": old_state,
                    "after": new_state,
                }
            )
    old_alerts = _old_mapping(previous, "alerts")
    for key in sorted(alerts.keys() - old_alerts.keys()):
        events.append(
            {**base, "event": "alert_raised", "key": key, "alert": alerts[key]}
        )
    for key in sorted(alerts.keys() & old_alerts.keys()):
        current_alert = alerts[key]
        old_alert = old_alerts[key]
        if not isinstance(current_alert, Mapping) or not isinstance(old_alert, Mapping):
            continue
        if _alert_signature(current_alert) != _alert_signature(old_alert):
            events.append(
                {
                    **base,
                    "event": "alert_updated",
                    "key": key,
                    "before": old_alert,
                    "alert": current_alert,
                }
            )
    for key in sorted(old_alerts.keys() - alerts.keys()):
        events.append(
            {**base, "event": "alert_cleared", "key": key, "alert": old_alerts[key]}
        )
    return events


def load_status(path: Path) -> dict[str, object] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise MonitorError(f"cannot read {path}: {exc}") from exc
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MonitorError(f"status file {path} is invalid JSON") from exc
    schemas = {STATUS_SCHEMA, *LEGACY_STATUS_SCHEMAS}
    if not isinstance(value, dict) or value.get("schema_version") not in schemas:
        raise MonitorError(f"status file {path} has an unsupported schema")
    return value


def write_json_atomic(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def write_status_atomic(path: Path, status: Mapping[str, object]) -> None:
    write_json_atomic(path, status)


def append_events(path: Path, events: Iterable[Mapping[str, object]]) -> None:
    records = list(events)
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    try:
        descriptor = os.open(path, flags, 0o600)
        os.chmod(path, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
            for event in records:
                handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")))
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise MonitorError(f"cannot append event ledger {path}: {exc}") from exc


def load_attention(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise MonitorError(f"cannot read attention file {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != ATTENTION_SCHEMA:
        raise MonitorError(f"attention file {path} has an unsupported schema")
    return value


def update_attention(
    previous: Mapping[str, object] | None,
    current: Mapping[str, object],
    events: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Latch alert transitions until the operator explicitly acknowledges them."""
    raw_entries = _old_mapping(previous, "entries")
    entries: dict[str, dict[str, object]] = {
        key: dict(value)
        for key, value in raw_entries.items()
        if isinstance(key, str) and isinstance(value, Mapping)
    }
    for event in events:
        kind = event.get("event")
        key = event.get("key")
        if kind not in ("alert_raised", "alert_updated", "alert_cleared") or not isinstance(
            key, str
        ):
            continue
        prior = entries.get(key, {})
        if kind == "alert_raised":
            entries[key] = {
                "state": "active",
                "first_raised_at": prior.get("first_raised_at", event["at"]),
                "last_changed_at": event["at"],
                "cleared_at": None,
                "acknowledged_at": None,
                "occurrences": int(prior.get("occurrences", 0)) + 1,
                "alert": event.get("alert"),
            }
        elif kind == "alert_updated":
            entries[key] = {
                **prior,
                "state": "active",
                "last_changed_at": event["at"],
                "cleared_at": None,
                "acknowledged_at": None,
                "alert": event.get("alert"),
            }
        else:
            entries[key] = {
                **prior,
                "state": "cleared",
                "last_changed_at": event["at"],
                "cleared_at": event["at"],
                "alert": event.get("alert", prior.get("alert")),
            }
    # Reconcile from the authoritative current snapshot on every poll. This
    # repairs a crash after status replacement but before attention replacement
    # without requiring the alert transition to occur a second time.
    current_alerts = _old_mapping(current, "alerts")
    for key, alert in current_alerts.items():
        if not isinstance(key, str) or not isinstance(alert, Mapping):
            continue
        prior = entries.get(key)
        if prior is None:
            entries[key] = {
                "state": "active",
                "first_raised_at": current["observed_at"],
                "last_changed_at": current["observed_at"],
                "cleared_at": None,
                "acknowledged_at": None,
                "occurrences": 1,
                "alert": alert,
            }
        elif prior.get("state") != "active":
            entries[key] = {
                **prior,
                "state": "active",
                "last_changed_at": current["observed_at"],
                "cleared_at": None,
                "acknowledged_at": None,
                "occurrences": int(prior.get("occurrences", 0)) + 1,
                "alert": alert,
            }
        else:
            entries[key] = {**prior, "alert": alert}
    notification = current.get("notification", {})
    return {
        "schema_version": ATTENTION_SCHEMA,
        "updated_at": current["observed_at"],
        "needs_attention": any(
            value.get("acknowledged_at") is None for value in entries.values()
        ),
        "active_alert_keys": sorted(current.get("alerts", {})),
        "entries": entries,
        "notification": notification if isinstance(notification, Mapping) else {},
    }


def acknowledge_attention(
    path: Path, keys: tuple[str, ...], *, acknowledge_all: bool, now: float
) -> int:
    attention = load_attention(path)
    if attention is None:
        raise MonitorError(f"attention file does not exist: {path}")
    entries = _old_mapping(attention, "entries")
    requested = set(entries) if acknowledge_all else set(keys)
    unknown = requested - set(entries)
    if unknown:
        raise MonitorError(f"unknown attention keys: {', '.join(sorted(unknown))}")
    stamp = _utc(now)
    updated = {
        key: (
            {**value, "acknowledged_at": stamp}
            if key in requested and isinstance(value, Mapping)
            else value
        )
        for key, value in entries.items()
    }
    write_json_atomic(
        path,
        {
            **attention,
            "updated_at": stamp,
            "needs_attention": any(
                isinstance(value, Mapping)
                and value.get("acknowledged_at") is None
                for value in updated.values()
            ),
            "entries": updated,
        },
    )
    return len(requested)


WINDOWS_TOAST_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
$nodes = $xml.GetElementsByTagName('text')
$nodes.Item(0).AppendChild($xml.CreateTextNode($env:NFL_MONITOR_TITLE)) > $null
$nodes.Item(1).AppendChild($xml.CreateTextNode($env:NFL_MONITOR_BODY)) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Windows PowerShell').Show($toast)
""".strip()


def _notification_event_id(event: Mapping[str, object]) -> str:
    material = {
        key: event.get(key)
        for key in ("event", "key", "registration_key", "at", "after", "alert")
    }
    return json.dumps(material, sort_keys=True, separators=(",", ":"))


def _notifiable_events(events: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for event in events:
        kind = event.get("event")
        if kind in ("alert_raised", "alert_updated") or (
            kind == "cohort_transition" and event.get("after") in ("failed", "succeeded")
        ) or (
            kind == "registered_coordinator_accepted"
            and event.get("effective_state") == "succeeded"
        ) or (
            kind == "provider_cohort_completed_without_acceptance"
        ):
            selected.append(dict(event))
    return selected


def _notification_text(events: list[Mapping[str, object]]) -> tuple[str, str]:
    errors = any(
        isinstance(event.get("alert"), Mapping)
        and event["alert"].get("severity") == "error"
        for event in events
    )
    accepted_registration_keys = {
        event.get("registration_key")
        for event in events
        if event.get("event") == "registered_coordinator_accepted"
    }
    successful_acceptance = any(
        (
            event.get("event") == "cohort_transition"
            and event.get("after") == "succeeded"
        )
        or event.get("event") == "registered_coordinator_accepted"
        for event in events
    )
    unresolved_without_acceptance = [
        event
        for event in events
        if event.get("event") == "provider_cohort_completed_without_acceptance"
        and event.get("registration_key") not in accepted_registration_keys
    ]
    failed_acceptance = any(
        event.get("effective_state") == "failed"
        for event in unresolved_without_acceptance
    )
    pending_acceptance = any(
        event.get("effective_state") == "pending_acceptance"
        for event in unresolved_without_acceptance
    )
    if failed_acceptance and not errors:
        title = "NFL cloud results need adjudication"
    elif pending_acceptance and not errors:
        title = "NFL cloud results await acceptance"
    elif successful_acceptance and not errors:
        title = "NFL cloud cohort completed"
    else:
        title = "NFL cloud jobs need attention" if errors else "NFL cloud job warning"
    details: list[str] = []
    for event in events[:5]:
        if event.get("event") == "cohort_transition":
            details.append(f"cohort is {event.get('after')}")
            continue
        if event.get("event") == "registered_coordinator_accepted":
            details.append("coordinator accepted provider results")
            continue
        if event.get("event") == "provider_cohort_completed_without_acceptance":
            if event.get("registration_key") in accepted_registration_keys:
                continue
            if event.get("effective_state") == "failed":
                details.append(
                    "provider cohort complete; coordinator acceptance was not obtained"
                )
            else:
                details.append(
                    "provider cohort complete; coordinator acceptance is pending"
                )
            continue
        alert = event.get("alert", {})
        if not isinstance(alert, Mapping):
            continue
        execution = alert.get("execution") or alert.get("prefix") or event.get("key")
        kind = alert.get("kind")
        if kind in ("execution_retried", "exact_e4_retried"):
            details.append(
                f"{execution}: {alert.get('retried_count')}/{alert.get('task_count')} tasks retried"
            )
        elif kind in ("execution_failed", "exact_e4_failed"):
            details.append(f"{execution}: failed ({alert.get('reason') or 'provider failure'})")
        elif kind == "lane_capacity_with_unclaimed_prefix":
            details.append(f"{execution}: queue target unclaimed while a lane is free")
        elif kind in ("provider_query_failed", "exact_e4_query_failed"):
            details.append(f"{execution}: provider query failed")
        elif kind == "registered_coordinator_failed":
            details.append(
                f"{alert.get('coordinator')}: coordinator failed after provider work"
            )
        elif kind == "registered_coordinator_post_provider_pending":
            details.append(
                f"{alert.get('coordinator')}: provider succeeded but acceptance gate is pending"
            )
        else:
            details.append(f"{execution}: {kind}")
    if len(events) > 5:
        details.append(f"and {len(events) - 5} more")
    return title, "; ".join(details)[:900]


def deliver_windows_toast(
    command: str,
    events: list[Mapping[str, object]],
    *,
    timeout: float,
    runner: Runner | None = None,
) -> str | None:
    title, body = _notification_text(events)
    environment = {**os.environ, "NFL_MONITOR_TITLE": title, "NFL_MONITOR_BODY": body}
    call = runner or subprocess.run
    try:
        result = call(
            [
                command,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                WINDOWS_TOAST_SCRIPT,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)
    if result.returncode:
        return (result.stderr or result.stdout or "no detail").strip()[:800]
    return None


def _prepare_notification(
    config: Config,
    previous: Mapping[str, object] | None,
    events: Iterable[Mapping[str, object]],
    *,
    now: float,
) -> tuple[dict[str, object], bool]:
    prior = _old_mapping(previous, "notification")
    pending_raw = prior.get("pending_events", [])
    pending = [dict(item) for item in pending_raw if isinstance(item, Mapping)]
    known = {_notification_event_id(item) for item in pending}
    new_events = _notifiable_events(events)
    for event in new_events:
        identity = _notification_event_id(event)
        if identity not in known:
            pending.append(event)
            known.add(identity)
    last_attempt_epoch = prior.get("last_attempt_at_epoch")
    retry_due = (
        not isinstance(last_attempt_epoch, (int, float))
        or now - float(last_attempt_epoch) >= config.notification_retry_seconds
    )
    should_attempt = bool(
        config.windows_toast_command
        and pending
        and (new_events or retry_due)
    )
    return (
        {
            "enabled": bool(config.windows_toast_command),
            "transport": "windows_toast" if config.windows_toast_command else "disabled",
            "pending_events": pending if config.windows_toast_command else [],
            "last_attempt_at": prior.get("last_attempt_at"),
            "last_attempt_at_epoch": last_attempt_epoch,
            "last_success_at": prior.get("last_success_at"),
            "last_error": prior.get("last_error"),
        },
        should_attempt,
    )


def run_once(
    config: Config,
    *,
    runner: Runner | None = None,
    notifier: Runner | None = None,
    clock: Callable[[], float] | None = None,
    emit: Callable[[str], object] | None = None,
) -> dict[str, object]:
    previous = load_status(config.state_file)
    observed = (clock or time.time)()
    current = collect_status(
        config, previous, now=observed, runner=runner
    )
    events = transition_events(previous, current)
    notification, should_notify = _prepare_notification(
        config, previous, events, now=observed
    )
    current["notification"] = notification
    prior_attention = (
        load_attention(config.attention_file) if config.attention_file else None
    )
    attention = update_attention(prior_attention, current, events)
    if config.events_file:
        append_events(config.events_file, events)
    write_status_atomic(config.state_file, current)
    if config.attention_file:
        write_json_atomic(config.attention_file, attention)

    if should_notify:
        pending = notification["pending_events"]
        assert isinstance(pending, list)
        error = deliver_windows_toast(
            str(config.windows_toast_command),
            pending,
            timeout=config.notification_timeout_seconds,
            runner=notifier,
        )
        notification["last_attempt_at"] = current["observed_at"]
        notification["last_attempt_at_epoch"] = observed
        if error is None:
            notification["pending_events"] = []
            notification["last_success_at"] = current["observed_at"]
            notification["last_error"] = None
            delivery_event = {
                "schema_version": EVENT_SCHEMA,
                "at": current["observed_at"],
                "event": "notification_delivered",
                "transport": "windows_toast",
            }
        else:
            notification["last_error"] = error
            delivery_event = {
                "schema_version": EVENT_SCHEMA,
                "at": current["observed_at"],
                "event": "notification_delivery_failed",
                "transport": "windows_toast",
                "error": error,
            }
        events.append(delivery_event)
        if config.events_file:
            append_events(config.events_file, [delivery_event])
        write_status_atomic(config.state_file, current)
        if config.attention_file:
            attention = update_attention(attention, current, [delivery_event])
            write_json_atomic(config.attention_file, attention)

    output = emit or (lambda line: print(line, flush=True))
    for event in events:
        output(json.dumps(event, sort_keys=True, separators=(",", ":")))
    return current


def _positive(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write atomic Cloud Run lane status and journal only transitions."
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("~/.local/state/nfl-dfs/cloud-run-lane-monitor.json"),
    )
    parser.add_argument("--events-file", type=Path)
    parser.add_argument("--attention-file", type=Path)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--job", action="append", dest="jobs")
    parser.add_argument("--expect-prefix", action="append", default=[])
    parser.add_argument(
        "--launcher-registry-dir", action="append", type=Path, default=[]
    )
    parser.add_argument("--launcher-lane")
    parser.add_argument("--queue-grace-seconds", type=_positive, default=120.0)
    parser.add_argument("--stall-seconds", type=_positive, default=3_600.0)
    parser.add_argument(
        "--coordinator-post-provider-grace-seconds",
        type=_positive,
        default=180.0,
    )
    parser.add_argument("--e4-execution")
    parser.add_argument("--e4-project", default=DEFAULT_E4_PROJECT)
    parser.add_argument("--e4-stall-seconds", type=_positive, default=25_200.0)
    parser.add_argument("--poll-seconds", type=_positive, default=60.0)
    parser.add_argument("--command-timeout-seconds", type=_positive, default=45.0)
    parser.add_argument("--windows-toast-command")
    parser.add_argument(
        "--notification-timeout-seconds", type=_positive, default=10.0
    )
    parser.add_argument(
        "--notification-retry-seconds", type=_positive, default=300.0
    )
    parser.add_argument("--gcloud", default="gcloud")
    parser.add_argument("--ack-alert", action="append", default=[])
    parser.add_argument("--ack-all", action="store_true")
    parser.add_argument("--once", action="store_true")
    return parser


def _config(args: argparse.Namespace) -> Config:
    jobs = tuple(args.jobs or DEFAULT_JOBS)
    prefixes = tuple(dict.fromkeys(args.expect_prefix))
    if not jobs or any(not value.strip() for value in jobs):
        raise MonitorError("at least one nonempty lab job is required")
    if len(jobs) != len(set(jobs)):
        raise MonitorError("lab jobs must be unique")
    if any(not value.strip() for value in prefixes):
        raise MonitorError("expected prefixes must be nonempty")
    registry_dirs = tuple(path.expanduser() for path in args.launcher_registry_dir)
    if registry_dirs and not args.launcher_lane:
        raise MonitorError("--launcher-lane is required with a launcher registry")
    if args.launcher_lane and not registry_dirs:
        raise MonitorError("--launcher-registry-dir is required with --launcher-lane")
    if args.windows_toast_command is not None and not args.windows_toast_command.strip():
        raise MonitorError("Windows toast command must be nonempty")
    return Config(
        state_file=args.state_file.expanduser(),
        events_file=args.events_file.expanduser() if args.events_file else None,
        attention_file=(
            args.attention_file.expanduser() if args.attention_file else None
        ),
        project=args.project,
        region=args.region,
        jobs=jobs,
        expected_prefixes=prefixes,
        launcher_registry_dirs=registry_dirs,
        launcher_lane=args.launcher_lane,
        queue_grace_seconds=args.queue_grace_seconds,
        stall_seconds=args.stall_seconds,
        coordinator_post_provider_grace_seconds=(
            args.coordinator_post_provider_grace_seconds
        ),
        e4_execution=args.e4_execution,
        e4_project=args.e4_project,
        e4_stall_seconds=args.e4_stall_seconds,
        command_timeout_seconds=args.command_timeout_seconds,
        windows_toast_command=args.windows_toast_command,
        notification_timeout_seconds=args.notification_timeout_seconds,
        notification_retry_seconds=args.notification_retry_seconds,
        gcloud=args.gcloud,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        config = _config(args)
        if args.ack_all or args.ack_alert:
            if config.attention_file is None:
                raise MonitorError("--attention-file is required to acknowledge alerts")
            count = acknowledge_attention(
                config.attention_file,
                tuple(args.ack_alert),
                acknowledge_all=args.ack_all,
                now=time.time(),
            )
            print(json.dumps({"acknowledged": count}, sort_keys=True))
            return 0
        while True:
            run_once(config)
            if args.once:
                return 0
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        return 130
    except MonitorError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
