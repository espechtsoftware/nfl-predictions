#!/usr/bin/env python3
"""ID-keyed QB availability table for the Sunday chain (read-only BigQuery).

  PYTHONPATH=<tools> python qb_flags.py OUT_CSV [--season 2026] [--week 2] [--group 153428]

Every QB in the latest projection batch (no projection threshold), with gsis_id, dk_player_id, team, salary,
proj_points, feature depth_rank, report injury_status, the DK feed status for the draft group, and the shared
classifier's team_class / role (qb_classify.py). Consumers: vet_book.py, vet_replace_v4.py, gen_sheet.py.
"""
import argparse, csv, pathlib, sys
import pandas as pd
from google.cloud import bigquery
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from qb_classify import classify_qbs  # noqa: E402

P = "nfl-predictions-503414"
ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--season", type=int, required=True)
ap.add_argument("--week", type=int, required=True); ap.add_argument("--group", type=int, required=True); a = ap.parse_args()
c = bigquery.Client(project=P)
q = f"""
WITH proj AS (
  SELECT gsis_id, dk_player_id, display_name, team, salary, proj_points
  FROM `{P}.nfl_predictions.player_projections`
  WHERE season=@s AND week=@w AND position='QB'
    AND generated_at=(SELECT MAX(generated_at) FROM `{P}.nfl_predictions.player_projections` WHERE season=@s AND week=@w)
),
inf AS (SELECT gsis_id, depth_rank, injury_status FROM `{P}.nfl_features.player_week_inference` WHERE season=@s AND week=@w AND position='QB'),
dk AS (SELECT dk_player_id, status, pulled_at FROM `{P}.nfl_raw.dk_salaries` WHERE draft_group_id=@g AND position='QB'
       QUALIFY ROW_NUMBER() OVER (PARTITION BY dk_player_id ORDER BY pulled_at DESC)=1)
SELECT p.gsis_id, p.dk_player_id, p.display_name AS qb_name, p.team, p.salary, ROUND(p.proj_points,2) AS proj,
       i.depth_rank, IFNULL(i.injury_status,'') AS injury_status, IFNULL(d.status,'') AS dk_status,
       (d.dk_player_id IS NOT NULL) AS dk_row_present, CAST(d.pulled_at AS STRING) AS dk_pulled_at,
       @s AS season, @w AS week, @g AS draft_group
FROM proj p LEFT JOIN inf i USING (gsis_id) LEFT JOIN dk d ON d.dk_player_id = p.dk_player_id
ORDER BY p.team, i.depth_rank"""
df = c.query(q, job_config=bigquery.QueryJobConfig(query_parameters=[
    bigquery.ScalarQueryParameter("s", "INT64", a.season), bigquery.ScalarQueryParameter("w", "INT64", a.week),
    bigquery.ScalarQueryParameter("g", "INT64", a.group)])).result().to_dataframe()
out = classify_qbs(df).drop(columns=["depth"])
out.to_csv(a.out, index=False)
n = out.role.value_counts().to_dict(); t = out.drop_duplicates("team").team_class.value_counts().to_dict()
print(f"{len(out)} QBs -> {a.out} | roles {n} | teams {t}")
