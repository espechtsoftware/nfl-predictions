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

import os
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


GAME_FACTOR_SIGMA = 0.18  # lognormal sigma of the shared per-game factor


def simulate(
    comps: pd.DataFrame,
    n_sims: int = 10_000,
    seed: int | None = None,
    keep_draws: bool = False,
    game_ids: pd.Series | None = None,
) -> SimResult:
    """game_ids (aligned to comps) enables correlated game environments:
    one shared lognormal factor per (game, sim) scales every player's
    opportunity in that game, so shootouts lift whole games together.
    Milly winners take 50-80% of their points from one game — without this
    the simulator prices such lineups as near-impossible. Mean-preserving
    (E[factor]=1), so projections are unchanged; only the joint tail moves."""
    rng = np.random.default_rng(seed)
    n = len(comps)

    game_mult = np.ones((n, n_sims))
    if game_ids is not None:
        codes, uniq = pd.factorize(pd.Series(game_ids).fillna("_none").to_numpy())
        # GAME_SIM_MODE=possession swaps the lognormal game factor for the
        # drive-state Markov engine in game_sim.py (issue #13 item 6). Read
        # at call time like the other A/B env flags (N_DARKGAME, ALT_CEIL).
        # Off by default -- see reports/possession-simulator-design.md; its
        # transition probabilities are a placeholder, not yet fit from pbp.
        if os.environ.get("GAME_SIM_MODE", "lognormal") == "possession":
            from . import game_sim
            g = game_sim.game_factor_matrix(rng, len(uniq), n_sims)
        else:
            g = rng.lognormal(-GAME_FACTOR_SIGMA ** 2 / 2, GAME_FACTOR_SIGMA,
                              (len(uniq), n_sims))
        game_mult = g[codes]

    def col(name: str) -> np.ndarray:
        return np.nan_to_num(comps[name].to_numpy(dtype=float))[:, None]

    def opp(name: str) -> np.ndarray:
        """Opportunity means, scaled by the shared game factor per sim."""
        return col(name) * game_mult

    targets = rng.poisson(opp("targets"))
    receptions = rng.binomial(targets, col("catch_rate"))
    rec_yards = _gamma_yards(rng, receptions, col("ypr"))
    rec_tds = rng.poisson(col("rec_tds"), (n, n_sims))

    carries = rng.poisson(opp("carries"))
    rush_yards = _gamma_yards(rng, carries, col("ypc"))
    rush_tds = rng.poisson(col("rush_tds"), (n, n_sims))

    attempts = rng.poisson(opp("pass_attempts"))
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
