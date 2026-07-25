-- Point-in-time rolling usage features. The cardinal rule: a row for
-- (player, season, week) contains only data from weeks strictly before
-- `week` — enforced by the `1 PRECEDING` upper window bound.
--
-- Small-sample smoothing: red zone counts shrink toward a positional prior
-- with weight PRIOR_K games (empirical-Bayes style; tuned on validation).
CREATE OR REPLACE TABLE `${features}.player_week_usage` AS
WITH position_map AS (
  SELECT gsis_id, season, ANY_VALUE(position HAVING MAX week) AS position
  FROM `${raw}.rosters_weekly`
  WHERE gsis_id IS NOT NULL
  GROUP BY gsis_id, season
),
snaps AS (
  SELECT i.gsis_id, n.season, n.week, n.offense_pct AS snap_share
  FROM `${raw}.snap_counts` n
  JOIN `${raw}.player_ids` i ON i.pfr_id = n.pfr_player_id
  WHERE i.gsis_id IS NOT NULL
),
usage AS (
  SELECT
    COALESCE(rec.gsis_id, rush.gsis_id) AS gsis_id,
    COALESCE(rec.season, rush.season)   AS season,
    COALESCE(rec.week, rush.week)       AS week,
    COALESCE(rec.team, rush.team)       AS team,
    COALESCE(rec.rz20_targets, 0)  AS rz20_targets,
    COALESCE(rec.rz10_targets, 0)  AS rz10_targets,
    COALESCE(rec.total_targets, 0) AS total_targets,
    rec.target_share,
    rec.air_yards_share,
    rec.rz20_target_share,
    rec.rz10_target_share,
    COALESCE(rush.rz20_carries, 0)  AS rz20_carries,
    COALESCE(rush.gl3_carries, 0)   AS gl3_carries,
    COALESCE(rush.total_carries, 0) AS total_carries,
    rush.carry_share,
    rush.gl3_carry_share
  FROM `${features}.rz_receiving` rec
  FULL OUTER JOIN `${features}.rz_rushing` rush
    USING (game_id, season, week, team, gsis_id)
),
-- Synthetic rows for each team's next unplayed game (player_week_role marks
-- them is_upcoming). All source metrics are NULL, so the strictly-prior
-- windows below naturally yield "as of now" rollups for the upcoming week —
-- the rows live inference needs and the training table (021) must exclude.
upcoming_rows AS (
  SELECT
    ro.gsis_id, ro.season, ro.week, ro.team,
    CAST(NULL AS INT64) AS rz20_targets,
    CAST(NULL AS INT64) AS rz10_targets,
    CAST(NULL AS INT64) AS total_targets,
    CAST(NULL AS FLOAT64) AS target_share,
    CAST(NULL AS FLOAT64) AS air_yards_share,
    CAST(NULL AS FLOAT64) AS rz20_target_share,
    CAST(NULL AS FLOAT64) AS rz10_target_share,
    CAST(NULL AS INT64) AS rz20_carries,
    CAST(NULL AS INT64) AS gl3_carries,
    CAST(NULL AS INT64) AS total_carries,
    CAST(NULL AS FLOAT64) AS carry_share,
    CAST(NULL AS FLOAT64) AS gl3_carry_share
  FROM `${features}.player_week_role` ro
  WHERE ro.is_upcoming
    AND NOT EXISTS (
      SELECT 1 FROM usage u2
      WHERE u2.gsis_id = ro.gsis_id AND u2.season = ro.season AND u2.week = ro.week
    )
),
usage_all AS (
  SELECT u.*, FALSE AS is_upcoming FROM usage u
  UNION ALL
  SELECT up.*, TRUE AS is_upcoming FROM upcoming_rows up
),
with_snaps AS (
  SELECT u.*, s.snap_share
  FROM usage_all u
  LEFT JOIN snaps s USING (gsis_id, season, week)
),
rolled AS (
  SELECT
    gsis_id, season, week, team, is_upcoming,

    -- Trailing 4-week averages, EXCLUDING current week (1 PRECEDING is key)
    AVG(rz20_targets)      OVER w4 AS rz20_targets_l4,
    AVG(rz10_targets)      OVER w4 AS rz10_targets_l4,
    AVG(total_targets)     OVER w4 AS targets_l4,
    AVG(target_share)      OVER w4 AS target_share_l4,
    AVG(air_yards_share)   OVER w4 AS air_yards_share_l4,
    AVG(rz20_target_share) OVER w4 AS rz20_target_share_l4,
    AVG(rz10_target_share) OVER w4 AS rz10_target_share_l4,
    AVG(rz20_carries)      OVER w4 AS rz20_carries_l4,
    AVG(gl3_carries)       OVER w4 AS gl3_carries_l4,
    AVG(total_carries)     OVER w4 AS carries_l4,
    AVG(carry_share)       OVER w4 AS carry_share_l4,
    AVG(gl3_carry_share)   OVER w4 AS gl3_carry_share_l4,
    AVG(snap_share)        OVER w4 AS snap_share_l4,

    -- Season-to-date, also excluding current
    AVG(rz20_targets)  OVER wstd AS rz20_targets_std,
    AVG(target_share)  OVER wstd AS target_share_std,
    AVG(total_targets) OVER wstd AS targets_std,
    AVG(total_carries) OVER wstd AS carries_std,
    SUM(rz20_targets)  OVER wstd AS rz20_targets_sum_prior,
    SUM(gl3_carries)   OVER wstd AS gl3_carries_sum_prior,

    -- Trend: recent form vs season baseline
    SAFE_DIVIDE(AVG(target_share) OVER w4, AVG(target_share) OVER wstd)
      AS target_share_trend,
    SAFE_DIVIDE(AVG(carry_share) OVER w4, AVG(carry_share) OVER wstd)
      AS carry_share_trend,

    COUNT(*) OVER wstd AS games_played_prior
  FROM with_snaps
  WINDOW
    w4   AS (PARTITION BY gsis_id, season ORDER BY week
             ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING),
    wstd AS (PARTITION BY gsis_id, season ORDER BY week
             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
),
-- League-wide per-position per-game priors for shrinkage. Stable enough
-- year to year that using the full history is fine.
position_priors AS (
  SELECT pm.position,
         AVG(u.rz20_targets) AS prior_rz20_per_game,
         AVG(u.gl3_carries)  AS prior_gl3_per_game
  FROM usage u
  JOIN position_map pm USING (gsis_id, season)
  GROUP BY pm.position
)
SELECT
  r.*,
  pm.position,
  1.5 * r.target_share_l4 + 0.7 * r.air_yards_share_l4 AS wopr_l4,
  SAFE_DIVIDE(
    r.rz20_targets_sum_prior + (${prior_k} * pp.prior_rz20_per_game),
    r.games_played_prior + ${prior_k}
  ) AS rz20_targets_smoothed,
  SAFE_DIVIDE(
    r.gl3_carries_sum_prior + (${prior_k} * pp.prior_gl3_per_game),
    r.games_played_prior + ${prior_k}
  ) AS gl3_carries_smoothed
FROM rolled r
LEFT JOIN position_map pm USING (gsis_id, season)
LEFT JOIN position_priors pp ON pp.position = pm.position;
