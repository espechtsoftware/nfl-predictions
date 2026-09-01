#!/usr/bin/env python3
"""Durable, read-only Cloud Run lane monitor for a systemd user service.

Each poll atomically replaces one JSON status file.  Stdout contains compact
JSON only when execution, lane, prefix, or alert state changes, so journald is
quiet between transitions.  Every gcloud call is an execution list/describe.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


STATUS_SCHEMA = "cloud-run-lane-monitor-status/v1"
EVENT_SCHEMA = "cloud-run-lane-monitor-event/v1"
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
    project: str = DEFAULT_PROJECT
    region: str = DEFAULT_REGION
    jobs: tuple[str, ...] = DEFAULT_JOBS
    expected_prefixes: tuple[str, ...] = ()
    stall_seconds: float = 3_600.0
    e4_execution: str | None = None
    e4_project: str = DEFAULT_E4_PROJECT
    e4_stall_seconds: float = 25_200.0
    command_timeout_seconds: float = 45.0
    gcloud: str = "gcloud"

    def identity(self) -> dict[str, object]:
        return {
            "project": self.project,
            "region": self.region,
            "jobs": list(self.jobs),
            "expected_prefixes": list(self.expected_prefixes),
            "stall_seconds": self.stall_seconds,
            "e4_execution": self.e4_execution,
            "e4_project": self.e4_project if self.e4_execution else None,
            "e4_stall_seconds": self.e4_stall_seconds if self.e4_execution else None,
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
                item = _summary(row, job, config.expected_prefixes)
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
    lane_state = "unknown" if not lab_ok else ("active" if active else "idle")
    prefix_status: dict[str, dict[str, object]] = {}
    for prefix in config.expected_prefixes:
        matches = sorted(
            item["name"]
            for key, item in fresh.items()
            if key.startswith("lab:")
            and prefix in item["matched_expected_prefixes"]
        )
        state = "claimed" if matches else ("unclaimed" if lab_ok else "unknown")
        prefix_status[prefix] = {"state": state, "execution_names": matches}

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
            if latest and latest["state"] in FAILED:
                alerts[f"execution-failure:{job}:{latest['name']}"] = _alert(
                    "execution_failed",
                    "error",
                    job=job,
                    execution=latest["name"],
                    state=latest["state"],
                    reason=latest["reason"],
                    counts=latest["counts"],
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
        if lane_state == "idle":
            for prefix, item in prefix_status.items():
                if item["state"] == "unclaimed":
                    alerts[f"lane-idle-unclaimed:{prefix}"] = _alert(
                        "lane_idle_with_unclaimed_prefix",
                        "error",
                        prefix=prefix,
                        jobs=list(config.jobs),
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
        "queries": queries,
        "lane": {"state": lane_state, "active_executions": active},
        "expected_prefixes": prefix_status,
        "executions": executions,
        "e4_execution_key": e4_key,
        "progress": progress,
        "alerts": alerts,
    }


def transition_events(
    previous: Mapping[str, object] | None, current: Mapping[str, object]
) -> list[dict[str, object]]:
    """Build transition-only event records for stdout/journald."""
    base = {"schema_version": EVENT_SCHEMA, "at": current["observed_at"]}
    alerts = _old_mapping(current, "alerts")
    if previous is None or previous.get("monitor") != current.get("monitor"):
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
    if not isinstance(value, dict) or value.get("schema_version") != STATUS_SCHEMA:
        raise MonitorError(f"status file {path} has an unsupported schema")
    return value


def write_status_atomic(path: Path, status: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(status, handle, sort_keys=True, separators=(",", ":"))
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


def run_once(
    config: Config,
    *,
    runner: Runner | None = None,
    clock: Callable[[], float] | None = None,
    emit: Callable[[str], object] | None = None,
) -> dict[str, object]:
    previous = load_status(config.state_file)
    current = collect_status(
        config, previous, now=(clock or time.time)(), runner=runner
    )
    events = transition_events(previous, current)
    write_status_atomic(config.state_file, current)
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
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--job", action="append", dest="jobs")
    parser.add_argument("--expect-prefix", action="append", default=[])
    parser.add_argument("--stall-seconds", type=_positive, default=3_600.0)
    parser.add_argument("--e4-execution")
    parser.add_argument("--e4-project", default=DEFAULT_E4_PROJECT)
    parser.add_argument("--e4-stall-seconds", type=_positive, default=25_200.0)
    parser.add_argument("--poll-seconds", type=_positive, default=60.0)
    parser.add_argument("--command-timeout-seconds", type=_positive, default=45.0)
    parser.add_argument("--gcloud", default="gcloud")
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
    return Config(
        state_file=args.state_file.expanduser(),
        project=args.project,
        region=args.region,
        jobs=jobs,
        expected_prefixes=prefixes,
        stall_seconds=args.stall_seconds,
        e4_execution=args.e4_execution,
        e4_project=args.e4_project,
        e4_stall_seconds=args.e4_stall_seconds,
        command_timeout_seconds=args.command_timeout_seconds,
        gcloud=args.gcloud,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        config = _config(args)
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
