from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

import pytest

from nfl_dfs.research import corpus_retrieval_neo4j as projection
from nfl_dfs.research import corpus_neo4j_extensions as extensions
from scripts import load_corpus_retrieval_neo4j as cli


ROOT = Path(__file__).resolve().parents[1]


def _self_hash(value: dict[str, Any], field: str) -> dict[str, Any]:
    result = deepcopy(value)
    result[field] = projection.canonical_sha256(result)
    return result


def _identity(uri: str, generation: int, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _placeholder_identity(name: str, generation: int) -> dict[str, object]:
    raw = f"fixture:{name}".encode()
    return _identity(f"gs://dedicated-research/run/{name}", generation, raw)


def _bundle(
    *, completion_complete: bool = True, result_production_license: bool = False,
    analytics: bool = False,
) -> dict[str, Any]:
    manifest_raw = b"fixture-manifest"
    suite_identity = _identity(
        "gs://dedicated-research/run/governance/suite-manifest.json",
        10,
        manifest_raw,
    )
    snapshot_identity = _identity(
        "gs://dedicated-research/input/snapshot.json", 11, manifest_raw
    )
    run_id = "20260821-retrieval-fixture-v1"
    task_id = "slate-2023-w1"
    strategy_ids = ["coverage194", "strict200", "ladder", "mean"]
    sidecars: list[dict[str, object]] = []
    sidecar_bodies: dict[tuple[str, str], bytes] = {}
    ordinal = 20

    def add_sidecar(
        role: str, strategy_id: str, suffix: str,
        body: dict[str, object] | None = None,
    ) -> None:
        nonlocal ordinal
        raw = None if body is None else projection.canonical_json_bytes(body)
        identity = (
            _placeholder_identity(suffix, ordinal)
            if raw is None
            else _identity(f"gs://dedicated-research/run/{suffix}", ordinal, raw)
        )
        ordinal += 1
        if raw is not None:
            sidecar_bodies[(role, strategy_id)] = raw
        sidecars.append({
            "role": role,
            "strategy_id": strategy_id,
            "format": (
                "canonical-compressed-npz-v1"
                if suffix.endswith(".npz")
                else "canonical-json-v1"
            ),
            "object_identity": identity,
            "semantic": (
                {"fixture": suffix}
                if body is None
                else {
                    "schema_version": body["schema_version"],
                    "canonical_json_sha256": identity["sha256"],
                }
            ),
        })

    add_sidecar("unique-lineups", "", "artifacts/unique-lineups.json")
    add_sidecar("unique-lineup-scores", "", "artifacts/unique-lineup-scores.npz")
    add_sidecar("strict-gt-200-events", "", "artifacts/strict-gt-200-events.npz")
    enrichment_rows = {
        "players": [{
            "player_id": "p1", "lineup_support": 10,
            "lineup_world_support": 400_000, "strict_gt_200_event_count": 8,
            "event_rate": 0.00002, "enrichment_vs_all_lineups": 1.5,
            "minimum_support_qualified": True,
        }],
        "pairs": [{
            "player_ids": ["p1", "p2"], "lineup_support": 8,
            "lineup_world_support": 320_000, "strict_gt_200_event_count": 7,
            "event_rate": 0.000021875, "enrichment_vs_all_lineups": 1.4,
            "minimum_support_qualified": True,
        }],
        "tags": [], "stack_signatures": [], "teams": [],
        "team_pairs": [], "games": [],
    }

    def enrichment(scope: str, blocks: list[str]) -> dict[str, object]:
        return _self_hash({
            "schema_version": "corpus-retrieval-enrichment/v1",
            "analysis_scope": scope,
            "world_blocks": blocks,
            "heldout_worlds_used": scope == "all-r0-r4-descriptive",
            "primary_event": {"operator": ">", "threshold": 200.0},
            "lineup_count": 80,
            "world_count": len(blocks) * 10_000,
            "global_event_count": 100,
            "global_event_rate": 0.00003125,
            "minimum_lineup_support": 5,
            **deepcopy(enrichment_rows),
        }, "enrichment_sha256")

    add_sidecar(
        "enrichment-discovery", "", "artifacts/enrichment-discovery.json",
        enrichment("discovery-r0-r3", ["R0", "R1", "R2", "R3"])
        if analytics else None,
    )
    add_sidecar(
        "enrichment-all-worlds", "", "artifacts/enrichment-all-worlds.json",
        enrichment("all-r0-r4-descriptive", ["R0", "R1", "R2", "R3", "R4"])
        if analytics else None,
    )
    redundancy = _self_hash({
        "schema_version": "corpus-retrieval-redundancy-topk/v1",
        "analysis_scope": "all-r0-r4-descriptive",
        "world_blocks": ["R0", "R1", "R2", "R3", "R4"],
        "heldout_worlds_used": True,
        "selection_law": "fixture",
        "correlation_scope": "retained-high-overlap-pairs-only",
        "pair_universe_count": 1,
        "retained_pair_limit": 1,
        "retained_pair_count": 1,
        "exact_duplicate_score_vector_groups": [],
        "pairs": [{
            "left_lineup_index": 0,
            "right_lineup_index": 1,
            "left_lineup_id": "lineup-000",
            "right_lineup_id": "lineup-001",
            "shared_player_count": 7,
            "pearson_score_correlation": 0.75,
            "exact_score_vector_duplicate": False,
            "strict_gt_200_event_intersection": 2,
            "strict_gt_200_event_union": 4,
            "strict_gt_200_event_jaccard": 0.5,
        }],
    }, "redundancy_sha256")
    add_sidecar(
        "redundancy-topk", "", "artifacts/redundancy-topk.json",
        redundancy if analytics else None,
    )
    add_sidecar("fill-insight", "", "artifacts/fill-insight.json")
    for strategy_id in strategy_ids:
        selection = _self_hash({
            "schema_version": "corpus-retrieval-selection/v1",
            "task_id": task_id,
            "strategy": {"strategy_id": strategy_id},
            "selection_law": "R0--R3 discovery only; R4 held out",
            "entry_budget": 80,
            "selected_lineup_indices": list(range(80)),
            "selected_lineup_ids": [f"lineup-{index:03d}" for index in range(80)],
            "selected_lineups": [],
            "selection_trace": [],
            "metrics": {
                "discovery_r0_r3": {
                    "portfolio_world_best_mean": 180.0,
                    "portfolio_worlds_ge_194": 10,
                },
                "heldout_r4": {
                    "portfolio_world_best_mean": 179.0,
                    "portfolio_worlds_ge_194": 2,
                },
            },
        }, "selection_sha256")
        add_sidecar(
            "strategy-selection", strategy_id, f"strategies/{strategy_id}/selection.json",
            selection if analytics else None,
        )
        add_sidecar(
            "strategy-selected-scores",
            strategy_id,
            f"strategies/{strategy_id}/selected-scores.npz",
        )

    nodes: list[dict[str, object]] = [
        {
            "id": "snapshot:fixture",
            "kind": "CorpusSnapshot",
            "properties": {"snapshot_manifest_sha256": "a" * 64},
        },
        {
            "id": f"retrieval-task:{run_id}:{task_id}",
            "kind": "RetrievalTask",
            "properties": {"run_id": run_id, "task_id": task_id},
        },
    ]
    nodes.extend({
        "id": f"candidate:{task_id}:lineup-{index:03d}",
        "kind": "LineupCandidate",
        "properties": {
            "lineup_index": index,
            "strict_gt_200_event_count_all_r0_r4_descriptive": index,
        },
    } for index in range(80))
    nodes.extend({
        "id": f"retrieval-result:{run_id}:{task_id}:{strategy_id}",
        "kind": "RetrievalStrategyResult",
        "properties": {"strategy_id": strategy_id, "entry_budget": 80},
    } for strategy_id in strategy_ids)
    edges = [{
        "from": f"retrieval-task:{run_id}:{task_id}",
        "type": "USES_SNAPSHOT",
        "to": "snapshot:fixture",
        "properties": {},
    }]
    graph = _self_hash({
        "schema_version": projection.GRAPH_SCHEMA,
        "dedicated_analytical_graph_only": True,
        "authoritative_source": "create-once-sidecars-and-task-result",
        "large_bodies_are_pointers": True,
        "analytic_artifact_pointers": deepcopy(sidecars),
        "nodes": nodes,
        "edges": edges,
        "licenses": {
            "decision_authority": False,
            "corpus_fill_authority": False,
            "corpus_producer_input_authority": False,
            "fill_insight_uses_discovery_blocks_only": True,
            "heldout_content_is_descriptive_only": True,
            "live_money_policy_authority": False,
        },
    }, "graph_projection_sha256")
    graph_raw = projection.canonical_json_bytes(graph)
    graph_identity = _identity(
        "gs://dedicated-research/run/tasks/0000/graph-projection.json",
        ordinal,
        graph_raw,
    )
    sidecars.append({
        "role": "graph-projection",
        "strategy_id": "",
        "format": "canonical-json-v1",
        "object_identity": graph_identity,
        "semantic": {"fixture": "graph-projection.json"},
    })

    task_result = _self_hash({
        "schema_version": projection.TASK_RESULT_SCHEMA,
        "publication_mode": "create_once",
        "suite_manifest_identity": suite_identity,
        "suite_manifest_sha256": "b" * 64,
        "snapshot_manifest_identity": snapshot_identity,
        "snapshot_manifest_sha256": "c" * 64,
        "run_id": run_id,
        "snapshot_id": "snapshot-fixture-v1",
        "task_index": 0,
        "task_id": task_id,
        "snapshot_task_sha256": "d" * 64,
        "execution": {
            "execution_id": "retrieval-fixture-abcde",
            "execution_name": "projects/p/locations/r/jobs/j/executions/x",
            "task_index": 0,
            "attempt": 0,
            "retry_count": 0,
            "mode": "cloud-run-task",
            "code_commit": "e" * 40,
            "image_uri": "image",
            "image_digest": "sha256:" + "f" * 64,
        },
        "coverage": {
            "source_block_count": 5,
            "source_candidate_rows": 100,
            "unique_lineup_count": 80,
            "discovery_eligible_lineup_count": 80,
            "heldout_only_lineup_count": 0,
            "world_count": 50_000,
            "lineup_world_score_count": 4_000_000,
            "every_unique_lineup_scored_in_every_world": True,
            "strategy_count": 4,
            "exact_budget_per_strategy": 80,
            "all_strategies_exact_budget": True,
        },
        "primary_event_summary": {"operator": ">", "threshold": 200.0},
        "source_receipts": [],
        "sidecars": sidecars,
        "strategy_results": [
            {"ordinal": index, "strategy_id": strategy_id}
            for index, strategy_id in enumerate(strategy_ids)
        ],
        "graph_projection_object": graph_identity,
        "fill_insight_object": next(
            row["object_identity"]
            for row in sidecars
            if row["role"] == "fill-insight"
        ),
        "licenses": {
            "analytics_authority": True,
            "corpus_fill_authority": False,
            "historical_outcome_read_authority": False,
            "live_money_policy_authority": False,
            "production_default_change_authority": result_production_license,
        },
    }, "task_result_sha256")
    task_result_raw = projection.canonical_json_bytes(task_result)
    task_result_identity = _identity(
        "gs://dedicated-research/run/tasks/0000/result.json",
        ordinal + 1,
        task_result_raw,
    )

    completion = _self_hash({
        "schema_version": projection.COMPLETION_SCHEMA,
        "publication_mode": "create_once",
        "suite_manifest_identity": suite_identity,
        "suite_manifest_sha256": "b" * 64,
        "snapshot_manifest_identity": snapshot_identity,
        "snapshot_manifest_sha256": "c" * 64,
        "run_id": run_id,
        "snapshot_id": "snapshot-fixture-v1",
        "coverage": {
            "task_count": 1,
            "strategy_count": 4,
            "task_strategy_cell_count": 4,
            "all_tasks_complete": completion_complete,
            "all_strategies_equal_budget": True,
        },
        "task_results": [{
            "task_index": 0,
            "task_id": task_id,
            "snapshot_task_sha256": "d" * 64,
            "task_result_sha256": task_result["task_result_sha256"],
            "task_result_object": task_result_identity,
            "unique_lineup_count": 80,
            "lineup_world_score_count": 4_000_000,
            "strategy_count": 4,
            "exact_budget_per_strategy": 80,
        }],
        "licenses": {
            "analytical_graph_projection_ready": True,
            "corpus_fill_authority": False,
            "historical_outcome_read_authority": False,
            "live_money_policy_authority": False,
            "production_default_change_authority": False,
        },
    }, "batch_completion_sha256")
    completion_raw = projection.canonical_json_bytes(completion)
    completion_identity = _identity(
        "gs://dedicated-research/run/governance/completion.json",
        ordinal + 2,
        completion_raw,
    )
    inventory_identities = [
        completion_identity,
        task_result_identity,
        *(row["object_identity"] for row in sidecars),
    ]
    inventory = sorted(
        ({
            "uri": row["uri"],
            "generation": row["generation"],
            "bytes": row["bytes"],
        } for row in inventory_identities),
        key=lambda row: (row["uri"], row["generation"]),
    )
    terminal = _self_hash({
        "schema_version": projection.TERMINAL_SCHEMA,
        "finished_at_utc": "2026-08-21T20:00:00Z",
        "execution_contract": _placeholder_identity("governance/contract.json", 1),
        "prefix_claim": _placeholder_identity("governance/claim.json", 2),
        "runtime_iam_evidence": _placeholder_identity("governance/iam.json", 3),
        "launch_intent": _placeholder_identity("governance/intent.json", 4),
        "launch_ledger": _placeholder_identity("governance/launch.json", 5),
        "execution_name_ledger": _placeholder_identity("governance/name.json", 6),
        "execution": {
            "execution_id": "retrieval-fixture-abcde",
            "execution_name": "projects/p/locations/r/jobs/j/executions/x",
        },
        "suite_manifest_identity": suite_identity,
        "snapshot_manifest_identity": snapshot_identity,
        "task_index": 0,
        "task_id": task_id,
        "result_object": task_result_identity,
        "task_result_sha256": task_result["task_result_sha256"],
        "batch_completion": completion_identity,
        "batch_completion_sha256": completion["batch_completion_sha256"],
        "post_terminal_job": {"name": "parked-job", "uid": "fixed"},
        "output_inventory_before_terminal": inventory,
        "output_inventory_before_terminal_sha256": projection.canonical_sha256(inventory),
        "one_execution": True,
        "attempt_zero": True,
        "retry_count": 0,
        "generation_pinned_replay": True,
        "successful_deployment_remains_parked": True,
        "uses_realized_outcomes": False,
        "bigquery_access_licensed": False,
        "corpus_fill_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
    }, "terminal_receipt_sha256")
    terminal_raw = projection.canonical_json_bytes(terminal)
    terminal_identity = _identity(
        "gs://dedicated-research/run/governance/terminal-receipt.json",
        ordinal + 3,
        terminal_raw,
    )
    return {
        "terminal_receipt_raw": terminal_raw,
        "terminal_receipt_identity": terminal_identity,
        "batch_completion_raw": completion_raw,
        "task_result_raw": task_result_raw,
        "graph_projection_raw": graph_raw,
        "sidecar_bodies": sidecar_bodies,
    }


def _plan(bundle: dict[str, Any]) -> projection.Neo4jLoadPlan:
    return projection.build_load_plan(**{
        key: bundle[key]
        for key in (
            "terminal_receipt_raw", "terminal_receipt_identity",
            "batch_completion_raw", "task_result_raw", "graph_projection_raw",
        )
    })


def _parametric_bundle(task_index: int = 0) -> dict[str, Any]:
    batch_id = "20260821-corpus-parametric-fixture-v1"
    manifest_sha = "2" * 64
    manifest_identity = _placeholder_identity("parametric/manifest.json", 200)
    completion_authority = _placeholder_identity(
        "parametric/source-completion.json", 350
    )
    policy_inventory = _placeholder_identity(
        "parametric/policy-inventory.json", 351
    )

    task_materials: list[dict[str, Any]] = []
    for index in range(54):
        task_key = f"task-{index:04d}"
        season = 2023 + index // 18
        week = index % 18 + 1
        slate_id = f"{season}-w{week}-main"
        task_sha = projection.canonical_sha256({
            "task_index": index,
            "slate_id": slate_id,
        })
        task_authority_sha = projection.canonical_sha256({
            "artifact_source_authority_task_index": index,
        })
        world_receipt_set_sha = projection.canonical_sha256({
            "world_artifact_receipt_set_task_index": index,
        })
        generation_base = 10_000 + index * 1_000
        variants: list[dict[str, object]] = []
        policy_rows: list[dict[str, object]] = []
        result_rows: list[dict[str, object]] = []
        for ordinal, parameter_id in enumerate(extensions.PARAMETER_SET_ORDER):
            policy = _placeholder_identity(
                f"parametric/{task_key}/{parameter_id}/effective-policy.json",
                generation_base + 10 + ordinal,
            )
            result = _placeholder_identity(
                f"parametric/{task_key}/{parameter_id}/result.json",
                generation_base + 20 + ordinal,
            )
            variants.append({
                "ordinal": ordinal,
                "parameter_set_id": parameter_id,
                "parameter_set_sha256": str(ordinal + 3) * 64,
                "effective_policy_receipt": policy,
                "result_object": result,
            })
            policy_rows.append({
                "ordinal": ordinal,
                "parameter_set_id": parameter_id,
                "object_identity": policy,
            })
            result_rows.append({
                "ordinal": ordinal,
                "parameter_set_id": parameter_id,
                "object_identity": result,
            })
        authorities = {
            role: _placeholder_identity(
                f"parametric/{task_key}/authority/{role}.json",
                generation_base + 100 + ordinal,
            )
            for ordinal, role in enumerate(extensions.AUTHORITY_ROLES)
        }
        terminal = _self_hash({
            "schema": extensions.PARAMETRIC_TERMINAL_SCHEMA,
            "batch_manifest_sha256": manifest_sha,
            "evidence_contract_identity": _placeholder_identity(
                f"parametric/{task_key}/evidence-contract.json",
                generation_base + 200,
            ),
            "evidence_contract_sha256": "a" * 64,
            "task_request_sha256": "b" * 64,
            "task_index": index,
            "task_sha256": task_sha,
            "execution_id": f"parametric-execution-{index}",
            "execution_uid": f"parametric-uid-{index}",
            "task_attempt": 0,
            "max_retries": 0,
            "succeeded_count": 1,
            "failed_count": 0,
            "cancelled_count": 0,
            "retried_count": 0,
            "completed_condition": "True",
            "strict_terminal_success": True,
            "runtime_image_terminal_verification": {
                "source_commit_sha": "c" * 40,
                "cloud_build_id": "12345678-1234-1234-1234-123456789abc",
                "immutable_image": {"digest": "sha256:" + "d" * 64},
                "terminal_verification_required": True,
            },
            "ambient_score_relevant_keys_present": [],
            "authorities": authorities,
            "runtime_policy_objects": policy_rows,
            "variant_result_objects": result_rows,
            "outcome_columns_read": [],
            "uses_realized_outcomes": False,
            "historical_scoring_licensed": False,
            "production_change_licensed": False,
            "decision_authority": False,
        }, "terminal_receipt_sha256")
        terminal_raw = projection.canonical_json_bytes(terminal)
        terminal_identity = _identity(
            f"gs://dedicated-research/parametric/{task_key}/task-terminal.json",
            generation_base + 300,
            terminal_raw,
        )
        task = _self_hash({
            "schema_version": extensions.PARAMETRIC_TASK_SCHEMA,
            "publication_mode": "create_once",
            "batch_manifest_identity": manifest_identity,
            "batch_id": batch_id,
            "batch_manifest_sha256": manifest_sha,
            "parameter_schema_sha256": "e" * 64,
            "common_law_sha256": "f" * 64,
            "task_index": index,
            "task_sha256": task_sha,
            "slate_id": slate_id,
            "world_artifact_receipts": [],
            "world_artifact_receipt_set_sha256": world_receipt_set_sha,
            "artifact_source_authority_task_sha256": task_authority_sha,
            "code_source": {},
            "immutable_image": {},
            "source_receipts": [],
            "source_receipt_set_sha256": "3" * 64,
            "later_source_freeze_manifest_sha256": "4" * 64,
            "artifact_source_authority_completion": completion_authority,
            "artifact_source_authority_completion_sha256": "5" * 64,
            "effective_policy_inventory_identity": policy_inventory,
            "effective_policy_inventory_sha256": "6" * 64,
            "effective_policy_rule_universe_sha256": "7" * 64,
            "effective_policy_inventory_source_set_sha256": "8" * 64,
            "effective_policy_classified_input_projection_sha256": "9" * 64,
            "world_schedule": {},
            "world_seed": index + 1,
            "solver": {},
            "execution": {
                "execution_id": f"parametric-execution-{index}",
                "execution_uid": f"parametric-uid-{index}",
                "task_index": index,
                "attempt": 1,
                "retry_count": 0,
                "terminal_status": "succeeded",
                "terminal_receipt": terminal_identity,
            },
            "variant_results": variants,
        }, "task_result_sha256")
        task_raw = projection.canonical_json_bytes(task)
        task_identity = _identity(
            f"gs://dedicated-research/parametric/{task_key}/task-result.json",
            generation_base + 400,
            task_raw,
        )
        task_materials.append({
            "season": season,
            "week": week,
            "slate_id": slate_id,
            "task": task,
            "task_raw": task_raw,
            "task_identity": task_identity,
            "terminal": terminal,
            "terminal_raw": terminal_raw,
            "terminal_identity": terminal_identity,
        })

    completion = _self_hash({
        "schema_version": extensions.PARAMETRIC_COMPLETION_SCHEMA,
        "publication_mode": "create_once",
        "batch_manifest_identity": manifest_identity,
        "batch_id": batch_id,
        "batch_manifest_sha256": manifest_sha,
        "parameter_schema_sha256": "e" * 64,
        "common_law_sha256": "f" * 64,
        "later_source_freeze_manifest_sha256": "4" * 64,
        "artifact_source_authority_completion": completion_authority,
        "artifact_source_authority_completion_sha256": "5" * 64,
        "effective_policy_classified_input_projection_sha256": "9" * 64,
        "coverage": {
            "task_count": 54,
            "parameter_set_count": 7,
            "matrix_cell_count": 378,
            "complete": True,
        },
        "task_results": [
            {
                "task_index": index,
                "task_sha256": material["task"]["task_sha256"],
                "artifact_source_authority_task_sha256": material["task"][
                    "artifact_source_authority_task_sha256"
                ],
                "world_artifact_receipt_set_sha256": material["task"][
                    "world_artifact_receipt_set_sha256"
                ],
                "task_result_sha256": material["task"]["task_result_sha256"],
                "task_result_object": material["task_identity"],
            }
            for index, material in enumerate(task_materials)
        ],
    }, "batch_completion_sha256")
    completion_raw = projection.canonical_json_bytes(completion)
    completion_identity = _identity(
        "gs://dedicated-research/parametric/batch-completion.json",
        370,
        completion_raw,
    )
    endpoint_rows = []
    coverage_rows = []
    outside_rows = []
    for ordinal, parameter_id in enumerate(extensions.PARAMETER_SET_ORDER):
        endpoint_rows.append(_self_hash({
            "schema": "corpus-score-free-endpoint-summary/v1",
            "parameter_set_id": parameter_id,
            "world_count": 50_000,
            "simulated_candidate_ceiling_c": 180.0 + ordinal,
            "simulated_exact80_maximum_s": 170.0 + ordinal,
            "simulated_conversion_gap_c_minus_s": 10.0,
        }, "endpoint_summary_sha256"))
        coverage_rows.append(_self_hash({
            "schema": "corpus-score-matrix-coverage/v1",
            "parameter_set_id": parameter_id,
            "generated_unique_roster_count": 100 + ordinal,
            "candidate_score_row_count": 100 + ordinal,
            "selected_roster_count": 80,
            "selected_score_row_count": 80,
            "world_count": 50_000,
            "complete_generated_unique_roster_row_coverage": True,
            "complete_selected_roster_row_coverage": True,
            "selected_rows_are_exact_candidate_subset": True,
        }, "coverage_sha256"))
        outside_rows.append(_self_hash({
            "schema": "corpus-outside-incumbent-law-nonvacuity/v1",
            "variant_ordinal": ordinal,
            "parameter_set_id": parameter_id,
            "outside_incumbent_law_unique_count": ordinal,
            "passed": True,
        }, "outside_law_nonvacuity_sha256"))
    challenger_rows = [{
        "challenger_variant_ordinal": ordinal,
        "challenger_parameter_set_id": extensions.PARAMETER_SET_ORDER[ordinal],
        "minimum_primary_optimum_delta_micro": 0,
        "maximum_primary_optimum_delta_micro": ordinal,
        "zero_delta_count": 1000 - ordinal,
        "positive_delta_count": ordinal,
        "all_deltas_nonnegative": True,
    } for ordinal in range(1, 7)]
    selected = task_materials[task_index]
    task = selected["task"]
    terminal = selected["terminal"]
    verification = _self_hash({
        "schema": extensions.PARAMETRIC_VERIFICATION_SCHEMA,
        "task_index": task_index,
        "season": selected["season"],
        "week": selected["week"],
        "slate_id": selected["slate_id"],
        "source_binding_sha256": "1" * 64,
        "registered_law_sha256": "2" * 64,
        "attempt_ledger_sha256": "3" * 64,
        "matrix_authority_sha256": "4" * 64,
        "solver_evidence_task_root_sha256": "5" * 64,
        "published_task_evidence_root_sha256": "6" * 64,
        "draft_sha256": "7" * 64,
        "authority_bundle_sha256": "8" * 64,
        "artifact_source_authority_completion_object_sha256": "9" * 64,
        "artifact_source_authority_completion_sha256": task[
            "artifact_source_authority_completion_sha256"
        ],
        "artifact_source_authority_task_sha256": task[
            "artifact_source_authority_task_sha256"
        ],
        "evidence_contract_sha256": "c" * 64,
        "task_result_sha256": task["task_result_sha256"],
        "terminal_receipt_sha256": terminal["terminal_receipt_sha256"],
        "variant_result_sha256s": [str(index + 1) * 64 for index in range(7)],
        "batch_result_sha256": "d" * 64,
        "candidate_score_sha256s": [str(index + 2) * 64 for index in range(7)],
        "selected_score_sha256s": [str(index + 3) * 64 for index in range(7)],
        "paired_primary_optimum_summary": _self_hash({
            "schema": "corpus-paired-primary-optimum-monotonicity/v1",
            "challenger_summaries": challenger_rows,
            "all_deltas_nonnegative": True,
        }, "paired_monotonicity_sha256"),
        "outside_incumbent_law_summaries": outside_rows,
        "score_free_endpoint_summaries": endpoint_rows,
        "score_matrix_coverage_summaries": coverage_rows,
        "verified_cell_count": 7_000,
        "verified_solver_stage_count": 14_000,
        "verified_unique_candidate_count": 721,
        "verified_selected_entry_count": 560,
        "verified_gate_ids": list(extensions.VERIFIED_GATE_IDS),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }, "verification_sha256")
    verification_raw = projection.canonical_json_bytes(verification)
    verification_identity = _identity(
        (
            "gs://dedicated-research/parametric/"
            f"task-{task_index:04d}/independent-verification.json"
        ),
        10_000 + task_index * 1_000 + 500,
        verification_raw,
    )
    return {
        "batch_completion_raw": completion_raw,
        "batch_completion_identity": completion_identity,
        "task_result_raw": selected["task_raw"],
        "task_result_identity": selected["task_identity"],
        "terminal_receipt_raw": selected["terminal_raw"],
        "terminal_receipt_identity": selected["terminal_identity"],
        "independent_verification_raw": verification_raw,
        "independent_verification_identity": verification_identity,
    }


def test_builds_receipt_bound_pointer_only_plan() -> None:
    plan = _plan(_bundle())
    assert plan.run_id == "20260821-retrieval-fixture-v1"
    assert plan.task_id == "slate-2023-w1"
    assert plan.summary()["large_world_bodies_stored"] is False
    assert plan.summary()["production_policy_mutation"] is False
    assert any(row["kind"] == "LineupCandidate" for row in plan.nodes)
    assert any(row["kind"] == "CorpusArtifactPointer" for row in plan.nodes)
    assert all(type(row["source_bytes"]) is int and row["source_bytes"] > 0 for row in plan.nodes)
    assert plan.graph_projection_identity["generation"]
    assert plan.terminal_receipt_identity["sha256"]


def test_rejects_incomplete_completion_and_unsafe_result() -> None:
    with pytest.raises(projection.CorpusRetrievalNeo4jError, match="incomplete"):
        _plan(_bundle(completion_complete=False))
    with pytest.raises(
        projection.CorpusRetrievalNeo4jError,
        match="production_default_change_authority",
    ):
        _plan(_bundle(result_production_license=True))


def test_rejects_changed_graph_bytes_and_generation_binding() -> None:
    changed = _bundle()
    changed["graph_projection_raw"] += b" "
    with pytest.raises(projection.CorpusRetrievalNeo4jError, match="content identity"):
        _plan(changed)

    changed = _bundle()
    terminal = projection.parse_canonical_json_bytes(
        changed["terminal_receipt_raw"], label="fixture terminal"
    )
    assert isinstance(terminal, dict)
    terminal.pop("terminal_receipt_sha256")
    terminal["result_object"]["generation"] = "999"
    terminal = _self_hash(terminal, "terminal_receipt_sha256")
    changed["terminal_receipt_raw"] = projection.canonical_json_bytes(terminal)
    changed["terminal_receipt_identity"] = _identity(
        "gs://dedicated-research/run/governance/terminal-receipt.json",
        1000,
        changed["terminal_receipt_raw"],
    )
    with pytest.raises(projection.CorpusRetrievalNeo4jError):
        _plan(changed)


def test_cypher_is_parameterized_and_apply_is_idempotent() -> None:
    plan = _plan(_bundle())
    statements = projection.load_statements(plan)
    assert len(statements) == 2
    assert all("$rows" in statement.query for statement in statements)
    assert all(plan.task_id not in statement.query for statement in statements)
    assert "MERGE" in statements[0].query
    assert "ON CREATE SET" in statements[0].query
    calls: list[tuple[str, dict[str, object]]] = []

    def accepted(query: str, parameters: dict[str, object]) -> dict[str, object]:
        calls.append((query, parameters))
        count = len(parameters["rows"])
        return {"row_count": count, "accepted_count": count}

    first = projection.apply_load_plan(
        plan, run_statement=accepted, database="corpus-research"
    )
    second = projection.apply_load_plan(
        plan, run_statement=accepted, database="corpus-research"
    )
    assert first == second
    assert first["idempotent"] is True
    assert first["database"] == "corpus-research"
    assert first["load_result_sha256"] == projection.canonical_sha256({
        key: value for key, value in first.items()
        if key != "load_result_sha256"
    })
    assert "node.source_bytes = row.source_bytes" in statements[0].query
    assert "source_alias.task_index <> row.task_index" in statements[0].query
    assert "source_alias.source_bytes = row.source_bytes" in statements[0].query
    assert len(calls) == 4


def test_immutable_conflict_fails_closed() -> None:
    plan = _plan(_bundle())

    def conflict(query: str, parameters: dict[str, object]) -> dict[str, object]:
        del query
        count = len(parameters["rows"])
        return {"row_count": count, "accepted_count": count - 1}

    with pytest.raises(projection.CorpusRetrievalNeo4jError, match="conflict"):
        projection.apply_load_plan(
            plan, run_statement=conflict, database="corpus-research"
        )


def test_execute_requires_literal_flag_and_environment_gate() -> None:
    with pytest.raises(projection.CorpusRetrievalNeo4jError, match="literal"):
        projection.require_execute_gate(execute=False, environ={projection.ENABLE_ENV: "1"})
    with pytest.raises(projection.CorpusRetrievalNeo4jError, match="literal"):
        projection.require_execute_gate(execute=True, environ={})
    projection.require_execute_gate(
        execute=True, environ={projection.ENABLE_ENV: "1"}
    )


def test_cli_validate_and_dry_run_never_contact_neo4j(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _bundle()
    paths: dict[str, Path] = {}
    for key in (
        "terminal_receipt_raw", "batch_completion_raw", "task_result_raw",
        "graph_projection_raw",
    ):
        path = tmp_path / f"{key}.json"
        path.write_bytes(bundle[key])
        paths[key] = path
    identity_path = tmp_path / "terminal-identity.json"
    identity_path.write_bytes(
        projection.canonical_json_bytes(bundle["terminal_receipt_identity"])
    )
    common = [
        "--terminal-receipt", str(paths["terminal_receipt_raw"]),
        "--terminal-receipt-identity", str(identity_path),
        "--batch-completion", str(paths["batch_completion_raw"]),
        "--task-result", str(paths["task_result_raw"]),
        "--graph-projection", str(paths["graph_projection_raw"]),
    ]
    assert cli.main(["validate", *common]) == 0
    validate = capsys.readouterr().out
    assert '"neo4j_contacted":false' in validate
    assert cli.main(["dry-run", *common]) == 0
    dry_run = capsys.readouterr().out
    assert '"parameter_names":["rows"]' in dry_run
    assert '"neo4j_contacted":false' in dry_run


def test_schema_file_matches_runtime_statements() -> None:
    raw = (ROOT / "cypher/corpus_retrieval_neo4j_schema.cypher").read_text()
    without_comments = "\n".join(
        line for line in raw.splitlines() if not line.lstrip().startswith("//")
    )
    actual = [" ".join(row.split()) for row in without_comments.split(";") if row.strip()]
    expected = [" ".join(row.split()) for row in projection.SCHEMA_STATEMENTS]
    assert actual == expected


def test_compact_retrieval_analytics_materialize_without_npz_bodies() -> None:
    bundle = _bundle(analytics=True)
    plan = extensions.append_retrieval_analytics(
        _plan(bundle),
        task_result_raw=bundle["task_result_raw"],
        json_sidecar_bodies=bundle["sidecar_bodies"],
    )
    kinds = {str(row["kind"]) for row in plan.nodes}
    assert "CorpusAssociationMeasurement" in kinds
    assert "CorpusCorrelationMeasurement" in kinds
    assert "CorpusStrategySplitMeasurement" in kinds
    assert all(row["workstream_namespace"] == extensions.RETRIEVAL_NAMESPACE for row in plan.nodes)
    assert not any("scores" in str(row["metric_name"]) for row in plan.nodes)


def test_parametric_extension_is_parented_separate_and_no_feedback() -> None:
    parent = _plan(_bundle())
    plan = extensions.append_parametric_batch(parent, **_parametric_bundle())
    namespaces = {str(row["workstream_namespace"]) for row in plan.nodes}
    assert namespaces == {
        extensions.RETRIEVAL_NAMESPACE,
        extensions.PARAMETRIC_NAMESPACE,
    }
    assert extensions.POPULATION_NAMESPACE not in namespaces
    assert sum(row["kind"] == "CorpusParametricArm" for row in plan.nodes) == 7
    assert sum(row["kind"] == "CorpusParametricRule" for row in plan.nodes) == 5
    parent_edges = [
        row for row in plan.relationships
        if row["relationship_type"] == "DERIVED_FROM_RETRIEVAL_TASK0"
    ]
    assert len(parent_edges) == 1
    assert parent_edges[0]["properties_json"] == (
        '{"automatic_policy_feedback":false,"lineage_scope":"suite-root-only",'
        '"same_slate_derivation_claim":false}'
    )
    assert parent_edges[0]["task_index_present"] is False
    workstream = next(
        row for row in plan.nodes if row["kind"] == "CorpusParametricWorkstream"
    )
    assert '"automatic_policy_feedback":false' in workstream["properties_json"]
    assert '"world_matrices_stored_in_graph":false' in workstream["properties_json"]
    assert '"corpus_fill_authority":false' in workstream["properties_json"]
    assert '"corpus_population_mutation_authority":false' in workstream[
        "properties_json"
    ]
    assert workstream["task_index_present"] is False
    assert all(type(row["source_bytes"]) is int for row in plan.nodes)
    assert not any(
        row["relationship_type"] in {"AUTHORIZES", "DEPLOYS", "MUTATES_POLICY"}
        for row in plan.relationships
    )


def test_parametric_task_zero_and_53_append_idempotently() -> None:
    parent = _plan(_bundle())
    task_zero = extensions.append_parametric_batch(
        parent, **_parametric_bundle(0)
    )
    task_53 = extensions.append_parametric_batch(
        task_zero, **_parametric_bundle(53)
    )
    repeated = extensions.append_parametric_batch(
        task_53, **_parametric_bundle(53)
    )
    assert repeated.plan_sha256 == task_53.plan_sha256
    assert len(repeated.nodes) == len(task_53.nodes)
    assert len(repeated.relationships) == len(task_53.relationships)

    task_53_nodes = [
        row for row in task_53.nodes if row["task_index"] == 53
    ]
    assert task_53_nodes
    assert all(row["task_index_present"] is True for row in task_53_nodes)
    assert all(row["slate_id"] == "2025-w18-main" for row in task_53_nodes)
    assert all(row["task_id"] == "2025-w18-main" for row in task_53_nodes)
    assert all("task-0053" in row["logical_id"] for row in task_53_nodes)
    assert not any("task-0000" in row["logical_id"] for row in task_53_nodes)
    task_53_edges = [
        row for row in task_53.relationships if row["task_index"] == 53
    ]
    assert task_53_edges
    assert all(row["slate_id"] == "2025-w18-main" for row in task_53_edges)
    assert sum(
        row["kind"] == "CorpusParametricWorkstream" for row in task_53.nodes
    ) == 1
    assert sum(
        row["relationship_type"] == "DERIVED_FROM_RETRIEVAL_TASK0"
        for row in task_53.relationships
    ) == 1
    receipt = projection.build_load_result_receipt(
        task_53,
        database="corpus-research",
        node_count=len(task_53.nodes),
        relationship_count=len(task_53.relationships),
    )
    assert receipt["workstream_namespaces"] == [
        extensions.PARAMETRIC_NAMESPACE,
        extensions.RETRIEVAL_NAMESPACE,
    ]
    assert receipt["task_indexes"] == [0, 53]
    assert sum(receipt["namespace_node_counts"].values()) == len(task_53.nodes)


def test_parametric_rejects_task_season_week_and_completion_mismatches() -> None:
    parent = _plan(_bundle())

    terminal_mismatch = _parametric_bundle(53)
    terminal = projection.parse_canonical_json_bytes(
        terminal_mismatch["terminal_receipt_raw"], label="fixture terminal"
    )
    assert isinstance(terminal, dict)
    terminal.pop("terminal_receipt_sha256")
    terminal["task_index"] = 52
    terminal = _self_hash(terminal, "terminal_receipt_sha256")
    terminal_mismatch["terminal_receipt_raw"] = projection.canonical_json_bytes(
        terminal
    )
    terminal_mismatch["terminal_receipt_identity"] = _identity(
        "gs://dedicated-research/parametric/task-0053/task-terminal-drift.json",
        999_001,
        terminal_mismatch["terminal_receipt_raw"],
    )
    with pytest.raises(projection.CorpusRetrievalNeo4jError):
        extensions.append_parametric_batch(parent, **terminal_mismatch)

    verification_mismatch = _parametric_bundle(53)
    verification = projection.parse_canonical_json_bytes(
        verification_mismatch["independent_verification_raw"],
        label="fixture verification",
    )
    assert isinstance(verification, dict)
    verification.pop("verification_sha256")
    verification["season"] = 2024
    verification["week"] = 17
    verification = _self_hash(verification, "verification_sha256")
    verification_mismatch["independent_verification_raw"] = (
        projection.canonical_json_bytes(verification)
    )
    verification_mismatch["independent_verification_identity"] = _identity(
        "gs://dedicated-research/parametric/task-0053/verification-drift.json",
        999_002,
        verification_mismatch["independent_verification_raw"],
    )
    with pytest.raises(
        projection.CorpusRetrievalNeo4jError, match="not accepted"
    ):
        extensions.append_parametric_batch(parent, **verification_mismatch)

    completion_mismatch = _parametric_bundle(53)
    completion = projection.parse_canonical_json_bytes(
        completion_mismatch["batch_completion_raw"], label="fixture completion"
    )
    assert isinstance(completion, dict)
    completion.pop("batch_completion_sha256")
    completion["task_results"][53]["task_sha256"] = "0" * 64
    completion = _self_hash(completion, "batch_completion_sha256")
    completion_mismatch["batch_completion_raw"] = projection.canonical_json_bytes(
        completion
    )
    completion_mismatch["batch_completion_identity"] = _identity(
        "gs://dedicated-research/parametric/batch-completion-drift.json",
        999_003,
        completion_mismatch["batch_completion_raw"],
    )
    with pytest.raises(
        projection.CorpusRetrievalNeo4jError, match="binding differs"
    ):
        extensions.append_parametric_batch(parent, **completion_mismatch)


def test_cross_task_retained_object_alias_is_rejected() -> None:
    plan = extensions.append_parametric_batch(
        _plan(_bundle()), **_parametric_bundle(0)
    )
    source = deepcopy(next(
        row for row in plan.nodes
        if row["kind"] == "CorpusParametricArtifactPointer"
    ))
    source["id"] = f"{source['id']}:task-0053-alias"
    source["logical_id"] = f"{source['logical_id']}:task-0053-alias"
    source["task_id"] = "2025-w18-main"
    source["task_index"] = 53
    source["slate_id"] = "2025-w18-main"
    with pytest.raises(
        projection.CorpusRetrievalNeo4jError, match="aliases across task indexes"
    ):
        projection.append_load_plan(plan, nodes=[source], relationships=[])


def test_load_result_receipt_is_create_exclusive_and_secret_free(
    tmp_path: Path,
) -> None:
    plan = _plan(_bundle())

    def accepted(_query: str, parameters: dict[str, object]) -> dict[str, object]:
        count = len(parameters["rows"])
        return {"row_count": count, "accepted_count": count}

    receipt = projection.apply_load_plan(
        plan, run_statement=accepted, database="corpus-research"
    )
    raw = projection.canonical_json_bytes(receipt)
    assert receipt["schema_version"] == projection.LOAD_RESULT_SCHEMA
    assert receipt["authority_flags"] == {
        "automatic_policy_feedback": False,
        "corpus_fill_authority": False,
        "corpus_population_mutation_authority": False,
        "decision_authority": False,
        "historical_outcome_read_authority": False,
        "live_money_policy_authority": False,
        "production_default_change_authority": False,
        "production_policy_authority": False,
    }
    assert b"bolt+s://private-endpoint" not in raw
    assert b"secret-user" not in raw
    assert b"secret-password" not in raw
    assert not re.search(rb'"(?:uri|username|password)"', raw)

    receipt_path = tmp_path / "load-result.json"
    cli._write_load_result_create_exclusive(receipt_path, receipt)
    assert receipt_path.read_bytes() == raw
    with pytest.raises(
        projection.CorpusRetrievalNeo4jError, match="already exists"
    ):
        cli._write_load_result_create_exclusive(receipt_path, receipt)
    assert receipt_path.read_bytes() == raw


def test_parametric_extension_rejects_unaccepted_verification() -> None:
    bundle = _parametric_bundle()
    verification = projection.parse_canonical_json_bytes(
        bundle["independent_verification_raw"], label="fixture verification"
    )
    assert isinstance(verification, dict)
    verification.pop("verification_sha256")
    verification["decision_authority"] = True
    verification = _self_hash(verification, "verification_sha256")
    bundle["independent_verification_raw"] = projection.canonical_json_bytes(
        verification
    )
    bundle["independent_verification_identity"] = _identity(
        "gs://dedicated-research/parametric/independent-verification.json",
        999,
        bundle["independent_verification_raw"],
    )
    with pytest.raises(projection.CorpusRetrievalNeo4jError, match="not accepted"):
        extensions.append_parametric_batch(_plan(_bundle()), **bundle)


def test_analysis_query_catalog_is_read_only_and_complete() -> None:
    source = (ROOT / "cypher/corpus_retrieval_analysis_queries.cypher").read_text()
    for query_name in (
        "high_tail_lineups",
        "high_tail_world_event_pointer",
        "player_pair_team_game_enrichment",
        "lineup_pair_correlations",
        "parameter_rule_arm_effects",
        "discovery_vs_heldout_strategy_comparison",
        "uncertainty_and_support_inputs",
        "parametric_workstream_parent_and_firewall",
        "parametric_suite_task_and_arm_coverage",
        "cross_slate_parameter_arm_effects",
        "cross_slate_arm_score_and_population_ranking",
        "reserved_population_namespace_audit",
    ):
        assert f"// query: {query_name}" in source
    upper = source.upper()
    for write_word in ("CREATE", "MERGE", "DELETE", "DETACH", "REMOVE"):
        assert not re.search(rf"\b{write_word}\b", upper)
    assert "$run_id" in source
    assert "$task_id" in source
    assert "$batch_id" in source
