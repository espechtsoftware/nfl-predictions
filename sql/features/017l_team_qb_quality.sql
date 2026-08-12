-- Research-only team passing-quality feature frozen in
-- reports/2026-08-11-tabpfn-team-qb-quality-protocol.md.
--
-- This remains a side table rather than joining player_week_training or
-- player_week_inference. That keeps the repaired production/cache source
-- identity unchanged while the isolated TabPFN arm is evaluated. The cache
-- generator broadcasts the value only to RB/WR/TE rows; QB rows remain NULL.
CREATE OR REPLACE TABLE `${features}.team_week_qb_quality` AS
WITH schedule_spine AS (
  -- Every completed regular-season team game plus only the live target row.
  -- Loading the entire future schedule would let unplayed games consume
  -- bounded ROWS slots before a later upcoming target.
  SELECT season, week,
    CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE home_team END AS team
  FROM `${raw}.schedules`
  WHERE game_type = 'REG' AND home_score IS NOT NULL AND away_score IS NOT NULL
  UNION DISTINCT
  SELECT season, week,
    CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE away_team END AS team
  FROM `${raw}.schedules`
  WHERE game_type = 'REG' AND home_score IS NOT NULL AND away_score IS NOT NULL
  UNION DISTINCT
  SELECT season, week, team
  FROM `${features}.player_week_role`
  WHERE is_upcoming AND team IS NOT NULL
),
weekly_dropbacks AS (
  SELECT
    CASE posteam
      WHEN 'OAK' THEN 'LV'
      WHEN 'SD' THEN 'LAC'
      WHEN 'STL' THEN 'LA'
      ELSE posteam
    END AS team,
    season,
    week,
    SUM(CAST(cpoe AS FLOAT64)) AS cpoe_sum,
    COUNT(cpoe) AS cpoe_dropbacks
  FROM `${raw}.pbp`
  WHERE qb_dropback = 1
    AND posteam IS NOT NULL
    AND cpoe IS NOT NULL
    AND season_type = 'REG'
  GROUP BY 1, 2, 3
),
spined AS (
  SELECT
    s.team,
    s.season,
    s.week,
    d.cpoe_sum,
    d.cpoe_dropbacks
  FROM schedule_spine s
  LEFT JOIN weekly_dropbacks d USING (team, season, week)
),
rolled AS (
  SELECT
    team,
    season,
    week,
    SAFE_DIVIDE(
      SUM(cpoe_sum) OVER prior_six_team_games,
      SUM(cpoe_dropbacks) OVER prior_six_team_games
    ) AS team_qb_cpoe_l6,
    SUM(cpoe_dropbacks) OVER prior_six_team_games
      AS team_qb_cpoe_dropbacks_l6,
    COUNTIF(cpoe_dropbacks IS NOT NULL) OVER prior_six_team_games
      AS team_qb_cpoe_games_l6
  FROM spined
  WINDOW prior_six_team_games AS (
    PARTITION BY team
    ORDER BY season, week
    ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
  )
)
SELECT * FROM rolled;
