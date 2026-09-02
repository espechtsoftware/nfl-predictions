from __future__ import annotations

import json
import stat
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from scripts import cloud_build_monitor as monitor


@dataclass(frozen=True)
class FailedCall:
    stderr: str = "simulated provider failure"
    returncode: int = 1


class FakeGcloud:
    def __init__(self, responses: list[object]) -> None:
        self._responses: Iterator[object] = iter(responses)
        self.calls: list[list[str]] = []

    def __call__(
        self, args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
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
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(
        self, args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(args), dict(kwargs)))
        return subprocess.CompletedProcess(
            args, self.returncode, stdout="", stderr="toast failed"
        )


def _build(
    build_id: str,
    status: str,
    *,
    create_time: str = "1970-01-01T00:01:40Z",
    start_time: str | None = "1970-01-01T00:01:50Z",
    finish_time: str | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "id": build_id,
        "status": status,
        "createTime": create_time,
        "logUrl": f"https://example.invalid/{build_id}",
    }
    if start_time is not None:
        value["startTime"] = start_time
    if finish_time is not None:
        value["finishTime"] = finish_time
    return value


def _event_records(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_cli_defaults_query_both_projects_read_only_and_expose_working(
    tmp_path: Path, monkeypatch
) -> None:
    lab = _build("lab-build-exact", "WORKING")
    production = _build("production-build-exact", "QUEUED", start_time=None)
    fake = FakeGcloud([[lab], [lab], [production], [production]])
    monkeypatch.setattr(monitor.subprocess, "run", fake)
    monkeypatch.setattr(monitor.time, "time", FakeClock(120.0))
    state_file = tmp_path / "state" / "status.json"

    assert monitor.main(["--once", "--state-file", str(state_file)]) == 0

    status = json.loads(state_file.read_text(encoding="utf-8"))
    assert status["monitor"]["projects"] == list(monitor.DEFAULT_PROJECTS)
    assert status["projects"]["nfl-2-506823"]["working_build_ids"] == [
        "lab-build-exact"
    ]
    assert status["projects"]["nfl-predictions-503414"][
        "working_build_ids"
    ] == []
    assert status["projects"]["nfl-predictions-503414"][
        "pending_build_ids"
    ] == ["production-build-exact"]
    assert status["projects"]["nfl-predictions-503414"][
        "active_build_ids"
    ] == ["production-build-exact"]
    assert sorted(status["builds"]) == [
        "nfl-2-506823:lab-build-exact",
        "nfl-predictions-503414:production-build-exact",
    ]
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600
    assert len(fake.calls) == 4
    assert [call[call.index("--project") + 1] for call in fake.calls] == [
        "nfl-2-506823",
        "nfl-2-506823",
        "nfl-predictions-503414",
        "nfl-predictions-503414",
    ]
    assert ["--ongoing" in call for call in fake.calls] == [True, False, True, False]
    assert all(call[:3] == ["gcloud", "builds", "list"] for call in fake.calls)
    assert all(
        not ({"submit", "cancel", "delete", "update"} & set(call))
        for call in fake.calls
    )


def test_working_to_success_persists_exact_transition_and_notifies_once(
    tmp_path: Path,
) -> None:
    working = _build("084-image-build", "WORKING")
    success = _build(
        "084-image-build",
        "SUCCESS",
        finish_time="1970-01-01T00:03:20Z",
    )
    fake = FakeGcloud(
        [[working], [working], [], [success], [], [success]]
    )
    notifier = FakeNotifier()
    events_file = tmp_path / "events.jsonl"
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        events_file=events_file,
        projects=("nfl-2-506823",),
        windows_toast_command="toast.exe",
    )

    monitor.poll_once(config, runner=fake, notifier=notifier, clock=FakeClock(120.0))
    monitor.poll_once(config, runner=fake, notifier=notifier, clock=FakeClock(210.0))
    monitor.poll_once(config, runner=fake, notifier=notifier, clock=FakeClock(220.0))

    records = _event_records(events_file)
    transitions = [
        record for record in records if record["event"] == "build_status_transition"
    ]
    terminals = [record for record in records if record["event"] == "build_terminal"]
    assert transitions == [
        {
            "after": "SUCCESS",
            "at": "1970-01-01T00:03:30Z",
            "before": "WORKING",
            "build_id": "084-image-build",
            "event": "build_status_transition",
            "finish_time": "1970-01-01T00:03:20Z",
            "project": "nfl-2-506823",
            "schema_version": monitor.EVENT_SCHEMA,
            "start_time": "1970-01-01T00:01:50Z",
        }
    ]
    assert len(terminals) == 1
    assert terminals[0]["status"] == "SUCCESS"
    assert terminals[0]["bootstrap"] is False
    assert len(notifier.calls) == 1
    environment = notifier.calls[0][1]["env"]
    assert isinstance(environment, dict)
    assert environment["NFL_MONITOR_TITLE"] == "NFL Cloud Build completed"
    assert "084-image-b" in environment["NFL_MONITOR_BODY"]
    current = monitor.load_status(config.state_file)
    assert current is not None
    item = current["builds"]["nfl-2-506823:084-image-build"]
    assert item["status"] == "SUCCESS"
    assert item["provider_observation_stale"] is False


@pytest.mark.parametrize(
    ("provider_status", "outcome"),
    [
        ("SUCCESS", "success"),
        ("FAILURE", "failure"),
        ("CANCELLED", "cancelled"),
        ("TIMEOUT", "timeout"),
    ],
)
def test_recent_terminal_bootstrap_alert_covers_required_statuses(
    tmp_path: Path, provider_status: str, outcome: str
) -> None:
    terminal = _build(
        f"build-{provider_status.lower()}",
        provider_status,
        finish_time="1970-01-01T00:03:10Z",
    )
    fake = FakeGcloud([[], [terminal]])
    lines: list[str] = []
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        events_file=tmp_path / "events.jsonl",
        projects=("nfl-2-506823",),
    )

    monitor.poll_once(
        config,
        runner=fake,
        clock=FakeClock(200.0),
        emit=lines.append,
    )

    events = [json.loads(line) for line in lines]
    terminal_events = [event for event in events if event["event"] == "build_terminal"]
    assert len(terminal_events) == 1
    assert terminal_events[0]["status"] == provider_status
    assert terminal_events[0]["outcome"] == outcome
    assert terminal_events[0]["bootstrap"] is True


def test_query_failure_retains_exact_working_build_as_stale_then_recovers(
    tmp_path: Path,
) -> None:
    working = _build("exact-retained-id", "WORKING")
    fake = FakeGcloud(
        [
            [working],
            [working],
            FailedCall("ongoing unavailable"),
            FailedCall("recent unavailable"),
            [working],
            [working],
        ]
    )
    events_file = tmp_path / "events.jsonl"
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        events_file=events_file,
        projects=("nfl-2-506823",),
        stale_working_seconds=1_000,
    )

    monitor.poll_once(config, runner=fake, clock=FakeClock(120.0))
    failed = monitor.poll_once(config, runner=fake, clock=FakeClock(130.0))

    key = "nfl-2-506823:exact-retained-id"
    assert failed["projects"]["nfl-2-506823"]["query_state"] == "error"
    assert failed["projects"]["nfl-2-506823"]["stale_working_build_ids"] == [
        "exact-retained-id"
    ]
    assert failed["builds"][key]["provider_observation_stale"] is True
    assert set(failed["alerts"]) == {
        "provider-query:nfl-2-506823:ongoing",
        "provider-query:nfl-2-506823:recent",
        "working-stale:nfl-2-506823:exact-retained-id",
    }

    recovered = monitor.poll_once(config, runner=fake, clock=FakeClock(140.0))
    assert recovered["projects"]["nfl-2-506823"]["query_state"] == "ok"
    assert recovered["projects"]["nfl-2-506823"]["stale_working_build_ids"] == []
    assert recovered["builds"][key]["provider_observation_stale"] is False
    records = _event_records(events_file)
    cleared = {
        record["key"] for record in records if record["event"] == "alert_cleared"
    }
    assert cleared == {
        "provider-query:nfl-2-506823:ongoing",
        "provider-query:nfl-2-506823:recent",
        "working-stale:nfl-2-506823:exact-retained-id",
    }


def test_long_working_build_is_exposed_as_stale_without_repeated_alert_updates(
    tmp_path: Path,
) -> None:
    working = _build(
        "hung-build",
        "WORKING",
        create_time="1970-01-01T00:00:10Z",
        start_time="1970-01-01T00:00:20Z",
    )
    fake = FakeGcloud([[working], [working], [working], [working]])
    events_file = tmp_path / "events.jsonl"
    config = monitor.Config(
        state_file=tmp_path / "status.json",
        events_file=events_file,
        projects=("nfl-predictions-503414",),
        stale_working_seconds=60,
    )

    first = monitor.poll_once(config, runner=fake, clock=FakeClock(100.0))
    second = monitor.poll_once(config, runner=fake, clock=FakeClock(110.0))

    project = first["projects"]["nfl-predictions-503414"]
    assert project["working_build_ids"] == ["hung-build"]
    assert project["stale_working_build_ids"] == ["hung-build"]
    assert second["projects"]["nfl-predictions-503414"][
        "stale_working_build_ids"
    ] == ["hung-build"]
    records = _event_records(events_file)
    relevant = [
        record
        for record in records
        if record.get("key")
        == "working-stale:nfl-predictions-503414:hung-build"
    ]
    assert [record["event"] for record in relevant] == ["alert_raised"]


def test_systemd_unit_is_durable_read_only_and_covers_both_projects() -> None:
    unit = (
        Path(__file__).parents[1]
        / "deploy/systemd/nfl-cloud-build-monitor.service"
    ).read_text(encoding="utf-8")

    assert "Restart=always" in unit
    assert "--project nfl-2-506823" in unit
    assert "--project nfl-predictions-503414" in unit
    assert "%h/.local/state/nfl-dfs/cloud-build-monitor/status.json" in unit
    assert "%h/.local/state/nfl-dfs/cloud-build-monitor/events.jsonl" in unit
    assert "-m scripts.cloud_build_monitor" in unit
    assert not ({"submit", "cancel", "delete", "update"} & set(unit.split()))
