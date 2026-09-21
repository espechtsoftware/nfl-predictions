"""Offline contract for the manual 2026 full-field DK capture workflow."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from nfl_dfs.ingest import ownership_import as oi


LINEUP = (
    "QB Quarter Back RB Runner One RB Runner Two WR Wide One WR Wide Two "
    "WR Wide Three TE Tight End FLEX Flex Player DST Defense"
)


def _write_full_field(path: Path, *, time_remaining: str = "0") -> Path:
    # DK places the entry block and player-ownership block side by side. The
    # ownership block can extend below the last entry, hence nine total rows.
    rows = 9
    data = {
        "Rank": ["1", "2", "3", "4"] + [None] * (rows - 4),
        "EntryId": ["0001", "0002", "0003", "0004"] + [None] * (rows - 4),
        "EntryName": ["one", "two", "three", "four"] + [None] * (rows - 4),
        "TimeRemaining": [time_remaining] * 4 + [None] * (rows - 4),
        "Points": ["200.5", "190.0", "180.0", "170.0"] + [None] * (rows - 4),
        "Lineup": [LINEUP] * 4 + [None] * (rows - 4),
        "Player": [
            "Quarter Back", "Runner One", "Runner Two", "Wide One",
            "Wide Two", "Wide Three", "Tight End", "Flex Player", "Defense",
        ],
        "Roster Position": [
            "QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST",
        ],
        "%Drafted": ["100.00%"] * rows,
        "FPTS": ["20.0"] * rows,
        "Winnings": ["$1,000", "$100", "$50", "$0"] + [None] * (rows - 4),
    }
    pd.DataFrame(data).to_csv(path, index=False)
    return path


def test_full_field_validation_preserves_rosters_scores_and_duplicate_keys(tmp_path):
    source = _write_full_field(tmp_path / "standings.csv")
    result = oi.validate_full_field_capture(source, expected_entries=4)

    entries = result["entries"]
    assert entries.entry_id.tolist() == ["0001", "0002", "0003", "0004"]
    assert entries.points.tolist() == pytest.approx([200.5, 190.0, 180.0, 170.0])
    assert entries.lineup.eq(LINEUP).all()
    assert entries.lineup_slots_json.str.contains('"slot": "QB"').all()
    assert entries.duplicate_key.nunique() == 1
    assert entries.lineup_sha256.nunique() == 1
    assert entries.payout.iloc[0] == 1000.0
    assert result["roster_format"] == "classic"
    assert result["ownership_mass"] == pytest.approx(900.0)
    assert result["max_duplicate_count"] == 4
    assert len(result["source_sha256"]) == 64


def test_full_field_validation_rejects_partial_or_unsettled_export(tmp_path):
    source = _write_full_field(tmp_path / "standings.csv")
    with pytest.raises(ValueError, match="full-field count mismatch"):
        oi.validate_full_field_capture(source, expected_entries=5)

    unsettled = _write_full_field(
        tmp_path / "unsettled.csv", time_remaining="12:34"
    )
    with pytest.raises(ValueError, match="not demonstrably settled"):
        oi.validate_full_field_capture(unsettled, expected_entries=4)


def test_capture_defaults_to_validation_only_without_external_writes(
    tmp_path, monkeypatch
):
    source = _write_full_field(tmp_path / "contest-standings-12345.csv")

    def unexpected(*args, **kwargs):
        raise AssertionError("validation-only mode attempted an external write")

    monkeypatch.setattr(oi, "_archive_bytes_create_only", unexpected)
    monkeypatch.setattr(oi, "load_dataframe", unexpected)
    result = oi.capture_full_field(
        str(source),
        season=2026,
        week=1,
        contest_id="12345",
        contest_name="Millionaire Maker",
        expected_entries=4,
    )

    assert result["status"] == "validated-only"
    assert result["apply_required"] is True
    assert result["evidence_timing"] == "settlement_pending_operator_confirmation"
    assert result["validation"]["operator_confirmed_settled"] is False
    assert result["contest"]["observed_entries"] == 4
    assert result["source"]["capture_time_basis"] == "source_file_mtime"


def test_apply_archives_source_first_and_receipt_last_with_retry_safe_jobs(
    tmp_path, monkeypatch
):
    source = _write_full_field(tmp_path / "contest-standings-12345.csv")
    events: list[tuple] = []

    def fake_archive(*, bucket_name, object_name, payload, content_type):
        events.append(("archive", object_name, payload, content_type))
        return "created"

    def fake_load(frame, table, *, write_disposition, job_id, **table_contract):
        events.append(
            ("load", table, frame.copy(), write_disposition, job_id, table_contract)
        )

    monkeypatch.setattr(oi, "_archive_bytes_create_only", fake_archive)
    monkeypatch.setattr(oi, "load_dataframe", fake_load)
    monkeypatch.setattr(oi, "_preflight_warehouse_contract", lambda: None)
    result = oi.capture_full_field(
        str(source),
        season=2026,
        week=1,
        contest_id="12345",
        contest_name="Millionaire Maker",
        expected_entries=4,
        captured_at="2026-09-15T10:30:00-05:00",
        bucket_name="portable-test-bucket",
        confirm_settled=True,
        confirm_full_field=True,
        apply=True,
    )

    assert [event[0] for event in events] == ["archive", "load", "load", "archive"]
    assert "/contest_id=12345/capture_id=" in events[0][1]
    assert events[0][1].endswith("/source.csv")
    assert events[-1][1].endswith("/receipt.json")
    receipt = json.loads(events[-1][2])
    assert receipt["capture_id"] == result["capture_id"]
    assert receipt["source"]["captured_at"] == "2026-09-15T15:30:00Z"
    assert receipt["validation"]["operator_confirmed_full_field"] is True

    entries_load, ownership_load = events[1], events[2]
    assert entries_load[1] == "contest_entries"
    assert ownership_load[1] == "contest_ownership"
    assert entries_load[4].startswith("dk_entries_")
    assert ownership_load[4].startswith("dk_ownership_")
    assert entries_load[4] != ownership_load[4]
    assert entries_load[5] == {
        "partition_field": "imported_at",
        "clustering_fields": ("season", "week", "contest_id"),
    }
    assert ownership_load[5] == {"partition_field": "imported_at"}
    for frame in (entries_load[2], ownership_load[2]):
        assert frame.capture_id.eq(result["capture_id"]).all()
        assert frame.source_sha256.eq(result["source"]["sha256"]).all()
        assert frame.evidence_timing.eq("post_settlement").all()
        assert frame.expected_entries.eq(4).all()


def test_apply_requires_explicit_operator_confirmations(tmp_path):
    source = _write_full_field(tmp_path / "contest-standings-12345.csv")
    with pytest.raises(ValueError, match="confirm-settled"):
        oi.capture_full_field(
            str(source), season=2026, week=1, contest_id="12345",
            contest_name="Millionaire Maker", expected_entries=4, apply=True,
        )


def test_capture_rejects_wrong_contest_filename(tmp_path):
    source = _write_full_field(tmp_path / "contest-standings-99999.csv")
    with pytest.raises(ValueError, match="not present in source filename"):
        oi.capture_full_field(
            str(source), season=2026, week=1, contest_id="12345",
            contest_name="Millionaire Maker", expected_entries=4,
        )


def test_validation_reconstructs_ownership_from_entry_rosters(tmp_path):
    source = _write_full_field(tmp_path / "standings.csv")
    frame = pd.read_csv(source, dtype=str)
    frame.loc[0, "Player"] = "Wrong Player"  # mass remains exactly 900
    frame.to_csv(source, index=False)
    with pytest.raises(ValueError, match="ownership summary does not reproduce"):
        oi.validate_full_field_capture(source, expected_entries=4)


def test_capture_id_binds_persisted_metadata(tmp_path):
    source = _write_full_field(tmp_path / "contest-standings-12345.csv")
    common = {
        "path": str(source), "season": 2026, "week": 1,
        "contest_id": "12345", "contest_name": "Millionaire Maker",
        "expected_entries": 4, "confirm_settled": True,
        "confirm_full_field": True,
    }
    first = oi.capture_full_field(
        **common, captured_at="2026-09-15T10:30:00-05:00"
    )
    second = oi.capture_full_field(
        **common, captured_at="2026-09-15T10:31:00-05:00"
    )
    assert first["capture_id"] != second["capture_id"]


def test_warehouse_preflight_rejects_unpartitioned_existing_table(monkeypatch):
    table = SimpleNamespace(
        time_partitioning=None,
        clustering_fields=None,
        schema=[],
    )
    monkeypatch.setattr("nfl_dfs.bq.client", lambda: SimpleNamespace(
        get_table=lambda table_id: table
    ))
    with pytest.raises(RuntimeError, match="partition/clustering"):
        oi._preflight_warehouse_contract()


def test_showdown_duplicate_key_preserves_captain_assignment():
    a = oi.parse_lineup_slots(
        "CPT Josh Allen FLEX Stefon Diggs FLEX James Cook "
        "FLEX Dalton Kincaid FLEX Player Five FLEX Bills"
    )
    b = oi.parse_lineup_slots(
        "CPT Stefon Diggs FLEX Josh Allen FLEX James Cook "
        "FLEX Dalton Kincaid FLEX Player Five FLEX Bills"
    )
    assert oi._duplicate_key(a, "showdown") != oi._duplicate_key(b, "showdown")


def _write_full_field_with_blank_entry(path: Path) -> Path:
    """DraftKings lists never-filled entries with an EntryId and Rank but a blank Lineup (2026-09-14: 1,314 of them
    in the Week-1 Millionaire export). They are part of the field at zero points."""
    rows = 9
    data = {
        "Rank": ["1", "2", "3", "4", "5"] + [None] * (rows - 5),
        "EntryId": ["0001", "0002", "0003", "0004", "0005"] + [None] * (rows - 5),
        "EntryName": ["one", "two", "three", "four", "blank"] + [None] * (rows - 5),
        "TimeRemaining": ["0"] * 5 + [None] * (rows - 5),
        "Points": ["200.5", "190.0", "180.0", "170.0", "0"] + [None] * (rows - 5),
        "Lineup": [LINEUP] * 4 + [None] + [None] * (rows - 5),
        "Player": [
            "Quarter Back", "Runner One", "Runner Two", "Wide One",
            "Wide Two", "Wide Three", "Tight End", "Flex Player", "Defense",
        ],
        "Roster Position": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"],
        "%Drafted": ["80.00%"] * rows,   # 4 of the 5 submitted entries hold each player: DK divides by the whole field
        "FPTS": ["20.0"] * rows,
        "Winnings": ["$1,000", "$100", "$50", "$0", "$0"] + [None] * (rows - 5),
    }
    pd.DataFrame(data).to_csv(path, index=False)
    return path


def test_full_field_validation_counts_blank_lineup_entries_toward_the_field(tmp_path):
    source = _write_full_field_with_blank_entry(tmp_path / "standings.csv")
    result = oi.validate_full_field_capture(source, expected_entries=5)
    assert result["blank_lineup_entries"] == 1
    assert len(result["entries"]) == 4
    with pytest.raises(ValueError, match="count mismatch"):
        oi.validate_full_field_capture(source, expected_entries=4)


def test_full_field_validation_ranks_ties_at_draftkings_two_decimal_precision(tmp_path):
    """The export serialises 217.06 as 217.05998 for some entries; tied entries must still reproduce DK's shared rank."""
    rows = 9
    data = {
        "Rank": ["1", "1", "3", "4"] + [None] * (rows - 4),
        "EntryId": ["0001", "0002", "0003", "0004"] + [None] * (rows - 4),
        "EntryName": ["one", "two", "three", "four"] + [None] * (rows - 4),
        "TimeRemaining": ["0"] * 4 + [None] * (rows - 4),
        "Points": ["217.06", "217.05998", "180.0", "170.0"] + [None] * (rows - 4),
        "Lineup": [LINEUP] * 4 + [None] * (rows - 4),
        "Player": ["Quarter Back", "Runner One", "Runner Two", "Wide One", "Wide Two", "Wide Three", "Tight End", "Flex Player", "Defense"],
        "Roster Position": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"],
        "%Drafted": ["100.00%"] * rows,
        "FPTS": ["20.0"] * rows,
        "Winnings": ["$1,000", "$1,000", "$50", "$0"] + [None] * (rows - 4),
    }
    source = tmp_path / "standings.csv"
    pd.DataFrame(data).to_csv(source, index=False)
    result = oi.validate_full_field_capture(source, expected_entries=4)
    assert result["winner_score"] == pytest.approx(217.06, abs=0.01)


def test_ownership_cross_check_rejects_gaps_on_players_above_one_percent(tmp_path):
    """The one-entry tolerance applies only below 1% ownership; a one-entry gap on a 75%-owned player fails closed."""
    source = _write_full_field(tmp_path / "standings.csv")
    raw = oi._read_export(source)
    entries = oi._parse_entries_frame(raw, source)
    ownership = oi._parse_standings_frame(raw, source)
    assert oi._validate_ownership_against_entries(entries, ownership, field_size=4) == []
    ownership.loc[ownership.display_name.eq("Flex Player"), "pct_drafted"] = 75.0
    with pytest.raises(ValueError, match="pct_mismatch"):
        oi._validate_ownership_against_entries(entries, ownership, field_size=4)


def _entries_and_summary(n_rows: int, field_size: int, shown_overrides: dict[str, float]):
    """`n_rows` complete identical lineups in a field of `field_size`; the summary shows every player at the
    lineup-derived share except the overrides."""
    rows = 9
    data = {
        "Rank": [str(i + 1) for i in range(n_rows)] + [None] * max(0, rows - n_rows),
        "EntryId": [f"{i:04d}" for i in range(n_rows)] + [None] * max(0, rows - n_rows),
        "EntryName": ["u"] * n_rows + [None] * max(0, rows - n_rows),
        "TimeRemaining": ["0"] * n_rows + [None] * max(0, rows - n_rows),
        "Points": ["100.0"] * n_rows + [None] * max(0, rows - n_rows),
        "Lineup": [LINEUP] * n_rows + [None] * max(0, rows - n_rows),
    }
    length = max(rows, n_rows)
    players = ["Quarter Back", "Runner One", "Runner Two", "Wide One", "Wide Two", "Wide Three", "Tight End", "Flex Player", "Defense"]
    data["Player"] = players + [None] * (length - 9)
    data["Roster Position"] = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"] + [None] * (length - 9)
    derived = round(100.0 * n_rows / field_size, 2)
    data["%Drafted"] = [f"{shown_overrides.get(p, derived):.2f}%" for p in players] + [None] * (length - 9)
    data["FPTS"] = ["10.0"] * 9 + [None] * (length - 9)
    raw = pd.DataFrame(data)
    return oi._parse_entries_frame(raw, "synthetic"), oi._parse_standings_frame(raw, "synthetic")


def test_small_field_one_entry_shortfall_on_a_lightly_held_player_is_tolerated_and_recorded():
    """68-entry Week-2 satellite: players held by two entries were shown at 1.47% (one entry) by DraftKings."""
    entries, ownership = _entries_and_summary(2, 68, {"Flex Player": 1.47})
    assert oi._validate_ownership_against_entries(entries, ownership, field_size=68) == ["Flex Player"]
    entries, ownership = _entries_and_summary(4, 59, {"Tight End": 3.39})     # Goedert: 6.78 derived, 3.39 shown
    assert oi._validate_ownership_against_entries(entries, ownership, field_size=59) == ["Tight End"]


def test_large_field_half_share_on_a_near_zero_player_is_tolerated_but_not_more():
    """Millionaire Week 2: 69 lineups held a player DraftKings summarised at 0.02% (0.04% derived)."""
    entries, ownership = _entries_and_summary(69, 172_761, {"Wide Three": 0.02})
    assert oi._validate_ownership_against_entries(entries, ownership, field_size=172_761) == ["Wide Three"]
    entries, ownership = _entries_and_summary(6, 594, {"Runner Two": 0.51})         # supersat 195660201: Engram 1.01 derived, 0.51 shown
    assert oi._validate_ownership_against_entries(entries, ownership, field_size=594) == ["Runner Two"]
    entries, ownership = _entries_and_summary(69, 172_761, {"Wide Three": 0.11})   # shown far above derived: not a rounding shortfall
    with pytest.raises(ValueError, match="pct_mismatch"):
        oi._validate_ownership_against_entries(entries, ownership, field_size=172_761)


def test_shortfall_on_a_widely_held_player_still_fails_closed():
    """A two-entry gap is tolerated only while the shown share is below 5%; the 75% case above stays a failure."""
    entries, ownership = _entries_and_summary(10, 68, {"Runner One": 11.76})     # 14.71 derived, shown two entries short
    with pytest.raises(ValueError, match="pct_mismatch"):
        oi._validate_ownership_against_entries(entries, ownership, field_size=68)


def test_mass_tolerance_scales_with_the_field(tmp_path):
    """68 complete lineups summing to 895.43 (Week-2 satellite) validate; the same shortfall in a 4-entry field does not."""
    rows = 68
    data = {
        "Rank": [str(i + 1) for i in range(rows)], "EntryId": [f"{i:04d}" for i in range(rows)], "EntryName": ["u"] * rows,
        "TimeRemaining": ["0"] * rows, "Points": [f"{200 - i:.1f}" for i in range(rows)], "Lineup": [LINEUP] * rows,
        "Player": ["Quarter Back", "Runner One", "Runner Two", "Wide One", "Wide Two", "Wide Three", "Tight End", "Flex Player", "Defense"] + [None] * (rows - 9),
        "Roster Position": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"] + [None] * (rows - 9),
        "%Drafted": ["100.00%"] * 8 + ["95.43%"] + [None] * (rows - 9),
        "FPTS": ["10.0"] * 9 + [None] * (rows - 9),
    }
    source = tmp_path / "standings.csv"; pd.DataFrame(data).to_csv(source, index=False)
    with pytest.raises(ValueError, match="pct_mismatch"):      # a 4.57-point gap on a 95%-owned player is not a rounding shortfall
        oi.validate_full_field_capture(source, expected_entries=68)
    data["%Drafted"] = ["100.00%"] * 8 + ["100.00%"] + [None] * (rows - 9)
    pd.DataFrame(data).to_csv(source, index=False)
    result = oi.validate_full_field_capture(source, expected_entries=68)
    assert result["ownership_mass_tolerance"] == pytest.approx(min(10.0, max(2.0, 600.0 / 68)))
