"""Offline coverage for the overlay-detection scaffold's env gate.

No network or BigQuery access here or in CI — run() must return before
touching either when INGEST_CONTESTS_ENABLED isn't set, which is the
default (this session has no GCP credentials and no live DK slate).
"""

import requests

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
