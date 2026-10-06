-- The season's regular-season games: kickoff (Eastern), teams, lines, scores.
SELECT CAST(season AS INT64) AS season, CAST(week AS INT64) AS week, game_id,
       gameday, gametime, weekday, home_team, away_team,
       home_score, away_score, total_line, spread_line
FROM `${raw}.schedules`
WHERE season = ${season} AND game_type = 'REG'
ORDER BY week, gameday, gametime
