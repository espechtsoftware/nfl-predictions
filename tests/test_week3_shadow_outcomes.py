"""Offline tests for the outcomes builder's pure mapping (no BigQuery)."""
import importlib.util, pathlib, subprocess, sys
import pandas as pd, pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("w3o", ROOT / "scripts" / "week3_shadow_outcomes.py"); w3o = importlib.util.module_from_spec(spec); spec.loader.exec_module(w3o)

FRAME = pd.DataFrame({"id": ["00-1", "00-2", "00-3", "KC_DST", "BUF_DST"], "gsis_id": ["00-1", "00-2", "00-3", "0.0", "0.0"], "pos": ["QB", "WR", "RB", "DST", "DST"],
                      "team": ["KC", "KC", "BUF", "KC", "BUF"], "game_id": ["2026_03_BUF_KC"] * 5})
SKILL = pd.DataFrame({"gsis_id": ["00-1", "00-2"], "dk_points": [24.5, 11.0], "has_stat_line": [True, True]})
DST = pd.DataFrame({"team": ["kc"], "dst_dk_points": [7.0]})
FINAL = pd.DataFrame({"game_id": ["2026_03_BUF_KC"], "home_team": ["KC"], "away_team": ["BUF"], "home_score": [27], "away_score": [20], "is_final": [True]})


def test_mapping_and_zero_fill():
    out, rec = w3o.build(FRAME, SKILL, DST, FINAL)
    got = dict(zip(out.id, out.actual_points)); src = dict(zip(out.id, out.source))
    assert got == {"00-1": 24.5, "00-2": 11.0, "00-3": 0.0, "KC_DST": 7.0, "BUF_DST": 0.0}
    assert src["00-3"] == "absent_after_final" and src["BUF_DST"] == "dst_absent_after_final" and src["KC_DST"] == "team_defense_week.dst_dk_points"
    assert rec["counts"] == {"skill_row": 2, "dst_row": 1, "absent_after_final": 1, "dst_absent_after_final": 1} and rec["games"]["2026_03_BUF_KC"]["is_final"]


def test_refuses_non_final_game():
    nf = FINAL.assign(is_final=[False])
    with pytest.raises(RuntimeError, match="not final"): w3o.build(FRAME, SKILL, DST, nf)
    with pytest.raises(RuntimeError): w3o.build(FRAME, SKILL, DST, FINAL.iloc[0:0])   # game absent from the schedule


def test_cli_requires_release_flag(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "week3_shadow_outcomes.py"), "--run", str(tmp_path), "--season", "2026", "--week", "3", "--out", str(tmp_path / "o")], capture_output=True, text=True)
    assert r.returncode == 2 and "release" in r.stderr
