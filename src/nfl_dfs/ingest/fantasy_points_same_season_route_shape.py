"""Manifest-locked import for same-season broad receiver route shapes."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from .fantasy_points_advanced import _grouped_rows, _number
from .fantasy_points_route import (
    PANEL_ID,
    _canonical_teams,
    _resolve_player,
    _sha256,
    _snapshot_maps,
)
from .fantasy_points_same_season_coverage import _csv_shape, _write_once
from ..names import norm_name


PLAN_NAME = "same-season-route-shape-last-four-v1"
REPORT = "receiving-separation-by-breaks"
SEASONS = (2022, 2023, 2024, 2025)
TARGET_WEEKS = tuple(range(5, 19))
TABLE = "fantasy_points_route_shape_l4"

ROUTE_GROUPS = {
    "Horizontally Breaking": "horizontal",
    "Vertically Breaking": "vertical",
    "Static": "static",
    "Shallow/Underneath": "shallow",
    "Backfield": "backfield",
}
ROUTE_SHAPE_FEATURES = tuple(
    f"fp_route_shape_l4_{name}_share"
    for name in ("horizontal", "vertical", "static", "shallow")
)


def validate_manifest(input_dir: str | Path) -> tuple[dict, dict[tuple, dict]]:
    """Validate the complete frozen 56-export grid and every artifact."""
    root = Path(input_dir)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError("same-season route-shape manifest schema must be 1")
    if not str(manifest.get("run_id", "")).endswith(f"__{PLAN_NAME}"):
        raise ValueError("same-season route-shape manifest has the wrong run id")
    exports = manifest.get("exports")
    expected_count = len(SEASONS) * len(TARGET_WEEKS)
    if not isinstance(exports, list) or len(exports) != expected_count:
        raise ValueError(
            f"same-season route-shape manifest has {len(exports or [])} "
            f"exports; expected {expected_count}"
        )
    keyed: dict[tuple, dict] = {}
    for item in exports:
        if item.get("report") != REPORT:
            raise ValueError("same-season route-shape manifest has another report")
        season = int(item.get("season", 0))
        target_week = int(item.get("target_week", 0))
        key = (season, target_week)
        if key in keyed:
            raise ValueError(f"duplicate same-season route-shape export: {key}")
        if season not in SEASONS or target_week not in TARGET_WEEKS:
            raise ValueError(f"unexpected route-shape season/target week: {key}")
        expected_weeks = list(range(target_week - 4, target_week))
        if item.get("weeks") != expected_weeks:
            raise ValueError(
                f"{key} has source weeks {item.get('weeks')}; "
                f"expected {expected_weeks}"
            )
        if item.get("status") != "downloaded":
            raise ValueError(f"{key} was not downloaded")
        if item.get("context") != "Player":
            raise ValueError(f"{key} has the wrong report context")
        if item.get("include_group_headers") is not True:
            raise ValueError(f"{key} omitted required group headers")
        relative = Path(str(item.get("path", "")))
        if not relative.name or relative != Path(relative.name):
            raise ValueError(f"{key} has an unsafe artifact path")
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        if _sha256(path) != item.get("sha256"):
            raise ValueError(f"{key} artifact hash differs from manifest")
        if path.stat().st_size != int(item.get("bytes", -1)):
            raise ValueError(f"{key} artifact byte count differs from manifest")
        rows, columns = _csv_shape(path)
        if rows != int(item.get("csv_rows_including_headers", -1)):
            raise ValueError(f"{key} artifact row count differs from manifest")
        if columns != int(item.get("max_csv_columns", -1)):
            raise ValueError(f"{key} artifact width differs from manifest")
        keyed[key] = {**item, "local_path": path}
    expected = {
        (season, week) for season in SEASONS for week in TARGET_WEEKS
    }
    if set(keyed) != expected:
        raise ValueError("same-season route-shape manifest is not the frozen grid")
    return manifest, keyed


def _route_count(value: object) -> float:
    """Treat a blank route bucket as zero; the partition check validates it."""
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
) -> tuple[pd.DataFrame, dict]:
    """Parse, resolve and normalize every exact route-shape window."""
    by_name, by_season_team = _snapshot_maps(snapshots)
    output: list[dict] = []
    statuses: Counter[str] = Counter()
    duplicate_groups = 0
    partition_rows = 0
    required = {
        "Player Details::Name", "Player Details::Team",
        "Player Details::POS", "Player Details::G",
        "Player Details::Season", "Overall::RTE",
        *(f"{group}::RTE" for group in ROUTE_GROUPS),
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
                    raise ValueError(
                        f"{artifact['path']} row {source_row} has wrong season")
                games = int(row["Player Details::G"])
                if not 1 <= games <= 4:
                    raise ValueError(
                        f"{artifact['path']} row {source_row} has G={games}")
                identity = _identity(row)
                if identity[1] not in {"WR", "TE"}:
                    continue
                overall = _number(row["Overall::RTE"])
                counts = {
                    name: _route_count(row[f"{group}::RTE"])
                    for group, name in ROUTE_GROUPS.items()
                }
                values = [overall, *counts.values()]
                if not all(np.isfinite(value) and value >= 0 for value in values):
                    raise ValueError(
                        f"{artifact['path']} row {source_row} has invalid routes")
                if not np.isclose(
                    sum(counts.values()), overall, atol=1e-9, rtol=0.0
                ):
                    raise ValueError(
                        f"{artifact['path']} row {source_row} route buckets "
                        "do not partition Overall"
                    )
                partition_rows += 1
                grouped[identity].append({
                    "row": row,
                    "source_row": source_row,
                    "games": games,
                    "overall": overall,
                    "counts": counts,
                })

            for identity in sorted(grouped):
                normalized_name, pos, teams = identity
                group = grouped[identity]
                split = len(group) != 1
                duplicate_groups += int(split)
                first = group[0]
                gsis_id, status = _resolve_player(
                    season, normalized_name, pos, teams,
                    by_name, by_season_team,
                )
                statuses[status] += 1
                overall = first["overall"] if not split else np.nan
                counts = {
                    name: value if not split else np.nan
                    for name, value in first["counts"].items()
                }
                shares = {
                    f"fp_route_shape_l4_{name}_share": (
                        value / overall if overall > 0 else np.nan
                    )
                    for name, value in counts.items()
                }
                supported = bool(
                    not split
                    and overall >= 30
                    and all(np.isfinite(shares[name])
                            for name in ROUTE_SHAPE_FEATURES)
                )
                row = first["row"]
                output.append({
                    "season": season,
                    "target_week": target_week,
                    "source_week_start": target_week - 4,
                    "source_week_end": target_week - 1,
                    "gsis_id": gsis_id,
                    "resolution_status": status,
                    "vendor_name": row["Player Details::Name"].strip(),
                    "normalized_name": normalized_name,
                    "vendor_team": row["Player Details::Team"].strip(),
                    "canonical_teams": ",".join(teams),
                    "pos": pos,
                    "games": first["games"],
                    "split_duplicate": split,
                    "overall_routes": overall,
                    **{f"{name}_routes": value for name, value in counts.items()},
                    **shares,
                    "fp_route_shape_l4_partition_valid": not split,
                    "fp_route_shape_l4_supported": supported,
                    "source_run_id": manifest["run_id"],
                    "source_file": artifact["path"],
                    "source_sha256": artifact["sha256"],
                    "source_rows": ",".join(
                        str(item["source_row"]) for item in group),
                })
    frame = pd.DataFrame(output)
    keys = ["season", "target_week", "normalized_name", "pos"]
    if frame.duplicated(keys).any():
        raise ValueError("same-season route-shape import has duplicate identities")
    return frame, {
        "rows": int(len(frame)),
        "resolved_rows": int(frame.gsis_id.notna().sum()),
        "supported_rows": int(frame.fp_route_shape_l4_supported.sum()),
        "partition_valid_source_rows": int(partition_rows),
        "unresolved_rows": int(statuses["unresolved"]),
        "ambiguous_rows": int(statuses["ambiguous"]),
        "duplicate_groups_suppressed": int(duplicate_groups),
    }


def read_exports(
    input_dir: str | Path,
    snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    manifest, artifacts = validate_manifest(input_dir)
    rows, row_audit = read_windows(manifest, artifacts, snapshots)
    return rows, {
        "run_id": manifest["run_id"],
        "exports": len(artifacts),
        "route_shape": row_audit,
    }


def run(input_dir: str | Path, *, write: bool = False) -> dict:
    """Audit the frozen grid and optionally create its private raw table."""
    from ..bq import query_df
    from ..config import settings

    snapshots = query_df(f"""
        SELECT DISTINCT season, gsis_id, name, pos, team
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season BETWEEN 2022 AND 2025
        """, params={"panel_id": PANEL_ID})
    rows, audit = read_exports(input_dir, snapshots)
    table_ref = f"{settings.raw}.{TABLE}"
    audit.update({"table": table_ref, "write_requested": bool(write)})
    if write:
        audit["write_disposition"] = _write_once(
            table_ref,
            rows,
            run_id=audit["run_id"],
            hash_columns=("source_sha256",),
        )
    print("FP_SAME_SEASON_ROUTE_SHAPE_IMPORT_JSON=" + json.dumps(
        audit, sort_keys=True))
    return audit
