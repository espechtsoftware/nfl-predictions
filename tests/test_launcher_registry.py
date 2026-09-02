from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import time

import pytest

from scripts import cloud_run_lane_monitor as monitor


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
    state_root: Path | None = None,
) -> list[str]:
    args = [
        str(REGISTRY),
        "run",
        "--root",
        str(root),
    ]
    if state_root is not None:
        args.extend(("--state-root", str(state_root)))
    return [
        *args,
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


def _wait_for_one_receipt(
    root: Path, *, state_root: Path | None = None, timeout: float = 5.0
) -> Path:
    directory = (state_root or root / ".tmp") / "launchers"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        receipts = list(directory.glob("*")) if directory.is_dir() else []
        if len(receipts) == 1:
            return receipts[0]
        time.sleep(0.02)
    raise AssertionError("timed out waiting for exactly one launcher receipt")


def _completion_records(root: Path) -> list[tuple[Path, dict[str, object]]]:
    directory = root / ".tmp" / "launcher-completions"
    return [
        (path, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(directory.glob("*.json"))
    ]


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


def test_child_receives_live_lane_receipt_and_wrapper_identity(tmp_path: Path) -> None:
    output = tmp_path / "attestation.json"
    probe = _write_executable(
        tmp_path / "probe.sh",
        """#!/usr/bin/env bash
set -euo pipefail
[[ -f "$NFL_LAUNCHER_REGISTRY_RECEIPT" ]]
actual=$(sha256sum "$NFL_LAUNCHER_REGISTRY_RECEIPT" | awk '{print $1}')
[[ "$actual" == "$NFL_LAUNCHER_REGISTRY_RECEIPT_SHA256" ]]
jq -n --arg receipt "$NFL_LAUNCHER_REGISTRY_RECEIPT" \\
  --arg sha "$NFL_LAUNCHER_REGISTRY_RECEIPT_SHA256" \\
  --arg lane "$NFL_LAUNCHER_REGISTRY_LANE" \\
  --arg pid "$NFL_LAUNCHER_REGISTRY_WRAPPER_PID" \\
  --arg ticks "$NFL_LAUNCHER_REGISTRY_WRAPPER_START_TICKS" \\
  '{receipt:$receipt,sha256:$sha,lane:$lane,pid:$pid,ticks:$ticks}' > "$1"
""",
    )
    completed = subprocess.run(
        _argv(
            tmp_path, lane="cloud-run-job.attested",
            command=[str(probe), str(output)],
        ), text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    attestation = json.loads(output.read_text())
    assert attestation["lane"] == "cloud-run-job.attested"
    assert attestation["pid"].isdigit() and attestation["ticks"].isdigit()
    assert len(attestation["sha256"]) == 64
    completions = _completion_records(tmp_path)
    assert len(completions) == 1
    completion_path, completion = completions[0]
    assert completion_path.stem == attestation["sha256"]
    assert completion["receipt_sha256"] == attestation["sha256"]
    assert completion["exit_status"] == 0
    assert completion["schema_version"] == "shared-launcher-completion/v1"
    assert stat.S_IMODE(completion_path.stat().st_mode) == 0o600
    assert monitor._validated_completion(completion_path) == completion


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


def test_canonical_state_root_excludes_same_lane_across_worktrees(
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "worktree-a"
    root_b = tmp_path / "worktree-b"
    state_root = tmp_path / "canonical-state"
    root_a.mkdir()
    root_b.mkdir()
    holder_script = _holder_script(root_a)
    contender = _write_executable(root_b / "contender.sh", "#!/bin/sh\nexit 0\n")
    ready = root_a / "ready"
    holder = subprocess.Popen(
        _argv(
            root_a,
            state_root=state_root,
            lane="test-cross-worktree-lab-jobs",
            prefixes="084m590r2",
            command=[str(holder_script), str(ready)],
        ),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_for(ready)
        receipt = _wait_for_one_receipt(root_a, state_root=state_root)
        assert receipt.parent == state_root / "launchers"
        refused = subprocess.run(
            _argv(
                root_b,
                state_root=state_root,
                lane="test-cross-worktree-lab-jobs",
                prefixes="084b590r2",
                command=[str(contender)],
            ),
            text=True,
            capture_output=True,
            check=False,
        )
        assert refused.returncode == 2
        assert "launcher lane is already owned: test-cross-worktree-lab-jobs" in refused.stderr
        assert receipt.exists()
    finally:
        _stop(holder)
    assert list((state_root / "launchers").iterdir()) == []


def test_nfl2_shared_lane_rejects_implicit_per_worktree_state(tmp_path: Path) -> None:
    result = subprocess.run(
        _argv(
            tmp_path,
            lane="nfl2-lab-jobs",
            command=["/usr/bin/true"],
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "requires canonical --state-root" in result.stderr

    wrong_explicit = subprocess.run(
        _argv(
            tmp_path,
            state_root=tmp_path / "wrong-canonical-root",
            lane="nfl2-lab-jobs",
            command=["/usr/bin/true"],
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert wrong_explicit.returncode == 2
    assert "requires canonical --state-root" in wrong_explicit.stderr


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


def test_dead_owner_receipt_requires_manual_adjudication(tmp_path: Path) -> None:
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
    assert result.returncode == 2
    assert stale.exists()
    assert "surviving child work cannot be excluded" in result.stderr
    assert "manual adjudication required" in result.stderr


def test_sigkill_orphan_blocks_contender_while_child_group_survives(
    tmp_path: Path,
) -> None:
    wrapped = subprocess.Popen(
        _argv(
            tmp_path,
            lane="cloud-run-job.sigkill",
            command=["/bin/sleep", "30"],
        ),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    receipt = _wait_for_one_receipt(tmp_path)
    child_pid: int | None = None
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = subprocess.run(
                ["pgrep", "-P", str(wrapped.pid)],
                text=True,
                capture_output=True,
                check=False,
            )
            values = [int(value) for value in result.stdout.split()]
            if values:
                child_pid = values[0]
                break
            time.sleep(0.02)
        assert child_pid is not None
        os.kill(wrapped.pid, signal.SIGKILL)
        assert wrapped.wait(timeout=5) == -signal.SIGKILL
        assert Path(f"/proc/{child_pid}").exists()

        contender = subprocess.run(
            _argv(
                tmp_path,
                lane="cloud-run-job.sigkill",
                command=["/usr/bin/true"],
            ),
            text=True,
            capture_output=True,
            check=False,
        )
        assert contender.returncode == 2
        assert receipt.exists()
        assert "surviving child work cannot be excluded" in contender.stderr
    finally:
        if child_pid is not None:
            try:
                os.killpg(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        receipt.unlink(missing_ok=True)


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
    records = _completion_records(tmp_path)
    assert len(records) == 1
    _, completion = records[0]
    assert completion["exit_status"] == child_status
    assert completion["lane"] == "cloud-run-job.exit"
    assert completion["target_run_id_prefixes"] == ["run-a", "run-b"]

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


def test_cleanup_failure_retains_receipt_after_terminal_publication(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "rm",
        """#!/usr/bin/env bash
set -euo pipefail
last=${!#}
if [[ "$last" == */.launcher-group.* ]]; then
  exit 1
fi
exec /usr/bin/rm "$@"
""",
    )
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    result = subprocess.run(
        _argv(
            tmp_path,
            lane="cloud-run-job.cleanup-failure",
            prefixes="cleanup-failure",
            command=["/usr/bin/true"],
        ),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode == 2
    receipts = list((tmp_path / ".tmp" / "launchers").glob("*.json"))
    assert len(receipts) == 1
    records = _completion_records(tmp_path)
    assert len(records) == 1
    _, completion = records[0]
    assert completion["exit_status"] == 0
    assert "prerequisite_cleanup_failed" in result.stderr
    # The retained receipt makes the post-publication wrapper failure visible
    # as a terminalized orphan and prevents a receiptless accepted success.
    receipt_sha = hashlib.sha256(receipts[0].read_bytes()).hexdigest()
    assert receipt_sha == completion["receipt_sha256"]
    contender = subprocess.run(
        _argv(
            tmp_path,
            lane="cloud-run-job.cleanup-failure",
            prefixes="replacement",
            command=["/usr/bin/true"],
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert contender.returncode == 2
    assert "manual adjudication required" in contender.stderr


@pytest.mark.parametrize(("child_status", "wrapper_status"), [(0, 2), (7, 7)])
def test_completion_write_failure_preserves_orphan_guard_and_child_status(
    tmp_path: Path, child_status: int, wrapper_status: int
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(fake_bin / "sync", "#!/usr/bin/env bash\nexit 1\n")
    child = _write_executable(
        tmp_path / "completion-failure-child.sh",
        "#!/usr/bin/env bash\nexit \"$1\"\n",
    )
    environment = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}

    result = subprocess.run(
        _argv(
            tmp_path,
            lane="cloud-run-job.completion-failure",
            command=[str(child), str(child_status)],
        ),
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )

    assert result.returncode == wrapper_status
    assert "action=completion_failed" in result.stderr
    receipts = list((tmp_path / ".tmp" / "launchers").iterdir())
    assert len(receipts) == 1
    assert _completion_records(tmp_path) == []
    reacquired = subprocess.run(
        _argv(
            tmp_path,
            lane="cloud-run-job.completion-failure",
            command=["/usr/bin/true"],
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert reacquired.returncode == 2
    assert "manual adjudication required" in reacquired.stderr


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
    records = _completion_records(tmp_path)
    assert len(records) == 1
    assert records[0][1]["exit_status"] == 143
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
