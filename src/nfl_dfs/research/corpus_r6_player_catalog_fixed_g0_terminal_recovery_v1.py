"""Truthful terminal recovery for the fixed-G0 R6 catalog projection.

Both adapter-local task-0 attempts are consumed and failed before their first
GCS object read.  This module never retries either smoke.  It binds the prior
successful production one-slate real-artifact smoke, the corrected adapter
bytes, and two local review locks before it exposes the existing 54-slate
generation-pinned projection materializer.
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


class CorpusR6FixedG0TerminalRecoveryV1Error(RuntimeError):
    """The terminal recovery evidence or execution boundary differs."""


REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[3]
REVIEW_LOCK_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-terminal-recovery-review-lock/v1"
)
FINAL_LOCK_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-final-release-lock/v2"
)
AMENDMENT_PATH: Final = (
    "reports/2026-08-26-r6-fixed-g0-terminal-smoke-recovery-amendment.md"
)
AMENDMENT_SHA256: Final = (
    "6a6f6aa924f7f751132b13694483f74b1c5622eeea75677c41acf341b6fda242"
)
AMENDMENT_BYTES: Final = 5933
V2_FAILURE_PATH: Final = (
    "reports/2026-08-26-r6-fixed-g0-v2-smoke-publication-schema-failure.md"
)
V2_FAILURE_SHA256: Final = (
    "a06d986650049b0052e9e37793c3565dd7123420136a91d479b564901b99cda1"
)
V2_FAILURE_BYTES: Final = 3005
V1_ATTEMPT_PATH: Final = adapter.FIXED_TASK0_SMOKE_ATTEMPT_PATH
V1_ATTEMPT_SHA256: Final = (
    "35d2a32334f7b06074a8f37245042881f4dd100796e3093b1e09639a6d81ae48"
)
V1_ATTEMPT_BYTES: Final = 3278
V1_ATTEMPT_INTERNAL_SHA256: Final = (
    "2e3adc38313f2811cf7d245e77d7838915cb9602cc416e3c581e20d029d57eff"
)
V2_ATTEMPT_PATH: Final = adapter.FIXED_TASK0_SMOKE_ATTEMPT_V2_PATH
V2_ATTEMPT_SHA256: Final = (
    "36e28956944cf3d9ed68152d773f381838c3385965d0bb47bfca0f068deaa6c5"
)
V2_ATTEMPT_BYTES: Final = 3904
V2_ATTEMPT_INTERNAL_SHA256: Final = (
    "8a2d364c711c047a6704c9e441cea7b9275671bad224428575c62b1ccbfa1115"
)
RECOVERY_LOCK_PATH: Final = adapter.FIXED_TASK0_SMOKE_RECOVERY_REVIEW_LOCK_PATH
RECOVERY_LOCK_SHA256: Final = (
    "71e4dfee04ffcc9898009b051f8dc7cd1db9fcd4e9f4be61f852b8ace1910341"
)
RECOVERY_LOCK_BYTES: Final = 4026
RECOVERY_LOCK_INTERNAL_SHA256: Final = (
    "c3ce327b6d3ce484294b7d04014a3077f922c605997be299800ac5759e3c80a6"
)
PRIOR_SMOKE_RESULT_PATH: Final = (
    "reports/corpus-parametric-runs/"
    "20260823-foundry-production-v12-panel-index/panel-index-live/"
    "extreme-tail-smoke-2023-w01/result.json"
)
PRIOR_SMOKE_RESULT_SHA256: Final = (
    "73464ee66c358dbedf30d34b6348e049e5e218a28f542428053a0d6e6674ac99"
)
PRIOR_SMOKE_RESULT_BYTES: Final = 386371
PRIOR_SMOKE_INTERNAL_SHA256: Final = (
    "ceddab226e3ff66e5668e227d144c1431cb889da95e90570d9b7619d35fd346e"
)
PRIOR_SMOKE_TIME_PATH: Final = (
    "reports/corpus-parametric-runs/"
    "20260823-foundry-production-v12-panel-index/panel-index-live/"
    "extreme-tail-smoke-2023-w01/time-v.txt"
)
PRIOR_SMOKE_TIME_SHA256: Final = (
    "89261ccb4fe08d7ae137c07f45979e49e1fd48a136e7042840f496b61da0e3cc"
)
PRIOR_SMOKE_TIME_BYTES: Final = 1251
OFFICIAL_RECEIPT_PATH: Final = (
    "reports/corpus-parametric-runs/"
    "20260823-foundry-production-v12-panel-index/panel-index-live/published.json"
)
OFFICIAL_RECEIPT_SHA256: Final = (
    "70dfc8e9773958272d10d9dc58d9300556f401bfe08c1e352e36746cd23ed2e5"
)
OFFICIAL_RECEIPT_BYTES: Final = 1370
OFFICIAL_RECEIPT_INTERNAL_SHA256: Final = (
    "bf5ac51420a9483028b0325f0a2f8e4b1b8dba42880f3dced8bfdd2087f2e283"
)
BASE_REVIEW_COMMIT: Final = "eb26dea4fcb282eff9a63d85731557adea7052aa"
BASE_REVIEW_PATH: Final = adapter.FIXED_ADAPTER_REVIEW_LOCK_PATH
BASE_REVIEW_SHA256: Final = (
    "2785f5a31391f8da20aa7bc7daf44b315ba125502cd4d9d765ce25df22773083"
)
BASE_REVIEW_BYTES: Final = 3683
BASE_REVIEW_INTERNAL_SHA256: Final = (
    "b87fd596d5795db943337cb17204ebcc99cce0d32b39dc7011af0d463eec2710"
)
REVIEW_LOCK_PATH: Final = (
    "reports/2026-08-26-r6-player-catalog-fixed-g0-terminal-recovery-review-lock.json"
)
FINAL_LOCK_PATH: Final = adapter.FIXED_FINAL_RELEASE_LOCK_PATH
FOCUSED_OUTPUT_PATH: Final = (
    "reports/2026-08-26-r6-fixed-g0-terminal-recovery-focused-test-output.txt"
)
MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_player_catalog_fixed_g0_terminal_recovery_v1.py"
)
TEST_PATH: Final = (
    "tests/test_corpus_r6_player_catalog_fixed_g0_terminal_recovery_v1.py"
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
FOCUSED_TEST_CWD: Final = "/tmp/nfl-r6-recovery-lock-1df12164"
FOCUSED_TEST_PYTHONPATH: Final = "/tmp/nfl-r6-recovery-lock-1df12164/src"
EXPECTED_FOCUSED_CASE_COUNT: Final = 148
PROJECTION_COMMAND: Final = (
    ".venv/bin/python",
    "-m",
    "nfl_dfs.research.corpus_r6_player_catalog_fixed_g0_terminal_recovery_v1",
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
_PRIOR_SMOKE_FALSE_FIELDS: Final = (
    "analytical_authority",
    "automatic_retry_licensed",
    "corpus_fill_licensed",
    "decision_authority",
    "graph_mutation_licensed",
    "historical_scoring_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "promotion_authority",
    "r6_freeze_authority",
    "uses_realized_outcomes",
)


def _fail(message: str) -> None:
    raise CorpusR6FixedG0TerminalRecoveryV1Error(message)


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


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        _fail(f"{label} keys differ")


def _validate_self_hash(
    value: Mapping[str, Any], *, field: str, label: str,
) -> str:
    retained = value.get(field)
    if type(retained) is not str or not re.fullmatch(r"[0-9a-f]{64}", retained):
        _fail(f"{label} self-hash differs")
    work = dict(value)
    work.pop(field, None)
    if canonical_sha256(work) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _binding(path: str, raw: bytes) -> dict[str, Any]:
    return {
        "relative_path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _expected_binding(path: str, sha256: str, size: int) -> dict[str, Any]:
    return {"relative_path": path, "sha256": sha256, "bytes": size}


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
        raise CorpusR6FixedG0TerminalRecoveryV1Error(
            f"{label} tracked read failed"
        ) from exc
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != sha256:
        _fail(f"{label} file binding differs")
    return raw


def _require_tracked_absence(
    repository: adapter.SubprocessGitRepositoryV1,
    *,
    commit: str,
    path: str,
    label: str,
) -> None:
    if (
        type(commit) is not str
        or re.fullmatch(r"[0-9a-f]{40}", commit) is None
        or type(path) is not str
        or not path
        or Path(path).is_absolute()
        or any(part in {"", ".", ".."} for part in Path(path).parts)
    ):
        _fail(f"{label} absence query differs")
    try:
        observed = repository._run(
            [
                "ls-tree",
                "--full-tree",
                "-z",
                "--name-only",
                commit,
                "--",
                path,
            ],
            label=f"{label} absence proof",
        )
    except Exception as exc:
        raise CorpusR6FixedG0TerminalRecoveryV1Error(
            f"{label} absence proof failed"
        ) from exc
    if observed != b"":
        _fail(f"{label} must remain absent")


def _parse_json(raw: bytes, *, label: str, one_newline: bool = True) -> dict[str, Any]:
    if type(raw) is not bytes or (one_newline and not raw.endswith(b"\n")):
        _fail(f"{label} bytes differ")
    body = raw[:-1] if one_newline else raw
    try:
        value = json.loads(body)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusR6FixedG0TerminalRecoveryV1Error(
            f"{label} is not JSON"
        ) from exc
    item = _mapping(value, label=label)
    if canonical_bytes(item) != body:
        _fail(f"{label} is not canonical JSON")
    return item


def _measure_current(
    repository: adapter.SubprocessGitRepositoryV1, head: str,
) -> list[dict[str, Any]]:
    return [
        _binding(path, repository.read_tracked(head, path))
        for path in IMPLEMENTATION_PATHS
    ]


def _base_review(
    repository: adapter.SubprocessGitRepositoryV1,
) -> tuple[adapter.AdapterReviewBindingV1, dict[str, Any]]:
    raw = _read_exact(
        repository,
        commit=BASE_REVIEW_COMMIT,
        path=BASE_REVIEW_PATH,
        sha256=BASE_REVIEW_SHA256,
        size=BASE_REVIEW_BYTES,
        label="base adapter review lock",
    )
    review = adapter._adapter_review_binding_from_raw_v1(
        raw=raw, review_lock_commit_sha=BASE_REVIEW_COMMIT
    )
    normalized = adapter._reopen_adapter_review_binding_v1(
        review=review, read_tracked=repository.read_tracked
    )
    if normalized["review_lock_internal_sha256"] != BASE_REVIEW_INTERNAL_SHA256:
        _fail("base adapter review internal hash differs")
    return review, adapter._normalize_adapter_review_binding(review)


def validate_fixed_terminal_evidence_v1(
    *, repository: adapter.SubprocessGitRepositoryV1, head: str,
) -> dict[str, Any]:
    """Validate all frozen terminal and prior-smoke evidence without cloud access."""
    amendment_raw = _read_exact(
        repository, commit=head, path=AMENDMENT_PATH,
        sha256=AMENDMENT_SHA256, size=AMENDMENT_BYTES,
        label="terminal recovery amendment",
    )
    failure_raw = _read_exact(
        repository, commit=head, path=V2_FAILURE_PATH,
        sha256=V2_FAILURE_SHA256, size=V2_FAILURE_BYTES,
        label="v2 failure report",
    )
    v1_raw = _read_exact(
        repository, commit=head, path=V1_ATTEMPT_PATH,
        sha256=V1_ATTEMPT_SHA256, size=V1_ATTEMPT_BYTES,
        label="v1 attempt",
    )
    v2_raw = _read_exact(
        repository, commit=head, path=V2_ATTEMPT_PATH,
        sha256=V2_ATTEMPT_SHA256, size=V2_ATTEMPT_BYTES,
        label="v2 attempt",
    )
    recovery_raw = _read_exact(
        repository, commit=head, path=RECOVERY_LOCK_PATH,
        sha256=RECOVERY_LOCK_SHA256, size=RECOVERY_LOCK_BYTES,
        label="v2 recovery review lock",
    )
    smoke_raw = _read_exact(
        repository, commit=head, path=PRIOR_SMOKE_RESULT_PATH,
        sha256=PRIOR_SMOKE_RESULT_SHA256, size=PRIOR_SMOKE_RESULT_BYTES,
        label="prior real-artifact smoke result",
    )
    smoke_time_raw = _read_exact(
        repository, commit=head, path=PRIOR_SMOKE_TIME_PATH,
        sha256=PRIOR_SMOKE_TIME_SHA256, size=PRIOR_SMOKE_TIME_BYTES,
        label="prior smoke execution record",
    )
    g0_raw = _read_exact(
        repository, commit=adapter.FIXED_SOURCE_COMMIT_SHA,
        path=adapter.FIXED_G0_LOCK_PATH,
        sha256=adapter.FIXED_G0_LOCK_FILE_SHA256,
        size=adapter.FIXED_G0_LOCK_FILE_BYTES,
        label="fixed G0 lock",
    )
    official_raw = _read_exact(
        repository, commit=adapter.FIXED_SOURCE_COMMIT_SHA,
        path=OFFICIAL_RECEIPT_PATH,
        sha256=OFFICIAL_RECEIPT_SHA256,
        size=OFFICIAL_RECEIPT_BYTES,
        label="official panel publication receipt",
    )
    review, normalized_review = _base_review(repository)
    v1 = adapter._validate_task0_smoke_attempt_v1(
        adapter._parse_canonical_json(
            v1_raw, label="terminal v1 attempt", allow_one_newline=True
        ),
        expected_adapter_review_binding=normalized_review,
    )
    recovery_value = _parse_json(recovery_raw, label="v2 recovery review lock")
    recovery_measurements = [
        adapter._normalize_file_binding(
            row, label=f"v2 recovery implementation[{ordinal}]"
        )
        for ordinal, row in enumerate(
            _sequence(
                recovery_value.get("implementation_measurements"),
                label="v2 recovery implementation measurements",
            )
        )
    ]
    recovery = adapter.validate_task0_smoke_recovery_review_lock_v1(
        recovery_value,
        expected_implementation_commit_sha=str(
            recovery_value.get("implementation_commit_sha")
        ),
        expected_implementation_measurements=recovery_measurements,
        expected_v1_attempt_raw=v1_raw,
    )
    if recovery["task0_smoke_recovery_review_lock_sha256"] != (
        RECOVERY_LOCK_INTERNAL_SHA256
    ):
        _fail("v2 recovery review-lock internal hash differs")
    v2 = adapter._validate_task0_smoke_attempt_v2(
        adapter._parse_canonical_json(
            v2_raw, label="terminal v2 attempt", allow_one_newline=True
        ),
        expected_recovery_review_lock=recovery,
        expected_recovery_review_lock_file=_expected_binding(
            RECOVERY_LOCK_PATH, RECOVERY_LOCK_SHA256, RECOVERY_LOCK_BYTES
        ),
        expected_v1_attempt_raw=v1_raw,
    )
    normalized_pins = adapter._normalize_pins(adapter.FIXED_PINS)
    g0 = adapter._validate_g0_lock(
        adapter._parse_canonical_json(
            g0_raw, label="terminal fixed G0 lock", allow_one_newline=True
        ),
        normalized_pins=normalized_pins,
    )
    official = adapter._validate_publication_receipt(
        adapter._parse_canonical_json(
            official_raw,
            label="terminal official panel receipt",
            allow_one_newline=True,
        ),
        normalized_pins=normalized_pins,
        lock=g0,
    )
    if (
        official["schema_version"] != "foundry-v12-panel-index-publication/v1"
        or official["publication_receipt_sha256"]
        != OFFICIAL_RECEIPT_INTERNAL_SHA256
    ):
        _fail("official publication receipt schema/hash differs")
    smoke = _parse_json(smoke_raw, label="prior real-artifact smoke result")
    if _validate_self_hash(
        smoke,
        field="one_slate_execution_sha256",
        label="prior real-artifact smoke result",
    ) != PRIOR_SMOKE_INTERNAL_SHA256:
        _fail("prior real-artifact smoke internal hash differs")
    verification = _mapping(smoke.get("verification"), label="smoke verification")
    if (
        smoke.get("schema_version") != "corpus-extreme-tail-one-slate-execution/v1"
        or smoke.get("execution_mode")
        != "authoritative-dose-one-slate-outcome-blind-smoke"
        or smoke.get("slate_id") != "2023-w01"
        or smoke.get("panel_index_identity") != dict(adapter.FIXED_PANEL_IDENTITY)
        or smoke.get("panel_index_sha256") != adapter.FIXED_PANEL_INDEX_SHA256
        or smoke.get("task_acceptance_identity")
        != {
            "bytes": 15032,
            "generation": "1787524357272657",
            "sha256": "800e673713602035daed571c0d11dea9f2cc841ca4e33145b8763a162096d0a4",
            "uri": (
                "gs://nfl-predictions-503414-corpus-parametric/research/"
                "corpus-parametric-research/batches/"
                "20260823-corpus-parametric-production-batch-v12a/tasks/"
                "task-0000-2023-w01/variants/transport/accepted-terminal.json"
            ),
        }
        or smoke.get("carrier_identity")
        != {
            "bytes": 12023,
            "generation": "1787521590972723",
            "sha256": "8149de8f5ca66c89d1137b92328f0add7f76c46aeff281d9323ca6ac5ce20548",
            "uri": (
                "gs://nfl-predictions-503414-corpus-parametric/research/"
                "corpus-parametric-research/batches/"
                "20260823-corpus-parametric-production-batch-v12a/tasks/"
                "task-0000-2023-w01/result/task-result.json"
            ),
        }
        or set(verification)
        != {
            "canonical_authoritative_dose_verified",
            "canonical_reconstruction_verified",
            "carrier_source_receipts_verified",
            "panel_content_identity_verified",
            "panel_membership_binding_verified",
            "support_census_canonical_replay_verified",
            "task_acceptance_carrier_binding_verified",
            "task_acceptance_content_identity_verified",
        }
        or any(value is not True for value in verification.values())
        or any(
            smoke.get(field) is not False for field in _PRIOR_SMOKE_FALSE_FIELDS
        )
    ):
        _fail("prior real-artifact smoke semantics differ")
    try:
        time_text = smoke_time_raw.decode("utf-8")
    except UnicodeError as exc:
        raise CorpusR6FixedG0TerminalRecoveryV1Error(
            "prior smoke execution record is not UTF-8"
        ) from exc
    if (
        "run_corpus_extreme_tail_one_slate_smoke_v1.py" not in time_text
        or "--slate-id 2023-w01" not in time_text
        or "Exit status: 0" not in time_text
    ):
        _fail("prior smoke execution status differs")
    _require_tracked_absence(
        repository,
        commit=head,
        path=adapter.FIXED_TASK0_SMOKE_RECEIPT_PATH,
        label="adapter smoke success receipt",
    )
    return {
        "amendment_file": _binding(AMENDMENT_PATH, amendment_raw),
        "v2_failure_file": _binding(V2_FAILURE_PATH, failure_raw),
        "v1_attempt_file": _binding(V1_ATTEMPT_PATH, v1_raw),
        "v1_attempt_internal_sha256": v1[
            "task0_real_artifact_smoke_attempt_sha256"
        ],
        "v2_attempt_file": _binding(V2_ATTEMPT_PATH, v2_raw),
        "v2_attempt_internal_sha256": v2[
            "task0_real_artifact_smoke_attempt_v2_sha256"
        ],
        "v2_recovery_lock_file": _binding(RECOVERY_LOCK_PATH, recovery_raw),
        "v2_recovery_lock_internal_sha256": recovery[
            "task0_smoke_recovery_review_lock_sha256"
        ],
        "prior_real_artifact_smoke_file": _binding(
            PRIOR_SMOKE_RESULT_PATH, smoke_raw
        ),
        "prior_real_artifact_smoke_internal_sha256": smoke[
            "one_slate_execution_sha256"
        ],
        "prior_real_artifact_smoke_time_file": _binding(
            PRIOR_SMOKE_TIME_PATH, smoke_time_raw
        ),
        "official_publication_receipt_file": _binding(
            OFFICIAL_RECEIPT_PATH, official_raw
        ),
        "official_publication_receipt_internal_sha256": official[
            "publication_receipt_sha256"
        ],
        "base_adapter_review_binding": adapter._normalize_adapter_review_binding(
            review
        ),
    }


def _focused_output(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes:
        _fail("focused output must be exact bytes")
    try:
        raw.decode("ascii")
    except UnicodeError as exc:
        raise CorpusR6FixedG0TerminalRecoveryV1Error(
            "focused output is not ASCII"
        ) from exc
    if not raw.endswith(b"\n"):
        _fail("focused output must end with one complete line")
    lines = raw[:-1].split(b"\n")
    if len(lines) < 2 or any(line == b"" for line in lines):
        _fail("focused output must contain progress and one summary")
    progress_lines = lines[:-1]
    summary = lines[-1]
    completed = 0
    prior_percentage = -1
    for line in progress_lines:
        match = re.fullmatch(
            rb"(\.+)( +)\[([ ]{0,2})([1-9][0-9]?|100)%\]",
            line,
        )
        if match is None:
            _fail("focused output progress differs")
        completed += len(match.group(1))
        if len(match.group(3)) + len(match.group(4)) != 3:
            _fail("focused output percentage width differs")
        percentage = int(match.group(4))
        expected_percentage = completed * 100 // EXPECTED_FOCUSED_CASE_COUNT
        if (
            completed > EXPECTED_FOCUSED_CASE_COUNT
            or percentage != expected_percentage
            or percentage <= prior_percentage
        ):
            _fail("focused output progress accounting differs")
        prior_percentage = percentage
    if completed != EXPECTED_FOCUSED_CASE_COUNT or prior_percentage != 100:
        _fail("focused output case coverage differs")
    summary_pattern = (
        str(EXPECTED_FOCUSED_CASE_COUNT).encode("ascii")
        + rb" passed in (?:0|[1-9][0-9]*)\.[0-9]{2}s"
    )
    if re.fullmatch(summary_pattern, summary) is None:
        _fail("focused output pass summary differs")
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
        independent_static_review_passed is not True
        or focused_pass_count != EXPECTED_FOCUSED_CASE_COUNT
    ):
        _fail("terminal recovery review approval differs")
    body: dict[str, Any] = {
        "schema_version": REVIEW_LOCK_SCHEMA,
        "implementation_commit_sha": implementation_commit_sha,
        "implementation_measurements": [dict(row) for row in implementation_measurements],
        **{key: value for key, value in evidence.items()},
        "focused_test_command": list(FOCUSED_TEST_COMMAND),
        "focused_test_cwd": FOCUSED_TEST_CWD,
        "focused_test_pythonpath": FOCUSED_TEST_PYTHONPATH,
        "focused_test_output_file": dict(focused_output_file),
        "focused_test_invocation_count": 1,
        "focused_test_passed_count": focused_pass_count,
        "independent_static_review_passed": True,
        "p0_open_count": 0,
        "p1_open_count": 0,
        "p2_open_count": 0,
        "adapter_attempt_count": 2,
        "adapter_v1_smoke_passed": False,
        "adapter_v2_smoke_passed": False,
        "adapter_success_receipt_absent": True,
        "prior_real_artifact_smoke_passed": True,
        "third_adapter_smoke_allowed": False,
        "projection_publication_licensed": False,
        "cloud_read_licensed": False,
        "gcs_mutation_licensed": False,
        "world_matrix_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["terminal_recovery_review_lock_sha256"] = canonical_sha256(body)
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
    item = _mapping(value, label="terminal recovery review lock")
    retained = _validate_self_hash(
        item,
        field="terminal_recovery_review_lock_sha256",
        label="terminal recovery review lock",
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
        _fail("terminal recovery review lock differs")
    item["terminal_recovery_review_lock_sha256"] = retained
    return item


def _build_final_lock(
    *, review_lock_file: Mapping[str, Any], review_lock: Mapping[str, Any],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": FINAL_LOCK_SCHEMA,
        "evidence_source_commit_sha": adapter.FIXED_SOURCE_COMMIT_SHA,
        "implementation_commit_sha": review_lock["implementation_commit_sha"],
        "implementation_measurements": review_lock["implementation_measurements"],
        "focused_test_command": list(FOCUSED_TEST_COMMAND),
        "focused_test_cwd": FOCUSED_TEST_CWD,
        "focused_test_pythonpath": FOCUSED_TEST_PYTHONPATH,
        "terminal_recovery_review_lock_file": dict(review_lock_file),
        "terminal_recovery_review_lock_internal_sha256": review_lock[
            "terminal_recovery_review_lock_sha256"
        ],
        "base_adapter_review_binding": review_lock["base_adapter_review_binding"],
        "amendment_file": review_lock["amendment_file"],
        "v2_failure_file": review_lock["v2_failure_file"],
        "v1_attempt_file": review_lock["v1_attempt_file"],
        "v1_attempt_internal_sha256": review_lock["v1_attempt_internal_sha256"],
        "v2_attempt_file": review_lock["v2_attempt_file"],
        "v2_attempt_internal_sha256": review_lock["v2_attempt_internal_sha256"],
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
        "prior_real_artifact_smoke_time_file": review_lock[
            "prior_real_artifact_smoke_time_file"
        ],
        "prior_real_artifact_smoke_passed": True,
        "third_adapter_smoke_allowed": False,
        "independent_static_review_passed": True,
        "p0_open_count": 0,
        "p1_open_count": 0,
        "p2_open_count": 0,
        "current_clean_git_required": True,
        "required_source_task_count": catalog.TASK_COUNT,
        "required_task_acceptance_body_reopen_count": catalog.TASK_COUNT,
        "required_carrier_body_reopen_count": catalog.TASK_COUNT,
        "all_inputs_derived_before_first_output": True,
        "projection_only_publication_reviewed": True,
        "projection_only_publication_licensed": True,
        "projection_release_command": list(PROJECTION_COMMAND),
        "production_enable_environment_variable": PRODUCTION_ENABLE_ENV,
        "production_enable_environment_value": "1",
        "gcs_create_once_required": True,
        "gcs_overwrite_licensed": False,
        "world_matrix_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["final_release_lock_sha256"] = canonical_sha256(body)
    return body


def validate_final_lock_v2(
    value: object,
    *,
    review_lock_file: Mapping[str, Any],
    review_lock: Mapping[str, Any],
) -> dict[str, Any]:
    item = _mapping(value, label="terminal recovery final lock")
    retained = _validate_self_hash(
        item, field="final_release_lock_sha256", label="terminal recovery final lock"
    )
    expected = _build_final_lock(
        review_lock_file=review_lock_file, review_lock=review_lock
    )
    if canonical_bytes(item) != canonical_bytes(expected):
        _fail("terminal recovery final lock differs")
    item["final_release_lock_sha256"] = retained
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
        parent = parent / part
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
        write_fd = os.open(
            path.name,
            write_flags,
            0o600,
            dir_fd=directory_fd,
        )
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
        raise CorpusR6FixedG0TerminalRecoveryV1Error(
            f"{label} create-once failed"
        ) from exc
    except OSError as exc:
        raise CorpusR6FixedG0TerminalRecoveryV1Error(
            f"{label} secure write failed"
        ) from exc
    finally:
        if reopen_fd is not None:
            os.close(reopen_fd)
        if write_fd is not None:
            os.close(write_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def build_review_lock_production_v1(
    *, output_relative_path: str, independent_static_review_passed: bool,
) -> dict[str, Any]:
    if output_relative_path != REVIEW_LOCK_PATH:
        _fail("terminal recovery review-lock output differs")
    output = _safe_output_path(REVIEW_LOCK_PATH, label="terminal recovery review lock")
    repository = adapter.SubprocessGitRepositoryV1()
    head = repository.require_current_clean_head()
    measurements = _measure_current(repository, head)
    evidence = validate_fixed_terminal_evidence_v1(repository=repository, head=head)
    focused_raw = repository.read_tracked(head, FOCUSED_OUTPUT_PATH)
    focused = _focused_output(focused_raw)
    lock = _build_review_lock(
        implementation_commit_sha=head,
        implementation_measurements=measurements,
        evidence=evidence,
        focused_output_file=_binding(FOCUSED_OUTPUT_PATH, focused_raw),
        focused_pass_count=int(focused["passed_test_count"]),
        independent_static_review_passed=independent_static_review_passed,
    )
    _write_once(output, lock, label="terminal recovery review lock")
    return lock


def _resolve_review_lock(
    *, repository: adapter.SubprocessGitRepositoryV1, head: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = repository.read_tracked(head, REVIEW_LOCK_PATH)
    value = _parse_json(raw, label="tracked terminal recovery review lock")
    implementation_commit = str(value.get("implementation_commit_sha"))
    raw_measurements = _sequence(
        value.get("implementation_measurements"),
        label="tracked terminal recovery implementation measurements",
    )
    measurements = [
        _mapping(row, label=f"terminal recovery measurement[{ordinal}]")
        for ordinal, row in enumerate(raw_measurements)
    ]
    if [row.get("relative_path") for row in measurements] != list(
        IMPLEMENTATION_PATHS
    ):
        _fail("tracked terminal recovery implementation paths differ")
    for measurement in measurements:
        row = _mapping(measurement, label="terminal recovery measurement")
        _read_exact(
            repository,
            commit=implementation_commit,
            path=str(row["relative_path"]),
            sha256=str(row["sha256"]),
            size=int(row["bytes"]),
            label="reviewed terminal recovery implementation",
        )
        _read_exact(
            repository,
            commit=head,
            path=str(row["relative_path"]),
            sha256=str(row["sha256"]),
            size=int(row["bytes"]),
            label="current terminal recovery implementation",
        )
    evidence = validate_fixed_terminal_evidence_v1(repository=repository, head=head)
    focused_raw = repository.read_tracked(head, FOCUSED_OUTPUT_PATH)
    focused = _focused_output(focused_raw)
    lock = validate_review_lock_v1(
        value,
        implementation_commit_sha=implementation_commit,
        implementation_measurements=measurements,
        evidence=evidence,
        focused_output_file=_binding(FOCUSED_OUTPUT_PATH, focused_raw),
        focused_pass_count=int(focused["passed_test_count"]),
    )
    return lock, _binding(REVIEW_LOCK_PATH, raw)


def build_final_lock_production_v2(
    *, output_relative_path: str, publication_approved: bool,
) -> dict[str, Any]:
    if output_relative_path != FINAL_LOCK_PATH or publication_approved is not True:
        _fail("terminal recovery final approval/output differs")
    output = _safe_output_path(FINAL_LOCK_PATH, label="terminal recovery final lock")
    repository = adapter.SubprocessGitRepositoryV1()
    head = repository.require_current_clean_head()
    review, review_file = _resolve_review_lock(repository=repository, head=head)
    lock = _build_final_lock(review_lock_file=review_file, review_lock=review)
    _write_once(output, lock, label="terminal recovery final lock")
    return lock


def _resolve_final_lock(
    *, repository: adapter.SubprocessGitRepositoryV1,
) -> tuple[str, adapter.AdapterReviewBindingV1, dict[str, Any]]:
    head = repository.require_current_clean_head()
    review, review_file = _resolve_review_lock(repository=repository, head=head)
    raw = repository.read_tracked(head, FINAL_LOCK_PATH)
    final = validate_final_lock_v2(
        _parse_json(raw, label="tracked terminal recovery final lock"),
        review_lock_file=review_file,
        review_lock=review,
    )
    base_review, normalized_base = _base_review(repository)
    if final["base_adapter_review_binding"] != normalized_base:
        _fail("terminal final/base review binding differs")
    return head, base_review, final


def publish_projection_production_v1() -> dict[str, Any]:
    if os.environ.get(PRODUCTION_ENABLE_ENV) != "1":
        _fail("terminal recovery projection is parked")
    repository = adapter.SubprocessGitRepositoryV1()
    _, base_review, _ = _resolve_final_lock(repository=repository)
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
        description="Terminal recovery for fixed-G0 R6 catalog projection"
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
            "adapter_success_receipt_absent": True,
            "default_state": "parked",
            "final_lock_path": FINAL_LOCK_PATH,
            "prior_real_artifact_smoke_passed": True,
            "projection_command": list(PROJECTION_COMMAND),
            "review_lock_path": REVIEW_LOCK_PATH,
            "third_adapter_smoke_allowed": False,
            "uses_realized_outcomes": False,
        }).decode("ascii"))
        return 0
    if args.command == "build-review-lock":
        result = build_review_lock_production_v1(
            output_relative_path=args.output,
            independent_static_review_passed=args.static_review_approved,
        )
    elif args.command == "build-final-lock":
        result = build_final_lock_production_v2(
            output_relative_path=args.output,
            publication_approved=args.publication_approved,
        )
    elif args.command == "publish-projection" and args.execute is True:
        result = publish_projection_production_v1()
    else:
        _fail("explicit terminal recovery gate absent")
    print(canonical_bytes(result).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
