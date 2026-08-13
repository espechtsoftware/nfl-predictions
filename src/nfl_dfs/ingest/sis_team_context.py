"""Audited SIS team-game defense/line intake for historical PIT features.

The write-once raw table name predates its final content: this tranche contains
team pass defense, pass rush and blocking. Team passing/rushing offense and run
defense live in ``sis_team_run_context_game``. Keep that acquisition split
explicit rather than renaming provenance-bound raw tables.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..ops.sis_downloads import artifact_name, load_plan, plan_request_ceiling
from .fantasy_points_same_season_coverage import _write_once


TABLE = "sis_team_context_game"
SOURCE_RUN = "sis-team-context-tranche-1-v1"
EXPECTED_REPORTS = (
    "pass-defense-totals", "pass-defense-value",
    "pass-rush-totals", "pass-rush-value",
    "blocking-totals", "blocking-value",
)
EXPECTED_SEASON_ROWS = {
    2019: 512, 2021: 544, 2022: 542,
    2023: 544, 2024: 544, 2025: 544,
}

TEAM_ABBREVIATIONS = {
    "49ers": "SF", "Bears": "CHI", "Bengals": "CIN", "Bills": "BUF",
    "Broncos": "DEN", "Browns": "CLE", "Buccaneers": "TB",
    "Cardinals": "ARI", "Chargers": "LAC", "Chiefs": "KC",
    "Colts": "IND", "Commanders": "WAS", "Cowboys": "DAL",
    "Dolphins": "MIA", "Eagles": "PHI", "Falcons": "ATL",
    "Football Team": "WAS", "Giants": "NYG", "Jaguars": "JAX",
    "Jets": "NYJ", "Lions": "DET", "Packers": "GB", "Panthers": "CAR",
    "Patriots": "NE", "Raiders": "LV", "Rams": "LA", "Ravens": "BAL",
    "Redskins": "WAS", "Saints": "NO", "Seahawks": "SEA",
    "Steelers": "PIT", "Texans": "HOU", "Titans": "TEN",
    "Vikings": "MIN",
}

KEY_COLUMNS = ("season", "week", "team_name", "opp_name")

# Position-based schemas are intentional: two SIS blocking views export
# duplicate visible column labels, so DictReader would silently discard data.
SCHEMAS: dict[str, tuple[tuple[str, ...], tuple[str | None, ...]]] = {
    "passing-totals": (
        ("Rank", "Season", "Team", "Week", "Opp.", "Games", "Dropbacks",
         "Att", "Comp", "Catchable", "On-Tgt", "Gross Yds", "Net Yds",
         "Air Yards", "Intended Air Yards", "TDs", "Ints", "Sacks",
         "Pressures"),
        (None, "season", "team_name", "week", "opp_name", "games",
         "pass_dropbacks", "pass_attempts", "pass_completions",
         "pass_catchable", "pass_on_target", "pass_gross_yards",
         "pass_net_yards", "pass_air_yards", "pass_intended_air_yards",
         "pass_tds", "pass_interceptions", "pass_sacks", "pass_pressures"),
    ),
    "rushing-totals": (
        ("Rank", "Season", "Team", "Week", "Opp.", "Games", "Att", "Yds",
         "YAContact", "TDs", "Brkn Tkls", "Missed Tkls", "1st Downs",
         "Fum", "Fum Lost", "Hit at Line", "Stuffs", "Used Designed Gap"),
        (None, "season", "team_name", "week", "opp_name", "games",
         "rush_attempts", "rush_yards", "rush_yards_after_contact",
         "rush_tds", "rush_broken_tackles", "rush_missed_tackles",
         "rush_first_downs", "rush_fumbles", "rush_fumbles_lost",
         "rush_hit_at_line", "rush_stuffs", "rush_used_designed_gap"),
    ),
    "rushing-value": (
        ("Rank", "Season", "Team", "Week", "Opp.", "Att", "Points Earned",
         "PE Per Play", "Points Above Avg", "PAA Per Play", "EPA", "EPA/A",
         "Positive%", "PAR", "WAR", "Boom%", "Bust%"),
        (None, "season", "team_name", "week", "opp_name",
         "rush_value_attempts", "rush_points_earned",
         "rush_points_earned_per_play", "rush_points_above_average",
         "rush_paa_per_play", "rush_epa", "rush_epa_per_attempt",
         "rush_positive_rate", "rush_par", "rush_war", "rush_boom_rate",
         "rush_bust_rate"),
    ),
    "run-defense-totals": (
        ("Rank", "Season", "Team", "Week", "Opp.", "Games", "Att", "Yards",
         "TDs", "YAC", "First Downs", "Tackle Broken", "Missed Tkls", "FF",
         "FR", "FR TD", "Stuffs", "TFL"),
        (None, "season", "team_name", "week", "opp_name", "games",
         "rdef_attempts", "rdef_yards", "rdef_tds",
         "rdef_yards_after_contact", "rdef_first_downs",
         "rdef_tackles_broken", "rdef_missed_tackles",
         "rdef_forced_fumbles", "rdef_fumble_recoveries",
         "rdef_fumble_recovery_tds", "rdef_stuffs",
         "rdef_tackles_for_loss"),
    ),
    "run-defense-value": (
        ("Rank", "Season", "Team", "Week", "Opp.", "Points Saved",
         "PS Per Play", "Points Above Avg", "PAA Per Play", "EPA/A",
         "Positive%", "PAR", "WAR", "Boom%", "Bust%"),
        (None, "season", "team_name", "week", "opp_name",
         "rdef_points_saved", "rdef_points_saved_per_play",
         "rdef_points_above_average", "rdef_paa_per_play",
         "rdef_epa_per_attempt", "rdef_positive_rate", "rdef_par",
         "rdef_war", "rdef_boom_rate", "rdef_bust_rate"),
    ),
    "pass-defense-totals": (
        ("Rank", "Season", "Team", "Week", "Opp.", "Games", "Att",
         "Catchable", "Comp", "Yds", "TDs", "Ints", "Dropped INT",
         "Int. Yards", "Pass Def.", "Intended Air Yards", "DPI", "DPI Yds"),
        (None, "season", "team_name", "week", "opp_name", "games",
         "pdef_attempts", "pdef_catchable", "pdef_completions",
         "pdef_yards", "pdef_tds", "pdef_ints", "pdef_dropped_ints",
         "pdef_interception_yards", "pdef_pass_defenses",
         "pdef_intended_air_yards", "pdef_dpi", "pdef_dpi_yards"),
    ),
    "pass-defense-value": (
        ("Rank", "Season", "Team", "Week", "Opp.", "Att", "Points Saved",
         "PS Per Play", "Points Above Avg", "PAA Per Play", "EPA",
         "EPA/Play", "Positive%", "PAR", "WAR", "Boom%", "Bust%"),
        (None, "season", "team_name", "week", "opp_name", "pdef_value_attempts",
         "pdef_points_saved", "pdef_points_saved_per_play",
         "pdef_points_above_average", "pdef_paa_per_play", "pdef_epa",
         "pdef_epa_per_play", "pdef_positive_rate", "pdef_par", "pdef_war",
         "pdef_boom_rate", "pdef_bust_rate"),
    ),
    "pass-rush-totals": (
        ("Rank", "Season", "Team", "Week", "Opp.", "Games", "Solo Sacks",
         "Assist Sacks", "Combined Sacks", "Hurries", "Hits", "Knockdowns",
         "Pressures", "Pass Defl.", "Passes Batted", "FF", "FR"),
        (None, "season", "team_name", "week", "opp_name", "games",
         "prush_solo_sacks", "prush_assist_sacks", "prush_combined_sacks",
         "prush_hurries", "prush_hits", "prush_knockdowns",
         "prush_pressures", "prush_pass_deflections", "prush_passes_batted",
         "prush_forced_fumbles", "prush_fumble_recoveries"),
    ),
    "pass-rush-value": (
        ("Rank", "Season", "Team", "Week", "Opp.", "Points Saved",
         "PS Per Play", "Points Above Avg", "PAA Per Play", "Positive%",
         "PAR", "WAR"),
        (None, "season", "team_name", "week", "opp_name",
         "prush_points_saved", "prush_points_saved_per_play",
         "prush_points_above_average", "prush_paa_per_play",
         "prush_positive_rate", "prush_par", "prush_war"),
    ),
    "blocking-totals": (
        ("Rank", "Year", "Team", "Week", "Opp.", "Games", "Snaps", "BB",
         "Holds", "PassSnap", "BB", "Holds", "RushSnap", "BB", "Holds"),
        (None, "season", "team_name", "week", "opp_name", "games",
         "block_snaps", "block_blown_blocks", "block_holds",
         "pass_block_snaps", "pass_block_blown_blocks", "pass_block_holds",
         "run_block_snaps", "run_block_blown_blocks", "run_block_holds"),
    ),
    "blocking-value": (
        ("Rank", "Year", "Team", "Week", "Opp.", "Snaps", "Points Earned",
         "PE Per Play", "Points Above Avg", "PAA Per Play", "PAR", "WAR",
         "Snaps", "Points Earned", "Snaps", "Points Earned"),
        (None, "season", "team_name", "week", "opp_name", "block_value_snaps",
         "block_points_earned", "block_points_earned_per_play",
         "block_points_above_average", "block_paa_per_play", "block_par",
         "block_war", "pass_block_value_snaps", "pass_block_points_earned",
         "run_block_value_snaps", "run_block_points_earned"),
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value: str, *, integer: bool = False) -> float | int:
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return np.nan
    percentage = cleaned.endswith("%")
    if percentage:
        cleaned = cleaned[:-1]
    parsed = float(cleaned)
    if not np.isfinite(parsed):
        raise ValueError(f"SIS numeric value is not finite: {value!r}")
    if percentage:
        parsed /= 100.0
    if integer:
        if not parsed.is_integer():
            raise ValueError(f"SIS integer field is fractional: {value!r}")
        return int(parsed)
    return parsed


def _identity_map(manifest: dict, artifact: Path) -> dict[tuple, int]:
    identities = manifest.get("identities")
    if not isinstance(identities, list):
        raise ValueError(f"{artifact.name} manifest has no identity rows")
    output: dict[tuple, int] = {}
    for item in identities:
        key = (
            int(item["season"]), int(item["week"]),
            str(item["team"]), str(item["opp"]),
        )
        team_id = int(item["teamId"])
        if key in output:
            raise ValueError(f"{artifact.name} manifest repeats identity {key}")
        output[key] = team_id
    return output


def _read_artifact(artifact: Path, manifest_path: Path, report: str) -> pd.DataFrame:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("artifact") != artifact.name:
        raise ValueError(f"{manifest_path.name} points to another artifact")
    if manifest.get("sha256") != _sha256(artifact):
        raise ValueError(f"{artifact.name} hash differs from its manifest")
    source_header, output_header = SCHEMAS[report]
    with artifact.open(encoding="utf-8-sig", newline="") as handle:
        source = list(csv.reader(handle))
    if not source or tuple(source[0]) != source_header:
        raise ValueError(f"{artifact.name} SIS schema differs")
    if len(source) - 1 != int(manifest.get("rows", -1)):
        raise ValueError(f"{artifact.name} row count differs from its manifest")
    identities = _identity_map(manifest, artifact)
    records = []
    for source_row, values in enumerate(source[1:], start=2):
        if len(values) != len(output_header):
            raise ValueError(f"{artifact.name} row {source_row} width differs")
        row = {
            name: value
            for name, value in zip(output_header, values)
            if name is not None
        }
        row["season"] = _number(row["season"], integer=True)
        row["week"] = _number(row["week"], integer=True)
        if "games" in row and _number(row["games"], integer=True) != 1:
            raise ValueError(f"{artifact.name} row {source_row} is not game grain")
        key = tuple(row[column] for column in KEY_COLUMNS)
        if key not in identities:
            raise ValueError(f"{artifact.name} row {source_row} lacks stable SIS ID")
        row["team_id"] = identities[key]
        for column in tuple(row):
            if column not in {*KEY_COLUMNS, "team_id", "games"}:
                row[column] = _number(row[column])
        row[f"source_sha256_{report.replace('-', '_')}"] = manifest["sha256"]
        records.append(row)
    frame = pd.DataFrame(records)
    if frame.duplicated(list(KEY_COLUMNS)).any():
        raise ValueError(f"{artifact.name} repeats team-game keys")
    if set(identities) != set(map(tuple, frame[list(KEY_COLUMNS)].to_numpy())):
        raise ValueError(f"{artifact.name} CSV/API identity universes differ")
    return frame.drop(columns=["games"], errors="ignore")


def read_tranche(
    input_dir: str | Path,
    plan_path: str | Path = "automation/sis/plans/team-context-tranche-1.json",
) -> tuple[pd.DataFrame, dict]:
    """Validate all 108 artifacts and form one exact team-game table."""
    root = Path(input_dir)
    plan = Path(plan_path)
    specs = load_plan(plan)
    if len(specs) != 108 or {spec.report for spec in specs} != set(EXPECTED_REPORTS):
        raise ValueError("SIS team-context plan differs from its frozen tranche")
    state_path = root / f".{plan.stem}.run-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("plan_sha256") != _sha256(plan):
        raise ValueError("SIS team-context run state has another plan hash")
    if int(state.get("ceiling", -1)) != plan_request_ceiling(plan):
        raise ValueError("SIS team-context run-state ceiling differs")
    if not 0 <= int(state.get("used", -1)) <= int(state["ceiling"]):
        raise ValueError("SIS team-context run-state request count is invalid")

    report_parts: dict[str, list[pd.DataFrame]] = {
        report: [] for report in EXPECTED_REPORTS}
    for spec in specs:
        artifact = root / artifact_name(spec)
        manifest = artifact.with_suffix(".manifest.json")
        if not artifact.is_file() or not manifest.is_file():
            raise FileNotFoundError(artifact if not artifact.is_file() else manifest)
        report_parts[spec.report].append(
            _read_artifact(artifact, manifest, spec.report))

    reports = {}
    for report, parts in report_parts.items():
        combined = pd.concat(parts, ignore_index=True)
        if combined.duplicated(list(KEY_COLUMNS)).any():
            raise ValueError(f"SIS {report} repeats a team-game across windows")
        counts = combined.groupby("season").size().to_dict()
        if counts != EXPECTED_SEASON_ROWS:
            raise ValueError(f"SIS {report} season rows differ: {counts}")
        reports[report] = combined

    base = reports[EXPECTED_REPORTS[0]]
    for report in EXPECTED_REPORTS[1:]:
        incoming = reports[report]
        if set(map(tuple, base[list(KEY_COLUMNS)].to_numpy())) != set(
            map(tuple, incoming[list(KEY_COLUMNS)].to_numpy())
        ):
            raise ValueError(f"SIS {report} team-game universe differs")
        if "team_id" in incoming:
            incoming = incoming.drop(columns=["team_id"])
        base = base.merge(
            incoming, on=list(KEY_COLUMNS), how="inner", validate="one_to_one")

    name_to_id = {}
    for frame in reports.values():
        for row in frame[["team_name", "team_id"]].drop_duplicates().itertuples(
            index=False
        ):
            prior = name_to_id.setdefault(str(row.team_name), int(row.team_id))
            if prior != int(row.team_id):
                raise ValueError(f"SIS team name maps to multiple IDs: {row.team_name}")
    if missing := (set(base.team_name) | set(base.opp_name)) - set(TEAM_ABBREVIATIONS):
        raise ValueError(f"SIS team abbreviations missing: {sorted(missing)}")
    if missing := set(base.opp_name) - set(name_to_id):
        raise ValueError(f"SIS opponent IDs missing: {sorted(missing)}")
    base["team"] = base.team_name.map(TEAM_ABBREVIATIONS)
    base["opp"] = base.opp_name.map(TEAM_ABBREVIATIONS)
    base["opp_team_id"] = base.opp_name.map(name_to_id).astype(int)
    base["game_key"] = base.apply(
        lambda row: f"{row.season}-{row.week:02d}-"
        + "-".join(sorted((row.team, row.opp))), axis=1)
    base["source_run_id"] = SOURCE_RUN
    base = base.sort_values(["season", "week", "team_id"]).reset_index(drop=True)
    if base.duplicated(["season", "week", "team"]).any():
        raise ValueError("SIS final table repeats a canonical team-week")
    if not base.groupby("game_key").size().eq(2).all():
        raise ValueError("SIS final table does not contain both sides of every game")
    audit = {
        "source_run_id": SOURCE_RUN,
        "artifacts": len(specs),
        "rows": int(len(base)),
        "games": int(base.game_key.nunique()),
        "seasons": sorted(map(int, base.season.unique())),
        "season_rows": {
            str(key): int(value)
            for key, value in base.groupby("season").size().items()
        },
        "columns": list(base.columns),
        "api_requests_used": int(state["used"]),
        "api_request_ceiling": int(state["ceiling"]),
        "point_in_time_contract": "target week W may use only source week < W",
    }
    return base, audit


def run(
    input_dir: str | Path,
    *,
    plan_path: str | Path = "automation/sis/plans/team-context-tranche-1.json",
    write: bool = False,
) -> dict:
    from ..config import settings

    rows, audit = read_tranche(input_dir, plan_path)
    table_ref = f"{settings.raw}.{TABLE}"
    audit.update({"table": table_ref, "write_requested": bool(write)})
    if write:
        hash_columns = tuple(
            column for column in rows if column.startswith("source_sha256_")
        )
        audit["write_disposition"] = _write_once(
            table_ref, rows, run_id=SOURCE_RUN, hash_columns=hash_columns)
    print("SIS_TEAM_CONTEXT_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit


__all__ = ["read_tranche", "run"]
