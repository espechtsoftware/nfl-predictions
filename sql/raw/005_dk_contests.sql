-- Overlay-detection scaffold (issue #13 item 4): append-only fill-rate
-- snapshots for DK contests tied to real NFL draft groups. Same
-- never-overwrite rationale as dk_salaries — how a contest's fill rate
-- moved toward lock is the signal, not just its final state.
CREATE TABLE IF NOT EXISTS `${raw}.dk_contest_fills` (
  pulled_at TIMESTAMP,        -- when YOU fetched it
  contest_id INT64,
  draft_group_id INT64,       -- matches dk_salaries.draft_group_id
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
