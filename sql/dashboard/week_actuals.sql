-- DK points per player from the box score (player_week_actuals), the
-- fallback for players no contest drafted.
SELECT gsis_id, dk_points
FROM `${features}.player_week_actuals`
WHERE season = ${season} AND week = ${week}
