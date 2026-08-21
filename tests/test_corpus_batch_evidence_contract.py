"""Offline tests for the outcome-blind corpus batch evidence contract."""

from __future__ import annotations

from copy import deepcopy

import pytest

from nfl_dfs.research import corpus_batch_evidence_contract as evidence
from nfl_dfs.research import corpus_parametric_batch as batch


def _receipt(name: str, generation: int = 1) -> dict[str, object]:
    return {
        "uri": f"gs://test-bucket/contracts/{name}.json",
        "generation": str(generation),
        "sha256": f"{generation % 10}" * 64,
        "bytes": 100 + generation,
    }


def _common_law() -> dict[str, object]:
    digest = "sha256:" + "a" * 64
    source_receipts = {
        "later_source_freeze": _receipt("later-source-freeze", 2),
    }
    return {
        "code_source": _receipt("code-source", 1),
        "immutable_image": {
            "uri": f"registry.example/nfl-dfs/corpus@{digest}",
            "digest": digest,
        },
        "source_receipts": source_receipts,
        "source_receipt_set_sha256": batch.canonical_sha256(source_receipts),
        "later_source_freeze_manifest_sha256": "9" * 64,
        "artifact_source_authority_completion": _receipt(
            "artifact-source-authority-completion", 14
        ),
        "artifact_source_authority_completion_sha256": "2" * 64,
        "effective_policy_inventory_identity": _receipt(
            "effective-policy-inventory", 3
        ),
        "effective_policy_inventory_sha256": (
            evidence.EXPECTED_INVENTORY_SHA256
        ),
        "effective_policy_rule_universe_sha256": (
            evidence.EXPECTED_RULE_UNIVERSE_SHA256
        ),
        "effective_policy_inventory_source_set_sha256": (
            evidence.EXPECTED_INVENTORY_SOURCE_SET_SHA256
        ),
        "effective_policy_classified_input_projection_sha256": (
            evidence.EXPECTED_CLASSIFIED_INPUT_PROJECTION_SHA256
        ),
        "world_schedule": _receipt("world-schedule", 4),
        "world_seed": 7331,
        "objective": _receipt("objective", 5),
        "solve_budget": {
            "solve_attempts_per_seed": 200,
            "worlds_per_block": 10_000,
            "solver_timeout_seconds": 120,
            "candidate_entry_budget": 1_000,
            "selected_entry_budget": 80,
        },
        "generator_families": _receipt("generator-families", 6),
        "unique_fill": _receipt("unique-fill", 7),
        "deduplication": _receipt("deduplication", 8),
        "admission": _receipt("admission", 9),
        "cbwu": _receipt("cbwu", 10),
        "selector": _receipt("selector", 11),
        "line_194": _receipt("line-194", 12),
        "exact_80": _receipt("exact-80", 13),
        "solver": {
            "name": "cbc",
            "version": "2.10.3",
            "binary_sha256": "b" * 64,
            "options_sha256": "c" * 64,
            "exact_mode": True,
        },
        "retry_law": {"max_attempts_per_task": 1, "max_retries": 0},
        "fresh_model_state_per_parameter_set": True,
        "worker_environment_inheritance": False,
        "worker_graph_mutation": False,
    }


def _world_artifacts(task_index: int) -> dict[str, dict[str, object]]:
    return {
        role: _receipt(
            f"task-{task_index}-{role}", 70 + task_index * 10 + ordinal
        )
        for ordinal, role in enumerate(batch.TASK_WORLD_SOURCE_ROLES)
    }


def _tasks() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for task_index, (season, week) in enumerate(((2023, 1), (2024, 2))):
        artifacts = _world_artifacts(task_index)
        rows.append({
            "task_index": task_index,
            "slate_id": f"{season}-w{week}-main",
            "season": season,
            "week": week,
            "result_receipt_uri": (
                f"gs://test-bucket/batches/corpus-demo-v1/tasks/"
                f"{task_index:03d}.json"
            ),
            "variant_output_prefix": (
                f"gs://test-bucket/batches/corpus-demo-v1/variants/"
                f"task-{task_index:03d}/"
            ),
            "world_artifact_receipts": artifacts,
            "world_artifact_receipt_set_sha256": batch.canonical_sha256(
                artifacts
            ),
            "artifact_source_authority_task_sha256": (
                str(5 + task_index) * 64
            ),
        })
    return rows


def _manifest() -> dict[str, object]:
    return batch.build_batch_manifest(
        batch_id="corpus-demo-v1",
        created_at_utc="2026-08-21T12:00:00Z",
        output_prefix="gs://test-bucket/batches/corpus-demo-v1/",
        common_law=_common_law(),
        tasks=_tasks(),
    )


def _manifest_identity(manifest: dict[str, object]) -> dict[str, object]:
    return batch.object_identity_for_json(
        manifest, uri=manifest["manifest_uri"], generation="100"
    )


def _contract() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    manifest = _manifest()
    identity = _manifest_identity(manifest)
    contract = evidence.build_corpus_batch_evidence_contract(
        batch_manifest=manifest,
        batch_manifest_identity=identity,
    )
    return manifest, identity, contract


def _rehash(contract: dict[str, object]) -> None:
    body = {
        key: value
        for key, value in contract.items()
        if key != "evidence_contract_sha256"
    }
    contract["evidence_contract_sha256"] = batch.canonical_sha256(body)


def test_contract_binds_exact_batch_and_is_outcome_blind() -> None:
    manifest, identity, contract = _contract()
    assert contract["schema_version"] == evidence.SCHEMA
    assert contract["decision_authority"] is False
    assert contract["uses_realized_outcomes"] is False
    assert contract["knowledge_class"] == "outcome_blind"
    assert contract["publication_mode"] == "create_once"
    assert contract["contract_uri"] == (
        manifest["output_prefix"]
        + "governance/pre-run-evidence-contract.json"
    )
    binding = contract["batch_binding"]
    assert binding["batch_manifest_identity"] == identity
    assert binding["batch_manifest_sha256"] == manifest[
        "batch_manifest_sha256"
    ]
    assert binding["parameter_schema_sha256"] == batch.PARAMETER_SCHEMA_SHA256
    assert [row["parameter_set_id"] for row in binding["parameter_sets"]] == list(
        batch.PARAMETER_SET_ORDER
    )
    assert len(binding["task_lattice"]) == 2
    assert evidence.validate_corpus_batch_evidence_contract(
        contract,
        batch_manifest=manifest,
        batch_manifest_identity=identity,
    ) == contract


def test_historical_law_is_incumbent_vs_all_six_with_c_and_s_coprimary() -> None:
    _, _, contract = _contract()
    law = contract["historical_decision_law"]
    assert law["incumbent_parameter_set_id"] == "incumbent"
    assert law["comparison_count"] == 6
    assert [
        row["challenger_parameter_set_id"]
        for row in law["challenger_comparisons"]
    ] == list(batch.PARAMETER_SET_ORDER[1:])
    assert law["co_primary_endpoint_ids"] == [
        "endpoint:corpus:realized-candidate-ceiling-c",
        "endpoint:corpus:realized-exact80-maximum-s",
    ]
    assert law["joint_p_formula"] == (
        "max(p_C_mean_two_sided,p_C_signed_rank_two_sided,"
        "p_S_mean_two_sided,p_S_signed_rank_two_sided)"
    )
    assert law["multiplicity"] == {
        "alpha": 0.05,
        "family": "six-frozen-challengers-vs-common-incumbent",
        "holm_formula": (
            "sort (joint_p,challenger_ordinal); at zero-based position j "
            "compute min(1,(6-j)*joint_p); take the capped running maximum; "
            "map back to challenger ordinal"
        ),
        "hypothesis_count": 6,
        "method": "holm_step_down",
        "missing_or_invalid_comparison": "invalidate_entire_completion",
        "rounded_values_may_decide": False,
    }
    assert law["paired_test_law"] == evidence.PAIRED_TEST_LAW
    paired = law["paired_test_law"]
    assert paired["monte_carlo_rng_lifecycle"] == (
        "fresh-default_rng-seed-for-each-challenger-and-endpoint"
    )
    assert paired["monte_carlo_rng_call"] == (
        "rng.choice((-1.0,1.0),size=(take,n_nonzero))"
    )
    assert paired["same_sign_matrix_for_mean_and_signed_rank"] is True
    assert "holm_adjusted_joint_p_le_0.05" in law[
        "historical_pass_predicates"
    ]


def test_nominee_order_and_shadow_boundary_are_literal() -> None:
    _, _, contract = _contract()
    law = contract["historical_decision_law"]
    assert law["nominee_pool"] == "historical_pass_true_only"
    assert law["nominee_order"] == [
        "smallest_holm_adjusted_joint_p",
        "largest_mean_delta_s",
        "largest_mean_delta_c",
        "largest_selected_s_200_count_delta",
        "smallest_fixed_parameter_set_ordinal",
    ]
    machine = contract["license_state_machine"]
    assert machine["invariants"]["at_most_one_shadow_parameter_set"] is True
    assert machine["invariants"]["shadow_default_off"] is True
    nominee = next(
        row for row in machine["transitions"]
        if row["event"]
        == "separately_governed_realized_completion_with_nominee"
    )
    state = nominee["result"]
    assert state["prospective_shadow_create_licensed"] is True
    assert state["prospective_shadow_freeze_licensed"] is True
    assert state["prospective_shadow_deploy_default_off_licensed"] is True
    assert state["prospective_shadow_passed"] is False
    for key in (
        "production_change_licensed", "adoption_licensed",
        "default_on_licensed", "money_entry_licensed",
        "historical_retry_licensed", "historical_retune_licensed",
    ):
        assert state[key] is False
    assert machine["unseen_2026_transition"]["inside_this_contract"] is False


def test_score_free_nonvacuity_gates_include_monotonicity_and_rule_escape() -> None:
    _, _, contract = _contract()
    gates = {
        row["id"]: row for row in contract["pre_outcome_gate_registry"]
    }
    monotonicity = gates[
        "gate:corpus:paired-objective-relaxation-monotonicity"
    ]["predicate"]
    assert "challenger primary optimum minus incumbent primary optimum" in (
        monotonicity
    )
    assert ">= 0" in monotonicity
    assert "6 * task_count * 1000" in monotonicity
    nonvacuity = gates[
        "gate:corpus:outside-incumbent-law-nonvacuity"
    ]["predicate"]
    assert "every single-removal arm" in nonvacuity
    assert "violating its removed rule while satisfying the other four" in (
        nonvacuity
    )
    assert "all-five arm" in nonvacuity
    coverage = gates[
        "gate:corpus:historical-exact-roster-coverage-contract"
    ]["predicate"]
    assert "every frozen generated-unique roster" in coverage
    assert "exact80-only" in coverage
    assert "task_index,season,week,slate_id" in coverage
    assert "no cross-slate aliasing" in coverage
    simulated_coverage = gates[
        "gate:corpus:simulated-score-matrix-exact-roster-world-coverage"
    ]["predicate"]
    assert "exactly 50000 ordered values" in simulated_coverage
    assert "equals the complete generated-unique roster set" in (
        simulated_coverage
    )
    assert "R0..R4 x 0..9999" in simulated_coverage
    assert "selected-only" in simulated_coverage
    assert all(row["required_for_outcome_read"] is True for row in gates.values())


def test_endpoint_registry_freezes_formulas_directions_and_exact_units() -> None:
    endpoints = {row["id"]: row for row in evidence.endpoint_registry()}
    assert len(endpoints) == 24
    simulated_coverage = endpoints[
        "endpoint:corpus:simulated-scored-generated-unique-count"
    ]
    assert simulated_coverage["direction"] == (
        "exact_generated_unique_by_50000_required"
    )
    assert "exactly one float64 score row" in simulated_coverage["formula"]
    assert "ordered R0..R4 x 0..9999" in simulated_coverage["formula"]
    coverage_endpoint = endpoints[
        "endpoint:corpus:realized-scored-generated-unique-count"
    ]
    assert coverage_endpoint["direction"] == (
        "exact_generated_unique_count_required"
    )
    assert "complete frozen keyed" in coverage_endpoint["formula"]
    assert "task_index,season,week,slate_id" in coverage_endpoint["formula"]
    c_endpoint = endpoints["endpoint:corpus:realized-candidate-ceiling-c"]
    s_endpoint = endpoints["endpoint:corpus:realized-exact80-maximum-s"]
    assert c_endpoint["gate_role"] == "historical_co_primary"
    assert s_endpoint["gate_role"] == "historical_co_primary"
    assert c_endpoint["direction"] == s_endpoint["direction"] == (
        "higher_is_better"
    )
    assert c_endpoint["population_stage"] == "generated_unique"
    assert s_endpoint["population_stage"] == "selected_exact80"
    assert c_endpoint["thresholds_micro"] == [
        value * 1_000_000 for value in evidence.THRESHOLDS_DK
    ]
    assert endpoints[
        "endpoint:corpus:dk-invalid-generated-unique-count"
    ]["direction"] == "exact_zero_required"
    violation_ids = [
        endpoint_id for endpoint_id in endpoints if endpoint_id.endswith(
            "-violations"
        )
    ]
    assert len(violation_ids) == 10


def test_all_results_winners_and_losers_are_required() -> None:
    _, _, contract = _contract()
    reporting = contract["reporting_law"]
    assert reporting["parameter_set_order"] == list(batch.PARAMETER_SET_ORDER)
    assert reporting["all_seven_outcome_blind_rows_required"] is True
    assert reporting["all_seven_realized_rows_required_if_outcomes_are_read"] is True
    assert reporting["complete_winner_loser_table_required"] is True
    assert reporting["failed_tied_losing_or_ineligible_arms_reported"] is True
    assert reporting["winner_or_nominee_only_output"] == "forbidden"
    winner_loser = contract["historical_decision_law"][
        "winner_loser_reporting"
    ]
    assert winner_loser["realized_result_rows_required"] == 7
    assert winner_loser[
        "losing_tied_failed_or_ineligible_rows_may_be_omitted"
    ] is False


def test_graph_topology_is_append_only_truthful_and_batch_bound() -> None:
    _, _, contract = _contract()
    topology = contract["graph_extension_topology"]
    assert topology["parent_graph"] == evidence.PARENT_GRAPH
    assert topology["storage_plane"] == {
        "application_operational_datastore_shared": False,
        "authoritative_artifacts": (
            "canonical-create-once-json-and-generation-pinned-object-bodies"
        ),
        "dedicated_logical_database_required": True,
        "graph_can_authorize_execution_or_policy": False,
        "graph_payload_scope": (
            "identities-relations-rule-states-measurements-and-object-pointers"
        ),
        "large_world_matrices_or_raw_score_bodies_in_graph": False,
        "projection_is_append_only": True,
        "projection_is_rebuildable_from_authorities": True,
        "recommended_query_projection": "dedicated-neo4j-or-equivalent",
    }
    assert topology["adapter_law"] == {
        "append_only_new_graph_version": True,
        "decision_authority_before_realized_completion": False,
        "graph_is_run_controller": False,
        "independent_adapter_required": True,
        "outcome_blind_worker_graph_mutation": False,
        "parent_graph_immutable": True,
        "realized_decision_authority_scope": (
            "historical-shadow-nomination-only"
        ),
    }
    counts = topology["resolved_cardinalities"]
    assert counts == {
        "endpoint_count": 24,
        "gate_count": 14,
        "license_count": 12,
        "parameter_count": 5,
        "parameter_set_count": 7,
        "population_count": 42,
        "realized_measurement_count_if_completed": 56,
        "score_free_measurement_count": 26_252,
        "task_execution_count": 2,
    }
    population_families = [
        row for row in topology["node_families"]
        if row["kind"] == "population"
    ]
    assert len(population_families) == 3
    assert all(
        "task-{task_index_04d}" in row["id"]
        and row["cardinality"] == 14
        for row in population_families
    )
    measurement_families = [
        row for row in topology["node_families"]
        if row["kind"] == "measurement"
    ]
    assert {row["grain"] for row in measurement_families} == {
        "task_parameter_set", "task_parameter_set_visit",
        "task_challenger_visit",
    }
    assert all("task-{task_index_04d}" in row["id"] for row in measurement_families)
    assert sum(
        row["cardinality"] for row in measurement_families
        if row["materialization_phase"] == "score_free_completion"
    ) == 26_252
    assert sum(
        row["cardinality"] for row in measurement_families
        if row["materialization_phase"] == "realized_completion_only"
    ) == 56
    assert topology["population_stage_law"] == {
        "admission_label": "first-occurrence-generated-unique-union",
        "cbwu_admission_claim_permitted": False,
        "selected_population": "selected-exact80",
        "visit_population": "visit-output",
    }


def test_current_contract_fails_closed_on_missing_historical_authorities() -> None:
    _, _, contract = _contract()
    readiness = contract["pre_run_artifact_readiness"]
    assert readiness["historical_outcome_read_ready"] is False
    assert readiness["missing_role_count"] == 5
    missing = {
        row["role"]: row["blocks"]
        for row in contract["missing_pre_run_artifacts"]
    }
    assert missing == {
        "paired_statistics_implementation": "historical_outcome_read",
        "independent_paired_statistics_verifier": "historical_outcome_read",
        "historical_score_query_contract": "historical_outcome_read",
        "realized_completion_schema": "historical_outcome_read",
        "unseen_2026_shadow_gate_protocol": "prospective_shadow_deployment",
    }


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda value: value["endpoint_registry"][0].__setitem__(
                "direction", "lower_is_better"
            ),
            "differs from the frozen preregistration",
        ),
        (
            lambda value: value["historical_decision_law"][
                "multiplicity"
            ].__setitem__("hypothesis_count", 5),
            "differs from the frozen preregistration",
        ),
        (
            lambda value: value["license_state_machine"]["initial_state"].__setitem__(
                "production_change_licensed", True
            ),
            "differs from the frozen preregistration",
        ),
        (
            lambda value: value["reporting_law"]["parameter_set_order"].pop(),
            "differs from the frozen preregistration",
        ),
        (
            lambda value: value["pre_outcome_gate_registry"].pop(),
            "differs from the frozen preregistration",
        ),
    ],
)
def test_coordinated_tamper_and_rehash_still_fails(
    mutator, match: str
) -> None:
    manifest, identity, contract = _contract()
    mutator(contract)
    _rehash(contract)
    with pytest.raises(evidence.CorpusBatchEvidenceContractError, match=match):
        evidence.validate_corpus_batch_evidence_contract(
            contract,
            batch_manifest=manifest,
            batch_manifest_identity=identity,
        )


def test_manifest_inventory_drift_fails_before_contract_build() -> None:
    law = _common_law()
    law["effective_policy_inventory_sha256"] = "0" * 64
    manifest = batch.build_batch_manifest(
        batch_id="corpus-demo-v1",
        created_at_utc="2026-08-21T12:00:00Z",
        output_prefix="gs://test-bucket/batches/corpus-demo-v1/",
        common_law=law,
        tasks=_tasks(),
    )
    identity = _manifest_identity(manifest)
    with pytest.raises(
        evidence.CorpusBatchEvidenceContractError,
        match="effective_policy_inventory_sha256 differs",
    ):
        evidence.build_corpus_batch_evidence_contract(
            batch_manifest=manifest,
            batch_manifest_identity=identity,
        )


def test_manifest_identity_and_task_lattice_are_not_interchangeable() -> None:
    manifest, identity, contract = _contract()
    other = deepcopy(manifest)
    other["tasks"][0]["slate_id"] = "2023-w9-main"
    other["tasks"][0]["task_sha256"] = batch.canonical_sha256({
        key: other["tasks"][0][key]
        for key in other["tasks"][0]
        if key != "task_sha256"
    })
    other["batch_manifest_sha256"] = batch.canonical_sha256({
        key: other[key] for key in other if key != "batch_manifest_sha256"
    })
    other_identity = _manifest_identity(other)
    with pytest.raises(
        evidence.CorpusBatchEvidenceContractError,
        match="differs from the frozen preregistration",
    ):
        evidence.validate_corpus_batch_evidence_contract(
            contract,
            batch_manifest=other,
            batch_manifest_identity=other_identity,
        )
    assert identity != other_identity


def test_canonical_bytes_and_create_once_identity_replay() -> None:
    manifest, manifest_identity, contract = _contract()
    raw = batch.canonical_json_bytes(contract)
    assert evidence.validate_corpus_batch_evidence_contract_bytes(
        raw,
        batch_manifest=manifest,
        batch_manifest_identity=manifest_identity,
    ) == contract
    contract_identity = batch.object_identity_for_json(
        contract, uri=contract["contract_uri"], generation="101"
    )
    assert evidence.validate_corpus_batch_evidence_contract_identity(
        contract,
        contract_identity,
        batch_manifest=manifest,
        batch_manifest_identity=manifest_identity,
    ) == contract_identity
    bad_identity = deepcopy(contract_identity)
    bad_identity["uri"] = (
        "gs://test-bucket/batches/corpus-demo-v1/governance/other.json"
    )
    with pytest.raises(
        evidence.CorpusBatchEvidenceContractError,
        match="URI differs from deterministic path",
    ):
        evidence.validate_corpus_batch_evidence_contract_identity(
            contract,
            bad_identity,
            batch_manifest=manifest,
            batch_manifest_identity=manifest_identity,
        )


def test_noncanonical_or_duplicate_json_bytes_fail_closed() -> None:
    manifest, identity, contract = _contract()
    noncanonical = ("{\n  \"schema_version\": \"x\"\n}").encode()
    with pytest.raises(
        evidence.CorpusBatchEvidenceContractError,
        match="retained evidence contract bytes are invalid",
    ):
        evidence.validate_corpus_batch_evidence_contract_bytes(
            noncanonical,
            batch_manifest=manifest,
            batch_manifest_identity=identity,
        )
    raw = batch.canonical_json_bytes(contract)
    duplicate = raw[:-1] + b',"schema_version":"duplicate"}'
    with pytest.raises(
        evidence.CorpusBatchEvidenceContractError,
        match="retained evidence contract bytes are invalid",
    ):
        evidence.validate_corpus_batch_evidence_contract_bytes(
            duplicate,
            batch_manifest=manifest,
            batch_manifest_identity=identity,
        )
