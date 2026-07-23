-- Red zone rushing usage; goal-line split at <=3 is where RB touchdown
-- equity actually lives.
CREATE OR REPLACE TABLE `${features}.rz_rushing` AS
WITH plays AS (
  SELECT
    game_id, season, week, posteam, rusher_player_id,
    yardline_100, rush_attempt, rush_touchdown, yards_gained
  FROM `${raw}.pbp`
  WHERE rush_attempt = 1
    AND rusher_player_id IS NOT NULL
    AND season_type IN ('REG','POST')
),
player_level AS (
  SELECT
    game_id, season, week, posteam AS team, rusher_player_id AS gsis_id,
    COUNTIF(yardline_100 <= 20) AS rz20_carries,
    COUNTIF(yardline_100 <= 10) AS rz10_carries,
    COUNTIF(yardline_100 <=  5) AS rz5_carries,
    COUNTIF(yardline_100 <=  3) AS gl3_carries,
    COUNTIF(yardline_100 <= 20 AND rush_touchdown = 1) AS rz20_rush_tds,
    COUNT(*) AS total_carries,
    SUM(yards_gained) AS total_rush_yards
  FROM plays
  GROUP BY 1,2,3,4,5
),
team_level AS (
  SELECT
    game_id, posteam AS team,
    COUNTIF(yardline_100 <= 20) AS team_rz20_carries,
    COUNTIF(yardline_100 <=  3) AS team_gl3_carries,
    COUNT(*) AS team_carries
  FROM plays
  GROUP BY 1,2
)
SELECT
  p.*,
  SAFE_DIVIDE(p.rz20_carries, t.team_rz20_carries) AS rz20_carry_share,
  SAFE_DIVIDE(p.gl3_carries,  t.team_gl3_carries)  AS gl3_carry_share,
  SAFE_DIVIDE(p.total_carries, t.team_carries)     AS carry_share
FROM player_level p
JOIN team_level t USING (game_id, team);
