-- Our served projections for the week: the newest batch (one generated_at
-- spans every slate_id) generated before ${lock_utc}. A player listed under
-- several slates keeps one row.
WITH p AS (
  SELECT * FROM `${predictions}.player_projections`
  WHERE season = ${season} AND week = ${week}
    AND generated_at < TIMESTAMP('${lock_utc}')
  QUALIFY generated_at = MAX(generated_at) OVER ()
)
SELECT generated_at, slate_id, gsis_id, dk_player_id, display_name, position,
       team, opponent, salary, proj_points, proj_p10, proj_p50, proj_p90
FROM p
QUALIFY ROW_NUMBER() OVER (PARTITION BY dk_player_id ORDER BY slate_id) = 1
