#!/usr/bin/env python3
"""Same-process, create-once launcher for the T230 ordinal-6 replacement.

This controller owns the narrow transition that the offline replacement
contract intentionally cannot perform: create the reviewed attempt-1 intent
and, only when this exact invocation created it, submit one Cloud Run
execution request in the same process.  Cloud I/O and submission are injected
so the cardinality and collision laws can be tested without network access.

The current recovery module must bind ``replacement_worker_launch_plan`` and
its SHA-256 into the candidate intent before this controller can submit.  An
older or partially integrated candidate therefore fails before intent
publication and before the injected submitter is called.

This file grants no bridge-verifier, lane-resume, panel, scoring, graph,
promotion, decision, or production authority.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Final, Protocol

from nfl_dfs.research import (
    corpus_extreme_tail_panel_platform_replacement_v1 as replacement,
)
from nfl_dfs.research import corpus_extreme_tail_panel_execution as execution
from nfl_dfs.research import corpus_extreme_tail_panel_transport as transport
from nfl_dfs.research import corpus_parametric_batch as batch

import run_corpus_extreme_tail_panel_transport_v1 as transport_cli


LAUNCH_PLAN_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-worker-launch-plan/v1"
)
LAUNCH_OWNERSHIP_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-worker-launch-ownership/v1"
)
REPLACEMENT_STAGE_START_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-worker-stage-start/v1"
)
SUBMISSION_TERMINAL_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-submission-terminal/v1"
)
CONTROLLER_RESULT_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-worker-controller-result/v1"
)
EXECUTION_FLAGS_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-worker-execution-flags/v1"
)

ENABLE_ENV: Final = "FOUNDRY_T230_PRODUCTION_TRANSPORT_ENABLED"
HANDSHAKE_WAIT_SECONDS: Final = 300
FLAGS_FILE_MODE: Final = 0o600
ORIGINAL_RUNTIME_PAYLOAD_SHA256: Final = (
    "1c95fd4312db7baff61e0c25366cc07e515d74fef0741ebbd4f852ccf5c9cc19"
)
ORIGINAL_RUNTIME_PAYLOAD_BYTES: Final = 7688
LIVE_JOB_PROJECTION_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-live-job-projection/v1"
)
SUBMITTED_EXECUTION_PROJECTION_SCHEMA: Final = (
    "foundry-t230-ordinal-6-replacement-submitted-execution-projection/v1"
)

# Cloud Run's v1 JSON projection omits ``value`` for the exact empty-string
# overrides frozen by the reviewed replacement contract.  Deriving the
# allowlist from that single contract constant prevents controller/module
# drift and still rejects every omitted non-empty or unknown value.
_CLOUD_RUN_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES: Final = frozenset(
    replacement.PRIMARY_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_EXECUTION = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?")

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

_LAUNCH_OWNERSHIP_KEYS: Final = frozenset({
    "schema_version",
    "run_id",
    "operation",
    "source_ordinal",
    "runtime_attempt_ordinal",
    "replacement_intent_identity",
    "replacement_intent",
    "platform_replacement_intent_sha256",
    "worker_launch_plan",
    "worker_launch_plan_sha256",
    "post_submission_receipt_validation_law_sha256",
    "runtime_payload_sha256",
    "execution_flags_sha256",
    "execution_flags_bytes",
    "configured_environment_sha256",
    "configured_environment_entry_count",
    "submitted_execution_projection",
    "submitted_execution_projection_sha256",
    "precreate_live_job_projection",
    "precreate_live_job_projection_sha256",
    "gcloud_argv",
    "gcloud_argv_sha256",
    "cloud_execution_name",
    "reuse_job",
    "immutable_image",
    "submission_returncode",
    "submission_stdout_sha256",
    "submission_stdout_bytes",
    "submission_stderr_sha256",
    "submission_stderr_bytes",
    "intent_created_by_this_process",
    "first_creator_submitted",
    "submission_call_count",
    "request_consumed",
    "automatic_resubmission_allowed",
    "second_replacement_allowed",
    "result_or_effect_content_inspected_before_submission",
    "launch_ownership_sha256",
    *_FALSE_AUTHORITY_FIELDS,
})

_STAGE_START_KEYS: Final = frozenset({
    "schema_version",
    "run_id",
    "operation",
    "source_ordinal",
    "runtime_attempt_ordinal",
    "replacement_intent_identity",
    "launch_ownership",
    "launch_ownership_identity",
    "launch_ownership_sha256",
    "worker_launch_plan",
    "worker_launch_plan_sha256",
    "post_submission_receipt_validation_law_sha256",
    "runtime_payload_sha256",
    "execution_flags_sha256",
    "configured_environment_sha256",
    "submitted_execution_projection_sha256",
    "precreate_live_job_projection_sha256",
    "gcloud_argv_sha256",
    "cloud_execution_name",
    "cloud_job",
    "immutable_image",
    "execution_envelope",
    "execution_authority_identity",
    "compute_release_identity",
    "predecessor_identity",
    "replacement_stage_start_uri",
    "core_execution_requires_handshake",
    "published_after_exact_async_submission_response",
    "task_count",
    "parallelism",
    "max_retries",
    "automatic_resubmission_allowed",
    "original_launch_request_reused",
    "primary_runtime_attempt_reused",
    "result_or_effect_content_inspected_before_submission",
    "replacement_stage_start_sha256",
    *_FALSE_AUTHORITY_FIELDS,
})

_SUBMITTED_EXECUTION_PROJECTION_KEYS: Final = frozenset({
    "schema_version",
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
    "full_execution_envelope_exactly_validated",
    "worker_launch_plan_sha256",
    "execution_flags_sha256",
    "describe_argv",
    "describe_stdout_sha256",
    "describe_stdout_bytes",
})


class T230PlatformReplacementControllerError(RuntimeError):
    """The same-process replacement controller failed closed."""


class ReplacementControllerBackend(replacement.PlatformReplacementBackend, Protocol):
    """The reviewed known-name backend used by the offline contract and controller."""


@dataclass(frozen=True)
class SubmissionObservation:
    """Exact output of the sole injected Cloud Run submission call."""

    returncode: int
    stdout: bytes
    stderr: bytes


class CloudSubmitter(Protocol):
    """Exact job observer plus one-call adapter; neither method may retry."""

    def observe_reused_job(self) -> Mapping[str, object]: ...

    def observe_submitted_execution(
        self,
        *,
        execution_name: str,
        worker_launch_plan_sha256: str,
        execution_flags_sha256: str,
    ) -> Mapping[str, object]: ...

    def submit(
        self,
        *,
        argv: Sequence[str],
        execution_flags: Mapping[str, object],
    ) -> SubmissionObservation: ...


CandidateBuilder = Callable[..., Mapping[str, object]]
IntentValidator = Callable[[object], Mapping[str, object]]
EvidenceResolver = Callable[
    [ReplacementControllerBackend], Mapping[str, object]
]
ExistingIntentResolver = Callable[..., Mapping[str, object]]


def _fail(message: str) -> None:
    raise T230PlatformReplacementControllerError(message)


def _canonical(value: object) -> bytes:
    return batch.canonical_json_bytes(value)


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    if field in result:
        _fail(f"self-hash field already exists: {field}")
    result[field] = batch.canonical_sha256(result)
    return result


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
        raise T230PlatformReplacementControllerError(
            f"{label} identity differs"
        ) from exc


def _false_authorities(value: Mapping[str, object], *, label: str) -> None:
    for field in _FALSE_AUTHORITY_FIELDS:
        if value.get(field) is not False:
            _fail(f"{label}.{field} must be false")


def _authority_closure() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _expected_live_job_projection_v1() -> dict[str, object]:
    return {
        "schema_version": LIVE_JOB_PROJECTION_SCHEMA,
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
    }


def validate_live_reused_job_projection_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("live reused-job projection must be one object")
    retained = dict(value)
    expected = _expected_live_job_projection_v1()
    describe_argv = [
        "gcloud", "run", "jobs", "describe", replacement.REUSE_JOB,
        "--project", transport.PROJECT,
        "--region", transport.REGION,
        "--format=json",
    ]
    variable = {
        "describe_argv": retained.pop("describe_argv", None),
        "describe_stdout_sha256": retained.pop(
            "describe_stdout_sha256", None
        ),
        "describe_stdout_bytes": retained.pop("describe_stdout_bytes", None),
        "cloud_describe_exactly_validated": retained.pop(
            "cloud_describe_exactly_validated", None
        ),
    }
    if (
        _canonical(retained) != _canonical(expected)
        or variable["describe_argv"] != describe_argv
        or not isinstance(variable["describe_stdout_sha256"], str)
        or _SHA256.fullmatch(str(variable["describe_stdout_sha256"])) is None
        or type(variable["describe_stdout_bytes"]) is not int
        or int(variable["describe_stdout_bytes"]) < 1
        or variable["cloud_describe_exactly_validated"] is not True
    ):
        _fail("live reused-job projection differs")
    return {**expected, **variable}


def _live_job_semantic_projection_v1(
    value: Mapping[str, object],
) -> dict[str, object]:
    retained = validate_live_reused_job_projection_v1(value)
    return {
        key: item
        for key, item in retained.items()
        if key not in {
            "describe_argv",
            "describe_stdout_sha256",
            "describe_stdout_bytes",
            "cloud_describe_exactly_validated",
        }
    }


def _submitted_execution_describe_argv(execution_name: str) -> list[str]:
    if (
        _EXECUTION.fullmatch(execution_name) is None
        or not execution_name.startswith(replacement.REUSE_JOB + "-")
        or execution_name == replacement.FAILED_EXECUTION
    ):
        _fail("submitted execution name differs")
    return [
        "gcloud", "run", "jobs", "executions", "describe", execution_name,
        "--project", transport.PROJECT,
        "--region", transport.REGION,
        "--format=json",
    ]


def validate_submitted_execution_projection_v1(
    value: object,
    *,
    execution_name: str,
    launch_plan: Mapping[str, object],
    execution_flags: Mapping[str, object],
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("submitted execution projection must be one object")
    plan = validate_worker_launch_plan_v1(launch_plan)
    flags = validate_worker_execution_flags_v1(execution_flags)
    item = dict(value)
    if set(item) != _SUBMITTED_EXECUTION_PROJECTION_KEYS:
        _fail("submitted execution projection fields differ")
    variable = {
        "describe_argv": item.pop("describe_argv", None),
        "describe_stdout_sha256": item.pop("describe_stdout_sha256", None),
        "describe_stdout_bytes": item.pop("describe_stdout_bytes", None),
    }
    retained_plan_sha = item.pop("worker_launch_plan_sha256", None)
    retained_flags_sha = item.pop("execution_flags_sha256", None)
    expected = {
        "schema_version": SUBMITTED_EXECUTION_PROJECTION_SCHEMA,
        "execution_name": execution_name,
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
        "args": flags["flags"]["--args"],
        "configured_environment": flags["flags"]["--update-env-vars"],
        "runtime_evidence_volume": _expected_live_job_projection_v1()[
            "runtime_evidence_volume"
        ],
        "full_execution_envelope_exactly_validated": True,
    }
    if (
        _canonical(item) != _canonical(expected)
        or variable["describe_argv"]
        != _submitted_execution_describe_argv(execution_name)
        or not isinstance(variable["describe_stdout_sha256"], str)
        or _SHA256.fullmatch(str(variable["describe_stdout_sha256"])) is None
        or type(variable["describe_stdout_bytes"]) is not int
        or int(variable["describe_stdout_bytes"]) < 1
        or retained_plan_sha != plan["worker_launch_plan_sha256"]
        or retained_flags_sha != flags["flags_sha256"]
    ):
        _fail("submitted execution projection differs from exact flags/plan")
    return {
        **expected,
        "worker_launch_plan_sha256": plan["worker_launch_plan_sha256"],
        "execution_flags_sha256": flags["flags_sha256"],
        **variable,
    }


def _absolute_regular_target(value: str, *, label: str) -> str:
    path = Path(value)
    if (
        not path.is_absolute()
        or path.name in {"", ".", ".."}
        or "\x00" in value
    ):
        _fail(f"{label} must be one absolute file path")
    return str(path)


def _handshake_guard_source_v1() -> str:
    """Return the exact in-container known-name handshake guard source."""
    # This is mechanics-only code carried literally in the execution flags.
    # It has no list API and opens only the two predeclared handshake names.
    ownership_keys = json.dumps(
        sorted(_LAUNCH_OWNERSHIP_KEYS), separators=(",", ":")
    )
    stage_start_keys = json.dumps(
        sorted(_STAGE_START_KEYS), separators=(",", ":")
    )
    false_fields = json.dumps(
        list(_FALSE_AUTHORITY_FIELDS), separators=(",", ":")
    )
    return "\n".join((
        "import hashlib,json,os,time",
        "from google.api_core.exceptions import NotFound",
        "from google.cloud import storage",
        "def canonical(value):",
        " return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()",
        "def split_uri(uri):",
        " assert uri.startswith('gs://')",
        " bucket,marker,name=uri[5:].partition('/')",
        " assert marker and bucket and name and not name.endswith('/') and '//' not in name",
        " return bucket,name",
        "def exact_known(uri):",
        " bucket,name=split_uri(uri)",
        " client=storage.Client(project=os.environ['T230_PROJECT'])",
        " deadline=time.monotonic()+int(os.environ['T230_HANDSHAKE_WAIT_SECONDS'])",
        " while True:",
        "  blob=client.bucket(bucket).blob(name)",
        "  try: blob.reload()",
        "  except NotFound:",
        "   if time.monotonic()>=deadline: raise RuntimeError('handshake object absent')",
        "   time.sleep(1); continue",
        "  generation=int(blob.generation)",
        "  pinned=client.bucket(bucket).blob(name,generation=generation)",
        "  raw=pinned.download_as_bytes(if_generation_match=generation)",
        "  identity={'uri':uri,'generation':str(generation),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}",
        "  return identity,json.loads(raw.decode('utf-8'))",
        "def check_hash(body,field):",
        " retained=body[field]; value=dict(body); del value[field]",
        " assert retained==hashlib.sha256(canonical(value)).hexdigest()",
        "intent_id,intent=exact_known(os.environ['T230_REPLACEMENT_INTENT_URI'])",
        "assert intent_id=={'uri':os.environ['T230_REPLACEMENT_INTENT_URI'],'generation':os.environ['T230_REPLACEMENT_INTENT_GENERATION'],'sha256':os.environ['T230_REPLACEMENT_INTENT_SHA256'],'bytes':int(os.environ['T230_REPLACEMENT_INTENT_BYTES'])}",
        "check_hash(intent,'platform_replacement_intent_sha256')",
        "plan=intent['replacement_worker_launch_plan']",
        "check_hash(plan,'worker_launch_plan_sha256')",
        "assert intent['replacement_worker_launch_plan_sha256']==plan['worker_launch_plan_sha256']",
        "law=plan['post_submission_receipt_validation_law']",
        "assert intent['post_submission_receipt_validation_law']==law",
        "assert plan['post_submission_receipt_validation_law_sha256']==hashlib.sha256(canonical(law)).hexdigest()",
        "assert law['launch_ownership_schema_version']==os.environ['T230_OWNERSHIP_SCHEMA']",
        "assert law['worker_stage_start_schema_version']==os.environ['T230_STAGE_START_SCHEMA']",
        "for body in (intent,plan):",
        f" for field in {false_fields}: assert body.get(field) is False",
        "ownership_id,ownership=exact_known(os.environ['T230_OWNERSHIP_URI'])",
        f"assert set(ownership)==set({ownership_keys})",
        "check_hash(ownership,'launch_ownership_sha256')",
        "assert ownership['schema_version']==os.environ['T230_OWNERSHIP_SCHEMA']",
        "assert ownership['replacement_intent_identity']==intent_id",
        "assert ownership['replacement_intent']==intent",
        "assert ownership['platform_replacement_intent_sha256']==intent['platform_replacement_intent_sha256']",
        "assert ownership['cloud_execution_name']==os.environ['CLOUD_RUN_EXECUTION']",
        "assert ownership['reuse_job']==os.environ['T230_EXPECTED_JOB']",
        "assert ownership['immutable_image']==plan['immutable_image']",
        "assert ownership['worker_launch_plan']==plan",
        "assert ownership['worker_launch_plan_sha256']==plan['worker_launch_plan_sha256']",
        "assert ownership['post_submission_receipt_validation_law_sha256']==plan['post_submission_receipt_validation_law_sha256']",
        "assert ownership['runtime_payload_sha256']==plan['runtime_payload_sha256']",
        "assert ownership['source_ordinal']==int(os.environ['T230_SOURCE_ORDINAL'])",
        "assert ownership['runtime_attempt_ordinal']==int(os.environ['T230_RUNTIME_ATTEMPT'])",
        "assert ownership['request_consumed'] is True and ownership['first_creator_submitted'] is True",
        "projection=ownership['submitted_execution_projection']",
        "assert ownership['submitted_execution_projection_sha256']==hashlib.sha256(canonical(projection)).hexdigest()",
        "assert projection['execution_name']==ownership['cloud_execution_name']",
        "assert projection['job']==ownership['reuse_job']",
        "assert projection['image']==os.environ['T230_IMAGE']",
        "assert projection['args']==['-ceu',plan['runtime_payload']]",
        "assert projection['worker_launch_plan_sha256']==ownership['worker_launch_plan_sha256']",
        "assert projection['execution_flags_sha256']==ownership['execution_flags_sha256']",
        "assert ownership['configured_environment_sha256']==hashlib.sha256(canonical(projection['configured_environment'])).hexdigest()",
        "assert ownership['configured_environment_entry_count']==len(projection['configured_environment'])",
        "assert ownership['gcloud_argv_sha256']==hashlib.sha256(canonical(ownership['gcloud_argv'])).hexdigest()",
        "assert ownership['precreate_live_job_projection_sha256']==hashlib.sha256(canonical(ownership['precreate_live_job_projection'])).hexdigest()",
        "for field in " + false_fields + ": assert ownership.get(field) is False",
        "start_id,start=exact_known(os.environ['T230_STAGE_START_URI'])",
        f"assert set(start)==set({stage_start_keys})",
        "check_hash(start,'replacement_stage_start_sha256')",
        "assert start['schema_version']==os.environ['T230_STAGE_START_SCHEMA']",
        "assert start['replacement_intent_identity']==intent_id",
        "assert start['launch_ownership']==ownership",
        "assert start['launch_ownership_identity']==ownership_id",
        "assert start['launch_ownership_sha256']==ownership['launch_ownership_sha256']",
        "assert start['cloud_execution_name']==os.environ['CLOUD_RUN_EXECUTION']",
        "assert start['cloud_job']==ownership['reuse_job']",
        "assert start['immutable_image']==ownership['immutable_image']",
        "assert start['worker_launch_plan']==plan",
        "assert start['worker_launch_plan_sha256']==plan['worker_launch_plan_sha256']",
        "assert start['post_submission_receipt_validation_law_sha256']==plan['post_submission_receipt_validation_law_sha256']",
        "assert start['runtime_payload_sha256']==ownership['runtime_payload_sha256']",
        "assert start['execution_flags_sha256']==ownership['execution_flags_sha256']",
        "assert start['configured_environment_sha256']==ownership['configured_environment_sha256']",
        "assert start['submitted_execution_projection_sha256']==ownership['submitted_execution_projection_sha256']",
        "assert start['precreate_live_job_projection_sha256']==ownership['precreate_live_job_projection_sha256']",
        "assert start['gcloud_argv_sha256']==ownership['gcloud_argv_sha256']",
        "assert start['execution_envelope']==plan['execution_envelope']",
        "assert start['execution_authority_identity']==plan['execution_authority_identity']",
        "assert start['compute_release_identity']==plan['compute_release_identity']",
        "assert start['predecessor_identity']==plan['predecessor_identity']",
        "assert start['core_execution_requires_handshake'] is True",
        "for field in " + false_fields + ": assert start.get(field) is False",
        "print(json.dumps({'handshake_verified':True,'ownership_identity':ownership_id,'stage_start_identity':start_id},sort_keys=True,separators=(',',':')))",
    ))


def _worker_runtime_payload_v1() -> str:
    """Return the exact D2 mechanics payload; no transport run-stage is used."""
    return "\n".join((
        "set -euo pipefail",
        "umask 077",
        "python -c \"$T230_HANDSHAKE_GUARD_SOURCE\" >/tmp/replacement-handshake.json",
        "python scripts/run_corpus_extreme_tail_panel_transport_v1.py materialize-image-evidence \\",
        "  --image-evidence-uri \"$T230_EVIDENCE_URI\" \\",
        "  --image-evidence-generation \"$T230_EVIDENCE_GENERATION\" \\",
        "  --image-evidence-sha256 \"$T230_EVIDENCE_SHA256\" \\",
        "  --image-evidence-bytes \"$T230_EVIDENCE_BYTES\" \\",
        "  --execute >/tmp/materialized-image-evidence.json",
        "jq -cn --arg uri \"$T230_AUTHORITY_URI\" \\",
        "  --arg generation \"$T230_AUTHORITY_GENERATION\" \\",
        "  --arg sha256 \"$T230_AUTHORITY_SHA256\" \\",
        "  --argjson bytes \"$T230_AUTHORITY_BYTES\" \\",
        "  '{uri:$uri,generation:$generation,sha256:$sha256,bytes:$bytes}' \\",
        "  >/tmp/execution-authority.json",
        "python scripts/run_corpus_extreme_tail_panel_v1.py run-slate \\",
        "  --execution-authority-identity /tmp/execution-authority.json \\",
        "  --source-ordinal 6 \\",
        "  --runtime-attempt-ordinal 1 \\",
        "  --receipt-output /tmp/replacement-worker-core-receipt.json \\",
        "  --execute >/tmp/replacement-worker-core-stdout.json",
        "cmp -s /tmp/replacement-worker-core-receipt.json /tmp/replacement-worker-core-stdout.json",
    ))


def _gcloud_argv(flags_path: str) -> list[str]:
    return [
        "gcloud",
        "run",
        "jobs",
        "execute",
        replacement.REUSE_JOB,
        "--project",
        transport.PROJECT,
        "--region",
        transport.REGION,
        "--async",
        "--tasks",
        "1",
        "--task-timeout",
        f"{transport.TASK_TIMEOUT_SECONDS}s",
        f"--flags-file={flags_path}",
        "--format=value(metadata.name)",
    ]


def build_worker_launch_plan_v1(
    *,
    image_evidence_identity: Mapping[str, object],
    flags_path: str,
) -> dict[str, object]:
    """Build the intent-bound template for one unchanged-D2 core worker."""
    evidence = _identity(image_evidence_identity, label="image evidence")
    retained_flags_path = _absolute_regular_target(
        flags_path, label="execution flags path"
    )
    contract = replacement.frozen_platform_replacement_contract_v1()
    authority = _identity(
        contract["execution_authority_identity"], label="execution authority"
    )
    payload = _worker_runtime_payload_v1()
    guard = _handshake_guard_source_v1()
    fixed_environment = {
        ENABLE_ENV: "1",
        "T230_PROJECT": transport.PROJECT,
        "T230_EXPECTED_JOB": replacement.REUSE_JOB,
        "T230_SOURCE_ORDINAL": str(replacement.SOURCE_ORDINAL),
        "T230_RUNTIME_ATTEMPT": str(replacement.REPLACEMENT_RUNTIME_ATTEMPT),
        "T230_IMAGE": replacement.FROZEN_D2_URI,
        "T230_HANDSHAKE_WAIT_SECONDS": str(HANDSHAKE_WAIT_SECONDS),
        "T230_HANDSHAKE_GUARD_SOURCE": guard,
        "T230_REPLACEMENT_INTENT_URI": replacement.REPLACEMENT_INTENT_URI,
        "T230_OWNERSHIP_URI": replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI,
        "T230_STAGE_START_URI": replacement.REPLACEMENT_STAGE_START_URI,
        "T230_OWNERSHIP_SCHEMA": LAUNCH_OWNERSHIP_SCHEMA,
        "T230_STAGE_START_SCHEMA": REPLACEMENT_STAGE_START_SCHEMA,
        "T230_EVIDENCE_URI": str(evidence["uri"]),
        "T230_EVIDENCE_GENERATION": str(evidence["generation"]),
        "T230_EVIDENCE_SHA256": str(evidence["sha256"]),
        "T230_EVIDENCE_BYTES": str(evidence["bytes"]),
        "T230_AUTHORITY_URI": str(authority["uri"]),
        "T230_AUTHORITY_GENERATION": str(authority["generation"]),
        "T230_AUTHORITY_SHA256": str(authority["sha256"]),
        "T230_AUTHORITY_BYTES": str(authority["bytes"]),
    }
    body = {
        "schema_version": LAUNCH_PLAN_SCHEMA,
        "run_id": transport.RUN_ID,
        "project": transport.PROJECT,
        "region": transport.REGION,
        "reuse_job": replacement.REUSE_JOB,
        "operation": replacement.OPERATION,
        "source_ordinal": replacement.SOURCE_ORDINAL,
        "runtime_attempt_ordinal": replacement.REPLACEMENT_RUNTIME_ATTEMPT,
        "immutable_image": contract["immutable_image"],
        "execution_envelope": contract["replacement_execution_envelope"],
        "image_evidence_identity": evidence,
        "execution_authority_identity": authority,
        "compute_release_identity": contract["compute_release_identity"],
        "predecessor_identity": contract["predecessor_identity"],
        "replacement_intent_uri": replacement.REPLACEMENT_INTENT_URI,
        "launch_ownership_uri": replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI,
        "replacement_stage_start_uri": replacement.REPLACEMENT_STAGE_START_URI,
        "post_submission_receipt_validation_law": contract[
            "post_submission_receipt_validation_law"
        ],
        "post_submission_receipt_validation_law_sha256": (
            batch.canonical_sha256(
                contract["post_submission_receipt_validation_law"]
            )
        ),
        "canonical_result_uri": replacement.RESULT_URI,
        "canonical_worker_stage_uri": replacement.PRIMARY_STAGE_RECEIPT_URI,
        "runtime_payload": payload,
        "runtime_payload_sha256": sha256(payload.encode("utf-8")).hexdigest(),
        "runtime_payload_bytes": len(payload.encode("utf-8")),
        "handshake_guard_source_sha256": sha256(
            guard.encode("utf-8")
        ).hexdigest(),
        "handshake_guard_source_bytes": len(guard.encode("utf-8")),
        "fixed_environment": dict(sorted(fixed_environment.items())),
        "execution_flags_template": {
            "--args": ["-ceu", payload],
            "--update-env-vars": {
                **dict(sorted(fixed_environment.items())),
                "T230_REPLACEMENT_INTENT_GENERATION": (
                    "${created_replacement_intent_identity.generation}"
                ),
                "T230_REPLACEMENT_INTENT_SHA256": (
                    "${created_replacement_intent_identity.sha256}"
                ),
                "T230_REPLACEMENT_INTENT_BYTES": (
                    "${created_replacement_intent_identity.bytes_decimal}"
                ),
            },
        },
        "dynamic_environment_fields": [
            "T230_REPLACEMENT_INTENT_GENERATION",
            "T230_REPLACEMENT_INTENT_SHA256",
            "T230_REPLACEMENT_INTENT_BYTES",
        ],
        "dynamic_environment_derivation": (
            "only from the normalized identity returned by this process's "
            "generation-match-zero replacement-intent create"
        ),
        "flags_path": retained_flags_path,
        "gcloud_argv": _gcloud_argv(retained_flags_path),
        "live_job_projection": _expected_live_job_projection_v1(),
        "live_job_describe_argv": [
            "gcloud", "run", "jobs", "describe", replacement.REUSE_JOB,
            "--project", transport.PROJECT,
            "--region", transport.REGION,
            "--format=json",
        ],
        "submitted_execution_describe_required_before_handshake": True,
        "core_cli": [
            "python",
            "scripts/run_corpus_extreme_tail_panel_v1.py",
            "run-slate",
            "--execution-authority-identity",
            "/tmp/execution-authority.json",
            "--source-ordinal",
            "6",
            "--runtime-attempt-ordinal",
            "1",
            "--receipt-output",
            "/tmp/replacement-worker-core-receipt.json",
            "--execute",
        ],
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
        **_authority_closure(),
    }
    return _self_hash(body, "worker_launch_plan_sha256")


def validate_worker_launch_plan_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("worker launch plan must be one object")
    item = dict(value)
    _validate_self_hash(
        item, field="worker_launch_plan_sha256", label="worker launch plan"
    )
    _false_authorities(item, label="worker launch plan")
    expected = build_worker_launch_plan_v1(
        image_evidence_identity=item.get("image_evidence_identity", {}),
        flags_path=str(item.get("flags_path", "")),
    )
    if _canonical(item) != _canonical(expected):
        _fail("worker launch plan differs after replay")
    return expected


def _resolve_frozen_image_evidence_identity_v1(
    backend: ReplacementControllerBackend,
) -> dict[str, object]:
    contract = replacement.frozen_platform_replacement_contract_v1()
    authority_identity = _identity(
        contract.get("execution_authority_identity"),
        label="frozen execution authority",
    )
    try:
        authority = execution.reopen_published_t230_execution_authority_v1(
            execution_authority_identity=authority_identity,
            read_exact=backend.read,
        )
    except Exception as exc:
        raise T230PlatformReplacementControllerError(
            "frozen execution authority replay failed"
        ) from exc
    if (
        authority.get("immutable_image")
        != contract.get("immutable_image")
        or authority.get("output_prefix") != transport.OUTPUT_PREFIX
        or authority.get("simulated_execution_only") is not True
    ):
        _fail("frozen execution authority surface differs")
    return _identity(
        authority.get("image_evidence_identity"),
        label="authority-bound image evidence",
    )


def build_worker_execution_flags_v1(
    *,
    launch_plan: Mapping[str, object],
    replacement_intent_identity: Mapping[str, object],
) -> dict[str, object]:
    plan = validate_worker_launch_plan_v1(launch_plan)
    intent_identity = _identity(
        replacement_intent_identity, label="replacement intent"
    )
    if intent_identity["uri"] != replacement.REPLACEMENT_INTENT_URI:
        _fail("replacement intent URI differs")
    retained_fixed = plan.get("fixed_environment")
    if not isinstance(retained_fixed, Mapping) or any(
        type(key) is not str or type(value) is not str
        for key, value in retained_fixed.items()
    ):
        _fail("worker fixed environment differs")
    environment = dict(retained_fixed)
    environment.update({
        "T230_REPLACEMENT_INTENT_GENERATION": str(intent_identity["generation"]),
        "T230_REPLACEMENT_INTENT_SHA256": str(intent_identity["sha256"]),
        "T230_REPLACEMENT_INTENT_BYTES": str(intent_identity["bytes"]),
    })
    flags = {
        "--args": ["-ceu", plan["runtime_payload"]],
        "--update-env-vars": dict(sorted(environment.items())),
    }
    envelope = {
        "schema_version": EXECUTION_FLAGS_SCHEMA,
        "run_id": transport.RUN_ID,
        "worker_launch_plan": plan,
        "worker_launch_plan_sha256": plan["worker_launch_plan_sha256"],
        "replacement_intent_identity": intent_identity,
        "flags": flags,
        "flags_sha256": batch.canonical_sha256(flags),
        "flags_bytes": len(_canonical(flags)),
        "contains_only_exact_worker_execution_overrides": True,
        **_authority_closure(),
    }
    return _self_hash(envelope, "execution_flags_envelope_sha256")


def validate_worker_execution_flags_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("worker execution flags must be one object")
    item = dict(value)
    _validate_self_hash(
        item,
        field="execution_flags_envelope_sha256",
        label="worker execution flags",
    )
    _false_authorities(item, label="worker execution flags")
    plan = validate_worker_launch_plan_v1(item.get("worker_launch_plan"))
    flags = item.get("flags")
    if (
        item.get("schema_version") != EXECUTION_FLAGS_SCHEMA
        or item.get("run_id") != transport.RUN_ID
        or item.get("worker_launch_plan_sha256")
        != plan["worker_launch_plan_sha256"]
        or not isinstance(flags, Mapping)
        or set(flags) != {"--args", "--update-env-vars"}
        or item.get("flags_sha256") != batch.canonical_sha256(flags)
        or item.get("flags_bytes") != len(_canonical(flags))
        or item.get("contains_only_exact_worker_execution_overrides") is not True
    ):
        _fail("worker execution flags frozen surface differs")
    intent_identity = _identity(
        item.get("replacement_intent_identity"), label="flags replacement intent"
    )
    environment = flags.get("--update-env-vars")
    arguments = flags.get("--args")
    if (
        not isinstance(environment, Mapping)
        or any(
            type(key) is not str or type(retained) is not str
            for key, retained in environment.items()
        )
        or arguments != ["-ceu", plan["runtime_payload"]]
    ):
        _fail("worker execution flag arguments differ")
    if (
        environment.get("T230_REPLACEMENT_INTENT_URI") != intent_identity["uri"]
        or environment.get("T230_REPLACEMENT_INTENT_GENERATION") != intent_identity["generation"]
        or environment.get("T230_REPLACEMENT_INTENT_SHA256") != intent_identity["sha256"]
        or environment.get("T230_REPLACEMENT_INTENT_BYTES") != str(intent_identity["bytes"])
        or environment.get("T230_SOURCE_ORDINAL") != "6"
        or environment.get("T230_RUNTIME_ATTEMPT") != "1"
        or environment.get("T230_IMAGE") != replacement.FROZEN_D2_URI
    ):
        _fail("worker execution flag environment differs")
    expected = build_worker_execution_flags_v1(
        launch_plan=plan,
        replacement_intent_identity=intent_identity,
    )
    if _canonical(item) != _canonical(expected):
        _fail("worker execution flags differ after replay")
    return expected


def _read_equal_known_object(
    backend: ReplacementControllerBackend,
    *,
    uri: str,
    expected_raw: bytes,
    label: str,
) -> tuple[dict[str, object], bytes]:
    identity_value, raw = backend.read_known_uri(uri)
    identity = _identity(identity_value, label=label)
    if (
        identity["uri"] != uri
        or not isinstance(raw, bytes)
        or raw != expected_raw
        or backend.read(identity) != raw
        or identity["sha256"] != sha256(raw).hexdigest()
        or identity["bytes"] != len(raw)
    ):
        _fail(f"{label} differs")
    return identity, raw


def _create_once_or_equal(
    backend: ReplacementControllerBackend,
    *,
    uri: str,
    raw: bytes,
    label: str,
) -> tuple[dict[str, object], bool]:
    try:
        identity_value = backend.create(uri, raw)
    except transport.JournalObjectExists:
        identity, _ = _read_equal_known_object(
            backend, uri=uri, expected_raw=raw, label=label
        )
        return identity, False
    identity = _identity(identity_value, label=label)
    if (
        identity["uri"] != uri
        or identity["sha256"] != sha256(raw).hexdigest()
        or identity["bytes"] != len(raw)
        or backend.read(identity) != raw
    ):
        _fail(f"{label} create-once reopen differs")
    return identity, True


def _require_recovery_surface_absent(
    backend: ReplacementControllerBackend,
) -> None:
    contract = replacement.frozen_platform_replacement_contract_v1()
    uris = contract.get("absent_before_replacement_uris")
    if not isinstance(uris, Sequence) or isinstance(uris, (str, bytes)):
        _fail("replacement absence surface differs")
    for uri in uris:
        if not isinstance(uri, str):
            _fail("replacement absence URI differs")
        retained = backend.probe_known_uri_metadata(uri)
        if retained is None:
            continue
        if not isinstance(retained, Mapping):
            _fail(f"replacement absence probe is ambiguous: {uri}")
        _fail(f"replacement precondition object exists: {uri}")


def _validate_candidate_with_plan(
    value: object,
    *,
    expected_plan: Mapping[str, object],
    expected_live_job_projection: Mapping[str, object],
    intent_validator: IntentValidator,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("offline intent candidate differs")
    candidate = dict(value)
    if (
        candidate.get("disposition") != "offline-intent-candidate-only"
        or candidate.get("intent_identity") is not None
        or candidate.get("intent_created_by_this_invocation") is not False
        or candidate.get("cloud_execution_submission_allowed_this_invocation") is not False
        or candidate.get("same_process_launch_controller_review_required") is not True
        or candidate.get("resolve_only") is not True
    ):
        _fail("offline intent candidate authority differs")
    _false_authorities(candidate, label="offline intent candidate")
    try:
        intent = dict(intent_validator(candidate.get("intent")))
    except Exception as exc:
        raise T230PlatformReplacementControllerError(
            "offline candidate intent validation failed"
        ) from exc
    plan = validate_worker_launch_plan_v1(
        intent.get("replacement_worker_launch_plan")
    )
    expected = validate_worker_launch_plan_v1(expected_plan)
    live_job = validate_live_reused_job_projection_v1(
        expected_live_job_projection
    )
    if (
        _canonical(plan) != _canonical(expected)
        or intent.get("replacement_worker_launch_plan_sha256")
        != plan["worker_launch_plan_sha256"]
        or _canonical(intent.get("replacement_live_job_projection"))
        != _canonical(live_job)
        or intent.get("replacement_live_job_projection_sha256")
        != batch.canonical_sha256(live_job)
    ):
        _fail("offline candidate does not bind exact launch plan/live job")
    return {
        "candidate": candidate,
        "intent": intent,
        "launch_plan": plan,
        "live_job_projection": live_job,
    }


def _submission_observation(value: object) -> SubmissionObservation:
    if not isinstance(value, SubmissionObservation):
        _fail("submission adapter result differs")
    if (
        type(value.returncode) is not int
        or not isinstance(value.stdout, bytes)
        or not isinstance(value.stderr, bytes)
    ):
        _fail("submission observation types differ")
    return value


def _execution_from_submission(value: SubmissionObservation) -> str | None:
    if value.returncode != 0:
        return None
    try:
        stdout = value.stdout.decode("ascii")
    except UnicodeDecodeError:
        return None
    rows = [row.strip() for row in stdout.splitlines() if row.strip()]
    if len(rows) != 1:
        return None
    execution = rows[0]
    if (
        _EXECUTION.fullmatch(execution) is None
        or not execution.startswith(replacement.REUSE_JOB + "-")
        or execution == replacement.FAILED_EXECUTION
        or value.stdout != (execution + "\n").encode("ascii")
    ):
        return None
    return execution


def build_worker_launch_ownership_v1(
    *,
    replacement_intent_identity: Mapping[str, object],
    replacement_intent: Mapping[str, object],
    launch_plan: Mapping[str, object],
    execution_flags: Mapping[str, object],
    cloud_execution_name: str,
    submission: SubmissionObservation,
    submitted_execution: Mapping[str, object],
    precreate_live_job_projection: Mapping[str, object],
    replacement_intent_validator: IntentValidator,
) -> dict[str, object]:
    try:
        replacement_intent = dict(
            replacement_intent_validator(replacement_intent)
        )
    except Exception as exc:
        raise T230PlatformReplacementControllerError(
            "worker launch ownership intent validation failed"
        ) from exc
    intent_identity = _identity(
        replacement_intent_identity, label="ownership replacement intent"
    )
    plan = validate_worker_launch_plan_v1(launch_plan)
    flags = validate_worker_execution_flags_v1(execution_flags)
    execution = _execution_from_submission(submission)
    observed_execution = validate_submitted_execution_projection_v1(
        submitted_execution,
        execution_name=cloud_execution_name,
        launch_plan=plan,
        execution_flags=flags,
    )
    precreate_live_job = validate_live_reused_job_projection_v1(
        precreate_live_job_projection
    )
    intent_live_job = validate_live_reused_job_projection_v1(
        replacement_intent.get("replacement_live_job_projection")
    )
    intent_raw = _canonical(replacement_intent)
    receipt_law = plan["post_submission_receipt_validation_law"]
    if (
        intent_identity["uri"] != replacement.REPLACEMENT_INTENT_URI
        or intent_identity["sha256"] != sha256(intent_raw).hexdigest()
        or intent_identity["bytes"] != len(intent_raw)
        or execution is None
        or execution != cloud_execution_name
        or flags["replacement_intent_identity"] != intent_identity
        or flags["worker_launch_plan_sha256"] != plan["worker_launch_plan_sha256"]
        or _canonical(_live_job_semantic_projection_v1(precreate_live_job))
        != _canonical(_live_job_semantic_projection_v1(intent_live_job))
        or replacement_intent.get("post_submission_receipt_validation_law")
        != receipt_law
    ):
        _fail("worker launch ownership inputs differ")
    body = {
        "schema_version": LAUNCH_OWNERSHIP_SCHEMA,
        "run_id": transport.RUN_ID,
        "operation": replacement.OPERATION,
        "source_ordinal": replacement.SOURCE_ORDINAL,
        "runtime_attempt_ordinal": replacement.REPLACEMENT_RUNTIME_ATTEMPT,
        "replacement_intent_identity": intent_identity,
        "replacement_intent": dict(replacement_intent),
        "platform_replacement_intent_sha256": replacement_intent.get(
            "platform_replacement_intent_sha256"
        ),
        "worker_launch_plan": plan,
        "worker_launch_plan_sha256": plan["worker_launch_plan_sha256"],
        "post_submission_receipt_validation_law_sha256": (
            batch.canonical_sha256(receipt_law)
        ),
        "runtime_payload_sha256": plan["runtime_payload_sha256"],
        "execution_flags_sha256": flags["flags_sha256"],
        "execution_flags_bytes": flags["flags_bytes"],
        "configured_environment_sha256": batch.canonical_sha256(
            flags["flags"]["--update-env-vars"]
        ),
        "configured_environment_entry_count": len(
            flags["flags"]["--update-env-vars"]
        ),
        "submitted_execution_projection": observed_execution,
        "submitted_execution_projection_sha256": batch.canonical_sha256(
            observed_execution
        ),
        "precreate_live_job_projection": precreate_live_job,
        "precreate_live_job_projection_sha256": batch.canonical_sha256(
            precreate_live_job
        ),
        "gcloud_argv": list(plan["gcloud_argv"]),
        "gcloud_argv_sha256": batch.canonical_sha256(plan["gcloud_argv"]),
        "cloud_execution_name": execution,
        "reuse_job": replacement.REUSE_JOB,
        "immutable_image": plan["immutable_image"],
        "submission_returncode": submission.returncode,
        "submission_stdout_sha256": sha256(submission.stdout).hexdigest(),
        "submission_stdout_bytes": len(submission.stdout),
        "submission_stderr_sha256": sha256(submission.stderr).hexdigest(),
        "submission_stderr_bytes": len(submission.stderr),
        "intent_created_by_this_process": True,
        "first_creator_submitted": True,
        "submission_call_count": 1,
        "request_consumed": True,
        "automatic_resubmission_allowed": False,
        "second_replacement_allowed": False,
        "result_or_effect_content_inspected_before_submission": False,
        **_authority_closure(),
    }
    return _self_hash(body, "launch_ownership_sha256")


def _validate_worker_launch_ownership_v1(
    value: object, *, replacement_intent_validator: IntentValidator
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("worker launch ownership must be one object")
    item = dict(value)
    if set(item) != _LAUNCH_OWNERSHIP_KEYS:
        _fail("worker launch ownership fields differ")
    _validate_self_hash(
        item, field="launch_ownership_sha256", label="worker launch ownership"
    )
    _false_authorities(item, label="worker launch ownership")
    contract = replacement.frozen_platform_replacement_contract_v1()
    plan = validate_worker_launch_plan_v1(item.get("worker_launch_plan"))
    intent_identity = _identity(
        item.get("replacement_intent_identity"), label="ownership intent"
    )
    intent_value = item.get("replacement_intent")
    if not isinstance(intent_value, Mapping):
        _fail("worker launch ownership replacement intent differs")
    try:
        replacement_intent = dict(
            replacement_intent_validator(intent_value)
        )
    except Exception as exc:
        raise T230PlatformReplacementControllerError(
            "worker launch ownership embedded intent validation failed"
        ) from exc
    _validate_self_hash(
        replacement_intent,
        field="platform_replacement_intent_sha256",
        label="ownership replacement intent",
    )
    _false_authorities(
        replacement_intent, label="ownership replacement intent"
    )
    intent_raw = _canonical(replacement_intent)
    intent_live_job = validate_live_reused_job_projection_v1(
        replacement_intent.get("replacement_live_job_projection")
    )
    expected_flags = build_worker_execution_flags_v1(
        launch_plan=plan, replacement_intent_identity=intent_identity
    )
    execution_name = item.get("cloud_execution_name")
    projection_value = item.get("submitted_execution_projection")
    if not isinstance(projection_value, Mapping):
        _fail("worker launch ownership execution projection differs")
    projection = dict(projection_value)
    if set(projection) != _SUBMITTED_EXECUTION_PROJECTION_KEYS:
        _fail("worker launch ownership execution projection fields differ")
    environment = projection.get("configured_environment")
    arguments = projection.get("args")
    gcloud_argv = item.get("gcloud_argv")
    flags_rows = (
        [row for row in gcloud_argv if row.startswith("--flags-file=")]
        if isinstance(gcloud_argv, list)
        and all(isinstance(row, str) for row in gcloud_argv)
        else []
    )
    flags_path = (
        flags_rows[0].split("=", 1)[1] if len(flags_rows) == 1 else ""
    )
    precreate_live_job = validate_live_reused_job_projection_v1(
        item.get("precreate_live_job_projection")
    )
    if (
        item.get("schema_version") != LAUNCH_OWNERSHIP_SCHEMA
        or item.get("run_id") != transport.RUN_ID
        or item.get("operation") != replacement.OPERATION
        or item.get("source_ordinal") != replacement.SOURCE_ORDINAL
        or item.get("runtime_attempt_ordinal") != replacement.REPLACEMENT_RUNTIME_ATTEMPT
        or intent_identity["uri"] != replacement.REPLACEMENT_INTENT_URI
        or intent_identity["sha256"] != sha256(intent_raw).hexdigest()
        or intent_identity["bytes"] != len(intent_raw)
        or replacement_intent.get("schema_version") != replacement.INTENT_SCHEMA
        or replacement_intent.get("run_id") != transport.RUN_ID
        or replacement_intent.get("operation") != replacement.OPERATION
        or replacement_intent.get("source_ordinal")
        != replacement.SOURCE_ORDINAL
        or replacement_intent.get("replacement_worker_launch_plan") != plan
        or replacement_intent.get("replacement_worker_launch_plan_sha256")
        != plan["worker_launch_plan_sha256"]
        or replacement_intent.get("post_submission_receipt_validation_law")
        != plan["post_submission_receipt_validation_law"]
        or replacement_intent.get("replacement_live_job_projection_sha256")
        != batch.canonical_sha256(intent_live_job)
        or item.get("platform_replacement_intent_sha256")
        != replacement_intent["platform_replacement_intent_sha256"]
        or not isinstance(item.get("platform_replacement_intent_sha256"), str)
        or _SHA256.fullmatch(
            str(item.get("platform_replacement_intent_sha256"))
        ) is None
        or not isinstance(item.get("worker_launch_plan_sha256"), str)
        or _SHA256.fullmatch(str(item["worker_launch_plan_sha256"])) is None
        or item.get("worker_launch_plan_sha256")
        != plan["worker_launch_plan_sha256"]
        or item.get("post_submission_receipt_validation_law_sha256")
        != plan["post_submission_receipt_validation_law_sha256"]
        or not isinstance(item.get("runtime_payload_sha256"), str)
        or _SHA256.fullmatch(str(item["runtime_payload_sha256"])) is None
        or not isinstance(item.get("execution_flags_sha256"), str)
        or _SHA256.fullmatch(str(item["execution_flags_sha256"])) is None
        or item.get("execution_flags_sha256")
        != expected_flags["flags_sha256"]
        or type(item.get("execution_flags_bytes")) is not int
        or item.get("execution_flags_bytes") != expected_flags["flags_bytes"]
        or not isinstance(item.get("configured_environment_sha256"), str)
        or _SHA256.fullmatch(
            str(item.get("configured_environment_sha256"))
        ) is None
        or type(item.get("configured_environment_entry_count")) is not int
        or int(item.get("configured_environment_entry_count", 0)) < 1
        or not isinstance(environment, Mapping)
        or any(
            type(key) is not str or type(retained) is not str
            for key, retained in environment.items()
        )
        or item.get("configured_environment_sha256")
        != batch.canonical_sha256(environment)
        or environment
        != expected_flags["flags"]["--update-env-vars"]
        or item.get("configured_environment_entry_count") != len(environment)
        or not isinstance(arguments, list)
        or len(arguments) != 2
        or arguments[0] != "-ceu"
        or not isinstance(arguments[1], str)
        or sha256(arguments[1].encode("utf-8")).hexdigest()
        != item.get("runtime_payload_sha256")
        or item.get("submitted_execution_projection_sha256")
        != batch.canonical_sha256(projection)
        or item.get("precreate_live_job_projection_sha256")
        != batch.canonical_sha256(precreate_live_job)
        or _canonical(_live_job_semantic_projection_v1(precreate_live_job))
        != _canonical(plan["live_job_projection"])
        or not isinstance(gcloud_argv, list)
        or _canonical(gcloud_argv) != _canonical(_gcloud_argv(flags_path))
        or item.get("gcloud_argv_sha256")
        != batch.canonical_sha256(gcloud_argv)
        or not isinstance(execution_name, str)
        or _execution_from_submission(
            SubmissionObservation(
                returncode=item.get("submission_returncode", -1),
                stdout=(execution_name + "\n").encode("ascii"),
                stderr=b"",
            )
        ) != execution_name
        or item.get("reuse_job") != replacement.REUSE_JOB
        or item.get("immutable_image") != contract["immutable_image"]
        or item.get("runtime_payload_sha256")
        != plan["runtime_payload_sha256"]
        or item.get("submission_returncode") != 0
        or item.get("submission_stdout_sha256")
        != sha256((execution_name + "\n").encode("ascii")).hexdigest()
        or item.get("submission_stdout_bytes")
        != len((execution_name + "\n").encode("ascii"))
        or not isinstance(item.get("submission_stderr_sha256"), str)
        or _SHA256.fullmatch(str(item["submission_stderr_sha256"])) is None
        or type(item.get("submission_stderr_bytes")) is not int
        or int(item["submission_stderr_bytes"]) < 0
        or projection.get("schema_version")
        != SUBMITTED_EXECUTION_PROJECTION_SCHEMA
        or projection.get("execution_name") != execution_name
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
        or projection.get("command") != ["bash"]
        or projection.get("runtime_evidence_volume")
        != _expected_live_job_projection_v1()["runtime_evidence_volume"]
        or projection.get("full_execution_envelope_exactly_validated")
        is not True
        or projection.get("worker_launch_plan_sha256")
        != item.get("worker_launch_plan_sha256")
        or projection.get("execution_flags_sha256")
        != item.get("execution_flags_sha256")
        or projection.get("describe_argv")
        != _submitted_execution_describe_argv(execution_name)
        or not isinstance(projection.get("describe_stdout_sha256"), str)
        or _SHA256.fullmatch(str(projection["describe_stdout_sha256"])) is None
        or type(projection.get("describe_stdout_bytes")) is not int
        or int(projection["describe_stdout_bytes"]) < 1
        or item.get("intent_created_by_this_process") is not True
        or item.get("first_creator_submitted") is not True
        or item.get("submission_call_count") != 1
        or item.get("request_consumed") is not True
        or item.get("automatic_resubmission_allowed") is not False
        or item.get("second_replacement_allowed") is not False
        or item.get("result_or_effect_content_inspected_before_submission") is not False
    ):
        _fail("worker launch ownership frozen surface differs")
    return item


def validate_worker_launch_ownership_v1(value: object) -> dict[str, object]:
    """Pure production replay with the reviewed exact intent validator."""
    return _validate_worker_launch_ownership_v1(
        value,
        replacement_intent_validator=(
            replacement.validate_platform_replacement_intent_v1
        ),
    )


def build_replacement_worker_stage_start_v1(
    *,
    replacement_intent_identity: Mapping[str, object],
    launch_ownership_identity: Mapping[str, object],
    launch_ownership: Mapping[str, object],
    launch_plan: Mapping[str, object],
    replacement_intent_validator: IntentValidator,
) -> dict[str, object]:
    intent_identity = _identity(
        replacement_intent_identity, label="stage-start replacement intent"
    )
    ownership_identity = _identity(
        launch_ownership_identity, label="stage-start launch ownership"
    )
    ownership = _validate_worker_launch_ownership_v1(
        launch_ownership,
        replacement_intent_validator=replacement_intent_validator,
    )
    plan = validate_worker_launch_plan_v1(launch_plan)
    ownership_raw = _canonical(ownership)
    if (
        ownership_identity["uri"] != replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI
        or ownership_identity["sha256"] != sha256(ownership_raw).hexdigest()
        or ownership_identity["bytes"] != len(ownership_raw)
        or ownership["replacement_intent_identity"] != intent_identity
        or ownership["worker_launch_plan_sha256"] != plan["worker_launch_plan_sha256"]
    ):
        _fail("replacement worker stage-start lineage differs")
    body = {
        "schema_version": REPLACEMENT_STAGE_START_SCHEMA,
        "run_id": transport.RUN_ID,
        "operation": replacement.OPERATION,
        "source_ordinal": replacement.SOURCE_ORDINAL,
        "runtime_attempt_ordinal": replacement.REPLACEMENT_RUNTIME_ATTEMPT,
        "replacement_intent_identity": intent_identity,
        "launch_ownership": ownership,
        "launch_ownership_identity": ownership_identity,
        "launch_ownership_sha256": ownership["launch_ownership_sha256"],
        "worker_launch_plan": plan,
        "worker_launch_plan_sha256": plan["worker_launch_plan_sha256"],
        "post_submission_receipt_validation_law_sha256": plan[
            "post_submission_receipt_validation_law_sha256"
        ],
        "runtime_payload_sha256": plan["runtime_payload_sha256"],
        "execution_flags_sha256": ownership["execution_flags_sha256"],
        "configured_environment_sha256": ownership[
            "configured_environment_sha256"
        ],
        "submitted_execution_projection_sha256": ownership[
            "submitted_execution_projection_sha256"
        ],
        "precreate_live_job_projection_sha256": ownership[
            "precreate_live_job_projection_sha256"
        ],
        "gcloud_argv_sha256": ownership["gcloud_argv_sha256"],
        "cloud_execution_name": ownership["cloud_execution_name"],
        "cloud_job": replacement.REUSE_JOB,
        "immutable_image": plan["immutable_image"],
        "execution_envelope": plan["execution_envelope"],
        "execution_authority_identity": plan["execution_authority_identity"],
        "compute_release_identity": plan["compute_release_identity"],
        "predecessor_identity": plan["predecessor_identity"],
        "replacement_stage_start_uri": replacement.REPLACEMENT_STAGE_START_URI,
        "core_execution_requires_handshake": True,
        "published_after_exact_async_submission_response": True,
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "automatic_resubmission_allowed": False,
        "original_launch_request_reused": False,
        "primary_runtime_attempt_reused": False,
        "result_or_effect_content_inspected_before_submission": False,
        **_authority_closure(),
    }
    return _self_hash(body, "replacement_stage_start_sha256")


def _validate_replacement_worker_stage_start_v1(
    value: object, *, replacement_intent_validator: IntentValidator
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("replacement worker stage start must be one object")
    item = dict(value)
    if set(item) != _STAGE_START_KEYS:
        _fail("replacement worker stage-start fields differ")
    _validate_self_hash(
        item,
        field="replacement_stage_start_sha256",
        label="replacement worker stage start",
    )
    _false_authorities(item, label="replacement worker stage start")
    contract = replacement.frozen_platform_replacement_contract_v1()
    plan = validate_worker_launch_plan_v1(item.get("worker_launch_plan"))
    intent_identity = _identity(
        item.get("replacement_intent_identity"), label="stage-start intent"
    )
    ownership_identity = _identity(
        item.get("launch_ownership_identity"), label="stage-start ownership"
    )
    ownership = _validate_worker_launch_ownership_v1(
        item.get("launch_ownership"),
        replacement_intent_validator=replacement_intent_validator,
    )
    ownership_raw = _canonical(ownership)
    expected_flags = build_worker_execution_flags_v1(
        launch_plan=plan,
        replacement_intent_identity=intent_identity,
    )
    execution_name = item.get("cloud_execution_name")
    if (
        item.get("schema_version") != REPLACEMENT_STAGE_START_SCHEMA
        or item.get("run_id") != transport.RUN_ID
        or item.get("operation") != replacement.OPERATION
        or item.get("source_ordinal") != replacement.SOURCE_ORDINAL
        or item.get("runtime_attempt_ordinal") != replacement.REPLACEMENT_RUNTIME_ATTEMPT
        or intent_identity["uri"] != replacement.REPLACEMENT_INTENT_URI
        or ownership_identity["uri"]
        != replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI
        or ownership_identity["sha256"] != sha256(ownership_raw).hexdigest()
        or ownership_identity["bytes"] != len(ownership_raw)
        or item.get("launch_ownership_sha256")
        != ownership["launch_ownership_sha256"]
        or any(
            not isinstance(item.get(field), str)
            or _SHA256.fullmatch(str(item[field])) is None
            for field in (
                "launch_ownership_sha256",
                "worker_launch_plan_sha256",
                "runtime_payload_sha256",
                "execution_flags_sha256",
                "configured_environment_sha256",
                "submitted_execution_projection_sha256",
                "precreate_live_job_projection_sha256",
                "gcloud_argv_sha256",
            )
        )
        or item.get("worker_launch_plan_sha256")
        != plan["worker_launch_plan_sha256"]
        or item.get("post_submission_receipt_validation_law_sha256")
        != plan["post_submission_receipt_validation_law_sha256"]
        or item.get("runtime_payload_sha256")
        != plan["runtime_payload_sha256"]
        or item.get("execution_flags_sha256")
        != expected_flags["flags_sha256"]
        or item.get("configured_environment_sha256")
        != batch.canonical_sha256(
            expected_flags["flags"]["--update-env-vars"]
        )
        or item.get("submitted_execution_projection_sha256")
        != ownership["submitted_execution_projection_sha256"]
        or item.get("precreate_live_job_projection_sha256")
        != ownership["precreate_live_job_projection_sha256"]
        or item.get("gcloud_argv_sha256")
        != batch.canonical_sha256(plan["gcloud_argv"])
        or item.get("cloud_execution_name")
        != ownership["cloud_execution_name"]
        or item.get("execution_envelope") != plan["execution_envelope"]
        or item.get("execution_authority_identity")
        != plan["execution_authority_identity"]
        or item.get("compute_release_identity")
        != plan["compute_release_identity"]
        or item.get("predecessor_identity") != plan["predecessor_identity"]
        or not isinstance(execution_name, str)
        or _execution_from_submission(
            SubmissionObservation(
                returncode=0,
                stdout=(execution_name + "\n").encode("ascii"),
                stderr=b"",
            )
        ) != execution_name
        or item.get("replacement_stage_start_uri") != replacement.REPLACEMENT_STAGE_START_URI
        or item.get("cloud_job") != replacement.REUSE_JOB
        or item.get("immutable_image") != contract["immutable_image"]
        or item.get("execution_envelope")
        != contract["replacement_execution_envelope"]
        or _identity(
            item.get("execution_authority_identity"),
            label="stage-start authority",
        ) != _identity(
            contract["execution_authority_identity"], label="contract authority"
        )
        or _identity(
            item.get("compute_release_identity"), label="stage-start release"
        ) != _identity(
            contract["compute_release_identity"], label="contract release"
        )
        or _identity(
            item.get("predecessor_identity"), label="stage-start predecessor"
        ) != _identity(
            contract["predecessor_identity"], label="contract predecessor"
        )
        or item.get("core_execution_requires_handshake") is not True
        or item.get("published_after_exact_async_submission_response") is not True
        or item.get("task_count") != 1
        or item.get("parallelism") != 1
        or item.get("max_retries") != 0
        or item.get("automatic_resubmission_allowed") is not False
        or item.get("original_launch_request_reused") is not False
        or item.get("primary_runtime_attempt_reused") is not False
        or item.get("result_or_effect_content_inspected_before_submission") is not False
    ):
        _fail("replacement worker stage-start frozen surface differs")
    return item


def validate_replacement_worker_stage_start_v1(
    value: object,
) -> dict[str, object]:
    """Pure production replay with the reviewed exact intent validator."""
    return _validate_replacement_worker_stage_start_v1(
        value,
        replacement_intent_validator=(
            replacement.validate_platform_replacement_intent_v1
        ),
    )


def _controller_result(
    *,
    disposition: str,
    intent_identity: Mapping[str, object] | None,
    cloud_execution_name: str | None,
    submission: SubmissionObservation | None,
    launch_ownership_identity: Mapping[str, object] | None = None,
    replacement_stage_start_identity: Mapping[str, object] | None = None,
    submission_terminal_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    body = {
        "schema_version": CONTROLLER_RESULT_SCHEMA,
        "run_id": transport.RUN_ID,
        "disposition": disposition,
        "replacement_intent_identity": (
            None if intent_identity is None else _identity(
                intent_identity, label="controller result intent"
            )
        ),
        "cloud_execution_name": cloud_execution_name,
        "submission_call_count": 0 if submission is None else 1,
        "submission_returncode": None if submission is None else submission.returncode,
        "submission_stdout_sha256": (
            None if submission is None else sha256(submission.stdout).hexdigest()
        ),
        "submission_stderr_sha256": (
            None if submission is None else sha256(submission.stderr).hexdigest()
        ),
        "launch_ownership_identity": (
            None if launch_ownership_identity is None else _identity(
                launch_ownership_identity, label="controller result ownership"
            )
        ),
        "replacement_stage_start_identity": (
            None if replacement_stage_start_identity is None else _identity(
                replacement_stage_start_identity,
                label="controller result stage start",
            )
        ),
        "submission_terminal_identity": (
            None if submission_terminal_identity is None else _identity(
                submission_terminal_identity,
                label="controller result submission terminal",
            )
        ),
        "request_consumed": intent_identity is not None,
        "automatic_resubmission_allowed": False,
        "second_replacement_allowed": False,
        "bridge_verifier_submitted": False,
        "lane_resume_allowed": False,
        **_authority_closure(),
    }
    return _self_hash(body, "controller_result_sha256")


def _publish_consumed_submission_terminal_v1(
    *,
    backend: ReplacementControllerBackend,
    intent_identity: Mapping[str, object],
    launch_plan: Mapping[str, object],
    disposition: str,
    submission: SubmissionObservation,
    cloud_execution_name: str | None,
    failure_fingerprint: bytes,
) -> dict[str, object]:
    plan = validate_worker_launch_plan_v1(launch_plan)
    body = {
        "schema_version": SUBMISSION_TERMINAL_SCHEMA,
        "run_id": transport.RUN_ID,
        "operation": replacement.OPERATION,
        "source_ordinal": replacement.SOURCE_ORDINAL,
        "runtime_attempt_ordinal": replacement.REPLACEMENT_RUNTIME_ATTEMPT,
        "replacement_intent_identity": _identity(
            intent_identity, label="submission-terminal intent"
        ),
        "worker_launch_plan_sha256": plan["worker_launch_plan_sha256"],
        "disposition": disposition,
        "submission_attempt_count": 1,
        "submission_returncode": submission.returncode,
        "submission_stdout_sha256": sha256(submission.stdout).hexdigest(),
        "submission_stdout_bytes": len(submission.stdout),
        "submission_stderr_sha256": sha256(submission.stderr).hexdigest(),
        "submission_stderr_bytes": len(submission.stderr),
        "failure_fingerprint_sha256": sha256(failure_fingerprint).hexdigest(),
        "failure_fingerprint_bytes": len(failure_fingerprint),
        "cloud_execution_name": cloud_execution_name,
        "request_consumed": True,
        "replacement_terminal_invalid": True,
        "automatic_resubmission_allowed": False,
        "second_replacement_allowed": False,
        "result_or_effect_content_inspected": False,
        **_authority_closure(),
    }
    terminal = _self_hash(body, "submission_terminal_sha256")
    try:
        terminal_identity, _created = _create_once_or_equal(
            backend,
            uri=replacement.REPLACEMENT_EXECUTION_TERMINAL_URI,
            raw=_canonical(terminal),
            label="consumed replacement submission terminal",
        )
    except Exception as exc:
        raise T230PlatformReplacementControllerError(
            "consumed-terminal publication failed; submission remains "
            "consumed and resubmission is forbidden"
        ) from exc
    return terminal_identity


def _launch_replacement_worker_same_process_v1(
    *,
    backend: ReplacementControllerBackend,
    submitter: CloudSubmitter,
    flags_path: str,
    candidate_builder: CandidateBuilder,
    existing_intent_resolver: ExistingIntentResolver,
    intent_validator: IntentValidator,
    evidence_resolver: EvidenceResolver,
) -> dict[str, object]:
    """Create the intent and make at most one injected submit call.

    No loop or recursive recovery path in this function can call ``submit``.
    Once intent creation succeeds, every submission outcome consumes the sole
    attempt.  Only an exact async response can create ownership/start objects.
    """
    evidence = _identity(evidence_resolver(backend), label="resolved evidence")
    plan = build_worker_launch_plan_v1(
        image_evidence_identity=evidence, flags_path=flags_path
    )

    # The normalized exact live describe is intent-bound.  It is direct-known,
    # read-only, and cannot submit an execution.
    try:
        live_job = validate_live_reused_job_projection_v1(
            submitter.observe_reused_job()
        )
    except Exception as exc:
        raise T230PlatformReplacementControllerError(
            "live reused-job envelope validation failed"
        ) from exc

    # Presence is checked before the new-candidate absence census.  Existing
    # intent replay is resolve-only and can never reach the submit call.
    existing_metadata = backend.probe_known_uri_metadata(
        replacement.REPLACEMENT_INTENT_URI
    )
    if existing_metadata is not None:
        if not isinstance(existing_metadata, Mapping):
            _fail("existing replacement intent metadata is ambiguous")
        try:
            resolved_value = existing_intent_resolver(
                backend=backend,
                replacement_worker_launch_plan=plan,
                replacement_live_job_projection=live_job,
            )
        except Exception as exc:
            raise T230PlatformReplacementControllerError(
                "existing replacement intent replay failed closed"
            ) from exc
        if not isinstance(resolved_value, Mapping):
            _fail("existing replacement intent resolver differs")
        resolved = dict(resolved_value)
        if (
            resolved.get("disposition")
            != "equal-existing-intent-resolve-only"
            or resolved.get("intent_created_by_this_invocation") is not False
            or resolved.get("cloud_execution_submission_allowed_this_invocation")
            is not False
            or resolved.get("resolve_only") is not True
        ):
            _fail("existing replacement intent granted authority")
        _false_authorities(resolved, label="existing intent resolver")
        intent_identity = _identity(
            resolved.get("intent_identity"), label="existing intent"
        )
        return _controller_result(
            disposition="replacement-intent-existing-resolve-only",
            intent_identity=intent_identity,
            cloud_execution_name=None,
            submission=None,
        )

    try:
        candidate_value = candidate_builder(
            backend=backend,
            replacement_worker_launch_plan=plan,
            replacement_live_job_projection=live_job,
        )
    except TypeError as exc:
        raise T230PlatformReplacementControllerError(
            "offline replacement module lacks the intent-bound worker launch-plan API"
        ) from exc
    validated = _validate_candidate_with_plan(
        candidate_value,
        expected_plan=plan,
        expected_live_job_projection=live_job,
        intent_validator=intent_validator,
    )
    intent = dict(validated["intent"])
    intent_raw = _canonical(intent)

    # Controller-owned final metadata-only census.  The live reused-job
    # re-description below is deliberately the last external read before the
    # generation-match-zero create and one submission.
    replacement.require_platform_replacement_surface_absent_v1(
        backend=backend
    )

    # Re-describe the exact reused job after all candidate/lineage/census work.
    # Provenance can differ between observations, but the runnable job surface
    # cannot.
    try:
        precreate_live_job = validate_live_reused_job_projection_v1(
            submitter.observe_reused_job()
        )
    except Exception as exc:
        raise T230PlatformReplacementControllerError(
            "pre-create reused-job envelope validation failed"
        ) from exc
    if (
        _canonical(_live_job_semantic_projection_v1(precreate_live_job))
        != _canonical(_live_job_semantic_projection_v1(live_job))
    ):
        _fail("reused-job envelope changed before intent create")

    # No mutable observation is allowed between this second exact describe,
    # create, flag derivation, and the one submission call.
    try:
        intent_identity, intent_created = _create_once_or_equal(
            backend,
            uri=replacement.REPLACEMENT_INTENT_URI,
            raw=intent_raw,
            label="replacement intent",
        )
    except T230PlatformReplacementControllerError:
        raise
    except Exception as exc:
        # Creation may have reached storage.  It is therefore consumed and no
        # Cloud execution submission is permitted from this invocation.
        raise T230PlatformReplacementControllerError(
            "replacement intent creation was ambiguous; submission forbidden"
        ) from exc

    if not intent_created:
        return _controller_result(
            disposition="replacement-intent-existing-resolve-only",
            intent_identity=intent_identity,
            cloud_execution_name=None,
            submission=None,
        )

    execution_flags = build_worker_execution_flags_v1(
        launch_plan=plan,
        replacement_intent_identity=intent_identity,
    )
    argv = tuple(str(value) for value in plan["gcloud_argv"])
    try:
        observed_value = submitter.submit(
            argv=argv,
            execution_flags=execution_flags["flags"],
        )
        submission = _submission_observation(observed_value)
    except Exception as exc:
        # Exactly one adapter call was attempted.  The intent is consumed and
        # there is deliberately no submit call in this exception handler.
        submission = SubmissionObservation(
            returncode=-1, stdout=b"", stderr=b"submission-adapter-exception"
        )
        terminal_identity = _publish_consumed_submission_terminal_v1(
            backend=backend,
            intent_identity=intent_identity,
            launch_plan=plan,
            disposition="submission-adapter-exception-consumed",
            submission=submission,
            cloud_execution_name=None,
            failure_fingerprint=(
                f"{type(exc).__name__}:{exc}".encode("utf-8", "backslashreplace")
            ),
        )
        return _controller_result(
            disposition="replacement-worker-submission-ambiguous-consumed",
            intent_identity=intent_identity,
            cloud_execution_name=None,
            submission=submission,
            submission_terminal_identity=terminal_identity,
        )

    execution = _execution_from_submission(submission)
    if execution is None:
        terminal_identity = _publish_consumed_submission_terminal_v1(
            backend=backend,
            intent_identity=intent_identity,
            launch_plan=plan,
            disposition="submission-response-ambiguous-consumed",
            submission=submission,
            cloud_execution_name=None,
            failure_fingerprint=b"submission-response-not-one-exact-name",
        )
        return _controller_result(
            disposition="replacement-worker-submission-ambiguous-consumed",
            intent_identity=intent_identity,
            cloud_execution_name=None,
            submission=submission,
            submission_terminal_identity=terminal_identity,
        )

    try:
        submitted_execution = validate_submitted_execution_projection_v1(
            submitter.observe_submitted_execution(
                execution_name=execution,
                worker_launch_plan_sha256=plan["worker_launch_plan_sha256"],
                execution_flags_sha256=execution_flags["flags_sha256"],
            ),
            execution_name=execution,
            launch_plan=plan,
            execution_flags=execution_flags,
        )
    except Exception as exc:
        terminal_identity = _publish_consumed_submission_terminal_v1(
            backend=backend,
            intent_identity=intent_identity,
            launch_plan=plan,
            disposition="submitted-execution-envelope-unverified-consumed",
            submission=submission,
            cloud_execution_name=execution,
            failure_fingerprint=(
                f"{type(exc).__name__}:{exc}".encode("utf-8", "backslashreplace")
            ),
        )
        return _controller_result(
            disposition=(
                "replacement-worker-submitted-envelope-unverified-consumed"
            ),
            intent_identity=intent_identity,
            cloud_execution_name=execution,
            submission=submission,
            submission_terminal_identity=terminal_identity,
        )

    try:
        ownership = build_worker_launch_ownership_v1(
            replacement_intent_identity=intent_identity,
            replacement_intent=intent,
            launch_plan=plan,
            execution_flags=execution_flags,
            cloud_execution_name=execution,
            submission=submission,
            submitted_execution=submitted_execution,
            precreate_live_job_projection=precreate_live_job,
            replacement_intent_validator=intent_validator,
        )
        ownership_identity, _ownership_created = _create_once_or_equal(
            backend,
            uri=replacement.REPLACEMENT_LAUNCH_OWNERSHIP_URI,
            raw=_canonical(ownership),
            label="replacement launch ownership",
        )
    except Exception as exc:
        try:
            terminal_identity = _publish_consumed_submission_terminal_v1(
                backend=backend,
                intent_identity=intent_identity,
                launch_plan=plan,
                disposition="launch-ownership-publication-failed-consumed",
                submission=submission,
                cloud_execution_name=execution,
                failure_fingerprint=(
                    f"{type(exc).__name__}:{exc}".encode(
                        "utf-8", "backslashreplace"
                    )
                ),
            )
        except Exception as terminal_exc:
            raise T230PlatformReplacementControllerError(
                "ownership and consumed-terminal publication both failed; "
                "submission remains consumed"
            ) from terminal_exc
        return _controller_result(
            disposition="replacement-worker-ownership-undurable-consumed",
            intent_identity=intent_identity,
            cloud_execution_name=execution,
            submission=submission,
            submission_terminal_identity=terminal_identity,
        )
    try:
        start = build_replacement_worker_stage_start_v1(
            replacement_intent_identity=intent_identity,
            launch_ownership_identity=ownership_identity,
            launch_ownership=ownership,
            launch_plan=plan,
            replacement_intent_validator=intent_validator,
        )
        start_identity, _start_created = _create_once_or_equal(
            backend,
            uri=replacement.REPLACEMENT_STAGE_START_URI,
            raw=_canonical(start),
            label="replacement worker stage start",
        )
    except Exception as exc:
        try:
            terminal_identity = _publish_consumed_submission_terminal_v1(
                backend=backend,
                intent_identity=intent_identity,
                launch_plan=plan,
                disposition="worker-stage-start-publication-failed-consumed",
                submission=submission,
                cloud_execution_name=execution,
                failure_fingerprint=(
                    f"{type(exc).__name__}:{exc}".encode(
                        "utf-8", "backslashreplace"
                    )
                ),
            )
        except Exception as terminal_exc:
            raise T230PlatformReplacementControllerError(
                "stage-start and consumed-terminal publication both failed; "
                "submission remains consumed"
            ) from terminal_exc
        return _controller_result(
            disposition="replacement-worker-stage-start-undurable-consumed",
            intent_identity=intent_identity,
            cloud_execution_name=execution,
            submission=submission,
            launch_ownership_identity=ownership_identity,
            submission_terminal_identity=terminal_identity,
        )
    return _controller_result(
        disposition="replacement-worker-submitted-once-handshake-durable",
        intent_identity=intent_identity,
        cloud_execution_name=execution,
        submission=submission,
        launch_ownership_identity=ownership_identity,
        replacement_stage_start_identity=start_identity,
    )


def launch_replacement_worker_same_process_v1(
    *,
    backend: ReplacementControllerBackend,
    submitter: CloudSubmitter,
) -> dict[str, object]:
    """Reviewed public entry: no caller-selected validator or evidence."""
    return _launch_replacement_worker_same_process_v1(
        backend=backend,
        submitter=submitter,
        flags_path=replacement.REAL_ARTIFACT_PREFLIGHT_FLAGS_PATH,
        candidate_builder=(
            replacement.prepare_platform_replacement_intent_candidate_v1
        ),
        existing_intent_resolver=(
            replacement.resolve_equal_existing_platform_replacement_intent_v1
        ),
        intent_validator=replacement.validate_platform_replacement_intent_v1,
        evidence_resolver=_resolve_frozen_image_evidence_identity_v1,
    )


def _preflight_replacement_worker_real_artifacts_v1(
    *,
    backend: ReplacementControllerBackend,
    submitter: CloudSubmitter,
    evidence_resolver: EvidenceResolver,
    preflight_builder: Callable[..., Mapping[str, object]],
    preflight_validator: Callable[..., Mapping[str, object]],
) -> dict[str, object]:
    """Exercise the real read boundary with no create or submit authority."""
    evidence = _identity(evidence_resolver(backend), label="preflight evidence")
    plan = build_worker_launch_plan_v1(
        image_evidence_identity=evidence,
        flags_path=replacement.REAL_ARTIFACT_PREFLIGHT_FLAGS_PATH,
    )
    try:
        live_job = validate_live_reused_job_projection_v1(
            submitter.observe_reused_job()
        )
    except Exception as exc:
        raise T230PlatformReplacementControllerError(
            "preflight live reused-job validation failed"
        ) from exc
    try:
        receipt_value = preflight_builder(
            backend=backend,
            replacement_worker_launch_plan=plan,
            replacement_live_job_projection=live_job,
        )
        receipt = dict(preflight_validator(receipt_value))
    except Exception as exc:
        raise T230PlatformReplacementControllerError(
            "real-artifact preflight failed closed"
        ) from exc
    if (
        receipt.get("replacement_worker_launch_plan_sha256")
        != plan["worker_launch_plan_sha256"]
        or receipt.get("live_job_projection_sha256")
        != batch.canonical_sha256(live_job)
        or receipt.get("gcs_publication_count") != 0
        or receipt.get("cloud_submit_count") != 0
        or receipt.get("realized_outcomes_read") is not False
        or receipt.get("result_or_effect_content_inspected") is not False
        or receipt.get("review_lock_read") is not False
        or receipt.get("intent_built") is not False
        or receipt.get("intent_published") is not False
        or receipt.get("passed") is not True
    ):
        _fail("real-artifact preflight receipt authority differs")
    _false_authorities(receipt, label="real-artifact preflight receipt")
    return receipt


def preflight_replacement_worker_real_artifacts_v1(
    *,
    backend: ReplacementControllerBackend,
    submitter: CloudSubmitter,
) -> dict[str, object]:
    """Reviewed public preflight: exact reads only; no caller-shaped law."""
    return _preflight_replacement_worker_real_artifacts_v1(
        backend=backend,
        submitter=submitter,
        evidence_resolver=_resolve_frozen_image_evidence_identity_v1,
        preflight_builder=(
            replacement.preflight_platform_replacement_real_artifacts_v1
        ),
        preflight_validator=(
            replacement.validate_platform_replacement_real_artifact_preflight_v1
        ),
    )


def _identity_environment(
    prefix: str, identity_value: Mapping[str, object]
) -> dict[str, str]:
    retained = _identity(identity_value, label=prefix.lower())
    return {
        f"{prefix}_URI": str(retained["uri"]),
        f"{prefix}_GENERATION": str(retained["generation"]),
        f"{prefix}_SHA256": str(retained["sha256"]),
        f"{prefix}_BYTES": str(retained["bytes"]),
    }


def _primary_configured_environment_v1(
    lineage: Mapping[str, object],
) -> dict[str, str]:
    proof = lineage.get("primary_launch_publication_proof")
    predecessors = lineage.get("predecessor_identities")
    if (
        not isinstance(proof, Mapping)
        or not isinstance(predecessors, Sequence)
        or isinstance(predecessors, (str, bytes))
        or len(predecessors) != 1
    ):
        _fail("primary launch lineage environment differs")
    environment = {
        ENABLE_ENV: "1",
        "T230_OPERATION": replacement.OPERATION,
        "T230_SOURCE_ORDINAL": str(replacement.SOURCE_ORDINAL),
        "T230_ATTEMPT": str(replacement.PRIMARY_RUNTIME_ATTEMPT),
        "T230_BENCHMARK": "0",
        "T230_IMAGE": replacement.FROZEN_D2_URI,
        "T230_PRED_COUNT": "1",
    }
    environment.update(_identity_environment(
        "T230_PRED0", predecessors[0]
    ))
    environment.update({
        "T230_PRED1_URI": "", "T230_PRED1_GENERATION": "",
        "T230_PRED1_SHA256": "", "T230_PRED1_BYTES": "",
    })
    environment.update(_identity_environment(
        "T230_CONTRACT", lineage["transport_contract_identity"]
    ))
    environment.update(_identity_environment(
        "T230_EVIDENCE", lineage["image_evidence_identity"]
    ))
    environment.update(_identity_environment(
        "T230_AUTHORITY", lineage["execution_authority_identity"]
    ))
    environment.update(_identity_environment(
        "T230_LAUNCH_REQUEST", proof["target_identity"]
    ))
    environment.update(_identity_environment(
        "T230_LAUNCH_INTENT", proof["intent_identity"]
    ))
    environment.update(_identity_environment(
        "T230_LAUNCH_COMPLETION", proof["completion_identity"]
    ))
    environment.update(_identity_environment(
        "T230_COMPUTE", lineage["compute_release_identity"]
    ))
    for prefix in ("T230_RESULT", "T230_LANE0", "T230_LANE1"):
        environment.update({
            f"{prefix}_URI": "", f"{prefix}_GENERATION": "",
            f"{prefix}_SHA256": "", f"{prefix}_BYTES": "",
        })
    return dict(sorted(environment.items()))


def _one_mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be one object")
    return dict(value)


def _cloud_run_v1_envelope(
    value: object,
    *,
    expected_name: str,
    expected_job: str,
    job_resource: bool,
) -> dict[str, object]:
    body = _one_mapping(value, label="Cloud Run describe")
    metadata = _one_mapping(body.get("metadata"), label="Cloud Run metadata")
    spec = _one_mapping(body.get("spec"), label="Cloud Run spec")
    if job_resource:
        outer = _one_mapping(spec.get("template"), label="job outer template")
        outer_spec = _one_mapping(outer.get("spec"), label="job outer spec")
    else:
        outer_spec = spec
    task_template = _one_mapping(
        outer_spec.get("template"), label="Cloud Run task template"
    )
    task = _one_mapping(task_template.get("spec"), label="Cloud Run task spec")
    containers = task.get("containers")
    if (
        not isinstance(containers, Sequence)
        or isinstance(containers, (str, bytes))
        or len(containers) != 1
    ):
        _fail("Cloud Run describe must contain one container")
    container = _one_mapping(containers[0], label="Cloud Run container")
    limits = _one_mapping(
        _one_mapping(container.get("resources"), label="container resources").get(
            "limits"
        ),
        label="container resource limits",
    )
    env_rows = container.get("env", [])
    if not isinstance(env_rows, Sequence) or isinstance(env_rows, (str, bytes)):
        _fail("Cloud Run configured environment differs")
    configured_environment: dict[str, str] = {}
    for row_value in env_rows:
        row = _one_mapping(row_value, label="Cloud Run environment row")
        keys = set(row)
        name = row.get("name")
        if keys == {"name"}:
            if (
                not isinstance(name, str)
                or name not in _CLOUD_RUN_NAME_ONLY_EMPTY_ENVIRONMENT_NAMES
            ):
                _fail("Cloud Run name-only environment row is not frozen empty")
            retained = ""
        elif keys == {"name", "value"}:
            retained = row.get("value")
        else:
            _fail("Cloud Run environment row is not one literal value")
        if (
            not isinstance(name, str)
            or not isinstance(retained, str)
            or name in configured_environment
        ):
            _fail("Cloud Run environment key/value differs")
        configured_environment[name] = retained
    volumes = task.get("volumes", [])
    mounts = container.get("volumeMounts", [])
    expected_volumes = [{
        "name": "foundry-t230-runtime-evidence",
        "emptyDir": {"medium": "Memory", "sizeLimit": "1Mi"},
    }]
    expected_mounts = [{
        "name": "foundry-t230-runtime-evidence",
        "mountPath": "/etc/nfl-dfs",
    }]
    labels = metadata.get("labels", {})
    name = metadata.get("name")
    if (
        not isinstance(name, str)
        or not (name == expected_name or name.endswith("/" + expected_name))
        or (not job_resource and (
            not isinstance(labels, Mapping)
            or labels.get("run.googleapis.com/job") != expected_job
        ))
        or volumes != expected_volumes
        or mounts != expected_mounts
    ):
        _fail("Cloud Run describe identity/volume differs")
    return {
        "job": expected_job,
        "image": container.get("image"),
        "service_account": task.get("serviceAccountName"),
        "cpu": limits.get("cpu"),
        "memory": limits.get("memory"),
        "task_count": outer_spec.get("taskCount"),
        "parallelism": outer_spec.get("parallelism"),
        "max_retries": task.get("maxRetries"),
        "task_timeout_seconds": int(str(task.get("timeoutSeconds", "-1"))),
        "command": container.get("command"),
        "args": container.get("args"),
        "configured_environment": dict(sorted(configured_environment.items())),
        "runtime_evidence_volume": {
            "type": "in-memory",
            "name": "foundry-t230-runtime-evidence",
            "size_limit": "1Mi",
            "mount_path": "/etc/nfl-dfs",
        },
    }
class SubprocessCloudSubmitter:
    """Direct-known production observer and one-shot submission adapter."""

    def __init__(self) -> None:
        self._last_execution_flags: dict[str, object] | None = None

    @staticmethod
    def _describe(argv: Sequence[str], *, label: str) -> tuple[object, bytes]:
        completed = subprocess.run(
            list(argv), check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if completed.returncode != 0 or not completed.stdout:
            _fail(f"{label} direct-known describe failed")
        try:
            value = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise T230PlatformReplacementControllerError(
                f"{label} direct-known describe is not JSON"
            ) from exc
        return value, completed.stdout

    def observe_reused_job(self) -> Mapping[str, object]:
        argv = list(replacement.LIVE_JOB_DESCRIBE_ARGV)
        value, raw = self._describe(argv, label="live reused job")
        body = _one_mapping(value, label="live reused job")
        envelope = _cloud_run_v1_envelope(
            body,
            expected_name=replacement.REUSE_JOB,
            expected_job=replacement.REUSE_JOB,
            job_resource=True,
        )
        return {
            "schema_version": LIVE_JOB_PROJECTION_SCHEMA,
            **envelope,
            "describe_argv": argv,
            "describe_stdout_sha256": sha256(raw).hexdigest(),
            "describe_stdout_bytes": len(raw),
            "cloud_describe_exactly_validated": True,
        }

    def observe_submitted_execution(
        self,
        *,
        execution_name: str,
        worker_launch_plan_sha256: str,
        execution_flags_sha256: str,
    ) -> Mapping[str, object]:
        if self._last_execution_flags is None:
            _fail("submitted execution describe preceded submission")
        argv = _submitted_execution_describe_argv(execution_name)
        value, raw = self._describe(argv, label="submitted execution")
        body = _one_mapping(value, label="submitted execution")
        envelope = _cloud_run_v1_envelope(
            body,
            expected_name=execution_name,
            expected_job=replacement.REUSE_JOB,
            job_resource=False,
        )
        return {
            "schema_version": SUBMITTED_EXECUTION_PROJECTION_SCHEMA,
            "execution_name": execution_name,
            **envelope,
            "full_execution_envelope_exactly_validated": True,
            "worker_launch_plan_sha256": worker_launch_plan_sha256,
            "execution_flags_sha256": execution_flags_sha256,
            "describe_argv": argv,
            "describe_stdout_sha256": sha256(raw).hexdigest(),
            "describe_stdout_bytes": len(raw),
        }

    def observe_primary_terminal(
        self,
        *,
        execution_name: str,
        expected_environment: Mapping[str, str],
    ) -> Mapping[str, object]:
        if execution_name != replacement.FAILED_EXECUTION:
            _fail("primary terminal execution differs")
        execution_argv = list(replacement.EXECUTION_DESCRIBE_ARGV)
        task_argv = list(replacement.TASK_DESCRIBE_ARGV)
        execution_value, execution_raw = self._describe(
            execution_argv, label="primary failed execution"
        )
        task_value, task_raw = self._describe(
            task_argv, label="primary failed task"
        )
        execution_body = _one_mapping(
            execution_value, label="primary failed execution"
        )
        if (
            not isinstance(task_value, Sequence)
            or isinstance(task_value, (str, bytes))
            or len(task_value) != 1
        ):
            _fail("primary exact execution-scoped task query differs")
        task_body = _one_mapping(task_value[0], label="primary failed task")
        envelope = _cloud_run_v1_envelope(
            execution_body,
            expected_name=replacement.FAILED_EXECUTION,
            expected_job=replacement.REUSE_JOB,
            job_resource=False,
        )
        expected_env = dict(sorted(expected_environment.items()))
        arguments = envelope.get("args")
        if (
            envelope != {
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
                "args": arguments,
                "configured_environment": expected_env,
                "runtime_evidence_volume": _expected_live_job_projection_v1()[
                    "runtime_evidence_volume"
                ],
            }
            or not isinstance(arguments, list)
            or len(arguments) != 2
            or arguments[0] != "-ceu"
            or not isinstance(arguments[1], str)
            or len(arguments[1].encode("utf-8"))
            != replacement.FROZEN_PRIMARY_RUNTIME_PAYLOAD_BYTES
            or sha256(arguments[1].encode("utf-8")).hexdigest()
            != replacement.FROZEN_PRIMARY_RUNTIME_PAYLOAD_SHA256
        ):
            _fail("primary execution exact envelope/environment differs")
        execution_status = _one_mapping(
            execution_body.get("status"), label="primary execution status"
        )
        execution_conditions = execution_status.get("conditions")
        if not isinstance(execution_conditions, Sequence):
            _fail("primary execution conditions differ")
        completed = [
            _one_mapping(row, label="execution Completed condition")
            for row in execution_conditions
            if isinstance(row, Mapping) and row.get("type") == "Completed"
        ]
        task_metadata = _one_mapping(
            task_body.get("metadata"), label="primary task metadata"
        )
        task_labels = task_metadata.get("labels")
        task_spec = _one_mapping(task_body.get("spec"), label="primary task spec")
        task_status = _one_mapping(
            task_body.get("status"), label="primary task status"
        )
        task_conditions = task_status.get("conditions")
        if not isinstance(task_conditions, Sequence):
            _fail("primary task conditions differ")
        task_completed = [
            _one_mapping(row, label="task Completed condition")
            for row in task_conditions
            if isinstance(row, Mapping) and row.get("type") == "Completed"
        ]
        last = _one_mapping(
            task_status.get("lastAttemptResult"), label="last task attempt"
        )
        last_status = _one_mapping(last.get("status"), label="last task status")
        if (
            len(completed) != 1
            or completed[0].get("status") != "False"
            or completed[0].get("message")
            != (
                "Task atlas-minimal-c-s2023-w1-v1-rffts-task0 failed with "
                "exit code: 0 and message: Internal error."
            )
            or not isinstance(execution_status.get("completionTime"), str)
            or not str(execution_status["completionTime"]).endswith("Z")
            or task_metadata.get("name") != replacement.FAILED_TASK
            or not isinstance(task_labels, Mapping)
            or task_labels.get("run.googleapis.com/execution")
            != replacement.FAILED_EXECUTION
            or task_labels.get("run.googleapis.com/job")
            != replacement.REUSE_JOB
            or task_labels.get("cloud.googleapis.com/location")
            != transport.REGION
            or task_spec != {}
            or len(task_completed) != 1
            or task_completed[0].get("status") != "False"
            or task_completed[0].get("message") != "Internal error."
            or "index" in task_status
            or "retried" in task_status
            or last_status != {"code": 13, "message": "Internal error."}
            or "exitCode" in last
        ):
            _fail("primary execution/task terminal literals differ")
        contract = replacement.frozen_platform_replacement_contract_v1()
        configured_environment_raw = _canonical(expected_env)
        projection = {
            "schema_version": replacement.TERMINAL_PROJECTION_SCHEMA,
            "execution_name": replacement.FAILED_EXECUTION,
            "job": replacement.REUSE_JOB,
            "operation": replacement.OPERATION,
            "source_ordinal": replacement.SOURCE_ORDINAL,
            "runtime_attempt_ordinal": replacement.PRIMARY_RUNTIME_ATTEMPT,
            "completed_status": "False",
            "task_completed_status": "False",
            "completed_message": completed[0]["message"],
            "execution_describe_argv": execution_argv,
            "execution_describe_stdout_sha256": sha256(execution_raw).hexdigest(),
            "execution_describe_stdout_bytes": len(execution_raw),
            "task_describe_argv": task_argv,
            "task_describe_stdout_sha256": sha256(task_raw).hexdigest(),
            "task_describe_stdout_bytes": len(task_raw),
            "configured_environment_sha256": sha256(
                configured_environment_raw
            ).hexdigest(),
            "configured_environment_entry_count": len(expected_env),
            "failed_count": execution_status.get("failedCount"),
            "succeeded_count": execution_status.get("succeededCount", 0),
            "cancelled_count": execution_status.get("cancelledCount", 0),
            "task_count": 1,
            "parallelism": 1,
            "max_retries": 0,
            "task_timeout_seconds": transport.TASK_TIMEOUT_SECONDS,
            "service_account": replacement.SERVICE_ACCOUNT,
            "image": replacement.FROZEN_D2_URI,
            "cpu": "8",
            "memory": "32Gi",
            "task_spec": {},
            "task_status_index_present": False,
            "task_status_retried_present": False,
            "task_last_attempt_exit_code_present": False,
            "cloud_task_name": replacement.FAILED_TASK,
            "last_attempt_status_code": 13,
            "last_attempt_status_message": "Internal error.",
            "execution_completed_message_exit_code": 0,
            "primary_stage_start_identity": contract["primary_stage_start_identity"],
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
            "runtime_evidence_volume": _expected_live_job_projection_v1()[
                "runtime_evidence_volume"
            ],
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
        return replacement.validate_primary_terminal_projection_v1(projection)

    def submit(
        self,
        *,
        argv: Sequence[str],
        execution_flags: Mapping[str, object],
    ) -> SubmissionObservation:
        if self._last_execution_flags is not None:
            _fail("submission adapter was already consumed")
        if not isinstance(execution_flags, Mapping):
            _fail("submission flags differ")
        self._last_execution_flags = dict(execution_flags)
        if isinstance(argv, (str, bytes)) or any(
            not isinstance(value, str) for value in argv
        ):
            _fail("gcloud submission argv types differ")
        flags_argument = next(
            (value for value in argv if value.startswith("--flags-file=")), None
        )
        if flags_argument is None:
            _fail("gcloud argv lacks the exact flags path")
        path = Path(flags_argument.split("=", 1)[1])
        _absolute_regular_target(str(path), label="execution flags path")
        if list(argv) != _gcloud_argv(str(path)):
            _fail("gcloud submission argv differs from exact launch plan")
        raw = _canonical(execution_flags) + b"\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                FLAGS_FILE_MODE,
            )
        except FileExistsError:
            metadata = path.stat(follow_symlinks=False)
            if (
                path.is_symlink()
                or not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != FLAGS_FILE_MODE
                or metadata.st_uid != os.geteuid()
                or path.read_bytes() != raw
            ):
                _fail("existing execution flags file differs")
        else:
            try:
                written = 0
                while written < len(raw):
                    count = os.write(descriptor, raw[written:])
                    if count < 1:
                        _fail("execution flags write made no progress")
                    written += count
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        metadata = path.stat(follow_symlinks=False)
        if (
            path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != FLAGS_FILE_MODE
            or metadata.st_uid != os.geteuid()
        ):
            _fail("execution flags file ownership/mode differs")
        completed = subprocess.run(
            list(argv),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return SubmissionObservation(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class GCSPlatformReplacementBackend(transport_cli.GCSJournalBackend):
    """Generation-pinned GCS backend with no list/latest operation."""

    def __init__(self, client: object, cloud: SubprocessCloudSubmitter) -> None:
        super().__init__(client)
        self._cloud = cloud

    def probe_known_uri_metadata(
        self, uri: str
    ) -> Mapping[str, object] | None:
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.reload()
        except Exception as exc:
            try:
                from google.api_core.exceptions import NotFound
            except ImportError:  # pragma: no cover - production dependency
                NotFound = ()  # type: ignore[assignment,misc]
            if NotFound and isinstance(exc, NotFound):
                return None
            raise
        if blob.generation is None:
            _fail("known-name metadata probe lacks generation")
        return {
            "uri": uri,
            "generation": str(blob.generation),
            "present": True,
            "content_inspected": False,
        }

    def observe_primary_terminal(
        self, execution_name: str
    ) -> Mapping[str, object]:
        # Reopen the pinned launch/authority lineage first, so the configured
        # environment is compared against exact journal identities rather than
        # trusting values echoed by the execution describe.
        lineage = replacement.reopen_fixed_primary_lineage_for_controller_v1(
            backend=self
        )
        expected_environment = _primary_configured_environment_v1(lineage)
        return self._cloud.observe_primary_terminal(
            execution_name=execution_name,
            expected_environment=expected_environment,
        )


def _load_identity(path: Path) -> dict[str, object]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        _fail("identity input must be one absolute regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise T230PlatformReplacementControllerError(
            "identity input is not valid JSON"
        ) from exc
    return _identity(value, label="identity input")


def _write_once(path: Path, value: Mapping[str, object]) -> None:
    if not path.is_absolute() or path.is_symlink():
        _fail("output must be one absolute non-symlink path")
    raw = _canonical(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError:
        if not path.is_file() or path.is_symlink() or path.read_bytes() != raw:
            _fail("create-once output differs")


def _fixed_preflight_receipt_path_v1() -> Path:
    """Return the fixed lexical target only when its whole path is safe."""
    repository_root = Path(transport.REPOSITORY_ROOT)
    relative = Path(
        replacement.REAL_ARTIFACT_PREFLIGHT_RECEIPT_RELATIVE_PATH
    )
    if (
        not repository_root.is_absolute()
        or repository_root.is_symlink()
        or not repository_root.is_dir()
        or relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        _fail("real-artifact preflight receipt root/path differs")
    parent = repository_root
    for part in relative.parts[:-1]:
        parent = parent / part
        if parent.is_symlink() or not parent.is_dir():
            _fail("real-artifact preflight receipt parent is unsafe")
    target = parent / relative.parts[-1]
    if target.is_symlink() or target.exists():
        _fail("real-artifact preflight receipt already exists")
    return target


def _write_preflight_receipt_once(
    path: Path, value: Mapping[str, object]
) -> None:
    """Write the one tracked smoke receipt; any prior path blocks rerun."""
    fixed_path = _fixed_preflight_receipt_path_v1()
    if path != fixed_path:
        _fail("real-artifact preflight receipt path differs")
    raw = _canonical(value) + b"\n"
    directory_fd: int | None = None
    file_fd: int | None = None
    try:
        directory_fd = os.open(
            path.parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        file_fd = os.open(
            path.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | os.O_CLOEXEC,
            0o644,
            dir_fd=directory_fd,
        )
        written = 0
        while written < len(raw):
            count = os.write(file_fd, raw[written:])
            if count < 1:
                _fail("real-artifact preflight receipt write made no progress")
            written += count
        os.fsync(file_fd)
    except FileExistsError as exc:
        raise T230PlatformReplacementControllerError(
            "real-artifact preflight receipt create-once collision"
        ) from exc
    except OSError as exc:
        raise T230PlatformReplacementControllerError(
            "real-artifact preflight receipt secure write failed"
        ) from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reviewed T230 ordinal-6 same-process replacement controller"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("parked")
    launch = commands.add_parser("launch-worker")
    launch.add_argument("--execute", action="store_true", required=True)
    preflight = commands.add_parser("preflight-worker")
    preflight.add_argument("--preflight", action="store_true", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "parked":
        print('{"cloud_submission_enabled":false,"state":"parked"}')
        return 0
    if args.command == "launch-worker" and os.environ.get(ENABLE_ENV) != "1":
        _fail(f"{ENABLE_ENV}=1 is required for launch-worker")
    preflight_output: Path | None = None
    if args.command == "preflight-worker":
        # This check is deliberately lexical and precedes storage-client
        # construction or any real-artifact observation.
        preflight_output = _fixed_preflight_receipt_path_v1()
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover - production dependency
        raise T230PlatformReplacementControllerError(
            "google-cloud-storage is required for launch-worker"
        ) from exc
    cloud = SubprocessCloudSubmitter()
    backend = GCSPlatformReplacementBackend(
        storage.Client(project=transport.PROJECT), cloud
    )
    if args.command == "preflight-worker":
        result = preflight_replacement_worker_real_artifacts_v1(
            backend=backend, submitter=cloud
        )
        if preflight_output is None:  # pragma: no cover - parser-owned branch
            _fail("real-artifact preflight receipt path is absent")
        _write_preflight_receipt_once(preflight_output, result)
    else:
        result = launch_replacement_worker_same_process_v1(
            backend=backend,
            submitter=cloud,
        )
    print(_canonical(result).decode("utf-8"))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
