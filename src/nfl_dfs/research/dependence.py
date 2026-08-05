"""Role-weighted variogram dependence suite (plan §4.3; September
research designs instrument #0, 2026-08-05).

WHY: energy scores are nearly insensitive to miscorrelation (Scheuerer
& Hamill 2015), and GPP tails are DECIDED by joint behavior — a QB-WR1
double boom, a shootout lifting both QBs, WR1/WR2 usage competition
(negative), RB grinding out a game his own DST closes down. The
variogram score restricted to those registered role pairs is the sharp
instrument: for each pair (i, j) compare the sim's expected
|D_i - D_j|^p against the realized |x_i - x_j|^p; positively-dependent
players have SMALLER expected differences than independence implies,
so a sim with the right copula scores strictly lower (better) on the
same marginals. Upper-tail co-occurrence at registered quantiles is
reported alongside because variograms alone can miss tail-only
dependence.

This is the mechanism gate for ANY dependence change (TD ledger,
Schaake shuffle, CE worlds): role-pair scores must improve held-out
while marginals must not degrade. Pure numpy; offline-testable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np

log = logging.getLogger(__name__)

# Registered role pairs and weights (September designs instrument #0):
# weights reflect how often the pair decides a Milly tail, not
# statistical taste. Registered BEFORE experiments so arms can't shop.
DEFAULT_ROLE_WEIGHTS: dict[str, float] = {
    "qb_wr1_same_team": 3.0,
    "qb_opp_qb": 2.0,
    "wr1_wr2_same_team": 2.0,
    "rb_own_dst": 1.0,
}

# Registered quantile levels for upper-tail co-occurrence.
DEFAULT_TAIL_QUANTILES: tuple[float, ...] = (0.85, 0.95)

_ROLE_ALIASES = {"RB": "RB1"}


@dataclass
class DependenceReport:
    """Scores for one draws matrix vs one realized slate (or season).

    variogram: per pair-type score, LOWER IS BETTER.
    weighted_total: role-weighted sum — the single gate number.
    tail: pair_type -> quantile -> {"sim", "realized", "gap"} joint
        upper-tail exceedance rates (gap lower is better).
    n_pairs: pair instances found per type (vacuity check: a zero here
        means the roles/teams inputs never produced the pair).
    """

    variogram: dict[str, float] = field(default_factory=dict)
    weighted_total: float = float("nan")
    n_pairs: dict[str, int] = field(default_factory=dict)
    tail: dict[str, dict[float, dict[str, float]]] = field(
        default_factory=dict)
    tail_gap_total: float = float("nan")


def role_pair_indices(
    roles: Sequence[str],
    teams: Sequence[str],
    games: Sequence[str],
) -> dict[str, list[tuple[int, int]]]:
    """Registered pair instances from per-player role/team/game labels.

    Roles use the role model's labels (QB, WR1, WR2, RB1, DST; bare RB
    accepted as RB1). Players outside registered roles are ignored.
    Duplicate (game, team, role) rows keep the first and warn — a
    duplicate usually means the caller passed a season-level frame
    without factorizing games.
    """
    slots: dict[tuple[str, str], dict[str, int]] = {}
    game_teams: dict[str, list[str]] = {}
    for ix, (role, team, game) in enumerate(zip(roles, teams, games)):
        role = _ROLE_ALIASES.get(str(role), str(role))
        key = (str(game), str(team))
        team_slots = slots.setdefault(key, {})
        if role in team_slots:
            log.warning("duplicate role %s for %s; keeping first", role, key)
            continue
        team_slots[role] = ix
        teams_in_game = game_teams.setdefault(str(game), [])
        if str(team) not in teams_in_game:
            teams_in_game.append(str(team))

    pairs: dict[str, list[tuple[int, int]]] = {
        k: [] for k in DEFAULT_ROLE_WEIGHTS}
    for (game, team), team_slots in slots.items():
        if "QB" in team_slots and "WR1" in team_slots:
            pairs["qb_wr1_same_team"].append(
                (team_slots["QB"], team_slots["WR1"]))
        if "WR1" in team_slots and "WR2" in team_slots:
            pairs["wr1_wr2_same_team"].append(
                (team_slots["WR1"], team_slots["WR2"]))
        if "RB1" in team_slots and "DST" in team_slots:
            pairs["rb_own_dst"].append(
                (team_slots["RB1"], team_slots["DST"]))
    for game, teams_in_game in game_teams.items():
        if len(teams_in_game) == 2:
            a = slots.get((game, teams_in_game[0]), {})
            b = slots.get((game, teams_in_game[1]), {})
            if "QB" in a and "QB" in b:
                pairs["qb_opp_qb"].append((a["QB"], b["QB"]))
        elif len(teams_in_game) > 2:
            log.warning("game %s has %d teams; skipping opp-QB pair",
                        game, len(teams_in_game))
    return pairs


def variogram_score(
    draws: np.ndarray,
    actuals: np.ndarray,
    pairs: Iterable[tuple[int, int]],
    p: float = 0.5,
) -> float:
    """Mean squared variogram error over pair instances (lower better):
    mean_(i,j) ( |x_i - x_j|^p  -  E_sims |D_i - D_j|^p )^2.

    p=0.5 is the Scheuerer & Hamill default — robust to the heavy right
    tails DK points have.
    """
    pairs = list(pairs)
    if not pairs:
        return float("nan")
    i = np.array([a for a, _ in pairs])
    j = np.array([b for _, b in pairs])
    sim_gamma = np.abs(draws[i] - draws[j]) ** p       # (pairs, sims)
    obs_gamma = np.abs(actuals[i] - actuals[j]) ** p   # (pairs,)
    return float(np.mean((obs_gamma - sim_gamma.mean(axis=1)) ** 2))


def tail_cooccurrence(
    draws: np.ndarray,
    actuals: np.ndarray,
    pairs: Iterable[tuple[int, int]],
    q: float,
) -> dict[str, float]:
    """Joint upper-tail exceedance at each player's OWN sim q-quantile.

    Thresholds come from the sim's marginals, so the statistic isolates
    the JOINT tail given the sim's own margins: an independent sim
    lands near (1-q)^2 regardless of marginal quality. Returns the sim
    co-exceedance rate, the realized rate across pair instances, and
    their absolute gap (lower better).
    """
    pairs = list(pairs)
    if not pairs:
        return {"sim": float("nan"), "realized": float("nan"),
                "gap": float("nan")}
    i = np.array([a for a, _ in pairs])
    j = np.array([b for _, b in pairs])
    thresh = np.quantile(draws, q, axis=1)             # (players,)
    joint = ((draws[i] >= thresh[i, None])
             & (draws[j] >= thresh[j, None]))          # (pairs, sims)
    sim_rate = float(joint.mean())
    realized = float(np.mean((actuals[i] >= thresh[i])
                             & (actuals[j] >= thresh[j])))
    return {"sim": sim_rate, "realized": realized,
            "gap": abs(realized - sim_rate)}


def dependence_report(
    draws: np.ndarray,
    actuals: np.ndarray,
    roles: Sequence[str],
    teams: Sequence[str],
    games: Sequence[str],
    *,
    p: float = 0.5,
    weights: dict[str, float] | None = None,
    quantiles: Sequence[float] = DEFAULT_TAIL_QUANTILES,
) -> DependenceReport:
    """Full instrument-#0 scorecard for one sim against realized joints.

    draws: (n_players, n_sims); actuals: (n_players,); roles/teams/
    games: per-player labels aligned to the draws rows. Compare two
    sims by running this twice on the SAME actuals and labels — the
    better copula has the lower weighted_total and tail_gap_total.
    """
    draws = np.asarray(draws, dtype=float)
    actuals = np.asarray(actuals, dtype=float)
    if draws.ndim != 2 or draws.shape[0] != actuals.shape[0]:
        raise ValueError(
            f"draws {draws.shape} misaligned with actuals {actuals.shape}")
    w = dict(DEFAULT_ROLE_WEIGHTS if weights is None else weights)
    pairs = role_pair_indices(roles, teams, games)

    rep = DependenceReport()
    total = 0.0
    tail_total = 0.0
    wsum = 0.0
    for name, plist in pairs.items():
        rep.n_pairs[name] = len(plist)
        score = variogram_score(draws, actuals, plist, p=p)
        rep.variogram[name] = score
        rep.tail[name] = {}
        for q in quantiles:
            rep.tail[name][q] = tail_cooccurrence(draws, actuals, plist, q)
        if plist and name in w:
            total += w[name] * score
            tail_total += w[name] * float(np.mean(
                [rep.tail[name][q]["gap"] for q in quantiles]))
            wsum += w[name]
    rep.weighted_total = total / wsum if wsum else float("nan")
    rep.tail_gap_total = tail_total / wsum if wsum else float("nan")
    return rep
