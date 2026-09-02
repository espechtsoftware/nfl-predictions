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
import json
import math
import os
import re
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


STATUS_SCHEMA = "cloud-run-lane-monitor-status/v2"
LEGACY_STATUS_SCHEMAS = frozenset(("cloud-run-lane-monitor-status/v1",))
EVENT_SCHEMA = "cloud-run-lane-monitor-event/v2"
ATTENTION_SCHEMA = "cloud-run-lane-monitor-attention/v1"
REGISTRY_SCHEMA = "shared-launcher-registry/v1"
ALERT_POLICY = "expected-execution-retry-and-capacity/v2"
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


def _live_registry_targets(config: Config) -> dict[str, object]:
    """Return one PID/start-tick-validated live queue receipt, if present."""
    if not config.launcher_registry_dirs:
        return {
            "state": "disabled",
            "lane": config.launcher_lane,
            "receipt": None,
            "prefixes": [],
            "error": None,
        }
    matches: list[tuple[Path, Mapping[str, object]]] = []
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
                    continue
                matches.append((path, receipt))
        if len(matches) > 1:
            names = ", ".join(str(path) for path, _ in matches)
            raise MonitorError(f"multiple live launcher receipts own the lane: {names}")
    except MonitorError as exc:
        return {
            "state": "error",
            "lane": config.launcher_lane,
            "receipt": None,
            "prefixes": [],
            "error": str(exc),
        }
    if not matches:
        return {
            "state": "no_live_receipt",
            "lane": config.launcher_lane,
            "receipt": None,
            "prefixes": [],
            "error": None,
        }
    path, receipt = matches[0]
    return {
        "state": "live",
        "lane": receipt["lane"],
        "receipt": str(path),
        "owner": receipt["owner"],
        "pid": receipt["pid"],
        "process_start_ticks": receipt["process_start_ticks"],
        "prefixes": list(receipt["target_run_id_prefixes"]),
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
    all_values = tuple(_strings(row)) if prefixes else ()
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
        "matched_expected_prefixes": [
            prefix for prefix in prefixes if any(prefix in value for value in all_values)
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
    if registry["state"] == "live":
        registry_prefixes = tuple(str(value) for value in registry["prefixes"])
        queue_source = "live_launcher_receipt"
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
        state = "claimed" if matches else ("unclaimed" if lab_ok else "unknown")
        prefix_status[prefix] = {
            "state": state,
            "execution_names": matches,
            "execution_states": states,
        }

    if not lab_ok:
        cohort_state = "unknown"
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
    for job, error in errors:
        alerts[f"provider-query:{job}"] = _alert(
            "provider_query_failed", "error", job=job, error=error
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
        "cohort": {"state": cohort_state},
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
    if (
        previous is None
        or previous.get("monitor") != current.get("monitor")
        or previous.get("schema_version") != STATUS_SCHEMA
    ):
        return [
            {**base, "event": "monitor_started", "lane_state": current["lane"]["state"]},
            *(
                {**base, "event": "alert_raised", "key": key, "alert": alert}
                for key, alert in sorted(alerts.items())
            ),
        ]
    events: list[dict[str, object]] = []
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
        for key in ("event", "key", "at", "after", "alert")
    }
    return json.dumps(material, sort_keys=True, separators=(",", ":"))


def _notifiable_events(events: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for event in events:
        kind = event.get("event")
        if kind in ("alert_raised", "alert_updated") or (
            kind == "cohort_transition" and event.get("after") in ("failed", "succeeded")
        ):
            selected.append(dict(event))
    return selected


def _notification_text(events: list[Mapping[str, object]]) -> tuple[str, str]:
    errors = any(
        isinstance(event.get("alert"), Mapping)
        and event["alert"].get("severity") == "error"
        for event in events
    )
    if any(
        event.get("event") == "cohort_transition" and event.get("after") == "succeeded"
        for event in events
    ) and not errors:
        title = "NFL cloud cohort completed"
    else:
        title = "NFL cloud jobs need attention" if errors else "NFL cloud job warning"
    details: list[str] = []
    for event in events[:5]:
        if event.get("event") == "cohort_transition":
            details.append(f"cohort is {event.get('after')}")
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
