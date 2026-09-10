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
  booster_own FLOAT64
)
PARTITION BY DATE(generated_at)
CLUSTER BY season, week;
