-- Actual contest ownership, imported from DraftKings contest-standings CSV
-- exports (see ingest/ownership_import.py). This is the training data the
-- field simulator's naive ownership proxy is waiting on: once a season of
-- rows accumulates, a regression (value, salary rank, team total -> owned%)
-- slots in behind backtest/field.py's `ownership` parameter.
CREATE TABLE IF NOT EXISTS `${raw}.contest_ownership` (
  imported_at TIMESTAMP,
  season INT64,
  week INT64,
  contest_id STRING,
  contest_name STRING,
  display_name STRING,          -- as DK prints it in the export
  roster_position STRING,       -- QB/RB/WR/TE/FLEX/DST
  pct_drafted FLOAT64,          -- 0-100
  fpts FLOAT64
)
PARTITION BY DATE(imported_at);
