"""check_ownership_lag: the reviewer's gate 4 (sum >= 280, percentages, enough rows)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_ownership_lag as col  # noqa: E402


def _write(tmp_path, values):
    p = tmp_path / "ownership_lag.csv"
    pd.DataFrame({"display_name": [f"P{i}" for i in range(len(values))], "pred_own": values}).to_csv(p, index=False)
    return p


def test_a_live_week_passes(tmp_path):
    ok, msg = col.check(_write(tmp_path, [20.0, 15.0] + [2.5] * 150))
    assert ok and "sum 410" in msg and "P0 20.0%" in msg


def test_a_collapsed_rebuild_refuses(tmp_path):
    ok, msg = col.check(_write(tmp_path, [5.9] + [1.2] * 150))
    assert not ok and "collapsed" in msg
    assert col.main([str(tmp_path / "ownership_lag.csv")]) == 2


def test_fractions_missing_and_short_files_refuse(tmp_path):
    assert not col.check(_write(tmp_path, [0.2] * 150))[0]
    assert not col.check(tmp_path / "nope.csv")[0]
    assert not col.check(_write(tmp_path, [50.0] * 20))[0]
