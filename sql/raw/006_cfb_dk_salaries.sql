-- CFB (college football) DK slate/salary snapshot, issue #13 item 7 (owner
-- request 2026-07-31): DK now runs college football DFS (QB/2RB/3WR/FLEX/
-- Superflex, 8 slots). Collection-only scaffold so the 2026 CFB season
-- yields a backtestable dataset for a 2027 go/no-go decision — no models,
-- features, or optimizer work reads this table yet.
--
-- Deliberately a separate table from `dk_salaries`, not a `sport` column on
-- it: same shape, but this must never touch the validated NFL ingest path,
-- and CFB rosters differ (QB/RB/WR/FLEX/Superflex, not DK NFL Classic's
-- QB/RB/RB/WR/WR/WR/TE/FLEX/DST) so keeping the tables distinct avoids an
-- implicit schema contract across two different games. `dk_contest_fills`
-- (005) is reused with a `sport` column instead, since contest fill-rate
-- rows carry no roster-shape assumptions.
CREATE TABLE IF NOT EXISTS `${raw}.cfb_dk_salaries` (
  pulled_at TIMESTAMP,          -- when YOU fetched it
  draft_group_id INT64,
  slate_type STRING,            -- 'classic' | 'showdown'
  season INT64, week INT64,     -- week left NULL for now, same as dk_salaries (see ingest/dk_job.py)
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
-- draft_group_id, not season/week: week is always NULL here (see above) and
-- draft_group_id is the natural access path, matching dk_salaries' key.
CLUSTER BY draft_group_id, dk_player_id;
