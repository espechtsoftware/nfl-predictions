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
),
tw AS (
  SELECT o.team, o.season, o.week, o.off_plays, d.def_plays
  FROM off_tw o JOIN def_tw d USING (team, season, week)
),
with_upcoming AS (
  SELECT * FROM tw
  UNION ALL
  SELECT DISTINCT
    ro.team, ro.season, ro.week,
    CAST(NULL AS INT64) AS off_plays,
    CAST(NULL AS INT64) AS def_plays
  FROM `${features}.player_week_role` ro
  WHERE ro.is_upcoming
    AND NOT EXISTS (
      SELECT 1 FROM tw prior
      WHERE prior.team = ro.team AND prior.season = ro.season
        AND prior.week = ro.week
    )
)
SELECT
  team, season, week,
  AVG(off_plays) OVER w AS off_plays_l6,
  AVG(def_plays) OVER w AS def_plays_faced_l6
FROM with_upcoming
WINDOW w AS (
  PARTITION BY team ORDER BY season, week
  ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
);
