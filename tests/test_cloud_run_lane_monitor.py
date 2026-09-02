from __future__ import annotations

import json
import os
import stat
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from scripts import cloud_run_lane_monitor as monitor


@dataclass(frozen=True)
class FailedCall:
    stderr: str = "simulated provider failure"
    returncode: int = 1


class FakeGcloud:
    def __init__(self, responses: list[object]) -> None:
        self._responses: Iterator[object] = iter(responses)
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        assert kwargs == {
            "check": False,
            "capture_output": True,
            "text": True,
            "timeout": 45.0,
        }
        response = next(self._responses)
        if isinstance(response, FailedCall):
            return subprocess.CompletedProcess(
                args, response.returncode, stdout="", stderr=response.stderr
            )
        return subprocess.CompletedProcess(
            args, 0, stdout=json.dumps(response), stderr=""
        )


class FakeClock:
    def __init__(self, *values: float) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


class FakeNotifier:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(args), dict(kwargs)))
        return subprocess.CompletedProcess(
            args, self.returncode, stdout="", stderr=self.stderr
        )


def _execution(
    name: str,
    job: str,
    state: str,
    *,
    run_id: str | None = None,
    transitioned_at: str = "1970-01-01T00:00:10Z",
    retried: int = 0,
    task_count: int = 1,
    created_at: str = "1970-01-01T00:00:00Z",
) -> dict[str, object]:
    condition = {
        "type": "Completed",
        "status": {"active": "Unknown", "success": "True", "failed": "False"}[state],
        "lastTransitionTime": transitioned_at,
    }
    status: dict[str, object] = {
        "conditions": [condition],
        "retriedCount": retried,
    }
    if state == "active":
        status.update(startTime="1970-01-01T00:00:10Z", runningCount=1)
    elif state == "success":
        status.update(
            startTime="1970-01-01T00:00:10Z",
            completionTime="1970-01-01T00:01:00Z",
            succeededCount=1,
        )
    else:
        condition.update(reason="NonZeroExitCode", message="task exited 1")
        status.update(
            startTime="1970-01-01T00:00:10Z",
            completionTime="1970-01-01T00:01:00Z",
            failedCount=1,
        )
    env = [] if run_id is None else [{"name": "RUN_ID", "value": run_id}]
    return {
        "metadata": {
            "name": name,
            "uid": f"uid-{name}",
            "creationTimestamp": created_at,
            "labels": {"run.googleapis.com/job": job},
        },
        "spec": {
            "taskCount": task_count,
            "template": {"spec": {"containers": [{"env": env}]}},
        },
        "status": status,
    }


def _events(lines: list[str]) -> list[dict[str, object]]:
    return [json.loads(line) for line in lines]


def test_cli_defaults_are_read_only_and_optional_e4_is_exact(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    prefix = "083-confirm-"
    e4_name = "atlas-cbc-32g-full-2023-w8-v1-7zpd4"
    fake = FakeGcloud(
        [
            [_execution("lab-run-a1", "lab-run", "active", run_id=f"{prefix}001")],
            [],
            _execution(e4_name, "atlas-cbc-32g-full-2023-w8-v1", "active"),
        ]
    )
    monkeypatch.setattr(monitor.subprocess, "run", fake)
    monkeypatch.setattr(monitor.time, "time", FakeClock(20.0))
    state_file = tmp_path / "state" / "status.json"

    assert monitor.main(
        [
            "--once",
            "--state-file",
            str(state_file),
            "--expect-prefix",
            prefix,
            "--e4-execution",
            e4_name,
        ]
    ) == 0

    status = json.loads(state_file.read_text(encoding="utf-8"))
    assert status["lane"]["state"] == "active"
    assert status["expected_prefixes"][prefix] == {
        "state": "claimed",
        "execution_names": ["lab-run-a1"],
        "execution_states": {"lab-run-a1": "running"},
    }
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600
    assert not list(state_file.parent.glob(".*.tmp"))
    assert [call[4] for call in fake.calls] == ["list", "list", "describe"]
    assert [call[call.index("--project") + 1] for call in fake.calls] == [
        "nfl-2-506823",
        "nfl-2-506823",
        "nfl-predictions-503414",
    ]
    assert fake.calls[2][5] == e4_name
    assert all(
        not ({"execute", "cancel", "update", "delete", "replace"} & set(call))
        for call in fake.calls
    )
    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [item["event"] for item in emitted] == ["monitor_started"]


def test_unchanged_poll_is_silent_then_idle_unclaimed_raises_once(tmp_path: Path) -> None:
    active = _execution("lab-run-a1", "lab-run", "active", run_id="different-run")
    succeeded = _execution("lab-run-a1", "lab-run", "success", run_id="different-run")
    fake = FakeGcloud([[active], [], [active], [], [succeeded], [], [succeeded], []])
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        expected_prefixes=("083-confirm-",),
        queue_grace_seconds=30,
        stall_seconds=1_000,
    )
    lines: list[str] = []

    monitor.run_once(config, runner=fake, clock=FakeClock(20), emit=lines.append)
    lines.clear()
    monitor.run_once(config, runner=fake, clock=FakeClock(30), emit=lines.append)
    assert lines == []

    monitor.run_once(config, runner=fake, clock=FakeClock(70), emit=lines.append)
    events = _events(lines)
    assert {item["event"] for item in events} >= {
        "execution_transition",
        "lane_transition",
        "alert_raised",
    }
    raised = [item for item in events if item["event"] == "alert_raised"]
    assert [item["key"] for item in raised] == [
        "lane-capacity-unclaimed:083-confirm-"
    ]
    current = monitor.load_status(config.state_file)
    assert current is not None
    assert current["lane"]["state"] == "idle"

    lines.clear()
    monitor.run_once(config, runner=fake, clock=FakeClock(80), emit=lines.append)
    assert lines == []


def test_stall_alert_is_transition_only_and_progress_clears_it(tmp_path: Path) -> None:
    active = _execution("lab-run-a1", "lab-run", "active")
    progressed = _execution("lab-run-a1", "lab-run", "active", retried=1)
    fake = FakeGcloud(
        [[active], [], [active], [], [active], [], [progressed], []]
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json", stall_seconds=60
    )
    lines: list[str] = []
    monitor.run_once(config, runner=fake, clock=FakeClock(10), emit=lines.append)

    lines.clear()
    monitor.run_once(config, runner=fake, clock=FakeClock(71), emit=lines.append)
    assert [(item["event"], item.get("key")) for item in _events(lines)] == [
        ("alert_raised", "execution-stalled:lab-run:lab-run-a1")
    ]

    lines.clear()
    monitor.run_once(config, runner=fake, clock=FakeClock(90), emit=lines.append)
    assert lines == []

    monitor.run_once(config, runner=fake, clock=FakeClock(91), emit=lines.append)
    events = _events(lines)
    assert [item["event"] for item in events] == [
        "execution_transition",
        "alert_raised",
        "alert_cleared",
    ]
    assert events[1]["key"] == "execution-retried:lab-run:lab-run-a1"
    assert events[2]["key"] == "execution-stalled:lab-run:lab-run-a1"


def test_failures_transition_and_partial_query_failure_never_claims_idle(
    tmp_path: Path,
) -> None:
    active = _execution("lab-run-a1", "lab-run", "active")
    failed = _execution("lab-run-a1", "lab-run", "failed")
    fake = FakeGcloud(
        [
            [active],
            [],
            [failed],
            [],
            [failed],
            FailedCall(),
        ]
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        expected_prefixes=("083-confirm-",),
        stall_seconds=1_000,
    )
    lines: list[str] = []
    monitor.run_once(config, runner=fake, clock=FakeClock(20), emit=lines.append)

    lines.clear()
    failed_status = monitor.run_once(
        config, runner=fake, clock=FakeClock(70), emit=lines.append
    )
    assert failed_status["alerts"]["execution-failure:lab-run:lab-run-a1"][
        "kind"
    ] == "execution_failed"
    assert {item["event"] for item in _events(lines)} >= {
        "execution_transition",
        "alert_raised",
    }

    lines.clear()
    unknown = monitor.run_once(
        config, runner=fake, clock=FakeClock(80), emit=lines.append
    )
    assert unknown["lane"]["state"] == "unknown"
    assert unknown["expected_prefixes"]["083-confirm-"]["state"] == "unknown"
    assert "provider-query:lab-run-slow" in unknown["alerts"]
    assert all(
        not key.startswith("lane-idle-unclaimed:") for key in unknown["alerts"]
    )


def test_exact_e4_failure_is_detected_without_listing_production(tmp_path: Path) -> None:
    name = "atlas-cbc-32g-full-2023-w8-v1-7zpd4"
    fake = FakeGcloud(
        [
            [],
            [],
            _execution(name, "atlas-cbc-32g-full-2023-w8-v1", "active"),
            [],
            [],
            _execution(name, "atlas-cbc-32g-full-2023-w8-v1", "failed"),
        ]
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        e4_execution=name,
        e4_stall_seconds=1_000,
    )
    lines: list[str] = []
    monitor.run_once(config, runner=fake, clock=FakeClock(20), emit=lines.append)

    lines.clear()
    status = monitor.run_once(
        config, runner=fake, clock=FakeClock(70), emit=lines.append
    )
    assert status["alerts"][f"e4-failure:{name}"]["kind"] == "exact_e4_failed"
    assert any(item["event"] == "execution_transition" for item in _events(lines))
    production_calls = [
        call
        for call in fake.calls
        if call[call.index("--project") + 1] == "nfl-predictions-503414"
    ]
    assert len(production_calls) == 2
    assert all(call[4:6] == ["describe", name] for call in production_calls)


def test_retry_raises_once_then_escalates_when_every_task_retried(
    tmp_path: Path,
) -> None:
    base = _execution("lab-run-a1", "lab-run", "active", task_count=2)
    one = _execution(
        "lab-run-a1", "lab-run", "active", retried=1, task_count=2
    )
    all_retried = _execution(
        "lab-run-a1", "lab-run", "active", retried=2, task_count=2
    )
    fake = FakeGcloud(
        [
            [base],
            [],
            [one],
            [],
            [all_retried],
            [],
            [all_retried],
            [],
        ]
    )
    config = monitor.Config(state_file=tmp_path / "status.json", stall_seconds=1_000)
    lines: list[str] = []
    monitor.run_once(config, runner=fake, clock=FakeClock(10), emit=lines.append)

    lines.clear()
    monitor.run_once(config, runner=fake, clock=FakeClock(20), emit=lines.append)
    raised = [item for item in _events(lines) if item["event"] == "alert_raised"]
    assert len(raised) == 1
    assert raised[0]["alert"]["severity"] == "warning"
    assert raised[0]["alert"]["escalation"] == "retry_observed"

    lines.clear()
    monitor.run_once(config, runner=fake, clock=FakeClock(30), emit=lines.append)
    updated = [item for item in _events(lines) if item["event"] == "alert_updated"]
    assert len(updated) == 1
    assert updated[0]["alert"]["severity"] == "error"
    assert updated[0]["alert"]["escalation"] == "all_tasks_retried"

    lines.clear()
    monitor.run_once(config, runner=fake, clock=FakeClock(40), emit=lines.append)
    assert lines == []


def test_failed_expected_execution_is_not_hidden_by_newer_execution(
    tmp_path: Path,
) -> None:
    prefix = "083b580r1"
    failed = _execution(
        "lab-run-old",
        "lab-run",
        "failed",
        run_id=f"{prefix}-run",
        created_at="1970-01-01T00:00:00Z",
    )
    newer = _execution(
        "lab-run-new",
        "lab-run",
        "active",
        run_id="unrelated-new-run",
        created_at="1970-01-01T00:02:00Z",
    )
    fake = FakeGcloud([[failed, newer], []])
    config = monitor.Config(
        state_file=tmp_path / "status.json", expected_prefixes=(prefix,)
    )

    status = monitor.run_once(config, runner=fake, clock=FakeClock(200), emit=lambda _: None)

    assert f"execution-failure:lab-run:lab-run-old" in status["alerts"]
    assert "execution-failure:lab-run:lab-run-new" not in status["alerts"]


def test_live_registry_targets_drive_free_lane_queue_alert(tmp_path: Path) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    ticks = monitor._process_start_ticks(os.getpid())
    assert ticks is not None
    (registry / "queue.json").write_text(
        json.dumps(
            {
                "acquired_at_utc": "2026-09-01T22:53:46Z",
                "lane": "nfl2-lab-jobs",
                "owner": "production",
                "pid": os.getpid(),
                "process_start_ticks": ticks,
                "schema_version": "shared-launcher-registry/v1",
                "script_path": "/absolute/queue.sh",
                "target_run_id_prefixes": ["083b580r1", "083b581r1", "083b582r1"],
            }
        ),
        encoding="utf-8",
    )
    first = _execution("lab-run-a", "lab-run", "active", run_id="083b580r1-x")
    second = _execution(
        "lab-run-slow-a", "lab-run-slow", "active", run_id="083b581r1-x"
    )
    second_done = _execution(
        "lab-run-slow-a", "lab-run-slow", "success", run_id="083b581r1-x"
    )
    fake = FakeGcloud(
        [[first], [second], [first], [second_done], [first], [second_done]]
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
        queue_grace_seconds=60,
    )
    lines: list[str] = []
    monitor.run_once(config, runner=fake, clock=FakeClock(10), emit=lines.append)
    assert monitor.load_status(config.state_file)["authorized_queue"]["state"] == "live"

    lines.clear()
    monitor.run_once(config, runner=fake, clock=FakeClock(20), emit=lines.append)
    assert not any(item["event"] == "alert_raised" for item in _events(lines))

    lines.clear()
    status = monitor.run_once(
        config, runner=fake, clock=FakeClock(81), emit=lines.append
    )
    key = "lane-capacity-unclaimed:083b582r1"
    assert key in status["alerts"]
    assert any(
        item["event"] == "alert_raised" and item.get("key") == key
        for item in _events(lines)
    )


def test_alerts_are_durable_and_delivered_without_a_shell(tmp_path: Path) -> None:
    failed = _execution("lab-run-a1", "lab-run", "failed")
    fake = FakeGcloud([[failed], []])
    notifier = FakeNotifier()
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        events_file=tmp_path / "events.jsonl",
        attention_file=tmp_path / "attention.json",
        windows_toast_command="powershell.exe",
    )

    status = monitor.run_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=FakeClock(70),
        emit=lambda _: None,
    )

    assert status["notification"]["pending_events"] == []
    assert status["notification"]["last_success_at"] == "1970-01-01T00:01:10Z"
    assert len(notifier.calls) == 1
    args, kwargs = notifier.calls[0]
    assert args[:3] == ["powershell.exe", "-NoProfile", "-NonInteractive"]
    assert "shell" not in kwargs
    assert kwargs["timeout"] == 10.0
    assert "lab-run-a1" in kwargs["env"]["NFL_MONITOR_BODY"]
    ledger = _events(config.events_file.read_text(encoding="utf-8").splitlines())
    assert {item["event"] for item in ledger} >= {
        "monitor_started",
        "alert_raised",
        "notification_delivered",
    }
    attention = json.loads(config.attention_file.read_text(encoding="utf-8"))
    assert attention["needs_attention"] is True
    assert "execution-failure:lab-run:lab-run-a1" in attention["entries"]
    assert stat.S_IMODE(config.events_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(config.attention_file.stat().st_mode) == 0o600


def test_notification_failure_never_loses_status_or_pending_alert(
    tmp_path: Path,
) -> None:
    failed = _execution("lab-run-a1", "lab-run", "failed")
    fake = FakeGcloud([[failed], []])
    notifier = FakeNotifier(returncode=1, stderr="toast unavailable")
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        events_file=tmp_path / "events.jsonl",
        attention_file=tmp_path / "attention.json",
        windows_toast_command="powershell.exe",
    )

    status = monitor.run_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=FakeClock(70),
        emit=lambda _: None,
    )

    assert config.state_file.exists()
    assert status["notification"]["pending_events"]
    assert status["notification"]["last_error"] == "toast unavailable"
    ledger = _events(config.events_file.read_text(encoding="utf-8").splitlines())
    assert ledger[-1]["event"] == "notification_delivery_failed"


def test_tracked_user_unit_is_persistent_and_uses_durable_alert_outputs() -> None:
    unit = (
        Path(__file__).resolve().parents[1]
        / "deploy/systemd/nfl-cloud-run-lane-monitor.service"
    ).read_text(encoding="utf-8")

    assert "Restart=always" in unit
    assert "WantedBy=default.target" in unit
    assert "%h/.local/state/nfl-dfs/cloud-run-lane-monitor/status.json" in unit
    assert "%h/.local/state/nfl-dfs/cloud-run-lane-monitor/events.jsonl" in unit
    assert "%h/.local/state/nfl-dfs/cloud-run-lane-monitor/attention.json" in unit
    assert "--launcher-registry-dir %h/projects/nfl2/.tmp/launchers" in unit
    assert "--windows-toast-command" in unit
