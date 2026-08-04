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
            # Slice to the booster's own training columns: a registry model
            # trained before a featureset addition must keep predicting until
            # the next weekly retrain picks the new columns up.
            out[name] = self.models[name].predict(X[self.models[name].feature_name()])

        for name, (lo, hi) in RATE_CLIPS.items():
            out[name] = out[name].clip(lo, hi)
        for name in ("targets", "rec_tds", "carries", "rush_tds",
                     "pass_attempts", "pass_tds", "interceptions"):
            out[name] = out[name].clip(lower=0.0)

        is_qb = (df.position == "QB").to_numpy()
        out.loc[is_qb, ["targets", "rec_tds"]] = 0.0
        out.loc[~is_qb, ["pass_attempts", "pass_tds", "interceptions"]] = 0.0
        return out


class _EnsembleBooster:
    """Booster-compatible average of K members trained on shuffled
    column orders (MODEL_ENSEMBLE lever). Implements the two methods the
    predict path uses: predict() and feature_name()."""

    def __init__(self, members):
        self.members = members

    def feature_name(self):
        return self.members[0].feature_name()

    def predict(self, X):
        preds = [m.predict(X[m.feature_name()]) for m in self.members]
        return np.mean(preds, axis=0)


def _fit(
    tr: pd.DataFrame,
    label: pd.Series,
    target_season: int,
    params: dict,
    num_boost_round: int,
    denom: pd.Series | None = None,
) -> lgb.Booster:
    w = sample_weights(tr, target_season)
    # A/B lever (env RATE_DENOM_WEIGHTS, off by default; data audit
    # 2026-08-03 finding 7): rate components (catch_rate, ypr, ypc, ypa)
    # weigh a 1-target rate the same as a 12-target rate, inflating rate
    # noise. With the lever on, rate rows are weighted by recency x
    # denominator so high-volume observations dominate the rate fit.
    import os as _os

    if denom is not None and _os.environ.get("RATE_DENOM_WEIGHTS"):
        w = w * denom.to_numpy(dtype=float)
    X = build_X(tr)
    # A/B lever (env MODEL_ENSEMBLE=K, off by default = 1; 2026-08-04,
    # the order-luck treatment): train K members with per-member seeds
    # AND per-member COLUMN ORDER, average predictions. Column order is
    # the measured tie-break dimension (Addendum 34: ±5 tail weeks of
    # "order luck" per rebuild); averaging over shuffled orders directly
    # attenuates the band every rebuild draws from. K=1 is byte-identical
    # to the pre-lever behavior.
    import os as _os2

    K = int(_os2.environ.get("MODEL_ENSEMBLE", "1") or 1)
    if K <= 1:
        dset = lgb.Dataset(X, label, weight=w,
                           categorical_feature=["position"])
        return lgb.train(params, dset, num_boost_round=num_boost_round)
    members = []
    for k in range(K):
        rng = np.random.default_rng(9000 + k)
        cols = list(X.columns)
        rng.shuffle(cols)
        pk = {**params, "seed": 9000 + k,
              "feature_fraction_seed": 9100 + k,
              "bagging_seed": 9200 + k, "data_random_seed": 9300 + k}
        dset = lgb.Dataset(X[cols], label, weight=w,
                           categorical_feature=["position"])
        members.append(lgb.train(pk, dset, num_boost_round=num_boost_round))
    return _EnsembleBooster(members)


def train(
    panel: pd.DataFrame, target_season: int, num_boost_round: int = 400
) -> ComponentModels:
    """Train every component on seasons before `target_season`."""
    tr = panel[panel.season < target_season]
    # A/B lever (env TRAIN_MAX_WEEK, off by default): drop late-season
    # training rows. Rest-week dynamics (playoff-locked starters on a
    # half, surprise backups) generate labels unrepresentative of the
    # weeks the user actually plays; fully-rested stars vanish entirely
    # (no stats row), so the residue is systematically weird. 16 keeps
    # ~88% of rows and excludes the modern weeks 17-18.
    import os as _os

    max_wk = int(_os.environ.get("TRAIN_MAX_WEEK", "0"))
    if max_wk:
        tr = tr[tr.week <= max_wk]
    if tr.empty:
        raise ValueError(f"no training rows before season {target_season}")

    recv = tr[_RECEIVING(tr)]
    qb = tr[_PASSING(tr)]
    caught = recv[recv.y_targets > 0]
    with_rec = recv[recv.y_receptions > 0]
    rushed = tr[tr.y_carries > 0]
    attempted = qb[qb.y_pass_attempts > 0]

    specs: dict = {
        "targets": (recv, recv.y_targets, COUNT_PARAMS, None),
        "catch_rate": (caught, caught.y_receptions / caught.y_targets,
                       RATE_PARAMS, caught.y_targets),
        "ypr": (with_rec, with_rec.y_rec_yards / with_rec.y_receptions,
                RATE_PARAMS, with_rec.y_receptions),
        "rec_tds": (recv, recv.y_rec_tds, COUNT_PARAMS, None),
        "carries": (tr[_ALL(tr)], tr.y_carries, COUNT_PARAMS, None),
        "ypc": (rushed, rushed.y_rush_yards / rushed.y_carries,
                RATE_PARAMS, rushed.y_carries),
        "rush_tds": (tr[_ALL(tr)], tr.y_rush_tds, COUNT_PARAMS, None),
        "pass_attempts": (qb, qb.y_pass_attempts, COUNT_PARAMS, None),
        "ypa": (attempted, attempted.y_pass_yards / attempted.y_pass_attempts,
                RATE_PARAMS, attempted.y_pass_attempts),
        "pass_tds": (qb, qb.y_pass_tds, COUNT_PARAMS, None),
        "interceptions": (qb, qb.y_interceptions, COUNT_PARAMS, None),
    }

    models = {
        name: _fit(rows, label, target_season, params, num_boost_round,
                   denom=denom)
        for name, (rows, label, params, denom) in specs.items()
    }
    return ComponentModels(models=models)
