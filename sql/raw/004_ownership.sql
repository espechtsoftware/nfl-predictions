-- Actual contest ownership, imported from DraftKings contest-standings CSV
-- exports (see ingest/ownership_import.py). This is the training data the
-- field simulator's naive ownership proxy is waiting on: once a season of
-- rows accumulates, a regression (value, salary rank, team total -> owned%)
-- slots in behind backtest/field.py's `ownership` parameter.
CREATE TABLE IF NOT EXISTS `${raw}.contest_ownership` (
  imported_at TIMESTAMP,
  captured_at TIMESTAMP,
  evidence_timing STRING,       -- always post_settlement for full-field captures
  capture_version STRING,
  capture_id STRING,            -- exact source + contest identity
  import_id STRING,             -- legacy-compatible alias of capture_id
  season INT64,
  week INT64,
  contest_id STRING,
  contest_name STRING,
  expected_entries INT64,
  source_sha256 STRING,
  source_bytes INT64,
  source_uri STRING,            -- immutable create-only raw CSV archive
  display_name STRING,          -- as DK prints it in the export
  roster_position STRING,       -- QB/RB/WR/TE/FLEX/DST
  pct_drafted FLOAT64,          -- 0-100
  fpts FLOAT64
)
PARTITION BY DATE(imported_at);

-- Keep one-time setup idempotent for projects whose ownership table predates
-- the complete-field capture contract.
ALTER TABLE `${raw}.contest_ownership`
  ADD COLUMN IF NOT EXISTS captured_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS evidence_timing STRING,
  ADD COLUMN IF NOT EXISTS capture_version STRING,
  ADD COLUMN IF NOT EXISTS capture_id STRING,
  ADD COLUMN IF NOT EXISTS import_id STRING,
  ADD COLUMN IF NOT EXISTS expected_entries INT64,
  ADD COLUMN IF NOT EXISTS source_sha256 STRING,
  ADD COLUMN IF NOT EXISTS source_bytes INT64,
  ADD COLUMN IF NOT EXISTS source_uri STRING;

-- Full settled field: raw roster string plus parsed slot order, canonical
-- duplicate identity and optional payout evidence.  No feature/model query is
-- allowed to treat these post-settlement rows as same-week PIT input.
CREATE TABLE IF NOT EXISTS `${raw}.contest_entries` (
  imported_at TIMESTAMP,
  captured_at TIMESTAMP,
  evidence_timing STRING,
  capture_version STRING,
  capture_id STRING,
  import_id STRING,
  season INT64,
  week INT64,
  contest_id STRING,
  contest_name STRING,
  expected_entries INT64,
  source_sha256 STRING,
  source_bytes INT64,
  source_uri STRING,
  rank INT64,
  entry_id STRING,
  entry_name STRING,
  points FLOAT64,
  time_remaining_raw STRING,
  payout FLOAT64,
  payout_raw STRING,
  lineup STRING,
  roster_format STRING,
  lineup_slots_json STRING,
  n_players INT64,
  players_key STRING,           -- legacy name-set key (Classic-compatible)
  duplicate_key STRING,         -- captain-aware for Showdown
  lineup_sha256 STRING,
  is_top20 BOOL
)
PARTITION BY DATE(imported_at)
CLUSTER BY season, week, contest_id;

ALTER TABLE `${raw}.contest_entries`
  ADD COLUMN IF NOT EXISTS captured_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS evidence_timing STRING,
  ADD COLUMN IF NOT EXISTS capture_version STRING,
  ADD COLUMN IF NOT EXISTS capture_id STRING,
  ADD COLUMN IF NOT EXISTS import_id STRING,
  ADD COLUMN IF NOT EXISTS contest_name STRING,
  ADD COLUMN IF NOT EXISTS expected_entries INT64,
  ADD COLUMN IF NOT EXISTS source_sha256 STRING,
  ADD COLUMN IF NOT EXISTS source_bytes INT64,
  ADD COLUMN IF NOT EXISTS source_uri STRING,
  ADD COLUMN IF NOT EXISTS time_remaining_raw STRING,
  ADD COLUMN IF NOT EXISTS payout FLOAT64,
  ADD COLUMN IF NOT EXISTS payout_raw STRING,
  ADD COLUMN IF NOT EXISTS roster_format STRING,
  ADD COLUMN IF NOT EXISTS lineup_slots_json STRING,
  ADD COLUMN IF NOT EXISTS n_players INT64,
  ADD COLUMN IF NOT EXISTS duplicate_key STRING,
  ADD COLUMN IF NOT EXISTS lineup_sha256 STRING,
  ADD COLUMN IF NOT EXISTS is_top20 BOOL;
