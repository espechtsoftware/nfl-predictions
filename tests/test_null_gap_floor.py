"""Null-calibrated construction floor (S1): oracle chain ordering, exact
C/S sums, world sensitivity, aggregation, and fail-closed validation."""
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.null_gap_floor import (
    NullGapError,
    aggregate_null_floor,
    slate_null_gaps,
)


def _players():
    """Feasible 36-player slate: 4 teams, 2 games, flat $5,500 salaries so
    every nine-player roster lands inside the $49k-$50k window."""
    rows = []
    games = {"T0": ("T1", "g0"), "T1": ("T0", "g0"),
             "T2": ("T3", "g1"), "T3": ("T2", "g1")}
    for team, (opp, game) in games.items():
        rows.append((f"QB_{team}", "QB", team, opp, game))
        for k in range(2):
            rows.append((f"RB_{team}{k}", "RB", team, opp, game))
        for k in range(3):
            rows.append((f"WR_{team}{k}", "WR", team, opp, game))
        for k in range(2):
            rows.append((f"TE_{team}{k}", "TE", team, opp, game))
        rows.append((f"DST_{team}", "DST", team, opp, game))
    return pd.DataFrame(
        rows, columns=["id", "pos", "team", "opp", "game_id"]
    ).assign(salary=5500, actual=0.0)


# Two legal rosters under QB+2 / one bring-back / RB rules.
R1 = ("QB_T0", "RB_T20", "RB_T30", "WR_T00", "WR_T01", "WR_T10",
      "TE_T20", "WR_T20", "DST_T1")
R2 = ("QB_T2", "RB_T00", "RB_T10", "WR_T20", "WR_T21", "WR_T30",
      "TE_T00", "TE_T10", "DST_T3")


def _world(pump_teams, base=8.0, boost=25.0):
    players = _players()
    return {
        row.id: (boost if row.team in pump_teams else base)
        for row in players.itertuples(index=False)
    }


def test_chain_ordering_and_exact_sums():
    players = _players()
    world = _world({"T0", "T1"})
    result = slate_null_gaps(players, [R1, R2], [0], world)
    assert result["h"] >= result["p"] >= result["c"] >= result["s"]
    assert result["c"] == pytest.approx(
        max(sum(world[p] for p in R1), sum(world[p] for p in R2)))
    assert result["s"] == pytest.approx(sum(world[p] for p in R1))
    assert result["support_size"] == len(set(R1) | set(R2))
    for key in ("h_minus_p", "p_minus_c", "c_minus_s"):
        assert result[key] >= -1e-9


def test_world_substitution_moves_the_chain():
    players = _players()
    g0_world = slate_null_gaps(players, [R1, R2], [0], _world({"T0", "T1"}))
    g1_world = slate_null_gaps(
        players, [R1, R2], [0], _world({"T2", "T3"}, boost=31.0))
    assert g0_world["h"] != g1_world["h"]
    # R1 stacks game g0, R2 stacks game g1: the pool best must flip.
    assert g0_world["s"] != g1_world["s"] or g0_world["c"] != g1_world["c"]


def test_deterministic():
    players = _players()
    world = _world({"T0", "T1"})
    first = slate_null_gaps(players, [R1, R2], [0], world)
    second = slate_null_gaps(players, [R1, R2], [0], world)
    assert first == second


def test_aggregation_reports_winnable_share():
    results = [
        {"h_minus_p": 2.0, "p_minus_c": 50.0, "c_minus_s": 3.0},
        {"h_minus_p": 4.0, "p_minus_c": 60.0, "c_minus_s": 5.0},
        {"h_minus_p": 6.0, "p_minus_c": 70.0, "c_minus_s": 7.0},
    ]
    report = aggregate_null_floor(results)
    gap = report["gaps"]["p_minus_c"]
    assert gap["null_median"] == pytest.approx(60.0)
    assert gap["winnable_vs_null_median"] == pytest.approx(68.914 - 60.0)
    assert gap["fraction_null_at_or_above_observed"] == pytest.approx(1 / 3)
    assert report["uses_realized_outcomes"] is False


def test_fail_closed_validation():
    players = _players()
    world = _world({"T0"})
    with pytest.raises(NullGapError):
        slate_null_gaps(players, [], [0], world)
    with pytest.raises(NullGapError):
        slate_null_gaps(players, [R1], [1], world)
    incomplete = dict(world)
    incomplete.pop("QB_T0")
    with pytest.raises(NullGapError):
        slate_null_gaps(players, [R1, R2], [0], incomplete)
    with pytest.raises(NullGapError):
        slate_null_gaps(
            players, [R1[:8] + ("QB_T0",)], [0], world)  # duplicate id
    with pytest.raises(NullGapError):
        aggregate_null_floor([])
