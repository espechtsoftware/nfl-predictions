"""Offline tests for the winner structure census."""
from __future__ import annotations

import pytest

from nfl_dfs.analysis.winner_structure_census import (
    StructureCensusError,
    roster_structure,
    structure_census,
    structure_report,
)

POS = {
    "QB_A": "QB", "WR_A1": "WR", "WR_A2": "WR", "TE_A": "TE",
    "RB_B": "RB", "WR_B": "WR", "RB_C": "RB", "WR_D1": "WR",
    "WR_D2": "WR", "DST_C": "DST", "WR_C": "WR",
}
TEAM = {
    "QB_A": "AA", "WR_A1": "AA", "WR_A2": "AA", "TE_A": "AA",
    "RB_B": "BB", "WR_B": "BB", "RB_C": "CC", "WR_D1": "DD",
    "WR_D2": "DD", "DST_C": "CC", "WR_C": "CC",
}
OPP = {
    "QB_A": "BB", "WR_A1": "BB", "WR_A2": "BB", "TE_A": "BB",
    "RB_B": "AA", "WR_B": "AA", "RB_C": "DD", "WR_D1": "CC",
    "WR_D2": "CC", "DST_C": "DD", "WR_C": "DD",
}


def test_roster_structure_full_shape():
    roster = ["QB_A", "WR_A1", "WR_A2", "TE_A", "RB_B", "RB_C",
              "WR_D1", "WR_D2", "DST_C"]
    s = roster_structure(roster, POS, TEAM, OPP)
    assert s["qb_stack"] == 3
    assert s["bring_back"] == 1
    assert s["double_stack"] and s["full_production_shape"]
    assert not s["naked_qb"]
    # Game AA|BB holds QB_A, WR_A1, WR_A2, TE_A, RB_B = 5.
    assert s["max_game_concentration"] == 5
    assert s["n_games"] == 2
    assert s["max_secondary_stack"] == 2  # WR_D1 + WR_D2 on DD


def test_roster_structure_naked_qb():
    roster = ["QB_A", "RB_B", "RB_C", "WR_B", "WR_C", "WR_D1",
              "WR_D2", "TE_A", "DST_C"]
    # TE_A is on AA -> stack 1? TE_A shares team AA with QB_A.
    s = roster_structure(roster, POS, TEAM, OPP)
    assert s["qb_stack"] == 1
    without_te = ["QB_A", "RB_B", "RB_C", "WR_B", "WR_C", "WR_D1",
                  "WR_D2", "DST_C"]
    with pytest.raises(StructureCensusError, match="nine unique"):
        roster_structure(without_te, POS, TEAM, OPP)


def test_structure_census_distributions():
    base = {
        "qb_stack": 2, "bring_back": 1, "double_stack": True,
        "full_production_shape": True, "naked_qb": False,
        "max_game_concentration": 4, "n_games": 4,
        "max_secondary_stack": 1,
    }
    other = {**base, "qb_stack": 0, "double_stack": False,
             "full_production_shape": False, "naked_qb": True,
             "bring_back": 0}
    census = structure_census([base, base, other])
    assert census["n"] == 3
    assert census["qb_stack_dist"] == {"0": 1, "1": 0, "2": 2, "3+": 0}
    assert census["double_stack_rate"] == pytest.approx(2 / 3)
    assert census["naked_qb_rate"] == pytest.approx(1 / 3)
    assert census["bring_back_dist"] == {"0": 1, "1": 2, "2+": 0}


def test_structure_report_flags():
    census = structure_census([{
        "qb_stack": 2, "bring_back": 1, "double_stack": True,
        "full_production_shape": True, "naked_qb": False,
        "max_game_concentration": 4, "n_games": 4,
        "max_secondary_stack": 1,
    }])
    report = structure_report(census, census, census, [{"season": 2023}])
    assert report["uses_realized_outcomes"] is False
    assert report["gate_decision"] is None
    with pytest.raises(StructureCensusError, match="empty"):
        structure_report(census, census, census, [])
