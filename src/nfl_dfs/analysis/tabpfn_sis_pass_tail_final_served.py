"""Final-served gate for the frozen SIS opponent pass-tail cache pair."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager

import numpy as np
import pandas as pd

from . import route_final_served_calibration as calibration
from . import served_position_calibration as position_calibration
from . import served_tail_calibration as served
from . import tabpfn_sched_final_served as inherited


TABLES = {
    "control": "tabpfn_sis_pass_tail_control_v1",
    "treatment": "tabpfn_sis_pass_tail_treatment_v1",
}
OUTPUT_PREFIX = "TABPFN_SIS_PASS_TAIL_FINAL_SERVED_JSON="
EXPECTED_CACHE_ROWS = 52_307
PASS_POSITIONS = ("QB", "WR", "TE")
EXPECTED_PASS_ROWS = {2023: 3_848, 2024: 3_791, 2025: 3_796}


@contextmanager
def _cache_environment(table: str):
    if table not in set(TABLES.values()):
        raise ValueError(f"unlicensed SIS pass-tail cache {table!r}")
    prior = os.environ.get("TABPFN_MARGINAL_TABLE")
    os.environ["TABPFN_MARGINAL_TABLE"] = table
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop("TABPFN_MARGINAL_TABLE", None)
        else:
            os.environ["TABPFN_MARGINAL_TABLE"] = prior


def _cache_keys(table: str):
    from ..bq import query_df
    from ..config import settings

    return query_df(f"""
        SELECT season, week, gsis_id
        FROM `{settings.features}.{table}`
        WHERE season IN UNNEST(@seasons)
          AND label_law = 'active_only' AND feature_law = 'base'
        ORDER BY season, week, gsis_id
        """, params={"seasons": list(calibration.ALL_SEASONS)})


def _score_schedule(
    folds: dict[int, tuple[pd.DataFrame, np.ndarray]],
    schedule: dict[int, dict],
) -> tuple[pd.DataFrame, float]:
    scores = []
    maximum_mean_delta = 0.0
    for season in calibration.EVALUATION_SEASONS:
        frame, draws = folds[season]
        corrected = position_calibration.apply_position_scales(
            draws, frame.position, schedule[season]["factors"])
        maximum_mean_delta = max(maximum_mean_delta, float(np.max(np.abs(
            corrected.mean(axis=1, dtype=np.float64)
            - np.asarray(draws).mean(axis=1, dtype=np.float64)
        ), initial=0.0)))
        scored = served._score_draws(frame, corrected)
        actual = frame.actual.to_numpy(float)
        for threshold in (20, 25, 30):
            probability = (corrected >= threshold).mean(axis=1)
            truth = actual >= threshold
            scored[f"event_{threshold}"] = truth
            scored[f"probability_{threshold}"] = probability
            scored[f"brier_{threshold}"] = np.square(probability - truth)
        scores.append(scored)
    return pd.concat(scores, ignore_index=True), maximum_mean_delta


def _summary(rows: pd.DataFrame, label: str) -> dict:
    report = served._summarize(rows, label)
    for threshold in (20, 25, 30):
        observed = float(rows[f"event_{threshold}"].mean())
        predicted = float(rows[f"probability_{threshold}"].mean())
        report[f"events_{threshold}"] = int(rows[f"event_{threshold}"].sum())
        report[f"brier_{threshold}"] = float(rows[f"brier_{threshold}"].mean())
        report[f"probability_{threshold}"] = predicted
        report[f"event_rate_{threshold}"] = observed
        report[f"reliability_gap_{threshold}"] = predicted - observed
    return report


def _summaries(rows: pd.DataFrame) -> dict:
    return {
        "aggregate": _summary(rows, "aggregate"),
        "seasons": {
            str(season): _summary(rows[rows.season.eq(season)], str(season))
            for season in calibration.EVALUATION_SEASONS
        },
        "positions": {
            position: _summary(rows[rows.position.eq(position)], position)
            for position in PASS_POSITIONS
        },
        "position_seasons": {
            f"{position}:{season}": _summary(
                rows[rows.position.eq(position) & rows.season.eq(season)],
                f"{position}:{season}",
            )
            for position in PASS_POSITIONS
            for season in calibration.EVALUATION_SEASONS
        },
    }


def _proper_score_ratios(
    control: pd.DataFrame, treatment: pd.DataFrame,
) -> dict:
    cells = []
    by_position: dict[str, list[float]] = {position: [] for position in PASS_POSITIONS}
    for position in PASS_POSITIONS:
        mask = control.position.eq(position)
        for quantile in (95, 99):
            base = float(control.loc[mask, f"pinball_q{quantile}"].mean())
            value = float(treatment.loc[mask, f"pinball_q{quantile}"].mean())
            if base <= 0 or not np.isfinite(base + value):
                raise ValueError("invalid SIS pass-tail pinball ratio")
            ratio = value / base
            by_position[position].append(ratio)
            cells.append({
                "position": position,
                "quantile": quantile,
                "control_pinball": base,
                "treatment_pinball": value,
                "treatment_to_control_ratio": ratio,
            })
    position_means = {
        position: float(np.mean(values))
        for position, values in by_position.items()
    }
    return {
        "equal_position_equal_quantile_mean_ratio": float(np.mean([
            row["treatment_to_control_ratio"] for row in cells])),
        "position_mean_ratios": position_means,
        "improving_positions": sorted([
            position for position, ratio in position_means.items()
            if ratio < 1.0
        ]),
        "cells": cells,
    }


def _paired_uncertainty(
    control: pd.DataFrame, treatment: pd.DataFrame,
) -> dict:
    columns = (
        "point_abs_error", "crps", "brier_20", "brier_25", "brier_30",
        "pinball_q90", "pinball_q95", "pinball_q99",
    )
    output = {}
    for column in columns:
        delta = treatment[column].to_numpy(float) - control[column].to_numpy(float)
        standard_error = served._cluster_standard_error(
            delta, control.season.to_numpy(), control.week.to_numpy())
        mean = float(delta.mean())
        output[column] = {
            "mean_delta": mean,
            "cluster_se": standard_error,
            "cluster_ci95_low": mean - 1.96 * standard_error,
            "cluster_ci95_high": mean + 1.96 * standard_error,
        }
    return output


def evaluate_pass_tail_arms(
    control_folds: dict[int, tuple[pd.DataFrame, np.ndarray]],
    treatment_folds: dict[int, tuple[pd.DataFrame, np.ndarray]],
) -> dict:
    alignment = [
        "season", "week", "gsis_id", "position", "actual",
        "market_covered", "tabpfn_covered",
    ]
    for season in calibration.ALL_SEASONS:
        if not control_folds[season][0][alignment].equals(
            treatment_folds[season][0][alignment]
        ):
            raise ValueError(f"SIS pass-tail arm rows differ in {season}")
    schedules = {
        "control": calibration.fit_walk_forward_schedule(control_folds),
        "treatment": calibration.fit_walk_forward_schedule(treatment_folds),
    }
    control_scores, control_delta = _score_schedule(
        control_folds, schedules["control"])
    treatment_scores, treatment_delta = _score_schedule(
        treatment_folds, schedules["treatment"])
    keys = ["season", "week", "gsis_id", "position", "actual"]
    if not control_scores[keys].equals(treatment_scores[keys]):
        raise ValueError("SIS pass-tail calibrated score rows differ")
    control_pass = control_scores[
        control_scores.position.isin(PASS_POSITIONS)].reset_index(drop=True)
    treatment_pass = treatment_scores[
        treatment_scores.position.isin(PASS_POSITIONS)].reset_index(drop=True)
    counts = control_pass.groupby("season").size().to_dict()
    if counts != EXPECTED_PASS_ROWS:
        raise ValueError(f"SIS pass-tail primary rows differ: {counts}")
    ratios = _proper_score_ratios(control_pass, treatment_pass)
    maximum_delta = max(control_delta, treatment_delta)
    gate = {
        "equal_position_equal_q95_q99_ratio_below_1": (
            ratios["equal_position_equal_quantile_mean_ratio"] < 1.0
        ),
        "at_least_two_positions_improve": (
            len(ratios["improving_positions"]) >= 2
        ),
        "maximum_mean_delta_at_most_1e_10": maximum_delta <= 1e-10,
    }
    gate["passes"] = all(gate.values())
    return {
        "control_schedule": {
            str(key): value for key, value in schedules["control"].items()},
        "treatment_schedule": {
            str(key): value for key, value in schedules["treatment"].items()},
        "control": _summaries(control_pass),
        "treatment": _summaries(treatment_pass),
        "proper_score_ratios": ratios,
        "maximum_mean_delta": {
            "control": control_delta, "treatment": treatment_delta},
        "paired_loss_uncertainty": _paired_uncertainty(
            control_pass, treatment_pass),
        "gate": gate,
    }


def run(panel_id: str) -> dict:
    expected_panel = os.environ.get("TABPFN_SIS_PASS_TAIL_PANEL_ID", "").strip()
    if not expected_panel or panel_id != expected_panel:
        raise ValueError("SIS pass-tail gate panel differs from historical panel")
    served._validate_environment()
    usage = inherited.accepted_usage_law()

    from ..backtest.replay import (
        _market_blend_worlds,
        load_panel_and_dst,
        replay_projections,
    )
    from ..bq import query_df
    from ..config import settings
    from ..models.blend import effective_model_weight
    from ..models.prop_market import market_points

    accepted = query_df(f"""
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
            "seasons": list(calibration.ALL_SEASONS),
            "positions": list(calibration.POSITIONS),
        })
    cache_keys = {arm: _cache_keys(table) for arm, table in TABLES.items()}
    if not cache_keys["control"].equals(cache_keys["treatment"]):
        raise ValueError("SIS pass-tail cache target keys differ")
    if len(cache_keys["control"]) != EXPECTED_CACHE_ROWS:
        raise ValueError("SIS pass-tail cache row count differs")

    folds = {arm: {} for arm in TABLES}
    parity = {arm: [] for arm in TABLES}
    with inherited._common_environment(usage):
        weight = effective_model_weight()
        if not np.isclose(weight, 0.45, rtol=0, atol=0):
            raise ValueError("SIS pass-tail gate blend weight differs")
        for season in calibration.ALL_SEASONS:
            panel, _ = load_panel_and_dst(season)
            market = market_points((season,)).drop_duplicates(
                ["season", "week", "gsis_id"])
            for arm, table in TABLES.items():
                with _cache_environment(table):
                    projected, draws = replay_projections(
                        panel, season, n_sims=served.N_SIMS, seed=0,
                        return_draws=True)
                projected, draws, _ = _market_blend_worlds(
                    projected, draws, market, weight)
                season_keys = cache_keys[arm][
                    cache_keys[arm].season.eq(season)]
                frame, aligned, arm_parity = calibration._align_arm(
                    projected, draws, accepted, season_keys, season,
                    require_control_parity=False)
                folds[arm][season] = (frame, aligned)
                parity[arm].append(arm_parity)

    report = evaluate_pass_tail_arms(folds["control"], folds["treatment"])
    report.update({
        "disposition": (
            "tabpfn-sis-pass-tail-final-served-passes"
            if report["gate"]["passes"]
            else "tabpfn-sis-pass-tail-final-served-fails"),
        "panel": panel_id,
        "version": "v1",
        "label_law": "active_only",
        "feature_law": "base",
        "mode": "shared-33-vs-sis-opponent-pass-tail-three-column-cache",
        "primary_population": "active QB/WR/TE",
        "cache_tables": TABLES,
        "cache_rows": int(len(cache_keys["control"])),
        "parity": parity,
        "common_usage_law": usage,
        "simulation": {
            "calibration_season": calibration.CALIBRATION_SEASON,
            "evaluation_seasons": list(calibration.EVALUATION_SEASONS),
            "n_sims": served.N_SIMS,
            "seed": 0,
            "model_ensemble": 1,
            "game_sim_mode": "possession",
            "game_sim_team_factors": "1",
            "sim_widen_draws": "fitted",
            "tabpfn_marginals": "1",
            "emp_marginals_fallback": "1",
            "shape_mix": 1.0,
            "blend_model_weight": 0.45,
            "position_factor_grid": "0.750:0.005:1.500",
        },
    })
    print(OUTPUT_PREFIX + json.dumps(report, sort_keys=True))
    return report


__all__ = [
    "TABLES", "_cache_environment", "evaluate_pass_tail_arms", "run",
]
