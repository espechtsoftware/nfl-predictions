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
ACTUAL_IMAGE_DIGEST_ENV: Final = "R6_V7_RECOVERY_ACTUAL_IMAGE_DIGEST"
ACTUAL_CODE_SHA_ENV: Final = "R6_V7_RECOVERY_ACTUAL_CODE_SHA"
RECOVERY_CHILD_WALL_SECONDS: Final = 5_400
PROVIDER_TASK_WALL_SECONDS: Final = 7_260
ORIGINAL_CHILD_WALL_SECONDS: Final = 1_800
FIXED_PROJECT: Final = "nfl-predictions-503414"
FIXED_JOB: Final = "atlas-cbc-32g-full-2023-w8-v1"
SCHEMA: Final = "corpus-r6-v7-terminal-root-timeout-recovery-terminal/v1"
AMENDMENT_SCHEMA: Final = "corpus-r6-v7-terminal-root-timeout-amendment/v1"
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
    ):
        _fail("recovery code/image/execution binding differs")
    return {
        "amendment_identity": _identity_from_environment(
            AMENDMENT_IDENTITY_ENV, env
        ),
        "execution_name": execution,
        "actual_image_digest": actual_image,
        "actual_code_commit": actual_commit,
        "logical_image_digest": logical_image,
        "logical_code_commit": logical_commit,
    }


def validate_amendment_v1(
    value: object, *, identity: Mapping[str, object], runtime: Mapping[str, object],
) -> dict[str, object]:
    item = dict(value) if isinstance(value, Mapping) else {}
    expected = {
        "schema_version", "run_id", "failure_execution_identity",
        "original_manifest_identity", "preserved_layer_receipt_identities",
        "original_image_digest", "replacement_image_digest",
        "original_code_commit", "replacement_code_commit", "child_command",
        "child_command_sha256", "request_identity", "request_sha256",
        "request_bytes", "process_budget_identity",
        "publisher_process_budget_sha256", "read_allowlist_sha256",
        "write_allowlist_sha256", "root_uri", "root_create_once",
        "original_child_wall_seconds", "replacement_child_wall_seconds",
        "provider_task_wall_seconds", "recovery_terminal_evidence_uri",
        "terminal_receipt_uri", "finalize_receipt_uri", "policy",
        "amendment_sha256",
    }
    if set(item) != expected:
        _fail("timeout amendment fields differ")
    prior_hash = item.pop("amendment_sha256", None)
    if prior_hash != sha256(canonical_bytes_v1(item)).hexdigest():
        _fail("timeout amendment self-hash differs")
    item["amendment_sha256"] = prior_hash
    if (
        identity["bytes"] != len(canonical_bytes_v1(item))
        or identity["sha256"] != sha256(canonical_bytes_v1(item)).hexdigest()
        or item.get("schema_version") != AMENDMENT_SCHEMA
        or item.get("run_id") != "20260828-r6-current-bank-crossed-screen-v7"
        or item.get("replacement_image_digest")
        != runtime["actual_image_digest"]
        or item.get("replacement_code_commit") != runtime["actual_code_commit"]
        or item.get("original_image_digest")
        != runtime["logical_image_digest"]
        or item.get("original_code_commit") != runtime["logical_code_commit"]
        or item.get("original_child_wall_seconds")
        != ORIGINAL_CHILD_WALL_SECONDS
        or item.get("replacement_child_wall_seconds")
        != RECOVERY_CHILD_WALL_SECONDS
        or item.get("provider_task_wall_seconds")
        != PROVIDER_TASK_WALL_SECONDS
        or item.get("root_create_once") is not True
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
    authority = task_manifest.reopen_task_manifest_authority_v1(
        amendment["original_manifest_identity"], read_exact=transport.read_exact
    )
    manifest, task = _validate_original_task_v1(amendment, authority)
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
    process_budget_bindings = (
        task_manifest._exact_task_process_budget_bindings_v1(
            manifest=manifest, task=task, read_exact=transport.read_exact
        )
    )
    budget = process_budget_bindings[0]
    if (
        budget["process_budget_identity"] != amendment["process_budget_identity"]
        or budget["process_budget_sha256"]
        != amendment["publisher_process_budget_sha256"]
        or sha256(canonical_bytes_v1(budget["read_allowlist"])).hexdigest()
        != amendment["read_allowlist_sha256"]
        or sha256(canonical_bytes_v1(budget["write_allowlist"])).hexdigest()
        != amendment["write_allowlist_sha256"]
    ):
        _fail("recovery process-budget allowlists differ")
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
    evidence_identity = transport.publish_create_once(
        str(amendment["recovery_terminal_evidence_uri"]), evidence_raw
    )
    return {
        "schema_version": "corpus-r6-v7-terminal-root-timeout-recovery-dispatch/v1",
        "cloud_execution_name": runtime["execution_name"],
        "amendment_identity": dict(runtime["amendment_identity"]),
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
