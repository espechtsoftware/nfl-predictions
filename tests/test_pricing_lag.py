"""Offline tests for the DK pricing-lag model (issue #13 item 3): salary
regressed on trailing production, residual = structural mispricing.
Covers correctness of the point-in-time filter (never fit on the season
being scored) and that the residual actually separates an underpriced
player from a fairly-priced one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from nfl_dfs.models import pricing_lag


def test_train_never_uses_target_season_rows(panel):
    """Corrupting the target season's salaries must not change the fitted
    model -- train() filters those rows out before fitting."""
    target_season = sorted(panel.season.unique())[-1]
    clean_models = pricing_lag.train(panel, target_season)

    corrupted = panel.copy()
    mask = corrupted.season == target_season
    corrupted.loc[mask, "salary"] = 999_999
    corrupted_models = pricing_lag.train(corrupted, target_season)

    assert clean_models.keys() == corrupted_models.keys()
    for pos in clean_models:
        np.testing.assert_allclose(
            clean_models[pos].ridge.coef_, corrupted_models[pos].ridge.coef_
        )
        assert clean_models[pos].ridge.intercept_ == corrupted_models[pos].ridge.intercept_


def test_train_requires_earlier_seasons(panel):
    first_season = sorted(panel.season.unique())[0]
    models = pricing_lag.train(panel, first_season)
    assert models == {}


def test_fitted_model_beats_naive_mean_baseline(panel):
    """Sanity check: the synthetic panel's salary is a function of
    production plus noise, so a trailing-production regression should fit
    meaningfully better than predicting the position mean."""
    target_season = sorted(panel.season.unique())[-1]
    models = pricing_lag.train(panel, target_season)
    va = panel[panel.season == target_season]
    out = pricing_lag.residuals(va, models)

    assert set(out.columns) == set(pricing_lag.RESIDUAL_COLUMNS)
    assert not out.empty

    mae_model = out.salary_residual.abs().mean()
    naive_pred = va.groupby("position").salary.transform("mean")
    mae_naive = (va.salary.to_numpy() - naive_pred.to_numpy())
    mae_naive = np.abs(mae_naive).mean()
    assert mae_model < mae_naive


def test_residual_flags_underpriced_player():
    """Two players with identical trailing production but very different
    salaries: the cheap one should get a strongly negative residual/z and
    the fair one should sit close to zero."""
    rng = np.random.default_rng(0)
    rows = []
    for season in range(2018, 2024):
        for week in range(1, 18):
            usage = 0.25 + rng.normal(0, 0.01)
            rows.append({
                "gsis_id": "00-A", "season": season, "week": week,
                "position": "WR",
                "target_share_l4": usage, "carry_share_l4": 0.0,
                "wopr_l4": 1.5 * usage, "rz20_targets_smoothed": usage * 4,
                "ez_targets_l4": usage * 1.5, "deep_targets_l4": usage * 2.0,
                "gl3_carries_smoothed": 0.0, "snap_share_l4": 0.8,
                "dk_points_l4": 14 + rng.normal(0, 0.5),
                "dk_points_std": 14, "games_played_prior": 50,
                "salary": 7000 + rng.normal(0, 50),
            })
            rows.append({
                "gsis_id": "00-B", "season": season, "week": week,
                "position": "WR",
                "target_share_l4": usage, "carry_share_l4": 0.0,
                "wopr_l4": 1.5 * usage, "rz20_targets_smoothed": usage * 4,
                "ez_targets_l4": usage * 1.5, "deep_targets_l4": usage * 2.0,
                "gl3_carries_smoothed": 0.0, "snap_share_l4": 0.8,
                "dk_points_l4": 14 + rng.normal(0, 0.5),
                "dk_points_std": 14, "games_played_prior": 50,
                # Same production trail, but DK hasn't caught up to it.
                "salary": 4200 + rng.normal(0, 50),
            })
    df = pd.DataFrame(rows)
    target_season = 2023
    models = pricing_lag.train(df, target_season)
    va = df[df.season == target_season]
    out = pricing_lag.residuals(va, models)

    a = out[out.gsis_id == "00-A"].salary_residual.mean()
    b = out[out.gsis_id == "00-B"].salary_residual.mean()
    az = out[out.gsis_id == "00-A"].salary_residual_z.mean()
    bz = out[out.gsis_id == "00-B"].salary_residual_z.mean()
    # Same trailing production, ~$2800 salary gap: the model splits the
    # difference, so each player's residual should recover roughly half
    # the gap in the direction DK actually priced them wrong.
    assert a > 1000  # 00-A is overpriced relative to its production trail
    assert b < -1000  # 00-B is underpriced -- the structural value signal
    assert bz < az - 1.5


def test_walk_forward_residuals_out_of_sample(panel):
    out = pricing_lag.walk_forward_residuals(panel, min_train_seasons=4)
    seasons = sorted(panel.season.unique())
    assert not out.empty
    # First eligible scored season is index `min_train_seasons` (0-based).
    assert out.season.min() == seasons[4]
    assert out.salary_residual.notna().all()
    assert out.salary_residual_z.notna().all()


def test_walk_forward_residuals_empty_when_too_few_seasons(small_panel):
    out = pricing_lag.walk_forward_residuals(small_panel, min_train_seasons=99)
    assert out.empty
    assert list(out.columns) == pricing_lag.RESIDUAL_COLUMNS


def test_sparse_position_skipped_not_crashed():
    """A position with fewer than MIN_TRAIN_ROWS rows should be silently
    excluded from the fitted models and from the resulting residuals,
    never raise."""
    rng = np.random.default_rng(1)
    rows = []
    for week in range(1, 4):  # only 3 rows -> below MIN_TRAIN_ROWS
        rows.append({
            "gsis_id": "00-X", "season": 2018, "week": week, "position": "TE",
            "target_share_l4": 0.1, "carry_share_l4": 0.0, "wopr_l4": 0.1,
            "rz20_targets_smoothed": 0.1, "ez_targets_l4": 0.1,
            "deep_targets_l4": 0.1, "gl3_carries_smoothed": 0.0,
            "snap_share_l4": 0.5, "dk_points_l4": 5.0, "dk_points_std": 5.0,
            "games_played_prior": 10, "salary": 3000 + rng.normal(0, 10),
        })
    df = pd.DataFrame(rows)
    models = pricing_lag.train(df, target_season=2019)
    assert models == {}
    out = pricing_lag.residuals(df[df.season == 2018], models)
    assert out.empty
