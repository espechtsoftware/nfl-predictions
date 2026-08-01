-- QB NGS passing metrics (2026-08-01, candidate features): ngs_passing was
-- the audit's one fully-unused raw table. CPOE (completion % above
-- expectation) is the strongest public QB skill signal; time-to-throw
-- proxies protection/scheme. l6 strictly prior; NGS covers 2016+ and only
-- qualifying QBs (NaN elsewhere; build_X handles it). Gated behind
-- EXTRA_FEATURES like all candidates -- the 5-for-5 feature law applies.
CREATE OR REPLACE TABLE `${features}.qb_week_ngs` AS
SELECT
  player_gsis_id AS gsis_id, season, week,
  AVG(completion_percentage_above_expectation) OVER w AS qb_cpoe_l6,
  AVG(avg_time_to_throw) OVER w AS qb_time_to_throw_l6
FROM `${raw}.ngs_passing`
WHERE week > 0
WINDOW w AS (
  PARTITION BY player_gsis_id ORDER BY season, week
  ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
);
