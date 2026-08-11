"""Manifest-locked import for same-season Fantasy Points coverage windows."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from .fantasy_points_advanced import _grouped_rows, _number
from .fantasy_points_coverage import TEAM_NAMES
from .fantasy_points_route import (
    PANEL_ID,
    _canonical_teams,
    _resolve_player,
    _sha256,
    _snapshot_maps,
)
from ..names import norm_name


PLAN_NAME = "same-season-coverage-last-four-v1"
SEASONS = (2022, 2023, 2024, 2025)
TARGET_WEEKS = tuple(range(5, 19))
REPORT_CONTEXTS = {
    "receiving-man-vs-zone": "Player",
    "receiving-separation-by-coverage": "Player",
    "coverage-matrix": "Defense",
}
RECEIVER_TABLE = "fantasy_points_receiver_coverage_l4"
DEFENSE_TABLE = "fantasy_points_defense_coverage_l4"


def _csv_shape(path: Path) -> tuple[int, int]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    return len(rows), max((len(row) for row in rows), default=0)


def validate_manifest(input_dir: str | Path) -> tuple[dict, dict[tuple, dict]]:
    """Validate a complete 168-export run and return keyed artifacts."""
    root = Path(input_dir)
    manifest_path = root / "manifest.json"
    payload = json.loads(manifest_path.read_text())
    if payload.get("schema_version") != 1:
        raise ValueError("same-season coverage manifest schema must be 1")
    if not str(payload.get("run_id", "")).endswith(f"__{PLAN_NAME}"):
        raise ValueError("same-season coverage manifest has the wrong run id")
    exports = payload.get("exports")
    expected_count = len(REPORT_CONTEXTS) * len(SEASONS) * len(TARGET_WEEKS)
    if not isinstance(exports, list) or len(exports) != expected_count:
        raise ValueError(
            f"same-season coverage manifest has {len(exports or [])} exports; "
            f"expected {expected_count}"
        )
    keyed: dict[tuple, dict] = {}
    for item in exports:
        report = item.get("report")
        season = int(item.get("season", 0))
        target_week = int(item.get("target_week", 0))
        key = (report, season, target_week)
        if key in keyed:
            raise ValueError(f"duplicate same-season coverage export: {key}")
        if report not in REPORT_CONTEXTS:
            raise ValueError(f"unexpected same-season coverage report: {report}")
        if season not in SEASONS or target_week not in TARGET_WEEKS:
            raise ValueError(f"unexpected season/target week: {key}")
        expected_weeks = list(range(target_week - 4, target_week))
        if item.get("weeks") != expected_weeks:
            raise ValueError(
                f"{key} has source weeks {item.get('weeks')}; "
                f"expected {expected_weeks}"
            )
        if item.get("status") != "downloaded":
            raise ValueError(f"{key} was not downloaded")
        if item.get("context") != REPORT_CONTEXTS[report]:
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
        (report, season, target_week)
        for report in REPORT_CONTEXTS
        for season in SEASONS
        for target_week in TARGET_WEEKS
    }
    if set(keyed) != expected:
        raise ValueError("same-season coverage manifest is not the frozen grid")
    return payload, keyed


def _identity(row: dict[str, str]) -> tuple[str, str, tuple[str, ...]]:
    pos = row["Player Details::POS"].strip().upper()
    pos = "RB" if pos == "FB" else pos
    return (
        norm_name(row["Player Details::Name"].strip()),
        pos,
        _canonical_teams(row["Player Details::Team"].strip()),
    )


def _read_receiver_window(
    artifact: dict,
    *,
    family: str,
) -> dict[tuple[str, str, tuple[str, ...]], list[dict]]:
    path = artifact["local_path"]
    columns, rows = _grouped_rows(path)
    common = {
        "Player Details::Name", "Player Details::Team",
        "Player Details::POS", "Player Details::G",
        "Player Details::Season", "Overall::RTE", "Man::RTE",
        "Zone::RTE",
    }
    if family == "man_zone":
        required = common | {
            f"{group}::{metric}"
            for group in ("Overall", "Man", "Zone")
            for metric in ("TPRR", "YPRR", "FP/RR")
        }
    else:
        required = common | {
            "Overall::SEP SCORE", "Man::SEP SCORE", "Zone::SEP SCORE",
        }
    if missing := required - set(columns):
        raise ValueError(f"{path.name} missing {sorted(missing)}")
    season = int(artifact["season"])
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for source_row, row in enumerate(rows, start=3):
        if int(row["Player Details::Season"]) != season:
            raise ValueError(f"{path.name} row {source_row} has wrong season")
        games = int(row["Player Details::G"])
        if not 1 <= games <= 4:
            raise ValueError(f"{path.name} row {source_row} has G={games}")
        identity = _identity(row)
        if identity[1] not in {"WR", "TE"}:
            continue
        grouped[identity].append({"row": row, "source_row": source_row})
    return grouped


def read_receiver_windows(
    manifest: dict,
    artifacts: dict[tuple, dict],
    snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    by_name, by_season_team = _snapshot_maps(snapshots)
    output: list[dict] = []
    statuses: Counter[str] = Counter()
    duplicate_groups = 0
    for season in SEASONS:
        for target_week in TARGET_WEEKS:
            man_artifact = artifacts[
                ("receiving-man-vs-zone", season, target_week)]
            sep_artifact = artifacts[
                ("receiving-separation-by-coverage", season, target_week)]
            man = _read_receiver_window(man_artifact, family="man_zone")
            sep = _read_receiver_window(sep_artifact, family="separation")
            for identity in sorted(set(man) & set(sep)):
                normalized_name, pos, teams = identity
                man_group, sep_group = man[identity], sep[identity]
                split = len(man_group) != 1 or len(sep_group) != 1
                duplicate_groups += int(split)
                gsis_id, status = _resolve_player(
                    season, normalized_name, pos, teams,
                    by_name, by_season_team,
                )
                statuses[status] += 1
                man_row = man_group[0]["row"]
                sep_row = sep_group[0]["row"]
                values = {
                    "overall_routes": _number(man_row["Overall::RTE"]),
                    "overall_tprr": _number(man_row["Overall::TPRR"]),
                    "overall_yprr": _number(man_row["Overall::YPRR"]),
                    "overall_fprr": _number(man_row["Overall::FP/RR"]),
                    "man_routes": _number(man_row["Man::RTE"]),
                    "man_tprr": _number(man_row["Man::TPRR"]),
                    "man_yprr": _number(man_row["Man::YPRR"]),
                    "man_fprr": _number(man_row["Man::FP/RR"]),
                    "zone_routes": _number(man_row["Zone::RTE"]),
                    "zone_tprr": _number(man_row["Zone::TPRR"]),
                    "zone_yprr": _number(man_row["Zone::YPRR"]),
                    "zone_fprr": _number(man_row["Zone::FP/RR"]),
                    "overall_sep": _number(sep_row["Overall::SEP SCORE"]),
                    "man_sep": _number(sep_row["Man::SEP SCORE"]),
                    "zone_sep": _number(sep_row["Zone::SEP SCORE"]),
                    "sep_overall_routes": _number(sep_row["Overall::RTE"]),
                    "sep_man_routes": _number(sep_row["Man::RTE"]),
                    "sep_zone_routes": _number(sep_row["Zone::RTE"]),
                }
                if split:
                    values = {name: np.nan for name in values}
                supported = (
                    not split
                    and min(values["overall_routes"], values["sep_overall_routes"])
                    >= 50
                    and min(values["man_routes"], values["sep_man_routes"]) >= 10
                    and min(values["zone_routes"], values["sep_zone_routes"])
                    >= 25
                    and all(np.isfinite(values[name]) for name in (
                        "overall_tprr", "overall_yprr", "overall_fprr",
                        "man_tprr", "man_yprr", "man_fprr",
                        "zone_tprr", "zone_yprr", "zone_fprr",
                        "overall_sep", "man_sep", "zone_sep",
                    ))
                )
                output.append({
                    "season": season,
                    "target_week": target_week,
                    "source_week_start": target_week - 4,
                    "source_week_end": target_week - 1,
                    "gsis_id": gsis_id,
                    "resolution_status": status,
                    "vendor_name": man_row["Player Details::Name"].strip(),
                    "normalized_name": normalized_name,
                    "vendor_team": man_row["Player Details::Team"].strip(),
                    "canonical_teams": ",".join(teams),
                    "pos": pos,
                    "split_duplicate": split,
                    "fp_cov_l4_supported": supported,
                    "source_run_id": manifest["run_id"],
                    "man_zone_source_file": man_artifact["path"],
                    "man_zone_source_sha256": man_artifact["sha256"],
                    "separation_source_file": sep_artifact["path"],
                    "separation_source_sha256": sep_artifact["sha256"],
                    "man_zone_source_rows": ",".join(
                        str(item["source_row"]) for item in man_group),
                    "separation_source_rows": ",".join(
                        str(item["source_row"]) for item in sep_group),
                    **values,
                })
    frame = pd.DataFrame(output)
    if frame.duplicated(["season", "target_week", "normalized_name", "pos"]).any():
        raise ValueError("same-season receiver import has duplicate target identities")
    return frame, {
        "rows": int(len(frame)),
        "resolved_rows": int(frame.gsis_id.notna().sum()),
        "supported_rows": int(frame.fp_cov_l4_supported.sum()),
        "unresolved_rows": int(statuses["unresolved"]),
        "ambiguous_rows": int(statuses["ambiguous"]),
        "duplicate_groups_suppressed": int(duplicate_groups),
    }


def read_defense_windows(
    manifest: dict,
    artifacts: dict[tuple, dict],
) -> tuple[pd.DataFrame, dict]:
    output: list[dict] = []
    for season in SEASONS:
        for target_week in TARGET_WEEKS:
            artifact = artifacts[("coverage-matrix", season, target_week)]
            path = artifact["local_path"]
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            if len(rows) != 34 or any(len(row) != 22 for row in rows):
                raise ValueError(f"{path.name} is not a 32-team 22-column matrix")
            header = rows[1]
            positions = {}
            for name in ("Name", "G", "Season", "DB", "MAN %", "ZONE %"):
                matches = [index for index, value in enumerate(header) if value == name]
                if len(matches) != 1:
                    raise ValueError(f"{path.name} has {len(matches)} {name!r} columns")
                positions[name] = matches[0]
            seen: set[str] = set()
            for source_row, row in enumerate(rows[2:], start=3):
                if int(row[positions["Season"]]) != season:
                    raise ValueError(f"{path.name} row {source_row} has wrong season")
                games = int(row[positions["G"]])
                if not 1 <= games <= 4:
                    raise ValueError(f"{path.name} row {source_row} has G={games}")
                vendor_name = row[positions["Name"]].strip()
                if vendor_name not in TEAM_NAMES:
                    raise ValueError(f"unmapped defense {vendor_name!r}")
                team = TEAM_NAMES[vendor_name]
                if team in seen:
                    raise ValueError(f"duplicate defense {team} in {path.name}")
                seen.add(team)
                output.append({
                    "season": season,
                    "target_week": target_week,
                    "source_week_start": target_week - 4,
                    "source_week_end": target_week - 1,
                    "team": team,
                    "games": games,
                    "dropbacks": int(row[positions["DB"]]),
                    "def_man_rate": _number(row[positions["MAN %"]]) / 100.0,
                    "def_zone_rate": _number(row[positions["ZONE %"]]) / 100.0,
                    "source_run_id": manifest["run_id"],
                    "source_file": artifact["path"],
                    "source_sha256": artifact["sha256"],
                    "source_row": source_row,
                })
            if len(seen) != 32:
                raise ValueError(f"{path.name} did not resolve 32 defenses")
    frame = pd.DataFrame(output)
    rates = frame[["def_man_rate", "def_zone_rate"]]
    if not ((rates >= 0) & (rates <= 1)).all().all():
        raise ValueError("same-season defense coverage rate outside [0,1]")
    return frame, {
        "rows": int(len(frame)),
        "teams": int(frame.team.nunique()),
        "target_windows": int(frame[["season", "target_week"]].drop_duplicates().shape[0]),
    }


def read_exports(
    input_dir: str | Path,
    snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    manifest, artifacts = validate_manifest(input_dir)
    receivers, receiver_audit = read_receiver_windows(
        manifest, artifacts, snapshots)
    defenses, defense_audit = read_defense_windows(manifest, artifacts)
    return receivers, defenses, {
        "run_id": manifest["run_id"],
        "exports": len(artifacts),
        "receiver": receiver_audit,
        "defense": defense_audit,
    }


def _repeated_values(value: object) -> list:
    """Normalize BigQuery repeated fields without scalar truth testing."""
    return [] if value is None else list(value)


def _write_once(
    table_ref: str,
    rows: pd.DataFrame,
    *,
    run_id: str,
    hash_columns: tuple[str, ...],
) -> str:
    from google.api_core.exceptions import NotFound

    from ..bq import client, load_dataframe, query_df

    try:
        client().get_table(table_ref)
    except NotFound:
        payload = rows.copy()
        payload["ingested_at"] = pd.Timestamp.now(tz="UTC")
        load_dataframe(payload, table_ref, write_disposition="WRITE_EMPTY")
        return "created"
    hash_array = ", ".join(hash_columns)
    existing = query_df(f"""
        SELECT
          (SELECT COUNT(*) FROM `{table_ref}`) AS n_rows,
          (SELECT ARRAY_AGG(DISTINCT source_run_id) FROM `{table_ref}`)
            AS run_ids,
          (SELECT ARRAY_AGG(DISTINCT source_hash ORDER BY source_hash)
           FROM `{table_ref}`, UNNEST([{hash_array}]) AS source_hash)
            AS hashes
        """).iloc[0]
    expected_hashes = sorted({
        str(value)
        for column in hash_columns
        for value in rows[column].dropna().unique()
    })
    existing_run_ids = _repeated_values(existing.run_ids)
    existing_hashes = _repeated_values(existing.hashes)
    if (
        int(existing.n_rows or 0) != len(rows)
        or existing_run_ids != [run_id]
        or sorted(existing_hashes) != expected_hashes
    ):
        raise RuntimeError(f"refusing to overwrite non-identical {table_ref}")
    return "already-identical"


def run(input_dir: str | Path, *, write: bool = False) -> dict:
    """Audit the frozen exact-window grid and optionally create raw tables."""
    from ..bq import query_df
    from ..config import settings

    snapshots = query_df(f"""
        SELECT DISTINCT season, gsis_id, name, pos, team
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season BETWEEN 2022 AND 2025
        """, params={"panel_id": PANEL_ID})
    receivers, defenses, audit = read_exports(input_dir, snapshots)
    receiver_ref = f"{settings.raw}.{RECEIVER_TABLE}"
    defense_ref = f"{settings.raw}.{DEFENSE_TABLE}"
    audit.update({
        "receiver_table": receiver_ref,
        "defense_table": defense_ref,
        "write_requested": bool(write),
    })
    if write:
        audit["receiver_write_disposition"] = _write_once(
            receiver_ref,
            receivers,
            run_id=audit["run_id"],
            hash_columns=(
                "man_zone_source_sha256", "separation_source_sha256"),
        )
        audit["defense_write_disposition"] = _write_once(
            defense_ref,
            defenses,
            run_id=audit["run_id"],
            hash_columns=("source_sha256",),
        )
    print("FP_SAME_SEASON_COVERAGE_IMPORT_JSON=" + json.dumps(
        audit, sort_keys=True))
    return audit
