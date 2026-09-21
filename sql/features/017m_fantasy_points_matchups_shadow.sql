-- Shadow-only PIT matchup identity surface. It is intentionally not included
-- by model features or project-slate until a separately frozen efficacy study.
CREATE OR REPLACE TABLE `${features}.player_week_fp_matchups_shadow` AS
SELECT
  source_run_id, target_season AS season, target_week AS week,
  source_season, report, player_name, team_raw, opponent_raw,
  source_file, source_sha256, captured_at, raw_row_json
FROM `${raw}.fantasy_points_matchups_live`
WHERE target_season IS NOT NULL AND target_week IS NOT NULL
  AND captured_at IS NOT NULL;
