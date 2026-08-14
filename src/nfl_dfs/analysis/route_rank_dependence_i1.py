"""Frozen current-stack Route component/rank dependence screen (I1-R)."""

from __future__ import annotations

import base64
import json
import os
import zlib
from contextlib import contextmanager
from math import log

import numpy as np
import pandas as pd

from . import final_served_dependence as g0
from . import g1_archetype_topology as g1
from . import route_final_served_calibration as calibration
from . import served_position_calibration as position_calibration
from . import served_tail_calibration as served
from . import tabpfn_route_channel_final_served as route_gate
from . import tabpfn_sched_final_served as inherited
from .fantasy_points_route_share import ROUTE_FEATURES


CACHE_TABLE = "tabpfn_active_label_treatment_v2"
EXPECTED_CACHE_ROWS = 52_307
EXPECTED_SUPPORTED_ROWS = 7_848
EXPECTED_SLATES = 54
OUTPUT_CHUNK_PREFIX = "ROUTE_RANK_DEPENDENCE_I1_CHUNK="
OUTPUT_CHUNK_SIZE = 80_000
FAMILY_NAMES = (
    "g0_multiplicity_mse",
    "g0_role_pair_mse",
    "g1_primary_broad_mse",
    "g1_overall_joint_q90_brier",
    "g1_overall_variogram_p0_5",
)


@contextmanager
def _component_environment(route: bool):
    prior = os.environ.get("EXTRA_FEATURES")
    if prior and prior.strip():
        raise ValueError("Route rank gate inherited an EXTRA_FEATURES arm")
    if route:
        os.environ["EXTRA_FEATURES"] = ",".join(ROUTE_FEATURES)
    else:
        os.environ.pop("EXTRA_FEATURES", None)
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop("EXTRA_FEATURES", None)
        else:
            os.environ["EXTRA_FEATURES"] = prior


def _cache_keys():
    from ..bq import query_df
    from ..config import settings

    return query_df(f"""
        SELECT season, week, gsis_id
        FROM `{settings.features}.{CACHE_TABLE}`
        WHERE season IN UNNEST(@seasons)
        ORDER BY season, week, gsis_id
        """, params={"seasons": list(calibration.ALL_SEASONS)})


def _terminal_arm(
    *,
    route: bool,
    accepted: pd.DataFrame,
    cache_keys: pd.DataFrame,
    schedule: dict[int, dict],
) -> tuple[pd.DataFrame, np.ndarray, dict]:
    from ..backtest.replay import (
        _market_blend_worlds,
        load_panel_and_dst,
        replay_projections,
    )
    from ..models.blend import effective_model_weight
    from ..models.prop_market import market_points

    frames = []
    draw_parts = []
    parity = []
    maximum_mean_delta = 0.0
    weight = effective_model_weight()
    if not np.isclose(weight, 0.45, rtol=0, atol=0):
        raise ValueError("Route rank gate blend weight differs")
    for season in calibration.EVALUATION_SEASONS:
        panel, _ = load_panel_and_dst(season)
        market = market_points((season,)).drop_duplicates(
            ["season", "week", "gsis_id"])
        with _component_environment(route), g0._selected_cache(CACHE_TABLE):
            projected, draws = replay_projections(
                panel, season, n_sims=10_000, seed=0, return_draws=True)
        projected, draws, _ = _market_blend_worlds(
            projected, draws, market, weight)
        frame, aligned, arm_parity = calibration._align_arm(
            projected, draws, accepted,
            cache_keys[cache_keys.season.eq(season)], season,
            require_control_parity=False,
        )
        metadata = accepted[accepted.season.eq(season)][[
            "season", "week", "gsis_id", "pos", "team", "opp", "game_id",
        ]].rename(columns={"pos": "position"})
        frame = frame.merge(
            metadata,
            on=["season", "week", "gsis_id", "position"],
            how="left", validate="one_to_one",
        )
        if frame[["team", "opp", "game_id"]].isna().any().any():
            raise ValueError(f"Route rank {season} game metadata does not align")
        corrected = position_calibration.apply_position_scales(
            aligned, frame.position, schedule[season]["factors"])
        before = np.asarray(aligned, dtype=float).mean(axis=1)
        after = corrected.mean(axis=1)
        maximum_mean_delta = max(
            maximum_mean_delta,
            float(np.max(np.abs(after - before), initial=0.0)),
        )
        frame["mean_projection"] = after
        frames.append(frame)
        draw_parts.append(corrected)
        parity.append(arm_parity)
    return (
        pd.concat(frames, ignore_index=True),
        np.concatenate(draw_parts, axis=0),
        {"parity": parity, "maximum_mean_delta": maximum_mean_delta},
    )


def _broad_relationships(
    pairs: pd.DataFrame,
    frame: pd.DataFrame,
    draws: np.ndarray,
) -> tuple[dict, dict]:
    thresholds = np.quantile(draws, 0.90, axis=1)
    actual = frame.actual.to_numpy(float) > thresholds
    simulated = draws > thresholds[:, None]
    contributions = g1.pair_contributions(pairs, actual, simulated)
    broad = {
        str(relationship): g1._summarize_contributions(
            group, min_pairs=g1.BROAD_MIN_PAIRS,
            min_booms=g1.BROAD_MIN_BOOMS,
        )
        for relationship, group in contributions.groupby(
            "relationship", sort=True)
    }
    return broad, g1.pair_scorecard(pairs, frame, draws)


def _mean_squared_gap(rows: list[dict]) -> float:
    values = [
        float(row["log_simulated_to_realized"])
        for row in rows
        if row.get("supported")
        and row.get("log_simulated_to_realized") is not None
    ]
    if not values:
        raise ValueError("Route rank dependence family has no supported cells")
    return float(np.mean(np.square(values)))


def dependence_gate(
    control_g0: dict,
    route_g0: dict,
    control_broad: dict,
    route_broad: dict,
    control_scorecard: dict,
    route_scorecard: dict,
    sorted_marginal_delta: float,
    mean_delta: float = 0.0,
) -> dict:
    def g0_rows(report: dict, kind: str) -> list[dict]:
        return [
            row for row in report["cells"].values()
            if row.get("kind") == kind
        ]

    primary_control = [
        control_broad[name] for name in g1.PRIMARY_RELATIONSHIPS
        if name in control_broad
    ]
    primary_route = [
        route_broad[name] for name in g1.PRIMARY_RELATIONSHIPS
        if name in route_broad
    ]
    losses = {
        "control": {
            "g0_multiplicity_mse": _mean_squared_gap(
                g0_rows(control_g0, "multiplicity")),
            "g0_role_pair_mse": _mean_squared_gap(
                g0_rows(control_g0, "conditional")),
            "g1_primary_broad_mse": _mean_squared_gap(primary_control),
            "g1_overall_joint_q90_brier": float(
                control_scorecard["overall"]["joint_q90_brier"]),
            "g1_overall_variogram_p0_5": float(
                control_scorecard["overall"]["variogram_p0_5"]),
        },
        "route": {
            "g0_multiplicity_mse": _mean_squared_gap(
                g0_rows(route_g0, "multiplicity")),
            "g0_role_pair_mse": _mean_squared_gap(
                g0_rows(route_g0, "conditional")),
            "g1_primary_broad_mse": _mean_squared_gap(primary_route),
            "g1_overall_joint_q90_brier": float(
                route_scorecard["overall"]["joint_q90_brier"]),
            "g1_overall_variogram_p0_5": float(
                route_scorecard["overall"]["variogram_p0_5"]),
        },
    }
    ratios = {}
    for name in FAMILY_NAMES:
        base = losses["control"][name]
        value = losses["route"][name]
        if base <= 0 or not np.isfinite(base + value):
            raise ValueError(f"Route rank family {name} has invalid loss")
        ratios[name] = value / base

    hub = ("QB_WR", "QB_TE")
    hub_control = np.mean([
        abs(float(control_broad[name]["log_simulated_to_realized"]))
        for name in hub
    ])
    hub_route = np.mean([
        abs(float(route_broad[name]["log_simulated_to_realized"]))
        for name in hub
    ])
    relationship_regressions = []
    paired_score_regressions = []
    relationship_rows = {}
    for name in g1.PRIMARY_RELATIONSHIPS:
        left = control_broad.get(name)
        right = route_broad.get(name)
        if not left or not right or not left.get("supported") or not right.get(
            "supported"
        ):
            continue
        left_gap = abs(float(left["log_simulated_to_realized"]))
        right_gap = abs(float(right["log_simulated_to_realized"]))
        gap_increase = right_gap - left_gap
        if gap_increase > log(1.15):
            relationship_regressions.append(name)
        base_score = control_scorecard[name]
        route_score = route_scorecard[name]
        brier_ratio = (
            route_score["joint_q90_brier"] / base_score["joint_q90_brier"])
        variogram_ratio = (
            route_score["variogram_p0_5"] / base_score["variogram_p0_5"])
        if brier_ratio > 1.10 and variogram_ratio > 1.10:
            paired_score_regressions.append(name)
        relationship_rows[name] = {
            "control_abs_log_gap": left_gap,
            "route_abs_log_gap": right_gap,
            "abs_log_gap_increase": gap_increase,
            "joint_q90_brier_ratio": brier_ratio,
            "variogram_ratio": variogram_ratio,
        }

    checks = {
        "sorted_marginal_max_abs_delta_at_most_1e_10": (
            sorted_marginal_delta <= 1e-10),
        "mean_max_abs_delta_at_most_1e_10": mean_delta <= 1e-10,
        "equal_family_mean_ratio_below_1": float(np.mean(
            list(ratios.values()))) < 1.0,
        "at_least_three_families_improve": sum(
            value < 1.0 for value in ratios.values()) >= 3,
        "qb_wr_qb_te_mean_abs_gap_does_not_increase": hub_route <= hub_control,
        "no_primary_relationship_material_regression": (
            not relationship_regressions),
        "no_primary_relationship_double_score_regression": (
            not paired_score_regressions),
    }
    checks["passes"] = all(checks.values())
    return {
        "checks": checks,
        "losses": losses,
        "family_ratios": ratios,
        "equal_family_mean_ratio": float(np.mean(list(ratios.values()))),
        "improving_families": sorted([
            name for name, value in ratios.items() if value < 1.0]),
        "qb_hub": {
            "relationships": list(hub),
            "control_mean_abs_log_gap": float(hub_control),
            "route_mean_abs_log_gap": float(hub_route),
        },
        "relationship_regressions": relationship_regressions,
        "paired_score_regressions": paired_score_regressions,
        "relationships": relationship_rows,
    }


def encoded_report_lines(report: dict) -> list[str]:
    payload = json.dumps(
        report, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = base64.b64encode(zlib.compress(payload, level=9)).decode("ascii")
    chunks = [
        encoded[start:start + OUTPUT_CHUNK_SIZE]
        for start in range(0, len(encoded), OUTPUT_CHUNK_SIZE)
    ] or [""]
    total = len(chunks)
    return [
        f"{OUTPUT_CHUNK_PREFIX}{index}/{total}:{chunk}"
        for index, chunk in enumerate(chunks, start=1)
    ]


def run(panel_id: str) -> dict:
    expected_panel = os.environ.get("ROUTE_RANK_I1_PANEL_ID", "").strip()
    if not expected_panel or panel_id != expected_panel:
        raise ValueError("Route rank gate panel differs from historical panel")
    served._validate_environment()
    usage = inherited.accepted_usage_law()
    asoe = route_gate.selected_asoe_law()
    schedule = g0._selected_schedule({
        "G0_POSITION_SCHEDULE_B64": os.environ.get(
            "ROUTE_RANK_I1_POSITION_SCHEDULE_B64", "")
    })

    from ..bq import query_df
    from ..config import settings

    cache_keys = _cache_keys()
    if len(cache_keys) != EXPECTED_CACHE_ROWS or cache_keys.duplicated(
        ["season", "week", "gsis_id"]
    ).any():
        raise ValueError("Route rank cache keys differ")
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
        control_frame, control_draws, control_audit = _terminal_arm(
            route=False, accepted=accepted, cache_keys=cache_keys,
            schedule=schedule)
        route_frame, route_draws, route_audit = _terminal_arm(
            route=True, accepted=accepted, cache_keys=cache_keys,
            schedule=schedule)
    keys = [
        "season", "week", "gsis_id", "position", "team", "opp", "game_id",
        "actual",
    ]
    if not control_frame[keys].equals(route_frame[keys]):
        raise ValueError("Route rank control/treatment terminal rows differ")
    mean_delta = float(np.max(np.abs(
        control_frame.mean_projection.to_numpy(float)
        - route_frame.mean_projection.to_numpy(float)
    ), initial=0.0))
    sorted_delta = float(np.max(np.abs(
        np.sort(control_draws, axis=1) - np.sort(route_draws, axis=1)
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
        raise ValueError("Route rank control/treatment support rows differ")
    supported = control_frame[support].reset_index(drop=True)
    control_supported_draws = control_draws[support.to_numpy()]
    route_supported_draws = route_draws[support.to_numpy()]
    if len(supported) != EXPECTED_SUPPORTED_ROWS or supported[[
        "season", "week"]].drop_duplicates().shape[0] != EXPECTED_SLATES:
        raise ValueError("Route rank G0/G1 support population differs")
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
    control_g0 = g0.evaluate_dependence(
        control_frame, control_draws)
    route_g0 = g0.evaluate_dependence(route_frame, route_draws)
    control_broad, control_scorecard = _broad_relationships(
        pairs, supported, control_supported_draws)
    route_broad, route_scorecard = _broad_relationships(
        pairs, supported, route_supported_draws)
    gate = dependence_gate(
        control_g0, route_g0, control_broad, route_broad,
        control_scorecard, route_scorecard, sorted_delta, mean_delta)
    report = {
        "version": "i1-r-v1",
        "panel": panel_id,
        "disposition": (
            "route-rank-dependence-i1-passes"
            if gate["checks"]["passes"]
            else "route-rank-dependence-i1-fails"),
        "cache_table": CACHE_TABLE,
        "component_feature_difference": list(ROUTE_FEATURES),
        "common_usage_law": usage,
        "common_phase_s_asoe_law": asoe,
        "common_position_schedule": {
            str(key): value for key, value in schedule.items()},
        "sorted_marginal_max_abs_delta": sorted_delta,
        "mean_max_abs_delta": mean_delta,
        "control_audit": control_audit,
        "route_audit": route_audit,
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
        "route": {
            "g0": route_g0,
            "g1_broad_relationships": route_broad,
            "g1_scorecard": route_scorecard,
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


__all__ = [
    "_component_environment", "dependence_gate", "encoded_report_lines",
    "run",
]
