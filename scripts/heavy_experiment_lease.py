#!/usr/bin/env python3
"""Fail-closed GCS lease for all heavyweight research experiments.

The active object is intentionally permanent until either:

* a generation-pinned immutable terminal-completion receipt licenses normal
  release; or
* an operator supplies a generation/hash-bound audit and an explicit recovery
  authorization.

There is no age-based expiry, stale-lock heuristic, signal handler, or local
process-liveness shortcut in this module.  Every deletion is preceded by a
durable create-only intent and uses the exact active-object generation.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import storage


PROJECT = "nfl-predictions-503414"
LEASE_URI = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    "heavy-experiment-active-v1.json"
)
LEASE_VERSION = "heavy-experiment-active-v1"
ACQUISITION_RECEIPT_VERSION = "heavy-experiment-acquisition-receipt-v1"
AUDIT_VERSION = "heavy-experiment-audit-v1"
COMPLETION_VERSION = "heavy-experiment-terminal-completion-v1"
COMPLETION_REFERENCE_VERSION = (
    "heavy-experiment-terminal-completion-reference-v1"
)
REGISTERED_POPULATION_VERSION = "heavy-experiment-registered-population-v1"
TERMINAL_EXECUTION_VERSION = "heavy-experiment-terminal-execution-v1"
TERMINAL_CENSUS_VERSION = "heavy-experiment-terminal-census-v1"
STRICT_HARVEST_VERSION = "heavy-experiment-strict-harvest-v1"
RELEASE_INTENT_VERSION = "heavy-experiment-release-intent-v1"
RELEASE_COMPLETION_VERSION = "heavy-experiment-release-completion-v1"
RECOVERY_AUTH_VERSION = "heavy-experiment-recovery-authorization-v1"
RECOVERY_INTENT_VERSION = "heavy-experiment-recovery-intent-v1"
RECOVERY_COMPLETION_VERSION = "heavy-experiment-recovery-completion-v1"

_GOVERNANCE_ROOT = (
    "gs://nfl-predictions-503414-raw/research-governance"
)
_RUN_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{2,80}")
_JOB_FAMILY_RE = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE_SHA_RE = re.compile(r"[0-9a-f]{40}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_IMAGE_RE = re.compile(r"[^\s]+@sha256:[0-9a-f]{64}")


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode_json(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return value


def _read_json(path: Path, *, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"cannot read {label}") from exc
    return _decode_json(raw, label=label), raw


def _write_create_only(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError as exc:
        raise RuntimeError(f"refusing to replace local receipt: {path}") from exc


def _parse_gcs(uri: str) -> tuple[str, str]:
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if match is None or "//" in match.group(2):
        raise RuntimeError("heavy-experiment GCS URI is invalid")
    return match.group(1), match.group(2)


def _utc_timestamp(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError(f"{label} must include a timezone")
    return value


def _now_iso(now: Callable[[], datetime] | None = None) -> str:
    value = (now or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError("lease clock must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _positive_int(value: Any, *, label: str, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"{label} must be an integer")
    if value < (0 if allow_zero else 1):
        raise RuntimeError(f"{label} is out of range")
    return value


def _validate_identity(
    *, run_id: Any, job_family: Any, code_sha: Any, image: Any,
    protocol_sha256: Any,
) -> None:
    if not isinstance(run_id, str) or _RUN_ID_RE.fullmatch(run_id) is None:
        raise RuntimeError("heavy-experiment run ID differs")
    if (
        not isinstance(job_family, str)
        or _JOB_FAMILY_RE.fullmatch(job_family) is None
    ):
        raise RuntimeError("heavy-experiment job family differs")
    if not isinstance(code_sha, str) or _CODE_SHA_RE.fullmatch(code_sha) is None:
        raise RuntimeError("heavy-experiment code SHA differs")
    if not isinstance(image, str) or _IMAGE_RE.fullmatch(image) is None:
        raise RuntimeError("heavy-experiment immutable image differs")
    if (
        not isinstance(protocol_sha256, str)
        or _SHA256_RE.fullmatch(protocol_sha256) is None
    ):
        raise RuntimeError("heavy-experiment protocol SHA differs")


def _validate_lease_payload(payload: Mapping[str, Any]) -> None:
    required = {
        "version", "run_id", "job_family", "code_sha", "image",
        "protocol_sha256", "acquired_at",
    }
    if set(payload) != required or payload.get("version") != LEASE_VERSION:
        raise RuntimeError("heavy-experiment active lease schema differs")
    _validate_identity(
        run_id=payload.get("run_id"),
        job_family=payload.get("job_family"),
        code_sha=payload.get("code_sha"),
        image=payload.get("image"),
        protocol_sha256=payload.get("protocol_sha256"),
    )
    _utc_timestamp(payload.get("acquired_at"), label="lease acquired_at")


def _object_metadata(blob: Any, *, uri: str, raw: bytes,
                     create_only: bool) -> dict[str, Any]:
    generation = str(getattr(blob, "generation", ""))
    if not generation.isdigit():
        raise RuntimeError("GCS object generation is missing")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "md5_hash": str(getattr(blob, "md5_hash", "") or ""),
        "crc32c": str(getattr(blob, "crc32c", "") or ""),
        "create_only": create_only,
    }


def _validate_object_reference(
    value: Any, *, expected_uri: str | None = None,
) -> dict[str, Any]:
    required = {
        "uri", "generation", "sha256", "bytes", "md5_hash", "crc32c",
        "create_only",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise RuntimeError("heavy-experiment object receipt schema differs")
    uri = value.get("uri")
    if not isinstance(uri, str):
        raise RuntimeError("heavy-experiment object URI differs")
    _parse_gcs(uri)
    if expected_uri is not None and uri != expected_uri:
        raise RuntimeError("heavy-experiment object URI differs")
    if not str(value.get("generation", "")).isdigit():
        raise RuntimeError("heavy-experiment object generation differs")
    if _SHA256_RE.fullmatch(str(value.get("sha256", ""))) is None:
        raise RuntimeError("heavy-experiment object SHA-256 differs")
    _positive_int(value.get("bytes"), label="object bytes")
    if not isinstance(value.get("md5_hash"), str) or not isinstance(
        value.get("crc32c"), str,
    ):
        raise RuntimeError("heavy-experiment object checksums differ")
    if value.get("create_only") is not True:
        raise RuntimeError("heavy-experiment object was not create-only")
    return value


def _client_or_default(client: Any | None) -> Any:
    return client if client is not None else storage.Client(project=PROJECT)


def _download_exact(
    client: Any, reference: Mapping[str, Any], *, label: str,
) -> tuple[bytes, dict[str, Any]]:
    expected = _validate_object_reference(reference)
    bucket_name, object_name = _parse_gcs(str(expected["uri"]))
    generation = int(str(expected["generation"]))
    blob = client.bucket(bucket_name).blob(object_name, generation=generation)
    raw = blob.download_as_bytes(if_generation_match=generation)
    blob.reload(if_generation_match=generation)
    actual = _object_metadata(
        blob, uri=str(expected["uri"]), raw=raw, create_only=True,
    )
    for key in ("generation", "sha256", "bytes", "md5_hash", "crc32c"):
        if actual[key] != expected[key]:
            raise RuntimeError(f"{label} exact object {key} differs")
    return raw, actual


def _download_current(client: Any) -> tuple[bytes, dict[str, Any]]:
    bucket_name, object_name = _parse_gcs(LEASE_URI)
    observed_generation = False
    absent_observations = 0
    for _attempt in range(3):
        blob = client.bucket(bucket_name).blob(object_name)
        try:
            blob.reload()
        except NotFound:
            absent_observations += 1
            continue
        observed_generation = True
        generation = int(str(blob.generation))
        pinned = client.bucket(bucket_name).blob(
            object_name, generation=generation,
        )
        try:
            raw = pinned.download_as_bytes(if_generation_match=generation)
            pinned.reload(if_generation_match=generation)
        except (NotFound, PreconditionFailed):
            # The current object changed between discovery and the pinned read.
            # Retry the snapshot; never translate this race directly to absent.
            continue
        return raw, _object_metadata(
            pinned, uri=LEASE_URI, raw=raw, create_only=True,
        )
    if not observed_generation and absent_observations == 3:
        raise NotFound("heavy-experiment active lease is absent")
    raise RuntimeError("heavy-experiment active lease snapshot is indeterminate")


def _upload_create_only(
    client: Any, uri: str, raw: bytes,
) -> dict[str, Any]:
    bucket_name, object_name = _parse_gcs(uri)
    blob = client.bucket(bucket_name).blob(object_name)
    blob.upload_from_string(
        raw, content_type="application/json", if_generation_match=0,
    )
    blob.reload()
    reference = _object_metadata(blob, uri=uri, raw=raw, create_only=True)
    _download_exact(client, reference, label="newly created")
    return reference


def _load_acquisition_receipt(
    receipt_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    receipt, _raw = _read_json(
        receipt_path, label="heavy-experiment acquisition receipt",
    )
    if set(receipt) != {"version", "lease", "object"} or receipt.get(
        "version",
    ) != ACQUISITION_RECEIPT_VERSION:
        raise RuntimeError("heavy-experiment acquisition receipt differs")
    lease = receipt.get("lease")
    if not isinstance(lease, dict):
        raise RuntimeError("heavy-experiment acquisition lease differs")
    _validate_lease_payload(lease)
    object_reference = _validate_object_reference(
        receipt.get("object"), expected_uri=LEASE_URI,
    )
    if sha256(_canonical_json(lease)).hexdigest() != object_reference["sha256"]:
        raise RuntimeError("heavy-experiment acquisition content hash differs")
    if len(_canonical_json(lease)) != object_reference["bytes"]:
        raise RuntimeError("heavy-experiment acquisition content size differs")
    return receipt, lease, object_reference


def acquire(
    *, run_id: str, job_family: str, code_sha: str, image: str,
    protocol_sha256: str, receipt_path: Path, client: Any | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Atomically acquire the shared lease and persist its local receipt."""
    _validate_identity(
        run_id=run_id, job_family=job_family, code_sha=code_sha, image=image,
        protocol_sha256=protocol_sha256,
    )
    if receipt_path.exists():
        raise RuntimeError("heavy-experiment acquisition receipt already exists")
    payload = {
        "version": LEASE_VERSION,
        "run_id": run_id,
        "job_family": job_family,
        "code_sha": code_sha,
        "image": image,
        "protocol_sha256": protocol_sha256,
        "acquired_at": _now_iso(now),
    }
    raw = _canonical_json(payload)
    gcs = _client_or_default(client)
    try:
        uploaded = _upload_create_only(gcs, LEASE_URI, raw)
    except PreconditionFailed as exc:
        raise RuntimeError(
            "heavy-experiment lease is occupied; audit or explicit operator "
            "recovery is required (leases never expire automatically)",
        ) from exc
    receipt = {
        "version": ACQUISITION_RECEIPT_VERSION,
        "lease": payload,
        "object": uploaded,
    }
    _write_create_only(receipt_path, _canonical_json(receipt))
    return receipt


def audit(
    *, receipt_path: Path | None = None, output_path: Path | None = None,
    client: Any | None = None, now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Inspect the lease without interpreting age and without deleting it."""
    if output_path is not None and output_path.exists():
        raise RuntimeError("heavy-experiment audit output already exists")
    expected: dict[str, Any] | None = None
    if receipt_path is not None:
        _receipt, _lease, expected = _load_acquisition_receipt(receipt_path)
    gcs = _client_or_default(client)
    try:
        raw, object_reference = _download_current(gcs)
    except NotFound:
        report: dict[str, Any] = {
            "version": AUDIT_VERSION,
            "lease_uri": LEASE_URI,
            "audited_at": _now_iso(now),
            "status": "absent",
            "object": None,
            "lease": None,
            "validation_errors": [],
            "expected_receipt_match": expected is None,
            "age_evaluated": False,
            "automatic_expiry_permitted": False,
            "delete_attempted": False,
        }
    except RuntimeError as exc:
        report = {
            "version": AUDIT_VERSION,
            "lease_uri": LEASE_URI,
            "audited_at": _now_iso(now),
            "status": "indeterminate",
            "object": None,
            "lease": None,
            "validation_errors": [str(exc)],
            "expected_receipt_match": None,
            "age_evaluated": False,
            "automatic_expiry_permitted": False,
            "delete_attempted": False,
        }
    else:
        errors: list[str] = []
        lease: dict[str, Any] | None
        try:
            lease = _decode_json(raw, label="active heavy-experiment lease")
            _validate_lease_payload(lease)
        except RuntimeError as exc:
            lease = None
            errors.append(str(exc))
        expected_match = None if expected is None else all(
            object_reference[key] == expected[key]
            for key in ("uri", "generation", "sha256", "bytes")
        )
        if expected_match is False:
            errors.append("active object differs from supplied acquisition receipt")
        report = {
            "version": AUDIT_VERSION,
            "lease_uri": LEASE_URI,
            "audited_at": _now_iso(now),
            "status": "occupied-valid" if lease is not None else "occupied-invalid",
            "object": object_reference,
            "lease": lease,
            "validation_errors": errors,
            "expected_receipt_match": expected_match,
            "age_evaluated": False,
            "automatic_expiry_permitted": False,
            "delete_attempted": False,
        }
    if output_path is not None:
        _write_create_only(output_path, _canonical_json(report))
    return report


def _load_completion_reference(
    path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    value, _raw = _read_json(path, label="terminal completion reference")
    if set(value) != {"version", "object"} or value.get(
        "version",
    ) != COMPLETION_REFERENCE_VERSION:
        raise RuntimeError("terminal completion reference differs")
    return value, _validate_object_reference(value.get("object"))


def _object_binding(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "uri": value["uri"],
        "generation": value["generation"],
        "sha256": value["sha256"],
    }


def _validate_evidence_identity(
    value: Mapping[str, Any], *, lease: Mapping[str, Any], label: str,
) -> None:
    for key in ("run_id", "job_family", "code_sha", "image", "protocol_sha256"):
        if value.get(key) != lease.get(key):
            raise RuntimeError(f"{label} {key} differs from lease")


def _terminal_count(value: Any, *, label: str) -> int:
    if value is None:
        return 0
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    return _positive_int(value, label=label, allow_zero=True)


def _validate_terminal_execution_receipt(
    value: Mapping[str, Any], *, lease: Mapping[str, Any],
    lease_binding: Mapping[str, Any], job: str, execution: str,
    expected_state: str, expected_completion_time: str,
) -> None:
    required = {
        "version", "run_id", "job_family", "code_sha", "image",
        "protocol_sha256", "lease", "job", "execution", "terminal_state",
        "completion_time", "cloud_run_execution",
    }
    if not required <= set(value) or value.get(
        "version",
    ) != TERMINAL_EXECUTION_VERSION:
        raise RuntimeError("terminal execution receipt schema differs")
    _validate_evidence_identity(
        value, lease=lease, label="terminal execution receipt",
    )
    if (
        value.get("lease") != lease_binding
        or value.get("job") != job
        or value.get("execution") != execution
        or value.get("terminal_state") != expected_state
        or value.get("completion_time") != expected_completion_time
    ):
        raise RuntimeError("terminal execution receipt identity differs")
    _utc_timestamp(
        value.get("completion_time"), label="execution receipt completion_time",
    )
    metadata = value.get("cloud_run_execution")
    identity = metadata.get("metadata") if isinstance(metadata, dict) else None
    if not isinstance(identity, dict) or identity.get("name") != execution:
        raise RuntimeError("terminal Cloud Run execution identity differs")
    status = metadata.get("status")
    if not isinstance(status, dict):
        raise RuntimeError("terminal Cloud Run execution status differs")
    conditions = status.get("conditions")
    if not isinstance(conditions, list):
        raise RuntimeError("terminal Cloud Run execution conditions differ")
    completed = [
        row for row in status.get("conditions", [])
        if isinstance(row, dict) and row.get("type") == "Completed"
    ]
    if len(completed) != 1 or completed[0].get("status") == "Unknown" or not status.get(
        "completionTime",
    ):
        raise RuntimeError("Cloud Run execution is not terminal")
    if status.get("completionTime") != expected_completion_time:
        raise RuntimeError("Cloud Run execution completion time differs")
    succeeded = _terminal_count(
        status.get("succeededCount"), label="Cloud Run succeededCount",
    )
    failed = _terminal_count(
        status.get("failedCount"), label="Cloud Run failedCount",
    )
    cancelled = _terminal_count(
        status.get("cancelledCount"), label="Cloud Run cancelledCount",
    )
    condition_status = completed[0].get("status")
    reason = str(completed[0].get("reason", ""))
    if expected_state == "succeeded":
        valid_state = (
            condition_status == "True" and succeeded > 0
            and failed == 0 and cancelled == 0
        )
    elif expected_state == "failed":
        valid_state = condition_status == "False" and failed > 0
    else:
        valid_state = (
            condition_status == "False"
            and (cancelled > 0 or "cancel" in reason.lower())
        )
    if not valid_state:
        raise RuntimeError("Cloud Run terminal state differs from census")
    spec = metadata.get("spec")
    task_count_raw = spec.get("taskCount") if isinstance(spec, dict) else None
    if task_count_raw is not None:
        task_count = _terminal_count(
            task_count_raw, label="Cloud Run taskCount",
        )
        if task_count < 1 or succeeded + failed + cancelled != task_count:
            raise RuntimeError("Cloud Run terminal task counts differ")


def _load_terminal_evidence(
    client: Any, completion: Mapping[str, Any], *, lease: Mapping[str, Any],
    lease_object: Mapping[str, Any],
) -> dict[str, Any]:
    """Retrieve and independently reconcile all immutable terminal evidence."""
    refs: dict[str, dict[str, Any]] = {}
    payloads: dict[str, dict[str, Any]] = {}
    for key, label in (
        ("registered_population_object", "registered population"),
        ("terminal_census_object", "terminal census"),
        ("strict_harvest_object", "strict harvest"),
    ):
        reference = _validate_object_reference(completion.get(key))
        raw, _metadata = _download_exact(client, reference, label=label)
        refs[key] = reference
        payloads[key] = _decode_json(raw, label=label)

    lease_binding = {
        "uri": LEASE_URI,
        "generation": lease_object["generation"],
        "sha256": lease_object["sha256"],
    }
    population = payloads["registered_population_object"]
    population_required = {
        "version", "run_id", "job_family", "code_sha", "image",
        "protocol_sha256", "lease", "expected_executions", "executions",
        "registered_at",
    }
    if not population_required <= set(population) or population.get(
        "version",
    ) != REGISTERED_POPULATION_VERSION:
        raise RuntimeError("registered population schema differs")
    _validate_evidence_identity(
        population, lease=lease, label="registered population",
    )
    if population.get("lease") != lease_binding:
        raise RuntimeError("registered population lease binding differs")
    expected = _positive_int(
        population.get("expected_executions"),
        label="registered expected executions",
    )
    population_rows = population.get("executions")
    if not isinstance(population_rows, list) or len(population_rows) != expected:
        raise RuntimeError("registered population executions differ")
    identities: list[tuple[str, str]] = []
    for row in population_rows:
        if not isinstance(row, dict) or set(row) != {"job", "execution"}:
            raise RuntimeError("registered execution identity schema differs")
        job = row.get("job")
        execution = row.get("execution")
        if (
            not isinstance(job, str)
            or _JOB_FAMILY_RE.fullmatch(job) is None
            or not isinstance(execution, str)
            or re.fullmatch(r"[a-z0-9][a-z0-9-]{2,126}", execution) is None
            or not execution.startswith(job + "-")
        ):
            raise RuntimeError("registered execution identity differs")
        identities.append((job, execution))
    if len(set(identities)) != len(identities):
        raise RuntimeError("registered population contains duplicate executions")
    _utc_timestamp(population.get("registered_at"), label="population registered_at")

    census = payloads["terminal_census_object"]
    census_required = {
        "version", "run_id", "job_family", "code_sha", "image",
        "protocol_sha256", "lease", "registered_population_object",
        "executions", "execution_receipts_sha256", "censused_at",
    }
    if not census_required <= set(census) or census.get(
        "version",
    ) != TERMINAL_CENSUS_VERSION:
        raise RuntimeError("terminal census schema differs")
    _validate_evidence_identity(census, lease=lease, label="terminal census")
    if census.get("lease") != lease_binding or census.get(
        "registered_population_object",
    ) != _object_binding(refs["registered_population_object"]):
        raise RuntimeError("terminal census source binding differs")
    census_rows = census.get("executions")
    if not isinstance(census_rows, list) or len(census_rows) != expected:
        raise RuntimeError("terminal census executions differ")
    derived_counts = {"succeeded": 0, "failed": 0, "cancelled": 0}
    receipt_rows: list[dict[str, Any]] = []
    for identity, row in zip(identities, census_rows, strict=True):
        if not isinstance(row, dict) or set(row) != {
            "job", "execution", "terminal_state", "completion_time",
            "execution_receipt_object",
        }:
            raise RuntimeError("terminal census execution schema differs")
        if (row.get("job"), row.get("execution")) != identity:
            raise RuntimeError("terminal census population identity differs")
        state = row.get("terminal_state")
        if state not in derived_counts:
            raise RuntimeError("terminal census contains a nonterminal state")
        _utc_timestamp(
            row.get("completion_time"), label="execution completion_time",
        )
        execution_reference = _validate_object_reference(
            row.get("execution_receipt_object"),
        )
        execution_raw, _execution_metadata = _download_exact(
            client, execution_reference, label="terminal execution receipt",
        )
        execution_receipt = _decode_json(
            execution_raw, label="terminal execution receipt",
        )
        _validate_terminal_execution_receipt(
            execution_receipt, lease=lease, lease_binding=lease_binding,
            job=identity[0], execution=identity[1], expected_state=str(state),
            expected_completion_time=str(row.get("completion_time")),
        )
        derived_counts[str(state)] += 1
        receipt_rows.append({
            "job": identity[0], "execution": identity[1],
            "object": execution_reference,
        })
    derived_receipt_sha = sha256(_canonical_json({
        "execution_receipts": receipt_rows,
    })).hexdigest()
    if census.get("execution_receipts_sha256") != derived_receipt_sha:
        raise RuntimeError("terminal census receipt aggregate differs")
    _utc_timestamp(census.get("censused_at"), label="census censused_at")

    harvest = payloads["strict_harvest_object"]
    harvest_required = {
        "version", "run_id", "job_family", "code_sha", "image",
        "protocol_sha256", "lease", "registered_population_object",
        "terminal_census_object", "release_class", "full_population_terminal",
        "strict_harvest_complete", "disposition", "artifact_receipts_sha256",
        "uses_realized_outcomes", "harvested_at",
    }
    if not harvest_required <= set(harvest) or harvest.get(
        "version",
    ) != STRICT_HARVEST_VERSION:
        raise RuntimeError("strict harvest schema differs")
    _validate_evidence_identity(harvest, lease=lease, label="strict harvest")
    if (
        harvest.get("lease") != lease_binding
        or harvest.get("registered_population_object")
        != _object_binding(refs["registered_population_object"])
        or harvest.get("terminal_census_object")
        != _object_binding(refs["terminal_census_object"])
    ):
        raise RuntimeError("strict harvest source binding differs")
    if harvest.get("full_population_terminal") is not True or harvest.get(
        "strict_harvest_complete",
    ) is not True:
        raise RuntimeError("strict harvest is not complete")
    if (
        not isinstance(harvest.get("disposition"), str)
        or not harvest["disposition"].strip()
        or _SHA256_RE.fullmatch(
            str(harvest.get("artifact_receipts_sha256", "")),
        ) is None
        or not isinstance(harvest.get("uses_realized_outcomes"), bool)
    ):
        raise RuntimeError("strict harvest disposition/evidence differs")
    if harvest.get("release_class") == "terminal-fail-closed":
        reason = harvest.get("fail_closed_reason")
        if not isinstance(reason, str) or not reason.strip():
            raise RuntimeError("strict fail-closed harvest lacks a reason")
    _utc_timestamp(harvest.get("harvested_at"), label="harvest harvested_at")
    return {
        "references": refs,
        "expected_executions": expected,
        "succeeded_executions": derived_counts["succeeded"],
        "failed_executions": derived_counts["failed"],
        "cancelled_executions": derived_counts["cancelled"],
        "execution_receipts_sha256": derived_receipt_sha,
        "harvest": harvest,
    }


def _validate_completion(
    value: Mapping[str, Any], *, lease: Mapping[str, Any],
    lease_object: Mapping[str, Any], evidence: Mapping[str, Any],
) -> None:
    required = {
        "version", "run_id", "job_family", "code_sha", "image",
        "protocol_sha256", "lease", "release_class",
        "full_population_terminal", "strict_harvest_complete",
        "expected_executions", "terminal_executions",
        "succeeded_executions", "failed_executions",
        "cancelled_executions", "nonterminal_executions",
        "terminal_execution_receipts_sha256", "strict_harvest_sha256",
        "uses_realized_outcomes", "completed_at",
        "registered_population_object", "terminal_census_object",
        "strict_harvest_object",
    }
    missing = sorted(required - set(value))
    if missing or value.get("version") != COMPLETION_VERSION:
        raise RuntimeError(
            "heavy-experiment terminal completion schema differs: "
            + ",".join(missing),
        )
    _validate_identity(
        run_id=value.get("run_id"), job_family=value.get("job_family"),
        code_sha=value.get("code_sha"), image=value.get("image"),
        protocol_sha256=value.get("protocol_sha256"),
    )
    for key in ("run_id", "job_family", "code_sha", "image", "protocol_sha256"):
        if value.get(key) != lease.get(key):
            raise RuntimeError(f"terminal completion {key} differs from lease")
    binding = value.get("lease")
    expected_binding = {
        "uri": LEASE_URI,
        "generation": lease_object["generation"],
        "sha256": lease_object["sha256"],
    }
    if binding != expected_binding:
        raise RuntimeError("terminal completion lease binding differs")
    if value.get("full_population_terminal") is not True or value.get(
        "strict_harvest_complete",
    ) is not True:
        raise RuntimeError("terminal completion is not strict/full-population")
    expected = _positive_int(
        value.get("expected_executions"), label="expected executions",
    )
    terminal = _positive_int(
        value.get("terminal_executions"), label="terminal executions",
    )
    succeeded = _positive_int(
        value.get("succeeded_executions"), label="succeeded executions",
        allow_zero=True,
    )
    failed = _positive_int(
        value.get("failed_executions"), label="failed executions",
        allow_zero=True,
    )
    cancelled = _positive_int(
        value.get("cancelled_executions"), label="cancelled executions",
        allow_zero=True,
    )
    nonterminal = _positive_int(
        value.get("nonterminal_executions"), label="nonterminal executions",
        allow_zero=True,
    )
    if (
        terminal != expected
        or nonterminal != 0
        or succeeded + failed + cancelled != expected
    ):
        raise RuntimeError("terminal completion population counts differ")
    if (
        expected != evidence["expected_executions"]
        or succeeded != evidence["succeeded_executions"]
        or failed != evidence["failed_executions"]
        or cancelled != evidence["cancelled_executions"]
    ):
        raise RuntimeError("terminal completion differs from immutable census")
    release_class = value.get("release_class")
    if release_class == "terminal-success":
        if succeeded != expected or failed != 0 or cancelled != 0:
            raise RuntimeError("terminal-success completion counts differ")
    elif release_class == "terminal-fail-closed":
        reason = value.get("fail_closed_reason")
        if not isinstance(reason, str) or not reason.strip():
            raise RuntimeError("fail-closed completion lacks a reason")
    else:
        raise RuntimeError("terminal completion release class differs")
    for key in ("terminal_execution_receipts_sha256", "strict_harvest_sha256"):
        if _SHA256_RE.fullmatch(str(value.get(key, ""))) is None:
            raise RuntimeError(f"terminal completion {key} differs")
    references = evidence["references"]
    for key in (
        "registered_population_object", "terminal_census_object",
        "strict_harvest_object",
    ):
        if value.get(key) != references[key]:
            raise RuntimeError(f"terminal completion {key} differs")
    if value.get("terminal_execution_receipts_sha256") != evidence.get(
        "execution_receipts_sha256",
    ) or value.get("strict_harvest_sha256") != references[
        "strict_harvest_object"
    ]["sha256"]:
        raise RuntimeError("terminal completion evidence hashes differ")
    harvest = evidence["harvest"]
    if (
        release_class != harvest.get("release_class")
        or value.get("uses_realized_outcomes")
        != harvest.get("uses_realized_outcomes")
    ):
        raise RuntimeError("terminal completion differs from strict harvest")
    if not isinstance(value.get("uses_realized_outcomes"), bool):
        raise RuntimeError("terminal completion outcome scope differs")
    _utc_timestamp(value.get("completed_at"), label="completion completed_at")


def _record_uri(kind: str, generation: str, content_sha256: str) -> str:
    if kind not in {
        "release-intents-v1", "release-completions-v1",
        "recovery-intents-v1", "recovery-completions-v1",
    }:
        raise RuntimeError("heavy-experiment record kind differs")
    return (
        f"{_GOVERNANCE_ROOT}/heavy-experiment-{kind}/"
        f"generation-{generation}-{content_sha256[:16]}.json"
    )


def _ensure_record(
    client: Any, *, uri: str, expected: Mapping[str, Any],
    now: Callable[[], datetime] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = dict(expected)
    payload["recorded_at"] = _now_iso(now)
    raw = _canonical_json(payload)
    try:
        reference = _upload_create_only(client, uri, raw)
        return payload, reference
    except PreconditionFailed:
        bucket_name, object_name = _parse_gcs(uri)
        blob = client.bucket(bucket_name).blob(object_name)
        blob.reload()
        generation = int(str(blob.generation))
        pinned = client.bucket(bucket_name).blob(object_name, generation=generation)
        existing_raw = pinned.download_as_bytes(if_generation_match=generation)
        pinned.reload(if_generation_match=generation)
        existing = _decode_json(existing_raw, label="durable lease record")
        for key, value in expected.items():
            if existing.get(key) != value:
                raise RuntimeError("existing durable lease record differs")
        if set(existing) != set(expected) | {"recorded_at"}:
            raise RuntimeError("existing durable lease record schema differs")
        _utc_timestamp(existing.get("recorded_at"), label="record recorded_at")
        return existing, _object_metadata(
            pinned, uri=uri, raw=existing_raw, create_only=True,
        )


def _load_existing_record(
    client: Any, *, uri: str, expected: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Require a pre-existing durable record and verify all bound content."""
    bucket_name, object_name = _parse_gcs(uri)
    blob = client.bucket(bucket_name).blob(object_name)
    blob.reload()
    generation = int(str(blob.generation))
    pinned = client.bucket(bucket_name).blob(object_name, generation=generation)
    raw = pinned.download_as_bytes(if_generation_match=generation)
    pinned.reload(if_generation_match=generation)
    existing = _decode_json(raw, label="durable lease record")
    for key, value in expected.items():
        if existing.get(key) != value:
            raise RuntimeError("existing durable lease record differs")
    if set(existing) != set(expected) | {"recorded_at"}:
        raise RuntimeError("existing durable lease record schema differs")
    _utc_timestamp(existing.get("recorded_at"), label="record recorded_at")
    return existing, _object_metadata(
        pinned, uri=uri, raw=raw, create_only=True,
    )


def _ensure_raw_record(
    client: Any, *, kind: str, raw: bytes,
) -> dict[str, Any]:
    if kind not in {"audit", "authorization"}:
        raise RuntimeError("recovery input kind differs")
    digest = sha256(raw).hexdigest()
    uri = (
        f"{_GOVERNANCE_ROOT}/heavy-experiment-recovery-inputs-v1/"
        f"{kind}-{digest}.json"
    )
    try:
        return _upload_create_only(client, uri, raw)
    except PreconditionFailed:
        bucket_name, object_name = _parse_gcs(uri)
        blob = client.bucket(bucket_name).blob(object_name)
        blob.reload()
        generation = int(str(blob.generation))
        pinned = client.bucket(bucket_name).blob(object_name, generation=generation)
        existing = pinned.download_as_bytes(if_generation_match=generation)
        pinned.reload(if_generation_match=generation)
        if existing != raw or sha256(existing).hexdigest() != digest:
            raise RuntimeError("existing durable recovery input differs")
        return _object_metadata(
            pinned, uri=uri, raw=existing, create_only=True,
        )


def _delete_exact(client: Any, object_reference: Mapping[str, Any]) -> None:
    bucket_name, object_name = _parse_gcs(LEASE_URI)
    generation = int(str(object_reference["generation"]))
    blob = client.bucket(bucket_name).blob(object_name, generation=generation)
    blob.delete(if_generation_match=generation)


def _active_exact_present(
    client: Any, object_reference: Mapping[str, Any], *, label: str,
) -> bool:
    try:
        _download_exact(client, object_reference, label=label)
    except NotFound:
        return False
    return True


def _require_current_matches(
    client: Any, object_reference: Mapping[str, Any],
) -> None:
    raw, current = _download_current(client)
    for key in ("uri", "generation", "sha256", "bytes", "md5_hash", "crc32c"):
        if current[key] != object_reference[key]:
            raise RuntimeError(
                "heavy-experiment release target is not the current active lease",
            )
    if sha256(raw).hexdigest() != object_reference["sha256"]:
        raise RuntimeError("current active lease content hash differs")


def _current_state_after_target_release(
    client: Any, object_reference: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        _raw, current = _download_current(client)
    except NotFound:
        return {"status": "globally-absent", "successor_object": None}
    if current["generation"] == object_reference["generation"]:
        raise RuntimeError("released lease generation is still active")
    return {"status": "successor-active", "successor_object": current}


def release(
    *, receipt_path: Path, completion_reference_path: Path,
    release_receipt_path: Path, client: Any | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Release only from a durable, strict, terminal-population receipt."""
    if release_receipt_path.exists():
        raise RuntimeError("heavy-experiment release receipt already exists")
    _receipt, lease, lease_object = _load_acquisition_receipt(receipt_path)
    _reference, completion_object = _load_completion_reference(
        completion_reference_path,
    )
    gcs = _client_or_default(client)
    completion_raw, _metadata = _download_exact(
        gcs, completion_object, label="terminal completion",
    )
    completion = _decode_json(
        completion_raw, label="terminal heavy-experiment completion",
    )
    evidence = _load_terminal_evidence(
        gcs, completion, lease=lease, lease_object=lease_object,
    )
    _validate_completion(
        completion, lease=lease, lease_object=lease_object,
        evidence=evidence,
    )

    target_key = (
        str(lease_object["generation"]), str(lease_object["sha256"]),
    )
    intent_uri = _record_uri("release-intents-v1", *target_key)
    intent_expected = {
        "version": RELEASE_INTENT_VERSION,
        "release_kind": "strict-terminal-completion",
        "lease": dict(lease),
        "lease_object": dict(lease_object),
        "completion_object": dict(completion_object),
        "completion_sha256": sha256(completion_raw).hexdigest(),
        "delete_requires_exact_generation": True,
        "automatic_expiry_used": False,
    }
    active_present = _active_exact_present(
        gcs, lease_object, label="active heavy-experiment lease",
    )
    if not active_present:
        # An interrupted prior release may have deleted the exact generation.
        # Only a pre-existing byte-compatible durable intent licenses resume.
        try:
            _intent, intent_reference = _load_existing_record(
                gcs, uri=intent_uri, expected=intent_expected,
            )
        except Exception as exc:
            raise RuntimeError(
                "active lease generation is absent without a verifiable "
                "durable release intent",
            ) from exc
    else:
        _require_current_matches(gcs, lease_object)
        _intent, intent_reference = _ensure_record(
            gcs, uri=intent_uri, expected=intent_expected, now=now,
        )
        _require_current_matches(gcs, lease_object)
        _delete_exact(gcs, lease_object)

    current_state = _current_state_after_target_release(gcs, lease_object)

    completion_record_uri = _record_uri(
        "release-completions-v1", *target_key,
    )
    completion_record_expected = {
        "version": RELEASE_COMPLETION_VERSION,
        "release_kind": "strict-terminal-completion",
        "lease_object": dict(lease_object),
        "completion_object": dict(completion_object),
        "release_intent_object": dict(intent_reference),
        "exact_generation_delete_completed": True,
        "automatic_expiry_used": False,
    }
    _completion_record, completion_record_reference = _ensure_record(
        gcs, uri=completion_record_uri, expected=completion_record_expected,
        now=now,
    )
    result = {
        "version": RELEASE_COMPLETION_VERSION,
        "lease": dict(lease),
        "lease_object": dict(lease_object),
        "terminal_completion_object": dict(completion_object),
        "release_intent_object": dict(intent_reference),
        "release_completion_object": dict(completion_record_reference),
        "exact_generation_delete_completed": True,
        "active_state_after_target_release": current_state,
    }
    _write_create_only(release_receipt_path, _canonical_json(result))
    return result


def _validate_audit_for_recovery(
    audit_value: Mapping[str, Any], *, audit_raw: bytes,
) -> tuple[dict[str, Any], str]:
    if audit_value.get("version") != AUDIT_VERSION or audit_value.get(
        "lease_uri",
    ) != LEASE_URI or audit_value.get("status") not in {
        "occupied-valid", "occupied-invalid",
    }:
        raise RuntimeError("operator recovery audit differs")
    if audit_value.get("delete_attempted") is not False or audit_value.get(
        "automatic_expiry_permitted",
    ) is not False or audit_value.get("age_evaluated") is not False:
        raise RuntimeError("operator recovery audit is not non-destructive")
    object_reference = _validate_object_reference(
        audit_value.get("object"), expected_uri=LEASE_URI,
    )
    return object_reference, sha256(audit_raw).hexdigest()


def _validate_recovery_authorization(
    value: Mapping[str, Any], *, audit_sha256: str,
    object_reference: Mapping[str, Any], confirm_generation: str,
    confirm_sha256: str, confirm_run_id: str,
) -> None:
    required = {
        "version", "lease_uri", "lease_generation", "lease_sha256",
        "audit_sha256", "run_id", "job_family", "operator", "reason",
        "authorized_at", "confirmed_run_abandoned",
        "confirmed_no_live_cloud_executions",
        "confirmed_no_live_local_launchers", "permit_exact_generation_delete",
        "evidence",
    }
    if set(value) != required or value.get("version") != RECOVERY_AUTH_VERSION:
        raise RuntimeError("operator recovery authorization schema differs")
    if (
        value.get("lease_uri") != LEASE_URI
        or str(value.get("lease_generation")) != object_reference["generation"]
        or value.get("lease_sha256") != object_reference["sha256"]
        or value.get("audit_sha256") != audit_sha256
        or confirm_generation != object_reference["generation"]
        or confirm_sha256 != object_reference["sha256"]
        or value.get("run_id") != confirm_run_id
    ):
        raise RuntimeError("operator recovery exact identity differs")
    if not isinstance(value.get("run_id"), str) or not value["run_id"].strip():
        raise RuntimeError("operator recovery run ID differs")
    if (
        not isinstance(value.get("job_family"), str)
        or not value["job_family"].strip()
        or not isinstance(value.get("operator"), str)
        or not value["operator"].strip()
        or not isinstance(value.get("reason"), str)
        or not value["reason"].strip()
    ):
        raise RuntimeError("operator recovery attribution differs")
    _utc_timestamp(value.get("authorized_at"), label="recovery authorized_at")
    for key in (
        "confirmed_run_abandoned", "confirmed_no_live_cloud_executions",
        "confirmed_no_live_local_launchers", "permit_exact_generation_delete",
    ):
        if value.get(key) is not True:
            raise RuntimeError(f"operator recovery confirmation {key} is absent")
    evidence = value.get("evidence")
    if (
        not isinstance(evidence, list)
        or not evidence
        or any(not isinstance(item, str) or not item.strip() for item in evidence)
    ):
        raise RuntimeError("operator recovery evidence is absent")


def recover(
    *, audit_path: Path, authorization_path: Path,
    recovery_receipt_path: Path, confirm_generation: str,
    confirm_sha256: str, confirm_run_id: str, client: Any | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Explicitly recover an abandoned exact lease; never infer abandonment."""
    if recovery_receipt_path.exists():
        raise RuntimeError("heavy-experiment recovery receipt already exists")
    audit_value, audit_raw = _read_json(
        audit_path, label="operator recovery audit",
    )
    object_reference, audit_sha = _validate_audit_for_recovery(
        audit_value, audit_raw=audit_raw,
    )
    authorization, authorization_raw = _read_json(
        authorization_path, label="operator recovery authorization",
    )
    _validate_recovery_authorization(
        authorization, audit_sha256=audit_sha,
        object_reference=object_reference,
        confirm_generation=confirm_generation,
        confirm_sha256=confirm_sha256,
        confirm_run_id=confirm_run_id,
    )
    lease = audit_value.get("lease")
    if isinstance(lease, dict):
        _validate_lease_payload(lease)
        if lease.get("run_id") != authorization.get("run_id") or lease.get(
            "job_family",
        ) != authorization.get("job_family"):
            raise RuntimeError("operator recovery lease identity differs")

    gcs = _client_or_default(client)
    audit_object = _ensure_raw_record(gcs, kind="audit", raw=audit_raw)
    authorization_object = _ensure_raw_record(
        gcs, kind="authorization", raw=authorization_raw,
    )
    target_key = (
        str(object_reference["generation"]), str(object_reference["sha256"]),
    )
    intent_uri = _record_uri("recovery-intents-v1", *target_key)
    intent_expected = {
        "version": RECOVERY_INTENT_VERSION,
        "recovery_kind": "explicit-operator-recovery",
        "lease_object": dict(object_reference),
        "audit_sha256": audit_sha,
        "authorization_sha256": sha256(authorization_raw).hexdigest(),
        "audit_object": audit_object,
        "authorization_object": authorization_object,
        "operator": authorization["operator"],
        "reason": authorization["reason"],
        "evidence": authorization["evidence"],
        "delete_requires_exact_generation": True,
        "automatic_expiry_used": False,
    }
    active_present = _active_exact_present(
        gcs, object_reference, label="operator-recovery active lease",
    )
    if not active_present:
        try:
            _intent, intent_reference = _load_existing_record(
                gcs, uri=intent_uri, expected=intent_expected,
            )
        except Exception as exc:
            raise RuntimeError(
                "recovery target is absent without a verifiable durable "
                "recovery intent",
            ) from exc
    else:
        _require_current_matches(gcs, object_reference)
        _intent, intent_reference = _ensure_record(
            gcs, uri=intent_uri, expected=intent_expected, now=now,
        )
        _require_current_matches(gcs, object_reference)
        _delete_exact(gcs, object_reference)

    current_state = _current_state_after_target_release(gcs, object_reference)

    completion_uri = _record_uri("recovery-completions-v1", *target_key)
    completion_expected = {
        "version": RECOVERY_COMPLETION_VERSION,
        "recovery_kind": "explicit-operator-recovery",
        "lease_object": dict(object_reference),
        "recovery_intent_object": dict(intent_reference),
        "authorization_sha256": sha256(authorization_raw).hexdigest(),
        "exact_generation_delete_completed": True,
        "automatic_expiry_used": False,
    }
    _completion, completion_reference = _ensure_record(
        gcs, uri=completion_uri, expected=completion_expected, now=now,
    )
    result = {
        "version": RECOVERY_COMPLETION_VERSION,
        "lease_object": dict(object_reference),
        "recovery_intent_object": dict(intent_reference),
        "recovery_completion_object": dict(completion_reference),
        "operator": authorization["operator"],
        "reason": authorization["reason"],
        "exact_generation_delete_completed": True,
        "active_state_after_target_release": current_state,
    }
    _write_create_only(recovery_receipt_path, _canonical_json(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fail-closed shared GCS heavy-experiment lease",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    acquire_parser = subparsers.add_parser("acquire")
    acquire_parser.add_argument("--run-id", required=True)
    acquire_parser.add_argument("--job-family", required=True)
    acquire_parser.add_argument("--code-sha", required=True)
    acquire_parser.add_argument("--image", required=True)
    acquire_parser.add_argument("--protocol-sha256", required=True)
    acquire_parser.add_argument("--receipt", type=Path, required=True)

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--receipt", type=Path)
    audit_parser.add_argument("--output", type=Path)

    release_parser = subparsers.add_parser("release")
    release_parser.add_argument("--receipt", type=Path, required=True)
    release_parser.add_argument(
        "--completion-reference", type=Path, required=True,
    )
    release_parser.add_argument("--release-receipt", type=Path, required=True)

    recover_parser = subparsers.add_parser("recover")
    recover_parser.add_argument("--audit", type=Path, required=True)
    recover_parser.add_argument("--authorization", type=Path, required=True)
    recover_parser.add_argument("--recovery-receipt", type=Path, required=True)
    recover_parser.add_argument("--confirm-generation", required=True)
    recover_parser.add_argument("--confirm-sha256", required=True)
    recover_parser.add_argument("--confirm-run-id", required=True)

    args = parser.parse_args()
    if args.command == "acquire":
        result = acquire(
            run_id=args.run_id, job_family=args.job_family,
            code_sha=args.code_sha, image=args.image,
            protocol_sha256=args.protocol_sha256,
            receipt_path=args.receipt,
        )
        print("HEAVY_EXPERIMENT_LEASE_ACQUIRED " + json.dumps(
            result["object"], sort_keys=True,
        ))
    elif args.command == "audit":
        result = audit(receipt_path=args.receipt, output_path=args.output)
        print("HEAVY_EXPERIMENT_LEASE_AUDIT " + json.dumps(
            result, sort_keys=True,
        ))
    elif args.command == "release":
        result = release(
            receipt_path=args.receipt,
            completion_reference_path=args.completion_reference,
            release_receipt_path=args.release_receipt,
        )
        print("HEAVY_EXPERIMENT_LEASE_RELEASED " + json.dumps(
            result["release_completion_object"], sort_keys=True,
        ))
    else:
        result = recover(
            audit_path=args.audit, authorization_path=args.authorization,
            recovery_receipt_path=args.recovery_receipt,
            confirm_generation=args.confirm_generation,
            confirm_sha256=args.confirm_sha256,
            confirm_run_id=args.confirm_run_id,
        )
        print("HEAVY_EXPERIMENT_LEASE_RECOVERED " + json.dumps(
            result["recovery_completion_object"], sort_keys=True,
        ))


if __name__ == "__main__":
    main()
