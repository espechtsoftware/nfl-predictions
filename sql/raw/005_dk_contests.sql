-- Overlay-detection scaffold (issue #13 item 4): append-only fill-rate
-- snapshots for DK contests tied to real NFL draft groups. Same
-- never-overwrite rationale as dk_salaries — how a contest's fill rate
-- moved toward lock is the signal, not just its final state.
CREATE TABLE IF NOT EXISTS `${raw}.dk_contest_fills` (
  pulled_at TIMESTAMP,        -- when YOU fetched it
  contest_id INT64,
  draft_group_id INT64,       -- matches dk_salaries.draft_group_id (or cfb_dk_salaries')
  sport STRING,                -- 'NFL' | 'CFB' (issue #13 item 7); NULL on pre-migration rows, treat as 'NFL'
  name STRING,
  game_type STRING,
  entry_fee FLOAT64,
  max_entries INT64,
  entries INT64,               -- entries gathered so far ("nt" in DK's payload)
  fill_rate FLOAT64,           -- entries / max_entries
  prize_pool FLOAT64,
  is_guaranteed BOOL,
  overlay_dollars FLOAT64,     -- max(prize_pool - entries*entry_fee, 0) when guaranteed, else 0
  start_time TIMESTAMP
)
PARTITION BY DATE(pulled_at)
CLUSTER BY draft_group_id, contest_id;

-- Migration: reuse this table for CFB contest polls (issue #13 item 7)
-- instead of a separate twin — same shape, one more discriminator column.
-- Does not touch the validated NFL ingest path; existing rows stay NULL.
ALTER TABLE `${raw}.dk_contest_fills`
  ADD COLUMN IF NOT EXISTS sport STRING;

-- NFL-only view: the safe default read path now that the table holds both
-- sports (CFB collection scheduled 2026-07-31). Future overlay-detection /
-- contest-analysis queries should read this, not the raw table, so CFB
-- Saturday contests can never silently blend into NFL overlay signals.
-- (sport IS NULL kept for pre-migration rows; the table was empty at
-- migration time, so in practice every row carries an explicit sport.)
CREATE OR REPLACE VIEW `${raw}.dk_contest_fills_nfl` AS
SELECT * FROM `${raw}.dk_contest_fills`
WHERE sport = 'NFL' OR sport IS NULL;
