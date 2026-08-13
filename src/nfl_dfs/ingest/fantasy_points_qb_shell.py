"""Manifest-locked import for the frozen QB shell-fit window grid."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .fantasy_points_advanced import _number
from .fantasy_points_coverage import TEAM_NAMES
from .fantasy_points_route import _sha256
from .fantasy_points_same_season_coverage import (
    PLAN_NAME as DEFENSE_PLAN_NAME,
    _csv_shape,
    _write_once,
    validate_manifest as validate_defense_manifest,
)


PLAN_NAME = "same-season-qb-shell-fit-last-four-v1"
SEASONS = (2022, 2023, 2024, 2025)
TARGET_WEEKS = tuple(range(5, 19))
TABLE = "fantasy_points_qb_shell_l4"

_HEADER = (
    "Rank", "Name", "G", "Season", "Location", "Team Name", "DB",
    "MAN %", "FP/DB", "ZONE %", "FP/DB", "1-HI/MOF C %", "FP/DB",
    "2-HI/MOF O %", "FP/DB", "COVER 0 %", "COVER 1 %", "COVER 2 %",
    "COVER 2 MAN %", "COVER 3 %", "COVER 4 %", "COVER 6 %",
)


def validate_manifest(input_dir: str | Path) -> tuple[dict, dict[tuple, dict]]:
    """Validate the complete frozen 56-export Offense grid."""
    root = Path(input_dir)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError("QB shell manifest schema must be 1")
    if not str(manifest.get("run_id", "")).endswith(f"__{PLAN_NAME}"):
        raise ValueError("QB shell manifest has the wrong run id")
    exports = manifest.get("exports")
    expected_count = len(SEASONS) * len(TARGET_WEEKS)
    if not isinstance(exports, list) or len(exports) != expected_count:
        raise ValueError(
            f"QB shell manifest has {len(exports or [])} exports; "
            f"expected {expected_count}"
        )
    keyed: dict[tuple, dict] = {}
    for item in exports:
        season = int(item.get("season", 0))
        target_week = int(item.get("target_week", 0))
        key = (season, target_week)
        if key in keyed:
            raise ValueError(f"duplicate QB shell export: {key}")
        if item.get("report") != "coverage-matrix":
            raise ValueError("QB shell manifest has another report")
        if season not in SEASONS or target_week not in TARGET_WEEKS:
            raise ValueError(f"unexpected QB shell season/target week: {key}")
        expected_weeks = list(range(target_week - 4, target_week))
        if item.get("weeks") != expected_weeks:
            raise ValueError(
                f"{key} has source weeks {item.get('weeks')}; "
                f"expected {expected_weeks}"
            )
        if item.get("status") != "downloaded":
            raise ValueError(f"{key} was not downloaded")
        if item.get("context") != "Offense":
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
        raise ValueError("QB shell manifest is not the frozen grid")
    return manifest, keyed


def _read_matrix(artifact: dict, *, prefix: str) -> list[dict]:
    path = artifact["local_path"]
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) != 34 or any(len(row) != len(_HEADER) for row in rows):
        raise ValueError(f"{path.name} is not a 32-team 22-column matrix")
    if tuple(rows[1]) != _HEADER:
        raise ValueError(f"{path.name} has an unexpected matrix header")
    season = int(artifact["season"])
    target_week = int(artifact["target_week"])
    output: list[dict] = []
    seen: set[str] = set()
    for source_row, row in enumerate(rows[2:], start=3):
        if int(row[3]) != season:
            raise ValueError(f"{path.name} row {source_row} has wrong season")
        games = int(row[2])
        if not 1 <= games <= 4:
            raise ValueError(f"{path.name} row {source_row} has G={games}")
        vendor_name = row[1].strip()
        if vendor_name not in TEAM_NAMES:
            raise ValueError(f"unmapped team {vendor_name!r}")
        team = TEAM_NAMES[vendor_name]
        if team in seen:
            raise ValueError(f"duplicate team {team} in {path.name}")
        seen.add(team)
        metrics = {
            f"{prefix}_dropbacks": _number(row[6]),
            f"{prefix}_man_rate": _number(row[7]) / 100.0,
            f"{prefix}_man_fpdb": _number(row[8]),
            f"{prefix}_zone_rate": _number(row[9]) / 100.0,
            f"{prefix}_zone_fpdb": _number(row[10]),
            f"{prefix}_one_high_rate": _number(row[11]) / 100.0,
            f"{prefix}_one_high_fpdb": _number(row[12]),
            f"{prefix}_two_high_rate": _number(row[13]) / 100.0,
            f"{prefix}_two_high_fpdb": _number(row[14]),
        }
        if not all(np.isfinite(value) for value in metrics.values()):
            raise ValueError(f"{path.name} row {source_row} has nonfinite shell data")
        rates = [value for name, value in metrics.items() if name.endswith("_rate")]
        if not all(0 <= value <= 1 for value in rates):
            raise ValueError(f"{path.name} row {source_row} has invalid shell rate")
        output.append({
            "season": season,
            "target_week": target_week,
            "source_week_start": target_week - 4,
            "source_week_end": target_week - 1,
            "team": team,
            f"{prefix}_games": games,
            f"{prefix}_source_file": artifact["path"],
            f"{prefix}_source_sha256": artifact["sha256"],
            f"{prefix}_source_row": source_row,
            **metrics,
        })
    if len(seen) != 32:
        raise ValueError(f"{path.name} did not resolve 32 teams")
    return output


def read_exports(
    input_dir: str | Path,
    defense_input_dir: str | Path,
) -> tuple[pd.DataFrame, dict]:
    """Parse the Offense grid and the accepted matching Defense grid."""
    offense_manifest, offense_artifacts = validate_manifest(input_dir)
    defense_manifest, defense_artifacts = validate_defense_manifest(
        defense_input_dir)
    if not str(defense_manifest["run_id"]).endswith(f"__{DEFENSE_PLAN_NAME}"):
        raise ValueError("QB shell defense source has the wrong plan")
    offense_rows: list[dict] = []
    defense_rows: list[dict] = []
    for season in SEASONS:
        for target_week in TARGET_WEEKS:
            offense_rows.extend(_read_matrix(
                offense_artifacts[(season, target_week)], prefix="off"))
            defense_rows.extend(_read_matrix(
                defense_artifacts[("coverage-matrix", season, target_week)],
                prefix="def",
            ))
    keys = ["season", "target_week", "source_week_start", "source_week_end", "team"]
    offense = pd.DataFrame(offense_rows)
    defense = pd.DataFrame(defense_rows)
    if offense.duplicated(keys).any() or defense.duplicated(keys).any():
        raise ValueError("QB shell source has duplicate team windows")
    rows = offense.merge(defense, on=keys, how="inner", validate="one_to_one")
    expected_rows = len(SEASONS) * len(TARGET_WEEKS) * 32
    if len(rows) != expected_rows:
        raise ValueError(f"QB shell merge has {len(rows)} rows, expected {expected_rows}")
    rows["offense_source_run_id"] = offense_manifest["run_id"]
    rows["defense_source_run_id"] = defense_manifest["run_id"]
    return rows, {
        "offense_source_run_id": offense_manifest["run_id"],
        "defense_source_run_id": defense_manifest["run_id"],
        "offense_exports": len(offense_artifacts),
        "defense_exports_validated": len(defense_artifacts),
        "rows": int(len(rows)),
        "teams": int(rows.team.nunique()),
        "target_windows": int(
            rows[["season", "target_week"]].drop_duplicates().shape[0]),
    }


def run(
    input_dir: str | Path,
    defense_input_dir: str | Path,
    *,
    write: bool = False,
) -> dict:
    """Audit the two frozen grids and optionally create the private raw table."""
    from ..config import settings

    rows, audit = read_exports(input_dir, defense_input_dir)
    table_ref = f"{settings.raw}.{TABLE}"
    audit.update({"table": table_ref, "write_requested": bool(write)})
    if write:
        # _write_once's single run-id contract does not represent this two-run
        # table, so bind both immutable run IDs into one deterministic identity.
        rows = rows.copy()
        rows["source_run_id"] = (
            rows.offense_source_run_id + "|" + rows.defense_source_run_id)
        audit["write_disposition"] = _write_once(
            table_ref,
            rows,
            run_id=(
                f"{audit['offense_source_run_id']}|"
                f"{audit['defense_source_run_id']}"),
            hash_columns=("off_source_sha256", "def_source_sha256"),
        )
    print("FP_QB_SHELL_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit
