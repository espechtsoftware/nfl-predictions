#!/usr/bin/env python3
"""Read-only watcher for the lab-to-production handoff documents.

The watcher fetches ``origin/main`` without touching the lab worktree, reads
three fixed blobs from the fetched commit, and records only their identities.
It never pulls, checks out, merges, resets, or invokes any cloud command.
Document transitions and read failures are written to an fsynced JSONL ledger
and can be surfaced through a bounded, non-shell Windows WinRT toast.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
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


STATUS_SCHEMA = "lab-action-note-monitor-status/v1"
EVENT_SCHEMA = "lab-action-note-monitor-event/v1"
DEFAULT_REPO = Path("~/projects/nfl2")
DEFAULT_REMOTE = "origin"
DEFAULT_BRANCH = "main"
PRIMARY_DOCUMENT = "handoffs/LAB-TO-PRODUCTION-2026-09-01-ACTION-NOTE.md"
DOCUMENTS = (
    PRIMARY_DOCUMENT,
    "PREREG-052.md",
    "reports/2026-09-01-priority-ranking.md",
)
UPDATE_RE = re.compile(rb"(?m)^## Update ([0-9]+)(?=\b|[ :])")


class MonitorError(RuntimeError):
    """The monitor's durable state or configuration is invalid."""


class InboxReadError(RuntimeError):
    """The remote ref or one of its required blobs could not be read."""


Runner = Callable[..., subprocess.CompletedProcess[object]]


@dataclass(frozen=True)
class Config:
    repo: Path
    state_file: Path
    events_file: Path
    remote: str = DEFAULT_REMOTE
    branch: str = DEFAULT_BRANCH
    git: str = "git"
    command_timeout_seconds: float = 45.0
    windows_toast_command: str | None = None
    notification_timeout_seconds: float = 10.0
    notification_retry_seconds: float = 300.0

    @property
    def ref(self) -> str:
        return f"{self.remote}/{self.branch}"

    def identity(self) -> dict[str, object]:
        return {
            "repo": str(self.repo),
            "remote": self.remote,
            "branch": self.branch,
            "documents": list(DOCUMENTS),
            "read_policy": "fetch-ref-then-read-pinned-commit/v1",
        }


def _utc(epoch: float) -> str:
    return (
        datetime.fromtimestamp(epoch, timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _run(
    args: list[str],
    *,
    timeout: float,
    runner: Runner | None,
) -> bytes:
    call = runner or subprocess.run
    try:
        result = call(
            args,
            check=False,
            capture_output=True,
            text=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InboxReadError(f"git command failed: {exc}") from exc
    if result.returncode:
        stderr = result.stderr
        stdout = result.stdout
        detail_raw = stderr or stdout or b"no detail"
        if isinstance(detail_raw, str):
            detail = detail_raw
        else:
            detail = bytes(detail_raw).decode("utf-8", errors="replace")
        raise InboxReadError(
            f"git command exited {result.returncode}: {detail.strip()[:800]}"
        )
    value = result.stdout
    return value.encode("utf-8") if isinstance(value, str) else bytes(value)


def _highest_update(content: bytes) -> int | None:
    values = [int(match.group(1)) for match in UPDATE_RE.finditer(content)]
    return max(values, default=None)


def fetch_snapshot(
    config: Config, *, runner: Runner | None = None
) -> dict[str, object]:
    """Fetch and read a coherent snapshot without mutating the lab worktree."""
    base = [config.git, "-C", str(config.repo)]
    _run(
        [*base, "fetch", "--quiet", config.remote, config.branch],
        timeout=config.command_timeout_seconds,
        runner=runner,
    )
    raw_commit = _run(
        [*base, "rev-parse", "--verify", f"{config.ref}^{{commit}}"],
        timeout=config.command_timeout_seconds,
        runner=runner,
    )
    try:
        commit = raw_commit.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise InboxReadError("fetched commit identity is not ASCII") from exc
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise InboxReadError("fetched commit identity is not a full SHA-1")

    blobs: dict[str, dict[str, object]] = {}
    primary_update: int | None = None
    for document in DOCUMENTS:
        content = _run(
            [*base, "show", f"{commit}:{document}"],
            timeout=config.command_timeout_seconds,
            runner=runner,
        )
        blobs[document] = {
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        }
        if document == PRIMARY_DOCUMENT:
            primary_update = _highest_update(content)
    return {
        "commit": commit,
        "documents": blobs,
        "primary_highest_update": primary_update,
    }


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


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _document_hashes(snapshot: Mapping[str, object]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path, value in _mapping(snapshot.get("documents")).items():
        if isinstance(path, str) and isinstance(value, Mapping):
            digest = value.get("sha256")
            if isinstance(digest, str):
                result[path] = digest
    return result


def _event(kind: str, at: str, **details: object) -> dict[str, object]:
    return {
        "schema_version": EVENT_SCHEMA,
        "at": at,
        "event": kind,
        **details,
    }


def _event_id(event: Mapping[str, object]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


def _notifiable(events: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    kinds = {"documents_changed", "new_highest_update", "poll_failed"}
    return [dict(event) for event in events if event.get("event") in kinds]


def _notification_text(
    events: list[Mapping[str, object]], status: Mapping[str, object]
) -> tuple[str, str]:
    failures = [event for event in events if event.get("event") == "poll_failed"]
    if failures:
        error = str(failures[-1].get("error") or "unknown fetch/read failure")
        return "NFL lab handoff monitor failed", error[:900]
    last_good = _mapping(status.get("last_good"))
    update = last_good.get("primary_highest_update")
    changed: list[str] = []
    for event in events:
        if event.get("event") == "documents_changed":
            values = event.get("documents", [])
            if isinstance(values, list):
                changed.extend(Path(str(value)).name for value in values[:3])
    update_text = f"Update {update}" if isinstance(update, int) else "action note"
    suffix = f"; changed: {', '.join(dict.fromkeys(changed))}" if changed else ""
    return "NFL lab handoff changed", f"Lab {update_text} is available{suffix}"[:900]


def deliver_toast(
    command: str,
    title: str,
    body: str,
    *,
    timeout: float,
    runner: Runner | None = None,
) -> str | None:
    """Deliver a bounded WinRT toast without a shell or document content."""
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


def _notification(
    config: Config,
    previous: Mapping[str, object] | None,
    events: list[Mapping[str, object]],
    *,
    now: float,
) -> tuple[dict[str, object], bool]:
    prior = _mapping(previous.get("notification")) if previous else {}
    raw_pending = prior.get("pending_events", [])
    pending = [dict(value) for value in raw_pending if isinstance(value, Mapping)]
    known = {_event_id(value) for value in pending}
    new_events = _notifiable(events)
    for value in new_events:
        identity = _event_id(value)
        if identity not in known:
            pending.append(value)
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
                "windows_winrt_toast" if config.windows_toast_command else "disabled"
            ),
            "pending_events": pending if config.windows_toast_command else [],
            "last_attempt_at": prior.get("last_attempt_at"),
            "last_attempt_at_epoch": last_attempt,
            "last_success_at": prior.get("last_success_at"),
            "last_error": prior.get("last_error"),
        },
        should_attempt,
    )


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
    if not math.isfinite(now):
        raise MonitorError("clock returned a nonfinite value")
    at = _utc(now)
    sequence = int(previous.get("sequence", 0)) + 1 if previous else 1
    old_good = _mapping(previous.get("last_good")) if previous else {}
    prior_poll = _mapping(previous.get("poll")) if previous else {}
    events: list[dict[str, object]] = []
    if previous is None:
        events.append(_event("monitor_started", at))

    try:
        snapshot = fetch_snapshot(config, runner=runner)
    except InboxReadError as exc:
        error = str(exc)
        if prior_poll.get("ok") is not False or prior_poll.get("error") != error:
            events.append(_event("poll_failed", at, error=error))
        status: dict[str, object] = {
            "schema_version": STATUS_SCHEMA,
            "sequence": sequence,
            "observed_at": at,
            "observed_at_epoch": now,
            "monitor": config.identity(),
            "poll": {"ok": False, "error": error},
            # This is copied intact: a partial/failed read never advances hashes.
            "last_good": dict(old_good),
            "alerts": {
                "lab-inbox-read": {
                    "kind": "lab_action_note_read_failed",
                    "severity": "error",
                    "error": error,
                }
            },
        }
    else:
        old_hashes = _document_hashes(old_good)
        new_hashes = _document_hashes(snapshot)
        changed = sorted(
            path for path in DOCUMENTS if old_hashes.get(path) != new_hashes.get(path)
        )
        old_update = old_good.get("primary_highest_update")
        new_update = snapshot.get("primary_highest_update")
        if prior_poll.get("ok") is False:
            events.append(_event("poll_recovered", at, commit=snapshot["commit"]))
        if changed:
            events.append(
                _event(
                    "documents_changed",
                    at,
                    commit=snapshot["commit"],
                    documents=changed,
                    previous_highest_update=old_update,
                    highest_update=new_update,
                )
            )
        if isinstance(new_update, int) and (
            not isinstance(old_update, int) or new_update > old_update
        ):
            events.append(
                _event(
                    "new_highest_update",
                    at,
                    commit=snapshot["commit"],
                    previous=old_update,
                    current=new_update,
                )
            )
        if old_good and not changed and old_good.get("commit") != snapshot["commit"]:
            events.append(
                _event(
                    "source_advanced_without_document_change",
                    at,
                    previous_commit=old_good.get("commit"),
                    commit=snapshot["commit"],
                )
            )
        status = {
            "schema_version": STATUS_SCHEMA,
            "sequence": sequence,
            "observed_at": at,
            "observed_at_epoch": now,
            "monitor": config.identity(),
            "poll": {"ok": True, "error": None},
            "last_good": {**snapshot, "observed_at": at},
            "alerts": {},
        }

    notification, should_notify = _notification(
        config, previous, events, now=now
    )
    status["notification"] = notification
    append_events(config.events_file, events)
    write_json_atomic(config.state_file, status)

    if should_notify:
        pending = notification["pending_events"]
        assert isinstance(pending, list)
        title, body = _notification_text(pending, status)
        error = deliver_toast(
            str(config.windows_toast_command),
            title,
            body,
            timeout=config.notification_timeout_seconds,
            runner=notifier,
        )
        notification["last_attempt_at"] = at
        notification["last_attempt_at_epoch"] = now
        if error is None:
            notification["pending_events"] = []
            notification["last_success_at"] = at
            notification["last_error"] = None
            delivery = _event("notification_delivered", at)
        else:
            notification["last_error"] = error
            delivery = _event("notification_delivery_failed", at, error=error)
        events.append(delivery)
        append_events(config.events_file, [delivery])
        write_json_atomic(config.state_file, status)

    output = emit or (lambda line: print(line, flush=True))
    for event in events:
        output(json.dumps(event, sort_keys=True, separators=(",", ":")))
    return status


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
        description="Watch exact origin/main lab handoff blobs without pulling."
    )
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path(
            "~/.local/state/nfl-dfs/lab-action-note-monitor/status.json"
        ),
    )
    parser.add_argument(
        "--events-file",
        type=Path,
        default=Path(
            "~/.local/state/nfl-dfs/lab-action-note-monitor/events.jsonl"
        ),
    )
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--git", default="git")
    parser.add_argument("--command-timeout-seconds", type=_positive, default=45.0)
    parser.add_argument("--poll-seconds", type=_positive, default=120.0)
    parser.add_argument("--windows-toast-command")
    parser.add_argument(
        "--notification-timeout-seconds", type=_positive, default=10.0
    )
    parser.add_argument(
        "--notification-retry-seconds", type=_positive, default=300.0
    )
    parser.add_argument("--once", action="store_true")
    return parser


def _config(args: argparse.Namespace) -> Config:
    repo = args.repo.expanduser().resolve()
    if not repo.is_dir():
        raise MonitorError(f"lab repository does not exist: {repo}")
    if not args.remote.strip() or not args.branch.strip():
        raise MonitorError("remote and branch must be nonempty")
    if args.windows_toast_command is not None and not args.windows_toast_command.strip():
        raise MonitorError("Windows toast command must be nonempty")
    return Config(
        repo=repo,
        state_file=args.state_file.expanduser(),
        events_file=args.events_file.expanduser(),
        remote=args.remote,
        branch=args.branch,
        git=args.git,
        command_timeout_seconds=args.command_timeout_seconds,
        windows_toast_command=args.windows_toast_command,
        notification_timeout_seconds=args.notification_timeout_seconds,
        notification_retry_seconds=args.notification_retry_seconds,
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
