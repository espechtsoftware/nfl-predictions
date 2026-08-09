"""Mechanism and tail audit for the frozen K=1 Milly-ownership fade arm."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.research.panel_compare import (  # noqa: E402
    metrics, slate_scores, tail_first_gate,
)


SOURCE = "20260808-e80-k1-c616390"
THRESHOLDS = (187, 194, 200, 210, 220, 230, 240)


def _panel_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"invalid panel id {value!r}")
    return value


def _load(panel: str, promoted: bool) -> pd.DataFrame:
    table = "replay_candidates" if promoted else "replay_candidates_staging"
    eligibility = "AND research_eligible" if promoted else ""
    return query_df(f"""
      SELECT season, week, cand_ix, players, selected, actual_score,
             code_sha, config_hash, lever_env, seeds
      FROM `{settings.predictions}.{table}`
      WHERE panel_run_id = '{_panel_id(panel)}' {eligibility}
    """)


def _levers(value: object) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in str(value or "").split(","):
        if "=" in item:
            key, val = item.split("=", 1)
            out[key.strip()] = val.strip()
    return out


def _feature_audit(source: str, treatment: str) -> dict:
    invariant = """
      id, gsis_id, name, pos, team, opp, game_id, salary, proj,
      consensus_div, market_points, model_points_pre, mean_projection,
      proj_p10, proj_p50, proj_p90, proj_std, target_share_last,
      carry_share_last, snap_share_last, target_share_jump, carry_share_jump,
      snap_share_jump, target_share_l4, carry_share_l4, snap_share_l4,
      dk_points_l4, implied_team_total, spread, game_total, is_cold_start,
      depth_rank, depth_rank_delta, team_vacated_target_share,
      team_vacated_carry_share, salary_delta_wow, games_played_prior, actual,
      ensemble_point_0, ensemble_point_1, ensemble_point_2, feature_missing,
      model_ensemble_size, model_member_spec
    """
    result = query_df(f"""
      WITH source_rows AS (
        SELECT season, week, id, own_est, proj_tourney,
               TO_JSON_STRING(STRUCT({invariant})) AS invariant_payload
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{_panel_id(source)}' AND research_eligible
      ), treatment_rows AS (
        SELECT season, week, id, own_est, proj_tourney,
               TO_JSON_STRING(STRUCT({invariant})) AS invariant_payload
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{_panel_id(treatment)}'
      ), paired AS (
        SELECT COALESCE(s.season, t.season) AS season,
               COALESCE(s.week, t.week) AS week,
               s.id AS source_id, t.id AS treatment_id,
               s.own_est AS source_own, t.own_est AS treatment_own,
               s.proj_tourney AS source_tourney,
               t.proj_tourney AS treatment_tourney,
               s.invariant_payload AS source_invariant,
               t.invariant_payload AS treatment_invariant
        FROM source_rows s FULL OUTER JOIN treatment_rows t
        USING (season, week, id)
      )
      SELECT
        (SELECT COUNT(*) FROM source_rows) AS source_rows,
        (SELECT COUNT(*) FROM treatment_rows) AS treatment_rows,
        COUNTIF(source_id IS NULL) AS treatment_only_rows,
        COUNTIF(treatment_id IS NULL) AS source_only_rows,
        COUNTIF(source_invariant != treatment_invariant)
                AS invariant_mismatch_rows,
        COUNTIF(season <= 2022 AND
                (ABS(source_own-treatment_own) > 1e-10 OR
                 ABS(source_tourney-treatment_tourney) > 1e-8))
                AS preownership_change_rows,
        COUNTIF(season >= 2023 AND ABS(source_own-treatment_own) > 1e-10)
                AS ownership_changed_rows,
        COUNT(DISTINCT IF(season >= 2023 AND
                ABS(source_own-treatment_own) > 1e-10,
                FORMAT('%d-%d',season,week),NULL)) AS ownership_changed_slates,
        MAX(ABS((treatment_tourney-source_tourney)
                + 25.0*(treatment_own-source_own))) AS fade_equation_max_error
      FROM paired
    """).iloc[0]
    ints = [name for name in result.index if name != "fade_equation_max_error"]
    report = {name: int(result.get(name) or 0) for name in ints}
    report["fade_equation_max_error"] = float(
        result.fade_equation_max_error or 0.0)
    return report


def _candidate_audit(source: str, treatment: str) -> dict:
    result = query_df(f"""
      WITH source_rows AS (
        SELECT season, week, players, selected, actual_score, p_line,
               sim_mean, clear_bits_194
        FROM `{settings.predictions}.replay_candidates`
        WHERE panel_run_id = '{_panel_id(source)}' AND research_eligible
      ), treatment_rows AS (
        SELECT season, week, players, selected, actual_score, p_line,
               sim_mean, clear_bits_194
        FROM `{settings.predictions}.replay_candidates_staging`
        WHERE panel_run_id = '{_panel_id(treatment)}'
      ), paired AS (
        SELECT s.players AS source_players, t.players AS treatment_players,
               s.selected AS source_selected, t.selected AS treatment_selected,
               s.actual_score AS source_actual, t.actual_score AS treatment_actual,
               s.p_line AS source_p_line, t.p_line AS treatment_p_line,
               s.sim_mean AS source_mean, t.sim_mean AS treatment_mean,
               s.clear_bits_194 AS source_bits, t.clear_bits_194 AS treatment_bits
        FROM source_rows s FULL OUTER JOIN treatment_rows t
        USING (season, week, players)
      )
      SELECT
        (SELECT COUNT(*) FROM source_rows) AS source_rows,
        (SELECT COUNT(*) FROM treatment_rows) AS treatment_rows,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL)
                AS common_rows,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NULL)
                AS source_only_rows,
        COUNTIF(source_players IS NULL AND treatment_players IS NOT NULL)
                AS treatment_only_rows,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND ABS(source_actual-treatment_actual) > 1e-8)
                AS common_actual_mismatch,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND ABS(source_p_line-treatment_p_line) > 1e-8)
                AS common_p_line_mismatch,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND ABS(source_mean-treatment_mean) > 1e-6)
                AS common_sim_mean_mismatch,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND source_bits != treatment_bits) AS common_support_mismatch,
        COUNTIF(source_selected AND COALESCE(NOT treatment_selected, TRUE))
                AS selected_source_only,
        COUNTIF(treatment_selected AND COALESCE(NOT source_selected, TRUE))
                AS selected_treatment_only
      FROM paired
    """).iloc[0]
    return {name: int(result.get(name) or 0) for name in result.index}


def _ownership_book(panel: str, promoted: bool) -> dict:
    table = "replay_candidates" if promoted else "replay_candidates_staging"
    eligibility = "AND c.research_eligible" if promoted else ""
    result = query_df(f"""
      WITH books AS (
        SELECT c.season, c.week, c.cand_ix,
               SUM(f.own_est) AS own_sum,
               SUM(LN(GREATEST(f.own_est, 1e-12))) AS log_own_product
        FROM `{settings.predictions}.{table}` c
        CROSS JOIN UNNEST(SPLIT(c.players, ',')) player_id
        JOIN `{settings.predictions}.slate_player_features` f
          ON f.panel_run_id = c.panel_run_id AND f.season = c.season
         AND f.week = c.week AND f.id = player_id
        WHERE c.panel_run_id = '{_panel_id(panel)}' AND c.selected {eligibility}
        GROUP BY c.season, c.week, c.cand_ix
      )
      SELECT COUNT(*) AS selected_rows, AVG(own_sum) AS mean_own_sum,
             APPROX_QUANTILES(own_sum,100)[OFFSET(50)] AS median_own_sum,
             AVG(log_own_product) AS mean_log_own_product,
             APPROX_QUANTILES(log_own_product,100)[OFFSET(50)]
                AS median_log_own_product
      FROM books
    """).iloc[0]
    return {
        "selected_rows": int(result.selected_rows or 0),
        "mean_own_sum": float(result.mean_own_sum),
        "median_own_sum": float(result.median_own_sum),
        "mean_log_own_product": float(result.mean_log_own_product),
        "median_log_own_product": float(result.median_log_own_product),
    }


def _validate(name: str, rows: pd.DataFrame) -> list[str]:
    if rows.empty:
        return [f"{name} is empty"]
    failures: list[str] = []
    slates = slate_scores(rows)
    if len(slates) != 107:
        failures.append(f"{name} does not have 107 slates")
    if not slates.n_selected.eq(80).all():
        failures.append(f"{name} does not select 80 every slate")
    for field in ("code_sha", "config_hash", "lever_env", "seeds"):
        if rows[field].nunique(dropna=False) != 1:
            failures.append(f"{name} has mixed {field}")
    return failures


def _mechanism_failures(source: pd.DataFrame, treatment: pd.DataFrame,
                        features: dict, candidates: dict) -> list[str]:
    failures: list[str] = []
    if source.empty or treatment.empty:
        return failures
    if source.config_hash.iloc[0] != treatment.config_hash.iloc[0]:
        failures.append("source/treatment config hashes differ")
    if source.seeds.iloc[0] != treatment.seeds.iloc[0]:
        failures.append("source/treatment seeds differ")
    source_levers = _levers(source.lever_env.iloc[0])
    treatment_levers = _levers(treatment.lever_env.iloc[0])
    if source_levers.get("OWN_MODEL", ""):
        failures.append("source unexpectedly uses an ownership model")
    if treatment_levers.get("OWN_MODEL") != "milly_fade":
        failures.append("treatment does not identify milly_fade")
    treatment_other = dict(treatment_levers)
    treatment_other.pop("OWN_MODEL", None)
    if source_levers != treatment_other:
        failures.append("ownership arm changes unrelated replay levers")
    if (features.get("source_rows") != features.get("treatment_rows")
            or features.get("source_only_rows")
            or features.get("treatment_only_rows")
            or features.get("invariant_mismatch_rows")):
        failures.append("upstream player snapshots differ")
    if features.get("preownership_change_rows"):
        failures.append("ownership changed without prior training data")
    if features.get("ownership_changed_slates") != 54:
        failures.append("Milly ownership did not change all 2023-2025 slates")
    if features.get("ownership_changed_rows", 0) <= 0:
        failures.append("Milly ownership estimate never changed")
    if features.get("fade_equation_max_error", 1.0) > 1e-6:
        failures.append("tourney projection does not equal frozen linear fade")
    for field in ("common_actual_mismatch", "common_p_line_mismatch",
                  "common_sim_mean_mismatch", "common_support_mismatch"):
        if candidates.get(field):
            failures.append(f"shared candidate worlds differ in {field}")
    if not candidates.get("source_only_rows") or not candidates.get("treatment_only_rows"):
        failures.append("ownership fade did not change the candidate book")
    if not candidates.get("selected_source_only") or not candidates.get("selected_treatment_only"):
        failures.append("ownership fade did not change the selected book")
    return failures


def _season_metrics(source: pd.DataFrame, treatment: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for season in sorted(source.season.unique()):
        s = source[source.season.eq(season)]
        t = treatment[treatment.season.eq(season)]
        row: dict[str, int] = {"season": int(season), "slates": int(len(s))}
        for threshold in THRESHOLDS:
            row[f"source_selected_{threshold}"] = int(
                s.selected_best.ge(threshold).sum())
            row[f"treatment_selected_{threshold}"] = int(
                t.selected_best.ge(threshold).sum())
            row[f"source_oracle_{threshold}"] = int(s.oracle.ge(threshold).sum())
            row[f"treatment_oracle_{threshold}"] = int(
                t.oracle.ge(threshold).sum())
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("treatment")
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--output")
    args = parser.parse_args()
    source = _load(args.source, True)
    treatment = _load(args.treatment, False)
    failures = _validate("source", source) + _validate("treatment", treatment)
    feature_audit: dict = {}
    candidate_audit: dict = {}
    source_slates = pd.DataFrame()
    treatment_slates = pd.DataFrame()
    if not source.empty and not treatment.empty:
        feature_audit = _feature_audit(args.source, args.treatment)
        candidate_audit = _candidate_audit(args.source, args.treatment)
        failures.extend(_mechanism_failures(
            source, treatment, feature_audit, candidate_audit))
        source_slates = slate_scores(source)
        treatment_slates = slate_scores(treatment)
    gate = (tail_first_gate(source_slates, treatment_slates)
            if not source_slates.empty and not treatment_slates.empty else {})
    if gate:
        gate["mechanism_valid"] = not failures
        gate["passes"] = all(v for k, v in gate.items() if k != "passes")
    report = {
        "source": args.source,
        "treatment": args.treatment,
        "source_metrics": metrics(source_slates) if not source_slates.empty else {},
        "treatment_metrics": (metrics(treatment_slates)
                              if not treatment_slates.empty else {}),
        "season_metrics": (_season_metrics(source_slates, treatment_slates)
                           if not source_slates.empty else []),
        "feature_mechanism": feature_audit,
        "candidate_mechanism": candidate_audit,
        "source_selected_ownership": (
            _ownership_book(args.source, True) if not source.empty else {}),
        "treatment_selected_ownership": (
            _ownership_book(args.treatment, False) if not treatment.empty else {}),
        "tail_first_gate": gate,
        "disposition": ("pass" if gate.get("passes") else
                        "invalid" if failures else "reject"),
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
