from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as source_manifest,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_cloud_v1 as cloud,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_process_adapter_v1 as adapter,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_runtime_v1 as child_runtime,
)


def _identity(tag: str, value: object | None = None) -> dict[str, object]:
    raw = contract.canonical_json_bytes_v1(
        {"tag": tag} if value is None else value
    )
    return {
        "uri": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            f"successor-cloud-fixture/{tag}.json"
        ),
        "generation": str(700_000 + len(tag)),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _source_task(index: int) -> dict[str, object]:
    return {
        "task_index": index,
        "source_ordinal": index,
        "task_binding_sha256": f"{index + 1:064x}",
        "task_science_binding_sha256": f"{index + 101:064x}",
        "request_sha256": f"{index + 201:064x}",
    }


def _source_manifest() -> dict[str, object]:
    tasks = [_source_task(index) for index in range(cloud.TASK_COUNT)]
    body = {
        "layer_id": "broad-selection-receipt",
        "phase": contract.BROAD_SCREEN_PHASE,
        "task_count": cloud.TASK_COUNT,
        "task_bindings": tasks,
    }
    body["task_manifest_sha256"] = contract.canonical_sha256_v1(body)
    return body


def _task_binding(index: int, source: dict[str, object]) -> dict[str, object]:
    source_budget_ids = [
        _identity(f"source-{index:03d}-fold-{fold}")
        for fold in range(contract.FOLDS_PER_SLATE)
    ]
    successor_budget_ids = [
        _identity(f"successor-{index:03d}-fold-{fold}")
        for fold in range(contract.FOLDS_PER_SLATE)
    ]
    return cloud.build_task_binding_v1(
        source_ordinal=index,
        slate_id=f"2025-w{index + 1:02d}",
        source_task_binding=source["task_bindings"][index],
        projection_bundle_identity=_identity(f"bundle-{index:03d}"),
        source_process_budget_identities=source_budget_ids,
        successor_process_budget_identities=successor_budget_ids,
        slate_process_budget_identity=_identity(f"slate-budget-{index:03d}"),
        result_uri=(
            contract.OUTPUT_NAMESPACE
            + f"successor-cloud-fixture/results/source-{index:03d}.json"
        ),
    )


def _dispatcher_runtime() -> dict[str, object]:
    environment = {
        cloud.ENABLE_ENV: "1",
        "GOOGLE_CLOUD_PROJECT": cloud.FIXED_GCP_PROJECT,
        "CODE_SHA": "a" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
        "CLOUD_RUN_JOB": "successor-fixture",
        "CLOUD_RUN_EXECUTION": "successor-fixture-00001",
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_COUNT": str(cloud.TASK_COUNT),
        "CLOUD_RUN_TASK_ATTEMPT": "0",
    }
    return cloud.build_dispatcher_runtime_evidence_v1(
        environ=environment,
        observed_command=list(cloud.DISPATCHER_COMMAND),
        pid=400,
        parent_pid=300,
    )


def test_bootstrap_registers_distinct_successor_commands() -> None:
    bootstrap = cloud.build_bootstrap_v1(
        code_commit="a" * 40,
        image_digest="sha256:" + "b" * 64,
        run_authorization_identity=_identity("run-authorization"),
    )
    assert cloud.validate_bootstrap_v1(bootstrap) == bootstrap
    dispatcher, matrix = bootstrap["process_specs"]
    assert dispatcher["command"] == list(cloud.DISPATCHER_COMMAND)
    assert matrix["command"] == child_runtime.canonical_matrix_selector_command_v1()
    assert matrix["command"] != [
        "/usr/local/bin/python3.11",
        "/app/src/nfl_dfs/research/"
        "corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1.py",
        "matrix-selector",
    ]
    assert bootstrap["source_control_process_spec_compatible"] is False


def test_prelaunch_authorization_is_successor_specific_and_nonterminal() -> None:
    authorization = cloud.build_run_authorization_v1(
        source_task_manifest_identity=_identity("source-manifest"),
        output_prefix=contract.OUTPUT_NAMESPACE + "successor-cloud-fixture/",
        code_commit="a" * 40,
        image_digest="sha256:" + "b" * 64,
        reused_job_name="atlas-cbc-32g-full-2023-w8-v1",
    )
    assert cloud.validate_run_authorization_v1(authorization) == authorization
    assert authorization["task_count"] == 54
    assert authorization["cloud_execution_attestation_present"] is False
    assert authorization["launch_submission_authority"] is False
    assert authorization["source_control_runtime_compatibility_claimed"] is False


def test_manifest_registers_exact_6480_fit_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source_manifest()
    monkeypatch.setattr(
        source_manifest, "validate_task_manifest_v1", lambda value: dict(value)
    )
    source_identity = _identity("source-manifest", source)
    run_identity = _identity("run-authorization")
    bootstrap = cloud.build_bootstrap_v1(
        code_commit="a" * 40,
        image_digest="sha256:" + "b" * 64,
        run_authorization_identity=run_identity,
    )
    bootstrap_identity = _identity("bootstrap", bootstrap)
    bindings = [
        _task_binding(index, source) for index in range(cloud.TASK_COUNT)
    ]
    manifest = cloud.build_task_manifest_v1(
        output_prefix=contract.OUTPUT_NAMESPACE + "successor-cloud-fixture/",
        source_task_manifest=source,
        source_task_manifest_identity=source_identity,
        bootstrap=bootstrap,
        bootstrap_identity=bootstrap_identity,
        run_authorization_identity=run_identity,
        task_bindings=bindings,
    )
    assert manifest["task_count"] == 54
    assert manifest["fit_count_precharge_per_task"] == 120
    assert manifest["fit_count_precharge_total"] == 6_480
    assert manifest["source_control_fit_parity_claimed"] is False
    assert cloud.validate_task_manifest_v1(
        manifest, source_task_manifest=source, bootstrap=bootstrap
    ) == manifest
    manifest_identity = _identity("successor-manifest", manifest)
    configuration = cloud.build_cloud_run_job_configuration_v1(
        task_manifest=manifest,
        task_manifest_identity=manifest_identity,
        reused_job_name="atlas-cbc-32g-full-2023-w8-v1",
    )
    assert configuration["container_command"] == [
        cloud.DISPATCHER_COMMAND[0]
    ]
    assert configuration["container_args"] == list(
        cloud.DISPATCHER_COMMAND[1:]
    )
    assert configuration["task_count"] == 54
    assert configuration["parallelism"] == 54
    assert configuration["max_retries"] == 0
    assert configuration["new_job_creation_allowed"] is False

    changed = deepcopy(manifest)
    changed["fit_count_precharge_total"] = 17_280
    changed["task_manifest_sha256"] = contract.canonical_sha256_v1({
        key: row for key, row in changed.items()
        if key != "task_manifest_sha256"
    })
    with pytest.raises(
        cloud.CorpusR6CurrentBankSelectorSuccessorCloudV1Error,
        match="canonical replay differs",
    ):
        cloud.validate_task_manifest_v1(
            changed, source_task_manifest=source, bootstrap=bootstrap
        )


def test_slate_budget_is_five_folds_120_fits_one_create_once_write() -> None:
    source_budget_ids = [_identity(f"source-budget-{fold}") for fold in range(5)]
    successor_budget_ids = [
        _identity(f"successor-budget-{fold}") for fold in range(5)
    ]
    scientific = [_identity("later"), *[_identity(f"world-{b}") for b in contract.WORLD_BLOCKS]]
    result_uri = contract.OUTPUT_NAMESPACE + "successor-cloud-fixture/results/source-000.json"
    budget = cloud.build_slate_process_budget_v1(
        source_ordinal=0,
        slate_id="2025-w18",
        source_task_manifest_identity=_identity("source-manifest"),
        bootstrap_identity=_identity("bootstrap"),
        run_authorization_identity=_identity("run-authorization"),
        design_identity=_identity("design"),
        topology_identity=_identity("topology"),
        projection_bundle_identity=_identity("bundle"),
        source_process_budget_identities=source_budget_ids,
        successor_process_budget_identities=successor_budget_ids,
        scientific_read_identities=scientific,
        result_uri=result_uri,
    )
    assert cloud.validate_slate_process_budget_v1(budget) == budget
    assert budget["fold_process_count"] == 5
    assert budget["compute_fit_precharge"] == 120
    assert budget["write_allowlist"] == [{
        "role": "successor-slate-result",
        "uri": result_uri,
        "max_bytes": cloud.MAXIMUM_SLATE_RESULT_BYTES,
        "create_once": True,
    }]


def test_dispatcher_runtime_rejects_old_control_command() -> None:
    runtime = _dispatcher_runtime()
    assert cloud.validate_dispatcher_runtime_evidence_v1(runtime) == runtime
    environment = {
        cloud.ENABLE_ENV: "1",
        "GOOGLE_CLOUD_PROJECT": cloud.FIXED_GCP_PROJECT,
        "CODE_SHA": "a" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
        "CLOUD_RUN_JOB": "successor-fixture",
        "CLOUD_RUN_EXECUTION": "successor-fixture-00001",
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_COUNT": str(cloud.TASK_COUNT),
        "CLOUD_RUN_TASK_ATTEMPT": "0",
    }
    with pytest.raises(
        cloud.CorpusR6CurrentBankSelectorSuccessorCloudV1Error,
        match="runtime environment differs",
    ):
        cloud.build_dispatcher_runtime_evidence_v1(
            environ=environment,
            observed_command=child_runtime.canonical_matrix_selector_command_v1(),
            pid=400,
            parent_pid=300,
        )
