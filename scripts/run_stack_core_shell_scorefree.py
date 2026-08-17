#!/usr/bin/env python3
"""Run one immutable score-free stack-core x shell treatment shard."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
import re

from google.cloud import bigquery, storage

from nfl_dfs.analysis.stack_core_shell import run_scorefree_slate
from run_cbwu_seed_order_audit import _upload_create_only
from stack_core_shell_sources import (
    PROJECT,
    PROTOCOL_SHA256,
    SOURCE_PANELS,
    load_slate_sources,
    validate_local_sources,
)


RUN_ID = "20260816-stack-core-shell-scorefree-v1"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-runs/"
    f"{RUN_ID}"
)
SUPPORT_RUN_ID = "20260816-stack-core-shell-control-support-census-v1"
SUPPORT_URI = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-support-runs/"
    f"{SUPPORT_RUN_ID}/report.json"
)


def _download_support(
    client: storage.Client, uri: str, expected_sha256: str,
) -> tuple[dict, dict[str, object]]:
    if uri != SUPPORT_URI or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise RuntimeError("stack-core/shell support identity differs")
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if match is None:
        raise RuntimeError("stack-core/shell support URI differs")
    blob = client.bucket(match.group(1)).blob(match.group(2))
    blob.reload()
    raw = blob.download_as_bytes()
    digest = sha256(raw).hexdigest()
    if digest != expected_sha256 or int(blob.size or -1) != len(raw) or \
            not str(blob.generation or "").isdigit():
        raise RuntimeError("stack-core/shell support artifact differs")
    report = json.loads(raw)
    anchor = report.get("selected_anchor")
    expected_disposition = {
        230: "p230-supported-stack-core-shell-treatment-licensed",
        220: "p220-supported-stack-core-shell-treatment-licensed",
        210: "p210-supported-stack-core-shell-treatment-licensed",
    }
    if report.get("version") != "stack-core-shell-control-support-report-v1" or \
            report.get("run_id") != SUPPORT_RUN_ID or \
            report.get("uses_realized_outcomes") is not False or \
            report.get("effect_fields_inspected") is not False or \
            report.get("treatment_constructed") is not False or \
            report.get("production_change_licensed") is not False or \
            report.get("historical_scoring_licensed") is not False or \
            report.get("protocol_sha256") != PROTOCOL_SHA256 or \
            report.get("mechanical") != {
                "seasons": [2023, 2024, 2025], "slates": 54,
                "heldout_folds": 270, "worlds_per_fold": 10_000,
                "source_artifacts": 270, "all_valid": True,
            } or anchor not in expected_disposition or \
            report.get("disposition") != expected_disposition[anchor] or \
            report.get("adequate_by_threshold", {}).get(str(anchor)) is not True:
        raise RuntimeError("stack-core/shell support disposition differs")
    return report, {
        "uri": uri,
        "sha256": digest,
        "bytes": len(raw),
        "generation": str(blob.generation),
        "updated": blob.updated.isoformat() if blob.updated else None,
        "selected_anchor": int(anchor),
        "disposition": report["disposition"],
    }


def run(
    season: int,
    week: int,
    output_uri: str,
    support_uri: str,
    support_sha256: str,
) -> dict:
    expected_uri = f"{OUTPUT_PREFIX}/slate-{season}-{week}.json"
    if season not in {2023, 2024, 2025} or week not in range(1, 19) or \
            output_uri != expected_uri:
        raise RuntimeError("stack-core/shell score-free shard identity differs")
    source_hashes = validate_local_sources()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("stack-core/shell score-free code/image is required")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    _support, support_receipt = _download_support(
        gcs, support_uri, support_sha256,
    )
    books, artifact_receipts = load_slate_sources(
        bq, gcs, season=season, week=week,
    )
    result = run_scorefree_slate(
        books,
        season=season,
        week=week,
        expected_worlds_per_block=10_000,
        progress_callback=lambda block: print(
            "STACK_CORE_SHELL_FOLD_COMPLETE",
            season,
            week,
            block,
            flush=True,
        ),
    )
    payload = {
        "version": "stack-core-shell-scorefree-shard-v1",
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "treatment_constructed": True,
        "effect_fields_generated": True,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        "season": season,
        "week": week,
        "code_sha": code_sha,
        "analysis_image": image,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_hashes": source_hashes,
        "source_panels": list(SOURCE_PANELS),
        "support_receipt": support_receipt,
        "artifact_receipts": artifact_receipts,
        "slate": result,
    }
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("STACK_CORE_SHELL_SHARD_COMPLETE", season, week, flush=True)
    return {**payload, "output": upload}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--support-uri", required=True)
    parser.add_argument("--support-sha256", required=True)
    args = parser.parse_args()
    run(
        args.season, args.week, args.output_uri,
        args.support_uri, args.support_sha256,
    )


if __name__ == "__main__":
    main()
