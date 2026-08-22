-- Defense concessions to point-in-time receiver roles (plan §5.2, P1 v1).
--
-- RESEARCH TABLE: outside the production build glob on purpose; executed by
-- scripts/build_receiver_matchup_features.py after 017l (it reads
-- `${features}.receiver_week_role_pit`).
--
-- Directly implements "the opponent gives up points to WR1s": every source
-- receiver-game line is attributed to the defense it faced under the
-- receiver's PRE-GAME consensus role (017l week-W roles use only strictly
-- prior games plus the week-W pre-game depth chart). Target-week rows
-- aggregate the defense's last eight (and four) completed games STRICTLY
-- prior in cross-season order over a defense-game spine, so a game where no
-- supported WR1 faced the defense contributes zeros rather than being
-- skipped.
--
-- Frozen v1 shrinkage law: per-target efficiency rates shrink toward the
-- league's cumulative same-role rate over all games strictly prior to the
-- target week, with a fixed pseudo-count of 32 targets. Raw numerators and
-- denominators are retained beside every shrunk value.
--
-- The plan's `*_over_expectation` adjusted views require receipted frozen
-- historical projections and enter at P3; they are absent here by design
-- (annotation rows carry them null with reason `source-absent`).
--
-- Receiving DK points: 1/reception + 0.1/yard + 6/TD + 3 bonus at 100+
-- receiving yards (DraftKings law; receiving-only by construction).

CREATE OR REPLACE TABLE `${features}.defense_receiver_role_concession_pit` AS
WITH role_rows AS (
  SELECT gsis_id, season, week, team, role_label
  FROM `${features}.receiver_week_role_pit`
  WHERE role_supported AND role_label IS NOT NULL
),
receiver_lines AS (
  SELECT
    w.player_id AS gsis_id,
    w.season,
    w.week,
    w.team,
    w.opponent_team AS defense,
    r.role_label,
    w.targets,
    w.receptions,
    w.receiving_yards,
    w.receiving_tds,
    w.receptions * 1.0
      + w.receiving_yards * 0.1
      + w.receiving_tds * 6.0
      + IF(w.receiving_yards >= 100, 3.0, 0.0) AS receiving_dk
  FROM `${raw}.weekly_stats` w
  JOIN role_rows r
    ON r.gsis_id = w.player_id
   AND r.season = w.season
   AND r.week = w.week
  WHERE w.position IN ('WR', 'TE')
    AND w.opponent_team IS NOT NULL
),
defense_games AS (
  SELECT DISTINCT defense, season, week
  FROM receiver_lines
),
defense_game_seq AS (
  SELECT
    defense,
    season,
    week,
    ROW_NUMBER() OVER (
      PARTITION BY defense ORDER BY season, week
    ) AS defense_game_ordinal
  FROM defense_games
),
roles AS (
  SELECT DISTINCT role_label FROM role_rows
),
per_game_role AS (
  SELECT
    g.defense,
    g.season,
    g.week,
    g.defense_game_ordinal,
    ro.role_label,
    COALESCE(SUM(l.targets), 0) AS targets_allowed,
    COALESCE(SUM(l.receptions), 0) AS receptions_allowed,
    COALESCE(SUM(l.receiving_yards), 0) AS receiving_yards_allowed,
    COALESCE(SUM(l.receiving_tds), 0) AS receiving_tds_allowed,
    COALESCE(SUM(l.receiving_dk), 0) AS receiving_dk_allowed,
    COUNT(l.gsis_id) AS role_receiver_count
  FROM defense_game_seq g
  CROSS JOIN roles ro
  LEFT JOIN receiver_lines l
    ON l.defense = g.defense
   AND l.season = g.season
   AND l.week = g.week
   AND l.role_label = ro.role_label
  GROUP BY g.defense, g.season, g.week, g.defense_game_ordinal, ro.role_label
),
windowed AS (
  SELECT
    p.*,
    COUNT(p.week) OVER prior_8 AS prior_defense_games_l8,
    COUNT(p.week) OVER prior_4 AS prior_defense_games_l4,
    SUM(p.targets_allowed) OVER prior_8 AS targets_allowed_sum_l8,
    SUM(p.receptions_allowed) OVER prior_8 AS receptions_allowed_sum_l8,
    SUM(p.receiving_yards_allowed) OVER prior_8
      AS receiving_yards_allowed_sum_l8,
    SUM(p.receiving_tds_allowed) OVER prior_8
      AS receiving_tds_allowed_sum_l8,
    SUM(p.receiving_dk_allowed) OVER prior_8
      AS receiving_dk_allowed_sum_l8,
    SUM(p.targets_allowed) OVER prior_4 AS targets_allowed_sum_l4,
    SUM(p.receiving_dk_allowed) OVER prior_4
      AS receiving_dk_allowed_sum_l4,
    SUM(p.role_receiver_count) OVER prior_8 AS role_receiver_count_l8,
    MAX(p.season * 100 + p.week) OVER prior_1 AS max_source_season_week
  FROM per_game_role p
  WINDOW
    prior_1 AS (
      PARTITION BY p.defense, p.role_label ORDER BY p.defense_game_ordinal
      ROWS BETWEEN 1 PRECEDING AND 1 PRECEDING
    ),
    prior_4 AS (
      PARTITION BY p.defense, p.role_label ORDER BY p.defense_game_ordinal
      ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ),
    prior_8 AS (
      PARTITION BY p.defense, p.role_label ORDER BY p.defense_game_ordinal
      ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
    )
),
-- League cumulative same-role rates strictly prior to each target week,
-- for the frozen pseudo-count shrinkage.
league_week AS (
  SELECT
    role_label,
    season,
    week,
    SUM(targets_allowed) AS week_targets,
    SUM(receptions_allowed) AS week_receptions,
    SUM(receiving_yards_allowed) AS week_yards,
    SUM(receiving_tds_allowed) AS week_tds,
    SUM(receiving_dk_allowed) AS week_dk
  FROM per_game_role
  GROUP BY role_label, season, week
),
league_prior AS (
  SELECT
    role_label,
    season,
    week,
    SUM(week_targets) OVER league_window AS league_targets_prior,
    SUM(week_receptions) OVER league_window AS league_receptions_prior,
    SUM(week_yards) OVER league_window AS league_yards_prior,
    SUM(week_tds) OVER league_window AS league_tds_prior,
    SUM(week_dk) OVER league_window AS league_dk_prior
  FROM league_week
  WINDOW league_window AS (
    PARTITION BY role_label ORDER BY season, week
    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
  )
)
SELECT
  w.defense,
  w.season,
  w.week,
  w.role_label,
  w.defense_game_ordinal,
  w.prior_defense_games_l8,
  w.prior_defense_games_l4,
  w.max_source_season_week,
  w.role_receiver_count_l8,
  w.targets_allowed_sum_l8,
  w.receptions_allowed_sum_l8,
  w.receiving_yards_allowed_sum_l8,
  w.receiving_tds_allowed_sum_l8,
  w.receiving_dk_allowed_sum_l8,
  w.targets_allowed_sum_l4,
  w.receiving_dk_allowed_sum_l4,
  SAFE_DIVIDE(w.targets_allowed_sum_l8, w.prior_defense_games_l8)
    AS targets_allowed_per_game_l8,
  SAFE_DIVIDE(w.receiving_dk_allowed_sum_l8, w.prior_defense_games_l8)
    AS receiving_dk_allowed_per_game_l8,
  SAFE_DIVIDE(w.receiving_dk_allowed_sum_l4, w.prior_defense_games_l4)
    AS receiving_dk_allowed_per_game_l4,
  SAFE_DIVIDE(w.receptions_allowed_sum_l8, w.targets_allowed_sum_l8)
    AS catch_rate_allowed_raw_l8,
  SAFE_DIVIDE(w.receiving_yards_allowed_sum_l8, w.targets_allowed_sum_l8)
    AS yards_per_target_allowed_raw_l8,
  SAFE_DIVIDE(w.receiving_dk_allowed_sum_l8, w.targets_allowed_sum_l8)
    AS dk_per_target_allowed_raw_l8,
  -- Frozen shrinkage: pseudo-count 32 targets toward the league cumulative
  -- same-role prior strictly before the target week.
  SAFE_DIVIDE(
    w.receptions_allowed_sum_l8
      + 32 * SAFE_DIVIDE(lp.league_receptions_prior, lp.league_targets_prior),
    w.targets_allowed_sum_l8 + 32
  ) AS catch_rate_allowed_shrunk_l8,
  SAFE_DIVIDE(
    w.receiving_yards_allowed_sum_l8
      + 32 * SAFE_DIVIDE(lp.league_yards_prior, lp.league_targets_prior),
    w.targets_allowed_sum_l8 + 32
  ) AS yards_per_target_allowed_shrunk_l8,
  SAFE_DIVIDE(
    w.receiving_tds_allowed_sum_l8
      + 32 * SAFE_DIVIDE(lp.league_tds_prior, lp.league_targets_prior),
    w.targets_allowed_sum_l8 + 32
  ) AS tds_per_target_allowed_shrunk_l8,
  SAFE_DIVIDE(
    w.receiving_dk_allowed_sum_l8
      + 32 * SAFE_DIVIDE(lp.league_dk_prior, lp.league_targets_prior),
    w.targets_allowed_sum_l8 + 32
  ) AS dk_per_target_allowed_shrunk_l8,
  SAFE_DIVIDE(lp.league_dk_prior, lp.league_targets_prior)
    AS league_dk_per_target_prior,
  (w.prior_defense_games_l8 >= 4) AS concession_supported,
  IF(w.prior_defense_games_l8 >= 4, NULL, 'below-support-threshold')
    AS concession_support_reason
FROM windowed w
LEFT JOIN league_prior lp
  ON lp.role_label = w.role_label
 AND lp.season = w.season
 AND lp.week = w.week
