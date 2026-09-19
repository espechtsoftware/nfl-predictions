-- PREPARED ONLY: execute after release authorization, writer census and fresh inventory comparison.


-- First verify all 36 snapshots exist and stop competing writers; this restore is not atomic.

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.player_id_overrides` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_id_overrides`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.player_id_map` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_id_map`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.dk_salary_week` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__dk_salary_week`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.player_week_role` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_role`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.rz_receiving` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__rz_receiving`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.rz_rushing` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__rz_rushing`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.schedule_long` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__schedule_long`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.player_week_actuals` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_actuals`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.player_week_usage` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_usage`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.player_week_efficiency` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_efficiency`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.player_week_advanced` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_advanced`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.team_week_context` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_context`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.defense_week_allowed` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__defense_week_allowed`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.defense_week_coverage` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__defense_week_coverage`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.referee_game_tendency` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__referee_game_tendency`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.team_week_neutral_pass` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_neutral_pass`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.team_week_ol_out` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_ol_out`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.team_week_pace` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_pace`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.defense_week_blitz` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__defense_week_blitz`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.team_week_target_concentration` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_target_concentration`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.qb_week_ngs` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__qb_week_ngs`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.team_week_ftn_offense` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_ftn_offense`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.player_week_xfp` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_xfp`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.team_week_schedule_ctx` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_schedule_ctx`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.player_week_fp_route` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_fp_route`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.team_week_qb_quality` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_qb_quality`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.player_week_injury` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_injury`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.team_week_vacated` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_vacated`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.game_weather` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__game_weather`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.player_week_training` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_training`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.defense_points_against` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__defense_points_against`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.player_week_inference` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_inference`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.team_defense_week` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_defense_week`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_features.tabpfn_projections` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__tabpfn_projections`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_predictions.player_projections` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_predictions__player_projections`;

CREATE OR REPLACE TABLE `nfl-predictions-503414.nfl_predictions.div_shadow` CLONE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_predictions__div_shadow`;

CREATE OR REPLACE VIEW `nfl-predictions-503414.nfl_features.unmatched_dk_players` AS
WITH latest_pull AS (
  SELECT MAX(pulled_at) AS ts FROM `nfl-predictions-503414.nfl_raw.dk_salaries`
)
SELECT DISTINCT s.dk_player_id, s.display_name, s.team_abbr, s.position, s.salary
FROM `nfl-predictions-503414.nfl_raw.dk_salaries` s, latest_pull
WHERE s.pulled_at = latest_pull.ts
  AND s.dk_player_id NOT IN (SELECT dk_player_id FROM `nfl-predictions-503414.nfl_features.player_id_map`)
ORDER BY s.salary DESC;
