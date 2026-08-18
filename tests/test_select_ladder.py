"""SELECT_LADDER lever (Ring A / A1): portfolio-marginal greedy on a
sparse tail-utility ladder. Vacuity law: off-by-default byte-identical;
the lever fires; the E[max] term pays for depth binary coverage ignores;
deterministic ties; spec parsing fails closed."""
import numpy as np
import pytest

from nfl_dfs.backtest import engine
from nfl_dfs.optimizer.lineup import (
    _parse_ladder,
    select_ladder_entries,
    select_tail_entries,
)


def test_off_by_default_is_byte_identical():
    totals = np.random.default_rng(0).normal(170, 20, size=(30, 200))
    base = select_tail_entries(totals, 8, 194.0)
    unset = select_tail_entries(totals, 8, 194.0, env={})
    empty = select_tail_entries(totals, 8, 194.0, env={"SELECT_LADDER": ""})
    assert base == unset == empty


def test_lever_gates_select_tail_entries():
    totals = np.random.default_rng(1).normal(170, 20, size=(30, 200))
    ladder = select_tail_entries(
        totals, 8, 194.0, env={"SELECT_LADDER": "210:4,194:1,mean:0.01"})
    assert len(ladder) == 8 and len(set(ladder)) == 8


def test_mean_term_prefers_depth_over_redundancy():
    # World 0: cand A scores 200, cand B scores 265 — binary coverage at
    # 194 treats them as redundant; the E[max] term must keep the 265.
    a = np.array([200.0, 100.0, 100.0, 100.0])
    b = np.array([265.0, 100.0, 100.0, 100.0])
    c = np.array([100.0, 196.0, 100.0, 100.0])
    totals = np.array([a, b, c])
    picked = select_ladder_entries(
        totals, 2, {194.0: 1.0}, mean_weight=0.01)
    assert 1 in picked, "ladder+mean dropped the deep candidate"


def test_pure_ladder_matches_coverage_counts_at_one_threshold():
    totals = np.random.default_rng(2).normal(175, 25, size=(40, 500))
    line = 194.0
    ladder_pick = select_ladder_entries(totals, 10, {line: 1.0})
    coverage_pick = select_tail_entries(totals, 10, line)
    covered_ladder = (totals[ladder_pick] >= line).any(axis=0).sum()
    covered_greedy = (totals[coverage_pick] >= line).any(axis=0).sum()
    # Same submodular objective, different tie-breaks: covered-world
    # counts must match exactly even when identities differ.
    assert covered_ladder == covered_greedy


def test_higher_rungs_outrank_shoulder_redundancy():
    # One candidate clears 240 in a world already covered at 194; a pure
    # 194 selector is indifferent, the ladder is not.
    base = np.full(6, 100.0)
    a = base.copy(); a[0] = 200.0                     # covers 194 in w0
    b = base.copy(); b[0] = 245.0                     # 240 in the SAME world
    c = base.copy(); c[1] = 196.0                     # fresh 194 world
    totals = np.array([a, b, c])
    ladder = {240.0: 8.0, 210.0: 2.0, 194.0: 1.0}
    picked = select_ladder_entries(totals, 2, ladder)
    assert set(picked) == {1, 2}, "ladder failed to pay for the 240 rung"


def test_deterministic_and_repeatable():
    totals = np.random.default_rng(3).normal(170, 20, size=(25, 300))
    ladder = {210.0: 4.0, 194.0: 1.0}
    first = select_ladder_entries(totals, 8, ladder, mean_weight=0.001)
    second = select_ladder_entries(totals, 8, ladder, mean_weight=0.001)
    assert first == second


def test_parse_ladder_and_fail_closed():
    ladder, mean_weight = _parse_ladder("240:32,194:1,mean:0.5")
    assert ladder == {240.0: 32.0, 194.0: 1.0}
    assert mean_weight == 0.5
    with pytest.raises(ValueError):
        _parse_ladder("194")           # no weight
    with pytest.raises(ValueError):
        _parse_ladder("194:-1")        # negative weight
    with pytest.raises(ValueError):
        _parse_ladder("mean:0")        # no positive term


def test_lever_is_registered():
    assert "SELECT_LADDER" in engine._lever_keys
