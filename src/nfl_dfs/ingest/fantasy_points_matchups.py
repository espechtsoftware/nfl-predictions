"""Validated staging and append-once loading for Fantasy Points matchups.

The Playwright collector deliberately remains separate from this module. A
download is not a consumed feature: the raw run must pass its schedule gate,
then be copied to a deterministic staging directory, then be loaded with
source hashes and an idempotent job identity. This module never changes the
existing Route Share table or model feature inputs.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import settings
from ..ops.fantasy_points_matchups import (
    MATCHUPS,
    read_matchup_pairs,
)
from ..ingest.fantasy_points_advanced import _grouped_rows

TABLE = "fantasy_points_matchups_live"
SCHEMA_VERSION = 1


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc(value: object, field: str) -> pd.Timestamp:
    stamp = pd.Timestamp(str(value))
    if stamp.tzinfo is None:
        raise ValueError(f"matchup manifest {field} must be timezone-aware")
    return stamp.tz_convert("UTC")


def _validate_raw_manifest(root: Path) -> dict[str, Any]:
    path = root / "manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("matchup capture manifest schema must be 1")
    if payload.get("status") != "complete":
        raise ValueError("matchup capture is not complete; raw artifacts retained")
    for key in ("run_id", "target_season", "target_week", "started_at_utc", "finished_at_utc"):
        if key not in payload:
            raise ValueError(f"matchup capture manifest missing {key}")
    _utc(payload["started_at_utc"], "started_at_utc")
    _utc(payload["finished_at_utc"], "finished_at_utc")
    reports = payload.get("reports")
    if not isinstance(reports, list) or len(reports) != len(MATCHUPS):
        raise ValueError("matchup capture must contain all three reports")
    if {str(item.get("key")) for item in reports} != {item.key for item in MATCHUPS}:
        raise ValueError("matchup capture reports do not match the frozen report set")
    failures = payload.get("schedule_gate_failures") or []
    if failures:
        raise ValueError(f"matchup schedule gate failed: {sorted(failures)}")
    for report in reports:
        if report.get("status") != "captured":
            raise ValueError(f"report {report.get('key')} is not captured")
        if not report.get("schedule_gate", {}).get("passes"):
            raise ValueError(f"report {report.get('key')} has a failed schedule gate")
        path_value = Path(str(report.get("path", "")))
        if path_value.name != str(report.get("path", "")):
            raise ValueError("matchup report path is not a safe filename")
        artifact = root / path_value
        if not artifact.is_file() or _sha256(artifact) != report.get("sha256"):
            raise ValueError(f"report {report.get('key')} hash or file differs")
    return payload


def _row_records(path: Path, report: str, *, target_season: int, target_week: int,
                 source_run_id: str, source_sha256: str, captured_at: str) -> list[dict[str, Any]]:
    columns, rows = _grouped_rows(path)
    records: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows, start=1):
        if report in {"qb-coverage-matchup", "wr-coverage-matchup"}:
            team = str(row.get("Player Details::Team", "")).strip().upper()
            opponent = str(row.get("Player Details::OPP", "")).strip().upper()
            source_season = int(row["Player Details::Season"])
            player = str(row.get("Player Details::Name", "")).strip() or None
        elif report == "line-matchups":
            team = str(row.get("Offense Stats::Team", "")).strip().upper()
            opponent = str(row.get("Defense Stats::Name", "")).strip()
            source_season = int(row["Team Details::Season"])
            player = None
        else:
            raise ValueError(f"unsupported matchup report {report!r}")
        if not team or not opponent:
            raise ValueError(f"{path.name} row {row_number} has blank identity")
        records.append({
            "source_run_id": source_run_id,
            "capture_id": source_run_id,
            "target_season": int(target_season),
            "target_week": int(target_week),
            "source_season": source_season,
            "report": report,
            "row_number": row_number,
            "player_name": player,
            "team_raw": team,
            "opponent_raw": opponent,
            "raw_row_json": json.dumps(row, sort_keys=True, separators=(",", ":")),
            "source_file": path.name,
            "source_sha256": source_sha256,
            "captured_at": captured_at,
        })
    return records


def stage_run(input_dir: str | Path, staging_root: str | Path) -> Path:
    """Copy a complete, schedule-gated raw run into an immutable staging run.

    Failed raw runs are never deleted. A ``staging-failure.json`` receipt is
    written beside them and the exception is re-raised for the caller.
    """
    root = Path(input_dir)
    destination = Path(staging_root) / root.name
    failure = root / "staging-failure.json"
    try:
        manifest = _validate_raw_manifest(root)
        if destination.exists():
            existing = destination / "manifest.json"
            if existing.exists() and json.loads(existing.read_text()).get("source_run_id") == manifest["run_id"]:
                return existing
            raise FileExistsError(f"staging destination already exists: {destination}")
        temp = destination.with_name(destination.name + ".staging")
        if temp.exists():
            shutil.rmtree(temp)
        temp.mkdir(parents=True)
        staged_reports = []
        for report in manifest["reports"]:
            source = root / report["path"]
            target = temp / source.name
            shutil.copy2(source, target)
            staged_reports.append({"report": report["key"], "path": target.name, "sha256": _sha256(target)})
        staged = {
            "schema_version": SCHEMA_VERSION,
            "status": "staged",
            "source_run_id": manifest["run_id"],
            "target_season": manifest["target_season"],
            "target_week": manifest["target_week"],
            "source_manifest_sha256": _sha256(root / "manifest.json"),
            "staged_at_utc": datetime.now(UTC).isoformat(),
            "reports": staged_reports,
        }
        (temp / "manifest.json").write_text(json.dumps(staged, indent=2) + "\n", encoding="utf-8")
        temp.rename(destination)
        return destination / "manifest.json"
    except Exception as exc:
        failure.write_text(json.dumps({"status": "staging_failed", "error": f"{type(exc).__name__}: {exc}", "at_utc": datetime.now(UTC).isoformat()}, indent=2) + "\n", encoding="utf-8")
        raise


def normalize_staged(input_dir: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    root = Path(input_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "staged":
        raise ValueError("matchup staging manifest is not staged")
    records: list[dict[str, Any]] = []
    for report in manifest.get("reports", []):
        path = root / report["path"]
        digest = _sha256(path)
        if digest != report.get("sha256"):
            raise ValueError(f"staged report hash differs: {path.name}")
        pairs, seasons, _ = read_matchup_pairs(path, report["report"])
        if not pairs or not seasons:
            raise ValueError(f"staged report has no valid rows: {path.name}")
        records.extend(_row_records(
            path, report["report"],
            target_season=int(manifest["target_season"]),
            target_week=int(manifest["target_week"]),
            source_run_id=str(manifest["source_run_id"]),
            source_sha256=digest,
            captured_at=str(manifest["staged_at_utc"]),
        ))
    frame = pd.DataFrame.from_records(records)
    if frame.empty or frame.duplicated(["source_run_id", "report", "row_number"]).any():
        raise ValueError("staged matchup rows are empty or duplicate")
    return frame, {"table": f"{settings.raw}.{TABLE}", "source_run_id": manifest["source_run_id"], "rows": len(frame)}


def run(input_dir: str | Path, *, write: bool = False) -> dict[str, Any]:
    """Normalize a staged run and optionally append it to BigQuery."""
    from ..bq import load_dataframe, query_df
    frame, audit = normalize_staged(input_dir)
    table = audit["table"]
    existing = pd.DataFrame()
    if write:
        existing = query_df(f"SELECT source_run_id, report, row_number, source_sha256 FROM `{table}` WHERE source_run_id = @run", params={"run": audit["source_run_id"]})
        keys = ["source_run_id", "report", "row_number"]
        if not existing.empty:
            conflicts = frame[keys + ["source_sha256"]].merge(
                existing[keys + ["source_sha256"]], on=keys, how="inner",
                suffixes=("_new", "_existing"),
            )
            if not conflicts.empty and (conflicts.source_sha256_new != conflicts.source_sha256_existing).any():
                raise RuntimeError("existing matchup rows conflict with staged source")
        novel = frame if existing.empty else frame.merge(existing[keys], on=keys, how="left", indicator=True).loc[lambda x: x._merge.eq("left_only")].drop(columns="_merge")
        if not novel.empty:
            job_id = "fp_matchups_" + hashlib.sha256((audit["source_run_id"] + "|" + str(len(frame))).encode()).hexdigest()[:32]
            load_dataframe(novel, table, write_disposition="WRITE_APPEND", partition_field="captured_at", clustering_fields=("target_season", "target_week", "report"), job_id=job_id)
        audit.update({"write": True, "append_rows": len(novel), "status": "consumed"})
    else:
        audit.update({"write": False, "append_rows": None, "status": "validated"})
    print("FP_MATCHUP_INGEST_JSON=" + json.dumps(audit, sort_keys=True))
    return audit
