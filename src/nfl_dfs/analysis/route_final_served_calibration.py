"""Walk-forward final-served calibration of the exact Route Share arm."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager

import numpy as np
import pandas as pd

from ..ingest.fantasy_points_route import EXPECTED_HASHES, PANEL_ID, TABLE
from . import served_position_calibration as position_calibration
from . import served_tail_calibration as served
from . import served_tail_recalibration as uncertainty
from .fantasy_points_route_components import (
    EXPECTED_RESOLVED_PLAYERS,
    EXPECTED_RESOLVED_ROWS,
)
from .fantasy_points_route_share import (
    ROUTE_FEATURES,
    attach_strict_prior_route,
)


CALIBRATION_SEASON = 2022
EVALUATION_SEASONS = (2023, 2024, 2025)
ALL_SEASONS = (CALIBRATION_SEASON, *EVALUATION_SEASONS)
POSITIONS = ("QB", "RB", "WR", "TE")
PRIMARY_POSITIONS = ("RB", "WR", "TE")
EXPECTED_ROWS = {2022: 5_115, 2023: 5_177, 2024: 5_098, 2025: 5_121}
EXPECTED_PRIMARY_ROWS = {2023: 4_666, 2024: 4_596, 2025: 4_614}
SCALE_GRID = np.round(np.arange(0.75, 1.5001, 0.005), 3)
QUANTILES = ((90, 0.90), (95, 0.95), (99, 0.99))
OUTPUT_PREFIX = "ROUTE_FINAL_SERVED_CALIBRATION_JSON="


@contextmanager
def _arm_environment(treatment: bool):
    prior = os.environ.get("EXTRA_FEATURES")
    if treatment:
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


def _fit_position_factors(
    folds: dict[int, tuple[pd.DataFrame, np.ndarray]],
) -> dict:
    """Fit the frozen normalized-pinball objective on arbitrary prior folds."""
    seasons = tuple(sorted(int(season) for season in folds))
    if not seasons:
        raise ValueError("Route final-served calibration has no prior folds")
    if any(season < CALIBRATION_SEASON for season in seasons):
        raise ValueError("Route calibration fold precedes the licensed history")
    selected: dict[str, float] = {}
    reports: dict[str, dict] = {}
    for position in POSITIONS:
        prepared = {}
        identity = {}
        for season in seasons:
            frame, draws = folds[season]
            values = np.asarray(draws, dtype=float)
            if values.ndim != 2 or len(frame) != values.shape[0]:
                raise ValueError("Route calibration fold rows do not align")
            mask = frame.position.astype(str).eq(position).to_numpy()
            if not mask.any():
                raise ValueError(f"Route calibration lacks {position} in {season}")
            actual = frame.loc[mask, "actual"].to_numpy(dtype=float)
            position_draws = values[mask]
            means = position_draws.mean(axis=1)
            quantiles = np.quantile(
                position_draws, [level for _, level in QUANTILES], axis=1)
            for index, (label, level) in enumerate(QUANTILES):
                loss = float(served._pinball(
                    actual, quantiles[index], level).mean())
                if not np.isfinite(loss) or loss <= 0:
                    raise ValueError(
                        f"invalid identity loss for {season} {position} q{label}")
                prepared[(season, label)] = (
                    actual, means, quantiles[index], level)
                identity[(season, label)] = loss

        curve = []
        for factor in SCALE_GRID:
            season_objectives = []
            for season in seasons:
                ratios = []
                for label, _ in QUANTILES:
                    actual, means, quantile, level = prepared[(season, label)]
                    corrected = means + float(factor) * (quantile - means)
                    loss = float(served._pinball(
                        actual, corrected, level).mean())
                    ratios.append(loss / identity[(season, label)])
                season_objectives.append(float(np.mean(ratios)))
            curve.append(float(np.mean(season_objectives)))
        minimum = min(curve)
        tied = [
            float(factor) for factor, objective in zip(SCALE_GRID, curve)
            if np.isclose(objective, minimum, rtol=0, atol=1e-12)
        ]
        factor = min(tied, key=lambda value: (abs(value - 1.0), value))
        selected[position] = float(factor)
        reports[position] = {
            "selected_factor": float(factor),
            "minimum_objective": float(minimum),
            # The grid is fixed globally; storing aligned objectives avoids a
            # >256 KiB structured Cloud Logging payload without dropping the
            # mandatory factor curve.
            "curve_objectives": curve,
        }
    return {
        "calibration_seasons": list(seasons),
        "factors": selected,
        "positions": reports,
    }


def fit_walk_forward_schedule(
    folds: dict[int, tuple[pd.DataFrame, np.ndarray]],
) -> dict[int, dict]:
    """Fit each target from that arm's strictly earlier OOS folds only."""
    if set(folds) != set(ALL_SEASONS):
        raise ValueError("Route factor schedule requires exact 2022-2025 folds")
    schedule = {}
    for target in EVALUATION_SEASONS:
        prior = {
            season: folds[season]
            for season in ALL_SEASONS
            if season < target
        }
        fit = _fit_position_factors(prior)
        if fit["calibration_seasons"] != list(range(2022, target)):
            raise ValueError("Route factor schedule is not strictly walk-forward")
        schedule[target] = fit
    return schedule


def score_walk_forward(
    folds: dict[int, tuple[pd.DataFrame, np.ndarray]],
    schedule: dict[int, dict],
) -> tuple[pd.DataFrame, float]:
    """Apply one arm's frozen target-specific factors and score its folds."""
    if set(schedule) != set(EVALUATION_SEASONS):
        raise ValueError("Route factor schedule lacks an evaluation season")
    scores = []
    max_mean_delta = 0.0
    for target in EVALUATION_SEASONS:
        frame, draws = folds[target]
        corrected = position_calibration.apply_position_scales(
            draws, frame.position, schedule[target]["factors"])
        before = np.asarray(draws, dtype=float).mean(axis=1)
        after = corrected.mean(axis=1)
        max_mean_delta = max(
            max_mean_delta,
            float(np.max(np.abs(after - before), initial=0.0)),
        )
        scores.append(served._score_draws(frame, corrected))
    return pd.concat(scores, ignore_index=True), max_mean_delta


def _summaries(scores: pd.DataFrame) -> dict:
    primary = scores[scores.position.isin(PRIMARY_POSITIONS)].copy()
    if len(primary) != sum(EXPECTED_PRIMARY_ROWS.values()):
        raise ValueError("Route calibrated primary population differs")
    return {
        "folds": [
            served._summarize(primary[primary.season.eq(season)], str(season))
            for season in EVALUATION_SEASONS
        ],
        "aggregate": {
            **served._summarize(primary, "aggregate"),
            "positions": {
                str(position): served._summarize(group, str(position))
                for position, group in primary.groupby("position", sort=True)
            },
        },
    }


def evaluate_calibrated_arms(
    control_folds: dict[int, tuple[pd.DataFrame, np.ndarray]],
    treatment_folds: dict[int, tuple[pd.DataFrame, np.ndarray]],
) -> dict:
    """Fit, score and compare two already-aligned final-served arms."""
    for season in ALL_SEASONS:
        left = control_folds[season][0]
        right = treatment_folds[season][0]
        keys = [
            "season", "week", "gsis_id", "position", "actual",
            "market_covered", "tabpfn_covered",
        ]
        if not left[keys].equals(right[keys]):
            raise ValueError(f"Route control/treatment rows differ in {season}")
    control_schedule = fit_walk_forward_schedule(control_folds)
    treatment_schedule = fit_walk_forward_schedule(treatment_folds)
    control_scores, control_mean_delta = score_walk_forward(
        control_folds, control_schedule)
    treatment_scores, treatment_mean_delta = score_walk_forward(
        treatment_folds, treatment_schedule)
    keys = ["season", "week", "gsis_id", "position", "actual"]
    if not control_scores[keys].equals(treatment_scores[keys]):
        raise ValueError("Route calibrated score rows differ")
    control_reports = _summaries(control_scores)
    treatment_reports = _summaries(treatment_scores)
    control_primary = control_scores[
        control_scores.position.isin(PRIMARY_POSITIONS)].reset_index(drop=True)
    treatment_primary = treatment_scores[
        treatment_scores.position.isin(PRIMARY_POSITIONS)].reset_index(drop=True)
    gate = calibrated_route_gate(
        control_reports["aggregate"],
        treatment_reports["aggregate"],
        max(control_mean_delta, treatment_mean_delta),
    )
    return {
        "control_schedule": {
            str(key): value for key, value in control_schedule.items()},
        "treatment_schedule": {
            str(key): value for key, value in treatment_schedule.items()},
        "control": control_reports,
        "treatment": treatment_reports,
        "maximum_mean_delta": {
            "control": control_mean_delta,
            "treatment": treatment_mean_delta,
        },
        "paired_loss_uncertainty": uncertainty._paired_loss_uncertainty(
            control_primary, treatment_primary),
        "gate": gate,
        "disposition": (
            "route-final-served-calibration-passes"
            if gate["passes"]
            else "route-final-served-calibration-fails"
        ),
    }


def calibrated_route_gate(
    control_summary: dict,
    treatment_summary: dict,
    maximum_mean_delta: float,
) -> dict:
    """The one frozen scientific comparison plus its mechanical invariant."""
    gate = {
        "aggregate_calibrated_30_brier_improves": (
            float(treatment_summary["brier_30"])
            < float(control_summary["brier_30"])
        ),
        "maximum_mean_delta_at_most_1e_10": maximum_mean_delta <= 1e-10,
    }
    gate["passes"] = all(gate.values())
    return gate


def _align_arm(
    projected: pd.DataFrame,
    draws: np.ndarray,
    accepted: pd.DataFrame,
    tabpfn_keys: pd.DataFrame,
    season: int,
    *,
    require_control_parity: bool,
) -> tuple[pd.DataFrame, np.ndarray, dict]:
    keys = ["season", "week", "gsis_id", "position"]
    source = projected.copy()
    source["_draw_index"] = np.arange(len(source))
    source["tabpfn_covered"] = source.merge(
        tabpfn_keys.assign(tabpfn_covered=True),
        on=["season", "week", "gsis_id"],
        how="left",
        sort=False,
        validate="many_to_one",
    ).tabpfn_covered.fillna(False).to_numpy(bool)
    source["market_covered"] = source.market_points.notna()
    expected = accepted[accepted.season.eq(season)].rename(columns={
        "pos": "position",
        "actual": "accepted_actual",
        "model_points_pre": "accepted_model_points_pre",
        "mean_projection": "accepted_mean_projection",
    })
    joined = expected.merge(
        source, on=keys, how="left", validate="one_to_one", indicator=True)
    if not joined._merge.eq("both").all():
        raise ValueError(f"Route final-served {season} keys do not align")
    joined = joined[joined.was_active.fillna(False).astype(bool)]
    joined = joined[joined.position.isin(POSITIONS)].reset_index(drop=True)
    if len(joined) != EXPECTED_ROWS[season]:
        raise ValueError(
            f"Route final-served {season} has {len(joined)} rows; "
            f"expected {EXPECTED_ROWS[season]}")
    actual_delta = np.abs(
        joined.accepted_actual.to_numpy(float) - joined.actual.to_numpy(float))
    if float(actual_delta.max(initial=0.0)) > served.ACTUAL_TOLERANCE:
        raise ValueError("Route final-served actuals disagree")
    pre_delta = np.abs(
        joined.accepted_model_points_pre.to_numpy(float)
        - joined.model_points_pre.to_numpy(float))
    final_delta = np.abs(
        joined.accepted_mean_projection.to_numpy(float)
        - joined.proj_points.to_numpy(float))
    if require_control_parity:
        if float(pre_delta.max(initial=0.0)) > served.MEAN_TOLERANCE:
            raise ValueError("Route control post-shaper mean differs")
        if float(final_delta.max(initial=0.0)) > served.MEAN_TOLERANCE:
            raise ValueError("Route control post-blend mean differs")
    frame = joined[[
        "season", "week", "gsis_id", "position", "accepted_actual",
        "market_covered", "tabpfn_covered",
    ]].rename(columns={"accepted_actual": "actual"})
    indices = joined._draw_index.to_numpy(int)
    parity = {
        "season": int(season),
        "rows": int(len(joined)),
        "tabpfn_coverage": float(frame.tabpfn_covered.mean()),
        "market_coverage": float(frame.market_covered.mean()),
        "max_actual_abs_delta": float(actual_delta.max(initial=0.0)),
        "max_accepted_post_shaper_mean_abs_delta": float(
            pre_delta.max(initial=0.0)),
        "max_accepted_post_blend_mean_abs_delta": float(
            final_delta.max(initial=0.0)),
        "control_parity_required": bool(require_control_parity),
    }
    return frame, np.asarray(draws)[indices], parity


def run(panel_id: str = PANEL_ID) -> dict:
    if panel_id != PANEL_ID:
        raise ValueError(f"Route recalibration is frozen to panel {PANEL_ID}")
    served._validate_environment()
    from ..backtest.replay import (
        _market_blend_worlds,
        load_panel_and_dst,
        replay_projections,
    )
    from ..bq import query_df
    from ..config import settings
    from ..models.blend import effective_model_weight
    from ..models.prop_market import market_points

    route = query_df(f"""
        SELECT season, week, gsis_id, route_share, source_sha256
        FROM `{settings.raw}.{TABLE}`
        WHERE resolution_status = 'resolved'
        """)
    if len(route) != EXPECTED_RESOLVED_ROWS:
        raise ValueError("Route recalibration source row count differs")
    if route.gsis_id.nunique() != EXPECTED_RESOLVED_PLAYERS:
        raise ValueError("Route recalibration source player count differs")
    if set(route.source_sha256.dropna().astype(str)) != set(
            EXPECTED_HASHES.values()):
        raise ValueError("Route recalibration source hashes differ")
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
            "seasons": list(ALL_SEASONS),
            "positions": list(POSITIONS),
        })
    tabpfn_keys = query_df(f"""
        SELECT DISTINCT season, week, gsis_id
        FROM `{settings.features}.tabpfn_projections`
        WHERE season IN UNNEST(@seasons)
        """, params={"seasons": list(ALL_SEASONS)})

    folds = {"control": {}, "treatment": {}}
    parity = {"control": [], "treatment": []}
    with served._production_environment():
        weight = effective_model_weight()
        if not np.isclose(weight, 0.45, rtol=0, atol=0):
            raise ValueError("Route recalibration blend weight differs")
        for season in ALL_SEASONS:
            panel, _ = load_panel_and_dst(season)
            panel = panel.drop(columns=[
                "fp_route_source_season", "fp_route_source_week",
                "fp_route_prior_observations", *ROUTE_FEATURES,
            ], errors="ignore")
            panel = attach_strict_prior_route(panel, route)
            market = market_points((season,)).drop_duplicates(
                ["season", "week", "gsis_id"])
            season_tabpfn = tabpfn_keys[tabpfn_keys.season.eq(season)]
            for arm, treatment in (("control", False), ("treatment", True)):
                with _arm_environment(treatment):
                    projected, draws = replay_projections(
                        panel,
                        season,
                        n_sims=served.N_SIMS,
                        seed=0,
                        return_draws=True,
                    )
                projected, draws, _ = _market_blend_worlds(
                    projected, draws, market, weight)
                frame, aligned_draws, arm_parity = _align_arm(
                    projected,
                    draws,
                    accepted,
                    season_tabpfn,
                    season,
                    require_control_parity=(arm == "control"),
                )
                folds[arm][season] = (frame, aligned_draws)
                parity[arm].append(arm_parity)

    report = evaluate_calibrated_arms(
        folds["control"], folds["treatment"])
    report.update({
        "panel": PANEL_ID,
        "parity": parity,
        "source_audit": {
            "resolved_rows": int(len(route)),
            "resolved_players": int(route.gsis_id.nunique()),
            "source_hashes": sorted(EXPECTED_HASHES.values()),
        },
        "simulation": {
            "calibration_season": CALIBRATION_SEASON,
            "evaluation_seasons": list(EVALUATION_SEASONS),
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
