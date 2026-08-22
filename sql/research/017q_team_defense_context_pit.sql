-- Team defense context, strictly prior (rb/qb-matchup workstream, v1).
--
-- RESEARCH TABLE, outside the production build glob; executed by
-- scripts/build_receiver_matchup_features.py. One row per
-- (defense, season, week) game occurrence, serving BOTH the RB and QB
-- matchup families from three sources with their own spines and support:
--
--   * SIS run defense (2022+): attempt-weighted EPA/attempt, boom and
--     bust rates allowed, stuff rate, yards-after-contact per attempt —
--     the RB family's unit-context component;
--   * PFR pass rush (2018+): pressures, sacks, blitzes, hurries per game
--     summed over defenders — the QB family's pressure component
--     (fewer allowed pressures is offense-favorable; orientation is
--     applied at annotation time);
--   * QB passing concessions: full QB DraftKings points allowed per game
--     (0.04/pass yard + 4/pass TD - 1/INT + 3 bonus at 300, plus rushing
--     0.1/6/100-bonus, minus 1 per lost fumble).
--
-- All windows are the defense's last eight games strictly prior in
-- cross-season order, per source. Missing sources stay null with their
-- own support flags; nothing is averaged across incompatible sources.

CREATE OR REPLACE TABLE `${features}.team_defense_context_pit` AS
WITH sis_games AS (
  SELECT
    team AS defense,
    season,
    week,
    rdef_attempts,
    rdef_epa_per_attempt * rdef_attempts AS rdef_epa_total,
    rdef_boom_rate * rdef_attempts AS rdef_boom_total,
    rdef_bust_rate * rdef_attempts AS rdef_bust_total,
    rdef_stuffs,
    rdef_yards_after_contact,
    ROW_NUMBER() OVER (
      PARTITION BY team ORDER BY season, week
    ) AS game_seq
  FROM `${raw}.sis_team_run_context_game`
  WHERE team IS NOT NULL AND rdef_attempts IS NOT NULL
),
sis_windowed AS (
  SELECT
    defense,
    season,
    week,
    COUNT(week) OVER prior_8 AS sis_prior_games_l8,
    SAFE_DIVIDE(
      SUM(rdef_epa_total) OVER prior_8,
      SUM(rdef_attempts) OVER prior_8
    ) AS rdef_epa_per_attempt_l8,
    SAFE_DIVIDE(
      SUM(rdef_boom_total) OVER prior_8,
      SUM(rdef_attempts) OVER prior_8
    ) AS rdef_boom_rate_l8,
    SAFE_DIVIDE(
      SUM(rdef_bust_total) OVER prior_8,
      SUM(rdef_attempts) OVER prior_8
    ) AS rdef_bust_rate_l8,
    SAFE_DIVIDE(
      SUM(rdef_stuffs) OVER prior_8,
      SUM(rdef_attempts) OVER prior_8
    ) AS rdef_stuff_rate_l8,
    SAFE_DIVIDE(
      SUM(rdef_yards_after_contact) OVER prior_8,
      SUM(rdef_attempts) OVER prior_8
    ) AS rdef_yac_per_attempt_l8,
    MAX(season * 100 + week) OVER prior_1 AS sis_max_source_season_week
  FROM sis_games
  WINDOW
    prior_1 AS (
      PARTITION BY defense ORDER BY game_seq
      ROWS BETWEEN 1 PRECEDING AND 1 PRECEDING
    ),
    prior_8 AS (
      PARTITION BY defense ORDER BY game_seq
      ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
    )
),
pfr_games AS (
  SELECT
    team AS defense,
    season,
    week,
    SUM(def_pressures) AS pressures,
    SUM(def_sacks) AS sacks,
    SUM(def_times_blitzed) AS blitzes,
    SUM(def_times_hurried) AS hurries
  FROM `${raw}.pfr_advstats_def`
  WHERE team IS NOT NULL
  GROUP BY team, season, week
),
pfr_seq AS (
  SELECT
    p.*,
    ROW_NUMBER() OVER (
      PARTITION BY defense ORDER BY season, week
    ) AS game_seq
  FROM pfr_games p
),
pfr_windowed AS (
  SELECT
    defense,
    season,
    week,
    COUNT(week) OVER prior_8 AS pfr_prior_games_l8,
    SAFE_DIVIDE(
      SUM(pressures) OVER prior_8, COUNT(week) OVER prior_8
    ) AS pressures_per_game_l8,
    SAFE_DIVIDE(
      SUM(sacks) OVER prior_8, COUNT(week) OVER prior_8
    ) AS sacks_per_game_l8,
    SAFE_DIVIDE(
      SUM(blitzes) OVER prior_8, COUNT(week) OVER prior_8
    ) AS blitzes_per_game_l8,
    SAFE_DIVIDE(
      SUM(hurries) OVER prior_8, COUNT(week) OVER prior_8
    ) AS hurries_per_game_l8,
    MAX(season * 100 + week) OVER prior_1 AS pfr_max_source_season_week
  FROM pfr_seq
  WINDOW
    prior_1 AS (
      PARTITION BY defense ORDER BY game_seq
      ROWS BETWEEN 1 PRECEDING AND 1 PRECEDING
    ),
    prior_8 AS (
      PARTITION BY defense ORDER BY game_seq
      ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
    )
),
qb_games AS (
  SELECT
    w.opponent_team AS defense,
    w.season,
    w.week,
    SUM(
      w.passing_yards * 0.04
      + w.passing_tds * 4.0
      - w.passing_interceptions * 1.0
      + IF(w.passing_yards >= 300, 3.0, 0.0)
      + w.rushing_yards * 0.1
      + w.rushing_tds * 6.0
      + IF(w.rushing_yards >= 100, 3.0, 0.0)
      - COALESCE(w.fumbles_lost_total, 0) * 1.0
    ) AS qb_dk_allowed
  FROM `${raw}.weekly_stats` w
  WHERE w.position = 'QB' AND w.opponent_team IS NOT NULL
  GROUP BY w.opponent_team, w.season, w.week
),
qb_seq AS (
  SELECT
    q.*,
    ROW_NUMBER() OVER (
      PARTITION BY defense ORDER BY season, week
    ) AS game_seq
  FROM qb_games q
),
qb_windowed AS (
  SELECT
    defense,
    season,
    week,
    COUNT(week) OVER prior_8 AS qb_prior_games_l8,
    SAFE_DIVIDE(
      SUM(qb_dk_allowed) OVER prior_8, COUNT(week) OVER prior_8
    ) AS qb_dk_allowed_per_game_l8,
    MAX(season * 100 + week) OVER prior_1 AS qb_max_source_season_week
  FROM qb_seq
  WINDOW
    prior_1 AS (
      PARTITION BY defense ORDER BY game_seq
      ROWS BETWEEN 1 PRECEDING AND 1 PRECEDING
    ),
    prior_8 AS (
      PARTITION BY defense ORDER BY game_seq
      ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
    )
),
spine AS (
  SELECT DISTINCT defense, season, week FROM qb_windowed
  UNION DISTINCT
  SELECT DISTINCT defense, season, week FROM sis_windowed
  UNION DISTINCT
  SELECT DISTINCT defense, season, week FROM pfr_windowed
)
SELECT
  s.defense,
  s.season,
  s.week,
  sis.sis_prior_games_l8,
  sis.sis_max_source_season_week,
  sis.rdef_epa_per_attempt_l8,
  sis.rdef_boom_rate_l8,
  sis.rdef_bust_rate_l8,
  sis.rdef_stuff_rate_l8,
  sis.rdef_yac_per_attempt_l8,
  (COALESCE(sis.sis_prior_games_l8, 0) >= 4) AS run_context_supported,
  pfr.pfr_prior_games_l8,
  pfr.pfr_max_source_season_week,
  pfr.pressures_per_game_l8,
  pfr.sacks_per_game_l8,
  pfr.blitzes_per_game_l8,
  pfr.hurries_per_game_l8,
  (COALESCE(pfr.pfr_prior_games_l8, 0) >= 4) AS pass_rush_supported,
  qb.qb_prior_games_l8,
  qb.qb_max_source_season_week,
  qb.qb_dk_allowed_per_game_l8,
  (COALESCE(qb.qb_prior_games_l8, 0) >= 4) AS qb_concession_supported
FROM spine s
LEFT JOIN sis_windowed sis
  ON sis.defense = s.defense AND sis.season = s.season AND sis.week = s.week
LEFT JOIN pfr_windowed pfr
  ON pfr.defense = s.defense AND pfr.season = s.season AND pfr.week = s.week
LEFT JOIN qb_windowed qb
  ON qb.defense = s.defense AND qb.season = s.season AND qb.week = s.week
