"""Frozen G2 QB-rooted upper-tail Gumbel dependence calibration and gate.

The immutable scientific contract is
``reports/2026-08-12-g2-qb-gumbel-factor-protocol.md``.  This diagnostic is
lineup-free.  It may license, but never performs, a later exact-80 replay.
"""

from __future__ import annotations

from contextlib import contextmanager
import gc
from hashlib import sha256
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from . import final_served_dependence as g0
from . import g1_archetype_topology as g1
from ..research.qb_gumbel_factor import apply_qb_gumbel_factor


OUTPUT_META_PREFIX = "G2_QB_GUMBEL_FACTOR_META="
OUTPUT_CHUNK_PREFIX = "G2_QB_GUMBEL_FACTOR_CHUNK="
CALIBRATION_META_PREFIX = "G2_QB_GUMBEL_CALIBRATION_META="
CALIBRATION_CHUNK_PREFIX = "G2_QB_GUMBEL_CALIBRATION_CHUNK="
CALIBRATION_SEASONS = (2019, 2021, 2022)
EVALUATION_SEASONS = (2023, 2024, 2025)
THETA_GRID = (1.00, 1.05, 1.10, 1.15, 1.20, 1.30, 1.40, 1.60, 2.00)
TARGET_RELATIONSHIPS = ("QB_WR", "QB_TE")
PRIMARY_WEIGHTS = {
    "QB_WR": 3.0,
    "QB_TE": 2.0,
    "QB_RB": 1.0,
    "WR_WR": 2.0,
    "RB_RB": 1.0,
    "TE_TE": 1.0,
    "QB_OPP_QB": 1.0,
    "QB_OPP_WR": 1.0,
    "QB_OPP_TE": 1.0,
    "WR_OPP_WR": 1.0,
}
HISTORICAL_CACHE = "tabpfn_projections_pit_v2"
N_BOOTSTRAPS = 2_000
BOOTSTRAP_SEED = 1_703
FLOAT_TOLERANCE = 1e-12


def _load_json(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _emit_transport(report: dict, meta_prefix: str, chunk_prefix: str) -> None:
    meta, chunks = g1.encode_report_transport(report)
    print(meta_prefix + json.dumps(meta, sort_keys=True), flush=True)
    for index, chunk in enumerate(chunks):
        print(f"{chunk_prefix}{index}/{len(chunks)}:{chunk}", flush=True)


def _require_reference_hash(path: str | Path, environment_name: str) -> dict:
    source = Path(path)
    expected = os.environ.get(environment_name, "").strip()
    if not expected:
        raise ValueError(f"G2 environment {environment_name} is missing")
    observed = sha256(source.read_bytes()).hexdigest()
    if observed != expected:
        raise ValueError(f"G2 prerequisite {source.name} hash differs")
    return _load_json(source)


def _filter_pairs(pairs: pd.DataFrame, relationship: str) -> pd.DataFrame:
    result = pairs[pairs.relationship.eq(relationship)].copy()
    if result.empty:
        raise ValueError(f"G2 has no {relationship} calibration pairs")
    return result


def _single_score(
    pairs: pd.DataFrame,
    frame: pd.DataFrame,
    draws: np.ndarray,
    relationship: str,
) -> dict:
    return g1.pair_scorecard(
        _filter_pairs(pairs, relationship), frame, draws,
    )[relationship]


def select_grid_cell(grid: list[dict]) -> dict:
    """Apply the frozen tolerance and deterministic G2 tiebreaks."""
    if not grid:
        raise ValueError("G2 theta grid is empty")
    best_brier = min(row["joint_q90_brier"] for row in grid)
    tied = [
        row for row in grid
        if row["joint_q90_brier"] <= best_brier + FLOAT_TOLERANCE
    ]
    best_variogram = min(row["variogram_p0_5"] for row in tied)
    tied = [
        row for row in tied
        if row["variogram_p0_5"] <= best_variogram + FLOAT_TOLERANCE
    ]
    return min(tied, key=lambda row: (
        row["theta_wr"] + row["theta_te"],
        row["theta_wr"],
        row["theta_te"],
    ))


def fit_theta_grid(
    frame: pd.DataFrame,
    draws: np.ndarray,
    pairs: pd.DataFrame,
) -> tuple[dict, list[dict], dict]:
    """Fit the frozen Cartesian grid without touching held-out outcomes."""
    counts = {
        relationship: int(_filter_pairs(pairs, relationship).shape[0])
        for relationship in TARGET_RELATIONSHIPS
    }
    relationship_scores: dict[str, dict[float, dict]] = {
        relationship: {} for relationship in TARGET_RELATIONSHIPS
    }
    audits: dict[str, dict[float, dict]] = {
        relationship: {} for relationship in TARGET_RELATIONSHIPS
    }
    for relationship in TARGET_RELATIONSHIPS:
        for theta in THETA_GRID:
            theta_wr = theta if relationship == "QB_WR" else 1.0
            theta_te = theta if relationship == "QB_TE" else 1.0
            treatment, audit = apply_qb_gumbel_factor(
                draws, frame, theta_wr=theta_wr, theta_te=theta_te)
            relationship_scores[relationship][theta] = _single_score(
                pairs, frame, treatment, relationship)
            audits[relationship][theta] = audit

    total = float(sum(counts.values()))
    grid = []
    for theta_wr in THETA_GRID:
        for theta_te in THETA_GRID:
            wr = relationship_scores["QB_WR"][theta_wr]
            te = relationship_scores["QB_TE"][theta_te]
            grid.append({
                "theta_wr": float(theta_wr),
                "theta_te": float(theta_te),
                "joint_q90_brier": float(
                    (counts["QB_WR"] * wr["joint_q90_brier"]
                     + counts["QB_TE"] * te["joint_q90_brier"]) / total),
                "variogram_p0_5": float(
                    (counts["QB_WR"] * wr["variogram_p0_5"]
                     + counts["QB_TE"] * te["variogram_p0_5"]) / total),
                "relationship_scores": {
                    "QB_WR": wr,
                    "QB_TE": te,
                },
            })
    selected = select_grid_cell(grid)
    return selected, grid, {
        "relationship_pair_counts": counts,
        "theta_audits": {
            relationship: {
                str(theta): value for theta, value in values.items()
            }
            for relationship, values in audits.items()
        },
    }


def _weighted_score(scorecard: dict, metric: str) -> float:
    missing = set(PRIMARY_WEIGHTS) - set(scorecard)
    if missing:
        raise ValueError(f"G2 scorecard missing {sorted(missing)}")
    denominator = float(sum(PRIMARY_WEIGHTS.values()))
    return float(sum(
        weight * float(scorecard[relationship][metric])
        for relationship, weight in PRIMARY_WEIGHTS.items()
    ) / denominator)


def _g0_abs_log_error(report: dict) -> tuple[float, dict]:
    values = {}
    for cell in g0.CELL_BANDS:
        row = report["cells"].get(cell, {})
        value = row.get("log_simulated_to_realized")
        if row.get("supported") and value is not None and np.isfinite(value):
            values[cell] = abs(float(value))
    if not values:
        raise ValueError("G2 held-out G0 has no supported cells")
    return float(sum(values.values())), values


def _g1_abs_log_error(broad: dict) -> tuple[float, dict]:
    values = {}
    for relationship, weight in PRIMARY_WEIGHTS.items():
        row = broad.get(relationship, {})
        value = row.get("log_simulated_to_realized")
        if not row.get("supported"):
            continue
        if value is None or not np.isfinite(value):
            raise ValueError(f"G2 held-out G1 value missing for {relationship}")
        values[relationship] = {
            "absolute_log_error": abs(float(value)),
            "weight": float(weight),
        }
    if not set(TARGET_RELATIONSHIPS).issubset(values):
        raise ValueError("G2 held-out QB-receiver support is incomplete")
    total = float(sum(
        row["weight"] * row["absolute_log_error"] for row in values.values()
    ))
    return total, values


def score_heldout(
    frame: pd.DataFrame,
    draws: np.ndarray,
    games: pd.DataFrame,
) -> dict:
    """Recompute the frozen G0/G1 score-free held-out diagnostics."""
    full_g0 = g0.evaluate_dependence(frame, draws)
    mask = (
        frame.position.isin(g1.POSITIONS)
        & frame.mean_projection.ge(g0.MIN_MEAN)
    ).to_numpy(bool)
    supported = frame.loc[mask].reset_index(drop=True)
    supported_draws = np.asarray(draws)[mask]
    supported, archetype_audit = g1.attach_walk_forward_archetypes(
        supported, games)
    pairs = g1.build_pair_book(supported)
    thresholds = np.quantile(supported_draws, 0.90, axis=1)
    actual_flags = supported.actual.to_numpy(float) > thresholds
    simulated_flags = supported_draws > thresholds[:, None]
    contributions = g1.pair_contributions(
        pairs, actual_flags, simulated_flags)
    cells, broad = g1.summarize_cells(contributions)
    scorecard = g1.pair_scorecard(pairs, supported, supported_draws)
    g0_abs, g0_cells = _g0_abs_log_error(full_g0)
    g1_abs, g1_cells = _g1_abs_log_error(broad)
    return {
        "population": {
            "rows": int(len(supported)),
            "slates": int(supported[["season", "week"]].drop_duplicates().shape[0]),
            "pairs": int(len(pairs)),
            "relationship_counts": {
                str(key): int(value) for key, value in
                pairs.relationship.value_counts().sort_index().items()
            },
        },
        "archetypes": archetype_audit,
        "g0": full_g0,
        "cells": cells,
        "broad_relationships": broad,
        "scorecard": scorecard,
        "topology": g1.topology_diagnostics(cells),
        "primary": {
            "joint_q90_brier": _weighted_score(scorecard, "joint_q90_brier"),
            "variogram_p0_5": _weighted_score(scorecard, "variogram_p0_5"),
            "g0_absolute_log_error_sum": g0_abs,
            "g0_cell_errors": g0_cells,
            "g1_weighted_absolute_log_error_sum": g1_abs,
            "g1_relationship_errors": g1_cells,
        },
    }


def paired_primary_bootstrap(
    frame: pd.DataFrame,
    control_draws: np.ndarray,
    treatment_draws: np.ndarray,
    games: pd.DataFrame,
) -> dict:
    """Paired whole-slate intervals for the two primary proper scores."""
    mask = (
        frame.position.isin(g1.POSITIONS)
        & frame.mean_projection.ge(g0.MIN_MEAN)
    ).to_numpy(bool)
    supported = frame.loc[mask].reset_index(drop=True)
    supported, _ = g1.attach_walk_forward_archetypes(supported, games)
    control = np.asarray(control_draws)[mask]
    treatment = np.asarray(treatment_draws)[mask]
    if control.shape != treatment.shape or not np.isfinite(
            control).all() or not np.isfinite(treatment).all():
        raise ValueError("G2 bootstrap arms are invalid or misaligned")
    pairs = g1.build_pair_book(supported)
    thresholds = np.quantile(control, 0.90, axis=1)
    actual = supported.actual.to_numpy(float)
    slates = sorted({
        (int(row.season), int(row.week)) for row in supported.itertuples()
    })
    slate_index = {value: index for index, value in enumerate(slates)}
    relationship_index = {
        relationship: index for index, relationship in
        enumerate(PRIMARY_WEIGHTS)
    }
    shape = (len(slates), len(PRIMARY_WEIGHTS))
    counts = np.zeros(shape, dtype=float)
    sums = {
        "control_joint_q90_brier": np.zeros(shape, dtype=float),
        "treatment_joint_q90_brier": np.zeros(shape, dtype=float),
        "control_variogram_p0_5": np.zeros(shape, dtype=float),
        "treatment_variogram_p0_5": np.zeros(shape, dtype=float),
    }
    for relationship, group in pairs[
            pairs.relationship.isin(PRIMARY_WEIGHTS)
    ].groupby("relationship", sort=True):
        left = group.source_index.to_numpy(int)
        right = group.target_index.to_numpy(int)
        observed = np.abs(actual[left] - actual[right]) ** 0.5
        outcome = (
            (actual[left] > thresholds[left])
            & (actual[right] > thresholds[right])
        ).astype(float)
        values = {
            "control_joint_q90_brier": np.empty(len(group), dtype=float),
            "treatment_joint_q90_brier": np.empty(len(group), dtype=float),
            "control_variogram_p0_5": np.empty(len(group), dtype=float),
            "treatment_variogram_p0_5": np.empty(len(group), dtype=float),
        }
        for start in range(0, len(group), 256):
            stop = min(start + 256, len(group))
            for arm, draws in (("control", control), ("treatment", treatment)):
                simulated_left = draws[left[start:stop]]
                simulated_right = draws[right[start:stop]]
                probability = np.mean(
                    (simulated_left > thresholds[left[start:stop], None])
                    & (simulated_right > thresholds[right[start:stop], None]),
                    axis=1,
                )
                expectation = np.mean(
                    np.abs(simulated_left - simulated_right) ** 0.5, axis=1)
                values[f"{arm}_joint_q90_brier"][start:stop] = np.square(
                    outcome[start:stop] - probability)
                values[f"{arm}_variogram_p0_5"][start:stop] = np.square(
                    observed[start:stop] - expectation)
        values_frame = group[["season", "week"]].reset_index(drop=True).copy()
        for key, value in values.items():
            values_frame[key] = value
        aggregate = values_frame.groupby(["season", "week"], sort=True).agg(
            count=("season", "size"),
            **{key: (key, "sum") for key in values},
        )
        relationship_offset = relationship_index[relationship]
        for (season, week), row in aggregate.iterrows():
            slate_offset = slate_index[(int(season), int(week))]
            counts[slate_offset, relationship_offset] = float(row["count"])
            for key in sums:
                sums[key][slate_offset, relationship_offset] = float(row[key])
    if (counts.sum(axis=0) == 0).any():
        raise ValueError("G2 bootstrap primary relationship support is incomplete")

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    bootstrap_weights = rng.multinomial(
        len(slates), np.full(len(slates), 1.0 / len(slates)),
        size=N_BOOTSTRAPS,
    )
    denominator = bootstrap_weights @ counts
    if (denominator <= 0).any():
        raise ValueError("G2 bootstrap resample lost relationship support")
    normalized_weights = np.array(
        [PRIMARY_WEIGHTS[key] for key in PRIMARY_WEIGHTS], dtype=float)
    normalized_weights /= normalized_weights.sum()
    samples = {}
    points = {}
    total_counts = counts.sum(axis=0)
    for key, value in sums.items():
        samples[key] = (
            (bootstrap_weights @ value) / denominator
        ) @ normalized_weights
        points[key] = float((value.sum(axis=0) / total_counts) @ normalized_weights)
    report = {}
    for metric in ("joint_q90_brier", "variogram_p0_5"):
        control_key = f"control_{metric}"
        treatment_key = f"treatment_{metric}"
        delta = samples[treatment_key] - samples[control_key]
        low, high = np.quantile(delta, [0.025, 0.975]).tolist()
        report[metric] = {
            "control": points[control_key],
            "treatment": points[treatment_key],
            "treatment_minus_control": (
                points[treatment_key] - points[control_key]),
            "paired_slate_bootstrap_ci95_low": float(low),
            "paired_slate_bootstrap_ci95_high": float(high),
            "interval_crosses_zero": bool(low <= 0 <= high),
        }
    return {
        "replicates": N_BOOTSTRAPS,
        "seed": BOOTSTRAP_SEED,
        "cluster": "season-week-slate",
        "slates": len(slates),
        "metrics": report,
    }


def validate_control_reproduction(
    observed: dict,
    g0_reference: dict,
    g1_reference: dict,
) -> list[str]:
    failures = []
    for key in ("rows", "slates", "pairs"):
        if observed["population"].get(key) != g1_reference["population"].get(key):
            failures.append(f"g1-population:{key}")
    if observed["population"].get("relationship_counts") != \
            g1_reference["population"].get("relationship_counts"):
        failures.append("g1-population:relationship-counts")
    for key in ("rows", "slates", "n_sims"):
        if observed["g0"]["population"].get(key) != \
                g0_reference["population"].get(key):
            failures.append(f"g0-population:{key}")
    for cell in g0.CELL_BANDS:
        for metric in ("realized_estimate", "simulated_estimate"):
            left = observed["g0"]["cells"][cell].get(metric)
            right = g0_reference["cells"][cell].get(metric)
            if left is None or right is None or not np.isclose(
                    left, right, rtol=0, atol=FLOAT_TOLERANCE):
                failures.append(f"g0:{cell}:{metric}")
    for relationship in g1.ALL_RELATIONSHIPS:
        for metric in ("realized_lift", "simulated_lift"):
            left = observed["broad_relationships"][relationship].get(metric)
            right = g1_reference["broad_relationships"][relationship].get(metric)
            if left is None or right is None or not np.isclose(
                    left, right, rtol=0, atol=FLOAT_TOLERANCE):
                failures.append(f"g1:{relationship}:{metric}")
        for metric in ("joint_q90_brier", "variogram_p0_5"):
            left = observed["scorecard"][relationship].get(metric)
            right = g1_reference["scorecard"][relationship].get(metric)
            if left is None or right is None or not np.isclose(
                    left, right, rtol=0, atol=FLOAT_TOLERANCE):
                failures.append(f"g1-score:{relationship}:{metric}")
    if observed["archetypes"] != g1_reference["archetypes"]:
        failures.append("g1:archetype-audit")
    return failures


def gate_decision(
    control: dict,
    treatment: dict,
    *,
    invariants_pass: bool,
    selected: dict,
    treatment_audit: dict,
) -> dict:
    control_primary = control["primary"]
    treatment_primary = treatment["primary"]
    selected_active = (
        float(selected["theta_wr"]) > 1.0
        or float(selected["theta_te"]) > 1.0
    )
    gates = {
        "terminal_and_exact_marginal_invariants_pass": bool(invariants_pass),
        "selected_theta_is_active": bool(selected_active),
        "eligible_receiver_ranks_change": (
            int(treatment_audit.get("changed_rank_rows", 0)) > 0),
        "primary_joint_q90_brier_improves": (
            treatment_primary["joint_q90_brier"]
            < control_primary["joint_q90_brier"]),
        "primary_variogram_improves": (
            treatment_primary["variogram_p0_5"]
            < control_primary["variogram_p0_5"]),
        "g0_absolute_log_error_improves": (
            treatment_primary["g0_absolute_log_error_sum"]
            < control_primary["g0_absolute_log_error_sum"]),
        "g1_weighted_absolute_log_error_improves": (
            treatment_primary["g1_weighted_absolute_log_error_sum"]
            < control_primary["g1_weighted_absolute_log_error_sum"]),
        "qb_wr_absolute_log_error_improves": (
            treatment_primary["g1_relationship_errors"]["QB_WR"]
            ["absolute_log_error"]
            < control_primary["g1_relationship_errors"]["QB_WR"]
            ["absolute_log_error"]),
        "qb_te_absolute_log_error_improves": (
            treatment_primary["g1_relationship_errors"]["QB_TE"]
            ["absolute_log_error"]
            < control_primary["g1_relationship_errors"]["QB_TE"]
            ["absolute_log_error"]),
    }
    if not invariants_pass:
        disposition = "g2-invalid-or-inconclusive"
    elif all(gates.values()):
        disposition = "g2-dependence-gate-passes"
    else:
        disposition = "g2-dependence-gate-fails"
    return {
        "disposition": disposition,
        "exact80_licensed": disposition == "g2-dependence-gate-passes",
        "gate": {**gates, "passes": all(gates.values())},
    }


@contextmanager
def _historical_environment():
    from . import served_tail_calibration as served

    with served._production_environment():
        with g0._selected_cache(HISTORICAL_CACHE):
            yield


def _align_historical_season(
    projected: pd.DataFrame,
    draws: np.ndarray,
    accepted: pd.DataFrame,
    cache_keys: pd.DataFrame,
    season: int,
) -> tuple[pd.DataFrame, np.ndarray, dict]:
    from . import served_tail_calibration as served

    keys = ["season", "week", "gsis_id", "position"]
    source = projected.copy()
    source["_draw_index"] = np.arange(len(source), dtype=int)
    source["tabpfn_covered"] = source.merge(
        cache_keys.assign(tabpfn_covered=True),
        on=["season", "week", "gsis_id"], how="left", sort=False,
        validate="many_to_one",
    ).tabpfn_covered.fillna(False).to_numpy(bool)
    source["market_covered"] = source.market_points.notna()
    expected = accepted[accepted.season.eq(season)].rename(columns={
        "pos": "position",
        "team": "accepted_team",
        "opp": "accepted_opp",
        "game_id": "accepted_game_id",
        "actual": "accepted_actual",
        "model_points_pre": "accepted_model_points_pre",
        "mean_projection": "accepted_mean_projection",
    })
    joined = expected.merge(
        source, on=keys, how="left", validate="one_to_one", indicator=True)
    if not joined._merge.eq("both").all():
        raise ValueError(f"G2 historical {season} keys do not align")
    joined = joined[
        joined.was_active.fillna(False).astype(bool)
        & joined.position.isin(g1.POSITIONS)
    ].reset_index(drop=True)
    if joined.empty or joined[["season", "week", "gsis_id"]].duplicated().any():
        raise ValueError(f"G2 historical {season} supported rows differ")
    actual_delta = np.abs(
        joined.accepted_actual.to_numpy(float) - joined.actual.to_numpy(float))
    pre_delta = np.abs(
        joined.accepted_model_points_pre.to_numpy(float)
        - joined.model_points_pre.to_numpy(float))
    final_delta = np.abs(
        joined.accepted_mean_projection.to_numpy(float)
        - joined.proj_points.to_numpy(float))
    if actual_delta.max(initial=0.0) > served.ACTUAL_TOLERANCE:
        raise ValueError(f"G2 historical {season} actuals disagree")
    if pre_delta.max(initial=0.0) > served.MEAN_TOLERANCE:
        raise ValueError(f"G2 historical {season} post-shaper means disagree")
    if final_delta.max(initial=0.0) > served.MEAN_TOLERANCE:
        raise ValueError(f"G2 historical {season} post-blend means disagree")
    if not joined.tabpfn_covered.all():
        raise ValueError(f"G2 historical {season} cache coverage differs")
    for accepted_name, source_name in (
            ("accepted_team", "team"), ("accepted_opp", "opp"),
            ("accepted_game_id", "game_id")):
        if source_name in joined and not joined[accepted_name].astype(str).eq(
                joined[source_name].astype(str)).all():
            raise ValueError(
                f"G2 historical {season} {source_name} metadata differs")
    frame = joined[[
        "season", "week", "gsis_id", "position", "accepted_team",
        "accepted_opp", "accepted_game_id", "accepted_actual",
        "market_covered", "tabpfn_covered",
    ]].rename(columns={
        "accepted_team": "team", "accepted_opp": "opp",
        "accepted_game_id": "game_id", "accepted_actual": "actual",
    })
    indices = joined._draw_index.to_numpy(int)
    aligned = np.asarray(draws)[indices]
    frame["mean_projection"] = aligned.mean(axis=1)
    return frame, aligned, {
        "season": int(season),
        "rows": int(len(frame)),
        "slates": int(frame[["season", "week"]].drop_duplicates().shape[0]),
        "tabpfn_coverage": float(frame.tabpfn_covered.mean()),
        "market_coverage": float(frame.market_covered.mean()),
        "max_actual_abs_delta": float(actual_delta.max(initial=0.0)),
        "max_post_shaper_mean_abs_delta": float(pre_delta.max(initial=0.0)),
        "max_post_blend_mean_abs_delta": float(final_delta.max(initial=0.0)),
    }


def _load_historical_book(panel_id: str) -> tuple[pd.DataFrame, np.ndarray, dict]:
    from ..backtest.replay import (
        _market_blend_worlds, load_panel_and_dst, replay_projections)
    from ..bq import query_df
    from ..config import settings
    from ..models.blend import effective_model_weight
    from ..models.prop_market import market_points

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
            "seasons": list(CALIBRATION_SEASONS),
            "positions": list(g1.POSITIONS),
        })
    if accepted.empty or accepted.duplicated(
            ["season", "week", "gsis_id"]).any():
        raise ValueError("G2 historical accepted snapshot is missing or duplicated")
    cache_keys = query_df(f"""
        SELECT season, week, gsis_id
        FROM `{settings.features}.{HISTORICAL_CACHE}`
        WHERE season IN UNNEST(@seasons)
        ORDER BY season, week, gsis_id
        """, params={"seasons": list(CALIBRATION_SEASONS)})
    if cache_keys.empty or cache_keys.duplicated(
            ["season", "week", "gsis_id"]).any():
        raise ValueError("G2 historical cache keys differ")

    frames, draw_parts, parity = [], [], []
    with _historical_environment():
        weight = effective_model_weight()
        if not np.isclose(weight, 0.45, rtol=0, atol=0):
            raise ValueError("G2 historical blend weight differs")
        for season in CALIBRATION_SEASONS:
            panel, _ = load_panel_and_dst(season)
            market = market_points((season,)).drop_duplicates(
                ["season", "week", "gsis_id"])
            projected, draws = replay_projections(
                panel, season, n_sims=10_000, seed=0, return_draws=True)
            projected, draws, _ = _market_blend_worlds(
                projected, draws, market, weight)
            frame, aligned, audit = _align_historical_season(
                projected, draws, accepted,
                cache_keys[cache_keys.season.eq(season)], season)
            frames.append(frame)
            draw_parts.append(aligned)
            parity.append(audit)
    return pd.concat(frames, ignore_index=True), np.concatenate(draw_parts), {
        "panel": panel_id,
        "cache_table": HISTORICAL_CACHE,
        "cache_rows": int(len(cache_keys)),
        "parity": parity,
    }


def _load_games() -> pd.DataFrame:
    from ..bq import query_df
    from ..config import settings

    return query_df(f"""
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


def _calibration_pair_book(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    supported = frame[
        frame.position.isin(g1.POSITIONS)
        & frame.mean_projection.ge(g0.MIN_MEAN)
    ].reset_index(drop=True)
    supported["archetype"] = supported.position.astype(str) + "-calibration"
    pairs = g1.build_pair_book(supported)
    pairs = pairs[pairs.relationship.isin(TARGET_RELATIONSHIPS)].reset_index(drop=True)
    return supported, pairs


def run(panel_id: str) -> dict:
    """Run the sole frozen G2 calibration and held-out dependence gate."""
    expected_panel = os.environ.get("G2_PANEL_ID", "").strip()
    historical_panel = os.environ.get("G2_HISTORICAL_PANEL_ID", "").strip()
    selected_eval_panel = os.environ.get("G2_SELECTED_EVAL_PANEL_ID", "").strip()
    if not expected_panel or panel_id != expected_panel:
        raise ValueError("G2 panel differs from terminal selection")
    if not historical_panel or not selected_eval_panel:
        raise ValueError("G2 selected panel identity is incomplete")
    root = Path(os.environ.get("G2_REFERENCE_ROOT", "/app/reports"))
    g0_path = root / "g0-dependence-runs/20260812-g0-final-served-dependence-v2/report.json"
    g1_path = root / "g1-topology-runs/20260812-g1-archetype-topology-v3/report.json"
    g0_reference = _require_reference_hash(
        g0_path, "G2_G0_REPORT_SHA256")
    g1_reference = _require_reference_hash(
        g1_path, "G2_G1_REPORT_SHA256")
    if g1_reference.get("disposition") != "stable-qb-hub-confirmed" or \
            not g1_reference.get("g2_licensed") or \
            not g1_reference.get("invariants", {}).get("passes"):
        raise ValueError("G2 lacks a valid G1 license")

    historical_frame, historical_draws, historical_audit = \
        _load_historical_book(historical_panel)
    calibration_frame, calibration_pairs = _calibration_pair_book(
        historical_frame)
    historical_mask = (
        historical_frame.position.isin(g1.POSITIONS)
        & historical_frame.mean_projection.ge(g0.MIN_MEAN)
    ).to_numpy(bool)
    calibration_draws = historical_draws[historical_mask]
    selected, grid, fit_audit = fit_theta_grid(
        calibration_frame, calibration_draws, calibration_pairs)
    calibration_artifact = {
        "version": "v1",
        "historical_panel": historical_panel,
        "historical": historical_audit,
        "fit": {
            "calibration_seasons": list(CALIBRATION_SEASONS),
            "theta_grid": list(THETA_GRID),
            "selected": selected,
            "grid": grid,
            **fit_audit,
        },
    }
    expected_calibration_sha = os.environ.get(
        "G2_CALIBRATION_JSON_SHA256", "").strip()
    if expected_calibration_sha:
        content = json.dumps(
            calibration_artifact, sort_keys=True, allow_nan=False,
            separators=(",", ":"),
        ).encode()
        if sha256(content).hexdigest() != expected_calibration_sha:
            raise ValueError("G2 calibration artifact differs from frozen v2")
    # The frozen protocol requires all grid scores to be durable before any
    # held-out reconstruction or outcome evaluation begins.
    _emit_transport(
        calibration_artifact,
        CALIBRATION_META_PREFIX,
        CALIBRATION_CHUNK_PREFIX,
    )
    del (
        historical_frame, historical_draws, calibration_frame,
        calibration_draws, calibration_pairs,
    )
    gc.collect()

    heldout_frame, heldout_draws, terminal = g1._load_terminal_book(panel_id)
    games = _load_games()
    control = score_heldout(heldout_frame, heldout_draws, games)
    reproduction_failures = validate_control_reproduction(
        control, g0_reference, g1_reference)
    treatment_draws, treatment_audit = apply_qb_gumbel_factor(
        heldout_draws, heldout_frame,
        theta_wr=float(selected["theta_wr"]),
        theta_te=float(selected["theta_te"]),
    )
    sorted_equal = bool(all(
        np.array_equal(np.sort(before), np.sort(after))
        for before, after in zip(heldout_draws, treatment_draws)
    ))
    unchanged_mask = ~heldout_frame.position.isin(["WR", "TE"]).to_numpy(bool)
    unchanged_non_receivers = bool(np.array_equal(
        heldout_draws[unchanged_mask], treatment_draws[unchanged_mask]))
    deterministic, repeated_audit = apply_qb_gumbel_factor(
        heldout_draws, heldout_frame,
        theta_wr=float(selected["theta_wr"]),
        theta_te=float(selected["theta_te"]),
    )
    invariants = {
        "control_reproduction_failures": reproduction_failures,
        "historical_parity_passes": all(
            value["tabpfn_coverage"] == 1.0
            and value["max_post_shaper_mean_abs_delta"] <= 1e-4
            and value["max_post_blend_mean_abs_delta"] <= 1e-4
            for value in historical_audit["parity"]),
        "exact_sorted_draw_multisets": sorted_equal,
        "non_receivers_unchanged": unchanged_non_receivers,
        "deterministic_output": bool(
            np.array_equal(treatment_draws, deterministic)
            and treatment_audit == repeated_audit),
        "finite_output": bool(np.isfinite(treatment_draws).all()),
        "maximum_mean_delta": float(treatment_audit["maximum_mean_delta"]),
        "passes": False,
    }
    del deterministic, repeated_audit
    gc.collect()
    invariants["passes"] = bool(
        not reproduction_failures
        and invariants["historical_parity_passes"]
        and invariants["exact_sorted_draw_multisets"]
        and invariants["non_receivers_unchanged"]
        and invariants["deterministic_output"]
        and invariants["finite_output"]
        and invariants["maximum_mean_delta"] <= 1e-10
    )
    treatment = score_heldout(heldout_frame, treatment_draws, games)
    bootstrap = paired_primary_bootstrap(
        heldout_frame, heldout_draws, treatment_draws, games)
    decision = gate_decision(
        control, treatment,
        invariants_pass=invariants["passes"],
        selected=selected,
        treatment_audit=treatment_audit,
    )
    report = {
        "version": "v1",
        "panel": panel_id,
        "historical_panel": historical_panel,
        "selected_eval_panel": selected_eval_panel,
        "terminal": terminal,
        "historical": historical_audit,
        "fit": {
            "calibration_seasons": list(CALIBRATION_SEASONS),
            "theta_grid": list(THETA_GRID),
            "selected": selected,
            "grid": grid,
            **fit_audit,
        },
        "treatment_audit": treatment_audit,
        "invariants": invariants,
        "control": control,
        "treatment": treatment,
        "bootstrap": bootstrap,
        **decision,
    }
    _emit_transport(report, OUTPUT_META_PREFIX, OUTPUT_CHUNK_PREFIX)
    return report


__all__ = [
    "CALIBRATION_SEASONS", "EVALUATION_SEASONS", "PRIMARY_WEIGHTS",
    "THETA_GRID", "fit_theta_grid", "gate_decision", "run",
    "paired_primary_bootstrap", "score_heldout",
    "select_grid_cell", "validate_control_reproduction",
]
