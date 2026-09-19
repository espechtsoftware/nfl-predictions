-- PREPARED ONLY: execute after release authorization, writer census and fresh inventory comparison.


DECLARE release_snapshot_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP();

CREATE SCHEMA `nfl-predictions-503414.nfl_release_20260919_input_repair` OPTIONS(location='US', default_table_expiration_days=14);

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_id_overrides` CLONE `nfl-predictions-503414.nfl_features.player_id_overrides` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_id_map` CLONE `nfl-predictions-503414.nfl_features.player_id_map` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__dk_salary_week` CLONE `nfl-predictions-503414.nfl_features.dk_salary_week` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_role` CLONE `nfl-predictions-503414.nfl_features.player_week_role` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__rz_receiving` CLONE `nfl-predictions-503414.nfl_features.rz_receiving` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__rz_rushing` CLONE `nfl-predictions-503414.nfl_features.rz_rushing` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__schedule_long` CLONE `nfl-predictions-503414.nfl_features.schedule_long` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_actuals` CLONE `nfl-predictions-503414.nfl_features.player_week_actuals` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_usage` CLONE `nfl-predictions-503414.nfl_features.player_week_usage` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_efficiency` CLONE `nfl-predictions-503414.nfl_features.player_week_efficiency` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_advanced` CLONE `nfl-predictions-503414.nfl_features.player_week_advanced` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_context` CLONE `nfl-predictions-503414.nfl_features.team_week_context` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__defense_week_allowed` CLONE `nfl-predictions-503414.nfl_features.defense_week_allowed` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__defense_week_coverage` CLONE `nfl-predictions-503414.nfl_features.defense_week_coverage` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__referee_game_tendency` CLONE `nfl-predictions-503414.nfl_features.referee_game_tendency` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_neutral_pass` CLONE `nfl-predictions-503414.nfl_features.team_week_neutral_pass` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_ol_out` CLONE `nfl-predictions-503414.nfl_features.team_week_ol_out` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_pace` CLONE `nfl-predictions-503414.nfl_features.team_week_pace` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__defense_week_blitz` CLONE `nfl-predictions-503414.nfl_features.defense_week_blitz` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_target_concentration` CLONE `nfl-predictions-503414.nfl_features.team_week_target_concentration` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__qb_week_ngs` CLONE `nfl-predictions-503414.nfl_features.qb_week_ngs` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_ftn_offense` CLONE `nfl-predictions-503414.nfl_features.team_week_ftn_offense` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_xfp` CLONE `nfl-predictions-503414.nfl_features.player_week_xfp` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_schedule_ctx` CLONE `nfl-predictions-503414.nfl_features.team_week_schedule_ctx` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_fp_route` CLONE `nfl-predictions-503414.nfl_features.player_week_fp_route` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_qb_quality` CLONE `nfl-predictions-503414.nfl_features.team_week_qb_quality` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_injury` CLONE `nfl-predictions-503414.nfl_features.player_week_injury` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_week_vacated` CLONE `nfl-predictions-503414.nfl_features.team_week_vacated` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__game_weather` CLONE `nfl-predictions-503414.nfl_features.game_weather` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_training` CLONE `nfl-predictions-503414.nfl_features.player_week_training` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__defense_points_against` CLONE `nfl-predictions-503414.nfl_features.defense_points_against` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__player_week_inference` CLONE `nfl-predictions-503414.nfl_features.player_week_inference` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__team_defense_week` CLONE `nfl-predictions-503414.nfl_features.team_defense_week` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__tabpfn_projections` CLONE `nfl-predictions-503414.nfl_features.tabpfn_projections` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_predictions__player_projections` CLONE `nfl-predictions-503414.nfl_predictions.player_projections` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

CREATE SNAPSHOT TABLE `nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_predictions__div_shadow` CLONE `nfl-predictions-503414.nfl_predictions.div_shadow` FOR SYSTEM_TIME AS OF release_snapshot_ts OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));

SELECT release_snapshot_ts AS release_snapshot_ts;
