import pandas as pd

from nfl_dfs import bq


def test_load_dataframe_repeats_partition_and_clustering_contract(monkeypatch):
    captured = {}

    class _Job:
        def result(self):
            return None

    class _Client:
        def load_table_from_dataframe(self, df, table, job_config):
            captured.update(df=df, table=table, config=job_config)
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
