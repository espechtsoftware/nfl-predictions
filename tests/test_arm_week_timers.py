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


def test_run_refuses_without_group_before_any_preflight():
    r = subprocess.run(["bash", str(SCRIPT), "4", "--run"], capture_output=True, text=True,
                       env={**{k: v for k, v in os.environ.items() if k != "GROUP"}, "EXPECT_SHA": PIN})
    assert r.returncode == 2 and "without GROUP" in r.stderr


def test_units_carry_path_and_group():
    r = _run(GROUP="154078")
    line = _unit_line(r.stdout, "nfl-week4-t70-build")
    assert "GROUP=154078" in line and "PATH=" in line


def test_main_book_cap_rides_into_the_units():
    r = _run(GROUP="154078", UNION_MAIN_CAP="0.4")
    assert r.returncode == 0, r.stderr
    assert "UNION_MAIN_CAP=0.4" in _unit_line(r.stdout, "nfl-week4-t70-build")


def test_ownership_term_rides_into_the_units_and_the_saturday_steps_print():
    r = _run(GROUP="154078", UNION_MAIN_OWN_TILT="0.20")
    assert r.returncode == 0, r.stderr
    assert "UNION_MAIN_OWN_TILT=0.20" in _unit_line(r.stdout, "nfl-week4-t70-build")
    assert "--lag-features --out" in r.stdout and "check_ownership_lag.py" in r.stdout
    assert 'check_ownership_lag.py" "${OWNERSHIP_LAG:-$OUT/ownership_lag.csv}" || exit 2' in SCRIPT.read_text()   # gate 4 before arming


def test_tabpfn_predictor_rides_into_the_units_and_is_preflighted():
    r = _run(GROUP="154078", UNION_MAIN_OWN_TILT="0.20", UNION_MAIN_OWN_PREDICTOR="tabpfn")
    assert r.returncode == 0, r.stderr
    assert "UNION_MAIN_OWN_PREDICTOR=tabpfn" in _unit_line(r.stdout, "nfl-week4-t70-build")
    assert "ownership_tabpfn.py lags" in r.stdout
    src = SCRIPT.read_text()
    assert "TABPFN PREFLIGHT FAILED" in src and "0bec4237eb4c4bc1228571e5628685b3cc26e8aaed433f8b8f2056d5062edde9" in src


def test_small_contest_overlap_limit_rides_into_the_units():
    r = _run(GROUP="154078", ENTER_SMALL_MAX_SHARED="5")
    assert r.returncode == 0, r.stderr
    assert "ENTER_SMALL_MAX_SHARED=5" in _unit_line(r.stdout, "nfl-week4-t70-build")


def test_lev_cbc_threads_rides_into_the_units():
    r = _run(GROUP="154078", LEV_CBC_THREADS="8")
    assert r.returncode == 0, r.stderr
    assert "LEV_CBC_THREADS=8" in _unit_line(r.stdout, "nfl-week4-d12800-sat-build")


def test_sunday_early_supply_units():
    """Operator 2026-10-01: with 8 threads the D12800 is ~2 h, so a second one runs on Sunday's pre-dawn information:
    props 03:45, project-slate 04:00, the D12800 at EARLY_SUPPLY_CT; Saturday's D12800 and D6400 stay as fallbacks."""
    r = _run(GROUP="154078", EARLY_SUPPLY_CT="04:30", LEV_CBC_THREADS="8", SKIP_UNITS="d6400")
    assert r.returncode == 0, r.stderr
    sun = _unit_line(r.stdout, "nfl-week4-d12800-sun-build")
    assert "2026-10-04 04:30 America/Chicago" in sun and "PAID_LEV=2560 PAID_BOOM=10240" in sun and "LEV_CBC_THREADS=8" in sun
    assert "d12800sun" in sun                                                   # its own run tag
    assert "2026-10-04 03:45 America/Chicago" in _unit_line(r.stdout, "nfl-week4-early-props")
    proj = _unit_line(r.stdout, "nfl-week4-early-project")
    assert "2026-10-04 04:00 America/Chicago" in proj and "project-slate" in proj and "T70_ACTIVE_Q" not in proj
    assert "2026-10-03 10:30 America/Chicago" in _unit_line(r.stdout, "nfl-week4-d12800-sat-build")   # kept as fallback
    assert "2026-10-03 10:35 America/Chicago" in _unit_line(r.stdout, "nfl-week4-d6400-sat-build")
    none = _run(GROUP="154078")
    assert "d12800-sun-build" not in none.stdout and "early-props" not in none.stdout   # opt-in


def test_fp_projections_unit_is_armed_before_t70_and_skippable():
    """2026-10-05 (reviewer): the FP projection pages are captured pre-lock on Sunday, after the inactives and before T-70."""
    r = _run(GROUP="154078")
    assert r.returncode == 0, r.stderr
    line = _unit_line(r.stdout, "nfl-week4-fp-projections")
    assert "2026-10-04 10:40 America/Chicago" in line and line.endswith("fp_projections_capture.sh sunday-prelock")
    assert "GCP_PROJECT=nfl-predictions-503414" in line and "WEEK=4" in line and "PROD_PY=" in line
    assert "FP projections capture at 10:40 CT" in r.stdout
    r = _run(GROUP="154078", SKIP_UNITS="fpproj", FP_PROJ_CT="10:41")
    assert r.returncode == 0 and "# SKIPPED (fpproj): nfl-week4-fp-projections" in r.stdout
    text = SCRIPT.read_text()                       # the Saturday capture at arming never stops the arming
    assert '"$FP_PROJ_CAPTURE" saturday-arm \\\n      || echo "FP PROJECTIONS: the Saturday capture FAILED' in text
