-- CFB DFS collection-only scaffold (issue #13 item 7, added 2026-07-31,
-- owner request): DraftKings now runs college football DFS slates. These
-- mirror dk_salaries/dk_contest_fills structurally but are separate
-- (twin) tables rather than shared ones, so the validated NFL ingest path
-- and its schema stay untouched. Populated by `nfl-dfs ingest-cfb`,
-- gated behind INGEST_CFB_ENABLED (noop until opted in). Collection only:
-- no season/week resolution (no CFB schedule table exists to resolve
-- against), no features, no optimizer support.
CREATE TABLE IF NOT EXISTS `${raw}.cfb_dk_salaries` (
  pulled_at TIMESTAMP,          -- when YOU fetched it
  draft_group_id INT64,
  slate_type STRING,            -- 'classic' | 'showdown'
  dk_player_id INT64,
  dk_draftable_id INT64,        -- slate-specific ID DK's lineup upload wants
  dk_cpt_draftable_id INT64,    -- showdown only: the CPT-slot draftable ID
  display_name STRING,
  team_abbr STRING,
  position STRING,
  salary INT64,
  roster_slot STRING,
  game_start TIMESTAMP,
  status STRING,                -- 'None' | 'O' | 'Q' | 'D' ...
  dk_ppg FLOAT64                -- DK's own points-per-game figure when present
)
PARTITION BY DATE(pulled_at)
CLUSTER BY draft_group_id, dk_player_id;

-- Overlay-detection twin for CFB, same never-overwrite/free-EV rationale
-- as dk_contest_fills (see sql/raw/005_dk_contests.sql).
CREATE TABLE IF NOT EXISTS `${raw}.cfb_dk_contest_fills` (
  pulled_at TIMESTAMP,
  contest_id INT64,
  draft_group_id INT64,
  name STRING,
  game_type STRING,
  entry_fee FLOAT64,
  max_entries INT64,
  entries INT64,
  fill_rate FLOAT64,
  prize_pool FLOAT64,
  is_guaranteed BOOL,
  overlay_dollars FLOAT64,
  start_time TIMESTAMP
)
PARTITION BY DATE(pulled_at)
CLUSTER BY draft_group_id, contest_id;
