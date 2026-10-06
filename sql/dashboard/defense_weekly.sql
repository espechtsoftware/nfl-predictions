-- DK points allowed per defense per position per week (the rear-view table
-- the old /defense page read; its rolling columns include the current week).
-- Only weeks whose opposing offense has at least one stat line: before the
-- stats land, player_week_actuals holds zeros that would rank as shutouts.
WITH played AS (
  SELECT season, week, team
  FROM `${features}.player_week_actuals`
  WHERE season = ${season}
  GROUP BY 1, 2, 3
  HAVING LOGICAL_OR(has_stat_line)
),
faced AS (
  SELECT s.season, s.week, s.opponent AS defense
  FROM `${features}.schedule_long` s
  JOIN played p ON p.season = s.season AND p.week = s.week AND p.team = s.team
)
SELECT d.team, CAST(d.season AS INT64) AS season, CAST(d.week AS INT64) AS week,
       d.position, d.fp_allowed
FROM `${features}.defense_points_against` d
JOIN faced f ON f.season = d.season AND f.week = d.week AND f.defense = d.team
WHERE d.season = ${season}
ORDER BY week, team, position
