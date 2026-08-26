from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import (
    corpus_extreme_tail_panel_platform_replacement_v1 as replacement,
)
from nfl_dfs.research import corpus_extreme_tail_panel_transport as transport
from nfl_dfs.research import corpus_parametric_batch as batch


def _identity(uri: str, marker: str, *, generation: str = "1") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": marker * 64,
        "bytes": 100,
    }


def _terminal() -> dict[str, object]:
    contract = replacement.frozen_platform_replacement_contract_v1()
    return {
        "schema_version": replacement.TERMINAL_PROJECTION_SCHEMA,
        "execution_name": replacement.FAILED_EXECUTION,
        "job": contract["reuse_job"],
        "operation": replacement.OPERATION,
        "source_ordinal": replacement.SOURCE_ORDINAL,
        "runtime_attempt_ordinal": replacement.PRIMARY_RUNTIME_ATTEMPT,
        "completed_status": "False",
        "task_completed_status": "False",
        "completed_message": (
            "Task atlas-minimal-c-s2023-w1-v1-rffts-task0 failed with "
            "exit code: 0 and message: Internal error."
        ),
        "execution_describe_argv": list(replacement.EXECUTION_DESCRIBE_ARGV),
        "execution_describe_stdout_sha256": "d" * 64,
        "execution_describe_stdout_bytes": 4096,
        "task_describe_argv": list(replacement.TASK_DESCRIBE_ARGV),
        "task_describe_stdout_sha256": "e" * 64,
        "task_describe_stdout_bytes": 2048,
        "configured_environment_sha256": "f" * 64,
        "configured_environment_entry_count": 48,
        "failed_count": 1,
        "succeeded_count": 0,
        "cancelled_count": 0,
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "task_timeout_seconds": 21600,
        "service_account": contract["service_account"],
        "image": replacement.FROZEN_D2_URI,
        "cpu": "8",
        "memory": "32Gi",
        "cloud_task_name": replacement.FAILED_TASK,
        "task_spec": {},
        "task_status_index_present": False,
        "task_status_retried_present": False,
        "task_last_attempt_exit_code_present": False,
        "last_attempt_status_code": 13,
        "last_attempt_status_message": "Internal error.",
        "execution_completed_message_exit_code": 0,
        "primary_stage_start_identity": contract[
            "primary_stage_start_identity"
        ],
        "primary_runtime_measurement_identity": contract[
            "primary_runtime_measurement_identity"
        ],
        "original_launch_request_identity": contract[
            "primary_launch_request_identity"
        ],
        "transport_contract_identity": contract["transport_contract_identity"],
        "job_config_identity": contract["job_config_identity"],
        "predecessor_identity": contract["predecessor_identity"],
        "execution_authority_identity": contract[
            "execution_authority_identity"
        ],
        "compute_release_identity": contract["compute_release_identity"],
        "runtime_evidence_volume": {
            "type": "in-memory",
            "name": "foundry-t230-runtime-evidence",
            "size_limit": "1Mi",
            "mount_path": "/etc/nfl-dfs",
        },
        "execution_terminal_exactly_validated": True,
        "task_terminal_exactly_validated": True,
        "execution_envelope_exactly_validated": True,
        "execution_environment_exactly_validated": True,
        "frozen_runtime_payload_exactly_validated": True,
        "frozen_runtime_payload_sha256": (
            replacement.FROZEN_PRIMARY_RUNTIME_PAYLOAD_SHA256
        ),
        "frozen_runtime_payload_bytes": (
            replacement.FROZEN_PRIMARY_RUNTIME_PAYLOAD_BYTES
        ),
        "system_platform_error_observed": True,
        "result_or_effect_content_inspected": False,
        "realized_outcomes_read": False,
    }


def _lineage() -> dict[str, object]:
    contract = replacement.frozen_platform_replacement_contract_v1()
    request = contract["primary_launch_request_identity"]
    return {
        "transport_contract_sha256": "1" * 64,
        "transport_contract_identity": contract["transport_contract_identity"],
        "job_config_identity": contract["job_config_identity"],
        "predecessor_identities": [contract["predecessor_identity"]],
        "primary_stage_start_identity": contract[
            "primary_stage_start_identity"
        ],
        "primary_stage_start_sha256": contract[
            "primary_stage_start_self_sha256"
        ],
        "primary_runtime_measurement_identity": contract[
            "primary_runtime_measurement_identity"
        ],
        "primary_runtime_measurement_sha256": contract[
            "primary_runtime_measurement_self_sha256"
        ],
        "primary_launch_request_identity": request,
        "primary_launch_publication_proof": {
            "intent_identity": _identity("gs://fixture/intent.json", "2"),
            "target_identity": request,
            "completion_identity": _identity("gs://fixture/completion.json", "3"),
        },
        "execution_authority_identity": contract["execution_authority_identity"],
        "execution_authority_sha256": "4" * 64,
        "image_evidence_identity": _identity(
            "gs://fixture/image-evidence.json", "e"
        ),
        "manifest_identity": _identity("gs://fixture/manifest.json", "5"),
        "execution_manifest_sha256": "6" * 64,
        "compute_release_identity": contract["compute_release_identity"],
        "compute_release_sha256": "7" * 64,
        "result_uri": replacement.RESULT_URI,
        "acceptance_uri": replacement.ACCEPTANCE_URI,
    }


def _implementations() -> list[dict[str, object]]:
    paths = (
        replacement.IMPLEMENTATION_RELATIVE_PATH,
        replacement.TEST_RELATIVE_PATH,
        replacement.CONTROLLER_RELATIVE_PATH,
        replacement.CONTROLLER_TEST_RELATIVE_PATH,
    )
    return [
        {
            "relative_path": path,
            "sha256": marker * 64,
            "bytes": 1234 + ordinal,
        }
        for ordinal, (path, marker) in enumerate(zip(paths, "89ab", strict=True))
    ]


def _correction_addendum_measurement() -> dict[str, object]:
    return {
        "relative_path": replacement.CORRECTION_ADDENDUM_RELATIVE_PATH,
        "sha256": replacement.CORRECTION_ADDENDUM_SHA256,
        "bytes": replacement.CORRECTION_ADDENDUM_BYTES,
    }


def _preflight_correction_addendum_measurement() -> dict[str, object]:
    return {
        "relative_path": replacement.PREFLIGHT_CORRECTION_ADDENDUM_RELATIVE_PATH,
        "sha256": "d" * 64,
        "bytes": 3456,
    }


def _first_corrected_focused_test_output_measurement() -> dict[str, object]:
    return {
        "relative_path": (
            replacement.FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_RELATIVE_PATH
        ),
        "sha256": replacement.FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_SHA256,
        "bytes": replacement.FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_BYTES,
    }


def _post_preflight_fix_focused_test_output_measurement() -> dict[str, object]:
    return {
        "relative_path": (
            replacement.POST_PREFLIGHT_FIX_FOCUSED_TEST_OUTPUT_RELATIVE_PATH
        ),
        "sha256": "e" * 64,
        "bytes": 4567,
    }


def _rehash(value: dict[str, object], field: str) -> None:
    value.pop(field, None)
    value[field] = batch.canonical_sha256(value)


def _review_lock(
    implementations: list[dict[str, object]] | None = None,
    correction_addendum_measurement: dict[str, object] | None = None,
    preflight_correction_addendum_measurement: dict[str, object] | None = None,
) -> dict[str, object]:
    rows = deepcopy(implementations if implementations is not None else _implementations())
    lock = {
        "schema_version": replacement.REVIEW_LOCK_SCHEMA,
        "run_id": transport.RUN_ID,
        "review_method": "independent-static-contract-review-v1",
        "reviewed_candidate_disposition": "accepted-no-p0-p1-p2",
        "amendment_measurement": {
            "relative_path": replacement.AMENDMENT_RELATIVE_PATH,
            "sha256": replacement.AMENDMENT_SHA256,
            "bytes": replacement.AMENDMENT_BYTES,
        },
        "correction_addendum_measurement": (
            deepcopy(
                correction_addendum_measurement
                if correction_addendum_measurement is not None
                else _correction_addendum_measurement()
            )
        ),
        "preflight_correction_addendum_measurement": deepcopy(
            preflight_correction_addendum_measurement
            if preflight_correction_addendum_measurement is not None
            else _preflight_correction_addendum_measurement()
        ),
        "reviewed_implementation_measurements": rows,
        "reviewed_implementation_measurements_sha256": batch.canonical_sha256(rows),
        "failed_focused_test_candidate_measurements": [
            dict(row)
            for row in replacement.PRIOR_FAILED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS
        ],
        "failed_focused_test_candidate_measurements_sha256": (
            batch.canonical_sha256(
                list(
                    replacement.PRIOR_FAILED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS
                )
            )
        ),
        "first_corrected_focused_test_candidate_measurements": [
            dict(row)
            for row in replacement.FIRST_CORRECTED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS
        ],
        "first_corrected_focused_test_candidate_measurements_sha256": (
            batch.canonical_sha256(
                list(
                    replacement.FIRST_CORRECTED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS
                )
            )
        ),
        "first_corrected_focused_test_output_measurement": (
            _first_corrected_focused_test_output_measurement()
        ),
        "post_preflight_fix_focused_test_output_measurement": (
            _post_preflight_fix_focused_test_output_measurement()
        ),
        "source_ast_parse_passed": True,
        "tests_ast_parse_passed": True,
        "controller_ast_parse_passed": True,
        "controller_tests_ast_parse_passed": True,
        "git_diff_check_passed": True,
        "focused_test_command": list(replacement.FOCUSED_TEST_COMMAND),
        "prior_failed_focused_test_command": list(
            replacement.FOCUSED_TEST_COMMAND
        ),
        "prior_failed_invocation_count": 1,
        "prior_failed_pytest_exit_code": 1,
        "prior_failed_failure_node_ids": list(
            replacement.PRIOR_FAILED_FOCUSED_TEST_NODE_IDS
        ),
        "prior_failed_failure_count": 3,
        "prior_failed_cloud_call_count": 0,
        "prior_failed_preflight_invocation_count": 0,
        "prior_failed_intent_built": False,
        "prior_failed_realized_outcomes_read": False,
        "prior_failed_collected_passed_counts_available": False,
        "prior_failed_test_output_sha256_available": False,
        "first_corrected_candidate_invocation_count": 1,
        "first_corrected_candidate_result": "passed",
        "first_corrected_tests_collected": 271,
        "first_corrected_tests_passed": 271,
        "first_corrected_tests_failed": 0,
        "first_corrected_tests_skipped": 0,
        "first_corrected_test_warnings": 0,
        "first_corrected_pytest_exit_code": 0,
        "first_corrected_pytest_wall_milliseconds": 3515,
        "first_corrected_test_output_sha256": (
            replacement.FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_SHA256
        ),
        "first_corrected_test_output_bytes": (
            replacement.FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_BYTES
        ),
        "corrected_candidate_invocation_count": 1,
        "corrected_candidate_invocation_count_max": 1,
        "focused_test_total_invocation_count": 3,
        "focused_test_total_invocation_count_max": 3,
        "corrected_candidate_result": "passed",
        "real_artifact_preflight_receipt_measurement": {
            "relative_path": (
                replacement.REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH
            ),
            "sha256": "f" * 64,
            "bytes": 2345,
        },
        "real_artifact_preflight_command": list(
            replacement.REAL_ARTIFACT_PREFLIGHT_COMMAND
        ),
        "first_failed_real_artifact_preflight_command": list(
            replacement.REAL_ARTIFACT_PREFLIGHT_COMMAND
        ),
        "first_failed_real_artifact_preflight_invocation_count": 1,
        "first_failed_real_artifact_preflight_exit_code": 1,
        "first_failed_real_artifact_preflight_error_lines": list(
            replacement.FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_ERROR_LINES
        ),
        "first_failed_real_artifact_preflight_output_measurement_available": False,
        "first_failed_real_artifact_preflight_receipt_created": False,
        "first_failed_real_artifact_preflight_cloud_read_performed": True,
        "first_failed_real_artifact_preflight_cloud_mutation_executed": False,
        "first_failed_real_artifact_preflight_gcs_publication_count": 0,
        "first_failed_real_artifact_preflight_cloud_submit_count": 0,
        "first_failed_real_artifact_preflight_realized_outcomes_read": False,
        "corrected_real_artifact_preflight_invocation_count": 1,
        "real_artifact_preflight_invocation_count": 2,
        "real_artifact_preflight_invocation_count_max": 2,
        "real_artifact_preflight_passed": True,
        "real_artifact_preflight_realized_outcomes_read": False,
        "focused_test_cloud_call_count": 0,
        "cloud_read_performed": True,
        "cloud_mutation_executed": False,
        "gcs_publication_count": 0,
        "cloud_submit_count": 0,
        "tests_collected": 101,
        "tests_passed": 101,
        "tests_failed": 0,
        "tests_skipped": 0,
        "test_warnings": 0,
        "pytest_exit_code": 0,
        "test_output_sha256": "e" * 64,
        "test_output_bytes": 4567,
        "realized_outcomes_read": False,
        "independent_review_complete": True,
        **{field: False for field in replacement._FALSE_AUTHORITY_FIELDS},
    }
    _rehash(lock, "review_lock_sha256")
    return lock


def _review_lock_binding(lock: dict[str, object]) -> dict[str, object]:
    raw = batch.canonical_json_bytes(lock) + b"\n"
    return {
        "relative_path": replacement.REVIEW_LOCK_RELATIVE_PATH,
        "source_commit_sha": "d" * 40,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "tracked_at_head": True,
        "clean_at_head": True,
    }


def _launch_plan() -> dict[str, object]:
    contract = replacement.frozen_platform_replacement_contract_v1()
    receipt_law = contract["post_submission_receipt_validation_law"]
    plan = {
        "schema_version": replacement.WORKER_LAUNCH_PLAN_SCHEMA,
        "run_id": transport.RUN_ID,
        "project": transport.PROJECT,
        "region": transport.REGION,
        "reuse_job": contract["reuse_job"],
        "operation": replacement.OPERATION,
        "source_ordinal": replacement.SOURCE_ORDINAL,
        "runtime_attempt_ordinal": replacement.REPLACEMENT_RUNTIME_ATTEMPT,
        "immutable_image": contract["immutable_image"],
        "execution_envelope": contract["replacement_execution_envelope"],
        "post_submission_receipt_validation_law": receipt_law,
        "post_submission_receipt_validation_law_sha256": (
            batch.canonical_sha256(receipt_law)
        ),
        "execution_authority_identity": contract["execution_authority_identity"],
        "image_evidence_identity": _identity(
            "gs://fixture/image-evidence.json", "e"
        ),
        "compute_release_identity": contract["compute_release_identity"],
        "predecessor_identity": contract["predecessor_identity"],
        "replacement_intent_uri": replacement.REPLACEMENT_INTENT_URI,
        "launch_ownership_uri": replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI,
        "replacement_stage_start_uri": replacement.REPLACEMENT_STAGE_START_URI,
        "canonical_result_uri": replacement.RESULT_URI,
        "canonical_worker_stage_uri": replacement.PRIMARY_STAGE_RECEIPT_URI,
        "flags_path": replacement.REAL_ARTIFACT_PREFLIGHT_FLAGS_PATH,
        "execution_flags_template": {
            "--args": ["-ceu", "frozen-replacement-payload"],
            "--update-env-vars": {
                "T230_RUNTIME_ATTEMPT": "1",
                "T230_SOURCE_ORDINAL": "6",
            },
        },
        "submission_mode": "async-single-request",
        "max_submission_calls": 1,
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "task_timeout_seconds": transport.TASK_TIMEOUT_SECONDS,
        "same_process_intent_create_and_submission_required": True,
        "runtime_waits_for_launch_ownership_and_stage_start": True,
        "transport_run_stage_used": False,
        "original_launch_request_reused": False,
        "primary_runtime_attempt_reused": False,
        "second_replacement_allowed": False,
        "request_consumed_on_ambiguous_submission": True,
        "result_or_effect_content_inspected_before_submission": False,
        **{field: False for field in replacement._FALSE_AUTHORITY_FIELDS},
    }
    _rehash(plan, "worker_launch_plan_sha256")
    return plan


def _live_job() -> dict[str, object]:
    return {
        "schema_version": replacement.LIVE_JOB_PROJECTION_SCHEMA,
        "job": replacement.REUSE_JOB,
        "image": replacement.FROZEN_D2_URI,
        "service_account": replacement.SERVICE_ACCOUNT,
        "cpu": "8",
        "memory": "32Gi",
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "task_timeout_seconds": transport.TASK_TIMEOUT_SECONDS,
        "command": ["bash"],
        "args": [
            "-ceu",
            "python scripts/run_corpus_extreme_tail_panel_transport_v1.py parked",
        ],
        "configured_environment": {},
        "runtime_evidence_volume": {
            "type": "in-memory",
            "name": "foundry-t230-runtime-evidence",
            "size_limit": "1Mi",
            "mount_path": "/etc/nfl-dfs",
        },
        "describe_argv": list(replacement.LIVE_JOB_DESCRIBE_ARGV),
        "describe_stdout_sha256": "a" * 64,
        "describe_stdout_bytes": 8192,
        "cloud_describe_exactly_validated": True,
    }


def _intent() -> dict[str, object]:
    implementations = _implementations()
    lock = _review_lock(implementations)
    return replacement.build_platform_replacement_intent_v1(
        terminal_projection=_terminal(),
        primary_lineage=_lineage(),
        review_lock_binding=_review_lock_binding(lock),
        review_lock=lock,
        recovery_implementation_measurements=implementations,
        replacement_worker_launch_plan=_launch_plan(),
        replacement_live_job_projection=_live_job(),
    )


class _Backend:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[dict[str, object], bytes]] = {}
        self.terminal = _terminal()
        self.generation = 100
        self.observed_execution_names: list[str] = []
        self.metadata_probe_uris: list[str] = []
        self.known_body_reads: list[str] = []
        self.create_calls: list[str] = []

    def observe_primary_terminal(self, execution_name: str) -> dict[str, object]:
        self.observed_execution_names.append(execution_name)
        return deepcopy(self.terminal)

    def probe_known_uri_metadata(self, uri: str) -> dict[str, object] | None:
        self.metadata_probe_uris.append(uri)
        if uri not in self.objects:
            return None
        identity, _raw = self.objects[uri]
        return dict(identity)

    def read(self, identity: dict[str, object]) -> bytes:
        retained, raw = self.objects[str(identity["uri"])]
        if retained != identity:
            raise AssertionError("pinned identity differs")
        return raw

    def read_known_uri(self, uri: str) -> tuple[dict[str, object], bytes]:
        self.known_body_reads.append(uri)
        if uri not in self.objects:
            raise FileNotFoundError(uri)
        identity, raw = self.objects[uri]
        return dict(identity), raw

    def create(self, uri: str, raw: bytes) -> dict[str, object]:
        del raw
        self.create_calls.append(uri)
        raise AssertionError("offline component must never create an object")

    def _put(self, uri: str, raw: bytes) -> dict[str, object]:
        self.generation += 1
        identity = {
            "uri": uri,
            "generation": str(self.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[uri] = (identity, raw)
        return dict(identity)


def _patch_candidate_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    implementations = _implementations()
    lock = _review_lock(implementations)
    binding = _review_lock_binding(lock)
    monkeypatch.setattr(
        replacement,
        "_reopen_fixed_primary_lineage_v1",
        lambda _backend: _lineage(),
    )
    monkeypatch.setattr(
        replacement,
        "_reopen_recovery_review_lock_v1",
        lambda _backend: (deepcopy(binding), deepcopy(lock)),
    )
    monkeypatch.setattr(
        replacement,
        "_implementation_measurements",
        lambda: deepcopy(implementations),
    )


def test_frozen_contract_pins_exact_primary_evidence_bridge_and_offline_boundary() -> None:
    contract = replacement.frozen_platform_replacement_contract_v1()

    assert replacement.validate_platform_replacement_contract_v1(contract) == contract
    assert contract["source_ordinal"] == 6
    assert contract["failed_execution"] == replacement.FAILED_EXECUTION
    assert contract["immutable_image"]["uri"] == replacement.FROZEN_D2_URI
    assert contract["primary_runtime_attempt_ordinal"] == 0
    assert contract["replacement_runtime_attempt_ordinal"] == 1
    assert contract["task_max_retries"] == 0
    assert contract["max_replacement_worker_executions"] == 1
    assert contract["replacement_worker_limit_excludes_bridge_verifier"] is True
    assert contract["max_bridge_verifier_executions_after_worker_success"] == 1
    assert contract["pre_submit_live_job_exact_description_required"] is True
    assert (
        contract["pre_submit_live_job_must_equal_replacement_execution_envelope"]
        is True
    )
    assert contract["changed_or_ambiguous_live_job_is_terminal"] is True
    for field in (
        "submission_failure_terminal_create_once_required",
        "ambiguous_submission_requires_terminal_receipt",
        "nonzero_submission_requires_terminal_receipt",
        "malformed_submission_response_requires_terminal_receipt",
        "unverified_submitted_envelope_requires_terminal_receipt",
        "terminal_receipt_publication_failure_still_consumes_attempt",
    ):
        assert contract[field] is True
    assert contract["primary_stage_start_identity"] == {
        "uri": replacement.PRIMARY_STAGE_START_URI,
        "generation": "1787709944159900",
        "sha256": "744f5f944089eb01ad5a100574e69734eeb9008c2977968a67f513936c91013b",
        "bytes": 3593,
    }
    assert contract["primary_runtime_measurement_identity"] == {
        "uri": replacement.PRIMARY_RUNTIME_MEASUREMENT_URI,
        "generation": "1787710039301316",
        "sha256": "80beaefc343166a3f06f9e1221f4f2126a76758114dc7c50a97838eb71623c0c",
        "bytes": 13520,
    }
    assert contract["amendment_measurement"] == {
        "relative_path": replacement.AMENDMENT_RELATIVE_PATH,
        "sha256": replacement.AMENDMENT_SHA256,
        "bytes": replacement.AMENDMENT_BYTES,
    }
    assert contract["same_process_controller_relative_path"] == (
        replacement.CONTROLLER_RELATIVE_PATH
    )
    assert contract["offline_component_may_publish_replacement_intent"] is False
    assert contract["offline_component_may_submit_cloud_execution"] is False
    assert contract["primary_name_only_empty_environment_names"] == [
        "T230_PRED1_URI",
        "T230_PRED1_GENERATION",
        "T230_PRED1_SHA256",
        "T230_PRED1_BYTES",
        "T230_RESULT_URI",
        "T230_RESULT_GENERATION",
        "T230_RESULT_SHA256",
        "T230_RESULT_BYTES",
        "T230_LANE0_URI",
        "T230_LANE0_GENERATION",
        "T230_LANE0_SHA256",
        "T230_LANE0_BYTES",
        "T230_LANE1_URI",
        "T230_LANE1_GENERATION",
        "T230_LANE1_SHA256",
        "T230_LANE1_BYTES",
    ]
    assert contract["primary_name_only_empty_environment_names"] == list(
        replacement.PRIMARY_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES
    )
    assert contract[
        "primary_name_only_empty_environment_names_sha256"
    ] == batch.canonical_sha256(
        list(replacement.PRIMARY_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES)
    )
    assert contract[
        "primary_name_only_empty_normalization_exact_allowlist_required"
    ] is True
    assert contract[
        "unknown_primary_name_only_environment_row_is_terminal"
    ] is True
    assert contract[
        "primary_environment_value_from_or_extra_fields_are_terminal"
    ] is True
    assert contract["correction_addendum_relative_path"] == (
        replacement.CORRECTION_ADDENDUM_RELATIVE_PATH
    )
    assert contract["prior_failed_invocation_count"] == 1
    assert contract["prior_failed_pytest_exit_code"] == 1
    assert contract["prior_failed_focused_test_node_ids"] == list(
        replacement.PRIOR_FAILED_FOCUSED_TEST_NODE_IDS
    )
    assert contract["corrected_candidate_invocation_count_max"] == 1
    assert contract["corrected_candidate_invocation_count"] == 1
    assert contract["first_corrected_candidate_invocation_count"] == 1
    assert contract["first_corrected_tests_collected"] == 271
    assert contract["first_corrected_tests_passed"] == 271
    assert contract["first_corrected_focused_test_output_measurement"] == (
        _first_corrected_focused_test_output_measurement()
    )
    assert contract["preflight_correction_addendum_relative_path"] == (
        replacement.PREFLIGHT_CORRECTION_ADDENDUM_RELATIVE_PATH
    )
    assert contract["post_preflight_fix_focused_test_output_relative_path"] == (
        replacement.POST_PREFLIGHT_FIX_FOCUSED_TEST_OUTPUT_RELATIVE_PATH
    )
    assert contract["focused_test_total_invocation_count_max"] == 3
    assert contract["focused_test_total_invocation_count"] == 3
    assert contract["corrected_candidate_result"] == "passed"
    assert contract[
        "outcome_blind_real_artifact_preflight_required_before_review_lock"
    ] is True
    assert contract["real_artifact_preflight_command"] == list(
        replacement.REAL_ARTIFACT_PREFLIGHT_COMMAND
    )
    assert contract["real_artifact_preflight_invocation_count"] == 2
    assert contract["real_artifact_preflight_invocation_count_max"] == 2
    assert contract["first_failed_real_artifact_preflight_receipt_created"] is False
    assert contract["first_failed_real_artifact_preflight_error_lines"] == list(
        replacement.FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_ERROR_LINES
    )
    assert contract["real_artifact_preflight_may_read_review_lock"] is False
    assert contract["real_artifact_preflight_may_build_replacement_intent"] is False
    assert contract["real_artifact_preflight_may_publish_gcs"] is False
    assert contract["real_artifact_preflight_may_submit_cloud_execution"] is False
    assert contract["real_artifact_preflight_cloud_read_performed"] is True
    assert contract["real_artifact_preflight_cloud_mutation_executed"] is False
    assert contract["real_artifact_preflight_gcs_publication_count"] == 0
    assert contract["real_artifact_preflight_cloud_submit_count"] == 0
    receipt_law = contract["post_submission_receipt_validation_law"]
    assert receipt_law["launch_ownership_schema_version"] == (
        replacement.LAUNCH_OWNERSHIP_SCHEMA
    )
    assert receipt_law["worker_stage_start_schema_version"] == (
        replacement.REPLACEMENT_STAGE_START_SCHEMA
    )
    assert receipt_law["exact_key_sets_required"] is True
    assert receipt_law["extra_fields_allowed"] is False
    assert contract["replacement_intent_delete_allowed"] is False
    assert contract["replacement_intent_overwrite_allowed"] is False
    assert contract["replacement_intent_mutation_allowed"] is False
    assert contract["unequal_replacement_intent_collision_terminal"] is True
    assert contract["equal_existing_replacement_intent_resolve_only"] is True
    assert contract["original_or_recovery_object_delete_allowed"] is False
    assert contract["original_or_recovery_object_overwrite_allowed"] is False
    assert contract["original_or_recovery_object_mutation_allowed"] is False
    assert contract["all_recovery_and_bridge_publications_create_once"] is True
    assert contract["unequal_recovery_or_bridge_collision_terminal"] is True
    absent = set(contract["absent_before_replacement_uris"])
    assert absent == set(replacement._ABSENT_BEFORE_REPLACEMENT)
    assert set(contract["absent_effect_surface_uris"]) == set(
        replacement._ABSENT_EFFECT_SURFACE
    )
    assert replacement.REPLACEMENT_INTENT_URI in absent
    assert replacement.REPLACEMENT_INTENT_URI not in set(
        contract["absent_effect_surface_uris"]
    )
    assert contract["new_authorization_requires_intent_uri_absent"] is True
    assert (
        contract["equal_existing_intent_resolution_requires_intent_uri_absent"]
        is False
    )
    assert contract["equal_existing_intent_resolution_must_not_launch"] is True
    assert replacement.RESULT_URI in absent
    assert replacement.PRIMARY_STAGE_RECEIPT_URI in absent
    assert replacement.REPLACEMENT_RUNTIME_MEASUREMENT_URI in absent
    assert replacement.ACCEPTANCE_URI in absent
    assert replacement.BRIDGE_VERIFIER_RUNTIME_MEASUREMENT_URI in absent
    assert replacement.SUPPLEMENTAL_LANE_ROOT_URI in absent
    assert replacement.SUPPLEMENTAL_PANEL_ROOT_URI in absent
    assert contract["primary_attempt_reuse_allowed"] is False
    assert contract["second_replacement_allowed"] is False
    assert contract["v1_lane_root_can_directly_accept_worker_attempt_one"] is False
    assert contract["ordinal_seven_resume_before_bridge_verifier_allowed"] is False
    for field in replacement._FALSE_AUTHORITY_FIELDS:
        assert contract[field] is False


def test_contract_rejects_coherently_rehashed_name_only_empty_allowlist_change() -> None:
    contract = replacement.frozen_platform_replacement_contract_v1()
    names = list(contract["primary_name_only_empty_environment_names"])
    names[-1] = "T230_UNKNOWN_BYTES"
    contract["primary_name_only_empty_environment_names"] = names
    contract["primary_name_only_empty_environment_names_sha256"] = (
        batch.canonical_sha256(names)
    )
    _rehash(contract, "platform_replacement_contract_sha256")

    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.validate_platform_replacement_contract_v1(contract)


def test_terminal_projection_accepts_only_authoritative_exact_literals() -> None:
    assert replacement.TASK_DESCRIBE_ARGV == (
        "gcloud",
        "beta",
        "run",
        "jobs",
        "executions",
        "tasks",
        "list",
        "--execution=atlas-minimal-c-s2023-w1-v1-rffts",
        "--project=nfl-predictions-503414",
        "--region=us-central1",
        "--limit=2",
        "--format=json",
    )
    assert replacement.validate_primary_terminal_projection_v1(_terminal()) == _terminal()


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("execution_name", "atlas-minimal-c-s2023-w1-v1-other"),
        ("runtime_attempt_ordinal", 1),
        ("cloud_task_name", "different-task0"),
        ("completed_status", "True"),
        ("task_completed_status", "True"),
        ("execution_describe_argv", ["gcloud", "list"]),
        ("execution_describe_stdout_sha256", "f" * 63),
        ("execution_describe_stdout_bytes", 0),
        ("execution_describe_stdout_bytes", True),
        ("task_describe_argv", ["gcloud", "list"]),
        ("task_describe_stdout_sha256", "f" * 63),
        ("task_describe_stdout_bytes", 0),
        ("task_describe_stdout_bytes", True),
        ("configured_environment_sha256", "f" * 63),
        ("configured_environment_entry_count", 0),
        ("configured_environment_entry_count", True),
        ("completed_message", "Task failed because of timeout"),
        (
            "completed_message",
            "Task atlas-minimal-c-s2023-w1-v1-rffts-task0 failed with "
            "exit code: 0 and message: Internal error",
        ),
        (
            "completed_message",
            "Task atlas-minimal-c-s2023-w1-v1-rffts-task0 failed with "
            "exit code: 0 and message: internal error.",
        ),
        (
            "completed_message",
            " Task atlas-minimal-c-s2023-w1-v1-rffts-task0 failed with "
            "exit code: 0 and message: Internal error.",
        ),
        (
            "completed_message",
            "Task atlas-minimal-c-s2023-w1-v1-rffts-task0 failed with  "
            "exit code: 0 and message: Internal error.",
        ),
        (
            "completed_message",
            "Task atlas-minimal-c-s2023-w1-v1-rffts-task0 failed with "
            "exit code: 0 and message: Internal error. extra",
        ),
        ("failed_count", 0),
        ("succeeded_count", 1),
        ("cancelled_count", 1),
        ("max_retries", 1),
        ("task_spec", {"index": 0}),
        ("task_status_index_present", True),
        ("task_status_retried_present", True),
        ("task_last_attempt_exit_code_present", True),
        ("last_attempt_status_code", 12),
        ("last_attempt_status_message", "Internal error"),
        ("last_attempt_status_message", "internal error."),
        ("last_attempt_status_message", " Internal error."),
        ("last_attempt_status_message", "Internal error. "),
        ("execution_completed_message_exit_code", 1),
        ("image", "example.invalid/image@sha256:" + "f" * 64),
        ("frozen_runtime_payload_sha256", "f" * 64),
        ("frozen_runtime_payload_bytes", 7687),
        ("system_platform_error_observed", False),
        ("result_or_effect_content_inspected", True),
        ("realized_outcomes_read", True),
    ],
)
def test_terminal_projection_rejects_every_nonexact_failure(
    field: str, changed: object
) -> None:
    value = _terminal()
    value[field] = changed
    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.validate_primary_terminal_projection_v1(value)


def test_terminal_projection_rejects_changed_primary_runtime_identity() -> None:
    value = _terminal()
    value["primary_runtime_measurement_identity"] = dict(
        value["primary_runtime_measurement_identity"]
    )
    value["primary_runtime_measurement_identity"]["generation"] = "2"
    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.validate_primary_terminal_projection_v1(value)


def test_review_lock_binds_truthful_failed_and_corrected_focused_history() -> None:
    implementations = _implementations()
    lock = _review_lock(implementations)

    assert replacement.validate_recovery_review_lock_v1(
        lock,
        expected_implementation_measurements=implementations,
    ) == lock
    assert [
        row["relative_path"]
        for row in lock["reviewed_implementation_measurements"]
    ] == [
        replacement.IMPLEMENTATION_RELATIVE_PATH,
        replacement.TEST_RELATIVE_PATH,
        replacement.CONTROLLER_RELATIVE_PATH,
        replacement.CONTROLLER_TEST_RELATIVE_PATH,
    ]
    assert lock["focused_test_command"] == list(replacement.FOCUSED_TEST_COMMAND)
    assert lock["prior_failed_invocation_count"] == 1
    assert lock["prior_failed_pytest_exit_code"] == 1
    assert lock["prior_failed_failure_node_ids"] == list(
        replacement.PRIOR_FAILED_FOCUSED_TEST_NODE_IDS
    )
    assert lock["prior_failed_collected_passed_counts_available"] is False
    assert lock["prior_failed_test_output_sha256_available"] is False
    assert lock["first_corrected_candidate_invocation_count"] == 1
    assert lock["first_corrected_tests_collected"] == 271
    assert lock["first_corrected_tests_passed"] == 271
    assert lock["first_corrected_focused_test_output_measurement"] == (
        _first_corrected_focused_test_output_measurement()
    )
    assert lock["post_preflight_fix_focused_test_output_measurement"] == (
        _post_preflight_fix_focused_test_output_measurement()
    )
    assert lock["corrected_candidate_invocation_count"] == 1
    assert lock["corrected_candidate_invocation_count_max"] == 1
    assert lock["focused_test_total_invocation_count"] == 3
    assert lock["focused_test_total_invocation_count_max"] == 3
    assert lock["corrected_candidate_result"] == "passed"
    assert lock["correction_addendum_measurement"] == (
        _correction_addendum_measurement()
    )
    assert lock["real_artifact_preflight_command"] == list(
        replacement.REAL_ARTIFACT_PREFLIGHT_COMMAND
    )
    assert lock["real_artifact_preflight_invocation_count"] == 2
    assert lock["real_artifact_preflight_invocation_count_max"] == 2
    assert lock["real_artifact_preflight_passed"] is True
    assert lock["first_failed_real_artifact_preflight_invocation_count"] == 1
    assert lock["first_failed_real_artifact_preflight_exit_code"] == 1
    assert lock["first_failed_real_artifact_preflight_receipt_created"] is False
    assert lock["corrected_real_artifact_preflight_invocation_count"] == 1
    assert lock["real_artifact_preflight_realized_outcomes_read"] is False
    assert lock["focused_test_cloud_call_count"] == 0
    assert lock["cloud_read_performed"] is True
    assert lock["cloud_mutation_executed"] is False
    assert lock["gcs_publication_count"] == 0
    assert lock["cloud_submit_count"] == 0
    assert lock["realized_outcomes_read"] is False
    canonical_tracked_bytes = batch.canonical_json_bytes(lock) + b"\n"
    binding = _review_lock_binding(lock)
    assert binding["sha256"] == sha256(canonical_tracked_bytes).hexdigest()
    assert binding["bytes"] == len(canonical_tracked_bytes)


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("reviewed_candidate_disposition", "accepted"),
        ("controller_ast_parse_passed", False),
        ("controller_tests_ast_parse_passed", False),
        ("prior_failed_invocation_count", 0),
        ("prior_failed_pytest_exit_code", 0),
        ("prior_failed_failure_node_ids", []),
        ("prior_failed_cloud_call_count", 1),
        ("prior_failed_preflight_invocation_count", 1),
        ("prior_failed_intent_built", True),
        ("prior_failed_realized_outcomes_read", True),
        ("prior_failed_collected_passed_counts_available", True),
        ("prior_failed_test_output_sha256_available", True),
        ("corrected_candidate_invocation_count", 2),
        ("corrected_candidate_invocation_count_max", 2),
        ("focused_test_total_invocation_count", 1),
        ("focused_test_total_invocation_count_max", 4),
        ("corrected_candidate_result", "failed"),
        ("real_artifact_preflight_command", ["different"]),
        ("real_artifact_preflight_invocation_count", 1),
        ("real_artifact_preflight_invocation_count", True),
        ("real_artifact_preflight_invocation_count_max", 3),
        ("first_failed_real_artifact_preflight_receipt_created", True),
        ("first_failed_real_artifact_preflight_exit_code", 0),
        ("first_corrected_tests_collected", 270),
        ("first_corrected_test_output_sha256", "e" * 64),
        ("real_artifact_preflight_passed", False),
        ("real_artifact_preflight_realized_outcomes_read", True),
        ("focused_test_cloud_call_count", 1),
        ("cloud_read_performed", False),
        ("cloud_mutation_executed", True),
        ("gcs_publication_count", 1),
        ("cloud_submit_count", 1),
        ("tests_failed", 1),
        ("pytest_exit_code", 1),
        ("test_output_sha256", "f" * 64),
        ("test_output_bytes", 1),
        ("realized_outcomes_read", True),
        ("independent_review_complete", False),
    ],
)
def test_review_lock_rejects_widening_or_incomplete_review(
    field: str, changed: object
) -> None:
    lock = _review_lock()
    lock[field] = changed
    _rehash(lock, "review_lock_sha256")
    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.validate_recovery_review_lock_v1(
            lock,
            expected_implementation_measurements=_implementations(),
        )


def test_review_lock_rejects_current_source_controller_or_test_drift() -> None:
    implementations = _implementations()
    lock = _review_lock(implementations)
    for ordinal in range(len(implementations)):
        changed = deepcopy(implementations)
        changed[ordinal]["sha256"] = "e" * 64
        with pytest.raises(replacement.T230PlatformReplacementError):
            replacement.validate_recovery_review_lock_v1(
                lock,
                expected_implementation_measurements=changed,
            )


def test_review_lock_rejects_coherently_rehashed_failed_candidate_history() -> None:
    lock = _review_lock()
    failed = deepcopy(lock["failed_focused_test_candidate_measurements"])
    failed[0]["sha256"] = "c" * 64
    lock["failed_focused_test_candidate_measurements"] = failed
    lock["failed_focused_test_candidate_measurements_sha256"] = (
        batch.canonical_sha256(failed)
    )
    _rehash(lock, "review_lock_sha256")

    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.validate_recovery_review_lock_v1(
            lock,
            expected_implementation_measurements=_implementations(),
        )


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("relative_path", "reports/different.json"),
        ("sha256", "e" * 63),
        ("bytes", 0),
        ("bytes", True),
    ],
)
def test_review_lock_rejects_changed_preflight_receipt_measurement(
    field: str, changed: object
) -> None:
    lock = _review_lock()
    measurement = dict(lock["real_artifact_preflight_receipt_measurement"])
    measurement[field] = changed
    lock["real_artifact_preflight_receipt_measurement"] = measurement
    _rehash(lock, "review_lock_sha256")
    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.validate_recovery_review_lock_v1(
            lock,
            expected_implementation_measurements=_implementations(),
        )


def test_reopen_review_lock_rejects_valid_wrong_preflight_file_sha(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    implementations = _implementations()
    repository_root = transport.REPOSITORY_ROOT
    retained_measurements: dict[str, dict[str, object]] = {}
    for relative_path in (
        replacement.CORRECTION_ADDENDUM_RELATIVE_PATH,
        replacement.PREFLIGHT_CORRECTION_ADDENDUM_RELATIVE_PATH,
        replacement.FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
    ):
        raw = (repository_root / relative_path).read_bytes()
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        retained_measurements[relative_path] = {
            "relative_path": relative_path,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
    addendum_measurement = retained_measurements[
        replacement.CORRECTION_ADDENDUM_RELATIVE_PATH
    ]
    preflight_addendum_measurement = retained_measurements[
        replacement.PREFLIGHT_CORRECTION_ADDENDUM_RELATIVE_PATH
    ]
    first_corrected_output_measurement = retained_measurements[
        replacement.FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_RELATIVE_PATH
    ]
    post_preflight_fix_output_raw = b"post-preflight-fix focused-test fixture\n"
    post_preflight_fix_output_path = (
        tmp_path
        / replacement.POST_PREFLIGHT_FIX_FOCUSED_TEST_OUTPUT_RELATIVE_PATH
    )
    post_preflight_fix_output_path.parent.mkdir(parents=True, exist_ok=True)
    post_preflight_fix_output_path.write_bytes(post_preflight_fix_output_raw)
    post_preflight_fix_output_measurement = {
        "relative_path": (
            replacement.POST_PREFLIGHT_FIX_FOCUSED_TEST_OUTPUT_RELATIVE_PATH
        ),
        "sha256": sha256(post_preflight_fix_output_raw).hexdigest(),
        "bytes": len(post_preflight_fix_output_raw),
    }
    receipt = replacement._build_real_artifact_preflight_receipt_v1(
        terminal_projection=_terminal(),
        primary_lineage=_lineage(),
        correction_addendum_measurement=addendum_measurement,
        preflight_correction_addendum_measurement=(
            preflight_addendum_measurement
        ),
        first_corrected_focused_test_output_measurement=(
            first_corrected_output_measurement
        ),
        post_preflight_fix_focused_test_output_measurement=(
            post_preflight_fix_output_measurement
        ),
        recovery_implementation_measurements=implementations,
        replacement_worker_launch_plan=_launch_plan(),
        replacement_live_job_projection=_live_job(),
    )
    receipt_raw = batch.canonical_json_bytes(receipt) + b"\n"
    receipt_path = (
        tmp_path
        / replacement.REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH
    )
    receipt_path.write_bytes(receipt_raw)
    actual_receipt_sha = sha256(receipt_raw).hexdigest()
    wrong_valid_sha = "0" * 64
    assert wrong_valid_sha != actual_receipt_sha
    lock = _review_lock(
        implementations,
        correction_addendum_measurement=addendum_measurement,
        preflight_correction_addendum_measurement=(
            preflight_addendum_measurement
        ),
    )
    lock["post_preflight_fix_focused_test_output_measurement"] = (
        post_preflight_fix_output_measurement
    )
    lock["test_output_sha256"] = post_preflight_fix_output_measurement["sha256"]
    lock["test_output_bytes"] = post_preflight_fix_output_measurement["bytes"]
    lock["real_artifact_preflight_receipt_measurement"] = {
        "relative_path": (
            replacement.REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH
        ),
        "sha256": wrong_valid_sha,
        "bytes": len(receipt_raw),
    }
    _rehash(lock, "review_lock_sha256")
    lock_path = tmp_path / replacement.REVIEW_LOCK_RELATIVE_PATH
    lock_path.write_bytes(batch.canonical_json_bytes(lock) + b"\n")
    monkeypatch.setattr(transport, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(
        replacement,
        "_implementation_measurements",
        lambda: deepcopy(implementations),
    )

    with pytest.raises(
        replacement.T230PlatformReplacementError,
        match="tracked real-artifact preflight receipt bytes differ",
    ):
        replacement._reopen_recovery_review_lock_v1(_Backend())


def test_intent_is_exact_attempt_one_offline_candidate_and_authority_closed() -> None:
    intent = _intent()

    assert replacement.validate_platform_replacement_intent_v1(intent) == intent
    assert intent["primary_runtime_attempt_ordinal"] == 0
    assert intent["replacement_runtime_attempt_ordinal"] == 1
    assert intent["max_replacement_worker_executions"] == 1
    assert intent["replacement_worker_limit_excludes_bridge_verifier"] is True
    assert intent["max_bridge_verifier_executions_after_worker_success"] == 1
    assert intent["pre_submit_live_job_exact_description_required"] is True
    assert (
        intent["pre_submit_live_job_must_equal_replacement_execution_envelope"]
        is True
    )
    assert intent["changed_or_ambiguous_live_job_is_terminal"] is True
    assert intent["correction_addendum_measurement"] == (
        _correction_addendum_measurement()
    )
    assert intent["preflight_correction_addendum_measurement"] == (
        _preflight_correction_addendum_measurement()
    )
    assert intent["first_corrected_focused_test_output_measurement"] == (
        _first_corrected_focused_test_output_measurement()
    )
    assert intent["post_preflight_fix_focused_test_output_measurement"] == (
        _post_preflight_fix_focused_test_output_measurement()
    )
    assert intent["prior_failed_invocation_count"] == 1
    assert intent["corrected_candidate_invocation_count"] == 1
    assert intent["focused_test_total_invocation_count"] == 3
    assert intent["corrected_candidate_result"] == "passed"
    assert intent[
        "no_launch_authority_before_corrected_pass_preflight_and_lock"
    ] is True
    assert intent["real_artifact_preflight_command"] == list(
        replacement.REAL_ARTIFACT_PREFLIGHT_COMMAND
    )
    assert intent["real_artifact_preflight_invocation_count"] == 2
    assert intent["real_artifact_preflight_passed"] is True
    assert intent["real_artifact_preflight_cloud_read_performed"] is True
    assert intent["real_artifact_preflight_cloud_mutation_executed"] is False
    assert intent["real_artifact_preflight_gcs_publication_count"] == 0
    assert intent["real_artifact_preflight_cloud_submit_count"] == 0
    assert intent["real_artifact_preflight_realized_outcomes_read"] is False
    assert intent["post_submission_receipt_validation_law"] == (
        replacement.frozen_platform_replacement_contract_v1()[
            "post_submission_receipt_validation_law"
        ]
    )
    for field in (
        "submission_failure_terminal_create_once_required",
        "ambiguous_submission_requires_terminal_receipt",
        "nonzero_submission_requires_terminal_receipt",
        "malformed_submission_response_requires_terminal_receipt",
        "unverified_submitted_envelope_requires_terminal_receipt",
        "terminal_receipt_publication_failure_still_consumes_attempt",
    ):
        assert intent[field] is True
    assert intent["create_once_generation_match"] == 0
    assert intent["replacement_intent_delete_allowed"] is False
    assert intent["replacement_intent_overwrite_allowed"] is False
    assert intent["replacement_intent_mutation_allowed"] is False
    assert intent["unequal_replacement_intent_collision_terminal"] is True
    assert intent["equal_existing_replacement_intent_resolve_only"] is True
    assert intent["original_or_recovery_object_delete_allowed"] is False
    assert intent["original_or_recovery_object_overwrite_allowed"] is False
    assert intent["original_or_recovery_object_mutation_allowed"] is False
    assert intent["all_recovery_and_bridge_publications_create_once"] is True
    assert intent["unequal_recovery_or_bridge_collision_terminal"] is True
    assert intent["offline_component_grants_launch_permission"] is False
    assert intent["same_process_launch_controller_review_required"] is True
    assert intent["original_launch_request_reused"] is False
    assert intent["primary_runtime_attempt_reused"] is False
    assert intent["second_replacement_allowed"] is False
    assert intent["replacement_runtime_measurement_uri"] == (
        replacement.REPLACEMENT_RUNTIME_MEASUREMENT_URI
    )
    assert intent["separate_success_completion_required"] is True
    assert intent["supplemental_lane_and_panel_roots_required"] is True
    assert intent["review_lock_binding"]["tracked_at_head"] is True
    assert intent["review_lock"] == _review_lock(_implementations())
    assert intent["replacement_worker_launch_plan"] == _launch_plan()
    assert intent["replacement_worker_launch_plan_sha256"] == _launch_plan()[
        "worker_launch_plan_sha256"
    ]
    assert intent["replacement_live_job_projection"] == _live_job()
    assert intent["replacement_live_job_projection_sha256"] == (
        batch.canonical_sha256(_live_job())
    )
    for field in replacement._FALSE_AUTHORITY_FIELDS:
        assert intent[field] is False


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("runtime_attempt_ordinal", 0),
        ("max_submission_calls", 2),
        ("task_count", 2),
        ("parallelism", 2),
        ("max_retries", 1),
        ("submission_mode", "sync"),
        ("post_submission_receipt_validation_law", {}),
        ("post_submission_receipt_validation_law_sha256", "f" * 64),
        ("same_process_intent_create_and_submission_required", False),
        ("request_consumed_on_ambiguous_submission", False),
        ("result_or_effect_content_inspected_before_submission", True),
        ("uses_realized_outcomes", True),
    ],
)
def test_intent_rejects_widened_or_changed_worker_launch_plan(
    field: str, changed: object
) -> None:
    plan = _launch_plan()
    plan[field] = changed
    _rehash(plan, "worker_launch_plan_sha256")
    implementations = _implementations()
    lock = _review_lock(implementations)
    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.build_platform_replacement_intent_v1(
            terminal_projection=_terminal(),
            primary_lineage=_lineage(),
            review_lock_binding=_review_lock_binding(lock),
            review_lock=lock,
            recovery_implementation_measurements=implementations,
            replacement_worker_launch_plan=plan,
            replacement_live_job_projection=_live_job(),
        )


def test_intent_rejects_worker_launch_plan_envelope_mutation() -> None:
    plan = _launch_plan()
    plan["execution_envelope"] = deepcopy(plan["execution_envelope"])
    plan["execution_envelope"]["cpu"] = "4"
    _rehash(plan, "worker_launch_plan_sha256")
    implementations = _implementations()
    lock = _review_lock(implementations)
    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.build_platform_replacement_intent_v1(
            terminal_projection=_terminal(),
            primary_lineage=_lineage(),
            review_lock_binding=_review_lock_binding(lock),
            review_lock=lock,
            recovery_implementation_measurements=implementations,
            replacement_worker_launch_plan=plan,
            replacement_live_job_projection=_live_job(),
        )


def test_intent_rejects_image_evidence_not_bound_by_frozen_authority() -> None:
    plan = _launch_plan()
    plan["image_evidence_identity"] = _identity(
        "gs://fixture/different-image-evidence.json", "f"
    )
    _rehash(plan, "worker_launch_plan_sha256")
    implementations = _implementations()
    lock = _review_lock(implementations)
    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.build_platform_replacement_intent_v1(
            terminal_projection=_terminal(),
            primary_lineage=_lineage(),
            review_lock_binding=_review_lock_binding(lock),
            review_lock=lock,
            recovery_implementation_measurements=implementations,
            replacement_worker_launch_plan=plan,
            replacement_live_job_projection=_live_job(),
        )


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("job", "different-job"),
        ("image", "example.invalid/image@sha256:" + "f" * 64),
        ("service_account", "other@example.invalid"),
        ("cpu", "4"),
        ("memory", "16Gi"),
        ("task_count", 2),
        ("parallelism", 2),
        ("max_retries", 1),
        ("task_timeout_seconds", 21599),
        ("command", ["python"]),
        ("args", ["different"]),
        ("configured_environment", {"UNEXPECTED": "1"}),
        (
            "runtime_evidence_volume",
            {
                "type": "in-memory",
                "name": "wrong",
                "size_limit": "1Mi",
                "mount_path": "/etc/nfl-dfs",
            },
        ),
        ("describe_argv", ["gcloud", "run", "jobs", "list"]),
        ("describe_stdout_sha256", "f" * 63),
        ("describe_stdout_bytes", 0),
        ("describe_stdout_bytes", True),
        ("cloud_describe_exactly_validated", False),
    ],
)
def test_intent_rejects_changed_or_ambiguous_live_reused_job(
    field: str, changed: object
) -> None:
    implementations = _implementations()
    lock = _review_lock(implementations)
    live_job = _live_job()
    live_job[field] = changed
    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.build_platform_replacement_intent_v1(
            terminal_projection=_terminal(),
            primary_lineage=_lineage(),
            review_lock_binding=_review_lock_binding(lock),
            review_lock=lock,
            recovery_implementation_measurements=implementations,
            replacement_worker_launch_plan=_launch_plan(),
            replacement_live_job_projection=live_job,
        )


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("replacement_runtime_attempt_ordinal", 0),
        ("max_replacement_worker_executions", 2),
        ("replacement_worker_limit_excludes_bridge_verifier", False),
        ("max_bridge_verifier_executions_after_worker_success", 2),
        ("pre_submit_live_job_exact_description_required", False),
        ("pre_submit_live_job_must_equal_replacement_execution_envelope", False),
        ("changed_or_ambiguous_live_job_is_terminal", False),
        ("real_artifact_preflight_invocation_count", 1),
        ("real_artifact_preflight_passed", False),
        ("real_artifact_preflight_cloud_read_performed", False),
        ("real_artifact_preflight_cloud_mutation_executed", True),
        ("real_artifact_preflight_gcs_publication_count", 1),
        ("real_artifact_preflight_cloud_submit_count", 1),
        ("real_artifact_preflight_realized_outcomes_read", True),
        ("post_submission_receipt_validation_law", {}),
        ("submission_failure_terminal_create_once_required", False),
        ("ambiguous_submission_requires_terminal_receipt", False),
        ("nonzero_submission_requires_terminal_receipt", False),
        ("malformed_submission_response_requires_terminal_receipt", False),
        ("unverified_submitted_envelope_requires_terminal_receipt", False),
        ("terminal_receipt_publication_failure_still_consumes_attempt", False),
        ("second_replacement_allowed", True),
        ("replacement_intent_delete_allowed", True),
        ("replacement_intent_overwrite_allowed", True),
        ("replacement_intent_mutation_allowed", True),
        ("unequal_replacement_intent_collision_terminal", False),
        ("equal_existing_replacement_intent_resolve_only", False),
        ("original_or_recovery_object_delete_allowed", True),
        ("original_or_recovery_object_overwrite_allowed", True),
        ("original_or_recovery_object_mutation_allowed", True),
        ("all_recovery_and_bridge_publications_create_once", False),
        ("unequal_recovery_or_bridge_collision_terminal", False),
        ("offline_component_grants_launch_permission", True),
        ("bridge_verifier_licensed", True),
        ("lane_resume_licensed", True),
        ("historical_scoring_licensed", True),
        ("uses_realized_outcomes", True),
    ],
)
def test_intent_rejects_coherently_rehashed_widening(
    field: str, changed: object
) -> None:
    value = _intent()
    value[field] = changed
    _rehash(value, "platform_replacement_intent_sha256")
    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.validate_platform_replacement_intent_v1(value)


@pytest.mark.parametrize(
    ("path", "changed"),
    [
        (("job",), "different-job"),
        (("operation",), "verify-slate"),
        (("source_ordinal",), 7),
        (("runtime_attempt_ordinal",), 0),
        (("immutable_image", "uri"), "example.invalid/image@sha256:" + "f" * 64),
        (("immutable_image", "digest"), "sha256:" + "f" * 64),
        (("service_account",), "other@example.invalid"),
        (("cpu",), "4"),
        (("memory",), "16Gi"),
        (("task_count",), 2),
        (("parallelism",), 2),
        (("max_retries",), 1),
        (("task_timeout_seconds",), 21599),
        (("runtime_evidence_volume", "type"), "secret"),
        (("runtime_evidence_volume", "name"), "other"),
        (("runtime_evidence_volume", "size_limit"), "2Mi"),
        (("runtime_evidence_volume", "mount_path"), "/tmp/evidence"),
        (("transport_contract_identity", "generation"), "2"),
        (("job_config_identity", "generation"), "2"),
        (("execution_authority_identity", "generation"), "2"),
        (("compute_release_identity", "generation"), "2"),
        (("predecessor_identity", "generation"), "2"),
    ],
)
def test_intent_rejects_every_attempt_one_envelope_mutation(
    path: tuple[str, ...], changed: object
) -> None:
    value = _intent()
    retained = value["replacement_execution_envelope"]
    assert isinstance(retained, dict)
    for field in path[:-1]:
        retained = retained[field]
        assert isinstance(retained, dict)
    retained[path[-1]] = changed
    _rehash(value, "platform_replacement_intent_sha256")
    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.validate_platform_replacement_intent_v1(value)


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("relative_path", "reports/other.json"),
        ("source_commit_sha", "f" * 39),
        ("sha256", "f" * 64),
        ("bytes", 1),
        ("tracked_at_head", False),
        ("clean_at_head", False),
    ],
)
def test_intent_rejects_untracked_or_changed_review_lock_binding(
    field: str, changed: object
) -> None:
    implementations = _implementations()
    lock = _review_lock(implementations)
    binding = _review_lock_binding(lock)
    binding[field] = changed
    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.build_platform_replacement_intent_v1(
            terminal_projection=_terminal(),
            primary_lineage=_lineage(),
            review_lock_binding=binding,
            review_lock=lock,
            recovery_implementation_measurements=implementations,
            replacement_worker_launch_plan=_launch_plan(),
            replacement_live_job_projection=_live_job(),
        )


def test_intent_rejects_changed_exact_primary_launch_identity() -> None:
    lineage = _lineage()
    lineage["primary_launch_request_identity"] = dict(
        lineage["primary_launch_request_identity"]
    )
    lineage["primary_launch_request_identity"]["generation"] = "2"
    implementations = _implementations()
    lock = _review_lock(implementations)
    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.build_platform_replacement_intent_v1(
            terminal_projection=_terminal(),
            primary_lineage=lineage,
            review_lock_binding=_review_lock_binding(lock),
            review_lock=lock,
            recovery_implementation_measurements=implementations,
            replacement_worker_launch_plan=_launch_plan(),
            replacement_live_job_projection=_live_job(),
        )


def test_real_artifact_preflight_is_lock_free_read_only_and_authority_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _Backend()
    implementations = _implementations()
    monkeypatch.setattr(
        replacement,
        "_reopen_fixed_primary_lineage_v1",
        lambda _backend: _lineage(),
    )
    monkeypatch.setattr(
        replacement,
        "_implementation_measurements",
        lambda: deepcopy(implementations),
    )
    monkeypatch.setattr(
        replacement,
        "_correction_addendum_measurement",
        lambda: _correction_addendum_measurement(),
    )
    monkeypatch.setattr(
        replacement,
        "_preflight_correction_addendum_measurement",
        lambda: _preflight_correction_addendum_measurement(),
    )
    monkeypatch.setattr(
        replacement,
        "_first_corrected_focused_test_output_measurement",
        lambda: _first_corrected_focused_test_output_measurement(),
    )
    monkeypatch.setattr(
        replacement,
        "_post_preflight_fix_focused_test_output_measurement",
        lambda: _post_preflight_fix_focused_test_output_measurement(),
    )
    monkeypatch.setattr(
        replacement,
        "_reopen_recovery_review_lock_v1",
        lambda _backend: (_ for _ in ()).throw(
            AssertionError("preflight must not read the review lock")
        ),
    )

    receipt = replacement.preflight_platform_replacement_real_artifacts_v1(
        backend=backend,
        replacement_worker_launch_plan=_launch_plan(),
        replacement_live_job_projection=_live_job(),
    )

    assert replacement.validate_platform_replacement_real_artifact_preflight_v1(
        receipt,
        expected_implementation_measurements=implementations,
    ) == receipt
    assert receipt["schema_version"] == replacement.REAL_ARTIFACT_PREFLIGHT_SCHEMA
    assert receipt["command"] == list(
        replacement.REAL_ARTIFACT_PREFLIGHT_COMMAND
    )
    assert receipt["invocation_count"] == 2
    assert receipt["invocation_count_max"] == 2
    assert receipt["first_failed_invocation_count"] == 1
    assert receipt["first_failed_exit_code"] == 1
    assert receipt["first_failed_error_lines"] == list(
        replacement.FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_ERROR_LINES
    )
    assert receipt["first_failed_receipt_created"] is False
    assert receipt["corrected_invocation_count"] == 1
    assert receipt["correction_addendum_measurement"] == (
        _correction_addendum_measurement()
    )
    assert receipt["preflight_correction_addendum_measurement"] == (
        _preflight_correction_addendum_measurement()
    )
    assert receipt["first_corrected_focused_test_output_measurement"] == (
        _first_corrected_focused_test_output_measurement()
    )
    assert receipt["post_preflight_fix_focused_test_output_measurement"] == (
        _post_preflight_fix_focused_test_output_measurement()
    )
    assert receipt["passed"] is True
    assert receipt["cloud_read_performed"] is True
    assert receipt["cloud_mutation_executed"] is False
    assert receipt["cloud_read_commands"] == [
        list(replacement.EXECUTION_DESCRIBE_ARGV),
        list(replacement.TASK_DESCRIBE_ARGV),
        list(replacement.LIVE_JOB_DESCRIBE_ARGV),
    ]
    assert receipt["cloud_read_command_count"] == 3
    assert receipt["gcs_publication_count"] == 0
    assert receipt["cloud_submit_count"] == 0
    assert receipt["realized_outcomes_read"] is False
    assert receipt["result_or_effect_content_inspected"] is False
    assert receipt["review_lock_read"] is False
    assert receipt["intent_built"] is False
    assert receipt["intent_published"] is False
    assert receipt["absence_uris"] == list(
        replacement._ABSENT_BEFORE_REPLACEMENT
    )
    assert receipt["absence_probe_count"] == (
        len(replacement._ABSENT_BEFORE_REPLACEMENT) * 2
    )
    assert backend.metadata_probe_uris == list(
        replacement._ABSENT_BEFORE_REPLACEMENT
    ) * 2
    assert backend.known_body_reads == []
    assert backend.create_calls == []
    for field in replacement._FALSE_AUTHORITY_FIELDS:
        assert receipt[field] is False


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("command", ["different"]),
        ("invocation_count", 1),
        ("invocation_count_max", 3),
        ("first_failed_invocation_count", 2),
        ("first_failed_error_lines", ["different"]),
        ("first_failed_output_measurement_available", True),
        ("first_failed_receipt_created", True),
        ("corrected_invocation_count", 2),
        ("absence_probe_count", 1),
        ("all_effect_surface_absent", False),
        ("flags_template_path", "/tmp/different.json"),
        ("passed", False),
        ("cloud_read_performed", False),
        ("cloud_mutation_executed", True),
        ("cloud_read_commands", []),
        ("cloud_read_command_count", 2),
        ("gcs_publication_count", 1),
        ("cloud_submit_count", 1),
        ("realized_outcomes_read", True),
        ("result_or_effect_content_inspected", True),
        ("review_lock_read", True),
        ("intent_built", True),
        ("intent_published", True),
    ],
)
def test_real_artifact_preflight_rejects_coherently_rehashed_widening(
    field: str, changed: object
) -> None:
    receipt = replacement._build_real_artifact_preflight_receipt_v1(
        terminal_projection=_terminal(),
        primary_lineage=_lineage(),
        correction_addendum_measurement=_correction_addendum_measurement(),
        preflight_correction_addendum_measurement=(
            _preflight_correction_addendum_measurement()
        ),
        first_corrected_focused_test_output_measurement=(
            _first_corrected_focused_test_output_measurement()
        ),
        post_preflight_fix_focused_test_output_measurement=(
            _post_preflight_fix_focused_test_output_measurement()
        ),
        recovery_implementation_measurements=_implementations(),
        replacement_worker_launch_plan=_launch_plan(),
        replacement_live_job_projection=_live_job(),
    )
    receipt[field] = changed
    _rehash(receipt, "real_artifact_preflight_sha256")
    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.validate_platform_replacement_real_artifact_preflight_v1(
            receipt,
            expected_implementation_measurements=_implementations(),
        )


def test_candidate_operator_is_metadata_only_and_never_publishes_or_authorizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _Backend()
    _patch_candidate_dependencies(monkeypatch)

    result = replacement.prepare_platform_replacement_intent_candidate_v1(
        backend=backend,
        replacement_worker_launch_plan=_launch_plan(),
        replacement_live_job_projection=_live_job(),
    )

    assert result["disposition"] == "offline-intent-candidate-only"
    assert result["intent_identity"] is None
    assert result["intent_created_by_this_invocation"] is False
    assert result["cloud_execution_submission_allowed_this_invocation"] is False
    assert result["same_process_launch_controller_review_required"] is True
    assert result["resolve_only"] is True
    assert backend.observed_execution_names == [replacement.FAILED_EXECUTION]
    assert backend.metadata_probe_uris == list(
        replacement._ABSENT_BEFORE_REPLACEMENT
    ) * 2
    assert backend.known_body_reads == []
    assert backend.create_calls == []
    for field in replacement._FALSE_AUTHORITY_FIELDS:
        assert result[field] is False


def test_equal_existing_intent_replay_is_reachable_exact_and_resolve_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _Backend()
    intent = _intent()
    intent_identity = backend._put(
        replacement.REPLACEMENT_INTENT_URI,
        batch.canonical_json_bytes(intent),
    )
    _patch_candidate_dependencies(monkeypatch)

    result = replacement.resolve_equal_existing_platform_replacement_intent_v1(
        backend=backend,
        replacement_worker_launch_plan=_launch_plan(),
        replacement_live_job_projection=_live_job(),
    )

    assert result["disposition"] == "equal-existing-intent-resolve-only"
    assert result["intent_identity"] == intent_identity
    assert result["intent"] == intent
    assert result["intent_created_by_this_invocation"] is False
    assert result["cloud_execution_submission_allowed_this_invocation"] is False
    assert result["resolve_only"] is True
    assert backend.metadata_probe_uris == list(
        replacement._ABSENT_EFFECT_SURFACE
    ) * 2
    assert replacement.REPLACEMENT_INTENT_URI not in backend.metadata_probe_uris
    assert backend.known_body_reads == [replacement.REPLACEMENT_INTENT_URI]
    assert backend.create_calls == []


def test_existing_unequal_intent_is_terminal_and_never_authorizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _Backend()
    backend._put(replacement.REPLACEMENT_INTENT_URI, b'{"different":true}')
    _patch_candidate_dependencies(monkeypatch)

    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.resolve_equal_existing_platform_replacement_intent_v1(
            backend=backend,
            replacement_worker_launch_plan=_launch_plan(),
            replacement_live_job_projection=_live_job(),
        )

    assert backend.known_body_reads == [replacement.REPLACEMENT_INTENT_URI]
    assert backend.create_calls == []


def test_resolve_only_replay_rejects_missing_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _Backend()
    _patch_candidate_dependencies(monkeypatch)

    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.resolve_equal_existing_platform_replacement_intent_v1(
            backend=backend,
            replacement_worker_launch_plan=_launch_plan(),
            replacement_live_job_projection=_live_job(),
        )

    assert backend.known_body_reads == [replacement.REPLACEMENT_INTENT_URI]
    assert backend.create_calls == []


@pytest.mark.parametrize("present_uri", replacement._ABSENT_BEFORE_REPLACEMENT)
def test_candidate_rejects_any_present_recovery_or_bridge_object_without_body_read(
    present_uri: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _Backend()
    backend._put(present_uri, b"must-not-be-read")
    _patch_candidate_dependencies(monkeypatch)

    with pytest.raises(replacement.T230PlatformReplacementError):
        replacement.prepare_platform_replacement_intent_candidate_v1(
            backend=backend,
            replacement_worker_launch_plan=_launch_plan(),
            replacement_live_job_projection=_live_job(),
        )

    assert backend.known_body_reads == []
    assert backend.create_calls == []


def test_live_intent_operator_fails_before_observation_probe_or_create() -> None:
    backend = _Backend()

    with pytest.raises(
        replacement.T230PlatformReplacementError,
        match="separately sealed same-process launch controller",
    ):
        replacement.prepare_platform_replacement_intent_once_v1(backend=backend)

    assert backend.observed_execution_names == []
    assert backend.metadata_probe_uris == []
    assert backend.known_body_reads == []
    assert backend.create_calls == []
