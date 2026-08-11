"""Hash-locked import for the paid receiver coverage-fit diagnostic."""

from __future__ import annotations

import csv
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
from ..names import norm_name


RECEIVER_TABLE = "fantasy_points_receiver_coverage_prior"
DEFENSE_TABLE = "fantasy_points_defense_coverage_prior"
SEASONS = (2022, 2023, 2024, 2025)
MAN_ZONE_HASHES = {
    2022: "8033f7b539335a1d4bf4590ac7bcb0994c19eaf66b69a749803dbbf4f686e26d",
    2023: "aef16ffb479911bbdfeb072dba8edf5fa4fc3ba6ec8aad8caf029009e8e850f5",
    2024: "53e22d570a89c0e5578928cf7ca3634d94e6378fd3a896f67500e86361c0585c",
    2025: "b448016a04cf883bfbe53913e0666812e72f53ab92f853c6cb71db594bc86404",
}
SEPARATION_HASHES = {
    2022: "6eaf9e0d63794f39679f048c24f409b79c0b798611708cdc71fadfe84328ea1c",
    2023: "11538dfee6662572ab5502993a36fcb45e15a8d15f6ea7e288cd1082125c0787",
    2024: "2d97db23f9452118c4b16da70e7eb024c161625f84778d701d4f84b6fd033db0",
    2025: "0b7ccaffba50d0a2608cfab1dbc803fd57d46693d1984ff37bf85619c91193da",
}
DEFENSE_HASHES = {
    2022: "45ff5738d28c19b0dd098f07de438d335a1be229c32066fc19eb90ad58b740bf",
    2023: "52af5f92251eec85b34b875a24bccaa1e4d1b44196bf68b2e4e14ff65e35a394",
    2024: "7270273e2e3ee400865c4c9c69b96d0b7eba2f0f005526942b5324a8fbe9606a",
    2025: "35ccde32e391b65426ace44452019389d1f1ef08d9cd5a279a6d5d2c9bd2b8c8",
}
EXPECTED_RECEIVER_ROWS = {2022: 540, 2023: 513, 2024: 522, 2025: 519}
DEFENSE_FILENAMES = {
    2022: "2022-Defense-coverageMatrixExport.csv",
    2023: "2023-Defense-coverageMatrixExport.csv",
    2024: "2024-Defense-coverageMatrixExport.csv",
    2025: "Devense-coverageMatrixExport.csv",
}
TEAM_NAMES = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL", "Denver Broncos": "DEN",
    "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA", "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN", "New England Patriots": "NE",
    "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}


def _identity(row: dict[str, str]) -> tuple[str, str, tuple[str, ...]]:
    pos = row["Player Details::POS"].strip().upper()
    pos = "RB" if pos == "FB" else pos
    return (
        norm_name(row["Player Details::Name"].strip()),
        pos,
        _canonical_teams(row["Player Details::Team"].strip()),
    )


def _read_receiver_family(
    path: Path,
    *,
    season: int,
    family: str,
) -> tuple[dict[tuple, list[dict]], str]:
    expected_hash = (
        MAN_ZONE_HASHES if family == "man_zone" else SEPARATION_HASHES
    )[season]
    actual_hash = _sha256(path)
    if actual_hash != expected_hash:
        raise ValueError(f"{path.name} hash {actual_hash} != frozen {expected_hash}")
    columns, source = _grouped_rows(path)
    required = {
        "Player Details::Name", "Player Details::Team",
        "Player Details::POS", "Player Details::Season",
        "Overall::RTE", "Overall::TPRR", "Overall::YPRR",
        "Man::RTE", "Man::TPRR", "Man::YPRR",
        "Zone::RTE", "Zone::TPRR", "Zone::YPRR",
    }
    if family == "man_zone":
        required |= {"Overall::FP/RR", "Man::FP/RR", "Zone::FP/RR"}
    else:
        required |= {
            "Zone::SEP SCORE",
            "Cover 2::RTE", "Cover 2::SEP SCORE",
            "Cover 3::RTE", "Cover 3::SEP SCORE",
            "Cover 4::RTE", "Cover 4::SEP SCORE",
            "Cover 6::RTE", "Cover 6::SEP SCORE",
        }
    if missing := required - set(columns):
        raise ValueError(f"{path.name} missing {sorted(missing)}")
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for source_row, row in enumerate(source, start=3):
        if int(row["Player Details::Season"]) != season:
            raise ValueError(f"{path.name} row {source_row} has wrong season")
        if row["Player Details::POS"].strip().upper() == "QB":
            continue
        grouped[(season, *_identity(row))].append({
            "row": row,
            "source_row": source_row,
        })
    if sum(len(values) for values in grouped.values()) != EXPECTED_RECEIVER_ROWS[season]:
        raise ValueError(f"{path.name} has unexpected skill-position row count")
    return grouped, actual_hash


def _metric(row: dict[str, str], name: str) -> float:
    return _number(row.get(name))


def read_receiver_exports(
    root: str | Path,
    snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    root = Path(root)
    by_name, by_season_team = _snapshot_maps(snapshots)
    output: list[dict] = []
    status_counts: Counter[str] = Counter()
    duplicate_groups = 0
    for season in SEASONS:
        man_path = root / f"{season}-receivingManVsZoneExport.csv"
        sep_path = root / f"{season}-receivingSeparationByCoverageExport.csv"
        man, man_hash = _read_receiver_family(
            man_path, season=season, family="man_zone")
        sep, sep_hash = _read_receiver_family(
            sep_path, season=season, family="separation")
        if set(man) != set(sep):
            raise ValueError(f"{season} receiver coverage identity universes differ")
        for key in sorted(man):
            _, normalized_name, pos, teams = key
            man_group, sep_group = man[key], sep[key]
            split = len(man_group) != 1 or len(sep_group) != 1
            if split:
                known = (
                    season == 2022
                    and normalized_name == norm_name("Brock Wright")
                    and pos == "TE"
                    and teams == ("DET",)
                    and len(man_group) == len(sep_group) == 2
                )
                if not known:
                    raise ValueError("unexpected duplicate receiver coverage identity")
                duplicate_groups += 1
            first = man_group[0]["row"]
            gsis_id, status = _resolve_player(
                season, normalized_name, pos, teams,
                by_name, by_season_team)
            status_counts[status] += 1
            man_row = man_group[0]["row"]
            sep_row = sep_group[0]["row"]
            values = {
                "overall_routes": _metric(man_row, "Overall::RTE"),
                "overall_tprr": _metric(man_row, "Overall::TPRR"),
                "overall_yprr": _metric(man_row, "Overall::YPRR"),
                "overall_fprr": _metric(man_row, "Overall::FP/RR"),
                "man_routes": _metric(man_row, "Man::RTE"),
                "man_tprr": _metric(man_row, "Man::TPRR"),
                "man_yprr": _metric(man_row, "Man::YPRR"),
                "man_fprr": _metric(man_row, "Man::FP/RR"),
                "zone_routes": _metric(man_row, "Zone::RTE"),
                "zone_tprr": _metric(man_row, "Zone::TPRR"),
                "zone_yprr": _metric(man_row, "Zone::YPRR"),
                "zone_fprr": _metric(man_row, "Zone::FP/RR"),
                "zone_sep": _metric(sep_row, "Zone::SEP SCORE"),
            }
            for shell in (2, 3, 4, 6):
                values[f"cover{shell}_routes"] = _metric(
                    sep_row, f"Cover {shell}::RTE")
                values[f"cover{shell}_sep"] = _metric(
                    sep_row, f"Cover {shell}::SEP SCORE")
            if split:
                values = {name: np.nan for name in values}
            output.append({
                "season": season,
                "gsis_id": gsis_id,
                "resolution_status": status,
                "vendor_name": first["Player Details::Name"].strip(),
                "normalized_name": normalized_name,
                "vendor_team": first["Player Details::Team"].strip(),
                "canonical_teams": ",".join(teams),
                "vendor_pos": first["Player Details::POS"].strip().upper(),
                "pos": pos,
                "split_duplicate": split,
                "man_zone_source_file": man_path.name,
                "man_zone_source_sha256": man_hash,
                "separation_source_file": sep_path.name,
                "separation_source_sha256": sep_hash,
                "man_zone_source_rows": ",".join(
                    str(item["source_row"]) for item in man_group),
                "separation_source_rows": ",".join(
                    str(item["source_row"]) for item in sep_group),
                **values,
            })
    frame = pd.DataFrame(output)
    audit = {
        "rows": int(len(frame)),
        "resolved_rows": int(frame.gsis_id.notna().sum()),
        "unresolved_rows": int(status_counts["unresolved"]),
        "ambiguous_rows": int(status_counts["ambiguous"]),
        "duplicate_groups_suppressed": duplicate_groups,
    }
    return frame, audit


def _read_matrix(path: Path, season: int) -> tuple[list[list[str]], str]:
    actual_hash = _sha256(path)
    if actual_hash != DEFENSE_HASHES[season]:
        raise ValueError(f"{path.name} hash {actual_hash} != frozen hash")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) != 34 or len(rows[0]) != len(rows[1]) or len(rows[1]) != 22:
        raise ValueError(f"{path.name} is not the frozen 32x22 matrix")
    if any(len(row) != 22 for row in rows[2:]):
        raise ValueError(f"{path.name} has malformed rows")
    return rows, actual_hash


def read_defense_exports(root: str | Path) -> tuple[pd.DataFrame, dict]:
    root = Path(root)
    output: list[dict] = []
    required = (
        "Name", "Season", "MAN %", "ZONE %", "COVER 2 %",
        "COVER 3 %", "COVER 4 %", "COVER 6 %",
    )
    for season in SEASONS:
        path = root / DEFENSE_FILENAMES[season]
        rows, source_hash = _read_matrix(path, season)
        header = rows[1]
        positions = {}
        for name in required:
            matches = [ix for ix, value in enumerate(header) if value == name]
            if len(matches) != 1:
                raise ValueError(f"{path.name} has {len(matches)} {name!r} columns")
            positions[name] = matches[0]
        seen: set[str] = set()
        for source_row, row in enumerate(rows[2:], start=3):
            if int(row[positions["Season"]]) != season:
                raise ValueError(f"{path.name} row {source_row} has wrong season")
            vendor_name = row[positions["Name"]].strip()
            if vendor_name not in TEAM_NAMES:
                raise ValueError(f"unmapped defense {vendor_name!r}")
            team = TEAM_NAMES[vendor_name]
            if team in seen:
                raise ValueError(f"duplicate defense {team} in {path.name}")
            seen.add(team)
            output.append({
                "season": season,
                "team": team,
                "vendor_name": vendor_name,
                "def_man_rate": _number(row[positions["MAN %"]]) / 100.0,
                "def_zone_rate": _number(row[positions["ZONE %"]]) / 100.0,
                "def_cover2_rate": _number(row[positions["COVER 2 %"]]) / 100.0,
                "def_cover3_rate": _number(row[positions["COVER 3 %"]]) / 100.0,
                "def_cover4_rate": _number(row[positions["COVER 4 %"]]) / 100.0,
                "def_cover6_rate": _number(row[positions["COVER 6 %"]]) / 100.0,
                "source_file": path.name,
                "source_sha256": source_hash,
                "source_row": source_row,
            })
        if len(seen) != 32:
            raise ValueError(f"{path.name} did not resolve 32 defenses")
    frame = pd.DataFrame(output)
    rates = frame[[column for column in frame if column.startswith("def_")]]
    if not ((rates >= 0) & (rates <= 1)).all().all():
        raise ValueError("defense coverage rate outside [0,1]")
    return frame, {"rows": int(len(frame)), "teams": int(frame.team.nunique())}


def read_exports(
    input_dir: str | Path,
    snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    receivers, receiver_audit = read_receiver_exports(input_dir, snapshots)
    defenses, defense_audit = read_defense_exports(input_dir)
    return receivers, defenses, {
        "receiver": receiver_audit,
        "defense": defense_audit,
    }


def _ensure_table(table_ref: str, rows: pd.DataFrame, hashes: set[str]) -> str:
    from google.api_core.exceptions import NotFound

    from ..bq import client, load_dataframe, query_df

    try:
        client().get_table(table_ref)
    except NotFound:
        payload = rows.copy()
        payload["ingested_at"] = pd.Timestamp.now(tz="UTC")
        load_dataframe(payload, table_ref, write_disposition="WRITE_EMPTY")
        return "created"
    existing = query_df(f"""
        SELECT COUNT(*) AS n_rows,
               ARRAY_AGG(DISTINCT source_sha256 ORDER BY source_sha256) AS hashes
        FROM `{table_ref}`
        """).iloc[0]
    if int(existing.n_rows or 0) != len(rows) or set(existing.hashes) != hashes:
        raise RuntimeError(f"refusing to overwrite non-identical {table_ref}")
    return "already-identical"


def _receiver_identity_query(table_ref: str) -> str:
    """Return the idempotency query using a non-reserved hash alias."""
    return f"""
        SELECT COUNT(*) AS n_rows,
               ARRAY_AGG(DISTINCT source_hash ORDER BY source_hash) AS hashes
        FROM `{table_ref}`,
        UNNEST([man_zone_source_sha256, separation_source_sha256]) AS source_hash
        """


def run(input_dir: str | Path, *, write: bool = False) -> dict:
    """Audit the three frozen source families and optionally create tables."""
    from ..bq import query_df
    from ..config import settings

    snapshots = query_df(f"""
        SELECT DISTINCT season, gsis_id, name, pos, team
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season BETWEEN 2022 AND 2025
        """, params={"panel_id": PANEL_ID})
    receivers, defenses, audit = read_exports(input_dir, snapshots)
    audit.update({
        "receiver_table": f"{settings.raw}.{RECEIVER_TABLE}",
        "defense_table": f"{settings.raw}.{DEFENSE_TABLE}",
        "write_requested": bool(write),
    })
    if write:
        receiver_hashes = set(MAN_ZONE_HASHES.values()) | set(SEPARATION_HASHES.values())
        # Receiver rows carry two hashes, so idempotency needs a direct query.
        from google.api_core.exceptions import NotFound
        from ..bq import client, load_dataframe

        receiver_ref = f"{settings.raw}.{RECEIVER_TABLE}"
        try:
            client().get_table(receiver_ref)
        except NotFound:
            payload = receivers.copy()
            payload["ingested_at"] = pd.Timestamp.now(tz="UTC")
            load_dataframe(payload, receiver_ref, write_disposition="WRITE_EMPTY")
            audit["receiver_write_disposition"] = "created"
        else:
            existing = query_df(
                _receiver_identity_query(receiver_ref)).iloc[0]
            if (int(existing.n_rows or 0) != 2 * len(receivers)
                    or set(existing.hashes) != receiver_hashes):
                raise RuntimeError(
                    f"refusing to overwrite non-identical {receiver_ref}")
            audit["receiver_write_disposition"] = "already-identical"
        audit["defense_write_disposition"] = _ensure_table(
            f"{settings.raw}.{DEFENSE_TABLE}", defenses,
            set(DEFENSE_HASHES.values()))
    print("FP_COVERAGE_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit
