"""Bounded successor for the failed fixed-G0 catalog projection.

The first licensed 54-slate projection is consumed: it failed while exact-
validating the generation-pinned source-completion object's top-level keys,
before any output create.  This module exact-binds that old final lock and the
failure report, reviews the narrow false-valued-field correction, and can
license exactly one corrected projection invocation.  It never opens an
outcome, world-matrix body, or arm-result body.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog


class CorpusR6FixedG0ProjectionSuccessorV1Error(RuntimeError):
    """The successor evidence, lock, or one-rerun boundary differs."""


REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[3]
REVIEW_LOCK_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-projection-successor-review-lock/v1"
)
FINAL_LOCK_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-projection-successor-final-lock/v1"
)
OLD_FINAL_LOCK_COMMIT: Final = "8660373b8d5e027acd6057ce42f03707ebdbded1"
OLD_FINAL_LOCK_PATH: Final = adapter.FIXED_FINAL_RELEASE_LOCK_PATH
OLD_FINAL_LOCK_SHA256: Final = (
    "6f9f0fc3d5672604013d62f82db1f9d4b0078514eeeb0f327be2d0ddbc3e3908"
)
OLD_FINAL_LOCK_BYTES: Final = 6560
OLD_FINAL_LOCK_INTERNAL_SHA256: Final = (
    "de08f1b51d8a71df2fc0acd399f84b869f38367e8641d0d387aceadf434cf744"
)
OLD_FINAL_LOCK_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-final-release-lock/v2"
)
OLD_PROJECTION_COMMAND: Final = (
    ".venv/bin/python",
    "-m",
    "nfl_dfs.research.corpus_r6_player_catalog_fixed_g0_terminal_recovery_v1",
    "publish-projection",
    "--execute",
)
FAILURE_REPORT_PATH: Final = (
    "reports/2026-08-26-r6-fixed-g0-catalog-projection-"
    "source-completion-schema-failure.md"
)
FAILURE_REPORT_SHA256: Final = (
    "9641b731687835edffa75c6c06d413bcc077fc5443bad4251a98639f5375208c"
)
FAILURE_REPORT_BYTES: Final = 4905
FAILED_PROJECTION_CWD: Final = "/tmp/nfl-r6-catalog-projection-8660373b"
FAILED_PROJECTION_EXIT_CODE: Final = 1
FAILED_PROJECTION_EXCEPTION: Final = (
    "CorpusR6FixedG0AdapterV1Error: "
    "fixed artifact-source completion keys differ"
)
OBSERVED_SOURCE_COMPLETION_FIELD: Final = (
    "complete_dk_salary_coverage_claimed"
)
OBSERVED_SOURCE_COMPLETION_VALUE: Final = False
REVIEW_LOCK_PATH: Final = (
    "reports/2026-08-26-r6-player-catalog-fixed-g0-"
    "projection-successor-review-lock.json"
)
FINAL_LOCK_PATH: Final = (
    "reports/2026-08-26-r6-player-catalog-fixed-g0-"
    "projection-successor-final-lock.json"
)
PROJECTION_ATTEMPT_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-projection-successor-attempt/v1"
)
PROJECTION_ATTEMPT_PATH: Final = (
    "reports/2026-08-26-r6-player-catalog-fixed-g0-"
    "projection-successor-attempt.json"
)
FOCUSED_OUTPUT_PATH: Final = (
    "reports/2026-08-26-r6-fixed-g0-projection-successor-"
    "focused-test-output.txt"
)
MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_player_catalog_fixed_g0_projection_successor_v1.py"
)
TEST_PATH: Final = (
    "tests/test_corpus_r6_player_catalog_fixed_g0_projection_successor_v1.py"
)
IMPLEMENTATION_PATHS: Final = (
    *adapter.FIXED_ADAPTER_IMPLEMENTATION_PATHS,
    MODULE_PATH,
    TEST_PATH,
)
FOCUSED_TEST_COMMAND: Final = (
    "/home/erich/projects/nfl-predictions/.venv/bin/python",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "--color=no",
    adapter.FIXED_ADAPTER_TEST_PATH,
    TEST_PATH,
)
FOCUSED_TEST_CWD: Final = "/tmp/nfl-r6-catalog-projection-successor-v1"
FOCUSED_TEST_PYTHONPATH: Final = (
    "/tmp/nfl-r6-catalog-projection-successor-v1/src"
)
EXPECTED_ADAPTER_CASE_COUNT: Final = 124
EXPECTED_SUCCESSOR_CASE_COUNT: Final = 26
EXPECTED_FOCUSED_CASE_COUNT: Final = (
    EXPECTED_ADAPTER_CASE_COUNT + EXPECTED_SUCCESSOR_CASE_COUNT
)
PROJECTION_COMMAND: Final = (
    ".venv/bin/python",
    "-m",
    "nfl_dfs.research.corpus_r6_player_catalog_fixed_g0_projection_successor_v1",
    "publish-projection",
    "--execute",
)
PRODUCTION_ENABLE_ENV: Final = adapter.PRODUCTION_ENABLE_ENV

_FALSE_AUTHORITY_FIELDS: Final = (
    "analytical_authority",
    *catalog.FALSE_AUTHORITY_FIELDS,
    "deployment_authority",
    "selection_authority",
    "uses_realized_outcomes",
)


def _fail(message: str) -> None:
    raise CorpusR6FixedG0ProjectionSuccessorV1Error(message)


def canonical_bytes(value: object) -> bytes:
    return adapter.canonical_json_bytes(value)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _validate_self_hash(
    value: Mapping[str, Any], *, field: str, label: str,
) -> str:
    retained = value.get(field)
    if type(retained) is not str or re.fullmatch(r"[0-9a-f]{64}", retained) is None:
        _fail(f"{label} self-hash differs")
    body = dict(value)
    body.pop(field, None)
    if canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _binding(path: str, raw: bytes) -> dict[str, Any]:
    return {
        "relative_path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _read_exact(
    repository: adapter.SubprocessGitRepositoryV1,
    *,
    commit: str,
    path: str,
    sha256: str,
    size: int,
    label: str,
) -> bytes:
    try:
        raw = repository.read_tracked(commit, path)
    except Exception as exc:
        raise CorpusR6FixedG0ProjectionSuccessorV1Error(
            f"{label} tracked read failed"
        ) from exc
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != sha256:
        _fail(f"{label} file binding differs")
    return raw


def _parse_json(raw: bytes, *, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw.endswith(b"\n"):
        _fail(f"{label} bytes differ")
    body = raw[:-1]
    try:
        value = json.loads(body)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusR6FixedG0ProjectionSuccessorV1Error(
            f"{label} is not JSON"
        ) from exc
    item = _mapping(value, label=label)
    if canonical_bytes(item) != body:
        _fail(f"{label} is not canonical JSON")
    return item


def _normalize_file_binding(value: object, *, label: str) -> dict[str, Any]:
    item = _mapping(value, label=label)
    if set(item) != {"relative_path", "sha256", "bytes"}:
        _fail(f"{label} keys differ")
    path = item["relative_path"]
    digest = item["sha256"]
    size = item["bytes"]
    if (
        type(path) is not str
        or not path
        or Path(path).is_absolute()
        or any(part in {"", ".", ".."} for part in Path(path).parts)
        or type(digest) is not str
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        or type(size) is not int
        or size < 1
    ):
        _fail(f"{label} differs")
    return {"relative_path": path, "sha256": digest, "bytes": size}


def _normalize_measurements(value: object) -> list[dict[str, Any]]:
    rows = [
        _normalize_file_binding(row, label=f"successor implementation[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(value, label="successor implementation measurements")
        )
    ]
    if [row["relative_path"] for row in rows] != list(IMPLEMENTATION_PATHS):
        _fail("successor implementation paths differ")
    return rows


def _measure_current(
    repository: adapter.SubprocessGitRepositoryV1, head: str,
) -> list[dict[str, Any]]:
    return [
        _binding(path, repository.read_tracked(head, path))
        for path in IMPLEMENTATION_PATHS
    ]


def _validate_old_final_lock(value: object) -> dict[str, Any]:
    item = _mapping(value, label="old terminal-recovery final lock")
    retained = _validate_self_hash(
        item,
        field="final_release_lock_sha256",
        label="old terminal-recovery final lock",
    )
    if (
        retained != OLD_FINAL_LOCK_INTERNAL_SHA256
        or item.get("schema_version") != OLD_FINAL_LOCK_SCHEMA
        or item.get("evidence_source_commit_sha")
        != adapter.FIXED_SOURCE_COMMIT_SHA
        or item.get("adapter_attempt_count") != 2
        or item.get("adapter_v1_smoke_passed") is not False
        or item.get("adapter_v2_smoke_passed") is not False
        or item.get("adapter_success_receipt_absent") is not True
        or item.get("prior_real_artifact_smoke_passed") is not True
        or item.get("third_adapter_smoke_allowed") is not False
        or item.get("current_clean_git_required") is not True
        or item.get("required_source_task_count") != catalog.TASK_COUNT
        or item.get("required_task_acceptance_body_reopen_count")
        != catalog.TASK_COUNT
        or item.get("required_carrier_body_reopen_count") != catalog.TASK_COUNT
        or item.get("all_inputs_derived_before_first_output") is not True
        or item.get("projection_only_publication_reviewed") is not True
        or item.get("projection_only_publication_licensed") is not True
        or item.get("projection_release_command") != list(OLD_PROJECTION_COMMAND)
        or item.get("gcs_create_once_required") is not True
        or item.get("gcs_overwrite_licensed") is not False
        or item.get("world_matrix_bodies_read") is not False
        or item.get("result_object_bodies_read") is not False
        or item.get("outcome_columns_read") != []
        or any(item.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("old terminal-recovery final-lock semantics differ")
    return item


def _adapter_review_from_old_final(
    old_final: Mapping[str, Any],
) -> adapter.AdapterReviewBindingV1:
    binding = _mapping(
        old_final.get("base_adapter_review_binding"),
        label="old final base adapter review binding",
    )
    expected = {
        "review_lock_commit_sha",
        "implementation_commit_sha",
        "review_lock_relative_path",
        "review_lock_file_sha256",
        "review_lock_file_bytes",
        "review_lock_internal_sha256",
        "implementation_measurements",
    }
    if set(binding) != expected:
        _fail("old final base adapter review binding keys differ")
    try:
        return adapter.AdapterReviewBindingV1(**binding)
    except TypeError as exc:
        raise CorpusR6FixedG0ProjectionSuccessorV1Error(
            "old final base adapter review binding differs"
        ) from exc


def validate_successor_evidence_v1(
    *, repository: adapter.SubprocessGitRepositoryV1, head: str,
) -> dict[str, Any]:
    """Exact-reopen old authority and the correction report, without cloud."""
    old_raw = _read_exact(
        repository,
        commit=OLD_FINAL_LOCK_COMMIT,
        path=OLD_FINAL_LOCK_PATH,
        sha256=OLD_FINAL_LOCK_SHA256,
        size=OLD_FINAL_LOCK_BYTES,
        label="old terminal-recovery final lock",
    )
    current_old_raw = _read_exact(
        repository,
        commit=head,
        path=OLD_FINAL_LOCK_PATH,
        sha256=OLD_FINAL_LOCK_SHA256,
        size=OLD_FINAL_LOCK_BYTES,
        label="current preserved old final lock",
    )
    if current_old_raw != old_raw:
        _fail("current old final lock bytes differ")
    old_final = _validate_old_final_lock(
        _parse_json(old_raw, label="old terminal-recovery final lock")
    )
    report_raw = _read_exact(
        repository,
        commit=head,
        path=FAILURE_REPORT_PATH,
        sha256=FAILURE_REPORT_SHA256,
        size=FAILURE_REPORT_BYTES,
        label="projection failure report",
    )
    return {
        "old_final_lock_commit_sha": OLD_FINAL_LOCK_COMMIT,
        "old_final_lock_file": _binding(OLD_FINAL_LOCK_PATH, old_raw),
        "old_final_lock_internal_sha256": old_final[
            "final_release_lock_sha256"
        ],
        "base_adapter_review_binding": old_final[
            "base_adapter_review_binding"
        ],
        "prior_real_artifact_smoke_file": old_final[
            "prior_real_artifact_smoke_file"
        ],
        "prior_real_artifact_smoke_internal_sha256": old_final[
            "prior_real_artifact_smoke_internal_sha256"
        ],
        "projection_failure_report_file": _binding(
            FAILURE_REPORT_PATH, report_raw
        ),
        "failed_projection_command": list(OLD_PROJECTION_COMMAND),
        "failed_projection_cwd": FAILED_PROJECTION_CWD,
        "failed_projection_clean_commit_sha": OLD_FINAL_LOCK_COMMIT,
        "failed_projection_exit_code": FAILED_PROJECTION_EXIT_CODE,
        "failed_projection_exception": FAILED_PROJECTION_EXCEPTION,
        "failed_projection_source_completion_identity": dict(
            adapter.FIXED_SOURCE_COMPLETION_IDENTITY
        ),
        "observed_source_completion_field": OBSERVED_SOURCE_COMPLETION_FIELD,
        "observed_source_completion_value": OBSERVED_SOURCE_COMPLETION_VALUE,
        "source_task_zero_keys_matched": True,
        "source_task_fifty_three_keys_matched": True,
        "first_projection_output_create_count": 0,
        "first_projection_failed_before_output_create_phase": True,
        "adapter_attempt_count": 2,
        "adapter_v1_smoke_passed": False,
        "adapter_v2_smoke_passed": False,
        "adapter_success_receipt_absent": True,
        "prior_real_artifact_smoke_passed": True,
        "third_adapter_smoke_allowed": False,
    }


def _focused_output(raw: bytes) -> dict[str, int]:
    if type(raw) is not bytes:
        _fail("focused output must be exact bytes")
    try:
        raw.decode("ascii")
    except UnicodeError as exc:
        raise CorpusR6FixedG0ProjectionSuccessorV1Error(
            "focused output is not ASCII"
        ) from exc
    if not raw.endswith(b"\n"):
        _fail("focused output must end with one complete line")
    lines = raw[:-1].split(b"\n")
    if len(lines) < 2 or any(line == b"" for line in lines):
        _fail("focused output must contain progress and one summary")
    completed = 0
    prior_percentage = -1
    for line in lines[:-1]:
        match = re.fullmatch(
            rb"(\.+)( +)\[([ ]{0,2})([1-9][0-9]?|100)%\]", line
        )
        if match is None:
            _fail("focused output progress differs")
        completed += len(match.group(1))
        if len(match.group(3)) + len(match.group(4)) != 3:
            _fail("focused output percentage width differs")
        percentage = int(match.group(4))
        if (
            completed > EXPECTED_FOCUSED_CASE_COUNT
            or percentage != completed * 100 // EXPECTED_FOCUSED_CASE_COUNT
            or percentage <= prior_percentage
        ):
            _fail("focused output progress accounting differs")
        prior_percentage = percentage
    summary = lines[-1]
    pattern = (
        str(EXPECTED_FOCUSED_CASE_COUNT).encode("ascii")
        + rb" passed in (?:0|[1-9][0-9]*)\.[0-9]{2}s"
    )
    if (
        completed != EXPECTED_FOCUSED_CASE_COUNT
        or prior_percentage != 100
        or re.fullmatch(pattern, summary) is None
    ):
        _fail("focused output pass accounting differs")
    return {"passed_test_count": EXPECTED_FOCUSED_CASE_COUNT, "exit_code": 0}


def _build_review_lock(
    *,
    implementation_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, Any],
    focused_output_file: Mapping[str, Any],
    focused_pass_count: int,
    independent_static_review_passed: bool,
) -> dict[str, Any]:
    if (
        re.fullmatch(r"[0-9a-f]{40}", implementation_commit_sha) is None
        or independent_static_review_passed is not True
        or focused_pass_count != EXPECTED_FOCUSED_CASE_COUNT
    ):
        _fail("successor review approval differs")
    measurements = _normalize_measurements(implementation_measurements)
    focused = _normalize_file_binding(
        focused_output_file, label="successor focused output"
    )
    body: dict[str, Any] = {
        "schema_version": REVIEW_LOCK_SCHEMA,
        "implementation_commit_sha": implementation_commit_sha,
        "implementation_measurements": measurements,
        **dict(evidence),
        "focused_test_command": list(FOCUSED_TEST_COMMAND),
        "focused_test_cwd": FOCUSED_TEST_CWD,
        "focused_test_pythonpath": FOCUSED_TEST_PYTHONPATH,
        "focused_test_output_file": focused,
        "focused_test_invocation_count": 1,
        "focused_test_passed_count": EXPECTED_FOCUSED_CASE_COUNT,
        "expected_adapter_case_count": EXPECTED_ADAPTER_CASE_COUNT,
        "expected_successor_case_count": EXPECTED_SUCCESSOR_CASE_COUNT,
        "independent_static_review_passed": True,
        "p0_open_count": 0,
        "p1_open_count": 0,
        "p2_open_count": 0,
        "projection_attempt_count": 1,
        "first_projection_passed": False,
        "corrected_projection_rerun_licensed": False,
        "third_projection_attempt_licensed": False,
        "projection_publication_licensed": False,
        "gcs_mutation_licensed": False,
        "world_matrix_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["projection_successor_review_lock_sha256"] = canonical_sha256(body)
    return body


def validate_review_lock_v1(
    value: object,
    *,
    implementation_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, Any],
    focused_output_file: Mapping[str, Any],
    focused_pass_count: int,
) -> dict[str, Any]:
    item = _mapping(value, label="projection successor review lock")
    retained = _validate_self_hash(
        item,
        field="projection_successor_review_lock_sha256",
        label="projection successor review lock",
    )
    expected = _build_review_lock(
        implementation_commit_sha=implementation_commit_sha,
        implementation_measurements=implementation_measurements,
        evidence=evidence,
        focused_output_file=focused_output_file,
        focused_pass_count=focused_pass_count,
        independent_static_review_passed=True,
    )
    if canonical_bytes(item) != canonical_bytes(expected):
        _fail("projection successor review lock differs")
    item["projection_successor_review_lock_sha256"] = retained
    return item


def _build_final_lock(
    *, review_lock_file: Mapping[str, Any], review_lock: Mapping[str, Any],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": FINAL_LOCK_SCHEMA,
        "evidence_source_commit_sha": adapter.FIXED_SOURCE_COMMIT_SHA,
        "implementation_commit_sha": review_lock["implementation_commit_sha"],
        "implementation_measurements": review_lock[
            "implementation_measurements"
        ],
        "projection_successor_review_lock_file": _normalize_file_binding(
            review_lock_file, label="projection successor review-lock file"
        ),
        "projection_successor_review_lock_internal_sha256": review_lock[
            "projection_successor_review_lock_sha256"
        ],
        "old_final_lock_commit_sha": review_lock[
            "old_final_lock_commit_sha"
        ],
        "old_final_lock_file": review_lock["old_final_lock_file"],
        "old_final_lock_internal_sha256": review_lock[
            "old_final_lock_internal_sha256"
        ],
        "base_adapter_review_binding": review_lock[
            "base_adapter_review_binding"
        ],
        "projection_failure_report_file": review_lock[
            "projection_failure_report_file"
        ],
        "failed_projection_command": review_lock[
            "failed_projection_command"
        ],
        "failed_projection_cwd": review_lock["failed_projection_cwd"],
        "failed_projection_clean_commit_sha": review_lock[
            "failed_projection_clean_commit_sha"
        ],
        "failed_projection_exit_code": review_lock[
            "failed_projection_exit_code"
        ],
        "failed_projection_exception": review_lock[
            "failed_projection_exception"
        ],
        "failed_projection_source_completion_identity": review_lock[
            "failed_projection_source_completion_identity"
        ],
        "observed_source_completion_field": review_lock[
            "observed_source_completion_field"
        ],
        "observed_source_completion_value": review_lock[
            "observed_source_completion_value"
        ],
        "source_task_zero_keys_matched": True,
        "source_task_fifty_three_keys_matched": True,
        "first_projection_output_create_count": 0,
        "first_projection_failed_before_output_create_phase": True,
        "adapter_attempt_count": 2,
        "adapter_v1_smoke_passed": False,
        "adapter_v2_smoke_passed": False,
        "adapter_success_receipt_absent": True,
        "prior_real_artifact_smoke_file": review_lock[
            "prior_real_artifact_smoke_file"
        ],
        "prior_real_artifact_smoke_internal_sha256": review_lock[
            "prior_real_artifact_smoke_internal_sha256"
        ],
        "prior_real_artifact_smoke_passed": True,
        "third_adapter_smoke_allowed": False,
        "focused_test_command": list(FOCUSED_TEST_COMMAND),
        "focused_test_cwd": FOCUSED_TEST_CWD,
        "focused_test_pythonpath": FOCUSED_TEST_PYTHONPATH,
        "focused_test_output_file": review_lock["focused_test_output_file"],
        "focused_test_invocation_count": 1,
        "focused_test_passed_count": EXPECTED_FOCUSED_CASE_COUNT,
        "independent_static_review_passed": True,
        "p0_open_count": 0,
        "p1_open_count": 0,
        "p2_open_count": 0,
        "current_clean_git_required": True,
        "projection_attempt_count_before_successor": 1,
        "first_projection_passed": False,
        "maximum_projection_attempt_count": 2,
        "corrected_projection_rerun_licensed": True,
        "third_projection_attempt_licensed": False,
        "projection_attempt_marker_schema": PROJECTION_ATTEMPT_SCHEMA,
        "projection_attempt_marker_relative_path": PROJECTION_ATTEMPT_PATH,
        "projection_attempt_marker_create_once_before_client": True,
        "required_source_task_count": catalog.TASK_COUNT,
        "required_task_acceptance_body_reopen_count": catalog.TASK_COUNT,
        "required_carrier_body_reopen_count": catalog.TASK_COUNT,
        "all_inputs_derived_before_first_output": True,
        "generation_pinned_input_reads_required": True,
        "projection_only_publication_reviewed": True,
        "projection_only_publication_licensed": True,
        "projection_release_command": list(PROJECTION_COMMAND),
        "production_enable_environment_variable": PRODUCTION_ENABLE_ENV,
        "production_enable_environment_value": "1",
        "gcs_create_once_required": True,
        "gcs_exact_reopen_required": True,
        "gcs_overwrite_licensed": False,
        "world_matrix_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["projection_successor_final_lock_sha256"] = canonical_sha256(body)
    return body


def validate_final_lock_v1(
    value: object,
    *, review_lock_file: Mapping[str, Any], review_lock: Mapping[str, Any],
) -> dict[str, Any]:
    item = _mapping(value, label="projection successor final lock")
    retained = _validate_self_hash(
        item,
        field="projection_successor_final_lock_sha256",
        label="projection successor final lock",
    )
    expected = _build_final_lock(
        review_lock_file=review_lock_file, review_lock=review_lock
    )
    if canonical_bytes(item) != canonical_bytes(expected):
        _fail("projection successor final lock differs")
    item["projection_successor_final_lock_sha256"] = retained
    return item


def _build_projection_attempt_v1(
    *,
    current_clean_commit_sha: str,
    final_lock_file: Mapping[str, Any],
    final_lock: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the durable reservation that consumes projection attempt two."""
    if re.fullmatch(r"[0-9a-f]{40}", current_clean_commit_sha) is None:
        _fail("projection attempt current-clean commit differs")
    final = _mapping(final_lock, label="projection successor final lock")
    retained_final_hash = _validate_self_hash(
        final,
        field="projection_successor_final_lock_sha256",
        label="projection successor final lock",
    )
    final_file = _normalize_file_binding(
        final_lock_file, label="projection successor final-lock file"
    )
    measurements = _normalize_measurements(final.get("implementation_measurements"))
    successor_measurements = [
        measurement
        for measurement in measurements
        if measurement["relative_path"] == MODULE_PATH
    ]
    if (
        final_file["relative_path"] != FINAL_LOCK_PATH
        or final.get("schema_version") != FINAL_LOCK_SCHEMA
        or final.get("projection_successor_final_lock_sha256")
        != retained_final_hash
        or final.get("projection_attempt_count_before_successor") != 1
        or final.get("maximum_projection_attempt_count") != 2
        or final.get("corrected_projection_rerun_licensed") is not True
        or final.get("third_projection_attempt_licensed") is not False
        or final.get("projection_attempt_marker_schema")
        != PROJECTION_ATTEMPT_SCHEMA
        or final.get("projection_attempt_marker_relative_path")
        != PROJECTION_ATTEMPT_PATH
        or final.get("projection_attempt_marker_create_once_before_client")
        is not True
        or final.get("projection_release_command") != list(PROJECTION_COMMAND)
        or re.fullmatch(
            r"[0-9a-f]{40}", str(final.get("implementation_commit_sha"))
        )
        is None
        or len(successor_measurements) != 1
    ):
        _fail("projection successor final-lock attempt semantics differ")
    body: dict[str, Any] = {
        "schema_version": PROJECTION_ATTEMPT_SCHEMA,
        "attempt_id": "fixed-g0-catalog-projection-successor-attempt-2",
        "attempt_relative_path": PROJECTION_ATTEMPT_PATH,
        "command": list(PROJECTION_COMMAND),
        "projection_attempt_ordinal": 2,
        "projection_attempt_count_before_reservation": 1,
        "lifetime_projection_attempt_count_after_reservation": 2,
        "maximum_projection_attempt_count": 2,
        "projection_successor_final_lock_file": final_file,
        "projection_successor_final_lock_internal_sha256": retained_final_hash,
        "projection_successor_final_lock_schema": FINAL_LOCK_SCHEMA,
        "reviewed_implementation_commit_sha": final[
            "implementation_commit_sha"
        ],
        "current_clean_commit_sha": current_clean_commit_sha,
        "current_source_identity": {
            "commit_sha": current_clean_commit_sha,
            "successor_module_file": successor_measurements[0],
        },
        "implementation_measurements": measurements,
        "state": "attempt-2-reserved-after-final-lock-before-cloud-client",
        "final_lock_reopened_before_reservation": True,
        "current_implementation_reopened_before_reservation": True,
        "reserved_before_cloud_client_construction": True,
        "local_attempt_marker_create_count": 1,
        "corrected_projection_rerun_reserved": True,
        "corrected_projection_rerun_license_consumed": True,
        "corrected_projection_rerun_licensed": False,
        "additional_projection_attempt_licensed": False,
        "third_projection_attempt_licensed": False,
        "cloud_client_constructed": False,
        "cloud_contact_performed": False,
        "gcs_read_count": 0,
        "gcs_mutation_count": 0,
        "gcs_overwrite_licensed": False,
        "request_authoritative_publication": False,
        "outcome_columns_read": [],
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["projection_successor_attempt_sha256"] = canonical_sha256(body)
    return body


def validate_projection_attempt_v1(
    value: object,
    *,
    current_clean_commit_sha: str,
    final_lock_file: Mapping[str, Any],
    final_lock: Mapping[str, Any],
) -> dict[str, Any]:
    item = _mapping(value, label="projection successor attempt")
    retained = _validate_self_hash(
        item,
        field="projection_successor_attempt_sha256",
        label="projection successor attempt",
    )
    expected = _build_projection_attempt_v1(
        current_clean_commit_sha=current_clean_commit_sha,
        final_lock_file=final_lock_file,
        final_lock=final_lock,
    )
    if canonical_bytes(item) != canonical_bytes(expected):
        _fail("projection successor attempt differs")
    item["projection_successor_attempt_sha256"] = retained
    return item


def _safe_output_path(relative_path: str, *, label: str) -> Path:
    relative = Path(relative_path)
    root = REPOSITORY_ROOT
    if (
        not root.is_absolute()
        or root.is_symlink()
        or not root.is_dir()
        or relative.is_absolute()
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        _fail(f"{label} path differs")
    parent = root
    for part in relative.parts[:-1]:
        parent /= part
        if parent.is_symlink() or not parent.is_dir():
            _fail(f"{label} parent is unsafe")
    path = parent / relative.parts[-1]
    if path.is_symlink() or path.exists():
        _fail(f"{label} already exists")
    return path


def _write_once(path: Path, value: Mapping[str, Any], *, label: str) -> None:
    raw = canonical_bytes(dict(value)) + b"\n"
    directory_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        directory_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        directory_flags |= os.O_CLOEXEC
    write_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    read_flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        write_flags |= os.O_NOFOLLOW
        read_flags |= os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        write_flags |= os.O_CLOEXEC
        read_flags |= os.O_CLOEXEC
    directory_fd: int | None = None
    write_fd: int | None = None
    reopen_fd: int | None = None
    try:
        directory_fd = os.open(path.parent, directory_flags)
        write_fd = os.open(path.name, write_flags, 0o600, dir_fd=directory_fd)
        written = 0
        while written < len(raw):
            count = os.write(write_fd, raw[written:])
            if count < 1:
                _fail(f"{label} write made no progress")
            written += count
        os.fsync(write_fd)
        written_stat = os.fstat(write_fd)
        retained_write_fd = write_fd
        write_fd = None
        os.close(retained_write_fd)
        reopen_fd = os.open(path.name, read_flags, dir_fd=directory_fd)
        reopened_stat = os.fstat(reopen_fd)
        if (
            not stat.S_ISREG(reopened_stat.st_mode)
            or stat.S_IMODE(reopened_stat.st_mode) != 0o600
            or (reopened_stat.st_dev, reopened_stat.st_ino)
            != (written_stat.st_dev, written_stat.st_ino)
        ):
            _fail(f"{label} secure reopen differs")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(reopen_fd, 65_536)
            if not chunk:
                break
            chunks.append(chunk)
        if b"".join(chunks) != raw:
            _fail(f"{label} reopened bytes differ")
        retained_reopen_fd = reopen_fd
        reopen_fd = None
        os.close(retained_reopen_fd)
        os.fsync(directory_fd)
    except FileExistsError as exc:
        raise CorpusR6FixedG0ProjectionSuccessorV1Error(
            f"{label} create-once failed"
        ) from exc
    except OSError as exc:
        raise CorpusR6FixedG0ProjectionSuccessorV1Error(
            f"{label} secure write failed"
        ) from exc
    finally:
        if reopen_fd is not None:
            os.close(reopen_fd)
        if write_fd is not None:
            os.close(write_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def _reserve_projection_attempt_v1(
    *,
    current_clean_commit_sha: str,
    final_lock_file: Mapping[str, Any],
    final_lock: Mapping[str, Any],
) -> dict[str, Any]:
    attempt = _build_projection_attempt_v1(
        current_clean_commit_sha=current_clean_commit_sha,
        final_lock_file=final_lock_file,
        final_lock=final_lock,
    )
    output = _safe_output_path(
        PROJECTION_ATTEMPT_PATH, label="projection successor attempt"
    )
    _write_once(output, attempt, label="projection successor attempt")
    return validate_projection_attempt_v1(
        attempt,
        current_clean_commit_sha=current_clean_commit_sha,
        final_lock_file=final_lock_file,
        final_lock=final_lock,
    )


def build_review_lock_production_v1(
    *, output_relative_path: str, independent_static_review_passed: bool,
) -> dict[str, Any]:
    if output_relative_path != REVIEW_LOCK_PATH:
        _fail("projection successor review-lock output differs")
    output = _safe_output_path(REVIEW_LOCK_PATH, label="successor review lock")
    repository = adapter.SubprocessGitRepositoryV1()
    head = repository.require_current_clean_head()
    measurements = _measure_current(repository, head)
    evidence = validate_successor_evidence_v1(repository=repository, head=head)
    focused_raw = repository.read_tracked(head, FOCUSED_OUTPUT_PATH)
    focused = _focused_output(focused_raw)
    lock = _build_review_lock(
        implementation_commit_sha=head,
        implementation_measurements=measurements,
        evidence=evidence,
        focused_output_file=_binding(FOCUSED_OUTPUT_PATH, focused_raw),
        focused_pass_count=focused["passed_test_count"],
        independent_static_review_passed=independent_static_review_passed,
    )
    _write_once(output, lock, label="successor review lock")
    return lock


def _resolve_review_lock(
    *, repository: adapter.SubprocessGitRepositoryV1, head: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    raw = repository.read_tracked(head, REVIEW_LOCK_PATH)
    value = _parse_json(raw, label="tracked projection successor review lock")
    implementation_commit = str(value.get("implementation_commit_sha"))
    measurements = _normalize_measurements(
        value.get("implementation_measurements")
    )
    for ordinal, measurement in enumerate(measurements):
        for commit, state in ((implementation_commit, "reviewed"), (head, "current")):
            _read_exact(
                repository,
                commit=commit,
                path=measurement["relative_path"],
                sha256=measurement["sha256"],
                size=measurement["bytes"],
                label=f"{state} successor implementation[{ordinal}]",
            )
    evidence = validate_successor_evidence_v1(repository=repository, head=head)
    focused_raw = repository.read_tracked(head, FOCUSED_OUTPUT_PATH)
    focused = _focused_output(focused_raw)
    lock = validate_review_lock_v1(
        value,
        implementation_commit_sha=implementation_commit,
        implementation_measurements=measurements,
        evidence=evidence,
        focused_output_file=_binding(FOCUSED_OUTPUT_PATH, focused_raw),
        focused_pass_count=focused["passed_test_count"],
    )
    return lock, _binding(REVIEW_LOCK_PATH, raw), evidence


def build_final_lock_production_v1(
    *, output_relative_path: str, publication_approved: bool,
) -> dict[str, Any]:
    if output_relative_path != FINAL_LOCK_PATH or publication_approved is not True:
        _fail("projection successor final approval/output differs")
    output = _safe_output_path(FINAL_LOCK_PATH, label="successor final lock")
    repository = adapter.SubprocessGitRepositoryV1()
    head = repository.require_current_clean_head()
    review, review_file, _ = _resolve_review_lock(repository=repository, head=head)
    lock = _build_final_lock(review_lock_file=review_file, review_lock=review)
    _write_once(output, lock, label="successor final lock")
    return lock


def _resolve_final_lock(
    *, repository: adapter.SubprocessGitRepositoryV1,
) -> tuple[
    str,
    adapter.AdapterReviewBindingV1,
    dict[str, Any],
    dict[str, Any],
]:
    head = repository.require_current_clean_head()
    review, review_file, evidence = _resolve_review_lock(
        repository=repository, head=head
    )
    raw = repository.read_tracked(head, FINAL_LOCK_PATH)
    final = validate_final_lock_v1(
        _parse_json(raw, label="tracked projection successor final lock"),
        review_lock_file=review_file,
        review_lock=review,
    )
    old_final_raw = _read_exact(
        repository,
        commit=OLD_FINAL_LOCK_COMMIT,
        path=OLD_FINAL_LOCK_PATH,
        sha256=OLD_FINAL_LOCK_SHA256,
        size=OLD_FINAL_LOCK_BYTES,
        label="old final lock for adapter review",
    )
    old_final = _validate_old_final_lock(
        _parse_json(old_final_raw, label="old final lock for adapter review")
    )
    if old_final["base_adapter_review_binding"] != evidence[
        "base_adapter_review_binding"
    ]:
        _fail("successor/base adapter review binding differs")
    base_review = _adapter_review_from_old_final(old_final)
    adapter._reopen_adapter_review_binding_v1(
        review=base_review, read_tracked=repository.read_tracked
    )
    return head, base_review, final, _binding(FINAL_LOCK_PATH, raw)


def publish_projection_production_v1() -> dict[str, Any]:
    """Resolve the new clean-head lock before constructing a cloud client."""
    if os.environ.get(PRODUCTION_ENABLE_ENV) != "1":
        _fail("projection successor is parked")
    repository = adapter.SubprocessGitRepositoryV1()
    head, base_review, final, final_file = _resolve_final_lock(
        repository=repository
    )
    _reserve_projection_attempt_v1(
        current_clean_commit_sha=head,
        final_lock_file=final_file,
        final_lock=final,
    )
    backend = adapter.GCSGenerationBackendV1.from_default_client()
    return adapter._publish_pinned_projection_release_v1(
        pins=adapter.FIXED_PINS,
        adapter_review=base_review,
        read_tracked=repository.read_tracked,
        transport=backend.transport(),
        request_authoritative_publication=False,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bounded successor for fixed-G0 catalog projection"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    review = subparsers.add_parser("build-review-lock")
    review.add_argument("--output", required=True)
    review.add_argument("--static-review-approved", action="store_true", required=True)
    review.add_argument("--build", action="store_true", required=True)
    final = subparsers.add_parser("build-final-lock")
    final.add_argument("--output", required=True)
    final.add_argument("--publication-approved", action="store_true", required=True)
    final.add_argument("--build", action="store_true", required=True)
    publish = subparsers.add_parser("publish-projection")
    publish.add_argument("--execute", action="store_true", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "status":
        print(canonical_bytes({
            "adapter_attempt_count": 2,
            "corrected_projection_rerun_licensed": False,
            "default_state": "parked",
            "first_projection_output_create_count": 0,
            "first_projection_passed": False,
            "projection_attempt_count": 1,
            "projection_attempt_marker_path": PROJECTION_ATTEMPT_PATH,
            "projection_command": list(PROJECTION_COMMAND),
            "successor_final_lock_path": FINAL_LOCK_PATH,
            "successor_review_lock_path": REVIEW_LOCK_PATH,
            "third_adapter_smoke_allowed": False,
            "third_projection_attempt_licensed": False,
            "uses_realized_outcomes": False,
        }).decode("ascii"))
        return 0
    if args.command == "build-review-lock":
        result = build_review_lock_production_v1(
            output_relative_path=args.output,
            independent_static_review_passed=args.static_review_approved,
        )
    elif args.command == "build-final-lock":
        result = build_final_lock_production_v1(
            output_relative_path=args.output,
            publication_approved=args.publication_approved,
        )
    elif args.command == "publish-projection" and args.execute is True:
        result = publish_projection_production_v1()
    else:
        _fail("explicit projection successor gate absent")
    print(canonical_bytes(result).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
