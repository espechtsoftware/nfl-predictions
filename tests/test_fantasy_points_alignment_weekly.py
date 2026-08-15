import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.ingest import fantasy_points_alignment_weekly as weekly


def _write_alignment(path):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "Player Details", "", "", "", "", "", "Overall",
            "Wide", "Slot", "Inline", "Backfield",
        ])
        writer.writerow([
            "Rank", "Name", "Team", "POS", "G", "Season", "RTE",
            "RTE", "RTE", "RTE", "RTE",
        ])
        writer.writerow([
            1, "Wide Receiver", "HST", "WR", 4, 2026, 100,
            70, 20, 10, "",
        ])
        writer.writerow([
            2, "Slot Receiver", "HST", "WR", 4, 2026, 80,
            10, 60, 10, "",
        ])


def _manifest(tmp_path, *, target_week=5):
    artifact = tmp_path / "alignment.csv"
    _write_alignment(artifact)
    rows = list(csv.reader(artifact.open()))
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    now = datetime(2026, 10, 7, 15, tzinfo=UTC).isoformat()
    manifest = {
        "schema_version": 1,
        "status": "complete",
        "run_id": f"20261007T150000Z__{weekly.PLAN_NAME}",
        "plan_sha256": weekly.PLAN_SHA256,
        "selected_target_week": target_week,
        "started_at_utc": now,
        "finished_at_utc": now,
        "exports": [{
            "status": "downloaded",
            "report": weekly.REPORT,
            "season": 2026,
            "weeks": list(range(target_week - 4, target_week)),
            "include_group_headers": True,
            "context": "Player",
            "target_week": target_week,
            "retrieved_at_utc": now,
            "source_url": (
                "https://data.fantasypoints.com/nfl/tools/player/"
                "receiving-separation-by-alignment"
            ),
            "path": artifact.name,
            "bytes": artifact.stat().st_size,
            "csv_rows_including_headers": len(rows),
            "max_csv_columns": max(map(len, rows)),
            "sha256": digest,
        }],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return manifest


def test_frozen_weekly_plan_hash_matches_tracked_file():
    path = (
        Path(__file__).resolve().parents[1]
        / "automation/fantasy_points/plans/2026-alignment-last-four-weekly-v1.json"
    )
    assert hashlib.sha256(path.read_bytes()).hexdigest() == weekly.PLAN_SHA256


def test_weekly_alignment_manifest_and_parser_are_strictly_prior(tmp_path):
    manifest = _manifest(tmp_path)
    parsed, artifact = weekly.validate_manifest(tmp_path, target_week=5)
    assert parsed["run_id"] == manifest["run_id"]
    snapshots = pd.DataFrame([
        {"season": 2026, "gsis_id": "wide", "name": "Wide Receiver",
         "pos": "WR", "team": "HOU"},
        {"season": 2026, "gsis_id": "slot", "name": "Slot Receiver",
         "pos": "WR", "team": "HOU"},
    ])
    players, teams, audit = weekly.normalize_artifact(
        parsed, artifact, snapshots)
    assert players.source_week_start.eq(1).all()
    assert players.source_week_end.eq(4).all()
    assert players.source_week_end.lt(players.target_week).all()
    assert audit["supported_player_rows"] == 2
    assert teams.iloc[0].offense_wide_share == pytest.approx(0.5)
    assert teams.iloc[0].source_sha256 == artifact["sha256"]


def test_weekly_alignment_rejects_target_week_in_source_window(tmp_path):
    payload = _manifest(tmp_path)
    payload["exports"][0]["weeks"] = [2, 3, 4, 5]
    (tmp_path / "manifest.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="weeks"):
        weekly.validate_manifest(tmp_path, target_week=5)


def test_weekly_alignment_append_is_idempotent_and_conflicts_on_hash():
    rows = pd.DataFrame([{
        "season": 2026, "target_week": 5,
        "normalized_name": "receiver", "position": "WR",
        "source_sha256": "same",
    }])
    existing = rows.copy()
    assert weekly._novel_or_identical(
        rows, existing,
        keys=["season", "target_week", "normalized_name", "position"],
    ).empty
    changed = existing.copy()
    changed["source_sha256"] = "different"
    with pytest.raises(RuntimeError, match="conflicts"):
        weekly._novel_or_identical(
            rows, changed,
            keys=["season", "target_week", "normalized_name", "position"],
        )
