"""Offline coverage for the CFB data-collection scaffold's env gate
(issue #13 item 7).

No network or BigQuery access here or in CI — run() must return before
touching either when INGEST_CFB_ENABLED isn't set, which is the default
(this session has no GCP credentials, and CFB season hasn't started).
"""

import logging

import pytest
import requests

from nfl_dfs.ingest import cfb_job


def _draftables_payload(player_id=1):
    return {
        "competitions": [
            {
                "competitionId": 1,
                "startTime": "2026-08-30T17:00:00.0000000Z",
            }
        ],
        "draftables": [
            {
                "draftableId": player_id,
                "playerId": player_id,
                "displayName": "Test QB",
                "teamAbbreviation": "ABC",
                "position": "QB",
                "salary": 9000,
                "rosterSlotId": 1,
                "status": "None",
                "competition": {"competitionId": 1},
            }
        ],
    }


def _http_error(status_code, gid):
    response = requests.Response()
    response.status_code = status_code
    response.url = f"https://api.draftkings.test/draftgroups/{gid}/draftables"
    return requests.HTTPError(
        f"{status_code} response for draft group {gid}", response=response
    )


def test_run_is_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("INGEST_CFB_ENABLED", raising=False)

    def boom(*a, **k):
        raise AssertionError("should not touch the network when disabled")

    monkeypatch.setattr(requests.Session, "get", boom)
    cfb_job.run()  # must not raise


def test_run_bails_before_contests_when_no_draft_groups(monkeypatch):
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
    # No draft groups -> nothing to match contests to, and the job must
    # bail before ever calling cfb_contests (would waste a poll for nothing).
    assert calls == []


def test_run_loads_salaries_and_contests_when_enabled(monkeypatch):
    monkeypatch.setenv("INGEST_CFB_ENABLED", "1")

    groups = [{"draftGroupId": 90002, "sportId": 5, "draftGroupState": "Upcoming"}]
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_draft_groups", lambda session=None: groups
    )
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.fetch_draftables",
        lambda gid, session=None: _draftables_payload(),
    )
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_contests",
        lambda session=None: [
            {
                "id": 1,
                "dg": 90002,
                "n": "CFB $100K Kickoff",
                "gameType": "Classic",
                "a": 10,
                "m": 10_000,
                "nt": 2_000,
                "po": 100_000.0,
                "attr": {"IsGuaranteed": "true"},
                "sd": "/Date(1785513600000)/",
            }
        ],
    )

    loaded = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.cfb_job.load_dataframe",
        lambda df, table, **kw: loaded.append((table, df, kw)),
    )

    cfb_job.run()

    tables = [table for table, _, _ in loaded]
    assert tables == ["cfb_dk_salaries", "dk_contest_fills"]

    salaries_df = loaded[0][1]
    assert list(salaries_df.dk_player_id) == [1]
    assert str(salaries_df.game_start.dtype) == "datetime64[ns, UTC]"
    assert loaded[0][2] == {
        "write_disposition": "WRITE_APPEND",
        "partition_field": "pulled_at",
        "clustering_fields": ("draft_group_id", "dk_player_id"),
    }

    contests_df = loaded[1][1]
    assert list(contests_df.sport) == ["CFB"]
    assert loaded[1][2] == {
        "write_disposition": "WRITE_APPEND",
        "partition_field": "pulled_at",
        "clustering_fields": ("draft_group_id", "contest_id"),
    }


def test_run_skips_draftables_404_and_persists_healthy_group(monkeypatch, caplog):
    monkeypatch.setenv("INGEST_CFB_ENABLED", "1")
    groups = [
        {"draftGroupId": 152863, "sportId": 5, "draftGroupState": "Upcoming"},
        {"draftGroupId": 152864, "sportId": 5, "draftGroupState": "Upcoming"},
    ]
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_draft_groups", lambda session=None: groups
    )

    def fetch_draftables(gid, session=None):
        if gid == 152863:
            raise _http_error(404, gid)
        return _draftables_payload(player_id=2)

    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.fetch_draftables", fetch_draftables
    )
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_contests", lambda session=None: []
    )
    loaded = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.cfb_job.load_dataframe",
        lambda df, table, **kw: loaded.append((table, df)),
    )

    with caplog.at_level(logging.WARNING, logger=cfb_job.__name__):
        cfb_job.run()

    assert [table for table, _ in loaded] == ["cfb_dk_salaries"]
    assert list(loaded[0][1].draft_group_id) == [152864]
    assert "Skipping stale CFB draft group 152863" in caplog.text


def test_run_propagates_non_404_draftables_http_error(monkeypatch):
    monkeypatch.setenv("INGEST_CFB_ENABLED", "1")
    groups = [
        {"draftGroupId": 152865, "sportId": 5, "draftGroupState": "Upcoming"}
    ]
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_draft_groups", lambda session=None: groups
    )

    def fetch_draftables(gid, session=None):
        raise _http_error(503, gid)

    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.fetch_draftables", fetch_draftables
    )

    with pytest.raises(requests.HTTPError) as caught:
        cfb_job.run()

    assert caught.value.response is not None
    assert caught.value.response.status_code == 503


def test_run_fails_closed_when_all_draftables_groups_return_404(monkeypatch):
    monkeypatch.setenv("INGEST_CFB_ENABLED", "1")
    groups = [
        {"draftGroupId": 152863, "sportId": 5, "draftGroupState": "Upcoming"},
        {"draftGroupId": 152864, "sportId": 5, "draftGroupState": "Upcoming"},
    ]
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_draft_groups", lambda session=None: groups
    )

    def fetch_draftables(gid, session=None):
        raise _http_error(404, gid)

    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.fetch_draftables", fetch_draftables
    )
    loaded = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.cfb_job.load_dataframe",
        lambda *args, **kwargs: loaded.append(args),
    )

    with pytest.raises(RuntimeError, match="All advertised upcoming CFB"):
        cfb_job.run()

    assert loaded == []


def test_run_with_no_upcoming_groups_remains_a_noop(monkeypatch):
    monkeypatch.setenv("INGEST_CFB_ENABLED", "1")
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_draft_groups", lambda session=None: []
    )
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_contests", lambda session=None: []
    )
    loaded = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.cfb_job.load_dataframe",
        lambda *args, **kwargs: loaded.append(args),
    )

    cfb_job.run()

    assert loaded == []
