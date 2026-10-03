-- DK points allowed per defense per position per week (the rear-view table
-- the old /defense page read; its rolling columns include the current week).
SELECT team, CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
       position, fp_allowed
FROM `${features}.defense_points_against`
WHERE season = ${season}
ORDER BY week, team, position
