-- Fantasy Points' DraftKings projected ownership, every pre-lock retrieval
-- (the newest is chosen in Python).
SELECT name, position, team, salary, projected_ownership_pct, retrieved_at
FROM `${raw}.fantasy_points_projected_ownership`
WHERE season = ${season} AND week = ${week}
  AND operator = 'DraftKings'
  AND retrieved_at < TIMESTAMP('${lock_utc}')
