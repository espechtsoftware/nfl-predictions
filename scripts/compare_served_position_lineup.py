"""Audit the frozen same-image control/treatment position-scale replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.research import served_position_lineup as experiment  # noqa: E402
from nfl_dfs.research.served_tail_lineup import (  # noqa: E402
    CANDIDATE_MEAN_ATOL,
    generator_summary,
    panel_id,
)


def _candidates(panel: str, *, promoted: bool) -> pd.DataFrame:
    table = "replay_candidates" if promoted else "replay_candidates_staging"
    eligibility = "AND research_eligible" if promoted else ""
    return query_df(f"""
        SELECT season, week, cand_ix, tag, all_tags, players, selected,
               selected_rank, actual_score, sim_mean, labels_complete,
               research_eligible, code_sha, config_hash, lever_env, seeds
        FROM `{settings.predictions}.{table}`
        WHERE panel_run_id = '{panel_id(panel)}' {eligibility}
        """)


def _feature_invariance(
    left: str,
    right: str,
    *,
    left_promoted: bool,
    right_promoted: bool,
    ignored_numeric_fields: tuple[str, ...] = (),
) -> dict:
    """Compare every persisted player input except run/code identity."""
    exact_fields = (
        "gsis_id", "name", "pos", "team", "opp", "game_id",
        "is_cold_start", "feature_missing", "model_member_spec",
    )
    all_numeric_fields = (
        "salary", "proj", "proj_tourney", "own_est", "consensus_div",
        "market_points", "model_points_pre", "mean_projection",
        "proj_p10", "proj_p50", "proj_p90", "proj_std",
        "target_share_last", "carry_share_last", "snap_share_last",
        "target_share_jump", "carry_share_jump", "snap_share_jump",
        "target_share_l4", "carry_share_l4", "snap_share_l4",
        "dk_points_l4", "implied_team_total", "spread", "game_total",
        "depth_rank", "depth_rank_delta", "team_vacated_target_share",
        "team_vacated_carry_share", "salary_delta_wow",
        "games_played_prior", "actual", "ensemble_point_0",
        "ensemble_point_1", "ensemble_point_2", "model_ensemble_size",
    )
    ignored = set(ignored_numeric_fields)
    unknown = ignored - set(all_numeric_fields)
    if unknown:
        raise ValueError(f"unknown ignored numeric fields: {sorted(unknown)}")
    numeric_fields = tuple(
        field for field in all_numeric_fields if field not in ignored)
    checks = [f"l.{field} IS DISTINCT FROM r.{field}" for field in exact_fields]
    checks.extend(
        f"((l.{field} IS NULL) != (r.{field} IS NULL) OR "
        f"(l.{field} IS NOT NULL AND r.{field} IS NOT NULL AND "
        f"ABS(l.{field} - r.{field}) > 1e-12))"
        for field in numeric_fields
    )
    maxima = ", ".join(
        f"COALESCE(ABS(l.{field} - r.{field}), 0.0)"
        for field in numeric_fields
    )
    left_eligibility = "AND research_eligible" if left_promoted else ""
    right_eligibility = "AND research_eligible" if right_promoted else ""
    row = query_df(f"""
      WITH left_rows AS (
        SELECT * FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{panel_id(left)}' {left_eligibility}
          AND season IN (2023, 2024, 2025)
      ), right_rows AS (
        SELECT * FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{panel_id(right)}' {right_eligibility}
          AND season IN (2023, 2024, 2025)
      ), paired AS (
        SELECT l.id AS left_id, r.id AS right_id,
               ({' OR '.join(checks)}) AS material_mismatch,
               GREATEST({maxima}) AS max_numeric_abs_delta
        FROM left_rows l FULL OUTER JOIN right_rows r
        USING (season, week, id)
      )
      SELECT
        (SELECT COUNT(*) FROM left_rows) AS left_rows,
        (SELECT COUNT(*) FROM right_rows) AS right_rows,
        COUNTIF(left_id IS NULL) AS right_only_rows,
        COUNTIF(right_id IS NULL) AS left_only_rows,
        COUNTIF(left_id IS NOT NULL AND right_id IS NOT NULL
                AND material_mismatch) AS mismatch_rows,
        MAX(IF(left_id IS NOT NULL AND right_id IS NOT NULL,
               max_numeric_abs_delta, NULL)) AS max_numeric_abs_delta
      FROM paired
    """).iloc[0]
    report = {
        name: int(row.get(name) or 0)
        for name in row.index if name != "max_numeric_abs_delta"
    }
    report["max_numeric_abs_delta"] = float(
        row.max_numeric_abs_delta or 0.0)
    report["ignored_numeric_fields"] = sorted(ignored)
    return report


def _candidate_audit(
    left: str,
    right: str,
    *,
    left_promoted: bool,
    right_promoted: bool,
) -> dict:
    left_table = "replay_candidates" if left_promoted \
        else "replay_candidates_staging"
    right_table = "replay_candidates" if right_promoted \
        else "replay_candidates_staging"
    left_eligibility = "AND research_eligible" if left_promoted else ""
    right_eligibility = "AND research_eligible" if right_promoted else ""
    row = query_df(f"""
      WITH left_rows AS (
        SELECT season, week, players, actual_score, sim_mean
        FROM `{settings.predictions}.{left_table}`
        WHERE panel_run_id = '{panel_id(left)}' {left_eligibility}
          AND season IN (2023, 2024, 2025)
      ), right_rows AS (
        SELECT season, week, players, actual_score, sim_mean
        FROM `{settings.predictions}.{right_table}`
        WHERE panel_run_id = '{panel_id(right)}' {right_eligibility}
          AND season IN (2023, 2024, 2025)
      ), paired AS (
        SELECT l.players AS left_players, r.players AS right_players,
               l.actual_score AS left_actual, r.actual_score AS right_actual,
               l.sim_mean AS left_mean, r.sim_mean AS right_mean
        FROM left_rows l FULL OUTER JOIN right_rows r
        USING (season, week, players)
      ), counts AS (
        SELECT COALESCE(l.season, r.season) AS season,
               COALESCE(l.week, r.week) AS week
        FROM (SELECT DISTINCT season, week FROM left_rows) l
        FULL OUTER JOIN (SELECT DISTINCT season, week FROM right_rows) r
        USING (season, week)
      )
      SELECT
        (SELECT COUNT(*) FROM left_rows) AS left_rows,
        (SELECT COUNT(*) FROM right_rows) AS right_rows,
        COUNTIF(left_players IS NOT NULL AND right_players IS NOT NULL)
            AS common_rows,
        COUNTIF(left_players IS NOT NULL AND right_players IS NULL)
            AS left_only_rows,
        COUNTIF(left_players IS NULL AND right_players IS NOT NULL)
            AS right_only_rows,
        COUNTIF(left_players IS NOT NULL AND right_players IS NOT NULL
                AND ABS(left_actual - right_actual) > 1e-8)
            AS common_actual_mismatch,
        COUNTIF(left_players IS NOT NULL AND right_players IS NOT NULL
                AND ABS(left_mean - right_mean) > {CANDIDATE_MEAN_ATOL})
            AS common_sim_mean_mismatch,
        MAX(IF(left_players IS NOT NULL AND right_players IS NOT NULL,
               ABS(left_mean - right_mean), NULL))
            AS max_common_sim_mean_abs_delta,
        (SELECT COUNT(*) FROM counts) AS paired_slates
      FROM paired
    """).iloc[0]
    report = {
        name: int(row.get(name) or 0)
        for name in row.index if name != "max_common_sim_mean_abs_delta"
    }
    report["max_common_sim_mean_abs_delta"] = float(
        row.max_common_sim_mean_abs_delta or 0.0)
    report["sim_mean_absolute_tolerance"] = CANDIDATE_MEAN_ATOL
    return report


def _source_control_reproduction(source: pd.DataFrame, control: pd.DataFrame) -> dict:
    source_best = source[source.selected].groupby(["season", "week"])[
        "actual_score"].max().rename("source_best")
    control_best = control[control.selected].groupby(["season", "week"])[
        "actual_score"].max().rename("control_best")
    paired = source_best.to_frame().join(control_best, how="outer")
    mismatch = paired.isna().any(axis=1) | (
        paired.source_best - paired.control_best).abs().gt(1e-8)
    return {
        "paired_slates": int(len(paired)),
        "weekly_max_mismatches": int(mismatch.sum()),
        "max_weekly_max_abs_delta": float(
            (paired.source_best - paired.control_best).abs().max() or 0.0),
    }


def _winner_position_contributions(panel: str) -> list[dict]:
    rows = query_df(f"""
      WITH winners AS (
        SELECT season, week, cand_ix, players, actual_score
        FROM `{settings.predictions}.replay_candidates_staging`
        WHERE panel_run_id = '{panel_id(panel)}' AND selected
          AND season IN (2023, 2024, 2025)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week ORDER BY actual_score DESC, cand_ix) = 1
      ), roster AS (
        SELECT season, week, cand_ix, actual_score, player_id
        FROM winners, UNNEST(SPLIT(players, ',')) AS player_id
      ), features AS (
        SELECT season, week, id, pos, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{panel_id(panel)}'
          AND season IN (2023, 2024, 2025)
      )
      SELECT r.season, r.week, ANY_VALUE(r.cand_ix) AS cand_ix,
             ANY_VALUE(r.actual_score) AS lineup_score,
             SUM(IF(f.pos = 'QB', f.actual, 0)) AS qb_points,
             SUM(IF(f.pos = 'RB', f.actual, 0)) AS rb_points,
             SUM(IF(f.pos = 'WR', f.actual, 0)) AS wr_points,
             SUM(IF(f.pos = 'TE', f.actual, 0)) AS te_points,
             SUM(IF(f.pos = 'DST', f.actual, 0)) AS dst_points,
             COUNTIF(f.id IS NULL) AS unresolved_players
      FROM roster r LEFT JOIN features f
        ON r.season = f.season AND r.week = f.week AND r.player_id = f.id
      GROUP BY r.season, r.week ORDER BY r.season, r.week
    """)
    return rows.to_dict("records")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=experiment.SOURCE_PANEL)
    parser.add_argument("--control", default=experiment.CONTROL_PANEL)
    parser.add_argument("--treatment", default=experiment.TREATMENT_PANEL)
    parser.add_argument("--experiment-code-sha", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    source = _candidates(args.source, promoted=True)
    control = _candidates(args.control, promoted=False)
    treatment = _candidates(args.treatment, promoted=False)
    source_eval = source[source.season.isin(experiment.EVALUATION_SEASONS)]
    failures = experiment.validate_candidate_panel(
        "source", source, seasons=experiment.SOURCE_SEASONS, promoted=True,
        expected_code_sha=experiment.SOURCE_CODE_SHA)
    for name, rows in (("control", control), ("treatment", treatment)):
        failures.extend(experiment.validate_candidate_panel(
            name, rows, seasons=experiment.EVALUATION_SEASONS, promoted=False,
            expected_code_sha=args.experiment_code_sha))

    audits: dict = {}
    scores: dict = {}
    contributions: dict = {}
    if not source.empty and not control.empty and not treatment.empty:
        audits = {
            "source_control_features": _feature_invariance(
                args.source, args.control,
                left_promoted=True, right_promoted=False),
            "control_treatment_features": _feature_invariance(
                args.control, args.treatment,
                left_promoted=False, right_promoted=False),
            "source_control_candidates": _candidate_audit(
                args.source, args.control,
                left_promoted=True, right_promoted=False),
            "control_treatment_candidates": _candidate_audit(
                args.control, args.treatment,
                left_promoted=False, right_promoted=False),
            "source_control_reproduction": _source_control_reproduction(
                source_eval, control),
        }
        failures.extend(experiment.mechanism_failures(
            source_eval, control, treatment,
            audits["source_control_features"],
            audits["control_treatment_features"],
            audits["source_control_candidates"],
            audits["control_treatment_candidates"],
            audits["source_control_reproduction"],
            experiment_code_sha=args.experiment_code_sha,
        ))
        if not failures:
            scores = experiment.comparison_report(source, control, treatment)
            contributions = {
                "control": _winner_position_contributions(args.control),
                "treatment": _winner_position_contributions(args.treatment),
            }

    decision = dict(scores.get("tail_first_decision", {}))
    decision["mechanism_valid"] = not failures
    decision["passes"] = bool(not failures and decision.get("passes"))
    if failures:
        disposition = "invalid"
    elif decision.get("passes"):
        disposition = "pass"
    elif decision.get("neutral"):
        disposition = "neutral"
    else:
        disposition = "reject"
    report = {
        "source": args.source,
        "control": args.control,
        "treatment": args.treatment,
        "mode": "served-position-scales-same-image-control-treatment",
        "position_spec": experiment.POSITION_SPEC,
        **audits,
        "source_generator_summary": generator_summary(source),
        "control_generator_summary": generator_summary(control),
        "treatment_generator_summary": generator_summary(treatment),
        **scores,
        "winner_position_contributions": contributions,
        "tail_first_decision": decision,
        "disposition": disposition,
        "failures": failures,
    }
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
