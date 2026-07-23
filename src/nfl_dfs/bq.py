"""Thin BigQuery helpers.

google-cloud-bigquery is an optional dependency (the modeling / optimizer /
backtest code runs on plain DataFrames), so the import is deferred until a
client is actually needed.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from .config import settings

if TYPE_CHECKING:  # pragma: no cover
    from google.cloud import bigquery

log = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"


def client() -> "bigquery.Client":
    from google.cloud import bigquery

    return bigquery.Client(project=settings.project)


def render_sql(path: str | Path, **extra: Any) -> str:
    """Read a .sql file and substitute ${raw} / ${features} / ${predictions}
    dataset placeholders plus any extra ${key} values."""
    text = Path(path).read_text()
    subs = {
        "raw": settings.raw,
        "features": settings.features,
        "predictions": settings.predictions,
        **{k: str(v) for k, v in extra.items()},
    }
    for key, value in subs.items():
        text = text.replace("${" + key + "}", value)
    unresolved = re.findall(r"\$\{(\w+)\}", text)
    if unresolved:
        raise ValueError(f"Unresolved SQL placeholders in {path}: {unresolved}")
    return text


def run_sql_file(path: str | Path, **extra: Any) -> None:
    sql = render_sql(path, **extra)
    log.info("Running %s", path)
    client().query(sql).result()


def query_df(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    from google.cloud import bigquery

    job_config = None
    if params:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[_to_bq_param(k, v) for k, v in params.items()]
        )
    return client().query(sql, job_config=job_config).to_dataframe()


def _to_bq_param(name: str, value: Any):
    from google.cloud import bigquery

    if isinstance(value, (list, tuple)):
        elem = "INT64" if value and isinstance(value[0], int) else "STRING"
        return bigquery.ArrayQueryParameter(name, elem, list(value))
    if isinstance(value, bool):
        return bigquery.ScalarQueryParameter(name, "BOOL", value)
    if isinstance(value, int):
        return bigquery.ScalarQueryParameter(name, "INT64", value)
    if isinstance(value, float):
        return bigquery.ScalarQueryParameter(name, "FLOAT64", value)
    return bigquery.ScalarQueryParameter(name, "STRING", str(value))


def load_dataframe(
    df: pd.DataFrame,
    table: str,
    write_disposition: str = "WRITE_TRUNCATE",
    partition_field: str | None = None,
) -> None:
    """Load a DataFrame into `dataset.table` (fully qualified or raw-relative)."""
    from google.cloud import bigquery

    if "." not in table:
        table = f"{settings.raw}.{table}"
    job_config = bigquery.LoadJobConfig(write_disposition=write_disposition, autodetect=True)
    if partition_field:
        job_config.time_partitioning = bigquery.TimePartitioning(field=partition_field)
    log.info("Loading %d rows into %s (%s)", len(df), table, write_disposition)
    client().load_table_from_dataframe(df, table, job_config=job_config).result()
