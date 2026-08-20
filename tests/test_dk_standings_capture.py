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
