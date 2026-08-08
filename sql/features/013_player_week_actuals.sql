-- Realized per-player-week stat lines and DK classic points (labels).
-- The source stat rows are preserved, then completed with zero labels for
-- salary-listed players on already-played regular-season slates. Without the
-- zero rows, the historical replay universe conditions on having recorded a
-- box-score event and cannot represent a pre-lock player pool honestly.
CREATE OR REPLACE TABLE `${features}.player_week_actuals` AS
WITH stats AS (
  SELECT
    player_id AS gsis_id,
    CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
    team,
    targets, receptions,
    receiving_yards AS rec_yards,
    receiving_tds AS rec_tds,
    carries,
    rushing_yards AS rush_yards,
    rushing_tds AS rush_tds,
    attempts AS pass_attempts,
    completions,
    passing_yards AS pass_yards,
    passing_tds AS pass_tds,
    passing_interceptions AS interceptions,
    sack_fumbles_lost + rushing_fumbles_lost + receiving_fumbles_lost
      AS fumbles_lost,
    passing_2pt_conversions + rushing_2pt_conversions
      + receiving_2pt_conversions AS two_pt,
    special_teams_tds,
    0.04 * passing_yards
      + 4 * passing_tds
      + IF(passing_yards >= 300, 3, 0)
      - passing_interceptions
      + 0.1 * rushing_yards
      + 6 * rushing_tds
      + IF(rushing_yards >= 100, 3, 0)
      + receptions
      + 0.1 * receiving_yards
      + 6 * receiving_tds
      + IF(receiving_yards >= 100, 3, 0)
      - (sack_fumbles_lost + rushing_fumbles_lost + receiving_fumbles_lost)
      + 2 * (passing_2pt_conversions + rushing_2pt_conversions
             + receiving_2pt_conversions)
      + 6 * special_teams_tds AS dk_points,
    TRUE AS has_stat_line
  FROM `${raw}.weekly_stats`
  WHERE season_type = 'REG' AND player_id IS NOT NULL
),
played_team_weeks AS (
  SELECT CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
         CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                        WHEN 'STL' THEN 'LA' ELSE home_team END AS team
  FROM `${raw}.schedules`
  WHERE game_type = 'REG' AND DATE(gameday) < CURRENT_DATE()
  UNION ALL
  SELECT CAST(season AS INT64), CAST(week AS INT64),
         CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                        WHEN 'STL' THEN 'LA' ELSE away_team END
  FROM `${raw}.schedules`
  WHERE game_type = 'REG' AND DATE(gameday) < CURRENT_DATE()
),
salary_zeros AS (
  SELECT
    s.gsis_id, s.season, s.week, s.team,
    CAST(0 AS FLOAT64) AS targets,
    CAST(0 AS FLOAT64) AS receptions,
    CAST(0 AS FLOAT64) AS rec_yards,
    CAST(0 AS FLOAT64) AS rec_tds,
    CAST(0 AS FLOAT64) AS carries,
    CAST(0 AS FLOAT64) AS rush_yards,
    CAST(0 AS FLOAT64) AS rush_tds,
    CAST(0 AS FLOAT64) AS pass_attempts,
    CAST(0 AS FLOAT64) AS completions,
    CAST(0 AS FLOAT64) AS pass_yards,
    CAST(0 AS FLOAT64) AS pass_tds,
    CAST(0 AS FLOAT64) AS interceptions,
    CAST(0 AS FLOAT64) AS fumbles_lost,
    CAST(0 AS FLOAT64) AS two_pt,
    CAST(0 AS FLOAT64) AS special_teams_tds,
    CAST(0 AS FLOAT64) AS dk_points,
    FALSE AS has_stat_line
  FROM `${features}.dk_salary_week` s
  JOIN played_team_weeks p USING (season, week, team)
  WHERE s.position IN ('QB', 'RB', 'WR', 'TE')
    AND NOT EXISTS (
      SELECT 1 FROM stats a
      WHERE a.gsis_id = s.gsis_id AND a.season = s.season AND a.week = s.week
    )
)
SELECT * FROM stats
UNION ALL
SELECT * FROM salary_zeros;
