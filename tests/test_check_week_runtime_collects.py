"""O-20: the week-runtime preflight reports EVERY failure, not just the first.

The 10-02 dry run stopped on the missing Saturday sets file and never reached the stale UNION_SAT_DOSE check, which then
stopped Saturday's arm at 10:13 (14 minutes before the 10:30 D12800). These tests rebuild that shape in tmp_path: a
healthy sandbox (git-initialised stand-ins for the production checkout and the pinned lab clone) passes, and the same
sandbox with the two 10-02 failures prints BOTH and exits 2 once.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_week_runtime.py"
PREFIX = "WEEK RUNTIME PREFLIGHT FAILED: "
HELPERS = ("ordering_shadows.py", "hybrid30.py", "vet_book.py", "player_score.py", "book_sheet.py",
           "fill_dk_entries.py", "qb_classify.py", "qb_flags.py", "vet_replace_v4.py", "verify_enter_bundle.py")


def _git_repo(path: Path, files: dict[str, str]) -> str:
    path.mkdir(parents=True)
    for rel, text in files.items():
        (path / rel).parent.mkdir(parents=True, exist_ok=True)
        (path / rel).write_text(text)
    g = ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(g[:3] + ["init", "-q"], check=True)
    subprocess.run(g + ["add", "-A"], check=True)
    subprocess.run(g + ["commit", "-q", "-m", "fixture"], check=True)
    return subprocess.run(g[:3] + ["rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()


def _healthy(tmp_path: Path) -> dict[str, str]:
    live_week = '\n'.join(['p.add_argument("--min-proj")', 'p.add_argument("--tail-sleeve")', 'p.add_argument("--tail-line")',
                           'p.add_argument("--tail-sleeve-selector", choices=["emax", "mean"])',
                           'p.add_argument("--selector", choices=["dual_emax", "mean", "class"])',
                           'p.add_argument("--mean-dst-cap")', ''])
    sha = _git_repo(tmp_path / "clone", {"scripts/live_week.py": live_week,
                                         "src/nfl2/two_track.py": "def select_top_mean(dst_of=None): pass\n"})
    _git_repo(tmp_path / "prod", {"scripts/sunday_build_host.sh": "#!/usr/bin/env bash\n"})
    tools = tmp_path / "tools"; tools.mkdir()
    for name in HELPERS:
        (tools / name).write_text("")
    contests = tmp_path / "out" / "contests.json"
    contests.parent.mkdir()
    contests.write_text(json.dumps([{"name": "se", "contest_id": "123", "entries": 20, "keep": 5}]))
    sat_run = tmp_path / "satrun"; sat_run.mkdir(); (sat_run / "receipt.json").write_text("{}")
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL")}
    env.update({
        "HOME": str(tmp_path), "PYTHONPATH": str(ROOT / "src"),
        "SEASON": "2026", "WEEK": "5", "WEEKDIR": "w05", "SUNDAY": "2026-10-11", "GROUP": "999999",
        "OUT": str(contests.parent), "CLONE": str(tmp_path / "clone"), "PROD": str(tmp_path / "prod"),
        "PROD_PY": sys.executable, "LAB_PY": sys.executable, "TOOLS": str(tools), "CONTESTS_JSON": str(contests),
        "LIVE_DIR": str(tmp_path / "live"), "EXPECT_SHA": sha, "BOOK_ENTRIES": "90", "TAIL_SLEEVE": "0",
        "ENTER_LAYOUT": "sequential", "LIVE_SELECTOR": "mean", "UNION_SATURDAY_RUN": str(sat_run),
        "UNION_SAT_DOSE": "2560/10240,1280/5120",
    })
    return env


def _run(env, role="build"):
    return subprocess.run([sys.executable, str(SCRIPT), "--role", role], env=env, capture_output=True, text=True, timeout=120)


def _failures(r):
    return [l[len(PREFIX):] for l in r.stderr.splitlines() if l.startswith(PREFIX)]


def test_the_healthy_sandbox_passes(tmp_path):
    r = _run(_healthy(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "week runtime preflight ok: role=build" in r.stdout
    assert _failures(r) == []


def test_two_independent_failures_are_both_reported(tmp_path):
    """The 10-02 shape: the sets file is missing AND UNION_SAT_DOSE is malformed. Both lines print; exit 2 once."""
    env = _healthy(tmp_path)
    env.update(ENTER_ORDER="fewest-low", OWNERSHIP_SETS=str(tmp_path / "out" / "ownership_sets.csv"),
               UNION_SAT_DOSE="2560-10240")
    r = _run(env)
    assert r.returncode == 2
    found = _failures(r)
    assert any(f.startswith("UNION_SAT_DOSE='2560-10240' must be lev/boom[,lev/boom...]") for f in found), found
    assert any(f.startswith("ENTER_ORDER=fewest-low needs the Saturday sets file") for f in found), found
    assert found[-1] == "2 check(s) failed (each listed above)"
    assert "preflight ok" not in r.stdout


def test_failures_in_different_sections_are_all_reported(tmp_path):
    """An early identity failure no longer hides a contest failure or the watchers' chosen-dose check."""
    env = _healthy(tmp_path)
    env["EXPECT_SHA"] = "0" * 40
    Path(env["CONTESTS_JSON"]).write_text(json.dumps([{"name": "se", "contest_id": "REPLACE", "entries": 20, "keep": 5}]))
    env["CHOSEN_FILE"] = str(tmp_path / "out" / "chosen-dose.env")
    r = _run(env, role="watchers")
    assert r.returncode == 2
    found = _failures(r)
    assert any(f.startswith("live clone identity ") for f in found), found
    assert any(f.startswith("contest template marker remains") for f in found), found
    assert any(f.startswith("contest id is not numeric") for f in found), found
    assert any(f.startswith("chosen dose file missing") for f in found), found
    assert found[-1] == f"{len(found) - 1} check(s) failed (each listed above)"


def test_a_missing_prerequisite_skips_its_dependants_without_crashing(tmp_path):
    env = _healthy(tmp_path)
    del env["CLONE"]
    Path(env["CONTESTS_JSON"]).unlink()
    r = _run(env)
    assert r.returncode == 2 and "Traceback" not in r.stderr, r.stderr
    found = _failures(r)
    assert found[0] == "missing environment: CLONE"
    assert any(f.startswith("contest file missing") for f in found), found


def test_union_main_mix_needs_a_clone_whose_optimize_takes_the_shape_options(tmp_path):
    """--main mix (study 18) solves with optimize(second_game_pair=, qb_game_max=): a clone without them must fail at
    arming, never with a TypeError at the Sunday solve. Checked by capability in the clone's lineup.py."""
    env = _healthy(tmp_path); env["UNION_MAIN"] = "mix"; env["UNION_MIX_PORTFOLIO"] = "ws"
    fails = _failures(_run(env))
    assert any("UNION_MAIN=mix needs the pinned lab clone's optimize() to take second_game_pair and qb_game_max" in f for f in fails)
    clone = Path(env["CLONE"])
    (clone / "src" / "nfl2" / "core").mkdir(parents=True)
    (clone / "src" / "nfl2" / "core" / "lineup.py").write_text(
        "def optimize(pool, second_game_pair=None, qb_game_max=None): pass\ndef _apply_game_shape(): pass\n")
    g = ["git", "-C", str(clone), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(g + ["add", "-A"], check=True); subprocess.run(g + ["commit", "-q", "-m", "re-pin"], check=True)
    env["EXPECT_SHA"] = subprocess.run(g[:3] + ["rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    assert not any("UNION_MAIN" in f for f in _failures(_run(env)))
    env["UNION_MAIN"] = "bogus"
    assert any("must be mean, pmo_x50 or mix" in f for f in _failures(_run(env)))


def test_union_mix_portfolio_must_be_mix_or_ws(tmp_path):
    env = _healthy(tmp_path); env["UNION_MIX_PORTFOLIO"] = "ws"
    assert not any("UNION_MIX_PORTFOLIO" in f for f in _failures(_run(env)))
    env["UNION_MIX_PORTFOLIO"] = "thesis"
    assert any("UNION_MIX_PORTFOLIO='thesis' must be mix or ws" in f for f in _failures(_run(env)))
    env.pop("UNION_MIX_PORTFOLIO"); env["UNION_MAIN"] = "mix"        # reviewer 10-05: no silent default arm
    assert any("UNION_MAIN=mix needs UNION_MIX_PORTFOLIO=mix|ws" in f for f in _failures(_run(env)))


def test_union_mix_spares_must_be_0_to_50_and_not_0_with_a_mix_main(tmp_path):
    env = _healthy(tmp_path); env["UNION_MIX_SPARES"] = "15"
    assert not any("UNION_MIX_SPARES" in f for f in _failures(_run(env)))
    env["UNION_MIX_SPARES"] = "lots"
    assert any("UNION_MIX_SPARES='lots' must be an integer 0..50" in f for f in _failures(_run(env)))
    env["UNION_MIX_SPARES"] = "0"; env["UNION_MAIN"] = "mix"; env["UNION_MIX_PORTFOLIO"] = "ws"
    assert any("UNION_MIX_SPARES=0 with UNION_MAIN=mix" in f for f in _failures(_run(env)))



def test_the_qb_cap_is_armed_only_at_the_k_it_was_calibrated_at(tmp_path):
    env = _healthy(tmp_path); env["UNION_MAIN"] = "pmo_x50"
    env["UNION_MAIN_QB_CAP_ROWS"] = "7"
    assert any("needs UNION_MAIN_QB_CAP_K" in f for f in _failures(_run(env)))
    env["UNION_MAIN_QB_CAP_K"] = "26"                                    # the sandbox book is 90 rows
    assert any("was calibrated at K 26, but BOOK_ENTRIES=90" in f for f in _failures(_run(env)))
    env["UNION_MAIN_QB_CAP_K"] = "90"
    assert not any("QB_CAP" in f for f in _failures(_run(env)))
    env.pop("UNION_MAIN_QB_CAP_ROWS")
    assert any("UNION_MAIN_QB_CAP_K is set without" in f for f in _failures(_run(env)))



def test_the_qb_cap_check_never_skips_a_missing_book_size(tmp_path):
    env = _healthy(tmp_path); env["UNION_MAIN"] = "pmo_x50"
    env["UNION_MAIN_QB_CAP_ROWS"] = "7"; env["UNION_MAIN_QB_CAP_K"] = "26"; env.pop("BOOK_ENTRIES", None)
    assert any("needs BOOK_ENTRIES" in f for f in _failures(_run(env)))


def test_union_mix_fill_must_be_group_value_or_rr_with_a_mix_main(tmp_path):
    """Study 42's switch (operator 10-06): unset is today's group fill; set, it must name a fill and ride a MIX main."""
    env = _healthy(tmp_path)
    assert not any("UNION_MIX_FILL" in f for f in _failures(_run(env)))
    env["UNION_MIX_FILL"] = "value"
    assert any("UNION_MIX_FILL='value' must be group, value or rr, with UNION_MAIN=mix" in f for f in _failures(_run(env)))
    env["UNION_MAIN"] = "mix"; env["UNION_MIX_PORTFOLIO"] = "mix"
    assert not any("UNION_MIX_FILL" in f for f in _failures(_run(env)))
    env["UNION_MIX_FILL"] = "rr"
    assert not any("UNION_MIX_FILL" in f for f in _failures(_run(env)))
    env["UNION_MIX_FILL"] = "best"
    assert any("UNION_MIX_FILL='best'" in f for f in _failures(_run(env)))


def test_union_mix_cover_games_must_be_0_to_8_with_the_mix(tmp_path):
    """Study 43's switch: 0 (or unset) is off; 1..8 needs UNION_MAIN=mix and UNION_MIX_PORTFOLIO=mix."""
    env = _healthy(tmp_path); env["UNION_MIX_COVER_GAMES"] = "0"
    assert not any("UNION_MIX_COVER_GAMES" in f for f in _failures(_run(env)))
    env["UNION_MIX_COVER_GAMES"] = "4"
    assert any("UNION_MIX_COVER_GAMES='4' must be 0..8, with UNION_MAIN=mix" in f for f in _failures(_run(env)))
    env["UNION_MAIN"] = "mix"; env["UNION_MIX_PORTFOLIO"] = "mix"
    assert not any("UNION_MIX_COVER_GAMES" in f for f in _failures(_run(env)))
    env["UNION_MIX_COVER_GAMES"] = "9"
    assert any("UNION_MIX_COVER_GAMES='9'" in f for f in _failures(_run(env)))


def test_union_mix_bring_back_top_wr_is_only_the_tested_arm(tmp_path):
    """Study 71's switch: empty (or unset) is off; only A1,B, with the MIX portfolio, the round-robin fill and none of the
    half / cover / winner order or select / priority order / whole-book term (LIVE_CB + the rule, the arm the harness read)."""
    env = _healthy(tmp_path); env["UNION_MIX_BRING_BACK_TOP_WR"] = ""
    assert not any("UNION_MIX_BRING_BACK_TOP_WR" in f for f in _failures(_run(env)))
    env["UNION_MIX_BRING_BACK_TOP_WR"] = "A1,B"
    assert any("UNION_MIX_BRING_BACK_TOP_WR='A1,B' must be empty or A1,B" in f for f in _failures(_run(env)))   # no mix
    env.update({"UNION_MAIN": "mix", "UNION_MIX_PORTFOLIO": "mix", "UNION_MIX_FILL": "rr"})
    assert not any("UNION_MIX_BRING_BACK_TOP_WR" in f for f in _failures(_run(env)))
    env["UNION_PRIORITY_ORDER"] = "1"
    assert any("UNION_MIX_BRING_BACK_TOP_WR='A1,B'" in f for f in _failures(_run(env)))
    env["UNION_PRIORITY_ORDER"] = "0"; env["UNION_MIX_BRING_BACK_TOP_WR"] = "A1"
    assert any("UNION_MIX_BRING_BACK_TOP_WR='A1'" in f for f in _failures(_run(env)))


def test_union_mix_bring_back_rows_is_only_4_with_the_rule(tmp_path):
    """Study 71b's dose: empty = every A1/B row; only 4 (TOPBB_N4, the tested decision arm), and only with the rule A1,B."""
    env = _healthy(tmp_path)
    env.update({"UNION_MAIN": "mix", "UNION_MIX_PORTFOLIO": "mix", "UNION_MIX_FILL": "rr"})
    env["UNION_MIX_BRING_BACK_TOP_WR_ROWS"] = "4"
    assert any("UNION_MIX_BRING_BACK_TOP_WR_ROWS='4'" in f for f in _failures(_run(env)))     # no rule
    env["UNION_MIX_BRING_BACK_TOP_WR"] = "A1,B"
    assert not any("UNION_MIX_BRING_BACK_TOP_WR_ROWS" in f for f in _failures(_run(env)))
    env["UNION_MIX_BRING_BACK_TOP_WR_ROWS"] = "2"
    assert any("UNION_MIX_BRING_BACK_TOP_WR_ROWS='2'" in f for f in _failures(_run(env)))
    env["UNION_MIX_BRING_BACK_TOP_WR_ROWS"] = ""
    assert not any("UNION_MIX_BRING_BACK_TOP_WR_ROWS" in f for f in _failures(_run(env)))


def test_union_mix_rs_rows_must_be_0_9_13_17_with_mix_rr_and_no_cover(tmp_path):
    """Study 46's switch: 0 (or unset) is off; 9 / 13 / 17 need the MIX portfolio, the round-robin fill and no cover."""
    env = _healthy(tmp_path); env["UNION_MIX_RS_ROWS"] = "0"
    assert not any("UNION_MIX_RS_ROWS" in f for f in _failures(_run(env)))
    env.update({"UNION_MIX_RS_ROWS": "13", "UNION_MAIN": "mix", "UNION_MIX_PORTFOLIO": "mix"})
    assert any("UNION_MIX_RS_ROWS='13' must be 0, 9, 13 or 17" in f for f in _failures(_run(env)))   # no rr
    env["UNION_MIX_FILL"] = "rr"
    assert not any("UNION_MIX_RS_ROWS" in f for f in _failures(_run(env)))
    env["UNION_MIX_COVER_GAMES"] = "4"
    assert any("UNION_MIX_RS_ROWS='13'" in f for f in _failures(_run(env)))
    env["UNION_MIX_COVER_GAMES"] = "0"; env["UNION_MIX_RS_ROWS"] = "12"
    assert any("UNION_MIX_RS_ROWS='12'" in f for f in _failures(_run(env)))


def test_union_winner_order_is_0_or_1_and_needs_the_mix(tmp_path):
    """Study 48b's switch: 0 (or unset) is off; 1 needs UNION_MAIN=mix."""
    env = _healthy(tmp_path); env["UNION_WINNER_ORDER"] = "0"
    assert not any("UNION_WINNER_ORDER" in f for f in _failures(_run(env)))
    env["UNION_WINNER_ORDER"] = "1"
    assert any("UNION_WINNER_ORDER='1' must be 0 or 1, and 1 needs UNION_MAIN=mix" in f for f in _failures(_run(env)))
    env["UNION_MAIN"] = "mix"; env["UNION_MIX_PORTFOLIO"] = "mix"
    assert not any("UNION_WINNER_ORDER" in f for f in _failures(_run(env)))
    env["UNION_WINNER_ORDER"] = "2"
    assert any("UNION_WINNER_ORDER='2'" in f for f in _failures(_run(env)))


def test_union_winner_select_needs_the_mix_spares_and_not_the_order(tmp_path):
    env = _healthy(tmp_path); env.update({"UNION_MAIN": "mix", "UNION_MIX_PORTFOLIO": "mix", "UNION_WINNER_SELECT": "1"})
    assert not any("UNION_WINNER_SELECT" in f for f in _failures(_run(env)))
    env["UNION_WINNER_ORDER"] = "1"
    assert any("UNION_WINNER_SELECT='1' must be 0 or 1; 1 needs UNION_MAIN=mix with spares and UNION_WINNER_ORDER off" in f
               for f in _failures(_run(env)))


def test_the_term_block_needs_the_mix_rr_and_a_pinned_file(tmp_path):
    """The prior-top term block (the operator 10-07): rows in 1..K-1, the mix with rr, nothing it is refused with, and the
    term file present with its sha pinned."""
    import hashlib
    f = tmp_path / "priortop-w5.csv"; f.write_text("dk_player_id,pred_own\n1,10\n")
    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    env = _healthy(tmp_path); env.update({"UNION_MAIN": "mix", "UNION_MIX_PORTFOLIO": "mix", "UNION_MIX_FILL": "rr",
                                          "UNION_TERM_BLOCK_ROWS": "8", "UNION_TERM_BLOCK_SOURCE": str(f), "UNION_TERM_BLOCK_SHA256": sha})
    assert not any("UNION_TERM_BLOCK_ROWS" in x for x in _failures(_run(env)))
    for k, v, msg in (("UNION_TERM_BLOCK_SHA256", "0" * 64, "sha"), ("UNION_TERM_BLOCK_SHA256", "", "no UNION_TERM_BLOCK_SHA256"),
                      ("UNION_TERM_BLOCK_SOURCE", str(tmp_path / "nope.csv"), "does not exist"), ("UNION_MIX_FILL", "group", "rr"),
                      ("UNION_TERM_BLOCK_ROWS", "90", "BOOK_ENTRIES"), ("UNION_MAIN_OWN_TILT", "0.2", "whole-book"),
                      ("UNION_TERM_BLOCK_CAP", "9", "cap")):
        bad = dict(env, **{k: v})
        assert any("UNION_TERM_BLOCK_ROWS" in x and msg in x for x in _failures(_run(bad))), (k, v)
    env["UNION_TERM_BLOCK_ROWS"] = "0"; env["UNION_TERM_BLOCK_SOURCE"] = ""
    assert not any("UNION_TERM_BLOCK_ROWS" in x for x in _failures(_run(env)))


def _commit(path: Path, rel: str, text: str) -> str:
    g = ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    (path / rel).parent.mkdir(parents=True, exist_ok=True)
    (path / rel).write_text(text)
    subprocess.run(g + ["add", "-A"], check=True)
    subprocess.run(g + ["commit", "-q", "-m", rel], check=True)
    return subprocess.run(g[:3] + ["rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()


def test_production_code_that_moved_since_arming_fails_and_docs_do_not(tmp_path):
    """The outside review 10-07, M3: Sunday runs the code armed on Saturday. PROD_ARMED_HEAD pins it; a later docs-only
    pull (HANDOFF, reports, briefings, README) passes, a code change fails, and a malformed pin fails."""
    env = _healthy(tmp_path)
    prod = Path(env["PROD"])
    armed = subprocess.run(["git", "-C", str(prod), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    env["PROD_ARMED_HEAD"] = armed
    assert _run(env).returncode == 0
    _commit(prod, "HANDOFF.md", "a note\n"); _commit(prod, "reports/x.md", "r\n")
    r = _run(env)
    assert r.returncode == 0, r.stderr                                                  # docs only
    _commit(prod, "scripts/sunday_build_host.sh", "#!/usr/bin/env bash\necho changed\n")
    r = _run(env)
    assert r.returncode == 2
    assert any(f.startswith(f"production code moved since arming ({armed[:12]} -> ") and "scripts/sunday_build_host.sh" in f
               for f in _failures(r)), _failures(r)
    env["PROD_ARMED_HEAD"] = "abc"
    assert any("PROD_ARMED_HEAD must be a full 40-character commit" in f for f in _failures(_run(env)))


def test_his_package_is_armed_only_whole_and_the_flat_35_never_alone(tmp_path):
    """His 10-09 package (study 89, Addendum 186): UNION_MAIN_OWN_CAP_DELTA=15 needs the mix and UNION_MAIN_CAP=0.35; the
    player cap 0.35 needs the ownership cap; (0.5, off) is the book as before."""
    def fresh(name):
        d = tmp_path / name; d.mkdir(); return _healthy(d)

    alone = "UNION_MAIN_CAP=0.35 without the ownership cap: the flat 35% never runs alone"
    pkg = "UNION_MAIN_OWN_CAP_DELTA="
    env = fresh("a"); env.update(UNION_MAIN_CAP="0.35")
    assert any(f.startswith(alone) for f in _failures(_run(env)))
    env = fresh("b"); env.update(UNION_MAIN_CAP="0.5", UNION_MAIN_OWN_CAP_DELTA="15", UNION_MAIN="mix", UNION_MIX_PORTFOLIO="mix")
    assert any(f.startswith(pkg + "'15' is his package only") for f in _failures(_run(env)))
    env = fresh("c"); env.update(UNION_MAIN_CAP="0.35", UNION_MAIN_OWN_CAP_DELTA="12", UNION_MAIN="mix", UNION_MIX_PORTFOLIO="mix")
    assert any(f.startswith(pkg + "'12' is his package only") for f in _failures(_run(env)))
    env = fresh("c10"); env.update(UNION_MAIN_CAP="0.35", UNION_MAIN_OWN_CAP_DELTA="10", UNION_MAIN="mix", UNION_MIX_PORTFOLIO="mix")
    assert not any(f.startswith(pkg) for f in _failures(_run(env)))        # +10: study 90 / 100's variant, only on his decision
    env = fresh("d"); env.update(UNION_MAIN_CAP="0.35", UNION_MAIN_OWN_CAP_DELTA="15", UNION_MAIN="mix", UNION_MIX_PORTFOLIO="mix")
    found = _failures(_run(env))
    assert not any(f.startswith(alone) or f.startswith(pkg) for f in found), found
    env = fresh("e"); env.update(UNION_MAIN_CAP="0.5", UNION_MAIN_OWN_CAP_DELTA="0")
    assert not any(f.startswith(alone) or f.startswith(pkg) for f in _failures(_run(env)))


def test_his_test2_row_rules_ride_only_on_his_package(tmp_path):
    """His 10-09 test 2 (study 91): UNION_MIX_ROW_RULES=te1_low1 needs the mix and his package (the ownership file)."""
    def fresh(name):
        d = tmp_path / name; d.mkdir(); return _healthy(d)

    msg = "UNION_MIX_ROW_RULES="
    env = fresh("a"); env.update(UNION_MIX_ROW_RULES="te1_low1", UNION_MAIN="mix", UNION_MIX_PORTFOLIO="mix", UNION_MAIN_CAP="0.5")
    assert any(f.startswith(msg + "'te1_low1' must be te1_low1, with UNION_MAIN=mix and his package") for f in _failures(_run(env)))
    env = fresh("b"); env.update(UNION_MIX_ROW_RULES="te2", UNION_MAIN="mix", UNION_MIX_PORTFOLIO="mix")
    assert any(f.startswith(msg + "'te2'") for f in _failures(_run(env)))
    env = fresh("c"); env.update(UNION_MIX_ROW_RULES="te1_low1", UNION_MAIN="mix", UNION_MIX_PORTFOLIO="mix", UNION_MAIN_CAP="0.35",
                                 UNION_MAIN_OWN_CAP_DELTA="15")
    assert not any(f.startswith(msg) for f in _failures(_run(env)))


def test_his_onecatch_rides_only_on_the_row_rules_and_his_package(tmp_path):
    """His 10-09 decision (study 93's ONECATCH): UNION_MIX_ONE_CATCHER_ALL=1 needs the mix, the row rules and his package."""
    def fresh(name):
        d = tmp_path / name; d.mkdir(); return _healthy(d)

    msg = "UNION_MIX_ONE_CATCHER_ALL="
    pkg = dict(UNION_MAIN="mix", UNION_MIX_PORTFOLIO="mix", UNION_MAIN_CAP="0.35", UNION_MAIN_OWN_CAP_DELTA="15")
    env = fresh("a"); env.update(pkg, UNION_MIX_ONE_CATCHER_ALL="1")                      # no row rules
    assert any(f.startswith(msg + "'1' must be 1, with UNION_MIX_ROW_RULES=te1_low1") for f in _failures(_run(env)))
    env = fresh("b"); env.update(pkg, UNION_MIX_ROW_RULES="te1_low1", UNION_MIX_ONE_CATCHER_ALL="2")
    assert any(f.startswith(msg + "'2'") for f in _failures(_run(env)))
    env = fresh("c"); env.update(UNION_MAIN="mix", UNION_MIX_PORTFOLIO="mix", UNION_MAIN_CAP="0.5", UNION_MIX_ONE_CATCHER_ALL="1")
    assert any(f.startswith(msg + "'1'") for f in _failures(_run(env)))                    # no package
    env = fresh("d"); env.update(pkg, UNION_MIX_ROW_RULES="te1_low1", UNION_MIX_ONE_CATCHER_ALL="1", UNION_MIX_FILL="rr")
    assert not any(f.startswith(msg) for f in _failures(_run(env)))
    env = fresh("e"); env.update(pkg, UNION_MIX_ROW_RULES="te1_low1", UNION_MIX_ONE_CATCHER_ALL="0")
    assert not any(f.startswith(msg) for f in _failures(_run(env)))
    # the union refuses the whole run with these, so Saturday's check must fail on them (the outside reviewer's finding)
    live = dict(pkg, UNION_MIX_ROW_RULES="te1_low1", UNION_MIX_ONE_CATCHER_ALL="1", UNION_MIX_FILL="rr", UNION_MIX_COVER_GAMES="0",
                UNION_MIX_RS_ROWS="0", UNION_WINNER_SELECT="0")
    env = fresh("f"); env.update(live)
    assert not any(f.startswith("UNION_MIX_ONE_CATCHER_ALL=1 is refused") for f in _failures(_run(env)))
    for i, bad in enumerate((dict(UNION_MIX_FILL="group"), dict(UNION_MIX_PORTFOLIO="ws"), dict(UNION_MIX_COVER_GAMES="4"),
                             dict(UNION_MIX_RS_ROWS="13"), dict(UNION_MIX_BRING_BACK_TOP_WR="A1,B"), dict(UNION_WINNER_SELECT="1"))):
        env = fresh(f"g{i}"); env.update(live, **bad)
        k = next(iter(bad))
        assert any(f.startswith("UNION_MIX_ONE_CATCHER_ALL=1 is refused") and f"{k}=" in f for f in _failures(_run(env))), bad


def test_his_rbmate_rides_only_on_onecatch(tmp_path):
    """His 10-09 decision (study 94's RBMATE4): UNION_MIX_RB_MATE_C=4 needs UNION_MIX_ONE_CATCHER_ALL=1 (and so everything
    that needs); any other value is refused."""
    def fresh(name):
        d = tmp_path / name; d.mkdir(); return _healthy(d)

    msg = "UNION_MIX_RB_MATE_C="
    live = dict(UNION_MAIN="mix", UNION_MIX_PORTFOLIO="mix", UNION_MAIN_CAP="0.35", UNION_MAIN_OWN_CAP_DELTA="15",
                UNION_MIX_ROW_RULES="te1_low1", UNION_MIX_ONE_CATCHER_ALL="1", UNION_MIX_FILL="rr")
    env = fresh("a"); env.update(live, UNION_MIX_RB_MATE_C="4")
    assert not any(f.startswith(msg) for f in _failures(_run(env)))
    env = fresh("b"); env.update(live, UNION_MIX_RB_MATE_C="0")
    assert not any(f.startswith(msg) for f in _failures(_run(env)))
    env = fresh("c"); env.update(live, UNION_MIX_RB_MATE_C="8")
    assert any(f.startswith(msg + "'8' must be 4") for f in _failures(_run(env)))
    env = fresh("d"); env.update(live, UNION_MIX_ONE_CATCHER_ALL="0", UNION_MIX_RB_MATE_C="4")
    assert any(f.startswith(msg + "'4' must be 4 (study 94's tested value), with UNION_MIX_ONE_CATCHER_ALL=1") for f in _failures(_run(env)))
