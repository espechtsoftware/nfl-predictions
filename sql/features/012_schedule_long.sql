-- One row per team-game with Vegas context. Implied totals from the closing
-- spread/total: the single strongest projection feature in the system.
-- nflverse convention: spread_line is relative to the home team (positive =
-- home favored), so implied_home = total/2 + spread_home/2.
CREATE OR REPLACE TABLE `${features}.schedule_long` AS
-- Team codes NORMALIZED to the modern convention (OAK->LV, SD->LAC,
-- STL->LA) to match rosters/stats-derived tables. Before 2026-08-03 the
-- historical codes silently dropped ~1,500 relocated-franchise training
-- rows (2014-19) at 021's inner join and NULLed opponent-defense
-- features on 1,458 more (data audit, Addendum 42).
WITH base AS (
  SELECT
    game_id, season, week, game_type,
    gameday, weekday, gametime,
    CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE home_team END AS home_team,
    CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE away_team END AS away_team,
    spread_line,                       -- home margin expectation
    total_line,
    roof, surface, temp, wind,
    home_rest, away_rest
  FROM `${raw}.schedules`
  WHERE total_line IS NOT NULL
)
SELECT
  game_id, season, week, game_type, gameday,
  home_team AS team, away_team AS opponent, TRUE AS is_home,
  spread_line * -1 AS team_spread,     -- negative = this team favored
  total_line AS game_total,
  total_line / 2 + spread_line / 2 AS implied_team_total,
  total_line / 2 - spread_line / 2 AS implied_opponent_total,
  spread_line AS expected_margin,
  roof, surface, home_rest AS days_rest
FROM base
UNION ALL
SELECT
  game_id, season, week, game_type, gameday,
  away_team AS team, home_team AS opponent, FALSE AS is_home,
  spread_line AS team_spread,
  total_line AS game_total,
  total_line / 2 - spread_line / 2 AS implied_team_total,
  total_line / 2 + spread_line / 2 AS implied_opponent_total,
  spread_line * -1 AS expected_margin,
  roof, surface, away_rest AS days_rest
FROM base;
