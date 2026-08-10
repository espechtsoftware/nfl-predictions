"""Audit the preregistered K=1 + CE role-belief candidate experiment."""
from __future__ import annotations

import argparse
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import re
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.research.panel_compare import metrics, slate_scores  # noqa: E402


SOURCE_PANEL = "20260809-e80-k1-ce12-c616390"
UNION_PANEL = "20260810-e80-k1-ce12-roleunion-c616390"
FIXED_PANEL = "20260810-e80-k1-ce12-role12-c616390"
ROLE_FEATURES = (
    "target_share_last,carry_share_last,snap_share_last,"
    "target_share_jump,carry_share_jump,snap_share_jump"
)
THRESHOLDS = (187, 194, 200, 210, 220, 230, 240)

_CE_SPEC = spec_from_file_location(
    "_role_ce_compare",
    Path(__file__).resolve().parent / "compare_k1_ce_panel.py")
assert _CE_SPEC and _CE_SPEC.loader
_ce = module_from_spec(_CE_SPEC)
_CE_SPEC.loader.exec_module(_ce)


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
    """Parse persisted KEY=value fields, including a JSON cap-map value."""
    raw = str(value or "")
    matches = list(re.finditer(r"(?:^|,)([A-Z][A-Z0-9_]*)=", raw))
    out: dict[str, str] = {}
    for ix, match in enumerate(matches):
        start = match.end()
        stop = matches[ix + 1].start() if ix + 1 < len(matches) else len(raw)
        out[match.group(1)] = raw[start:stop].rstrip(",")
    return out


def _candidate_pair_audit(source: str, treatment: str) -> dict:
    result = query_df(f"""
      WITH source_rows AS (
        SELECT season, week, players, tag, selected, actual_score, p_line,
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
               s.tag AS source_tag, t.tag AS treatment_tag,
               s.selected AS source_selected, t.selected AS treatment_selected,
               s.actual_score AS source_actual, t.actual_score AS treatment_actual,
               s.p_line AS source_p_line, t.p_line AS treatment_p_line,
               s.sim_mean AS source_mean, t.sim_mean AS treatment_mean,
               s.clear_bits_194 AS source_bits, t.clear_bits_194 AS treatment_bits
        FROM source_rows s FULL OUTER JOIN treatment_rows t
        USING (season, week, players)
      ), source_counts AS (
        SELECT season, week, COUNT(*) AS n, COUNTIF(tag='ce') AS n_ce
        FROM source_rows GROUP BY season, week
      ), treatment_counts AS (
        SELECT season, week, COUNT(*) AS n, COUNTIF(tag='ce') AS n_ce,
               COUNTIF(tag='epi') AS n_role
        FROM treatment_rows GROUP BY season, week
      ), counts AS (
        SELECT COALESCE(s.season,t.season) AS season,
               COALESCE(s.week,t.week) AS week, s.n AS source_n,
               t.n AS treatment_n, s.n_ce AS source_ce, t.n_ce AS treatment_ce,
               t.n_role
        FROM source_counts s FULL OUTER JOIN treatment_counts t
        USING (season,week)
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
        COUNTIF(source_players IS NULL AND treatment_players IS NOT NULL
                AND treatment_tag='epi') AS novel_role_rows,
        COUNTIF(source_players IS NOT NULL AND source_tag='ce'
                AND (treatment_players IS NULL OR treatment_tag!='ce'))
                AS missing_source_ce_rows,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND ABS(source_actual-treatment_actual)>1e-8)
                AS common_actual_mismatch,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND ABS(source_p_line-treatment_p_line)>1e-8)
                AS common_p_line_mismatch,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND ABS(source_mean-treatment_mean)>1e-6)
                AS common_sim_mean_mismatch,
        COUNTIF(source_players IS NOT NULL AND treatment_players IS NOT NULL
                AND source_bits!=treatment_bits) AS common_support_mismatch,
        COUNTIF(source_selected AND COALESCE(NOT treatment_selected,TRUE))
                AS selected_source_only,
        COUNTIF(treatment_selected AND COALESCE(NOT source_selected,TRUE))
                AS selected_treatment_only,
        COUNTIF(treatment_selected AND treatment_tag='epi') AS selected_role_rows,
        (SELECT COUNT(*) FROM counts) AS paired_slates,
        (SELECT COUNTIF(treatment_n>source_n) FROM counts)
                AS slates_with_larger_treatment,
        (SELECT COUNTIF(treatment_n=source_n) FROM counts)
                AS slates_with_equal_pools,
        (SELECT MIN(treatment_n-source_n) FROM counts) AS min_pool_delta,
        (SELECT MAX(treatment_n-source_n) FROM counts) AS max_pool_delta,
        (SELECT COUNTIF(n_role>0) FROM counts) AS slates_with_role,
        (SELECT MIN(n_role) FROM counts) AS min_role_per_slate,
        (SELECT MAX(n_role) FROM counts) AS max_role_per_slate,
        (SELECT COUNTIF(source_ce=treatment_ce) FROM counts)
                AS slates_with_equal_ce_count
      FROM paired
    """).iloc[0]
    return {name: int(result.get(name) or 0) for name in result.index}


def _role_frontiers(source: pd.DataFrame,
                    treatment: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    incumbent = slate_scores(source)[["season", "week", "oracle"]]
    role = treatment[treatment.tag.eq("epi")]
    role_best = role.groupby(["season", "week"]).actual_score.max().rename(
        "role_best").reset_index()
    pair = incumbent.merge(role_best, on=["season", "week"], how="left",
                           validate="one_to_one")
    pair["frontier_gain"] = pair.role_best - pair.oracle
    report = {
        "role_frontier_weeks": int(pair.frontier_gain.gt(1e-9).sum()),
        "role_new_200_weeks": int(
            (pair.oracle.lt(200) & pair.role_best.ge(200)).sum()),
        "role_new_210_weeks": int(
            (pair.oracle.lt(210) & pair.role_best.ge(210)).sum()),
        "max_role_score": float(pair.role_best.max()),
        "max_frontier_gain": float(pair.frontier_gain.max()),
        "frontier_weeks": pair[pair.frontier_gain.gt(1e-9)].sort_values(
            "frontier_gain", ascending=False).to_dict("records"),
    }
    return pair, report


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
        failures.append("source and treatment seed identities differ")

    source_levers = _lever_values(source.lever_env.iloc[0])
    treatment_levers = _lever_values(treatment.lever_env.iloc[0])
    expected_source = {"N_CE": "12", "N_EPISTEMIC": "0", "N_BOOM": "28"}
    expected_treatment = {
        "N_CE": "12", "N_EPISTEMIC": "12",
        "N_BOOM": "28" if mode == "union" else "16",
    }
    for key, value in expected_source.items():
        if source_levers.get(key) != value:
            failures.append(f"source {key} is not {value}")
    for key, value in expected_treatment.items():
        if treatment_levers.get(key) != value:
            failures.append(f"treatment {key} is not {value}")
    exact_role = {
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
        "ROLE_BELIEF_SEED": "7331",
        "CE_SEED": "1701",
    }
    for key, value in exact_role.items():
        if treatment_levers.get(key) != value:
            failures.append(f"treatment {key} is not the frozen value")
    if treatment_levers.get("REPLACEMENT_SLOTS") != "12":
        failures.append("treatment replacement quota is not 12")
    if mode == "fixed":
        if treatment_levers.get("GEN_POOL_CAP_MAP") != source_levers.get(
                "GEN_POOL_CAP_MAP"):
            failures.append("fixed treatment cap map differs from source")
    else:
        if "GEN_POOL_CAP_MAP" in treatment_levers:
            failures.append("union treatment must be uncapped")

    allowed = {
        "N_EPISTEMIC", "N_BOOM", "EPISTEMIC_FAMILY",
        "ROLE_BELIEF_FEATURES", "ROLE_BELIEF_SEED",
    }
    if mode == "union":
        allowed |= {"GEN_POOL_CAP_MAP"}
    source_other = {k: v for k, v in source_levers.items() if k not in allowed}
    treatment_other = {
        k: v for k, v in treatment_levers.items() if k not in allowed}
    if source_other != treatment_other:
        failures.append("role treatment changes unrelated replay levers")

    if (feature_audit.get("source_rows") != feature_audit.get("treatment_rows")
            or feature_audit.get("source_only_rows")
            or feature_audit.get("treatment_only_rows")
            or feature_audit.get("mismatch_rows")):
        failures.append("source/treatment player snapshots are not invariant")
    if pair_audit.get("paired_slates") != 107:
        failures.append("candidate audit does not cover 107 paired slates")
    if (pair_audit.get("slates_with_role") != 107
            or pair_audit.get("min_role_per_slate") != 12
            or pair_audit.get("max_role_per_slate") != 12):
        failures.append("role generator did not retain exactly 12 candidates per slate")
    if pair_audit.get("novel_role_rows", 0) <= 0:
        failures.append("role generator produced no source-novel roster")
    if pair_audit.get("missing_source_ce_rows"):
        failures.append("role treatment failed to preserve source CE candidates")
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
        if pair_audit.get("selected_role_rows", 0) <= 0:
            failures.append("fixed treatment selected no role candidates")
        if pair_audit.get("selected_source_only", 0) <= 0:
            failures.append("fixed treatment removed no source selected roster")
        if pair_audit.get("selected_treatment_only", 0) <= 0:
            failures.append("fixed treatment added no selected roster")
    return failures


def _score_gates(source_metrics: dict, treatment_metrics: dict,
                 role_report: dict, mechanism_valid: bool) -> tuple[dict, dict]:
    union = {
        "mechanism_valid": mechanism_valid,
        "role_new_200_weeks_at_least_2":
            role_report.get("role_new_200_weeks", 0) >= 2,
        "role_frontier_weeks_at_least_2":
            role_report.get("role_frontier_weeks", 0) >= 2,
    }
    union["passes"] = all(union.values())
    fixed = {
        "mechanism_valid": mechanism_valid,
        "selected_200_lift_at_least_2":
            treatment_metrics.get("clear_200", 0)
            >= source_metrics.get("clear_200", 0) + 2,
    }
    for threshold in (210, 220, 230, 240):
        fixed[f"selected_{threshold}_not_worse"] = (
            treatment_metrics.get(f"clear_{threshold}", 0)
            >= source_metrics.get(f"clear_{threshold}", 0))
    for threshold in (200, 210, 220, 230, 240):
        fixed[f"oracle_{threshold}_not_worse"] = (
            treatment_metrics.get(f"oracle_{threshold}", 0)
            >= source_metrics.get(f"oracle_{threshold}", 0))
    fixed["novel_role_frontier"] = role_report.get("role_frontier_weeks", 0) >= 1
    fixed["passes"] = all(fixed.values())
    return union, fixed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("treatment")
    parser.add_argument("--source", default=SOURCE_PANEL)
    parser.add_argument("--mode", required=True, choices=("union", "fixed"))
    parser.add_argument("--output")
    args = parser.parse_args()
    source = _candidates(args.source, promoted=True)
    treatment = _candidates(args.treatment, promoted=False)
    failures = (_ce._validate_panel("source", source)
                + _ce._validate_panel("treatment", treatment))
    feature_audit: dict = {}
    pair_audit: dict = {}
    role_report: dict = {}
    source_slates = pd.DataFrame()
    treatment_slates = pd.DataFrame()
    if not source.empty and not treatment.empty:
        feature_audit = _ce._feature_invariance(args.source, args.treatment)
        pair_audit = _candidate_pair_audit(args.source, args.treatment)
        failures.extend(_mechanism_failures(
            source, treatment, feature_audit, pair_audit, args.mode))
        _, role_report = _role_frontiers(source, treatment)
        source_slates = slate_scores(source)
        treatment_slates = slate_scores(treatment)

    source_metrics = metrics(source_slates) if not source_slates.empty else {}
    treatment_metrics = metrics(treatment_slates) if not treatment_slates.empty else {}
    union_gate, fixed_gate = _score_gates(
        source_metrics, treatment_metrics, role_report, not failures)
    active_gate = union_gate if args.mode == "union" else fixed_gate
    report = {
        "source": args.source,
        "treatment": args.treatment,
        "mode": args.mode,
        "source_metrics": source_metrics,
        "treatment_metrics": treatment_metrics,
        "season_metrics": (
            _ce._season_metrics(source_slates, treatment_slates)
            if not source_slates.empty and not treatment_slates.empty else []),
        "feature_invariance": feature_audit,
        "candidate_pair_audit": pair_audit,
        "role_frontier": role_report,
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
