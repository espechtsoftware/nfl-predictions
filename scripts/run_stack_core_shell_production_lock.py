#!/usr/bin/env python3
"""Create one outcome-free all-five-block stack-core/shell roster lock."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any

from google.cloud import bigquery, storage

from nfl_dfs.analysis.stack_core_shell import (
    build_production_form,
    production_form_receipt,
)
from run_cbwu_seed_order_audit import _upload_create_only
from run_stack_core_shell_scorefree import RUN_ID as SCORE_FREE_RUN_ID
from stack_core_shell_sources import (
    PROJECT,
    PROTOCOL_SHA256 as SCORE_FREE_PROTOCOL_SHA256,
    SOURCE_PANELS,
    load_slate_sources,
    validate_local_sources,
)


RUN_ID = "20260816-stack-core-shell-production-lock-v1"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-lock-runs/"
    f"{RUN_ID}"
)
SCORE_FREE_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-runs/"
    f"{SCORE_FREE_RUN_ID}"
)
SCORE_FREE_REPORT_URI = f"{SCORE_FREE_PREFIX}/report.json"
SCORE_FREE_COMPLETION_URI = f"{SCORE_FREE_PREFIX}/completion.txt"
HISTORICAL_PROTOCOL = Path(
    "reports/2026-08-16-stack-core-shell-historical-score-protocol.md"
)
HISTORICAL_PROTOCOL_SHA256 = (
    "f562ce6e9a7e0458a1fd3382692f6761f1d9de56edb06ab4350403584cd702fc"
)


def _parse_gcs(uri: str) -> tuple[str, str]:
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if match is None or uri.endswith("/") or ".." in match.group(2).split("/"):
        raise RuntimeError("stack-core/shell lock GCS URI differs")
    return match.group(1), match.group(2)


def _download(
    client: storage.Client, uri: str, expected_sha256: str,
) -> tuple[bytes, dict[str, Any]]:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise RuntimeError("stack-core/shell lock input hash differs")
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name)
    blob.reload()
    raw = blob.download_as_bytes()
    digest = sha256(raw).hexdigest()
    if digest != expected_sha256 or int(blob.size or -1) != len(raw) or not str(
        blob.generation or ""
    ).isdigit():
        raise RuntimeError("stack-core/shell lock input object differs")
    return raw, {
        "uri": uri,
        "sha256": digest,
        "bytes": len(raw),
        "generation": str(blob.generation),
        "updated": blob.updated.isoformat() if blob.updated else None,
    }


def _scorefree_license(
    client: storage.Client,
    *,
    report_sha256: str,
    completion_sha256: str,
) -> dict[str, object]:
    report_raw, report_receipt = _download(
        client, SCORE_FREE_REPORT_URI, report_sha256,
    )
    completion_raw, completion_receipt = _download(
        client, SCORE_FREE_COMPLETION_URI, completion_sha256,
    )
    report = json.loads(report_raw)
    completion = dict(
        line.split("=", 1)
        for line in completion_raw.decode("utf-8").splitlines()
        if "=" in line
    )
    gate = report.get("gate", {})
    if report.get("version") != "stack-core-shell-scorefree-report-v1" or \
            report.get("run_id") != SCORE_FREE_RUN_ID or \
            report.get("uses_realized_outcomes") is not False or \
            report.get("production_change_licensed") is not False or \
            report.get("historical_scoring_licensed") is not True or \
            report.get("protocol_sha256") != SCORE_FREE_PROTOCOL_SHA256 or \
            report.get("source_hashes") != validate_local_sources() or \
            report.get("source_panels") != list(SOURCE_PANELS) or \
            report.get("disposition") != "stack-core-shell-shadow-licensed" or \
            gate.get("passes_scorefree_gate") is not True or \
            gate.get("disposition") != "stack-core-shell-shadow-licensed" or \
            report.get("mechanical") != {
                "seasons": [2023, 2024, 2025], "slates": 54,
                "heldout_folds": 270, "worlds_per_fold": 10_000,
                "source_artifacts": 270, "all_valid": True,
            }:
        raise RuntimeError("stack-core/shell score-free license differs")
    expected_completion = {
        "run_id": SCORE_FREE_RUN_ID,
        "report_sha256": report_sha256,
        "disposition": "stack-core-shell-shadow-licensed",
        "uses_realized_outcomes": "false",
        "historical_scoring_licensed": "true",
        "production_change_licensed": "false",
    }
    if any(completion.get(key) != value for key, value in expected_completion.items()):
        raise RuntimeError("stack-core/shell score-free completion differs")
    ledger_sha256 = completion.get("accepted_execution_ledger_sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", ledger_sha256):
        raise RuntimeError("stack-core/shell accepted execution ledger differs")
    return {
        "report": report_receipt,
        "completion": completion_receipt,
        "scorefree_code_sha": report.get("code_sha"),
        "scorefree_image": report.get("analysis_image"),
        "scorefree_execution_ledger_sha256": ledger_sha256,
        "disposition": report["disposition"],
    }


def run(
    season: int,
    week: int,
    output_uri: str,
    scorefree_report_sha256: str,
    scorefree_completion_sha256: str,
) -> dict[str, object]:
    expected_uri = f"{OUTPUT_PREFIX}/slate-{season}-{week}.json"
    if season not in {2023, 2024, 2025} or week not in range(1, 19) or \
            output_uri != expected_uri:
        raise RuntimeError("stack-core/shell production lock identity differs")
    if not HISTORICAL_PROTOCOL.is_file() or sha256(
        HISTORICAL_PROTOCOL.read_bytes()
    ).hexdigest() != HISTORICAL_PROTOCOL_SHA256:
        raise RuntimeError("stack-core/shell historical protocol differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("stack-core/shell lock code/image is required")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    license_receipt = _scorefree_license(
        gcs,
        report_sha256=scorefree_report_sha256,
        completion_sha256=scorefree_completion_sha256,
    )
    books, artifact_receipts = load_slate_sources(
        bq, gcs, season=season, week=week,
    )
    result = build_production_form(
        books, expected_worlds_per_block=10_000,
    )
    lock = production_form_receipt(result, season=season, week=week)
    lock["proposal_components"] = [{
        "roster": sorted(str(player) for player in proposal.lineup.ids),
        "core": list(proposal.core),
        "shell": list(proposal.shell),
        "rank": list(proposal.rank),
    } for proposal in result["proposal_receipt"]["proposals"]]
    payload = {
        "version": "stack-core-shell-production-lock-shard-v1",
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "actual_scores_queried": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": True,
        "season": season,
        "week": week,
        "code_sha": code_sha,
        "analysis_image": image,
        "historical_protocol_sha256": HISTORICAL_PROTOCOL_SHA256,
        "source_hashes": validate_local_sources(),
        "source_panels": list(SOURCE_PANELS),
        "scorefree_license": license_receipt,
        "artifact_receipts": artifact_receipts,
        "lock": lock,
    }
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("STACK_CORE_SHELL_PRODUCTION_LOCK_COMPLETE", season, week, flush=True)
    return {**payload, "output": upload}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--scorefree-report-sha256", required=True)
    parser.add_argument("--scorefree-completion-sha256", required=True)
    args = parser.parse_args()
    run(
        args.season,
        args.week,
        args.output_uri,
        args.scorefree_report_sha256,
        args.scorefree_completion_sha256,
    )


if __name__ == "__main__":
    main()
