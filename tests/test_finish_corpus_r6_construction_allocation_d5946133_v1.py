from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "scripts"
    / "finish_corpus_r6_construction_allocation_d5946133_v1.py"
)
SPEC = importlib.util.spec_from_file_location("construction_finisher", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
finisher = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = finisher
SPEC.loader.exec_module(finisher)


def _identity(name: str, ordinal: int = 1, *, create_once: bool = False) -> dict:
    value = {
        "uri": f"gs://fixture/{name}.json",
        "generation": str(ordinal),
        "sha256": f"{ordinal % 16:x}" * 64,
        "bytes": 100 + ordinal,
    }
    if create_once:
        value["create_once"] = True
    return value


def _selection_envelope() -> dict:
    value = {
        "schema_version": (
            "corpus-r6-construction-allocation-terminal-envelope/v1"
        ),
        "terminal_identity": _identity("selection-terminal", 1, create_once=True),
        "terminal_sha256": "1" * 64,
        "selection_identity": _identity("selection", 2, create_once=True),
        "selection_receipt_sha256": "2" * 64,
        "runtime_build_attestation_identity": _identity(
            "runtime-build", 3, create_once=True
        ),
        "execution_authority_sha256": "3" * 64,
        "execution_reopen_receipt_sha256": "4" * 64,
        "runtime_execution_attestation_identity": _identity(
            "runtime-execution", 4, create_once=True
        ),
        "multiplicity_family_sha256": "5" * 64,
        "independent_audit_evaluation_authority_available": False,
        "unconsumed_audit_placeholder_count": 54,
        "upstream_reopen_receipt_sha256": "6" * 64,
        "complete": True,
        "create_once": True,
        "uses_target_slate_outcomes": False,
    }
    value["envelope_sha256"] = finisher.canonical_sha256(value)
    return value


def _collect_result() -> dict:
    value = {
        "schema_version": finisher.COLLECT_SCHEMA,
        "manifest_identity": dict(finisher.SOURCE_MANIFEST_IDENTITY),
        "manifest_sha256": "7" * 64,
        "provider_build_receipt": {"provider_observed": True},
        "provider_execution_receipt": {
            "identity": _identity("runtime-execution", 4),
            "job_name": finisher.JOB,
            "job_generation": finisher.JOB_GENERATION,
            "execution_name": finisher.SOURCE_EXECUTION_NAME,
            "execution_uid": finisher.SOURCE_EXECUTION_UID,
            "task_count": 54,
            "succeeded_count": 54,
            "image_digest": finisher.IMAGE_DIGEST,
            "code_sha": finisher.CODE_SHA,
            "provider_observed": True,
        },
        "shard_count": 54,
        "shard_identities_sha256": "8" * 64,
        "selection_receipt_sha256": "9" * 64,
        "terminal_envelope": _selection_envelope(),
        "terminal_reopen_complete": True,
        "all_shards_resolved_by_deterministic_name_without_listing": True,
        "all_shards_generation_exact_reopened": True,
        "selection_published_before_terminal_root": True,
        "selection_upstream_authorities_generation_exact_reopened": True,
        "input_manifest_and_ordered_shards_generation_exact_reopened": True,
        "runtime_execution_provider_attestation_exact_reopened": True,
        "audit_placeholders_have_evaluation_authority": False,
        "outcome_data_accessed": False,
        "grading_performed": False,
        "deployment_mutation_performed": False,
        "execution_launched": False,
        "automatic_relaunch": False,
        "complete": True,
    }
    value["collect_sha256"] = finisher.canonical_sha256(value)
    return value


def _grade_prepared_result() -> dict:
    return {
        "schema_version": finisher.GRADE_PREPARED_SCHEMA,
        "manifest_identity": _identity("grade-manifest", 10, create_once=True),
        "manifest_sha256": "a" * 64,
        "selection_terminal_identity": _selection_envelope()["terminal_identity"],
        "outcome_authority_identity": dict(finisher.OUTCOME_COMPLETION_IDENTITY),
        "outcome_authority_opened": False,
        "uses_realized_outcomes": False,
        "complete": True,
    }


def _grade_envelope() -> dict:
    value = {
        "schema_version": (
            "corpus-r6-construction-allocation-grade-terminal-envelope/v1"
        ),
        "terminal_identity": _identity("grade-terminal", 11, create_once=True),
        "terminal_sha256": "b" * 64,
        "manifest_identity": _grade_prepared_result()["manifest_identity"],
        "manifest_sha256": "a" * 64,
        "historical_outcome_lease_identity": dict(
            finisher.HISTORICAL_OUTCOME_LEASE_IDENTITY
        ),
        "terminal_root_was_last_scientific_publication": True,
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": "external-launcher-watcher",
        "complete": True,
    }
    value["envelope_sha256"] = finisher.canonical_sha256(value)
    return value


def _grade_result() -> dict:
    envelope = _grade_envelope()
    return {
        "schema_version": finisher.GRADE_PUBLISHED_SCHEMA,
        "terminal_envelope": envelope,
        "terminal_identity": envelope["terminal_identity"],
        "grade_report_identity": _identity("grade-report", 12, create_once=True),
        "historical_outcome_lease_identity": dict(
            finisher.HISTORICAL_OUTCOME_LEASE_IDENTITY
        ),
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": "external-launcher-watcher",
        "historical_outcome_lease_released": False,
        "terminal_reopen_receipt_sha256": "c" * 64,
        "uses_realized_outcomes": True,
        "automatic_retry_licensed": False,
        "complete": True,
    }


def _grade_reopen_result() -> dict:
    receipt = {
        "schema_version": "corpus-r6-construction-allocation-grade-reopen/v1",
        "terminal_identity": _grade_envelope()["terminal_identity"],
        "terminal_sha256": "b" * 64,
        "manifest_identity": _grade_prepared_result()["manifest_identity"],
        "selection_terminal_identity": _selection_envelope()["terminal_identity"],
        "outcome_authority_identity": dict(finisher.OUTCOME_COMPLETION_IDENTITY),
        "outcome_snapshot_identity": dict(finisher.OUTCOME_SNAPSHOT_IDENTITY),
        "historical_outcome_lease_identity": dict(
            finisher.HISTORICAL_OUTCOME_LEASE_IDENTITY
        ),
        "historical_outcome_lease_body_sha256": "d" * 64,
        "historical_outcome_lease_unchanged_during_reopen": True,
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": "external-launcher-watcher",
        "grade_report_identity": _identity("grade-report", 12, create_once=True),
        "outcome_document_count": 54,
        "selection_predecessor_closure_replayed": True,
        "outcome_predecessor_closure_replayed": True,
        "all_grade_children_generation_exact_reopened": True,
        "grade_independently_recomputed": True,
        "object_listing_used": False,
        "overwrite_used": False,
        "scientific_object_delete_used": False,
        "uses_realized_outcomes": True,
        "complete": True,
    }
    receipt["reopen_sha256"] = finisher.canonical_sha256(receipt)
    return {
        "schema_version": finisher.GRADE_REOPEN_SCHEMA,
        "reopen_receipt": receipt,
        "historical_outcome_lease_identity": dict(
            finisher.HISTORICAL_OUTCOME_LEASE_IDENTITY
        ),
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": "external-launcher-watcher",
        "historical_outcome_lease_released": False,
        "uses_realized_outcomes": True,
        "complete": True,
    }


def _execution(
    *,
    name: str,
    uid: str,
    task_count: int,
    args: list[str],
    environment: dict[str, str],
    generation: str = finisher.JOB_GENERATION,
    succeeded: int = 1,
) -> dict:
    return {
        "metadata": {
            "name": name,
            "uid": uid,
            "labels": {
                "run.googleapis.com/job": finisher.JOB,
                "run.googleapis.com/jobUid": finisher.JOB_UID,
                "run.googleapis.com/jobGeneration": generation,
            },
        },
        "spec": {
            "taskCount": task_count,
            "parallelism": min(4, task_count),
            "template": {
                "spec": {
                    "maxRetries": 0,
                    "timeout": "21600s",
                    "serviceAccountName": finisher.SERVICE_ACCOUNT,
                    "containers": [
                        {
                            "image": finisher.IMMUTABLE_IMAGE,
                            "command": ["/bin/bash"],
                            "args": args,
                            "resources": {
                                "limits": {"cpu": "8", "memory": "32Gi"}
                            },
                            "env": [
                                {"name": key, "value": value}
                                for key, value in environment.items()
                            ],
                        }
                    ],
                }
            },
        },
        "status": {
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": succeeded,
            "failedCount": 0,
            "cancelledCount": 0,
            "runningCount": 0,
            "completionTime": "2026-08-30T23:00:00Z",
        },
    }


def _source_environment() -> dict[str, str]:
    raw = finisher.canonical_bytes(finisher.source_request_v1())
    return {
        "CODE_SHA": finisher.CODE_SHA,
        "IMAGE_DIGEST": finisher.IMAGE_DIGEST,
        "BUILD_ID": finisher.BUILD_ID,
        finisher.ENABLE_ENV: finisher.ENABLE_VALUE,
        finisher.MANIFEST_ENV: finisher.canonical_bytes(
            finisher.SOURCE_MANIFEST_IDENTITY, newline=False
        ).decode("ascii"),
        finisher.REQUEST_SHA_ENV: sha256(raw).hexdigest(),
        finisher.REQUEST_B64_ENV: __import__("base64").b64encode(raw).decode("ascii"),
        "R6_CONSTRUCTION_ALLOCATION_JOB_NAME": finisher.JOB,
        "R6_CONSTRUCTION_ALLOCATION_FULL_IMAGE": finisher.IMMUTABLE_IMAGE,
        "R6_CONSTRUCTION_ALLOCATION_NO_OUTCOME_SMOKE": "false",
        "R6_CONSTRUCTION_ALLOCATION_TARGET_OUTCOMES_ALLOWED": "false",
    }


def _launch_receipt(phase: str, request: dict, request_raw: bytes) -> dict:
    bound = finisher._request_bound_identity(phase, request)  # noqa: SLF001
    source = None
    attestation = None
    if phase in {"collect", "reopen"}:
        source = {
            "name": finisher.SOURCE_EXECUTION_NAME,
            "uid": finisher.SOURCE_EXECUTION_UID,
            "task_count": 54,
        }
        attestation = {
            "uri": (
                finisher.SOURCE_MANIFEST_IDENTITY["uri"].removesuffix(
                    "input-manifest.json"
                )
                + "authorities/runtime-execution-attestation-"
                + finisher.SOURCE_EXECUTION_NAME
                + ".json"
            ),
            "generation": "20",
            "sha256": "e" * 64,
            "bytes": 500,
        }
    receipt = {
        "schema_version": finisher.LAUNCH_SCHEMA,
        "phase": phase,
        "code_sha": finisher.CODE_SHA,
        "cloud_build_id": finisher.BUILD_ID,
        "provider_resolved_image": finisher.IMMUTABLE_IMAGE,
        "image_digest": finisher.IMAGE_DIGEST,
        "reused_job": {
            "name": finisher.JOB,
            "uid": finisher.JOB_UID,
            "generation": int(finisher.JOB_GENERATION),
        },
        "execution": {
            "name": f"{finisher.JOB}-abc12",
            "uid": "12345678-1234-1234-1234-123456789abc",
            "task_count": 1,
        },
        "bound_input_authority_identity": bound,
        "manifest_identity": bound,
        "runtime_execution_attestation_identity": attestation,
        "source_task_execution": source,
        "request_sha256": "0" * 64,
        "no_outcome_smoke_mode": False,
        "target_slate_outcomes_allowed": phase in {"grade", "grade-reopen"},
        "execution_provider_reopened": True,
        "complete": True,
    }
    transported = finisher.canonical_bytes(
        finisher.transport_request_v1(
            phase=phase, request=request, launch_receipt=receipt
        )
    )
    receipt["request_sha256"] = sha256(transported).hexdigest()
    return receipt


def test_exact_frozen_authorities_and_canonical_source_request() -> None:
    raw = finisher.canonical_bytes(finisher.source_request_v1())
    assert sha256(raw).hexdigest() == (
        "43b2aeec243d3db45ca3a9f1d671f5197925bd0850caaceb3a8b43385e15f6a2"
    )
    assert finisher.GRADE_RUN_ID == (
        "20260830-construction-allocation-d5946133-grade-v1"
    )
    assert finisher.GRADE_MANIFEST_URI.endswith(
        "/20260830-construction-allocation-d5946133-grade-v1/grade-manifest.json"
    )
    assert finisher.OUTCOME_COMPLETION_IDENTITY["generation"] == "1787987567275104"


def test_launcher_receipt_accepts_one_pretty_json_object_only() -> None:
    request = finisher.source_request_v1()
    receipt = _launch_receipt("collect", request, finisher.canonical_bytes(request))
    pretty = (json.dumps(receipt, indent=2) + "\n").encode("ascii")
    assert finisher._parse_launcher_json(  # noqa: SLF001
        pretty, label="collect launcher stdout"
    ) == receipt

    with pytest.raises(finisher.FinisherError, match="one JSON document"):
        finisher._parse_launcher_json(  # noqa: SLF001
            pretty + b"{}\n", label="collect launcher stdout"
        )
    with pytest.raises(finisher.FinisherError, match="string-keyed object"):
        finisher._parse_launcher_json(  # noqa: SLF001
            b"[]\n", label="collect launcher stdout"
        )


def test_collect_and_independent_reopen_result_validation() -> None:
    result = _collect_result()
    assert finisher.validate_collect_result_v1(result) == result
    tampered = deepcopy(result)
    tampered["outcome_data_accessed"] = True
    tampered["collect_sha256"] = finisher.canonical_sha256(
        {key: value for key, value in tampered.items() if key != "collect_sha256"}
    )
    with pytest.raises(finisher.FinisherError, match="authority differs"):
        finisher.validate_collect_result_v1(tampered)


def test_grade_requests_derive_only_from_validated_predecessors() -> None:
    prepare = finisher.grade_prepare_request_v1(
        reopen_result=_collect_result(), frozen_at="2026-08-30T23:00:00Z"
    )
    assert set(prepare) == {
        "schema_version",
        "run_id",
        "grade_id",
        "frozen_at",
        "code_sha",
        "immutable_image",
        "output_prefix",
        "selection_terminal_envelope",
        "outcome_authority_identity",
    }
    assert prepare["selection_terminal_envelope"] == _selection_envelope()
    assert prepare["outcome_authority_identity"] == finisher.OUTCOME_COMPLETION_IDENTITY

    grade = finisher.grade_request_v1(grade_prepare_result=_grade_prepared_result())
    assert grade == {
        "schema_version": (
            "corpus-r6-construction-allocation-grade-execute-request/v1"
        ),
        "manifest_identity": _grade_prepared_result()["manifest_identity"],
    }
    reopen = finisher.grade_reopen_request_v1(grade_result=_grade_result())
    assert reopen["terminal_envelope"] == _grade_envelope()
    assert reopen["code_sha"] == finisher.CODE_SHA


def test_bad_predecessor_cannot_derive_grade_request() -> None:
    bad = _collect_result()
    bad["collect_sha256"] = "0" * 64
    with pytest.raises(finisher.FinisherError, match="self-hash"):
        finisher.grade_prepare_request_v1(
            reopen_result=bad, frozen_at="2026-08-30T23:00:00Z"
        )


@pytest.mark.parametrize(
    ("phase", "result"),
    [
        ("collect", _collect_result()),
        ("reopen", _collect_result()),
        ("grade-prepare", _grade_prepared_result()),
        ("grade", _grade_result()),
        ("grade-reopen", _grade_reopen_result()),
    ],
)
def test_exact_one_canonical_stdout_document(phase: str, result: dict) -> None:
    logs = [{"textPayload": finisher.canonical_bytes(result).decode("ascii")}]
    assert finisher.result_from_exact_stdout_logs_v1(logs, phase=phase) == result

    with pytest.raises(finisher.FinisherError, match="document count"):
        finisher.result_from_exact_stdout_logs_v1(logs + logs, phase=phase)

    pretty = json.dumps(result, indent=2) + "\n"
    with pytest.raises(finisher.FinisherError, match="canonical JSON"):
        finisher.result_from_exact_stdout_logs_v1(
            [{"textPayload": pretty}], phase=phase
        )


def test_source_provider_execution_requires_exact_name_uid_and_54_successes() -> None:
    execution = _execution(
        name=finisher.SOURCE_EXECUTION_NAME,
        uid=finisher.SOURCE_EXECUTION_UID,
        task_count=54,
        args=[
            "/app/scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh",
            "container-task",
        ],
        environment=_source_environment(),
        succeeded=54,
    )
    assert finisher.validate_source_execution_v1(execution) == execution
    wrong = deepcopy(execution)
    wrong["metadata"]["uid"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    with pytest.raises(finisher.FinisherError, match="immutable authority"):
        finisher.validate_source_execution_v1(wrong)


@pytest.mark.parametrize("phase", ["collect", "reopen", "grade-prepare", "grade", "grade-reopen"])
def test_launch_receipt_binds_exact_phase_request(phase: str) -> None:
    if phase in {"collect", "reopen"}:
        request = finisher.source_request_v1()
    elif phase == "grade-prepare":
        request = finisher.grade_prepare_request_v1(
            reopen_result=_collect_result(), frozen_at="2026-08-30T23:00:00Z"
        )
    elif phase == "grade":
        request = finisher.grade_request_v1(
            grade_prepare_result=_grade_prepared_result()
        )
    else:
        request = finisher.grade_reopen_request_v1(grade_result=_grade_result())
    raw = finisher.canonical_bytes(request)
    launch = _launch_receipt(phase, request, raw)
    assert finisher.validate_launch_receipt_v1(
        launch, phase=phase, request=request, request_raw=raw
    ) == launch
    bad = deepcopy(launch)
    bad["execution"]["uid"] = "not-a-provider-uuid"
    with pytest.raises(finisher.FinisherError, match="launch receipt differs"):
        finisher.validate_launch_receipt_v1(
            bad, phase=phase, request=request, request_raw=raw
        )


def test_collect_transport_adds_only_exact_runtime_execution_attestation() -> None:
    request = finisher.source_request_v1()
    raw = finisher.canonical_bytes(request)
    launch = _launch_receipt("collect", request, raw)
    transported = finisher.transport_request_v1(
        phase="collect", request=request, launch_receipt=launch
    )
    assert set(transported) == {
        "manifest_identity",
        "runtime_execution_attestation_identity",
    }
    assert transported["manifest_identity"] == finisher.SOURCE_MANIFEST_IDENTITY
    assert transported["runtime_execution_attestation_identity"] == launch[
        "runtime_execution_attestation_identity"
    ]
    assert launch["request_sha256"] != sha256(raw).hexdigest()


def test_phase_execution_validates_exact_request_transport() -> None:
    phase = "grade"
    request = finisher.grade_request_v1(
        grade_prepare_result=_grade_prepared_result()
    )
    raw = finisher.canonical_bytes(request)
    launch = _launch_receipt(phase, request, raw)
    bound = finisher._request_bound_identity(phase, request)  # noqa: SLF001
    environment = {
        "CODE_SHA": finisher.CODE_SHA,
        "IMAGE_DIGEST": finisher.IMAGE_DIGEST,
        "BUILD_ID": finisher.BUILD_ID,
        finisher.ENABLE_ENV: finisher.ENABLE_VALUE,
        finisher.MANIFEST_ENV: finisher.canonical_bytes(
            bound, newline=False
        ).decode("ascii"),
        finisher.REQUEST_SHA_ENV: sha256(raw).hexdigest(),
        finisher.REQUEST_B64_ENV: __import__("base64").b64encode(raw).decode("ascii"),
        "R6_CONSTRUCTION_ALLOCATION_JOB_NAME": finisher.JOB,
        "R6_CONSTRUCTION_ALLOCATION_FULL_IMAGE": finisher.IMMUTABLE_IMAGE,
        "R6_CONSTRUCTION_ALLOCATION_NO_OUTCOME_SMOKE": "false",
        "R6_CONSTRUCTION_ALLOCATION_TARGET_OUTCOMES_ALLOWED": "true",
        finisher.GRADE_ENABLE_ENV: "1",
        finisher.GRADE_CODE_SHA_ENV: finisher.CODE_SHA,
        finisher.GRADE_IMAGE_ENV: finisher.IMMUTABLE_IMAGE,
    }
    execution = _execution(
        name=launch["execution"]["name"],
        uid=launch["execution"]["uid"],
        task_count=1,
        args=finisher._phase_args(phase),  # noqa: SLF001
        environment=environment,
    )
    assert finisher.validate_phase_execution_v1(
        execution,
        phase=phase,
        execution_name=launch["execution"]["name"],
        execution_uid=launch["execution"]["uid"],
        request=request,
        request_raw=raw,
        launch_receipt=launch,
    ) == execution
    execution["spec"]["template"]["spec"]["containers"][0]["env"][-4][
        "value"
    ] = "false"
    with pytest.raises(finisher.FinisherError, match="contract differs"):
        finisher.validate_phase_execution_v1(
            execution,
            phase=phase,
            execution_name=launch["execution"]["name"],
            execution_uid=launch["execution"]["uid"],
            request=request,
            request_raw=raw,
            launch_receipt=launch,
        )


def test_grade_reopen_requires_exact_completion_snapshot_and_live_lease() -> None:
    value = _grade_reopen_result()
    assert finisher.validate_result_v1(value, phase="grade-reopen") == value
    bad = deepcopy(value)
    bad["reopen_receipt"]["outcome_snapshot_identity"]["generation"] = "999"
    body = bad["reopen_receipt"]
    body["reopen_sha256"] = finisher.canonical_sha256(
        {key: item for key, item in body.items() if key != "reopen_sha256"}
    )
    with pytest.raises(finisher.FinisherError, match="grade-reopen result differs"):
        finisher.validate_result_v1(bad, phase="grade-reopen")


def test_default_off_exact_log_filter_and_known_name_absence_guard() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "I_UNDERSTAND_D5946133_POST54_FINISHER_V1" in text
    assert 'labels.\"run.googleapis.com/execution_name\"' in text
    assert "run.googleapis.com%2Fstdout" in text
    assert '"storage",\n                "objects",\n                "describe"' in text
    assert "GRADE_MANIFEST_URI" in text
    assert "run jobs executions list" not in text
    assert '"storage", "ls"' not in text
    assert "prefix_listing_used\": False" in text


def test_all_derived_state_is_outside_clean_checkout() -> None:
    assert finisher.DEFAULT_RUN_DIR.is_absolute()
    assert finisher.CLEAN_ROOT not in finisher.DEFAULT_RUN_DIR.parents
    assert (ROOT / ".tmp") in finisher.DEFAULT_RUN_DIR.parents
