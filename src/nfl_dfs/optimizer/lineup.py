"""DK NFL Classic lineup optimization (guide §9).

Universal constraints are the DraftKings legality layer: roster slots, the
$50k cap, and athletes from at least two teams. Tournament strategy such as
multi-game diversity, stacking, salary spend and correlation exclusions is
supplied through an explicit construction preset.

For GPPs, prefer optimizing over simulated outcomes (see simulate_lineups):
optimize each Monte Carlo draw and keep the lineups that recur — that bakes
in correlation without hand-coded rules.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable, Mapping

import numpy as np
import pulp

log = logging.getLogger(__name__)

SALARY_CAP = 50_000
# Tournament construction constants (named presets decide whether to use them): a
# sub-$4k ceiling punt appeared in 94% of 2025 Milly Maker winners.
PUNT_MAX_SALARY = 4_000
# PUNT_MIN default 0 ADOPTED 2026-08-05 (Addendum 77): the hard punt
# MANDATE deletion scored 26/107 vs 25 with better mean-best and the
# program-max 271.1 — the p90 ceiling VALUATION of punt-priced players
# (replay.build_slates / live mirror) is what carries the punt edge,
# and it stays. PUNT_MIN=1 env restores the mandate.
PUNT_MIN = 0
LEVERAGE_PENALTY = 25.0  # pts deducted x naive-ownership weight (chalk fade)
ROSTER_SIZE = 9
MAX_FROM_TEAM = 8
# Bare/shared legality construction has no multi-game diversity mandate.
# The incumbent named preset opts into two games explicitly.
MIN_GAMES = 1
INCUMBENT_MIN_GAMES = 2

Player = dict[str, Any]  # id, name, pos, team, opp, game_id, salary, proj


@dataclass(frozen=True)
class StackRules:
    """Optional strategic correlation rules; bare construction is neutral."""

    qb_stack_min: int = 0        # pass catchers required from the QB's team
    bring_back_min: int = 0      # players required from the QB's opponent
    forbid_rb_vs_dst: bool = False
    forbid_two_rb_same_team: bool = False
    # Research-only exact/exception bounds.  ``None`` and ``False`` preserve
    # the production formulation byte-for-byte; the constraint-lattice shadow
    # opts in explicitly and never changes the money policy's StackRules.
    qb_stack_max: int | None = None
    bring_back_max: int | None = None
    require_rb_vs_dst: bool = False
    require_two_rb_same_team: bool = False


@dataclass
class Lineup:
    players: list[Player]
    tag: str = ""  # which generator produced it (lev/boom/game); analysis only

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
        """Players in DK upload order: QB RB RB WR WR WR TE FLEX DST.

        Slot labels don't affect DK scoring (all 9 spots count the same),
        so which specific player lands in FLEX is free to optimize for
        late-swap flexibility instead: when every player carries a
        `kickoff` time, the position with a surplus over its required
        minimum sends its LATEST-kickoff player to FLEX (the only slot
        that accepts any of RB/WR/TE) rather than its lowest-projected
        one. Missing kickoff data (the common case — most callers don't
        have it) falls back to the original proj-based assignment."""
        pool = list(self.players)
        has_kickoffs = bool(pool) and all(p.get("kickoff") for p in pool)

        def take(pos: str, n: int, flex_eligible: bool = False) -> list[Player]:
            cands = [p for p in pool if p["pos"] == pos]
            if flex_eligible and has_kickoffs and len(cands) > n:
                # Earliest n lock into the hard slot; the latest-kickoff
                # surplus player is left behind for FLEX.
                got = sorted(cands, key=lambda p: p["kickoff"])[:n]
            else:
                got = sorted(cands, key=lambda p: -p["proj"])[:n]
            for g in got:
                pool.remove(g)
            return got

        ordered = (
            take("QB", 1)
            + take("RB", 2, flex_eligible=True)
            + take("WR", 3, flex_eligible=True)
            + take("TE", 1, flex_eligible=True)
        )
        dst = take("DST", 1)
        flex = [p for p in pool if p["pos"] in ("RB", "WR", "TE")]
        return ordered + flex + dst


def add_classic_lineup_constraints(
    prob: pulp.LpProblem,
    x: Mapping[object, pulp.LpVariable],
    players: list[Player],
    *,
    budget: int = SALARY_CAP,
    locks: set | None = None,
    bans: set | None = None,
    banned_lineups: list[frozenset] | None = None,
    stack: StackRules | None = None,
    max_overlap: int = 8,
    punt_max_salary: int | None = None,
    punt_min: int = 0,
    game_lock: tuple[str, int] | None = None,
    min_salary: int | None = None,
    max_salary: int | None = None,
    max_per_game: int | None = None,
    min_games: int | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    """Add the shared DraftKings Classic feasibility domain to ``prob``.

    This function deliberately adds constraints only: callers own the
    objective, solver configuration, and result auditing.  ``optimize`` uses
    it with the same arguments and constraint order as the historical inline
    formulation. With omitted strategy arguments and ``env=None`` this is
    legality-only. Production and replay callers resolve a named construction
    preset and pass its effective values explicitly.
    """
    prob += pulp.lpSum(x[p["id"]] * p["salary"] for p in players) <= budget
    # Strategy environment is caller-supplied data, never ambient process
    # state. Omission therefore cannot activate a house rule.
    _env = {} if env is None else env

    _min_sal = (min_salary if min_salary is not None
                else int(_env.get("MIN_LINEUP_SALARY", "0") or 0))
    if _min_sal:
        prob += pulp.lpSum(x[p["id"]] * p["salary"] for p in players) >= _min_sal
    if max_salary is not None and max_salary < budget:
        prob += pulp.lpSum(x[p["id"]] * p["salary"] for p in players) <= max_salary
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

    # Multi-game diversity is strategy, not DK legality. The incumbent named
    # preset supplies 2; the universal layer resolves to 1 (disabled).
    _min_games = (min_games if min_games is not None
                  else int(_env.get("MIN_GAMES", "1") or 1))
    if _min_games < 1:
        raise ValueError("minimum games must be at least one")
    games = sorted({p.get("game_id") for p in players if p.get("game_id")})
    if _min_games == 1:
        # DK legality itself does not require game metadata or a multi-game
        # roster.  Missing game IDs therefore remain legal in the neutral
        # construction domain.
        pass
    elif _min_games > len(games):
        # An explicitly requested strategy dose must never disappear merely
        # because the slate cannot satisfy it.
        prob += pulp.lpSum([]) >= 1
    elif _min_games == 2:
        # Preserve the incumbent preset's historical LP formulation and
        # constraint order exactly.  The generalized formulation below is
        # necessary only for experimental doses above two games; using it for
        # the incumbent can change CBC tie resolution despite defining the
        # same feasible roster set.
        for game in games:
            prob += pulp.lpSum(
                x[p["id"]] for p in players if p.get("game_id") != game
            ) >= 1
    elif _min_games > 2:
        game_used = {
            game: pulp.LpVariable(f"game_used_{index}", cat="Binary")
            for index, game in enumerate(games)
        }
        for game, used in game_used.items():
            ids = [p["id"] for p in players if p.get("game_id") == game]
            prob += pulp.lpSum(x[pid] for pid in ids) >= used
            prob += pulp.lpSum(x[pid] for pid in ids) <= ROSTER_SIZE * used
        prob += pulp.lpSum(game_used.values()) >= _min_games

    # Tournament punt slot: winners rostered a sub-$4k player who scored
    # 15+ in 94% of 2025 Milly Makers (reports/2025-milly-winners.csv).
    if punt_min and punt_max_salary:
        if _env.get("PUNT_STRICT") and any(
                "punt_elig" in p for p in players):
            punts = [p["id"] for p in players if p.get("punt_elig")]
        else:
            punts = [p["id"] for p in players
                     if p["salary"] <= punt_max_salary]
        if punts:
            prob += pulp.lpSum(x[pid] for pid in punts) >= punt_min

    # A/B lever (env VALUE2_MIN, off by default): salary-barbell second
    # tier — 84% of first-place Milly lineups carried >=2 skill players
    # under $5,300 (44% carried three; 4for4 via 2026-08-03 triage). The
    # sub-$4k punt rule mandates ONE extreme value; this requires N
    # players under VALUE2_MAX (default 5300), punt included.
    v2_min = int(_env.get("VALUE2_MIN", "0"))
    if v2_min:
        v2_max = int(_env.get("VALUE2_MAX", "5300"))
        cheap2 = [p["id"] for p in players
                  if p["salary"] <= v2_max and p["pos"] != "DST"]
        if len(cheap2) >= v2_min:
            prob += pulp.lpSum(x[pid] for pid in cheap2) >= v2_min

    # A/B lever (env OWN_BARBELL, off by default; review #4 F4): winners
    # reach their contrarian ownership-sum via a BARBELL (mega-chalk studs
    # + near-zero-owned punts), not a smooth fade. Linear proxy for an
    # ownership-variance floor: require >= NLOW skill players at or below
    # LOW ownership AND >= NHIGH at or above HIGH. Needs own_est on the
    # pool rows (replay attaches it); silently inert otherwise.
    if _env.get("OWN_BARBELL") and any(
            p.get("own_est") is not None for p in players):
        b_low = float(_env.get("OWN_BARBELL_LOW", "0.05"))
        b_high = float(_env.get("OWN_BARBELL_HIGH", "0.20"))
        n_low = int(_env.get("OWN_BARBELL_NLOW", "3"))
        n_high = int(_env.get("OWN_BARBELL_NHIGH", "2"))
        lows = [p["id"] for p in players if p["pos"] != "DST"
                and (p.get("own_est") or 0) <= b_low]
        highs = [p["id"] for p in players if p["pos"] != "DST"
                 and (p.get("own_est") or 0) >= b_high]
        if len(lows) >= n_low and len(highs) >= n_high:
            prob += pulp.lpSum(x[pid] for pid in lows) >= n_low
            prob += pulp.lpSum(x[pid] for pid in highs) >= n_high

    # A/B lever (env MAX_PER_GAME, off by default): cap same-game players.
    # 28 fully-mapped Milly winners average 2.96 from their most-loaded
    # game (22/28 used only 2-3) across 5.3 distinct games; our entries
    # average 4.6 from one game — the concentrated-game folklore the
    # 5-stack generators encode is contradicted by the winners (2026-08-03).
    max_pg = (max_per_game if max_per_game is not None
              else int(_env.get("MAX_PER_GAME", "0")))
    if max_pg:
        by_game: dict = {}
        for p in players:
            by_game.setdefault(p.get("game_id"), []).append(p["id"])
        for gid, ids in by_game.items():
            if gid is not None and len(ids) > max_pg:
                prob += pulp.lpSum(x[pid] for pid in ids) <= max_pg

    # A/B lever (env MIN_LOWOWN, off by default): winner ownership shape
    # — real Milly winners carry ~2 sub-5%-owned players (Addendum 38,
    # stable 2019-2024). Requires callers to stamp a boolean `low_own`
    # on pool dicts (replay build_slates does); silently inert otherwise.
    min_lowown = int(_env.get("MIN_LOWOWN", "0"))
    if min_lowown:
        lows = [p["id"] for p in players if p.get("low_own")]
        if lows:
            prob += pulp.lpSum(x[pid] for pid in lows) >= min(
                min_lowown, len(lows))

    if game_lock:
        gid, n_from_game = game_lock
        in_game = [p["id"] for p in players if p.get("game_id") == gid]
        if len(in_game) >= n_from_game:
            prob += pulp.lpSum(x[pid] for pid in in_game) >= n_from_game

    for pid in locks or ():
        prob += x[pid] == 1
    for pid in bans or ():
        prob += x[pid] == 0

    # Uniqueness for multi-entry: forbid previously generated lineups
    for prev in banned_lineups or ():
        prob += pulp.lpSum(x[pid] for pid in prev if pid in x) <= max_overlap

    if stack:
        _apply_stack_rules(prob, x, players, teams, stack)


def optimize(
    players: list[Player],
    budget: int = SALARY_CAP,
    locks: set | None = None,
    bans: set | None = None,
    banned_lineups: list[frozenset] | None = None,
    stack: StackRules | None = None,
    objective_col: str = "proj",
    max_overlap: int = 8,
    punt_max_salary: int | None = None,
    punt_min: int = 0,
    game_lock: tuple[str, int] | None = None,
    min_salary: int | None = None,
    max_salary: int | None = None,
    max_per_game: int | None = None,
    min_games: int | None = None,
    env: Mapping[str, str] | None = None,
    objective_floor_col: str | None = None,
    objective_floor: float | None = None,
    interaction_objective: Mapping[tuple[object, ...], float] | None = None,
    interaction_floor_weights: Mapping[tuple[object, ...], float] | None = None,
    interaction_floor: float | None = None,
) -> Lineup | None:
    """Solve one lineup. Returns None if infeasible.
    game_lock=(game_id, n) forces >= n players from that game — the
    concentrated-game-stack construction (issue #6): Milly winners take
    50-80% of their points from one game."""
    prob = pulp.LpProblem("dfs", pulp.LpMaximize)
    x = {p["id"]: pulp.LpVariable(f"x_{p['id']}", cat="Binary") for p in players}
    by_id = {p["id"]: p for p in players}

    interaction_maps = [
        mapping for mapping in (
            interaction_objective, interaction_floor_weights,
        ) if mapping is not None
    ]
    canonical_interactions: dict[tuple[object, ...], float] = {}
    for mapping in interaction_maps:
        for raw_tuple, raw_weight in mapping.items():
            key = tuple(sorted(tuple(raw_tuple), key=str))
            weight = float(raw_weight)
            if len(key) not in {2, 3} or len(set(key)) != len(key) or \
                    any(player_id not in x for player_id in key):
                raise ValueError("interaction tuple must contain 2-3 pool players")
            if not np.isfinite(weight) or weight < 0.0:
                raise ValueError("interaction weights must be finite/nonnegative")
            if key in canonical_interactions and \
                    canonical_interactions[key] != weight:
                raise ValueError("interaction tuple has conflicting weights")
            canonical_interactions[key] = weight
    y: dict[tuple[object, ...], pulp.LpVariable] = {}
    for index, key in enumerate(sorted(canonical_interactions, key=lambda t: tuple(
            str(value) for value in t))):
        # This product variable is exactly integral whenever the roster x
        # variables are binary: all members selected forces y=1; any missing
        # member forces y=0. Keeping y continuous therefore preserves the
        # feasible set/objective exactly while avoiding thousands of redundant
        # branch-and-bound integers in interaction-heavy research solves.
        variable = pulp.LpVariable(
            f"interaction_{index}", lowBound=0.0, upBound=1.0,
            cat="Continuous",
        )
        y[key] = variable
        for player_id in key:
            prob += variable <= x[player_id]
        prob += variable >= pulp.lpSum(x[player_id] for player_id in key) - (
            len(key) - 1
        )

    def interaction_expression(weights: Mapping[tuple[object, ...], float]):
        normalized = dict(sorted((
            (tuple(sorted(tuple(key), key=str)), float(value))
            for key, value in weights.items()
        ), key=lambda row: tuple(str(value) for value in row[0])))
        return pulp.lpSum(y[key] * weight for key, weight in normalized.items())

    if interaction_objective is None:
        prob += pulp.lpSum(
            x[p["id"]] * float(p[objective_col]) for p in players
        )
    else:
        prob += interaction_expression(interaction_objective)
    if (objective_floor_col is None) != (objective_floor is None):
        raise ValueError(
            "objective floor column and value must be provided together"
        )
    if objective_floor_col is not None:
        floor = float(objective_floor)
        if not np.isfinite(floor):
            raise ValueError("objective floor must be finite")
        prob += pulp.lpSum(
            x[p["id"]] * float(p[objective_floor_col]) for p in players
        ) >= floor
    if (interaction_floor_weights is None) != (interaction_floor is None):
        raise ValueError(
            "interaction floor weights and value must be provided together"
        )
    if interaction_floor_weights is not None:
        floor = float(interaction_floor)
        if not np.isfinite(floor):
            raise ValueError("interaction floor must be finite")
        prob += interaction_expression(interaction_floor_weights) >= floor
    add_classic_lineup_constraints(
        prob,
        x,
        players,
        budget=budget,
        locks=locks,
        bans=bans,
        banned_lineups=banned_lineups,
        stack=stack,
        max_overlap=max_overlap,
        punt_max_salary=punt_max_salary,
        punt_min=punt_min,
        game_lock=game_lock,
        min_salary=min_salary,
        max_salary=max_salary,
        max_per_game=max_per_game,
        min_games=min_games,
        env=env,
    )

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[prob.status] != "Optimal":
        return None
    chosen = [by_id[pid] for pid, var in x.items() if var.value() == 1]
    return Lineup(chosen)


def _apply_stack_rules(prob, x, players, teams, stack: StackRules) -> None:
    for label, value in (
        ("qb_stack_min", stack.qb_stack_min),
        ("bring_back_min", stack.bring_back_min),
    ):
        if int(value) != value or value < 0:
            raise ValueError(f"{label} must be one nonnegative integer")
    for label, value, minimum in (
        ("qb_stack_max", stack.qb_stack_max, stack.qb_stack_min),
        ("bring_back_max", stack.bring_back_max, stack.bring_back_min),
    ):
        if value is not None and (
            int(value) != value or value < minimum
        ):
            raise ValueError(f"{label} must be an integer at least its minimum")
    if stack.forbid_rb_vs_dst and stack.require_rb_vs_dst:
        raise ValueError("RB-versus-DST cannot be both forbidden and required")
    if stack.forbid_two_rb_same_team and stack.require_two_rb_same_team:
        raise ValueError("same-team RBs cannot be both forbidden and required")

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
        if stack.qb_stack_max is not None:
            prob += pulp.lpSum(x[i] for i in catchers) <= (
                stack.qb_stack_max * qb_sum
                + len(catchers) * (1 - qb_sum)
            )
        # Bring-back: >= k skill players from the QB's opponent
        if stack.bring_back_min or stack.bring_back_max is not None:
            opps = {p["opp"] for p in players if p["pos"] == "QB" and p["team"] == team}
            opp_skill = [
                p["id"] for p in players
                if p["team"] in opps and p["pos"] in ("RB", "WR", "TE")
            ]
            prob += pulp.lpSum(x[i] for i in opp_skill) >= (
                stack.bring_back_min * qb_sum
            )
            if stack.bring_back_max is not None:
                prob += pulp.lpSum(x[i] for i in opp_skill) <= (
                    stack.bring_back_max * qb_sum
                    + len(opp_skill) * (1 - qb_sum)
                )

    if stack.forbid_rb_vs_dst:
        dsts = [p for p in players if p["pos"] == "DST"]
        for dst in dsts:
            opposing_rbs = [
                p["id"] for p in players
                if p["pos"] == "RB" and p["team"] == dst["opp"]
            ]
            for rb_id in opposing_rbs:
                prob += x[rb_id] + x[dst["id"]] <= 1

    if stack.require_rb_vs_dst:
        dsts = [p for p in players if p["pos"] == "DST"]
        for dst in dsts:
            opposing_rbs = [
                p["id"] for p in players
                if p["pos"] == "RB" and p["team"] == dst["opp"]
            ]
            prob += pulp.lpSum(x[rb_id] for rb_id in opposing_rbs) >= x[
                dst["id"]
            ]

    if stack.forbid_two_rb_same_team:
        rbs_by_team: dict[str, list] = {}
        for p in players:
            if p["pos"] == "RB":
                rbs_by_team.setdefault(p["team"], []).append(p["id"])
        for ids in rbs_by_team.values():
            if len(ids) > 1:
                prob += pulp.lpSum(x[i] for i in ids) <= 1

    if stack.require_two_rb_same_team:
        rbs_by_team: dict[str, list] = {}
        for p in players:
            if p["pos"] == "RB":
                rbs_by_team.setdefault(p["team"], []).append(p["id"])
        witnesses = []
        for index, (team, ids) in enumerate(sorted(rbs_by_team.items())):
            if len(ids) < 2:
                continue
            witness = pulp.LpVariable(
                f"required_same_team_rb_{index}_{team}", cat="Binary"
            )
            witnesses.append(witness)
            prob += pulp.lpSum(x[i] for i in ids) >= 2 * witness
        prob += pulp.lpSum(witnesses) >= 1


def optimize_many(
    players: list[Player],
    n_lineups: int,
    stack: StackRules | None = None,
    max_overlap: int | None = None,
    punt_max_salary: int | None = PUNT_MAX_SALARY,
    punt_min: int = PUNT_MIN,
    env: Mapping[str, str] | None = None,
    telemetry: dict[str, int] | None = None,
    attempt_callback: Callable[[dict[str, object]], None] | None = None,
    **kwargs,
) -> list[Lineup]:
    """Generate n unique lineups; each new lineup may share at most
    max_overlap players with any previous one."""
    # Assumption-validation lever (2026-08-01): PUNT_MIN env overrides the
    # mandatory-punt rule so its causal value can be measured (the rule was
    # adopted from "94% of Milly winners had a punt" -- correlational).
    _env = {} if env is None else env
    effective_max_overlap = (
        int(_env.get("MAX_OVERLAP", "8"))
        if max_overlap is None else int(max_overlap)
    )

    punt_min = int(_env.get("PUNT_MIN", punt_min))
    # PUNT_MAX (2026-08-03): the $4k threshold was inherited from the
    # 2025 winner study (punts cluster $2.9-3.9k) and never dose-tested.
    if "PUNT_MAX" in _env:
        punt_max_salary = (
            int(_env["PUNT_MAX"]) if _env["PUNT_MAX"] else None
        )
    lineups: list[Lineup] = []
    banned: list[frozenset] = []
    stats = {
        "requested": int(n_lineups),
        "solve_attempts": 0,
        "solver_errors": 0,
        "infeasible": 0,
        "successful": 0,
    }

    def _publish() -> None:
        stats["returned"] = len(lineups)
        if telemetry is not None:
            telemetry.clear()
            telemetry.update(stats)

    for requested_ordinal in range(n_lineups):
        # CBC runs as a subprocess and occasionally fails to launch under
        # load (seen in replays and tests). One retry, then return what we
        # have rather than blowing up the whole batch.
        for attempt in (1, 2):
            stats["solve_attempts"] += 1
            solve_started = perf_counter()
            try:
                lu = optimize(players, stack=stack, banned_lineups=banned,
                              max_overlap=effective_max_overlap,
                              punt_max_salary=punt_max_salary,
                              punt_min=punt_min, env=_env, **kwargs)
                solve_duration = perf_counter() - solve_started
                break
            except pulp.PulpSolverError as exc:
                solve_duration = perf_counter() - solve_started
                stats["solver_errors"] += 1
                if attempt_callback is not None:
                    attempt_callback({
                        "requested_ordinal": requested_ordinal,
                        "retry_ordinal": attempt - 1,
                        "duration_seconds": solve_duration,
                        "status": "error",
                        "roster_ids": None,
                    })
                log.warning("CBC solve failed (attempt %d): %s", attempt, exc)
                lu = None
        else:
            log.warning("CBC unavailable; returning %d lineups", len(lineups))
            _publish()
            return lineups
        if lu is None:
            stats["infeasible"] += 1
            if attempt_callback is not None:
                attempt_callback({
                    "requested_ordinal": requested_ordinal,
                    "retry_ordinal": attempt - 1,
                    "duration_seconds": solve_duration,
                    "status": "infeasible",
                    "roster_ids": None,
                })
            log.warning("Pool exhausted after %d lineups", len(lineups))
            break
        if attempt_callback is not None:
            attempt_callback({
                "requested_ordinal": requested_ordinal,
                "retry_ordinal": attempt - 1,
                "duration_seconds": solve_duration,
                "status": "new",
                "roster_ids": tuple(lu.ids),
            })
        lineups.append(lu)
        stats["successful"] += 1
        banned.append(lu.ids)
    _publish()
    return lineups


def select_tail_entries(
    cand_totals: np.ndarray, n_entries: int, line: float,
    env: Mapping[str, str] | None = None,
    trace_capture: Callable[[Mapping[str, Any]], None] | None = None,
) -> list[int]:
    """Pick the n_entries candidates that maximize P(best-of-N >= line)
    against correlated draws. cand_totals[c, k] = candidate c's total in
    sim k. Greedy max-coverage over the sims each candidate clears the
    line in (submodular, so greedy is within 1-1/e of optimal): two
    entries that boom in the SAME sims are redundant no matter how good
    each looks alone. Slots left after coverage saturates go to the
    highest remaining P(>= line), then mean total."""
    cand_totals = np.asarray(cand_totals, dtype=float)
    # A/B lever (env SELECT_LSE=<alpha>, off by default; review #4 F1):
    # binary coverage treats a 200 and a 265 in the same world as equal
    # once the world is "covered" — the hypothesized cause of the
    # below-random assembly overlap (1.87 vs null 2.51: coverage
    # scatters co-booms to stretch breadth). Log-sum-exp keeps paying
    # for DEPTH above the line, letting the portfolio concentrate
    # co-booming players into single entries when the exchange rate
    # favors it. alpha in 1/DK-points; ~0.05-0.15 spans soft-to-sharp.
    import math as _math
    _env = {} if env is None else env
    _alpha = float(_env.get("SELECT_LSE", "0") or 0)
    _ladder_spec = _env.get("SELECT_LADDER", "")
    if not _math.isfinite(_alpha) or _alpha < 0:
        raise ValueError("SELECT_LSE must be finite and nonnegative")
    if _alpha > 0 and _ladder_spec:
        raise ValueError("SELECT_LSE and SELECT_LADDER are mutually exclusive")
    if _alpha > 0:
        if trace_capture is not None:
            raise ValueError(
                "prelock tracing supports the binary-tail selector only"
            )
        return _select_lse_entries(cand_totals, n_entries, line, _alpha)
    # Research lever (env SELECT_LADDER, off by default; Ring A / A1,
    # protocol pending the operator's utility freeze): portfolio-marginal
    # greedy on a sparse tail-utility ladder (optionally plus an E[max]
    # term) instead of binary coverage at one line.  Registered in the
    # immutable lever set; never set on production deployments.
    if _ladder_spec:
        if trace_capture is not None:
            raise ValueError(
                "prelock tracing supports the binary-tail selector only"
            )
        ladder, mean_weight = _parse_ladder(_ladder_spec)
        return select_ladder_entries(
            cand_totals, n_entries, ladder, mean_weight=mean_weight)
    clears = cand_totals >= line
    return select_from_support(clears, clears.mean(axis=1),
                               cand_totals.mean(axis=1), n_entries,
                               trace_capture=trace_capture)


def select_from_support(
    clears: np.ndarray,
    p_line: np.ndarray,
    mean_total: np.ndarray,
    n_entries: int,
    trace_capture: Callable[[Mapping[str, Any]], None] | None = None,
) -> list[int]:
    """THE greedy coverage selector, expressed over its sufficient
    statistics: the per-world clear mask plus the two tiebreakers
    (p_line, then mean total).

    Factored out 2026-08-05 (Sol audit 3): the acceptance gate rebuilt
    selection from persisted masks with binary 0/1 totals, which
    silently DISCARDS the mean-total tiebreak — so a reproduction test
    could pass on fixtures and diverge in production. Production and
    the gate now call this same function, and any candidate set that
    ties on coverage and p_line is broken identically in both."""
    clears = np.asarray(clears, dtype=bool)
    p_line = np.asarray(p_line, dtype=float)
    mean_total = np.asarray(mean_total, dtype=float)
    n_entries = min(n_entries, len(clears))
    if trace_capture is None:
        selected: list[int] = []
        covered = np.zeros(clears.shape[1], dtype=bool)
        remaining = set(range(len(clears)))
        while len(selected) < n_entries and remaining:
            best = max(
                remaining,
                key=lambda i: (
                    int(np.count_nonzero(clears[i] & ~covered)),
                    p_line[i],
                    mean_total[i],
                ),
            )
            if not np.count_nonzero(clears[best] & ~covered):
                break  # coverage saturated; fill below
            selected.append(best)
            covered |= clears[best]
            remaining.discard(best)
        fill = sorted(
            remaining,
            key=lambda i: (p_line[i], mean_total[i]),
            reverse=True,
        )
        selected += fill[: n_entries - len(selected)]
        return selected

    selected: list[int] = []
    steps: list[dict[str, Any]] = []
    covered = np.zeros(clears.shape[1], dtype=bool)
    remaining = set(range(len(clears)))
    while len(selected) < n_entries and remaining:
        fresh = {
            index: int(np.count_nonzero(clears[index] & ~covered))
            for index in remaining
        }
        best = max(
            remaining,
            key=lambda i: (fresh[i], p_line[i], mean_total[i]),
        )
        if not fresh[best]:
            break  # coverage saturated; fill below
        steps.append({
            "candidate_index": int(best),
            "selector_rank": len(selected),
            "selection_phase": "COVERAGE",
            "fresh_world_count": fresh[best],
            "individual_clear_count": int(np.count_nonzero(clears[best])),
            "p_line": float(p_line[best]),
            "mean_simulated_total": float(mean_total[best]),
            "tiebreak_values": [
                fresh[best],
                float(p_line[best]),
                float(mean_total[best]),
            ],
        })
        selected.append(best)
        covered |= clears[best]
        remaining.discard(best)
    fill = sorted(remaining, key=lambda i: (p_line[i], mean_total[i]),
                  reverse=True)
    selected_fill = fill[: n_entries - len(selected)]
    for best in selected_fill:
        steps.append({
            "candidate_index": int(best),
            "selector_rank": len(steps),
            "selection_phase": "SATURATION_FILL",
            "fresh_world_count": int(
                np.count_nonzero(clears[best] & ~covered)
            ),
            "individual_clear_count": int(np.count_nonzero(clears[best])),
            "p_line": float(p_line[best]),
            "mean_simulated_total": float(mean_total[best]),
            "tiebreak_values": [
                float(p_line[best]),
                float(mean_total[best]),
            ],
        })
    selected += selected_fill
    selected_step = {
        int(step["candidate_index"]): step for step in steps
    }
    trace_capture({
        "schema_version": "binary-tail-selector-trace/v1",
        "candidate_count": len(clears),
        "world_count": int(clears.shape[1]),
        "selected_indices": [int(index) for index in selected],
        "steps": steps,
        "decisions": [
            (
                dict(selected_step[index])
                if index in selected_step
                else {
                    "candidate_index": index,
                    "selector_rank": None,
                    "selection_phase": "TERMINAL",
                    "fresh_world_count": int(
                        np.count_nonzero(clears[index] & ~covered)
                    ),
                    "individual_clear_count": int(
                        np.count_nonzero(clears[index])
                    ),
                    "p_line": float(p_line[index]),
                    "mean_simulated_total": float(mean_total[index]),
                    "tiebreak_values": [
                        int(np.count_nonzero(clears[index] & ~covered)),
                        float(p_line[index]),
                        float(mean_total[index]),
                    ],
                }
            )
            for index in range(len(clears))
        ],
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    })
    return selected


def _select_lse_entries(
    cand_totals: np.ndarray, n_entries: int, line: float, alpha: float
) -> list[int]:
    """Greedy portfolio selection on sum_w log(sum_{i in S}
    exp(alpha*(score_iw - line))) — still submodular (log of a modular
    sum), so greedy keeps the 1-1/e guarantee. Unlike binary coverage,
    the marginal gain of a candidate never hits zero in a world already
    covered — it just shrinks — so depth can outbid breadth."""
    T = np.asarray(cand_totals, dtype=float)
    n_entries = min(n_entries, len(T))
    E = np.exp(np.clip(alpha * (T - line), -60.0, 60.0))
    S = np.full(T.shape[1], 1e-12)
    remaining = set(range(len(T)))
    selected: list[int] = []
    while len(selected) < n_entries and remaining:
        idx = np.fromiter(remaining, dtype=int)
        gains = np.log1p(E[idx] / S).sum(axis=1)
        best = int(idx[int(np.argmax(gains))])
        selected.append(best)
        S = S + E[best]
        remaining.discard(best)
    return selected


def _parse_ladder(spec: str) -> tuple[dict[float, float], float]:
    """Parse SELECT_LADDER: comma-separated ``threshold:weight`` pairs plus
    an optional ``mean:<weight>`` E[max] term, e.g.
    ``"240:32,230:16,220:8,210:4,200:2,194:1"`` or ``"mean:1"``. Junk
    fails closed rather than silently selecting under a half-read utility.
    """
    import math

    if not isinstance(spec, str) or not spec.strip():
        raise ValueError("SELECT_LADDER is empty")
    tokens = spec.split(",")
    if any(not token.strip() for token in tokens):
        raise ValueError("SELECT_LADDER contains an empty entry")
    ladder: dict[float, float] = {}
    mean_weight = 0.0
    mean_seen = False
    for token in (t.strip() for t in tokens):
        key, _, value = token.partition(":")
        if not value:
            raise ValueError(f"SELECT_LADDER entry {token!r} lacks a weight")
        weight = float(value)
        if not math.isfinite(weight) or weight < 0:
            raise ValueError(f"SELECT_LADDER weight is invalid in {token!r}")
        if key.strip().lower() == "mean":
            if mean_seen:
                raise ValueError("SELECT_LADDER repeats the mean term")
            mean_seen = True
            mean_weight = weight
            continue
        threshold = float(key)
        if not math.isfinite(threshold) or threshold <= 0:
            raise ValueError(f"SELECT_LADDER threshold is invalid in {token!r}")
        if threshold in ladder:
            raise ValueError(f"SELECT_LADDER repeats threshold {threshold:g}")
        ladder[threshold] = weight
    if mean_weight <= 0 and not any(weight > 0 for weight in ladder.values()):
        raise ValueError("SELECT_LADDER specifies no positive utility term")
    return ladder, mean_weight


def select_ladder_entries(
    cand_totals: np.ndarray,
    n_entries: int,
    ladder: dict[float, float],
    mean_weight: float = 0.0,
) -> list[int]:
    """Greedy portfolio-marginal selection on E[u(max)] for the sparse
    ladder utility u(x) = sum_t w_t*1[x >= t] + mean_weight*x.

    Each step adds the candidate maximizing
    sum_w [u(max(m_w, S_iw)) - u(m_w)], where m_w is the book's best
    total so far in world w. The objective is monotone submodular for any
    nondecreasing u, so greedy keeps the same (1-1/e) guarantee binary
    coverage has; unlike binary coverage it credits raising an
    already-covered world (the C-S mean gap's fingerprint) and values the
    thresholds the operator is actually paid on. m starts at 0.0, which
    is exact for nonnegative DK totals. Ties break by mean total then
    lower candidate index, deterministically.
    """
    T = np.asarray(cand_totals, dtype=float)
    n_entries = min(n_entries, len(T))
    if T.ndim != 2 or not np.isfinite(T).all():
        raise ValueError("ladder candidate totals must be a finite matrix")
    if not np.isfinite(mean_weight) or mean_weight < 0:
        raise ValueError("ladder mean weight is invalid")
    if any(
        not np.isfinite(float(threshold))
        or float(threshold) <= 0
        or not np.isfinite(float(weight))
        or float(weight) < 0
        for threshold, weight in ladder.items()
    ):
        raise ValueError("ladder threshold or weight is invalid")
    if mean_weight <= 0 and not any(float(weight) > 0 for weight in ladder.values()):
        raise ValueError("ladder utility has no positive term")
    if mean_weight > 0 and np.any(T < 0):
        raise ValueError(
            "ladder mean utility requires nonnegative candidate totals"
        )
    thresholds = np.array(sorted(ladder), dtype=float)
    weights = np.array([ladder[t] for t in thresholds], dtype=float)
    mean_total = T.mean(axis=1)
    m = np.zeros(T.shape[1])
    # cleared[t, w]: book already clears threshold t in world w.
    cleared = np.zeros((len(thresholds), T.shape[1]), dtype=bool)
    remaining = set(range(len(T)))
    selected: list[int] = []
    while len(selected) < n_entries and remaining:
        idx = np.fromiter(sorted(remaining), dtype=int)
        gains = np.zeros(len(idx))
        for t_ix, threshold in enumerate(thresholds):
            newly = (T[idx] >= threshold) & ~cleared[t_ix]
            gains += weights[t_ix] * newly.sum(axis=1)
        if mean_weight > 0:
            gains += mean_weight * np.maximum(T[idx] - m, 0.0).sum(axis=1)
        order = np.lexsort((-idx, mean_total[idx], gains))
        best = int(idx[order[-1]])
        selected.append(best)
        np.maximum(m, T[best], out=m)
        cleared |= T[best] >= thresholds[:, None]
        remaining.discard(best)
    return selected


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
    env: Mapping[str, str] | None = None,
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
        locks=locks, bans=bans, max_overlap=6, env=env,
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
        env=env,
    )
    return core, lineups
