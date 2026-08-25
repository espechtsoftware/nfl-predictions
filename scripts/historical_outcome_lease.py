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

from google.api_core.exceptions import PreconditionFailed
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
    receipt_path.write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return receipt


def _verified_lease_blob(receipt: dict, *, storage_client=None):
    """Validate a receipt and return its live, byte-verified lease blob."""
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


def _completion_rows(path: Path) -> tuple[dict[str, str], bool]:
    lines = path.read_text(encoding="utf-8").splitlines()
    loose_pairs = [line.split("=", 1) for line in lines if "=" in line]
    loose_rows = dict(loose_pairs)
    core_only_keys = _CORE_STRICT_COMPLETION_KEYS - {
        "schema_version", "run_id", "uses_realized_outcomes", "disposition",
    }
    core = (
        loose_rows.get("disposition") == CORE_STRICT_DISPOSITION
        or bool(set(loose_rows) & core_only_keys)
        or loose_rows.get("schema_version") == CORE_STRICT_COMPLETION_SCHEMA
    )
    if not core:
        # Preserve the legacy finisher contract exactly.
        return dict(line.split("=", 1) for line in lines if "=" in line), False
    if any("=" not in line for line in lines):
        raise RuntimeError("Core v1 strict completion syntax differs")
    pairs = [line.split("=", 1) for line in lines]
    if len({key for key, _ in pairs}) != len(pairs):
        raise RuntimeError("Core v1 strict completion has duplicate keys")
    rows = dict(pairs)
    if set(rows) != _CORE_STRICT_COMPLETION_KEYS:
        raise RuntimeError("Core v1 strict completion keys differ")
    return rows, True


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


def release(
    *, receipt_path: Path, execution_path: Path, completion_path: Path,
    storage_client=None,
) -> None:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    client, lease, expected_object, blob, _ = _verified_lease_blob(
        receipt, storage_client=storage_client
    )
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
    completion, is_core = _completion_rows(completion_path)
    if completion.get("run_id") != lease["run_id"] or \
            completion.get("uses_realized_outcomes") != "true" or \
            not completion.get("disposition"):
        raise RuntimeError("historical-outcome strict completion differs")
    if is_core:
        _validate_core_strict_rows(
            rows=completion,
            client=client,
            lease=lease,
            lease_object=expected_object,
        )
    blob.delete(if_generation_match=int(expected_object["generation"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    acquire_parser = sub.add_parser("acquire")
    acquire_parser.add_argument("--run-id", required=True)
    acquire_parser.add_argument("--job", required=True)
    acquire_parser.add_argument("--code-sha", required=True)
    acquire_parser.add_argument("--image", required=True)
    acquire_parser.add_argument("--receipt", type=Path, required=True)
    release_parser = sub.add_parser("release")
    release_parser.add_argument("--receipt", type=Path, required=True)
    release_parser.add_argument("--execution", type=Path, required=True)
    release_parser.add_argument("--completion", type=Path, required=True)
    materialize_parser = sub.add_parser("materialize-core-v1-completion")
    materialize_parser.add_argument("--receipt", type=Path, required=True)
    materialize_parser.add_argument("--completion-uri", required=True)
    materialize_parser.add_argument("--output", type=Path, required=True)
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
    else:
        release(
            receipt_path=args.receipt, execution_path=args.execution,
            completion_path=args.completion,
        )
        print("HISTORICAL_OUTCOME_LEASE_RELEASED")


if __name__ == "__main__":
    main()
