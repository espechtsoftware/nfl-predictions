"""Offline tests for scripts/priority_field_monitor.py (type loading, priority keys, depth flags, the MH arithmetic)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SPEC = importlib.util.spec_from_file_location("priority_field_monitor", Path(__file__).resolve().parents[1] / "scripts" / "priority_field_monitor.py")
M = importlib.util.module_from_spec(_SPEC); _SPEC.loader.exec_module(M)


def test_load_types_reads_both_id_conventions_and_later_files_win(tmp_path):
    a = tmp_path / "a.csv"; a.write_text('contest_id,week,type,size\n111,1,"$4,444 MEGA Milly sat",402\n222,1,$20 Milly sat (1 seat),11\n')
    b = tmp_path / "b.csv"; b.write_text("w5_contest_id,type,series\n333,$333 Wildcat sat,x\n222,$555 Milly sat,y\n")
    t = M.load_types([a, b, tmp_path / "missing.csv"])
    assert t == {"111": "$4,444 MEGA Milly sat", "222": "$555 Milly sat", "333": "$333 Wildcat sat"}


def test_priority_keys_follow_the_operator():
    for t in ("$4,444 MEGA Milly sat", "$4,444 Showdown MEGA Milly sat", "$555 Milly supersat [2x]", "$333 Wildcat sat",
              "FFWC qualifier ($14M)", "FFWC qualifier sat/supersat", "Midseason Warm Up Milly sat"):
        assert M.is_priority(t)
    for t in ("$20 Milly sat (1 seat)", "$20 Milly supersat [25x]", "$20 Milly supersat [2x/4x]", "Millionaire (main)", "other GPP"):
        assert not M.is_priority(t)


def test_top_flags_pay_at_least_rank_one():
    assert M.top_flags([1, 2], [11, 11], 0.05).tolist() == [True, False]
    assert M.top_flags([5, 6], [100, 100], 0.05).tolist() == [True, False]
    assert M.top_flags([10, 11], [100, 100], 0.10).tolist() == [True, False]


def _lineups():
    # two contests; contest A: exposed 10 lineups (2 events), reference 10 (1); contest B: exposed 5 (1), reference 15 (1)
    rows = []
    for c, e_n, e_t, r_n, r_t in (("A", 10, 2, 10, 1), ("B", 5, 1, 15, 1)):
        rows += [{"week": 1, "contest_id": c, "cheap": 2, "top5": i < e_t} for i in range(e_n)]
        rows += [{"week": 1, "contest_id": c, "cheap": 0, "top5": i < r_t} for i in range(r_n)]
    return pd.DataFrame(rows)


def test_odds_ratio_matches_the_hand_computation():
    d = _lineups()
    est, lo, hi, ev = M.odds_ratio(d, "contest_id", d.cheap >= 2, d.cheap <= 1, "top5")
    assert est == pytest.approx(1.6 / 0.6) and ev == 5


def test_lineups_outside_both_levels_are_ignored():
    d = pd.concat([_lineups(), pd.DataFrame([{"week": 1, "contest_id": "A", "cheap": 1, "top5": True}])], ignore_index=True)
    est, _, _, _ = M.odds_ratio(d, "contest_id", d.cheap >= 2, d.cheap == 0, "top5")
    assert est == pytest.approx(1.6 / 0.6)


def test_feature_cells_shape():
    d = _lineups()
    cells = M.feature_cells(d, "contest_id", d.cheap >= 2, d.cheap <= 1, "top5")
    assert set(cells.columns) == {"week", "u", "k", "n", "t"} and int(cells.n.sum()) == len(d) and int(cells.t.sum()) == 5


def test_constants():
    assert M.CHEAP_MAX_SALARY == 4000 and M.DEPTHS == (0.02, 0.05, 0.10) and M.MIN_USER_LINEUPS == 3
    assert M.FPM.CHEAP_MAX_SALARY == 4000
