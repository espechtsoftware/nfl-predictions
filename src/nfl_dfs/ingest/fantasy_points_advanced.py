"""Hash-locked import for licensed Fantasy Points Advanced player exports."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .fantasy_points_route import (
    PANEL_ID,
    _canonical_teams,
    _resolve_player,
    _sha256,
    _snapshot_maps,
)
from ..names import norm_name


TABLE = "fantasy_points_advanced_prior"
EXPECTED_HASHES = {
    "receiving": {
        2022: "28a0c4d19cb1578c0d3eb36bea84f971ae1e645c72d784915b031b1f3fec4313",
        2023: "38a4424f952b62250e6dd721f34b1b95de4704d01686f41aa242ba39fcc6510f",
        2024: "c656488c84fa3a90d536690546d9a5dee42cd5c3ac8683d1c1b67166a6195753",
        2025: "354648754659d2308b32b3c3b5ab9dd2423608ae82820c07b664edea93b81974",
    },
    "rushing": {
        2022: "05600c957a50fa63116517ffe72a54f73a5af47496aa52f556b112cfbee6164f",
        2023: "c24551981349c807b429ca71bbbe4ce8efa6f0e5d695f409e13875b54b4a0f43",
        2024: "3300d87d81080232a8f619558d9b9e009e5ec9e83ad4778a227c4e14cb102c30",
        2025: "fcd858042ddc1f90bd60dd1461a9cf4f6402ea127c68d681e8ec3a0e86c9c390",
    },
    "passing": {
        2022: "55d29f3e7995c0f08c6943d02e7f28a55744a11dd82b167821d1c61509e9aeba",
        2023: "5085de7ab8dc8f9d1f228dcff60cec2ccff73d2dc2ed72b09921ad0c87424474",
        2024: "753b7a000e7483e4633b1416b33402dad358be95b5bf503fad8641e0094be069",
        2025: "615fc914ff57b708d09ce525007df09f52db1370172aaa3f0d7456d0046da5c1",
    },
}
EXPECTED_ROWS = {
    "receiving": {2022: 545, 2023: 517, 2024: 528, 2025: 526},
    "rushing": {2022: 354, 2023: 334, 2024: 322, 2025: 329},
    "passing": {2022: 83, 2023: 80, 2024: 77, 2025: 77},
}
FILE_SUFFIX = {
    "receiving": "receivingAdvancedExport.csv",
    "rushing": "rushingAdvancedExport.csv",
    "passing": "passingAdvancedExport.csv",
}
FEATURE_SPECS = {
    "receiving": {
        "TPRR": ("fp_adv_rec_tprr", False),
        "aDOT": ("fp_adv_rec_adot", False),
        "AY Share": ("fp_adv_rec_air_yard_share", True),
        "YPRR": ("fp_adv_rec_yprr", False),
        "1READ %": ("fp_adv_rec_first_read_rate", True),
        "XFP/RR": ("fp_adv_rec_xfp_per_route", False),
    },
    "rushing": {
        "Advanced::i5 %": ("fp_adv_rush_i5_rate", True),
        "Advanced::MTF/ATT": ("fp_adv_rush_mtf_per_att", False),
        "Advanced::YACO/ATT": ("fp_adv_rush_yaco_per_att", False),
        "Advanced::STUFF %": ("fp_adv_rush_stuff_rate", True),
    },
    "passing": {
        "Passing Advanced::CPOE": ("fp_adv_qb_cpoe", True),
        "Passing Advanced::aDOT": ("fp_adv_qb_adot", False),
        "Passing Advanced::Deep Throw %": ("fp_adv_qb_deep_throw_rate", True),
        "Passing Advanced::TWT %": ("fp_adv_qb_twt_rate", True),
        "Passing Advanced::PRESS SK %": ("fp_adv_qb_pressure_sack_rate", True),
    },
}
DERIVED_FEATURES = {"passing": ("fp_adv_qb_scramble_rate",)}
FEATURE_COLUMNS = tuple(
    spec[0]
    for family in ("passing", "receiving", "rushing")
    for spec in FEATURE_SPECS[family].values()
) + ("fp_adv_qb_scramble_rate",)


def _grouped_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3 or len(rows[0]) != len(rows[1]):
        raise ValueError(f"{path.name} lacks two-row grouped headers")
    groups: list[str] = []
    current = ""
    for value in rows[0]:
        if value.strip():
            current = value.strip()
        groups.append(current)
    if not current or not groups[0]:
        raise ValueError(f"{path.name} has blank grouped-header identity")
    semantic = [f"{group}::{name.strip()}" for group, name in zip(groups, rows[1])]
    if len(set(semantic)) != len(semantic):
        raise ValueError(f"{path.name} has duplicate group-qualified columns")
    if any(len(row) != len(semantic) for row in rows[2:]):
        raise ValueError(f"{path.name} has a malformed data-row width")
    return semantic, [dict(zip(semantic, row)) for row in rows[2:]]


def _plain_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f"{path.name} has missing/duplicate columns")
        return list(reader.fieldnames), list(reader)


def _cell(row: dict[str, str], family: str, name: str) -> str:
    if family == "receiving":
        return row.get(name, "")
    return row.get(f"Player Details::{name}", "")


def _number(value: object, *, percentage: bool = False) -> float:
    if value is None or str(value).strip() == "":
        return np.nan
    parsed = float(str(value).replace("%", "").strip())
    if not np.isfinite(parsed):
        raise ValueError("Advanced export contains a non-finite value")
    if percentage:
        # Air-yard share can legitimately be negative or exceed 100% when a
        # player's positive air yards offset teammates' negative air yards.
        parsed /= 100.0
    return parsed


def _parse_file(family: str, season: int, path: Path) -> list[dict]:
    columns, rows = (
        _plain_rows(path) if family == "receiving" else _grouped_rows(path))
    if len(rows) != EXPECTED_ROWS[family][season]:
        raise ValueError(
            f"{path.name} has {len(rows)} rows, want {EXPECTED_ROWS[family][season]}")
    required = set(FEATURE_SPECS[family])
    if family != "receiving":
        required |= {"Player Details::Name", "Player Details::Team",
                     "Player Details::POS", "Player Details::Season"}
    else:
        required |= {"Name", "Team", "POS", "Season"}
    if family == "passing":
        required |= {"Passing::DB", "Scrambles::SCRM"}
    if missing := required - set(columns):
        raise ValueError(f"{path.name} missing {sorted(missing)}")
    parsed: list[dict] = []
    for source_row, row in enumerate(rows, start=3 if family != "receiving" else 2):
        row_season = int(_cell(row, family, "Season"))
        if row_season != season:
            raise ValueError(f"{path.name} row {source_row} is season {row_season}")
        metrics = {
            output: _number(row.get(source), percentage=percentage)
            for source, (output, percentage) in FEATURE_SPECS[family].items()
        }
        if family == "passing":
            dropbacks = _number(row.get("Passing::DB"))
            scrambles = _number(row.get("Scrambles::SCRM"))
            metrics["fp_adv_qb_scramble_rate"] = (
                scrambles / dropbacks if dropbacks > 0 else np.nan)
        parsed.append({
            "season": season,
            "family": family,
            "vendor_name": _cell(row, family, "Name").strip(),
            "vendor_team": _cell(row, family, "Team").strip(),
            "vendor_pos": _cell(row, family, "POS").strip().upper(),
            "source_row": source_row,
            "metrics": metrics,
        })
    return parsed


def normalize_records(records: list[dict], snapshots: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Resolve parsed source records and coalesce only audited duplicates."""
    by_name, by_season_team = _snapshot_maps(snapshots)
    normalized: list[dict] = []
    resolution: list[str] = []
    for record in records:
        name = record["vendor_name"]
        vendor_pos = record["vendor_pos"]
        pos = "RB" if vendor_pos == "FB" else vendor_pos
        teams = _canonical_teams(record["vendor_team"])
        normalized_name = norm_name(name)
        gsis_id, status = _resolve_player(
            int(record["season"]), normalized_name, pos, teams,
            by_name, by_season_team)
        resolution.append(status)
        row = {
            "season": int(record["season"]),
            "family": record["family"],
            "gsis_id": gsis_id,
            "resolution_status": status,
            "vendor_name": name,
            "normalized_name": normalized_name,
            "vendor_team": record["vendor_team"],
            "canonical_teams": ",".join(teams),
            "vendor_pos": vendor_pos,
            "pos": pos,
            "source_file": record["source_file"],
            "source_sha256": record["source_sha256"],
            "source_row": int(record["source_row"]),
            "source_rows": str(record["source_row"]),
            "split_duplicate": False,
            **{column: np.nan for column in FEATURE_COLUMNS},
            **record["metrics"],
        }
        normalized.append(row)
    out = pd.DataFrame(normalized)
    out["_identity"] = out.gsis_id.fillna(
        "UNRESOLVED:" + out.normalized_name + ":" + out.pos + ":"
        + out.canonical_teams)
    keys = ["season", "family", "_identity"]
    coalesced: list[pd.Series] = []
    duplicate_groups = 0
    for _, group in out.groupby(keys, sort=False, dropna=False):
        if len(group) == 1:
            coalesced.append(group.iloc[0].copy())
            continue
        duplicate_groups += 1
        first = group.iloc[0].copy()
        known_split = (
            int(first.season) == 2022
            and first.family == "receiving"
            and first.normalized_name == norm_name("Brock Wright")
            and first.vendor_team == "DET"
        )
        if not known_split:
            values = group[list(FEATURE_COLUMNS)]
            if any(values[column].dropna().nunique() > 1 for column in values):
                raise ValueError("conflicting Advanced duplicate player-season")
        # The audited split lacks enough denominators for every frozen rate.
        # Suppress all rates instead of choosing one half or adding ratios.
        first[list(FEATURE_COLUMNS)] = np.nan
        first["split_duplicate"] = True
        first["source_rows"] = ",".join(str(value) for value in group.source_row)
        coalesced.append(first)
    result = pd.DataFrame(coalesced).drop(columns="_identity").reset_index(drop=True)
    audit = {
        "source_rows": len(records),
        "normalized_rows": len(result),
        "duplicate_groups_coalesced": duplicate_groups,
        "resolved_source_rows": resolution.count("resolved"),
        "unresolved_source_rows": resolution.count("unresolved"),
        "ambiguous_source_rows": resolution.count("ambiguous"),
        "resolved_normalized_rows": int(result.gsis_id.notna().sum()),
    }
    return result, audit


def read_exports(input_dir: str | Path, snapshots: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    root = Path(input_dir)
    records: list[dict] = []
    for family in ("receiving", "rushing", "passing"):
        for season, expected_hash in EXPECTED_HASHES[family].items():
            path = root / f"{season}-{FILE_SUFFIX[family]}"
            if not path.is_file():
                raise FileNotFoundError(path)
            actual_hash = _sha256(path)
            if actual_hash != expected_hash:
                raise ValueError(
                    f"{path.name} hash {actual_hash} != frozen {expected_hash}")
            parsed = _parse_file(family, season, path)
            for record in parsed:
                record["source_file"] = path.name
                record["source_sha256"] = actual_hash
            records.extend(parsed)
    return normalize_records(records, snapshots)


def run(input_dir: str | Path, *, write: bool = False) -> dict:
    """Audit licensed Advanced exports and optionally create a private table."""
    from google.api_core.exceptions import NotFound

    from ..bq import client, load_dataframe, query_df
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
                       ARRAY_AGG(DISTINCT source_sha256 ORDER BY source_sha256) AS hashes
                FROM `{table_ref}`
                """).iloc[0]
            wanted = sorted(
                value for family in EXPECTED_HASHES.values()
                for value in family.values())
            if (int(existing.n_rows or 0) != len(rows)
                    or sorted(list(existing.hashes)) != wanted):
                raise RuntimeError(f"refusing to overwrite non-identical {table_ref}")
            audit["write_disposition"] = "already-identical"
    print("FP_ADVANCED_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit
