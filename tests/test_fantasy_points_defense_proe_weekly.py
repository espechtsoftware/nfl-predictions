"""2026 weekly Defense PROE: frozen plan, one strictly-prior source week, schedule completeness, value-level append."""
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.ingest import fantasy_points_defense_proe_weekly as weekly
from nfl_dfs.ingest.fantasy_points_coverage import TEAM_NAMES
from nfl_dfs.ingest.fantasy_points_defense_proe import EXPECTED_COLUMNS
from nfl_dfs.ops import fantasy_points_downloads as fp

PLAN = Path(__file__).resolve().parents[1] / "automation/fantasy_points/plans/2026-defense-proe-weekly-v1.json"
NAMES = sorted(TEAM_NAMES)[:32]


def _run_dir(tmp_path, target_week=3, *, bye=(), value="-4.5", mutate=None, extra_week=False):
    source = target_week - 1
    path = tmp_path / "Defense-proeReportExport.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(EXPECTED_COLUMNS)
        for rank, name in enumerate(NAMES, start=1):
            weeks = {f"W{w}": "" for w in range(1, 19)}
            playing = TEAM_NAMES[name] not in bye
            if playing:
                weeks[f"W{source}"] = value
            if extra_week and rank == 1:
                weeks["W1" if source != 1 else "W2"] = "3.0"
            writer.writerow([rank, name, 1 if playing else 0, 2026, "", name, *weeks.values(), value if playing else ""])
    rows = list(csv.reader(path.open()))
    now = datetime(2026, 9, 23, 20, tzinfo=UTC).isoformat()
    manifest = {"schema_version": 1, "status": "complete", "run_id": f"20260923T200000Z__{weekly.PLAN_NAME}",
                "plan_sha256": weekly.PLAN_SHA256, "selected_target_week": target_week,
                "started_at_utc": now, "finished_at_utc": now,
                "exports": [{"status": "downloaded", "report": "offense-proe", "season": 2026, "weeks": [source],
                             "include_group_headers": False, "context": "Defense", "target_week": target_week,
                             "retrieved_at_utc": now,
                             "source_url": "https://data.fantasypoints.com/nfl/tools/team/defense/proe-report",
                             "path": path.name, "bytes": path.stat().st_size,
                             "csv_rows_including_headers": len(rows), "max_csv_columns": max(map(len, rows)),
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}
    if mutate:
        mutate(manifest)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


def test_frozen_plan_is_one_previous_week_defense_export_per_target_week():
    assert hashlib.sha256(PLAN.read_bytes()).hexdigest() == weekly.PLAN_SHA256
    _, specs = fp.load_plan(PLAN)
    for week in range(2, 19):
        (spec,) = fp.select_target_week(specs, week)
        assert (spec.report, spec.context, spec.weeks, spec.season) == ("offense-proe", "Defense", (week - 1,), 2026)


def test_one_source_week_normalizes_to_the_historical_schema(tmp_path):
    manifest, artifact = weekly.validate_manifest(_run_dir(tmp_path), target_week=3)
    rows = weekly.normalize_artifact(manifest, artifact, set(TEAM_NAMES[n] for n in NAMES))
    assert len(rows) == 32 and rows.week.eq(2).all() and rows.season.eq(2026).all()
    assert rows.defense_proe.eq(-0.045).all()
    assert list(rows.columns) == ["season", "week", "team", "defense_proe_pct", "defense_proe", "source_file",
                                  "source_sha256", "source_row", "source_run_id"]


def test_bye_teams_are_absent_and_must_match_the_schedule(tmp_path):
    bye = {"ARI", "ATL"}
    manifest, artifact = weekly.validate_manifest(_run_dir(tmp_path, bye=bye), target_week=3)
    playing = {TEAM_NAMES[n] for n in NAMES} - bye
    assert set(weekly.normalize_artifact(manifest, artifact, playing).team) == playing
    with pytest.raises(ValueError, match="differ from the Week-2 schedule"):
        weekly.normalize_artifact(manifest, artifact, playing | {"ARI"})


def test_a_value_outside_the_source_week_fails_closed(tmp_path):
    manifest, artifact = weekly.validate_manifest(_run_dir(tmp_path, extra_week=True), target_week=3)
    with pytest.raises(ValueError, match="non-source week"):
        weekly.normalize_artifact(manifest, artifact, {TEAM_NAMES[n] for n in NAMES})


@pytest.mark.parametrize("mutate, match", [
    (lambda m: m["exports"][0].update(weeks=[3]), "weeks"),
    (lambda m: m["exports"][0].update(context="Offense"), "context"),
    (lambda m: m.update(plan_sha256="0" * 64), "plan hash"),
    (lambda m: m["exports"][0].update(source_url="https://example.com/x"), "source URL"),
])
def test_manifest_is_fail_closed(tmp_path, mutate, match):
    with pytest.raises(ValueError, match=match):
        weekly.validate_manifest(_run_dir(tmp_path, mutate=mutate), target_week=3)


def test_append_compares_values_not_file_hashes(tmp_path):
    manifest, artifact = weekly.validate_manifest(_run_dir(tmp_path), target_week=3)
    rows = weekly.normalize_artifact(manifest, artifact, {TEAM_NAMES[n] for n in NAMES})
    stored = rows.assign(source_sha256="an-earlier-capture")
    assert weekly.rows_to_append(rows, stored).empty                       # unchanged week re-captured: no-op
    assert len(weekly.rows_to_append(rows, stored.iloc[:10])) == 22
    with pytest.raises(RuntimeError, match="conflicts"):
        weekly.rows_to_append(rows, stored.assign(defense_proe_pct=1.0))
