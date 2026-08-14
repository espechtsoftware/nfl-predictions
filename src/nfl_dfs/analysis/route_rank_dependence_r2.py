"""Frozen fixed-midpoint Route component dependence screen (R2)."""

from __future__ import annotations

import os

import numpy as np

from . import final_served_dependence as g0
from . import g1_archetype_topology as g1
from . import route_final_served_calibration as calibration
from . import route_rank_dependence_i1 as i1
from . import served_tail_calibration as served
from . import tabpfn_route_channel_final_served as route_gate
from . import tabpfn_sched_final_served as inherited
from .fantasy_points_route_share import ROUTE_FEATURES


CACHE_TABLE = i1.CACHE_TABLE
EXPECTED_CACHE_ROWS = i1.EXPECTED_CACHE_ROWS
EXPECTED_SUPPORTED_ROWS = i1.EXPECTED_SUPPORTED_ROWS
EXPECTED_SLATES = i1.EXPECTED_SLATES
MIDPOINT_WEIGHT = 0.5
OUTPUT_CHUNK_PREFIX = "ROUTE_RANK_DEPENDENCE_R2_CHUNK="
OUTPUT_CHUNK_SIZE = 80_000


def midpoint_rank_remap(
    control_draws: np.ndarray,
    route_draws: np.ndarray,
) -> np.ndarray:
    """Rank exact control values by the fixed control/Route midpoint score."""
    control = np.asarray(control_draws)
    route = np.asarray(route_draws)
    if control.ndim != 2 or route.shape != control.shape:
        raise ValueError("R2 control and Route draws must be aligned 2-D arrays")
    if not np.isfinite(control).all() or not np.isfinite(route).all():
        raise ValueError("R2 control and Route draws must be finite")

    score = MIDPOINT_WEIGHT * control + MIDPOINT_WEIGHT * route
    rank_order = np.argsort(score, axis=1, kind="stable")
    sorted_control = np.sort(control, axis=1, kind="stable")
    treatment = np.empty_like(control)
    np.put_along_axis(treatment, rank_order, sorted_control, axis=1)
    return treatment


def encoded_report_lines(report: dict) -> list[str]:
    prior_prefix = i1.OUTPUT_CHUNK_PREFIX
    prior_size = i1.OUTPUT_CHUNK_SIZE
    try:
        i1.OUTPUT_CHUNK_PREFIX = OUTPUT_CHUNK_PREFIX
        i1.OUTPUT_CHUNK_SIZE = OUTPUT_CHUNK_SIZE
        return i1.encoded_report_lines(report)
    finally:
        i1.OUTPUT_CHUNK_PREFIX = prior_prefix
        i1.OUTPUT_CHUNK_SIZE = prior_size


def run(panel_id: str) -> dict:
    expected_panel = os.environ.get("ROUTE_RANK_R2_PANEL_ID", "").strip()
    if not expected_panel or panel_id != expected_panel:
        raise ValueError("Route rank R2 panel differs from historical panel")
    served._validate_environment()
    usage = inherited.accepted_usage_law()
    asoe = route_gate.selected_asoe_law()
    schedule = g0._selected_schedule({
        "G0_POSITION_SCHEDULE_B64": os.environ.get(
            "ROUTE_RANK_R2_POSITION_SCHEDULE_B64", "")
    })

    from ..bq import query_df
    from ..config import settings

    cache_keys = i1._cache_keys()
    if len(cache_keys) != EXPECTED_CACHE_ROWS or cache_keys.duplicated(
        ["season", "week", "gsis_id"]
    ).any():
        raise ValueError("Route rank R2 cache keys differ")
    accepted = query_df(f"""
        SELECT season, week, gsis_id, pos, team, opp, game_id, actual,
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
    with inherited._common_environment(usage):
        control_frame, control_draws, control_audit = i1._terminal_arm(
            route=False, accepted=accepted, cache_keys=cache_keys,
            schedule=schedule)
        route_frame, route_draws, route_audit = i1._terminal_arm(
            route=True, accepted=accepted, cache_keys=cache_keys,
            schedule=schedule)
    keys = [
        "season", "week", "gsis_id", "position", "team", "opp", "game_id",
        "actual",
    ]
    if not control_frame[keys].equals(route_frame[keys]):
        raise ValueError("Route rank R2 component rows differ")

    treatment_draws = midpoint_rank_remap(control_draws, route_draws)
    treatment_frame = control_frame.copy()
    sorted_delta = float(np.max(np.abs(
        np.sort(control_draws, axis=1, kind="stable")
        - np.sort(treatment_draws, axis=1, kind="stable")
    ), initial=0.0))
    mean_delta = float(np.max(np.abs(
        control_draws.mean(axis=1) - treatment_draws.mean(axis=1)
    ), initial=0.0))
    raw_route_sorted_delta = float(np.max(np.abs(
        np.sort(control_draws, axis=1, kind="stable")
        - np.sort(route_draws, axis=1, kind="stable")
    ), initial=0.0))
    raw_route_mean_delta = float(np.max(np.abs(
        control_draws.mean(axis=1) - route_draws.mean(axis=1)
    ), initial=0.0))

    support = (
        control_frame.position.isin(g1.POSITIONS)
        & control_frame.mean_projection.ge(g0.MIN_MEAN)
    )
    route_support = (
        route_frame.position.isin(g1.POSITIONS)
        & route_frame.mean_projection.ge(g0.MIN_MEAN)
    )
    if not support.equals(route_support):
        raise ValueError("Route rank R2 component support rows differ")
    supported = control_frame[support].reset_index(drop=True)
    control_supported_draws = control_draws[support.to_numpy()]
    treatment_supported_draws = treatment_draws[support.to_numpy()]
    if len(supported) != EXPECTED_SUPPORTED_ROWS or supported[[
        "season", "week"
    ]].drop_duplicates().shape[0] != EXPECTED_SLATES:
        raise ValueError("Route rank R2 G0/G1 support population differs")
    games = query_df(f"""
        SELECT gsis_id, position, season, week, y_dk_points AS dk_points,
               was_active
        FROM `{settings.features}.player_week_training`
        WHERE season IN UNNEST(@seasons)
          AND position IN UNNEST(@positions)
          AND was_active
        ORDER BY season, week, gsis_id
        """, params={
            "seasons": list(g1.HISTORY_SEASONS),
            "positions": list(g1.POSITIONS),
        })
    supported, archetype_audit = g1.attach_walk_forward_archetypes(
        supported, games)
    pairs = g1.build_pair_book(supported)
    control_g0 = g0.evaluate_dependence(control_frame, control_draws)
    treatment_g0 = g0.evaluate_dependence(treatment_frame, treatment_draws)
    control_broad, control_scorecard = i1._broad_relationships(
        pairs, supported, control_supported_draws)
    treatment_broad, treatment_scorecard = i1._broad_relationships(
        pairs, supported, treatment_supported_draws)
    gate = i1.dependence_gate(
        control_g0, treatment_g0, control_broad, treatment_broad,
        control_scorecard, treatment_scorecard, sorted_delta, mean_delta)
    report = {
        "version": "route-rank-r2-v1",
        "panel": panel_id,
        "disposition": (
            "route-rank-dependence-r2-passes"
            if gate["checks"]["passes"]
            else "route-rank-dependence-r2-fails"),
        "cache_table": CACHE_TABLE,
        "component_feature_difference": list(ROUTE_FEATURES),
        "midpoint_weight": MIDPOINT_WEIGHT,
        "rank_transform": "stable-midpoint-rank-map-exact-control-values",
        "common_usage_law": usage,
        "common_phase_s_asoe_law": asoe,
        "common_position_schedule": {
            str(key): value for key, value in schedule.items()},
        "sorted_marginal_max_abs_delta": sorted_delta,
        "mean_max_abs_delta": mean_delta,
        "raw_route_component": {
            "sorted_marginal_max_abs_delta": raw_route_sorted_delta,
            "mean_max_abs_delta": raw_route_mean_delta,
            "audit": route_audit,
        },
        "control_audit": control_audit,
        "population": {
            "rows": int(len(supported)),
            "slates": EXPECTED_SLATES,
            "pairs": int(len(pairs)),
        },
        "archetypes": archetype_audit,
        "control": {
            "g0": control_g0,
            "g1_broad_relationships": control_broad,
            "g1_scorecard": control_scorecard,
        },
        "treatment": {
            "g0": treatment_g0,
            "g1_broad_relationships": treatment_broad,
            "g1_scorecard": treatment_scorecard,
        },
        "gate": gate,
        "bootstrap": {
            "g0_replicates": g0.N_BOOTSTRAPS,
            "g0_seed": g0.BOOTSTRAP_SEED,
            "g1_replicates": g1.N_BOOTSTRAPS,
            "g1_seed": g1.BOOTSTRAP_SEED,
            "cluster": "season-week-slate",
        },
    }
    for line in encoded_report_lines(report):
        print(line)
    return report


__all__ = ["encoded_report_lines", "midpoint_rank_remap", "run"]
