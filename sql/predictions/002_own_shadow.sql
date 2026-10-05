CREATE TABLE IF NOT EXISTS `${predictions}.own_shadow` (
  generated_at TIMESTAMP,
  season INT64,
  week INT64,
  gsis_id STRING,
  name STRING,
  pos STRING,
  salary INT64,
  n_pool INT64,
  pred_own FLOAT64,
  source STRING,
  booster_own FLOAT64,
  -- 2026-10-05: who built this vector (nfl_dfs.inference.own_shadow). NULL =
  -- a row written before the column existed (legacy). Readers select ONE
  -- writer; never "the latest row of the week".
  writer STRING,
  run_type STRING
)
PARTITION BY DATE(generated_at)
CLUSTER BY season, week;
