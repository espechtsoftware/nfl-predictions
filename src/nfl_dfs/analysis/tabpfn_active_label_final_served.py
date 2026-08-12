"""Final-served gate for the frozen TabPFN active-label correction."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager

import numpy as np

from ..ingest.fantasy_points_route import PANEL_ID
from ..research.usage_dirichlet_lineup import FITTED_K
from . import route_final_served_calibration as calibration
from . import served_tail_calibration as served


CONTROL_TABLE = "tabpfn_active_label_control_v1"
TREATMENT_TABLE = "tabpfn_active_label_treatment_v1"
TABLES = {"control": CONTROL_TABLE, "treatment": TREATMENT_TABLE}
FITTED_K_TEXT = FITTED_K
OUTPUT_PREFIX = "TABPFN_ACTIVE_LABEL_FINAL_SERVED_JSON="


def _accepted_usage_law() -> dict[str, str]:
    """Validate the simulator law selected by the earlier frozen decision."""
    mode = os.environ.get("GAME_SIM_USAGE", "").strip().lower()
    value = os.environ.get("DIRICHLET_K", "").strip()
    if mode in ("", "off", "false", "none"):
        if value:
            raise ValueError("DIRICHLET_K is set while fitted-K usage is inactive")
        return {"mode": "production-multinomial", "game_sim_usage": "", "k": ""}
    if mode != "dirichlet":
        raise ValueError(f"unsupported accepted GAME_SIM_USAGE={mode!r}")
    if value != FITTED_K_TEXT or not np.isclose(
            float(value), float(FITTED_K), rtol=0, atol=0):
        raise ValueError("active-label gate requires the exact frozen fitted K")
    return {
        "mode": "data-fitted-dirichlet",
        "game_sim_usage": "dirichlet",
        "k": FITTED_K_TEXT,
    }


@contextmanager
def _common_environment(usage: dict[str, str]):
    """Apply the production book plus the already-decided common usage law."""
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
        raise ValueError(f"unlicensed active-label cache {table!r}")
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
        ORDER BY season, week, gsis_id
        """, params={"seasons": list(calibration.ALL_SEASONS)})


def run(panel_id: str = PANEL_ID) -> dict:
    """Run the one frozen active-label final-served comparison."""
    if panel_id != PANEL_ID:
        raise ValueError(f"active-label gate is frozen to panel {PANEL_ID}")
    served._validate_environment()
    usage = _accepted_usage_law()

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
        raise ValueError("active-label cache target keys differ")

    folds = {arm: {} for arm in TABLES}
    parity = {arm: [] for arm in TABLES}
    with _common_environment(usage):
        weight = effective_model_weight()
        if not np.isclose(weight, 0.45, rtol=0, atol=0):
            raise ValueError("active-label gate blend weight differs")
        for season in calibration.ALL_SEASONS:
            panel, _ = load_panel_and_dst(season)
            market = market_points((season,)).drop_duplicates(
                ["season", "week", "gsis_id"])
            for arm, table in TABLES.items():
                with _cache_environment(table):
                    projected, draws = replay_projections(
                        panel,
                        season,
                        n_sims=served.N_SIMS,
                        seed=0,
                        return_draws=True,
                    )
                projected, draws, _ = _market_blend_worlds(
                    projected, draws, market, weight)
                season_keys = cache_keys[arm][
                    cache_keys[arm].season.eq(season)]
                frame, aligned_draws, arm_parity = calibration._align_arm(
                    projected,
                    draws,
                    accepted,
                    season_keys,
                    season,
                    require_control_parity=False,
                )
                folds[arm][season] = (frame, aligned_draws)
                parity[arm].append(arm_parity)

    report = calibration.evaluate_calibrated_arms(
        folds["control"], folds["treatment"])
    report["calibration_engine_disposition"] = report["disposition"]
    report["disposition"] = (
        "tabpfn-active-label-final-served-passes"
        if report["gate"]["passes"]
        else "tabpfn-active-label-final-served-fails"
    )
    report.update({
        "panel": panel_id,
        "mode": "same-code-current-label-vs-active-only-tabpfn-cache",
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
