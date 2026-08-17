#!/usr/bin/env python3
"""Score the frozen stack-core/shell roster locks after construction closes."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery, storage

from nfl_dfs.analysis.stack_core_shell_historical import (
    aggregate_historical,
    compare_locked_slate,
)
from aggregate_stack_core_shell_production_locks import (
    REPORT_VERSION as LOCK_REPORT_VERSION,
    validate_lock,
)
from run_cbwu_seed_order_audit import _query, _upload_create_only
from run_stack_core_shell_production_lock import (
    HISTORICAL_PROTOCOL,
    HISTORICAL_PROTOCOL_SHA256,
    RUN_ID as LOCK_RUN_ID,
)
from stack_core_shell_sources import (
    PLAYER_TABLE,
    PROJECT,
    REPAIR_PANEL,
    SOURCE_PANELS,
    SOURCE_TABLE,
    validate_local_sources,
)


RUN_ID = "20260816-stack-core-shell-historical-score-v1"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-historical-runs/"
    f"{RUN_ID}"
)
OUTPUT_URI = f"{OUTPUT_PREFIX}/report.json"
LOCK_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-lock-runs/"
    f"{LOCK_RUN_ID}"
)
LOCK_REPORT_URI = f"{LOCK_PREFIX}/report.json"
LOCK_COMPLETION_URI = f"{LOCK_PREFIX}/completion.txt"
SOURCE_ACTUAL_SQL = f"""
SELECT panel_run_id, season, week, cand_ix, players, actual_score
FROM `{SOURCE_TABLE}`
WHERE (
  panel_run_id IN UNNEST(@source_panels)
  AND NOT (panel_run_id=@r3_panel AND season=2025 AND week=1)
) OR (
  panel_run_id=@repair_panel AND season=2025 AND week=1
)
ORDER BY panel_run_id, season, week, cand_ix
"""
PLAYER_ACTUAL_SQL = f"""
SELECT season, week, id AS player_id, actual
FROM `{PLAYER_TABLE}`
WHERE panel_run_id=@r0_panel AND season IN (2023, 2024, 2025)
ORDER BY season, week, player_id
"""


def _parse_gcs(uri: str) -> tuple[str, str]:
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if match is None or uri.endswith("/") or ".." in match.group(2).split("/"):
        raise RuntimeError("stack-core/shell historical GCS URI differs")
    return match.group(1), match.group(2)


def _download(
    client: storage.Client, uri: str, expected_sha256: str,
) -> tuple[bytes, dict[str, Any]]:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise RuntimeError("stack-core/shell historical input hash differs")
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name)
    blob.reload()
    raw = blob.download_as_bytes()
    digest = sha256(raw).hexdigest()
    if digest != expected_sha256 or int(blob.size or -1) != len(raw) or \
            not str(blob.generation or "").isdigit():
        raise RuntimeError("stack-core/shell historical input object differs")
    return raw, {
        "uri": uri, "sha256": digest, "bytes": len(raw),
        "generation": str(blob.generation),
        "updated": blob.updated.isoformat() if blob.updated else None,
    }


def _lock_license(
    client: storage.Client,
    *,
    report_sha256: str,
    completion_sha256: str,
) -> tuple[dict[str, object], dict[str, object]]:
    report_raw, report_receipt = _download(
        client, LOCK_REPORT_URI, report_sha256,
    )
    completion_raw, completion_receipt = _download(
        client, LOCK_COMPLETION_URI, completion_sha256,
    )
    report = json.loads(report_raw)
    completion = dict(
        line.split("=", 1)
        for line in completion_raw.decode("utf-8").splitlines()
        if "=" in line
    )
    if report.get("version") != LOCK_REPORT_VERSION or \
            report.get("run_id") != LOCK_RUN_ID or \
            report.get("uses_realized_outcomes") is not False or \
            report.get("actual_scores_queried") is not False or \
            report.get("production_change_licensed") is not False or \
            report.get("historical_scoring_licensed") is not True or \
            report.get("historical_protocol_sha256") != HISTORICAL_PROTOCOL_SHA256 or \
            report.get("source_hashes") != validate_local_sources() or \
            report.get("source_panels") != list(SOURCE_PANELS) or \
            report.get("mechanical") != {
                "seasons": [2023, 2024, 2025], "slates": 54,
                "source_artifacts": 270, "all_valid": True,
                "rosters_locked_before_actual_query": True,
            } or not isinstance(report.get("locks"), list) or \
            len(report["locks"]) != 54 or \
            not isinstance(report.get("artifact_receipts"), list) or \
            len(report["artifact_receipts"]) != 270:
        raise RuntimeError("stack-core/shell lock report differs")
    expected_grid = [
        (season, week) for season in (2023, 2024, 2025) for week in range(1, 19)
    ]
    if [(row.get("season"), row.get("week")) for row in report["locks"]] != expected_grid:
        raise RuntimeError("stack-core/shell lock grid differs")
    for (season, week), lock in zip(expected_grid, report["locks"], strict=True):
        validate_lock(lock, season, week)
    expected_completion = {
        "run_id": LOCK_RUN_ID,
        "report_sha256": report_sha256,
        "uses_realized_outcomes": "false",
        "actual_scores_queried": "false",
        "historical_scoring_licensed": "true",
        "production_change_licensed": "false",
        "rosters_locked_before_actual_query": "true",
    }
    if any(completion.get(key) != value for key, value in expected_completion.items()) or \
            not re.fullmatch(
                r"[0-9a-f]{64}", completion.get("accepted_execution_ledger_sha256", ""),
            ):
        raise RuntimeError("stack-core/shell lock completion differs")
    return report, {
        "report": report_receipt,
        "completion": completion_receipt,
        "accepted_execution_ledger_sha256": completion[
            "accepted_execution_ledger_sha256"
        ],
        "lock_code_sha": report.get("code_sha"),
        "lock_image": report.get("analysis_image"),
        "scorefree_license": report.get("scorefree_license"),
    }


def _actual_maps(players: pd.DataFrame) -> dict[tuple[int, int], dict[str, float]]:
    if players.empty or players.duplicated(["season", "week", "player_id"]).any():
        raise RuntimeError("stack-core/shell player outcomes are missing or duplicate")
    maps = {}
    for (season, week), group in players.groupby(["season", "week"], sort=True):
        values = pd.to_numeric(group.actual, errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise RuntimeError("stack-core/shell player outcome is non-finite")
        maps[(int(season), int(week))] = {
            str(player_id): float(actual)
            for player_id, actual in zip(group.player_id, values, strict=True)
        }
    expected = {
        (season, week) for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    if set(maps) != expected:
        raise RuntimeError("stack-core/shell player outcome grid differs")
    return maps


def _native_actual_parity(
    sources: pd.DataFrame,
    actual_maps: dict[tuple[int, int], dict[str, float]],
) -> dict[str, object]:
    if len(sources) != 68_199:
        raise RuntimeError("stack-core/shell native parity row count differs")
    malformed = missing = 0
    differences = []
    for row in sources.itertuples(index=False):
        roster = [value for value in str(row.players).split(",") if value]
        if len(roster) != 9 or len(set(roster)) != 9:
            malformed += 1
            continue
        actual = actual_maps[(int(row.season), int(row.week))]
        absent = [player for player in roster if player not in actual]
        missing += len(absent)
        if absent:
            continue
        differences.append(abs(
            float(sum(actual[player] for player in roster)) - float(row.actual_score)
        ))
    maximum = float(max(differences, default=float("inf")))
    if malformed or missing or len(differences) != len(sources) or maximum > 1e-9:
        raise RuntimeError("stack-core/shell native actual-score parity differs")
    return {
        "registered_candidate_rows": len(sources), "slots_per_roster": 9,
        "malformed_rosters": malformed, "missing_player_outcomes": missing,
        "compared_rows": len(differences), "maximum_absolute_error": maximum,
        "absolute_tolerance": 1e-9, "relative_tolerance": 0.0,
        "source_storage_type": "FLOAT",
    }


def run(
    output_uri: str,
    lock_report_sha256: str,
    lock_completion_sha256: str,
) -> dict[str, object]:
    if output_uri != OUTPUT_URI:
        raise RuntimeError("stack-core/shell historical output identity differs")
    if not HISTORICAL_PROTOCOL.is_file() or sha256(
        HISTORICAL_PROTOCOL.read_bytes()
    ).hexdigest() != HISTORICAL_PROTOCOL_SHA256:
        raise RuntimeError("stack-core/shell historical protocol differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("stack-core/shell scorer code/image is required")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    lock_report, lock_receipt = _lock_license(
        gcs,
        report_sha256=lock_report_sha256,
        completion_sha256=lock_completion_sha256,
    )
    params = [
        bigquery.ArrayQueryParameter("source_panels", "STRING", list(SOURCE_PANELS)),
        bigquery.ScalarQueryParameter("r3_panel", "STRING", SOURCE_PANELS[3]),
        bigquery.ScalarQueryParameter("repair_panel", "STRING", REPAIR_PANEL),
    ]
    sources = _query(bq, SOURCE_ACTUAL_SQL, params)
    players = _query(bq, PLAYER_ACTUAL_SQL, [
        bigquery.ScalarQueryParameter("r0_panel", "STRING", SOURCE_PANELS[0]),
    ])
    actual_maps = _actual_maps(players)
    parity = _native_actual_parity(sources, actual_maps)
    rows = [
        compare_locked_slate(
            lock, actual_maps[(int(lock["season"]), int(lock["week"]))],
        )
        for lock in lock_report["locks"]
    ]
    result = aggregate_historical(rows)
    result.update({
        "run_id": RUN_ID,
        "scorer_code_sha": code_sha,
        "scorer_image": image,
        "historical_protocol_sha256": HISTORICAL_PROTOCOL_SHA256,
        "lock_receipt": lock_receipt,
        "native_actual_score_parity": parity,
        "source_artifacts": {
            "count": len(lock_report["artifact_receipts"]),
            "sha256": sha256(json.dumps(
                lock_report["artifact_receipts"],
                sort_keys=True,
                separators=(",", ":"),
            ).encode()).hexdigest(),
        },
    })
    raw = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("STACK_CORE_SHELL_HISTORICAL_SCORE_COMPLETE", result["gate"]["disposition"])
    return {**result, "output": upload}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--lock-report-sha256", required=True)
    parser.add_argument("--lock-completion-sha256", required=True)
    args = parser.parse_args()
    run(
        args.output_uri,
        args.lock_report_sha256,
        args.lock_completion_sha256,
    )


if __name__ == "__main__":
    main()
