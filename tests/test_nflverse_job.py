"""Offline guard for nflverse_job._load's write dispositions.

Regression for the 2026-07-28 data loss: the scheduled (incremental) run
loads only the current season, and _load's old unconditional WRITE_TRUNCATE
wiped the 2014-2024 backfill from every season-scoped raw table. The
incremental path must delete-then-append, never truncate."""

import pandas as pd

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
