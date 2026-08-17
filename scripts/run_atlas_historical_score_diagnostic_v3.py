#!/usr/bin/env python3
"""Run the frozen repair5-bound ATLAS realized-score diagnostic once."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
import re
from typing import Any, Mapping

from google.cloud import bigquery, storage

from nfl_dfs.analysis.atlas_historical_score import aggregate_diagnostic
from nfl_dfs.research.atlas_historical_v3_sources import (
    EXPECTED_SOURCE_HASHES,
    HISTORICAL_PREFIX,
    HISTORICAL_RUN_ID,
    UPSTREAM_CODE_SHA,
    UPSTREAM_IMAGE,
    UPSTREAM_PREFIX,
    loads_json,
    validate_receipt,
)
from render_atlas_matched_diversity_repair4_command import render
from run_atlas_historical_score_diagnostic import (
    PLAYER_SQL,
    PROJECT,
    SOURCE_SQL,
    _actual_maps,
    _player_params,
    _query,
    _run_slate,
    _source_params,
    _upload_create_only,
    _validate_native_actual_parity,
    _validate_upstream_reports,
)
from run_cbwu_seed_order_audit import _parse_gcs


UPSTREAM_RECEIPT_URI = f"{HISTORICAL_PREFIX}/upstream-receipt.json"
OUTPUT_URI = f"{HISTORICAL_PREFIX}/report.json"


def _object_receipt(blob: storage.Blob, uri: str, raw: bytes) -> dict[str, Any]:
    blob.reload()
    return {
        "uri": uri,
        "generation": str(blob.generation or ""),
        "bytes": len(raw),
        "sha256": sha256(raw).hexdigest(),
        "md5_hash": str(blob.md5_hash or ""),
        "crc32c": str(blob.crc32c or ""),
        "updated": blob.updated.isoformat() if blob.updated else "",
    }


def _download_exact_json(
    client: storage.Client, receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    uri = str(receipt.get("uri", ""))
    generation = str(receipt.get("generation", ""))
    if not generation.isdigit():
        raise RuntimeError("ATLAS historical v3 object generation differs")
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name, generation=int(generation))
    raw = blob.download_as_bytes()
    observed = _object_receipt(blob, uri, raw)
    expected = {
        key: receipt.get(key)
        for key in (
            "uri", "generation", "bytes", "sha256", "md5_hash", "crc32c", "updated",
        )
    }
    if observed != expected:
        raise RuntimeError("ATLAS historical v3 immutable object changed")
    value = loads_json(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("ATLAS historical v3 JSON object differs")
    return value, observed


def _download_source_receipt(
    client: storage.Client, uri: str, generation: str, digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if uri != UPSTREAM_RECEIPT_URI or not generation.isdigit() or \
            not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise RuntimeError("ATLAS historical v3 source receipt identity differs")
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name, generation=int(generation))
    raw = blob.download_as_bytes()
    observed = _object_receipt(blob, uri, raw)
    if observed["generation"] != generation or observed["sha256"] != digest:
        raise RuntimeError("ATLAS historical v3 source receipt changed")
    value = loads_json(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("ATLAS historical v3 source receipt payload differs")
    return value, observed


def run(
    *, upstream_receipt_uri: str, upstream_receipt_generation: str,
    upstream_receipt_sha256: str, output_uri: str,
) -> dict[str, Any]:
    if output_uri != OUTPUT_URI:
        raise RuntimeError("ATLAS historical v3 output identity differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("ATLAS historical v3 scorer code/image identity is required")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    receipt, receipt_object = _download_source_receipt(
        gcs, upstream_receipt_uri, upstream_receipt_generation,
        upstream_receipt_sha256,
    )
    grid_command = render(UPSTREAM_PREFIX)
    source = validate_receipt(receipt, grid_command)
    upstream_reports: dict[int, dict[str, Any]] = {}
    downloaded_receipts: dict[str, dict[str, Any]] = {}
    for season in (2023, 2024, 2025):
        key = f"season-{season}"
        report, object_receipt = _download_exact_json(gcs, source["objects"][key])
        upstream_reports[season] = report
        downloaded_receipts[key] = object_receipt
    aggregate, aggregate_receipt = _download_exact_json(
        gcs, source["objects"]["report"],
    )
    downloaded_receipts["report"] = aggregate_receipt
    _validate_upstream_reports(upstream_reports, aggregate, downloaded_receipts)

    sources = _query(bq, SOURCE_SQL, _source_params())
    players = _query(bq, PLAYER_SQL, _player_params())
    actual_maps = _actual_maps(players)
    parity = _validate_native_actual_parity(sources, actual_maps)
    upstream_by_key = {
        (int(row["season"]), int(row["week"])): row
        for report in upstream_reports.values() for row in report["slates"]
    }
    if set(upstream_by_key) != set(actual_maps):
        raise RuntimeError("ATLAS historical v3 upstream/player slate grids differ")

    rows: list[dict[str, Any]] = []
    artifact_receipts: list[dict[str, Any]] = []
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            source_rows = sources[
                sources.season.astype(int).eq(season)
                & sources.week.astype(int).eq(week)
            ].copy()
            catalog = players[
                players.season.astype(int).eq(season)
                & players.week.astype(int).eq(week)
            ].copy()
            row, slate_receipts = _run_slate(
                season=season, week=week, source=source_rows, catalog=catalog,
                actual=actual_maps[(season, week)],
                upstream=upstream_by_key[(season, week)], gcs=gcs,
            )
            rows.append(row)
            artifact_receipts.extend(slate_receipts)
            print("ATLAS_HISTORICAL_V3_SLATE_COMPLETE", season, week, flush=True)

    result = aggregate_diagnostic(rows)
    artifact_raw = json.dumps(
        artifact_receipts, sort_keys=True, separators=(",", ":"),
    ).encode()
    result.update({
        "run_id": HISTORICAL_RUN_ID,
        "scorer_code_sha": code_sha,
        "scorer_image": image,
        "source_hashes": dict(EXPECTED_SOURCE_HASHES),
        "upstream": {
            "run_id": receipt["upstream_run_id"],
            "code_sha": UPSTREAM_CODE_SHA,
            "image": UPSTREAM_IMAGE,
            "receipt_object": receipt_object,
            "objects": downloaded_receipts,
            "executions": source["execution_names"],
            "strict_harvest": source["strict_harvest"],
            "attempt_disposition": receipt["attempt"]["resolution"]["disposition"],
            "scorefree_gate_passed": aggregate.get("gate", {}).get(
                "passes_scorefree_gate"
            ),
        },
        "native_actual_score_parity": parity,
        "source_artifacts": {
            "count": len(artifact_receipts),
            "sha256": sha256(artifact_raw).hexdigest(),
            "receipts": artifact_receipts,
        },
    })
    raw = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    uploaded = _upload_create_only(gcs, output_uri, raw)
    print("ATLAS_HISTORICAL_V3_RESULT " + json.dumps({
        "gate": result["gate"], "output": uploaded,
    }, sort_keys=True))
    return {**result, "output": uploaded}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-receipt-uri", required=True)
    parser.add_argument("--upstream-receipt-generation", required=True)
    parser.add_argument("--upstream-receipt-sha256", required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(
        upstream_receipt_uri=args.upstream_receipt_uri,
        upstream_receipt_generation=args.upstream_receipt_generation,
        upstream_receipt_sha256=args.upstream_receipt_sha256,
        output_uri=args.output_uri,
    )


if __name__ == "__main__":
    main()
