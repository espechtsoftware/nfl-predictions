"""O-19: `sunday_build_host.sh` takes no arguments.

It used to accept and ignore them, so `sunday_build_host.sh --check` (2026-10-02) started a real build in the live OUT
and clone. The driver must refuse ANY argument before its first side effect. Both tests run the real script in a
sandbox: every path variable points into tmp_path, HOME is tmp_path, and both interpreters are recording fakes that
exit 1, so even an unguarded run cannot reach BigQuery, the lab clone or the real week directory.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "scripts" / "sunday_build_host.sh"
REFUSAL = "sunday_build_host.sh takes no arguments (use run_week_build.sh --check)"


def _sandbox(tmp_path: Path) -> dict[str, str]:
    fake = tmp_path / "fake-python"
    fake.write_text('#!/usr/bin/env bash\necho "$0 $*" >> "$SANDBOX/interpreter-calls"\nexit 1\n')
    fake.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    env = {
        "PATH": "/usr/bin:/bin", "HOME": str(home), "SANDBOX": str(tmp_path),
        "WEEK": "5", "SEASON": "2026", "GROUP": "999999", "WEEKDIR": "w05", "RUN_SUFFIX": "test",
        "OUT": str(tmp_path / "out"), "CLONE": str(tmp_path / "clone"), "PROD": str(tmp_path / "prod"),
        "TOOLS": str(tmp_path / "tools"), "LIVE_DIR": str(tmp_path / "live"),
        "CONTESTS_JSON": str(tmp_path / "out" / "contests.json"),
        "PROD_PY": str(fake), "LAB_PY": str(fake),
        "BOOK_ENTRIES": "90", "TAIL_SLEEVE": "0", "MAX_PER_GAME": "0",
    }
    return env


def _tree(tmp_path: Path) -> set[str]:
    return {str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")}


def test_check_flag_is_refused_before_any_side_effect(tmp_path):
    env = _sandbox(tmp_path)
    before = _tree(tmp_path)
    r = subprocess.run(["bash", str(HOST), "--check"], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert r.stdout.strip() == REFUSAL
    assert _tree(tmp_path) == before, "the refused call wrote something"
    assert not (tmp_path / "out").exists()


def test_any_argument_is_refused(tmp_path):
    env = _sandbox(tmp_path)
    r = subprocess.run(["bash", str(HOST), "4"], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and REFUSAL in r.stdout
    assert not (tmp_path / "out").exists()


def test_plain_call_passes_the_guard(tmp_path):
    """No arguments: the driver proceeds as before (here it stops at the sandbox's missing contests file)."""
    env = _sandbox(tmp_path)
    r = subprocess.run(["bash", str(HOST)], env=env, capture_output=True, text=True, timeout=60)
    assert REFUSAL not in r.stdout
    assert "per-game cap:" in r.stdout
    assert "contests file missing" in r.stdout
    assert (tmp_path / "out").is_dir(), "the plain call reached its first side effect (mkdir OUT)"


def test_the_guard_precedes_the_first_side_effect():
    lines = HOST.read_text().splitlines()
    guard = next(i for i, l in enumerate(lines) if "(( $# == 0 ))" in l)
    first_effect = next(i for i, l in enumerate(lines) if l.startswith(("mkdir", "echo", "LOG=", "exec")))
    assert guard < first_effect
