"""Outcome-blind fit of within-team target/carry concentration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import gammaln


CALIBRATION_SEASONS = (2021, 2022)
EVALUATION_SEASONS = (2023, 2024, 2025)
ALL_SEASONS = (*CALIBRATION_SEASONS, *EVALUATION_SEASONS)
POSITIONS = ("QB", "RB", "WR", "TE")
KINDS = ("targets", "carries")
MIN_OBSERVED_TOTAL = 15
MIN_CONCENTRATION = 0.05
K_BOUNDS = (5.0, 500.0)
OPTIMIZER_X_TOL = 1e-6
OBJECTIVE_TIE_TOL = 1e-10
MIN_OPPORTUNITY_COVERAGE = 0.95
NUM_BOOST_ROUND = 400
BOOTSTRAP_RESAMPLES = 2_000
BOOTSTRAP_SEED = 8_112_026
DESCRIPTIVE_GRID = (
    5.0, 8.0, 12.0, 16.0, 20.0, 24.0, 29.0, 35.0, 40.0,
    50.0, 65.0, 80.0, 100.0, 150.0, 200.0, 300.0, 500.0,
)
OUTPUT_PREFIX = "USAGE_DIRICHLET_CALIBRATION_JSON="
FORBIDDEN_ENVS = (
    "EXTRA_FEATURES",
    "DROP_FEATURES",
    "MODEL_ENSEMBLE_MIX",
    "RATE_DENOM_WEIGHTS",
    "TABPFN_COMPONENTS",
    "TRAIN_MAX_WEEK",
)


@dataclass(frozen=True)
class UsageGroup:
    season: int
    week: int
    team: str
    kind: str
    players: tuple[str, ...]
    probabilities: np.ndarray
    observed: np.ndarray

    @property
    def total(self) -> int:
        return int(self.observed.sum())


def _validate_environment() -> None:
    ensemble = os.environ.get("MODEL_ENSEMBLE", "").strip()
    if ensemble not in ("", "1"):
        raise ValueError("usage calibration requires MODEL_ENSEMBLE=1")
    active = [
        name for name in FORBIDDEN_ENVS
        if os.environ.get(name, "").strip() not in ("", "0")
    ]
    if active:
        raise ValueError(f"usage calibration has active model levers: {active}")


def _validate_counts(values: np.ndarray, label: str) -> np.ndarray:
    numeric = np.asarray(values, dtype=float)
    if not np.isfinite(numeric).all() or (numeric < 0).any():
        raise ValueError(f"{label} outcomes must be finite and nonnegative")
    rounded = np.rint(numeric)
    if not np.allclose(numeric, rounded, rtol=0, atol=1e-9):
        raise ValueError(f"{label} outcomes must be integer counts")
    return rounded.astype(np.int64)


def build_usage_groups(
    rows: pd.DataFrame,
    predicted: pd.DataFrame,
    season: int,
) -> tuple[list[UsageGroup], dict]:
    """Build exact conditional groups and the frozen coverage audit."""
    if len(rows) != len(predicted):
        raise ValueError("usage calibration predictions are not row aligned")
    required = {
        "season", "week", "team", "gsis_id", "position", "was_active",
        "y_targets", "y_carries",
    }
    missing = required - set(rows.columns)
    if missing:
        raise ValueError(f"usage calibration rows lack {sorted(missing)}")
    if not rows.season.eq(season).all():
        raise ValueError("usage calibration target rows mix seasons")
    if not set(KINDS).issubset(predicted.columns):
        raise ValueError("usage calibration lacks target/carry predictions")

    base = rows.reset_index(drop=True).copy()
    base = base[
        base.was_active.fillna(False).astype(bool)
        & base.position.astype(str).isin(POSITIONS)
        & base.team.notna()
        & base.gsis_id.notna()
    ].copy()
    prediction = predicted.reset_index(drop=True).loc[base.index]
    base = base.reset_index(drop=True)
    prediction = prediction.reset_index(drop=True)
    if base.empty:
        raise ValueError(f"usage calibration has no active rows in {season}")

    groups: list[UsageGroup] = []
    audit: dict[str, dict] = {}
    for kind in KINDS:
        subset = base.copy()
        estimates = pd.to_numeric(
            prediction[kind], errors="coerce").to_numpy(float)
        if kind == "targets":
            keep = subset.position.astype(str).ne("QB").to_numpy()
            subset = subset.loc[keep].reset_index(drop=True)
            estimates = estimates[keep]
        outcomes = _validate_counts(
            subset[f"y_{kind}"].to_numpy(), kind)
        if not np.isfinite(estimates).all() or (estimates < 0).any():
            raise ValueError(f"{kind} predictions must be finite/nonnegative")
        subset["_prediction"] = estimates
        subset["_observed"] = outcomes

        otherwise_eligible_groups = 0
        otherwise_eligible_opportunities = 0
        excluded_zero_mean_groups = 0
        excluded_zero_mean_opportunities = 0
        group_sizes: list[int] = []
        for (week, team), group in subset.groupby(
                ["week", "team"], sort=True, dropna=False):
            observed_total = int(group["_observed"].sum())
            if len(group) < 2 or observed_total < MIN_OBSERVED_TOTAL:
                continue
            otherwise_eligible_groups += 1
            otherwise_eligible_opportunities += observed_total
            positive = group["_prediction"].to_numpy(float) > 0
            excluded_has_usage = bool(
                (group["_observed"].to_numpy(np.int64)[~positive] > 0).any())
            if positive.sum() < 2 or excluded_has_usage:
                excluded_zero_mean_groups += 1
                excluded_zero_mean_opportunities += observed_total
                continue
            eligible = group.loc[positive].sort_values("gsis_id")
            eligible_total = int(eligible["_observed"].sum())
            if eligible_total < MIN_OBSERVED_TOTAL:
                # This can only occur when zero-mean players had usage, which
                # is already excluded above; retain the explicit fail-closed
                # guard so a future population change cannot alter the law.
                excluded_zero_mean_groups += 1
                excluded_zero_mean_opportunities += observed_total
                continue
            means = eligible["_prediction"].to_numpy(float)
            probabilities = means / means.sum()
            observed = eligible["_observed"].to_numpy(np.int64)
            group_sizes.append(len(eligible))
            groups.append(UsageGroup(
                season=int(season),
                week=int(week),
                team=str(team),
                kind=kind,
                players=tuple(eligible.gsis_id.astype(str)),
                probabilities=probabilities,
                observed=observed,
            ))
        retained_opportunities = (
            otherwise_eligible_opportunities
            - excluded_zero_mean_opportunities
        )
        coverage = (
            retained_opportunities / otherwise_eligible_opportunities
            if otherwise_eligible_opportunities else 0.0
        )
        kind_groups = [g for g in groups if g.kind == kind]
        audit[kind] = {
            "season": int(season),
            "active_rows": int(len(subset)),
            "otherwise_eligible_groups": int(otherwise_eligible_groups),
            "otherwise_eligible_opportunities": int(
                otherwise_eligible_opportunities),
            "retained_groups": int(len(kind_groups)),
            "retained_players": int(sum(len(g.players) for g in kind_groups)),
            "retained_opportunities": int(retained_opportunities),
            "excluded_zero_mean_groups": int(excluded_zero_mean_groups),
            "excluded_zero_mean_opportunities": int(
                excluded_zero_mean_opportunities),
            "opportunity_coverage": float(coverage),
            "minimum_group_size": int(min(group_sizes)) if group_sizes else 0,
            "maximum_group_size": int(max(group_sizes)) if group_sizes else 0,
        }
    if not groups:
        raise ValueError(f"usage calibration retained no groups in {season}")
    return groups, audit


def _log_coefficient(observed: np.ndarray) -> float:
    return float(
        gammaln(observed.sum() + 1)
        - gammaln(observed + 1).sum()
    )


def multinomial_nll(group: UsageGroup) -> float:
    p = np.asarray(group.probabilities, dtype=float)
    y = np.asarray(group.observed, dtype=np.int64)
    if (p <= 0).any() or not np.isclose(p.sum(), 1.0, rtol=0, atol=1e-12):
        raise ValueError("multinomial probabilities are invalid")
    return float(-(_log_coefficient(y) + np.dot(y, np.log(p))))


def dirichlet_multinomial_nll(group: UsageGroup, concentration: float) -> float:
    if not np.isfinite(concentration) or concentration <= 0:
        raise ValueError("Dirichlet concentration must be positive and finite")
    p = np.asarray(group.probabilities, dtype=float)
    y = np.asarray(group.observed, dtype=np.int64)
    alpha = np.maximum(concentration * p, MIN_CONCENTRATION)
    alpha_0 = float(alpha.sum())
    log_probability = (
        _log_coefficient(y)
        + float(gammaln(alpha_0) - gammaln(alpha_0 + y.sum()))
        + float((gammaln(alpha + y) - gammaln(alpha)).sum())
    )
    return float(-log_probability)


def concentration_objective(
    groups: list[UsageGroup], concentration: float,
) -> float:
    if not groups:
        raise ValueError("concentration objective has no groups")
    return float(sum(
        dirichlet_multinomial_nll(group, concentration)
        for group in groups
    ))


def fit_concentration(groups: list[UsageGroup]) -> dict:
    """Fit the one frozen global K with deterministic endpoint handling."""
    result = minimize_scalar(
        lambda value: concentration_objective(groups, float(value)),
        bounds=K_BOUNDS,
        method="bounded",
        options={"xatol": OPTIMIZER_X_TOL},
    )
    candidates = [float(result.x), *K_BOUNDS]
    scored = [
        (value, concentration_objective(groups, value))
        for value in candidates
    ]
    minimum = min(objective for _, objective in scored)
    tied = [
        (value, objective) for value, objective in scored
        if abs(objective - minimum) <= OBJECTIVE_TIE_TOL
    ]
    selected, objective = max(tied, key=lambda pair: pair[0])
    return {
        "selected_k": float(selected),
        "selected_k_display": round(float(selected), 6),
        "objective": float(objective),
        "optimizer_success": bool(result.success),
        "optimizer_message": str(result.message),
        "optimizer_iterations": int(result.nit),
        "strictly_interior": bool(K_BOUNDS[0] < selected < K_BOUNDS[1]),
        "bounds": list(K_BOUNDS),
        "x_tolerance": OPTIMIZER_X_TOL,
        "descriptive_curve": [
            {
                "k": value,
                "negative_log_likelihood": concentration_objective(
                    groups, value),
            }
            for value in DESCRIPTIVE_GRID
        ],
    }


def score_groups(groups: list[UsageGroup], concentration: float) -> pd.DataFrame:
    records = []
    for group in groups:
        production = multinomial_nll(group)
        fitted = dirichlet_multinomial_nll(group, concentration)
        records.append({
            "season": group.season,
            "week": group.week,
            "team": group.team,
            "kind": group.kind,
            "players": len(group.players),
            "opportunities": group.total,
            "production_nll": production,
            "fitted_nll": fitted,
            "fitted_minus_production": fitted - production,
        })
    return pd.DataFrame.from_records(records)


def summarize_scores(scores: pd.DataFrame) -> dict:
    if scores.empty:
        raise ValueError("usage score summary has no groups")
    opportunities = int(scores.opportunities.sum())
    production = float(scores.production_nll.sum())
    fitted = float(scores.fitted_nll.sum())
    return {
        "groups": int(len(scores)),
        "opportunities": opportunities,
        "production_nll_sum": production,
        "fitted_nll_sum": fitted,
        "production_mean_nll_per_group": float(scores.production_nll.mean()),
        "fitted_mean_nll_per_group": float(scores.fitted_nll.mean()),
        "mean_nll_improvement_per_group": float(
            scores.production_nll.mean() - scores.fitted_nll.mean()),
        "production_nll_per_opportunity": production / opportunities,
        "fitted_nll_per_opportunity": fitted / opportunities,
    }


def clustered_bootstrap(scores: pd.DataFrame) -> dict:
    """Fixed team-week cluster bootstrap of fitted-minus-production NLL."""
    frame = scores.copy()
    frame["cluster"] = (
        frame.season.astype(str) + ":" + frame.week.astype(str)
        + ":" + frame.team.astype(str)
    )
    clusters = [
        group.fitted_minus_production.to_numpy(float)
        for _, group in frame.groupby("cluster", sort=True)
    ]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.empty(BOOTSTRAP_RESAMPLES, dtype=float)
    for index in range(BOOTSTRAP_RESAMPLES):
        selected = rng.integers(0, len(clusters), size=len(clusters))
        values = np.concatenate([clusters[item] for item in selected])
        draws[index] = float(values.mean())
    return {
        "clusters": int(len(clusters)),
        "resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
        "observed_mean_fitted_minus_production": float(
            frame.fitted_minus_production.mean()),
        "bootstrap_mean": float(draws.mean()),
        "ci95": [
            float(np.quantile(draws, 0.025)),
            float(np.quantile(draws, 0.975)),
        ],
    }


def usage_gate(
    fit: dict,
    population: dict[int, dict],
    evaluation_scores: pd.DataFrame,
) -> dict:
    aggregate = summarize_scores(evaluation_scores)
    by_kind = {
        kind: summarize_scores(evaluation_scores[evaluation_scores.kind.eq(kind)])
        for kind in KINDS
    }
    by_season = {
        season: summarize_scores(
            evaluation_scores[evaluation_scores.season.eq(season)])
        for season in EVALUATION_SEASONS
    }
    coverage_passes = all(
        population[season][kind]["opportunity_coverage"]
        >= MIN_OPPORTUNITY_COVERAGE
        for season in ALL_SEASONS
        for kind in KINDS
    )
    season_improvements = sum(
        report["fitted_mean_nll_per_group"]
        < report["production_mean_nll_per_group"]
        for report in by_season.values()
    )
    checks = {
        "optimizer_succeeded": bool(fit["optimizer_success"]),
        "selected_k_strictly_interior": bool(fit["strictly_interior"]),
        "opportunity_coverage_at_least_95pct_each_kind_season": (
            coverage_passes),
        "aggregate_mean_nll_per_group_improves": (
            aggregate["fitted_mean_nll_per_group"]
            < aggregate["production_mean_nll_per_group"]),
        "target_mean_nll_per_group_improves": (
            by_kind["targets"]["fitted_mean_nll_per_group"]
            < by_kind["targets"]["production_mean_nll_per_group"]),
        "carry_mean_nll_per_group_improves": (
            by_kind["carries"]["fitted_mean_nll_per_group"]
            < by_kind["carries"]["production_mean_nll_per_group"]),
        "at_least_two_of_three_seasons_improve": season_improvements >= 2,
    }
    checks["passes"] = all(checks.values())
    return {
        **checks,
        "improving_seasons": int(season_improvements),
    }


def run() -> dict:
    """Train prior-season models, fit K, and emit the one frozen report."""
    _validate_environment()
    from ..backtest.replay import load_panel_and_dst
    from ..models import coldstart, components

    groups_by_season: dict[int, list[UsageGroup]] = {}
    population: dict[int, dict] = {}
    prediction_rows: dict[int, int] = {}
    for season in ALL_SEASONS:
        panel, _ = load_panel_and_dst(season)
        fitted = components.train(
            panel,
            target_season=season,
            num_boost_round=NUM_BOOST_ROUND,
        )
        rows = panel[panel.season.eq(season)].reset_index(drop=True)
        model_rows = coldstart.fill_cold_start_features(rows.copy())
        predicted = fitted.predict_components(model_rows)
        groups, audit = build_usage_groups(rows, predicted, season)
        groups_by_season[season] = groups
        population[season] = audit
        prediction_rows[season] = int(len(rows))

    calibration_groups = [
        group
        for season in CALIBRATION_SEASONS
        for group in groups_by_season[season]
    ]
    evaluation_groups = [
        group
        for season in EVALUATION_SEASONS
        for group in groups_by_season[season]
    ]
    fit = fit_concentration(calibration_groups)
    calibration_scores = score_groups(
        calibration_groups, fit["selected_k"])
    evaluation_scores = score_groups(
        evaluation_groups, fit["selected_k"])
    gate = usage_gate(fit, population, evaluation_scores)

    report = {
        "fit": fit,
        "population": {str(key): value for key, value in population.items()},
        "prediction_rows": {
            str(key): value for key, value in prediction_rows.items()},
        "calibration": {
            "aggregate": summarize_scores(calibration_scores),
            "by_season": {
                str(season): summarize_scores(
                    calibration_scores[
                        calibration_scores.season.eq(season)])
                for season in CALIBRATION_SEASONS
            },
            "by_kind": {
                kind: summarize_scores(
                    calibration_scores[calibration_scores.kind.eq(kind)])
                for kind in KINDS
            },
        },
        "evaluation": {
            "aggregate": summarize_scores(evaluation_scores),
            "by_season": {
                str(season): summarize_scores(
                    evaluation_scores[evaluation_scores.season.eq(season)])
                for season in EVALUATION_SEASONS
            },
            "by_kind": {
                kind: summarize_scores(
                    evaluation_scores[evaluation_scores.kind.eq(kind)])
                for kind in KINDS
            },
            "clustered_bootstrap": clustered_bootstrap(evaluation_scores),
        },
        "gate": gate,
        "disposition": (
            "data-fitted-usage-concentration-passes"
            if gate["passes"]
            else "data-fitted-usage-concentration-fails"
        ),
        "model": {
            "calibration_seasons": list(CALIBRATION_SEASONS),
            "evaluation_seasons": list(EVALUATION_SEASONS),
            "ensemble": 1,
            "num_boost_round": NUM_BOOST_ROUND,
            "extra_features": [],
            "minimum_observed_total": MIN_OBSERVED_TOTAL,
            "minimum_concentration": MIN_CONCENTRATION,
        },
    }
    print(OUTPUT_PREFIX + json.dumps(report, sort_keys=True))
    return report
