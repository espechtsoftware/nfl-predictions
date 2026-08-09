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

def _sql_dir() -> Path:
    """sql/ lives at the repo root, NOT inside the package. Two layouts:
    a source checkout (this file is src/nfl_dfs/bq.py, so parents[2] is the
    root) and the container (pip-installed into site-packages, where
    parents[2] is /usr/local/lib/python3.11 — but the Dockerfile copies
    sql/ into the WORKDIR). The checkout path silently broke every
    scheduled build-features run (see the deficiency log, 2026-07-31)."""
    candidates = (
        Path(__file__).resolve().parents[2] / "sql",  # source checkout
        Path.cwd() / "sql",                           # container WORKDIR /app
    )
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


SQL_DIR = _sql_dir()


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
    clustering_fields: tuple[str, ...] | list[str] | None = None,
) -> None:
    """Load a DataFrame into `dataset.table` (fully qualified or raw-relative)."""
    from google.cloud import bigquery

    if "." not in table:
        table = f"{settings.raw}.{table}"
    job_config = bigquery.LoadJobConfig(write_disposition=write_disposition, autodetect=True)
    if write_disposition == "WRITE_APPEND":
        # Schema evolution (2026-08-04 readiness check): appends with NEW
        # columns (e.g. dk_draftable_id added to the ingest in July while
        # the off-season table kept the old schema) otherwise fail the
        # first September pull.
        job_config.schema_update_options = [
            bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
    if partition_field:
        job_config.time_partitioning = bigquery.TimePartitioning(field=partition_field)
    if clustering_fields:
        # BigQuery rejects a load into an existing clustered/partitioned
        # table when the job repeats only its partition specification. Keep
        # both parts of the destination contract explicit.
        job_config.clustering_fields = list(clustering_fields)
    log.info("Loading %d rows into %s (%s)", len(df), table, write_disposition)
    client().load_table_from_dataframe(df, table, job_config=job_config).result()
