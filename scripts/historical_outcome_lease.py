#!/usr/bin/env python3
"""Create/release the durable single-active historical-outcome lease."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

from run_cbwu_seed_order_audit import _parse_gcs, _upload_create_only


PROJECT = "nfl-predictions-503414"
LEASE_URI = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    "historical-outcome-active-v1.json"
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
    receipt_path.write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return receipt


def _verified_lease_blob(receipt: dict):
    """Validate a receipt and return its live, byte-verified lease blob."""
    lease = receipt.get("lease", {})
    expected_object = receipt.get("object", {})
    if lease.get("version") != "historical-outcome-active-v1" or \
            expected_object.get("uri") != LEASE_URI or \
            expected_object.get("create_only") is not True or \
            not str(expected_object.get("generation", "")).isdigit() or \
            not re.fullmatch(r"[0-9a-f]{64}", str(expected_object.get("sha256", ""))):
        raise RuntimeError("historical-outcome lease receipt differs")
    client = storage.Client(project=PROJECT)
    bucket, name = _parse_gcs(LEASE_URI)
    blob = client.bucket(bucket).blob(
        name, generation=int(expected_object["generation"]))
    raw = blob.download_as_bytes()
    if sha256(raw).hexdigest() != expected_object["sha256"] or \
            json.loads(raw) != lease:
        raise RuntimeError("historical-outcome active lease changed")
    return client, lease, expected_object, blob, raw


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
) -> None:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    _, lease, expected_object, blob, _ = _verified_lease_blob(receipt)
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    status = execution.get("status", {})
    completed = [
        row for row in status.get("conditions", []) if row.get("type") == "Completed"
    ]
    name_value = str(execution.get("metadata", {}).get("name", ""))
    if len(completed) != 1 or completed[0].get("status") == "Unknown" or \
            not name_value.startswith(str(lease["job"]) + "-") or \
            not status.get("completionTime"):
        raise RuntimeError("historical-outcome execution is not terminal")
    completion = dict(
        line.split("=", 1)
        for line in completion_path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    if completion.get("run_id") != lease["run_id"] or \
            completion.get("uses_realized_outcomes") != "true" or \
            not completion.get("disposition"):
        raise RuntimeError("historical-outcome strict completion differs")
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
    else:
        release(
            receipt_path=args.receipt, execution_path=args.execution,
            completion_path=args.completion,
        )
        print("HISTORICAL_OUTCOME_LEASE_RELEASED")


if __name__ == "__main__":
    main()
