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
import os

import numpy as np
import pandas as pd
from scipy import stats

from ..models import calibration, coldstart, components, simulate
from .engine import BacktestResult, run as engine_run
from .payout import Contest

log = logging.getLogger(__name__)

DST_FALLBACK_PROJ = 6.0  # league-average DST DK points, for week-1 rows


def own_mode() -> str:
    """OWN_MODEL env, normalized (2026-08-04 audit): default "fade";
    falsy spellings ("", "0", "off", "false", "no", "none") DISABLE —
    before this, OWN_MODEL=0 silently enabled the strongest mode (full
    model-own field, deliberately not adopted) because any non-"fade"
    truthy string flips the model into the field sampler."""
    v = os.environ.get("OWN_MODEL", "fade").strip().lower()
    return "" if v in ("", "0", "off", "false", "no", "none") else v


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

    # Big-play mixture rate (env BIGPLAY=<scale>): expected house-calls
    # per game from the point-in-time deep-target profile. At scale 1 a
    # 3-deep-targets/wk receiver draws ~0.09 long-TD events/game.
    bigplay = None
    _bp = float(os.environ.get("BIGPLAY", "0") or 0)
    if _bp and "deep_targets_l4" in rows.columns:
        bigplay = 0.03 * _bp * pd.to_numeric(
            rows.deep_targets_l4, errors="coerce").fillna(0.0)
    sim = simulate.simulate(cm.predict_components(rows), n_sims=n_sims,
                        seed=seed, game_ids=rows.get("game_id"),
                        team_ids=rows.get("team"),
                        game_totals=rows.get("game_total"),
                        bigplay_rate=bigplay,
                        keep_draws=return_draws)
    summary = sim.summary
    if widen:
        summary = calibration.apply_widen(summary, rows.position)
    # A/B lever (env SIM_WIDEN_DRAWS): the fitted widen factors above
    # only ever stretched the SUMMARY quantiles — the draws that drive
    # lineup optimization, boom solves, and tail-coverage selection have
    # always been the raw (known-too-narrow: QB 1.5x, RB 1.45x per the
    # calibration's own fit) composition. "fitted" applies DEFAULT_WIDEN
    # to the draws mean-preservingly; or pass explicit "WR:1.3,QB:1.5".
    draws_out = (apply_draw_shape(sim.draws, rows.position, seed,
                                  keys=rows[["season", "week", "gsis_id"]])
                 if return_draws else sim.draws)
    keep = [c for c in ("gsis_id", "name", "season", "week", "team", "opponent",
                        "position", "game_id", "salary") if c in rows.columns]
    out = pd.concat([rows[keep], summary], axis=1)
    out["actual"] = rows["y_dk_points"].to_numpy()
    out["naive"] = rows.get("dk_points_l4")  # trailing average, the free baseline
    if return_draws:
        return out, draws_out.astype(np.float32)
    return out


def apply_draw_shape(draws: np.ndarray, positions: pd.Series,
                     seed: int | None,
                     keys: pd.DataFrame | None = None) -> np.ndarray:
    """ADOPTED DEFAULTS (Addendum 40, combo "EW" — 24/107 tails vs 16
    same-build control, largest gain in program history): fitted draw
    widening + empirically-shaped marginals, composed, mean-preserving.
    Shared by replays AND the live sim-mode path so what was validated
    is exactly what fires on Sundays. Env overrides: SIM_WIDEN_DRAWS=off
    or an explicit "WR:1.3,..." spec; EMP_MARGINALS=0 disables."""
    out = draws
    widen_spec = os.environ.get("SIM_WIDEN_DRAWS", "fitted")
    if widen_spec.lower() not in ("off", "0", ""):
        out = _widen_draws(out, positions, widen_spec)
    shaped = None
    # TABPFN_MARGINALS ADOPTED default-on 2026-08-04 (Addendum 50):
    # +6 tails alone (24 vs 18), STPFN stack = best mean-best of the
    # panel (179.5) at equal tails. Requires the tabpfn_projections
    # cache (GPU job tabpfn-gen, ~$0.05/wk); missing cache falls back
    # to empirical marginals below. "0"/"" disables.
    if (os.environ.get("TABPFN_MARGINALS", "1") not in ("0", "")
            and keys is not None):
        shaped = _tabpfn_marginals(out, keys)
    if shaped is not None:
        out = shaped
    elif os.environ.get("EMP_MARGINALS", "1") not in ("0", ""):
        out = _empirical_marginals(
            out, positions,
            np.random.default_rng(0 if seed is None else seed + 7))
    # A/B lever (env SHAPE_MIX, off by default = 1.0): apply the shaping
    # to only the first fraction f of sims, leaving the rest RAW — the
    # EW-vs-PB2 diff showed 15 weeks converted but 9 regressed (each
    # world-model sees booms the other misses); mixed worlds let the
    # coverage selector hedge across both regimes.
    mix = float(os.environ.get("SHAPE_MIX", "1") or 1)
    if mix <= 0.0:
        return draws  # 0 = all-raw (was returning fully-shaped — audit)
    if mix < 1.0:
        k = int(mix * draws.shape[1])
        out = np.concatenate([out[:, :k], draws[:, k:]], axis=1)
    return out


def _tabpfn_marginals(draws: np.ndarray, keys: pd.DataFrame) -> np.ndarray:
    """TABPFN_MARGINALS=1 (A/B, off by default; Addenda 43/46): reshape
    each player's marginal onto the TabPFN-v2 walk-forward quantiles
    cached in features.tabpfn_projections (generated on GPU, context =
    strictly-prior seasons). Same rank-reordering mechanism as
    _empirical_marginals — the correlation copula survives untouched —
    but the target distribution is PER-PLAYER, not a (pos, tier) family.
    TabPFN arrives calibrated where our quantiles under-cover (three
    independent confirmations). Rows without a cached prediction keep
    their original draws. Tails extrapolate linearly beyond q01/q99."""
    from ..bq import query_df
    from ..config import settings

    season = int(keys.season.iloc[0])
    q = query_df(f"SELECT * FROM `{settings.features}.tabpfn_projections` "
                 f"WHERE season = {season}")
    if q.empty:
        log.warning("TABPFN_MARGINALS on but no cached rows for season %s "
                    "— falling back to empirical marginals", season)
        return None
    qcols = sorted(c for c in q.columns if c.startswith("q") and c[1:].isdigit())
    levels = np.array([int(c[1:]) / 100 for c in qcols])
    q = q.set_index(["week", "gsis_id"])
    out = draws.copy()
    n = draws.shape[1]
    hit = 0
    for i in range(len(keys)):
        k = (int(keys.week.iloc[i]), keys.gsis_id.iloc[i])
        try:
            qv = q.loc[k, qcols].to_numpy(dtype=float)
        except KeyError:
            continue
        if qv.ndim > 1:  # duplicate cache rows; take the first
            qv = qv[0]
        row = draws[i]
        ranks = row.argsort().argsort() / max(n - 1, 1)
        y = np.interp(ranks, levels, qv)
        lo, hi = ranks < levels[0], ranks > levels[-1]
        y[lo] = qv[0] + (ranks[lo] - levels[0]) * (qv[1] - qv[0]) / (
            levels[1] - levels[0])
        y[hi] = qv[-1] + (ranks[hi] - levels[-1]) * (qv[-1] - qv[-2]) / (
            levels[-1] - levels[-2])
        out[i] = np.maximum(y, 0.0)
        hit += 1
    log.info("tabpfn marginals: %d/%d rows mapped", hit, len(keys))
    return out


def _empirical_marginals(draws: np.ndarray, positions: pd.Series,
                         rng: np.random.Generator) -> np.ndarray:
    """Reshape each player's marginal to the empirically-fitted family
    for (position, projection tier) — models/emp_marginals.py — while
    preserving BOTH our correlation structure (rank reordering: the
    possession-engine copula survives byte-for-byte) and our first two
    moments (affine match to the row's own mean/std). Only skew and
    kurtosis change: RB/WR high tiers go weibull-fat, TE lognormal at
    the bottom, QB skew-normal. Env EMP_MARGINALS=1."""
    from scipy import stats as _st

    from ..models.emp_marginals import ROWS

    # EMP_POS (A/B, default all): comma list of positions to reshape —
    # the EW-book sweep found the TE slot REGRESSED under the empirical
    # TE family (13.1 actual vs winners' 21.5), so a no-TE arm exists.
    allow = {p.strip().upper() for p in
             os.environ.get("EMP_POS", "").split(",") if p.strip()}
    by_pos: dict = {}
    for r in ROWS:
        if allow and r["pos"] not in allow:
            continue
        by_pos.setdefault(r["pos"], []).append(r)

    def family_sample(r, n):
        d = r["dist"]
        if d == "exgaussian":
            return _st.exponnorm.rvs(K=r["tau"] / r["sigma"], loc=r["mu"],
                                     scale=r["sigma"], size=n, random_state=rng)
        if d == "skew_normal":
            return _st.skewnorm.rvs(a=r["alpha"], loc=r["loc"],
                                    scale=r["scale"], size=n, random_state=rng)
        if d == "weibull":
            return _st.weibull_min.rvs(c=r.get("c", r.get("a", 1.0)),
                                       scale=r["scale"], size=n, random_state=rng)
        if d == "lognormal":
            return _st.lognorm.rvs(s=r["sigma"], scale=np.exp(r["mu"]),
                                   size=n, random_state=rng)
        if d == "generalized_gamma":
            return _st.gengamma.rvs(a=r["a"], c=r.get("c", r.get("d", 1.0)),
                                    scale=r.get("scale", r.get("beta", 1.0)),
                                    size=n, random_state=rng)
        # scale/loc are irrelevant post-affine-match; only SHAPE params
        # matter. Some source rows store rate (beta) instead of scale.
        gscale = r.get("scale", 1.0 / r["beta"] if r.get("beta") else 1.0)
        if d == "shifted_gamma":
            return r.get("shift", 0.0) + _st.gamma.rvs(
                a=r["alpha"], scale=gscale, size=n, random_state=rng)
        if d == "gamma":
            return _st.gamma.rvs(a=r["alpha"], scale=gscale, size=n,
                                 random_state=rng)
        raise ValueError(d)

    out = draws.copy()
    n_sims = draws.shape[1]
    pos_arr = positions.astype(str).str.upper().to_numpy()
    for i in range(draws.shape[0]):
        rows_p = by_pos.get(pos_arr[i])
        if not rows_p:
            continue
        mu, sd = float(draws[i].mean()), float(draws[i].std())
        if sd < 1e-6:
            continue
        r = min(rows_p, key=lambda t: abs((t["lo"] + t["hi"]) / 2 - mu))
        s = family_sample(r, n_sims)
        s_sd = s.std()
        if s_sd < 1e-9:
            continue
        s = (s - s.mean()) * (sd / s_sd) + mu  # affine: our mean & std
        # rank reorder: our copula, their shape
        order = np.argsort(np.argsort(draws[i]))
        out[i] = np.sort(s)[order]
    return out


def _widen_draws(draws: np.ndarray, positions: pd.Series, spec: str) -> np.ndarray:
    """Mean-preserving per-position spread widening of the draw matrix
    (draws[i, k] = player i's points in sim k). E[row] is exactly
    unchanged; row std scales by the position factor. spec: "fitted"
    (calibration.DEFAULT_WIDEN) or "WR:1.3,QB:1.5"."""
    if spec.strip().lower() == "fitted":
        factors = dict(calibration.DEFAULT_WIDEN)
    else:
        factors = {k.strip().upper(): float(v) for k, _, v in
                   (p.partition(":") for p in spec.split(","))}
    w = positions.map(lambda p: factors.get(str(p).upper(), 1.0)) \
                 .to_numpy(dtype=np.float64)[:, None]
    mu = draws.mean(axis=1, keepdims=True)
    return mu + (draws - mu) * w


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
        # One row per (season, week, team) or the merge fans out duplicate
        # DST rows (2023: a mid-week QB change flagged two starters, which
        # crashed the engine's unique-id reindex).
        qb_starts = qb_starts.drop_duplicates(subset=["season", "week", "team"])
        d = d.merge(qb_starts.rename(columns={"team": "opp"}),
                    on=["season", "week", "opp"], how="left")
        starts = d.pop("prior_starts")
    if vegas is not None and not vegas.empty:
        vegas = vegas.drop_duplicates(subset=["season", "week", "team"])
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


def _punt_boom_from_signals(df: pd.DataFrame) -> set[tuple]:
    """(gsis_id, season, week) keys matching a winning-punt archetype
    (Addendum 24/36): cheap starting TEs (depth_rank 1 — DK's TE pricing
    compression puts real starters at min price), newly-promoted rank-1s
    (the Gadsden case: rank 2 -> 1), and injury-cascade beneficiaries
    (top-decile vacated share that week). Salary gating happens at
    application time; these are role signals only.

    df columns: gsis_id, season, week, position, depth_rank, prev_rank,
    vac (max of vacated target/carry share). All point-in-time."""
    te_starter = (df.position == "TE") & (df.depth_rank == 1)
    promoted = (df.depth_rank == 1) & (df.prev_rank >= 2)
    vac_pct = df.groupby(["season", "week"]).vac.rank(pct=True)
    cascade = (df.vac > 0) & (vac_pct >= 0.90)
    hit = df[te_starter | promoted | cascade]
    return {(r.gsis_id, int(r.season), int(r.week)) for r in hit.itertuples()}


def _punt_boom_flags(seasons: list) -> set[tuple]:
    from ..bq import query_df
    from ..config import settings

    yrs = ",".join(str(int(s)) for s in seasons)
    df = query_df(f"""
        SELECT gsis_id, season, week, position, depth_rank,
               LAG(depth_rank) OVER (
                   PARTITION BY gsis_id, season ORDER BY week) prev_rank,
               GREATEST(COALESCE(team_vacated_target_share, 0),
                        COALESCE(team_vacated_carry_share, 0)) vac
        FROM `{settings.features}.player_week_training`
        WHERE season IN ({yrs})""")
    return _punt_boom_from_signals(df)


def punt_boom_flags_live(season: int, week: int) -> set[tuple]:
    """Live-inference variant: the upcoming week's rows live in
    player_week_inference (training rows only exist for played weeks), so
    the rank-2->1 transition needs history unioned with the current week."""
    from ..bq import query_df
    from ..config import settings

    sig = ("gsis_id, season, week, position, depth_rank, "
           "team_vacated_target_share, team_vacated_carry_share")
    df = query_df(f"""
        WITH hist AS (
          SELECT {sig} FROM `{settings.features}.player_week_training`
          WHERE season = {int(season)} AND week < {int(week)}
          UNION ALL
          SELECT {sig} FROM `{settings.features}.player_week_inference`
          WHERE season = {int(season)} AND week = {int(week)}
        )
        SELECT * FROM (
          SELECT gsis_id, season, week, position, depth_rank,
                 LAG(depth_rank) OVER (
                     PARTITION BY gsis_id, season ORDER BY week) prev_rank,
                 GREATEST(COALESCE(team_vacated_target_share, 0),
                          COALESCE(team_vacated_carry_share, 0)) vac
          FROM hist)
        WHERE week = {int(week)}""")
    return _punt_boom_from_signals(df)


def _wr_boom_flags(seasons: list) -> set[tuple]:
    """(gsis_id, season, week) for WRs with a boom-SHAPED role: top-decile
    deep-target volume among that week's WRs (point-in-time l4 window).
    Real Milly winners' WR slots average 29.9 pts vs our 19.9 (Addendum
    38), and the eruptions are deep threats at punt/mid prices. Salary
    gating happens at application (PUNT_BOOM_WR / WR_BOOM envs)."""
    from ..bq import query_df
    from ..config import settings

    yrs = ",".join(str(int(s)) for s in seasons)
    df = query_df(f"""
        SELECT gsis_id, season, week, deep_targets_l4
        FROM `{settings.features}.player_week_training`
        WHERE season IN ({yrs}) AND position = 'WR'
          AND deep_targets_l4 IS NOT NULL AND deep_targets_l4 > 0""")
    pct = df.groupby(["season", "week"]).deep_targets_l4.rank(pct=True)
    hit = df[pct >= 0.90]
    return {(r.gsis_id, int(r.season), int(r.week)) for r in hit.itertuples()}


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
    # A/B lever (env PUNT_VALUE=tail, off by default): value punts at the
    # top-quartile MEAN (proj_tail) instead of the p90 point — ETR's
    # ceiling definition; more stable and it sees the far tail p90 cuts
    # off. Default stays p90 (the validated shipping rule).
    ceil_col = ("proj_tail" if os.environ.get("PUNT_VALUE") == "tail"
                and "proj_tail" in skill.columns else "proj_p90")
    skill["proj"] = skill.proj_points.where(~punt,
                                            skill[["proj_points", ceil_col]].max(axis=1))
    import os as _os2

    _k = float(_os2.environ.get("ALT_CEIL", "0") or 0)
    if _k and "ceil_spread" in skill.columns:
        # Market-implied ceiling room boosts modest-salary objectives
        mod = skill.salary <= 6500
        skill.loc[mod, "proj"] += _k * pd.to_numeric(
            skill.loc[mod, "ceil_spread"], errors="coerce").fillna(0)
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
    own_booster = None
    # OWN_MODEL default "fade" ADOPTED 2026-08-04 (QF arm): model own in
    # the chalk fade, naive field kept as the stable yardstick. "" disables.
    if own_mode():
        replay_season = int(skill.season.max())
        own_booster = _ownership_booster(replay_season)
    # ADOPTED at +2 (Addendum 37): the only lever to beat the 49f8dac
    # baseline on every metric at once (tails 16 vs 15, both >=237 weeks
    # kept, median and ROI up). Dose-response was clean — 4 and 8
    # overwhelm the p90 punt valuation and destroy the slate-breakers.
    punt_boom = float(os.environ.get("PUNT_BOOM", "2") or 0)
    boom_keys: set = set()
    if punt_boom:
        try:
            boom_keys = _punt_boom_flags(sorted(skill.season.unique()))
            log.info("punt-boom: %d flagged player-weeks", len(boom_keys))
        except Exception:
            log.exception("punt-boom signals unavailable; lever inert")
            punt_boom = 0.0
    # A/B levers (off by default — separate gates so the ADOPTED punt
    # boom's behavior never changes silently): PUNT_BOOM_WR=1 adds the
    # deep-threat-WR archetype to the punt-boom flag set; WR_BOOM=<pts>
    # boosts OUR objective for boom-shaped MID-band ($4-6.5k) WRs, the
    # band where real winners' WR eruptions live.
    wr_boom = float(os.environ.get("WR_BOOM", "0") or 0)
    wr_keys: set = set()
    if wr_boom or os.environ.get("PUNT_BOOM_WR"):
        try:
            wr_keys = _wr_boom_flags(sorted(skill.season.unique()))
            log.info("wr-boom: %d flagged player-weeks", len(wr_keys))
            if os.environ.get("PUNT_BOOM_WR") and punt_boom:
                boom_keys = boom_keys | wr_keys
        except Exception:
            log.exception("wr-boom signals unavailable; lever inert")
            wr_boom = 0.0
    slates = []
    for (season, week), grp in skill.groupby(["season", "week"]):
        cols = ["id", "name", "pos", "team", "opp", "game_id",
                "salary", "proj", "actual", "season", "week", "draw_idx"]
        if "consensus_div" in grp.columns:  # DIV_TILT lever input
            cols.append("consensus_div")
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
        # Engine requires unique ids (actual.reindex, draw alignment);
        # guard against upstream merge fan-outs rather than crash mid-run.
        dup = frame.id.duplicated()
        if dup.any():
            log.warning("slate %s wk %s: dropping %d duplicate-id rows",
                        season, week, int(dup.sum()))
            frame = frame[~dup]
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
        # A/B lever (env LEV_POS_WEIGHTS, e.g. "RB:0.5,QB:0.8,WR:1.2,TE:1.1,
        # DST:2.0", off by default = uniform): position-weighted chalk fade.
        # Levitan's 452-top-10 Milly study: ownership-vs-points corr by
        # position is RB .55 / QB .53 / TE .48 / WR .47 / DST .21 -- the
        # crowd is nearly RIGHT about RB chalk (fading it is expensive) and
        # nearly uninformed about DST (fading it is cheap leverage).

        lev_w = 1.0
        spec = os.environ.get("LEV_POS_WEIGHTS", "")
        if spec:
            wmap = {k.strip().upper(): float(v) for k, _, v in
                    (part.partition(":") for part in spec.split(","))}
            lev_w = frame.pos.str.upper().map(wmap).fillna(1.0).to_numpy()
        # LEV_PENALTY env (assumption validation): the 25.0 constant was
        # hand-set pre-A/B-era; 0 tests whether the chalk fade helps at all.
        lev_pen = float(os.environ.get("LEV_PENALTY", LEVERAGE_PENALTY))
        # OWN_MODEL=1 (2026-08-01, the LineStar-ownership capstone): swap
        # the naive value/salary softmax for the trained ownership model
        # (walk-forward fit, seasons < replay season) in BOTH the chalk
        # fade here and the field sampler (engine passes frame.model_own
        # through when present). OOS 2025: model corr .727 vs naive .548.
        own = None
        if own_mode() and own_booster is not None:
            own = _model_ownership(own_booster, frame)
            # OWN_MODEL=fade (2026-08-03 graveyard review): the original
            # rejection conflated decision input with measurement — the
            # model went into the fade AND the field, and the "median
            # doubled" verdict partly reflects a sharper yardstick, not
            # worse lineups. fade-only keeps the naive field (stable
            # measurement) while the fade uses the better own estimate.
            if own_mode() not in ("fade", ""):
                frame["model_own"] = own
        if own is None:
            own = naive_ownership(frame)
        # A/B lever (env LEV_SHAPE=sqrt, off by default = linear): a
        # LINEAR chalk penalty keeps paying all the way to the 0.1%-owned
        # fringe, pulling entries toward implausibly low-owned players
        # (pangadfs's OwnershipPenalty argues the same). sqrt gives
        # diminishing reward for going ever more contrarian; rescaled to
        # the same slate-mean penalty so only the SHAPE changes.
        own_eff = own
        if os.environ.get("LEV_SHAPE") == "sqrt":
            root = np.sqrt(np.maximum(own, 0.0))
            m = root.mean()
            if m > 1e-12:
                own_eff = root * (np.mean(own) / m)
        frame["proj_tourney"] = frame.proj - lev_pen * lev_w * own_eff
        # A/B lever (env DIV_TILT, off by default; external review 3.2):
        # tilt toward players where OUR model diverges from the prop
        # market — Addendum 45 measured disagreement predictive in BOTH
        # directions, so conviction (positive div) earns objective
        # points. Dose = DIV_TILT * clip(div, -3, 3).
        _dt = float(os.environ.get("DIV_TILT", "0") or 0)
        if _dt and "consensus_div" in frame.columns:
            frame["proj_tourney"] += _dt * frame.consensus_div.fillna(
                0.0).clip(-3.0, 3.0)
        # A/B lever (env DST_PUNT_BONUS, off by default): 2023-24 Milly
        # winners used a cheap DST as their punt in 29/31 weeks (addendum
        # 7). The bonus tilts OUR objective toward sub-punt-cap DSTs;
        # the field's proj is untouched.

        dst_bonus = float(os.environ.get("DST_PUNT_BONUS", "0") or 0)
        if dst_bonus:
            from ..optimizer.lineup import PUNT_MAX_SALARY as _punt_cap

            cheap_dst = (frame.pos == "DST") & (frame.salary <= _punt_cap)
            frame.loc[cheap_dst, "proj_tourney"] += dst_bonus
        # A/B lever (env PUNT_BOOM, off by default): Addendum 36 found a
        # perfect punt swap crosses 194 in 16/28 near-miss weeks while
        # our punts average 7.3 with 45% duds. Boost OUR objective for
        # punt-priced skill players matching a winning-punt archetype
        # (see _punt_boom_from_signals); the field's proj is untouched.
        if punt_boom and boom_keys:
            from ..optimizer.lineup import PUNT_MAX_SALARY as _pcap2

            keys = list(zip(frame.id, frame.season.astype(int),
                            frame.week.astype(int)))
            boom = pd.Series([k in boom_keys for k in keys],
                             index=frame.index)
            boom &= (frame.salary <= _pcap2) & (frame.pos != "DST")
            frame.loc[boom, "proj_tourney"] += punt_boom
        # A/B lever (env PUNT_SLOPE, off by default): winners' punts
        # cluster $2.9-3.9k; the hard $3,500 threshold failed its
        # rebuilt-data confirmation (a cliff only binds in the sliver).
        # This is the SHAPED version: within the punt band, cheaper
        # punts get a boost proportional to distance below $4k.
        slope = float(os.environ.get("PUNT_SLOPE", "0") or 0)
        if slope:
            from ..optimizer.lineup import PUNT_MAX_SALARY as _pcap3

            pmask = (frame.salary <= _pcap3) & (frame.pos != "DST")
            frame.loc[pmask, "proj_tourney"] += (
                slope * (_pcap3 - frame.loc[pmask, "salary"]) / 1000.0)
        # A/B lever (env PUNT_STRICT, off by default): the CONDITIONAL
        # threshold — unflagged punts must be <=$3,500; boom-archetype
        # punts stay eligible to $4k (cheap punts are min-priced
        # STARTERS; an expensive punt must earn its price with a role
        # signal). Consumed by the optimizer's punt constraint via the
        # punt_elig flag when PUNT_STRICT is set.
        if os.environ.get("PUNT_STRICT") and punt_boom and boom_keys:
            keys2 = list(zip(frame.id, frame.season.astype(int),
                             frame.week.astype(int)))
            boom2 = pd.Series([k in boom_keys for k in keys2],
                              index=frame.index)
            frame["punt_elig"] = (
                (frame.salary <= 3500)
                | (boom2 & (frame.salary <= 4000))) & (frame.pos != "DST")
        if wr_boom and wr_keys:
            keys = list(zip(frame.id, frame.season.astype(int),
                            frame.week.astype(int)))
            wb = pd.Series([k in wr_keys for k in keys], index=frame.index)
            wb &= (frame.pos == "WR") & frame.salary.between(4000, 6500)
            frame.loc[wb, "proj_tourney"] += wr_boom
        # Ownership-shape flag for the MIN_LOWOWN optimizer constraint
        # (winner spec, Addendum 38: ~2 sub-5%-owned players per winning
        # lineup). Expected ownership ~= within-position weight x roster
        # slots for that position.
        slots = {"QB": 1.0, "RB": 2.5, "WR": 3.5, "TE": 1.2, "DST": 1.0}
        frame["low_own"] = (own * frame.pos.map(slots).fillna(1.0)
                            .to_numpy()) < 0.05
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
        -- RotoGuru rows (position 'Def', <=2021) carry dk_points actuals;
        -- LineStar-backfilled rows (position 'DST', 2022-24) don't, so
        -- actuals are computed from pbp + schedules with DK DST scoring
        -- (same accounting as app.store.trailing_kdst). LAR->LA maps the
        -- one abbreviation difference vs nflverse.
        WITH sal AS (
          SELECT season, week,
                 IF(team_abbr = 'LAR', 'LA', team_abbr) AS team,
                 IF(opponent = 'LAR', 'LA', opponent) AS opp,
                 salary, dk_points
          FROM `{settings.raw}.dk_salaries_historical`
          WHERE UPPER(position) IN ('DEF', 'DST') AND season = {season}
        ),
        def_game AS (
          SELECT p.game_id, p.defteam AS team, ANY_VALUE(p.week) AS week,
                 SUM(CAST(p.sack AS INT64)) AS sacks,
                 SUM(CAST(p.interception AS INT64))
                   + SUM(IF(p.fumble_lost = 1, 1, 0)) AS takeaways,
                 SUM(IF(p.touchdown = 1 AND p.td_team = p.defteam, 1, 0)) AS tds
          FROM `{settings.raw}.pbp` p
          WHERE p.season = {season} AND p.defteam IS NOT NULL
          GROUP BY p.game_id, p.defteam
        ),
        pts AS (
          SELECT game_id, home_team AS team, away_score AS pa
          FROM `{settings.raw}.schedules` WHERE season = {season}
          UNION ALL
          SELECT game_id, away_team, home_score
          FROM `{settings.raw}.schedules` WHERE season = {season}
        ),
        computed AS (
          SELECT dg.team, dg.week,
                 dg.sacks + 2*dg.takeaways + 6*dg.tds +
                 CASE WHEN p.pa = 0 THEN 10 WHEN p.pa <= 6 THEN 7
                      WHEN p.pa <= 13 THEN 4 WHEN p.pa <= 20 THEN 1
                      WHEN p.pa <= 27 THEN 0 WHEN p.pa <= 34 THEN -1
                      ELSE -4 END AS dk
          FROM def_game dg JOIN pts p USING (game_id, team)
        )
        SELECT sal.season, sal.week, sal.team, sal.opp, sal.salary,
               COALESCE(sal.dk_points, c.dk) AS actual
        FROM sal
        LEFT JOIN computed c ON c.team = sal.team AND c.week = sal.week
        WHERE COALESCE(sal.dk_points, c.dk) IS NOT NULL
        """
    )
    return panel, dst


TAIL_LINE_DEFAULT = 194.0  # min 2025 Milly-winning line; 0 disables


def _ownership_booster(replay_season: int):
    """OWN_MODEL=1: LightGBM ownership model fit on LineStar-backfilled
    contest ownership, WALK-FORWARD (seasons strictly before the replayed
    one -- point-in-time discipline applies to auxiliary models too).
    Returns None when no prior-season ownership exists (e.g. 2022)."""
    from ..models import ownership as own_mod

    frame = own_mod.training_frame()
    tr = frame[frame.season < replay_season]
    if len(tr) < 1000:
        log.warning("OWN_MODEL: only %d prior-season ownership rows before "
                    "%s; falling back to naive", len(tr), replay_season)
        return None
    log.info("OWN_MODEL: fit on %d rows from seasons < %s", len(tr), replay_season)
    return own_mod.train(tr)


def _model_ownership(booster, frame: pd.DataFrame) -> np.ndarray:
    """Predicted pct -> naive_ownership-compatible weights (normalized
    within position), so LEVERAGE_PENALTY's scale and the field sampler's
    per-slot semantics are preserved. frame['proj'] stands in for the
    public points expectation the model trained on."""
    from ..models import ownership as own_mod

    f = pd.DataFrame({
        "season": frame["season"], "week": frame["week"],
        "position": frame["pos"], "salary": frame["salary"],
        "proj_points": frame["proj"],
    })
    pct = own_mod.predict_ownership(booster, f)
    out = np.zeros(len(frame))
    for _pos, idx in frame.groupby("pos").groups.items():
        loc = frame.index.get_indexer(idx)
        tot = pct[loc].sum()
        out[loc] = pct[loc] / tot if tot > 0 else 1.0 / max(len(loc), 1)
    return out


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
    # Market blend (guide §7.7) with real prop-derived medians when the
    # season has prop_lines coverage; players without a line keep the
    # model projection (blend() falls back on NaN).
    try:
        from ..models.blend import BLEND_W, blend as _blend
        from ..models.prop_market import market_points

        mkt = market_points((season,))
        if not mkt.empty:
            # Dedup + length guard (2026-08-04 audit): market_points
            # dedups on NAME norm, not gsis — two name variants of one
            # player produce duplicate (season, week, gsis_id) keys, the
            # left merge fans rows out, and every draw_idx after the
            # first duplicate points at the NEXT player's draws.
            mkt = mkt.drop_duplicates(["season", "week", "gsis_id"])
            _n_before = len(proj)
            proj = proj.merge(mkt, on=["season", "week", "gsis_id"],
                              how="left")
            assert len(proj) == _n_before, "market merge fanned out rows"
            _pre = proj.proj_points.to_numpy().copy()
            proj["proj_points"] = _blend(_pre,
                                         proj.market_points.to_numpy(),
                                         BLEND_W)
            # Consensus divergence (external review 3.2 / Addendum 45's
            # two-way disagreement signal): our PRE-blend projection minus
            # the market's — carried on the frame for the DIV_TILT lever.
            proj["consensus_div"] = np.where(
                proj.market_points.notna(),
                _pre - proj.market_points.to_numpy(), 0.0)
            log.info("prop-market blend applied to %d/%d rows",
                     int(proj.market_points.notna().sum()), len(proj))
            # Weight sweep: BLEND_W was fit against the weak dk_ppg
            # market; the prop market is stronger and likely deserves
            # more weight. MAE(w) over blended rows only.
            have = proj.market_points.notna().to_numpy()
            act = proj.actual.to_numpy()[have]
            mdl, mrk = _pre[have], proj.market_points.to_numpy()[have]
            import numpy as _np

            print("  blend-weight sweep (w = model weight; blended rows):")
            for w in (0.0, 0.1, 0.2, 0.3, 0.4, 0.45, 0.5, 0.6, 0.7, 1.0):
                mae = _np.abs(w * mdl + (1 - w) * mrk - act).mean()
                print(f"    w={w:.2f}  MAE={mae:.4f}")
    except Exception:
        log.exception("prop market unavailable; replaying unblended")
    # A/B lever (env TABPFN_MEAN=w, off by default; 2026-08-04): blend
    # the cached TabPFN walk-forward MEAN into the projection at weight
    # w. Rationale: TabPFN beat the quick-LGB on RMSE everywhere, and
    # on COLD-START rows its edge over the trailing baseline is 4x the
    # veteran edge (MAE 4.55 vs 6.10) — ICL shines on thin slices where
    # boosting starves. Rows without cache keep the model mean.
    try:
        _tw = float(os.environ.get("TABPFN_MEAN", "0") or 0)
        if _tw:
            from ..bq import query_df as _qdf
            from ..config import settings as _st

            tb = _qdf(f"SELECT season, week, gsis_id, mean AS tab_mean "
                      f"FROM `{_st.features}.tabpfn_projections` "
                      f"WHERE season = {int(season)}").drop_duplicates(
                          ["season", "week", "gsis_id"])
            _n = len(proj)
            proj = proj.merge(tb, on=["season", "week", "gsis_id"],
                              how="left")
            assert len(proj) == _n, "tabpfn mean merge fanned out rows"
            have = proj.tab_mean.notna()
            proj.loc[have, "proj_points"] = (
                (1 - _tw) * proj.loc[have, "proj_points"]
                + _tw * proj.loc[have, "tab_mean"])
            log.info("TabPFN mean blended (w=%.2f) into %d rows",
                     _tw, int(have.sum()))
    except Exception:
        log.exception("prop market unavailable; replaying unblended")
    try:  # market ceiling room (env ALT_CEIL, off by default)
        import os as _os

        k = float(_os.environ.get("ALT_CEIL", "0") or 0)
        if k:
            from ..models.prop_market import market_ceilings

            mc = market_ceilings((season,)).drop_duplicates(
                ["season", "week", "gsis_id"])
            proj = proj.merge(mc, on=["season", "week", "gsis_id"],
                              how="left")
    except Exception:
        log.exception("alt ceilings unavailable")
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

    # Assumption-validation levers (2026-08-01): these construction rules
    # predate the deterministic A/B era and were adopted on correlational
    # evidence; the envs let each be causally tested with one exact run.
    # Defaults reproduce the adopted construction unchanged.
    stack = (StackRules(
                 qb_stack_min=int(os.environ.get("STACK_QB_MIN", "2")),
                 bring_back_min=int(os.environ.get("STACK_BRING_BACK", "1")),
                 forbid_rb_vs_dst=os.environ.get("FORBID_RB_DST", "1") != "0")
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
    slates = build_slates(proj, dst)
    result = engine_run(slates, contest,
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
        # The user doesn't play rest-week slates (17-18); report the
        # tail on the weeks he actually enters.
        pb = [max(w.lineup_scores) for w in result.weeks if w.week <= 16]
        if pb and len(pb) < len(best):
            print(f"  playable weeks (<=16): mean best {_np.mean(pb):.1f}  "
                  f">=194: {sum(b >= 194 for b in pb)}/{len(pb)}  "
                  f">=187 (20k-qualifier line): "
                  f"{sum(b >= 187 for b in pb)}/{len(pb)}")
        # Honest per-week bar: the ACTUAL score that won the Milly that
        # week (real_lines.py, 2019/23/24/25). Era-portable, unlike the
        # 2025-anchored constants above.
        from .real_lines import REAL_LINES

        pairs = [(max(w.lineup_scores), REAL_LINES[(w.season, w.week)])
                 for w in result.weeks if (w.season, w.week) in REAL_LINES]
        if pairs:
            beat = sum(b >= ln for b, ln in pairs)
            gap = _np.mean([ln - b for b, ln in pairs])
            print(f"  vs REAL winning lines ({len(pairs)} wks known): "
                  f"beat {beat}/{len(pairs)}  mean gap {gap:.0f} pts  "
                  f"within 20: {sum(0 < ln - b <= 20 for b, ln in pairs)}")
        # Milly winners spend the cap (2025: median $0 left, max $100;
        # 2023-24: 90% within $300) — flag if our entries leave money.
        left = [50_000 - lu.salary for w in result.weeks for lu in w.lineups]
        print(f"  salary left on table: mean {_np.mean(left):.0f}  "
              f"median {_np.median(left):.0f}  p90 {_np.percentile(left, 90):.0f}  "
              f"share >$1k: {100 * _np.mean(_np.array(left) > 1000):.0f}%")
        _entries_to_line(result.weeks)
        _confidence_calibration(result.weeks, proj)
        _entry_anatomy(result.weeks)
        _capture_rates(result.weeks, slates)
        _duplication_risk(result.weeks)
        try:  # persist rosters for human review (nfl_features.replay_lineups)
            from ..bq import load_dataframe
            from ..config import settings

            rows = []
            for w in result.weeks:
                order = np.argsort(w.lineup_scores)[::-1]
                for rk, ix in enumerate(order):
                    lu = w.lineups[ix]
                    for p in lu.players:
                        rows.append({
                            "season": w.season, "week": w.week,
                            "score_rank": rk + 1, "tag": lu.tag or "lev",
                            # selection order (greedy coverage is nested:
                            # first N entries ~ optimal N-entry portfolio)
                            # -> one 150-entry run yields P(best-of-N)
                            # curves for every N (entries sweet-spot study)
                            "entry_ix": int(ix) + 1,
                            "lineup_score": round(w.lineup_scores[ix], 1),
                            "player": p.get("name"), "pos": p.get("pos"),
                            "team": p.get("team"), "salary": p.get("salary"),
                            "proj": round(float(p.get("proj", 0)), 1),
                            "actual": round(float(p.get("actual") or 0), 1)})
            load_dataframe(pd.DataFrame(rows),
                           f"{settings.features}.replay_lineups",
                           write_disposition="WRITE_TRUNCATE")
            print(f"  rosters persisted: {len(rows)} rows -> replay_lineups")
        except Exception:
            log.exception("could not persist replay rosters")


def _duplication_risk(weeks, field_size: int = 150_000) -> None:
    """Estimated copies of each entry in a Milly-sized field: field_size
    x product of player ownerships (naive proxy until the real model).
    Arbitrates whether engineered uniqueness (underspend, forced pivots)
    is needed or our entries are already effectively unique."""
    import numpy as _np

    from ..optimizer.lineup import LEVERAGE_PENALTY

    est = []
    for w in weeks:
        for lu in w.lineups:
            owns = [max(1e-4, min(0.6, (p.get("proj", 0)
                    - p.get("proj_tourney", p.get("proj", 0)))
                    / LEVERAGE_PENALTY)) for p in lu.players]
            est.append(field_size * float(_np.prod(owns)))
    if not est:
        return
    e = _np.array(est)
    print(f"  duplication risk (est copies in a {field_size//1000}k field, "
          f"naive ownership): median {_np.median(e):.3f}  "
          f"p90 {_np.percentile(e, 90):.2f}  max {e.max():.1f}  "
          f"entries with >=1 est copy: {int((e >= 1).sum())}/{len(e)}")


def _capture_rates(weeks, slates) -> None:
    """Did our 40 hold the slate's best-scoring punt / QB at all? Breadth
    (distinct players held per tier) + capture tell whether misses are a
    prediction problem or a diversity problem."""
    import numpy as _np

    from ..optimizer.lineup import PUNT_MAX_SALARY

    by_wk = {int(s.week.iloc[0]): s for s in slates}
    rows = []
    for w in weeks:
        sl = by_wk.get(w.week)
        if sl is None:
            continue
        punts = sl[(sl.salary <= PUNT_MAX_SALARY)]
        best_punt = punts.actual.max() if len(punts) else 0
        qbs = sl[sl.pos == "QB"]
        best_qb = qbs.actual.max() if len(qbs) else 0
        held_p, held_q = set(), set()
        our_bp, our_bq = 0.0, 0.0
        for lu in w.lineups:
            for p in lu.players:
                a = float(p.get("actual") or 0)
                if p["salary"] <= PUNT_MAX_SALARY:
                    held_p.add(p["id"]); our_bp = max(our_bp, a)
                if p["pos"] == "QB":
                    held_q.add(p["id"]); our_bq = max(our_bq, a)
        rows.append({"pc": our_bp >= best_punt - 1e-6,
                     "qc": our_bq >= best_qb - 1e-6,
                     "np": len(held_p), "nq": len(held_q),
                     "pgap": best_punt - our_bp, "qgap": best_qb - our_bq})
    if not rows:
        return
    d = pd.DataFrame(rows)
    print(f"  capture rates across our 40 (per week):")
    print(f"    slate-best PUNT held: {int(d.pc.sum())}/{len(d)} weeks  "
          f"(distinct punts held avg {d.np.mean():.1f}, "
          f"miss gap avg {d[~d.pc].pgap.mean():.1f} pts)")
    print(f"    slate-best QB held:   {int(d.qc.sum())}/{len(d)} weeks  "
          f"(distinct QBs held avg {d.nq.mean():.1f}, "
          f"miss gap avg {d[~d.qc].qgap.mean():.1f} pts)")


def _entry_anatomy(weeks) -> None:
    """Why do our best entries win? Compare each week's top scorer (and
    top quintile) against the rest of the 40 on structure: generator of
    origin, game concentration, QB stack size, punt production, chalk
    level, salary. Ownership is recovered from the leverage tilt:
    proj_tourney = proj - LEVERAGE_PENALTY * ownership."""
    import numpy as _np

    from ..optimizer.lineup import LEVERAGE_PENALTY, PUNT_MAX_SALARY

    def feats(lu):
        ps = lu.players
        games = {}
        for p in ps:
            games[p.get("game_id")] = games.get(p.get("game_id"), 0) + 1
        qb = next((p for p in ps if p["pos"] == "QB"), None)
        stack_n = sum(1 for p in ps if qb is not None and p["pos"] in
                      ("WR", "TE") and p["team"] == qb["team"])
        punts = [p for p in ps if p["salary"] <= PUNT_MAX_SALARY]
        own = sum(max(0.0, (p.get("proj", 0) - p.get("proj_tourney",
                   p.get("proj", 0)))) / LEVERAGE_PENALTY for p in ps)
        return {
            "tag": lu.tag or "lev",
            "max_game": max(games.values()) if games else 0,
            "stack": stack_n,
            "punt_actual": max((float(p.get("actual") or 0) for p in punts),
                               default=0.0),
            "own": own,
            "salary": lu.salary,
        }

    rows, best_tags = [], []
    for w in weeks:
        order = _np.argsort(w.lineup_scores)[::-1]
        for rank_pos, idx in enumerate(order):
            f = feats(w.lineups[idx])
            f["score"] = w.lineup_scores[idx]
            f["is_best"] = rank_pos == 0
            f["is_top8"] = rank_pos < 8
            rows.append(f)
            if rank_pos == 0:
                best_tags.append(f["tag"])
    if not rows:
        return
    df = pd.DataFrame(rows)
    pool_share = df.tag.value_counts(normalize=True)
    from collections import Counter

    bt = Counter(best_tags)
    print("  entry anatomy (what wins within our own 40):")
    print("    weekly best by generator: "
          + "  ".join(f"{t}:{bt.get(t, 0)}/{len(best_tags)} "
                      f"(pool {100 * pool_share.get(t, 0):.0f}%)"
                      for t in ("lev", "boom", "game", "nostk", "midqb", "dark")))
    for label, mask in (("weekly best", df.is_best),
                        ("top-8/week", df.is_top8),
                        ("rest", ~df.is_top8)):
        g = df[mask]
        print(f"    {label:>11}: score {g.score.mean():5.1f}  "
              f"max-from-game {g.max_game.mean():.2f}  "
              f"QB stack {g['stack'].mean():.2f}  "
              f"punt pts {g.punt_actual.mean():5.1f}  "
              f"chalk {g.own.mean():.2f}  salary {g.salary.mean():.0f}")


def _confidence_calibration(weeks, proj: pd.DataFrame,
                            line: float = 194.0, dst_std: float = 5.4) -> None:
    """Judge the app's confidence formula (normal-approx P(entry >= line)
    from per-player proj mean/std — app._rank_by_confidence) the same way
    the selection order is judged: where does each week's best scorer land
    when entries are ordered by that confidence?"""
    from statistics import NormalDist

    import numpy as _np

    mu_map = {(r.week, r.gsis_id): r.proj_points for r in proj.itertuples()}
    sd_map = {(r.week, r.gsis_id): r.proj_std for r in proj.itertuples()}
    ranks = []
    for w in weeks:
        conf = []
        for lu in w.lineups:
            mu = sum(float(mu_map.get((w.week, p["id"]), p["proj"]))
                     for p in lu.players)
            var = sum(float(sd_map.get((w.week, p["id"]), dst_std)) ** 2
                      for p in lu.players)
            conf.append(1 - NormalDist(mu, max(var ** 0.5, 1e-6)).cdf(line))
        order = _np.argsort(conf)[::-1]  # most confident first
        best_idx = int(_np.argmax(w.lineup_scores))
        ranks.append(int(_np.where(order == best_idx)[0][0]) + 1)
    if ranks:
        r = _np.array(ranks)
        print(f"  app-confidence ordering, best scorer's rank: "
              f"median {int(_np.median(r))}  rank-1 hit {int((r == 1).sum())}"
              f"/{len(r)}  in top-5 {int((r <= 5).sum())}/{len(r)}"
              f"  in top-10 {int((r <= 10).sum())}/{len(r)}")


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

    print("  entries-to-line (N for 50% chance best-of-N >= line); "
          "top3 = the week's three best entry scores:")
    print(f"    {'week':>4} {'mu':>6} {'sd':>5} {'top3':>20} {'brk':>4} "
          + " ".join(f"N@{ln}" for ln in lines))
    med = {ln: [] for ln in lines}
    best_ranks: list[int] = []
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
        top3 = ",".join(f"{v:.1f}" for v in sorted(s)[::-1][:3])
        best_rank = int(_np.argmax(s)) + 1  # selection position of the
        best_ranks.append(best_rank)        # week's best scorer (1 = the
        print(f"    {w.week:>4} {mu:6.1f} {sd:5.1f} {top3:>20} {best_rank:>4} "
              + " ".join(f"{x:>7}" for x in ns))  # entry we trusted most)
    if best_ranks:
        br = _np.array(best_ranks)
        print(f"    best scorer's selection rank: median {int(_np.median(br))}"
              f"  rank-1 hit {int((br == 1).sum())}/{len(br)} weeks"
              f"  in top-5 {int((br <= 5).sum())}/{len(br)}"
              f"  in top-10 {int((br <= 10).sum())}/{len(br)}")
    for ln in lines:
        if med[ln]:
            m = sorted(med[ln])[len(med[ln]) // 2]
            within = sum(n <= 150_000 for n in med[ln])
            print(f"    line {ln}: median N {'inf' if m == math.inf else f'{m:,.0f}'}"
                  f"  weeks reachable within a 150k-entry field: "
                  f"{within}/{len(med[ln])}")
