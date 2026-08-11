"""Manifest-locked import for same-season Advanced Passing windows."""

from __future__ import annotations

import json
from collections import Counter
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


PLAN_NAME = "same-season-advanced-passing-last-four-v1"
SEASONS = (2022, 2023, 2024, 2025)
TARGET_WEEKS = tuple(range(5, 19))
TABLE = "fantasy_points_advanced_passing_l4"

FEATURE_SPECS = {
    "Passing Advanced::CPOE": ("fp_pass_l4_cpoe", True),
    "Passing Advanced::aDOT": ("fp_pass_l4_adot", False),
    "Passing Advanced::Deep Throw %": ("fp_pass_l4_deep_throw_rate", True),
    "Passing Advanced::YAC %": ("fp_pass_l4_yac_rate", True),
    "Passing Advanced::ADJ CMP %": (
        "fp_pass_l4_adjusted_completion_rate", True),
    "Passing Advanced::1Read %": ("fp_pass_l4_first_read_rate", True),
    "Passing Advanced::ACC %": ("fp_pass_l4_accuracy_rate", True),
    "Passing Advanced::CATCH %": ("fp_pass_l4_catchable_rate", True),
    "Passing Advanced::OFF %": ("fp_pass_l4_off_target_rate", True),
    "Passing Advanced::HERO %": ("fp_pass_l4_hero_rate", True),
    "Passing Advanced::TWT %": ("fp_pass_l4_twt_rate", True),
    "Passing Advanced::DROP %": ("fp_pass_l4_drop_rate", True),
    "Passing Advanced::TTT": ("fp_pass_l4_time_to_throw", False),
    "Passing Advanced::TTP": ("fp_pass_l4_time_to_pressure", False),
    "Passing Advanced::TTSK": ("fp_pass_l4_time_to_sack", False),
    "Passing Advanced::TTSC": ("fp_pass_l4_time_to_scramble", False),
    "Passing Advanced::PRESS %": ("fp_pass_l4_pressure_rate", True),
    "Passing Advanced::PRESS SK %": (
        "fp_pass_l4_pressure_sack_rate", True),
    "Passing Advanced::PrROE": (
        "fp_pass_l4_pressure_rate_over_expected", False),
    "Passing Advanced::CHK %": ("fp_pass_l4_checkdown_rate", True),
    "Passing Advanced::RPO %": ("fp_pass_l4_rpo_rate", True),
}
PASSING_FEATURES = tuple(value[0] for value in FEATURE_SPECS.values()) + (
    "fp_pass_l4_scramble_rate",
)


def validate_manifest(input_dir: str | Path) -> tuple[dict, dict[tuple, dict]]:
    """Validate the complete frozen 56-export grid and its artifacts."""
    root = Path(input_dir)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError("same-season passing manifest schema must be 1")
    if not str(manifest.get("run_id", "")).endswith(f"__{PLAN_NAME}"):
        raise ValueError("same-season passing manifest has the wrong run id")
    exports = manifest.get("exports")
    expected_count = len(SEASONS) * len(TARGET_WEEKS)
    if not isinstance(exports, list) or len(exports) != expected_count:
        raise ValueError(
            f"same-season passing manifest has {len(exports or [])} exports; "
            f"expected {expected_count}"
        )
    keyed: dict[tuple, dict] = {}
    for item in exports:
        if item.get("report") != "advanced-passing":
            raise ValueError("same-season passing manifest has another report")
        season = int(item.get("season", 0))
        target_week = int(item.get("target_week", 0))
        key = (season, target_week)
        if key in keyed:
            raise ValueError(f"duplicate same-season passing export: {key}")
        if season not in SEASONS or target_week not in TARGET_WEEKS:
            raise ValueError(f"unexpected passing season/target week: {key}")
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
        raise ValueError("same-season passing manifest is not the frozen grid")
    return manifest, keyed


def read_windows(
    manifest: dict,
    artifacts: dict[tuple, dict],
    snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Parse, resolve and normalize every exact passing window."""
    by_name, by_season_team = _snapshot_maps(snapshots)
    output: list[dict] = []
    statuses: Counter[str] = Counter()
    required = {
        "Player Details::Name", "Player Details::Team",
        "Player Details::POS", "Player Details::G",
        "Player Details::Season", "Passing::DB", "Scrambles::SCRM",
        *FEATURE_SPECS,
    }
    for season in SEASONS:
        for target_week in TARGET_WEEKS:
            artifact = artifacts[(season, target_week)]
            columns, rows = _grouped_rows(artifact["local_path"])
            if missing := required - set(columns):
                raise ValueError(
                    f"{artifact['path']} missing {sorted(missing)}")
            seen: set[tuple[str, str]] = set()
            for source_row, row in enumerate(rows, start=3):
                if int(row["Player Details::Season"]) != season:
                    raise ValueError(
                        f"{artifact['path']} row {source_row} has wrong season")
                games = int(row["Player Details::G"])
                if not 1 <= games <= 4:
                    raise ValueError(
                        f"{artifact['path']} row {source_row} has G={games}")
                pos = row["Player Details::POS"].strip().upper()
                if pos != "QB":
                    raise ValueError(
                        f"{artifact['path']} row {source_row} is not a QB")
                vendor_name = row["Player Details::Name"].strip()
                normalized_name = norm_name(vendor_name)
                identity = (normalized_name, pos)
                if identity in seen:
                    raise ValueError(
                        f"duplicate QB identity in {artifact['path']}: {identity}")
                seen.add(identity)
                vendor_team = row["Player Details::Team"].strip()
                teams = _canonical_teams(vendor_team)
                gsis_id, status = _resolve_player(
                    season, normalized_name, pos, teams,
                    by_name, by_season_team,
                )
                statuses[status] += 1
                dropbacks = _number(row["Passing::DB"])
                scrambles = _number(row["Scrambles::SCRM"])
                metrics = {
                    output_name: _number(
                        row[source_name], percentage=percentage)
                    for source_name, (output_name, percentage)
                    in FEATURE_SPECS.items()
                }
                metrics["fp_pass_l4_scramble_rate"] = (
                    scrambles / dropbacks if dropbacks > 0 else np.nan)
                output.append({
                    "season": season,
                    "target_week": target_week,
                    "source_week_start": target_week - 4,
                    "source_week_end": target_week - 1,
                    "gsis_id": gsis_id,
                    "resolution_status": status,
                    "vendor_name": vendor_name,
                    "normalized_name": normalized_name,
                    "vendor_team": vendor_team,
                    "canonical_teams": ",".join(teams),
                    "pos": pos,
                    "games": games,
                    "dropbacks": dropbacks,
                    "fp_pass_l4_supported": bool(dropbacks >= 80),
                    "source_run_id": manifest["run_id"],
                    "source_file": artifact["path"],
                    "source_sha256": artifact["sha256"],
                    "source_row": source_row,
                    **metrics,
                })
    frame = pd.DataFrame(output)
    keys = ["season", "target_week", "normalized_name", "pos"]
    if frame.duplicated(keys).any():
        raise ValueError("same-season passing import has duplicate identities")
    return frame, {
        "rows": int(len(frame)),
        "resolved_rows": int(frame.gsis_id.notna().sum()),
        "supported_rows": int(frame.fp_pass_l4_supported.sum()),
        "unresolved_rows": int(statuses["unresolved"]),
        "ambiguous_rows": int(statuses["ambiguous"]),
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
        "passing": row_audit,
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
    print("FP_SAME_SEASON_PASSING_IMPORT_JSON=" + json.dumps(
        audit, sort_keys=True))
    return audit
