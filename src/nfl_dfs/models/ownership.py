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
    """Historical training data: LineStar-backfilled contest ownership
    (2022-2025, real DK GPP pct_drafted) joined to dk_salaries_historical
    by normalized name within (season, week). proj_points is the
    strictly-prior trailing-4 mean of PPR points -- deliberately the
    PUBLIC-visible expectation ("recent points"), which is what actually
    drives chalk, rather than our model's projection."""
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
          SELECT DISTINCT season, week, UPPER(display_name) AS uname,
                 position, salary
          FROM `{settings.raw}.dk_salaries_historical`
        ),
        prod AS (
          SELECT season, week, UPPER(player_display_name) AS uname,
                 AVG(fantasy_points_ppr) OVER (
                   PARTITION BY player_id ORDER BY season, week
                   ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
                 ) AS proj_points
          FROM `{settings.raw}.weekly_stats`
        )
        SELECT own.season, own.week, own.uname AS display_name,
               sal.position, sal.salary,
               COALESCE(prod.proj_points, 0) AS proj_points,
               own.pct_drafted
        FROM own
        JOIN sal USING (season, week, uname)
        LEFT JOIN (SELECT DISTINCT season, week, uname, proj_points
                   FROM prod) prod USING (season, week, uname)
    """)
    if df.empty:
        raise RuntimeError(
            "contest_ownership has no joinable rows -- run "
            "nfl_dfs.ingest.linestar_backfill (or import weekly standings "
            "CSVs in-season via nfl-dfs import-ownership), then rerun."
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


def run_training(holdout_season: int = 2025) -> None:
    """CLI entry: walk-forward evaluation -- train on seasons before
    `holdout_season`, score out-of-sample against real contest ownership,
    and compare with the naive value/salary softmax the field sim uses
    today. Then refit on everything and save."""
    frame = training_frame()
    tr = frame[frame.season < holdout_season]
    ho = frame[frame.season == holdout_season]
    print(f"train {len(tr)} rows (<{holdout_season}); holdout {len(ho)} rows")

    booster = train(tr)
    pred = predict_ownership(booster, ho)
    corr = np.corrcoef(pred, ho[TARGET])[0, 1]

    # Naive comparator: value within (week, position), same shape the
    # field simulation's naive_ownership uses.
    naive = ho.groupby(["week", "position"]).value.rank(pct=True)
    naive_corr = np.corrcoef(naive, ho[TARGET])[0, 1]
    print(f"OUT-OF-SAMPLE {holdout_season}: model corr {corr:.3f} "
          f"vs naive value-rank corr {naive_corr:.3f}")

    booster = train(frame)  # refit on all seasons for the live artifact
    import os

    os.makedirs("models", exist_ok=True)
    out = "models/ownership.txt"
    booster.save_model(out)
    print(f"saved {out} (refit on all {len(frame)} rows)")
