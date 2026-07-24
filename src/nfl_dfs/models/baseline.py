"""Baseline model (guide §7.3): LightGBM on DK points directly, plus three
quantile regressors for a usable distribution. Deliberately crude — this is
the floor every later model must beat, and the honest MAE number comes from
walk-forward validation against the market, never a random split.
"""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from . import validation
from .featureset import FEATURES, build_X
from .weights import sample_weights

LABEL = "y_dk_points"
QUANTILES = (0.10, 0.50, 0.90)
# (p90 - p10) spans 2.5631 standard deviations for a normal.
_P10_P90_TO_STD = 2.5631

MEAN_PARAMS = dict(
    objective="regression",
    metric="mae",
    learning_rate=0.06,
    num_leaves=31,
    min_data_in_leaf=40,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=1,
    lambda_l2=5.0,
    verbosity=-1,
)


@dataclass
class BaselineModel:
    mean_model: lgb.Booster
    quantile_models: dict[float, lgb.Booster]
    target_season: int

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        X = build_X(df)
        q = np.column_stack(
            [self.quantile_models[a].predict(X) for a in QUANTILES]
        )
        # Quantile regressors can cross; sort per row to restore monotonicity.
        q.sort(axis=1)
        out = pd.DataFrame(
            {
                "proj_points": self.mean_model.predict(X),
                "proj_p10": q[:, 0],
                "proj_p50": q[:, 1],
                "proj_p90": q[:, 2],
            },
            index=df.index,
        )
        out["proj_std"] = np.maximum((out.proj_p90 - out.proj_p10) / _P10_P90_TO_STD, 0.0)
        return out


@dataclass
class WalkForwardResult:
    fold_reports: dict[int, validation.EvalReport]
    test_season: int


def train(
    panel: pd.DataFrame, target_season: int, num_boost_round: int = 400
) -> BaselineModel:
    """Train on every season before `target_season`, recency-weighted."""
    tr = panel[panel.season < target_season]
    if tr.empty:
        raise ValueError(f"no training rows before season {target_season}")
    X = build_X(tr)
    w = sample_weights(tr, target_season)
    dset = lgb.Dataset(X, tr[LABEL], weight=w, categorical_feature=["position"])

    mean_model = lgb.train(MEAN_PARAMS, dset, num_boost_round=num_boost_round)
    quantile_models = {}
    for alpha in QUANTILES:
        params = {**MEAN_PARAMS, "objective": "quantile", "alpha": alpha, "metric": "quantile"}
        quantile_models[alpha] = lgb.train(params, dset, num_boost_round=num_boost_round)
    return BaselineModel(mean_model, quantile_models, target_season)


def walk_forward(
    panel: pd.DataFrame,
    min_train_seasons: int = 4,
    num_boost_round: int = 400,
) -> WalkForwardResult:
    """Expanding-window validation; the market comparison uses DK's own
    points-per-game figure (`dk_ppg`) when present."""
    folds, test = validation.walk_forward_folds(
        sorted(panel.season.unique()), min_train_seasons=min_train_seasons
    )
    reports: dict[int, validation.EvalReport] = {}
    for _train_seasons, val_season in folds:
        model = train(panel, target_season=val_season, num_boost_round=num_boost_round)
        va = panel[panel.season == val_season]
        preds = model.predict(va)
        reports[val_season] = validation.evaluate(
            va[LABEL],
            preds.proj_points.to_numpy(),
            market=va.dk_ppg if "dk_ppg" in va.columns else None,
            p10=preds.proj_p10.to_numpy(),
            p90=preds.proj_p90.to_numpy(),
            positions=va.position,
        )
    return WalkForwardResult(fold_reports=reports, test_season=test)


FEATURE_LIST = FEATURES  # re-exported for registry metadata
