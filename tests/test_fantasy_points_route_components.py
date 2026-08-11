import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import fantasy_points_route_components as diagnostic
from nfl_dfs.models import featureset


def test_route_component_features_are_opt_in(monkeypatch):
    frame = pd.DataFrame([{
        "position": "WR",
        "fp_route_share_last": 0.80,
        "fp_route_share_l4": 0.75,
        "fp_route_share_jump": 0.05,
        "fp_route_cross_season": 0,
    }])
    monkeypatch.delenv("EXTRA_FEATURES", raising=False)
    assert not set(diagnostic.ROUTE_FEATURES) & set(featureset.build_X(frame))
    monkeypatch.setenv("EXTRA_FEATURES", ",".join(diagnostic.ROUTE_FEATURES))
    assert set(diagnostic.ROUTE_FEATURES) <= set(featureset.build_X(frame))


def test_ensemble_crps_matches_two_member_example():
    draws = np.array([[0.0, 2.0], [1.0, 1.0]])
    actual = np.array([1.0, 1.0])
    assert diagnostic.ensemble_crps(draws, actual).tolist() == pytest.approx(
        [0.5, 0.0])


def test_component_gate_is_tail_first_and_requires_coverage():
    aggregate = {"control_brier_30": 0.01, "treatment_brier_30": 0.009}
    coverage = {2023: 0.80, 2024: 0.90, 2025: 1.0}
    assert diagnostic.component_gate(aggregate, coverage)["passes"]
    coverage[2023] = 0.799
    assert not diagnostic.component_gate(aggregate, coverage)["passes"]
    coverage[2023] = 0.80
    aggregate["treatment_brier_30"] = 0.011
    assert not diagnostic.component_gate(aggregate, coverage)["passes"]


def test_component_metrics_respect_rate_denominators():
    rows = pd.DataFrame([
        {
            "position": "WR", "y_targets": 2, "y_receptions": 1,
            "y_rec_yards": 10, "y_rec_tds": 0, "y_carries": 0,
            "y_rush_yards": 0, "y_rush_tds": 0, "y_pass_attempts": 0,
            "y_pass_yards": 0, "y_pass_tds": 0, "y_interceptions": 0,
        },
        {
            "position": "QB", "y_targets": 0, "y_receptions": 0,
            "y_rec_yards": 0, "y_rec_tds": 0, "y_carries": 2,
            "y_rush_yards": 8, "y_rush_tds": 0, "y_pass_attempts": 4,
            "y_pass_yards": 28, "y_pass_tds": 1, "y_interceptions": 0,
        },
    ])
    predicted = pd.DataFrame({
        name: np.zeros(len(rows)) for name in diagnostic.components.COMPONENT_NAMES
    })
    predicted["catch_rate"] = [0.5, 0.0]
    predicted["ypr"] = [10.0, 0.0]
    predicted["ypc"] = [0.0, 4.0]
    predicted["ypa"] = [0.0, 7.0]
    report = diagnostic.component_metrics(rows, predicted)
    assert report["catch_rate"] == {"rows": 1, "mae": 0.0}
    assert report["ypa"] == {"rows": 1, "mae": 0.0}
    assert report["pass_attempts"]["rows"] == 1


def test_route_component_environment_rejects_other_feature_arm(monkeypatch):
    monkeypatch.setenv("EXTRA_FEATURES", "target_share_last")
    with pytest.raises(ValueError, match="blank EXTRA_FEATURES"):
        diagnostic._validate_environment()


def test_component_evaluation_keeps_common_rows_and_applies_gate(monkeypatch):
    panel_rows = []
    accepted_rows = []
    for season in diagnostic.HELD_OUT_SEASONS:
        for position, player in (("QB", "qb"), ("WR", "wr")):
            actual = 25.0 if position == "QB" else 35.0
            panel_rows.append({
                "season": season,
                "week": 5,
                "gsis_id": f"{player}-{season}",
                "position": position,
                "was_active": True,
                "y_dk_points": actual,
                "y_targets": 2 if position == "WR" else 0,
                "y_receptions": 1 if position == "WR" else 0,
                "y_rec_yards": 10 if position == "WR" else 0,
                "y_rec_tds": 0,
                "y_carries": 1,
                "y_rush_yards": 4,
                "y_rush_tds": 0,
                "y_pass_attempts": 4 if position == "QB" else 0,
                "y_pass_yards": 28 if position == "QB" else 0,
                "y_pass_tds": 1 if position == "QB" else 0,
                "y_interceptions": 0,
                "fp_route_share_last": 0.75 if position == "WR" else np.nan,
            })
            accepted_rows.append({
                "season": season,
                "week": 5,
                "gsis_id": f"{player}-{season}",
                "pos": position,
                "actual": actual,
            })

    def fake_components(panel, evaluation, held_out, treatment):
        value = 1.0 if treatment else 0.0
        return pd.DataFrame({
            name: np.full(len(evaluation), value)
            for name in diagnostic.components.COMPONENT_NAMES
        })

    def fake_scores(rows, predicted, seed):
        row = rows[rows.position.eq("WR")].iloc[0]
        treatment = float(predicted.targets.iloc[0]) == 1.0
        return pd.DataFrame([{
            "season": row.season,
            "week": row.week,
            "gsis_id": row.gsis_id,
            "position": row.position,
            "actual": row.y_dk_points,
            "point": 34.0 if treatment else 32.0,
            "crps": 1.0 if treatment else 2.0,
            "p_20": 0.9,
            "p_30": 0.8 if treatment else 0.4,
            "q90": 30.0,
            "exceeds_q90": True,
            "q95": 32.0,
            "exceeds_q95": True,
            "q99": 40.0,
            "exceeds_q99": False,
        }])

    monkeypatch.setattr(diagnostic, "_fit_predict_components", fake_components)
    monkeypatch.setattr(diagnostic, "_score_composed", fake_scores)
    report = diagnostic.evaluate_component_models(
        pd.DataFrame(panel_rows), pd.DataFrame(accepted_rows))
    assert report["gate"]["passes"]
    assert report["aggregate"]["rows"] == 3
    assert report["coverage"] == {"2023": 1.0, "2024": 1.0, "2025": 1.0}
