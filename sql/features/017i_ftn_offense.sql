-- FTN offense/defense charting rates (2026-08-02, candidate features):
-- the audit found we consume 1 of ~20 FTN fields. Two mechanism-backed
-- candidates from the unused set, l6 strictly prior, 2022+ (earlier
-- rows NULL; build_X NaN-fills):
--   * pa_rate_l6 (team OFFENSE play-action rate) — play-action drives
--     deep shots and YPA; claimed consumer is the WR ceiling the real
--     Milly winners exploit (Addendum 38 slot decomposition).
--   * def_pressure_rate_l6 (defense pressure GENERATED per dropback,
--     outcome-based: sacks + QB out-of-pocket + throwaways) — distinct
--     from blitz_rate_l6 which counts rushers sent, not results.
CREATE OR REPLACE TABLE `${features}.team_week_ftn_offense` AS
WITH plays AS (
  SELECT p.posteam AS team, p.defteam, p.season, p.week,
         IF(f.is_play_action, 1, 0) AS pa,
         IF(p.sack = 1 OR f.is_qb_out_of_pocket OR f.is_throw_away, 1, 0)
           AS pressured
  FROM `${raw}.pbp` p
  JOIN `${raw}.ftn_charting` f
    ON f.nflverse_game_id = p.game_id AND f.nflverse_play_id = p.play_id
  WHERE p.pass = 1 AND p.posteam IS NOT NULL
),
off_tw AS (
  SELECT team, season, week, SUM(pa) AS pa, COUNT(*) AS n
  FROM plays GROUP BY team, season, week
),
def_tw AS (
  SELECT defteam AS team, season, week, SUM(pressured) AS pr, COUNT(*) AS n
  FROM plays WHERE defteam IS NOT NULL GROUP BY defteam, season, week
),
upcoming AS (
  SELECT DISTINCT team, season, week
  FROM `${features}.player_week_role`
  WHERE is_upcoming
),
off_tw_with_upcoming AS (
  SELECT * FROM off_tw
  UNION ALL
  SELECT u.team, u.season, u.week,
         CAST(NULL AS INT64) AS pa, CAST(NULL AS INT64) AS n
  FROM upcoming u
  WHERE NOT EXISTS (
    SELECT 1 FROM off_tw prior
    WHERE prior.team = u.team AND prior.season = u.season
      AND prior.week = u.week
  )
),
def_tw_with_upcoming AS (
  SELECT * FROM def_tw
  UNION ALL
  SELECT u.team, u.season, u.week,
         CAST(NULL AS INT64) AS pr, CAST(NULL AS INT64) AS n
  FROM upcoming u
  WHERE NOT EXISTS (
    SELECT 1 FROM def_tw prior
    WHERE prior.team = u.team AND prior.season = u.season
      AND prior.week = u.week
  )
),
off_roll AS (
  SELECT team, season, week,
         SAFE_DIVIDE(SUM(pa) OVER w, SUM(n) OVER w) AS pa_rate_l6
  FROM off_tw_with_upcoming
  WINDOW w AS (PARTITION BY team ORDER BY season, week
               ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING)
),
def_roll AS (
  SELECT team, season, week,
         SAFE_DIVIDE(SUM(pr) OVER w, SUM(n) OVER w) AS def_pressure_rate_l6
  FROM def_tw_with_upcoming
  WINDOW w AS (PARTITION BY team ORDER BY season, week
               ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING)
)
SELECT COALESCE(o.team, d.team) AS team,
       COALESCE(o.season, d.season) AS season,
       COALESCE(o.week, d.week) AS week,
       o.pa_rate_l6, d.def_pressure_rate_l6
FROM off_roll o
FULL OUTER JOIN def_roll d USING (team, season, week);
