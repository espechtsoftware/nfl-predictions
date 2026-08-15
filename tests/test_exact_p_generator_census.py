from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.research import exact_p_generator_census as census


def test_reconstruct_cbwu_uses_frozen_quota_then_fill_order():
    books = {
        seed: [
            (f"{seed}-a", ("lev",)),
            (f"{seed}-b", ("boom",)),
        ]
        for seed in census.SEED_ORDER
    }

    assert census.reconstruct_cbwu(books) == [
        (census.SEED_ORDER[0], f"{census.SEED_ORDER[0]}-a"),
        (census.SEED_ORDER[1], f"{census.SEED_ORDER[1]}-a"),
    ]


def _fixture() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = [f"p{index}" for index in range(9)]
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"]
    teams = ["A", "C", "E", "A", "A", "B", "G", "I", "K"]
    opponents = ["B", "D", "F", "B", "B", "A", "H", "J", "L"]
    salaries = [6000] * 7 + [4000, 3000]
    player_rows = []
    native_rows = []
    retained_rows = []
    p_rows = []
    slate_keys = [
        (season, week)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    ]
    for season, week in slate_keys:
        for player, pos, team, opp, salary in zip(
            base, positions, teams, opponents, salaries, strict=True,
        ):
            player_rows.append({
                "season": season,
                "week": week,
                "id": player,
                "pos": pos,
                "team": team,
                "opp": opp,
                "game_id": "unused",
                "salary": salary,
            })
        for seed_index, seed in enumerate(census.SEED_ORDER):
            wr = f"x{seed_index}"
            te = f"t{seed_index}"
            player_rows.extend([
                {
                    "season": season, "week": week, "id": wr, "pos": "WR",
                    "team": f"X{seed_index}", "opp": f"Y{seed_index}",
                    "game_id": "unused", "salary": 4000,
                },
                {
                    "season": season, "week": week, "id": te, "pos": "TE",
                    "team": f"T{seed_index}", "opp": f"U{seed_index}",
                    "game_id": "unused", "salary": 6000,
                },
            ])
            first = tuple(sorted([*base[:7], wr, base[8]]))
            second = tuple(sorted([*base[:6], te, base[7], base[8]]))
            family = "lev" if seed_index % 2 == 0 else "boom"
            for cand_ix, roster in enumerate((first, second)):
                native_rows.append({
                    "season": season,
                    "week": week,
                    "panel_run_id": seed,
                    "cand_ix": cand_ix,
                    "players": ",".join(roster),
                    "tag": family,
                    "all_tags": json.dumps([family]),
                })
        retained_rows.extend([
            {
                "season": season,
                "week": week,
                "candidate_index": 0,
                "players": native_rows[-10]["players"],
                "tag": "CBWU_R0",
            },
            {
                "season": season,
                "week": week,
                "candidate_index": 1,
                "players": native_rows[-8]["players"],
                "tag": "CBWU_R1",
            },
        ])
        p_rows.append({
            "season": season,
            "week": week,
            "players": ",".join(sorted(base)),
        })
    return tuple(map(pd.DataFrame, (
        player_rows, native_rows, retained_rows, p_rows,
    )))


def test_census_identifies_native_generation_search_without_scores():
    result = census.analyze_exact_p_generator_census(*_fixture())

    assert result["slates"] == 54
    assert result["disposition"] == "native-generation-search-dominant"
    assert result["loss_stage_counts"] == {
        "native_generation_search": 54,
        "fixed_budget_admission": 0,
        "invalid_retained": 0,
    }
    assert not result["uses_candidate_or_lineup_scores"]
    assert not result["production_change_licensed"]
    assert result["records"][0]["p_player_representation"]["combination_absent"]


def test_census_preflight_proves_plumbing_without_membership_disclosure():
    players, native, retained, exact_p = _fixture()
    mask = players.season.eq(2023)
    result = census.validate_exact_p_census_plumbing(
        players[mask].copy(),
        native[native.season.eq(2023)].copy(),
        retained[retained.season.eq(2023)].copy(),
        exact_p[exact_p.season.eq(2023)].copy(),
        expected_slates=18,
    )

    assert result["slates"] == 18
    assert result["exact_p_source_resolved"]
    assert result["retained_cbwu_reproduced"]
    assert result["membership_or_distance_values_persisted"] is False
    assert result["candidate_yield_persisted"] is False
    assert result["loss_stage_or_disposition_persisted"] is False
    assert result["scientific_result_licensed"] is False
    encoded = json.dumps(result)
    assert "exact_p_in_native_union" not in encoded
    assert "loss_stage_counts" not in encoded


def test_census_rejects_any_candidate_outcome_column():
    players, native, retained, exact_p = _fixture()
    native["actual_score"] = 0.0

    with pytest.raises(ValueError, match="forbidden columns"):
        census.analyze_exact_p_generator_census(
            players, native, retained, exact_p,
        )


def test_cloud_runner_does_not_use_reserved_rows_alias():
    source = Path("scripts/run_exact_p_generator_constraint_census.py").read_text(
        encoding="utf-8",
    )

    assert "COUNT(*) AS rows" not in source
    assert "COUNT(*) AS row_count" in source
    assert "_load_corrected_identities" in source
    assert "oracle_rosters_repair4`\n        WHERE" not in source
    assert "--identity-generation" in source
    assert "validate_exact_p_census_plumbing" in source


def test_exact_p_census_finisher_is_strict_and_create_only():
    source = Path(
        "scripts/cloud_finish_exact_p_generator_constraint_census.sh"
    ).read_text(encoding="utf-8")

    assert "[ ! -e \"$OUT/report.json\" ]" in source
    assert "uses_candidate_or_lineup_scores" in source
    assert "production_change_licensed" in source
    assert "sum(int(value) for value in loss.values()) != 54" in source
    assert "exact_p_in_retained_cbwu" in source


def test_corrected_source_census_launcher_requires_narrow_preflight():
    launch = Path(
        "scripts/cloud_exact_p_generator_census_source1.sh"
    ).read_text(encoding="utf-8")
    finish = Path(
        "scripts/cloud_finish_exact_p_generator_census_source1.sh"
    ).read_text(encoding="utf-8")
    identity_finish = Path(
        "scripts/cloud_finish_exact_p_corrected_identity_source.sh"
    ).read_text(encoding="utf-8")

    assert "strict exact-P census plumbing preflight is absent" in launch
    assert "strict full corrected-identity harvest is absent" in launch
    assert "identity_generation" in launch
    assert "membership_or_distance_values_persisted" in finish
    assert '"disposition" in r' in finish
    assert "generation.txt" in identity_finish
