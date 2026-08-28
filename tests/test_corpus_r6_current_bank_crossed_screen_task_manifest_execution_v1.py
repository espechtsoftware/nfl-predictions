from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as manifest,
)


def _identity(uri: str, body: object, *, generation: str = "7") -> dict[str, object]:
    raw = contract.canonical_json_bytes_v1(body)
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _rehash(value: dict[str, object], field: str) -> None:
    value.pop(field, None)
    value[field] = contract.canonical_sha256_v1(value)


def test_pre_design_authorization_exact_stream_proof_budget_for_all_layers() -> None:
    authorization = manifest.build_pre_design_run_authorization_v1(
        output_prefix=contract.OUTPUT_NAMESPACE + "controller-focused/",
        code_commit="a" * 40,
        image_digest="sha256:" + "b" * 64,
        reused_job_name="controller-focused-job",
    )
    assert manifest.validate_pre_design_run_authorization_v1(
        authorization
    ) == authorization
    budget = authorization["dispatcher_resource_budget"]
    assert budget["external_dispatcher_process_count"] == 220
    assert budget["maximum_processes_per_dispatcher_task"] == 4
    assert [
        row["simultaneous_process_tree_maximum"]
        for row in budget["simultaneous_process_tree_by_layer"]
    ] == [2, 4, 2, 2, 4, 2, 2, 2]
    assert budget["simultaneous_process_tree_by_layer_sha256"] == (
        contract.canonical_sha256_v1(
            budget["simultaneous_process_tree_by_layer"]
        )
    )
    assert budget["maximum_dispatcher_wall_seconds"] == (
        manifest.MAXIMUM_DISPATCHER_WALL_SECONDS
    )
    assert budget["maximum_exact_identity_proofs_per_dispatcher"] == (
        manifest.MAXIMUM_DISPATCHER_EXACT_IDENTITY_PROOFS
    )
    assert budget["maximum_streamed_bytes_per_exact_identity_proof"] == (
        manifest.MAXIMUM_DISPATCHER_EXACT_PROOF_BYTES
    )
    assert budget["cloud_run_container_resource_limits"] == {
        "cpu": manifest.FIXED_CLOUD_RUN_CPU_LIMIT,
        "memory": manifest.FIXED_CLOUD_RUN_MEMORY_LIMIT,
    }
    assert budget["cloud_run_container_working_directory"] == ""
    assert budget["cloud_run_container_volume_mounts"] == []
    assert budget["cloud_run_task_template_volumes"] == []
    assert budget["publisher_maximum_single_scientific_body_bytes"] == 768_000_000
    assert budget["publisher_maximum_peak_rss_bytes"] == 24 * 1024**3
    assert budget["cloud_run_container_memory_bytes"] == 32 * 1024**3
    assert budget["publisher_provider_memory_margin_bytes"] == 8 * 1024**3
    assert budget["publisher_peak_rss_strictly_below_provider_memory"] is True
    publisher_precharge = budget["publisher_resource_precharge_authority"]
    assert publisher_precharge == {
        "maximum_single_scientific_body_bytes": 768_000_000,
        "maximum_peak_rss_bytes": 24 * 1024**3,
        "maximum_address_space_bytes": 24 * 1024**3,
        "required_cloud_run_container_memory_bytes": 32 * 1024**3,
        "baseline_rss_reserve_bytes": 2 * 1024**3,
        "single_body_raw_reserve_bytes": 768_000_000,
        "single_body_decode_expansion_multiplier": 16,
        "single_body_decode_expansion_reserve_bytes": 12_288_000_000,
        "compact_state_expansion_multiplier": 8,
        "compact_state_expansion_reserve_bytes": 512_000_000,
        "derivation_output_reserve_bytes": 4 * 1024**3,
        "worst_case_rss_bytes": 20_010_450_944,
        "worst_case_rss_within_process_limit": True,
        "process_limit_strictly_below_provider_memory": True,
    }
    assert budget["publisher_resource_precharge_authority_sha256"] == (
        contract.canonical_sha256_v1(publisher_precharge)
    )
    terminal_budget = authorization["host_terminal_observation_budget"]
    assert terminal_budget["resolver_role"] == "host-finalizer-only"
    assert terminal_budget["uri_source"] == (
        "exact-manifest-task-terminal-evidence-uris"
    )
    assert terminal_budget["maximum_resolution_count_per_layer"] == 54
    assert terminal_budget["total_resolution_count"] == 220
    assert [
        row["task_count"]
        for row in terminal_budget["per_layer_resolution_authorities"]
    ] == [1, 54, 54, 1, 54, 54, 1, 1]
    assert terminal_budget["current_generation_metadata_lookup_per_uri"] == 1
    assert terminal_budget["immediate_generation_pin_required"] is True
    assert terminal_budget["generation_exact_hash_read_required"] is True
    assert terminal_budget["listing_allowed"] is False
    assert terminal_budget["logs_allowed"] is False
    assert terminal_budget["scientific_output_resolution_allowed"] is False
    assert authorization["host_terminal_observation_budget_sha256"] == (
        contract.canonical_sha256_v1(terminal_budget)
    )
    rows = budget["streamed_publication_proof_budgets"]
    assert [row["task_count"] for row in rows] == [1, 54, 54, 1, 54, 54, 1, 1]
    assert [row["layer_output_proof_count"] for row in rows] == [
        54, 54, 54, 1, 54, 54, 2, 1,
    ]
    assert rows[0]["output_proof_counts_by_task"] == [54]
    assert rows[0]["streamed_byte_ceilings_by_task"] == [54 * 256_000_000]
    assert rows[1]["streamed_byte_ceilings_by_task"] == [32_000_000] * 54
    assert rows[4]["streamed_byte_ceilings_by_task"] == [96_000_000] * 54
    assert rows[5]["streamed_byte_ceilings_by_task"] == [768_000_000] * 54
    assert rows[6]["streamed_byte_ceilings_by_task"] == [272_000_000]

    drifted = deepcopy(authorization)
    drifted_budget = drifted["dispatcher_resource_budget"]
    drifted_budget["maximum_exact_identity_proofs_per_dispatcher"] = 65
    drifted["dispatcher_resource_budget_sha256"] = contract.canonical_sha256_v1(
        drifted_budget
    )
    _rehash(drifted, "pre_design_run_authorization_sha256")
    with pytest.raises(
        manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error,
        match="canonical replay differs",
    ):
        manifest.validate_pre_design_run_authorization_v1(drifted)

    drifted = deepcopy(authorization)
    drifted_terminal_budget = drifted["host_terminal_observation_budget"]
    drifted_terminal_budget["listing_allowed"] = True
    drifted["host_terminal_observation_budget_sha256"] = (
        contract.canonical_sha256_v1(drifted_terminal_budget)
    )
    _rehash(drifted, "pre_design_run_authorization_sha256")
    with pytest.raises(
        manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error,
        match="canonical replay differs",
    ):
        manifest.validate_pre_design_run_authorization_v1(drifted)

    drifted = deepcopy(authorization)
    drifted_budget = drifted["dispatcher_resource_budget"]
    drifted_rows = drifted_budget["streamed_publication_proof_budgets"]
    drifted_rows[0]["layer_streamed_byte_ceiling"] -= 1
    drifted_budget["streamed_publication_proof_budgets_sha256"] = (
        contract.canonical_sha256_v1(drifted_rows)
    )
    drifted["dispatcher_resource_budget_sha256"] = contract.canonical_sha256_v1(
        drifted_budget
    )
    _rehash(drifted, "pre_design_run_authorization_sha256")
    with pytest.raises(
        manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error,
        match="canonical replay differs",
    ):
        manifest.validate_pre_design_run_authorization_v1(drifted)


def _observation_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    command = manifest.canonical_dispatcher_process_spec_v1()["command"]
    fake_manifest = {
        "task_manifest_sha256": "d" * 64,
        "task_count": 1,
        "code_commit": "a" * 40,
        "image_digest": "sha256:" + "b" * 64,
        "reused_job_name": "controller-focused-job",
        "dispatcher_process_spec": {"command": command},
        "task_bindings": [{
            "task_terminal_evidence_uri": (
                contract.OUTPUT_NAMESPACE
                + "controller-focused/authorities/task-terminal-evidence/"
                "projection/task-000.json"
            ),
        }],
    }
    manifest_identity = _identity(
        contract.OUTPUT_NAMESPACE
        + "controller-focused/authorities/task-manifests/00-projection.json",
        fake_manifest,
    )
    execution_name = (
        "projects/nfl-predictions-503414/locations/us-central1/jobs/"
        "controller-focused-job/executions/controller-focused-execution"
    )
    common_environment = {
        "R6_CURRENT_BANK_TASK_DISPATCH_ENABLED": "1",
        manifest.DISPATCH_MANIFEST_IDENTITY_ENV: (
            contract.canonical_json_bytes_v1(manifest_identity).decode("utf-8")
        ),
        manifest.DISPATCH_RESUME_AUTHORITY_IDENTITY_ENV: (
            manifest.ABSENT_RESUME_AUTHORITY_ENV_VALUE
        ),
        "GOOGLE_CLOUD_PROJECT": manifest.FIXED_GCP_PROJECT,
        "CODE_SHA": fake_manifest["code_commit"],
        "R6_RUNTIME_IMAGE_DIGEST": fake_manifest["image_digest"],
        "CLOUD_RUN_JOB": fake_manifest["reused_job_name"],
    }
    task_environment = {
        **common_environment,
        "CLOUD_RUN_EXECUTION": execution_name,
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
    }
    terminal_sha = "c" * 64
    terminal_identity = {
        "uri": contract.OUTPUT_NAMESPACE
        + "controller-focused/authorities/task-terminal-evidence/"
        "projection/task-000.json",
        "generation": "8",
        "sha256": terminal_sha,
        "bytes": 1,
    }
    terminal_evidence = {
        "task_completed": True,
        "cloud_execution_name": execution_name,
        "task_terminal_evidence_sha256": terminal_sha,
        "dispatcher_runtime_evidence": {
            "kernel_observed_command": command,
            "kernel_observed_command_sha256": contract.canonical_sha256_v1(command),
            "selected_environment": task_environment,
            "selected_environment_sha256": contract.canonical_sha256_v1(
                task_environment
            ),
        },
    }
    monkeypatch.setattr(
        manifest, "validate_task_manifest_v1", lambda value: dict(value)
    )
    monkeypatch.setattr(
        manifest,
        "_validated_terminal_record_v1",
        lambda *args, **kwargs: (terminal_evidence, terminal_identity),
    )
    provider_container = {
        "image": fake_manifest["image_digest"],
        "command": command[:1],
        "args": command[1:],
        "environment": common_environment,
        "working_dir": "",
        "volume_mounts": [],
        "resource_limits": {
            "cpu": manifest.FIXED_CLOUD_RUN_CPU_LIMIT,
            "memory": manifest.FIXED_CLOUD_RUN_MEMORY_LIMIT,
        },
    }
    execution_template = {
        "containers": [provider_container],
        "maximum_task_retries": 0,
        "timeout_seconds": manifest.MAXIMUM_DISPATCHER_WALL_SECONDS,
        "volumes": [],
    }
    overrides = {
        "container_overrides": [],
        "task_count": None,
        "timeout_seconds": None,
    }
    task_observations = [{
        "task_index": 0,
        "task_name": execution_name + "/tasks/0",
        "attempt": 0,
        "terminal_state": "SUCCEEDED",
        "exit_code": 0,
        "task_terminal_evidence_sha256": terminal_sha,
        "conditions": [{"type": "Completed", "state": "CONDITION_SUCCEEDED"}],
        "kernel_dispatcher_command": command,
        "kernel_dispatcher_command_sha256": contract.canonical_sha256_v1(command),
        "kernel_dispatcher_environment": task_environment,
        "kernel_dispatcher_environment_sha256": contract.canonical_sha256_v1(
            task_environment
        ),
    }]
    execution_conditions = [
        {"type": "Completed", "state": "CONDITION_SUCCEEDED"}
    ]
    source = {
        "schema_version": manifest.CLOUD_RUN_EXECUTION_OBSERVATION_SOURCE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "collection_semantics": (
            "cloud-run-v2-api-plus-dispatcher-kernel-observation"
        ),
        "manifest_identity": manifest_identity,
        "task_manifest_sha256": fake_manifest["task_manifest_sha256"],
        "project_id": manifest.FIXED_GCP_PROJECT,
        "location": manifest.FIXED_CLOUD_RUN_LOCATION,
        "job_name": fake_manifest["reused_job_name"],
        "job_uid": "job-uid",
        "job_generation": "9",
        "execution_name": execution_name,
        "execution_uid": "execution-uid",
        "execution_generation": "10",
        "code_commit": fake_manifest["code_commit"],
        "image_digest": fake_manifest["image_digest"],
        "job_dispatcher_command": command,
        "job_dispatcher_command_sha256": contract.canonical_sha256_v1(command),
        "job_dispatcher_environment": common_environment,
        "job_dispatcher_environment_sha256": contract.canonical_sha256_v1(
            common_environment
        ),
        "job_dispatcher_environment_semantics": (
            manifest._COMPLETE_PROVIDER_JOB_ENVIRONMENT_SEMANTICS
        ),
        "job_dispatcher_environment_complete_provider_spec": True,
        "job_dispatcher_environment_redirect_keys_absent": True,
        "provider_job_container_spec": provider_container,
        "provider_job_container_spec_sha256": contract.canonical_sha256_v1(
            provider_container
        ),
        "provider_execution_task_template": execution_template,
        "provider_execution_task_template_sha256": contract.canonical_sha256_v1(
            execution_template
        ),
        "provider_run_job_overrides": overrides,
        "provider_run_job_overrides_sha256": contract.canonical_sha256_v1(
            overrides
        ),
        "task_terminal_generation_resolution_scope": (
            manifest._task_terminal_generation_resolution_scope_v1(
                fake_manifest["task_bindings"]
            )
        ),
        "task_terminal_generation_resolution_scope_sha256": (
            contract.canonical_sha256_v1(
                manifest._task_terminal_generation_resolution_scope_v1(
                    fake_manifest["task_bindings"]
                )
            )
        ),
        "task_count": 1,
        "parallelism": 1,
        "maximum_task_retries": 0,
        "task_observations": task_observations,
        "task_observations_sha256": contract.canonical_sha256_v1(
            task_observations
        ),
        "execution_conditions": execution_conditions,
        "execution_conditions_sha256": contract.canonical_sha256_v1(
            execution_conditions
        ),
        "source_capture_complete": True,
        "provider_attestation_claimed": False,
    }
    _rehash(source, "cloud_run_execution_observation_source_sha256")
    return source, fake_manifest, manifest_identity


def test_observation_source_derives_no_execution_overrides_from_exact_subtrees(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, fake_manifest, manifest_identity = _observation_fixture(monkeypatch)
    assert manifest.validate_cloud_run_execution_observation_source_v1(
        source,
        manifest=fake_manifest,
        manifest_identity=manifest_identity,
        task_terminal_records=[{"fixture": True}],
    ) == source

    assert source["task_terminal_generation_resolution_scope"] == {
        "resolver_role": "host-finalizer-only",
        "uri_source": "exact-manifest-task-terminal-evidence-uris",
        "resolved_uri_count": 1,
        "resolved_uris_sha256": contract.canonical_sha256_v1([
            fake_manifest["task_bindings"][0]["task_terminal_evidence_uri"]
        ]),
        "current_generation_metadata_lookup_per_uri": 1,
        "immediate_generation_pin_required": True,
        "generation_exact_hash_read_required": True,
        "listing_allowed": False,
        "logs_allowed": False,
        "scientific_output_resolution_allowed": False,
        "current_generation_resolution_performed": True,
    }

    for field, value in (
        ("listing_allowed", True),
        ("resolved_uri_count", 2),
        ("scientific_output_resolution_allowed", True),
    ):
        drifted = deepcopy(source)
        drifted_scope = drifted["task_terminal_generation_resolution_scope"]
        drifted_scope[field] = value
        drifted["task_terminal_generation_resolution_scope_sha256"] = (
            contract.canonical_sha256_v1(drifted_scope)
        )
        _rehash(drifted, "cloud_run_execution_observation_source_sha256")
        with pytest.raises(
            manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error,
            match="observation source authority differs",
        ):
            manifest.validate_cloud_run_execution_observation_source_v1(
                drifted,
                manifest=fake_manifest,
                manifest_identity=manifest_identity,
                task_terminal_records=[{"fixture": True}],
            )

    drifted = deepcopy(source)
    drifted["provider_run_job_overrides"]["container_overrides"] = [{
        "args": ["--caller-command"],
    }]
    drifted["provider_run_job_overrides_sha256"] = contract.canonical_sha256_v1(
        drifted["provider_run_job_overrides"]
    )
    _rehash(drifted, "cloud_run_execution_observation_source_sha256")
    with pytest.raises(
        manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error,
        match="execution overrides are present",
    ):
        manifest.validate_cloud_run_execution_observation_source_v1(
            drifted,
            manifest=fake_manifest,
            manifest_identity=manifest_identity,
            task_terminal_records=[{"fixture": True}],
        )

    drifted = deepcopy(source)
    drifted["provider_execution_task_template"]["volumes"] = [{
        "name": "caller-code",
        "secret": "alternate-code",
    }]
    drifted["provider_execution_task_template_sha256"] = (
        contract.canonical_sha256_v1(
            drifted["provider_execution_task_template"]
        )
    )
    _rehash(drifted, "cloud_run_execution_observation_source_sha256")
    with pytest.raises(
        manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error,
        match="TaskTemplate authority differs",
    ):
        manifest.validate_cloud_run_execution_observation_source_v1(
            drifted,
            manifest=fake_manifest,
            manifest_identity=manifest_identity,
            task_terminal_records=[{"fixture": True}],
        )

    drifted = deepcopy(source)
    drifted["provider_execution_task_template"]["containers"][0]["args"] = [
        "-c", "import os",
    ]
    drifted["provider_execution_task_template_sha256"] = (
        contract.canonical_sha256_v1(
            drifted["provider_execution_task_template"]
        )
    )
    _rehash(drifted, "cloud_run_execution_observation_source_sha256")
    with pytest.raises(
        manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error,
        match="launch authority differs",
    ):
        manifest.validate_cloud_run_execution_observation_source_v1(
            drifted,
            manifest=fake_manifest,
            manifest_identity=manifest_identity,
            task_terminal_records=[{"fixture": True}],
        )

    drifted = deepcopy(source)
    drifted["execution_command_override_present"] = False
    _rehash(drifted, "cloud_run_execution_observation_source_sha256")
    with pytest.raises(
        manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error,
        match="fields differ",
    ):
        manifest.validate_cloud_run_execution_observation_source_v1(
            drifted,
            manifest=fake_manifest,
            manifest_identity=manifest_identity,
            task_terminal_records=[{"fixture": True}],
        )


def test_wrong_process_budget_schema_cannot_cross_a_registered_layer() -> None:
    body = {
        "schema_version": contract.PROCESS_BUDGET_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "process_role": "broad-evaluator",
        "process_ordinal": 0,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    _rehash(body, "process_budget_sha256")
    identity = _identity(
        contract.OUTPUT_NAMESPACE + "controller-focused/budgets/wrong.json",
        body,
    )
    with pytest.raises(
        manifest.CorpusR6CurrentBankCrossedScreenTaskManifestV1Error,
        match="schema differs from registered layer",
    ):
        manifest._exact_task_process_budget_bindings_v1(
            manifest={"layer_id": "broad-evaluation-result"},
            task={
                "request": {"process_budget_identity": identity},
                "process_role": "broad-evaluator",
                "phase": contract.BROAD_SCREEN_PHASE,
                "source_ordinal": 0,
                "process_ordinal": 0,
            },
            read_exact=lambda supplied: contract.canonical_json_bytes_v1(body),
        )
