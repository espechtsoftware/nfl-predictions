from types import SimpleNamespace

import pandas as pd

from nfl_dfs import bq


def test_load_dataframe_repeats_partition_and_clustering_contract(monkeypatch):
    captured = {}

    class _Job:
        def result(self):
            return None

    class _Client:
        def load_table_from_dataframe(self, df, table, job_config, **kwargs):
            captured.update(df=df, table=table, config=job_config, kwargs=kwargs)
            return _Job()

    monkeypatch.setattr(bq, "client", lambda: _Client())

    bq.load_dataframe(
        pd.DataFrame([{"requested_at": pd.Timestamp("2026-09-01T00:00:00Z")}]),
        "project.dataset.audit",
        write_disposition="WRITE_APPEND",
        partition_field="requested_at",
        clustering_fields=("request_kind", "http_status"),
    )

    config = captured["config"]
    assert config.time_partitioning.field == "requested_at"
    assert config.clustering_fields == ["request_kind", "http_status"]
    assert captured["table"] == "project.dataset.audit"
    assert captured["kwargs"] == {}


def test_load_dataframe_forwards_create_once_job_id(monkeypatch):
    captured = {}

    class _Job:
        def result(self):
            return None

    class _Client:
        def load_table_from_dataframe(self, df, table, job_config, **kwargs):
            captured.update(table=table, kwargs=kwargs)
            return _Job()

    monkeypatch.setattr(bq, "client", lambda: _Client())
    bq.load_dataframe(
        pd.DataFrame([{"capture_id": "abc"}]),
        "project.dataset.contest_entries",
        write_disposition="WRITE_APPEND",
        job_id="dk_entries_abc",
    )
    assert captured == {
        "table": "project.dataset.contest_entries",
        "kwargs": {"job_id": "dk_entries_abc"},
    }


def test_load_dataframe_accepts_only_same_destination_job_retry(monkeypatch):
    from google.api_core.exceptions import Conflict

    completed = []

    class _Existing:
        destination = SimpleNamespace(
            project="project", dataset_id="dataset", table_id="contest_entries"
        )
        job_type = "load"
        write_disposition = "WRITE_APPEND"
        output_rows = 1

        def result(self):
            completed.append(True)

    class _Client:
        def load_table_from_dataframe(self, df, table, job_config, **kwargs):
            raise Conflict("job already exists")

        def get_job(self, job_id, location):
            assert job_id == "dk_entries_abc"
            return _Existing()

    monkeypatch.setattr(bq, "client", lambda: _Client())
    bq.load_dataframe(
        pd.DataFrame([{"capture_id": "abc"}]),
        "project.dataset.contest_entries",
        write_disposition="WRITE_APPEND",
        job_id="dk_entries_abc",
    )
    assert completed == [True]
