"""Offline coverage for the CFB data-collection scaffold's env gate
(issue #13 item 7).

No network or BigQuery access here or in CI — run() must return before
touching either when INGEST_CFB_ENABLED isn't set, which is the default
(this session has no GCP credentials, and CFB season hasn't started).
"""

import requests

from nfl_dfs.ingest import cfb_job


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
        lambda gid, session=None: {
            "competitions": [{"competitionId": 1, "startTime": "2026-08-30T17:00:00Z"}],
            "draftables": [
                {
                    "draftableId": 1,
                    "playerId": 1,
                    "displayName": "Test QB",
                    "teamAbbreviation": "ABC",
                    "position": "QB",
                    "salary": 9000,
                    "rosterSlotId": 1,
                    "status": "None",
                    "competition": {"competitionId": 1},
                }
            ],
        },
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
        lambda df, table, **kw: loaded.append((table, df)),
    )

    cfb_job.run()

    tables = [t for t, _ in loaded]
    assert tables == ["cfb_dk_salaries", "dk_contest_fills"]

    salaries_df = loaded[0][1]
    assert list(salaries_df.dk_player_id) == [1]

    contests_df = loaded[1][1]
    assert list(contests_df.sport) == ["CFB"]
