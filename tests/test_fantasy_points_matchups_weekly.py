import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs import bq
from nfl_dfs.ingest import fantasy_points_matchups_weekly as weekly
from nfl_dfs.ops import fantasy_points_matchups as matchups
from tests.fp_matchup_fixtures import (
    FakeDriver,
    _write_grouped,
    capture,
    directional_pairs,
    export_rows_for,
    schedule_frame,
    snapshots_for,
)


def _good_script(schedule):
    pairs = directional_pairs(schedule)
    return {d.key: [export_rows_for(d.key, pairs)] for d in matchups.MATCHUPS}


class FakeWarehouse:
    """Records loads and answers the loader's two query shapes."""

    def __init__(self, snapshots: pd.DataFrame) -> None:
        self.snapshots = snapshots
        self.tables: dict[str, pd.DataFrame] = {}
        self.loads: list[tuple[str, int, str | None]] = []

    def query_df(self, sql: str, params=None):
        from google.api_core.exceptions import NotFound

        if "rosters_weekly" in sql:
            return self.snapshots
        table = sql.split("`")[1]
        if table not in self.tables:
            raise NotFound(table)
        frame = self.tables[table]
        return frame[(frame.season == params["season"]) & (frame.target_week == params["target_week"])]

    def load_dataframe(self, df, table, write_disposition="WRITE_TRUNCATE", job_id=None, **_):
        assert write_disposition == "WRITE_APPEND"
        self.loads.append((table, len(df), job_id))
        self.tables[table] = pd.concat([self.tables.get(table, pd.DataFrame()), df], ignore_index=True)


@pytest.fixture
def warehouse(monkeypatch):
    schedule = schedule_frame()
    house = FakeWarehouse(snapshots_for(schedule))
    monkeypatch.setattr(bq, "query_df", house.query_df)
    monkeypatch.setattr(bq, "load_dataframe", house.load_dataframe)
    return house


def _captured_run(tmp_path, monkeypatch, *, archive=True) -> Path:
    schedule = schedule_frame()
    driver = FakeDriver(_good_script(schedule))
    return capture(tmp_path, monkeypatch, driver, schedule=schedule, archive=archive).parent


def test_metric_columns_are_deterministic_and_unique():
    assert weekly.metric_column("Cover 3::QB Cover 3 %") == "cover_3__qb_cover_3_pct"
    assert weekly.metric_column("Matchup::EXP FP/DB") == "matchup__exp_fp_per_db"
    assert weekly.metric_column("Offense Stats::ADJ YBC/ATT") == "offense__adj_ybc_per_att"
    for report in weekly.REPORTS:
        names = weekly.metric_columns(report)
        assert len(names) == len(set(names))
    assert len(weekly.metric_columns("qb-coverage-matchup")) == 25
    assert len(weekly.metric_columns("wr-coverage-matchup")) == 31
    assert len(weekly.metric_columns("line-matchups")) == 12


def test_loader_stages_a_validated_run_once_with_full_lineage(tmp_path, monkeypatch, warehouse):
    run_dir = _captured_run(tmp_path, monkeypatch)
    stamp = datetime(2026, 9, 22, 16, 0, tzinfo=UTC)
    audit = weekly.run(run_dir, target_week=3, write=True, now=stamp)
    assert audit["input_kind"] == "run-dir"
    assert audit["status_counts"] == {"validated": 0, "staged": 3}
    assert [table for table, _, _ in warehouse.loads] == [
        f"{bq.settings.raw}.{weekly.TABLES[key]}" for key in weekly.REPORTS
    ]
    for table, rows, job_id in warehouse.loads:
        assert rows == 4
        assert job_id.startswith("fp-matchup-weekly--")
    qb = warehouse.tables[f"{bq.settings.raw}.fantasy_points_qb_coverage_matchup_weekly"]
    assert set(qb.columns) >= set(weekly.KEY_COLUMNS) | {
        "gsis_id", "resolution_status", "source_run_id", "source_retrieved_at",
        "first_kickoff_utc", "archive_uri", "ingested_at", "matchup__cov_grade",
    }
    assert qb.resolution_status.eq("resolved").all()
    assert qb.gsis_id.notna().all()
    assert (qb.season == 2026).all() and (qb.target_week == 3).all()
    assert (qb.source_season == 2025).all()
    assert qb.source_run_id.eq(run_dir.name).all()
    assert qb.archive_uri.str.startswith("gs://test-bucket/").all()
    assert sorted(zip(qb.team, qb.opponent)) == directional_pairs(schedule_frame())
    line = warehouse.tables[f"{bq.settings.raw}.fantasy_points_line_matchup_weekly"]
    assert line.identity.tolist() == line.team.tolist()
    assert line.resolution_status.eq("team").all()
    assert line.gsis_id.isna().all()
    ledger = matchups.read_ledger(run_dir)
    for key in weekly.REPORTS:
        assert ledger["reports"][key]["staged"]["rows"] == 4
        assert ledger["reports"][key]["consumed"] is None
        assert (run_dir / f"staging-receipt-{key}.json").is_file()
    receipt = json.loads((run_dir / "staging-receipt-qb-coverage-matchup.json").read_text())
    assert receipt["write_disposition"] == "appended"
    assert receipt["status"] == "staged"

    # Idempotent: the same bytes append nothing and the ledger stays bound.
    again = weekly.run(run_dir, target_week=3, write=True, now=stamp)
    assert len(warehouse.loads) == 3
    for key in weekly.REPORTS:
        assert again["reports"][key]["write_disposition"] == "already-identical"
        assert again["reports"][key]["append_rows"] == 0
        assert again["reports"][key]["existing_rows_for_target_week"] == 4


def test_loader_keeps_a_second_capture_of_the_same_week_beside_the_first(tmp_path, monkeypatch, warehouse):
    first = _captured_run(tmp_path, monkeypatch)
    weekly.run(first, target_week=3, write=True)
    schedule = schedule_frame()
    pairs = directional_pairs(schedule)
    script = {d.key: [export_rows_for(d.key, pairs, value=0.9)] for d in matchups.MATCHUPS}
    second = capture(
        tmp_path / "second", monkeypatch, FakeDriver(script), schedule=schedule,
        archive=True, now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
    ).parent
    audit = weekly.run(second, target_week=3, write=True)
    for key in weekly.REPORTS:
        assert audit["reports"][key]["append_rows"] == 4
        assert audit["reports"][key]["existing_rows_for_target_week"] == 4
    qb = warehouse.tables[f"{bq.settings.raw}.fantasy_points_qb_coverage_matchup_weekly"]
    assert qb.source_sha256.nunique() == 2
    assert qb.source_run_id.nunique() == 2
    assert len(qb) == 8


def test_loader_dry_run_writes_nothing_and_reports_counts(tmp_path, monkeypatch, warehouse):
    run_dir = _captured_run(tmp_path, monkeypatch, archive=False)
    audit = weekly.run(run_dir, target_week=3, write=False)
    assert warehouse.loads == []
    assert audit["status_counts"] == {"validated": 3, "staged": 0}
    assert audit["reports"]["wr-coverage-matchup"]["table_existed"] is False
    assert not list(run_dir.glob("staging-receipt-*.json"))
    with pytest.raises(ValueError, match="no hash-addressed archive recorded"):
        weekly.run(run_dir, target_week=3, write=True)


def test_loader_rejects_wrong_week_old_schema_and_tampered_bytes(tmp_path, monkeypatch, warehouse):
    run_dir = _captured_run(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="target week differs"):
        weekly.run(run_dir, target_week=4)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    original = manifest_path.read_text()
    manifest["schema_version"] = 1
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="schema must be 2"):
        weekly.run(run_dir, target_week=3)
    manifest_path.write_text(original)
    artifact = run_dir / manifest["validated_reports"]["line-matchups"]["path"]
    artifact.write_bytes(artifact.read_bytes().replace(b"1.50", b"9.99"))
    with pytest.raises(ValueError, match="hash differs"):
        weekly.run(run_dir, target_week=3)


def test_loader_refuses_a_partial_run_unless_told_and_never_stages_rejected_exports(tmp_path, monkeypatch, warehouse):
    schedule = schedule_frame()
    pairs = directional_pairs(schedule)
    stale = [(team, "KC" if team == "BUF" else opponent) for team, opponent in pairs]
    script = _good_script(schedule)
    script["qb-coverage-matchup"] = [export_rows_for("qb-coverage-matchup", stale)]
    with pytest.raises(matchups.MatchupCaptureError):
        capture(tmp_path, monkeypatch, FakeDriver(script), schedule=schedule, archive=True, max_attempts=1)
    run_dir = next((tmp_path / "automated").iterdir())
    with pytest.raises(ValueError, match="no validated export for \\['qb-coverage-matchup'\\]"):
        weekly.run(run_dir, target_week=3, write=True)
    audit = weekly.run(run_dir, target_week=3, write=True, allow_partial=True)
    assert audit["missing_reports"] == ["qb-coverage-matchup"]
    assert sorted(audit["reports"]) == ["line-matchups", "wr-coverage-matchup"]
    assert all("qb_coverage" not in table for table, _, _ in warehouse.loads)


def test_loader_fails_on_header_drift_and_non_numeric_cells(tmp_path, monkeypatch, warehouse):
    run_dir = _captured_run(tmp_path, monkeypatch)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    entry = manifest["validated_reports"]["wr-coverage-matchup"]
    path = run_dir / entry["path"]
    raw = path.read_bytes()
    # Same byte count, one cell letters instead of digits: re-hash to keep the
    # manifest honest so only the numeric gate is under test.
    tampered = raw.replace(b'"0.51"', b'"abcd"', 1)
    assert len(tampered) == len(raw) and tampered != raw
    path.write_bytes(tampered)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for report in manifest["reports"]:
        if report["key"] == "wr-coverage-matchup":
            report["sha256"] = digest
    entry["sha256"] = digest
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="non-numeric"):
        weekly.run(run_dir, target_week=3)

    schedule = schedule_frame()
    drifted = run_dir / "drift.csv"
    rows = export_rows_for("qb-coverage-matchup", directional_pairs(schedule))
    _write_grouped(drifted, "qb-coverage-matchup", rows)
    drifted.write_text(drifted.read_text(encoding="utf-8-sig").replace("COV GRADE", "COV SCORE", 1), encoding="utf-8-sig")
    with pytest.raises(ValueError, match="header drift"):
        weekly._rederive_artifact(
            report="qb-coverage-matchup", local_path=drifted,
            claimed_sha256=hashlib.sha256(drifted.read_bytes()).hexdigest(),
            claimed_bytes=drifted.stat().st_size,
            retrieved_at=pd.Timestamp("2026-09-22T15:00Z"),
            expected=matchups.expected_schedule_pairs(schedule),
            first_kickoff=pd.Timestamp("2026-09-27T17:00Z"), target_week=3,
        )


def test_rows_to_append_skips_same_key_and_rejects_corrupt_existing():
    rows = pd.DataFrame([
        {"season": 2026, "target_week": 3, "report": "line-matchups", "identity": "BUF",
         "team": "BUF", "opponent": "BAL", "source_sha256": "aa", "offense__ybco": 1.0},
        {"season": 2026, "target_week": 3, "report": "line-matchups", "identity": "BAL",
         "team": "BAL", "opponent": "BUF", "source_sha256": "aa", "offense__ybco": 2.0},
    ])
    existing = rows.iloc[:1][list(weekly.KEY_COLUMNS)]
    novel = weekly.rows_to_append(rows, existing)
    assert novel.identity.tolist() == ["BAL"]
    assert weekly.rows_to_append(rows, pd.DataFrame()).equals(rows)
    with pytest.raises(RuntimeError, match="duplicate append keys"):
        weekly.rows_to_append(rows, pd.concat([existing, existing]))


# Seal mode (Week 1, schema-1 member runs) -------------------------------------


def _schema1_run(root: Path, run_id: str, schedule, *, key: str, retrieved: str, kickoff: str) -> tuple[Path, str]:
    run_dir = root / run_id
    run_dir.mkdir(parents=True)
    artifact = run_dir / f"{key}.csv"
    _write_grouped(artifact, key, export_rows_for(key, directional_pairs(schedule)))
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    expected = matchups.expected_schedule_pairs(schedule)
    manifest = {
        "schema_version": 1, "capture_id": matchups.CAPTURE_ID, "run_id": run_id,
        "target_season": 2026, "target_week": 1, "first_kickoff_utc": kickoff,
        "expected_schedule_pairs": [list(p) for p in sorted(expected)],
        "reports": [{
            "key": key, "status": "captured", "path": artifact.name, "sha256": digest,
            "bytes": artifact.stat().st_size, "retrieved_at_utc": retrieved,
            "source_url": f"https://data.fantasypoints.com/nfl/tools/x/{key}",
        }],
        "status": "failed", "error": "RuntimeError: matchup schedule gate failed for: other",
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    return run_dir, digest


def test_seal_mode_stages_independently_validated_members(tmp_path, monkeypatch, warehouse):
    schedule = schedule_frame(gameday="2026-09-13")
    kickoff = "2026-09-13T17:00:00+00:00"
    root = tmp_path / "automated"
    members = []
    for index, key in enumerate(weekly.REPORTS):
        run_id = f"2026090919{index:02d}00Z__{matchups.CAPTURE_ID}__week-01"
        retrieved = f"2026-09-09T19:{index:02d}:30+00:00"
        _, digest = _schema1_run(root, run_id, schedule, key=key, retrieved=retrieved, kickoff=kickoff)
        members.append({
            "report": key, "source_run_id": run_id, "retrieved_at_utc": retrieved,
            "source_url": "https://data.fantasypoints.com/nfl/tools/x", "sha256": digest,
            "bytes": (root / run_id / f"{key}.csv").stat().st_size,
            "archive_uri": f"gs://bucket/licensed/fantasy-points/live-matchups/season=2026/week=01/sha256={digest}/{key}.csv",
            "archive_generation": "1",
        })
    seal_path = tmp_path / "seal.json"
    seal_path.write_text(json.dumps({
        "schema_version": 1, "capture_id": matchups.CAPTURE_ID, "status": weekly.SEAL_STATUS,
        "target_season": 2026, "target_week": 1, "first_kickoff_utc": kickoff, "members": members,
    }))
    audit = weekly.run(seal_path, target_week=1, write=True, output_root=root)
    assert audit["input_kind"] == "seal"
    assert audit["status_counts"] == {"validated": 0, "staged": 3}
    assert len(warehouse.loads) == 3
    wr = warehouse.tables[f"{bq.settings.raw}.fantasy_points_wr_coverage_matchup_weekly"]
    assert (wr.target_week == 1).all()
    assert wr.source_run_id.iloc[0].startswith("20260909")
    for member in members:
        ledger = matchups.read_ledger(root / member["source_run_id"])
        entry = ledger["reports"][member["report"]]
        assert entry["downloaded"]["attempts"][0]["rederived_by"] == "fantasy_points_matchups_weekly"
        assert entry["validated"]["sha256"] == member["sha256"]
        assert entry["staged"]["rows"] == 4

    bad = json.loads(seal_path.read_text())
    bad["members"][0]["sha256"] = "0" * 64
    (tmp_path / "bad.json").write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="no report record with the sealed hash"):
        weekly.run(tmp_path / "bad.json", target_week=1, output_root=root)
    with pytest.raises(ValueError, match="needs output_root"):
        weekly.run(seal_path, target_week=1)


def test_seal_mode_rejects_a_member_captured_after_kickoff(tmp_path, monkeypatch, warehouse):
    schedule = schedule_frame(gameday="2026-09-13")
    kickoff = "2026-09-13T17:00:00+00:00"
    root = tmp_path / "automated"
    members = []
    for index, key in enumerate(weekly.REPORTS):
        run_id = f"2026091318{index:02d}00Z__{matchups.CAPTURE_ID}__week-01"
        retrieved = "2026-09-13T18:00:00+00:00" if key == "line-matchups" else "2026-09-13T12:00:00+00:00"
        _, digest = _schema1_run(root, run_id, schedule, key=key, retrieved=retrieved, kickoff=kickoff)
        members.append({
            "report": key, "source_run_id": run_id, "retrieved_at_utc": retrieved,
            "sha256": digest, "bytes": (root / run_id / f"{key}.csv").stat().st_size,
            "archive_uri": "gs://bucket/x",
        })
    seal_path = tmp_path / "seal.json"
    seal_path.write_text(json.dumps({
        "schema_version": 1, "capture_id": matchups.CAPTURE_ID, "status": weekly.SEAL_STATUS,
        "target_season": 2026, "target_week": 1, "first_kickoff_utc": kickoff, "members": members,
    }))
    with pytest.raises(ValueError, match="line-matchups: retrieved at/after"):
        weekly.run(seal_path, target_week=1, output_root=root)
    assert warehouse.loads == []
