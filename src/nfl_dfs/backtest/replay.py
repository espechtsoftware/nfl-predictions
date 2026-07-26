"""Season replay: what would the system have projected, and how close was it?

Trains the component models ONLY on seasons before the replay season, then
projects every week of that season through the production path (cold-start
fill -> components -> Monte Carlo) using the point-in-time feature rows.
Faithful to production: the weekly Tuesday retrain never includes the
in-progress season either (models/train_job.py trains on season < target).

Two layers, matching data availability:
- Projection replay (any season): MAE vs. the naive trailing-average
  baseline, rank correlation, p10/p90 coverage, P(20+) calibration.
- Contest replay (seasons with salaries, 2014-2021): full slates including
  RotoGuru DST rows -> optimizer -> field simulation -> ROI.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import stats

from ..models import calibration, coldstart, components, simulate
from .engine import BacktestResult, run as engine_run
from .payout import Contest

log = logging.getLogger(__name__)

DST_FALLBACK_PROJ = 6.0  # league-average DST DK points, for week-1 rows


def replay_projections(
    panel: pd.DataFrame,
    season: int,
    n_sims: int = 10_000,
    num_boost_round: int = 400,
    seed: int = 0,
    widen: bool = True,
    return_draws: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, np.ndarray]:
    """Project every (player, week) row of `season` with models trained on
    strictly earlier seasons. Rows carry point-in-time features, so no
    per-week retraining is needed for fidelity.

    return_draws=True also returns the raw correlated draw matrix
    (row-aligned with the output frame, float32) for tail-objective entry
    selection."""
    cm = components.train(panel, target_season=season, num_boost_round=num_boost_round)
    rows = panel[panel.season == season].reset_index(drop=True)
    if rows.empty:
        raise ValueError(f"no {season} rows in panel")
    rows = coldstart.fill_cold_start_features(rows)

    sim = simulate.simulate(cm.predict_components(rows), n_sims=n_sims,
                        seed=seed, game_ids=rows.get("game_id"),
                        keep_draws=return_draws)
    summary = sim.summary
    if widen:
        summary = calibration.apply_widen(summary, rows.position)
    keep = [c for c in ("gsis_id", "name", "season", "week", "team", "opponent",
                        "position", "game_id", "salary") if c in rows.columns]
    out = pd.concat([rows[keep], summary], axis=1)
    out["actual"] = rows["y_dk_points"].to_numpy()
    out["naive"] = rows.get("dk_points_l4")  # trailing average, the free baseline
    if return_draws:
        return out, sim.draws.astype(np.float32)
    return out


def replay_metrics(proj: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """(overall metrics, per-position table)."""
    err = proj.proj_points - proj.actual
    have_naive = proj.dropna(subset=["naive"])
    overall = {
        "rows": len(proj),
        "mae": float(err.abs().mean()),
        "naive_mae": float((have_naive.naive - have_naive.actual).abs().mean()),
        "coverage_p10": float((proj.actual < proj.proj_p10).mean()),
        "coverage_p90": float((proj.actual < proj.proj_p90).mean()),
        # Calibration of the GPP ceiling probability
        "mean_p20_predicted": float(proj.p_20_plus.mean()),
        "rate_20_plus_actual": float((proj.actual >= 20).mean()),
    }
    rows = []
    for pos, grp in proj.groupby("position"):
        rows.append({
            "position": pos,
            "n": len(grp),
            "mae": float((grp.proj_points - grp.actual).abs().mean()),
            "rank_corr": float(stats.spearmanr(grp.proj_points, grp.actual).statistic),
            "coverage_p10": float((grp.actual < grp.proj_p10).mean()),
            "coverage_p90": float((grp.actual < grp.proj_p90).mean()),
        })
    return overall, pd.DataFrame(rows).set_index("position")


def dst_slate_rows(dst: pd.DataFrame,
                   qb_starts: pd.DataFrame | None = None,
                   vegas: pd.DataFrame | None = None) -> pd.DataFrame:
    """RotoGuru DST rows -> slate rows.

    Projection tiers (best available wins): Vegas-first model (opponent
    implied total + trailing form + opposing-QB experience — see
    inference/dst_projections.model_projection) > trailing form + raw
    QB-experience adjustment > trailing form alone. `vegas` columns:
    season, week, team, opp_implied."""
    d = dst.sort_values(["team", "season", "week"]).copy()
    d["proj"] = (
        d.groupby(["team", "season"])["actual"]
        .transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
        .fillna(DST_FALLBACK_PROJ)
    )
    starts = pd.Series(pd.NA, index=d.index)
    if qb_starts is not None and not qb_starts.empty:
        d = d.merge(qb_starts.rename(columns={"team": "opp"}),
                    on=["season", "week", "opp"], how="left")
        starts = d.pop("prior_starts")
    if vegas is not None and not vegas.empty:
        from ..inference.dst_projections import model_projection

        d = d.merge(vegas, on=["season", "week", "team"], how="left")
        d["proj"] = model_projection(d.pop("opp_implied"), d["proj"], starts)
    elif starts.notna().any():
        from ..inference.qb_experience import adjustment

        d["proj"] = d["proj"] + adjustment(starts)
    d["id"] = "DST_" + d.team
    d["name"] = d.team + " DST"
    d["pos"] = "DST"
    return d


def build_slates(proj: pd.DataFrame, dst: pd.DataFrame | None) -> list[pd.DataFrame]:
    """One engine-ready slate per week: skill rows from the replay (dropping
    the few without a salary) plus DST rows when provided."""
    skill = proj.dropna(subset=["salary"]).copy()
    dropped = len(proj) - len(skill)
    if dropped:
        log.info("build_slates: dropped %d skill rows without salary", dropped)
    skill["id"] = skill.gsis_id
    skill["pos"] = skill.position
    skill["opp"] = skill.opponent
    # Row position in the replay_projections frame == row in its draw
    # matrix; -1 (DST) means "no draws, use the static projection".
    skill["draw_idx"] = skill.index.to_numpy()
    # Tournament tilt (mirrors app._player_pool): ceiling-valued punts.
    # The chalk-fade penalty is applied per-slate below.
    from ..optimizer.lineup import PUNT_MAX_SALARY

    punt = skill.salary <= PUNT_MAX_SALARY
    skill["proj"] = skill.proj_points.where(~punt,
                                            skill[["proj_points", "proj_p90"]].max(axis=1))
    if "name" not in skill.columns:
        skill["name"] = skill.gsis_id

    qb_starts, vegas = None, None
    if dst is not None and len(dst):
        try:
            from ..inference.qb_experience import starter_prior_starts

            qb_starts = starter_prior_starts()
        except Exception:
            log.exception("QB-experience data unavailable; DST projections "
                          "without the opponent adjustment")
        try:
            from ..bq import query_df
            from ..config import settings

            vegas = query_df(
                f"""
                SELECT season, week, home_team AS team,
                       (total_line - spread_line)/2 AS opp_implied
                FROM `{settings.raw}.schedules`
                WHERE game_type='REG' AND total_line IS NOT NULL
                UNION ALL
                SELECT season, week, away_team AS team,
                       (total_line + spread_line)/2 AS opp_implied
                FROM `{settings.raw}.schedules`
                WHERE game_type='REG' AND total_line IS NOT NULL
                """
            )
        except Exception:
            log.exception("Vegas lines unavailable; DST projections "
                          "without the implied-total model")
    dst_rows = (dst_slate_rows(dst, qb_starts, vegas)
                if dst is not None else None)
    slates = []
    for (season, week), grp in skill.groupby(["season", "week"]):
        cols = ["id", "name", "pos", "team", "opp", "game_id",
                "salary", "proj", "actual", "season", "week", "draw_idx"]
        frame = grp[cols].copy()
        if dst_rows is not None:
            d = dst_rows[(dst_rows.season == season) & (dst_rows.week == week)].copy()
            d["game_id"] = d.team + "@" + d.opp
            d["draw_idx"] = -1
            frame = pd.concat([frame, d[cols]], ignore_index=True)
        # RotoGuru DST rows occasionally lack salary or points; a single NaN
        # poisons the field sampler's ownership softmax.
        n0 = len(frame)
        frame = frame.dropna(subset=["salary", "proj", "actual"])
        frame = frame[frame.salary > 0]  # RotoGuru's missing-salary sentinel
        if len(frame) < n0:
            log.info("slate %s wk %s: dropped %d rows with missing salary/proj/actual",
                     season, week, n0 - len(frame))
        frame["salary"] = frame.salary.astype(int)
        # Our entries optimize the leverage-tilted objective; the field
        # simulation keeps the untilted proj — the field is chalky by
        # definition, and that asymmetry IS the leverage.
        from ..optimizer.lineup import LEVERAGE_PENALTY
        from .field import naive_ownership

        frame = frame.reset_index(drop=True)
        frame["proj_tourney"] = frame.proj - LEVERAGE_PENALTY * naive_ownership(frame)
        # A/B lever (env DST_PUNT_BONUS, off by default): 2023-24 Milly
        # winners used a cheap DST as their punt in 29/31 weeks (addendum
        # 7). The bonus tilts OUR objective toward sub-punt-cap DSTs;
        # the field's proj is untouched.
        import os

        dst_bonus = float(os.environ.get("DST_PUNT_BONUS", "0") or 0)
        if dst_bonus:
            from ..optimizer.lineup import PUNT_MAX_SALARY as _punt_cap

            cheap_dst = (frame.pos == "DST") & (frame.salary <= _punt_cap)
            frame.loc[cheap_dst, "proj_tourney"] += dst_bonus
        slates.append(frame)
    return slates


def run_contest_replay(
    proj: pd.DataFrame,
    dst: pd.DataFrame,
    contest: Contest,
    n_entries: int = 20,
    field_size: int = 5_000,
    seed: int = 42,
    sharp_fraction: float = 0.15,
    stack=None,
    draws: np.ndarray | None = None,
    tail_line: float | None = None,
    n_boom_solves: int = 40,
) -> BacktestResult:
    return engine_run(build_slates(proj, dst), contest,
                      n_entries=n_entries, field_size=field_size, seed=seed,
                      sharp_fraction=sharp_fraction, stack=stack,
                      draws=draws, tail_line=tail_line,
                      n_boom_solves=n_boom_solves)


# Warehouse entry point ------------------------------------------------------


def load_panel_and_dst(season: int):
    from ..bq import query_df
    from ..config import settings

    panel = query_df(
        f"""
        SELECT t.*, i.name
        FROM `{settings.features}.player_week_training` t
        LEFT JOIN `{settings.raw}.player_ids` i USING (gsis_id)
        WHERE t.season BETWEEN {settings.train_first_season} AND {season}
        """
    )
    dst = query_df(
        f"""
        SELECT season, week, team_abbr AS team, opponent AS opp,
               salary, dk_points AS actual
        FROM `{settings.raw}.dk_salaries_historical`
        WHERE position = 'Def' AND season = {season}
        """
    )
    return panel, dst


TAIL_LINE_DEFAULT = 194.0  # min 2025 Milly-winning line; 0 disables


def run(
    season: int,
    n_sims: int = 10_000,
    contest: Contest | None = None,
    n_entries: int = 40,
    field_size: int = 5_000,
    sharp_fraction: float = 0.15,
    tail_line: float | None = None,
) -> None:
    panel, dst = load_panel_and_dst(season)
    proj, draws = replay_projections(panel, season, n_sims=n_sims,
                                     return_draws=True)
    overall, by_pos = replay_metrics(proj)

    print(f"\n=== Projection replay: {season} "
          f"(trained on {int(panel.season.min())}-{season - 1}) ===")
    for k, v in overall.items():
        print(f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}")
    print(by_pos.round(3).to_string())

    if dst.empty:
        print(f"\nNo {season} DST/salary data (see README data deficiency log) "
              f"— skipping contest replay.")
        return
    if contest is None:
        from .payout import gpp

        contest = gpp()
    # QB stacking validated on both imputed-2025 and real-2021 replays
    # (reports/2026-07-25-system-study.md addendum); mean objective beat a
    # p90 objective on real salaries, so stacking is the only GPP default.
    from ..optimizer.lineup import StackRules

    stack = (StackRules(qb_stack_min=2, bring_back_min=1)
             if "gpp" in contest.name else None)
    # Tail-objective selection (issue #5) is a GPP concept only; double-ups
    # want the mean objective. tail_line=0 disables explicitly.
    if tail_line is None and "gpp" in contest.name:
        tail_line = TAIL_LINE_DEFAULT
    use_tail = bool(tail_line)
    if use_tail:
        print(f"\n  entry selection: P(best >= {tail_line:.0f}) greedy "
              f"coverage over correlated draws")
    best_by_week = {}
    result = run_contest_replay(proj, dst, contest,
                                n_entries=n_entries, field_size=field_size,
                                sharp_fraction=sharp_fraction, stack=stack,
                                draws=draws if use_tail else None,
                                tail_line=tail_line if use_tail else None)
    print(f"\n=== Contest replay: {season} "
          f"(field {sharp_fraction:.0%} optimizer-built) ===")
    print(result.summary())
    best = [max(w.lineup_scores) for w in result.weeks]
    if best:
        import numpy as _np

        print(f"  tail: mean best {_np.mean(best):.1f}  max {_np.max(best):.1f}  "
              f"weeks best>=237 (avg 2025 milly line): {sum(b >= 237 for b in best)}"
              f"/{len(best)}  >=194 (min line): {sum(b >= 194 for b in best)}/{len(best)}")
        _entries_to_line(result.weeks)


def _entries_to_line(weeks, lines=(194, 237)) -> None:
    """Order-statistics extrapolation: from each week's entry-score
    distribution (normal fit to the generated entries), how many entries N
    would give a 50% chance that the best of N clears a Milly line?
    N = ln(0.5)/ln(P(one entry < line)). Two opposing biases roughly cancel:
    a normal fit thins the right tail (overstates N for correlated stacks),
    while extrapolating from the optimizer's top picks assumes entry quality
    doesn't degrade with N (understates it). Read as order-of-magnitude."""
    import math
    from statistics import NormalDist

    import numpy as _np

    print("  entries-to-line (N for 50% chance best-of-N >= line):")
    print(f"    {'week':>4} {'mu':>6} {'sd':>5} {'best':>6} "
          + " ".join(f"N@{ln}" for ln in lines))
    med = {ln: [] for ln in lines}
    for w in weeks:
        s = _np.asarray(w.lineup_scores, dtype=float)
        if len(s) < 5 or s.std(ddof=1) == 0:
            continue
        mu, sd = s.mean(), s.std(ddof=1)
        ns = []
        for ln in lines:
            p_under = NormalDist(mu, sd).cdf(ln)
            n = math.inf if p_under >= 1.0 else (
                1.0 if p_under <= 0.5 else math.log(0.5) / math.log(p_under))
            med[ln].append(n)
            ns.append("inf" if n == math.inf else f"{n:.0f}")
        print(f"    {w.week:>4} {mu:6.1f} {sd:5.1f} {max(s):6.1f} "
              + " ".join(f"{x:>7}" for x in ns))
    for ln in lines:
        if med[ln]:
            m = sorted(med[ln])[len(med[ln]) // 2]
            within = sum(n <= 150_000 for n in med[ln])
            print(f"    line {ln}: median N {'inf' if m == math.inf else f'{m:,.0f}'}"
                  f"  weeks reachable within a 150k-entry field: "
                  f"{within}/{len(med[ln])}")
