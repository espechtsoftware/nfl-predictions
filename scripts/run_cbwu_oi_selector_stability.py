#!/usr/bin/env python3
"""Run the frozen paired, outcome-free CBWU-OI selector diagnostic."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from google.cloud import bigquery, storage

from nfl_dfs.inference.multiseed_portfolio import (
    combine_cbwu_books,
    combine_cbwu_order_invariant_books,
)
from nfl_dfs.research.cbwu_oi_selector_stability import (
    BLOCK_COUNT,
    BOOTSTRAP_PER_BLOCK,
    BOOTSTRAP_RESAMPLES,
    ENTRY_COUNT,
    LINE,
    WORLDS_PER_BLOCK,
    analyze_paired_selector_stability,
    summarize_paired_selector_stability,
)
from nfl_dfs.research.source_preflight import (
    resolve_panel_artifacts,
    validate_execution_identity,
    verify_local_sha256,
)

from run_cbwu_seed_order_audit import (
    FORENSIC_MANIFEST_SHA256,
    PLAYER_SQL,
    PROJECT,
    SOURCE_PANEL_IDS,
    SOURCE_SQL,
    _candidate_batch,
    _download_artifact,
    _parse_gcs,
    _query,
    _upload_create_only,
    validate_scorefree_queries,
)


VERSION = "cbwu-oi-selector-stability-v1"
PROTOCOL_PATH = Path(
    "reports/2026-08-15-cbwu-oi-selector-stability-protocol.md"
)
PROTOCOL_SHA256 = (
    "81c8d0ff7750c7781e9c9181699b3bdf397d6161c8bf6e7a91025d233236cb01"
)
CBWU_REPORT_PATH = Path(
    "reports/cbwu-order-invariant-runs/"
    "20260815-cbwu-order-invariant-repair-v1/report.json"
)
CBWU_REPORT_SHA256 = (
    "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
)
OUTPUT_URI = (
    "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
    "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
    "20260815-cbwu-oi-selector-stability-v1/result.json"
)
FREQUENCY_URI = (
    "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
    "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
    "20260815-cbwu-oi-selector-stability-v1/candidate-frequencies.json.gz"
)


def _lineup_identities(batch) -> list[list[str]]:
    result = [
        sorted(str(value) for value in lineup.ids)
        for lineup in batch.candidates
    ]
    if len(result) != len({tuple(value) for value in result}):
        raise RuntimeError("selector-stability candidate identities repeat")
    return result


def _upload_frequency_artifact(
    client: storage.Client,
    uri: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    compressed = gzip.compress(encoded, compresslevel=9, mtime=0)
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name)
    digest = hashlib.sha256(compressed).hexdigest()
    blob.metadata = {
        "sha256": digest,
        "version": VERSION,
        "uses_realized_outcomes": "false",
    }
    blob.upload_from_string(
        compressed, content_type="application/gzip", if_generation_match=0,
    )
    blob.reload()
    return {
        "uri": uri,
        "generation": str(blob.generation),
        "sha256": digest,
        "compressed_bytes": len(compressed),
        "uncompressed_bytes": len(encoded),
        "content_encoding": "gzip",
        "create_only": True,
    }


def run(output_uri: str, frequency_uri: str) -> dict[str, Any]:
    if output_uri != OUTPUT_URI or frequency_uri != FREQUENCY_URI:
        raise RuntimeError("selector-stability output identity differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    validate_execution_identity(code_sha, image)
    local_receipts = verify_local_sha256({
        "protocol": (PROTOCOL_PATH, PROTOCOL_SHA256),
        "cbwu_oi_report": (CBWU_REPORT_PATH, CBWU_REPORT_SHA256),
    })
    validate_scorefree_queries()

    source_report = json.loads(CBWU_REPORT_PATH.read_text(encoding="utf-8"))
    if (
        source_report.get("uses_realized_outcomes") is not False
        or source_report.get("aggregate", {}).get(
            "passes_scorefree_gate"
        ) is not True
        or len(source_report.get("slates", [])) != 54
    ):
        raise RuntimeError("selector-stability CBWU-OI source did not pass")
    expected_by_slate = {
        (int(row["season"]), int(row["week"])): row
        for row in source_report["slates"]
    }
    if len(expected_by_slate) != 54:
        raise RuntimeError("selector-stability source slate keys repeat")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    sources = _query(bq, SOURCE_SQL, [bigquery.ArrayQueryParameter(
        "panel_ids", "STRING", list(SOURCE_PANEL_IDS),
    )])
    players = _query(bq, PLAYER_SQL)
    preflight = resolve_panel_artifacts(
        sources.to_dict("records"), panel_ids=SOURCE_PANEL_IDS,
        expected_slates=54,
    )
    if set(players.manifest_sha256.astype(str)) != {FORENSIC_MANIFEST_SHA256}:
        raise RuntimeError("selector-stability forensic manifest differs")
    slates = [tuple(int(value) for value in key)
              for key in preflight["slates"]]
    if set(slates) != set(expected_by_slate):
        raise RuntimeError("selector-stability slate population differs")
    source_map = {
        (str(row["panel_run_id"]), int(row["season"]), int(row["week"])): row
        for row in preflight["artifacts"]
    }

    records = []
    artifact_receipts = []
    for season, week in slates:
        catalog = players[
            players.season.astype(int).eq(season)
            & players.week.astype(int).eq(week)
        ].copy()
        books = {}
        for seed, panel_id in enumerate(SOURCE_PANEL_IDS):
            group = sources[
                sources.panel_run_id.astype(str).eq(panel_id)
                & sources.season.astype(int).eq(season)
                & sources.week.astype(int).eq(week)
            ].copy()
            source = source_map[(panel_id, season, week)]
            artifact, receipt = _download_artifact(
                gcs, str(source["uri"]), str(source["sha256"]),
            )
            books[f"R{seed}"] = _candidate_batch(group, artifact, catalog)
            artifact_receipts.append({
                "seed": seed,
                "panel_run_id": panel_id,
                "season": season,
                "week": week,
                "candidate_rows": int(source["source_rows"]),
                **receipt,
            })

        order = tuple(books)
        canonical = combine_cbwu_books(
            books, order, expected_worlds_per_book=WORLDS_PER_BLOCK,
        )
        rotations = tuple(order[offset:] + order[:offset] for offset in range(5))
        oi_batches = [
            combine_cbwu_order_invariant_books(
                books, rotation, tail_line=LINE,
                expected_worlds_per_book=WORLDS_PER_BLOCK,
            )
            for rotation in rotations
        ]
        oi = oi_batches[0]
        oi_identities = _lineup_identities(oi)
        if any(
            _lineup_identities(batch) != oi_identities
            or not np.array_equal(
                np.asarray(batch.candidate_totals),
                np.asarray(oi.candidate_totals),
            )
            for batch in oi_batches[1:]
        ):
            raise RuntimeError("selector-stability OI rotation differs")
        if len(canonical.candidates) != len(oi.candidates):
            raise RuntimeError("selector-stability candidate budget differs")

        expected = expected_by_slate[(season, week)]
        if expected.get("order_invariant") is not True:
            raise RuntimeError("selector-stability source rotation did not pass")
        record = analyze_paired_selector_stability(
            np.asarray(canonical.candidate_totals),
            _lineup_identities(canonical),
            expected["control"]["identities"],
            np.asarray(oi.candidate_totals),
            oi_identities,
            expected["treatment"]["identities"],
            season=season,
            week=week,
        )
        records.append(record)

    frequency_payload = {
        "version": VERSION,
        "code_sha": code_sha,
        "image": image,
        "protocol_sha256": PROTOCOL_SHA256,
        "cbwu_oi_scorefree_report_sha256": CBWU_REPORT_SHA256,
        "uses_realized_outcomes": False,
        "slates": [
            {
                "season": row["season"],
                "week": row["week"],
                **row["candidate_frequencies"],
            }
            for row in records
        ],
    }
    frequency_receipt = _upload_frequency_artifact(
        gcs, frequency_uri, frequency_payload,
    )
    report = {
        "version": VERSION,
        "code_sha": code_sha,
        "image": image,
        "protocol_sha256": PROTOCOL_SHA256,
        "cbwu_oi_scorefree_report_sha256": CBWU_REPORT_SHA256,
        "local_source_receipts": local_receipts,
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "source_panels": list(SOURCE_PANEL_IDS),
        "source_preflight": {
            key: preflight[key]
            for key in ("panel_ids", "slates", "slate_count", "artifact_count")
        },
        "source_artifacts": artifact_receipts,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "selector_tuned": False,
        "historical_arm_licensed": False,
        "production_change_licensed": False,
        "world_contract": {
            "block_count": BLOCK_COUNT,
            "worlds_per_block": WORLDS_PER_BLOCK,
            "full_worlds": BLOCK_COUNT * WORLDS_PER_BLOCK,
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "bootstrap_per_block": BOOTSTRAP_PER_BLOCK,
            "bootstrap_worlds": BLOCK_COUNT * BOOTSTRAP_PER_BLOCK,
            "entry_count": ENTRY_COUNT,
            "line": LINE,
        },
        "result": summarize_paired_selector_stability(records),
        "frequency_artifact": frequency_receipt,
        "consequence": (
            "descriptive paired selector-stability result only; cannot tune, "
            "adopt, reject or promote CBWU-OI and cannot change production"
        ),
    }
    payload = (json.dumps(
        report, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode("utf-8")
    report["output"] = _upload_create_only(gcs, output_uri, payload)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--frequency-uri", required=True)
    args = parser.parse_args()
    report = run(args.output_uri, args.frequency_uri)
    print(json.dumps({
        "version": report["version"],
        "uses_realized_outcomes": report["uses_realized_outcomes"],
        "slates": report["result"]["overall"]["slates"],
        "output": report["output"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
