-- Raw play-by-play landing table. Loaded WRITE_TRUNCATE by the nflverse job
-- with autodetect; this DDL documents the columns the downstream SQL depends
-- on (PBP has ~370 columns; the loader lands all of them).
CREATE TABLE IF NOT EXISTS `${raw}.pbp` (
  game_id STRING, play_id INT64, season INT64, week INT64, season_type STRING,
  posteam STRING, defteam STRING,
  yardline_100 INT64, down INT64, ydstogo INT64, qtr INT64,
  game_seconds_remaining INT64, score_differential INT64,
  play_type STRING, pass_attempt INT64, rush_attempt INT64,
  complete_pass INT64, touchdown INT64, pass_touchdown INT64, rush_touchdown INT64,
  passer_player_id STRING, rusher_player_id STRING, receiver_player_id STRING,
  air_yards FLOAT64, yards_after_catch FLOAT64, yards_gained INT64,
  epa FLOAT64, wpa FLOAT64, cpoe FLOAT64,
  shotgun INT64, no_huddle INT64, qb_dropback INT64,
  drive INT64, series INT64, fixed_drive_result STRING
)
PARTITION BY RANGE_BUCKET(season, GENERATE_ARRAY(1999, 2040, 1))
CLUSTER BY game_id, posteam;
