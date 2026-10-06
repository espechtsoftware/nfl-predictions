-- Team offense per week: points scored (schedules), DK points by the team's
-- players (player_week_actuals), total yards (weekly_stats) and plays (pbp).
WITH pts AS (
  SELECT CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
         home_team AS team, home_score AS points
  FROM `${raw}.schedules`
  WHERE season = ${season} AND game_type = 'REG' AND home_score IS NOT NULL
  UNION ALL
  SELECT CAST(season AS INT64), CAST(week AS INT64), away_team, away_score
  FROM `${raw}.schedules`
  WHERE season = ${season} AND game_type = 'REG' AND away_score IS NOT NULL
),
dk AS (
  SELECT season, week, team, SUM(dk_points) AS dk_points
  FROM `${features}.player_week_actuals`
  WHERE season = ${season} AND has_stat_line
  GROUP BY 1, 2, 3
),
yd AS (
  SELECT CAST(season AS INT64) AS season, CAST(week AS INT64) AS week, team,
         SUM(IFNULL(passing_yards, 0)) + SUM(IFNULL(rushing_yards, 0)) AS yards
  FROM `${raw}.weekly_stats`
  WHERE season = ${season} AND season_type = 'REG'
  GROUP BY 1, 2, 3
),
pl AS (
  SELECT CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
         posteam AS team, COUNTIF(pass_attempt = 1 OR rush_attempt = 1) AS plays
  FROM `${raw}.pbp`
  WHERE season = ${season} AND season_type = 'REG' AND posteam IS NOT NULL
  GROUP BY 1, 2, 3
)
SELECT pts.season, pts.week, pts.team, pts.points, dk.dk_points, yd.yards, pl.plays
FROM pts
LEFT JOIN dk USING (season, week, team)
LEFT JOIN yd USING (season, week, team)
LEFT JOIN pl USING (season, week, team)
ORDER BY week, team
