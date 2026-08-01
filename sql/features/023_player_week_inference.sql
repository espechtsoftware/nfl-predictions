-- Live-slate feature rows: the upcoming week's synthetic usage rows (014)
-- joined to the same point-in-time features the model trained on (021).
-- Before this table existed, inference joined player_week_training at the
-- upcoming week — rows that can't exist until the games are played — so
-- every live projection silently fell back to cold-start fills.
--
-- Differences from the training table, all deliberate:
--   * no labels and no games_played_prior filter — debut players belong
--     here (they're the next-man-up rows this table exists to price);
--   * position falls back to the roster when there's no usage history;
--   * opponent defense joins as-of its latest built week (the defense
--     table has no upcoming-week rows; one-week-stale l6 windows are fine
--     for features the models treat as optional).
CREATE OR REPLACE TABLE `${features}.player_week_inference` AS
WITH def_asof AS (
  SELECT * FROM `${features}.defense_week_allowed`
  QUALIFY ROW_NUMBER() OVER (PARTITION BY team, season ORDER BY week DESC) = 1
)
SELECT
  -- Keys
  u.gsis_id, u.season, u.week, u.team, s.opponent,
  COALESCE(u.position, ro.position) AS position, s.game_id,

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

  u.rz20_targets_smoothed
    * t.rz10_pass_rate_std
    * SAFE_DIVIDE(t.implied_team_total, 22.0) AS xtd_receiving_proxy,

  -- Opponent (as-of latest built defense week)
  d.epa_per_dropback_allowed_l6, d.epa_per_rush_allowed_l6,
  d.rz_td_rate_allowed_l6,
  d.qb_fp_allowed_adj_l6, d.rb_fp_allowed_adj_l6,
  d.wr_fp_allowed_adj_l6, d.te_fp_allowed_adj_l6,

  -- Opponent secondary: exact-week join, no as-of needed — 017a's spine is
  -- the schedule, so the upcoming week has a row with strictly-prior
  -- windows and a live injury-report top_cb_out.
  cv.cb_ypt_allowed_l6, cv.cb_comp_rate_allowed_l6, cv.db_ypt_allowed_l6,
  cv.top_cb_out,

  -- Player state
  i.injury_status, i.practice_level, i.practice_participation_trend,
  COALESCE(i.games_missed_l4, 0) AS games_missed_l4,

  -- Role (depth chart + draft capital; cold-start priors read these)
  ro.depth_rank, ro.depth_rank_delta, ro.is_rookie, ro.draft_round,

  -- Game environment extras, same definitions as the training table.
  -- ref_flags_prior is NULL for upcoming games (officials data is
  -- post-game) until a midweek crew-assignment source exists.
  IF(rt.ref_prior_games >= 5, rt.ref_flags_prior, NULL) AS ref_flags_prior,
  np.neutral_pass_rate_l6,
  COALESCE(ol.team_ol_out, 0) AS team_ol_out,
  -- Candidate features (EXTRA_FEATURES gate in featureset.py)
  pc.off_plays_l6 + pcd.def_plays_faced_l6 AS pace_env_l6,
  bl.blitz_rate_l6 AS opp_blitz_rate_l6,
  tc.top2_target_share_l6 AS team_top2_target_share_l6,
  qn.qb_cpoe_l6,
  qn.qb_time_to_throw_l6,

  -- Opportunity vacated by teammates ruled Out this week (own share
  -- excluded), same definition as the training table.
  GREATEST(
    COALESCE(v.vacated_target_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.target_share_l4, 0), 0),
    0) AS team_vacated_target_share,
  GREATEST(
    COALESCE(v.vacated_carry_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.carry_share_l4, 0), 0),
    0) AS team_vacated_carry_share,

  -- Target quality + NGS context (024)
  adv.ez_targets_l4, adv.deep_targets_l4, adv.separation_l4, adv.stacked_box_l4,

  -- Weather
  w.wind_mph, w.temp_f, w.is_dome,

  -- DFS-specific (salary and dk_ppg come from the live slate pull at
  -- inference time; only the derived delta belongs here)
  dk.salary_delta_wow,

  -- Cold start flag (§7.6): no usable rolling history
  (u.games_played_prior IS NULL OR u.games_played_prior < 1
   OR u.target_share_l4 IS NULL AND u.carry_share_l4 IS NULL) AS is_cold_start

FROM `${features}.player_week_usage` u
JOIN `${features}.schedule_long` s
  ON s.team = u.team AND s.season = u.season AND s.week = u.week
LEFT JOIN `${features}.player_week_efficiency` e
  ON e.gsis_id = u.gsis_id AND e.season = u.season AND e.week = u.week
LEFT JOIN `${features}.team_week_context` t
  ON t.team = u.team AND t.season = u.season AND t.week = u.week
LEFT JOIN def_asof d
  ON d.team = s.opponent AND d.season = u.season
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
LEFT JOIN `${features}.referee_game_tendency` rt ON rt.game_id = s.game_id
LEFT JOIN `${features}.team_week_neutral_pass` np
  ON np.team = u.team AND np.season = u.season AND np.week = u.week
LEFT JOIN `${features}.team_week_ol_out` ol
  ON ol.team = u.team AND ol.season = u.season AND ol.week = u.week
LEFT JOIN `${features}.team_week_pace` pc
  ON pc.team = u.team AND pc.season = u.season AND pc.week = u.week
LEFT JOIN `${features}.team_week_pace` pcd
  ON pcd.team = s.opponent AND pcd.season = u.season AND pcd.week = u.week
LEFT JOIN `${features}.defense_week_blitz` bl
  ON bl.team = s.opponent AND bl.season = u.season AND bl.week = u.week
LEFT JOIN `${features}.team_week_target_concentration` tc
  ON tc.team = u.team AND tc.season = u.season AND tc.week = u.week
LEFT JOIN `${features}.qb_week_ngs` qn
  ON qn.gsis_id = u.gsis_id AND qn.season = u.season AND qn.week = u.week
WHERE u.is_upcoming
  AND COALESCE(u.position, ro.position) IN ('QB', 'RB', 'WR', 'TE')
-- Same mid-week team-change dedup as 021 (audit 2026-08-01).
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY u.gsis_id, u.season, u.week ORDER BY u.team
) = 1;
