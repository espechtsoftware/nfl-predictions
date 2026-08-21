SELECT DISTINCT season, week, id
FROM `nfl-predictions-503414.nfl_predictions.slate_player_features`
  FOR SYSTEM_TIME AS OF @source_snapshot_at
WHERE season IN (2023, 2024, 2025)
  AND week BETWEEN 1 AND 18
  AND id IS NOT NULL
ORDER BY season, week, id
