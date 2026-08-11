"""Frozen same-season Advanced Receiving distribution diagnostic."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .fantasy_points_route_components import ensemble_crps
from .fantasy_points_route_share import CONTROL_NUMERIC, _preprocessor
from .served_tail_calibration import _pinball
from ..ingest.fantasy_points_advanced_receiving_support import (
    METRICS,
    PANEL_ID,
    PLAN_NAME,
    PLAN_SHA256,
    TABLE,
)


SOURCE_RUN_ID = (
    "20260811T155845Z__same-season-advanced-receiving-support-windows-v1"
)
SOURCE_ROWS = 34_227
SOURCE_HASHES = 108
HELD_OUT_SEASONS = (2023, 2024, 2025)
TARGET_WEEKS = tuple(range(5, 19))
ENSEMBLE_MEMBERS = 1_000
BOOTSTRAP_REPS = 10_000
BOOTSTRAP_SEED = 20_260_811
MIN_CUMULATIVE_ROUTES = 20.0
FULL_RECENCY_ROUTES = 80.0
TREATMENT_FEATURES = (
    "fp_adv_rec_blend_tprr",
    "fp_adv_rec_blend_yprr",
    "fp_adv_rec_blend_xfp_per_route",
)
SOURCE_TO_TREATMENT = {
    "fp_adv_rec_tprr": "fp_adv_rec_blend_tprr",
    "fp_adv_rec_yprr": "fp_adv_rec_blend_yprr",
    "fp_adv_rec_xfp_per_route": "fp_adv_rec_blend_xfp_per_route",
}


def build_blended_features(windows: pd.DataFrame) -> pd.DataFrame:
    """Collapse cumulative/last-four rows under the frozen route-weight law."""
    needed = {
        "season", "target_week", "window_type", "source_week_start",
        "source_week_end", "gsis_id", "resolution_status", "pos", "routes",
        "source_run_id", *METRICS,
    }
    if missing := needed - set(windows.columns):
        raise ValueError(f"Advanced Receiving windows missing {sorted(missing)}")
    rows = windows[
        windows.resolution_status.eq("resolved")
        & windows.gsis_id.notna()
        & windows.pos.isin(["WR", "TE"])
    ].copy()
    rows["season"] = pd.to_numeric(rows.season, errors="raise").astype(int)
    rows["target_week"] = pd.to_numeric(
        rows.target_week, errors="raise").astype(int)
    rows["source_week_end"] = pd.to_numeric(
        rows.source_week_end, errors="raise").astype(int)
    if not rows.source_week_end.eq(rows.target_week - 1).all():
        raise ValueError("Advanced Receiving source does not end at target W-1")
    if set(rows.source_run_id.astype(str)) != {SOURCE_RUN_ID}:
        raise ValueError("Advanced Receiving rows have the wrong source run")
    keys = ["season", "target_week", "gsis_id"]
    if rows.duplicated(keys + ["window_type"]).any():
        raise ValueError("Advanced Receiving windows have duplicate players")

    columns = [
        *keys, "pos", "routes", "source_week_start", "source_week_end",
        *SOURCE_TO_TREATMENT,
    ]
    cumulative = rows[rows.window_type.eq("cumulative")][columns].copy()
    if cumulative.duplicated(keys).any():
        raise ValueError("cumulative Advanced Receiving rows are not unique")
    cumulative = cumulative.rename(columns={
        "routes": "cumulative_routes",
        "source_week_start": "cumulative_source_week_start",
        "source_week_end": "cumulative_source_week_end",
        **{metric: f"{metric}_cumulative" for metric in SOURCE_TO_TREATMENT},
    })
    last_four = rows[rows.window_type.eq("last_four")][[
        *keys, "routes", "source_week_start", "source_week_end",
        *SOURCE_TO_TREATMENT,
    ]].copy()
    if last_four.duplicated(keys).any():
        raise ValueError("last-four Advanced Receiving rows are not unique")
    last_four = last_four.rename(columns={
        "routes": "last_four_routes",
        "source_week_start": "last_four_source_week_start",
        "source_week_end": "last_four_source_week_end",
        **{metric: f"{metric}_last_four" for metric in SOURCE_TO_TREATMENT},
    })
    out = cumulative.merge(last_four, on=keys, how="left", validate="one_to_one")
    cumulative_routes = pd.to_numeric(
        out.cumulative_routes, errors="coerce").to_numpy(float)
    finite_cumulative = np.isfinite(cumulative_routes)
    support = finite_cumulative & (cumulative_routes >= MIN_CUMULATIVE_ROUTES)
    for metric in SOURCE_TO_TREATMENT:
        support &= np.isfinite(pd.to_numeric(
            out[f"{metric}_cumulative"], errors="coerce").to_numpy(float))
    last_routes = pd.to_numeric(
        out.last_four_routes, errors="coerce").to_numpy(float)
    base_weight = np.where(
        np.isfinite(last_routes),
        np.clip(last_routes / FULL_RECENCY_ROUTES, 0.0, 1.0),
        0.0,
    )
    out["fp_adv_rec_recency_weight"] = base_weight
    out["fp_adv_rec_supported"] = support
    for source, destination in SOURCE_TO_TREATMENT.items():
        cumulative_value = pd.to_numeric(
            out[f"{source}_cumulative"], errors="coerce").to_numpy(float)
        last_value = pd.to_numeric(
            out[f"{source}_last_four"], errors="coerce").to_numpy(float)
        weight = np.where(np.isfinite(last_value), base_weight, 0.0)
        blended = (1.0 - weight) * cumulative_value + weight * np.where(
            np.isfinite(last_value), last_value, cumulative_value)
        out[destination] = np.where(support, blended, np.nan)
    if out.loc[out.fp_adv_rec_supported, list(TREATMENT_FEATURES)].isna().any(axis=None):
        raise ValueError("supported Advanced Receiving blend is non-finite")
    return out


def attach_blended_features(
    targets: pd.DataFrame,
    windows: pd.DataFrame,
) -> pd.DataFrame:
    needed = {"season", "week", "gsis_id", "pos"}
    if missing := needed - set(targets.columns):
        raise ValueError(f"Advanced Receiving targets missing {sorted(missing)}")
    features = build_blended_features(windows).rename(
        columns={"target_week": "week"})
    keep = [
        "season", "week", "gsis_id", "cumulative_source_week_end",
        "last_four_source_week_end", "cumulative_routes", "last_four_routes",
        "fp_adv_rec_recency_weight", "fp_adv_rec_supported",
        *TREATMENT_FEATURES,
    ]
    out = targets.merge(
        features[keep],
        on=["season", "week", "gsis_id"],
        how="left",
        validate="one_to_one",
    )
    out["fp_adv_rec_supported"] = out.fp_adv_rec_supported.fillna(False).astype(bool)
    supported = out.fp_adv_rec_supported
    if supported.any():
        if not out.loc[supported, "cumulative_source_week_end"].eq(
            out.loc[supported, "week"] - 1
        ).all():
            raise ValueError("Advanced Receiving target join violates PIT")
        if not out.loc[supported, "pos"].isin(["WR", "TE"]).all():
            raise ValueError("Advanced Receiving target join includes another position")
    return out


def _fit_arm(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import Pipeline

    columns = [*numeric, "pos"]
    model = Pipeline([
        ("features", _preprocessor(numeric)),
        ("model", Ridge(alpha=10.0)),
    ])
    train_actual = train.actual.to_numpy(dtype=float)
    train_mean = train.mean_projection.to_numpy(dtype=float)
    model.fit(train[columns], train_actual - train_mean)
    train_center = train_mean + model.predict(train[columns])
    test_center = (
        test.mean_projection.to_numpy(dtype=float) + model.predict(test[columns])
    )
    residual_errors = train_actual - train_center
    probabilities: list[np.ndarray] = []
    for threshold in (20, 30):
        labels = train.actual.ge(threshold).astype(int).to_numpy()
        if len(np.unique(labels)) != 2:
            raise ValueError(f"Advanced Receiving train has one {threshold}-point class")
        classifier = Pipeline([
            ("features", _preprocessor(numeric)),
            ("model", LogisticRegression(
                C=0.1, solver="lbfgs", max_iter=2000)),
        ])
        classifier.fit(train[columns], labels)
        probabilities.append(classifier.predict_proba(test[columns])[:, 1])

    quantile_levels = (np.arange(ENSEMBLE_MEMBERS, dtype=float) + 0.5) / ENSEMBLE_MEMBERS
    draws = np.empty((len(test), ENSEMBLE_MEMBERS), dtype=float)
    overall = np.quantile(residual_errors, quantile_levels)
    for pos in ("WR", "TE"):
        train_mask = train.pos.eq(pos).to_numpy()
        test_mask = test.pos.eq(pos).to_numpy()
        errors = residual_errors[train_mask]
        source = errors if len(errors) >= 200 else residual_errors
        draws[test_mask] = test_center[test_mask, None] + np.quantile(
            source, quantile_levels)[None, :]
    if not np.isfinite(draws).all():
        raise ValueError("Advanced Receiving predictive draws are non-finite")
    return test_center, draws, probabilities[0], probabilities[1]


def _row_metrics(
    test: pd.DataFrame,
    arm: str,
    center: np.ndarray,
    draws: np.ndarray,
    p20: np.ndarray,
    p30: np.ndarray,
) -> pd.DataFrame:
    actual = test.actual.to_numpy(dtype=float)
    out = pd.DataFrame(index=test.index)
    out[f"{arm}_mae"] = np.abs(actual - center)
    out[f"{arm}_crps"] = ensemble_crps(draws, actual)
    out[f"{arm}_p20"] = p20
    out[f"{arm}_p30"] = p30
    out[f"{arm}_brier20"] = (p20 - (actual >= 20)) ** 2
    out[f"{arm}_brier30"] = (p30 - (actual >= 30)) ** 2
    for level, label in ((0.90, "90"), (0.95, "95"), (0.99, "99")):
        quantile = np.quantile(draws, level, axis=1)
        out[f"{arm}_q{label}"] = quantile
        out[f"{arm}_pinball{label}"] = _pinball(actual, quantile, level)
        out[f"{arm}_exceed{label}"] = actual > quantile
    return out


def evaluate(rows: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    needed = {
        "season", "week", "gsis_id", "pos", "actual", "mean_projection",
        "fp_adv_rec_supported", *CONTROL_NUMERIC, *TREATMENT_FEATURES,
    }
    if missing := needed - set(rows.columns):
        raise ValueError(f"Advanced Receiving evaluation missing {sorted(missing)}")
    base = rows[
        rows.pos.isin(["WR", "TE"])
        & rows.week.isin(TARGET_WEEKS)
        & rows.actual.notna()
        & rows.mean_projection.notna()
    ].copy()
    eligible_rows = {
        str(season): int(base.season.eq(season).sum())
        for season in HELD_OUT_SEASONS
    }
    supported = base[base.fp_adv_rec_supported].copy()
    predictions: list[pd.DataFrame] = []
    for held_out in HELD_OUT_SEASONS:
        train = supported[supported.season.lt(held_out)].copy()
        test = supported[supported.season.eq(held_out)].copy()
        if train.empty or test.empty:
            raise ValueError(f"Advanced Receiving fold {held_out} is empty")
        fold = test[["season", "week", "gsis_id", "pos", "actual"]].copy()
        for arm, numeric in (
            ("control", CONTROL_NUMERIC),
            ("treatment", CONTROL_NUMERIC + TREATMENT_FEATURES),
        ):
            values = _fit_arm(train, test, numeric)
            metrics = _row_metrics(test, arm, *values)
            fold = pd.concat([fold, metrics], axis=1)
        predictions.append(fold)
    combined = pd.concat(predictions, ignore_index=True)
    report = summarize(combined)
    report["eligible_rows_by_fold"] = eligible_rows
    report["supported_rows_by_fold"] = {
        str(season): int(combined.season.eq(season).sum())
        for season in HELD_OUT_SEASONS
    }
    report["gate"] = diagnostic_gate(report)
    report["disposition"] = (
        "advanced-receiving-diagnostic-passes"
        if report["gate"]["passes"]
        else "advanced-receiving-diagnostic-fails"
    )
    return report, combined


def _score(part: pd.DataFrame, label: str) -> dict:
    if part.empty:
        raise ValueError(f"Advanced Receiving score cell {label} is empty")
    result = {
        "cell": label,
        "rows": int(len(part)),
        "events_20": int(part.actual.ge(20).sum()),
        "events_30": int(part.actual.ge(30).sum()),
    }
    for arm in ("control", "treatment"):
        for metric in (
            "mae", "crps", "brier20", "brier30",
            "pinball90", "pinball95", "pinball99",
        ):
            result[f"{arm}_{metric}"] = float(part[f"{arm}_{metric}"].mean())
        for label_q, nominal in (("90", 0.10), ("95", 0.05), ("99", 0.01)):
            rate = float(part[f"{arm}_exceed{label_q}"].mean())
            result[f"{arm}_exceed{label_q}"] = rate
            result[f"{arm}_calibration_abs{label_q}"] = abs(rate - nominal)
    return result


def _cluster_uncertainty(rows: pd.DataFrame) -> dict:
    metric_pairs = {
        "crps": ("control_crps", "treatment_crps"),
        "mae": ("control_mae", "treatment_mae"),
        "pinball95": ("control_pinball95", "treatment_pinball95"),
        "pinball99": ("control_pinball99", "treatment_pinball99"),
        "brier30": ("control_brier30", "treatment_brier30"),
    }
    clusters = rows[["season", "week"]].drop_duplicates().sort_values(
        ["season", "week"]).reset_index(drop=True)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    sampled = rng.integers(0, len(clusters), size=(BOOTSTRAP_REPS, len(clusters)))
    output: dict[str, dict] = {}
    for metric, (control, treatment) in metric_pairs.items():
        weekly = rows.assign(
            delta=rows[treatment].to_numpy(float) - rows[control].to_numpy(float)
        ).groupby(["season", "week"], sort=True).delta.mean().reindex(
            pd.MultiIndex.from_frame(clusters)).to_numpy(float)
        bootstrap = weekly[sampled].mean(axis=1)
        standard_deviation = float(np.std(weekly, ddof=1))
        output[metric] = {
            "treatment_minus_control": float(weekly.mean()),
            "cluster_weeks": int(len(weekly)),
            "ci95": [
                float(np.quantile(bootstrap, 0.025)),
                float(np.quantile(bootstrap, 0.975)),
            ],
            "mde_80pct_two_sided": float(
                (1.96 + 0.842) * standard_deviation / np.sqrt(len(weekly))
            ),
        }
    return output


def summarize(rows: pd.DataFrame) -> dict:
    folds = [_score(rows[rows.season.eq(season)], str(season))
             for season in HELD_OUT_SEASONS]
    positions = [_score(rows[rows.pos.eq(pos)], pos) for pos in ("WR", "TE")]
    aggregate = _score(rows, "aggregate")
    ratios = []
    for fold in folds:
        for label in ("95", "99"):
            ratios.append(
                fold[f"treatment_pinball{label}"] / fold[f"control_pinball{label}"]
            )
    return {
        "folds": folds,
        "positions": positions,
        "aggregate": aggregate,
        "equal_fold_upper_pinball_ratio": float(np.mean(ratios)),
        "uncertainty": _cluster_uncertainty(rows),
    }


def diagnostic_gate(report: dict) -> dict:
    aggregate = report["aggregate"]
    folds = report["folds"]
    supported_rows = sum(report["supported_rows_by_fold"].values())
    checks = {
        "supported_rows_at_least_6000": supported_rows >= 6_000,
        "events_30_at_least_100": aggregate["events_30"] >= 100,
        "aggregate_crps_ratio_at_most_0_995": (
            aggregate["treatment_crps"] <= 0.995 * aggregate["control_crps"]
        ),
        "equal_fold_q95_q99_pinball_ratio_at_most_0_995": (
            report["equal_fold_upper_pinball_ratio"] <= 0.995
        ),
        "q95_calibration_error_worsens_at_most_10pct": (
            aggregate["treatment_calibration_abs95"]
            <= 1.10 * aggregate["control_calibration_abs95"]
        ),
        "q99_calibration_error_worsens_at_most_10pct": (
            aggregate["treatment_calibration_abs99"]
            <= 1.10 * aggregate["control_calibration_abs99"]
        ),
        "aggregate_brier30_worsens_at_most_1pct": (
            aggregate["treatment_brier30"]
            <= 1.01 * aggregate["control_brier30"]
        ),
        "each_fold_brier30_worsens_at_most_2pct": all(
            fold["treatment_brier30"] <= 1.02 * fold["control_brier30"]
            for fold in folds
        ),
        "aggregate_mae_nonworsening": (
            aggregate["treatment_mae"] <= aggregate["control_mae"]
        ),
    }
    checks["passes"] = all(checks.values())
    return checks


def run(
    panel_id: str = PANEL_ID,
    *,
    output: str | Path | None = None,
) -> dict:
    if panel_id != PANEL_ID:
        raise ValueError(f"Advanced Receiving protocol is frozen to panel {PANEL_ID}")
    from ..bq import query_df
    from ..config import settings

    windows = query_df(f"""
        SELECT * EXCEPT(ingested_at)
        FROM `{settings.raw}.{TABLE}`
        """)
    if len(windows) != SOURCE_ROWS:
        raise ValueError(f"Advanced Receiving table has {len(windows)} rows")
    if set(windows.source_run_id.astype(str)) != {SOURCE_RUN_ID}:
        raise ValueError("Advanced Receiving table has the wrong run id")
    if windows.source_sha256.astype(str).nunique() != SOURCE_HASHES:
        raise ValueError("Advanced Receiving table has the wrong source hash count")
    targets = query_df(f"""
        SELECT season, week, gsis_id, pos, mean_projection, salary,
               target_share_last, target_share_jump,
               snap_share_last, snap_share_jump,
               team_vacated_target_share, depth_rank,
               games_played_prior, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season BETWEEN 2022 AND 2025
          AND week BETWEEN 5 AND 18
          AND pos IN ('WR', 'TE')
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={"panel_id": panel_id})
    joined = attach_blended_features(targets, windows)
    report, _ = evaluate(joined)
    report.update({
        "protocol": PLAN_NAME,
        "plan_sha256": PLAN_SHA256,
        "source_run_id": SOURCE_RUN_ID,
        "source_rows": SOURCE_ROWS,
        "source_hashes": SOURCE_HASHES,
        "panel_id": panel_id,
    })
    if output is not None:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("FP_ADVANCED_RECEIVING_DIAGNOSTIC_JSON=" + json.dumps(
        report, sort_keys=True))
    return report
