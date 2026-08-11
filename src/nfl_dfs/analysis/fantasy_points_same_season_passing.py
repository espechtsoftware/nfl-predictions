"""Frozen same-season last-four-week Advanced Passing diagnostic."""

from __future__ import annotations

import json

import pandas as pd

from .fantasy_points_coverage_fit import _score
from .fantasy_points_route_share import CONTROL_NUMERIC, _fit_predict
from ..ingest.fantasy_points_route import PANEL_ID
from ..ingest.fantasy_points_same_season_passing import (
    PASSING_FEATURES,
    PLAN_NAME,
    TABLE,
)


HELD_OUT_SEASONS = (2023, 2024, 2025)


def attach_same_season_passing(
    targets: pd.DataFrame,
    passing: pd.DataFrame,
) -> pd.DataFrame:
    """Attach only the exact same-season W-4:W-1 passing window."""
    target_needed = {"season", "week", "gsis_id", "pos"}
    source_needed = {
        "season", "target_week", "gsis_id", "resolution_status",
        "fp_pass_l4_supported", "source_week_start", "source_week_end",
        "source_run_id", *PASSING_FEATURES,
    }
    if missing := target_needed - set(targets.columns):
        raise ValueError(f"passing targets missing {sorted(missing)}")
    if missing := source_needed - set(passing.columns):
        raise ValueError(f"passing source missing {sorted(missing)}")
    source = passing[
        passing.resolution_status.eq("resolved") & passing.gsis_id.notna()
    ].copy()
    keys = ["season", "target_week", "gsis_id"]
    if source.duplicated(keys).any():
        raise ValueError("same-season passing source has duplicate QB windows")
    source = source.rename(columns={
        "target_week": "source_target_week",
        "source_week_start": "passing_source_week_start",
        "source_week_end": "passing_source_week_end",
        "source_run_id": "passing_source_run_id",
    }).drop(columns="pos", errors="ignore")
    out = targets.merge(
        source,
        left_on=["season", "week", "gsis_id"],
        right_on=["season", "source_target_week", "gsis_id"],
        how="left",
        validate="many_to_one",
    )
    out["fp_pass_l4_supported"] = out[
        "fp_pass_l4_supported"].fillna(False).astype(bool)
    populated = out.fp_pass_l4_supported
    if populated.any():
        target_week = out.loc[populated, "week"].astype(int)
        checks = (
            out.loc[populated, "source_target_week"].astype(int).eq(target_week)
            & out.loc[populated, "passing_source_week_start"].astype(int).eq(
                target_week - 4)
            & out.loc[populated, "passing_source_week_end"].astype(int).eq(
                target_week - 1)
            & target_week.ge(5)
            & out.loc[populated, "pos"].eq("QB")
        )
        if not checks.all():
            raise ValueError("same-season passing join violated PIT/QB rules")
    return out


def _correlations(frame: pd.DataFrame, fold: int) -> list[dict]:
    residual = frame.actual.astype(float) - frame.mean_projection.astype(float)
    tail = frame.actual.ge(30).astype(int)
    rows: list[dict] = []
    for feature in PASSING_FEATURES:
        valid = frame[feature].notna()
        rows.append({
            "fold": int(fold),
            "feature": feature,
            "rows": int(valid.sum()),
            "spearman_projection_residual": float(
                frame.loc[valid, feature].astype(float).corr(
                    residual[valid], method="spearman")),
            "pearson_tail_30": float(
                frame.loc[valid, feature].astype(float).corr(
                    tail[valid].astype(float))),
        })
    return rows


def passing_gate(aggregate: dict, coverage: dict[int, float]) -> dict:
    checks = {
        "coverage_at_least_50pct_each_fold": all(
            coverage.get(season, 0.0) >= 0.50
            for season in HELD_OUT_SEASONS
        ),
        "aggregate_30_brier_improves": (
            aggregate["treatment_brier_30"]
            < aggregate["control_brier_30"]
        ),
    }
    return {**checks, "passes": all(checks.values())}


def evaluate(rows: pd.DataFrame) -> dict:
    needed = {
        "season", "week", "gsis_id", "pos", "actual",
        "mean_projection", "fp_pass_l4_supported",
        *CONTROL_NUMERIC, *PASSING_FEATURES,
    }
    if missing := needed - set(rows.columns):
        raise ValueError(f"passing evaluation rows missing {sorted(missing)}")
    base = rows[
        rows.pos.eq("QB") & rows.week.between(5, 18)
        & rows.mean_projection.notna() & rows.actual.notna()
    ].copy()
    coverage = {
        season: float(base[base.season.eq(season)].fp_pass_l4_supported.mean())
        for season in HELD_OUT_SEASONS
    }
    eligible = base[base.fp_pass_l4_supported].copy()
    fold_frames: list[pd.DataFrame] = []
    fold_reports: list[dict] = []
    correlations: list[dict] = []
    for held_out in HELD_OUT_SEASONS:
        train = eligible[
            eligible.season.lt(held_out) & eligible.season.ge(2022)].copy()
        test = eligible[eligible.season.eq(held_out)].copy()
        if train.empty or test.empty:
            raise ValueError(f"same-season passing fold {held_out} is empty")
        control = _fit_predict(train, test, CONTROL_NUMERIC)
        treatment = _fit_predict(
            train, test, CONTROL_NUMERIC + PASSING_FEATURES)
        test["control_score"] = test.mean_projection + control[0]
        test["control_tail_20"], test["control_tail_30"] = control[1:]
        test["treatment_score"] = test.mean_projection + treatment[0]
        test["treatment_tail_20"], test["treatment_tail_30"] = treatment[1:]
        fold_frames.append(test)
        fold_reports.append(_score(test, str(held_out)))
        correlations.extend(_correlations(test, held_out))
    combined = pd.concat(fold_frames, ignore_index=True)
    aggregate = _score(combined, "aggregate")
    gate = passing_gate(aggregate, coverage)
    return {
        "disposition": (
            "same-season-passing-player-tail-passes"
            if gate["passes"]
            else "same-season-passing-player-tail-fails"
        ),
        "coverage": {str(key): value for key, value in coverage.items()},
        "folds": fold_reports,
        "aggregate": aggregate,
        "correlations": correlations,
        "gate": gate,
    }


def run(panel_id: str = PANEL_ID) -> dict:
    if panel_id != PANEL_ID:
        raise ValueError(f"same-season passing protocol is frozen to {PANEL_ID}")
    from ..bq import query_df
    from ..config import settings

    passing = query_df(f"SELECT * FROM `{settings.raw}.{TABLE}`")
    run_ids = set(passing.source_run_id.dropna().astype(str))
    if len(run_ids) != 1 or not next(iter(run_ids)).endswith(f"__{PLAN_NAME}"):
        raise ValueError("same-season passing table provenance is invalid")
    targets = query_df(f"""
        SELECT season, week, gsis_id, pos, mean_projection, salary,
               target_share_last, target_share_jump,
               snap_share_last, snap_share_jump,
               team_vacated_target_share, depth_rank,
               games_played_prior, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season BETWEEN 2022 AND 2025
          AND week BETWEEN 5 AND 18 AND pos = 'QB'
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={"panel_id": panel_id})
    report = evaluate(attach_same_season_passing(targets, passing))
    report["panel"] = panel_id
    report["source_run_id"] = next(iter(run_ids))
    print("FP_SAME_SEASON_PASSING_JSON=" + json.dumps(report, sort_keys=True))
    return report
