import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.ops import fantasy_points_matchups as matchups
from tests.fp_matchup_fixtures import (
    FakeDriver,
    capture,
    directional_pairs,
    export_rows_for,
    schedule_frame,
)


def _grouped_csv(path: Path, report: str) -> None:
    if report == "qb-coverage-matchup":
        path.write_text(
            '"Player Details","","","","","",""\n'
            '"Rank","Name","Team","POS","G","Season","OPP"\n'
            '"1","QB One","BUF","QB","17","2025","BLT"\n'
            '"2","QB Two","BLT","QB","17","2025","BUF"\n',
            encoding="utf-8",
        )
    else:
        path.write_text(
            '"Team Details","","","","","","Offense Stats","","","","","","","","Defense Stats"\n'
            '"Rank","Name","G","Season","Location","Team Name","RUSH GRADE","PASS GRADE","ADJ YBC/ATT","PRESS %","PrROE","Team","TM ATT","YBCO","Name"\n'
            '"1","Buffalo Bills","17","2025","Buffalo","Bills","1","1","1","1","1","BUF","1","1","Baltimore Ravens"\n'
            '"2","Baltimore Ravens","17","2025","Baltimore","Ravens","1","1","1","1","1","BLT","1","1","Buffalo Bills"\n',
            encoding="utf-8",
        )


def test_read_matchup_pairs_normalizes_team_codes(tmp_path):
    qb = tmp_path / "qb.csv"
    _grouped_csv(qb, "qb-coverage-matchup")
    pairs, seasons, rows = matchups.read_matchup_pairs(
        qb, "qb-coverage-matchup"
    )
    assert pairs == {("BUF", "BAL"), ("BAL", "BUF")}
    assert seasons == {2025}
    assert rows == 2

    line = tmp_path / "line.csv"
    _grouped_csv(line, "line-matchups")
    pairs, seasons, rows = matchups.read_matchup_pairs(line, "line-matchups")
    assert pairs == {("BUF", "BAL"), ("BAL", "BUF")}
    assert seasons == {2025}
    assert rows == 2


def test_team_aliases_cover_vendor_spellings_seen_in_matchup_exports():
    assert matchups._team("ARZ") == "ARI"
    assert matchups._team("CLV") == "CLE"
    assert matchups._team("JAC") == "JAX"
    assert matchups._team("WSH") == "WAS"
    assert matchups._team("LAR") == "LA"
    assert matchups._team(" kc ") == "KC"
    assert matchups._team(None) == ""


def test_schedule_gate_rejects_stale_or_missing_pairs():
    schedule = pd.DataFrame([{"home_team": "BUF", "away_team": "BLT"}])
    expected = matchups.expected_schedule_pairs(schedule)
    good = matchups.validate_matchup_pairs(
        {("BUF", "BAL"), ("BAL", "BUF")}, expected,
        report="line-matchups",
    )
    assert good["passes"]
    stale = matchups.validate_matchup_pairs(
        {("BUF", "KC"), ("BAL", "BUF")}, expected,
        report="line-matchups",
    )
    assert not stale["passes"]
    assert stale["unexpected_pairs"] == [["BUF", "KC"]]
    assert stale["missing_pairs"] == [["BUF", "BAL"]]


def test_schedule_gate_reconciles_one_prior_season_multi_team_identity():
    schedule = pd.DataFrame([{"home_team": "CIN", "away_team": "TB"}])
    expected = matchups.expected_schedule_pairs(schedule)
    gate = matchups.validate_matchup_pairs(
        {
            ("CIN", "TB"),
            ("TB", "CIN"),
            ("CLV, CIN", "TB"),
        },
        expected,
        report="qb-coverage-matchup",
    )
    assert gate == {
        "report": "qb-coverage-matchup",
        "passes": True,
        "observed_pairs": 3,
        "normalized_observed_pairs": 2,
        "expected_pairs": 2,
        "reconciled_multi_team_pairs": [
            {
                "observed": ["CLV, CIN", "TB"],
                "normalized": ["CIN", "TB"],
            }
        ],
        "unexpected_pairs": [],
        "missing_pairs": [],
    }


def test_schedule_gate_rejects_unmatched_multi_team_identity():
    schedule = pd.DataFrame([{"home_team": "CIN", "away_team": "TB"}])
    expected = matchups.expected_schedule_pairs(schedule)
    gate = matchups.validate_matchup_pairs(
        {("CLV, BAL", "TB"), ("TB", "CIN")},
        expected,
        report="qb-coverage-matchup",
    )
    assert not gate["passes"]
    assert gate["reconciled_multi_team_pairs"] == []
    assert gate["unexpected_pairs"] == [["CLV, BAL", "TB"]]
    assert gate["missing_pairs"] == [["CIN", "TB"]]


def test_reconcile_team_resolves_only_one_scheduled_component():
    expected = {("CIN", "TB"), ("TB", "CIN")}
    assert matchups.reconcile_team("CIN", "TB", expected) == "CIN"
    assert matchups.reconcile_team("CLV, CIN", "TB", expected) == "CIN"
    assert matchups.reconcile_team("CLV, BAL", "TB", expected) is None
    assert matchups.reconcile_team("CIN, CIN", "TB", expected) is None
    assert matchups.reconcile_team("KC", "TB", expected) is None


def test_first_kickoff_is_eastern_and_all_games_not_sunday_only():
    schedule = pd.DataFrame([
        {"gameday": "2026-09-10", "gametime": "20:20"},
        {"gameday": "2026-09-13", "gametime": "13:00"},
    ])
    assert matchups.first_kickoff_utc(schedule) == pd.Timestamp(
        "2026-09-11T00:20:00Z"
    )


def test_source_regime_preserves_vendor_early_season_warning():
    assert matchups.source_regime({2025}, 2026, 1) == (
        "vendor-prior-season-early"
    )
    assert matchups.source_regime({2026}, 2026, 2) == (
        "vendor-active-season-early"
    )
    assert matchups.source_regime({2025}, 2026, 3) == (
        "vendor-prior-season-early"
    )
    assert matchups.source_regime({2026}, 2026, 3) == (
        "vendor-active-season-early"
    )
    assert matchups.source_regime({2026}, 2026, 4) == (
        "vendor-active-season-mature"
    )
    with pytest.raises(ValueError, match="expected active season"):
        matchups.source_regime({2025}, 2026, 4)
    with pytest.raises(ValueError, match="mixes source seasons"):
        matchups.source_regime({2025, 2026}, 2026, 2)


def test_capture_contract_is_frozen_to_2026(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="frozen to 2026"):
        matchups.run(
            season=2025, week=1, output_root=tmp_path,
            profile_dir=tmp_path / "profile", headless=True,
            timeout_seconds=1, archive=False,
            now=datetime(2025, 8, 1, tzinfo=UTC),
        )


# Status ledger ---------------------------------------------------------------


def test_ledger_refuses_to_skip_a_status_and_binds_to_one_artifact(tmp_path):
    matchups.new_ledger(tmp_path, "run-1", ["qb-coverage-matchup"])
    with pytest.raises(RuntimeError, match="cannot record 'validated' before 'downloaded'"):
        matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "validated", sha256="a")
    matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "downloaded", sha256="a", path="x")
    matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "validated", sha256="a", path="x")
    with pytest.raises(RuntimeError, match="already recorded for a different artifact"):
        matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "validated", sha256="b")
    with pytest.raises(RuntimeError, match="cannot record 'consumed' before 'staged'"):
        matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "consumed", sha256="a")
    with pytest.raises(KeyError):
        matchups.advance_ledger(tmp_path, "wr-coverage-matchup", "downloaded", sha256="a")
    with pytest.raises(ValueError, match="unknown ledger status"):
        matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "archived", sha256="a")
    ledger = matchups.read_ledger(tmp_path)
    assert ledger["reports"]["qb-coverage-matchup"]["validated"]["sha256"] == "a"
    assert ledger["reports"]["qb-coverage-matchup"]["staged"] is None


# Mocked end-to-end capture ---------------------------------------------------


def _good_script(schedule: pd.DataFrame) -> dict[str, list[list[list[str]]]]:
    pairs = directional_pairs(schedule)
    return {key: [export_rows_for(key, pairs)] for key in matchups.MATCHUPS_KEYS} if hasattr(
        matchups, "MATCHUPS_KEYS"
    ) else {definition.key: [export_rows_for(definition.key, pairs)] for definition in matchups.MATCHUPS}


def test_capture_validates_every_report_and_records_control_state(monkeypatch, tmp_path):
    schedule = schedule_frame()
    driver = FakeDriver(_good_script(schedule))
    manifest_path = capture(tmp_path, monkeypatch, driver, schedule=schedule, archive=True)
    manifest = json.loads(manifest_path.read_text())
    assert manifest["schema_version"] == 2
    assert manifest["status"] == "complete"
    assert manifest["status_counts"] == {
        "downloaded": 0, "rejected": 0, "validated": 0, "archived": 3,
    }
    assert sorted(manifest["validated_reports"]) == [
        "line-matchups", "qb-coverage-matchup", "wr-coverage-matchup",
    ]
    for report in manifest["reports"]:
        assert report["attempt"] == 1
        assert report["status"] == "archived"
        control = report["vendor_schedule_week_control"]
        assert control["on_load"]["selected"] == "2"
        assert control["after_select"]["selected"] == "3"
        assert control["after_apply"]["selected"] == "3"
        assert report["values_request"]["table_property"] == report["property"]
        assert report["schedule_gate"]["passes"]
        assert report["source_regime"] == "vendor-prior-season-early"
        assert report["archive_uri"].endswith(report["path"])
        assert (manifest_path.parent / report["path"]).is_file()
    ledger = matchups.read_ledger(manifest_path.parent)
    for key, entry in ledger["reports"].items():
        assert [a["sha256"] for a in entry["downloaded"]["attempts"]] == [
            manifest["validated_reports"][key]["sha256"]
        ]
        assert entry["validated"]["archive_uri"] == manifest["validated_reports"][key]["archive_uri"]
        assert entry["staged"] is None and entry["consumed"] is None


def test_capture_retries_a_stale_vendor_schedule_and_keeps_the_rejected_export(monkeypatch, tmp_path):
    schedule = schedule_frame()
    pairs = directional_pairs(schedule)
    # Week-1 2026 shape: the vendor answers once with Arizona-at-Carolina-style
    # wrong opponents, then with the real schedule.
    stale = [(team, "KC" if team == "BUF" else opponent) for team, opponent in pairs]
    stale = [(team, "BUF" if team == "KC" else opponent) for team, opponent in stale]
    script = _good_script(schedule)
    script["wr-coverage-matchup"] = [
        export_rows_for("wr-coverage-matchup", stale),
        export_rows_for("wr-coverage-matchup", pairs),
    ]
    driver = FakeDriver(script)
    manifest_path = capture(tmp_path, monkeypatch, driver, schedule=schedule)
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "complete"
    wr = [r for r in manifest["reports"] if r["key"] == "wr-coverage-matchup"]
    assert [r["status"] for r in wr] == ["rejected", "validated"]
    assert wr[0]["rejection"]["failure_class"] == "schedule-gate"
    assert wr[0]["schedule_gate"]["unexpected_pairs"] == [["BUF", "KC"], ["KC", "BUF"]]
    assert wr[0]["path"] == "wr-coverage-matchup.attempt-01.csv"
    assert wr[1]["path"] == "wr-coverage-matchup.attempt-02.csv"
    assert (manifest_path.parent / wr[0]["path"]).is_file(), "rejected export must be preserved"
    assert manifest["validated_reports"]["wr-coverage-matchup"]["attempt"] == 2
    assert manifest["status_counts"] == {
        "downloaded": 0, "rejected": 1, "validated": 3, "archived": 0,
    }
    assert driver.events.count("navigate:wr-coverage-matchup") == 2
    ledger = matchups.read_ledger(manifest_path.parent)
    attempts = ledger["reports"]["wr-coverage-matchup"]["downloaded"]["attempts"]
    assert [a["attempt"] for a in attempts] == [1, 2]
    assert attempts[0]["sha256"] == wr[0]["sha256"]
    assert ledger["reports"]["wr-coverage-matchup"]["validated"]["attempt"] == 2


def test_capture_fails_closed_after_max_attempts_and_keeps_every_export(monkeypatch, tmp_path):
    schedule = schedule_frame()
    pairs = directional_pairs(schedule)
    stale = [(team, "KC" if team == "BUF" else opponent) for team, opponent in pairs]
    script = _good_script(schedule)
    script["qb-coverage-matchup"] = [export_rows_for("qb-coverage-matchup", stale)] * 2
    driver = FakeDriver(script)
    with pytest.raises(matchups.MatchupCaptureError, match="after 2 attempts for: qb-coverage-matchup") as info:
        capture(tmp_path, monkeypatch, driver, schedule=schedule, max_attempts=2)
    assert info.value.failure_class == "schedule-gate"
    run_dir = next((tmp_path / "automated").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["failure_class"] == "schedule-gate"
    assert manifest["schedule_gate_failures"] == ["qb-coverage-matchup"]
    assert manifest["status_counts"] == {
        "downloaded": 0, "rejected": 2, "validated": 2, "archived": 0,
    }
    assert sorted(p.name for p in run_dir.glob("*.csv")) == [
        "line-matchups.attempt-01.csv",
        "qb-coverage-matchup.attempt-01.csv",
        "qb-coverage-matchup.attempt-02.csv",
        "wr-coverage-matchup.attempt-01.csv",
    ]
    # Later reports were still captured and validated after the QB gate failed.
    assert sorted(manifest["validated_reports"]) == ["line-matchups", "wr-coverage-matchup"]


def test_capture_distinguishes_vendor_week_not_open_from_missing_option(monkeypatch, tmp_path):
    schedule = schedule_frame()
    # Week 3 2026-09-21: option present, control reverts to 2 after Apply.
    driver = FakeDriver(_good_script(schedule), retained=False)
    with pytest.raises(matchups.MatchupCaptureError, match="shows '2' after Apply, not 3") as info:
        capture(tmp_path, monkeypatch, driver, schedule=schedule)
    assert info.value.failure_class == "vendor-week-not-retained"
    run_dir = next((tmp_path / "automated").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["failure_class"] == "vendor-week-not-retained"
    control = manifest["failure_detail"]["schedule_week_control"]
    assert control["on_load"]["selected"] == "2"
    assert control["after_select"]["selected"] == "3"
    assert control["after_apply"]["selected"] == "2"
    assert manifest["reports"] == []
    assert list(run_dir.glob("*.csv")) == []

    # The option itself is absent: a different class with the options listed.
    driver = FakeDriver(_good_script(schedule), options=("1", "2"))
    with pytest.raises(matchups.MatchupCaptureError, match="has no option 3") as info:
        capture(
            tmp_path, monkeypatch, driver, schedule=schedule,
            now=datetime(2026, 9, 22, 15, 1, tzinfo=UTC),
        )
    assert info.value.failure_class == "vendor-week-unavailable"
    assert info.value.detail["options_visible"] == ["1", "2"]
    manifests = sorted((tmp_path / "automated").glob("*/manifest.json"))
    latest = json.loads(manifests[-1].read_text())
    assert latest["failure_class"] == "vendor-week-unavailable"
    assert latest["failure_detail"]["options_visible"] == ["1", "2"]


def test_capture_rejects_non_default_history_scope_and_no_rows(monkeypatch, tmp_path):
    schedule = schedule_frame()
    driver = FakeDriver(_good_script(schedule), history_scope=("Last 4",))
    with pytest.raises(matchups.MatchupCaptureError) as info:
        capture(tmp_path, monkeypatch, driver, schedule=schedule)
    assert info.value.failure_class == "history-scope-not-default"

    driver = FakeDriver(_good_script(schedule), rows_rendered=1)
    with pytest.raises(matchups.MatchupCaptureError) as info:
        capture(
            tmp_path, monkeypatch, driver, schedule=schedule,
            now=datetime(2026, 9, 22, 15, 1, tzinfo=UTC),
        )
    assert info.value.failure_class == "no-rows"


def test_capture_refuses_to_start_after_first_kickoff(monkeypatch, tmp_path):
    schedule = schedule_frame(gameday="2026-09-20")
    driver = FakeDriver(_good_script(schedule))
    with pytest.raises(matchups.MatchupCaptureError, match="after first kickoff") as info:
        capture(
            tmp_path, monkeypatch, driver, schedule=schedule,
            now=datetime(2026, 9, 22, 15, 0, tzinfo=UTC),
        )
    assert info.value.failure_class == "after-kickoff"
    assert not (tmp_path / "automated").exists()
