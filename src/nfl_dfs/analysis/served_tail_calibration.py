"""Frozen calibration audit of the final draws that score adopted lineups."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager

import numpy as np
import pandas as pd

from ..ingest.fantasy_points_route import PANEL_ID


HELD_OUT_SEASONS = (2023, 2024, 2025)
POSITIONS = ("RB", "WR", "TE")
EXPECTED_FOLD_ROWS = {2023: 4_666, 2024: 4_596, 2025: 4_614}
EXPECTED_ROWS = sum(EXPECTED_FOLD_ROWS.values())
N_SIMS = 10_000
MEAN_TOLERANCE = 1e-4
ACTUAL_TOLERANCE = 0.11
PRODUCTION_ENV = {
    "MODEL_ENSEMBLE": "1",
    "EXTRA_FEATURES": "",
    "GAME_SIM_MODE": "possession",
    "GAME_SIM_PACE": "",
    "GAME_SIM_TEAM_FACTORS": "1",
    "GAME_SIM_USAGE": "",
    "TD_LEDGER": "",
    "SIM_WIDEN_DRAWS": "fitted",
    "ROOKIE_WIDEN": "",
    "TABPFN_MARGINALS": "1",
    "EMP_MARGINALS": "1",
    "EMP_POS": "",
    "SHAPE_MIX": "1",
    "SERVED_TAIL_SCALE": "1",
    "SERVED_POSITION_SCALES": "",
    "BLEND_MODEL_WEIGHT": "0.45",
    "BIGPLAY": "0",
    "TABPFN_COMPONENTS": "0",
    "ENSEMBLE_WORLD_MODE": "",
}
FORBIDDEN_ACTIVE_ENVS = (
    "DROP_FEATURES", "RATE_DENOM_WEIGHTS", "MODEL_ENSEMBLE_MIX",
    "TRAIN_MAX_WEEK", "TABPFN_MEAN", "ALT_CEIL", "N_ROUTE_TAIL",
    "N_COVERAGE_TAIL", "SCHAAKE_DIAG", "SCHAAKE_TEMPLATE_MODE",
)


def _validate_environment() -> None:
    """Fail before overwriting any inherited research intervention."""
    active = [
        key for key in FORBIDDEN_ACTIVE_ENVS
        if os.environ.get(key, "").strip().lower()
        not in ("", "0", "off", "false", "none")
    ]
    if active:
        raise ValueError(f"served-tail diagnostic has active levers: {active}")
    ensemble = os.environ.get("MODEL_ENSEMBLE", "").strip()
    if ensemble not in ("", "1"):
        raise ValueError("served-tail diagnostic requires MODEL_ENSEMBLE=1")
    if os.environ.get("EXTRA_FEATURES", "").strip():
        raise ValueError("served-tail diagnostic requires blank EXTRA_FEATURES")


@contextmanager
def _production_environment():
    prior = {key: os.environ.get(key) for key in PRODUCTION_ENV}
    os.environ.update(PRODUCTION_ENV)
    try:
        yield
    finally:
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _cluster_standard_error(
    values: np.ndarray,
    season: np.ndarray,
    week: np.ndarray,
) -> float:
    """Finite-cluster-corrected SE for an equally weighted row mean."""
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all() or not len(values):
        raise ValueError("cluster SE values must be finite and nonempty")
    groups = pd.DataFrame({
        "season": np.asarray(season, dtype=int),
        "week": np.asarray(week, dtype=int),
        "centered": values - values.mean(),
    }).groupby(["season", "week"], sort=False).centered.sum()
    n_clusters = len(groups)
    if n_clusters < 2:
        raise ValueError("cluster SE requires at least two slates")
    variance = (
        n_clusters / (n_clusters - 1)
        * float(np.square(groups.to_numpy(float)).sum())
        / float(len(values) ** 2)
    )
    return float(np.sqrt(max(variance, 0.0)))


def _pinball(actual: np.ndarray, quantile: np.ndarray, level: float) -> np.ndarray:
    residual = np.asarray(actual, dtype=float) - np.asarray(quantile, dtype=float)
    return np.maximum(level * residual, (level - 1.0) * residual)


def _score_draws(frame: pd.DataFrame, draws: np.ndarray) -> pd.DataFrame:
    """Reduce a player-by-world matrix to persisted row-level scores."""
    from .fantasy_points_route_components import ensemble_crps

    values = np.asarray(draws, dtype=float)
    if values.ndim != 2 or values.shape[0] != len(frame):
        raise ValueError("served-tail draws are not row aligned")
    if values.shape[1] != N_SIMS or not np.isfinite(values).all():
        raise ValueError("served-tail draws have wrong size or non-finite values")
    actual = pd.to_numeric(frame.actual, errors="coerce").to_numpy(float)
    if not np.isfinite(actual).all():
        raise ValueError("served-tail outcomes must be finite")
    out = frame[[
        "season", "week", "gsis_id", "position", "market_covered",
        "tabpfn_covered",
    ]].copy()
    out["actual"] = actual
    out["point_abs_error"] = np.abs(values.mean(axis=1) - actual)
    out["crps"] = ensemble_crps(values, actual)
    for threshold in (20, 30):
        truth = actual >= threshold
        probability = (values >= threshold).mean(axis=1)
        out[f"event_{threshold}"] = truth
        out[f"brier_{threshold}"] = np.square(probability - truth)
    quantiles = np.quantile(values, (0.90, 0.95, 0.99), axis=1)
    for index, level in enumerate((0.90, 0.95, 0.99)):
        label = int(round(level * 100))
        q = quantiles[index]
        out[f"exceeds_q{label}"] = actual > q
        out[f"pinball_q{label}"] = _pinball(actual, q, level)
    return out


def _summarize(frame: pd.DataFrame, label: str) -> dict:
    if frame.empty:
        raise ValueError(f"served-tail metric slice {label} is empty")
    report = {
        "fold": label,
        "rows": int(len(frame)),
        "slates": int(frame[["season", "week"]].drop_duplicates().shape[0]),
        "point_mae": float(frame.point_abs_error.mean()),
        "crps": float(frame.crps.mean()),
        "events_20": int(frame.event_20.sum()),
        "events_30": int(frame.event_30.sum()),
        "brier_20": float(frame.brier_20.mean()),
        "brier_30": float(frame.brier_30.mean()),
        "market_coverage": float(frame.market_covered.mean()),
        "tabpfn_coverage": float(frame.tabpfn_covered.mean()),
    }
    for label_q, nominal in ((90, 0.10), (95, 0.05), (99, 0.01)):
        values = frame[f"exceeds_q{label_q}"].astype(float).to_numpy()
        observed = float(values.mean())
        binomial_se = float(np.sqrt(observed * (1.0 - observed) / len(values)))
        cluster_se = _cluster_standard_error(
            values, frame.season.to_numpy(), frame.week.to_numpy())
        report[f"q{label_q}_exceedance"] = observed
        report[f"q{label_q}_calibration_gap"] = observed - nominal
        report[f"q{label_q}_binomial_se"] = binomial_se
        report[f"q{label_q}_cluster_se"] = cluster_se
        report[f"q{label_q}_cluster_ci95_low"] = observed - 1.96 * cluster_se
        report[f"q{label_q}_cluster_ci95_high"] = observed + 1.96 * cluster_se
        report[f"q{label_q}_minimum_detectable_gap_95"] = 1.96 * cluster_se
        report[f"q{label_q}_pinball"] = float(
            frame[f"pinball_q{label_q}"].mean())
    return report


def served_tail_gate(aggregate: dict) -> dict:
    above = all(
        aggregate[f"q{label}_exceedance"] > nominal
        for label, nominal in ((90, 0.10), (95, 0.05), (99, 0.01))
    )
    checks = {
        "all_quantile_exceedances_above_nominal": above,
        "q99_cluster_ci95_low_above_nominal": (
            aggregate["q99_cluster_ci95_low"] > 0.01
        ),
    }
    return {**checks, "passes": all(checks.values())}


def _align_evaluation(
    projected: pd.DataFrame,
    draws: np.ndarray,
    accepted: pd.DataFrame,
    tabpfn_keys: pd.DataFrame,
    season: int,
) -> tuple[pd.DataFrame, np.ndarray, dict]:
    """Match final-path worlds to the exact accepted active player rows."""
    keys = ["season", "week", "gsis_id", "position"]
    required_projected = {
        *keys, "actual", "was_active", "model_points_pre", "proj_points",
        "market_points",
    }
    if missing := required_projected - set(projected.columns):
        raise ValueError(f"served-tail projections missing {sorted(missing)}")
    if draws.shape[0] != len(projected):
        raise ValueError("served-tail projection/draw rows differ")
    source = projected.copy()
    source["_draw_index"] = np.arange(len(source))
    source["tabpfn_covered"] = source.merge(
        tabpfn_keys.assign(tabpfn_covered=True),
        on=["season", "week", "gsis_id"], how="left", sort=False,
        validate="many_to_one",
    ).tabpfn_covered.fillna(False).to_numpy(bool)
    source["market_covered"] = source.market_points.notna()
    expected = accepted[accepted.season.eq(season)].copy()
    expected = expected.rename(columns={
        "pos": "position",
        "actual": "accepted_actual",
        "model_points_pre": "accepted_model_points_pre",
        "mean_projection": "accepted_mean_projection",
    })
    joined = expected.merge(
        source,
        on=keys,
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if not joined._merge.eq("both").all():
        missing = joined.loc[joined._merge.ne("both"), keys].head()
        raise ValueError(
            "served-tail accepted keys missing from replay: "
            f"{missing.to_dict('records')}")
    joined = joined[joined.was_active.fillna(False).astype(bool)].copy()
    joined = joined[joined.position.isin(POSITIONS)].reset_index(drop=True)
    expected_rows = EXPECTED_FOLD_ROWS.get(season)
    if expected_rows is not None and len(joined) != expected_rows:
        raise ValueError(
            f"served-tail {season} has {len(joined)} active rows; "
            f"expected {expected_rows}")
    actual_delta = np.abs(
        joined.accepted_actual.to_numpy(float) - joined.actual.to_numpy(float))
    if float(actual_delta.max(initial=0.0)) > ACTUAL_TOLERANCE:
        raise ValueError("served-tail accepted actuals disagree with replay")
    pre_delta = np.abs(
        joined.accepted_model_points_pre.to_numpy(float)
        - joined.model_points_pre.to_numpy(float))
    final_delta = np.abs(
        joined.accepted_mean_projection.to_numpy(float)
        - joined.proj_points.to_numpy(float))
    if float(pre_delta.max(initial=0.0)) > MEAN_TOLERANCE:
        raise ValueError("served-tail post-shaper means differ from accepted panel")
    if float(final_delta.max(initial=0.0)) > MEAN_TOLERANCE:
        raise ValueError("served-tail post-blend means differ from accepted panel")
    frame = joined[[
        "season", "week", "gsis_id", "position", "accepted_actual",
        "market_covered", "tabpfn_covered",
    ]].rename(columns={"accepted_actual": "actual"})
    indices = joined._draw_index.to_numpy(int)
    parity = {
        "season": int(season),
        "rows": int(len(joined)),
        "max_actual_abs_delta": float(actual_delta.max(initial=0.0)),
        "max_post_shaper_mean_abs_delta": float(pre_delta.max(initial=0.0)),
        "max_post_blend_mean_abs_delta": float(final_delta.max(initial=0.0)),
    }
    return frame, np.asarray(draws)[indices], parity


def _evaluate_scores(scores: pd.DataFrame, parity: list[dict]) -> dict:
    if len(scores) != EXPECTED_ROWS:
        raise ValueError(
            f"served-tail aggregate has {len(scores)} rows; expected {EXPECTED_ROWS}")
    folds = [
        _summarize(scores[scores.season.eq(season)], str(season))
        for season in HELD_OUT_SEASONS
    ]
    aggregate = _summarize(scores, "aggregate")
    aggregate["positions"] = {
        str(position): _summarize(group, str(position))
        for position, group in scores.groupby("position", sort=True)
    }
    gate = served_tail_gate(aggregate)
    return {
        "panel": PANEL_ID,
        "folds": folds,
        "aggregate": aggregate,
        "parity": parity,
        "gate": gate,
        "simulation": {
            "n_sims": N_SIMS,
            "model_ensemble": 1,
            "game_sim_mode": "possession",
            "game_sim_team_factors": "1",
            "sim_widen_draws": "fitted",
            "tabpfn_marginals": "1",
            "emp_marginals_fallback": "1",
            "shape_mix": 1.0,
            "blend_model_weight": 0.45,
        },
        "disposition": (
            "served-upper-tail-defect-confirmed" if gate["passes"]
            else "served-upper-tail-defect-not-confirmed"
        ),
    }


def run(panel_id: str = PANEL_ID) -> dict:
    if panel_id != PANEL_ID:
        raise ValueError(f"served-tail protocol is frozen to {PANEL_ID}")
    _validate_environment()
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
            "seasons": list(HELD_OUT_SEASONS),
            "positions": list(POSITIONS),
        })
    scores: list[pd.DataFrame] = []
    parity: list[dict] = []
    with _production_environment():
        weight = effective_model_weight()
        if not np.isclose(weight, 0.45, rtol=0, atol=0):
            raise ValueError(f"served-tail model blend weight is {weight}, not 0.45")
        for season in HELD_OUT_SEASONS:
            panel, _ = load_panel_and_dst(season)
            projected, draws = replay_projections(
                panel, season, n_sims=N_SIMS, seed=0, return_draws=True)
            market = market_points((season,)).drop_duplicates(
                ["season", "week", "gsis_id"])
            projected, draws, _ = _market_blend_worlds(
                projected, draws, market, weight)
            tabpfn_keys = query_df(f"""
                SELECT DISTINCT season, week, gsis_id
                FROM `{settings.features}.tabpfn_projections`
                WHERE season = @season
                """, params={"season": int(season)})
            frame, final_draws, fold_parity = _align_evaluation(
                projected, draws, accepted, tabpfn_keys, season)
            scores.append(_score_draws(frame, final_draws))
            parity.append(fold_parity)
    report = _evaluate_scores(pd.concat(scores, ignore_index=True), parity)
    print("SERVED_TAIL_CALIBRATION_JSON=" + json.dumps(report, sort_keys=True))
    return report
