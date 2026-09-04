-- Quota telemetry and collection-only prop markets from The Odds API.
-- Neither table is read by the model, optimizer, API, or UI.  The shadow
-- feed is live-only: historical backfill is deliberately prohibited by the
-- ingestion command so spending and point-in-time provenance stay bounded.

CREATE TABLE IF NOT EXISTS `${raw}.odds_api_requests` (
  -- Modes remain NULLABLE to match load_dataframe's append/autodetect
  -- contract. The ingestion code always supplies these five identity fields.
  requested_at TIMESTAMP,
  request_kind STRING,
  endpoint STRING,                    -- path only; never query/API key
  historical BOOL,
  is_shadow BOOL,
  season INT64,
  week INT64,
  event_id STRING,
  markets STRING,
  bookmakers STRING,
  regions STRING,
  http_status INT64,
  requests_remaining INT64,
  requests_used INT64,
  requests_last INT64,
  response_event_count INT64,
  response_market_count INT64,
  response_market_keys STRING,
  error_type STRING
)
PARTITION BY DATE(requested_at)
CLUSTER BY request_kind, is_shadow, http_status;

CREATE TABLE IF NOT EXISTS `${raw}.prop_lines_shadow` (
  season INT64,
  week INT64,
  event_id STRING,
  commence_time TIMESTAMP,
  home_team STRING,
  away_team STRING,
  snapshot_ts STRING,
  bookmaker STRING,
  market STRING,
  outcome_name STRING,
  player STRING,
  price INT64,
  point FLOAT64,
  pulled_at TIMESTAMP
)
PARTITION BY DATE(pulled_at)
CLUSTER BY season, week, market, bookmaker;

-- Raw pick'em/DFS-platform observations from the provider's ``us_dfs``
-- region.  Capture does not license these fields for scoring or selection.
CREATE TABLE IF NOT EXISTS `${raw}.prop_lines_us_dfs` (
  season INT64,
  week INT64,
  event_id STRING,
  commence_time TIMESTAMP,
  home_team STRING,
  away_team STRING,
  snapshot_utc TIMESTAMP,
  platform STRING,
  platform_title STRING,
  platform_last_update TIMESTAMP,
  market STRING,
  market_last_update TIMESTAMP,
  outcome_name STRING,
  player_ref STRING,
  line FLOAT64,
  price FLOAT64,
  displayed_multiplier FLOAT64,
  pulled_at TIMESTAMP
)
PARTITION BY DATE(pulled_at)
CLUSTER BY season, week, market, platform;
