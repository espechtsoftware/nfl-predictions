import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models.validation import calibration_table, evaluate, walk_forward_folds
from nfl_dfs.models.weights import sample_weights


def test_walk_forward_folds_never_leak_future():
    folds, test = walk_forward_folds(list(range(2015, 2026)), min_train_seasons=6)
    assert test == 2025
    for train_seasons, val in folds:
        assert max(train_seasons) < val
        assert test not in train_seasons and val != test


def test_walk_forward_requires_enough_seasons():
    with pytest.raises(ValueError):
        walk_forward_folds([2023, 2024], min_train_seasons=6)


def test_evaluate_market_comparison():
    rng = np.random.default_rng(0)
    y = pd.Series(rng.uniform(0, 30, 500))
    good = y.to_numpy() + rng.normal(0, 1, 500)
    bad_market = pd.Series(y.to_numpy() + rng.normal(0, 5, 500))
    rep = evaluate(y, good, market=bad_market)
    assert rep.beats_market
    rep2 = evaluate(y, y.to_numpy() + rng.normal(0, 9, 500), market=bad_market)
    assert not rep2.beats_market


def test_evaluate_coverage():
    rng = np.random.default_rng(1)
    y = pd.Series(rng.normal(15, 5, 2000))
    p10 = np.quantile(y, 0.1) * np.ones(2000)
    p90 = np.quantile(y, 0.9) * np.ones(2000)
    rep = evaluate(y, y.to_numpy(), p10=p10, p90=p90)
    assert rep.coverage_p10 == pytest.approx(0.10, abs=0.02)
    assert rep.coverage_p90 == pytest.approx(0.90, abs=0.02)


def test_calibration_table():
    y = np.arange(100.0)
    preds = {0.5: np.full(100, 49.5)}
    tab = calibration_table(y, preds)
    assert tab.iloc[0].empirical == pytest.approx(0.5, abs=0.01)


def test_sample_weights_decay_and_guard():
    df = pd.DataFrame({"season": [2020, 2022, 2024]})
    w = sample_weights(df, target_season=2024, half_life_seasons=2.0)
    assert w[2] == 1.0
    assert w[1] == pytest.approx(0.5)
    assert w[0] == pytest.approx(0.25)
    with pytest.raises(ValueError):
        sample_weights(pd.DataFrame({"season": [2026]}), target_season=2024)
