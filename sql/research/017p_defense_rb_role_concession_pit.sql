-- Defense concessions to point-in-time RB roles (rb-matchup v1).
--
-- RESEARCH TABLE, outside the production build glob; executed by
-- scripts/build_receiver_matchup_features.py after 017o. Mirrors the
-- frozen 017m law with TWO concession surfaces per RB role:
--
--   * rushing: attempts, yards, TDs and rushing DK allowed
--     (0.1/yard + 6/TD + 3 bonus at 100+ rushing yards);
--   * receiving: targets, receptions, yards, TDs and receiving DK allowed
--     (1/reception + 0.1/yard + 6/TD + 3 bonus at 100+ receiving yards) —
--     the checkdown-back surface the WR/TE table deliberately excludes.
--
-- Windows are the defense's last eight (and four) games strictly prior in
-- cross-season order over a defense-game spine with zero-filled role
-- games. Efficiency rates are ratio-of-sums with the frozen
-- pseudo-count-32 shrinkage toward the league cumulative same-role prior
-- strictly before the target week (rushing shrinks on attempts,
-- receiving on targets). Adjusted `*_over_expectation` views wait for
-- receipted frozen projections, as in 017m.

CREATE OR REPLACE TABLE `${features}.defense_rb_role_concession_pit` AS
WITH role_rows AS (
  SELECT gsis_id, season, week, role_label
  FROM `${features}.rb_week_role_pit`
  WHERE role_supported AND role_label IS NOT NULL
),
rb_lines AS (
  SELECT
    w.player_id AS gsis_id,
    w.season,
    w.week,
    w.opponent_team AS defense,
    r.role_label,
    w.carries,
    w.rushing_yards,
    w.rushing_tds,
    w.rushing_yards * 0.1
      + w.rushing_tds * 6.0
      + IF(w.rushing_yards >= 100, 3.0, 0.0) AS rushing_dk,
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
  WHERE w.position = 'RB'
    AND w.opponent_team IS NOT NULL
),
defense_games AS (
  SELECT DISTINCT defense, season, week FROM rb_lines
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
    COALESCE(SUM(l.carries), 0) AS rush_attempts_allowed,
    COALESCE(SUM(l.rushing_yards), 0) AS rushing_yards_allowed,
    COALESCE(SUM(l.rushing_tds), 0) AS rushing_tds_allowed,
    COALESCE(SUM(l.rushing_dk), 0) AS rushing_dk_allowed,
    COALESCE(SUM(l.targets), 0) AS targets_allowed,
    COALESCE(SUM(l.receptions), 0) AS receptions_allowed,
    COALESCE(SUM(l.receiving_yards), 0) AS receiving_yards_allowed,
    COALESCE(SUM(l.receiving_tds), 0) AS receiving_tds_allowed,
    COALESCE(SUM(l.receiving_dk), 0) AS receiving_dk_allowed,
    COUNT(l.gsis_id) AS role_player_count
  FROM defense_game_seq g
  CROSS JOIN roles ro
  LEFT JOIN rb_lines l
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
    SUM(p.rush_attempts_allowed) OVER prior_8 AS rush_attempts_sum_l8,
    SUM(p.rushing_yards_allowed) OVER prior_8 AS rushing_yards_sum_l8,
    SUM(p.rushing_tds_allowed) OVER prior_8 AS rushing_tds_sum_l8,
    SUM(p.rushing_dk_allowed) OVER prior_8 AS rushing_dk_sum_l8,
    SUM(p.rushing_dk_allowed) OVER prior_4 AS rushing_dk_sum_l4,
    SUM(p.targets_allowed) OVER prior_8 AS targets_sum_l8,
    SUM(p.receptions_allowed) OVER prior_8 AS receptions_sum_l8,
    SUM(p.receiving_yards_allowed) OVER prior_8 AS receiving_yards_sum_l8,
    SUM(p.receiving_tds_allowed) OVER prior_8 AS receiving_tds_sum_l8,
    SUM(p.receiving_dk_allowed) OVER prior_8 AS receiving_dk_sum_l8,
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
league_week AS (
  SELECT
    role_label,
    season,
    week,
    SUM(rush_attempts_allowed) AS week_rush_attempts,
    SUM(rushing_yards_allowed) AS week_rushing_yards,
    SUM(rushing_tds_allowed) AS week_rushing_tds,
    SUM(rushing_dk_allowed) AS week_rushing_dk,
    SUM(targets_allowed) AS week_targets,
    SUM(receiving_dk_allowed) AS week_receiving_dk
  FROM per_game_role
  GROUP BY role_label, season, week
),
league_prior AS (
  SELECT
    role_label,
    season,
    week,
    SUM(week_rush_attempts) OVER league_window AS league_rush_attempts_prior,
    SUM(week_rushing_yards) OVER league_window AS league_rushing_yards_prior,
    SUM(week_rushing_tds) OVER league_window AS league_rushing_tds_prior,
    SUM(week_rushing_dk) OVER league_window AS league_rushing_dk_prior,
    SUM(week_targets) OVER league_window AS league_targets_prior,
    SUM(week_receiving_dk) OVER league_window AS league_receiving_dk_prior
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
  w.rush_attempts_sum_l8,
  w.rushing_yards_sum_l8,
  w.rushing_tds_sum_l8,
  w.rushing_dk_sum_l8,
  w.targets_sum_l8,
  w.receptions_sum_l8,
  w.receiving_yards_sum_l8,
  w.receiving_tds_sum_l8,
  w.receiving_dk_sum_l8,
  SAFE_DIVIDE(w.rushing_dk_sum_l8, w.prior_defense_games_l8)
    AS rushing_dk_allowed_per_game_l8,
  SAFE_DIVIDE(w.rushing_dk_sum_l4, w.prior_defense_games_l4)
    AS rushing_dk_allowed_per_game_l4,
  SAFE_DIVIDE(w.receiving_dk_sum_l8, w.prior_defense_games_l8)
    AS receiving_dk_allowed_per_game_l8,
  SAFE_DIVIDE(w.rushing_yards_sum_l8, w.rush_attempts_sum_l8)
    AS yards_per_attempt_allowed_raw_l8,
  SAFE_DIVIDE(
    w.rushing_yards_sum_l8
      + 32 * SAFE_DIVIDE(
          lp.league_rushing_yards_prior, lp.league_rush_attempts_prior),
    w.rush_attempts_sum_l8 + 32
  ) AS yards_per_attempt_allowed_shrunk_l8,
  SAFE_DIVIDE(
    w.rushing_dk_sum_l8
      + 32 * SAFE_DIVIDE(
          lp.league_rushing_dk_prior, lp.league_rush_attempts_prior),
    w.rush_attempts_sum_l8 + 32
  ) AS rushing_dk_per_attempt_allowed_shrunk_l8,
  SAFE_DIVIDE(
    w.receiving_dk_sum_l8
      + 32 * SAFE_DIVIDE(
          lp.league_receiving_dk_prior, lp.league_targets_prior),
    w.targets_sum_l8 + 32
  ) AS receiving_dk_per_target_allowed_shrunk_l8,
  (w.prior_defense_games_l8 >= 4) AS concession_supported,
  IF(w.prior_defense_games_l8 >= 4, NULL, 'below-support-threshold')
    AS concession_support_reason
FROM windowed w
LEFT JOIN league_prior lp
  ON lp.role_label = w.role_label
 AND lp.season = w.season
 AND lp.week = w.week
