"""Frozen four-feature Fantasy Points Route Share component-model test."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager

import numpy as np
import pandas as pd

from ..ingest.fantasy_points_route import EXPECTED_HASHES, PANEL_ID, TABLE
from ..models import coldstart, components, simulate
from ..models.featureset import active_training_rows
from .fantasy_points_route_share import ROUTE_FEATURES, attach_strict_prior_route


HELD_OUT_SEASONS = (2023, 2024, 2025)
ROUTE_POSITIONS = ("RB", "WR", "TE")
EXPECTED_RESOLVED_ROWS = 26_881
EXPECTED_RESOLVED_PLAYERS = 1_029
N_SIMS = 10_000
NUM_BOOST_ROUND = 400
SIM_ENV = {
    "GAME_SIM_MODE": "possession",
    "GAME_SIM_TEAM_FACTORS": "1",
}
FORBIDDEN_MODEL_ENVS = (
    "DROP_FEATURES",
    "RATE_DENOM_WEIGHTS",
    "MODEL_ENSEMBLE_MIX",
    "TRAIN_MAX_WEEK",
)


def _truth_spec(rows: pd.DataFrame, name: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (truth, mask) using the component model's own support rules."""
    position = rows.position.astype(str).to_numpy()
    all_rows = np.ones(len(rows), dtype=bool)
    receiving = position != "QB"
    passing = position == "QB"
    direct = {
        "targets": ("y_targets", receiving),
        "rec_tds": ("y_rec_tds", receiving),
        "carries": ("y_carries", all_rows),
        "rush_tds": ("y_rush_tds", all_rows),
        "pass_attempts": ("y_pass_attempts", passing),
        "pass_tds": ("y_pass_tds", passing),
        "interceptions": ("y_interceptions", passing),
    }
    if name in direct:
        column, mask = direct[name]
        truth = pd.to_numeric(rows[column], errors="coerce").to_numpy(float)
        return truth, mask & np.isfinite(truth)
    rates = {
        "catch_rate": ("y_receptions", "y_targets", receiving),
        "ypr": ("y_rec_yards", "y_receptions", receiving),
        "ypc": ("y_rush_yards", "y_carries", all_rows),
        "ypa": ("y_pass_yards", "y_pass_attempts", passing),
    }
    if name not in rates:
        raise ValueError(f"unknown component {name}")
    numerator, denominator, population = rates[name]
    num = pd.to_numeric(rows[numerator], errors="coerce").to_numpy(float)
    den = pd.to_numeric(rows[denominator], errors="coerce").to_numpy(float)
    mask = population & np.isfinite(num) & np.isfinite(den) & (den > 0)
    truth = np.full(len(rows), np.nan, dtype=float)
    truth[mask] = num[mask] / den[mask]
    return truth, mask


def component_metrics(rows: pd.DataFrame, predicted: pd.DataFrame) -> dict:
    """MAE for all eleven component means on their supported populations."""
    if len(rows) != len(predicted):
        raise ValueError("component prediction rows are misaligned")
    report: dict[str, dict] = {}
    for name in components.COMPONENT_NAMES:
        if name not in predicted:
            raise ValueError(f"component prediction missing {name}")
        truth, mask = _truth_spec(rows, name)
        estimate = pd.to_numeric(predicted[name], errors="coerce").to_numpy(float)
        mask &= np.isfinite(estimate)
        if not mask.any():
            raise ValueError(f"component {name} has no supported rows")
        absolute_error = np.abs(estimate[mask] - truth[mask])
        report[name] = {
            "rows": int(mask.sum()),
            "mae": float(absolute_error.mean()),
        }
    return report


def ensemble_crps(draws: np.ndarray, actual: np.ndarray) -> np.ndarray:
    """Efficient empirical CRPS for a row-aligned ensemble of draws."""
    values = np.asarray(draws, dtype=float)
    truth = np.asarray(actual, dtype=float)
    if values.ndim != 2 or truth.shape != (values.shape[0],):
        raise ValueError("CRPS inputs are not row aligned")
    if not np.isfinite(values).all() or not np.isfinite(truth).all():
        raise ValueError("CRPS inputs must be finite")
    members = values.shape[1]
    if members < 1:
        raise ValueError("CRPS requires at least one ensemble member")
    first = np.mean(np.abs(values - truth[:, None]), axis=1)
    ordered = np.sort(values, axis=1)
    coefficients = 2 * np.arange(members, dtype=float) - members + 1
    pair_term = (ordered * coefficients).sum(axis=1) / (members * members)
    return first - pair_term


def component_gate(aggregate: dict, coverage: dict[int, float]) -> dict:
    checks = {
        "coverage_at_least_80pct_each_fold": all(
            coverage.get(season, 0.0) >= 0.80
            for season in HELD_OUT_SEASONS
        ),
        "aggregate_30_brier_improves": (
            aggregate["treatment_brier_30"]
            < aggregate["control_brier_30"]
        ),
    }
    checks["passes"] = all(checks.values())
    return checks


def _validate_environment() -> None:
    ensemble = os.environ.get("MODEL_ENSEMBLE", "").strip()
    if ensemble not in ("", "1"):
        raise ValueError("Route component diagnostic requires MODEL_ENSEMBLE=1")
    if os.environ.get("EXTRA_FEATURES", "").strip():
        raise ValueError("Route component diagnostic requires blank EXTRA_FEATURES")
    active = [key for key in FORBIDDEN_MODEL_ENVS
              if os.environ.get(key, "").strip() not in ("", "0")]
    if active:
        raise ValueError(f"Route component diagnostic has active levers: {active}")


@contextmanager
def _arm_environment(treatment: bool):
    """Set the exact model feature arm and restore the process afterward."""
    keys = ("MODEL_ENSEMBLE", "EXTRA_FEATURES")
    prior = {key: os.environ.get(key) for key in keys}
    os.environ["MODEL_ENSEMBLE"] = "1"
    if treatment:
        os.environ["EXTRA_FEATURES"] = ",".join(ROUTE_FEATURES)
    else:
        os.environ.pop("EXTRA_FEATURES", None)
    try:
        yield
    finally:
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _fit_predict_components(
    panel: pd.DataFrame,
    evaluation: pd.DataFrame,
    held_out: int,
    treatment: bool,
) -> pd.DataFrame:
    with _arm_environment(treatment):
        fitted = components.train(
            panel, target_season=held_out, num_boost_round=NUM_BOOST_ROUND)
        model_rows = coldstart.fill_cold_start_features(
            evaluation.copy()).reset_index(drop=True)
        return fitted.predict_components(model_rows)


def _score_composed(
    rows: pd.DataFrame,
    predicted: pd.DataFrame,
    seed: int,
) -> pd.DataFrame:
    primary = rows.position.isin(ROUTE_POSITIONS).to_numpy()
    eval_rows = rows.loc[primary].reset_index(drop=True)
    eval_components = predicted.loc[primary].reset_index(drop=True)
    actual = pd.to_numeric(
        eval_rows.y_dk_points, errors="coerce").to_numpy(float)
    if not np.isfinite(actual).all():
        raise ValueError("Route component evaluation has non-finite DK points")
    result = simulate.simulate(
        eval_components,
        n_sims=N_SIMS,
        seed=seed,
        keep_draws=True,
        game_ids=eval_rows.get("game_id"),
        team_ids=eval_rows.get("team"),
        game_totals=eval_rows.get("game_total"),
        env=SIM_ENV,
    )
    if result.draws is None:
        raise RuntimeError("Route component simulation did not retain draws")
    draws = np.asarray(result.draws, dtype=float)
    out = eval_rows[["season", "week", "gsis_id", "position"]].copy()
    out["actual"] = actual
    out["point"] = draws.mean(axis=1)
    out["crps"] = ensemble_crps(draws, actual)
    for threshold in (20, 30):
        out[f"p_{threshold}"] = (draws >= threshold).mean(axis=1)
    for quantile in (90, 95, 99):
        q = np.quantile(draws, quantile / 100, axis=1)
        out[f"q{quantile}"] = q
        out[f"exceeds_q{quantile}"] = actual > q
    return out


def _comparison_metrics(frame: pd.DataFrame, label: str) -> dict:
    from sklearn.metrics import brier_score_loss

    actual = frame.actual.to_numpy(float)
    report = {
        "fold": label,
        "rows": int(len(frame)),
        "events_20": int((actual >= 20).sum()),
        "events_30": int((actual >= 30).sum()),
        "tail_rate_20": float((actual >= 20).mean()),
        "tail_rate_30": float((actual >= 30).mean()),
    }
    for arm in ("control", "treatment"):
        point = frame[f"{arm}_point"].to_numpy(float)
        report[f"{arm}_mae"] = float(np.abs(point - actual).mean())
        report[f"{arm}_crps"] = float(frame[f"{arm}_crps"].mean())
        for threshold in (20, 30):
            truth = (actual >= threshold).astype(int)
            report[f"{arm}_brier_{threshold}"] = float(
                brier_score_loss(truth, frame[f"{arm}_p_{threshold}"]))
        for quantile in (90, 95, 99):
            report[f"{arm}_q{quantile}_exceedance"] = float(
                frame[f"{arm}_exceeds_q{quantile}"].mean())
    return report


def _combine_arm_scores(
    control: pd.DataFrame,
    treatment: pd.DataFrame,
) -> pd.DataFrame:
    keys = ["season", "week", "gsis_id", "position"]
    if not control[keys].equals(treatment[keys]):
        raise ValueError("control/treatment Route component rows differ")
    out = control[[*keys, "actual"]].copy()
    if not np.allclose(control.actual, treatment.actual, rtol=0, atol=0):
        raise ValueError("control/treatment Route component outcomes differ")
    for arm, source in (("control", control), ("treatment", treatment)):
        for column in source.columns:
            if column in {*keys, "actual"}:
                continue
            out[f"{arm}_{column}"] = source[column].to_numpy()
    return out


def _aggregate_components(folds: list[dict]) -> dict:
    aggregate: dict[str, dict[str, dict]] = {}
    for arm in ("control", "treatment"):
        aggregate[arm] = {}
        for name in components.COMPONENT_NAMES:
            rows = sum(fold[arm][name]["rows"] for fold in folds)
            weighted = sum(
                fold[arm][name]["mae"] * fold[arm][name]["rows"]
                for fold in folds
            )
            aggregate[arm][name] = {
                "rows": int(rows),
                "mae": float(weighted / rows),
            }
    return aggregate


def evaluate_component_models(
    panel: pd.DataFrame,
    accepted: pd.DataFrame,
) -> dict:
    keys = ["season", "week", "gsis_id"]
    if panel.duplicated(keys).any():
        raise ValueError("training panel has duplicate player-weeks")
    if accepted.duplicated(keys).any():
        raise ValueError("accepted panel has duplicate player-weeks")
    accepted_columns = accepted[keys + ["pos", "actual"]].rename(
        columns={"pos": "accepted_pos", "actual": "accepted_actual"})
    keyed = panel.merge(
        accepted_columns,
        on=keys,
        how="right",
        validate="one_to_one",
        indicator=True,
    )
    if not keyed._merge.eq("both").all():
        missing = keyed.loc[
            keyed._merge.ne("both"), keys].head().to_dict("records")
        raise ValueError(
            "accepted Route component keys missing training rows: "
            f"{missing}")
    keyed = keyed.drop(columns="_merge")
    if not keyed.position.astype(str).eq(keyed.accepted_pos.astype(str)).all():
        raise ValueError("accepted Route component positions disagree")
    training_actual = pd.to_numeric(keyed.y_dk_points, errors="coerce")
    accepted_actual = pd.to_numeric(keyed.accepted_actual, errors="coerce")
    if not np.allclose(training_actual, accepted_actual, rtol=0, atol=0.11,
                       equal_nan=False):
        raise ValueError("accepted Route component actuals disagree")
    keyed = active_training_rows(keyed)
    if keyed.empty:
        raise ValueError("Route component evaluation has no active rows")

    coverage: dict[int, float] = {}
    comparisons: list[pd.DataFrame] = []
    fold_reports: list[dict] = []
    component_folds: list[dict] = []
    for held_out in HELD_OUT_SEASONS:
        evaluation = keyed[keyed.season.eq(held_out)].reset_index(drop=True)
        if evaluation.empty:
            raise ValueError(f"Route component fold {held_out} is empty")
        primary = evaluation.position.isin(ROUTE_POSITIONS)
        coverage[held_out] = float(
            evaluation.loc[primary, "fp_route_share_last"].notna().mean())
        arm_scores: dict[str, pd.DataFrame] = {}
        arm_component_metrics: dict[str, dict] = {}
        for treatment, arm in ((False, "control"), (True, "treatment")):
            predicted = _fit_predict_components(
                panel, evaluation, held_out, treatment)
            arm_component_metrics[arm] = component_metrics(
                evaluation, predicted)
            arm_scores[arm] = _score_composed(
                evaluation, predicted, seed=20_260_811 + held_out)
        comparison = _combine_arm_scores(
            arm_scores["control"], arm_scores["treatment"])
        comparisons.append(comparison)
        report = _comparison_metrics(comparison, str(held_out))
        report["coverage"] = coverage[held_out]
        report["positions"] = {
            str(position): _comparison_metrics(group, str(position))
            for position, group in comparison.groupby("position", sort=True)
        }
        report["components"] = arm_component_metrics
        fold_reports.append(report)
        component_folds.append(arm_component_metrics)

    combined = pd.concat(comparisons, ignore_index=True)
    aggregate = _comparison_metrics(combined, "aggregate")
    aggregate["positions"] = {
        str(position): _comparison_metrics(group, str(position))
        for position, group in combined.groupby("position", sort=True)
    }
    aggregate["components"] = _aggregate_components(component_folds)
    gate = component_gate(aggregate, coverage)
    return {
        "panel": PANEL_ID,
        "folds": fold_reports,
        "aggregate": aggregate,
        "coverage": {str(key): value for key, value in coverage.items()},
        "gate": gate,
        "simulation": {
            "n_sims": N_SIMS,
            "model_ensemble": 1,
            **{key.lower(): value for key, value in SIM_ENV.items()},
        },
        "disposition": (
            "route-share-component-tail-passes" if gate["passes"]
            else "route-share-component-tail-fails"),
    }


def run(panel_id: str = PANEL_ID) -> dict:
    if panel_id != PANEL_ID:
        raise ValueError(f"Route component protocol is frozen to {PANEL_ID}")
    _validate_environment()
    from ..bq import query_df
    from ..config import settings

    completeness = query_df(f"""
        SELECT COUNT(DISTINCT FORMAT('%d-%d', season, week)) AS slates,
               COUNTIF(selected) AS selected_rows
        FROM `{settings.predictions}.replay_candidates`
        WHERE panel_run_id = @panel_id AND research_eligible
        """, params={"panel_id": panel_id}).iloc[0]
    if int(completeness.slates or 0) != 107:
        raise ValueError("corrected K1 panel is incomplete")
    if int(completeness.selected_rows or 0) != 107 * 80:
        raise ValueError("corrected K1 panel is not exact true-80")

    route = query_df(f"""
        SELECT season, week, gsis_id, route_share, source_sha256
        FROM `{settings.raw}.{TABLE}`
        WHERE resolution_status = 'resolved'
        """)
    if len(route) != EXPECTED_RESOLVED_ROWS:
        raise ValueError("Route component source row count differs")
    if route.gsis_id.nunique() != EXPECTED_RESOLVED_PLAYERS:
        raise ValueError("Route component source player count differs")
    if set(route.source_sha256.dropna().astype(str)) != set(
            EXPECTED_HASHES.values()):
        raise ValueError("Route component source hashes differ")

    panel = query_df(f"""
        SELECT *
        FROM `{settings.features}.player_week_training`
        WHERE season BETWEEN {int(settings.train_first_season)} AND 2025
          AND position IN ('QB', 'RB', 'WR', 'TE')
        """)
    panel = attach_strict_prior_route(panel, route)
    accepted = query_df(f"""
        SELECT season, week, gsis_id, pos, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id
          AND research_eligible
          AND season IN UNNEST(@seasons)
          AND pos IN ('QB', 'RB', 'WR', 'TE')
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={
            "panel_id": panel_id,
            "seasons": list(HELD_OUT_SEASONS),
        })
    report = evaluate_component_models(panel, accepted)
    report["source_audit"] = {
        "resolved_rows": int(len(route)),
        "resolved_players": int(route.gsis_id.nunique()),
        "source_hashes": sorted(EXPECTED_HASHES.values()),
        "training_rows": int(len(panel)),
        "accepted_rows": int(len(accepted)),
    }
    print("FP_ROUTE_COMPONENT_JSON=" + json.dumps(report, sort_keys=True))
    return report
