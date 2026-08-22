-- All-week player matchup annotations, all families (modeling feed, v1).
--
-- RESEARCH TABLE, outside the production build glob; executed by
-- scripts/build_receiver_matchup_features.py AFTER 017l..017q. This is the
-- SQL twin of the frozen per-slate annotation laws, materialized for EVERY
-- (season, week, player) so winners and the 420k-lineup realized corpus
-- join instantly by (season, week, gsis_id).
--
-- Universe note (documented deviation from the per-slate contract
-- objects): percentile populations here are the WEEKLY position group
-- (`universe = 'weekly-position-group'`), a superset of any one slate's
-- eligible players. The frozen component laws, edge mean, >=2-component
-- support, and the 0.75/0.40 easy law are identical. Analysis-grade
-- per-slate objects remain the contract path; this table is the bulk
-- modeling feed.
--
-- Families and their components (c1..c4, larger = offense-favorable):
--   receiver: c1 role concession (receiving DK/game to consensus role),
--             c2 alignment vulnerability (wide-share-weighted defender
--                DK/target by alignment), c3 top-two workload defender
--                quality for the dominant alignment, c4 shell fit;
--   rb:       c1 rushing concession to role, c2 checkdown receiving
--             concession to role, c3 run-defense EPA/attempt allowed;
--   qb:       c1 full-QB-DK concession, c2 NEGATED pressures per game,
--             c3 secondary yards/target allowed. `qb_depth1` carries the
--             starter gate where depth charts support it (through 2024).

CREATE OR REPLACE TABLE `${features}.player_matchup_week_pit` AS
WITH schedule_opponents AS (
  SELECT season, week, home_team AS team, away_team AS opponent
  FROM `${raw}.schedules`
  UNION ALL
  SELECT season, week, away_team AS team, home_team AS opponent
  FROM `${raw}.schedules`
),
defense_alignment AS (
  SELECT
    defense,
    season,
    week,
    alignment,
    SUM(defender_exposure_weight * dk_per_target_allowed_shrunk_l8)
      AS unit_dk_per_target,
    AVG(IF(workload_rank <= 2, dk_per_target_allowed_shrunk_l8, NULL))
      AS top2_dk_per_target
  FROM `${features}.defender_alignment_quality_week_pit`
  WHERE defender_supported
  GROUP BY defense, season, week, alignment
),
league_man AS (
  SELECT season, AVG(def_man_rate) AS league_man_rate
  FROM `${raw}.fantasy_points_defense_coverage_prior`
  GROUP BY season
),
-- Vendor tables can carry split_duplicate rows; collapse to one row per
-- key so joins never fan out.
fp_alignment AS (
  SELECT
    season,
    target_week,
    gsis_id,
    LOGICAL_OR(alignment_supported) AS alignment_supported,
    AVG(player_wide_share) AS player_wide_share
  FROM `${raw}.fantasy_points_alignment_player_l4`
  WHERE gsis_id IS NOT NULL
    AND COALESCE(split_duplicate, FALSE) = FALSE
  GROUP BY season, target_week, gsis_id
),
fp_shell AS (
  SELECT
    season,
    gsis_id,
    AVG(man_fprr) AS man_fprr,
    AVG(zone_fprr) AS zone_fprr
  FROM `${raw}.fantasy_points_receiver_coverage_prior`
  WHERE gsis_id IS NOT NULL
    AND COALESCE(split_duplicate, FALSE) = FALSE
  GROUP BY season, gsis_id
),
receiver_base AS (
  SELECT
    r.gsis_id,
    r.season,
    r.week,
    'receiver' AS family,
    r.position,
    r.team,
    so.opponent,
    r.role_label,
    r.role_supported,
    r.role_consensus_score,
    conc.receiving_dk_allowed_per_game_l8 AS c1_raw,
    CASE
      WHEN al.alignment_supported IS TRUE
        AND al.player_wide_share IS NOT NULL
        AND wide.unit_dk_per_target IS NOT NULL
        AND slot.unit_dk_per_target IS NOT NULL
      THEN al.player_wide_share * wide.unit_dk_per_target
           + (1 - al.player_wide_share) * slot.unit_dk_per_target
      ELSE NULL
    END AS c2_raw,
    CASE
      WHEN al.alignment_supported IS TRUE
        AND al.player_wide_share IS NOT NULL
      THEN IF(al.player_wide_share >= 0.5,
              wide.top2_dk_per_target, slot.top2_dk_per_target)
      ELSE NULL
    END AS c3_raw,
    CASE
      WHEN shell.man_fprr IS NOT NULL AND shell.zone_fprr IS NOT NULL
        AND shd.def_man_rate IS NOT NULL
        AND lm.league_man_rate IS NOT NULL
      THEN (shell.man_fprr - shell.zone_fprr)
           * (shd.def_man_rate - lm.league_man_rate)
      ELSE NULL
    END AS c4_raw,
    CAST(NULL AS BOOL) AS qb_depth1
  FROM `${features}.receiver_week_role_pit` r
  JOIN schedule_opponents so
    ON so.season = r.season AND so.week = r.week AND so.team = r.team
  LEFT JOIN `${features}.defense_receiver_role_concession_pit` conc
    ON conc.season = r.season AND conc.week = r.week
   AND conc.defense = so.opponent AND conc.role_label = r.role_label
   AND conc.concession_supported AND r.role_supported
  LEFT JOIN fp_alignment al
    ON al.season = r.season AND al.target_week = r.week
   AND al.gsis_id = r.gsis_id
  LEFT JOIN defense_alignment wide
    ON wide.season = r.season AND wide.week = r.week
   AND wide.defense = so.opponent AND wide.alignment = 'wide'
  LEFT JOIN defense_alignment slot
    ON slot.season = r.season AND slot.week = r.week
   AND slot.defense = so.opponent AND slot.alignment = 'slot'
  LEFT JOIN fp_shell shell
    ON shell.season = r.season AND shell.gsis_id = r.gsis_id
  LEFT JOIN `${raw}.fantasy_points_defense_coverage_prior` shd
    ON shd.season = r.season AND shd.team = so.opponent
  LEFT JOIN league_man lm ON lm.season = r.season
),
rb_base AS (
  SELECT
    r.gsis_id,
    r.season,
    r.week,
    'rb' AS family,
    'RB' AS position,
    r.team,
    so.opponent,
    r.role_label,
    r.role_supported,
    r.role_consensus_score,
    conc.rushing_dk_allowed_per_game_l8 AS c1_raw,
    conc.receiving_dk_allowed_per_game_l8 AS c2_raw,
    IF(ctx.run_context_supported, ctx.rdef_epa_per_attempt_l8, NULL)
      AS c3_raw,
    CAST(NULL AS FLOAT64) AS c4_raw,
    CAST(NULL AS BOOL) AS qb_depth1
  FROM `${features}.rb_week_role_pit` r
  JOIN schedule_opponents so
    ON so.season = r.season AND so.week = r.week AND so.team = r.team
  LEFT JOIN `${features}.defense_rb_role_concession_pit` conc
    ON conc.season = r.season AND conc.week = r.week
   AND conc.defense = so.opponent AND conc.role_label = r.role_label
   AND conc.concession_supported AND r.role_supported
  LEFT JOIN `${features}.team_defense_context_pit` ctx
    ON ctx.season = r.season AND ctx.week = r.week
   AND ctx.defense = so.opponent
),
qb_players AS (
  SELECT DISTINCT
    w.player_id AS gsis_id,
    w.season,
    w.week,
    w.team
  FROM `${raw}.weekly_stats` w
  WHERE w.position = 'QB' AND w.player_id IS NOT NULL
),
qb_depth AS (
  SELECT gsis_id, season, week, MIN(SAFE_CAST(depth_team AS INT64)) AS qb_depth_rank
  FROM `${raw}.depth_charts`
  WHERE gsis_id IS NOT NULL AND formation = 'Offense' AND position = 'QB'
  GROUP BY gsis_id, season, week
),
qb_base AS (
  SELECT
    q.gsis_id,
    q.season,
    q.week,
    'qb' AS family,
    'QB' AS position,
    q.team,
    so.opponent,
    CAST(NULL AS STRING) AS role_label,
    CAST(NULL AS BOOL) AS role_supported,
    CAST(NULL AS FLOAT64) AS role_consensus_score,
    IF(ctx.qb_concession_supported, ctx.qb_dk_allowed_per_game_l8, NULL)
      AS c1_raw,
    IF(ctx.pass_rush_supported, -ctx.pressures_per_game_l8, NULL)
      AS c2_raw,
    cov.db_ypt_allowed_l6 AS c3_raw,
    CAST(NULL AS FLOAT64) AS c4_raw,
    (qd.qb_depth_rank = 1) AS qb_depth1
  FROM qb_players q
  JOIN schedule_opponents so
    ON so.season = q.season AND so.week = q.week AND so.team = q.team
  LEFT JOIN `${features}.team_defense_context_pit` ctx
    ON ctx.season = q.season AND ctx.week = q.week
   AND ctx.defense = so.opponent
  LEFT JOIN `${features}.defense_week_coverage` cov
    ON cov.season = q.season AND cov.week = q.week
   AND cov.team = so.opponent
  LEFT JOIN qb_depth qd
    ON qd.gsis_id = q.gsis_id AND qd.season = q.season AND qd.week = q.week
),
unioned AS (
  SELECT * FROM receiver_base
  UNION ALL SELECT * FROM rb_base
  UNION ALL SELECT * FROM qb_base
),
ranked AS (
  SELECT
    u.*,
    IF(u.c1_raw IS NULL, NULL,
       PERCENT_RANK() OVER (PARTITION BY u.season, u.week, u.family,
         (u.c1_raw IS NULL) ORDER BY u.c1_raw)) AS c1_pct,
    IF(u.c2_raw IS NULL, NULL,
       PERCENT_RANK() OVER (PARTITION BY u.season, u.week, u.family,
         (u.c2_raw IS NULL) ORDER BY u.c2_raw)) AS c2_pct,
    IF(u.c3_raw IS NULL, NULL,
       PERCENT_RANK() OVER (PARTITION BY u.season, u.week, u.family,
         (u.c3_raw IS NULL) ORDER BY u.c3_raw)) AS c3_pct,
    IF(u.c4_raw IS NULL, NULL,
       PERCENT_RANK() OVER (PARTITION BY u.season, u.week, u.family,
         (u.c4_raw IS NULL) ORDER BY u.c4_raw)) AS c4_pct
  FROM unioned u
)
SELECT
  r.*,
  'weekly-position-group' AS universe,
  (
    IF(r.c1_pct IS NULL, 0, 1) + IF(r.c2_pct IS NULL, 0, 1)
    + IF(r.c3_pct IS NULL, 0, 1) + IF(r.c4_pct IS NULL, 0, 1)
  ) AS component_count,
  (
    COALESCE(r.c1_pct, 0) + COALESCE(r.c2_pct, 0)
    + COALESCE(r.c3_pct, 0) + COALESCE(r.c4_pct, 0)
  ) / NULLIF(
    IF(r.c1_pct IS NULL, 0, 1) + IF(r.c2_pct IS NULL, 0, 1)
    + IF(r.c3_pct IS NULL, 0, 1) + IF(r.c4_pct IS NULL, 0, 1), 0
  ) AS matchup_edge_score,
  CASE
    WHEN (
      IF(r.c1_pct IS NULL, 0, 1) + IF(r.c2_pct IS NULL, 0, 1)
      + IF(r.c3_pct IS NULL, 0, 1) + IF(r.c4_pct IS NULL, 0, 1)
    ) < 2 THEN NULL
    ELSE (
      (
        COALESCE(r.c1_pct, 0) + COALESCE(r.c2_pct, 0)
        + COALESCE(r.c3_pct, 0) + COALESCE(r.c4_pct, 0)
      ) / (
        IF(r.c1_pct IS NULL, 0, 1) + IF(r.c2_pct IS NULL, 0, 1)
        + IF(r.c3_pct IS NULL, 0, 1) + IF(r.c4_pct IS NULL, 0, 1)
      ) >= 0.75
      AND LEAST(
        COALESCE(r.c1_pct, 1), COALESCE(r.c2_pct, 1),
        COALESCE(r.c3_pct, 1), COALESCE(r.c4_pct, 1)
      ) >= 0.40
    )
  END AS easy_matchup
FROM ranked r
