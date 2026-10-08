"""Task 2b: do QB/RB/WR/TE stat lines silently lose their position (no player_week_role row)?"""
import sys; sys.path.insert(0, ".")
from bqh import q
print("== actuals rows WITH a stat line, by season: role row present? position from the season roster for those without ==")
print(q("""
WITH a AS (SELECT a.*, r.position rpos FROM `nfl_features.player_week_actuals` a
           LEFT JOIN `nfl_features.player_week_role` r ON r.gsis_id = a.gsis_id AND r.season = a.season AND r.week = a.week
           WHERE a.season BETWEEN 2014 AND 2026 AND a.has_stat_line),
 sp AS (SELECT gsis_id, season, ANY_VALUE(position) pos FROM `nfl_raw.rosters_weekly` WHERE gsis_id IS NOT NULL GROUP BY 1, 2)
SELECT a.season, COUNT(*) stat_lines, COUNTIF(a.rpos IS NOT NULL) with_role,
       COUNTIF(a.rpos IS NULL AND sp.pos IN ('QB','RB','WR','TE','FB','HB')) skill_pos_without_role,
       ROUND(SUM(IF(a.rpos IS NULL AND sp.pos IN ('QB','RB','WR','TE','FB','HB'), a.dk_points, 0)), 0) dk_lost_skill,
       ROUND(SUM(IF(a.rpos IS NOT NULL, a.dk_points, 0)), 0) dk_with_role,
       COUNTIF(a.rpos IS NULL AND sp.pos IS NULL) no_roster_at_all,
       STRING_AGG(DISTINCT IF(a.rpos IS NULL, sp.pos, NULL), ',') other_positions
FROM a LEFT JOIN sp USING (gsis_id, season) GROUP BY 1 ORDER BY 1""").to_string(index=False))
print("\n== TE stat lines specifically lost: TEs (season roster) with a stat line but no role row ==")
print(q("""
WITH a AS (SELECT a.*, r.position rpos FROM `nfl_features.player_week_actuals` a
           LEFT JOIN `nfl_features.player_week_role` r ON r.gsis_id = a.gsis_id AND r.season = a.season AND r.week = a.week
           WHERE a.season BETWEEN 2014 AND 2026 AND a.has_stat_line),
 sp AS (SELECT gsis_id, season, ANY_VALUE(position) pos FROM `nfl_raw.rosters_weekly` WHERE gsis_id IS NOT NULL GROUP BY 1, 2)
SELECT a.season, sp.pos, COUNT(*) n_lost, ROUND(AVG(a.dk_points), 2) mean_dk, COUNTIF(a.dk_points >= 20) n_20plus
FROM a JOIN sp USING (gsis_id, season) WHERE a.rpos IS NULL AND sp.pos IN ('QB','RB','WR','TE','FB')
GROUP BY 1, 2 ORDER BY 1, 2""").to_string(index=False))
print("\n== role-table position vs the same week's roster position (mismatch counts) ==")
print(q("""
SELECT r.season, COUNT(*) n, COUNTIF(r.position != w.position) mismatch
FROM `nfl_features.player_week_role` r JOIN (SELECT gsis_id, season, week, ANY_VALUE(position) position FROM `nfl_raw.rosters_weekly` GROUP BY 1,2,3) w
USING (gsis_id, season, week) WHERE r.season BETWEEN 2014 AND 2026 GROUP BY 1 ORDER BY 1""").to_string(index=False))
