-- Shadow-only destination for validated Fantasy Points live matchup exports.
-- No current feature or model query reads this table.
CREATE TABLE IF NOT EXISTS `${raw}.fantasy_points_matchups_live` (
  source_run_id STRING NOT NULL,
  capture_id STRING NOT NULL,
  target_season INT64 NOT NULL,
  target_week INT64 NOT NULL,
  source_season INT64 NOT NULL,
  report STRING NOT NULL,
  row_number INT64 NOT NULL,
  player_name STRING,
  team_raw STRING NOT NULL,
  opponent_raw STRING NOT NULL,
  raw_row_json STRING NOT NULL,
  source_file STRING NOT NULL,
  source_sha256 STRING NOT NULL,
  captured_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(captured_at)
CLUSTER BY target_season, target_week, report;
