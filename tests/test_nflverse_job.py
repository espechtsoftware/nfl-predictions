"""Offline guards for nflverse ingestion and collector-time snapshots.

Regression for the 2026-07-28 data loss: the scheduled (incremental) run
loads only the current season, and _load's old unconditional WRITE_TRUNCATE
wiped the 2014-2024 backfill from every season-scoped raw table. The
incremental path must delete-then-append, never truncate."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from nfl_dfs.ingest import nflverse_job


class FakeFrame:
    def __init__(self, pdf):
        self._pdf = pdf

    def to_pandas(self):
        return self._pdf


def _capture(monkeypatch):
    loads, deletes = [], []
    monkeypatch.setattr(
        nflverse_job, "load_dataframe",
        lambda df, table, **kw: loads.append((table, kw.get("write_disposition",
                                                            "WRITE_TRUNCATE"))))
    monkeypatch.setattr(
        nflverse_job, "_delete_seasons",
        lambda table, seasons: deletes.append((table, tuple(seasons))))
    return loads, deletes


def test_incremental_load_deletes_then_appends(monkeypatch):
    loads, deletes = _capture(monkeypatch)
    df = FakeFrame(pd.DataFrame({"season": [2025], "x": [1]}))
    nflverse_job._load(df, "pbp", replace_seasons=[2025])
    assert deletes == [("pbp", (2025,))]
    assert loads == [("pbp", "WRITE_APPEND")]


def test_full_refresh_truncates(monkeypatch):
    loads, deletes = _capture(monkeypatch)
    df = FakeFrame(pd.DataFrame({"season": [2014, 2025], "x": [1, 2]}))
    nflverse_job._load(df, "pbp", replace_seasons=None)
    assert deletes == []
    assert loads == [("pbp", "WRITE_TRUNCATE")]


def test_incremental_without_season_column_falls_back_to_truncate(monkeypatch):
    loads, deletes = _capture(monkeypatch)
    df = FakeFrame(pd.DataFrame({"dt": ["2025-09-01"], "x": [1]}))
    nflverse_job._load(df, "depth_charts_snapshots", replace_seasons=[2025])
    assert deletes == []
    assert loads == [("depth_charts_snapshots", "WRITE_TRUNCATE")]


def _injury_frame() -> FakeFrame:
    rows = []
    for season, player, modified in (
        (2025, "00-old", "2025-09-05T15:00:00Z"),
        (2026, "00-live", None),
    ):
        rows.append({
            "season": season,
            "game_type": "REG",
            "team": "CHI",
            "week": 1,
            "gsis_id": player,
            "position": "WR",
            "full_name": "Example Player",
            "first_name": "Example",
            "last_name": "Player",
            "report_primary_injury": "Hamstring",
            "report_secondary_injury": None,
            "report_status": "Questionable",
            "practice_primary_injury": "Hamstring",
            "practice_secondary_injury": None,
            "practice_status": "Limited Participation in Practice",
            "date_modified": modified,
            "season_type": "REG",
        })
    return FakeFrame(pd.DataFrame(rows))


def test_injury_snapshot_is_live_season_only_and_preserves_null_source_time():
    pulled_at = datetime(2026, 9, 4, 16, 30, tzinfo=timezone.utc)
    out = nflverse_job.prepare_injury_snapshot(
        _injury_frame(), planning_season=2026, pulled_at=pulled_at,
    )
    assert out.gsis_id.tolist() == ["00-live"]
    assert out.season.tolist() == [2026]
    assert out.pulled_at.iloc[0] == pd.Timestamp(pulled_at)
    assert pd.isna(out.date_modified.iloc[0])
    assert out.capture_id.str.fullmatch(r"[0-9a-f]{64}").all()
    assert out.source_row_sha256.str.fullmatch(r"[0-9a-f]{64}").all()

    later = nflverse_job.prepare_injury_snapshot(
        _injury_frame(), planning_season=2026,
        pulled_at=datetime(2026, 9, 5, 16, 30, tzinfo=timezone.utc),
    )
    assert later.capture_id.iloc[0] != out.capture_id.iloc[0]
    assert later.source_row_sha256.iloc[0] == out.source_row_sha256.iloc[0]


def test_injury_snapshot_rejects_naive_collector_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        nflverse_job.prepare_injury_snapshot(
            _injury_frame(), planning_season=2026,
            pulled_at=datetime(2026, 9, 4, 16, 30),
        )


def test_injury_snapshot_append_uses_irreplaceable_table_contract(monkeypatch):
    calls = []
    monkeypatch.setattr(
        nflverse_job, "load_dataframe",
        lambda df, table, **kwargs: calls.append((df, table, kwargs)),
    )
    count = nflverse_job.append_injury_snapshot(
        _injury_frame(), planning_season=2026,
        pulled_at=datetime(2026, 9, 4, 16, 30, tzinfo=timezone.utc),
    )
    assert count == 1
    assert len(calls) == 1
    payload, table, kwargs = calls[0]
    assert len(payload) == 1
    assert table == "injury_snapshots"
    assert kwargs == {
        "write_disposition": "WRITE_APPEND",
        "partition_field": "pulled_at",
        "clustering_fields": ("season", "week", "gsis_id"),
    }
