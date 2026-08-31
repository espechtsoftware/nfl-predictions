from __future__ import annotations

from hashlib import sha256
import inspect
import json

import pytest

from nfl_dfs.research import corpus_r6_matchup_source_task0_v3 as task0
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


def _identity(label: str) -> dict[str, object]:
    raw = source.canonical_json_bytes({"fixture": label})
    return {
        "uri": f"gs://fixture-bucket/task0/{label}.json",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _binding() -> dict[str, object]:
    return {
        "commit_sha": "a" * 40,
        "relative_path": "config/corpus-r6-matchup-capture-plan-v3.json",
        "sha256": "b" * 64,
        "bytes": 123,
        "capture_plan_sha256": "c" * 64,
    }


def _verifier_receipt() -> dict[str, object]:
    budget = {
        "schema_version": "fixture-read-budget/v1",
        "ledger_kind": "fixture",
        "max_object_bytes": 100,
        "max_invocation_read_bytes": 1000,
        "max_read_operations": 10,
        "read_bytes_reserved": 10,
        "read_operations_reserved": 1,
        "read_charge_manifest_sha256": "f" * 64,
        "all_payload_reads_charged_before_access": True,
        "failed_reads_remain_charged": True,
        "per_invocation_only": True,
        "cross_process_durable_ledger": False,
        "exact_read_budget_sha256": "0" * 64,
    }
    body: dict[str, object] = {
        "schema_version": task0.TASK0_VERIFIER_RECEIPT_SCHEMA,
        "complete": True,
        "run_id": "fixture-task0-run",
        "source_task_ordinal": 0,
        "task_id": "fixture-task-0",
        "slate": {"slate_id": "2022-w01", "season": 2022, "week": 1},
        "worker_execution_name": "atlas-job-worker-abc12",
        "verifier_execution_name": "atlas-job-verify-def34",
        "worker_result_identity": _identity("worker"),
        "capture_plan_v3_binding": _binding(),
        "executed_dependency_closure_sha256": "d" * 64,
        "runtime_binding_sha256": "e" * 64,
        "component_task_release_identity": _identity("component"),
        "operator_result_identity": _identity("operator"),
        "candidate_v2_capture_v3_predecessors_deep_reopened": True,
        "one_real_component_ordinal_exact_reopened": True,
        "component_leaf_identity_count_exact_reopened": 49,
        "component_leaf_identity_manifest_sha256": "1" * 64,
        "one_real_source_ordinal_exact_reopened": True,
        "publication_callback_exposed": False,
        "write_inventory_count": 0,
        "ambient_service_account_write_capability": "not_evaluated",
        "cloud_mutation_performed": False,
        "exact_read_cache_budget_summary": budget,
        "transport_read_budget_summary": dict(budget),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    body["task0_verifier_receipt_sha256"] = task0.batch_v3.canonical_sha256(body)
    return body


def _provider_spec(
    *, phase: str, execution: str, run_id: str, payload: bytes,
    worker_execution: str = "DISABLED",
    verifier_execution: str = "DISABLED",
    publisher_execution: str = "DISABLED",
) -> dict[str, object]:
    return {
        "schema_version": task0.TASK0_PROVIDER_EXECUTION_SPEC_SCHEMA,
        "phase": phase,
        "project": task0.PROVIDER_PROJECT,
        "region": task0.PROVIDER_REGION,
        "job": task0.PROVIDER_JOB,
        "job_uid": task0.PROVIDER_JOB_UID,
        "job_generation": "17",
        "execution_name": execution,
        "execution_uid": "12345678-1234-4234-8234-123456789abc",
        "completion_time": "2026-08-30T12:34:56.123Z",
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "timeout_seconds": "86400s",
        "service_account": task0.PROVIDER_SERVICE_ACCOUNT,
        "cpu": "8",
        "memory": "32Gi",
        "command": ["/bin/bash"],
        "args": [task0.PROVIDER_CONTROLLER_PATH, "container-run", phase],
        "image_uri": (
            "us-central1-docker.pkg.dev/nfl-predictions-503414/"
            f"nfl-dfs/nfl-dfs@sha256:{'2' * 64}"
        ),
        "image_digest": f"sha256:{'2' * 64}",
        "code_sha": "3" * 40,
        "image_source_commit_sha": "3" * 40,
        "build_id": "12345678-1234-4234-8234-123456789abc",
        "mode": phase,
        "outcomes_allowed": False,
        "request_run_id": run_id,
        "payload_sha256": sha256(payload).hexdigest(),
        "payload_bytes": len(payload),
        "bound_worker_execution": worker_execution,
        "bound_verifier_execution": verifier_execution,
        "bound_publisher_execution": publisher_execution,
        "succeeded_count": 1,
        "failed_count": 0,
        "cancelled_count": 0,
        "running_count": 0,
    }


def _provider_receipt_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], dict[str, object]]:
    run_id = "fixture-task0-run"
    worker_execution = "atlas-job-worker-abc12"
    verifier_execution = "atlas-job-verify-def34"
    root_uri = "gs://fixture-bucket/task0/worker.json"
    worker_root = {
        "worker_execution_name": worker_execution,
        "output_uri_inventory": {"result_root_uri": root_uri},
    }
    worker_output = {
        "schema_version": "corpus-r6-matchup-source-task0-worker-publication/v3",
        "complete": True,
        "run_id": run_id,
        "worker_execution_name": worker_execution,
        "worker_result": worker_root,
        "worker_result_identity": {**_identity("worker"), "uri": root_uri},
        "task0_result_root_was_final_create_once_request": True,
    }
    monkeypatch.setattr(
        task0,
        "validate_task0_worker_result_structure_v3",
        lambda value: dict(value),
    )
    worker = task0._build_task0_provider_receipt_v3(
        provider_execution_spec=_provider_spec(
            phase="worker", execution=worker_execution, run_id=run_id,
            payload=b"{}",
        ),
        operator_output=worker_output,
    )
    worker_raw = task0.batch_v3.canonical_json_bytes(worker) + b"\n"
    verifier = task0._build_task0_provider_receipt_v3(
        provider_execution_spec=_provider_spec(
            phase="verify", execution=verifier_execution, run_id=run_id,
            payload=worker_raw, worker_execution=worker_execution,
        ),
        operator_output=_verifier_receipt(),
        worker_provider_receipt=worker,
    )
    return worker, verifier


def test_task0_inventory_is_exact_sorted_and_includes_real_component_leaves() -> None:
    inventory = task0._output_inventory(
        run_id="fixture-task0-run",
        slate={"slate_id": "2022-w01", "season": 2022, "week": 1},
    )
    assert inventory["uris"] == sorted(inventory["uris"])
    assert len(inventory["uris"]) == len(set(inventory["uris"]))
    assert inventory["uri_count"] > 7
    assert any("candidate-support-rows.json" in uri for uri in inventory["uris"])
    assert any("/slices/" in uri for uri in inventory["uris"])
    assert inventory["result_root_uri"].endswith(task0.TASK0_RESULT_FILENAME)
    assert task0._validate_output_inventory(inventory) == inventory


def test_worker_and_verifier_are_default_off_before_cloud_or_git(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(task0.WORKER_ENABLE_ENV, raising=False)
    monkeypatch.delenv(task0.VERIFIER_ENABLE_ENV, raising=False)
    monkeypatch.setattr(
        task0.batch_v3,
        "_validate_local_context_v3",
        lambda: pytest.fail("local/cloud prerequisites must not be reached"),
    )
    with pytest.raises(task0.CorpusR6MatchupSourceTask0V3Error, match="requires"):
        task0.publish_task0_worker_v3(run_id="fixture-task0-run")
    with pytest.raises(task0.CorpusR6MatchupSourceTask0V3Error, match="requires"):
        task0.verify_task0_worker_v3(worker_result_identity=_identity("worker"))
    assert set(inspect.signature(task0.verify_task0_worker_v3).parameters) == {
        "worker_result_identity"
    }


def test_verifier_receipt_is_distinct_read_only_and_binds_full_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _verifier_receipt()
    assert task0.validate_task0_verifier_receipt_v3(receipt) == receipt
    _, provider_receipt = _provider_receipt_pair(monkeypatch)
    closure = {"dependency_closure_sha256": "d" * 64}
    runtime = {"runtime_binding_sha256": "e" * 64}
    monkeypatch.setattr(
        task0.batch_v3,
        "_validate_local_context_v3",
        lambda: (closure, runtime, {}, _binding(), b"{}"),
    )
    monkeypatch.setenv(
        task0.BOUND_WORKER_EXECUTION_ENV, receipt["worker_execution_name"]
    )
    monkeypatch.setenv(
        task0.BOUND_VERIFIER_EXECUTION_ENV, receipt["verifier_execution_name"]
    )
    provider_raw = task0.batch_v3.canonical_json_bytes(provider_receipt) + b"\n"
    provider_identity = {
        "uri": (
            "gs://nfl-predictions-503414-corpus-source/research/"
            "corpus-r6-matchup-source-controller-v3/fixture-task0-run/verify/"
            "atlas-job-verify-def34/provider-receipt.json"
        ),
        "generation": "17",
        "sha256": sha256(provider_raw).hexdigest(),
        "bytes": len(provider_raw),
    }

    class ExactReadOnlyTransport:
        def read_exact(self, identity: object) -> bytes:
            assert identity == provider_identity
            return provider_raw

    monkeypatch.setattr(
        task0.batch_mechanics,
        "_trusted_gcs_transport_v1",
        lambda *, expected_write_uris: ExactReadOnlyTransport(),
    )
    with pytest.raises(
        task0.CorpusR6MatchupSourceTask0V3Error,
        match="controller provider receipt",
    ):
        task0.authorize_full_publication_v3(
            provider_receipt, expected_run_id="fixture-task0-run"
        )
    gate = task0.authorize_full_publication_v3(
        provider_identity, expected_run_id="fixture-task0-run"
    )
    assert gate["full_publication_gate_passed"] is True
    assert gate["publication_callback_exposed"] is False
    assert gate["write_inventory_count"] == 0
    assert gate["ambient_service_account_write_capability"] == "not_evaluated"
    assert gate["verifier_provider_receipt"] == provider_receipt
    assert gate["verifier_provider_receipt_identity"] == provider_identity
    assert task0.validate_full_publication_authorization_v3(gate) == gate
    assert (
        task0.revalidate_full_publication_authorization_provider_source_v3(gate)
        == gate
    )
    with pytest.raises(
        task0.CorpusR6MatchupSourceTask0V3Error,
        match="provider",
    ):
        task0.authorize_full_publication_v3(
            receipt, expected_run_id="fixture-task0-run"
        )
    with pytest.raises(
        task0.CorpusR6MatchupSourceTask0V3Error, match="execution binding"
    ):
        task0.authorize_full_publication_v3(
            provider_identity, expected_run_id="different-task0-run"
        )
    changed = dict(receipt)
    changed["verifier_execution_name"] = changed["worker_execution_name"]
    changed.pop("task0_verifier_receipt_sha256")
    changed["task0_verifier_receipt_sha256"] = task0.batch_v3.canonical_sha256(
        changed
    )
    with pytest.raises(task0.CorpusR6MatchupSourceTask0V3Error, match="distinct"):
        task0.validate_task0_verifier_receipt_v3(changed)


def test_provider_bound_independent_reopen_is_distinct_and_write_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "fixture-task0-run"
    worker = "atlas-job-worker-abc12"
    verifier = "atlas-job-verify-def34"
    publisher = "atlas-job-publish-ghi56"
    reopener = "atlas-job-reopen-jkl78"
    batch_identity = _identity("batch-release")
    verifier_provider_identity = {
        "uri": (
            "gs://nfl-predictions-503414-corpus-source/research/"
            "corpus-r6-matchup-source-controller-v3/fixture-task0-run/verify/"
            "atlas-job-verify-def34/provider-receipt.json"
        ),
        "generation": "17",
        "sha256": "b" * 64,
        "bytes": 1234,
    }
    publication: dict[str, object] = {
        "schema_version": task0.PROVIDER_PUBLICATION_STDOUT_SCHEMA,
        "complete": True,
        "run_id": run_id,
        "batch_release_identity": batch_identity,
        "source_release_v3_identity": _identity("source-release"),
        "task_count": 54,
        "terminal_batch_root_requested_last": True,
        "same_process_deep_reopen_complete": True,
        "independent_process_deep_reopen_complete": False,
        "independent_process_deep_reopen_required": True,
        "task0_full_publication_authorization_sha256": "a" * 64,
        "task0_worker_execution_name": worker,
        "task0_verifier_execution_name": verifier,
        "task0_verifier_provider_receipt_identity": verifier_provider_identity,
        "task0_verifier_provider_receipt_sha256": "c" * 64,
        "cloud_mutation_performed": True,
        "full_publication_receipt_sha256": "d" * 64,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    publication["provider_publication_stdout_sha256"] = (
        task0.batch_v3.canonical_sha256(publication)
    )
    provider = task0._build_task0_provider_receipt_v3(
        provider_execution_spec=_provider_spec(
            phase="publish", execution=publisher, run_id=run_id,
            payload=(
                task0.batch_v3.canonical_json_bytes(verifier_provider_identity)
                + b"\n"
            ),
            worker_execution=worker, verifier_execution=verifier,
        ),
        operator_output=publication,
    )
    mismatched_publication = dict(publication)
    mismatched_publication["task0_worker_execution_name"] = (
        "atlas-job-wrong-mno90"
    )
    mismatched_publication.pop("provider_publication_stdout_sha256")
    mismatched_publication["provider_publication_stdout_sha256"] = (
        task0.batch_v3.canonical_sha256(mismatched_publication)
    )
    with pytest.raises(
        task0.CorpusR6MatchupSourceTask0V3Error,
        match="publish provider stdout",
    ):
        task0._build_task0_provider_receipt_v3(
            provider_execution_spec=_provider_spec(
                phase="publish", execution=publisher, run_id=run_id,
                payload=(
                    task0.batch_v3.canonical_json_bytes(
                        verifier_provider_identity
                    ) + b"\n"
                ),
                worker_execution=worker, verifier_execution=verifier,
            ),
            operator_output=mismatched_publication,
        )
    provider_raw = task0.batch_v3.canonical_json_bytes(provider) + b"\n"
    provider_identity = {
        "uri": (
            "gs://nfl-predictions-503414-corpus-source/research/"
            "corpus-r6-matchup-source-controller-v3/fixture-task0-run/publish/"
            "atlas-job-publish-ghi56/provider-receipt.json"
        ),
        "generation": "19",
        "sha256": sha256(provider_raw).hexdigest(),
        "bytes": len(provider_raw),
    }
    budget = _verifier_receipt()["exact_read_cache_budget_summary"]
    monkeypatch.setattr(
        task0,
        "_exact_reopen_provider_receipt_v3",
        lambda value: (provider, provider_identity)
        if value == provider_identity
        else pytest.fail("publication identity differs"),
    )
    monkeypatch.setenv(task0.BOUND_PUBLISHER_EXECUTION_ENV, publisher)
    monkeypatch.setenv(task0.EXECUTION_NAME_ENV, reopener)
    monkeypatch.setattr(
        task0.batch_v3,
        "reopen_matchup_source_batch_outer_candidate_authority_v3",
        lambda *, batch_release_identity: {
            "batch_release_identity": batch_release_identity,
            "source_release_v3_identity": _identity("source-release"),
            "source_task_count": 54,
            "source_task_ordinals_reopened": list(range(54)),
            "task0_full_publication_authorization_sha256": "a" * 64,
            "task0_full_publication_authorization": {
                "verifier_provider_receipt_identity": verifier_provider_identity,
            },
            "task0_worker_execution_name": worker,
            "task0_verifier_execution_name": verifier,
            "candidate_v2_capture_v3_component_v3_source_v3_deep_reopen_complete": True,
            "write_disabled_public_reopen_complete": True,
            "write_capability_enabled": False,
            "cloud_mutation_performed": False,
            "exact_read_cache_budget_receipt": budget,
            "transport_read_budget_receipt": dict(budget),
        },
    )
    receipt = task0.independently_reopen_provider_publication_v3(
        publication_provider_receipt_identity=provider_identity
    )
    assert receipt["publisher_execution_name"] == publisher
    assert receipt["reopen_execution_name"] == reopener
    assert receipt["publication_callback_exposed"] is False
    assert receipt["write_inventory_count"] == 0
    assert receipt["write_capability_enabled"] is False
    assert task0.validate_independent_reopen_receipt_v3(receipt) == receipt
    with pytest.raises(
        task0.CorpusR6MatchupSourceTask0V3Error,
        match="reopen provider/predecessor binding",
    ):
        task0._build_task0_provider_receipt_v3(
            provider_execution_spec=_provider_spec(
                phase="reopen", execution=reopener, run_id=run_id,
                payload=(
                    task0.batch_v3.canonical_json_bytes(provider_identity) + b"\n"
                ),
                worker_execution="atlas-job-wrong-mno90",
                verifier_execution=verifier,
                publisher_execution=publisher,
            ),
            operator_output=receipt,
        )


def test_worker_publishes_bounded_inventory_and_result_root_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "fixture-task0-run"
    slate = {"slate_id": "2022-w01", "season": 2022, "week": 1}
    inventory = task0._output_inventory(run_id=run_id, slate=slate)

    class Transport:
        def __init__(self) -> None:
            self.expected = list(inventory["uris"])
            self.store: dict[str, bytes] = {}
            self.order: list[str] = []

        def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
            assert uri in self.expected and uri not in self.store
            self.store[uri] = raw
            self.order.append(uri)
            return {"uri": uri, "generation": str(len(self.order)),
                    "sha256": sha256(raw).hexdigest(), "bytes": len(raw)}

        def read_exact(self, identity: dict[str, object]) -> bytes:
            return self.store[str(identity["uri"])]

        def write_budget_receipt(self) -> dict[str, object]:
            completed = sorted(self.store)
            return {"expected_write_uris": self.expected,
                    "completed_write_uris": completed,
                    "pending_write_uris": sorted(set(self.expected) - set(completed))}

        def require_completed_exactly_v1(
            self, *, completed_uris: list[str], pending_uris: list[str]
        ) -> None:
            assert sorted(completed_uris) == sorted(self.store)
            assert list(pending_uris) == []

        def read_budget_receipt(self) -> dict[str, object]:
            return {"fixture": True}

    transport = Transport()
    binding = _binding()
    root_identity = _identity("candidate-root")
    closure = {"dependency_closure_sha256": "d" * 64}
    runtime = {"runtime_binding_sha256": "e" * 64}
    plan = {
        "source_task_bindings": [{"task_id": "fixture-task-0", "slate": slate}],
        "fixed_g0_candidate_authority_root_identity": root_identity,
        "producer_id": "fixture-producer",
        "component_producer_code_identity": {"fixture": "code"},
    }
    candidate_identity = _identity("candidate-release")
    catalog_identity = _identity("catalog")
    upstream_identity = _identity("upstream")
    replay_identity = _identity("replay")
    catalog_release_identity = _identity("catalog-release")
    candidate_artifact_identity = _identity("candidate-artifact")
    inner = {
        "receipt": {}, "receipt_identity": replay_identity,
        "catalog_release": {}, "catalog_release_identity": catalog_release_identity,
        "structural_catalogs": [{"fixture": "catalog"}],
        "candidate_release": {"entries": [{
            "candidate_artifact_identity": candidate_artifact_identity,
        }]},
        "candidate_release_identity": candidate_identity,
    }
    monkeypatch.setenv(task0.WORKER_ENABLE_ENV, task0.WORKER_ENABLE_VALUE)
    monkeypatch.setenv(task0.EXECUTION_NAME_ENV, "atlas-job-worker-abc12")
    monkeypatch.setattr(
        task0.batch_v3, "_validate_local_context_v3",
        lambda: (closure, runtime, plan, binding, b"{}"),
    )
    monkeypatch.setattr(
        task0.batch_mechanics, "_trusted_gcs_transport_v1",
        lambda *, expected_write_uris: transport,
    )
    monkeypatch.setattr(
        task0.batch_v3, "_trusted_remote_prerequisites_v3",
        lambda **kwargs: {"upstream_source_release": {},
                          "upstream_source_release_identity": upstream_identity,
                          "upstream_pack_row_objects": []},
    )
    monkeypatch.setattr(task0.batch_v3, "_deep_validate_capture_plan_v3", lambda **kwargs: {})
    monkeypatch.setattr(task0.component_v3, "_open_candidate", lambda **kwargs: ({}, {}))
    monkeypatch.setattr(task0.component_v3, "_require_plan_candidate_equality", lambda **kwargs: None)
    monkeypatch.setattr(task0.component_v3, "_derive_inner_inputs", lambda **kwargs: inner)
    monkeypatch.setattr(task0.batch_v3, "_trusted_dependency_closure_v3", lambda: closure)
    monkeypatch.setattr(task0.batch_v3, "_build_runtime_binding_v3", lambda value: runtime)
    monkeypatch.setattr(task0.batch_v3, "_operator_code_identity", lambda value: {"fixture": "operator"})

    def fake_component(**kwargs: object) -> dict[str, object]:
        materialize = kwargs["body_materializer"]
        assert callable(materialize)
        identities: dict[str, dict[str, object]] = {}
        for uri in inventory["uris"]:
            if "/producer/" not in uri or uri.endswith(task0.TASK0_COMPONENT_ROOT_FILENAME):
                continue
            raw = json.dumps({"uri": uri}, sort_keys=True, separators=(",", ":")).encode()
            identities[uri] = dict(materialize(uri, raw))
        task_prefix = task0._task_prefix(run_id=run_id, slate_id="2022-w01")
        bundle_uri = f"{task_prefix}producer/component-input-bundle.json"
        receipt_uri = f"{task_prefix}producer/component-producer-receipt.json"
        body = {
            "schema_version": task0.producer_v1.ONE_TASK_RESULT_SCHEMA,
            "source_task_ordinal": 0, "task_id": "fixture-task-0", "slate": slate,
            "fixed_g0_replay_receipt_identity": replay_identity,
            "catalog_release_identity": catalog_release_identity,
            "catalog_identity": catalog_identity,
            "accepted_candidate_release_identity": candidate_identity,
            "upstream_source_release_identity": upstream_identity,
            "producer_code_identity": {"fixture": "code"},
            "input_bundle": {"fixture": "bundle"},
            "input_bundle_identity": identities[bundle_uri],
            "producer_receipt": {"fixture": "receipt"},
            "producer_receipt_identity": identities[receipt_uri],
            "support_preflight_passed": True,
        }
        body["one_task_result_sha256"] = task0.batch_v3.canonical_sha256(body)
        return body

    monkeypatch.setattr(task0.producer_v1, "produce_one_component_task_v1", fake_component)

    def fake_operator(**kwargs: object) -> dict[str, object]:
        publish = kwargs["publish_create_once"]
        prefix = str(kwargs["output_prefix"])
        identities = []
        for filename in ("matchup-source-export.json", "matchup-capture-receipt.json",
                         "matchup-operator-result.json"):
            raw = json.dumps({"filename": filename}, sort_keys=True,
                             separators=(",", ":")).encode()
            identities.append(dict(publish(f"{prefix}{filename}", raw)))
        return {"task_id": "fixture-task-0", "slate": slate,
                "source_export_identity": identities[0],
                "capture_receipt_identity": identities[1],
                "operator_result_identity": identities[2]}

    monkeypatch.setattr(task0.operator_v2, "publish_matchup_source_triple_v2", fake_operator)
    result = task0.publish_task0_worker_v3(run_id=run_id)
    assert result["complete"] is True
    assert transport.order[-1] == inventory["result_root_uri"]
    assert sorted(transport.store) == inventory["uris"]
    assert result["worker_result_identity"]["uri"] == inventory["result_root_uri"]
    component_root_uri = next(
        uri for uri in inventory["uris"]
        if uri.endswith(task0.TASK0_COMPONENT_ROOT_FILENAME)
    )
    component_root = json.loads(transport.store[component_root_uri])
    expected_leaf_uris = sorted(
        uri for uri in inventory["uris"]
        if "/producer/" in uri
        and not uri.endswith(task0.TASK0_COMPONENT_ROOT_FILENAME)
    )
    assert component_root["component_object_identity_count"] == len(
        expected_leaf_uris
    )
    assert [
        row["uri"] for row in component_root["component_object_identities"]
    ] == expected_leaf_uris
