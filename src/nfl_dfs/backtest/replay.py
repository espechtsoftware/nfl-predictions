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
) -> pd.DataFrame:
    """Project every (player, week) row of `season` with models trained on
    strictly earlier seasons. Rows carry point-in-time features, so no
    per-week retraining is needed for fidelity."""
    cm = components.train(panel, target_season=season, num_boost_round=num_boost_round)
    rows = panel[panel.season == season].reset_index(drop=True)
    if rows.empty:
        raise ValueError(f"no {season} rows in panel")
    rows = coldstart.fill_cold_start_features(rows)

    sim = simulate.simulate(cm.predict_components(rows), n_sims=n_sims, seed=seed)
    summary = sim.summary
    if widen:
        summary = calibration.apply_widen(summary, rows.position)
    keep = [c for c in ("gsis_id", "name", "season", "week", "team", "opponent",
                        "position", "game_id", "salary") if c in rows.columns]
    out = pd.concat([rows[keep], summary], axis=1)
    out["actual"] = rows["y_dk_points"].to_numpy()
    out["naive"] = rows.get("dk_points_l4")  # trailing average, the free baseline
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


def dst_slate_rows(dst: pd.DataFrame) -> pd.DataFrame:
    """RotoGuru DST rows -> slate rows. Projection is the trailing 4-week
    average of that defense's DK points (strictly prior weeks)."""
    d = dst.sort_values(["team", "season", "week"]).copy()
    d["proj"] = (
        d.groupby(["team", "season"])["actual"]
        .transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
        .fillna(DST_FALLBACK_PROJ)
    )
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
    # Tournament tilt (mirrors app._player_pool): ceiling-valued punts.
    # The chalk-fade penalty is applied per-slate below.
    from ..optimizer.lineup import PUNT_MAX_SALARY

    punt = skill.salary <= PUNT_MAX_SALARY
    skill["proj"] = skill.proj_points.where(~punt,
                                            skill[["proj_points", "proj_p90"]].max(axis=1))
    if "name" not in skill.columns:
        skill["name"] = skill.gsis_id

    dst_rows = dst_slate_rows(dst) if dst is not None else None
    slates = []
    for (season, week), grp in skill.groupby(["season", "week"]):
        cols = ["id", "name", "pos", "team", "opp", "game_id",
                "salary", "proj", "actual", "season", "week"]
        frame = grp[cols].copy()
        if dst_rows is not None:
            d = dst_rows[(dst_rows.season == season) & (dst_rows.week == week)].copy()
            d["game_id"] = d.team + "@" + d.opp
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
) -> BacktestResult:
    return engine_run(build_slates(proj, dst), contest,
                      n_entries=n_entries, field_size=field_size, seed=seed,
                      sharp_fraction=sharp_fraction, stack=stack)


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


def run(
    season: int,
    n_sims: int = 10_000,
    contest: Contest | None = None,
    n_entries: int = 40,
    field_size: int = 5_000,
    sharp_fraction: float = 0.15,
) -> None:
    panel, dst = load_panel_and_dst(season)
    proj = replay_projections(panel, season, n_sims=n_sims)
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
    best_by_week = {}
    result = run_contest_replay(proj, dst, contest,
                                n_entries=n_entries, field_size=field_size,
                                sharp_fraction=sharp_fraction, stack=stack)
    print(f"\n=== Contest replay: {season} "
          f"(field {sharp_fraction:.0%} optimizer-built) ===")
    print(result.summary())
    best = [max(w.lineup_scores) for w in result.weeks]
    if best:
        import numpy as _np

        print(f"  tail: mean best {_np.mean(best):.1f}  max {_np.max(best):.1f}  "
              f"weeks best>=237 (avg 2025 milly line): {sum(b >= 237 for b in best)}"
              f"/{len(best)}  >=194 (min line): {sum(b >= 194 for b in best)}/{len(best)}")
