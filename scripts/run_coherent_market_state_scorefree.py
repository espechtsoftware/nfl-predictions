#!/usr/bin/env python3
"""Run one immutable outcome-free coherent market-state slate shard."""

from __future__ import annotations

import argparse
import json
import os
import re

from google.cloud import bigquery, storage

from coherent_market_state_sources import (
    PROJECT,
    SOURCE_PANELS,
    load_slate_sources,
    validate_local_sources,
)
from nfl_dfs.analysis.coherent_market_state import (
    protocol_receipt,
    run_scorefree_slate,
)
from run_cbwu_seed_order_audit import _upload_create_only


RUN_ID = "20260816-coherent-market-state-scorefree-v1"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/coherent-market-state-runs/"
    f"{RUN_ID}"
)


def run(
    season: int,
    week: int,
    output_uri: str,
    *,
    run_id: str = RUN_ID,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict:
    expected_uri = f"{output_prefix}/slate-{season}-{week}.json"
    if season not in {2023, 2024, 2025} or week not in range(1, 19) or \
            output_uri != expected_uri or run_id != RUN_ID:
        raise RuntimeError("coherent-state shard identity differs")
    source_hashes = validate_local_sources()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("coherent-state code/image identity is required")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    books, artifact_receipts = load_slate_sources(
        bq, gcs, season=season, week=week,
    )
    result = run_scorefree_slate(
        books,
        season=season,
        week=week,
        expected_worlds_per_block=10_000,
        progress_callback=lambda block: print(
            "COHERENT_MARKET_STATE_FOLD_COMPLETE",
            season,
            week,
            block,
            flush=True,
        ),
    )
    payload = {
        "version": "coherent-market-state-scorefree-shard-v1",
        "run_id": run_id,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        "season": season,
        "week": week,
        "code_sha": code_sha,
        "analysis_image": image,
        "source_hashes": source_hashes,
        "source_panels": list(SOURCE_PANELS),
        "protocol_receipt": protocol_receipt(),
        "artifact_receipts": artifact_receipts,
        "slate": result,
    }
    raw = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("COHERENT_MARKET_STATE_SHARD_RESULT " + json.dumps(
        upload, sort_keys=True,
    ))
    return {**payload, "output": upload}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(args.season, args.week, args.output_uri)


if __name__ == "__main__":
    main()
