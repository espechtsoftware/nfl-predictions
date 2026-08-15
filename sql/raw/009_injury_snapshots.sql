-- Append-only collector-time snapshots of the nflverse injury report.
--
-- Beginning with the 2025 source season, nflverse retains report/practice
-- statuses while `date_modified` can be NULL for every row.  Those final
-- season files cannot be admitted to a point-in-time feature simply because
-- the report is nominally weekly.  The scheduled collector therefore records
-- what it actually observed and when.  Feature SQL may use a row only when
-- `pulled_at` is before the common Sunday-main lock.
CREATE TABLE IF NOT EXISTS `${raw}.injury_snapshots` (
  pulled_at TIMESTAMP NOT NULL,
  capture_id STRING NOT NULL,
  season INT64,
  game_type STRING,
  team STRING,
  week INT64,
  gsis_id STRING,
  position STRING,
  full_name STRING,
  first_name STRING,
  last_name STRING,
  report_primary_injury STRING,
  report_secondary_injury STRING,
  report_status STRING,
  practice_primary_injury STRING,
  practice_secondary_injury STRING,
  practice_status STRING,
  date_modified TIMESTAMP,
  season_type STRING,
  source_row_sha256 STRING NOT NULL
)
PARTITION BY DATE(pulled_at)
CLUSTER BY season, week, gsis_id;
