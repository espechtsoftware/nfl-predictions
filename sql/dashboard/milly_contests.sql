-- One main-slate Classic Millionaire per (season, week).
-- Primary source: DraftKings' contest lobby polls (dk_contest_fills), which
-- know the contest and its draft group before lock; the largest
-- "Fantasy Football Millionaire" that is not a satellite, showdown, MEGA or
-- split slate wins, and its Sunday start date names the NFL week.
-- Fallback for weeks the lobby polls missed: the largest imported standings
-- named like a Millionaire (the Week-3 import is labelled "milly20").
WITH fills AS (
  SELECT CAST(contest_id AS STRING) AS contest_id,
         ANY_VALUE(draft_group_id) AS draft_group_id,
         ANY_VALUE(name) AS contest_name,
         MAX(max_entries) AS field_size,
         MIN(start_time) AS start_time
  FROM `${raw}.dk_contest_fills_nfl`
  WHERE REGEXP_CONTAINS(name, r'Fantasy Football Millionaire')
    AND NOT REGEXP_CONTAINS(name, r'(?i)satellite|supersat|showdown|mega|ticket|qualifier|\(')
  GROUP BY 1
),
weeks AS (
  SELECT DISTINCT CAST(season AS INT64) AS season, CAST(week AS INT64) AS week, gameday
  FROM `${raw}.schedules`
  WHERE game_type = 'REG'
),
fills_week AS (
  SELECT w.season, w.week, f.*
  FROM fills f
  JOIN weeks w
    ON w.gameday = FORMAT_DATE('%Y-%m-%d', DATE(f.start_time, 'America/New_York'))
  QUALIFY ROW_NUMBER() OVER (PARTITION BY w.season, w.week
                             ORDER BY f.field_size DESC, f.contest_id) = 1
),
entries AS (
  SELECT season, week, contest_id, ANY_VALUE(contest_name) AS contest_name,
         COUNT(DISTINCT entry_id) AS n_entries
  FROM `${raw}.contest_entries`
  GROUP BY 1, 2, 3
),
entries_week AS (
  SELECT * FROM entries
  WHERE REGEXP_CONTAINS(contest_name, r'(?i)millionaire|^milly')
    AND NOT REGEXP_CONTAINS(contest_name, r'(?i)\(thu|mega|\$555|satellite|supersat|showdown')
  QUALIFY ROW_NUMBER() OVER (PARTITION BY season, week
                             ORDER BY n_entries DESC, contest_id) = 1
)
-- When the lobby's contest has no imported standings but a Millionaire-named
-- import exists for the week, the import wins (its contest_id is the one the
-- standings carry); lobby_contest_id / standings_contest_id keep both so the
-- callers can print the mismatch.
SELECT
  COALESCE(f.season, e.season) AS season,
  COALESCE(f.week, e.week) AS week,
  CASE WHEN nf.n_entries IS NOT NULL THEN f.contest_id
       ELSE COALESCE(e.contest_id, f.contest_id) END AS contest_id,
  CASE WHEN nf.n_entries IS NOT NULL THEN f.contest_name
       ELSE COALESCE(e.contest_name, f.contest_name) END AS contest_name,
  f.draft_group_id,
  f.start_time,
  f.field_size,
  CASE WHEN nf.n_entries IS NOT NULL THEN nf.n_entries ELSE e.n_entries END AS n_entries,
  f.contest_id AS lobby_contest_id,
  e.contest_id AS standings_contest_id
FROM fills_week f
FULL OUTER JOIN entries_week e
  ON e.season = f.season AND e.week = f.week
LEFT JOIN entries nf
  ON nf.season = f.season AND nf.week = f.week AND nf.contest_id = f.contest_id
