-- XFP + schedule-context candidates (2026-08-03, vendor round-6 /
-- research round-5 triage). All EXTRA_FEATURES-gated; leakage-safe.
--
-- xfp_l4: expected fantasy points from OPPORTUNITY alone — each target
-- valued at a league-average rate for its (air-yards band x field zone)
-- bucket, each carry for its (field zone) bucket. Bucket rates are
-- computed ONCE from 2014-2018 seasons only (fixed priors, so rows for
-- 2019+ replays are point-in-time; earlier seasons see mild in-sample
-- rates, acceptable for a candidate feature). The Fantasy Points Data
-- lineage: opportunity is sticky, efficiency is noise.
--
-- net_rest_diff: own days_rest minus opponent's (we carried only own).
-- body_clock_offset: hours between kickoff local time and the visiting
-- team's home-timezone body clock (Harvard/Stanford west-coast night
-- effect); approximated from schedules' gametime + a team-timezone map.
CREATE OR REPLACE TABLE `${features}.player_week_xfp` AS
WITH bucket_rates AS (
  SELECT * FROM (
    SELECT
      CASE WHEN air_yards >= 20 THEN 'deep'
           WHEN air_yards >= 10 THEN 'mid' ELSE 'short' END AS ab,
      CASE WHEN yardline_100 <= 10 THEN 'rz10'
           WHEN yardline_100 <= 20 THEN 'rz20' ELSE 'field' END AS fz,
      -- DK PPR points per target in bucket
      AVG(COALESCE(yards_gained, 0) * 0.1
          + IF(complete_pass = 1, 1.0, 0.0)
          + IF(pass_touchdown = 1, 6.0, 0.0)) AS fp_per_tgt
    FROM `${raw}.pbp`
    WHERE season BETWEEN 2014 AND 2018 AND pass = 1
      AND air_yards IS NOT NULL
    GROUP BY ab, fz)
),
carry_rates AS (
  SELECT
    CASE WHEN yardline_100 <= 5 THEN 'gl'
         WHEN yardline_100 <= 20 THEN 'rz' ELSE 'field' END AS fz,
    AVG(COALESCE(yards_gained, 0) * 0.1
        + IF(rush_touchdown = 1, 6.0, 0.0)) AS fp_per_carry
  FROM `${raw}.pbp`
  WHERE season BETWEEN 2014 AND 2018 AND rush = 1
  GROUP BY fz
),
tgt_xfp AS (
  SELECT p.receiver_player_id AS gsis_id, p.season, p.week,
         SUM(br.fp_per_tgt) AS xfp_rec
  FROM `${raw}.pbp` p
  JOIN bucket_rates br
    ON br.ab = CASE WHEN p.air_yards >= 20 THEN 'deep'
                    WHEN p.air_yards >= 10 THEN 'mid' ELSE 'short' END
   AND br.fz = CASE WHEN p.yardline_100 <= 10 THEN 'rz10'
                    WHEN p.yardline_100 <= 20 THEN 'rz20' ELSE 'field' END
  WHERE p.pass = 1 AND p.receiver_player_id IS NOT NULL
    AND p.air_yards IS NOT NULL
  GROUP BY gsis_id, season, week
),
carry_xfp AS (
  SELECT p.rusher_player_id AS gsis_id, p.season, p.week,
         SUM(cr.fp_per_carry) AS xfp_rush
  FROM `${raw}.pbp` p
  JOIN carry_rates cr
    ON cr.fz = CASE WHEN p.yardline_100 <= 5 THEN 'gl'
                    WHEN p.yardline_100 <= 20 THEN 'rz' ELSE 'field' END
  WHERE p.rush = 1 AND p.rusher_player_id IS NOT NULL
  GROUP BY gsis_id, season, week
),
weekly AS (
  SELECT COALESCE(t.gsis_id, c.gsis_id) AS gsis_id,
         COALESCE(t.season, c.season) AS season,
         COALESCE(t.week, c.week) AS week,
         COALESCE(t.xfp_rec, 0) + COALESCE(c.xfp_rush, 0) AS xfp
  FROM tgt_xfp t
  FULL OUTER JOIN carry_xfp c USING (gsis_id, season, week)
)
SELECT gsis_id, season, week,
       AVG(xfp) OVER (PARTITION BY gsis_id, season ORDER BY week
                      ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS xfp_l4
FROM weekly;

CREATE OR REPLACE TABLE `${features}.team_week_schedule_ctx` AS
WITH tz AS (
  SELECT team, offset_hours FROM UNNEST([
    STRUCT('SEA' AS team, -3 AS offset_hours), ('SF', -3), ('LA', -3),
    ('LAC', -3), ('LV', -3), ('ARI', -2), ('DEN', -2),
    ('DAL', -1), ('HOU', -1), ('KC', -1), ('MIN', -1), ('GB', -1),
    ('CHI', -1), ('NO', -1), ('TEN', -1),
    ('BUF', 0), ('MIA', 0), ('NE', 0), ('NYJ', 0), ('NYG', 0),
    ('PHI', 0), ('PIT', 0), ('BAL', 0), ('CIN', 0), ('CLE', 0),
    ('WAS', 0), ('CAR', 0), ('ATL', 0), ('JAX', 0), ('TB', 0),
    ('DET', 0), ('IND', 0)])
)
SELECT s.team, s.season, s.week,
       s.days_rest - opp.days_rest AS net_rest_diff,
       -- ET kickoff hour + visitor's tz offset = body-clock hour
       CAST(SPLIT(sc.gametime, ':')[SAFE_OFFSET(0)] AS INT64)
         + COALESCE(z.offset_hours, 0) AS body_clock_hour
FROM `${features}.schedule_long` s
JOIN `${features}.schedule_long` opp
  ON opp.game_id = s.game_id AND opp.team = s.opponent
LEFT JOIN `${raw}.schedules` sc ON sc.game_id = s.game_id
LEFT JOIN tz z ON z.team = s.team;
