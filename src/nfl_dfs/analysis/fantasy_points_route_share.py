"""Frozen paid Fantasy Points true Route Share tail diagnostic."""

from __future__ import annotations

import json
from collections.abc import Iterable

import numpy as np
import pandas as pd

from ..ingest.fantasy_points_route import EXPECTED_HASHES, PANEL_ID, TABLE


SOURCE_SEASONS = (2022, 2023, 2024, 2025)
HELD_OUT_SEASONS = (2024, 2025)
CONTROL_NUMERIC = (
    "mean_projection",
    "salary",
    "target_share_last",
    "target_share_jump",
    "snap_share_last",
    "snap_share_jump",
    "team_vacated_target_share",
    "depth_rank",
    "games_played_prior",
)
ROUTE_FEATURES = (
    "fp_route_share_last",
    "fp_route_share_l4",
    "fp_route_share_jump",
    "fp_route_cross_season",
)


def attach_strict_prior_route(
    targets: pd.DataFrame,
    route: pd.DataFrame,
) -> pd.DataFrame:
    """Attach last/l4/jump Route Share from strictly earlier observations."""
    target_needed = {"season", "week", "gsis_id"}
    route_needed = {"season", "week", "gsis_id", "route_share"}
    if missing := target_needed - set(targets.columns):
        raise ValueError(f"targets missing {sorted(missing)}")
    if missing := route_needed - set(route.columns):
        raise ValueError(f"route history missing {sorted(missing)}")
    history = route.dropna(subset=["gsis_id", "route_share"]).copy()
    history["season"] = pd.to_numeric(history.season, errors="raise").astype(int)
    history["week"] = pd.to_numeric(history.week, errors="raise").astype(int)
    history["route_share"] = pd.to_numeric(
        history.route_share, errors="raise").astype(float)
    if not history.route_share.between(0, 1).all():
        raise ValueError("Route Share history outside [0, 1]")
    keys = ["season", "week", "gsis_id"]
    if history.duplicated(keys).any():
        raise ValueError("Route Share history has duplicate resolved player-weeks")
    history["_order"] = history.season * 100 + history.week
    by_player = {
        str(player): group.sort_values("_order", kind="stable").reset_index(
            drop=True)
        for player, group in history.groupby("gsis_id", sort=False)
    }
    additions: list[dict] = []
    for row in targets[["season", "week", "gsis_id"]].itertuples(index=False):
        current = int(row.season) * 100 + int(row.week)
        player = by_player.get(str(row.gsis_id))
        result = {
            "fp_route_source_season": np.nan,
            "fp_route_source_week": np.nan,
            "fp_route_prior_observations": 0,
            "fp_route_share_last": np.nan,
            "fp_route_share_l4": np.nan,
            "fp_route_share_jump": np.nan,
            "fp_route_cross_season": np.nan,
        }
        if player is not None:
            position = int(np.searchsorted(
                player._order.to_numpy(dtype=int), current, side="left"))
            if position > 0:
                recent = player.iloc[max(0, position - 4):position]
                latest = player.iloc[position - 1]
                result.update({
                    "fp_route_source_season": int(latest.season),
                    "fp_route_source_week": int(latest.week),
                    "fp_route_prior_observations": int(position),
                    "fp_route_share_last": float(latest.route_share),
                    "fp_route_share_l4": float(recent.route_share.mean()),
                    "fp_route_cross_season": int(
                        int(latest.season) < int(row.season)),
                })
                if position >= 2:
                    result["fp_route_share_jump"] = float(
                        latest.route_share - player.iloc[position - 2].route_share)
        additions.append(result)
    out = pd.concat(
        [targets.copy(), pd.DataFrame(additions, index=targets.index)], axis=1)
    source_order = (
        out.fp_route_source_season.fillna(-1).astype(int) * 100
        + out.fp_route_source_week.fillna(-1).astype(int))
    target_order = out.season.astype(int) * 100 + out.week.astype(int)
    if (source_order[out.fp_route_source_season.notna()]
            >= target_order[out.fp_route_source_season.notna()]).any():
        raise ValueError("Route Share join used same/future week")
    return out


def _preprocessor(numeric: Iterable[str]):
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    return ColumnTransformer([
        ("numeric", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), list(numeric)),
        ("position", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]), ["pos"]),
    ])


def _fit_predict(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import Pipeline

    columns = [*numeric, "pos"]
    regression = Pipeline([
        ("features", _preprocessor(numeric)),
        ("model", Ridge(alpha=10.0)),
    ])
    y_residual = (
        train.actual.to_numpy(dtype=float)
        - train.mean_projection.to_numpy(dtype=float))
    regression.fit(train[columns], y_residual)
    probabilities: list[np.ndarray] = []
    for threshold in (20, 30):
        classifier = Pipeline([
            ("features", _preprocessor(numeric)),
            ("model", LogisticRegression(
                C=0.1, solver="lbfgs", max_iter=2000)),
        ])
        classifier.fit(
            train[columns], train.actual.ge(threshold).astype(int).to_numpy())
        probabilities.append(classifier.predict_proba(test[columns])[:, 1])
    return regression.predict(test[columns]), *probabilities


def route_tail_deltas(rows: pd.DataFrame, held_out: int) -> pd.DataFrame:
    """Predict the frozen Route Share contribution to 30-point tails.

    Training is identical to the passing player diagnostic. Target outcomes
    are deliberately neither required nor read, which lets the same function
    construct point-in-time candidate objectives.
    """
    if held_out not in HELD_OUT_SEASONS:
        raise ValueError(f"unsupported Route Share held-out season {held_out}")
    needed = {
        "season", "week", "gsis_id", "pos", "actual",
        "mean_projection", "fp_route_source_season",
        "fp_route_source_week", "fp_route_share_last",
        *CONTROL_NUMERIC, *ROUTE_FEATURES,
    }
    if missing := needed - set(rows.columns):
        raise ValueError(f"Route Share rows missing {sorted(missing)}")
    eligible = rows[
        rows.pos.isin(["RB", "WR", "TE"])
        & rows.mean_projection.notna()
        & rows.fp_route_share_last.notna()
    ].copy()
    train = eligible[
        eligible.season.lt(held_out) & eligible.actual.notna()
    ].copy()
    target = eligible[eligible.season.eq(held_out)].copy()
    if train.empty or target.empty:
        raise ValueError(
            f"Route Share season {held_out} has empty train or target rows")
    _, _, control_p30 = _fit_predict(train, target, CONTROL_NUMERIC)
    _, _, treatment_p30 = _fit_predict(
        train, target, CONTROL_NUMERIC + ROUTE_FEATURES)
    out = target[[
        "season", "week", "gsis_id", "fp_route_source_season",
        "fp_route_source_week",
    ]].copy()
    out["route_control_p30"] = control_p30
    out["route_treatment_p30"] = treatment_p30
    out["route_delta_30"] = (
        out.route_treatment_p30 - out.route_control_p30)
    numeric = out[[
        "route_control_p30", "route_treatment_p30", "route_delta_30",
    ]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("Route Share tail predictions are non-finite")
    source_order = (
        out.fp_route_source_season.astype(int) * 100
        + out.fp_route_source_week.astype(int)
    )
    target_order = out.season.astype(int) * 100 + out.week.astype(int)
    if source_order.ge(target_order).any():
        raise ValueError("Route Share tail signal used non-prior information")
    if out.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("Route Share tail signal has duplicate player-weeks")
    return out.reset_index(drop=True)


def load_route_tail_deltas(
    held_out: int,
    panel_id: str = PANEL_ID,
) -> pd.DataFrame:
    """Load and construct the one preregistered candidate-generation signal."""
    if panel_id != PANEL_ID:
        raise ValueError(f"Route Share protocol is frozen to panel {PANEL_ID}")
    if held_out not in HELD_OUT_SEASONS:
        raise ValueError(f"unsupported Route Share held-out season {held_out}")
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
    if set(route.source_sha256.dropna().astype(str)) != set(
            EXPECTED_HASHES.values()):
        raise ValueError("Route Share table provenance does not match protocol")
    snapshots = query_df(f"""
        SELECT season, week, gsis_id, pos, mean_projection, salary,
               target_share_last, target_share_jump,
               snap_share_last, snap_share_jump,
               team_vacated_target_share, depth_rank,
               games_played_prior, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id
          AND research_eligible
          AND season IN UNNEST(@seasons)
          AND pos IN ('RB', 'WR', 'TE')
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={
            "panel_id": panel_id,
            "seasons": list(SOURCE_SEASONS),
        })
    joined = attach_strict_prior_route(snapshots, route)
    return route_tail_deltas(joined, held_out)


def _score(frame: pd.DataFrame, label: str) -> dict:
    from sklearn.metrics import brier_score_loss, mean_absolute_error

    truth = frame.actual.to_numpy(dtype=float)
    wr_te = frame.pos.isin(["WR", "TE"]).to_numpy()
    if not wr_te.any():
        raise ValueError(f"{label} has no WR/TE rows")
    report = {
        "fold": label,
        "rows": int(len(frame)),
        "control_mae": float(mean_absolute_error(truth, frame.control_score)),
        "treatment_mae": float(
            mean_absolute_error(truth, frame.treatment_score)),
    }
    for threshold in (20, 30):
        actual = frame.actual.ge(threshold).astype(int).to_numpy()
        report[f"tail_rate_{threshold}"] = float(actual.mean())
        for arm in ("control", "treatment"):
            probability = frame[f"{arm}_tail_{threshold}"].to_numpy(float)
            report[f"{arm}_brier_{threshold}"] = float(
                brier_score_loss(actual, probability))
            report[f"{arm}_wr_te_brier_{threshold}"] = float(
                brier_score_loss(actual[wr_te], probability[wr_te]))
    return report


def _calibration_deciles(frame: pd.DataFrame) -> list[dict]:
    stacked: list[pd.DataFrame] = []
    for arm in ("control", "treatment"):
        part = pd.DataFrame({
            "arm": arm,
            "probability": frame[f"{arm}_tail_30"].to_numpy(dtype=float),
            "actual_tail": frame.actual.ge(30).astype(int).to_numpy(),
        })
        part["decile"] = pd.qcut(
            part.probability.rank(method="first"), 10, labels=False,
            duplicates="drop")
        stacked.append(part)
    return pd.concat(stacked, ignore_index=True).groupby(
        ["arm", "decile"], observed=True).agg(
            rows=("actual_tail", "size"),
            mean_probability=("probability", "mean"),
            actual_rate=("actual_tail", "mean"),
        ).reset_index().to_dict("records")


def route_gate(
    folds: list[dict],
    aggregate: dict,
    coverage: dict[int, float],
) -> dict:
    checks = {
        "coverage_at_least_80pct_each_fold": all(
            coverage.get(season, 0.0) >= 0.80 for season in HELD_OUT_SEASONS),
        "aggregate_30_brier_improves": (
            aggregate["treatment_brier_30"]
            < aggregate["control_brier_30"]),
        "aggregate_wr_te_30_brier_improves": (
            aggregate["treatment_wr_te_brier_30"]
            < aggregate["control_wr_te_brier_30"]),
        "no_fold_30_brier_worse_over_1pct": all(
            fold["treatment_brier_30"]
            <= fold["control_brier_30"] * 1.01 for fold in folds),
    }
    checks["passes"] = all(checks.values())
    return checks


def evaluate_route(rows: pd.DataFrame) -> dict:
    needed = {
        "season", "week", "gsis_id", "pos", "actual",
        *CONTROL_NUMERIC, *ROUTE_FEATURES,
    }
    if missing := needed - set(rows.columns):
        raise ValueError(f"evaluation rows missing {sorted(missing)}")
    eligible = rows[
        rows.pos.isin(["RB", "WR", "TE"])
        & rows.actual.notna()
        & rows.mean_projection.notna()
    ].copy()
    coverage: dict[int, float] = {}
    coverage_rows: list[dict] = []
    for season in HELD_OUT_SEASONS:
        fold = eligible[eligible.season.eq(season)]
        covered = int(fold.fp_route_share_last.notna().sum())
        total = int(len(fold))
        coverage[season] = covered / total if total else 0.0
        coverage_rows.append({
            "season": season, "eligible_rows": total,
            "covered_rows": covered, "coverage": coverage[season],
        })
    data = eligible[eligible.fp_route_share_last.notna()].copy()
    predictions: list[pd.DataFrame] = []
    fold_scores: list[dict] = []
    for held_out in HELD_OUT_SEASONS:
        train = data[data.season.lt(held_out)]
        test = data[data.season.eq(held_out)]
        if train.empty or test.empty:
            raise ValueError(f"fold {held_out} has empty train or test rows")
        fold = test[[
            "season", "week", "gsis_id", "pos", "mean_projection", "actual",
        ]].copy()
        for arm, numeric in (
            ("control", CONTROL_NUMERIC),
            ("treatment", CONTROL_NUMERIC + ROUTE_FEATURES),
        ):
            residual, tail20, tail30 = _fit_predict(train, test, numeric)
            fold[f"{arm}_score"] = (
                test.mean_projection.to_numpy(dtype=float) + residual)
            fold[f"{arm}_tail_20"] = tail20
            fold[f"{arm}_tail_30"] = tail30
        predictions.append(fold)
        fold_scores.append(_score(fold, str(held_out)))
    combined = pd.concat(predictions, ignore_index=True)
    aggregate = _score(combined, "aggregate")
    gate = route_gate(fold_scores, aggregate, coverage)
    return {
        "panel_id": PANEL_ID,
        "folds": fold_scores,
        "aggregate": aggregate,
        "coverage": coverage_rows,
        "gate": gate,
        "disposition": (
            "route-share-player-tail-passes" if gate["passes"]
            else "route-share-player-tail-fails"),
        "calibration_deciles_30": _calibration_deciles(combined),
    }


def run(panel_id: str = PANEL_ID) -> dict:
    if panel_id != PANEL_ID:
        raise ValueError(f"Route Share protocol is frozen to panel {PANEL_ID}")
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
    if set(route.source_sha256.dropna().astype(str)) != set(
            EXPECTED_HASHES.values()):
        raise ValueError("Route Share table provenance does not match protocol")
    snapshots = query_df(f"""
        SELECT season, week, gsis_id, pos, mean_projection, salary,
               target_share_last, target_share_jump,
               snap_share_last, snap_share_jump,
               team_vacated_target_share, depth_rank,
               games_played_prior, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id
          AND research_eligible
          AND season IN UNNEST(@seasons)
          AND pos IN ('RB', 'WR', 'TE')
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={"panel_id": panel_id, "seasons": list(SOURCE_SEASONS)})
    joined = attach_strict_prior_route(snapshots, route)
    report = evaluate_route(joined)
    report["source_audit"] = {
        "route_rows": int(len(route)),
        "snapshot_rows": int(len(snapshots)),
        "rows_with_prior_route": int(joined.fp_route_share_last.notna().sum()),
        "source_hashes": sorted(EXPECTED_HASHES.values()),
    }
    report["route_feature_missingness"] = {
        feature: float(joined[feature].isna().mean())
        for feature in ROUTE_FEATURES
    }
    print("FP_ROUTE_SHARE_JSON=" + json.dumps(report, sort_keys=True))
    return report
