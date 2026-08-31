from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "scripts" / "launcher_registry.sh"


def _write_executable(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _argv(
    root: Path,
    *,
    lane: str,
    command: list[str],
    prefixes: str = "run-a,run-b",
) -> list[str]:
    return [
        str(REGISTRY),
        "run",
        "--root",
        str(root),
        "--lane",
        lane,
        "--owner",
        "production",
        "--target-prefixes",
        prefixes,
        "--",
        *command,
    ]


def _wait_for(path: Path, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for {path}")


def _wait_for_one_receipt(root: Path, *, timeout: float = 5.0) -> Path:
    directory = root / ".tmp" / "launchers"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        receipts = list(directory.glob("*")) if directory.is_dir() else []
        if len(receipts) == 1:
            return receipts[0]
        time.sleep(0.02)
    raise AssertionError("timed out waiting for exactly one launcher receipt")


def _holder_script(root: Path) -> Path:
    return _write_executable(
        root / "holder.sh",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'ready\\n' > "$1"
trap 'exit 0' INT TERM HUP
while :; do sleep 0.05; done
""",
    )


def _stop(process: subprocess.Popen[str]) -> int:
    if process.poll() is None:
        process.terminate()
    return process.wait(timeout=5)


def test_same_lane_refuses_live_owner_and_receipt_is_readable(tmp_path: Path) -> None:
    holder_script = _holder_script(tmp_path)
    ready = tmp_path / "ready"
    holder = subprocess.Popen(
        _argv(
            tmp_path,
            lane="cloud-run-job.shared",
            prefixes="e4-grade,e4-grade-reopen",
            command=[str(holder_script), str(ready)],
        ),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_for(ready)
        receipt_path = _wait_for_one_receipt(tmp_path)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt == {
            "acquired_at_utc": receipt["acquired_at_utc"],
            "lane": "cloud-run-job.shared",
            "owner": "production",
            "pid": holder.pid,
            "process_start_ticks": receipt["process_start_ticks"],
            "schema_version": "shared-launcher-registry/v1",
            "script_path": str(holder_script.resolve()),
            "target_run_id_prefixes": ["e4-grade", "e4-grade-reopen"],
        }
        assert receipt["process_start_ticks"] > 0

        refused = subprocess.run(
            _argv(
                tmp_path,
                lane="cloud-run-job.shared",
                command=["/usr/bin/true"],
            ),
            text=True,
            capture_output=True,
            check=False,
        )
        assert refused.returncode == 2
        assert "launcher lane is already owned: cloud-run-job.shared" in refused.stderr
        assert receipt_path.exists()
    finally:
        _stop(holder)
    assert list((tmp_path / ".tmp" / "launchers").iterdir()) == []


def test_same_lane_refuses_paused_owner(tmp_path: Path) -> None:
    holder_script = _holder_script(tmp_path)
    ready = tmp_path / "ready"
    holder = subprocess.Popen(
        _argv(
            tmp_path,
            lane="cloud-run-job.paused",
            command=[str(holder_script), str(ready)],
        ),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    paused = False
    try:
        _wait_for(ready)
        receipt = _wait_for_one_receipt(tmp_path)
        os.kill(holder.pid, signal.SIGSTOP)
        paused = True

        refused = subprocess.run(
            _argv(
                tmp_path,
                lane="cloud-run-job.paused",
                command=["/usr/bin/true"],
            ),
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        assert refused.returncode == 2
        assert "launcher lane is already owned: cloud-run-job.paused" in refused.stderr
        assert receipt.exists()
    finally:
        if paused and holder.poll() is None:
            os.kill(holder.pid, signal.SIGCONT)
        _stop(holder)
    assert list((tmp_path / ".tmp" / "launchers").iterdir()) == []


def test_distinct_lanes_can_coexist(tmp_path: Path) -> None:
    holder_script = _holder_script(tmp_path)
    ready = tmp_path / "ready"
    holder = subprocess.Popen(
        _argv(
            tmp_path,
            lane="cloud-run-job.alpha",
            command=[str(holder_script), str(ready)],
        ),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_for(ready)
        alpha_receipt = _wait_for_one_receipt(tmp_path)
        other = subprocess.run(
            _argv(
                tmp_path,
                lane="cloud-run-job.beta",
                command=["/usr/bin/true"],
            ),
            text=True,
            capture_output=True,
            check=False,
        )
        assert other.returncode == 0, other.stderr
        assert alpha_receipt.exists()
        assert json.loads(alpha_receipt.read_text(encoding="utf-8"))["lane"] == (
            "cloud-run-job.alpha"
        )
    finally:
        _stop(holder)


def test_provably_stale_same_lane_receipt_is_logged_and_removed(tmp_path: Path) -> None:
    registry_dir = tmp_path / ".tmp" / "launchers"
    registry_dir.mkdir(parents=True)
    stale = registry_dir / "stale-99999999.json"
    stale.write_text(
        json.dumps(
            {
                "acquired_at_utc": "2026-08-31T00:00:00Z",
                "lane": "cloud-run-job.stale",
                "owner": "production",
                "pid": 99_999_999,
                "process_start_ticks": 1,
                "schema_version": "shared-launcher-registry/v1",
                "script_path": "/provably/stale/launcher.sh",
                "target_run_id_prefixes": ["stale-run"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        _argv(
            tmp_path,
            lane="cloud-run-job.stale",
            command=["/usr/bin/true"],
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not stale.exists()
    assert list(registry_dir.iterdir()) == []
    log = (tmp_path / ".tmp" / "launcher-registry.log").read_text(encoding="utf-8")
    assert "action=stale_cleanup lane=cloud-run-job.stale" in log
    assert "reason=pid_absent" in log
    assert str(stale) in log


@pytest.mark.parametrize("child_status", [0, 7])
def test_receipt_and_flock_clean_up_after_normal_or_nonzero_exit(
    tmp_path: Path, child_status: int
) -> None:
    child = _write_executable(
        tmp_path / "exit-code.sh",
        """#!/usr/bin/env bash
exit "$1"
""",
    )
    result = subprocess.run(
        _argv(
            tmp_path,
            lane="cloud-run-job.exit",
            command=[str(child), str(child_status)],
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == child_status
    assert list((tmp_path / ".tmp" / "launchers").iterdir()) == []

    reacquired = subprocess.run(
        _argv(
            tmp_path,
            lane="cloud-run-job.exit",
            command=["/usr/bin/true"],
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert reacquired.returncode == 0, reacquired.stderr


def test_lane_remains_owned_while_launcher_descendant_survives(tmp_path: Path) -> None:
    descendant_pid_file = tmp_path / "descendant.pid"
    launcher = _write_executable(
        tmp_path / "spawn-descendant.py",
        """#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

descendant = subprocess.Popen(["/bin/sleep", "30"])
Path(sys.argv[1]).write_text(str(descendant.pid), encoding="utf-8")
""",
    )
    wrapped = subprocess.Popen(
        _argv(
            tmp_path,
            lane="cloud-run-job.descendant",
            command=[str(launcher), str(descendant_pid_file)],
        ),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    descendant_pid: int | None = None
    try:
        _wait_for(descendant_pid_file)
        descendant_pid = int(descendant_pid_file.read_text(encoding="utf-8"))
        receipt = _wait_for_one_receipt(tmp_path)
        time.sleep(0.1)
        assert wrapped.poll() is None
        assert receipt.exists()
        assert os.getpgid(descendant_pid) != os.getpgid(wrapped.pid)

        refused = subprocess.run(
            _argv(
                tmp_path,
                lane="cloud-run-job.descendant",
                command=["/usr/bin/true"],
            ),
            text=True,
            capture_output=True,
            check=False,
        )
        assert refused.returncode == 2
        assert "launcher lane is already owned: cloud-run-job.descendant" in refused.stderr

        os.kill(descendant_pid, signal.SIGTERM)
        assert wrapped.wait(timeout=5) == 0
        assert list((tmp_path / ".tmp" / "launchers").iterdir()) == []
    finally:
        if descendant_pid is not None:
            try:
                os.kill(descendant_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if wrapped.poll() is None:
            _stop(wrapped)


def test_signal_cleans_receipt_and_releases_flock(tmp_path: Path) -> None:
    descendant_pid_file = tmp_path / "signal-descendant.pid"
    holder_script = _write_executable(
        tmp_path / "signal-descendant.py",
        """#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys
import time

descendant = subprocess.Popen(["/bin/sleep", "30"])
Path(sys.argv[1]).write_text(str(descendant.pid), encoding="utf-8")
time.sleep(30)
""",
    )
    holder = subprocess.Popen(
        _argv(
            tmp_path,
            lane="cloud-run-job.signal",
            command=[str(holder_script), str(descendant_pid_file)],
        ),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _wait_for(descendant_pid_file)
    descendant_pid = int(descendant_pid_file.read_text(encoding="utf-8"))
    receipt = _wait_for_one_receipt(tmp_path)
    assert receipt.exists()
    assert os.getpgid(descendant_pid) != os.getpgid(holder.pid)
    assert _stop(holder) == 143
    assert list((tmp_path / ".tmp" / "launchers").iterdir()) == []
    deadline = time.monotonic() + 5
    while Path(f"/proc/{descendant_pid}").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not Path(f"/proc/{descendant_pid}").exists()

    reacquired = subprocess.run(
        _argv(
            tmp_path,
            lane="cloud-run-job.signal",
            command=["/usr/bin/true"],
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert reacquired.returncode == 0, reacquired.stderr
