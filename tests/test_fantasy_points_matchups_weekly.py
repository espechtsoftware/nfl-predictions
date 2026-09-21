import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs import bq
from nfl_dfs.ingest import fantasy_points_matchups_weekly as weekly
from nfl_dfs.ops import fantasy_points_matchups as matchups
from tests.fp_matchup_fixtures import (
    DEFAULT_NOW,
    FakeDriver,
    _write_grouped,
    archive_check_ok,
    capture,
    directional_pairs,
    export_rows_for,
    factory_for,
    schedule_frame,
    snapshots_for,
)


KICKOFF = pd.Timestamp("2026-09-27T17:00:00Z")


def _good_script(schedule, **kwargs):
    pairs = directional_pairs(schedule)
    return {d.key: [export_rows_for(d.key, pairs, **kwargs)] for d in matchups.MATCHUPS}


class FakeWarehouse:
    """Records loads and answers the loader's query shapes."""

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
    monkeypatch.setattr(weekly, "_schedule", lambda season, week: schedule)
    return house


def _run(*args, **kwargs):
    kwargs.setdefault("archive_check", archive_check_ok)
    return weekly.run(*args, **kwargs)


def _captured_run(tmp_path, monkeypatch, *, archive=True, now=None) -> Path:
    schedule = schedule_frame()
    driver = FakeDriver(_good_script(schedule))
    return capture(tmp_path, monkeypatch, driver, schedule=schedule, archive=archive, now=now).parent


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
    audit = _run(run_dir, target_week=3, write=True, now=stamp)
    assert audit["input_kind"] == "run-dir"
    assert audit["schedule_authority"].endswith(".schedules")
    assert audit["first_kickoff_utc"] == KICKOFF.isoformat()
    assert audit["status_counts"] == {"validated": 0, "staged": 3}
    assert [table for table, _, _ in warehouse.loads] == [
        f"{bq.settings.raw}.{weekly.TABLES[key]}" for key in weekly.REPORTS
    ]
    for table, rows, job_id in warehouse.loads:
        assert rows == 4
        assert job_id.startswith("fp-matchup-weekly--")
    qb = warehouse.tables[f"{bq.settings.raw}.fantasy_points_qb_coverage_matchup_weekly"]
    assert set(qb.columns) >= set(weekly.KEY_COLUMNS) | set(weekly.VENDOR_KEY) | {
        "identity", "gsis_id", "resolution_status", "source_run_id", "source_retrieved_at",
        "first_kickoff_utc", "archive_uri", "ingested_at", "matchup__cov_grade",
    }
    assert qb.resolution_status.eq("resolved").all()
    assert qb.gsis_id.notna().all()
    assert (qb.season == 2026).all() and (qb.target_week == 3).all()
    assert (qb.source_season == 2025).all()
    assert qb.source_run_id.eq(run_dir.name).all()
    assert qb.source_row.tolist() == [3, 4, 5, 6]
    prefix = (
        f"gs://{bq.settings.gcs_bucket}/licensed/fantasy-points/live-matchups/"
        "season=2026/week=03/sha256="
    )
    assert qb.archive_uri.str.startswith(prefix).all()
    assert sorted(zip(qb.team, qb.opponent)) == directional_pairs(schedule_frame())
    line = warehouse.tables[f"{bq.settings.raw}.fantasy_points_line_matchup_weekly"]
    assert line.identity.tolist() == line.team.tolist()
    assert line.resolution_status.eq("team").all()
    assert line.gsis_id.isna().all()
    ledger = matchups.read_ledger(run_dir)
    for key in weekly.REPORTS:
        assert ledger["reports"][key]["staged"]["rows"] == 4
        assert ledger["reports"][key]["staged"]["sha256"] == ledger["reports"][key]["validated"]["sha256"]
        assert ledger["reports"][key]["consumed"] is None
        assert (run_dir / f"staging-receipt-{key}.json").is_file()
    receipt = json.loads((run_dir / "staging-receipt-qb-coverage-matchup.json").read_text())
    assert receipt["write_disposition"] == "appended"
    assert receipt["status"] == "staged"
    assert receipt["archive_generation"] == "1"

    # Idempotent: the same bytes append nothing and the ledger stays bound.
    again = _run(run_dir, target_week=3, write=True, now=stamp)
    assert len(warehouse.loads) == 3
    for key in weekly.REPORTS:
        assert again["reports"][key]["write_disposition"] == "already-identical"
        assert again["reports"][key]["append_rows"] == 0
        assert again["reports"][key]["existing_rows_for_target_week"] == 4


def test_loader_append_key_is_a_function_of_the_bytes_not_the_roster(tmp_path, monkeypatch, warehouse):
    run_dir = _captured_run(tmp_path, monkeypatch)
    # First load with one QB missing from the roster snapshot.
    full = warehouse.snapshots
    warehouse.snapshots = full[full.name != "QB BAL"]
    first = _run(run_dir, target_week=3, write=True)
    assert first["reports"]["qb-coverage-matchup"]["unresolved_rows"] == 1
    qb_table = f"{bq.settings.raw}.fantasy_points_qb_coverage_matchup_weekly"
    assert len(warehouse.tables[qb_table]) == 4
    # The roster now resolves him; re-running appends nothing and issues no job.
    warehouse.snapshots = full
    second = _run(run_dir, target_week=3, write=True)
    assert second["reports"]["qb-coverage-matchup"]["append_rows"] == 0
    assert second["reports"]["qb-coverage-matchup"]["write_disposition"] == "already-identical"
    assert len(warehouse.loads) == 3
    assert len(warehouse.tables[qb_table]) == 4
    assert warehouse.tables[qb_table].identity.str.startswith("UNRESOLVED:").sum() == 1


def test_loader_keeps_a_second_capture_of_the_same_week_beside_the_first(tmp_path, monkeypatch, warehouse):
    first = _captured_run(tmp_path, monkeypatch)
    _run(first, target_week=3, write=True)
    schedule = schedule_frame()
    pairs = directional_pairs(schedule)
    script = {d.key: [export_rows_for(d.key, pairs, value=0.9)] for d in matchups.MATCHUPS}
    second = capture(
        tmp_path / "second", monkeypatch, FakeDriver(script), schedule=schedule,
        archive=True, now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
    ).parent
    audit = _run(second, target_week=3, write=True)
    for key in weekly.REPORTS:
        assert audit["reports"][key]["append_rows"] == 4
        assert audit["reports"][key]["existing_rows_for_target_week"] == 4
    qb = warehouse.tables[f"{bq.settings.raw}.fantasy_points_qb_coverage_matchup_weekly"]
    assert qb.source_sha256.nunique() == 2
    assert qb.source_run_id.nunique() == 2
    assert len(qb) == 8


def test_loader_dry_run_writes_nothing_and_reports_counts(tmp_path, monkeypatch, warehouse):
    run_dir = _captured_run(tmp_path, monkeypatch, archive=False)
    audit = _run(run_dir, target_week=3, write=False)
    assert warehouse.loads == []
    assert audit["status_counts"] == {"validated": 3, "staged": 0}
    assert audit["reports"]["wr-coverage-matchup"]["table_existed"] is False
    assert audit["reports"]["wr-coverage-matchup"]["max_games"] == 17
    assert not list(run_dir.glob("staging-receipt-*.json"))
    with pytest.raises(ValueError, match="no hash-addressed archive recorded"):
        _run(run_dir, target_week=3, write=True)


def test_loader_requires_the_archive_object_on_write(tmp_path, monkeypatch, warehouse):
    run_dir = _captured_run(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="archive object is missing"):
        weekly.run(
            run_dir, target_week=3, write=True,
            archive_check=lambda uri: {"exists": False, "generation": None},
        )
    assert warehouse.loads == []
    # A URI that is not the hash-addressed object for these bytes is refused
    # even in a dry run.
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    bogus = "gs://other-bucket/sha256=0000/nothing.csv"
    for report in manifest["reports"]:
        report["archive_uri"] = bogus
    for entry in manifest["validated_reports"].values():
        entry["archive_uri"] = bogus
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="is not the hash-addressed object"):
        _run(run_dir, target_week=3)


def test_loader_rejects_wrong_week_old_schema_and_tampered_bytes(tmp_path, monkeypatch, warehouse):
    run_dir = _captured_run(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="target week differs"):
        _run(run_dir, target_week=4)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    original = manifest_path.read_text()
    manifest["schema_version"] = 1
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="schema must be 2"):
        _run(run_dir, target_week=3)
    manifest_path.write_text(original)
    artifact = run_dir / manifest["validated_reports"]["line-matchups"]["path"]
    artifact.write_bytes(artifact.read_bytes().replace(b"1.50", b"9.99"))
    with pytest.raises(ValueError, match="hash differs"):
        _run(run_dir, target_week=3)


def test_loader_derives_kickoff_and_pairs_from_the_schedule_not_the_manifest(tmp_path, monkeypatch, warehouse):
    run_dir = _captured_run(tmp_path, monkeypatch)
    manifest_path = run_dir / "manifest.json"
    original = manifest_path.read_text()
    manifest = json.loads(original)
    # Manifest claims a later kickoff and post-kickoff retrievals: refused
    # against the schedule authority even though the two claims agree.
    manifest["first_kickoff_utc"] = "2026-10-04T17:00:00+00:00"
    for report in manifest["reports"]:
        report["retrieved_at_utc"] = "2026-09-28T12:00:00+00:00"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="differs from the schedule authority"):
        _run(run_dir, target_week=3, write=True)
    assert warehouse.loads == []
    # Kickoff intact, retrievals moved after it: refused.
    manifest = json.loads(original)
    for report in manifest["reports"]:
        report["retrieved_at_utc"] = "2026-09-28T12:00:00+00:00"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="retrieved at/after"):
        _run(run_dir, target_week=3, write=True)
    # Retrieval moved earlier than the file was written: refused.
    manifest = json.loads(original)
    for report in manifest["reports"]:
        report["retrieved_at_utc"] = "2026-09-01T12:00:00+00:00"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="after its recorded retrieval"):
        _run(run_dir, target_week=3)
    # Manifest pairs tampered: refused.
    manifest = json.loads(original)
    manifest["expected_schedule_pairs"] = manifest["expected_schedule_pairs"][:2]
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="expected pairs differ from the schedule authority"):
        _run(run_dir, target_week=3)
    manifest_path.write_text(original)
    # A file whose modification time is after kickoff (a late copy) is refused.
    artifact = run_dir / manifest["validated_reports"]["line-matchups"]["path"]
    late = pd.Timestamp("2026-09-27T18:00:00Z").timestamp()
    os.utime(artifact, (late, late))
    with pytest.raises(ValueError, match="at/after the first kickoff"):
        _run(run_dir, target_week=3)


def test_loader_active_season_export_cannot_post_date_the_target_week(tmp_path, monkeypatch, warehouse):
    schedule = schedule_frame()
    pairs = directional_pairs(schedule)
    # An active-season (2026) aggregate with 3 games played for target Week 3.
    script = {d.key: [export_rows_for(d.key, pairs, season=2026, games=3)] for d in matchups.MATCHUPS}
    run_dir = capture(tmp_path, monkeypatch, FakeDriver(script), schedule=schedule, archive=True).parent
    with pytest.raises(ValueError, match="3 games played in an active-season export for target Week 3"):
        _run(run_dir, target_week=3)
    script = {d.key: [export_rows_for(d.key, pairs, season=2026, games=2)] for d in matchups.MATCHUPS}
    run_dir = capture(
        tmp_path / "ok", monkeypatch, FakeDriver(script), schedule=schedule, archive=True,
        now=datetime(2026, 9, 22, 15, 1, tzinfo=UTC),
    ).parent
    audit = _run(run_dir, target_week=3)
    assert audit["reports"]["line-matchups"]["source_regime"] == "vendor-active-season-early"


def test_loader_refuses_a_partial_run_unless_told_and_never_stages_rejected_exports(tmp_path, monkeypatch, warehouse):
    schedule = schedule_frame()
    pairs = directional_pairs(schedule)
    stale = [(team, "KC" if team == "BUF" else opponent) for team, opponent in pairs]
    script = _good_script(schedule)
    script["qb-coverage-matchup"] = [export_rows_for("qb-coverage-matchup", stale)]
    with pytest.raises(matchups.MatchupCaptureError):
        capture(tmp_path, monkeypatch, FakeDriver(script), schedule=schedule, archive=True, max_attempts=1)
    run_dir = next((tmp_path / "automated").iterdir())
    with pytest.raises(ValueError, match="no accepted export for {'qb-coverage-matchup': 'no-validated-export'}"):
        _run(run_dir, target_week=3, write=True)
    audit = _run(run_dir, target_week=3, write=True, allow_partial=True)
    assert audit["missing_reports"] == {"qb-coverage-matchup": "no-validated-export"}
    assert sorted(audit["reports"]) == ["line-matchups", "wr-coverage-matchup"]
    assert all("qb_coverage" not in table for table, _, _ in warehouse.loads)


def test_loader_stages_archived_reports_when_a_later_archive_failed(tmp_path, monkeypatch, warehouse):
    schedule = schedule_frame()
    calls = {"n": 0}

    def flaky_archive(path, digest, season, week):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("archive unavailable")
        return weekly.expected_archive_uri(digest, path.name, week)

    monkeypatch.setattr(matchups, "_schedule", lambda season, week: schedule)
    monkeypatch.setattr(matchups, "_archive", flaky_archive)
    with pytest.raises(matchups.MatchupCaptureError):
        matchups.run(
            season=2026, week=3, output_root=tmp_path / "automated",
            profile_dir=tmp_path / "profile", headless=True, timeout_seconds=1.0,
            archive=True, now=DEFAULT_NOW, clock=lambda: DEFAULT_NOW,
            driver_factory=factory_for(FakeDriver(_good_script(schedule))),
        )
    run_dir = next((tmp_path / "automated").iterdir())
    dry = _run(run_dir, target_week=3)
    assert dry["status_counts"] == {"validated": 3, "staged": 0}
    with pytest.raises(ValueError, match="no hash-addressed archive recorded"):
        _run(run_dir, target_week=3, write=True)
    audit = _run(run_dir, target_week=3, write=True, allow_partial=True)
    assert audit["missing_reports"] == {"line-matchups": "no-archive"}
    assert sorted(audit["reports"]) == ["qb-coverage-matchup", "wr-coverage-matchup"]
    assert len(warehouse.loads) == 2


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
            report["archive_uri"] = weekly.expected_archive_uri(digest, path.name, 3)
    entry["sha256"] = digest
    entry["archive_uri"] = weekly.expected_archive_uri(digest, path.name, 3)
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="non-numeric"):
        _run(run_dir, target_week=3)

    schedule = schedule_frame()
    drifted = run_dir / "drift.csv"
    rows = export_rows_for("qb-coverage-matchup", directional_pairs(schedule))
    _write_grouped(drifted, "qb-coverage-matchup", rows)
    drifted.write_bytes(drifted.read_bytes().replace(b"COV GRADE", b"COV SCORE", 1))
    with pytest.raises(ValueError, match="header drift"):
        weekly._rederive_artifact(
            report="qb-coverage-matchup", local_path=drifted,
            claimed_sha256=hashlib.sha256(drifted.read_bytes()).hexdigest(),
            claimed_bytes=drifted.stat().st_size,
            retrieved_at=pd.Timestamp.now(tz="UTC") + pd.Timedelta(seconds=1),
            expected=matchups.expected_schedule_pairs(schedule),
            first_kickoff=pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=5), target_week=3,
            archive_uri=None,
        )


def test_rows_to_append_skips_same_key_and_rejects_corrupt_existing():
    rows = pd.DataFrame([
        {"season": 2026, "target_week": 3, "report": "line-matchups", "source_sha256": "aa",
         "source_row": 3, "team": "BUF", "offense__ybco": 1.0},
        {"season": 2026, "target_week": 3, "report": "line-matchups", "source_sha256": "aa",
         "source_row": 4, "team": "BAL", "offense__ybco": 2.0},
    ])
    existing = rows.iloc[:1][list(weekly.KEY_COLUMNS)]
    novel = weekly.rows_to_append(rows, existing)
    assert novel.team.tolist() == ["BAL"]
    assert weekly.rows_to_append(rows, pd.DataFrame()).equals(rows)
    with pytest.raises(RuntimeError, match="duplicate append keys"):
        weekly.rows_to_append(rows, pd.concat([existing, existing]))


# Seal mode (Week 1, schema-1 member runs) -------------------------------------


def _schema1_run(root: Path, run_id: str, schedule, *, keys: list[str], retrieved: str, kickoff: str) -> dict[str, str]:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    expected = matchups.expected_schedule_pairs(schedule)
    reports, digests = [], {}
    for key in keys:
        artifact = run_dir / f"{key}.csv"
        _write_grouped(artifact, key, export_rows_for(key, directional_pairs(schedule)))
        stamp = pd.Timestamp(retrieved).timestamp()
        os.utime(artifact, (stamp, stamp))
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        digests[key] = digest
        reports.append({
            "key": key, "status": "captured", "path": artifact.name, "sha256": digest,
            "bytes": artifact.stat().st_size, "retrieved_at_utc": retrieved,
            "source_url": f"https://data.fantasypoints.com/nfl/tools/x/{key}",
        })
    manifest = {
        "schema_version": 1, "capture_id": matchups.CAPTURE_ID, "run_id": run_id,
        "target_season": 2026, "target_week": 1, "first_kickoff_utc": kickoff,
        "expected_schedule_pairs": [list(p) for p in sorted(expected)],
        "reports": reports,
        "status": "failed", "error": "RuntimeError: matchup schedule gate failed for: other",
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    return digests


def _seal(tmp_path, root, schedule, kickoff, *, layout: dict[str, list[str]], retrieved="2026-09-09T19:31:30+00:00"):
    members = []
    for run_id, keys in layout.items():
        digests = _schema1_run(root, run_id, schedule, keys=keys, retrieved=retrieved, kickoff=kickoff)
        for key in keys:
            members.append({
                "report": key, "source_run_id": run_id, "retrieved_at_utc": retrieved,
                "source_url": "https://data.fantasypoints.com/nfl/tools/x", "sha256": digests[key],
                "bytes": (root / run_id / f"{key}.csv").stat().st_size,
                "archive_uri": weekly.expected_archive_uri(digests[key], f"{key}.csv", 1),
                "archive_generation": "1788968427798186",
            })
    seal_path = tmp_path / "seal.json"
    seal_path.write_text(json.dumps({
        "schema_version": 1, "capture_id": matchups.CAPTURE_ID, "status": weekly.SEAL_STATUS,
        "target_season": 2026, "target_week": 1, "first_kickoff_utc": kickoff, "members": members,
    }))
    return seal_path, members


def _sealed_generation(uri: str) -> dict:
    return {"exists": True, "generation": "1788968427798186"}


def test_seal_mode_stages_members_that_share_one_run_dir(tmp_path, monkeypatch, warehouse):
    schedule = schedule_frame(gameday="2026-09-13")
    monkeypatch.setattr(weekly, "_schedule", lambda season, week: schedule)
    kickoff = "2026-09-13T17:00:00+00:00"
    root = tmp_path / "automated"
    # The real Week-1 shape: QB from one run, WR and OL/DL from another.
    seal_path, members = _seal(tmp_path, root, schedule, kickoff, layout={
        f"20260909T193712Z__{matchups.CAPTURE_ID}__week-01": ["qb-coverage-matchup"],
        f"20260909T193116Z__{matchups.CAPTURE_ID}__week-01": ["wr-coverage-matchup", "line-matchups"],
    })
    audit = weekly.run(seal_path, target_week=1, write=True, output_root=root, archive_check=_sealed_generation)
    assert audit["input_kind"] == "seal"
    assert audit["status_counts"] == {"validated": 0, "staged": 3}
    assert len(warehouse.loads) == 3
    wr = warehouse.tables[f"{bq.settings.raw}.fantasy_points_wr_coverage_matchup_weekly"]
    assert (wr.target_week == 1).all()
    shared = matchups.read_ledger(root / f"20260909T193116Z__{matchups.CAPTURE_ID}__week-01")
    for key in ("wr-coverage-matchup", "line-matchups"):
        entry = shared["reports"][key]
        assert entry["downloaded"]["attempts"][0]["rederived_by"] == "fantasy_points_matchups_weekly"
        assert entry["validated"]["sha256"] == next(m["sha256"] for m in members if m["report"] == key)
        assert entry["staged"]["rows"] == 4
    assert shared["reports"]["qb-coverage-matchup"]["downloaded"] is None
    assert all(
        (root / m["source_run_id"] / f"staging-receipt-{m['report']}.json").is_file() for m in members
    )

    # Re-run: nothing appended, ledgers unchanged, no error.
    again = weekly.run(seal_path, target_week=1, write=True, output_root=root, archive_check=_sealed_generation)
    assert len(warehouse.loads) == 3
    assert all(r["write_disposition"] == "already-identical" for r in again["reports"].values())

    # A sealed generation that differs from the object's is refused before any load.
    warehouse.loads.clear()
    with pytest.raises(ValueError, match="archive generation"):
        weekly.run(seal_path, target_week=1, write=True, output_root=root, archive_check=archive_check_ok)
    assert warehouse.loads == []

    bad = json.loads(seal_path.read_text())
    bad["members"][0]["sha256"] = "0" * 64
    (tmp_path / "bad.json").write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="no report record with the sealed hash"):
        weekly.run(tmp_path / "bad.json", target_week=1, output_root=root)
    with pytest.raises(ValueError, match="needs output_root"):
        weekly.run(seal_path, target_week=1)
    monkeypatch.setattr(weekly, "_schedule", lambda season, week: schedule_frame(gameday="2026-09-14"))
    with pytest.raises(ValueError, match="seal first kickoff .* differs from the schedule authority"):
        weekly.run(seal_path, target_week=1, output_root=root)


def test_seal_mode_rejects_a_member_captured_after_kickoff(tmp_path, monkeypatch, warehouse):
    schedule = schedule_frame(gameday="2026-09-13")
    monkeypatch.setattr(weekly, "_schedule", lambda season, week: schedule)
    kickoff = "2026-09-13T17:00:00+00:00"
    root = tmp_path / "automated"
    seal_path, members = _seal(tmp_path, root, schedule, kickoff, layout={
        f"20260913T180000Z__{matchups.CAPTURE_ID}__week-01": list(weekly.REPORTS),
    }, retrieved="2026-09-13T18:00:00+00:00")
    with pytest.raises(ValueError, match="retrieved at/after"):
        weekly.run(seal_path, target_week=1, output_root=root)
    assert warehouse.loads == []
