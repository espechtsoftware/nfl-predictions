from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v1 as authority
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1
from nfl_dfs.research import corpus_v12_import as v12_import
from nfl_dfs.research import residual_world_columns as rw


NAMESPACE = "gs://fixture/r6-candidates/"
CATALOG_NAMESPACE = authority.catalog_adapter.FIXED_CATALOG_NAMESPACE
SOURCE_COMMIT = authority.catalog_adapter.FIXED_SOURCE_COMMIT_SHA


def _digest(label: str) -> str:
    return source.canonical_sha256({"fixture": label})


def _opaque_identity(label: str) -> dict[str, object]:
    return {
        "uri": f"gs://fixture/evidence/{label}.json",
        "generation": str(int(_digest(label)[:12], 16) + 1),
        "sha256": _digest(f"object:{label}"),
        "bytes": 100 + len(label),
    }


def _body_identity(
    body: Mapping[str, object], *, uri: str, generation: str,
) -> dict[str, object]:
    raw = source.canonical_json_bytes(body)
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _players() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for position, count in (("QB", 3), ("RB", 8), ("WR", 10), ("TE", 5), ("DST", 3)):
        for ordinal in range(count):
            rows.append({
                "id": f"{position.lower()}-{ordinal:02d}",
                "pos": position,
                "team": f"T{ordinal % 4}",
                "opp": f"T{(ordinal + 1) % 4}",
                "game_id": f"game-{ordinal % 4}",
                "salary": 3_000,
            })
    return sorted(rows, key=lambda row: str(row["id"]))


def _legal_lineups(players: list[dict[str, object]]) -> list[list[str]]:
    by_position = {
        position: [str(row["id"]) for row in players if row["pos"] == position]
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    lineups = [
        sorted([qb, *rbs, *wrs, *tes, dst])
        for qb, rbs, wrs, tes, dst in product(
            by_position["QB"],
            combinations(by_position["RB"], 2),
            combinations(by_position["WR"], 3),
            combinations(by_position["TE"], 2),
            by_position["DST"],
        )
    ]
    assert len(lineups) > 120
    return lineups[:120]


def _variant(
    *,
    source_ordinal: int,
    arm_ordinal: int,
    lineups: list[list[str]],
    task_sha256: str,
    batch_manifest_sha256: str,
    completion_identity: Mapping[str, object],
    completion_sha256: str,
    task_authority_sha256: str,
    source_manifest_sha256: str,
    world_identities: Mapping[str, Mapping[str, object]],
    visit_schedule_sha256: str,
) -> dict[str, object]:
    unique = [*lineups[:80], lineups[80 + arm_ordinal]]
    visits = [*unique, unique[0], unique[1], unique[2], unique[3]]
    slate = catalog_v1.expected_slate_for_source_task(source_ordinal)
    selected = unique[:80]
    expected_lane = catalog_v1.expected_lane_for_source_task(source_ordinal)
    task_source_binding = {
        "binding_sha256": _digest(f"binding:{source_ordinal}"),
        "batch_manifest_sha256": batch_manifest_sha256,
        "task_index": expected_lane["task_ordinal"],
        "task_sha256": task_sha256,
        "artifact_source_authority_completion_object_sha256": (
            completion_identity["sha256"]
        ),
        "artifact_source_authority_completion_sha256": completion_sha256,
        "artifact_source_authority_task_sha256": task_authority_sha256,
        "later_source_freeze_manifest_sha256": source_manifest_sha256,
        "world_artifact_receipt_set_sha256": source.canonical_sha256(
            world_identities
        ),
    }
    body: dict[str, object] = {
        "schema": v12_import.snapshot.VARIANT_RESULT_SCHEMA,
        "slate": slate,
        "profile": {
            "ordinal": arm_ordinal,
            "parameter_set_id": batch.PARAMETER_SET_ORDER[arm_ordinal],
        },
        "later_source_freeze_manifest_sha256": source_manifest_sha256,
        "artifact_sha256_by_block": {
            block: world_identities[role]["sha256"]
            for block, role in zip(
                rw.WORLD_BLOCKS, batch.TASK_WORLD_SOURCE_ROLES, strict=True
            )
        },
        "task_source_binding": task_source_binding,
        "visit_schedule_sha256": visit_schedule_sha256,
        "attempt_ledger_sha256": _digest(
            f"attempts:{source_ordinal}:{arm_ordinal}"
        ),
        "matrix_authority_sha256": _digest(
            f"matrix:{source_ordinal}:{arm_ordinal}"
        ),
        "solver_evidence_task_root_sha256": _digest(
            f"solver:{source_ordinal}:{arm_ordinal}"
        ),
        "visit_rosters": visits,
        "unique_rosters": unique,
        "first_occurrence_visit_indices": list(range(len(unique))),
        "coverage": {
            "scheduled_visits": len(visits),
            "attempted_visits": len(visits),
            "optimal_visits": len(visits),
            "unique_candidates": len(unique),
            "selected_entries": 80,
        },
        "runtime_effective_policy": {
            "fixture": f"arm-{arm_ordinal}"
        },
        "variant_attempt_rows_sha256": _digest(
            f"attempt-rows:{source_ordinal}:{arm_ordinal}"
        ),
        "candidate_score_sha256": _digest(
            f"candidate-score:{source_ordinal}:{arm_ordinal}"
        ),
        "selector": {
            "candidate_count": len(unique),
            "world_count": 5,
            "entry_count": 80,
            "tail_line_dk": 230.0,
            "selected_indices": list(range(80)),
            "tie_law_applied": "fixture-first-occurrence",
        },
        "selected_rosters": selected,
        "selected_score_sha256": _digest(
            f"selected-score:{source_ordinal}:{arm_ordinal}"
        ),
        "house_rule_violation_census": {},
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["result_sha256"] = source.canonical_sha256(body)
    return body


def _transport_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _transport_sha(value: object) -> str:
    return sha256(_transport_bytes(value)).hexdigest()


def _authoritative_acceptance(
    carrier_identity: Mapping[str, object],
    *,
    task_index: int,
    task_sha256: str,
) -> dict[str, object]:
    scheduler_sha = _digest(f"scheduler:{task_index}")
    governance = {
        "governance_mode": "live-all-region-census",
        "deployment_attestation_sha256": None,
        "governance_observed_at_utc": "2026-08-24T12:00:00Z",
        "attestation_created_at_utc": None,
        "attestation_expires_at_utc": None,
        "scheduler_census_sha256": scheduler_sha,
    }
    terminal = {
        "execution_id": f"verifier-{task_index}",
        "execution_name": f"verifier-{task_index}",
        "execution_uid": f"verifier-uid-{task_index}",
        "task_index": task_index,
        "phase": "verifier",
        "state": "True",
        "counters": {
            "succeeded": 1,
            "failed": 0,
            "cancelled": 0,
            "retried": 0,
        },
        "metadata_sha256": _digest(f"terminal:{task_index}"),
    }
    census = {
        "job": {
            "name": f"fixture-job-{task_index}",
            "uid": f"fixture-job-uid-{task_index}",
            "generation": str(task_index + 1),
            "observed_generation": str(task_index + 1),
            "spec_sha256": _digest(f"job:{task_index}"),
        },
        "phase": "verifier",
        "task_index": task_index,
        "execution_id": terminal["execution_id"],
        "execution_uid": terminal["execution_uid"],
        "execution_names": [f"producer-{task_index}", f"verifier-{task_index}"],
        "execution_census_sha256": _digest(f"census:{task_index}"),
        "scheduler_census_sha256": scheduler_sha,
        "launch_governance_authorization_sha256": _transport_sha(governance),
        "terminal_scheduler_census_sha256": scheduler_sha,
        "governance_authorization": governance,
        "all_regions_complete": True,
        "exactly_one_new_execution": True,
        "no_active_executions": True,
        "job_remains_parked": True,
    }
    body: dict[str, object] = {
        "schema_version": v12_import.TASK_ACCEPTANCE_SCHEMA,
        "accepted_at_utc": "2026-08-24T12:00:00Z",
        "transport_contract": _opaque_identity(f"transport:{task_index}"),
        "retrieval_task0_prerequisite_identity": _opaque_identity(
            f"retrieval:{task_index}"
        ),
        "task_index": task_index,
        "task_sha256": task_sha256,
        "producer_close": _opaque_identity(f"producer-close:{task_index}"),
        "science_terminal": _opaque_identity(f"science-terminal:{task_index}"),
        "task_result": dict(carrier_identity),
        "verifier_worker_completion": _opaque_identity(
            f"verifier-completion:{task_index}"
        ),
        "independent_verification": _opaque_identity(
            f"independent-verification:{task_index}"
        ),
        "independent_verification_sha256": _digest(
            f"verification:{task_index}"
        ),
        "verifier_terminal_execution": terminal,
        "terminal_governance_census": census,
        "evidence_object_count": 140,
        "complete_evidence_receipt": True,
        "independent_verification_complete": True,
        "strict_verifier_terminal_success": True,
        "accepted": True,
        "partial_result": False,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    body["task_acceptance_sha256"] = _transport_sha(body)
    return body


def _old_catalog_terminal_final_lock_raw() -> bytes:
    body: dict[str, object] = {
        "schema_version": authority.catalog_successor.OLD_FINAL_LOCK_SCHEMA,
        "evidence_source_commit_sha": SOURCE_COMMIT,
        "implementation_commit_sha": "2" * 40,
        "implementation_measurements": [],
        "focused_test_command": [],
        "focused_test_cwd": "/fixture",
        "focused_test_pythonpath": "/fixture/src",
        "terminal_recovery_review_lock_file": {"fixture": True},
        "terminal_recovery_review_lock_internal_sha256": _digest(
            "terminal-review"
        ),
        "base_adapter_review_binding": {
            "review_lock_commit_sha": "3" * 40,
            "implementation_commit_sha": "4" * 40,
            "review_lock_relative_path": "reports/fixture-adapter-review.json",
            "review_lock_file_sha256": _digest("adapter-review-file"),
            "review_lock_file_bytes": 100,
            "review_lock_internal_sha256": _digest("adapter-review-internal"),
            "implementation_measurements": [],
        },
        "amendment_file": {"fixture": True},
        "v2_failure_file": {"fixture": True},
        "v1_attempt_file": {"fixture": True},
        "v1_attempt_internal_sha256": _digest("v1-attempt"),
        "v2_attempt_file": {"fixture": True},
        "v2_attempt_internal_sha256": _digest("v2-attempt"),
        "adapter_attempt_count": 2,
        "adapter_v1_smoke_passed": False,
        "adapter_v2_smoke_passed": False,
        "adapter_success_receipt_absent": True,
        "prior_real_artifact_smoke_file": {"fixture": True},
        "prior_real_artifact_smoke_internal_sha256": _digest("prior-smoke"),
        "prior_real_artifact_smoke_time_file": {"fixture": True},
        "prior_real_artifact_smoke_passed": True,
        "third_adapter_smoke_allowed": False,
        "independent_static_review_passed": True,
        "p0_open_count": 0,
        "p1_open_count": 0,
        "p2_open_count": 0,
        "current_clean_git_required": True,
        "required_source_task_count": source.TASK_COUNT,
        "required_task_acceptance_body_reopen_count": source.TASK_COUNT,
        "required_carrier_body_reopen_count": source.TASK_COUNT,
        "all_inputs_derived_before_first_output": True,
        "projection_only_publication_reviewed": True,
        "projection_only_publication_licensed": True,
        "projection_release_command": list(
            authority.catalog_successor.OLD_PROJECTION_COMMAND
        ),
        "production_enable_environment_variable": (
            authority.catalog_adapter.PRODUCTION_ENABLE_ENV
        ),
        "production_enable_environment_value": "1",
        "gcs_create_once_required": True,
        "gcs_overwrite_licensed": False,
        "world_matrix_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        **{
            field: False
            for field in authority.catalog_successor._FALSE_AUTHORITY_FIELDS
        },
    }
    body["final_release_lock_sha256"] = source.canonical_sha256(body)
    return source.canonical_json_bytes(body) + b"\n"


def _successor_authority_files(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[tuple[str, str], bytes], bytes]:
    successor = authority.catalog_successor
    old_raw = _old_catalog_terminal_final_lock_raw()
    failure_raw = b"fixture projection failed before output creation\n"
    implementation_commit = "2" * 40
    implementation_raw = {
        path: f"fixture implementation: {path}\n".encode("utf-8")
        for path in successor.IMPLEMENTATION_PATHS
    }
    focused_raw = b".  [100%]\n1 passed in 0.01s\n"
    monkeypatch.setattr(successor, "OLD_FINAL_LOCK_COMMIT", "5" * 40)
    monkeypatch.setattr(successor, "OLD_FINAL_LOCK_SHA256", sha256(old_raw).hexdigest())
    monkeypatch.setattr(successor, "OLD_FINAL_LOCK_BYTES", len(old_raw))
    monkeypatch.setattr(
        successor,
        "OLD_FINAL_LOCK_INTERNAL_SHA256",
        json.loads(old_raw.decode())["final_release_lock_sha256"],
    )
    monkeypatch.setattr(successor, "FAILURE_REPORT_SHA256", sha256(failure_raw).hexdigest())
    monkeypatch.setattr(successor, "FAILURE_REPORT_BYTES", len(failure_raw))
    monkeypatch.setattr(successor, "EXPECTED_ADAPTER_CASE_COUNT", 0)
    monkeypatch.setattr(successor, "EXPECTED_SUCCESSOR_CASE_COUNT", 1)
    monkeypatch.setattr(successor, "EXPECTED_FOCUSED_CASE_COUNT", 1)
    measurements = [
        {
            "relative_path": path,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        for path, raw in implementation_raw.items()
    ]
    evidence = {
        "old_final_lock_commit_sha": successor.OLD_FINAL_LOCK_COMMIT,
        "old_final_lock_file": {
            "relative_path": successor.OLD_FINAL_LOCK_PATH,
            "sha256": sha256(old_raw).hexdigest(),
            "bytes": len(old_raw),
        },
        "old_final_lock_internal_sha256": successor.OLD_FINAL_LOCK_INTERNAL_SHA256,
        "base_adapter_review_binding": json.loads(old_raw.decode())["base_adapter_review_binding"],
        "prior_real_artifact_smoke_file": {"fixture": True},
        "prior_real_artifact_smoke_internal_sha256": _digest("prior-smoke"),
        "projection_failure_report_file": {
            "relative_path": successor.FAILURE_REPORT_PATH,
            "sha256": sha256(failure_raw).hexdigest(),
            "bytes": len(failure_raw),
        },
        "failed_projection_command": list(successor.OLD_PROJECTION_COMMAND),
        "failed_projection_cwd": successor.FAILED_PROJECTION_CWD,
        "failed_projection_clean_commit_sha": successor.OLD_FINAL_LOCK_COMMIT,
        "failed_projection_exit_code": successor.FAILED_PROJECTION_EXIT_CODE,
        "failed_projection_exception": successor.FAILED_PROJECTION_EXCEPTION,
        "failed_projection_source_completion_identity": dict(
            authority.catalog_adapter.FIXED_SOURCE_COMPLETION_IDENTITY
        ),
        "observed_source_completion_field": successor.OBSERVED_SOURCE_COMPLETION_FIELD,
        "observed_source_completion_value": successor.OBSERVED_SOURCE_COMPLETION_VALUE,
        "source_task_zero_keys_matched": True,
        "source_task_fifty_three_keys_matched": True,
        "first_projection_output_create_count": 0,
        "first_projection_failed_before_output_create_phase": True,
        "adapter_attempt_count": 2,
        "adapter_v1_smoke_passed": False,
        "adapter_v2_smoke_passed": False,
        "adapter_success_receipt_absent": True,
        "prior_real_artifact_smoke_passed": True,
        "third_adapter_smoke_allowed": False,
    }
    review = successor._build_review_lock(
        implementation_commit_sha=implementation_commit,
        implementation_measurements=measurements,
        evidence=evidence,
        focused_output_file={
            "relative_path": successor.FOCUSED_OUTPUT_PATH,
            "sha256": sha256(focused_raw).hexdigest(),
            "bytes": len(focused_raw),
        },
        focused_pass_count=1,
        independent_static_review_passed=True,
    )
    review_raw = successor.canonical_bytes(review) + b"\n"
    final = successor._build_final_lock(
        review_lock_file={
            "relative_path": successor.REVIEW_LOCK_PATH,
            "sha256": sha256(review_raw).hexdigest(),
            "bytes": len(review_raw),
        },
        review_lock=review,
    )
    final_raw = successor.canonical_bytes(final) + b"\n"
    files = {
        (successor.OLD_FINAL_LOCK_COMMIT, successor.OLD_FINAL_LOCK_PATH): old_raw,
        (SOURCE_COMMIT, successor.OLD_FINAL_LOCK_PATH): old_raw,
        (SOURCE_COMMIT, successor.FAILURE_REPORT_PATH): failure_raw,
        (SOURCE_COMMIT, successor.FOCUSED_OUTPUT_PATH): focused_raw,
        (SOURCE_COMMIT, successor.REVIEW_LOCK_PATH): review_raw,
        (SOURCE_COMMIT, successor.FINAL_LOCK_PATH): final_raw,
    }
    for path, raw in implementation_raw.items():
        files[(implementation_commit, path)] = raw
        files[(SOURCE_COMMIT, path)] = raw
    monkeypatch.setattr(
        authority.catalog_adapter,
        "_reopen_adapter_review_binding_v1",
        lambda **_kwargs: None,
    )
    return files, final_raw


def _chain(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(authority, "VISITS_PER_BLOCK", 17)
    players = _players()
    lineups = _legal_lineups(players)
    panel_identity = _opaque_identity("fixed-g0-panel")
    store: dict[tuple[str, str], bytes] = {}
    read_counts: dict[tuple[str, str], int] = {}
    result_body_read_count = 0
    source_manifest_sha = _digest("later-source-internal")
    later_source_identity = _opaque_identity("later-source")
    completion_identity = _opaque_identity("source-completion")
    completion_sha = _digest("source-completion-internal")
    batch_manifest_sha = _digest("batch-manifest")
    members: list[dict[str, object]] = []
    task_rows: list[dict[str, object]] = []
    for source_ordinal in range(source.TASK_COUNT):
        expected_lane = catalog_v1.expected_lane_for_source_task(source_ordinal)
        slate = catalog_v1.expected_slate_for_source_task(source_ordinal)
        task_sha = _digest(f"task:{source_ordinal}")
        task_authority_sha = _digest(f"source-authority:{source_ordinal}")
        world_identities = {
            role: _opaque_identity(f"world:{source_ordinal}:{role}")
            for role in batch.TASK_WORLD_SOURCE_ROLES
        }
        schedule_rows = [
            {"block": block, "index": index}
            for block in rw.WORLD_BLOCKS
            for index in range(authority.VISITS_PER_BLOCK)
        ]
        visit_schedule_sha = source.canonical_sha256(schedule_rows)
        world_schedule = {
            "schema": authority.WORLD_SCHEDULE_SCHEMA,
            "method": "top-total-slate-player-draw-desc",
            "score_accumulator": "float64-sum-of-all-slate-player-draws",
            "tie_break": "world-index-ascending-stable",
            "block_order": list(rw.WORLD_BLOCKS),
            "source_worlds_per_block": rw.WORLDS_PER_BLOCK,
            "visits_per_block": authority.VISITS_PER_BLOCK,
            "slates": [{
                "task_index": expected_lane["task_ordinal"],
                "season": slate["season"],
                "week": slate["week"],
                "slate_id": slate["slate_id"],
                "later_source_freeze_manifest_sha256": source_manifest_sha,
                "world_artifact_receipt_set_sha256": source.canonical_sha256(
                    world_identities
                ),
                "blocks": [{
                    "block": block,
                    "world_indices": list(range(authority.VISITS_PER_BLOCK)),
                } for block in rw.WORLD_BLOCKS],
                "visit_schedule_sha256": visit_schedule_sha,
            }],
        }
        world_schedule_identity = _body_identity(
            world_schedule,
            uri=f"gs://fixture/schedules/{source_ordinal:02d}/world-schedule.json",
            generation=str(900 + source_ordinal),
        )
        store[(
            world_schedule_identity["uri"],
            world_schedule_identity["generation"],
        )] = source.canonical_json_bytes(world_schedule)
        variants = [
            _variant(
                source_ordinal=source_ordinal,
                arm_ordinal=arm_ordinal,
                lineups=lineups,
                task_sha256=task_sha,
                batch_manifest_sha256=batch_manifest_sha,
                completion_identity=completion_identity,
                completion_sha256=completion_sha,
                task_authority_sha256=task_authority_sha,
                source_manifest_sha256=source_manifest_sha,
                world_identities=world_identities,
                visit_schedule_sha256=visit_schedule_sha,
            )
            for arm_ordinal in range(7)
        ]
        result_identities: list[dict[str, object]] = []
        carrier_result_rows: list[dict[str, object]] = []
        arms: list[dict[str, object]] = []
        for arm_ordinal, variant in enumerate(variants):
            result_raw = source.canonical_json_bytes(variant)
            result_identity = _body_identity(
                variant,
                uri=(
                    f"gs://fixture/results/{source_ordinal:02d}/"
                    f"{arm_ordinal}/result.json"
                ),
                generation=str(1_000 + source_ordinal * 7 + arm_ordinal),
            )
            store[(result_identity["uri"], result_identity["generation"])] = (
                result_raw
            )
            result_identities.append(result_identity)
            carrier_result_rows.append({
                "ordinal": arm_ordinal,
                "parameter_set_id": batch.PARAMETER_SET_ORDER[arm_ordinal],
                "parameter_set_sha256": _digest(
                    f"parameter:{source_ordinal}:{arm_ordinal}"
                ),
                "effective_policy_receipt": {"fixture": True},
                "result_object": result_identity,
            })
            arms.append({
                "arm_ordinal": arm_ordinal,
                "parameter_set_id": batch.PARAMETER_SET_ORDER[arm_ordinal],
                "result_identity": result_identity,
            })
        carrier: dict[str, object] = {
            "schema_version": batch.TASK_RESULT_SCHEMA,
            "publication_mode": "create_once",
            "task_index": expected_lane["task_ordinal"],
            "slate_id": slate["slate_id"],
            "task_sha256": task_sha,
            "batch_manifest_sha256": batch_manifest_sha,
            "artifact_source_authority_completion": completion_identity,
            "artifact_source_authority_completion_sha256": completion_sha,
            "artifact_source_authority_task_sha256": task_authority_sha,
            "later_source_freeze_manifest_sha256": source_manifest_sha,
            "world_artifact_receipts": world_identities,
            "world_artifact_receipt_set_sha256": source.canonical_sha256(
                world_identities
            ),
            "world_schedule": world_schedule_identity,
            "variant_results": carrier_result_rows,
        }
        carrier["task_result_sha256"] = source.canonical_sha256(carrier)
        carrier_identity = _body_identity(
            carrier,
            uri=f"gs://fixture/carriers/{source_ordinal:02d}/task-result.json",
            generation=str(2_000 + source_ordinal),
        )
        store[(carrier_identity["uri"], carrier_identity["generation"])] = (
            source.canonical_json_bytes(carrier)
        )
        acceptance = _authoritative_acceptance(
            carrier_identity,
            task_index=int(expected_lane["task_ordinal"]),
            task_sha256=task_sha,
        )
        acceptance_raw = _transport_bytes(acceptance)
        acceptance_identity = {
            "uri": f"gs://fixture/acceptances/{source_ordinal:02d}.json",
            "generation": str(3_000 + source_ordinal),
            "sha256": sha256(acceptance_raw).hexdigest(),
            "bytes": len(acceptance_raw),
        }
        store[(acceptance_identity["uri"], acceptance_identity["generation"])] = (
            acceptance_raw
        )
        member: dict[str, object] = {
            "slate_id": slate["slate_id"],
            **expected_lane,
            "source_task_ordinal": source_ordinal,
            "source_task_authority_sha256": task_authority_sha,
            "task_acceptance_identity": acceptance_identity,
            "carrier_identity": carrier_identity,
            "arms": arms,
        }
        members.append(member)
        task_rows.append({
            "task_sha256": task_sha,
            "task_authority_sha256": task_authority_sha,
            "world_identities": world_identities,
            "world_schedule": world_schedule,
            "world_schedule_identity": world_schedule_identity,
            "acceptance": acceptance,
            "acceptance_identity": acceptance_identity,
            "carrier": carrier,
            "carrier_identity": carrier_identity,
            "result_identities": result_identities,
        })

    panel = {
        "panel_id": "v12:" + _digest("terminals"),
        "panel_index_sha256": _digest("panel-index"),
        "accepted_slate_count": source.TASK_COUNT,
        "accepted_slates": members,
    }
    git_binding = {
        "sha256": _digest("g0-lock-file"),
        "g0_authority_lock_sha256": _digest("g0-lock-internal"),
        "source_commit_sha": SOURCE_COMMIT,
    }
    publication_receipt = {
        "panel_object_identity": panel_identity,
        "publication_receipt_sha256": _digest("publication-receipt"),
    }
    publication_binding = {"sha256": _digest("publication-file")}
    tracked_root = catalog_v1.normalize_tracked_root_binding({
        "g0_authority_lock_schema": (
            authority.panel_execution.G0_AUTHORITY_LOCK_SCHEMA
        ),
        "g0_authority_lock_relative_path": (
            authority.panel_execution.FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH
        ),
        "g0_authority_lock_file_sha256": git_binding["sha256"],
        "g0_authority_lock_sha256": git_binding["g0_authority_lock_sha256"],
        "source_commit_sha": SOURCE_COMMIT,
        "panel_object_identity": panel_identity,
        "panel_index_sha256": panel["panel_index_sha256"],
        "accepted_slate_count": source.TASK_COUNT,
    })
    code_identity = catalog_v1.normalize_code_identity({
        "source_commit_sha": SOURCE_COMMIT,
        "module_path": authority.catalog_adapter.FIXED_CATALOG_MODULE_PATH,
        "module_sha256": authority.catalog_adapter.FIXED_CATALOG_MODULE_SHA256,
    })
    member_bindings: list[dict[str, object]] = []
    source_bindings: list[dict[str, object]] = []
    completion_bindings: list[dict[str, object]] = []
    catalog_identities: list[dict[str, object]] = []
    catalog_bodies: list[dict[str, object]] = []
    for source_ordinal, (member, task_row) in enumerate(
        zip(members, task_rows, strict=True)
    ):
        slate = catalog_v1.expected_slate_for_source_task(source_ordinal)
        expected_lane = catalog_v1.expected_lane_for_source_task(source_ordinal)
        player_ids_sha = source.canonical_sha256([
            player["id"] for player in players
        ])
        catalog_sha = source.canonical_sha256(players)
        member_binding = catalog_v1.normalize_member_binding({
            "lane_id": expected_lane["lane_id"],
            "lane_ordinal": expected_lane["lane_ordinal"],
            "task_ordinal": expected_lane["task_ordinal"],
            "source_task_ordinal": source_ordinal,
            "task_id": catalog_v1.task_id_for_source_task(source_ordinal),
            "slate_id": slate["slate_id"],
            "accepted_slate_membership_sha256": source.canonical_sha256(member),
            "task_acceptance_identity": task_row["acceptance_identity"],
            "carrier_identity": task_row["carrier_identity"],
            "source_task_authority_sha256": task_row[
                "task_authority_sha256"
            ],
        })
        source_binding = catalog_v1.normalize_source_catalog_binding({
            "later_source_freeze_identity": later_source_identity,
            "later_source_freeze_manifest_sha256": source_manifest_sha,
            "source_task_ordinal": source_ordinal,
            "slate": slate,
            "catalog_sha256": catalog_sha,
            "catalog_player_count": len(players),
            "catalog_player_ids_sha256": player_ids_sha,
        })
        completion_binding = catalog_v1.normalize_completion_binding({
            "artifact_source_authority_completion_identity": completion_identity,
            "artifact_source_authority_completion_sha256": completion_sha,
            "later_source_freeze_identity": later_source_identity,
            "later_source_freeze_manifest_sha256": source_manifest_sha,
            "source_task_ordinal": source_ordinal,
            "slate": slate,
            "universe_scope": catalog_v1.UNIVERSE_SCOPE,
            "task_source_authority_sha256": task_row[
                "task_authority_sha256"
            ],
            "catalog_sha256": catalog_sha,
            "catalog_player_count": len(players),
            "catalog_player_ids_sha256": player_ids_sha,
        })
        derivation = catalog_v1.build_derivation_receipt_v1(
            tracked_root_binding=tracked_root,
            accepted_member_binding=member_binding,
            source_catalog_binding=source_binding,
            artifact_source_completion_binding=completion_binding,
            structural_players=players,
            derivation_code_identity=code_identity,
        )
        child_prefix = (
            f"{CATALOG_NAMESPACE}tasks/{source_ordinal:04d}-"
            f"{slate['slate_id']}/"
        )
        derivation_identity = _body_identity(
            derivation,
            uri=f"{child_prefix}catalog-derivation-receipt.json",
            generation=str(4_000 + source_ordinal * 2),
        )
        store[(derivation_identity["uri"], derivation_identity["generation"])] = (
            source.canonical_json_bytes(derivation)
        )
        catalog = catalog_v1.build_player_catalog_v1(
            derivation_receipt=derivation,
            derivation_receipt_identity=derivation_identity,
            structural_players=players,
        )
        catalog_identity = _body_identity(
            catalog,
            uri=f"{child_prefix}player-catalog.json",
            generation=str(4_001 + source_ordinal * 2),
        )
        store[(catalog_identity["uri"], catalog_identity["generation"])] = (
            source.canonical_json_bytes(catalog)
        )
        member_bindings.append(member_binding)
        source_bindings.append(source_binding)
        completion_bindings.append(completion_binding)
        catalog_identities.append(catalog_identity)
        catalog_bodies.append(catalog)

    def raw_read(identity: Mapping[str, object]) -> bytes:
        return store[(str(identity["uri"]), str(identity["generation"]))]

    catalog_release = catalog_v1.build_release_v1(
        release_id=authority.catalog_adapter.FIXED_RELEASE_ID,
        catalog_namespace=CATALOG_NAMESPACE,
        expected_tracked_root_binding=tracked_root,
        expected_member_bindings=member_bindings,
        expected_source_catalog_bindings=source_bindings,
        expected_completion_bindings=completion_bindings,
        expected_derivation_code_identity=code_identity,
        player_catalog_identities=catalog_identities,
        read_exact=raw_read,
    )
    catalog_release_identity = _body_identity(
        catalog_release,
        uri=f"{CATALOG_NAMESPACE}catalog-release.json",
        generation="5000",
    )
    store[(
        catalog_release_identity["uri"],
        catalog_release_identity["generation"],
    )] = source.canonical_json_bytes(catalog_release)
    acceptance_manifest = [{
        "source_task_ordinal": ordinal,
        "identity": task_row["acceptance_identity"],
        "self_hash": task_row["acceptance"]["task_acceptance_sha256"],
    } for ordinal, task_row in enumerate(task_rows)]
    carrier_manifest = [{
        "source_task_ordinal": ordinal,
        "identity": task_row["carrier_identity"],
        "self_hash": task_row["carrier"]["task_result_sha256"],
    } for ordinal, task_row in enumerate(task_rows)]
    replay_receipt: dict[str, object] = {
        "schema_version": authority.catalog_adapter.ADAPTER_SCHEMA,
        "replay_id": "fixed-g0-r6-player-catalog-projection-v1",
        "replay_scope": "accepted-panel-index-projection-rooted-in-frozen-g0-evidence",
        "pin_set_sha256": _digest("pin-set"),
        "tracked_root_binding": tracked_root,
        "official_publication_receipt_file": {"fixture": True},
        "official_publication_receipt_sha256": _digest("publication"),
        "adapter_review_binding": {"fixture": True},
        "lane_terminal_identities": [
            _opaque_identity("lane-terminal-0"),
            _opaque_identity("lane-terminal-1"),
        ],
        "lane_completion_identities": [
            _opaque_identity("lane-completion-0"),
            _opaque_identity("lane-completion-1"),
        ],
        "later_source_freeze_identity": later_source_identity,
        "later_source_freeze_manifest_sha256": source_manifest_sha,
        "artifact_source_authority_completion_identity": completion_identity,
        "artifact_source_authority_completion_sha256": completion_sha,
        "derivation_code_identity": code_identity,
        "catalog_namespace": CATALOG_NAMESPACE,
        "catalog_release_identity": catalog_release_identity,
        "catalog_release_sha256": catalog_release["release_sha256"],
        "task_count": source.TASK_COUNT,
        "task_acceptance_body_count": source.TASK_COUNT,
        "task_acceptance_body_manifest_sha256": source.canonical_sha256(
            acceptance_manifest
        ),
        "carrier_body_count": source.TASK_COUNT,
        "carrier_body_manifest_sha256": source.canonical_sha256(
            carrier_manifest
        ),
        "member_binding_manifest_sha256": source.canonical_sha256(
            member_bindings
        ),
        "source_catalog_binding_manifest_sha256": source.canonical_sha256(
            source_bindings
        ),
        "completion_binding_manifest_sha256": source.canonical_sha256(
            completion_bindings
        ),
        "structural_catalog_manifest_sha256": source.canonical_sha256([
            players for _ in range(source.TASK_COUNT)
        ]),
        "catalog_identity_manifest_sha256": source.canonical_sha256(
            catalog_identities
        ),
        "accepted_panel_index_projection_only": True,
        "fresh_task_or_arm_body_revalidation_performed": True,
        "task_acceptance_bodies_reopened": True,
        "carrier_bodies_reopened": True,
        "source_completion_artifact_bodies_reopened": False,
        "world_matrix_bodies_reopened": False,
        "result_object_bodies_reopened": False,
        "execution_manifest_pin_required": True,
        "self_authorizing": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{
            field: False for field in authority._CATALOG_REPLAY_FALSE_FIELDS
        },
    }
    replay_receipt["replay_receipt_sha256"] = source.canonical_sha256(
        replay_receipt
    )
    catalog_replay_receipt_identity = _body_identity(
        replay_receipt,
        uri=(
            f"{CATALOG_NAMESPACE}"
            f"{authority.CATALOG_REPLAY_RECEIPT_FILENAME}"
        ),
        generation="5001",
    )
    store[(
        catalog_replay_receipt_identity["uri"],
        catalog_replay_receipt_identity["generation"],
    )] = source.canonical_json_bytes(replay_receipt)
    git_files, final_lock_raw = _successor_authority_files(monkeypatch)

    def replay(**_kwargs: object) -> tuple[object, ...]:
        return (
            publication_binding,
            publication_receipt,
            panel,
            [],
            git_binding,
        )

    def read_task_variant_results(
        carrier_raw: bytes,
        *,
        carrier_identity: Mapping[str, object],
        read_exact: Any,
        require_authoritative: bool,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        nonlocal result_body_read_count
        assert require_authoritative is True
        carrier = json.loads(carrier_raw.decode())
        retained = carrier["task_result_sha256"]
        unhashed = {
            key: value for key, value in carrier.items()
            if key != "task_result_sha256"
        }
        assert retained == source.canonical_sha256(unhashed)
        results: list[dict[str, object]] = []
        for row in carrier["variant_results"]:
            identity = row["result_object"]
            raw = read_exact(identity)
            results.append(
                v12_import.snapshot.validate_variant_result_bytes(
                    raw,
                    identity=identity,
                    require_authoritative=False,
                )
            )
            result_body_read_count += 1
        return carrier, results

    monkeypatch.setattr(
        authority.panel_execution, "replay_published_v12_panel_v1", replay
    )
    monkeypatch.setattr(
        authority.v12_import.snapshot,
        "read_task_variant_results",
        read_task_variant_results,
    )
    return {
        "players": players,
        "lineups": lineups,
        "members": members,
        "panel": panel,
        "panel_identity": panel_identity,
        "git_binding": git_binding,
        "task_rows": task_rows,
        "catalog_release_identity": catalog_release_identity,
        "catalog_replay_receipt_identity": catalog_replay_receipt_identity,
        "catalog_replay_receipt": replay_receipt,
        "member_bindings": member_bindings,
        "source_bindings": source_bindings,
        "completion_bindings": completion_bindings,
        "store": store,
        "read_counts": read_counts,
        "result_body_read_count": lambda: result_body_read_count,
        "final_lock_raw": final_lock_raw,
        "git_files": git_files,
        "catalogs": catalog_bodies,
    }


@pytest.fixture
def chain(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    return _chain(monkeypatch)


def _read_exact(chain: Mapping[str, Any]):
    def read(identity: Mapping[str, object]) -> bytes:
        key = (str(identity["uri"]), str(identity["generation"]))
        chain["read_counts"][key] = chain["read_counts"].get(key, 0) + 1
        return chain["store"][key]

    return read


def _noop_head(_root: Path) -> str:
    return SOURCE_COMMIT


def _git_blob(chain: Mapping[str, Any]):
    def read(_root: Path, commit: str, path: str) -> bytes:
        return chain["git_files"][(commit, path)]

    return read


def _noop_status(_root: Path, _paths: object) -> bytes:
    return b""


def _material(chain: Mapping[str, Any]) -> dict[str, object]:
    return authority.derive_fixed_g0_candidate_material_v1(
        repository_root=Path("/fixture"),
        catalog_replay_receipt_identity=chain[
            "catalog_replay_receipt_identity"
        ],
        read_exact=_read_exact(chain),
        git_head=_noop_head,
        git_blob=_git_blob(chain),
        git_status=_noop_status,
    )


def _build(chain: Mapping[str, Any]) -> dict[str, object]:
    material = _material(chain)
    identities = _publish_candidate_artifacts(chain, material)
    return _build_from_identities(chain, identities)


def _publish_candidate_artifacts(
    chain: Mapping[str, Any], material: Mapping[str, object],
) -> list[dict[str, object]]:
    identities: list[dict[str, object]] = []
    for ordinal, artifact_value in enumerate(material["candidate_artifacts"]):
        artifact = dict(artifact_value)
        slate = artifact["slate"]
        identity = _body_identity(
            artifact,
            uri=(
                f"{NAMESPACE}source-task-{ordinal:02d}-"
                f"{slate['slate_id']}/accepted-candidates.json"
            ),
            generation=str(10_000 + ordinal),
        )
        identities.append(identity)
        chain["store"][(identity["uri"], identity["generation"])] = (
            source.canonical_json_bytes(artifact)
        )
    return identities


def _build_from_identities(
    chain: Mapping[str, Any], identities: list[dict[str, object]],
    *, read_exact: Any | None = None,
) -> dict[str, object]:
    return authority.build_fixed_g0_candidate_authority_v1(
        release_id="fixed-g0-accepted-candidates-v1",
        namespace=NAMESPACE,
        repository_root=Path("/fixture"),
        catalog_replay_receipt_identity=chain[
            "catalog_replay_receipt_identity"
        ],
        candidate_artifact_identities=identities,
        read_exact=read_exact or _read_exact(chain),
        git_head=_noop_head,
        git_blob=_git_blob(chain),
        git_status=_noop_status,
    )


def _rehash(value: dict[str, object], field: str) -> None:
    value[field] = source.canonical_sha256({
        key: item for key, item in value.items() if key != field
    })


def _coherent_artifact_replacement(
    bundle_value: Mapping[str, object],
    *,
    rows: list[dict[str, object]],
    generation: str,
    chain: Mapping[str, Any],
) -> dict[str, object]:
    bundle = deepcopy(bundle_value)
    release = bundle["candidate_release"]
    old_entry = release["entries"][0]
    artifact = source.build_accepted_candidate_artifact_v1(
        source_task_ordinal=0,
        rows=rows,
    )
    identity = _body_identity(
        artifact,
        uri=old_entry["candidate_artifact_identity"]["uri"],
        generation=generation,
    )
    chain["store"][(identity["uri"], identity["generation"])] = (
        source.canonical_json_bytes(artifact)
    )
    entry_body = {
        "source_task_ordinal": 0,
        "task_id": artifact["task_id"],
        "slate": artifact["slate"],
        "catalog_identity": old_entry["catalog_identity"],
        "candidate_artifact": artifact,
        "candidate_artifact_identity": identity,
        "candidate_count": artifact["candidate_count"],
        "ordered_candidate_ids_sha256": artifact["ordered_candidate_ids_sha256"],
    }
    new_entry = {
        **entry_body,
        "accepted_candidate_release_entry_sha256": source.canonical_sha256(
            entry_body
        ),
    }
    entries = [new_entry, *release["entries"][1:]]
    release = source.build_accepted_candidate_release_v1(
        release_id=release["release_id"],
        namespace=release["namespace"],
        source_candidate_panel_identity=release["source_candidate_panel_identity"],
        entries=entries,
    )
    bundle["candidate_release"] = release
    bundle["candidate_artifacts"][0] = artifact
    bundle["candidate_artifact_manifest_sha256"] = source.canonical_sha256(
        bundle["candidate_artifacts"]
    )
    old_sidecar = bundle["lineage_sidecars"][0]
    old_lineage = {
        row["candidate_id"]: row for row in old_sidecar["candidates"]
    }
    fabricated_lineage: list[dict[str, object]] = []
    for row in artifact["rows"]:
        candidate_id = row["candidate_id"]
        if candidate_id in old_lineage:
            lineage = deepcopy(old_lineage[candidate_id])
            lineage["player_ids"] = row["player_ids"]
            lineage["roster_sha256"] = source.canonical_sha256(row["player_ids"])
        else:
            lineage = {
                "candidate_id": candidate_id,
                "player_ids": row["player_ids"],
                "roster_sha256": source.canonical_sha256(row["player_ids"]),
                "source_arm_ordinals": [0],
                "source_arms": [batch.PARAMETER_SET_ORDER[0]],
                "occurrence_count": 1,
                "occurrences": [{
                    "arm_ordinal": 0,
                    "parameter_set_id": batch.PARAMETER_SET_ORDER[0],
                    "visit_ordinal": 999_999,
                }],
            }
        fabricated_lineage.append(lineage)
    sidecar = deepcopy(old_sidecar)
    old_visit_count = int(sidecar["visit_occurrence_count"])
    sidecar["visit_occurrence_count"] = sum(
        int(row["occurrence_count"]) for row in fabricated_lineage
    )
    sidecar["candidate_count"] = len(fabricated_lineage)
    sidecar["candidates"] = fabricated_lineage
    sidecar["candidate_lineage_manifest_sha256"] = source.canonical_sha256(
        fabricated_lineage
    )
    _rehash(sidecar, "candidate_lineage_sidecar_sha256")
    bundle["lineage_sidecars"][0] = sidecar
    bundle["lineage_sidecar_manifest_sha256"] = source.canonical_sha256(
        bundle["lineage_sidecars"]
    )
    receipt = bundle["slate_derivation_receipts"][0]
    prior_count = int(receipt["candidate_count"])
    receipt["candidate_artifact_identity"] = identity
    receipt["candidate_artifact_sha256"] = artifact["candidate_artifact_sha256"]
    receipt["candidate_count"] = artifact["candidate_count"]
    receipt["ordered_candidate_ids_sha256"] = artifact[
        "ordered_candidate_ids_sha256"
    ]
    receipt["candidate_row_manifest_sha256"] = artifact[
        "candidate_row_manifest_sha256"
    ]
    receipt["visit_occurrence_count"] = sidecar["visit_occurrence_count"]
    receipt["lineage_sidecar_sha256"] = sidecar[
        "candidate_lineage_sidecar_sha256"
    ]
    receipt["candidate_lineage_manifest_sha256"] = sidecar[
        "candidate_lineage_manifest_sha256"
    ]
    _rehash(receipt, "slate_derivation_sha256")
    bundle["slate_derivation_manifest_sha256"] = source.canonical_sha256(
        bundle["slate_derivation_receipts"]
    )
    panel = bundle["panel_derivation_receipt"]
    panel["candidate_release_sha256"] = release[
        "accepted_candidate_release_sha256"
    ]
    panel["candidate_release_body_sha256"] = source.canonical_sha256(release)
    panel["total_candidate_count"] = (
        int(panel["total_candidate_count"])
        - prior_count
        + int(artifact["candidate_count"])
    )
    panel["total_visit_occurrence_count"] = (
        int(panel["total_visit_occurrence_count"])
        - old_visit_count
        + int(sidecar["visit_occurrence_count"])
    )
    panel["slates"][0]["slate_derivation_sha256"] = receipt[
        "slate_derivation_sha256"
    ]
    panel["slates"][0]["candidate_artifact_identity"] = identity
    panel["slates"][0]["candidate_count"] = artifact["candidate_count"]
    panel["slates"][0]["ordered_candidate_ids_sha256"] = artifact[
        "ordered_candidate_ids_sha256"
    ]
    panel["slates"][0]["lineage_sidecar_sha256"] = sidecar[
        "candidate_lineage_sidecar_sha256"
    ]
    panel["slate_derivation_manifest_sha256"] = source.canonical_sha256(
        bundle["slate_derivation_receipts"]
    )
    panel["candidate_artifact_identity_manifest_sha256"] = source.canonical_sha256([
        entry["candidate_artifact_identity"] for entry in release["entries"]
    ])
    panel["lineage_sidecar_manifest_sha256"] = source.canonical_sha256(
        bundle["lineage_sidecars"]
    )
    _rehash(panel, "panel_derivation_sha256")
    _rehash(bundle, "candidate_authority_bundle_sha256")
    return bundle


def _validate(bundle: Mapping[str, object], chain: Mapping[str, Any]) -> object:
    return authority.validate_fixed_g0_candidate_authority_v1(
        bundle,
        repository_root=Path("/fixture"),
        catalog_replay_receipt_identity=chain[
            "catalog_replay_receipt_identity"
        ],
        read_exact=_read_exact(chain),
        git_head=_noop_head,
        git_blob=_git_blob(chain),
        git_status=_noop_status,
    )


def test_full_54_release_preserves_full_union_and_exact_lineage(
    chain: dict[str, Any],
) -> None:
    bundle = _build(chain)
    assert bundle["task_count"] == 54
    assert len(bundle["candidate_release"]["entries"]) == 54
    assert len(bundle["slate_derivation_receipts"]) == 54
    assert chain["result_body_read_count"]() == 54 * 7 * 2
    assert all(
        chain["read_counts"][(
            row["acceptance_identity"]["uri"],
            row["acceptance_identity"]["generation"],
        )] == 2
        for row in chain["task_rows"]
    )
    assert all(
        chain["read_counts"][(
            row["carrier_identity"]["uri"],
            row["carrier_identity"]["generation"],
        )] == 2
        for row in chain["task_rows"]
    )
    assert all(
        chain["read_counts"][(
            row["world_schedule_identity"]["uri"],
            row["world_schedule_identity"]["generation"],
        )] == 2
        for row in chain["task_rows"]
    )

    artifact = bundle["candidate_artifacts"][0]
    candidate_ids = [row["candidate_id"] for row in artifact["rows"]]
    assert candidate_ids == sorted(candidate_ids)
    assert len(candidate_ids) == 87
    slate = catalog_v1.expected_slate_for_source_task(0)
    nonselected_id = v12_import.canonical_lineup_id(slate, chain["lineups"][80])
    arm6_only_id = v12_import.canonical_lineup_id(slate, chain["lineups"][86])
    assert nonselected_id in candidate_ids
    assert arm6_only_id in candidate_ids
    lineage = {
        row["candidate_id"]: row
        for row in bundle["lineage_sidecars"][0]["candidates"]
    }
    assert lineage[arm6_only_id]["source_arm_ordinals"] == [6]
    assert lineage[arm6_only_id]["origin_blocks"] == ["R4"]
    assert lineage[arm6_only_id]["occurrence_counts_by_block"] == {
        block: 1 if block == "R4" else 0 for block in rw.WORLD_BLOCKS
    }
    assert lineage[arm6_only_id]["source_arms_by_block"]["R4"] == [
        batch.PARAMETER_SET_ORDER[6]
    ]
    assert lineage[arm6_only_id]["occurrences"] == [{
        "arm_ordinal": 6,
        "parameter_set_id": batch.PARAMETER_SET_ORDER[6],
        "visit_ordinal": 80,
        "block_id": "R4",
        "objective_world_index": 12,
    }]
    duplicate_id = v12_import.canonical_lineup_id(slate, chain["lineups"][0])
    assert lineage[duplicate_id]["occurrence_count"] == 14
    assert _validate(bundle, chain) == bundle
    assert chain["result_body_read_count"]() == 54 * 7 * 3
    assert all(
        chain["read_counts"][(
            row["world_schedule_identity"]["uri"],
            row["world_schedule_identity"]["generation"],
        )] == 3
        for row in chain["task_rows"]
    )
    assert all(
        chain["read_counts"][(
            entry["candidate_artifact_identity"]["uri"],
            entry["candidate_artifact_identity"]["generation"],
        )] == 3
        for entry in bundle["candidate_release"]["entries"]
    )


def test_build_exact_reads_every_create_once_candidate_generation(
    chain: dict[str, Any],
) -> None:
    material = _material(chain)
    identities = _publish_candidate_artifacts(chain, material)
    bundle = _build_from_identities(chain, identities)
    assert bundle["task_count"] == source.TASK_COUNT
    assert all(
        chain["read_counts"][(identity["uri"], identity["generation"])] == 1
        for identity in identities
    )


def test_build_rejects_absent_create_once_candidate_generation(
    chain: dict[str, Any],
) -> None:
    material = _material(chain)
    identities = _publish_candidate_artifacts(chain, material)
    missing = identities[17]
    del chain["store"][(missing["uri"], missing["generation"])]
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match=r"published candidate artifact\[17\] exact read failed",
    ):
        _build_from_identities(chain, identities)


def test_build_rejects_wrong_create_once_candidate_bytes(
    chain: dict[str, Any],
) -> None:
    material = _material(chain)
    identities = _publish_candidate_artifacts(chain, material)
    wrong = identities[23]
    chain["store"][(wrong["uri"], wrong["generation"])] = b"{}"
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match=r"published candidate artifact\[23\] exact content identity differs",
    ):
        _build_from_identities(chain, identities)


def test_validator_repeats_create_once_reads_and_rejects_equivocation(
    chain: dict[str, Any],
) -> None:
    bundle = _build(chain)
    target = bundle["candidate_release"]["entries"][0][
        "candidate_artifact_identity"
    ]
    target_key = (target["uri"], target["generation"])
    target_calls = 0
    stable_read = _read_exact(chain)

    def equivocate(identity: Mapping[str, object]) -> bytes:
        nonlocal target_calls
        key = (str(identity["uri"]), str(identity["generation"]))
        if key == target_key:
            target_calls += 1
            if target_calls == 2:
                return b"{}"
        return stable_read(identity)

    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match=r"published candidate artifact\[0\] exact content identity differs",
    ):
        authority.validate_fixed_g0_candidate_authority_v1(
            bundle,
            repository_root=Path("/fixture"),
            catalog_replay_receipt_identity=chain[
                "catalog_replay_receipt_identity"
            ],
            read_exact=equivocate,
            git_head=_noop_head,
            git_blob=_git_blob(chain),
            git_status=_noop_status,
        )
    assert target_calls == 2


def test_catalog_root_source_commit_is_bound_to_fixed_g0_git(
    chain: dict[str, Any],
) -> None:
    alternate = deepcopy(chain["catalog_replay_receipt"]["tracked_root_binding"])
    alternate["source_commit_sha"] = "9" * 40
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match="exact tracked G0 root",
    ):
        authority._validate_catalog_root(
            alternate,
            panel_identity=chain["panel_identity"],
            panel=chain["panel"],
            git_binding=chain["git_binding"],
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "completion-object",
        "completion-internal",
        "source-task",
        "source-internal",
        "task-hash",
        "batch-hash",
        "world-set",
        "world-map",
    ],
)
def test_result_task_source_binding_rejects_coherent_hash_splices(
    mutation: str,
    chain: dict[str, Any],
) -> None:
    task_row = chain["task_rows"][0]
    identity = task_row["result_identities"][0]
    body = json.loads(
        chain["store"][(identity["uri"], identity["generation"])].decode()
    )
    binding = body["task_source_binding"]
    if mutation == "completion-object":
        binding["artifact_source_authority_completion_object_sha256"] = _digest(
            "alternate-completion-object"
        )
    elif mutation == "completion-internal":
        binding["artifact_source_authority_completion_sha256"] = _digest(
            "alternate-completion-internal"
        )
    elif mutation == "source-task":
        binding["artifact_source_authority_task_sha256"] = _digest(
            "alternate-source-task"
        )
    elif mutation == "source-internal":
        binding["later_source_freeze_manifest_sha256"] = _digest(
            "alternate-source-internal"
        )
    elif mutation == "task-hash":
        binding["task_sha256"] = _digest("alternate-task")
    elif mutation == "batch-hash":
        binding["batch_manifest_sha256"] = _digest("alternate-batch")
    elif mutation == "world-set":
        binding["world_artifact_receipt_set_sha256"] = _digest(
            "alternate-world-set"
        )
    else:
        body["artifact_sha256_by_block"][rw.WORLD_BLOCKS[0]] = (
            _digest("alternate-world-object")
        )
    imported = v12_import.V12ImportedTask(
        carrier=task_row["carrier"],
        variant_results=(),
        compatibility_receipt={},
    )
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match="completion/source/internal/task hash chain differs",
    ):
        authority._validate_result_task_source_binding(
            source_task_ordinal=0,
            arm_ordinal=0,
            body=body,
            imported=imported,
            catalog_binding={
                "source_catalog_binding": chain["source_bindings"][0],
                "completion_binding": chain["completion_bindings"][0],
            },
            common_binding_sha256=None,
        )


@pytest.mark.parametrize(
    "manifest_field",
    [
        "source_catalog_binding_manifest_sha256",
        "completion_binding_manifest_sha256",
        "structural_catalog_manifest_sha256",
    ],
)
def test_terminal_catalog_release_rejects_coherently_rehashed_catalog_splice(
    manifest_field: str,
    chain: dict[str, Any],
) -> None:
    receipt = deepcopy(chain["catalog_replay_receipt"])
    receipt[manifest_field] = _digest(f"alternate:{manifest_field}")
    _rehash(receipt, "replay_receipt_sha256")
    identity = _body_identity(
        receipt,
        uri=chain["catalog_replay_receipt_identity"]["uri"],
        generation="5999",
    )
    chain["store"][(identity["uri"], identity["generation"])] = (
        source.canonical_json_bytes(receipt)
    )
    chain["catalog_replay_receipt_identity"] = identity
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match="catalog release lattice differs",
    ):
        _material(chain)


def test_terminal_catalog_final_lock_rejects_alternate_evidence_commit(
    chain: dict[str, Any],
) -> None:
    final_lock = json.loads(chain["final_lock_raw"].decode())
    final_lock["evidence_source_commit_sha"] = "9" * 40
    _rehash(final_lock, "projection_successor_final_lock_sha256")
    chain["final_lock_raw"] = source.canonical_json_bytes(final_lock) + b"\n"
    chain["git_files"][(
        SOURCE_COMMIT,
        authority.catalog_successor.FINAL_LOCK_PATH,
    )] = chain["final_lock_raw"]
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match="successor authority replay failed",
    ):
        _material(chain)


def test_authoritative_replay_rejects_coherently_rehashed_legal_substitution(
    chain: dict[str, Any],
) -> None:
    bundle = _build(chain)
    rows = [
        {"candidate_id": row["candidate_id"], "player_ids": row["player_ids"]}
        for row in bundle["candidate_artifacts"][0]["rows"]
    ]
    slate = catalog_v1.expected_slate_for_source_task(0)
    replacement = chain["lineups"][100]
    rows[0] = {
        "candidate_id": v12_import.canonical_lineup_id(slate, replacement),
        "player_ids": replacement,
    }
    rows.sort(key=lambda row: str(row["candidate_id"]))
    tampered = _coherent_artifact_replacement(
        bundle, rows=rows, generation="90001", chain=chain
    )
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match="differs",
    ):
        _validate(tampered, chain)


@pytest.mark.parametrize("mutation", ["omission", "extra", "reorder"])
def test_authoritative_replay_rejects_coherently_rehashed_population_drift(
    mutation: str,
    chain: dict[str, Any],
) -> None:
    bundle = _build(chain)
    rows = [
        {"candidate_id": row["candidate_id"], "player_ids": row["player_ids"]}
        for row in bundle["candidate_artifacts"][0]["rows"]
    ]
    if mutation == "omission":
        rows = rows[:-1]
    elif mutation == "extra":
        slate = catalog_v1.expected_slate_for_source_task(0)
        extra = chain["lineups"][101]
        rows.append({
            "candidate_id": v12_import.canonical_lineup_id(slate, extra),
            "player_ids": extra,
        })
        rows.sort(key=lambda row: str(row["candidate_id"]))
    else:
        rows[0], rows[1] = rows[1], rows[0]
    tampered = _coherent_artifact_replacement(
        bundle,
        rows=rows,
        generation={"omission": "90002", "extra": "90003", "reorder": "90004"}[
            mutation
        ],
        chain=chain,
    )
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match="differs",
    ):
        _validate(tampered, chain)


def test_panel_to_carrier_arm_splice_fails_closed(chain: dict[str, Any]) -> None:
    chain["members"][0]["arms"][6]["result_identity"] = deepcopy(
        chain["members"][1]["arms"][6]["result_identity"]
    )
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match="differs",
    ):
        _material(chain)


def test_missing_catalog_player_fails_whole_slate_without_filtering(
    chain: dict[str, Any],
) -> None:
    invalid = sorted([*chain["lineups"][0][:-1], "zz-not-in-catalog"])
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match="outside the exact structural catalog",
    ):
        authority._validate_roster_against_catalog(
            invalid,
            catalog={"players": chain["players"]},
            label="fixture roster",
        )


def test_invalid_dk_shape_fails_whole_slate_without_filtering(
    chain: dict[str, Any],
) -> None:
    original = list(chain["lineups"][0])
    invalid = sorted([
        *(player_id for player_id in original if not player_id.startswith("dst-")),
        "qb-02",
    ])
    assert len(invalid) == 9 and len(set(invalid)) == 9
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match="DraftKings classic roster/salary law",
    ):
        authority._validate_roster_against_catalog(
            invalid,
            catalog={"players": chain["players"]},
            label="fixture roster",
        )


def test_full_slate_derivation_rejects_one_bad_accepted_roster_without_filtering(
    chain: dict[str, Any],
) -> None:
    member = chain["members"][0]
    imported = v12_import.reopen_v12_task(
        acceptance_receipt_identity=member["task_acceptance_identity"],
        carrier_identity=member["carrier_identity"],
        read_exact=_read_exact(chain),
        require_authoritative=True,
    )
    variants = [deepcopy(value) for value in imported.variant_results]
    variants[0]["visit_rosters"][0] = sorted([
        *chain["lineups"][0][:-1],
        "zz-not-in-catalog",
    ])
    variants[0]["unique_rosters"][0] = variants[0]["visit_rosters"][0]
    corrupted = v12_import.V12ImportedTask(
        carrier=imported.carrier,
        variant_results=tuple(variants),
        compatibility_receipt=imported.compatibility_receipt,
    )
    catalog_binding = {
        "source_catalog_binding": chain["source_bindings"][0],
        "completion_binding": chain["completion_bindings"][0],
        "catalog_identity": chain["catalog_release_identity"],
    }
    schedule_identity, schedule_row, visit_schedule = (
        authority._reopen_task_world_schedule(
            source_task_ordinal=0,
            imported=corrupted,
            read_exact=_read_exact(chain),
        )
    )
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match="unique book differs|outside the exact structural catalog",
    ):
        authority._derive_slate_material(
            source_task_ordinal=0,
            member=member,
            catalog=chain["catalogs"][0],
            catalog_binding=catalog_binding,
            imported=corrupted,
            world_schedule_identity=schedule_identity,
            world_schedule_row=schedule_row,
            visit_schedule=visit_schedule,
        )


def test_validator_requires_the_external_exact_catalog_replay_receipt_identity(
    chain: dict[str, Any],
) -> None:
    bundle = _build(chain)
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match="expected catalog replay receipt",
    ):
        authority.validate_fixed_g0_candidate_authority_v1(
            bundle,
            repository_root=Path("/fixture"),
            catalog_replay_receipt_identity=_opaque_identity(
                "coherent-alternate-catalog-receipt"
            ),
            read_exact=_read_exact(chain),
            git_head=_noop_head,
            git_blob=_git_blob(chain),
            git_status=_noop_status,
        )


def test_exact_world_schedule_row_tamper_fails_before_lineage_derivation(
    chain: dict[str, Any],
) -> None:
    member = chain["members"][0]
    imported = v12_import.reopen_v12_task(
        acceptance_receipt_identity=member["task_acceptance_identity"],
        carrier_identity=member["carrier_identity"],
        read_exact=_read_exact(chain),
        require_authoritative=True,
    )
    changed = deepcopy(chain["task_rows"][0]["world_schedule"])
    changed["slates"][0]["blocks"][0]["world_indices"][0:2] = [1, 0]
    changed_raw = source.canonical_json_bytes(changed)
    changed_identity = {
        "uri": "gs://fixture/schedules/tampered/world-schedule.json",
        "generation": "99001",
        "sha256": sha256(changed_raw).hexdigest(),
        "bytes": len(changed_raw),
    }
    changed_carrier = deepcopy(imported.carrier)
    changed_carrier["world_schedule"] = changed_identity
    changed_import = v12_import.V12ImportedTask(
        carrier=changed_carrier,
        variant_results=imported.variant_results,
        compatibility_receipt=imported.compatibility_receipt,
    )
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match="self-hash differs",
    ):
        authority._reopen_task_world_schedule(
            source_task_ordinal=0,
            imported=changed_import,
            read_exact=lambda _identity: changed_raw,
        )


def test_missing_carrier_bound_world_schedule_fails_closed(
    chain: dict[str, Any],
) -> None:
    member = chain["members"][0]
    imported = v12_import.reopen_v12_task(
        acceptance_receipt_identity=member["task_acceptance_identity"],
        carrier_identity=member["carrier_identity"],
        read_exact=_read_exact(chain),
        require_authoritative=True,
    )
    changed_carrier = deepcopy(imported.carrier)
    del changed_carrier["world_schedule"]
    changed_import = v12_import.V12ImportedTask(
        carrier=changed_carrier,
        variant_results=imported.variant_results,
        compatibility_receipt=imported.compatibility_receipt,
    )
    with pytest.raises(
        authority.CorpusR6FixedG0CandidateAuthorityV1Error,
        match="world schedule identity",
    ):
        authority._reopen_task_world_schedule(
            source_task_ordinal=0,
            imported=changed_import,
            read_exact=_read_exact(chain),
        )
