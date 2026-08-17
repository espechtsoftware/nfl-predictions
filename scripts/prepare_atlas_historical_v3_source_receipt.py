#!/usr/bin/env python3
"""Seal the complete score-blind repair5 source for historical scoring v3."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

from google.cloud import storage

from nfl_dfs.research.atlas_historical_v3_sources import (
    EXPECTED_CELLS,
    HISTORICAL_PREFIX,
    HISTORICAL_RUN_ID,
    UPSTREAM_PREFIX,
    UPSTREAM_RUN_ID,
    build_receipt,
    canonical_json,
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


def prepare() -> dict[str, Any]:
    upstream = ROOT / "reports/atlas-matched-diversity-runs" / UPSTREAM_RUN_ID
    if not (upstream / "completion.txt").is_file():
        raise RuntimeError("ATLAS historical v3 awaits strict repair5 completion")
    if OUT.exists():
        raise RuntimeError("ATLAS historical v3 immutable local source receipt exists")
    client = storage.Client(project=PROJECT)
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
    digest = sha256(raw).hexdigest()
    (OUT / "upstream-receipt.sha256").write_text(
        f"{digest}  {receipt_path}\n", encoding="utf-8",
    )
    uploaded = _upload_create_only(client, RECEIPT_URI, raw)
    object_raw = canonical_json(uploaded)
    (OUT / "upstream-receipt-object.json").write_bytes(object_raw)
    (OUT / "upstream-receipt-object.sha256").write_text(
        f"{sha256(object_raw).hexdigest()}  {OUT / 'upstream-receipt-object.json'}\n",
        encoding="utf-8",
    )
    print("ATLAS_HISTORICAL_V3_SOURCE_SEALED " + json.dumps(
        uploaded, sort_keys=True,
    ))
    return uploaded


def main() -> None:
    prepare()


if __name__ == "__main__":
    main()
