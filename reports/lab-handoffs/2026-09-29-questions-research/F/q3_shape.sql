-- F1 shapes: per-user-week stack / bring-back / games / QB-salary via dk_salaries teams (main-slate draft groups)
WITH sal AS (
  SELECT wk, display_name, ANY_VALUE(team_abbr) AS team, ANY_VALUE(position) AS pos, ANY_VALUE(salary) AS salary,
         ANY_VALUE(game_start) AS game_start
  FROM (
    SELECT CASE draft_group_id WHEN 151307 THEN 1 WHEN 153428 THEN 2 WHEN 153769 THEN 3 END AS wk,
           display_name, team_abbr, position, salary, game_start,
           ROW_NUMBER() OVER (PARTITION BY draft_group_id, display_name ORDER BY pulled_at DESC) AS rn
    FROM nfl_raw.dk_salaries WHERE season=2026 AND draft_group_id IN (151307,153428,153769)
  ) WHERE rn = 1 GROUP BY 1,2
), e AS (
  SELECT week, contest_id, entry_id, rank, points, lineup_slots_json,
         REGEXP_REPLACE(entry_name, r'\s*\(\d+/\d+\)\s*$', '') AS user,
         COUNT(*) OVER (PARTITION BY contest_id) AS n_field
  FROM nfl_raw.contest_entries WHERE contest_id IN ('193028206','195648007','195905122')
), pl AS (
  SELECT e.week, e.user, e.entry_id, JSON_VALUE(j,'$.slot') AS slot, JSON_VALUE(j,'$.player') AS player,
         s.team, s.pos, s.salary, s.game_start,
         -- opponent via same game_start + schedule not available here; game id approximated by team pair below
         CASE WHEN s.team IS NULL THEN 1 ELSE 0 END AS unmatched
  FROM e, UNNEST(JSON_EXTRACT_ARRAY(e.lineup_slots_json)) AS j
  LEFT JOIN sal s ON s.wk = e.week AND s.display_name = JSON_VALUE(j,'$.player')
), sched AS (
  SELECT season, week, home_team AS team, CONCAT(away_team,'@',home_team) AS game FROM nfl_raw.schedules WHERE season=2026 AND week<=3
  UNION ALL
  SELECT season, week, away_team AS team, CONCAT(away_team,'@',home_team) AS game FROM nfl_raw.schedules WHERE season=2026 AND week<=3
), pl2 AS (
  SELECT pl.*, sc.game FROM pl LEFT JOIN sched sc ON sc.week = pl.week AND sc.team = pl.team
), row_feats AS (
  SELECT week, user, entry_id,
    MAX(CASE WHEN slot='QB' THEN team END) AS qb_team,
    MAX(CASE WHEN slot='QB' THEN game END) AS qb_game,
    MAX(CASE WHEN slot='QB' THEN salary END) AS qb_sal,
    MAX(CASE WHEN slot='QB' THEN player END) AS qb,
    SUM(unmatched) AS n_unmatched,
    COUNT(DISTINCT game) AS n_games,
    COUNTIF(pos='TE') AS n_te,
    COUNTIF(salary>=7000) AS n_7k,
    ARRAY_AGG(STRUCT(slot, player, team, pos, game)) AS ps
  FROM pl2 GROUP BY 1,2,3
), row2 AS (
  SELECT week, user, entry_id, qb, qb_sal, n_unmatched, n_games, n_te, n_7k,
    (SELECT COUNTIF(p.team = qb_team AND p.pos IN ('WR','TE')) FROM UNNEST(ps) p) AS stk,
    (SELECT COUNTIF(p.game = qb_game AND p.team != qb_team AND p.pos IN ('WR','TE','RB')) FROM UNNEST(ps) p) AS bb,
    (SELECT MAX(c) FROM (SELECT COUNT(*) c FROM UNNEST(ps) p WHERE p.pos != 'DST' GROUP BY p.game)) AS max_game
  FROM row_feats
)
SELECT week, user, COUNT(*) AS n, COUNT(DISTINCT qb) AS n_qb, ROUND(AVG(qb_sal)) AS qb_sal,
       ROUND(AVG(stk),3) AS stk, ROUND(AVG(IF(stk>=1,1,0)),3) AS stk1_rate, ROUND(AVG(IF(stk>=2,1,0)),3) AS stk2_rate,
       ROUND(AVG(IF(bb>=1,1,0)),3) AS bb_rate, ROUND(AVG(n_games),3) AS n_games, ROUND(AVG(max_game),3) AS max_game,
       ROUND(AVG(n_te),3) AS n_te, ROUND(AVG(n_7k),3) AS n_7k, SUM(n_unmatched) AS n_unmatched
FROM row2 GROUP BY 1,2
