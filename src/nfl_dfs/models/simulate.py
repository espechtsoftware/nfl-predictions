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
    team_ids: pd.Series | None = None,
) -> SimResult:
    """game_ids (aligned to comps) enables correlated game environments:
    one shared lognormal factor per (game, sim) scales every player's
    opportunity in that game, so shootouts lift whole games together.
    Milly winners take 50-80% of their points from one game — without this
    the simulator prices such lineups as near-impossible. Mean-preserving
    (E[factor]=1), so projections are unchanged; only the joint tail moves.

    team_ids (aligned to comps, optional): only consulted when
    GAME_SIM_MODE=possession. Lets the two teams in a game draw DIFFERENT
    mean-preserving factors (game_sim.team_game_factors) instead of one
    shared value — the game-script asymmetry (leading team runs more,
    trailing team's DST/receivers skew differently) that's the possession
    sim's whole motivation over the shared lognormal factor. Without
    team_ids, possession mode falls back to one shared factor per game
    (game_sim.game_factor_matrix), same granularity as the lognormal draw."""
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
            # GAME_SIM_TEAM_FACTORS=0 forces the shared per-game factor even
            # when team_ids are supplied -- the middle arm of the 3-arm A/B
            # (lognormal / possession-shared / possession-team), so a team-arm
            # result can be attributed to team independence vs the drive
            # engine itself. See the design doc's correlation caveat.
            team_arm = os.environ.get("GAME_SIM_TEAM_FACTORS", "1") != "0"
            if team_ids is not None and team_arm:
                team_series = pd.Series(team_ids).fillna("_none").reset_index(drop=True)
                game_series = pd.Series(codes)
                # Row order within each game group is player order, not a
                # kickoff coin flip -- "first" just needs to be a stable,
                # consistent pick per game so both of a game's teams land
                # on different slots; which team is slot 0 vs 1 doesn't
                # matter since factors_a/factors_b are symmetric in intent.
                first_team = team_series.groupby(game_series).transform("first")
                slot = (team_series != first_team).astype(int).to_numpy()
                factors_a, factors_b = game_sim.team_game_factors(rng, len(uniq), n_sims)
                game_mult = np.where(slot[:, None] == 0, factors_a[codes], factors_b[codes])
            else:
                g = game_sim.game_factor_matrix(rng, len(uniq), n_sims)
                game_mult = g[codes]
        else:
            g = rng.lognormal(-GAME_FACTOR_SIGMA ** 2 / 2, GAME_FACTOR_SIGMA,
                              (len(uniq), n_sims))
            game_mult = g[codes]

    def col(name: str) -> np.ndarray:
        return np.nan_to_num(comps[name].to_numpy(dtype=float))[:, None]

    def opp(name: str) -> np.ndarray:
        """Opportunity means, scaled by the shared game factor per sim."""
        return col(name) * game_mult

    # GAME_SIM_USAGE=dirichlet (+ team_ids): correlated within-team usage.
    # Instead of each player independently Poisson-ing around their own
    # mean, each TEAM's total opportunity mean is split across teammates
    # by a Dirichlet draw centered on their shares
    # (game_sim.allocate_drive_usage), then Poisson-ed. Teammates become
    # negatively correlated (WR1 boom <-> WR2 squeeze) and low-share
    # players occasionally draw real volume -- the next-man-up boom
    # variance Addendum 24 found under-modeled. Mean-preserving:
    # E[Dirichlet share] = prior share. Off by default; same call-time
    # env pattern as GAME_SIM_MODE.
    usage_dirichlet = (os.environ.get("GAME_SIM_USAGE", "") == "dirichlet"
                       and team_ids is not None)
    team_codes = None
    if usage_dirichlet:
        team_codes, _ = pd.factorize(pd.Series(team_ids).fillna("_none").to_numpy())

    def opp_draw(name: str) -> np.ndarray:
        """Integer opportunity draws for stat `name` (targets/carries)."""
        means = opp(name)
        if not usage_dirichlet:
            return rng.poisson(means)
        from . import game_sim
        base = np.nan_to_num(comps[name].to_numpy(dtype=float))
        means = means.copy()
        for t in np.unique(team_codes):
            rows = np.flatnonzero((team_codes == t) & (base > 0))
            if len(rows) < 2:
                continue  # nothing to reallocate within
            shares = base[rows] / base[rows].sum()
            totals = means[rows].sum(axis=0)  # (n_sims,) game-factor-scaled
            alloc = game_sim.allocate_drive_usage(rng, totals, shares, n_sims=n_sims)
            means[rows] = np.atleast_2d(alloc).T
        return rng.poisson(means)

    targets = opp_draw("targets")
    receptions = rng.binomial(targets, col("catch_rate"))
    rec_yards = _gamma_yards(rng, receptions, col("ypr"))
    rec_tds = rng.poisson(col("rec_tds"), (n, n_sims))

    carries = opp_draw("carries")
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
