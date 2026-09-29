from google.cloud import bigquery
import pandas as pd
P = "nfl-predictions-503414"; c = bigquery.Client(project=P)
# every projection batch generated in the 3 days before each lock, for the main slate's players; plus official points and ownership
q = f"""
WITH grp AS (SELECT 1 AS week, TIMESTAMP('2026-09-13 17:00:00') AS lk, '193028206' AS cid UNION ALL SELECT 2, TIMESTAMP('2026-09-20 17:00:00'), '195648007' UNION ALL SELECT 3, TIMESTAMP('2026-09-27 17:00:00'), '195905122')
SELECT p.week, p.generated_at, p.display_name, p.position, p.salary, p.proj_points, p.proj_p90, p.proj_std
FROM `{P}.nfl_predictions.player_projections` p JOIN grp g ON p.week = g.week
WHERE p.season = 2026 AND p.generated_at BETWEEN TIMESTAMP_SUB(g.lk, INTERVAL 72 HOUR) AND g.lk"""
d = c.query(q).to_dataframe(); d.to_parquet("proj_batches.parquet")
print(d.groupby("week").agg(batches=("generated_at", "nunique"), rows=("display_name", "size"), first=("generated_at", "min"), last=("generated_at", "max")))
b = d.groupby(["week", "generated_at"]).size().reset_index(name="n"); print(b.to_string())
q2 = f"""
WITH grp AS (SELECT 1 AS week, '193028206' AS cid UNION ALL SELECT 2, '195648007' UNION ALL SELECT 3, '195905122')
SELECT o.week, o.display_name, SUM(o.pct_drafted) own, MAX(o.fpts) fpts FROM (
  SELECT o.week, o.display_name, o.roster_position, o.pct_drafted, o.fpts FROM `{P}.nfl_raw.contest_ownership` o JOIN grp g ON o.contest_id = g.cid AND o.week = g.week
  WHERE o.season = 2026 QUALIFY ROW_NUMBER() OVER (PARTITION BY o.week, o.display_name, o.roster_position ORDER BY o.imported_at DESC) = 1) o GROUP BY 1, 2"""
o = c.query(q2).to_dataframe(); o.to_parquet("own_pts.parquet"); print("own/pts rows", o.shape)
q3 = f"""SELECT * FROM `{P}.nfl_predictions.market_source_log` WHERE season = 2026 LIMIT 5"""
try:
    m = c.query(q3).to_dataframe(); print("market_source_log columns:", m.columns.tolist())
except Exception as ex: print("market_source_log:", str(ex)[:200])
