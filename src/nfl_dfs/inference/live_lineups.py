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


class RoleBeliefUnavailable(RuntimeError):
    """The promoted role-union path could not reproduce its alternate model."""


class LatentRoleUnavailable(RuntimeError):
    """The prospective latent-role shadow could not build its frozen book."""


def _apply_live_inactive_policy(
    skill: pd.DataFrame, season: int,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Redistribute known-vacated usage, then remove inactive slate rows.

    Stored projection snapshots retain O/IR rows at zero for auditing.  A
    live simulation book has a different contract: those rows must not enter
    the component sampler or any legal-lineup pool.  Status exclusion is
    therefore driven directly by the current DK/injury columns and remains
    effective even if the historical cascade inputs are unavailable.
    """
    from . import cascade_adjust
    from .run_projections import _cascade_adjuster

    out_ids = tuple(cascade_adjust.find_out_players(skill))
    if not out_ids:
        return skill, out_ids

    adjusted = skill
    adjust = _cascade_adjuster(int(season))
    if adjust is not None:
        adjusted, adjusted_ids = adjust(skill)
        if set(adjusted_ids) != set(out_ids):
            raise RuntimeError(
                "live inactive cascade disagrees with current slate status"
            )
    active = adjusted[~adjusted.gsis_id.isin(out_ids)].reset_index(drop=True)
    if active.empty:
        raise RuntimeError("live inactive policy removed every skill player")
    log.info(
        "live inactive policy excluded %d player(s) before simulation: %s",
        len(out_ids), ", ".join(out_ids),
    )
    return active, out_ids


def _log_ownership_shadow(
    frame: pd.DataFrame,
    own: np.ndarray,
    own_source: str,
    season: int,
    week: int,
) -> None:
    """Best-effort asynchronous capture of the irrecoverable live own vector."""
    try:
        from datetime import datetime, timezone

        from ..bq import load_dataframe
        from ..config import settings

        # The booster prediction is what the in-season calibration grades
        # even when construction falls back to the naive fade.
        booster_own = None
        if own_source != "booster":
            try:
                from ..backtest.replay import (
                    _model_ownership, _ownership_booster)

                booster = _ownership_booster(int(season))
                if booster is not None:
                    booster_own = _model_ownership(booster, frame)
            except Exception:
                log.info("own-shadow: booster unavailable, logging naive only")
        shadow = pd.DataFrame({
            "generated_at": datetime.now(timezone.utc),
            "season": int(season), "week": int(week),
            "gsis_id": frame.get("gsis_id"),
            "name": frame.get("name"),
            "pos": frame.pos, "salary": frame.salary,
            "n_pool": len(frame),
            "pred_own": own, "source": own_source,
            "booster_own": (own if own_source == "booster" else booster_own),
        })

        def _write_shadow(df=shadow, src=own_source):
            try:
                load_dataframe(
                    df, f"{settings.predictions}.own_shadow",
                    write_disposition="WRITE_APPEND")
                log.info("own-shadow: %d rows (%s)", len(df), src)
            except Exception:
                log.exception("own-shadow write failed")

        import threading
        threading.Thread(target=_write_shadow, daemon=True).start()
    except Exception:
        log.exception("own-shadow logging failed; build unaffected")


def build_slate_with_draws(season: int, week: int, n_sims: int | None = None,
                           seed: int = 42, lev_scale: float = 1.0,
                           apply_notes: bool = True,
                           model_variant: str | None = None,
                           allowed_ids: set | None = None,
                           salary_overrides: dict[int, int] | None = None,
                           policy_env: dict[str, str] | None = None,
                           expected_model_k: int | None = None,
                           required_model_features: tuple[str, ...] = (),
                           forbidden_model_features: tuple[str, ...] = (),
                           route_source_policy: bool = False,
                           log_ownership_shadow: bool = True,
                           ) -> tuple[pd.DataFrame, np.ndarray]:
    """Engine-ready slate frame + aligned draw matrix for the live week."""
    from ..backtest.field import naive_ownership
    from ..backtest.replay import (
        apply_draw_shape,
        apply_served_position_scales,
        apply_served_tail_scale,
        punt_boom_flags_live,
    )
    from ..models import coldstart, simulate
    from ..models.train_job import load_latest_component_models
    from ..optimizer.lineup import LEVERAGE_PENALTY, PUNT_MAX_SALARY
    from .. import notes as manual_notes
    from ..models.blend import (blend, effective_model_weight,
                                market_projection_frame,
                                shift_draws_to_means)
    from .run_projections import upcoming_slate_features

    import os as _os

    runtime_env = _os.environ if policy_env is None else policy_env

    if n_sims is None:
        n_sims = int(runtime_env.get("LIVE_SIMS", LIVE_SIMS_DEFAULT))
    if model_variant is None:
        model, version = load_latest_component_models()
    else:
        model, version = load_latest_component_models(model_variant)
        from ..models.components import effective_ensemble_size
        from ..models.train_job import registered_ensemble_size

        expected_k = (expected_model_k if expected_model_k is not None
                      else effective_ensemble_size(runtime_env))
        loaded_k = registered_ensemble_size(model)
        if loaded_k != expected_k:
            raise RuntimeError(
                f"registry variant {model_variant} contains K={loaded_k}, "
                f"but MODEL_ENSEMBLE={expected_k}")
    if required_model_features or forbidden_model_features:
        from .route_share_shadow import validate_component_feature_contract

        validate_component_feature_contract(
            model,
            registry_variant=model_variant or "canonical",
            required=required_model_features,
            forbidden=forbidden_model_features,
        )
    feats = upcoming_slate_features(season, week)
    skill = feats[feats.dk_position.isin(["QB", "RB", "WR", "TE"])] \
        .reset_index(drop=True)
    skill = coldstart.fill_cold_start_features(skill)
    skill, _ = _apply_live_inactive_policy(skill, season)
    if route_source_policy:
        from .route_share_shadow import apply_live_route_policy

        skill = apply_live_route_policy(skill, season, week)
    comps = model.predict_components(skill)
    if apply_notes:
        # Multiplier notes (chat-converted opportunity scalers). Gated by
        # the same "My notes" toggle as boost/ban prefs (2026-08-04) —
        # off = the untouched algorithm. NOTE: the STORED Sunday
        # projections (run_projections) bake these in; only this live
        # recompute honors the toggle fully.
        comps = manual_notes.apply_notes(comps, skill, season, week)
    from ..research import sis_asoe_final_served as asoe_module

    asoe_enabled = asoe_module.treatment_enabled(runtime_env)
    sim = simulate.simulate(
        comps,
        n_sims=n_sims,
        seed=seed,
        keep_draws=True,
        game_ids=skill.get("game_id"),
        team_ids=skill.get("team"),
        game_totals=skill.get("game_total"),
        keep_target_receiving=asoe_enabled,
        env=runtime_env,
    )
    if asoe_enabled:
        multipliers, asoe_audit = asoe_module.live_target_allocation_multipliers(
            skill, comps
        )
        treatment_sim = simulate.simulate(
            comps,
            n_sims=n_sims,
            seed=seed,
            game_ids=skill.get("game_id"),
            team_ids=skill.get("team"),
            game_totals=skill.get("game_total"),
            target_allocation_multipliers=multipliers,
            keep_target_receiving=True,
            env=runtime_env,
        )
        changed_rows = ~np.isclose(multipliers, 1.0, rtol=0, atol=1e-15)
        asoe_raw = sim.draws.copy()
        asoe_raw[changed_rows] = (
            sim.draws[changed_rows]
            - sim.target_receiving_draws[changed_rows]
            + treatment_sim.target_receiving_draws[changed_rows]
        )
        sim.draws = asoe_module.rank_transport(sim.draws, asoe_raw)
        log.info("live SIS ASOE target allocation audit=%s", asoe_audit)
    # keys enable per-player marginal levers (TABPFN_MARGINALS) live —
    # without them the lever silently fell through to empirical
    # marginals, a replay/live parity gap (2026-08-04 audit).
    _kc = [c for c in ("season", "week", "gsis_id", "is_rookie")
           if c in skill.columns]
    draws = apply_draw_shape(sim.draws, skill.position, seed,
                             keys=skill[_kc]
                             if {"season", "week", "gsis_id"}
                             <= set(_kc) else None,
                             env=runtime_env)
    model_points_pre = draws.mean(axis=1, dtype=np.float64)

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
    market_values = np.asarray(market, dtype=float)
    blended = blend(model_points_pre, market_values,
                    effective_model_weight(runtime_env))
    draws = shift_draws_to_means(draws, blended)
    draws = apply_served_tail_scale(draws, skill.position, env=runtime_env)
    draws = apply_served_position_scales(
        draws, skill.position, env=runtime_env)

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
    frame["model_points_pre"] = model_points_pre
    frame["market_points"] = market_values
    frame["mean_projection"] = draws.mean(axis=1, dtype=np.float64)
    frame["proj_p10"] = np.percentile(draws, 10, axis=1)
    frame["proj_p50"] = np.percentile(draws, 50, axis=1)
    frame["proj_p90"] = np.percentile(draws, 90, axis=1)
    frame["proj_std"] = draws.std(axis=1, dtype=np.float64)
    for column in comps.columns:
        frame[f"component_mean_{column}"] = pd.to_numeric(
            comps[column], errors="coerce").to_numpy()
    for column in (
        "fp_route_source_season", "fp_route_source_week",
        "fp_route_source_sha256", "fp_route_prior_observations",
        "fp_route_share_last", "fp_route_share_l4",
        "fp_route_share_jump", "fp_route_cross_season",
        "fp_route_fallback", "fp_route_shadow_supported",
    ):
        if column in skill:
            frame[column] = skill[column].to_numpy()

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
    # `upcoming_slate_features` deliberately deduplicates the UNION of
    # upcoming classic draft groups toward the largest group.  That is the
    # right feature universe, but not necessarily the price list for a
    # selected Sunday/afternoon slate.  Apply the exact group snapshot
    # supplied by the app before *any* salary-sensitive tilt or solve.
    if salary_overrides:
        exact_salary = frame.id.map(salary_overrides)
        frame.loc[exact_salary.notna(), "salary"] = exact_salary.dropna()
        frame["salary"] = frame.salary.astype(int)

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
    if own_mode(runtime_env):
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
    if log_ownership_shadow:
        _log_ownership_shadow(frame, own, _own_src, season, week)
    frame["proj_tourney"] = frame.proj - LEVERAGE_PENALTY * lev_scale * own
    # PUNT_BOOM default 0 ADOPTED 2026-08-05 (Addendum 77/79b — mirror
    # of the replay default): the archetype boost is deleted; env
    # restores it for A/Bs.
    _pb = float(runtime_env.get("PUNT_BOOM", "0") or 0)
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
    frame.attrs["model_version"] = version
    return frame, draws


def build_sim_lineups(season: int, week: int, n_entries: int,
                      stack, tail_line: float, n_sims: int | None = None,
                      seed: int = 42, lev_scale: float = 1.0,
                      locks: set | None = None, bans: set | None = None,
                      allowed_ids: set | None = None,
                      salary_overrides: dict[int, int] | None = None,
                      theses: list | None = None,
                      apply_notes: bool = True,
                      model_variant: str | None = None,
                      cand_log_table: str | None = None,
                      cand_log_async: bool = True,
                      cand_log_required: bool = False,
                      panel_run_id: str | None = None,
                      candidate_run_type: str | None = None,
                      policy_env: dict[str, str] | None = None,
                      expected_model_k: int | None = None,
                      belief_model_variant: str | None = None,
                      model_required_features: tuple[str, ...] = (),
                      model_forbidden_features: tuple[str, ...] = (),
                      belief_required_features: tuple[str, ...] = (),
                      belief_forbidden_features: tuple[str, ...] = (),
                      route_source_policy: bool = False,
                      distribution_artifact_spec=None,
                      _candidate_capture=None,
                      _control_candidate_capture=None,
                      _candidate_transform=None,
                      _explicit_epistemic_scenarios=None,
                      _latent_scenario_receipt=None,
                      _latent_scenario_factory=None,
                      _multiseed_inner: bool = False,
                      _log_ownership_shadow: bool = True) -> list:
    """Full validated pipeline on the live slate -> selected entries in
    coverage order (first = broadest boom coverage).

    locks: dk_player_ids required in every entry (plumbed through every
    candidate generator). bans: excluded from the pool entirely.
    allowed_ids: restrict to one DK slate's player set (draft_group_id
    requests) — draw_idx stays valid because rows only get DROPPED."""
    from ..backtest.engine import tail_select_lineups

    runtime_env = policy_env or {}
    portfolio = runtime_env.get("MULTISEED_PORTFOLIO", "").upper()
    multiseed_portfolios = {
        "CBWU", "CBWU_ARCHETYPE_SHADOW", "CBWU_LATENT_ROLE_SHADOW",
    }
    if portfolio and portfolio not in multiseed_portfolios:
        raise ValueError(f"unknown MULTISEED_PORTFOLIO={portfolio!r}")
    if portfolio in multiseed_portfolios and not _multiseed_inner:
        if _candidate_transform is not None:
            raise ValueError("outer CBWU build cannot accept a candidate transform")
        if distribution_artifact_spec is not None:
            raise ValueError(
                "CBWU live build cannot capture a single-seed distribution artifact")
        if (_explicit_epistemic_scenarios is not None
                or _latent_scenario_receipt is not None):
            raise ValueError(
                "outer CBWU build cannot receive one seed's latent scenarios")
        if portfolio == "CBWU_LATENT_ROLE_SHADOW":
            if _latent_scenario_factory is None:
                raise ValueError("latent-role CBWU requires a scenario factory")
        elif _latent_scenario_factory is not None:
            raise ValueError(
                "latent-role scenario factory requires its named shadow")
        if (
            _control_candidate_capture is not None
            and portfolio != "CBWU_ARCHETYPE_SHADOW"
        ):
            raise ValueError(
                "paired control capture requires CBWU_ARCHETYPE_SHADOW"
            )
        from .archetype_candidate_allocator import ALLOCATION_VERSION
        from .multiseed_portfolio import (
            combine_archetype_shadow_books,
            combine_cbwu_books,
        )

        raw_pairs = runtime_env.get("MULTISEED_SEED_PAIRS", "")
        parsed: list[tuple[str, int, int]] = []
        try:
            for item in raw_pairs.split(";"):
                label, values = item.split("=", 1)
                projection_seed, role_seed = values.split(":", 1)
                parsed.append((label, int(projection_seed), int(role_seed)))
        except (TypeError, ValueError) as exc:
            raise ValueError("MULTISEED_SEED_PAIRS is malformed") from exc
        labels = tuple(label for label, _, _ in parsed)
        if labels != ("R0", "R1", "R2", "R3", "R4"):
            raise ValueError("CBWU requires registered R0--R4 seed order")
        try:
            worlds_per_block = int(
                runtime_env["MULTISEED_WORLDS_PER_BLOCK"])
            candidate_entry_basis = int(
                runtime_env["MULTISEED_CANDIDATE_ENTRY_BASIS"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("CBWU world/budget contract is missing") from exc
        if worlds_per_block <= 0 or candidate_entry_basis != 80:
            raise ValueError("CBWU requires positive worlds and an 80-entry basis")
        if n_entries > candidate_entry_basis:
            raise ValueError(
                "CBWU supports at most its licensed 80-entry selection book")
        if n_sims is not None and int(n_sims) != worlds_per_block:
            raise ValueError(
                "CBWU n_sims must match MULTISEED_WORLDS_PER_BLOCK")
        if portfolio == "CBWU_ARCHETYPE_SHADOW":
            if runtime_env.get("ARCHETYPE_ALLOCATION_VERSION") != \
                    ALLOCATION_VERSION:
                raise ValueError("archetype allocation version differs")
            try:
                archetype_tail_line = float(runtime_env["ARCHETYPE_TAIL_LINE"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("archetype tail line contract is missing") from exc
            if abs(float(tail_line) - archetype_tail_line) > 1e-12:
                raise ValueError("archetype shadow tail line differs")

        captured = {}

        def _run_seed(
            label: str, projection_seed: int, role_seed: int, *,
            transform=None, persist: bool = False,
        ):
            seed_env = dict(runtime_env)
            seed_env["REPLAY_PROJECTION_SEED"] = str(projection_seed)
            seed_env["ROLE_BELIEF_SEED"] = str(role_seed)
            seed_env["MULTISEED_SOURCE_LABEL"] = label
            holder = []
            result = build_sim_lineups(
                season, week, n_entries=n_entries, stack=stack,
                tail_line=tail_line, n_sims=worlds_per_block,
                seed=projection_seed, lev_scale=lev_scale,
                locks=locks, bans=bans, allowed_ids=allowed_ids,
                salary_overrides=salary_overrides, theses=theses,
                apply_notes=apply_notes, model_variant=model_variant,
                cand_log_table=(cand_log_table if persist else ""),
                cand_log_async=(cand_log_async if persist else False),
                cand_log_required=(cand_log_required if persist else False),
                panel_run_id=panel_run_id,
                candidate_run_type=candidate_run_type,
                policy_env=seed_env, expected_model_k=expected_model_k,
                belief_model_variant=belief_model_variant,
                model_required_features=model_required_features,
                model_forbidden_features=model_forbidden_features,
                belief_required_features=belief_required_features,
                belief_forbidden_features=belief_forbidden_features,
                route_source_policy=route_source_policy,
                _candidate_capture=(holder.append if transform is None else None),
                _control_candidate_capture=None,
                _candidate_transform=transform,
                _explicit_epistemic_scenarios=None,
                _latent_scenario_receipt=None,
                _latent_scenario_factory=_latent_scenario_factory,
                _multiseed_inner=True,
                _log_ownership_shadow=(persist and _log_ownership_shadow),
            )
            if transform is None:
                if len(holder) != 1:
                    raise RuntimeError(
                        f"CBWU {label} produced {len(holder)} candidate books")
                captured[label] = holder[0]
            return result

        # Produce the non-base books first.  No partial result is returned or
        # persisted; the final R0 call runs only after all four succeeded.
        for label, projection_seed, role_seed in parsed[1:]:
            _run_seed(label, projection_seed, role_seed)

        def _combine(r0_batch):
            books = {"R0": r0_batch, **captured}
            if portfolio == "CBWU_ARCHETYPE_SHADOW":
                if _control_candidate_capture is not None:
                    _control_candidate_capture(combine_cbwu_books(
                        books,
                        labels,
                        expected_worlds_per_book=worlds_per_block,
                    ))
                combined = combine_archetype_shadow_books(
                    books,
                    labels,
                    tail_line=archetype_tail_line,
                    expected_worlds_per_book=worlds_per_block,
                )
            else:
                combined = combine_cbwu_books(
                    books, labels,
                    expected_worlds_per_book=worlds_per_block)
                if portfolio == "CBWU_LATENT_ROLE_SHADOW":
                    from ..backtest.engine import CandidateBatch

                    latent_seed_receipts = {
                        name: {
                            "latent_optimization_receipt": tuple(
                                books[name].metadata.get(
                                    "latent_optimization_receipt", ()
                                )
                            ),
                            "latent_scenario_receipt": dict(
                                books[name].metadata.get(
                                    "latent_scenario_receipt", {}
                                )
                            ),
                        }
                        for name in labels
                    }
                    combined = CandidateBatch(
                        candidates=combined.candidates,
                        candidate_totals=combined.candidate_totals,
                        player_ids=combined.player_ids,
                        player_rows=combined.player_rows,
                        row_draws=combined.row_draws,
                        all_tags=combined.all_tags,
                        metadata={
                            **combined.metadata,
                            "portfolio": "CBWU_LATENT_ROLE_SHADOW",
                            "production_enabled": False,
                            "prospective_shadow_id": runtime_env.get(
                                "PROSPECTIVE_SHADOW_ID", ""),
                            "uses_realized_outcomes": False,
                            "latent_seed_receipts": latent_seed_receipts,
                        },
                    )
            if _candidate_capture is not None:
                _candidate_capture(combined)
            return combined

        label, projection_seed, role_seed = parsed[0]
        return _run_seed(
            label, projection_seed, role_seed,
            transform=_combine, persist=True)

    slate, draws = build_slate_with_draws(
        season, week, n_sims=n_sims, seed=seed, lev_scale=lev_scale,
        apply_notes=apply_notes, model_variant=model_variant,
        allowed_ids=allowed_ids, salary_overrides=salary_overrides,
        policy_env=policy_env, expected_model_k=expected_model_k,
        required_model_features=model_required_features,
        forbidden_model_features=model_forbidden_features,
        route_source_policy=route_source_policy,
        log_ownership_shadow=_log_ownership_shadow)
    model_version = slate.attrs.get("model_version")
    wants_role = (
        int(runtime_env.get("N_EPISTEMIC", "0") or 0) > 0
        and runtime_env.get("EPISTEMIC_FAMILY") == "role_draws"
    )
    wants_latent_role = (
        int(runtime_env.get("N_EPISTEMIC", "0") or 0) > 0
        and runtime_env.get("EPISTEMIC_FAMILY") == "latent_role_states"
    )
    if wants_latent_role:
        if not belief_model_variant:
            raise LatentRoleUnavailable(
                "latent-role policy requires the tail_k1_role registry variant")
        if (
            _latent_scenario_factory is None
            and _explicit_epistemic_scenarios is None
        ):
            raise LatentRoleUnavailable(
                "latent-role policy requires conditional scenarios")
        if (
            _latent_scenario_factory is not None
            and _explicit_epistemic_scenarios is not None
        ):
            raise ValueError(
                "latent-role scenarios must come from one source")
    elif (
        _latent_scenario_factory is not None
        or _explicit_epistemic_scenarios is not None
        or _latent_scenario_receipt is not None
    ):
        raise ValueError(
            "latent-role scenario inputs require the named latent family")
    belief_slate = None
    belief_draws = None
    role_model_version = None
    if wants_role:
        if not belief_model_variant:
            raise RoleBeliefUnavailable(
                "role-union policy requires a role model registry variant")
        try:
            belief_seed = int(runtime_env.get("ROLE_BELIEF_SEED", seed))
            belief_slate, belief_draws = build_slate_with_draws(
                season, week, n_sims=n_sims, seed=belief_seed,
                lev_scale=lev_scale, apply_notes=apply_notes,
                model_variant=belief_model_variant, allowed_ids=allowed_ids,
                salary_overrides=salary_overrides, policy_env=policy_env,
                expected_model_k=expected_model_k,
                required_model_features=belief_required_features,
                forbidden_model_features=belief_forbidden_features,
                route_source_policy=route_source_policy,
                log_ownership_shadow=False)
            role_model_version = belief_slate.attrs.get("model_version")
        except Exception as exc:
            raise RoleBeliefUnavailable(
                f"alternate role model {belief_model_variant} unavailable: "
                f"{type(exc).__name__}: {str(exc)[:180]}") from exc
    if allowed_ids:  # safety no-op — restriction now happens pre-fade
        slate = slate[slate.id.isin(allowed_ids)]
        if belief_slate is not None:
            belief_slate = belief_slate[belief_slate.id.isin(allowed_ids)]
    if bans:
        slate = slate[~slate.id.isin(bans)]
        if belief_slate is not None:
            belief_slate = belief_slate[~belief_slate.id.isin(bans)]
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
                if belief_slate is not None:
                    belief_norms = belief_slate.name.map(norm_name)
                    belief_drop = (
                        belief_norms.isin(nb)
                        & ~belief_slate.id.isin(locks or set()))
                    belief_slate = belief_slate[~belief_drop]
                    belief_boost = belief_slate.name.map(norm_name).isin(bo)
                    belief_slate.loc[
                        belief_boost, "proj_tourney"] += BOOST_BONUS
                log.info("notes applied in sim path: %d banned, %d boosted",
                         int(drop.sum()), int(bmask.sum()))
        except Exception:
            log.exception("note prefs unavailable; building without them")
    slate = slate.reset_index(drop=True)
    if belief_slate is not None:
        belief_slate = belief_slate.reset_index(drop=True)
        if set(belief_slate.id) != set(slate.id):
            raise RoleBeliefUnavailable(
                "baseline and alternate role-model player pools differ")
        belief_slate = (belief_slate.set_index("id", drop=False)
                        .loc[slate.id.tolist()].reset_index(drop=True))
        if list(belief_slate.id) != list(slate.id):
            raise RoleBeliefUnavailable(
                "baseline and alternate role-model player order differs")
    if locks:
        missing = set(locks) - set(slate.id)
        if missing:
            raise ValueError(f"locked players not in slate: {sorted(missing)}")
    latent_scenarios = _explicit_epistemic_scenarios
    latent_scenario_receipt = _latent_scenario_receipt
    if wants_latent_role and _latent_scenario_factory is not None:
        try:
            built = _latent_scenario_factory(
                season=int(season),
                week=int(week),
                source_label=str(runtime_env.get(
                    "MULTISEED_SOURCE_LABEL", "single")),
                projection_seed=int(seed),
                role_seed=int(runtime_env.get("ROLE_BELIEF_SEED", seed)),
                n_sims=int(draws.shape[1]),
                slate=slate.copy(deep=True),
                conditional_model_variant=str(belief_model_variant),
                policy_env=dict(runtime_env),
            )
        except Exception as exc:
            raise LatentRoleUnavailable(
                "latent-role scenario factory failed: "
                f"{type(exc).__name__}: {str(exc)[:180]}"
            ) from exc
        if (
            not isinstance(built, tuple)
            or len(built) != 2
            or not isinstance(built[1], dict)
        ):
            raise LatentRoleUnavailable(
                "latent-role scenario factory returned a malformed bundle")
        latent_scenarios, latent_scenario_receipt = built
    if wants_latent_role:
        if not isinstance(latent_scenario_receipt, dict):
            raise LatentRoleUnavailable(
                "latent-role scenario receipt is unavailable")
        if latent_scenario_receipt.get("uses_realized_outcomes") is not False:
            raise LatentRoleUnavailable(
                "latent-role scenario receipt is not score-free")
    if distribution_artifact_spec is not None:
        if belief_slate is None or belief_draws is None:
            raise RuntimeError(
                "player-distribution capture requires the paired belief model")
        from .route_share_shadow import persist_distribution_artifact

        artifact_uri, artifact_sha = persist_distribution_artifact(
            slate, draws, belief_slate, belief_draws,
            season=season, week=week,
            model_version=str(model_version or ""),
            belief_model_version=str(role_model_version or ""),
            spec=distribution_artifact_spec,
        )
        slate["route_distribution_artifact_uri"] = artifact_uri
        slate["route_distribution_artifact_sha256"] = artifact_sha
        slate["route_distribution_arm"] = distribution_artifact_spec.arm
        slate["route_distribution_model_variant"] = (
            distribution_artifact_spec.model_variant)
        slate["route_distribution_belief_variant"] = (
            distribution_artifact_spec.belief_model_variant)
    pool = slate.to_dict("records")
    # Persist every live candidate (reranker training data, September
    # designs #3 — irrecoverable post-build). App builds use async writes so
    # storage never blocks a user response; prospective shadows request a
    # synchronous write so a successful job means the pre-lock artifact is
    # durably frozen.
    from ..config import settings as _settings
    if cand_log_table is None:
        cand_log_table = f"{_settings.predictions}.live_candidates"
    try:
        latent_optimization_receipt = [] if wants_latent_role else None
        lineups = tail_select_lineups(
            slate, pool, draws, tail_line=tail_line, n_entries=n_entries,
            stack=stack, objective_col="proj_tourney",
            candidate_multiple=int(runtime_env.get("CAND_MULT", "2")),
            candidate_generation_entries=int(runtime_env.get(
                "MULTISEED_CANDIDATE_ENTRY_BASIS", n_entries) or n_entries),
            n_game_stacks=int(runtime_env.get("N_GAMESTACK", "4")),
            locks=set(locks or ()), theses=theses,
            cand_log_table=cand_log_table, cand_log_async=cand_log_async,
            cand_log_required=cand_log_required,
            panel_run_id=panel_run_id, candidate_run_type=candidate_run_type,
            policy_env=policy_env, belief_slate=belief_slate,
            belief_draws=belief_draws,
            explicit_epistemic_scenarios=latent_scenarios,
            latent_optimization_receipt=latent_optimization_receipt,
            latent_scenario_receipt=latent_scenario_receipt,
            candidate_capture=_candidate_capture,
            candidate_transform=_candidate_transform)
    except RuntimeError as exc:
        if wants_role and "role-belief generator produced" in str(exc):
            raise RoleBeliefUnavailable(str(exc)) from exc
        if wants_latent_role and "latent role" in str(exc).lower():
            raise LatentRoleUnavailable(str(exc)) from exc
        raise
    for lineup in lineups:
        lineup.model_version = model_version
        lineup.role_model_version = (
            latent_scenario_receipt.get("conditional_model_version")
            if wants_latent_role else role_model_version
        )
    return lineups
