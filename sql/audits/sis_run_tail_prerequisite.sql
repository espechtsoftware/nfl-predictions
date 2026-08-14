-- Outcome-blind prerequisite for an adaptive SIS opponent run-tail arm.
-- This reads only salary-universe membership and strictly-prior features.
WITH sis AS (
  SELECT
    season,
    week,
    team,
    rdef_boom_rate * rdef_attempts AS boom_events,
    rdef_bust_rate * rdef_attempts AS bust_events,
    rdef_attempts
  FROM `nfl-predictions-503414.nfl_raw.sis_team_run_context_game`
  WHERE source_run_id = 'sis-team-run-context-tranche-2-v1'
),
lagged AS (
  SELECT
    season,
    week,
    team,
    MAX(week) OVER prior_four AS source_week_end,
    COUNTIF(rdef_attempts IS NOT NULL) OVER prior_four AS prior_games,
    SAFE_DIVIDE(
      SUM(boom_events) OVER prior_four,
      SUM(rdef_attempts) OVER prior_four
    ) AS rdef_boom_rate_l4,
    SAFE_DIVIDE(
      SUM(bust_events) OVER prior_four,
      SUM(rdef_attempts) OVER prior_four
    ) AS rdef_bust_rate_l4
  FROM sis
  WINDOW prior_four AS (
    PARTITION BY season, team
    ORDER BY week
    ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
  )
),
panel AS (
  SELECT
    season,
    week,
    opp AS opponent,
    COUNT(*) AS salary_rb_rows
  FROM `nfl-predictions-503414.nfl_predictions.slate_player_features`
  WHERE panel_run_id = '20260812-pitclean-e80-selected-tabpfn-active-v2'
    AND pos = 'RB'
  GROUP BY season, week, opponent
),
prior_features AS (
  SELECT
    season,
    week,
    opponent,
    ANY_VALUE(rb_fp_allowed_adj_l6) AS rb_fp_allowed_adj_l6,
    ANY_VALUE(epa_per_dropback_allowed_l6) AS epa_per_dropback_allowed_l6,
    ANY_VALUE(epa_per_rush_allowed_l6) AS epa_per_rush_allowed_l6
  FROM `nfl-predictions-503414.nfl_features.player_week_training`
  WHERE season BETWEEN 2023 AND 2025
    AND position = 'RB'
  GROUP BY season, week, opponent
),
joined AS (
  SELECT
    panel.*,
    prior_features.* EXCEPT (season, week, opponent),
    lagged.source_week_end,
    lagged.prior_games,
    lagged.rdef_boom_rate_l4,
    lagged.rdef_bust_rate_l4
  FROM panel
  LEFT JOIN prior_features USING (season, week, opponent)
  LEFT JOIN lagged
    ON lagged.season = panel.season
    AND lagged.week = panel.week
    AND lagged.team = panel.opponent
),
grains AS (
  SELECT 'all' AS fold, * FROM joined
  UNION ALL
  SELECT CAST(season AS STRING) AS fold, * FROM joined
)
SELECT
  fold,
  COUNT(*) AS opponent_team_weeks,
  SUM(salary_rb_rows) AS salary_rb_rows,
  COUNTIF(
    prior_games >= 2
    AND source_week_end < week
    AND rdef_boom_rate_l4 IS NOT NULL
    AND rdef_bust_rate_l4 IS NOT NULL
  ) AS supported_team_weeks,
  SUM(IF(
    prior_games >= 2
      AND source_week_end < week
      AND rdef_boom_rate_l4 IS NOT NULL
      AND rdef_bust_rate_l4 IS NOT NULL,
    salary_rb_rows,
    0
  )) AS supported_salary_rb_rows,
  CORR(IF(prior_games >= 2, rdef_boom_rate_l4, NULL), rb_fp_allowed_adj_l6)
    AS boom_vs_rb_fp,
  CORR(IF(prior_games >= 2, rdef_bust_rate_l4, NULL), rb_fp_allowed_adj_l6)
    AS bust_vs_rb_fp,
  CORR(
    IF(prior_games >= 2, rdef_boom_rate_l4, NULL),
    epa_per_dropback_allowed_l6
  ) AS boom_vs_dropback_epa,
  CORR(
    IF(prior_games >= 2, rdef_boom_rate_l4, NULL),
    epa_per_rush_allowed_l6
  ) AS boom_vs_rush_epa,
  CORR(
    IF(prior_games >= 2, rdef_bust_rate_l4, NULL),
    epa_per_rush_allowed_l6
  ) AS bust_vs_rush_epa,
  CORR(
    IF(prior_games >= 2, rdef_boom_rate_l4, NULL),
    IF(prior_games >= 2, rdef_bust_rate_l4, NULL)
  ) AS boom_vs_bust
FROM grains
GROUP BY fold
ORDER BY IF(fold = 'all', 0, CAST(fold AS INT64));
