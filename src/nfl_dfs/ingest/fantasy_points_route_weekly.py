"""Prospective, manifest-locked Fantasy Points Route Share ingestion.

The historical Route Share import is deliberately hash-locked to 2022--2025.
This module owns the separate append-only 2026 operating path: exactly one
completed source week for one future target week, with immutable raw bytes and
strict point-in-time provenance.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .fantasy_points_route import (
    EXPECTED_COLUMNS,
    TABLE,
    WEEK_COLUMNS,
    _canonical_teams,
    _resolve_player,
    _sha256,
    _snapshot_maps,
)
from ..names import norm_name


PLAN_NAME = "2026-route-share-weekly-v1"
PLAN_SHA256 = "cb6cf183c9f7455344954b227100152baeded9df4d5b3699b326d5b4e6baa35a"
SEASON = 2026


def _csv_shape(path: Path) -> tuple[int, int]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    return len(rows), max((len(row) for row in rows), default=0)


def _utc_timestamp(value: object, field: str) -> pd.Timestamp:
    try:
        stamp = pd.Timestamp(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"weekly Route manifest has invalid {field}") from exc
    if stamp.tzinfo is None:
        raise ValueError(f"weekly Route manifest {field} is not timezone-aware")
    return stamp.tz_convert("UTC")


def validate_manifest(
    input_dir: str | Path,
    *,
    target_week: int,
) -> tuple[dict, dict]:
    """Validate one completed downloader run and its sole licensed artifact."""
    if not 2 <= int(target_week) <= 18:
        raise ValueError("weekly Route target week must be between 2 and 18")
    root = Path(input_dir)
    manifest_path = root / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("weekly Route manifest schema must be 1")
    if payload.get("status") != "complete":
        raise ValueError("weekly Route manifest is not complete")
    if not str(payload.get("run_id", "")).endswith(f"__{PLAN_NAME}"):
        raise ValueError("weekly Route manifest has the wrong run id")
    if payload.get("plan_sha256") != PLAN_SHA256:
        raise ValueError("weekly Route manifest has the wrong frozen plan hash")
    if payload.get("selected_target_week") != int(target_week):
        raise ValueError("weekly Route manifest target week differs from request")
    _utc_timestamp(payload.get("started_at_utc"), "started_at_utc")
    _utc_timestamp(payload.get("finished_at_utc"), "finished_at_utc")

    exports = payload.get("exports")
    if not isinstance(exports, list) or len(exports) != 1:
        raise ValueError("weekly Route manifest must contain exactly one export")
    item = exports[0]
    source_week = int(target_week) - 1
    expected = {
        "status": "downloaded",
        "report": "route-share",
        "season": SEASON,
        "weeks": [source_week],
        "include_group_headers": False,
        "context": None,
        "target_week": int(target_week),
    }
    for key, value in expected.items():
        if item.get(key) != value:
            raise ValueError(
                f"weekly Route export {key}={item.get(key)!r}; expected {value!r}"
            )
    retrieved = _utc_timestamp(item.get("retrieved_at_utc"), "retrieved_at_utc")
    if not str(item.get("source_url", "")).startswith(
        "https://data.fantasypoints.com/nfl/tools/player/"
    ):
        raise ValueError("weekly Route export has an unexpected source URL")
    relative = Path(str(item.get("path", "")))
    if not relative.name or relative != Path(relative.name):
        raise ValueError("weekly Route export has an unsafe artifact path")
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_hash = _sha256(path)
    if actual_hash != item.get("sha256"):
        raise ValueError("weekly Route artifact hash differs from manifest")
    if path.stat().st_size != int(item.get("bytes", -1)):
        raise ValueError("weekly Route artifact byte count differs from manifest")
    rows, columns = _csv_shape(path)
    if rows != int(item.get("csv_rows_including_headers", -1)):
        raise ValueError("weekly Route artifact row count differs from manifest")
    if columns != int(item.get("max_csv_columns", -1)):
        raise ValueError("weekly Route artifact width differs from manifest")
    return payload, {
        **item,
        "local_path": path,
        "source_week": source_week,
        "retrieved_at": retrieved,
    }


def normalize_artifact(
    manifest: dict,
    artifact: dict,
    snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Validate and resolve one single-week Route Share export."""
    path = Path(artifact["local_path"])
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if tuple(frame.columns) != EXPECTED_COLUMNS:
        raise ValueError("weekly Route Share schema mismatch")
    if frame.empty:
        raise ValueError("weekly Route Share export is empty")
    if not pd.to_numeric(frame["Season"], errors="raise").eq(SEASON).all():
        raise ValueError("weekly Route Share export contains another season")
    games = pd.to_numeric(frame["G"], errors="raise")
    if not games.eq(1).all():
        raise ValueError("weekly Route Share export is not a one-game window")

    source_week = int(artifact["source_week"])
    target_week = int(artifact["target_week"])
    if source_week >= target_week:
        raise ValueError("weekly Route source week is not strictly prior")
    source_column = f"W{source_week}"
    other_columns = [column for column in WEEK_COLUMNS if column != source_column]
    if frame[other_columns].notna().any(axis=None):
        raise ValueError("weekly Route export contains a non-source week value")
    if frame[source_column].isna().any():
        raise ValueError("weekly Route export contains a blank source-week value")

    by_name, by_season_team = _snapshot_maps(snapshots)
    records: list[dict] = []
    statuses: list[str] = []
    for source_row, row in frame.iterrows():
        name = "" if pd.isna(row["Name"]) else str(row["Name"]).strip()
        vendor_team = "" if pd.isna(row["Team"]) else str(row["Team"]).strip()
        vendor_pos = (
            "" if pd.isna(row["POS"]) else str(row["POS"]).strip().upper()
        )
        if not name or not vendor_team or not vendor_pos:
            raise ValueError(f"weekly Route row {source_row + 2} has blank identity")
        pos = "RB" if vendor_pos == "FB" else vendor_pos
        normalized = norm_name(name)
        teams = _canonical_teams(vendor_team)
        gsis_id, status = _resolve_player(
            SEASON,
            normalized,
            pos,
            teams,
            by_name,
            by_season_team,
        )
        percentage = float(row[source_column])
        if not 0.0 <= percentage <= 100.0:
            raise ValueError(
                f"weekly Route {name} {source_column} outside [0, 100]"
            )
        statuses.append(status)
        records.append({
            "season": SEASON,
            "week": source_week,
            "gsis_id": gsis_id,
            "resolution_status": status,
            "vendor_name": name,
            "normalized_name": normalized,
            "vendor_team": vendor_team,
            "canonical_teams": ",".join(teams),
            "vendor_pos": vendor_pos,
            "pos": pos,
            "route_share_pct": percentage,
            "route_share": percentage / 100.0,
            "source_file": str(artifact["path"]),
            "source_sha256": str(artifact["sha256"]),
            "source_row": int(source_row) + 2,
            "source_target_week": target_week,
            "source_retrieved_at": artifact["retrieved_at"],
            "source_run_id": str(manifest["run_id"]),
        })
    out = pd.DataFrame(records)
    out["_identity"] = _logical_identity(out)
    keys = ["season", "week", "_identity"]
    conflicts = out.groupby(keys, dropna=False).route_share_pct.nunique()
    if conflicts.gt(1).any():
        bad = conflicts[conflicts.gt(1)].index.tolist()[:5]
        raise ValueError(f"conflicting weekly Route player-weeks: {bad}")
    before = len(out)
    out = out.sort_values(
        ["season", "week", "_identity", "source_row"], kind="stable"
    ).drop_duplicates(keys, keep="first")
    out = out.drop(columns="_identity").reset_index(drop=True)
    return out, {
        "source_rows": int(len(frame)),
        "normalized_rows": int(len(out)),
        "coalesced_identical_rows": int(before - len(out)),
        "resolved_rows": int(out.gsis_id.notna().sum()),
        "unresolved_rows": int(statuses.count("unresolved")),
        "ambiguous_rows": int(statuses.count("ambiguous")),
        "season": SEASON,
        "source_week": source_week,
        "target_week": target_week,
        "source_sha256": str(artifact["sha256"]),
    }


def _logical_identity(frame: pd.DataFrame) -> pd.Series:
    return frame.gsis_id.fillna(
        "UNRESOLVED:"
        + frame.normalized_name.astype(str)
        + ":"
        + frame.pos.astype(str)
        + ":"
        + frame.canonical_teams.astype(str)
    )


def rows_to_append(rows: pd.DataFrame, existing: pd.DataFrame) -> pd.DataFrame:
    """Return novel logical rows; reject any prior value/hash conflict."""
    wanted = rows.copy()
    wanted["_identity"] = _logical_identity(wanted)
    if existing.empty:
        return wanted.drop(columns="_identity")
    present = existing.copy()
    required = {
        "season", "week", "gsis_id", "normalized_name", "pos",
        "canonical_teams", "route_share_pct", "source_sha256",
    }
    if missing := required - set(present.columns):
        raise ValueError(f"existing weekly Route rows missing {sorted(missing)}")
    present["_identity"] = _logical_identity(present)
    keys = ["season", "week", "_identity"]
    if present.duplicated(keys).any():
        raise RuntimeError("existing weekly Route rows contain duplicate identities")
    joined = wanted.merge(
        present[keys + ["route_share_pct", "source_sha256"]],
        on=keys,
        how="left",
        suffixes=("", "_existing"),
        indicator=True,
    )
    overlap = joined._merge.eq("both")
    same_value = joined.route_share_pct.eq(joined.route_share_pct_existing)
    same_hash = joined.source_sha256.eq(joined.source_sha256_existing)
    if (overlap & ~(same_value & same_hash)).any():
        bad = joined.loc[
            overlap & ~(same_value & same_hash), keys
        ].to_dict("records")[:5]
        raise RuntimeError(f"weekly Route append conflicts with stored rows: {bad}")
    novel_keys = joined.loc[joined._merge.eq("left_only"), keys]
    if novel_keys.empty:
        return rows.iloc[0:0].copy()
    novel = wanted.merge(novel_keys, on=keys, how="inner")
    return novel.drop(columns="_identity").reset_index(drop=True)


def _archive_object_name(artifact: dict) -> str:
    return (
        "licensed/fantasy-points/route-share/"
        f"season={SEASON}/source_week={int(artifact['source_week']):02d}/"
        f"sha256={artifact['sha256']}/{artifact['path']}"
    )


def archive_artifact(artifact: dict, bucket_name: str) -> tuple[str, str]:
    """Create the hash-addressed raw object or verify an identical prior one."""
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    object_name = _archive_object_name(artifact)
    blob = storage.Client().bucket(bucket_name).blob(object_name)
    disposition = "created"
    try:
        blob.upload_from_filename(
            str(artifact["local_path"]),
            content_type="text/csv",
            if_generation_match=0,
        )
    except PreconditionFailed:
        stored = blob.download_as_bytes()
        if hashlib.sha256(stored).hexdigest() != artifact["sha256"]:
            raise RuntimeError("hash-addressed weekly Route archive is non-identical")
        disposition = "already-identical"
    return f"gs://{bucket_name}/{object_name}", disposition


def run(
    input_dir: str | Path,
    *,
    target_week: int,
    write: bool = False,
) -> dict:
    """Audit one weekly export and optionally archive/append it atomically."""
    from ..bq import load_dataframe, query_df
    from ..config import settings

    manifest, artifact = validate_manifest(input_dir, target_week=target_week)
    snapshots = query_df(f"""
        SELECT DISTINCT CAST(season AS INT64) AS season, gsis_id,
               full_name AS name, position AS pos, team
        FROM `{settings.raw}.rosters_weekly`
        WHERE CAST(season AS INT64) = @season
          AND CAST(week AS INT64) <= @target_week
          AND gsis_id IS NOT NULL AND full_name IS NOT NULL
        """, params={"season": SEASON, "target_week": int(target_week)})
    rows, audit = normalize_artifact(manifest, artifact, snapshots)
    table_ref = f"{settings.raw}.{TABLE}"
    existing = query_df(f"""
        SELECT season, week, gsis_id, normalized_name, pos, canonical_teams,
               route_share_pct, source_sha256
        FROM `{table_ref}`
        WHERE season = @season AND week = @source_week
        """, params={"season": SEASON, "source_week": int(artifact["source_week"])})
    novel = rows_to_append(rows, existing)
    audit.update({
        "table": table_ref,
        "source_run_id": manifest["run_id"],
        "write_requested": bool(write),
        "existing_rows": int(len(existing)),
        "append_rows": int(len(novel)),
        "fallback_label": (
            "route-share-unresolved-fallback"
            if not rows.gsis_id.notna().any()
            else (
                "route-share-ready-with-unresolved"
                if rows.gsis_id.isna().any()
                else "route-share-ready"
            )
        ),
    })
    if write:
        archive_uri, archive_disposition = archive_artifact(
            artifact, settings.gcs_bucket
        )
        audit["archive_uri"] = archive_uri
        audit["archive_disposition"] = archive_disposition
        if novel.empty:
            audit["write_disposition"] = "already-identical"
        else:
            payload = novel.copy()
            payload["archive_uri"] = archive_uri
            payload["ingested_at"] = datetime.now(UTC)
            load_dataframe(payload, table_ref, write_disposition="WRITE_APPEND")
            audit["write_disposition"] = "appended"
    print("FP_ROUTE_WEEKLY_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit
