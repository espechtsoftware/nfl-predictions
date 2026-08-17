#!/usr/bin/env python3
"""Validate the R5/2023 capacity canary without opening candidate content."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from google.cloud import bigquery, storage

from validate_same_law_capacity_execution import (
    execution_failures,
    scheduled_cell,
)


PROJECT = "nfl-predictions-503414"
REGION = "us-central1"
CANARY_REPLICATE = "R5"
CANARY_SEASON = 2023


def _int(value: Any, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"capacity canary {label} is not an integer") from exc
    return result


def validate_week_counts(
    rows: Sequence[Mapping[str, Any]],
    *,
    label: str,
    expected_season: int = CANARY_SEASON,
) -> list[dict[str, int]]:
    """Validate positive metadata-only row counts on all 18 weeks."""
    normalized = []
    for row in rows:
        season = _int(row.get("season"), f"{label} season")
        week = _int(row.get("week"), f"{label} week")
        count = _int(row.get("row_count"), f"{label} row count")
        if season != expected_season or not 1 <= week <= 18 or count <= 0:
            raise ValueError(f"capacity canary {label} population differs")
        normalized.append({"season": season, "week": week, "row_count": count})
    normalized.sort(key=lambda row: row["week"])
    if [row["week"] for row in normalized] != list(range(1, 19)):
        raise ValueError(f"capacity canary {label} week grid differs")
    return normalized


def validate_artifact_inventory(
    rows: Sequence[Mapping[str, Any]],
    *,
    panel_run_id: str,
    expected_season: int = CANARY_SEASON,
) -> list[dict[str, Any]]:
    """Validate exactly one positive, generation-bound artifact per week."""
    pattern = re.compile(
        rf"^cand_scores/{re.escape(panel_run_id)}/"
        rf"{expected_season}_w([1-9]|1[0-8])_[0-9a-f]{{12}}\.npz$"
    )
    normalized = []
    for row in rows:
        name = str(row.get("name", ""))
        match = pattern.fullmatch(name)
        if match is None:
            raise ValueError("capacity canary artifact identity differs")
        generation = str(row.get("generation", ""))
        size = _int(row.get("size"), "artifact size")
        if not generation.isdigit() or int(generation) <= 0 or size <= 0:
            raise ValueError("capacity canary artifact metadata differs")
        md5 = str(row.get("md5_hash", ""))
        crc32c = str(row.get("crc32c", ""))
        if not md5 or not crc32c:
            raise ValueError("capacity canary artifact checksum metadata missing")
        normalized.append({
            "season": expected_season,
            "week": int(match.group(1)),
            "uri": f"gs://{PROJECT}-raw/{name}",
            "generation": generation,
            "size": size,
            "md5_hash": md5,
            "crc32c": crc32c,
        })
    normalized.sort(key=lambda row: row["week"])
    if [row["week"] for row in normalized] != list(range(1, 19)):
        raise ValueError("capacity canary artifact week grid differs")
    return normalized


def _query(client: bigquery.Client, sql: str) -> list[dict[str, Any]]:
    return [dict(row.items()) for row in client.query(sql, location="US").result()]


def _artifact_metadata(client: storage.Client, panel: str) -> list[dict[str, Any]]:
    prefix = f"cand_scores/{panel}/{CANARY_SEASON}_w"
    return [{
        "name": blob.name,
        "generation": str(blob.generation or ""),
        "size": int(blob.size or 0),
        "md5_hash": str(blob.md5_hash or ""),
        "crc32c": str(blob.crc32c or ""),
    } for blob in client.list_blobs(f"{PROJECT}-raw", prefix=prefix)]


def validate_canary(
    execution: Mapping[str, Any],
    *,
    execution_name: str,
    bigquery_client: bigquery.Client,
    storage_client: storage.Client,
) -> dict[str, Any]:
    cell = scheduled_cell(CANARY_REPLICATE, CANARY_SEASON)
    failures = execution_failures(
        execution,
        cell=cell,
        execution_name=execution_name,
        require_success=True,
    )
    if failures:
        raise ValueError("; ".join(failures))
    panel = cell.panel_run_id
    candidate_counts = validate_week_counts(_query(bigquery_client, f"""
        SELECT season, week, COUNT(*) AS row_count
        FROM `{PROJECT}.nfl_predictions.replay_candidates_staging`
        WHERE panel_run_id = '{panel}' AND season = {CANARY_SEASON}
        GROUP BY season, week ORDER BY week
    """), label="candidate")
    feature_counts = validate_week_counts(_query(bigquery_client, f"""
        SELECT season, week, COUNT(*) AS row_count
        FROM `{PROJECT}.nfl_predictions.slate_player_features`
        WHERE panel_run_id = '{panel}' AND season = {CANARY_SEASON}
        GROUP BY season, week ORDER BY week
    """), label="feature")
    lineup_counts = validate_week_counts(_query(bigquery_client, f"""
        SELECT season, week, COUNT(*) AS row_count
        FROM `{cell.lineups_table}`
        WHERE season = {CANARY_SEASON}
        GROUP BY season, week ORDER BY week
    """), label="lineup")
    artifacts = validate_artifact_inventory(
        _artifact_metadata(storage_client, panel), panel_run_id=panel,
    )
    return {
        "version": "same-law-capacity-real-path-canary-v1",
        "status": True,
        "disposition": "metadata-only-real-path-canary-passes",
        "replicate": CANARY_REPLICATE,
        "season": CANARY_SEASON,
        "panel_run_id": panel,
        "job": cell.job,
        "execution": execution_name,
        "candidate_counts": candidate_counts,
        "feature_counts": feature_counts,
        "lineup_counts": lineup_counts,
        "artifacts": artifacts,
        "candidate_identity_opened": False,
        "candidate_score_opened": False,
        "outcome_opened": False,
        "remaining_cells_released": False,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-json", type=Path, required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("immutable capacity canary receipt already exists")
    execution = json.loads(args.execution_json.read_text(encoding="utf-8"))
    report = validate_canary(
        execution,
        execution_name=args.execution,
        bigquery_client=bigquery.Client(project=PROJECT),
        storage_client=storage.Client(project=PROJECT),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print("CAPACITY_CANARY_VERIFIED", args.execution)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
