-- Remaining raw landing tables. Most are loaded WRITE_TRUNCATE with schema
-- autodetect from the nflverse job; only the append-only snapshot tables
-- need explicit DDL for partitioning.

CREATE TABLE IF NOT EXISTS `${raw}.odds_snapshots` (
  pulled_at TIMESTAMP,
  event_id STRING,
  event_name STRING,
  start_time STRING,
  market_type STRING,           -- 'Moneyline' | 'Spread' | 'Total'
  selection STRING,
  line FLOAT64,
  odds_american STRING
)
PARTITION BY DATE(pulled_at);

CREATE TABLE IF NOT EXISTS `${raw}.weather` (
  pulled_at TIMESTAMP,
  game_id STRING,
  temp_f FLOAT64,
  wind_mph FLOAT64,
  precip_prob FLOAT64,
  is_dome BOOL
)
PARTITION BY DATE(pulled_at);

-- RotoGuru one-time historical backfill (2014+), includes actual DK points.
CREATE TABLE IF NOT EXISTS `${raw}.dk_salaries_historical` (
  season INT64, week INT64,
  rotoguru_gid STRING,
  display_name STRING,
  position STRING,
  team_abbr STRING,
  home_away STRING,
  opponent STRING,
  dk_points FLOAT64,
  salary INT64
);
