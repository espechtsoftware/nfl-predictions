"""Frozen strictly-prior Fantasy Points Defense PROE tail diagnostic."""

from __future__ import annotations

import json

import pandas as pd

from .fantasy_points_coverage_fit import _score
from .fantasy_points_route_share import CONTROL_NUMERIC, _fit_predict
from ..ingest.fantasy_points_defense_proe import (
    EXPECTED_HASHES,
    TABLE,
    attach_prior_l4,
)
from ..ingest.fantasy_points_route import PANEL_ID


HELD_OUT_SEASONS = (2023, 2024, 2025)
FEATURES = ("fp_def_proe_l4",)


def _correlations(frame: pd.DataFrame, fold: int) -> dict:
    residual = frame.actual.astype(float) - frame.mean_projection.astype(float)
    tail = frame.actual.ge(30).astype(int)
    return {
        "fold": int(fold),
        "rows": int(len(frame)),
        "spearman_projection_residual": float(
            frame.fp_def_proe_l4.astype(float).corr(
                residual, method="spearman")),
        "pearson_tail_30": float(
            frame.fp_def_proe_l4.astype(float).corr(tail.astype(float))),
    }


def defense_proe_gate(aggregate: dict, coverage: dict[int, float]) -> dict:
    checks = {
        "coverage_at_least_90pct_each_fold": all(
            coverage.get(season, 0.0) >= 0.90
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
        "mean_projection", "fp_def_proe_l4", "fp_def_proe_supported",
        *CONTROL_NUMERIC,
    }
    if missing := needed - set(rows.columns):
        raise ValueError(f"Defense PROE evaluation rows missing {sorted(missing)}")
    base = rows[
        rows.pos.isin(["QB", "WR", "TE"]) & rows.week.between(5, 18)
        & rows.mean_projection.notna() & rows.actual.notna()
    ].copy()
    coverage = {
        season: float(base[base.season.eq(season)].fp_def_proe_supported.mean())
        for season in HELD_OUT_SEASONS
    }
    eligible = base[base.fp_def_proe_supported].copy()
    fold_frames: list[pd.DataFrame] = []
    fold_reports: list[dict] = []
    correlations: list[dict] = []
    for held_out in HELD_OUT_SEASONS:
        train = eligible[
            eligible.season.lt(held_out) & eligible.season.ge(2022)].copy()
        test = eligible[eligible.season.eq(held_out)].copy()
        if train.empty or test.empty:
            raise ValueError(f"Defense PROE fold {held_out} is empty")
        control = _fit_predict(train, test, CONTROL_NUMERIC)
        treatment = _fit_predict(train, test, CONTROL_NUMERIC + FEATURES)
        test["control_score"] = test.mean_projection + control[0]
        test["control_tail_20"], test["control_tail_30"] = control[1:]
        test["treatment_score"] = test.mean_projection + treatment[0]
        test["treatment_tail_20"], test["treatment_tail_30"] = treatment[1:]
        fold_frames.append(test)
        fold_reports.append(_score(test, str(held_out)))
        correlations.append(_correlations(test, held_out))
    combined = pd.concat(fold_frames, ignore_index=True)
    aggregate = _score(combined, "aggregate")
    positions = {
        position: _score(combined[combined.pos.eq(position)], position)
        for position in ("QB", "WR", "TE")
    }
    gate = defense_proe_gate(aggregate, coverage)
    return {
        "disposition": (
            "defense-proe-pass-game-tail-passes"
            if gate["passes"]
            else "defense-proe-pass-game-tail-fails"
        ),
        "coverage": {str(key): value for key, value in coverage.items()},
        "folds": fold_reports,
        "aggregate": aggregate,
        "positions": positions,
        "correlations": correlations,
        "gate": gate,
    }


def run(panel_id: str = PANEL_ID) -> dict:
    if panel_id != PANEL_ID:
        raise ValueError(f"Defense PROE protocol is frozen to {PANEL_ID}")
    from ..bq import query_df
    from ..config import settings

    weekly = query_df(f"SELECT * FROM `{settings.raw}.{TABLE}`")
    hashes = set(weekly.source_sha256.dropna().astype(str))
    run_ids = set(weekly.source_run_id.dropna().astype(str))
    if hashes != set(EXPECTED_HASHES.values()) or len(run_ids) != 1:
        raise ValueError("Defense PROE table provenance is invalid")
    targets = query_df(f"""
        SELECT season, week, gsis_id, pos, opp AS defense,
               mean_projection, salary,
               target_share_last, target_share_jump,
               snap_share_last, snap_share_jump,
               team_vacated_target_share, depth_rank,
               games_played_prior, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season BETWEEN 2022 AND 2025
          AND week BETWEEN 5 AND 18 AND pos IN ('QB', 'WR', 'TE')
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={"panel_id": panel_id})
    report = evaluate(attach_prior_l4(targets, weekly))
    report["panel"] = panel_id
    report["source_run_id"] = next(iter(run_ids))
    print("FP_DEFENSE_PROE_JSON=" + json.dumps(report, sort_keys=True))
    return report
