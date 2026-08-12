"""Final-served gate for the frozen TabPFN SCHED feature-sync pair."""

from __future__ import annotations

import json
import math
import os
from contextlib import contextmanager

import numpy as np

from . import route_final_served_calibration as calibration
from . import served_tail_calibration as served


TABLES = {
    "control": "tabpfn_sched_control_v1",
    "treatment": "tabpfn_sched_treatment_v1",
}
OUTPUT_PREFIX = "TABPFN_SCHED_FINAL_SERVED_JSON="
EXPECTED_CACHE_ROWS = 52_307


def accepted_usage_law() -> dict[str, str]:
    """Validate the exact terminal usage branch supplied by the runner."""
    selected = os.environ.get("TABPFN_ACCEPTED_USAGE_LAW", "").strip().lower()
    selected_k = os.environ.get("TABPFN_ACCEPTED_DIRICHLET_K", "").strip()
    mode = os.environ.get("GAME_SIM_USAGE", "").strip().lower()
    value = os.environ.get("DIRICHLET_K", "").strip()
    if selected == "multinomial":
        if mode not in ("", "off", "false", "none") or value or selected_k:
            raise ValueError("SCHED multinomial branch has stray Dirichlet config")
        return {
            "mode": "production-multinomial",
            "game_sim_usage": "",
            "k": "",
        }
    if selected != "dirichlet":
        raise ValueError("SCHED gate requires an explicit accepted usage law")
    if mode != "dirichlet" or not selected_k or value != selected_k:
        raise ValueError("SCHED Dirichlet branch differs from accepted fitted K")
    try:
        numeric_k = float(value)
    except ValueError as exc:
        raise ValueError("SCHED accepted fitted K is not numeric") from exc
    if not math.isfinite(numeric_k) or numeric_k <= 0:
        raise ValueError("SCHED accepted fitted K must be finite and positive")
    return {
        "mode": "data-fitted-dirichlet",
        "game_sim_usage": "dirichlet",
        "k": value,
    }


@contextmanager
def _common_environment(usage: dict[str, str]):
    with served._production_environment():
        os.environ["GAME_SIM_USAGE"] = usage["game_sim_usage"]
        if usage["k"]:
            os.environ["DIRICHLET_K"] = usage["k"]
        else:
            os.environ.pop("DIRICHLET_K", None)
        yield


@contextmanager
def _cache_environment(table: str):
    if table not in set(TABLES.values()):
        raise ValueError(f"unlicensed SCHED cache {table!r}")
    prior = os.environ.get("TABPFN_MARGINAL_TABLE")
    os.environ["TABPFN_MARGINAL_TABLE"] = table
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop("TABPFN_MARGINAL_TABLE", None)
        else:
            os.environ["TABPFN_MARGINAL_TABLE"] = prior


def _cache_keys(table: str, label_law: str):
    from ..bq import query_df
    from ..config import settings

    return query_df(f"""
        SELECT season, week, gsis_id
        FROM `{settings.features}.{table}`
        WHERE season IN UNNEST(@seasons) AND label_law = @label_law
        ORDER BY season, week, gsis_id
        """, params={
            "seasons": list(calibration.ALL_SEASONS),
            "label_law": label_law,
        })


def run(panel_id: str) -> dict:
    expected_panel = os.environ.get("TABPFN_SCHED_PANEL_ID", "").strip()
    label_law = os.environ.get("TABPFN_SCHED_LABEL_LAW", "").strip()
    if not expected_panel or panel_id != expected_panel:
        raise ValueError("SCHED gate panel differs from terminal Tier-1 panel")
    if label_law not in {"current", "active_only"}:
        raise ValueError("SCHED gate requires the terminal label law")
    served._validate_environment()
    usage = accepted_usage_law()

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
        arm: _cache_keys(table, label_law) for arm, table in TABLES.items()
    }
    if not cache_keys["control"].equals(cache_keys["treatment"]):
        raise ValueError("SCHED cache target keys differ")
    if len(cache_keys["control"]) != EXPECTED_CACHE_ROWS:
        raise ValueError("SCHED cache row count differs")

    folds = {arm: {} for arm in TABLES}
    parity = {arm: [] for arm in TABLES}
    with _common_environment(usage):
        weight = effective_model_weight()
        if not np.isclose(weight, 0.45, rtol=0, atol=0):
            raise ValueError("SCHED gate blend weight differs")
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
        "tabpfn-sched-final-served-passes"
        if report["gate"]["passes"]
        else "tabpfn-sched-final-served-fails"
    )
    report.update({
        "panel": panel_id,
        "version": "v1",
        "label_law": label_law,
        "mode": "same-label-shared-33-vs-sched-plus-two-tabpfn-cache",
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
