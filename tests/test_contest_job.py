"""Offline coverage for the overlay-detection scaffold's env gate.

No network or BigQuery access here or in CI — run() must return before
touching either when INGEST_CONTESTS_ENABLED isn't set, which is the
default (this session has no GCP credentials and no live DK slate).
"""

import requests
import pandas as pd

from nfl_dfs.ingest import contest_job


def test_run_is_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("INGEST_CONTESTS_ENABLED", raising=False)

    def boom(*a, **k):
        raise AssertionError("should not touch the network when disabled")

    monkeypatch.setattr(requests.Session, "get", boom)
    contest_job.run()  # must not raise


def test_run_polls_when_enabled(monkeypatch):
    monkeypatch.setenv("INGEST_CONTESTS_ENABLED", "1")
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.nfl_draft_groups", lambda session=None: []
    )

    calls = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.nfl_contests",
        lambda session=None: calls.append("contests") or [],
    )

    contest_job.run()
    # No draft groups -> nothing to match contests to, and the job must
    # bail before ever calling nfl_contests (would waste a poll for nothing).
    assert calls == []


def test_run_preserves_existing_partition_and_clustering_contract(monkeypatch):
    monkeypatch.setenv("INGEST_CONTESTS_ENABLED", "1")
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.nfl_draft_groups",
        lambda session=None: [{"draftGroupId": 151307}],
    )
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.nfl_contests",
        lambda session=None: [{"id": 12345}],
    )
    frame = pd.DataFrame({
        "contest_id": [12345],
        "draft_group_id": [151307],
        "is_guaranteed": [True],
    })
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.contests_frame",
        lambda contests, *, draft_group_ids: frame,
    )
    loads = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.contest_job.load_dataframe",
        lambda df, table, **kwargs: loads.append((df, table, kwargs)),
    )

    contest_job.run()

    assert loads == [
        (
            frame,
            "dk_contest_fills",
            {
                "write_disposition": "WRITE_APPEND",
                "partition_field": "pulled_at",
                "clustering_fields": ("draft_group_id", "contest_id"),
            },
        )
    ]
