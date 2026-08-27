#!/usr/bin/env python3
"""Recover one already-successful R6 fixed BigQuery job, without submission.

This executable is deliberately separate from the ordinary outcome-supply
runner.  It has no job-creation capability.  ``prepare`` freezes the failed
execution, the existing read attempt, the still-live lease, and metadata for
the exact terminal-successful BigQuery job.  ``recover`` may look up only that
job and consume its existing result once.  ``finalize`` binds the successful
Cloud Run recovery envelope to the resulting create-once supply artifacts.

All command output is a compact control receipt.  Realized rows are written
only through the canonical supply transaction and are never printed here.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from typing import Final


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.research import corpus_parametric_batch as batch  # noqa: E402
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_full_union_outcome_supply_v1 as supply,
)
from nfl_dfs.research import corpus_realized_outcome_transport as registered  # noqa: E402
from nfl_dfs.research import lr8_label_score_map as shared  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
RECOVERY_ORDINAL: Final = 1
RECOVERY_ENABLED_ENV: Final = "R6_FULL_UNION_OUTCOME_RECOVERY_ENABLED"
RECOVERY_STAGE_TOKEN_ENV: Final = "R6_RECOVERY_STAGE_TOKEN"
RECOVERY_CODE_ENV: Final = "R6_FULL_UNION_RECOVERY_CODE_SHA"
RECOVERY_IMAGE_ENV: Final = "R6_FULL_UNION_RECOVERY_RUNTIME_IMAGE"
INTENT_SCHEMA: Final = "r6-full-union-outcome-supply-recovery-intent/v1"
WORKER_SCHEMA: Final = "r6-full-union-outcome-supply-recovery-worker/v1"
RECEIPT_SCHEMA: Final = "r6-full-union-outcome-supply-recovery-receipt/v1"
OPERATION: Final = "recover-terminal-successful-fixed-query-job"

_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_EXECUTION: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,127}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")

_IDENTITY_KEYS: Final = frozenset({"uri", "generation", "sha256", "bytes"})
_RUNTIME_KEYS: Final = frozenset({
    "code_sha", "image", "service_account",
})
_MEASUREMENT_KEYS: Final = frozenset({"sha256", "bytes"})
_FAILURE_KEYS: Final = frozenset({
    "launch_intent_measurement", "launch_stage_token", "launch_argv_sha256",
    "execution_name", "execution_uid", "terminal_execution_measurement",
    "terminal_projection",
})
_FAILURE_PROJECTION_KEYS: Final = frozenset({
    "completed_status", "failed_count", "succeeded_count", "running_count",
    "max_retries", "exit_code",
})
_SNAPSHOT_CODE_KEYS: Final = frozenset({
    "snapshot_module_sha256", "snapshot_cli_sha256",
    "snapshot_test_sha256", "snapshot_cli_test_sha256",
})
_ATTEMPT_CLAIM_KEYS: Final = frozenset({
    "attempt_sha256", "query_contract_sha256", "query_job_id",
    "query_location", "sql_sha256", "parameters_sha256",
    "table_receipt_set_sha256", "source_snapshot_at",
})
_FIXED_JOB_KEYS: Final = frozenset({
    "job_id", "location", "state", "error_result", "cache_hit",
    "total_bytes_processed", "created", "started", "ended", "sql_sha256",
    "parameters_sha256", "use_legacy_sql", "use_query_cache",
})
_OUTPUT_URI_KEYS: Final = frozenset({
    "query_evidence", "realized_source", "outcome_snapshot", "completion",
    "grade_root", "grade_completion", "worker_completion", "recovery_receipt",
})
_SAFETY_KEYS: Final = frozenset({
    "existing_job_lookup_only", "expected_get_job_calls",
    "expected_result_calls", "result_job_retry_disabled",
    "query_submission_licensed", "new_job_creation_licensed",
    "read_attempt_creation_licensed", "automatic_retry_licensed",
    "additional_recovery_licensed", "historical_retune_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority",
})
_INTENT_KEYS: Final = frozenset({
    "schema_version", "recovery_intent_sha256", "created_at", "project",
    "region", "run_id", "cloud_run_job", "recovery_ordinal", "operation",
    "original_runtime", "recovery_runtime", "original_supply_failure",
    "panel_freeze_identity", "outcome_key_projection_identity",
    "actual_root_smoke_receipt_identity", "query_compile_receipt_identity",
    "snapshot_code_identities", "historical_outcome_lease_identity",
    "read_attempt_identity", "read_attempt_claims", "fixed_query_job",
    "recovery_runner_sha256", "supply_module_sha256", "output_uris", "safety",
})
_RUNTIME_ENVELOPE_KEYS: Final = frozenset({
    "cloud_run_job", "cloud_run_execution", "cloud_run_task_index",
    "cloud_run_task_count", "cloud_run_task_attempt", "recovery_stage_token",
    "recovery_code_sha", "recovery_image",
})
_STANDARD_IDENTITY_KEYS: Final = frozenset({
    "attempt", "query_evidence", "realized_source", "outcome_snapshot",
    "completion",
})
_WORKER_KEYS: Final = frozenset({
    "schema_version", "worker_completion_sha256", "completed_at", "run_id",
    "cloud_run_job", "recovery_intent_identity", "recovery_intent_sha256",
    "original_runtime", "recovery_runtime", "runtime_envelope",
    "read_attempt_identity", "fixed_query_job", "standard_artifact_identities",
    "query_job_disposition", "get_job_call_count", "result_call_count",
    "job_submission_count", "new_job_count", "one_existing_result_consumed",
    "result_job_retry_disabled", "automatic_retry_licensed",
    "additional_recovery_licensed", "historical_retune_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority",
})
_TERMINAL_PROJECTION_KEYS: Final = frozenset({
    "execution_name", "execution_uid", "completed_status", "succeeded_count",
    "failed_count", "running_count", "completion_time", "max_retries",
})
_RECEIPT_KEYS: Final = frozenset({
    "schema_version", "recovery_receipt_sha256", "closed_at", "run_id",
    "cloud_run_job", "recovery_intent_identity", "recovery_intent_sha256",
    "worker_completion_identity", "worker_completion_sha256",
    "original_runtime", "recovery_runtime", "original_supply_failure",
    "recovery_terminal_execution_measurement", "recovery_terminal_projection",
    "runtime_envelope", "read_attempt_identity", "fixed_query_job",
    "standard_artifact_identities", "query_job_disposition",
    "get_job_call_count", "result_call_count", "job_submission_count",
    "new_job_count", "same_fixed_job_recovered", "recovery_closed",
    "automatic_retry_licensed", "additional_recovery_licensed",
    "historical_retune_licensed", "graph_mutation_licensed",
    "production_change_licensed", "decision_authority",
})

_ATTEMPT_KEYS: Final = frozenset({
    "schema_version", "run_id", "object_uri", "panel_freeze_identity",
    "panel_freeze_sha256", "panel_freeze_object_sha256",
    "outcome_key_projection_identity", "outcome_key_projection_sha256",
    "actual_root_smoke_receipt_identity", "actual_root_smoke_receipt_sha256",
    "later_source_freeze_identity", "later_source_freeze_sha256",
    "outcome_key_count", "outcome_keys_sha256", "query_contract",
    "query_contract_sha256", "table_receipts_before_query",
    "table_receipt_set_sha256", "historical_outcome_lease", "started_at",
    "uses_realized_outcomes_at_creation", "attempt_precedes_query",
    "historical_retry_licensed", "historical_retune_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority", "attempt_sha256",
})
_QUERY_CONTRACT_KEYS: Final = frozenset({
    "schema_version", "job_id", "location", "sql_sha256",
    "parameters_sha256", "union_keys_sha256", "tables", "selected_columns",
    "source_snapshot_at", "query_count", "use_query_cache",
    "panel_freeze_object_sha256",
})


class R6FullUnionRecoveryV1Error(RuntimeError):
    """The fixed-job recovery boundary failed closed."""


@dataclass(frozen=True, slots=True)
class RecoveryObjectV1:
    body: Mapping[str, object]
    identity: Mapping[str, object]


def _fail(message: str) -> None:
    raise R6FullUnionRecoveryV1Error(message)


def _canonical(value: object) -> bytes:
    return batch.canonical_json_bytes(value)


def _self_hashed(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(value)
    if field in result:
        raise AssertionError("self-hash field was pre-populated")
    result[field] = supply.canonical_sha256(result)
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> None:
    retained = value.get(field)
    if type(retained) is not str or _SHA256.fullmatch(retained) is None:
        _fail(f"{label} self hash differs")
    unhashed = dict(value)
    del unhashed[field]
    if supply.canonical_sha256(unhashed) != retained:
        _fail(f"{label} self hash differs")


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be one object")
    return dict(value)


def _exact_keys(value: Mapping[str, object], keys: frozenset[str], *, label: str) -> None:
    if frozenset(value) != keys:
        _fail(f"{label} fields differ")


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _code_sha(value: object, *, label: str) -> str:
    if type(value) is not str or _CODE_SHA.fullmatch(value) is None:
        _fail(f"{label} differs")
    return value


def _image(value: object, *, label: str) -> str:
    if type(value) is not str or _IMAGE.fullmatch(value) is None:
        _fail(f"{label} differs")
    return value


def _generation(value: object, *, label: str) -> str:
    if type(value) is int and value >= 1:
        return str(value)
    if type(value) is str and value.isdigit() and not value.startswith("0"):
        return value
    _fail(f"{label} generation differs")


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        result = batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise R6FullUnionRecoveryV1Error(str(exc)) from exc
    if frozenset(result) != _IDENTITY_KEYS:
        _fail(f"{label} fields differ")
    return result


def _identity_from_published(
    value: registered.PublishedObject, *, label: str,
) -> dict[str, object]:
    receipt = _mapping(value.receipt, label=f"{label} receipt")
    try:
        projected = {key: receipt[key] for key in _IDENTITY_KEYS}
    except KeyError as exc:
        raise R6FullUnionRecoveryV1Error(
            f"{label} receipt lacks a content identity"
        ) from exc
    return _identity(projected, label=label)


def _iso(value: object, *, label: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        _fail(f"{label} timestamp differs")
    return value.astimezone(timezone.utc).isoformat()


def _iso_text(value: object, *, label: str) -> str:
    if type(value) is not str:
        _fail(f"{label} timestamp differs")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise R6FullUnionRecoveryV1Error(f"{label} timestamp differs") from exc
    if parsed.tzinfo is None:
        _fail(f"{label} timestamp differs")
    return parsed.astimezone(timezone.utc).isoformat()


def _json(raw: bytes, *, label: str, newline_ok: bool = False) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} bytes differ")
    retained = raw[:-1] if newline_ok and raw.endswith(b"\n") else raw
    try:
        value = json.loads(retained)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise R6FullUnionRecoveryV1Error(f"{label} JSON differs") from exc
    if not isinstance(value, Mapping):
        _fail(f"{label} must be one JSON object")
    if _canonical(value) != retained:
        _fail(f"{label} is not canonical JSON")
    return dict(value)


def _gcs_parts(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or "/" not in uri.removeprefix("gs://"):
        _fail("GCS URI differs")
    return tuple(uri.removeprefix("gs://").split("/", 1))  # type: ignore[return-value]


def _is_not_found(exc: Exception) -> bool:
    try:
        from google.api_core.exceptions import NotFound
    except ImportError:
        return type(exc).__name__ == "NotFound"
    return isinstance(exc, NotFound) or type(exc).__name__ == "NotFound"


class GenerationPinnedGCSV1:
    """Known-name reads and generation-pinned create/equal publication."""

    def __init__(self, client: object):
        self._client = client
        self._cache: dict[tuple[str, str, str, int], bytes] = {}

    def read_exact(self, value: Mapping[str, object]) -> bytes:
        identity = _identity(value, label="generation-pinned read identity")
        key = (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )
        if key in self._cache:
            return self._cache[key]
        bucket, name = _gcs_parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        try:
            blob = self._client.bucket(bucket).blob(name, generation=generation)  # type: ignore[attr-defined]
            blob.reload(if_generation_match=generation)
            raw = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise R6FullUnionRecoveryV1Error(
                "generation-pinned object read failed"
            ) from exc
        if (
            type(raw) is not bytes
            or _generation(blob.generation, label="reopened object")
            != identity["generation"]
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("generation-pinned object content differs")
        self._cache[key] = raw
        return raw

    def resolve_known(self, uri: str) -> registered.PublishedObject | None:
        bucket, name = _gcs_parts(uri)
        try:
            current = self._client.bucket(bucket).blob(name)  # type: ignore[attr-defined]
            current.reload()
        except Exception as exc:
            if _is_not_found(exc):
                return None
            raise R6FullUnionRecoveryV1Error(
                "known-name object resolution failed"
            ) from exc
        generation = _generation(current.generation, label="current object")
        try:
            pinned = self._client.bucket(bucket).blob(  # type: ignore[attr-defined]
                name, generation=int(generation)
            )
            pinned.reload(if_generation_match=int(generation))
            raw = pinned.download_as_bytes(if_generation_match=int(generation))
        except Exception as exc:
            raise R6FullUnionRecoveryV1Error(
                "known-generation object reopen failed"
            ) from exc
        if type(raw) is not bytes or not raw:
            _fail("known object bytes differ")
        return registered.PublishedObject(
            receipt={
                "uri": uri,
                "generation": generation,
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
                "create_only": True,
            },
            reopened_raw=raw,
            created_at=_iso(pinned.time_created, label="object creation"),
            created=False,
        )

    def resolve_required(self, uri: str) -> registered.PublishedObject:
        value = self.resolve_known(uri)
        if value is None:
            _fail(f"required object is absent: {uri}")
        return value

    def require_identity(
        self, value: Mapping[str, object], *, label: str,
    ) -> registered.PublishedObject:
        expected = _identity(value, label=f"expected {label} identity")
        observed = self.resolve_required(str(expected["uri"]))
        if _identity_from_published(observed, label=label) != expected:
            _fail(f"current {label} identity differs")
        return observed

    def require_absent(self, uris: Sequence[str], *, label: str) -> None:
        for uri in uris:
            if self.resolve_known(uri) is not None:
                _fail(f"{label} must be absent: {uri}")

    def publish(self, uri: str, raw: bytes) -> registered.PublishedObject:
        if type(raw) is not bytes or not raw:
            _fail("create-only publication payload differs")
        bucket, name = _gcs_parts(uri)
        created = False
        try:
            blob = self._client.bucket(bucket).blob(name)  # type: ignore[attr-defined]
            blob.upload_from_string(
                raw, content_type="application/json", if_generation_match=0
            )
            created = True
        except Exception:
            created = False
        reopened = self.resolve_required(uri)
        if reopened.reopened_raw != raw:
            _fail("create-only publication collision differs")
        return registered.PublishedObject(
            receipt=reopened.receipt,
            reopened_raw=reopened.reopened_raw,
            created_at=reopened.created_at,
            created=created,
        )


def _output_roots(run_id: str) -> tuple[str, str, str]:
    supply_root = (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        f"corpus-r6-full-union-realized/{run_id}"
    )
    grade_root = (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        f"corpus-r6-full-union-realized-grades/{run_id}"
    )
    recovery_root = f"{supply_root}/recoveries/supply-attempt-01"
    return supply_root, grade_root, recovery_root


def _output_uris(run_id: str) -> dict[str, object]:
    supply_root, grade_root, recovery_root = _output_roots(run_id)
    return {
        "query_evidence": f"{supply_root}/query-evidence.json",
        "realized_source": f"{supply_root}/realized-source.json",
        "outcome_snapshot": f"{supply_root}/outcome-snapshot.json",
        "completion": f"{supply_root}/completion.json",
        "grade_root": f"{grade_root}/realized-grade-root.json",
        "grade_completion": f"{grade_root}/grade-completion.json",
        "worker_completion": f"{recovery_root}/worker-completion.json",
        "recovery_receipt": f"{recovery_root}/recovery-receipt.json",
    }


def _intent_uri(run_id: str) -> str:
    return f"{_output_roots(run_id)[2]}/recovery-intent.json"


def _measurement(raw: bytes) -> dict[str, object]:
    return {"sha256": sha256(raw).hexdigest(), "bytes": len(raw)}


def _read_local_object(path: Path, *, label: str) -> tuple[dict[str, object], bytes]:
    if path.is_symlink() or not path.is_file():
        _fail(f"{label} path differs")
    raw = path.read_bytes()
    return _json(raw, label=label, newline_ok=True), raw


def _runtime(
    *, code_sha: object, image: object, service_account: object, label: str,
) -> dict[str, object]:
    retained = {
        "code_sha": _code_sha(code_sha, label=f"{label} code SHA"),
        "image": _image(image, label=f"{label} image"),
        "service_account": str(service_account),
    }
    if not retained["service_account"] or "@" not in retained["service_account"]:
        _fail(f"{label} service account differs")
    return retained


def _failed_execution(
    *, launch_path: Path, terminal_path: Path, run_id: str, job: str,
    project: str, region: str, original_runtime: Mapping[str, object],
) -> dict[str, object]:
    launch, launch_raw = _read_local_object(
        launch_path, label="original supply launch intent"
    )
    terminal, terminal_raw = _read_local_object(
        terminal_path, label="original supply terminal execution"
    )
    metadata = _mapping(terminal.get("metadata"), label="original execution metadata")
    spec = _mapping(terminal.get("spec"), label="original execution spec")
    status = _mapping(terminal.get("status"), label="original execution status")
    template = _mapping(spec.get("template"), label="original execution template")
    task = _mapping(template.get("spec"), label="original execution task")
    containers = task.get("containers")
    conditions = status.get("conditions")
    labels = _mapping(metadata.get("labels"), label="original execution labels")
    if (
        not isinstance(containers, list) or len(containers) != 1
        or not isinstance(containers[0], Mapping)
        or not isinstance(conditions, list)
    ):
        _fail("original supply execution envelope differs")
    completed = [
        item for item in conditions
        if isinstance(item, Mapping) and item.get("type") == "Completed"
    ]
    name = str(metadata.get("name", "")).rsplit("/", 1)[-1]
    message = str(completed[0].get("message", "")) if len(completed) == 1 else ""
    match = re.search(r"exit code:\s*([0-9]+)", message)
    projection = {
        "completed_status": completed[0].get("status") if len(completed) == 1 else None,
        "failed_count": status.get("failedCount", 0),
        "succeeded_count": status.get("succeededCount", 0),
        "running_count": status.get("runningCount", 0),
        "max_retries": task.get("maxRetries"),
        "exit_code": int(match.group(1)) if match else None,
    }
    container = dict(containers[0])
    if (
        launch.get("schema_version") != "r6-full-union-stage-launch-intent/v1"
        or launch.get("stage") != "supply"
        or launch.get("run_id") != run_id
        or launch.get("job") != job
        or launch.get("project") != project
        or launch.get("region") != region
        or launch.get("code_sha") != original_runtime["code_sha"]
        or launch.get("image") != original_runtime["image"]
        or launch.get("service_account") != original_runtime["service_account"]
        or launch.get("automatic_retry_licensed") is not False
        or type(launch.get("token")) is not str
        or _SHA256.fullmatch(str(launch.get("token"))) is None
        or type(launch.get("argv_sha256")) is not str
        or _SHA256.fullmatch(str(launch.get("argv_sha256"))) is None
        or _EXECUTION.fullmatch(name) is None
        or metadata.get("uid") in (None, "")
        or labels.get("run.googleapis.com/job") != job
        or projection != {
            "completed_status": "False", "failed_count": 1,
            "succeeded_count": 0, "running_count": 0,
            "max_retries": 0, "exit_code": 1,
        }
        or container.get("image") != original_runtime["image"]
        or task.get("serviceAccountName") != original_runtime["service_account"]
    ):
        _fail("original supply terminal-failure binding differs")
    return {
        "launch_intent_measurement": _measurement(launch_raw),
        "launch_stage_token": launch["token"],
        "launch_argv_sha256": launch["argv_sha256"],
        "execution_name": name,
        "execution_uid": str(metadata["uid"]),
        "terminal_execution_measurement": _measurement(terminal_raw),
        "terminal_projection": projection,
    }


def _validate_attempt(
    raw: bytes, *, identity: Mapping[str, object], run_id: str,
    panel_identity: Mapping[str, object], projection_identity: Mapping[str, object],
    smoke_identity: Mapping[str, object], lease_identity: Mapping[str, object],
    original_runtime: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    attempt = _json(raw, label="existing R6 read attempt")
    _exact_keys(attempt, _ATTEMPT_KEYS, label="existing R6 read attempt")
    _validate_self_hash(attempt, field="attempt_sha256", label="existing R6 read attempt")
    contract = _mapping(attempt.get("query_contract"), label="frozen query contract")
    _exact_keys(contract, _QUERY_CONTRACT_KEYS, label="frozen query contract")
    lease = _mapping(attempt.get("historical_outcome_lease"), label="attempt lease")
    lease_body = _mapping(lease.get("body"), label="attempt lease body")
    lease_receipt = _mapping(lease.get("object_receipt"), label="attempt lease receipt")
    projected_lease = _identity(
        {key: lease_receipt.get(key) for key in _IDENTITY_KEYS},
        label="attempt lease identity",
    )
    source_snapshot = _iso_text(contract.get("source_snapshot_at"), label="source snapshot")
    if (
        attempt.get("schema_version") != supply.ATTEMPT_SCHEMA
        or attempt.get("run_id") != run_id
        or attempt.get("object_uri") != identity["uri"]
        or attempt.get("panel_freeze_identity") != panel_identity
        or attempt.get("outcome_key_projection_identity") != projection_identity
        or attempt.get("actual_root_smoke_receipt_identity") != smoke_identity
        or attempt.get("query_contract_sha256") != supply.canonical_sha256(contract)
        or attempt.get("table_receipt_set_sha256")
        != supply.canonical_sha256(attempt.get("table_receipts_before_query"))
        or projected_lease != lease_identity
        or lease_receipt.get("create_only") is not True
        or lease_body.get("run_id") != run_id
        or lease_body.get("job") != original_runtime.get("job", lease_body.get("job"))
        or lease_body.get("code_sha") != original_runtime["code_sha"]
        or lease_body.get("image") != original_runtime["image"]
        or contract.get("schema_version") != supply.QUERY_CONTRACT_SCHEMA
        or contract.get("query_count") != 1
        or contract.get("use_query_cache") is not False
        or type(contract.get("job_id")) is not str
        or type(contract.get("location")) is not str
        or type(contract.get("sql_sha256")) is not str
        or _SHA256.fullmatch(str(contract.get("sql_sha256"))) is None
        or type(contract.get("parameters_sha256")) is not str
        or _SHA256.fullmatch(str(contract.get("parameters_sha256"))) is None
        or source_snapshot != contract.get("source_snapshot_at")
        or attempt.get("uses_realized_outcomes_at_creation") is not False
        or attempt.get("attempt_precedes_query") is not True
        or any(attempt.get(field) is not False for field in (
            "historical_retry_licensed", "historical_retune_licensed",
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("existing R6 read-attempt contract differs")
    claims = {
        "attempt_sha256": attempt["attempt_sha256"],
        "query_contract_sha256": attempt["query_contract_sha256"],
        "query_job_id": contract["job_id"],
        "query_location": contract["location"],
        "sql_sha256": contract["sql_sha256"],
        "parameters_sha256": contract["parameters_sha256"],
        "table_receipt_set_sha256": attempt["table_receipt_set_sha256"],
        "source_snapshot_at": contract["source_snapshot_at"],
    }
    return attempt, claims


def _job_times(job: object) -> tuple[str, str, str]:
    return (
        _iso(getattr(job, "created", None), label="fixed job created"),
        _iso(getattr(job, "started", None), label="fixed job started"),
        _iso(getattr(job, "ended", None), label="fixed job ended"),
    )


def _terminal_job_metadata(
    get_job: Callable[..., object], *, claims: Mapping[str, object],
) -> dict[str, object]:
    try:
        job = get_job(str(claims["query_job_id"]), location=str(claims["query_location"]))
    except Exception as exc:
        raise R6FullUnionRecoveryV1Error("fixed BigQuery job lookup failed") from exc
    created, started, ended = _job_times(job)
    raw_sql = getattr(job, "query", None)
    metadata = {
        "job_id": getattr(job, "job_id", None),
        "location": getattr(job, "location", None),
        "state": getattr(job, "state", None),
        "error_result": getattr(job, "error_result", None),
        "cache_hit": getattr(job, "cache_hit", None),
        "total_bytes_processed": getattr(job, "total_bytes_processed", None),
        "created": created,
        "started": started,
        "ended": ended,
        "sql_sha256": sha256(str(raw_sql).encode()).hexdigest()
        if type(raw_sql) is str else None,
        "parameters_sha256": claims["parameters_sha256"],
        "use_legacy_sql": getattr(job, "use_legacy_sql", None),
        "use_query_cache": getattr(job, "use_query_cache", None),
    }
    if (
        metadata["job_id"] != claims["query_job_id"]
        or metadata["location"] != claims["query_location"]
        or metadata["state"] != "DONE"
        or metadata["error_result"] is not None
        or metadata["cache_hit"] is not False
        or type(metadata["total_bytes_processed"]) is not int
        or metadata["total_bytes_processed"] < 0
        or metadata["sql_sha256"] != claims["sql_sha256"]
        or metadata["use_legacy_sql"] is not False
        or metadata["use_query_cache"] is not False
        or not (created <= started <= ended)
    ):
        _fail("fixed BigQuery terminal-success metadata differs")
    return metadata


def _source_measurement(module: object, *, label: str) -> str:
    path = getattr(module, "__file__", None)
    if type(path) is not str or not Path(path).is_file():
        _fail(f"{label} source measurement differs")
    return sha256(Path(path).read_bytes()).hexdigest()


def validate_recovery_intent_v1(value: object) -> dict[str, object]:
    intent = _mapping(value, label="recovery intent")
    _exact_keys(intent, _INTENT_KEYS, label="recovery intent")
    _validate_self_hash(intent, field="recovery_intent_sha256", label="recovery intent")
    original = _mapping(intent.get("original_runtime"), label="original runtime")
    recovery = _mapping(intent.get("recovery_runtime"), label="recovery runtime")
    failure = _mapping(intent.get("original_supply_failure"), label="original failure")
    claims = _mapping(intent.get("read_attempt_claims"), label="read-attempt claims")
    fixed = _mapping(intent.get("fixed_query_job"), label="fixed query job")
    code = _mapping(intent.get("snapshot_code_identities"), label="snapshot code")
    outputs = _mapping(intent.get("output_uris"), label="recovery output URIs")
    safety = _mapping(intent.get("safety"), label="recovery safety law")
    for runtime, label in ((original, "original runtime"), (recovery, "recovery runtime")):
        _exact_keys(runtime, _RUNTIME_KEYS, label=label)
        _runtime(
            code_sha=runtime.get("code_sha"), image=runtime.get("image"),
            service_account=runtime.get("service_account"), label=label,
        )
    _exact_keys(failure, _FAILURE_KEYS, label="original failure")
    _exact_keys(
        _mapping(failure.get("launch_intent_measurement"), label="launch measurement"),
        _MEASUREMENT_KEYS, label="launch measurement",
    )
    _exact_keys(
        _mapping(failure.get("terminal_execution_measurement"), label="terminal measurement"),
        _MEASUREMENT_KEYS, label="terminal measurement",
    )
    _exact_keys(
        _mapping(failure.get("terminal_projection"), label="failure projection"),
        _FAILURE_PROJECTION_KEYS, label="failure projection",
    )
    _exact_keys(claims, _ATTEMPT_CLAIM_KEYS, label="read-attempt claims")
    _exact_keys(fixed, _FIXED_JOB_KEYS, label="fixed query job")
    _exact_keys(code, _SNAPSHOT_CODE_KEYS, label="snapshot code")
    _exact_keys(outputs, _OUTPUT_URI_KEYS, label="recovery output URIs")
    _exact_keys(safety, _SAFETY_KEYS, label="recovery safety law")
    run_id = intent.get("run_id")
    job = intent.get("cloud_run_job")
    if (
        intent.get("schema_version") != INTENT_SCHEMA
        or intent.get("project") != PROJECT
        or intent.get("region") != REGION
        or type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None
        or type(job) is not str or _JOB.fullmatch(job) is None
        or intent.get("recovery_ordinal") != RECOVERY_ORDINAL
        or intent.get("operation") != OPERATION
        or original["service_account"] != recovery["service_account"]
        or claims["query_job_id"] != fixed["job_id"]
        or claims["query_location"] != fixed["location"]
        or claims["sql_sha256"] != fixed["sql_sha256"]
        or claims["parameters_sha256"] != fixed["parameters_sha256"]
        or fixed["state"] != "DONE" or fixed["error_result"] is not None
        or fixed["cache_hit"] is not False
        or fixed["use_legacy_sql"] is not False
        or fixed["use_query_cache"] is not False
        or outputs != _output_uris(run_id)
        or safety != {
            "existing_job_lookup_only": True,
            "expected_get_job_calls": 1,
            "expected_result_calls": 1,
            "result_job_retry_disabled": True,
            "query_submission_licensed": False,
            "new_job_creation_licensed": False,
            "read_attempt_creation_licensed": False,
            "automatic_retry_licensed": False,
            "additional_recovery_licensed": False,
            "historical_retune_licensed": False,
            "graph_mutation_licensed": False,
            "production_change_licensed": False,
            "decision_authority": False,
        }
        or any(_SHA256.fullmatch(str(value)) is None for value in code.values())
        or intent.get("recovery_runner_sha256")
        != sha256(Path(__file__).read_bytes()).hexdigest()
        or intent.get("supply_module_sha256")
        != _source_measurement(supply, label="supply module")
    ):
        _fail("recovery intent contract differs")
    for field in (
        "panel_freeze_identity", "outcome_key_projection_identity",
        "actual_root_smoke_receipt_identity", "query_compile_receipt_identity",
        "historical_outcome_lease_identity", "read_attempt_identity",
    ):
        intent[field] = _identity(intent.get(field), label=field)
    _iso_text(intent.get("created_at"), label="recovery intent creation")
    return intent


def _existing_intent(
    store: GenerationPinnedGCSV1, *, run_id: str,
) -> RecoveryObjectV1 | None:
    observed = store.resolve_known(_intent_uri(run_id))
    if observed is None:
        return None
    body = validate_recovery_intent_v1(
        _json(observed.reopened_raw, label="persisted recovery intent")
    )
    return RecoveryObjectV1(
        body=body,
        identity=_identity_from_published(observed, label="recovery intent"),
    )


def prepare_recovery_intent_v1(
    *, project: str, region: str, run_id: str, job: str,
    original_code_sha: str, original_image: str,
    recovery_code_sha: str, recovery_image: str, service_account: str,
    original_launch_intent_path: Path, original_terminal_execution_path: Path,
    panel_freeze_identity: Mapping[str, object],
    outcome_key_projection_identity: Mapping[str, object],
    actual_root_smoke_receipt_identity: Mapping[str, object],
    query_compile_receipt_identity: Mapping[str, object],
    expected_lease_identity: Mapping[str, object],
    read_attempt_identity: Mapping[str, object],
    snapshot_code_identities: Mapping[str, object], storage_client: object,
    bq_client_factory: Callable[[], object],
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> RecoveryObjectV1:
    if (
        project != PROJECT or region != REGION
        or _RUN_ID.fullmatch(run_id) is None or _JOB.fullmatch(job) is None
    ):
        _fail("recovery controller identity differs")
    original = _runtime(
        code_sha=original_code_sha, image=original_image,
        service_account=service_account, label="original runtime",
    )
    recovery = _runtime(
        code_sha=recovery_code_sha, image=recovery_image,
        service_account=service_account, label="recovery runtime",
    )
    original_with_job = {**original, "job": job}
    failure = _failed_execution(
        launch_path=original_launch_intent_path,
        terminal_path=original_terminal_execution_path,
        run_id=run_id, job=job, project=project, region=region,
        original_runtime=original,
    )
    store = GenerationPinnedGCSV1(storage_client)
    retained_identities = {
        "panel_freeze_identity": _identity(panel_freeze_identity, label="panel freeze"),
        "outcome_key_projection_identity": _identity(
            outcome_key_projection_identity, label="outcome-key projection"
        ),
        "actual_root_smoke_receipt_identity": _identity(
            actual_root_smoke_receipt_identity, label="actual-root smoke"
        ),
        "query_compile_receipt_identity": _identity(
            query_compile_receipt_identity, label="query compile receipt"
        ),
        "historical_outcome_lease_identity": _identity(
            expected_lease_identity, label="historical-outcome lease"
        ),
        "read_attempt_identity": _identity(
            read_attempt_identity, label="read attempt"
        ),
    }
    for label, identity in retained_identities.items():
        store.require_identity(identity, label=label.replace("_", " "))
    lease_object = store.require_identity(
        retained_identities["historical_outcome_lease_identity"],
        label="historical-outcome lease",
    )
    lease = _json(
        lease_object.reopened_raw, label="historical-outcome lease", newline_ok=True
    )
    if (
        lease.get("run_id") != run_id or lease.get("job") != job
        or lease.get("code_sha") != original["code_sha"]
        or lease.get("image") != original["image"]
    ):
        _fail("live lease does not bind the original runtime")
    attempt_object = store.require_identity(
        retained_identities["read_attempt_identity"], label="read attempt"
    )
    _, claims = _validate_attempt(
        attempt_object.reopened_raw,
        identity=retained_identities["read_attempt_identity"], run_id=run_id,
        panel_identity=retained_identities["panel_freeze_identity"],
        projection_identity=retained_identities["outcome_key_projection_identity"],
        smoke_identity=retained_identities["actual_root_smoke_receipt_identity"],
        lease_identity=retained_identities["historical_outcome_lease_identity"],
        original_runtime=original_with_job,
    )
    outputs = _output_uris(run_id)
    store.require_absent(list(outputs.values()), label="pre-recovery downstream object")
    try:
        bq_client = bq_client_factory()
    except Exception as exc:
        raise R6FullUnionRecoveryV1Error("BigQuery recovery client construction failed") from exc
    if bq_client is None:
        _fail("BigQuery recovery client construction returned None")
    fixed = _terminal_job_metadata(bq_client.get_job, claims=claims)  # type: ignore[attr-defined]
    code = _mapping(snapshot_code_identities, label="snapshot code identities")
    _exact_keys(code, _SNAPSHOT_CODE_KEYS, label="snapshot code identities")
    for field, value in code.items():
        code[field] = _digest(value, label=field)
    existing = _existing_intent(store, run_id=run_id)
    if existing is not None:
        expected_bindings = {
            "project": project,
            "region": region,
            "run_id": run_id,
            "cloud_run_job": job,
            "original_runtime": original,
            "recovery_runtime": recovery,
            "original_supply_failure": failure,
            **retained_identities,
            "read_attempt_claims": claims,
            "fixed_query_job": fixed,
            "snapshot_code_identities": code,
            "output_uris": outputs,
        }
        if any(existing.body.get(field) != expected for field, expected in expected_bindings.items()):
            _fail("existing recovery intent differs from current requested bindings")
        return existing
    now = clock()
    intent = _self_hashed({
        "schema_version": INTENT_SCHEMA,
        "created_at": _iso(now, label="intent creation"),
        "project": project,
        "region": region,
        "run_id": run_id,
        "cloud_run_job": job,
        "recovery_ordinal": RECOVERY_ORDINAL,
        "operation": OPERATION,
        "original_runtime": original,
        "recovery_runtime": recovery,
        "original_supply_failure": failure,
        **retained_identities,
        "read_attempt_claims": claims,
        "fixed_query_job": fixed,
        "snapshot_code_identities": code,
        "recovery_runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "supply_module_sha256": _source_measurement(supply, label="supply module"),
        "output_uris": outputs,
        "safety": {
            "existing_job_lookup_only": True,
            "expected_get_job_calls": 1,
            "expected_result_calls": 1,
            "result_job_retry_disabled": True,
            "query_submission_licensed": False,
            "new_job_creation_licensed": False,
            "read_attempt_creation_licensed": False,
            "automatic_retry_licensed": False,
            "additional_recovery_licensed": False,
            "historical_retune_licensed": False,
            "graph_mutation_licensed": False,
            "production_change_licensed": False,
            "decision_authority": False,
        },
    }, field="recovery_intent_sha256")
    validated = validate_recovery_intent_v1(intent)
    published = store.publish(_intent_uri(run_id), _canonical(validated))
    return RecoveryObjectV1(
        body=validated,
        identity=_identity_from_published(published, label="recovery intent"),
    )


def _parameter_objects(spec: registered.QuerySpec) -> list[object]:
    from google.cloud import bigquery

    def timestamp(value: object) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        elif type(value) is str:
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError as exc:
                raise R6FullUnionRecoveryV1Error(
                    "fixed job TIMESTAMP parameter differs"
                ) from exc
        else:
            _fail("fixed job TIMESTAMP parameter differs")
        if parsed.tzinfo is None:
            _fail("fixed job TIMESTAMP parameter is naive")
        return parsed.astimezone(timezone.utc)

    result: list[object] = []
    for parameter in spec.parameters:
        retained: object = parameter.value
        if parameter.bq_type == "TIMESTAMP":
            if parameter.array:
                if isinstance(retained, (str, bytes)) or not isinstance(retained, Sequence):
                    _fail("fixed job TIMESTAMP array differs")
                retained = [timestamp(item) for item in retained]
            else:
                retained = timestamp(retained)
        if parameter.array:
            result.append(bigquery.ArrayQueryParameter(
                parameter.name, parameter.bq_type, list(retained)  # type: ignore[arg-type]
            ))
        else:
            result.append(bigquery.ScalarQueryParameter(
                parameter.name, parameter.bq_type, retained
            ))
    return result


def _parameter_api(values: Sequence[object]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for value in values:
        method = getattr(value, "to_api_repr", None)
        if not callable(method):
            _fail("fixed job parameter representation differs")
        raw = method()
        if not isinstance(raw, Mapping):
            _fail("fixed job parameter representation differs")
        result.append(dict(raw))
    return result


def _recover_existing_fixed_job(
    get_job: Callable[..., object], *, spec: registered.QuerySpec,
    expected_metadata: Mapping[str, object], counters: dict[str, int],
) -> supply.FullUnionOutcomeQueryResultV1:
    parameters = _parameter_objects(spec)
    counters["get_job"] += 1
    if counters["get_job"] != 1:
        _fail("fixed job lookup count differs")
    try:
        job = get_job(spec.job_id, location=spec.location)
    except Exception as exc:
        raise R6FullUnionRecoveryV1Error("exact fixed job recovery failed") from exc
    current = _terminal_job_metadata(lambda *_args, **_kwargs: job, claims={
        "query_job_id": spec.job_id,
        "query_location": spec.location,
        "sql_sha256": spec.sql_sha256,
        "parameters_sha256": spec.parameters_sha256,
    })
    actual_parameters = getattr(job, "query_parameters", None)
    if (
        current != dict(expected_metadata)
        or getattr(job, "query", None) != spec.sql
        or not isinstance(actual_parameters, Sequence)
        or isinstance(actual_parameters, (str, bytes))
        or _parameter_api(actual_parameters) != _parameter_api(parameters)
    ):
        _fail("exact fixed job configuration or terminal metadata differs")
    counters["result"] += 1
    if counters["result"] != 1:
        _fail("fixed job result-consumption count differs")
    try:
        completed = job.result(job_retry=None)  # type: ignore[attr-defined]
        rows = tuple(
            dict(row.items()) if hasattr(row, "items") else dict(row)
            for row in completed
        )
    except Exception as exc:
        raise R6FullUnionRecoveryV1Error(
            "existing fixed job result recovery failed"
        ) from exc
    receipt = {
        "job_id": current["job_id"],
        "location": current["location"],
        "sql_sha256": current["sql_sha256"],
        "parameters_sha256": current["parameters_sha256"],
        "created": current["created"],
        "started": current["started"],
        "ended": current["ended"],
        "total_bytes_processed": current["total_bytes_processed"],
        "cache_hit": current["cache_hit"],
        "error_result": current["error_result"],
    }
    return supply.FullUnionOutcomeQueryResultV1(
        result=shared.QueryResult(rows=rows, job_receipt=receipt),
        disposition="recovered",
    )


def _table_metadata(client: object, table_id: str) -> dict[str, object]:
    try:
        table = client.get_table(table_id)  # type: ignore[attr-defined]
    except Exception as exc:
        raise R6FullUnionRecoveryV1Error("table metadata read failed") from exc

    def field_payload(field: object) -> dict[str, object]:
        return {
            "name": field.name, "field_type": field.field_type, "mode": field.mode,
            "fields": [field_payload(child) for child in field.fields],
        }

    schema = [field_payload(field) for field in table.schema]
    if type(table.etag) is not str or not table.etag:
        _fail("table etag differs")
    return {
        "table_id": table_id,
        "etag": table.etag,
        "modified": _iso(table.modified, label="table modified"),
        "num_rows": table.num_rows,
        "schema_sha256": sha256(_canonical(schema)).hexdigest(),
    }


class _LeaseVerifier:
    def __init__(self, store: GenerationPinnedGCSV1, identity: Mapping[str, object]):
        self._store = store
        self._identity = _identity(identity, label="expected live lease")
        self._first: dict[str, object] | None = None

    def __call__(self) -> dict[str, object]:
        observed = self._store.require_identity(self._identity, label="live lease")
        body = _json(observed.reopened_raw, label="live lease", newline_ok=True)
        value = {
            "body": body,
            "object_receipt": {**self._identity, "create_only": True},
        }
        if self._first is None:
            self._first = value
        elif value != self._first:
            _fail("live lease changed during recovery")
        return value


class _RecoveryKnownReader:
    """Pin the old attempt and forbid pre-existing downstream recovery state."""

    def __init__(
        self, store: GenerationPinnedGCSV1, *, attempt_identity: Mapping[str, object],
        downstream_uris: Sequence[str],
    ) -> None:
        self._store = store
        self._attempt = _identity(attempt_identity, label="expected read attempt")
        self._downstream = frozenset(downstream_uris)

    def __call__(self, uri: str) -> registered.PublishedObject | None:
        observed = self._store.resolve_known(uri)
        if uri == self._attempt["uri"]:
            if observed is None:
                _fail("exact existing read attempt is absent")
            if _identity_from_published(observed, label="read attempt") != self._attempt:
                _fail("exact existing read attempt identity changed")
            return observed
        if uri in self._downstream and observed is not None:
            _fail(f"recover-only downstream object unexpectedly exists: {uri}")
        return observed


def _runtime_envelope(
    environ: Mapping[str, str], *, intent: Mapping[str, object],
    recovery_stage_token: str,
) -> dict[str, object]:
    recovery = _mapping(intent["recovery_runtime"], label="recovery runtime")
    execution = environ.get("CLOUD_RUN_EXECUTION", "")
    retained = {
        "cloud_run_job": environ.get("CLOUD_RUN_JOB"),
        "cloud_run_execution": execution,
        "cloud_run_task_index": environ.get("CLOUD_RUN_TASK_INDEX"),
        "cloud_run_task_count": environ.get("CLOUD_RUN_TASK_COUNT"),
        "cloud_run_task_attempt": environ.get("CLOUD_RUN_TASK_ATTEMPT"),
        "recovery_stage_token": environ.get(RECOVERY_STAGE_TOKEN_ENV),
        "recovery_code_sha": environ.get(RECOVERY_CODE_ENV),
        "recovery_image": environ.get(RECOVERY_IMAGE_ENV),
    }
    if (
        environ.get(RECOVERY_ENABLED_ENV) != "1"
        or retained["cloud_run_job"] != intent["cloud_run_job"]
        or type(execution) is not str or _EXECUTION.fullmatch(execution) is None
        or retained["cloud_run_task_index"] != "0"
        or retained["cloud_run_task_count"] != "1"
        or retained["cloud_run_task_attempt"] != "0"
        or retained["recovery_stage_token"] != recovery_stage_token
        or _SHA256.fullmatch(recovery_stage_token) is None
        or retained["recovery_code_sha"] != recovery["code_sha"]
        or retained["recovery_image"] != recovery["image"]
    ):
        _fail("recovery runtime environment differs")
    return retained


def _load_intent(
    store: GenerationPinnedGCSV1, identity: Mapping[str, object],
) -> RecoveryObjectV1:
    retained_identity = _identity(identity, label="expected recovery intent")
    observed = store.require_identity(retained_identity, label="recovery intent")
    body = validate_recovery_intent_v1(
        _json(observed.reopened_raw, label="recovery intent")
    )
    return RecoveryObjectV1(body=body, identity=retained_identity)


def _standard_identities(value: supply.FullUnionOutcomeSupplyV1) -> dict[str, object]:
    return {
        "attempt": dict(value.attempt_identity),
        "query_evidence": dict(value.query_evidence_identity),
        "realized_source": dict(value.realized_source_identity),
        "outcome_snapshot": dict(value.outcome_snapshot_identity),
        "completion": dict(value.completion_identity),
    }


def recover_supply_v1(
    *, project: str, run_id: str, job: str, original_code_sha: str,
    original_image: str, recovery_code_sha: str, recovery_image: str,
    recovery_stage_token: str, recovery_intent_identity: Mapping[str, object],
    environ: Mapping[str, str], storage_client: object,
    bq_client_factory: Callable[[], object],
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> RecoveryObjectV1:
    if project != PROJECT:
        _fail("recovery project differs")
    store = GenerationPinnedGCSV1(storage_client)
    retained = _load_intent(store, recovery_intent_identity)
    intent = dict(retained.body)
    original = _mapping(intent["original_runtime"], label="original runtime")
    recovery = _mapping(intent["recovery_runtime"], label="recovery runtime")
    if (
        intent["run_id"] != run_id or intent["cloud_run_job"] != job
        or original["code_sha"] != original_code_sha
        or original["image"] != original_image
        or recovery["code_sha"] != recovery_code_sha
        or recovery["image"] != recovery_image
    ):
        _fail("original/recovery runtime argument binding differs")
    runtime_envelope = _runtime_envelope(
        environ, intent=intent, recovery_stage_token=recovery_stage_token
    )
    outputs = _mapping(intent["output_uris"], label="recovery output URIs")
    store.require_absent(
        [
            str(outputs[key]) for key in (
                "query_evidence", "realized_source", "outcome_snapshot",
                "completion", "worker_completion", "recovery_receipt",
            )
        ],
        label="recover-only downstream object",
    )
    attempt_identity = _identity(intent["read_attempt_identity"], label="read attempt")
    store.require_identity(attempt_identity, label="read attempt")
    try:
        bq_client = bq_client_factory()
    except Exception as exc:
        raise R6FullUnionRecoveryV1Error("BigQuery recovery client construction failed") from exc
    if bq_client is None:
        _fail("BigQuery recovery client construction returned None")
    panel_identity = _identity(intent["panel_freeze_identity"], label="panel freeze")
    projection_identity = _identity(
        intent["outcome_key_projection_identity"], label="outcome-key projection"
    )
    smoke_identity = _identity(
        intent["actual_root_smoke_receipt_identity"], label="actual-root smoke"
    )
    projection_object = store.require_identity(
        projection_identity, label="outcome-key projection"
    )
    smoke_object = store.require_identity(smoke_identity, label="actual-root smoke")
    projection = _json(projection_object.reopened_raw, label="outcome-key projection")
    smoke = _json(smoke_object.reopened_raw, label="actual-root smoke")
    code = _mapping(intent["snapshot_code_identities"], label="snapshot code")
    config = supply.FullUnionOutcomeSupplyConfigV1(
        run_id=run_id, job=job, code_sha=original_code_sha,
        image=original_image, enabled=True,
    )
    counters = {"get_job": 0, "result": 0}
    fixed = _mapping(intent["fixed_query_job"], label="fixed query job")
    supplied = supply.supply_full_union_outcome_snapshot_v1(
        config=config,
        panel_freeze_identity=panel_identity,
        outcome_key_projection=projection,
        outcome_key_projection_identity=projection_identity,
        actual_root_smoke_receipt=smoke,
        actual_root_smoke_receipt_identity=smoke_identity,
        snapshot_module_sha256=code["snapshot_module_sha256"],
        snapshot_cli_sha256=code["snapshot_cli_sha256"],
        snapshot_test_sha256=code["snapshot_test_sha256"],
        snapshot_cli_test_sha256=code["snapshot_cli_test_sha256"],
        read_exact=store.read_exact,
        verify_lease=_LeaseVerifier(
            store, _identity(intent["historical_outcome_lease_identity"], label="lease")
        ),
        read_table_metadata=lambda table: _table_metadata(bq_client, table),
        get_or_create_query=lambda spec: _recover_existing_fixed_job(
            bq_client.get_job, spec=spec, expected_metadata=fixed, counters=counters  # type: ignore[attr-defined]
        ),
        publish=store.publish,
        read_known=_RecoveryKnownReader(
            store,
            attempt_identity=attempt_identity,
            downstream_uris=[
                str(outputs[key]) for key in (
                    "query_evidence", "realized_source", "outcome_snapshot",
                    "completion",
                )
            ],
        ),
        clock=clock,
    )
    standard = _standard_identities(supplied)
    if (
        counters != {"get_job": 1, "result": 1}
        or standard["attempt"] != attempt_identity
        or supplied.query_evidence.get("query_job_disposition") != "recovered"
        or supplied.completion.get("query_job_id") != fixed["job_id"]
    ):
        _fail("recover-only supply closure differs")
    completed_at = _iso(clock(), label="worker completion")
    worker = _self_hashed({
        "schema_version": WORKER_SCHEMA,
        "completed_at": completed_at,
        "run_id": run_id,
        "cloud_run_job": job,
        "recovery_intent_identity": dict(retained.identity),
        "recovery_intent_sha256": intent["recovery_intent_sha256"],
        "original_runtime": original,
        "recovery_runtime": recovery,
        "runtime_envelope": runtime_envelope,
        "read_attempt_identity": attempt_identity,
        "fixed_query_job": fixed,
        "standard_artifact_identities": standard,
        "query_job_disposition": "recovered",
        "get_job_call_count": 1,
        "result_call_count": 1,
        "job_submission_count": 0,
        "new_job_count": 0,
        "one_existing_result_consumed": True,
        "result_job_retry_disabled": True,
        "automatic_retry_licensed": False,
        "additional_recovery_licensed": False,
        "historical_retune_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }, field="worker_completion_sha256")
    validate_worker_completion_v1(worker, intent=intent, intent_identity=retained.identity)
    published = store.publish(str(outputs["worker_completion"]), _canonical(worker))
    return RecoveryObjectV1(
        body=worker,
        identity=_identity_from_published(published, label="worker completion"),
    )


def validate_worker_completion_v1(
    value: object, *, intent: Mapping[str, object],
    intent_identity: Mapping[str, object],
) -> dict[str, object]:
    worker = _mapping(value, label="recovery worker completion")
    _exact_keys(worker, _WORKER_KEYS, label="recovery worker completion")
    _validate_self_hash(
        worker, field="worker_completion_sha256", label="recovery worker completion"
    )
    runtime = _mapping(worker.get("runtime_envelope"), label="worker runtime envelope")
    standard = _mapping(
        worker.get("standard_artifact_identities"), label="standard artifacts"
    )
    _exact_keys(runtime, _RUNTIME_ENVELOPE_KEYS, label="worker runtime envelope")
    _exact_keys(standard, _STANDARD_IDENTITY_KEYS, label="standard artifacts")
    for label, identity in standard.items():
        standard[label] = _identity(identity, label=f"standard {label}")
    if (
        worker.get("schema_version") != WORKER_SCHEMA
        or worker.get("run_id") != intent["run_id"]
        or worker.get("cloud_run_job") != intent["cloud_run_job"]
        or worker.get("recovery_intent_identity") != intent_identity
        or worker.get("recovery_intent_sha256") != intent["recovery_intent_sha256"]
        or worker.get("original_runtime") != intent["original_runtime"]
        or worker.get("recovery_runtime") != intent["recovery_runtime"]
        or worker.get("read_attempt_identity") != intent["read_attempt_identity"]
        or worker.get("fixed_query_job") != intent["fixed_query_job"]
        or standard["attempt"] != intent["read_attempt_identity"]
        or worker.get("query_job_disposition") != "recovered"
        or worker.get("get_job_call_count") != 1
        or worker.get("result_call_count") != 1
        or worker.get("job_submission_count") != 0
        or worker.get("new_job_count") != 0
        or worker.get("one_existing_result_consumed") is not True
        or worker.get("result_job_retry_disabled") is not True
        or any(worker.get(field) is not False for field in (
            "automatic_retry_licensed", "additional_recovery_licensed",
            "historical_retune_licensed", "graph_mutation_licensed",
            "production_change_licensed", "decision_authority",
        ))
    ):
        _fail("recovery worker completion differs")
    _iso_text(worker.get("completed_at"), label="worker completion")
    return worker


def _recover_argv(intent: Mapping[str, object], identity: Mapping[str, object]) -> list[str]:
    original = _mapping(intent["original_runtime"], label="original runtime")
    recovery = _mapping(intent["recovery_runtime"], label="recovery runtime")
    result = [
        "/opt/nfl-predictions/scripts/recover_corpus_r6_full_union_outcome_supply_v1.py",
        "recover", "--execute", f"--project={intent['project']}",
        f"--run-id={intent['run_id']}", f"--job={intent['cloud_run_job']}",
        f"--original-code-sha={original['code_sha']}",
        f"--original-image={original['image']}",
        f"--recovery-code-sha={recovery['code_sha']}",
        f"--recovery-image={recovery['image']}",
    ]
    for suffix in ("uri", "generation", "sha256", "bytes"):
        result.append(f"--recovery-intent-{suffix}={identity[suffix]}")
    return result


def _terminal_success(
    value: Mapping[str, object], *, intent: Mapping[str, object],
    intent_identity: Mapping[str, object], worker: Mapping[str, object],
    stage_token: str,
) -> dict[str, object]:
    metadata = _mapping(value.get("metadata"), label="recovery execution metadata")
    spec = _mapping(value.get("spec"), label="recovery execution spec")
    status = _mapping(value.get("status"), label="recovery execution status")
    template = _mapping(spec.get("template"), label="recovery execution template")
    task = _mapping(template.get("spec"), label="recovery execution task")
    containers = task.get("containers")
    conditions = status.get("conditions")
    labels = _mapping(metadata.get("labels"), label="recovery execution labels")
    if (
        not isinstance(containers, list) or len(containers) != 1
        or not isinstance(containers[0], Mapping)
        or not isinstance(conditions, list)
    ):
        _fail("recovery terminal execution envelope differs")
    completed = [
        item for item in conditions
        if isinstance(item, Mapping) and item.get("type") == "Completed"
    ]
    container = dict(containers[0])
    raw_env = container.get("env", [])
    if not isinstance(raw_env, list) or not all(isinstance(item, Mapping) for item in raw_env):
        _fail("recovery execution environment differs")
    recovery = _mapping(intent["recovery_runtime"], label="recovery runtime")
    expected_env = sorted([
        {"name": RECOVERY_ENABLED_ENV, "value": "1"},
        {"name": RECOVERY_STAGE_TOKEN_ENV, "value": stage_token},
        {"name": RECOVERY_CODE_ENV, "value": recovery["code_sha"]},
        {"name": RECOVERY_IMAGE_ENV, "value": recovery["image"]},
    ], key=lambda item: item["name"])
    actual_env = sorted([dict(item) for item in raw_env], key=lambda item: str(item.get("name")))
    name = str(metadata.get("name", "")).rsplit("/", 1)[-1]
    projection = {
        "execution_name": name,
        "execution_uid": str(metadata.get("uid", "")),
        "completed_status": completed[0].get("status") if len(completed) == 1 else None,
        "succeeded_count": status.get("succeededCount", 0),
        "failed_count": status.get("failedCount", 0),
        "running_count": status.get("runningCount", 0),
        "completion_time": status.get("completionTime"),
        "max_retries": task.get("maxRetries"),
    }
    runtime = _mapping(worker["runtime_envelope"], label="worker runtime")
    if (
        name != runtime["cloud_run_execution"]
        or not name.startswith(str(intent["cloud_run_job"]) + "-")
        or labels.get("run.googleapis.com/job") != intent["cloud_run_job"]
        or projection["execution_uid"] == ""
        or projection["completed_status"] != "True"
        or projection["succeeded_count"] != 1
        or projection["failed_count"] != 0
        or projection["running_count"] != 0
        or projection["completion_time"] in (None, "")
        or projection["max_retries"] != 0
        or spec.get("taskCount") != 1 or spec.get("parallelism") != 1
        or str(task.get("timeoutSeconds")) != "28800"
        or task.get("serviceAccountName") != recovery["service_account"]
        or container.get("image") != recovery["image"]
        or container.get("command") != ["python"]
        or container.get("args") != _recover_argv(intent, intent_identity)
        or actual_env != expected_env
        or (container.get("volumeMounts", []) or []) != []
        or (task.get("volumes", []) or []) != []
        or (task.get("vpcAccess", {}) or {}) != {}
        or container.get("resources", {}).get("limits")
        != {"cpu": "8", "memory": "32Gi"}
    ):
        _fail("recovery terminal execution envelope differs")
    _iso_text(projection["completion_time"], label="recovery completion")
    return projection


def finalize_recovery_v1(
    *, project: str, region: str, run_id: str, job: str,
    original_code_sha: str, original_image: str,
    recovery_code_sha: str, recovery_image: str, service_account: str,
    recovery_stage_token: str, recovery_intent_identity: Mapping[str, object],
    recovery_terminal_execution_path: Path, storage_client: object,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> RecoveryObjectV1:
    if project != PROJECT or region != REGION:
        _fail("recovery finalizer location differs")
    store = GenerationPinnedGCSV1(storage_client)
    retained = _load_intent(store, recovery_intent_identity)
    intent = dict(retained.body)
    original = _mapping(intent["original_runtime"], label="original runtime")
    recovery = _mapping(intent["recovery_runtime"], label="recovery runtime")
    if (
        intent["run_id"] != run_id or intent["cloud_run_job"] != job
        or original != _runtime(
            code_sha=original_code_sha, image=original_image,
            service_account=service_account, label="original runtime",
        )
        or recovery != _runtime(
            code_sha=recovery_code_sha, image=recovery_image,
            service_account=service_account, label="recovery runtime",
        )
        or _SHA256.fullmatch(recovery_stage_token) is None
    ):
        _fail("recovery finalizer runtime binding differs")
    outputs = _mapping(intent["output_uris"], label="recovery output URIs")
    worker_object = store.resolve_required(str(outputs["worker_completion"]))
    worker_identity = _identity_from_published(worker_object, label="worker completion")
    worker = validate_worker_completion_v1(
        _json(worker_object.reopened_raw, label="worker completion"),
        intent=intent, intent_identity=retained.identity,
    )
    standard = _mapping(
        worker["standard_artifact_identities"], label="standard artifacts"
    )
    expected_standard_uris = {
        "attempt": str(intent["read_attempt_identity"]["uri"]),  # type: ignore[index]
        "query_evidence": str(outputs["query_evidence"]),
        "realized_source": str(outputs["realized_source"]),
        "outcome_snapshot": str(outputs["outcome_snapshot"]),
        "completion": str(outputs["completion"]),
    }
    for label, expected_uri in expected_standard_uris.items():
        identity = _identity(standard.get(label), label=f"standard {label}")
        if identity["uri"] != expected_uri:
            _fail(f"standard {label} URI differs")
        store.require_identity(identity, label=f"standard {label}")
    terminal, terminal_raw = _read_local_object(
        recovery_terminal_execution_path, label="recovery terminal execution"
    )
    projection = _terminal_success(
        terminal, intent=intent, intent_identity=retained.identity,
        worker=worker, stage_token=recovery_stage_token,
    )
    existing = store.resolve_known(str(outputs["recovery_receipt"]))
    existing_body: dict[str, object] | None = None
    if existing is not None:
        existing_body = validate_recovery_receipt_v1(
            _json(existing.reopened_raw, label="recovery receipt"), intent=intent,
            intent_identity=retained.identity,
        )
    closed_at = (
        str(existing_body["closed_at"])
        if existing_body is not None
        else _iso(clock(), label="recovery receipt closure")
    )
    receipt = _self_hashed({
        "schema_version": RECEIPT_SCHEMA,
        "closed_at": closed_at,
        "run_id": run_id,
        "cloud_run_job": job,
        "recovery_intent_identity": dict(retained.identity),
        "recovery_intent_sha256": intent["recovery_intent_sha256"],
        "worker_completion_identity": worker_identity,
        "worker_completion_sha256": worker["worker_completion_sha256"],
        "original_runtime": original,
        "recovery_runtime": recovery,
        "original_supply_failure": intent["original_supply_failure"],
        "recovery_terminal_execution_measurement": _measurement(terminal_raw),
        "recovery_terminal_projection": projection,
        "runtime_envelope": worker["runtime_envelope"],
        "read_attempt_identity": intent["read_attempt_identity"],
        "fixed_query_job": intent["fixed_query_job"],
        "standard_artifact_identities": worker["standard_artifact_identities"],
        "query_job_disposition": "recovered",
        "get_job_call_count": 1,
        "result_call_count": 1,
        "job_submission_count": 0,
        "new_job_count": 0,
        "same_fixed_job_recovered": True,
        "recovery_closed": True,
        "automatic_retry_licensed": False,
        "additional_recovery_licensed": False,
        "historical_retune_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }, field="recovery_receipt_sha256")
    validate_recovery_receipt_v1(
        receipt, intent=intent, intent_identity=retained.identity
    )
    if existing is not None:
        assert existing_body is not None
        if existing_body != receipt:
            _fail("existing recovery receipt differs from exact replay")
        return RecoveryObjectV1(
            body=existing_body,
            identity=_identity_from_published(existing, label="recovery receipt"),
        )
    published = store.publish(str(outputs["recovery_receipt"]), _canonical(receipt))
    return RecoveryObjectV1(
        body=receipt,
        identity=_identity_from_published(published, label="recovery receipt"),
    )


def validate_recovery_receipt_v1(
    value: object, *, intent: Mapping[str, object],
    intent_identity: Mapping[str, object],
) -> dict[str, object]:
    receipt = _mapping(value, label="recovery receipt")
    _exact_keys(receipt, _RECEIPT_KEYS, label="recovery receipt")
    _validate_self_hash(receipt, field="recovery_receipt_sha256", label="recovery receipt")
    projection = _mapping(
        receipt.get("recovery_terminal_projection"), label="recovery terminal projection"
    )
    measurement = _mapping(
        receipt.get("recovery_terminal_execution_measurement"),
        label="recovery terminal measurement",
    )
    runtime = _mapping(receipt.get("runtime_envelope"), label="receipt runtime envelope")
    standard = _mapping(
        receipt.get("standard_artifact_identities"), label="receipt standard artifacts"
    )
    _exact_keys(projection, _TERMINAL_PROJECTION_KEYS, label="recovery terminal projection")
    _exact_keys(measurement, _MEASUREMENT_KEYS, label="recovery terminal measurement")
    _exact_keys(runtime, _RUNTIME_ENVELOPE_KEYS, label="receipt runtime envelope")
    _exact_keys(standard, _STANDARD_IDENTITY_KEYS, label="receipt standard artifacts")
    for label, identity in standard.items():
        standard[label] = _identity(identity, label=f"receipt standard {label}")
    recovery = _mapping(intent["recovery_runtime"], label="recovery runtime")
    if (
        receipt.get("schema_version") != RECEIPT_SCHEMA
        or receipt.get("run_id") != intent["run_id"]
        or receipt.get("cloud_run_job") != intent["cloud_run_job"]
        or receipt.get("recovery_intent_identity") != intent_identity
        or receipt.get("recovery_intent_sha256") != intent["recovery_intent_sha256"]
        or receipt.get("original_runtime") != intent["original_runtime"]
        or receipt.get("recovery_runtime") != intent["recovery_runtime"]
        or receipt.get("original_supply_failure") != intent["original_supply_failure"]
        or receipt.get("read_attempt_identity") != intent["read_attempt_identity"]
        or receipt.get("fixed_query_job") != intent["fixed_query_job"]
        or standard["attempt"] != intent["read_attempt_identity"]
        or runtime.get("cloud_run_job") != intent["cloud_run_job"]
        or runtime.get("cloud_run_execution") != projection.get("execution_name")
        or runtime.get("cloud_run_task_index") != "0"
        or runtime.get("cloud_run_task_count") != "1"
        or runtime.get("cloud_run_task_attempt") != "0"
        or runtime.get("recovery_code_sha") != recovery["code_sha"]
        or runtime.get("recovery_image") != recovery["image"]
        or type(runtime.get("recovery_stage_token")) is not str
        or _SHA256.fullmatch(str(runtime.get("recovery_stage_token"))) is None
        or receipt.get("query_job_disposition") != "recovered"
        or receipt.get("get_job_call_count") != 1
        or receipt.get("result_call_count") != 1
        or receipt.get("job_submission_count") != 0
        or receipt.get("new_job_count") != 0
        or receipt.get("same_fixed_job_recovered") is not True
        or receipt.get("recovery_closed") is not True
        or projection.get("completed_status") != "True"
        or projection.get("succeeded_count") != 1
        or projection.get("failed_count") != 0
        or projection.get("running_count") != 0
        or projection.get("max_retries") != 0
        or any(receipt.get(field) is not False for field in (
            "automatic_retry_licensed", "additional_recovery_licensed",
            "historical_retune_licensed", "graph_mutation_licensed",
            "production_change_licensed", "decision_authority",
        ))
    ):
        _fail("recovery receipt contract differs")
    _identity(receipt.get("worker_completion_identity"), label="worker completion")
    _digest(receipt.get("worker_completion_sha256"), label="worker completion self hash")
    _iso_text(receipt.get("closed_at"), label="recovery receipt closure")
    return receipt


def _add_identity(parser: argparse.ArgumentParser, prefix: str) -> None:
    parser.add_argument(f"--{prefix}-uri", required=True)
    parser.add_argument(f"--{prefix}-generation", required=True)
    parser.add_argument(f"--{prefix}-sha256", required=True)
    parser.add_argument(f"--{prefix}-bytes", type=int, required=True)


def _arg_identity(args: argparse.Namespace, prefix: str) -> dict[str, object]:
    field = prefix.replace("-", "_")
    return _identity({
        "uri": getattr(args, f"{field}_uri"),
        "generation": getattr(args, f"{field}_generation"),
        "sha256": getattr(args, f"{field}_sha256"),
        "bytes": getattr(args, f"{field}_bytes"),
    }, label=prefix)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_subparsers(dest="operation", required=True)

    def runtime(name: str) -> argparse.ArgumentParser:
        child = operations.add_parser(name)
        child.add_argument("--execute", action="store_true")
        child.add_argument("--project", default=PROJECT)
        child.add_argument("--region", default=REGION)
        child.add_argument("--run-id", required=True)
        child.add_argument("--job", required=True)
        child.add_argument("--original-code-sha", required=True)
        child.add_argument("--original-image", required=True)
        child.add_argument("--recovery-code-sha", required=True)
        child.add_argument("--recovery-image", required=True)
        return child

    prepare = runtime("prepare")
    prepare.add_argument("--service-account", required=True)
    prepare.add_argument("--original-launch-intent", type=Path, required=True)
    prepare.add_argument("--original-terminal-execution", type=Path, required=True)
    for prefix in (
        "panel-freeze", "outcome-key-projection", "actual-root-smoke",
        "query-compile", "expected-lease", "read-attempt",
    ):
        _add_identity(prepare, prefix)
    prepare.add_argument("--snapshot-module-sha256", required=True)
    prepare.add_argument("--snapshot-cli-sha256", required=True)
    prepare.add_argument("--snapshot-test-sha256", required=True)
    prepare.add_argument("--snapshot-cli-test-sha256", required=True)

    recover = runtime("recover")
    for prefix in ("recovery-intent",):
        _add_identity(recover, prefix)

    finalize = runtime("finalize")
    finalize.add_argument("--service-account", required=True)
    finalize.add_argument("--recovery-stage-token", required=True)
    finalize.add_argument("--recovery-terminal-execution", type=Path, required=True)
    _add_identity(finalize, "recovery-intent")
    return parser


def _summary(value: RecoveryObjectV1, *, status: str) -> dict[str, object]:
    return {
        "schema_version": "r6-full-union-outcome-supply-recovery-cli/v1",
        "status": status,
        "object_identity": dict(value.identity),
        "run_id": value.body["run_id"],
        "cloud_run_job": value.body["cloud_run_job"],
        "outcome_rows_in_stdout": False,
        "job_submission_count": 0,
        "new_job_count": 0,
        "automatic_retry_licensed": False,
        "decision_authority": False,
    }


def main(
    argv: Sequence[str] | None = None, *, environ: Mapping[str, str] | None = None,
    storage_client: object | None = None,
    bq_client_factory: Callable[[], object] | None = None,
) -> int:
    args = _parser().parse_args(argv)
    if args.execute is not True:
        _fail("--execute is required explicitly")
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client(project=PROJECT)
    if bq_client_factory is None:
        def bq_client_factory() -> object:
            from google.cloud import bigquery

            return bigquery.Client(project=PROJECT)
    common = {
        "project": args.project,
        "run_id": args.run_id,
        "job": args.job,
        "original_code_sha": args.original_code_sha,
        "original_image": args.original_image,
        "recovery_code_sha": args.recovery_code_sha,
        "recovery_image": args.recovery_image,
    }
    if args.operation == "prepare":
        value = prepare_recovery_intent_v1(
            **common, region=args.region, service_account=args.service_account,
            original_launch_intent_path=args.original_launch_intent,
            original_terminal_execution_path=args.original_terminal_execution,
            panel_freeze_identity=_arg_identity(args, "panel-freeze"),
            outcome_key_projection_identity=_arg_identity(args, "outcome-key-projection"),
            actual_root_smoke_receipt_identity=_arg_identity(args, "actual-root-smoke"),
            query_compile_receipt_identity=_arg_identity(args, "query-compile"),
            expected_lease_identity=_arg_identity(args, "expected-lease"),
            read_attempt_identity=_arg_identity(args, "read-attempt"),
            snapshot_code_identities={
                "snapshot_module_sha256": args.snapshot_module_sha256,
                "snapshot_cli_sha256": args.snapshot_cli_sha256,
                "snapshot_test_sha256": args.snapshot_test_sha256,
                "snapshot_cli_test_sha256": args.snapshot_cli_test_sha256,
            },
            storage_client=storage_client, bq_client_factory=bq_client_factory,
        )
        status = "R6_FULL_UNION_RECOVERY_INTENT_CLOSED"
    elif args.operation == "recover":
        value = recover_supply_v1(
            **common,
            recovery_stage_token=str((os.environ if environ is None else environ).get(
                RECOVERY_STAGE_TOKEN_ENV, ""
            )),
            recovery_intent_identity=_arg_identity(args, "recovery-intent"),
            environ=os.environ if environ is None else environ,
            storage_client=storage_client, bq_client_factory=bq_client_factory,
        )
        status = "R6_FULL_UNION_FIXED_JOB_RECOVERED"
    elif args.operation == "finalize":
        value = finalize_recovery_v1(
            **common, region=args.region, service_account=args.service_account,
            recovery_stage_token=args.recovery_stage_token,
            recovery_intent_identity=_arg_identity(args, "recovery-intent"),
            recovery_terminal_execution_path=args.recovery_terminal_execution,
            storage_client=storage_client,
        )
        status = "R6_FULL_UNION_RECOVERY_CLOSED"
    else:  # pragma: no cover - argparse owns the operation domain
        raise AssertionError("unknown recovery operation")
    print(_canonical(_summary(value, status=status)).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (R6FullUnionRecoveryV1Error, supply.CorpusR6FullUnionOutcomeSupplyV1Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
