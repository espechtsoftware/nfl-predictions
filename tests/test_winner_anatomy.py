"""Offline tests for the winner anatomy diagnostics."""
from __future__ import annotations

import math

import pytest

from nfl_dfs.analysis.winner_anatomy import (
    WinnerAnatomyError,
    anatomy_report,
    optimum_realism,
    ownership_profile,
    same_team_code,
)


def test_ownership_profile_full_and_partial():
    full = ownership_profile([20.0, 15.0, 9.9, 4.9, 3.0, 2.0, 1.0, 30.0, 8.0])
    assert full["n_matched"] == 9
    assert full["sum_pct"] == pytest.approx(93.8)
    assert full["n_below_5"] == 4
    assert full["n_below_10"] == 6
    assert full["min_pct"] == pytest.approx(1.0)
    expected_log = sum(math.log10(p / 100.0) for p in
                       (20.0, 15.0, 9.9, 4.9, 3.0, 2.0, 1.0, 30.0, 8.0))
    assert full["log10_product"] == pytest.approx(expected_log)

    partial = ownership_profile([20.0, None, 5.0] + [None] * 6)
    assert partial["n_matched"] == 2
    assert partial["sum_pct"] == pytest.approx(25.0)

    empty = ownership_profile([None] * 9)
    assert empty["n_matched"] == 0 and empty["sum_pct"] is None

    with pytest.raises(WinnerAnatomyError, match="nine slots"):
        ownership_profile([10.0] * 8)
    with pytest.raises(WinnerAnatomyError, match="outside"):
        ownership_profile([0.0] + [10.0] * 8)


def test_optimum_realism_counts_and_guards():
    roster = [f"P{i}" for i in range(9)]
    world = {p: 30.0 for p in roster}
    world["P0"] = 55.0
    world["P1"] = 41.0
    ceilings = {p: 40.0 for p in roster}
    del ceilings["P2"]
    result = optimum_realism(world, ceilings, roster)
    assert result["n_beyond_realized_max"] == 2
    assert set(result["players_beyond"]) == {"P0", "P1"}
    assert result["n_never_realized"] == 1
    assert result["excess_total"] == pytest.approx(16.0)
    assert result["max_single_excess"] == pytest.approx(15.0)

    with pytest.raises(WinnerAnatomyError, match="world scores"):
        optimum_realism({p: 1.0 for p in roster[:-1]}, ceilings, roster)
    with pytest.raises(WinnerAnatomyError, match="unique"):
        optimum_realism(world, ceilings, ["P0"] * 9)


def test_same_team_code_aliases():
    assert same_team_code("JAX", "JAC")
    assert same_team_code("was", "WSH")
    assert same_team_code("LAR", "LA")
    assert not same_team_code("KC", "GB")


def _entry(season, week, constructible, ownership, pool_overlap):
    return {
        "season": season, "week": week,
        "production_valid": constructible,
        "overlap": {
            "pool": {"max_overlap": pool_overlap},
            "selected": {"max_overlap": pool_overlap - 1},
            "exact_winner_in_pool": pool_overlap == 9,
        },
        "ownership": ownership,
        "realism": {
            "optimum": {"n_beyond_realized_max": 2, "excess_total": 12.0},
            "winner": {"n_beyond_realized_max": 0, "excess_total": 0.0},
        },
    }


def test_anatomy_report_aggregates_and_flags():
    own = ownership_profile([10.0] * 9)
    report = anatomy_report([
        _entry(2023, 1, True, own, 9),
        _entry(2023, 2, False, None, 5),
    ])
    assert report["n_winners"] == 2
    assert report["overlap"]["all"]["n_exact_in_pool"] == 1
    assert report["overlap"]["constructible"]["n"] == 1
    assert report["overlap"]["rule_violating"]["pool_max_overlap_min"] == 5
    assert report["ownership"]["n_with_ownership"] == 1
    assert report["ownership"]["fully_matched"] == 1
    assert report["realism"]["optima_with_any_beyond_max"] == 2
    assert report["realism"]["winners_with_any_beyond_max"] == 0
    assert report["uses_realized_outcomes"] is True
    assert report["gate_decision"] is None
    with pytest.raises(WinnerAnatomyError, match="duplicate"):
        anatomy_report([
            _entry(2023, 1, True, own, 9),
            _entry(2023, 1, True, own, 9),
        ])
