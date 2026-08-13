"""Frozen summary refit and final-served position calibration diagnostic."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os

import numpy as np
import pandas as pd

from . import served_tail_calibration as control
from . import served_tail_recalibration as global_recalibration
from ..ingest.fantasy_points_route import PANEL_ID
from ..models import calibration
from ..models.blend import permutation_invariant_row_mean


CALIBRATION_SEASONS = (2019, 2021, 2022)
EVALUATION_SEASONS = (2023, 2024, 2025)
POSITIONS = ("QB", "RB", "WR", "TE")
QUANTILES = ((90, 0.90), (95, 0.95), (99, 0.99))
POSITION_SCALE_GRID = np.round(np.arange(0.75, 1.5001, 0.005), 3)
PIT_V2_FLAG = "SERVED_POSITION_CALIBRATION_PIT_V2"
PIT_V2_CACHE = "tabpfn_projections_pit_v2"


def execution_contract(panel_id: str, env: dict | None = None) -> dict:
    """Resolve the immutable v1 or explicitly licensed PIT-clean v2 law."""
    values = os.environ if env is None else env
    pit_v2 = str(values.get(PIT_V2_FLAG, "")).strip().lower() in {
        "1", "true", "yes", "on",
    }
    if not pit_v2:
        if panel_id != PANEL_ID:
            raise ValueError(
                f"position calibration protocol is frozen to {PANEL_ID}")
        control._validate_environment()
        return {
            "version": "v1",
            "panel": PANEL_ID,
            "model_ensemble": 1,
            "tabpfn_table": "tabpfn_projections",
        }

    ensemble_text = str(values.get("MODEL_ENSEMBLE", "")).strip()
    if ensemble_text not in {"1", "3"}:
        raise ValueError("PIT-clean position calibration requires MODEL_ENSEMBLE=1 or 3")
    if str(values.get("EXTRA_FEATURES", "")).strip():
        raise ValueError("PIT-clean position calibration requires blank EXTRA_FEATURES")
    active = [
        key for key in control.FORBIDDEN_ACTIVE_ENVS
        if str(values.get(key, "")).strip().lower()
        not in ("", "0", "off", "false", "none")
    ]
    if active:
        raise ValueError(
            f"PIT-clean position calibration has active levers: {active}")
    cache = str(values.get("TABPFN_MARGINAL_TABLE", "")).strip()
    if cache != PIT_V2_CACHE:
        raise ValueError(
            f"PIT-clean position calibration requires {PIT_V2_CACHE}")
    if not panel_id or panel_id == PANEL_ID:
        raise ValueError("PIT-clean position calibration requires a repaired panel")
    return {
        "version": "v2",
        "panel": panel_id,
        "model_ensemble": int(ensemble_text),
        "tabpfn_table": PIT_V2_CACHE,
    }


@contextmanager
def _served_environment(contract: dict):
    """Reproduce the selected base while retaining v1 defaults unchanged."""
    production = dict(control.PRODUCTION_ENV)
    production["MODEL_ENSEMBLE"] = str(contract["model_ensemble"])
    production["TABPFN_MARGINAL_TABLE"] = (
        "" if contract["version"] == "v1" else contract["tabpfn_table"]
    )
    prior = {key: os.environ.get(key) for key in production}
    os.environ.update(production)
    try:
        yield
    finally:
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def apply_position_scales(
    draws: np.ndarray,
    positions: pd.Series,
    factors: dict[str, float],
) -> np.ndarray:
    """Apply frozen per-position final-draw scales without moving row means."""
    values = np.asarray(draws, dtype=np.float64)
    if values.ndim != 2 or len(positions) != values.shape[0]:
        raise ValueError("position-scale rows do not align")
    normalized = {str(key).upper(): float(value) for key, value in factors.items()}
    if set(normalized) != set(POSITIONS):
        raise ValueError(f"position scales must contain exactly {POSITIONS}")
    if any(
        not np.isfinite(value) or value < 0.75 or value > 1.50
        for value in normalized.values()
    ):
        raise ValueError("position scales must be finite and in [0.75, 1.50]")
    scale = positions.astype(str).str.upper().map(normalized)
    if scale.isna().any():
        raise ValueError("position-scale frame contains an unsupported position")
    before = permutation_invariant_row_mean(values, keepdims=True)
    out = before + scale.to_numpy(dtype=np.float64)[:, None] * (values - before)
    out += before - permutation_invariant_row_mean(out, keepdims=True)
    max_delta = float(np.max(np.abs(
        permutation_invariant_row_mean(out, keepdims=True) - before
    )))
    if max_delta > 1e-10:
        raise ValueError(f"position scale changed a row mean by {max_delta:.3g}")
    return out


def fit_position_scales(
    folds: dict[int, tuple[pd.DataFrame, np.ndarray]],
) -> dict:
    """Fit one final-served scale per position on frozen calibration folds."""
    if set(folds) != set(CALIBRATION_SEASONS):
        raise ValueError("position-scale fit requires all calibration seasons")
    report: dict[str, dict] = {}
    selected_factors: dict[str, float] = {}
    for position in POSITIONS:
        prepared: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        identity: dict[tuple[int, int], float] = {}
        for season in CALIBRATION_SEASONS:
            frame, draws = folds[season]
            mask = frame.position.astype(str).eq(position).to_numpy()
            if not mask.any():
                raise ValueError(f"no {position} calibration rows for {season}")
            actual = frame.loc[mask, "actual"].to_numpy(dtype=float)
            values = np.asarray(draws, dtype=float)[mask]
            means = values.mean(axis=1)
            quantiles = np.quantile(
                values, [level for _, level in QUANTILES], axis=1)
            for index, (label, level) in enumerate(QUANTILES):
                loss = float(control._pinball(
                    actual, quantiles[index], level).mean())
                if not np.isfinite(loss) or loss <= 0:
                    raise ValueError(
                        f"invalid identity pinball for {season} {position} q{label}")
                prepared[(season, label)] = (actual, means, quantiles[index])
                identity[(season, label)] = loss

        curve = []
        for factor in POSITION_SCALE_GRID:
            ratios = []
            for season in CALIBRATION_SEASONS:
                for label, level in QUANTILES:
                    actual, means, quantile = prepared[(season, label)]
                    corrected = means + float(factor) * (quantile - means)
                    ratios.append(float(control._pinball(
                        actual, corrected, level).mean()) / identity[(season, label)])
            curve.append({
                "factor": float(factor),
                "objective": float(np.mean(ratios)),
            })
        minimum = min(row["objective"] for row in curve)
        tied = [
            row["factor"] for row in curve
            if np.isclose(row["objective"], minimum, rtol=0, atol=1e-12)
        ]
        selected = min(tied, key=lambda value: (abs(value - 1.0), value))
        selected_factors[position] = float(selected)
        report[position] = {
            "selected_factor": float(selected),
            "minimum_objective": float(minimum),
            "curve": curve,
        }
    return {"factors": selected_factors, "positions": report}


def _summaries(scores: pd.DataFrame) -> dict:
    return {
        "folds": [
            control._summarize(scores[scores.season.eq(season)], str(season))
            for season in sorted(scores.season.unique())
        ],
        "aggregate": {
            **control._summarize(scores, "aggregate"),
            "positions": {
                str(position): control._summarize(group, str(position))
                for position, group in scores.groupby("position", sort=True)
            },
        },
    }


def _position_pinball_ratios(
    source: pd.DataFrame,
    treatment: pd.DataFrame,
) -> dict:
    keys = ["season", "week", "gsis_id", "position"]
    if not source[keys].equals(treatment[keys]):
        raise ValueError("position-scale score rows do not align")
    cells = []
    by_position: dict[str, list[float]] = {position: [] for position in POSITIONS}
    for position in POSITIONS:
        for season in EVALUATION_SEASONS:
            mask = source.position.eq(position) & source.season.eq(season)
            if not mask.any():
                raise ValueError(f"no evaluation rows for {position} {season}")
            for label, _ in QUANTILES:
                base = float(source.loc[mask, f"pinball_q{label}"].mean())
                value = float(treatment.loc[mask, f"pinball_q{label}"].mean())
                if base <= 0 or not np.isfinite(base + value):
                    raise ValueError("invalid position pinball ratio")
                ratio = value / base
                by_position[position].append(ratio)
                cells.append({
                    "position": position,
                    "season": season,
                    "quantile": label,
                    "treatment_to_control_ratio": ratio,
                })
    return {
        "mean_ratio": float(np.mean([row["treatment_to_control_ratio"] for row in cells])),
        "position_mean_ratios": {
            position: float(np.mean(values))
            for position, values in by_position.items()
        },
        "cells": cells,
    }


def _mean_absolute_position_gap(summary: dict) -> float:
    gaps = []
    for position in POSITIONS:
        position_summary = summary["positions"][position]
        gaps.extend(
            abs(float(position_summary[f"q{label}_calibration_gap"]))
            for label, _ in QUANTILES
        )
    return float(np.mean(gaps))


def position_calibration_gate(
    factors: dict[str, float],
    source_summary: dict,
    treatment_summary: dict,
    pinball_ratios: dict,
    max_mean_delta: float,
) -> dict:
    source_gap = _mean_absolute_position_gap(source_summary)
    treatment_gap = _mean_absolute_position_gap(treatment_summary)
    source_wr99 = abs(float(
        source_summary["positions"]["WR"]["q99_calibration_gap"]))
    treatment_wr99 = abs(float(
        treatment_summary["positions"]["WR"]["q99_calibration_gap"]))
    source_te99 = abs(float(
        source_summary["positions"]["TE"]["q99_calibration_gap"]))
    treatment_te99 = abs(float(
        treatment_summary["positions"]["TE"]["q99_calibration_gap"]))
    checks = {
        "wr_factor_above_1": float(factors["WR"]) > 1.0,
        "te_factor_below_1": float(factors["TE"]) < 1.0,
        "position_quantile_gap_improves_at_least_10pct": (
            source_gap > 0 and treatment_gap <= 0.90 * source_gap
        ),
        "wr_q99_absolute_gap_strictly_improves": treatment_wr99 < source_wr99,
        "te_q99_absolute_gap_strictly_improves": treatment_te99 < source_te99,
        "mean_position_fold_quantile_pinball_ratio_at_most_1": (
            float(pinball_ratios["mean_ratio"]) <= 1.0
        ),
        "each_position_pinball_ratio_at_most_1_01": all(
            float(value) <= 1.01
            for value in pinball_ratios["position_mean_ratios"].values()
        ),
        "crps_relative_worsening_at_most_0_5pct": (
            float(treatment_summary["crps"]) <= 1.005 * float(source_summary["crps"])
        ),
        "brier20_relative_worsening_at_most_1pct": (
            float(treatment_summary["brier_20"])
            <= 1.01 * float(source_summary["brier_20"])
        ),
        "brier30_relative_worsening_at_most_1pct": (
            float(treatment_summary["brier_30"])
            <= 1.01 * float(source_summary["brier_30"])
        ),
        "maximum_mean_delta_at_most_1e_10": max_mean_delta <= 1e-10,
    }
    return {
        **checks,
        "source_mean_absolute_position_quantile_gap": source_gap,
        "treatment_mean_absolute_position_quantile_gap": treatment_gap,
        "passes": all(checks.values()),
    }


def _load_accepted(seasons: tuple[int, ...], panel_id: str) -> pd.DataFrame:
    from ..bq import query_df
    from ..config import settings

    return query_df(f"""
        SELECT season, week, gsis_id, pos, actual,
               model_points_pre, mean_projection
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season IN UNNEST(@seasons)
          AND pos IN UNNEST(@positions)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={
            "panel_id": panel_id,
            "seasons": list(seasons),
            "positions": list(POSITIONS),
        })


def _align_fold(
    projected: pd.DataFrame,
    draws: np.ndarray,
    accepted: pd.DataFrame,
    tabpfn_keys: pd.DataFrame,
    season: int,
) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame, dict]:
    keys = ["season", "week", "gsis_id", "position"]
    required = {
        *keys, "actual", "was_active", "model_points_pre", "proj_points",
        "proj_p10", "proj_p50", "proj_p90", "proj_std",
    }
    if missing := required - set(projected.columns):
        raise ValueError(f"position calibration projections missing {sorted(missing)}")
    if draws.shape[0] != len(projected):
        raise ValueError("position calibration projection/draw rows differ")
    source = projected.copy()
    source["_draw_index"] = np.arange(len(source))
    source["tabpfn_covered"] = source.merge(
        tabpfn_keys.assign(tabpfn_covered=True),
        on=["season", "week", "gsis_id"], how="left", sort=False,
        validate="many_to_one",
    ).tabpfn_covered.fillna(False).to_numpy(bool)
    source["market_covered"] = source.market_points.notna()
    expected = accepted[accepted.season.eq(season)].rename(columns={
        "pos": "position",
        "actual": "accepted_actual",
        "model_points_pre": "accepted_model_points_pre",
        "mean_projection": "accepted_mean_projection",
    })
    joined = expected.merge(
        source, on=keys, how="left", validate="one_to_one", indicator=True)
    if not joined._merge.eq("both").all():
        missing = joined.loc[joined._merge.ne("both"), keys].head()
        raise ValueError(
            "position calibration accepted keys missing from replay: "
            f"{missing.to_dict('records')}")
    joined = joined[joined.was_active.fillna(False).astype(bool)]
    joined = joined[joined.position.isin(POSITIONS)].reset_index(drop=True)
    if set(joined.position.astype(str)) != set(POSITIONS):
        raise ValueError(f"position calibration {season} lacks a position")
    actual_delta = np.abs(
        joined.accepted_actual.to_numpy(float) - joined.actual.to_numpy(float))
    pre_delta = np.abs(
        joined.accepted_model_points_pre.to_numpy(float)
        - joined.model_points_pre.to_numpy(float))
    final_delta = np.abs(
        joined.accepted_mean_projection.to_numpy(float)
        - joined.proj_points.to_numpy(float))
    if float(actual_delta.max(initial=0.0)) > control.ACTUAL_TOLERANCE:
        raise ValueError("position calibration accepted actuals disagree")
    if float(pre_delta.max(initial=0.0)) > control.MEAN_TOLERANCE:
        raise ValueError("position calibration post-shaper means disagree")
    if float(final_delta.max(initial=0.0)) > control.MEAN_TOLERANCE:
        raise ValueError("position calibration post-blend means disagree")
    frame = joined[[
        "season", "week", "gsis_id", "position", "accepted_actual",
        "market_covered", "tabpfn_covered",
    ]].rename(columns={"accepted_actual": "actual"})
    summary = joined[[
        "season", "week", "gsis_id", "position", "accepted_actual",
        "proj_p10", "proj_p50", "proj_p90", "proj_std",
    ]].rename(columns={"accepted_actual": "actual"})
    counts = joined.groupby("position").size().astype(int).to_dict()
    parity = {
        "season": int(season),
        "rows": int(len(joined)),
        "rows_by_position": {str(key): int(value) for key, value in counts.items()},
        "tabpfn_coverage": float(frame.tabpfn_covered.mean()),
        "tabpfn_coverage_by_position": {
            str(position): float(group.tabpfn_covered.mean())
            for position, group in frame.groupby("position", sort=True)
        },
        "max_actual_abs_delta": float(actual_delta.max(initial=0.0)),
        "max_post_shaper_mean_abs_delta": float(pre_delta.max(initial=0.0)),
        "max_post_blend_mean_abs_delta": float(final_delta.max(initial=0.0)),
    }
    indices = joined._draw_index.to_numpy(int)
    return frame, np.asarray(draws)[indices], summary, parity


def _replay_folds(
    seasons: tuple[int, ...],
    accepted: pd.DataFrame,
    tabpfn_table: str,
) -> tuple[dict[int, tuple[pd.DataFrame, np.ndarray]], dict[int, pd.DataFrame], list[dict]]:
    from ..backtest.replay import (
        _market_blend_worlds,
        load_panel_and_dst,
        replay_projections,
    )
    from ..bq import query_df
    from ..config import settings
    from ..models.blend import effective_model_weight
    from ..models.prop_market import market_points

    weight = effective_model_weight()
    if not np.isclose(weight, 0.45, rtol=0, atol=0):
        raise ValueError(f"position calibration blend weight is {weight}, not 0.45")
    folds = {}
    summaries = {}
    parity = []
    for season in seasons:
        panel, _ = load_panel_and_dst(season)
        projected, draws = replay_projections(
            panel, season, n_sims=control.N_SIMS, seed=0, return_draws=True)
        market = market_points((season,)).drop_duplicates(
            ["season", "week", "gsis_id"])
        projected, draws, _ = _market_blend_worlds(
            projected, draws, market, weight)
        tabpfn_keys = query_df(f"""
            SELECT DISTINCT season, week, gsis_id
            FROM `{settings.features}.{tabpfn_table}`
            WHERE season = @season
            """, params={"season": int(season)})
        frame, final_draws, summary, fold_parity = _align_fold(
            projected, draws, accepted, tabpfn_keys, season)
        folds[season] = (frame, final_draws)
        summaries[season] = summary
        parity.append(fold_parity)
    return folds, summaries, parity


def _summary_coverage(frame: pd.DataFrame) -> dict:
    def summarize(group: pd.DataFrame) -> dict:
        return {
            "rows": int(len(group)),
            "below_p10": float((group.actual < group.proj_p10).mean()),
            "below_p90": float((group.actual < group.proj_p90).mean()),
        }

    return {
        "aggregate": summarize(frame),
        "positions": {
            str(position): summarize(group)
            for position, group in frame.groupby("position", sort=True)
        },
    }


def _summary_refit(
    calibration_summaries: dict[int, pd.DataFrame],
    evaluation_summaries: dict[int, pd.DataFrame],
) -> dict:
    calibration_frame = pd.concat(
        [calibration_summaries[season] for season in CALIBRATION_SEASONS],
        ignore_index=True)
    factors = calibration.fit_widen_factors(calibration_frame)
    if set(factors) != set(POSITIONS):
        raise ValueError("summary refit did not return all positions")
    implied = {
        position: round(
            float(calibration.DEFAULT_WIDEN[position]) * float(factors[position]), 4)
        for position in POSITIONS
    }

    def compare(frames: dict[int, pd.DataFrame], seasons: tuple[int, ...]) -> dict:
        source = pd.concat([frames[season] for season in seasons], ignore_index=True)
        corrected_quantiles = calibration.apply_widen(
            source[["proj_p10", "proj_p50", "proj_p90", "proj_std"]],
            source.position,
            factors=factors,
        )
        treatment = source.copy()
        treatment[["proj_p10", "proj_p50", "proj_p90", "proj_std"]] = \
            corrected_quantiles[["proj_p10", "proj_p50", "proj_p90", "proj_std"]]
        return {
            "control": _summary_coverage(source),
            "treatment": _summary_coverage(treatment),
        }

    return {
        "incremental_factors": factors,
        "implied_absolute_factors": implied,
        "calibration": compare(calibration_summaries, CALIBRATION_SEASONS),
        "evaluation": compare(evaluation_summaries, EVALUATION_SEASONS),
        "disposition": "summary-only-refit-does-not-govern-tabpfn-covered-draws",
    }


def run(panel_id: str = PANEL_ID) -> dict:
    contract = execution_contract(panel_id)
    all_seasons = CALIBRATION_SEASONS + EVALUATION_SEASONS
    accepted = _load_accepted(all_seasons, panel_id)
    with _served_environment(contract):
        folds, summary_folds, parity = _replay_folds(
            all_seasons, accepted, contract["tabpfn_table"])
    calibration_folds = {
        season: folds[season] for season in CALIBRATION_SEASONS}
    evaluation_folds = {
        season: folds[season] for season in EVALUATION_SEASONS}
    r1 = _summary_refit(
        {season: summary_folds[season] for season in CALIBRATION_SEASONS},
        {season: summary_folds[season] for season in EVALUATION_SEASONS},
    )
    fit = fit_position_scales(calibration_folds)
    factors = fit["factors"]

    calibration_source_parts = []
    calibration_treatment_parts = []
    evaluation_source_parts = []
    evaluation_treatment_parts = []
    max_mean_delta = 0.0
    for season in all_seasons:
        frame, draws = folds[season]
        corrected = apply_position_scales(draws, frame.position, factors)
        max_mean_delta = max(max_mean_delta, float(np.max(np.abs(
            corrected.mean(axis=1, dtype=np.float64)
            - np.asarray(draws).mean(axis=1, dtype=np.float64)
        ))))
        source_scores = control._score_draws(frame, draws)
        treatment_scores = control._score_draws(frame, corrected)
        if season in CALIBRATION_SEASONS:
            calibration_source_parts.append(source_scores)
            calibration_treatment_parts.append(treatment_scores)
        else:
            evaluation_source_parts.append(source_scores)
            evaluation_treatment_parts.append(treatment_scores)

    calibration_source = pd.concat(calibration_source_parts, ignore_index=True)
    calibration_treatment = pd.concat(
        calibration_treatment_parts, ignore_index=True)
    evaluation_source = pd.concat(evaluation_source_parts, ignore_index=True)
    evaluation_treatment = pd.concat(
        evaluation_treatment_parts, ignore_index=True)
    calibration_reports = {
        "control": _summaries(calibration_source),
        "treatment": _summaries(calibration_treatment),
    }
    pinball_ratios = _position_pinball_ratios(
        evaluation_source, evaluation_treatment)
    evaluation_reports = {
        "control": _summaries(evaluation_source),
        "treatment": _summaries(evaluation_treatment),
        "position_pinball_ratios": pinball_ratios,
        "paired_loss_uncertainty": global_recalibration._paired_loss_uncertainty(
            evaluation_source, evaluation_treatment),
        "maximum_mean_delta": max_mean_delta,
    }
    gate = position_calibration_gate(
        factors,
        evaluation_reports["control"]["aggregate"],
        evaluation_reports["treatment"]["aggregate"],
        pinball_ratios,
        max_mean_delta,
    )
    report = {
        "panel": panel_id,
        "contract": contract,
        "r1_summary_refit": r1,
        "r2_final_served_fit": fit,
        "calibration": calibration_reports,
        "evaluation": evaluation_reports,
        "parity": parity,
        "simulation": {
            "n_sims": control.N_SIMS,
            "seed": 0,
            "positions": list(POSITIONS),
            "calibration_seasons": list(CALIBRATION_SEASONS),
            "evaluation_seasons": list(EVALUATION_SEASONS),
            "model_ensemble": contract["model_ensemble"],
            "game_sim_mode": "possession",
            "game_sim_team_factors": "1",
            "sim_widen_draws": "fitted",
            "tabpfn_marginals": "1",
            "tabpfn_marginal_table": contract["tabpfn_table"],
            "shape_mix": 1.0,
            "blend_model_weight": 0.45,
        },
        "gate": gate,
        "disposition": (
            "served-position-calibration-passes"
            if gate["passes"] else "served-position-calibration-fails"
        ),
    }
    print("SERVED_POSITION_CALIBRATION_JSON=" + json.dumps(report, sort_keys=True))
    return report
