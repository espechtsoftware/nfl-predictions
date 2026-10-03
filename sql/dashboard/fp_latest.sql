-- Shared CTEs (an include: inc:fp_latest): the week's main-slate lock
-- and Fantasy Points' newest pre-lock DraftKings projected ownership (fpo)
-- and projection (fpp) per (normalised name, team). A key two FP rows share
-- is a collision and is dropped (HAVING COUNT(*) = 1), never merged.
lock AS (
  SELECT CAST(week AS INT64) AS week,
         TIMESTAMP(CONCAT(MIN(gameday), ' 13:00:00'), 'America/New_York') AS lock_ts
  FROM `${raw}.schedules`
  WHERE season = ${season} AND game_type = 'REG' AND weekday = 'Sunday'
  GROUP BY 1
),
fpo AS (
  SELECT week, norm(name) AS k, team_code(team) AS team, ANY_VALUE(projected_ownership_pct) AS fp_own
  FROM (
    SELECT o.* FROM `${raw}.fantasy_points_projected_ownership` o
    JOIN lock l ON l.week = o.week
    WHERE o.season = ${season} AND o.operator = 'DraftKings' AND o.retrieved_at < l.lock_ts
    QUALIFY o.retrieved_at = MAX(o.retrieved_at) OVER (PARTITION BY o.week)
  )
  GROUP BY 1, 2, 3
  HAVING COUNT(*) = 1
),
fpp AS (
  SELECT week, norm(name) AS k, team_code(team) AS team, ANY_VALUE(fantasy_points) AS fp_proj
  FROM (
    SELECT f.* FROM `${raw}.fantasy_points_dfs_projections` f
    JOIN lock l ON l.week = f.week
    WHERE f.season = ${season} AND f.operator = 'DraftKings' AND f.game_type = 'Classic'
      AND f.retrieved_at < l.lock_ts
    QUALIFY ROW_NUMBER() OVER (PARTITION BY f.week, f.name, f.team
                               ORDER BY f.retrieved_at DESC, f.slate_name = 'Main' DESC,
                                        f.n_games DESC) = 1
  )
  GROUP BY 1, 2, 3
  HAVING COUNT(*) = 1
),
fp_weeks AS (SELECT DISTINCT week FROM fpo)
