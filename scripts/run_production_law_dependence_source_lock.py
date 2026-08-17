#!/usr/bin/env python3
"""Create the sole outcome-free input lock for production-law dependence."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re

from google.cloud import bigquery, storage
import pandas as pd

from run_cbwu_seed_order_audit import _parse_gcs, _query, _upload_create_only


PROJECT = "nfl-predictions-503414"
RUN_ID = "20260817-production-law-dependence-source-lock-v1"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/"
    f"production-law-dependence-runs/{RUN_ID}"
)
OUTPUT_URI = f"{OUTPUT_PREFIX}/source-lock.json"
PROTOCOL = Path(
    "reports/2026-08-17-production-law-dependence-remeasurement-protocol.md"
)
PROTOCOL_SHA256 = (
    "0ab5850416d856537b47bedaf23b3fdce827dcf2f99e35f589520a123b63919f"
)
TRANSFER_REPORT = Path(
    "reports/atlas-money-transfer-runs/"
    "20260815-atlas-current-money-transfer-v1/report.json"
)
TRANSFER_REPORT_SHA256 = (
    "8e568f8e5e343319ab4e4f48421b41f3266e56ecb592abce77f3ed6d246cd446"
)
CBWU_REPORT = Path(
    "reports/cbwu-order-invariant-runs/"
    "20260815-cbwu-order-invariant-repair-v1/report.json"
)
CBWU_REPORT_SHA256 = (
    "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
)
REPAIR_VALIDATION = Path(
    "reports/atlas-mvp-source-repair-runs/"
    "20260816-atlas-mvp-source-repair-r3-2025-v1/validation.json"
)
REPAIR_VALIDATION_SHA256 = (
    "4938df8c8f7f84dea40baf2f76cd84f78cdc9e1a097c271b419e3dc8c6b5cd37"
)
REPAIR_EXECUTION = REPAIR_VALIDATION.with_name("execution.json")
REPAIR_EXECUTION_SHA256 = (
    "f2bb244daf1b2d9515bee59799095fcbdd44414acb16b06e65e8298bd87c62b7"
)
REPAIR_COMPLETION = REPAIR_VALIDATION.with_name("completion.txt")
REPAIR_COMPLETION_SHA256 = (
    "7bbff5dd3721ba436f79cb984091e7aa5815642629ab2c5615a6f2d9aacaa592"
)
SOURCE_PANELS = tuple(
    f"20260815-atlas-money-worlds-r{seed}-v1" for seed in range(5)
)
PLAYER_TABLE = f"{PROJECT}.nfl_predictions.slate_player_features"
PLAYER_SQL = f"""
SELECT season, week, id AS player_id, pos AS position, team,
       proj AS mean_projection
FROM `{PLAYER_TABLE}`
WHERE panel_run_id=@r0_panel AND season IN (2023, 2024, 2025)
ORDER BY season, week, player_id
"""
FORBIDDEN_QUERY_TOKENS = (
    "actual", "score", "rank", "ownership", "selected", "payout",
    "labels_complete",
)


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _validate_local_sources() -> dict[str, str]:
    expected = {
        str(PROTOCOL): PROTOCOL_SHA256,
        str(TRANSFER_REPORT): TRANSFER_REPORT_SHA256,
        str(CBWU_REPORT): CBWU_REPORT_SHA256,
        str(REPAIR_VALIDATION): REPAIR_VALIDATION_SHA256,
        str(REPAIR_EXECUTION): REPAIR_EXECUTION_SHA256,
        str(REPAIR_COMPLETION): REPAIR_COMPLETION_SHA256,
    }
    for raw, digest in expected.items():
        path = Path(raw)
        if not path.is_file() or _file_sha(path) != digest:
            raise RuntimeError(f"production-law dependence source differs: {path}")
    present = [token for token in FORBIDDEN_QUERY_TOKENS if token in PLAYER_SQL.lower()]
    if present:
        raise RuntimeError(
            "production-law dependence catalog query is outcome-facing: "
            + ", ".join(present)
        )
    return expected


def _validate_policy_and_artifacts(transfer: dict) -> list[dict]:
    if transfer.get("version") != "atlas-current-money-transfer-v1" or \
            transfer.get("uses_realized_outcomes") is not False or \
            transfer.get("candidate_or_lineup_scores_read") is not False or \
            transfer.get("transfer_disposition", {}).get("mechanical", {}).get(
                "passes"
            ) is not True:
        raise RuntimeError("production-law dependence transfer source differs")
    receipt = transfer.get("source_policy_receipt", {})
    law = receipt.get("simulation_law", {})
    if receipt.get("policy_id") != "classic-k1-role12-boom40-poscal-cbwu-v4" or \
            law != {
                "dirichlet_k": None,
                "game_mode": "possession",
                "game_sim_usage_env": "",
                "td_ledger": False,
                "team_factors": True,
                "usage_allocation": "production-multinomial",
            } or transfer.get("source_panels") != list(SOURCE_PANELS):
        raise RuntimeError("production-law dependence policy receipt differs")
    artifacts = transfer.get("source_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 270:
        raise RuntimeError("production-law dependence artifact count differs")
    required = {
        "bytes", "candidate_rows", "generation", "panel_run_id", "season",
        "seed", "sha256", "updated", "uri", "week",
    }
    expected_grid = [
        (season, week, seed)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
        for seed in range(5)
    ]
    normalized = sorted(
        artifacts,
        key=lambda row: (int(row["season"]), int(row["week"]), int(row["seed"])),
    )
    if [(int(row["season"]), int(row["week"]), int(row["seed"]))
        for row in normalized] != expected_grid:
        raise RuntimeError("production-law dependence artifact grid differs")
    for row in normalized:
        if set(row) != required or \
                row["panel_run_id"] != SOURCE_PANELS[int(row["seed"])] or \
                not re.fullmatch(r"[0-9a-f]{64}", str(row["sha256"])) or \
                not str(row["generation"]).isdigit() or \
                not isinstance(row["bytes"], int) or row["bytes"] <= 0 or \
                not isinstance(row["candidate_rows"], int) or \
                row["candidate_rows"] < 80:
            raise RuntimeError("production-law dependence artifact receipt differs")
    return normalized


def _validate_object_metadata(gcs: storage.Client, artifacts: list[dict]) -> None:
    for index, row in enumerate(artifacts, start=1):
        bucket, name = _parse_gcs(str(row["uri"]))
        blob = gcs.bucket(bucket).blob(name)
        blob.reload()
        updated = blob.updated.isoformat() if blob.updated else ""
        if str(blob.generation) != str(row["generation"]) or \
                int(blob.size or -1) != int(row["bytes"]) or \
                updated != str(row["updated"]):
            raise RuntimeError("production-law dependence GCS source object changed")
        if index % 25 == 0 or index == len(artifacts):
            print(
                "PRODUCTION_LAW_DEPENDENCE_SOURCE_METADATA_COMPLETE",
                index, len(artifacts), flush=True,
            )


def _catalog_rows(frame: pd.DataFrame) -> list[dict]:
    expected_slates = {
        (season, week)
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    if frame.empty or frame.duplicated(["season", "week", "player_id"]).any() or \
            set(zip(frame.season.astype(int), frame.week.astype(int))) != expected_slates:
        raise RuntimeError("production-law dependence player catalog grid differs")
    projections = pd.to_numeric(frame.mean_projection, errors="coerce")
    if projections.isna().any() or not all(math.isfinite(float(value)) for value in projections):
        raise RuntimeError("production-law dependence served means are non-finite")
    rows = []
    for row, projection in zip(frame.itertuples(index=False), projections, strict=True):
        position = str(row.position).upper()
        team = str(row.team).upper()
        player_id = str(row.player_id)
        if not player_id or not position or not team:
            raise RuntimeError("production-law dependence player identity is empty")
        rows.append({
            "season": int(row.season),
            "week": int(row.week),
            "player_id": player_id,
            "position": position,
            "team": team,
            "mean_projection": float(projection),
        })
    if rows != sorted(rows, key=lambda value: (
        value["season"], value["week"], value["player_id"],
    )):
        raise RuntimeError("production-law dependence catalog order differs")
    return rows


def run(output_uri: str) -> dict:
    if output_uri != OUTPUT_URI:
        raise RuntimeError("production-law dependence source-lock URI differs")
    source_hashes = _validate_local_sources()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("production-law dependence code/image is required")

    transfer = json.loads(TRANSFER_REPORT.read_text(encoding="utf-8"))
    artifacts = _validate_policy_and_artifacts(transfer)
    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    _validate_object_metadata(gcs, artifacts)
    catalog = _query(bq, PLAYER_SQL, [
        bigquery.ScalarQueryParameter("r0_panel", "STRING", SOURCE_PANELS[0]),
    ])
    rows = _catalog_rows(catalog)
    catalog_raw = json.dumps(
        rows, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()
    eligible = [
        row for row in rows
        if row["position"] in {"QB", "RB", "WR", "TE"}
        and row["mean_projection"] >= 4.0
    ]
    if not eligible:
        raise RuntimeError("production-law dependence eligible catalog is empty")
    payload = {
        "version": "production-law-dependence-source-lock-v1",
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "actual_outcomes_queried": False,
        "candidate_or_lineup_scores_read": False,
        "production_change_licensed": False,
        "code_sha": code_sha,
        "analysis_image": image,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_hashes": source_hashes,
        "source_policy_receipt": transfer["source_policy_receipt"],
        "source_panels": list(SOURCE_PANELS),
        "artifact_count": len(artifacts),
        "artifact_receipts": artifacts,
        "catalog_rows": len(rows),
        "eligible_rows": len(eligible),
        "slates": 54,
        "catalog_sha256": sha256(catalog_raw).hexdigest(),
        "catalog": rows,
    }
    raw = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("PRODUCTION_LAW_DEPENDENCE_SOURCE_LOCK_RESULT " + json.dumps(
        upload, sort_keys=True,
    ))
    return {**payload, "output": upload}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(args.output_uri)


if __name__ == "__main__":
    main()
