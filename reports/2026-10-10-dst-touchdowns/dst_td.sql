-- team-week DST touchdowns (defensive return TDs + punt / kickoff return TDs) and the pre-week predictors, 2022-2026 REG
WITH plays AS (
  SELECT season, week, game_id, posteam, defteam, td_team, play_type, CAST(touchdown AS INT64) td, CAST(return_touchdown AS INT64) rtd,
         CAST(interception AS INT64) intc, CAST(fumble_lost AS INT64) fl, home_team, away_team, spread_line, total_line
  FROM `nfl-predictions-503414.nfl_raw.pbp` WHERE season BETWEEN 2022 AND 2026 AND season_type = 'REG' AND posteam IS NOT NULL),
games AS (
  SELECT DISTINCT season, week, game_id, home_team, away_team, spread_line, total_line FROM plays),
tw AS (   -- team-week rows (both sides of every game)
  SELECT season, week, game_id, home_team team, away_team opp, total_line, spread_line, (total_line + spread_line) / 2 AS team_implied,
         (total_line - spread_line) / 2 AS opp_implied FROM games
  UNION ALL
  SELECT season, week, game_id, away_team, home_team, total_line, -spread_line, (total_line - spread_line) / 2, (total_line + spread_line) / 2 FROM games),
dst_td AS (   -- touchdowns scored by a team while NOT on offense: defensive returns (td_team = defteam) and kick / punt returns
  SELECT season, week, game_id, td_team team, COUNT(*) n
  FROM plays WHERE td = 1 AND td_team IS NOT NULL AND (
        (td_team = defteam AND play_type IN ('pass', 'run', 'qb_kneel', 'qb_spike', 'no_play') )
     OR (play_type = 'punt' AND td_team = defteam)
     OR (play_type = 'kickoff' AND rtd = 1 AND td_team = posteam)
     OR (play_type IN ('field_goal', 'extra_point') AND td_team = defteam))
  GROUP BY 1, 2, 3, 4),
give AS (   -- an offense's giveaways (interceptions + lost fumbles) per game
  SELECT season, week, game_id, posteam team, SUM(intc + fl) giveaways FROM plays WHERE play_type IN ('pass', 'run') GROUP BY 1, 2, 3, 4),
base AS (
  SELECT t.*, IFNULL(d.n, 0) dst_tds, IFNULL(g.giveaways, 0) opp_giveaways_this_week
  FROM tw t LEFT JOIN dst_td d USING (season, week, game_id, team)
  LEFT JOIN give g ON g.season = t.season AND g.week = t.week AND g.game_id = t.game_id AND g.team = t.opp),
og AS (   -- the opponent's own giveaways and DST-TDs-allowed, by week (as an offense)
  SELECT season, week, team AS opp, IFNULL(g.giveaways, 0) giveaways,
         (SELECT COUNT(*) FROM dst_td x WHERE x.season = b.season AND x.week = b.week AND x.team = b.opp) AS dst_tds_allowed
  FROM base b LEFT JOIN give g USING (season, week, team))
SELECT b.season, b.week, b.team, b.opp, b.team_implied, b.opp_implied, b.spread_line AS team_spread_signed, b.dst_tds,
  -- the team's DST TDs per game in PRIOR weeks of the same season
  (SELECT AVG(b2.dst_tds) FROM base b2 WHERE b2.season = b.season AND b2.team = b.team AND b2.week < b.week) AS prior_dst_td_pg,
  (SELECT COUNT(*) FROM base b2 WHERE b2.season = b.season AND b2.team = b.team AND b2.week < b.week) AS prior_games,
  -- the opponent's giveaways per game in PRIOR weeks (as an offense) and DST TDs it allowed per game
  (SELECT AVG(o.giveaways) FROM og o WHERE o.season = b.season AND o.opp = b.opp AND o.week < b.week) AS opp_prior_giveaways_pg,
  (SELECT AVG(o.dst_tds_allowed) FROM og o WHERE o.season = b.season AND o.opp = b.opp AND o.week < b.week) AS opp_prior_dsttd_allowed_pg
FROM base b
