"""Frozen prior-season receiver coverage-fit correlation diagnostic."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .fantasy_points_advanced_tail import _calibration_deciles
from .fantasy_points_route_share import CONTROL_NUMERIC, _fit_predict
from ..ingest.fantasy_points_coverage import (
    DEFENSE_HASHES,
    DEFENSE_TABLE,
    MAN_ZONE_HASHES,
    PANEL_ID,
    RECEIVER_TABLE,
    SEPARATION_HASHES,
)


HELD_OUT_SEASONS = (2024, 2025)
COVERAGE_FEATURES = (
    "fp_cov_matchup_tprr_edge",
    "fp_cov_matchup_yprr_edge",
    "fp_cov_matchup_fprr_edge",
    "fp_cov_matchup_sep_edge",
)


def attach_previous_season_coverage(
    targets: pd.DataFrame,
    receivers: pd.DataFrame,
    defenses: pd.DataFrame,
) -> pd.DataFrame:
    """Attach source season N-1 and compute the four frozen matchup edges."""
    target_needed = {"season", "week", "gsis_id", "pos", "opp"}
    receiver_needed = {
        "season", "gsis_id", "resolution_status", "overall_routes",
        "overall_tprr", "overall_yprr", "overall_fprr",
        "man_routes", "man_tprr", "man_yprr", "man_fprr",
        "zone_routes", "zone_tprr", "zone_yprr", "zone_fprr", "zone_sep",
        *{f"cover{shell}_{suffix}"
          for shell in (2, 3, 4, 6) for suffix in ("routes", "sep")},
    }
    defense_needed = {
        "season", "team", "def_man_rate", "def_zone_rate",
        *{f"def_cover{shell}_rate" for shell in (2, 3, 4, 6)},
    }
    for label, frame, needed in (
        ("targets", targets, target_needed),
        ("receivers", receivers, receiver_needed),
        ("defenses", defenses, defense_needed),
    ):
        if missing := needed - set(frame.columns):
            raise ValueError(f"{label} missing {sorted(missing)}")
    source_receivers = receivers[
        receivers.resolution_status.eq("resolved") & receivers.gsis_id.notna()
    ].copy()
    if source_receivers.duplicated(["season", "gsis_id"]).any():
        raise ValueError("receiver coverage source has duplicate player-seasons")
    if defenses.duplicated(["season", "team"]).any():
        raise ValueError("defense coverage source has duplicate team-seasons")
    source_receivers["target_season"] = source_receivers.season.astype(int) + 1
    source_receivers = source_receivers.rename(
        columns={"season": "fp_cov_receiver_source_season"})
    # Target position is the serving-time identity. The source position is
    # already constrained by the resolved GSIS key and would otherwise make
    # pandas suffix the target `pos` column during the merge.
    source_receivers = source_receivers.drop(columns="pos", errors="ignore")
    source_defenses = defenses.copy()
    source_defenses["target_season"] = source_defenses.season.astype(int) + 1
    source_defenses = source_defenses.rename(columns={
        "season": "fp_cov_defense_source_season", "team": "source_opp",
    })
    out = targets.copy()
    out["target_season"] = pd.to_numeric(out.season, errors="raise").astype(int)
    out = out.merge(
        source_receivers,
        on=["target_season", "gsis_id"], how="left", validate="many_to_one",
    ).merge(
        source_defenses,
        left_on=["target_season", "opp"],
        right_on=["target_season", "source_opp"],
        how="left", validate="many_to_one",
    )
    supported = (
        out.overall_routes.ge(200)
        & out.man_routes.ge(25)
        & out.zone_routes.ge(100)
    )
    man_zone_rates = out.def_man_rate + out.def_zone_rate
    man_weight = out.def_man_rate / man_zone_rates
    zone_weight = out.def_zone_rate / man_zone_rates
    for metric in ("tprr", "yprr", "fprr"):
        expected = (
            man_weight * out[f"man_{metric}"]
            + zone_weight * out[f"zone_{metric}"]
        )
        out[f"fp_cov_matchup_{metric}_edge"] = (
            expected - out[f"overall_{metric}"]
        ).where(supported & man_zone_rates.gt(0))

    shell_total = sum(out[f"def_cover{shell}_rate"] for shell in (2, 3, 4, 6))
    retained = pd.Series(0.0, index=out.index)
    weighted = pd.Series(0.0, index=out.index)
    for shell in (2, 3, 4, 6):
        available = (
            out[f"cover{shell}_routes"].ge(20)
            & out[f"cover{shell}_sep"].notna()
        )
        weight = out[f"def_cover{shell}_rate"].where(available, 0.0)
        retained = retained + weight
        weighted = weighted + weight * out[f"cover{shell}_sep"].fillna(0.0)
    out["fp_cov_retained_shell_weight"] = retained
    out["fp_cov_matchup_sep_edge"] = (
        weighted / retained - out.zone_sep
    ).where(supported & retained.gt(0) & retained.div(shell_total).ge(0.50))
    out["fp_cov_supported"] = out[list(COVERAGE_FEATURES)].notna().all(axis=1)
    populated = out.fp_cov_supported
    if populated.any():
        target_season = out.loc[populated, "season"].astype(int)
        if not out.loc[populated, "fp_cov_receiver_source_season"].astype(
                int).eq(target_season - 1).all():
            raise ValueError("receiver coverage join used non-prior season")
        if not out.loc[populated, "fp_cov_defense_source_season"].astype(
                int).eq(target_season - 1).all():
            raise ValueError("defense coverage join used non-prior season")
        if not out.loc[populated, "source_opp"].eq(
                out.loc[populated, "opp"]).all():
            raise ValueError("coverage join used the wrong opponent")
    return out.drop(columns="target_season")


def _correlations(frame: pd.DataFrame, fold: int) -> list[dict]:
    residual = frame.actual.astype(float) - frame.mean_projection.astype(float)
    tail = frame.actual.ge(30).astype(int)
    reports: list[dict] = []
    for feature in COVERAGE_FEATURES:
        values = frame[feature].astype(float)
        spearman = values.corr(residual, method="spearman")
        binary = values.corr(tail.astype(float), method="pearson")
        ranks = values.rank(method="first")
        quintile = pd.qcut(ranks, 5, labels=False, duplicates="drop")
        bands = pd.Series("middle", index=frame.index)
        bands[quintile.eq(0)] = "bottom"
        bands[quintile.eq(quintile.max())] = "top"
        band_rows = []
        for band in ("bottom", "middle", "top"):
            use = bands.eq(band)
            band_rows.append({
                "band": band,
                "rows": int(use.sum()),
                "event_rate_30": float(tail[use].mean()),
                "mean_projection_residual": float(residual[use].mean()),
                "mean_feature": float(values[use].mean()),
            })
        reports.append({
            "fold": int(fold),
            "feature": feature,
            "rows": int(len(frame)),
            "spearman_projection_residual": float(spearman),
            "pearson_tail_30": float(binary),
            "quintile_bands": band_rows,
        })
    return reports


def _score(frame: pd.DataFrame, label: str) -> dict:
    from sklearn.metrics import brier_score_loss, mean_absolute_error

    truth = frame.actual.to_numpy(dtype=float)
    report = {
        "fold": label,
        "rows": int(len(frame)),
        "control_mae": float(mean_absolute_error(truth, frame.control_score)),
        "treatment_mae": float(mean_absolute_error(
            truth, frame.treatment_score)),
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


def coverage_gate(
    folds: list[dict],
    aggregate: dict,
    coverage: dict[int, float],
) -> dict:
    checks = {
        "coverage_at_least_25pct_each_fold": all(
            coverage.get(season, 0.0) >= 0.25 for season in HELD_OUT_SEASONS),
        "aggregate_30_brier_improves": (
            aggregate["treatment_brier_30"] < aggregate["control_brier_30"]),
        "fold_30_brier_no_more_than_1pct_worse": all(
            fold["treatment_brier_30"]
            <= fold["control_brier_30"] * 1.01
            for fold in folds),
        "aggregate_20_brier_no_more_than_1pct_worse": (
            aggregate["treatment_brier_20"]
            <= aggregate["control_brier_20"] * 1.01),
    }
    return {**checks, "passes": all(checks.values())}


def evaluate(rows: pd.DataFrame) -> dict:
    base = rows[
        rows.pos.isin(["WR", "TE"])
        & rows.mean_projection.notna()
        & rows.actual.notna()
    ].copy()
    coverage = {
        season: float(base[base.season.eq(season)].fp_cov_supported.mean())
        for season in HELD_OUT_SEASONS
    }
    eligible = base[base.fp_cov_supported].copy()
    fold_frames: list[pd.DataFrame] = []
    fold_reports: list[dict] = []
    correlations: list[dict] = []
    for held_out in HELD_OUT_SEASONS:
        train = eligible[eligible.season.lt(held_out)].copy()
        test = eligible[eligible.season.eq(held_out)].copy()
        if train.empty or test.empty:
            raise ValueError(f"coverage-fit fold {held_out} is empty")
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
    gate = coverage_gate(fold_reports, aggregate, coverage)
    return {
        "disposition": (
            "coverage-fit-player-tail-passes" if gate["passes"]
            else "coverage-fit-player-tail-fails"),
        "coverage": {str(key): value for key, value in coverage.items()},
        "folds": fold_reports,
        "aggregate": aggregate,
        "correlations": correlations,
        "gate": gate,
    }


def coverage_tail_deltas(rows: pd.DataFrame, held_out: int) -> pd.DataFrame:
    """Construct the frozen score-free 30-point coverage contribution."""
    if held_out not in HELD_OUT_SEASONS:
        raise ValueError(f"unsupported coverage-fit held-out season {held_out}")
    needed = {
        "season", "week", "gsis_id", "pos", "opp", "actual",
        "mean_projection", "fp_cov_supported",
        "fp_cov_receiver_source_season", "fp_cov_defense_source_season",
        *CONTROL_NUMERIC, *COVERAGE_FEATURES,
    }
    if missing := needed - set(rows.columns):
        raise ValueError(f"coverage-fit rows missing {sorted(missing)}")
    eligible = rows[
        rows.pos.isin(["WR", "TE"])
        & rows.mean_projection.notna()
        & rows.fp_cov_supported.astype(bool)
    ].copy()
    train = eligible[
        eligible.season.lt(held_out) & eligible.actual.notna()
    ].copy()
    target = eligible[eligible.season.eq(held_out)].copy()
    if train.empty or target.empty:
        raise ValueError(
            f"coverage-fit season {held_out} has empty train or target rows")
    _, _, control_p30 = _fit_predict(train, target, CONTROL_NUMERIC)
    _, _, treatment_p30 = _fit_predict(
        train, target, CONTROL_NUMERIC + COVERAGE_FEATURES)
    out = target[[
        "season", "week", "gsis_id", "opp",
        "fp_cov_receiver_source_season", "fp_cov_defense_source_season",
    ]].copy()
    out["coverage_control_p30"] = control_p30
    out["coverage_treatment_p30"] = treatment_p30
    out["coverage_delta_30"] = (
        out.coverage_treatment_p30 - out.coverage_control_p30)
    numeric = out[[
        "coverage_control_p30", "coverage_treatment_p30",
        "coverage_delta_30",
    ]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("coverage-fit tail predictions are non-finite")
    target_season = out.season.astype(int)
    if not out.fp_cov_receiver_source_season.astype(int).eq(
            target_season - 1).all():
        raise ValueError("coverage-fit receiver signal used non-prior season")
    if not out.fp_cov_defense_source_season.astype(int).eq(
            target_season - 1).all():
        raise ValueError("coverage-fit defense signal used non-prior season")
    if out.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("coverage-fit signal has duplicate player-weeks")
    return out.reset_index(drop=True)


def load_coverage_tail_deltas(
    held_out: int,
    panel_id: str = PANEL_ID,
) -> pd.DataFrame:
    """Load and construct the one licensed coverage candidate signal."""
    if panel_id != PANEL_ID:
        raise ValueError(f"coverage-fit protocol is frozen to panel {PANEL_ID}")
    if held_out not in HELD_OUT_SEASONS:
        raise ValueError(f"unsupported coverage-fit held-out season {held_out}")
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
    receivers = query_df(f"SELECT * FROM `{settings.raw}.{RECEIVER_TABLE}`")
    defenses = query_df(f"SELECT * FROM `{settings.raw}.{DEFENSE_TABLE}`")
    receiver_hashes = set(
        receivers.man_zone_source_sha256.dropna().astype(str))
    receiver_hashes |= set(
        receivers.separation_source_sha256.dropna().astype(str))
    expected_receiver_hashes = (
        set(MAN_ZONE_HASHES.values()) | set(SEPARATION_HASHES.values()))
    if receiver_hashes != expected_receiver_hashes:
        raise ValueError("receiver coverage provenance does not match protocol")
    if set(defenses.source_sha256.dropna().astype(str)) != set(
            DEFENSE_HASHES.values()):
        raise ValueError("defense coverage provenance does not match protocol")
    snapshots = query_df(f"""
        SELECT season, week, gsis_id, pos, opp, mean_projection, salary,
               target_share_last, target_share_jump,
               snap_share_last, snap_share_jump,
               team_vacated_target_share, depth_rank,
               games_played_prior, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season BETWEEN 2023 AND @held_out AND pos IN ('WR', 'TE')
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={"panel_id": panel_id, "held_out": int(held_out)})
    joined = attach_previous_season_coverage(snapshots, receivers, defenses)
    return coverage_tail_deltas(joined, held_out)


def run(panel_id: str = PANEL_ID) -> dict:
    if panel_id != PANEL_ID:
        raise ValueError(f"coverage-fit protocol is frozen to panel {PANEL_ID}")
    from ..bq import query_df
    from ..config import settings

    receivers = query_df(f"SELECT * FROM `{settings.raw}.{RECEIVER_TABLE}`")
    defenses = query_df(f"SELECT * FROM `{settings.raw}.{DEFENSE_TABLE}`")
    receiver_hashes = set(receivers.man_zone_source_sha256.dropna().astype(str))
    receiver_hashes |= set(receivers.separation_source_sha256.dropna().astype(str))
    if receiver_hashes != set(MAN_ZONE_HASHES.values()) | set(SEPARATION_HASHES.values()):
        raise ValueError("receiver coverage provenance does not match protocol")
    if set(defenses.source_sha256.dropna().astype(str)) != set(DEFENSE_HASHES.values()):
        raise ValueError("defense coverage provenance does not match protocol")
    targets = query_df(f"""
        SELECT season, week, gsis_id, pos, opp, mean_projection, salary,
               target_share_last, target_share_jump,
               snap_share_last, snap_share_jump,
               team_vacated_target_share, depth_rank,
               games_played_prior, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season BETWEEN 2023 AND 2025 AND pos IN ('WR', 'TE')
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={"panel_id": panel_id})
    report = evaluate(attach_previous_season_coverage(
        targets, receivers, defenses))
    report["panel"] = panel_id
    print("FP_COVERAGE_FIT_JSON=" + json.dumps(report, sort_keys=True))
    return report
