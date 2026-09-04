#!/usr/bin/env python3
"""Export and optionally publish the PREREG-064 common-lock market table."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from nfl_dfs.analysis.prereg064_market_extract import (
    SUPPORTED_MARKETS,
    build_market_extract,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True,
    ).strip()


def _query(client: Any, sql: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    job = client.query(sql)
    frame = job.result().to_dataframe()
    return frame, {
        "job_id": job.job_id,
        "location": job.location,
        "total_bytes_processed": int(job.total_bytes_processed or 0),
    }


def _table_identity(client: Any, name: str) -> dict[str, Any]:
    table = client.get_table(name)
    return {
        "table": name,
        "etag": table.etag,
        "modified": table.modified.isoformat() if table.modified else None,
        "num_rows": int(table.num_rows),
    }


def _upload_create_only(local: Path, uri: str) -> dict[str, Any]:
    from google.cloud import storage

    if not uri.startswith("gs://"):
        raise ValueError(f"not a GCS URI: {uri}")
    bucket_name, name = uri[5:].split("/", 1)
    blob = storage.Client().bucket(bucket_name).blob(name)
    blob.upload_from_filename(str(local), if_generation_match=0)
    blob.reload()
    return {
        "uri": uri,
        "generation": str(blob.generation),
        "metageneration": str(blob.metageneration),
        "bytes": int(blob.size),
        "crc32c": blob.crc32c,
        "md5": blob.md5_hash,
        "sha256": _sha256(local),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="nfl-predictions-503414")
    parser.add_argument("--seasons", nargs="+", type=int, default=[2023, 2024])
    parser.add_argument("--snapshot-parquet", type=Path, required=True)
    parser.add_argument("--snapshot-uri", required=True)
    parser.add_argument("--snapshot-generation", required=True)
    parser.add_argument("--snapshot-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--upload-prefix")
    args = parser.parse_args()

    from google.cloud import bigquery

    args.output_dir.mkdir(parents=True, exist_ok=True)
    client = bigquery.Client(project=args.project)
    seasons = ",".join(str(int(value)) for value in args.seasons)
    markets = ",".join(f"'{value}'" for value in sorted(SUPPORTED_MARKETS))
    props, props_job = _query(client, f"""
        SELECT season, week, event_id, commence_time, home_team, away_team,
               snapshot_ts, bookmaker, market, outcome_name, player, price,
               point, pulled_at
        FROM `{args.project}.nfl_raw.prop_lines`
        WHERE season IN ({seasons}) AND market IN ({markets})
    """)
    schedules, schedules_job = _query(client, f"""
        SELECT season, week, game_id, gameday, gametime, game_type, weekday,
               home_team, away_team
        FROM `{args.project}.nfl_raw.schedules`
        WHERE season IN ({seasons})
    """)
    actuals, actuals_job = _query(client, f"""
        SELECT season, week, gsis_id, was_active, y_targets, y_receptions,
               y_rec_yards, y_rec_tds, y_carries, y_rush_yards, y_rush_tds,
               y_pass_attempts, y_pass_yards, y_pass_tds, y_interceptions,
               y_dk_points
        FROM `{args.project}.nfl_features.player_week_training`
        WHERE season IN ({seasons})
    """)
    snapshot = pd.read_parquet(args.snapshot_parquet)
    snapshot = snapshot[snapshot.season.isin(args.seasons)].copy()
    if _sha256(args.snapshot_parquet) != args.snapshot_sha256:
        raise ValueError("snapshot SHA-256 does not match declared identity")

    extract, audit = build_market_extract(props, schedules, snapshot, actuals)
    parquet_path = args.output_dir / "prereg064_common_lock_market_extract.parquet"
    extract.to_parquet(parquet_path, index=False, compression="zstd")
    parquet_identity: dict[str, Any] = {
        "path": str(parquet_path.resolve()),
        "bytes": parquet_path.stat().st_size,
        "sha256": _sha256(parquet_path),
    }
    if args.upload_prefix:
        parquet_identity.update(_upload_create_only(
            parquet_path,
            f"{args.upload_prefix.rstrip('/')}/{parquet_path.name}",
        ))

    manifest = {
        "experiment": "092a-market",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "production_code_sha": _git_sha(),
        "contains_realized_outcomes": True,
        "purpose": "development-only PREREG-064 source scoreboard",
        "seasons_requested": args.seasons,
        "snapshot_source": {
            "uri": args.snapshot_uri,
            "generation": args.snapshot_generation,
            "sha256": args.snapshot_sha256,
        },
        "warehouse_sources": [
            _table_identity(client, f"{args.project}.nfl_raw.prop_lines"),
            _table_identity(client, f"{args.project}.nfl_raw.schedules"),
            _table_identity(
                client, f"{args.project}.nfl_features.player_week_training"
            ),
        ],
        "query_jobs": {
            "props": props_job,
            "schedules": schedules_job,
            "actuals": actuals_job,
        },
        "audit": audit,
        "artifact": parquet_identity,
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.upload_prefix:
        manifest["manifest_artifact"] = _upload_create_only(
            manifest_path,
            f"{args.upload_prefix.rstrip('/')}/{manifest_path.name}",
        )
        # The immutable remote manifest intentionally omits its own identity.
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
