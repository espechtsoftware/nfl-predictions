from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_final_forensic_hpcs",
    ROOT / "scripts/run_final_forensic_hpcs.py",
)
assert SPEC and SPEC.loader
analyzer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analyzer)


def _prelock():
    return [{
        "id": "scope",
        "expected_rows": 2,
        "expected_player_rows": 3,
        "expected_slates": 1,
        "seasons": [2025],
        "prelock_row_hash": "hash",
        "prelock_candidate_summary": {"row_count": 2},
        "prelock_feature_summary": {"row_count": 3},
    }]


def test_prelock_comparison_fails_on_any_drift():
    analyzer._prelock_equal(_prelock(), _prelock())
    drifted = _prelock()
    drifted[0]["prelock_row_hash"] = "changed"
    with pytest.raises(RuntimeError, match="prelock drift"):
        analyzer._prelock_equal(_prelock(), drifted)


def _universe_frames():
    features = pd.DataFrame([
        {
            "season": 2025, "week": 1, "id": "qb", "pos": "QB",
            "team": "A", "opp": "B", "game_id": "B@A", "salary": 7000,
            "actual": 25.0,
        },
        {
            "season": 2025, "week": 1, "id": "DST_A", "pos": "DST",
            "team": "A", "opp": "B", "game_id": "B@A", "salary": 3000,
            "actual": 8.0,
        },
    ])
    authoritative = pd.DataFrame([
        {
            "season": 2025, "week": 1, "id": "qb", "pos": "QB",
            "name": "Quarter Back", "team": "A", "opp": "B",
            "game_id": "B@A", "kickoff_time": "13:00", "salary": 7000,
            "authoritative_actual": 25.0,
        },
        {
            "season": 2025, "week": 1, "id": "DST_A", "pos": "DST",
            "name": "A DST", "team": "A", "opp": "B",
            "game_id": "B@A", "kickoff_time": "13:00", "salary": None,
            "authoritative_actual": 8.0,
        },
    ])
    return features, authoritative


def test_authoritative_universe_requires_feature_subset_and_exact_scores():
    features, authoritative = _universe_frames()
    reconciled, audit = analyzer._reconcile_universe(features, authoritative)
    assert len(reconciled) == 2
    assert audit["authoritative_only_rows"] == 0

    with pytest.raises(RuntimeError, match="absent from authoritative"):
        analyzer._reconcile_universe(features, authoritative.iloc[:1])

    wrong = authoritative.copy()
    wrong.loc[wrong.id.eq("qb"), "authoritative_actual"] = 26.0
    with pytest.raises(RuntimeError, match="authoritative actuals"):
        analyzer._reconcile_universe(features, wrong)


def test_authoritative_only_skill_player_expands_hindsight_universe():
    features, authoritative = _universe_frames()
    authoritative = pd.concat([
        authoritative,
        pd.DataFrame([{
            "season": 2025, "week": 1, "id": "wr_extra", "pos": "WR",
            "name": "Extra Receiver", "team": "A", "opp": "B",
            "game_id": "B@A", "kickoff_time": "13:00", "salary": 3000,
            "authoritative_actual": 20.0,
        }]),
    ], ignore_index=True)

    reconciled, audit = analyzer._reconcile_universe(features, authoritative)

    extra = reconciled[reconciled.id.eq("wr_extra")].iloc[0]
    assert len(reconciled) == 3
    assert audit["authoritative_only_rows"] == 1
    assert audit["authoritative_only_by_position"] == {"WR": 1}
    assert extra.actual == 20.0
    assert extra.feature_missing == '["missing_frozen_feature_row"]'
    assert "authoritative_only_no_frozen_feature_row" in extra.source_features_json


def test_authoritative_universe_accepts_different_source_game_ids():
    features, authoritative = _universe_frames()
    features["game_id"] = ["2025_01_A_B", "DST_SOURCE_A_B"]
    authoritative["game_id"] = ["A@B", "B@A"]
    reconciled, audit = analyzer._reconcile_universe(features, authoritative)
    assert len(reconciled) == 2
    assert audit["frozen_rows_verified_against_authoritative"] is True


def test_actual_ownership_join_matches_names_without_using_dst():
    features = pd.DataFrame([
        {
            "season": 2025, "week": 1, "id": "p1", "name": "Odell Beckham Jr.",
            "pos": "WR",
        },
        {
            "season": 2025, "week": 1, "id": "DST_A", "name": "A DST",
            "pos": "DST",
        },
    ])
    ownership = pd.DataFrame([
        {
            "season": 2025, "week": 1, "display_name": "Odell Beckham",
            "actual_ownership": 7.5, "actual_ownership_contests": 3,
        }
    ])

    joined, audit = analyzer._attach_actual_ownership(features, ownership)

    assert joined.loc[joined.id.eq("p1"), "actual_ownership"].iloc[0] == 7.5
    assert pd.isna(joined.loc[joined.id.eq("DST_A"), "actual_ownership"].iloc[0])
    assert audit["match_rate_when_available"] == 1.0
    assert audit["overall_match_rate"] == 1.0
    assert audit["selection_use"] == "forbidden_outcome_only"


def test_actual_ownership_join_excludes_ambiguous_reference_names():
    features = pd.DataFrame([
        {"season": 2025, "week": 1, "id": "p1", "name": "Chris Smith", "pos": "WR"},
        {"season": 2025, "week": 1, "id": "p2", "name": "Chris Smith", "pos": "TE"},
    ])
    ownership = pd.DataFrame([{
        "season": 2025, "week": 1, "display_name": "Chris Smith",
        "actual_ownership": 7.5, "actual_ownership_contests": 3,
    }])

    joined, audit = analyzer._attach_actual_ownership(features, ownership)

    assert joined.actual_ownership.isna().all()
    assert audit["ambiguous_reference_rows_excluded"] == 2
    assert audit["matched_player_rows"] == 0


def test_route_history_reconstruction_is_strictly_prior_and_source_verified():
    features = pd.DataFrame([
        {
            "season": 2023, "week": 2, "id": "p1",
            "fp_route_source_season": 2023,
            "fp_route_source_week": 1,
        },
        {
            "season": 2023, "week": 1, "id": "p2",
            "fp_route_source_season": 2022,
            "fp_route_source_week": 18,
        },
    ])
    history = pd.DataFrame([
        {"season": 2023, "week": 1, "gsis_id": "p1", "route_share": 0.70},
        {"season": 2023, "week": 2, "gsis_id": "p1", "route_share": 0.99},
        {"season": 2022, "week": 18, "gsis_id": "p2", "route_share": 0.65},
    ])

    joined = analyzer._attach_route_history(features, history)

    assert joined.loc[joined.id.eq("p1"), "fp_route_share_last"].iloc[0] == 0.70
    assert joined.loc[joined.id.eq("p2"), "fp_route_share_last"].iloc[0] == 0.65
    wrong = features.copy()
    wrong.loc[wrong.id.eq("p1"), "fp_route_source_week"] = 2
    with pytest.raises(RuntimeError, match="strict-prior route reconstruction"):
        analyzer._attach_route_history(wrong, history)
