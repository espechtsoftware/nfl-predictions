import json
import os
import sys
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
ENV_SCRIPT = ROOT / "scripts" / "week_env.sh"
LIVE_REPAIR_SHA = "2dc116ce95647a776ba9c36cf194f44d022d03a4"
# The Week-3 pin (2026-09-22): nfl2 9b341d77 -> parent 69f98a75 (Doubtful inactive set) -> which
# descends from 2dc116ce (the reviewed Week-2 live-game input repair). Verified with
# `git merge-base --is-ancestor 2dc116ce 9b341d77` when the pin moved.
# 2026-09-25: advanced to 65305f5a (parent 9b341d77, one commit: LIVE_FLEX_LATEST, default off in nfl2).
# 2026-09-29: advanced to 826d8de6 for Week 4 (the two-track branch + the DK->nflverse team alias); it descends from
# 65305f5a and 2dc116ce.
LIVE_PIN_SHA = "32cdb6112beb68ce5171423a8e12bf684256bbf2"


def test_week3_default_keeps_the_reviewed_live_game_input_repair():
    source = ENV_SCRIPT.read_text()
    assert f"NFL2_EXPECT_SHA:-{LIVE_PIN_SHA}" in source, "EXPECT_SHA default is not the reviewed live pin"
    assert "week4-live-center" in source and "week3-live-center}}" not in source
    assert LIVE_REPAIR_SHA[:8] in source, "the pin's lineage to the Week-2 repair is no longer documented"
    assert "e7255e98bf87297452befb61fb508ad4b368b59f" not in source


def test_week3_default_puts_the_latest_starter_in_flex():
    source = ENV_SCRIPT.read_text()
    assert "export LIVE_FLEX_LATEST=${LIVE_FLEX_LATEST:-1}" in source


def test_week3_default_turns_the_per_game_cap_on():
    source = ENV_SCRIPT.read_text()
    assert "export MAX_PER_GAME=${MAX_PER_GAME:-4}" in source


def test_missing_contests_file_fails_with_an_actionable_message(tmp_path):
    missing = tmp_path / "contests.json"
    env = os.environ.copy()
    env.update({
        "GROUP": "153769",
        "SEASON": "2026",
        "OUT": str(tmp_path / "out"),
        "CONTESTS_JSON": str(missing),
        "PROD_PY": "/bin/false",
    })
    result = subprocess.run(
        ["bash", "-c", f"source {ENV_SCRIPT}; week_env 3"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert f"contests file missing: {missing}" in result.stderr


def test_two_track_contests_split_mean_rows_and_the_tail_sleeve(tmp_path):
    """Operator 2026-09-27: BOOK_ENTRIES is the mean-track row count the builder receives; TAIL_SLEEVE the Millionaire
    rows appended after them. Under head with 19 one-entry satellites + a 20-entry supersat + a tail Millionaire seat:
    mean rows = 4 head + 15 unique + 16 unique = 35 (no 90-row floor since 2026-09-28); sleeve = 1."""
    contests = tmp_path / "contests.json"
    cs = [{"name": "sat20", "contest_id": str(1000 + i), "entries": 1, "keep": 1} for i in range(19)]
    cs += [{"name": "supersat", "contest_id": "2000", "entries": 20, "keep": 20},
           {"name": "milly20", "contest_id": "3000", "entries": 1, "keep": 1, "track": "tail"}]
    contests.write_text(json.dumps(cs))
    env = os.environ.copy()
    env.update({"GROUP": "153769", "SEASON": "2026", "OUT": str(tmp_path / "out"), "CONTESTS_JSON": str(contests),
                "ENTER_LAYOUT": "head", "PROD_PY": sys.executable, "PROD": str(ROOT)})
    r = subprocess.run(["bash", "-c", f"source {ENV_SCRIPT}; week_env 3 >/dev/null && echo $BOOK_ENTRIES $TAIL_SLEEVE $LIVE_SELECTOR $LIVE_MIN_PROJ $MEAN_OWN_TILT $MEAN_DST_CAP $ENTER_FLAG_LATE_Q_ONLY $T70_ACTIVE_Q $T70_VACATED_BUMP $TAIL_SLEEVE_SELECTOR $CLASS_SLEEVE_EVERY ${{UNION_SATURDAY_RUN:-none}} $UNION_SAT_DOSE $UNION_PMO $UNION_PMO_CAP $UNION_MAIN $CASH_SHADOW $CASH_SHADOW_N"],
                       env=env, text=True, capture_output=True, check=False)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["35", "1", "mean", "1.0", "0", "0.25", "1", "1", "1", "mean", "2", "none", "2560/10240,1280/5120", "0", "0.5", "pmo_x50", "1", "20"]   # reviewer 2026-09-28 10:30: mean everywhere, class sleeve 2, class withdrawn   # operator decisions 2026-09-28 as defaults


def test_entries_watcher_runs_through_the_afternoon_swaps():
    env = {k: v for k, v in os.environ.items() if k not in ("ENTRIES_END_CT", "ENTRIES_END_UTC")}
    run = lambda e: subprocess.run(["bash", "-c", f"source {ENV_SCRIPT} && week_env 4 >/dev/null 2>&1; echo $ENTRIES_END_UTC"],
                                   capture_output=True, text=True, env=e).stdout.strip()
    assert run(env) == "2026-10-04 20:20:00+00:00"                     # 15:20 CT, after the ~14:40 late swap
    assert run({**env, "ENTRIES_END_CT": "11:58"}) == "2026-10-04 16:58:00+00:00"
    watcher = (ROOT / "scripts" / "sunday_watch_dk_entries.sh").read_text()
    assert "1658" not in watcher and '"$END_EPOCH"' in watcher


def test_week4_union_main_dst_cap_and_sleeve_source():
    source = ENV_SCRIPT.read_text()
    assert "export UNION_MAIN=${UNION_MAIN:-pmo_x50}" in source
    assert "UNION_MAIN_DST_CAP=${UNION_MAIN_DST_CAP-0.25}" in source           # operator 2026-09-28
    assert "UNION_SLEEVE_INCLUDES_MAIN=${UNION_SLEEVE_INCLUDES_MAIN-1}" in source


def test_main_book_cap_is_a_setting_that_reaches_the_union_step():
    assert "export UNION_MAIN_CAP=${UNION_MAIN_CAP:-0.5}" in ENV_SCRIPT.read_text()   # as entered; L17: looser HARMFUL
    host = (ROOT / "scripts" / "sunday_build_host.sh").read_text()
    assert '--main-cap-share "$UNION_MAIN_CAP"' in host
    assert "int(0.5 * a.entries)" not in (ROOT / "scripts" / "union_reselect.py").read_text()


def test_sleeve_cap_is_off_unless_set():
    assert "export UNION_SLEEVE_CAP=${UNION_SLEEVE_CAP-0.5}" in ENV_SCRIPT.read_text()        # operator 09-30 after L19; empty = off
    assert '--sleeve-cap-share "$UNION_SLEEVE_CAP"' in (ROOT / "scripts" / "sunday_build_host.sh").read_text()


def test_week_window_starts_saturday_midnight_central():
    env = {k: v for k, v in os.environ.items() if k != "WEEK_WINDOW_START_UTC"}
    r = subprocess.run(["bash", "-c", f"source {ENV_SCRIPT} && week_env 4 154078 >/dev/null 2>&1; echo $SATURDAY $WEEK_WINDOW_START_UTC"],
                       capture_output=True, text=True, env=env)
    assert r.stdout.split() == ["2026-10-03", "2026-10-03T05:00:00"]      # Saturday 00:00 CDT = 05:00Z


def test_ownership_term_is_off_unless_armed_and_the_chain_falls_back_named():
    src = ENV_SCRIPT.read_text()
    assert "export UNION_MAIN_OWN_TILT=${UNION_MAIN_OWN_TILT:-0}" in src                     # off until the arm line sets 0.20
    assert "OWNERSHIP_LAG=${OWNERSHIP_LAG:-$OUT/ownership_lag.csv}" in src
    host = (ROOT / "scripts" / "sunday_build_host.sh").read_text()
    assert 'BLEND_SRC="$OUT/ownership_blend-$RUN_TAG.csv"' in host
    assert '[[ -n "$OWN_SRC" ]] && UNION_ARGS+=(--main-own-tilt "$OWN_TILT" --main-own-source "$OWN_SRC")' in host
    assert "grep -q 'OWN TERM REFUSED'" in host and "own_term_refused.txt" in host
    assert 'strip_own "${UNION_ARGS[@]}"; MEAN_ARGS_U=("${OUT_ARGS[@]}")' in host         # the mean fallback never carries the term
    assert "timeout 120" in host                                                           # a hung capture cannot stall the union


def test_strip_own_drops_exactly_the_terms_flags():
    host = (ROOT / "scripts" / "sunday_build_host.sh").read_text()
    start = host.index("  strip_own() {"); end = host.index("done; }", start) + len("done; }")
    fn = host[start:end]
    script = fn + '\nstrip_own --main pmo_x50 --main-own-tilt 0.2 --entries 36 --main-own-source "/x y/b.csv" --tail-sleeve 85\nprintf "%s|" "${OUT_ARGS[@]}"'
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout
    assert out == "--main|pmo_x50|--entries|36|--tail-sleeve|85|"


def test_ownership_fallback_chain_tabpfn_blend_lag_none_is_loud(tmp_path):
    """Operator 2026-09-30 ("falls back loudly") and 2026-10-01 (cracks audit A): TabPFN -> blend -> Saturday's lag file
    at 0.10 -> no term. Run own_banner/own_use_lag for real: a passing lag file is used at the lag tilt; a collapsed one
    leaves no term; every step writes the banner and the marker line."""
    src = ENV_SCRIPT.read_text()
    assert "UNION_MAIN_OWN_PREDICTOR=${UNION_MAIN_OWN_PREDICTOR:-blend}" in src
    assert "UNION_MAIN_OWN_LAG_TILT=${UNION_MAIN_OWN_LAG_TILT:-0.10}" in src
    host = (ROOT / "scripts" / "sunday_build_host.sh").read_text()
    assert host.index("scripts/ownership_blend.py") < host.index('"${UNION_MAIN_OWN_PREDICTOR:-blend}" == "tabpfn"')
    start = host.index("  own_banner() {"); end = host.index("  if [[ ( \"${UNION_MAIN:-mean}\" == \"pmo_x50\"", start)   # the term block (pmo_x50 or mix)
    fns = host[start:end]
    good = tmp_path / "lag_good.csv"; good.write_text("display_name,pred_own\n" + "".join(f"P{i},{20.0 if i < 10 else 2.0}\n" for i in range(150)))
    bad = tmp_path / "lag_bad.csv"; bad.write_text("display_name,pred_own\n" + "".join(f"P{i},1.0\n" for i in range(150)))
    def run(lag):
        script = (f'OUT={tmp_path}; RUN_TAG=t70x; PROD={ROOT}; PROD_PY={sys.executable}; OWNERSHIP_LAG={lag}; '
                  'OWN_SRC=""; OWN_TILT=0.20\n' + fns + 'own_use_lag; own_banner BLEND "no valid LineStar capture"; echo "[$OWN_SRC|$OWN_TILT]"\n')
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    r = run(good)
    assert f"[{good}|0.10]" in r.stdout and "!!! OWNERSHIP BLEND FAILED for t70x: no valid LineStar capture -- FALLING BACK TO lag_good.csv at tilt 0.10" in r.stdout
    r = run(bad)
    assert "[|0]" in r.stdout and "FALLING BACK TO none: NO TERM" in r.stdout
    marker = (tmp_path / "own_term_fallback-t70x.txt").read_text().splitlines()
    assert len(marker) == 2 and "fallback lag_good.csv at tilt 0.10" in marker[0] and "fallback none: NO TERM" in marker[1]
    assert "own_use_lag; else OWN_SRC=\"\"; OWN_TILT=\"0\"; fi" in host                              # union refusal: lag, then none

def test_week4_small_contest_overlap_limit_is_on_by_default_and_can_be_turned_off(tmp_path):
    src = ENV_SCRIPT.read_text()
    assert "export ENTER_SMALL_MAX_SHARED=${ENTER_SMALL_MAX_SHARED-5}" in src          # operator 2026-09-30: Week 4
    env = {k: v for k, v in os.environ.items() if k != "ENTER_SMALL_MAX_SHARED"}
    # Hermetic (2026-10-04): book sizes given, so week_env never needs the host's Week-4 contests.json. Without this the
    # test passed only on the laptop and failed in the Cloud Build live lane (week_env returned before the export).
    env.update({"BOOK_ENTRIES": "90", "TAIL_SLEEVE": "0", "PROD": str(ROOT), "PROD_PY": sys.executable,
                "OUT": str(tmp_path / "out"), "CONTESTS_JSON": str(tmp_path / "absent-contests.json")})
    run = lambda e: subprocess.run(["bash", "-c", f"source {ENV_SCRIPT}; week_env 4 154078 >/dev/null 2>&1; echo [$ENTER_SMALL_MAX_SHARED]"],
                                   capture_output=True, text=True, env=e).stdout.strip()
    assert run(env) == "[5]" and run({**env, "ENTER_SMALL_MAX_SHARED": ""}) == "[]"


def test_build_host_layout_precheck_counts_the_tail_sleeve(tmp_path):
    """Week-4 smoke 2026-10-01: the pre-build check compared rows_needed (mean + sleeve) with BOOK_ENTRIES (mean only)
    and refused every two-track build. Run the check itself on a two-track plan: 6 main rows + 1 sleeve row."""
    host = (ROOT / "scripts" / "sunday_build_host.sh").read_text()
    start = host.index('"$PROD_PY" - "$CONTESTS_JSON" <<\'PYEOF\' || exit 2'); body = host.index("\n", start) + 1
    code = host[body:host.index("\nPYEOF", body)]
    plan = [{"name": "a", "contest_id": "1", "entries": 3, "keep": 3, "track": "mean"},
            {"name": "b", "contest_id": "2", "entries": 3, "keep": 3, "track": "mean"},
            {"name": "m", "contest_id": "3", "entries": 1, "keep": 1, "track": "tail", "priority": 1}]
    cj = tmp_path / "contests.json"; cj.write_text(json.dumps(plan))
    sys.path.insert(0, str(ROOT / "src"))
    from nfl_dfs.inference.enter_layout import rows_needed, sleeve_size
    need, tail = rows_needed(plan, "head"), sleeve_size(plan, "head")
    base = {**os.environ, "PROD": str(ROOT), "ENTER_LAYOUT": "head", "BOOK_ENTRIES": str(need - tail)}
    run = lambda env: subprocess.run([sys.executable, "-c", code, str(cj)], capture_output=True, text=True, env=env)
    assert run({**base, "TAIL_SLEEVE": str(tail)}).returncode == 0                       # mean + sleeve covers the plan
    r = run({**base, "TAIL_SLEEVE": "0"})
    assert r.returncode != 0 and "distinct lineups but the book holds" in r.stderr       # the guard still bites


def test_exposure_cap_books_count_the_tail_sleeve():
    """Week-4 smoke 2026-10-01: both exposure_cap_book calls passed --entries $BOOK_ENTRIES (mean rows) and failed on the
    tail contests' ranks ("reads rank 106 but the book is 105"); the same defect class as the contests pre-check."""
    host = (ROOT / "scripts" / "sunday_build_host.sh").read_text()
    calls = [l for l in host.splitlines() if "--layout" in l and "exposure" not in l and "--entries" in l and "CONTESTS_JSON" in l]
    cap_block = host[host.index("# 6. exposure caps"):host.index("# 6b.") + 2000]
    assert cap_block.count('--entries "$((BOOK_ENTRIES + ${TAIL_SLEEVE:-0}))"') == 2
    assert '--entries "$BOOK_ENTRIES" --layout' not in cap_block


def test_week4_overlap_ceiling_is_ten_by_default_after_the_smoke():
    assert "export ENTER_SMALL_OVERLAP_MAX_ENTRIES=${ENTER_SMALL_OVERLAP_MAX_ENTRIES-10}" in ENV_SCRIPT.read_text()


def test_mix_spares_default_reaches_the_union_and_the_units():
    """reviewer 2026-10-06 (blocking): with a mix main, 15 spare rows (study 24's sizing) are the Sunday replacement
    step's in-shape supply; the setting reaches the union and rides every armed unit."""
    assert "export UNION_MIX_SPARES=${UNION_MIX_SPARES-15}" in ENV_SCRIPT.read_text()
    assert '--mix-spares "${UNION_MIX_SPARES:-15}"' in (ROOT / "scripts" / "sunday_build_host.sh").read_text()
    assert " UNION_MIX_SPARES " in (ROOT / "scripts" / "arm_week_timers.sh").read_text()


def test_linestar_is_retired_from_the_build_and_the_arming_steps():
    """Operator 10-04 / the 10-06 revision check: no LineStar capture per union (it cost up to 120 s inside the T-70
    window) or at Saturday's arming; the ownership chain is FP -> LAG -> none."""
    host = (ROOT / "scripts" / "sunday_build_host.sh").read_text()
    arm = (ROOT / "scripts" / "arm_week_timers.sh").read_text()
    assert "linestar_ownership_capture.py" not in host and "linestar_ownership_capture.py" not in arm
    assert "LineStar RETIRED 2026-10-06" in host
