"""Offline coverage for the CFB collection-only scaffold's env gate.

No network or BigQuery access here or in CI — run() must return before
touching either when INGEST_CFB_ENABLED isn't set, which is the default
(this session has no GCP credentials and DK has no live CFB slate yet)."""

import pandas as pd
import requests

from nfl_dfs.ingest import cfb_job


def test_run_is_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("INGEST_CFB_ENABLED", raising=False)

    def boom(*a, **k):
        raise AssertionError("should not touch the network when disabled")

    monkeypatch.setattr(requests.Session, "get", boom)
    cfb_job.run()  # must not raise


def test_run_noop_when_enabled_but_no_groups(monkeypatch):
    monkeypatch.setenv("INGEST_CFB_ENABLED", "1")
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_draft_groups", lambda session=None: []
    )

    calls = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_contests",
        lambda session=None: calls.append("contests") or [],
    )

    cfb_job.run()
    # No draft groups -> nothing to match contests to; bail before polling
    # contests, same as contest_job.
    assert calls == []


def _fixture_payload():
    return {
        "competitions": [{"competitionId": 1, "startTime": "2026-09-05T23:00:00Z"}],
        "draftables": [
            {
                "draftableId": 5001,
                "playerId": 501,
                "displayName": "Some QB",
                "teamAbbreviation": "OSU",
                "position": "QB",
                "salary": 9500,
                "rosterSlotId": 601,
                "status": "None",
                "competition": {"competitionId": 1},
                "draftStatAttributes": [{"id": 90, "value": "24.1"}],
            },
        ],
    }


def test_run_polls_and_loads_when_enabled(monkeypatch):
    monkeypatch.setenv("INGEST_CFB_ENABLED", "1")

    group = {"draftGroupId": 77001, "gameTypeDescription": "Classic",
              "draftGroupState": "Upcoming"}
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_draft_groups", lambda session=None: [group]
    )
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.fetch_draftables",
        lambda gid, session=None: _fixture_payload(),
    )
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_contests", lambda session=None: []
    )

    loaded = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.cfb_job.load_dataframe",
        lambda df, table, **kw: loaded.append((table, df)),
    )

    cfb_job.run()

    assert len(loaded) == 1
    table, df = loaded[0]
    assert table == "cfb_dk_salaries"
    assert list(df.dk_player_id) == [501]
    assert df.iloc[0].salary == 9500


def test_run_loads_contests_when_present(monkeypatch):
    monkeypatch.setenv("INGEST_CFB_ENABLED", "1")

    group = {"draftGroupId": 77001, "gameTypeDescription": "Classic",
              "draftGroupState": "Upcoming"}
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_draft_groups", lambda session=None: [group]
    )
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.fetch_draftables",
        lambda gid, session=None: {"competitions": [], "draftables": []},
    )
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_contests",
        lambda session=None: [
            {"id": 1, "dg": 77001, "n": "CFB $50K Slate", "gameType": "Classic",
             "a": 10, "m": 5000, "nt": 4000, "po": 50_000.0,
             "attr": {"IsGuaranteed": "true"}, "sd": "/Date(1785513600000)/"},
        ],
    )

    loaded = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.cfb_job.load_dataframe",
        lambda df, table, **kw: loaded.append((table, df)),
    )

    cfb_job.run()

    assert len(loaded) == 1
    table, df = loaded[0]
    assert table == "cfb_dk_contest_fills"
    assert list(df.contest_id) == [1]
