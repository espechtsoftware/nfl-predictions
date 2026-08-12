-- Point-in-time efficiency (rate) features: trailing windows on realized
-- efficiency, all excluding the current week.
CREATE OR REPLACE TABLE `${features}.player_week_efficiency` AS
WITH per_game AS (
  SELECT
    a.gsis_id, a.season, a.week,
    SAFE_DIVIDE(a.rec_yards, NULLIF(a.targets, 0))    AS yards_per_target,
    SAFE_DIVIDE(a.rec_yards, NULLIF(a.receptions, 0)) AS yards_per_reception,
    SAFE_DIVIDE(a.receptions, NULLIF(a.targets, 0))   AS catch_rate,
    SAFE_DIVIDE(a.rush_yards, NULLIF(a.carries, 0))   AS yards_per_carry,
    SAFE_DIVIDE(a.pass_yards, NULLIF(a.pass_attempts, 0)) AS yards_per_attempt,
    -- A salary-listed inactive needs a zero label for honest replay scoring,
    -- but it is not a played game and must not depress rolling production.
    IF(a.has_stat_line, a.dk_points, NULL) AS dk_points
  FROM `${features}.player_week_actuals` a
),
-- Synthetic rows for each team's next unplayed game (same device as 014):
-- NULL metrics, so the strictly-prior windows emit as-of-now values on the
-- upcoming week's row for live inference.
per_game_all AS (
  SELECT * FROM per_game
  UNION ALL
  SELECT
    ro.gsis_id, ro.season, ro.week,
    CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64),
    CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64)
  FROM `${features}.player_week_role` ro
  WHERE ro.is_upcoming
    AND NOT EXISTS (
      SELECT 1 FROM per_game g2
      WHERE g2.gsis_id = ro.gsis_id AND g2.season = ro.season AND g2.week = ro.week
    )
),
adot AS (
  SELECT
    receiver_player_id AS gsis_id, season, week,
    AVG(air_yards) AS adot
  FROM `${raw}.pbp`
  WHERE pass_attempt = 1 AND receiver_player_id IS NOT NULL
  GROUP BY 1, 2, 3
)
SELECT
  g.gsis_id, g.season, g.week,
  AVG(g.yards_per_target)    OVER w8 AS yards_per_target_l8,
  AVG(g.yards_per_reception) OVER w8 AS yards_per_reception_l8,
  AVG(g.catch_rate)          OVER w8 AS catch_rate_l8,
  AVG(g.yards_per_carry)     OVER w8 AS yards_per_carry_l8,
  AVG(g.yards_per_attempt)   OVER w8 AS yards_per_attempt_l8,
  AVG(g.dk_points)           OVER w4 AS dk_points_l4,
  AVG(g.dk_points)           OVER wstd AS dk_points_std,
  STDDEV(g.dk_points)        OVER wstd AS dk_points_vol,
  AVG(ad.adot)               OVER w8 AS adot_l8
FROM per_game_all g
LEFT JOIN adot ad USING (gsis_id, season, week)
WINDOW
  w4   AS (PARTITION BY g.gsis_id, g.season ORDER BY g.week
           ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING),
  w8   AS (PARTITION BY g.gsis_id, g.season ORDER BY g.week
           ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING),
  wstd AS (PARTITION BY g.gsis_id, g.season ORDER BY g.week
           ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING);
