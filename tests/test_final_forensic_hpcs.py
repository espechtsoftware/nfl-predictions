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
            "team": "A", "opp": "B", "game_id": "B@A", "salary": 7000,
            "authoritative_actual": 25.0,
        },
        {
            "season": 2025, "week": 1, "id": "DST_A", "pos": "DST",
            "team": "A", "opp": "B", "game_id": "B@A", "salary": None,
            "authoritative_actual": 8.0,
        },
    ])
    return features, authoritative


def test_authoritative_universe_requires_exact_membership_and_scores():
    features, authoritative = _universe_frames()
    analyzer._verify_universe(features, authoritative)

    with pytest.raises(RuntimeError, match="salary-listed universe differs"):
        analyzer._verify_universe(features.iloc[:1], authoritative)

    wrong = authoritative.copy()
    wrong.loc[wrong.id.eq("qb"), "authoritative_actual"] = 26.0
    with pytest.raises(RuntimeError, match="authoritative actuals"):
        analyzer._verify_universe(features, wrong)
