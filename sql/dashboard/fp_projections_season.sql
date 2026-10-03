-- Fantasy Points' newest pre-lock DraftKings Classic projection per player
-- per week (any Classic slate; the main slate's row wins when present).
WITH lock AS (
  SELECT CAST(week AS INT64) AS week,
         TIMESTAMP(CONCAT(MIN(gameday), ' 13:00:00'), 'America/New_York') AS lock_ts
  FROM `${raw}.schedules`
  WHERE season = ${season} AND game_type = 'REG' AND weekday = 'Sunday'
  GROUP BY 1
)
SELECT f.week, f.name, f.position, f.team, f.fantasy_points
FROM `${raw}.fantasy_points_dfs_projections` f
JOIN lock l ON l.week = f.week
WHERE f.season = ${season} AND f.operator = 'DraftKings' AND f.game_type = 'Classic'
  AND f.retrieved_at < l.lock_ts
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY f.week, f.name, f.team
  ORDER BY f.retrieved_at DESC, f.slate_name = 'Main' DESC, f.n_games DESC) = 1
