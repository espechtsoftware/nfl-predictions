-- Offensive-line injuries (2026-08-01; candidate, not in NUMERIC_FEATURES):
-- the public prices skill-player injuries; pass-protection losses (LT/C/RT
-- out) change sack rate, time to throw, and depth of target for EVERY skill
-- player on the team.
--
-- O-22 (d) (2026-10-05): rebuilt point in time; replaces 017d. 017d counted
-- raw nflverse `report_status = 'Out'` rows with no lock filter (5-18
-- post-lock Out team-weeks a season in 2014-24) and had a row only for
-- team-weeks with an Out lineman, which 021/023 COALESCEd to 0, so a week with
-- no admissible report (all of 2025: NULL date_modified, Data deficiency log
-- 2026-08-15) read as "no lineman out". Now:
--   * Out designations come from `${features}.player_week_injury` (018: modified
--     or collected at/before the Sunday-main lock), positions from the latest
--     weekly roster row at or before the week (the roster feed lags the
--     upcoming week);
--   * one row per player_week_usage team-week: the count of Out linemen where
--     the injury table covers that season-week (0 when none), NULL where it
--     does not cover it.
CREATE OR REPLACE TABLE `${features}.team_week_ol_out` AS
WITH pit_weeks AS (
  SELECT DISTINCT season, week FROM `${features}.player_week_injury`
), outs AS (
  SELECT i.gsis_id, i.season, i.week
  FROM `${features}.player_week_injury` i
  WHERE i.injury_status = 'Out'
), roster AS (
  SELECT o.season, o.week, r.team, r.position, o.gsis_id
  FROM outs o
  JOIN `${raw}.rosters_weekly` r
    ON r.gsis_id = o.gsis_id AND r.season = o.season AND r.week <= o.week
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY o.gsis_id, o.season, o.week ORDER BY r.week DESC, r.team) = 1
), ol_outs AS (
  SELECT team, season, week, COUNT(DISTINCT gsis_id) AS n
  FROM roster
  WHERE position IN ('OL', 'T', 'G', 'C')
  GROUP BY 1, 2, 3
), spine AS (
  SELECT DISTINCT team, season, week
  FROM `${features}.player_week_usage`
  WHERE team IS NOT NULL
)
SELECT s.team, s.season, s.week,
       IF(pw.season IS NULL, NULL, IFNULL(o.n, 0)) AS team_ol_out
FROM spine s
LEFT JOIN pit_weeks pw ON pw.season = s.season AND pw.week = s.week
LEFT JOIN ol_outs o ON o.team = s.team AND o.season = s.season AND o.week = s.week;
