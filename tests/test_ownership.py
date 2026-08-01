"""Offline coverage for the ownership-model seed (issue #11)."""

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models import ownership


def _pool(n=60, seed=3):
    rng = np.random.default_rng(seed)
    pos = rng.choice(["QB", "RB", "WR", "TE", "DST"], n)
    salary = rng.integers(3000, 9500, n)
    proj = salary / 500 + rng.normal(0, 3, n)
    return pd.DataFrame({
        "season": 2026, "week": rng.integers(1, 4, n),
        "position": pos, "salary": salary,
        "proj_points": np.clip(proj, 1, None),
    })


def test_build_features_shapes_and_ranks():
    f = ownership.build_features(_pool())
    for c in ownership.FEATURES:
        assert c in f.columns
    assert (f.salary_rank_pos >= 1).all()
    assert f.is_min_price.isin([0.0, 1.0]).all()


def test_train_predict_roundtrip_bounded():
    frame = ownership.build_features(_pool())
    # synthetic truth: chalk follows value with noise
    v = frame.value
    frame["pct_drafted"] = np.clip(3 + 4 * (v - v.mean()) / v.std()
                                   + np.random.default_rng(0).normal(0, 1, len(v)),
                                   0.1, 60)
    booster = ownership.train(frame, num_boost_round=60)
    pred = ownership.predict_ownership(booster, frame)
    assert pred.shape == (len(frame),)
    assert (pred >= 0).all() and (pred <= 100).all()
    corr = np.corrcoef(pred, frame.pct_drafted)[0, 1]
    assert corr > 0.5  # learns the value-chalk relationship


def test_training_frame_raises_helpfully_when_empty(monkeypatch):
    import nfl_dfs.models.ownership as own
    monkeypatch.setattr("nfl_dfs.bq.query_df", lambda sql: pd.DataFrame())
    with pytest.raises(RuntimeError, match="import-ownership"):
        own.training_frame()
