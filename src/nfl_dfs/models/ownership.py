"""Ownership prediction model — seeded pre-season, fit on standings (issue #11).

DK contest-standings CSVs (`nfl-dfs import-ownership`) land per-player
`pct_drafted` in `nfl_raw.contest_ownership`. Once week-1+ rows exist,
`nfl-dfs train-ownership` fits a LightGBM regressor mapping
salary/projection features to logit ownership; until then everything
downstream keeps using `backtest.field.naive_ownership` (value+salary
softmax) — this module deliberately presents the same shape so the swap
is one call.

Feature philosophy (guide §8.5 / issue #13 item 3): the interesting
residual is ownership vs *salary-implied* popularity. The pricing-lag
residual (models/pricing_lag.py) is the natural extra feature once its
weekly table accumulates alongside real ownership; start with the
features that exist for every player-week today.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

FEATURES = [
    "salary",
    "proj_points",
    "value",            # proj / (salary/1000)
    "salary_rank_pos",  # 1 = most expensive at position that week
    "value_rank_pos",
    "is_min_price",     # sub-$4k punt territory (Addendum 24 archetypes)
]
TARGET = "pct_drafted"
_EPS = 1e-3


def build_features(pool: pd.DataFrame) -> pd.DataFrame:
    """Feature frame from a pool with salary/proj_points/position columns.
    Works on live pools (prediction) and joined history (training)."""
    df = pool.copy()
    df["value"] = df.proj_points / (df.salary / 1000.0).clip(lower=0.1)
    df["salary_rank_pos"] = df.groupby(["season", "week", "position"])["salary"] \
        .rank(ascending=False, method="min")
    df["value_rank_pos"] = df.groupby(["season", "week", "position"])["value"] \
        .rank(ascending=False, method="min")
    df["is_min_price"] = (df.salary <= 4000).astype(float)
    return df


def training_frame() -> pd.DataFrame:
    """Join contest ownership to salaries and projections by normalized
    display name within (season, week). Raises with a friendly message
    until standings CSVs have been imported (in-season task)."""
    from ..bq import query_df
    from ..config import settings

    df = query_df(f"""
        WITH own AS (
          SELECT season, week, UPPER(display_name) AS uname,
                 AVG(pct_drafted) AS pct_drafted
          FROM `{settings.raw}.contest_ownership`
          GROUP BY season, week, uname
        ),
        sal AS (
          SELECT DISTINCT draft_group_id, season, week,
                 UPPER(display_name) AS uname, position, salary
          FROM `{settings.raw}.dk_salaries`
          WHERE slate_type = 'classic'
        ),
        proj AS (
          SELECT season, week, UPPER(display_name) AS uname,
                 AVG(proj_points) AS proj_points
          FROM `{settings.predictions}.player_projections`
          GROUP BY season, week, uname
        )
        SELECT own.season, own.week, own.uname AS display_name,
               sal.position, sal.salary, proj.proj_points, own.pct_drafted
        FROM own
        JOIN sal USING (season, week, uname)
        JOIN proj USING (season, week, uname)
    """)
    if df.empty:
        raise RuntimeError(
            "contest_ownership has no joinable rows yet -- import weekly "
            "standings CSVs in-season (nfl-dfs import-ownership), then rerun."
        )
    return build_features(df)


def train(frame: pd.DataFrame, num_boost_round: int = 300):
    """LightGBM on logit(pct_drafted). Returns the booster."""
    import lightgbm as lgb

    y = frame[TARGET].clip(_EPS, 100 - _EPS) / 100.0
    y = np.log(y / (1 - y))
    ds = lgb.Dataset(frame[FEATURES], label=y)
    params = {"objective": "regression", "metric": "l2", "verbosity": -1,
              "learning_rate": 0.05, "num_leaves": 15}
    booster = lgb.train(params, ds, num_boost_round=num_boost_round)
    log.info("ownership model trained on %d rows", len(frame))
    return booster


def predict_ownership(booster, pool: pd.DataFrame) -> np.ndarray:
    """Predicted pct_drafted (0-100) for a live pool frame."""
    feats = build_features(pool)
    logit = booster.predict(feats[FEATURES])
    return 100.0 / (1.0 + np.exp(-logit))


def run_training() -> None:
    """CLI entry: fit on all imported standings and report in-sample fit
    vs the naive value/salary proxy so week-over-week improvement is
    visible from week 1."""
    frame = training_frame()
    booster = train(frame)
    pred = predict_ownership(booster, frame)
    corr = np.corrcoef(pred, frame[TARGET])[0, 1]
    print(f"trained on {len(frame)} player-weeks; in-sample corr {corr:.3f}")
    out = "models/ownership.txt"
    booster.save_model(out)
    print(f"saved {out} -- wire into run_projections/field sim once "
          f"out-of-sample beats the naive proxy")
