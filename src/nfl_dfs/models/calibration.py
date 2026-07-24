"""Quantile calibration: widen the simulated p10-p90 band per position.

Season replays showed the Monte Carlo distribution is too narrow — actuals
fell below p10 on 13-24% of rows (target 10%), worst for QB/RB where TD
variance dominates. The fix is a per-position multiplicative widen of the
quantile band around the median (std scales with it), fit on replayed
seasons by grid search to hit nominal coverage.

DEFAULT_WIDEN was fit on pooled 2019+2021 replays (models trained strictly
pre-season; see backtest/replay.py) and verified out-of-sample on 2025.
Refit with `fit_widen_factors` whenever the simulator changes materially.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_WIDEN = {"QB": 1.5, "RB": 1.45, "TE": 1.05, "WR": 1.1}


def apply_widen(
    preds: pd.DataFrame,
    positions: pd.Series,
    factors: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Stretch [proj_p10, proj_p90] around proj_p50 by each row's position
    factor; proj_std scales with the band. proj_points is untouched — the
    mean was never the problem."""
    factors = DEFAULT_WIDEN if factors is None else factors
    w = positions.map(lambda p: factors.get(p, 1.0)).to_numpy(dtype=float)
    out = preds.copy()
    p50 = out.proj_p50.to_numpy()
    out["proj_p10"] = p50 - (p50 - out.proj_p10.to_numpy()) * w
    out["proj_p90"] = p50 + (out.proj_p90.to_numpy() - p50) * w
    out["proj_std"] = out.proj_std.to_numpy() * w
    return out


def fit_widen_factors(
    replay_proj: pd.DataFrame,
    grid: np.ndarray | None = None,
    targets: tuple[float, float] = (0.10, 0.90),
) -> dict[str, float]:
    """Per-position widen factor minimizing coverage error on replayed
    projections (columns: position, actual, proj_p10/p50/p90)."""
    grid = np.arange(1.0, 2.61, 0.05) if grid is None else grid
    lo, hi = targets
    factors: dict[str, float] = {}
    for pos, grp in replay_proj.groupby("position"):
        p50 = grp.proj_p50.to_numpy()
        d10 = p50 - grp.proj_p10.to_numpy()
        d90 = grp.proj_p90.to_numpy() - p50
        actual = grp.actual.to_numpy()
        losses = [
            abs(np.mean(actual < p50 - d10 * w) - lo)
            + abs(np.mean(actual < p50 + d90 * w) - hi)
            for w in grid
        ]
        factors[str(pos)] = round(float(grid[int(np.argmin(losses))]), 2)
    return factors
