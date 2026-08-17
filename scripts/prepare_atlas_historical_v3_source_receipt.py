#!/usr/bin/env python3
"""Seal the complete score-blind repair5 source for historical scoring v3."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

from nfl_dfs.research.atlas_historical_v3_sources import (
    EXPECTED_CELLS,
    HISTORICAL_PREFIX,
    HISTORICAL_RUN_ID,
    UPSTREAM_PREFIX,
    UPSTREAM_RUN_ID,
    build_receipt,
    canonical_json,
    loads_json,
    validate_receipt,
)
from render_atlas_matched_diversity_repair4_command import render
from run_cbwu_seed_order_audit import _parse_gcs, _upload_create_only


PROJECT = "nfl-predictions-503414"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/atlas-historical-score-runs" / HISTORICAL_RUN_ID
RECEIPT_URI = f"{HISTORICAL_PREFIX}/upstream-receipt.json"


def _object_metadata(client: storage.Client, uri: str) -> dict[str, Any]:
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name)
    blob.reload()
    if blob.generation is None or blob.size is None:
        raise RuntimeError(f"ATLAS historical v3 object metadata is incomplete: {uri}")
    return {
        "generation": str(blob.generation),
        "size": int(blob.size),
        "md5_hash": str(blob.md5_hash or ""),
        "crc32c": str(blob.crc32c or ""),
        "updated": blob.updated.isoformat() if blob.updated else "",
    }


def _job_execution_names(job: str) -> list[str]:
    command = [
        "gcloud", "run", "jobs", "executions", "list",
        "--project", PROJECT, "--region", "us-central1", "--job", job,
        "--format=value(metadata.name)",
    ]
    output = subprocess.run(
        command, check=True, text=True, capture_output=True,
    ).stdout
    names = sorted({line.strip() for line in output.splitlines() if line.strip()})
    if not names:
        raise RuntimeError(f"ATLAS historical v3 job has no execution: {job}")
    return names


def _upload_or_recover(
    client: storage.Client, raw: bytes,
) -> dict[str, str | int | bool]:
    try:
        return _upload_create_only(client, RECEIPT_URI, raw)
    except PreconditionFailed:
        bucket, name = _parse_gcs(RECEIPT_URI)
        blob = client.bucket(bucket).blob(name)
        existing = blob.download_as_bytes()
        blob.reload()
        if existing != raw or blob.generation is None:
            raise RuntimeError("ATLAS historical v3 cloud receipt differs")
        return {
            "uri": RECEIPT_URI, "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
            "create_only": True,
        }


def _seal_local_upload(
    client: storage.Client, receipt_path: Path, raw: bytes,
) -> dict[str, Any]:
    digest = sha256(raw).hexdigest()
    digest_path = OUT / "upstream-receipt.sha256"
    expected_digest_line = f"{digest}  {receipt_path}\n"
    if digest_path.exists():
        if digest_path.read_text(encoding="utf-8") != expected_digest_line:
            raise RuntimeError("ATLAS historical v3 local receipt hash differs")
    else:
        digest_path.write_text(expected_digest_line, encoding="utf-8")
    uploaded = _upload_or_recover(client, raw)
    object_raw = canonical_json(uploaded)
    object_path = OUT / "upstream-receipt-object.json"
    if object_path.exists():
        if object_path.read_bytes() != object_raw:
            raise RuntimeError("ATLAS historical v3 local object receipt differs")
    else:
        with object_path.open("xb") as handle:
            handle.write(object_raw)
    object_digest_path = OUT / "upstream-receipt-object.sha256"
    object_digest_line = f"{sha256(object_raw).hexdigest()}  {object_path}\n"
    if object_digest_path.exists():
        if object_digest_path.read_text(encoding="utf-8") != object_digest_line:
            raise RuntimeError("ATLAS historical v3 object-receipt hash differs")
    else:
        object_digest_path.write_text(object_digest_line, encoding="utf-8")
    return uploaded


def prepare() -> dict[str, Any]:
    upstream = ROOT / "reports/atlas-matched-diversity-runs" / UPSTREAM_RUN_ID
    if not (upstream / "completion.txt").is_file():
        raise RuntimeError("ATLAS historical v3 awaits strict repair5 completion")
    client = storage.Client(project=PROJECT)
    if OUT.exists():
        receipt_path = OUT / "upstream-receipt.json"
        if not receipt_path.is_file() or (OUT / "manifest.txt").exists():
            raise RuntimeError("ATLAS historical v3 immutable local run exists")
        raw = receipt_path.read_bytes()
        receipt = loads_json(raw.decode("utf-8"))
        if not isinstance(receipt, dict):
            raise RuntimeError("ATLAS historical v3 recovery receipt differs")
        validate_receipt(receipt, render(UPSTREAM_PREFIX))
        uploaded = _seal_local_upload(client, receipt_path, raw)
        print("ATLAS_HISTORICAL_V3_SOURCE_RECOVERED " + json.dumps(
            uploaded, sort_keys=True,
        ))
        return uploaded
    metadata: dict[str, dict[str, Any]] = {}
    names = ["report.json", *(f"season-{season}.json" for season in (2023, 2024, 2025))]
    names.extend(f"slate-{season}-{week}.json" for season, week in EXPECTED_CELLS)
    for name in names:
        uri = f"{UPSTREAM_PREFIX}/{name}"
        metadata[uri] = _object_metadata(client, uri)
    jobs = {
        f"atlas-md-s{season}-w{week}-r5": _job_execution_names(
            f"atlas-md-s{season}-w{week}-r5"
        )
        for season, week in EXPECTED_CELLS
    }
    grid_command = render(UPSTREAM_PREFIX)
    receipt = build_receipt(
        root=ROOT, object_metadata=metadata, job_execution_names=jobs,
        grid_command=grid_command,
    )
    raw = canonical_json(receipt)
    OUT.mkdir(parents=True, exist_ok=False)
    receipt_path = OUT / "upstream-receipt.json"
    with receipt_path.open("xb") as handle:
        handle.write(raw)
    uploaded = _seal_local_upload(client, receipt_path, raw)
    print("ATLAS_HISTORICAL_V3_SOURCE_SEALED " + json.dumps(
        uploaded, sort_keys=True,
    ))
    return uploaded


def main() -> None:
    prepare()


if __name__ == "__main__":
    main()
