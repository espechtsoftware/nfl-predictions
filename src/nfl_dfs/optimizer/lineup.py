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
# Tournament construction defaults (the only mode this shop plays): a
# sub-$4k ceiling punt appeared in 94% of 2025 Milly Maker winners.
PUNT_MAX_SALARY = 4_000
PUNT_MIN = 1
LEVERAGE_PENALTY = 25.0  # pts deducted x naive-ownership weight (chalk fade)
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
) -> Lineup | None:
    """Solve one lineup. Returns None if infeasible.
    game_lock=(game_id, n) forces >= n players from that game — the
    concentrated-game-stack construction (issue #6): Milly winners take
    50-80% of their points from one game."""
    prob = pulp.LpProblem("dfs", pulp.LpMaximize)
    x = {p["id"]: pulp.LpVariable(f"x_{p['id']}", cat="Binary") for p in players}
    by_id = {p["id"]: p for p in players}

    prob += pulp.lpSum(x[p["id"]] * float(p[objective_col]) for p in players)
    prob += pulp.lpSum(x[p["id"]] * p["salary"] for p in players) <= budget
    # Milly winners spend the cap (2025 median $0 left; 2023-24 90% within
    # $300). Replay-validated 2026-07-26 (run I): mean best-of-40 180.1 ->
    # 182.3 with a floor of 49000. Env MIN_LINEUP_SALARY overrides; 0 disables.
    import os as _os

    _min_sal = (min_salary if min_salary is not None
                else int(_os.environ.get("MIN_LINEUP_SALARY", "49000") or 0))
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

    # Minimum 2 different games: for every game, players NOT in that game >= 1
    games = sorted({p.get("game_id") for p in players if p.get("game_id")})
    if len(games) >= MIN_GAMES:
        for game in games:
            prob += pulp.lpSum(
                x[p["id"]] for p in players if p.get("game_id") != game
            ) >= 1

    # Tournament punt slot: winners rostered a sub-$4k player who scored
    # 15+ in 94% of 2025 Milly Makers (reports/2025-milly-winners.csv).
    if punt_min and punt_max_salary:
        if _os.environ.get("PUNT_STRICT") and any(
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
    v2_min = int(_os.environ.get("VALUE2_MIN", "0"))
    if v2_min:
        v2_max = int(_os.environ.get("VALUE2_MAX", "5300"))
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
    if _os.environ.get("OWN_BARBELL") and any(
            p.get("own_est") is not None for p in players):
        b_low = float(_os.environ.get("OWN_BARBELL_LOW", "0.05"))
        b_high = float(_os.environ.get("OWN_BARBELL_HIGH", "0.20"))
        n_low = int(_os.environ.get("OWN_BARBELL_NLOW", "3"))
        n_high = int(_os.environ.get("OWN_BARBELL_NHIGH", "2"))
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
              else int(_os.environ.get("MAX_PER_GAME", "0")))
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
    import os as _os2

    min_lowown = int(_os2.environ.get("MIN_LOWOWN", "0"))
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
    punt_max_salary: int | None = PUNT_MAX_SALARY,
    punt_min: int = PUNT_MIN,
    **kwargs,
) -> list[Lineup]:
    """Generate n unique lineups; each new lineup may share at most
    max_overlap players with any previous one."""
    # Assumption-validation lever (2026-08-01): PUNT_MIN env overrides the
    # mandatory-punt rule so its causal value can be measured (the rule was
    # adopted from "94% of Milly winners had a punt" -- correlational).
    import os as _os

    punt_min = int(_os.environ.get("PUNT_MIN", punt_min))
    # PUNT_MAX (2026-08-03): the $4k threshold was inherited from the
    # 2025 winner study (punts cluster $2.9-3.9k) and never dose-tested.
    if _os.environ.get("PUNT_MAX"):
        punt_max_salary = int(_os.environ["PUNT_MAX"])
    lineups: list[Lineup] = []
    banned: list[frozenset] = []
    for _ in range(n_lineups):
        # CBC runs as a subprocess and occasionally fails to launch under
        # load (seen in replays and tests). One retry, then return what we
        # have rather than blowing up the whole batch.
        for attempt in (1, 2):
            try:
                lu = optimize(players, stack=stack, banned_lineups=banned,
                              max_overlap=max_overlap,
                              punt_max_salary=punt_max_salary,
                              punt_min=punt_min, **kwargs)
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


def select_tail_entries(
    cand_totals: np.ndarray, n_entries: int, line: float
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
    import os as _os
    _alpha = float(_os.environ.get("SELECT_LSE", "0") or 0)
    if _alpha > 0:
        return _select_lse_entries(cand_totals, n_entries, line, _alpha)
    clears = cand_totals >= line
    p_line = clears.mean(axis=1)
    mean_total = cand_totals.mean(axis=1)
    n_entries = min(n_entries, len(cand_totals))
    selected: list[int] = []
    covered = np.zeros(cand_totals.shape[1], dtype=bool)
    remaining = set(range(len(cand_totals)))
    while len(selected) < n_entries and remaining:
        best = max(remaining,
                   key=lambda i: (int(np.count_nonzero(clears[i] & ~covered)),
                                  p_line[i], mean_total[i]))
        if not np.count_nonzero(clears[best] & ~covered):
            break  # coverage saturated; fill below
        selected.append(best)
        covered |= clears[best]
        remaining.discard(best)
    fill = sorted(remaining, key=lambda i: (p_line[i], mean_total[i]),
                  reverse=True)
    selected += fill[: n_entries - len(selected)]
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
