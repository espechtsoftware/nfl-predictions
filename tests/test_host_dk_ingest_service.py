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
