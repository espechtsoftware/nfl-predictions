-- Point-in-time RB roles (rb-matchup workstream, v1).
--
-- RESEARCH TABLE, outside the production build glob; executed by
-- scripts/build_receiver_matchup_features.py. Mirrors the frozen 017l
-- consensus law for running backs: within-team component percentiles from
-- strictly-prior CROSS-SEASON game windows plus the week-of pre-game depth
-- chart; at least two non-null components and two eligible teammates; ranks
-- RB1/RB2/RB3+ with depth then gsis tie-breaks.
--
-- Components: last-four carry share (player carries / team carries per
-- game), last-four target share (nflverse per-game share — the receiving
-- role that drives checkdown value), and current depth rank. Route share
-- is retained where the FantasyPoints weekly table supports RBs.

CREATE OR REPLACE TABLE `${features}.rb_week_role_pit` AS
WITH rb_games AS (
  SELECT
    w.player_id AS gsis_id,
    w.season,
    w.week,
    w.season_type,
    w.team,
    w.carries,
    SAFE_DIVIDE(
      w.carries,
      NULLIF(SUM(w.carries) OVER (
        PARTITION BY w.team, w.season, w.week
      ), 0)
    ) AS carry_share_game,
    w.target_share,
    ROW_NUMBER() OVER (
      PARTITION BY w.player_id ORDER BY w.season, w.week
    ) AS game_seq
  FROM `${raw}.weekly_stats` w
  WHERE w.position = 'RB'
    AND w.player_id IS NOT NULL
),
route_games AS (
  SELECT season, week, gsis_id, route_share
  FROM `${raw}.fantasy_points_route_share`
  WHERE gsis_id IS NOT NULL AND route_share IS NOT NULL
),
components AS (
  SELECT
    g.gsis_id,
    g.season,
    g.week,
    g.season_type,
    g.team,
    g.game_seq,
    AVG(g.carry_share_game) OVER prior_1 AS carry_share_l1,
    AVG(g.carry_share_game) OVER prior_4 AS carry_share_l4,
    AVG(g.target_share) OVER prior_4 AS target_share_l4,
    AVG(r.route_share) OVER prior_4 AS route_share_l4,
    COUNT(g.week) OVER prior_4 AS prior_game_count_l4,
    MAX(g.season * 100 + g.week) OVER prior_1 AS max_source_season_week
  FROM rb_games g
  LEFT JOIN route_games r
    ON r.gsis_id = g.gsis_id AND r.season = g.season AND r.week = g.week
  WINDOW
    prior_1 AS (
      PARTITION BY g.gsis_id ORDER BY g.game_seq
      ROWS BETWEEN 1 PRECEDING AND 1 PRECEDING
    ),
    prior_4 AS (
      PARTITION BY g.gsis_id ORDER BY g.game_seq
      ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    )
),
depth AS (
  SELECT
    gsis_id,
    season,
    week,
    MIN(SAFE_CAST(depth_team AS INT64)) AS depth_rank_current
  FROM `${raw}.depth_charts`
  WHERE gsis_id IS NOT NULL
    AND formation = 'Offense'
    AND position = 'RB'
  GROUP BY gsis_id, season, week
),
joined AS (
  SELECT c.*, d.depth_rank_current
  FROM components c
  LEFT JOIN depth d
    ON d.gsis_id = c.gsis_id AND d.season = c.season AND d.week = c.week
),
ranked AS (
  SELECT
    j.*,
    COUNT(*) OVER team_week AS eligible_teammate_count,
    IF(j.carry_share_l4 IS NULL, NULL,
       PERCENT_RANK() OVER (PARTITION BY j.team, j.season, j.week,
         (j.carry_share_l4 IS NULL)
         ORDER BY j.carry_share_l4)) AS carry_share_percentile,
    IF(j.target_share_l4 IS NULL, NULL,
       PERCENT_RANK() OVER (PARTITION BY j.team, j.season, j.week,
         (j.target_share_l4 IS NULL)
         ORDER BY j.target_share_l4)) AS target_share_percentile,
    IF(j.route_share_l4 IS NULL, NULL,
       PERCENT_RANK() OVER (PARTITION BY j.team, j.season, j.week,
         (j.route_share_l4 IS NULL)
         ORDER BY j.route_share_l4)) AS route_share_percentile,
    IF(j.depth_rank_current IS NULL, NULL,
       PERCENT_RANK() OVER (PARTITION BY j.team, j.season, j.week,
         (j.depth_rank_current IS NULL)
         ORDER BY j.depth_rank_current DESC)) AS depth_percentile
  FROM joined j
  WINDOW team_week AS (PARTITION BY j.team, j.season, j.week)
),
scored AS (
  SELECT
    r.*,
    (
      IF(r.carry_share_percentile IS NULL, 0, 1)
      + IF(r.target_share_percentile IS NULL, 0, 1)
      + IF(r.route_share_percentile IS NULL, 0, 1)
      + IF(r.depth_percentile IS NULL, 0, 1)
    ) AS role_component_count,
    (
      COALESCE(r.carry_share_percentile, 0)
      + COALESCE(r.target_share_percentile, 0)
      + COALESCE(r.route_share_percentile, 0)
      + COALESCE(r.depth_percentile, 0)
    ) / NULLIF(
      IF(r.carry_share_percentile IS NULL, 0, 1)
      + IF(r.target_share_percentile IS NULL, 0, 1)
      + IF(r.route_share_percentile IS NULL, 0, 1)
      + IF(r.depth_percentile IS NULL, 0, 1), 0
    ) AS role_consensus_score
  FROM ranked r
),
supported_ranked AS (
  SELECT
    s.*,
    (s.role_component_count >= 2 AND s.eligible_teammate_count >= 2)
      AS role_supported,
    IF(s.role_component_count >= 2 AND s.eligible_teammate_count >= 2,
       ROW_NUMBER() OVER (
         PARTITION BY s.team, s.season, s.week,
           (s.role_component_count >= 2 AND s.eligible_teammate_count >= 2)
         ORDER BY s.role_consensus_score DESC,
           s.depth_rank_current ASC NULLS LAST,
           s.gsis_id ASC
       ), NULL) AS role_rank_consensus
  FROM scored s
)
SELECT
  sr.gsis_id,
  sr.season,
  sr.week,
  sr.season_type,
  sr.team,
  sr.game_seq,
  sr.prior_game_count_l4,
  sr.max_source_season_week,
  sr.carry_share_l1,
  sr.carry_share_l4,
  sr.target_share_l4,
  sr.route_share_l4,
  sr.depth_rank_current,
  sr.carry_share_percentile,
  sr.target_share_percentile,
  sr.route_share_percentile,
  sr.depth_percentile,
  sr.role_component_count,
  sr.role_consensus_score,
  sr.eligible_teammate_count,
  sr.role_supported,
  CASE
    WHEN sr.role_component_count < 2 THEN 'below-support-threshold'
    WHEN sr.eligible_teammate_count < 2 THEN 'below-support-threshold'
    ELSE NULL
  END AS role_support_reason,
  sr.role_rank_consensus,
  CASE
    WHEN sr.role_rank_consensus IS NULL THEN NULL
    WHEN sr.role_rank_consensus = 1 THEN 'RB1'
    WHEN sr.role_rank_consensus = 2 THEN 'RB2'
    ELSE 'RB3+'
  END AS role_label
FROM supported_ranked sr
