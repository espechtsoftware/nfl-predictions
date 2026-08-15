"""Fail-closed primitives for the final preseason forensic closure.

This module deliberately separates two phases:

* manifest/inventory validation is outcome-free and is safe before the freeze;
* H/P/C/S decomposition consumes realized scores only after the manifest
  containing the immutable analyzer image has been committed.

The functions are pure apart from reading files supplied by the caller.  Cloud
and BigQuery access belongs in the guarded launcher/analyzer scripts so tests
can exercise every invariant offline.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import pulp


PROTOCOL_ID = "20260814-final-preseason-forensic-v1"
TAILS = (240, 230, 220, 210, 200, 194, 187)
BETWEEN_ARM_VARIANCE_PANEL_IDS = (
    "20260807-livefaithful-b2-91d596e",
    "20260807-trusted-b0-ef6d31c",
    "20260808-deterministic-baseline-c616390",
    "20260808-e80-k1-c616390",
    "20260808-e80-k3-c616390",
    "20260808-e80-msctl-d99b125",
    "20260808-livefaithful-b3-ee6f433",
    "20260809-e80-k1-ce12-c616390",
    "20260810-lockfix-e80-k1-8677d21",
    "20260810-lockfix-e80-k1-role12union-8677d21",
    "20260810-lockfix-e80-k3-8677d21",
    "20260811-pitclean-e80-k1-a12ab31",
    "20260811-pitclean-e80-k1-role12union-a12ab31",
    "20260811-pitclean-e80-k3-a12ab31",
)
REQUIRED_OUTPUTS = (
    "provenance_and_arm_ledger",
    "opportunity_decomposition",
    "portfolio_entry_count_and_money",
    "player_capture_calibration_and_dependence",
    "construction_selection_regime_and_data_quality",
    "experiment_meta_analysis_and_kill_list",
    "week1_operational_readiness",
    "prospective_charter_and_opportunity_register",
    "exhaustion_certificate",
)
REQUIRED_MECHANISM_FAMILIES = (
    "player_marginals_and_calibration",
    "availability_and_role_change",
    "market_and_vendor_data",
    "game_and_player_dependence",
    "candidate_generation",
    "roster_construction",
    "decision_structure",
    "portfolio_selection",
    "ownership_and_field_modeling",
    "contest_choice",
    "entry_count_and_bankroll",
    "data_and_pit_integrity",
    "operations",
)
REQUIRED_FORENSIC_ARTIFACT_PATHS = (
    "reports/milly-winners-2019-2023-2024.csv",
    "reports/2025-milly-winners.csv",
    "reports/2025-milly-rosters.csv",
    (
        "reports/g0-dependence-runs/"
        "20260812-g0-final-served-dependence-v2/report.json"
    ),
    (
        "reports/g1-topology-runs/"
        "20260812-g1-archetype-topology-v3/report.json"
    ),
    (
        "reports/portfolio-effective-rank-runs/"
        "20260813-incumbent-effective-rank-v2/report.json"
    ),
    (
        "reports/multiseed-candidate-world-runs/"
        "20260813-multiseed-candidate-world-v1/report.json"
    ),
    (
        "reports/selector-resampling-runs/"
        "20260814-selector-resampling-v1/report.json"
    ),
    (
        "reports/tabpfn-sis-pass-tail-runs/"
        "20260814-sis-pass-tail-exact80-v1/report.json"
    ),
)
ANALYSIS_CHECKLIST = (
    ("provenance_and_terminal_arm_ledger", "confirmatory", "compute"),
    ("authoritative_score_salary_legality_parity", "confirmatory", "compute"),
    ("hpcs_additive_opportunity_decomposition", "confirmatory", "compute"),
    ("exact80_tail_grid_and_weekly_maxima", "confirmatory", "compute"),
    ("nested_20_40_80_entry_curve", "confirmatory", "compute"),
    ("contest_payout_roi_cash_drawdown", "confirmatory", "compute_or_unidentifiable"),
    ("winner_places_2_through_5_comparison", "confirmatory", "compute_or_unidentifiable"),
    ("salary_to_selected_player_capture_funnel", "confirmatory", "compute"),
    ("served_marginal_calibration_and_rank", "confirmatory", "compute"),
    ("candidate_signal_rank_and_probability_skill", "confirmatory", "compute"),
    ("unselected_high_score_near_miss_frontier", "confirmatory", "compute"),
    ("generator_tag_yield_and_overlap", "exploratory", "compute"),
    ("route_share_pool_admission_bound", "exploratory", "compute"),
    ("roster_construction_shape_inventory", "exploratory", "compute"),
    ("salary_and_positional_spend", "exploratory", "compute"),
    ("selected_exposure_vs_realized_value", "exploratory", "compute"),
    ("historical_ownership_and_duplication_proxy", "exploratory", "compute_or_unidentifiable"),
    ("joint_score_and_tail_dependence", "confirmatory", "reference_frozen"),
    ("paired_nonstationary_evt_diagnostic", "exploratory", "compute"),
    ("late_swap_recourse_ceiling", "exploratory", "compute"),
    ("effective_rank_spectral_and_random_controls", "exploratory", "reference_frozen"),
    ("slate_relative_rank_ap_and_ndcg", "exploratory", "compute"),
    ("winner_inverse_belief_distance", "exploratory", "compute_or_unidentifiable"),
    ("prelock_regime_splits", "exploratory", "compute"),
    ("within_season_failure_autocorrelation", "exploratory", "compute"),
    ("season_drift_and_leave_one_season_out", "exploratory", "compute"),
    ("feature_missingness_error_census", "exploratory", "compute"),
    ("source_pit_join_backup_readiness_census", "confirmatory", "compute"),
    ("panel_factor_design_rank_and_estimability", "exploratory", "compute"),
    ("between_arm_variance_common_slates", "exploratory", "compute"),
    ("corpus_understanding_toolkit", "exploratory", "compute"),
    ("arm_effect_breadth_uncertainty_and_kill_list", "exploratory", "compute"),
    ("cloud_runtime_data_cost_census", "exploratory", "compute_or_unidentifiable"),
    ("prospective_opportunity_register_and_charter", "exploratory", "compute"),
    ("week1_end_to_end_dress_rehearsal", "confirmatory", "pending_external"),
    ("adversarial_exhaustion_certificate", "confirmatory", "compute"),
    ("independent_deterministic_reproduction", "confirmatory", "post_review_gate"),
    ("forensic_corpus_cleanup_before_production", "confirmatory", "post_review_gate"),
)
WAREHOUSE_TABLE_SCHEMAS = {
    "player_corpus": [
        {"name": "manifest_sha256", "type": "STRING", "mode": "REQUIRED"},
        {"name": "analysis_code_sha", "type": "STRING", "mode": "REQUIRED"},
        {"name": "analysis_image", "type": "STRING", "mode": "REQUIRED"},
        {"name": "scope", "type": "STRING", "mode": "REQUIRED"},
        {"name": "season", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "week", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "slate_run_id", "type": "STRING", "mode": "NULLABLE"},
        {"name": "player_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "player_name", "type": "STRING", "mode": "REQUIRED"},
        {"name": "position", "type": "STRING", "mode": "REQUIRED"},
        {"name": "team", "type": "STRING", "mode": "REQUIRED"},
        {"name": "opponent", "type": "STRING", "mode": "REQUIRED"},
        {"name": "game_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "kickoff_time", "type": "STRING", "mode": "REQUIRED"},
        {"name": "salary", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "actual_score", "type": "FLOAT", "mode": "REQUIRED"},
        {"name": "mean_projection", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "proj_p10", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "proj_p50", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "proj_p90", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "proj_std", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "fp_route_source_season", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "fp_route_source_week", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "fp_route_prior_observations", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "fp_route_share_last", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "fp_route_share_l4", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "fp_route_share_jump", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "fp_route_cross_season", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "estimated_ownership", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "actual_ownership", "type": "FLOAT", "mode": "NULLABLE"},
        {
            "name": "actual_ownership_contests", "type": "INTEGER",
            "mode": "NULLABLE",
        },
        {"name": "feature_missing", "type": "STRING", "mode": "REQUIRED"},
        {"name": "feature_missing_any", "type": "BOOLEAN", "mode": "REQUIRED"},
        {"name": "source_features_json", "type": "STRING", "mode": "REQUIRED"},
    ],
    "candidate_corpus": [
        {"name": "manifest_sha256", "type": "STRING", "mode": "REQUIRED"},
        {"name": "analysis_code_sha", "type": "STRING", "mode": "REQUIRED"},
        {"name": "analysis_image", "type": "STRING", "mode": "REQUIRED"},
        {"name": "scope", "type": "STRING", "mode": "REQUIRED"},
        {"name": "season", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "week", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "panel_run_id", "type": "STRING", "mode": "NULLABLE"},
        {"name": "source_seed", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "candidate_index", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "roster_ordered", "type": "STRING", "mode": "REQUIRED"},
        {"name": "roster_key", "type": "STRING", "mode": "REQUIRED"},
        {"name": "salary", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "actual_score", "type": "FLOAT", "mode": "REQUIRED"},
        {"name": "selected", "type": "BOOLEAN", "mode": "REQUIRED"},
        {"name": "selected_rank", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "p_line", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "sim_mean", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "sim_q99", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "tag", "type": "STRING", "mode": "NULLABLE"},
        {"name": "all_tags", "type": "STRING", "mode": "NULLABLE"},
        {"name": "source_candidate_json", "type": "STRING", "mode": "REQUIRED"},
    ],
    "actual_selections": [
        {"name": "manifest_sha256", "type": "STRING", "mode": "REQUIRED"},
        {"name": "analysis_code_sha", "type": "STRING", "mode": "REQUIRED"},
        {"name": "analysis_image", "type": "STRING", "mode": "REQUIRED"},
        {"name": "scope", "type": "STRING", "mode": "REQUIRED"},
        {"name": "season", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "week", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "selected_rank", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "candidate_index", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "roster_ordered", "type": "STRING", "mode": "REQUIRED"},
        {"name": "roster_key", "type": "STRING", "mode": "REQUIRED"},
        {"name": "salary", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "actual_score", "type": "FLOAT", "mode": "REQUIRED"},
        {"name": "p_line", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "sim_mean", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "sim_q99", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "tag", "type": "STRING", "mode": "NULLABLE"},
        {"name": "all_tags", "type": "STRING", "mode": "NULLABLE"},
        {"name": "source_candidate_json", "type": "STRING", "mode": "REQUIRED"},
    ],
    "oracle_rosters": [
        {"name": "manifest_sha256", "type": "STRING", "mode": "REQUIRED"},
        {"name": "analysis_code_sha", "type": "STRING", "mode": "REQUIRED"},
        {"name": "analysis_image", "type": "STRING", "mode": "REQUIRED"},
        {"name": "scope", "type": "STRING", "mode": "REQUIRED"},
        {"name": "season", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "week", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "layer", "type": "STRING", "mode": "REQUIRED"},
        {"name": "roster_key", "type": "STRING", "mode": "REQUIRED"},
        {"name": "salary", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "actual_score", "type": "FLOAT", "mode": "REQUIRED"},
        {"name": "solver_status", "type": "STRING", "mode": "NULLABLE"},
        {"name": "legality_verified", "type": "BOOLEAN", "mode": "REQUIRED"},
        {"name": "player_support_gap", "type": "FLOAT", "mode": "REQUIRED"},
        {"name": "construction_gap", "type": "FLOAT", "mode": "REQUIRED"},
        {"name": "selection_gap", "type": "FLOAT", "mode": "REQUIRED"},
    ],
}
WAREHOUSE_TABLE_PREFIX = (
    "nfl-predictions-503414.nfl_forensic_review.final_forensic_20260814_"
)
LEDGER_STATUSES = frozenset({
    "selected",
    "rejected",
    "neutral",
    "invalid_repaired",
    "invalid_unadjudicated",
    "not_run_prerequisite_failed",
    "prospective_only",
    "duplicate_mechanism",
    "operational_complete",
    "deferred_with_falsifier",
})
REQUIRED_LEDGER_FIELDS = frozenset({
    "id",
    "family",
    "stage",
    "status",
    "protocol_paths",
    "result_paths",
    "execution_ids",
    "gate",
    "operator_override",
    "cloud_cost_status",
    "production_relevance",
    "transfer_boundary",
})
OUTPUT_SCHEMAS = {
    "provenance_and_arm_ledger": [
        "manifest_sha256", "production", "panels", "arm_ledger",
        "report_inventory", "artifact_inventory", "warehouse_retention",
        "analysis_checklist",
    ],
    "opportunity_decomposition": [
        "season", "week", "scope", "H", "P", "C", "S", "gaps",
        "thresholds", "first_failed_layer",
    ],
    "portfolio_entry_count_and_money": [
        "scope", "entry_count", "portfolio_prefix", "contest_assumptions",
        "payout_scenarios", "duplication_scenarios", "roi_bounds",
    ],
    "player_capture_calibration_and_dependence": [
        "position", "tail_bucket", "support_capture", "calibration",
        "dependence", "known_winner_context",
    ],
    "construction_selection_regime_and_data_quality": [
        "mechanism", "regime", "construction_gap", "selection_gap",
        "distinct_improved_slates", "distinct_worsened_slates",
        "data_quality",
    ],
    "experiment_meta_analysis_and_kill_list": [
        "arm_id", "family", "status", "effect", "breadth", "uncertainty",
        "cost", "kill_reason", "falsifier",
    ],
    "week1_operational_readiness": [
        "check", "status", "evidence", "owner_action", "deadline",
    ],
    "prospective_charter_and_opportunity_register": [
        "item", "priority", "predeclared_question", "trigger", "decision_law",
        "transfer_boundary",
    ],
    "exhaustion_certificate": [
        "taxonomy_family", "terminal_arms", "open_historical_arms",
        "prospective_items", "falsifier", "certified",
    ],
}
TAXONOMY_RULES = {
    family: {
        "disposition_rule": (
            "Every historical arm in this family must be selected, rejected, "
            "neutral, repaired, invalid-unadjudicated, prerequisite-closed, prospective-only, "
            "duplicate, operationally complete, or deferred with a falsifier."
        ),
        "falsifier_rule": (
            "Reopen only with outcome-unseen prospective evidence, a genuinely "
            "new data grain/mechanism, or a documented integrity defect that "
            "invalidates the cited evidence."
        ),
    }
    for family in REQUIRED_MECHANISM_FAMILIES
}


class FreezeManifestError(ValueError):
    """Raised when a closure freeze is incomplete or internally inconsistent."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def report_inventory(
    repo_root: str | Path,
    paths: Iterable[str | Path] | None = None,
) -> list[dict[str, Any]]:
    """Return a deterministic byte-level inventory of tracked report inputs."""
    root = Path(repo_root).resolve()
    selected = paths
    if selected is None:
        selected = sorted((root / "reports").glob("*.md"))
    rows: list[dict[str, Any]] = []
    for value in selected:
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        path = path.resolve()
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise FreezeManifestError(f"report outside repository: {path}") from exc
        if not path.is_file():
            raise FreezeManifestError(f"missing report: {relative}")
        name = path.name
        if name.endswith("-protocol.md"):
            kind = "protocol"
        elif name.endswith("-result.md"):
            kind = "result"
        elif "reconciliation" in name:
            kind = "reconciliation"
        elif "review" in name or "feedback" in name:
            kind = "review"
        elif "plan" in name or "roadmap" in name or "queue" in name:
            kind = "plan"
        elif "audit" in name or "inventory" in name:
            kind = "audit"
        else:
            kind = "supporting"
        rows.append({
            "path": relative.as_posix(),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "kind": kind,
        })
    return sorted(rows, key=lambda row: row["path"])


def manifest_digest(manifest: Mapping[str, Any]) -> str:
    """Hash canonical JSON, excluding an optional recorded self digest."""
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_freeze_manifest(
    *,
    repo_root: str | Path,
    analysis_image: str,
    analysis_code_sha: str,
    production: Mapping[str, Any],
    panels: Sequence[Mapping[str, Any]],
    between_arm_variance: Mapping[str, Any],
    warehouse_retention: Mapping[str, Any],
    registry_path: str | Path,
    output_root: str = (
        "reports/final-forensic-runs/"
        "20260814-final-preseason-forensic-v1"
    ),
) -> dict[str, Any]:
    """Build the outcome-free manifest from a reviewed terminal registry."""
    root = Path(repo_root).resolve()
    source = Path(registry_path)
    if not source.is_absolute():
        source = root / source
    registry = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(registry, list):
        raise FreezeManifestError("arm registry must be a JSON list")
    ledger: list[dict[str, Any]] = []
    for raw in registry:
        row = dict(raw)
        row.setdefault("execution_ids", [])
        row.setdefault("operator_override", "none")
        row.setdefault(
            "cloud_cost_status", "recorded in cited evidence or not separately metered"
        )
        ledger.append(row)

    artifact_path = source.relative_to(root).as_posix()
    artifact_paths = (artifact_path, *REQUIRED_FORENSIC_ARTIFACT_PATHS)
    artifacts = []
    for path in dict.fromkeys(artifact_paths):
        artifact = root / path
        if not artifact.is_file():
            raise FreezeManifestError(f"missing required artifact: {path}")
        artifacts.append({"path": path, "sha256": sha256_file(artifact)})
    manifest: dict[str, Any] = {
        "protocol_id": PROTOCOL_ID,
        "analysis_image": analysis_image,
        "analysis_code_sha": analysis_code_sha,
        "outcome_query_after_freeze_only": True,
        "production": dict(production),
        "panels": [dict(panel) for panel in panels],
        "between_arm_variance": dict(between_arm_variance),
        "warehouse_retention": dict(warehouse_retention),
        "analysis_checklist": [
            {
                "id": item_id,
                "evidence_class": evidence_class,
                "required_disposition": disposition,
            }
            for item_id, evidence_class, disposition in ANALYSIS_CHECKLIST
        ],
        "artifacts": artifacts,
        "report_inventory": report_inventory(root),
        "protocol_exclusions": [{
            "path": "reports/2026-08-11-final-preseason-forensic-closure-protocol.md",
            "reason": (
                "This is the governing closure protocol being frozen, not a "
                "prior experimental arm."
            ),
        }],
        "result_exclusions": [],
        "arm_ledger": ledger,
        "analysis_contract": [
            {
                "id": output_id,
                "output_path": f"{output_root}/{index:02d}-{output_id}.json",
                "schema": OUTPUT_SCHEMAS[output_id],
            }
            for index, output_id in enumerate(REQUIRED_OUTPUTS, start=1)
        ],
        "mechanism_taxonomy": [
            {"id": family, **TAXONOMY_RULES[family]}
            for family in REQUIRED_MECHANISM_FAMILIES
        ],
    }
    manifest["manifest_sha256"] = manifest_digest(manifest)
    validate_freeze_manifest(manifest, repo_root=root)
    return manifest


def validate_freeze_manifest(
    manifest: Mapping[str, Any],
    *,
    repo_root: str | Path,
    verify_files: bool = True,
) -> dict[str, Any]:
    """Validate the complete pre-outcome forensic freeze contract.

    The validator intentionally rejects open-ended ledger labels, unpinned
    images, unaccounted protocols, and output/taxonomy omissions.  It does not
    inspect or query a realized score.
    """
    root = Path(repo_root).resolve()
    failures: list[str] = []
    if manifest.get("protocol_id") != PROTOCOL_ID:
        failures.append("protocol_id differs")
    image = str(manifest.get("analysis_image", ""))
    if "@sha256:" not in image or len(image.rsplit("@sha256:", 1)[-1]) != 64:
        failures.append("analysis_image is not an immutable sha256 digest")
    code_sha = str(manifest.get("analysis_code_sha", ""))
    if len(code_sha) != 40 or any(
        char not in "0123456789abcdef" for char in code_sha
    ):
        failures.append("analysis_code_sha is not a full lowercase git SHA")
    if manifest.get("outcome_query_after_freeze_only") is not True:
        failures.append("outcome-query firewall is not enabled")
    warehouse = manifest.get("warehouse_retention", {})
    if set(warehouse) != {
        "retention_days", "write_disposition", "extension_policy", "tables",
        "isolation_dataset", "cleanup_policy", "cleanup_deadline",
    }:
        failures.append("warehouse retention contract has unknown/missing fields")
    if warehouse.get("retention_days") != 90:
        failures.append("warehouse retention_days must be exactly 90")
    if warehouse.get("write_disposition") != "WRITE_EMPTY":
        failures.append("warehouse write disposition must be WRITE_EMPTY")
    if warehouse.get("extension_policy") != "extend_only_until_cleanup_deadline":
        failures.append("warehouse extension policy differs")
    if warehouse.get("isolation_dataset") != (
        "nfl-predictions-503414.nfl_forensic_review"
    ):
        failures.append("warehouse isolation dataset differs")
    if warehouse.get("cleanup_policy") != "delete_after_review_before_week1":
        failures.append("warehouse cleanup policy differs")
    if warehouse.get("cleanup_deadline") != "before_first_2026_production_build":
        failures.append("warehouse cleanup deadline differs")
    warehouse_tables = warehouse.get("tables", [])
    table_by_id = {str(row.get("id", "")): row for row in warehouse_tables}
    if len(warehouse_tables) != 4 or set(table_by_id) != set(WAREHOUSE_TABLE_SCHEMAS):
        failures.append("warehouse table inventory is incomplete")
    for table_id, schema in WAREHOUSE_TABLE_SCHEMAS.items():
        row = table_by_id.get(table_id, {})
        table_name = str(row.get("table", ""))
        if set(row) != {"id", "table", "schema"}:
            failures.append(f"warehouse table contract differs: {table_id}")
        if table_name != WAREHOUSE_TABLE_PREFIX + table_id:
            failures.append(f"warehouse table name is invalid: {table_id}")
        if row.get("schema") != schema:
            failures.append(f"warehouse schema differs: {table_id}")
    production = manifest.get("production", {})
    for key in (
        "policy_id", "fallback_policy_id", "service_revision",
        "service_image", "component_panel", "position_panel", "cbwu_panel",
    ):
        if not str(production.get(key, "")).strip():
            failures.append(f"production.{key} is missing")

    between_arm = manifest.get("between_arm_variance", {})
    expected_between_fields = {
        "source_table", "panel_ids", "common_slates", "common_slate_sha256",
        "expected_entries_by_panel", "expected_panel_count",
        "expected_common_slate_count", "estimand", "selection_bias",
        "use_restriction",
    }
    if set(between_arm) != expected_between_fields:
        failures.append("between-arm variance contract has unknown/missing fields")
    if between_arm.get("source_table") != (
        "nfl-predictions-503414.nfl_predictions.replay_candidates"
    ):
        failures.append("between-arm variance source table differs")
    if tuple(between_arm.get("panel_ids", [])) != BETWEEN_ARM_VARIANCE_PANEL_IDS:
        failures.append("between-arm variance panel population differs")
    if between_arm.get("expected_panel_count") != len(
        BETWEEN_ARM_VARIANCE_PANEL_IDS
    ):
        failures.append("between-arm variance panel count differs")
    common_slates = between_arm.get("common_slates", [])
    if between_arm.get("expected_common_slate_count") != 107 or len(
        common_slates
    ) != 107:
        failures.append("between-arm variance common-slate count differs")
    if any(
        not isinstance(row, str)
        or len(row) != 7
        or row[4] != "-"
        or not row[:4].isdigit()
        or not row[5:].isdigit()
        for row in common_slates
    ) or common_slates != sorted(set(common_slates)):
        failures.append("between-arm common-slate identities are malformed")
    canonical_slates = json.dumps(
        common_slates, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if hashlib.sha256(canonical_slates).hexdigest() != between_arm.get(
        "common_slate_sha256"
    ):
        failures.append("between-arm common-slate hash differs")
    entries = between_arm.get("expected_entries_by_panel", {})
    if set(entries) != set(BETWEEN_ARM_VARIANCE_PANEL_IDS) or any(
        value not in {40, 80} for value in entries.values()
    ):
        failures.append("between-arm entry-count contract differs")
    if "may not" not in str(between_arm.get("use_restriction", "")).lower():
        failures.append("between-arm use restriction is not explicit")

    expected_checklist = [
        {
            "id": item_id,
            "evidence_class": evidence_class,
            "required_disposition": disposition,
        }
        for item_id, evidence_class, disposition in ANALYSIS_CHECKLIST
    ]
    if manifest.get("analysis_checklist") != expected_checklist:
        failures.append("analysis checklist is incomplete, altered, or reordered")

    artifacts = manifest.get("artifacts", [])
    artifact_paths = [str(row.get("path", "")) for row in artifacts]
    if len(artifact_paths) != len(set(artifact_paths)):
        failures.append("artifact inventory repeats paths")
    missing_artifacts = set(REQUIRED_FORENSIC_ARTIFACT_PATHS) - set(
        artifact_paths
    )
    if missing_artifacts:
        failures.append(
            "required forensic artifacts are not pinned: "
            f"{sorted(missing_artifacts)}"
        )

    outputs = manifest.get("analysis_contract", [])
    output_ids = [str(item.get("id", "")) for item in outputs]
    if tuple(output_ids) != REQUIRED_OUTPUTS:
        failures.append("analysis_contract does not exactly name nine outputs")
    for item in outputs:
        if not item.get("output_path") or not item.get("schema"):
            failures.append(f"analysis output is incomplete: {item.get('id')}")

    families = manifest.get("mechanism_taxonomy", [])
    family_ids = [str(item.get("id", "")) for item in families]
    if tuple(family_ids) != REQUIRED_MECHANISM_FAMILIES:
        failures.append("mechanism taxonomy is incomplete or reordered")
    for item in families:
        if not item.get("disposition_rule") or not item.get("falsifier_rule"):
            failures.append(f"taxonomy rule is incomplete: {item.get('id')}")

    ledger = manifest.get("arm_ledger", [])
    ledger_ids: set[str] = set()
    referenced_protocols: set[str] = set()
    referenced_results: set[str] = set()
    for row in ledger:
        missing = REQUIRED_LEDGER_FIELDS - set(row)
        if missing:
            failures.append(
                f"ledger {row.get('id', '<unknown>')} lacks {sorted(missing)}"
            )
        arm_id = str(row.get("id", ""))
        if not arm_id or arm_id in ledger_ids:
            failures.append(f"duplicate/empty ledger id: {arm_id!r}")
        ledger_ids.add(arm_id)
        if row.get("status") not in LEDGER_STATUSES:
            failures.append(f"ledger {arm_id} has open status {row.get('status')!r}")
        if row.get("family") not in REQUIRED_MECHANISM_FAMILIES:
            failures.append(f"ledger {arm_id} has unknown family")
        if not str(row.get("gate", "")).strip():
            failures.append(f"ledger {arm_id} has no gate/disposition text")
        if row.get("status") == "deferred_with_falsifier" and not str(
            row.get("transfer_boundary", "")
        ).strip():
            failures.append(f"deferred ledger {arm_id} lacks falsifier boundary")
        referenced_protocols.update(map(str, row.get("protocol_paths", [])))
        referenced_results.update(map(str, row.get("result_paths", [])))

    inventory = manifest.get("report_inventory", [])
    inventory_paths = [str(row.get("path", "")) for row in inventory]
    if len(inventory_paths) != len(set(inventory_paths)):
        failures.append("report_inventory repeats paths")
    protocol_paths = {
        row["path"] for row in inventory if row.get("kind") == "protocol"
    }
    exclusions = manifest.get("protocol_exclusions", [])
    excluded_paths = {str(row.get("path", "")) for row in exclusions}
    for row in exclusions:
        if not str(row.get("reason", "")).strip():
            failures.append(f"protocol exclusion lacks reason: {row.get('path')}")
    unaccounted = protocol_paths - referenced_protocols - excluded_paths
    if unaccounted:
        failures.append(f"unaccounted protocols: {sorted(unaccounted)}")
    overclaimed = referenced_protocols - protocol_paths
    if overclaimed:
        failures.append(f"ledger references uninventoried protocols: {sorted(overclaimed)}")

    result_paths = {
        row["path"] for row in inventory if row.get("kind") == "result"
    }
    result_exclusions = manifest.get("result_exclusions", [])
    excluded_results = {str(row.get("path", "")) for row in result_exclusions}
    for row in result_exclusions:
        if not str(row.get("reason", "")).strip():
            failures.append(f"result exclusion lacks reason: {row.get('path')}")
    unaccounted_results = result_paths - referenced_results - excluded_results
    if unaccounted_results:
        failures.append(f"unaccounted results: {sorted(unaccounted_results)}")
    overclaimed_results = referenced_results - result_paths
    if overclaimed_results:
        failures.append(
            "ledger references uninventoried results: "
            f"{sorted(overclaimed_results)}"
        )

    for panel in manifest.get("panels", []):
        for key in (
            "id", "table", "expected_rows", "expected_slates", "seasons",
            "prelock_row_hash", "estimand", "scope_boundary",
        ):
            if panel.get(key) in (None, "", []):
                failures.append(f"panel {panel.get('id')} lacks {key}")
    if len(manifest.get("panels", [])) < 3:
        failures.append("component, position and CBWU panel scopes are required")

    if verify_files:
        current_inventory = report_inventory(root)
        current_paths = {row["path"] for row in current_inventory}
        frozen_paths = set(inventory_paths)
        if current_paths != frozen_paths:
            failures.append(
                "report inventory membership drift: "
                f"added={sorted(current_paths - frozen_paths)} "
                f"removed={sorted(frozen_paths - current_paths)}"
            )
        for row in inventory:
            path = root / str(row.get("path", ""))
            if not path.is_file():
                failures.append(f"inventoried file missing: {row.get('path')}")
                continue
            if path.stat().st_size != int(row.get("bytes", -1)):
                failures.append(f"inventoried size drift: {row.get('path')}")
            elif sha256_file(path) != row.get("sha256"):
                failures.append(f"inventoried hash drift: {row.get('path')}")
        for artifact in manifest.get("artifacts", []):
            path = root / str(artifact.get("path", ""))
            if not path.is_file():
                failures.append(f"artifact missing: {artifact.get('path')}")
            elif sha256_file(path) != artifact.get("sha256"):
                failures.append(f"artifact hash drift: {artifact.get('path')}")

    recorded_digest = manifest.get("manifest_sha256")
    computed_digest = manifest_digest(manifest)
    if recorded_digest and recorded_digest != computed_digest:
        failures.append("manifest_sha256 differs")
    if failures:
        raise FreezeManifestError("; ".join(failures))
    return {
        "protocol_id": PROTOCOL_ID,
        "manifest_sha256": computed_digest,
        "reports": len(inventory),
        "protocols": len(protocol_paths),
        "ledger_entries": len(ledger),
        "outputs": len(outputs),
        "mechanism_families": len(families),
    }


def _normalise_player_frame(players: pd.DataFrame) -> pd.DataFrame:
    required = {"id", "pos", "team", "opp", "game_id", "salary", "actual"}
    missing = required - set(players)
    if missing:
        raise ValueError(f"player frame lacks {sorted(missing)}")
    frame = players.copy()
    frame["id"] = frame.id.astype(str)
    frame["pos"] = frame.pos.astype(str).str.upper().replace({"DEF": "DST"})
    frame["team"] = frame.team.astype(str)
    frame["opp"] = frame.opp.astype(str)
    # Historical feature snapshots use multiple identifiers for the same game
    # (for example ``2019_01_BUF_NYJ`` for skill players and ``BUF@NYJ`` /
    # ``NYJ@BUF`` for DST).  Game-count and minimum-two-game constraints must
    # therefore use the matchup, not the source-specific display id.
    frame["game_id"] = [
        canonical_game_id(team, opponent)
        for team, opponent in zip(frame.team, frame.opp, strict=True)
    ]
    frame["salary"] = pd.to_numeric(frame.salary, errors="raise").astype(int)
    frame["actual"] = pd.to_numeric(frame.actual, errors="raise").astype(float)
    if frame.id.duplicated().any():
        raise ValueError("player ids repeat within slate")
    if not frame.pos.isin(("QB", "RB", "WR", "TE", "DST")).all():
        raise ValueError("player frame contains an unsupported position")
    if not np.isfinite(frame.actual).all() or not np.isfinite(frame.salary).all():
        raise ValueError("player frame contains non-finite score/salary")
    return frame.sort_values("id", kind="stable").reset_index(drop=True)


def canonical_game_id(team: object, opponent: object) -> str:
    """Return a direction-independent game key from the two team codes."""
    sides = sorted((str(team), str(opponent)))
    if not sides[0] or not sides[1] or sides[0] == sides[1]:
        raise ValueError("cannot construct canonical game id")
    return "|".join(sides)


def audit_roster(
    players: pd.DataFrame,
    roster_ids: Sequence[str],
    *,
    min_salary: int = 49_000,
    salary_cap: int = 50_000,
) -> dict[str, Any]:
    """Independently reconstruct one roster's score and frozen legality."""
    frame = _normalise_player_frame(players).set_index("id", drop=False)
    ids = tuple(map(str, roster_ids))
    failures: list[str] = []
    if len(ids) != 9 or len(set(ids)) != 9:
        failures.append("roster does not contain nine unique ids")
    unknown = sorted(set(ids) - set(frame.index))
    if unknown:
        failures.append(f"unknown player ids: {unknown}")
        chosen = frame.iloc[0:0]
    else:
        chosen = frame.loc[list(ids)]
    counts = chosen.pos.value_counts().to_dict()
    expected = {
        "QB": counts.get("QB", 0) == 1,
        "DST": counts.get("DST", 0) == 1,
        "RB": 2 <= counts.get("RB", 0) <= 3,
        "WR": 3 <= counts.get("WR", 0) <= 4,
        "TE": 1 <= counts.get("TE", 0) <= 2,
    }
    failures.extend(f"invalid {pos} count" for pos, valid in expected.items() if not valid)
    salary = int(chosen.salary.sum())
    if not min_salary <= salary <= salary_cap:
        failures.append("salary outside frozen range")
    if chosen.team.value_counts().max() > 8:
        failures.append("more than eight players from one team")
    if chosen.game_id.nunique() < 2:
        failures.append("fewer than two games")
    qbs = chosen[chosen.pos.eq("QB")]
    if len(qbs) == 1:
        team = str(qbs.iloc[0].team)
        if not ((chosen.team.eq(team)) & chosen.pos.isin(("WR", "TE"))).any():
            failures.append("QB lacks a same-team WR/TE")
    if (chosen[chosen.pos.eq("RB")].team.value_counts() > 1).any():
        failures.append("two RBs from one team")
    dsts = chosen[chosen.pos.eq("DST")]
    if len(dsts) == 1:
        dst_opp = str(dsts.iloc[0].opp)
        if ((chosen.pos.eq("RB")) & chosen.team.eq(dst_opp)).any():
            failures.append("RB faces selected DST")
    return {
        "valid": not failures,
        "failures": failures,
        "salary": salary,
        "actual_score": float(chosen.actual.sum()),
        "players": sorted(ids),
    }


def _solve_oracle(
    players: pd.DataFrame,
    allowed_ids: set[str] | None = None,
    *,
    locked_choices: Sequence[Sequence[str]] | None = None,
    locked_flex_positions: Sequence[str | None] | None = None,
    min_salary: int = 49_000,
    salary_cap: int = 50_000,
) -> dict[str, Any]:
    """Solve the exact frozen legal-lineup oracle with deterministic ties."""
    frame = _normalise_player_frame(players)
    if allowed_ids is not None:
        frame = frame[frame.id.isin(set(map(str, allowed_ids)))].copy()
    if frame.empty:
        raise ValueError("oracle player support is empty")
    rows = list(frame.itertuples(index=False))
    problem = pulp.LpProblem("forensic_oracle", pulp.LpMaximize)
    decision = {
        row.id: pulp.LpVariable(f"x_{index}", cat="Binary")
        for index, row in enumerate(rows)
    }
    score_expr = pulp.lpSum(decision[row.id] * row.actual for row in rows)
    salary_expr = pulp.lpSum(decision[row.id] * row.salary for row in rows)
    problem += score_expr
    problem += salary_expr <= salary_cap
    problem += salary_expr >= min_salary
    problem += pulp.lpSum(decision.values()) == 9
    choice_variables: list[pulp.LpVariable] = []
    normalized_choices: list[set[str]] = []
    if locked_choices is not None:
        normalized_choices = [set(map(str, choice)) for choice in locked_choices]
        if not normalized_choices:
            raise ValueError("recourse oracle has no first-stage choices")
        choice_variables = [
            pulp.LpVariable(f"choice_{index}", cat="Binary")
            for index in range(len(normalized_choices))
        ]
        problem += pulp.lpSum(choice_variables) == 1
        if locked_flex_positions is None:
            locked_flex_positions = [None] * len(normalized_choices)
        if len(locked_flex_positions) != len(normalized_choices):
            raise ValueError("recourse FLEX locks do not align with choices")
        locked_flex_positions = [
            None if value is None else str(value).upper()
            for value in locked_flex_positions
        ]
        if any(
            value not in {None, "RB", "WR", "TE"}
            for value in locked_flex_positions
        ):
            raise ValueError("recourse FLEX lock has an ineligible position")
        position_by_id = frame.set_index("id").pos.to_dict()
        if any(
            flex_position is not None
            and not any(
                position_by_id.get(player) == flex_position for player in choice
            )
            for choice, flex_position in zip(
                normalized_choices, locked_flex_positions, strict=True
            )
        ):
            raise ValueError("recourse FLEX lock is absent from its early core")
        early_union = set().union(*normalized_choices)
        unknown_early = early_union - set(decision)
        if unknown_early:
            raise ValueError(f"recourse choice has unknown players: {sorted(unknown_early)}")
        for player in sorted(early_union):
            problem += decision[player] == pulp.lpSum(
                choice_variables[index]
                for index, choice in enumerate(normalized_choices)
                if player in choice
            )

    def count(position: str):
        return pulp.lpSum(decision[row.id] for row in rows if row.pos == position)

    problem += count("QB") == 1
    problem += count("DST") == 1
    rb_flex_locked = pulp.lpSum(
        choice_variables[index]
        for index, value in enumerate(locked_flex_positions or [])
        if value == "RB"
    )
    wr_flex_locked = pulp.lpSum(
        choice_variables[index]
        for index, value in enumerate(locked_flex_positions or [])
        if value == "WR"
    )
    te_flex_locked = pulp.lpSum(
        choice_variables[index]
        for index, value in enumerate(locked_flex_positions or [])
        if value == "TE"
    )
    problem += count("RB") >= 2 + rb_flex_locked
    problem += count("RB") <= 3 - wr_flex_locked - te_flex_locked
    problem += count("WR") >= 3 + wr_flex_locked
    problem += count("WR") <= 4 - rb_flex_locked - te_flex_locked
    problem += count("TE") >= 1 + te_flex_locked
    problem += count("TE") <= 2 - rb_flex_locked - wr_flex_locked
    for team in sorted(frame.team.unique()):
        ids = [row.id for row in rows if row.team == team]
        problem += pulp.lpSum(decision[player] for player in ids) <= 8
        rbs = [row.id for row in rows if row.team == team and row.pos == "RB"]
        if len(rbs) > 1:
            problem += pulp.lpSum(decision[player] for player in rbs) <= 1
    games = sorted(frame.game_id.unique())
    if len(games) >= 2:
        for game in games:
            problem += pulp.lpSum(
                decision[row.id] for row in rows if row.game_id != game
            ) >= 1
    for qb in (row for row in rows if row.pos == "QB"):
        catchers = [
            row.id for row in rows
            if row.team == qb.team and row.pos in ("WR", "TE")
        ]
        problem += pulp.lpSum(decision[player] for player in catchers) >= decision[qb.id]
    for dst in (row for row in rows if row.pos == "DST"):
        for rb in (
            row for row in rows if row.pos == "RB" and row.team == dst.opp
        ):
            problem += decision[dst.id] + decision[rb.id] <= 1

    solver = pulp.PULP_CBC_CMD(msg=0)
    problem.solve(solver)
    if pulp.LpStatus[problem.status] != "Optimal":
        raise ValueError(f"oracle is {pulp.LpStatus[problem.status]}")
    optimum = float(pulp.value(score_expr))
    # Freeze the primary optimum, then prefer the lowest stable id-rank sum.
    problem += score_expr >= optimum - 1e-7
    problem.sense = pulp.LpMinimize
    rank = {row.id: index + 1 for index, row in enumerate(rows)}
    tie_objective = pulp.lpSum(decision[row.id] * rank[row.id] for row in rows)
    if choice_variables:
        tie_objective = tie_objective * (len(choice_variables) + 1) + pulp.lpSum(
            variable * (index + 1)
            for index, variable in enumerate(choice_variables)
        )
    problem.setObjective(tie_objective)
    problem.solve(solver)
    if pulp.LpStatus[problem.status] != "Optimal":
        raise ValueError("oracle deterministic tie solve failed")
    chosen = sorted(row.id for row in rows if decision[row.id].value() > 0.5)
    audit = audit_roster(
        frame, chosen, min_salary=min_salary, salary_cap=salary_cap
    )
    if not audit["valid"] or not np.isclose(
        audit["actual_score"], optimum, rtol=0.0, atol=1e-6
    ):
        raise ValueError("oracle failed independent legality/score reconstruction")
    audit["solver_status"] = "Optimal"
    if choice_variables:
        audit["source_choice_index"] = next(
            index for index, variable in enumerate(choice_variables)
            if variable.value() > 0.5
        )
    return audit


def recourse_ceiling_slate(
    players: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    expected_entries: int = 80,
    compute_liveness: bool = False,
) -> dict[str, Any]:
    """Hindsight upper bound after locking each selected entry's early core.

    This is deliberately not a playable policy: realized scores choose the
    best legal late-game completion.  It sizes the option value available from
    the incumbent first-stage book and may only generate prospective research.
    """
    frame = _normalise_player_frame(players)
    if "kickoff_time" not in players:
        raise ValueError("recourse ceiling requires kickoff_time")
    kickoff = players[["id", "kickoff_time"]].copy()
    kickoff["id"] = kickoff.id.astype(str)

    def kickoff_minutes(value: object) -> int:
        parts = str(value).split(":")
        if len(parts) < 2:
            raise ValueError(f"invalid kickoff time: {value}")
        return int(parts[0]) * 60 + int(parts[1])

    kickoff["minutes"] = kickoff.kickoff_time.map(kickoff_minutes)
    if kickoff.id.duplicated().any():
        raise ValueError("recourse kickoff rows repeat player ids")
    minutes = kickoff.set_index("id").minutes.to_dict()
    decision_stages = sorted(set(minutes.values()))
    if len(decision_stages) < 2:
        return {
            "status": "not_identifiable_single_lock_stage",
            "incumbent_selected_best": float(
                pd.to_numeric(
                    candidates[candidates.selected.fillna(False).astype(bool)].actual_score,
                    errors="raise",
                ).max()
            ),
            "decision_stages_minutes": decision_stages,
            "interpretation": "No later-lock player exists on this slate.",
        }
    initial_lock = decision_stages[0]
    late_ids = {
        player for player, value in minutes.items() if value > initial_lock
    }
    selected = candidates[
        candidates.selected.fillna(False).astype(bool)
    ].sort_values("selected_rank", kind="stable")
    if len(selected) != expected_entries:
        raise ValueError(f"recourse ceiling requires exact-{expected_entries}")
    rosters = [
        tuple(item for item in str(value).split(",") if item)
        for value in selected.players
    ]
    if any(len(roster) != 9 or len(set(roster)) != 9 for roster in rosters):
        raise ValueError("recourse source roster is malformed")

    positions = frame.set_index("id").pos.to_dict()

    def flex_player(roster: Sequence[str]) -> str:
        eligible = [player for player in roster if positions[player] in {"RB", "WR", "TE"}]
        counts = Counter(positions[player] for player in eligible)
        surplus = [
            position for position, minimum in (("RB", 2), ("WR", 3), ("TE", 1))
            if counts.get(position, 0) > minimum
        ]
        if len(surplus) != 1:
            raise ValueError("recourse source roster has no unique FLEX position")
        flex_candidates = [
            player for player in roster if positions[player] == surplus[0]
        ]
        # Mirrors Lineup.slot_order when kickoff data are available: hard
        # position slots take the earliest players and FLEX retains the latest.
        return sorted(flex_candidates, key=lambda player: minutes[player])[-1]

    flex_players = [flex_player(roster) for roster in rosters]
    locked_choices = [
        tuple(player for player in roster if player not in late_ids)
        for roster in rosters
    ]
    locked_flex_positions = [
        positions[player] if player in choice else None
        for player, choice in zip(flex_players, locked_choices, strict=True)
    ]
    early_union = set().union(*(set(choice) for choice in locked_choices))
    allowed = late_ids | early_union
    bound = _solve_oracle(
        frame,
        allowed,
        locked_choices=locked_choices,
        locked_flex_positions=locked_flex_positions,
        min_salary=0,
        salary_cap=50_000,
    )
    source_index = int(bound.pop("source_choice_index"))
    incumbent_best = float(pd.to_numeric(selected.actual_score, errors="raise").max())
    if float(bound["actual_score"]) + 1e-6 < incumbent_best:
        raise ValueError("recourse ceiling fell below its feasible incumbent book")
    tail_grid = {
        str(tail): {
            "incumbent_reaches": incumbent_best >= tail,
            "perfect_information_reaches": float(bound["actual_score"]) >= tail,
            "newly_reached": incumbent_best < tail <= float(bound["actual_score"]),
        }
        for tail in TAILS
    }
    liveness: dict[str, Any]
    if compute_liveness:
        stage_rows = []
        cache: dict[tuple[int, tuple[str, ...], str | None], float] = {}
        for stage in decision_stages[1:]:
            stage_late_ids = {
                player for player, value in minutes.items() if value >= stage
            }
            per_entry_bounds = []
            for roster_index, roster in enumerate(rosters):
                core = tuple(sorted(
                    player for player in roster if minutes[player] < stage
                ))
                source_flex = flex_players[roster_index]
                flex_lock = positions[source_flex] if source_flex in core else None
                key = (stage, core, flex_lock)
                if key not in cache:
                    stage_bound = _solve_oracle(
                        frame,
                        stage_late_ids | set(core),
                        locked_choices=[core],
                        locked_flex_positions=[flex_lock],
                        min_salary=0,
                        salary_cap=50_000,
                    )
                    cache[key] = float(stage_bound["actual_score"])
                per_entry_bounds.append(cache[key])
            stage_rows.append({
                "decision_stage_minutes": stage,
                "unique_locked_cores": len({
                    tuple(sorted(
                        player for player in roster if minutes[player] < stage
                    ))
                    for roster in rosters
                }),
                "unique_locked_core_flex_states": int(sum(
                    key[0] == stage for key in cache
                )),
                "perfect_information_live_entries": {
                    str(tail): int(sum(value >= tail for value in per_entry_bounds))
                    for tail in TAILS
                },
                "maximum_reachable": float(max(per_entry_bounds)),
                "median_reachable": float(np.median(per_entry_bounds)),
            })
        liveness = {
            "status": "computed_for_incumbent_locked_cores",
            "stages": stage_rows,
            "warning": (
                "Liveness uses realized future scores and therefore states only "
                "whether an entry was capable under perfect hindsight, not what "
                "could have been recognized at the decision time."
            ),
        }
    else:
        liveness = {
            "status": "not_computed_nonproduction_scope",
            "reason": "Detailed 80-core solves are reserved for the deployed CBWU scope.",
        }
    return {
        "status": "computed_perfect_information_upper_bound",
        "incumbent_selected_best": incumbent_best,
        "perfect_information_recourse_ceiling": float(bound["actual_score"]),
        "ceiling_gain": float(bound["actual_score"] - incumbent_best),
        "source_selected_rank": int(selected.iloc[source_index].selected_rank),
        "source_early_players": sorted(locked_choices[source_index]),
        "late_player_count": len(late_ids),
        "final_roster": bound,
        "initial_lock_minutes": initial_lock,
        "decision_stages_minutes": decision_stages,
        "tail_grid": tail_grid,
        "per_stage_liveness": liveness,
        "salary_floor_after_lock": 0,
        "realistic_recourse": {
            "status": "unidentifiable_from_frozen_summary_corpus",
            "reason": (
                "The frozen panel retains player quantiles and full-lineup score "
                "summaries, not joint late-player draws conditional on observed "
                "early results. Constructing them after viewing outcomes would "
                "invent a new model rather than measure a frozen policy."
            ),
            "required_prospective_input": (
                "Retain pre-lock player/world draws with kickoff-stage identity, "
                "then freeze a conditional late-swap objective before Week 1."
            ),
        },
        "interpretation": (
            "Perfect-information hindsight upper bound on incumbent early cores; "
            "actual kickoff stages, the production latest-kickoff FLEX assignment, "
            "and final salary/position legality are enforced. "
            "It is not a backtested policy, adoption gate, or achievable expectation."
        ),
    }


def decompose_slate(
    players: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    selected_rosters: Sequence[str] | None = None,
    expected_entries: int = 80,
    min_salary: int = 49_000,
    salary_cap: int = 50_000,
) -> dict[str, Any]:
    """Compute the corrected H/P/C/S decomposition for one frozen slate."""
    frame = _normalise_player_frame(players)
    required = {"players", "actual_score"}
    if not required <= set(candidates):
        raise ValueError(f"candidate frame lacks {sorted(required - set(candidates))}")
    pool = candidates.copy()
    roster_ids: list[tuple[str, ...]] = []
    audits: list[dict[str, Any]] = []
    for row in pool.itertuples(index=False):
        ids = tuple(item for item in str(row.players).split(",") if item)
        audit = audit_roster(
            frame, ids, min_salary=min_salary, salary_cap=salary_cap
        )
        if not audit["valid"]:
            raise ValueError(f"illegal candidate roster: {audit['failures']}")
        if not np.isclose(
            audit["actual_score"], float(row.actual_score), rtol=0.0, atol=1e-6
        ):
            raise ValueError("candidate actual score fails reconstruction")
        roster_ids.append(ids)
        audits.append(audit)
    canonical = [tuple(sorted(ids)) for ids in roster_ids]
    if len(canonical) != len(set(canonical)):
        raise ValueError("candidate pool contains duplicate rosters")
    pool = pool.reset_index(drop=True)
    pool["roster_key"] = [",".join(ids) for ids in canonical]

    if selected_rosters is None:
        if "selected" not in pool:
            raise ValueError("selected membership is absent")
        selected = pool[pool.selected.fillna(False).astype(bool)].copy()
        if "selected_rank" in selected:
            selected = selected.sort_values("selected_rank", kind="stable")
        selected_keys = selected.roster_key.tolist()
    else:
        selected_keys = [
            ",".join(sorted(item for item in str(value).split(",") if item))
            for value in selected_rosters
        ]
        if not set(selected_keys) <= set(pool.roster_key):
            raise ValueError("selected roster is absent from the candidate pool")
        selected = pool.set_index("roster_key").loc[selected_keys].reset_index()
    if len(selected_keys) != expected_entries or len(set(selected_keys)) != expected_entries:
        raise ValueError(f"selected book is not exact-{expected_entries}")

    support = set().union(*(set(ids) for ids in roster_ids)) if roster_ids else set()
    full_oracle = _solve_oracle(
        frame, min_salary=min_salary, salary_cap=salary_cap
    )
    support_oracle = _solve_oracle(
        frame, support, min_salary=min_salary, salary_cap=salary_cap
    )
    candidate_row = pool.sort_values(
        ["actual_score", "roster_key"], ascending=[False, True], kind="stable"
    ).iloc[0]
    selected_row = selected.sort_values(
        ["actual_score", "roster_key"], ascending=[False, True], kind="stable"
    ).iloc[0]
    h_score = float(full_oracle["actual_score"])
    p_score = float(support_oracle["actual_score"])
    c_score = float(candidate_row.actual_score)
    s_score = float(selected_row.actual_score)
    if not (h_score + 1e-6 >= p_score >= c_score - 1e-6 >= s_score - 1e-6):
        raise ValueError("H/P/C/S ordering invariant failed")
    return {
        "H": full_oracle,
        "P": support_oracle,
        "C": {
            "actual_score": c_score,
            "players": str(candidate_row.roster_key).split(","),
        },
        "S": {
            "actual_score": s_score,
            "players": str(selected_row.roster_key).split(","),
        },
        "gaps": {
            "player_support": h_score - p_score,
            "construction": p_score - c_score,
            "selection": c_score - s_score,
        },
        "thresholds": {
            str(tail): {
                "H": h_score >= tail,
                "P": p_score >= tail,
                "C": c_score >= tail,
                "S": s_score >= tail,
                "first_failed_layer": (
                    "player_support" if h_score >= tail > p_score
                    else "construction" if p_score >= tail > c_score
                    else "selection" if c_score >= tail > s_score
                    else "none"
                ),
            }
            for tail in TAILS
        },
        "candidate_count": len(pool),
        "supported_player_count": len(support),
        "selected_count": len(selected_keys),
    }


__all__ = [
    "FreezeManifestError",
    "BETWEEN_ARM_VARIANCE_PANEL_IDS",
    "LEDGER_STATUSES",
    "PROTOCOL_ID",
    "ANALYSIS_CHECKLIST",
    "REQUIRED_FORENSIC_ARTIFACT_PATHS",
    "REQUIRED_MECHANISM_FAMILIES",
    "REQUIRED_OUTPUTS",
    "TAILS",
    "WAREHOUSE_TABLE_SCHEMAS",
    "WAREHOUSE_TABLE_PREFIX",
    "audit_roster",
    "build_freeze_manifest",
    "canonical_game_id",
    "decompose_slate",
    "manifest_digest",
    "recourse_ceiling_slate",
    "report_inventory",
    "sha256_file",
    "validate_freeze_manifest",
]
