-- Append-only log of every DK slate pull. Never overwrite: the history of
-- how a player's status changed before lock is itself a valuable feature.
CREATE TABLE IF NOT EXISTS `${raw}.dk_salaries` (
  pulled_at TIMESTAMP,          -- when YOU fetched it
  draft_group_id INT64,
  slate_type STRING,            -- 'classic' | 'showdown'
  season INT64, week INT64,
  dk_player_id INT64,
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
CLUSTER BY season, week, dk_player_id;
