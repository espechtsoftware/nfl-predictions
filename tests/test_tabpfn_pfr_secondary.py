import numpy as np
import pandas as pd

from nfl_dfs.analysis import tabpfn_pfr_secondary_final_served as final_served
from nfl_dfs.backtest import replay


def test_pfr_secondary_arm_environment_coordinates_drop_and_cache(monkeypatch):
    monkeypatch.setenv("TABPFN_MARGINAL_TABLE", "prior")
    monkeypatch.setenv("DROP_FEATURES", "prior_drop")
    for arm in final_served.ARMS:
        with final_served._arm_environment(arm):
            assert replay._tabpfn_marginal_table() == final_served.TABLES[arm]
            expected = ",".join(final_served.ARM_DROPS[arm])
            assert __import__("os").environ.get("DROP_FEATURES", "") == expected
    assert __import__("os").environ["TABPFN_MARGINAL_TABLE"] == "prior"
    assert __import__("os").environ["DROP_FEATURES"] == "prior_drop"


def test_pfr_secondary_branch_choice_uses_brier_then_fixed_tie_order(monkeypatch):
    seasons = (2022, 2023, 2024, 2025)
    folds = {}
    for arm in final_served.ARMS:
        folds[arm] = {}
        for season in seasons:
            frame = pd.DataFrame({
                "season": [season], "week": [1], "gsis_id": ["p"],
                "position": ["WR"], "actual": [31.0],
                "market_covered": [True], "tabpfn_covered": [True],
            })
            folds[arm][season] = (frame, np.zeros((1, 2)))

    monkeypatch.setattr(
        final_served.calibration, "fit_walk_forward_schedule",
        lambda _folds: {2023: {}, 2024: {}, 2025: {}},
    )
    values = {
        "control": 0.20, "drop_rates": 0.18,
        "drop_top_cb": 0.18, "drop_all": 0.19,
    }
    ordered = iter(final_served.ARMS)

    def fake_score(_folds, _schedule):
        arm = next(ordered)
        rows = []
        for season in (2023, 2024, 2025):
            rows.append(pd.DataFrame({
                "season": [season], "week": [1], "gsis_id": ["p"],
                "position": ["WR"], "actual": [31.0],
                "market_covered": [True], "tabpfn_covered": [True],
                "point_abs_error": [1.0], "crps": [1.0],
                "event_20": [True], "event_30": [True],
                "brier_20": [0.1], "brier_30": [values[arm]],
                "exceeds_q90": [False], "pinball_q90": [1.0],
                "exceeds_q95": [False], "pinball_q95": [1.0],
                "exceeds_q99": [False], "pinball_q99": [1.0],
            }))
        return pd.concat(rows, ignore_index=True), 0.0

    monkeypatch.setattr(final_served.calibration, "score_walk_forward", fake_score)
    monkeypatch.setattr(final_served, "_summaries", lambda scores: {
        "folds": [], "aggregate": {"brier_30": float(scores.brier_30.mean())}
    })
    monkeypatch.setattr(
        final_served.uncertainty, "_paired_loss_uncertainty",
        lambda _left, _right: {},
    )
    result = final_served._evaluate_arms(folds)
    assert result["gate"]["eligible_arms"] == [
        "drop_rates", "drop_top_cb", "drop_all"]
    assert result["gate"]["selected_arm"] == "drop_rates"
