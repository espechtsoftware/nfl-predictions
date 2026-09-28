from google.cloud import bigquery
P = "nfl-predictions-503414"
c = bigquery.Client(project=P)
sql = f"""
WITH inj AS (
  SELECT season, week, gsis_id, ANY_VALUE(report_status) rs, ANY_VALUE(practice_status) ps
  FROM `{P}.nfl_raw.injuries` WHERE game_type = "REG" AND season BETWEEN 2018 AND 2025 GROUP BY 1,2,3),
ros AS (
  SELECT season, week, gsis_id, ANY_VALUE(pfr_id) pfr_id, ANY_VALUE(position) position, ANY_VALUE(full_name) full_name,
         ANY_VALUE(team) team, ANY_VALUE(status) status
  FROM `{P}.nfl_raw.rosters_weekly`
  WHERE game_type = "REG" AND season BETWEEN 2018 AND 2025 AND position IN ("QB","RB","WR","TE") AND gsis_id IS NOT NULL
  GROUP BY 1,2,3),
teamweeks AS (SELECT DISTINCT season, week, team FROM `{P}.nfl_raw.snap_counts` WHERE game_type = "REG"),
snaps AS (SELECT season, week, pfr_player_id, SUM(offense_snaps) off FROM `{P}.nfl_raw.snap_counts`
          WHERE game_type = "REG" GROUP BY 1,2,3),
ws AS (
  SELECT season, week, player_id,
    0.04*IFNULL(passing_yards,0) + 4*IFNULL(passing_tds,0) - IFNULL(passing_interceptions,0) + IF(IFNULL(passing_yards,0) >= 300, 3, 0)
    + 0.1*IFNULL(rushing_yards,0) + 6*IFNULL(rushing_tds,0) + IF(IFNULL(rushing_yards,0) >= 100, 3, 0)
    + IFNULL(receptions,0) + 0.1*IFNULL(receiving_yards,0) + 6*IFNULL(receiving_tds,0) + IF(IFNULL(receiving_yards,0) >= 100, 3, 0)
    - IFNULL(rushing_fumbles_lost,0) - IFNULL(receiving_fumbles_lost,0) - IFNULL(sack_fumbles_lost,0)
    + 2*(IFNULL(passing_2pt_conversions,0) + IFNULL(rushing_2pt_conversions,0) + IFNULL(receiving_2pt_conversions,0))
    + 6*IFNULL(special_teams_tds,0) AS dk
  FROM `{P}.nfl_raw.weekly_stats` WHERE season_type = "REG")
SELECT r.season, r.week, r.gsis_id, r.position, r.full_name, r.team, r.status,
       IFNULL(i.rs, "None") rs, i.ps, IFNULL(s.off, 0) off, w.dk
FROM ros r
JOIN teamweeks t ON t.season = r.season AND t.week = r.week AND t.team = r.team
LEFT JOIN inj i ON i.season = r.season AND i.week = r.week AND i.gsis_id = r.gsis_id
LEFT JOIN snaps s ON s.season = r.season AND s.week = r.week AND s.pfr_player_id = r.pfr_id
LEFT JOIN ws w ON w.season = r.season AND w.week = r.week AND w.player_id = r.gsis_id
"""
df = c.query(sql).to_dataframe(); df.to_parquet("base.parquet"); print(df.shape); print(df.rs.value_counts().head(8))
sal = c.query(f"SELECT season, week, display_name, position, team_abbr, salary, dk_points FROM `{P}.nfl_raw.dk_salaries_historical` WHERE season BETWEEN 2018 AND 2025").to_dataframe()
sal.to_parquet("sal.parquet"); print(sal.shape)
