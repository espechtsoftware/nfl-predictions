"""Final-served gate for the frozen PFR secondary-feature ablation."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager

import numpy as np

from . import route_final_served_calibration as calibration
from . import served_tail_calibration as served
from . import served_tail_recalibration as uncertainty
from . import tabpfn_sched_final_served as inherited


ARMS = ("control", "drop_rates", "drop_top_cb", "drop_all")
ARM_DROPS = {
    "control": (),
    "drop_rates": (
        "cb_ypt_allowed_l6",
        "cb_comp_rate_allowed_l6",
        "db_ypt_allowed_l6",
    ),
    "drop_top_cb": ("top_cb_out",),
    "drop_all": (
        "cb_ypt_allowed_l6",
        "cb_comp_rate_allowed_l6",
        "db_ypt_allowed_l6",
        "top_cb_out",
    ),
}
TABLES = {arm: f"tabpfn_pfr_secondary_{arm}_v1" for arm in ARMS}
OUTPUT_PREFIX = "TABPFN_PFR_SECONDARY_FINAL_SERVED_JSON="
EXPECTED_CACHE_ROWS = 52_307
TIE_ORDER = ("drop_rates", "drop_top_cb", "drop_all")


@contextmanager
def _arm_environment(arm: str):
    if arm not in ARMS:
        raise ValueError(f"unlicensed PFR secondary arm {arm!r}")
    prior_table = os.environ.get("TABPFN_MARGINAL_TABLE")
    prior_drop = os.environ.get("DROP_FEATURES")
    os.environ["TABPFN_MARGINAL_TABLE"] = TABLES[arm]
    if ARM_DROPS[arm]:
        os.environ["DROP_FEATURES"] = ",".join(ARM_DROPS[arm])
    else:
        os.environ.pop("DROP_FEATURES", None)
    try:
        yield
    finally:
        if prior_table is None:
            os.environ.pop("TABPFN_MARGINAL_TABLE", None)
        else:
            os.environ["TABPFN_MARGINAL_TABLE"] = prior_table
        if prior_drop is None:
            os.environ.pop("DROP_FEATURES", None)
        else:
            os.environ["DROP_FEATURES"] = prior_drop


def _cache_keys(table: str, arm: str):
    from ..bq import query_df
    from ..config import settings

    return query_df(f"""
        SELECT season, week, gsis_id
        FROM `{settings.features}.{table}`
        WHERE season IN UNNEST(@seasons)
          AND label_law = 'active_only' AND feature_law = @arm
        ORDER BY season, week, gsis_id
        """, params={
            "seasons": list(calibration.ALL_SEASONS),
            "arm": arm,
        })


def _summaries(scores):
    expected = sum(calibration.EXPECTED_ROWS[season]
                   for season in calibration.EVALUATION_SEASONS)
    if len(scores) != expected:
        raise ValueError(
            f"PFR secondary evaluation has {len(scores)} rows; expected {expected}")
    return {
        "folds": [
            served._summarize(scores[scores.season.eq(season)], str(season))
            for season in calibration.EVALUATION_SEASONS
        ],
        "aggregate": {
            **served._summarize(scores, "aggregate"),
            "positions": {
                str(position): served._summarize(group, str(position))
                for position, group in scores.groupby("position", sort=True)
            },
        },
    }


def _evaluate_arms(folds: dict[str, dict[int, tuple]]) -> dict:
    alignment = [
        "season", "week", "gsis_id", "position", "actual",
        "market_covered", "tabpfn_covered",
    ]
    control_folds = folds["control"]
    for arm in ARMS[1:]:
        for season in calibration.ALL_SEASONS:
            if not control_folds[season][0][alignment].equals(
                    folds[arm][season][0][alignment]):
                raise ValueError(
                    f"PFR secondary {arm} rows differ in {season}")

    schedules = {
        arm: calibration.fit_walk_forward_schedule(folds[arm]) for arm in ARMS
    }
    scored = {}
    mean_deltas = {}
    for arm in ARMS:
        scored[arm], mean_deltas[arm] = calibration.score_walk_forward(
            folds[arm], schedules[arm])
    keys = ["season", "week", "gsis_id", "position", "actual"]
    for arm in ARMS[1:]:
        if not scored["control"][keys].equals(scored[arm][keys]):
            raise ValueError(f"PFR secondary calibrated {arm} rows differ")

    summaries = {arm: _summaries(scored[arm]) for arm in ARMS}
    control_brier = float(summaries["control"]["aggregate"]["brier_30"])
    treatment_gates = {}
    for arm in ARMS[1:]:
        arm_brier = float(summaries[arm]["aggregate"]["brier_30"])
        checks = {
            "aggregate_active_skill_30_brier_improves": arm_brier < control_brier,
            "maximum_mean_delta_at_most_1e_10": mean_deltas[arm] <= 1e-10,
        }
        treatment_gates[arm] = {**checks, "passes": all(checks.values())}
    eligible = [arm for arm in TIE_ORDER if treatment_gates[arm]["passes"]]
    selected = min(
        eligible,
        key=lambda arm: (
            float(summaries[arm]["aggregate"]["brier_30"]),
            TIE_ORDER.index(arm),
        ),
    ) if eligible else None
    return {
        "schedules": {
            arm: {str(key): value for key, value in schedules[arm].items()}
            for arm in ARMS
        },
        "summaries": summaries,
        "maximum_mean_delta": mean_deltas,
        "paired_loss_uncertainty": {
            arm: uncertainty._paired_loss_uncertainty(
                scored["control"], scored[arm])
            for arm in ARMS[1:]
        },
        "gate": {
            "primary_metric": "aggregate active QB/RB/WR/TE Brier at 30",
            "control_brier_30": control_brier,
            "treatments": treatment_gates,
            "eligible_arms": eligible,
            "selected_arm": selected,
            "passes": selected is not None,
        },
    }


def run(panel_id: str) -> dict:
    expected_panel = os.environ.get(
        "TABPFN_PFR_SECONDARY_PANEL_ID", "").strip()
    if not expected_panel or panel_id != expected_panel:
        raise ValueError("PFR secondary gate panel differs from terminal panel")
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
    cache_keys = {
        arm: _cache_keys(TABLES[arm], arm) for arm in ARMS
    }
    base_keys = cache_keys["control"]
    if len(base_keys) != EXPECTED_CACHE_ROWS:
        raise ValueError("PFR secondary cache row count differs")
    if any(not base_keys.equals(cache_keys[arm]) for arm in ARMS[1:]):
        raise ValueError("PFR secondary cache target keys differ")

    folds = {arm: {} for arm in ARMS}
    parity = {arm: [] for arm in ARMS}
    with inherited._common_environment(usage):
        weight = effective_model_weight()
        if not np.isclose(weight, 0.45, rtol=0, atol=0):
            raise ValueError("PFR secondary gate blend weight differs")
        for season in calibration.ALL_SEASONS:
            panel, _ = load_panel_and_dst(season)
            market = market_points((season,)).drop_duplicates(
                ["season", "week", "gsis_id"])
            for arm in ARMS:
                with _arm_environment(arm):
                    projected, draws = replay_projections(
                        panel, season, n_sims=served.N_SIMS, seed=0,
                        return_draws=True)
                projected, draws, _ = _market_blend_worlds(
                    projected, draws, market, weight)
                season_keys = cache_keys[arm][
                    cache_keys[arm].season.eq(season)]
                frame, aligned, arm_parity = calibration._align_arm(
                    projected, draws, accepted, season_keys, season,
                    require_control_parity=(arm == "control"))
                folds[arm][season] = (frame, aligned)
                parity[arm].append(arm_parity)

    report = _evaluate_arms(folds)
    selected = report["gate"]["selected_arm"]
    report.update({
        "disposition": (
            "tabpfn-pfr-secondary-final-served-eligible"
            if selected else "tabpfn-pfr-secondary-final-served-no-eligible-drop"),
        "panel": panel_id,
        "version": "v1",
        "label_law": "active_only",
        "mode": "coordinated-lightgbm-and-tabpfn-pfr-secondary-drop-ablation",
        "primary_population": "active QB/RB/WR/TE",
        "arm_drops": {arm: list(ARM_DROPS[arm]) for arm in ARMS},
        "cache_tables": TABLES,
        "cache_rows": int(len(base_keys)),
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


__all__ = ["ARMS", "ARM_DROPS", "TABLES", "_arm_environment",
           "_evaluate_arms", "run"]
