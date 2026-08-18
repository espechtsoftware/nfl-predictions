"""Fail-closed helpers for the ATLAS repair6 proof-transport amendment.

This module performs no network, storage, query, solver, or launch action.
Scientific shard bytes stay opaque: the equivalence helper removes only the
two exact, independently validated leading provenance fields and compares the
complete remaining bytes.
"""

from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence


PROTOCOL_ID = "20260817-atlas-repair6-proof-transport-v1"
PROTOCOL_SHA256 = (
    "23bf6bc88c46d18205360910e2e8875621d0201df70022f05d36893240115e29"
)

PROJECT = "nfl-predictions-503414"
SERVICE_ACCOUNT = "817589974517-compute@developer.gserviceaccount.com"
REPAIR5_CODE_SHA = "60f296fdad769b30c0bb7334118698f156e462b9"
REPAIR5_IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
    "sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb"
)
REPAIR6_CODE_SHA = "061767492628fccf0c9058fa8e1d41acb5fd55dc"
REPAIR6_IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
    "sha256:86b852e838f1ac685f40d8f0aed136337cdc5e230f38335076e45aaf24727487"
)

REPAIR6_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/"
    "20260817-atlas-matched-diversity-mvp-v1-repair6"
)
LEGACY_PROOF_PREFIX = REPAIR6_PREFIX + "-proof"
REPLACEMENT_PROOF_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/"
    "20260817-atlas-matched-diversity-mvp-v1-repair6-proof-transport-v1"
)
TARGET_JOB = "atlas-md-s2023-w7-r6"
TARGET_EXECUTION = "atlas-md-s2023-w7-r6-9pxdt"
TARGET_URI = REPAIR6_PREFIX + "/slate-2023-7.json"
FAILED_PROOF_JOB = "atlas-md-s2023-w1-r6-proof"
FAILED_PROOF_EXECUTION = "atlas-md-s2023-w1-r6-proof-m6ctm"
FAILED_PROOF_URI = LEGACY_PROOF_PREFIX + "/slate-2023-1.json"
REPLACEMENT_PROOF_JOB = "atlas-md-s2023-w1-r6-proof-r1"
REPLACEMENT_PROOF_URI = REPLACEMENT_PROOF_PREFIX + "/slate-2023-1.json"
EXPECTED_FAILURE = "RuntimeError: ATLAS MVP shard season/week/output identity differs"
FORBIDDEN_PROGRESS_MARKERS = (
    "ATLAS_MVP_SEED_COMPLETE",
    "ATLAS_MVP_SLATE_COMPLETE",
    "ATLAS_MVP_SHARD_RESULT",
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_PUBLIC_SUFFIX_PREFIX = b'"season":2023,"shard_week":1,'


def canonical_provenance_prefix(*, image: str, code_sha: str) -> bytes:
    """Return the exact leading bytes emitted by the pinned canonical writer."""
    if not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image):
        raise ValueError("ATLAS proof provenance image differs")
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        raise ValueError("ATLAS proof provenance code SHA differs")
    image_json = json.dumps(image, ensure_ascii=True, separators=(",", ":"))
    code_json = json.dumps(code_sha, ensure_ascii=True, separators=(",", ":"))
    return (
        f'{{"analysis_image":{image_json},"code_sha":{code_json},'
    ).encode("ascii")


def opaque_suffix(raw: bytes, *, image: str, code_sha: str) -> bytes:
    """Remove exactly the two leading provenance fields without JSON parsing."""
    if not isinstance(raw, bytes) or not raw:
        raise ValueError("ATLAS proof object bytes are missing")
    prefix = canonical_provenance_prefix(image=image, code_sha=code_sha)
    if not raw.startswith(prefix):
        raise ValueError("ATLAS proof leading provenance differs")
    suffix = raw[len(prefix):]
    if not suffix.startswith(_PUBLIC_SUFFIX_PREFIX) or not suffix.endswith(b"\n"):
        raise ValueError("ATLAS proof opaque payload framing differs")
    return suffix


def compare_opaque_provenance_normalized(
    repair5_raw: bytes,
    repair6_raw: bytes,
) -> dict[str, Any]:
    """Require exact equality after removing only forced provenance bytes."""
    repair5_suffix = opaque_suffix(
        repair5_raw, image=REPAIR5_IMAGE, code_sha=REPAIR5_CODE_SHA,
    )
    repair6_suffix = opaque_suffix(
        repair6_raw, image=REPAIR6_IMAGE, code_sha=REPAIR6_CODE_SHA,
    )
    if repair5_raw == repair6_raw:
        raise ValueError("ATLAS proof raw objects unexpectedly match")
    if repair5_suffix != repair6_suffix:
        raise ValueError("ATLAS proof normalized opaque bytes differ")
    suffix_sha = sha256(repair5_suffix).hexdigest()
    return {
        "version": "atlas-repair6-proof-provenance-equivalence-v1",
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": PROTOCOL_SHA256,
        "repair5_raw_bytes": len(repair5_raw),
        "repair5_raw_sha256": sha256(repair5_raw).hexdigest(),
        "repair6_raw_bytes": len(repair6_raw),
        "repair6_raw_sha256": sha256(repair6_raw).hexdigest(),
        "raw_bytes_equal": False,
        "normalized_suffix_bytes": len(repair5_suffix),
        "normalized_suffix_sha256": suffix_sha,
        "normalized_suffix_equal": True,
        "normalized_fields": ["analysis_image", "code_sha"],
        "json_parsed": False,
        "slate_fields_inspected": False,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "production_change_licensed": False,
        "disposition": "valid-provenance-normalized-byte-equivalence",
    }


def completed_state(value: Mapping[str, Any]) -> str:
    """Return Unknown/True/False from a complete fail-closed status object."""
    status = value.get("status")
    if not isinstance(status, Mapping):
        raise ValueError("ATLAS proof execution status is missing")
    conditions = status.get("conditions", [])
    if not isinstance(conditions, Sequence) or isinstance(
        conditions, (str, bytes)
    ):
        raise ValueError("ATLAS proof execution conditions differ")
    completed = [
        row for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    malformed = [
        row for row in conditions
        if not isinstance(row, Mapping)
    ]
    if malformed or len(completed) > 1:
        raise ValueError("ATLAS proof Completed condition population differs")
    succeeded = int(status.get("succeededCount") or 0)
    failed = int(status.get("failedCount") or 0)
    cancelled = int(status.get("cancelledCount") or 0)
    completion_time = status.get("completionTime")
    if not completed:
        if succeeded or failed or cancelled or completion_time:
            raise ValueError("ATLAS proof terminal counts lack Completed condition")
        return "Unknown"
    state = completed[0].get("status")
    if state == "Unknown":
        if succeeded or failed or cancelled or completion_time:
            raise ValueError("ATLAS proof Unknown status has terminal evidence")
        return "Unknown"
    if state == "True":
        if succeeded != 1 or failed or cancelled or not completion_time:
            raise ValueError("ATLAS proof successful terminal evidence differs")
        return "True"
    if state == "False":
        if succeeded or failed + cancelled != 1 or not completion_time:
            raise ValueError("ATLAS proof failed terminal evidence differs")
        return "False"
    raise ValueError("ATLAS proof Completed state differs")


def validate_execution_contract(
    value: Mapping[str, Any],
    *,
    job: str,
    execution: str,
    season: str,
    week: str,
    uri: str,
    command: str,
    expected_state: str,
) -> dict[str, Any]:
    """Validate one immutable repair6 execution without inspecting an object."""
    if value.get("metadata", {}).get("name") != execution or \
            not execution.startswith(job + "-"):
        raise ValueError("ATLAS proof execution identity differs")
    spec = value.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            not isinstance(containers, list) or len(containers) != 1:
        raise ValueError("ATLAS proof task shape differs")
    container = containers[0]
    env_rows = container.get("env", [])
    if not isinstance(env_rows, list) or any(
        not isinstance(row, Mapping) for row in env_rows
    ):
        raise ValueError("ATLAS proof environment differs")
    env = {str(row.get("name")): str(row.get("value", "")) for row in env_rows}
    if len(env) != len(env_rows) or container.get("image") != REPAIR6_IMAGE or \
            container.get("command") != ["python"] or \
            container.get("args") != [
                "-c", command, "--season", season, "--week", week,
                "--output-uri", uri,
            ] or env != {
                "CODE_SHA": REPAIR6_CODE_SHA,
                "ANALYSIS_IMAGE": REPAIR6_IMAGE,
            } or container.get("resources", {}).get("limits") != {
                "cpu": "8", "memory": "32Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "43200" or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise ValueError("ATLAS proof execution contract differs")
    state = completed_state(value)
    if state != expected_state:
        raise ValueError("ATLAS proof execution terminal state differs")
    return {
        "job": job,
        "execution": execution,
        "season": int(season),
        "week": int(week),
        "uri": uri,
        "state": state,
    }


def classify_failed_legacy_proof(
    value: Mapping[str, Any],
    *,
    command: str,
    error_text: str,
    legacy_proof_inventory: Sequence[str],
) -> dict[str, Any]:
    """Classify only the exact pre-model legacy proof transport failure."""
    validate_execution_contract(
        value,
        job=FAILED_PROOF_JOB,
        execution=FAILED_PROOF_EXECUTION,
        season="2023",
        week="1",
        uri=FAILED_PROOF_URI,
        command=command,
        expected_state="False",
    )
    completed = [
        row for row in value["status"]["conditions"]
        if row.get("type") == "Completed"
    ]
    condition = completed[0]
    if condition.get("reason") != "NonZeroExitCode" or \
            "exit code: 1" not in str(condition.get("message", "")).lower():
        raise ValueError("ATLAS legacy proof terminal reason differs")
    if list(legacy_proof_inventory):
        raise ValueError("ATLAS legacy proof prefix is not empty")
    if error_text.count(EXPECTED_FAILURE) != 1 or \
            not error_text.rstrip().endswith(EXPECTED_FAILURE) or \
            any(marker in error_text for marker in FORBIDDEN_PROGRESS_MARKERS):
        raise ValueError("ATLAS legacy proof failure class differs")
    return {
        "version": "atlas-repair6-proof-transport-classification-v1",
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": PROTOCOL_SHA256,
        "failed_job": FAILED_PROOF_JOB,
        "failed_execution": FAILED_PROOF_EXECUTION,
        "failed_uri": FAILED_PROOF_URI,
        "failure_log_sha256": sha256(error_text.encode()).hexdigest(),
        "legacy_proof_objects": 0,
        "failed_before_scientific_work": True,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "production_change_licensed": False,
        "disposition": "exact-pre-model-proof-prefix-transport-failure",
    }


def validate_object_metadata(value: Mapping[str, Any], *, uri: str) -> dict[str, Any]:
    """Validate safe object metadata without opening its body."""
    generation = str(value.get("generation", ""))
    digest = str(value.get("sha256", ""))
    size = int(value.get("bytes") or 0)
    if value.get("uri") != uri or not generation.isdigit() or \
            int(generation) <= 0 or size <= 0 or \
            not _SHA256_RE.fullmatch(digest):
        raise ValueError("ATLAS proof object metadata differs")
    return {
        "uri": uri,
        "generation": generation,
        "bytes": size,
        "sha256": digest,
    }


__all__ = [
    "EXPECTED_FAILURE",
    "FORBIDDEN_PROGRESS_MARKERS",
    "FAILED_PROOF_EXECUTION",
    "FAILED_PROOF_JOB",
    "FAILED_PROOF_URI",
    "LEGACY_PROOF_PREFIX",
    "PROTOCOL_ID",
    "PROTOCOL_SHA256",
    "REPAIR5_CODE_SHA",
    "REPAIR5_IMAGE",
    "REPAIR6_CODE_SHA",
    "REPAIR6_IMAGE",
    "REPAIR6_PREFIX",
    "REPLACEMENT_PROOF_JOB",
    "REPLACEMENT_PROOF_PREFIX",
    "REPLACEMENT_PROOF_URI",
    "TARGET_EXECUTION",
    "TARGET_JOB",
    "TARGET_URI",
    "canonical_provenance_prefix",
    "classify_failed_legacy_proof",
    "compare_opaque_provenance_normalized",
    "completed_state",
    "opaque_suffix",
    "validate_execution_contract",
    "validate_object_metadata",
]
