"""Prospective append-only 2026 Fantasy Points Defense PROE ingestion.

The historical Defense PROE import is hash-locked to four 2022--2025 season files.  This module owns the 2026
operating path, modelled on the weekly Route Share path: one frozen-plan export of the Weekly Pass Rate Over
Expectation report in the Defense context holding exactly one completed source week (target week W, source week
W-1), validated, archived by content hash and appended to the same `fantasy_points_defense_proe` table with the
same row schema (season, week, team, defense_proe_pct, ...).  Every team that played the source week (from the
schedule) must carry a value and no other team may; an existing team-week with a different value fails closed.

Backfill of 2026 Weeks 1-2 = target weeks 2 and 3:
  fantasy-points-download run --plan automation/fantasy_points/plans/2026-defense-proe-weekly-v1.json --target-week 2
  python -m nfl_dfs.ingest.fantasy_points_defense_proe_weekly <run dir> --target-week 2 [--write]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .fantasy_points_coverage import TEAM_NAMES
from .fantasy_points_defense_proe import EXPECTED_COLUMNS, TABLE, WEEK_COLUMNS
from .fantasy_points_route import _sha256


PLAN_NAME = "2026-defense-proe-weekly-v1"
PLAN_SHA256 = "b22795408a5e97707b39d6fdc33915a4f5bc89b4bfcb47a6905ccaf03e75cdfd"
SEASON = 2026
SOURCE_URL_PREFIX = "https://data.fantasypoints.com/nfl/tools/team/"


def _utc(value: object, field: str) -> pd.Timestamp:
    try:
        stamp = pd.Timestamp(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"weekly Defense PROE manifest has invalid {field}") from exc
    if stamp.tzinfo is None:
        raise ValueError(f"weekly Defense PROE manifest {field} is not timezone-aware")
    return stamp.tz_convert("UTC")


def _csv_shape(path: Path) -> tuple[int, int]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    return len(rows), max((len(row) for row in rows), default=0)


def validate_manifest(input_dir: str | Path, *, target_week: int) -> tuple[dict, dict]:
    """Validate one complete single-source-week Defense PROE download."""
    target_week = int(target_week)
    if not 2 <= target_week <= 18:
        raise ValueError("weekly Defense PROE target week must be within 2..18")
    root = Path(input_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("status") != "complete":
        raise ValueError("weekly Defense PROE manifest is not complete schema 1")
    if not str(manifest.get("run_id", "")).endswith(f"__{PLAN_NAME}"):
        raise ValueError("weekly Defense PROE manifest has the wrong run id")
    if manifest.get("plan_sha256") != PLAN_SHA256:
        raise ValueError("weekly Defense PROE manifest has the wrong frozen plan hash")
    if manifest.get("selected_target_week") != target_week:
        raise ValueError("weekly Defense PROE manifest target week differs")
    _utc(manifest.get("started_at_utc"), "started_at_utc")
    _utc(manifest.get("finished_at_utc"), "finished_at_utc")
    exports = manifest.get("exports")
    if not isinstance(exports, list) or len(exports) != 1:
        raise ValueError("weekly Defense PROE manifest must contain exactly one export")
    item = exports[0]
    expected = {"status": "downloaded", "report": "offense-proe", "season": SEASON, "weeks": [target_week - 1],
                "include_group_headers": False, "context": "Defense", "target_week": target_week}
    for name, value in expected.items():
        if item.get(name) != value:
            raise ValueError(f"weekly Defense PROE export {name}={item.get(name)!r}; expected {value!r}")
    retrieved = _utc(item.get("retrieved_at_utc"), "retrieved_at_utc")
    if not str(item.get("source_url", "")).startswith(SOURCE_URL_PREFIX):
        raise ValueError("weekly Defense PROE export has an unexpected source URL")
    relative = Path(str(item.get("path", "")))
    if not relative.name or relative != Path(relative.name):
        raise ValueError("weekly Defense PROE export has an unsafe path")
    path = root / relative
    if not path.is_file() or _sha256(path) != item.get("sha256"):
        raise ValueError("weekly Defense PROE artifact is missing or changed")
    if path.stat().st_size != int(item.get("bytes", -1)):
        raise ValueError("weekly Defense PROE artifact byte count differs")
    rows, columns = _csv_shape(path)
    if rows != int(item.get("csv_rows_including_headers", -1)) or columns != int(item.get("max_csv_columns", -1)):
        raise ValueError("weekly Defense PROE artifact shape differs from manifest")
    return manifest, {**item, "local_path": path, "source_week": target_week - 1, "retrieved_at": retrieved}


def normalize_artifact(manifest: dict, artifact: dict, teams_played: set[str]) -> pd.DataFrame:
    """Team-week rows for the one source week, in the historical table's schema."""
    path = Path(artifact["local_path"])
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    if tuple(frame.columns) != EXPECTED_COLUMNS:
        raise ValueError("weekly Defense PROE schema mismatch")
    if not pd.to_numeric(frame.Season, errors="raise").eq(SEASON).all():
        raise ValueError("weekly Defense PROE export contains another season")
    source_week = int(artifact["source_week"])
    source_column = f"W{source_week}"
    others = [column for column in WEEK_COLUMNS if column != source_column]
    if frame[others].apply(lambda col: col.str.strip().ne("")).any(axis=None):
        raise ValueError("weekly Defense PROE export contains a non-source week value")
    records: list[dict] = []
    for source_index, row in frame.iterrows():
        vendor_name = row["Name"].strip()
        if vendor_name not in TEAM_NAMES:
            raise ValueError(f"weekly Defense PROE has unmapped team {vendor_name!r}")
        cell = row[source_column].strip()
        if not cell:
            if int(row["G"] or 0) != 0:
                raise ValueError(f"weekly Defense PROE {vendor_name} has G={row['G']} but no value")
            continue
        if int(row["G"]) != 1:
            raise ValueError(f"weekly Defense PROE {vendor_name} is not a one-game window")
        value_pct = float(cell)
        if not np.isfinite(value_pct) or not -100 <= value_pct <= 100:
            raise ValueError(f"weekly Defense PROE {vendor_name} has invalid PROE")
        records.append({
            "season": SEASON,
            "week": source_week,
            "team": TEAM_NAMES[vendor_name],
            "defense_proe_pct": value_pct,
            "defense_proe": value_pct / 100.0,
            "source_file": str(artifact["path"]),
            "source_sha256": str(artifact["sha256"]),
            "source_row": int(source_index) + 2,
            "source_run_id": str(manifest["run_id"]),
        })
    out = pd.DataFrame(records)
    if out.empty:
        raise ValueError("weekly Defense PROE export has no populated team")
    if out.team.duplicated().any():
        raise ValueError("weekly Defense PROE export repeats a team")
    got = set(out.team)
    if got != set(teams_played):
        raise ValueError(f"weekly Defense PROE teams differ from the Week-{source_week} schedule: "
                         f"missing {sorted(set(teams_played) - got)}, extra {sorted(got - set(teams_played))}")
    return out


def rows_to_append(rows: pd.DataFrame, existing: pd.DataFrame) -> pd.DataFrame:
    """Team-weeks not stored yet; a stored team-week with a different value fails closed (a re-capture of an
    unchanged week is a no-op even though its file hash differs)."""
    keys = ["season", "week", "team"]
    if existing.empty:
        return rows.copy()
    if existing.duplicated(keys).any():
        raise RuntimeError("stored Defense PROE rows repeat team-weeks")
    joined = rows.merge(existing[keys + ["defense_proe_pct"]], on=keys, how="left",
                        suffixes=("", "_existing"), indicator=True)
    overlap = joined._merge.eq("both")
    changed = overlap & ~np.isclose(joined.defense_proe_pct, joined.defense_proe_pct_existing.astype(float),
                                    atol=1e-9, rtol=0)
    if changed.any():
        raise RuntimeError(f"weekly Defense PROE conflicts with stored values: "
                           f"{joined.loc[changed, keys].to_dict('records')[:5]}")
    novel = joined.loc[joined._merge.eq("left_only"), keys]
    return rows.merge(novel, on=keys, how="inner", validate="one_to_one") if len(novel) else rows.iloc[0:0].copy()


def _archive(artifact: dict, bucket_name: str) -> tuple[str, str]:
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    object_name = (f"licensed/fantasy-points/defense-proe/season={SEASON}/week={int(artifact['source_week']):02d}/"
                   f"sha256={artifact['sha256']}/{artifact['path']}")
    blob = storage.Client().bucket(bucket_name).blob(object_name)
    try:
        blob.upload_from_filename(str(artifact["local_path"]), content_type="text/csv", if_generation_match=0)
        disposition = "created"
    except PreconditionFailed:
        if hashlib.sha256(blob.download_as_bytes()).hexdigest() != artifact["sha256"]:
            raise RuntimeError("weekly Defense PROE archive object is non-identical")
        disposition = "already-identical"
    return f"gs://{bucket_name}/{object_name}", disposition


def run(input_dir: str | Path, *, target_week: int, write: bool = False) -> dict:
    from ..bq import load_dataframe, query_df
    from ..config import settings

    manifest, artifact = validate_manifest(input_dir, target_week=target_week)
    source_week = int(artifact["source_week"])
    sched = query_df(f"""
        SELECT home_team AS team FROM `{settings.raw}.schedules`
        WHERE season = @season AND week = @week AND game_type = 'REG'
        UNION DISTINCT
        SELECT away_team FROM `{settings.raw}.schedules`
        WHERE season = @season AND week = @week AND game_type = 'REG'
        """, params={"season": SEASON, "week": source_week})
    rows = normalize_artifact(manifest, artifact, set(sched.team))
    ref = f"{settings.raw}.{TABLE}"
    existing = query_df(f"""SELECT season, week, team, defense_proe_pct FROM `{ref}`
                            WHERE season = @season AND week = @week""",
                        params={"season": SEASON, "week": source_week})
    novel = rows_to_append(rows, existing)
    audit = {"table": ref, "season": SEASON, "source_week": source_week, "target_week": int(target_week),
             "source_run_id": manifest["run_id"], "source_sha256": artifact["sha256"], "rows": int(len(rows)),
             "existing_rows": int(len(existing)), "append_rows": int(len(novel)), "write_requested": bool(write),
             "point_in_time_contract": "one completed source week (W-1) per target week W"}
    if write:
        audit["archive_uri"], audit["archive_disposition"] = _archive(artifact, settings.gcs_bucket)
        if not novel.empty:
            load_dataframe(novel, ref, write_disposition="WRITE_APPEND")
        audit["write_disposition"] = "appended" if not novel.empty else "already-identical"
        audit["ingested_at"] = datetime.now(UTC).isoformat()
    print("FP_DEFENSE_PROE_WEEKLY_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fp-defense-proe-weekly", description=__doc__.splitlines()[0])
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--target-week", type=int, required=True)
    parser.add_argument("--write", action="store_true")
    a = parser.parse_args(argv)
    run(a.input_dir, target_week=a.target_week, write=a.write)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["PLAN_NAME", "PLAN_SHA256", "normalize_artifact", "rows_to_append", "run", "validate_manifest"]
