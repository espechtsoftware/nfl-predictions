"""All-arms union census (B1): legality revalidation, revaluation from
corrected snapshots, attribution, aggregation, and fail-closed checks."""
import pandas as pd
import pytest

from nfl_dfs.research.all_arms_union import (
    UnionCensusError,
    slate_union_census,
    union_census_report,
)


def _players():
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
    frame = pd.DataFrame(
        rows, columns=["id", "pos", "team", "opp", "game_id"])
    frame["salary"] = 5500
    frame["actual"] = [10.0 + i for i in range(len(frame))]
    return frame


LEGAL_A = ("QB_T0", "RB_T20", "RB_T30", "WR_T00", "WR_T01", "WR_T10",
           "TE_T20", "WR_T20", "DST_T1")
LEGAL_B = ("QB_T2", "RB_T00", "RB_T10", "WR_T20", "WR_T21", "WR_T30",
           "TE_T00", "TE_T10", "DST_T3")
# No QB+2 stack: only one T0 pass catcher with QB_T0.
ILLEGAL = ("QB_T0", "RB_T20", "RB_T30", "WR_T00", "WR_T20", "WR_T21",
           "TE_T30", "WR_T30", "DST_T1")


def _candidates():
    players = _players()
    actual = dict(zip(players.id, players.actual))
    rows = []
    for panel, roster in (
        ("panel-one", LEGAL_A), ("panel-two", LEGAL_A),
        ("panel-two", LEGAL_B), ("panel-three", ILLEGAL),
    ):
        rows.append({
            "panel_run_id": panel,
            "players": ",".join(roster),
            "actual_score": sum(actual[p] for p in roster),
        })
    return pd.DataFrame(rows)


def test_union_census_revalidates_and_attributes():
    result = slate_union_census(_candidates(), _players())
    assert result["n_panels"] == 3
    assert result["n_distinct_rosters"] == 3
    assert result["n_legal_rosters"] == 2
    assert result["dropped_illegal"] == 1
    players = _players()
    actual = dict(zip(players.id, players.actual))
    expected = max(sum(actual[p] for p in LEGAL_A),
                   sum(actual[p] for p in LEGAL_B))
    assert result["union_c"] == pytest.approx(expected)
    assert result["stored_label_mismatch_rosters"] == 0


def test_stored_labels_are_reconciled_not_trusted():
    candidates = _candidates()
    # Corrupt one stored label: revalued score must win, mismatch counted.
    candidates.loc[0, "actual_score"] += 50.0
    result = slate_union_census(candidates, _players())
    assert result["stored_label_mismatch_rosters"] == 1
    players = _players()
    actual = dict(zip(players.id, players.actual))
    expected = max(sum(actual[p] for p in LEGAL_A),
                   sum(actual[p] for p in LEGAL_B))
    assert result["union_c"] == pytest.approx(expected)


def test_unmatched_players_are_dropped_and_counted():
    candidates = _candidates()
    ghost = LEGAL_B[:8] + ("GHOST",)
    candidates = pd.concat([candidates, pd.DataFrame([{
        "panel_run_id": "panel-four",
        "players": ",".join(ghost),
        "actual_score": 0.0,
    }])], ignore_index=True)
    result = slate_union_census(candidates, _players())
    assert result["dropped_unmatched_players"] == 1


def test_report_aggregates_and_anchors():
    rows = pd.DataFrame({
        "season": [2023, 2024], "week": [1, 2],
        "union_c": [190.0, 200.0],
        "clears_194": [False, True], "clears_240": [False, False],
    })
    report = union_census_report(
        rows, comparison={"cbwu_oi_pool_c": 186.73})
    assert report["union_c_mean"] == pytest.approx(195.0)
    assert report["union_grid"]["194"] == 1
    anchor = report["comparison_anchors"]["cbwu_oi_pool_c"]
    assert anchor["union_minus_anchor"] == pytest.approx(195.0 - 186.73)


def test_fail_closed():
    with pytest.raises(UnionCensusError):
        slate_union_census(_candidates().iloc[:0], _players())
    bad = _candidates()
    bad.loc[0, "players"] = "QB_T0,QB_T0"
    with pytest.raises(UnionCensusError):
        slate_union_census(bad, _players())
    with pytest.raises(UnionCensusError):
        union_census_report(pd.DataFrame({
            "season": [2023, 2023], "week": [1, 1],
            "union_c": [1.0, 2.0]}))
