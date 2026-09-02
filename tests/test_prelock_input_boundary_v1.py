from __future__ import annotations

import pytest

from nfl_dfs import bq
from nfl_dfs.inference.prelock_input_boundary_v1 import (
    ALLOWED_BIGQUERY_TABLE_URIS,
    PrelockInputBoundaryError,
    build_prelock_input_read_manifest_v1,
    enforced_prelock_bigquery_boundary_v1,
)


class _Client:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def query(self, sql: str, *args, **kwargs):
        del args, kwargs
        self.queries.append(sql)
        return object()

    def load_table_from_dataframe(self, *args, **kwargs):
        raise AssertionError("write method must not be exposed")


def test_bigquery_boundary_allows_exact_tables_and_exposes_no_write_method(
    monkeypatch,
) -> None:
    delegate = _Client()
    original_factory = lambda: delegate
    monkeypatch.setattr(bq, "client", original_factory)
    allowed = min(ALLOWED_BIGQUERY_TABLE_URIS)

    with enforced_prelock_bigquery_boundary_v1() as salary:
        proxy = bq.client()
        proxy.query(f"SELECT * FROM `{allowed}`")
        with pytest.raises(AttributeError):
            proxy.load_table_from_dataframe([], allowed)

    with (
        pytest.raises(PrelockInputBoundaryError, match="observed"),
        enforced_prelock_bigquery_boundary_v1(),
    ):
        try:
            bq.client().query("SELECT * FROM `another-project.outcomes.actuals`")
        except PrelockInputBoundaryError:
            pass

    assert bq.client is original_factory
    assert delegate.queries == [f"SELECT * FROM `{allowed}`"]
    with enforced_prelock_bigquery_boundary_v1() as generation:
        pass
    manifest = build_prelock_input_read_manifest_v1(
        salary_boundary=salary,
        generation_boundary=generation,
    )
    assert manifest["activation_windows"] == [
        "salary-authority",
        "lineup-generation",
    ]
    assert manifest["outcome_sources_allowed"] == []


def test_bigquery_boundary_rejects_write_sql_unqualified_and_nested_activation(
    monkeypatch,
) -> None:
    delegate = _Client()
    monkeypatch.setattr(bq, "client", lambda: delegate)
    allowed = min(ALLOWED_BIGQUERY_TABLE_URIS)

    with (
        pytest.raises(PrelockInputBoundaryError, match="observed"),
        enforced_prelock_bigquery_boundary_v1(),
    ):
        try:
            bq.client().query(f"DELETE FROM `{allowed}` WHERE TRUE")
        except PrelockInputBoundaryError:
            pass
    with (
        pytest.raises(PrelockInputBoundaryError, match="observed"),
        enforced_prelock_bigquery_boundary_v1(),
    ):
        try:
            bq.client().query("SELECT 1")
        except PrelockInputBoundaryError:
            pass
    for sql in (
        f"SELECT * FROM `{allowed}`; DELETE FROM `{allowed}` WHERE TRUE",
        f"WITH rows AS (SELECT * FROM `{allowed}`) SELECT * FROM rows; "
        f"INSERT INTO `{allowed}` SELECT * FROM rows",
        f"WITH rows AS (SELECT * FROM `{allowed}`) "
        f"DELETE FROM `{allowed}` WHERE TRUE",
        f"SELECT * FROM `{allowed}`;",
    ):
        with (
            pytest.raises(PrelockInputBoundaryError, match="observed"),
            enforced_prelock_bigquery_boundary_v1(),
        ):
            try:
                bq.client().query(sql)
            except PrelockInputBoundaryError:
                pass
    with enforced_prelock_bigquery_boundary_v1():
        proxy = bq.client()
        with pytest.raises(AttributeError):
            _ = proxy._delegate
    assert delegate.queries == []
    inner = enforced_prelock_bigquery_boundary_v1()
    with (
        enforced_prelock_bigquery_boundary_v1(),
        pytest.raises(PrelockInputBoundaryError, match="concurrent"),
    ):
        inner.__enter__()
