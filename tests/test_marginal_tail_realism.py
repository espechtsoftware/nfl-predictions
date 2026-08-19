"""Offline tests for the marginal upper-tail realism machinery."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.marginal_tail_realism import (
    TailRealismError,
    apply_tail_shrink,
    assert_ranks_preserved,
    effect_census,
    fit_tail_shrink,
    point_in_time_ceiling,
)


def _draws(seed: int = 3, n: int = 5000) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.gamma(2.0, 6.0, size=n)


def test_fit_tail_shrink_lands_target_on_ceiling():
    draws = _draws()
    anchor = float(np.quantile(draws, 0.95))
    target = float(np.quantile(draws, 0.999))
    ceiling = anchor + 0.5 * (target - anchor)
    fit = fit_tail_shrink(draws, ceiling)
    assert fit["shrink"] == pytest.approx(0.5, rel=1e-9)
    transformed = apply_tail_shrink(
        draws[None, :], np.array([fit["anchor"]]),
        np.array([fit["shrink"]]))[0]
    assert float(np.quantile(transformed, 0.999)) == pytest.approx(
        ceiling, rel=1e-6)


def test_fit_never_inflates_and_clips_to_unit():
    draws = _draws()
    generous = float(draws.max()) + 100.0
    assert fit_tail_shrink(draws, generous)["shrink"] == 1.0
    below_anchor = float(np.quantile(draws, 0.50))
    assert fit_tail_shrink(draws, below_anchor)["shrink"] == 0.0
    with pytest.raises(TailRealismError, match="1-D draw"):
        fit_tail_shrink(draws[:50], 10.0)


def test_apply_changes_only_above_anchor_and_preserves_ranks():
    draws = np.vstack([_draws(1), _draws(2)])
    anchors = np.quantile(draws, 0.95, axis=1)
    shrinks = np.array([0.4, 1.0])
    after = apply_tail_shrink(draws, anchors, shrinks)
    below = draws[0] <= anchors[0]
    assert np.array_equal(after[0][below], draws[0][below])
    assert np.array_equal(after[1], draws[1])
    assert (after[0][~below] < draws[0][~below]).all()
    assert_ranks_preserved(draws, after)
    collapsed = apply_tail_shrink(draws, anchors, np.array([0.0, 0.0]))
    assert_ranks_preserved(draws, collapsed)
    with pytest.raises(TailRealismError, match="inverted"):
        assert_ranks_preserved(draws, -draws)
    with pytest.raises(TailRealismError, match="\\[0, 1\\]"):
        apply_tail_shrink(draws, anchors, np.array([1.2, 0.5]))


def test_point_in_time_ceiling_is_strictly_walk_forward():
    history = pd.DataFrame({
        "season": [2023, 2023, 2023, 2024, 2024],
        "week":   [1,    2,    2,    1,    3],
        "id":     ["A",  "A",  "B",  "B",  "A"],
        "pos":    ["WR", "WR", "WR", "WR", "WR"],
        "actual": [10.0, 30.0, 20.0, 25.0, 99.0],
    })
    ceilings = point_in_time_ceiling(history, season=2024, week=3)
    # Rows at or after 2024 w3 (A's 99.0) must not leak in.
    pos_q = np.quantile([10.0, 30.0, 20.0, 25.0], 0.999)
    assert ceilings["A"] == pytest.approx(1.1 * max(30.0, pos_q))
    assert ceilings["B"] == pytest.approx(1.1 * max(25.0, pos_q))
    with pytest.raises(TailRealismError, match="no realized history"):
        point_in_time_ceiling(history, season=2023, week=1)


def test_effect_census_discloses_movement():
    draws = np.vstack([_draws(1), _draws(2)])
    anchors = np.quantile(draws, 0.95, axis=1)
    shrinks = np.array([0.4, 1.0])
    after = apply_tail_shrink(draws, anchors, shrinks)
    census = effect_census(draws, after, shrinks)
    assert census["n_players"] == 2
    assert 0.0 < census["fraction_draws_changed"] < 0.06
    assert census["fraction_players_shrunk"] == pytest.approx(0.5)
    assert census["fraction_players_collapsed"] == 0.0
    assert census["max_abs_change"] > 0.0
