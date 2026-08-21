SELECT
  panel_run_id AS panel_id,
  season,
  week,
  cand_ix,
  tag,
  all_tags,
  players
FROM
  `nfl-predictions-503414.nfl_predictions.replay_candidates_staging`
  FOR SYSTEM_TIME AS OF TIMESTAMP('2026-08-21T17:42:00Z')
WHERE
  season = 2023
  AND week = 1
  AND panel_run_id IN (
    '20260815-atlas-money-worlds-r0-v1',
    '20260815-atlas-money-worlds-r1-v1',
    '20260815-atlas-money-worlds-r2-v1',
    '20260815-atlas-money-worlds-r3-v1',
    '20260815-atlas-money-worlds-r4-v1'
  )
ORDER BY panel_id, cand_ix
