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


def test_union_mix_fill_must_be_group_or_value_with_a_mix_main(tmp_path):
    """Study 42's switch (operator 10-06): unset is today's group fill; set, it must name a fill and ride a MIX main."""
    env = _healthy(tmp_path)
    assert not any("UNION_MIX_FILL" in f for f in _failures(_run(env)))
    env["UNION_MIX_FILL"] = "value"
    assert any("UNION_MIX_FILL='value' must be group or value, with UNION_MAIN=mix" in f for f in _failures(_run(env)))
    env["UNION_MAIN"] = "mix"; env["UNION_MIX_PORTFOLIO"] = "mix"
    assert not any("UNION_MIX_FILL" in f for f in _failures(_run(env)))
    env["UNION_MIX_FILL"] = "best"
    assert any("UNION_MIX_FILL='best'" in f for f in _failures(_run(env)))
