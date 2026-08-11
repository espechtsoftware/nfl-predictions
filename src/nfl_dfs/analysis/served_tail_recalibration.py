"""Frozen walk-forward fit and untouched served-tail recalibration gate."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import served_tail_calibration as control
from ..ingest.fantasy_points_route import PANEL_ID


CALIBRATION_SEASONS = (2019, 2021, 2022)
EVALUATION_SEASONS = (2023, 2024, 2025)
POSITIONS = ("RB", "WR", "TE")
SCALE_GRID = np.round(np.arange(1.0, 1.2501, 0.005), 3)
EXPECTED_EVALUATION_ROWS = control.EXPECTED_ROWS


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


def fit_scale(folds: dict[int, tuple[pd.DataFrame, np.ndarray]]) -> dict:
    """Select the one global scale by frozen q95/q99 pinball objective."""
    if set(folds) != set(CALIBRATION_SEASONS):
        raise ValueError("served-tail fit requires all calibration seasons")
    prepared: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    identity_losses: dict[tuple[int, int], float] = {}
    for season in CALIBRATION_SEASONS:
        frame, draws = folds[season]
        actual = frame.actual.to_numpy(float)
        means = np.asarray(draws, dtype=float).mean(axis=1)
        quantiles = np.quantile(draws, (0.95, 0.99), axis=1)
        for index, level in enumerate((0.95, 0.99)):
            label = int(level * 100)
            prepared[(season, label)] = (actual, means, quantiles[index])
            loss = float(control._pinball(
                actual, quantiles[index], level).mean())
            if not np.isfinite(loss) or loss <= 0:
                raise ValueError("served-tail identity pinball is invalid")
            identity_losses[(season, label)] = loss

    curve: list[dict] = []
    for factor in SCALE_GRID:
        ratios = []
        cells = {}
        for season in CALIBRATION_SEASONS:
            for label, level in ((95, 0.95), (99, 0.99)):
                actual, means, quantile = prepared[(season, label)]
                corrected = means + float(factor) * (quantile - means)
                loss = float(control._pinball(
                    actual, corrected, level).mean())
                ratio = loss / identity_losses[(season, label)]
                ratios.append(ratio)
                cells[f"{season}_q{label}_pinball_ratio"] = ratio
        curve.append({
            "factor": float(factor),
            "objective": float(np.mean(ratios)),
            **cells,
        })
    minimum = min(row["objective"] for row in curve)
    selected = min(
        row["factor"] for row in curve
        if np.isclose(row["objective"], minimum, rtol=0, atol=1e-12)
    )
    return {
        "selected_factor": float(selected),
        "minimum_objective": float(minimum),
        "curve": curve,
    }


def _paired_loss_uncertainty(
    control_scores: pd.DataFrame,
    treatment_scores: pd.DataFrame,
) -> dict:
    keys = ["season", "week", "gsis_id", "position"]
    if not control_scores[keys].equals(treatment_scores[keys]):
        raise ValueError("served-tail paired score rows do not align")
    reports = {}
    for column in (
        "crps", "brier_20", "brier_30",
        "pinball_q90", "pinball_q95", "pinball_q99",
    ):
        delta = (
            treatment_scores[column].to_numpy(float)
            - control_scores[column].to_numpy(float)
        )
        se = control._cluster_standard_error(
            delta,
            control_scores.season.to_numpy(),
            control_scores.week.to_numpy(),
        )
        mean = float(delta.mean())
        reports[column] = {
            "mean_delta": mean,
            "cluster_se": se,
            "cluster_ci95_low": mean - 1.96 * se,
            "cluster_ci95_high": mean + 1.96 * se,
        }
    return reports


def _upper_pinball_ratio(
    control_scores: pd.DataFrame,
    treatment_scores: pd.DataFrame,
) -> tuple[float, list[dict]]:
    cells = []
    ratios = []
    for season in EVALUATION_SEASONS:
        c = control_scores[control_scores.season.eq(season)]
        t = treatment_scores[treatment_scores.season.eq(season)]
        for label in (95, 99):
            base = float(c[f"pinball_q{label}"].mean())
            ratio = float(t[f"pinball_q{label}"].mean()) / base
            ratios.append(ratio)
            cells.append({
                "season": season,
                "quantile": label,
                "treatment_to_control_ratio": ratio,
            })
    return float(np.mean(ratios)), cells


def recalibration_gate(
    control_summary: dict,
    treatment_summary: dict,
    upper_pinball_ratio: float,
    max_mean_delta: float,
) -> dict:
    c = control_summary
    t = treatment_summary
    c99 = abs(float(c["q99_calibration_gap"]))
    t99 = abs(float(t["q99_calibration_gap"]))
    c95 = abs(float(c["q95_calibration_gap"]))
    t95 = abs(float(t["q95_calibration_gap"]))
    c90 = abs(float(c["q90_calibration_gap"]))
    t90 = abs(float(t["q90_calibration_gap"]))
    checks = {
        "q99_absolute_error_improves_at_least_25pct": (
            c99 > 0 and t99 <= 0.75 * c99),
        "q95_absolute_error_strictly_improves": t95 < c95,
        "q90_absolute_error_worsens_no_more_than_0_0025": (
            t90 <= c90 + 0.0025),
        "upper_pinball_ratio_at_most_1": upper_pinball_ratio <= 1.0,
        "crps_relative_worsening_at_most_0_5pct": (
            float(t["crps"]) <= 1.005 * float(c["crps"])),
        "brier20_relative_worsening_at_most_1pct": (
            float(t["brier_20"]) <= 1.01 * float(c["brier_20"])),
        "brier30_relative_worsening_at_most_1pct": (
            float(t["brier_30"]) <= 1.01 * float(c["brier_30"])),
        "maximum_mean_delta_at_most_1e_10": max_mean_delta <= 1e-10,
    }
    return {**checks, "passes": all(checks.values())}


def _load_accepted(seasons: tuple[int, ...]) -> pd.DataFrame:
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
            "panel_id": PANEL_ID,
            "seasons": list(seasons),
            "positions": list(POSITIONS),
        })


def _replay_folds(
    seasons: tuple[int, ...],
    accepted: pd.DataFrame,
) -> tuple[dict[int, tuple[pd.DataFrame, np.ndarray]], list[dict]]:
    from ..backtest.replay import (
        _market_blend_worlds,
        load_panel_and_dst,
        replay_projections,
    )
    from ..bq import query_df
    from ..config import settings
    from ..models.blend import effective_model_weight
    from ..models.prop_market import market_points

    folds = {}
    parity = []
    weight = effective_model_weight()
    if not np.isclose(weight, 0.45, rtol=0, atol=0):
        raise ValueError(f"served-tail model blend weight is {weight}, not 0.45")
    for season in seasons:
        panel, _ = load_panel_and_dst(season)
        projected, draws = replay_projections(
            panel, season, n_sims=control.N_SIMS, seed=0,
            return_draws=True)
        market = market_points((season,)).drop_duplicates(
            ["season", "week", "gsis_id"])
        projected, draws, _ = _market_blend_worlds(
            projected, draws, market, weight)
        tabpfn_keys = query_df(f"""
            SELECT DISTINCT season, week, gsis_id
            FROM `{settings.features}.tabpfn_projections`
            WHERE season = @season
            """, params={"season": int(season)})
        frame, final_draws, fold_parity = control._align_evaluation(
            projected, draws, accepted, tabpfn_keys, season)
        folds[season] = (frame, final_draws)
        parity.append(fold_parity)
    return folds, parity


def run(panel_id: str = PANEL_ID) -> dict:
    if panel_id != PANEL_ID:
        raise ValueError(f"served-tail protocol is frozen to {PANEL_ID}")
    control._validate_environment()
    from ..backtest.replay import apply_served_tail_scale

    with control._production_environment():
        calibration_accepted = _load_accepted(CALIBRATION_SEASONS)
        calibration_folds, calibration_parity = _replay_folds(
            CALIBRATION_SEASONS, calibration_accepted)
        fit = fit_scale(calibration_folds)
        factor = float(fit["selected_factor"])
        if factor == 1.0:
            report = {
                "panel": PANEL_ID,
                "fit": fit,
                "calibration_parity": calibration_parity,
                "disposition": "calibration-does-not-support-widening",
            }
            print("SERVED_TAIL_RECALIBRATION_JSON=" + json.dumps(
                report, sort_keys=True))
            return report

        calibration_control_parts = []
        calibration_treatment_parts = []
        calibration_mean_delta = 0.0
        for season in CALIBRATION_SEASONS:
            frame, draws = calibration_folds[season]
            corrected = apply_served_tail_scale(
                draws, frame.position,
                env={"SERVED_TAIL_SCALE": str(factor)})
            calibration_mean_delta = max(
                calibration_mean_delta,
                float(np.max(np.abs(
                    corrected.mean(axis=1) - draws.mean(axis=1)))),
            )
            calibration_control_parts.append(control._score_draws(frame, draws))
            calibration_treatment_parts.append(
                control._score_draws(frame, corrected))

        evaluation_accepted = _load_accepted(EVALUATION_SEASONS)
        evaluation_folds, evaluation_parity = _replay_folds(
            EVALUATION_SEASONS, evaluation_accepted)
        evaluation_control_parts = []
        evaluation_treatment_parts = []
        evaluation_mean_delta = 0.0
        for season in EVALUATION_SEASONS:
            frame, draws = evaluation_folds[season]
            corrected = apply_served_tail_scale(
                draws, frame.position,
                env={"SERVED_TAIL_SCALE": str(factor)})
            evaluation_mean_delta = max(
                evaluation_mean_delta,
                float(np.max(np.abs(
                    corrected.mean(axis=1) - draws.mean(axis=1)))),
            )
            evaluation_control_parts.append(control._score_draws(frame, draws))
            evaluation_treatment_parts.append(
                control._score_draws(frame, corrected))

    calibration_control = pd.concat(
        calibration_control_parts, ignore_index=True)
    calibration_treatment = pd.concat(
        calibration_treatment_parts, ignore_index=True)
    evaluation_control = pd.concat(
        evaluation_control_parts, ignore_index=True)
    evaluation_treatment = pd.concat(
        evaluation_treatment_parts, ignore_index=True)
    if len(evaluation_control) != EXPECTED_EVALUATION_ROWS:
        raise ValueError(
            f"served-tail evaluation has {len(evaluation_control)} rows; "
            f"expected {EXPECTED_EVALUATION_ROWS}")

    pinball_ratio, pinball_cells = _upper_pinball_ratio(
        evaluation_control, evaluation_treatment)
    calibration_reports = {
        "control": _summaries(calibration_control),
        "treatment": _summaries(calibration_treatment),
        "maximum_mean_delta": calibration_mean_delta,
    }
    evaluation_reports = {
        "control": _summaries(evaluation_control),
        "treatment": _summaries(evaluation_treatment),
        "maximum_mean_delta": evaluation_mean_delta,
        "upper_pinball_ratio": pinball_ratio,
        "upper_pinball_cells": pinball_cells,
        "paired_loss_uncertainty": _paired_loss_uncertainty(
            evaluation_control, evaluation_treatment),
    }
    gate = recalibration_gate(
        evaluation_reports["control"]["aggregate"],
        evaluation_reports["treatment"]["aggregate"],
        pinball_ratio,
        evaluation_mean_delta,
    )
    report = {
        "panel": PANEL_ID,
        "fit": fit,
        "calibration_parity": calibration_parity,
        "evaluation_parity": evaluation_parity,
        "calibration": calibration_reports,
        "evaluation": evaluation_reports,
        "gate": gate,
        "disposition": (
            "served-tail-recalibration-stage-a-passes" if gate["passes"]
            else "served-tail-recalibration-stage-a-fails"
        ),
    }
    print("SERVED_TAIL_RECALIBRATION_JSON=" + json.dumps(
        report, sort_keys=True))
    return report
