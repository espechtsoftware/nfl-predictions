"""Offline tests for scripts/ownership_tabpfn_rows_2026.py (the 2026 context rows for the live TabPFN ownership step)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("otr26", ROOT / "scripts" / "ownership_tabpfn_rows_2026.py")
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)

L23_COLUMNS = ["season", "week", "id", "gsis_id", "name", "pos", "pos_code", "salary", "mean_projection",
               "implied_team_total", "game_total", "spread", "salary_delta_wow", "value", "own_l1", "own_l3",
               "linestar_own", "target_own", "is_eval", "base_blend", "base_lag"]


def test_spread_flipped_to_history_convention():
    total = pd.Series([48.0, 48.0, 40.0])
    implied = pd.Series([27.0, 21.0, np.nan])          # a 6-point favourite, its underdog, a missing implied total
    live = pd.Series([6.0, -6.0, 3.5])                  # live convention: favourite positive
    out, meta = M.historical_spread(total, implied, live)
    assert out.tolist() == [-6.0, 6.0, -3.5]            # history: favourite negative; missing implied -> -spread
    assert meta["from_minus_spread"] == 1 and meta["disagree_gt_1pt"] == 0 and meta["still_nan"] == 0


def test_spread_refuses_the_history_convention_fed_back_in():
    total = pd.Series([48.0] * 10)
    implied = pd.Series([27.0] * 10)
    already_history = pd.Series([-6.0] * 10)           # a frame that is already in the historical sign
    with pytest.raises(SystemExit, match="spread conversion refused"):
        M.historical_spread(total, implied, already_history)


def test_lag_columns_follow_l23():
    by_week = {1: {"a": 10.0, "b": 2.0}, 2: {"a": 20.0}, 3: {"c": 5.0}}
    keys = ["a", "b", "c"]
    l1, l3 = M.lag_columns(keys, 1, by_week)
    assert np.isnan(l1) and np.isnan(l3)                # W1: no panel week before it
    l1, l3 = M.lag_columns(keys, 2, by_week)
    assert l1 == [10.0, 2.0, 0.0] and l3 == [10.0, 2.0, 0.0]
    l1, l3 = M.lag_columns(keys, 3, by_week)
    assert l1 == [20.0, 0.0, 0.0]                        # listed in W2 or 0
    assert l3 == [15.0, 1.0, 0.0]                        # mean over W2 and W1, 0 when not listed


def _frame(week: int) -> pd.DataFrame:
    return pd.DataFrame({
        "season": 2026, "week": week, "id": ["1", "2", "3", "4", "5"], "gsis_id": ["g1", "g2", "g3", "g4", "g5"],
        "name": ["Josh Allen", "Tony Pollard Jr.", "Low Guy", "Kicker", "Bills"],
        "display_name": ["Josh Allen", "Tony Pollard Jr.", "Low Guy", "Kicker", "Bills"],
        "pos": ["QB", "RB", "WR", "K", "DST"], "salary": [8000, 6000, 3000, 4500, 3000],
        "mean_projection": [22.0, 14.0, 0.5, 8.0, 7.0], "implied_team_total": [27.0, 21.0, 21.0, 27.0, 27.0],
        "game_total": [48.0] * 5, "spread": [6.0, -6.0, -6.0, 6.0, 6.0], "salary_delta_wow": [200.0, -100.0, 0.0, 0.0, 0.0]})


def test_build_week_rows_have_l23_columns_and_conventions():
    by_week = {1: {"joshallen": 30.0, "tonypollard": 12.0}, 2: {"joshallen": 25.0, "lowguy": 1.0}}
    ls = {("josh allen", "QB"): 28.5}
    d, meta = M.build_week(_frame(2), 2026, 2, by_week, ls)
    assert list(d.columns) == L23_COLUMNS
    assert d.name.tolist() == ["Josh Allen", "Tony Pollard Jr."]          # skill only, projection >= 1
    assert d.pos_code.tolist() == [0, 1]
    assert d.spread.tolist() == [-6.0, 6.0]
    assert d.target_own.tolist() == [25.0, 0.0]
    assert d.own_l1.tolist() == [30.0, 12.0] and d.own_l3.tolist() == [30.0, 12.0]
    assert d.linestar_own.iloc[0] == 28.5 and np.isnan(d.linestar_own.iloc[1])
    assert not d.is_eval.any() and d.base_blend.isna().all() and d.base_lag.isna().all()
    assert d.value.round(3).tolist() == [2.75, 2.333]
    assert meta["target_pct_matched_by_frame_skill"] == 26.0              # includes the sub-1 projection player


def test_build_week_refuses_wrong_week_and_duplicate_keys():
    by_week = {1: {}, 2: {}}
    with pytest.raises(SystemExit, match="expected 2"):
        M.build_week(_frame(1), 2026, 2, by_week, {})
    dup = _frame(2)
    dup.loc[2, "display_name"] = "Josh Allen"
    with pytest.raises(SystemExit, match="duplicate name keys"):
        M.build_week(dup, 2026, 2, by_week, {})
