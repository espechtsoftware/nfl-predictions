"""Backtest engine (guide §10): reconstruct historical slates, project with
point-in-time features only, build lineups, score against actuals, simulate
contest outcomes, report ROI.

Run over 3+ full seasons before risking money: single-season DFS results
are noise, and a bad model looks great over 17 weeks about as often as it
looks bad.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field

import numpy as np
import pandas as pd

from ..optimizer.lineup import (Lineup, StackRules, optimize, optimize_many,
                                select_tail_entries)
from . import field as field_sim
from .payout import Contest, roi

log = logging.getLogger(__name__)

REQUIRED_COLS = {"id", "name", "pos", "team", "opp", "game_id",
                 "salary", "proj", "actual"}


@dataclass
class WeekResult:
    season: int
    week: int
    lineups: list[Lineup]
    lineup_scores: list[float]
    percentiles: list[float]
    winnings: list[float]


@dataclass
class BacktestResult:
    weeks: list[WeekResult] = dc_field(default_factory=list)
    contest: Contest | None = None

    @property
    def total_roi(self) -> float:
        w = [x for wk in self.weeks for x in wk.winnings]
        return roi(np.array(w), self.contest.entry_fee) if w else 0.0

    def roi_by_season(self) -> dict[int, float]:
        out: dict[int, list[float]] = {}
        for wk in self.weeks:
            out.setdefault(wk.season, []).extend(wk.winnings)
        return {s: roi(np.array(w), self.contest.entry_fee) for s, w in out.items()}

    def summary(self) -> str:
        lines = [f"contest={self.contest.name}  entries={sum(len(w.winnings) for w in self.weeks)}"]
        for season, r in sorted(self.roi_by_season().items()):
            lines.append(f"  {season}: ROI {r:+.1%}")
        lines.append(f"  TOTAL: ROI {self.total_roi:+.1%}")
        med = np.median([p for wk in self.weeks for p in wk.percentiles] or [0])
        lines.append(f"  median finish percentile: {med:.1%} (lower is better)")
        return "\n".join(lines)


def leakage_guard(slate: pd.DataFrame) -> None:
    """Cheap structural checks that the slate frame is point-in-time: the
    projection must not equal the actual (a copied column is the classic
    reconstruction bug), and required columns exist."""
    missing = REQUIRED_COLS - set(slate.columns)
    if missing:
        raise ValueError(f"Slate missing columns: {sorted(missing)}")
    both = slate.dropna(subset=["proj", "actual"])
    if len(both) >= 30 and np.allclose(both["proj"], both["actual"]):
        raise AssertionError(
            "proj == actual for the whole slate; projections were "
            "reconstructed from the answer key."
        )


def _row_draws(slate: pd.DataFrame, draws: np.ndarray) -> np.ndarray:
    """Per-slate-row draw matrix, aligned to slate row order. Rows without a
    draw (DST, draw_idx == -1) get their static projection in every sim."""
    di = slate["draw_idx"].to_numpy(dtype=int)
    out = np.empty((len(slate), draws.shape[1]), dtype=np.float32)
    has = di >= 0
    out[has] = draws[di[has]]
    out[~has] = slate["proj"].to_numpy(dtype=float)[~has, None]
    return out


def tail_select_lineups(
    slate: pd.DataFrame,
    pool: list[dict],
    draws: np.ndarray,
    tail_line: float,
    n_entries: int,
    stack: StackRules | None,
    objective_col: str,
    candidate_multiple: int = 2,
    n_boom_solves: int = 40,
    n_game_stacks: int = 4,
    n_per_game: int = 3,
) -> list[Lineup]:
    """Entry selection on P(best-of-N >= tail_line) (guide: issue #5).

    Candidates come from two generators: the diverse leverage-objective
    batch (what we entered before), plus one solve per top-total sim —
    'if the slate booms like THIS, what's the best lineup?' — which yields
    genuinely boom-correlated entries the mean objective never builds.
    Selection is greedy sim-coverage (see select_tail_entries)."""
    rd = _row_draws(slate, draws)
    cands = optimize_many(pool, n_lineups=candidate_multiple * n_entries,
                          stack=stack, objective_col=objective_col)
    for lu in cands:
        lu.tag = "lev"
    seen = {lu.ids for lu in cands}
    boom_sims = np.argsort(rd.sum(axis=0))[::-1][:n_boom_solves]
    for k in boom_sims:
        sim_pool = [{**p, "proj_sim": float(rd[i, k])}
                    for i, p in enumerate(pool)]
        try:
            lu = optimize(sim_pool, stack=stack, objective_col="proj_sim")
        except Exception as exc:  # CBC subprocess flake: skip this draw
            log.warning("boom-draw solve failed: %s", exc)
            continue
        if lu is not None and lu.ids not in seen:
            lu.tag = "boom"
            seen.add(lu.ids)
            cands.append(lu)
    # Anti-correlation A/B (env N_NOSTACK): candidates with NO stack
    # rules — pure variance plays; coverage selection decides if any
    # earn slots. Prior is low (all 48 studied Milly winners stacked).
    import os as _os

    n_nostack = int(_os.environ.get("N_NOSTACK", "0"))
    if n_nostack:
        banned_ns = []
        for _ in range(n_nostack):
            try:
                lu = optimize(pool, stack=None, objective_col=objective_col,
                              banned_lineups=banned_ns, max_overlap=7)
            except Exception:
                break
            if lu is None:
                break
            banned_ns.append(lu.ids)
            if lu.ids not in seen:
                lu.tag = "nostk"
                seen.add(lu.ids)
                cands.append(lu)
    # Mid-tier QB A/B (env N_MIDQB): one candidate locked on each of the
    # top-N $4-6.5k QBs by simulated p90 — targets the measured miss zone
    # (17/41 top-scorer misses were QBs, 27/41 mid-salary).
    n_midqb = int(_os.environ.get("N_MIDQB", "0"))
    if n_midqb:
        qb_rows = [(i, p) for i, p in enumerate(pool)
                   if p["pos"] == "QB" and 4000 < p["salary"] <= 6500]
        qb_rows.sort(key=lambda t: -float(np.percentile(rd[t[0]], 90)))
        for _, qb in qb_rows[:n_midqb]:
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              locks={qb["id"]})
            except Exception:
                continue
            if lu is not None and lu.ids not in seen:
                lu.tag = "midqb"
                seen.add(lu.ids)
                cands.append(lu)
    # Concentrated game stacks (issue #6): for each top game environment,
    # force >= 5 players from that game. Winners take 50-80% of points
    # from one game; these are deliberately lower-mean, higher-variance
    # candidates — coverage selection decides how many survive.
    game_proj = (slate[slate.get("game_id").notna()]
                 .groupby("game_id")["proj"].sum().sort_values(ascending=False)
                 if "game_id" in slate.columns else pd.Series(dtype=float))
    for gid in game_proj.head(n_game_stacks).index:
        banned = []
        for _ in range(n_per_game):
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              game_lock=(gid, 5), banned_lineups=banned,
                              max_overlap=7)
            except Exception as exc:
                log.warning("game-stack solve failed (%s): %s", gid, exc)
                break
            if lu is None:
                break
            banned.append(lu.ids)
            if lu.ids not in seen:
                lu.tag = "game"
                seen.add(lu.ids)
                cands.append(lu)
    if not cands:
        return []
    id2row = {pid: i for i, pid in enumerate(slate["id"])}
    cand_totals = np.stack([
        rd[[id2row[p["id"]] for p in lu.players]].sum(axis=0) for lu in cands
    ])
    picked = select_tail_entries(cand_totals, n_entries, tail_line)
    return [cands[i] for i in picked]


def run_week(
    slate: pd.DataFrame,
    contest: Contest,
    n_entries: int = 20,
    field_size: int = 5_000,
    stack: StackRules | None = None,
    seed: int | None = 42,
    sharp_fraction: float = 0.0,
    draws: np.ndarray | None = None,
    tail_line: float | None = None,
    n_boom_solves: int = 40,
) -> WeekResult | None:
    """Backtest one historical slate. `slate` columns: REQUIRED_COLS.
    With `draws` (player-draw matrix indexed by the slate's draw_idx
    column) and `tail_line`, entries are selected to maximize
    P(best entry >= tail_line) instead of taking the top objective batch."""
    leakage_guard(slate)
    season = int(slate["season"].iloc[0]) if "season" in slate else 0
    week = int(slate["week"].iloc[0]) if "week" in slate else 0

    pool = slate.to_dict("records")
    obj = "proj_tourney" if "proj_tourney" in slate.columns else "proj"
    if draws is not None and tail_line is not None and "draw_idx" in slate.columns:
        import os as _os

        lineups = tail_select_lineups(
            slate, pool, draws, tail_line, n_entries, stack, obj,
            candidate_multiple=int(_os.environ.get("CAND_MULT", "2")),
            n_boom_solves=int(_os.environ.get("N_BOOM", str(n_boom_solves))))
    else:
        lineups = optimize_many(pool, n_lineups=n_entries, stack=stack,
                                objective_col=obj)
    if not lineups:
        log.warning("No feasible lineups for %s week %s", season, week)
        return None

    actual = slate.set_index("id")["actual"]
    lineup_scores = [float(actual.reindex([p["id"] for p in lu.players]).sum())
                     for lu in lineups]

    fld = field_sim.sample_field(slate, n_lineups=field_size, seed=seed,
                                 sharp_fraction=sharp_fraction)
    scores = field_sim.field_scores(fld, slate["actual"].to_numpy())

    percentiles, winnings = [], []
    for s in lineup_scores:
        beaten = float(np.mean(scores > s))
        rank = max(1, int(round(beaten * contest.field_size)) + 1)
        percentiles.append(beaten)
        winnings.append(contest.payout_for_rank(rank))

    return WeekResult(season, week, lineups, lineup_scores, percentiles, winnings)


def run(
    slates: list[pd.DataFrame],
    contest: Contest,
    n_entries: int = 20,
    field_size: int = 5_000,
    stack: StackRules | None = None,
    seed: int | None = 42,
    sharp_fraction: float = 0.0,
    draws: np.ndarray | None = None,
    tail_line: float | None = None,
    n_boom_solves: int = 40,
) -> BacktestResult:
    result = BacktestResult(contest=contest)
    for slate in slates:
        wk = run_week(slate, contest, n_entries=n_entries,
                      field_size=field_size, stack=stack, seed=seed,
                      sharp_fraction=sharp_fraction, draws=draws,
                      tail_line=tail_line, n_boom_solves=n_boom_solves)
        if wk is not None:
            result.weeks.append(wk)
            log.info("season %s week %s: best %.1f pts, best pct %.1f%%",
                     wk.season, wk.week, max(wk.lineup_scores),
                     100 * min(wk.percentiles))
    return result
