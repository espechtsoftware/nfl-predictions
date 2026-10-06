-- Fantasy Points' DraftKings Classic projections for the week (licensed:
-- shown only as comparisons inside the IAP app, never exported).
SELECT slate_id, slate_name, n_games, name, position, team, salary,
       slate_player_id, fantasy_points, retrieved_at
FROM `${raw}.fantasy_points_dfs_projections`
WHERE season = ${season} AND week = ${week}
  AND operator = 'DraftKings' AND game_type = 'Classic'
  AND retrieved_at < TIMESTAMP('${lock_utc}')
