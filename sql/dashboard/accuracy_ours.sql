-- Our newest pre-lock projection batch per week against realized DK points.
-- Lock = 13:00 Eastern on the week's Sunday (the main slate).
WITH lock AS (
  SELECT CAST(week AS INT64) AS week,
         TIMESTAMP(CONCAT(MIN(gameday), ' 13:00:00'), 'America/New_York') AS lock_ts
  FROM `${raw}.schedules`
  WHERE season = ${season} AND game_type = 'REG' AND weekday = 'Sunday'
  GROUP BY 1
),
p AS (
  SELECT p.* FROM `${predictions}.player_projections` p
  JOIN lock l ON l.week = p.week
  WHERE p.season = ${season} AND p.generated_at < l.lock_ts
  QUALIFY p.generated_at = MAX(p.generated_at) OVER (PARTITION BY p.week)
),
p1 AS (
  SELECT * FROM p
  QUALIFY ROW_NUMBER() OVER (PARTITION BY week, gsis_id ORDER BY slate_id) = 1
)
SELECT p1.week, p1.gsis_id, p1.display_name, p1.position, p1.team, p1.salary,
       p1.proj_points, a.dk_points
FROM p1
JOIN `${features}.player_week_actuals` a
  ON a.gsis_id = p1.gsis_id AND a.season = p1.season AND a.week = p1.week
WHERE p1.position IN ('QB', 'RB', 'WR', 'TE')
