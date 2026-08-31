from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import (
    corpus_r6_construction_allocation_collector_repair_v1 as repair,
)
from scripts import (
    run_corpus_r6_construction_allocation_collector_repair_v1 as runner,
)


REPAIR_CODE = "a" * 40
REPAIR_IMAGE = "us-central1-docker.pkg.dev/x/y/z@sha256:" + "b" * 64
REPAIR_BUILD = "12345678-1234-1234-1234-123456789abc"
BUILD_IDENTITY = {
    "uri": "gs://fixture/repair-build.json",
    "generation": "7",
    "sha256": "c" * 64,
    "bytes": 100,
}


def _envelope() -> dict[str, object]:
    return {
        "schema_version": (
            "corpus-r6-construction-allocation-terminal-envelope/v1"
        ),
        "terminal_identity": {
            "uri": repair.TERMINAL_URI,
            "generation": "2",
            "sha256": "d" * 64,
            "bytes": 200,
            "create_once": True,
        },
        "selection_identity": {
            "uri": repair.SELECTION_URI,
            "generation": "1",
            "sha256": "e" * 64,
            "bytes": 150,
            "create_once": True,
        },
        "runtime_execution_attestation_identity": dict(
            repair.SOURCE_EXECUTION_ATTESTATION_IDENTITY
        ),
        "envelope_sha256": "f" * 64,
        "complete": True,
        "create_once": True,
        "uses_target_slate_outcomes": False,
    }


def _source_collect() -> dict[str, object]:
    return {
        "schema_version": (
            "corpus-r6-construction-allocation-snapshot-shard-collect/v1"
        ),
        "manifest_identity": dict(repair.SOURCE_MANIFEST_IDENTITY),
        "shard_count": 54,
        "shard_identities_sha256": "1" * 64,
        "selection_receipt_sha256": "2" * 64,
        "terminal_envelope": _envelope(),
        "all_shards_generation_exact_reopened": True,
        "input_manifest_and_ordered_shards_generation_exact_reopened": True,
        "runtime_execution_provider_attestation_exact_reopened": True,
        "outcome_data_accessed": False,
        "grading_performed": False,
        "complete": True,
    }


def _repair_result(phase: str) -> dict[str, object]:
    prior = None
    if phase == "reopen":
        prior = {
            "phase": "collect",
            "execution_name": repair.JOB_NAME + "-abcde",
            "execution_uid": "collect-uid",
        }
    request = repair.request_v1(
        phase=phase,
        collector_runtime_build_attestation_identity=BUILD_IDENTITY,
        prior_repair_execution=prior,
    )
    return repair.collect_result_v1(
        request=request,
        collector_code_sha=REPAIR_CODE,
        collector_image=REPAIR_IMAGE,
        collector_build_id=REPAIR_BUILD,
        source_collect_result=_source_collect(),
    )


def _execution(phase: str, suffix: str) -> dict[str, object]:
    return repair.repair_execution_v1(
        phase=phase,
        code_sha=REPAIR_CODE,
        image=REPAIR_IMAGE,
        build_id=REPAIR_BUILD,
        job_generation="43",
        execution_name=repair.JOB_NAME + "-" + suffix,
        execution_uid=phase + "-uid",
        completion_time="2026-08-31T03:00:00Z",
    )


def test_request_is_one_use_and_source_runtime_is_frozen() -> None:
    request = repair.request_v1(
        phase="collect",
        collector_runtime_build_attestation_identity=BUILD_IDENTITY,
    )
    assert repair.validate_request_v1(request) == request
    assert request["source_code_sha"] == repair.SOURCE_CODE_SHA
    assert request["source_image"] == repair.SOURCE_IMAGE
    assert request["failed_collect_execution"] == repair.FAILED_COLLECT_EXECUTION
    assert (
        request["failed_repair_v1_execution"]
        == repair.FAILED_REPAIR_V1_EXECUTION
    )
    assert request["immutable_execution_label_is_generation_authority"] is True
    assert request["shard_recomputation_licensed"] is False
    assert request["target_slate_outcomes_allowed"] is False

    forged = deepcopy(request)
    forged["failed_collect_execution"]["name"] = repair.JOB_NAME + "-other"
    body = dict(forged)
    body.pop("request_sha256")
    forged["request_sha256"] = repair.digest(body)
    with pytest.raises(repair.CollectorRepairV1Error):
        repair.validate_request_v1(forged)


def test_exact_failed_repair_v1_request_is_retained_as_ancestry() -> None:
    body = {
        "schema_version": repair.LEGACY_REQUEST_SCHEMA,
        "version": repair.LEGACY_VERSION,
        "phase": "collect",
        "source_manifest_identity": dict(repair.SOURCE_MANIFEST_IDENTITY),
        "source_code_sha": repair.SOURCE_CODE_SHA,
        "source_image": repair.SOURCE_IMAGE,
        "source_build_id": repair.SOURCE_BUILD_ID,
        "source_execution_name": repair.SOURCE_EXECUTION_NAME,
        "source_execution_uid": repair.SOURCE_EXECUTION_UID,
        "source_runtime_execution_attestation_identity": dict(
            repair.SOURCE_EXECUTION_ATTESTATION_IDENTITY
        ),
        "failed_collect_execution": dict(repair.FAILED_COLLECT_EXECUTION),
        "collector_runtime_build_attestation_identity": dict(
            repair.FAILED_REPAIR_V1_BUILD_ATTESTATION_IDENTITY
        ),
        "prior_repair_execution": None,
        "selection_uri": repair.SELECTION_URI,
        "terminal_uri": repair.TERMINAL_URI,
        "repair_receipt_uri": repair.LEGACY_REPAIR_RECEIPT_URI,
        "source_and_collector_runtime_are_distinct": True,
        "existing_54_shards_are_only_selection_authority": True,
        "shard_recomputation_licensed": False,
        "target_slate_outcomes_allowed": False,
        "automatic_relaunch_licensed": False,
    }
    request = {**body, "request_sha256": repair.digest(body)}
    raw = repair.canonical_bytes(request, newline=True)
    assert repair.validate_failed_repair_v1_request(request) == request
    assert request["request_sha256"] == repair.FAILED_REPAIR_V1_EXECUTION[
        "request_sha256"
    ]
    assert sha256(raw).hexdigest() == repair.FAILED_REPAIR_V1_EXECUTION[
        "request_transport_sha256"
    ]

    forged = deepcopy(request)
    forged["phase"] = "reopen"
    forged_body = dict(forged)
    forged_body.pop("request_sha256")
    forged["request_sha256"] = repair.digest(forged_body)
    with pytest.raises(repair.CollectorRepairV1Error):
        repair.validate_failed_repair_v1_request(forged)


def test_reopen_requires_exact_prior_collect_coordinate() -> None:
    with pytest.raises(repair.CollectorRepairV1Error):
        repair.request_v1(
            phase="reopen",
            collector_runtime_build_attestation_identity=BUILD_IDENTITY,
            prior_repair_execution={
                "phase": "reopen",
                "execution_name": repair.JOB_NAME + "-abcde",
                "execution_uid": "uid",
            },
        )


def test_sidecar_binds_old_science_to_two_new_collector_executions() -> None:
    collected = _repair_result("collect")
    reopened = _repair_result("reopen")
    closure = {
        "complete": True,
        "outcome_data_accessed": False,
        "post_lock_data_read": False,
        "terminal_envelope": _envelope(),
        "upstream_reopen_receipt": {
            "fixed_g0_panel_reopen": {
                "panel_id": repair.cross.FOUNDRY_G0_PANEL_ID,
                "panel_index_sha256": (
                    "479b65bb40fcab6ba6721431718c8e2e95fc0a28a4354f1e7b3b1e205c69b094"
                ),
                "accepted_slate_count": 54,
            },
        },
        "execution_authority": {
            "task_count": 54,
            "ordered_shard_identities_sha256": "1" * 64,
            "runtime_execution_attestation_identity": dict(
                repair.SOURCE_EXECUTION_ATTESTATION_IDENTITY
            ),
        },
    }
    receipt = repair.receipt_v1(
        collect_result=collected,
        reopen_result=reopened,
        collect_execution=_execution("collect", "abcde"),
        reopen_execution=_execution("reopen", "fghij"),
        selection_reopen_receipt=closure,
    )
    assert repair.validate_receipt_v1(receipt) == receipt
    assert receipt["source_code_sha"] == repair.SOURCE_CODE_SHA
    assert receipt["collector_code_sha"] == REPAIR_CODE
    assert receipt["shard_recomputation_performed"] is False
    assert receipt["selection_terminal_v1_unchanged"] is True
    assert receipt["failed_repair_v1_execution"] == repair.FAILED_REPAIR_V1_EXECUTION
    assert receipt["corrected_invalid_predicates"] == [
        "panel_index_sha256-equals-panel_id-suffix",
        "current-job-generation-equals-frozen-execution-generation",
    ]


def test_container_collect_passes_source_runtime_only_to_legacy_collector(
    monkeypatch,
) -> None:
    request = repair.request_v1(
        phase="collect",
        collector_runtime_build_attestation_identity=BUILD_IDENTITY,
    )
    monkeypatch.setattr(runner, "_request_from_environment", lambda: request)
    monkeypatch.setattr(
        runner,
        "_validate_collector_runtime",
        lambda request, *, store, provider: (
            REPAIR_CODE, REPAIR_IMAGE, REPAIR_BUILD
        ),
    )
    monkeypatch.setattr(runner, "_assert_known_output_state", lambda **_: None)
    monkeypatch.setattr(runner, "_validate_failure_chain", lambda: None)
    monkeypatch.setattr(runner.source_runner, "GCSExactKnownNameStoreV1", object)
    monkeypatch.setattr(runner.source_runner, "GCloudBuildProviderV1", lambda **_: object())
    observed: dict[str, object] = {}

    def collect(**kwargs):
        observed.update(kwargs)
        return _source_collect()

    monkeypatch.setattr(runner.source_runner, "collect_v1", collect)
    result = runner.container_collect_v1()
    assert result["collector_code_sha"] == REPAIR_CODE
    assert observed["manifest_identity"] == repair.SOURCE_MANIFEST_IDENTITY
    assert (
        observed["runtime_execution_attestation_identity"]
        == repair.SOURCE_EXECUTION_ATTESTATION_IDENTITY
    )
    assert observed["environment"][runner.SOURCE_CODE_ENV] == repair.SOURCE_CODE_SHA
    assert (
        observed["environment"][runner.SOURCE_IMAGE_DIGEST_ENV]
        == repair.SOURCE_IMAGE_DIGEST
    )
