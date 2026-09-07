"""Offline guards for nflverse ingestion and collector-time snapshots.

Regression for the 2026-07-28 data loss: the scheduled (incremental) run
loads only the current season, and _load's old unconditional WRITE_TRUNCATE
wiped the 2014-2024 backfill from every season-scoped raw table. The
incremental path must delete-then-append, never truncate."""

from datetime import UTC, datetime, timezone

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


def _early_planning_injury_frame() -> FakeFrame:
    """Match the sparse schema in nflverse's first 2026 release."""
    return FakeFrame(pd.DataFrame([{
        "season": 2026,
        "season_type": "REG",
        "game_type": "REG",
        "team": "CHI",
        "week": 1,
        "gsis_id": "00-live",
        "position": "WR",
        "full_name": "Example Player",
        "first_name": "Example",
        "last_name": "Player",
        "report_status": None,
        "practice_primary_injury": "Hamstring",
        "practice_status": "Limited Participation in Practice",
    }]))


class _InjuryDownloader:
    def __init__(self, frame: FakeFrame):
        self.frame = frame
        self.calls = []

    def download(self, repository, path, **kwargs):
        self.calls.append((repository, path, kwargs))
        return self.frame


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


def test_early_injury_schema_normalizes_only_known_nullable_absences():
    pulled_at = datetime(2026, 9, 7, 14, 0, tzinfo=UTC)

    out = nflverse_job.prepare_injury_snapshot(
        _early_planning_injury_frame(),
        planning_season=2026,
        pulled_at=pulled_at,
    )

    assert out.gsis_id.tolist() == ["00-live"]
    assert set(nflverse_job.INJURY_OPTIONAL_ABSENT_COLUMNS) <= set(out.columns)
    assert out[list(nflverse_job.INJURY_OPTIONAL_ABSENT_COLUMNS)].isna().all().all()

    missing_required = _early_planning_injury_frame().to_pandas().drop(
        columns=["practice_status"],
    )
    with pytest.raises(ValueError, match=r"missing required columns.*practice_status"):
        nflverse_job.prepare_injury_snapshot(
            FakeFrame(missing_required),
            planning_season=2026,
            pulled_at=pulled_at,
        )


def test_planning_season_injury_bypass_is_exact_and_key_validated(monkeypatch):
    downloader = _InjuryDownloader(_early_planning_injury_frame())
    monkeypatch.setattr(
        nflverse_job, "_injury_downloader", lambda: downloader,
    )

    out = nflverse_job._planning_season_injury_frame(
        planning_season=2026,
        data_season=2025,
        roster_year=2026,
    )

    assert downloader.calls == [(
        "nflverse-data",
        "injuries/injuries_2026",
        {"season": 2026},
    )]
    assert out.gsis_id.tolist() == ["00-live"]
    with pytest.raises(ValueError, match="exactly one year"):
        nflverse_job._planning_season_injury_frame(
            planning_season=2027,
            data_season=2025,
            roster_year=2026,
        )


@pytest.mark.parametrize(
    ("change", "message"),
    (
        (lambda frame: frame.iloc[0:0], "is empty"),
        (lambda frame: frame.assign(season=2025), "has seasons"),
        (lambda frame: frame.assign(gsis_id=" "), "empty gsis_id"),
        (lambda frame: frame.assign(team=" "), "empty team"),
        (lambda frame: pd.concat([frame, frame], ignore_index=True), "duplicate"),
    ),
)
def test_planning_season_injury_bypass_rejects_bad_source(
    monkeypatch, change, message,
):
    frame = change(_early_planning_injury_frame().to_pandas())
    monkeypatch.setattr(
        nflverse_job,
        "_injury_downloader",
        lambda: _InjuryDownloader(FakeFrame(frame)),
    )

    with pytest.raises(ValueError, match=message):
        nflverse_job._planning_season_injury_frame(
            planning_season=2026,
            data_season=2025,
            roster_year=2026,
        )


@pytest.mark.parametrize(
    ("data_season", "roster_year", "uses_planning_bypass"),
    ((2025, 2026, True), (2026, 2026, False)),
)
def test_run_stamps_injury_after_source_returns_across_lock(
    monkeypatch, data_season, roster_year, uses_planning_bypass,
):
    """A source returned after lock can never inherit the run-start time."""
    import nflreadpy as nfl

    planning_season = 2026
    slate_lock = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)
    run_started_at = slate_lock - pd.Timedelta(seconds=1)
    source_returned_at = slate_lock + pd.Timedelta(seconds=1)
    later_ordinary_return = source_returned_at + pd.Timedelta(seconds=1)
    times = iter((run_started_at, source_returned_at, later_ordinary_return))
    events = []
    appended = []

    monkeypatch.setattr(nflverse_job, "current_season", lambda: planning_season)
    monkeypatch.setattr(
        nfl,
        "get_current_season",
        lambda roster=False: roster_year if roster else data_season,
    )
    monkeypatch.setattr(
        nflverse_job,
        "_utc_now",
        lambda: events.append("clock") or next(times),
    )
    monkeypatch.setattr(
        nflverse_job,
        "_prospective_source_seasons",
        lambda *args, **kwargs: ([data_season], []),
    )
    monkeypatch.setattr(
        nflverse_job,
        "_weekly_roster_frame",
        lambda *args, **kwargs: pd.DataFrame({"season": [data_season]}),
    )
    monkeypatch.setattr(nflverse_job, "_load", lambda *args, **kwargs: None)

    ordinary = _early_planning_injury_frame().to_pandas().assign(
        season=data_season,
    )
    planning = _early_planning_injury_frame().to_pandas()

    def load_injuries(*args, **kwargs):
        events.append("ordinary-source-returned")
        return FakeFrame(ordinary)

    def load_planning(**kwargs):
        events.append("planning-source-returned")
        return planning

    monkeypatch.setattr(nfl, "load_injuries", load_injuries)
    monkeypatch.setattr(
        nflverse_job, "_planning_season_injury_frame", load_planning,
    )
    monkeypatch.setattr(
        nflverse_job,
        "append_injury_snapshot",
        lambda frame, **kwargs: appended.append((frame, kwargs)) or len(frame),
    )

    blank = FakeFrame(pd.DataFrame({"season": [data_season]}))
    for name in (
        "load_pbp", "load_player_stats", "load_schedules", "load_officials",
        "load_ff_playerids", "load_draft_picks", "load_combine",
        "load_snap_counts", "load_nextgen_stats", "load_ftn_charting",
        "load_pfr_advstats",
    ):
        monkeypatch.setattr(nfl, name, lambda *args, **kwargs: blank)

    nflverse_job.run()

    assert len(appended) == 1
    assert appended[0][1]["pulled_at"] == source_returned_at
    assert appended[0][1]["pulled_at"] > slate_lock
    if uses_planning_bypass:
        assert events.index("planning-source-returned") < events.index("clock", 1)
    else:
        assert "planning-source-returned" not in events
        assert events.index("ordinary-source-returned") < events.index("clock", 1)


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
