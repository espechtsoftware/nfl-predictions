#!/usr/bin/env python3
"""Durable, read-only monitor for Cloud Build in the two program projects.

The monitor discovers both ongoing and recent builds, preserves every exact
``project/build-id`` it has observed, and writes status transitions to an
fsynced JSONL ledger.  It has no Cloud Build mutation command path.  Terminal
transitions and stalled/query alerts can be delivered through the same
bounded Windows WinRT toast mechanism used by the Cloud Run monitor.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scripts.cloud_run_lane_monitor import (
    WINDOWS_TOAST_SCRIPT,
    append_events,
    write_json_atomic,
)


STATUS_SCHEMA = "cloud-build-monitor-status/v1"
EVENT_SCHEMA = "cloud-build-monitor-event/v1"
DEFAULT_PROJECTS = ("nfl-2-506823", "nfl-predictions-503414")
NONTERMINAL_STATUSES = frozenset(("STATUS_UNKNOWN", "PENDING", "QUEUED", "WORKING"))
TERMINAL_STATUSES = frozenset(
    ("SUCCESS", "FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED", "EXPIRED")
)


class MonitorError(RuntimeError):
    """The monitor's local configuration or durable state is invalid."""


class ProviderError(RuntimeError):
    """A read-only provider query or response was invalid."""


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class Config:
    state_file: Path
    events_file: Path | None = None
    projects: tuple[str, ...] = DEFAULT_PROJECTS
    recent_limit: int = 100
    stale_working_seconds: float = 3_600.0
    bootstrap_terminal_lookback_seconds: float = 21_600.0
    command_timeout_seconds: float = 45.0
    windows_toast_command: str | None = None
    notification_timeout_seconds: float = 10.0
    notification_retry_seconds: float = 300.0
    gcloud: str = "gcloud"

    def identity(self) -> dict[str, object]:
        return {
            "projects": list(self.projects),
            "recent_limit": self.recent_limit,
            "stale_working_seconds": self.stale_working_seconds,
            "bootstrap_terminal_lookback_seconds": (
                self.bootstrap_terminal_lookback_seconds
            ),
            "query_policy": "ongoing-plus-recent-read-only/v1",
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


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _build_key(project: str, build_id: str) -> str:
    return f"{project}:{build_id}"


def _state_class(status: str, finish_time: object) -> str:
    if status in NONTERMINAL_STATUSES:
        return "working" if status == "WORKING" else "pending"
    if status == "SUCCESS":
        return "success"
    if status in ("FAILURE", "INTERNAL_ERROR"):
        return "failure"
    if status == "CANCELLED":
        return "cancelled"
    if status in ("TIMEOUT", "EXPIRED"):
        return "timeout"
    return "unknown_terminal" if finish_time else "unknown"


def _summary(row: Mapping[str, object], project: str) -> dict[str, object]:
    build_id = row.get("id")
    status = row.get("status")
    if not isinstance(build_id, str) or not build_id.strip():
        raise ProviderError(f"{project} build response has no exact id")
    if not isinstance(status, str) or not status.strip():
        raise ProviderError(f"{project}/{build_id} has no provider status")
    status = status.strip().upper()
    create_time = row.get("createTime")
    start_time = row.get("startTime")
    finish_time = row.get("finishTime")
    for label, value in (
        ("createTime", create_time),
        ("startTime", start_time),
        ("finishTime", finish_time),
    ):
        if value is not None and _epoch(value) is None:
            raise ProviderError(f"{project}/{build_id} has invalid {label}")
    if status in TERMINAL_STATUSES and not finish_time:
        # Preserve the provider status but make the incomplete terminal
        # mechanics visible rather than inventing a finish timestamp.
        terminal_mechanics_complete = False
    else:
        terminal_mechanics_complete = True
    state_class = _state_class(status, finish_time)
    return {
        "project": project,
        "build_id": build_id,
        "status": status,
        "state_class": state_class,
        "create_time": create_time,
        "start_time": start_time,
        "finish_time": finish_time,
        "status_detail": row.get("statusDetail"),
        "log_url": row.get("logUrl"),
        "terminal_mechanics_complete": terminal_mechanics_complete,
    }


def _query_json(
    args: list[str], *, timeout: float, runner: Runner | None
) -> object:
    call = runner or subprocess.run
    try:
        result = call(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProviderError(f"provider query failed: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "no detail").strip()[:800]
        raise ProviderError(
            f"provider query exited {result.returncode}: {detail}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProviderError("provider query returned invalid JSON") from exc


def _list_builds(
    config: Config,
    project: str,
    *,
    ongoing: bool,
    runner: Runner | None,
) -> list[Mapping[str, object]]:
    args = [config.gcloud, "builds", "list"]
    if ongoing:
        args.append("--ongoing")
    args.extend(
        [
            "--project",
            project,
            "--sort-by=~createTime",
            "--limit",
            str(config.recent_limit),
            "--format=json",
        ]
    )
    value = _query_json(
        args,
        timeout=config.command_timeout_seconds,
        runner=runner,
    )
    if not isinstance(value, list) or not all(
        isinstance(row, Mapping) for row in value
    ):
        phase = "ongoing" if ongoing else "recent"
        raise ProviderError(f"{project} {phase} build list is not an object array")
    return value


def _query_phase(
    config: Config,
    project: str,
    *,
    phase: str,
    runner: Runner | None,
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    try:
        rows = _list_builds(
            config, project, ongoing=phase == "ongoing", runner=runner
        )
        builds: dict[str, dict[str, object]] = {}
        for row in rows:
            item = _summary(row, project)
            key = _build_key(project, str(item["build_id"]))
            if key in builds and builds[key] != item:
                raise ProviderError(
                    f"{project} {phase} response duplicates build "
                    f"{item['build_id']} with different metadata"
                )
            builds[key] = item
    except ProviderError as exc:
        return {}, {"ok": False, "error": str(exc)}
    return builds, {"ok": True, "error": None, "count": len(builds)}


def _is_nonterminal(item: Mapping[str, object]) -> bool:
    return item.get("status") in NONTERMINAL_STATUSES


def _working_age(item: Mapping[str, object], now: float) -> float | None:
    started = _epoch(item.get("start_time"))
    created = _epoch(item.get("create_time"))
    origin = started if started is not None else created
    return max(0.0, now - origin) if origin is not None else None


def collect_status(
    config: Config,
    previous: Mapping[str, object] | None,
    *,
    now: float,
    runner: Runner | None = None,
) -> dict[str, object]:
    """Return one coherent status snapshot from read-only list queries."""
    if not math.isfinite(now):
        raise MonitorError("clock returned a nonfinite value")
    if previous is not None and previous.get("monitor") != config.identity():
        previous = None
    old_builds = _mapping(previous.get("builds")) if previous else {}
    builds: dict[str, dict[str, object]] = {}
    queries: dict[str, dict[str, object]] = {}
    projects: dict[str, dict[str, object]] = {}
    alerts: dict[str, dict[str, object]] = {}
    stamp = _utc(now)

    for project in config.projects:
        ongoing, ongoing_query = _query_phase(
            config, project, phase="ongoing", runner=runner
        )
        recent, recent_query = _query_phase(
            config, project, phase="recent", runner=runner
        )
        queries[f"{project}:ongoing"] = ongoing_query
        queries[f"{project}:recent"] = recent_query
        # The recent query is issued after ongoing and therefore wins a race
        # where a build becomes terminal between the two calls.
        fresh = {**ongoing, **recent}
        for key, item in fresh.items():
            prior = old_builds.get(key)
            first_seen = (
                prior.get("first_seen_at")
                if isinstance(prior, Mapping)
                else stamp
            )
            builds[key] = {
                **item,
                "first_seen_at": first_seen,
                "last_seen_at": stamp,
                "last_seen_at_epoch": now,
                "provider_observation_stale": False,
            }

        project_prefix = f"{project}:"
        for key, item in old_builds.items():
            if (
                key.startswith(project_prefix)
                and key not in builds
                and isinstance(item, Mapping)
            ):
                builds[key] = {
                    **item,
                    "provider_observation_stale": True,
                }

        phase_queries = {"ongoing": ongoing_query, "recent": recent_query}
        for phase, query in phase_queries.items():
            if query["ok"]:
                continue
            alert_key = f"provider-query:{project}:{phase}"
            alerts[alert_key] = {
                "kind": "cloud_build_query_failed",
                "severity": "error",
                "project": project,
                "phase": phase,
                "error": query["error"],
            }

        project_items = {
            key: item
            for key, item in builds.items()
            if key.startswith(project_prefix)
        }
        active_ids: list[str] = []
        working_ids: list[str] = []
        pending_ids: list[str] = []
        stale_active_ids: list[str] = []
        stale_working_ids: list[str] = []
        provider_stale_ids: list[str] = []
        for key, item in sorted(project_items.items()):
            if item.get("provider_observation_stale"):
                provider_stale_ids.append(str(item["build_id"]))
            if not _is_nonterminal(item):
                continue
            build_id = str(item["build_id"])
            active_ids.append(build_id)
            if item.get("status") == "WORKING":
                working_ids.append(build_id)
            else:
                pending_ids.append(build_id)
            age = _working_age(item, now)
            stale_reason: str | None = None
            if item.get("provider_observation_stale"):
                stale_reason = "provider_observation_not_refreshed"
            elif age is not None and age >= config.stale_working_seconds:
                stale_reason = "working_duration_threshold_exceeded"
            if stale_reason is None:
                continue
            stale_active_ids.append(build_id)
            if item.get("status") == "WORKING":
                stale_working_ids.append(build_id)
            alert_key = f"working-stale:{project}:{build_id}"
            alerts[alert_key] = {
                "kind": "cloud_build_working_stale",
                "severity": "warning",
                "project": project,
                "build_id": build_id,
                "status": item.get("status"),
                "reason": stale_reason,
                "working_age_seconds": int(age) if age is not None else None,
                "threshold_seconds": config.stale_working_seconds,
                "last_seen_at": item.get("last_seen_at"),
            }
        query_ok_count = sum(bool(value["ok"]) for value in phase_queries.values())
        query_state = (
            "ok" if query_ok_count == 2 else "partial" if query_ok_count else "error"
        )
        projects[project] = {
            "query_state": query_state,
            "observed_build_ids": sorted(
                str(item["build_id"]) for item in fresh.values()
            ),
            "active_build_ids": active_ids,
            "working_build_ids": working_ids,
            "pending_build_ids": pending_ids,
            "stale_active_build_ids": stale_active_ids,
            "stale_working_build_ids": stale_working_ids,
            "provider_stale_build_ids": provider_stale_ids,
        }

    sequence = int(previous.get("sequence", 0)) + 1 if previous else 1
    return {
        "schema_version": STATUS_SCHEMA,
        "sequence": sequence,
        "observed_at": stamp,
        "observed_at_epoch": now,
        "monitor": config.identity(),
        "queries": queries,
        "projects": projects,
        "builds": builds,
        "alerts": alerts,
    }


def _event(kind: str, at: object, **details: object) -> dict[str, object]:
    return {
        "schema_version": EVENT_SCHEMA,
        "at": at,
        "event": kind,
        **details,
    }


def _alert_signature(alert: Mapping[str, object]) -> str:
    material = {
        key: alert.get(key)
        for key in (
            "kind",
            "severity",
            "project",
            "phase",
            "build_id",
            "status",
            "reason",
            "error",
        )
    }
    return json.dumps(material, sort_keys=True, separators=(",", ":"))


def transition_events(
    previous: Mapping[str, object] | None,
    current: Mapping[str, object],
) -> list[dict[str, object]]:
    """Emit exact build-status and alert transitions only once."""
    at = current["observed_at"]
    if previous is not None and previous.get("monitor") != current.get("monitor"):
        previous = None
    events: list[dict[str, object]] = []
    old_builds = _mapping(previous.get("builds")) if previous else {}
    new_builds = _mapping(current.get("builds"))
    if previous is None:
        events.append(_event("monitor_started", at))

    now = float(current["observed_at_epoch"])
    lookback = float(current["monitor"]["bootstrap_terminal_lookback_seconds"])
    for key, item in sorted(new_builds.items()):
        if not isinstance(item, Mapping) or item.get("provider_observation_stale"):
            continue
        prior = old_builds.get(key)
        if not isinstance(prior, Mapping):
            if _is_nonterminal(item):
                events.append(
                    _event(
                        "build_observed",
                        at,
                        project=item.get("project"),
                        build_id=item.get("build_id"),
                        status=item.get("status"),
                    )
                )
            terminal_epoch = (
                _epoch(item.get("finish_time"))
                or _epoch(item.get("start_time"))
                or _epoch(item.get("create_time"))
            )
            if (
                item.get("state_class")
                in ("success", "failure", "cancelled", "timeout")
                and terminal_epoch is not None
                and 0 <= now - terminal_epoch <= lookback
            ):
                events.append(_terminal_event(at, item, bootstrap=True))
            continue
        before = prior.get("status")
        after = item.get("status")
        if before == after:
            continue
        events.append(
            _event(
                "build_status_transition",
                at,
                project=item.get("project"),
                build_id=item.get("build_id"),
                before=before,
                after=after,
                start_time=item.get("start_time"),
                finish_time=item.get("finish_time"),
            )
        )
        if item.get("state_class") in (
            "success",
            "failure",
            "cancelled",
            "timeout",
        ):
            events.append(_terminal_event(at, item, bootstrap=False))

    old_alerts = _mapping(previous.get("alerts")) if previous else {}
    new_alerts = _mapping(current.get("alerts"))
    for key in sorted(new_alerts.keys() - old_alerts.keys()):
        events.append(
            _event(
                "alert_raised",
                at,
                key=key,
                alert=new_alerts[key],
            )
        )
    for key in sorted(new_alerts.keys() & old_alerts.keys()):
        before = old_alerts[key]
        after = new_alerts[key]
        if (
            isinstance(before, Mapping)
            and isinstance(after, Mapping)
            and _alert_signature(before) != _alert_signature(after)
        ):
            events.append(
                _event(
                    "alert_updated",
                    at,
                    key=key,
                    before=before,
                    alert=after,
                )
            )
    for key in sorted(old_alerts.keys() - new_alerts.keys()):
        events.append(
            _event(
                "alert_cleared",
                at,
                key=key,
                alert=old_alerts[key],
            )
        )
    return events


def _terminal_event(
    at: object, item: Mapping[str, object], *, bootstrap: bool
) -> dict[str, object]:
    return _event(
        "build_terminal",
        at,
        project=item.get("project"),
        build_id=item.get("build_id"),
        status=item.get("status"),
        outcome=item.get("state_class"),
        create_time=item.get("create_time"),
        start_time=item.get("start_time"),
        finish_time=item.get("finish_time"),
        log_url=item.get("log_url"),
        bootstrap=bootstrap,
    )


def load_status(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise MonitorError(f"cannot read status file {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != STATUS_SCHEMA:
        raise MonitorError(f"status file {path} has an unsupported schema")
    return value


def _event_id(event: Mapping[str, object]) -> str:
    material = {
        key: event.get(key)
        for key in ("event", "at", "project", "build_id", "status", "key", "alert")
    }
    return json.dumps(material, sort_keys=True, separators=(",", ":"))


def _notifiable(events: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    return [
        dict(event)
        for event in events
        if event.get("event") in ("build_terminal", "alert_raised", "alert_updated")
    ]


def _notification_text(events: list[Mapping[str, object]]) -> tuple[str, str]:
    terminal = [event for event in events if event.get("event") == "build_terminal"]
    alerts = [
        event
        for event in events
        if event.get("event") in ("alert_raised", "alert_updated")
    ]
    failures = any(
        event.get("outcome") in ("failure", "cancelled", "timeout")
        for event in terminal
    ) or any(
        isinstance(event.get("alert"), Mapping)
        and event["alert"].get("severity") == "error"
        for event in alerts
    )
    title = (
        "NFL Cloud Builds need attention"
        if failures
        else "NFL Cloud Build completed"
    )
    details: list[str] = []
    for event in terminal[:5]:
        project = str(event.get("project") or "unknown-project")
        build_id = str(event.get("build_id") or "unknown-build")
        details.append(f"{project}/{build_id[:12]}: {event.get('status')}")
    for event in alerts[: max(0, 5 - len(details))]:
        alert = _mapping(event.get("alert"))
        target = alert.get("build_id") or alert.get("project") or event.get("key")
        details.append(f"{target}: {alert.get('kind')}")
    if len(terminal) + len(alerts) > 5:
        details.append(f"and {len(terminal) + len(alerts) - 5} more")
    return title, "; ".join(details)[:900]


def _prepare_notification(
    config: Config,
    previous: Mapping[str, object] | None,
    events: list[Mapping[str, object]],
    *,
    now: float,
) -> tuple[dict[str, object], bool]:
    prior = _mapping(previous.get("notification")) if previous else {}
    pending_raw = prior.get("pending_events", [])
    pending = [dict(value) for value in pending_raw if isinstance(value, Mapping)]
    known = {_event_id(value) for value in pending}
    new_events = _notifiable(events)
    for event in new_events:
        identity = _event_id(event)
        if identity not in known:
            pending.append(event)
            known.add(identity)
    last_attempt = prior.get("last_attempt_at_epoch")
    retry_due = (
        not isinstance(last_attempt, (int, float))
        or now - float(last_attempt) >= config.notification_retry_seconds
    )
    should_attempt = bool(
        config.windows_toast_command and pending and (new_events or retry_due)
    )
    return (
        {
            "enabled": bool(config.windows_toast_command),
            "transport": (
                "windows_winrt_toast"
                if config.windows_toast_command
                else "disabled"
            ),
            "pending_events": pending if config.windows_toast_command else [],
            "last_attempt_at": prior.get("last_attempt_at"),
            "last_attempt_at_epoch": last_attempt,
            "last_success_at": prior.get("last_success_at"),
            "last_error": prior.get("last_error"),
        },
        should_attempt,
    )


def deliver_toast(
    command: str,
    title: str,
    body: str,
    *,
    timeout: float,
    runner: Runner | None = None,
) -> str | None:
    call = runner or subprocess.run
    environment = {
        **os.environ,
        "NFL_MONITOR_TITLE": title[:160],
        "NFL_MONITOR_BODY": body[:900],
    }
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
        detail = result.stderr or result.stdout or "no detail"
        return str(detail).strip()[:800]
    return None


def poll_once(
    config: Config,
    *,
    runner: Runner | None = None,
    notifier: Runner | None = None,
    clock: Callable[[], float] | None = None,
    emit: Callable[[str], object] | None = None,
) -> dict[str, object]:
    previous = load_status(config.state_file)
    now = (clock or time.time)()
    current = collect_status(config, previous, now=now, runner=runner)
    events = transition_events(previous, current)
    notification, should_notify = _prepare_notification(
        config, previous, events, now=now
    )
    current["notification"] = notification
    if config.events_file:
        append_events(config.events_file, events)
    write_json_atomic(config.state_file, current)

    if should_notify:
        pending = notification["pending_events"]
        assert isinstance(pending, list)
        title, body = _notification_text(pending)
        error = deliver_toast(
            str(config.windows_toast_command),
            title,
            body,
            timeout=config.notification_timeout_seconds,
            runner=notifier,
        )
        notification["last_attempt_at"] = current["observed_at"]
        notification["last_attempt_at_epoch"] = now
        if error is None:
            notification["pending_events"] = []
            notification["last_success_at"] = current["observed_at"]
            notification["last_error"] = None
            delivery = _event(
                "notification_delivered",
                current["observed_at"],
                transport="windows_winrt_toast",
            )
        else:
            notification["last_error"] = error
            delivery = _event(
                "notification_delivery_failed",
                current["observed_at"],
                transport="windows_winrt_toast",
                error=error,
            )
        events.append(delivery)
        if config.events_file:
            append_events(config.events_file, [delivery])
        write_json_atomic(config.state_file, current)

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


def _positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist exact Cloud Build status transitions read-only."
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("~/.local/state/nfl-dfs/cloud-build-monitor/status.json"),
    )
    parser.add_argument("--events-file", type=Path)
    parser.add_argument("--project", action="append", dest="projects")
    parser.add_argument("--recent-limit", type=_positive_integer, default=100)
    parser.add_argument(
        "--stale-working-seconds", type=_positive, default=3_600.0
    )
    parser.add_argument(
        "--bootstrap-terminal-lookback-seconds",
        type=_positive,
        default=21_600.0,
    )
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
    parser.add_argument("--once", action="store_true")
    return parser


def _config(args: argparse.Namespace) -> Config:
    projects = tuple(args.projects or DEFAULT_PROJECTS)
    if not projects or any(not value.strip() for value in projects):
        raise MonitorError("at least one nonempty Cloud Build project is required")
    if len(projects) != len(set(projects)):
        raise MonitorError("Cloud Build projects must be unique")
    if not args.gcloud.strip():
        raise MonitorError("gcloud command must be nonempty")
    if (
        args.windows_toast_command is not None
        and not args.windows_toast_command.strip()
    ):
        raise MonitorError("Windows toast command must be nonempty")
    return Config(
        state_file=args.state_file.expanduser(),
        events_file=args.events_file.expanduser() if args.events_file else None,
        projects=projects,
        recent_limit=args.recent_limit,
        stale_working_seconds=args.stale_working_seconds,
        bootstrap_terminal_lookback_seconds=(
            args.bootstrap_terminal_lookback_seconds
        ),
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
        while True:
            poll_once(config)
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
