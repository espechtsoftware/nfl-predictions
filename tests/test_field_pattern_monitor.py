"""Offline tests for scripts/field_pattern_monitor.py (the Mantel-Haenszel arithmetic; no BigQuery)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SPEC = importlib.util.spec_from_file_location("field_pattern_monitor", Path(__file__).resolve().parents[1] / "scripts" / "field_pattern_monitor.py")
M = importlib.util.module_from_spec(_SPEC); _SPEC.loader.exec_module(M)


def _cells(rows):
    return pd.DataFrame(rows, columns=["week", "u", "k", "n", "t"])


def test_mh_matches_hand_computation():
    # stratum 1: a=2 b=8 c=1 d=9 (n 20) -> ad/n 0.9, bc/n 0.4; stratum 2: a=1 b=4 c=1 d=14 -> 0.7, 0.2; OR 1.6 / 0.6
    c = _cells([(1, 1, 2, 10, 2), (1, 1, 0, 10, 1), (1, 2, 3, 5, 1), (1, 2, 1, 15, 1)])
    est, num, den = M.mh_odds_ratio(c, lambda k: k >= 2)
    assert est == pytest.approx(1.6 / 0.6)
    assert num.sum() == pytest.approx(1.6) and den.sum() == pytest.approx(0.6)


def test_exposure_levels_pool_within_a_stratum():
    # k 2 and 3 are both exposed under k >= 2: splitting the exposed cell must not change the answer
    a = _cells([(1, 1, 2, 10, 2), (1, 1, 0, 10, 1)])
    b = _cells([(1, 1, 2, 6, 1), (1, 1, 3, 4, 1), (1, 1, 0, 10, 1)])
    assert M.mh_odds_ratio(a, lambda k: k >= 2)[0] == pytest.approx(M.mh_odds_ratio(b, lambda k: k >= 2)[0])


def test_single_level_stratum_adds_nothing():
    base = _cells([(1, 1, 2, 10, 2), (1, 1, 0, 10, 1), (1, 2, 3, 5, 1), (1, 2, 1, 15, 1)])
    more = pd.concat([base, _cells([(2, 9, 2, 40, 5)])], ignore_index=True)  # exposed lineups only
    assert M.mh_odds_ratio(more, lambda k: k >= 2)[0] == pytest.approx(M.mh_odds_ratio(base, lambda k: k >= 2)[0])


def test_no_discordant_information_is_nan():
    c = _cells([(1, 1, 2, 10, 0), (1, 1, 0, 10, 0)])
    assert np.isnan(M.mh_odds_ratio(c, lambda k: k >= 2)[0])


def test_bootstrap_interval_brackets_estimate():
    rng = np.random.default_rng(0); rows = []
    for u in range(300):
        for k, p in ((0, 0.01), (2, 0.02)):
            n = 30; rows.append((1, u, k, n, int(rng.binomial(n, p))))
    est, num, den = M.mh_odds_ratio(_cells(rows), lambda k: k >= 2)
    lo, hi = M.bootstrap_ci(num, den, reps=300)
    assert lo < est < hi


def test_history_base_rates():
    assert sum(M.HIST_P_BEST_STACK[k] for k in (1, 2, 3, 4)) == pytest.approx(0.55)
    assert M.CHEAP_MAX_SALARY == 4000


def test_game_total_ranks_break_ties_by_game_id():
    fr = pd.DataFrame({"game_id": ["2026_05_B", "2026_05_A", "2026_05_C", "2026_05_A", "2026_05_D"],
                       "game_total": [47.5, 47.5, 51.0, 47.5, 40.0]})
    assert M.game_total_ranks(fr) == {"2026_05_C": 1, "2026_05_A": 2, "2026_05_B": 3, "2026_05_D": 4}


def test_game_total_ranks_put_a_missing_total_last():
    fr = pd.DataFrame({"game_id": ["G1", "G2", "G3"], "game_total": [44.5, np.nan, 51.0]})
    assert M.game_total_ranks(fr) == {"G3": 1, "G1": 2, "G2": 3}


def test_slate_arrays_drop_unpriced_rows_and_stay_aligned():
    fr = pd.DataFrame({"display_name": ["A QB", "B WR", "C TE", "A QB", "D RB"], "salary": [6500.0, 3500.0, np.nan, 6500.0, 4000.0],
                       "pos": ["QB", "WR", "TE", "QB", "RB"], "game_id": ["G1", "G1", "G2", "G1", "G2"]})
    names, sal, pos, qrank = M.slate_arrays(fr, {"G1": 2, "G2": 1})
    assert names == ["A QB", "B WR", "D RB"] and sal == [6500, 3500, 4000] and pos == ["QB", "WR", "RB"] and qrank == [2, 0, 0]
    assert all(isinstance(x, int) for x in sal)


def test_bootstrap_without_information_is_nan():
    lo, hi = M.bootstrap_ci(pd.Series([0.0, 0.0]), pd.Series([0.0, 0.0]), reps=20)
    assert np.isnan(lo) and np.isnan(hi)
