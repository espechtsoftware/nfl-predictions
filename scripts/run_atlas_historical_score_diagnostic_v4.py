#!/usr/bin/env python3
"""Run the frozen ATLAS repair5/repair6 hybrid realized-score diagnostic."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

from google.cloud import bigquery, storage

from nfl_dfs.analysis.atlas_historical_score import aggregate_diagnostic
from nfl_dfs.research.atlas_historical_v3_sources import loads_json
from nfl_dfs.research.atlas_historical_v4_sources import (
    HISTORICAL_PREFIX,
    HISTORICAL_RUN_ID,
    PROTOCOL_SHA256,
    validate_shard,
    validate_source_receipt,
)
from nfl_dfs.research.atlas_repair6_hybrid import REPAIR5_PREFIX, REPAIR6_PREFIX
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
)
from run_cbwu_seed_order_audit import _parse_gcs


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "reports/2026-08-17-atlas-historical-score-v4-hybrid-protocol.md"
UPSTREAM_RECEIPT_URI = f"{HISTORICAL_PREFIX}/upstream-receipt.json"
OUTPUT_URI = f"{HISTORICAL_PREFIX}/report.json"


def _object_receipt(blob: storage.Blob, uri: str, raw: bytes) -> dict[str, Any]:
    blob.reload()
    return {
        "uri": uri, "generation": str(blob.generation or ""),
        "bytes": len(raw), "sha256": sha256(raw).hexdigest(),
        "md5_hash": str(blob.md5_hash or ""), "crc32c": str(blob.crc32c or ""),
        "updated": blob.updated.isoformat() if blob.updated else "",
    }


def _download_receipt(
    client: storage.Client, *, uri: str, generation: str, digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if uri != UPSTREAM_RECEIPT_URI or not generation.isdigit() or \
            not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise RuntimeError("ATLAS historical v4 source receipt identity differs")
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name, generation=int(generation))
    raw = blob.download_as_bytes(if_generation_match=int(generation))
    observed = _object_receipt(blob, uri, raw)
    if observed["generation"] != generation or observed["sha256"] != digest:
        raise RuntimeError("ATLAS historical v4 source receipt changed")
    value = loads_json(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("ATLAS historical v4 source receipt payload differs")
    return value, observed


def _download_shard(
    client: storage.Client, expected: Mapping[str, Any], *, season: int,
    week: int, source: str, code_sha: str, image: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    uri = str(expected.get("uri", ""))
    generation = str(expected.get("generation", ""))
    if not generation.isdigit():
        raise RuntimeError("ATLAS historical v4 shard generation differs")
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name, generation=int(generation))
    raw = blob.download_as_bytes(if_generation_match=int(generation))
    observed = _object_receipt(blob, uri, raw)
    comparable = {
        key: expected.get(key)
        for key in ("uri", "generation", "bytes", "sha256", "md5_hash", "crc32c", "updated")
    }
    if observed != comparable:
        raise RuntimeError("ATLAS historical v4 immutable shard changed")
    value = loads_json(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("ATLAS historical v4 shard JSON differs")
    row = validate_shard(
        value, season=season, week=week, source=source,
        code_sha=code_sha, image=image,
    )
    return row, observed


def run(
    *, upstream_receipt_uri: str, upstream_receipt_generation: str,
    upstream_receipt_sha256: str, output_uri: str,
) -> dict[str, Any]:
    if output_uri != OUTPUT_URI or sha256(PROTOCOL.read_bytes()).hexdigest() != \
            PROTOCOL_SHA256:
        raise RuntimeError("ATLAS historical v4 frozen identity differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("ATLAS historical v4 scorer code/image identity is required")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    receipt, receipt_object = _download_receipt(
        gcs, uri=upstream_receipt_uri,
        generation=upstream_receipt_generation,
        digest=upstream_receipt_sha256,
    )
    source = validate_source_receipt(
        receipt, repair5_grid_command=render(REPAIR5_PREFIX),
        repair6_grid_command=render(REPAIR6_PREFIX),
    )
    accepted = source["accepted_rows"]
    upstream_by_key = {}
    downloaded = {}
    for row in accepted:
        season, week = int(row[0]), int(row[1])
        source_name = row[2]
        source_code = receipt[
            "repair6_code_sha" if source_name == "repair6" else "repair5_code_sha"
        ]
        source_image = receipt[
            "repair6_image" if source_name == "repair6" else "repair5_image"
        ]
        key = f"{season}-{week}"
        slate, object_receipt = _download_shard(
            gcs, receipt["objects"][key], season=season, week=week,
            source=source_name, code_sha=source_code, image=source_image,
        )
        upstream_by_key[(season, week)] = slate
        downloaded[key] = object_receipt
    if len(upstream_by_key) != 54:
        raise RuntimeError("ATLAS historical v4 source slate grid differs")

    sources = _query(bq, SOURCE_SQL, _source_params())
    players = _query(bq, PLAYER_SQL, _player_params())
    actual_maps = _actual_maps(players)
    parity = _validate_native_actual_parity(sources, actual_maps)
    if set(upstream_by_key) != set(actual_maps):
        raise RuntimeError("ATLAS historical v4 upstream/player grid differs")

    rows = []
    artifact_receipts = []
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
            print("ATLAS_HISTORICAL_V4_SLATE_COMPLETE", season, week, flush=True)

    result = aggregate_diagnostic(rows)
    artifact_raw = json.dumps(
        artifact_receipts, sort_keys=True, separators=(",", ":"),
    ).encode()
    source_hashes = {
        "protocol": PROTOCOL_SHA256,
        "source_module": sha256((
            ROOT / "src/nfl_dfs/research/atlas_historical_v4_sources.py"
        ).read_bytes()).hexdigest(),
        "runner": sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    result.update({
        "run_id": HISTORICAL_RUN_ID, "scorer_code_sha": code_sha,
        "scorer_image": image, "source_hashes": source_hashes,
        "upstream": {
            "run_id": receipt["run_id"], "receipt_object": receipt_object,
            "population_receipt_sha256": upstream_receipt_sha256,
            "repair5_cells": 54 - len(source["eligible_cells"]),
            "repair6_cells": len(source["eligible_cells"]),
            "objects": downloaded,
            "executions": {f"{row[0]}-{row[1]}": row[4] for row in accepted},
            "disposition": receipt["disposition"],
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
    print("ATLAS_HISTORICAL_V4_RESULT " + json.dumps({
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
