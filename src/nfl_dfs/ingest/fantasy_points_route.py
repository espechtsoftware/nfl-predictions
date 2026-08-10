"""Hash-locked import for licensed Fantasy Points weekly Route Share exports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from ..names import norm_name


PANEL_ID = "20260810-lockfix-e80-k1-8677d21"
TABLE = "fantasy_points_route_share"
EXPECTED_HASHES = {
    2022: "68c92bcb01a97e9e603807496b44515c599bf6dd091ac7a47ec2c2802f9b4637",
    2023: "c4940b8d7163b2baf0734b0b70d5c5c9bee456c1c004c61341ebcc5aa97a81d0",
    2024: "45b68bb3fef0cd74c96ad88943141f37865647ef699f1e41553fca895f5408f7",
    2025: "305b5ff5523e09645ef41bd7f3c1f290b035e3d97b5f1d0c942815feebc43717",
}
EXPECTED_ROWS = {2022: 647, 2023: 621, 2024: 625, 2025: 637}
WEEK_COLUMNS = tuple(f"W{week}" for week in range(1, 19))
EXPECTED_COLUMNS = (
    "Rank", "Name", "Team", "POS", "G", "Season", *WEEK_COLUMNS,
    "TM RTE %",
)
TEAM_MAP = {
    "ARZ": "ARI",
    "BLT": "BAL",
    "CLV": "CLE",
    "HST": "HOU",
    "SL": "LA",
    "STL": "LA",
    "OAK": "LV",
    "SD": "LAC",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_teams(value: object) -> tuple[str, ...]:
    teams = {
        TEAM_MAP.get(part.strip().upper(), part.strip().upper())
        for part in str(value or "").split(",") if part.strip()
    }
    return tuple(sorted(teams))


def _snapshot_maps(snapshots: pd.DataFrame) -> tuple[dict, dict]:
    needed = {"season", "gsis_id", "name", "pos", "team"}
    if missing := needed - set(snapshots.columns):
        raise ValueError(f"snapshots missing {sorted(missing)}")
    rows = snapshots.dropna(subset=["gsis_id", "name", "pos", "team"]).copy()
    rows["normalized_name"] = rows.name.map(norm_name)
    rows["pos"] = rows.pos.replace({"FB": "RB"})
    by_name: dict[tuple[str, str], set[str]] = {}
    by_season_team: dict[tuple[int, str, str, str], set[str]] = {}
    for row in rows.itertuples(index=False):
        key = (str(row.normalized_name), str(row.pos))
        by_name.setdefault(key, set()).add(str(row.gsis_id))
        team_key = (int(row.season), *key, str(row.team))
        by_season_team.setdefault(team_key, set()).add(str(row.gsis_id))
    return by_name, by_season_team


def _resolve_player(
    season: int,
    normalized_name: str,
    pos: str,
    teams: tuple[str, ...],
    by_name: dict,
    by_season_team: dict,
) -> tuple[str | None, str]:
    candidates = set(by_name.get((normalized_name, pos), set()))
    if len(candidates) == 1:
        return next(iter(candidates)), "resolved"
    team_candidates: set[str] = set()
    for team in teams:
        team_candidates.update(by_season_team.get(
            (season, normalized_name, pos, team), set()))
    if len(team_candidates) == 1:
        return next(iter(team_candidates)), "resolved"
    if candidates or team_candidates:
        return None, "ambiguous"
    return None, "unresolved"


def normalize_exports(
    frames: dict[int, pd.DataFrame],
    snapshots: pd.DataFrame,
    source_hashes: dict[int, str],
    source_files: dict[int, str] | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Validate, resolve and unpivot the four season exports."""
    if set(frames) != set(EXPECTED_HASHES):
        raise ValueError("Route Share frames must contain exactly 2022-2025")
    by_name, by_season_team = _snapshot_maps(snapshots)
    records: list[dict] = []
    source_resolution: list[str] = []
    for season in sorted(frames):
        frame = frames[season].copy()
        if tuple(frame.columns) != EXPECTED_COLUMNS:
            raise ValueError(f"{season} Route Share schema mismatch")
        if len(frame) != EXPECTED_ROWS[season]:
            raise ValueError(
                f"{season} Route Share has {len(frame)} rows, "
                f"want {EXPECTED_ROWS[season]}")
        parsed_season = pd.to_numeric(frame["Season"], errors="raise")
        if not parsed_season.eq(season).all():
            raise ValueError(f"{season} export contains another season")
        for source_row, row in frame.iterrows():
            name = "" if pd.isna(row["Name"]) else str(row["Name"]).strip()
            vendor_team = (
                "" if pd.isna(row["Team"]) else str(row["Team"]).strip())
            vendor_pos = (
                "" if pd.isna(row["POS"])
                else str(row["POS"]).strip().upper())
            if not name or not vendor_team or not vendor_pos:
                raise ValueError(f"{season} row {source_row} has blank identity")
            pos = "RB" if vendor_pos == "FB" else vendor_pos
            normalized = norm_name(name)
            teams = _canonical_teams(vendor_team)
            gsis_id, status = _resolve_player(
                season, normalized, pos, teams, by_name, by_season_team)
            source_resolution.append(status)
            for week, column in enumerate(WEEK_COLUMNS, start=1):
                value = row[column]
                if pd.isna(value) or str(value).strip() == "":
                    continue
                percentage = float(value)
                if not 0.0 <= percentage <= 100.0:
                    raise ValueError(
                        f"{season} {name} {column} outside [0, 100]")
                records.append({
                    "season": season,
                    "week": week,
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
                    "source_file": (source_files or {}).get(
                        season, f"{season}-receivingRouteShareReportExport.csv"),
                    "source_sha256": source_hashes[season],
                    "source_row": int(source_row) + 2,
                })
    out = pd.DataFrame(records)
    if out.empty:
        raise ValueError("Route Share exports have no populated weeks")
    resolved_key = out.gsis_id.fillna(
        "UNRESOLVED:" + out.normalized_name + ":" + out.pos + ":"
        + out.canonical_teams)
    out["_identity"] = resolved_key
    keys = ["season", "week", "_identity"]
    conflicts = out.groupby(keys, dropna=False).route_share_pct.nunique()
    if conflicts.gt(1).any():
        bad = conflicts[conflicts.gt(1)].index.tolist()[:5]
        raise ValueError(f"conflicting Route Share player-weeks: {bad}")
    before = len(out)
    out = out.sort_values(
        ["season", "week", "_identity", "source_row"], kind="stable",
    ).drop_duplicates(keys, keep="first")
    coalesced = before - len(out)
    out = out.drop(columns="_identity").reset_index(drop=True)
    audit = {
        "source_rows": int(sum(len(frame) for frame in frames.values())),
        "populated_week_rows": int(before),
        "normalized_week_rows": int(len(out)),
        "coalesced_identical_rows": int(coalesced),
        "resolved_source_rows": int(source_resolution.count("resolved")),
        "unresolved_source_rows": int(source_resolution.count("unresolved")),
        "ambiguous_source_rows": int(source_resolution.count("ambiguous")),
        "resolved_week_rows": int(out.gsis_id.notna().sum()),
    }
    return out, audit


def read_exports(
    input_dir: str | Path,
    snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    root = Path(input_dir)
    frames: dict[int, pd.DataFrame] = {}
    source_files: dict[int, str] = {}
    for season, expected_hash in EXPECTED_HASHES.items():
        path = root / f"{season}-receivingRouteShareReportExport.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise ValueError(
                f"{path.name} hash {actual_hash} != frozen {expected_hash}")
        frames[season] = pd.read_csv(path, encoding="utf-8-sig")
        source_files[season] = path.name
    return normalize_exports(
        frames, snapshots, EXPECTED_HASHES, source_files=source_files)


def run(input_dir: str | Path, *, write: bool = False) -> dict:
    """Audit the licensed files and optionally create the private raw table."""
    from google.api_core.exceptions import NotFound

    from ..bq import client, load_dataframe, query_df
    from ..config import settings

    snapshots = query_df(f"""
        SELECT DISTINCT season, gsis_id, name, pos, team
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id
          AND research_eligible
          AND season BETWEEN 2022 AND 2025
        """, params={"panel_id": PANEL_ID})
    rows, audit = read_exports(input_dir, snapshots)
    audit["table"] = f"{settings.raw}.{TABLE}"
    audit["write_requested"] = bool(write)
    if write:
        table_ref = f"{settings.raw}.{TABLE}"
        try:
            client().get_table(table_ref)
        except NotFound:
            payload = rows.copy()
            payload["ingested_at"] = pd.Timestamp.now(tz="UTC")
            load_dataframe(payload, table_ref, write_disposition="WRITE_EMPTY")
            audit["write_disposition"] = "created"
        else:
            existing = query_df(f"""
                SELECT COUNT(*) AS n_rows,
                       ARRAY_AGG(DISTINCT source_sha256 ORDER BY source_sha256)
                         AS hashes
                FROM `{table_ref}`
                """).iloc[0]
            wanted = sorted(EXPECTED_HASHES.values())
            present = sorted(list(existing.hashes))
            if int(existing.n_rows or 0) != len(rows) or present != wanted:
                raise RuntimeError(
                    f"refusing to overwrite non-identical {table_ref}")
            audit["write_disposition"] = "already-identical"
    print("FP_ROUTE_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit
