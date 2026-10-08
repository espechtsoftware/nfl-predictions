"""Task 2a: team abbreviations per source and season; join coverage between pbp, schedules and actuals."""
import sys; sys.path.insert(0, ".")
from bqh import q
print("== team codes that do not appear in all three sources, by season ==")
d = q("""
WITH s AS (SELECT DISTINCT season, t FROM `nfl_raw.schedules`, UNNEST([home_team, away_team]) t WHERE game_type = 'REG' AND season BETWEEN 2014 AND 2026),
 p AS (SELECT DISTINCT season, defteam t FROM `nfl_raw.pbp` WHERE season_type = 'REG' AND season BETWEEN 2014 AND 2026 AND defteam IS NOT NULL),
 a AS (SELECT DISTINCT season, team t FROM `nfl_features.player_week_actuals` WHERE season BETWEEN 2014 AND 2026)
SELECT season, t, LOGICAL_OR(src = 's') in_sched, LOGICAL_OR(src = 'p') in_pbp, LOGICAL_OR(src = 'a') in_actuals
FROM (SELECT season, t, 's' src FROM s UNION ALL SELECT season, t, 'p' FROM p UNION ALL SELECT season, t, 'a' FROM a)
GROUP BY 1, 2 HAVING NOT (in_sched AND in_pbp AND in_actuals) ORDER BY 1, 2""")
print(d.to_string(index=False) if len(d) else "(none: every team code is present in all three sources in every season)")
print("\n== relocated / renamed franchises: codes per season in schedules ==")
print(q("""SELECT season, STRING_AGG(DISTINCT t, ',' ORDER BY t) codes FROM `nfl_raw.schedules`, UNNEST([home_team, away_team]) t
WHERE game_type = 'REG' AND season BETWEEN 2014 AND 2026 AND t IN ('LA','LAR','STL','SD','LAC','OAK','LV','JAX','JAC','WAS','WSH')
GROUP BY 1 ORDER BY 1""").to_string(index=False))
print("\n== actuals team-weeks that do NOT join to a REG schedule game (season, week, team as home/away) ==")
print(q("""
WITH tg AS (SELECT season, week, home_team team FROM `nfl_raw.schedules` WHERE game_type='REG' UNION ALL SELECT season, week, away_team FROM `nfl_raw.schedules` WHERE game_type='REG'),
 aw AS (SELECT DISTINCT season, week, team FROM `nfl_features.player_week_actuals` WHERE season BETWEEN 2014 AND 2026)
SELECT aw.season, COUNT(*) team_weeks, COUNTIF(tg.team IS NULL) unmatched, STRING_AGG(IF(tg.team IS NULL, CONCAT(aw.team, 'w', CAST(aw.week AS STRING)), NULL), ' ' LIMIT 12) examples
FROM aw LEFT JOIN tg USING (season, week, team) GROUP BY 1 ORDER BY 1""").to_string(index=False))
print("\n== pbp defense-weeks that do NOT join to a schedule game, and schedule games (played) with no pbp dropbacks ==")
print(q("""
WITH tg AS (SELECT season, week, home_team team, away_team opp, game_id FROM `nfl_raw.schedules` WHERE game_type='REG' AND result IS NOT NULL
            UNION ALL SELECT season, week, away_team, home_team, game_id FROM `nfl_raw.schedules` WHERE game_type='REG' AND result IS NOT NULL),
 dw AS (SELECT season, week, defteam d, COUNT(*) n FROM `nfl_raw.pbp` WHERE season_type='REG' AND qb_dropback=1 AND epa IS NOT NULL AND season BETWEEN 2014 AND 2026 GROUP BY 1,2,3)
SELECT tg.season, COUNT(*) played_team_games, COUNTIF(dw.d IS NULL) no_pbp_for_defense, MIN(dw.n) min_dropbacks_faced, MAX(dw.n) max_dropbacks_faced
FROM tg LEFT JOIN dw ON dw.season = tg.season AND dw.week = tg.week AND dw.d = tg.team WHERE tg.season BETWEEN 2014 AND 2026 GROUP BY 1 ORDER BY 1""").to_string(index=False))
print("\n== do pbp game_ids match schedule game_ids (and weeks)? ==")
print(q("""
WITH pg AS (SELECT DISTINCT season, week, game_id FROM `nfl_raw.pbp` WHERE season_type='REG' AND season BETWEEN 2014 AND 2026),
 sg AS (SELECT season, week, game_id FROM `nfl_raw.schedules` WHERE game_type='REG' AND season BETWEEN 2014 AND 2026)
SELECT pg.season, COUNT(*) pbp_games, COUNTIF(sg.game_id IS NULL) not_in_sched, COUNTIF(sg.week != pg.week) week_mismatch
FROM pg LEFT JOIN sg USING (game_id) GROUP BY 1 ORDER BY 1""").to_string(index=False))
