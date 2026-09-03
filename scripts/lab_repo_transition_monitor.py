#!/usr/bin/env python3
"""Watch every lab ``origin/main`` transition and surface actionable commits.

The monitor never changes the lab checkout.  It fetches the remote tracking
ref, records every newly reachable commit, and marks commits touching the
research handoff/contract/result surfaces as wake-worthy.  Poll failures are
events too, so a dead network or invalid repository cannot look like an idle
queue.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from scripts.cloud_run_lane_monitor import append_events, write_json_atomic
from scripts.lab_action_note_monitor import deliver_toast

STATUS_SCHEMA = "lab-repo-transition-monitor-status/v1"
EVENT_SCHEMA = "lab-repo-transition-monitor-event/v1"
SHA_RE = re.compile(r"[0-9a-f]{40}")
MAX_COMMITS_PER_POLL = 100
MAX_PATHS_PER_COMMIT = 40


class MonitorError(RuntimeError):
    """The monitor configuration or durable state is invalid."""


class RepoReadError(RuntimeError):
    """The remote repository could not be read coherently."""


Runner = Callable[..., subprocess.CompletedProcess[object]]


@dataclass(frozen=True)
class Config:
    repo: Path
    state_file: Path
    events_file: Path
    remote: str = "origin"
    branch: str = "main"
    git: str = "git"
    command_timeout_seconds: float = 45.0
    windows_toast_command: str | None = None
    notification_timeout_seconds: float = 10.0

    @property
    def ref(self) -> str:
        return f"{self.remote}/{self.branch}"


def _utc(epoch: float) -> str:
    return (
        datetime.fromtimestamp(epoch, UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _run(
    args: list[str], *, config: Config, runner: Runner | None = None
) -> bytes:
    call = runner or subprocess.run
    try:
        result = call(
            args,
            check=False,
            capture_output=True,
            text=False,
            timeout=config.command_timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepoReadError(f"git command failed: {exc}") from exc
    if result.returncode:
        detail_raw = result.stderr or result.stdout or b"no detail"
        detail = (
            detail_raw
            if isinstance(detail_raw, str)
            else bytes(detail_raw).decode("utf-8", errors="replace")
        )
        raise RepoReadError(
            f"git command exited {result.returncode}: {detail.strip()[:800]}"
        )
    stdout = result.stdout
    return stdout.encode() if isinstance(stdout, str) else bytes(stdout)


def _git(config: Config, *args: str, runner: Runner | None = None) -> bytes:
    return _run(
        [config.git, "-C", str(config.repo), *args],
        config=config,
        runner=runner,
    )


def _head(config: Config, *, runner: Runner | None = None) -> str:
    _git(config, "fetch", "--quiet", config.remote, config.branch, runner=runner)
    value = _git(
        config,
        "rev-parse",
        "--verify",
        f"{config.ref}^{{commit}}",
        runner=runner,
    ).decode("ascii", errors="strict").strip()
    if SHA_RE.fullmatch(value) is None:
        raise RepoReadError("fetched head is not a full SHA-1")
    return value


def _wake_path(path: str) -> bool:
    """Return whether a changed path can request or unblock production work."""
    pure = PurePosixPath(path)
    if not pure.parts:
        return False
    if pure.parts[0] in {"handoffs", "reports"}:
        return True
    name = pure.name
    if len(pure.parts) == 1 and (
        name.startswith(("PREREG-", "AUDIT-"))
        and name.endswith(".md")
    ):
        return True
    if pure.parts[0] == "scripts":
        return (
            name.startswith(("queue_", "relaunch_"))
            or (name.startswith("prereg") and name.endswith("_report.py"))
        )
    return False


def _split_nul(raw: bytes) -> list[str]:
    return [
        value.decode("utf-8", errors="replace")
        for value in raw.split(b"\0")
        if value
    ]


def _commit_rows(
    config: Config,
    previous_head: str,
    head: str,
    *,
    runner: Runner | None = None,
) -> tuple[list[dict[str, object]], bool]:
    if SHA_RE.fullmatch(previous_head) is None:
        raise RepoReadError("previous head is not a full SHA-1")
    raw = _git(
        config,
        "rev-list",
        "--reverse",
        f"{previous_head}..{head}",
        runner=runner,
    )
    commits = [line for line in raw.decode("ascii").splitlines() if line]
    truncated = len(commits) > MAX_COMMITS_PER_POLL
    commits = commits[-MAX_COMMITS_PER_POLL:]
    rows: list[dict[str, object]] = []
    for commit in commits:
        if SHA_RE.fullmatch(commit) is None:
            raise RepoReadError("rev-list returned a malformed commit")
        subject = _git(
            config,
            "show",
            "-s",
            "--format=%s",
            commit,
            runner=runner,
        ).decode("utf-8", errors="replace").strip()[:500]
        paths = _split_nul(
            _git(
                config,
                "diff-tree",
                "--root",
                "--no-commit-id",
                "--name-only",
                "-r",
                "-z",
                commit,
                runner=runner,
            )
        )
        wake_paths = [path for path in paths if _wake_path(path)]
        rows.append(
            {
                "commit": commit,
                "subject": subject,
                "paths": paths[:MAX_PATHS_PER_COMMIT],
                "paths_truncated": len(paths) > MAX_PATHS_PER_COMMIT,
                "wake_paths": wake_paths[:MAX_PATHS_PER_COMMIT],
                "wake_paths_truncated": len(wake_paths) > MAX_PATHS_PER_COMMIT,
                "wake_worthy": bool(wake_paths),
            }
        )
    return rows, truncated


def _load(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise MonitorError(f"cannot read state file {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != STATUS_SCHEMA:
        raise MonitorError(f"state file {path} has an unsupported schema")
    return value


def _event(kind: str, at: str, **values: object) -> dict[str, object]:
    return {"schema_version": EVENT_SCHEMA, "at": at, "event": kind, **values}


def poll_once(
    config: Config,
    *,
    runner: Runner | None = None,
    notifier: Runner | None = None,
    clock: Callable[[], float] | None = None,
    emit: Callable[[str], object] | None = None,
) -> dict[str, object]:
    previous = _load(config.state_file)
    now = (clock or time.time)()
    if not math.isfinite(now):
        raise MonitorError("clock returned a nonfinite value")
    at = _utc(now)
    prior_head = previous.get("head") if previous else None
    prior_poll = previous.get("poll") if previous else None
    events: list[dict[str, object]] = []
    if previous is None:
        events.append(_event("monitor_started", at))
    try:
        head = _head(config, runner=runner)
        rows: list[dict[str, object]] = []
        truncated = False
        if isinstance(prior_head, str) and prior_head != head:
            rows, truncated = _commit_rows(
                config, prior_head, head, runner=runner
            )
            if not rows:
                # A force-push still must be visible even if old..new is empty.
                events.append(
                    _event(
                        "remote_history_replaced",
                        at,
                        previous_head=prior_head,
                        head=head,
                    )
                )
        if isinstance(prior_poll, Mapping) and prior_poll.get("ok") is False:
            events.append(_event("poll_recovered", at, head=head))
        for row in rows:
            events.append(_event("new_commit", at, **row))
        status: dict[str, object] = {
            "schema_version": STATUS_SCHEMA,
            "sequence": int(previous.get("sequence", 0)) + 1 if previous else 1,
            "observed_at": at,
            "observed_at_epoch": now,
            "repo": str(config.repo),
            "ref": config.ref,
            "head": head,
            "poll": {"ok": True, "error": None},
            "commits_truncated": truncated,
            "last_transition": rows[-1] if rows else (
                previous.get("last_transition") if previous else None
            ),
        }
    except (RepoReadError, UnicodeError) as exc:
        error = str(exc)
        if not isinstance(prior_poll, Mapping) or (
            prior_poll.get("ok") is not False or prior_poll.get("error") != error
        ):
            events.append(_event("poll_failed", at, error=error))
        status = {
            "schema_version": STATUS_SCHEMA,
            "sequence": int(previous.get("sequence", 0)) + 1 if previous else 1,
            "observed_at": at,
            "observed_at_epoch": now,
            "repo": str(config.repo),
            "ref": config.ref,
            "head": prior_head,
            "poll": {"ok": False, "error": error},
            "commits_truncated": False,
            "last_transition": previous.get("last_transition") if previous else None,
        }

    append_events(config.events_file, events)
    write_json_atomic(config.state_file, status)
    wake_events = [
        event
        for event in events
        if event.get("event") in {"poll_failed", "remote_history_replaced"}
        or (event.get("event") == "new_commit" and event.get("wake_worthy"))
    ]
    if config.windows_toast_command and wake_events:
        latest = wake_events[-1]
        if latest.get("event") == "new_commit":
            title = "NFL lab repository changed"
            body = (
                f"{str(latest.get('commit'))[:12]} {latest.get('subject')}; "
                f"wake paths: {', '.join(str(v) for v in latest.get('wake_paths', [])[:4])}"
            )
        else:
            title = "NFL lab repository monitor needs attention"
            body = str(latest.get("error") or latest.get("event"))
        error = deliver_toast(
            config.windows_toast_command,
            title[:160],
            body[:900],
            timeout=config.notification_timeout_seconds,
            runner=notifier,
        )
        notification = _event(
            "notification_delivered" if error is None else "notification_failed",
            at,
            error=error,
        )
        append_events(config.events_file, [notification])
        events.append(notification)

    output = emit or (lambda line: print(line, flush=True))
    for event in events:
        output(json.dumps(event, sort_keys=True, separators=(",", ":")))
    return status


def _positive(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("~/projects/nfl2"))
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("~/.local/state/nfl-dfs/lab-repo-monitor/status.json"),
    )
    parser.add_argument(
        "--events-file",
        type=Path,
        default=Path("~/.local/state/nfl-dfs/lab-repo-monitor/events.jsonl"),
    )
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--git", default="git")
    parser.add_argument("--command-timeout-seconds", type=_positive, default=45.0)
    parser.add_argument("--poll-seconds", type=_positive, default=120.0)
    parser.add_argument("--windows-toast-command")
    parser.add_argument(
        "--notification-timeout-seconds", type=_positive, default=10.0
    )
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = Config(
        repo=args.repo.expanduser().resolve(),
        state_file=args.state_file.expanduser(),
        events_file=args.events_file.expanduser(),
        remote=args.remote,
        branch=args.branch,
        git=args.git,
        command_timeout_seconds=args.command_timeout_seconds,
        windows_toast_command=args.windows_toast_command,
        notification_timeout_seconds=args.notification_timeout_seconds,
    )
    if not config.repo.is_dir():
        raise SystemExit(f"lab repository does not exist: {config.repo}")
    while True:
        poll_once(config)
        if args.once:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
