"""Audit the one frozen served-tail recalibration Stage B lineup replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.research import served_tail_lineup as stage_b  # noqa: E402


TREATMENT_PANEL = "20260811-lockfix-e80-k1-role12-tail1025-v1"


def _candidates(panel: str, *, promoted: bool) -> pd.DataFrame:
    table = "replay_candidates" if promoted else "replay_candidates_staging"
    eligibility = "AND research_eligible" if promoted else ""
    return query_df(f"""
        SELECT season, week, cand_ix, tag, all_tags, players, selected,
               selected_rank, actual_score, sim_mean, labels_complete,
               research_eligible, code_sha, config_hash, lever_env, seeds
        FROM `{settings.predictions}.{table}`
        WHERE panel_run_id = '{stage_b.panel_id(panel)}' {eligibility}
        """)


def _feature_invariance(source: str, treatment: str) -> dict:
    """Compare every persisted player input except run/code identity."""
    exact_fields = (
        "gsis_id", "name", "pos", "team", "opp", "game_id",
        "is_cold_start", "feature_missing", "model_member_spec",
    )
    numeric_fields = (
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
    material_checks = [
        f"s.{field} IS DISTINCT FROM t.{field}" for field in exact_fields
    ]
    material_checks.extend(
        f"((s.{field} IS NULL) != (t.{field} IS NULL) OR "
        f"(s.{field} IS NOT NULL AND t.{field} IS NOT NULL AND "
        f"ABS(s.{field} - t.{field}) > 1e-12))"
        for field in numeric_fields
    )
    max_numeric_delta = ", ".join(
        f"COALESCE(ABS(s.{field} - t.{field}), 0.0)"
        for field in numeric_fields
    )
    result = query_df(f"""
      WITH source_rows AS (
        SELECT *
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{stage_b.panel_id(source)}'
          AND research_eligible AND season IN (2023, 2024, 2025)
      ), treatment_rows AS (
        SELECT *
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{stage_b.panel_id(treatment)}'
          AND season IN (2023, 2024, 2025)
      ), paired AS (
        SELECT s.id AS source_id, t.id AS treatment_id,
               ({' OR '.join(material_checks)}) AS material_mismatch,
               GREATEST({max_numeric_delta}) AS max_numeric_abs_delta
        FROM source_rows s FULL OUTER JOIN treatment_rows t
        USING (season, week, id)
      )
      SELECT
        (SELECT COUNT(*) FROM source_rows) AS source_rows,
        (SELECT COUNT(*) FROM treatment_rows) AS treatment_rows,
        COUNTIF(source_id IS NULL) AS treatment_only_rows,
        COUNTIF(treatment_id IS NULL) AS source_only_rows,
        COUNTIF(source_id IS NOT NULL AND treatment_id IS NOT NULL
                AND material_mismatch) AS mismatch_rows,
        MAX(IF(source_id IS NOT NULL AND treatment_id IS NOT NULL,
               max_numeric_abs_delta, NULL)) AS max_numeric_abs_delta
      FROM paired
    """).iloc[0]
    report = {
        name: int(result.get(name) or 0)
        for name in result.index if name != "max_numeric_abs_delta"
    }
    report["max_numeric_abs_delta"] = float(
        result.max_numeric_abs_delta or 0.0)
    return report


def _candidate_audit(source: str, treatment: str) -> dict:
    result = query_df(f"""
      WITH source_rows AS (
        SELECT season, week, players, selected, actual_score, sim_mean
        FROM `{settings.predictions}.replay_candidates`
        WHERE panel_run_id = '{stage_b.panel_id(source)}'
          AND research_eligible AND season IN (2023, 2024, 2025)
      ), treatment_rows AS (
        SELECT season, week, players, selected, actual_score, sim_mean
        FROM `{settings.predictions}.replay_candidates_staging`
        WHERE panel_run_id = '{stage_b.panel_id(treatment)}'
          AND season IN (2023, 2024, 2025)
      ), paired AS (
        SELECT s.players AS source_players, t.players AS treatment_players,
               s.selected AS source_selected,
               t.selected AS treatment_selected,
               s.actual_score AS source_actual,
               t.actual_score AS treatment_actual,
               s.sim_mean AS source_mean, t.sim_mean AS treatment_mean
        FROM source_rows s FULL OUTER JOIN treatment_rows t
        USING (season, week, players)
      ), source_counts AS (
        SELECT season, week, COUNT(*) AS n
        FROM source_rows GROUP BY season, week
      ), treatment_counts AS (
        SELECT season, week, COUNT(*) AS n
        FROM treatment_rows GROUP BY season, week
      ), counts AS (
        SELECT COALESCE(s.season, t.season) AS season,
               COALESCE(s.week, t.week) AS week,
               s.n AS source_n, t.n AS treatment_n
        FROM source_counts s FULL OUTER JOIN treatment_counts t
        USING (season, week)
      )
      SELECT
        (SELECT COUNT(*) FROM source_rows) AS source_rows,
        (SELECT COUNT(*) FROM treatment_rows) AS treatment_rows,
        COUNTIF(source_players IS NOT NULL
                AND treatment_players IS NOT NULL) AS common_rows,
        COUNTIF(source_players IS NOT NULL
                AND treatment_players IS NULL) AS source_only_rows,
        COUNTIF(source_players IS NULL
                AND treatment_players IS NOT NULL) AS treatment_only_rows,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND ABS(source_actual - treatment_actual) > 1e-8)
                AS common_actual_mismatch,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND ABS(source_mean - treatment_mean)
                    > {stage_b.CANDIDATE_MEAN_ATOL})
                AS common_sim_mean_mismatch,
        MAX(IF(source_players IS NOT NULL AND treatment_players IS NOT NULL,
               ABS(source_mean - treatment_mean), NULL))
                AS max_common_sim_mean_abs_delta,
        COUNTIF(source_selected AND COALESCE(NOT treatment_selected, TRUE))
                AS selected_source_only,
        COUNTIF(treatment_selected AND COALESCE(NOT source_selected, TRUE))
                AS selected_treatment_only,
        (SELECT COUNT(*) FROM counts) AS paired_slates,
        (SELECT MIN(treatment_n - source_n) FROM counts) AS min_pool_delta,
        (SELECT MAX(treatment_n - source_n) FROM counts) AS max_pool_delta
      FROM paired
    """).iloc[0]
    report = {
        name: int(result.get(name) or 0)
        for name in result.index
        if name != "max_common_sim_mean_abs_delta"
    }
    report["max_common_sim_mean_abs_delta"] = float(
        result.max_common_sim_mean_abs_delta or 0.0
    )
    report["sim_mean_absolute_tolerance"] = stage_b.CANDIDATE_MEAN_ATOL
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("treatment", nargs="?", default=TREATMENT_PANEL)
    parser.add_argument("--source", default=stage_b.SOURCE_PANEL)
    parser.add_argument("--treatment-code-sha", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    source = _candidates(args.source, promoted=True)
    treatment = _candidates(args.treatment, promoted=False)
    failures = stage_b.validate_candidate_panel(
        "source", source, seasons=stage_b.SOURCE_SEASONS, promoted=True,
        expected_code_sha=stage_b.SOURCE_CODE_SHA,
    )
    failures.extend(stage_b.validate_candidate_panel(
        "treatment", treatment, seasons=stage_b.EVALUATION_SEASONS,
        promoted=False, expected_code_sha=args.treatment_code_sha,
    ))

    feature_audit: dict = {}
    candidate_audit: dict = {}
    scores: dict = {}
    if not source.empty and not treatment.empty:
        feature_audit = _feature_invariance(args.source, args.treatment)
        candidate_audit = _candidate_audit(args.source, args.treatment)
        source_eval = source[source.season.isin(stage_b.EVALUATION_SEASONS)]
        failures.extend(stage_b.mechanism_failures(
            source_eval, treatment, feature_audit, candidate_audit,
            treatment_code_sha=args.treatment_code_sha,
        ))
        scores = stage_b.comparison_report(source, treatment)

    decision = scores.get("tail_first_decision", {})
    decision["mechanism_valid"] = not failures
    decision["passes"] = bool(not failures and decision.get("passes"))
    if failures:
        disposition = "invalid"
    elif decision.get("passes"):
        disposition = "pass"
    elif decision.get("operator_review_required"):
        disposition = "operator-review"
    elif decision.get("tie_through_210"):
        disposition = "neutral"
    else:
        disposition = "reject"
    report = {
        "source": args.source,
        "treatment": args.treatment,
        "mode": "served-tail-scale-1.025-partial-panel",
        "feature_invariance": feature_audit,
        "candidate_audit": candidate_audit,
        "source_generator_summary": stage_b.generator_summary(source),
        "source_evaluation_generator_summary": stage_b.generator_summary(
            source[source.season.isin(stage_b.EVALUATION_SEASONS)]),
        "treatment_generator_summary": stage_b.generator_summary(treatment),
        **scores,
        "tail_first_decision": decision,
        "disposition": disposition,
        "failures": failures,
    }
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
