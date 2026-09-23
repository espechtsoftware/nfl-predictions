import json
from datetime import UTC, datetime

import pytest

from nfl_dfs.ops import fantasy_points_matchup_status as status
from nfl_dfs.ops import fantasy_points_matchups as matchups
from tests.fp_matchup_fixtures import (
    FakeDriver,
    capture,
    directional_pairs,
    export_rows_for,
    schedule_frame,
)


def _script(schedule, **kwargs):
    pairs = directional_pairs(schedule)
    return {d.key: [export_rows_for(d.key, pairs, **kwargs)] for d in matchups.MATCHUPS}


def test_status_separates_downloaded_validated_staged_and_failed_runs(tmp_path, monkeypatch):
    schedule = schedule_frame()
    root = tmp_path / "automated"
    # A complete schema-2 run, then advance one report to staged by hand.
    complete = capture(tmp_path, monkeypatch, FakeDriver(_script(schedule)), schedule=schedule, archive=True).parent
    sha = json.loads((complete / "manifest.json").read_text())["validated_reports"]["line-matchups"]["sha256"]
    matchups.advance_ledger(complete, "line-matchups", "staged", sha256=sha, rows=4, table="t")
    # A failed schema-2 run: QB gate exhausted after one attempt, other reports validated.
    pairs = directional_pairs(schedule)
    stale = [(team, "KC" if team == "BUF" else opponent) for team, opponent in pairs]
    script = _script(schedule)
    script["qb-coverage-matchup"] = [export_rows_for("qb-coverage-matchup", stale)]
    with pytest.raises(matchups.MatchupCaptureError):
        capture(
            tmp_path, monkeypatch, FakeDriver(script), schedule=schedule, max_attempts=1,
            now=datetime(2026, 9, 22, 15, 1, tzinfo=UTC),
        )
    # A schema-1 failed run in the old layout with one gate-passing report.
    legacy = root / f"20260909T190000Z__{matchups.CAPTURE_ID}__week-01"
    legacy.mkdir()
    (legacy / "qb-coverage-matchup.csv").write_text("x")
    (legacy / "manifest.json").write_text(json.dumps({
        "schema_version": 1, "capture_id": matchups.CAPTURE_ID, "run_id": legacy.name,
        "target_week": 1, "status": "failed", "error": "RuntimeError: gate",
        "reports": [
            {"key": "qb-coverage-matchup", "status": "captured", "path": "qb-coverage-matchup.csv",
             "schedule_gate": {"passes": True}},
            {"key": "wr-coverage-matchup", "status": "captured", "path": "missing.csv",
             "schedule_gate": {"passes": False}},
        ],
    }))
    # Not a matchup capture: ignored by the scan.
    other = root / "20260921T025357Z__2026-route-share-weekly-v1"
    other.mkdir()
    (other / "manifest.json").write_text(json.dumps({"capture_id": "other"}))

    runs = status.scan(root)
    assert [r["target_week"] for r in runs] == [1, 3, 3]
    legacy_status, ok, failed = runs
    assert legacy_status["schema_version"] == 1 and legacy_status["run_status"] == "failed"
    assert legacy_status["reports"]["qb-coverage-matchup"]["reached"] == "gate_passed"
    assert legacy_status["reports"]["qb-coverage-matchup"]["validated"] is False
    assert legacy_status["reports"]["wr-coverage-matchup"]["reached"] == "none"
    assert legacy_status["reports"]["wr-coverage-matchup"]["downloaded"] is False

    assert ok["run_status"] == "complete" and ok["ledger"] is True
    assert ok["reports"]["line-matchups"]["reached"] == "staged"
    assert ok["reports"]["qb-coverage-matchup"]["reached"] == "validated"

    assert failed["run_status"] == "failed" and failed["failure_class"] == "schedule-gate"
    assert failed["reports"]["qb-coverage-matchup"]["reached"] == "downloaded"
    assert failed["reports"]["qb-coverage-matchup"]["rejections"] == ["schedule-gate"]
    assert failed["reports"]["wr-coverage-matchup"]["reached"] == "validated"

    summary = status.summarize(runs)
    assert summary["weeks"]["3"] == {
        "runs": 2, "complete_runs": 1, "failed_runs": 1,
        "reports": {
            "qb-coverage-matchup": {"downloaded": 2, "gate_passed": 1, "validated": 1, "staged": 0, "consumed": 0},
            "wr-coverage-matchup": {"downloaded": 2, "gate_passed": 2, "validated": 2, "staged": 0, "consumed": 0},
            "line-matchups": {"downloaded": 2, "gate_passed": 2, "validated": 2, "staged": 1, "consumed": 0},
        },
    }
    assert summary["weeks"]["1"]["reports"]["qb-coverage-matchup"] == {
        "downloaded": 1, "gate_passed": 1, "validated": 0, "staged": 0, "consumed": 0,
    }
    assert status.scan(root, week=1)[0]["run_id"] == legacy.name
    assert status.main(["--output-root", str(root), "--json"]) == 0
