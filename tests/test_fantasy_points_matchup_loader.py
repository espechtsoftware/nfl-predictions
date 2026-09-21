import hashlib
import json
from pathlib import Path

import pytest

from nfl_dfs.ingest import fantasy_points_matchups as loader


def _csv(path: Path, report: str) -> None:
    if report == "qb-coverage-matchup":
        path.write_text(
            '"Player Details","","","","","",""\n'
            '"Rank","Name","Team","POS","G","Season","OPP"\n'
            '"1","QB One","BUF","QB","1","2026","BLT"\n',
            encoding="utf-8",
        )
    elif report == "wr-coverage-matchup":
        path.write_text(
            '"Player Details","","","","","",""\n'
            '"Rank","Name","Team","POS","G","Season","OPP"\n'
            '"1","WR One","BLT","WR","1","2026","BUF"\n',
            encoding="utf-8",
        )
    else:
        path.write_text(
            '"Team Details","","","","","","Offense Stats","","","","","","","","Defense Stats"\n'
            '"Rank","Name","G","Season","Location","Team Name","RUSH GRADE","PASS GRADE","ADJ YBC/ATT","PRESS %","PrROE","Team","TM ATT","YBCO","Name"\n'
            '"1","Buffalo Bills","1","2026","Buffalo","Bills","1","1","1","1","1","BUF","1","1","Baltimore Ravens"\n',
            encoding="utf-8",
        )


def _raw_run(tmp_path: Path, complete: bool = True) -> Path:
    root = tmp_path / "raw"
    root.mkdir()
    reports = []
    for definition in loader.MATCHUPS:
        path = root / f"{definition.key}.csv"
        _csv(path, definition.key)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        reports.append({
            "key": definition.key,
            "status": "captured",
            "path": path.name,
            "sha256": digest,
            "schedule_gate": {"passes": True},
        })
    payload = {
        "schema_version": 1,
        "status": "complete" if complete else "failed",
        "run_id": "run-2026-w02",
        "target_season": 2026,
        "target_week": 2,
        "started_at_utc": "2026-09-20T10:00:00Z",
        "finished_at_utc": "2026-09-20T10:05:00Z",
        "reports": reports,
        "schedule_gate_failures": [],
    }
    (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    return root


def test_stage_and_normalize_preserves_hashes_and_statuses(tmp_path):
    raw = _raw_run(tmp_path)
    manifest = loader.stage_run(raw, tmp_path / "staged")
    staged, audit = loader.normalize_staged(manifest.parent)
    assert json.loads(manifest.read_text())["status"] == "staged"
    assert len(staged) == 3
    assert set(staged["report"]) == {x.key for x in loader.MATCHUPS}
    assert audit["source_run_id"] == "run-2026-w02"
    assert staged["source_sha256"].notna().all()


def test_failed_raw_run_is_retained_and_emits_failure_receipt(tmp_path):
    raw = _raw_run(tmp_path, complete=False)
    with pytest.raises(ValueError, match="not complete"):
        loader.stage_run(raw, tmp_path / "staged")
    receipt = json.loads((raw / "staging-failure.json").read_text())
    assert receipt["status"] == "staging_failed"
    assert (raw / "qb-coverage-matchup.csv").is_file()


def test_staging_is_idempotent_for_same_source_run(tmp_path):
    raw = _raw_run(tmp_path)
    first = loader.stage_run(raw, tmp_path / "staged")
    second = loader.stage_run(raw, tmp_path / "staged")
    assert first == second


def test_read_only_loader_reports_validated_without_bigquery(monkeypatch, tmp_path):
    raw = _raw_run(tmp_path)
    staged_manifest = loader.stage_run(raw, tmp_path / "staged")
    monkeypatch.setattr(loader, "settings", type("Settings", (), {"raw": "project.raw"})())
    audit = loader.run(staged_manifest.parent, write=False)
    assert audit["status"] == "validated"
    assert audit["append_rows"] is None
    assert audit["rows"] == 3
