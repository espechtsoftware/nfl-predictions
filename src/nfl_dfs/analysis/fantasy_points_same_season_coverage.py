"""Frozen same-season last-four-week Fantasy Points coverage diagnostic."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .fantasy_points_coverage_fit import _score
from .fantasy_points_route_share import CONTROL_NUMERIC, _fit_predict
from ..ingest.fantasy_points_route import PANEL_ID
from ..ingest.fantasy_points_same_season_coverage import (
    DEFENSE_TABLE,
    RECEIVER_TABLE,
)


HELD_OUT_SEASONS = (2023, 2024, 2025)
COVERAGE_FEATURES = (
    "fp_cov_l4_matchup_tprr_edge",
    "fp_cov_l4_matchup_yprr_edge",
    "fp_cov_l4_matchup_fprr_edge",
    "fp_cov_l4_matchup_sep_edge",
)


def attach_same_season_coverage(
    targets: pd.DataFrame,
    receivers: pd.DataFrame,
    defenses: pd.DataFrame,
) -> pd.DataFrame:
    """Attach exact W-4:W-1 inputs and compute the four frozen edges."""
    target_needed = {"season", "week", "gsis_id", "pos", "opp"}
    receiver_needed = {
        "season", "target_week", "gsis_id", "resolution_status",
        "fp_cov_l4_supported", "source_week_start", "source_week_end",
        "overall_tprr", "overall_yprr", "overall_fprr", "overall_sep",
        "man_tprr", "man_yprr", "man_fprr", "man_sep",
        "zone_tprr", "zone_yprr", "zone_fprr", "zone_sep",
        "source_run_id",
    }
    defense_needed = {
        "season", "target_week", "team", "source_week_start",
        "source_week_end", "def_man_rate", "def_zone_rate", "source_run_id",
    }
    for label, frame, needed in (
        ("targets", targets, target_needed),
        ("receivers", receivers, receiver_needed),
        ("defenses", defenses, defense_needed),
    ):
        if missing := needed - set(frame.columns):
            raise ValueError(f"{label} missing {sorted(missing)}")

    source_receivers = receivers[
        receivers.resolution_status.eq("resolved")
        & receivers.gsis_id.notna()
    ].copy()
    if source_receivers.duplicated(["season", "target_week", "gsis_id"]).any():
        raise ValueError("same-season receiver source has duplicate player windows")
    if defenses.duplicated(["season", "target_week", "team"]).any():
        raise ValueError("same-season defense source has duplicate team windows")
    source_receivers = source_receivers.rename(columns={
        "target_week": "source_target_week",
        "source_week_start": "receiver_source_week_start",
        "source_week_end": "receiver_source_week_end",
        "source_run_id": "receiver_source_run_id",
    }).drop(columns="pos", errors="ignore")
    source_defenses = defenses.rename(columns={
        "target_week": "defense_target_week",
        "team": "source_opp",
        "source_week_start": "defense_source_week_start",
        "source_week_end": "defense_source_week_end",
        "source_run_id": "defense_source_run_id",
    })
    out = targets.copy()
    out = out.merge(
        source_receivers,
        left_on=["season", "week", "gsis_id"],
        right_on=["season", "source_target_week", "gsis_id"],
        how="left",
        validate="many_to_one",
    ).merge(
        source_defenses,
        left_on=["season", "week", "opp"],
        right_on=["season", "defense_target_week", "source_opp"],
        how="left",
        validate="many_to_one",
    )
    rates = out.def_man_rate + out.def_zone_rate
    man_weight = out.def_man_rate / rates
    zone_weight = out.def_zone_rate / rates
    supported = out.fp_cov_l4_supported.fillna(False).astype(bool) & rates.gt(0)
    for metric in ("tprr", "yprr", "fprr", "sep"):
        expected = (
            man_weight * out[f"man_{metric}"]
            + zone_weight * out[f"zone_{metric}"]
        )
        out[f"fp_cov_l4_matchup_{metric}_edge"] = (
            expected - out[f"overall_{metric}"]
        ).where(supported)
    out["fp_cov_l4_supported"] = (
        supported & out[list(COVERAGE_FEATURES)].notna().all(axis=1)
    )
    populated = out.fp_cov_l4_supported
    if populated.any():
        target_week = out.loc[populated, "week"].astype(int)
        target_season = out.loc[populated, "season"].astype(int)
        checks = (
            out.loc[populated, "source_target_week"].astype(int).eq(target_week)
            & out.loc[populated, "defense_target_week"].astype(int).eq(target_week)
            & out.loc[populated, "receiver_source_week_start"].astype(int).eq(
                target_week - 4)
            & out.loc[populated, "defense_source_week_start"].astype(int).eq(
                target_week - 4)
            & out.loc[populated, "receiver_source_week_end"].astype(int).eq(
                target_week - 1)
            & out.loc[populated, "defense_source_week_end"].astype(int).eq(
                target_week - 1)
            & out.loc[populated, "season"].astype(int).eq(target_season)
            & out.loc[populated, "source_opp"].eq(out.loc[populated, "opp"])
        )
        if not checks.all():
            raise ValueError("same-season coverage join violated PIT/opponent rules")
        if target_week.lt(5).any():
            raise ValueError("same-season coverage populated before target Week 5")
    return out


def _correlations(frame: pd.DataFrame, fold: int) -> list[dict]:
    residual = frame.actual.astype(float) - frame.mean_projection.astype(float)
    tail = frame.actual.ge(30).astype(int)
    return [{
        "fold": int(fold),
        "feature": feature,
        "rows": int(len(frame)),
        "spearman_projection_residual": float(
            frame[feature].astype(float).corr(residual, method="spearman")),
        "pearson_tail_30": float(
            frame[feature].astype(float).corr(tail.astype(float))),
    } for feature in COVERAGE_FEATURES]


def coverage_gate(aggregate: dict, coverage: dict[int, float]) -> dict:
    checks = {
        "coverage_at_least_30pct_each_fold": all(
            coverage.get(season, 0.0) >= 0.30 for season in HELD_OUT_SEASONS
        ),
        "aggregate_30_brier_improves": (
            aggregate["treatment_brier_30"]
            < aggregate["control_brier_30"]
        ),
    }
    return {**checks, "passes": all(checks.values())}


def evaluate(rows: pd.DataFrame) -> dict:
    base = rows[
        rows.pos.isin(["WR", "TE"])
        & rows.week.between(5, 18)
        & rows.mean_projection.notna()
        & rows.actual.notna()
    ].copy()
    coverage = {
        season: float(base[base.season.eq(season)].fp_cov_l4_supported.mean())
        for season in HELD_OUT_SEASONS
    }
    eligible = base[base.fp_cov_l4_supported].copy()
    fold_frames: list[pd.DataFrame] = []
    fold_reports: list[dict] = []
    correlations: list[dict] = []
    for held_out in HELD_OUT_SEASONS:
        train = eligible[eligible.season.lt(held_out)].copy()
        test = eligible[eligible.season.eq(held_out)].copy()
        if train.empty or test.empty:
            raise ValueError(f"same-season coverage fold {held_out} is empty")
        control = _fit_predict(train, test, CONTROL_NUMERIC)
        treatment = _fit_predict(
            train, test, CONTROL_NUMERIC + COVERAGE_FEATURES)
        test["control_score"] = test.mean_projection + control[0]
        test["control_tail_20"], test["control_tail_30"] = control[1:]
        test["treatment_score"] = test.mean_projection + treatment[0]
        test["treatment_tail_20"], test["treatment_tail_30"] = treatment[1:]
        fold_frames.append(test)
        fold_reports.append(_score(test, str(held_out)))
        correlations.extend(_correlations(test, held_out))
    combined = pd.concat(fold_frames, ignore_index=True)
    aggregate = _score(combined, "aggregate")
    gate = coverage_gate(aggregate, coverage)
    return {
        "disposition": (
            "same-season-coverage-player-tail-passes"
            if gate["passes"]
            else "same-season-coverage-player-tail-fails"
        ),
        "coverage": {str(key): value for key, value in coverage.items()},
        "folds": fold_reports,
        "aggregate": aggregate,
        "correlations": correlations,
        "gate": gate,
    }


def run(panel_id: str = PANEL_ID) -> dict:
    if panel_id != PANEL_ID:
        raise ValueError(f"same-season coverage protocol is frozen to {PANEL_ID}")
    from ..bq import query_df
    from ..config import settings

    receivers = query_df(f"SELECT * FROM `{settings.raw}.{RECEIVER_TABLE}`")
    defenses = query_df(f"SELECT * FROM `{settings.raw}.{DEFENSE_TABLE}`")
    targets = query_df(f"""
        SELECT season, week, gsis_id, pos, opp, mean_projection, salary,
               target_share_last, target_share_jump,
               snap_share_last, snap_share_jump,
               team_vacated_target_share, depth_rank,
               games_played_prior, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season BETWEEN 2022 AND 2025
          AND week BETWEEN 5 AND 18 AND pos IN ('WR', 'TE')
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={"panel_id": panel_id})
    report = evaluate(attach_same_season_coverage(
        targets, receivers, defenses))
    report["panel"] = panel_id
    print("FP_SAME_SEASON_COVERAGE_JSON=" + json.dumps(report, sort_keys=True))
    return report
