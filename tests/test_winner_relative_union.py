"""Frozen-B1 generated-union versus Milly winner, without oracle mixing."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from nfl_dfs.analysis.winner_relative_union import (
    WinnerRelativeUnionError,
    score_cents,
    winner_relative_union_census,
)


LEGAL_A = (
    "QB_T0", "RB_T20", "RB_T30", "WR_T00", "WR_T01", "WR_T10",
    "TE_T20", "WR_T20", "DST_T1",
)
LEGAL_B = (
    "QB_T2", "RB_T00", "RB_T10", "WR_T20", "WR_T21", "WR_T30",
    "TE_T00", "TE_T10", "DST_T3",
)
# DK-legal but outside the old production QB+2/bring-back strategy region.
OPEN_SHAPE = (
    "QB_T0", "RB_T20", "RB_T30", "WR_T00", "WR_T20", "WR_T21",
    "TE_T30", "WR_T30", "DST_T1",
)


def _players() -> pd.DataFrame:
    rows = []
    games = {
        "T0": ("T1", "g0"), "T1": ("T0", "g0"),
        "T2": ("T3", "g1"), "T3": ("T2", "g1"),
    }
    ix = 0
    for team, (opp, game) in games.items():
        specs = [
            (f"QB_{team}", "QB"),
            (f"RB_{team}0", "RB"), (f"RB_{team}1", "RB"),
            (f"WR_{team}0", "WR"), (f"WR_{team}1", "WR"),
            (f"WR_{team}2", "WR"),
            (f"TE_{team}0", "TE"), (f"TE_{team}1", "TE"),
            (f"DST_{team}", "DST"),
        ]
        for player_id, pos in specs:
            rows.append({
                "season": 2025,
                "week": 1,
                "id": player_id,
                "name": f"Name {player_id}",
                "pos": pos,
                "team": team,
                "opp": opp,
                "game_id": game,
                "salary": 5_500,
                "actual": 8.0 + ix / 4.0,
            })
            ix += 1
    return pd.DataFrame(rows)


def _score(roster: tuple[str, ...], players: pd.DataFrame) -> float:
    actual = dict(zip(players.id, players.actual))
    return float(sum(actual[player] for player in roster))


def _candidates(*, include_open: bool = False) -> pd.DataFrame:
    players = _players()
    rows = [
        {
            "panel_run_id": "panel-a", "season": 2025, "week": 1,
            "cand_ix": 0, "tag": "boom", "all_tags": json.dumps(["boom"]),
            "selected": False, "selected_rank": -1,
            "players": ",".join(LEGAL_A),
            "actual_score": _score(LEGAL_A, players),
        },
        {
            # The same exact roster was selected by a second source panel.
            "panel_run_id": "panel-b", "season": 2025, "week": 1,
            "cand_ix": 0, "tag": "dark",
            "all_tags": json.dumps(["dark", "boom"]),
            "selected": True, "selected_rank": 0,
            "players": ",".join(reversed(LEGAL_A)),
            "actual_score": _score(LEGAL_A, players),
        },
        {
            "panel_run_id": "panel-b", "season": 2025, "week": 1,
            "cand_ix": 1, "tag": "lev", "all_tags": json.dumps(["lev"]),
            "selected": False, "selected_rank": -1,
            "players": ",".join(LEGAL_B),
            "actual_score": _score(LEGAL_B, players),
        },
    ]
    if include_open:
        rows.append({
            "panel_run_id": "panel-a", "season": 2025, "week": 1,
            "cand_ix": 1, "tag": "open", "all_tags": json.dumps(["open"]),
            "selected": False, "selected_rank": -1,
            "players": ",".join(OPEN_SHAPE),
            "actual_score": _score(OPEN_SHAPE, players),
        })
    return pd.DataFrame(rows)


def _run(winner_score: float, *, include_open: bool = False) -> dict:
    expected_distinct = 3 if include_open else 2
    return winner_relative_union_census(
        _candidates(include_open=include_open),
        _players(),
        {(2025, 1): winner_score},
        {"panel-a": "family-a", "panel-b": "family-b"},
        expected_panels=["panel-a", "panel-b"],
        expected_slates=1,
        expected_distinct_legal_rosters=expected_distinct,
        expected_winner_slates=1,
    )


def test_exact_generated_identity_sources_selection_and_anatomy():
    players = _players()
    best = max(_score(LEGAL_A, players), _score(LEGAL_B, players))
    report = _run(best - 1.0)
    slate = report["per_slate"][0]
    assert report["summary"]["slates_beaten"] == 1
    assert slate["best_class"] == "beat"
    assert slate["union_margin"] == pytest.approx(1.0)
    assert len(slate["best_rosters"]) == 1
    roster = slate["best_rosters"][0]
    assert roster["roster_ids"] == sorted(
        LEGAL_A if _score(LEGAL_A, players) == best else LEGAL_B)
    if set(roster["roster_ids"]) == set(LEGAL_A):
        assert roster["selected_any"] is True
        assert {source["panel_run_id"] for source in roster["sources"]} == {
            "panel-a", "panel-b"}
        assert roster["selected_sources"][0]["selected_rank"] == 0
        assert roster["generator_tags"] == ["boom", "dark"]
    assert roster["anatomy"]["salary_total"] == 49_500
    assert roster["anatomy"]["flex_position"] in {"RB", "WR", "TE"}
    assert len(roster["anatomy"]["players"]) == 9
    assert report["labels"]["contains_only_actually_generated_rosters"] is True
    assert report["labels"]["contains_hindsight_h_or_p"] is False
    assert report["labels"]["contains_simulated_world_optima"] is False


def test_tie_and_near_buckets_use_published_score_cents():
    players = _players()
    best = max(_score(LEGAL_A, players), _score(LEGAL_B, players))
    tied = _run(best)
    assert tied["summary"]["slates_tied"] == 1
    assert tied["summary"]["slates_within_10_or_better"] == 1
    near = _run(best + 9.999)
    assert near["summary"]["slates_within_10_loss"] == 1
    assert near["per_slate"][0]["best_class"] == "within_10_loss"
    assert score_cents(best + 9.999) - score_cents(best) == 1_000
    farther = _run(best + 24.999)
    assert farther["summary"]["slates_within_25_loss"] == 1


def test_b1_legality_does_not_reimpose_strategy_rules():
    players = _players()
    best = max(
        _score(LEGAL_A, players),
        _score(LEGAL_B, players),
        _score(OPEN_SHAPE, players),
    )
    report = _run(best + 40.0, include_open=True)
    assert report["population"]["distinct_legal_generated_rosters"] == 3
    open_ids = sorted(OPEN_SHAPE)
    open_records = [
        record for record in report["per_slate"][0]["best_rosters"]
        if record["roster_ids"] == open_ids
    ]
    if open_records:
        assert open_records[0]["anatomy"]["full_production_shape"] is False


def test_label_reconciliation_and_population_gates_fail_closed():
    candidates = _candidates()
    candidates.loc[0, "actual_score"] += 0.02
    with pytest.raises(WinnerRelativeUnionError, match="labels disagree"):
        winner_relative_union_census(
            candidates,
            _players(),
            {(2025, 1): 200.0},
            {"panel-a": "family-a", "panel-b": "family-b"},
            expected_panels=["panel-a", "panel-b"],
            expected_slates=1,
            expected_distinct_legal_rosters=2,
            expected_winner_slates=1,
        )
    with pytest.raises(WinnerRelativeUnionError, match="distinct-roster count"):
        winner_relative_union_census(
            _candidates(),
            _players(),
            {(2025, 1): 200.0},
            {"panel-a": "family-a", "panel-b": "family-b"},
            expected_panels=["panel-a", "panel-b"],
            expected_slates=1,
            expected_distinct_legal_rosters=999,
            expected_winner_slates=1,
        )
