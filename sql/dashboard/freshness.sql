-- When each live input last moved (the overview page's freshness strip).
SELECT 'odds_snapshots' AS source, MAX(pulled_at) AS newest
FROM `${raw}.odds_snapshots` WHERE pulled_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
UNION ALL
SELECT 'player_projections', MAX(generated_at)
FROM `${predictions}.player_projections` WHERE season = ${season}
UNION ALL
SELECT 'contest_entries', MAX(imported_at)
FROM `${raw}.contest_entries` WHERE imported_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
