"""Strictly lagged Next Gen Stats receiving-tail diagnostic."""

from __future__ import annotations

import json
from collections.abc import Iterable

import numpy as np
import pandas as pd


PANEL_ID = "20260810-lockfix-e80-k1-8677d21"
SOURCE_SEASONS = (2019, 2021, 2022, 2023, 2024, 2025)
HELD_OUT_SEASONS = (2024, 2025)
HISTORY_SEASONS = tuple(range(2016, 2026))
NGS_FIELDS = (
    "avg_separation",
    "avg_cushion",
    "avg_intended_air_yards",
    "percent_share_of_intended_air_yards",
    "avg_yac_above_expectation",
)
NGS_FEATURES = tuple(f"ngs_{field}_l4" for field in NGS_FIELDS)
EXISTING_RECEIVER_FEATURES = (
    "separation_l4",
    "air_yards_share_l4",
    "adot_l8",
)
CONTROL_NUMERIC = (
    "proj",
    "salary",
    "target_share_last",
    "target_share_jump",
    "snap_share_last",
    "snap_share_jump",
    "team_vacated_target_share",
    "depth_rank",
    "games_played_prior",
    *EXISTING_RECEIVER_FEATURES,
)


def _weighted_recent(group: pd.DataFrame, field: str) -> float:
    values = pd.to_numeric(group[field], errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(values)
    if not finite.any():
        return np.nan
    weights = pd.to_numeric(group.targets, errors="coerce").to_numpy(
        dtype=float,
    )
    usable = finite & np.isfinite(weights) & (weights > 0)
    if usable.any() and float(weights[usable].sum()) > 0:
        return float(np.average(values[usable], weights=weights[usable]))
    return float(values[finite].mean())


def attach_strict_prior_ngs(
    targets: pd.DataFrame,
    ngs: pd.DataFrame,
) -> pd.DataFrame:
    """Attach target-weighted last-four NGS observations before each row."""
    target_needed = {"season", "week", "gsis_id"}
    ngs_needed = {
        "season", "season_type", "week", "player_gsis_id", "targets",
        *NGS_FIELDS,
    }
    if missing := target_needed - set(targets.columns):
        raise ValueError(f"targets missing {sorted(missing)}")
    if missing := ngs_needed - set(ngs.columns):
        raise ValueError(f"NGS receiving rows missing {sorted(missing)}")

    history = ngs[
        ngs.season_type.eq("REG")
        & pd.to_numeric(ngs.week, errors="coerce").gt(0)
        & ngs.player_gsis_id.notna()
    ].copy()
    history["season"] = pd.to_numeric(history.season, errors="raise").astype(int)
    history["week"] = pd.to_numeric(history.week, errors="raise").astype(int)
    history["player_gsis_id"] = history.player_gsis_id.astype(str)
    keys = ["season", "week", "player_gsis_id"]
    if history.duplicated(keys).any():
        raise ValueError("NGS receiving history has duplicate player-weeks")
    history["_order"] = history.season * 100 + history.week
    by_player = {
        str(player): group.sort_values("_order", kind="stable").reset_index(
            drop=True)
        for player, group in history.groupby("player_gsis_id", sort=False)
    }

    additions: list[dict] = []
    for row in targets[["season", "week", "gsis_id"]].itertuples(index=False):
        current = int(row.season) * 100 + int(row.week)
        player = by_player.get(str(row.gsis_id))
        result = {
            "ngs_source_season": np.nan,
            "ngs_source_week": np.nan,
            "ngs_prior_observations": 0,
            **{feature: np.nan for feature in NGS_FEATURES},
        }
        if player is not None:
            position = int(np.searchsorted(
                player._order.to_numpy(dtype=int), current, side="left",
            ))
            if position > 0:
                recent = player.iloc[max(0, position - 4):position]
                latest = recent.iloc[-1]
                result["ngs_source_season"] = int(latest.season)
                result["ngs_source_week"] = int(latest.week)
                result["ngs_prior_observations"] = int(len(recent))
                for field, feature in zip(NGS_FIELDS, NGS_FEATURES):
                    result[feature] = _weighted_recent(recent, field)
        additions.append(result)
    out = pd.concat(
        [targets.reset_index(drop=True), pd.DataFrame(additions)], axis=1,
    )
    source_order = (
        pd.to_numeric(out.ngs_source_season, errors="coerce") * 100
        + pd.to_numeric(out.ngs_source_week, errors="coerce")
    )
    target_order = out.season.astype(int) * 100 + out.week.astype(int)
    if source_order.ge(target_order).fillna(False).any():
        raise ValueError("NGS join used same-week or future information")
    return out


def _preprocessor(numeric: Iterable[str]):
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    return ColumnTransformer([
        (
            "numeric",
            Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]),
            list(numeric),
        ),
        (
            "position",
            Pipeline([
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore")),
            ]),
            ["pos"],
        ),
    ])


def _fit_predict(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric: tuple[str, ...],
) -> tuple[np.ndarray, dict[int, np.ndarray]]:
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import Pipeline

    columns = [*numeric, "pos"]
    regression = Pipeline([
        ("features", _preprocessor(numeric)),
        ("model", Ridge(alpha=10.0)),
    ])
    y_residual = train.actual.to_numpy(dtype=float) - train.proj.to_numpy(
        dtype=float,
    )
    regression.fit(train[columns], y_residual)
    tails: dict[int, np.ndarray] = {}
    for threshold in (20, 30):
        classifier = Pipeline([
            ("features", _preprocessor(numeric)),
            (
                "model",
                LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000),
            ),
        ])
        classifier.fit(
            train[columns], train.actual.ge(threshold).astype(int),
        )
        tails[threshold] = classifier.predict_proba(test[columns])[:, 1]
    return regression.predict(test[columns]), tails


def _score(frame: pd.DataFrame, label: str) -> dict:
    from sklearn.metrics import brier_score_loss, mean_absolute_error

    report = {
        "fold": label,
        "rows": int(len(frame)),
        "control_mae": float(mean_absolute_error(
            frame.actual, frame.control_score,
        )),
        "treatment_mae": float(mean_absolute_error(
            frame.actual, frame.treatment_score,
        )),
    }
    for threshold in (20, 30):
        truth = frame.actual.ge(threshold).astype(int)
        report[f"tail_{threshold}_rate"] = float(truth.mean())
        report[f"control_brier_{threshold}"] = float(
            brier_score_loss(truth, frame[f"control_tail_{threshold}"])
        )
        report[f"treatment_brier_{threshold}"] = float(
            brier_score_loss(truth, frame[f"treatment_tail_{threshold}"])
        )
    return report


def _gate(
    folds: list[dict],
    aggregate: dict,
    weighted_coverage: dict[int, float],
) -> dict:
    return {
        "at_least_1000_rows_each_fold": all(
            fold["rows"] >= 1000 for fold in folds
        ),
        "candidate_weighted_coverage_at_least_70pct": all(
            weighted_coverage.get(season, 0.0) >= 0.70
            for season in HELD_OUT_SEASONS
        ),
        "aggregate_brier_30_improves": (
            aggregate["treatment_brier_30"]
            < aggregate["control_brier_30"]
        ),
        "aggregate_brier_20_not_worse": (
            aggregate["treatment_brier_20"]
            <= aggregate["control_brier_20"]
        ),
        "aggregate_mae_not_worse": (
            aggregate["treatment_mae"] <= aggregate["control_mae"]
        ),
        "no_fold_brier_30_worse_over_1pct": all(
            fold["treatment_brier_30"]
            <= fold["control_brier_30"] * 1.01
            for fold in folds
        ),
    }


def evaluate_ngs(
    rows: pd.DataFrame,
    *,
    weighted_coverage: dict[int, float],
) -> dict:
    needed = {
        "season", "week", "gsis_id", "pos", "actual",
        "ngs_source_season", *CONTROL_NUMERIC, *NGS_FEATURES,
    }
    if missing := needed - set(rows.columns):
        raise ValueError(f"evaluation rows missing {sorted(missing)}")
    data = rows[
        rows.pos.isin(["WR", "TE"])
        & rows.actual.notna()
        & rows.proj.notna()
        & rows.ngs_source_season.notna()
    ].copy()
    if data.empty:
        raise ValueError("no complete NGS evaluation rows")

    predictions: list[pd.DataFrame] = []
    fold_scores: list[dict] = []
    for held_out in HELD_OUT_SEASONS:
        train = data[data.season.lt(held_out)]
        test = data[data.season.eq(held_out)]
        if train.empty or test.empty:
            raise ValueError(f"fold {held_out} has empty train or test rows")
        fold = test[[
            "season", "week", "gsis_id", "pos", "proj", "actual",
        ]].copy()
        for label, numeric in (
            ("control", CONTROL_NUMERIC),
            ("treatment", CONTROL_NUMERIC + NGS_FEATURES),
        ):
            residual, tails = _fit_predict(train, test, numeric)
            fold[f"{label}_score"] = test.proj.to_numpy(dtype=float) + residual
            for threshold, probabilities in tails.items():
                fold[f"{label}_tail_{threshold}"] = probabilities
        predictions.append(fold)
        fold_scores.append(_score(fold, str(held_out)))
    all_predictions = pd.concat(predictions, ignore_index=True)
    aggregate = _score(all_predictions, "aggregate")
    gate = _gate(fold_scores, aggregate, weighted_coverage)
    return {
        "panel_id": PANEL_ID,
        "folds": fold_scores,
        "aggregate": aggregate,
        "weighted_coverage": {
            str(key): float(value) for key, value in weighted_coverage.items()
        },
        "gate": gate,
        "disposition": (
            "ngs-receiver-tail-gate-passes" if all(gate.values())
            else "ngs-receiver-tail-gate-fails"
        ),
        "calibration_deciles": _calibration_deciles(all_predictions),
    }


def _calibration_deciles(frame: pd.DataFrame) -> list[dict]:
    pieces: list[pd.DataFrame] = []
    for threshold in (20, 30):
        for arm in ("control", "treatment"):
            probability = frame[f"{arm}_tail_{threshold}"].to_numpy(dtype=float)
            part = pd.DataFrame({
                "threshold": threshold,
                "arm": arm,
                "probability": probability,
                "actual_tail": frame.actual.ge(threshold).astype(int).to_numpy(),
            })
            part["decile"] = pd.qcut(
                part.probability.rank(method="first"), 10, labels=False,
                duplicates="drop",
            )
            pieces.append(part)
    joined = pd.concat(pieces, ignore_index=True)
    return joined.groupby(
        ["threshold", "arm", "decile"], observed=True,
    ).agg(
        rows=("actual_tail", "size"),
        mean_probability=("probability", "mean"),
        actual_rate=("actual_tail", "mean"),
    ).reset_index().to_dict("records")


def run(panel_id: str = PANEL_ID) -> dict:
    if panel_id != PANEL_ID:
        raise ValueError(f"NGS protocol is frozen to panel {PANEL_ID}")
    import nflreadpy as nfl

    from ..bq import query_df
    from ..config import settings

    completeness = query_df(f"""
        SELECT COUNT(DISTINCT FORMAT('%d-%d', season, week)) AS slates,
               COUNTIF(selected) AS selected_rows,
               COUNT(*) AS candidate_rows
        FROM `{settings.predictions}.replay_candidates_staging`
        WHERE panel_run_id = @panel_id
        """, params={"panel_id": panel_id}).iloc[0]
    if int(completeness.slates or 0) != 107:
        raise ValueError("corrected K1 panel is incomplete")
    if int(completeness.selected_rows or 0) != 107 * 80:
        raise ValueError("corrected K1 panel is not exact true-80")

    snapshots = query_df(f"""
      WITH used AS (
        SELECT season, week, player_id AS gsis_id,
               COUNT(*) AS candidate_appearances
        FROM `{settings.predictions}.replay_candidates_staging`,
             UNNEST(SPLIT(players, ',')) AS player_id
        WHERE panel_run_id = @panel_id
        GROUP BY season, week, player_id
      ), features AS (
        SELECT p.season, p.week, p.gsis_id, p.pos, p.proj, p.salary,
               p.target_share_last, p.target_share_jump,
               p.snap_share_last, p.snap_share_jump,
               p.team_vacated_target_share, p.depth_rank,
               p.games_played_prior, p.actual,
               f.separation_l4, f.air_yards_share_l4, f.adot_l8
        FROM `{settings.predictions}.slate_player_features` p
        LEFT JOIN `{settings.features}.player_week_training` f
          USING (season, week, gsis_id)
        WHERE p.panel_run_id = @panel_id
          AND p.season IN UNNEST(@seasons)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY p.season, p.week, p.gsis_id
          ORDER BY p.generated_at DESC
        ) = 1
      )
      SELECT f.*, u.candidate_appearances
      FROM features f JOIN used u USING (season, week, gsis_id)
      WHERE f.pos IN ('WR', 'TE')
      """, params={"panel_id": panel_id, "seasons": list(SOURCE_SEASONS)})
    ngs = nfl.load_nextgen_stats(
        seasons=list(HISTORY_SEASONS), stat_type="receiving",
    ).to_pandas()
    joined = attach_strict_prior_ngs(snapshots, ngs)
    weighted_coverage: dict[int, float] = {}
    for season in HELD_OUT_SEASONS:
        fold = joined[joined.season.eq(season)]
        total = float(fold.candidate_appearances.sum())
        covered = float(fold.loc[
            fold.ngs_source_season.notna(), "candidate_appearances"
        ].sum())
        weighted_coverage[season] = covered / total if total > 0 else 0.0
    report = evaluate_ngs(joined, weighted_coverage=weighted_coverage)
    report["source_audit"] = {
        "candidate_rows": int(completeness.candidate_rows or 0),
        "snapshot_rows": int(len(snapshots)),
        "rows_with_prior_ngs": int(joined.ngs_source_season.notna().sum()),
        "ngs_rows_downloaded": int(len(ngs)),
    }
    report["ngs_feature_missingness"] = {
        feature: float(joined[feature].isna().mean())
        for feature in NGS_FEATURES
    }
    print("NGS_RECEIVER_TAIL_JSON=" + json.dumps(report, sort_keys=True))
    return report
