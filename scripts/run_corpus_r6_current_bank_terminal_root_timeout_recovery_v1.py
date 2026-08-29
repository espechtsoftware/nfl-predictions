#!/usr/bin/env python3
"""Run the one authorized V7 terminal-root timeout recovery.

This is an administrative transport adapter.  It exact-reopens the original
V7 task authority, preserves its canonical publisher command/request and
process-budget allowlists, and grants that child 5,400 seconds under the
existing 7,260-second Cloud Run task ceiling.  It never accepts caller science
or a caller output URI.
"""

from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from typing import Final, Mapping

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_aggregate_v1 as publisher,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)


ENABLE_ENV: Final = "R6_V7_TERMINAL_ROOT_TIMEOUT_RECOVERY_ENABLED"
AMENDMENT_IDENTITY_ENV: Final = "R6_V7_TIMEOUT_AMENDMENT_IDENTITY"
LAUNCH_OWNERSHIP_IDENTITY_ENV: Final = (
    "R6_V7_TIMEOUT_LAUNCH_OWNERSHIP_IDENTITY"
)
ACTUAL_IMAGE_DIGEST_ENV: Final = "R6_V7_RECOVERY_ACTUAL_IMAGE_DIGEST"
ACTUAL_CODE_SHA_ENV: Final = "R6_V7_RECOVERY_ACTUAL_CODE_SHA"
RECOVERY_CHILD_WALL_SECONDS: Final = 5_400
PROVIDER_TASK_WALL_SECONDS: Final = 7_260
ORIGINAL_CHILD_WALL_SECONDS: Final = 1_800
FIXED_PROJECT: Final = "nfl-predictions-503414"
FIXED_JOB: Final = "atlas-cbc-32g-full-2023-w8-v1"
FIXED_JOB_UID: Final = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
FIXED_FAILED_EXECUTION: Final = "atlas-cbc-32g-full-2023-w8-v1-9clnn"
FIXED_ORIGINAL_IMAGE_DIGEST: Final = (
    "sha256:440e910df2ca8aafd7a6055922327f76c7bd5b480ecb84cd6adeb1cc4c1f00bf"
)
FIXED_ORIGINAL_CODE_COMMIT: Final = (
    "5a293157e9ed9d14c9ba2f7d96d020db845442d3"
)
FIXED_CHILD_COMMAND: Final = (
    "/usr/local/bin/python3.11",
    "/app/scripts/run_corpus_r6_current_bank_crossed_screen_aggregate_v1.py",
    "publish-terminal-root",
)
FIXED_CHILD_COMMAND_SHA256: Final = (
    "7f85965c94b1468bfee63e9043fb89d20f0d95442dd890ad1383b2c58f9c1a9d"
)
FIXED_PUBLISHER_PROCESS_BUDGET_SHA256: Final = (
    "0acb5dfaf977e78f517979dfb5972854caab597f6a1ac0363f9a51b6dd077b08"
)
FIXED_READ_ALLOWLIST_SHA256: Final = (
    "236068484e3784fdbdef2fbde646b7b18c80fc7a09fb47012126f19eaa373c0d"
)
FIXED_WRITE_ALLOWLIST_SHA256: Final = (
    "fe3363d47293225e45b06cfe5e6e0a6aec9f53665a9ea024d38b30f041583b28"
)
FIXED_PREDECESSOR_TASK_COUNTS: Final = (1, 54, 54, 1, 54, 54, 1)
# 3 recovery authorities + (manifest + four common authorities + three
# authorities for each predecessor + projection budget + 219 task terminal
# records) + request + failed terminal + publisher budget.
EXPECTED_PRECHILD_EXACT_READS: Final = 252
FIXED_OUTPUT_PREFIX: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-current-bank-crossed-screens/"
    "20260828-r6-current-bank-crossed-screen-v7/"
)
FIXED_RECOVERY_PREFIX: Final = (
    f"{FIXED_OUTPUT_PREFIX}authorities/terminal-root-timeout-recovery-v1/"
)
FIXED_BUILD_RECEIPT_URI: Final = (
    f"{FIXED_OUTPUT_PREFIX}authorities/runtime-images/"
    "terminal-root-timeout-recovery-build.json"
)
FIXED_ORIGINAL_MANIFEST_IDENTITY: Final = {
    "bytes": 97_966,
    "generation": "1787969290338122",
    "sha256": "dd382d531997be0d9a888872f24adb6706dde27e8083ca72e8cf0367581a00ee",
    "uri": f"{FIXED_OUTPUT_PREFIX}authorities/task-manifests/07-terminal-root.json",
}
FIXED_REQUEST_IDENTITY: Final = {
    "bytes": 87_517,
    "generation": "1787969289908323",
    "sha256": "96ac78df2f507a8ccea9c2d5219652e3e93e5be23b7c046d6a2205095b6c1de7",
    "uri": (
        f"{FIXED_OUTPUT_PREFIX}authorities/layer-preparation/"
        "07-terminal-root/task-000/request.json"
    ),
}
FIXED_PROCESS_BUDGET_IDENTITY: Final = {
    "bytes": 99_018,
    "generation": "1787969289539506",
    "sha256": "9a6beac3e82b13ace5c4252b18ca4868b1cb4e6165901c6ff7d2a8bdf1ce3d47",
    "uri": (
        f"{FIXED_OUTPUT_PREFIX}authorities/layer-preparation/"
        "07-terminal-root/task-000/process-budget.json"
    ),
}
FIXED_FAILURE_TERMINAL_IDENTITY: Final = {
    "bytes": 4_893,
    "generation": "1787972142926585",
    "sha256": "45ba752a1accc54633768ed0c5003ded51a59c23f4498573c64419080c9c6dc8",
    "uri": (
        f"{FIXED_OUTPUT_PREFIX}authorities/task-terminal-evidence/"
        "terminal-root/task-000.json"
    ),
}
FIXED_PREDECESSOR_RECEIPT_IDENTITIES: Final = (
    {"bytes": 29_411, "generation": "1787948369433750", "sha256": "eaf0606fd2f21f7c3a12dcb14ec5971cd029512d13391b1172dfacfadee94daa", "uri": f"{FIXED_OUTPUT_PREFIX}authorities/layer-execution-receipts/00-projection.json"},
    {"bytes": 119_094, "generation": "1787951032623189", "sha256": "a0a7c15fd2b613f954ae6fda11a36e22c68c0474017dd58500e7934d4ebd7de5", "uri": f"{FIXED_OUTPUT_PREFIX}authorities/layer-execution-receipts/01-broad-selection-receipt.json"},
    {"bytes": 119_629, "generation": "1787952323877617", "sha256": "689640c614b34843f0299e78e604e15a0144128b71fdac5ad8fa90f63a2816d3", "uri": f"{FIXED_OUTPUT_PREFIX}authorities/layer-execution-receipts/02-broad-evaluation-result.json"},
    {"bytes": 12_274, "generation": "1787953734171852", "sha256": "10b7e83378ab92743129fc91178aac37d48fccc0ff40738f33743be5b2d54609", "uri": f"{FIXED_OUTPUT_PREFIX}authorities/layer-execution-receipts/03-nomination.json"},
    {"bytes": 122_166, "generation": "1787959833133827", "sha256": "d6f46371380ca74842f615c403ed181ca9e4198768a743843bd8bf6a65457a9a", "uri": f"{FIXED_OUTPUT_PREFIX}authorities/layer-execution-receipts/04-confirmation-selection-receipt.json"},
    {"bytes": 122_670, "generation": "1787965225773143", "sha256": "da06133faddd69e3a841ca60f7abeeebd141dc96ce45e6b15b2266724194e4fe", "uri": f"{FIXED_OUTPUT_PREFIX}authorities/layer-execution-receipts/05-confirmation-evaluation-result.json"},
    {"bytes": 14_196, "generation": "1787968757097735", "sha256": "385ea5d7793aafd518b708fe6343a8e1c948b5cb868d5a4971f5ba4741869df5", "uri": f"{FIXED_OUTPUT_PREFIX}authorities/layer-execution-receipts/06-aggregate-finalists.json"},
)
SCHEMA: Final = "corpus-r6-v7-terminal-root-timeout-recovery-terminal/v1"
AMENDMENT_SCHEMA: Final = "corpus-r6-v7-terminal-root-timeout-amendment/v1"
LAUNCH_OWNERSHIP_SCHEMA: Final = (
    "corpus-r6-v7-terminal-root-timeout-launch-ownership/v1"
)
_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_REDIRECT_ENV_KEYS: Final = (
    "STORAGE_EMULATOR_HOST",
    "CLOUDSDK_API_ENDPOINT_OVERRIDES_STORAGE",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "PYTHONHOME",
    "PYTHONPATH",
    "LD_AUDIT",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "R6_GCS_ENDPOINT",
    "R6_PROJECT_OVERRIDE",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


class TerminalRootTimeoutRecoveryV1Error(RuntimeError):
    """The bounded timeout recovery failed closed."""


def _fail(message: str) -> None:
    raise TerminalRootTimeoutRecoveryV1Error(message)


def canonical_bytes_v1(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = dict(value) if isinstance(value, Mapping) else {}
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} fields differ")
    if (
        type(item["uri"]) is not str
        or not str(item["uri"]).startswith("gs://")
        or type(item["generation"]) is not str
        or not str(item["generation"]).isdecimal()
        or str(item["generation"]).startswith("0")
        or type(item["sha256"]) is not str
        or _SHA_RE.fullmatch(str(item["sha256"])) is None
        or type(item["bytes"]) is not int
        or not 0 < int(item["bytes"]) <= 32_000_000
    ):
        _fail(f"{label} is not a bounded exact identity")
    return item


def _identity_from_environment(
    name: str, environ: Mapping[str, str],
) -> dict[str, object]:
    raw = environ.get(name, "")
    if not raw or len(raw.encode("utf-8")) > 8_192:
        _fail(f"{name} differs")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TerminalRootTimeoutRecoveryV1Error(
            f"{name} is not JSON"
        ) from exc
    if canonical_bytes_v1(value).decode("utf-8") != raw:
        _fail(f"{name} is not canonical JSON")
    return _identity(value, label=name)


def recovery_topology_v1(
    original_manifest_identity: Mapping[str, object],
) -> dict[str, str]:
    uri = str(original_manifest_identity["uri"])
    prefix, marker, suffix = uri.partition("/authorities/")
    if (
        marker != "/authorities/"
        or suffix != "task-manifests/07-terminal-root.json"
    ):
        _fail("original terminal-root manifest URI differs")
    output_prefix = f"{prefix}/"
    if output_prefix != FIXED_OUTPUT_PREFIX:
        _fail("original terminal-root output prefix differs")
    recovery_prefix = (
        f"{output_prefix}authorities/terminal-root-timeout-recovery-v1/"
    )
    return {
        "output_prefix": output_prefix,
        "amendment_uri": f"{recovery_prefix}amendment.json",
        "launch_ownership_uri": f"{recovery_prefix}launch-ownership.json",
        "execution_claim_uri": f"{recovery_prefix}execution-claim.json",
        "terminal_evidence_uri": f"{recovery_prefix}terminal-evidence.json",
        "terminal_receipt_uri": f"{recovery_prefix}terminal-receipt.json",
        "finalize_receipt_uri": f"{recovery_prefix}finalize-receipt.json",
        "root_uri": f"{output_prefix}root.json",
    }


def _load_dispatcher_v1():
    path = Path(__file__).with_name(
        "run_corpus_r6_current_bank_crossed_screen_task_dispatcher_v1.py"
    )
    spec = importlib.util.spec_from_file_location(
        "r6_v7_frozen_dispatcher_for_timeout_recovery", path,
    )
    if spec is None or spec.loader is None:
        _fail("frozen dispatcher module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_preclient_environment_v1(
    environ: Mapping[str, str], *, observed_command: list[str],
) -> dict[str, object]:
    env = dict(environ)
    canonical_command = [
        "/usr/local/bin/python3.11",
        "-I",
        "/app/scripts/run_corpus_r6_current_bank_terminal_root_timeout_recovery_v1.py",
    ]
    if observed_command != canonical_command:
        _fail("recovery kernel command differs")
    if env.get(ENABLE_ENV) != "1":
        _fail("recovery enable gate differs")
    if any(env.get(key) for key in _REDIRECT_ENV_KEYS):
        _fail("recovery redirect environment is forbidden")
    if (
        env.get("GOOGLE_CLOUD_PROJECT") != FIXED_PROJECT
        or env.get("CLOUD_RUN_JOB") != FIXED_JOB
        or env.get("CLOUD_RUN_TASK_INDEX") != "0"
        or env.get("CLOUD_RUN_TASK_COUNT") != "1"
        or env.get("CLOUD_RUN_TASK_ATTEMPT") != "0"
    ):
        _fail("recovery Cloud Run binding differs")
    execution = env.get("CLOUD_RUN_EXECUTION", "")
    actual_image = env.get(ACTUAL_IMAGE_DIGEST_ENV, "")
    actual_commit = env.get(ACTUAL_CODE_SHA_ENV, "")
    logical_image = env.get("R6_RUNTIME_IMAGE_DIGEST", "")
    logical_commit = env.get("CODE_SHA", "")
    if (
        not execution
        or not actual_image.startswith("sha256:")
        or _SHA_RE.fullmatch(actual_image[7:]) is None
        or _COMMIT_RE.fullmatch(actual_commit) is None
        or not logical_image.startswith("sha256:")
        or _SHA_RE.fullmatch(logical_image[7:]) is None
        or _COMMIT_RE.fullmatch(logical_commit) is None
        or logical_image != FIXED_ORIGINAL_IMAGE_DIGEST
        or logical_commit != FIXED_ORIGINAL_CODE_COMMIT
        or actual_image == FIXED_ORIGINAL_IMAGE_DIGEST
        or actual_commit == FIXED_ORIGINAL_CODE_COMMIT
    ):
        _fail("recovery code/image/execution binding differs")
    amendment_identity = _identity_from_environment(
        AMENDMENT_IDENTITY_ENV, env
    )
    ownership_identity = _identity_from_environment(
        LAUNCH_OWNERSHIP_IDENTITY_ENV, env
    )
    if (
        amendment_identity["uri"] != f"{FIXED_RECOVERY_PREFIX}amendment.json"
        or ownership_identity["uri"]
        != f"{FIXED_RECOVERY_PREFIX}launch-ownership.json"
    ):
        _fail("recovery preclient authority URI differs")
    return {
        "amendment_identity": amendment_identity,
        "launch_ownership_identity": ownership_identity,
        "execution_name": execution,
        "actual_image_digest": actual_image,
        "actual_code_commit": actual_commit,
        "logical_image_digest": logical_image,
        "logical_code_commit": logical_commit,
    }


def validate_amendment_v1(
    value: object, *, identity: Mapping[str, object], runtime: Mapping[str, object],
) -> dict[str, object]:
    identity = _identity(identity, label="timeout amendment identity")
    item = dict(value) if isinstance(value, Mapping) else {}
    expected = {
        "schema_version", "run_id", "failure_execution_identity",
        "original_manifest_identity", "preserved_layer_receipt_identities",
        "original_image_digest", "replacement_image_digest",
        "original_code_commit", "replacement_code_commit", "child_command",
        "replacement_build_receipt_identity",
        "child_command_sha256", "request_identity", "request_sha256",
        "request_bytes", "process_budget_identity",
        "publisher_process_budget_sha256", "read_allowlist_sha256",
        "write_allowlist_sha256", "root_uri", "root_create_once",
        "original_child_wall_seconds", "replacement_child_wall_seconds",
        "provider_task_wall_seconds", "recovery_terminal_evidence_uri",
        "launch_ownership_uri", "execution_claim_uri",
        "terminal_receipt_uri", "finalize_receipt_uri", "policy",
        "amendment_sha256",
    }
    if set(item) != expected:
        _fail("timeout amendment fields differ")
    prior_hash = item.pop("amendment_sha256", None)
    if prior_hash != sha256(canonical_bytes_v1(item)).hexdigest():
        _fail("timeout amendment self-hash differs")
    item["amendment_sha256"] = prior_hash
    original_manifest_identity = _identity(
        item.get("original_manifest_identity"),
        label="amendment original manifest identity",
    )
    topology = recovery_topology_v1(original_manifest_identity)
    _identity(
        item.get("failure_execution_identity"),
        label="amendment failed terminal identity",
    )
    request_identity = _identity(
        item.get("request_identity"), label="amendment request identity"
    )
    process_budget_identity = _identity(
        item.get("process_budget_identity"),
        label="amendment process-budget identity",
    )
    build_receipt_identity = _identity(
        item.get("replacement_build_receipt_identity"),
        label="amendment replacement build receipt identity",
    )
    if (
        identity["bytes"] != len(canonical_bytes_v1(item))
        or identity["sha256"] != sha256(canonical_bytes_v1(item)).hexdigest()
        or identity["uri"] != topology["amendment_uri"]
        or item.get("schema_version") != AMENDMENT_SCHEMA
        or item.get("run_id") != "20260828-r6-current-bank-crossed-screen-v7"
        or item.get("replacement_image_digest")
        != runtime["actual_image_digest"]
        or item.get("replacement_code_commit") != runtime["actual_code_commit"]
        or item.get("original_image_digest")
        != FIXED_ORIGINAL_IMAGE_DIGEST
        or item.get("original_image_digest")
        != runtime["logical_image_digest"]
        or item.get("original_code_commit") != FIXED_ORIGINAL_CODE_COMMIT
        or item.get("original_code_commit") != runtime["logical_code_commit"]
        or item.get("original_manifest_identity")
        != FIXED_ORIGINAL_MANIFEST_IDENTITY
        or item.get("request_identity") != FIXED_REQUEST_IDENTITY
        or item.get("process_budget_identity")
        != FIXED_PROCESS_BUDGET_IDENTITY
        or item.get("failure_execution_identity")
        != FIXED_FAILURE_TERMINAL_IDENTITY
        or item.get("preserved_layer_receipt_identities")
        != list(FIXED_PREDECESSOR_RECEIPT_IDENTITIES)
        or build_receipt_identity["uri"] != FIXED_BUILD_RECEIPT_URI
        or item.get("replacement_image_digest")
        == item.get("original_image_digest")
        or item.get("replacement_code_commit")
        == item.get("original_code_commit")
        or item.get("original_child_wall_seconds")
        != ORIGINAL_CHILD_WALL_SECONDS
        or item.get("replacement_child_wall_seconds")
        != RECOVERY_CHILD_WALL_SECONDS
        or item.get("provider_task_wall_seconds")
        != PROVIDER_TASK_WALL_SECONDS
        or item.get("child_command") != list(FIXED_CHILD_COMMAND)
        or item.get("child_command_sha256") != FIXED_CHILD_COMMAND_SHA256
        or item.get("request_sha256") != FIXED_REQUEST_IDENTITY["sha256"]
        or item.get("request_bytes") != FIXED_REQUEST_IDENTITY["bytes"]
        or item.get("publisher_process_budget_sha256")
        != FIXED_PUBLISHER_PROCESS_BUDGET_SHA256
        or item.get("read_allowlist_sha256")
        != FIXED_READ_ALLOWLIST_SHA256
        or item.get("write_allowlist_sha256")
        != FIXED_WRITE_ALLOWLIST_SHA256
        or item.get("root_create_once") is not True
        or item.get("root_uri") != topology["root_uri"]
        or item.get("launch_ownership_uri")
        != topology["launch_ownership_uri"]
        or item.get("execution_claim_uri") != topology["execution_claim_uri"]
        or item.get("recovery_terminal_evidence_uri")
        != topology["terminal_evidence_uri"]
        or item.get("terminal_receipt_uri")
        != topology["terminal_receipt_uri"]
        or item.get("finalize_receipt_uri")
        != topology["finalize_receipt_uri"]
        or request_identity["sha256"] != item.get("request_sha256")
        or request_identity["bytes"] != item.get("request_bytes")
        or process_budget_identity != item.get("process_budget_identity")
    ):
        _fail("timeout amendment runtime/wall binding differs")
    policy = dict(item.get("policy", {}))
    if policy != {
        "algorithm_changed": False,
        "child_command_changed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "historical_scoring_licensed": False,
        "process_budget_changed": False,
        "realized_outcomes_read": False,
        "request_changed": False,
        "scientific_inputs_changed": False,
        "single_replacement_launch_allowed": True,
    }:
        _fail("timeout amendment policy differs")
    receipts = item.get("preserved_layer_receipt_identities")
    if not isinstance(receipts, list) or len(receipts) != 7:
        _fail("timeout amendment preserved receipt count differs")
    for index, receipt in enumerate(receipts):
        retained = _identity(receipt, label=f"preserved receipt[{index}]")
        if f"/{index:02d}-" not in str(retained["uri"]):
            _fail("timeout amendment preserved receipt order differs")
    for field in (
        "child_command_sha256", "request_sha256",
        "publisher_process_budget_sha256", "read_allowlist_sha256",
        "write_allowlist_sha256", "amendment_sha256",
    ):
        if type(item.get(field)) is not str or _SHA_RE.fullmatch(
            str(item[field])
        ) is None:
            _fail(f"timeout amendment {field} differs")
    return item


def validate_launch_ownership_v1(
    value: object, *, identity: Mapping[str, object],
    amendment: Mapping[str, object], runtime: Mapping[str, object],
) -> dict[str, object]:
    identity = _identity(identity, label="launch ownership identity")
    item = dict(value) if isinstance(value, Mapping) else {}
    expected = {
        "schema_version", "run_id", "amendment_identity",
        "original_manifest_identity", "failure_execution_identity",
        "failure_execution_name", "job_name", "job_uid",
        "prior_execution_name", "launch_ordinal", "execution_claim_uri",
        "replacement_image_digest", "replacement_code_commit",
        "replacement_build_receipt_identity",
        "recovery_dispatcher_command", "task_count", "parallelism",
        "maximum_task_retries", "provider_task_wall_seconds",
        "maximum_submission_calls", "single_submission_consumed_on_acceptance",
        "uses_realized_outcomes", "scientific_inputs_changed",
        "launch_ownership_sha256",
    }
    if set(item) != expected:
        _fail("launch ownership fields differ")
    prior_hash = item.pop("launch_ownership_sha256", None)
    if prior_hash != sha256(canonical_bytes_v1(item)).hexdigest():
        _fail("launch ownership self-hash differs")
    item["launch_ownership_sha256"] = prior_hash
    for field, label in (
        ("amendment_identity", "ownership amendment identity"),
        ("original_manifest_identity", "ownership original manifest identity"),
        ("failure_execution_identity", "ownership failed terminal identity"),
        ("replacement_build_receipt_identity", "ownership build receipt identity"),
    ):
        _identity(item.get(field), label=label)
    canonical = canonical_bytes_v1(item)
    if (
        identity["uri"] != amendment["launch_ownership_uri"]
        or identity["bytes"] != len(canonical)
        or identity["sha256"] != sha256(canonical).hexdigest()
        or item.get("schema_version") != LAUNCH_OWNERSHIP_SCHEMA
        or item.get("run_id") != amendment["run_id"]
        or item.get("amendment_identity") != runtime["amendment_identity"]
        or item.get("original_manifest_identity")
        != amendment["original_manifest_identity"]
        or item.get("failure_execution_identity")
        != amendment["failure_execution_identity"]
        or item.get("failure_execution_name")
        != FIXED_FAILED_EXECUTION
        or item.get("job_name") != FIXED_JOB
        or item.get("job_uid")
        != FIXED_JOB_UID
        or item.get("prior_execution_name")
        != FIXED_FAILED_EXECUTION
        or item.get("launch_ordinal") != 1
        or item.get("execution_claim_uri")
        != amendment["execution_claim_uri"]
        or item.get("replacement_image_digest")
        != runtime["actual_image_digest"]
        or item.get("replacement_code_commit") != runtime["actual_code_commit"]
        or item.get("replacement_build_receipt_identity")
        != amendment["replacement_build_receipt_identity"]
        or item.get("recovery_dispatcher_command") != [
            "/usr/local/bin/python3.11", "-I",
            "/app/scripts/run_corpus_r6_current_bank_terminal_root_timeout_recovery_v1.py",
        ]
        or item.get("task_count") != 1
        or item.get("parallelism") != 1
        or item.get("maximum_task_retries") != 0
        or item.get("provider_task_wall_seconds") != PROVIDER_TASK_WALL_SECONDS
        or item.get("maximum_submission_calls") != 1
        or item.get("single_submission_consumed_on_acceptance") is not True
        or item.get("uses_realized_outcomes") is not False
        or item.get("scientific_inputs_changed") is not False
    ):
        _fail("launch ownership binding differs")
    return item


def build_execution_claim_v1(
    *, amendment_identity: Mapping[str, object],
    ownership_identity: Mapping[str, object], runtime: Mapping[str, object],
) -> dict[str, object]:
    body = {
        "schema_version": (
            "corpus-r6-v7-terminal-root-timeout-execution-claim/v1"
        ),
        "amendment_identity": dict(amendment_identity),
        "launch_ownership_identity": dict(ownership_identity),
        "cloud_execution_name": runtime["execution_name"],
        "cloud_job_name": FIXED_JOB,
        "cloud_job_uid": FIXED_JOB_UID,
        "cloud_task_index": 0,
        "cloud_task_attempt": 0,
        "cloud_task_count": 1,
        "actual_image_digest": runtime["actual_image_digest"],
        "actual_code_commit": runtime["actual_code_commit"],
        "replacement_launch_ordinal": 1,
        "claim_create_once_required": True,
        "claim_collision_relicenses_execution": False,
        "uses_realized_outcomes": False,
        "scientific_inputs_read_before_claim": False,
    }
    body["execution_claim_sha256"] = sha256(
        canonical_bytes_v1(body)
    ).hexdigest()
    return body


def validate_clean_build_receipt_v1(
    value: object, *, identity: Mapping[str, object],
    amendment: Mapping[str, object], runtime: Mapping[str, object],
) -> dict[str, object]:
    identity = _identity(identity, label="clean-build receipt identity")
    item = dict(value) if isinstance(value, Mapping) else {}
    expected = {
        "schema_version", "build_id", "build_status", "source_commit",
        "source_archive_identity", "immutable_image_uri", "image_digest",
        "clean_archive", "uncommitted_files_included",
        "focused_tests_passed", "focused_test_count",
        "build_context_contract_passed", "isolated_image_smoke_passed",
        "recovery_source_sha256", "publisher_source_sha256",
        "normalized_publisher_source_sha256", "recovery_test_source_sha256",
        "uses_realized_outcomes", "build_receipt_sha256",
    }
    if set(item) != expected:
        _fail("clean-build receipt fields differ")
    prior_hash = item.pop("build_receipt_sha256", None)
    if prior_hash != sha256(canonical_bytes_v1(item)).hexdigest():
        _fail("clean-build receipt self-hash differs")
    item["build_receipt_sha256"] = prior_hash
    canonical = canonical_bytes_v1(item)
    source_archive_identity = _identity(
        item.get("source_archive_identity"), label="build source archive"
    )
    for field in (
        "recovery_source_sha256", "publisher_source_sha256",
        "normalized_publisher_source_sha256", "recovery_test_source_sha256",
        "build_receipt_sha256",
    ):
        if type(item.get(field)) is not str or _SHA_RE.fullmatch(
            str(item[field])
        ) is None:
            _fail(f"clean-build receipt {field} differs")
    recovery_source_sha256 = sha256(Path(__file__).read_bytes()).hexdigest()
    publisher_raw = Path(str(publisher.__file__)).read_bytes()
    publisher_source_sha256 = sha256(publisher_raw).hexdigest()
    replacement_constant = (
        b"MAXIMUM_PUBLISHER_WALL_SECONDS: Final = 5_400"
    )
    if publisher_raw.count(replacement_constant) != 1:
        _fail("replacement publisher wall constant count differs")
    normalized_publisher_sha256 = sha256(publisher_raw.replace(
        replacement_constant,
        b"MAXIMUM_PUBLISHER_WALL_SECONDS: Final = 1_800",
    )).hexdigest()
    if (
        identity != amendment["replacement_build_receipt_identity"]
        or identity["uri"] != FIXED_BUILD_RECEIPT_URI
        or identity["bytes"] != len(canonical)
        or identity["sha256"] != sha256(canonical).hexdigest()
        or item.get("schema_version")
        != "corpus-r6-v7-terminal-root-timeout-clean-build-receipt/v1"
        or item.get("build_status") != "SUCCESS"
        or type(item.get("build_id")) is not str
        or not str(item["build_id"])
        or not str(source_archive_identity["uri"]).startswith(
            "gs://nfl-predictions-503414_cloudbuild/source/"
        )
        or not str(source_archive_identity["uri"]).endswith(".tgz")
        or item.get("source_commit") != runtime["actual_code_commit"]
        or item.get("image_digest") != runtime["actual_image_digest"]
        or not str(item.get("immutable_image_uri", "")).endswith(
            f"@{runtime['actual_image_digest']}"
        )
        or item.get("clean_archive") is not True
        or item.get("uncommitted_files_included") is not False
        or item.get("focused_tests_passed") is not True
        or type(item.get("focused_test_count")) is not int
        or int(item["focused_test_count"]) < 1
        or item.get("build_context_contract_passed") is not True
        or item.get("isolated_image_smoke_passed") is not True
        or item.get("recovery_source_sha256") != recovery_source_sha256
        or item.get("publisher_source_sha256") != publisher_source_sha256
        or item.get("normalized_publisher_source_sha256")
        != normalized_publisher_sha256
        or item.get("normalized_publisher_source_sha256")
        != "075c0b29c17b7d8376a775f80ce7863fd1f060ed2f9522eb10561a2d6f93ff35"
        or item.get("uses_realized_outcomes") is not False
    ):
        _fail("clean-build receipt binding differs")
    return item


def _validate_original_task_v1(
    amendment: Mapping[str, object], authority: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    manifest = dict(authority.get("manifest", {}))
    manifest_identity = _identity(
        authority.get("manifest_identity"), label="reopened manifest identity",
    )
    if manifest_identity != amendment["original_manifest_identity"]:
        _fail("reopened original manifest identity differs")
    if (
        manifest.get("layer_id") != "terminal-root"
        or manifest.get("task_count") != 1
        or manifest.get("image_digest") != amendment["original_image_digest"]
        or manifest.get("code_commit") != amendment["original_code_commit"]
        or manifest.get("reused_job_name") != FIXED_JOB
    ):
        _fail("original terminal-root manifest binding differs")
    task = dict(manifest["task_bindings"][0])
    request_raw = canonical_bytes_v1(task["request"])
    command = task_manifest.render_child_command_v1(
        "terminal-root", task["request"]
    )
    if (
        command != task["child_command"]
        or command != amendment["child_command"]
        or task.get("child_command_sha256")
        != amendment["child_command_sha256"]
        or sha256(request_raw).hexdigest() != task.get("request_sha256")
        or task.get("request_sha256") != amendment["request_sha256"]
        or len(request_raw) != task.get("request_bytes")
        or task.get("request_bytes") != amendment["request_bytes"]
        or task["request"].get("process_budget_identity")
        != amendment["process_budget_identity"]
        or task.get("maximum_wall_seconds") != ORIGINAL_CHILD_WALL_SECONDS
        or task["expected_outputs"] != [{
            "create_once": True,
            "maximum_bytes": 16_000_000,
            "prior_identity": None,
            "role": "root",
            "source_ordinal": None,
            "topology_ordinal": 274,
            "uri": amendment["root_uri"],
        }]
    ):
        _fail("original child command/request/output binding differs")
    return manifest, task


def validate_frozen_prechild_authorities_v1(
    *, amendment: Mapping[str, object], manifest: Mapping[str, object],
    task: Mapping[str, object], manifest_identity: Mapping[str, object],
    read_exact,
) -> list[dict[str, object]]:
    receipt_identities = [
        row["receipt_identity"] for row in manifest["predecessor_layer_receipts"]
    ]
    if (
        receipt_identities != list(FIXED_PREDECESSOR_RECEIPT_IDENTITIES)
        or receipt_identities
        != amendment["preserved_layer_receipt_identities"]
    ):
        _fail("reopened predecessor receipt identities differ")
    request_raw = read_exact(amendment["request_identity"])
    canonical_request = canonical_bytes_v1(task["request"])
    if (
        amendment["request_identity"] != FIXED_REQUEST_IDENTITY
        or request_raw != canonical_request
        or len(request_raw) != amendment["request_bytes"]
        or sha256(request_raw).hexdigest() != amendment["request_sha256"]
    ):
        _fail("generation-exact task request differs from frozen manifest")
    failure_raw = read_exact(amendment["failure_execution_identity"])
    failure = task_manifest.strict_json_v1(
        failure_raw, label="failed task-terminal evidence"
    )
    retained_failure = task_manifest.validate_task_terminal_evidence_v1(
        failure, manifest=manifest, manifest_identity=manifest_identity
    )
    if (
        amendment["failure_execution_identity"]
        != FIXED_FAILURE_TERMINAL_IDENTITY
        or amendment["failure_execution_identity"]["uri"]
        != task["task_terminal_evidence_uri"]
        or retained_failure.get("cloud_execution_name")
        != FIXED_FAILED_EXECUTION
        or retained_failure.get("task_completed") is not False
        or retained_failure.get("timed_out") is not True
        or retained_failure.get("stdout_overflow") is not False
        or retained_failure.get("stderr_overflow") is not False
        or retained_failure.get("publication_identities") != []
        or retained_failure.get("publication_evidence") != []
        or retained_failure.get("child_task_binding_evidence") is not None
        or retained_failure.get("child_stderr_bytes") != 0
        or retained_failure.get("child_stderr_sha256") != sha256(b"").hexdigest()
    ):
        _fail("failed task-terminal authority differs")
    process_budget_bindings = (
        task_manifest._exact_task_process_budget_bindings_v1(
            manifest=manifest, task=task, read_exact=read_exact
        )
    )
    if len(process_budget_bindings) != 1:
        _fail("terminal-root process-budget binding count differs")
    budget = process_budget_bindings[0]
    if (
        amendment["process_budget_identity"]
        != FIXED_PROCESS_BUDGET_IDENTITY
        or budget["process_budget_identity"]
        != amendment["process_budget_identity"]
        or budget["process_budget_sha256"]
        != amendment["publisher_process_budget_sha256"]
        or sha256(canonical_bytes_v1(budget["read_allowlist"])).hexdigest()
        != amendment["read_allowlist_sha256"]
        or sha256(canonical_bytes_v1(budget["write_allowlist"])).hexdigest()
        != amendment["write_allowlist_sha256"]
        or budget["write_allowlist"] != [{
            "ordinal": 274,
            "role": "root",
            "uri": f"{FIXED_OUTPUT_PREFIX}root.json",
            "max_bytes": 16_000_000,
            "create_once": True,
        }]
    ):
        _fail("recovery process-budget allowlists differ")
    return process_budget_bindings


def validate_wrapper_read_budget_v1(
    *, authority: Mapping[str, object], observed_reads: object,
    maximum_reads: object,
) -> None:
    receipts = authority.get("predecessor_layer_receipts")
    if not isinstance(receipts, list):
        _fail("reopened predecessor receipt set differs")
    task_counts = tuple(
        len(row.get("task_records", []))
        if isinstance(row, Mapping) else -1
        for row in receipts
    )
    if (
        task_counts != FIXED_PREDECESSOR_TASK_COUNTS
        or type(observed_reads) is not int
        or observed_reads != EXPECTED_PRECHILD_EXACT_READS
        or type(maximum_reads) is not int
        or EXPECTED_PRECHILD_EXACT_READS > maximum_reads
    ):
        _fail("recovery wrapper exact-read budget differs")


def execute_recovery_v1(
    *, runtime: Mapping[str, object], dispatcher: object,
) -> dict[str, object]:
    deadline = dispatcher.EndToEndWallDeadlineV1(
        PROVIDER_TASK_WALL_SECONDS
    )
    transport = dispatcher.GCSExactReadTransportV1(
        validated_runtime={
            "project_id": FIXED_PROJECT,
            "storage_endpoint": task_manifest.FIXED_STORAGE_ENDPOINT,
            "redirect_environment_present": False,
        },
        wall_deadline=deadline,
    )
    amendment_raw = transport.read_exact(runtime["amendment_identity"])
    amendment = validate_amendment_v1(
        task_manifest.strict_json_v1(
            amendment_raw, label="timeout recovery amendment"
        ),
        identity=runtime["amendment_identity"],
        runtime=runtime,
    )
    ownership_raw = transport.read_exact(runtime["launch_ownership_identity"])
    ownership = validate_launch_ownership_v1(
        task_manifest.strict_json_v1(
            ownership_raw, label="timeout recovery launch ownership"
        ),
        identity=runtime["launch_ownership_identity"],
        amendment=amendment,
        runtime=runtime,
    )
    claim = build_execution_claim_v1(
        amendment_identity=runtime["amendment_identity"],
        ownership_identity=runtime["launch_ownership_identity"],
        runtime=runtime,
    )
    claim_identity = transport.publish_create_once(
        str(amendment["execution_claim_uri"]), canonical_bytes_v1(claim)
    )
    if transport.prove_exact_identity(claim_identity) != claim_identity:
        _fail("recovery execution claim exact-generation proof differs")
    build_receipt_raw = transport.read_exact(
        amendment["replacement_build_receipt_identity"]
    )
    validate_clean_build_receipt_v1(
        task_manifest.strict_json_v1(
            build_receipt_raw, label="timeout recovery clean-build receipt"
        ),
        identity=amendment["replacement_build_receipt_identity"],
        amendment=amendment,
        runtime=runtime,
    )
    authority = task_manifest.reopen_task_manifest_authority_v1(
        amendment["original_manifest_identity"], read_exact=transport.read_exact
    )
    manifest, task = _validate_original_task_v1(amendment, authority)
    process_budget_bindings = validate_frozen_prechild_authorities_v1(
        amendment=amendment,
        manifest=manifest,
        task=task,
        manifest_identity=authority["manifest_identity"],
        read_exact=transport.read_exact,
    )
    validate_wrapper_read_budget_v1(
        authority=authority,
        observed_reads=transport._read_count,
        maximum_reads=dispatcher.MAXIMUM_EXACT_READS,
    )
    logical_environment = dict(os.environ)
    logical_environment["CODE_SHA"] = str(amendment["original_code_commit"])
    logical_environment["R6_RUNTIME_IMAGE_DIGEST"] = str(
        amendment["original_image_digest"]
    )
    child_environment = dispatcher.sanitized_child_environment_v1(
        environ=logical_environment,
        manifest=manifest,
        manifest_identity=authority["manifest_identity"],
        task=task,
    )
    result = dict(dispatcher._run_child_bounded_v1(
        command=list(task["child_command"]),
        input_bytes=canonical_bytes_v1(task["request"]),
        environment=child_environment,
        stdout_ceiling=int(task["child_stdout_byte_ceiling"]),
        stderr_ceiling=int(task["child_stderr_byte_ceiling"]),
        timeout_seconds=RECOVERY_CHILD_WALL_SECONDS,
    ))
    if (
        result.get("exit_code") != 0
        or result.get("timed_out") is not False
        or result.get("stdout_overflow") is not False
        or result.get("stderr_overflow") is not False
        or result.get("stderr") != b""
    ):
        _fail("recovery child did not complete cleanly")
    try:
        child_value = json.loads(bytes(result["stdout"]).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TerminalRootTimeoutRecoveryV1Error(
            "recovery child stdout is not JSON"
        ) from exc
    amended_task = dict(task)
    amended_task["maximum_wall_seconds"] = RECOVERY_CHILD_WALL_SECONDS
    envelope = task_manifest._validate_child_envelope_transport_v1(
        manifest=manifest,
        task=amended_task,
        value=child_value,
        process_budget_bindings=process_budget_bindings,
        child_elapsed_milliseconds=int(result["elapsed_milliseconds"]),
        cloud_execution_name=str(runtime["execution_name"]),
    )
    task_manifest.validate_child_task_binding_evidence_v1(
        envelope["task_binding_evidence"],
        manifest=manifest,
        manifest_identity=authority["manifest_identity"],
    )
    publications = task_manifest._publication_identities_from_child(
        manifest=manifest, task=task, envelope=envelope
    )
    if len(publications) != 1 or publications[0]["uri"] != amendment["root_uri"]:
        _fail("recovery root publication identity differs")
    if transport.prove_exact_identity(publications[0]) != publications[0]:
        _fail("recovery root exact-generation proof differs")
    evidence = {
        "schema_version": SCHEMA,
        "amendment_identity": dict(runtime["amendment_identity"]),
        "launch_ownership_identity": dict(runtime["launch_ownership_identity"]),
        "execution_claim_identity": claim_identity,
        "replacement_build_receipt_identity": amendment[
            "replacement_build_receipt_identity"
        ],
        "original_manifest_identity": dict(authority["manifest_identity"]),
        "cloud_execution_name": runtime["execution_name"],
        "actual_image_digest": runtime["actual_image_digest"],
        "actual_code_commit": runtime["actual_code_commit"],
        "logical_frozen_image_digest": runtime["logical_image_digest"],
        "logical_frozen_code_commit": runtime["logical_code_commit"],
        "child_command": list(task["child_command"]),
        "child_command_sha256": task["child_command_sha256"],
        "request_sha256": task["request_sha256"],
        "request_bytes": task["request_bytes"],
        "process_budget_identity": amendment["process_budget_identity"],
        "publisher_process_budget_sha256": amendment[
            "publisher_process_budget_sha256"
        ],
        "read_allowlist_sha256": amendment["read_allowlist_sha256"],
        "write_allowlist_sha256": amendment["write_allowlist_sha256"],
        "original_child_wall_seconds": ORIGINAL_CHILD_WALL_SECONDS,
        "replacement_child_wall_seconds": RECOVERY_CHILD_WALL_SECONDS,
        "provider_task_wall_seconds": PROVIDER_TASK_WALL_SECONDS,
        "child_elapsed_milliseconds": result["elapsed_milliseconds"],
        "child_stdout_bytes": len(result["stdout"]),
        "child_stdout_sha256": sha256(result["stdout"]).hexdigest(),
        "child_stderr_bytes": 0,
        "child_stderr_sha256": sha256(b"").hexdigest(),
        "root_identity": publications[0],
        "root_generation_exact_reopen_proved": True,
        "root_body_embedded": False,
        "raw_child_streams_embedded": False,
        "task_completed": True,
        "realized_outcomes_read": False,
        "scientific_outputs_exposed_to_controller": False,
    }
    evidence["terminal_recovery_sha256"] = sha256(
        canonical_bytes_v1(evidence)
    ).hexdigest()
    evidence_raw = canonical_bytes_v1(evidence)
    terminal_transport = dispatcher.GCSExactReadTransportV1(
        validated_runtime={
            "project_id": FIXED_PROJECT,
            "storage_endpoint": task_manifest.FIXED_STORAGE_ENDPOINT,
            "redirect_environment_present": False,
        },
        wall_deadline=deadline,
    )
    evidence_identity = terminal_transport.publish_create_once(
        f"{FIXED_RECOVERY_PREFIX}terminal-evidence.json", evidence_raw
    )
    if (
        terminal_transport.prove_exact_identity(evidence_identity)
        != evidence_identity
    ):
        _fail("recovery terminal evidence exact-generation proof differs")
    return {
        "schema_version": "corpus-r6-v7-terminal-root-timeout-recovery-dispatch/v1",
        "cloud_execution_name": runtime["execution_name"],
        "amendment_identity": dict(runtime["amendment_identity"]),
        "launch_ownership_identity": dict(runtime["launch_ownership_identity"]),
        "execution_claim_identity": claim_identity,
        "terminal_recovery_evidence_identity": evidence_identity,
        "root_identity": publications[0],
        "task_completed": True,
        "raw_child_streams_embedded": False,
        "realized_outcomes_read": False,
    }


def _observed_command_v1() -> list[str]:
    raw = Path("/proc/self/cmdline").read_bytes()
    if not raw.endswith(b"\0"):
        _fail("recovery kernel command is unavailable")
    try:
        return [part.decode("utf-8") for part in raw[:-1].split(b"\0")]
    except UnicodeDecodeError as exc:
        raise TerminalRootTimeoutRecoveryV1Error(
            "recovery kernel command is not UTF-8"
        ) from exc


def main() -> int:
    stage = "preclient"
    try:
        if sys.stdin.buffer.read(1):
            _fail("recovery stdin must be immediate EOF")
        runtime = validate_preclient_environment_v1(
            os.environ, observed_command=_observed_command_v1()
        )
        stage = "execution"
        result = execute_recovery_v1(
            runtime=runtime, dispatcher=_load_dispatcher_v1()
        )
        sys.stdout.buffer.write(canonical_bytes_v1(result) + b"\n")
        return 0
    except Exception:
        diagnostic = {
            "schema_version": "corpus-r6-v7-terminal-root-timeout-recovery-failure/v1",
            "classification": "bounded-recovery-failure",
            "stage": stage,
            "raw_child_streams_embedded": False,
            "realized_outcomes_read": False,
        }
        sys.stderr.buffer.write(canonical_bytes_v1(diagnostic) + b"\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
