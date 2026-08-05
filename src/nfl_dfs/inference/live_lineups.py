"""Live classic sim-mode: the VALIDATED replay engine on the live slate.

Until 2026-08-03 the live classic path was MILP-on-projections plus a
normal-approximation confidence ranking, while every validated gain
(boom-draw candidates, tail-coverage selection of 40, and the adopted
EW draw shaping) lived only in replays. This module closes that fidelity
gap: features -> cold-start fill -> component models -> correlated sims
-> EW shaping -> the SAME candidate generation and coverage selection
the six-season panels graded (engine.tail_select_lineups).

Design choices, deliberate:
- Market blend enters as an additive per-player shift on the draws
  (mean = validated live blend; SHAPE = validated EW worlds).
- Same tournament tilts as replay build_slates: punt ceiling valuation,
  punt-boom archetype boost, chalk-fade on OUR objective only, low_own
  flags for MIN_LOWOWN.
- Deterministic seed so a rebuild of the same slate reproduces exactly.
- Callers (app) wrap this in a fallback to the plain MILP path: a slate
  built the old way beats a 500.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


LIVE_SIMS_DEFAULT = 30_000  # adopted 2026-08-03: +2 tails, best ROI and
# medians of its panel — 3x compute is pennies on ONE live slate while
# panels stay at 10k (research cadence). Env LIVE_SIMS overrides.


def build_slate_with_draws(season: int, week: int, n_sims: int | None = None,
                           seed: int = 42, lev_scale: float = 1.0,
                           apply_notes: bool = True,
                           allowed_ids: set | None = None,
                           ) -> tuple[pd.DataFrame, np.ndarray]:
    """Engine-ready slate frame + aligned draw matrix for the live week."""
    from ..backtest.field import naive_ownership
    from ..backtest.replay import apply_draw_shape, punt_boom_flags_live
    from ..models import coldstart, simulate
    from ..models.train_job import load_latest_component_models
    from ..optimizer.lineup import LEVERAGE_PENALTY, PUNT_MAX_SALARY
    from .. import notes as manual_notes
    from ..models.blend import blend, market_projection_frame
    from .run_projections import BLEND_WEIGHT, upcoming_slate_features

    import os as _os

    if n_sims is None:
        n_sims = int(_os.environ.get("LIVE_SIMS", LIVE_SIMS_DEFAULT))
    model, version = load_latest_component_models()
    feats = upcoming_slate_features(season, week)
    skill = feats[feats.dk_position.isin(["QB", "RB", "WR", "TE"])] \
        .reset_index(drop=True)
    skill = coldstart.fill_cold_start_features(skill)
    comps = model.predict_components(skill)
    if apply_notes:
        # Multiplier notes (chat-converted opportunity scalers). Gated by
        # the same "My notes" toggle as boost/ban prefs (2026-08-04) —
        # off = the untouched algorithm. NOTE: the STORED Sunday
        # projections (run_projections) bake these in; only this live
        # recompute honors the toggle fully.
        comps = manual_notes.apply_notes(comps, skill, season, week)
    sim = simulate.simulate(comps, n_sims=n_sims, seed=seed, keep_draws=True,
                            game_ids=skill.get("game_id"),
                            team_ids=skill.get("team"),
                            game_totals=skill.get("game_total"))
    # keys enable per-player marginal levers (TABPFN_MARGINALS) live —
    # without them the lever silently fell through to empirical
    # marginals, a replay/live parity gap (2026-08-04 audit).
    _kc = [c for c in ("season", "week", "gsis_id", "is_rookie")
           if c in skill.columns]
    draws = apply_draw_shape(sim.draws, skill.position, seed,
                             keys=skill[_kc]
                             if {"season", "week", "gsis_id"}
                             <= set(_kc) else None)

    # Market blend as an additive mean shift — draw shape untouched.
    # Props-first (review #5 round 3 parity fix): the replay blend that
    # validated BLEND_W uses prop-market points; DK PPG is the fallback.
    market = market_projection_frame(skill)
    try:
        from ..models.prop_market import market_points as _prop_points
        _pm = _prop_points((int(season),))
        _pm = _pm[_pm.week == int(week)]
        if len(_pm):
            _m = skill[["gsis_id"]].merge(
                _pm[["gsis_id", "market_points"]], on="gsis_id",
                how="left").market_points
            if _m.notna().sum() >= 0.3 * len(skill):
                market = _m.astype(float)
                log.info("live blend source: props (%d/%d rows)",
                         int(_m.notna().sum()), len(skill))
    except Exception:
        log.exception("live prop market unavailable; DK PPG stand-in")
    blended = blend(draws.mean(axis=1), np.asarray(market, dtype=float),
                    BLEND_WEIGHT)
    draws = draws + (blended - draws.mean(axis=1))[:, None]

    frame = pd.DataFrame({
        "id": skill.dk_player_id.astype(int),
        "gsis_id": skill.gsis_id,
        "name": skill.display_name,
        "pos": skill.position if "position" in skill.columns
               else skill.dk_position,
        "team": skill.get("team", skill.get("team_abbr")),
        "opp": skill.get("opponent"),
        "salary": pd.to_numeric(skill.salary, errors="coerce"),
        "season": season, "week": week,
    })
    frame["game_id"] = skill.get(
        "game_id", frame.team.astype(str) + "@" + frame.opp.astype(str))
    frame["draw_idx"] = np.arange(len(frame))
    frame["proj"] = draws.mean(axis=1)

    # DST rows: static live projections, no draws (draw_idx -1).
    try:
        from .dst_projections import project_dst

        dst = project_dst(season, week, model_version=version)
        if not dst.empty:
            d = pd.DataFrame({
                "id": dst.dk_player_id.astype(int),
                "gsis_id": "", "name": dst.display_name,
                "pos": "DST", "team": dst.get("team", dst.display_name),
                "opp": dst.get("opponent"),
                "salary": pd.to_numeric(dst.salary, errors="coerce"),
                "season": season, "week": week,
                "draw_idx": -1, "proj": dst.proj_points,
            })
            d["game_id"] = d.team.astype(str) + "@" + d.opp.astype(str)
            frame = pd.concat([frame, d], ignore_index=True)
    except Exception:
        log.exception("live DST rows unavailable; skill-only slate")

    frame = frame.dropna(subset=["salary", "proj"])
    frame = frame[frame.salary > 0]
    frame["salary"] = frame.salary.astype(int)
    frame = frame[~frame.id.duplicated()].reset_index(drop=True)
    # Slate restriction BEFORE ownership/fade (review #5 round 3): the
    # feature frame is the UNION of every upcoming draft group;
    # normalizing ownership over the union distorted both the chalk
    # fade and the own_shadow calibration for single-slate builds.
    if allowed_ids:
        frame = frame[frame.id.isin(allowed_ids)].reset_index(drop=True)

    # Tournament tilts, replay-identical (see backtest.replay.build_slates)
    punt = (frame.salary <= PUNT_MAX_SALARY) & (frame.draw_idx >= 0)
    p90 = np.percentile(draws, 90, axis=1)
    frame.loc[punt, "proj"] = np.maximum(
        frame.loc[punt, "proj"], p90[frame.loc[punt, "draw_idx"].to_numpy()])
    # OWN_MODEL=fade ADOPTED 2026-08-04 (QF arm, replay-validated): the
    # trained ownership model feeds the chalk fade (naive stays the field
    # yardstick elsewhere). Live mirror of backtest.replay's fade path;
    # falls back to naive WITH A WARNING only if the booster can't train
    # (contest_ownership empty — never true since 2022). "" disables.
    import os as _os

    own = None
    from ..backtest.replay import own_mode
    if own_mode():
        try:
            from ..backtest.replay import _model_ownership, _ownership_booster

            booster = _ownership_booster(int(season))
            if booster is not None:
                own = _model_ownership(booster, frame)
        except Exception:
            log.exception("ownership model unavailable; fade uses naive")
    if own is None:
        own = naive_ownership(frame)
        _own_src = "naive"
    else:
        _own_src = "booster"
    # Ownership shadow log (2026-08-05): the predicted-ownership vector
    # at BUILD TIME is what the in-season calibration (queue item 4)
    # grades against imported real ownership — and it is irrecoverable
    # after the build (late scratches shift the pool). Best-effort.
    try:
        from datetime import datetime, timezone

        from ..bq import load_dataframe
        from ..config import settings
        # the BOOSTER prediction is the one worth grading vs real
        # ownership (queue item 4) even though construction now uses
        # the naive fade (Addendum 80) — compute it for the log only.
        booster_own = None
        if _own_src != "booster":
            try:
                from ..backtest.replay import (_model_ownership,
                                               _ownership_booster)
                _b = _ownership_booster(int(season))
                if _b is not None:
                    booster_own = _model_ownership(_b, frame)
            except Exception:
                log.info("own-shadow: booster unavailable, logging naive only")
        shadow = pd.DataFrame({
            "generated_at": datetime.now(timezone.utc),
            "season": int(season), "week": int(week),
            "gsis_id": frame.get("gsis_id"),
            "name": frame.get("name"),
            "pos": frame.pos, "salary": frame.salary,
            "n_pool": len(frame),  # slate-restricted universe size
            "pred_own": own, "source": _own_src,
            "booster_own": (own if _own_src == "booster"
                            else booster_own),
        })

        def _write_shadow(df=shadow, src=_own_src):
            try:
                load_dataframe(df, f"{settings.predictions}.own_shadow",
                               write_disposition="WRITE_APPEND")
                log.info("own-shadow: %d rows (%s)", len(df), src)
            except Exception:
                log.exception("own-shadow write failed")

        import threading
        threading.Thread(target=_write_shadow, daemon=True).start()
    except Exception:
        log.exception("own-shadow logging failed; build unaffected")
    frame["proj_tourney"] = frame.proj - LEVERAGE_PENALTY * lev_scale * own
    # PUNT_BOOM default 0 ADOPTED 2026-08-05 (Addendum 77/79b — mirror
    # of the replay default): the archetype boost is deleted; env
    # restores it for A/Bs.
    _pb = float(_os.environ.get("PUNT_BOOM", "0") or 0)
    if _pb:
        try:
            boom = punt_boom_flags_live(season, week)
            keys = list(zip(frame.gsis_id, [season] * len(frame),
                            [week] * len(frame)))
            bmask = pd.Series([k in boom for k in keys], index=frame.index)
            bmask &= punt & (frame.pos != "DST")
            frame.loc[bmask, "proj_tourney"] += _pb
        except Exception:
            log.exception("live punt-boom flags unavailable; tilt skipped")
    slots = {"QB": 1.0, "RB": 2.5, "WR": 3.5, "TE": 1.2, "DST": 1.0}
    frame["low_own"] = (own * frame.pos.map(slots).fillna(1.0)
                        .to_numpy()) < 0.05
    return frame, draws


def build_sim_lineups(season: int, week: int, n_entries: int,
                      stack, tail_line: float, n_sims: int | None = None,
                      seed: int = 42, lev_scale: float = 1.0,
                      locks: set | None = None, bans: set | None = None,
                      allowed_ids: set | None = None,
                      theses: list | None = None,
                      apply_notes: bool = True) -> list:
    """Full validated pipeline on the live slate -> selected entries in
    coverage order (first = broadest boom coverage).

    locks: dk_player_ids required in every entry (plumbed through every
    candidate generator). bans: excluded from the pool entirely.
    allowed_ids: restrict to one DK slate's player set (draft_group_id
    requests) — draw_idx stays valid because rows only get DROPPED."""
    from ..backtest.engine import tail_select_lineups

    slate, draws = build_slate_with_draws(season, week, n_sims=n_sims,
                                          seed=seed, lev_scale=lev_scale,
                                          apply_notes=apply_notes,
                                          allowed_ids=allowed_ids)
    if allowed_ids:  # safety no-op — restriction now happens pre-fade
        slate = slate[slate.id.isin(allowed_ids)]
    if bans:
        slate = slate[~slate.id.isin(bans)]
    if apply_notes:
        # Converted watch-notes (boost/ban prefs) applied INSIDE the sim
        # path (2026-08-04 — previously MILP-only, so the default build
        # silently ignored them). apply_notes=False = pure algorithm.
        try:
            from ..notes import BOOST_BONUS, _prefs_table, norm_name
            from ..bq import query_df

            p = query_df(f"SELECT norm, kind FROM `{_prefs_table()}` WHERE "
                         f"season={int(season)} AND week={int(week)}")
            if not p.empty:
                nb = set(p[p.kind == "ban"].norm)
                bo = set(p[p.kind == "boost"].norm)
                norms = slate.name.map(norm_name)
                drop = norms.isin(nb) & ~slate.id.isin(locks or set())
                slate = slate[~drop]
                bmask = slate.name.map(norm_name).isin(bo)
                slate.loc[bmask, "proj_tourney"] += BOOST_BONUS
                log.info("notes applied in sim path: %d banned, %d boosted",
                         int(drop.sum()), int(bmask.sum()))
        except Exception:
            log.exception("note prefs unavailable; building without them")
    slate = slate.reset_index(drop=True)
    if locks:
        missing = set(locks) - set(slate.id)
        if missing:
            raise ValueError(f"locked players not in slate: {sorted(missing)}")
    pool = slate.to_dict("records")
    # Persist every live candidate (reranker training data, September
    # designs #3 — irrecoverable post-build). Explicit destination +
    # async write: never mutates global env, never blocks the build.
    from ..config import settings as _settings
    lineups = tail_select_lineups(
        slate, pool, draws, tail_line=tail_line, n_entries=n_entries,
        stack=stack, objective_col="proj_tourney",
        locks=set(locks or ()), theses=theses,
        cand_log_table=f"{_settings.predictions}.live_candidates",
        cand_log_async=True)
    return lineups
