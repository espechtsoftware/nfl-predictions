"""Manifest-locked import for prior-window receiver alignment routes."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from .fantasy_points_advanced import _grouped_rows, _number
from .fantasy_points_route import (
    _canonical_teams,
    _resolve_player,
    _sha256,
    _snapshot_maps,
)
from .fantasy_points_same_season_coverage import _csv_shape
from ..names import norm_name


PLAN_NAME = "same-season-alignment-last-four-v1"
REPORT = "receiving-separation-by-alignment"
SEASONS = (2022, 2023, 2024, 2025)
TARGET_WEEKS = tuple(range(5, 19))
MIN_PLAYER_WIDE_SLOT_ROUTES = 20.0
MIN_TEAM_WIDE_SLOT_ROUTES = 80.0
PLAYER_TABLE = "fantasy_points_alignment_player_l4"
TEAM_TABLE = "fantasy_points_alignment_team_l4"


def validate_manifest(input_dir: str | Path) -> tuple[dict, dict[tuple, dict]]:
    root = Path(input_dir)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError("alignment manifest schema must be 1")
    if not str(manifest.get("run_id", "")).endswith(f"__{PLAN_NAME}"):
        raise ValueError("alignment manifest has the wrong run id")
    exports = manifest.get("exports")
    expected_count = len(SEASONS) * len(TARGET_WEEKS)
    if not isinstance(exports, list) or len(exports) != expected_count:
        raise ValueError(
            f"alignment manifest has {len(exports or [])} exports; "
            f"expected {expected_count}"
        )
    keyed: dict[tuple, dict] = {}
    for item in exports:
        season = int(item.get("season", 0))
        target_week = int(item.get("target_week", 0))
        key = (season, target_week)
        if key in keyed:
            raise ValueError(f"duplicate alignment export: {key}")
        if season not in SEASONS or target_week not in TARGET_WEEKS:
            raise ValueError(f"unexpected alignment season/week: {key}")
        if item.get("report") != REPORT:
            raise ValueError(f"{key} has another report")
        if item.get("weeks") != list(range(target_week - 4, target_week)):
            raise ValueError(f"{key} source weeks are not W-4..W-1")
        if item.get("status") != "downloaded" or item.get("context") != "Player":
            raise ValueError(f"{key} was not a completed Player export")
        if item.get("include_group_headers") is not True:
            raise ValueError(f"{key} omitted required group headers")
        relative = Path(str(item.get("path", "")))
        if not relative.name or relative != Path(relative.name):
            raise ValueError(f"{key} has an unsafe artifact path")
        path = root / relative
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise ValueError(f"{key} artifact is missing or changed")
        if path.stat().st_size != int(item.get("bytes", -1)):
            raise ValueError(f"{key} artifact byte count differs")
        rows, columns = _csv_shape(path)
        if rows != int(item.get("csv_rows_including_headers", -1)):
            raise ValueError(f"{key} artifact row count differs")
        if columns != int(item.get("max_csv_columns", -1)):
            raise ValueError(f"{key} artifact width differs")
        keyed[key] = {**item, "local_path": path}
    expected = {(season, week) for season in SEASONS for week in TARGET_WEEKS}
    if set(keyed) != expected:
        raise ValueError("alignment manifest is not the frozen grid")
    return manifest, keyed


def _route_count(value: object) -> float:
    if value is None or str(value).strip() == "":
        return 0.0
    return _number(value)


def _identity(row: dict[str, str]) -> tuple[str, str, tuple[str, ...]]:
    pos = row["Player Details::POS"].strip().upper()
    pos = "RB" if pos == "FB" else pos
    return (
        norm_name(row["Player Details::Name"].strip()),
        pos,
        _canonical_teams(row["Player Details::Team"].strip()),
    )


def read_windows(
    manifest: dict,
    artifacts: dict[tuple, dict],
    snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Parse player alignment profiles and their team-level route mixture."""
    by_name, by_season_team = _snapshot_maps(snapshots)
    players: list[dict] = []
    statuses: Counter[str] = Counter()
    required = {
        "Player Details::Name", "Player Details::Team",
        "Player Details::POS", "Player Details::G",
        "Player Details::Season", "Overall::RTE",
        "Wide::RTE", "Slot::RTE", "Inline::RTE", "Backfield::RTE",
    }
    for season in SEASONS:
        for target_week in TARGET_WEEKS:
            artifact = artifacts[(season, target_week)]
            columns, rows = _grouped_rows(artifact["local_path"])
            if missing := required - set(columns):
                raise ValueError(f"{artifact['path']} missing {sorted(missing)}")
            grouped: dict[tuple, list[dict]] = defaultdict(list)
            for source_row, row in enumerate(rows, start=3):
                if int(row["Player Details::Season"]) != season:
                    raise ValueError(f"{artifact['path']} has another season")
                games = int(row["Player Details::G"])
                if not 1 <= games <= 4:
                    raise ValueError(f"{artifact['path']} row {source_row} G={games}")
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
                    raise ValueError(f"{artifact['path']} has invalid routes")
                if not np.isclose(
                    counts["wide"] + counts["slot"] + counts["inline"]
                    + counts["backfield"], counts["overall"], atol=1e-9, rtol=0,
                ):
                    raise ValueError(f"{artifact['path']} buckets do not partition Overall")
                grouped[identity].append({
                    "row": row, "source_row": source_row,
                    "games": games, "counts": counts,
                })

            for identity in sorted(grouped):
                normalized_name, pos, teams = identity
                group = grouped[identity]
                split = len(group) != 1 or len(teams) != 1
                first = group[0]
                gsis_id, status = _resolve_player(
                    season, normalized_name, pos, teams,
                    by_name, by_season_team,
                )
                statuses[status] += 1
                counts = {
                    name: value if not split else np.nan
                    for name, value in first["counts"].items()
                }
                wide_slot = counts["wide"] + counts["slot"]
                supported = bool(
                    not split and gsis_id is not None
                    and wide_slot >= MIN_PLAYER_WIDE_SLOT_ROUTES
                )
                players.append({
                    "season": season,
                    "target_week": target_week,
                    "source_week_start": target_week - 4,
                    "source_week_end": target_week - 1,
                    "gsis_id": gsis_id,
                    "resolution_status": status,
                    "normalized_name": normalized_name,
                    "vendor_name": first["row"]["Player Details::Name"].strip(),
                    "team": teams[0] if len(teams) == 1 else None,
                    "canonical_teams": ",".join(teams),
                    "position": pos,
                    "games": first["games"],
                    "split_duplicate": split,
                    "overall_routes": counts["overall"],
                    "wide_routes": counts["wide"],
                    "slot_routes": counts["slot"],
                    "inline_routes": counts["inline"],
                    "wide_slot_routes": wide_slot,
                    "player_wide_share": (
                        counts["wide"] / wide_slot if wide_slot > 0 else np.nan
                    ),
                    "alignment_supported": supported,
                    "source_run_id": manifest["run_id"],
                    "source_file": artifact["path"],
                    "source_sha256": artifact["sha256"],
                    "source_rows": ",".join(str(item["source_row"]) for item in group),
                })
    player_frame = pd.DataFrame(players)
    if player_frame.duplicated(["season", "target_week", "normalized_name", "position"]).any():
        raise ValueError("alignment import repeats player identities")

    team_source = player_frame[
        player_frame.team.notna() & ~player_frame.split_duplicate
    ].copy()
    teams = team_source.groupby(
        ["season", "target_week", "team"], as_index=False
    ).agg(
        wide_routes=("wide_routes", "sum"),
        slot_routes=("slot_routes", "sum"),
        inline_routes=("inline_routes", "sum"),
        player_rows=("normalized_name", "size"),
    )
    teams["wide_slot_routes"] = teams.wide_routes + teams.slot_routes
    teams["offense_wide_share"] = teams.wide_routes / teams.wide_slot_routes.replace(0, np.nan)
    teams["offense_alignment_supported"] = (
        teams.wide_slot_routes >= MIN_TEAM_WIDE_SLOT_ROUTES
    )
    if not player_frame.source_week_end.lt(player_frame.target_week).all():
        raise ValueError("alignment import contains target-week information")
    return player_frame, teams, {
        "player_rows": int(len(player_frame)),
        "resolved_player_rows": int(player_frame.gsis_id.notna().sum()),
        "supported_player_rows": int(player_frame.alignment_supported.sum()),
        "team_rows": int(len(teams)),
        "supported_team_rows": int(teams.offense_alignment_supported.sum()),
        "unresolved_rows": int(statuses["unresolved"]),
        "ambiguous_rows": int(statuses["ambiguous"]),
    }


def read_exports(
    input_dir: str | Path,
    snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    manifest, artifacts = validate_manifest(input_dir)
    players, teams, audit = read_windows(manifest, artifacts, snapshots)
    return players, teams, {
        "run_id": manifest["run_id"],
        "plan_sha256": manifest.get("plan_sha256"),
        "exports": len(artifacts),
        **audit,
    }


def run(input_dir: str | Path, *, write: bool = False) -> dict:
    from .fantasy_points_same_season_coverage import _write_once
    from ..bq import query_df
    from ..config import settings

    snapshots = query_df(f"""
        SELECT DISTINCT season, gsis_id, name, pos, team
        FROM `{settings.predictions}.slate_player_features`
        WHERE research_eligible AND season BETWEEN 2022 AND 2025
        """)
    players, teams, audit = read_exports(input_dir, snapshots)
    player_ref = f"{settings.raw}.{PLAYER_TABLE}"
    team_ref = f"{settings.raw}.{TEAM_TABLE}"
    audit.update({
        "player_table": player_ref,
        "team_table": team_ref,
        "write_requested": bool(write),
    })
    if write:
        audit["player_write_disposition"] = _write_once(
            player_ref, players, run_id=audit["run_id"],
            hash_columns=("source_sha256",),
        )
        team_payload = teams.copy()
        team_payload["source_run_id"] = audit["run_id"]
        team_payload["source_sha256"] = audit["plan_sha256"]
        audit["team_write_disposition"] = _write_once(
            team_ref, team_payload, run_id=audit["run_id"],
            hash_columns=("source_sha256",),
        )
    print("FP_ALIGNMENT_L4_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit


__all__ = [
    "MIN_PLAYER_WIDE_SLOT_ROUTES", "MIN_TEAM_WIDE_SLOT_ROUTES",
    "read_exports", "read_windows", "run", "validate_manifest",
]
