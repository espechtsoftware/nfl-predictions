-- Opponent concessions, opponent-adjusted, trailing 6 weeks. Raw "points
-- allowed to WRs" is badly confounded by schedule, so positional fantasy
-- points allowed are expressed relative to what those offenses scored
-- against everyone else (a simple two-pass adjustment).
CREATE OR REPLACE TABLE `${features}.defense_week_allowed` AS
WITH def_games AS (
  SELECT
    defteam AS team, season, week, game_id,
    AVG(IF(qb_dropback = 1, epa, NULL)) AS epa_per_dropback_allowed,
    AVG(IF(rush_attempt = 1, epa, NULL)) AS epa_per_rush_allowed,
    SAFE_DIVIDE(
      COUNTIF(touchdown = 1 AND yardline_100 <= 20),
      NULLIF(COUNTIF(yardline_100 <= 20 AND (pass_attempt = 1 OR rush_attempt = 1)), 0)
    ) AS rz_td_rate_allowed
  FROM `${raw}.pbp`
  WHERE defteam IS NOT NULL AND season_type = 'REG'
  GROUP BY 1, 2, 3, 4
),
-- Positional DK points allowed: join actuals to the schedule to find who
-- each player faced that week.
pos_allowed AS (
  SELECT
    s.opponent AS team,       -- the defense
    a.season, a.week,
    pm.position,
    SUM(a.dk_points) AS pos_dk_points_allowed
  FROM `${features}.player_week_actuals` a
  JOIN `${features}.schedule_long` s
    ON s.team = a.team AND s.season = a.season AND s.week = a.week
  JOIN (
    SELECT gsis_id, season, ANY_VALUE(position HAVING MAX week) AS position
    FROM `${raw}.rosters_weekly` WHERE gsis_id IS NOT NULL
    GROUP BY gsis_id, season
  ) pm ON pm.gsis_id = a.gsis_id AND pm.season = a.season
  WHERE pm.position IN ('QB', 'RB', 'WR', 'TE')
  GROUP BY 1, 2, 3, 4
),
-- Offense strength, point-in-time: what each offense's position group has
-- scored per game THROUGH THE PRIOR WEEK. A season-wide average here would
-- let week-3 adjustments see week-18 offense — the same leak the rolling
-- features guard against with 1 PRECEDING.
off_week AS (
  SELECT a.team, a.season, a.week, pm.position,
         SUM(a.dk_points) AS pos_dk_points
  FROM `${features}.player_week_actuals` a
  JOIN (
    SELECT gsis_id, season, ANY_VALUE(position HAVING MAX week) AS position
    FROM `${raw}.rosters_weekly` WHERE gsis_id IS NOT NULL
    GROUP BY gsis_id, season
  ) pm ON pm.gsis_id = a.gsis_id AND pm.season = a.season
  WHERE pm.position IN ('QB', 'RB', 'WR', 'TE')
  GROUP BY 1, 2, 3, 4
),
off_strength AS (
  SELECT team, season, week, position,
         AVG(pos_dk_points) OVER (
           PARTITION BY team, season, position ORDER BY week
           ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
         ) AS pos_dk_points_pg_prior
  FROM off_week
),
adjusted AS (
  SELECT
    p.team, p.season, p.week, p.position,
    p.pos_dk_points_allowed,
    -- Points allowed relative to that offense's usual output so far. NULL in
    -- an offense's first week (no prior baseline) — honest, not imputed.
    p.pos_dk_points_allowed - o.pos_dk_points_pg_prior AS pos_dk_points_allowed_adj
  FROM pos_allowed p
  JOIN `${features}.schedule_long` s
    ON s.team = p.team AND s.season = p.season AND s.week = p.week
  LEFT JOIN off_strength o
    ON o.team = s.opponent AND o.season = p.season
   AND o.week = p.week AND o.position = p.position
)
SELECT
  d.team, d.season, d.week,
  AVG(d.epa_per_dropback_allowed) OVER w6 AS epa_per_dropback_allowed_l6,
  AVG(d.epa_per_rush_allowed)     OVER w6 AS epa_per_rush_allowed_l6,
  AVG(d.rz_td_rate_allowed)       OVER w6 AS rz_td_rate_allowed_l6,
  AVG(qb.pos_dk_points_allowed_adj) OVER w6 AS qb_fp_allowed_adj_l6,
  AVG(rb.pos_dk_points_allowed_adj) OVER w6 AS rb_fp_allowed_adj_l6,
  AVG(wr.pos_dk_points_allowed_adj) OVER w6 AS wr_fp_allowed_adj_l6,
  AVG(te.pos_dk_points_allowed_adj) OVER w6 AS te_fp_allowed_adj_l6
FROM def_games d
LEFT JOIN (SELECT * FROM adjusted WHERE position = 'QB') qb
  USING (team, season, week)
LEFT JOIN (SELECT * FROM adjusted WHERE position = 'RB') rb
  USING (team, season, week)
LEFT JOIN (SELECT * FROM adjusted WHERE position = 'WR') wr
  USING (team, season, week)
LEFT JOIN (SELECT * FROM adjusted WHERE position = 'TE') te
  USING (team, season, week)
WINDOW w6 AS (PARTITION BY d.team, d.season ORDER BY d.week
              ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING);
