-- Auditor's own team-game panel, 2013-2026 REG (2013 only as cross-season history for 2014 week 1-3 windows).
-- Team codes normalized to the modern convention in EVERY source (schedules carry OAK/SD/STL; pbp/actuals carry LV/LAC/LA).
WITH sched AS (
  SELECT season, week, game_id, weekday, total_line, spread_line, result,
         CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC' WHEN 'STL' THEN 'LA' ELSE home_team END home,
         CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC' WHEN 'STL' THEN 'LA' ELSE away_team END away
  FROM `nfl_raw.schedules` WHERE game_type = 'REG' AND season BETWEEN 2013 AND 2026),
tg AS (
  SELECT season, week, game_id, weekday, home team, away opp, (total_line + spread_line) / 2 itt, result IS NOT NULL played FROM sched
  UNION ALL
  SELECT season, week, game_id, weekday, away, home, (total_line - spread_line) / 2, result IS NOT NULL FROM sched),
-- player-game rows with position (exact-week roster position via player_week_role) and DK salary
pg AS (
  SELECT a.season, a.week, a.team, a.gsis_id, r.position pos, a.dk_points dk, IFNULL(a.targets, 0) tgt, IFNULL(a.carries, 0) car,
         IFNULL(a.pass_attempts, 0) att, a.has_stat_line hs, s.salary
  FROM `nfl_features.player_week_actuals` a
  JOIN `nfl_features.player_week_role` r ON r.gsis_id = a.gsis_id AND r.season = a.season AND r.week = a.week
  LEFT JOIN `nfl_features.dk_salary_week` s ON s.gsis_id = a.gsis_id AND s.season = a.season AND s.week = a.week
  WHERE r.position IN ('QB', 'RB', 'WR', 'TE') AND a.season BETWEEN 2013 AND 2026),
off AS (
  SELECT season, week, team,
    -- hindsight definitions (the reviewer's): best scorer at the position in that game
    MAX(IF(pos = 'QB', dk, NULL)) qb_max,
    MAX(IF(pos = 'TE', dk, NULL)) te1_max,
    MAX(IF(pos = 'RB', dk, NULL)) rb1_max,
    ARRAY_AGG(IF(pos = 'WR', dk, NULL) IGNORE NULLS ORDER BY dk DESC LIMIT 2) wr_max2,
    -- starting QB = most pass attempts
    ARRAY_AGG(IF(pos = 'QB' AND hs, dk, NULL) IGNORE NULLS ORDER BY att DESC, dk DESC LIMIT 1)[SAFE_OFFSET(0)] qb_main,
    -- pre-lock definitions: highest DK salary at the position among players with a stat line that game
    ARRAY_AGG(IF(pos = 'TE' AND hs AND salary IS NOT NULL, dk, NULL) IGNORE NULLS ORDER BY salary DESC, gsis_id LIMIT 1)[SAFE_OFFSET(0)] te1_sal,
    ARRAY_AGG(IF(pos = 'RB' AND hs AND salary IS NOT NULL, dk, NULL) IGNORE NULLS ORDER BY salary DESC, gsis_id LIMIT 1)[SAFE_OFFSET(0)] rb1_sal,
    ARRAY_AGG(IF(pos = 'QB' AND hs AND salary IS NOT NULL, dk, NULL) IGNORE NULLS ORDER BY salary DESC, gsis_id LIMIT 1)[SAFE_OFFSET(0)] qb_sal,
    ARRAY_AGG(IF(pos = 'WR' AND hs AND salary IS NOT NULL, dk, NULL) IGNORE NULLS ORDER BY salary DESC, gsis_id LIMIT 2) wr_sal2,
    ARRAY_AGG(IF(pos = 'TE' AND hs AND salary IS NOT NULL, gsis_id, NULL) IGNORE NULLS ORDER BY salary DESC, gsis_id LIMIT 1)[SAFE_OFFSET(0)] te1_sal_id,
    SUM(IF(pos = 'TE', dk, 0)) te_grp, SUM(IF(pos = 'WR', dk, 0)) wr_grp, SUM(IF(pos = 'RB', dk, 0)) rb_grp, SUM(IF(pos = 'QB', dk, 0)) qb_grp,
    SUM(IF(pos = 'TE', tgt, 0)) te_tgt, SUM(IF(pos = 'WR', tgt, 0)) wr_tgt, SUM(IF(pos = 'RB', tgt, 0)) rb_tgt, SUM(tgt) tm_tgt,
    SUM(IF(pos = 'RB', car, 0)) rb_car, SUM(car) tm_car,
    COUNTIF(pos = 'TE' AND hs) n_te_played
  FROM pg GROUP BY 1, 2, 3),
-- per-game pass defense (pbp): EPA per dropback allowed, one row per defense-game
dgame AS (
  SELECT season, week, defteam d, AVG(IF(qb_dropback = 1, epa, NULL)) epa_db, COUNTIF(qb_dropback = 1 AND epa IS NOT NULL) n_db
  FROM `nfl_raw.pbp` WHERE season_type = 'REG' AND defteam IS NOT NULL AND season BETWEEN 2013 AND 2026 GROUP BY 1, 2, 3),
dwin AS (
  SELECT season, week, d, epa_db, n_db,
    AVG(epa_db) OVER w_in6 epa_in6, COUNT(epa_db) OVER w_in6 n_in6,                     -- production training definition (017): within season, previous 6 games
    AVG(epa_db) OVER w_inall epa_inall, COUNT(epa_db) OVER w_inall n_inall,              -- season to date
    AVG(epa_db) OVER w_x6 epa_x6, COUNT(epa_db) OVER w_x6 n_x6,                          -- across seasons, previous 6 games
    SUM(epa_db * n_db) OVER w_x6 / SUM(n_db) OVER w_x6 epa_x6_pw                         -- across seasons, play-weighted
  FROM dgame
  WINDOW w_in6 AS (PARTITION BY d, season ORDER BY week ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING),
         w_inall AS (PARTITION BY d, season ORDER BY week ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
         w_x6 AS (PARTITION BY d ORDER BY season, week ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING)),
dwin2 AS (
  SELECT *, LAG(epa_in6) OVER (PARTITION BY d, season ORDER BY week) epa_stale,            -- production LIVE/frame definition (023 as-of join): one game stale
            LAG(n_in6) OVER (PARTITION BY d, season ORDER BY week) n_stale
  FROM dwin),
-- DK points allowed by position (the reviewer's measure, built from actuals with normalized codes)
allowed AS (
  SELECT o.season, o.week, t.opp d, o.wr_grp, o.te_grp, o.rb_grp, o.qb_main
  FROM off o JOIN tg t ON t.season = o.season AND t.week = o.week AND t.team = o.team),
awin AS (
  SELECT season, week, d,
    AVG(wr_grp) OVER w wr_al, AVG(te_grp) OVER w te_al, AVG(rb_grp) OVER w rb_al, COUNT(*) OVER w n_al,
    AVG(te_grp) OVER wx te_al_x8, AVG(wr_grp) OVER wx wr_al_x8, AVG(rb_grp) OVER wx rb_al_x8
  FROM allowed
  WINDOW w AS (PARTITION BY d, season ORDER BY week ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
         wx AS (PARTITION BY d ORDER BY season, week ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING))
SELECT t.season, t.week, t.game_id, t.weekday, t.team, t.opp, t.itt,
  o.* EXCEPT (season, week, team),
  dw.epa_db opp_epa_this_game, dw.epa_in6, dw.n_in6, dw.epa_inall, dw.n_inall, dw.epa_x6, dw.n_x6, dw.epa_x6_pw, dw.epa_stale, dw.n_stale,
  aw.wr_al, aw.te_al, aw.rb_al, aw.n_al, aw.te_al_x8, aw.wr_al_x8, aw.rb_al_x8
FROM tg t
LEFT JOIN off o ON o.season = t.season AND o.week = t.week AND o.team = t.team
LEFT JOIN dwin2 dw ON dw.season = t.season AND dw.week = t.week AND dw.d = t.opp
LEFT JOIN awin aw ON aw.season = t.season AND aw.week = t.week AND aw.d = t.opp
WHERE t.played
