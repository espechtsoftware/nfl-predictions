"""Cross-entropy sampling of coherent, game-local rare environments."""
from __future__ import annotations

import logging

import numpy as np
from scipy.stats import truncnorm

log = logging.getLogger(__name__)

KNOBS = (
    ("pace", 0.80, 1.30, 1.00, 0.10),
    ("pass_tilt", -0.15, 0.15, 0.00, 0.05),
    ("score_split", 0.30, 0.70, 0.50, 0.08),
    ("usage_conc", 0.50, 2.00, 1.00, 0.25),
)


def _parameter_arrays(n_games: int):
    lo = np.tile([k[1] for k in KNOBS], n_games).astype(float)
    hi = np.tile([k[2] for k in KNOBS], n_games).astype(float)
    mu = np.tile([k[3] for k in KNOBS], n_games).astype(float)
    sd = np.tile([k[4] for k in KNOBS], n_games).astype(float)
    return lo, hi, mu, sd


def sample_knobs(rng, n: int, mu=None, sd=None, n_games: int = 1):
    """Draw from the actual bounded (truncated-normal) proposal."""
    lo, hi, prior_mu, prior_sd = _parameter_arrays(n_games)
    mu = prior_mu if mu is None else np.asarray(mu, dtype=float).reshape(-1)
    sd = prior_sd if sd is None else np.asarray(sd, dtype=float).reshape(-1)
    a, b = (lo - mu) / sd, (hi - mu) / sd
    x = truncnorm.rvs(a, b, loc=mu, scale=sd, size=(n, len(mu)),
                      random_state=rng)
    shaped = x.reshape(n, n_games, len(KNOBS))
    return shaped[:, 0, :] if n_games == 1 else shaped


def apply_knobs(draws: np.ndarray, knobs: np.ndarray, team_codes,
                pos_is_pass, game_codes=None) -> np.ndarray:
    """Apply pace, scoring and usage changes independently within games.

    Team scoring allocations are paired only with the opponent in the same
    game. Pass tilt and usage concentration redistribute a team's existing
    fantasy-point total rather than manufacturing player-level boosts.
    """
    out = np.maximum(draws.astype(float).copy(), 0.0)
    tc = np.asarray(team_codes)
    pc = np.asarray(pos_is_pass, dtype=bool)
    gc = (np.zeros(len(tc), dtype=int) if game_codes is None
          else np.asarray(game_codes))
    games = list(dict.fromkeys(gc.tolist()))
    K = np.asarray(knobs, dtype=float)
    if K.ndim == 1:
        K = np.repeat(K[None, :], len(games), axis=0)
    if len(K) != len(games):
        raise ValueError("one CE knob vector is required per game")

    for gi, game in enumerate(games):
        gm = gc == game
        pace, tilt, split, conc = K[gi]
        out[gm] *= pace
        teams = sorted(np.unique(tc[gm]).tolist())
        if len(teams) == 2:
            a, b = (gm & (tc == teams[0])), (gm & (tc == teams[1]))
            total = out[a].sum(axis=0) + out[b].sum(axis=0)
            for mask, share in ((a, split), (b, 1.0 - split)):
                cur = out[mask].sum(axis=0)
                out[mask] *= np.divide(total * share, cur,
                                       out=np.ones_like(cur), where=cur > 0)

        for team in teams:
            tm = gm & (tc == team)
            before = out[tm].sum(axis=0)
            pass_mask, run_mask = tm & pc, tm & ~pc
            out[pass_mask] *= 1.0 + tilt
            out[run_mask] *= 1.0 - tilt
            after_tilt = out[tm].sum(axis=0)
            out[tm] *= np.divide(before, after_tilt,
                                 out=np.ones_like(before), where=after_tilt > 0)
            if conc != 1.0:
                concentrated = np.power(np.maximum(out[tm], 1e-12), conc)
                denom = concentrated.sum(axis=0)
                out[tm] = concentrated * np.divide(
                    before, denom, out=np.ones_like(before), where=denom > 0)
    return out


def ce_iterate(score_world, rng, n_per_round: int = 60, rounds: int = 4,
               elite_frac: float = 0.2, smooth: float = 0.7,
               n_games: int = 1, min_ess_frac: float = 0.20):
    """Fit a bounded proposal and return elites from the final round only."""
    lo, hi, prior_mu, prior_sd = _parameter_arrays(n_games)
    mu, sd = prior_mu.copy(), prior_sd.copy()
    hist = []
    final_elites = None
    for r in range(rounds):
        X = sample_knobs(rng, n_per_round, mu, sd, n_games=n_games)
        flat = X.reshape(n_per_round, -1)
        s = np.asarray([score_world(x) for x in X], dtype=float)
        k = max(2, int(elite_frac * n_per_round))
        idx = np.argsort(s)[::-1][:k]
        E = flat[idx]
        final_elites = E

        weights = _iw(flat, mu, sd, prior_mu, prior_sd, lo, hi)
        ess = (weights.sum() ** 2) / max(float((weights ** 2).sum()), 1e-12)
        collapsed = ess < min_ess_frac * n_per_round
        new_mu = E.mean(axis=0)
        new_sd = np.maximum(E.std(axis=0), prior_sd * 0.10)
        if collapsed:
            # Do not narrow an already poorly supported proposal further.
            new_sd = np.maximum(new_sd, sd)
        mu = smooth * new_mu + (1.0 - smooth) * mu
        sd = smooth * new_sd + (1.0 - smooth) * sd
        mu = np.clip(mu, lo, hi)
        hist.append({"round": r, "elite_mean_score": float(s[idx].mean()),
                     "all_mean_score": float(s.mean()), "ess": float(ess),
                     "collapsed": collapsed, "mu": mu.copy().tolist()})
        log.info("CE round %d: elite %.1f (all %.1f) ESS %.1f%s", r,
                 s[idx].mean(), s.mean(), ess,
                 " (proposal guarded)" if collapsed else "")

    elites = final_elites.reshape(-1, n_games, len(KNOBS))
    shaped = elites[:, 0, :] if n_games == 1 else elites
    weights = _iw(final_elites, mu, sd, prior_mu, prior_sd, lo, hi)
    return shaped, weights, hist


def _iw(X, mu, sd, prior_mu, prior_sd, lo, hi):
    """Prior/proposal weights using matching truncated-normal densities."""
    X = np.asarray(X, dtype=float).reshape(len(X), -1)

    def logpdf(x, m, s):
        a, b = (lo - m) / s, (hi - m) / s
        return truncnorm.logpdf(x, a, b, loc=m, scale=s).sum(axis=1)

    logw = logpdf(X, prior_mu, prior_sd) - logpdf(X, mu, sd)
    logw -= np.max(logw)
    return np.exp(logw)
