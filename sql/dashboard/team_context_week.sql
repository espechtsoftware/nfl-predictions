-- nflverse schedule lines as the feature build stored them (fallback when
-- odds_snapshots has no pull for a game). spread: negative = team favored.
SELECT team, opponent, is_home, implied_team_total, spread, game_total
FROM `${features}.team_week_context`
WHERE season = ${season} AND week = ${week}
