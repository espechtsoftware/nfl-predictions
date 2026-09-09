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


def test_all_branch_scope_surfaces_handoff_commits_before_main(tmp_path: Path) -> None:
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
        all_branches=True,
    )
    baseline = monitor.poll_once(config, clock=lambda: 1.0, emit=lambda _: None)
    assert baseline["heads"] == {"main": _git(writer, "rev-parse", "main")}

    _git(writer, "checkout", "-b", "lab/review")
    implementation = _commit(writer, "src/law.py", "x = 1\n", "implementation")
    handoff = _commit(writer, "reports/REVIEW.md", "ready\n", "review handoff")
    _git(writer, "push", "-u", "origin", "lab/review")

    status = monitor.poll_once(config, clock=lambda: 2.0, emit=lambda _: None)
    assert status["heads"]["lab/review"] == handoff
    events = [
        json.loads(line)
        for line in config.events_file.read_text(encoding="utf-8").splitlines()
    ]
    created = [event for event in events if event["event"] == "remote_branch_created"]
    assert created[-1] == {
        "schema_version": monitor.EVENT_SCHEMA,
        "at": "1970-01-01T00:00:02Z",
        "event": "remote_branch_created",
        "branch": "lab/review",
        "head": handoff,
    }
    commits = [event for event in events if event["event"] == "new_commit"]
    assert [event["commit"] for event in commits] == [implementation, handoff]
    assert [event["branch"] for event in commits] == ["lab/review", "lab/review"]
    assert [event["wake_worthy"] for event in commits] == [False, True]


def test_all_branch_scope_migrates_main_only_state_without_history_flood(
    tmp_path: Path,
) -> None:
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

    state = tmp_path / "state.json"
    events_file = tmp_path / "events.jsonl"
    monitor.poll_once(
        monitor.Config(repo=watcher, state_file=state, events_file=events_file),
        clock=lambda: 1.0,
        emit=lambda _: None,
    )
    status = monitor.poll_once(
        monitor.Config(
            repo=watcher,
            state_file=state,
            events_file=events_file,
            all_branches=True,
        ),
        clock=lambda: 2.0,
        emit=lambda _: None,
    )
    events = [json.loads(line) for line in events_file.read_text().splitlines()]
    assert status["branch_count"] == 1 and status["heads"]["main"] == status["head"]
    assert [event["event"] for event in events].count("all_branches_baselined") == 1
    assert not [event for event in events if event["event"] == "new_commit"]


def test_systemd_unit_enables_all_branch_scope() -> None:
    unit = (
        Path(__file__).resolve().parents[1]
        / "deploy/systemd/nfl-lab-repo-transition-monitor.service"
    ).read_text()
    assert "--poll-seconds 120" in unit and "--all-branches" in unit
