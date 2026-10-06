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


MAX_ZERO_ROUTE_SHARE = 0.50   # completeness guard; see normalize (2026-09-23)
# The settle gate (reviewer + laptop, 2026-10-06): FP's first Tuesday Week-4 export carried PRELIMINARY Monday-night
# numbers (14 ATL/NO rows revised and 2 added at 10:23 CT; README deficiency log). A source week is imported only from a
# file retrieved at or after SETTLE_HOUR_CT on the day after that week's LAST kickoff (Tuesday noon after a Monday
# game); --operator-early overrides, recorded. Capture/archive is unaffected (every-paid-page rule); only the import waits.
SETTLE_HOUR_CT = 12


class RouteNotSettledError(RuntimeError):
    """An import of a source week from a file retrieved before the week's settle time."""


class RouteRevisionError(RuntimeError):
    """The vendor's export changed stored rows' CONTENT (a value changed, or a stored player is gone). Never an automatic
    delete: the repair (delete + re-import) is operator-approved. `report` carries the content diff."""

    def __init__(self, message: str, report: dict):
        super().__init__(message)
        self.report = report


def settle_time_utc(kickoffs_et: list[tuple[str, str]]) -> pd.Timestamp:
    """SETTLE_HOUR_CT (America/Chicago) on the day after the LAST kickoff, as UTC. kickoffs_et: (gameday 'YYYY-MM-DD',
    gametime 'HH:MM') pairs in US Eastern time (nflverse schedules)."""
    if not kickoffs_et:
        raise ValueError("no kickoffs for the source week: the settle time is unknown")
    last = max(pd.Timestamp(f"{d} {t}").tz_localize("America/New_York") for d, t in kickoffs_et)
    day = last.tz_convert("America/Chicago").normalize() + pd.Timedelta(days=1)
    return (day + pd.Timedelta(hours=SETTLE_HOUR_CT)).tz_convert("UTC")


def content_diff(rows: pd.DataFrame, existing: pd.DataFrame) -> dict:
    """The export against the stored rows of the same source week, by CONTENT (route_share_pct per logical identity):
    changed values, stored identities the export no longer holds, new identities, and hash-only differences."""
    keys = ["season", "week", "_identity"]
    want = rows.assign(_identity=_logical_identity(rows))[keys + ["route_share_pct", "canonical_teams", "source_sha256"]]
    have = existing.assign(_identity=_logical_identity(existing))[keys + ["route_share_pct", "canonical_teams", "source_sha256"]]
    j = want.merge(have, on=keys, how="outer", suffixes=("", "_existing"), indicator=True)
    both = j._merge.eq("both")
    same = j.route_share_pct.round(6).eq(j.route_share_pct_existing.round(6)) | (j.route_share_pct.isna() & j.route_share_pct_existing.isna())
    changed = j[both & ~same]; removed = j[j._merge.eq("right_only")]; added = j[j._merge.eq("left_only")]
    hash_only = j[both & same & j.source_sha256.ne(j.source_sha256_existing)]
    team = lambda d, c="canonical_teams": {str(k): int(v) for k, v in d[c].astype(str).value_counts().items()}
    return {"changed": int(len(changed)), "changed_by_team": team(changed), "removed": int(len(removed)),
            "removed_by_team": team(removed, "canonical_teams_existing"), "added": int(len(added)),
            "added_by_team": team(added), "hash_only": int(len(hash_only)),
            "examples": changed[keys].head(5).to_dict("records") + removed[keys].head(3).to_dict("records")}

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
    # Completeness guard (2026-09-23). The 2026-09-21 02:53Z import stored Week 2 from an export Fantasy Points had
    # not finished processing: 185 of 200 route shares were 0 (Jefferson 0 vs 95.8 final), and 67 players were
    # missing. The append-once rule then (correctly) refused the finished export, so the defect persisted until an
    # operator-approved delete. A finished week has ~7.5% zeros (20 of 265 in Week 1, 20 of 267 in Week 2).
    zero_share = float(out.route_share_pct.fillna(0).eq(0).mean()) if len(out) else 1.0
    if zero_share > MAX_ZERO_ROUTE_SHARE:
        raise ValueError(
            f"weekly Route source week looks unfinished: {zero_share:.0%} of {len(out)} route shares are 0 "
            f"(limit {MAX_ZERO_ROUTE_SHARE:.0%}); re-download after the vendor finishes processing the week")
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


MIN_ROWS_VS_PRIOR_WEEK = 0.80   # completeness guard (laptop review of 60a6042d, 2026-09-23)


def check_row_count(rows: int, prior_rows: int) -> None:
    """A finished week lists about as many players as the week before (265, then 267 in 2026); the unfinished
    2026 Week-2 export listed 200. Refuse a source week below 80% of the prior stored week (no check without one)."""
    if prior_rows > 0 and rows < MIN_ROWS_VS_PRIOR_WEEK * prior_rows:
        raise ValueError(
            f"weekly Route source week looks unfinished: {rows} rows vs {prior_rows} in the prior week "
            f"(minimum {MIN_ROWS_VS_PRIOR_WEEK:.0%}); re-download after the vendor finishes processing the week")


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
    # by CONTENT (2026-10-06): a changed value, or a stored identity the export no longer holds, is a vendor REVISION;
    # a different file hash with identical values is not (it appends nothing for those rows)
    diff = content_diff(rows, existing)
    if diff["changed"] or diff["removed"]:
        raise RouteRevisionError(
            f"weekly Route append conflicts with stored rows: {diff['examples']} -- a vendor REVISION: "
            f"{diff['changed']} changed {diff['changed_by_team']}, {diff['removed']} removed {diff['removed_by_team']}, "
            f"{diff['added']} added {diff['added_by_team']}", diff)
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
    operator_early: bool = False,
) -> dict:
    """Audit one weekly export and optionally archive/append it atomically."""
    from ..bq import load_dataframe, query_df
    from ..config import settings

    manifest, artifact = validate_manifest(input_dir, target_week=target_week)
    kick = query_df(f"""
        SELECT CAST(gameday AS STRING) AS gameday, CAST(gametime AS STRING) AS gametime
        FROM `{settings.raw}.schedules`
        WHERE CAST(season AS INT64) = @season AND CAST(week AS INT64) = @week AND game_type = 'REG'
          AND gameday IS NOT NULL AND gametime IS NOT NULL
        """, params={"season": SEASON, "week": int(artifact["source_week"])})
    settle = settle_time_utc(list(zip(kick.gameday, kick.gametime)))
    settled = bool(artifact["retrieved_at"] >= settle)
    gate = {"settle_time_utc": settle.isoformat(), "retrieved_at_utc": artifact["retrieved_at"].isoformat(),
            "settled": settled, "operator_early": bool(operator_early)}
    if not settled:
        msg = (f"Route source week {artifact['source_week']} retrieved {gate['retrieved_at_utc']}, before its settle time "
               f"{gate['settle_time_utc']} (noon CT the day after the week's last kickoff): the vendor may still revise it")
        if write and not operator_early:
            raise RouteNotSettledError(msg + "; re-download after the settle time, or pass --route-operator-early (recorded)")
        print(("OPERATOR-EARLY IMPORT (recorded): " if write else "NOTE (audit only): ") + msg, flush=True)
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
    source_week = int(artifact["source_week"])
    if source_week > 1:
        prior_rows = int(query_df(f"""
            SELECT COUNT(*) AS n FROM `{table_ref}` WHERE season = @season AND week = @prior_week
            """, params={"season": SEASON, "prior_week": source_week - 1}).n.iloc[0])
        check_row_count(len(rows), prior_rows)
    try:
        novel = rows_to_append(rows, existing)
    except RouteRevisionError as exc:
        r = exc.report
        print("!" * 100 + f"\n!!! FANTASY POINTS REVISED STORED ROUTE ROWS (source week {source_week}): {r['changed']} changed "
              f"{r['changed_by_team']}, {r['removed']} removed {r['removed_by_team']}, {r['added']} added {r['added_by_team']}. "
              "The stored rows are KEPT. The repair (delete + re-import of the revised export) is OPERATOR-APPROVED, never "
              "automatic (README deficiency log, 2026-09-21 W2 and 2026-10-06 W4).\nDEFICIENCY-LOG DRAFT: | "
              f"{datetime.now(UTC):%Y-%m-%d} | Fantasy Points revised the Week-{source_week} Route Share export after it was "
              f"stored ({r['changed']} rows changed {r['changed_by_team']}, {r['removed']} removed, {r['added']} added; new "
              f"file {artifact.get('sha256', '')[:8]}). | The stored values are stale for those players until repaired. | "
              "Awaiting the operator's approval to delete + re-import. |\n" + "!" * 100, flush=True)
        raise
    audit.update({"settle_gate": gate, "revision_check": "no stored row changed" if not existing.empty else "first import",
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
