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
    text = SCRIPT.read_text()                       # the Saturday capture at arming never stops the arming ...
    assert '"$FP_PROJ_CAPTURE" saturday-arm \\\n    || echo "FP PROJECTIONS: the Saturday capture FAILED' in text
    # ... and never delays it (reviewer 10-05): it runs only after the last timer is armed
    assert text.index('"$FP_PROJ_CAPTURE" saturday-arm') > text.rindex("\n  arm t70project ")
    assert text.index('"$FP_PROJ_CAPTURE" saturday-arm') > text.rindex("\narm fpproj ")


def test_the_capture_only_job_cannot_wait_ahead_of_the_t70_money_path():
    """Reviewer 10-05: lock wait + timeout of the projections wrapper (defaults) end before the T-70 build starts, and
    its lock wait is shorter than the T-70 ownership capture's, so a hung capture never degrades the money-path input."""
    import re
    wrapper = (SCRIPT.parent / "fp_projections_capture.sh").read_text()
    wait = int(re.search(r'flock -w "\$\{FP_PROJ_LOCK_WAIT_S:-(\d+)\}"', wrapper).group(1))
    run = int(re.search(r'timeout "\$\{FP_PROJ_TIMEOUT_S:-(\d+)\}"', wrapper).group(1))
    text = SCRIPT.read_text()
    hh, mm = map(int, re.search(r"FP_PROJ_CT=\$\{FP_PROJ_CT:-(\d\d):(\d\d)\}", text).groups())
    th, tm = map(int, re.search(r"T70_BUILD_CT:-(\d\d):(\d\d)\}", text).groups())
    assert wait + run < ((th * 60 + tm) - (hh * 60 + mm)) * 60
    host = (SCRIPT.parent / "sunday_build_host.sh").read_text()
    assert wait < int(re.search(r'flock -w "\$\{FP_OWN_LOCK_WAIT_S:-(\d+)\}" "\$FP_PROFILE_LOCK"', host).group(1))



def test_the_arming_banner_states_the_main_book_its_portfolio_and_the_projections():
    r = _run(GROUP="154078", UNION_MAIN="mix", UNION_MIX_PORTFOLIO="ws", UNION_PROJ_SOURCE="fp")
    assert r.returncode == 0, r.stderr
    assert "# Main book: UNION_MAIN=mix PORTFOLIO=ws; projections: fp" in r.stdout
    r = _run(GROUP="154078", UNION_MAIN="mix")
    assert "PORTFOLIO=UNSET (refused at arming)" in r.stdout
    assert "UNION_MIX_PORTFOLIO=ws" in _unit_line(_run(GROUP="154078", UNION_MAIN="mix", UNION_MIX_PORTFOLIO="ws").stdout, "nfl-week4-t70-build")


def test_two_sunday_fp_captures_are_armed_and_one_key_skips_both():
    """The outside review (10-06): one 240-second 10:40 capture was the only post-inactives FP chance; a second unit runs
    at 10:46 (before the 10:50 T-70 build); SKIP_UNITS fpproj skips both."""
    r = _run()
    assert "2026-10-04 10:40 America/Chicago" in _unit_line(r.stdout, "nfl-week4-fp-projections")
    assert "2026-10-04 10:46 America/Chicago" in _unit_line(r.stdout, "nfl-week4-fp-projections-2")
    s = _run(SKIP_UNITS="fpproj")
    assert not [l for l in s.stdout.splitlines() if l.startswith("systemd-run") and "fp-projections" in l]
    assert "# SKIPPED (fpproj): nfl-week4-fp-projections-2" in s.stdout


def test_the_stale_fp_refusal_rides_the_t70_gate_not_the_t70_rules():
    """The reviewer (10-06, R1): sunday_build_host refuses a pre-inactives FP capture on the unit that carries the T-70
    gate's MIN_PROJ_GENERATED_AT -- only the 10:50 unit, even with both T-70 rules off -- never keyed on T70_DECLARED."""
    from pathlib import Path
    r = _run(D800_LEV="0", D800_BOOM="4800", T70_MIN_PROJ_CT="10:30", T70_ACTIVE_Q="0", T70_VACATED_BUMP="0")
    assert r.returncode == 0, r.stderr
    assert "MIN_PROJ_GENERATED_AT=2026-10-04T15:30:00+00:00" in _unit_line(r.stdout, "nfl-week4-t70-build")
    assert "MIN_PROJ_GENERATED_AT" not in _unit_line(r.stdout, "nfl-week4-d3200-build")
    host = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_build_host.sh").read_text()
    assert '[[ -n "${MIN_PROJ_GENERATED_AT:-}" ]] && echo --require-after-inactives' in host
    assert '"$T70_DECLARED" == on ]] && echo --require-after-inactives' not in host


def test_the_union_overlap_limit_rides_into_the_units_and_defaults_to_7():
    """The outside review's lever (10-06): UNION_MEAN_MAX_SHARED reaches the build units; the host defaults to 7."""
    from pathlib import Path
    r = _run(UNION_MEAN_MAX_SHARED="5")
    assert "UNION_MEAN_MAX_SHARED=5" in _unit_line(r.stdout, "nfl-week4-t70-build")
    assert "UNION_MEAN_MAX_SHARED" not in _unit_line(_run().stdout, "nfl-week4-t70-build")
    host = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_build_host.sh").read_text()
    assert '--mean-max-shared "${UNION_MEAN_MAX_SHARED:-7}"' in host and "--mean-max-shared 7 " not in host


def test_the_mix_fill_rides_into_the_units_and_unset_keeps_the_group_fill():
    """Study 42's switch (operator 10-06): UNION_MIX_FILL reaches the build units; unset passes no --mix-fill (group)."""
    from pathlib import Path
    r = _run(UNION_MIX_FILL="value")
    assert "UNION_MIX_FILL=value" in _unit_line(r.stdout, "nfl-week4-t70-build")
    assert "UNION_MIX_FILL" not in _unit_line(_run().stdout, "nfl-week4-t70-build")
    host = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_build_host.sh").read_text()
    assert '-n "${UNION_MIX_FILL:-}" ]] && UNION_ARGS+=(--mix-fill "$UNION_MIX_FILL")' in host


def test_the_mix_cover_rides_into_the_units_and_0_passes_nothing():
    """Study 43's switch: UNION_MIX_COVER_GAMES reaches the build units; the host passes --mix-cover-games only when not 0."""
    from pathlib import Path
    r = _run(UNION_MIX_COVER_GAMES="4")
    assert "UNION_MIX_COVER_GAMES=4" in _unit_line(r.stdout, "nfl-week4-t70-build")
    host = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_build_host.sh").read_text()
    assert '"${UNION_MIX_COVER_GAMES:-0}" != 0 ]] && UNION_ARGS+=(--mix-cover-games "$UNION_MIX_COVER_GAMES")' in host


def test_the_bring_back_top_wr_rides_into_the_units_and_empty_passes_nothing():
    """Study 71's switch: UNION_MIX_BRING_BACK_TOP_WR reaches the build units; the host passes --mix-bring-back-top-wr only
    when it is set (empty = off, the default), and the Week-5 arm defaults it to off and allows only the tested arm."""
    from pathlib import Path
    r = _run(UNION_MIX_BRING_BACK_TOP_WR="A1,B")
    assert "UNION_MIX_BRING_BACK_TOP_WR=A1,B" in _unit_line(r.stdout, "nfl-week4-t70-build")
    root = Path(__file__).resolve().parents[1] / "scripts"
    host = (root / "sunday_build_host.sh").read_text()
    assert '-n "${UNION_MIX_BRING_BACK_TOP_WR:-}" ]] && UNION_ARGS+=(--mix-bring-back-top-wr "$UNION_MIX_BRING_BACK_TOP_WR")' in host
    arm = (root / "arm_week5_saturday.sh").read_text()
    assert '\nBRING_BACK_TOP_WR=""' in arm
    assert "UNION_MIX_BRING_BACK_TOP_WR=$BRING_BACK_TOP_WR" in arm
    assert '"$BRING_BACK_TOP_WR" == "A1,B" && "$SHAPE" == mixt && "$MIX_FILL" == rr' in arm


def test_the_bring_back_rows_cap_rides_into_the_units_and_needs_the_rule():
    """Study 71b's dose: UNION_MIX_BRING_BACK_TOP_WR_ROWS reaches the build units; the host passes
    --mix-bring-back-top-wr-rows only with the rule itself set; the Week-5 arm allows only 4 with A1,B (default off)."""
    from pathlib import Path
    r = _run(UNION_MIX_BRING_BACK_TOP_WR="A1,B", UNION_MIX_BRING_BACK_TOP_WR_ROWS="4")
    assert "UNION_MIX_BRING_BACK_TOP_WR_ROWS=4" in _unit_line(r.stdout, "nfl-week4-t70-build")
    root = Path(__file__).resolve().parents[1] / "scripts"
    host = (root / "sunday_build_host.sh").read_text()
    assert ('-n "${UNION_MIX_BRING_BACK_TOP_WR:-}" && -n "${UNION_MIX_BRING_BACK_TOP_WR_ROWS:-}" ]] && '
            'UNION_ARGS+=(--mix-bring-back-top-wr-rows "$UNION_MIX_BRING_BACK_TOP_WR_ROWS")') in host
    arm = (root / "arm_week5_saturday.sh").read_text()
    assert '\nBRING_BACK_TOP_WR_ROWS=""' in arm
    assert "UNION_MIX_BRING_BACK_TOP_WR_ROWS=$BRING_BACK_TOP_WR_ROWS" in arm
    assert '"$BRING_BACK_TOP_WR_ROWS" == 4 && "$BRING_BACK_TOP_WR" == "A1,B"' in arm


def test_the_half_and_half_rides_into_the_units_and_0_passes_nothing():
    """Study 46's switch: UNION_MIX_RS_ROWS reaches the build units; the host passes --mix-rs-rows only when not 0."""
    from pathlib import Path
    r = _run(UNION_MIX_RS_ROWS="13")
    assert "UNION_MIX_RS_ROWS=13" in _unit_line(r.stdout, "nfl-week4-t70-build")
    host = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_build_host.sh").read_text()
    assert '"${UNION_MIX_RS_ROWS:-0}" != 0 ]] && UNION_ARGS+=(--mix-rs-rows "$UNION_MIX_RS_ROWS")' in host


def test_the_winner_order_rides_into_the_units_and_the_host_falls_back_loudly():
    """Study 48b's switch: UNION_WINNER_ORDER reaches the build units; the host applies it only with the mix and keeps the
    book's own order, loudly, on any failure."""
    from pathlib import Path
    r = _run(UNION_WINNER_ORDER="1")
    assert "UNION_WINNER_ORDER=1" in _unit_line(r.stdout, "nfl-week4-t70-build")
    host = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_build_host.sh").read_text()
    assert '[[ "${UNION_WINNER_ORDER:-0}" == "1" ]] && WIN_FLAG="--winner-order"' in host
    assert '[[ "${UNION_WINNER_SELECT:-0}" == "1" ]] && WIN_FLAG="--winner-select"' in host
    assert '[[ -n "$WIN_FLAG" && "${UNION_MAIN:-mean}" == "mix" ]]' in host
    assert "NOT APPLIED for $RUN_TAG" in host and 'UNION_ARGS+=("$WIN_FLAG" "$OUT/winner_inputs-$RUN_TAG.csv")' in host
    r2 = _run(UNION_WINNER_SELECT="1")
    assert "UNION_WINNER_SELECT=1" in _unit_line(r2.stdout, "nfl-week4-t70-build")


def test_the_term_block_rides_into_the_units_and_a_missing_block_stops_publication():
    """The prior-top term block (the operator 10-07): its env reaches the build units; the host passes it to the union and
    marks a union built WITHOUT it term_block_missing (not publishable until his decision)."""
    from pathlib import Path
    r = _run(UNION_TERM_BLOCK_ROWS="8", UNION_TERM_BLOCK_SOURCE="/x/priortop-w5.csv", UNION_TERM_BLOCK_SHA256="ab" * 32)
    line = _unit_line(r.stdout, "nfl-week4-t70-build")
    assert "UNION_TERM_BLOCK_ROWS=8" in line and "UNION_TERM_BLOCK_SOURCE=/x/priortop-w5.csv" in line and "UNION_TERM_BLOCK_SHA256=" in line
    host = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_build_host.sh").read_text()
    assert 'UNION_ARGS+=(--term-block-rows "$UNION_TERM_BLOCK_ROWS"' in host
    assert '| tee "$UNION_DIR/term_block_missing" > "$OUT/ALERT-term-block-missing-$RUN_TAG.txt"' in host
    after = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_after_build.sh").read_text()
    assert '[[ "${TERM_BLOCK_MISSING_OK:-0}" == "1" ]] && echo --accept-term-block-missing' in after
    arm = (Path(__file__).resolve().parents[1] / "scripts" / "arm_week5_saturday.sh").read_text()
    assert '\nTERM_ROWS="" ' in arm and "UNION_TERM_BLOCK_SHA256=$TERM_SHA" in arm         # M2: empty refuses to arm
    assert '[[ -n "$TERM_ROWS" ]] || stop "TERM_ROWS is not set' in arm
    assert "\nTERM_FILE=reports/2026-10-08-live-block/cheap2-w5.csv " in arm and "--require-bonus" in arm


def test_the_week5_arm_pins_the_class_sleeves_model_in_step_0():
    """O-42 (10-07): week_env's CLASS_SLEEVE_EVERY=2 makes every build's preflight need $OUT/class_model.json + .sha256;
    the Week-5 arm checks the installed model against a pinned CLASS_SHA in step 0 (so --check catches it too)."""
    from pathlib import Path
    arm = (Path(__file__).resolve().parents[1] / "scripts" / "arm_week5_saturday.sh").read_text()
    assert "\nCLASS_SHA=92cec73388193a107c235ff3d8e8dafeea9a2d5d0121b481814b2e4fe0802f13 " in arm
    step0 = arm[arm.index("# 0. the checkout"):arm.index('say "step 0 OK')]
    assert '[[ -s $W/class_model.json && -s $W/class_model.json.sha256 ]] || stop' in step0
    assert '"$(sha256sum $W/class_model.json | cut -c1-64)" == "$CLASS_SHA"' in step0
    assert '"$(cut -c1-64 $W/class_model.json.sha256)" == "$CLASS_SHA"' in step0
    env = (Path(__file__).resolve().parents[1] / "scripts" / "week_env.sh").read_text()
    assert "CLASS_SLEEVE_EVERY=${CLASS_SLEEVE_EVERY-2}" in env and "CLASS_MODEL=${CLASS_MODEL:-$OUT/class_model.json}" in env


def test_study_56s_cell_quotas_ride_into_the_units_and_the_week5_arm_keeps_them_off():
    """Study 56's switch (the operator 10-07): UNION_MIX_CELL_QUOTAS reaches the build units and the host passes
    --mix-cell-quotas; unset passes nothing; the Week-5 arm keeps MIX_QUOTAS empty until 56 passes and he says yes."""
    from pathlib import Path
    r = _run(UNION_MIX_CELL_QUOTAS="A1=0.40,A2=0.26,B=0.17,C=0.17")
    assert "UNION_MIX_CELL_QUOTAS=A1=0.40,A2=0.26,B=0.17,C=0.17" in _unit_line(r.stdout, "nfl-week4-t70-build")
    assert "UNION_MIX_CELL_QUOTAS" not in _unit_line(_run().stdout, "nfl-week4-t70-build")
    host = (Path(__file__).resolve().parents[1] / "scripts" / "sunday_build_host.sh").read_text()
    assert '-n "${UNION_MIX_CELL_QUOTAS:-}" ]] && UNION_ARGS+=(--mix-cell-quotas "$UNION_MIX_CELL_QUOTAS")' in host
    arm = (Path(__file__).resolve().parents[1] / "scripts" / "arm_week5_saturday.sh").read_text()
    assert '\nMIX_QUOTAS="" ' in arm and "e+=(UNION_MIX_CELL_QUOTAS=$MIX_QUOTAS)" in arm


def test_the_priority_order_rides_into_the_units_and_the_week5_arm_keeps_it_off():
    """Priority-first dealing (the operator 10-07): UNION_PRIORITY_ORDER reaches the build units; the host passes
    --priority-order only with the mix; the Week-5 arm keeps PRIORITY_ORDER=0 until the screen, A3 and his yes, and unsets
    it for the house shape; check_week_runtime refuses it off the mix."""
    from pathlib import Path
    r = _run(UNION_PRIORITY_ORDER="1")
    assert "UNION_PRIORITY_ORDER=1" in _unit_line(r.stdout, "nfl-week4-t70-build")
    assert "UNION_PRIORITY_ORDER" not in _unit_line(_run().stdout, "nfl-week4-t70-build")
    root = Path(__file__).resolve().parents[1]
    host = (root / "scripts" / "sunday_build_host.sh").read_text()
    assert '[[ "${UNION_MAIN:-mean}" == "mix" && "${UNION_PRIORITY_ORDER:-0}" == "1" ]] && UNION_ARGS+=(--priority-order)' in host
    arm = (root / "scripts" / "arm_week5_saturday.sh").read_text()
    assert "\nPRIORITY_ORDER=0 " in arm and "UNION_PRIORITY_ORDER=$PRIORITY_ORDER" in arm and "-u UNION_PRIORITY_ORDER" in arm
    chk = (root / "scripts" / "check_week_runtime.py").read_text()
    assert 'os.environ.get("UNION_PRIORITY_ORDER", "")' in chk and "the priority-first deal" in chk


def test_the_t70_second_dk_pull_and_the_week5_arm_count():
    """O-59 (the operator 10-08: "Add a 10:47 pull"): T70_PROJECT=1 arms a second ingest-dk unit at 10:47 CT beside the 10:33
    one, and the Week-5 arm's EXPECT_N matches the print-only unit list it counts (step 6's --check)."""
    import re
    r = _run(T70_PROJECT="1", T70_MIN_PROJ_CT="10:30")
    pull2 = _unit_line(r.stdout, "nfl-week4-t70-pull-2")
    assert "2026-10-04 10:47 America/Chicago" in pull2 and pull2.rstrip().endswith("ingest-dk")
    assert "2026-10-04 10:33 America/Chicago" in _unit_line(r.stdout, "nfl-week4-t70-pull")
    assert "t70-pull-2" not in _run().stdout                                         # off without T70_PROJECT
    arm = (Path(__file__).resolve().parents[1] / "scripts" / "arm_week5_saturday.sh").read_text()
    expect = int(re.search(r'\nSKIP="d6400"; EXPECT_N=(\d+)', arm).group(1))
    e = {k: v for k, v in os.environ.items() if not k.startswith(("D800_", "D3200_", "SKIP_", "T70_", "GCP_", "EARLY_"))}
    e.update({"EXPECT_SHA": PIN, "GCLOUD": "/bin/true", "NFL_DFS_CLI": "/bin/true", "SKIP_UNITS": "d6400",
              "D3200_LEV": "0", "D3200_BOOM": "4800", "D800_LEV": "0", "D800_BOOM": "4800", "EARLY_PROPS_CT": "04:30",
              "EARLY_PROJECT_CT": "04:45", "EARLY_SUPPLY_CT": "05:00", "T70_MIN_PROJ_CT": "10:30", "T70_PROJECT": "1"})
    out = subprocess.run(["bash", str(SCRIPT), "5"], capture_output=True, text=True, env=e)
    assert out.returncode == 0, out.stderr
    units = sorted(set(re.findall(r"nfl-week5-[a-z0-9-]+", out.stdout + out.stderr)) - {"nfl-week5-d6400-build"})
    assert len(units) == expect == 13, units


def test_the_player_cap_rides_into_the_units_and_the_week5_arm_refuses_it_unset():
    """His 10-09 trial (HANDOFF a391f2e5): UNION_MAIN_CAP reaches the build units, the host passes --main-cap-share, and the
    Week-5 arm sets it explicitly (0.5 from study 89's READ: his rule said DO NOT ARM 0.35) and refuses to arm while it is
    empty."""
    from pathlib import Path
    r = _run(UNION_MAIN_CAP="0.35")
    assert "UNION_MAIN_CAP=0.35" in _unit_line(r.stdout, "nfl-week4-t70-build")
    root = Path(__file__).resolve().parents[1] / "scripts"
    host = (root / "sunday_build_host.sh").read_text()
    assert '[[ -n "${UNION_MAIN_CAP:-}" ]] && UNION_ARGS+=(--main-cap-share "$UNION_MAIN_CAP")' in host
    arm = (root / "arm_week5_saturday.sh").read_text()
    import re
    assert re.search(r'\nMAIN_CAP="(0\.35|0\.5)" ', arm) and "UNION_MAIN_CAP=$MAIN_CAP" in arm
    assert '|| stop "MAIN_CAP=$MAIN_CAP with OWN_CAP_DELTA=$OWN_CAP_DELTA: (0.5, 0) = the book as before' in arm   # 10-09: paired with the ownership cap


def test_his_package_rides_into_the_units_and_the_week5_arm_pairs_the_two_caps():
    """His 10-09 package (HANDOFF 5380e0e7): UNION_MAIN_OWN_CAP_DELTA reaches the build units; the host captures FP's
    ownership for it even at tilt 0, passes the three flags, and on no file builds the book as before (0.5, in place) with an
    ALERT; the builder's own refusal line becomes the same ALERT; the arm allows only (0.5, 0) or (0.35, 15) with the mix."""
    from pathlib import Path
    r = _run(UNION_MAIN_OWN_CAP_DELTA="15")
    assert "UNION_MAIN_OWN_CAP_DELTA=15" in _unit_line(r.stdout, "nfl-week4-t70-build")
    root = Path(__file__).resolve().parents[1] / "scripts"
    host = (root / "sunday_build_host.sh").read_text()
    block = host[host.index("  OWN_CAP_SRC=\"\"; OWN_CAP_ON=0"):host.index("  # Study 48b's winner-likeness order")]
    assert 'if [[ "${UNION_MAIN:-mean}" == "mix" && "${UNION_MAIN_OWN_CAP_DELTA:-0}" != "0" ]]; then' in block
    assert "nfl_dfs.ops.fantasy_points_ownership collect" in block and "scripts/ownership_fp.py" in block
    assert ('UNION_ARGS+=(--main-own-cap-delta "$UNION_MAIN_OWN_CAP_DELTA" --main-own-cap-source "$OWN_CAP_SRC"' in block
            and '--main-own-cap-fallback-share "${UNION_MAIN_OWN_CAP_FALLBACK_SHARE:-0.5}")' in block)
    assert 'set_cap_share "${UNION_MAIN_OWN_CAP_FALLBACK_SHARE:-0.5}"' in block and 'own_cap_alert "${OWN_CAP_WHY:-no FP ownership file}"' in block
    assert "grep -q 'OWN CAP NOT APPLIED' \"$OUT/union-$RUN_TAG.txt\"" in host
    assert 'cp "$OUT/ALERT-own-cap-not-applied-$RUN_TAG.txt" "$UNION_DIR/own_cap_not_applied.txt"' in host
    arm = (root / "arm_week5_saturday.sh").read_text()
    import re
    pair = re.search(r'\nMAIN_CAP="(0\.35|0\.5)" .*?\nOWN_CAP_DELTA=(0|10|15) ', arm, re.S)
    assert pair and pair.groups() in (("0.5", "0"), ("0.35", "15"), ("0.35", "10")), "the arm carries his package whole, or today's book"
    assert "UNION_MAIN_OWN_CAP_DELTA=$OWN_CAP_DELTA" in arm
    assert ('[[ ( "$MAIN_CAP" == 0.5 && "$OWN_CAP_DELTA" == 0 ) || ( "$MAIN_CAP" == 0.35 && ( "$OWN_CAP_DELTA" == 15 || "$OWN_CAP_DELTA" == 10 ) '
            '&& "$SHAPE" == mixt ) ]]' in arm)


def test_his_test2_row_rules_ride_into_the_units_only_with_the_package():
    """His 10-09 test 2 (HANDOFF 2ab54e30): UNION_MIX_ROW_RULES reaches the units; the host passes the three flags only when
    the ownership cap is on (its file), else an ALERT; the builder's refusal line becomes the same ALERT; the arm keeps it off
    ("") unless study 91 passes his rule, and then only with the package."""
    from pathlib import Path
    r = _run(UNION_MIX_ROW_RULES="te1_low1")
    assert "UNION_MIX_ROW_RULES=te1_low1" in _unit_line(r.stdout, "nfl-week4-t70-build")
    root = Path(__file__).resolve().parents[1] / "scripts"
    host = (root / "sunday_build_host.sh").read_text()
    assert 'if [[ "${UNION_MAIN:-mean}" == "mix" && "${UNION_MIX_ROW_RULES:-}" == "te1_low1" ]]; then' in host
    assert "UNION_ARGS+=(--mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3)" in host
    assert 'row_rules_alert "the ownership cap is not on for this run (no FP ownership file)"' in host
    assert "grep -q 'ROW RULES NOT APPLIED' \"$OUT/union-$RUN_TAG.txt\"" in host
    arm = (root / "arm_week5_saturday.sh").read_text()
    assert '\nROW_RULES="" ' in arm or '\nROW_RULES="te1_low1" ' in arm
    assert "UNION_MIX_ROW_RULES=$ROW_RULES" in arm
    assert '[[ -z "$ROW_RULES" || ( "$ROW_RULES" == te1_low1 && ( "$OWN_CAP_DELTA" == 15 || "$OWN_CAP_DELTA" == 10 ) ) ]]' in arm


def test_his_onecatch_rides_into_the_units_only_on_top_of_the_row_rules():
    """His 10-09 decision (HANDOFF 90e8470c, study 93's ONECATCH): UNION_MIX_ONE_CATCHER_ALL reaches the units; the host passes
    the bare flag only when the row rules were passed (ROW_RULES_ON), else an ALERT; the builder's refusal line and a house
    fallback raise the same ALERT; the arm keeps it 0 unless every check passes, and 1 only with te1_low1 and the package."""
    from pathlib import Path
    r = _run(UNION_MIX_ONE_CATCHER_ALL="1")
    assert "UNION_MIX_ONE_CATCHER_ALL=1" in _unit_line(r.stdout, "nfl-week4-t70-build")
    root = Path(__file__).resolve().parents[1] / "scripts"
    host = (root / "sunday_build_host.sh").read_text()
    assert "UNION_ARGS+=(--mix-max-te 1 --mix-max-low-own 1 --mix-low-own-pct 3); ROW_RULES_ON=1" in host
    assert 'if [[ "${UNION_MAIN:-mean}" == "mix" && "${UNION_MIX_ONE_CATCHER_ALL:-0}" == "1" ]]; then\n    if (( ROW_RULES_ON )); then\n      UNION_ARGS+=(--mix-one-catcher-all)' in host
    assert 'one_catcher_alert "the row rules are not on for this run' in host
    assert "grep -q 'ONE CATCHER NOT APPLIED' \"$OUT/union-$RUN_TAG.txt\"" in host
    assert '"$UNION_MAIN_EFFECTIVE" != "mix" ]]; then\n    one_catcher_alert "the MIX main was refused' in host
    assert '"$UNION_DIR/one_catcher_not_applied.txt"' in host
    # the ALERT block sits after the row-rules block (ROW_RULES_ON is set first) and before the union runs
    assert host.index("ROW_RULES_ON=1") < host.index("UNION_ARGS+=(--mix-one-catcher-all)") < host.index('UNION_RC=0; run_union "${UNION_ARGS[@]}"')
    arm = (root / "arm_week5_saturday.sh").read_text()
    assert "\nONE_CATCHER_ALL=0 " in arm or "\nONE_CATCHER_ALL=1 " in arm
    assert "UNION_MIX_ONE_CATCHER_ALL=$ONE_CATCHER_ALL" in arm
    assert ('[[ "$ONE_CATCHER_ALL" == 0 || ( "$ONE_CATCHER_ALL" == 1 && "$ROW_RULES" == te1_low1 && ( "$OWN_CAP_DELTA" == 15 || "$OWN_CAP_DELTA" == 10 ) '
            '&& "$SHAPE" == mixt && "$MIX_FILL" == rr \\\n      && "$MIX_COVER" == 0 && "$MIX_RS" == 0 && -z "$BRING_BACK_TOP_WR" '
            '&& "$WINNER_SELECT" == 0 ) ]]') in arm


def test_his_rbmate_rides_into_the_units_only_on_top_of_onecatch():
    """His 10-09 decision (HANDOFF ad00da5c, study 94's RBMATE4, read with ONECATCH in study 96): UNION_MIX_RB_MATE_C reaches
    the units; the host passes --mix-rb-mate-c 4 only when ONECATCH was passed (ONE_CATCHER_ON), else an ALERT; the builder's
    refusal line and a house fallback raise the same ALERT; the arm keeps it 0 unless every check passes, 4 only with ONECATCH."""
    from pathlib import Path
    r = _run(UNION_MIX_RB_MATE_C="4")
    assert "UNION_MIX_RB_MATE_C=4" in _unit_line(r.stdout, "nfl-week4-t70-build")
    root = Path(__file__).resolve().parents[1] / "scripts"
    host = (root / "sunday_build_host.sh").read_text()
    assert "UNION_ARGS+=(--mix-one-catcher-all); ONE_CATCHER_ON=1" in host
    assert ('if [[ "${UNION_MAIN:-mean}" == "mix" && "${UNION_MIX_RB_MATE_C:-0}" != "0" ]]; then\n'
            '    if (( ONE_CATCHER_ON )) && [[ "${UNION_MIX_RB_MATE_C}" == "4" ]]; then\n      UNION_ARGS+=(--mix-rb-mate-c 4)') in host
    assert 'rb_mate_alert "ONECATCH is not on for this run' in host
    assert "grep -q 'RB MATE NOT APPLIED' \"$OUT/union-$RUN_TAG.txt\"" in host
    assert '"$UNION_MAIN_EFFECTIVE" != "mix" ]]; then\n    rb_mate_alert "the MIX main was refused' in host
    assert '"$UNION_DIR/rb_mate_not_applied.txt"' in host
    assert host.index("ONE_CATCHER_ON=1") < host.index("UNION_ARGS+=(--mix-rb-mate-c 4)") < host.index('UNION_RC=0; run_union "${UNION_ARGS[@]}"')
    arm = (root / "arm_week5_saturday.sh").read_text()
    assert "\nRB_MATE_C=0 " in arm or "\nRB_MATE_C=4 " in arm
    assert "UNION_MIX_RB_MATE_C=$RB_MATE_C" in arm
    assert '[[ "$RB_MATE_C" == 0 || ( "$RB_MATE_C" == 4 && "$ONE_CATCHER_ALL" == 1 ) ]]' in arm
