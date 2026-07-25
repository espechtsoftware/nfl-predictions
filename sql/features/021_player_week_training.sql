-- The joined, model-ready wide table. Every feature is point-in-time; the
-- labels (y_*) are the only same-week values. Leakage assertions in
-- nfl_dfs.features.leakage run against this table after every build.
CREATE OR REPLACE TABLE `${features}.player_week_training` AS
SELECT
  -- Keys
  u.gsis_id, u.season, u.week, u.team, s.opponent, u.position, s.game_id,

  -- Usage (point-in-time, §5.2)
  u.targets_l4, u.target_share_l4, u.air_yards_share_l4, u.wopr_l4,
  u.rz20_targets_l4, u.rz10_targets_l4,
  u.rz20_target_share_l4, u.rz10_target_share_l4,
  u.rz20_targets_smoothed,
  u.carries_l4, u.carry_share_l4, u.gl3_carries_l4, u.gl3_carry_share_l4,
  u.gl3_carries_smoothed,
  u.snap_share_l4,
  u.target_share_std, u.target_share_trend, u.carry_share_trend,
  u.games_played_prior,

  -- Efficiency
  e.yards_per_target_l8, e.yards_per_reception_l8, e.catch_rate_l8,
  e.yards_per_carry_l8, e.yards_per_attempt_l8, e.adot_l8,
  e.dk_points_l4, e.dk_points_std, e.dk_points_vol,

  -- Game context
  t.implied_team_total, t.spread, t.game_total, t.expected_game_script,
  t.is_home, t.days_rest,
  t.plays_l4, t.pass_rate_l4, t.pace_l4, t.proe_l4, t.expected_plays,

  -- The strongest single derived feature (§5.4): expected TDs from red zone
  -- opportunity — stable part (opportunity) x league-average conversion.
  u.rz20_targets_smoothed
    * t.rz10_pass_rate_std
    * SAFE_DIVIDE(t.implied_team_total, 22.0) AS xtd_receiving_proxy,

  -- Opponent
  d.epa_per_dropback_allowed_l6, d.epa_per_rush_allowed_l6,
  d.rz_td_rate_allowed_l6,
  d.qb_fp_allowed_adj_l6, d.rb_fp_allowed_adj_l6,
  d.wr_fp_allowed_adj_l6, d.te_fp_allowed_adj_l6,

  -- Opponent secondary (CB coverage from PFR advstats, 2018+; NULL before)
  cv.cb_ypt_allowed_l6, cv.cb_comp_rate_allowed_l6, cv.db_ypt_allowed_l6,
  cv.top_cb_out,

  -- Player state
  i.injury_status, i.practice_level, i.practice_participation_trend,
  COALESCE(i.games_missed_l4, 0) AS games_missed_l4,

  -- Role (depth chart + draft capital; cold-start priors read these)
  ro.depth_rank, ro.is_rookie, ro.draft_round,

  -- Opportunity vacated by teammates ruled Out this week (own share
  -- excluded): the point-in-time next-man-up signal.
  GREATEST(
    COALESCE(v.vacated_target_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.target_share_l4, 0), 0),
    0) AS team_vacated_target_share,
  GREATEST(
    COALESCE(v.vacated_carry_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.carry_share_l4, 0), 0),
    0) AS team_vacated_carry_share,

  -- Target quality + NGS context (024): TD opportunity beats TD history
  adv.ez_targets_l4, adv.deep_targets_l4, adv.separation_l4, adv.stacked_box_l4,

  -- Weather
  w.wind_mph, w.temp_f, w.is_dome,

  -- DFS-specific
  dk.salary, dk.salary_delta_wow, dk.dk_ppg,

  -- Cold start flag (§7.6): no usable rolling history
  (u.games_played_prior IS NULL OR u.games_played_prior < 1
   OR u.target_share_l4 IS NULL AND u.carry_share_l4 IS NULL) AS is_cold_start,

  -- Labels (multiple, for the component models)
  a.targets       AS y_targets,
  a.receptions    AS y_receptions,
  a.rec_yards     AS y_rec_yards,
  a.rec_tds       AS y_rec_tds,
  a.carries       AS y_carries,
  a.rush_yards    AS y_rush_yards,
  a.rush_tds      AS y_rush_tds,
  a.pass_attempts AS y_pass_attempts,
  a.pass_yards    AS y_pass_yards,
  a.pass_tds      AS y_pass_tds,
  a.interceptions AS y_interceptions,
  a.dk_points     AS y_dk_points

FROM `${features}.player_week_usage` u
JOIN `${features}.player_week_actuals` a USING (gsis_id, season, week)
JOIN `${features}.schedule_long` s
  ON s.team = u.team AND s.season = u.season AND s.week = u.week
LEFT JOIN `${features}.player_week_efficiency` e
  ON e.gsis_id = u.gsis_id AND e.season = u.season AND e.week = u.week
LEFT JOIN `${features}.team_week_context` t
  ON t.team = u.team AND t.season = u.season AND t.week = u.week
LEFT JOIN `${features}.defense_week_allowed` d
  ON d.team = s.opponent AND d.season = u.season AND d.week = u.week
LEFT JOIN `${features}.defense_week_coverage` cv
  ON cv.team = s.opponent AND cv.season = u.season AND cv.week = u.week
LEFT JOIN `${features}.player_week_injury` i
  ON i.gsis_id = u.gsis_id AND i.season = u.season AND i.week = u.week
LEFT JOIN `${features}.game_weather` w ON w.game_id = s.game_id
LEFT JOIN `${features}.dk_salary_week` dk
  ON dk.gsis_id = u.gsis_id AND dk.season = u.season AND dk.week = u.week
LEFT JOIN `${features}.player_week_role` ro
  ON ro.gsis_id = u.gsis_id AND ro.season = u.season AND ro.week = u.week
LEFT JOIN `${features}.team_week_vacated` v
  ON v.team = u.team AND v.season = u.season AND v.week = u.week
LEFT JOIN `${features}.player_week_advanced` adv
  ON adv.gsis_id = u.gsis_id AND adv.season = u.season AND adv.week = u.week
WHERE u.position IN ('QB', 'RB', 'WR', 'TE')
  AND u.games_played_prior >= 1
  -- Upcoming-week synthetic rows (014) are inference-only; the actuals
  -- inner join already drops them, this states the intent.
  AND NOT u.is_upcoming;
