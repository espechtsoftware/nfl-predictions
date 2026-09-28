from google.cloud import bigquery
P = "nfl-predictions-503414"; c = bigquery.Client(project=P)
dc = c.query(f"""SELECT season, week, club_code team, gsis_id, position, CAST(depth_team AS INT64) depth
  FROM `{P}.nfl_raw.depth_charts` WHERE game_type="REG" AND season BETWEEN 2019 AND 2024 AND position IN ("QB","RB","WR","TE") AND gsis_id IS NOT NULL""").to_dataframe()
dc.to_parquet("depth.parquet"); print("depth", dc.shape, dc.depth.value_counts().head(4).to_dict())
