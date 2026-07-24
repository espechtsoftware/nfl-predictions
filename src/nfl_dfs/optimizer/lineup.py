"""DK NFL Classic lineup optimization (guide §9).

Constraints: 1 QB, 2-3 RB, 3-4 WR, 1-2 TE (9 total with one FLEX), 1 DST,
$50k cap, >= 2 games, <= 8 players from one team. Stacking is expressed as
constraints (QB + pass catcher, bring-back, no RB vs opposing DST) because
optimizing independent projections is the classic beginner error: DK is
winner-take-most, and you need correlated upside.

For GPPs, prefer optimizing over simulated outcomes (see simulate_lineups):
optimize each Monte Carlo draw and keep the lineups that recur — that bakes
in correlation without hand-coded rules.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pulp

log = logging.getLogger(__name__)

SALARY_CAP = 50_000
ROSTER_SIZE = 9
MAX_FROM_TEAM = 8
MIN_GAMES = 2

Player = dict[str, Any]  # id, name, pos, team, opp, game_id, salary, proj


@dataclass
class StackRules:
    qb_stack_min: int = 1        # pass catchers required from the QB's team
    bring_back_min: int = 0      # players required from the QB's opponent
    forbid_rb_vs_dst: bool = True
    forbid_two_rb_same_team: bool = True


@dataclass
class Lineup:
    players: list[Player]

    @property
    def ids(self) -> frozenset:
        return frozenset(p["id"] for p in self.players)

    @property
    def salary(self) -> int:
        return sum(p["salary"] for p in self.players)

    @property
    def proj(self) -> float:
        return float(sum(p["proj"] for p in self.players))

    def slot_order(self) -> list[Player]:
        """Players in DK upload order: QB RB RB WR WR WR TE FLEX DST."""
        pool = list(self.players)

        def take(pos: str, n: int) -> list[Player]:
            got = sorted([p for p in pool if p["pos"] == pos],
                         key=lambda p: -p["proj"])[:n]
            for g in got:
                pool.remove(g)
            return got

        ordered = take("QB", 1) + take("RB", 2) + take("WR", 3) + take("TE", 1)
        dst = take("DST", 1)
        flex = [p for p in pool if p["pos"] in ("RB", "WR", "TE")]
        return ordered + flex + dst


def optimize(
    players: list[Player],
    budget: int = SALARY_CAP,
    locks: set | None = None,
    bans: set | None = None,
    banned_lineups: list[frozenset] | None = None,
    stack: StackRules | None = None,
    objective_col: str = "proj",
    max_overlap: int = 8,
) -> Lineup | None:
    """Solve one lineup. Returns None if infeasible."""
    prob = pulp.LpProblem("dfs", pulp.LpMaximize)
    x = {p["id"]: pulp.LpVariable(f"x_{p['id']}", cat="Binary") for p in players}
    by_id = {p["id"]: p for p in players}

    prob += pulp.lpSum(x[p["id"]] * float(p[objective_col]) for p in players)
    prob += pulp.lpSum(x[p["id"]] * p["salary"] for p in players) <= budget
    prob += pulp.lpSum(x.values()) == ROSTER_SIZE

    def count(pos: str):
        return pulp.lpSum(x[p["id"]] for p in players if p["pos"] == pos)

    prob += count("QB") == 1
    prob += count("DST") == 1
    prob += count("RB") >= 2
    prob += count("RB") <= 3
    prob += count("WR") >= 3
    prob += count("WR") <= 4
    prob += count("TE") >= 1
    prob += count("TE") <= 2

    teams = sorted({p["team"] for p in players})
    for team in teams:
        prob += pulp.lpSum(x[p["id"]] for p in players if p["team"] == team) <= MAX_FROM_TEAM

    # Minimum 2 different games: for every game, players NOT in that game >= 1
    games = sorted({p.get("game_id") for p in players if p.get("game_id")})
    if len(games) >= MIN_GAMES:
        for game in games:
            prob += pulp.lpSum(
                x[p["id"]] for p in players if p.get("game_id") != game
            ) >= 1

    for pid in locks or ():
        prob += x[pid] == 1
    for pid in bans or ():
        prob += x[pid] == 0

    # Uniqueness for multi-entry: forbid previously generated lineups
    for prev in banned_lineups or ():
        prob += pulp.lpSum(x[pid] for pid in prev if pid in x) <= max_overlap

    if stack:
        _apply_stack_rules(prob, x, players, teams, stack)

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[prob.status] != "Optimal":
        return None
    chosen = [by_id[pid] for pid, var in x.items() if var.value() == 1]
    return Lineup(chosen)


def _apply_stack_rules(prob, x, players, teams, stack: StackRules) -> None:
    catchers_by_team: dict[str, list] = {}
    qbs_by_team: dict[str, list] = {}
    for p in players:
        if p["pos"] in ("WR", "TE"):
            catchers_by_team.setdefault(p["team"], []).append(p["id"])
        elif p["pos"] == "QB":
            qbs_by_team.setdefault(p["team"], []).append(p["id"])

    for team in teams:
        qbs = qbs_by_team.get(team, [])
        if not qbs:
            continue
        qb_sum = pulp.lpSum(x[i] for i in qbs)
        # If QB from team T is rostered, require >= k WR/TE from team T
        catchers = catchers_by_team.get(team, [])
        prob += pulp.lpSum(x[i] for i in catchers) >= stack.qb_stack_min * qb_sum
        # Bring-back: >= k skill players from the QB's opponent
        if stack.bring_back_min:
            opps = {p["opp"] for p in players if p["pos"] == "QB" and p["team"] == team}
            opp_skill = [
                p["id"] for p in players
                if p["team"] in opps and p["pos"] in ("RB", "WR", "TE")
            ]
            prob += pulp.lpSum(x[i] for i in opp_skill) >= stack.bring_back_min * qb_sum

    if stack.forbid_rb_vs_dst:
        dsts = [p for p in players if p["pos"] == "DST"]
        for dst in dsts:
            opposing_rbs = [
                p["id"] for p in players
                if p["pos"] == "RB" and p["team"] == dst["opp"]
            ]
            for rb_id in opposing_rbs:
                prob += x[rb_id] + x[dst["id"]] <= 1

    if stack.forbid_two_rb_same_team:
        rbs_by_team: dict[str, list] = {}
        for p in players:
            if p["pos"] == "RB":
                rbs_by_team.setdefault(p["team"], []).append(p["id"])
        for ids in rbs_by_team.values():
            if len(ids) > 1:
                prob += pulp.lpSum(x[i] for i in ids) <= 1


def optimize_many(
    players: list[Player],
    n_lineups: int,
    stack: StackRules | None = None,
    max_overlap: int = 7,
    **kwargs,
) -> list[Lineup]:
    """Generate n unique lineups; each new lineup may share at most
    max_overlap players with any previous one."""
    lineups: list[Lineup] = []
    banned: list[frozenset] = []
    for _ in range(n_lineups):
        # CBC runs as a subprocess and occasionally fails to launch under
        # load (seen in replays and tests). One retry, then return what we
        # have rather than blowing up the whole batch.
        for attempt in (1, 2):
            try:
                lu = optimize(players, stack=stack, banned_lineups=banned,
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
        banned.append(lu.ids)
    return lineups


def simulate_lineups(
    players: list[Player],
    draws: np.ndarray,
    n_keep: int = 20,
    stack: StackRules | None = None,
    n_draw_solves: int = 200,
    **kwargs,
) -> list[tuple[Lineup, int]]:
    """GPP construction from simulated outcomes: optimize a lineup for each
    of n_draw_solves Monte Carlo draws (draws[i, k] = player i's points in
    sim k, aligned with `players`), then keep the lineups that recur most.
    Correlated draws bake stacking in without hand-coded rules; explicit
    stack rules can still be layered on top."""
    counts: Counter[frozenset] = Counter()
    exemplars: dict[frozenset, Lineup] = {}
    n_sims = draws.shape[1]
    for k in range(min(n_draw_solves, n_sims)):
        sim_players = [
            {**p, "proj": float(draws[i, k])} for i, p in enumerate(players)
        ]
        lu = optimize(sim_players, stack=stack, **kwargs)
        if lu is None:
            continue
        key = lu.ids
        counts[key] += 1
        if key not in exemplars:
            # Re-express the lineup with mean projections for reporting
            by_id = {p["id"]: p for p in players}
            exemplars[key] = Lineup([by_id[i] for i in key])
    return [(exemplars[key], n) for key, n in counts.most_common(n_keep)]


# Auto-core conviction rules. A player makes the core when the scout batch
# keeps picking him despite forced diversity, AND he's a value at his
# position (or so consensus that value doesn't matter). The salary guard
# keeps the core from hoarding the cap: every non-core slot must retain at
# least a mid-tier budget, so a stud-stacked core sheds its priciest
# marginal member — the "cheap good QB over three studs" philosophy.
CORE_CONVICTION = 0.6
CORE_SUPER_CONVICTION = 0.85
CORE_MIN, CORE_MAX = 2, 7
CORE_FREE_SLOT_BUDGET = 4_500


def _auto_core(consensus: Lineup, counts, n_scout: int,
               stable_pool: list[Player]) -> list[Player]:
    def value(p: Player) -> float:
        return p["proj"] / (p["salary"] / 1000.0)

    med_value: dict[str, float] = {}
    for pos in {p["pos"] for p in stable_pool}:
        vals = sorted(value(p) for p in stable_pool if p["pos"] == pos)
        med_value[pos] = vals[len(vals) // 2]

    core = []
    for p in sorted(consensus.players, key=lambda p: -counts[p["id"]]):
        share = counts[p["id"]] / n_scout
        if share < CORE_CONVICTION:
            break  # sorted by conviction; nothing below threshold qualifies
        if value(p) >= med_value[p["pos"]] or share >= CORE_SUPER_CONVICTION:
            core.append(p)
    core = core[:CORE_MAX]

    # Budget guard: leave every free slot at least CORE_FREE_SLOT_BUDGET.
    while len(core) > CORE_MIN:
        free_slots = 9 - len(core)
        if SALARY_CAP - sum(p["salary"] for p in core) >= free_slots * CORE_FREE_SLOT_BUDGET:
            break
        core.remove(max(core, key=lambda p: p["salary"]))

    if len(core) < CORE_MIN:
        core = sorted(consensus.players, key=lambda p: -counts[p["id"]])[:CORE_MIN]
    return core


def core_and_variations(
    stable_pool: list[Player],
    upside_pool: list[Player],
    n_lineups: int,
    core_size: int | None = None,
    scout_n: int = 15,
    stack: StackRules | None = None,
    locks: set | None = None,
    bans: set | None = None,
    max_overlap: int | None = None,
) -> tuple[list[dict], list[Lineup]]:
    """Suggest a core, then build entries that vary around it.

    Scouts a diverse batch of lineups on the stable objective (median
    projection) and counts exposure. With core_size=None (default) the core
    sizes itself: consensus players (>=60% of scout lineups) who are also
    values at their position — or near-unanimous — capped so the remaining
    slots keep real budget. An explicit core_size takes the N most-consensus
    instead. Either way the core is a subset of one scout lineup, so it's
    jointly feasible by construction. Entries are then optimized on the
    upside objective with the core locked; max_overlap defaults to
    len(core) + 1 so every pair of entries differs in at least two of the
    free spots.

    Returns (core, lineups) where core entries are {"id", "conviction"}.
    Empty core/lineups if the slate is infeasible.
    """
    from collections import Counter

    scout = optimize_many(
        stable_pool, n_lineups=scout_n, stack=stack,
        locks=locks, bans=bans, max_overlap=6,
    )
    if not scout:
        return [], []
    counts = Counter(p["id"] for lu in scout for p in lu.players)
    consensus = max(scout, key=lambda lu: sum(counts[p["id"]] for p in lu.players))

    if core_size is None:
        core_players = _auto_core(consensus, counts, len(scout), stable_pool)
    else:
        core_players = sorted(
            consensus.players, key=lambda p: -counts[p["id"]]
        )[:core_size]
    core = [
        {"id": p["id"], "conviction": round(counts[p["id"]] / len(scout), 2)}
        for p in core_players
    ]
    core_ids = {c["id"] for c in core}
    lineups = optimize_many(
        upside_pool,
        n_lineups=n_lineups,
        stack=stack,
        locks=core_ids | (locks or set()),
        bans=bans,
        max_overlap=max_overlap if max_overlap is not None else len(core_ids) + 1,
    )
    return core, lineups
