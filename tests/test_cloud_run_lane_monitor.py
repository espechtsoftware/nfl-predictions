from __future__ import annotations

import json
import hashlib
import os
import stat
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

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


def _write_registry_receipt(
    registry: Path,
    prefixes: list[str],
    *,
    name: str = "queue.json",
    acquired_at: str = "2026-09-01T22:53:46Z",
    start_tick_offset: int = 0,
) -> Path:
    ticks = monitor._process_start_ticks(os.getpid())
    assert ticks is not None
    path = registry / name
    path.write_text(
        json.dumps(
            {
                "acquired_at_utc": acquired_at,
                "lane": "nfl2-lab-jobs",
                "owner": "production",
                "pid": os.getpid(),
                "process_start_ticks": ticks + start_tick_offset,
                "schema_version": "shared-launcher-registry/v1",
                "script_path": "/absolute/queue.sh",
                "target_run_id_prefixes": prefixes,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_completion(receipt_path: Path, exit_status: int) -> Path:
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    receipt_sha256 = hashlib.sha256(raw).hexdigest()
    directory = receipt_path.parent.parent / "launcher-completions"
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / f"{receipt_sha256}.json"
    path.write_text(
        json.dumps(
            {
                "acquired_at_utc": receipt["acquired_at_utc"],
                "completed_at_utc": "2026-09-01T23:53:46Z",
                "exit_status": exit_status,
                "lane": receipt["lane"],
                "owner": receipt["owner"],
                "pid": receipt["pid"],
                "process_start_ticks": receipt["process_start_ticks"],
                "receipt_sha256": receipt_sha256,
                "schema_version": "shared-launcher-completion/v1",
                "script_path": receipt["script_path"],
                "target_run_id_prefixes": receipt["target_run_id_prefixes"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def test_cli_defaults_are_read_only_and_optional_e4_is_exact(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    prefix = "083-confirm"
    e4_name = "atlas-cbc-32g-full-2023-w8-v1-7zpd4"
    fake = FakeGcloud(
        [
            [_execution("lab-run-a1", "lab-run", "active", run_id=f"{prefix}-001")],
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


def test_prefix_matching_uses_only_exact_run_id_environment(tmp_path: Path) -> None:
    prefix = "084m590r2"
    row = _execution(
        f"name-{prefix}", "lab-run", "success", run_id=None
    )
    row["metadata"]["annotations"] = {"note": f"mentions {prefix}-run"}
    row["spec"]["template"]["spec"]["containers"][0]["args"] = [
        f"x{prefix}-run"
    ]
    exact_without_separator = _execution(
        "exact-without-separator", "lab-run", "success", run_id=prefix
    )
    embedded = _execution(
        "embedded-prefix", "lab-run", "success", run_id=f"x{prefix}-run"
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json", expected_prefixes=(prefix,)
    )

    status = monitor.run_once(
        config,
        runner=FakeGcloud([[row, exact_without_separator, embedded], []]),
        clock=FakeClock(10),
        emit=lambda _: None,
    )

    assert status["expected_prefixes"][prefix]["state"] == "unclaimed"
    assert status["cohort"]["provider_state"] == "waiting"


def test_distinct_trailing_delimiter_prefixes_cannot_collapse() -> None:
    row = _execution("lab-run-a", "lab-run", "success", run_id="foo-bar")

    summary = monitor._summary(row, "lab-run", ("foo", "foo-"))

    assert summary["matched_expected_prefixes"] == ["foo"]


def test_duplicate_or_malformed_run_id_fails_provider_evidence(tmp_path: Path) -> None:
    prefix = "084m590r2"
    row = _execution("lab-run-a", "lab-run", "success", run_id=f"{prefix}-run")
    env = row["spec"]["template"]["spec"]["containers"][0]["env"]
    env.append({"name": "RUN_ID", "value": f"{prefix}-other"})
    config = monitor.Config(
        state_file=tmp_path / "status.json", expected_prefixes=(prefix,)
    )

    status = monitor.run_once(
        config,
        runner=FakeGcloud([[row], []]),
        clock=FakeClock(10),
        emit=lambda _: None,
    )

    assert status["queries"]["lab-run"]["ok"] is False
    assert "duplicate RUN_ID" in status["queries"]["lab-run"]["error"]
    assert status["alerts"]["provider-query:lab-run"]["severity"] == "error"


@pytest.mark.parametrize("second_state", ("success", "active", "failed"))
def test_duplicate_provider_claim_for_prefix_is_failed_and_latched(
    tmp_path: Path, second_state: str,
) -> None:
    prefix = "084m590r2"
    first = _execution("lab-run-a", "lab-run", "success", run_id=f"{prefix}-one")
    second = _execution(
        "lab-run-slow-b", "lab-run-slow", second_state, run_id=f"{prefix}-two"
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        attention_file=tmp_path / "attention.json",
        expected_prefixes=(prefix,),
    )

    status = monitor.run_once(
        config,
        runner=FakeGcloud([[first], [second]]),
        clock=FakeClock(10),
        emit=lambda _: None,
    )

    alert_key = f"duplicate-prefix-claim:{prefix}"
    assert status["expected_prefixes"][prefix]["state"] == "duplicate"
    assert status["cohort"]["provider_state"] == "failed"
    assert status["cohort"]["state"] == "failed"
    assert status["alerts"][alert_key]["execution_names"] == [
        "lab-run-a", "lab-run-slow-b"
    ]
    attention = monitor.load_attention(config.attention_file)
    assert attention is not None
    assert attention["entries"][alert_key]["state"] == "active"


def test_registered_coordinator_failure_overrides_provider_acceptance_only(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    receipt = _write_registry_receipt(registry, ["084m590r2"])
    active = _execution(
        "lab-run-mechanics",
        "lab-run",
        "active",
        run_id="084m590r2-20260902T030000Z",
    )
    succeeded = _execution(
        "lab-run-mechanics",
        "lab-run",
        "success",
        run_id="084m590r2-20260902T030000Z",
    )
    unrelated = _execution(
        "lab-run-newer",
        "lab-run",
        "success",
        run_id="unrelated-20260902T040000Z",
        created_at="1970-01-01T00:02:00Z",
    )
    fake = FakeGcloud(
        [
            [active],
            [],
            [succeeded, unrelated],
            [],
        ]
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )
    lines: list[str] = []
    first = monitor.run_once(
        config, runner=fake, clock=FakeClock(20), emit=lines.append
    )
    assert first["registered_coordinator"]["state"] == "running"
    assert first["cohort"]["state"] == "running"
    completion = _write_completion(receipt, 1)
    receipt.unlink()

    lines.clear()
    second = monitor.run_once(
        config, runner=fake, clock=FakeClock(70), emit=lines.append
    )

    registration_key = completion.stem
    alert_key = f"registered-coordinator-failure:{registration_key}"
    assert second["cohort"] == {
        "state": "failed",
        "provider_state": "succeeded",
        "acceptance_state": "failed",
    }
    assert second["registered_coordinator"]["source"] == "terminal_launcher_record"
    assert second["registered_coordinator"]["exit_status"] == 1
    assert second["alerts"][alert_key]["prefixes"] == ["084m590r2"]
    assert "unrelated" not in json.dumps(second["alerts"][alert_key])
    assert any(
        event["event"] == "alert_raised" and event.get("key") == alert_key
        for event in _events(lines)
    )
    assert all(
        not ({"start", "stop", "restart", "reset-failed"} & set(call))
        for call in fake.calls
    )


def test_provider_success_without_coordinator_acceptance_alerts_after_grace(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    receipt = _write_registry_receipt(registry, ["084m590r2"])
    succeeded = _execution(
        "lab-run-mechanics",
        "lab-run",
        "success",
        run_id="084m590r2-20260902T030000Z",
    )
    fake = FakeGcloud(
        [
            [succeeded],
            [],
            [succeeded],
            [],
        ]
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
        coordinator_post_provider_grace_seconds=180,
    )
    first = monitor.run_once(
        config, runner=fake, clock=FakeClock(10), emit=lambda _: None
    )
    assert first["cohort"]["acceptance_state"] == "post_provider_pending"
    assert not any(
        key.startswith("registered-coordinator-post-provider:")
        for key in first["alerts"]
    )
    receipt.unlink()

    second = monitor.run_once(
        config, runner=fake, clock=FakeClock(191), emit=lambda _: None
    )
    key = (
        "registered-coordinator-post-provider:"
        f"{first['registered_coordinator']['registration_key']}"
    )
    assert second["registered_coordinator"]["post_provider_seconds"] == 181
    assert second["alerts"][key]["kind"] == (
        "registered_coordinator_post_provider_pending"
    )
    assert second["alerts"][key]["severity"] == "error"


def test_zero_exit_terminal_record_confirms_acceptance(tmp_path: Path) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    receipt = _write_registry_receipt(registry, ["084m590r2"])
    succeeded = _execution(
        "lab-run-mechanics",
        "lab-run",
        "success",
        run_id="084m590r2-20260902T030000Z",
    )
    fake = FakeGcloud([[succeeded], [], [succeeded], []])
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )
    first = monitor.run_once(
        config, runner=fake, clock=FakeClock(10), emit=lambda _: None
    )
    assert first["cohort"]["acceptance_state"] == "post_provider_pending"
    completion = _write_completion(receipt, 0)
    receipt.unlink()

    second = monitor.run_once(
        config, runner=fake, clock=FakeClock(70), emit=lambda _: None
    )

    assert second["cohort"]["acceptance_state"] == "succeeded"
    assert second["registered_coordinator"]["exit_status"] == 0
    assert second["registered_coordinator"]["completion_path"] == str(completion)
    assert not any(
        key.startswith("registered-coordinator-") for key in second["alerts"]
    )


def test_live_receipt_with_published_completion_is_valid_terminalizing_state(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    receipt = _write_registry_receipt(registry, ["084m590r2"])
    completion = _write_completion(receipt, 0)
    succeeded = _execution(
        "lab-run-mechanics", "lab-run", "success", run_id="084m590r2-run"
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )

    status = monitor.run_once(
        config,
        runner=FakeGcloud([[succeeded], []]),
        clock=FakeClock(70),
        emit=lambda _: None,
    )

    assert status["authorized_queue"]["state"] == "terminalizing"
    assert status["registered_coordinator"]["registration_key"] == completion.stem
    assert status["registered_coordinator"]["state"] == "succeeded"
    assert status["cohort"]["state"] == "succeeded"
    assert "launcher-registry" not in status["alerts"]


def test_provider_success_pending_acceptance_notifies_once_then_acceptance_notifies(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    receipt = _write_registry_receipt(registry, ["084m590r2"])
    active = _execution(
        "lab-run-mechanics", "lab-run", "active", run_id="084m590r2-run"
    )
    succeeded = _execution(
        "lab-run-mechanics", "lab-run", "success", run_id="084m590r2-run"
    )
    fake = FakeGcloud([[active], [], [succeeded], [], [succeeded], []])
    notifier = FakeNotifier()
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
        windows_toast_command="powershell.exe",
    )
    monitor.run_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=FakeClock(10),
        emit=lambda _: None,
    )
    lines: list[str] = []
    pending = monitor.run_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=FakeClock(20),
        emit=lines.append,
    )
    assert pending["cohort"]["provider_state"] == "succeeded"
    assert pending["cohort"]["state"] == "pending_acceptance"
    assert len(notifier.calls) == 1
    assert notifier.calls[0][1]["env"]["NFL_MONITOR_TITLE"] == (
        "NFL cloud results await acceptance"
    )
    assert not any(
        event["event"] == "cohort_transition" and event.get("after") == "succeeded"
        for event in _events(lines)
    )
    assert any(
        event["event"] == "provider_cohort_completed_without_acceptance"
        for event in _events(lines)
    )

    _write_completion(receipt, 0)
    receipt.unlink()
    accepted = monitor.run_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=FakeClock(30),
        emit=lambda _: None,
    )
    assert accepted["cohort"]["state"] == "succeeded"
    assert len(notifier.calls) == 2
    assert notifier.calls[1][1]["env"]["NFL_MONITOR_TITLE"] == (
        "NFL cloud cohort completed"
    )


def test_terminal_failure_is_recovered_after_monitor_restart(tmp_path: Path) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    receipt = _write_registry_receipt(registry, ["084m590r2"])
    completion = _write_completion(receipt, 1)
    receipt.unlink()
    succeeded = _execution(
        "lab-run-mechanics",
        "lab-run",
        "success",
        run_id="084m590r2-20260902T030000Z",
    )
    fake = FakeGcloud([[succeeded], []])
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )

    status = monitor.run_once(
        config, runner=fake, clock=FakeClock(70), emit=lambda _: None
    )

    key = f"registered-coordinator-failure:{completion.stem}"
    assert status["authorized_queue"]["source"] == "terminal_launcher_record"
    assert status["cohort"]["acceptance_state"] == "failed"
    assert status["alerts"][key]["exit_status"] == 1


def test_exact_receipt_failure_cannot_be_hidden_by_later_same_prefix_success(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    first_receipt = _write_registry_receipt(registry, ["084m590r2"])
    active = _execution(
        "lab-run-mechanics", "lab-run", "active", run_id="084m590r2-run"
    )
    succeeded = _execution(
        "lab-run-mechanics", "lab-run", "success", run_id="084m590r2-run"
    )
    fake = FakeGcloud([[active], [], [succeeded], []])
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )
    first = monitor.run_once(
        config, runner=fake, clock=FakeClock(10), emit=lambda _: None
    )
    first_key = first["registered_coordinator"]["registration_key"]
    _write_completion(first_receipt, 1)
    first_receipt.unlink()
    second_receipt = _write_registry_receipt(
        registry,
        ["084m590r2"],
        name="later.json",
        acquired_at="2026-09-01T23:00:00Z",
    )
    second_completion = _write_completion(second_receipt, 0)
    second_receipt.unlink()

    second = monitor.run_once(
        config, runner=fake, clock=FakeClock(70), emit=lambda _: None
    )

    assert second["registered_coordinator"]["registration_key"] == first_key
    assert second["registered_coordinator"]["exit_status"] == 1
    assert second["registered_coordinator"]["completion_path"] != str(second_completion)
    assert second["cohort"]["state"] == "failed"
    assert first_key in second["blocking_completion_failure_keys"]


def test_unrelated_later_failure_alerts_without_poisoning_exact_success(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    tracked_receipt = _write_registry_receipt(registry, ["cohort-a"])
    active = _execution(
        "lab-run-a", "lab-run", "active", run_id="cohort-a-run"
    )
    succeeded = _execution(
        "lab-run-a", "lab-run", "success", run_id="cohort-a-run"
    )
    fake = FakeGcloud([[active], [], [succeeded], []])
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        attention_file=tmp_path / "attention.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )
    first = monitor.run_once(
        config, runner=fake, clock=FakeClock(10), emit=lambda _: None
    )
    tracked_key = first["registered_coordinator"]["registration_key"]
    _write_completion(tracked_receipt, 0)
    tracked_receipt.unlink()
    unrelated_receipt = _write_registry_receipt(
        registry,
        ["cohort-c"],
        name="unrelated.json",
        acquired_at="2026-09-01T23:53:00Z",
    )
    unrelated_completion = _write_completion(unrelated_receipt, 9)
    unrelated_receipt.unlink()
    lines: list[str] = []

    second = monitor.run_once(
        config, runner=fake, clock=FakeClock(70), emit=lines.append
    )

    unrelated_alert = (
        f"registered-coordinator-failure:{unrelated_completion.stem}"
    )
    assert second["registered_coordinator"]["registration_key"] == tracked_key
    assert second["registered_coordinator"]["exit_status"] == 0
    assert second["cohort"] == {
        "state": "succeeded",
        "provider_state": "succeeded",
        "acceptance_state": "succeeded",
    }
    assert second["blocking_completion_failure_keys"] == []
    assert unrelated_alert in second["alerts"]
    events = _events(lines)
    assert any(
        event["event"] == "registered_coordinator_accepted"
        and event["registration_key"] == tracked_key
        and event["effective_state"] == "succeeded"
        for event in events
    )
    assert any(
        event["event"] == "registered_coordinator_failed"
        and event["registration_key"] == unrelated_completion.stem
        for event in events
    )
    attention = monitor.load_attention(config.attention_file)
    assert attention is not None
    assert attention["entries"][unrelated_alert]["state"] == "active"


def test_terminal_coordinator_advances_when_replacement_finishes_between_polls(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    first_receipt = _write_registry_receipt(registry, ["cohort-a"])
    first_active = _execution(
        "lab-run-a", "lab-run", "active", run_id="cohort-a-run"
    )
    first_success = _execution(
        "lab-run-a", "lab-run", "success", run_id="cohort-a-run"
    )
    second_success = _execution(
        "lab-run-b", "lab-run", "success", run_id="cohort-b-run"
    )
    fake = FakeGcloud(
        [
            [first_active], [],
            [first_success], [],
            [second_success], [],
            [second_success], [],
        ]
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )
    first = monitor.run_once(
        config, runner=fake, clock=FakeClock(10), emit=lambda _: None
    )
    first_key = first["registered_coordinator"]["registration_key"]
    _write_completion(first_receipt, 0)
    first_receipt.unlink()
    second = monitor.run_once(
        config, runner=fake, clock=FakeClock(70), emit=lambda _: None
    )
    assert second["registered_coordinator"]["registration_key"] == first_key
    assert second["cohort"]["state"] == "succeeded"

    replacement_receipt = _write_registry_receipt(
        registry,
        ["cohort-b"],
        name="replacement.json",
        acquired_at="2026-09-01T22:53:46Z",
        start_tick_offset=1,
    )
    replacement_completion = _write_completion(replacement_receipt, 9)
    replacement_receipt.unlink()
    third = monitor.run_once(
        config, runner=fake, clock=FakeClock(130), emit=lambda _: None
    )

    replacement_key = replacement_completion.stem
    failure_alert = f"registered-coordinator-failure:{replacement_key}"
    assert third["authorized_queue"]["prefixes"] == ["cohort-b"]
    assert third["registered_coordinator"]["registration_key"] == replacement_key
    assert third["registered_coordinator"]["exit_status"] == 9
    assert third["cohort"]["state"] == "failed"
    assert third["blocking_completion_failure_keys"] == [replacement_key]
    assert failure_alert in third["alerts"]

    fourth = monitor.run_once(
        config, runner=fake, clock=FakeClock(190), emit=lambda _: None
    )
    assert fourth["registered_coordinator"]["registration_key"] == replacement_key
    assert fourth["cohort"]["state"] == "failed"
    assert fourth["blocking_completion_failure_keys"] == [replacement_key]
    assert failure_alert in fourth["alerts"]


def test_cold_start_success_notifies_once_after_exact_acceptance(tmp_path: Path) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    receipt = _write_registry_receipt(registry, ["084m590r2"])
    completion = _write_completion(receipt, 0)
    receipt.unlink()
    succeeded = _execution(
        "lab-run-mechanics", "lab-run", "success", run_id="084m590r2-run"
    )
    fake = FakeGcloud([[succeeded], [], [succeeded], []])
    notifier = FakeNotifier()
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        events_file=tmp_path / "events.jsonl",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
        windows_toast_command="powershell.exe",
    )
    lines: list[str] = []

    first = monitor.run_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=FakeClock(70),
        emit=lines.append,
    )

    assert first["cohort"]["state"] == "succeeded"
    assert first["new_completion_keys"] == [completion.stem]
    assert any(
        event["event"] == "registered_coordinator_accepted"
        and event["recovered"] is True
        for event in _events(lines)
    )
    assert len(notifier.calls) == 1
    assert notifier.calls[0][1]["env"]["NFL_MONITOR_TITLE"] == (
        "NFL cloud cohort completed"
    )

    lines.clear()
    monitor.run_once(
        config,
        runner=fake,
        notifier=notifier,
        clock=FakeClock(130),
        emit=lines.append,
    )
    assert len(notifier.calls) == 1
    assert not any(
        event["event"] == "registered_coordinator_accepted"
        for event in _events(lines)
    )

    third_fake = FakeGcloud([[succeeded], []])
    third = monitor.run_once(
        config,
        runner=third_fake,
        notifier=notifier,
        clock=FakeClock(190),
        emit=lambda _: None,
    )
    assert third["registered_coordinator"]["state"] == "succeeded"
    assert third["registered_coordinator"]["registration_key"] == completion.stem
    assert third["cohort"]["state"] == "succeeded"
    assert len(notifier.calls) == 1


def test_cold_start_latest_success_is_not_poisoned_by_historical_failure(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    old_receipt = _write_registry_receipt(registry, ["old"])
    old_completion = _write_completion(old_receipt, 1)
    old_receipt.unlink()
    latest_receipt = _write_registry_receipt(
        registry,
        ["current"],
        name="latest.json",
        acquired_at="2026-09-01T23:53:00Z",
    )
    latest_completion = _write_completion(latest_receipt, 0)
    latest_receipt.unlink()
    succeeded = _execution(
        "lab-run-current", "lab-run", "success", run_id="current-run"
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        attention_file=tmp_path / "attention.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )
    lines: list[str] = []

    status = monitor.run_once(
        config,
        runner=FakeGcloud([[succeeded], []]),
        clock=FakeClock(70),
        emit=lines.append,
    )

    failure_alert = f"registered-coordinator-failure:{old_completion.stem}"
    assert status["registered_coordinator"]["registration_key"] == (
        latest_completion.stem
    )
    assert status["cohort"]["state"] == "succeeded"
    assert status["blocking_completion_failure_keys"] == []
    assert failure_alert in status["alerts"]
    assert any(
        event["event"] == "registered_coordinator_accepted"
        and event["registration_key"] == latest_completion.stem
        and event["effective_state"] == "succeeded"
        for event in _events(lines)
    )
    attention = monitor.load_attention(config.attention_file)
    assert attention is not None
    assert attention["entries"][failure_alert]["state"] == "active"


def test_live_replacement_rearms_but_still_latches_observed_terminal_failure(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    old_receipt = _write_registry_receipt(registry, ["old"])
    old_completion = _write_completion(old_receipt, 1)
    old_receipt.unlink()
    replacement = _write_registry_receipt(
        registry,
        ["new"],
        name="replacement.json",
        acquired_at="2026-09-02T00:00:00Z",
    )
    active = _execution("lab-run-new", "lab-run", "active", run_id="new-run")
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )

    status = monitor.run_once(
        config,
        runner=FakeGcloud([[active], []]),
        clock=FakeClock(70),
        emit=lambda _: None,
    )

    assert status["registered_coordinator"]["registration_key"] != old_completion.stem
    assert status["registered_coordinator"]["registration_key"] == hashlib.sha256(
        replacement.read_bytes()
    ).hexdigest()
    assert status["registered_coordinator"]["state"] == "running"
    assert status["blocking_completion_failure_keys"] == []
    failure_key = f"registered-coordinator-failure:{old_completion.stem}"
    assert failure_key in status["alerts"]
    assert status["cohort"]["state"] == "running"


def test_historical_completion_mutation_alerts_without_poisoning_live_cohort(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    old_receipt = _write_registry_receipt(registry, ["old"])
    old_completion = _write_completion(old_receipt, 1)
    old_receipt.unlink()
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        attention_file=tmp_path / "attention.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )
    failed = _execution("lab-run-old", "lab-run", "failed", run_id="old-run")
    first = monitor.run_once(
        config,
        runner=FakeGcloud([[failed], []]),
        clock=FakeClock(10),
        emit=lambda _: None,
    )
    assert first["cohort"]["state"] == "failed"

    value = json.loads(old_completion.read_text(encoding="utf-8"))
    value["completed_at_utc"] = "2026-09-01T23:59:59Z"
    old_completion.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    old_completion.chmod(0o600)
    replacement = _write_registry_receipt(
        registry,
        ["new"],
        name="replacement.json",
        acquired_at="2026-09-01T23:53:00Z",
    )
    active = _execution("lab-run-new", "lab-run", "active", run_id="new-run")
    second = monitor.run_once(
        config,
        runner=FakeGcloud([[active], []]),
        clock=FakeClock(70),
        emit=lambda _: None,
    )

    replacement_key = hashlib.sha256(replacement.read_bytes()).hexdigest()
    changed_key = f"launcher-completion-changed:{old_completion.stem}"
    assert second["registered_coordinator"]["registration_key"] == replacement_key
    assert second["cohort"]["state"] == "running"
    assert second["blocking_completion_failure_keys"] == []
    assert second["changed_completion_keys"] == [old_completion.stem]
    assert changed_key in second["alerts"]
    attention = monitor.load_attention(config.attention_file)
    assert attention is not None
    assert attention["entries"][changed_key]["state"] == "active"


def test_current_completion_integrity_failure_stays_failed_until_rearm(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    receipt = _write_registry_receipt(registry, ["current"])
    completion = _write_completion(receipt, 0)
    receipt.unlink()
    succeeded = _execution(
        "lab-run-current", "lab-run", "success", run_id="current-run"
    )
    fake = FakeGcloud([[succeeded], [], [succeeded], [], [succeeded], []])
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )
    first = monitor.run_once(
        config, runner=fake, clock=FakeClock(10), emit=lambda _: None
    )
    assert first["cohort"]["state"] == "succeeded"

    value = json.loads(completion.read_text(encoding="utf-8"))
    value["completed_at_utc"] = "2026-09-01T23:59:59Z"
    completion.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    completion.chmod(0o600)
    second = monitor.run_once(
        config, runner=fake, clock=FakeClock(70), emit=lambda _: None
    )
    assert second["registered_coordinator"]["state"] == "failed"
    assert second["cohort"]["state"] == "failed"
    assert second["completion_integrity_failure_keys"] == [completion.stem]

    third = monitor.run_once(
        config, runner=fake, clock=FakeClock(130), emit=lambda _: None
    )
    alert_key = f"launcher-completion-changed:{completion.stem}"
    assert third["registered_coordinator"]["state"] == "failed"
    assert third["registered_coordinator"]["acceptance_state"] == "failed"
    assert third["cohort"]["state"] == "failed"
    assert third["completion_integrity_failure_keys"] == [completion.stem]
    assert alert_key in third["alerts"]
    coordinator_alert = third["alerts"][
        f"registered-coordinator-failure:{completion.stem}"
    ]
    assert coordinator_alert["exit_status"] == 0
    assert coordinator_alert["reason"] == (
        "registered completion evidence failed immutable-ledger integrity"
    )


def test_transient_invalid_registry_read_does_not_poison_completion_ledger(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    receipt = _write_registry_receipt(registry, ["current"])
    completion = _write_completion(receipt, 0)
    receipt.unlink()
    succeeded = _execution(
        "lab-run-current", "lab-run", "success", run_id="current-run"
    )
    fake = FakeGcloud(
        [[succeeded], [], [succeeded], [], [succeeded], []]
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        attention_file=tmp_path / "attention.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )

    first = monitor.run_once(
        config, runner=fake, clock=FakeClock(10), emit=lambda _: None
    )
    assert first["cohort"]["state"] == "succeeded"
    original_record_sha256 = first["launcher_completions"][completion.stem][
        "record_sha256"
    ]

    completion.chmod(0o644)
    invalid_lines: list[str] = []
    invalid = monitor.run_once(
        config, runner=fake, clock=FakeClock(70), emit=invalid_lines.append
    )
    assert invalid["authorized_queue"]["state"] == "error"
    assert invalid["registered_coordinator"]["acceptance_state"] == "unverifiable"
    assert invalid["changed_completion_keys"] == []
    assert invalid["new_completion_keys"] == []
    assert invalid["completion_integrity_failure_keys"] == []
    assert invalid["seen_completion_keys"] == [completion.stem]
    assert invalid["launcher_completions"][completion.stem][
        "record_sha256"
    ] == original_record_sha256
    assert "launcher-registry" in invalid["alerts"]

    completion.chmod(0o600)
    recovered_lines: list[str] = []
    recovered = monitor.run_once(
        config, runner=fake, clock=FakeClock(130), emit=recovered_lines.append
    )
    assert recovered["authorized_queue"]["state"] == "no_live_receipt"
    assert recovered["registered_coordinator"]["state"] == "succeeded"
    assert recovered["cohort"]["state"] == "succeeded"
    assert recovered["changed_completion_keys"] == []
    assert recovered["new_completion_keys"] == []
    assert recovered["completion_integrity_failure_keys"] == []
    assert not any(
        key.startswith("launcher-completion-") for key in recovered["alerts"]
    )
    assert not any(
        event["event"] == "registered_coordinator_accepted"
        for event in _events([*invalid_lines, *recovered_lines])
    )


def test_failure_between_polls_alerts_without_poisoning_live_replacement(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    first_receipt = _write_registry_receipt(registry, ["cohort-a"])
    first_active = _execution(
        "lab-run-a", "lab-run", "active", run_id="cohort-a-run"
    )
    second_active = _execution(
        "lab-run-b", "lab-run", "active", run_id="cohort-b-run"
    )
    fake = FakeGcloud([[first_active], [], [second_active], []])
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        attention_file=tmp_path / "attention.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )
    first = monitor.run_once(
        config, runner=fake, clock=FakeClock(10), emit=lambda _: None
    )
    first_key = first["registered_coordinator"]["registration_key"]

    completion = _write_completion(first_receipt, 1)
    first_receipt.unlink()
    replacement = _write_registry_receipt(
        registry,
        ["cohort-b"],
        name="replacement.json",
        acquired_at="2026-09-02T00:00:00Z",
    )
    lines: list[str] = []
    second = monitor.run_once(
        config, runner=fake, clock=FakeClock(70), emit=lines.append
    )

    replacement_key = hashlib.sha256(replacement.read_bytes()).hexdigest()
    alert_key = f"registered-coordinator-failure:{completion.stem}"
    assert completion.stem == first_key
    assert second["registered_coordinator"]["registration_key"] == replacement_key
    assert second["registered_coordinator"]["state"] == "running"
    assert second["cohort"]["state"] == "running"
    assert second["blocking_completion_failure_keys"] == []
    assert alert_key in second["alerts"]
    events = _events(lines)
    assert any(
        event["event"] == "registered_coordinator_failed"
        and event["registration_key"] == first_key
        for event in events
    )
    assert any(
        event["event"] == "alert_raised" and event.get("key") == alert_key
        for event in events
    )
    attention = monitor.load_attention(config.attention_file)
    assert attention is not None
    assert attention["entries"][alert_key]["state"] == "active"


def test_dead_receipt_without_completion_is_actionable_after_restart(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    receipt = _write_registry_receipt(registry, ["084m590r2"])
    value = json.loads(receipt.read_text(encoding="utf-8"))
    value["process_start_ticks"] += 1
    receipt.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    succeeded = _execution(
        "lab-run-mechanics", "lab-run", "success", run_id="084m590r2-run"
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )

    status = monitor.run_once(
        config,
        runner=FakeGcloud([[succeeded], []]),
        clock=FakeClock(70),
        emit=lambda _: None,
    )

    key = status["registered_coordinator"]["registration_key"]
    assert status["registered_coordinator"]["state"] == "orphaned"
    assert status["cohort"]["state"] == "failed"
    assert f"registered-coordinator-orphaned:{key}" in status["alerts"]


def test_dead_receipt_with_matching_completion_requires_cleanup(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    receipt = _write_registry_receipt(registry, ["084m590r2"])
    value = json.loads(receipt.read_text(encoding="utf-8"))
    value["process_start_ticks"] += 1
    receipt.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    completion = _write_completion(receipt, 0)
    succeeded = _execution(
        "lab-run-mechanics", "lab-run", "success", run_id="084m590r2-run"
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        attention_file=tmp_path / "attention.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )

    status = monitor.run_once(
        config,
        runner=FakeGcloud([[succeeded], []]),
        clock=FakeClock(70),
        emit=lambda _: None,
    )

    key = completion.stem
    alert_key = f"registered-coordinator-cleanup-required:{key}"
    assert status["authorized_queue"]["state"] == "terminalized_orphan"
    assert status["registered_coordinator"]["registration_key"] == key
    assert status["registered_coordinator"]["state"] == "succeeded"
    assert status["cohort"]["state"] == "succeeded"
    assert alert_key in status["alerts"]
    attention = monitor.load_attention(config.attention_file)
    assert attention is not None
    assert attention["entries"][alert_key]["state"] == "active"


def test_attention_reconciles_after_status_write_precedes_attention_crash(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "launchers"
    registry.mkdir()
    receipt = _write_registry_receipt(registry, ["current"])
    completion = _write_completion(receipt, 7)
    receipt.unlink()
    succeeded = _execution(
        "lab-run-current", "lab-run", "success", run_id="current-run"
    )
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        attention_file=tmp_path / "attention.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )
    # Model termination immediately after the durable status replacement.
    first = monitor.collect_status(
        config,
        None,
        now=10,
        runner=FakeGcloud([[succeeded], []]),
    )
    monitor.write_status_atomic(config.state_file, first)
    assert not config.attention_file.exists()

    second = monitor.run_once(
        config,
        runner=FakeGcloud([[succeeded], []]),
        clock=FakeClock(70),
        emit=lambda _: None,
    )

    alert_key = f"registered-coordinator-failure:{completion.stem}"
    assert alert_key in second["alerts"]
    attention = monitor.load_attention(config.attention_file)
    assert attention is not None
    assert attention["needs_attention"] is True
    assert attention["active_alert_keys"] == [alert_key]
    assert attention["entries"][alert_key]["state"] == "active"
    assert attention["entries"][alert_key]["acknowledged_at"] is None


def test_missing_configured_registry_and_tampered_completion_are_visible(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing" / "launchers"
    fake = FakeGcloud([[], []])
    config = monitor.Config(
        state_file=tmp_path / "missing-status.json",
        launcher_registry_dirs=(missing,),
        launcher_lane="nfl2-lab-jobs",
    )
    missing_status = monitor.run_once(
        config, runner=fake, clock=FakeClock(10), emit=lambda _: None
    )
    assert missing_status["alerts"]["launcher-registry"]["kind"] == (
        "launcher_registry_invalid"
    )
    assert str(missing) in missing_status["alerts"]["launcher-registry"]["error"]

    registry = tmp_path / "tampered" / "launchers"
    registry.mkdir(parents=True)
    receipt = _write_registry_receipt(registry, ["084m590r2"])
    completion = _write_completion(receipt, 0)
    receipt.unlink()
    record = json.loads(completion.read_text(encoding="utf-8"))
    record["target_run_id_prefixes"] = ["different-prefix"]
    completion.write_text(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    fake = FakeGcloud([[], []])
    config = monitor.Config(
        state_file=tmp_path / "tampered-status.json",
        launcher_registry_dirs=(registry,),
        launcher_lane="nfl2-lab-jobs",
    )
    tampered_status = monitor.run_once(
        config, runner=fake, clock=FakeClock(20), emit=lambda _: None
    )
    assert "does not reconstruct its bound receipt" in tampered_status["alerts"][
        "launcher-registry"
    ]["error"]


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


def test_notification_copy_distinguishes_failed_and_superseded_acceptance() -> None:
    failed = {
        "event": "provider_cohort_completed_without_acceptance",
        "effective_state": "failed",
        "registration_key": "receipt-a",
    }
    title, body = monitor._notification_text([failed])
    assert title == "NFL cloud results need adjudication"
    assert "was not obtained" in body

    accepted = {
        "event": "registered_coordinator_accepted",
        "effective_state": "succeeded",
        "registration_key": "receipt-a",
    }
    title, body = monitor._notification_text([failed, accepted])
    assert title == "NFL cloud cohort completed"
    assert "was not obtained" not in body
    assert "coordinator accepted provider results" in body

    other_accepted = {**accepted, "registration_key": "receipt-b"}
    title, body = monitor._notification_text([failed, other_accepted])
    assert title == "NFL cloud results need adjudication"
    assert "was not obtained" in body
    assert "coordinator accepted provider results" in body


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
    assert (
        "--launcher-registry-dir "
        "%h/.local/state/nfl-dfs/lab-launcher-registry/launchers"
    ) in unit
    assert "--coordinator-post-provider-grace-seconds 180" in unit
    assert "--windows-toast-command" in unit
