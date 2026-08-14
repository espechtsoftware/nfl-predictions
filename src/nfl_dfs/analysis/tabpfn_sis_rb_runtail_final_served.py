"""Score-free final-served gate for the adaptive SIS RB run-tail arm."""

from __future__ import annotations

import base64
from contextlib import contextmanager
from hashlib import sha256
import json
import os
import zlib

import numpy as np
import pandas as pd

from . import route_final_served_calibration as calibration
from . import served_tail_calibration as served
from . import tabpfn_sched_final_served as inherited
from . import tabpfn_sis_pass_tail_final_served as pass_tail


TABLES = {
    "control": "tabpfn_sis_rb_runtail_control_v1",
    "treatment": "tabpfn_sis_rb_runtail_treatment_v1",
}
OUTPUT_CHUNK_PREFIX = "TABPFN_SIS_RB_RUNTAIL_FINAL_SERVED_CHUNK="
OUTPUT_META_PREFIX = "TABPFN_SIS_RB_RUNTAIL_FINAL_SERVED_META="
OUTPUT_CHUNK_SIZE = 80_000
EXPECTED_CACHE_ROWS = 52_307
EXPECTED_RB_ROWS = {2023: 1329, 2024: 1307, 2025: 1325}


@contextmanager
def _cache_environment(table: str):
    if table not in set(TABLES.values()):
        raise ValueError(f"unlicensed SIS RB run-tail cache {table!r}")
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


def _proper_score_ratio(
    control: pd.DataFrame, treatment: pd.DataFrame,
) -> dict:
    cells = []
    for quantile in (95, 99):
        base = float(control[f"pinball_q{quantile}"].mean())
        value = float(treatment[f"pinball_q{quantile}"].mean())
        if base <= 0 or not np.isfinite(base + value):
            raise ValueError("invalid SIS RB run-tail pinball ratio")
        cells.append({
            "quantile": quantile,
            "control_pinball": base,
            "treatment_pinball": value,
            "treatment_to_control_ratio": value / base,
        })
    return {
        "equal_q95_q99_mean_ratio": float(np.mean([
            row["treatment_to_control_ratio"] for row in cells
        ])),
        "cells": cells,
    }


def _summaries(rows: pd.DataFrame) -> dict:
    return {
        "aggregate": pass_tail._summary(rows, "aggregate"),
        "seasons": {
            str(season): pass_tail._summary(
                rows[rows.season.eq(season)], str(season)
            )
            for season in calibration.EVALUATION_SEASONS
        },
    }


def evaluate_runtail_arms(
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
            raise ValueError(f"SIS RB run-tail arm rows differ in {season}")
    schedules = {
        "control": calibration.fit_walk_forward_schedule(control_folds),
        "treatment": calibration.fit_walk_forward_schedule(treatment_folds),
    }
    control_scores, control_delta = pass_tail._score_schedule(
        control_folds, schedules["control"]
    )
    treatment_scores, treatment_delta = pass_tail._score_schedule(
        treatment_folds, schedules["treatment"]
    )
    keys = ["season", "week", "gsis_id", "position", "actual"]
    if not control_scores[keys].equals(treatment_scores[keys]):
        raise ValueError("SIS RB run-tail calibrated rows differ")
    control_rb = control_scores[control_scores.position.eq("RB")].reset_index(
        drop=True
    )
    treatment_rb = treatment_scores[
        treatment_scores.position.eq("RB")
    ].reset_index(drop=True)
    counts = control_rb.groupby("season").size().to_dict()
    if counts != EXPECTED_RB_ROWS:
        raise ValueError(f"SIS RB run-tail primary rows differ: {counts}")
    ratios = _proper_score_ratio(control_rb, treatment_rb)
    maximum_delta = max(control_delta, treatment_delta)
    gate = {
        "equal_q95_q99_mean_ratio_below_1": (
            ratios["equal_q95_q99_mean_ratio"] < 1.0
        ),
        "maximum_mean_delta_at_most_1e_10": maximum_delta <= 1e-10,
    }
    gate["passes"] = all(gate.values())
    return {
        "control_schedule": {
            str(key): value for key, value in schedules["control"].items()
        },
        "treatment_schedule": {
            str(key): value for key, value in schedules["treatment"].items()
        },
        "control": _summaries(control_rb),
        "treatment": _summaries(treatment_rb),
        "proper_score_ratio": ratios,
        "maximum_mean_delta": {
            "control": control_delta, "treatment": treatment_delta,
        },
        "paired_loss_uncertainty": pass_tail._paired_uncertainty(
            control_rb, treatment_rb
        ),
        "gate": gate,
    }


def encoded_report_lines(report: dict) -> list[str]:
    payload = json.dumps(
        report, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    compressed = zlib.compress(payload, level=9)
    encoded = base64.b64encode(compressed).decode("ascii")
    chunks = [
        encoded[start:start + OUTPUT_CHUNK_SIZE]
        for start in range(0, len(encoded), OUTPUT_CHUNK_SIZE)
    ] or [""]
    meta = {
        "chunks": len(chunks),
        "json_bytes": len(payload),
        "json_sha256": sha256(payload).hexdigest(),
        "zlib_bytes": len(compressed),
        "zlib_sha256": sha256(compressed).hexdigest(),
    }
    lines = [OUTPUT_META_PREFIX + json.dumps(meta, sort_keys=True)]
    lines.extend(
        f"{OUTPUT_CHUNK_PREFIX}{index}/{len(chunks)}:{chunk}"
        for index, chunk in enumerate(chunks)
    )
    return lines


def run(panel_id: str) -> dict:
    expected = os.environ.get("TABPFN_SIS_RB_RUNTAIL_PANEL_ID", "").strip()
    if not expected or panel_id != expected:
        raise ValueError("SIS RB run-tail panel differs")
    served._validate_environment()
    usage = inherited.accepted_usage_law()

    from ..backtest.replay import (
        _market_blend_worlds, load_panel_and_dst, replay_projections,
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
          AND season IN UNNEST(@seasons) AND pos IN UNNEST(@positions)
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
        raise ValueError("SIS RB run-tail cache keys differ")
    if len(cache_keys["control"]) != EXPECTED_CACHE_ROWS:
        raise ValueError("SIS RB run-tail cache row count differs")

    folds = {arm: {} for arm in TABLES}
    parity = {arm: [] for arm in TABLES}
    with inherited._common_environment(usage):
        weight = effective_model_weight()
        if not np.isclose(weight, 0.45, rtol=0, atol=0):
            raise ValueError("SIS RB run-tail blend weight differs")
        for season in calibration.ALL_SEASONS:
            panel, _ = load_panel_and_dst(season)
            market = market_points((season,)).drop_duplicates(
                ["season", "week", "gsis_id"]
            )
            for arm, table in TABLES.items():
                with _cache_environment(table):
                    projected, draws = replay_projections(
                        panel, season, n_sims=served.N_SIMS, seed=0,
                        return_draws=True,
                    )
                projected, draws, _ = _market_blend_worlds(
                    projected, draws, market, weight
                )
                season_keys = cache_keys[arm][
                    cache_keys[arm].season.eq(season)
                ]
                frame, aligned, arm_parity = calibration._align_arm(
                    projected, draws, accepted, season_keys, season,
                    require_control_parity=False,
                )
                folds[arm][season] = (frame, aligned)
                parity[arm].append(arm_parity)

    report = evaluate_runtail_arms(folds["control"], folds["treatment"])
    report.update({
        "disposition": (
            "tabpfn-sis-rb-runtail-final-served-passes"
            if report["gate"]["passes"]
            else "tabpfn-sis-rb-runtail-final-served-fails"
        ),
        "panel": panel_id,
        "version": "v1",
        "adaptive_retrospective": True,
        "label_law": "active_only",
        "feature_law": "base",
        "mode": "shared-33-vs-sis-rb-opponent-run-tail-two-column-cache",
        "primary_population": "active RB",
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
    for line in encoded_report_lines(report):
        print(line, flush=True)
    return report


__all__ = [
    "TABLES", "_cache_environment", "encoded_report_lines",
    "evaluate_runtail_arms", "run",
]
