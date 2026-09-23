"""The typed DDL is the contract; the loader and shadow must produce exactly its columns."""

import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from nfl_dfs.ingest import fantasy_points_matchups_weekly as weekly
from nfl_dfs.research import fp_matchup_shadow as shadow
from tests.fp_matchup_fixtures import (
    FakeDriver,
    capture,
    directional_pairs,
    export_rows_for,
    schedule_frame,
    snapshots_for,
)


REPO = Path(__file__).resolve().parents[1]
SQL = REPO / "sql"


def _ddl_tables(path: Path) -> dict[str, list[str]]:
    """Map each CREATE TABLE's bare table name to its ordered column names."""
    text = path.read_text()
    tables: dict[str, list[str]] = {}
    for match in re.finditer(
        r"CREATE TABLE IF NOT EXISTS `\$\{(raw|features)\}\.(\w+)`\s*\((.*?)\)\s*PARTITION BY",
        text, re.S,
    ):
        body = match.group(3)
        columns = []
        for line in body.splitlines():
            line = line.strip().rstrip(",")
            if not line or line.startswith("--"):
                continue
            columns.append(line.split()[0])
        tables[match.group(2)] = columns
    return tables


def _staged_frames(tmp_path, monkeypatch) -> dict[str, pd.DataFrame]:
    schedule = schedule_frame()
    pairs = directional_pairs(schedule)
    script = {key: [export_rows_for(key, pairs)] for key in weekly.REPORTS}
    run_dir = capture(tmp_path, monkeypatch, FakeDriver(script), schedule=schedule, archive=True).parent
    kickoff = pd.Timestamp("2026-09-27T17:00:00Z")
    expected = {(a, b) for a, b in pairs}
    capture_info, artifacts = weekly.validate_run_dir(
        run_dir, target_week=3, kickoff=kickoff, expected=expected,
    )
    frames = {}
    for key in weekly.REPORTS:
        rows, _ = weekly.normalize_report(capture_info, artifacts[key], snapshots_for(schedule))
        payload = weekly._typed_payload(rows)
        payload["ingested_at"] = datetime(2026, 9, 22, 16, 0, tzinfo=UTC)
        frames[key] = payload
    return frames


def test_staging_ddl_matches_loader_columns_exactly(tmp_path, monkeypatch):
    ddl = _ddl_tables(SQL / "raw" / "010_fantasy_points_matchups_weekly.sql")
    assert set(ddl) == set(weekly.TABLES.values())
    frames = _staged_frames(tmp_path, monkeypatch)
    for key, table in weekly.TABLES.items():
        assert list(frames[key].columns) == ddl[table], table
    assert weekly.DDL_PATH == "raw/010_fantasy_points_matchups_weekly.sql"
    assert (SQL / weekly.DDL_PATH).is_file()


def test_shadow_ddl_matches_builder_columns_exactly(tmp_path, monkeypatch):
    ddl = _ddl_tables(SQL / "research" / "fp_matchup_shadow_tables.sql")
    assert set(ddl) == set(shadow.SHADOW_TABLES.values())
    staged = _staged_frames(tmp_path, monkeypatch)
    for frame in staged.values():
        frame.drop(columns=["ingested_at"], inplace=True)
    frames, _ = shadow.build(
        week=3, kickoff=pd.Timestamp("2026-09-27T17:00:00Z"), staged=staged,
        snapshots=snapshots_for(schedule_frame()), generated_at=datetime(2026, 9, 25, tzinfo=UTC),
    )
    for key, table in shadow.SHADOW_TABLES.items():
        assert list(shadow._typed_payload(frames[key]).columns) == ddl[table], table
    assert shadow.DDL_PATH == "research/fp_matchup_shadow_tables.sql"
    assert (SQL / shadow.DDL_PATH).is_file()


def test_shadow_ddl_is_outside_the_feature_build_glob():
    assert not list((SQL / "features").glob("*fp_matchup*"))
    assert not list((SQL / "features").glob("*fantasy_points_matchup*"))
    for path in (SQL / "raw" / "010_fantasy_points_matchups_weekly.sql", SQL / "research" / "fp_matchup_shadow_tables.sql"):
        text = path.read_text()
        assert text.count("CREATE TABLE IF NOT EXISTS") == 3, path.name
        assert "CREATE OR REPLACE" not in text, path.name
