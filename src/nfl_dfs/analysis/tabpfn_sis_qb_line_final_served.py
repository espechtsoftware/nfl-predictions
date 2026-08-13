"""Final-served gate for the frozen SIS QB line-context cache pair."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager

import numpy as np

from . import route_final_served_calibration as calibration
from . import served_tail_calibration as served
from . import served_tail_recalibration as uncertainty
from . import tabpfn_sched_final_served as inherited


TABLES = {
    "control": "tabpfn_sis_qb_line_control_v1",
    "treatment": "tabpfn_sis_qb_line_treatment_v1",
}
OUTPUT_PREFIX = "TABPFN_SIS_QB_LINE_FINAL_SERVED_JSON="
EXPECTED_CACHE_ROWS = 52_307
EXPECTED_QB_ROWS = {2023: 511, 2024: 502, 2025: 507}


@contextmanager
def _cache_environment(table: str):
    if table not in set(TABLES.values()):
        raise ValueError(f"unlicensed SIS QB line cache {table!r}")
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


def _evaluate_qb_arms(
    control_folds: dict[int, tuple],
    treatment_folds: dict[int, tuple],
) -> dict:
    """Fit each arm independently, then apply the frozen QB-only gate."""
    alignment = [
        "season", "week", "gsis_id", "position", "actual",
        "market_covered", "tabpfn_covered",
    ]
    for season in calibration.ALL_SEASONS:
        if not control_folds[season][0][alignment].equals(
            treatment_folds[season][0][alignment]
        ):
            raise ValueError(f"SIS QB line arm rows differ in {season}")
    schedules = {
        "control": calibration.fit_walk_forward_schedule(control_folds),
        "treatment": calibration.fit_walk_forward_schedule(treatment_folds),
    }
    control_scores, control_delta = calibration.score_walk_forward(
        control_folds, schedules["control"])
    treatment_scores, treatment_delta = calibration.score_walk_forward(
        treatment_folds, schedules["treatment"])
    keys = ["season", "week", "gsis_id", "position", "actual"]
    if not control_scores[keys].equals(treatment_scores[keys]):
        raise ValueError("SIS QB line calibrated score rows differ")
    control_qb = control_scores[control_scores.position.eq("QB")].reset_index(
        drop=True)
    treatment_qb = treatment_scores[
        treatment_scores.position.eq("QB")].reset_index(drop=True)
    counts = control_qb.groupby("season").size().to_dict()
    if counts != EXPECTED_QB_ROWS:
        raise ValueError(f"SIS QB line primary rows differ: {counts}")

    def summaries(rows):
        return {
            "folds": [
                served._summarize(rows[rows.season.eq(season)], str(season))
                for season in calibration.EVALUATION_SEASONS
            ],
            "aggregate": served._summarize(rows, "aggregate"),
        }

    control_report = summaries(control_qb)
    treatment_report = summaries(treatment_qb)
    maximum_delta = max(control_delta, treatment_delta)
    gate = {
        "aggregate_active_qb_30_brier_improves": (
            treatment_report["aggregate"]["brier_30"]
            < control_report["aggregate"]["brier_30"]
        ),
        "maximum_mean_delta_at_most_1e_10": maximum_delta <= 1e-10,
    }
    gate["passes"] = all(gate.values())
    return {
        "control_schedule": {
            str(key): value for key, value in schedules["control"].items()},
        "treatment_schedule": {
            str(key): value for key, value in schedules["treatment"].items()},
        "control": control_report,
        "treatment": treatment_report,
        "maximum_mean_delta": {
            "control": control_delta, "treatment": treatment_delta},
        "paired_loss_uncertainty": uncertainty._paired_loss_uncertainty(
            control_qb, treatment_qb),
        "gate": gate,
    }


def run(panel_id: str) -> dict:
    expected_panel = os.environ.get("TABPFN_SIS_QB_LINE_PANEL_ID", "").strip()
    if not expected_panel or panel_id != expected_panel:
        raise ValueError("SIS QB line gate panel differs from terminal panel")
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
        raise ValueError("SIS QB line cache target keys differ")
    if len(cache_keys["control"]) != EXPECTED_CACHE_ROWS:
        raise ValueError("SIS QB line cache row count differs")

    folds = {arm: {} for arm in TABLES}
    parity = {arm: [] for arm in TABLES}
    with inherited._common_environment(usage):
        weight = effective_model_weight()
        if not np.isclose(weight, 0.45, rtol=0, atol=0):
            raise ValueError("SIS QB line gate blend weight differs")
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

    report = _evaluate_qb_arms(folds["control"], folds["treatment"])
    report.update({
        "disposition": (
            "tabpfn-sis-qb-line-final-served-passes"
            if report["gate"]["passes"]
            else "tabpfn-sis-qb-line-final-served-fails"),
        "panel": panel_id,
        "version": "v1",
        "label_law": "active_only",
        "feature_law": "base",
        "mode": "shared-33-vs-sis-qb-offensive-line-two-column-cache",
        "primary_population": "active QB",
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


__all__ = ["TABLES", "_cache_environment", "_evaluate_qb_arms", "run"]
