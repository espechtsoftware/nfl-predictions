from __future__ import annotations

import base64
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_paid_source_discovery_matrix_freeze_v1 as freeze
from nfl_dfs.research import lr8_later_period_source as later
from nfl_dfs.research import corpus_r6_population_crossed_scoring_v1 as crossed
from scripts import run_corpus_r6_paid_source_discovery_matrix_freeze_v1 as runner


def _identity(uri: str, raw: bytes, generation: int) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _npz(block: str, values: np.ndarray) -> bytes:
    handle = BytesIO()
    np.savez(
        handle,
        cand_ix=np.arange(1, dtype=np.int64),
        totals=np.zeros((1, 3), dtype=np.float32),
        tail_line=np.array([0], dtype=np.float32),
        player_ids=np.array([f"p{index:02d}" for index in range(9)]),
        player_draws=np.asarray(values, dtype=np.float32),
    )
    return handle.getvalue()


def _fixture(monkeypatch: pytest.MonkeyPatch) -> tuple[dict, dict, dict, list]:
    monkeypatch.setattr(freeze, "TASK_COUNT", 1)
    monkeypatch.setattr(freeze, "WORLDS_PER_BLOCK", 3)
    monkeypatch.setattr(freeze, "DISCOVERY_WORLD_COUNT", 12)
    monkeypatch.setattr(later.rw, "WORLDS_PER_BLOCK", 3)
    roster = [f"p{index:02d}" for index in range(9)]
    artifact = source.build_accepted_candidate_artifact_v1(
        source_task_ordinal=0,
        rows=[
            {"candidate_id": f"candidate-{index:03d}", "player_ids": roster}
            for index in range(80)
        ],
    )
    artifact_raw = source.canonical_json_bytes(artifact)
    artifact_identity = _identity("gs://test/candidates.json", artifact_raw, 1)
    descriptor = {
        "source_task_ordinal": 0,
        "task_id": artifact["task_id"],
        "slate": artifact["slate"],
        "candidate_artifact_identity": artifact_identity,
        "candidate_artifact_sha256": artifact["candidate_artifact_sha256"],
        "candidate_count": 80,
        "ordered_candidate_ids_sha256": artifact["ordered_candidate_ids_sha256"],
    }
    objects: dict[str, bytes] = {artifact_identity["uri"]: artifact_raw}
    receipts = []
    expected = []
    for block_index, block in enumerate(freeze.WORLD_BLOCKS):
        values = np.arange(27, dtype=np.float32).reshape(9, 3) + block_index
        raw = _npz(block, values)
        identity = _identity(f"gs://test/{block}.npz", raw, block_index + 2)
        objects[identity["uri"]] = raw
        receipts.append({
            **identity,
            "block": block,
            "candidate_rows": 1,
        })
        if block != "R4":
            expected.extend(values.sum(axis=0, dtype=np.float32).tolist())
    task = freeze._task_binding(
        run_id="matrix-test-run",
        descriptor=descriptor,
        source_slate={
            "slate_id": artifact["slate"]["slate_id"],
            "season": artifact["slate"]["season"],
            "week": artifact["slate"]["week"],
            "artifact_receipts": receipts,
        },
    )
    manifest = freeze._with_hash({
        "schema_version": freeze.MANIFEST_SCHEMA,
        "run_id": "matrix-test-run",
        "code_sha": "1" * 40,
        "immutable_image": (
            "us-central1-docker.pkg.dev/nfl-predictions-503414/"
            "nfl-dfs/nfl-dfs@sha256:" + "2" * 64
        ),
        "image_digest": "sha256:" + "2" * 64,
        "build_id": "12345678-1234-1234-1234-123456789abc",
        "runtime_build_attestation_identity": _identity(
            "gs://test/build.json", b"x", 99
        ),
        "candidate_authority_root_identity": freeze.CANDIDATE_ROOT_IDENTITY,
        "candidate_authority_release_sha256": "3" * 64,
        "later_source_freeze_identity": freeze.LATER_SOURCE_FREEZE_IDENTITY,
        "later_source_freeze_sha256": "4" * 64,
        "task_count": 1,
        "discovery_blocks": list(freeze.DISCOVERY_BLOCKS),
        "heldout_block": freeze.HELDOUT_BLOCK,
        "worlds_per_block": 3,
        "discovery_world_count": 12,
        "scoring_law": freeze._scoring_law(),
        "tasks": [task],
        "task_binding_manifest_sha256": freeze.canonical_sha256([task]),
        "output_prefix": freeze.OUTPUT_PREFIX + "/matrix-test-run/",
        "terminal_uri": freeze.OUTPUT_PREFIX + "/matrix-test-run/terminal.json",
        "reopen_terminal_uri": (
            freeze.OUTPUT_PREFIX + "/matrix-test-run/reopen-terminal.json"
        ),
        "task0_required_before_full_execution": True,
        "task0_publication_allowed": False,
        "root_published_last": True,
        "bounded_memory_law": (
            "one-slate-one-npz-block-at-a-time-disk-backed-float64-memmap"
        ),
        "r4_heldout_bound_but_not_read": True,
        **freeze._policy(),
    }, field="manifest_sha256")
    return manifest, objects, artifact, expected


def _runtime(
    manifest: dict,
    *,
    mode: str = "task",
    task0_gate_sha256: str = "5" * 64,
) -> dict[str, object]:
    task_count = 1 if mode == "task0" else freeze.TASK_COUNT
    execution_id = {
        "task0": "atlas-cbc-32g-full-2023-w8-v1-smk12",
        "task": "atlas-cbc-32g-full-2023-w8-v1-abc12",
        "reopen-task": "atlas-cbc-32g-full-2023-w8-v1-rop12",
    }[mode]
    return freeze._with_hash({
        "schema_version": freeze.RUNTIME_AUTHORITY_SCHEMA,
        "runtime_mode": mode,
        "project_id": "nfl-predictions-503414",
        "region": "us-central1",
        "job_name": "atlas-cbc-32g-full-2023-w8-v1",
        "execution_id": execution_id,
        "source_task_ordinal": 0,
        "task_count": task_count,
        "scientific_task_count": freeze.TASK_COUNT,
        "task_attempt": 0,
        "manifest_sha256": manifest["manifest_sha256"],
        "code_sha": manifest["code_sha"],
        "immutable_image": manifest["immutable_image"],
        "build_id": manifest["build_id"],
        "task0_execution_id": (
            "none" if mode != "task" else "atlas-cbc-32g-full-2023-w8-v1-smk12"
        ),
        "task0_gate_sha256": (
            "none" if mode != "task" else task0_gate_sha256
        ),
        "outcomes_allowed": False,
    }, field="runtime_authority_sha256")


def _task0_gate(manifest: dict, manifest_identity: dict) -> dict[str, object]:
    runtime = _runtime(manifest, mode="task0")
    task0_receipt = freeze._with_hash({
        "schema_version": freeze.TASK0_SCHEMA,
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "source_task_ordinal": 0,
        "task_binding_sha256": manifest["tasks"][0]["task_binding_sha256"],
        "local_materialization_sha256": "9" * 64,
        "matrix_sha256": "a" * 64,
        "matrix_shape": [
            manifest["tasks"][0]["candidate_count"],
            freeze.DISCOVERY_WORLD_COUNT,
        ],
        "matrix_dtype": freeze.MATRIX_DTYPE.str,
        "runtime_authority": runtime,
        "runtime_authority_sha256": runtime["runtime_authority_sha256"],
        "publication_performed": False,
        "task0_storage_adapter_write_api_present": False,
        "service_account": freeze.SERVICE_ACCOUNT,
        "service_account_write_capability_absence_asserted": False,
        "ambient_service_account_write_capability_restricted": False,
        "write_boundary_is_adapter_not_iam": True,
        "write_api_invoked": False,
        "full_cohort_execution_launched": False,
        "mechanical_launch_gate_passed": True,
        "r4_body_read": False,
        "complete": True,
        **freeze._policy(),
    }, field="task0_receipt_sha256")
    provider_receipt = _provider(
        manifest,
        payload_identity=manifest_identity,
        mode="task0",
        execution_id="atlas-cbc-32g-full-2023-w8-v1-smk12",
    )
    return freeze._with_hash({
        "schema_version": freeze.TASK0_GATE_SCHEMA,
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "execution_id": "atlas-cbc-32g-full-2023-w8-v1-smk12",
        "task0_receipt": task0_receipt,
        "task0_receipt_sha256": task0_receipt["task0_receipt_sha256"],
        "provider_execution_receipt": provider_receipt,
        "provider_execution_sha256": provider_receipt[
            "provider_execution_sha256"
        ],
        "exactly_one_canonical_stdout_receipt": True,
        "full_cohort_execution_launched": False,
        "complete": True,
    }, field="task0_gate_sha256")


def _provider(
    manifest: dict,
    *,
    payload_identity: dict,
    mode: str,
    execution_id: str,
) -> dict[str, object]:
    task_count = 1 if mode == "task0" else freeze.TASK_COUNT
    gate = _task0_gate(manifest, payload_identity) if mode == "task" else None
    body = {
        "schema_version": freeze.PROVIDER_EXECUTION_SCHEMA,
        "execution_id": execution_id,
        "execution_uid": "execution-uid",
        "job_name": freeze.JOB_NAME,
        "job_uid": freeze.JOB_UID,
        "mode": mode,
        "payload_identity": payload_identity,
        "payload_sha256": "6" * 64,
        "task_count": task_count,
        "parallelism": 1 if mode == "task0" else freeze.TASK_COUNT,
        "succeeded_count": task_count,
        "failed_count": 0,
        "cancelled_count": 0,
        "running_count": 0,
        "max_retries": 0,
        "timeout_seconds": freeze.TASK_TIMEOUT_SECONDS,
        "service_account": freeze.SERVICE_ACCOUNT,
        "immutable_image": manifest["immutable_image"],
        "command": list(freeze.CONTAINER_COMMAND),
        "args": [freeze.CONTAINER_SCRIPT, "container-run", mode],
        "resources": {"cpu": freeze.CPU_LIMIT, "memory": freeze.MEMORY_LIMIT},
        "environment_sha256": "7" * 64,
        "code_sha": manifest["code_sha"],
        "build_id": manifest["build_id"],
        "task0_execution_id": (
            "atlas-cbc-32g-full-2023-w8-v1-smk12" if mode == "task" else "none"
        ),
        "task0_gate_sha256": gate["task0_gate_sha256"] if gate else "none",
        "task0_gate_receipt": gate,
        "outcomes_allowed": False,
        "terminal": True,
        "complete": True,
    }
    return freeze._with_hash(body, field="provider_execution_sha256")


def test_matrix_v2_binds_lineage_and_never_reads_r4(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    manifest, objects, _, expected = _fixture(monkeypatch)
    calls = []

    def read_exact(identity: dict) -> bytes:
        calls.append(identity["uri"])
        return objects[identity["uri"]]

    path = tmp_path / "matrix.bin"
    local = freeze.build_task_matrix_file_v1(
        manifest_value=manifest,
        source_task_ordinal=0,
        read_exact=read_exact,
        destination=path,
    )
    with path.open("rb") as handle:
        header = json.loads(handle.readline())
    assert set(header) == {
        "schema_version", "candidate_ids", "candidate_artifact_identity",
        "candidate_ids_sha256", "dtype", "shape", "block_order",
        "worlds_per_block", "source_world_artifact_identities",
        "source_world_artifact_manifest_sha256", "r4_heldout_not_read",
    }
    assert header["schema_version"] == freeze.MATRIX_ENVELOPE_SCHEMA
    assert header["block_order"] == ["R0", "R1", "R2", "R3"]
    assert header["shape"] == [80, 12]
    assert header["dtype"] == "<f8"
    assert header["source_world_artifact_manifest_sha256"] == (
        freeze.canonical_sha256(header["source_world_artifact_identities"])
    )
    assert "gs://test/R4.npz" not in calls
    matrix = np.memmap(
        path, dtype="<f8", mode="r", offset=len(freeze.canonical_json_bytes(header)) + 1,
        shape=(80, 12), order="C",
    )
    assert matrix[0].tolist() == expected
    player_draws = np.concatenate([
        np.arange(27, dtype=np.float32).reshape(9, 3) + block_index
        for block_index in range(5)
    ], axis=1)
    production = crossed._score_rosters_v1(
        prepared=SimpleNamespace(
            players=tuple(
                SimpleNamespace(player_id=f"p{index:02d}") for index in range(9)
            ),
            player_draws=player_draws,
        ),
        rosters=[tuple(f"p{index:02d}" for index in range(9))] * 80,
        blocks=("R0", "R1", "R2", "R3"),
    )
    assert production.dtype == matrix.dtype == np.dtype("float64")
    assert np.array_equal(production, matrix)
    assert production.tobytes(order="C") == matrix.tobytes(order="C")
    assert local["r4_body_read"] is False
    manifest_raw = freeze.canonical_json_bytes(manifest)
    manifest_identity = _identity(
        manifest["output_prefix"] + "manifest.json", manifest_raw, 19
    )
    smoke = freeze.build_task0_receipt_v1(
        manifest_value=manifest,
        manifest_identity=manifest_identity,
        local_materialization_value=local,
        runtime_authority=_runtime(manifest, mode="task0"),
    )
    assert smoke["publication_performed"] is False
    assert smoke["task0_storage_adapter_write_api_present"] is False
    assert smoke["ambient_service_account_write_capability_restricted"] is False
    assert freeze.validate_task0_receipt_v1(
        smoke,
        manifest_value=manifest,
        manifest_identity=manifest_identity,
        expected_execution_id="atlas-cbc-32g-full-2023-w8-v1-smk12",
    ) == smoke
    payload = freeze.canonical_json_bytes(manifest_identity)
    provider_environment = {
        runner.CODE_SHA_ENV: manifest["code_sha"],
        runner.IMAGE_ENV: manifest["immutable_image"],
        "IMAGE_DIGEST": manifest["image_digest"],
        runner.BUILD_ID_ENV: manifest["build_id"],
        runner.ENABLE_ENV: runner.ENABLE_VALUE,
        runner.MODE_ENV: "task0",
        runner.OUTCOMES_ENV: "false",
        runner.PAYLOAD_ENV: base64.b64encode(payload).decode("ascii"),
        runner.PAYLOAD_SHA_ENV: sha256(payload).hexdigest(),
        runner.TASK0_EXECUTION_ENV: "none",
        runner.TASK0_GATE_SHA_ENV: "none",
        runner.TASK0_GATE_B64_ENV: "none",
    }
    provider_observation = {
        "execution_id": "atlas-cbc-32g-full-2023-w8-v1-smk12",
        "execution_uid": "task0-execution-uid",
        "job_name": freeze.JOB_NAME,
        "job_uid": freeze.JOB_UID,
        "task_count": 1,
        "parallelism": 1,
        "succeeded_count": 1,
        "failed_count": 0,
        "cancelled_count": 0,
        "running_count": 0,
        "terminal": True,
        "max_retries": 0,
        "timeout_seconds": freeze.TASK_TIMEOUT_SECONDS,
        "service_account": freeze.SERVICE_ACCOUNT,
        "immutable_image": manifest["immutable_image"],
        "command": list(freeze.CONTAINER_COMMAND),
        "args": [freeze.CONTAINER_SCRIPT, "container-run", "task0"],
        "resources": {"cpu": freeze.CPU_LIMIT, "memory": freeze.MEMORY_LIMIT},
        "environment": provider_environment,
    }
    objects[manifest_identity["uri"]] = manifest_raw
    gate = runner.validate_task0_gate(
        manifest_identity=manifest_identity,
        task0_receipt_value=smoke,
        execution_id="atlas-cbc-32g-full-2023-w8-v1-smk12",
        store=runner.ReadOnlyStoreAdapterV1(
            lambda identity: objects[identity["uri"]]
        ),
        provider=SimpleNamespace(completed=lambda execution: provider_observation),
    )
    assert gate["exactly_one_canonical_stdout_receipt"] is True
    assert gate["provider_execution_receipt"]["mode"] == "task0"
    assert gate["manifest_identity"] == manifest_identity
    wrong_payload_observation = {
        **provider_observation,
        "environment": {
            **provider_environment,
            runner.PAYLOAD_SHA_ENV: "f" * 64,
        },
    }
    with pytest.raises(
        runner.DiscoveryMatrixRunnerV1Error,
        match="payload environment differs",
    ):
        runner.validate_task0_gate(
            manifest_identity=manifest_identity,
            task0_receipt_value=smoke,
            execution_id="atlas-cbc-32g-full-2023-w8-v1-smk12",
            store=runner.ReadOnlyStoreAdapterV1(
                lambda identity: objects[identity["uri"]]
            ),
            provider=SimpleNamespace(
                completed=lambda execution: wrong_payload_observation
            ),
        )


def test_vectorized_matrix_kernel_is_bit_exact_with_production_float64_law() -> None:
    rng = np.random.default_rng(271_828)
    for _ in range(100):
        draws = rng.normal(0.0, 50.0, size=(96, 257)).astype(np.float32)
        roster_indices = np.stack([
            rng.choice(draws.shape[0], size=9, replace=False)
            for _ in range(64)
        ])
        freezer_scores = draws[roster_indices].sum(axis=1, dtype=np.float64)
        production_scores = np.empty_like(freezer_scores)
        for ordinal, indices in enumerate(roster_indices):
            production_scores[ordinal] = draws[indices].sum(
                axis=0, dtype=np.float64
            )
        assert freezer_scores.dtype == production_scores.dtype == np.dtype("float64")
        assert np.array_equal(freezer_scores, production_scores)
        assert freezer_scores.tobytes(order="C") == production_scores.tobytes(order="C")


def test_terminal_registry_reopen_is_bounded_and_generation_exact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    manifest, objects, artifact, _ = _fixture(monkeypatch)
    matrix_path = tmp_path / "matrix.bin"
    local = freeze.build_task_matrix_file_v1(
        manifest_value=manifest, source_task_ordinal=0,
        read_exact=lambda identity: objects[identity["uri"]],
        destination=matrix_path,
    )
    matrix_raw = matrix_path.read_bytes()
    matrix_identity = _identity(manifest["tasks"][0]["matrix_uri"], matrix_raw, 20)
    manifest_raw = freeze.canonical_json_bytes(manifest)
    manifest_identity = _identity(
        manifest["output_prefix"] + "manifest.json", manifest_raw, 21
    )
    task0_gate = _task0_gate(manifest, manifest_identity)
    task0_gate_raw = freeze.canonical_json_bytes(task0_gate)
    task0_gate_environment = {
        runner.TASK0_EXECUTION_ENV: task0_gate["execution_id"],
        runner.TASK0_GATE_SHA_ENV: task0_gate["task0_gate_sha256"],
        runner.TASK0_GATE_B64_ENV: base64.b64encode(task0_gate_raw).decode("ascii"),
    }
    assert runner._task0_gate_from_environment(
        task0_gate_environment,
        manifest=manifest,
        manifest_identity=manifest_identity,
    ) == task0_gate
    with pytest.raises(
        runner.DiscoveryMatrixRunnerV1Error,
        match="task0 gate environment differs",
    ):
        runner._task0_gate_from_environment(
            {**task0_gate_environment, runner.TASK0_GATE_B64_ENV: "none"},
            manifest=manifest,
            manifest_identity=manifest_identity,
        )
    result = freeze.build_task_result_v1(
        manifest_value=manifest, local_materialization_value=local,
        matrix_identity=matrix_identity,
        runtime_authority=_runtime(
            manifest, task0_gate_sha256=task0_gate["task0_gate_sha256"]
        ),
    )
    result_raw = freeze.canonical_json_bytes(result)
    result_identity = _identity(manifest["tasks"][0]["task_result_uri"], result_raw, 22)
    terminal = freeze.build_terminal_v1(
        manifest_value=manifest, manifest_identity=manifest_identity,
        task_results=[result], task_result_identities=[result_identity],
        provider_execution_receipt=_provider(
            manifest,
            payload_identity=manifest_identity,
            mode="task",
            execution_id="atlas-cbc-32g-full-2023-w8-v1-abc12",
        ),
    )
    terminal_raw = freeze.canonical_json_bytes(terminal)
    terminal_identity = _identity("gs://test/terminal.json", terminal_raw, 23)
    objects.update({
        manifest_identity["uri"]: manifest_raw,
        result_identity["uri"]: result_raw,
        terminal_identity["uri"]: terminal_raw,
    })
    calls = []

    def read_exact(identity: dict) -> bytes:
        calls.append(identity["uri"])
        return objects[identity["uri"]]

    reopened = freeze.reopen_terminal_registry_v1(
        terminal_identity=terminal_identity, read_exact=read_exact
    )
    assert len(reopened.matrix_registry) == 1
    assert reopened.matrix_registry[0]["matrix_identity"] == matrix_identity
    assert matrix_identity["uri"] not in calls
    assert all(not uri.endswith(".npz") for uri in calls)
    assert reopened.reopen_receipt["matrix_bodies_read"] is False
    assert reopened.matrix_registry[0]["candidate_ids_sha256"] == (
        artifact["ordered_candidate_ids_sha256"]
    )
    local_audit = freeze.reopen_terminal_v1(
        terminal_identity=terminal_identity,
        read_exact=read_exact,
        fetch_exact_to_file=lambda identity, path: path.write_bytes(matrix_raw),
        workspace=tmp_path / "local-reopen-audit",
    )
    assert local_audit["schema_version"] == freeze.LOCAL_REOPEN_AUDIT_SCHEMA
    assert local_audit["provider_execution_bound"] is False
    assert local_audit["publishable_as_reopen_terminal"] is False
    providerless = dict(terminal)
    providerless.pop("provider_execution_receipt")
    providerless.pop("provider_execution_sha256")
    providerless.pop("terminal_sha256")
    providerless = freeze._with_hash(providerless, field="terminal_sha256")
    providerless_raw = freeze.canonical_json_bytes(providerless)
    providerless_identity = _identity(
        "gs://test/providerless-terminal.json", providerless_raw, 230
    )
    objects[providerless_identity["uri"]] = providerless_raw
    with pytest.raises(
        freeze.CorpusR6PaidSourceDiscoveryMatrixFreezeV1Error,
        match="provider execution",
    ):
        freeze.reopen_terminal_registry_v1(
            terminal_identity=providerless_identity, read_exact=read_exact
        )
    reopen_receipt = freeze.reopen_matrix_task_v1(
        reopened_root=reopened,
        source_task_ordinal=0,
        read_exact=read_exact,
        fetch_exact_to_file=lambda identity, path: path.write_bytes(matrix_raw),
        destination=tmp_path / "reopen-matrix.bin",
        runtime_authority=_runtime(manifest, mode="reopen-task"),
    )
    reopen_raw = freeze.canonical_json_bytes(reopen_receipt)
    reopen_identity = _identity(
        manifest["tasks"][0]["reopen_task_uri"], reopen_raw, 24
    )
    reopen_root = freeze.collect_reopen_tasks_v1(
        reopened_root=reopened,
        task_receipts=[reopen_receipt],
        task_receipt_identities=[reopen_identity],
        provider_execution_receipt=_provider(
            manifest,
            payload_identity=terminal_identity,
            mode="reopen-task",
            execution_id="atlas-cbc-32g-full-2023-w8-v1-rop12",
        ),
    )
    assert reopen_root["bounded_54_way_one_slate_reopen"] is True
    assert reopen_root["all_matrix_bytes_generation_exact_reopened"] is True


def test_matrix_fails_closed_on_candidate_order_tamper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    manifest, objects, _, _ = _fixture(monkeypatch)
    tampered = dict(manifest)
    task = dict(tampered["tasks"][0])
    task["ordered_candidate_ids_sha256"] = "f" * 64
    task.pop("task_binding_sha256")
    task = freeze._with_hash(task, field="task_binding_sha256")
    tampered["tasks"] = [task]
    tampered["task_binding_manifest_sha256"] = freeze.canonical_sha256([task])
    tampered.pop("manifest_sha256")
    tampered = freeze._with_hash(tampered, field="manifest_sha256")
    with pytest.raises(
        freeze.CorpusR6PaidSourceDiscoveryMatrixFreezeV1Error,
        match="candidate artifact/order differs",
    ):
        freeze.build_task_matrix_file_v1(
            manifest_value=tampered, source_task_ordinal=0,
            read_exact=lambda identity: objects[identity["uri"]],
            destination=tmp_path / "tampered.bin",
        )
