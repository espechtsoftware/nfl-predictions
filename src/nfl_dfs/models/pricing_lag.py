"""DK pricing-lag model (issue #13 item 3; guide §8.5 "salary lag as the
actual edge"). DK sets salary partly from trailing production, with
roughly a one-to-two-week lag before a role change gets repriced.
Regressing salary on trailing-production features isolates that lag: the
residual (actual salary minus production-implied salary) is a
*structural* value signal, distinct from the changepoint-based alert in
`trends/alerts.py` — it flags players DK has been pricing behind their
established trailing role for a while, not just this week's spike.

Ridge regression per position, walk-forward by season (never fit on the
season being scored — CLAUDE.md: walk-forward validation only, by
season). Feature set is deliberately restricted to trailing usage /
production columns: no salary itself, no game-environment or opponent
columns, since those aren't inputs to DK's own pricing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from ..bq import load_dataframe, query_df
from ..config import settings

log = logging.getLogger(__name__)

WATCHLIST_Z_THRESHOLD = -1.5  # residual_z below this = structurally underpriced

TRAILING_FEATURES = [
    "target_share_l4",
    "carry_share_l4",
    "wopr_l4",
    "rz20_targets_smoothed",
    "ez_targets_l4",
    "deep_targets_l4",
    "gl3_carries_smoothed",
    "snap_share_l4",
    "dk_points_l4",
    "dk_points_std",
    "games_played_prior",
]
TARGET = "salary"
MIN_TRAIN_ROWS = 20
RESIDUAL_COLUMNS = [
    "gsis_id", "season", "week", "position",
    "salary", "salary_predicted", "salary_residual", "salary_residual_z",
]


@dataclass
class PricingLagModel:
    position: str
    scaler: StandardScaler
    ridge: Ridge
    feature_cols: list[str]

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        X = _feature_matrix(df, self.feature_cols)
        return self.ridge.predict(self.scaler.transform(X))


def _feature_matrix(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for c in cols:
        X[c] = pd.to_numeric(df[c], errors="coerce") if c in df.columns else np.nan
    return X.fillna(X.median(numeric_only=True)).fillna(0.0)


def train(
    panel: pd.DataFrame, target_season: int, alpha: float = 5.0
) -> dict[str, PricingLagModel]:
    """One Ridge model per position, trained on seasons strictly before
    `target_season`. Rows from `target_season` (or later) are never used
    for fitting, regardless of what else is in `panel` — the caller can
    pass the full panel and rely on this filter for point-in-time safety."""
    tr = panel[panel.season < target_season]
    models: dict[str, PricingLagModel] = {}
    for pos, grp in tr.groupby("position"):
        if len(grp) < MIN_TRAIN_ROWS:
            continue
        X_raw = _feature_matrix(grp, TRAILING_FEATURES)
        scaler = StandardScaler().fit(X_raw)
        ridge = Ridge(alpha=alpha).fit(scaler.transform(X_raw), grp[TARGET].astype(float))
        models[pos] = PricingLagModel(pos, scaler, ridge, TRAILING_FEATURES)
    return models


def residuals(panel: pd.DataFrame, models: dict[str, PricingLagModel]) -> pd.DataFrame:
    """actual salary minus production-implied salary, plus a within-slice
    z-score for comparability across positions with different salary
    ranges. Negative = DK is pricing below what trailing production
    implies -- a structural value play; positive = overpriced (chalk)."""
    frames = []
    for pos, grp in panel.groupby("position"):
        model = models.get(pos)
        if model is None or grp.empty:
            continue
        pred = model.predict(grp)
        actual = grp[TARGET].to_numpy(dtype=float)
        resid = actual - pred
        sd = resid.std()
        z = resid / sd if sd > 0 else np.zeros_like(resid)
        frames.append(pd.DataFrame({
            "gsis_id": grp["gsis_id"].to_numpy(),
            "season": grp["season"].to_numpy(),
            "week": grp["week"].to_numpy(),
            "position": pos,
            "salary": actual,
            "salary_predicted": pred,
            "salary_residual": resid,
            "salary_residual_z": z,
        }))
    if not frames:
        return pd.DataFrame(columns=RESIDUAL_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def walk_forward_residuals(
    panel: pd.DataFrame, min_train_seasons: int = 4
) -> pd.DataFrame:
    """Expanding-window: each season's residuals come from a model trained
    only on strictly earlier seasons, so the concatenated result is
    out-of-sample throughout and safe to use as a downstream feature
    (e.g. an input to the ownership-residual work in issue #11)."""
    seasons = sorted(panel["season"].unique())
    frames = []
    for i in range(min_train_seasons, len(seasons)):
        target_season = seasons[i]
        models = train(panel, target_season)
        if not models:
            continue
        va = panel[panel["season"] == target_season]
        frames.append(residuals(va, models))
    if not frames:
        return pd.DataFrame(columns=RESIDUAL_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def _training_panel() -> pd.DataFrame:
    return query_df(
        f"""
        SELECT gsis_id, season, week, position, {", ".join(TRAILING_FEATURES)}, {TARGET}
        FROM `{settings.features}.player_week_training`
        WHERE position IN ('QB', 'RB', 'WR', 'TE') AND {TARGET} IS NOT NULL
        """
    )


def run(season: int, week: int) -> None:
    """Write this season's walk-forward residuals to
    nfl_features.salary_pricing_lag and log the current week's watchlist."""
    panel = _training_panel()
    wf = walk_forward_residuals(panel[panel["season"] <= season])
    if wf.empty:
        log.info("Not enough seasons yet for a pricing-lag fit")
        return
    load_dataframe(wf, f"{settings.features}.salary_pricing_lag")
    watch = wf[
        (wf["season"] == season)
        & (wf["week"] == week)
        & (wf["salary_residual_z"] <= WATCHLIST_Z_THRESHOLD)
    ].sort_values("salary_residual_z")
    if watch.empty:
        log.info("No structurally underpriced players this week")
        return
    log.info(
        "Pricing-lag watchlist (%d players):\n%s",
        len(watch),
        watch.head(15).to_string(index=False),
    )


if __name__ == "__main__":
    import sys

    from ..config import current_season

    logging.basicConfig(level=logging.INFO)
    season = current_season()
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run(season, week)
