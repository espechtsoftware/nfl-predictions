from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.research import same_law_capacity_curve as capacity


def _fixture() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base_players = [
        ("q", "QB", "A", "B", 6000),
        ("rb1", "RB", "C", "H", 6000),
        ("rb2", "RB", "D", "I", 5800),
        ("wr1", "WR", "A", "B", 6000),
        ("wr2", "WR", "A", "B", 5800),
        ("wr3", "WR", "B", "A", 5000),
        ("te", "TE", "E", "J", 4800),
        ("dst", "DST", "F", "G", 5000),
        ("flex-shared", "WR", "X", "Y", 4800),
    ]
    player_rows = [
        {
            "season": 2023,
            "week": 1,
            "id": player_id,
            "pos": position,
            "team": team,
            "opp": opponent,
            "game_id": "unused",
            "salary": salary,
        }
        for player_id, position, team, opponent, salary in base_players
    ]
    for index in range(50):
        for family_index, _family in enumerate(capacity.BASE_FAMILIES):
            player_rows.append({
                "season": 2023,
                "week": 1,
                "id": f"flex-{index}-{family_index}",
                "pos": "WR",
                "team": f"X{index}-{family_index}",
                "opp": f"Y{index}-{family_index}",
                "game_id": "unused",
                "salary": 4800,
            })
    fixed = ["q", "rb1", "rb2", "wr1", "wr2", "wr3", "te", "dst"]
    candidate_rows = []
    for index, replicate in enumerate(capacity.BOOK_ORDER):
        entries = [(
            "flex-shared",
            "lev",
            ["lev", "boom"] if index == 0 else ["lev"],
        )]
        entries.extend(
            (f"flex-{index}-{family_index}", family, [family])
            for family_index, family in enumerate(capacity.BASE_FAMILIES)
        )
        for cand_ix, (flex, tag, tags) in enumerate(entries):
            candidate_rows.append({
                "season": 2023,
                "week": 1,
                "replicate": replicate,
                "cand_ix": cand_ix,
                "players": ",".join(sorted([*fixed, flex])),
                "tag": tag,
                "all_tags": json.dumps(tags),
            })
    exact_p = pd.DataFrame([{
        "season": 2023,
        "week": 1,
        "players": ",".join(sorted([*fixed, "flex-49-5"])),
    }])
    return pd.DataFrame(player_rows), pd.DataFrame(candidate_rows), exact_p


def test_seed_ledger_reproduces_all_frozen_values():
    frame = pd.read_csv(
        Path("reports/2026-08-17-same-law-capacity-curve-seeds.csv")
    )

    result = capacity.validate_seed_ledger(frame)

    assert len(result) == 50
    assert result[0] == {
        "replicate": "R0",
        "projection_seed": 0,
        "role_seed": 7331,
        "source": "existing-phase-s",
    }
    assert result[-1]["replicate"] == "R49"
    assert len({
        value
        for row in result
        for value in (row["projection_seed"], row["role_seed"])
    }) == 100


def test_seed_ledger_rejects_post_freeze_change():
    frame = pd.read_csv(
        Path("reports/2026-08-17-same-law-capacity-curve-seeds.csv")
    )
    frame.loc[5, "projection_seed"] += 1

    with pytest.raises(ValueError, match="seed identity differs"):
        capacity.validate_seed_ledger(frame)


def test_capacity_curve_is_nested_complete_and_identity_only():
    players, candidates, exact_p = _fixture()

    result = capacity.analyze_same_law_capacity_curve(
        players, candidates, exact_p, expected_slates=1,
    )

    assert result["population"] == {
        "slates": 1,
        "books": 50,
        "book_slate_cells": 50,
        "scales": ["1x", "2x", "5x", "10x"],
    }
    assert result["uses_realized_outcome_values"] is False
    assert result["uses_outcome_derived_exact_p_identity"] is True
    assert result["production_change_licensed"] is False
    assert result["disposition"] == "complete-descriptive-capacity-curve"
    cells = {row["scale"]: row for row in result["cells"]}
    assert [cells[scale]["raw_candidates"] for scale in ("1x", "2x", "5x", "10x")] == [
        35, 70, 175, 350,
    ]
    assert [cells[scale]["distinct_rosters"] for scale in ("1x", "2x", "5x", "10x")] == [
        31, 61, 151, 301,
    ]
    assert [cells[scale]["new_distinct_rosters"] for scale in ("1x", "2x", "5x", "10x")] == [
        31, 30, 90, 150,
    ]
    assert cells["1x"]["marginal_yield_slope"] is None
    assert cells["2x"]["marginal_yield_slope"] == pytest.approx(-0.2)
    assert cells["1x"]["multi_family"]["distinct_identities"] == 1
    assert cells["2x"]["multi_family"]["new_distinct_identities"] == 0
    assert cells["1x"]["exact_p"]["present"] is False
    assert cells["1x"]["exact_p"]["minimum_replacement_distance"] == 1
    assert cells["10x"]["exact_p"]["present"] is True
    assert cells["10x"]["exact_p"]["minimum_replacement_distance"] == 0
    assert result["aggregate"]["minimum_distance_step_counts"]["10x"] == {
        "improved": 1,
        "tied": 0,
        "worsened": 0,
    }
    json.dumps(result, allow_nan=False, sort_keys=True)


def test_capacity_curve_rejects_any_score_or_outcome_column():
    players, candidates, exact_p = _fixture()
    candidates["actual_score"] = 0.0

    with pytest.raises(ValueError, match="forbidden columns"):
        capacity.analyze_same_law_capacity_curve(
            players, candidates, exact_p, expected_slates=1,
        )


def test_capacity_curve_requires_every_book_on_every_slate():
    players, candidates, exact_p = _fixture()
    candidates = candidates[~candidates.replicate.eq("R49")].copy()

    with pytest.raises(ValueError, match="book population differs"):
        capacity.analyze_same_law_capacity_curve(
            players, candidates, exact_p, expected_slates=1,
        )
