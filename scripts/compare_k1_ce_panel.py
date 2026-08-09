"""Audit the frozen corrected K=1 cross-entropy experiment.

The accepted source is read from the promoted research table and the CE arm
from staging.  ``union`` is a candidate-frontier gate only; ``fixed`` is the
equal-budget, equal-realized-pool scoring comparison.
"""
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
from nfl_dfs.research.panel_compare import metrics, slate_scores  # noqa: E402


SOURCE_PANEL = "20260808-e80-k1-c616390"
THRESHOLDS = (187, 194, 200, 210, 220, 230, 240)


def _panel_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"invalid panel id {value!r}")
    return value


def _candidates(panel: str, promoted: bool) -> pd.DataFrame:
    table = "replay_candidates" if promoted else "replay_candidates_staging"
    eligibility = "AND research_eligible" if promoted else ""
    return query_df(f"""
        SELECT season, week, cand_ix, tag, all_tags, players, selected,
               actual_score, code_sha, config_hash, lever_env, seeds
        FROM `{settings.predictions}.{table}`
        WHERE panel_run_id = '{_panel_id(panel)}' {eligibility}
        """)


def _lever_values(value: str) -> dict[str, str]:
    """Parse persisted levers, tolerating commas inside the cap-map JSON."""
    out: dict[str, str] = {}
    for item in str(value or "").split(","):
        if "=" in item:
            key, val = item.split("=", 1)
            out[key.strip()] = val.strip()
    return out


def _feature_invariance(source: str, treatment: str) -> dict:
    # Every point-in-time player field that can affect worlds or candidate
    # construction is included.  Run identity/timestamps are intentionally
    # excluded.
    fields = """
      id, gsis_id, name, pos, team, opp, game_id, salary, proj, proj_tourney,
      own_est, consensus_div, market_points, model_points_pre, mean_projection,
      proj_p10, proj_p50, proj_p90, proj_std, target_share_last,
      carry_share_last, snap_share_last, target_share_jump, carry_share_jump,
      snap_share_jump, target_share_l4, carry_share_l4, snap_share_l4,
      dk_points_l4, implied_team_total, spread, game_total, is_cold_start,
      depth_rank, depth_rank_delta, team_vacated_target_share,
      team_vacated_carry_share, salary_delta_wow, games_played_prior, actual,
      ensemble_point_0, ensemble_point_1, ensemble_point_2, feature_missing,
      code_sha, config_hash, model_ensemble_size, model_member_spec
    """
    result = query_df(f"""
      WITH source_rows AS (
        SELECT season, week, id, TO_JSON_STRING(STRUCT({fields})) AS payload
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{_panel_id(source)}' AND research_eligible
      ), treatment_rows AS (
        SELECT season, week, id, TO_JSON_STRING(STRUCT({fields})) AS payload
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{_panel_id(treatment)}'
      ), paired AS (
        SELECT s.payload AS source_payload, t.payload AS treatment_payload
        FROM source_rows s FULL OUTER JOIN treatment_rows t
        USING (season, week, id)
      )
      SELECT
        (SELECT COUNT(*) FROM source_rows) AS source_rows,
        (SELECT COUNT(*) FROM treatment_rows) AS treatment_rows,
        COUNTIF(source_payload IS NULL) AS treatment_only_rows,
        COUNTIF(treatment_payload IS NULL) AS source_only_rows,
        COUNTIF(source_payload IS NOT NULL AND treatment_payload IS NOT NULL
                AND source_payload != treatment_payload) AS mismatch_rows
      FROM paired
    """).iloc[0]
    return {name: int(result.get(name) or 0) for name in result.index}


def _candidate_pair_audit(source: str, treatment: str) -> dict:
    result = query_df(f"""
      WITH source_rows AS (
        SELECT season, week, players, selected, actual_score, p_line,
               sim_mean, clear_bits_194
        FROM `{settings.predictions}.replay_candidates`
        WHERE panel_run_id = '{_panel_id(source)}' AND research_eligible
      ), treatment_rows AS (
        SELECT season, week, players, tag, selected, actual_score, p_line,
               sim_mean, clear_bits_194
        FROM `{settings.predictions}.replay_candidates_staging`
        WHERE panel_run_id = '{_panel_id(treatment)}'
      ), paired AS (
        SELECT s.players AS source_players, t.players AS treatment_players,
               s.selected AS source_selected, t.selected AS treatment_selected,
               s.actual_score AS source_actual, t.actual_score AS treatment_actual,
               s.p_line AS source_p_line, t.p_line AS treatment_p_line,
               s.sim_mean AS source_mean, t.sim_mean AS treatment_mean,
               s.clear_bits_194 AS source_bits,
               t.clear_bits_194 AS treatment_bits, t.tag AS treatment_tag
        FROM source_rows s FULL OUTER JOIN treatment_rows t
        USING (season, week, players)
      ), source_counts AS (
        SELECT season, week, COUNT(*) AS n FROM source_rows GROUP BY season, week
      ), treatment_counts AS (
        SELECT season, week, COUNT(*) AS n,
               COUNTIF(tag = 'ce') AS n_ce
        FROM treatment_rows GROUP BY season, week
      ), counts AS (
        SELECT COALESCE(s.season, t.season) AS season,
               COALESCE(s.week, t.week) AS week, s.n AS source_n,
               t.n AS treatment_n, t.n_ce
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
        COUNTIF(source_players IS NULL AND treatment_players IS NOT NULL
                AND treatment_tag = 'ce') AS novel_ce_rows,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND ABS(source_actual - treatment_actual) > 1e-8)
                AS common_actual_mismatch,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND ABS(source_p_line - treatment_p_line) > 1e-8)
                AS common_p_line_mismatch,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND ABS(source_mean - treatment_mean) > 1e-6)
                AS common_sim_mean_mismatch,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND source_bits != treatment_bits) AS common_support_mismatch,
        COUNTIF(source_selected AND treatment_selected) AS selected_shared,
        COUNTIF(source_selected AND COALESCE(NOT treatment_selected, TRUE))
                AS selected_source_only,
        COUNTIF(treatment_selected AND COALESCE(NOT source_selected, TRUE))
                AS selected_treatment_only,
        (SELECT COUNT(*) FROM counts) AS paired_slates,
        (SELECT COUNTIF(treatment_n > source_n) FROM counts)
                AS slates_with_larger_treatment,
        (SELECT COUNTIF(treatment_n = source_n) FROM counts)
                AS slates_with_equal_pools,
        (SELECT MIN(treatment_n - source_n) FROM counts) AS min_pool_delta,
        (SELECT MAX(treatment_n - source_n) FROM counts) AS max_pool_delta,
        (SELECT COUNTIF(n_ce > 0) FROM counts) AS slates_with_ce,
        (SELECT MIN(n_ce) FROM counts) AS min_ce_per_slate,
        (SELECT MAX(n_ce) FROM counts) AS max_ce_per_slate
      FROM paired
    """).iloc[0]
    return {name: int(result.get(name) or 0) for name in result.index}


def _validate_panel(name: str, rows: pd.DataFrame) -> list[str]:
    failures: list[str] = []
    if rows.empty:
        return [f"{name} is empty"]
    slates = slate_scores(rows)
    if len(slates) != 107:
        failures.append(f"{name} has {len(slates)} slates, want 107")
    if not slates.n_selected.eq(80).all():
        failures.append(f"{name} does not select exactly 80 every slate")
    for col in ("code_sha", "config_hash", "lever_env", "seeds"):
        if rows[col].nunique(dropna=False) != 1:
            failures.append(f"{name} has mixed {col}")
    return failures


def _mechanism_failures(source: pd.DataFrame, treatment: pd.DataFrame,
                        feature_audit: dict, pair_audit: dict,
                        mode: str) -> list[str]:
    failures: list[str] = []
    if source.empty or treatment.empty:
        return failures
    if source.code_sha.iloc[0] != treatment.code_sha.iloc[0]:
        failures.append("source and treatment code SHA differ")
    if source.config_hash.iloc[0] != treatment.config_hash.iloc[0]:
        failures.append("source and treatment config hashes differ")
    if source.seeds.iloc[0] != treatment.seeds.iloc[0]:
        failures.append("source and treatment seeds differ")

    source_levers = _lever_values(source.lever_env.iloc[0])
    treatment_levers = _lever_values(treatment.lever_env.iloc[0])
    expected = ({"N_CE": "12", "N_BOOM": "40"} if mode == "union"
                else {"N_CE": "12", "N_BOOM": "28"})
    if source_levers.get("N_CE") != "0" or source_levers.get("N_BOOM") != "40":
        failures.append("source is not the frozen 0 CE / 40 boom control")
    for key, value in expected.items():
        if treatment_levers.get(key) != value:
            failures.append(f"treatment {key} is not {value}")
    if treatment_levers.get("CE_SEED") != "1701":
        failures.append("treatment CE_SEED is not 1701")
    allowed = {"N_CE", "N_BOOM", "CE_SEED"}
    if mode == "fixed":
        allowed |= {"GEN_POOL_CAP_MAP", "REPLACEMENT_SLOTS"}
        if "GEN_POOL_CAP_MAP" not in treatment_levers:
            failures.append("fixed treatment has no per-slate pool cap map")
        if treatment_levers.get("REPLACEMENT_SLOTS") != "12":
            failures.append("fixed treatment replacement quota is not 12")
    source_other = {k: v for k, v in source_levers.items() if k not in allowed}
    treatment_other = {
        k: v for k, v in treatment_levers.items() if k not in allowed}
    if source_other != treatment_other:
        failures.append("CE treatment changes unrelated replay levers")

    if (feature_audit.get("source_rows") != feature_audit.get("treatment_rows")
            or feature_audit.get("source_only_rows")
            or feature_audit.get("treatment_only_rows")
            or feature_audit.get("mismatch_rows")):
        failures.append("source/treatment player snapshots are not invariant")
    if pair_audit.get("paired_slates") != 107:
        failures.append("candidate audit does not cover 107 paired slates")
    if pair_audit.get("slates_with_ce") != 107:
        failures.append("CE did not produce a unique retained candidate every slate")
    if pair_audit.get("novel_ce_rows", 0) <= 0:
        failures.append("CE produced no roster absent from the source pool")
    for field in ("common_actual_mismatch", "common_p_line_mismatch",
                  "common_sim_mean_mismatch", "common_support_mismatch"):
        if pair_audit.get(field):
            failures.append(f"shared candidates differ in {field}")
    if mode == "union":
        if pair_audit.get("source_only_rows"):
            failures.append("union treatment is not a source-roster superset")
        if pair_audit.get("slates_with_larger_treatment") != 107:
            failures.append("union treatment did not expand every slate")
    else:
        if pair_audit.get("slates_with_equal_pools") != 107:
            failures.append("fixed treatment does not match every source pool size")
        if pair_audit.get("selected_source_only", 0) <= 0:
            failures.append("fixed treatment removed no source selected rosters")
        if pair_audit.get("selected_treatment_only", 0) <= 0:
            failures.append("fixed treatment added no selected rosters")
    return failures


def _season_metrics(source_slates: pd.DataFrame,
                    treatment_slates: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for season in sorted(source_slates.season.unique()):
        source = source_slates[source_slates.season.eq(season)]
        treatment = treatment_slates[treatment_slates.season.eq(season)]
        row: dict[str, int] = {"season": int(season), "slates": int(len(source))}
        for threshold in THRESHOLDS:
            row[f"source_selected_{threshold}"] = int(
                source.selected_best.ge(threshold).sum())
            row[f"treatment_selected_{threshold}"] = int(
                treatment.selected_best.ge(threshold).sum())
            row[f"source_oracle_{threshold}"] = int(
                source.oracle.ge(threshold).sum())
            row[f"treatment_oracle_{threshold}"] = int(
                treatment.oracle.ge(threshold).sum())
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("treatment")
    parser.add_argument("--source", default=SOURCE_PANEL)
    parser.add_argument("--mode", required=True, choices=("union", "fixed"))
    parser.add_argument("--output")
    args = parser.parse_args()
    source = _candidates(args.source, promoted=True)
    treatment = _candidates(args.treatment, promoted=False)
    failures = (_validate_panel("source", source)
                + _validate_panel("treatment", treatment))
    feature_audit: dict = {}
    pair_audit: dict = {}
    source_slates = pd.DataFrame()
    treatment_slates = pd.DataFrame()
    if not source.empty and not treatment.empty:
        feature_audit = _feature_invariance(args.source, args.treatment)
        pair_audit = _candidate_pair_audit(args.source, args.treatment)
        failures.extend(_mechanism_failures(
            source, treatment, feature_audit, pair_audit, args.mode))
        source_slates = slate_scores(source)
        treatment_slates = slate_scores(treatment)

    source_metrics = metrics(source_slates) if not source_slates.empty else {}
    treatment_metrics = (
        metrics(treatment_slates) if not treatment_slates.empty else {})
    union_gate: dict = {}
    fixed_gate: dict = {}
    if source_metrics and treatment_metrics:
        union_gate = {
            "mechanism_valid": not failures,
            "oracle_200_lift_at_least_2":
                treatment_metrics["oracle_200"] >= source_metrics["oracle_200"] + 2,
            "oracle_210_not_worse":
                treatment_metrics["oracle_210"] >= source_metrics["oracle_210"],
            "oracle_220_not_worse":
                treatment_metrics["oracle_220"] >= source_metrics["oracle_220"],
            "oracle_230_not_worse":
                treatment_metrics["oracle_230"] >= source_metrics["oracle_230"],
            "oracle_240_not_worse":
                treatment_metrics["oracle_240"] >= source_metrics["oracle_240"],
        }
        union_gate["passes"] = all(union_gate.values())
        fixed_gate = {
            "mechanism_valid": not failures,
            "selected_200_lift_at_least_2":
                treatment_metrics["clear_200"] >= source_metrics["clear_200"] + 2,
            "selected_210_not_worse":
                treatment_metrics["clear_210"] >= source_metrics["clear_210"],
            "oracle_200_not_worse":
                treatment_metrics["oracle_200"] >= source_metrics["oracle_200"],
        }
        fixed_gate["passes"] = all(fixed_gate.values())

    active_gate = union_gate if args.mode == "union" else fixed_gate
    report = {
        "source": args.source,
        "treatment": args.treatment,
        "mode": args.mode,
        "source_metrics": source_metrics,
        "treatment_metrics": treatment_metrics,
        "season_metrics": (_season_metrics(source_slates, treatment_slates)
                           if not source_slates.empty and not treatment_slates.empty
                           else []),
        "feature_invariance": feature_audit,
        "candidate_pair_audit": pair_audit,
        "union_gate": union_gate,
        "fixed_gate": fixed_gate,
        "disposition": ("pass" if active_gate.get("passes") else
                        "invalid" if failures else "reject"),
        "failures": failures,
    }
    compact = json.dumps(report, separators=(",", ":"), sort_keys=True)
    print(compact)
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
