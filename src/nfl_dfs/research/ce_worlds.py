"""Workstream D: cross-entropy rare-world generation (scoring plan §10).

Elite legal lineups come from a structured subset of game
environments. HYPER hand-picked that subset (top-N games by projected
total, everyone at p98) and nulled at 24/107. A cross-entropy sampler
LEARNS which environments produce elite oracle lineups instead of
assuming them.

Latent knobs are simulator parameters with clear semantics and
validated bounds (plan §10.2) — NOT the buried hand-specified TD
ledger under a new name:
    pace multiplier, pass-rate tilt, team scoring split,
    usage concentration
The loop keeps importance weights so downstream probabilities stay
unbiased, and monitors effective sample size so the proposal cannot
collapse onto a handful of worlds.
"""
from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)

# (name, lo, hi, prior_mean, prior_sd) — bounds are the documented
# ranges of the corresponding simulator behaviour
KNOBS = (
    ("pace", 0.80, 1.30, 1.00, 0.10),
    ("pass_tilt", -0.15, 0.15, 0.00, 0.05),
    ("score_split", 0.30, 0.70, 0.50, 0.08),
    ("usage_conc", 0.50, 2.00, 1.00, 0.25),
)


def sample_knobs(rng, n: int, mu=None, sd=None) -> np.ndarray:
    """Truncated-normal proposal over the knob vector."""
    mu = np.array([k[3] for k in KNOBS]) if mu is None else np.asarray(mu)
    sd = np.array([k[4] for k in KNOBS]) if sd is None else np.asarray(sd)
    lo = np.array([k[1] for k in KNOBS])
    hi = np.array([k[2] for k in KNOBS])
    x = rng.normal(mu, sd, size=(n, len(KNOBS)))
    return np.clip(x, lo, hi)


def apply_knobs(draws: np.ndarray, knobs: np.ndarray, team_codes,
                pos_is_pass) -> np.ndarray:
    """Deform a world's player means coherently at team/game level.

    pace scales everyone; pass_tilt moves pass-game players against
    run-game players; score_split shifts one team's share against the
    other; usage_conc sharpens or flattens within-team distribution.
    Mean-preserving in expectation across the prior.
    """
    out = draws.astype(float).copy()
    pace, tilt, split, conc = knobs
    out *= pace
    out[pos_is_pass] *= (1.0 + tilt)
    out[~pos_is_pass] *= (1.0 - tilt)
    tc = np.asarray(team_codes)
    for i, t in enumerate(np.unique(tc)):
        m = tc == t
        share = split if i == 0 else (1.0 - split)
        out[m] *= (2.0 * share)
        v = out[m]
        if len(v) > 1 and conc != 1.0:
            mu = v.mean(axis=0, keepdims=True)
            out[m] = mu + (v - mu) * conc
    return np.maximum(out, 0.0)


def ce_iterate(score_world, rng, n_per_round: int = 60, rounds: int = 4,
               elite_frac: float = 0.2, smooth: float = 0.7):
    """Cross-entropy loop. `score_world(knobs) -> float` returns the
    world's constrained-oracle objective. Returns (elite_knobs,
    weights, diagnostics) with importance weights relative to the
    production prior so downstream probabilities stay unbiased."""
    mu = np.array([k[3] for k in KNOBS], dtype=float)
    sd = np.array([k[4] for k in KNOBS], dtype=float)
    p_mu, p_sd = mu.copy(), sd.copy()
    hist = []
    elites = np.empty((0, len(KNOBS)))
    for r in range(rounds):
        X = sample_knobs(rng, n_per_round, mu, sd)
        s = np.array([score_world(x) for x in X])
        k = max(2, int(elite_frac * n_per_round))
        idx = np.argsort(s)[::-1][:k]
        E = X[idx]
        elites = np.vstack([elites, E])
        new_mu = E.mean(axis=0)
        new_sd = np.maximum(E.std(axis=0), 1e-3)
        mu = smooth * new_mu + (1 - smooth) * mu
        sd = smooth * new_sd + (1 - smooth) * sd
        # effective sample size guards against proposal collapse
        w = _iw(E, mu, sd, p_mu, p_sd)
        ess = (w.sum() ** 2) / np.maximum((w ** 2).sum(), 1e-12)
        hist.append({"round": r, "elite_mean_score": float(s[idx].mean()),
                     "all_mean_score": float(s.mean()),
                     "ess": float(ess), "mu": mu.copy().tolist()})
        log.info("CE round %d: elite %.1f (all %.1f) ESS %.1f mu %s",
                 r, s[idx].mean(), s.mean(), ess, np.round(mu, 3))
    return elites, _iw(elites, mu, sd, p_mu, p_sd), hist


def _iw(X, mu, sd, p_mu, p_sd):
    """Importance weights prior/proposal (diagonal normals)."""
    def logpdf(x, m, s):
        return -0.5 * (((x - m) / s) ** 2 + np.log(2 * np.pi * s ** 2)).sum(1)
    return np.exp(logpdf(X, p_mu, p_sd) - logpdf(X, mu, sd))
