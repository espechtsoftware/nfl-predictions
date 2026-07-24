"""Walk-forward validation and the metrics that matter (guide §6.3):
MAE vs. the market, distribution calibration, and within-position rank
correlation. Random k-fold leaks team-season effects; never use it here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class EvalReport:
    mae: float
    market_mae: float | None = None
    beats_market: bool | None = None
    coverage_p10: float | None = None
    coverage_p90: float | None = None
    rank_corr_by_position: dict[str, float] = field(default_factory=dict)


def walk_forward_folds(
    seasons: list[int], min_train_seasons: int = 6
) -> tuple[list[tuple[list[int], int]], int]:
    """Expanding-window folds over `seasons`, holding the final season out
    entirely as the test set (touch once, at the very end).

    Returns ([(train_seasons, val_season), ...], test_season).
    """
    seasons = sorted(set(seasons))
    test = seasons[-1]
    develop = seasons[:-1]
    folds = [
        (develop[:i], develop[i]) for i in range(min_train_seasons, len(develop))
    ]
    if not folds:
        raise ValueError(
            f"need at least {min_train_seasons + 2} seasons for "
            f"{min_train_seasons} train + 1 validation + 1 test; got {len(seasons)}"
        )
    return folds, test


def evaluate(
    y: pd.Series | np.ndarray,
    pred: np.ndarray,
    market: pd.Series | np.ndarray | None = None,
    p10: np.ndarray | None = None,
    p90: np.ndarray | None = None,
    positions: pd.Series | None = None,
) -> EvalReport:
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    rep = EvalReport(mae=float(np.abs(pred - y).mean()))

    if market is not None:
        market = np.asarray(market, dtype=float)
        ok = ~np.isnan(market)
        # An all-null market (no props/dk_ppg for the period — see the README
        # data deficiency log) means "no comparison", not "didn't beat it".
        if ok.any():
            rep.market_mae = float(np.abs(market[ok] - y[ok]).mean())
            rep.beats_market = bool(np.abs(pred[ok] - y[ok]).mean() < rep.market_mae)

    if p10 is not None:
        rep.coverage_p10 = float(np.mean(y < np.asarray(p10, dtype=float)))
    if p90 is not None:
        rep.coverage_p90 = float(np.mean(y < np.asarray(p90, dtype=float)))

    if positions is not None:
        pos = np.asarray(positions)
        for p in pd.unique(pos):
            mask = pos == p
            if mask.sum() >= 3:
                rho = stats.spearmanr(pred[mask], y[mask]).statistic
                rep.rank_corr_by_position[str(p)] = float(rho)
    return rep


def calibration_table(
    y: np.ndarray, preds: dict[float, np.ndarray]
) -> pd.DataFrame:
    """Empirical fraction of actuals below each predicted quantile. A
    calibrated p10 shows empirical ≈ 0.10; plot this every retrain."""
    y = np.asarray(y, dtype=float)
    rows = [
        {"quantile": q, "empirical": float(np.mean(y < np.asarray(qs, dtype=float)))}
        for q, qs in sorted(preds.items())
    ]
    return pd.DataFrame(rows)
