"""scripts/fp_projections_capture.sh: the pre-lock capture of the FP projection pages (reviewer 2026-10-05). Offline: the
collector is replaced by a fake interpreter; the shared browser-profile lock is exercised for real with flock."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fp_projections_capture.sh"


def _fake_py(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "fake_python"
    p.write_text(f"#!/usr/bin/env bash\n{body}\n")
    p.chmod(0o755)
    return p


def _run(tmp_path, py, **env):
    e = {**os.environ, "WEEK": "5", "PROD": str(ROOT), "PROD_PY": str(py), "FP_PROFILE_LOCK": str(tmp_path / "fp.lock"),
         "FP_PROJ_LOG_DIR": str(tmp_path / "logs"), **env}
    return subprocess.run(["bash", str(SCRIPT), "test"], capture_output=True, text=True, env=e, timeout=60)


def test_success_prints_one_line_and_passes_the_week(tmp_path):
    py = _fake_py(tmp_path, 'echo "$@"')
    r = _run(tmp_path, py)
    assert r.returncode == 0 and r.stdout.startswith("FP PROJECTIONS CAPTURED for Week 5 (test)")
    (log,) = (tmp_path / "logs").glob("week5-test-*.log")
    assert log.read_text().strip() == "-m nfl_dfs.ops.fantasy_points_projections collect --week 5"


def test_failure_is_loud_and_fails_the_unit(tmp_path):
    py = _fake_py(tmp_path, 'echo "ERROR: dfs: no table payload was observed" >&2; exit 2')
    r = _run(tmp_path, py)
    assert r.returncode == 1
    assert "FP PROJECTIONS CAPTURE FAILED for Week 5 (test, exit 2): ERROR: dfs: no table payload was observed" in r.stderr


def test_a_held_profile_lock_times_out_loudly_instead_of_colliding(tmp_path):
    py = _fake_py(tmp_path, "echo ran")
    lock = tmp_path / "fp.lock"
    holder = subprocess.Popen(["flock", str(lock), "sleep", "5"])
    try:
        import time
        time.sleep(0.5)
        r = _run(tmp_path, py, FP_LOCK_WAIT_S="1")
    finally:
        holder.kill(); holder.wait()
    assert r.returncode == 1 and "FP PROJECTIONS CAPTURE FAILED" in r.stderr
    (log,) = (tmp_path / "logs").glob("week5-test-*.log")
    assert "ran" not in log.read_text()                         # the collector never started under someone else's lock


def test_the_builds_ownership_capture_takes_the_same_lock():
    text = (ROOT / "scripts" / "sunday_build_host.sh").read_text()
    assert ('flock -w "${FP_LOCK_WAIT_S:-300}" "$FP_PROFILE_LOCK" timeout 240 "$PROD_PY" -m '
            'nfl_dfs.ops.fantasy_points_ownership collect') in text
    assert "FP_PROFILE_LOCK=${FP_PROFILE_LOCK:-$HOME/.cache/nfl-dfs/fantasy-points-profile.lock}" in text
    assert "FP_PROFILE_LOCK:-$HOME/.cache/nfl-dfs/fantasy-points-profile.lock" in SCRIPT.read_text()
