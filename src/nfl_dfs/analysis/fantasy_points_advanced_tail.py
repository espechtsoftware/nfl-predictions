"""Frozen prior-season Fantasy Points Advanced player-tail diagnostic."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .fantasy_points_route_share import CONTROL_NUMERIC, _fit_predict
from ..ingest.fantasy_points_advanced import (
    EXPECTED_HASHES,
    FEATURE_COLUMNS,
    PANEL_ID,
    TABLE,
)


HELD_OUT_SEASONS = (2024, 2025)
QB_FEATURES = (
    "fp_adv_qb_cpoe",
    "fp_adv_qb_adot",
    "fp_adv_qb_deep_throw_rate",
    "fp_adv_qb_twt_rate",
    "fp_adv_qb_pressure_sack_rate",
    "fp_adv_qb_scramble_rate",
)
RECEIVING_FEATURES = (
    "fp_adv_rec_tprr",
    "fp_adv_rec_adot",
    "fp_adv_rec_air_yard_share",
    "fp_adv_rec_yprr",
    "fp_adv_rec_first_read_rate",
    "fp_adv_rec_xfp_per_route",
)
RUSHING_FEATURES = (
    "fp_adv_rush_i5_rate",
    "fp_adv_rush_mtf_per_att",
    "fp_adv_rush_yaco_per_att",
    "fp_adv_rush_stuff_rate",
)
GROUPS = {
    "QB": ({"QB"}, QB_FEATURES, ("passing",)),
    "RB": ({"RB"}, RECEIVING_FEATURES + RUSHING_FEATURES,
           ("receiving", "rushing")),
    "WR_TE": ({"WR", "TE"}, RECEIVING_FEATURES, ("receiving",)),
}


def _calibration_deciles(actual: np.ndarray, probability: np.ndarray) -> list[dict]:
    """Return stable equal-count calibration bins ordered by probability."""
    if len(actual) != len(probability) or not len(actual):
        raise ValueError("calibration inputs must be nonempty and aligned")
    frame = pd.DataFrame({
        "actual": np.asarray(actual, dtype=int),
        "probability": np.asarray(probability, dtype=float),
    }).sort_values("probability", kind="stable").reset_index(drop=True)
    if not np.isfinite(frame.probability.to_numpy()).all():
        raise ValueError("calibration probabilities must be finite")
    # A rank-based cut remains deterministic when a low-capacity model emits
    # tied probabilities and avoids silently dropping requested bins.
    frame["decile"] = np.floor(
        np.arange(len(frame), dtype=float) * min(10, len(frame)) / len(frame)
    ).astype(int)
    return [
        {
            "decile": int(decile) + 1,
            "rows": int(len(group)),
            "mean_probability": float(group.probability.mean()),
            "event_rate": float(group.actual.mean()),
        }
        for decile, group in frame.groupby("decile", sort=True)
    ]


def _score(frame: pd.DataFrame, label: str) -> dict:
    from sklearn.metrics import brier_score_loss, mean_absolute_error

    if frame.empty:
        raise ValueError(f"{label} has no evaluation rows")
    truth = frame.actual.to_numpy(dtype=float)
    report = {
        "fold": label,
        "rows": int(len(frame)),
        "control_mae": float(mean_absolute_error(truth, frame.control_score)),
        "treatment_mae": float(
            mean_absolute_error(truth, frame.treatment_score)),
    }
    for threshold in (20, 30):
        actual = frame.actual.ge(threshold).astype(int).to_numpy()
        report[f"events_{threshold}"] = int(actual.sum())
        report[f"tail_rate_{threshold}"] = float(actual.mean())
        for arm in ("control", "treatment"):
            probability = frame[f"{arm}_tail_{threshold}"].to_numpy(float)
            report[f"{arm}_brier_{threshold}"] = float(
                brier_score_loss(actual, probability))
            if threshold == 30:
                report[f"{arm}_calibration_deciles_30"] = (
                    _calibration_deciles(actual, probability))
    return report


def attach_previous_season_advanced(
    targets: pd.DataFrame,
    advanced: pd.DataFrame,
) -> pd.DataFrame:
    """Attach only source season N-1 to a target in season N."""
    target_needed = {"season", "gsis_id", "pos"}
    advanced_needed = {
        "season", "family", "gsis_id", "resolution_status", *FEATURE_COLUMNS,
    }
    if missing := target_needed - set(targets.columns):
        raise ValueError(f"targets missing {sorted(missing)}")
    if missing := advanced_needed - set(advanced.columns):
        raise ValueError(f"Advanced rows missing {sorted(missing)}")
    history = advanced[
        advanced.resolution_status.eq("resolved") & advanced.gsis_id.notna()
    ].copy()
    keys = ["season", "family", "gsis_id"]
    if history.duplicated(keys).any():
        raise ValueError("Advanced history has duplicate resolved player-seasons")
    history["season"] = pd.to_numeric(history.season, errors="raise").astype(int)
    out = targets.copy()
    out["_source_season"] = pd.to_numeric(
        out.season, errors="raise").astype(int) - 1
    for family in ("passing", "receiving", "rushing"):
        source = history[history.family.eq(family)].copy()
        source = source.rename(columns={"season": "_source_season"})
        family_features = [
            column for column in FEATURE_COLUMNS
            if source[column].notna().any()
        ]
        source[f"fp_adv_{family}_present"] = True
        keep = ["_source_season", "gsis_id", f"fp_adv_{family}_present",
                *family_features]
        out = out.merge(
            source[keep], on=["_source_season", "gsis_id"], how="left",
            validate="many_to_one")
        out[f"fp_adv_{family}_present"] = out[
            f"fp_adv_{family}_present"].fillna(False).astype(bool)
    for column in FEATURE_COLUMNS:
        if column not in out:
            out[column] = np.nan
    any_present = out[[
        "fp_adv_passing_present",
        "fp_adv_receiving_present",
        "fp_adv_rushing_present",
    ]].any(axis=1)
    source = out._source_season.where(any_present)
    target = pd.to_numeric(out.season, errors="raise").astype(int)
    if not source.dropna().eq(target[source.notna()] - 1).all():
        raise ValueError("Advanced join used a non-previous source season")
    out["_source_season"] = source
    return out.rename(columns={"_source_season": "fp_adv_source_season"})


def _available(rows: pd.DataFrame, families: tuple[str, ...]) -> pd.Series:
    mask = pd.Series(True, index=rows.index)
    for family in families:
        mask &= rows[f"fp_adv_{family}_present"].astype(bool)
    return mask


def advanced_gate(
    folds: list[dict],
    positions: list[dict],
    coverage: dict[tuple[int, str], float],
    aggregate: dict,
) -> dict:
    position_improvements = sum(
        row["treatment_brier_30"] < row["control_brier_30"]
        for row in positions)
    checks = {
        "coverage_at_least_60pct_each_position_fold": all(
            coverage.get((season, pos), 0.0) >= 0.60
            for season in HELD_OUT_SEASONS for pos in ("QB", "RB", "WR", "TE")
        ),
        "aggregate_30_brier_improves": (
            aggregate["treatment_brier_30"] < aggregate["control_brier_30"]),
        "at_least_two_position_groups_improve_30_brier": (
            position_improvements >= 2),
        "no_position_group_30_brier_worse_over_1pct": all(
            row["treatment_brier_30"] <= row["control_brier_30"] * 1.01
            for row in positions),
        "no_fold_30_brier_worse_over_1pct": all(
            row["treatment_brier_30"] <= row["control_brier_30"] * 1.01
            for row in folds),
    }
    checks["passes"] = all(checks.values())
    return checks


def evaluate_advanced(rows: pd.DataFrame) -> dict:
    needed = {
        "season", "week", "gsis_id", "pos", "actual",
        "mean_projection", *CONTROL_NUMERIC, *FEATURE_COLUMNS,
        "fp_adv_passing_present", "fp_adv_receiving_present",
        "fp_adv_rushing_present",
    }
    if missing := needed - set(rows.columns):
        raise ValueError(f"Advanced evaluation rows missing {sorted(missing)}")
    base = rows[
        rows.pos.isin(["QB", "RB", "WR", "TE"])
        & rows.actual.notna() & rows.mean_projection.notna()
    ].copy()
    coverage: dict[tuple[int, str], float] = {}
    coverage_rows: list[dict] = []
    missingness_rows: list[dict] = []
    for season in HELD_OUT_SEASONS:
        for pos in ("QB", "RB", "WR", "TE"):
            part = base[base.season.eq(season) & base.pos.eq(pos)]
            families = GROUPS[
                "WR_TE" if pos in {"WR", "TE"} else pos][2]
            covered = int(_available(part, families).sum())
            total = int(len(part))
            coverage[(season, pos)] = covered / total if total else 0.0
            coverage_rows.append({
                "season": season, "position": pos, "eligible_rows": total,
                "covered_rows": covered, "coverage": coverage[(season, pos)],
            })
    for season in HELD_OUT_SEASONS:
        for group, (positions, features, families) in GROUPS.items():
            part = base[
                base.season.eq(season)
                & base.pos.isin(positions)
                & _available(base, families)
            ]
            for feature in features:
                missing = int(part[feature].isna().sum())
                missingness_rows.append({
                    "season": season,
                    "position_group": group,
                    "feature": feature,
                    "rows": int(len(part)),
                    "missing_rows": missing,
                    "missing_rate": missing / len(part) if len(part) else 0.0,
                })

    predictions: list[pd.DataFrame] = []
    for held_out in HELD_OUT_SEASONS:
        for group, (positions, features, families) in GROUPS.items():
            eligible = base[
                base.pos.isin(positions) & _available(base, families)]
            train = eligible[
                eligible.season.lt(held_out) & eligible.season.ge(2023)]
            test = eligible[eligible.season.eq(held_out)]
            if train.empty or test.empty:
                raise ValueError(
                    f"Advanced {held_out} {group} has empty train or test rows")
            fold = test[[
                "season", "week", "gsis_id", "pos", "mean_projection", "actual",
            ]].copy()
            fold["group"] = group
            for arm, numeric in (
                ("control", CONTROL_NUMERIC),
                ("treatment", CONTROL_NUMERIC + tuple(features)),
            ):
                residual, tail20, tail30 = _fit_predict(train, test, numeric)
                fold[f"{arm}_score"] = (
                    test.mean_projection.to_numpy(dtype=float) + residual)
                fold[f"{arm}_tail_20"] = tail20
                fold[f"{arm}_tail_30"] = tail30
            predictions.append(fold)
    combined = pd.concat(predictions, ignore_index=True)
    fold_scores = [
        _score(combined[combined.season.eq(season)], str(season))
        for season in HELD_OUT_SEASONS
    ]
    position_scores = [
        _score(combined[combined.group.eq(group)], group)
        for group in GROUPS
    ]
    aggregate = _score(combined, "aggregate")
    gate = advanced_gate(fold_scores, position_scores, coverage, aggregate)
    return {
        "panel_id": PANEL_ID,
        "folds": fold_scores,
        "position_groups": position_scores,
        "aggregate": aggregate,
        "coverage": coverage_rows,
        "feature_missingness": missingness_rows,
        "gate": gate,
        "disposition": (
            "advanced-prior-player-tail-passes" if gate["passes"]
            else "advanced-prior-player-tail-fails"),
    }


def run(panel_id: str = PANEL_ID) -> dict:
    if panel_id != PANEL_ID:
        raise ValueError(f"Advanced protocol is frozen to panel {PANEL_ID}")
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
    advanced = query_df(f"""
        SELECT * EXCEPT(ingested_at)
        FROM `{settings.raw}.{TABLE}`
        """)
    wanted_hashes = {
        value for family in EXPECTED_HASHES.values() for value in family.values()
    }
    if set(advanced.source_sha256.dropna().astype(str)) != wanted_hashes:
        raise ValueError("Advanced table provenance does not match protocol")
    snapshots = query_df(f"""
        SELECT season, week, gsis_id, pos, mean_projection, salary,
               target_share_last, target_share_jump,
               snap_share_last, snap_share_jump,
               team_vacated_target_share, depth_rank,
               games_played_prior, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season BETWEEN 2023 AND 2025
          AND pos IN ('QB', 'RB', 'WR', 'TE')
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={"panel_id": panel_id})
    joined = attach_previous_season_advanced(snapshots, advanced)
    report = evaluate_advanced(joined)
    report["source_audit"] = {
        "advanced_rows": int(len(advanced)),
        "snapshot_rows": int(len(snapshots)),
        "source_hashes": sorted(wanted_hashes),
    }
    print("FP_ADVANCED_TAIL_JSON=" + json.dumps(report, sort_keys=True))
    return report
