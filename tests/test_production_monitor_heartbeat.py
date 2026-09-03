from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts import production_monitor_heartbeat as heartbeat


class FakeRunner:
    def __init__(self, active: str = "active") -> None:
        self.active = active
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if "is-active" in args:
            return subprocess.CompletedProcess(args, 0, stdout=f"{self.active}\n", stderr="")
        if "restart" in args:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        raise AssertionError(args)


def _config(tmp_path: Path, state_file: Path) -> heartbeat.Config:
    return heartbeat.Config(
        targets=(heartbeat.Target("example.service", state_file, 300.0),),
        status_file=tmp_path / "heartbeat.json",
        events_file=tmp_path / "events.jsonl",
    )


def test_healthy_monitor_is_not_restarted(tmp_path: Path) -> None:
    state = tmp_path / "monitor.json"
    state.write_text(
        json.dumps({"observed_at_epoch": 900.0, "poll": {"ok": True}}),
        encoding="utf-8",
    )
    runner = FakeRunner()
    result = heartbeat.run_once(
        _config(tmp_path, state),
        runner=runner,
        clock=lambda: 1000.0,
        emit=lambda _: None,
    )
    assert result["healthy"] is True
    assert not any("restart" in call for call in runner.calls)


def test_stale_monitor_is_restarted_and_recorded(tmp_path: Path) -> None:
    state = tmp_path / "monitor.json"
    state.write_text(
        json.dumps({"observed_at_epoch": 1.0, "poll": {"ok": True}}),
        encoding="utf-8",
    )
    runner = FakeRunner()
    result = heartbeat.run_once(
        _config(tmp_path, state),
        runner=runner,
        clock=lambda: 1000.0,
        emit=lambda _: None,
    )
    assert result["targets"][0]["restarted"] is True
    assert any("restart" in call for call in runner.calls)
    events = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert events[-1]["event"] == "monitor_restarted"
