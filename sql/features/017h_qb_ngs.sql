-- QB NGS passing metrics (2026-08-01, candidate features): ngs_passing was
-- the audit's one fully-unused raw table. CPOE (completion % above
-- expectation) is the strongest public QB skill signal; time-to-throw
-- proxies protection/scheme. l6 strictly prior; NGS covers 2016+ and only
-- qualifying QBs (NaN elsewhere; build_X handles it). Gated behind
-- EXTRA_FEATURES like all candidates -- the 5-for-5 feature law applies.
CREATE OR REPLACE TABLE `${features}.qb_week_ngs` AS
WITH observations AS (
  SELECT
    player_gsis_id AS gsis_id, season, week,
    completion_percentage_above_expectation AS cpoe,
    avg_time_to_throw AS time_to_throw
  FROM `${raw}.ngs_passing`
  WHERE week > 0
),
-- Append only the live target row. Using the entire roster-week spine would
-- change ROWS-window semantics for historical backups; a single null row
-- preserves every replay value and carries the last six qualifying NGS games
-- into the upcoming inference week.
with_upcoming AS (
  SELECT gsis_id, season, week, cpoe, time_to_throw
  FROM observations
  UNION ALL
  SELECT DISTINCT
    ro.gsis_id, ro.season, ro.week,
    CAST(NULL AS FLOAT64) AS cpoe,
    CAST(NULL AS FLOAT64) AS time_to_throw
  FROM `${features}.player_week_role` ro
  WHERE ro.is_upcoming
    AND ro.position = 'QB'
    AND NOT EXISTS (
      SELECT 1 FROM observations prior
      WHERE prior.gsis_id = ro.gsis_id
        AND prior.season = ro.season
        AND prior.week = ro.week
    )
)
SELECT
  gsis_id, season, week,
  AVG(cpoe) OVER w AS qb_cpoe_l6,
  AVG(time_to_throw) OVER w AS qb_time_to_throw_l6
FROM with_upcoming
WINDOW w AS (
  PARTITION BY gsis_id ORDER BY season, week
  ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
);
