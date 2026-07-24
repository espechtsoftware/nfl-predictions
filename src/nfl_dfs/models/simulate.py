"""Monte Carlo composition of component predictions (guide §6.2).

Each draw samples opportunity (Poisson), conversion (Binomial), and yardage
(Gamma with the predicted per-unit rate as its mean), then scores the stat
line with real DK rules — bonuses included, which is the entire point: the
mean never sees the 100-yard cliff, the draws do.

Distributions are chosen so the simulated mean equals the analytic
composition of the components (Poisson/Binomial/Gamma all preserve their
means); a biased sampler would silently shift every projection.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .scoring import StatLine, dk_points

# Gamma shape per unit of opportunity: higher = tighter yardage around the
# predicted rate. ~2 per touch reproduces observed per-catch/carry variance.
_YARDS_SHAPE = 2.0


@dataclass
class SimResult:
    summary: pd.DataFrame
    draws: np.ndarray | None = None


def _gamma_yards(
    rng: np.random.Generator, count: np.ndarray, per_unit: np.ndarray
) -> np.ndarray:
    """Total yards over `count` opportunities averaging `per_unit` each.
    Gamma(shape=count*k, scale=per_unit/k) has mean count*per_unit."""
    shape = count * _YARDS_SHAPE
    scale = np.broadcast_to(per_unit / _YARDS_SHAPE, shape.shape)
    out = np.zeros(shape.shape)
    pos = shape > 0
    out[pos] = rng.gamma(shape[pos], scale[pos])
    return out


def simulate(
    comps: pd.DataFrame,
    n_sims: int = 10_000,
    seed: int | None = None,
    keep_draws: bool = False,
) -> SimResult:
    rng = np.random.default_rng(seed)
    n = len(comps)

    def col(name: str) -> np.ndarray:
        return np.nan_to_num(comps[name].to_numpy(dtype=float))[:, None]

    targets = rng.poisson(col("targets"), (n, n_sims))
    receptions = rng.binomial(targets, col("catch_rate"))
    rec_yards = _gamma_yards(rng, receptions, col("ypr"))
    rec_tds = rng.poisson(col("rec_tds"), (n, n_sims))

    carries = rng.poisson(col("carries"), (n, n_sims))
    rush_yards = _gamma_yards(rng, carries, col("ypc"))
    rush_tds = rng.poisson(col("rush_tds"), (n, n_sims))

    attempts = rng.poisson(col("pass_attempts"), (n, n_sims))
    pass_yards = _gamma_yards(rng, attempts, col("ypa"))
    pass_tds = rng.poisson(col("pass_tds"), (n, n_sims))
    interceptions = rng.poisson(col("interceptions"), (n, n_sims))

    draws = dk_points(
        StatLine(
            pass_yards=pass_yards,
            pass_tds=pass_tds,
            interceptions=interceptions,
            rush_yards=rush_yards,
            rush_tds=rush_tds,
            receptions=receptions,
            rec_yards=rec_yards,
            rec_tds=rec_tds,
        )
    )

    summary = pd.DataFrame(
        {
            "proj_points": draws.mean(axis=1),
            "proj_p10": np.percentile(draws, 10, axis=1),
            "proj_p50": np.percentile(draws, 50, axis=1),
            "proj_p90": np.percentile(draws, 90, axis=1),
            "proj_std": draws.std(axis=1),
            "p_20_plus": (draws >= 20.0).mean(axis=1),
        },
        index=comps.index,
    )
    return SimResult(summary=summary, draws=draws if keep_draws else None)
