from __future__ import annotations

from copy import deepcopy

import pytest

from nfl_dfs.inference.prelock_candidate_lineage_v1 import (
    CANDIDATE_UNIVERSE_SCOPE,
    ROSTER_IDENTITY_SCHEMA,
    PrelockCandidateLineageError,
    assert_outcome_free,
    build_prelock_candidate_lineage_v1,
    canonical_sha256,
    validate_prelock_candidate_lineage_v1,
)

SHA = "a" * 64


def _roster(offset: int) -> dict[str, object]:
    return {
        "slate_id": "2026-w01-main",
        "internal_player_id_namespace": "production-lineup-id-v1",
        "draftable_player_id_namespace": "draftkings-draftable-id-v1",
        "player_id_bridge": [
            {
                "internal_player_id": f"internal-{offset + index:03d}",
                "draftable_player_id": f"draftable-{offset + index:03d}",
            }
            for index in range(9)
        ],
        "salary_catalog_sha256": "b" * 64,
        "legacy_lineup_ids": [],
    }


def _roster_id(raw: dict[str, object]) -> str:
    internal_ids = sorted(
        pair["internal_player_id"] for pair in raw["player_id_bridge"]
    )
    return "roster-v1-" + canonical_sha256(
        {
            "schema_version": ROSTER_IDENTITY_SCHEMA,
            "slate_id": raw["slate_id"],
            "internal_player_id_namespace": raw["internal_player_id_namespace"],
            "internal_player_ids": internal_ids,
        }
    )


def _fixture() -> dict[str, object]:
    roster_a = _roster(1)
    roster_b = _roster(101)
    roster_a_id = _roster_id(roster_a)
    roster_b_id = _roster_id(roster_b)
    strategy_id = "coverage-194-v1"
    return {
        "run_header": {
            "run_id": "lineage-run-001",
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
            "selector_ids": [strategy_id],
            "effective_candidate_stage_id": "effective-candidates",
            "paid_strategy_id": strategy_id,
            "code_sha256": SHA,
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
        "roster_identities": [roster_a, roster_b],
        "proposal_requests": [
            {
                "request_id": "request-0",
                "request_ordinal": 0,
                "source_label": "seed-a",
                "family": "leverage",
                "requested_ordinal": 0,
                "world_id": 0,
                "generator_config_sha256": "d" * 64,
                "terminal_status": "PRODUCED",
            },
            {
                "request_id": "request-1",
                "request_ordinal": 1,
                "source_label": "seed-a",
                "family": "boom",
                "requested_ordinal": 0,
                "world_id": 1,
                "generator_config_sha256": "d" * 64,
                "terminal_status": "PRODUCED",
            },
            {
                "request_id": "request-2",
                "request_ordinal": 2,
                "source_label": "seed-a",
                "family": "role",
                "requested_ordinal": 0,
                "world_id": 2,
                "generator_config_sha256": "d" * 64,
                "terminal_status": "SOLVER_ERROR",
            },
            {
                "request_id": "request-3",
                "request_ordinal": 3,
                "source_label": "seed-a",
                "family": "boom",
                "requested_ordinal": 1,
                "world_id": 3,
                "generator_config_sha256": "d" * 64,
                "terminal_status": "PRODUCED",
            },
            {
                "request_id": "request-4",
                "request_ordinal": 4,
                "source_label": "seed-a",
                "family": "dark",
                "requested_ordinal": 0,
                "world_id": None,
                "generator_config_sha256": "d" * 64,
                "terminal_status": "EXHAUSTED_NOT_ATTEMPTED",
            },
        ],
        "solve_attempts": [
            {
                "attempt_id": "attempt-0",
                "attempt_ordinal": 0,
                "request_id": "request-0",
                "retry_ordinal": 0,
                "status": "PRODUCED",
                "roster_id": roster_a_id,
            },
            {
                "attempt_id": "attempt-1",
                "attempt_ordinal": 1,
                "request_id": "request-1",
                "retry_ordinal": 0,
                "status": "PRODUCED",
                "roster_id": roster_a_id,
            },
            {
                "attempt_id": "attempt-2",
                "attempt_ordinal": 2,
                "request_id": "request-2",
                "retry_ordinal": 0,
                "status": "SOLVER_ERROR",
                "roster_id": None,
            },
            {
                "attempt_id": "attempt-3",
                "attempt_ordinal": 3,
                "request_id": "request-3",
                "retry_ordinal": 0,
                "status": "SOLVER_ERROR",
                "roster_id": None,
            },
            {
                "attempt_id": "attempt-4",
                "attempt_ordinal": 4,
                "request_id": "request-3",
                "retry_ordinal": 1,
                "status": "PRODUCED",
                "roster_id": roster_b_id,
            },
        ],
        "generated_occurrences": [
            {
                "occurrence_id": "occurrence-0",
                "occurrence_ordinal": 0,
                "attempt_id": "attempt-0",
                "request_id": "request-0",
                "roster_id": roster_a_id,
            },
            {
                "occurrence_id": "occurrence-1",
                "occurrence_ordinal": 1,
                "attempt_id": "attempt-1",
                "request_id": "request-1",
                "roster_id": roster_a_id,
            },
            {
                "occurrence_id": "occurrence-2",
                "occurrence_ordinal": 2,
                "attempt_id": "attempt-4",
                "request_id": "request-3",
                "roster_id": roster_b_id,
            },
        ],
        "dedupe_decisions": [
            {
                "decision_id": "dedupe-0",
                "occurrence_id": "occurrence-0",
                "roster_id": roster_a_id,
                "disposition": "FIRST_SEEN",
                "duplicate_of_occurrence_id": None,
            },
            {
                "decision_id": "dedupe-1",
                "occurrence_id": "occurrence-1",
                "roster_id": roster_a_id,
                "disposition": "DUPLICATE_CROSS_FAMILY",
                "duplicate_of_occurrence_id": "occurrence-0",
            },
            {
                "decision_id": "dedupe-2",
                "occurrence_id": "occurrence-2",
                "roster_id": roster_b_id,
                "disposition": "FIRST_SEEN",
                "duplicate_of_occurrence_id": None,
            },
        ],
        "admission_decisions": [
            {
                "decision_id": "admission-native-0",
                "stage_id": "native-pool",
                "stage_ordinal": 0,
                "candidate_instance_id": "candidate-native-0",
                "candidate_ordinal": 0,
                "roster_id": roster_a_id,
                "source_occurrence_ids": ["occurrence-0", "occurrence-1"],
                "input_candidate_instance_ids": [],
                "admission_preset_id": "native-admission-v1",
                "disposition": "RETAINED",
                "reason": "RETAINED_NATIVE",
            },
            {
                "decision_id": "admission-native-1",
                "stage_id": "native-pool",
                "stage_ordinal": 0,
                "candidate_instance_id": "candidate-native-1",
                "candidate_ordinal": 1,
                "roster_id": roster_b_id,
                "source_occurrence_ids": ["occurrence-2"],
                "input_candidate_instance_ids": [],
                "admission_preset_id": "native-admission-v1",
                "disposition": "RETAINED",
                "reason": "RETAINED_NATIVE",
            },
            {
                "decision_id": "admission-effective-0",
                "stage_id": "effective-candidates",
                "stage_ordinal": 1,
                "candidate_instance_id": "candidate-effective-0",
                "candidate_ordinal": 0,
                "roster_id": roster_a_id,
                "source_occurrence_ids": [],
                "input_candidate_instance_ids": ["candidate-native-0"],
                "admission_preset_id": "effective-stage-v1",
                "disposition": "RETAINED",
                "reason": "TRANSFORM_RETAINED",
            },
            {
                "decision_id": "admission-effective-1",
                "stage_id": "effective-candidates",
                "stage_ordinal": 1,
                "candidate_instance_id": "candidate-effective-1",
                "candidate_ordinal": 1,
                "roster_id": roster_b_id,
                "source_occurrence_ids": [],
                "input_candidate_instance_ids": ["candidate-native-1"],
                "admission_preset_id": "effective-stage-v1",
                "disposition": "RETAINED",
                "reason": "TRANSFORM_RETAINED",
            },
        ],
        "strategy_decisions": [
            {
                "decision_id": "strategy-0",
                "strategy_id": strategy_id,
                "candidate_instance_id": "candidate-effective-0",
                "roster_id": roster_a_id,
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
            },
            {
                "decision_id": "strategy-1",
                "strategy_id": strategy_id,
                "candidate_instance_id": "candidate-effective-1",
                "roster_id": roster_b_id,
                "candidate_ordinal": 1,
                "eligibility": "ELIGIBLE",
                "eligibility_reason": "EFFECTIVE_CANDIDATE",
                "decision": "NOT_SELECTED",
                "decision_reason": "NOT_SELECTED_BOOK_FULL",
                "selector_rank": None,
                "selection_phase": "TERMINAL",
                "fresh_world_count": 0,
                "individual_clear_count": 2,
                "p_line": 0.5,
                "mean_simulated_total": 190.0,
                "tiebreak_values": [0.5, 190.0],
            },
        ],
        "book_transitions": [
            {
                "transition_id": "book-0",
                "strategy_id": strategy_id,
                "candidate_instance_id": "candidate-effective-0",
                "roster_id": roster_a_id,
                "selector_rank": 0,
                "postselector_rank": 0,
                "export_rank": 0,
                "disposition": "RETAINED",
                "reason": "RETAINED_POSTSELECTOR",
            }
        ],
        "prepared_entries": [
            {
                "prepared_entry_id": "prepared-0",
                "strategy_id": strategy_id,
                "candidate_instance_id": "candidate-effective-0",
                "roster_id": roster_a_id,
                "contest_id": "contest-001",
                "entry_id": "draftkings-entry-001",
                "entry_row_ordinal": 0,
                "export_rank": 0,
                "filled_csv_sha256": "e" * 64,
                "paid_export_receipt_sha256": "f" * 64,
                "status": "PREPARED_NOT_CONFIRMED",
            }
        ],
    }


def _build(raw: dict[str, object]) -> dict[str, object]:
    return build_prelock_candidate_lineage_v1(**raw)


def _k2_fixture() -> dict[str, object]:
    raw = _fixture()
    raw["run_header"]["entry_budget"] = 2
    raw["strategy_decisions"][1].update(
        {
            "decision": "SELECTED",
            "decision_reason": "SELECTED_SATURATION_FILL",
            "selector_rank": 1,
            "selection_phase": "SATURATION_FILL",
        }
    )
    raw["book_transitions"].append(
        {
            "transition_id": "book-1",
            "strategy_id": "coverage-194-v1",
            "candidate_instance_id": "candidate-effective-1",
            "roster_id": _roster_id(raw["roster_identities"][1]),
            "selector_rank": 1,
            "postselector_rank": 1,
            "export_rank": 1,
            "disposition": "RETAINED",
            "reason": "RETAINED_POSTSELECTOR",
        }
    )
    raw["prepared_entries"].append(
        {
            "prepared_entry_id": "prepared-1",
            "strategy_id": "coverage-194-v1",
            "candidate_instance_id": "candidate-effective-1",
            "roster_id": _roster_id(raw["roster_identities"][1]),
            "contest_id": "contest-001",
            "entry_id": "draftkings-entry-002",
            "entry_row_ordinal": 1,
            "export_rank": 1,
            "filled_csv_sha256": "e" * 64,
            "paid_export_receipt_sha256": "f" * 64,
            "status": "PREPARED_NOT_CONFIRMED",
        }
    )
    return raw


def test_full_prelock_lifecycle_reconciles_without_decision_authority() -> None:
    sidecar = _build(_fixture())

    assert sidecar["candidate_universe_scope"] == CANDIDATE_UNIVERSE_SCOPE
    assert sidecar["authority"] == {
        "decision_authority": False,
        "graph_decision_authority": False,
        "outcome_authority": False,
        "promotion_authority": False,
        "scoring_authority": False,
    }
    assert sidecar["uses_realized_outcomes"] is False
    assert sidecar["post_lock_data_read"] is False
    assert sidecar["counts"] == {
        "proposal_request_count": 5,
        "solve_attempt_count": 5,
        "generated_occurrence_count": 3,
        "unique_generated_roster_count": 2,
        "dedupe_decision_count": 3,
        "admission_decision_count": 4,
        "effective_candidate_count": 2,
        "strategy_decision_count": 2,
        "raw_selected_count": 1,
        "final_book_lineup_count": 1,
        "prepared_entry_count": 1,
    }
    assert validate_prelock_candidate_lineage_v1(sidecar) == sidecar
    assert sidecar["dedupe_decisions"][1]["disposition"] == ("DUPLICATE_CROSS_FAMILY")


def test_input_order_is_canonical_and_hash_tampering_fails_closed() -> None:
    raw = _fixture()
    expected = _build(raw)
    reordered = deepcopy(raw)
    for field in (
        "roster_identities",
        "proposal_requests",
        "solve_attempts",
        "generated_occurrences",
        "dedupe_decisions",
        "admission_decisions",
        "strategy_decisions",
    ):
        reordered[field].reverse()
    for roster in reordered["roster_identities"]:
        roster["player_id_bridge"].reverse()
    assert _build(reordered) == expected

    tampered = deepcopy(expected)
    tampered["counts"]["generated_occurrence_count"] = 99
    with pytest.raises(PrelockCandidateLineageError, match="self-hash"):
        validate_prelock_candidate_lineage_v1(tampered)

    tampered["sidecar_sha256"] = canonical_sha256(
        {key: value for key, value in tampered.items() if key != "sidecar_sha256"}
    )
    with pytest.raises(PrelockCandidateLineageError, match="do not reconcile"):
        validate_prelock_candidate_lineage_v1(tampered)


def test_recursive_outcome_firewall_and_prelock_boundary() -> None:
    with pytest.raises(PrelockCandidateLineageError, match="outcome-bearing"):
        assert_outcome_free({"safe": [{"realized_week_score": 201.4}]})

    raw = _fixture()
    raw["run_header"]["frozen_at_utc"] = raw["run_header"]["slate_lock_at_utc"]
    with pytest.raises(PrelockCandidateLineageError, match="before slate lock"):
        _build(raw)


def test_failed_solve_has_no_roster_and_no_candidate_first_loss_claim() -> None:
    raw = _fixture()
    raw["solve_attempts"][2]["roster_id"] = _roster_id(raw["roster_identities"][0])
    with pytest.raises(PrelockCandidateLineageError, match="must not carry"):
        _build(raw)

    raw = _fixture()
    raw["proposal_requests"][4]["terminal_status"] = "INFEASIBLE"
    with pytest.raises(PrelockCandidateLineageError, match="lacks a solve-attempt"):
        _build(raw)


def test_duplicate_attribution_and_downstream_cardinality_fail_closed() -> None:
    raw = _fixture()
    raw["dedupe_decisions"][1]["duplicate_of_occurrence_id"] = "occurrence-2"
    with pytest.raises(PrelockCandidateLineageError, match="first matching"):
        _build(raw)

    raw = _fixture()
    raw["strategy_decisions"].pop()
    with pytest.raises(PrelockCandidateLineageError, match="every effective"):
        _build(raw)

    raw = _fixture()
    raw["prepared_entries"][0]["roster_id"] = _roster_id(raw["roster_identities"][1])
    with pytest.raises(PrelockCandidateLineageError, match="exact paid export"):
        _build(raw)


def test_strategy_trace_uses_closed_mapping_for_provisional_events() -> None:
    strategy_rows = _build(_k2_fixture())["strategy_decisions"]
    assert [row["selection_phase"] for row in strategy_rows] == [
        "COVERAGE",
        "SATURATION_FILL",
    ]
    assert [row["tiebreak_values"] for row in strategy_rows] == [
        [0.75, 210.0],
        [0.5, 190.0],
    ]
    assert [row["fresh_world_count"] for row in strategy_rows] == [2, 0]

    raw = _fixture()
    raw["strategy_decisions"][0]["selection_phase"] = "coverage"
    with pytest.raises(PrelockCandidateLineageError, match="closed enum"):
        _build(raw)

    raw = _fixture()
    raw["strategy_decisions"][0]["tiebreak_values"] = [2, 0.75, 210.0]
    with pytest.raises(PrelockCandidateLineageError, match="tiebreak"):
        _build(raw)


def test_produced_attempt_and_dedupe_cardinality_reject_duplicate_rows() -> None:
    raw = _fixture()
    duplicate = deepcopy(raw["generated_occurrences"][0])
    duplicate.update({"occurrence_id": "occurrence-3", "occurrence_ordinal": 3})
    raw["generated_occurrences"].append(duplicate)
    with pytest.raises(PrelockCandidateLineageError, match="one-to-one"):
        _build(raw)

    raw = _fixture()
    duplicate = deepcopy(raw["dedupe_decisions"][1])
    duplicate["decision_id"] = "dedupe-3"
    raw["dedupe_decisions"].append(duplicate)
    with pytest.raises(PrelockCandidateLineageError, match="one-to-one"):
        _build(raw)


def test_every_occurrence_must_reach_one_initial_candidate() -> None:
    raw = _fixture()
    raw["admission_decisions"][0]["source_occurrence_ids"] = ["occurrence-0"]
    with pytest.raises(PrelockCandidateLineageError, match="every generated"):
        _build(raw)


def test_retained_candidate_cannot_disappear_or_fork_between_stages() -> None:
    raw = _fixture()
    raw["admission_decisions"].pop(3)
    with pytest.raises(PrelockCandidateLineageError, match="flow exactly once"):
        _build(raw)

    raw = _fixture()
    duplicate = deepcopy(raw["admission_decisions"][3])
    duplicate.update(
        {
            "decision_id": "admission-effective-2",
            "candidate_instance_id": "candidate-effective-2",
            "candidate_ordinal": 2,
        }
    )
    raw["admission_decisions"].append(duplicate)
    with pytest.raises(PrelockCandidateLineageError, match="one candidate"):
        _build(raw)


def test_strategy_book_and_prepared_candidate_cardinality_is_unique() -> None:
    raw = _fixture()
    duplicate = deepcopy(raw["strategy_decisions"][0])
    duplicate["decision_id"] = "strategy-duplicate"
    raw["strategy_decisions"].append(duplicate)
    with pytest.raises(PrelockCandidateLineageError, match="one decision"):
        _build(raw)

    raw = _fixture()
    duplicate = deepcopy(raw["book_transitions"][0])
    duplicate["transition_id"] = "book-duplicate"
    raw["book_transitions"].append(duplicate)
    with pytest.raises(PrelockCandidateLineageError, match="one book transition"):
        _build(raw)

    raw = _k2_fixture()
    raw["book_transitions"][1]["roster_id"] = _roster_id(raw["roster_identities"][0])
    with pytest.raises(PrelockCandidateLineageError, match="matching strategy"):
        _build(raw)

    raw = _k2_fixture()
    raw["prepared_entries"][1]["candidate_instance_id"] = "candidate-effective-0"
    raw["prepared_entries"][1]["roster_id"] = _roster_id(raw["roster_identities"][0])
    with pytest.raises(PrelockCandidateLineageError, match="repeats a candidate"):
        _build(raw)


def test_validate_rejects_noncanonical_partition_order() -> None:
    sidecar = _build(_fixture())
    sidecar["proposal_requests"].reverse()
    sidecar["sidecar_sha256"] = canonical_sha256(
        {key: value for key, value in sidecar.items() if key != "sidecar_sha256"}
    )
    with pytest.raises(PrelockCandidateLineageError, match="canonical order"):
        validate_prelock_candidate_lineage_v1(sidecar)
