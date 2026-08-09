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
    directional_gate, high_tail_gate, metrics, slate_scores)


def _panel_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"invalid panel id {value!r}")
    return value


def _candidates(panel: str, promoted: bool) -> pd.DataFrame:
    table = "replay_candidates" if promoted else "replay_candidates_staging"
    eligibility = "AND research_eligible" if promoted else ""
    return query_df(f"""
        SELECT season, week, cand_ix, players, selected, actual_score,
               sim_mean, salary, code_sha, config_hash, lever_env, seeds
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


def _split_member_world_seed(value: str) -> tuple[str, str | None]:
    """Separate the research-only coherent-member seed from all others."""
    member_seed: str | None = None
    rest: list[str] = []
    for item in str(value or "").split(";"):
        if item.startswith("ENSEMBLE_WORLD_SEED="):
            member_seed = item.split("=", 1)[1]
        elif item:
            rest.append(item)
    return ";".join(rest), member_seed


def _validate_panel(name: str, rows: pd.DataFrame,
                    entries_expected: int = 40) -> list[str]:
    failures: list[str] = []
    if rows.empty:
        return [f"{name} is empty"]
    slates = slate_scores(rows)
    if len(slates) != 107:
        failures.append(f"{name} has {len(slates)} slates, want 107")
    if not slates.n_selected.eq(entries_expected).all():
        failures.append(
            f"{name} does not select exactly {entries_expected} every slate")
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


def _member_world_pair_audit(source: str, treatment: str) -> dict:
    """Compute candidate/support movement in BigQuery without huge downloads."""
    result = query_df(f"""
        WITH source_rows AS (
          SELECT season, week, cand_ix, players, selected, actual_score,
                 p_line, sim_mean, clear_bits_194
          FROM `{settings.predictions}.replay_candidates`
          WHERE panel_run_id = '{_panel_id(source)}' AND research_eligible
        ), treatment_rows AS (
          SELECT season, week, cand_ix, players, selected, actual_score,
                 p_line, sim_mean, clear_bits_194
          FROM `{settings.predictions}.replay_candidates_staging`
          WHERE panel_run_id = '{_panel_id(treatment)}'
        ), paired AS (
          SELECT s.*, t.cand_ix AS treatment_cand_ix,
                 t.players AS treatment_players,
                 t.selected AS treatment_selected,
                 t.actual_score AS treatment_actual_score,
                 t.p_line AS treatment_p_line,
                 t.sim_mean AS treatment_sim_mean,
                 t.clear_bits_194 AS treatment_clear_bits_194
          FROM source_rows s FULL OUTER JOIN treatment_rows t
          USING (season, week, cand_ix)
        ), source_selected AS (
          SELECT season, week, players FROM source_rows WHERE selected
        ), treatment_selected AS (
          SELECT season, week, players FROM treatment_rows WHERE selected
        ), selected_pair AS (
          SELECT s.players AS source_players, t.players AS treatment_players
          FROM source_selected s FULL OUTER JOIN treatment_selected t
          USING (season, week, players)
        )
        SELECT
          (SELECT COUNT(*) FROM source_rows) AS source_rows,
          (SELECT COUNT(*) FROM treatment_rows) AS treatment_rows,
          COUNTIF(cand_ix IS NULL OR treatment_cand_ix IS NULL) AS missing_rows,
          COUNTIF(cand_ix IS NOT NULL AND treatment_cand_ix IS NOT NULL
                  AND players != treatment_players) AS roster_mismatch,
          COUNTIF(cand_ix IS NOT NULL AND treatment_cand_ix IS NOT NULL
                  AND clear_bits_194 != treatment_clear_bits_194)
                  AS support_mismatch,
          COUNTIF(cand_ix IS NOT NULL AND treatment_cand_ix IS NOT NULL
                  AND ABS(p_line - treatment_p_line) > 1e-8)
                  AS p_line_mismatch,
          COUNTIF(cand_ix IS NOT NULL AND treatment_cand_ix IS NOT NULL
                  AND ABS(sim_mean - treatment_sim_mean) > 1e-6)
                  AS sim_mean_mismatch,
          COUNTIF(cand_ix IS NOT NULL AND treatment_cand_ix IS NOT NULL
                  AND players = treatment_players
                  AND ABS(actual_score - treatment_actual_score) > 1e-8)
                  AS same_roster_actual_mismatch,
          (SELECT COUNTIF(source_players IS NOT NULL
                          AND treatment_players IS NOT NULL)
             FROM selected_pair) AS selected_shared,
          (SELECT COUNTIF(source_players IS NOT NULL
                          AND treatment_players IS NULL)
             FROM selected_pair) AS selected_source_only,
          (SELECT COUNTIF(source_players IS NULL
                          AND treatment_players IS NOT NULL)
             FROM selected_pair) AS selected_treatment_only
        FROM paired
        """).iloc[0]
    return {name: int(result.get(name) or 0) for name in result.index}


def _member_world_mechanism(
    source_candidates: pd.DataFrame,
    treatment_candidates: pd.DataFrame,
    source_features: pd.DataFrame,
    treatment_features: pd.DataFrame,
    source_mean_audit: dict,
    treatment_mean_audit: dict,
    pair_audit: dict,
) -> tuple[dict, list[str]]:
    """Prove coherent member-world sampling changed only joint worlds."""
    failures: list[str] = []
    keys = ["season", "week", "id"]
    invariant_columns = (
        "pos", "salary", "actual", "proj", "mean_projection",
        "model_points_pre", "market_points", "model_ensemble_size",
        "model_member_spec", "ensemble_point_0", "ensemble_point_1",
        "ensemble_point_2")
    for name, frame in (("source", source_features),
                        ("treatment", treatment_features)):
        needed = {*keys, *invariant_columns}
        missing = needed - set(frame.columns)
        if missing:
            failures.append(f"{name} feature snapshot missing {sorted(missing)}")
        elif frame.empty or frame.duplicated(keys).any():
            failures.append(f"{name} feature snapshot empty or duplicate")
    if failures:
        return {}, failures

    source_levers = _lever_values(str(source_candidates.lever_env.iloc[0]))
    treatment_levers = _lever_values(
        str(treatment_candidates.lever_env.iloc[0]))
    if source_levers.get("ENSEMBLE_WORLD_MODE", ""):
        failures.append("source unexpectedly enables ensemble world mode")
    if treatment_levers.get("ENSEMBLE_WORLD_MODE") != "member_sample":
        failures.append("treatment does not identify member_sample world mode")

    source_seed_rest, source_member_seed = _split_member_world_seed(
        str(source_candidates.seeds.iloc[0]))
    treatment_seed_rest, treatment_member_seed = _split_member_world_seed(
        str(treatment_candidates.seeds.iloc[0]))
    if source_member_seed is not None:
        failures.append("source unexpectedly records an ensemble-world seed")
    if treatment_member_seed != "8161":
        failures.append("treatment does not record ensemble-world seed 8161")
    if source_seed_rest != treatment_seed_rest:
        failures.append("source/treatment non-member-world seeds differ")

    joined = source_features.merge(
        treatment_features, on=keys, how="outer",
        suffixes=("_source", "_treatment"), indicator=True,
        validate="one_to_one")
    if not joined._merge.eq("both").all():
        failures.append("source/treatment player universes differ")
    joined = joined[joined._merge.eq("both")].copy()
    mismatch_rows: dict[str, int] = {}
    for col in invariant_columns:
        source_col = joined[f"{col}_source"]
        treatment_col = joined[f"{col}_treatment"]
        null_mismatch = source_col.isna() != treatment_col.isna()
        if pd.api.types.is_numeric_dtype(source_col):
            value_mismatch = (
                source_col - treatment_col).abs().fillna(0).gt(1e-8)
        else:
            value_mismatch = source_col.fillna("").ne(
                treatment_col.fillna(""))
        count = int((null_mismatch | value_mismatch).sum())
        mismatch_rows[col] = count
        if count:
            failures.append(f"source/treatment {col} feature rows differ")

    expected_spec = json.dumps(
        ensemble_member_specs({"MODEL_ENSEMBLE": "3"}),
        separators=(",", ":"), sort_keys=True)
    for name, frame in (("source", source_features),
                        ("treatment", treatment_features)):
        sizes = pd.to_numeric(
            frame.model_ensemble_size, errors="coerce").dropna().unique()
        specs = frame.model_member_spec.dropna().astype(str).unique()
        if len(sizes) != 1 or int(sizes[0]) != 3:
            failures.append(f"{name} does not uniformly record K=3")
        if len(specs) != 1 or specs[0] != expected_spec:
            failures.append(f"{name} K=3 member specification is wrong")

    for name, audit in (("source", source_mean_audit),
                        ("treatment", treatment_mean_audit)):
        if (audit["duplicate_feature_keys"]
                or audit["missing_roster_players"]
                or audit["max_abs_error"] > 1e-3):
            failures.append(f"{name} candidate/player mean parity failed")
    changed = (pair_audit.get("missing_rows", 0)
               + pair_audit.get("roster_mismatch", 0)
               + pair_audit.get("support_mismatch", 0))
    if changed <= 0:
        failures.append("member-world mode did not change candidates or support")
    if pair_audit.get("selected_source_only", 0) <= 0:
        failures.append("member-world mode did not remove any selected rosters")
    if pair_audit.get("selected_treatment_only", 0) <= 0:
        failures.append("member-world mode did not add any selected rosters")
    if pair_audit.get("same_roster_actual_mismatch", 0):
        failures.append("same-roster actual scores differ")

    report = {
        "source_mode": source_levers.get("ENSEMBLE_WORLD_MODE", ""),
        "treatment_mode": treatment_levers.get("ENSEMBLE_WORLD_MODE", ""),
        "source_member_world_seed": source_member_seed,
        "treatment_member_world_seed": treatment_member_seed,
        "non_member_world_seeds_match":
            source_seed_rest == treatment_seed_rest,
        "invariant_feature_mismatch_rows": mismatch_rows,
        "candidate_and_support_change": pair_audit,
        "source_candidate_mean_max_abs_error":
            source_mean_audit["max_abs_error"],
        "treatment_candidate_mean_max_abs_error":
            treatment_mean_audit["max_abs_error"],
    }
    return report, failures


def _lever_values(value: str) -> dict[str, str]:
    """Parse the persisted comma-delimited replay lever manifest."""
    out: dict[str, str] = {}
    for item in str(value or "").split(","):
        if "=" in item:
            key, val = item.split("=", 1)
            out[key.strip()] = val.strip()
    return out


def _salary_floor_mechanism(source: pd.DataFrame,
                            treatment: pd.DataFrame,
                            source_features: pd.DataFrame,
                            treatment_features: pd.DataFrame) -> tuple[dict, list[str]]:
    """Prove the $49k lineup-floor deletion fired and nothing upstream moved."""
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
    feature_mismatches: dict[str, int] = {}
    for col in ("pos", "proj", "mean_projection", "model_points_pre",
                "market_points"):
        source_col = joined[f"{col}_source"]
        treatment_col = joined[f"{col}_treatment"]
        null_mismatch = source_col.isna() != treatment_col.isna()
        if pd.api.types.is_numeric_dtype(source_col):
            value_mismatch = (source_col - treatment_col).abs().fillna(0).gt(1e-8)
        else:
            value_mismatch = source_col.fillna("").ne(
                treatment_col.fillna(""))
        count = int((null_mismatch | value_mismatch).sum())
        feature_mismatches[col] = count
        if count:
            failures.append(f"source/treatment {col} features differ")

    source_levers = _lever_values(str(source.lever_env.iloc[0]))
    treatment_levers = _lever_values(str(treatment.lever_env.iloc[0]))
    source_floor = int(source_levers.get("MIN_LINEUP_SALARY", "49000") or 0)
    treatment_floor = int(
        treatment_levers.get("MIN_LINEUP_SALARY", "49000") or 0)
    if source_floor != 49_000:
        failures.append("source does not identify the default $49k floor")
    if treatment_floor != 0:
        failures.append("treatment does not identify salary-floor deletion")

    def salary_report(frame: pd.DataFrame) -> dict:
        salary = pd.to_numeric(frame.salary, errors="coerce")
        selected = frame.selected.astype(bool)
        selected_salary = salary[selected]
        return {
            "rows": int(len(frame)),
            "missing_salary_rows": int(salary.isna().sum()),
            "below_49000_rows": int(salary.lt(49_000).sum()),
            "below_49000_selected": int((salary.lt(49_000) & selected).sum()),
            "salary_min": float(salary.min()),
            "salary_median": float(salary.median()),
            "salary_p10": float(salary.quantile(0.10)),
            "selected_salary_min": float(selected_salary.min()),
            "selected_salary_median": float(selected_salary.median()),
            "selected_salary_p10": float(selected_salary.quantile(0.10)),
        }

    source_salary = salary_report(source)
    treatment_salary = salary_report(treatment)
    if source_salary["missing_salary_rows"] or treatment_salary["missing_salary_rows"]:
        failures.append("candidate salary is missing")
    if source_salary["below_49000_rows"]:
        failures.append("source contains candidates below its $49k floor")
    if not treatment_salary["below_49000_rows"]:
        failures.append("salary-floor deletion generated no sub-$49k candidates")

    source_selected = source[source.selected].loc[:, ["season", "week", "players"]]
    treatment_selected = treatment[treatment.selected].loc[
        :, ["season", "week", "players"]]
    selected_join = source_selected.merge(
        treatment_selected, on=["season", "week", "players"], how="outer",
        indicator=True)
    report = {
        "source_floor": source_floor,
        "treatment_floor": treatment_floor,
        "unchanged_feature_mismatch_rows": feature_mismatches,
        "source_salary": source_salary,
        "treatment_salary": treatment_salary,
        "selected_rosters_shared": int(selected_join._merge.eq("both").sum()),
        "selected_rosters_source_only": int(
            selected_join._merge.eq("left_only").sum()),
        "selected_rosters_treatment_only": int(
            selected_join._merge.eq("right_only").sum()),
    }
    return report, failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="accepted/promoted same-image baseline")
    ap.add_argument("treatment", help="accepted staging ablation")
    ap.add_argument("--mechanism", choices=(
        "blend", "ensemble", "salary", "member_world"))
    ap.add_argument("--entries-expected", type=int, default=40)
    ap.add_argument("--output")
    a = ap.parse_args()
    if not 1 <= a.entries_expected <= 150:
        ap.error("--entries-expected must be from 1 through 150")
    source = _candidates(a.source, promoted=True)
    treatment = _candidates(a.treatment, promoted=False)
    failures = (_validate_panel("source", source, a.entries_expected)
                + _validate_panel(
                    "treatment", treatment, a.entries_expected))
    if not source.empty and not treatment.empty:
        if source.code_sha.iloc[0] != treatment.code_sha.iloc[0]:
            failures.append("source and treatment code SHA differ")
        if source.config_hash.iloc[0] != treatment.config_hash.iloc[0]:
            failures.append("source and treatment config hashes differ")
        if (a.mechanism not in ("ensemble", "member_world")
                and source.seeds.iloc[0] != treatment.seeds.iloc[0]):
            failures.append("source and treatment seeds differ")
    ss = slate_scores(source) if not source.empty else pd.DataFrame()
    ts = slate_scores(treatment) if not treatment.empty else pd.DataFrame()
    treatment_gate, seasons = ({}, pd.DataFrame())
    incumbent_gate = {}
    tail_gate, tail_seasons = ({}, pd.DataFrame())
    if not ss.empty and not ts.empty:
        treatment_gate, seasons = directional_gate(ss, ts)
        incumbent_gate, _ = directional_gate(ts, ss)
        tail_gate, tail_seasons = high_tail_gate(ss, ts, threshold=200.0)
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
    elif a.mechanism == "salary" and not source.empty and not treatment.empty:
        mechanism_report, mechanism_failures = _salary_floor_mechanism(
            source, treatment, _features(a.source, True),
            _features(a.treatment, False))
        failures.extend(mechanism_failures)
    elif (a.mechanism == "member_world"
          and not source.empty and not treatment.empty):
        mechanism_report, mechanism_failures = _member_world_mechanism(
            source, treatment,
            _ensemble_features(a.source, True),
            _ensemble_features(a.treatment, False),
            _candidate_mean_audit(a.source, True),
            _candidate_mean_audit(a.treatment, False),
            _member_world_pair_audit(a.source, a.treatment))
        failures.extend(mechanism_failures)
    if failures:
        disposition = "invalid"
    elif treatment_gate.get("passes"):
        disposition = "remove-improves"
    elif incumbent_gate.get("passes"):
        disposition = "incumbent-supported"
    else:
        disposition = "unsupported-neutral"
    if tail_gate:
        tail_gate["clear_194_not_worse"] = int(
            (ts.selected_best >= 194).sum()) >= int(
                (ss.selected_best >= 194).sum())
        tail_gate["clear_210_not_worse"] = int(
            (ts.selected_best >= 210).sum()) >= int(
                (ss.selected_best >= 210).sum())
        tail_gate["oracle_200_not_worse"] = int(
            (ts.oracle >= 200).sum()) >= int((ss.oracle >= 200).sum())
        tail_gate["mechanism_and_panel_valid"] = not failures
        tail_gate["passes"] = all(
            value for key, value in tail_gate.items() if key != "passes")
    report = {
        "source": a.source,
        "treatment": a.treatment,
        "entries_expected": a.entries_expected,
        "source_metrics": metrics(ss) if not ss.empty else {},
        "treatment_metrics": metrics(ts) if not ts.empty else {},
        "season_metrics": seasons.to_dict("records"),
        "ablation_improves_gate": treatment_gate,
        "incumbent_supported_gate": incumbent_gate,
        "high_tail_200_gate": tail_gate,
        "high_tail_200_season_metrics": tail_seasons.to_dict("records"),
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
