-- The joined, model-ready wide table. Every feature is point-in-time; the
-- labels (y_*) are the only same-week values. Leakage assertions in
-- nfl_dfs.features.leakage run against this table after every build.
CREATE OR REPLACE TABLE `${features}.player_week_training` AS
SELECT
  -- Keys
  u.gsis_id, u.season, u.week, u.team, s.opponent, u.position, s.game_id,
  u.was_active,

  -- Usage (point-in-time, §5.2)
  u.targets_l4, u.target_share_l4, u.air_yards_share_l4, u.wopr_l4,
  u.rz20_targets_l4, u.rz10_targets_l4,
  u.rz20_target_share_l4, u.rz10_target_share_l4,
  u.rz20_targets_smoothed,
  u.carries_l4, u.carry_share_l4, u.gl3_carries_l4, u.gl3_carry_share_l4,
  u.gl3_carries_smoothed,
  u.snap_share_l4,
  u.target_share_last, u.carry_share_last, u.snap_share_last,
  u.target_share_jump, u.carry_share_jump, u.snap_share_jump,
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
  ro.depth_rank, ro.depth_rank_delta, ro.is_rookie, ro.draft_round,

  -- Game environment extras (2026-08-01): referee-crew flag tendency
  -- (strictly-prior 20-game window; NULL live until a midweek crew
  -- source exists) and neutral-situation pass rate (script-stripped
  -- schematic identity, l6 strictly prior).
  IF(rt.ref_prior_games >= 5, rt.ref_flags_prior, NULL) AS ref_flags_prior,
  np.neutral_pass_rate_l6,
  COALESCE(ol.team_ol_out, 0) AS team_ol_out,
  -- Candidate features (EXTRA_FEATURES gate in featureset.py)
  pc.off_plays_l6 + pcd.def_plays_faced_l6 AS pace_env_l6,
  bl.blitz_rate_l6 AS opp_blitz_rate_l6,
  fo.pa_rate_l6,
  fd.def_pressure_rate_l6 AS opp_pressure_rate_l6,
  xf.xfp_l4,
  sx.net_rest_diff,
  sx.body_clock_hour,
  tc.top2_target_share_l6 AS team_top2_target_share_l6,
  qn.qb_cpoe_l6,
  qn.qb_time_to_throw_l6,

  -- Licensed Route Share prospective shadow. 017k mechanically selects only
  -- observations earlier than this target week. These remain inert unless a
  -- shadow model explicitly opts into the four registered EXTRA_FEATURES.
  fr.fp_route_source_season, fr.fp_route_source_week,
  fr.fp_route_source_sha256,
  fr.fp_route_prior_observations,
  fr.fp_route_share_last, fr.fp_route_share_l4,
  fr.fp_route_share_jump, fr.fp_route_cross_season,
  fr.fp_route_fallback,

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

  -- Causally-directed vacated capture (2026-08-03 event study, Addendum
  -- 44): 553 target-hog / 369 carry-hog absences 2019-25 show vacated
  -- TARGETS flow laterally to other WRs (WR1/WR2 +2.5-2.6 share pts,
  -- WR3 +1.9, TE +1.2, RB ~0) while vacated CARRIES concentrate in the
  -- backfield (RB2 +15.8, RB1 +9.5, RB3 +7.5, others ~0). These weight
  -- the team-level sum by the empirical capture rate of the player's
  -- (position x depth) cell — the interaction a GBM must otherwise
  -- discover on its own. EXTRA_FEATURES candidates.
  GREATEST(
    COALESCE(v.vacated_target_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.target_share_l4, 0), 0),
    0) * CASE
      WHEN COALESCE(u.position, ro.position) = 'WR' AND ro.depth_rank <= 2 THEN 0.100
      WHEN COALESCE(u.position, ro.position) = 'WR' THEN 0.073
      WHEN COALESCE(u.position, ro.position) = 'TE' THEN 0.050
      WHEN COALESCE(u.position, ro.position) = 'RB' AND ro.depth_rank <= 2 THEN 0.033
      ELSE 0.009 END AS vacated_capture_tgt,
  GREATEST(
    COALESCE(v.vacated_carry_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.carry_share_l4, 0), 0),
    0) * CASE
      WHEN COALESCE(u.position, ro.position) = 'RB' AND ro.depth_rank = 1 THEN 0.270
      WHEN COALESCE(u.position, ro.position) = 'RB' AND ro.depth_rank = 2 THEN 0.450
      WHEN COALESCE(u.position, ro.position) = 'RB' THEN 0.210
      WHEN COALESCE(u.position, ro.position) = 'QB' THEN 0.047
      ELSE 0.020 END AS vacated_capture_car,

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
LEFT JOIN `${features}.team_week_ftn_offense` fo
  ON fo.team = u.team AND fo.season = u.season AND fo.week = u.week
LEFT JOIN `${features}.player_week_xfp` xf
  ON xf.gsis_id = u.gsis_id AND xf.season = u.season AND xf.week = u.week
LEFT JOIN `${features}.team_week_schedule_ctx` sx
  ON sx.team = u.team AND sx.season = u.season AND sx.week = u.week
LEFT JOIN `${features}.team_week_ftn_offense` fd
  ON fd.team = s.opponent AND fd.season = u.season AND fd.week = u.week
LEFT JOIN `${features}.team_week_target_concentration` tc
  ON tc.team = u.team AND tc.season = u.season AND tc.week = u.week
LEFT JOIN `${features}.qb_week_ngs` qn
  ON qn.gsis_id = u.gsis_id AND qn.season = u.season AND qn.week = u.week
LEFT JOIN `${features}.player_week_fp_route` fr
  ON fr.gsis_id = u.gsis_id AND fr.season = u.season AND fr.week = u.week
WHERE u.position IN ('QB', 'RB', 'WR', 'TE')
  -- Salary-spined history deliberately retains in-season debuts and listed
  -- players with no prior stat line. Cold-start handling is part of the live
  -- model contract; filtering these rows made that regime unreplayable.
  -- Upcoming-week synthetic rows (014) are inference-only; the actuals
  -- inner join already drops them, this states the intent.
  AND NOT u.is_upcoming
-- Mid-week team changes (trades/waivers: McCaffrey 2022 wk7, Bennett
-- 2017 wk10, ...) give a player two upstream team rows and therefore two
-- training rows (2026-08-01 audit: 9 dupes in 52,422). Keep one,
-- deterministically.
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY u.gsis_id, u.season, u.week ORDER BY u.team
) = 1;
