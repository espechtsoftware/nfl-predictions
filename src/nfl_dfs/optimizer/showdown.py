"""DK NFL Showdown Captain Mode lineup optimization (guide §9.5).

Single-game format: 6 roster spots — 1 Captain (CPT) + 5 FLEX — drawn from
the two teams in one game. The captain scores 1.5x fantasy points and costs
1.5x his FLEX salary; the $50k cap is unchanged, and a lineup must include
at least one player from each team. Every position in the game's pool is
eligible for every spot, including K and DST (which exist on showdown
slates even though DK Classic has no kicker).

Captain choice is the whole game here: the MILP picks it jointly with the
flex spots, and two lineups with the same six players but different
captains are different entries. Classic-slate stacking rules don't apply —
in a single game every player is already "stacked" with every other — so
correlation is left to captain/flex diversity across entries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pulp

from .lineup import PUNT_MAX_SALARY, PUNT_MIN, Player

log = logging.getLogger(__name__)

SALARY_CAP = 50_000
ROSTER_SIZE = 6
FLEX_SPOTS = ROSTER_SIZE - 1
CPT_MULT = 1.5
MAX_FROM_TEAM = ROSTER_SIZE - 1  # DK: at least one player from each team


def cpt_salary(salary: int) -> int:
    """DK charges exactly 1.5x the FLEX salary for the captain slot."""
    return int(round(salary * CPT_MULT))


@dataclass
class ShowdownLineup:
    captain: Player
    flex: list[Player]

    @property
    def players(self) -> list[Player]:
        return [self.captain] + self.flex

    @property
    def ids(self) -> frozenset:
        return frozenset(p["id"] for p in self.players)

    @property
    def key(self) -> tuple:
        """Lineup identity: same six players with a different captain is a
        different DK entry."""
        return (self.captain["id"], self.ids)

    @property
    def salary(self) -> int:
        return cpt_salary(self.captain["salary"]) + sum(p["salary"] for p in self.flex)

    @property
    def proj(self) -> float:
        return float(CPT_MULT * self.captain["proj"]
                     + sum(p["proj"] for p in self.flex))

    def slot_order(self) -> list[Player]:
        """Players in DK upload order: CPT then FLEX by projection."""
        return [self.captain] + sorted(self.flex, key=lambda p: -p["proj"])


def optimize_showdown(
    players: list[Player],
    budget: int = SALARY_CAP,
    locks: set | None = None,
    bans: set | None = None,
    captain_lock=None,
    banned_lineups: list[tuple] | None = None,
    max_overlap: int = FLEX_SPOTS,
    objective_col: str = "proj",
    punt_max_salary: int | None = PUNT_MAX_SALARY,
    punt_min: int = PUNT_MIN,
) -> ShowdownLineup | None:
    """Solve one Captain Mode lineup. Returns None if infeasible.

    locks/bans apply to the six-man roster regardless of slot;
    captain_lock forces a specific player into the CPT spot. banned_lineups
    takes ShowdownLineup.key tuples: a new lineup must differ from each by
    its captain or by more than ROSTER_SIZE - max_overlap - 1 players — the
    default (5) only forbids exact repeats, captain included.
    """
    prob = pulp.LpProblem("dfs_showdown", pulp.LpMaximize)
    c = {p["id"]: pulp.LpVariable(f"c_{p['id']}", cat="Binary") for p in players}
    f = {p["id"]: pulp.LpVariable(f"f_{p['id']}", cat="Binary") for p in players}
    by_id = {p["id"]: p for p in players}

    prob += pulp.lpSum(
        c[p["id"]] * CPT_MULT * float(p[objective_col])
        + f[p["id"]] * float(p[objective_col])
        for p in players
    )
    prob += pulp.lpSum(
        c[p["id"]] * cpt_salary(p["salary"]) + f[p["id"]] * p["salary"]
        for p in players
    ) <= budget
    prob += pulp.lpSum(c.values()) == 1
    prob += pulp.lpSum(f.values()) == FLEX_SPOTS
    for p in players:
        prob += c[p["id"]] + f[p["id"]] <= 1

    # At least one player from each team (equivalently, <= 5 from any one)
    for team in sorted({p["team"] for p in players}):
        prob += pulp.lpSum(
            c[p["id"]] + f[p["id"]] for p in players if p["team"] == team
        ) <= MAX_FROM_TEAM

    # Tournament punt: at least one sub-$4k roster spot (FLEX pricing)
    if punt_min and punt_max_salary:
        punts = [p["id"] for p in players if p["salary"] <= punt_max_salary]
        if punts:
            prob += pulp.lpSum(c[pid] + f[pid] for pid in punts) >= punt_min

    for pid in locks or ():
        prob += c[pid] + f[pid] == 1
    for pid in bans or ():
        prob += c[pid] + f[pid] == 0
    if captain_lock is not None:
        prob += c[captain_lock] == 1

    # Uniqueness: shared-player count, +1 if the previous captain is
    # re-captained, must stay <= max_overlap + 1.
    for prev_cpt, prev_ids in banned_lineups or ():
        prob += (
            pulp.lpSum(c[pid] + f[pid] for pid in prev_ids if pid in c)
            + (c[prev_cpt] if prev_cpt in c else 0)
        ) <= max_overlap + 1

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[prob.status] != "Optimal":
        return None
    captain = next(by_id[pid] for pid, var in c.items() if var.value() == 1)
    flex = [by_id[pid] for pid, var in f.items() if var.value() == 1]
    return ShowdownLineup(captain, flex)


def optimize_many_showdown(
    players: list[Player],
    n_lineups: int,
    max_overlap: int = FLEX_SPOTS,
    **kwargs,
) -> list[ShowdownLineup]:
    """Generate n unique Captain Mode lineups. With the default max_overlap
    the same six players may recur under a different captain — in a
    six-man, two-team pool that's a legitimately distinct entry; lower it
    to force player-set diversity too."""
    lineups: list[ShowdownLineup] = []
    banned: list[tuple] = []
    for _ in range(n_lineups):
        # Same CBC-launch flakiness handling as the classic optimizer.
        for attempt in (1, 2):
            try:
                lu = optimize_showdown(players, banned_lineups=banned,
                                       max_overlap=max_overlap, **kwargs)
                break
            except pulp.PulpSolverError as exc:
                log.warning("CBC solve failed (attempt %d): %s", attempt, exc)
                lu = None
        else:
            log.warning("CBC unavailable; returning %d lineups", len(lineups))
            return lineups
        if lu is None:
            log.warning("Pool exhausted after %d lineups", len(lineups))
            break
        lineups.append(lu)
        banned.append(lu.key)
    return lineups
