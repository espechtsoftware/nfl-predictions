"""Component models (guide §6.2): predict opportunity and efficiency
separately, then let the simulator compose them. Losses match the label's
distribution (§7.2) — counts get Poisson, rates get plain regression on the
observed ratio with the denominator as support.

Position masks are applied at prediction time: a QB gets zero expected
targets and a WR gets zero pass attempts, no matter what the trees say.
"""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from .featureset import LGB_THREADS, build_X
from .weights import sample_weights

COUNT_PARAMS = dict(
    num_threads=LGB_THREADS,
    objective="poisson",
    metric="poisson",
    learning_rate=0.06,
    num_leaves=31,
    min_data_in_leaf=40,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=1,
    lambda_l2=5.0,
    verbosity=-1,
)
RATE_PARAMS = {**COUNT_PARAMS, "objective": "regression", "metric": "mae"}

# name -> (label expression, row filter, params). Rates are trained only on
# rows where the denominator exists; counts on every row of the position
# group so the zeros are learned, not imputed.
_RECEIVING = lambda df: df.position != "QB"  # noqa: E731
_PASSING = lambda df: df.position == "QB"  # noqa: E731
_ALL = lambda df: pd.Series(True, index=df.index)  # noqa: E731

# Clips keep composed distributions sane even when a model extrapolates.
RATE_CLIPS = {
    "catch_rate": (0.2, 0.95),
    "ypr": (2.0, 25.0),
    "ypc": (1.5, 9.0),
    "ypa": (4.0, 12.0),
}

COMPONENT_NAMES = [
    "targets",
    "catch_rate",
    "ypr",
    "rec_tds",
    "carries",
    "ypc",
    "rush_tds",
    "pass_attempts",
    "ypa",
    "pass_tds",
    "interceptions",
]


@dataclass
class ComponentModels:
    models: dict[str, lgb.Booster]

    def predict_components(self, df: pd.DataFrame) -> pd.DataFrame:
        X = build_X(df)
        out = pd.DataFrame(index=df.index)
        for name in COMPONENT_NAMES:
            out[name] = self.models[name].predict(X)

        for name, (lo, hi) in RATE_CLIPS.items():
            out[name] = out[name].clip(lo, hi)
        for name in ("targets", "rec_tds", "carries", "rush_tds",
                     "pass_attempts", "pass_tds", "interceptions"):
            out[name] = out[name].clip(lower=0.0)

        is_qb = (df.position == "QB").to_numpy()
        out.loc[is_qb, ["targets", "rec_tds"]] = 0.0
        out.loc[~is_qb, ["pass_attempts", "pass_tds", "interceptions"]] = 0.0
        return out


def _fit(
    tr: pd.DataFrame,
    label: pd.Series,
    target_season: int,
    params: dict,
    num_boost_round: int,
) -> lgb.Booster:
    dset = lgb.Dataset(
        build_X(tr),
        label,
        weight=sample_weights(tr, target_season),
        categorical_feature=["position"],
    )
    return lgb.train(params, dset, num_boost_round=num_boost_round)


def train(
    panel: pd.DataFrame, target_season: int, num_boost_round: int = 400
) -> ComponentModels:
    """Train every component on seasons before `target_season`."""
    tr = panel[panel.season < target_season]
    if tr.empty:
        raise ValueError(f"no training rows before season {target_season}")

    recv = tr[_RECEIVING(tr)]
    qb = tr[_PASSING(tr)]
    caught = recv[recv.y_targets > 0]
    with_rec = recv[recv.y_receptions > 0]
    rushed = tr[tr.y_carries > 0]
    attempted = qb[qb.y_pass_attempts > 0]

    specs: dict[str, tuple[pd.DataFrame, pd.Series, dict]] = {
        "targets": (recv, recv.y_targets, COUNT_PARAMS),
        "catch_rate": (caught, caught.y_receptions / caught.y_targets, RATE_PARAMS),
        "ypr": (with_rec, with_rec.y_rec_yards / with_rec.y_receptions, RATE_PARAMS),
        "rec_tds": (recv, recv.y_rec_tds, COUNT_PARAMS),
        "carries": (tr[_ALL(tr)], tr.y_carries, COUNT_PARAMS),
        "ypc": (rushed, rushed.y_rush_yards / rushed.y_carries, RATE_PARAMS),
        "rush_tds": (tr[_ALL(tr)], tr.y_rush_tds, COUNT_PARAMS),
        "pass_attempts": (qb, qb.y_pass_attempts, COUNT_PARAMS),
        "ypa": (attempted, attempted.y_pass_yards / attempted.y_pass_attempts, RATE_PARAMS),
        "pass_tds": (qb, qb.y_pass_tds, COUNT_PARAMS),
        "interceptions": (qb, qb.y_interceptions, COUNT_PARAMS),
    }

    models = {
        name: _fit(rows, label, target_season, params, num_boost_round)
        for name, (rows, label, params) in specs.items()
    }
    return ComponentModels(models=models)
