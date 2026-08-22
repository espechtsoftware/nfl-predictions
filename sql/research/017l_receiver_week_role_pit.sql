-- Point-in-time receiver roles (matchup plan §5.1, P1 v1).
--
-- RESEARCH TABLE: lives under sql/research/ deliberately — the production
-- build glob executes only sql/features/*.sql, and this table must not join
-- the nightly build until the annotation layer graduates (P3+). Executed by
-- scripts/build_receiver_matchup_features.py (default-off, --execute gated).
--
-- One row per (season, week, gsis_id) for every WR/TE player-week that
-- appears in `${raw}.weekly_stats` (played weeks; the broader roster/salary
-- universe is applied at annotation-join time and flagged there — plan
-- §5.1's "name the universe used" clause). A player's role for week W is
-- derived ONLY from games strictly before W in cross-season game order plus
-- the week-W pre-game depth chart, which is published before kickoff.
--
-- Frozen v1 consensus law (plan §5.1): within each team/week/position
-- group, convert each available last-four component (target share, route
-- share, air-yards share) to a within-team percentile, invert current depth
-- rank, average the available component percentiles, require at least two
-- non-null components and at least two eligible teammates, rank descending
-- with depth-rank-ascending then gsis-id tie-breaks. Salary tie-breaks are
-- deferred to the annotation join. Sensitivity ranks (target-only,
-- route-only, depth-only) are retained beside the consensus.
--
-- Known nulls carried with reasons downstream: depth_charts ends at 2024
-- (2025 depth components are null); route share begins in 2022.

CREATE OR REPLACE TABLE `${features}.receiver_week_role_pit` AS
WITH receiver_games AS (
  SELECT
    player_id AS gsis_id,
    season,
    week,
    season_type,
    team,
    position,
    targets,
    target_share,
    air_yards_share,
    -- Global cross-season game ordinal per player: season boundaries do
    -- not reset the as-of window (plan law; unlike season-partitioned
    -- production features).
    ROW_NUMBER() OVER (
      PARTITION BY player_id ORDER BY season, week
    ) AS game_seq
  FROM `${raw}.weekly_stats`
  WHERE position IN ('WR', 'TE')
    AND player_id IS NOT NULL
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
    g.position,
    g.game_seq,
    -- Strictly prior windows in cross-season game order.
    AVG(g.target_share) OVER prior_1 AS target_share_l1,
    AVG(g.target_share) OVER prior_4 AS target_share_l4,
    AVG(g.air_yards_share) OVER prior_4 AS air_yards_share_l4,
    AVG(r.route_share) OVER prior_1 AS route_share_l1,
    AVG(r.route_share) OVER prior_4 AS route_share_l4,
    COUNT(g.week) OVER prior_4 AS prior_game_count_l4,
    MAX(g.season * 100 + g.week) OVER prior_1 AS max_source_season_week
  FROM receiver_games g
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
-- Week-W depth chart is pre-game information: the minimum offensive depth
-- slot for the player that week. Lower is better.
depth AS (
  SELECT
    gsis_id,
    season,
    week,
    MIN(depth_team) AS depth_rank_current
  FROM `${raw}.depth_charts`
  WHERE gsis_id IS NOT NULL
    AND formation = 'Offense'
    AND position IN ('WR', 'TE')
  GROUP BY gsis_id, season, week
),
joined AS (
  SELECT
    c.*,
    d.depth_rank_current
  FROM components c
  LEFT JOIN depth d
    ON d.gsis_id = c.gsis_id AND d.season = c.season AND d.week = c.week
),
-- Within-team, within-week, within-position-group percentiles among
-- eligible receivers, computed only over non-null component values and
-- oriented so larger means a larger expected role.
ranked AS (
  SELECT
    j.*,
    COUNT(*) OVER team_week AS eligible_teammate_count,
    IF(j.target_share_l4 IS NULL, NULL,
       PERCENT_RANK() OVER (PARTITION BY j.team, j.season, j.week,
         j.position, (j.target_share_l4 IS NULL)
         ORDER BY j.target_share_l4)) AS target_share_percentile,
    IF(j.route_share_l4 IS NULL, NULL,
       PERCENT_RANK() OVER (PARTITION BY j.team, j.season, j.week,
         j.position, (j.route_share_l4 IS NULL)
         ORDER BY j.route_share_l4)) AS route_share_percentile,
    IF(j.air_yards_share_l4 IS NULL, NULL,
       PERCENT_RANK() OVER (PARTITION BY j.team, j.season, j.week,
         j.position, (j.air_yards_share_l4 IS NULL)
         ORDER BY j.air_yards_share_l4)) AS air_yards_percentile,
    IF(j.depth_rank_current IS NULL, NULL,
       PERCENT_RANK() OVER (PARTITION BY j.team, j.season, j.week,
         j.position, (j.depth_rank_current IS NULL)
         ORDER BY j.depth_rank_current DESC)) AS depth_percentile
  FROM joined j
  WINDOW team_week AS (PARTITION BY j.team, j.season, j.week, j.position)
),
scored AS (
  SELECT
    r.*,
    (
      IF(r.target_share_percentile IS NULL, 0, 1)
      + IF(r.route_share_percentile IS NULL, 0, 1)
      + IF(r.air_yards_percentile IS NULL, 0, 1)
      + IF(r.depth_percentile IS NULL, 0, 1)
    ) AS role_component_count,
    (
      COALESCE(r.target_share_percentile, 0)
      + COALESCE(r.route_share_percentile, 0)
      + COALESCE(r.air_yards_percentile, 0)
      + COALESCE(r.depth_percentile, 0)
    ) / NULLIF(
      IF(r.target_share_percentile IS NULL, 0, 1)
      + IF(r.route_share_percentile IS NULL, 0, 1)
      + IF(r.air_yards_percentile IS NULL, 0, 1)
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
         PARTITION BY s.team, s.season, s.week, s.position,
           (s.role_component_count >= 2 AND s.eligible_teammate_count >= 2)
         ORDER BY s.role_consensus_score DESC,
           s.depth_rank_current ASC NULLS LAST,
           s.gsis_id ASC
       ), NULL) AS role_rank_consensus,
    IF(s.target_share_l4 IS NULL, NULL,
       ROW_NUMBER() OVER (
         PARTITION BY s.team, s.season, s.week, s.position,
           (s.target_share_l4 IS NULL)
         ORDER BY s.target_share_l4 DESC, s.gsis_id ASC
       )) AS role_rank_target_only,
    IF(s.route_share_l4 IS NULL, NULL,
       ROW_NUMBER() OVER (
         PARTITION BY s.team, s.season, s.week, s.position,
           (s.route_share_l4 IS NULL)
         ORDER BY s.route_share_l4 DESC, s.gsis_id ASC
       )) AS role_rank_route_only,
    IF(s.depth_rank_current IS NULL, NULL,
       ROW_NUMBER() OVER (
         PARTITION BY s.team, s.season, s.week, s.position,
           (s.depth_rank_current IS NULL)
         ORDER BY s.depth_rank_current ASC, s.gsis_id ASC
       )) AS role_rank_depth_only
  FROM scored s
)
SELECT
  sr.gsis_id,
  sr.season,
  sr.week,
  sr.season_type,
  sr.team,
  sr.position,
  sr.game_seq,
  sr.prior_game_count_l4,
  sr.max_source_season_week,
  sr.target_share_l1,
  sr.target_share_l4,
  sr.route_share_l1,
  sr.route_share_l4,
  sr.air_yards_share_l4,
  sr.depth_rank_current,
  sr.target_share_percentile,
  sr.route_share_percentile,
  sr.air_yards_percentile,
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
    WHEN sr.position = 'WR' AND sr.role_rank_consensus = 1 THEN 'WR1'
    WHEN sr.position = 'WR' AND sr.role_rank_consensus = 2 THEN 'WR2'
    WHEN sr.position = 'WR' THEN 'WR3+'
    WHEN sr.role_rank_consensus = 1 THEN 'TE1'
    ELSE 'TE2+'
  END AS role_label,
  sr.role_rank_target_only,
  sr.role_rank_route_only,
  sr.role_rank_depth_only
FROM supported_ranked sr
