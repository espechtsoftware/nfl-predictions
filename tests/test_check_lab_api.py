"""check_lab_api: synthetic sources for every rule (always run), plus the real pinned clone when present."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_lab_api", ROOT / "scripts" / "check_lab_api.py")
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)


def _lab(tmp_path, body: str) -> Path:
    src = tmp_path / "src"; (src / "nfl2" / "core").mkdir(parents=True)
    (src / "nfl2" / "core" / "lineup.py").write_text(body)
    return src


def _tool(tmp_path, body: str) -> Path:
    d = tmp_path / "scripts"; d.mkdir(exist_ok=True)
    (d / "t.py").write_text(body)
    return d


def test_unknown_keyword_fails_and_known_passes(tmp_path):
    src = _lab(tmp_path, "def optimize(pool, stack=None, member_bounds=None):\n    pass\n")
    ok = _tool(tmp_path, "optimize(p, stack=1, **({'member_bounds': x} if x else {}))\n")
    assert C.check(src, ok, {"t.py": ("optimize",)}) == []
    (ok / "t.py").write_text("optimize(p, stack=1, **({'set_constraints': x} if x else {}))\n")
    assert any("set_constraints" in p for p in C.check(src, ok, {"t.py": ("optimize",)}))


def test_keywords_from_a_bound_dict_are_checked(tmp_path):
    src = _lab(tmp_path, "def select_top_mean(score, rosters, k, max_shared=7, dst_of=None):\n    pass\n")
    d = _tool(tmp_path, "args = {'dst_of': 1, 'dst_cap': 2}\nselect_top_mean(s, r, 5, max_shared=7, **args)\n")
    assert any("dst_cap" in p for p in C.check(src, d, {"t.py": ("select_top_mean",)}))


def test_too_many_positional_arguments_fail(tmp_path):
    src = _lab(tmp_path, "def validate_roster(roster, pos, team):\n    pass\n")
    d = _tool(tmp_path, "validate_roster(a, b, c, d)\n")
    assert any("4 positional" in p for p in C.check(src, d, {"t.py": ("validate_roster",)}))
    (d / "t.py").write_text("validate_roster(a, b, c)\n")
    assert C.check(src, d, {"t.py": ("validate_roster",)}) == []


def test_kwargs_signature_accepts_any_keyword_and_missing_things_are_named(tmp_path):
    src = _lab(tmp_path, "def dk_csv(lus, fr, path, **kw):\n    pass\n")
    d = _tool(tmp_path, "dk_csv(a, b, c, anything=1)\n")
    assert C.check(src, d, {"t.py": ("dk_csv",)}) == []
    assert any("expected a call to swap_entry" in p for p in C.check(src, d, {"t.py": ("dk_csv", "swap_entry")}))
    assert any("not defined in the pinned clone" in p for p in C.check(src, d, {"t.py": ("dk_csv", "swap_entry")}))
    assert C.check(tmp_path / "nowhere", d, {"t.py": ("dk_csv",)})[0].startswith("pinned lab clone source not found")


def _clone() -> Path | None:
    """NFL2_PINNED_SRC, else the live-center worktree checked out at the money path's CURRENT pin (mix_shapes.LIVE_PIN).
    2026-10-08: a hard-coded week4-live-center (pin 32cdb61) predates f69598b's qb_game_max / second_game_pair, so this
    test failed on a stale clone while the arm preflight, which checks the live clone, passed."""
    import subprocess
    from nfl_dfs.inference.mix_shapes import LIVE_PIN
    if os.environ.get("NFL2_PINNED_SRC") and (Path(os.environ["NFL2_PINNED_SRC"]) / "nfl2").is_dir():
        return Path(os.environ["NFL2_PINNED_SRC"])
    for wt in sorted(Path.home().glob("projects/.nfl2-worktrees/*-live-center"), reverse=True):
        head = subprocess.run(["git", "-C", str(wt), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if head == LIVE_PIN and (wt / "src" / "nfl2").is_dir():
            return wt / "src"
    return None


def test_money_path_scripts_match_the_pinned_clone():
    src = _clone()
    if src is None:
        pytest.skip("pinned lab clone not on this machine (set NFL2_PINNED_SRC); the arm preflight runs it hard")
    assert C.check(src) == []


def test_main_fails_closed_without_a_clone(tmp_path, capsys):
    assert C.main(["--clone", str(tmp_path / "none")]) == 2
    assert "LAB API CHECK FAILED" in capsys.readouterr().err


def test_the_arm_preflight_runs_the_check_hard_before_the_check_exit():
    s = (ROOT / "scripts" / "run_week_build.sh").read_text()
    call = '"$PROD_PY" "$SCRIPT_DIR/check_lab_api.py" --clone "$CLONE"'
    assert call in s and s.index(call) < s.index("if [[ \"${1:-}\" == '--check' ]]; then exit 0; fi")
    assert "|| true" not in s[s.index(call):s.index(call) + len(call) + 10]
