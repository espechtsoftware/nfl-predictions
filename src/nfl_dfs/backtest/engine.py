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
    draw (DST, draw_idx == -1) get their static projection in every sim.

    DST_CORR_DRAWS=1 (A/B, 2026-08-01): constants mean the tail selector
    can never prefer a DST for its boom worlds, even though DST scoring
    anti-correlates with the opposing offense (turnovers, points-allowed
    brackets) and 7/17 winning 2025 Milly punts were DSTs (Addendum 24).
    With the gate on, each DST row gets mean-preserving draws scaled by
    the INVERSE of its opponent's simulated offense total: mult =
    clip(2 - opp_total/mean, 0.3, 1.7), renormalized to mean 1."""
    import os as _os

    di = slate["draw_idx"].to_numpy(dtype=int)
    out = np.empty((len(slate), draws.shape[1]), dtype=np.float32)
    has = di >= 0
    out[has] = draws[di[has]]
    out[~has] = slate["proj"].to_numpy(dtype=float)[~has, None]
    if _os.environ.get("DST_CORR_DRAWS") and (~has).any() and "opp" in slate.columns:
        # Fitted 2026-08-01 from 4,390 team-games 2018-25: DST DK points
        # correlate -0.491 with the opposing offense's total fantasy
        # points, with relative sd 0.93 (mean 6.2, sd 5.8). The first
        # (nulled) version had it backwards on both axes: ~-0.9 corr but
        # only ~0.3 rel-sd. Draws hit the measured moments exactly:
        # mult = 1 + rel_sd*(corr*z_opp + sqrt(1-corr^2)*z_iid), floored
        # (DK DST brackets go to -4) and renormalized to mean 1.
        DST_OPP_CORR, DST_REL_SD = -0.491, 0.93
        rng = np.random.default_rng(7)
        teams = slate["team"].to_numpy()
        opps = slate["opp"].to_numpy()
        for i in np.flatnonzero(~has):
            rows = np.flatnonzero(has & (teams == opps[i]))
            if not len(rows):
                continue
            tot = draws[di[rows]].sum(axis=0)
            sd = tot.std()
            if sd <= 0 or tot.mean() <= 0:
                continue
            z_opp = (tot - tot.mean()) / sd
            z_iid = rng.standard_normal(tot.shape[0])
            mult = 1.0 + DST_REL_SD * (DST_OPP_CORR * z_opp
                                       + np.sqrt(1 - DST_OPP_CORR ** 2) * z_iid)
            mult = np.clip(mult, -0.7, None)
            out[i] = out[i] * (mult / mult.mean())
    return out


def _tier_thresholds(contest: Contest) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized form of Contest.payout_for_rank: cumulative field
    fractions and dollar payouts per tier."""
    cums, pays = [], []
    c = 0.0
    for top_frac, mult in contest.tiers:
        c += top_frac
        cums.append(c)
        pays.append(contest.entry_fee * mult)
    return np.asarray(cums), np.asarray(pays)


def select_dollar_entries(
    slate: pd.DataFrame,
    rd: np.ndarray,
    cands: list[Lineup],
    cand_totals: np.ndarray,
    n_entries: int,
    contest: Contest,
    sharp_fraction: float = 0.0,
    max_overlap: int = 7,
    n_field: int = 1000,
    n_sim_sub: int = 2000,
    seed: int = 42,
) -> list[int]:
    """SELECT_OBJ=dollars (2026-08-01): expected-DOLLARS entry selection.

    The tail-line objective is a step function at one line; real payouts
    are a curve. Here each candidate is scored by its expected winnings:
    a subsampled simulated FIELD (ownership-weighted lineups, scored in
    the SAME correlated sims as our candidates via the draw matrix) gives
    each candidate a per-sim rank, the contest curve converts rank to
    dollars, and E[$] is additive across entries -- so selection is
    greedy by E[$] under the uniqueness (max_overlap) constraint. This
    was issue #13's "expected-dollars objective once field model exists";
    the LineStar ownership model is that field model (pass model_own on
    the slate to use it)."""
    own_vec = (slate["model_own"].to_numpy()
               if "model_own" in slate.columns and slate["model_own"].notna().all()
               else None)
    fld = field_sim.sample_field(slate, n_lineups=n_field, seed=seed,
                                 ownership=own_vec,
                                 sharp_fraction=sharp_fraction)
    if not fld:
        return list(range(min(n_entries, len(cands))))
    rng = np.random.default_rng(seed)
    k_idx = rng.choice(rd.shape[1], size=min(n_sim_sub, rd.shape[1]),
                       replace=False)
    rd_sub = rd[:, k_idx]
    F = np.stack([rd_sub[f].sum(axis=0) for f in fld])  # (n_field, K)
    cums, pays = _tier_thresholds(contest)
    ct = cand_totals[:, k_idx]
    # Tail-resolved rank estimation (Addendum 34 fix): a coarse sampled
    # field resolves ranks only to 1/n_field, but GPP payouts concentrate
    # at 1e-5 of the field -- "beat the whole sample" spans $10..$100k.
    # Hybrid: empirical count where >= EMP_MIN field lineups are ahead;
    # otherwise a normal-tail extrapolation of the per-sim field score
    # distribution, capped by the empirical upper bound so the parametric
    # tail can only REFINE below sample resolution, never contradict it.
    EMP_MIN = 10
    from scipy.stats import norm

    mu = F.mean(axis=0)                                     # per-sim field mean
    sd = np.maximum(F.std(axis=0), 1e-6)
    n_f = F.shape[0]
    ev = np.empty(len(cands))
    for c in range(len(cands)):
        counts = (F > ct[c][None, :]).sum(axis=0)           # field ahead, sampled
        p_emp = counts / n_f
        p_par = norm.sf((ct[c] - mu) / sd)
        p_cap = (counts + 1.0) / n_f                        # empirical upper bound
        p = np.where(counts >= EMP_MIN, p_emp, np.minimum(p_par, p_cap))
        frac = p + 1.0 / contest.field_size                 # ~rank/field_size
        idx = np.searchsorted(cums, frac, side="left")
        pay = np.where(idx < len(pays), pays[np.minimum(idx, len(pays) - 1)], 0.0)
        ev[c] = float(pay.mean())
    order = np.argsort(ev)[::-1]
    picked: list[int] = []
    sel_ids: list[frozenset] = []
    for i in order:
        if len(picked) >= n_entries:
            break
        if all(len(cands[i].ids & s) <= max_overlap for s in sel_ids):
            picked.append(int(i))
            sel_ids.append(cands[i].ids)
    for i in order:  # fill if the overlap constraint ran the list dry
        if len(picked) >= n_entries:
            break
        if int(i) not in picked:
            picked.append(int(i))
    return picked


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
    contest: Contest | None = None,
    sharp_fraction: float = 0.0,
    locks: set | None = None,
    theses: list[dict] | None = None,
) -> list[Lineup]:
    """Entry selection on P(best-of-N >= tail_line) (guide: issue #5).

    Candidates come from two generators: the diverse leverage-objective
    batch (what we entered before), plus one solve per top-total sim —
    'if the slate booms like THIS, what's the best lineup?' — which yields
    genuinely boom-correlated entries the mean objective never builds.
    Selection is greedy sim-coverage (see select_tail_entries)."""
    rd = _row_draws(slate, draws)
    locks = locks or set()
    cands = optimize_many(pool, n_lineups=candidate_multiple * n_entries,
                          stack=stack, objective_col=objective_col,
                          locks=set(locks))
    # Thesis candidates (2026-08-03, OWS "Bink Machine" pattern): each
    # thesis {players: [ids], min: k} guarantees the POOL holds enough
    # combo-containing builds; the post-selection repair below enforces
    # the portfolio floor. Builds TOWARD correlated convictions (pairs
    # with watchlist conversions) instead of only capping exposure.
    for th in (theses or []):
        combo = set(th.get("players") or ())
        need = int(th.get("min") or 0)
        if not combo or need <= 0:
            continue
        banned_th: list = []
        for _ in range(max(need, 2)):
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              locks=combo | set(locks),
                              banned_lineups=banned_th, max_overlap=7)
            except Exception:
                break
            if lu is None:
                break
            banned_th.append(lu.ids)
            if lu.ids not in seen:
                lu.tag = "thesis"
                seen.add(lu.ids)
                cands.append(lu)
    for lu in cands:
        lu.tag = "lev"
    seen = {lu.ids for lu in cands}
    boom_sims = np.argsort(rd.sum(axis=0))[::-1][:n_boom_solves]
    for k in boom_sims:
        sim_pool = [{**p, "proj_sim": float(rd[i, k])}
                    for i, p in enumerate(pool)]
        try:
            lu = optimize(sim_pool, stack=stack, objective_col="proj_sim",
                          locks=set(locks))
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
                              banned_lineups=banned_ns, max_overlap=7,
                              locks=set(locks))
            except Exception:
                break
            if lu is None:
                break
            banned_ns.append(lu.ids)
            if lu.ids not in seen:
                lu.tag = "nostk"
                seen.add(lu.ids)
                cands.append(lu)
    # Low-salary candidate batch (env N_LOWSAL, off by default;
    # underspend-family redesign 2026-08-03): the validated $49k floor
    # pushes every candidate into near-cap build space; these solves at
    # a $47k floor reach constructions the floor forbids, and the
    # coverage selector decides if any earn slots (the original
    # underspend-dedup died with the WRONG rationale — dupe avoidance;
    # ours measure ~0 — this one is pure coverage breadth).
    n_lowsal = int(_os.environ.get("N_LOWSAL", "0"))
    if n_lowsal:
        banned_ls: list = []
        for _ in range(n_lowsal):
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              banned_lineups=banned_ls, max_overlap=7,
                              min_salary=47_000)
            except Exception:
                break
            if lu is None:
                break
            banned_ls.append(lu.ids)
            if lu.ids not in seen:
                lu.tag = "lowsal"
                seen.add(lu.ids)
                cands.append(lu)
    # Quality-diversity archive batch (env QD_CELLS = elites per cell,
    # off by default; MAP-Elites idea, research round 8 2026-08-03): the
    # named batches above are a hand-made archive; this tessellates the
    # descriptor space the real Milly winners actually occupy —
    # max-per-game concentration {2,3,4} (winners avg 2.96) x salary band
    # (winners spend the cap, but coverage may pay off-cap) — and solves
    # the best lineups per cell. Same tail-coverage selector downstream
    # decides which cells earn entries; empty/infeasible cells just skip.
    n_qd = int(_os.environ.get("QD_CELLS", "0"))
    if n_qd:
        for mpg in (2, 3, 4):
            for lo, hi in ((44_000, 47_500), (47_500, 49_000),
                           (49_000, 50_000)):
                banned_qd: list = []
                for _ in range(n_qd):
                    try:
                        lu = optimize(pool, stack=stack,
                                      objective_col=objective_col,
                                      banned_lineups=banned_qd,
                                      max_overlap=7, locks=set(locks),
                                      min_salary=lo, max_salary=hi,
                                      max_per_game=mpg)
                    except Exception:
                        break
                    if lu is None:
                        break
                    banned_qd.append(lu.ids)
                    if lu.ids not in seen:
                        lu.tag = "qd"
                        seen.add(lu.ids)
                        cands.append(lu)
    # Stack-depth A/B (env N_QB_VARIANTS): the harvest attribution found
    # the 40 entries spread over ~16 QBs with max 2-of-8 overlap vs the
    # weekly optimal — right stacks, wrong pieces. For each of the top-8
    # QBs by simulated p90, build several catcher-combination variants
    # (same QB, different pieces) so the pool holds real depth per stack.
    # ADOPTED 2026-08-04 (QF arm, final-exam combos): default 4. QBVAR4
    # alone +2 tails (25/107); with OWN_MODEL=fade, equal 25 tails, best
    # median of the program (14.6%) and two >=237 weeks. "0" disables.
    n_qbvar = int(_os.environ.get("N_QB_VARIANTS", "4"))
    if n_qbvar:
        qb_all = [(i, p) for i, p in enumerate(pool) if p["pos"] == "QB"]
        qb_all.sort(key=lambda t: -float(np.percentile(rd[t[0]], 90)))
        for _, qb in qb_all[:8]:
            banned_qv: list = []
            for _ in range(n_qbvar):
                try:
                    lu = optimize(pool, stack=stack,
                                  objective_col=objective_col,
                                  locks={qb["id"]} | set(locks),
                                  banned_lineups=banned_qv,
                                  max_overlap=6)
                except Exception:
                    break
                if lu is None:
                    break
                banned_qv.append(lu.ids)
                if lu.ids not in seen:
                    lu.tag = "qbvar"
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
                              locks={qb["id"]} | set(locks))
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
                              max_overlap=7, locks=set(locks))
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
    # Dark-game A/B (env N_DARKGAME): concentrated stacks from games
    # RANKED 5+ by projected total — 29% of matched 2025 Milly winners
    # stacked a game ranked 8th-14th on the slate (addendum 20 study).
    n_dark = int(_os.environ.get("N_DARKGAME", "10"))
    if n_dark and len(game_proj) > n_game_stacks:
        for gid in game_proj.index[n_game_stacks:n_game_stacks + n_dark]:
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              game_lock=(gid, 5), locks=set(locks))
            except Exception:
                continue
            if lu is not None and lu.ids not in seen:
                lu.tag = "dark"
                seen.add(lu.ids)
                cands.append(lu)
    if not cands:
        return []
    id2row = {pid: i for i, pid in enumerate(slate["id"])}
    cand_totals = np.stack([
        rd[[id2row[p["id"]] for p in lu.players]].sum(axis=0) for lu in cands
    ])
    if _os.environ.get("SELECT_OBJ") == "dollars" and contest is not None:
        picked = select_dollar_entries(slate, rd, cands, cand_totals,
                                       n_entries, contest,
                                       sharp_fraction=sharp_fraction)
    else:
        max_qbs = int(_os.environ.get("MAX_QBS", "0"))
        if max_qbs:
            qb_of = [next((p["id"] for p in lu.players if p["pos"] == "QB"),
                          None) for lu in cands]
            picked = _select_tail_qb_capped(cand_totals, n_entries,
                                            tail_line, qb_of, max_qbs)
        else:
            picked = select_tail_entries(cand_totals, n_entries, tail_line)
    if theses:
        picked = _enforce_theses(picked, cands, cand_totals, tail_line,
                                 theses)
    return [cands[i] for i in picked]


def _enforce_theses(picked: list[int], cands: list, cand_totals,
                    tail_line: float, theses: list[dict]) -> list[int]:
    """Portfolio floor per thesis: swap the weakest non-thesis entries
    for the best unpicked combo-containing candidates until each quota
    is met (best-effort — a thesis the pool can't satisfy is logged)."""
    import numpy as _np

    p_line = (cand_totals >= tail_line).mean(axis=1)
    picked = list(picked)
    for th in theses:
        combo = set(th.get("players") or ())
        need = int(th.get("min") or 0)
        if not combo or need <= 0:
            continue
        def has(i):
            return combo <= {p["id"] for p in cands[i].players}
        have = sum(1 for i in picked if has(i))
        pool_extra = sorted((i for i in range(len(cands))
                             if i not in picked and has(i)),
                            key=lambda i: -p_line[i])
        while have < need and pool_extra:
            worst = min((i for i in picked if not has(i)),
                        key=lambda i: p_line[i], default=None)
            if worst is None:
                break
            picked[picked.index(worst)] = pool_extra.pop(0)
            have += 1
        if have < need:
            log.warning("thesis %s: only %d/%d entries possible",
                        sorted(combo), have, need)
    return picked


def _select_tail_qb_capped(
    cand_totals: np.ndarray, n_entries: int, line: float,
    qb_of: list, max_qbs: int,
) -> list[int]:
    """select_tail_entries with a cap on DISTINCT QBs across the selected
    set (env MAX_QBS). Once the cap is reached, only candidates reusing an
    already-selected QB stay eligible — the freed slots buy combinatorial
    depth within the kept stacks instead of a 17th stack. Mirrors the
    greedy coverage + fill of select_tail_entries."""
    cand_totals = np.asarray(cand_totals, dtype=float)
    clears = cand_totals >= line
    p_line = clears.mean(axis=1)
    mean_total = cand_totals.mean(axis=1)
    n_entries = min(n_entries, len(cand_totals))
    selected: list[int] = []
    qbs: set = set()
    covered = np.zeros(cand_totals.shape[1], dtype=bool)
    remaining = set(range(len(cand_totals)))

    def eligible():
        if len(qbs) < max_qbs:
            return remaining
        return [i for i in remaining if qb_of[i] in qbs]

    while len(selected) < n_entries:
        pool_i = eligible()
        if not pool_i:
            break
        best = max(pool_i,
                   key=lambda i: (int(np.count_nonzero(clears[i] & ~covered)),
                                  p_line[i], mean_total[i]))
        if not np.count_nonzero(clears[best] & ~covered):
            break  # coverage saturated; fill below
        selected.append(best)
        qbs.add(qb_of[best])
        covered |= clears[best]
        remaining.discard(best)
    while len(selected) < n_entries:
        pool_i = eligible()
        if not pool_i:
            break
        best = max(pool_i, key=lambda i: (p_line[i], mean_total[i]))
        selected.append(best)
        qbs.add(qb_of[best])
        remaining.discard(best)
    return selected


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
            contest=contest, sharp_fraction=sharp_fraction,
            candidate_multiple=int(_os.environ.get("CAND_MULT", "2")),
            n_boom_solves=int(_os.environ.get("N_BOOM", str(n_boom_solves))),
            # Generator-mix A/B (2026-08-01): 2025 replays show the top-4
            # game-stack generator won 0/17 weeks from ~6% of the pool
            # while dark games won 4/17 from ~11% -- N_GAMESTACK=0 +
            # N_DARKGAME up reallocates toward what actually wins.
            n_game_stacks=int(_os.environ.get("N_GAMESTACK", "4")))
    else:
        lineups = optimize_many(pool, n_lineups=n_entries, stack=stack,
                                objective_col=obj)
    if not lineups:
        log.warning("No feasible lineups for %s week %s", season, week)
        return None

    actual = slate.set_index("id")["actual"]
    lineup_scores = [float(actual.reindex([p["id"] for p in lu.players]).sum())
                     for lu in lineups]

    # model_own column present => OWN_MODEL replay: the trained ownership
    # model drives the simulated field instead of the naive softmax.
    own_vec = (slate["model_own"].to_numpy()
               if "model_own" in slate.columns and slate["model_own"].notna().all()
               else None)
    fld = field_sim.sample_field(slate, n_lineups=field_size, seed=seed,
                                 ownership=own_vec,
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
