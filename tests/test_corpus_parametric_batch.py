"""Offline contract tests for the closed corpus parametric batch surface."""

from __future__ import annotations

from copy import deepcopy

import pytest

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
    result: dict[str, object] = {
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
        "effective_policy_inventory_sha256": "d" * 64,
        "effective_policy_rule_universe_sha256": "e" * 64,
        "effective_policy_inventory_source_set_sha256": "f" * 64,
        "effective_policy_classified_input_projection_sha256": "1" * 64,
        "world_schedule": _receipt("world-schedule", 4),
        "world_seed": 7331,
        "objective": _receipt("objective", 5),
        "solve_budget": {
            "solve_attempts_per_seed": 200,
            "worlds_per_block": 10_000,
            "solver_timeout_seconds": 600,
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
    return result


def _world_artifacts(task_index: int) -> dict[str, dict[str, object]]:
    return {
        role: _receipt(
            f"task-{task_index}-{role}", 70 + task_index * 10 + ordinal
        )
        for ordinal, role in enumerate(batch.TASK_WORLD_SOURCE_ROLES)
    }


def _tasks() -> list[dict[str, object]]:
    tasks = [
        {
            "task_index": 0,
            "slate_id": "2023-w1-main",
            "season": 2023,
            "week": 1,
            "result_receipt_uri": (
                "gs://test-bucket/batches/corpus-demo-v1/tasks/000.json"
            ),
            "variant_output_prefix": (
                "gs://test-bucket/batches/corpus-demo-v1/variants/task-000/"
            ),
            "world_artifact_receipts": _world_artifacts(0),
        },
        {
            "task_index": 1,
            "slate_id": "2023-w2-main",
            "season": 2023,
            "week": 2,
            "result_receipt_uri": (
                "gs://test-bucket/batches/corpus-demo-v1/tasks/001.json"
            ),
            "variant_output_prefix": (
                "gs://test-bucket/batches/corpus-demo-v1/variants/task-001/"
            ),
            "world_artifact_receipts": _world_artifacts(1),
        },
    ]
    for task in tasks:
        task["world_artifact_receipt_set_sha256"] = batch.canonical_sha256(
            task["world_artifact_receipts"]
        )
        task["artifact_source_authority_task_sha256"] = (
            str(5 + task["task_index"]) * 64
        )
    return tasks


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
        manifest,
        uri=manifest["manifest_uri"],
        generation="100",
    )


def _execution(task_index: int) -> dict[str, object]:
    return {
        "execution_id": "corpus-run-1",
        "execution_uid": "uid-corpus-run-1",
        "task_index": task_index,
        "attempt": 1,
        "retry_count": 0,
        "terminal_status": "succeeded",
        "terminal_receipt": _receipt(f"terminal-{task_index}", 20 + task_index),
    }


def _variant_results(
    manifest: dict[str, object], task_index: int,
) -> list[dict[str, object]]:
    prefix = manifest["tasks"][task_index]["variant_output_prefix"]
    rows: list[dict[str, object]] = []
    for parameter_set in manifest["parameter_sets"]:
        ordinal = parameter_set["ordinal"]
        parameter_set_id = parameter_set["parameter_set_id"]
        parameter_prefix = f"{prefix}{parameter_set_id}/"
        effective_policy = _receipt(
            f"policy-{task_index}-{ordinal}", 30 + task_index * 10 + ordinal
        )
        effective_policy["uri"] = f"{parameter_prefix}effective-policy.json"
        rows.append({
            "ordinal": ordinal,
            "parameter_set_id": parameter_set_id,
            "parameter_set_sha256": parameter_set["parameter_set_sha256"],
            "effective_policy_receipt": effective_policy,
            "result_object": {
                "uri": f"{parameter_prefix}result.json",
                "generation": str(50 + task_index * 10 + ordinal),
                "sha256": f"{(ordinal + 1) % 10}" * 64,
                "bytes": 1_000 + ordinal,
            },
        })
    return rows


def _task_result(manifest: dict[str, object], task_index: int) -> dict[str, object]:
    return batch.build_task_result_receipt(
        batch_manifest=manifest,
        batch_manifest_identity=_manifest_identity(manifest),
        task_index=task_index,
        execution=_execution(task_index),
        variant_results=_variant_results(manifest, task_index),
    )


def _retained_results(manifest: dict[str, object]) -> list[dict[str, object]]:
    retained = []
    for task_index, task in enumerate(manifest["tasks"]):
        receipt = _task_result(manifest, task_index)
        retained.append({
            "receipt": receipt,
            "object_identity": batch.object_identity_for_json(
                receipt,
                uri=task["result_receipt_uri"],
                generation=str(200 + task_index),
            ),
        })
    return retained


def test_spec_is_exactly_five_typed_fields_and_self_hashed() -> None:
    spec = batch.parameter_spec_manifest()

    assert [row["name"] for row in spec["parameters"]] == list(
        batch.PARAMETER_ORDER
    )
    assert [row["domain"] for row in spec["parameters"]] == [
        [0, 49_000],
        [0, 2],
        [0, 1],
        [False, True],
        [False, True],
    ]
    assert spec["parameter_schema_sha256"] == batch.PARAMETER_SCHEMA_SHA256
    assert batch.validate_parameter_spec_manifest(spec) == spec


def test_frozen_matrix_is_exactly_seven_complete_assignments() -> None:
    rows = batch.frozen_parameter_sets()

    assert len(rows) == 7
    assert tuple(row["parameter_set_id"] for row in rows) == (
        batch.PARAMETER_SET_ORDER
    )
    assert rows[0]["values"] == {
        "min_lineup_salary": 49_000,
        "qb_stack_min": 2,
        "bring_back_min": 1,
        "forbid_rb_vs_dst": True,
        "forbid_two_rb_same_team": True,
    }
    assert rows[-1]["values"] == {
        "min_lineup_salary": 0,
        "qb_stack_min": 0,
        "bring_back_min": 0,
        "forbid_rb_vs_dst": False,
        "forbid_two_rb_same_team": False,
    }
    assert rows[-1]["parameter_set_id"] == (
        "remove-all-five-shared-constraints"
    )
    assert "dk-classic-only" not in batch.PARAMETER_SET_ORDER
    assert all(batch.validate_parameter_set(row) == row for row in rows)


@pytest.mark.parametrize(
    "mutator, message",
    [
        (
            lambda values: values.pop("qb_stack_min"),
            "missing=.*qb_stack_min",
        ),
        (
            lambda values: values.update({"unregistered_env": 1}),
            "unknown=.*unregistered_env",
        ),
        (
            lambda values: values.update({"qb_stack_min": False}),
            "exact integer",
        ),
        (
            lambda values: values.update({"forbid_rb_vs_dst": 1}),
            "literal Boolean",
        ),
        (
            lambda values: values.update({"min_lineup_salary": "49000"}),
            "exact integer",
        ),
        (
            lambda values: values.update({"bring_back_min": 2}),
            "outside its frozen typed domain",
        ),
    ],
)
def test_parameter_values_have_no_defaults_coercion_or_unknown_keys(
    mutator: object, message: str,
) -> None:
    values = deepcopy(batch.frozen_parameter_sets()[0]["values"])
    mutator(values)

    with pytest.raises(batch.CorpusParametricBatchError, match=message):
        batch.validate_parameter_values(values)


def test_parameter_set_cannot_be_reassigned_even_with_a_recomputed_hash() -> None:
    row = deepcopy(batch.frozen_parameter_sets()[0])
    row["values"]["min_lineup_salary"] = 0
    body = {key: value for key, value in row.items() if key != "parameter_set_sha256"}
    row["parameter_set_sha256"] = batch.canonical_sha256(body)

    with pytest.raises(
        batch.CorpusParametricBatchError, match="frozen assignment"
    ):
        batch.validate_parameter_set(row)


def test_batch_manifest_binds_matrix_common_law_and_task_coverage() -> None:
    manifest = _manifest()
    replayed = batch.validate_batch_manifest(manifest)

    assert replayed == manifest
    assert replayed["estimand"] == batch.ESTIMAND
    assert replayed["publication_mode"] == "create_once"
    assert len(replayed["parameter_sets"]) == 7
    assert len(replayed["tasks"]) == 2
    assert replayed["output_prefix"].endswith(f"/{replayed['batch_id']}/")
    assert replayed["manifest_uri"] == (
        f"{replayed['output_prefix']}governance/batch-manifest.json"
    )
    assert replayed["create_once_prefix_claim_uri"] == (
        f"{replayed['output_prefix']}governance/prefix-claim.json"
    )
    assert replayed["common_law_sha256"] == batch.canonical_sha256(
        replayed["common_law"]
    )
    assert replayed["batch_manifest_sha256"] == batch.canonical_sha256({
        key: value
        for key, value in replayed.items()
        if key != "batch_manifest_sha256"
    })
    assert _manifest()["batch_manifest_sha256"] == replayed[
        "batch_manifest_sha256"
    ]


@pytest.mark.parametrize(
    "mutator, message",
    [
        (
            lambda law: law.pop("selector"),
            "missing=.*selector",
        ),
        (
            lambda law: law.update({"arbitrary_env": _receipt("bad", 99)}),
            "unknown=.*arbitrary_env",
        ),
        (
            lambda law: law.update({"worker_environment_inheritance": 0}),
            "literal Boolean",
        ),
        (
            lambda law: law["solve_budget"].update({
                "solve_attempts_per_seed": 199
            }),
            "200 visits per world-artifact block",
        ),
        (
            lambda law: law["solve_budget"].update({"worlds_per_block": 9_999}),
            "10,000 source worlds per block",
        ),
        (
            lambda law: law["solve_budget"].update({
                "solver_timeout_seconds": 121
            }),
            "one-monotonic-total-deadline law",
        ),
        (
            lambda law: law["solve_budget"].update({
                "candidate_entry_budget": 999
            }),
            "maximum visit outputs before first-occurrence deduplication",
        ),
        (
            lambda law: law["solve_budget"].update({"selected_entry_budget": 79}),
            "must equal exact-80",
        ),
        (
            lambda law: law["solver"].update({"exact_mode": False}),
            "exact_mode must be true",
        ),
        (
            lambda law: law.update({
                "retry_law": {"max_attempts_per_task": 2, "max_retries": 0}
            }),
            "exactly one attempt and zero retries",
        ),
        (
            lambda law: law.update({
                "retry_law": {"max_attempts_per_task": 2, "max_retries": 1}
            }),
            "exactly one attempt and zero retries",
        ),
    ],
)
def test_common_law_is_complete_typed_and_closed(
    mutator: object, message: str,
) -> None:
    law = _common_law()
    mutator(law)

    with pytest.raises(batch.CorpusParametricBatchError, match=message):
        batch.normalize_common_law(law)


def test_common_source_and_inventory_roles_and_hashes_are_exact() -> None:
    law = batch.normalize_common_law(_common_law())

    assert law["solve_budget"] == {
        "solve_attempts_per_seed": batch.SOLVE_ATTEMPTS_PER_BLOCK,
        "worlds_per_block": batch.WORLDS_PER_BLOCK,
        "solver_timeout_seconds": batch.SOLVER_TIMEOUT_SECONDS,
        "candidate_entry_budget": batch.MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION,
        "selected_entry_budget": batch.SELECTED_ENTRY_BUDGET,
    }
    assert batch.SOLVER_TIMEOUT_LAW == (
        "one monotonic total deadline per parameter-set visit across all "
        "solver stages"
    )
    assert tuple(law["source_receipts"]) == batch.SOURCE_RECEIPT_ROLES
    assert law["source_receipt_set_sha256"] == batch.canonical_sha256(
        law["source_receipts"]
    )
    assert law["later_source_freeze_manifest_sha256"] == "9" * 64
    assert law["later_source_freeze_manifest_sha256"] != law[
        "source_receipts"
    ]["later_source_freeze"]["sha256"]
    assert law["artifact_source_authority_completion"] == _receipt(
        "artifact-source-authority-completion", 14
    )
    assert law["artifact_source_authority_completion_sha256"] == "2" * 64
    assert law["artifact_source_authority_completion_sha256"] != law[
        "artifact_source_authority_completion"
    ]["sha256"]
    assert set(law) >= {
        "effective_policy_inventory_identity",
        "effective_policy_inventory_sha256",
        "effective_policy_rule_universe_sha256",
        "effective_policy_inventory_source_set_sha256",
        "effective_policy_classified_input_projection_sha256",
    }


@pytest.mark.parametrize(
    "mutator, message",
    [
        (
            lambda law: law["source_receipts"].pop(
                "later_source_freeze"
            ),
            "missing=.*later_source_freeze",
        ),
        (
            lambda law: law["source_receipts"].update({
                "projection_table": _receipt("projection-table", 91)
            }),
            "unknown=.*projection_table",
        ),
        (
            lambda law: law.update({"source_receipts": [_receipt("old-list", 92)]}),
            "must be an object",
        ),
        (
            lambda law: law.update({"source_receipt_set_sha256": "0" * 64}),
            "source-receipt-set hash differs",
        ),
        (
            lambda law: law.update({
                "later_source_freeze_manifest_sha256": law[
                    "source_receipts"
                ]["later_source_freeze"]["sha256"]
            }),
            "must not be conflated",
        ),
        (
            lambda law: law.update({
                "later_source_freeze_manifest_sha256": "A" * 64
            }),
            "lowercase SHA-256",
        ),
        (
            lambda law: law.pop("artifact_source_authority_completion"),
            "missing=.*artifact_source_authority_completion",
        ),
        (
            lambda law: law.update({
                "artifact_source_authority_completion_sha256": law[
                    "artifact_source_authority_completion"
                ]["sha256"]
            }),
            "must not be conflated",
        ),
        (
            lambda law: law.update({
                "artifact_source_authority_completion_sha256": True
            }),
            "lowercase SHA-256",
        ),
        (
            lambda law: law["artifact_source_authority_completion"].update({
                "uri": law["source_receipts"]["later_source_freeze"]["uri"]
            }),
            "URI overlaps a common source",
        ),
        (
            lambda law: law["effective_policy_inventory_identity"].update({
                "generation": "0"
            }),
            "positive decimal string",
        ),
        (
            lambda law: law.update({
                "effective_policy_classified_input_projection_sha256": True
            }),
            "lowercase SHA-256",
        ),
    ],
)
def test_common_source_and_inventory_poison_fails_closed(
    mutator: object, message: str,
) -> None:
    law = _common_law()
    mutator(law)

    with pytest.raises(batch.CorpusParametricBatchError, match=message):
        batch.normalize_common_law(law)


def test_task_world_artifact_roles_and_hash_are_exact() -> None:
    manifest = _manifest()

    for task in manifest["tasks"]:
        assert tuple(task["world_artifact_receipts"]) == (
            batch.TASK_WORLD_SOURCE_ROLES
        )
        assert task["world_artifact_receipt_set_sha256"] == (
            batch.canonical_sha256(task["world_artifact_receipts"])
        )
        assert len(task["artifact_source_authority_task_sha256"]) == 64


@pytest.mark.parametrize(
    "mutator, message",
    [
        (
            lambda task: task["world_artifact_receipts"].pop(
                "world_artifact_r4"
            ),
            "missing=.*world_artifact_r4",
        ),
        (
            lambda task: task["world_artifact_receipts"].update({
                "world_artifact_r5": _receipt("r5", 93)
            }),
            "unknown=.*world_artifact_r5",
        ),
        (
            lambda task: task.update({
                "world_artifact_receipt_set_sha256": "0" * 64
            }),
            "world-artifact-set hash differs",
        ),
        (
            lambda task: task.pop("artifact_source_authority_task_sha256"),
            "missing=.*artifact_source_authority_task_sha256",
        ),
        (
            lambda task: task.update({
                "artifact_source_authority_task_sha256": True
            }),
            "lowercase SHA-256",
        ),
        (
            lambda task: task["world_artifact_receipts"][
                "world_artifact_r1"
            ].update({
                "uri": task["world_artifact_receipts"]["world_artifact_r0"][
                    "uri"
                ],
                "generation": "999",
            }),
            "world artifact URIs repeat",
        ),
    ],
)
def test_task_world_artifact_poison_fails_closed(
    mutator: object, message: str,
) -> None:
    tasks = _tasks()
    mutator(tasks[0])

    with pytest.raises(batch.CorpusParametricBatchError, match=message):
        batch.build_batch_manifest(
            batch_id="corpus-demo-v1",
            created_at_utc="2026-08-21T12:00:00Z",
            output_prefix="gs://test-bucket/batches/corpus-demo-v1/",
            common_law=_common_law(),
            tasks=tasks,
        )


def test_batch_rejects_missing_reordered_or_drifted_nested_content() -> None:
    missing = _manifest()
    missing["parameter_sets"].pop()
    with pytest.raises(batch.CorpusParametricBatchError, match="exactly seven"):
        batch.validate_batch_manifest(missing)

    reordered = _manifest()
    reordered["parameter_sets"][0], reordered["parameter_sets"][1] = (
        reordered["parameter_sets"][1],
        reordered["parameter_sets"][0],
    )
    with pytest.raises(batch.CorpusParametricBatchError, match="fixed order"):
        batch.validate_batch_manifest(reordered)

    drifted = _manifest()
    drifted["common_law"]["world_seed"] = 0
    with pytest.raises(batch.CorpusParametricBatchError, match="common-law hash"):
        batch.validate_batch_manifest(drifted)


def test_output_prefix_is_deterministically_coupled_to_batch_id() -> None:
    with pytest.raises(
        batch.CorpusParametricBatchError, match="end with the exact batch_id"
    ):
        batch.build_batch_manifest(
            batch_id="corpus-demo-v1",
            created_at_utc="2026-08-21T12:00:00Z",
            output_prefix="gs://test-bucket/batches/some-other-batch/",
            common_law=_common_law(),
            tasks=_tasks(),
        )


@pytest.mark.parametrize(
    "field, poison, message",
    [
        (
            "manifest_uri",
            "gs://test-bucket/batches/corpus-demo-v1/manifest.json",
            "manifest URI differs from its deterministic path",
        ),
        (
            "create_once_prefix_claim_uri",
            "gs://test-bucket/batches/corpus-demo-v1/prefix-claim.json",
            "prefix-claim URI differs from its deterministic path",
        ),
    ],
)
def test_governance_uris_are_exact(field: str, poison: str, message: str) -> None:
    manifest = _manifest()
    manifest[field] = poison

    with pytest.raises(batch.CorpusParametricBatchError, match=message):
        batch.validate_batch_manifest(manifest)


def test_manifest_object_identity_must_use_exact_governance_uri() -> None:
    manifest = _manifest()
    identity = batch.object_identity_for_json(
        manifest,
        uri="gs://test-bucket/batches/corpus-demo-v1/manifest.json",
        generation="100",
    )

    with pytest.raises(
        batch.CorpusParametricBatchError, match="identity URI differs"
    ):
        batch.build_task_request(
            batch_manifest=manifest,
            batch_manifest_identity=identity,
            task_index=0,
        )


@pytest.mark.parametrize(
    "mutator, message",
    [
        (
            lambda tasks, law: law["source_receipts"][
                "later_source_freeze"
            ].update({
                "uri": (
                    "gs://test-bucket/batches/corpus-demo-v1/inputs/freeze.json"
                )
            }),
            "source/common artifact namespace overlaps",
        ),
        (
            lambda tasks, law: law["objective"].update({
                "uri": (
                    "gs://test-bucket/batches/corpus-demo-v1/inputs/objective.json"
                )
            }),
            "source/common artifact namespace overlaps",
        ),
        (
            lambda tasks, law: law[
                "effective_policy_inventory_identity"
            ].update({
                "uri": (
                    "gs://test-bucket/batches/corpus-demo-v1/inputs/policy.json"
                )
            }),
            "source/common artifact namespace overlaps",
        ),
        (
            lambda tasks, law: law[
                "artifact_source_authority_completion"
            ].update({
                "uri": (
                    "gs://test-bucket/batches/corpus-demo-v1/inputs/"
                    "source-authority.json"
                )
            }),
            "source/common artifact namespace overlaps",
        ),
        (
            lambda tasks, law: tasks[0]["world_artifact_receipts"][
                "world_artifact_r0"
            ].update({
                "uri": (
                    "gs://test-bucket/batches/corpus-demo-v1/inputs/world.npz"
                )
            }),
            "world artifact namespace overlaps",
        ),
        (
            lambda tasks, law: tasks[0].update({
                "result_receipt_uri": (
                    "gs://test-bucket/batches/corpus-demo-v1/"
                    "governance/task-result.json"
                )
            }),
            "task artifact namespace overlaps batch governance",
        ),
    ],
)
def test_governance_task_and_input_namespaces_cannot_overlap(
    mutator: object, message: str,
) -> None:
    tasks = _tasks()
    law = _common_law()
    mutator(tasks, law)
    if isinstance(law["source_receipts"], dict):
        law["source_receipt_set_sha256"] = batch.canonical_sha256(
            law["source_receipts"]
        )
    if isinstance(tasks[0]["world_artifact_receipts"], dict):
        tasks[0]["world_artifact_receipt_set_sha256"] = batch.canonical_sha256(
            tasks[0]["world_artifact_receipts"]
        )

    with pytest.raises(batch.CorpusParametricBatchError, match=message):
        batch.build_batch_manifest(
            batch_id="corpus-demo-v1",
            created_at_utc="2026-08-21T12:00:00Z",
            output_prefix="gs://test-bucket/batches/corpus-demo-v1/",
            common_law=law,
            tasks=tasks,
        )


@pytest.mark.parametrize(
    "field, poison",
    [
        (
            "result_receipt_uri",
            "gs://test-bucket/batches/other/tasks/000.json",
        ),
        (
            "variant_output_prefix",
            "gs://test-bucket/batches/other/variants/task-000/",
        ),
    ],
)
def test_task_paths_must_be_strictly_under_batch_output_prefix(
    field: str, poison: str,
) -> None:
    tasks = _tasks()
    tasks[0][field] = poison

    with pytest.raises(
        batch.CorpusParametricBatchError,
        match="strictly under the batch output prefix",
    ):
        batch.build_batch_manifest(
            batch_id="corpus-demo-v1",
            created_at_utc="2026-08-21T12:00:00Z",
            output_prefix="gs://test-bucket/batches/corpus-demo-v1/",
            common_law=_common_law(),
            tasks=tasks,
        )


def test_task_variant_prefixes_may_not_be_nested() -> None:
    tasks = _tasks()
    tasks[0]["variant_output_prefix"] = (
        "gs://test-bucket/batches/corpus-demo-v1/variants/"
    )

    with pytest.raises(batch.CorpusParametricBatchError, match="prefixes overlap"):
        batch.build_batch_manifest(
            batch_id="corpus-demo-v1",
            created_at_utc="2026-08-21T12:00:00Z",
            output_prefix="gs://test-bucket/batches/corpus-demo-v1/",
            common_law=_common_law(),
            tasks=tasks,
        )


def test_task_result_receipt_may_not_cross_into_another_variant_prefix() -> None:
    tasks = _tasks()
    tasks[0]["result_receipt_uri"] = (
        f"{tasks[1]['variant_output_prefix']}incumbent/result.json"
    )

    with pytest.raises(
        batch.CorpusParametricBatchError,
        match="crosses into a variant output prefix",
    ):
        batch.build_batch_manifest(
            batch_id="corpus-demo-v1",
            created_at_utc="2026-08-21T12:00:00Z",
            output_prefix="gs://test-bucket/batches/corpus-demo-v1/",
            common_law=_common_law(),
            tasks=tasks,
        )


def test_task_request_contains_only_pinned_manifest_identity_and_index() -> None:
    manifest = _manifest()
    identity = _manifest_identity(manifest)
    request = batch.build_task_request(
        batch_manifest=manifest,
        batch_manifest_identity=identity,
        task_index=1,
    )

    assert set(request) == {
        "schema_version",
        "batch_manifest_identity",
        "task_index",
        "task_request_sha256",
    }
    assert batch.validate_task_request(request) == request
    parsed_request, parsed_manifest = batch.bind_task_request_to_manifest(
        request, batch.canonical_json_bytes(manifest)
    )
    assert parsed_request == request
    assert parsed_manifest == manifest


def test_task_request_rejects_unpinned_or_extra_input() -> None:
    manifest = _manifest()
    request = batch.build_task_request(
        batch_manifest=manifest,
        batch_manifest_identity=_manifest_identity(manifest),
        task_index=0,
    )
    request["ENV"] = {"QB_STACK_MIN": "0"}
    with pytest.raises(batch.CorpusParametricBatchError, match="unknown=.*ENV"):
        batch.validate_task_request(request)

    bad_identity = _manifest_identity(manifest)
    bad_identity["sha256"] = "f" * 64
    with pytest.raises(batch.CorpusParametricBatchError, match="SHA-256 differs"):
        batch.build_task_request(
            batch_manifest=manifest,
            batch_manifest_identity=bad_identity,
            task_index=0,
        )


def test_canonical_parser_rejects_aliases_duplicates_and_format_drift() -> None:
    with pytest.raises(batch.CorpusParametricBatchError, match="duplicate key"):
        batch.parse_canonical_json_bytes(b'{"a":1,"a":2}', label="fixture")
    with pytest.raises(batch.CorpusParametricBatchError, match="non-finite"):
        batch.parse_canonical_json_bytes(b'{"a":NaN}', label="fixture")
    with pytest.raises(batch.CorpusParametricBatchError, match="not canonical"):
        batch.parse_canonical_json_bytes(b'{"a": 1}', label="fixture")


def test_successful_task_result_binds_every_common_identity_and_variant() -> None:
    manifest = _manifest()
    receipt = _task_result(manifest, 0)

    assert manifest["schema_version"] == "corpus-parametric-batch-manifest-v2"
    assert receipt["schema_version"] == "corpus-parametric-task-result-v2"
    assert receipt["batch_manifest_sha256"] == manifest["batch_manifest_sha256"]
    assert receipt["common_law_sha256"] == manifest["common_law_sha256"]
    assert receipt["code_source"] == manifest["common_law"]["code_source"]
    assert receipt["immutable_image"] == manifest["common_law"]["immutable_image"]
    assert receipt["source_receipts"] == manifest["common_law"]["source_receipts"]
    assert receipt["source_receipt_set_sha256"] == manifest["common_law"][
        "source_receipt_set_sha256"
    ]
    assert receipt["later_source_freeze_manifest_sha256"] == manifest[
        "common_law"
    ]["later_source_freeze_manifest_sha256"]
    assert receipt["artifact_source_authority_completion"] == manifest[
        "common_law"
    ]["artifact_source_authority_completion"]
    assert receipt["artifact_source_authority_completion_sha256"] == manifest[
        "common_law"
    ]["artifact_source_authority_completion_sha256"]
    assert receipt["effective_policy_inventory_identity"] == manifest[
        "common_law"
    ]["effective_policy_inventory_identity"]
    assert receipt["effective_policy_inventory_sha256"] == manifest[
        "common_law"
    ]["effective_policy_inventory_sha256"]
    assert receipt["effective_policy_rule_universe_sha256"] == manifest[
        "common_law"
    ]["effective_policy_rule_universe_sha256"]
    assert receipt["effective_policy_inventory_source_set_sha256"] == manifest[
        "common_law"
    ]["effective_policy_inventory_source_set_sha256"]
    assert receipt[
        "effective_policy_classified_input_projection_sha256"
    ] == manifest["common_law"][
        "effective_policy_classified_input_projection_sha256"
    ]
    assert receipt["world_artifact_receipts"] == manifest["tasks"][0][
        "world_artifact_receipts"
    ]
    assert receipt["world_artifact_receipt_set_sha256"] == manifest["tasks"][0][
        "world_artifact_receipt_set_sha256"
    ]
    assert receipt["artifact_source_authority_task_sha256"] == manifest[
        "tasks"
    ][0]["artifact_source_authority_task_sha256"]
    assert receipt["world_schedule"] == manifest["common_law"]["world_schedule"]
    assert receipt["solver"] == manifest["common_law"]["solver"]
    assert len(receipt["variant_results"]) == 7
    for row in receipt["variant_results"]:
        expected_prefix = (
            f"{manifest['tasks'][0]['variant_output_prefix']}"
            f"{row['parameter_set_id']}/"
        )
        assert row["effective_policy_receipt"]["uri"] == (
            f"{expected_prefix}effective-policy.json"
        )
        assert row["result_object"]["uri"] == f"{expected_prefix}result.json"
    assert batch.validate_task_result_receipt(
        receipt,
        batch_manifest=manifest,
        batch_manifest_identity=_manifest_identity(manifest),
    ) == receipt


@pytest.mark.parametrize(
    "mutator, message",
    [
        (
            lambda rows, execution, manifest: rows.pop(),
            "exactly seven",
        ),
        (
            lambda rows, execution, manifest: rows[1].update({
                "parameter_set_sha256": rows[0]["parameter_set_sha256"]
            }),
            "parameter-set binding differs",
        ),
        (
            lambda rows, execution, manifest: rows[0]["result_object"].update({
                "uri": "gs://test-bucket/outside/00.json"
            }),
            "outside its frozen output prefix",
        ),
        (
            lambda rows, execution, manifest: rows[0][
                "effective_policy_receipt"
            ].update({"uri": "gs://test-bucket/outside/policy.json"}),
            "outside its frozen output prefix",
        ),
        (
            lambda rows, execution, manifest: rows[1]["result_object"].update({
                "uri": rows[0]["result_object"]["uri"]
            }),
            "URIs repeat",
        ),
        (
            lambda rows, execution, manifest: rows[1][
                "effective_policy_receipt"
            ].update({"uri": rows[0]["effective_policy_receipt"]["uri"]}),
            "URIs repeat",
        ),
        (
            lambda rows, execution, manifest: rows[0]["result_object"].update({
                "uri": rows[1]["result_object"]["uri"]
            }),
            "deterministic path",
        ),
        (
            lambda rows, execution, manifest: execution.update({
                "terminal_status": "failed"
            }),
            "terminal succeeded",
        ),
        (
            lambda rows, execution, manifest: execution.update({
                "attempt": 2, "retry_count": 1
            }),
            "exceeds the frozen retry law",
        ),
    ],
)
def test_task_result_rejects_partial_drifted_or_failed_rows(
    mutator: object, message: str,
) -> None:
    manifest = _manifest()
    rows = _variant_results(manifest, 0)
    execution = _execution(0)
    mutator(rows, execution, manifest)

    with pytest.raises(batch.CorpusParametricBatchError, match=message):
        batch.build_task_result_receipt(
            batch_manifest=manifest,
            batch_manifest_identity=_manifest_identity(manifest),
            task_index=0,
            execution=execution,
            variant_results=rows,
        )


def test_result_replay_rejects_common_law_field_drift_even_if_rehashed() -> None:
    manifest = _manifest()
    receipt = _task_result(manifest, 0)
    receipt["later_source_freeze_manifest_sha256"] = "8" * 64
    body = {
        key: value for key, value in receipt.items() if key != "task_result_sha256"
    }
    receipt["task_result_sha256"] = batch.canonical_sha256(body)

    with pytest.raises(batch.CorpusParametricBatchError, match="binding differs"):
        batch.validate_task_result_receipt(
            receipt,
            batch_manifest=manifest,
            batch_manifest_identity=_manifest_identity(manifest),
        )


@pytest.mark.parametrize(
    "field",
    [
        "artifact_source_authority_completion_sha256",
        "artifact_source_authority_task_sha256",
        "world_artifact_receipt_set_sha256",
    ],
)
def test_result_replay_rejects_source_authority_binding_drift(
    field: str,
) -> None:
    manifest = _manifest()
    receipt = _task_result(manifest, 0)
    receipt[field] = "7" * 64
    body = {
        key: value for key, value in receipt.items() if key != "task_result_sha256"
    }
    receipt["task_result_sha256"] = batch.canonical_sha256(body)

    with pytest.raises(batch.CorpusParametricBatchError, match="binding differs"):
        batch.validate_task_result_receipt(
            receipt,
            batch_manifest=manifest,
            batch_manifest_identity=_manifest_identity(manifest),
        )


def test_result_replay_rejects_classified_projection_drift_if_rehashed() -> None:
    manifest = _manifest()
    receipt = _task_result(manifest, 0)
    receipt["effective_policy_classified_input_projection_sha256"] = "2" * 64
    body = {
        key: value for key, value in receipt.items() if key != "task_result_sha256"
    }
    receipt["task_result_sha256"] = batch.canonical_sha256(body)

    with pytest.raises(batch.CorpusParametricBatchError, match="binding differs"):
        batch.validate_task_result_receipt(
            receipt,
            batch_manifest=manifest,
            batch_manifest_identity=_manifest_identity(manifest),
        )


def test_completion_requires_the_exact_task_by_seven_variant_matrix() -> None:
    manifest = _manifest()
    retained = _retained_results(manifest)
    completion = batch.build_batch_completion_receipt(
        batch_manifest=manifest,
        batch_manifest_identity=_manifest_identity(manifest),
        retained_task_results=retained,
    )

    assert completion["coverage"] == {
        "task_count": 2,
        "parameter_set_count": 7,
        "matrix_cell_count": 14,
        "complete": True,
    }
    assert completion["schema_version"] == (
        "corpus-parametric-batch-completion-v2"
    )
    assert completion["later_source_freeze_manifest_sha256"] == manifest[
        "common_law"
    ]["later_source_freeze_manifest_sha256"]
    assert completion[
        "effective_policy_classified_input_projection_sha256"
    ] == manifest["common_law"][
        "effective_policy_classified_input_projection_sha256"
    ]
    assert completion["artifact_source_authority_completion"] == manifest[
        "common_law"
    ]["artifact_source_authority_completion"]
    assert completion["artifact_source_authority_completion_sha256"] == manifest[
        "common_law"
    ]["artifact_source_authority_completion_sha256"]
    assert len(completion["task_results"]) == 2
    assert [
        row["world_artifact_receipt_set_sha256"]
        for row in completion["task_results"]
    ] == [
        task["world_artifact_receipt_set_sha256"]
        for task in manifest["tasks"]
    ]
    assert [
        row["artifact_source_authority_task_sha256"]
        for row in completion["task_results"]
    ] == [
        task["artifact_source_authority_task_sha256"]
        for task in manifest["tasks"]
    ]
    assert batch.validate_batch_completion_receipt(
        completion,
        batch_manifest=manifest,
        batch_manifest_identity=_manifest_identity(manifest),
        retained_task_results=retained,
    ) == completion


def test_completion_replay_rejects_freeze_manifest_hash_drift() -> None:
    manifest = _manifest()
    retained = _retained_results(manifest)
    completion = batch.build_batch_completion_receipt(
        batch_manifest=manifest,
        batch_manifest_identity=_manifest_identity(manifest),
        retained_task_results=retained,
    )
    completion["later_source_freeze_manifest_sha256"] = "8" * 64
    body = {
        key: value
        for key, value in completion.items()
        if key != "batch_completion_sha256"
    }
    completion["batch_completion_sha256"] = batch.canonical_sha256(body)

    with pytest.raises(batch.CorpusParametricBatchError, match="differs"):
        batch.validate_batch_completion_receipt(
            completion,
            batch_manifest=manifest,
            batch_manifest_identity=_manifest_identity(manifest),
            retained_task_results=retained,
        )


def test_completion_replay_rejects_source_authority_hash_drift() -> None:
    manifest = _manifest()
    retained = _retained_results(manifest)
    completion = batch.build_batch_completion_receipt(
        batch_manifest=manifest,
        batch_manifest_identity=_manifest_identity(manifest),
        retained_task_results=retained,
    )
    completion["artifact_source_authority_completion_sha256"] = "7" * 64
    body = {
        key: value
        for key, value in completion.items()
        if key != "batch_completion_sha256"
    }
    completion["batch_completion_sha256"] = batch.canonical_sha256(body)

    with pytest.raises(batch.CorpusParametricBatchError, match="differs"):
        batch.validate_batch_completion_receipt(
            completion,
            batch_manifest=manifest,
            batch_manifest_identity=_manifest_identity(manifest),
            retained_task_results=retained,
        )


def test_completion_rejects_missing_reordered_or_wrong_object_receipts() -> None:
    manifest = _manifest()
    retained = _retained_results(manifest)
    with pytest.raises(batch.CorpusParametricBatchError, match="cover every"):
        batch.build_batch_completion_receipt(
            batch_manifest=manifest,
            batch_manifest_identity=_manifest_identity(manifest),
            retained_task_results=retained[:-1],
        )

    reordered = list(reversed(_retained_results(manifest)))
    with pytest.raises(batch.CorpusParametricBatchError, match="fixed task order"):
        batch.build_batch_completion_receipt(
            batch_manifest=manifest,
            batch_manifest_identity=_manifest_identity(manifest),
            retained_task_results=reordered,
        )

    wrong_uri = _retained_results(manifest)
    wrong_uri[0]["object_identity"]["uri"] = (
        "gs://test-bucket/batches/corpus-demo-v1/tasks/wrong.json"
    )
    with pytest.raises(batch.CorpusParametricBatchError, match="URI differs"):
        batch.build_batch_completion_receipt(
            batch_manifest=manifest,
            batch_manifest_identity=_manifest_identity(manifest),
            retained_task_results=wrong_uri,
        )

    wrong_bytes = _retained_results(manifest)
    wrong_bytes[0]["object_identity"]["bytes"] += 1
    with pytest.raises(batch.CorpusParametricBatchError, match="byte count differs"):
        batch.build_batch_completion_receipt(
            batch_manifest=manifest,
            batch_manifest_identity=_manifest_identity(manifest),
            retained_task_results=wrong_bytes,
        )
