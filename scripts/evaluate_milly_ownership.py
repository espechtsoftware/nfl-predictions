"""Walk-forward diagnostic for the contest-aware Milly ownership target."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.backtest.field import naive_ownership  # noqa: E402
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.models import ownership as generic_ownership  # noqa: E402
from nfl_dfs.research.milly_ownership import (  # noqa: E402
    TARGET, build_features, diagnostic_gate, join_milly_truth,
    prediction_metrics, predict_contest_model, select_main_milly_contests,
    train_contest_model,
)


SOURCE_PANEL = "20260808-e80-k1-c616390"
FOLDS = (2023, 2024, 2025)


def _ownership_rows() -> pd.DataFrame:
    return query_df(f"""
      SELECT season, week, contest_id, contest_name, display_name,
             roster_position, pct_drafted
      FROM `{settings.raw}.contest_ownership`
      WHERE season BETWEEN 2022 AND 2025
      QUALIFY ROW_NUMBER() OVER (
        PARTITION BY season, week, contest_id, display_name
        ORDER BY imported_at DESC
      ) = 1
    """)


def _feature_rows(panel: str) -> pd.DataFrame:
    return query_df(f"""
      SELECT id, name, pos, team, season, week, salary, proj,
             implied_team_total, spread, game_total, is_cold_start,
             depth_rank, depth_rank_delta, target_share_last,
             carry_share_last, snap_share_last, target_share_jump,
             carry_share_jump, snap_share_jump, target_share_l4,
             carry_share_l4, snap_share_l4, dk_points_l4,
             team_vacated_target_share, team_vacated_carry_share,
             salary_delta_wow, games_played_prior
      FROM `{settings.predictions}.slate_player_features`
      WHERE panel_run_id = '{panel}' AND research_eligible
        AND season BETWEEN 2022 AND 2025
    """)


def _add_naive_weights(features: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    out["naive_weight"] = np.nan
    for _, slate in out.groupby(["season", "week"], sort=False):
        proxy = slate[["pos", "proj", "salary"]].copy()
        out.loc[slate.index, "naive_weight"] = naive_ownership(proxy)
    if out.naive_weight.isna().any():
        raise ValueError("naive ownership proxy is incomplete")
    return out


def _naive_predictions(train: pd.DataFrame,
                       holdout: pd.DataFrame) -> np.ndarray:
    # Convert current within-position weights to percentage ownership using
    # only earlier-season Milly roster mass.  No held-out ownership value is
    # used for calibration.
    mass = (train.groupby(["season", "week", "position"])[TARGET].sum()
            .groupby("position").mean())
    missing = sorted(set(holdout.position) - set(mass.index))
    if missing:
        raise ValueError(f"no prior-season position mass for {missing}")
    return (holdout.naive_weight
            * holdout.position.map(mass).astype(float)).to_numpy()


def _position_calibration(frame: pd.DataFrame, prediction: np.ndarray,
                          method: str, season: int) -> list[dict]:
    scored = frame[["season", "week", "position", TARGET]].copy()
    scored["prediction"] = prediction
    rows: list[dict] = []
    for pos, group in scored.groupby("position"):
        slate_sums = group.groupby(["season", "week"])[
            [TARGET, "prediction"]].sum()
        rows.append({
            "season": season,
            "method": method,
            "position": str(pos),
            "rows": int(len(group)),
            "actual_mean": float(group[TARGET].mean()),
            "prediction_mean": float(group.prediction.mean()),
            "mean_bias": float((group.prediction - group[TARGET]).mean()),
            "actual_slate_mass_mean": float(slate_sums[TARGET].mean()),
            "prediction_slate_mass_mean": float(
                slate_sums.prediction.mean()),
        })
    return rows


def evaluate(panel: str = SOURCE_PANEL) -> dict:
    ownership = _ownership_rows()
    contests = select_main_milly_contests(ownership)
    observed = set(zip(contests.season.astype(int), contests.week.astype(int)))
    expected = {(season, week) for season in range(2022, 2026)
                for week in range(1, 19)}
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise ValueError(
            f"main Milly contract is not 72 regular-season slates; "
            f"missing={missing}, extra={extra}")

    features = _add_naive_weights(build_features(_feature_rows(panel)))
    joined, coverage = join_milly_truth(features, ownership, contests)
    joined = build_features(joined)
    generic_frame = generic_ownership.training_frame()
    metric_rows: list[dict] = []
    calibration_rows: list[dict] = []
    scored_folds: list[pd.DataFrame] = []

    for season in FOLDS:
        train = joined[joined.season.lt(season)].copy()
        holdout = joined[joined.season.eq(season)].copy()
        if train.empty or holdout.empty:
            raise ValueError(f"empty ownership fold for {season}")

        contest_booster = train_contest_model(train)
        contest_pred = predict_contest_model(contest_booster, holdout)

        generic_train = generic_frame[generic_frame.season.lt(season)]
        if len(generic_train) < 1000:
            raise ValueError(
                f"all-contest comparator has only {len(generic_train)} "
                f"prior rows for {season}")
        generic_booster = generic_ownership.train(generic_train)
        generic_input = pd.DataFrame({
            "season": holdout.season,
            "week": holdout.week,
            "position": holdout.position,
            "salary": holdout.salary,
            "proj_points": holdout.proj_points,
        })
        generic_pred = generic_ownership.predict_ownership(
            generic_booster, generic_input)
        naive_pred = _naive_predictions(train, holdout)

        scored = holdout[["season", "week", "position", TARGET]].copy()
        for method, pred in (
            ("contest_aware", contest_pred),
            ("all_contest", generic_pred),
            ("naive", naive_pred),
        ):
            metric_rows.append({
                "season": season, "method": method,
                **prediction_metrics(holdout, pred),
            })
            calibration_rows.extend(
                _position_calibration(holdout, np.asarray(pred), method, season))
            scored[method] = np.asarray(pred)
        scored_folds.append(scored)

    all_scored = pd.concat(scored_folds, ignore_index=True)
    for method in ("contest_aware", "all_contest", "naive"):
        metric_rows.append({
            "season": "aggregate", "method": method,
            **prediction_metrics(all_scored, all_scored[method]),
        })
    metrics_frame = pd.DataFrame(metric_rows)
    aggregate_coverage = float(coverage.matched_mass.sum() / coverage.own_sum.sum())
    gate = diagnostic_gate(metrics_frame, aggregate_coverage)

    coverage_rows = []
    for season, group in coverage.groupby("season"):
        coverage_rows.append({
            "season": int(season),
            "slates": int(len(group)),
            "truth_mass": float(group.own_sum.sum()),
            "matched_mass": float(group.matched_mass.sum()),
            "mass_coverage": float(group.matched_mass.sum() / group.own_sum.sum()),
            "min_week_mass_coverage": float(group.mass_coverage.min()),
            "matched_rows": int(group.matched_rows.sum()),
        })
    return {
        "source_panel": panel,
        "data_contract": {
            "selected_contests": int(len(contests)),
            "seasons": [2022, 2023, 2024, 2025],
            "held_out_folds": list(FOLDS),
            "contest_field_size_min": int(contests.field_size.min()),
            "contest_field_size_max": int(contests.field_size.max()),
            "contest_ownership_mass_min": float(contests.own_sum.min()),
            "contest_ownership_mass_max": float(contests.own_sum.max()),
        },
        "coverage": coverage_rows,
        "aggregate_mass_coverage": aggregate_coverage,
        "metrics": metric_rows,
        "position_calibration": calibration_rows,
        "gate": gate,
        "disposition": "pass" if gate["passes"] else "reject",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", default=SOURCE_PANEL)
    parser.add_argument("--output")
    args = parser.parse_args()
    if not args.panel.replace("-", "").replace("_", "").isalnum():
        parser.error("invalid panel id")
    report = evaluate(args.panel)
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
