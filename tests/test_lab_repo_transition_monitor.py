from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts import lab_repo_transition_monitor as monitor


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, relative: str, content: str, message: str) -> str:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", relative)
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_wake_path_is_bounded_to_coordination_surfaces() -> None:
    assert monitor._wake_path("handoffs/LAUNCH-CONTRACT-085.md")
    assert monitor._wake_path("reports/2026-09-03-read.md")
    assert monitor._wake_path("PREREG-062.md")
    assert monitor._wake_path("scripts/queue_085_efficacy_bound.sh")
    assert monitor._wake_path("scripts/prereg054_report.py")
    assert not monitor._wake_path("src/nfl2/laws.py")


def test_poll_records_each_new_commit_and_failures_are_visible(tmp_path: Path) -> None:
    upstream = tmp_path / "upstream.git"
    writer = tmp_path / "writer"
    watcher = tmp_path / "watcher"
    subprocess.run(["git", "init", "--bare", str(upstream)], check=True)
    subprocess.run(["git", "clone", str(upstream), str(writer)], check=True)
    _git(writer, "config", "user.name", "Test")
    _git(writer, "config", "user.email", "test@example.invalid")
    _git(writer, "checkout", "-b", "main")
    _commit(writer, "README.md", "base\n", "base")
    _git(writer, "push", "-u", "origin", "main")
    subprocess.run(["git", "clone", "-b", "main", str(upstream), str(watcher)], check=True)

    config = monitor.Config(
        repo=watcher,
        state_file=tmp_path / "state.json",
        events_file=tmp_path / "events.jsonl",
    )
    monitor.poll_once(config, clock=lambda: 1.0, emit=lambda _: None)
    wake = _commit(writer, "handoffs/NEXT.md", "launch\n", "launch request")
    quiet = _commit(writer, "src/law.py", "x = 1\n", "implementation")
    _git(writer, "push", "origin", "main")
    status = monitor.poll_once(config, clock=lambda: 2.0, emit=lambda _: None)
    assert status["head"] == quiet
    events = [
        json.loads(line)
        for line in config.events_file.read_text(encoding="utf-8").splitlines()
    ]
    commits = [event for event in events if event["event"] == "new_commit"]
    assert [event["commit"] for event in commits] == [wake, quiet]
    assert [event["wake_worthy"] for event in commits] == [True, False]
