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

    # A/B lever (env SHOWDOWN_BRING_BACK, off pending replay validation):
    # 88% of winning showdown lineups with a pass-position captain
    # (QB/WR/TE) carried an OPPOSING pass-position player (FantasyLabs
    # via 2026-08-03 research triage) — near-mandatory, and this
    # optimizer had NO bring-back rule at all. Conditional big-M: if the
    # captain is pass-position on team T, require >=1 QB/WR/TE from the
    # other team anywhere in the lineup.
    import os as _os

    if _os.environ.get("SHOWDOWN_BRING_BACK"):
        PASS_POS = ("QB", "WR", "TE")
        teams = sorted({p["team"] for p in players})
        if len(teams) == 2:
            for team in teams:
                opp_pass = [p["id"] for p in players
                            if p["team"] != team and p["pos"] in PASS_POS]
                own_pass_cpt = [p["id"] for p in players
                                if p["team"] == team and p["pos"] in PASS_POS]
                if opp_pass and own_pass_cpt:
                    prob += (pulp.lpSum(c[pid] + f[pid] for pid in opp_pass)
                             >= pulp.lpSum(c[pid] for pid in own_pass_cpt))
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


# --- Simulated-outcomes construction (issue #10 modernization) ------------
# Ports the classic side's correlated-draw machinery (lineup.simulate_lineups
# + lineup.select_tail_entries) to Captain Mode. Draws come from the caller
# (showdown_replay builds them from projection mean/sd + a shared game
# factor); these helpers only consume them.

def lineup_draw_totals(lineups, draws_by_id) -> "np.ndarray":
    """(n_lineups, n_sims) DK totals across draws, captain at 1.5x.
    draws_by_id: player id -> (n_sims,) points array."""
    import numpy as np

    totals = np.zeros((len(lineups), next(iter(draws_by_id.values())).shape[0]))
    for i, lu in enumerate(lineups):
        totals[i] = CPT_MULT * draws_by_id[lu.captain["id"]]
        for p in lu.flex:
            totals[i] += draws_by_id[p["id"]]
    return totals


def simulate_showdown_lineups(
    players: list[Player],
    draws_by_id: dict,
    n_keep: int = 20,
    n_draw_solves: int = 120,
    counters: dict | None = None,
    **kwargs,
) -> list[tuple[ShowdownLineup, int]]:
    """Optimize one lineup per Monte Carlo draw and keep the recurrent
    ones — captain choice included in identity (ShowdownLineup.key), since
    correlated draws are exactly what should discover which player's boom
    worlds deserve the 1.5x slot. A `counters` dict, when supplied, is
    filled with the salary-aware per-draw optimal rates over ALL solves
    ("n", "cpt": Counter, "flex": Counter) — the recurrence truncation
    below keeps only the top lineups, so this is the one place the full
    captain-optimal distribution is observable."""
    from collections import Counter

    counts: Counter[tuple] = Counter()
    exemplars: dict[tuple, ShowdownLineup] = {}
    n_sims = next(iter(draws_by_id.values())).shape[0]
    for k in range(min(n_draw_solves, n_sims)):
        sim_players = [
            {**p, "proj": float(draws_by_id[p["id"]][k])} for p in players
        ]
        lu = optimize_showdown(sim_players, **kwargs)
        if lu is None:
            continue
        if counters is not None:
            counters["n"] = counters.get("n", 0) + 1
            counters.setdefault("cpt", Counter())[lu.captain["id"]] += 1
            fc = counters.setdefault("flex", Counter())
            for p in lu.flex:
                fc[p["id"]] += 1
        counts[lu.key] += 1
        if lu.key not in exemplars:
            by_id = {p["id"]: p for p in players}
            exemplars[lu.key] = ShowdownLineup(
                by_id[lu.captain["id"]], [by_id[p["id"]] for p in lu.flex])
    return [(exemplars[k], n) for k, n in counts.most_common(n_keep)]


def showdown_player_metrics(
    pool: list[Player], draws_by_id: dict, counters: dict | None = None,
) -> list[dict]:
    """Per-player captaincy diagnostics from the correlated draws
    (Stokastic-style display, computed rather than intuited):

    - p_top:  share of draws where the player outscores the whole slate —
      the salary-FREE captain-optimal rate (CPT multiplies everyone the
      same 1.5x, so the draw's top scorer is its best captain).
    - p_top6: share of draws where the player lands in the best six — the
      salary-free "belongs in the perfect lineup" rate.
    - cpt_opt / flex_opt: salary-AWARE rates from the per-draw MILP solves
      when `counters` (filled by simulate_showdown_lineups) is supplied.
    """
    import numpy as np

    ids = [p["id"] for p in pool]
    mat = np.vstack([np.asarray(draws_by_id[i], dtype=float) for i in ids])
    n = mat.shape[1]
    p_top = np.bincount(mat.argmax(axis=0), minlength=len(ids)) / n
    top6 = np.bincount(
        np.argsort(-mat, axis=0)[:6, :].ravel(), minlength=len(ids)) / n
    total = counters.get("n", 0) if counters else 0
    out = []
    for k, p in enumerate(pool):
        row = {
            "id": p["id"], "name": p.get("name"), "team": p.get("team"),
            "position": p.get("pos"), "salary": p.get("salary"),
            "p_top": round(float(p_top[k]), 4),
            "p_top6": round(float(top6[k]), 4),
        }
        if total:
            row["cpt_opt"] = round(counters["cpt"].get(p["id"], 0) / total, 4)
            row["flex_opt"] = round(counters["flex"].get(p["id"], 0) / total, 4)
        out.append(row)
    out.sort(key=lambda r: (-r["p_top"], -r["p_top6"]))
    return out


def select_showdown_entries(
    candidates: list[ShowdownLineup],
    draws_by_id: dict,
    n_entries: int,
    line: float,
) -> list[ShowdownLineup]:
    """Greedy sim-coverage entry selection at a tail line — identical
    logic to the classic side's select_tail_entries, fed captain-weighted
    totals."""
    from .lineup import select_tail_entries

    if not candidates:
        return []
    totals = lineup_draw_totals(candidates, draws_by_id)
    idx = select_tail_entries(totals, n_entries, line)
    return [candidates[i] for i in idx]


# Correlated-draw construction adopted 2026-08-01 (Addendum 26): sim-mode
# capture 85.0% vs 80.7% MILP baseline on the 2025 showdown replay,
# slates >=90% capture doubled (16/41 vs 8/41).
SHOWDOWN_SIM_SIGMA = 0.18   # shared game-factor sigma (see simulate.py)
FALLBACK_SD_RATIO = 0.9     # sd for rows projected without a model sd
DEFAULT_SHOWDOWN_TAIL_LINE = 150.0


def showdown_draws(pool: list[Player], n_sims: int, seed: int) -> dict:
    """Correlated per-player point draws for one slate: a shared
    mean-preserving lognormal game factor (a single-game slate IS one
    environment) times an independent gamma per player matched to the
    player's projection mean/sd ('proj'/'proj_sd'; missing sd falls back
    to FALLBACK_SD_RATIO x mean)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    game = rng.lognormal(-SHOWDOWN_SIM_SIGMA ** 2 / 2, SHOWDOWN_SIM_SIGMA, n_sims)
    draws = {}
    for p in pool:
        m = float(p["proj"])
        s = float(p.get("proj_sd") or 0) or m * FALLBACK_SD_RATIO
        if m <= 0 or s <= 0:
            draws[p["id"]] = np.full(n_sims, max(m, 0.0)) * game
            continue
        shape = (m / s) ** 2
        draws[p["id"]] = rng.gamma(shape, m / shape, n_sims) * game
    return draws


def sim_mode_entries(pool: list[Player], n_entries: int, seed: int,
                     n_sims: int = 4000, tail_line: float | None = None,
                     with_metrics: bool = False,
                     **kwargs) -> list[ShowdownLineup] | tuple:
    """Simulated-outcomes construction: candidates from (a) a diverse MILP
    batch and (b) per-draw re-optimization recurrence, then greedy
    tail-line coverage across the correlated draws. kwargs (locks, bans,
    captain_lock, ...) pass through to every underlying solve.
    with_metrics=True additionally returns showdown_player_metrics (the
    captain board) as a second element."""
    import os

    draws = showdown_draws(pool, n_sims=n_sims, seed=seed)
    milp = optimize_many_showdown(pool, n_lineups=max(2 * n_entries, 30),
                                  max_overlap=4, **kwargs)
    counters: dict | None = {} if with_metrics else None
    recurrent = simulate_showdown_lineups(pool, draws, n_keep=n_entries,
                                          counters=counters, **kwargs)
    seen, candidates = set(), []
    for lu in milp + [l for l, _ in recurrent]:
        if lu.key not in seen:
            seen.add(lu.key)
            candidates.append(lu)
    if tail_line is None:
        tail_line = float(os.environ.get("SHOWDOWN_TAIL_LINE",
                                         DEFAULT_SHOWDOWN_TAIL_LINE) or 0)
    entries = select_showdown_entries(candidates, draws, n_entries, tail_line)
    if with_metrics:
        return entries, showdown_player_metrics(pool, draws, counters)
    return entries
