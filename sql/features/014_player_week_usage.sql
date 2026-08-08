-- Point-in-time rolling usage on the DK salary universe. Every historical
-- salary-listed skill player gets a row, even if he recorded no target/carry.
-- Active no-opportunity weeks are zeros; listed inactive weeks are NULL so
-- they occupy calendar time without being mistaken for played games.
CREATE OR REPLACE TABLE `${features}.player_week_usage` AS
WITH position_map AS (
  SELECT gsis_id, season, ANY_VALUE(position HAVING MAX week) AS position
  FROM `${raw}.rosters_weekly`
  WHERE gsis_id IS NOT NULL
  GROUP BY gsis_id, season
),
snaps AS (
  SELECT i.gsis_id, CAST(n.season AS INT64) AS season,
         CAST(n.week AS INT64) AS week, n.offense_pct AS snap_share
  FROM `${raw}.snap_counts` n
  JOIN `${raw}.player_ids` i ON i.pfr_id = n.pfr_player_id
  WHERE i.gsis_id IS NOT NULL
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY i.gsis_id, CAST(n.season AS INT64), CAST(n.week AS INT64)
    ORDER BY n.offense_pct DESC
  ) = 1
),
joined AS (
  SELECT
    sal.gsis_id, sal.season, sal.week, sal.team, sal.position,
    rec.rz20_targets, rec.rz10_targets, rec.total_targets,
    rec.target_share, rec.air_yards_share,
    rec.rz20_target_share, rec.rz10_target_share,
    rush.rz20_carries, rush.gl3_carries, rush.total_carries,
    rush.carry_share, rush.gl3_carry_share,
    sn.snap_share,
    COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL AS is_active,
    COALESCE(ro.is_upcoming, FALSE) AS is_upcoming
  FROM `${features}.dk_salary_week` sal
  LEFT JOIN `${features}.rz_receiving` rec
    ON rec.gsis_id = sal.gsis_id AND rec.season = sal.season
   AND rec.week = sal.week
   AND CASE rec.team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                     WHEN 'STL' THEN 'LA' ELSE rec.team END = sal.team
  LEFT JOIN `${features}.rz_rushing` rush
    ON rush.gsis_id = sal.gsis_id AND rush.season = sal.season
   AND rush.week = sal.week
   AND CASE rush.team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                      WHEN 'STL' THEN 'LA' ELSE rush.team END = sal.team
  LEFT JOIN `${features}.player_week_actuals` a
    ON a.gsis_id = sal.gsis_id AND a.season = sal.season AND a.week = sal.week
  LEFT JOIN snaps sn
    ON sn.gsis_id = sal.gsis_id AND sn.season = sal.season AND sn.week = sal.week
  LEFT JOIN `${features}.player_week_role` ro
    ON ro.gsis_id = sal.gsis_id AND ro.season = sal.season AND ro.week = sal.week
  WHERE sal.position IN ('QB', 'RB', 'WR', 'TE')
),
usage AS (
  SELECT
    gsis_id, season, week, team, position, is_upcoming, is_active, snap_share,
    IF(is_active, COALESCE(rz20_targets, 0), NULL) AS rz20_targets,
    IF(is_active, COALESCE(rz10_targets, 0), NULL) AS rz10_targets,
    IF(is_active, COALESCE(total_targets, 0), NULL) AS total_targets,
    IF(is_active, COALESCE(target_share, 0), NULL) AS target_share,
    IF(is_active, COALESCE(air_yards_share, 0), NULL) AS air_yards_share,
    IF(is_active, COALESCE(rz20_target_share, 0), NULL) AS rz20_target_share,
    IF(is_active, COALESCE(rz10_target_share, 0), NULL) AS rz10_target_share,
    IF(is_active, COALESCE(rz20_carries, 0), NULL) AS rz20_carries,
    IF(is_active, COALESCE(gl3_carries, 0), NULL) AS gl3_carries,
    IF(is_active, COALESCE(total_carries, 0), NULL) AS total_carries,
    IF(is_active, COALESCE(carry_share, 0), NULL) AS carry_share,
    IF(is_active, COALESCE(gl3_carry_share, 0), NULL) AS gl3_carry_share
  FROM joined
),
-- Roster-synthetic upcoming rows retain debut players not yet present in a
-- salary snapshot. Live projections still begin with the DK salary file and
-- therefore cannot accidentally emit an unsalaried player.
upcoming_rows AS (
  SELECT
    ro.gsis_id, ro.season, ro.week, ro.team, ro.position,
    TRUE AS is_upcoming, FALSE AS is_active,
    CAST(NULL AS FLOAT64) AS snap_share,
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
      SELECT 1 FROM usage u
      WHERE u.gsis_id = ro.gsis_id AND u.season = ro.season AND u.week = ro.week
    )
),
usage_all AS (
  SELECT * FROM usage
  UNION ALL
  SELECT * FROM upcoming_rows
),
rolled AS (
  SELECT
    gsis_id, season, week, team, position, is_upcoming,
    is_active AS was_active,

    AVG(rz20_targets) OVER w4 AS rz20_targets_l4,
    AVG(rz10_targets) OVER w4 AS rz10_targets_l4,
    AVG(total_targets) OVER w4 AS targets_l4,
    AVG(target_share) OVER w4 AS target_share_l4,
    AVG(air_yards_share) OVER w4 AS air_yards_share_l4,
    AVG(rz20_target_share) OVER w4 AS rz20_target_share_l4,
    AVG(rz10_target_share) OVER w4 AS rz10_target_share_l4,
    AVG(rz20_carries) OVER w4 AS rz20_carries_l4,
    AVG(gl3_carries) OVER w4 AS gl3_carries_l4,
    AVG(total_carries) OVER w4 AS carries_l4,
    AVG(carry_share) OVER w4 AS carry_share_l4,
    AVG(gl3_carry_share) OVER w4 AS gl3_carry_share_l4,
    AVG(snap_share) OVER w4 AS snap_share_l4,

    LAST_VALUE(target_share IGNORE NULLS) OVER w4 AS target_share_last,
    LAST_VALUE(carry_share IGNORE NULLS) OVER w4 AS carry_share_last,
    LAST_VALUE(snap_share IGNORE NULLS) OVER w4 AS snap_share_last,
    SUM(target_share) OVER w4 AS target_share_sum_l4,
    SUM(carry_share) OVER w4 AS carry_share_sum_l4,
    SUM(snap_share) OVER w4 AS snap_share_sum_l4,
    COUNT(target_share) OVER w4 AS target_share_n_l4,
    COUNT(carry_share) OVER w4 AS carry_share_n_l4,
    COUNT(snap_share) OVER w4 AS snap_share_n_l4,

    AVG(rz20_targets) OVER wstd AS rz20_targets_std,
    AVG(target_share) OVER wstd AS target_share_std,
    AVG(total_targets) OVER wstd AS targets_std,
    AVG(total_carries) OVER wstd AS carries_std,
    SUM(rz20_targets) OVER wstd AS rz20_targets_sum_prior,
    SUM(gl3_carries) OVER wstd AS gl3_carries_sum_prior,
    SAFE_DIVIDE(AVG(target_share) OVER w4, AVG(target_share) OVER wstd)
      AS target_share_trend,
    SAFE_DIVIDE(AVG(carry_share) OVER w4, AVG(carry_share) OVER wstd)
      AS carry_share_trend,
    COUNTIF(is_active) OVER wstd AS games_played_prior
  FROM usage_all
  WINDOW
    w4 AS (PARTITION BY gsis_id, season ORDER BY week
           ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING),
    wstd AS (PARTITION BY gsis_id, season ORDER BY week
             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
),
position_priors AS (
  SELECT COALESCE(u.position, pm.position) AS position,
         AVG(u.rz20_targets) AS prior_rz20_per_game,
         AVG(u.gl3_carries) AS prior_gl3_per_game
  FROM usage u
  LEFT JOIN position_map pm USING (gsis_id, season)
  GROUP BY position
)
SELECT
  r.* EXCEPT(
    position,
    target_share_sum_l4, carry_share_sum_l4, snap_share_sum_l4,
    target_share_n_l4, carry_share_n_l4, snap_share_n_l4
  ),
  COALESCE(r.position, pm.position) AS position,
  CASE WHEN r.target_share_n_l4 >= 2 THEN
    r.target_share_last - SAFE_DIVIDE(
      r.target_share_sum_l4 - r.target_share_last, r.target_share_n_l4 - 1)
  END AS target_share_jump,
  CASE WHEN r.carry_share_n_l4 >= 2 THEN
    r.carry_share_last - SAFE_DIVIDE(
      r.carry_share_sum_l4 - r.carry_share_last, r.carry_share_n_l4 - 1)
  END AS carry_share_jump,
  CASE WHEN r.snap_share_n_l4 >= 2 THEN
    r.snap_share_last - SAFE_DIVIDE(
      r.snap_share_sum_l4 - r.snap_share_last, r.snap_share_n_l4 - 1)
  END AS snap_share_jump,
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
LEFT JOIN position_priors pp
  ON pp.position = COALESCE(r.position, pm.position);
