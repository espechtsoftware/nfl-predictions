"""arm_week_timers.sh in print mode (no --run: nothing is armed, no provider call). Week-4 laptop additions."""
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "arm_week_timers.sh"
PIN = "54dd512" + "0" * 33


def _run(**env):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("D800_", "D3200_", "SKIP_", "T70_", "GCP_"))}
    e.update({"EXPECT_SHA": PIN, "GCLOUD": "/bin/true", "NFL_DFS_CLI": "/bin/true", **env})
    return subprocess.run(["bash", str(SCRIPT), "4"], capture_output=True, text=True, env=e)


def _unit_line(out: str, unit: str) -> str:
    lines = [l for l in out.splitlines() if l.startswith("systemd-run") and f'--unit="{unit}"' in l]
    assert len(lines) == 1, (unit, lines)
    return lines[0]


def test_week4_arm_line():
    r = _run(D3200_LEV="0", D3200_BOOM="4800", D800_LEV="0", D800_BOOM="4800", SKIP_UNITS="d6400sat d6400",
             T70_MIN_PROJ_CT="10:30", T70_PROJECT="1")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    runs = [l for l in out.splitlines() if l.startswith("systemd-run")]
    env_units = [l for l in runs if "t70-project" not in l]                               # gcloud takes --project instead
    assert env_units and all("GCP_PROJECT=nfl-predictions-503414" in l for l in env_units)  # the Week-3 5-second failure
    assert "# SKIPPED (d6400sat): nfl-week4-d6400-sat-build" in out and "# SKIPPED (d6400): nfl-week4-d6400-build" in out
    t70 = _unit_line(out, "nfl-week4-t70-build")
    assert "2026-10-04 10:50 America/Chicago" in t70 and "PAID_LEV=0 PAID_BOOM=4800" in t70
    assert "MIN_PROJ_GENERATED_AT=2026-10-04T15:30:00+00:00" in t70                        # 10:30 CT
    assert "MIN_PROJ_GENERATED_AT" not in _unit_line(out, "nfl-week4-d3200-build")          # the 09:10 book is pre-inactives by design
    assert "2026-10-04 10:33 America/Chicago" in _unit_line(out, "nfl-week4-t70-pull")
    proj = _unit_line(out, "nfl-week4-t70-project")
    assert "2026-10-04 10:36 America/Chicago" in proj and "T70_ACTIVE_Q=1,T70_VACATED_BUMP=1" in proj and "--wait" in proj
    assert "2026-10-03 10:30 America/Chicago" in _unit_line(out, "nfl-week4-d12800-sat-build")


def test_defaults_arm_every_build_and_no_t70_units():
    r = _run()
    assert r.returncode == 0, r.stderr
    assert "SKIPPED" not in r.stdout and "t70-pull" not in r.stdout and "MIN_PROJ_GENERATED_AT" not in r.stdout
    assert "PAID_LEV=160 PAID_BOOM=640" in _unit_line(r.stdout, "nfl-week4-t70-build")


def test_unknown_skip_key_is_refused():
    r = _run(SKIP_UNITS="d6400 nonsense")
    assert r.returncode == 2 and "unknown unit key nonsense" in r.stderr
