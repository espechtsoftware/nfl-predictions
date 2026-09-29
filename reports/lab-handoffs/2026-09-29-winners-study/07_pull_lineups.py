from google.cloud import bigquery
import pandas as pd
P = "nfl-predictions-503414"; c = bigquery.Client(project=P)
q = f"""
WITH e AS (
  SELECT week, contest_id, entry_id, REGEXP_REPLACE(entry_name, r'\\s*\\(\\d+/\\d+\\)\\s*$', '') AS user, rank, points, lineup_slots_json
  FROM `{P}.nfl_raw.contest_entries`
  WHERE season = 2026 AND contest_id IN ('193028206', '195648007', '195905122') AND n_players = 9
  QUALIFY ROW_NUMBER() OVER (PARTITION BY week, contest_id, entry_id ORDER BY imported_at DESC) = 1),
h AS (SELECT *, COUNT(*) OVER (PARTITION BY week, user) AS n_user FROM e)
SELECT week, entry_id, user, n_user, JSON_VALUE(it, '$.slot') AS slot, JSON_VALUE(it, '$.player') AS player
FROM h, UNNEST(JSON_QUERY_ARRAY(lineup_slots_json)) it WHERE n_user >= 20"""
d = c.query(q).to_dataframe(); d.to_parquet("heavy_lineups.parquet")
print(d.shape, d.groupby("week").agg(entries=("entry_id", "nunique"), users=("user", "nunique")).to_dict())
# the field's exposure per player (all entries), computed in SQL
q2 = f"""
WITH e AS (
  SELECT week, contest_id, entry_id, lineup_slots_json FROM `{P}.nfl_raw.contest_entries`
  WHERE season = 2026 AND contest_id IN ('193028206', '195648007', '195905122') AND n_players = 9
  QUALIFY ROW_NUMBER() OVER (PARTITION BY week, contest_id, entry_id ORDER BY imported_at DESC) = 1),
n AS (SELECT week, COUNT(*) n FROM e GROUP BY 1)
SELECT e.week, JSON_VALUE(it, '$.player') AS player, COUNT(*) / ANY_VALUE(n.n) AS field_expo
FROM e JOIN n USING (week), UNNEST(JSON_QUERY_ARRAY(e.lineup_slots_json)) it GROUP BY 1, 2"""
f = c.query(q2).to_dataframe(); f.to_parquet("field_expo.parquet"); print("field exposure rows", f.shape)
