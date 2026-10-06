"""scripts/weekly_picks_vs_field.py: the picks-vs-the-rest-of-the-field edge and its within-band null (offline).
The script itself reproduced the 10-05 report's observed edges exactly on 2026 W1-4 (regulars +4.9 / +8.4 / +6.4 / +4.7,
ours +2.9 / -9.7 / -6.2 / -2.4; laptop, 10-06), which needs the private inputs and is not repeated here."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("weekly_picks_vs_field", ROOT / "scripts" / "weekly_picks_vs_field.py")
PV = importlib.util.module_from_spec(spec); spec.loader.exec_module(PV)


def _panel():
    counts = pd.DataFrame({"player": ["A", "B", "C", "A", "B", "C", "A", "C"], "grp": ["reg", "reg", "reg", "rest", "rest", "rest", "ours", "ours"],
                           "k": [6, 2, 2, 3, 5, 2, 1, 1]})
    frame = pd.DataFrame({"display_name": ["A", "B", "C"], "pos": ["WR", "WR", "RB"], "salary": [6100, 6800, 5200]})
    return PV.panel(counts, {"reg": 10, "rest": 10, "ours": 2}, frame, pd.Series({"A": 20.0, "B": 5.0, "C": 10.0}))


def test_the_edge_is_the_share_difference_times_points():
    d = _panel()
    # regulars: A .6-.3, B .2-.5, C .2-.2 -> .3*20 - .3*5 + 0 = +4.5; ours: A .5-.3, B 0-.5, C .5-.2 -> 4 - 2.5 + 3 = +4.5
    assert PV.edge(d, "reg_share") == 4.5 and PV.edge(d, "our_share") == 4.5


def test_the_null_shuffles_only_within_position_and_salary_band():
    d = _panel()
    nul = PV.null_draws(d, "reg_share", b=200, seed=1)
    # A (6100) and B (6800) share the WR $6k band: their points may swap; C is alone in its band and keeps 10
    assert set(np.round(nul, 6)) <= {4.5, round(.3 * 5 - .3 * 20, 6)} and len(set(np.round(nul, 6))) == 2


def test_pool_reports_weeks_from_5_beside_the_baseline(tmp_path, capsys):
    log = tmp_path / "picks-vs-field.jsonl"
    log.write_text("\n".join(json.dumps({"season": 2026, "week": w, "group": g, "edge": e}) for w, g, e in
                             ((4, "ours", -2.4), (5, "ours", 1.0), (6, "ours", 3.0), (5, "regulars", 5.0))) + "\n")
    assert PV.main(["pool", "--out-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "ours      weeks >= 5: 2 | mean +2.0 pts/lineup | before FP (2026 W1-4): -3.8" in out
    assert "regulars  weeks >= 5: 1 | mean +5.0 pts/lineup | before FP (2026 W1-4): +6.1" in out
