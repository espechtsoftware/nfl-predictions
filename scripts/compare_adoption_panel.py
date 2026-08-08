"""Compare one accepted Phase-A source with one same-image ablation.

The source is read only from the promoted research table; the treatment is
read only from staging. A failed ablation never needs promotion to be scored.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.models.components import ensemble_member_specs  # noqa: E402
from nfl_dfs.research.panel_compare import (  # noqa: E402
    directional_gate, metrics, slate_scores)


def _panel_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"invalid panel id {value!r}")
    return value


def _candidates(panel: str, promoted: bool) -> pd.DataFrame:
    table = "replay_candidates" if promoted else "replay_candidates_staging"
    eligibility = "AND research_eligible" if promoted else ""
    return query_df(f"""
        SELECT season, week, cand_ix, players, selected, actual_score,
               sim_mean, code_sha, config_hash, lever_env, seeds
        FROM `{settings.predictions}.{table}`
        WHERE panel_run_id = '{_panel_id(panel)}' {eligibility}
        """)


def _features(panel: str, promoted: bool) -> pd.DataFrame:
    eligibility = "AND research_eligible" if promoted else ""
    return query_df(f"""
        SELECT season, week, id, pos, proj, mean_projection,
               model_points_pre, market_points
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{_panel_id(panel)}' {eligibility}
        """)


def _ensemble_features(panel: str, promoted: bool) -> pd.DataFrame:
    """Fetch the immutable fields needed to prove MODEL_ENSEMBLE fired."""
    eligibility = "AND research_eligible" if promoted else ""
    return query_df(f"""
        SELECT season, week, id, pos, salary, actual, proj,
               mean_projection, model_points_pre, market_points,
               model_ensemble_size, model_member_spec,
               ensemble_point_0, ensemble_point_1, ensemble_point_2
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{_panel_id(panel)}' {eligibility}
        """)


def _split_seed_provenance(value: str) -> tuple[str, dict[str, str]]:
    """Separate ensemble identity from every other recorded RNG setting."""
    ensemble: dict[str, str] = {}
    rest: list[str] = []
    for item in str(value or "").split(";"):
        if item.startswith("MODEL_ENSEMBLE_SIZE="):
            ensemble["size"] = item.split("=", 1)[1]
        elif item.startswith("MODEL_MEMBER_SPEC="):
            ensemble["spec"] = item.split("=", 1)[1]
        elif item:
            rest.append(item)
    return ";".join(rest), ensemble


def _validate_panel(name: str, rows: pd.DataFrame) -> list[str]:
    failures: list[str] = []
    if rows.empty:
        return [f"{name} is empty"]
    slates = slate_scores(rows)
    if len(slates) != 107:
        failures.append(f"{name} has {len(slates)} slates, want 107")
    if not slates.n_selected.eq(40).all():
        failures.append(f"{name} does not select exactly 40 every slate")
    for col in ("code_sha", "config_hash", "lever_env", "seeds"):
        if rows[col].nunique(dropna=False) != 1:
            failures.append(f"{name} has mixed {col}")
    return failures


def _candidate_mean_audit(panel: str, promoted: bool) -> dict:
    """Compute candidate/player world-mean parity in BigQuery, not locally."""
    table = "replay_candidates" if promoted else "replay_candidates_staging"
    eligibility = "AND research_eligible" if promoted else ""
    result = query_df(f"""
        WITH features AS (
          SELECT season, week, id, pos, proj, mean_projection
          FROM `{settings.predictions}.slate_player_features`
          WHERE panel_run_id = '{_panel_id(panel)}' {eligibility}
        ), duplicate_keys AS (
          SELECT COUNT(*) AS n FROM (
            SELECT season, week, id FROM features
            GROUP BY season, week, id HAVING COUNT(*) != 1)
        ), candidates AS (
          SELECT c.season, c.week, c.cand_ix, c.sim_mean,
                 COUNTIF(f.id IS NULL) AS missing,
                 SUM(IF(f.pos = 'DST', f.proj,
                        COALESCE(f.mean_projection, f.proj))) AS expected_mean
          FROM `{settings.predictions}.{table}` c
          CROSS JOIN UNNEST(SPLIT(c.players, ',')) player_id
          LEFT JOIN features f
            ON f.season = c.season AND f.week = c.week AND f.id = player_id
          WHERE c.panel_run_id = '{_panel_id(panel)}' {eligibility}
          GROUP BY c.season, c.week, c.cand_ix, c.sim_mean
        )
        SELECT COUNT(*) AS candidate_rows,
               (SELECT n FROM duplicate_keys) AS duplicate_feature_keys,
               SUM(missing) AS missing_roster_players,
               MAX(ABS(sim_mean - expected_mean)) AS max_abs_error
        FROM candidates
        """).iloc[0]
    return {
        "candidate_rows": int(result.candidate_rows or 0),
        "duplicate_feature_keys": int(result.duplicate_feature_keys or 0),
        "missing_roster_players": int(result.missing_roster_players or 0),
        "max_abs_error": (float(result.max_abs_error)
                          if pd.notna(result.max_abs_error) else float("inf")),
    }


def _no_market_reproduction(source: str, treatment: str) -> dict:
    """Exact control reproduction on slates where the lever has no input."""
    result = query_df(f"""
        WITH no_market_slates AS (
          SELECT season, week
          FROM `{settings.predictions}.slate_player_features`
          WHERE panel_run_id = '{_panel_id(source)}' AND research_eligible
          GROUP BY season, week
          HAVING COUNTIF(pos != 'DST' AND market_points IS NOT NULL) = 0
        ), source_rows AS (
          SELECT c.season, c.week, c.cand_ix, c.players, c.selected,
                 c.actual_score, c.sim_mean, c.p_line
          FROM `{settings.predictions}.replay_candidates` c
          JOIN no_market_slates n USING (season, week)
          WHERE c.panel_run_id = '{_panel_id(source)}' AND c.research_eligible
        ), treatment_rows AS (
          SELECT c.season, c.week, c.cand_ix, c.players, c.selected,
                 c.actual_score, c.sim_mean, c.p_line
          FROM `{settings.predictions}.replay_candidates_staging` c
          JOIN no_market_slates n USING (season, week)
          WHERE c.panel_run_id = '{_panel_id(treatment)}'
        ), paired AS (
          SELECT s.*, t.cand_ix AS treatment_cand_ix,
                 t.players AS treatment_players,
                 t.selected AS treatment_selected,
                 t.actual_score AS treatment_actual_score,
                 t.sim_mean AS treatment_sim_mean,
                 t.p_line AS treatment_p_line,
                 COALESCE(s.season, t.season) AS pair_season,
                 COALESCE(s.week, t.week) AS pair_week
          FROM source_rows s FULL OUTER JOIN treatment_rows t
          USING (season, week, cand_ix)
        )
        SELECT
          (SELECT COUNT(*) FROM no_market_slates) AS slates,
          (SELECT COUNT(*) FROM source_rows) AS source_rows,
          (SELECT COUNT(*) FROM treatment_rows) AS treatment_rows,
          COUNTIF(cand_ix IS NULL OR treatment_cand_ix IS NULL) AS missing_rows,
          COUNTIF(players != treatment_players) AS roster_mismatch,
          COUNTIF(selected != treatment_selected) AS selected_mismatch,
          MAX(ABS(actual_score - treatment_actual_score)) AS actual_max_delta,
          MAX(ABS(sim_mean - treatment_sim_mean)) AS sim_mean_max_delta,
          MAX(ABS(p_line - treatment_p_line)) AS p_line_max_delta
        FROM paired
        """).iloc[0]
    ints = ("slates", "source_rows", "treatment_rows", "missing_rows",
            "roster_mismatch", "selected_mismatch")
    floats = ("actual_max_delta", "sim_mean_max_delta", "p_line_max_delta")
    report = {name: int(result.get(name) or 0) for name in ints}
    report.update({name: (float(result[name]) if pd.notna(result[name]) else 0.0)
                   for name in floats})
    return report


def _blend_mechanism(source_features: pd.DataFrame,
                     treatment_features: pd.DataFrame,
                     source_mean_audit: dict,
                     treatment_mean_audit: dict,
                     no_market_reproduction: dict) -> tuple[dict, list[str]]:
    """Mechanically prove the model-only prop ablation fired."""
    failures: list[str] = []
    keys = ["season", "week", "id"]
    for name, frame in (("source", source_features),
                        ("treatment", treatment_features)):
        if frame.empty or frame.duplicated(keys).any():
            failures.append(f"{name} feature snapshot empty or duplicate")
    if failures:
        return {}, failures
    joined = source_features.merge(
        treatment_features, on=keys, how="outer",
        suffixes=("_source", "_treatment"), indicator=True,
        validate="one_to_one")
    if not joined._merge.eq("both").all():
        failures.append("source/treatment player universes differ")
    joined = joined[joined._merge.eq("both")].copy()
    covered = joined.market_points_source.notna()
    uncovered = ~covered
    market_null_mismatch = (
        joined.market_points_source.isna()
        != joined.market_points_treatment.isna())
    market_value_delta = (
        joined.market_points_source - joined.market_points_treatment).abs()
    market_mismatch = market_null_mismatch | market_value_delta.fillna(0).gt(1e-8)
    offense = joined.pos_source.ne("DST")
    defense = ~offense
    model_delta = (
        joined.model_points_pre_source[offense]
        - joined.model_points_pre_treatment[offense]).abs()
    # ``proj`` is the effective offensive projection and is therefore meant
    # to change under this lever.  Only DST's static projection is invariant.
    dst_proj_delta = (
        joined.proj_source[defense] - joined.proj_treatment[defense]).abs()
    expected_source = (
        0.45 * joined.model_points_pre_source
        + 0.55 * joined.market_points_source)
    source_error = (joined.mean_projection_source[covered]
                    - expected_source[covered]).abs()
    treatment_error = (
        joined.mean_projection_treatment
        - joined.model_points_pre_treatment).abs()
    uncovered_delta = (
        joined.mean_projection_treatment[uncovered]
        - joined.mean_projection_source[uncovered]).abs()
    covered_delta = (
        joined.mean_projection_treatment[covered]
        - joined.mean_projection_source[covered]).abs()
    if not covered.any():
        failures.append("prop coverage is zero")
    if market_mismatch.any():
        failures.append("source/treatment market inputs differ")
    if len(model_delta) and model_delta.max() > 1e-8:
        failures.append("source/treatment post-shaping model means differ")
    if len(dst_proj_delta) and dst_proj_delta.max() > 1e-8:
        failures.append("source/treatment DST projections differ")
    if len(source_error) and source_error.max() > 1e-5:
        failures.append("source persisted means do not match 0.45/0.55 blend")
    if len(treatment_error) and treatment_error.max() > 1e-5:
        failures.append("treatment persisted means are not model-only")
    if len(uncovered_delta) and uncovered_delta.max() > 1e-5:
        failures.append("uncovered player means changed")
    if not len(covered_delta) or covered_delta.mean() <= 1e-6:
        failures.append("covered player means did not change")

    for name, audit in (("source", source_mean_audit),
                        ("treatment", treatment_mean_audit)):
        if not audit["candidate_rows"]:
            failures.append(f"{name} candidate mean audit is empty")
        if audit["duplicate_feature_keys"]:
            failures.append(f"{name} feature keys are duplicate")
        if audit["missing_roster_players"]:
            failures.append(f"{name} candidate/player join is incomplete")
        # Candidate means are calculated from float32 worlds, so tolerate
        # accumulation noise but not an unshifted multi-point market delta.
        if audit["max_abs_error"] > 1e-3:
            failures.append(f"{name} candidate world means do not equal player means")
    reproduction_errors = sum(
        no_market_reproduction[name]
        for name in ("missing_rows", "roster_mismatch", "selected_mismatch"))
    reproduction_deltas = max(
        no_market_reproduction[name]
        for name in ("actual_max_delta", "sim_mean_max_delta",
                     "p_line_max_delta"))
    if not no_market_reproduction["slates"]:
        failures.append("no no-market slates available for exact control")
    if (no_market_reproduction["source_rows"]
            != no_market_reproduction["treatment_rows"]):
        failures.append("no-market control candidate counts differ")
    if reproduction_errors or reproduction_deltas > 1e-8:
        failures.append("no-market slates do not reproduce the control exactly")
    report = {
        "covered_player_weeks": int(covered.sum()),
        "uncovered_player_weeks": int(uncovered.sum()),
        "covered_mean_abs_ablation_delta": float(covered_delta.mean()),
        "market_input_mismatch_rows": int(market_mismatch.sum()),
        "post_shaping_model_max_abs_delta": (
            float(model_delta.max()) if len(model_delta) else 0.0),
        "dst_projection_max_abs_delta": (
            float(dst_proj_delta.max()) if len(dst_proj_delta) else 0.0),
        "uncovered_max_abs_delta": float(
            uncovered_delta.max()) if len(uncovered_delta) else 0.0,
        "source_blend_max_abs_error": float(
            source_error.max()) if len(source_error) else 0.0,
        "treatment_model_only_max_abs_error": float(
            treatment_error.max()) if len(treatment_error) else 0.0,
        "source_candidate_mean_max_abs_error": source_mean_audit["max_abs_error"],
        "treatment_candidate_mean_max_abs_error": treatment_mean_audit["max_abs_error"],
        "no_market_exact_reproduction": no_market_reproduction,
    }
    return report, failures


def _ensemble_mechanism(source_features: pd.DataFrame,
                        treatment_features: pd.DataFrame,
                        source_mean_audit: dict,
                        treatment_mean_audit: dict,
                        source_seeds: str,
                        treatment_seeds: str) -> tuple[dict, list[str]]:
    """Mechanically prove the three-member to one-member ablation fired."""
    failures: list[str] = []
    keys = ["season", "week", "id"]
    required = {
        *keys, "pos", "salary", "actual", "market_points",
        "model_points_pre", "mean_projection", "model_ensemble_size",
        "model_member_spec", "ensemble_point_0", "ensemble_point_1",
        "ensemble_point_2",
    }
    for name, frame in (("source", source_features),
                        ("treatment", treatment_features)):
        missing = required - set(frame.columns)
        if missing:
            failures.append(f"{name} feature snapshot missing {sorted(missing)}")
        elif frame.empty or frame.duplicated(keys).any():
            failures.append(f"{name} feature snapshot empty or duplicate")
    if failures:
        return {}, failures

    expected_source = ensemble_member_specs({"MODEL_ENSEMBLE": "3"})
    expected_treatment = ensemble_member_specs({"MODEL_ENSEMBLE": "1"})
    expected_source_json = json.dumps(
        expected_source, separators=(",", ":"), sort_keys=True)
    expected_treatment_json = json.dumps(
        expected_treatment, separators=(",", ":"), sort_keys=True)

    seed_rest_source, seed_ensemble_source = _split_seed_provenance(source_seeds)
    seed_rest_treatment, seed_ensemble_treatment = _split_seed_provenance(
        treatment_seeds)
    if seed_rest_source != seed_rest_treatment:
        failures.append("source and treatment non-ensemble seeds differ")
    if seed_ensemble_source != {
            "size": "3", "spec": expected_source_json}:
        failures.append("source seed provenance does not identify adopted K=3")
    if seed_ensemble_treatment != {
            "size": "1", "spec": expected_treatment_json}:
        failures.append("treatment seed provenance does not identify K=1")

    for name, frame, expected_size, expected_json in (
            ("source", source_features, 3, expected_source_json),
            ("treatment", treatment_features, 1, expected_treatment_json)):
        sizes = pd.to_numeric(
            frame.model_ensemble_size, errors="coerce").dropna().unique()
        specs = frame.model_member_spec.dropna().astype(str).unique()
        if len(sizes) != 1 or int(sizes[0]) != expected_size:
            failures.append(
                f"{name} feature snapshot does not uniformly record K={expected_size}")
        if len(specs) != 1 or specs[0] != expected_json:
            failures.append(f"{name} feature member specification is wrong")

    joined = source_features.merge(
        treatment_features, on=keys, how="outer",
        suffixes=("_source", "_treatment"), indicator=True,
        validate="one_to_one")
    if not joined._merge.eq("both").all():
        failures.append("source/treatment player universes differ")
    joined = joined[joined._merge.eq("both")].copy()

    input_mismatches: dict[str, int] = {}
    for col in ("pos", "salary", "actual", "market_points"):
        source_col = joined[f"{col}_source"]
        treatment_col = joined[f"{col}_treatment"]
        null_mismatch = source_col.isna() != treatment_col.isna()
        if pd.api.types.is_numeric_dtype(source_col):
            value_mismatch = (source_col - treatment_col).abs().fillna(0).gt(1e-8)
        else:
            value_mismatch = source_col.fillna("").ne(treatment_col.fillna(""))
        count = int((null_mismatch | value_mismatch).sum())
        input_mismatches[col] = count
        if count:
            failures.append(f"source/treatment {col} inputs differ")

    offense = joined.pos_source.ne("DST")
    source_members = joined.loc[offense, [
        "ensemble_point_0_source", "ensemble_point_1_source",
        "ensemble_point_2_source"]]
    treatment_member_0 = joined.loc[offense, "ensemble_point_0_treatment"]
    treatment_extra = joined.loc[offense, [
        "ensemble_point_1_treatment", "ensemble_point_2_treatment"]]
    if source_members.isna().any(axis=None):
        failures.append("source offense is missing one or more K=3 predictions")
    if treatment_member_0.isna().any():
        failures.append("treatment offense is missing its K=1 prediction")
    if treatment_extra.notna().any(axis=None):
        failures.append("treatment unexpectedly persisted extra model members")

    source_spread = source_members.max(axis=1) - source_members.min(axis=1)
    source_member_mean = source_members.mean(axis=1)
    member_ablation_delta = (
        source_member_mean - treatment_member_0).abs()
    model_mean_delta = (
        joined.loc[offense, "model_points_pre_source"]
        - joined.loc[offense, "model_points_pre_treatment"]).abs()
    if not len(source_spread) or not source_spread.gt(1e-8).any():
        failures.append("source K=3 members have no observed disagreement")
    if (not len(member_ablation_delta)
            or not member_ablation_delta.gt(1e-6).any()):
        failures.append("K=1 predictions do not differ from the K=3 member mean")
    # ``model_points_pre`` is the mean *after* marginal shaping, not the raw
    # component-model point prediction.  The adopted TabPFN shaper replaces
    # each player's complete marginal from a key-addressed quantile cache
    # while preserving the component simulator's ordinal copula.  With full
    # cache coverage, K=1 and K=3 should therefore have identical persisted
    # player means even though their joint lineup worlds differ.  On an
    # empirical fallback the means can move.  The member identities and
    # ``member_ablation_delta`` above prove the upstream lever fired; do not
    # impose an invalid direction on this downstream diagnostic.

    for name, audit in (("source", source_mean_audit),
                        ("treatment", treatment_mean_audit)):
        if not audit["candidate_rows"]:
            failures.append(f"{name} candidate mean audit is empty")
        if audit["duplicate_feature_keys"]:
            failures.append(f"{name} feature keys are duplicate")
        if audit["missing_roster_players"]:
            failures.append(f"{name} candidate/player join is incomplete")
        if audit["max_abs_error"] > 1e-3:
            failures.append(f"{name} candidate world means do not equal player means")

    report = {
        "source_ensemble_size": 3,
        "treatment_ensemble_size": 1,
        "offense_player_weeks": int(offense.sum()),
        "source_rows_with_member_disagreement": int(source_spread.gt(1e-8).sum()),
        "source_member_mean_spread": (
            float(source_spread.mean()) if len(source_spread) else 0.0),
        "source_member_max_spread": (
            float(source_spread.max()) if len(source_spread) else 0.0),
        "k1_vs_k3_mean_abs_delta": (
            float(member_ablation_delta.mean())
            if len(member_ablation_delta) else 0.0),
        "post_shaping_model_mean_abs_delta": (
            float(model_mean_delta.mean()) if len(model_mean_delta) else 0.0),
        "post_shaping_model_mean_changed_rows": int(
            model_mean_delta.gt(1e-6).sum()),
        "unchanged_input_mismatch_rows": input_mismatches,
        "non_ensemble_seeds_match": seed_rest_source == seed_rest_treatment,
        "source_candidate_mean_max_abs_error": source_mean_audit["max_abs_error"],
        "treatment_candidate_mean_max_abs_error": treatment_mean_audit["max_abs_error"],
    }
    return report, failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="accepted/promoted same-image baseline")
    ap.add_argument("treatment", help="accepted staging ablation")
    ap.add_argument("--mechanism", choices=("blend", "ensemble"))
    ap.add_argument("--output")
    a = ap.parse_args()
    source = _candidates(a.source, promoted=True)
    treatment = _candidates(a.treatment, promoted=False)
    failures = (_validate_panel("source", source)
                + _validate_panel("treatment", treatment))
    if not source.empty and not treatment.empty:
        if source.code_sha.iloc[0] != treatment.code_sha.iloc[0]:
            failures.append("source and treatment code SHA differ")
        if source.config_hash.iloc[0] != treatment.config_hash.iloc[0]:
            failures.append("source and treatment config hashes differ")
        if (a.mechanism != "ensemble"
                and source.seeds.iloc[0] != treatment.seeds.iloc[0]):
            failures.append("source and treatment seeds differ")
    ss = slate_scores(source) if not source.empty else pd.DataFrame()
    ts = slate_scores(treatment) if not treatment.empty else pd.DataFrame()
    treatment_gate, seasons = ({}, pd.DataFrame())
    incumbent_gate = {}
    if not ss.empty and not ts.empty:
        treatment_gate, seasons = directional_gate(ss, ts)
        incumbent_gate, _ = directional_gate(ts, ss)
    mechanism_report: dict = {}
    if a.mechanism == "blend" and not source.empty and not treatment.empty:
        mechanism_report, mechanism_failures = _blend_mechanism(
            _features(a.source, True), _features(a.treatment, False),
            _candidate_mean_audit(a.source, True),
            _candidate_mean_audit(a.treatment, False),
            _no_market_reproduction(a.source, a.treatment))
        failures.extend(mechanism_failures)
    elif a.mechanism == "ensemble" and not source.empty and not treatment.empty:
        mechanism_report, mechanism_failures = _ensemble_mechanism(
            _ensemble_features(a.source, True),
            _ensemble_features(a.treatment, False),
            _candidate_mean_audit(a.source, True),
            _candidate_mean_audit(a.treatment, False),
            str(source.seeds.iloc[0]), str(treatment.seeds.iloc[0]))
        failures.extend(mechanism_failures)
    if failures:
        disposition = "invalid"
    elif treatment_gate.get("passes"):
        disposition = "remove-improves"
    elif incumbent_gate.get("passes"):
        disposition = "incumbent-supported"
    else:
        disposition = "unsupported-neutral"
    report = {
        "source": a.source,
        "treatment": a.treatment,
        "source_metrics": metrics(ss) if not ss.empty else {},
        "treatment_metrics": metrics(ts) if not ts.empty else {},
        "season_metrics": seasons.to_dict("records"),
        "ablation_improves_gate": treatment_gate,
        "incumbent_supported_gate": incumbent_gate,
        "mechanism": mechanism_report,
        "disposition": disposition,
        "failures": failures,
    }
    payload = json.dumps(report, indent=2, sort_keys=True)
    # Cloud Logging recognizes this compact record as one structured
    # jsonPayload entry. Pretty-printed stdout can be split and interleaved,
    # while --output remains human-readable for local callers.
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    if a.output:
        Path(a.output).write_text(payload + "\n")
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
