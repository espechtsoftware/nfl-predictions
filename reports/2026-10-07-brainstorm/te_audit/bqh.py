"""Tiny read-only BigQuery helper for the TE-defense audit."""
import pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client()
def q(sql, **params):
    cfg = None
    if params:
        ps = []
        for k, v in params.items():
            if isinstance(v, list):
                t = "STRING" if (len(v) == 0 or isinstance(v[0], str)) else ("INT64" if isinstance(v[0], int) else "FLOAT64")
                ps.append(bigquery.ArrayQueryParameter(k, t, v))
            elif isinstance(v, int):
                ps.append(bigquery.ScalarQueryParameter(k, "INT64", v))
            elif isinstance(v, float):
                ps.append(bigquery.ScalarQueryParameter(k, "FLOAT64", v))
            else:
                ps.append(bigquery.ScalarQueryParameter(k, "STRING", v))
        cfg = bigquery.QueryJobConfig(query_parameters=ps)
    return BQ.query(sql, job_config=cfg).to_dataframe()
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60); pd.set_option("display.max_rows", 400)
