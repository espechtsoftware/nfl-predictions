#!/usr/bin/env python3
"""Run the frozen outcome-free ATLAS production-law transfer cell."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from google.cloud import bigquery, storage

from nfl_dfs.analysis.atlas_world_ranking import (
    EXACT_IDENTITY_TOLERANCE,
    aggregate_transfer_gate,
    complete_world_ranking_diagnostic,
)
from nfl_dfs.optimizer.lineup import StackRules
from nfl_dfs.research.atlas_money_transfer import (
    PROTOCOL_PATH,
    RUN_ID,
    VERSION as SOURCE_VERSION,
    acquisition_environment,
    canonical_policy_receipt,
    panel_id,
    source_environment_lever_text,
    validate_logged_source_environment,
)
from nfl_dfs.research.atlas_money_source_grid import (
    validate_environment_receipt,
)
from nfl_dfs.research.source_preflight import (
    resolve_panel_artifacts,
    validate_execution_identity,
    verify_local_sha256,
)

from run_atlas_world_ranking import (
    FORENSIC_MANIFEST_SHA256,
    PLAYER_SQL,
    PROJECT,
    _download_artifact,
    _player_rows,
    _query,
    _upload_create_only,
)


VERSION = "atlas-current-money-transfer-v1"
PROTOCOL_SHA256 = (
    "c6cb9605678bdfb68f54cbc9fd7adcea754500afb838d2a17a9c0861e4527423"
)
LAW_SEPARATION_AMENDMENT = Path(
    "reports/2026-08-16-atlas-transfer-law-separation-amendment.md"
)
LAW_SEPARATION_AMENDMENT_SHA256 = (
    "59326d6c8db4209a4eac44bbc80935adb8d93fb71a0b92a5d5325a30562fae54"
)
ARTIFACT_NATIVE_REPAIR = Path(
    "reports/2026-08-15-atlas-money-artifact-native-repair.md"
)
ARTIFACT_NATIVE_REPAIR_SHA256 = (
    "d51a32aeeb8d7f4546169709c4b0a5b8e6d8ef5aebf8b8a8adbd227f54d60812"
)
SOURCE_PANEL_IDS = tuple(panel_id(block) for block in range(5))
ACQUISITION_DIR = Path("reports/atlas-money-world-runs") / RUN_ID
ACQUISITION_MANIFEST = ACQUISITION_DIR / "manifest.txt"
SOURCE_GRID = ACQUISITION_DIR / "source-grid.json"
ACQUISITION_COMPLETE = ACQUISITION_DIR / "acquisition-complete.txt"
EXECUTION_RECEIPTS = ACQUISITION_DIR / "execution-metadata.sha256"
ENVIRONMENT_RECEIPTS = ACQUISITION_DIR / "environment-receipts.sha256"
OUTPUT_URI = (
    "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
    "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
    "20260815-atlas-current-money-transfer-v1/result.json"
)
FORBIDDEN_SOURCE_TOKENS = (
    "actual_score", "actual_rank", "actual_ownership", "selected",
    "payout", "contest_rank", "labels_complete",
)


def _manifest(path: Path) -> dict[str, str]:
    values = dict(
        line.rstrip("\n").split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    required = {
        "run_id", "image", "code_sha", "protocol_sha256",
        "policy_environment_sha256", "source_panels",
        "uses_realized_outcomes", "usage_allocation",
    }
    if not required <= set(values):
        raise RuntimeError("ATLAS transfer acquisition manifest is incomplete")
    return values


def validate_scorefree_sources() -> None:
    text = PLAYER_SQL.lower()
    present = [token for token in FORBIDDEN_SOURCE_TOKENS if token in text]
    if present:
        raise RuntimeError(
            "ATLAS money transfer source query contains forbidden fields: "
            + ", ".join(present)
        )


def _proxy_summary(rows: list[dict]) -> dict[str, Any]:
    diagnostics = [row["proxy_diagnostics"] for row in rows]
    return {
        "identity_tolerance": EXACT_IDENTITY_TOLERANCE,
        "mean_proxy_minus_exact_slack": float(np.mean([
            row["proxy_minus_exact_slack"]["mean"] for row in diagnostics
        ])),
        "mean_proxy_exact_rank_correlation_union": float(np.mean([
            row["proxy_exact_rank_correlation_union"] for row in diagnostics
        ])),
        "paired_exact_quality": {
            name: int(sum(
                row["paired_exact_quality"][name] for row in diagnostics
            ))
            for name in ("wins", "ties", "losses")
        },
        "mean_top_world_overlap": {
            top: float(np.mean([
                row["top_world_overlap"][top] for row in diagnostics
            ]))
            for top in ("8", "20", "40")
        },
        "mean_cutoff_ties": {
            arm: float(np.mean([
                row["cutoff_ties"][arm] for row in diagnostics
            ]))
            for arm in ("incumbent", "attainable")
        },
    }


def _combination_reach_summary(rows: list[dict]) -> dict[str, Any]:
    """Keep pair/core reach prominent without changing the Part-A gate."""
    result: dict[str, Any] = {}
    for metric in ("unique_player_pairs", "unique_qb_stack_cores"):
        incumbent = np.asarray([
            row["incumbent_exact"][metric] for row in rows
        ], dtype=float)
        attainable = np.asarray([
            row["attainable_exact"][metric] for row in rows
        ], dtype=float)
        ratios = attainable / np.maximum(incumbent, 1.0)

        def distribution(values: np.ndarray) -> dict[str, float]:
            return {
                "mean": float(values.mean()),
                "q10": float(np.quantile(values, 0.10)),
                "median": float(np.median(values)),
                "minimum": float(values.min()),
                "maximum": float(values.max()),
            }

        result[metric] = {
            "incumbent": distribution(incumbent),
            "attainable": distribution(attainable),
            "attainable_to_incumbent_ratio": distribution(ratios),
            "gating": False,
        }
    return result


def run(output_uri: str) -> dict[str, Any]:
    if output_uri != OUTPUT_URI:
        raise RuntimeError("ATLAS money transfer output identity differs")
    validate_scorefree_sources()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    validate_execution_identity(code_sha, image)
    expected_hashes = {
        "protocol": os.environ.get("PROTOCOL_SHA256", "").strip(),
        "law_separation_amendment": os.environ.get(
            "LAW_SEPARATION_AMENDMENT_SHA256", "",
        ).strip(),
        "acquisition_manifest": os.environ.get(
            "ACQUISITION_MANIFEST_SHA256", "",
        ).strip(),
        "source_grid": os.environ.get("SOURCE_GRID_SHA256", "").strip(),
        "acquisition_complete": os.environ.get(
            "ACQUISITION_COMPLETE_SHA256", "",
        ).strip(),
        "execution_receipts": os.environ.get(
            "EXECUTION_RECEIPTS_SHA256", "",
        ).strip(),
        "environment_receipts": os.environ.get(
            "ENVIRONMENT_RECEIPTS_SHA256", "",
        ).strip(),
        "artifact_native_repair": os.environ.get(
            "ARTIFACT_NATIVE_REPAIR_SHA256", "",
        ).strip(),
    }
    local_receipts = verify_local_sha256({
        "protocol": (PROTOCOL_PATH, expected_hashes["protocol"]),
        "law_separation_amendment": (
            LAW_SEPARATION_AMENDMENT,
            expected_hashes["law_separation_amendment"],
        ),
        "artifact_native_repair": (
            ARTIFACT_NATIVE_REPAIR,
            expected_hashes["artifact_native_repair"],
        ),
        "acquisition_manifest": (
            ACQUISITION_MANIFEST, expected_hashes["acquisition_manifest"],
        ),
        "source_grid": (SOURCE_GRID, expected_hashes["source_grid"]),
        "acquisition_complete": (
            ACQUISITION_COMPLETE, expected_hashes["acquisition_complete"],
        ),
        "execution_receipts": (
            EXECUTION_RECEIPTS, expected_hashes["execution_receipts"],
        ),
        "environment_receipts": (
            ENVIRONMENT_RECEIPTS, expected_hashes["environment_receipts"],
        ),
    })
    if local_receipts["protocol"] != PROTOCOL_SHA256:
        raise RuntimeError("ATLAS money transfer protocol differs")
    if local_receipts["law_separation_amendment"] != (
        LAW_SEPARATION_AMENDMENT_SHA256
    ):
        raise RuntimeError("ATLAS money transfer law amendment differs")
    if local_receipts["artifact_native_repair"] != (
        ARTIFACT_NATIVE_REPAIR_SHA256
    ):
        raise RuntimeError("ATLAS money transfer artifact repair differs")
    source_manifest = _manifest(ACQUISITION_MANIFEST)
    policy = canonical_policy_receipt()
    if (
        source_manifest["run_id"] != RUN_ID
        or source_manifest["protocol_sha256"] != PROTOCOL_SHA256
        or source_manifest["policy_environment_sha256"]
        != policy["engine_environment_sha256"]
        or source_manifest["source_panels"].split(",")
        != list(SOURCE_PANEL_IDS)
        or source_manifest["uses_realized_outcomes"] != "false"
        or source_manifest["usage_allocation"] != "production-multinomial"
        or source_manifest.get("game_sim_usage", "x") != ""
        or source_manifest.get("dirichlet_k", "x") != ""
        or source_manifest.get("sis_asoe", "x") != ""
    ):
        raise RuntimeError("ATLAS money transfer source manifest differs")

    source_rows = json.loads(SOURCE_GRID.read_text(encoding="utf-8"))
    source_binding_counts: dict[str, int] = {}
    for row in source_rows:
        panel = str(row.get("panel_run_id"))
        if panel not in SOURCE_PANEL_IDS:
            raise RuntimeError("ATLAS money transfer source panel differs")
        block = SOURCE_PANEL_IDS.index(panel)
        season = int(row.get("season"))
        binding = str(row.get("source_binding", ""))
        if binding not in {"candidate_table", "gcs_artifact_recovery"}:
            raise RuntimeError("ATLAS money transfer source binding differs")
        source_binding_counts[binding] = source_binding_counts.get(binding, 0) + 1
        receipt_path = (
            ACQUISITION_DIR / "environment-receipts" /
            f"r{block}-{season}.json"
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        environment = validate_environment_receipt(receipt)
        if str(receipt.get("sha256")) != str(
            row.get("environment_sha256", ""),
        ) or environment != acquisition_environment(
            block=block,
            season=season,
            code_sha=source_manifest["code_sha"],
            project=PROJECT,
        ):
            raise RuntimeError("ATLAS money transfer environment differs")
        lever_env = str(row.get("lever_env", ""))
        validate_logged_source_environment(lever_env, block)
        if binding == "gcs_artifact_recovery" and lever_env != (
            source_environment_lever_text(environment, block)
        ):
            raise RuntimeError("ATLAS recovered lever receipt differs")
        if str(row.get("code_sha")) != source_manifest["code_sha"]:
            raise RuntimeError("ATLAS money transfer source code differs")
    preflight = resolve_panel_artifacts(
        source_rows, panel_ids=SOURCE_PANEL_IDS, expected_slates=54,
    )
    source_by_key = {
        (str(row["panel_run_id"]), int(row["season"]), int(row["week"])): row
        for row in source_rows
    }

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    players = _query(bq, PLAYER_SQL)
    if set(players.manifest_sha256.astype(str)) != {FORENSIC_MANIFEST_SHA256}:
        raise RuntimeError("ATLAS money transfer player manifest differs")
    sources = {
        (str(row["panel_run_id"]), int(row["season"]), int(row["week"])): row
        for row in preflight["artifacts"]
    }
    diagnostics = []
    artifact_receipts = []
    stack = StackRules(
        qb_stack_min=2,
        bring_back_min=1,
        forbid_rb_vs_dst=True,
        forbid_two_rb_same_team=True,
    )
    optimizer_env = {
        "MIN_LINEUP_SALARY": "49000",
        "MIN_GAMES": "2",
        "PUNT_MIN": "0",
        "VALUE2_MIN": "0",
        "OWN_BARBELL": "",
        "MAX_PER_GAME": "0",
    }
    for source in preflight["artifacts"]:
        panel = str(source["panel_run_id"])
        block = SOURCE_PANEL_IDS.index(panel)
        season, week = int(source["season"]), int(source["week"])
        artifact, receipt = _download_artifact(
            gcs, str(source["uri"]), str(source["sha256"]),
        )
        catalog = players[
            players.season.astype(int).eq(season)
            & players.week.astype(int).eq(week)
        ].copy()
        player_ids = np.asarray(artifact["player_ids"]).astype(str)
        player_rows = _player_rows(catalog, player_ids)
        draws = np.asarray(artifact["player_draws"], dtype=np.float32)
        if draws.shape != (len(player_rows), 10_000) or \
                not np.isfinite(draws).all():
            raise RuntimeError("ATLAS money transfer player-world shape differs")
        diagnostic = complete_world_ranking_diagnostic(
            player_rows, draws, stack=stack, env=optimizer_env, n_worlds=40,
        )
        diagnostics.append({
            "seed": block,
            "panel_run_id": panel,
            "season": season,
            "week": week,
            **diagnostic,
        })
        grid = source_by_key[(panel, season, week)]
        artifact_receipts.append({
            "seed": block,
            "panel_run_id": panel,
            "season": season,
            "week": week,
            "candidate_rows": int(grid["source_rows"]),
            **receipt,
        })

    gate = aggregate_transfer_gate(diagnostics)
    mechanical_conditions = {
        "acquisition_executions_and_grid_valid": True,
        "exact_target_law_receipt_valid": True,
        "immutable_sources_and_player_worlds_valid": True,
        "point_in_time_player_catalog_complete": True,
        "deterministic_rank_and_exact_solve_valid": True,
        "outcome_firewall_valid": True,
    }
    report = {
        "version": VERSION,
        "source_version": SOURCE_VERSION,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "code_sha": code_sha,
        "image": image,
        "protocol_sha256": PROTOCOL_SHA256,
        "law_separation_amendment_sha256": (
            LAW_SEPARATION_AMENDMENT_SHA256
        ),
        "artifact_native_repair_sha256": ARTIFACT_NATIVE_REPAIR_SHA256,
        "local_source_receipts": local_receipts,
        "source_manifest": source_manifest,
        "source_policy_receipt": policy,
        "source_panels": list(SOURCE_PANEL_IDS),
        "source_preflight": {
            key: preflight[key]
            for key in ("panel_ids", "slates", "slate_count", "artifact_count")
        },
        "source_artifacts": artifact_receipts,
        "source_binding_counts": source_binding_counts,
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "production_constraints": {
            "salary_floor": 49_000,
            "salary_cap": 50_000,
            "qb_stack_min": 2,
            "bring_back_min": 1,
            "forbid_rb_vs_dst": True,
            "forbid_two_rb_same_team": True,
        },
        "gate": gate,
        "proxy_summary": _proxy_summary(diagnostics),
        "combination_reach": _combination_reach_summary(diagnostics),
        "law_separation": {
            "reference_measurement_law": {
                "usage_allocation": "finite-dirichlet",
                "dirichlet_k": 28.154043586960896,
                "sis_asoe_rank_transport": True,
            },
            "target_measurement_law": policy["simulation_law"],
            "effect_may_be_law_dependent": True,
        },
        "transfer_disposition": {
            "mechanical": {
                "passes": bool(all(mechanical_conditions.values())),
                "conditions": mechanical_conditions,
            },
            "effect": {
                "evaluated": True,
                "passes": bool(gate["passes_part_a_transfer"]),
                "conditions": gate["quality_conditions"],
            },
        },
        "diagnostics": diagnostics,
        "historical_arm_licensed": False,
        "production_change_licensed": False,
        "consequence": (
            "outcome-free current-law Part-A transfer only; a pass licenses "
            "a pre-lock ATLAS MVP shadow, never historical promotion"
        ),
    }
    payload = (json.dumps(
        report, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode("utf-8")
    report["output"] = _upload_create_only(gcs, output_uri, payload)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    report = run(args.output_uri)
    print(json.dumps({
        "version": report["version"],
        "gate": report["gate"],
        "proxy_summary": report["proxy_summary"],
        "output": report["output"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
