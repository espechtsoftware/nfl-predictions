-- Research/UI table: DK points allowed per defense per position per week
-- (the fantasy.nfl.com "points against" view), raw and with rolling windows.
--
-- NOTE: unlike every model feature table, the rolling columns here INCLUDE
-- the current week — this is a rear-view research table for the app's
-- defense page, never a model input. Models use defense_week_allowed,
-- whose windows end at 1 PRECEDING.
CREATE OR REPLACE TABLE `${features}.defense_points_against` AS
WITH pm AS (
  -- Deliberately resolve completed historical rows to their final recorded
  -- season position. This table is rear-view UI only and never a model input.
  SELECT gsis_id, season, ANY_VALUE(position HAVING MAX week) AS position
  FROM `${raw}.rosters_weekly`
  WHERE gsis_id IS NOT NULL
  GROUP BY gsis_id, season
),
pos_allowed AS (
  SELECT
    s.opponent AS team,            -- the defense
    a.season, a.week, pm.position,
    SUM(a.dk_points) AS fp_allowed
  FROM `${features}.player_week_actuals` a
  JOIN `${features}.schedule_long` s
    ON s.team = a.team AND s.season = a.season AND s.week = a.week
  JOIN pm ON pm.gsis_id = a.gsis_id AND pm.season = a.season
  WHERE pm.position IN ('QB', 'RB', 'WR', 'TE')
  GROUP BY 1, 2, 3, 4
)
SELECT
  team, season, week, position, fp_allowed,
  AVG(fp_allowed) OVER w3 AS fp_allowed_l3,
  AVG(fp_allowed) OVER w6 AS fp_allowed_l6,
  AVG(fp_allowed) OVER wseason AS fp_allowed_season,
  -- Positive = allowing more than its season norm lately (defense fading);
  -- negative = clamping down (defense improving).
  AVG(fp_allowed) OVER w3 - AVG(fp_allowed) OVER wseason AS trend
FROM pos_allowed
WINDOW
  w3      AS (PARTITION BY team, season, position ORDER BY week
              ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),
  w6      AS (PARTITION BY team, season, position ORDER BY week
              ROWS BETWEEN 5 PRECEDING AND CURRENT ROW),
  wseason AS (PARTITION BY team, season, position ORDER BY week
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW);
