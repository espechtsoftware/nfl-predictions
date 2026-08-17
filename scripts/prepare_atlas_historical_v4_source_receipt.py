#!/usr/bin/env python3
"""Seal the complete repair5/repair6 hybrid source for historical v4."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

from nfl_dfs.research.atlas_historical_v3_sources import loads_json
from nfl_dfs.research.atlas_historical_v4_sources import (
    HISTORICAL_PREFIX,
    HISTORICAL_RUN_ID,
    validate_source_receipt,
)
from nfl_dfs.research.atlas_repair6 import REPAIR6_RUN_ID, canonical_json
from nfl_dfs.research.atlas_repair6_hybrid import REPAIR5_PREFIX, REPAIR6_PREFIX
from render_atlas_matched_diversity_repair4_command import render
from run_cbwu_seed_order_audit import _parse_gcs, _upload_create_only


PROJECT = "nfl-predictions-503414"
ROOT = Path(__file__).resolve().parents[1]
HYBRID = ROOT / "reports/atlas-matched-diversity-runs" / REPAIR6_RUN_ID
OUT = ROOT / "reports/atlas-historical-score-runs" / HISTORICAL_RUN_ID
RECEIPT_URI = f"{HISTORICAL_PREFIX}/upstream-receipt.json"


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
            raise RuntimeError("ATLAS historical v4 cloud source receipt differs")
        return {
            "uri": RECEIPT_URI, "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
            "create_only": True,
        }


def _seal(client: storage.Client, receipt_path: Path, raw: bytes) -> dict[str, Any]:
    digest = sha256(raw).hexdigest()
    digest_path = OUT / "upstream-receipt.sha256"
    digest_line = f"{digest}  {receipt_path}\n"
    if digest_path.exists() and digest_path.read_text(encoding="utf-8") != digest_line:
        raise RuntimeError("ATLAS historical v4 local source hash differs")
    digest_path.write_text(digest_line, encoding="utf-8")
    uploaded = _upload_or_recover(client, raw)
    object_path = OUT / "upstream-receipt-object.json"
    object_raw = canonical_json(uploaded)
    if object_path.exists() and object_path.read_bytes() != object_raw:
        raise RuntimeError("ATLAS historical v4 local source object differs")
    if not object_path.exists():
        object_path.write_bytes(object_raw)
    object_hash = OUT / "upstream-receipt-object.sha256"
    object_hash.write_text(
        f"{sha256(object_raw).hexdigest()}  {object_path}\n", encoding="utf-8",
    )
    return uploaded


def prepare() -> dict[str, Any]:
    completion = HYBRID / "hybrid-completion.txt"
    source = HYBRID / "hybrid-population-receipt.json"
    finish_hashes = HYBRID / "hybrid-finish.sha256"
    if not completion.is_file() or not source.is_file() or not finish_hashes.is_file():
        raise RuntimeError("ATLAS historical v4 awaits the complete hybrid population")
    hashes = {
        path: digest for digest, path in (
            line.split(maxsplit=1) for line in finish_hashes.read_text(
                encoding="utf-8").splitlines() if line.strip()
        )
    }
    if hashes.get(str(source)) != sha256(source.read_bytes()).hexdigest() or \
            hashes.get(str(completion)) != sha256(completion.read_bytes()).hexdigest():
        raise RuntimeError("ATLAS historical v4 hybrid receipt is not sealed")
    raw = source.read_bytes()
    value = loads_json(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("ATLAS historical v4 hybrid receipt payload differs")
    validate_source_receipt(
        value, repair5_grid_command=render(REPAIR5_PREFIX),
        repair6_grid_command=render(REPAIR6_PREFIX),
    )
    client = storage.Client(project=PROJECT)
    if OUT.exists():
        receipt_path = OUT / "upstream-receipt.json"
        if not receipt_path.is_file() or (OUT / "manifest.txt").exists() or \
                receipt_path.read_bytes() != raw:
            raise RuntimeError("ATLAS historical v4 immutable local run exists")
        uploaded = _seal(client, receipt_path, raw)
        print("ATLAS_HISTORICAL_V4_SOURCE_RECOVERED " + json.dumps(
            uploaded, sort_keys=True,
        ))
        return uploaded
    OUT.mkdir(parents=True, exist_ok=False)
    receipt_path = OUT / "upstream-receipt.json"
    receipt_path.write_bytes(raw)
    uploaded = _seal(client, receipt_path, raw)
    print("ATLAS_HISTORICAL_V4_SOURCE_SEALED " + json.dumps(
        uploaded, sort_keys=True,
    ))
    return uploaded


def main() -> None:
    prepare()


if __name__ == "__main__":
    main()
