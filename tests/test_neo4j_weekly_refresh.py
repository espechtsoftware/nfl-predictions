"""scripts/neo4j_weekly_refresh.sh's stop path (the reviewer 10-07): it stops Neo4j on every exit -- clean or failed --
but only an instance THIS refresh started, leaves it running under --keep-running, and refuses to run under xtrace before
the credentials are sourced. Offline: a fake neo4j-milly, a fake python and a fake HOME; a local socket stands in for bolt."""
import os
import socket
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "neo4j_weekly_refresh.sh"
SECRET = "fake-password-never-printed"

FAKE_NEO4J = """#!/usr/bin/env bash
echo "$1" >> "$FAKE_LOG"
case $1 in
  status) [[ -f "$FAKE_STATE" ]] ;;
  start) touch "$FAKE_STATE" ;;
  stop) rm -f "$FAKE_STATE" ;;
esac
"""
FAKE_PY = """#!/usr/bin/env bash
echo "py $*" >> "$FAKE_LOG"
[[ -n "${FAKE_FAIL:-}" && "$*" == *"$FAKE_FAIL"* ]] && exit 1
exit 0
"""


@pytest.fixture
def env(tmp_path):
    home, bin_ = tmp_path / "home", tmp_path / "bin"
    (home / ".config").mkdir(parents=True); (home / "moneygate").mkdir(); bin_.mkdir()
    run = tmp_path / "t70"; run.mkdir(); (run / "frame.parquet").write_bytes(b"x")
    (home / "moneygate" / "weeks.json").write_text('{"weeks": {"4": {"t70_run": "%s"}}}' % run)
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(8)
    (home / ".config" / "neo4j-local-milly.txt").write_text(
        f"NEO4J_URI=bolt://127.0.0.1:{srv.getsockname()[1]}\nNEO4J_USER=neo4j\nNEO4J_PASSWORD={SECRET}\n")
    for name, body in (("neo4j-milly", FAKE_NEO4J), ("python", FAKE_PY)):
        (bin_ / name).write_text(body); (bin_ / name).chmod(0o755)
    users = tmp_path / "users.txt"; users.write_text("someone\n")
    e = {**os.environ, "HOME": str(home), "PATH": f"{bin_}:{os.environ['PATH']}", "MILLY_PY": str(bin_ / "python"),
         "FAKE_LOG": str(tmp_path / "calls.log"), "FAKE_STATE": str(tmp_path / "running")}
    yield {"env": e, "users": users, "log": tmp_path / "calls.log", "state": tmp_path / "running"}
    srv.close()


def _run(env, *extra, bash_flags=(), **over):
    r = subprocess.run(["bash", *bash_flags, str(SCRIPT), "4", str(env["users"]), *extra], env={**env["env"], **over},
                       capture_output=True, text=True, timeout=120)
    calls = env["log"].read_text().split("\n") if env["log"].exists() else []
    return r, [c for c in calls if c in ("status", "start", "stop")], [c for c in calls if c.startswith("py ")]


def test_a_refresh_that_started_neo4j_stops_it_on_a_clean_exit(env):
    r, neo, py = _run(env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert neo == ["status", "start", "stop"] and not env["state"].exists()
    assert "Neo4j stopped (this refresh started it)" in r.stdout
    assert len(py) == 8 and any("tier_edges.py" in c and "weekly_picks_vs_field.py" in c for c in py)
    assert any("field_pattern_monitor.py" in c and "--out" in c for c in py)
    assert any("priority_field_monitor.py" in c and "--out" in c for c in py)


def test_a_failed_load_still_stops_the_instance_it_started(env):
    r, neo, py = _run(env, FAKE_FAIL="--with-facts")
    assert r.returncode == 1 and "the facts load failed" in r.stdout
    assert neo == ["status", "start", "stop"] and not env["state"].exists() and len(py) == 2


def test_an_instance_already_running_is_left_as_found(env):
    env["state"].touch()
    r, neo, _ = _run(env)
    assert r.returncode == 0 and neo == ["status"] and env["state"].exists() and "left as found" in r.stdout
    r, neo, _ = _run(env, FAKE_FAIL="--apply")
    assert r.returncode == 1 and "stop" not in neo and env["state"].exists()


def test_keep_running_leaves_the_started_instance_up(env):
    r, neo, _ = _run(env, "--keep-running")
    assert r.returncode == 0 and neo == ["status", "start"] and env["state"].exists() and "LEFT RUNNING" in r.stdout


def test_xtrace_is_refused_before_the_credentials_are_sourced(env):
    r, neo, py = _run(env, bash_flags=("-x",))
    assert r.returncode == 1 and "refusing xtrace" in r.stdout
    assert SECRET not in r.stdout + r.stderr and neo == [] and py == []
