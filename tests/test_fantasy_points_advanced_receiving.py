import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import fantasy_points_advanced_receiving as diagnostic
from nfl_dfs.ingest import fantasy_points_advanced_receiving_support as support


def _window(window_type="cumulative", **overrides):
    row = {
        "season": 2025,
        "target_week": 9,
        "window_type": window_type,
        "source_week_start": 1 if window_type == "cumulative" else 5,
        "source_week_end": 8,
        "gsis_id": "wr-1",
        "resolution_status": "resolved",
        "pos": "WR",
        "routes": 40.0,
        "source_run_id": diagnostic.SOURCE_RUN_ID,
        **{metric: 0.2 for metric in support.METRICS},
    }
    row.update(overrides)
    return row


def test_blended_features_use_fixed_route_weight_and_three_fields():
    cumulative = _window(
        fp_adv_rec_tprr=0.2,
        fp_adv_rec_yprr=1.0,
        fp_adv_rec_xfp_per_route=0.4,
    )
    last_four = _window(
        "last_four",
        fp_adv_rec_tprr=0.4,
        fp_adv_rec_yprr=2.0,
        fp_adv_rec_xfp_per_route=0.8,
    )
    row = diagnostic.build_blended_features(
        pd.DataFrame([cumulative, last_four])).iloc[0]
    assert row.fp_adv_rec_supported
    assert row.fp_adv_rec_recency_weight == pytest.approx(0.5)
    assert row.fp_adv_rec_blend_tprr == pytest.approx(0.3)
    assert row.fp_adv_rec_blend_yprr == pytest.approx(1.5)
    assert row.fp_adv_rec_blend_xfp_per_route == pytest.approx(0.6)
    assert not any("adot" in name for name in diagnostic.TREATMENT_FEATURES)
    assert not any("first_read" in name for name in diagnostic.TREATMENT_FEATURES)


def test_blended_features_floor_and_pit_fail_closed():
    row = diagnostic.build_blended_features(pd.DataFrame([
        _window(routes=19.0),
    ])).iloc[0]
    assert not row.fp_adv_rec_supported
    assert row[list(diagnostic.TREATMENT_FEATURES)].isna().all()

    with pytest.raises(ValueError, match="target W-1"):
        diagnostic.build_blended_features(pd.DataFrame([
            _window(source_week_end=9),
        ]))


def test_attach_blended_features_leaves_unmatched_target_as_fallback():
    targets = pd.DataFrame([
        {"season": 2025, "week": 9, "gsis_id": "wr-1", "pos": "WR"},
        {"season": 2025, "week": 9, "gsis_id": "wr-2", "pos": "WR"},
    ])
    attached = diagnostic.attach_blended_features(
        targets, pd.DataFrame([_window()]))
    assert attached.set_index("gsis_id").loc["wr-1", "fp_adv_rec_supported"]
    assert not attached.set_index("gsis_id").loc[
        "wr-2", "fp_adv_rec_supported"]


def test_empirical_residual_arm_is_deterministic_and_finite():
    rows = []
    for index in range(80):
        rows.append({
            "pos": "WR" if index % 2 else "TE",
            "actual": float((index * 7) % 36),
            "mean_projection": 8.0 + (index % 9),
            **{
                column: float((index + offset) % 11)
                for offset, column in enumerate(diagnostic.CONTROL_NUMERIC)
                if column != "mean_projection"
            },
        })
    frame = pd.DataFrame(rows)
    first = diagnostic._fit_arm(
        frame.iloc[:60], frame.iloc[60:], diagnostic.CONTROL_NUMERIC)
    second = diagnostic._fit_arm(
        frame.iloc[:60], frame.iloc[60:], diagnostic.CONTROL_NUMERIC)
    assert first[1].shape == (20, diagnostic.ENSEMBLE_MEMBERS)
    for left, right in zip(first, second):
        assert np.isfinite(left).all()
        assert np.array_equal(left, right)


def test_advanced_receiving_gate_requires_all_frozen_checks():
    aggregate = {
        "events_30": 120,
        "control_crps": 2.0,
        "treatment_crps": 1.98,
        "control_calibration_abs95": 0.02,
        "treatment_calibration_abs95": 0.02,
        "control_calibration_abs99": 0.01,
        "treatment_calibration_abs99": 0.01,
        "control_brier30": 0.02,
        "treatment_brier30": 0.02,
        "control_mae": 3.0,
        "treatment_mae": 2.9,
    }
    report = {
        "aggregate": aggregate,
        "folds": [
            {"control_brier30": 0.02, "treatment_brier30": 0.02}
            for _ in diagnostic.HELD_OUT_SEASONS
        ],
        "supported_rows_by_fold": {"2023": 2000, "2024": 2000, "2025": 2000},
        "equal_fold_upper_pinball_ratio": 0.99,
    }
    assert diagnostic.diagnostic_gate(report)["passes"]
    report["equal_fold_upper_pinball_ratio"] = 1.0
    assert not diagnostic.diagnostic_gate(report)["passes"]
