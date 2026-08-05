"""SBI parameter registry (Workstream B, plan §6.2-§6.3, deliverable 16.3).

v0 registers THREE simulator parameters — deliberately small, because §6.2's
rule is to add parameters only after synthetic identifiability tests show the
registered summaries can recover them:

1. ``game_factor_sigma`` — the lognormal sigma of the shared per-game
   environment factor (`simulate.GAME_FACTOR_SIGMA`, production value 0.18).
2. ``usage_dirichlet_k`` — within-team opportunity-share concentration used
   by `game_sim.allocate_drive_usage` when GAME_SIM_USAGE=dirichlet
   (production value `game_sim.DIRICHLET_CONCENTRATION_SCALE`, 20.0).
3. ``td_alloc_k`` — passing-TD allocation concentration inside the TD event
   ledger. Production behavior is an exact multinomial on mean TD shares
   (equivalent to k → ∞); a finite k switches to Dirichlet-multinomial,
   making week-to-week TD shares burstier while preserving each player's
   marginal mean.

Injection contract (plan §2.4 — disabled experiments must be behaviorally
inert): `simulate.simulate(..., params=None)` is the default everywhere in
production and is REQUIRED to be byte-identical to the pre-SBI sampler —
same RNG stream order, same draws. tests/test_sbi.py pins this with golden
checksums captured from the pre-change code. Finite overrides only ever run
through `run_simulator` below, which is research-only.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..models import simulate

__all__ = [
    "ParamSpec",
    "REGISTRY",
    "PARAM_NAMES",
    "sample_prior",
    "to_unit",
    "from_unit",
    "synthetic_slate",
    "run_simulator",
]


@dataclass(frozen=True)
class ParamSpec:
    """One inferable simulator parameter with its prior range.

    ``log_scale`` priors are log-uniform (scale parameters spanning an order
    of magnitude or more); otherwise uniform. ``default`` is the production
    value, or None when production behavior corresponds to no finite value
    (td_alloc_k: exact multinomial == infinite concentration).
    """

    name: str
    default: float | None
    low: float
    high: float
    log_scale: bool
    rationale: str


REGISTRY: tuple[ParamSpec, ...] = (
    ParamSpec(
        name="game_factor_sigma",
        default=simulate.GAME_FACTOR_SIGMA,  # 0.18
        low=0.05,
        high=0.40,
        log_scale=False,
        rationale=(
            "Real game totals run 44.2 +/- 13.8 (pbp fit 2018-2025, see "
            "game_sim.py header), a relative sd of ~0.31 that UPPER-bounds "
            "the shared environment factor because total-points variance "
            "also includes drive-outcome noise the player-level Poisson/"
            "Gamma draws already carry. The validated production value is "
            "0.18; 0.05 keeps a near-independent-environment world in "
            "scope. Wide on purpose per plan §6.3 (expose misspecification)."
        ),
    ),
    ParamSpec(
        name="usage_dirichlet_k",
        default=20.0,  # game_sim.DIRICHLET_CONCENTRATION_SCALE default
        low=4.0,
        high=120.0,
        log_scale=True,
        rationale=(
            "K=20 shipped with the ledger note 'concentration scale is the "
            "retune knob' (game_sim.py); lower K = spikier next-man-up "
            "allocations, higher K = shares pinned to their priors. "
            "Dirichlet-multinomial fits of weekly usage shares typically "
            "land in the tens; log-uniform over 4-120 spans heavily "
            "overdispersed committees to near-deterministic role locks."
        ),
    ),
    ParamSpec(
        name="td_alloc_k",
        default=None,  # production = exact multinomial (k -> infinity)
        low=2.0,
        high=60.0,
        log_scale=True,
        rationale=(
            "Passing-TD counts are small integers allocated by red-zone "
            "roles that churn week to week, so realized TD shares are "
            "burstier than season-mean shares. The production ledger uses "
            "the mean shares exactly (k -> inf); a Dirichlet-multinomial "
            "with concentration k spans near-multinomial (k=60) down to "
            "one-catcher-takes-all bursts (k=2). Log-uniform: k is a scale "
            "parameter."
        ),
    ),
)

PARAM_NAMES: tuple[str, ...] = tuple(p.name for p in REGISTRY)
_SPEC_BY_NAME = {p.name: p for p in REGISTRY}


def _specs(names: tuple[str, ...] | list[str] | None) -> list[ParamSpec]:
    if names is None:
        return list(REGISTRY)
    return [_SPEC_BY_NAME[n] for n in names]


def to_unit(theta: np.ndarray, names: list[str] | None = None) -> np.ndarray:
    """Map parameter values (n, d) into the prior's unit cube (log-scale
    params via log). Rank/contraction metrics live in this space so uniform
    and log-uniform priors are treated on equal footing."""
    specs = _specs(names)
    theta = np.atleast_2d(np.asarray(theta, dtype=float))
    out = np.empty_like(theta)
    for j, s in enumerate(specs):
        if s.log_scale:
            out[:, j] = (np.log(theta[:, j]) - np.log(s.low)) / (
                np.log(s.high) - np.log(s.low)
            )
        else:
            out[:, j] = (theta[:, j] - s.low) / (s.high - s.low)
    return out


def from_unit(u: np.ndarray, names: list[str] | None = None) -> np.ndarray:
    specs = _specs(names)
    u = np.atleast_2d(np.asarray(u, dtype=float))
    out = np.empty_like(u)
    for j, s in enumerate(specs):
        if s.log_scale:
            out[:, j] = np.exp(np.log(s.low) + u[:, j] * (np.log(s.high) - np.log(s.low)))
        else:
            out[:, j] = s.low + u[:, j] * (s.high - s.low)
    return out


def sample_prior(
    rng: np.random.Generator, n: int, names: list[str] | None = None
) -> np.ndarray:
    """(n, d) prior draws via a Latin-hypercube design (plan §6.5 asks for a
    space-filling design; LHS is the simplest one). Each column is a
    permuted stratified sample of the unit interval, then mapped through
    the param's uniform or log-uniform transform."""
    specs = _specs(names)
    d = len(specs)
    u = (rng.random((n, d)) + np.stack([rng.permutation(n) for _ in range(d)], axis=1)) / n
    return from_unit(u, names=[s.name for s in specs])


# ---------------------------------------------------------------------------
# Synthetic slate + simulator harness
# ---------------------------------------------------------------------------

# role, targets, catch_rate, ypr, rec_tds, carries, ypc, rush_tds,
# pass_attempts, ypa, pass_tds, interceptions
_TEAM_TEMPLATE: tuple[tuple, ...] = (
    ("QB", 0.0, 0.0, 0.0, 0.00, 5.0, 4.5, 0.12, 33.0, 7.1, 1.55, 0.80),
    ("RB", 3.5, 0.75, 6.5, 0.06, 14.0, 4.3, 0.45, 0.0, 0.0, 0.0, 0.0),
    ("RB", 1.8, 0.72, 6.0, 0.03, 6.0, 4.1, 0.12, 0.0, 0.0, 0.0, 0.0),
    ("WR", 8.5, 0.64, 12.5, 0.42, 0.4, 6.0, 0.02, 0.0, 0.0, 0.0, 0.0),
    ("WR", 6.0, 0.62, 11.0, 0.28, 0.2, 5.0, 0.01, 0.0, 0.0, 0.0, 0.0),
    ("WR", 3.5, 0.60, 10.0, 0.14, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    ("TE", 4.5, 0.68, 9.0, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
)
_COMP_COLS = (
    "targets", "catch_rate", "ypr", "rec_tds", "carries", "ypc",
    "rush_tds", "pass_attempts", "ypa", "pass_tds", "interceptions",
)
# rec_tds sum (1.18) < pass_tds (1.55) on the template team, so the TD
# ledger's unrostered-catcher "other" bucket is exercised by construction.


def synthetic_slate(
    n_games: int = 3, seed: int = 0
) -> tuple[pd.DataFrame, pd.Series, pd.Series, np.ndarray]:
    """Deterministic synthetic slate: (comps, game_ids, team_ids, roles).

    ``n_games`` games x 2 teams x 7 players. Team-level volume jitter
    (+/-10%, seeded) keeps teams from being identical without touching
    the template's internal share structure. `catch_rate` and yardage
    rates are NOT jittered — only volume — so marginal-mean checks stay
    interpretable.
    """
    rng = np.random.default_rng(seed)
    rows, games, teams, roles = [], [], [], []
    for g in range(n_games):
        for side in ("A", "B"):
            team = f"T{2 * g + (side == 'B')}"
            vol = 1.0 + rng.uniform(-0.10, 0.10)
            for tmpl in _TEAM_TEMPLATE:
                role, vals = tmpl[0], dict(zip(_COMP_COLS, tmpl[1:]))
                for k in ("targets", "carries", "pass_attempts",
                          "rec_tds", "rush_tds", "pass_tds"):
                    vals[k] *= vol
                rows.append(vals)
                games.append(f"G{g}")
                teams.append(team)
                roles.append(role)
    comps = pd.DataFrame(rows)
    return comps, pd.Series(games), pd.Series(teams), np.array(roles)


@contextlib.contextmanager
def _env(**kv: str) -> Iterator[None]:
    old = {k: os.environ.get(k) for k in kv}
    os.environ.update(kv)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run_simulator(
    theta: dict[str, float] | None,
    comps: pd.DataFrame,
    game_ids: pd.Series,
    team_ids: pd.Series,
    n_sims: int = 1500,
    seed: int | None = None,
) -> np.ndarray:
    """Run the production simulator with parameter overrides; returns the
    (n_players, n_sims) DK-point draws matrix.

    Research-only harness: temporarily enables the two off-by-default
    joint-structure levers the registered parameters live behind
    (TD_LEDGER for td_alloc_k, GAME_SIM_USAGE=dirichlet for
    usage_dirichlet_k) so every registered parameter actually fires —
    inferring a parameter through a code path that never runs is exactly
    the vacuity failure the validation laws warn about. Production
    callers never go through here.
    """
    with _env(TD_LEDGER="1", GAME_SIM_USAGE="dirichlet", GAME_SIM_MODE="lognormal"):
        res = simulate.simulate(
            comps,
            n_sims=n_sims,
            seed=seed,
            keep_draws=True,
            game_ids=game_ids,
            team_ids=team_ids,
            params=theta,
        )
    assert res.draws is not None
    return res.draws
