from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.ops import fantasy_points_matchups as matchups


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
