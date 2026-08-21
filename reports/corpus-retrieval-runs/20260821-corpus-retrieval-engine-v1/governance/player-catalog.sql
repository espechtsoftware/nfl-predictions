SELECT
  player_id AS id,
  player_name AS name,
  position AS pos,
  team,
  opponent AS opp,
  game_id,
  salary,
  mean_projection AS proj
FROM
  `nfl-predictions-503414.nfl_forensic_review.final_forensic_20260814_player_corpus_repair4`
  FOR SYSTEM_TIME AS OF TIMESTAMP('2026-08-21T17:42:00Z')
WHERE
  scope = 'phase-s-cbwu-54'
  AND season = 2023
  AND week = 1
  AND slate_run_id = 'f6b66a804748'
  AND mean_projection IS NOT NULL
ORDER BY id
