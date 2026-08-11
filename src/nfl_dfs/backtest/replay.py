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
from ..research.candidate_features import PLAYER_SNAPSHOT_FEATURES
from .engine import BacktestResult, run as engine_run
from .payout import Contest

log = logging.getLogger(__name__)

DST_FALLBACK_PROJ = 6.0  # league-average DST DK points, for week-1 rows

# Frozen after the rejected wholesale fast-role panel. This exact family may
# train a second model for candidate generation, but it must never leak into
# the baseline projections used to score and select those candidates.
ROLE_BELIEF_FEATURES = (
    "target_share_last", "carry_share_last", "snap_share_last",
    "target_share_jump", "carry_share_jump", "snap_share_jump",
)


def own_mode(env: dict | None = None) -> str:
    """OWN_MODEL env, normalized. Default "" ADOPTED 2026-08-05
    (Addenda 77/80/84): the chalk fade STAYS (its true deletion cost
    ~2 tails in both builds) but runs on NAIVE ownership — the trained
    booster added nothing in the fade (naive-fade arms 26/27 vs 25)
    and leaves the construction path entirely. OWN_MODEL=fade restores
    the booster fade; falsy spellings ("", "0", "off", "false", "no",
    "none") mean naive-fade; any other truthy string flips the model
    into the field sampler (deliberately not adopted)."""
    v = (os.environ.get("OWN_MODEL", "") if env is None
         else env.get("OWN_MODEL", "")).strip().lower()
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
    comps = cm.predict_components(rows)
    member_points = (pd.DataFrame(index=rows.index)
                     if os.environ.get("TABPFN_COMPONENTS", "") not in ("", "0")
                     else cm.point_member_predictions(rows))
    # A/B lever (env TABPFN_COMPONENTS, off by default; 2026-08-04,
    # TabPFN-expansion): swap the LightGBM component MEANS for cached
    # walk-forward TabPFN predictions (features.tabpfn_components, GPU
    # job tabpfn-comp) — the deepest insertion point, gated behind its
    # own panel. Clips and position-zero rules re-applied so downstream
    # sim invariants hold; rows without cache keep the LGB values.
    if os.environ.get("TABPFN_COMPONENTS", "") not in ("", "0"):
        try:
            from ..bq import query_df as _qdf
            from ..config import settings as _st
            from ..models.components import COMPONENT_NAMES, RATE_CLIPS

            tc = _qdf(f"SELECT * FROM `{_st.features}.tabpfn_components` "
                      f"WHERE season = {int(season)}").drop_duplicates(
                          ["season", "week", "gsis_id"]).set_index(
                          ["week", "gsis_id"])
            idx = pd.MultiIndex.from_arrays(
                [rows.week.astype(int), rows.gsis_id])
            aligned = tc.reindex(idx)
            n_hit = int(aligned[COMPONENT_NAMES[0]].notna().sum())
            for name in COMPONENT_NAMES:
                if name not in aligned.columns:
                    continue
                v = aligned[name].to_numpy()
                have = ~pd.isna(v)
                comps.loc[have, name] = v[have].astype(float)
            for name, (lo, hi) in RATE_CLIPS.items():
                comps[name] = comps[name].clip(lo, hi)
            for name in ("targets", "rec_tds", "carries", "rush_tds",
                         "pass_attempts", "pass_tds", "interceptions"):
                comps[name] = comps[name].clip(lower=0.0)
            is_qb = (rows.position == "QB").to_numpy()
            comps.loc[is_qb, ["targets", "rec_tds"]] = 0.0
            comps.loc[~is_qb, ["pass_attempts", "pass_tds",
                               "interceptions"]] = 0.0
            log.info("TabPFN components swapped for %d/%d rows",
                     n_hit, len(rows))
        except Exception:
            log.exception("TabPFN components unavailable; LGB kept")
    member_world_mode = os.environ.get("ENSEMBLE_WORLD_MODE", "").strip()
    if member_world_mode not in ("", "member_sample"):
        raise ValueError(
            f"unknown ENSEMBLE_WORLD_MODE={member_world_mode!r}")
    if member_world_mode and not return_draws:
        raise ValueError(
            "ENSEMBLE_WORLD_MODE is research-only and requires "
            "return_draws=True")
    sim = simulate.simulate(comps, n_sims=n_sims,
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
    raw_draws = sim.draws
    if member_world_mode == "member_sample":
        member_seed = int(
            os.environ.get("ENSEMBLE_WORLD_SEED", "8161") or 8161)
        raw_draws, member_ids = apply_member_world_shift(
            raw_draws, member_points, member_seed)
        counts = np.bincount(member_ids, minlength=member_points.shape[1])
        log.info(
            "ensemble member-world shift: seed=%d counts=%s",
            member_seed, counts.tolist())
    draws_out = (apply_draw_shape(raw_draws, rows.position, seed,
                                  keys=rows[[c for c in ("season", "week",
                                         "gsis_id", "is_rookie")
                                         if c in rows.columns]])
                 if return_draws else sim.draws)
    # SCHAAKE_DIAG=1 (Workstream C gate): log role-pair dependence of
    # the PRODUCTION draws vs the same draws with the empirical
    # game-template copula imposed. Same marginals both sides — only
    # the joint pattern differs — so this is the honest control the
    # offline gate could not provide (it compared against independence).
    if return_draws and os.environ.get("SCHAAKE_DIAG"):
        try:
            from ..research.schaake_diag import log_dependence_ab
            log_dependence_ab(rows, draws_out)
        except Exception:
            log.exception("schaake diagnostic failed; replay unaffected")
            if os.environ.get("SCHAAKE_DIAG_STRICT"):
                raise
    keep = [c for c in (
        "gsis_id", "name", "season", "week", "team", "opponent",
        "position", "game_id", "salary", "injury_status", "was_active",
        *PLAYER_SNAPSHOT_FEATURES,
    ) if c in rows.columns]
    out = pd.concat([rows[keep], summary], axis=1)
    if not member_points.empty:
        out = pd.concat([out, member_points.reset_index(drop=True)], axis=1)
    out["actual"] = rows["y_dk_points"].to_numpy()
    out["naive"] = rows.get("dk_points_l4")  # trailing average, the free baseline
    if return_draws:
        return out, draws_out.astype(np.float32)
    return out


def apply_member_world_shift(
    draws: np.ndarray,
    member_points: pd.DataFrame,
    seed: int = 8161,
) -> tuple[np.ndarray, np.ndarray]:
    """Inject coherent ensemble beliefs before frozen marginal shaping.

    One fitted member is assigned to each simulation world and its centered
    point-prediction delta is applied to every player in that world. Assigning
    one member globally (rather than independently by player) represents a
    coherent model belief. The normal TabPFN/empirical rank shaper runs after
    this helper, restoring each player's calibrated marginal distribution and
    retaining only the member-induced joint-world ordering.

    This is an off-by-default research mechanism. It never changes the
    default averaged-component simulator.
    """
    values = np.asarray(draws, dtype=float)
    if values.ndim != 2:
        raise ValueError("draws must be a player-by-world matrix")
    columns = sorted(
        (column for column in member_points
         if column.startswith("ensemble_point_")),
        key=lambda column: int(column.rsplit("_", 1)[1]))
    if len(columns) < 2:
        raise ValueError(
            "member_sample requires at least two ensemble point predictions")
    points = member_points[columns].to_numpy(dtype=float)
    if points.shape[0] != values.shape[0] or not np.isfinite(points).all():
        raise ValueError("ensemble point predictions are missing or misaligned")
    n_members = points.shape[1]
    member_ids = np.arange(values.shape[1], dtype=int) % n_members
    np.random.default_rng(seed).shuffle(member_ids)
    centered = points - points.mean(axis=1, keepdims=True)
    shifted = values + centered[:, member_ids]
    return shifted, member_ids


def role_belief_projections(
    panel: pd.DataFrame,
    season: int,
    n_sims: int,
    num_boost_round: int = 400,
) -> tuple[pd.DataFrame, np.ndarray] | tuple[None, None]:
    """Train the frozen alternate role model without changing baseline env.

    The feature set is deliberately exact—this is a preregistered mechanism,
    not a sweep. A nonempty baseline EXTRA_FEATURES would bundle two changes
    and therefore hard-fails. Environment restoration is guaranteed even if
    model training fails.
    """
    raw = os.environ.get("ROLE_BELIEF_FEATURES", "").strip()
    if not raw:
        return None, None
    requested = tuple(x.strip() for x in raw.split(",") if x.strip())
    if len(requested) != len(set(requested)) or set(requested) != set(
            ROLE_BELIEF_FEATURES):
        raise ValueError(
            "ROLE_BELIEF_FEATURES must be exactly "
            + ",".join(ROLE_BELIEF_FEATURES))
    if os.environ.get("EXTRA_FEATURES", "").strip():
        raise ValueError(
            "role-belief panel requires an unmodified baseline EXTRA_FEATURES")
    previous = os.environ.get("EXTRA_FEATURES")
    os.environ["EXTRA_FEATURES"] = ",".join(ROLE_BELIEF_FEATURES)
    try:
        seed = int(os.environ.get("ROLE_BELIEF_SEED", "7331") or 7331)
        alternate, draws = replay_projections(
            panel, season, n_sims=n_sims,
            num_boost_round=num_boost_round, seed=seed, return_draws=True)
    finally:
        if previous is None:
            os.environ.pop("EXTRA_FEATURES", None)
        else:
            os.environ["EXTRA_FEATURES"] = previous
    keys = ["season", "week", "gsis_id"]
    expected = panel[panel.season == season].reset_index(drop=True)[keys]
    if not alternate[keys].reset_index(drop=True).equals(expected):
        raise ValueError("role-belief replay rows do not align with baseline panel")
    log.info("role-belief replay ready: season=%s rows=%d seed=%d features=%s",
             season, len(alternate), seed, ",".join(ROLE_BELIEF_FEATURES))
    return alternate, draws


def apply_draw_shape(draws: np.ndarray, positions: pd.Series,
                     seed: int | None,
                     keys: pd.DataFrame | None = None,
                     env: dict | None = None) -> np.ndarray:
    """ADOPTED DEFAULTS (Addendum 40, combo "EW" — 24/107 tails vs 16
    same-build control, largest gain in program history): fitted draw
    widening + empirically-shaped marginals, composed, mean-preserving.
    Shared by replays AND the live sim-mode path so what was validated
    is exactly what fires on Sundays. Env overrides: SIM_WIDEN_DRAWS=off
    or an explicit "WR:1.3,..." spec; EMP_MARGINALS=0 disables."""
    source = os.environ if env is None else env
    out = draws
    widen_spec = source.get("SIM_WIDEN_DRAWS", "fitted")
    if widen_spec.lower() not in ("off", "0", ""):
        out = _widen_draws(out, positions, widen_spec)
    # A/B lever (env ROOKIE_WIDEN, off by default; 2026-08-04 rookie
    # readiness): rookie q90 coverage measured 0.888 vs 0.904 veteran —
    # ceilings mildly under-covered exactly in the punt band where the
    # construction values players AT their ceiling. Fitted on 4,105
    # historical rookie rows: widening rookie draws' spread around their
    # mean by 1.07 restores exact 0.900 coverage. Needs keys carrying
    # is_rookie (replay rows and the live inference frame both do).
    rw = source.get("ROOKIE_WIDEN", "")
    if (rw not in ("", "0") and keys is not None
            and "is_rookie" in getattr(keys, "columns", [])):
        s = 1.07 if rw == "1" else float(rw)
        mask = keys.is_rookie.fillna(False).astype(bool).to_numpy()
        if mask.any():
            mu = out[mask].mean(axis=1, keepdims=True)
            out = out.copy()
            out[mask] = np.maximum(mu + s * (out[mask] - mu), 0.0)
    shaped = None
    # TABPFN_MARGINALS ADOPTED default-on 2026-08-04 (Addendum 50):
    # +6 tails alone (24 vs 18), STPFN stack = best mean-best of the
    # panel (179.5) at equal tails. Requires the tabpfn_projections
    # cache (GPU job tabpfn-gen, ~$0.05/wk); missing cache falls back
    # to empirical marginals below. "0"/"" disables.
    if (source.get("TABPFN_MARGINALS", "1") not in ("0", "")
            and keys is not None):
        shaped = _tabpfn_marginals(out, keys)
    if shaped is not None:
        out = shaped
    elif source.get("EMP_MARGINALS", "1") not in ("0", ""):
        out = _empirical_marginals(
            out, positions,
            np.random.default_rng(0 if seed is None else seed + 7),
            env=source)
    # A/B lever (env SHAPE_MIX, off by default = 1.0): apply the shaping
    # to only the first fraction f of sims, leaving the rest RAW — the
    # EW-vs-PB2 diff showed 15 weeks converted but 9 regressed (each
    # world-model sees booms the other misses); mixed worlds let the
    # coverage selector hedge across both regimes.
    mix = float(source.get("SHAPE_MIX", "1") or 1)
    if mix <= 0.0:
        return draws  # 0 = all-raw (was returning fully-shaped — audit)
    if mix < 1.0:
        k = int(mix * draws.shape[1])
        out = np.concatenate([out[:, :k], draws[:, k:]], axis=1)
    return out


def apply_served_tail_scale(
    draws: np.ndarray,
    positions: pd.Series,
    env: dict | None = None,
) -> np.ndarray:
    """Apply the preregistered mean-invariant final served spread scale.

    The production default is the identity. Research can supply the one
    global factor through ``SERVED_TAIL_SCALE``; no position-specific dose is
    accepted. The correction belongs after shaping and the market mean shift
    because those are the worlds whose calibration it is intended to repair.
    """
    source = os.environ if env is None else env
    spec = str(source.get("SERVED_TAIL_SCALE", "1") or "1").strip()
    try:
        factor = float(spec)
    except ValueError as exc:
        raise ValueError(f"invalid SERVED_TAIL_SCALE={spec!r}") from exc
    if factor in (0.0, 1.0):
        return draws
    if not np.isfinite(factor) or not 1.0 <= factor <= 1.25:
        raise ValueError("SERVED_TAIL_SCALE must be identity or in [1, 1.25]")
    values = np.asarray(draws)
    if values.ndim != 2 or len(positions) != values.shape[0]:
        raise ValueError("served-tail scale rows do not align")
    mask = positions.astype(str).str.upper().isin(("RB", "WR", "TE")) \
        .to_numpy()
    if not mask.any():
        return draws
    out = values.astype(np.float64, copy=True)
    before = out[mask].mean(axis=1, dtype=np.float64, keepdims=True)
    corrected = before + factor * (out[mask] - before)
    # Remove only floating summation drift; this keeps the transformation
    # exactly mean-invariant even for long simulation matrices.
    corrected += before - corrected.mean(
        axis=1, dtype=np.float64, keepdims=True)
    out[mask] = corrected
    max_delta = float(np.max(np.abs(
        out[mask].mean(axis=1, dtype=np.float64, keepdims=True) - before)))
    if max_delta > 1e-10:
        raise ValueError(
            f"served-tail scale changed a row mean by {max_delta:.3g}")
    return out


def _stable_ordinal_ranks(values: np.ndarray) -> np.ndarray:
    """Zero-based ranks with reproducible tie-breaking by world index.

    Simulation draws contain many exact ties (zero-volume players and
    discrete scoring outcomes in particular).  NumPy's default quicksort is
    intentionally unstable and may permute equal values differently across
    CPU-dispatched implementations.  Marginal shaping turns those arbitrary
    tie permutations into different joint worlds even though every player's
    marginal distribution is unchanged.  A stable sort makes the original
    simulation-column index the explicit, portable tie-breaker.
    """
    order = np.argsort(np.asarray(values), kind="stable")
    ranks = np.empty_like(order)
    ranks[order] = np.arange(order.size, dtype=order.dtype)
    return ranks


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
    try:
        q = query_df(
            f"SELECT * FROM `{settings.features}.tabpfn_projections` "
            f"WHERE season = {season}")
    except Exception:
        # Local tests, a newly-created project, or a transient warehouse
        # failure must take the documented empirical fallback rather than
        # aborting the entire projection/simulation path.
        log.exception("TabPFN marginal cache unavailable for season %s; "
                      "falling back to empirical marginals", season)
        return None
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
        ranks = _stable_ordinal_ranks(row) / max(n - 1, 1)
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
                         rng: np.random.Generator,
                         env: dict | None = None) -> np.ndarray:
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
    source = os.environ if env is None else env
    allow = {p.strip().upper() for p in
             source.get("EMP_POS", "").split(",") if p.strip()}
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
        order = _stable_ordinal_ranks(draws[i])
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
    # Projection accuracy is conditional on participating. Salary-listed
    # inactive rows remain in contest replay with a zero score, but they are
    # not training/evaluation examples for on-field player output.
    if "was_active" in proj.columns:
        proj = proj[proj.was_active.fillna(False).astype(bool)].copy()
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
    if "injury_status" in skill.columns:
        known_out = skill.injury_status.fillna("").astype(str).str.upper().eq("OUT")
        if known_out.any():
            log.info("build_slates: removed %d players known Out before lock",
                     int(known_out.sum()))
            skill = skill[~known_out].copy()
    skill["id"] = skill.gsis_id
    skill["pos"] = skill.position
    skill["opp"] = skill.opponent
    # Row position in the replay_projections frame == row in its draw
    # matrix; -1 (DST) means "no draws, use the static projection".
    skill["draw_idx"] = skill.index.to_numpy()
    # Keep the post-market mean before construction-specific p90 punt
    # valuation overwrites ``proj``. Blend audits must observe the actual
    # projection, not a downstream optimizer objective.
    skill["mean_projection"] = skill.proj_points
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
    # PUNT_BOOM default 0 ADOPTED 2026-08-05 (Addendum 77/79b): the
    # archetype boost + punt mandate deletion scored 26-27 vs 25; the
    # p90 punt VALUATION (build_slates) stays — it was never the dose.
    punt_boom = float(os.environ.get("PUNT_BOOM", "0") or 0)
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
                "salary", "proj", "actual", "season", "week", "draw_idx",
                "gsis_id"]  # Q99_WILD keys
        if "consensus_div" in grp.columns:  # DIV_TILT lever input
            cols.append("consensus_div")
        # point-in-time feature snapshot for the candidate table
        # (Sol audit 3 §B1): market/model disagreement + marginal
        # quantiles are only available DURING the run.
        for _c in (
            "market_points", "model_points_pre", "mean_projection",
            "proj_p10", "proj_p50", "proj_p90", "proj_std",
            *PLAYER_SNAPSHOT_FEATURES,
        ):
            if _c in grp.columns:
                cols.append(_c)
        for _c in (
            "fp_route_source_season", "fp_route_source_week",
            "route_control_p30", "route_treatment_p30", "route_delta_30",
            "fp_cov_receiver_source_season",
            "fp_cov_defense_source_season",
            "coverage_control_p30", "coverage_treatment_p30",
            "coverage_delta_30",
        ):
            if _c in grp.columns:
                cols.append(_c)
        cols.extend(c for c in grp.columns
                    if c.startswith("ensemble_point_") and c not in cols)
        frame = grp[cols].copy()
        if dst_rows is not None:
            d = dst_rows[(dst_rows.season == season) & (dst_rows.week == week)].copy()
            d["game_id"] = d.team + "@" + d.opp
            d["draw_idx"] = -1
            # DST rows lack optional slate columns (consensus_div —
            # 2026-08-04 crash: KeyError on every prop-covered season)
            for c in cols:
                if c not in d.columns:
                    if c == "consensus_div":
                        d[c] = 0.0
                    elif (c in ("market_points", "model_points_pre")
                          or c.startswith("ensemble_point_")):
                        # Missing epistemic information is not a zero-point
                        # belief.  NaN makes scenario construction retain the
                        # DST's incumbent projection.
                        d[c] = np.nan
                    elif c.startswith("proj_p") or c == "proj_std":
                        d[c] = d["proj"] if c != "proj_std" else 0.0
                    elif c in ("route_delta_30", "coverage_delta_30"):
                        d[c] = 0.0
                    elif (c.startswith("fp_route_source_")
                          or c.startswith("route_control_")
                          or c.startswith("route_treatment_")
                          or c.startswith("fp_cov_")
                          or c.startswith("coverage_control_")
                          or c.startswith("coverage_treatment_")):
                        d[c] = np.nan
                    elif c in PLAYER_SNAPSHOT_FEATURES:
                        # DST rows have no player-role history. Missingness is
                        # semantically different from a zero role or zero game
                        # total and must remain visible in the snapshot.
                        d[c] = np.nan
                    else:
                        d[c] = 0.0
            if "mean_projection" in cols:
                # DST has no simulated marginal. Its static projection is
                # therefore its world mean, not the generic numeric-missing
                # sentinel used for optional skill-player features.
                d["mean_projection"] = d["proj"]
            frame = pd.concat([frame, d[cols]], ignore_index=True)
        # RotoGuru DST rows occasionally lack salary or points; a single NaN
        # poisons the field sampler's ownership softmax.
        n0 = len(frame)
        frame = frame.dropna(subset=["salary", "proj", "actual"])
        frame = frame[frame.salary > 0]  # RotoGuru's missing-salary sentinel
        # Engine requires unique ids (actual.reindex, draw alignment). Never
        # select one by input order: that previously hid adjacent-Thursday DST
        # salaries and could assign the wrong opponent/price to a replay week.
        dup = frame.id.duplicated()
        if dup.any():
            ids = frame.loc[frame.id.duplicated(keep=False), "id"].tolist()
            raise ValueError(
                f"slate {season} wk {week}: duplicate ids after validated "
                f"joins: {ids[:8]}")
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
            if own_mode() not in ("fade", "milly_fade", ""):
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
        # Ownership estimate on the slate rows (review #4 F4): the
        # OWN_BARBELL constraint in optimize() reads it off the pool
        # dicts. Raw own (not LEV_SHAPE-transformed) — the constraint
        # wants the level, not the penalty shape.
        frame["own_est"] = own
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


def _limit_replay_slates(slates: list[pd.DataFrame],
                         max_weeks: int | None) -> list[pd.DataFrame]:
    """Audit-smoke limiter; production/default replay is unchanged."""
    if max_weeks is None:
        return slates
    if max_weeks < 1:
        raise ValueError("max_weeks must be at least 1")
    return slates[:max_weeks]


# Historical salary sources use a mixture of RotoGuru, LineStar, and modern
# NFL abbreviations.  schedule_long deliberately uses modern codes, so both
# sides of every historical salary/schedule join must use this complete map.
# Keep this list aligned with sql/features/001a_dk_salary_week.sql.
_HISTORICAL_TEAM_ALIASES = {
    "GNB": "GB",
    "JAC": "JAX",
    "KAN": "KC",
    "LAR": "LA",
    "LVR": "LV",
    "NOR": "NO",
    "NWE": "NE",
    "OAK": "LV",
    "SD": "LAC",
    "SDG": "LAC",
    "SFO": "SF",
    "STL": "LA",
    "TAM": "TB",
}


def _historical_team_sql(column: str) -> str:
    """BigQuery expression mapping a historical team column to modern codes."""
    whens = " ".join(
        f"WHEN '{old}' THEN '{new}'"
        for old, new in _HISTORICAL_TEAM_ALIASES.items()
    )
    return f"CASE {column} {whens} ELSE {column} END"


def _main_slate_sql(alias: str) -> str:
    """Independent schedule predicate for the DK Sunday main slate.

    Historical salary feeds are NFL-week feeds, not draft-group snapshots.
    The main GPP slate contains Sunday 1pm and late-afternoon games; London,
    primetime, Thursday/Friday/Saturday/Monday, and Sunday night are excluded.
    """
    return (
        f"{alias}.game_type = 'REG' "
        f"AND {alias}.weekday = 'Sunday' "
        f"AND SAFE.PARSE_TIME('%H:%M', {alias}.gametime) >= TIME '13:00:00' "
        f"AND SAFE.PARSE_TIME('%H:%M', {alias}.gametime) < TIME '19:00:00'"
    )


# Warehouse entry point ------------------------------------------------------


def load_panel_and_dst(season: int):
    from ..bq import query_df
    from ..config import settings

    salary_team = _historical_team_sql("team_abbr")
    salary_opp = _historical_team_sql("opponent")
    main_target = _main_slate_sql("sc")

    panel = query_df(
        f"""
        SELECT t.*, i.name
        FROM `{settings.features}.player_week_training` t
        LEFT JOIN (
          -- player_ids is not unique on gsis_id (legacy aliases and a few
          -- upstream collisions). A raw join duplicated otherwise unique
          -- training rows. Name is display-only here, so select one stable
          -- spelling without changing the model-fitting universe.
          SELECT gsis_id,
                 ARRAY_AGG(name IGNORE NULLS ORDER BY name LIMIT 1)
                   [SAFE_OFFSET(0)] AS name
          FROM `{settings.raw}.player_ids`
          WHERE gsis_id IS NOT NULL
          GROUP BY gsis_id
        ) i USING (gsis_id)
        LEFT JOIN `{settings.raw}.schedules` sc USING (game_id)
        WHERE t.season BETWEEN {settings.train_first_season} AND {season}
          -- Prior seasons remain complete model-training data. Only the
          -- target/evaluation season is restricted to the contest slate.
          AND (t.season < {season} OR ({main_target}))
        ORDER BY t.season, t.week, t.gsis_id
        """
    )  # ORDER BY: read-order determinism (variance review 2026-08-04)
    dst = query_df(
        f"""
        -- RotoGuru rows (position 'Def', <=2021) carry dk_points actuals;
        -- LineStar-backfilled rows (position 'DST', 2022-24) don't, so
        -- actuals are computed from pbp + schedules with DK DST scoring
        -- (same accounting as app.store.trailing_kdst). Historical salary
        -- sources use RotoGuru/LineStar aliases while schedule_long uses
        -- modern codes, so normalize BOTH team and opponent before joining.
        WITH sal_raw AS (
          SELECT season, week,
                 {salary_team} AS team,
                 {salary_opp} AS opp,
                 salary, dk_points
          FROM `{settings.raw}.dk_salaries_historical`
          WHERE UPPER(position) IN ('DEF', 'DST') AND season = {season}
        ),
        -- LineStar's weekly export labels the adjacent Thursday slate with
        -- the prior display week.  That leaves two salaries for some teams:
        -- one against this NFL week's opponent and one against next week's.
        -- Validate the opponent against the canonical schedule BEFORE any
        -- deduplication; dropping by input order selected the wrong salary.
        sal AS (
          SELECT h.*
          FROM sal_raw h
          JOIN `{settings.features}.schedule_long` s
            ON s.season = h.season AND s.week = h.week
           AND s.team = h.team AND s.opponent = h.opp
          JOIN `{settings.raw}.schedules` sc USING (game_id)
          WHERE {main_target}
        ),
        computed AS (
          -- One canonical scorer owns fumble-recovery team attribution,
          -- return/blocked-kick TDs, safeties, blocked kicks, defensive
          -- conversions, and the DK points-allowed exclusions.  The old
          -- replay-local approximation omitted several of those events.
          SELECT season, week, team, dst_dk_points AS dk
          FROM `{settings.features}.team_defense_week`
          WHERE season = {season}
        )
        SELECT sal.season, sal.week, sal.team, sal.opp, sal.salary,
               COALESCE(sal.dk_points, c.dk) AS actual
        FROM sal
        LEFT JOIN computed c ON c.team = sal.team AND c.week = sal.week
        WHERE COALESCE(sal.dk_points, c.dk) IS NOT NULL
        ORDER BY sal.season, sal.week, sal.team, sal.opp
        """
    )
    dst_key = ["season", "week", "team"]
    if not dst.empty and dst.duplicated(dst_key).any():
        bad = dst.loc[dst.duplicated(dst_key, keep=False), dst_key]
        raise ValueError(
            "DST salary replay is not one row per team-week after schedule "
            f"validation: {bad.head(8).to_dict('records')}")
    return panel, dst


TAIL_LINE_DEFAULT = 194.0  # min 2025 Milly-winning line; 0 disables


def _ownership_booster(replay_season: int):
    """OWN_MODEL=1: LightGBM ownership model fit on LineStar-backfilled
    contest ownership, WALK-FORWARD (seasons strictly before the replayed
    one -- point-in-time discipline applies to auxiliary models too).
    Returns None when no prior-season ownership exists (e.g. 2022)."""
    if own_mode() == "milly_fade":
        from ..research import milly_ownership as milly_own

        frame = milly_own.training_frame()
        tr = frame[frame.season < replay_season]
        if len(tr) < 1000:
            log.warning("MILLY OWN_MODEL: only %d prior-season ownership rows "
                        "before %s; falling back to naive", len(tr),
                        replay_season)
            return None
        log.info("MILLY OWN_MODEL: fit on %d exact-snapshot rows from seasons "
                 "< %s", len(tr), replay_season)
        return "milly", milly_own.train_contest_model(tr)

    from ..models import ownership as own_mod

    frame = own_mod.training_frame()
    tr = frame[frame.season < replay_season]
    if len(tr) < 1000:
        log.warning("OWN_MODEL: only %d prior-season ownership rows before "
                    "%s; falling back to naive", len(tr), replay_season)
        return None
    log.info("OWN_MODEL: fit on %d rows from seasons < %s", len(tr), replay_season)
    return "all_contest", own_mod.train(tr)


def _model_ownership(booster, frame: pd.DataFrame) -> np.ndarray:
    """Predicted pct -> naive_ownership-compatible weights (normalized
    within position), so LEVERAGE_PENALTY's scale and the field sampler's
    per-slot semantics are preserved. frame['proj'] stands in for the
    public points expectation the model trained on."""
    kind, model = (booster if isinstance(booster, tuple)
                   else ("all_contest", booster))
    if kind == "milly":
        from ..research import milly_ownership as milly_own

        f = milly_own.build_features(frame)
        pct = milly_own.predict_contest_model(model, f)
    else:
        from ..models import ownership as own_mod

        f = pd.DataFrame({
            "season": frame["season"], "week": frame["week"],
            "position": frame["pos"], "salary": frame["salary"],
            "proj_points": frame["proj"],
        })
        pct = own_mod.predict_ownership(model, f)
    out = np.zeros(len(frame))
    for _pos, idx in frame.groupby("pos").groups.items():
        loc = frame.index.get_indexer(idx)
        tot = pct[loc].sum()
        out[loc] = pct[loc] / tot if tot > 0 else 1.0 / max(len(loc), 1)
    return out


def _market_blend_worlds(
    frame: pd.DataFrame,
    frame_draws: np.ndarray,
    market: pd.DataFrame,
    model_weight: float,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Apply the prop blend to the exact post-shaping model worlds.

    Live lineup generation defines its model mean as ``draws.mean`` after
    TabPFN/empirical marginal shaping. Replay formerly blended the older
    LightGBM summary mean instead, so the UI and historical selector consumed
    different centers. This helper is shared by baseline and role-belief
    replay frames and also runs when ``market`` is empty: uncovered players
    remain model-only without taking a different alignment branch.
    """
    from ..models.blend import blend as _blend, shift_draws_to_means

    n_before = len(frame)
    if frame_draws.shape[0] != n_before:
        raise ValueError("market blend frame/draw rows do not align")
    frame = frame.merge(
        market, on=["season", "week", "gsis_id"], how="left",
        sort=False, validate="many_to_one")
    if len(frame) != n_before:
        raise ValueError("market merge fanned out rows")
    pre = frame_draws.mean(axis=1, dtype=np.float64)
    frame["proj_points"] = _blend(
        pre, frame.market_points.to_numpy(), model_weight)
    frame_draws = shift_draws_to_means(
        frame_draws, frame.proj_points.to_numpy())
    frame["consensus_div"] = np.where(
        frame.market_points.notna(),
        pre - frame.market_points.to_numpy(), 0.0)
    frame["model_points_pre"] = pre
    return frame, frame_draws, pre


def run(
    season: int,
    n_sims: int = 10_000,
    contest: Contest | None = None,
    n_entries: int = 40,
    field_size: int = 5_000,
    sharp_fraction: float = 0.15,
    tail_line: float | None = None,
    max_weeks: int | None = None,
) -> None:
    diagnostic_only = os.environ.get(
        "SCHAAKE_DIAG_ONLY", "").strip() not in ("", "0")
    if diagnostic_only and not os.environ.get("SCHAAKE_DIAG"):
        raise ValueError("SCHAAKE_DIAG_ONLY requires SCHAAKE_DIAG")
    panel, dst = load_panel_and_dst(season)
    proj, draws = replay_projections(panel, season, n_sims=n_sims,
                                     return_draws=True)
    if diagnostic_only:
        log.info(
            "Schaake dependence-only run complete for season %d; "
            "candidate generation skipped", season)
        return
    role_proj, role_draws = role_belief_projections(
        panel, season, n_sims=n_sims)
    if role_proj is not None:
        keys = ["season", "week", "gsis_id"]
        if not proj[keys].equals(role_proj[keys]):
            raise ValueError("baseline and role-belief projection rows differ")
    # Market blend (guide §7.7) with real prop-derived medians when the
    # season has prop_lines coverage; players without a line keep the
    # model projection (blend() falls back on NaN).
    try:
        from ..models.blend import effective_model_weight
        from ..models.prop_market import market_points

        blend_model_weight = effective_model_weight()
        mkt = market_points((season,))
        # Dedup + length guard (2026-08-04 audit): market_points dedups on
        # NAME norm, not gsis. The helper's many-to-one merge enforces this
        # even when an entire season has zero market rows.
        mkt = mkt.drop_duplicates(["season", "week", "gsis_id"])
        proj, draws, _pre = _market_blend_worlds(
            proj, draws, mkt, blend_model_weight)
        if role_proj is not None:
            # The control computes this too. It makes the candidate-only
            # belief vector exactly comparable to the rejected role arm.
            role_proj, role_draws, _ = _market_blend_worlds(
                role_proj, role_draws, mkt, blend_model_weight)
        covered = proj.market_points.notna()
        blend_delta = (proj.proj_points - proj.model_points_pre).abs()
        log.info(
            "prop-market blend: model_weight=%.3f covered=%d/%d "
            "covered_mean_abs_delta=%.6f uncovered_mean_abs_delta=%.6f",
            blend_model_weight, int(covered.sum()), len(proj),
            float(blend_delta[covered].mean()) if covered.any() else 0.0,
            float(blend_delta[~covered].mean()) if (~covered).any() else 0.0)
        # Weight sweep: MAE over blended rows only. A season with no props
        # is a valid model-only control, not a NaN diagnostic.
        have = covered.to_numpy()
        if have.any():
            act = proj.actual.to_numpy()[have]
            mdl, mrk = _pre[have], proj.market_points.to_numpy()[have]
            import numpy as _np

            print("  blend-weight sweep (w = model weight; blended rows):")
            for w in (0.0, 0.1, 0.2, 0.3, 0.4, 0.45, 0.5, 0.6, 0.7, 1.0):
                mae = _np.abs(w * mdl + (1 - w) * mrk - act).mean()
                print(f"    w={w:.2f}  MAE={mae:.4f}")
    except Exception:
        log.exception("prop market unavailable; replaying unblended")
    draws = apply_served_tail_scale(draws, proj.position)
    if role_proj is not None:
        role_draws = apply_served_tail_scale(role_draws, role_proj.position)
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
    n_route_tail = int(os.environ.get("N_ROUTE_TAIL", "0") or 0)
    if n_route_tail:
        if n_route_tail != 12:
            raise ValueError("the frozen Route Share candidate dose is 12")
        signal_columns = [
            "fp_route_source_season", "fp_route_source_week",
            "route_control_p30", "route_treatment_p30", "route_delta_30",
        ]
        if season in (2024, 2025):
            from ..analysis.fantasy_points_route_share import (
                load_route_tail_deltas,
            )

            signal = load_route_tail_deltas(season)
            before = len(proj)
            proj = proj.merge(
                signal[["season", "week", "gsis_id", *signal_columns]],
                on=["season", "week", "gsis_id"], how="left",
                validate="many_to_one",
            )
            if len(proj) != before:
                raise ValueError("Route Share signal merge fanned out rows")
            proj["route_delta_30"] = proj.route_delta_30.fillna(0.0)
            log.info(
                "Route Share tail signal: season=%d covered=%d/%d",
                season, int(proj.fp_route_source_season.notna().sum()),
                len(proj))
        else:
            for column in signal_columns:
                proj[column] = 0.0 if column == "route_delta_30" else np.nan
    n_coverage_tail = int(os.environ.get("N_COVERAGE_TAIL", "0") or 0)
    if n_coverage_tail:
        if n_coverage_tail != 12:
            raise ValueError("the frozen coverage-fit candidate dose is 12")
        signal_columns = [
            "opp", "fp_cov_receiver_source_season",
            "fp_cov_defense_source_season", "coverage_control_p30",
            "coverage_treatment_p30", "coverage_delta_30",
        ]
        if season in (2024, 2025):
            from ..analysis.fantasy_points_coverage_fit import (
                load_coverage_tail_deltas,
            )

            signal = load_coverage_tail_deltas(season)
            before = len(proj)
            # `opp` already exists on projection rows and is validated again
            # after the merge rather than creating an ambiguous suffix.
            proj = proj.merge(
                signal[[
                    "season", "week", "gsis_id",
                    *[column for column in signal_columns if column != "opp"],
                ]],
                on=["season", "week", "gsis_id"], how="left",
                validate="many_to_one",
            )
            if len(proj) != before:
                raise ValueError("coverage-fit signal merge fanned out rows")
            proj["coverage_delta_30"] = proj.coverage_delta_30.fillna(0.0)
            log.info(
                "coverage-fit tail signal: season=%d covered=%d/%d",
                season,
                int(proj.fp_cov_receiver_source_season.notna().sum()),
                len(proj),
            )
        else:
            for column in signal_columns:
                if column == "opp":
                    continue
                proj[column] = (
                    0.0 if column == "coverage_delta_30" else np.nan)
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
    slates = _limit_replay_slates(build_slates(proj, dst), max_weeks)
    belief_slates = None
    if role_proj is not None:
        belief_slates = _limit_replay_slates(
            build_slates(role_proj, dst), max_weeks)
        base_keys = [(int(s.season.iloc[0]), int(s.week.iloc[0]))
                     for s in slates]
        belief_keys = [(int(s.season.iloc[0]), int(s.week.iloc[0]))
                       for s in belief_slates]
        if base_keys != belief_keys:
            raise ValueError("baseline and role-belief slate weeks differ")
        for base, belief in zip(slates, belief_slates):
            if list(base.id) != list(belief.id):
                raise ValueError(
                    "baseline and role-belief slate player order differs")
    if max_weeks is not None:
        log.info("audit smoke: contest replay limited to %d week(s)",
                 max_weeks)
    result = engine_run(slates, contest,
                        n_entries=n_entries, field_size=field_size,
                        sharp_fraction=sharp_fraction, stack=stack,
                        draws=draws if use_tail else None,
                        tail_line=tail_line if use_tail else None,
                        belief_slates=belief_slates,
                        belief_draws=role_draws)
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
            # REPLAY_LINEUPS_TABLE env: diagnostic arms write to their
            # own table so concurrent runs can't clobber each other's
            # rosters (2026-08-05: the shared-table WRITE_TRUNCATE race
            # forced diag exports to be sequenced after ALL arms).
            _tbl = (os.environ.get("REPLAY_LINEUPS_TABLE")
                    or f"{settings.features}.replay_lineups")
            load_dataframe(pd.DataFrame(rows), _tbl,
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
