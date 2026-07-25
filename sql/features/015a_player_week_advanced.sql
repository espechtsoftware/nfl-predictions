-- Advanced target-quality and context metrics, strictly-prior windows.
--
-- Research-driven additions (see reports/2026-07-25-system-study.md and the
-- metric research that followed): TD *history* is the least stable fantasy
-- stat, so TD opportunity — end-zone and deep targets — is the better
-- input; air-yards-based target quality is the most predictive receiver
-- signal. NGS "over expected" metrics (RYOE/YACOE) were evaluated and
-- deliberately skipped: public research shows near-zero season-to-season
-- stability. Only two NGS features make the cut: separation (talent /
-- coverage-drawn proxy) and stacked-box rate (RB usage context).
--
-- Spine is player_week_usage, so upcoming-week synthetic rows (014) get
-- as-of-now values for live inference, same device as 015/016.
CREATE OR REPLACE TABLE `${features}.player_week_advanced` AS
WITH target_quality AS (
  -- Per player-game from pbp: end-zone targets (ball thrown to or past the
  -- goal line: air yards >= distance to goal) and deep targets (20+ air).
  SELECT
    receiver_player_id AS gsis_id,
    season, week,
    COUNTIF(air_yards >= yardline_100) AS ez_targets,
    COUNTIF(air_yards >= 20) AS deep_targets
  FROM `${raw}.pbp`
  WHERE pass_attempt = 1 AND receiver_player_id IS NOT NULL
    AND air_yards IS NOT NULL AND season_type = 'REG'
  GROUP BY 1, 2, 3
),
ngs_rec AS (
  SELECT player_gsis_id AS gsis_id, season, week, avg_separation
  FROM `${raw}.ngs_receiving`
  WHERE week > 0  -- week 0 rows are season aggregates
),
ngs_rush AS (
  SELECT player_gsis_id AS gsis_id, season, week,
         percent_attempts_gte_eight_defenders AS stacked_box_pct
  FROM `${raw}.ngs_rushing`
  WHERE week > 0
)
SELECT
  u.gsis_id, u.season, u.week,
  AVG(t.ez_targets)        OVER w4 AS ez_targets_l4,
  AVG(t.deep_targets)      OVER w4 AS deep_targets_l4,
  AVG(nr.avg_separation)   OVER w4 AS separation_l4,
  AVG(nu.stacked_box_pct)  OVER w4 AS stacked_box_l4
FROM `${features}.player_week_usage` u
LEFT JOIN target_quality t
  ON t.gsis_id = u.gsis_id AND t.season = u.season AND t.week = u.week
LEFT JOIN ngs_rec nr
  ON nr.gsis_id = u.gsis_id AND nr.season = u.season AND nr.week = u.week
LEFT JOIN ngs_rush nu
  ON nu.gsis_id = u.gsis_id AND nu.season = u.season AND nu.week = u.week
WINDOW w4 AS (PARTITION BY u.gsis_id, u.season ORDER BY u.week
              ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING);
