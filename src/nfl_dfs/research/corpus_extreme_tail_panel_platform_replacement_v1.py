"""Fail-closed one-time replacement law for T230 worker ordinal 6.

This module is a narrow mechanical amendment to the outcome-blind Foundry
T230 transport.  It does not retry an existing request.  It recognizes one
exact Cloud Run platform failure, exact-replays the already-consumed primary
launch and stage-start chain, proves that neither the core result nor the
canonical worker stage receipt exists, and builds the exact candidate for one
new attempt-1 replacement intent at a new create-once URI.

This module deliberately cannot publish that intent or grant Cloud Run launch
permission.  Those operations require a separately sealed same-process
controller whose bytes and tests join the post-test review lock.  A successful
replacement still grants no worker acceptance, verifier, lane, panel,
scoring, fill, graph, promotion, decision, or production authority.  Those
remain blocked until a separate bridge verifier completion and supplemental
lane/panel roots are implemented and exact-replayed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
import subprocess
from typing import Final, Protocol

from nfl_dfs.research import corpus_extreme_tail_panel_execution as execution
from nfl_dfs.research import corpus_extreme_tail_panel_transport as transport
from nfl_dfs.research import corpus_parametric_batch as batch


CONTRACT_SCHEMA: Final = (
    "foundry-t230-ordinal-6-platform-replacement-contract/v1"
)
TERMINAL_PROJECTION_SCHEMA: Final = (
    "foundry-t230-ordinal-6-platform-failure-projection/v1"
)
INTENT_SCHEMA: Final = (
    "foundry-t230-ordinal-6-platform-replacement-intent/v1"
)
OPERATOR_RESULT_SCHEMA: Final = (
    "foundry-t230-ordinal-6-platform-replacement-operator-result/v1"
)
REVIEW_LOCK_SCHEMA: Final = (
    "foundry-t230-ordinal-6-platform-replacement-review-lock/v2"
)
WORKER_LAUNCH_PLAN_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-worker-launch-plan/v1"
)
LIVE_JOB_PROJECTION_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-live-job-projection/v1"
)
REAL_ARTIFACT_PREFLIGHT_SCHEMA: Final = (
    "foundry-t230-ordinal-6-platform-replacement-real-artifact-preflight/v2"
)
LAUNCH_OWNERSHIP_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-worker-launch-ownership/v1"
)
REPLACEMENT_STAGE_START_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-worker-stage-start/v1"
)

SOURCE_ORDINAL: Final = 6
LANE_ORDINAL: Final = 0
OPERATION: Final = "run-slate"
PRIMARY_RUNTIME_ATTEMPT: Final = 0
REPLACEMENT_RUNTIME_ATTEMPT: Final = 1
MAX_REPLACEMENT_WORKER_EXECUTIONS: Final = 1
FAILED_EXECUTION: Final = "atlas-minimal-c-s2023-w1-v1-rffts"
FAILED_TASK: Final = FAILED_EXECUTION + "-task0"
REUSE_JOB: Final = transport.LANE_A_JOB
SERVICE_ACCOUNT: Final = (
    "817589974517-compute@developer.gserviceaccount.com"
)
FROZEN_D2_URI: Final = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
    "sha256:ed7da003c80ad47118c3c9242ec2e9047a24f489134bfdc0f534a6769d622fee"
)
FROZEN_D2_DIGEST: Final = (
    "sha256:ed7da003c80ad47118c3c9242ec2e9047a24f489134bfdc0f534a6769d622fee"
)
AMENDMENT_RELATIVE_PATH: Final = (
    "reports/2026-08-26-t230-ordinal6-bounded-platform-replacement-amendment.md"
)
AMENDMENT_SHA256: Final = (
    "72d4f85eeada11ab4148a82085837a6b4e6909d402b8084b232cebb618f3b7bd"
)
AMENDMENT_BYTES: Final = 10286
CORRECTION_ADDENDUM_RELATIVE_PATH: Final = (
    "reports/2026-08-26-t230-ordinal6-focused-test-correction-addendum.md"
)
CORRECTION_ADDENDUM_SHA256: Final = (
    "2192bbd35446b89f5b5cc9dc6a7bf681747f7b4cf00bf3d4fe72c1db53965dd8"
)
CORRECTION_ADDENDUM_BYTES: Final = 10362
PREFLIGHT_CORRECTION_ADDENDUM_RELATIVE_PATH: Final = (
    "reports/2026-08-26-t230-ordinal6-real-artifact-preflight-"
    "correction-addendum.md"
)
FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_RELATIVE_PATH: Final = (
    "reports/2026-08-26-t230-ordinal6-corrected-focused-test-output.txt"
)
FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_SHA256: Final = (
    "194407658363bec291839dce28931401bad3c2658310563edd3ba16380809fbc"
)
FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_BYTES: Final = 320
POST_PREFLIGHT_FIX_FOCUSED_TEST_OUTPUT_RELATIVE_PATH: Final = (
    "reports/2026-08-26-t230-ordinal6-post-preflight-fix-focused-test-output.txt"
)
IMPLEMENTATION_RELATIVE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_extreme_tail_panel_platform_replacement_v1.py"
)
TEST_RELATIVE_PATH: Final = (
    "tests/test_corpus_extreme_tail_panel_platform_replacement_v1.py"
)
CONTROLLER_RELATIVE_PATH: Final = (
    "scripts/run_corpus_extreme_tail_panel_platform_replacement_v1.py"
)
CONTROLLER_TEST_RELATIVE_PATH: Final = (
    "tests/test_run_corpus_extreme_tail_panel_platform_replacement_v1.py"
)
REVIEW_LOCK_RELATIVE_PATH: Final = (
    "reports/2026-08-26-t230-ordinal6-platform-replacement-review-lock.json"
)
REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH: Final = (
    "reports/2026-08-26-t230-ordinal6-platform-replacement-"
    "real-artifact-preflight.json"
)
REAL_ARTIFACT_PREFLIGHT_FLAGS_PATH: Final = (
    "/tmp/foundry-t230-ordinal6-replacement-worker-flags-v1.json"
)
FOCUSED_TEST_COMMAND: Final = (
    ".venv/bin/python",
    "-m",
    "pytest",
    "-q",
    TEST_RELATIVE_PATH,
    CONTROLLER_TEST_RELATIVE_PATH,
)
PRIOR_FAILED_INVOCATION_COUNT: Final = 1
CORRECTED_CANDIDATE_INVOCATION_COUNT_MAX: Final = 1
POST_PREFLIGHT_FIX_CANDIDATE_INVOCATION_COUNT_MAX: Final = 1
FOCUSED_TEST_TOTAL_INVOCATION_COUNT_MAX: Final = 3
PRIOR_FAILED_PYTEST_EXIT_CODE: Final = 1
REAL_ARTIFACT_PREFLIGHT_TOTAL_INVOCATION_COUNT_MAX: Final = 2
FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_EXIT_CODE: Final = 1
FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_ERROR_LINES: Final = (
    "primary execution/task terminal literals differ",
    "real-artifact preflight failed closed",
)

# Cloud Run's v1 execution projection omits ``value`` for these exact frozen
# empty-string attempt-0 overrides.  The production observer may normalize a
# name-only row to the empty string only when its name is in this ordered,
# contract-bound tuple.  Every unknown name-only row, ``valueFrom`` row, or
# row with extra fields remains terminal.
PRIMARY_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES: Final = (
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
)
PRIOR_FAILED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS: Final = (
    {
        "relative_path": IMPLEMENTATION_RELATIVE_PATH,
        "sha256": (
            "83dfa819da046777bcd9b0520519300bb8efd13fe3fc13401e813c25853a321b"
        ),
        "bytes": 90541,
    },
    {
        "relative_path": TEST_RELATIVE_PATH,
        "sha256": (
            "a01e486bb25db1112c322ff1825b7c9d5595a64900fe0879f1fa4ce1cbc86b6a"
        ),
        "bytes": 54236,
    },
    {
        "relative_path": CONTROLLER_RELATIVE_PATH,
        "sha256": (
            "169a385e00165f88b029509ffd89848a1e34b2e06a66af17770f1a246249576a"
        ),
        "bytes": 118931,
    },
    {
        "relative_path": CONTROLLER_TEST_RELATIVE_PATH,
        "sha256": (
            "4b2a6bbd0a937149af2c0c6a70368063953f0f052ba6a50d0653baa83f31255e"
        ),
        "bytes": 50301,
    },
)
PRIOR_FAILED_FOCUSED_TEST_NODE_IDS: Final = (
    (
        "tests/test_corpus_extreme_tail_panel_platform_replacement_v1.py::"
        "test_review_lock_rejects_changed_preflight_receipt_measurement["
        "sha256-eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee]"
    ),
    (
        "tests/test_run_corpus_extreme_tail_panel_platform_replacement_v1.py::"
        "test_production_cli_wires_only_reviewed_live_entry"
    ),
    (
        "tests/test_run_corpus_extreme_tail_panel_platform_replacement_v1.py::"
        "test_preflight_cli_uses_fixed_tracked_output_and_blocks_second_invocation"
    ),
)
FIRST_CORRECTED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS: Final = (
    {
        "relative_path": IMPLEMENTATION_RELATIVE_PATH,
        "sha256": (
            "f9c764cf1ed4f65ec17a6b9c8ca71062c9677d62e4094e2f0c7d2a60402e9f00"
        ),
        "bytes": 100552,
    },
    {
        "relative_path": TEST_RELATIVE_PATH,
        "sha256": (
            "f00eff040af23beae5070e654905471f3d204199b7c2c01eb2058b0941a03a35"
        ),
        "bytes": 63564,
    },
    {
        "relative_path": CONTROLLER_RELATIVE_PATH,
        "sha256": (
            "1bac84bf99c6b11ca5f7009dea5279978040b62ea0eea7d290d3781e69865904"
        ),
        "bytes": 119680,
    },
    {
        "relative_path": CONTROLLER_TEST_RELATIVE_PATH,
        "sha256": (
            "a3df0976b693e3f0e727ef4c03c9a0a0af4b006ff1059f745d7bed649e244940"
        ),
        "bytes": 56833,
    },
)
REAL_ARTIFACT_PREFLIGHT_COMMAND: Final = (
    ".venv/bin/python",
    CONTROLLER_RELATIVE_PATH,
    "preflight-worker",
    "--preflight",
)

RESULT_URI: Final = (
    transport.OUTPUT_PREFIX
    + "slates/06-2023-w07/foundry-t230-slate-analysis-v1.json"
)
ACCEPTANCE_URI: Final = (
    transport.OUTPUT_PREFIX
    + "slates/06-2023-w07/foundry-t230-slate-acceptance-v1.json"
)
PRIMARY_STAGE_RECEIPT_URI: Final = (
    transport.TRANSPORT_PREFIX + "stages/run-slate/06.json"
)
PRIMARY_STAGE_START_URI: Final = transport.stage_start_uri(
    OPERATION, SOURCE_ORDINAL, PRIMARY_RUNTIME_ATTEMPT
)
PRIMARY_RUNTIME_MEASUREMENT_URI: Final = (
    execution.runtime_measurement_uri_for_output_prefix(
        transport.OUTPUT_PREFIX,
        role="worker",
        source_ordinal=SOURCE_ORDINAL,
        runtime_attempt_ordinal=PRIMARY_RUNTIME_ATTEMPT,
    )
)
REPLACEMENT_RUNTIME_MEASUREMENT_URI: Final = (
    execution.runtime_measurement_uri_for_output_prefix(
        transport.OUTPUT_PREFIX,
        role="worker",
        source_ordinal=SOURCE_ORDINAL,
        runtime_attempt_ordinal=REPLACEMENT_RUNTIME_ATTEMPT,
    )
)
REPLACEMENT_STAGE_START_URI: Final = transport.stage_start_uri(
    OPERATION, SOURCE_ORDINAL, REPLACEMENT_RUNTIME_ATTEMPT
)
REPLACEMENT_INTENT_URI: Final = (
    transport.TRANSPORT_PREFIX
    + "platform-replacements/run-slate/06/attempt-01/launch-intent-v1.json"
)
REPLACEMENT_SUCCESS_COMPLETION_URI: Final = (
    transport.TRANSPORT_PREFIX
    + "platform-replacements/run-slate/06/attempt-01/success-completion-v1.json"
)
REPLACEMENT_EXECUTION_TERMINAL_URI: Final = (
    transport.TRANSPORT_PREFIX
    + "platform-replacements/run-slate/06/attempt-01/execution-terminal-v1.json"
)
REPLACEMENT_LAUNCH_OWNERSHIP_URI: Final = (
    transport.TRANSPORT_PREFIX
    + "platform-replacements/run-slate/06/attempt-01/launch-ownership-v1.json"
)
REPLACEMENT_WORKER_AMENDMENT_URI: Final = (
    transport.TRANSPORT_PREFIX
    + "platform-replacements/run-slate/06/attempt-01/worker-stage-amendment-v1.json"
)
BRIDGE_VERIFIER_LAUNCH_REQUEST_URI: Final = transport.launch_request_uri(
    "verify-slate", SOURCE_ORDINAL
)
BRIDGE_VERIFIER_STAGE_START_URI: Final = transport.stage_start_uri(
    "verify-slate", SOURCE_ORDINAL, 0
)
BRIDGE_VERIFIER_RUNTIME_MEASUREMENT_URI: Final = (
    execution.runtime_measurement_uri_for_output_prefix(
        transport.OUTPUT_PREFIX,
        role="verifier",
        source_ordinal=SOURCE_ORDINAL,
        runtime_attempt_ordinal=0,
    )
)
BRIDGE_VERIFIER_STAGE_RECEIPT_URI: Final = (
    transport.TRANSPORT_PREFIX + "stages/verify-slate/06.json"
)
BRIDGE_VERIFIER_EXECUTION_TERMINAL_URI: Final = (
    transport.TRANSPORT_PREFIX
    + "platform-replacements/verify-slate/06/attempt-00/"
    "execution-terminal-v1.json"
)
BRIDGE_VERIFIER_LAUNCH_OWNERSHIP_URI: Final = (
    transport.TRANSPORT_PREFIX
    + "platform-replacements/verify-slate/06/attempt-00/"
    "launch-ownership-v1.json"
)
BRIDGE_VERIFIER_COMPLETION_URI: Final = (
    transport.TRANSPORT_PREFIX
    + "platform-replacements/verify-slate/06/attempt-00/bridge-completion-v1.json"
)
SUPPLEMENTAL_LANE_ROOT_URI: Final = (
    transport.TRANSPORT_PREFIX
    + "platform-replacements/lanes/lane-0-ordinal-06-amendment-v1.json"
)
SUPPLEMENTAL_PANEL_ROOT_URI: Final = (
    transport.TRANSPORT_PREFIX
    + "platform-replacements/panel/ordinal-06-amendment-v1.json"
)

_PRIMARY_STAGE_START_IDENTITY: Final = {
    "uri": PRIMARY_STAGE_START_URI,
    "generation": "1787709944159900",
    "sha256": "744f5f944089eb01ad5a100574e69734eeb9008c2977968a67f513936c91013b",
    "bytes": 3593,
}
_PRIMARY_STAGE_START_SELF_SHA256: Final = (
    "c8b65e04fac81cd8834596cdba50ae45ee825865650c706049230f038d397548"
)
_PRIMARY_RUNTIME_MEASUREMENT_IDENTITY: Final = {
    "uri": PRIMARY_RUNTIME_MEASUREMENT_URI,
    "generation": "1787710039301316",
    "sha256": "80beaefc343166a3f06f9e1221f4f2126a76758114dc7c50a97838eb71623c0c",
    "bytes": 13520,
}
_PRIMARY_RUNTIME_MEASUREMENT_SELF_SHA256: Final = (
    "163d5073ccc516ddc91612de9c5fd1f7d93b77a6dd6d4cfd3d126e3e7787622a"
)
_PRIMARY_LAUNCH_REQUEST_IDENTITY: Final = {
    "uri": transport.launch_request_uri(OPERATION, SOURCE_ORDINAL),
    "generation": "1787709788000394",
    "sha256": "6e62e8f41dbb526fcd49672c8436f2bf000933248721b4363bdb1a85af931415",
    "bytes": 2525,
}
_TRANSPORT_CONTRACT_IDENTITY: Final = {
    "uri": transport.TRANSPORT_CONTRACT_URI,
    "generation": "1787692605903060",
    "sha256": "0ce6aa688ef9ca599f5fbafd8bd3e9d41a6557e1fe0c56c5caf15a2c80e64af9",
    "bytes": 11617,
}
_JOB_CONFIG_IDENTITY: Final = {
    "uri": transport.job_config_uri(REUSE_JOB),
    "generation": "1787692861799721",
    "sha256": "25682e42abb47cf87b8a465cdd00002df71f8b017433c25cbf91014577152656",
    "bytes": 1902,
}
_PREDECESSOR_IDENTITY: Final = {
    "uri": transport.TRANSPORT_PREFIX + "stages/verify-slate/05.json",
    "generation": "1787709754573677",
    "sha256": "6dd46009316b4ef6f0429d21287df329fefb926632e020e942998fc668ce5693",
    "bytes": 2063,
}
_EXECUTION_AUTHORITY_IDENTITY: Final = {
    "uri": transport.OUTPUT_PREFIX
    + "foundry-t230-panel-execution-authority-v1.json",
    "generation": "1787693122369176",
    "sha256": "2bca3aa90c238ed56c9137b0d9bea78384cb7c45df070954557040be9e73d1d8",
    "bytes": 5824,
}
_COMPUTE_RELEASE_IDENTITY: Final = {
    "uri": transport.COMPUTE_RELEASE_URI,
    "generation": "1787695033977025",
    "sha256": "0e1deaf971c83acd0fbf261b25de21df06120ad45469a44ff789c0f9f7afcc0f",
    "bytes": 3670,
}

_ABSENT_EFFECT_SURFACE: Final = (
    RESULT_URI,
    PRIMARY_STAGE_RECEIPT_URI,
    REPLACEMENT_STAGE_START_URI,
    REPLACEMENT_RUNTIME_MEASUREMENT_URI,
    REPLACEMENT_LAUNCH_OWNERSHIP_URI,
    REPLACEMENT_EXECUTION_TERMINAL_URI,
    REPLACEMENT_WORKER_AMENDMENT_URI,
    REPLACEMENT_SUCCESS_COMPLETION_URI,
    BRIDGE_VERIFIER_LAUNCH_REQUEST_URI,
    BRIDGE_VERIFIER_STAGE_START_URI,
    BRIDGE_VERIFIER_RUNTIME_MEASUREMENT_URI,
    BRIDGE_VERIFIER_STAGE_RECEIPT_URI,
    BRIDGE_VERIFIER_LAUNCH_OWNERSHIP_URI,
    BRIDGE_VERIFIER_EXECUTION_TERMINAL_URI,
    ACCEPTANCE_URI,
    BRIDGE_VERIFIER_COMPLETION_URI,
    SUPPLEMENTAL_LANE_ROOT_URI,
    SUPPLEMENTAL_PANEL_ROOT_URI,
)
_ABSENT_BEFORE_REPLACEMENT: Final = (
    REPLACEMENT_INTENT_URI,
    *_ABSENT_EFFECT_SURFACE,
)

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
_COMMIT = re.compile(r"[0-9a-f]{40}")
_COMPLETED_MESSAGE: Final = (
    "Task atlas-minimal-c-s2023-w1-v1-rffts-task0 failed with exit code: 0 "
    "and message: Internal error."
)
_LAST_ATTEMPT_MESSAGE: Final = "Internal error."
FROZEN_PRIMARY_RUNTIME_PAYLOAD_SHA256: Final = (
    "1c95fd4312db7baff61e0c25366cc07e515d74fef0741ebbd4f852ccf5c9cc19"
)
FROZEN_PRIMARY_RUNTIME_PAYLOAD_BYTES: Final = 7688
EXECUTION_DESCRIBE_ARGV: Final = (
    "gcloud",
    "run",
    "jobs",
    "executions",
    "describe",
    FAILED_EXECUTION,
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
    f"--execution={FAILED_EXECUTION}",
    f"--project={transport.PROJECT}",
    f"--region={transport.REGION}",
    "--limit=2",
    "--format=json",
)
LIVE_JOB_DESCRIBE_ARGV: Final = (
    "gcloud",
    "run",
    "jobs",
    "describe",
    REUSE_JOB,
    "--project",
    transport.PROJECT,
    "--region",
    transport.REGION,
    "--format=json",
)


class T230PlatformReplacementError(RuntimeError):
    """The ordinal-6 platform replacement failed closed."""


class PlatformReplacementBackend(transport.JournalBackend, Protocol):
    """Known-name store plus the exact normalized terminal observation."""

    def observe_primary_terminal(self, execution_name: str) -> Mapping[str, object]:
        """Return the exact normalized execution+task projection."""

    def probe_known_uri_metadata(self, uri: str) -> Mapping[str, object] | None:
        """Return metadata on presence or None only for an exact-name 404."""


def _fail(message: str) -> None:
    raise T230PlatformReplacementError(message)


def _canonical(value: object) -> bytes:
    return batch.canonical_json_bytes(value)


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    if field in body:
        _fail(f"{field} cannot be caller supplied")
    retained = dict(body)
    retained[field] = batch.canonical_sha256(retained)
    return retained


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> None:
    retained = value.get(field)
    if not isinstance(retained, str) or _SHA256.fullmatch(retained) is None:
        _fail(f"{label} hash differs")
    body = {key: item for key, item in value.items() if key != field}
    if batch.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise T230PlatformReplacementError(f"{label} identity differs") from exc


def _fixed_identity(value: Mapping[str, object]) -> dict[str, object]:
    return _identity(dict(value), label="fixed platform-replacement object")


def _image() -> dict[str, str]:
    return {"uri": FROZEN_D2_URI, "digest": FROZEN_D2_DIGEST}


def _runtime_evidence_volume() -> dict[str, object]:
    return {
        "type": "in-memory",
        "name": "foundry-t230-runtime-evidence",
        "size_limit": "1Mi",
        "mount_path": "/etc/nfl-dfs",
    }


def _replacement_execution_envelope() -> dict[str, object]:
    return {
        "job": REUSE_JOB,
        "operation": OPERATION,
        "source_ordinal": SOURCE_ORDINAL,
        "runtime_attempt_ordinal": REPLACEMENT_RUNTIME_ATTEMPT,
        "immutable_image": _image(),
        "service_account": SERVICE_ACCOUNT,
        "cpu": "8",
        "memory": "32Gi",
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "task_timeout_seconds": transport.TASK_TIMEOUT_SECONDS,
        "runtime_evidence_volume": _runtime_evidence_volume(),
        "transport_contract_identity": _fixed_identity(
            _TRANSPORT_CONTRACT_IDENTITY
        ),
        "job_config_identity": _fixed_identity(_JOB_CONFIG_IDENTITY),
        "execution_authority_identity": _fixed_identity(
            _EXECUTION_AUTHORITY_IDENTITY
        ),
        "compute_release_identity": _fixed_identity(_COMPUTE_RELEASE_IDENTITY),
        "predecessor_identity": _fixed_identity(_PREDECESSOR_IDENTITY),
    }


def _post_submission_receipt_law() -> dict[str, object]:
    """Return the exact controller-owned ownership/start validation law."""
    return {
        "launch_ownership_schema_version": LAUNCH_OWNERSHIP_SCHEMA,
        "worker_stage_start_schema_version": REPLACEMENT_STAGE_START_SCHEMA,
        "launch_ownership_uri": REPLACEMENT_LAUNCH_OWNERSHIP_URI,
        "worker_stage_start_uri": REPLACEMENT_STAGE_START_URI,
        "exact_key_sets_required": True,
        "self_hash_replay_required": True,
        "replacement_intent_identity_exact_reopen_required": True,
        "worker_launch_plan_exact_replay_required": True,
        "execution_flags_exact_replay_required": True,
        "submitted_execution_projection_exact_replay_required": True,
        "submitted_execution_name_must_equal_submission_response": True,
        "ownership_execution_name_must_equal_submitted_projection": True,
        "ownership_envelope_must_equal_replacement_intent": True,
        "ownership_fixed_authority_identities_must_equal_launch_plan": True,
        "stage_start_launch_ownership_identity_exact_reopen_required": True,
        "stage_start_execution_name_must_equal_ownership": True,
        "stage_start_envelope_must_equal_launch_plan": True,
        "stage_start_fixed_authority_identities_must_equal_launch_plan": True,
        "extra_fields_allowed": False,
        "false_authority_fields": list(_FALSE_AUTHORITY_FIELDS),
    }


def _false_authorities(value: Mapping[str, object], *, label: str) -> None:
    for field in _FALSE_AUTHORITY_FIELDS:
        if value.get(field) is not False:
            _fail(f"{label}.{field} must be false")


def _measure_local_file(
    *, relative_path: str, expected_sha256: str | None = None,
    expected_bytes: int | None = None,
) -> dict[str, object]:
    path = transport.REPOSITORY_ROOT / relative_path
    if path.is_symlink() or not path.is_file():
        _fail(f"required local file differs: {relative_path}")
    raw = path.read_bytes()
    measured = {
        "relative_path": relative_path,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    if (
        (expected_sha256 is not None and measured["sha256"] != expected_sha256)
        or (expected_bytes is not None and measured["bytes"] != expected_bytes)
    ):
        _fail(f"required local file bytes differ: {relative_path}")
    return measured


def _amendment_measurement() -> dict[str, object]:
    return _measure_local_file(
        relative_path=AMENDMENT_RELATIVE_PATH,
        expected_sha256=AMENDMENT_SHA256,
        expected_bytes=AMENDMENT_BYTES,
    )


def _correction_addendum_measurement() -> dict[str, object]:
    """Reopen the reviewed first test-history correction addendum."""
    return _measure_local_file(
        relative_path=CORRECTION_ADDENDUM_RELATIVE_PATH,
        expected_sha256=CORRECTION_ADDENDUM_SHA256,
        expected_bytes=CORRECTION_ADDENDUM_BYTES,
    )


def _preflight_correction_addendum_measurement() -> dict[str, object]:
    """Measure the separately reviewed failed-preflight correction law."""
    return _measure_local_file(
        relative_path=PREFLIGHT_CORRECTION_ADDENDUM_RELATIVE_PATH
    )


def _first_corrected_focused_test_output_measurement() -> dict[str, object]:
    """Reopen the durable output from the first corrected focused pass."""
    return _measure_local_file(
        relative_path=FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
        expected_sha256=FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_SHA256,
        expected_bytes=FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_BYTES,
    )


def _post_preflight_fix_focused_test_output_measurement() -> dict[str, object]:
    """Measure the durable output from the one post-preflight-fix test run."""
    return _measure_local_file(
        relative_path=POST_PREFLIGHT_FIX_FOCUSED_TEST_OUTPUT_RELATIVE_PATH
    )


def _implementation_measurements() -> list[dict[str, object]]:
    # Deliberately measured against a separately frozen post-test review lock.
    # The live authority surface is the operator plus its same-process
    # publisher/controller and both focused test files.
    return [
        _measure_local_file(relative_path=relative_path)
        for relative_path in (
            IMPLEMENTATION_RELATIVE_PATH,
            TEST_RELATIVE_PATH,
            CONTROLLER_RELATIVE_PATH,
            CONTROLLER_TEST_RELATIVE_PATH,
        )
    ]


def _validate_file_measurement(
    value: object, *, relative_path: str, label: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} measurement differs")
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


def _validate_implementation_measurements(
    value: object,
) -> list[dict[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        _fail("recovery implementation measurement set differs")
    rows = list(value)
    expected_paths = (
        IMPLEMENTATION_RELATIVE_PATH,
        TEST_RELATIVE_PATH,
        CONTROLLER_RELATIVE_PATH,
        CONTROLLER_TEST_RELATIVE_PATH,
    )
    if len(rows) != len(expected_paths):
        _fail("recovery implementation measurement count differs")
    return [
        _validate_file_measurement(
            rows[ordinal],
            relative_path=relative_path,
            label=f"recovery implementation[{ordinal}]",
        )
        for ordinal, relative_path in enumerate(expected_paths)
    ]


def _validate_review_lock_binding(
    value: object,
    *,
    review_lock: Mapping[str, object],
) -> dict[str, object]:
    """Validate the fixed-path Git binding for the reviewed lock bytes."""
    if not isinstance(value, Mapping):
        _fail("recovery review-lock binding must be one object")
    item = dict(value)
    raw = _canonical(review_lock) + b"\n"
    if (
        set(item)
        != {
            "relative_path",
            "source_commit_sha",
            "sha256",
            "bytes",
            "tracked_at_head",
            "clean_at_head",
        }
        or item.get("relative_path") != REVIEW_LOCK_RELATIVE_PATH
        or not isinstance(item.get("source_commit_sha"), str)
        or _COMMIT.fullmatch(str(item["source_commit_sha"])) is None
        or item.get("sha256") != sha256(raw).hexdigest()
        or type(item.get("bytes")) is not int
        or item.get("bytes") != len(raw)
        or item.get("tracked_at_head") is not True
        or item.get("clean_at_head") is not True
    ):
        _fail("recovery review-lock tracked binding differs")
    return item


def validate_recovery_review_lock_v1(
    value: object,
    *,
    expected_implementation_measurements: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Validate the externally created independent-review decision lock."""
    if not isinstance(value, Mapping):
        _fail("recovery review lock must be one object")
    item = dict(value)
    required = {
        "schema_version",
        "run_id",
        "review_method",
        "reviewed_candidate_disposition",
        "amendment_measurement",
        "correction_addendum_measurement",
        "preflight_correction_addendum_measurement",
        "reviewed_implementation_measurements",
        "reviewed_implementation_measurements_sha256",
        "failed_focused_test_candidate_measurements",
        "failed_focused_test_candidate_measurements_sha256",
        "first_corrected_focused_test_candidate_measurements",
        "first_corrected_focused_test_candidate_measurements_sha256",
        "first_corrected_focused_test_output_measurement",
        "post_preflight_fix_focused_test_output_measurement",
        "source_ast_parse_passed",
        "tests_ast_parse_passed",
        "controller_ast_parse_passed",
        "controller_tests_ast_parse_passed",
        "git_diff_check_passed",
        "focused_test_command",
        "prior_failed_focused_test_command",
        "prior_failed_invocation_count",
        "prior_failed_pytest_exit_code",
        "prior_failed_failure_node_ids",
        "prior_failed_failure_count",
        "prior_failed_cloud_call_count",
        "prior_failed_preflight_invocation_count",
        "prior_failed_intent_built",
        "prior_failed_realized_outcomes_read",
        "prior_failed_collected_passed_counts_available",
        "prior_failed_test_output_sha256_available",
        "first_corrected_candidate_invocation_count",
        "first_corrected_candidate_result",
        "first_corrected_tests_collected",
        "first_corrected_tests_passed",
        "first_corrected_tests_failed",
        "first_corrected_tests_skipped",
        "first_corrected_test_warnings",
        "first_corrected_pytest_exit_code",
        "first_corrected_pytest_wall_milliseconds",
        "first_corrected_test_output_sha256",
        "first_corrected_test_output_bytes",
        "corrected_candidate_invocation_count",
        "corrected_candidate_invocation_count_max",
        "focused_test_total_invocation_count",
        "focused_test_total_invocation_count_max",
        "corrected_candidate_result",
        "real_artifact_preflight_receipt_measurement",
        "real_artifact_preflight_command",
        "first_failed_real_artifact_preflight_command",
        "first_failed_real_artifact_preflight_invocation_count",
        "first_failed_real_artifact_preflight_exit_code",
        "first_failed_real_artifact_preflight_error_lines",
        "first_failed_real_artifact_preflight_output_measurement_available",
        "first_failed_real_artifact_preflight_receipt_created",
        "first_failed_real_artifact_preflight_cloud_read_performed",
        "first_failed_real_artifact_preflight_cloud_mutation_executed",
        "first_failed_real_artifact_preflight_gcs_publication_count",
        "first_failed_real_artifact_preflight_cloud_submit_count",
        "first_failed_real_artifact_preflight_realized_outcomes_read",
        "corrected_real_artifact_preflight_invocation_count",
        "real_artifact_preflight_invocation_count",
        "real_artifact_preflight_invocation_count_max",
        "real_artifact_preflight_passed",
        "real_artifact_preflight_realized_outcomes_read",
        "focused_test_cloud_call_count",
        "cloud_read_performed",
        "cloud_mutation_executed",
        "gcs_publication_count",
        "cloud_submit_count",
        "tests_collected",
        "tests_passed",
        "tests_failed",
        "tests_skipped",
        "test_warnings",
        "pytest_exit_code",
        "test_output_sha256",
        "test_output_bytes",
        "realized_outcomes_read",
        "independent_review_complete",
        *_FALSE_AUTHORITY_FIELDS,
        "review_lock_sha256",
    }
    if set(item) != required:
        _fail("recovery review lock fields differ")
    _validate_self_hash(item, field="review_lock_sha256", label="review lock")
    _false_authorities(item, label="review lock")
    rows = _validate_implementation_measurements(
        item.get("reviewed_implementation_measurements")
    )
    failed_rows = _validate_implementation_measurements(
        item.get("failed_focused_test_candidate_measurements")
    )
    amendment = item.get("amendment_measurement")
    correction_addendum = _validate_file_measurement(
        item.get("correction_addendum_measurement"),
        relative_path=CORRECTION_ADDENDUM_RELATIVE_PATH,
        label="focused-test correction addendum",
    )
    preflight_correction_addendum = _validate_file_measurement(
        item.get("preflight_correction_addendum_measurement"),
        relative_path=PREFLIGHT_CORRECTION_ADDENDUM_RELATIVE_PATH,
        label="real-artifact preflight correction addendum",
    )
    preflight_receipt = _validate_file_measurement(
        item.get("real_artifact_preflight_receipt_measurement"),
        relative_path=REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH,
        label="real-artifact preflight receipt",
    )
    first_corrected_output = _validate_file_measurement(
        item.get("first_corrected_focused_test_output_measurement"),
        relative_path=FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
        label="first corrected focused-test output",
    )
    post_preflight_fix_output = _validate_file_measurement(
        item.get("post_preflight_fix_focused_test_output_measurement"),
        relative_path=POST_PREFLIGHT_FIX_FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
        label="post-preflight-fix focused-test output",
    )
    first_corrected_rows = _validate_implementation_measurements(
        item.get("first_corrected_focused_test_candidate_measurements")
    )
    integer_results = {
        "tests_collected": item.get("tests_collected"),
        "tests_passed": item.get("tests_passed"),
        "tests_failed": item.get("tests_failed"),
        "tests_skipped": item.get("tests_skipped"),
        "test_warnings": item.get("test_warnings"),
        "pytest_exit_code": item.get("pytest_exit_code"),
        "test_output_bytes": item.get("test_output_bytes"),
    }
    history_integer_results = {
        "first_corrected_candidate_invocation_count": item.get(
            "first_corrected_candidate_invocation_count"
        ),
        "first_corrected_tests_collected": item.get(
            "first_corrected_tests_collected"
        ),
        "first_corrected_tests_passed": item.get(
            "first_corrected_tests_passed"
        ),
        "first_corrected_tests_failed": item.get(
            "first_corrected_tests_failed"
        ),
        "first_corrected_tests_skipped": item.get(
            "first_corrected_tests_skipped"
        ),
        "first_corrected_test_warnings": item.get(
            "first_corrected_test_warnings"
        ),
        "first_corrected_pytest_exit_code": item.get(
            "first_corrected_pytest_exit_code"
        ),
        "first_corrected_pytest_wall_milliseconds": item.get(
            "first_corrected_pytest_wall_milliseconds"
        ),
        "first_corrected_test_output_bytes": item.get(
            "first_corrected_test_output_bytes"
        ),
        "first_failed_real_artifact_preflight_invocation_count": item.get(
            "first_failed_real_artifact_preflight_invocation_count"
        ),
        "first_failed_real_artifact_preflight_exit_code": item.get(
            "first_failed_real_artifact_preflight_exit_code"
        ),
        "first_failed_real_artifact_preflight_gcs_publication_count": item.get(
            "first_failed_real_artifact_preflight_gcs_publication_count"
        ),
        "first_failed_real_artifact_preflight_cloud_submit_count": item.get(
            "first_failed_real_artifact_preflight_cloud_submit_count"
        ),
        "corrected_real_artifact_preflight_invocation_count": item.get(
            "corrected_real_artifact_preflight_invocation_count"
        ),
        "real_artifact_preflight_invocation_count_max": item.get(
            "real_artifact_preflight_invocation_count_max"
        ),
    }
    if (
        amendment
        != {
            "relative_path": AMENDMENT_RELATIVE_PATH,
            "sha256": AMENDMENT_SHA256,
            "bytes": AMENDMENT_BYTES,
        }
        or correction_addendum
        != {
            "relative_path": CORRECTION_ADDENDUM_RELATIVE_PATH,
            "sha256": CORRECTION_ADDENDUM_SHA256,
            "bytes": CORRECTION_ADDENDUM_BYTES,
        }
        or item.get("schema_version") != REVIEW_LOCK_SCHEMA
        or item.get("run_id") != transport.RUN_ID
        or item.get("review_method") != "independent-static-contract-review-v1"
        or item.get("reviewed_candidate_disposition")
        != "accepted-no-p0-p1-p2"
        or item.get("reviewed_implementation_measurements_sha256")
        != batch.canonical_sha256(rows)
        or failed_rows
        != [dict(row) for row in PRIOR_FAILED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS]
        or item.get("failed_focused_test_candidate_measurements_sha256")
        != batch.canonical_sha256(failed_rows)
        or first_corrected_rows
        != [
            dict(row)
            for row in FIRST_CORRECTED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS
        ]
        or item.get(
            "first_corrected_focused_test_candidate_measurements_sha256"
        )
        != batch.canonical_sha256(first_corrected_rows)
        or first_corrected_output
        != {
            "relative_path": FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
            "sha256": FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_SHA256,
            "bytes": FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_BYTES,
        }
        or item.get("source_ast_parse_passed") is not True
        or item.get("tests_ast_parse_passed") is not True
        or item.get("controller_ast_parse_passed") is not True
        or item.get("controller_tests_ast_parse_passed") is not True
        or item.get("git_diff_check_passed") is not True
        or item.get("focused_test_command") != list(FOCUSED_TEST_COMMAND)
        or item.get("prior_failed_focused_test_command")
        != list(FOCUSED_TEST_COMMAND)
        or type(item.get("prior_failed_invocation_count")) is not int
        or item.get("prior_failed_invocation_count")
        != PRIOR_FAILED_INVOCATION_COUNT
        or type(item.get("prior_failed_pytest_exit_code")) is not int
        or item.get("prior_failed_pytest_exit_code")
        != PRIOR_FAILED_PYTEST_EXIT_CODE
        or item.get("prior_failed_failure_node_ids")
        != list(PRIOR_FAILED_FOCUSED_TEST_NODE_IDS)
        or type(item.get("prior_failed_failure_count")) is not int
        or item.get("prior_failed_failure_count") != 3
        or type(item.get("prior_failed_cloud_call_count")) is not int
        or item.get("prior_failed_cloud_call_count") != 0
        or type(item.get("prior_failed_preflight_invocation_count")) is not int
        or item.get("prior_failed_preflight_invocation_count") != 0
        or item.get("prior_failed_intent_built") is not False
        or item.get("prior_failed_realized_outcomes_read") is not False
        or item.get("prior_failed_collected_passed_counts_available") is not False
        or item.get("prior_failed_test_output_sha256_available") is not False
        or any(type(value) is not int for value in history_integer_results.values())
        or type(item.get("first_corrected_candidate_invocation_count")) is not int
        or item.get("first_corrected_candidate_invocation_count") != 1
        or item.get("first_corrected_candidate_result") != "passed"
        or item.get("first_corrected_tests_collected") != 271
        or item.get("first_corrected_tests_passed") != 271
        or item.get("first_corrected_tests_failed") != 0
        or item.get("first_corrected_tests_skipped") != 0
        or item.get("first_corrected_test_warnings") != 0
        or item.get("first_corrected_pytest_exit_code") != 0
        or item.get("first_corrected_pytest_wall_milliseconds") != 3515
        or item.get("first_corrected_test_output_sha256")
        != FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_SHA256
        or item.get("first_corrected_test_output_bytes")
        != FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_BYTES
        or type(item.get("corrected_candidate_invocation_count")) is not int
        or item.get("corrected_candidate_invocation_count") != 1
        or type(item.get("corrected_candidate_invocation_count_max")) is not int
        or item.get("corrected_candidate_invocation_count_max")
        != CORRECTED_CANDIDATE_INVOCATION_COUNT_MAX
        or type(item.get("focused_test_total_invocation_count")) is not int
        or item.get("focused_test_total_invocation_count") != 3
        or type(item.get("focused_test_total_invocation_count_max")) is not int
        or item.get("focused_test_total_invocation_count_max")
        != FOCUSED_TEST_TOTAL_INVOCATION_COUNT_MAX
        or item.get("corrected_candidate_result") != "passed"
        or item.get("real_artifact_preflight_command")
        != list(REAL_ARTIFACT_PREFLIGHT_COMMAND)
        or item.get("first_failed_real_artifact_preflight_command")
        != list(REAL_ARTIFACT_PREFLIGHT_COMMAND)
        or item.get("first_failed_real_artifact_preflight_invocation_count") != 1
        or item.get("first_failed_real_artifact_preflight_exit_code")
        != FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_EXIT_CODE
        or item.get("first_failed_real_artifact_preflight_error_lines")
        != list(FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_ERROR_LINES)
        or item.get(
            "first_failed_real_artifact_preflight_output_measurement_available"
        ) is not False
        or item.get("first_failed_real_artifact_preflight_receipt_created") is not False
        or item.get(
            "first_failed_real_artifact_preflight_cloud_read_performed"
        ) is not True
        or item.get(
            "first_failed_real_artifact_preflight_cloud_mutation_executed"
        ) is not False
        or item.get("first_failed_real_artifact_preflight_gcs_publication_count") != 0
        or item.get("first_failed_real_artifact_preflight_cloud_submit_count") != 0
        or item.get(
            "first_failed_real_artifact_preflight_realized_outcomes_read"
        ) is not False
        or item.get("corrected_real_artifact_preflight_invocation_count") != 1
        or type(item.get("real_artifact_preflight_invocation_count")) is not int
        or item.get("real_artifact_preflight_invocation_count") != 2
        or item.get("real_artifact_preflight_invocation_count_max")
        != REAL_ARTIFACT_PREFLIGHT_TOTAL_INVOCATION_COUNT_MAX
        or item.get("real_artifact_preflight_passed") is not True
        or item.get("real_artifact_preflight_realized_outcomes_read")
        is not False
        or type(item.get("focused_test_cloud_call_count")) is not int
        or item.get("focused_test_cloud_call_count") != 0
        or item.get("cloud_read_performed") is not True
        or item.get("cloud_mutation_executed") is not False
        or type(item.get("gcs_publication_count")) is not int
        or item.get("gcs_publication_count") != 0
        or type(item.get("cloud_submit_count")) is not int
        or item.get("cloud_submit_count") != 0
        or any(type(value) is not int for value in integer_results.values())
        or int(integer_results["tests_collected"]) < 1
        or integer_results["tests_passed"]
        != integer_results["tests_collected"]
        or integer_results["tests_failed"] != 0
        or integer_results["tests_skipped"] != 0
        or integer_results["test_warnings"] != 0
        or integer_results["pytest_exit_code"] != 0
        or not isinstance(item.get("test_output_sha256"), str)
        or _SHA256.fullmatch(str(item["test_output_sha256"])) is None
        or item.get("test_output_sha256") != post_preflight_fix_output["sha256"]
        or item.get("test_output_bytes") != post_preflight_fix_output["bytes"]
        or item.get("realized_outcomes_read") is not False
        or item.get("independent_review_complete") is not True
    ):
        _fail("recovery review lock decision differs")
    if expected_implementation_measurements is not None:
        expected = _validate_implementation_measurements(
            expected_implementation_measurements
        )
        if rows != expected:
            _fail("current recovery bytes differ from independent review lock")
    if preflight_receipt != item["real_artifact_preflight_receipt_measurement"]:
        _fail("real-artifact preflight receipt measurement differs")
    if correction_addendum != item["correction_addendum_measurement"]:
        _fail("focused-test correction addendum measurement differs")
    if (
        preflight_correction_addendum
        != item["preflight_correction_addendum_measurement"]
    ):
        _fail("real-artifact preflight correction addendum measurement differs")
    if (
        post_preflight_fix_output
        != item["post_preflight_fix_focused_test_output_measurement"]
    ):
        _fail("post-preflight-fix focused-test output measurement differs")
    return item


def _reopen_recovery_review_lock_v1(
    _backend: transport.JournalBackend,
) -> tuple[dict[str, object], dict[str, object]]:
    path = transport.REPOSITORY_ROOT / REVIEW_LOCK_RELATIVE_PATH
    if path.is_symlink() or not path.is_file():
        _fail("tracked recovery review lock is absent")
    raw = path.read_bytes()
    lock = validate_recovery_review_lock_v1(
        transport.strict_json(raw, label="tracked recovery review lock"),
        expected_implementation_measurements=_implementation_measurements(),
    )
    preflight_path = (
        transport.REPOSITORY_ROOT
        / REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH
    )
    if preflight_path.is_symlink() or not preflight_path.is_file():
        _fail("tracked real-artifact preflight receipt is absent")
    preflight_raw = preflight_path.read_bytes()
    preflight = validate_platform_replacement_real_artifact_preflight_v1(
        transport.strict_json(
            preflight_raw, label="tracked real-artifact preflight receipt"
        ),
        expected_implementation_measurements=_implementation_measurements(),
    )
    correction_addendum_measurement = _correction_addendum_measurement()
    preflight_correction_addendum_measurement = (
        _preflight_correction_addendum_measurement()
    )
    first_corrected_output_measurement = (
        _first_corrected_focused_test_output_measurement()
    )
    post_preflight_fix_output_measurement = (
        _post_preflight_fix_focused_test_output_measurement()
    )
    if (
        preflight_raw != _canonical(preflight) + b"\n"
        or lock["real_artifact_preflight_receipt_measurement"]
        != _measure_local_file(
            relative_path=REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH
        )
        or preflight["reviewed_implementation_measurements"]
        != lock["reviewed_implementation_measurements"]
        or preflight["amendment_measurement"]
        != lock["amendment_measurement"]
        or preflight["correction_addendum_measurement"]
        != lock["correction_addendum_measurement"]
        or lock["correction_addendum_measurement"]
        != correction_addendum_measurement
        or preflight["preflight_correction_addendum_measurement"]
        != lock["preflight_correction_addendum_measurement"]
        or lock["preflight_correction_addendum_measurement"]
        != preflight_correction_addendum_measurement
        or preflight["first_corrected_focused_test_output_measurement"]
        != lock["first_corrected_focused_test_output_measurement"]
        or lock["first_corrected_focused_test_output_measurement"]
        != first_corrected_output_measurement
        or preflight["post_preflight_fix_focused_test_output_measurement"]
        != lock["post_preflight_fix_focused_test_output_measurement"]
        or lock["post_preflight_fix_focused_test_output_measurement"]
        != post_preflight_fix_output_measurement
        or preflight["command"] != lock["real_artifact_preflight_command"]
        or preflight["invocation_count"]
        != lock["real_artifact_preflight_invocation_count"]
        or preflight["invocation_count_max"]
        != lock["real_artifact_preflight_invocation_count_max"]
        or preflight["first_failed_invocation_count"]
        != lock["first_failed_real_artifact_preflight_invocation_count"]
        or preflight["first_failed_command"]
        != lock["first_failed_real_artifact_preflight_command"]
        or preflight["first_failed_exit_code"]
        != lock["first_failed_real_artifact_preflight_exit_code"]
        or preflight["first_failed_error_lines"]
        != lock["first_failed_real_artifact_preflight_error_lines"]
        or preflight["first_failed_receipt_created"]
        is not lock["first_failed_real_artifact_preflight_receipt_created"]
        or preflight["corrected_invocation_count"]
        != lock["corrected_real_artifact_preflight_invocation_count"]
        or preflight["passed"] is not lock["real_artifact_preflight_passed"]
        or preflight["gcs_publication_count"]
        != lock["gcs_publication_count"]
        or preflight["cloud_submit_count"]
        != lock["cloud_submit_count"]
        or preflight["cloud_read_performed"]
        is not lock["cloud_read_performed"]
        or preflight["cloud_mutation_executed"]
        is not lock["cloud_mutation_executed"]
        or preflight["realized_outcomes_read"]
        is not lock["real_artifact_preflight_realized_outcomes_read"]
    ):
        _fail("tracked real-artifact preflight receipt bytes differ")
    if raw != _canonical(lock) + b"\n":
        _fail(
            "tracked recovery review lock must be canonical JSON plus newline"
        )
    tracked_paths = (
        REVIEW_LOCK_RELATIVE_PATH,
        AMENDMENT_RELATIVE_PATH,
        CORRECTION_ADDENDUM_RELATIVE_PATH,
        PREFLIGHT_CORRECTION_ADDENDUM_RELATIVE_PATH,
        FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
        POST_PREFLIGHT_FIX_FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
        IMPLEMENTATION_RELATIVE_PATH,
        TEST_RELATIVE_PATH,
        CONTROLLER_RELATIVE_PATH,
        CONTROLLER_TEST_RELATIVE_PATH,
        REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH,
    )
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=transport.REPOSITORY_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.decode("ascii").strip()
        status = subprocess.run(
            [
                "git", "status", "--porcelain=v1", "--untracked-files=all",
                "--", *tracked_paths,
            ],
            cwd=transport.REPOSITORY_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
        committed = {
            relative_path: subprocess.run(
                ["git", "show", f"{head}:{relative_path}"],
                cwd=transport.REPOSITORY_ROOT,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout
            for relative_path in tracked_paths
        }
    except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        raise T230PlatformReplacementError(
            "tracked recovery review-lock Git replay failed"
        ) from exc
    if (
        _COMMIT.fullmatch(head) is None
        or status != b""
        or committed[REVIEW_LOCK_RELATIVE_PATH] != raw
        or any(
            (transport.REPOSITORY_ROOT / relative_path).is_symlink()
            or not (transport.REPOSITORY_ROOT / relative_path).is_file()
            or committed[relative_path]
            != (transport.REPOSITORY_ROOT / relative_path).read_bytes()
            for relative_path in tracked_paths
        )
    ):
        _fail("recovery review lock/source/tests are not tracked clean at HEAD")
    binding = {
        "relative_path": REVIEW_LOCK_RELATIVE_PATH,
        "source_commit_sha": head,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "tracked_at_head": True,
        "clean_at_head": True,
    }
    return binding, lock


def frozen_platform_replacement_contract_v1() -> dict[str, object]:
    """Return the immutable, one-cell mechanical amendment surface."""
    body = {
        "schema_version": CONTRACT_SCHEMA,
        "run_id": transport.RUN_ID,
        "operation": OPERATION,
        "source_ordinal": SOURCE_ORDINAL,
        "lane_ordinal": LANE_ORDINAL,
        "reuse_job": REUSE_JOB,
        "failed_execution": FAILED_EXECUTION,
        "service_account": SERVICE_ACCOUNT,
        "immutable_image": _image(),
        "amendment_measurement": {
            "relative_path": AMENDMENT_RELATIVE_PATH,
            "sha256": AMENDMENT_SHA256,
            "bytes": AMENDMENT_BYTES,
        },
        "correction_addendum_relative_path": (
            CORRECTION_ADDENDUM_RELATIVE_PATH
        ),
        "correction_addendum_measurement": {
            "relative_path": CORRECTION_ADDENDUM_RELATIVE_PATH,
            "sha256": CORRECTION_ADDENDUM_SHA256,
            "bytes": CORRECTION_ADDENDUM_BYTES,
        },
        "correction_addendum_measurement_from_review_lock_required": True,
        "preflight_correction_addendum_relative_path": (
            PREFLIGHT_CORRECTION_ADDENDUM_RELATIVE_PATH
        ),
        "preflight_correction_addendum_measurement_from_review_lock_required": (
            True
        ),
        "original_single_focused_test_invocation_law_superseded": True,
        "prior_failed_focused_test_candidate_measurements": [
            dict(row)
            for row in PRIOR_FAILED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS
        ],
        "prior_failed_focused_test_candidate_measurements_sha256": (
            batch.canonical_sha256(
                list(PRIOR_FAILED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS)
            )
        ),
        "prior_failed_focused_test_node_ids": list(
            PRIOR_FAILED_FOCUSED_TEST_NODE_IDS
        ),
        "prior_failed_invocation_count": PRIOR_FAILED_INVOCATION_COUNT,
        "prior_failed_pytest_exit_code": PRIOR_FAILED_PYTEST_EXIT_CODE,
        "prior_failed_cloud_call_count": 0,
        "prior_failed_preflight_invocation_count": 0,
        "prior_failed_intent_built": False,
        "prior_failed_realized_outcomes_read": False,
        "prior_failed_collected_passed_counts_available": False,
        "prior_failed_test_output_sha256_available": False,
        "first_corrected_focused_test_candidate_measurements": [
            dict(row)
            for row in FIRST_CORRECTED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS
        ],
        "first_corrected_focused_test_candidate_measurements_sha256": (
            batch.canonical_sha256(
                list(FIRST_CORRECTED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS)
            )
        ),
        "first_corrected_focused_test_output_measurement": {
            "relative_path": FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
            "sha256": FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_SHA256,
            "bytes": FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_BYTES,
        },
        "post_preflight_fix_focused_test_output_relative_path": (
            POST_PREFLIGHT_FIX_FOCUSED_TEST_OUTPUT_RELATIVE_PATH
        ),
        "post_preflight_fix_focused_test_output_measurement_from_review_lock_required": (
            True
        ),
        "first_corrected_candidate_invocation_count": 1,
        "first_corrected_candidate_result": "passed",
        "first_corrected_tests_collected": 271,
        "first_corrected_tests_passed": 271,
        "first_corrected_tests_failed": 0,
        "first_corrected_tests_skipped": 0,
        "first_corrected_test_warnings": 0,
        "first_corrected_pytest_exit_code": 0,
        "first_corrected_pytest_wall_milliseconds": 3515,
        "corrected_candidate_invocation_count_max": (
            POST_PREFLIGHT_FIX_CANDIDATE_INVOCATION_COUNT_MAX
        ),
        "focused_test_total_invocation_count_max": (
            FOCUSED_TEST_TOTAL_INVOCATION_COUNT_MAX
        ),
        "review_lock_relative_path": REVIEW_LOCK_RELATIVE_PATH,
        "review_lock_must_be_tracked_clean_at_head": True,
        "reviewed_recovery_implementation_measurement_set_required": True,
        "review_lock_must_exactly_match_current_source_and_tests": True,
        "review_lock_requires_truthful_corrected_focused_test_history": True,
        "focused_test_command": list(FOCUSED_TEST_COMMAND),
        "corrected_candidate_invocation_count": 1,
        "focused_test_total_invocation_count": 3,
        "corrected_candidate_result": "passed",
        "real_artifact_preflight_schema_version": (
            REAL_ARTIFACT_PREFLIGHT_SCHEMA
        ),
        "real_artifact_preflight_receipt_relative_path": (
            REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH
        ),
        "real_artifact_preflight_command": list(
            REAL_ARTIFACT_PREFLIGHT_COMMAND
        ),
        "first_failed_real_artifact_preflight_command": list(
            REAL_ARTIFACT_PREFLIGHT_COMMAND
        ),
        "first_failed_real_artifact_preflight_invocation_count": 1,
        "first_failed_real_artifact_preflight_exit_code": (
            FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_EXIT_CODE
        ),
        "first_failed_real_artifact_preflight_error_lines": list(
            FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_ERROR_LINES
        ),
        "first_failed_real_artifact_preflight_output_measurement_available": (
            False
        ),
        "first_failed_real_artifact_preflight_receipt_created": False,
        "first_failed_real_artifact_preflight_cloud_read_performed": True,
        "first_failed_real_artifact_preflight_cloud_mutation_executed": False,
        "first_failed_real_artifact_preflight_gcs_publication_count": 0,
        "first_failed_real_artifact_preflight_cloud_submit_count": 0,
        "first_failed_real_artifact_preflight_realized_outcomes_read": False,
        "corrected_real_artifact_preflight_invocation_count": 1,
        "real_artifact_preflight_invocation_count": 2,
        "real_artifact_preflight_invocation_count_max": (
            REAL_ARTIFACT_PREFLIGHT_TOTAL_INVOCATION_COUNT_MAX
        ),
        "outcome_blind_real_artifact_preflight_required_before_review_lock": (
            True
        ),
        "real_artifact_preflight_may_read_review_lock": False,
        "real_artifact_preflight_may_build_replacement_intent": False,
        "real_artifact_preflight_may_publish_gcs": False,
        "real_artifact_preflight_may_submit_cloud_execution": False,
        "real_artifact_preflight_cloud_read_performed": True,
        "real_artifact_preflight_cloud_mutation_executed": False,
        "real_artifact_preflight_gcs_publication_count": 0,
        "real_artifact_preflight_cloud_submit_count": 0,
        "same_process_controller_relative_path": CONTROLLER_RELATIVE_PATH,
        "same_process_controller_test_relative_path": (
            CONTROLLER_TEST_RELATIVE_PATH
        ),
        "review_lock_must_measure_controller_and_both_test_surfaces": True,
        "offline_component_may_publish_replacement_intent": False,
        "offline_component_may_submit_cloud_execution": False,
        "primary_name_only_empty_environment_names": list(
            PRIMARY_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES
        ),
        "primary_name_only_empty_environment_names_sha256": (
            batch.canonical_sha256(
                list(PRIMARY_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES)
            )
        ),
        "primary_name_only_empty_normalization_exact_allowlist_required": True,
        "unknown_primary_name_only_environment_row_is_terminal": True,
        "primary_environment_value_from_or_extra_fields_are_terminal": True,
        "primary_runtime_attempt_ordinal": PRIMARY_RUNTIME_ATTEMPT,
        "replacement_runtime_attempt_ordinal": REPLACEMENT_RUNTIME_ATTEMPT,
        "task_max_retries": 0,
        "max_replacement_worker_executions": (
            MAX_REPLACEMENT_WORKER_EXECUTIONS
        ),
        "replacement_worker_limit_excludes_bridge_verifier": True,
        "max_bridge_verifier_executions_after_worker_success": 1,
        "replacement_execution_envelope": _replacement_execution_envelope(),
        "pre_submit_live_job_exact_description_required": True,
        "pre_submit_live_job_must_equal_replacement_execution_envelope": True,
        "changed_or_ambiguous_live_job_is_terminal": True,
        "replacement_cloud_execution_must_be_separately_named": True,
        "primary_stage_start_identity": _fixed_identity(
            _PRIMARY_STAGE_START_IDENTITY
        ),
        "primary_stage_start_self_sha256": _PRIMARY_STAGE_START_SELF_SHA256,
        "primary_runtime_measurement_identity": _fixed_identity(
            _PRIMARY_RUNTIME_MEASUREMENT_IDENTITY
        ),
        "primary_runtime_measurement_self_sha256": (
            _PRIMARY_RUNTIME_MEASUREMENT_SELF_SHA256
        ),
        "primary_launch_request_identity": _fixed_identity(
            _PRIMARY_LAUNCH_REQUEST_IDENTITY
        ),
        "transport_contract_identity": _fixed_identity(
            _TRANSPORT_CONTRACT_IDENTITY
        ),
        "job_config_identity": _fixed_identity(_JOB_CONFIG_IDENTITY),
        "predecessor_identity": _fixed_identity(_PREDECESSOR_IDENTITY),
        "execution_authority_identity": _fixed_identity(
            _EXECUTION_AUTHORITY_IDENTITY
        ),
        "compute_release_identity": _fixed_identity(_COMPUTE_RELEASE_IDENTITY),
        "result_uri": RESULT_URI,
        "acceptance_uri": ACCEPTANCE_URI,
        "primary_stage_receipt_uri": PRIMARY_STAGE_RECEIPT_URI,
        "replacement_stage_start_uri": REPLACEMENT_STAGE_START_URI,
        "replacement_runtime_measurement_uri": (
            REPLACEMENT_RUNTIME_MEASUREMENT_URI
        ),
        "replacement_intent_uri": REPLACEMENT_INTENT_URI,
        "replacement_success_completion_uri": (
            REPLACEMENT_SUCCESS_COMPLETION_URI
        ),
        "replacement_execution_terminal_uri": (
            REPLACEMENT_EXECUTION_TERMINAL_URI
        ),
        "submission_failure_terminal_create_once_required": True,
        "ambiguous_submission_requires_terminal_receipt": True,
        "nonzero_submission_requires_terminal_receipt": True,
        "malformed_submission_response_requires_terminal_receipt": True,
        "unverified_submitted_envelope_requires_terminal_receipt": True,
        "terminal_receipt_publication_failure_still_consumes_attempt": True,
        "replacement_launch_ownership_uri": REPLACEMENT_LAUNCH_OWNERSHIP_URI,
        "post_submission_receipt_validation_law": (
            _post_submission_receipt_law()
        ),
        "replacement_worker_amendment_uri": REPLACEMENT_WORKER_AMENDMENT_URI,
        "bridge_verifier_launch_request_uri": (
            BRIDGE_VERIFIER_LAUNCH_REQUEST_URI
        ),
        "bridge_verifier_stage_start_uri": BRIDGE_VERIFIER_STAGE_START_URI,
        "bridge_verifier_runtime_measurement_uri": (
            BRIDGE_VERIFIER_RUNTIME_MEASUREMENT_URI
        ),
        "bridge_verifier_stage_receipt_uri": (
            BRIDGE_VERIFIER_STAGE_RECEIPT_URI
        ),
        "bridge_verifier_execution_terminal_uri": (
            BRIDGE_VERIFIER_EXECUTION_TERMINAL_URI
        ),
        "bridge_verifier_launch_ownership_uri": (
            BRIDGE_VERIFIER_LAUNCH_OWNERSHIP_URI
        ),
        "bridge_verifier_completion_uri": BRIDGE_VERIFIER_COMPLETION_URI,
        "supplemental_lane_root_uri": SUPPLEMENTAL_LANE_ROOT_URI,
        "supplemental_panel_root_uri": SUPPLEMENTAL_PANEL_ROOT_URI,
        "absent_before_replacement_uris": list(_ABSENT_BEFORE_REPLACEMENT),
        "absent_effect_surface_uris": list(_ABSENT_EFFECT_SURFACE),
        "new_authorization_requires_intent_uri_absent": True,
        "equal_existing_intent_resolution_requires_intent_uri_absent": False,
        "equal_existing_intent_resolution_must_not_launch": True,
        "primary_attempt_reuse_allowed": False,
        "original_launch_request_reused": False,
        "replacement_intent_create_once_generation_match": 0,
        "replacement_intent_consumed_if_launch_response_ambiguous": True,
        "replacement_intent_delete_allowed": False,
        "replacement_intent_overwrite_allowed": False,
        "replacement_intent_mutation_allowed": False,
        "unequal_replacement_intent_collision_terminal": True,
        "equal_existing_replacement_intent_resolve_only": True,
        "original_or_recovery_object_delete_allowed": False,
        "original_or_recovery_object_overwrite_allowed": False,
        "original_or_recovery_object_mutation_allowed": False,
        "all_recovery_and_bridge_publications_create_once": True,
        "unequal_recovery_or_bridge_collision_terminal": True,
        "launch_ownership_receipt_required": True,
        "existing_replacement_intent_allows_launch": False,
        "second_replacement_allowed": False,
        "replacement_worker_core_runtime_attempt_one_only": True,
        "canonical_worker_result_and_stage_uri_retained": True,
        "bridge_sequence": [
            "replacement-worker-core-run-slate-attempt-01",
            "amended-worker-stage-receipt-at-canonical-uri",
            "distinct-bridge-verifier-attempt-00",
            "standard-v1-ordinal-07-resume-after-bridge-verifier-only",
            "supplemental-lane-0-root",
            "supplemental-panel-root",
        ],
        "bridge_verifier_must_be_distinct_execution": True,
        "ordinal_seven_resume_before_bridge_verifier_allowed": False,
        "v1_lane_root_can_directly_accept_worker_attempt_one": False,
        "separate_success_completion_required": True,
        "supplemental_lane_and_panel_roots_required": True,
        "result_or_effect_content_inspected_for_eligibility": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "platform_replacement_contract_sha256")


def validate_platform_replacement_contract_v1(
    value: object,
) -> dict[str, object]:
    expected = frozen_platform_replacement_contract_v1()
    if not isinstance(value, Mapping) or _canonical(value) != _canonical(expected):
        _fail("platform-replacement contract differs")
    return expected


def validate_primary_terminal_projection_v1(
    value: object,
) -> dict[str, object]:
    """Accept only the exact code-13, zero-output platform failure class."""
    if not isinstance(value, Mapping):
        _fail("primary terminal projection must be one object")
    item = dict(value)
    required = {
        "schema_version",
        "execution_name",
        "job",
        "operation",
        "source_ordinal",
        "runtime_attempt_ordinal",
        "completed_status",
        "task_completed_status",
        "completed_message",
        "execution_describe_argv",
        "execution_describe_stdout_sha256",
        "execution_describe_stdout_bytes",
        "task_describe_argv",
        "task_describe_stdout_sha256",
        "task_describe_stdout_bytes",
        "configured_environment_sha256",
        "configured_environment_entry_count",
        "failed_count",
        "succeeded_count",
        "cancelled_count",
        "task_count",
        "parallelism",
        "max_retries",
        "task_timeout_seconds",
        "service_account",
        "image",
        "cpu",
        "memory",
        "cloud_task_name",
        "task_spec",
        "task_status_index_present",
        "task_status_retried_present",
        "task_last_attempt_exit_code_present",
        "last_attempt_status_code",
        "last_attempt_status_message",
        "execution_completed_message_exit_code",
        "primary_stage_start_identity",
        "primary_runtime_measurement_identity",
        "original_launch_request_identity",
        "transport_contract_identity",
        "job_config_identity",
        "predecessor_identity",
        "execution_authority_identity",
        "compute_release_identity",
        "runtime_evidence_volume",
        "execution_terminal_exactly_validated",
        "task_terminal_exactly_validated",
        "execution_envelope_exactly_validated",
        "execution_environment_exactly_validated",
        "frozen_runtime_payload_exactly_validated",
        "frozen_runtime_payload_sha256",
        "frozen_runtime_payload_bytes",
        "system_platform_error_observed",
        "result_or_effect_content_inspected",
        "realized_outcomes_read",
    }
    if set(item) != required:
        _fail("primary terminal projection fields differ")
    message = item.get("completed_message")
    task_message = item.get("last_attempt_status_message")
    exact_integer_fields = {
        "source_ordinal": SOURCE_ORDINAL,
        "runtime_attempt_ordinal": PRIMARY_RUNTIME_ATTEMPT,
        "failed_count": 1,
        "succeeded_count": 0,
        "cancelled_count": 0,
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "task_timeout_seconds": transport.TASK_TIMEOUT_SECONDS,
        "last_attempt_status_code": 13,
        "execution_completed_message_exit_code": 0,
        "frozen_runtime_payload_bytes": FROZEN_PRIMARY_RUNTIME_PAYLOAD_BYTES,
    }
    if any(
        type(item.get(field)) is not int or item.get(field) != expected
        for field, expected in exact_integer_fields.items()
    ):
        _fail("primary terminal integer evidence differs")
    describe_bytes = (
        item.get("execution_describe_stdout_bytes"),
        item.get("task_describe_stdout_bytes"),
    )
    describe_hashes = (
        item.get("execution_describe_stdout_sha256"),
        item.get("task_describe_stdout_sha256"),
        item.get("configured_environment_sha256"),
    )
    if (
        any(type(value) is not int or value < 1 for value in describe_bytes)
        or any(
            not isinstance(value, str) or _SHA256.fullmatch(value) is None
            for value in describe_hashes
        )
        or item.get("execution_describe_argv") != list(EXECUTION_DESCRIBE_ARGV)
        or item.get("task_describe_argv") != list(TASK_DESCRIBE_ARGV)
        or type(item.get("configured_environment_entry_count")) is not int
        or item.get("configured_environment_entry_count") < 1
    ):
        _fail("primary terminal exact-name describe provenance differs")
    if (
        item.get("schema_version") != TERMINAL_PROJECTION_SCHEMA
        or item.get("execution_name") != FAILED_EXECUTION
        or item.get("job") != REUSE_JOB
        or item.get("operation") != OPERATION
        or item.get("completed_status") != "False"
        or item.get("task_completed_status") != "False"
        or message != _COMPLETED_MESSAGE
        or task_message != _LAST_ATTEMPT_MESSAGE
        or item.get("service_account") != SERVICE_ACCOUNT
        or item.get("image") != FROZEN_D2_URI
        or item.get("cpu") != "8"
        or item.get("memory") != "32Gi"
        or item.get("cloud_task_name") != FAILED_TASK
        or item.get("task_spec") != {}
        or item.get("task_status_index_present") is not False
        or item.get("task_status_retried_present") is not False
        or item.get("task_last_attempt_exit_code_present") is not False
        or _identity(
            item.get("primary_stage_start_identity"),
            label="terminal primary stage start",
        )
        != _fixed_identity(_PRIMARY_STAGE_START_IDENTITY)
        or _identity(
            item.get("primary_runtime_measurement_identity"),
            label="terminal primary runtime measurement",
        )
        != _fixed_identity(_PRIMARY_RUNTIME_MEASUREMENT_IDENTITY)
        or _identity(
            item.get("original_launch_request_identity"),
            label="terminal original launch request",
        )
        != _fixed_identity(_PRIMARY_LAUNCH_REQUEST_IDENTITY)
        or _identity(
            item.get("transport_contract_identity"),
            label="terminal transport contract",
        )
        != _fixed_identity(_TRANSPORT_CONTRACT_IDENTITY)
        or _identity(
            item.get("job_config_identity"), label="terminal job config"
        )
        != _fixed_identity(_JOB_CONFIG_IDENTITY)
        or _identity(
            item.get("predecessor_identity"), label="terminal predecessor"
        )
        != _fixed_identity(_PREDECESSOR_IDENTITY)
        or _identity(
            item.get("execution_authority_identity"),
            label="terminal execution authority",
        )
        != _fixed_identity(_EXECUTION_AUTHORITY_IDENTITY)
        or _identity(
            item.get("compute_release_identity"),
            label="terminal compute release",
        )
        != _fixed_identity(_COMPUTE_RELEASE_IDENTITY)
        or item.get("runtime_evidence_volume") != _runtime_evidence_volume()
        or item.get("execution_terminal_exactly_validated") is not True
        or item.get("task_terminal_exactly_validated") is not True
        or item.get("execution_envelope_exactly_validated") is not True
        or item.get("execution_environment_exactly_validated") is not True
        or item.get("frozen_runtime_payload_exactly_validated") is not True
        or item.get("frozen_runtime_payload_sha256")
        != FROZEN_PRIMARY_RUNTIME_PAYLOAD_SHA256
        or item.get("system_platform_error_observed") is not True
        or item.get("result_or_effect_content_inspected") is not False
        or item.get("realized_outcomes_read") is not False
    ):
        _fail("primary terminal platform evidence differs")
    return item


def _exact_read_json(
    backend: transport.JournalBackend,
    identity: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    retained = _identity(identity, label=label)
    raw = backend.read(retained)
    if (
        not isinstance(raw, bytes)
        or len(raw) != retained["bytes"]
        or sha256(raw).hexdigest() != retained["sha256"]
    ):
        _fail(f"{label} exact read differs")
    return transport.strict_json(raw, label=label)


def _reopen_fixed_primary_lineage_v1(
    backend: transport.JournalBackend,
) -> dict[str, object]:
    """Replay the consumed request, exact start, D2, predecessor and releases."""
    start_identity = _fixed_identity(_PRIMARY_STAGE_START_IDENTITY)
    start = _exact_read_json(backend, start_identity, label="primary stage start")
    if start.get("stage_start_sha256") != _PRIMARY_STAGE_START_SELF_SHA256:
        _fail("primary stage-start self-hash differs")
    transport_sha = start.get("transport_contract_sha256")
    if not isinstance(transport_sha, str) or _SHA256.fullmatch(transport_sha) is None:
        _fail("primary stage-start transport hash differs")
    reopened = transport.reopen_stage_launch_authority_v1(
        stage_start=start,
        transport_contract_sha256=transport_sha,
        operation=OPERATION,
        source_ordinal=SOURCE_ORDINAL,
        runtime_attempt_ordinal=PRIMARY_RUNTIME_ATTEMPT,
        cloud_execution_name=FAILED_EXECUTION,
        read_exact=backend.read,
    )
    request = reopened["launch_request"]
    proof = reopened["launch_publication_proof"]
    contract_identity = _identity(
        reopened["transport_contract_identity"],
        label="reopened transport contract",
    )
    predecessor = _fixed_identity(_PREDECESSOR_IDENTITY)
    if (
        start_identity != _fixed_identity(_PRIMARY_STAGE_START_IDENTITY)
        or start.get("stage_start_uri") != PRIMARY_STAGE_START_URI
        or start.get("runtime_attempt_ordinal") != PRIMARY_RUNTIME_ATTEMPT
        or start.get("cloud_execution_name") != FAILED_EXECUTION
        or start.get("cloud_job") != REUSE_JOB
        or start.get("runtime_image") != _image()
        or start.get("max_retries") != 0
        or start.get("predecessor_identities") != [predecessor]
        or _identity(
            start.get("launch_request_identity"),
            label="primary start launch request",
        )
        != _fixed_identity(_PRIMARY_LAUNCH_REQUEST_IDENTITY)
        or contract_identity != _fixed_identity(_TRANSPORT_CONTRACT_IDENTITY)
        or _identity(
            request.get("job_config_identity"), label="primary request job config"
        )
        != _fixed_identity(_JOB_CONFIG_IDENTITY)
        or request.get("immutable_image") != _image()
        or request.get("runtime_attempt_ordinal") != PRIMARY_RUNTIME_ATTEMPT
        or request.get("request_consumed_even_if_execution_response_is_ambiguous")
        is not True
        or request.get("relaunch_allowed") is not False
        or request.get("max_retries") != 0
        or request.get("predecessor_identities") != [predecessor]
        or _identity(proof.get("target_identity"), label="primary proof target")
        != _fixed_identity(_PRIMARY_LAUNCH_REQUEST_IDENTITY)
    ):
        _fail("primary consumed launch/start lineage differs")
    transport.validate_stage_predecessor_inputs_v1(
        transport_contract_sha256=transport_sha,
        operation=OPERATION,
        source_ordinal=SOURCE_ORDINAL,
        predecessor_identities=[predecessor],
        read_exact=backend.read,
    )

    primary_runtime_identity = _fixed_identity(
        _PRIMARY_RUNTIME_MEASUREMENT_IDENTITY
    )
    primary_runtime = _exact_read_json(
        backend,
        primary_runtime_identity,
        label="primary worker runtime measurement",
    )
    if (
        primary_runtime.get("runtime_measurement_sha256")
        != _PRIMARY_RUNTIME_MEASUREMENT_SELF_SHA256
    ):
        _fail("primary runtime-measurement self-hash differs")
    published_runtime = execution._validate_published_runtime_measurement_v1(
        primary_runtime,
        role="worker",
        output_prefix=transport.OUTPUT_PREFIX,
        read_exact=backend.read,
    )
    if (
        primary_runtime_identity["uri"] != PRIMARY_RUNTIME_MEASUREMENT_URI
        or published_runtime.get("runtime_attempt_ordinal")
        != PRIMARY_RUNTIME_ATTEMPT
        or published_runtime.get("role") != "worker"
        or published_runtime.get("release_runtime_verified") is not True
        or published_runtime.get("immutable_image") != _image()
        or published_runtime.get("uses_realized_outcomes") is not False
    ):
        _fail("primary runtime measurement differs from frozen attempt 0")

    compute_identity = _fixed_identity(_COMPUTE_RELEASE_IDENTITY)
    compute = transport.reopen_compute_release_v1(
        compute_release_identity=compute_identity,
        read_exact=backend.read,
    )
    if (
        _identity(
            compute.get("transport_contract_identity"),
            label="compute-release transport contract",
        )
        != contract_identity
        or compute.get("transport_contract_sha256") != transport_sha
        or compute.get("scale_out_licensed") is not True
    ):
        _fail("compute release differs from the primary transport")

    authority_identity = _fixed_identity(_EXECUTION_AUTHORITY_IDENTITY)
    authority = execution.reopen_published_t230_execution_authority_v1(
        execution_authority_identity=authority_identity,
        read_exact=backend.read,
    )
    if (
        authority.get("immutable_image") != _image()
        or authority.get("output_prefix") != transport.OUTPUT_PREFIX
        or authority.get("simulated_execution_only") is not True
    ):
        _fail("execution authority differs from frozen D2/output")
    manifest_identity = _identity(
        authority.get("manifest_identity"), label="execution manifest"
    )
    image_evidence_identity = _identity(
        authority.get("image_evidence_identity"),
        label="execution authority image evidence",
    )
    manifest = execution.reopen_t230_panel_execution_manifest_v1(
        manifest_identity=manifest_identity,
        read_exact=backend.read,
    )
    members = manifest.get("source_members")
    if not isinstance(members, Sequence) or isinstance(members, (str, bytes)):
        _fail("execution manifest source membership differs")
    if len(members) != 54 or not isinstance(members[SOURCE_ORDINAL], Mapping):
        _fail("execution manifest does not contain exact ordinal 6")
    member = dict(members[SOURCE_ORDINAL])
    if (
        member.get("source_ordinal") != SOURCE_ORDINAL
        or member.get("slate_id") != "2023-w07"
        or member.get("result_uri") != RESULT_URI
        or member.get("acceptance_uri") != ACCEPTANCE_URI
    ):
        _fail("ordinal-6 source member differs")
    return {
        "transport_contract_sha256": transport_sha,
        "transport_contract_identity": contract_identity,
        "job_config_identity": _fixed_identity(_JOB_CONFIG_IDENTITY),
        "predecessor_identities": [predecessor],
        "primary_stage_start_identity": start_identity,
        "primary_stage_start_sha256": start["stage_start_sha256"],
        "primary_runtime_measurement_identity": primary_runtime_identity,
        "primary_runtime_measurement_sha256": primary_runtime[
            "runtime_measurement_sha256"
        ],
        "primary_launch_request_identity": _fixed_identity(
            _PRIMARY_LAUNCH_REQUEST_IDENTITY
        ),
        "primary_launch_publication_proof": dict(proof),
        "execution_authority_identity": authority_identity,
        "execution_authority_sha256": authority["execution_authority_sha256"],
        "image_evidence_identity": image_evidence_identity,
        "manifest_identity": manifest_identity,
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "compute_release_identity": compute_identity,
        "compute_release_sha256": compute["compute_release_sha256"],
        "result_uri": RESULT_URI,
        "acceptance_uri": ACCEPTANCE_URI,
    }


def reopen_fixed_primary_lineage_for_controller_v1(
    *,
    backend: transport.JournalBackend,
) -> dict[str, object]:
    """Expose the exact no-authority lineage projection to the controller."""
    return _reopen_fixed_primary_lineage_v1(backend)


def _validate_lineage_projection(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("primary lineage projection must be one object")
    item = dict(value)
    required = {
        "transport_contract_sha256",
        "transport_contract_identity",
        "job_config_identity",
        "predecessor_identities",
        "primary_stage_start_identity",
        "primary_stage_start_sha256",
        "primary_runtime_measurement_identity",
        "primary_runtime_measurement_sha256",
        "primary_launch_request_identity",
        "primary_launch_publication_proof",
        "execution_authority_identity",
        "execution_authority_sha256",
        "image_evidence_identity",
        "manifest_identity",
        "execution_manifest_sha256",
        "compute_release_identity",
        "compute_release_sha256",
        "result_uri",
        "acceptance_uri",
    }
    if set(item) != required:
        _fail("primary lineage projection fields differ")
    hash_fields = (
        "transport_contract_sha256",
        "primary_stage_start_sha256",
        "primary_runtime_measurement_sha256",
        "execution_authority_sha256",
        "execution_manifest_sha256",
        "compute_release_sha256",
    )
    if any(
        not isinstance(item.get(field), str)
        or _SHA256.fullmatch(str(item[field])) is None
        for field in hash_fields
    ):
        _fail("primary lineage hash differs")
    image_evidence_identity = _identity(
        item.get("image_evidence_identity"),
        label="lineage image evidence",
    )
    if (
        _identity(
            item.get("transport_contract_identity"), label="lineage contract"
        )
        != _fixed_identity(_TRANSPORT_CONTRACT_IDENTITY)
        or _identity(item.get("job_config_identity"), label="lineage job config")
        != _fixed_identity(_JOB_CONFIG_IDENTITY)
        or item.get("predecessor_identities")
        != [_fixed_identity(_PREDECESSOR_IDENTITY)]
        or _identity(
            item.get("primary_stage_start_identity"), label="lineage stage start"
        )
        != _fixed_identity(_PRIMARY_STAGE_START_IDENTITY)
        or item.get("primary_stage_start_sha256")
        != _PRIMARY_STAGE_START_SELF_SHA256
        or _identity(
            item.get("primary_runtime_measurement_identity"),
            label="lineage runtime measurement",
        )
        != _fixed_identity(_PRIMARY_RUNTIME_MEASUREMENT_IDENTITY)
        or item.get("primary_runtime_measurement_sha256")
        != _PRIMARY_RUNTIME_MEASUREMENT_SELF_SHA256
        or _identity(
            item.get("primary_launch_request_identity"),
            label="lineage launch request",
        )
        != _fixed_identity(_PRIMARY_LAUNCH_REQUEST_IDENTITY)
        or _identity(
            item.get("execution_authority_identity"),
            label="lineage execution authority",
        )
        != _fixed_identity(_EXECUTION_AUTHORITY_IDENTITY)
        or item.get("image_evidence_identity") != image_evidence_identity
        or _identity(
            item.get("compute_release_identity"), label="lineage compute release"
        )
        != _fixed_identity(_COMPUTE_RELEASE_IDENTITY)
        or item.get("result_uri") != RESULT_URI
        or item.get("acceptance_uri") != ACCEPTANCE_URI
    ):
        _fail("primary lineage fixed identity differs")
    proof = item.get("primary_launch_publication_proof")
    if (
        not isinstance(proof, Mapping)
        or set(proof)
        != {"intent_identity", "target_identity", "completion_identity"}
        or _identity(proof.get("target_identity"), label="lineage proof target")
        != _fixed_identity(_PRIMARY_LAUNCH_REQUEST_IDENTITY)
    ):
        _fail("primary lineage publication proof differs")
    return item


def _absence_rows() -> list[dict[str, object]]:
    return [
        {"uri": uri, "present": False, "content_inspected": False}
        for uri in _ABSENT_BEFORE_REPLACEMENT
    ]


def validate_replacement_live_job_projection_v1(
    value: object,
) -> dict[str, object]:
    """Validate the exact live reused-job state observed before authorization."""
    if not isinstance(value, Mapping):
        _fail("replacement live-job projection must be one object")
    item = dict(value)
    if set(item) != {
        "schema_version",
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
        "describe_argv",
        "describe_stdout_sha256",
        "describe_stdout_bytes",
        "cloud_describe_exactly_validated",
    }:
        _fail("replacement live-job projection fields differ")
    exact_integers = {
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "task_timeout_seconds": transport.TASK_TIMEOUT_SECONDS,
    }
    if any(
        type(item.get(field)) is not int or item.get(field) != expected
        for field, expected in exact_integers.items()
    ):
        _fail("replacement live-job integer envelope differs")
    if (
        item.get("schema_version") != LIVE_JOB_PROJECTION_SCHEMA
        or item.get("job") != REUSE_JOB
        or item.get("image") != FROZEN_D2_URI
        or item.get("service_account") != SERVICE_ACCOUNT
        or item.get("cpu") != "8"
        or item.get("memory") != "32Gi"
        or item.get("command") != ["bash"]
        or item.get("args")
        != [
            "-ceu",
            "python scripts/run_corpus_extreme_tail_panel_transport_v1.py parked",
        ]
        or item.get("configured_environment") != {}
        or item.get("runtime_evidence_volume") != _runtime_evidence_volume()
        or item.get("describe_argv") != list(LIVE_JOB_DESCRIBE_ARGV)
        or not isinstance(item.get("describe_stdout_sha256"), str)
        or _SHA256.fullmatch(str(item["describe_stdout_sha256"])) is None
        or type(item.get("describe_stdout_bytes")) is not int
        or item.get("describe_stdout_bytes") < 1
        or item.get("cloud_describe_exactly_validated") is not True
    ):
        _fail("replacement live-job exact description differs")
    return item


def _validate_replacement_worker_launch_plan(
    value: object,
) -> dict[str, object]:
    """Validate the plan's contract-facing surface and retain its exact bytes."""
    if not isinstance(value, Mapping):
        _fail("replacement worker launch plan must be one object")
    item = dict(value)
    _validate_self_hash(
        item,
        field="worker_launch_plan_sha256",
        label="replacement worker launch plan",
    )
    _false_authorities(item, label="replacement worker launch plan")
    exact_integers = {
        "source_ordinal": SOURCE_ORDINAL,
        "runtime_attempt_ordinal": REPLACEMENT_RUNTIME_ATTEMPT,
        "max_submission_calls": 1,
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "task_timeout_seconds": transport.TASK_TIMEOUT_SECONDS,
    }
    if any(
        type(item.get(field)) is not int or item.get(field) != expected
        for field, expected in exact_integers.items()
    ):
        _fail("replacement worker launch-plan integer envelope differs")
    image_evidence_identity = _identity(
        item.get("image_evidence_identity"),
        label="worker plan image evidence",
    )
    if (
        item.get("schema_version") != WORKER_LAUNCH_PLAN_SCHEMA
        or item.get("run_id") != transport.RUN_ID
        or item.get("project") != transport.PROJECT
        or item.get("region") != transport.REGION
        or item.get("reuse_job") != REUSE_JOB
        or item.get("operation") != OPERATION
        or item.get("immutable_image") != _image()
        or item.get("execution_envelope") != _replacement_execution_envelope()
        or item.get("post_submission_receipt_validation_law")
        != _post_submission_receipt_law()
        or item.get("post_submission_receipt_validation_law_sha256")
        != batch.canonical_sha256(_post_submission_receipt_law())
        or item.get("image_evidence_identity") != image_evidence_identity
        or _identity(
            item.get("execution_authority_identity"),
            label="worker plan execution authority",
        )
        != _fixed_identity(_EXECUTION_AUTHORITY_IDENTITY)
        or _identity(
            item.get("compute_release_identity"),
            label="worker plan compute release",
        )
        != _fixed_identity(_COMPUTE_RELEASE_IDENTITY)
        or _identity(
            item.get("predecessor_identity"),
            label="worker plan predecessor",
        )
        != _fixed_identity(_PREDECESSOR_IDENTITY)
        or item.get("replacement_intent_uri") != REPLACEMENT_INTENT_URI
        or item.get("launch_ownership_uri") != REPLACEMENT_LAUNCH_OWNERSHIP_URI
        or item.get("replacement_stage_start_uri") != REPLACEMENT_STAGE_START_URI
        or item.get("canonical_result_uri") != RESULT_URI
        or item.get("canonical_worker_stage_uri") != PRIMARY_STAGE_RECEIPT_URI
        or item.get("submission_mode") != "async-single-request"
        or item.get("same_process_intent_create_and_submission_required")
        is not True
        or item.get("runtime_waits_for_launch_ownership_and_stage_start")
        is not True
        or item.get("transport_run_stage_used") is not False
        or item.get("original_launch_request_reused") is not False
        or item.get("primary_runtime_attempt_reused") is not False
        or item.get("second_replacement_allowed") is not False
        or item.get("request_consumed_on_ambiguous_submission") is not True
        or item.get("result_or_effect_content_inspected_before_submission")
        is not False
    ):
        _fail("replacement worker launch-plan contract surface differs")
    return item


def _build_real_artifact_preflight_receipt_v1(
    *,
    terminal_projection: Mapping[str, object],
    primary_lineage: Mapping[str, object],
    correction_addendum_measurement: Mapping[str, object],
    preflight_correction_addendum_measurement: Mapping[str, object],
    first_corrected_focused_test_output_measurement: Mapping[str, object],
    post_preflight_fix_focused_test_output_measurement: Mapping[str, object],
    recovery_implementation_measurements: Sequence[Mapping[str, object]],
    replacement_worker_launch_plan: Mapping[str, object],
    replacement_live_job_projection: Mapping[str, object],
) -> dict[str, object]:
    terminal = validate_primary_terminal_projection_v1(terminal_projection)
    lineage = _validate_lineage_projection(primary_lineage)
    correction_addendum = _validate_file_measurement(
        correction_addendum_measurement,
        relative_path=CORRECTION_ADDENDUM_RELATIVE_PATH,
        label="real-artifact preflight correction addendum",
    )
    if correction_addendum != {
        "relative_path": CORRECTION_ADDENDUM_RELATIVE_PATH,
        "sha256": CORRECTION_ADDENDUM_SHA256,
        "bytes": CORRECTION_ADDENDUM_BYTES,
    }:
        _fail("real-artifact preflight first correction addendum differs")
    preflight_correction_addendum = _validate_file_measurement(
        preflight_correction_addendum_measurement,
        relative_path=PREFLIGHT_CORRECTION_ADDENDUM_RELATIVE_PATH,
        label="real-artifact preflight correction addendum",
    )
    first_corrected_output = _validate_file_measurement(
        first_corrected_focused_test_output_measurement,
        relative_path=FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
        label="first corrected focused-test output",
    )
    if first_corrected_output != {
        "relative_path": FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
        "sha256": FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_SHA256,
        "bytes": FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_BYTES,
    }:
        _fail("real-artifact preflight first corrected test output differs")
    post_preflight_fix_output = _validate_file_measurement(
        post_preflight_fix_focused_test_output_measurement,
        relative_path=POST_PREFLIGHT_FIX_FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
        label="post-preflight-fix focused-test output",
    )
    implementations = _validate_implementation_measurements(
        recovery_implementation_measurements
    )
    launch_plan = _validate_replacement_worker_launch_plan(
        replacement_worker_launch_plan
    )
    live_job = validate_replacement_live_job_projection_v1(
        replacement_live_job_projection
    )
    image_evidence = _identity(
        lineage.get("image_evidence_identity"),
        label="preflight lineage image evidence",
    )
    flags_template = launch_plan.get("execution_flags_template")
    if (
        _identity(
            launch_plan.get("image_evidence_identity"),
            label="preflight worker-plan image evidence",
        )
        != image_evidence
        or launch_plan.get("flags_path")
        != REAL_ARTIFACT_PREFLIGHT_FLAGS_PATH
        or not isinstance(flags_template, Mapping)
    ):
        _fail("real-artifact preflight worker plan differs")
    body = {
        "schema_version": REAL_ARTIFACT_PREFLIGHT_SCHEMA,
        "run_id": transport.RUN_ID,
        "command": list(REAL_ARTIFACT_PREFLIGHT_COMMAND),
        "invocation_count": 2,
        "invocation_count_max": REAL_ARTIFACT_PREFLIGHT_TOTAL_INVOCATION_COUNT_MAX,
        "amendment_measurement": {
            "relative_path": AMENDMENT_RELATIVE_PATH,
            "sha256": AMENDMENT_SHA256,
            "bytes": AMENDMENT_BYTES,
        },
        "correction_addendum_measurement": correction_addendum,
        "preflight_correction_addendum_measurement": (
            preflight_correction_addendum
        ),
        "first_corrected_focused_test_output_measurement": (
            first_corrected_output
        ),
        "post_preflight_fix_focused_test_output_measurement": (
            post_preflight_fix_output
        ),
        "first_failed_invocation_count": 1,
        "first_failed_command": list(REAL_ARTIFACT_PREFLIGHT_COMMAND),
        "first_failed_exit_code": FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_EXIT_CODE,
        "first_failed_error_lines": list(
            FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_ERROR_LINES
        ),
        "first_failed_output_measurement_available": False,
        "first_failed_receipt_created": False,
        "first_failed_cloud_read_performed": True,
        "first_failed_cloud_mutation_executed": False,
        "first_failed_gcs_publication_count": 0,
        "first_failed_cloud_submit_count": 0,
        "first_failed_realized_outcomes_read": False,
        "corrected_invocation_count": 1,
        "reviewed_implementation_measurements": implementations,
        "reviewed_implementation_measurements_sha256": (
            batch.canonical_sha256(implementations)
        ),
        "primary_terminal_projection": terminal,
        "primary_terminal_projection_sha256": batch.canonical_sha256(
            terminal
        ),
        "frozen_primary_lineage": lineage,
        "frozen_primary_lineage_sha256": batch.canonical_sha256(lineage),
        "image_evidence_identity": image_evidence,
        "replacement_worker_launch_plan": launch_plan,
        "replacement_worker_launch_plan_sha256": launch_plan[
            "worker_launch_plan_sha256"
        ],
        "live_job_projection": live_job,
        "live_job_projection_sha256": batch.canonical_sha256(live_job),
        "absence_uris": list(_ABSENT_BEFORE_REPLACEMENT),
        "absence_probe_count": len(_ABSENT_BEFORE_REPLACEMENT) * 2,
        "all_effect_surface_absent": True,
        "cloud_read_commands": [
            list(EXECUTION_DESCRIBE_ARGV),
            list(TASK_DESCRIBE_ARGV),
            list(LIVE_JOB_DESCRIBE_ARGV),
        ],
        "cloud_read_command_count": 3,
        "gcs_read_scope": (
            "generation-pinned-fixed-lineage-plus-exact-name-"
            "metadata-only-absence"
        ),
        "flags_template_path": REAL_ARTIFACT_PREFLIGHT_FLAGS_PATH,
        "flags_template_sha256": batch.canonical_sha256(flags_template),
        "flags_template_bytes": len(_canonical(flags_template)),
        "passed": True,
        "cloud_read_performed": True,
        "cloud_mutation_executed": False,
        "gcs_publication_count": 0,
        "cloud_submit_count": 0,
        "realized_outcomes_read": False,
        "result_or_effect_content_inspected": False,
        "review_lock_read": False,
        "intent_built": False,
        "intent_published": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "real_artifact_preflight_sha256")


def validate_platform_replacement_real_artifact_preflight_v1(
    value: object,
    *,
    expected_implementation_measurements: (
        Sequence[Mapping[str, object]] | None
    ) = None,
) -> dict[str, object]:
    """Pure-replay the tracked read-only reality-contact receipt."""
    if not isinstance(value, Mapping):
        _fail("real-artifact preflight receipt must be one object")
    item = dict(value)
    _validate_self_hash(
        item,
        field="real_artifact_preflight_sha256",
        label="real-artifact preflight",
    )
    _false_authorities(item, label="real-artifact preflight")
    implementations_value = item.get("reviewed_implementation_measurements")
    implementations = _validate_implementation_measurements(
        implementations_value
    )
    if expected_implementation_measurements is not None:
        expected_implementations = _validate_implementation_measurements(
            expected_implementation_measurements
        )
        if implementations != expected_implementations:
            _fail("real-artifact preflight implementation bytes differ")
    expected = _build_real_artifact_preflight_receipt_v1(
        terminal_projection=item.get("primary_terminal_projection", {}),
        primary_lineage=item.get("frozen_primary_lineage", {}),
        correction_addendum_measurement=item.get(
            "correction_addendum_measurement", {}
        ),
        preflight_correction_addendum_measurement=item.get(
            "preflight_correction_addendum_measurement", {}
        ),
        first_corrected_focused_test_output_measurement=item.get(
            "first_corrected_focused_test_output_measurement", {}
        ),
        post_preflight_fix_focused_test_output_measurement=item.get(
            "post_preflight_fix_focused_test_output_measurement", {}
        ),
        recovery_implementation_measurements=implementations,
        replacement_worker_launch_plan=item.get(
            "replacement_worker_launch_plan", {}
        ),
        replacement_live_job_projection=item.get(
            "live_job_projection", {}
        ),
    )
    if _canonical(item) != _canonical(expected):
        _fail("real-artifact preflight receipt differs after replay")
    return expected


def preflight_platform_replacement_real_artifacts_v1(
    *,
    backend: PlatformReplacementBackend,
    replacement_worker_launch_plan: Mapping[str, object],
    replacement_live_job_projection: Mapping[str, object],
) -> dict[str, object]:
    """Read-only reality contact; never reads a lock, builds an intent or writes."""
    terminal = validate_primary_terminal_projection_v1(
        backend.observe_primary_terminal(FAILED_EXECUTION)
    )
    _amendment_measurement()
    correction_addendum = _correction_addendum_measurement()
    preflight_correction_addendum = (
        _preflight_correction_addendum_measurement()
    )
    first_corrected_output = _first_corrected_focused_test_output_measurement()
    post_preflight_fix_output = (
        _post_preflight_fix_focused_test_output_measurement()
    )
    lineage = _reopen_fixed_primary_lineage_v1(backend)
    _require_absent(backend, _ABSENT_BEFORE_REPLACEMENT)
    implementations = _implementation_measurements()
    receipt = _build_real_artifact_preflight_receipt_v1(
        terminal_projection=terminal,
        primary_lineage=lineage,
        correction_addendum_measurement=correction_addendum,
        preflight_correction_addendum_measurement=(
            preflight_correction_addendum
        ),
        first_corrected_focused_test_output_measurement=(
            first_corrected_output
        ),
        post_preflight_fix_focused_test_output_measurement=(
            post_preflight_fix_output
        ),
        recovery_implementation_measurements=implementations,
        replacement_worker_launch_plan=replacement_worker_launch_plan,
        replacement_live_job_projection=replacement_live_job_projection,
    )
    _require_absent(backend, _ABSENT_BEFORE_REPLACEMENT)
    return receipt


def _require_absent(
    backend: PlatformReplacementBackend,
    uris: Sequence[str],
) -> None:
    for uri in uris:
        retained = backend.probe_known_uri_metadata(uri)
        if retained is None:
            continue
        if not isinstance(retained, Mapping):
            _fail(f"replacement absence probe is ambiguous: {uri}")
        _fail(f"replacement precondition object exists without content read: {uri}")


def require_platform_replacement_surface_absent_v1(
    *,
    backend: PlatformReplacementBackend,
) -> None:
    """Repeat the exact-name metadata-only census at the controller boundary."""
    _require_absent(backend, _ABSENT_BEFORE_REPLACEMENT)


def build_platform_replacement_intent_v1(
    *,
    terminal_projection: Mapping[str, object],
    primary_lineage: Mapping[str, object],
    review_lock_binding: Mapping[str, object],
    review_lock: Mapping[str, object],
    recovery_implementation_measurements: Sequence[Mapping[str, object]],
    replacement_worker_launch_plan: Mapping[str, object],
    replacement_live_job_projection: Mapping[str, object],
) -> dict[str, object]:
    terminal = validate_primary_terminal_projection_v1(terminal_projection)
    lineage = _validate_lineage_projection(primary_lineage)
    implementations = _validate_implementation_measurements(
        recovery_implementation_measurements
    )
    lock = validate_recovery_review_lock_v1(
        review_lock,
        expected_implementation_measurements=implementations,
    )
    lock_binding = _validate_review_lock_binding(
        review_lock_binding,
        review_lock=lock,
    )
    launch_plan = _validate_replacement_worker_launch_plan(
        replacement_worker_launch_plan
    )
    live_job = validate_replacement_live_job_projection_v1(
        replacement_live_job_projection
    )
    if _identity(
        launch_plan.get("image_evidence_identity"),
        label="worker plan image evidence",
    ) != _identity(
        lineage.get("image_evidence_identity"),
        label="lineage image evidence",
    ):
        _fail("worker launch-plan image evidence differs from frozen authority")
    contract = frozen_platform_replacement_contract_v1()
    body = {
        "schema_version": INTENT_SCHEMA,
        "run_id": transport.RUN_ID,
        "platform_replacement_contract_sha256": contract[
            "platform_replacement_contract_sha256"
        ],
        "operation": OPERATION,
        "source_ordinal": SOURCE_ORDINAL,
        "lane_ordinal": LANE_ORDINAL,
        "reuse_job": REUSE_JOB,
        "failed_execution": FAILED_EXECUTION,
        "immutable_image": _image(),
        "service_account": SERVICE_ACCOUNT,
        "amendment_measurement": {
            "relative_path": AMENDMENT_RELATIVE_PATH,
            "sha256": AMENDMENT_SHA256,
            "bytes": AMENDMENT_BYTES,
        },
        "correction_addendum_measurement": lock[
            "correction_addendum_measurement"
        ],
        "preflight_correction_addendum_measurement": lock[
            "preflight_correction_addendum_measurement"
        ],
        "first_corrected_focused_test_output_measurement": lock[
            "first_corrected_focused_test_output_measurement"
        ],
        "post_preflight_fix_focused_test_output_measurement": lock[
            "post_preflight_fix_focused_test_output_measurement"
        ],
        "prior_failed_invocation_count": PRIOR_FAILED_INVOCATION_COUNT,
        "first_corrected_candidate_invocation_count": lock[
            "first_corrected_candidate_invocation_count"
        ],
        "corrected_candidate_invocation_count": lock[
            "corrected_candidate_invocation_count"
        ],
        "focused_test_total_invocation_count": lock[
            "focused_test_total_invocation_count"
        ],
        "corrected_candidate_result": lock["corrected_candidate_result"],
        "no_launch_authority_before_corrected_pass_preflight_and_lock": True,
        "review_lock_binding": lock_binding,
        "review_lock": lock,
        "review_lock_sha256": lock["review_lock_sha256"],
        "real_artifact_preflight_receipt_measurement": lock[
            "real_artifact_preflight_receipt_measurement"
        ],
        "real_artifact_preflight_command": list(
            REAL_ARTIFACT_PREFLIGHT_COMMAND
        ),
        "first_failed_real_artifact_preflight_invocation_count": 1,
        "first_failed_real_artifact_preflight_exit_code": (
            FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_EXIT_CODE
        ),
        "first_failed_real_artifact_preflight_receipt_created": False,
        "corrected_real_artifact_preflight_invocation_count": 1,
        "real_artifact_preflight_invocation_count": 2,
        "real_artifact_preflight_passed": True,
        "real_artifact_preflight_cloud_read_performed": True,
        "real_artifact_preflight_cloud_mutation_executed": False,
        "real_artifact_preflight_gcs_publication_count": 0,
        "real_artifact_preflight_cloud_submit_count": 0,
        "real_artifact_preflight_realized_outcomes_read": False,
        "recovery_implementation_measurements": implementations,
        "recovery_implementation_measurements_sha256": (
            batch.canonical_sha256(implementations)
        ),
        "primary_runtime_attempt_ordinal": PRIMARY_RUNTIME_ATTEMPT,
        "replacement_runtime_attempt_ordinal": REPLACEMENT_RUNTIME_ATTEMPT,
        "task_max_retries": 0,
        "max_replacement_worker_executions": (
            MAX_REPLACEMENT_WORKER_EXECUTIONS
        ),
        "replacement_worker_limit_excludes_bridge_verifier": True,
        "max_bridge_verifier_executions_after_worker_success": 1,
        "replacement_execution_envelope": _replacement_execution_envelope(),
        "pre_submit_live_job_exact_description_required": True,
        "pre_submit_live_job_must_equal_replacement_execution_envelope": True,
        "changed_or_ambiguous_live_job_is_terminal": True,
        "replacement_worker_launch_plan": launch_plan,
        "replacement_worker_launch_plan_sha256": launch_plan[
            "worker_launch_plan_sha256"
        ],
        "replacement_live_job_projection": live_job,
        "replacement_live_job_projection_sha256": batch.canonical_sha256(
            live_job
        ),
        "replacement_cloud_execution_must_be_separately_named": True,
        "terminal_projection": terminal,
        "terminal_projection_sha256": batch.canonical_sha256(terminal),
        "primary_lineage": lineage,
        "primary_lineage_sha256": batch.canonical_sha256(lineage),
        "absence_check_after_terminal": _absence_rows(),
        "absence_check_immediately_before_create": _absence_rows(),
        "replacement_intent_uri": REPLACEMENT_INTENT_URI,
        "replacement_stage_start_uri": REPLACEMENT_STAGE_START_URI,
        "replacement_runtime_measurement_uri": (
            REPLACEMENT_RUNTIME_MEASUREMENT_URI
        ),
        "canonical_result_uri": RESULT_URI,
        "canonical_worker_stage_receipt_uri": PRIMARY_STAGE_RECEIPT_URI,
        "replacement_success_completion_uri": (
            REPLACEMENT_SUCCESS_COMPLETION_URI
        ),
        "replacement_execution_terminal_uri": (
            REPLACEMENT_EXECUTION_TERMINAL_URI
        ),
        "submission_failure_terminal_create_once_required": True,
        "ambiguous_submission_requires_terminal_receipt": True,
        "nonzero_submission_requires_terminal_receipt": True,
        "malformed_submission_response_requires_terminal_receipt": True,
        "unverified_submitted_envelope_requires_terminal_receipt": True,
        "terminal_receipt_publication_failure_still_consumes_attempt": True,
        "replacement_launch_ownership_uri": REPLACEMENT_LAUNCH_OWNERSHIP_URI,
        "post_submission_receipt_validation_law": (
            _post_submission_receipt_law()
        ),
        "replacement_worker_amendment_uri": REPLACEMENT_WORKER_AMENDMENT_URI,
        "bridge_verifier_launch_request_uri": (
            BRIDGE_VERIFIER_LAUNCH_REQUEST_URI
        ),
        "bridge_verifier_stage_start_uri": BRIDGE_VERIFIER_STAGE_START_URI,
        "bridge_verifier_runtime_measurement_uri": (
            BRIDGE_VERIFIER_RUNTIME_MEASUREMENT_URI
        ),
        "bridge_verifier_stage_receipt_uri": (
            BRIDGE_VERIFIER_STAGE_RECEIPT_URI
        ),
        "bridge_verifier_execution_terminal_uri": (
            BRIDGE_VERIFIER_EXECUTION_TERMINAL_URI
        ),
        "bridge_verifier_launch_ownership_uri": (
            BRIDGE_VERIFIER_LAUNCH_OWNERSHIP_URI
        ),
        "bridge_verifier_completion_uri": BRIDGE_VERIFIER_COMPLETION_URI,
        "supplemental_lane_root_uri": SUPPLEMENTAL_LANE_ROOT_URI,
        "supplemental_panel_root_uri": SUPPLEMENTAL_PANEL_ROOT_URI,
        "create_once_generation_match": 0,
        "replacement_intent_delete_allowed": False,
        "replacement_intent_overwrite_allowed": False,
        "replacement_intent_mutation_allowed": False,
        "unequal_replacement_intent_collision_terminal": True,
        "equal_existing_replacement_intent_resolve_only": True,
        "original_or_recovery_object_delete_allowed": False,
        "original_or_recovery_object_overwrite_allowed": False,
        "original_or_recovery_object_mutation_allowed": False,
        "all_recovery_and_bridge_publications_create_once": True,
        "unequal_recovery_or_bridge_collision_terminal": True,
        "first_creator_may_be_considered_by_reviewed_controller_only": True,
        "same_process_launch_controller_review_required": True,
        "offline_component_grants_launch_permission": False,
        "intent_creation_and_cloud_submission_must_share_one_reviewed_process": (
            True
        ),
        "request_consumed_even_if_execution_response_is_ambiguous": True,
        "launch_ownership_receipt_required_before_result_acceptance": True,
        "existing_intent_is_resolve_only": True,
        "original_launch_request_reused": False,
        "primary_runtime_attempt_reused": False,
        "second_replacement_allowed": False,
        "core_worker_runtime_attempt_one_required": True,
        "result_or_effect_content_inspected_for_eligibility": False,
        "separate_success_completion_required": True,
        "distinct_bridge_verifier_required": True,
        "ordinal_seven_resume_before_bridge_verifier_allowed": False,
        "supplemental_lane_and_panel_roots_required": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "platform_replacement_intent_sha256")


def validate_platform_replacement_intent_v1(
    value: object,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("platform-replacement intent must be one object")
    item = dict(value)
    _validate_self_hash(
        item, field="platform_replacement_intent_sha256", label="replacement intent"
    )
    _false_authorities(item, label="replacement intent")
    terminal = item.get("terminal_projection")
    lineage = item.get("primary_lineage")
    if not isinstance(terminal, Mapping) or not isinstance(lineage, Mapping):
        _fail("replacement intent evidence differs")
    expected = build_platform_replacement_intent_v1(
        terminal_projection=terminal,
        primary_lineage=lineage,
        review_lock_binding=item.get("review_lock_binding", {}),
        review_lock=item.get("review_lock", {}),
        recovery_implementation_measurements=item.get(
            "recovery_implementation_measurements", []
        ),
        replacement_worker_launch_plan=item.get(
            "replacement_worker_launch_plan", {}
        ),
        replacement_live_job_projection=item.get(
            "replacement_live_job_projection", {}
        ),
    )
    if _canonical(item) != _canonical(expected):
        _fail("platform-replacement intent differs after replay")
    return expected


def _prepare_platform_replacement_intent_candidate_context_v1(
    *,
    backend: PlatformReplacementBackend,
    replacement_worker_launch_plan: Mapping[str, object],
    replacement_live_job_projection: Mapping[str, object],
    absent_uris: Sequence[str],
) -> dict[str, object]:
    terminal = validate_primary_terminal_projection_v1(
        backend.observe_primary_terminal(FAILED_EXECUTION)
    )
    amendment = _amendment_measurement()
    if amendment != {
        "relative_path": AMENDMENT_RELATIVE_PATH,
        "sha256": AMENDMENT_SHA256,
        "bytes": AMENDMENT_BYTES,
    }:
        _fail("frozen replacement amendment differs")
    review_lock_binding, review_lock = _reopen_recovery_review_lock_v1(backend)
    implementations = _implementation_measurements()
    lineage = _reopen_fixed_primary_lineage_v1(backend)
    _require_absent(backend, absent_uris)
    intent = build_platform_replacement_intent_v1(
        terminal_projection=terminal,
        primary_lineage=lineage,
        review_lock_binding=review_lock_binding,
        review_lock=review_lock,
        recovery_implementation_measurements=implementations,
        replacement_worker_launch_plan=replacement_worker_launch_plan,
        replacement_live_job_projection=replacement_live_job_projection,
    )
    _require_absent(backend, absent_uris)
    return intent


def prepare_platform_replacement_intent_candidate_v1(
    *,
    backend: PlatformReplacementBackend,
    replacement_worker_launch_plan: Mapping[str, object],
    replacement_live_job_projection: Mapping[str, object],
) -> dict[str, object]:
    """Validate a new-authorization candidate; never publish or authorize."""
    intent = _prepare_platform_replacement_intent_candidate_context_v1(
        backend=backend,
        replacement_worker_launch_plan=replacement_worker_launch_plan,
        replacement_live_job_projection=replacement_live_job_projection,
        absent_uris=_ABSENT_BEFORE_REPLACEMENT,
    )
    return {
        "schema_version": OPERATOR_RESULT_SCHEMA,
        "disposition": "offline-intent-candidate-only",
        "intent_identity": None,
        "intent": intent,
        "intent_created_by_this_invocation": False,
        "cloud_execution_submission_allowed_this_invocation": False,
        "same_process_launch_controller_review_required": True,
        "resolve_only": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }


def resolve_equal_existing_platform_replacement_intent_v1(
    *,
    backend: PlatformReplacementBackend,
    replacement_worker_launch_plan: Mapping[str, object],
    replacement_live_job_projection: Mapping[str, object],
) -> dict[str, object]:
    """Exact-replay one existing equal intent without granting launch."""
    intent = _prepare_platform_replacement_intent_candidate_context_v1(
        backend=backend,
        replacement_worker_launch_plan=replacement_worker_launch_plan,
        replacement_live_job_projection=replacement_live_job_projection,
        absent_uris=_ABSENT_EFFECT_SURFACE,
    )
    expected_raw = _canonical(intent)
    try:
        identity_value, raw = backend.read_known_uri(REPLACEMENT_INTENT_URI)
    except FileNotFoundError as exc:
        raise T230PlatformReplacementError(
            "existing replacement intent is absent during resolve-only replay"
        ) from exc
    identity = _identity(identity_value, label="existing replacement intent")
    if (
        identity["uri"] != REPLACEMENT_INTENT_URI
        or not isinstance(raw, bytes)
        or raw != expected_raw
        or identity["sha256"] != sha256(raw).hexdigest()
        or identity["bytes"] != len(raw)
        or backend.read(identity) != raw
    ):
        _fail("existing replacement intent is unequal or ambiguous")
    retained = validate_platform_replacement_intent_v1(
        transport.strict_json(raw, label="existing replacement intent")
    )
    return {
        "schema_version": OPERATOR_RESULT_SCHEMA,
        "disposition": "equal-existing-intent-resolve-only",
        "intent_identity": identity,
        "intent": retained,
        "intent_created_by_this_invocation": False,
        "cloud_execution_submission_allowed_this_invocation": False,
        "same_process_launch_controller_review_required": True,
        "resolve_only": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }


def prepare_platform_replacement_intent_once_v1(
    *,
    backend: PlatformReplacementBackend,
) -> dict[str, object]:
    """Fail closed until a sealed same-process publisher/controller exists."""
    del backend
    _fail(
        "live replacement intent publication requires a separately sealed "
        "same-process launch controller"
    )


__all__ = [
    "ACCEPTANCE_URI",
    "AMENDMENT_BYTES",
    "AMENDMENT_RELATIVE_PATH",
    "AMENDMENT_SHA256",
    "BRIDGE_VERIFIER_COMPLETION_URI",
    "BRIDGE_VERIFIER_EXECUTION_TERMINAL_URI",
    "BRIDGE_VERIFIER_LAUNCH_OWNERSHIP_URI",
    "BRIDGE_VERIFIER_LAUNCH_REQUEST_URI",
    "BRIDGE_VERIFIER_RUNTIME_MEASUREMENT_URI",
    "BRIDGE_VERIFIER_STAGE_RECEIPT_URI",
    "BRIDGE_VERIFIER_STAGE_START_URI",
    "CONTRACT_SCHEMA",
    "CONTROLLER_RELATIVE_PATH",
    "CONTROLLER_TEST_RELATIVE_PATH",
    "CORRECTED_CANDIDATE_INVOCATION_COUNT_MAX",
    "CORRECTION_ADDENDUM_BYTES",
    "CORRECTION_ADDENDUM_RELATIVE_PATH",
    "CORRECTION_ADDENDUM_SHA256",
    "FAILED_EXECUTION",
    "FAILED_TASK",
    "EXECUTION_DESCRIBE_ARGV",
    "FIRST_CORRECTED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS",
    "FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_BYTES",
    "FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_RELATIVE_PATH",
    "FIRST_CORRECTED_FOCUSED_TEST_OUTPUT_SHA256",
    "FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_ERROR_LINES",
    "FIRST_FAILED_REAL_ARTIFACT_PREFLIGHT_EXIT_CODE",
    "FROZEN_D2_DIGEST",
    "FROZEN_D2_URI",
    "FROZEN_PRIMARY_RUNTIME_PAYLOAD_BYTES",
    "FROZEN_PRIMARY_RUNTIME_PAYLOAD_SHA256",
    "INTENT_SCHEMA",
    "LAUNCH_OWNERSHIP_SCHEMA",
    "LIVE_JOB_DESCRIBE_ARGV",
    "LIVE_JOB_PROJECTION_SCHEMA",
    "MAX_REPLACEMENT_WORKER_EXECUTIONS",
    "OPERATION",
    "OPERATOR_RESULT_SCHEMA",
    "POST_PREFLIGHT_FIX_FOCUSED_TEST_OUTPUT_RELATIVE_PATH",
    "PREFLIGHT_CORRECTION_ADDENDUM_RELATIVE_PATH",
    "PRIMARY_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES",
    "PRIMARY_RUNTIME_ATTEMPT",
    "PRIMARY_RUNTIME_MEASUREMENT_URI",
    "PRIOR_FAILED_FOCUSED_TEST_CANDIDATE_MEASUREMENTS",
    "PRIOR_FAILED_FOCUSED_TEST_NODE_IDS",
    "PRIOR_FAILED_INVOCATION_COUNT",
    "PRIOR_FAILED_PYTEST_EXIT_CODE",
    "PRIMARY_STAGE_RECEIPT_URI",
    "PRIMARY_STAGE_START_URI",
    "PlatformReplacementBackend",
    "REAL_ARTIFACT_PREFLIGHT_COMMAND",
    "REAL_ARTIFACT_PREFLIGHT_FLAGS_PATH",
    "REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH",
    "REAL_ARTIFACT_PREFLIGHT_SCHEMA",
    "REAL_ARTIFACT_PREFLIGHT_TOTAL_INVOCATION_COUNT_MAX",
    "REVIEW_LOCK_RELATIVE_PATH",
    "REVIEW_LOCK_SCHEMA",
    "REPLACEMENT_INTENT_URI",
    "REPLACEMENT_EXECUTION_TERMINAL_URI",
    "REPLACEMENT_LAUNCH_OWNERSHIP_URI",
    "REPLACEMENT_RUNTIME_ATTEMPT",
    "REPLACEMENT_RUNTIME_MEASUREMENT_URI",
    "REPLACEMENT_STAGE_START_URI",
    "REPLACEMENT_STAGE_START_SCHEMA",
    "REPLACEMENT_SUCCESS_COMPLETION_URI",
    "REPLACEMENT_WORKER_AMENDMENT_URI",
    "RESULT_URI",
    "SOURCE_ORDINAL",
    "SUPPLEMENTAL_LANE_ROOT_URI",
    "SUPPLEMENTAL_PANEL_ROOT_URI",
    "TERMINAL_PROJECTION_SCHEMA",
    "T230PlatformReplacementError",
    "TASK_DESCRIBE_ARGV",
    "FOCUSED_TEST_TOTAL_INVOCATION_COUNT_MAX",
    "WORKER_LAUNCH_PLAN_SCHEMA",
    "build_platform_replacement_intent_v1",
    "frozen_platform_replacement_contract_v1",
    "prepare_platform_replacement_intent_candidate_v1",
    "prepare_platform_replacement_intent_once_v1",
    "preflight_platform_replacement_real_artifacts_v1",
    "require_platform_replacement_surface_absent_v1",
    "reopen_fixed_primary_lineage_for_controller_v1",
    "resolve_equal_existing_platform_replacement_intent_v1",
    "validate_platform_replacement_contract_v1",
    "validate_platform_replacement_intent_v1",
    "validate_platform_replacement_real_artifact_preflight_v1",
    "validate_primary_terminal_projection_v1",
    "validate_replacement_live_job_projection_v1",
]
