"""Frozen score-free SIS ASOE conditional target-allocation gate."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

from . import usage_dirichlet_calibration as usage
from ..ingest import sis_asoe


CALIBRATION_SEASON = 2022
EVALUATION_SEASONS = (2023, 2024, 2025)
ALL_SEASONS = (CALIBRATION_SEASON, *EVALUATION_SEASONS)
TARGET_WEEKS = tuple(range(5, 19))
GLOBAL_K = 28.154043586960896
MIN_GROUP_PROBABILITY_MASS = 0.50
BETA_BOUNDS = (0.0, 8.0)
BETA_L2 = 0.01
BETA_X_TOL = 1e-6
BETA_ACTIVITY_FLOOR = 0.01
MIN_EVALUATION_GROUP_COVERAGE = 0.50
BOOTSTRAP_RESAMPLES = 2_000
BOOTSTRAP_SEED = 8_113_126
PANEL_ID = "20260811-pitclean-e80-k1-role12union-a12ab31"
OUTPUT_PREFIX = "SIS_ASOE_ALLOCATION_JSON="


@dataclass(frozen=True)
class AllocationGeometry:
    scores: np.ndarray
    supported_players: int
    supported_probability_mass: float
    valid: bool


def _validate_environment() -> None:
    usage._validate_environment()


def group_geometry(
    group: usage.UsageGroup,
    player_profiles: pd.DataFrame,
    offense_profiles: pd.DataFrame,
    defense_asoe: pd.DataFrame,
    opponent: str,
) -> AllocationGeometry:
    player = player_profiles[
        player_profiles.season.eq(group.season)
        & player_profiles.target_week.eq(group.week)
        & player_profiles.team.eq(group.team)
    ].drop_duplicates("gsis_id").set_index("gsis_id")
    offense = offense_profiles[
        offense_profiles.season.eq(group.season)
        & offense_profiles.target_week.eq(group.week)
        & offense_profiles.team.eq(group.team)
    ]
    defense = defense_asoe[
        defense_asoe.season.eq(group.season)
        & defense_asoe.target_week.eq(group.week)
        & defense_asoe.defense.eq(opponent)
    ]
    scores = np.zeros(len(group.players), dtype=np.float64)
    supported = np.zeros(len(group.players), dtype=bool)
    if len(offense) != 1 or len(defense) != 1:
        return AllocationGeometry(scores, 0, 0.0, False)
    off = offense.iloc[0]
    deff = defense.iloc[0]
    if not bool(off.offense_alignment_supported) or not bool(deff.asoe_supported):
        return AllocationGeometry(scores, 0, 0.0, False)
    for index, gsis_id in enumerate(group.players):
        if gsis_id not in player.index:
            continue
        row = player.loc[gsis_id]
        if isinstance(row, pd.DataFrame):
            raise ValueError("ASOE player profile repeats a player-week")
        if not bool(row.alignment_supported):
            continue
        scores[index] = float(deff.defense_asoe) * (
            float(row.player_wide_share) - float(off.offense_wide_share)
        )
        supported[index] = True
    mass = float(np.asarray(group.probabilities)[supported].sum())
    valid = bool(
        supported.sum() >= 2
        and mass >= MIN_GROUP_PROBABILITY_MASS
        and np.ptp(scores[supported]) > 0
    )
    return AllocationGeometry(scores, int(supported.sum()), mass, valid)


def tilt_probabilities(
    probabilities: np.ndarray,
    scores: np.ndarray,
    beta: float,
    *,
    valid: bool,
) -> np.ndarray:
    p = np.asarray(probabilities, dtype=np.float64)
    if not valid or beta == 0:
        return p.copy()
    centered = np.asarray(scores, dtype=np.float64) - float(np.dot(p, scores))
    logits = np.log(p) + float(beta) * centered
    logits -= float(logits.max())
    q = np.exp(logits)
    q /= q.sum()
    if not np.isfinite(q).all() or (q <= 0).any() or not np.isclose(
        q.sum(), 1.0, rtol=0, atol=1e-12
    ):
        raise ValueError("ASOE treatment probabilities are invalid")
    return q


def build_geometry_frame(
    groups: list[usage.UsageGroup],
    opponents: dict[tuple[int, int, str], str],
    player_profiles: pd.DataFrame,
    offense_profiles: pd.DataFrame,
    defense_asoe: pd.DataFrame,
) -> pd.DataFrame:
    records = []
    for ordinal, group in enumerate(groups):
        key = (group.season, group.week, group.team)
        if key not in opponents:
            raise ValueError(f"ASOE group has no schedule opponent: {key}")
        geometry = group_geometry(
            group, player_profiles, offense_profiles, defense_asoe,
            opponents[key],
        )
        records.append({
            "ordinal": ordinal,
            "season": group.season,
            "week": group.week,
            "team": group.team,
            "opponent": opponents[key],
            "geometry_valid": geometry.valid,
            "supported_players": geometry.supported_players,
            "supported_probability_mass": geometry.supported_probability_mass,
            "scores": geometry.scores,
            "group": group,
        })
    return pd.DataFrame.from_records(records)


def _objective(frame: pd.DataFrame, beta: float) -> float:
    losses = []
    for row in frame.itertuples(index=False):
        q = tilt_probabilities(
            row.group.probabilities, row.scores, beta,
            valid=bool(row.geometry_valid),
        )
        treatment = usage.UsageGroup(
            season=row.group.season, week=row.group.week,
            team=row.group.team, kind=row.group.kind,
            players=row.group.players, probabilities=q,
            observed=row.group.observed,
        )
        losses.append(usage.dirichlet_multinomial_nll(treatment, GLOBAL_K))
    return float(np.mean(losses) + BETA_L2 * beta * beta)


def fit_beta(frame: pd.DataFrame) -> dict:
    if frame.empty:
        raise ValueError("ASOE beta fit has no calibration groups")
    result = minimize_scalar(
        lambda value: _objective(frame, float(value)),
        bounds=BETA_BOUNDS, method="bounded",
        options={"xatol": BETA_X_TOL},
    )
    candidates = [float(result.x), 0.0, *BETA_BOUNDS]
    scored = [(value, _objective(frame, value)) for value in candidates]
    minimum = min(objective for _, objective in scored)
    tied = [
        pair for pair in scored
        if abs(pair[1] - minimum) <= usage.OBJECTIVE_TIE_TOL
    ]
    selected, objective = min(tied, key=lambda pair: abs(pair[0]))
    return {
        "beta": float(selected),
        "beta_display": round(float(selected), 6),
        "objective": float(objective),
        "optimizer_success": bool(result.success),
        "optimizer_message": str(result.message),
        "optimizer_iterations": int(result.nit),
        "bounds": list(BETA_BOUNDS),
        "l2_penalty": BETA_L2,
    }


def score_frame(frame: pd.DataFrame, beta: float) -> pd.DataFrame:
    records = []
    signatures: set[tuple] = set()
    for row in frame.itertuples(index=False):
        q = tilt_probabilities(
            row.group.probabilities, row.scores, beta,
            valid=bool(row.geometry_valid),
        )
        signatures.add(tuple(np.round(q, 12)))
        treatment = usage.UsageGroup(
            season=row.group.season, week=row.group.week,
            team=row.group.team, kind=row.group.kind,
            players=row.group.players, probabilities=q,
            observed=row.group.observed,
        )
        control_nll = usage.dirichlet_multinomial_nll(row.group, GLOBAL_K)
        treatment_nll = usage.dirichlet_multinomial_nll(treatment, GLOBAL_K)
        records.append({
            "season": row.group.season, "week": row.group.week,
            "team": row.group.team, "opportunities": row.group.total,
            "geometry_valid": bool(row.geometry_valid),
            "supported_probability_mass": row.supported_probability_mass,
            "probability_changed": not np.allclose(
                q, row.group.probabilities, rtol=0, atol=1e-12),
            "control_nll": control_nll,
            "treatment_nll": treatment_nll,
            "treatment_minus_control": treatment_nll - control_nll,
        })
    scores = pd.DataFrame.from_records(records)
    scores.attrs["probability_signatures"] = len(signatures)
    return scores


def summarize(scores: pd.DataFrame) -> dict:
    if scores.empty:
        raise ValueError("ASOE score summary has no groups")
    return {
        "groups": int(len(scores)),
        "opportunities": int(scores.opportunities.sum()),
        "control_mean_nll_per_group": float(scores.control_nll.mean()),
        "treatment_mean_nll_per_group": float(scores.treatment_nll.mean()),
        "mean_treatment_minus_control": float(scores.treatment_minus_control.mean()),
        "geometry_coverage": float(scores.geometry_valid.mean()),
        "changed_groups": int(scores.probability_changed.sum()),
    }


def clustered_bootstrap(scores: pd.DataFrame) -> dict:
    clusters = [
        group.treatment_minus_control.to_numpy(float)
        for _, group in scores.groupby(["season", "week", "team"], sort=True)
    ]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.empty(BOOTSTRAP_RESAMPLES)
    for index in range(BOOTSTRAP_RESAMPLES):
        selected = rng.integers(0, len(clusters), size=len(clusters))
        draws[index] = float(np.concatenate([clusters[i] for i in selected]).mean())
    return {
        "clusters": len(clusters), "resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
        "ci95": [float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))],
        "bootstrap_mean": float(draws.mean()),
    }


def gate_report(scores: pd.DataFrame, fit: dict) -> dict:
    evaluation = scores[scores.season.isin(EVALUATION_SEASONS)]
    coverage = {
        str(season): float(evaluation[evaluation.season.eq(season)].geometry_valid.mean())
        for season in EVALUATION_SEASONS
    }
    aggregate = summarize(evaluation)
    checks = {
        "optimizer_succeeded": bool(fit["optimizer_success"]),
        "evaluation_geometry_coverage_at_least_50pct_each_season": all(
            value >= MIN_EVALUATION_GROUP_COVERAGE for value in coverage.values()
        ),
        "conditional_law_active": bool(
            fit["beta"] >= BETA_ACTIVITY_FLOOR
            and evaluation.probability_changed.sum() >= 2
        ),
        "aggregate_mean_target_nll_improves": bool(
            aggregate["mean_treatment_minus_control"] < 0
        ),
    }
    checks["passes"] = all(checks.values())
    return {**checks, "coverage_by_season": coverage}


def run() -> dict:
    _validate_environment()
    from ..backtest.replay import load_panel_and_dst
    from ..bq import query_df
    from ..config import settings
    from ..models import coldstart, components

    player_profiles = query_df(
        f"SELECT * FROM `{settings.raw}.fantasy_points_alignment_player_l4`"
    )
    offense_profiles = query_df(
        f"SELECT * FROM `{settings.raw}.fantasy_points_alignment_team_l4`"
    )
    attempts = query_df(
        f"SELECT * FROM `{settings.raw}.sis_alignment_attempt_game`"
    )
    schedule = query_df(f"""
        SELECT CAST(season AS INT64) season, CAST(week AS INT64) week,
               CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                    WHEN 'STL' THEN 'LA' ELSE home_team END team,
               CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                    WHEN 'STL' THEN 'LA' ELSE away_team END opponent
        FROM `{settings.raw}.schedules`
        WHERE season IN UNNEST(@seasons) AND game_type='REG'
        UNION ALL
        SELECT CAST(season AS INT64), CAST(week AS INT64),
               CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                    WHEN 'STL' THEN 'LA' ELSE away_team END,
               CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                    WHEN 'STL' THEN 'LA' ELSE home_team END
        FROM `{settings.raw}.schedules`
        WHERE season IN UNNEST(@seasons) AND game_type='REG'
        """, params={"seasons": list(ALL_SEASONS)})
    defense_asoe, asoe_audit = sis_asoe.build_defense_asoe(
        attempts, offense_profiles, schedule,
    )

    groups: list[usage.UsageGroup] = []
    opponents: dict[tuple[int, int, str], str] = {}
    population: dict[str, dict] = {}
    for season in ALL_SEASONS:
        panel, _ = load_panel_and_dst(season)
        fitted = components.train(
            panel, target_season=season,
            num_boost_round=usage.NUM_BOOST_ROUND,
        )
        rows = panel[panel.season.eq(season)].reset_index(drop=True)
        predicted = fitted.predict_components(
            coldstart.fill_cold_start_features(rows.copy()))
        season_groups, audit = usage.build_usage_groups(rows, predicted, season)
        season_groups = [
            group for group in season_groups
            if group.kind == "targets" and group.week in TARGET_WEEKS
        ]
        if not season_groups:
            raise ValueError(f"ASOE retained no target groups in {season}")
        group_rows = rows[
            rows.week.isin(TARGET_WEEKS) & rows.team.notna() & rows.opponent.notna()
        ][["week", "team", "opponent"]].drop_duplicates()
        if group_rows.duplicated(["week", "team"]).any():
            raise ValueError(f"ASOE {season} panel has ambiguous opponents")
        opponents.update({
            (season, int(row.week), str(row.team)): str(row.opponent)
            for row in group_rows.itertuples(index=False)
        })
        groups.extend(season_groups)
        population[str(season)] = {
            "target_groups_weeks_5_18": len(season_groups),
            "usage_audit": audit["targets"],
        }

    geometry = build_geometry_frame(
        groups, opponents, player_profiles, offense_profiles, defense_asoe,
    )
    calibration = geometry[geometry.season.eq(CALIBRATION_SEASON)]
    fit = fit_beta(calibration)
    scores = score_frame(geometry, fit["beta"])
    calibration_scores = scores[scores.season.eq(CALIBRATION_SEASON)]
    evaluation_scores = scores[scores.season.isin(EVALUATION_SEASONS)]
    gate = gate_report(scores, fit)
    report = {
        "version": "v1",
        "panel": PANEL_ID,
        "control": {"allocation": "dirichlet", "k": GLOBAL_K},
        "treatment": "sis-asoe-conditional-target-center",
        "fit": fit,
        "population": population,
        "asoe": asoe_audit,
        "calibration": summarize(calibration_scores),
        "evaluation": {
            "aggregate": summarize(evaluation_scores),
            "by_season": {
                str(season): summarize(evaluation_scores[evaluation_scores.season.eq(season)])
                for season in EVALUATION_SEASONS
            },
            "clustered_bootstrap_diagnostic": clustered_bootstrap(evaluation_scores),
        },
        "gate": gate,
        "disposition": (
            "sis-asoe-allocation-passes-to-final-served"
            if gate["passes"] else "sis-asoe-allocation-fails"
        ),
        "outcomes_read": ["within-team target counts"],
        "forbidden_outcomes_read": [],
    }
    print(OUTPUT_PREFIX + json.dumps(report, sort_keys=True, allow_nan=False))
    return report


__all__ = [
    "build_geometry_frame", "fit_beta", "gate_report", "group_geometry",
    "run", "score_frame", "tilt_probabilities",
]
