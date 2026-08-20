"""SELECT_LADDER lever (Ring A / A1): portfolio-marginal greedy on a
sparse tail-utility ladder. Vacuity law: off-by-default byte-identical;
the lever fires; the E[max] term pays for depth binary coverage ignores;
deterministic ties; spec parsing fails closed."""
import numpy as np
import pytest

from nfl_dfs.backtest import engine
from nfl_dfs.optimizer.lineup import (
    _parse_ladder,
    select_from_support,
    select_ladder_entries,
    select_tail_entries,
)


def test_off_by_default_is_byte_identical(monkeypatch):
    monkeypatch.delenv("SELECT_LSE", raising=False)
    monkeypatch.delenv("SELECT_LADDER", raising=False)
    totals = np.array([
        [200.0, 100.0, 100.0, 100.0],
        [100.0, 200.0, 100.0, 100.0],
        [200.0, 200.0, 100.0, 100.0],
        [195.0, 195.0, 100.0, 100.0],
        [100.0, 100.0, 100.0, 100.0],
    ])
    clears = totals >= 194.0
    golden = select_from_support(
        clears, clears.mean(axis=1), totals.mean(axis=1), 4,
    )
    base = select_tail_entries(totals, 4, 194.0)
    unset = select_tail_entries(totals, 4, 194.0, env={})
    empty = select_tail_entries(
        totals, 4, 194.0,
        env={"SELECT_LSE": "0", "SELECT_LADDER": ""},
    )
    assert base == unset == empty == golden


def test_lever_gates_select_tail_entries():
    totals = np.array([
        [195.0, 195.0, 100.0, 100.0],
        [211.0, 100.0, 100.0, 100.0],
        [100.0, 100.0, 100.0, 100.0],
    ])
    incumbent = select_tail_entries(totals, 1, 194.0, env={})
    ladder = select_tail_entries(
        totals, 1, 194.0,
        env={"SELECT_LSE": "0", "SELECT_LADDER": "210:10,194:1"},
    )
    assert incumbent == [0]
    assert ladder == [1]


def test_explicit_lse_zero_isolated_from_host_environment(monkeypatch):
    totals = np.random.default_rng(11).normal(170, 20, size=(30, 200))
    spec = "170:10,180:10,187:7,194:7,200:6,210:10"
    expected = select_tail_entries(
        totals, 8, 194.0,
        env={"SELECT_LSE": "0", "SELECT_LADDER": spec},
    )
    monkeypatch.setenv("SELECT_LSE", "0.2")
    monkeypatch.setenv("SELECT_LADDER", "240:999")
    isolated = select_tail_entries(
        totals, 8, 194.0,
        env={"SELECT_LSE": "0", "SELECT_LADDER": spec},
    )
    assert isolated == expected


def test_mean_term_prefers_depth_over_redundancy():
    # Pure coverage prefers two shoulder clears. A sufficiently weighted
    # E[max] term instead prefers one much deeper score.
    totals = np.array([
        [195.0, 195.0, 0.0, 0.0],
        [1000.0, 0.0, 0.0, 0.0],
    ])
    pure = select_ladder_entries(totals, 1, {194.0: 1.0})
    with_mean = select_ladder_entries(
        totals, 1, {194.0: 1.0}, mean_weight=0.01,
    )
    assert pure == [0]
    assert with_mean == [1]


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
    # Binary coverage prefers two shoulder worlds; the weighted ladder
    # prefers the single higher-rung candidate on the first pick.
    totals = np.array([
        [195.0, 195.0, 100.0, 100.0],
        [245.0, 100.0, 100.0, 100.0],
    ])
    ladder = {240.0: 8.0, 210.0: 2.0, 194.0: 1.0}
    incumbent = select_tail_entries(totals, 1, 194.0, env={})
    picked = select_ladder_entries(totals, 1, ladder)
    assert incumbent == [0]
    assert picked == [1]


def test_ties_break_by_mean_then_lower_index():
    different_means = np.array([
        [194.0, 0.0],
        [200.0, 0.0],
    ])
    assert select_ladder_entries(
        different_means, 1, {194.0: 1.0},
    ) == [1]

    exact_tie = np.array([
        [200.0, 0.0],
        [200.0, 0.0],
    ])
    assert select_ladder_entries(exact_tie, 2, {194.0: 1.0}) == [0, 1]


def test_strict_non_ties_are_equivariant_to_candidate_row_order():
    totals = np.array([
        [211.0, 0.0, 0.0, 0.0],
        [195.0, 195.0, 0.0, 0.0],
        [0.0, 0.0, 205.0, 0.0],
        [0.0, 0.0, 0.0, 180.0],
    ])
    ladder = {170.0: 10.0, 194.0: 7.0, 200.0: 6.0, 210.0: 10.0}
    original = select_ladder_entries(totals, 3, ladder)
    permutation = np.array([2, 0, 3, 1])
    permuted = select_ladder_entries(totals[permutation], 3, ladder)
    assert original == [1, 2, 0]
    assert [int(permutation[index]) for index in permuted] == original


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
    with pytest.raises(ValueError):
        _parse_ladder("194:0")         # no positive term
    with pytest.raises(ValueError):
        _parse_ladder("194:1,194:2")   # duplicate threshold
    with pytest.raises(ValueError):
        _parse_ladder("mean:1,mean:2") # duplicate mean term
    with pytest.raises(ValueError):
        _parse_ladder("194:nan")       # non-finite weight
    with pytest.raises(ValueError):
        _parse_ladder("inf:1")         # non-finite threshold
    with pytest.raises(ValueError):
        _parse_ladder("0:1")           # empty-book baseline already clears
    with pytest.raises(ValueError):
        _parse_ladder("-1:1")          # thresholds must be positive
    with pytest.raises(ValueError):
        _parse_ladder("194:1,")         # empty entry


def test_ladder_rejects_nonfinite_matrix_and_direct_spec_values():
    totals = np.ones((3, 4), dtype=float)
    totals[0, 0] = np.nan
    with pytest.raises(ValueError, match="finite matrix"):
        select_ladder_entries(totals, 2, {194.0: 1.0})
    with pytest.raises(ValueError, match="threshold or weight"):
        select_ladder_entries(np.ones((3, 4)), 2, {np.inf: 1.0})
    with pytest.raises(ValueError, match="threshold or weight"):
        select_ladder_entries(np.ones((3, 4)), 2, {0.0: 1.0})
    with pytest.raises(ValueError, match="mean weight"):
        select_ladder_entries(
            np.ones((3, 4)), 2, {194.0: 1.0}, mean_weight=np.nan,
        )
    with pytest.raises(ValueError, match="nonnegative candidate totals"):
        select_ladder_entries(
            np.array([[200.0, -1.0], [195.0, 0.0]]),
            1,
            {194.0: 1.0},
            mean_weight=0.1,
        )


@pytest.mark.parametrize("alpha", ["-0.1", "nan", "inf"])
def test_lse_parameter_fails_closed(alpha):
    with pytest.raises(ValueError, match="finite and nonnegative"):
        select_tail_entries(
            np.ones((2, 3)), 1, 194.0,
            env={"SELECT_LSE": alpha, "SELECT_LADDER": ""},
        )


def test_lse_and_ladder_are_mutually_exclusive():
    with pytest.raises(ValueError, match="mutually exclusive"):
        select_tail_entries(
            np.ones((2, 3)), 1, 194.0,
            env={"SELECT_LSE": "0.1", "SELECT_LADDER": "194:1"},
        )


def test_lever_is_registered():
    assert "SELECT_LADDER" in engine._lever_keys
