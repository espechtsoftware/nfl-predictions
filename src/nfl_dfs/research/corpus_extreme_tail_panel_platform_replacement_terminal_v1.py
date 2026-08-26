"""Fail-closed terminal closure for the exhausted T230 ordinal-6 repair.

The sole attempt-1 worker exited nonzero.  This module can validate and retain
that mechanical failure, but it cannot launch a worker or verifier and cannot
read a result or acceptance body.  Publication remains controller-owned and
requires a separately tracked review lock and real-artifact preflight.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
import re
import subprocess
from typing import Final, Protocol

from nfl_dfs.research import corpus_extreme_tail_panel_execution as execution
from nfl_dfs.research import corpus_extreme_tail_panel_platform_replacement_v1 as replacement
from nfl_dfs.research import corpus_extreme_tail_panel_transport as transport
from nfl_dfs.research import corpus_parametric_batch as batch


CONTRACT_SCHEMA: Final = "foundry-t230-ordinal-6-terminal-closure-contract/v1"
TERMINAL_PROJECTION_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-failure-projection/v1"
)
SURFACE_CENSUS_SCHEMA: Final = (
    "foundry-t230-ordinal-6-terminal-closure-surface-census/v1"
)
LANE_A_SURFACE_CENSUS_SCHEMA: Final = (
    "foundry-t230-lane-a-terminal-closure-surface-census/v1"
)
PREFLIGHT_SCHEMA: Final = (
    "foundry-t230-ordinal-6-terminal-closure-real-artifact-preflight/v1"
)
PREFLIGHT_ATTEMPT_SCHEMA: Final = (
    "foundry-t230-ordinal-6-terminal-closure-preflight-attempt/v1"
)
REVIEW_LOCK_SCHEMA: Final = (
    "foundry-t230-ordinal-6-terminal-closure-review-lock/v1"
)
RECOVERY_TERMINAL_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-execution-terminal/v1"
)
LANE_A_CLOSURE_SCHEMA: Final = (
    "foundry-t230-lane-a-terminal-invalid-obligation/v1"
)
OPERATOR_RESULT_SCHEMA: Final = (
    "foundry-t230-ordinal-6-terminal-closure-operator-result/v1"
)

AMENDMENT_RELATIVE_PATH: Final = (
    "reports/2026-08-26-t230-ordinal6-replacement-terminal-closure-amendment.md"
)
AMENDMENT_SHA256: Final = (
    "301eaee07c6afd31e49def28fec258904adc6591e33715f6c3c7fc5c7a695730"
)
AMENDMENT_BYTES: Final = 11308
PANEL_CLOSURE_AMENDMENT_RELATIVE_PATH: Final = (
    "reports/2026-08-26-t230-current-run-terminal-panel-closure-amendment.md"
)
PANEL_CLOSURE_AMENDMENT_SHA256: Final = (
    "9aeec00853be5d8c8ae4e7b3f21e53ea392482d07f04876220feef7b73c06d82"
)
PANEL_CLOSURE_AMENDMENT_BYTES: Final = 10616
IMPLEMENTATION_RELATIVE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_extreme_tail_panel_platform_replacement_terminal_v1.py"
)
TEST_RELATIVE_PATH: Final = (
    "tests/test_corpus_extreme_tail_panel_platform_replacement_terminal_v1.py"
)
CONTROLLER_RELATIVE_PATH: Final = (
    "scripts/run_corpus_extreme_tail_panel_platform_replacement_terminal_v1.py"
)
CONTROLLER_TEST_RELATIVE_PATH: Final = (
    "tests/test_run_corpus_extreme_tail_panel_platform_replacement_terminal_v1.py"
)
PREFLIGHT_RELATIVE_PATH: Final = (
    "reports/2026-08-26-t230-ordinal6-terminal-closure-real-artifact-preflight.json"
)
PREFLIGHT_ATTEMPT_RELATIVE_PATH: Final = (
    "reports/2026-08-26-t230-ordinal6-terminal-closure-preflight-attempt.json"
)
REVIEW_LOCK_RELATIVE_PATH: Final = (
    "reports/2026-08-26-t230-ordinal6-terminal-closure-review-lock.json"
)
FOCUSED_TEST_OUTPUT_RELATIVE_PATH: Final = (
    "reports/2026-08-26-t230-ordinal6-terminal-closure-focused-test-output.txt"
)
FOCUSED_TEST_COMMAND: Final = (
    ".venv/bin/python",
    "-m",
    "pytest",
    "-q",
    TEST_RELATIVE_PATH,
    CONTROLLER_TEST_RELATIVE_PATH,
)
PREFLIGHT_COMMAND: Final = (
    ".venv/bin/python",
    CONTROLLER_RELATIVE_PATH,
    "preflight",
    "--preflight",
)
IMPLEMENTATION_COMMIT_ENV: Final = (
    "FOUNDRY_T230_TERMINAL_CLOSURE_IMPLEMENTATION_COMMIT"
)

SOURCE_ORDINAL: Final = 6
REPLACEMENT_EXECUTION: Final = "atlas-minimal-c-s2023-w1-v1-67669"
REPLACEMENT_TASK: Final = REPLACEMENT_EXECUTION + "-task0"
REPLACEMENT_STARTED_TIME: Final = "2026-08-26T05:15:51.761279Z"
REPLACEMENT_COMPLETION_TIME: Final = "2026-08-26T05:18:35.473406Z"
TASK_CREATION_TIME: Final = "2026-08-26T05:15:39.623775Z"
TASK_START_TIME: Final = "2026-08-26T05:18:10.221899Z"
TASK_COMPLETION_TIME: Final = "2026-08-26T05:18:32.275145Z"
TASK_MESSAGE: Final = "The container exited with an error."
TASK_REASON: Final = "NonZeroExitCode"
EXECUTION_DESCRIBE_ARGV: Final = (
    "gcloud",
    "run",
    "jobs",
    "executions",
    "describe",
    REPLACEMENT_EXECUTION,
    "--project",
    transport.PROJECT,
    "--region",
    transport.REGION,
    "--format=json",
)
TASK_DESCRIBE_ARGV: Final = (
    "gcloud",
    "beta",
    "run",
    "jobs",
    "executions",
    "tasks",
    "list",
    f"--execution={REPLACEMENT_EXECUTION}",
    f"--project={transport.PROJECT}",
    f"--region={transport.REGION}",
    "--limit=2",
    "--format=json",
)
EXECUTION_COMPLETED_MESSAGE: Final = (
    "Task atlas-minimal-c-s2023-w1-v1-67669-task0 failed with exit code: 1 "
    "and message: The container exited with an error."
)
EXECUTION_CONDITIONS: Final = [
    {
        "lastTransitionTime": "2026-08-26T05:18:35.473406Z",
        "message": EXECUTION_COMPLETED_MESSAGE,
        "reason": TASK_REASON,
        "status": "False",
        "type": "Completed",
    },
    {
        "lastTransitionTime": "2026-08-26T05:15:40.590844Z",
        "message": "Provisioned imported containers.",
        "status": "True",
        "type": "ResourcesAvailable",
    },
    {
        "lastTransitionTime": "2026-08-26T05:18:10.221899Z",
        "message": "Started deployed execution in 2m29.63s.",
        "status": "True",
        "type": "Started",
    },
    {
        "lastTransitionTime": "2026-08-26T05:15:40.489467Z",
        "message": "Imported container image.",
        "status": "True",
        "type": "ContainerReady",
    },
]

REPLACEMENT_INTENT_IDENTITY: Final = {
    "uri": replacement.REPLACEMENT_INTENT_URI,
    "generation": "1787721338174308",
    "sha256": "86f34d3c755b68a925e354c7379c1e6c54b7e4856b2dfc632009cc84de45133d",
    "bytes": 85600,
}
REPLACEMENT_OWNERSHIP_IDENTITY: Final = {
    "uri": replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI,
    "generation": "1787721341183601",
    "sha256": "15f0881fe9254bd765e2ed6278a6dd71b88ed579818b1d5734601b9256784fdf",
    "bytes": 145712,
}
REPLACEMENT_STAGE_START_IDENTITY: Final = {
    "uri": replacement.REPLACEMENT_STAGE_START_URI,
    "generation": "1787721341713255",
    "sha256": "468e278eb078395f6ebef9479a72f01247834b1d56a9aeb1a790662c4ef2cbb0",
    "bytes": 192151,
}

_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
    "replacement_execution_accepted",
    "worker_stage_accepted",
    "bridge_verifier_licensed",
    "lane_resume_licensed",
    "canonical_lane_root_licensed",
    "panel_release_licensed",
    "amended_panel_root_accepted",
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_CRC32C = re.compile(r"[A-Za-z0-9+/]{6}==")


class T230PlatformReplacementTerminalError(RuntimeError):
    """The ordinal-6 terminal closure failed closed."""


class TerminalClosureBackend(transport.JournalBackend, Protocol):
    """Exact-name backend; deliberately has no list or outcome method."""

    def probe_known_uri_metadata(self, uri: str) -> Mapping[str, object] | None:
        """Return one exact-name metadata projection or None only on 404."""


def _fail(message: str) -> None:
    raise T230PlatformReplacementTerminalError(message)


def _canonical(value: object) -> bytes:
    return batch.canonical_json_bytes(value)


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    if field in body:
        _fail(f"self-hash field already exists: {field}")
    retained = dict(body)
    retained[field] = batch.canonical_sha256(retained)
    return retained


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> None:
    retained = value.get(field)
    if not isinstance(retained, str) or _SHA256.fullmatch(retained) is None:
        _fail(f"{label} self-hash differs")
    body = dict(value)
    del body[field]
    if batch.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise T230PlatformReplacementTerminalError(
            f"{label} identity differs"
        ) from exc


def _false_authorities(value: Mapping[str, object], *, label: str) -> None:
    for field in _FALSE_AUTHORITY_FIELDS:
        if value.get(field) is not False:
            _fail(f"{label}.{field} must be false")


def _authority_closure() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _exact_read_json(
    backend: transport.JournalBackend,
    identity_value: Mapping[str, object],
    *,
    label: str,
) -> tuple[dict[str, object], dict[str, object], bytes]:
    identity = _identity(identity_value, label=label)
    raw = backend.read(identity)
    if (
        not isinstance(raw, bytes)
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} generation-pinned bytes differ")
    try:
        body = transport.strict_json(raw, label=label)
    except Exception as exc:
        raise T230PlatformReplacementTerminalError(
            f"{label} canonical JSON differs"
        ) from exc
    if _canonical(body) != raw:
        _fail(f"{label} body is not canonical JSON")
    return identity, body, raw


def frozen_terminal_closure_contract_v1() -> dict[str, object]:
    parent_contract = replacement.frozen_platform_replacement_contract_v1()
    body = {
        "schema_version": CONTRACT_SCHEMA,
        "run_id": transport.RUN_ID,
        "source_ordinal": SOURCE_ORDINAL,
        "primary_execution": replacement.FAILED_EXECUTION,
        "replacement_execution": REPLACEMENT_EXECUTION,
        "replacement_runtime_attempt_ordinal": 1,
        "replacement_worker_execution_limit": 1,
        "replacement_worker_execution_count": 1,
        "second_replacement_allowed": False,
        "bridge_verifier_allowed": False,
        "amendment_measurement": {
            "relative_path": AMENDMENT_RELATIVE_PATH,
            "sha256": AMENDMENT_SHA256,
            "bytes": AMENDMENT_BYTES,
        },
        "current_run_panel_closure_amendment_measurement": {
            "relative_path": PANEL_CLOSURE_AMENDMENT_RELATIVE_PATH,
            "sha256": PANEL_CLOSURE_AMENDMENT_SHA256,
            "bytes": PANEL_CLOSURE_AMENDMENT_BYTES,
        },
        "parent_platform_replacement_contract": parent_contract,
        "parent_replacement_contract_sha256": parent_contract[
            "platform_replacement_contract_sha256"
        ],
        "replacement_intent_identity": dict(REPLACEMENT_INTENT_IDENTITY),
        "replacement_launch_ownership_identity": dict(
            REPLACEMENT_OWNERSHIP_IDENTITY
        ),
        "replacement_stage_start_identity": dict(
            REPLACEMENT_STAGE_START_IDENTITY
        ),
        "recovery_execution_terminal_uri": (
            replacement.REPLACEMENT_EXECUTION_TERMINAL_URI
        ),
        "supplemental_lane_a_terminal_root_uri": (
            replacement.SUPPLEMENTAL_LANE_ROOT_URI
        ),
        "supplemental_panel_root_uri_reserved_and_unpublished": (
            replacement.SUPPLEMENTAL_PANEL_ROOT_URI
        ),
        "review_lock_relative_path": REVIEW_LOCK_RELATIVE_PATH,
        "preflight_relative_path": PREFLIGHT_RELATIVE_PATH,
        "preflight_attempt_relative_path": PREFLIGHT_ATTEMPT_RELATIVE_PATH,
        "implementation_relative_paths": [
            IMPLEMENTATION_RELATIVE_PATH,
            TEST_RELATIVE_PATH,
            CONTROLLER_RELATIVE_PATH,
            CONTROLLER_TEST_RELATIVE_PATH,
        ],
        "tracked_review_lock_required_before_publication": True,
        "review_lock_implementation_commit_must_precede_lock_head": True,
        "review_lock_must_not_embed_its_own_commit": True,
        "real_artifact_preflight_required_before_publication": True,
        "preflight_attempt_marker_create_once_before_any_cloud_read": True,
        "failed_or_crashed_preflight_consumes_attempt": True,
        "second_preflight_attempt_allowed": False,
        "result_body_may_be_read": False,
        "acceptance_body_may_be_read": False,
        "bucket_list_may_be_used": False,
        "cloud_submission_may_be_made": False,
        "ordinal_seven_may_resume": False,
        "current_panel_terminal_invalid": True,
        **_authority_closure(),
    }
    return _self_hash(body, "terminal_closure_contract_sha256")


def validate_terminal_closure_contract_v1(value: object) -> dict[str, object]:
    expected = frozen_terminal_closure_contract_v1()
    if not isinstance(value, Mapping) or _canonical(value) != _canonical(expected):
        _fail("terminal-closure contract differs")
    return expected


def _regular_file_measurement(
    repository_root: Path, relative_path: str, *, label: str
) -> dict[str, object]:
    relative = Path(relative_path)
    if (
        not repository_root.is_absolute()
        or not repository_root.is_dir()
        or repository_root.is_symlink()
        or relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        _fail(f"{label} path differs")
    current = repository_root
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            _fail(f"{label} path contains a symlink")
    if not current.is_file():
        _fail(f"{label} file is absent")
    raw = current.read_bytes()
    return {
        "relative_path": relative_path,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def terminal_closure_implementation_measurements_v1(
    *, repository_root: Path = transport.REPOSITORY_ROOT
) -> list[dict[str, object]]:
    return [
        _regular_file_measurement(
            repository_root, path, label=f"closure implementation[{ordinal}]"
        )
        for ordinal, path in enumerate(
            (
                IMPLEMENTATION_RELATIVE_PATH,
                TEST_RELATIVE_PATH,
                CONTROLLER_RELATIVE_PATH,
                CONTROLLER_TEST_RELATIVE_PATH,
            )
        )
    ]


def _validate_measurement(
    value: object, *, relative_path: str, label: str
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} measurement must be one object")
    item = dict(value)
    if (
        set(item) != {"relative_path", "sha256", "bytes"}
        or item.get("relative_path") != relative_path
        or not isinstance(item.get("sha256"), str)
        or _SHA256.fullmatch(str(item["sha256"])) is None
        or type(item.get("bytes")) is not int
        or int(item["bytes"]) < 1
    ):
        _fail(f"{label} measurement differs")
    return item


def verify_terminal_closure_implementation_commit_v1(
    *,
    implementation_source_commit_sha: str,
    expected_implementation_measurements: Sequence[Mapping[str, object]],
    repository_root: Path = transport.REPOSITORY_ROOT,
) -> str:
    """Prove reviewed implementation bytes equal one earlier clean commit."""
    if (
        not isinstance(implementation_source_commit_sha, str)
        or re.fullmatch(r"[0-9a-f]{40}", implementation_source_commit_sha) is None
    ):
        _fail("implementation source commit differs")
    current = terminal_closure_implementation_measurements_v1(
        repository_root=repository_root
    )
    if [dict(row) for row in expected_implementation_measurements] != current:
        _fail("implementation measurements differ from current bytes")
    candidate_paths = [
        *(str(row["relative_path"]) for row in current),
        AMENDMENT_RELATIVE_PATH,
        PANEL_CLOSURE_AMENDMENT_RELATIVE_PATH,
    ]
    try:
        status = subprocess.run(
            [
                "git",
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                *candidate_paths,
            ],
            cwd=repository_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise T230PlatformReplacementTerminalError(
            "implementation candidate Git status read failed"
        ) from exc
    if status != b"":
        _fail("implementation candidate paths are not tracked and clean")
    expected_files = [
        *current,
        {
            "relative_path": AMENDMENT_RELATIVE_PATH,
            "sha256": AMENDMENT_SHA256,
            "bytes": AMENDMENT_BYTES,
        },
        {
            "relative_path": PANEL_CLOSURE_AMENDMENT_RELATIVE_PATH,
            "sha256": PANEL_CLOSURE_AMENDMENT_SHA256,
            "bytes": PANEL_CLOSURE_AMENDMENT_BYTES,
        },
    ]
    for measurement in expected_files:
        try:
            committed = subprocess.run(
                [
                    "git",
                    "show",
                    f"{implementation_source_commit_sha}:{measurement['relative_path']}",
                ],
                cwd=repository_root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as exc:
            raise T230PlatformReplacementTerminalError(
                "implementation source commit replay failed"
            ) from exc
        if (
            len(committed) != measurement["bytes"]
            or sha256(committed).hexdigest() != measurement["sha256"]
            or (repository_root / str(measurement["relative_path"])).read_bytes()
            != committed
        ):
            _fail("implementation source commit bytes differ")
    return implementation_source_commit_sha


def build_preflight_attempt_marker_v1(
    *,
    implementation_source_commit_sha: str,
    reviewed_implementation_measurements: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    paths = (
        IMPLEMENTATION_RELATIVE_PATH,
        TEST_RELATIVE_PATH,
        CONTROLLER_RELATIVE_PATH,
        CONTROLLER_TEST_RELATIVE_PATH,
    )
    if (
        re.fullmatch(r"[0-9a-f]{40}", implementation_source_commit_sha) is None
        or len(reviewed_implementation_measurements) != len(paths)
    ):
        _fail("preflight-attempt implementation source differs")
    implementations = [
        _validate_measurement(
            row,
            relative_path=path,
            label=f"preflight-attempt implementation[{ordinal}]",
        )
        for ordinal, (row, path) in enumerate(
            zip(reviewed_implementation_measurements, paths, strict=True)
        )
    ]
    body = {
        "schema_version": PREFLIGHT_ATTEMPT_SCHEMA,
        "run_id": transport.RUN_ID,
        "source_ordinal": SOURCE_ORDINAL,
        "command": list(PREFLIGHT_COMMAND),
        "invocation_count": 1,
        "implementation_source_commit_sha": implementation_source_commit_sha,
        "reviewed_implementation_measurements": implementations,
        "reviewed_implementation_measurements_sha256": (
            batch.canonical_sha256(implementations)
        ),
        "amendment_measurement": {
            "relative_path": AMENDMENT_RELATIVE_PATH,
            "sha256": AMENDMENT_SHA256,
            "bytes": AMENDMENT_BYTES,
        },
        "current_run_panel_closure_amendment_measurement": {
            "relative_path": PANEL_CLOSURE_AMENDMENT_RELATIVE_PATH,
            "sha256": PANEL_CLOSURE_AMENDMENT_SHA256,
            "bytes": PANEL_CLOSURE_AMENDMENT_BYTES,
        },
        "independent_static_review_complete": True,
        "independent_static_disposition": "approve",
        "p0_count": 0,
        "p1_count": 0,
        "p2_count": 0,
        "attempt_consumed_even_if_read_or_process_fails": True,
        "second_preflight_attempt_allowed": False,
        "cloud_read_started_before_marker_fsync": False,
        "cloud_mutation_executed": False,
        "gcs_publication_count": 0,
        "cloud_submit_count": 0,
        "result_body_read": False,
        "acceptance_body_read": False,
        "realized_outcomes_read": False,
        **_authority_closure(),
    }
    return _self_hash(body, "preflight_attempt_marker_sha256")


def validate_preflight_attempt_marker_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("preflight-attempt marker must be one object")
    expected = build_preflight_attempt_marker_v1(
        implementation_source_commit_sha=str(
            value.get("implementation_source_commit_sha", "")
        ),
        reviewed_implementation_measurements=value.get(
            "reviewed_implementation_measurements", []
        ),
    )
    if _canonical(value) != _canonical(expected):
        _fail("preflight-attempt marker differs after replay")
    return expected


def focused_test_pass_count_v1(raw: bytes) -> int:
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise T230PlatformReplacementTerminalError(
            "closure focused output is not UTF-8"
        ) from exc
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    match = re.fullmatch(
        r"([1-9][0-9]*) passed in [0-9]+(?:\.[0-9]+)?s",
        lines[-1] if lines else "",
    )
    if (
        match is None
        or any(
            token in text.lower()
            for token in (" failed", " skipped", " warning", " error")
        )
    ):
        _fail("closure focused output is not one clean passing invocation")
    return int(match.group(1))


def build_terminal_closure_review_lock_v1(
    *,
    implementation_source_commit_sha: str,
    reviewed_implementation_measurements: Sequence[Mapping[str, object]],
    preflight_attempt_marker_measurement: Mapping[str, object],
    preflight_attempt_marker: Mapping[str, object],
    real_artifact_preflight_measurement: Mapping[str, object],
    real_artifact_preflight: Mapping[str, object],
    focused_test_output_measurement: Mapping[str, object],
    focused_test_collected: int,
) -> dict[str, object]:
    marker = validate_preflight_attempt_marker_v1(preflight_attempt_marker)
    preflight = validate_terminal_closure_preflight_v1(
        real_artifact_preflight,
        expected_implementation_measurements=reviewed_implementation_measurements,
    )
    implementations = [dict(row) for row in reviewed_implementation_measurements]
    marker_raw = _canonical(marker) + b"\n"
    preflight_raw = _canonical(preflight) + b"\n"
    marker_measurement = _validate_measurement(
        preflight_attempt_marker_measurement,
        relative_path=PREFLIGHT_ATTEMPT_RELATIVE_PATH,
        label="preflight-attempt marker",
    )
    preflight_measurement = _validate_measurement(
        real_artifact_preflight_measurement,
        relative_path=PREFLIGHT_RELATIVE_PATH,
        label="closure preflight",
    )
    output_measurement = _validate_measurement(
        focused_test_output_measurement,
        relative_path=FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
        label="focused test output",
    )
    if (
        implementation_source_commit_sha
        != marker["implementation_source_commit_sha"]
        or marker_measurement
        != {
            "relative_path": PREFLIGHT_ATTEMPT_RELATIVE_PATH,
            "sha256": sha256(marker_raw).hexdigest(),
            "bytes": len(marker_raw),
        }
        or preflight_measurement
        != {
            "relative_path": PREFLIGHT_RELATIVE_PATH,
            "sha256": sha256(preflight_raw).hexdigest(),
            "bytes": len(preflight_raw),
        }
        or preflight["preflight_attempt_marker_measurement"]
        != marker_measurement
        or preflight["preflight_attempt_marker_sha256"]
        != marker["preflight_attempt_marker_sha256"]
        or type(focused_test_collected) is not int
        or focused_test_collected < 1
    ):
        _fail("review-lock receipt/history binding differs")
    body = {
        "schema_version": REVIEW_LOCK_SCHEMA,
        "run_id": transport.RUN_ID,
        "source_ordinal": SOURCE_ORDINAL,
        "terminal_closure_contract_sha256": (
            frozen_terminal_closure_contract_v1()[
                "terminal_closure_contract_sha256"
            ]
        ),
        "amendment_measurement": {
            "relative_path": AMENDMENT_RELATIVE_PATH,
            "sha256": AMENDMENT_SHA256,
            "bytes": AMENDMENT_BYTES,
        },
        "current_run_panel_closure_amendment_measurement": {
            "relative_path": PANEL_CLOSURE_AMENDMENT_RELATIVE_PATH,
            "sha256": PANEL_CLOSURE_AMENDMENT_SHA256,
            "bytes": PANEL_CLOSURE_AMENDMENT_BYTES,
        },
        "implementation_source_commit_sha": implementation_source_commit_sha,
        "reviewed_implementation_measurements": implementations,
        "reviewed_implementation_measurements_sha256": (
            batch.canonical_sha256(implementations)
        ),
        "implementation_candidate_tracked_clean": True,
        "implementation_bytes_unchanged_since_review": True,
        "review_lock_must_be_tracked_in_later_clean_head": True,
        "independent_static_review_complete": True,
        "independent_static_disposition": "approve",
        "p0_count": 0,
        "p1_count": 0,
        "p2_count": 0,
        "focused_test_command": list(FOCUSED_TEST_COMMAND),
        "focused_test_invocation_count": 1,
        "focused_test_collected": focused_test_collected,
        "focused_test_passed": focused_test_collected,
        "focused_test_failed": 0,
        "focused_test_skipped": 0,
        "focused_test_warnings": 0,
        "focused_test_exit_code": 0,
        "focused_test_output_measurement": output_measurement,
        "preflight_attempt_marker_measurement": marker_measurement,
        "preflight_attempt_marker_sha256": marker[
            "preflight_attempt_marker_sha256"
        ],
        "real_artifact_preflight_measurement": preflight_measurement,
        "terminal_closure_preflight_sha256": preflight[
            "terminal_closure_preflight_sha256"
        ],
        "real_artifact_preflight_command": list(PREFLIGHT_COMMAND),
        "real_artifact_preflight_invocation_count": 1,
        "real_artifact_preflight_passed": True,
        "cloud_read_performed": True,
        "cloud_mutation_executed": False,
        "gcs_publication_count": 0,
        "cloud_submit_count": 0,
        "result_body_read": False,
        "acceptance_body_read": False,
        "realized_outcomes_read": False,
        "terminal_publication_authorized": True,
        "lane_a_closure_publication_authorized": True,
        "any_cloud_run_execution_authorized": False,
        **_authority_closure(),
    }
    return _self_hash(body, "terminal_closure_review_lock_sha256")


def validate_terminal_closure_review_lock_v1(
    value: object,
    *,
    expected_implementation_measurements: Sequence[Mapping[str, object]],
    expected_preflight_attempt_marker_measurement: Mapping[str, object],
    expected_preflight_attempt_marker: Mapping[str, object],
    expected_preflight_measurement: Mapping[str, object],
    expected_preflight: Mapping[str, object],
    expected_focused_test_output_measurement: Mapping[str, object],
    expected_focused_test_collected: int,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("terminal-closure review lock must be one object")
    expected = build_terminal_closure_review_lock_v1(
        implementation_source_commit_sha=str(
            value.get("implementation_source_commit_sha", "")
        ),
        reviewed_implementation_measurements=expected_implementation_measurements,
        preflight_attempt_marker_measurement=(
            expected_preflight_attempt_marker_measurement
        ),
        preflight_attempt_marker=expected_preflight_attempt_marker,
        real_artifact_preflight_measurement=expected_preflight_measurement,
        real_artifact_preflight=expected_preflight,
        focused_test_output_measurement=(
            expected_focused_test_output_measurement
        ),
        focused_test_collected=expected_focused_test_collected,
    )
    if _canonical(value) != _canonical(expected):
        _fail("terminal-closure review lock differs after replay")
    return expected


def reopen_terminal_closure_review_lock_v1(
    *, repository_root: Path = transport.REPOSITORY_ROOT
) -> tuple[dict[str, object], dict[str, object]]:
    """Reopen the tracked lock and prove exact local/Git equality."""
    implementations = terminal_closure_implementation_measurements_v1(
        repository_root=repository_root
    )
    amendment = _regular_file_measurement(
        repository_root, AMENDMENT_RELATIVE_PATH, label="closure amendment"
    )
    panel_amendment = _regular_file_measurement(
        repository_root,
        PANEL_CLOSURE_AMENDMENT_RELATIVE_PATH,
        label="panel closure amendment",
    )
    if amendment != {
        "relative_path": AMENDMENT_RELATIVE_PATH,
        "sha256": AMENDMENT_SHA256,
        "bytes": AMENDMENT_BYTES,
    } or panel_amendment != {
        "relative_path": PANEL_CLOSURE_AMENDMENT_RELATIVE_PATH,
        "sha256": PANEL_CLOSURE_AMENDMENT_SHA256,
        "bytes": PANEL_CLOSURE_AMENDMENT_BYTES,
    }:
        _fail("terminal-closure amendment bytes differ")
    marker_measurement = _regular_file_measurement(
        repository_root,
        PREFLIGHT_ATTEMPT_RELATIVE_PATH,
        label="preflight-attempt marker",
    )
    marker_raw = (repository_root / PREFLIGHT_ATTEMPT_RELATIVE_PATH).read_bytes()
    try:
        marker_body = transport.strict_json(
            marker_raw[:-1] if marker_raw.endswith(b"\n") else marker_raw,
            label="preflight-attempt marker",
        )
    except Exception as exc:
        raise T230PlatformReplacementTerminalError(
            "preflight-attempt marker JSON differs"
        ) from exc
    if marker_raw != _canonical(marker_body) + b"\n":
        _fail("preflight-attempt marker canonical bytes differ")
    marker = validate_preflight_attempt_marker_v1(marker_body)
    preflight_measurement = _regular_file_measurement(
        repository_root, PREFLIGHT_RELATIVE_PATH, label="closure preflight"
    )
    preflight_raw = (repository_root / PREFLIGHT_RELATIVE_PATH).read_bytes()
    try:
        preflight_body = transport.strict_json(
            preflight_raw[:-1] if preflight_raw.endswith(b"\n") else preflight_raw,
            label="closure preflight",
        )
    except Exception as exc:
        raise T230PlatformReplacementTerminalError(
            "terminal-closure preflight JSON differs"
        ) from exc
    if preflight_raw != _canonical(preflight_body) + b"\n":
        _fail("terminal-closure preflight canonical bytes differ")
    validate_terminal_closure_preflight_v1(
        preflight_body,
        expected_implementation_measurements=implementations,
    )
    lock_measurement = _regular_file_measurement(
        repository_root, REVIEW_LOCK_RELATIVE_PATH, label="closure review lock"
    )
    raw = (repository_root / REVIEW_LOCK_RELATIVE_PATH).read_bytes()
    try:
        lock = transport.strict_json(
            raw[:-1] if raw.endswith(b"\n") else raw,
            label="closure review lock",
        )
    except Exception as exc:
        raise T230PlatformReplacementTerminalError(
            "terminal-closure review lock JSON differs"
        ) from exc
    canonical = _canonical(lock)
    if raw != canonical + b"\n":
        _fail("terminal-closure review lock canonical bytes differ")
    focused_output_measurement = _regular_file_measurement(
        repository_root,
        FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
        label="closure focused output",
    )
    focused_test_collected = focused_test_pass_count_v1(
        (repository_root / FOCUSED_TEST_OUTPUT_RELATIVE_PATH).read_bytes()
    )
    retained = validate_terminal_closure_review_lock_v1(
        lock,
        expected_implementation_measurements=implementations,
        expected_preflight_attempt_marker_measurement=marker_measurement,
        expected_preflight_attempt_marker=marker,
        expected_preflight_measurement=preflight_measurement,
        expected_preflight=preflight_body,
        expected_focused_test_output_measurement=focused_output_measurement,
        expected_focused_test_collected=focused_test_collected,
    )
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.decode("ascii").strip()
    except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        raise T230PlatformReplacementTerminalError(
            "terminal-closure Git HEAD read failed"
        ) from exc
    scoped_paths = [
        *(
            row["relative_path"]
            for row in implementations
        ),
        AMENDMENT_RELATIVE_PATH,
        PANEL_CLOSURE_AMENDMENT_RELATIVE_PATH,
        PREFLIGHT_ATTEMPT_RELATIVE_PATH,
        PREFLIGHT_RELATIVE_PATH,
        FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
        REVIEW_LOCK_RELATIVE_PATH,
    ]
    try:
        status = subprocess.run(
            [
                "git",
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                *scoped_paths,
            ],
            cwd=repository_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise T230PlatformReplacementTerminalError(
            "terminal-closure Git status read failed"
        ) from exc
    if (
        head == retained["implementation_source_commit_sha"]
        or status != b""
    ):
        _fail("terminal-closure tracked HEAD is not exact and clean")
    verify_terminal_closure_implementation_commit_v1(
        implementation_source_commit_sha=str(
            retained["implementation_source_commit_sha"]
        ),
        expected_implementation_measurements=implementations,
        repository_root=repository_root,
    )
    for measurement in [
        *implementations,
        amendment,
        panel_amendment,
        marker_measurement,
        preflight_measurement,
        focused_output_measurement,
        lock_measurement,
    ]:
        try:
            committed = subprocess.run(
                [
                    "git",
                    "show",
                    f"{head}:{measurement['relative_path']}",
                ],
                cwd=repository_root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as exc:
            raise T230PlatformReplacementTerminalError(
                "terminal-closure committed-byte replay failed"
            ) from exc
        local = (repository_root / str(measurement["relative_path"])).read_bytes()
        if committed != local:
            _fail("terminal-closure local bytes differ from committed bytes")
    return lock_measurement, retained


def _validate_ownership_body(
    value: object, *, intent: Mapping[str, object]
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("replacement ownership must be one object")
    item = dict(value)
    _validate_self_hash(
        item, field="launch_ownership_sha256", label="replacement ownership"
    )
    _false_authorities(item, label="replacement ownership")
    if (
        item.get("schema_version")
        != "foundry-t230-ordinal-6-replacement-worker-launch-ownership/v1"
        or item.get("run_id") != transport.RUN_ID
        or item.get("operation") != replacement.OPERATION
        or item.get("source_ordinal") != SOURCE_ORDINAL
        or item.get("runtime_attempt_ordinal") != 1
        or item.get("replacement_intent_identity")
        != dict(REPLACEMENT_INTENT_IDENTITY)
        or item.get("replacement_intent") != dict(intent)
        or item.get("platform_replacement_intent_sha256")
        != intent.get("platform_replacement_intent_sha256")
        or item.get("cloud_execution_name") != REPLACEMENT_EXECUTION
        or item.get("reuse_job") != replacement.REUSE_JOB
        or item.get("immutable_image")
        != replacement.frozen_platform_replacement_contract_v1()[
            "immutable_image"
        ]
        or item.get("submission_returncode") != 0
        or item.get("intent_created_by_this_process") is not True
        or item.get("first_creator_submitted") is not True
        or item.get("submission_call_count") != 1
        or item.get("request_consumed") is not True
        or item.get("automatic_resubmission_allowed") is not False
        or item.get("second_replacement_allowed") is not False
        or item.get("result_or_effect_content_inspected_before_submission")
        is not False
    ):
        _fail("replacement ownership frozen surface differs")
    projection = item.get("submitted_execution_projection")
    if (
        not isinstance(projection, Mapping)
        or projection.get("execution_name") != REPLACEMENT_EXECUTION
        or projection.get("job") != replacement.REUSE_JOB
        or projection.get("image") != replacement.FROZEN_D2_URI
        or projection.get("service_account") != replacement.SERVICE_ACCOUNT
        or projection.get("cpu") != "8"
        or projection.get("memory") != "32Gi"
        or projection.get("task_count") != 1
        or projection.get("parallelism") != 1
        or projection.get("max_retries") != 0
        or projection.get("task_timeout_seconds")
        != transport.TASK_TIMEOUT_SECONDS
        or projection.get("full_execution_envelope_exactly_validated")
        is not True
        or item.get("submitted_execution_projection_sha256")
        != batch.canonical_sha256(projection)
    ):
        _fail("replacement ownership submitted envelope differs")
    return item


def _submitted_semantic_projection(value: Mapping[str, object]) -> dict[str, object]:
    excluded = {
        "schema_version",
        "full_execution_envelope_exactly_validated",
        "worker_launch_plan_sha256",
        "execution_flags_sha256",
        "describe_argv",
        "describe_stdout_sha256",
        "describe_stdout_bytes",
    }
    return {key: retained for key, retained in value.items() if key not in excluded}


def _validate_stage_start_body(
    value: object, *, ownership: Mapping[str, object]
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("replacement stage start must be one object")
    item = dict(value)
    _validate_self_hash(
        item,
        field="replacement_stage_start_sha256",
        label="replacement stage start",
    )
    _false_authorities(item, label="replacement stage start")
    if (
        item.get("schema_version")
        != "foundry-t230-ordinal-6-replacement-worker-stage-start/v1"
        or item.get("run_id") != transport.RUN_ID
        or item.get("operation") != replacement.OPERATION
        or item.get("source_ordinal") != SOURCE_ORDINAL
        or item.get("runtime_attempt_ordinal") != 1
        or item.get("launch_ownership_identity")
        != dict(REPLACEMENT_OWNERSHIP_IDENTITY)
        or item.get("launch_ownership") != dict(ownership)
        or item.get("launch_ownership_sha256")
        != ownership.get("launch_ownership_sha256")
        or item.get("cloud_execution_name") != REPLACEMENT_EXECUTION
        or item.get("cloud_job") != replacement.REUSE_JOB
        or item.get("immutable_image")
        != replacement.frozen_platform_replacement_contract_v1()[
            "immutable_image"
        ]
        or item.get("replacement_stage_start_uri")
        != replacement.REPLACEMENT_STAGE_START_URI
        or item.get("core_execution_requires_handshake") is not True
        or item.get("published_after_exact_async_submission_response")
        is not True
        or item.get("task_count") != 1
        or item.get("parallelism") != 1
        or item.get("max_retries") != 0
        or item.get("automatic_resubmission_allowed") is not False
        or item.get("original_launch_request_reused") is not False
        or item.get("primary_runtime_attempt_reused") is not False
    ):
        _fail("replacement stage-start frozen surface differs")
    return item


def reopen_replacement_launch_lineage_v1(
    *, backend: transport.JournalBackend
) -> dict[str, object]:
    """Exact-replay the three mechanics objects; no result is opened."""
    intent_identity, intent_body, _ = _exact_read_json(
        backend,
        REPLACEMENT_INTENT_IDENTITY,
        label="replacement intent",
    )
    try:
        intent = replacement.validate_platform_replacement_intent_v1(intent_body)
    except Exception as exc:
        raise T230PlatformReplacementTerminalError(
            "replacement intent exact replay failed"
        ) from exc
    ownership_identity, ownership_body, _ = _exact_read_json(
        backend,
        REPLACEMENT_OWNERSHIP_IDENTITY,
        label="replacement launch ownership",
    )
    ownership = _validate_ownership_body(ownership_body, intent=intent)
    start_identity, start_body, _ = _exact_read_json(
        backend,
        REPLACEMENT_STAGE_START_IDENTITY,
        label="replacement stage start",
    )
    start = _validate_stage_start_body(start_body, ownership=ownership)
    return {
        "replacement_intent_identity": intent_identity,
        "platform_replacement_intent_sha256": intent[
            "platform_replacement_intent_sha256"
        ],
        "replacement_launch_ownership_identity": ownership_identity,
        "launch_ownership_sha256": ownership["launch_ownership_sha256"],
        "replacement_stage_start_identity": start_identity,
        "replacement_stage_start_sha256": start[
            "replacement_stage_start_sha256"
        ],
        "replacement_execution": REPLACEMENT_EXECUTION,
        "replacement_submitted_execution_semantic_sha256": (
            batch.canonical_sha256(
                _submitted_semantic_projection(
                    ownership["submitted_execution_projection"]
                )
            )
        ),
        "lineage_exactly_replayed": True,
        "result_or_effect_content_inspected": False,
        "realized_outcomes_read": False,
    }


_TERMINAL_PROJECTION_KEYS: Final = frozenset({
    "schema_version",
    "execution_name",
    "task_name",
    "job",
    "completed_status",
    "completed_reason",
    "completed_message",
    "execution_status_keys",
    "execution_conditions",
    "start_time",
    "completion_time",
    "failed_count",
    "succeeded_count_present",
    "succeeded_count",
    "cancelled_count_present",
    "cancelled_count",
    "execution_observed_generation",
    "log_uri",
    "log_content_read",
    "task_api_version",
    "task_kind",
    "task_namespace",
    "task_resource_version",
    "task_self_link",
    "task_creation_time",
    "task_scheduled_time",
    "task_start_time",
    "task_completion_time",
    "task_running_state",
    "task_spec",
    "task_completed_condition",
    "task_started_condition",
    "task_last_attempt_result",
    "task_observed_generation",
    "execution_envelope",
    "execution_describe_argv",
    "execution_describe_stdout_sha256",
    "execution_describe_stdout_bytes",
    "task_describe_argv",
    "task_describe_stdout_sha256",
    "task_describe_stdout_bytes",
    "terminal_exactly_validated",
    "result_or_effect_content_inspected",
    "realized_outcomes_read",
})


def validate_replacement_failure_projection_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("replacement terminal projection must be one object")
    item = dict(value)
    if set(item) != _TERMINAL_PROJECTION_KEYS:
        _fail("replacement terminal projection fields differ")
    envelope = item.get("execution_envelope")
    if not isinstance(envelope, Mapping):
        _fail("replacement terminal envelope differs")
    if (
        item.get("schema_version") != TERMINAL_PROJECTION_SCHEMA
        or item.get("execution_name") != REPLACEMENT_EXECUTION
        or item.get("task_name") != REPLACEMENT_TASK
        or item.get("job") != replacement.REUSE_JOB
        or item.get("completed_status") != "False"
        or item.get("completed_reason") != TASK_REASON
        or item.get("completed_message") != EXECUTION_COMPLETED_MESSAGE
        or item.get("execution_status_keys")
        != [
            "completionTime",
            "conditions",
            "failedCount",
            "logUri",
            "observedGeneration",
            "startTime",
        ]
        or item.get("execution_conditions") != EXECUTION_CONDITIONS
        or item.get("start_time") != REPLACEMENT_STARTED_TIME
        or item.get("completion_time") != REPLACEMENT_COMPLETION_TIME
        or item.get("failed_count") != 1
        or item.get("succeeded_count_present") is not False
        or item.get("succeeded_count") != 0
        or item.get("cancelled_count_present") is not False
        or item.get("cancelled_count") != 0
        or item.get("execution_observed_generation") != 1
        or not isinstance(item.get("log_uri"), str)
        or not str(item["log_uri"])
        or item.get("log_content_read") is not False
        or item.get("task_api_version") != "run.googleapis.com/v1"
        or item.get("task_kind") != "Task"
        or item.get("task_namespace") != "817589974517"
        or item.get("task_resource_version") != "AAZZ7FoYxOc"
        or item.get("task_self_link")
        != (
            "/apis/run.googleapis.com/v1/namespaces/817589974517/tasks/"
            "atlas-minimal-c-s2023-w1-v1-67669-task0"
        )
        or item.get("task_creation_time") != TASK_CREATION_TIME
        or item.get("task_scheduled_time") != REPLACEMENT_STARTED_TIME
        or item.get("task_start_time") != TASK_START_TIME
        or item.get("task_completion_time") != TASK_COMPLETION_TIME
        or item.get("task_running_state") != "Failed"
        or item.get("task_spec") != {}
        or item.get("task_completed_condition")
        != {
            "message": TASK_MESSAGE,
            "reason": TASK_REASON,
            "status": "False",
            "type": "Completed",
        }
        or item.get("task_started_condition")
        != {"status": "True", "type": "Started"}
        or item.get("task_last_attempt_result")
        != {
            "exitCode": 1,
            "status": {"code": 10, "message": TASK_MESSAGE},
        }
        or item.get("task_observed_generation") != 1
        or envelope.get("execution_name") != REPLACEMENT_EXECUTION
        or envelope.get("job") != replacement.REUSE_JOB
        or envelope.get("image") != replacement.FROZEN_D2_URI
        or envelope.get("service_account") != replacement.SERVICE_ACCOUNT
        or envelope.get("cpu") != "8"
        or envelope.get("memory") != "32Gi"
        or envelope.get("task_count") != 1
        or envelope.get("parallelism") != 1
        or envelope.get("max_retries") != 0
        or envelope.get("task_timeout_seconds")
        != transport.TASK_TIMEOUT_SECONDS
        or set(envelope)
        != {
            "execution_name",
            "job",
            "image",
            "service_account",
            "cpu",
            "memory",
            "task_count",
            "parallelism",
            "max_retries",
            "task_timeout_seconds",
            "command",
            "args",
            "configured_environment",
            "runtime_evidence_volume",
        }
        or not isinstance(envelope.get("command"), list)
        or not isinstance(envelope.get("args"), list)
        or not isinstance(envelope.get("configured_environment"), Mapping)
        or not isinstance(envelope.get("runtime_evidence_volume"), Mapping)
        or item.get("execution_describe_argv")
        != list(EXECUTION_DESCRIBE_ARGV)
        or item.get("task_describe_argv") != list(TASK_DESCRIBE_ARGV)
        or item.get("terminal_exactly_validated") is not True
        or item.get("result_or_effect_content_inspected") is not False
        or item.get("realized_outcomes_read") is not False
    ):
        _fail("replacement terminal literals/envelope differ")
    for field in (
        "execution_describe_stdout_sha256",
        "task_describe_stdout_sha256",
    ):
        if not isinstance(item.get(field), str) or _SHA256.fullmatch(
            str(item[field])
        ) is None:
            _fail("replacement terminal describe hash differs")
    for field in (
        "execution_describe_stdout_bytes",
        "task_describe_stdout_bytes",
    ):
        if type(item.get(field)) is not int or int(item[field]) < 1:
            _fail("replacement terminal describe bytes differ")
    return item


def _metadata_row(value: object, *, expected_uri: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("surface metadata row must be one object")
    item = dict(value)
    expected_keys = {
        "uri",
        "present",
        "generation",
        "size",
        "crc32c",
        "etag",
        "content_type",
        "content_inspected",
    }
    if set(item) != expected_keys or item.get("uri") != expected_uri:
        _fail("surface metadata row fields/URI differ")
    if item.get("content_inspected") is not False:
        _fail("surface metadata content was inspected")
    if item.get("present") is False:
        if any(
            item.get(field) is not None
            for field in ("generation", "size", "crc32c", "etag", "content_type")
        ):
            _fail("absent surface carries presence metadata")
    elif item.get("present") is True:
        if (
            not isinstance(item.get("generation"), str)
            or not str(item["generation"]).isdigit()
            or type(item.get("size")) is not int
            or int(item["size"]) < 1
            or not isinstance(item.get("crc32c"), str)
            or _CRC32C.fullmatch(str(item["crc32c"])) is None
            or not isinstance(item.get("etag"), str)
            or not str(item["etag"])
            or not isinstance(item.get("content_type"), str)
        ):
            _fail("present surface metadata differs")
    else:
        _fail("surface metadata presence differs")
    return item


def terminal_surface_uris_v1() -> list[str]:
    contract = replacement.frozen_platform_replacement_contract_v1()
    rows = list(contract["absent_effect_surface_uris"])
    rows.append(replacement.REPLACEMENT_INTENT_URI)
    # Intent/ownership/start are expected present and handled as exact lineage,
    # not part of the effect census.  The terminal itself is absent precreate.
    excluded = {
        replacement.REPLACEMENT_INTENT_URI,
        replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI,
        replacement.REPLACEMENT_STAGE_START_URI,
    }
    ordered = [uri for uri in rows if uri not in excluded]
    if replacement.REPLACEMENT_EXECUTION_TERMINAL_URI not in ordered:
        ordered.append(replacement.REPLACEMENT_EXECUTION_TERMINAL_URI)
    return list(dict.fromkeys(ordered))


def lane_a_terminal_surface_uris_v1() -> list[str]:
    """Exact post-terminal surface: terminal present, every other effect absent."""
    ordered = [
        uri
        for uri in terminal_surface_uris_v1()
        if uri != replacement.REPLACEMENT_EXECUTION_TERMINAL_URI
    ]
    ordered.append(transport.lane_ledger_uri(0))
    for ordinal in range(6, 28):
        ordered.extend(
            [
                transport.TRANSPORT_PREFIX
                + f"stages/run-slate/{ordinal:02d}.json",
                transport.TRANSPORT_PREFIX
                + f"stages/verify-slate/{ordinal:02d}.json",
            ]
        )
    retained = list(dict.fromkeys(ordered))
    if (
        replacement.REPLACEMENT_EXECUTION_TERMINAL_URI in retained
        or replacement.SUPPLEMENTAL_LANE_ROOT_URI not in retained
        or replacement.SUPPLEMENTAL_PANEL_ROOT_URI not in retained
    ):
        _fail("Lane-A post-terminal surface construction differs")
    return retained


def build_surface_census_v1(
    *, rows: Sequence[Mapping[str, object]], pass_ordinal: int
) -> dict[str, object]:
    uris = terminal_surface_uris_v1()
    if pass_ordinal not in {1, 2} or len(rows) != len(uris):
        _fail("surface census cardinality/pass differs")
    retained = [
        _metadata_row(row, expected_uri=uri)
        for row, uri in zip(rows, uris, strict=True)
    ]
    by_uri = {row["uri"]: row for row in retained}
    # The exact post-failure metadata census established that neither the
    # result nor attempt-1 runtime exists.  Any later presence changes the
    # frozen terminal surface and must be separately amended, never silently
    # normalized into this closure.
    required_absent = set(uris)
    if any(by_uri[uri]["present"] is not False for uri in required_absent):
        _fail("post-worker effect/closure surface is already present")
    body = {
        "schema_version": SURFACE_CENSUS_SCHEMA,
        "run_id": transport.RUN_ID,
        "source_ordinal": SOURCE_ORDINAL,
        "replacement_execution": REPLACEMENT_EXECUTION,
        "pass_ordinal": pass_ordinal,
        "rows": retained,
        "rows_sha256": batch.canonical_sha256(retained),
        "probe_count": len(retained),
        "required_absence_count": len(required_absent),
        "required_effect_surface_absent": True,
        "result_content_inspected": False,
        "acceptance_content_inspected": False,
        "realized_outcomes_read": False,
        "bucket_list_used": False,
    }
    return _self_hash(body, "surface_census_sha256")


def validate_surface_census_v1(value: object, *, pass_ordinal: int) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("surface census must be one object")
    rows = value.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        _fail("surface census rows differ")
    expected = build_surface_census_v1(rows=rows, pass_ordinal=pass_ordinal)
    if _canonical(value) != _canonical(expected):
        _fail("surface census differs after replay")
    return expected


def build_lane_a_surface_census_v1(
    *, rows: Sequence[Mapping[str, object]], pass_ordinal: int
) -> dict[str, object]:
    uris = lane_a_terminal_surface_uris_v1()
    if pass_ordinal not in {1, 2} or len(rows) != len(uris):
        _fail("Lane-A surface census cardinality/pass differs")
    retained = [
        _metadata_row(row, expected_uri=uri)
        for row, uri in zip(rows, uris, strict=True)
    ]
    if any(row["present"] is not False for row in retained):
        _fail("post-terminal Lane-A effect/incomplete surface exists")
    body = {
        "schema_version": LANE_A_SURFACE_CENSUS_SCHEMA,
        "run_id": transport.RUN_ID,
        "lane_ordinal": 0,
        "source_ordinal": SOURCE_ORDINAL,
        "replacement_execution": REPLACEMENT_EXECUTION,
        "pass_ordinal": pass_ordinal,
        "rows": retained,
        "rows_sha256": batch.canonical_sha256(retained),
        "probe_count": len(retained),
        "required_absence_count": len(retained),
        "all_post_terminal_effect_and_incomplete_surfaces_absent": True,
        "replacement_execution_terminal_expected_present_separately": True,
        "result_content_inspected": False,
        "acceptance_content_inspected": False,
        "realized_outcomes_read": False,
        "bucket_list_used": False,
    }
    return _self_hash(body, "lane_a_surface_census_sha256")


def validate_lane_a_surface_census_v1(
    value: object, *, pass_ordinal: int
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("Lane-A surface census must be one object")
    rows = value.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        _fail("Lane-A surface census rows differ")
    expected = build_lane_a_surface_census_v1(
        rows=rows, pass_ordinal=pass_ordinal
    )
    if _canonical(value) != _canonical(expected):
        _fail("Lane-A surface census differs after replay")
    return expected


def build_terminal_closure_preflight_v1(
    *,
    launch_lineage: Mapping[str, object],
    terminal_projection: Mapping[str, object],
    first_census: Mapping[str, object],
    second_census: Mapping[str, object],
    reviewed_implementation_measurements: Sequence[Mapping[str, object]],
    preflight_attempt_marker_measurement: Mapping[str, object],
    preflight_attempt_marker: Mapping[str, object],
) -> dict[str, object]:
    terminal = validate_replacement_failure_projection_v1(terminal_projection)
    census_one = validate_surface_census_v1(first_census, pass_ordinal=1)
    census_two = validate_surface_census_v1(second_census, pass_ordinal=2)
    expected_lineage_keys = {
        "replacement_intent_identity",
        "platform_replacement_intent_sha256",
        "replacement_launch_ownership_identity",
        "launch_ownership_sha256",
        "replacement_stage_start_identity",
        "replacement_stage_start_sha256",
        "replacement_execution",
        "replacement_submitted_execution_semantic_sha256",
        "lineage_exactly_replayed",
        "result_or_effect_content_inspected",
        "realized_outcomes_read",
    }
    if (
        not isinstance(launch_lineage, Mapping)
        or set(launch_lineage) != expected_lineage_keys
        or launch_lineage.get("replacement_intent_identity")
        != dict(REPLACEMENT_INTENT_IDENTITY)
        or launch_lineage.get("replacement_launch_ownership_identity")
        != dict(REPLACEMENT_OWNERSHIP_IDENTITY)
        or launch_lineage.get("replacement_stage_start_identity")
        != dict(REPLACEMENT_STAGE_START_IDENTITY)
        or any(
            not isinstance(launch_lineage.get(field), str)
            or _SHA256.fullmatch(str(launch_lineage[field])) is None
            for field in (
                "platform_replacement_intent_sha256",
                "launch_ownership_sha256",
                "replacement_stage_start_sha256",
            )
        )
        or launch_lineage.get("replacement_execution") != REPLACEMENT_EXECUTION
        or launch_lineage.get("replacement_submitted_execution_semantic_sha256")
        != batch.canonical_sha256(terminal["execution_envelope"])
        or launch_lineage.get("lineage_exactly_replayed") is not True
        or launch_lineage.get("result_or_effect_content_inspected") is not False
        or launch_lineage.get("realized_outcomes_read") is not False
    ):
        _fail("preflight launch lineage differs")
    paths = (
        IMPLEMENTATION_RELATIVE_PATH,
        TEST_RELATIVE_PATH,
        CONTROLLER_RELATIVE_PATH,
        CONTROLLER_TEST_RELATIVE_PATH,
    )
    if (
        not isinstance(reviewed_implementation_measurements, Sequence)
        or isinstance(reviewed_implementation_measurements, (str, bytes))
        or len(reviewed_implementation_measurements) != len(paths)
    ):
        _fail("preflight implementation measurement cardinality differs")
    implementations = [
        _validate_measurement(
            row, relative_path=path, label=f"preflight implementation[{ordinal}]"
        )
        for ordinal, (row, path) in enumerate(
            zip(reviewed_implementation_measurements, paths, strict=True)
        )
    ]
    marker = validate_preflight_attempt_marker_v1(preflight_attempt_marker)
    marker_raw = _canonical(marker) + b"\n"
    expected_marker_measurement = {
        "relative_path": PREFLIGHT_ATTEMPT_RELATIVE_PATH,
        "sha256": sha256(marker_raw).hexdigest(),
        "bytes": len(marker_raw),
    }
    if (
        dict(preflight_attempt_marker_measurement)
        != expected_marker_measurement
        or marker["reviewed_implementation_measurements"] != implementations
    ):
        _fail("preflight-attempt marker binding differs")
    body = {
        "schema_version": PREFLIGHT_SCHEMA,
        "run_id": transport.RUN_ID,
        "source_ordinal": SOURCE_ORDINAL,
        "terminal_closure_contract": frozen_terminal_closure_contract_v1(),
        "amendment_measurement": {
            "relative_path": AMENDMENT_RELATIVE_PATH,
            "sha256": AMENDMENT_SHA256,
            "bytes": AMENDMENT_BYTES,
        },
        "current_run_panel_closure_amendment_measurement": {
            "relative_path": PANEL_CLOSURE_AMENDMENT_RELATIVE_PATH,
            "sha256": PANEL_CLOSURE_AMENDMENT_SHA256,
            "bytes": PANEL_CLOSURE_AMENDMENT_BYTES,
        },
        "reviewed_implementation_measurements": implementations,
        "reviewed_implementation_measurements_sha256": (
            batch.canonical_sha256(implementations)
        ),
        "implementation_source_commit_sha": marker[
            "implementation_source_commit_sha"
        ],
        "preflight_attempt_marker_measurement": expected_marker_measurement,
        "preflight_attempt_marker": marker,
        "preflight_attempt_marker_sha256": marker[
            "preflight_attempt_marker_sha256"
        ],
        "command": list(PREFLIGHT_COMMAND),
        "invocation_count": 1,
        "cloud_read_commands": [
            list(EXECUTION_DESCRIBE_ARGV),
            list(TASK_DESCRIBE_ARGV),
        ],
        "cloud_read_command_count": 2,
        "launch_lineage": dict(launch_lineage),
        "terminal_projection": terminal,
        "terminal_projection_sha256": batch.canonical_sha256(terminal),
        "first_surface_census": census_one,
        "second_surface_census": census_two,
        "metadata_probe_count": (
            int(census_one["probe_count"]) + int(census_two["probe_count"])
        ),
        "replacement_failed": True,
        "replacement_exhausted": True,
        "preflight_passed": True,
        "cloud_read_performed": True,
        "cloud_mutation_executed": False,
        "gcs_publication_count": 0,
        "cloud_submit_count": 0,
        "result_body_read": False,
        "acceptance_body_read": False,
        "realized_outcomes_read": False,
        **_authority_closure(),
    }
    return _self_hash(body, "terminal_closure_preflight_sha256")


def validate_terminal_closure_preflight_v1(
    value: object,
    *,
    expected_implementation_measurements: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("terminal-closure preflight must be one object")
    expected = build_terminal_closure_preflight_v1(
        launch_lineage=value.get("launch_lineage", {}),
        terminal_projection=value.get("terminal_projection", {}),
        first_census=value.get("first_surface_census", {}),
        second_census=value.get("second_surface_census", {}),
        reviewed_implementation_measurements=value.get(
            "reviewed_implementation_measurements", []
        ),
        preflight_attempt_marker_measurement=value.get(
            "preflight_attempt_marker_measurement", {}
        ),
        preflight_attempt_marker=value.get("preflight_attempt_marker", {}),
    )
    if _canonical(value) != _canonical(expected):
        _fail("terminal-closure preflight differs after replay")
    if (
        expected_implementation_measurements is not None
        and list(expected["reviewed_implementation_measurements"])
        != [dict(row) for row in expected_implementation_measurements]
    ):
        _fail("terminal-closure preflight current implementations differ")
    return expected


def build_replacement_execution_terminal_v1(
    *,
    preflight_measurement: Mapping[str, object],
    preflight: Mapping[str, object],
    review_lock_measurement: Mapping[str, object],
    review_lock_sha256: str,
) -> dict[str, object]:
    retained = validate_terminal_closure_preflight_v1(preflight)
    raw = _canonical(retained)
    tracked_raw = raw + b"\n"
    expected_preflight_measurement = {
        "relative_path": PREFLIGHT_RELATIVE_PATH,
        "sha256": sha256(tracked_raw).hexdigest(),
        "bytes": len(tracked_raw),
    }
    if (
        not isinstance(preflight_measurement, Mapping)
        or dict(preflight_measurement) != expected_preflight_measurement
    ):
        _fail("closure preflight measurement differs")
    if not isinstance(review_lock_measurement, Mapping):
        _fail("closure review-lock measurement differs")
    lock_measurement = dict(review_lock_measurement)
    if (
        set(lock_measurement) != {"relative_path", "sha256", "bytes"}
        or lock_measurement.get("relative_path") != REVIEW_LOCK_RELATIVE_PATH
        or not isinstance(lock_measurement.get("sha256"), str)
        or _SHA256.fullmatch(str(lock_measurement["sha256"])) is None
        or type(lock_measurement.get("bytes")) is not int
        or int(lock_measurement["bytes"]) < 1
    ):
        _fail("closure review-lock measurement differs")
    if not isinstance(review_lock_sha256, str) or _SHA256.fullmatch(
        review_lock_sha256
    ) is None:
        _fail("closure review-lock self-hash differs")
    body = {
        "schema_version": RECOVERY_TERMINAL_SCHEMA,
        "run_id": transport.RUN_ID,
        "source_ordinal": SOURCE_ORDINAL,
        "replacement_execution": REPLACEMENT_EXECUTION,
        "terminal_closure_contract_sha256": (
            frozen_terminal_closure_contract_v1()[
                "terminal_closure_contract_sha256"
            ]
        ),
        "preflight_measurement": expected_preflight_measurement,
        "preflight": retained,
        "terminal_closure_preflight_sha256": retained[
            "terminal_closure_preflight_sha256"
        ],
        "review_lock_measurement": lock_measurement,
        "review_lock_sha256": review_lock_sha256,
        "launch_lineage": retained["launch_lineage"],
        "terminal_projection": retained["terminal_projection"],
        "first_surface_census": retained["first_surface_census"],
        "second_surface_census": retained["second_surface_census"],
        "replacement_worker_execution_count": 1,
        "replacement_worker_execution_limit": 1,
        "request_consumed": True,
        "replacement_failed": True,
        "replacement_exhausted": True,
        "second_replacement_allowed": False,
        "bridge_verifier_allowed": False,
        "ordinal_seven_may_resume": False,
        "current_panel_terminal_invalid": True,
        "result_body_read": False,
        "acceptance_body_read": False,
        "realized_outcomes_read": False,
        **_authority_closure(),
    }
    return _self_hash(body, "replacement_execution_terminal_sha256")


def validate_replacement_execution_terminal_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("replacement execution terminal must be one object")
    expected = build_replacement_execution_terminal_v1(
        preflight_measurement=value.get("preflight_measurement", {}),
        preflight=value.get("preflight", {}),
        review_lock_measurement=value.get("review_lock_measurement", {}),
        review_lock_sha256=str(value.get("review_lock_sha256", "")),
    )
    if _canonical(value) != _canonical(expected):
        _fail("replacement execution terminal differs after replay")
    return expected


def build_lane_a_terminal_invalid_root_v1(
    *,
    recovery_terminal_identity: Mapping[str, object],
    recovery_terminal: Mapping[str, object],
    completed_worker_stage_identities: Sequence[Mapping[str, object]],
    completed_verifier_stage_identities: Sequence[Mapping[str, object]],
    completed_acceptance_identities: Sequence[Mapping[str, object]],
    first_lane_a_surface_census: Mapping[str, object],
    second_lane_a_surface_census: Mapping[str, object],
) -> dict[str, object]:
    terminal = validate_replacement_execution_terminal_v1(recovery_terminal)
    terminal_id = _identity(
        recovery_terminal_identity, label="replacement recovery terminal"
    )
    terminal_raw = _canonical(terminal)
    if (
        terminal_id["uri"] != replacement.REPLACEMENT_EXECUTION_TERMINAL_URI
        or terminal_id["sha256"] != sha256(terminal_raw).hexdigest()
        or terminal_id["bytes"] != len(terminal_raw)
    ):
        _fail("replacement recovery terminal identity differs")
    if not all(
        isinstance(rows, Sequence) and not isinstance(rows, (str, bytes))
        for rows in (
            completed_worker_stage_identities,
            completed_verifier_stage_identities,
            completed_acceptance_identities,
        )
    ):
        _fail("Lane-A completed identity lists differ")
    workers = [
        _identity(value, label=f"completed worker stage[{ordinal}]")
        for ordinal, value in enumerate(completed_worker_stage_identities)
    ]
    verifiers = [
        _identity(value, label=f"completed verifier stage[{ordinal}]")
        for ordinal, value in enumerate(completed_verifier_stage_identities)
    ]
    acceptances = [
        _identity(value, label=f"completed acceptance[{ordinal}]")
        for ordinal, value in enumerate(completed_acceptance_identities)
    ]
    if len(workers) != 6 or len(verifiers) != 6 or len(acceptances) != 6:
        _fail("Lane-A closure must bind exactly ordinals 0 through 5")
    census_one = validate_lane_a_surface_census_v1(
        first_lane_a_surface_census, pass_ordinal=1
    )
    census_two = validate_lane_a_surface_census_v1(
        second_lane_a_surface_census, pass_ordinal=2
    )
    expected_worker_uris = [
        transport.TRANSPORT_PREFIX + f"stages/run-slate/{ordinal:02d}.json"
        for ordinal in range(6)
    ]
    expected_verifier_uris = [
        transport.TRANSPORT_PREFIX + f"stages/verify-slate/{ordinal:02d}.json"
        for ordinal in range(6)
    ]
    # The acceptance URI is checked by its canonical suffix rather than the
    # unavailable result member projection in this closure-only layer.
    if (
        [row["uri"] for row in workers] != expected_worker_uris
        or [row["uri"] for row in verifiers] != expected_verifier_uris
        or any(
            not str(row["uri"]).startswith(transport.OUTPUT_PREFIX + "slates/")
            or not str(row["uri"]).endswith(
                "/foundry-t230-slate-acceptance-v1.json"
            )
            for row in acceptances
        )
        or len({row["uri"] for row in acceptances}) != 6
    ):
        _fail("Lane-A completed identity URI order differs")
    body = {
        "schema_version": LANE_A_CLOSURE_SCHEMA,
        "run_id": transport.RUN_ID,
        "lane_ordinal": 0,
        "required_source_ordinals": list(range(28)),
        "completed_source_ordinals": list(range(6)),
        "first_incomplete_source_ordinal": 6,
        "completed_acceptance_count": 6,
        "required_acceptance_count": 28,
        "completed_worker_stage_identities": workers,
        "completed_verifier_stage_identities": verifiers,
        "completed_acceptance_identities": acceptances,
        "first_post_terminal_surface_census": census_one,
        "second_post_terminal_surface_census": census_two,
        "replacement_recovery_terminal_identity": terminal_id,
        "replacement_recovery_terminal": terminal,
        "replacement_execution_terminal_sha256": terminal[
            "replacement_execution_terminal_sha256"
        ],
        "primary_execution": replacement.FAILED_EXECUTION,
        "replacement_execution": REPLACEMENT_EXECUTION,
        "canonical_lane_a_ledger_present": False,
        "lane_complete": False,
        "lane_terminal_invalid": True,
        "panel_terminal_invalid": True,
        "ordinal_seven_may_resume": False,
        "bridge_verifier_allowed": False,
        "second_replacement_allowed": False,
        "joint_panel_root_published": False,
        "result_body_read": False,
        "acceptance_body_read": False,
        "realized_outcomes_read": False,
        **_authority_closure(),
    }
    return _self_hash(body, "lane_a_terminal_invalid_root_sha256")


def validate_lane_a_terminal_invalid_root_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("Lane-A terminal-invalid root must be one object")
    expected = build_lane_a_terminal_invalid_root_v1(
        recovery_terminal_identity=value.get(
            "replacement_recovery_terminal_identity", {}
        ),
        recovery_terminal=value.get("replacement_recovery_terminal", {}),
        completed_worker_stage_identities=value.get(
            "completed_worker_stage_identities", []
        ),
        completed_verifier_stage_identities=value.get(
            "completed_verifier_stage_identities", []
        ),
        completed_acceptance_identities=value.get(
            "completed_acceptance_identities", []
        ),
        first_lane_a_surface_census=value.get(
            "first_post_terminal_surface_census", {}
        ),
        second_lane_a_surface_census=value.get(
            "second_post_terminal_surface_census", {}
        ),
    )
    if _canonical(value) != _canonical(expected):
        _fail("Lane-A terminal-invalid root differs after replay")
    return expected


__all__ = [
    "AMENDMENT_BYTES",
    "AMENDMENT_RELATIVE_PATH",
    "AMENDMENT_SHA256",
    "CONTROLLER_RELATIVE_PATH",
    "CONTROLLER_TEST_RELATIVE_PATH",
    "FOCUSED_TEST_OUTPUT_RELATIVE_PATH",
    "FOCUSED_TEST_COMMAND",
    "IMPLEMENTATION_RELATIVE_PATH",
    "IMPLEMENTATION_COMMIT_ENV",
    "LANE_A_CLOSURE_SCHEMA",
    "LANE_A_SURFACE_CENSUS_SCHEMA",
    "OPERATOR_RESULT_SCHEMA",
    "PANEL_CLOSURE_AMENDMENT_BYTES",
    "PANEL_CLOSURE_AMENDMENT_RELATIVE_PATH",
    "PANEL_CLOSURE_AMENDMENT_SHA256",
    "PREFLIGHT_COMMAND",
    "PREFLIGHT_ATTEMPT_RELATIVE_PATH",
    "PREFLIGHT_ATTEMPT_SCHEMA",
    "PREFLIGHT_RELATIVE_PATH",
    "PREFLIGHT_SCHEMA",
    "RECOVERY_TERMINAL_SCHEMA",
    "REPLACEMENT_COMPLETION_TIME",
    "REPLACEMENT_EXECUTION",
    "REPLACEMENT_INTENT_IDENTITY",
    "REPLACEMENT_OWNERSHIP_IDENTITY",
    "REPLACEMENT_STAGE_START_IDENTITY",
    "REPLACEMENT_STARTED_TIME",
    "REPLACEMENT_TASK",
    "REVIEW_LOCK_RELATIVE_PATH",
    "REVIEW_LOCK_SCHEMA",
    "SOURCE_ORDINAL",
    "SURFACE_CENSUS_SCHEMA",
    "TASK_COMPLETION_TIME",
    "TASK_CREATION_TIME",
    "TASK_MESSAGE",
    "TASK_REASON",
    "TASK_START_TIME",
    "TASK_DESCRIBE_ARGV",
    "EXECUTION_DESCRIBE_ARGV",
    "EXECUTION_COMPLETED_MESSAGE",
    "EXECUTION_CONDITIONS",
    "TERMINAL_PROJECTION_SCHEMA",
    "TEST_RELATIVE_PATH",
    "T230PlatformReplacementTerminalError",
    "TerminalClosureBackend",
    "build_lane_a_terminal_invalid_root_v1",
    "build_lane_a_surface_census_v1",
    "build_preflight_attempt_marker_v1",
    "build_replacement_execution_terminal_v1",
    "build_surface_census_v1",
    "build_terminal_closure_preflight_v1",
    "build_terminal_closure_review_lock_v1",
    "frozen_terminal_closure_contract_v1",
    "focused_test_pass_count_v1",
    "lane_a_terminal_surface_uris_v1",
    "reopen_terminal_closure_review_lock_v1",
    "reopen_replacement_launch_lineage_v1",
    "terminal_closure_implementation_measurements_v1",
    "terminal_surface_uris_v1",
    "validate_lane_a_terminal_invalid_root_v1",
    "validate_lane_a_surface_census_v1",
    "validate_preflight_attempt_marker_v1",
    "validate_replacement_execution_terminal_v1",
    "validate_replacement_failure_projection_v1",
    "validate_surface_census_v1",
    "validate_terminal_closure_contract_v1",
    "validate_terminal_closure_preflight_v1",
    "validate_terminal_closure_review_lock_v1",
    "verify_terminal_closure_implementation_commit_v1",
]
