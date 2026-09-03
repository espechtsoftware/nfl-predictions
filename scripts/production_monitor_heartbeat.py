#!/usr/bin/env python3
"""Backstop production monitors and publish one durable health snapshot."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts.cloud_run_lane_monitor import append_events, write_json_atomic
from scripts.lab_action_note_monitor import deliver_toast

STATUS_SCHEMA = "production-monitor-heartbeat-status/v1"
EVENT_SCHEMA = "production-monitor-heartbeat-event/v1"


class HeartbeatError(RuntimeError):
    """Heartbeat configuration or state is invalid."""


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class Target:
    unit: str
    state_file: Path
    max_age_seconds: float


@dataclass(frozen=True)
class Config:
    targets: tuple[Target, ...]
    status_file: Path
    events_file: Path
    systemctl: str = "systemctl"
    command_timeout_seconds: float = 30.0
    windows_toast_command: str | None = None
    notification_timeout_seconds: float = 10.0


def _utc(epoch: float) -> str:
    return (
        datetime.fromtimestamp(epoch, UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _run(
    args: list[str], *, config: Config, runner: Runner | None = None
) -> subprocess.CompletedProcess[str]:
    call = runner or subprocess.run
    try:
        return call(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=config.command_timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HeartbeatError(f"command failed: {exc}") from exc


def _service_state(
    config: Config, unit: str, *, runner: Runner | None = None
) -> str:
    result = _run(
        [config.systemctl, "--user", "is-active", unit],
        config=config,
        runner=runner,
    )
    return result.stdout.strip() or "unknown"


def _restart(
    config: Config, unit: str, *, runner: Runner | None = None
) -> tuple[bool, str | None]:
    result = _run(
        [config.systemctl, "--user", "restart", unit],
        config=config,
        runner=runner,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "no detail").strip()[:800]
        return False, detail
    return True, None


def _monitor_state(path: Path) -> Mapping[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def _active_alerts(state: Mapping[str, object] | None) -> list[str]:
    if not state:
        return []
    alerts = state.get("alerts")
    if isinstance(alerts, Mapping):
        return sorted(str(key) for key in alerts)
    return []


def run_once(
    config: Config,
    *,
    runner: Runner | None = None,
    notifier: Runner | None = None,
    clock: Callable[[], float] | None = None,
    emit: Callable[[str], object] | None = None,
) -> dict[str, object]:
    now = (clock or time.time)()
    if not math.isfinite(now):
        raise HeartbeatError("clock returned a nonfinite value")
    at = _utc(now)
    rows: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    for target in config.targets:
        service_state = _service_state(config, target.unit, runner=runner)
        state = _monitor_state(target.state_file)
        observed = state.get("observed_at_epoch") if state else None
        age = now - float(observed) if isinstance(observed, (int, float)) else None
        stale = age is None or age > target.max_age_seconds
        poll = state.get("poll") if state else None
        poll_ok = poll.get("ok") if isinstance(poll, Mapping) else None
        restart_reason: str | None = None
        if service_state != "active":
            restart_reason = f"service-{service_state}"
        elif stale:
            restart_reason = "state-missing-or-stale"
        restarted = False
        restart_error: str | None = None
        if restart_reason:
            restarted, restart_error = _restart(
                config, target.unit, runner=runner
            )
            events.append(
                {
                    "schema_version": EVENT_SCHEMA,
                    "at": at,
                    "event": "monitor_restarted" if restarted else "restart_failed",
                    "unit": target.unit,
                    "reason": restart_reason,
                    "error": restart_error,
                }
            )
        if poll_ok is False:
            events.append(
                {
                    "schema_version": EVENT_SCHEMA,
                    "at": at,
                    "event": "monitor_poll_unhealthy",
                    "unit": target.unit,
                    "error": poll.get("error") if isinstance(poll, Mapping) else None,
                }
            )
        rows.append(
            {
                "unit": target.unit,
                "service_state": service_state,
                "state_file": str(target.state_file),
                "state_age_seconds": age,
                "max_age_seconds": target.max_age_seconds,
                "poll_ok": poll_ok,
                "active_alerts": _active_alerts(state),
                "restart_reason": restart_reason,
                "restarted": restarted,
                "restart_error": restart_error,
            }
        )
    status = {
        "schema_version": STATUS_SCHEMA,
        "observed_at": at,
        "observed_at_epoch": now,
        "healthy": not any(
            row["restart_error"] is not None or row["poll_ok"] is False
            for row in rows
        ),
        "targets": rows,
        "next_action": (
            "inspect emitted monitor event"
            if events
            else "no action needed; continue state-diff monitoring"
        ),
    }
    append_events(config.events_file, events)
    write_json_atomic(config.status_file, status)
    if config.windows_toast_command and events:
        latest = events[-1]
        error = deliver_toast(
            config.windows_toast_command,
            "NFL production monitor heartbeat",
            f"{latest['event']}: {latest['unit']} ({latest.get('reason') or latest.get('error')})",
            timeout=config.notification_timeout_seconds,
            runner=notifier,
        )
        notification = {
            "schema_version": EVENT_SCHEMA,
            "at": at,
            "event": "notification_delivered" if error is None else "notification_failed",
            "error": error,
        }
        append_events(config.events_file, [notification])
        events.append(notification)
    output = emit or (lambda line: print(line, flush=True))
    # A heartbeat always emits one summary, including the healthy/no-action case.
    output(json.dumps(status, sort_keys=True, separators=(",", ":")))
    for event in events:
        output(json.dumps(event, sort_keys=True, separators=(",", ":")))
    return status


def _positive(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return parsed


def _target(value: str) -> Target:
    try:
        unit, path, raw_age = value.split("|", maxsplit=2)
        age = _positive(raw_age)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "target must be UNIT|STATE_FILE|MAX_AGE_SECONDS"
        ) from exc
    if not unit or not path:
        raise argparse.ArgumentTypeError("target unit and state path are required")
    return Target(unit=unit, state_file=Path(path).expanduser(), max_age_seconds=age)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", action="append", type=_target, required=True)
    parser.add_argument(
        "--status-file",
        type=Path,
        default=Path("~/.local/state/nfl-dfs/monitor-heartbeat/status.json"),
    )
    parser.add_argument(
        "--events-file",
        type=Path,
        default=Path("~/.local/state/nfl-dfs/monitor-heartbeat/events.jsonl"),
    )
    parser.add_argument("--systemctl", default="systemctl")
    parser.add_argument("--command-timeout-seconds", type=_positive, default=30.0)
    parser.add_argument("--windows-toast-command")
    parser.add_argument(
        "--notification-timeout-seconds", type=_positive, default=10.0
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = Config(
        targets=tuple(args.target),
        status_file=args.status_file.expanduser(),
        events_file=args.events_file.expanduser(),
        systemctl=args.systemctl,
        command_timeout_seconds=args.command_timeout_seconds,
        windows_toast_command=args.windows_toast_command,
        notification_timeout_seconds=args.notification_timeout_seconds,
    )
    run_once(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
