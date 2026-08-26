#!/usr/bin/env python3
"""Create/release the durable single-active historical-outcome lease."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import storage

from run_cbwu_seed_order_audit import _parse_gcs, _upload_create_only


PROJECT = "nfl-predictions-503414"
LEASE_URI = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    "historical-outcome-active-v1.json"
)
CORE_OUTCOME_PREFIX = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-core-v1-realized"
)
CORE_STRICT_COMPLETION_SCHEMA = (
    "core-v1-historical-outcome-strict-completion/v1"
)
CORE_STRICT_DISPOSITION = "core-v1-outcome-snapshot-closed"
R6_OUTCOME_PREFIX = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-full-union-realized"
)
R6_STRICT_COMPLETION_SCHEMA = (
    "r6-full-union-historical-outcome-strict-completion/v1"
)
R6_STRICT_DISPOSITION = "r6-full-union-realized-grade-closed"
R6_DEFAULT_COMPUTE_SERVICE_ACCOUNT = (
    "817589974517-compute@developer.gserviceaccount.com"
)
_R6_PROJECT_SERVICE_ACCOUNT = re.compile(
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]@"
    r"nfl-predictions-503414\.iam\.gserviceaccount\.com"
)
_CORE_STRICT_COMPLETION_KEYS = frozenset({
    "schema_version",
    "run_id",
    "uses_realized_outcomes",
    "disposition",
    "completion_uri",
    "completion_generation",
    "completion_sha256",
    "completion_bytes",
    "completion_self_sha256",
    "attempt_uri",
    "attempt_generation",
    "attempt_sha256",
    "attempt_bytes",
    "historical_outcome_lease_uri",
    "historical_outcome_lease_generation",
    "historical_outcome_lease_sha256",
    "historical_outcome_lease_bytes",
    "one_historical_outcome_read",
    "historical_outcome_lease_release_required",
})
_LEASE_BODY_KEYS = frozenset({
    "version", "run_id", "job", "code_sha", "image", "acquired_at",
})
_R6_STRICT_COMPLETION_KEYS = frozenset({
    "schema_version", "run_id", "job", "execution", "code_sha", "image",
    "service_account", "grade_stage_token",
    "uses_realized_outcomes", "disposition",
    "supply_completion_uri", "supply_completion_generation",
    "supply_completion_sha256", "supply_completion_bytes",
    "supply_completion_self_sha256",
    "attempt_uri", "attempt_generation", "attempt_sha256", "attempt_bytes",
    "query_evidence_uri", "query_evidence_generation",
    "query_evidence_sha256", "query_evidence_bytes",
    "grade_completion_uri", "grade_completion_generation",
    "grade_completion_sha256", "grade_completion_bytes",
    "grade_completion_self_sha256",
    "persisted_grade_root_uri", "persisted_grade_root_generation",
    "persisted_grade_root_sha256", "persisted_grade_root_bytes",
    "persisted_grade_root_self_sha256",
    "panel_freeze_uri", "panel_freeze_generation", "panel_freeze_sha256",
    "panel_freeze_bytes", "actual_root_smoke_receipt_uri",
    "actual_root_smoke_receipt_generation",
    "actual_root_smoke_receipt_sha256", "actual_root_smoke_receipt_bytes",
    "outcome_key_projection_uri", "outcome_key_projection_generation",
    "outcome_key_projection_sha256", "outcome_key_projection_bytes",
    "realized_source_uri", "realized_source_generation",
    "realized_source_sha256", "realized_source_bytes",
    "outcome_snapshot_uri", "outcome_snapshot_generation",
    "outcome_snapshot_sha256", "outcome_snapshot_bytes",
    "snapshot_module_sha256", "snapshot_cli_sha256",
    "snapshot_test_sha256", "snapshot_cli_test_sha256",
    "historical_outcome_lease_uri",
    "historical_outcome_lease_generation",
    "historical_outcome_lease_sha256", "historical_outcome_lease_bytes",
    "one_historical_outcome_read", "one_exact_query_job",
    "canonical_persisted_grade_replay_complete",
    "terminal_execution_envelope_validation_required",
    "historical_outcome_lease_release_required",
})


def _valid_r6_service_account(value: object) -> bool:
    return type(value) is str and (
        value == R6_DEFAULT_COMPUTE_SERVICE_ACCOUNT
        or _R6_PROJECT_SERVICE_ACCOUNT.fullmatch(value) is not None
    )


def acquire(
    *, run_id: str, job: str, code_sha: str, image: str, receipt_path: Path,
) -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,80}", run_id) or \
            not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,62}", job) or \
            not re.fullmatch(r"[0-9a-f]{40}", code_sha) or \
            not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image) or \
            receipt_path.exists():
        raise RuntimeError("historical-outcome lease identity differs")
    client = storage.Client(project=PROJECT)
    payload = {
        "version": "historical-outcome-active-v1",
        "run_id": run_id,
        "job": job,
        "code_sha": code_sha,
        "image": image,
        "acquired_at": datetime.now(timezone.utc).isoformat(),
    }
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    try:
        upload = _upload_create_only(client, LEASE_URI, raw)
    except PreconditionFailed as exc:
        raise RuntimeError("another historical-outcome experiment holds the lease") from exc
    receipt = {"lease": payload, "object": upload}
    _write_create_or_equal(
        receipt_path,
        (
            json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode(),
    )
    return receipt


def _validate_requested_lease_identity(
    *, run_id: object, job: object, code_sha: object, image: object,
) -> tuple[str, str, str, str]:
    retained = tuple(str(value) for value in (run_id, job, code_sha, image))
    if (
        re.fullmatch(r"[a-z0-9][a-z0-9-]{2,80}", retained[0]) is None
        or re.fullmatch(r"[a-z0-9][a-z0-9-]{2,62}", retained[1]) is None
        or re.fullmatch(r"[0-9a-f]{40}", retained[2]) is None
        or re.fullmatch(r".+@sha256:[0-9a-f]{64}", retained[3]) is None
    ):
        raise RuntimeError("historical-outcome lease identity differs")
    return retained  # type: ignore[return-value]


def resolve(
    *, run_id: str, job: str, code_sha: str, image: str,
    receipt_path: Path, storage_client=None,
) -> dict[str, object]:
    """Recover an ambiguously acquired lease by exact current identity.

    Resolution is deliberately known-name only.  It pins the current lease
    generation, reopens those exact bytes, and succeeds only when the live
    owner is the complete requested run/job/code/image tuple.  The local
    receipt is then created atomically or accepted only when byte-equal.
    """
    retained_run, retained_job, retained_code, retained_image = (
        _validate_requested_lease_identity(
            run_id=run_id, job=job, code_sha=code_sha, image=image,
        )
    )
    client = storage_client or storage.Client(project=PROJECT)
    identity, raw = _resolve_current_exact(
        client, LEASE_URI, label="historical-outcome active lease"
    )
    try:
        lease = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("historical-outcome active lease JSON differs") from exc
    if not isinstance(lease, Mapping) or set(lease) != _LEASE_BODY_KEYS:
        raise RuntimeError("historical-outcome active lease body differs")
    acquired_at = lease.get("acquired_at")
    try:
        parsed_acquired = datetime.fromisoformat(str(acquired_at))
    except ValueError as exc:
        raise RuntimeError("historical-outcome active lease time differs") from exc
    if (
        lease.get("version") != "historical-outcome-active-v1"
        or lease.get("run_id") != retained_run
        or lease.get("job") != retained_job
        or lease.get("code_sha") != retained_code
        or lease.get("image") != retained_image
        or type(acquired_at) is not str
        or parsed_acquired.tzinfo is None
        or parsed_acquired.utcoffset() is None
    ):
        raise RuntimeError(
            "current historical-outcome lease is not the exact requested owner"
        )
    receipt: dict[str, object] = {
        "lease": dict(lease),
        "object": {**identity, "create_only": True},
    }
    receipt_raw = (
        json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    _write_create_or_equal(receipt_path, receipt_raw)
    return receipt


def _lease_receipt_coordinates(
    receipt: object,
) -> tuple[dict[str, object], dict[str, object]]:
    if not isinstance(receipt, Mapping):
        raise RuntimeError("historical-outcome lease receipt differs")
    lease = receipt.get("lease", {})
    expected_object = receipt.get("object", {})
    if set(receipt) != {"lease", "object"} or \
            not isinstance(lease, Mapping) or \
            not isinstance(expected_object, Mapping) or \
            set(expected_object) != {
                "uri", "generation", "sha256", "bytes", "create_only",
            } or \
            lease.get("version") != "historical-outcome-active-v1" or \
            expected_object.get("uri") != LEASE_URI or \
            expected_object.get("create_only") is not True or \
            not isinstance(expected_object.get("generation"), str) or \
            re.fullmatch(r"[1-9][0-9]*", expected_object["generation"]) is None or \
            type(expected_object.get("bytes")) is not int or \
            expected_object["bytes"] < 1 or \
            not re.fullmatch(r"[0-9a-f]{64}", str(expected_object.get("sha256", ""))):
        raise RuntimeError("historical-outcome lease receipt differs")
    return dict(lease), dict(expected_object)


def _verified_lease_blob(receipt: dict, *, storage_client=None):
    """Validate a receipt and return its live, byte-verified lease blob."""
    lease, expected_object = _lease_receipt_coordinates(receipt)
    client = storage_client or storage.Client(project=PROJECT)
    bucket, name = _parse_gcs(LEASE_URI)
    blob = client.bucket(bucket).blob(
        name, generation=int(expected_object["generation"]))
    raw = blob.download_as_bytes()
    if len(raw) != expected_object["bytes"] or \
            sha256(raw).hexdigest() != expected_object["sha256"] or \
            json.loads(raw) != lease:
        raise RuntimeError("historical-outcome active lease changed")
    return client, lease, expected_object, blob, raw


def _object_identity(value: object, *, label: str) -> dict[str, object]:
    try:
        from nfl_dfs.research import corpus_parametric_batch as batch

        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise RuntimeError(f"{label} differs") from exc


def _canonical_json_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        from nfl_dfs.research import corpus_parametric_batch as batch

        value = batch.parse_canonical_json_bytes(raw, label=label)
    except Exception as exc:
        raise RuntimeError(f"{label} differs") from exc
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} must be one JSON object")
    return dict(value)


def _resolve_current_exact(client, uri: str, *, label: str):
    """Resolve one known GCS name, then reopen exactly that generation."""
    bucket_name, name = _parse_gcs(uri)
    try:
        current = client.bucket(bucket_name).blob(name)
        current.reload()
        generation_text = str(current.generation)
        if not generation_text.isdigit() or generation_text.startswith("0"):
            raise RuntimeError(f"{label} generation differs")
        generation = int(generation_text)
        pinned = client.bucket(bucket_name).blob(name, generation=generation)
        pinned.reload(if_generation_match=generation)
        raw = pinned.download_as_bytes(if_generation_match=generation)
    except Exception as exc:
        raise RuntimeError(f"{label} generation-pinned read failed") from exc
    if type(raw) is not bytes or not raw:
        raise RuntimeError(f"{label} is empty")
    identity = {
        "uri": uri,
        "generation": generation_text,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    return _object_identity(identity, label=f"{label} identity"), raw


def _read_identity_exact(client, value: object, *, label: str) -> bytes:
    """Read only the supplied generation and verify its complete identity."""
    identity = _object_identity(value, label=f"{label} identity")
    bucket_name, name = _parse_gcs(str(identity["uri"]))
    generation = int(str(identity["generation"]))
    try:
        blob = client.bucket(bucket_name).blob(name, generation=generation)
        blob.reload(if_generation_match=generation)
        raw = blob.download_as_bytes(if_generation_match=generation)
    except Exception as exc:
        raise RuntimeError(f"{label} exact read failed") from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        raise RuntimeError(f"{label} exact bytes differ")
    return raw


def _resolve_referenced_current(
    client, value: object, *, expected_uri: str, label: str,
) -> tuple[dict[str, object], dict[str, object], bytes, datetime]:
    expected = _object_identity(value, label=f"{label} retained identity")
    if expected["uri"] != expected_uri:
        raise RuntimeError(f"{label} URI differs")
    observed, raw = _resolve_current_exact(client, expected_uri, label=label)
    if observed != expected:
        raise RuntimeError(f"{label} current object changed")
    bucket_name, name = _parse_gcs(expected_uri)
    generation = int(str(expected["generation"]))
    try:
        pinned = client.bucket(bucket_name).blob(name, generation=generation)
        pinned.reload(if_generation_match=generation)
        created_at = pinned.time_created
    except Exception as exc:
        raise RuntimeError(f"{label} pinned creation time read failed") from exc
    if (
        not isinstance(created_at, datetime)
        or created_at.tzinfo is None
        or created_at.utcoffset() is None
    ):
        raise RuntimeError(f"{label} pinned creation time differs")
    return (
        expected,
        _canonical_json_object(raw, label=label),
        raw,
        created_at.astimezone(timezone.utc),
    )


def _validate_core_completion_evidence(
    *, client, raw: bytes, identity: Mapping[str, object],
    lease: Mapping[str, object], lease_object: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """Validate a Core completion and its exact attempt-to-lease binding."""
    from nfl_dfs.research import corpus_core_v1_outcome_supply as core

    completion = _canonical_json_object(raw, label="Core v1 outcome completion")
    expected_uri = f"{CORE_OUTCOME_PREFIX}/{lease['run_id']}/completion.json"
    retained_identity = _object_identity(
        identity, label="Core v1 outcome completion identity"
    )
    if (
        retained_identity["uri"] != expected_uri
        or completion.get("run_id") != lease.get("run_id")
        or completion.get("one_historical_outcome_read") is not True
        or completion.get("historical_outcome_lease_release_required") is not True
        or completion.get("lease_release_owner") != core.LEASE_RELEASE_OWNER
    ):
        raise RuntimeError("Core v1 outcome completion release law differs")
    identity_fields = (
        "catalog_identity",
        "attempt_identity",
        "player_source_identity",
        "outcome_snapshot_identity",
    )
    normalized = {
        field: _object_identity(
            completion.get(field), label=f"Core v1 completion {field}"
        )
        for field in identity_fields
    }
    expected_attempt_uri = (
        f"{CORE_OUTCOME_PREFIX}/{lease['run_id']}/read-attempt.json"
    )
    if normalized["attempt_identity"]["uri"] != expected_attempt_uri:
        raise RuntimeError("Core v1 outcome read attempt URI differs")
    catalog_sha = completion.get("catalog_sha256")
    outcome_key_count = completion.get("outcome_key_count")
    if (
        not isinstance(catalog_sha, str)
        or re.fullmatch(r"[0-9a-f]{64}", catalog_sha) is None
        or type(outcome_key_count) is not int
        or outcome_key_count < 1
    ):
        raise RuntimeError("Core v1 outcome completion scalar law differs")
    config = core.CoreOutcomeSupplyConfig(
        run_id=str(lease["run_id"]),
        job=str(lease["job"]),
        code_sha=str(lease["code_sha"]),
        image=str(lease["image"]),
        enabled=True,
    )
    try:
        validated = core.validate_core_outcome_completion(
            completion,
            config=config,
            catalog_identity=normalized["catalog_identity"],
            catalog_sha256=catalog_sha,
            attempt_identity=normalized["attempt_identity"],
            player_source_identity=normalized["player_source_identity"],
            outcome_snapshot_identity=normalized["outcome_snapshot_identity"],
            outcome_key_count=outcome_key_count,
        )
    except Exception as exc:
        raise RuntimeError("Core v1 outcome completion validation failed") from exc
    if validated != completion:
        raise RuntimeError("Core v1 outcome completion exact replay differs")

    attempt_identity, attempt_raw = _resolve_current_exact(
        client,
        str(normalized["attempt_identity"]["uri"]),
        label="Core v1 outcome read attempt",
    )
    if attempt_identity != normalized["attempt_identity"]:
        raise RuntimeError("Core v1 outcome read attempt identity differs")
    attempt = _canonical_json_object(
        attempt_raw, label="Core v1 outcome read attempt"
    )
    attempt_hash = attempt.get("attempt_sha256")
    attempt_body = dict(attempt)
    attempt_body.pop("attempt_sha256", None)
    expected_lease_receipt = dict(lease_object)
    historical_lease = attempt.get("historical_outcome_lease")
    if (
        set(attempt) != core._ATTEMPT_KEYS  # noqa: SLF001
        or attempt.get("schema_version") != core.ATTEMPT_SCHEMA
        or not isinstance(historical_lease, Mapping)
        or set(historical_lease) != {"body", "object_receipt"}
        or historical_lease.get("body") != dict(lease)
        or historical_lease.get("object_receipt") != expected_lease_receipt
        or attempt.get("run_id") != lease.get("run_id")
        or attempt.get("catalog_identity") != normalized["catalog_identity"]
        or attempt.get("catalog_sha256") != catalog_sha
        or attempt.get("outcome_key_count") != outcome_key_count
        or attempt.get("uses_realized_outcomes_at_creation") is not False
        or attempt.get("attempt_precedes_query") is not True
        or any(attempt.get(field) is not False for field in (
            "historical_retry_licensed",
            "historical_retune_licensed",
            "graph_mutation_licensed",
            "production_change_licensed",
            "decision_authority",
        ))
        or not isinstance(attempt_hash, str)
        or attempt_hash != core.canonical_sha256(attempt_body)
    ):
        raise RuntimeError("Core v1 outcome attempt-to-lease binding differs")
    return completion, attempt_identity


def _fsync_local_evidence(path: Path) -> None:
    file_descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(file_descriptor)
    finally:
        os.close(file_descriptor)
    directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def _write_create_or_equal(path: Path, raw: bytes) -> None:
    if type(raw) is not bytes or not raw:
        raise RuntimeError("strict completion bytes differ")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing_stat = path.lstat()
    except FileNotFoundError:
        existing_stat = None
    if existing_stat is not None:
        if not stat.S_ISREG(existing_stat.st_mode) or path.read_bytes() != raw:
            raise RuntimeError("strict completion local evidence differs")
        _fsync_local_evidence(path)
        return
    descriptor, temp_name = tempfile.mkstemp(
        prefix=".historical-outcome-completion.", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        try:
            os.link(temp_path, path)
        except FileExistsError:
            existing_stat = path.lstat()
            if not stat.S_ISREG(existing_stat.st_mode) or path.read_bytes() != raw:
                raise RuntimeError("strict completion create/equal race differs")
        _fsync_local_evidence(path)
    finally:
        temp_path.unlink(missing_ok=True)


def _core_strict_rows(
    *, lease: Mapping[str, object], lease_object: Mapping[str, object],
    completion: Mapping[str, object], completion_identity: Mapping[str, object],
    attempt_identity: Mapping[str, object],
) -> dict[str, str]:
    return {
        "schema_version": CORE_STRICT_COMPLETION_SCHEMA,
        "run_id": str(lease["run_id"]),
        "uses_realized_outcomes": "true",
        "disposition": CORE_STRICT_DISPOSITION,
        "completion_uri": str(completion_identity["uri"]),
        "completion_generation": str(completion_identity["generation"]),
        "completion_sha256": str(completion_identity["sha256"]),
        "completion_bytes": str(completion_identity["bytes"]),
        "completion_self_sha256": str(completion["completion_sha256"]),
        "attempt_uri": str(attempt_identity["uri"]),
        "attempt_generation": str(attempt_identity["generation"]),
        "attempt_sha256": str(attempt_identity["sha256"]),
        "attempt_bytes": str(attempt_identity["bytes"]),
        "historical_outcome_lease_uri": str(lease_object["uri"]),
        "historical_outcome_lease_generation": str(lease_object["generation"]),
        "historical_outcome_lease_sha256": str(lease_object["sha256"]),
        "historical_outcome_lease_bytes": str(lease_object["bytes"]),
        "one_historical_outcome_read": "true",
        "historical_outcome_lease_release_required": "true",
    }


def materialize_core_v1_completion(
    *, receipt_path: Path, completion_uri: str, output_path: Path,
    storage_client=None,
) -> dict[str, str]:
    """Create a local strict completion from one exact known Core object."""
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    client, lease, lease_object, _, _ = _verified_lease_blob(
        receipt, storage_client=storage_client
    )
    expected_uri = f"{CORE_OUTCOME_PREFIX}/{lease['run_id']}/completion.json"
    if completion_uri != expected_uri:
        raise RuntimeError("Core v1 outcome completion URI differs")
    completion_identity, raw = _resolve_current_exact(
        client, completion_uri, label="Core v1 outcome completion"
    )
    completion, attempt_identity = _validate_core_completion_evidence(
        client=client,
        raw=raw,
        identity=completion_identity,
        lease=lease,
        lease_object=lease_object,
    )
    rows = _core_strict_rows(
        lease=lease,
        lease_object=lease_object,
        completion=completion,
        completion_identity=completion_identity,
        attempt_identity=attempt_identity,
    )
    raw_rows = "".join(f"{key}={rows[key]}\n" for key in sorted(rows)).encode()
    _write_create_or_equal(output_path, raw_rows)
    return rows


def _validate_r6_supply_evidence(
    *, client, raw: bytes, identity: Mapping[str, object],
    lease: Mapping[str, object], lease_object: Mapping[str, object],
    expected_snapshot_code_identities: Mapping[str, object],
) -> dict[str, object]:
    """Replay the complete R6 supply chain through its one-query evidence."""
    from nfl_dfs.research import (
        corpus_r6_full_union_outcome_snapshot_v1 as outcome,
    )
    from nfl_dfs.research import corpus_r6_full_union_outcome_supply_v1 as supply

    completion = _canonical_json_object(
        raw, label="R6 full-union outcome completion"
    )
    expected_code = {
        field: str(expected_snapshot_code_identities.get(field, ""))
        for field in (
            "snapshot_module_sha256", "snapshot_cli_sha256",
            "snapshot_test_sha256", "snapshot_cli_test_sha256",
        )
    }
    if any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in expected_code.values()):
        raise RuntimeError("R6 full-union independent snapshot code pins differ")
    run_id = str(lease["run_id"])
    output_prefix = f"{R6_OUTCOME_PREFIX}/{run_id}"
    expected_completion_uri = f"{output_prefix}/completion.json"
    retained_completion_identity = _object_identity(
        identity, label="R6 full-union completion identity"
    )
    if (
        retained_completion_identity["uri"] != expected_completion_uri
        or completion.get("run_id") != run_id
    ):
        raise RuntimeError("R6 full-union outcome completion release law differs")

    expected_uris = {
        "projection": f"{output_prefix}/outcome-key-projection.json",
        "smoke": f"{output_prefix}/actual-root-smoke-receipt.json",
        "attempt": f"{output_prefix}/read-attempt.json",
        "query_evidence": f"{output_prefix}/query-evidence.json",
        "source": f"{output_prefix}/realized-source.json",
        "snapshot": f"{output_prefix}/outcome-snapshot.json",
    }
    identity_fields = {
        "projection": "outcome_key_projection_identity",
        "smoke": "actual_root_smoke_receipt_identity",
        "attempt": "attempt_identity",
        "query_evidence": "query_evidence_identity",
        "source": "realized_source_identity",
        "snapshot": "outcome_snapshot_identity",
    }
    objects: dict[str, dict[str, object]] = {}
    identities: dict[str, dict[str, object]] = {}
    created_at: dict[str, datetime] = {}
    for label, field in identity_fields.items():
        retained, body, _, creation_time = _resolve_referenced_current(
            client,
            completion.get(field),
            expected_uri=expected_uris[label],
            label=f"R6 full-union {label}",
        )
        identities[label] = retained
        objects[label] = body
        created_at[label] = creation_time

    read_exact = lambda value: _read_identity_exact(  # noqa: E731
        client, value, label="R6 full-union replay object"
    )
    try:
        projection, projection_identity, outcome_keys = (
            outcome.validate_outcome_key_projection_v1(
                objects["projection"],
                identity=identities["projection"],
                read_exact=read_exact,
            )
        )
        smoke = objects["smoke"]
        smoke_receipt, smoke_identity = (
            outcome.validate_actual_root_smoke_receipt_v1(
                smoke,
                identity=identities["smoke"],
                expected_panel_freeze_identity=completion.get(
                    "panel_freeze_identity"
                ),
                outcome_key_projection=projection,
                expected_outcome_key_projection_identity=projection_identity,
                expected_reviewed_source_commit_sha=lease.get("code_sha"),
                expected_runtime_immutable_image=lease.get("image"),
                expected_snapshot_module_sha256=expected_code[
                    "snapshot_module_sha256"
                ],
                expected_snapshot_cli_sha256=expected_code[
                    "snapshot_cli_sha256"
                ],
                expected_snapshot_test_sha256=expected_code[
                    "snapshot_test_sha256"
                ],
                expected_snapshot_cli_test_sha256=expected_code[
                    "snapshot_cli_test_sha256"
                ],
                read_exact=read_exact,
            )
        )
    except Exception as exc:
        raise RuntimeError("R6 full-union projection/smoke replay failed") from exc

    config = supply.FullUnionOutcomeSupplyConfigV1(
        run_id=run_id,
        job=str(lease["job"]),
        code_sha=str(lease["code_sha"]),
        image=str(lease["image"]),
        enabled=True,
    )
    root_sha = str(completion.get("panel_freeze_object_sha256", ""))
    legacy_config = supply._legacy_config(  # noqa: SLF001
        config, panel_freeze_object_sha256=root_sha
    )
    attempt = objects["attempt"]
    expected_lease = {
        "body": dict(lease),
        "object_receipt": dict(lease_object),
    }
    if attempt.get("historical_outcome_lease") != expected_lease:
        raise RuntimeError("R6 full-union attempt-to-lease binding differs")
    try:
        tables = supply._table_receipts(  # noqa: SLF001
            attempt.get("table_receipts_before_query")
        )
        spec, query_contract = supply._query_spec_from_contract(  # noqa: SLF001
            attempt.get("query_contract"),
            config=config,
            legacy_config=legacy_config,
            outcome_keys=outcome_keys,
            panel_freeze_object_sha256=root_sha,
        )
        retained_attempt = supply.validate_outcome_attempt_v1(
            attempt,
            config=config,
            object_uri=expected_uris["attempt"],
            panel_freeze_identity=completion["panel_freeze_identity"],
            projection=projection,
            projection_identity=projection_identity,
            smoke_receipt=smoke_receipt,
            smoke_receipt_identity=smoke_identity,
            query_contract=query_contract,
            table_receipts=tables,
            lease=expected_lease,
        )
        query_evidence, registered_rows, _ = supply.validate_query_evidence_v1(
            objects["query_evidence"],
            config=config,
            object_uri=expected_uris["query_evidence"],
            panel_freeze_identity=completion["panel_freeze_identity"],
            projection=projection,
            projection_identity=projection_identity,
            smoke_receipt=smoke_receipt,
            smoke_receipt_identity=smoke_identity,
            attempt=retained_attempt,
            attempt_identity=identities["attempt"],
            attempt_created_at=created_at["attempt"],
            spec=spec,
            query_contract=query_contract,
            outcome_keys=outcome_keys,
        )
        expected_source = outcome.build_realized_source_from_registered_rows_v1(
            outcome_key_projection=projection,
            outcome_key_projection_identity=projection_identity,
            registered_integer_micro_rows=registered_rows,
            read_exact=read_exact,
        )
        realized_source, realized_source_identity, _ = (
            outcome.validate_realized_source_v1(
                objects["source"],
                identity=identities["source"],
                outcome_key_projection=projection,
                outcome_key_projection_identity=projection_identity,
                read_exact=read_exact,
            )
        )
        outcome_snapshot, outcome_snapshot_identity, _ = (
            outcome.validate_outcome_snapshot_v1(
                objects["snapshot"],
                identity=identities["snapshot"],
                outcome_key_projection=projection,
                outcome_key_projection_identity=projection_identity,
                realized_source=realized_source,
                realized_source_identity=realized_source_identity,
                read_exact=read_exact,
            )
        )
        retained_completion = supply.validate_outcome_completion_v1(
            completion,
            config=config,
            object_uri=expected_completion_uri,
            panel_freeze_identity=completion["panel_freeze_identity"],
            projection=projection,
            projection_identity=projection_identity,
            smoke_receipt=smoke_receipt,
            smoke_receipt_identity=smoke_identity,
            attempt_identity=identities["attempt"],
            query_evidence_identity=identities["query_evidence"],
            realized_source_identity=realized_source_identity,
            outcome_snapshot_identity=outcome_snapshot_identity,
            query_job_id=str(query_evidence["query_job_receipt"]["job_id"]),
        )
    except Exception as exc:
        raise RuntimeError("R6 full-union supply canonical replay failed") from exc
    if (
        retained_completion != completion
        or len(registered_rows) != completion.get("outcome_key_count")
        or outcome.canonical_json_bytes(realized_source)
        != outcome.canonical_json_bytes(expected_source)
    ):
        raise RuntimeError("R6 full-union supply completion replay differs")
    return {
        "completion": completion,
        "completion_identity": retained_completion_identity,
        "panel_freeze_identity": dict(completion["panel_freeze_identity"]),
        "projection": projection,
        "projection_identity": projection_identity,
        "smoke_receipt": smoke_receipt,
        "smoke_identity": smoke_identity,
        "attempt": retained_attempt,
        "attempt_identity": identities["attempt"],
        "query_evidence": query_evidence,
        "query_evidence_identity": identities["query_evidence"],
        "realized_source": realized_source,
        "realized_source_identity": realized_source_identity,
        "outcome_snapshot": outcome_snapshot,
        "outcome_snapshot_identity": outcome_snapshot_identity,
        "read_exact": read_exact,
        "snapshot_code_identities": expected_code,
    }


def _validate_r6_grade_evidence(
    *, client, supply_replay: Mapping[str, object],
    grade_completion_raw: bytes,
    grade_completion_identity: Mapping[str, object],
    lease: Mapping[str, object],
) -> dict[str, object]:
    """Replay the terminal completion and all 54 persisted grade shards."""
    from nfl_dfs.research import corpus_r6_full_union_grade_release_v1 as release_v1
    from nfl_dfs.research import (
        corpus_r6_full_union_realized_grading_v1 as grading,
    )

    completion = _canonical_json_object(
        grade_completion_raw, label="R6 full-union grade completion"
    )
    run_id = str(lease["run_id"])
    grade_prefix = (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        f"corpus-r6-full-union-realized-grades/{run_id}"
    )
    expected_completion_uri = f"{grade_prefix}/grade-completion.json"
    expected_root_uri = f"{grade_prefix}/realized-grade-root.json"
    if grade_completion_identity.get("uri") != expected_completion_uri:
        raise RuntimeError("R6 full-union grade completion URI differs")
    root_identity, persisted_root, _, _ = _resolve_referenced_current(
        client,
        completion.get("persisted_grade_root_identity"),
        expected_uri=expected_root_uri,
        label="R6 full-union persisted grade root",
    )
    read_exact = supply_replay["read_exact"]
    if not callable(read_exact):  # pragma: no cover - internal invariant
        raise AssertionError("R6 replay exact reader is not callable")
    try:
        (
            retained_root,
            retained_root_identity,
            logical_root,
            shards,
        ) = grading.validate_persisted_realized_grade_v1(
            persisted_root,
            identity=root_identity,
            panel_freeze_identity=supply_replay["panel_freeze_identity"],
            outcome_key_projection=supply_replay["projection"],
            outcome_key_projection_identity=supply_replay["projection_identity"],
            realized_source=supply_replay["realized_source"],
            realized_source_identity=supply_replay["realized_source_identity"],
            outcome_snapshot=supply_replay["outcome_snapshot"],
            outcome_snapshot_identity=supply_replay["outcome_snapshot_identity"],
            read_exact=read_exact,
        )
        config = release_v1.FullUnionGradeReleaseConfigV1(
            run_id=run_id,
            job=str(lease["job"]),
            execution=str(completion.get("execution", "")),
            code_sha=str(lease["code_sha"]),
            image=str(lease["image"]),
            expected_supply_run_id=run_id,
            expected_supply_job=str(lease["job"]),
            expected_supply_code_sha=str(lease["code_sha"]),
            expected_supply_image=str(lease["image"]),
            snapshot_module_sha256=str(supply_replay[
                "snapshot_code_identities"
            ]["snapshot_module_sha256"]),  # type: ignore[index]
            snapshot_cli_sha256=str(supply_replay[
                "snapshot_code_identities"
            ]["snapshot_cli_sha256"]),  # type: ignore[index]
            snapshot_test_sha256=str(supply_replay[
                "snapshot_code_identities"
            ]["snapshot_test_sha256"]),  # type: ignore[index]
            snapshot_cli_test_sha256=str(supply_replay[
                "snapshot_code_identities"
            ]["snapshot_cli_test_sha256"]),  # type: ignore[index]
            enabled=True,
        )
        retained_completion, retained_completion_identity = (
            release_v1.validate_grade_completion_v1(
                completion,
                identity=grade_completion_identity,
                config=config,
                panel_freeze_identity=supply_replay["panel_freeze_identity"],
                outcome_supply_completion=supply_replay["completion"],
                outcome_supply_completion_identity=supply_replay[
                    "completion_identity"
                ],
                actual_root_smoke_receipt=supply_replay["smoke_receipt"],
                actual_root_smoke_receipt_identity=supply_replay[
                    "smoke_identity"
                ],
                historical_outcome_lease=supply_replay["attempt"][  # type: ignore[index]
                    "historical_outcome_lease"
                ],
                outcome_key_projection=supply_replay["projection"],
                outcome_key_projection_identity=supply_replay[
                    "projection_identity"
                ],
                realized_source=supply_replay["realized_source"],
                realized_source_identity=supply_replay[
                    "realized_source_identity"
                ],
                outcome_snapshot=supply_replay["outcome_snapshot"],
                outcome_snapshot_identity=supply_replay[
                    "outcome_snapshot_identity"
                ],
                persisted_grade_root=retained_root,
                persisted_grade_root_identity=retained_root_identity,
            )
        )
    except Exception as exc:
        raise RuntimeError(
            "R6 full-union persisted grade canonical replay failed"
        ) from exc
    coverage = logical_root.get("coverage")
    if not isinstance(coverage, Mapping):
        raise RuntimeError("R6 full-union grade coverage differs")
    if (
        retained_completion != completion
        or retained_completion_identity != dict(grade_completion_identity)
        or retained_root_identity != root_identity
        or len(shards) != 54
        or completion.get("source_slate_count") != 54
        or completion.get("slate_grade_object_count") != 54
        or completion.get("rank_80_book_count") != 2592
        or completion.get("prefix_grade_count") != 7776
        or completion.get("aggregate_cell_count") != 144
        or completion.get("aggregate_slate_row_count") != 7776
        or coverage.get("roster_sum_operation_count")
        != coverage.get("unique_final_union_roster_count")
        or coverage.get("roster_sum_operation_ceiling")
        != coverage.get("unique_final_union_roster_count")
        or any(completion.get(field) is not True for field in (
            "every_unique_final_union_roster_scored_once",
            "roster_sum_operation_ceiling_equals_final_union_count",
            "every_book_projected_from_union_score_lookup",
            "all_4_14_80_prefixes_projected_from_rank_80",
            "actual_player_outcome_keys_exact",
            "canonical_persisted_grade_replay_complete",
            "complete",
            "uses_realized_outcomes",
            "historical_outcome_lease_release_required",
        ))
        or completion.get("terminal_execution_envelope_validated") is not False
        or completion.get("terminal_execution_envelope_validation_owner")
        != release_v1.LEASE_RELEASE_OWNER
    ):
        raise RuntimeError("R6 full-union grade terminal coverage law differs")
    return {
        "completion": completion,
        "completion_identity": dict(grade_completion_identity),
        "persisted_root": retained_root,
        "persisted_root_identity": retained_root_identity,
    }


def _identity_rows(prefix: str, identity: Mapping[str, object]) -> dict[str, str]:
    return {
        f"{prefix}_uri": str(identity["uri"]),
        f"{prefix}_generation": str(identity["generation"]),
        f"{prefix}_sha256": str(identity["sha256"]),
        f"{prefix}_bytes": str(identity["bytes"]),
    }


def materialize_r6_full_union_completion(
    *, receipt_path: Path, supply_completion_uri: str,
    grade_completion_uri: str, output_path: Path,
    expected_service_account: str, expected_grade_stage_token: str,
    expected_snapshot_module_sha256: str,
    expected_snapshot_cli_sha256: str,
    expected_snapshot_test_sha256: str,
    expected_snapshot_cli_test_sha256: str,
    storage_client=None,
) -> dict[str, str]:
    """Materialize the only strict release proof for the R6 score chain."""
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    client, lease, lease_object, _, _ = _verified_lease_blob(
        receipt, storage_client=storage_client
    )
    run_id = str(lease["run_id"])
    expected_supply_uri = f"{R6_OUTCOME_PREFIX}/{run_id}/completion.json"
    expected_grade_uri = (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        f"corpus-r6-full-union-realized-grades/{run_id}/grade-completion.json"
    )
    if supply_completion_uri != expected_supply_uri:
        raise RuntimeError("R6 full-union supply completion URI differs")
    if grade_completion_uri != expected_grade_uri:
        raise RuntimeError("R6 full-union grade completion URI differs")
    expected_code = {
        "snapshot_module_sha256": expected_snapshot_module_sha256,
        "snapshot_cli_sha256": expected_snapshot_cli_sha256,
        "snapshot_test_sha256": expected_snapshot_test_sha256,
        "snapshot_cli_test_sha256": expected_snapshot_cli_test_sha256,
    }
    if (
        not _valid_r6_service_account(expected_service_account)
        or re.fullmatch(r"[0-9a-f]{64}", expected_grade_stage_token) is None
        or any(
            re.fullmatch(r"[0-9a-f]{64}", value) is None
            for value in expected_code.values()
        )
    ):
        raise RuntimeError("R6 full-union expected grade runtime differs")
    grade_identity, grade_raw = _resolve_current_exact(
        client, grade_completion_uri, label="R6 full-union grade completion"
    )
    grade_completion_shallow = _canonical_json_object(
        grade_raw, label="R6 full-union grade completion"
    )
    if (
        grade_completion_shallow.get("expected_supply_run_id") != lease["run_id"]
        or grade_completion_shallow.get("expected_supply_job") != lease["job"]
        or grade_completion_shallow.get("expected_supply_code_sha")
        != lease["code_sha"]
        or grade_completion_shallow.get("expected_supply_image") != lease["image"]
        or any(
            grade_completion_shallow.get(field) != value
            for field, value in expected_code.items()
        )
    ):
        raise RuntimeError("R6 grade independent supply/runtime/code pins differ")
    supply_identity, supply_raw = _resolve_current_exact(
        client, supply_completion_uri, label="R6 full-union supply completion"
    )
    supply_replay = _validate_r6_supply_evidence(
        client=client,
        raw=supply_raw,
        identity=supply_identity,
        lease=lease,
        lease_object=lease_object,
        expected_snapshot_code_identities=expected_code,
    )
    grade_replay = _validate_r6_grade_evidence(
        client=client,
        supply_replay=supply_replay,
        grade_completion_raw=grade_raw,
        grade_completion_identity=grade_identity,
        lease=lease,
    )
    supply_completion = supply_replay["completion"]
    grade_completion = grade_replay["completion"]
    persisted_root = grade_replay["persisted_root"]
    if not all(isinstance(value, Mapping) for value in (
        supply_completion, grade_completion, persisted_root,
    )):
        raise AssertionError("R6 strict replay return type differs")
    rows: dict[str, str] = {
        "schema_version": R6_STRICT_COMPLETION_SCHEMA,
        "run_id": run_id,
        "job": str(lease["job"]),
        "execution": str(grade_completion["execution"]),
        "code_sha": str(lease["code_sha"]),
        "image": str(lease["image"]),
        "service_account": expected_service_account,
        "grade_stage_token": expected_grade_stage_token,
        "uses_realized_outcomes": "true",
        "disposition": R6_STRICT_DISPOSITION,
        "supply_completion_self_sha256": str(
            supply_completion["completion_sha256"]
        ),
        "grade_completion_self_sha256": str(
            grade_completion["grade_completion_sha256"]
        ),
        "persisted_grade_root_self_sha256": str(
            persisted_root["persisted_grade_root_sha256"]
        ),
        "one_historical_outcome_read": "true",
        "one_exact_query_job": "true",
        "canonical_persisted_grade_replay_complete": "true",
        "terminal_execution_envelope_validation_required": "true",
        "historical_outcome_lease_release_required": "true",
        **_identity_rows("supply_completion", supply_identity),
        **_identity_rows(
            "attempt", supply_replay["attempt_identity"]  # type: ignore[arg-type]
        ),
        **_identity_rows(
            "query_evidence",
            supply_replay["query_evidence_identity"],  # type: ignore[arg-type]
        ),
        **_identity_rows("grade_completion", grade_identity),
        **_identity_rows(
            "persisted_grade_root",
            grade_replay["persisted_root_identity"],  # type: ignore[arg-type]
        ),
        **_identity_rows("historical_outcome_lease", lease_object),
        **_identity_rows(
            "panel_freeze",
            supply_replay["panel_freeze_identity"],  # type: ignore[arg-type]
        ),
        **_identity_rows(
            "actual_root_smoke_receipt",
            supply_replay["smoke_identity"],  # type: ignore[arg-type]
        ),
        **_identity_rows(
            "outcome_key_projection",
            supply_replay["projection_identity"],  # type: ignore[arg-type]
        ),
        **_identity_rows(
            "realized_source",
            supply_replay["realized_source_identity"],  # type: ignore[arg-type]
        ),
        **_identity_rows(
            "outcome_snapshot",
            supply_replay["outcome_snapshot_identity"],  # type: ignore[arg-type]
        ),
        **{
            field: str(value)
            for field, value in supply_replay[  # type: ignore[union-attr]
                "snapshot_code_identities"
            ].items()
        },
    }
    if set(rows) != _R6_STRICT_COMPLETION_KEYS:
        raise AssertionError("R6 strict completion row construction differs")
    raw_rows = "".join(
        f"{key}={rows[key]}\n" for key in sorted(rows)
    ).encode()
    _write_create_or_equal(output_path, raw_rows)
    return rows


def _completion_rows(path: Path) -> tuple[dict[str, str], str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    loose_pairs = [line.split("=", 1) for line in lines if "=" in line]
    loose_rows = dict(loose_pairs)
    common_keys = {
        "schema_version", "run_id", "uses_realized_outcomes", "disposition",
    }
    core_only_keys = (
        _CORE_STRICT_COMPLETION_KEYS - _R6_STRICT_COMPLETION_KEYS - common_keys
    )
    r6_only_keys = (
        _R6_STRICT_COMPLETION_KEYS - _CORE_STRICT_COMPLETION_KEYS - common_keys
    )
    r6 = (
        loose_rows.get("disposition") == R6_STRICT_DISPOSITION
        or bool(set(loose_rows) & r6_only_keys)
        or loose_rows.get("schema_version") == R6_STRICT_COMPLETION_SCHEMA
    )
    core = (
        loose_rows.get("disposition") == CORE_STRICT_DISPOSITION
        or bool(set(loose_rows) & core_only_keys)
        or loose_rows.get("schema_version") == CORE_STRICT_COMPLETION_SCHEMA
    )
    if r6 and core:
        raise RuntimeError("historical-outcome strict completion families alias")
    if not core and not r6:
        # Preserve the legacy finisher contract exactly.
        return dict(line.split("=", 1) for line in lines if "=" in line), "legacy"
    if any("=" not in line for line in lines):
        raise RuntimeError("historical-outcome strict completion syntax differs")
    pairs = [line.split("=", 1) for line in lines]
    if len({key for key, _ in pairs}) != len(pairs):
        raise RuntimeError("historical-outcome strict completion has duplicate keys")
    rows = dict(pairs)
    expected = (
        _R6_STRICT_COMPLETION_KEYS if r6 else _CORE_STRICT_COMPLETION_KEYS
    )
    if set(rows) != expected:
        family = "R6 full-union" if r6 else "Core v1"
        raise RuntimeError(f"{family} strict completion keys differ")
    if r6:
        return rows, "r6-full-union"
    if set(rows) != _CORE_STRICT_COMPLETION_KEYS:  # pragma: no cover
        raise RuntimeError("Core v1 strict completion keys differ")
    return rows, "core-v1"


def _validate_core_strict_rows(
    *, rows: Mapping[str, str], client, lease: Mapping[str, object],
    lease_object: Mapping[str, object],
) -> None:
    def positive_int(key: str) -> int:
        value = rows.get(key, "")
        if not re.fullmatch(r"[1-9][0-9]*", value):
            raise RuntimeError(f"Core v1 strict completion {key} differs")
        return int(value)

    completion_identity = _object_identity({
        "uri": rows.get("completion_uri"),
        "generation": rows.get("completion_generation"),
        "sha256": rows.get("completion_sha256"),
        "bytes": positive_int("completion_bytes"),
    }, label="Core v1 strict completion object identity")
    attempt_identity = _object_identity({
        "uri": rows.get("attempt_uri"),
        "generation": rows.get("attempt_generation"),
        "sha256": rows.get("attempt_sha256"),
        "bytes": positive_int("attempt_bytes"),
    }, label="Core v1 strict attempt identity")
    expected_lease = {
        "uri": rows.get("historical_outcome_lease_uri"),
        "generation": rows.get("historical_outcome_lease_generation"),
        "sha256": rows.get("historical_outcome_lease_sha256"),
        "bytes": positive_int("historical_outcome_lease_bytes"),
        "create_only": True,
    }
    if (
        rows.get("schema_version") != CORE_STRICT_COMPLETION_SCHEMA
        or rows.get("run_id") != lease.get("run_id")
        or rows.get("uses_realized_outcomes") != "true"
        or rows.get("disposition") != CORE_STRICT_DISPOSITION
        or rows.get("one_historical_outcome_read") != "true"
        or rows.get("historical_outcome_lease_release_required") != "true"
        or expected_lease != dict(lease_object)
    ):
        raise RuntimeError("Core v1 strict completion lease law differs")
    observed_identity, raw = _resolve_current_exact(
        client,
        str(completion_identity["uri"]),
        label="Core v1 outcome completion",
    )
    if observed_identity != completion_identity:
        raise RuntimeError("Core v1 strict completion object changed")
    completion, observed_attempt = _validate_core_completion_evidence(
        client=client,
        raw=raw,
        identity=observed_identity,
        lease=lease,
        lease_object=lease_object,
    )
    if (
        observed_attempt != attempt_identity
        or rows.get("completion_self_sha256")
        != completion.get("completion_sha256")
    ):
        raise RuntimeError("Core v1 strict completion content binding differs")


def _r6_identity_from_rows(
    rows: Mapping[str, str], prefix: str,
) -> dict[str, object]:
    byte_value = rows.get(f"{prefix}_bytes", "")
    if re.fullmatch(r"[1-9][0-9]*", byte_value) is None:
        raise RuntimeError(f"R6 strict completion {prefix} bytes differ")
    return _object_identity({
        "uri": rows.get(f"{prefix}_uri"),
        "generation": rows.get(f"{prefix}_generation"),
        "sha256": rows.get(f"{prefix}_sha256"),
        "bytes": int(byte_value),
    }, label=f"R6 strict completion {prefix} identity")


def _validate_r6_strict_rows(
    *, rows: Mapping[str, str], receipt_path: Path, completion_path: Path,
    client, lease: Mapping[str, object], lease_object: Mapping[str, object],
) -> None:
    expected_lease = {
        **_r6_identity_from_rows(rows, "historical_outcome_lease"),
        "create_only": True,
    }
    if (
        rows.get("schema_version") != R6_STRICT_COMPLETION_SCHEMA
        or rows.get("run_id") != lease.get("run_id")
        or rows.get("job") != lease.get("job")
        or rows.get("code_sha") != lease.get("code_sha")
        or rows.get("image") != lease.get("image")
        or rows.get("uses_realized_outcomes") != "true"
        or rows.get("disposition") != R6_STRICT_DISPOSITION
        or rows.get("one_historical_outcome_read") != "true"
        or rows.get("one_exact_query_job") != "true"
        or rows.get("canonical_persisted_grade_replay_complete") != "true"
        or rows.get("terminal_execution_envelope_validation_required") != "true"
        or rows.get("historical_outcome_lease_release_required") != "true"
        or expected_lease != dict(lease_object)
    ):
        raise RuntimeError("R6 full-union strict completion lease law differs")
    replayed = materialize_r6_full_union_completion(
        receipt_path=receipt_path,
        supply_completion_uri=str(rows["supply_completion_uri"]),
        grade_completion_uri=str(rows["grade_completion_uri"]),
        output_path=completion_path,
        expected_service_account=str(rows["service_account"]),
        expected_grade_stage_token=str(rows["grade_stage_token"]),
        expected_snapshot_module_sha256=str(rows["snapshot_module_sha256"]),
        expected_snapshot_cli_sha256=str(rows["snapshot_cli_sha256"]),
        expected_snapshot_test_sha256=str(rows["snapshot_test_sha256"]),
        expected_snapshot_cli_test_sha256=str(
            rows["snapshot_cli_test_sha256"]
        ),
        storage_client=client,
    )
    if dict(rows) != replayed:
        raise RuntimeError("R6 full-union strict completion replay differs")


def _r6_grade_cli_args(rows: Mapping[str, str]) -> list[str]:
    result = [
        "/opt/nfl-predictions/scripts/"
        "run_corpus_r6_full_union_realized_grade_v1.py",
        "--execute",
        f"--project={PROJECT}",
        f"--run-id={rows['run_id']}",
        f"--code-sha={rows['code_sha']}",
        f"--image={rows['image']}",
    ]
    for cli_prefix, row_prefix in (
        ("panel-freeze", "panel_freeze"),
        ("outcome-supply-completion", "supply_completion"),
        ("outcome-key-projection", "outcome_key_projection"),
        ("realized-source", "realized_source"),
        ("outcome-snapshot", "outcome_snapshot"),
        ("expected-lease", "historical_outcome_lease"),
    ):
        for suffix in ("uri", "generation", "sha256", "bytes"):
            result.append(
                f"--{cli_prefix}-{suffix}={rows[f'{row_prefix}_{suffix}']}"
            )
    result.extend([
        f"--expected-supply-run-id={rows['run_id']}",
        f"--expected-supply-job={rows['job']}",
        f"--expected-supply-code-sha={rows['code_sha']}",
        f"--expected-supply-image={rows['image']}",
        f"--snapshot-module-sha256={rows['snapshot_module_sha256']}",
        f"--snapshot-cli-sha256={rows['snapshot_cli_sha256']}",
        f"--snapshot-test-sha256={rows['snapshot_test_sha256']}",
        f"--snapshot-cli-test-sha256={rows['snapshot_cli_test_sha256']}",
    ])
    return result


def _validate_r6_execution_envelope(
    *, execution: Mapping[str, object], rows: Mapping[str, str],
    lease: Mapping[str, object],
) -> None:
    metadata = execution.get("metadata")
    status = execution.get("status")
    spec = execution.get("spec")
    if not all(isinstance(value, Mapping) for value in (metadata, status, spec)):
        raise RuntimeError("R6 grade execution envelope differs")
    name_value = str(metadata.get("name", ""))  # type: ignore[union-attr]
    execution_name = name_value.rsplit("/", 1)[-1]
    labels = metadata.get("labels")  # type: ignore[union-attr]
    conditions = status.get("conditions", [])  # type: ignore[union-attr]
    completed = [
        row for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ] if isinstance(conditions, list) else []
    template = spec.get("template")  # type: ignore[union-attr]
    template_spec = template.get("spec") if isinstance(template, Mapping) else None
    containers = (
        template_spec.get("containers")
        if isinstance(template_spec, Mapping) else None
    )
    if not isinstance(containers, list) or len(containers) != 1 or not isinstance(
        containers[0], Mapping
    ):
        raise RuntimeError("R6 grade execution container envelope differs")
    container = containers[0]
    raw_args = container.get("args")
    args = list(raw_args) if isinstance(raw_args, list) else []
    raw_env = container.get("env")
    env = list(raw_env) if isinstance(raw_env, list) else []
    expected_env = sorted([
        {"name": "R6_CHAIN_STAGE_TOKEN", "value": rows["grade_stage_token"]},
        {"name": "R6_FULL_UNION_REALIZED_GRADE_ENABLED", "value": "1"},
        {"name": "R6_FULL_UNION_REVIEWED_CODE_SHA", "value": rows["code_sha"]},
        {"name": "R6_FULL_UNION_RUNTIME_IMAGE", "value": rows["image"]},
    ], key=lambda item: item["name"])
    retained_env = sorted(
        [dict(item) for item in env if isinstance(item, Mapping)],
        key=lambda item: str(item.get("name", "")),
    )
    if (
        execution_name != rows.get("execution")
        or not execution_name.startswith(str(lease["job"]) + "-")
        or not isinstance(labels, Mapping)
        or labels.get("run.googleapis.com/job") != lease.get("job")
        or len(completed) != 1
        or completed[0].get("status") != "True"
        or status.get("completionTime") in (None, "")  # type: ignore[union-attr]
        or status.get("succeededCount") != 1  # type: ignore[union-attr]
        or (status.get("failedCount", 0) or 0) != 0  # type: ignore[union-attr]
        or (status.get("runningCount", 0) or 0) != 0  # type: ignore[union-attr]
        or spec.get("taskCount") != 1  # type: ignore[union-attr]
        or spec.get("parallelism") != 1  # type: ignore[union-attr]
        or template_spec.get("maxRetries") != 0  # type: ignore[union-attr]
        or str(template_spec.get("timeoutSeconds")) != "28800"  # type: ignore[union-attr]
        or template_spec.get("serviceAccountName")  # type: ignore[union-attr]
        != rows.get("service_account")
        or (template_spec.get("volumes", []) or []) != []  # type: ignore[union-attr]
        or (template_spec.get("vpcAccess", {}) or {}) != {}  # type: ignore[union-attr]
        or container.get("image") != lease.get("image")
        or container.get("command") != ["python"]
        or args != _r6_grade_cli_args(rows)
        or len(env) != len(expected_env)
        or not all(isinstance(item, Mapping) for item in env)
        or retained_env != expected_env
        or (container.get("volumeMounts", []) or []) != []
        or container.get("resources", {}).get("limits")  # type: ignore[union-attr]
        != {"cpu": "8", "memory": "32Gi"}
    ):
        raise RuntimeError("R6 grade terminal execution envelope differs")


def abandon(*, receipt_path: Path, reason: str, preserve_dir: Path) -> str:
    """Archive and delete OUR OWN live lease after a failed attempt.

    Generation-matched end to end: refuses to touch a lease the receipt
    does not describe byte-for-byte. The stale object is preserved
    create-only under research-governance/archive/ before deletion, and
    the local receipt moves into the failed-attempt directory so a later
    acquisition can never be blocked by (or confused with) this one.
    """
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,60}", reason):
        raise RuntimeError("abandon reason must be a short slug")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    client, _, expected_object, blob, raw = _verified_lease_blob(receipt)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive_uri = (
        "gs://nfl-predictions-503414-raw/research-governance/archive/"
        f"historical-outcome-stale-{stamp}-{reason}.json"
    )
    _upload_create_only(client, archive_uri, raw)
    blob.delete(if_generation_match=int(expected_object["generation"]))
    preserve_dir.mkdir(parents=True, exist_ok=True)
    target = preserve_dir / receipt_path.name
    if target.exists():
        raise RuntimeError("abandon preserve target already exists")
    receipt_path.rename(target)
    return archive_uri


def _local_file_identity(path: Path, *, label: str) -> dict[str, object]:
    try:
        info = path.lstat()
        raw = path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"{label} local evidence is absent") from exc
    if not stat.S_ISREG(info.st_mode) or not raw:
        raise RuntimeError(f"{label} local evidence differs")
    return {
        "name": path.name,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _release_intent_payload(
    *, lease: Mapping[str, object], lease_object: Mapping[str, object],
    execution_path: Path, completion_path: Path,
    completion: Mapping[str, str], contract: str,
) -> dict[str, object]:
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    name = str(execution.get("metadata", {}).get("name", "")).rsplit("/", 1)[-1]
    body: dict[str, object] = {
        "schema_version": "historical-outcome-generation-delete-intent/v1",
        "run_id": lease["run_id"],
        "job": lease["job"],
        "execution": name,
        "required_contract": contract,
        "strict_completion_schema": completion.get("schema_version"),
        "strict_completion_disposition": completion.get("disposition"),
        "historical_outcome_lease": dict(lease_object),
        "delete_if_generation_match": str(lease_object["generation"]),
        "strict_completion_file": _local_file_identity(
            completion_path, label="strict completion"
        ),
        "terminal_execution_file": _local_file_identity(
            execution_path, label="terminal execution"
        ),
        "strict_completion_validation_complete": True,
        "terminal_execution_validation_complete": True,
        "generation_matched_delete_only": True,
        "automatic_retry_licensed": False,
    }
    body["release_intent_sha256"] = sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return body


def _canonical_local_json(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _read_equal_release_intent(
    *, path: Path, expected: Mapping[str, object],
) -> dict[str, object]:
    try:
        info = path.lstat()
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("historical-outcome release intent differs") from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or not isinstance(value, Mapping)
        or raw != _canonical_local_json(value)
        or dict(value) != dict(expected)
    ):
        raise RuntimeError("historical-outcome release intent differs")
    return dict(value)


def _exact_lease_generation_absent(
    client, lease_object: Mapping[str, object],
) -> bool:
    bucket_name, name = _parse_gcs(str(lease_object["uri"]))
    generation = int(str(lease_object["generation"]))
    blob = client.bucket(bucket_name).blob(name, generation=generation)
    try:
        blob.reload(if_generation_match=generation)
    except NotFound:
        return True
    except Exception as exc:
        raise RuntimeError(
            "historical-outcome lease generation absence check failed"
        ) from exc
    return False


def _release_receipt_payload(
    *, intent: Mapping[str, object], recovered_after_delete: bool,
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": "historical-outcome-generation-delete-receipt/v1",
        "run_id": intent["run_id"],
        "job": intent["job"],
        "execution": intent["execution"],
        "historical_outcome_lease": intent["historical_outcome_lease"],
        "deleted_generation": intent["delete_if_generation_match"],
        "release_intent_sha256": intent["release_intent_sha256"],
        "strict_completion_file": intent["strict_completion_file"],
        "terminal_execution_file": intent["terminal_execution_file"],
        "generation_delete_complete": True,
        "exact_deleted_generation_absent": True,
        "recovered_after_delete": recovered_after_delete,
    }
    body["release_receipt_sha256"] = sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return body


def _validate_release_receipt(
    *, path: Path, intent: Mapping[str, object],
) -> dict[str, object]:
    try:
        info = path.lstat()
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("historical-outcome release receipt differs") from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or not isinstance(value, Mapping)
        or raw != _canonical_local_json(value)
    ):
        raise RuntimeError("historical-outcome release receipt differs")
    recovered = value.get("recovered_after_delete")
    if type(recovered) is not bool or dict(value) != _release_receipt_payload(
        intent=intent, recovered_after_delete=recovered
    ):
        raise RuntimeError("historical-outcome release receipt differs")
    return dict(value)


def validate_release_receipt_local(
    *, lease_receipt_path: Path, execution_path: Path,
    completion_path: Path, release_intent_path: Path,
    release_receipt_path: Path,
) -> dict[str, object]:
    """Validate the durable R6 delete receipt from local immutable evidence."""
    try:
        receipt = json.loads(lease_receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("historical-outcome lease receipt differs") from exc
    lease, lease_object = _lease_receipt_coordinates(receipt)
    completion, contract = _completion_rows(completion_path)
    if contract != "r6-full-union":
        raise RuntimeError("R6 full-union durable release contract differs")
    expected_intent = _release_intent_payload(
        lease=lease,
        lease_object=lease_object,
        execution_path=execution_path,
        completion_path=completion_path,
        completion=completion,
        contract=contract,
    )
    intent = _read_equal_release_intent(
        path=release_intent_path, expected=expected_intent
    )
    return _validate_release_receipt(
        path=release_receipt_path, intent=intent
    )


def release(
    *, receipt_path: Path, execution_path: Path, completion_path: Path,
    storage_client=None, required_contract: str = "auto",
    release_intent_path: Path | None = None,
    release_receipt_path: Path | None = None,
) -> None:
    if required_contract not in {"auto", "core-v1", "r6-full-union"}:
        raise RuntimeError("historical-outcome required completion contract differs")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    lease, expected_object = _lease_receipt_coordinates(receipt)
    client = storage_client or storage.Client(project=PROJECT)
    completion, contract = _completion_rows(completion_path)
    if required_contract != "auto" and contract != required_contract:
        raise RuntimeError("historical-outcome required strict contract differs")
    r6_release = contract == "r6-full-union"
    if r6_release and (
        release_intent_path is None or release_receipt_path is None
    ):
        raise RuntimeError("R6 full-union durable release paths are required")

    expected_intent: dict[str, object] | None = None
    retained_intent: dict[str, object] | None = None
    if r6_release:
        assert release_intent_path is not None
        assert release_receipt_path is not None
        expected_intent = _release_intent_payload(
            lease=lease,
            lease_object=expected_object,
            execution_path=execution_path,
            completion_path=completion_path,
            completion=completion,
            contract=contract,
        )
        if release_receipt_path.exists() and not release_intent_path.exists():
            raise RuntimeError(
                "historical-outcome release receipt lacks durable intent"
            )
        if release_intent_path.exists():
            retained_intent = _read_equal_release_intent(
                path=release_intent_path, expected=expected_intent
            )
            if _exact_lease_generation_absent(client, expected_object):
                if release_receipt_path.exists():
                    _validate_release_receipt(
                        path=release_receipt_path, intent=retained_intent
                    )
                else:
                    recovered_receipt = _release_receipt_payload(
                        intent=retained_intent, recovered_after_delete=True
                    )
                    _write_create_or_equal(
                        release_receipt_path,
                        _canonical_local_json(recovered_receipt),
                    )
                return
            if release_receipt_path.exists():
                _validate_release_receipt(
                    path=release_receipt_path, intent=retained_intent
                )
                raise RuntimeError(
                    "historical-outcome release receipt precedes generation delete"
                )

    client, verified_lease, verified_object, blob, _ = _verified_lease_blob(
        receipt, storage_client=client
    )
    if verified_lease != lease or verified_object != expected_object:
        raise AssertionError("historical-outcome verified lease coordinates differ")
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    status = execution.get("status", {})
    completed = [
        row for row in status.get("conditions", []) if row.get("type") == "Completed"
    ]
    name_value = str(execution.get("metadata", {}).get("name", ""))
    execution_name = name_value.rsplit("/", 1)[-1]
    if len(completed) != 1 or completed[0].get("status") != "True" or \
            not execution_name.startswith(str(lease["job"]) + "-") or \
            not status.get("completionTime"):
        raise RuntimeError("historical-outcome execution is not terminal")
    if completion.get("run_id") != lease["run_id"] or \
            completion.get("uses_realized_outcomes") != "true" or \
            not completion.get("disposition"):
        raise RuntimeError("historical-outcome strict completion differs")
    if contract == "core-v1":
        _validate_core_strict_rows(
            rows=completion,
            client=client,
            lease=lease,
            lease_object=expected_object,
        )
    elif contract == "r6-full-union":
        _validate_r6_strict_rows(
            rows=completion,
            receipt_path=receipt_path,
            completion_path=completion_path,
            client=client,
            lease=lease,
            lease_object=expected_object,
        )
        _validate_r6_execution_envelope(
            execution=execution, rows=completion, lease=lease
        )
        assert release_intent_path is not None
        assert release_receipt_path is not None
        assert expected_intent is not None
        _write_create_or_equal(
            release_intent_path, _canonical_local_json(expected_intent)
        )
        retained_intent = _read_equal_release_intent(
            path=release_intent_path, expected=expected_intent
        )
    blob.delete(if_generation_match=int(expected_object["generation"]))
    if r6_release:
        assert release_receipt_path is not None
        assert retained_intent is not None
        if not _exact_lease_generation_absent(client, expected_object):
            raise RuntimeError(
                "historical-outcome exact lease generation remains after delete"
            )
        release_receipt = _release_receipt_payload(
            intent=retained_intent, recovered_after_delete=False
        )
        _write_create_or_equal(
            release_receipt_path, _canonical_local_json(release_receipt)
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    acquire_parser = sub.add_parser("acquire")
    acquire_parser.add_argument("--run-id", required=True)
    acquire_parser.add_argument("--job", required=True)
    acquire_parser.add_argument("--code-sha", required=True)
    acquire_parser.add_argument("--image", required=True)
    acquire_parser.add_argument("--receipt", type=Path, required=True)
    resolve_parser = sub.add_parser("resolve")
    resolve_parser.add_argument("--run-id", required=True)
    resolve_parser.add_argument("--job", required=True)
    resolve_parser.add_argument("--code-sha", required=True)
    resolve_parser.add_argument("--image", required=True)
    resolve_parser.add_argument("--receipt", type=Path, required=True)
    release_parser = sub.add_parser("release")
    release_parser.add_argument("--receipt", type=Path, required=True)
    release_parser.add_argument("--execution", type=Path, required=True)
    release_parser.add_argument("--completion", type=Path, required=True)
    release_parser.add_argument("--release-intent", type=Path)
    release_parser.add_argument("--release-receipt", type=Path)
    release_parser.add_argument(
        "--required-contract",
        choices=("auto", "core-v1", "r6-full-union"),
        default="auto",
    )
    validate_release_parser = sub.add_parser("validate-release-receipt")
    validate_release_parser.add_argument(
        "--lease-receipt", type=Path, required=True
    )
    validate_release_parser.add_argument(
        "--execution", type=Path, required=True
    )
    validate_release_parser.add_argument(
        "--completion", type=Path, required=True
    )
    validate_release_parser.add_argument(
        "--release-intent", type=Path, required=True
    )
    validate_release_parser.add_argument(
        "--release-receipt", type=Path, required=True
    )
    materialize_parser = sub.add_parser("materialize-core-v1-completion")
    materialize_parser.add_argument("--receipt", type=Path, required=True)
    materialize_parser.add_argument("--completion-uri", required=True)
    materialize_parser.add_argument("--output", type=Path, required=True)
    materialize_r6_parser = sub.add_parser(
        "materialize-r6-full-union-completion"
    )
    materialize_r6_parser.add_argument("--receipt", type=Path, required=True)
    materialize_r6_parser.add_argument("--supply-completion-uri", required=True)
    materialize_r6_parser.add_argument("--grade-completion-uri", required=True)
    materialize_r6_parser.add_argument(
        "--expected-service-account", required=True
    )
    materialize_r6_parser.add_argument(
        "--expected-grade-stage-token", required=True
    )
    materialize_r6_parser.add_argument(
        "--expected-snapshot-module-sha256", required=True
    )
    materialize_r6_parser.add_argument(
        "--expected-snapshot-cli-sha256", required=True
    )
    materialize_r6_parser.add_argument(
        "--expected-snapshot-test-sha256", required=True
    )
    materialize_r6_parser.add_argument(
        "--expected-snapshot-cli-test-sha256", required=True
    )
    materialize_r6_parser.add_argument("--output", type=Path, required=True)
    abandon_parser = sub.add_parser("abandon")
    abandon_parser.add_argument("--receipt", type=Path, required=True)
    abandon_parser.add_argument("--reason", required=True)
    abandon_parser.add_argument("--preserve-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "acquire":
        value = acquire(
            run_id=args.run_id, job=args.job, code_sha=args.code_sha,
            image=args.image, receipt_path=args.receipt,
        )
        print("HISTORICAL_OUTCOME_LEASE_ACQUIRED " + json.dumps(
            value["object"], sort_keys=True,
        ))
    elif args.command == "resolve":
        value = resolve(
            run_id=args.run_id, job=args.job, code_sha=args.code_sha,
            image=args.image, receipt_path=args.receipt,
        )
        print("HISTORICAL_OUTCOME_LEASE_RESOLVED " + json.dumps(
            value["object"], sort_keys=True,
        ))
    elif args.command == "abandon":
        archived = abandon(
            receipt_path=args.receipt, reason=args.reason,
            preserve_dir=args.preserve_dir,
        )
        print("HISTORICAL_OUTCOME_LEASE_ABANDONED " + archived)
    elif args.command == "materialize-core-v1-completion":
        rows = materialize_core_v1_completion(
            receipt_path=args.receipt,
            completion_uri=args.completion_uri,
            output_path=args.output,
        )
        print("HISTORICAL_OUTCOME_CORE_V1_COMPLETION_MATERIALIZED " + json.dumps({
            "completion_uri": rows["completion_uri"],
            "completion_generation": rows["completion_generation"],
            "completion_sha256": rows["completion_sha256"],
            "completion_bytes": int(rows["completion_bytes"]),
            "output": str(args.output),
        }, sort_keys=True, separators=(",", ":")))
    elif args.command == "materialize-r6-full-union-completion":
        rows = materialize_r6_full_union_completion(
            receipt_path=args.receipt,
            supply_completion_uri=args.supply_completion_uri,
            grade_completion_uri=args.grade_completion_uri,
            output_path=args.output,
            expected_service_account=args.expected_service_account,
            expected_grade_stage_token=args.expected_grade_stage_token,
            expected_snapshot_module_sha256=(
                args.expected_snapshot_module_sha256
            ),
            expected_snapshot_cli_sha256=args.expected_snapshot_cli_sha256,
            expected_snapshot_test_sha256=args.expected_snapshot_test_sha256,
            expected_snapshot_cli_test_sha256=(
                args.expected_snapshot_cli_test_sha256
            ),
        )
        print("HISTORICAL_OUTCOME_R6_FULL_UNION_COMPLETION_MATERIALIZED " + json.dumps({
            "supply_completion_uri": rows["supply_completion_uri"],
            "grade_completion_uri": rows["grade_completion_uri"],
            "persisted_grade_root_uri": rows["persisted_grade_root_uri"],
            "execution": rows["execution"],
            "output": str(args.output),
        }, sort_keys=True, separators=(",", ":")))
    elif args.command == "validate-release-receipt":
        value = validate_release_receipt_local(
            lease_receipt_path=args.lease_receipt,
            execution_path=args.execution,
            completion_path=args.completion,
            release_intent_path=args.release_intent,
            release_receipt_path=args.release_receipt,
        )
        print(json.dumps({
            "lease_released": True,
            "execution": value["execution"],
            "deleted_generation": value["deleted_generation"],
            "release_intent_sha256": value["release_intent_sha256"],
            "release_receipt_sha256": value["release_receipt_sha256"],
        }, sort_keys=True, separators=(",", ":")))
    else:
        release(
            receipt_path=args.receipt, execution_path=args.execution,
            completion_path=args.completion,
            required_contract=args.required_contract,
            release_intent_path=args.release_intent,
            release_receipt_path=args.release_receipt,
        )
        print("HISTORICAL_OUTCOME_LEASE_RELEASED")


if __name__ == "__main__":
    main()
