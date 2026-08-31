from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_r6_construction_allocation_cross_operator_v1 as build_authority,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import (
    corpus_r6_paid_source_discovery_matrix_freeze_v1 as matrix_freeze,
)
from nfl_dfs.research import corpus_r6_paid_source_ablation_v1 as matchup
from nfl_dfs.research import paid_source_ablation_execution_v1 as execution
from nfl_dfs.research import paid_source_ablation_registry_v1 as registry
from tests import test_corpus_r6_matchup_component_producer_v1 as source_fixture
from tests import test_paid_source_ablations_v1 as paid_fixture


CODE_SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/"
    "nfl-dfs/nfl-dfs@" + DIGEST
)
BUILD_ID = "12345678-1234-1234-1234-123456789abc"


def _identity(raw: bytes, name: str) -> dict[str, object]:
    return {
        "uri": f"gs://fixture-bucket/paid-execution/{name}",
        "generation": str(int(sha256(name.encode()).hexdigest()[:12], 16) + 1),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _request_fixture() -> tuple[
    dict[str, object], dict[str, bytes], dict[str, object], bytes,
]:
    catalog = source_fixture._catalog(0)
    candidates = source.build_accepted_candidate_artifact_v1(
        source_task_ordinal=0,
        rows=source_fixture._candidate_rosters()[0]["rows"],
    )
    upstream = source_fixture._upstream()
    storage: dict[str, bytes] = {
        str(upstream["release_identity"]["uri"]): registry.canonical_json_bytes(
            upstream["release"]
        )
    }
    for pack, rows in zip(
        upstream["release"]["packs"], upstream["pack_rows"], strict=True
    ):
        storage[str(pack["exact_rows_identity"]["uri"])] = (
            registry.canonical_json_bytes(rows)
        )
    attestation = build_authority.runtime_build_attestation_v1(
        build_id=BUILD_ID,
        source_repository="https://github.com/example/nfl-predictions.git",
        requested_source_commit=CODE_SHA,
        resolved_source_commit=CODE_SHA,
        image_tag=(
            "us-central1-docker.pkg.dev/nfl-predictions-503414/"
            "nfl-dfs/nfl-dfs:paid-source-fixture"
        ),
        image_digest=DIGEST,
        provider_observed_at="2026-08-30T12:00:00Z",
    )
    attestation_raw = registry.canonical_json_bytes(attestation)
    attestation_identity = {
        **_identity(attestation_raw, "build-attestation.json"),
        "create_once": True,
    }
    storage[str(attestation_identity["uri"])] = attestation_raw
    source_root_raw = registry.canonical_json_bytes({"fixture": "source-v3"})
    source_root_identity = _identity(source_root_raw, "source-v3.json")
    storage[str(source_root_identity["uri"])] = source_root_raw
    matrix_root_raw = registry.canonical_json_bytes({"fixture": "matrix-root"})
    matrix_root_identity = _identity(matrix_root_raw, "matrix-root.json")
    storage[str(matrix_root_identity["uri"])] = matrix_root_raw
    request = execution.build_fp_sis_execution_request_v1(
        run_id="paid-source-fixture-v2",
        frozen_at="2026-08-30T12:00:00Z",
        source_v3_release_identity=source_root_identity,
        discovery_matrix_freeze_terminal_identity=matrix_root_identity,
        code_sha=CODE_SHA,
        immutable_image=IMAGE,
        build_id=BUILD_ID,
        runtime_build_attestation_identity=attestation_identity,
    )
    catalog_identity = paid_fixture._identity_for_body(catalog, "task0-catalog")
    candidate_identity = paid_fixture._identity_for_body(
        candidates, "task0-candidates"
    )
    member = {
        "source_task_ordinal": 0,
        "catalog_identity": catalog_identity,
        "candidate_artifact_identity": candidate_identity,
    }
    deep = {
        "release": {
            "entries": [member],
            "upstream_source_release_identity": upstream["release_identity"],
        },
        "member": member,
        "candidate_authority_binding": {
            "candidate_artifact_identity": candidate_identity,
        },
        "structural_catalog": catalog,
        "candidate_artifact": candidates,
    }
    return request, storage, deep, matrix_root_raw


def _matrix_fixture(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], list[str], dict[str, object]]:
    _, _, deep, _ = _request_fixture()
    ids = [str(row["candidate_id"]) for row in deep["candidate_artifact"]["rows"]]
    candidate_identity = deep["candidate_authority_binding"][
        "candidate_artifact_identity"
    ]
    source_ids = [_identity(b"world", f"R{index}.npz") for index in range(4)]
    values = np.zeros(
        (len(ids), matrix_freeze.DISCOVERY_WORLD_COUNT), dtype="<f8"
    )
    body = values.tobytes(order="C")
    header = {
        "schema_version": matrix_freeze.MATRIX_ENVELOPE_SCHEMA,
        "candidate_ids": ids,
        "candidate_artifact_identity": candidate_identity,
        "candidate_ids_sha256": registry.canonical_sha256(ids),
        "dtype": "<f8",
        "shape": [len(ids), matrix_freeze.DISCOVERY_WORLD_COUNT],
        "block_order": list(matrix_freeze.DISCOVERY_BLOCKS),
        "worlds_per_block": matrix_freeze.WORLDS_PER_BLOCK,
        "source_world_artifact_identities": source_ids,
        "source_world_artifact_manifest_sha256": registry.canonical_sha256(
            source_ids
        ),
        "r4_heldout_not_read": True,
    }
    raw = registry.canonical_json_bytes(header) + b"\n" + body
    path = tmp_path / "matrix.bin"
    path.write_bytes(raw)
    identity = _identity(raw, "matrix.bin")
    entry = {
        "source_task_ordinal": 0,
        "slate": deep["candidate_artifact"]["slate"],
        "matrix_identity": identity,
        "candidate_artifact_identity": candidate_identity,
        "candidate_ids_sha256": registry.canonical_sha256(ids),
        "source_world_artifact_identities": source_ids,
        "source_world_artifact_manifest_sha256": registry.canonical_sha256(
            source_ids
        ),
        "block_order": list(matrix_freeze.DISCOVERY_BLOCKS),
        "worlds_per_block": matrix_freeze.WORLDS_PER_BLOCK,
        "world_count": matrix_freeze.DISCOVERY_WORLD_COUNT,
        "dtype": "<f8",
        "scoring_law_id": matrix_freeze.SCORING_LAW_ID,
        "r4_heldout_identity": _identity(b"heldout", "R4.npz"),
        "r4_heldout_not_read": True,
        "matrix_lineage_sha256": "c" * 64,
        "matrix_body_sha256": sha256(body).hexdigest(),
    }
    return path, entry, ids, candidate_identity


def _task0_receipt(request: dict[str, object]) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": execution.TASK0_SCHEMA,
        "execution_request_sha256": request["execution_request_sha256"],
        "run_id": request["run_id"],
        "source_v3_release_identity": request["source_v3_release_identity"],
        "discovery_matrix_freeze_terminal_identity": request[
            "discovery_matrix_freeze_terminal_identity"
        ],
        "discovery_matrix_registry_reopen_sha256": "c" * 64,
        "task0_world_matrix_identity": request[
            "discovery_matrix_freeze_terminal_identity"
        ],
        "runtime_build_attestation_sha256": "d" * 64,
        "task0_slate_support_census_sha256": "e" * 64,
        "task0_source_task_ordinal": 0,
        "task0_k80_feasible_all_four_cells": True,
        "all_54_input_identities_frozen": True,
        "full_cohort_execution_launched": False,
        "publication_performed": False,
        "publication_callback_present": False,
        "write_api_reachable_from_task0": False,
        "runtime_principal_write_authority_status": "not-evaluated",
        "recognized_outcome_callback_present": False,
        "runtime_principal_outcome_authority_status": "not-evaluated",
        "outcome_artifacts_read": [],
        "world_matrix_body_read_count": 1,
        "matrix_streamed_to_disk_and_memmapped": True,
        "selection_bank_r0_r3_float64_exact": True,
        "r4_body_read": False,
        "mechanical_launch_gate_passed": True,
        "complete": True,
        **execution._policy(uses_realized_outcomes=False),
    }
    body["task0_receipt_sha256"] = registry.canonical_sha256(body)
    return body


def _task0_provider_gate(
    request: dict[str, object], *, service_account: str | None = None,
) -> dict[str, object]:
    receipt = _task0_receipt(request)
    request_sha = sha256(registry.canonical_json_bytes(request)).hexdigest()
    execution_row = {
        "name": "atlas-cbc-32g-full-2023-w8-v1-abc12",
        "uid": "fixture-execution-uid",
        "task_count": 1,
        "succeeded_count": 1,
        "failed_count": 0,
        "cancelled_count": 0,
        "running_count": 0,
        "creation_time": "2026-08-30T12:20:00Z",
        "start_time": "2026-08-30T12:21:00Z",
        "completion_time": "2026-08-30T12:30:00Z",
    }
    provider_spec: dict[str, object] = {
        "schema_version": execution.TASK0_PROVIDER_SPEC_SCHEMA,
        "provider": "google-cloud-run-v2-api",
        "project_id": execution.PROVIDER_PROJECT_ID,
        "region": execution.PROVIDER_REGION,
        "job_name": execution.PROVIDER_JOB_NAME,
        "job_uid": execution.PROVIDER_JOB_UID,
        "job_generation": "101",
        "execution_name": execution_row["name"],
        "execution_uid": execution_row["uid"],
        "service_account_name": (
            service_account or execution.PROVIDER_SERVICE_ACCOUNT
        ),
        "task_count": 1,
        "max_retries": 0,
        "timeout_seconds": execution.PROVIDER_TASK_TIMEOUT_SECONDS,
        "image": request["immutable_image"],
        "command": ["/bin/bash"],
        "args": [
            "/app/scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh",
            "container-run", "task0",
        ],
        "cpu": execution.PROVIDER_CPU,
        "memory": execution.PROVIDER_MEMORY,
        "environment_names": sorted([
            "BUILD_ID", "CODE_SHA", "IMAGE_DIGEST",
            "IMAGE_SOURCE_COMMIT_SHA", "IMAGE_URI",
            "R6_PAID_SOURCE_FP_SIS_ENABLE",
            "R6_PAID_SOURCE_FP_SIS_OUTCOMES_ALLOWED",
            "R6_PAID_SOURCE_FP_SIS_REQUEST_B64",
            "R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256",
        ]),
        "environment_bindings": {
            "code_sha": request["code_sha"],
            "image_source_commit_sha": request["code_sha"],
            "image_digest": request["image_digest"],
            "build_id": request["build_id"],
            "image_uri": request["immutable_image"],
            "enable_name": "R6_PAID_SOURCE_FP_SIS_ENABLE",
            "enable_value": "I_UNDERSTAND_FIXED_CORPUS_FP_SIS_ABLATION_V1",
            "outcomes_name": "R6_PAID_SOURCE_FP_SIS_OUTCOMES_ALLOWED",
            "outcomes_allowed": False,
            "request_b64_name": "R6_PAID_SOURCE_FP_SIS_REQUEST_B64",
            "request_sha256_name": "R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256",
            "request_sha256": request_sha,
            "execution_request_sha256": request["execution_request_sha256"],
        },
        "request_payload_sha256": request_sha,
        "creation_time": execution_row["creation_time"],
        "start_time": execution_row["start_time"],
        "completion_time": execution_row["completion_time"],
        "provider_observed_from_execution_describe": True,
        "uses_realized_outcomes": False,
    }
    provider_spec["provider_execution_spec_sha256"] = (
        registry.canonical_sha256(provider_spec)
    )
    return {
        "schema_version": execution.TASK0_CLOUD_RESULT_SCHEMA,
        "mode": "task0",
        "code_sha": request["code_sha"],
        "cloud_build_id": request["build_id"],
        "provider_resolved_image": request["immutable_image"],
        "execution": execution_row,
        "provider_execution_spec": provider_spec,
        "request_sha256": request_sha,
        "operator_receipt": receipt,
        "exact_execution_stdout_only": True,
        "task0_provider_gate_eligible": True,
        "outcome_artifacts_read": [],
        "complete": True,
    }


def test_request_binds_freezer_root_and_float64_r0_r3_law() -> None:
    request, _, _, _ = _request_fixture()
    assert execution.validate_fp_sis_execution_request_v1(request) == request
    assert "world_matrix_identities" not in request
    assert request["selection_bank_law"] == {
        "block_order": ["R0", "R1", "R2", "R3"],
        "worlds_per_block": 10_000,
        "world_count": 40_000,
        "dtype": "<f8",
        "scoring_law_id": "candidate-roster-r0-r3-float64-sum/v1",
        "r4_heldout_bound_but_not_read": True,
    }
    poisoned = deepcopy(request)
    poisoned["selection_bank_law"]["dtype"] = "<f4"
    poisoned.pop("execution_request_sha256")
    poisoned["execution_request_sha256"] = registry.canonical_sha256(poisoned)
    with pytest.raises(execution.PaidSourceAblationExecutionV1Error):
        execution.validate_fp_sis_execution_request_v1(poisoned)


def test_matrix_opener_stream_hashes_and_memmaps_exact_float64(
    tmp_path: Path,
) -> None:
    path, entry, ids, candidate_identity = _matrix_fixture(tmp_path)
    header, values = execution.open_discovery_world_matrix_file_v2(
        path,
        matrix_registry_entry=entry,
        candidate_ids=ids,
        candidate_artifact_identity=candidate_identity,
    )
    assert header["block_order"] == ["R0", "R1", "R2", "R3"]
    assert isinstance(values, np.memmap)
    assert values.dtype.str == "<f8"
    assert values.shape == (len(ids), 40_000)
    binding = matchup.build_discovery_world_matrix_binding_v2(
        world_matrix_identity=entry["matrix_identity"],
        candidate_ids=ids,
        world_scores=values,
        matrix_header=header,
        matrix_registry_entry=entry,
    )
    assert matchup.validate_discovery_world_matrix_binding_v2(
        binding, candidate_ids=ids, world_scores=values
    ) == binding
    values._mmap.close()

    wrong = deepcopy(entry)
    wrong["dtype"] = "<f4"
    with pytest.raises(
        execution.PaidSourceAblationExecutionV1Error,
        match="registry/identity differs",
    ):
        execution.open_discovery_world_matrix_file_v2(
            path,
            matrix_registry_entry=wrong,
            candidate_ids=ids,
            candidate_artifact_identity=candidate_identity,
        )


def test_task0_is_nonpublishing_and_reads_one_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, _, deep, _ = _request_fixture()
    matrix_identity = _identity(b"matrix", "task0-matrix.bin")
    entry = {"matrix_identity": matrix_identity}
    reopen_receipt = {"registry_reopen_sha256": "d" * 64}
    monkeypatch.setattr(
        execution, "_runtime_build_attestation",
        lambda request, read_exact: {
            "runtime_build_attestation_sha256": "e" * 64
        },
    )
    monkeypatch.setattr(
        execution, "_reopen_matrix_registry",
        lambda *args, **kwargs: ({}, [entry] * 54, reopen_receipt),
    )
    matrix_path = tmp_path / "fake.bin"
    monkeypatch.setattr(
        execution, "_slate_input",
        lambda **kwargs: ({"fixture": True}, matrix_path),
    )
    monkeypatch.setattr(execution, "_release_slate_matrix", lambda *args: None)
    monkeypatch.setattr(
        execution.matchup, "run_fp_sis_retrieval_support_census_v1",
        lambda **kwargs: {
            "source_task_ordinal": 0,
            "support_gate_status": "passed",
            "slate_support_census_sha256": "f" * 64,
        },
    )
    receipt = execution.run_fp_sis_task0_v1(
        request,
        read_exact=lambda identity: b"unused",
        fetch_exact_to_file=lambda identity, path: None,
        matrix_workspace=tmp_path,
        reopen_discovery_matrix_registry=lambda **kwargs: None,
        canonical_source_v3_reopen_by_ordinal=lambda ordinal: deep,
    )
    assert receipt["publication_performed"] is False
    assert receipt["publication_callback_present"] is False
    assert receipt["write_api_reachable_from_task0"] is False
    assert receipt["runtime_principal_write_authority_status"] == "not-evaluated"
    assert receipt["recognized_outcome_callback_present"] is False
    assert receipt["runtime_principal_outcome_authority_status"] == "not-evaluated"
    assert receipt["outcome_artifacts_read"] == []
    assert receipt["world_matrix_body_read_count"] == 1
    assert receipt["selection_bank_r0_r3_float64_exact"] is True
    assert receipt["r4_body_read"] is False
    assert execution.validate_fp_sis_task0_receipt_v1(
        receipt, request_value=request
    ) == receipt


def test_task0_provider_gate_binds_full_actual_spec_and_principal() -> None:
    request, _, _, _ = _request_fixture()
    gate = _task0_provider_gate(request)
    assert execution.validate_fp_sis_task0_provider_gate_v1(
        gate, request_value=request
    ) == gate

    wrong_principal = _task0_provider_gate(
        request, service_account="wrong-principal@example.invalid"
    )
    with pytest.raises(
        execution.PaidSourceAblationExecutionV1Error,
        match="exact task0 provider gate differs",
    ):
        execution.validate_fp_sis_task0_provider_gate_v1(
            wrong_principal, request_value=request
        )


def test_removed_all54_in_memory_entrypoint_fails_closed() -> None:
    with pytest.raises(
        execution.PaidSourceAblationExecutionV1Error,
        match="all-54 in-memory",
    ):
        execution._removed_all54_in_memory_terminal_v1(
            {},
            task0_receipt_value={},
            read_exact=lambda identity: b"",
            publish_create_once=lambda uri, raw: {},
            canonical_source_v3_reopen_by_ordinal=lambda ordinal: {},
        )


def test_one_slate_worker_reads_one_matrix_and_publishes_one_compact_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, _, _, _ = _request_fixture()
    task0 = _task0_receipt(request)
    task0_provider_gate = _task0_provider_gate(request)
    ordinal = 7
    matrix_identity = _identity(b"matrix", "worker-matrix.bin")
    entry = {
        "source_task_ordinal": ordinal,
        "slate": "2023-w08",
        "matrix_identity": matrix_identity,
        "matrix_lineage_sha256": "9" * 64,
    }
    registry_rows = [dict(entry, source_task_ordinal=index) for index in range(54)]
    registry_rows[ordinal] = entry
    reopen_receipt = {"registry_reopen_sha256": "c" * 64}
    monkeypatch.setattr(
        execution, "_runtime_build_attestation",
        lambda request, read_exact: {"runtime_build_attestation_sha256": "d" * 64},
    )
    monkeypatch.setattr(
        execution, "_reopen_matrix_registry",
        lambda *args, **kwargs: ({}, registry_rows, reopen_receipt),
    )
    selected: list[object] = []
    matrix_path = tmp_path / "worker.bin"
    monkeypatch.setattr(
        execution, "_slate_input",
        lambda **kwargs: (
            selected.append(kwargs["matrix_registry_entry"])
            or ({"fixture": True}, matrix_path)
        ),
    )
    released: list[Path] = []
    monkeypatch.setattr(
        execution, "_release_slate_matrix",
        lambda slate_input, path: released.append(path),
    )
    census = {
        "source_task_ordinal": ordinal,
        "slate": entry["slate"],
        "support_gate_status": "passed",
        "slate_support_census_sha256": "8" * 64,
    }
    monkeypatch.setattr(
        execution.matchup, "run_fp_sis_retrieval_support_census_v1",
        lambda **kwargs: census,
    )
    monkeypatch.setattr(
        execution.matchup, "validate_fp_sis_retrieval_support_census_v1",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        execution, "_diagnostics_from_census",
        lambda value: {"diagnostic_manifest_sha256": "7" * 64},
    )
    storage: dict[str, bytes] = {}

    def publish(uri: str, raw: bytes) -> dict[str, object]:
        assert uri.endswith("/tasks/0007.json")
        assert uri not in storage
        storage[uri] = raw
        return {**_identity(raw, "worker-result.json"), "uri": uri,
                "create_once": True}

    def read(identity: Mapping[str, object]) -> bytes:
        return storage[str(identity["uri"])]

    publication = execution.run_fp_sis_slate_task_v2(
        request,
        task0_receipt_value=task0,
        task0_provider_gate_value=task0_provider_gate,
        source_task_ordinal=ordinal,
        read_exact=read,
        fetch_exact_to_file=lambda identity, path: None,
        matrix_workspace=tmp_path,
        publish_create_once=publish,
        reopen_discovery_matrix_registry=lambda **kwargs: None,
        canonical_source_v3_reopen_by_ordinal=lambda index: {"ordinal": index},
    )
    assert selected == [entry]
    assert released == [matrix_path]
    assert publication["source_task_ordinal"] == ordinal
    assert publication["one_slate_only"] is True
    assert publication["matrix_body_read_count"] == 1
    assert publication["task0_provider_gate_sha256"] == (
        registry.canonical_sha256(task0_provider_gate)
    )
    assert len(storage) == 1


def test_collector_reads_zero_matrices_and_publishes_root_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, _, _, _ = _request_fixture()
    task0 = _task0_receipt(request)
    task0_provider_gate = _task0_provider_gate(request)
    registry_rows = [
        {
            "source_task_ordinal": ordinal,
            "slate": f"fixture-{ordinal:02d}",
            "matrix_lineage_sha256": f"{ordinal:064x}",
        }
        for ordinal in range(54)
    ]
    monkeypatch.setattr(
        execution, "_runtime_build_attestation", lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        execution, "_reopen_matrix_registry",
        lambda *args, **kwargs: (
            {}, registry_rows, {"registry_reopen_sha256": "c" * 64},
        ),
    )

    def open_publication(value: object, *, ordinal: int, **kwargs: object):
        body = {
            "slate": registry_rows[ordinal]["slate"],
            "task0_provider_gate_sha256": registry.canonical_sha256(
                task0_provider_gate
            ),
            "slate_result_sha256": f"{ordinal + 100:064x}",
            "slate_support_census_sha256": f"{ordinal + 200:064x}",
            "matrix_lineage_sha256": registry_rows[ordinal][
                "matrix_lineage_sha256"
            ],
            "slate_support_census": {"source_task_ordinal": ordinal},
        }
        raw = registry.canonical_json_bytes(body)
        return body, {**_identity(raw, f"result-{ordinal}.json"),
                      "create_once": True}

    monkeypatch.setattr(execution, "_open_slate_publication_v2", open_publication)
    panel = {
        "support_gate_status": "passed",
        "panel_support_census_sha256": "a" * 64,
    }
    monkeypatch.setattr(
        execution.matchup, "build_fp_sis_panel_support_census_v1",
        lambda values: panel,
    )
    monkeypatch.setattr(
        execution, "reopen_fp_sis_score_free_terminal_v1",
        lambda **kwargs: {"complete": True},
    )
    storage: dict[str, bytes] = {}
    publication_order: list[str] = []

    def publish(uri: str, raw: bytes) -> dict[str, object]:
        publication_order.append(uri)
        storage[uri] = raw
        return {**_identity(raw, uri.rsplit("/", 1)[-1]), "uri": uri,
                "create_once": True}

    def read(identity: Mapping[str, object]) -> bytes:
        return storage[str(identity["uri"])]

    result = execution.collect_fp_sis_score_free_terminal_v2(
        request,
        task0_receipt_value=task0,
        task0_provider_gate_value=task0_provider_gate,
        slate_publications=[{"source_task_ordinal": index} for index in range(54)],
        read_exact=read,
        publish_create_once=publish,
        reopen_discovery_matrix_registry=lambda **kwargs: None,
    )
    assert len(publication_order) == 2
    assert publication_order[0].endswith("/panel-support.json")
    assert publication_order[1] == request["terminal_uri"]
    assert result["slate_count"] == 54
    assert result["collector_matrix_body_read_count"] == 0
    assert result["terminal_root_last"] is True
    assert result["task0_provider_gate_sha256"] == (
        registry.canonical_sha256(task0_provider_gate)
    )
    terminal = json.loads(storage[request["terminal_uri"]])
    assert terminal["task0_provider_gate"] == task0_provider_gate
    assert terminal["task0_provider_gate_sha256"] == (
        registry.canonical_sha256(task0_provider_gate)
    )
    assert {
        row["task0_provider_gate_sha256"] for row in terminal["slate_results"]
    } == {registry.canonical_sha256(task0_provider_gate)}


def test_score_free_reopen_reports_exact_task0_provider_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, _, _, _ = _request_fixture()
    gate = _task0_provider_gate(request)
    terminal_identity = {
        **_identity(b"terminal", "terminal.json"),
        "create_once": True,
    }
    monkeypatch.setattr(
        execution,
        "_reopen_fp_sis_execution_terminal_v2",
        lambda *args, **kwargs: {
            "terminal": {"run_id": request["run_id"]},
            "task0_provider_gate": gate,
            "complete": True,
        },
    )
    reopened = execution.reopen_fp_sis_score_free_terminal_v1(
        terminal_identity=terminal_identity,
        terminal_sha256="f" * 64,
        read_exact=lambda identity: b"unused",
        reopen_discovery_matrix_registry=lambda **kwargs: None,
    )
    assert reopened["task0_provider_execution"] == {
        "name": gate["execution"]["name"],
        "uid": gate["execution"]["uid"],
        "completion_time": gate["execution"]["completion_time"],
    }
    assert reopened["task0_provider_execution_spec_sha256"] == gate[
        "provider_execution_spec"
    ]["provider_execution_spec_sha256"]
