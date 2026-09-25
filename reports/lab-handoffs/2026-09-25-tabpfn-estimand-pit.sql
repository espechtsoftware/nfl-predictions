-- Integrity 5.8 (laptop, 2026-09-25): calibration of the cached walk-forward TabPFN quantiles for 2025, by played status.
-- bq query --use_legacy_sql=false < reports/lab-handoffs/2026-09-25-tabpfn-estimand-pit.sql
WITH t AS (
  SELECT p.q10, p.q50, p.q90, tr.y_dk_points y, w.player_id IS NOT NULL played, UPPER(tr.position) pos
  FROM `nfl-predictions-503414.nfl_features.tabpfn_projections` p
  JOIN `nfl-predictions-503414.nfl_features.player_week_training` tr USING (season, week, gsis_id)
  LEFT JOIN (SELECT DISTINCT season, week, player_id FROM `nfl-predictions-503414.nfl_raw.weekly_stats`) w
    ON w.season = p.season AND w.week = p.week AND w.player_id = p.gsis_id
  WHERE p.season = 2025 AND tr.y_dk_points IS NOT NULL)
SELECT IF(played, 'played', 'did not play') grp, pos, COUNT(*) n,
  ROUND(AVG(IF(y <= q10, 1, 0)), 3) le_q10, ROUND(AVG(IF(y <= q50, 1, 0)), 3) le_q50, ROUND(AVG(IF(y <= q90, 1, 0)), 3) le_q90,
  ROUND(AVG(q10), 2) mean_q10, ROUND(AVG(q50), 2) mean_q50
FROM t WHERE pos IN ('QB', 'RB', 'WR', 'TE') GROUP BY 1, 2 ORDER BY 1 DESC, 2;
