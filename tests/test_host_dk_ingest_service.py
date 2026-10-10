from pathlib import Path


ROOT = Path(__file__).parents[1]
UNIT = ROOT / "deploy/systemd/nfl-host-dk-ingest.service"


def test_host_dk_service_uses_tracked_loop_and_production_project():
    text = UNIT.read_text()
    assert "ExecStart=%h/projects/nfl-predictions/scripts/host_ingest_dk_loop.sh" in text
    assert "Environment=GCP_PROJECT=nfl-predictions-503414" in text
    assert "Environment=INTERVAL_SECONDS=3600" in text
    # The OUT=%h/week3-sunday assertion this test originally carried was dropped
    # on merge, together with the setting itself. OUT's only effect in the loop is
    # to name the pid file, and relocating it would have hidden the running
    # prototype from the single-instance guard. See the PID_FILE tests below.


def test_host_dk_service_is_restartable_but_not_a_cloud_run_mutation():
    text = UNIT.read_text()
    assert "Restart=on-failure" in text
    assert "RestartSec=60s" in text
    assert "StartLimitIntervalSec=1h" in text
    assert "StartLimitBurst=3" in text
    assert "ExecStartPre=/usr/bin/test -x %h/projects/nfl-predictions/scripts/host_ingest_dk_loop.sh" in text
    assert "gcloud run" not in text


# --- Added on merge (workstation, 2026-09-21) ---------------------------------
# The unit as proposed set OUT=%h/week3-sunday. In the tracked loop OUT's only
# effect is to name the pid file, and LOCK_FILE derives from it, so that choice
# would have given the unit a different pid and lock file from the running
# prototype in week1-sunday. flock and the stale-pid check could not have seen
# it, and both loops would have run, double-pulling every hour.

from pathlib import Path as _Path

_UNIT = _Path(__file__).parents[1] / "deploy" / "systemd" / "nfl-host-dk-ingest.service"
_LOOP = _Path(__file__).parents[1] / "scripts" / "host_ingest_dk_loop.sh"
_PROTOTYPE_PID = "/home/erich/week1-sunday/host_ingest_dk_loop.pid"


def _env(unit_text):
    out = {}
    for line in unit_text.splitlines():
        if line.startswith("Environment="):
            k, _, v = line[len("Environment="):].partition("=")
            out[k] = v
    return out


def test_the_unit_shares_the_prototypes_pid_file():
    """Or its single-instance guard cannot see the process it must not duplicate."""
    env = _env(_UNIT.read_text())
    assert "PID_FILE" in env, "the unit must pin PID_FILE explicitly"
    assert env["PID_FILE"].replace("%h", "/home/erich") == _PROTOTYPE_PID


def test_the_unit_does_not_relocate_the_pid_file_via_out():
    """Setting OUT is the subtle way to defeat the guard; it must not be set."""
    assert "OUT" not in _env(_UNIT.read_text())


def test_the_loop_derives_its_lock_from_the_pid_file():
    """The reason pinning PID_FILE is sufficient: LOCK_FILE follows it."""
    loop = _LOOP.read_text()
    assert "LOCK_FILE=${LOCK_FILE:-${PID_FILE}.lock}" in loop
    assert "PID_FILE=${PID_FILE:-${OUT:-$HOME/week1-sunday}/host_ingest_dk_loop.pid}" in loop


def test_the_loop_refuses_to_start_beside_a_live_pid():
    """The behaviour the pinned path buys: a loud refusal, not a silent double-pull."""
    loop = _LOOP.read_text()
    assert 'kill -0 "$old_pid"' in loop
    assert "is still running" in loop
    assert "flock -n 9" in loop


# --- O-65 (laptop, 2026-10-10): one failed pull must not kill the loop ----------------------------------------------
# Fri 10-09 04:07 a ConnectionError made ingest-dk exit 1; run_pull's unconditional `set -e` re-armed errexit, so
# run_pair's failing call ended the loop (status 1), systemd's start limit stopped the restarts, and the hourly pulls
# stopped for 25.5 h. The loop below runs the REAL script with a stub CLI that fails its first call and then succeeds.

import os as _os
import subprocess as _subprocess
import sys as _sys


def test_the_loop_survives_a_failed_pull_and_runs_the_next_cycle(tmp_path):
    counter = tmp_path / "calls"
    stub = tmp_path / "nfl-dfs"
    stub.write_text("#!/usr/bin/env bash\n"
                    f"n=$(( $(cat {counter} 2>/dev/null || echo 0) + 1 )); echo $n > {counter}\n"
                    "[[ $n -eq 1 ]] && { echo 'ConnectionError (stub)' >&2; exit 1; }\n"
                    "exit 0\n")
    stub.chmod(0o755)
    env = {**_os.environ, "CLI": str(stub), "PROD_PY": _sys.executable, "INTERVAL_SECONDS": "1",
           "PID_FILE": str(tmp_path / "loop.pid"), "GCP_PROJECT": "nfl-predictions-503414"}
    try:
        out = _subprocess.run(["bash", str(_LOOP)], env=env, capture_output=True, text=True, timeout=6)
        stdout, stderr, rc = out.stdout, out.stderr, out.returncode
    except _subprocess.TimeoutExpired as e:      # the healthy outcome: still looping when the test stops it
        stdout = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = (e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        rc = None
    assert rc is None, f"the loop exited (rc {rc}) instead of continuing:\n{stdout}\n{stderr}"
    assert "ingest-dk exit=1" in stdout and "host DK ingest pair failed: ingest-dk=1 ingest-contests=0" in stderr
    assert "ingest-contests exit=0" in stdout                    # the second pull of the failed cycle still ran
    assert "host DK ingest pair succeeded" in stdout             # and a later cycle succeeded
    assert int(counter.read_text()) >= 4


def test_run_pull_restores_the_callers_errexit_instead_of_forcing_it():
    loop = _LOOP.read_text()
    assert "((errexit)) && set -e" in loop and "\n  set -e\n" not in loop.split("run_pull() {")[1].split("\n}\n")[0]
    assert "run_pull ingest-dk ingest-dk || dk_status=$?" in loop
