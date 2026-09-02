from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.inference import prelock_candidate_lineage_v1 as lineage
from nfl_dfs.research.prelock_lineage_graph_v2 import (
    AUTHORITY_FLAGS,
    PrelockLineageGraphV2Error,
    project_prelock_lineage_summary_v2,
)

PROJECTION_CREATED_AT = "2026-09-13T16:31:00Z"


def _roster() -> dict[str, object]:
    return {
        "slate_id": "2026-w01-main",
        "internal_player_id_namespace": "production-lineup-id-v1",
        "draftable_player_id_namespace": "draftkings-draftable-id-v1",
        "player_id_bridge": [
            {
                "internal_player_id": f"private-internal-{index}",
                "draftable_player_id": f"private-draftable-{index}",
            }
            for index in range(9)
        ],
        "salary_catalog_sha256": "b" * 64,
        "legacy_lineup_ids": ["private-legacy-lineup"],
    }


def _roster_id(roster: dict[str, object]) -> str:
    internal_ids = sorted(
        pair["internal_player_id"] for pair in roster["player_id_bridge"]
    )
    return "roster-v1-" + lineage.canonical_sha256(
        {
            "schema_version": lineage.ROSTER_IDENTITY_SCHEMA,
            "slate_id": roster["slate_id"],
            "internal_player_id_namespace": roster["internal_player_id_namespace"],
            "internal_player_ids": internal_ids,
        }
    )


def _sidecar() -> dict[str, object]:
    roster = _roster()
    roster_id = _roster_id(roster)
    requests = [
        ("private-request-produced-a", "leverage", "PRODUCED"),
        ("private-request-produced-b", "boom", "PRODUCED"),
        ("private-request-infeasible", "role", "INFEASIBLE"),
        ("private-request-error", "dark", "SOLVER_ERROR"),
        ("private-request-exhausted", "dark", "EXHAUSTED_NOT_ATTEMPTED"),
    ]
    return lineage.build_prelock_candidate_lineage_v1(
        run_header={
            "run_id": "summary-run-001",
            "run_type": "shadow-capture",
            "season": 2026,
            "week": 1,
            "slate_id": "2026-w01-main",
            "draft_group_id": 12345,
            "contest_id": "contest-001",
            "slate_lock_at_utc": "2026-09-13T17:00:00Z",
            "frozen_at_utc": "2026-09-13T16:30:00Z",
            "entry_budget": 1,
            "policy_id": "week1-policy-v1",
            "selector_ids": ["coverage-194-v1"],
            "effective_candidate_stage_id": "effective-candidates",
            "paid_strategy_id": "coverage-194-v1",
            "code_sha256": "a" * 64,
            "input_source_identities": [
                {
                    "role": "salary-catalog",
                    "uri": "gs://immutable-bucket/salary.csv",
                    "generation": "123456789",
                    "sha256": "c" * 64,
                    "bytes": 100,
                }
            ],
        },
        roster_identities=[roster],
        proposal_requests=[
            {
                "request_id": request_id,
                "request_ordinal": ordinal,
                "source_label": "seed-a",
                "family": family,
                "requested_ordinal": ordinal,
                "world_id": ordinal if status != "EXHAUSTED_NOT_ATTEMPTED" else None,
                "generator_config_sha256": "d" * 64,
                "terminal_status": status,
            }
            for ordinal, (request_id, family, status) in enumerate(requests)
        ],
        solve_attempts=[
            {
                "attempt_id": "private-attempt-produced-a",
                "attempt_ordinal": 0,
                "request_id": "private-request-produced-a",
                "retry_ordinal": 0,
                "status": "PRODUCED",
                "roster_id": roster_id,
            },
            {
                "attempt_id": "private-attempt-produced-b",
                "attempt_ordinal": 1,
                "request_id": "private-request-produced-b",
                "retry_ordinal": 0,
                "status": "PRODUCED",
                "roster_id": roster_id,
            },
            {
                "attempt_id": "private-attempt-infeasible",
                "attempt_ordinal": 2,
                "request_id": "private-request-infeasible",
                "retry_ordinal": 0,
                "status": "INFEASIBLE",
                "roster_id": None,
            },
            {
                "attempt_id": "private-attempt-error",
                "attempt_ordinal": 3,
                "request_id": "private-request-error",
                "retry_ordinal": 0,
                "status": "SOLVER_ERROR",
                "roster_id": None,
            },
        ],
        generated_occurrences=[
            {
                "occurrence_id": "private-occurrence-a",
                "occurrence_ordinal": 0,
                "attempt_id": "private-attempt-produced-a",
                "request_id": "private-request-produced-a",
                "roster_id": roster_id,
            },
            {
                "occurrence_id": "private-occurrence-b",
                "occurrence_ordinal": 1,
                "attempt_id": "private-attempt-produced-b",
                "request_id": "private-request-produced-b",
                "roster_id": roster_id,
            },
        ],
        dedupe_decisions=[
            {
                "decision_id": "private-dedupe-a",
                "occurrence_id": "private-occurrence-a",
                "roster_id": roster_id,
                "disposition": "FIRST_SEEN",
                "duplicate_of_occurrence_id": None,
            },
            {
                "decision_id": "private-dedupe-b",
                "occurrence_id": "private-occurrence-b",
                "roster_id": roster_id,
                "disposition": "DUPLICATE_CROSS_FAMILY",
                "duplicate_of_occurrence_id": "private-occurrence-a",
            },
        ],
        admission_decisions=[
            {
                "decision_id": "private-admission-native",
                "stage_id": "native-pool",
                "stage_ordinal": 0,
                "candidate_instance_id": "private-candidate-native",
                "candidate_ordinal": 0,
                "roster_id": roster_id,
                "source_occurrence_ids": [
                    "private-occurrence-a",
                    "private-occurrence-b",
                ],
                "input_candidate_instance_ids": [],
                "admission_preset_id": "native-admission-v1",
                "disposition": "RETAINED",
                "reason": "RETAINED_NATIVE",
            },
            {
                "decision_id": "private-admission-effective",
                "stage_id": "effective-candidates",
                "stage_ordinal": 1,
                "candidate_instance_id": "private-candidate-effective",
                "candidate_ordinal": 0,
                "roster_id": roster_id,
                "source_occurrence_ids": [],
                "input_candidate_instance_ids": ["private-candidate-native"],
                "admission_preset_id": "effective-stage-v1",
                "disposition": "RETAINED",
                "reason": "TRANSFORM_RETAINED",
            },
        ],
        strategy_decisions=[
            {
                "decision_id": "private-strategy-decision",
                "strategy_id": "coverage-194-v1",
                "candidate_instance_id": "private-candidate-effective",
                "roster_id": roster_id,
                "candidate_ordinal": 0,
                "eligibility": "ELIGIBLE",
                "eligibility_reason": "EFFECTIVE_CANDIDATE",
                "decision": "SELECTED",
                "decision_reason": "SELECTED_COVERAGE_PHASE",
                "selector_rank": 0,
                "selection_phase": "COVERAGE",
                "fresh_world_count": 2,
                "individual_clear_count": 3,
                "p_line": 0.75,
                "mean_simulated_total": 210.0,
                "tiebreak_values": [0.75, 210.0],
            }
        ],
        book_transitions=[
            {
                "transition_id": "private-book-transition",
                "strategy_id": "coverage-194-v1",
                "candidate_instance_id": "private-candidate-effective",
                "roster_id": roster_id,
                "selector_rank": 0,
                "postselector_rank": 0,
                "export_rank": 0,
                "disposition": "RETAINED",
                "reason": "RETAINED_POSTSELECTOR",
            }
        ],
        prepared_entries=[
            {
                "prepared_entry_id": "private-prepared-entry",
                "strategy_id": "coverage-194-v1",
                "candidate_instance_id": "private-candidate-effective",
                "roster_id": roster_id,
                "contest_id": "contest-001",
                "entry_id": "private-draftkings-entry",
                "entry_row_ordinal": 0,
                "export_rank": 0,
                "filled_csv_sha256": "e" * 64,
                "paid_export_receipt_sha256": "f" * 64,
                "status": "PREPARED_NOT_CONFIRMED",
            }
        ],
    )


def _identity(sidecar: dict[str, object]) -> dict[str, object]:
    raw = lineage.canonical_json_bytes(sidecar)
    return {
        "uri": "gs://immutable-bucket/prelock/summary-run-001.json",
        "generation": "987654321",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _project(sidecar: dict[str, object]):
    return project_prelock_lineage_summary_v2(
        sidecar=sidecar,
        sidecar_identity=_identity(sidecar),
        graph_release_id="prelock-summary-release-001",
        projection_created_at_utc=PROJECTION_CREATED_AT,
    )


def _metric_values(projection, parent_id: str) -> dict[str, int]:
    nodes = {row["node_id"]: row for row in projection.nodes}
    return {
        str(edge["properties"]["definition_id"]): int(
            nodes[edge["target_id"]]["properties"]["value"]
        )
        for edge in projection.relationships
        if edge["relationship"] == "HAS_METRIC" and edge["source_id"] == parent_id
    }


def test_summary_projects_only_existing_v2_aggregate_vocabulary() -> None:
    sidecar = _sidecar()
    projection = _project(sidecar)

    assert projection.governed_manifest["graph_schema_version"] == (
        "corpus-graph-vnext/v2"
    )
    assert projection.governed_manifest["authorized_outcome_release_id"] is None
    assert projection.governed_manifest["created_at_utc"] == PROJECTION_CREATED_AT
    assert projection.receipt["projection_created_at_utc"] == PROJECTION_CREATED_AT
    assert projection.receipt["aggregate_reconciliation_verified"] is True
    assert projection.receipt["authority_flags"] == AUTHORITY_FLAGS
    assert not any(AUTHORITY_FLAGS.values())
    assert projection.receipt["individual_candidate_row_count"] == 0
    assert projection.receipt["individual_roster_row_count"] == 0
    assert projection.receipt["individual_player_row_count"] == 0
    assert projection.receipt["outcome_namespace_row_count"] == 0

    kinds = Counter(row["kind"] for row in projection.nodes)
    assert not ({"Lineup", "PlayerSlate", "TeamSlate"} & set(kinds))
    assert kinds["SourceArtifact"] == 2
    assert kinds["CandidateSnapshot"] == 2
    assert kinds["SelectedBook"] == 1
    assert all(row["namespace"] != "realized" for row in projection.nodes)
    assert all(row["namespace"] != "realized" for row in projection.relationships)
    slate = next(row for row in projection.nodes if row["kind"] == "Slate")
    assert "slate_type" not in slate["properties"]

    release = next(row for row in projection.nodes if row["kind"] == "ScienceRelease")
    release_metrics = _metric_values(projection, release["node_id"])
    assert release_metrics["proposal_request_count"] == 5
    assert release_metrics["proposal_status_produced"] == 2
    assert release_metrics["proposal_status_infeasible"] == 1
    assert release_metrics["proposal_status_solver_error"] == 1
    assert release_metrics["proposal_status_exhausted_not_attempted"] == 1
    assert release_metrics["solve_attempt_count"] == 4
    assert release_metrics["dedupe_disposition_first_seen"] == 1
    assert release_metrics["dedupe_disposition_duplicate_cross_family"] == 1

    snapshots = sorted(
        (row for row in projection.nodes if row["kind"] == "CandidateSnapshot"),
        key=lambda row: row["properties"]["snapshot_id"],
    )
    by_stage = {row["properties"]["snapshot_id"]: row for row in snapshots}
    assert by_stage["native-pool"]["properties"]["lineup_count"] == 1
    assert (
        _metric_values(projection, by_stage["native-pool"]["node_id"])[
            "admission_input_count"
        ]
        == 2
    )
    assert by_stage["effective-candidates"]["properties"]["lineup_count"] == 1

    book = next(row for row in projection.nodes if row["kind"] == "SelectedBook")
    assert book["properties"]["selected_count"] == 1
    book_metrics = _metric_values(projection, book["node_id"])
    assert book_metrics["strategy_selected_count"] == 1
    assert book_metrics["final_book_count"] == 1
    assert book_metrics["prepared_entry_count"] == 1


def test_projection_is_deterministic_and_verifies_exact_sidecar_identity() -> None:
    sidecar = _sidecar()
    first = _project(sidecar)
    second = _project(deepcopy(sidecar))
    assert first == second

    identity = _identity(sidecar)
    identity["sha256"] = "0" * 64
    with pytest.raises(PrelockLineageGraphV2Error, match="content identity"):
        project_prelock_lineage_summary_v2(
            sidecar=sidecar,
            sidecar_identity=identity,
            graph_release_id="prelock-summary-release-001",
            projection_created_at_utc=PROJECTION_CREATED_AT,
        )


def test_outcome_bearing_input_is_rejected_before_projection() -> None:
    sidecar = _sidecar()
    sidecar["actual_score"] = 250.0
    with pytest.raises(PrelockLineageGraphV2Error, match="outcome-bearing"):
        project_prelock_lineage_summary_v2(
            sidecar=sidecar,
            sidecar_identity=_identity(sidecar),
            graph_release_id="prelock-summary-release-001",
            projection_created_at_utc=PROJECTION_CREATED_AT,
        )


def test_projection_never_leaks_detailed_candidate_or_player_identifiers() -> None:
    projection = _project(_sidecar())
    serialized = json.dumps(
        {
            "manifest": projection.governed_manifest,
            "nodes": projection.nodes,
            "relationships": projection.relationships,
            "load_plan": projection.load_plan,
            "receipt": projection.receipt,
        },
        sort_keys=True,
    )
    forbidden = {
        "private-internal-0",
        "private-draftable-0",
        "private-legacy-lineup",
        "private-request-produced-a",
        "private-attempt-produced-a",
        "private-occurrence-a",
        "private-dedupe-a",
        "private-admission-native",
        "private-candidate-native",
        "private-candidate-effective",
        "private-strategy-decision",
        "private-book-transition",
        "private-prepared-entry",
        "private-draftkings-entry",
        _roster_id(_roster()),
    }
    assert all(identifier not in serialized for identifier in forbidden)


def test_invalid_sidecar_reconciliation_cannot_be_summarized() -> None:
    sidecar = _sidecar()
    sidecar["counts"]["prepared_entry_count"] = 99
    sidecar["sidecar_sha256"] = lineage.canonical_sha256(
        {key: value for key, value in sidecar.items() if key != "sidecar_sha256"}
    )
    with pytest.raises(PrelockLineageGraphV2Error, match="do not reconcile"):
        project_prelock_lineage_summary_v2(
            sidecar=sidecar,
            sidecar_identity=_identity(sidecar),
            graph_release_id="prelock-summary-release-001",
            projection_created_at_utc=PROJECTION_CREATED_AT,
        )


def test_existing_v2_sourceartifact_bound_fails_closed_without_schema_change() -> None:
    sidecar = _sidecar()
    source = sidecar["run_header"]["input_source_identities"][0]
    source["uri"] = "gs://immutable-bucket/" + "x" * 520
    sidecar["run_header"]["record_sha256"] = lineage.canonical_sha256(
        {
            key: value
            for key, value in sidecar["run_header"].items()
            if key != "record_sha256"
        }
    )
    sidecar["sidecar_sha256"] = lineage.canonical_sha256(
        {key: value for key, value in sidecar.items() if key != "sidecar_sha256"}
    )
    with pytest.raises(
        PrelockLineageGraphV2Error,
        match="cannot represent a summary node without schema expansion",
    ):
        project_prelock_lineage_summary_v2(
            sidecar=sidecar,
            sidecar_identity=_identity(sidecar),
            graph_release_id="prelock-summary-release-001",
            projection_created_at_utc=PROJECTION_CREATED_AT,
        )


def test_projection_time_cannot_backdate_the_graph_manifest() -> None:
    sidecar = _sidecar()
    with pytest.raises(PrelockLineageGraphV2Error, match="precedes the sidecar freeze"):
        project_prelock_lineage_summary_v2(
            sidecar=sidecar,
            sidecar_identity=_identity(sidecar),
            graph_release_id="prelock-summary-release-001",
            projection_created_at_utc="2026-09-13T16:29:59Z",
        )


def test_exported_authority_flags_cannot_be_mutated() -> None:
    with pytest.raises(TypeError):
        AUTHORITY_FLAGS["decision_authority"] = True  # type: ignore[index]
