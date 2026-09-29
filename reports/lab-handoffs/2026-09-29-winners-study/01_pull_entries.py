from google.cloud import bigquery
import pandas as pd
P = "nfl-predictions-503414"; c = bigquery.Client(project=P)
q = f"""SELECT week, contest_id, entry_id, entry_name, rank, points
FROM `{P}.nfl_raw.contest_entries` WHERE season = 2026 AND week IN (1, 2, 3)
QUALIFY ROW_NUMBER() OVER (PARTITION BY week, contest_id, entry_id ORDER BY imported_at DESC) = 1"""
d = c.query(q).to_dataframe()
d["user"] = d.entry_name.astype(str).str.replace(r"\s*\(\d+/\d+\)\s*$", "", regex=True)
d["contest_id"] = d.contest_id.astype(str)
d.drop(columns=["entry_name"]).to_parquet("entries_all.parquet")
print(d.groupby("week").agg(contests=("contest_id", "nunique"), entries=("entry_id", "size"), users=("user", "nunique")))
