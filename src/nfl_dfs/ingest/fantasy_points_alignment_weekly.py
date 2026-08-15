"""Prospective append-only Fantasy Points alignment-window ingestion.

The historical alignment importer is intentionally write-once for its frozen
2022--2025 grid.  This module owns the separate 2026 operating path: one
manifest-locked W-4..W-1 export for one target week, archived by content hash
and appended only when that target week is not already present.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .fantasy_points_advanced import _grouped_rows
from .fantasy_points_alignment_l4 import (
    MIN_PLAYER_WIDE_SLOT_ROUTES,
    MIN_TEAM_WIDE_SLOT_ROUTES,
    PLAYER_TABLE,
    TEAM_TABLE,
    _identity,
    _route_count,
)
from .fantasy_points_route import _resolve_player, _sha256, _snapshot_maps
from .fantasy_points_same_season_coverage import _csv_shape


PLAN_NAME = "2026-alignment-last-four-weekly-v1"
PLAN_SHA256 = "48e771c98f89916ae3b865e2ad8f357bf69af84eb5ed5c4148a002954390692b"
REPORT = "receiving-separation-by-alignment"
SEASON = 2026


def _utc_timestamp(value: object, field: str) -> pd.Timestamp:
    try:
        stamp = pd.Timestamp(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"weekly alignment manifest has invalid {field}") from exc
    if stamp.tzinfo is None:
        raise ValueError(f"weekly alignment manifest {field} is not timezone-aware")
    return stamp.tz_convert("UTC")


def validate_manifest(
    input_dir: str | Path, *, target_week: int,
) -> tuple[dict, dict]:
    """Validate one complete target-week alignment download."""
    target_week = int(target_week)
    if not 5 <= target_week <= 18:
        raise ValueError("weekly alignment target week must be within 5..18")
    root = Path(input_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("status") != "complete":
        raise ValueError("weekly alignment manifest is not complete schema 1")
    if not str(manifest.get("run_id", "")).endswith(f"__{PLAN_NAME}"):
        raise ValueError("weekly alignment manifest has the wrong run id")
    if manifest.get("plan_sha256") != PLAN_SHA256:
        raise ValueError("weekly alignment manifest has the wrong frozen plan hash")
    if manifest.get("selected_target_week") != target_week:
        raise ValueError("weekly alignment manifest target week differs")
    _utc_timestamp(manifest.get("started_at_utc"), "started_at_utc")
    _utc_timestamp(manifest.get("finished_at_utc"), "finished_at_utc")
    exports = manifest.get("exports")
    if not isinstance(exports, list) or len(exports) != 1:
        raise ValueError("weekly alignment manifest must contain one export")
    item = exports[0]
    expected = {
        "status": "downloaded",
        "report": REPORT,
        "season": SEASON,
        "weeks": list(range(target_week - 4, target_week)),
        "include_group_headers": True,
        "context": "Player",
        "target_week": target_week,
    }
    for name, value in expected.items():
        if item.get(name) != value:
            raise ValueError(
                f"weekly alignment export {name}={item.get(name)!r}; "
                f"expected {value!r}"
            )
    retrieved = _utc_timestamp(item.get("retrieved_at_utc"), "retrieved_at_utc")
    if not str(item.get("source_url", "")).startswith(
        "https://data.fantasypoints.com/nfl/tools/player/"
    ):
        raise ValueError("weekly alignment export has an unexpected source URL")
    relative = Path(str(item.get("path", "")))
    if not relative.name or relative != Path(relative.name):
        raise ValueError("weekly alignment export has an unsafe path")
    path = root / relative
    if not path.is_file() or _sha256(path) != item.get("sha256"):
        raise ValueError("weekly alignment artifact is missing or changed")
    if path.stat().st_size != int(item.get("bytes", -1)):
        raise ValueError("weekly alignment artifact byte count differs")
    rows, columns = _csv_shape(path)
    if rows != int(item.get("csv_rows_including_headers", -1)):
        raise ValueError("weekly alignment artifact row count differs")
    if columns != int(item.get("max_csv_columns", -1)):
        raise ValueError("weekly alignment artifact width differs")
    return manifest, {**item, "local_path": path, "retrieved_at": retrieved}


def normalize_artifact(
    manifest: dict,
    artifact: dict,
    snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Parse one W-4..W-1 Player alignment export into live table rows."""
    target_week = int(artifact["target_week"])
    columns, rows = _grouped_rows(Path(artifact["local_path"]))
    required = {
        "Player Details::Name", "Player Details::Team",
        "Player Details::POS", "Player Details::G",
        "Player Details::Season", "Overall::RTE",
        "Wide::RTE", "Slot::RTE", "Inline::RTE", "Backfield::RTE",
    }
    if missing := required - set(columns):
        raise ValueError(f"weekly alignment artifact missing {sorted(missing)}")
    by_name, by_season_team = _snapshot_maps(snapshots)
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for source_row, row in enumerate(rows, start=3):
        if int(row["Player Details::Season"]) != SEASON:
            raise ValueError("weekly alignment artifact contains another season")
        games = int(row["Player Details::G"])
        if not 1 <= games <= 4:
            raise ValueError(f"weekly alignment row {source_row} has G={games}")
        identity = _identity(row)
        if identity[1] not in {"WR", "TE"}:
            continue
        counts = {
            name: _route_count(row[f"{group}::RTE"])
            for group, name in (
                ("Overall", "overall"), ("Wide", "wide"),
                ("Slot", "slot"), ("Inline", "inline"),
                ("Backfield", "backfield"),
            )
        }
        if not all(np.isfinite(value) and value >= 0 for value in counts.values()):
            raise ValueError("weekly alignment artifact has invalid routes")
        if not np.isclose(
            counts["wide"] + counts["slot"] + counts["inline"]
            + counts["backfield"], counts["overall"], atol=1e-9, rtol=0,
        ):
            raise ValueError("weekly alignment buckets do not partition Overall")
        grouped[identity].append({
            "row": row, "source_row": source_row, "games": games,
            "counts": counts,
        })

    records: list[dict] = []
    statuses: Counter[str] = Counter()
    for identity in sorted(grouped):
        normalized_name, position, teams = identity
        group = grouped[identity]
        split = len(group) != 1 or len(teams) != 1
        first = group[0]
        gsis_id, status = _resolve_player(
            SEASON, normalized_name, position, teams,
            by_name, by_season_team,
        )
        statuses[status] += 1
        counts = {
            name: value if not split else np.nan
            for name, value in first["counts"].items()
        }
        wide_slot = counts["wide"] + counts["slot"]
        records.append({
            "season": SEASON,
            "target_week": target_week,
            "source_week_start": target_week - 4,
            "source_week_end": target_week - 1,
            "gsis_id": gsis_id,
            "resolution_status": status,
            "normalized_name": normalized_name,
            "vendor_name": first["row"]["Player Details::Name"].strip(),
            "team": teams[0] if len(teams) == 1 else None,
            "canonical_teams": ",".join(teams),
            "position": position,
            "games": first["games"],
            "split_duplicate": split,
            "overall_routes": counts["overall"],
            "wide_routes": counts["wide"],
            "slot_routes": counts["slot"],
            "inline_routes": counts["inline"],
            "backfield_routes": counts["backfield"],
            "wide_slot_routes": wide_slot,
            "player_wide_share": (
                counts["wide"] / wide_slot if wide_slot > 0 else np.nan
            ),
            "alignment_supported": bool(
                not split and gsis_id is not None
                and wide_slot >= MIN_PLAYER_WIDE_SLOT_ROUTES
            ),
            "source_run_id": manifest["run_id"],
            "source_file": artifact["path"],
            "source_sha256": artifact["sha256"],
            "source_rows": ",".join(str(item["source_row"]) for item in group),
        })
    players = pd.DataFrame(records)
    if players.empty:
        raise ValueError("weekly alignment artifact has no WR/TE rows")
    player_key = ["season", "target_week", "normalized_name", "position"]
    if players.duplicated(player_key).any():
        raise ValueError("weekly alignment import repeats player identities")

    team_source = players[players.team.notna() & ~players.split_duplicate].copy()
    teams = team_source.groupby(
        ["season", "target_week", "team"], as_index=False
    ).agg(
        wide_routes=("wide_routes", "sum"),
        slot_routes=("slot_routes", "sum"),
        inline_routes=("inline_routes", "sum"),
        player_rows=("normalized_name", "size"),
    )
    teams["wide_slot_routes"] = teams.wide_routes + teams.slot_routes
    teams["offense_wide_share"] = (
        teams.wide_routes / teams.wide_slot_routes.replace(0, np.nan)
    )
    teams["offense_alignment_supported"] = (
        teams.wide_slot_routes >= MIN_TEAM_WIDE_SLOT_ROUTES
    )
    teams["source_run_id"] = manifest["run_id"]
    teams["source_sha256"] = artifact["sha256"]
    return players, teams, {
        "player_rows": int(len(players)),
        "resolved_player_rows": int(players.gsis_id.notna().sum()),
        "supported_player_rows": int(players.alignment_supported.sum()),
        "team_rows": int(len(teams)),
        "supported_team_rows": int(teams.offense_alignment_supported.sum()),
        "unresolved_rows": int(statuses["unresolved"]),
        "ambiguous_rows": int(statuses["ambiguous"]),
    }


def _novel_or_identical(
    rows: pd.DataFrame,
    existing: pd.DataFrame,
    *,
    keys: list[str],
) -> pd.DataFrame:
    if existing.empty:
        return rows.copy()
    if missing := set([*keys, "source_sha256"]) - set(existing):
        raise ValueError(f"existing weekly alignment rows lack {sorted(missing)}")
    if existing.duplicated(keys).any():
        raise RuntimeError("existing weekly alignment rows repeat logical keys")
    joined = rows.merge(
        existing[[*keys, "source_sha256"]],
        on=keys, how="left", suffixes=("", "_existing"), indicator=True,
    )
    overlap = joined._merge.eq("both")
    if (overlap & ~joined.source_sha256.eq(joined.source_sha256_existing)).any():
        bad = joined.loc[
            overlap & ~joined.source_sha256.eq(joined.source_sha256_existing), keys
        ].to_dict("records")[:5]
        raise RuntimeError(f"weekly alignment append conflicts: {bad}")
    novel_keys = joined.loc[joined._merge.eq("left_only"), keys]
    if novel_keys.empty:
        return rows.iloc[0:0].copy()
    return rows.merge(novel_keys, on=keys, how="inner", validate="one_to_one")


def _archive_artifact(artifact: dict, bucket_name: str) -> tuple[str, str]:
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    object_name = (
        "licensed/fantasy-points/alignment/season=2026/"
        f"target_week={int(artifact['target_week']):02d}/"
        f"sha256={artifact['sha256']}/{artifact['path']}"
    )
    blob = storage.Client().bucket(bucket_name).blob(object_name)
    disposition = "created"
    try:
        blob.upload_from_filename(
            str(artifact["local_path"]), content_type="text/csv",
            if_generation_match=0,
        )
    except PreconditionFailed:
        stored_hash = hashlib.sha256(blob.download_as_bytes()).hexdigest()
        if stored_hash != artifact["sha256"]:
            raise RuntimeError("weekly alignment archive is non-identical")
        disposition = "already-identical"
    return f"gs://{bucket_name}/{object_name}", disposition


def run(
    input_dir: str | Path, *, target_week: int, write: bool = False,
) -> dict:
    from ..bq import load_dataframe, query_df
    from ..config import settings

    manifest, artifact = validate_manifest(input_dir, target_week=target_week)
    snapshots = query_df(f"""
        SELECT DISTINCT CAST(season AS INT64) AS season, gsis_id,
               full_name AS name, position AS pos, team
        FROM `{settings.raw}.rosters_weekly`
        WHERE CAST(season AS INT64)=@season
          AND CAST(week AS INT64)<=@target_week
          AND gsis_id IS NOT NULL AND full_name IS NOT NULL
        """, params={"season": SEASON, "target_week": int(target_week)})
    players, teams, audit = normalize_artifact(manifest, artifact, snapshots)
    player_ref = f"{settings.raw}.{PLAYER_TABLE}"
    team_ref = f"{settings.raw}.{TEAM_TABLE}"
    player_keys = ["season", "target_week", "normalized_name", "position"]
    team_keys = ["season", "target_week", "team"]
    existing_players = query_df(f"""
        SELECT {', '.join(player_keys)}, source_sha256
        FROM `{player_ref}` WHERE season=@season AND target_week=@target_week
        """, params={"season": SEASON, "target_week": int(target_week)})
    existing_teams = query_df(f"""
        SELECT {', '.join(team_keys)}, source_sha256
        FROM `{team_ref}` WHERE season=@season AND target_week=@target_week
        """, params={"season": SEASON, "target_week": int(target_week)})
    novel_players = _novel_or_identical(
        players, existing_players, keys=player_keys)
    novel_teams = _novel_or_identical(teams, existing_teams, keys=team_keys)
    audit.update({
        "season": SEASON,
        "target_week": int(target_week),
        "source_week_start": int(target_week) - 4,
        "source_week_end": int(target_week) - 1,
        "source_run_id": manifest["run_id"],
        "source_sha256": artifact["sha256"],
        "player_table": player_ref,
        "team_table": team_ref,
        "existing_player_rows": int(len(existing_players)),
        "existing_team_rows": int(len(existing_teams)),
        "append_player_rows": int(len(novel_players)),
        "append_team_rows": int(len(novel_teams)),
        "write_requested": bool(write),
        "point_in_time_contract": "source weeks W-4 through W-1 only",
    })
    if write:
        uri, archive_disposition = _archive_artifact(
            artifact, settings.gcs_bucket)
        audit["archive_uri"] = uri
        audit["archive_disposition"] = archive_disposition
        if not novel_players.empty:
            load_dataframe(
                novel_players, player_ref, write_disposition="WRITE_APPEND")
        if not novel_teams.empty:
            load_dataframe(novel_teams, team_ref, write_disposition="WRITE_APPEND")
        audit["player_write_disposition"] = (
            "appended" if not novel_players.empty else "already-identical"
        )
        audit["team_write_disposition"] = (
            "appended" if not novel_teams.empty else "already-identical"
        )
        audit["ingested_at"] = datetime.now(UTC).isoformat()
    print("FP_ALIGNMENT_WEEKLY_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit


__all__ = [
    "PLAN_NAME", "PLAN_SHA256", "normalize_artifact", "run",
    "validate_manifest",
]
