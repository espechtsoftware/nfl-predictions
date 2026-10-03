-- Fantasy Points' newest pre-lock DraftKings projected ownership per week.
WITH lock AS (
  SELECT CAST(week AS INT64) AS week,
         TIMESTAMP(CONCAT(MIN(gameday), ' 13:00:00'), 'America/New_York') AS lock_ts
  FROM `${raw}.schedules`
  WHERE season = ${season} AND game_type = 'REG' AND weekday = 'Sunday'
  GROUP BY 1
)
SELECT o.week, o.name, o.position, o.team, o.projected_ownership_pct
FROM `${raw}.fantasy_points_projected_ownership` o
JOIN lock l ON l.week = o.week
WHERE o.season = ${season} AND o.operator = 'DraftKings' AND o.retrieved_at < l.lock_ts
QUALIFY o.retrieved_at = MAX(o.retrieved_at) OVER (PARTITION BY o.week)
