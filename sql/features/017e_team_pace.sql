-- Team pace, both sides of the ball (2026-08-01, candidate feature):
-- offensive plays run per game and defensive plays faced per game, l6
-- strictly prior. Consumed as pace_env_l6 = own offense + opponent
-- defense -- the "pace mismatch" claim reduces to expected play volume,
-- which is upstream of every player's opportunity.
CREATE OR REPLACE TABLE `${features}.team_week_pace` AS
WITH plays AS (
  SELECT posteam, defteam, season, week
  FROM `${raw}.pbp`
  WHERE posteam IS NOT NULL AND (pass = 1 OR rush = 1)
),
off_tw AS (
  SELECT posteam AS team, season, week, COUNT(*) AS off_plays
  FROM plays GROUP BY team, season, week
),
def_tw AS (
  SELECT defteam AS team, season, week, COUNT(*) AS def_plays
  FROM plays GROUP BY team, season, week
)
SELECT
  o.team, o.season, o.week,
  AVG(o.off_plays) OVER w AS off_plays_l6,
  AVG(d.def_plays) OVER w AS def_plays_faced_l6
FROM off_tw o
JOIN def_tw d USING (team, season, week)
WINDOW w AS (
  PARTITION BY o.team ORDER BY o.season, o.week
  ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
);
