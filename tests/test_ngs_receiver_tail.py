import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis.ngs_receiver_tail import (
    CONTROL_NUMERIC,
    NGS_FEATURES,
    _gate,
    attach_strict_prior_ngs,
    evaluate_ngs,
)


def _ngs_row(season, week, sep, targets=1, season_type="REG"):
    return {
        "season": season,
        "season_type": season_type,
        "week": week,
        "player_gsis_id": "p1",
        "targets": targets,
        "avg_separation": sep,
        "avg_cushion": sep + 1,
        "avg_intended_air_yards": sep + 2,
        "percent_share_of_intended_air_yards": sep / 10,
        "avg_yac_above_expectation": sep - 1,
    }


def test_attach_ngs_is_strict_lagged_cross_season_and_target_weighted():
    ngs = pd.DataFrame([
        _ngs_row(2023, 18, 2.0, targets=1),
        _ngs_row(2024, 0, 99.0, targets=100),
        _ngs_row(2024, 1, 4.0, targets=3),
        _ngs_row(2024, 2, 50.0, targets=1, season_type="POST"),
    ])
    targets = pd.DataFrame([
        {"season": 2024, "week": 1, "gsis_id": "p1"},
        {"season": 2024, "week": 2, "gsis_id": "p1"},
    ])
    out = attach_strict_prior_ngs(targets, ngs)
    assert out.ngs_source_season.tolist() == [2023, 2024]
    assert out.ngs_source_week.tolist() == [18, 1]
    assert out.ngs_avg_separation_l4.iloc[0] == pytest.approx(2.0)
    assert out.ngs_avg_separation_l4.iloc[1] == pytest.approx(3.5)
    assert out.ngs_prior_observations.tolist() == [1, 2]


def test_attach_ngs_leaves_uncovered_player_missing():
    ngs = pd.DataFrame([_ngs_row(2024, 1, 2.0)])
    targets = pd.DataFrame([
        {"season": 2024, "week": 1, "gsis_id": "rookie"},
    ])
    out = attach_strict_prior_ngs(targets, ngs)
    assert out.ngs_source_season.isna().all()
    assert out[list(NGS_FEATURES)].isna().all(axis=None)


def test_attach_ngs_rejects_duplicate_player_weeks():
    row = _ngs_row(2024, 1, 2.0)
    with pytest.raises(ValueError, match="duplicate player-weeks"):
        attach_strict_prior_ngs(
            pd.DataFrame([{"season": 2024, "week": 2, "gsis_id": "p1"}]),
            pd.DataFrame([row, row]),
        )


def test_ngs_gate_prioritizes_30_point_brier_with_guards():
    folds = [
        {"rows": 1000, "control_brier_30": 0.04,
         "treatment_brier_30": 0.039},
        {"rows": 1200, "control_brier_30": 0.05,
         "treatment_brier_30": 0.0504},
    ]
    aggregate = {
        "control_brier_30": 0.045, "treatment_brier_30": 0.044,
        "control_brier_20": 0.09, "treatment_brier_20": 0.089,
        "control_mae": 4.0, "treatment_mae": 3.99,
    }
    gate = _gate(folds, aggregate, {2024: 0.8, 2025: 0.7})
    assert all(gate.values())
    folds[1]["treatment_brier_30"] = 0.051
    gate = _gate(folds, aggregate, {2024: 0.8, 2025: 0.7})
    assert not gate["no_fold_brier_30_worse_over_1pct"]


def test_evaluate_ngs_runs_fixed_walk_forward_models():
    rng = np.random.default_rng(42)
    rows = []
    for season in (2019, 2021, 2022, 2023, 2024, 2025):
        for ix in range(80):
            proj = 8.0 + ix % 16
            actual = proj + rng.normal(0, 5) + (5 if ix % 17 == 0 else 0)
            row = {
                "season": season,
                "week": ix % 18 + 1,
                "gsis_id": f"{season}-{ix}",
                "pos": "WR" if ix % 3 else "TE",
                "actual": actual,
                "ngs_source_season": season - 1,
            }
            for col in CONTROL_NUMERIC:
                row[col] = proj if col == "proj" else float(ix % 7 + 1)
            for offset, col in enumerate(NGS_FEATURES):
                row[col] = float((ix + offset) % 11) / 10
            rows.append(row)
    report = evaluate_ngs(
        pd.DataFrame(rows), weighted_coverage={2024: 0.8, 2025: 0.8},
    )
    assert [fold["fold"] for fold in report["folds"]] == ["2024", "2025"]
    assert report["aggregate"]["rows"] == 160
    assert report["disposition"] == "ngs-receiver-tail-gate-fails"
