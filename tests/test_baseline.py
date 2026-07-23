import numpy as np

from nfl_dfs.models import baseline


def test_walk_forward_learns_signal(small_panel):
    result = baseline.walk_forward(small_panel, min_train_seasons=2, num_boost_round=120)
    assert result.fold_reports
    for season, rep in result.fold_reports.items():
        # Synthetic noise sigma is 6; a model that learned usage/vegas signal
        # must land well under the ~8.5 MAE of predicting the global mean.
        assert rep.mae < 7.5, f"{season}: MAE {rep.mae}"
        # Rank correlation within position should be clearly positive
        assert all(r > 0.2 for r in rep.rank_corr_by_position.values())


def test_quantiles_are_monotone(small_panel):
    model = baseline.train(small_panel, target_season=2022, num_boost_round=80)
    preds = model.predict(small_panel[small_panel.season == 2022])
    assert (preds.proj_p10 <= preds.proj_p50 + 1e-9).all()
    assert (preds.proj_p50 <= preds.proj_p90 + 1e-9).all()
    assert (preds.proj_std >= 0).all()


def test_coverage_roughly_calibrated(small_panel):
    model = baseline.train(small_panel, target_season=2022, num_boost_round=200)
    va = small_panel[small_panel.season == 2022]
    preds = model.predict(va)
    below_p10 = np.mean(va.y_dk_points.to_numpy() < preds.proj_p10.to_numpy())
    below_p90 = np.mean(va.y_dk_points.to_numpy() < preds.proj_p90.to_numpy())
    assert 0.03 < below_p10 < 0.22
    assert 0.78 < below_p90 < 0.97
