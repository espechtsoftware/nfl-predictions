"""G0 final-served teammate dependence diagnostic.

The scientific contract is frozen in
``reports/2026-08-12-g0-final-served-dependence-protocol.md``.  This module is
deliberately lineup-free: it compares realized q90 exceedances with the joint
distribution already emitted by the selected simulator.
"""

from __future__ import annotations

import base64
from collections import defaultdict
from contextlib import contextmanager
import json
from math import comb, log
import os

import numpy as np
import pandas as pd


N_BOOTSTRAPS = 2_000
BOOTSTRAP_SEED = 1_701
MIN_MEAN = 4.0
MIN_TEAM_WEEKS = 500
MIN_PAIR_TEAM_WEEKS = 500
MIN_CONDITIONING_BOOMS = 30

CELL_BANDS = {
    "multiplicity_ge2": log(1.10),
    "multiplicity_ge3": log(1.15),
    "multiplicity_ge4": log(1.25),
    "qb_wr": log(1.15),
    "qb_te": log(1.15),
    "qb_rb": log(1.15),
    "wr_wr": log(1.15),
    "rb_rb": log(1.15),
    "te_te": log(1.15),
}
MULTIPLICITY = {2: "multiplicity_ge2", 3: "multiplicity_ge3", 4: "multiplicity_ge4"}
QB_CELLS = {"WR": "qb_wr", "TE": "qb_te", "RB": "qb_rb"}
SAME_POSITION_CELLS = {"WR": "wr_wr", "RB": "rb_rb", "TE": "te_te"}
OUTPUT_PREFIX = "G0_FINAL_SERVED_DEPENDENCE_JSON="
LICENSED_CACHES = {
    "tabpfn_projections_pit_v2",
    "tabpfn_active_label_treatment_v2",
    "tabpfn_sched_treatment_v1",
    "tabpfn_team_qb_treatment_v1",
}


def poisson_binomial_tail(probabilities: np.ndarray, threshold: int) -> float:
    """Exact P(sum Bernoulli(p_i) >= threshold) via stable recursion."""
    p = np.asarray(probabilities, dtype=float)
    if p.ndim != 1 or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Poisson-binomial probabilities must be finite in [0, 1]")
    if threshold <= 0:
        return 1.0
    if threshold > len(p):
        return 0.0
    pmf = np.zeros(len(p) + 1, dtype=float)
    pmf[0] = 1.0
    used = 0
    for value in p:
        pmf[1:used + 2] = (
            pmf[1:used + 2] * (1.0 - value)
            + pmf[:used + 1] * value
        )
        pmf[0] *= 1.0 - value
        used += 1
    return float(pmf[threshold:].sum())


def binomial_tail(n: int, probability: float, threshold: int) -> float:
    """Pooled-binomial comparison retained only as a labeled diagnostic."""
    if n < 0 or not np.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("invalid binomial arguments")
    return float(sum(
        comb(n, k) * probability ** k * (1.0 - probability) ** (n - k)
        for k in range(max(0, threshold), n + 1)
    ))


def _empty_contribution(kind: str) -> dict[str, float]:
    if kind == "multiplicity":
        return {
            "groups": 0.0, "real_events": 0.0, "sim_events": 0.0,
            "poisson_expected": 0.0, "pooled_expected": 0.0,
        }
    return {
        "pairs": 0.0,
        "real_a1b1": 0.0, "real_a1": 0.0,
        "real_a0b1": 0.0, "real_a0": 0.0,
        "sim_a1b1": 0.0, "sim_a1": 0.0,
        "sim_a0b1": 0.0, "sim_a0": 0.0,
    }


def _add(target: dict[str, float], values: dict[str, float]) -> None:
    for key, value in values.items():
        target[key] += float(value)


def _conditional_contribution(
    actual: np.ndarray,
    simulated: np.ndarray,
    first: int,
    second: int,
) -> dict[str, float]:
    a = bool(actual[first])
    b = bool(actual[second])
    sim_a = simulated[first]
    sim_b = simulated[second]
    return {
        "pairs": 1.0,
        "real_a1b1": float(a and b),
        "real_a1": float(a),
        "real_a0b1": float((not a) and b),
        "real_a0": float(not a),
        "sim_a1b1": float(np.count_nonzero(sim_a & sim_b)),
        "sim_a1": float(np.count_nonzero(sim_a)),
        "sim_a0b1": float(np.count_nonzero((~sim_a) & sim_b)),
        "sim_a0": float(np.count_nonzero(~sim_a)),
    }


def _conditional_lift(values: np.ndarray, offset: int) -> np.ndarray:
    """Vectorized lift from aggregated contribution columns."""
    both, conditioned, other_only, not_conditioned = (
        values[:, offset], values[:, offset + 1],
        values[:, offset + 2], values[:, offset + 3],
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        return (both / conditioned) / (other_only / not_conditioned)


def _classify(
    point: float,
    ci_low: float,
    ci_high: float,
    band: float,
    supported: bool,
) -> str:
    if not supported or not np.isfinite([point, ci_low, ci_high]).all():
        return "unsupported"
    if ci_low >= -band and ci_high <= band:
        return "equivalent"
    if abs(point) > band and (ci_low > 0 or ci_high < 0):
        return "material-miss"
    return "inconclusive"


def _finite_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    return numeric if np.isfinite(numeric) else None


def _point_estimates(kind: str, totals: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if kind == "multiplicity":
        with np.errstate(divide="ignore", invalid="ignore"):
            return totals[:, 1] / totals[:, 3], totals[:, 2] / totals[:, 3]
    return _conditional_lift(totals, 1), _conditional_lift(totals, 5)


def evaluate_dependence(
    frame: pd.DataFrame,
    draws: np.ndarray,
    *,
    n_bootstraps: int = N_BOOTSTRAPS,
    bootstrap_seed: int = BOOTSTRAP_SEED,
) -> dict:
    """Evaluate the nine frozen G0 cells on one terminal served book.

    ``frame`` and ``draws`` must already be exact selected final-served rows
    after the market blend and target-season position scales.  Required frame
    columns are season/week/gsis_id/team/position/actual/mean_projection.
    """
    required = {
        "season", "week", "gsis_id", "team", "position", "actual",
        "mean_projection",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"G0 frame missing columns: {sorted(missing)}")
    values = np.asarray(draws, dtype=float)
    if values.ndim != 2 or values.shape[0] != len(frame) or values.shape[1] < 100:
        raise ValueError("G0 draws must be rows x at least 100 worlds")
    if not np.isfinite(values).all():
        raise ValueError("G0 draws contain non-finite values")
    source = frame.reset_index(drop=True).copy()
    if source.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("G0 frame contains duplicate player-week keys")
    source["position"] = source.position.astype(str).str.upper()
    source["team"] = source.team.astype(str).str.upper()
    source["_draw_index"] = np.arange(len(source))
    source = source[
        source.position.isin({"QB", "RB", "WR", "TE"})
        & source.mean_projection.ge(MIN_MEAN)
    ].reset_index(drop=True)
    if source.empty:
        raise ValueError("G0 support population is empty")
    values = values[source._draw_index.to_numpy(int)]
    thresholds = np.quantile(values, 0.90, axis=1)
    actual = source.actual.to_numpy(float) > thresholds
    simulated = values > thresholds[:, None]
    probabilities = simulated.mean(axis=1)
    pooled_probability = float(probabilities.mean())
    n_sims = values.shape[1]

    cell_kind = {
        **{cell: "multiplicity" for cell in MULTIPLICITY.values()},
        **{cell: "conditional" for cell in QB_CELLS.values()},
        **{cell: "conditional" for cell in SAME_POSITION_CELLS.values()},
    }
    contributions: dict[str, dict[tuple[int, int], dict[str, float]]] = {
        cell: defaultdict(lambda kind=kind: _empty_contribution(kind))
        for cell, kind in cell_kind.items()
    }

    for (season, week, _team), group in source.groupby(
        ["season", "week", "team"], sort=True
    ):
        indices = group.index.to_numpy(int)
        cluster = (int(season), int(week))
        if len(indices) >= 3:
            count_actual = int(actual[indices].sum())
            count_simulated = simulated[indices].sum(axis=0)
            for threshold, cell in MULTIPLICITY.items():
                _add(contributions[cell][cluster], {
                    "groups": 1.0,
                    "real_events": float(count_actual >= threshold),
                    "sim_events": float(np.mean(count_simulated >= threshold)),
                    "poisson_expected": poisson_binomial_tail(
                        probabilities[indices], threshold),
                    "pooled_expected": binomial_tail(
                        len(indices), pooled_probability, threshold),
                })

        qbs = group[group.position.eq("QB")].index.to_list()
        if len(qbs) == 1:
            qb = qbs[0]
            for position, cell in QB_CELLS.items():
                for teammate in group[group.position.eq(position)].index:
                    _add(contributions[cell][cluster], _conditional_contribution(
                        actual, simulated, qb, int(teammate)))

        for position, cell in SAME_POSITION_CELLS.items():
            teammates = [int(index) for index in group[
                group.position.eq(position)].index]
            for left_index, left in enumerate(teammates):
                for right in teammates[left_index + 1:]:
                    _add(contributions[cell][cluster], _conditional_contribution(
                        actual, simulated, left, right))
                    _add(contributions[cell][cluster], _conditional_contribution(
                        actual, simulated, right, left))

    clusters = sorted({
        cluster for by_cluster in contributions.values() for cluster in by_cluster
    })
    if not clusters:
        raise ValueError("G0 produced no slate clusters")
    cluster_index = {cluster: index for index, cluster in enumerate(clusters)}
    rng = np.random.default_rng(bootstrap_seed)
    bootstrap_weights = rng.multinomial(
        len(clusters), np.full(len(clusters), 1.0 / len(clusters)),
        size=n_bootstraps,
    ).astype(float)

    results = {}
    for cell in CELL_BANDS:
        kind = cell_kind[cell]
        fields = list(_empty_contribution(kind))
        matrix = np.zeros((len(clusters), len(fields)), dtype=float)
        for cluster, row in contributions[cell].items():
            matrix[cluster_index[cluster]] = [row[field] for field in fields]
        totals = matrix.sum(axis=0, keepdims=True)
        actual_estimate, simulated_estimate = _point_estimates(kind, totals)
        with np.errstate(divide="ignore", invalid="ignore"):
            point = float(np.log(simulated_estimate[0] / actual_estimate[0]))
        boot_totals = bootstrap_weights @ matrix
        boot_actual, boot_simulated = _point_estimates(kind, boot_totals)
        with np.errstate(divide="ignore", invalid="ignore"):
            boot_gap = np.log(boot_simulated / boot_actual)
        finite = boot_gap[np.isfinite(boot_gap)]
        if len(finite) < 0.95 * n_bootstraps:
            ci_low = ci_high = float("nan")
        else:
            ci_low, ci_high = np.quantile(finite, [0.025, 0.975]).tolist()

        total = dict(zip(fields, totals[0].tolist()))
        if kind == "multiplicity":
            threshold = int(cell[-1])
            supported = (
                total["groups"] >= MIN_TEAM_WEEKS
                and (threshold != 4 or (
                    total["real_events"] >= 8
                    and total["poisson_expected"] >= 5
                ))
            )
            support = {
                "team_weeks": int(total["groups"]),
                "realized_events": int(total["real_events"]),
                "poisson_binomial_expected_events": total["poisson_expected"],
            }
            pooled = total["real_events"] / total["pooled_expected"]
        else:
            supported = (
                total["pairs"] >= MIN_PAIR_TEAM_WEEKS
                and total["real_a1"] >= MIN_CONDITIONING_BOOMS
                and min(total["real_a1"], total["real_a0"],
                        total["sim_a1"], total["sim_a0"]) > 0
                and total["real_a1b1"] > 0 and total["real_a0b1"] > 0
                and total["sim_a1b1"] > 0 and total["sim_a0b1"] > 0
            )
            support = {
                "directed_pair_team_weeks": int(total["pairs"]),
                "realized_conditioning_booms": int(total["real_a1"]),
            }
            pooled = None
        classification = _classify(
            point, float(ci_low), float(ci_high), CELL_BANDS[cell], supported)
        point_out = _finite_or_none(point)
        ci_low_out = _finite_or_none(ci_low)
        ci_high_out = _finite_or_none(ci_high)
        results[cell] = {
            "kind": kind,
            "realized_estimate": _finite_or_none(actual_estimate[0]),
            "simulated_estimate": _finite_or_none(simulated_estimate[0]),
            "log_simulated_to_realized": point_out,
            "cluster_ci95_low": ci_low_out,
            "cluster_ci95_high": ci_high_out,
            "equivalence_band_abs_log": CELL_BANDS[cell],
            "supported": bool(supported),
            "classification": classification,
            "support": support,
            "pooled_binomial_realized_ratio": _finite_or_none(pooled),
        }

    classes = [row["classification"] for row in results.values()]
    if "material-miss" in classes:
        disposition = "dependence-premise-miss"
    elif all(value == "equivalent" for value in classes):
        disposition = "dependence-premise-reproduced"
    else:
        disposition = "dependence-premise-inconclusive"
    def predicted(cell: str, direction: int) -> bool:
        value = results[cell]["log_simulated_to_realized"]
        return bool(value is not None and direction * value > 0)

    return {
        "disposition": disposition,
        "g1_licensed": disposition == "dependence-premise-miss",
        "population": {
            "rows": int(len(source)),
            "slates": int(source[["season", "week"]].drop_duplicates().shape[0]),
            "mean_projection_minimum": MIN_MEAN,
            "n_sims": int(n_sims),
            "pooled_simulated_exceedance_probability": pooled_probability,
        },
        "bootstrap": {
            "clusters": int(len(clusters)),
            "replicates": int(n_bootstraps),
            "seed": int(bootstrap_seed),
        },
        "cells": results,
        "directional_predictions": {
            "simulated_wr_wr_above_realized": predicted("wr_wr", 1),
            "simulated_qb_wr_below_realized": predicted("qb_wr", -1),
            "simulated_ge4_below_realized": predicted("multiplicity_ge4", -1),
        },
    }


def _selected_schedule(env: dict[str, str] | None = None) -> dict[int, dict]:
    values = os.environ if env is None else env
    encoded = str(values.get("G0_POSITION_SCHEDULE_B64", "")).strip()
    if not encoded:
        raise ValueError("G0 selected position schedule is missing")
    try:
        # Cloud Run/gcloud removes terminal ``=`` padding from values passed
        # through --set-env-vars. Restore only the deterministic base64
        # padding; validation still rejects any non-alphabet bytes.
        padded = encoded + "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(padded, validate=True).decode("utf-8")
        raw = json.loads(decoded)
    except Exception as exc:
        raise ValueError("G0 selected position schedule is invalid") from exc
    expected_seasons = {2023, 2024, 2025}
    if {int(key) for key in raw} != expected_seasons:
        raise ValueError("G0 position schedule has the wrong seasons")
    schedule = {int(key): value for key, value in raw.items()}
    for season, value in schedule.items():
        factors = value.get("factors", {})
        if set(factors) != {"QB", "RB", "WR", "TE"}:
            raise ValueError(f"G0 {season} position factors are incomplete")
        numeric = np.array([factors[key] for key in ("QB", "RB", "WR", "TE")],
                           dtype=float)
        if not np.isfinite(numeric).all() or ((numeric < 0.75) | (numeric > 1.5)).any():
            raise ValueError(f"G0 {season} position factors are invalid")
    return schedule


@contextmanager
def _selected_cache(table: str):
    if table not in LICENSED_CACHES:
        raise ValueError(f"G0 unlicensed selected cache {table!r}")
    prior = os.environ.get("TABPFN_MARGINAL_TABLE")
    os.environ["TABPFN_MARGINAL_TABLE"] = table
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop("TABPFN_MARGINAL_TABLE", None)
        else:
            os.environ["TABPFN_MARGINAL_TABLE"] = prior


def run(panel_id: str) -> dict:
    """Recreate the terminal served draws and emit the sole frozen G0 report."""
    expected_panel = os.environ.get("G0_PANEL_ID", "").strip()
    table = os.environ.get("G0_CACHE_TABLE", "").strip()
    if not expected_panel or panel_id != expected_panel:
        raise ValueError("G0 panel differs from the terminal selection")
    if table not in LICENSED_CACHES:
        raise ValueError("G0 cache differs from the terminal selection")
    schedule = _selected_schedule()

    from . import route_final_served_calibration as calibration
    from . import served_position_calibration as position_calibration
    from . import served_tail_calibration as served
    from . import tabpfn_sched_final_served as inherited
    from ..backtest.replay import (
        _market_blend_worlds,
        load_panel_and_dst,
        replay_projections,
    )
    from ..bq import query_df
    from ..config import settings
    from ..models.blend import effective_model_weight
    from ..models.prop_market import market_points

    served._validate_environment()
    usage = inherited.accepted_usage_law()
    cache_keys = query_df(f"""
        SELECT season, week, gsis_id
        FROM `{settings.features}.{table}`
        WHERE season IN UNNEST(@seasons)
        ORDER BY season, week, gsis_id
        """, params={"seasons": list(calibration.ALL_SEASONS)})
    if len(cache_keys) != 52_307 or cache_keys.duplicated(
        ["season", "week", "gsis_id"]
    ).any():
        raise ValueError("G0 selected cache keys differ from terminal contract")
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

    frames = []
    draw_parts = []
    parity = []
    maximum_mean_delta = 0.0
    with inherited._common_environment(usage):
        weight = effective_model_weight()
        if not np.isclose(weight, 0.45, rtol=0, atol=0):
            raise ValueError("G0 blend weight differs from the terminal law")
        for season in calibration.EVALUATION_SEASONS:
            panel, _ = load_panel_and_dst(season)
            market = market_points((season,)).drop_duplicates(
                ["season", "week", "gsis_id"])
            with _selected_cache(table):
                projected, draws = replay_projections(
                    panel, season, n_sims=10_000, seed=0, return_draws=True)
            projected, draws, _ = _market_blend_worlds(
                projected, draws, market, weight)
            season_keys = cache_keys[cache_keys.season.eq(season)]
            frame, aligned_draws, arm_parity = calibration._align_arm(
                projected, draws, accepted, season_keys, season,
                require_control_parity=False)
            metadata = projected[[
                "season", "week", "gsis_id", "position", "team",
            ]].drop_duplicates(["season", "week", "gsis_id"])
            frame = frame.merge(
                metadata,
                on=["season", "week", "gsis_id", "position"],
                how="left", validate="one_to_one",
            )
            if frame.team.isna().any():
                raise ValueError(f"G0 {season} team metadata does not align")
            corrected = position_calibration.apply_position_scales(
                aligned_draws, frame.position, schedule[season]["factors"])
            before = np.asarray(aligned_draws, dtype=float).mean(axis=1)
            after = corrected.mean(axis=1)
            maximum_mean_delta = max(
                maximum_mean_delta,
                float(np.max(np.abs(after - before), initial=0.0)),
            )
            frame["mean_projection"] = after
            frames.append(frame)
            draw_parts.append(corrected)
            parity.append(arm_parity)

    report = evaluate_dependence(
        pd.concat(frames, ignore_index=True),
        np.concatenate(draw_parts, axis=0),
    )
    invariants = {
        "selected_cache_rows": int(len(cache_keys)),
        "selected_cache_unique_keys": int(cache_keys.drop_duplicates().shape[0]),
        "tabpfn_coverage_is_one": all(
            np.isclose(row["tabpfn_coverage"], 1.0, rtol=0, atol=0)
            for row in parity
        ),
        "maximum_mean_delta": maximum_mean_delta,
        "maximum_mean_delta_at_most_1e_10": maximum_mean_delta <= 1e-10,
        "passes": False,
    }
    invariants["passes"] = (
        invariants["selected_cache_rows"] == 52_307
        and invariants["selected_cache_unique_keys"] == 52_307
        and invariants["tabpfn_coverage_is_one"]
        and invariants["maximum_mean_delta_at_most_1e_10"]
    )
    if not invariants["passes"]:
        raise ValueError("G0 terminal served invariants failed")
    report.update({
        "version": "v1",
        "panel": panel_id,
        "cache_table": table,
        "position_schedule": {str(key): value for key, value in schedule.items()},
        "usage_law": usage,
        "parity": parity,
        "invariants": invariants,
    })
    print(OUTPUT_PREFIX + json.dumps(report, sort_keys=True, allow_nan=False))
    return report
