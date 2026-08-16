#!/usr/bin/env python3
"""Build the frozen hybrid GCS/BigQuery ATLAS acquisition source grid."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

from google.cloud import storage

from nfl_dfs.research.atlas_money_source_grid import (
    parse_artifact_name,
    validate_environment_receipt,
    validate_object_interval,
    validate_player_world_payload,
)
from nfl_dfs.research.atlas_money_transfer import (
    acquisition_environment,
    panel_id,
    source_environment_lever_text,
    validate_logged_source_environment,
)


SHA256_RE = re.compile(r"[0-9a-f]{64}")
PANELS = tuple(panel_id(block) for block in range(5))
SEASONS = (2023, 2024, 2025)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _execution_sources(run_dir: Path, project: str, code_sha: str) -> dict:
    result = {}
    lines = (run_dir / "executions.txt").read_text(
        encoding="utf-8",
    ).splitlines()
    if len(lines) != 15:
        raise RuntimeError("ATLAS source execution ledger differs")
    for line in lines:
        block_raw, season_raw, panel, _job, execution = line.split()
        block, season = int(block_raw), int(season_raw)
        if panel != panel_id(block) or season not in SEASONS:
            raise RuntimeError("ATLAS source execution key differs")
        key = (panel, season)
        if key in result:
            raise RuntimeError("ATLAS source execution key repeats")
        receipt = _load(
            run_dir / "environment-receipts" / f"r{block}-{season}.json"
        )
        values = validate_environment_receipt(receipt)
        if values != acquisition_environment(
            block=block, season=season, code_sha=code_sha, project=project,
        ):
            raise RuntimeError("ATLAS source environment receipt differs")
        metadata = _load(
            run_dir / "execution-metadata" / f"{execution}.json"
        )
        status = metadata.get("status", {})
        completed = [
            row for row in status.get("conditions", [])
            if row.get("type") == "Completed"
        ]
        if len(completed) != 1 or completed[0].get("status") != "True" or \
                int(status.get("succeededCount") or 0) != 1 or \
                int(status.get("failedCount") or 0) != 0 or \
                not status.get("startTime") or not status.get("completionTime"):
            raise RuntimeError("ATLAS source execution is not successful")
        result[key] = {
            "block": block,
            "season": season,
            "execution": execution,
            "start": status["startTime"],
            "complete": status["completionTime"],
            "environment_sha256": receipt["sha256"],
            "environment": values,
        }
    if set(result) != {(panel, season) for panel in PANELS for season in SEASONS}:
        raise RuntimeError("ATLAS source execution grid differs")
    return result


def _candidate_rows(raw_rows: list[dict], code_sha: str) -> dict:
    result = {}
    for row in raw_rows:
        try:
            key = (
                str(row["panel_run_id"]), int(row["season"]),
                int(row["week"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("ATLAS candidate source row is incomplete") from exc
        if key in result or key[0] not in PANELS:
            raise RuntimeError("ATLAS candidate source key differs/repeats")
        if any(int(row.get(name) or 0) != 1 for name in (
            "uri_count", "sha_count", "code_count", "lever_count",
        )):
            raise RuntimeError("ATLAS candidate source identity is ambiguous")
        if str(row.get("code_sha")) != code_sha or \
                int(row.get("source_rows") or 0) <= 0 or \
                SHA256_RE.fullmatch(
                    str(row.get("score_artifact_sha256", "")),
                ) is None:
            raise RuntimeError("ATLAS candidate source receipt differs")
        block = PANELS.index(key[0])
        validate_logged_source_environment(str(row.get("lever_env", "")), block)
        result[key] = row
    return result


def build_grid(
    *, project: str, bucket_name: str, run_dir: Path,
    bq_rows: list[dict], code_sha: str,
) -> tuple[list[dict], dict[str, int]]:
    executions = _execution_sources(run_dir, project, code_sha)
    candidate_rows = _candidate_rows(bq_rows, code_sha)
    client = storage.Client(project=project)
    bucket = client.bucket(bucket_name)
    objects = {}
    for panel in PANELS:
        prefix = f"cand_scores/{panel}/"
        for blob in client.list_blobs(bucket_name, prefix=prefix):
            parsed = parse_artifact_name(blob.name)
            key = (parsed["panel_run_id"], parsed["season"], parsed["week"])
            if key in objects:
                raise RuntimeError("ATLAS source object key repeats")
            if blob.generation is None or blob.time_created is None or \
                    blob.size is None or int(blob.size) <= 0:
                raise RuntimeError("ATLAS source object metadata is incomplete")
            objects[key] = (blob, parsed)

    slates = sorted({(season, week) for _, season, week in objects})
    expected = {
        (panel, season, week)
        for panel in PANELS for season, week in slates
    }
    if len(slates) != 54 or set(objects) != expected or \
            {season for season, _ in slates} != set(SEASONS):
        raise RuntimeError("ATLAS source object panel/slate grid differs")
    if not set(candidate_rows) <= set(objects):
        raise RuntimeError("ATLAS candidate source has an orphan cell")

    grid = []
    counts: Counter[str] = Counter()
    for key in sorted(
        objects, key=lambda item: (PANELS.index(item[0]), item[1], item[2]),
    ):
        panel, season, week = key
        block = PANELS.index(panel)
        blob, parsed = objects[key]
        execution = executions[(panel, season)]
        created = blob.time_created.isoformat()
        validate_object_interval(
            created=created,
            execution_start=execution["start"],
            execution_complete=execution["complete"],
        )
        uri = f"gs://{bucket_name}/{blob.name}"
        row = candidate_rows.get(key)
        if row is not None:
            if str(row.get("score_artifact_uri")) != uri:
                raise RuntimeError("ATLAS candidate/object URI differs")
            binding = "candidate_table"
            digest = str(row["score_artifact_sha256"])
            source_rows = int(row["source_rows"])
            lever_env = str(row["lever_env"])
            players = None
        else:
            binding = "gcs_artifact_recovery"
            summary = validate_player_world_payload(blob.download_as_bytes())
            digest = str(summary["sha256"])
            source_rows = int(summary["source_rows"])
            players = int(summary["players"])
            lever_env = source_environment_lever_text(
                execution["environment"], block,
            )
            validate_logged_source_environment(lever_env, block)
        counts[binding] += 1
        grid.append({
            "panel_run_id": panel,
            "season": season,
            "week": week,
            "slate_run_id": parsed["slate_run_id"],
            "score_artifact_uri": uri,
            "score_artifact_sha256": digest,
            "source_rows": source_rows,
            "players_if_recovered": players,
            "code_sha": code_sha,
            "lever_env": lever_env,
            "source_binding": binding,
            "execution": execution["execution"],
            "environment_sha256": execution["environment_sha256"],
            "object_generation": str(blob.generation),
            "object_time_created": created,
            "object_size": int(blob.size),
        })
    if len(grid) != 270 or sum(counts.values()) != 270:
        raise RuntimeError("ATLAS hybrid source grid differs")
    return grid, dict(sorted(counts.items()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--bq-grid", required=True, type=Path)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows = _load(args.bq_grid)
    if not isinstance(rows, list):
        raise RuntimeError("ATLAS BigQuery source grid is not a list")
    grid, counts = build_grid(
        project=args.project,
        bucket_name=args.bucket,
        run_dir=args.run_dir,
        bq_rows=rows,
        code_sha=args.code_sha,
    )
    args.output.write_text(
        json.dumps(grid, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print("ATLAS_MONEY_HYBRID_SOURCE_GRID_VALIDATED", len(grid), counts)


if __name__ == "__main__":
    main()
