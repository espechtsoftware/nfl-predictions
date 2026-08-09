"""Workstream C: similarity-conditioned Schaake shuffle (scoring plan
§9; axis corrected per review #5 round 3).

The idea: our marginals are calibrated but the DEPENDENCE between
players in a game is modelled (possession Markov + shared factor).
Real games contain joint patterns — shootouts, usage cannibalization,
blowout suppression, correlated touchdowns — that no parametric
coupling reproduced (the TD ledger tried and cost 8 tails).

A Schaake shuffle imports the dependence EMPIRICALLY: take a real
historical game, read off each ROLE's rank ACROSS a matched-game
sample, and impose that rank pattern on the current players' marginal
quantiles. Marginals are preserved exactly by construction (we only
permute which quantile each player receives); only the joint pattern
changes.

CRITICAL axis note: ranks are computed for each role ACROSS its
matched historical games — NOT within a single game across roles. The
within-game version does not preserve role marginals.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# roles the template carries, per team
ROLES = ("QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE1", "DST")
# similarity features (all available PRE-LOCK)
SIM_FEATURES = ("game_total", "spread_abs", "pace_env_l6",
                "neutral_pass_rate_l6", "team_top2_target_share_l6")


def assign_roles(players: pd.DataFrame) -> pd.Series:
    """Role label per player from PRE-LOCK information only (salary
    rank within team+position — never realized output)."""
    out = pd.Series(index=players.index, dtype=object)
    for (team, pos), g in players.groupby(["team", "pos"]):
        order = g.salary.rank(ascending=False, method="first")
        for idx, k in order.items():
            k = int(k)
            if pos == "QB" and k == 1:
                out[idx] = "QB"
            elif pos == "DST":
                out[idx] = "DST"
            elif pos in ("RB", "WR", "TE") and k <= 3:
                out[idx] = f"{pos}{k}" if pos != "TE" or k == 1 else None
    return out


def build_game_bank(games: pd.DataFrame) -> pd.DataFrame:
    """One row per historical GAME carrying BOTH teams' role ranks
    (suffix _a / _b).

    2026-08-06: the first version keyed templates by (game, team) and
    drew one row per world shared across both teams — which forced the
    two QBs in a game onto the same rank and produced a QB-vs-oppQB
    correlation of 0.87 against a realized 0.15. Dependence ACROSS the
    two teams (the shootout channel) is exactly what a game-level
    template preserves empirically, so the unit must be the game."""
    g = games.dropna(subset=["role", "dk_points"]).copy()
    g["rank_pct"] = g.groupby("role").dk_points.rank(pct=True)
    rows = []
    for (se, wk, gid), gg in g.groupby(["season", "week", "game_id"]):
        teams = list(gg.team.unique())
        if len(teams) != 2:
            continue
        # Preserve the football meaning of the two template sides.  The old
        # alphabetical a/b mapping could apply a favorite's outcome ranks to
        # the current underdog merely because of team abbreviations.
        if "implied_team_total" in gg:
            strength = (gg.groupby("team").implied_team_total.mean()
                        .to_dict())
            teams = sorted(teams, key=lambda t: (-strength.get(t, -np.inf),
                                                 str(t)))
        else:
            teams = sorted(teams)
        rec = {"season": se, "week": wk, "game_id": gid}
        for side, t in zip(("fav", "dog"), teams):
            sub = gg[gg.team == t]
            for _, r in sub.iterrows():
                rec[f"{r.role}_{side}"] = r.rank_pct
        for c in SIM_FEATURES:
            if c in gg.columns:
                rec[c] = pd.to_numeric(gg[c], errors="coerce").mean()
        rows.append(rec)
    return pd.DataFrame(rows)


def apply_schaake_game(draws, roles, teams, templates, seed=0,
                       team_values=None, template_probabilities=None):
    """Impose GAME-level template patterns: one historical game per
    simulated world; our two teams take its _a and _b sides."""
    rng = np.random.default_rng(seed)
    n, n_sims = draws.shape
    if templates.empty or n == 0:
        return draws
    out = draws.copy()
    srt = np.sort(draws, axis=1)
    tm = np.asarray(teams)
    sides = list(pd.unique(tm))
    if team_values is not None:
        tv = np.asarray(team_values, dtype=float)
        strength = {team: float(np.nanmean(tv[tm == team]))
                    for team in sides}
        sides = sorted(sides, key=lambda team: (-strength[team], str(team)))
    else:
        sides = sorted(sides)
    probabilities = None
    if template_probabilities is not None:
        probabilities = np.asarray(template_probabilities, dtype=float)
        if probabilities.shape != (len(templates),):
            raise ValueError("template probabilities do not match templates")
        if (not np.isfinite(probabilities).all()
                or np.any(probabilities < 0)
                or probabilities.sum() <= 0):
            raise ValueError("template probabilities are invalid")
        probabilities = probabilities / probabilities.sum()
    # Preserve the default path's seeded byte sequence.  ``choice(p=None)``
    # is statistically equivalent to ``integers`` but is not a contractual
    # guarantee of the same RNG consumption across NumPy versions.
    pick = (rng.integers(0, len(templates), size=n_sims)
            if probabilities is None
            else rng.choice(
                len(templates), size=n_sims, replace=True, p=probabilities))
    T = templates.reset_index(drop=True)
    # Sampling templates with replacement necessarily creates repeated
    # historical percentiles.  The Schaake operation must nevertheless be
    # a PERMUTATION of 0..n_sims-1 for every player; indexing the marginal
    # directly by the historical percentile changes its distribution.
    # A shared tie-break preserves the association of repeated templates
    # across roles while assigning every current marginal draw exactly once.
    tie_break = rng.permutation(n_sims)
    semantic_sides = any(str(c).endswith("_fav") for c in T.columns)
    for si, team in enumerate(sides[:2]):
        suf = (("fav", "dog")[si] if semantic_sides
               else ("a", "b")[si])
        for i in np.flatnonzero(tm == team):
            role = roles.iloc[i] if hasattr(roles, "iloc") else roles[i]
            col = f"{role}_{suf}"
            if col not in T.columns:
                continue
            r = T[col].to_numpy(dtype=float)[pick]
            r = np.where(np.isfinite(r), r, rng.random(n_sims))
            order = np.lexsort((tie_break, r))
            q = np.empty(n_sims, dtype=int)
            q[order] = np.arange(n_sims)
            out[i] = srt[i][q]
    return out


def build_template_bank(games: pd.DataFrame) -> pd.DataFrame:
    """DEPRECATED (team-keyed). One row per (game, team).

    `games` needs: game_id, season, week, team, role, dk_points, plus
    the similarity features. Ranks are percentile ranks of the role's
    realized score computed across ALL games in the bank for that
    role — the standard Schaake construction.
    """
    g = games.dropna(subset=["role", "dk_points"]).copy()
    g["rank_pct"] = g.groupby("role").dk_points.rank(pct=True)
    piv = g.pivot_table(index=["season", "week", "game_id", "team"],
                        columns="role", values="rank_pct", aggfunc="first")
    ctx = (g.groupby(["season", "week", "game_id", "team"])
             [[c for c in SIM_FEATURES if c in g.columns]].first())
    bank = piv.join(ctx).reset_index()
    return bank


def match_templates(bank: pd.DataFrame, ctx: dict, season: int, week: int,
                    k: int = 40, rng=None) -> pd.DataFrame:
    """K nearest historical (game, team) units by normalized distance
    on the similarity features. POINT-IN-TIME: only units strictly
    before (season, week) are eligible."""
    past = bank[(bank.season < season)
                | ((bank.season == season) & (bank.week < week))]
    if past.empty:
        return past
    feats = [c for c in SIM_FEATURES if c in past.columns and c in ctx]
    if not feats:
        return past.sample(min(k, len(past)),
                           random_state=0 if rng is None else None)
    X = past[feats].to_numpy(dtype=float)
    mu, sd = np.nanmean(X, axis=0), np.nanstd(X, axis=0) + 1e-9
    q = np.array([ctx[c] for c in feats], dtype=float)
    X = np.where(np.isfinite(X), X, mu)
    q = np.where(np.isfinite(q), q, mu)
    d = np.linalg.norm((X - mu) / sd - (q - mu) / sd, axis=1)
    return past.iloc[np.argsort(d)[:k]]


def apply_schaake(draws: np.ndarray, roles: pd.Series, teams: pd.Series,
                  templates: pd.DataFrame, seed: int = 0) -> np.ndarray:
    """Impose template rank patterns on existing marginal draws.

    For each simulated world, draw one matched template per team and
    give every rostered role the quantile of its OWN marginal
    distribution at that template's rank. Marginals are preserved
    exactly: we permute each player's own sorted draws, never mix
    players' distributions.
    """
    rng = np.random.default_rng(seed)
    n, n_sims = draws.shape
    if templates.empty:
        return draws
    out = draws.copy()
    srt = np.sort(draws, axis=1)          # each player's own marginal
    tmpl = templates[[r for r in ROLES if r in templates.columns]]
    tmat = tmpl.to_numpy(dtype=float)
    tcols = list(tmpl.columns)
    col_of = {r: i for i, r in enumerate(tcols)}
    pick = rng.integers(0, len(tmat), size=(n_sims,))
    tie_break = rng.permutation(n_sims)
    for team, idx in pd.Series(range(n), index=teams.to_numpy()).groupby(level=0):
        rows = idx.to_numpy()
        # a distinct template row per world for this team
        t_for_world = tmat[pick]
        for i in rows:
            role = roles.iloc[i]
            if role not in col_of:
                continue
            r = t_for_world[:, col_of[role]]
            r = np.where(np.isfinite(r), r, rng.random(n_sims))
            order = np.lexsort((tie_break, r))
            q = np.empty(n_sims, dtype=int)
            q[order] = np.arange(n_sims)
            out[i] = srt[i][q]
    return out
