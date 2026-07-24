CREATE TABLE IF NOT EXISTS `${predictions}.player_projections` (
  generated_at TIMESTAMP,
  model_version STRING,
  season INT64, week INT64, slate_id INT64,
  gsis_id STRING, dk_player_id INT64,
  display_name STRING, position STRING, team STRING, opponent STRING,
  salary INT64,
  proj_points FLOAT64,          -- mean
  proj_p10 FLOAT64,             -- 10th percentile
  proj_p50 FLOAT64,
  proj_p90 FLOAT64,             -- ceiling — what matters for GPP
  proj_std FLOAT64,
  p_20_plus FLOAT64,
  value FLOAT64,                -- proj_points / (salary/1000)
  proj_ownership FLOAT64        -- nullable until you have a source
)
PARTITION BY DATE(generated_at)
CLUSTER BY season, week;
