from __future__ import annotations

import json
import stat
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from scripts import lab_action_note_monitor as monitor


@dataclass(frozen=True)
class Response:
    stdout: bytes = b""
    stderr: bytes = b""
    returncode: int = 0


class FakeGit:
    def __init__(self, responses: list[Response]) -> None:
        self._responses: Iterator[Response] = iter(responses)
        self.calls: list[list[str]] = []

    def __call__(
        self, args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(list(args))
        assert kwargs == {
            "check": False,
            "capture_output": True,
            "text": False,
            "timeout": 45.0,
        }
        response = next(self._responses)
        return subprocess.CompletedProcess(
            args,
            response.returncode,
            stdout=response.stdout,
            stderr=response.stderr,
        )


class FakeNotifier:
    def __init__(self, *, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(
        self, args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(args), dict(kwargs)))
        return subprocess.CompletedProcess(
            args, self.returncode, stdout="", stderr=self.stderr
        )


def _primary(update: int, suffix: str = "") -> bytes:
    return (
        "# Lab to production\n\n"
        f"## Update {update} (2026-09-01)\n\n"
        f"Action {suffix}\n"
    ).encode()


def _snapshot(commit: str, update: int, suffix: str = "") -> list[Response]:
    return _snapshot_primary(commit, _primary(update, suffix))


def _snapshot_primary(commit: str, primary: bytes) -> list[Response]:
    return [
        Response(),
        Response(stdout=f"{commit}\n".encode()),
        Response(stdout=primary),
        Response(stdout=b"# prereg\n"),
        Response(stdout=b"# ranking\n"),
    ]


def _config(tmp_path: Path, **kwargs: object) -> monitor.Config:
    return monitor.Config(
        repo=tmp_path / "lab",
        state_file=tmp_path / "state" / "status.json",
        events_file=tmp_path / "state" / "events.jsonl",
        **kwargs,
    )


def _ledger(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_initial_snapshot_reads_only_exact_fetched_commit_and_persists_mode_0600(
    tmp_path: Path,
) -> None:
    commit = "a" * 40
    fake = FakeGit(_snapshot(commit, 11))
    config = _config(tmp_path)

    status = monitor.poll_once(
        config, runner=fake, clock=lambda: 100.0, emit=lambda _: None
    )

    assert status["poll"] == {"ok": True, "error": None}
    assert status["last_good"]["commit"] == commit
    assert status["last_good"]["primary_highest_update"] == 11
    assert set(status["last_good"]["documents"]) == set(monitor.DOCUMENTS)
    assert "HANDOFF.md" not in monitor.DOCUMENTS
    assert stat.S_IMODE(config.state_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(config.events_file.stat().st_mode) == 0o600
    assert [call[3] for call in fake.calls] == [
        "fetch",
        "rev-parse",
        "show",
        "show",
        "show",
    ]
    assert fake.calls[0][4:] == ["--quiet", "origin", "main"]
    assert all(call[:3] == ["git", "-C", str(config.repo)] for call in fake.calls)
    assert [call[4] for call in fake.calls[2:]] == [
        f"{commit}:{path}" for path in monitor.DOCUMENTS
    ]
    forbidden = {"pull", "checkout", "reset", "merge", "rebase", "clean"}
    assert all(not (forbidden & set(call)) for call in fake.calls)
    assert [event["event"] for event in _ledger(config.events_file)] == [
        "monitor_started",
        "documents_changed",
        "new_highest_update",
    ]


def test_document_rewrite_and_new_update_send_one_bounded_non_shell_toast(
    tmp_path: Path,
) -> None:
    first = "a" * 40
    second = "b" * 40
    fake = FakeGit(
        [
            *_snapshot(first, 11),
            *_snapshot(second, 12, "cancel the obsolete cohort"),
        ]
    )
    notifier = FakeNotifier()
    config = _config(tmp_path, windows_toast_command="powershell.exe")
    monitor.poll_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=lambda: 100.0,
        emit=lambda _: None,
    )
    notifier.calls.clear()

    status = monitor.poll_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=lambda: 200.0,
        emit=lambda _: None,
    )

    assert status["last_good"]["primary_highest_update"] == 12
    assert status["notification"]["pending_events"] == []
    assert len(notifier.calls) == 1
    args, kwargs = notifier.calls[0]
    assert args[:3] == ["powershell.exe", "-NoProfile", "-NonInteractive"]
    assert "shell" not in kwargs
    assert kwargs["timeout"] == 10.0
    assert kwargs["env"]["NFL_MONITOR_TITLE"] == "NFL lab handoff changed"
    assert "Update 12" in kwargs["env"]["NFL_MONITOR_BODY"]
    assert len(kwargs["env"]["NFL_MONITOR_BODY"]) <= 900
    recent = _ledger(config.events_file)
    assert any(event["event"] == "new_highest_update" for event in recent)
    assert recent[-1]["event"] == "notification_delivered"


def test_duplicate_update_numbers_still_identify_and_notify_new_revision(
    tmp_path: Path,
) -> None:
    first = "1" * 40
    second = "2" * 40
    original = (
        "# Lab to production\n\n"
        "## Update 11 (2026-09-01): mechanics ready\n\n"
        "First action.\n\n"
        "## Update 12 (2026-09-01): launch r2\n\n"
        "Second action.\n"
    ).encode()
    revised = original + (
        "\n## Update 11 (2026-09-02): first read failed\n\n"
        "Close the scheduler.\n\n"
        "## Update 12 (2026-09-02): OPERATOR DECISION\n\n"
        "Adopt D800.\n"
    ).encode()
    fake = FakeGit(
        [
            *_snapshot_primary(first, original),
            *_snapshot_primary(second, revised),
        ]
    )
    notifier = FakeNotifier()
    config = _config(tmp_path, windows_toast_command="powershell.exe")
    baseline = monitor.poll_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=lambda: 100.0,
        emit=lambda _: None,
    )
    notifier.calls.clear()

    status = monitor.poll_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=lambda: 200.0,
        emit=lambda _: None,
    )

    last_good = status["last_good"]
    assert last_good["primary_highest_update"] == 12
    assert last_good["primary_update_heading_count"] == 4
    assert last_good["primary_duplicate_update_numbers"] == [11, 12]
    assert last_good["primary_document_revision"]["commit"] == second
    assert (
        last_good["primary_document_revision"]["revision_id"]
        != baseline["last_good"]["primary_document_revision"]["revision_id"]
    )
    assert last_good["primary_latest_heading"] == {
        "number": 12,
        "ordinal": 4,
        "occurrence_for_number": 2,
        "line": 15,
        "heading": "Update 12 (2026-09-02): OPERATOR DECISION",
        "title": "(2026-09-02): OPERATOR DECISION",
    }
    assert status["alerts"]["duplicate-update-numbers"]["numbers"] == [11, 12]

    assert len(notifier.calls) == 1
    body = notifier.calls[0][1]["env"]["NFL_MONITOR_BODY"]
    assert "document changed at new commit 222222222222" in body
    assert "latest heading occurrence 4" in body
    assert "OPERATOR DECISION" in body
    assert "duplicate update numbers: 11, 12" in body

    second_events = [
        event
        for event in _ledger(config.events_file)
        if event.get("commit") == second
    ]
    changed = next(
        event for event in second_events if event["event"] == "documents_changed"
    )
    assert changed["primary_document_changed"] is True
    assert changed["previous_commit"] == first
    assert changed["primary_document_revision"] == last_good[
        "primary_document_revision"
    ]
    assert changed["latest_heading"] == last_good["primary_latest_heading"]
    assert changed["highest_update"] == changed["previous_highest_update"] == 12
    assert any(
        event["event"] == "duplicate_update_numbers_detected"
        for event in second_events
    )
    assert not any(
        event["event"] == "new_highest_update" for event in second_events
    )


def test_fetch_failure_alerts_once_and_never_overwrites_last_good_hashes(
    tmp_path: Path,
) -> None:
    commit = "c" * 40
    fake = FakeGit(
        [
            *_snapshot(commit, 11),
            Response(returncode=1, stderr=b"network unavailable"),
            Response(returncode=1, stderr=b"network unavailable"),
        ]
    )
    notifier = FakeNotifier()
    config = _config(tmp_path, windows_toast_command="powershell.exe")
    first = monitor.poll_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=lambda: 100.0,
        emit=lambda _: None,
    )
    good = first["last_good"]
    notifier.calls.clear()

    failed = monitor.poll_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=lambda: 200.0,
        emit=lambda _: None,
    )
    repeated = monitor.poll_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=lambda: 250.0,
        emit=lambda _: None,
    )

    assert failed["last_good"] == good
    assert repeated["last_good"] == good
    assert failed["alerts"]["lab-inbox-read"]["severity"] == "error"
    assert repeated["poll"]["ok"] is False
    assert len(notifier.calls) == 1
    assert "failed" in notifier.calls[0][1]["env"]["NFL_MONITOR_TITLE"]
    failures = [
        event for event in _ledger(config.events_file) if event["event"] == "poll_failed"
    ]
    assert len(failures) == 1
    assert [call[3] for call in fake.calls[-2:]] == ["fetch", "fetch"]


def test_partial_blob_read_failure_does_not_publish_mixed_snapshot(
    tmp_path: Path,
) -> None:
    first = "d" * 40
    second = "e" * 40
    fake = FakeGit(
        [
            *_snapshot(first, 11),
            Response(),
            Response(stdout=f"{second}\n".encode()),
            Response(stdout=_primary(12)),
            Response(returncode=1, stderr=b"missing PREREG-052.md"),
        ]
    )
    config = _config(tmp_path)
    baseline = monitor.poll_once(
        config, runner=fake, clock=lambda: 100.0, emit=lambda _: None
    )

    failed = monitor.poll_once(
        config, runner=fake, clock=lambda: 200.0, emit=lambda _: None
    )

    assert failed["poll"]["ok"] is False
    assert failed["last_good"] == baseline["last_good"]
    assert failed["last_good"]["commit"] == first
    assert failed["last_good"]["primary_highest_update"] == 11


def test_tracked_unit_is_persistent_and_points_at_durable_state() -> None:
    unit = (
        Path(__file__).resolve().parents[1]
        / "deploy/systemd/nfl-lab-action-note-monitor.service"
    ).read_text(encoding="utf-8")

    assert "Restart=always" in unit
    assert "WantedBy=default.target" in unit
    assert "--poll-seconds 120" in unit
    assert "-m scripts.lab_action_note_monitor" in unit
    assert "%h/projects/nfl2" in unit
    assert "%h/.local/state/nfl-dfs/lab-action-note-monitor/status.json" in unit
    assert "%h/.local/state/nfl-dfs/lab-action-note-monitor/events.jsonl" in unit
    assert "--windows-toast-command" in unit
