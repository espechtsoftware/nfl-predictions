import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.ops import fantasy_points_matchups as matchups
from tests.fp_matchup_fixtures import (
    DEFAULT_NOW,
    FakeDriver,
    capture,
    directional_pairs,
    export_rows_for,
    factory_for,
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
    matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "downloaded", sha256="a", path="x", attempt=1)
    matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "downloaded", sha256="a", path="y", attempt=2)
    with pytest.raises(RuntimeError, match="already recorded with another hash"):
        matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "downloaded", sha256="z", path="x", attempt=1)
    matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "validated", sha256="a", path="x")
    with pytest.raises(RuntimeError, match="already recorded for a different artifact"):
        matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "validated", sha256="b")
    with pytest.raises(RuntimeError, match="cannot record 'consumed' before 'staged'"):
        matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "consumed", sha256="a")
    with pytest.raises(RuntimeError, match="'staged' names hash 'b' but the validated artifact is 'a'"):
        matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "staged", sha256="b")
    matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "staged", sha256="a", rows=1)
    with pytest.raises(KeyError):
        matchups.advance_ledger(tmp_path, "wr-coverage-matchup", "downloaded", sha256="a")
    with pytest.raises(ValueError, match="unknown ledger status"):
        matchups.advance_ledger(tmp_path, "qb-coverage-matchup", "archived", sha256="a")
    ledger = matchups.read_ledger(tmp_path)
    entry = ledger["reports"]["qb-coverage-matchup"]
    assert [a["attempt"] for a in entry["downloaded"]["attempts"]] == [1, 2]
    assert entry["validated"]["sha256"] == "a"
    assert entry["staged"]["rows"] == 1
    assert entry["consumed"] is None


# Browser driver classification (production code, stubbed page) ---------------


class _Locator:
    def __init__(self, text="", visible=True, children=None):
        self._text = text
        self._visible = visible
        self._children = children or {}

    def count(self):
        return 1

    def nth(self, index):
        return self

    def is_visible(self):
        return self._visible

    def inner_text(self):
        return self._text

    def locator(self, selector):
        return self._children.get(selector, _Locator(visible=False))


CONTROL_SELECTOR = (
    "select, [role='combobox'], input, "
    "button.fpts-listbox-button, button.fpts-popover-button"
)


class _Page:
    """Enough of a page for _filter_container/_visible to find the controls."""

    def __init__(self, *, week_text="3", history_text="All", options=("1", "2", "3")):
        listbox = _Locator(week_text)
        popover = _Locator(history_text)
        self._labels = {
            "Schedule Week": _Locator("Schedule Week", children={
                "xpath=..": _Locator(children={
                    CONTROL_SELECTOR: listbox,
                    "button.fpts-listbox-button": listbox,
                }),
            }),
            "Week(s)": _Locator("Week(s)", children={
                "xpath=..": _Locator(children={
                    CONTROL_SELECTOR: popover,
                    "button.fpts-popover-button": popover,
                }),
            }),
        }
        self._options = options
        self.url = "https://data.fantasypoints.com/nfl/tools/player/qb-coverage-matchup"

    def set_default_timeout(self, value):
        pass

    def get_by_text(self, text, exact=False):
        return self._labels.get(text, _Locator(visible=False))

    def get_by_role(self, role, **kwargs):
        assert role == "option"
        options = self._options

        class _Options:
            def count(self_inner):
                return len(options)

            def nth(self_inner, index):
                return _Locator(options[index])

        return _Options()


def test_driver_maps_missing_option_to_vendor_week_unavailable_with_options(monkeypatch):
    driver = matchups.PlaywrightMatchupDriver(_Page(options=("1", "2")), timeout_seconds=1.0)

    def no_option(page, label, value):
        raise RuntimeError(f"filter {label!r} has no option {value!r}")

    monkeypatch.setattr(matchups, "_select_single_filter", no_option)
    with pytest.raises(matchups.MatchupCaptureError) as info:
        driver.select_week(3)
    assert info.value.failure_class == "vendor-week-unavailable"
    assert info.value.detail["options_visible"] == ["1", "2"]

    def no_label(page, label, value):
        raise RuntimeError(f"filter label is missing: {label}")

    monkeypatch.setattr(matchups, "_select_single_filter", no_label)
    with pytest.raises(matchups.MatchupCaptureError) as info:
        driver.select_week(3)
    assert info.value.failure_class == "control-missing"

    def other(page, label, value):
        raise RuntimeError("filter 'Schedule Week' did not retain '3'")

    monkeypatch.setattr(matchups, "_select_single_filter", other)
    with pytest.raises(matchups.MatchupCaptureError) as info:
        driver.select_week(3)
    assert info.value.failure_class == "browser"


def test_driver_reads_the_schedule_week_and_history_controls():
    driver = matchups.PlaywrightMatchupDriver(
        _Page(week_text="2\nWeek", history_text="All\nWeek(s)"), timeout_seconds=1.0,
    )
    assert driver.week_control() == {
        "present": True, "selected": "2", "history_scope": ["All", "Week(s)"],
    }
    missing = matchups.PlaywrightMatchupDriver(_Page(), timeout_seconds=1.0)
    missing.page._labels.pop("Schedule Week")
    state = missing.week_control()
    assert state["present"] is False and "filter label is missing" in state["error"]
    with pytest.raises(matchups.MatchupCaptureError) as info:
        matchups._verify_week_control(state, 3, control={})
    assert info.value.failure_class == "control-missing"


# Mocked end-to-end capture ---------------------------------------------------


def _good_script(schedule: pd.DataFrame) -> dict[str, list[list[list[str]]]]:
    pairs = directional_pairs(schedule)
    return {d.key: [export_rows_for(d.key, pairs)] for d in matchups.MATCHUPS}


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
    assert manifest["rejected_reports"] == {}
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
        assert report["vendor_path"].startswith("/nfl/tools/")
        assert report["schedule_gate"]["passes"]
        assert report["source_regime"] == "vendor-prior-season-early"
        assert report["retrieved_at_utc"] == DEFAULT_NOW.isoformat()
        assert report["archive_uri"] == (
            f"gs://{matchups.settings.gcs_bucket}/licensed/fantasy-points/live-matchups/"
            f"season=2026/week=03/sha256={report['sha256']}/{report['path']}"
        )
        assert (manifest_path.parent / report["path"]).is_file()
    assert manifest["finished_at_utc"] == DEFAULT_NOW.isoformat()
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
    # Week-1 2026 shape: the vendor answers once with wrong opponents, then
    # with the real schedule.
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
    assert manifest["rejected_reports"]["wr-coverage-matchup"]["attempts"] == 1
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
    with pytest.raises(
        matchups.MatchupCaptureError, match=r"failed for: qb-coverage-matchup \(2 attempts\)"
    ) as info:
        capture(tmp_path, monkeypatch, driver, schedule=schedule, max_attempts=2)
    assert info.value.failure_class == "schedule-gate"
    run_dir = next((tmp_path / "automated").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["failure_class"] == "schedule-gate"
    assert manifest["schedule_gate_failures"] == ["qb-coverage-matchup"]
    assert manifest["rejected_reports"]["qb-coverage-matchup"]["attempts"] == 2
    assert manifest["status_counts"] == {
        "downloaded": 0, "rejected": 2, "validated": 2, "archived": 0,
    }
    assert sorted(p.name for p in run_dir.glob("*.csv")) == [
        "line-matchups.attempt-01.csv",
        "qb-coverage-matchup.attempt-01.csv",
        "qb-coverage-matchup.attempt-02.csv",
        "wr-coverage-matchup.attempt-01.csv",
    ]
    # Byte-identical stale exports are still two attempts in the ledger.
    attempts = matchups.read_ledger(run_dir)["reports"]["qb-coverage-matchup"]["downloaded"]["attempts"]
    assert [a["attempt"] for a in attempts] == [1, 2]
    assert attempts[0]["sha256"] == attempts[1]["sha256"]
    # Later reports were still captured and validated after the QB gate failed.
    assert sorted(manifest["validated_reports"]) == ["line-matchups", "wr-coverage-matchup"]


def test_capture_stops_without_retry_on_parse_or_regime_rejections(monkeypatch, tmp_path):
    schedule = schedule_frame()
    pairs = directional_pairs(schedule)
    # Vendor header drift: the OPP column renamed on the WR export only.
    driver = FakeDriver(_good_script(schedule))
    original_export = driver.export

    def export_with_drift(destination):
        name = original_export(destination)
        if destination.name.startswith("wr-coverage-matchup"):
            destination.write_bytes(destination.read_bytes().replace(b'"OPP"', b'"Opponent"', 1))
        return name

    driver.export = export_with_drift
    with pytest.raises(matchups.MatchupCaptureError, match="missing") as info:
        capture(tmp_path, monkeypatch, driver, schedule=schedule)
    assert info.value.failure_class == "export-contract"
    run_dir = next((tmp_path / "automated").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["failure_class"] == "export-contract"
    assert manifest["schedule_gate_failures"] == []
    assert manifest["rejected_reports"]["wr-coverage-matchup"] == {
        "failure_class": "export-contract", "attempts": 1,
        "detail": manifest["reports"][1]["rejection"]["detail"],
    }
    assert driver.events.count("navigate:wr-coverage-matchup") == 1, "no re-download on drift"
    assert (run_dir / "wr-coverage-matchup.attempt-01.csv").is_file()

    # Source regime: a 2024 aggregate for a 2026 target week.
    script = _good_script(schedule)
    script["qb-coverage-matchup"] = [export_rows_for("qb-coverage-matchup", pairs, season=2024)]
    driver = FakeDriver(script)
    with pytest.raises(matchups.MatchupCaptureError, match="outside") as info:
        capture(
            tmp_path / "regime", monkeypatch, driver, schedule=schedule,
            now=datetime(2026, 9, 22, 15, 1, tzinfo=UTC),
        )
    assert info.value.failure_class == "source-regime"
    manifest = json.loads(
        next((tmp_path / "regime" / "automated").iterdir()).joinpath("manifest.json").read_text()
    )
    assert manifest["failure_class"] == "source-regime"
    assert manifest["rejected_reports"]["qb-coverage-matchup"]["attempts"] == 1
    assert manifest["reports"][0]["rejection"]["failure_class"] == "source-regime"
    assert driver.events.count("navigate:qb-coverage-matchup") == 1


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

    # The option itself is absent: the driver's class and payload propagate
    # to the manifest (the classification itself is unit-tested above).
    driver = FakeDriver(_good_script(schedule), options=("1", "2"))
    with pytest.raises(matchups.MatchupCaptureError, match="has no option 3") as info:
        capture(
            tmp_path, monkeypatch, driver, schedule=schedule,
            now=datetime(2026, 9, 22, 15, 1, tzinfo=UTC),
        )
    assert info.value.failure_class == "vendor-week-unavailable"
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


def test_capture_refuses_to_start_after_first_kickoff_and_uses_one_clock(monkeypatch, tmp_path):
    schedule = schedule_frame(gameday="2026-09-20")
    driver = FakeDriver(_good_script(schedule))
    with pytest.raises(matchups.MatchupCaptureError, match="after first kickoff") as info:
        capture(
            tmp_path, monkeypatch, driver, schedule=schedule,
            now=datetime(2026, 9, 22, 15, 0, tzinfo=UTC),
        )
    assert info.value.failure_class == "after-kickoff"
    assert not (tmp_path / "automated").exists()

    # A clock that crosses kickoff during the run trips the per-report gate
    # (kickoff 17:00Z): QB is retrieved and accepted before it, WR is
    # retrieved after it and never accepted.
    ticks = [
        datetime(2026, 9, 20, 16, 0, tzinfo=UTC),   # qb retrieved
        datetime(2026, 9, 20, 16, 1, tzinfo=UTC),   # qb post-report gate
        datetime(2026, 9, 20, 17, 30, tzinfo=UTC),  # wr retrieved
        datetime(2026, 9, 20, 17, 31, tzinfo=UTC),  # wr post-report gate: after kickoff
    ]

    def stepping_clock():
        return ticks.pop(0) if len(ticks) > 1 else ticks[0]

    driver = FakeDriver(_good_script(schedule))
    monkeypatch.setattr(matchups, "_schedule", lambda season, week: schedule)
    with pytest.raises(matchups.MatchupCaptureError, match="WR Coverage Matchup capture completed after first kickoff") as info:
        matchups.run(
            season=2026, week=3, output_root=tmp_path / "late",
            profile_dir=tmp_path / "profile", headless=True, timeout_seconds=1.0,
            archive=False, now=datetime(2026, 9, 20, 15, 59, tzinfo=UTC),
            clock=stepping_clock, driver_factory=factory_for(driver),
        )
    assert info.value.failure_class == "after-kickoff"
    manifest = json.loads(
        next((tmp_path / "late").iterdir()).joinpath("manifest.json").read_text()
    )
    assert [r["retrieved_at_utc"] for r in manifest["reports"]] == [
        "2026-09-20T16:00:00+00:00", "2026-09-20T17:30:00+00:00",
    ]
    assert [r["status"] for r in manifest["reports"]] == ["validated", "validated"]
    assert list(manifest["validated_reports"]) == ["qb-coverage-matchup"]
    assert manifest["finished_at_utc"] == "2026-09-20T17:31:00+00:00"


def test_capture_keeps_bytes_saved_before_a_mid_attempt_failure(monkeypatch, tmp_path):
    schedule = schedule_frame()
    driver = FakeDriver(_good_script(schedule))
    calls = {"n": 0}
    original = matchups._csv_shape

    def broken_shape(path):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk hiccup while reading the export")
        return original(path)

    monkeypatch.setattr(matchups, "_csv_shape", broken_shape)
    with pytest.raises(OSError, match="disk hiccup"):
        capture(tmp_path, monkeypatch, driver, schedule=schedule)
    run_dir = next((tmp_path / "automated").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["status"] == "failed" and manifest["failure_class"] == "browser"
    statuses = [(r["key"], r["status"]) for r in manifest["reports"]]
    assert statuses == [("qb-coverage-matchup", "validated"), ("wr-coverage-matchup", "downloaded")]
    partial = manifest["reports"][1]
    assert (run_dir / partial["path"]).is_file()
    assert partial["sha256"] and partial["bytes"] > 0
    assert manifest["status_counts"]["downloaded"] == 1
    ledger = matchups.read_ledger(run_dir)
    assert ledger["reports"]["wr-coverage-matchup"]["downloaded"]["attempts"][0]["sha256"] == partial["sha256"]
    assert ledger["reports"]["wr-coverage-matchup"]["validated"] is None


def test_capture_archive_failure_is_typed_and_keeps_the_validated_record(monkeypatch, tmp_path):
    schedule = schedule_frame()
    driver = FakeDriver(_good_script(schedule))
    calls = {"n": 0}

    def flaky_archive(path, digest, season, week):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("hash-addressed matchup archive is non-identical")
        return (
            f"gs://{matchups.settings.gcs_bucket}/licensed/fantasy-points/live-matchups/"
            f"season=2026/week=03/sha256={digest}/{path.name}"
        )

    monkeypatch.setattr(matchups, "_schedule", lambda season, week: schedule)
    monkeypatch.setattr(matchups, "_archive", flaky_archive)
    with pytest.raises(matchups.MatchupCaptureError, match="archive failed") as info:
        matchups.run(
            season=2026, week=3, output_root=tmp_path / "automated",
            profile_dir=tmp_path / "profile", headless=True, timeout_seconds=1.0,
            archive=True, now=DEFAULT_NOW, clock=lambda: DEFAULT_NOW,
            driver_factory=factory_for(driver),
        )
    assert info.value.failure_class == "archive"
    run_dir = next((tmp_path / "automated").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["failure_class"] == "archive"
    assert manifest["validated_reports"]["line-matchups"]["archive_uri"] is None
    assert "non-identical" in manifest["validated_reports"]["line-matchups"]["archive_error"]
    assert manifest["validated_reports"]["qb-coverage-matchup"]["archive_uri"].startswith("gs://")
    assert manifest["status_counts"] == {"downloaded": 0, "rejected": 0, "validated": 1, "archived": 2}
