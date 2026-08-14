from __future__ import annotations

import pandas as pd
import pytest

from nfl_dfs import bq


class _Job:
    def __init__(self, outcome):
        self.outcome = outcome

    def to_dataframe(self):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class _Client:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = 0

    def query(self, sql, job_config=None):
        self.calls += 1
        return _Job(next(self.outcomes))


def test_query_df_retries_complete_transient_reads(monkeypatch):
    transient = RuntimeError("BigQuery Storage internal error")
    expected = pd.DataFrame({"value": [1, 2]})
    fake = _Client([transient, transient, expected])
    delays = []
    monkeypatch.setattr(bq, "client", lambda: fake)
    monkeypatch.setattr(
        bq, "_retryable_read_error", lambda exc: exc is transient)
    monkeypatch.setattr(bq.time, "sleep", delays.append)

    result = bq.query_df("SELECT value")

    pd.testing.assert_frame_equal(result, expected)
    assert fake.calls == 3
    assert delays == [2.0, 4.0]


def test_query_df_does_not_retry_nontransient_errors(monkeypatch):
    fatal = ValueError("invalid query")
    fake = _Client([fatal])
    monkeypatch.setattr(bq, "client", lambda: fake)
    monkeypatch.setattr(bq, "_retryable_read_error", lambda exc: False)
    monkeypatch.setattr(
        bq.time, "sleep", lambda _delay: pytest.fail("unexpected retry"))

    with pytest.raises(ValueError, match="invalid query"):
        bq.query_df("not valid SQL")
    assert fake.calls == 1


def test_query_df_stops_after_bounded_attempts(monkeypatch):
    transient = RuntimeError("temporary")
    fake = _Client([transient] * 4)
    delays = []
    monkeypatch.setattr(bq, "client", lambda: fake)
    monkeypatch.setattr(bq, "_retryable_read_error", lambda exc: True)
    monkeypatch.setattr(bq.time, "sleep", delays.append)

    with pytest.raises(RuntimeError, match="temporary"):
        bq.query_df("SELECT 1")
    assert fake.calls == 4
    assert delays == [2.0, 4.0, 8.0]
