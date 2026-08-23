"""Focused offline tests for post-acceptance corpus realized grading."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_realized_grading as grading


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _receipt(name: str, generation: int = 1) -> dict[str, object]:
    return {
        "uri": f"gs://fixture-authority/{name}.json",
        "generation": str(generation),
        "sha256": _digest(name),
        "bytes": 100 + generation,
    }


def _json_identity(
    value: object, *, uri: str, generation: int,
) -> dict[str, object]:
    return batch.object_identity_for_json(
        value, uri=uri, generation=str(generation)
    )


def _common_law() -> dict[str, object]:
    source_receipts = {"later_source_freeze": _receipt("later-source", 2)}
    digest = "sha256:" + "a" * 64
    return {
        "code_source": _receipt("code-source", 1),
        "immutable_image": {
            "uri": f"registry.example/corpus@{digest}", "digest": digest,
        },
        "source_receipts": source_receipts,
        "source_receipt_set_sha256": batch.canonical_sha256(source_receipts),
        "later_source_freeze_manifest_sha256": "9" * 64,
        "artifact_source_authority_completion": _receipt(
            "source-authority-completion", 3
        ),
        "artifact_source_authority_completion_sha256": "8" * 64,
        "effective_policy_inventory_identity": _receipt("policy-inventory", 4),
        "effective_policy_inventory_sha256": "7" * 64,
        "effective_policy_rule_universe_sha256": "6" * 64,
        "effective_policy_inventory_source_set_sha256": "5" * 64,
        "effective_policy_classified_input_projection_sha256": "4" * 64,
        "world_schedule": _receipt("world-schedule", 5),
        "world_seed": 20_260_821,
        "objective": _receipt("objective", 6),
        "solve_budget": {
            "solve_attempts_per_seed": 200,
            "worlds_per_block": 10_000,
            "solver_timeout_seconds": 600,
            "candidate_entry_budget": 1_000,
            "selected_entry_budget": 80,
        },
        "generator_families": _receipt("generator-families", 7),
        "unique_fill": _receipt("unique-fill", 8),
        "deduplication": _receipt("deduplication", 9),
        "admission": _receipt("admission", 10),
        "cbwu": _receipt("cbwu", 11),
        "selector": _receipt("selector", 12),
        "line_194": _receipt("line-194", 13),
        "exact_80": _receipt("exact-80", 14),
        "solver": {
            "name": "cbc", "version": "2.10.3",
            "binary_sha256": "b" * 64, "options_sha256": "c" * 64,
            "exact_mode": True,
        },
        "retry_law": {"max_attempts_per_task": 1, "max_retries": 0},
        "fresh_model_state_per_parameter_set": True,
        "worker_environment_inheritance": False,
        "worker_graph_mutation": False,
    }


def _manifest() -> dict[str, object]:
    output = "gs://fixture-batch/corpus-parametric-research/batches/grade-fixture-v1/"
    tasks: list[dict[str, object]] = []
    for task_index in range(grading.EXPECTED_TASK_COUNT):
        season = 2023 + task_index // 18
        week = task_index % 18 + 1
        world_receipts = {
            role: _receipt(
                f"worlds/task-{task_index:04d}/{role}",
                1_000 + task_index * 10 + ordinal,
            )
            for ordinal, role in enumerate(batch.TASK_WORLD_SOURCE_ROLES)
        }
        tasks.append({
            "task_index": task_index,
            "slate_id": f"{season}-w{week}-main",
            "season": season,
            "week": week,
            "result_receipt_uri": f"{output}tasks/{task_index:04d}/result.json",
            "variant_output_prefix": f"{output}variants/task-{task_index:04d}/",
            "world_artifact_receipts": world_receipts,
            "world_artifact_receipt_set_sha256": batch.canonical_sha256(
                world_receipts
            ),
            "artifact_source_authority_task_sha256": _digest(
                f"source-task-{task_index}"
            ),
        })
    return batch.build_batch_manifest(
        batch_id="grade-fixture-v1",
        created_at_utc="2026-08-21T18:00:00Z",
        output_prefix=output,
        common_law=_common_law(),
        tasks=tasks,
    )


def _rosters() -> list[list[str]]:
    common = [f"p{index:03d}" for index in range(8)]
    return [sorted([*common, f"p{index:03d}"]) for index in range(8, 89)]


def _variant_result(
    manifest: dict[str, object], *, task_index: int, ordinal: int,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    task = manifest["tasks"][task_index]
    parameter_set = manifest["parameter_sets"][ordinal]
    rosters = _rosters()
    selected_indices = list(range(80))
    selected = [rosters[index] for index in selected_indices]
    body: dict[str, object] = {
        "schema": grading.VARIANT_RESULT_SCHEMA,
        "slate": {
            "season": task["season"], "week": task["week"],
            "slate_id": task["slate_id"],
        },
        "later_source_freeze_manifest_sha256": manifest["common_law"][
            "later_source_freeze_manifest_sha256"
        ],
        "artifact_sha256_by_block": {
            role: receipt["sha256"]
            for role, receipt in task["world_artifact_receipts"].items()
        },
        "task_source_binding": {
            "binding_sha256": _digest(f"binding-{task_index}"),
            "batch_manifest_sha256": manifest["batch_manifest_sha256"],
            "task_index": task_index,
            "task_sha256": task["task_sha256"],
            "artifact_source_authority_completion_object_sha256": _digest(
                "authority-completion-object"
            ),
            "artifact_source_authority_completion_sha256": manifest["common_law"][
                "artifact_source_authority_completion_sha256"
            ],
            "artifact_source_authority_task_sha256": task[
                "artifact_source_authority_task_sha256"
            ],
            "later_source_freeze_manifest_sha256": manifest["common_law"][
                "later_source_freeze_manifest_sha256"
            ],
            "world_artifact_receipt_set_sha256": task[
                "world_artifact_receipt_set_sha256"
            ],
        },
        "visit_schedule_sha256": _digest("visit-schedule"),
        "attempt_ledger_sha256": _digest(f"attempts-{task_index}"),
        "matrix_authority_sha256": _digest(f"matrix-{task_index}"),
        "solver_evidence_task_root_sha256": _digest(f"solver-{task_index}"),
        "profile": {
            "ordinal": ordinal,
            "parameter_set_id": parameter_set["parameter_set_id"],
            "parameter_set_sha256": parameter_set["parameter_set_sha256"],
            "parameter_values": parameter_set["values"],
            "stack_rules": {},
            "shared_constraints": {},
        },
        "runtime_effective_policy": {},
        "coverage": {
            "scheduled_visits": 1_000, "attempted_visits": 1_000,
            "optimal_visits": 1_000, "unique_candidates": len(rosters),
            "selected_entries": 80,
        },
        "variant_attempt_rows_sha256": _digest(
            f"attempt-rows-{task_index}-{ordinal}"
        ),
        "visit_rosters": [],
        "unique_rosters": rosters,
        "first_occurrence_visit_indices": list(range(len(rosters))),
        "candidate_score_sha256": _digest(
            f"candidate-scores-{task_index}-{ordinal}"
        ),
        "selector": {
            "candidate_count": len(rosters), "world_count": 50_000,
            "entry_count": 80, "tail_line_dk": 194.0,
            "selected_indices": selected_indices,
            "tie_law_applied": "gain,p_line,mean_score,first_occurrence",
        },
        "selected_rosters": selected,
        "selected_score_sha256": _digest(
            f"selected-scores-{task_index}-{ordinal}"
        ),
        "house_rule_violation_census": {},
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    result = {**body, "result_sha256": batch.canonical_sha256(body)}
    prefix = f"{task['variant_output_prefix']}{parameter_set['parameter_set_id']}/"
    identity = _json_identity(
        result,
        uri=f"{prefix}result.json",
        generation=20_000 + task_index * 10 + ordinal,
    )
    effective_policy = _receipt(
        f"effective-policy/task-{task_index:04d}/{ordinal}",
        30_000 + task_index * 10 + ordinal,
    )
    effective_policy["uri"] = f"{prefix}effective-policy.json"
    binding = {
        "ordinal": ordinal,
        "parameter_set_id": parameter_set["parameter_set_id"],
        "parameter_set_sha256": parameter_set["parameter_set_sha256"],
        "effective_policy_receipt": effective_policy,
        "result_object": identity,
    }
    return result, identity, binding


def _task_acceptance(
    *,
    task: dict[str, object],
    task_result_identity: dict[str, object],
    transport: dict[str, object],
    prerequisite: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    task_index = task["task_index"]
    body: dict[str, object] = {
        "schema_version": grading.TASK_ACCEPTANCE_SCHEMA,
        "accepted_at_utc": "2026-08-21T18:30:00Z",
        "transport_contract": transport,
        "retrieval_task0_prerequisite_identity": prerequisite,
        "task_index": task_index,
        "task_sha256": task["task_sha256"],
        "producer_close": _receipt(f"producer-close-{task_index}", 40_000 + task_index),
        "science_terminal": _receipt(f"science-terminal-{task_index}", 41_000 + task_index),
        "task_result": task_result_identity,
        "verifier_worker_completion": _receipt(
            f"verifier-completion-{task_index}", 42_000 + task_index
        ),
        "independent_verification": _receipt(
            f"independent-verification-{task_index}", 43_000 + task_index
        ),
        "independent_verification_sha256": _digest(
            f"independent-verification-body-{task_index}"
        ),
        "verifier_terminal_execution": {},
        "terminal_governance_census": {},
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
    value = {**body, "task_acceptance_sha256": batch.canonical_sha256(body)}
    identity = _json_identity(
        value,
        uri=f"{task['variant_output_prefix']}accepted-terminal.json",
        generation=50_000 + int(task_index),
    )
    return value, identity


def _outcome_rows(manifest: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for task in manifest["tasks"]:
        for player_index in range(89):
            score = 0 if player_index < 8 else player_index * 1_000_000
            if player_index == 88:
                score = 300_000_000
            rows.append({
                "task_index": task["task_index"],
                "season": task["season"],
                "week": task["week"],
                "slate_id": task["slate_id"],
                "player_id": f"p{player_index:03d}",
                "realized_score_micro": score,
            })
    return rows


def _accepted_fixture() -> dict[str, object]:
    manifest = _manifest()
    manifest_identity = _json_identity(
        manifest, uri=manifest["manifest_uri"], generation=10_000
    )
    transport = _receipt("transport-contract", 60_000)
    prerequisite = _receipt("retrieval-prerequisite", 60_001)
    accepted_tasks: list[dict[str, object]] = []
    retained_results: list[dict[str, object]] = []
    task_acceptance_identities: list[dict[str, object]] = []
    for task_index, task in enumerate(manifest["tasks"]):
        variant_rows: list[dict[str, object]] = []
        variant_bindings: list[dict[str, object]] = []
        for ordinal in range(7):
            result, identity, binding = _variant_result(
                manifest, task_index=task_index, ordinal=ordinal
            )
            variant_rows.append({"result": result, "object_identity": identity})
            variant_bindings.append(binding)
        task_result = batch.build_task_result_receipt(
            batch_manifest=manifest,
            batch_manifest_identity=manifest_identity,
            task_index=task_index,
            execution={
                "execution_id": f"fixture-task-{task_index:04d}",
                "execution_uid": f"fixture-uid-{task_index:04d}",
                "task_index": task_index,
                "attempt": 1,
                "retry_count": 0,
                "terminal_status": "succeeded",
                "terminal_receipt": _receipt(
                    f"terminal-{task_index}", 70_000 + task_index
                ),
            },
            variant_results=variant_bindings,
        )
        task_result_identity = _json_identity(
            task_result,
            uri=task["result_receipt_uri"],
            generation=80_000 + task_index,
        )
        task_acceptance, task_acceptance_identity = _task_acceptance(
            task=task,
            task_result_identity=task_result_identity,
            transport=transport,
            prerequisite=prerequisite,
        )
        accepted_tasks.append({
            "task_result": task_result,
            "task_result_identity": task_result_identity,
            "task_acceptance": task_acceptance,
            "task_acceptance_identity": task_acceptance_identity,
            "variant_results": variant_rows,
        })
        retained_results.append({
            "receipt": task_result, "object_identity": task_result_identity,
        })
        task_acceptance_identities.append(task_acceptance_identity)

    completion = batch.build_batch_completion_receipt(
        batch_manifest=manifest,
        batch_manifest_identity=manifest_identity,
        retained_task_results=retained_results,
    )
    completion_identity = _json_identity(
        completion,
        uri=f"{manifest['output_prefix']}governance/batch-completion.json",
        generation=90_000,
    )
    inventory_identities = [
        manifest_identity, completion_identity, *task_acceptance_identities,
    ]
    inventory = sorted(({
        "uri": row["uri"], "generation": row["generation"],
        "bytes": row["bytes"],
    } for row in inventory_identities), key=lambda row: (
        row["uri"], row["generation"]
    ))
    acceptance_body: dict[str, object] = {
        "schema_version": grading.BATCH_ACCEPTANCE_SCHEMA,
        "accepted_at_utc": "2026-08-21T18:45:00Z",
        "transport_contract": transport,
        "retrieval_task0_prerequisite_identity": prerequisite,
        "batch_mode": "complete-54-task",
        "batch_completion": completion_identity,
        "task_acceptances": task_acceptance_identities,
        "task_count": 54,
        "parameter_set_count": 7,
        "matrix_cell_count": 378,
        "output_inventory_before_batch_acceptance": inventory,
        "output_inventory_before_batch_acceptance_sha256": batch.canonical_sha256(
            inventory
        ),
        "output_object_count_before_batch_acceptance": len(inventory),
        "complete": True,
        "accepted": True,
        "partial_result": False,
        "independent_verification_complete_for_every_task": True,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    acceptance = {
        **acceptance_body,
        "batch_acceptance_sha256": batch.canonical_sha256(acceptance_body),
    }
    acceptance_identity = _json_identity(
        acceptance,
        uri=f"{manifest['output_prefix']}governance/batch-acceptance.json",
        generation=90_001,
    )
    source_identity = _receipt("actual-score-source", 100_000)
    outcome_rows = _outcome_rows(manifest)
    outcomes = grading.build_actual_player_outcomes(
        batch_manifest=manifest,
        source_identity=source_identity,
        rows=outcome_rows,
    )
    outcome_identity = _json_identity(
        outcomes,
        uri="gs://fixture-realized/grade-fixture-v1/actual-player-outcomes.json",
        generation=100_001,
    )
    return {
        "batch_manifest": manifest,
        "batch_manifest_identity": manifest_identity,
        "batch_completion": completion,
        "batch_completion_identity": completion_identity,
        "batch_acceptance": acceptance,
        "batch_acceptance_identity": acceptance_identity,
        "accepted_tasks": accepted_tasks,
        "actual_player_outcomes": outcomes,
        "actual_player_outcomes_identity": outcome_identity,
        "outcome_rows": outcome_rows,
        "source_identity": source_identity,
    }


@pytest.fixture(scope="module")
def evidence() -> dict[str, object]:
    return _accepted_fixture()


def _grade(evidence: dict[str, object], **overrides: object) -> dict[str, object]:
    inputs = {
        key: evidence[key]
        for key in (
            "batch_manifest", "batch_manifest_identity", "batch_completion",
            "batch_completion_identity", "batch_acceptance",
            "batch_acceptance_identity", "accepted_tasks",
            "actual_player_outcomes", "actual_player_outcomes_identity",
        )
    }
    inputs.update(overrides)
    return grading.grade_accepted_batch(**inputs)


def test_complete_54_by_7_batch_scores_every_roster_and_emits_graph_metrics(
    evidence: dict[str, object],
) -> None:
    result = _grade(evidence)

    assert result["schema_version"] == grading.RESULT_SCHEMA
    assert len(result["task_arm_metrics"]) == 54 * 7
    assert result["coverage"] == {
        "task_count": 54,
        "parameter_set_count": 7,
        "task_arm_count": 378,
        "generated_unique_membership_count": 54 * 7 * 81,
        "realized_scored_generated_unique_membership_count": 54 * 7 * 81,
        "selected_exact80_membership_count": 54 * 7 * 80,
        "realized_scored_selected_exact80_membership_count": 54 * 7 * 80,
        "distinct_task_roster_count": 54 * 81,
        "actual_player_outcome_row_count": 54 * 89,
        "endpoint_measurement_count": 54 * 7 * 4,
        "all_tasks_accepted": True,
        "all_task_arms_present": True,
        "every_generated_unique_roster_scored_exactly_once_per_task_arm": True,
        "every_selected_exact80_roster_scored_exactly_once_per_task_arm": True,
        "actual_player_outcome_keys_exact": True,
        "complete": True,
    }
    first = result["task_arm_metrics"][0]
    endpoints = {row["endpoint_id"]: row["value"] for row in first["endpoints"]}
    assert endpoints["endpoint:corpus:realized-candidate-ceiling-c"] == 300_000_000
    assert endpoints["endpoint:corpus:realized-exact80-maximum-s"] == 87_000_000
    assert endpoints[
        "endpoint:corpus:realized-conversion-gap-c-minus-s"
    ] == 213_000_000
    assert endpoints[
        "endpoint:corpus:realized-scored-generated-unique-count"
    ] == 81
    assert first["threshold_counts"][0] == {
        "threshold_micro": 187_000_000,
        "generated_unique_at_or_above_count": 1,
        "selected_exact80_at_or_above_count": 0,
    }
    assert grading.validate_realized_grade(result) == result
    assert grading.canonical_sha256({
        key: value for key, value in result.items()
        if key != "realized_grade_sha256"
    }) == result["realized_grade_sha256"]


def test_each_generated_unique_membership_has_one_scoring_pass(
    evidence: dict[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = grading._score_rosters
    scored_population_sizes: list[int] = []

    def counted(
        rosters: object, *, task_index: int, player_scores: object,
    ) -> object:
        scored_population_sizes.append(len(rosters))
        return original(
            rosters, task_index=task_index, player_scores=player_scores
        )

    monkeypatch.setattr(grading, "_score_rosters", counted)
    _grade(evidence)

    assert len(scored_population_sizes) == 54 * 7
    assert scored_population_sizes == [81] * (54 * 7)


def test_rank_and_roi_are_explicitly_unavailable_not_fabricated(
    evidence: dict[str, object],
) -> None:
    result = _grade(evidence)
    assert result["contest_metrics"] == {
        "availability": "unavailable",
        "reason": "full_field_standings_and_payout_ladder_not_supplied",
        "full_field_standings_identity": None,
        "payout_ladder_identity": None,
        "rank": None,
        "roi_micro_usd": None,
    }
    with pytest.raises(grading.CorpusRealizedGradingError, match="full-field"):
        _grade(evidence, contest_outcomes={"rank": 1, "roi": 42})


def test_incomplete_acceptance_or_missing_arm_fails_before_grading(
    evidence: dict[str, object],
) -> None:
    with pytest.raises(grading.CorpusRealizedGradingError, match="all 54 tasks"):
        _grade(evidence, accepted_tasks=evidence["accepted_tasks"][:-1])

    changed = list(evidence["accepted_tasks"])
    changed[0] = {**changed[0], "variant_results": changed[0]["variant_results"][:-1]}
    with pytest.raises(grading.CorpusRealizedGradingError, match="seven variant"):
        _grade(evidence, accepted_tasks=changed)


@pytest.mark.parametrize("remove,extra", [(True, False), (False, True)])
def test_player_outcome_keys_must_exactly_equal_full_generated_union(
    evidence: dict[str, object], remove: bool, extra: bool,
) -> None:
    rows = list(evidence["outcome_rows"])
    if remove:
        rows.pop()
    if extra:
        task = evidence["batch_manifest"]["tasks"][0]
        rows.append({
            "task_index": 0, "season": task["season"], "week": task["week"],
            "slate_id": task["slate_id"], "player_id": "unused-player",
            "realized_score_micro": 0,
        })
    outcomes = grading.build_actual_player_outcomes(
        batch_manifest=evidence["batch_manifest"],
        source_identity=evidence["source_identity"],
        rows=rows,
    )
    identity = _json_identity(
        outcomes,
        uri="gs://fixture-realized/grade-fixture-v1/changed-outcomes.json",
        generation=100_002,
    )
    with pytest.raises(grading.CorpusRealizedGradingError, match="exactly equal"):
        _grade(
            evidence,
            actual_player_outcomes=outcomes,
            actual_player_outcomes_identity=identity,
        )


def test_outcomes_are_task_slate_keyed_exact_micro_integers(
    evidence: dict[str, object],
) -> None:
    rows = deepcopy(evidence["outcome_rows"])
    rows[0]["week"] += 1
    with pytest.raises(grading.CorpusRealizedGradingError, match="task/slate"):
        grading.build_actual_player_outcomes(
            batch_manifest=evidence["batch_manifest"],
            source_identity=evidence["source_identity"],
            rows=rows,
        )
    rows = deepcopy(evidence["outcome_rows"])
    rows[0]["realized_score_micro"] = 1.5
    with pytest.raises(grading.CorpusRealizedGradingError, match="exact integer"):
        grading.build_actual_player_outcomes(
            batch_manifest=evidence["batch_manifest"],
            source_identity=evidence["source_identity"],
            rows=rows,
        )


def test_content_identity_and_self_hash_tampering_fail_closed(
    evidence: dict[str, object],
) -> None:
    outcomes = deepcopy(evidence["actual_player_outcomes"])
    outcomes["rows"][0]["realized_score_micro"] += 1
    with pytest.raises(grading.CorpusRealizedGradingError, match="content SHA-256"):
        _grade(evidence, actual_player_outcomes=outcomes)

    result = _grade(evidence)
    result["coverage"]["complete"] = False
    with pytest.raises(grading.CorpusRealizedGradingError, match="self-hash"):
        grading.validate_realized_grade(result)


def test_outcome_stage_cannot_write_inside_outcome_blind_batch_namespace(
    evidence: dict[str, object],
) -> None:
    identity = dict(evidence["actual_player_outcomes_identity"])
    identity["uri"] = (
        f"{evidence['batch_manifest']['output_prefix']}realized/outcomes.json"
    )
    with pytest.raises(grading.CorpusRealizedGradingError, match="outside"):
        _grade(evidence, actual_player_outcomes_identity=identity)
