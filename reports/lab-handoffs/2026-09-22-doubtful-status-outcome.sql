-- Did DK-Doubtful players actually play? 2026 classic slates, weeks 1-2 only
-- (weeks whose games have been played -- weekly_stats/snap_counts stop at 2).
-- Availability is measured by SNAPS, not by the presence of a stat line:
-- weekly_stats omits a player who suited up and recorded nothing, which would
-- otherwise be scored identically to an inactive.
WITH wk AS (
  SELECT DISTINCT season, week, DATE(gameday) AS gameday
  FROM `nfl-predictions-503414.nfl_raw.schedules`
  WHERE season = 2026 AND game_type = 'REG'
),
sal AS (
  SELECT s.dk_player_id, s.display_name, s.position, s.salary, s.status,
         s.pulled_at, s.game_start, wk.season, wk.week,
         REGEXP_REPLACE(LOWER(s.display_name), r"[^a-z]", "") AS key_name
  FROM `nfl-predictions-503414.nfl_raw.dk_salaries` s
  JOIN wk ON wk.gameday = DATE(s.game_start, 'America/New_York')
  WHERE s.slate_type = 'classic'
    AND s.pulled_at < s.game_start
    AND s.position IN ('QB','RB','WR','TE')
    AND wk.week <= 2
),
per_player AS (
  SELECT season, week, key_name,
         ANY_VALUE(display_name) AS display_name,
         LOGICAL_OR(status = 'D') AS ever_d,
         LOGICAL_OR(status = 'Q') AS ever_q,
         LOGICAL_OR(status IN ('O','OUT','IR')) AS ever_out,
         MAX(salary) AS salary,
         ARRAY_AGG(status ORDER BY pulled_at DESC LIMIT 1)[OFFSET(0)] AS final_status
  FROM sal GROUP BY season, week, key_name
),
snaps AS (
  SELECT season, week,
         REGEXP_REPLACE(LOWER(player), r"[^a-z]", "") AS key_name,
         SUM(COALESCE(offense_snaps,0)) AS off_snaps,
         SUM(COALESCE(st_snaps,0)) AS st_snaps
  FROM `nfl-predictions-503414.nfl_raw.snap_counts`
  WHERE season = 2026 AND game_type = 'REG' GROUP BY season, week, key_name
),
pts AS (
  SELECT season, week,
         REGEXP_REPLACE(LOWER(player_display_name), r"[^a-z]", "") AS key_name,
         SUM(fantasy_points_ppr) AS ppr
  FROM `nfl-predictions-503414.nfl_raw.weekly_stats`
  WHERE season = 2026 AND season_type = 'REG' GROUP BY season, week, key_name
),
j AS (
  SELECT p.*,
         COALESCE(sn.off_snaps,0) + COALESCE(sn.st_snaps,0) > 0 AS played,
         COALESCE(sn.off_snaps,0) AS off_snaps,
         COALESCE(pt.ppr, 0) AS ppr,
         CASE WHEN p.ever_out THEN 'OUT/IR at some pull'
              WHEN p.ever_d   THEN 'DOUBTFUL (never OUT)'
              WHEN p.ever_q   THEN 'QUESTIONABLE (never D/OUT)'
              ELSE 'no designation' END AS cohort
  FROM per_player p
  LEFT JOIN snaps sn USING (season, week, key_name)
  LEFT JOIN pts  pt USING (season, week, key_name)
)
SELECT cohort,
       COUNT(*) AS player_weeks,
       COUNTIF(played) AS played_n,
       ROUND(100*COUNTIF(played)/COUNT(*),1) AS pct_played,
       ROUND(AVG(salary),0) AS mean_salary,
       ROUND(AVG(ppr),2) AS mean_ppr,
       ROUND(AVG(IF(played, ppr, NULL)),2) AS mean_ppr_if_played,
       ROUND(1000*AVG(ppr)/AVG(salary),3) AS ppr_per_1k
FROM j GROUP BY cohort ORDER BY player_weeks DESC
