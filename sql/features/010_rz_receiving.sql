-- Red zone receiving usage by player-game, with inside-10 and inside-5 splits.
CREATE OR REPLACE TABLE `${features}.rz_receiving` AS
WITH plays AS (
  SELECT
    game_id, season, week, posteam, receiver_player_id,
    yardline_100,
    pass_attempt, complete_pass, pass_touchdown, air_yards
  FROM `${raw}.pbp`
  WHERE pass_attempt = 1
    AND receiver_player_id IS NOT NULL
    AND season_type IN ('REG','POST')
),
player_level AS (
  SELECT
    game_id, season, week, posteam AS team, receiver_player_id AS gsis_id,
    COUNTIF(yardline_100 <= 20) AS rz20_targets,
    COUNTIF(yardline_100 <= 10) AS rz10_targets,
    COUNTIF(yardline_100 <=  5) AS rz5_targets,
    COUNTIF(yardline_100 <= 20 AND pass_touchdown = 1) AS rz20_tds,
    COUNTIF(yardline_100 <= 10 AND complete_pass = 1)  AS rz10_receptions,
    COUNT(*) AS total_targets,
    SUM(air_yards) AS total_air_yards
  FROM plays
  GROUP BY 1,2,3,4,5
),
team_level AS (
  SELECT
    game_id, posteam AS team,
    COUNTIF(yardline_100 <= 20) AS team_rz20_targets,
    COUNTIF(yardline_100 <= 10) AS team_rz10_targets,
    COUNT(*) AS team_targets,
    SUM(air_yards) AS team_air_yards
  FROM plays
  GROUP BY 1,2
)
SELECT
  p.*,
  SAFE_DIVIDE(p.rz20_targets, t.team_rz20_targets) AS rz20_target_share,
  SAFE_DIVIDE(p.rz10_targets, t.team_rz10_targets) AS rz10_target_share,
  SAFE_DIVIDE(p.total_targets, t.team_targets)     AS target_share,
  SAFE_DIVIDE(p.total_air_yards, t.team_air_yards) AS air_yards_share
FROM player_level p
JOIN team_level t USING (game_id, team);
