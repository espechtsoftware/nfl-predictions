"""Final-served gate for the frozen TabPFN team-QB-quality cache pair."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager

import numpy as np

from . import route_final_served_calibration as calibration
from . import served_tail_calibration as served
from . import tabpfn_sched_final_served as inherited


TABLES = {
    "control": "tabpfn_team_qb_control_v1",
    "treatment": "tabpfn_team_qb_treatment_v1",
}
OUTPUT_PREFIX = "TABPFN_TEAM_QB_FINAL_SERVED_JSON="
EXPECTED_CACHE_ROWS = 52_307


@contextmanager
def _cache_environment(table: str):
    if table not in set(TABLES.values()):
        raise ValueError(f"unlicensed team-QB cache {table!r}")
    prior = os.environ.get("TABPFN_MARGINAL_TABLE")
    os.environ["TABPFN_MARGINAL_TABLE"] = table
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop("TABPFN_MARGINAL_TABLE", None)
        else:
            os.environ["TABPFN_MARGINAL_TABLE"] = prior


def _cache_keys(table: str, label_law: str, feature_law: str):
    from ..bq import query_df
    from ..config import settings

    return query_df(f"""
        SELECT season, week, gsis_id
        FROM `{settings.features}.{table}`
        WHERE season IN UNNEST(@seasons)
          AND label_law = @label_law AND feature_law = @feature_law
        ORDER BY season, week, gsis_id
        """, params={
            "seasons": list(calibration.ALL_SEASONS),
            "label_law": label_law,
            "feature_law": feature_law,
        })


def run(panel_id: str) -> dict:
    expected_panel = os.environ.get("TABPFN_TEAM_QB_PANEL_ID", "").strip()
    label_law = os.environ.get("TABPFN_TEAM_QB_LABEL_LAW", "").strip()
    feature_law = os.environ.get("TABPFN_TEAM_QB_FEATURE_LAW", "").strip()
    if not expected_panel or panel_id != expected_panel:
        raise ValueError("team-QB gate panel differs from terminal Tier-1 panel")
    if label_law not in {"current", "active_only"}:
        raise ValueError("team-QB gate requires the terminal label law")
    if feature_law not in {"base", "sched"}:
        raise ValueError("team-QB gate requires the terminal feature law")
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
        arm: _cache_keys(table, label_law, feature_law)
        for arm, table in TABLES.items()
    }
    if not cache_keys["control"].equals(cache_keys["treatment"]):
        raise ValueError("team-QB cache target keys differ")
    if len(cache_keys["control"]) != EXPECTED_CACHE_ROWS:
        raise ValueError("team-QB cache row count differs")

    folds = {arm: {} for arm in TABLES}
    parity = {arm: [] for arm in TABLES}
    with inherited._common_environment(usage):
        weight = effective_model_weight()
        if not np.isclose(weight, 0.45, rtol=0, atol=0):
            raise ValueError("team-QB gate blend weight differs")
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
                frame, aligned_draws, arm_parity = calibration._align_arm(
                    projected, draws, accepted, season_keys, season,
                    require_control_parity=False)
                folds[arm][season] = (frame, aligned_draws)
                parity[arm].append(arm_parity)

    report = calibration.evaluate_calibrated_arms(
        folds["control"], folds["treatment"])
    report["calibration_engine_disposition"] = report["disposition"]
    report["disposition"] = (
        "tabpfn-team-qb-final-served-passes"
        if report["gate"]["passes"]
        else "tabpfn-team-qb-final-served-fails"
    )
    report.update({
        "panel": panel_id,
        "version": "v1",
        "label_law": label_law,
        "feature_law": feature_law,
        "mode": "inherited-tabpfn-cache-vs-team-qb-cpoe-broadcast",
        "primary_population": "active RB/WR/TE",
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
