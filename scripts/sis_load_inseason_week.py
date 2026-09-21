#!/usr/bin/env python3
"""Load one in-season SIS team-game week into `nfl_raw.sis_team_context_game`.

WHY (operator decision 2026-09-18).  Every prior season is already in that table -- 2019 and
2021-2025, 17-18 weeks each -- and 2026 was empty, with the week's capture living only as loose
CSVs plus a bucket copy.  The operator's point: the data ends up in BigQuery anyway, so put it
where it cannot be lost rather than in files that can.

WHY A NEW SCRIPT RATHER THAN THE EXISTING IMPORTER.  `sis_team_context.read_tranche` is frozen to
the historical acquisition: it demands exactly 108 specs, a specific plan hash, a run-state file
and per-season row counts matching 2019/2021-2025.  Relaxing any of those to admit a weekly load
would weaken a validator that guards the historical table -- forbidden.  So this reuses the
per-artifact PARSER (`_read_artifact`, with the same position-based SCHEMAS and the same
`source_sha256_<report>` stamping) and does its own weekly assembly.  The frozen path is untouched.

SAFETY.  Nothing in `sql/features/` reads this table, so a load is inert for the Sunday build.
The script refuses to write a (season, week) that already has rows, so it cannot double-load.

DEFECT REPAIRED 2026-09-21.  The first version wrote only the parsed vendor columns and omitted
the six the loader is supposed to derive -- `team`, `opp`, `opp_team_id`, `game_key`,
`source_run_id`, `ingested_at`.  Every row of every other season carries them.  The load looked
successful, and the rows are fully populated on 73 of 79 columns, so nothing looked wrong; but
`team` is the natural join key, so a consumer joining on it silently drops the week, and one
aggregating without a team filter double-counts it.  The 2026 Week-1 load of 2026-09-19 landed
that way and a later corrected load appended 32 more, leaving 64 rows for 32 teams.  This version
derives the six columns with the SAME rules as the frozen historical importer (importing its
abbreviation map rather than copying it), validates both sides of every game, and refuses to write
a frame whose columns do not cover the destination table.

    python scripts/sis_load_inseason_week.py --input-dir <capture dir> --season 2026 --week 1 [--write]

Without --write it parses, validates and prints what it would load, and writes nothing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SOURCE_RUN = "sis-team-context-inseason-weekly-v1"
# The six columns the loader owns. Every row of every other season carries them;
# omitting them is what made the 2026 Week-1 load look successful while being
# unjoinable. Checked before any write.
CANONICAL_COLUMNS = ("team", "opp", "opp_team_id", "game_key", "source_run_id", "ingested_at")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nfl_dfs import bq  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.ingest.sis_team_context import (  # noqa: E402
    EXPECTED_REPORTS,
    KEY_COLUMNS,
    TABLE,
    _read_artifact,
)

DATASET = "nfl_raw"


def artifact_for(root: Path, report: str, season: int, week: int) -> Path:
    """The export CLI's naming: teams__<report>__season-Y__weeks-WW-WW__all-teams__game.csv"""
    name = (f"teams__{report}__season-{season}__weeks-{week:02d}-{week:02d}"
            f"__all-teams__game.csv")
    return root / name


def build(root: Path, season: int, week: int) -> pd.DataFrame:
    frames: dict[str, pd.DataFrame] = {}
    for report in EXPECTED_REPORTS:
        artifact = artifact_for(root, report, season, week)
        manifest = artifact.with_suffix(".manifest.json")
        if not artifact.is_file():
            raise FileNotFoundError(f"missing capture for {report}: {artifact}")
        if not manifest.is_file():
            raise FileNotFoundError(f"missing manifest for {report}: {manifest}")
        frame = _read_artifact(artifact, manifest, report)
        if frame.empty:
            raise ValueError(f"{report} parsed to zero rows")
        bad_season = set(frame.season.unique()) - {season}
        bad_week = set(frame.week.unique()) - {week}
        if bad_season or bad_week:
            raise ValueError(
                f"{report} carries unexpected season/week {bad_season or ''}{bad_week or ''}")
        if frame.duplicated(list(KEY_COLUMNS)).any():
            raise ValueError(f"{report} repeats a team-game key")
        frames[report] = frame

    base = frames[EXPECTED_REPORTS[0]]
    universe = set(map(tuple, base[list(KEY_COLUMNS)].to_numpy()))
    for report in EXPECTED_REPORTS[1:]:
        incoming = frames[report]
        if set(map(tuple, incoming[list(KEY_COLUMNS)].to_numpy())) != universe:
            raise ValueError(f"{report} covers a different team-game universe")
        if "team_id" in incoming:
            incoming = incoming.drop(columns=["team_id"])
        base = base.merge(incoming, on=list(KEY_COLUMNS), how="inner", validate="one_to_one")
    if len(base) != len(universe):
        raise ValueError("join changed the row count")
    return derive_canonical_columns(base)


def derive_canonical_columns(base: pd.DataFrame) -> pd.DataFrame:
    """Add the six columns the loader owns, exactly as the frozen importer does.

    Imports the abbreviation map from the frozen module rather than copying it, so
    the two cannot drift. Nothing here touches the frozen validator.
    """
    from datetime import UTC, datetime

    from nfl_dfs.ingest.sis_team_context import TEAM_ABBREVIATIONS

    base = base.copy()
    name_to_id = {}
    for row in base.itertuples():
        seen = name_to_id.setdefault(str(row.team_name), int(row.team_id))
        if seen != int(row.team_id):
            raise ValueError(f"SIS team name maps to multiple IDs: {row.team_name}")
    if missing := (set(base.team_name) | set(base.opp_name)) - set(TEAM_ABBREVIATIONS):
        raise ValueError(f"SIS team abbreviations missing: {sorted(missing)}")
    if missing := set(base.opp_name) - set(name_to_id):
        raise ValueError(f"SIS opponent IDs missing: {sorted(missing)}")
    base["team"] = base.team_name.map(TEAM_ABBREVIATIONS)
    base["opp"] = base.opp_name.map(TEAM_ABBREVIATIONS)
    base["opp_team_id"] = base.opp_name.map(name_to_id).astype(int)
    base["game_key"] = base.apply(
        lambda row: f"{row.season}-{row.week:02d}-" + "-".join(sorted((row.team, row.opp))), axis=1)
    base["source_run_id"] = SOURCE_RUN
    base["ingested_at"] = datetime.now(UTC)
    if base.duplicated(["season", "week", "team"]).any():
        raise ValueError("SIS weekly frame repeats a canonical team-week")
    sides = base.groupby("game_key").size()
    if not sides.eq(2).all():
        raise ValueError(
            f"SIS weekly frame does not carry both sides of every game: "
            f"{sides[sides != 2].to_dict()}")
    for column in CANONICAL_COLUMNS:
        if base[column].isna().any():
            raise ValueError(f"derived column {column} is null for some rows")
    return base


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input-dir", required=True, type=Path)
    ap.add_argument("--season", required=True, type=int)
    ap.add_argument("--week", required=True, type=int)
    ap.add_argument("--write", action="store_true", help="actually load; otherwise dry run")
    a = ap.parse_args()

    frame = build(a.input_dir, a.season, a.week)
    print(f"parsed {len(frame)} team-game rows, {len(frame.columns)} columns, "
          f"season {a.season} week {a.week}")
    lineage = [c for c in frame.columns if c.startswith("source_sha256_")]
    print("lineage columns:", ", ".join(sorted(lineage)))

    raw = settings.raw  # "<project>.<raw dataset>"
    existing = bq.query_df(
        f"SELECT COUNT(*) AS n FROM `{raw}.{TABLE}` "
        f"WHERE season = {a.season} AND week = {a.week}"
    ).iloc[0]["n"]
    if int(existing):
        print(f"REFUSING: {TABLE} already holds {existing} rows for "
              f"season {a.season} week {a.week}. Delete them first if a reload is intended.")
        return 1

    missing = [c for c in CANONICAL_COLUMNS if c not in frame.columns]
    if missing:
        print(f"REFUSING: frame is missing loader-derived columns {missing}; "
              f"rows without them are unjoinable and were the 2026-09-19 defect.")
        return 1
    destination = set(bq.query_df(
        f"SELECT column_name FROM `{raw}.INFORMATION_SCHEMA.COLUMNS` "
        f"WHERE table_name = '{TABLE}'").column_name)
    uncovered = destination - set(frame.columns)
    if uncovered:
        print(f"REFUSING: {TABLE} has {len(uncovered)} column(s) this frame does not "
              f"supply: {sorted(uncovered)}. A partial write looks successful and is not.")
        return 1

    if not a.write:
        print("dry run: nothing written. Re-run with --write to load.")
        return 0

    bq.load_dataframe(frame, f"{DATASET}.{TABLE}", write_disposition="WRITE_APPEND")
    after = bq.query_df(
        f"SELECT COUNT(*) AS n FROM `{raw}.{TABLE}` "
        f"WHERE season = {a.season} AND week = {a.week}"
    ).iloc[0]["n"]
    print(f"loaded. {TABLE} now holds {after} rows for season {a.season} week {a.week}")
    return 0 if int(after) == len(frame) else 1


if __name__ == "__main__":
    raise SystemExit(main())
