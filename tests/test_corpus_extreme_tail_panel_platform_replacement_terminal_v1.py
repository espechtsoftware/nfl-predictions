from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import (
    corpus_extreme_tail_panel_platform_replacement_terminal_v1 as closure,
)
from nfl_dfs.research import corpus_extreme_tail_panel_platform_replacement_v1 as replacement
from nfl_dfs.research import corpus_extreme_tail_panel_transport as transport
from nfl_dfs.research import corpus_parametric_batch as batch


def _envelope() -> dict[str, object]:
    return {
        "execution_name": closure.REPLACEMENT_EXECUTION,
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
        "args": ["-ceu", "frozen-payload"],
        "configured_environment": {"CLOUD_RUN_EXECUTION": closure.REPLACEMENT_EXECUTION},
        "runtime_evidence_volume": {
            "type": "in-memory",
            "name": "foundry-t230-runtime-evidence",
            "size_limit": "1Mi",
            "mount_path": "/etc/nfl-dfs",
        },
    }


def _terminal() -> dict[str, object]:
    return {
        "schema_version": closure.TERMINAL_PROJECTION_SCHEMA,
        "execution_name": closure.REPLACEMENT_EXECUTION,
        "task_name": closure.REPLACEMENT_TASK,
        "job": replacement.REUSE_JOB,
        "completed_status": "False",
        "completed_reason": closure.TASK_REASON,
        "completed_message": closure.EXECUTION_COMPLETED_MESSAGE,
        "execution_status_keys": [
            "completionTime",
            "conditions",
            "failedCount",
            "logUri",
            "observedGeneration",
            "startTime",
        ],
        "execution_conditions": deepcopy(closure.EXECUTION_CONDITIONS),
        "start_time": closure.REPLACEMENT_STARTED_TIME,
        "completion_time": closure.REPLACEMENT_COMPLETION_TIME,
        "failed_count": 1,
        "succeeded_count_present": False,
        "succeeded_count": 0,
        "cancelled_count_present": False,
        "cancelled_count": 0,
        "execution_observed_generation": 1,
        "log_uri": "https://console.cloud.google.com/run/jobs/executions/details/test",
        "log_content_read": False,
        "task_api_version": "run.googleapis.com/v1",
        "task_kind": "Task",
        "task_namespace": "817589974517",
        "task_resource_version": "AAZZ7FoYxOc",
        "task_self_link": (
            "/apis/run.googleapis.com/v1/namespaces/817589974517/tasks/"
            "atlas-minimal-c-s2023-w1-v1-67669-task0"
        ),
        "task_creation_time": closure.TASK_CREATION_TIME,
        "task_scheduled_time": closure.REPLACEMENT_STARTED_TIME,
        "task_start_time": closure.TASK_START_TIME,
        "task_completion_time": closure.TASK_COMPLETION_TIME,
        "task_running_state": "Failed",
        "task_spec": {},
        "task_completed_condition": {
            "message": closure.TASK_MESSAGE,
            "reason": closure.TASK_REASON,
            "status": "False",
            "type": "Completed",
        },
        "task_started_condition": {"status": "True", "type": "Started"},
        "task_last_attempt_result": {
            "exitCode": 1,
            "status": {"code": 10, "message": closure.TASK_MESSAGE},
        },
        "task_observed_generation": 1,
        "execution_envelope": _envelope(),
        "execution_describe_argv": list(closure.EXECUTION_DESCRIBE_ARGV),
        "execution_describe_stdout_sha256": "a" * 64,
        "execution_describe_stdout_bytes": 8192,
        "task_describe_argv": list(closure.TASK_DESCRIBE_ARGV),
        "task_describe_stdout_sha256": "b" * 64,
        "task_describe_stdout_bytes": 4096,
        "terminal_exactly_validated": True,
        "result_or_effect_content_inspected": False,
        "realized_outcomes_read": False,
    }


def _lineage() -> dict[str, object]:
    return {
        "replacement_intent_identity": dict(closure.REPLACEMENT_INTENT_IDENTITY),
        "platform_replacement_intent_sha256": "c" * 64,
        "replacement_launch_ownership_identity": dict(
            closure.REPLACEMENT_OWNERSHIP_IDENTITY
        ),
        "launch_ownership_sha256": "d" * 64,
        "replacement_stage_start_identity": dict(
            closure.REPLACEMENT_STAGE_START_IDENTITY
        ),
        "replacement_stage_start_sha256": "e" * 64,
        "replacement_execution": closure.REPLACEMENT_EXECUTION,
        "replacement_submitted_execution_semantic_sha256": batch.canonical_sha256(
            _envelope()
        ),
        "lineage_exactly_replayed": True,
        "result_or_effect_content_inspected": False,
        "realized_outcomes_read": False,
    }


def _rows() -> list[dict[str, object]]:
    return [
        {
            "uri": uri,
            "present": False,
            "generation": None,
            "size": None,
            "crc32c": None,
            "etag": None,
            "content_type": None,
            "content_inspected": False,
        }
        for uri in closure.terminal_surface_uris_v1()
    ]


def _lane_rows() -> list[dict[str, object]]:
    return [
        {
            "uri": uri,
            "present": False,
            "generation": None,
            "size": None,
            "crc32c": None,
            "etag": None,
            "content_type": None,
            "content_inspected": False,
        }
        for uri in closure.lane_a_terminal_surface_uris_v1()
    ]


def _implementations() -> list[dict[str, object]]:
    return closure.terminal_closure_implementation_measurements_v1()


def _marker() -> dict[str, object]:
    return closure.build_preflight_attempt_marker_v1(
        implementation_source_commit_sha="a" * 40,
        reviewed_implementation_measurements=_implementations(),
    )


def _marker_measurement() -> dict[str, object]:
    raw = batch.canonical_json_bytes(_marker()) + b"\n"
    return {
        "relative_path": closure.PREFLIGHT_ATTEMPT_RELATIVE_PATH,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _preflight() -> dict[str, object]:
    return closure.build_terminal_closure_preflight_v1(
        launch_lineage=_lineage(),
        terminal_projection=_terminal(),
        first_census=closure.build_surface_census_v1(
            rows=_rows(), pass_ordinal=1
        ),
        second_census=closure.build_surface_census_v1(
            rows=_rows(), pass_ordinal=2
        ),
        reviewed_implementation_measurements=_implementations(),
        preflight_attempt_marker_measurement=_marker_measurement(),
        preflight_attempt_marker=_marker(),
    )


def _terminal_receipt() -> dict[str, object]:
    preflight = _preflight()
    raw = batch.canonical_json_bytes(preflight) + b"\n"
    return closure.build_replacement_execution_terminal_v1(
        preflight_measurement={
            "relative_path": closure.PREFLIGHT_RELATIVE_PATH,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        },
        preflight=preflight,
        review_lock_measurement={
            "relative_path": closure.REVIEW_LOCK_RELATIVE_PATH,
            "sha256": "f" * 64,
            "bytes": 1234,
        },
        review_lock_sha256="1" * 64,
    )


def _identity(uri: str, raw: bytes, generation: str) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _measurement(relative_path: str, marker: str) -> dict[str, object]:
    return {"relative_path": relative_path, "sha256": marker * 64, "bytes": 10}


def _review_lock() -> tuple[
    dict[str, object],
    list[dict[str, object]],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    implementations = _implementations()
    marker = _marker()
    marker_measurement = _marker_measurement()
    preflight_body = _preflight()
    preflight_raw = batch.canonical_json_bytes(preflight_body) + b"\n"
    preflight_measurement = {
        "relative_path": closure.PREFLIGHT_RELATIVE_PATH,
        "sha256": sha256(preflight_raw).hexdigest(),
        "bytes": len(preflight_raw),
    }
    output = _measurement(closure.FOCUSED_TEST_OUTPUT_RELATIVE_PATH, "6")
    body = closure.build_terminal_closure_review_lock_v1(
        implementation_source_commit_sha="a" * 40,
        reviewed_implementation_measurements=implementations,
        preflight_attempt_marker_measurement=marker_measurement,
        preflight_attempt_marker=marker,
        real_artifact_preflight_measurement=preflight_measurement,
        real_artifact_preflight=preflight_body,
        focused_test_output_measurement=output,
        focused_test_collected=1,
    )
    return (
        body,
        implementations,
        marker_measurement,
        marker,
        preflight_measurement,
        preflight_body,
        output,
    )


def test_contract_is_terminal_and_grants_no_execution_or_scoring() -> None:
    value = closure.frozen_terminal_closure_contract_v1()
    assert closure.validate_terminal_closure_contract_v1(value) == value
    assert value["replacement_worker_execution_count"] == 1
    assert value["replacement_worker_execution_limit"] == 1
    assert value["second_replacement_allowed"] is False
    assert value["bridge_verifier_allowed"] is False
    assert value["current_panel_terminal_invalid"] is True
    assert value["historical_scoring_licensed"] is False


def test_preflight_attempt_marker_consumes_failure_and_rejects_retry_flip() -> None:
    value = _marker()
    assert closure.validate_preflight_attempt_marker_v1(value) == value
    assert value["attempt_consumed_even_if_read_or_process_fails"] is True
    assert value["second_preflight_attempt_allowed"] is False
    value["second_preflight_attempt_allowed"] = True
    value["preflight_attempt_marker_sha256"] = batch.canonical_sha256(
        {
            key: retained
            for key, retained in value.items()
            if key != "preflight_attempt_marker_sha256"
        }
    )
    with pytest.raises(closure.T230PlatformReplacementTerminalError):
        closure.validate_preflight_attempt_marker_v1(value)


def test_review_lock_is_exact_and_rejects_coherently_rehashed_extra() -> None:
    (
        value,
        implementations,
        marker_measurement,
        marker,
        preflight_measurement,
        preflight,
        output,
    ) = _review_lock()
    assert closure.validate_terminal_closure_review_lock_v1(
        value,
        expected_implementation_measurements=implementations,
        expected_preflight_attempt_marker_measurement=marker_measurement,
        expected_preflight_attempt_marker=marker,
        expected_preflight_measurement=preflight_measurement,
        expected_preflight=preflight,
        expected_focused_test_output_measurement=output,
        expected_focused_test_collected=1,
    ) == value
    value["extra"] = False
    value["terminal_closure_review_lock_sha256"] = batch.canonical_sha256(
        {
            key: retained
            for key, retained in value.items()
            if key != "terminal_closure_review_lock_sha256"
        }
    )
    with pytest.raises(closure.T230PlatformReplacementTerminalError):
        closure.validate_terminal_closure_review_lock_v1(
            value,
            expected_implementation_measurements=implementations,
            expected_preflight_attempt_marker_measurement=marker_measurement,
            expected_preflight_attempt_marker=marker,
            expected_preflight_measurement=preflight_measurement,
            expected_preflight=preflight,
            expected_focused_test_output_measurement=output,
            expected_focused_test_collected=1,
        )


@pytest.mark.parametrize(
    ("path", "bad"),
    [
        (("completed_message",), "near miss"),
        (("execution_conditions", 0, "message"), "near miss"),
        (("succeeded_count_present",), True),
        (("cancelled_count_present",), True),
        (("task_last_attempt_result", "exitCode"), 0),
        (("task_last_attempt_result", "status", "code"), 13),
        (("task_completed_condition", "message"), "near miss"),
        (("task_resource_version",), "changed"),
        (("execution_envelope", "max_retries"), 1),
        (("execution_describe_argv", -1), "--format=yaml"),
        (("result_or_effect_content_inspected",), True),
    ],
)
def test_terminal_projection_rejects_exact_surface_drift(
    path: tuple[object, ...], bad: object
) -> None:
    value: object = deepcopy(_terminal())
    cursor = value
    for key in path[:-1]:
        cursor = cursor[key]  # type: ignore[index]
    cursor[path[-1]] = bad  # type: ignore[index]
    with pytest.raises(closure.T230PlatformReplacementTerminalError):
        closure.validate_replacement_failure_projection_v1(value)


def test_surface_census_rejects_late_result_presence_without_opening_body() -> None:
    rows = _rows()
    row = next(item for item in rows if item["uri"] == replacement.RESULT_URI)
    row.update(
        {
            "present": True,
            "generation": "99",
            "size": 100,
            "crc32c": "AAAAAA==",
            "etag": "etag",
            "content_type": "application/json",
        }
    )
    with pytest.raises(closure.T230PlatformReplacementTerminalError):
        closure.build_surface_census_v1(rows=rows, pass_ordinal=1)


def test_lane_a_surface_census_repeats_full_post_terminal_absence_boundary() -> None:
    uris = closure.lane_a_terminal_surface_uris_v1()
    assert replacement.REPLACEMENT_EXECUTION_TERMINAL_URI not in uris
    assert replacement.RESULT_URI in uris
    assert replacement.REPLACEMENT_RUNTIME_MEASUREMENT_URI in uris
    assert replacement.BRIDGE_VERIFIER_STAGE_RECEIPT_URI in uris
    assert replacement.SUPPLEMENTAL_LANE_ROOT_URI in uris
    assert transport.lane_ledger_uri(0) in uris
    assert (
        transport.TRANSPORT_PREFIX + "stages/verify-slate/27.json"
    ) in uris
    first = closure.build_lane_a_surface_census_v1(
        rows=_lane_rows(), pass_ordinal=1
    )
    assert closure.validate_lane_a_surface_census_v1(
        first, pass_ordinal=1
    ) == first
    rows = _lane_rows()
    rows[0].update(
        {
            "present": True,
            "generation": "1",
            "size": 1,
            "crc32c": "AAAAAA==",
            "etag": "etag",
            "content_type": "application/json",
        }
    )
    with pytest.raises(closure.T230PlatformReplacementTerminalError):
        closure.build_lane_a_surface_census_v1(rows=rows, pass_ordinal=2)


def test_preflight_binds_terminal_to_exact_submitted_envelope() -> None:
    lineage = _lineage()
    lineage["replacement_submitted_execution_semantic_sha256"] = "0" * 64
    with pytest.raises(closure.T230PlatformReplacementTerminalError):
        closure.build_terminal_closure_preflight_v1(
            launch_lineage=lineage,
            terminal_projection=_terminal(),
            first_census=closure.build_surface_census_v1(
                rows=_rows(), pass_ordinal=1
            ),
            second_census=closure.build_surface_census_v1(
                rows=_rows(), pass_ordinal=2
            ),
            reviewed_implementation_measurements=(
                closure.terminal_closure_implementation_measurements_v1()
            ),
            preflight_attempt_marker_measurement=_marker_measurement(),
            preflight_attempt_marker=_marker(),
        )


def test_terminal_receipt_replays_and_remains_terminal_invalid() -> None:
    value = _terminal_receipt()
    assert closure.validate_replacement_execution_terminal_v1(value) == value
    assert value["replacement_failed"] is True
    assert value["replacement_exhausted"] is True
    assert value["bridge_verifier_allowed"] is False
    assert value["ordinal_seven_may_resume"] is False
    assert value["current_panel_terminal_invalid"] is True


def test_terminal_receipt_rejects_preflight_measurement_without_newline() -> None:
    preflight = _preflight()
    raw = batch.canonical_json_bytes(preflight)
    with pytest.raises(closure.T230PlatformReplacementTerminalError):
        closure.build_replacement_execution_terminal_v1(
            preflight_measurement={
                "relative_path": closure.PREFLIGHT_RELATIVE_PATH,
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
            preflight=preflight,
            review_lock_measurement={
                "relative_path": closure.REVIEW_LOCK_RELATIVE_PATH,
                "sha256": "f" * 64,
                "bytes": 1234,
            },
            review_lock_sha256="1" * 64,
        )


def test_lane_a_root_is_negative_six_of_twenty_eight() -> None:
    terminal = _terminal_receipt()
    terminal_raw = batch.canonical_json_bytes(terminal)
    terminal_identity = _identity(
        replacement.REPLACEMENT_EXECUTION_TERMINAL_URI,
        terminal_raw,
        "200",
    )
    workers = []
    verifiers = []
    acceptances = []
    for ordinal in range(6):
        worker_raw = f"worker-{ordinal}".encode()
        verifier_raw = f"verifier-{ordinal}".encode()
        acceptance_raw = f"acceptance-{ordinal}".encode()
        workers.append(
            _identity(
                transport.TRANSPORT_PREFIX
                + f"stages/run-slate/{ordinal:02d}.json",
                worker_raw,
                str(300 + ordinal),
            )
        )
        verifiers.append(
            _identity(
                transport.TRANSPORT_PREFIX
                + f"stages/verify-slate/{ordinal:02d}.json",
                verifier_raw,
                str(400 + ordinal),
            )
        )
        acceptances.append(
            _identity(
                transport.OUTPUT_PREFIX
                + f"slates/{ordinal:02d}-fixture/"
                "foundry-t230-slate-acceptance-v1.json",
                acceptance_raw,
                str(500 + ordinal),
            )
        )
    value = closure.build_lane_a_terminal_invalid_root_v1(
        recovery_terminal_identity=terminal_identity,
        recovery_terminal=terminal,
        completed_worker_stage_identities=workers,
        completed_verifier_stage_identities=verifiers,
        completed_acceptance_identities=acceptances,
        first_lane_a_surface_census=closure.build_lane_a_surface_census_v1(
            rows=_lane_rows(), pass_ordinal=1
        ),
        second_lane_a_surface_census=closure.build_lane_a_surface_census_v1(
            rows=_lane_rows(), pass_ordinal=2
        ),
    )
    assert closure.validate_lane_a_terminal_invalid_root_v1(value) == value
    assert value["completed_source_ordinals"] == list(range(6))
    assert value["first_incomplete_source_ordinal"] == 6
    assert value["completed_acceptance_count"] == 6
    assert value["required_acceptance_count"] == 28
    assert value["lane_terminal_invalid"] is True
    assert value["panel_terminal_invalid"] is True
    assert value["panel_release_licensed"] is False


@pytest.mark.parametrize(
    "field",
    [
        "lane_terminal_invalid",
        "panel_terminal_invalid",
        "ordinal_seven_may_resume",
        "historical_scoring_licensed",
    ],
)
def test_lane_a_root_rejects_authority_or_terminal_flip(field: str) -> None:
    # A compact adversary reuses the valid root from the preceding builder.
    terminal = _terminal_receipt()
    terminal_raw = batch.canonical_json_bytes(terminal)
    terminal_identity = _identity(
        replacement.REPLACEMENT_EXECUTION_TERMINAL_URI,
        terminal_raw,
        "200",
    )
    workers = [
        _identity(
            transport.TRANSPORT_PREFIX + f"stages/run-slate/{i:02d}.json",
            f"w{i}".encode(),
            str(10 + i),
        )
        for i in range(6)
    ]
    verifiers = [
        _identity(
            transport.TRANSPORT_PREFIX + f"stages/verify-slate/{i:02d}.json",
            f"v{i}".encode(),
            str(20 + i),
        )
        for i in range(6)
    ]
    acceptances = [
        _identity(
            transport.OUTPUT_PREFIX
            + f"slates/{i:02d}-fixture/foundry-t230-slate-acceptance-v1.json",
            f"a{i}".encode(),
            str(30 + i),
        )
        for i in range(6)
    ]
    value = closure.build_lane_a_terminal_invalid_root_v1(
        recovery_terminal_identity=terminal_identity,
        recovery_terminal=terminal,
        completed_worker_stage_identities=workers,
        completed_verifier_stage_identities=verifiers,
        completed_acceptance_identities=acceptances,
        first_lane_a_surface_census=closure.build_lane_a_surface_census_v1(
            rows=_lane_rows(), pass_ordinal=1
        ),
        second_lane_a_surface_census=closure.build_lane_a_surface_census_v1(
            rows=_lane_rows(), pass_ordinal=2
        ),
    )
    value[field] = not bool(value[field])
    value["lane_a_terminal_invalid_root_sha256"] = batch.canonical_sha256(
        {k: v for k, v in value.items() if k != "lane_a_terminal_invalid_root_sha256"}
    )
    with pytest.raises(closure.T230PlatformReplacementTerminalError):
        closure.validate_lane_a_terminal_invalid_root_v1(value)
