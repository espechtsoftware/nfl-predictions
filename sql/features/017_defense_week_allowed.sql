-- Opponent concessions, opponent-adjusted, trailing 6 weeks. Raw "points
-- allowed to WRs" is badly confounded by schedule, so positional fantasy
-- points allowed are expressed relative to what those offenses scored
-- against everyone else (a simple two-pass adjustment).
CREATE OR REPLACE TABLE `${features}.defense_week_allowed` AS
WITH position_week AS (
  -- Exact player-week position only. A season-final position leaks future
  -- RB/FB or WR/TE reclassifications into early-week positional concessions.
  SELECT gsis_id, CAST(season AS INT64) AS season,
         CAST(week AS INT64) AS week, UPPER(position) AS position
  FROM `${raw}.rosters_weekly`
  WHERE gsis_id IS NOT NULL AND position IS NOT NULL
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY gsis_id, CAST(season AS INT64), CAST(week AS INT64)
    ORDER BY UPPER(position)
  ) = 1
),
def_games AS (
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
  JOIN position_week pm
    ON pm.gsis_id = a.gsis_id AND pm.season = a.season AND pm.week = a.week
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
  JOIN position_week pm
    ON pm.gsis_id = a.gsis_id AND pm.season = a.season AND pm.week = a.week
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
),
-- O-22 (2026-10-05): AS-OF over the schedule spine. The old final SELECT had a
-- row only for each played game (a ROWS window over def_games), so serving
-- (023) took a defense's LATEST played row, whose window ends one game before
-- it: one game stale against training, the O-21 class. Every scheduled
-- defense-week (upcoming included) now averages the defense's 6 most recent
-- played games strictly before it within the season; played weeks carry the
-- same values as the old window, and 023 joins by exact week.
per_game AS (
  SELECT d.team, d.season, d.week,
         d.epa_per_dropback_allowed, d.epa_per_rush_allowed, d.rz_td_rate_allowed,
         qb.pos_dk_points_allowed_adj AS qb_adj, rb.pos_dk_points_allowed_adj AS rb_adj,
         wr.pos_dk_points_allowed_adj AS wr_adj, te.pos_dk_points_allowed_adj AS te_adj
  FROM def_games d
  LEFT JOIN (SELECT * FROM adjusted WHERE position = 'QB') qb USING (team, season, week)
  LEFT JOIN (SELECT * FROM adjusted WHERE position = 'RB') rb USING (team, season, week)
  LEFT JOIN (SELECT * FROM adjusted WHERE position = 'WR') wr USING (team, season, week)
  LEFT JOIN (SELECT * FROM adjusted WHERE position = 'TE') te USING (team, season, week)
),
spine AS (                 -- seasons the play-by-play covers (older schedule rows would be all NULL)
  SELECT DISTINCT team, season, week FROM `${features}.schedule_long`
  WHERE season >= (SELECT MIN(season) FROM def_games)
),
prior AS (
  SELECT s.team, s.season, s.week, g.* EXCEPT (team, season, week),
         ROW_NUMBER() OVER (PARTITION BY s.team, s.season, s.week ORDER BY g.week DESC) AS k
  FROM spine s
  JOIN per_game g
    ON g.team = s.team AND g.season = s.season AND g.week < s.week
)
SELECT
  s.team, s.season, s.week,
  AVG(pr.epa_per_dropback_allowed) AS epa_per_dropback_allowed_l6,
  AVG(pr.epa_per_rush_allowed)     AS epa_per_rush_allowed_l6,
  AVG(pr.rz_td_rate_allowed)       AS rz_td_rate_allowed_l6,
  AVG(pr.qb_adj) AS qb_fp_allowed_adj_l6,
  AVG(pr.rb_adj) AS rb_fp_allowed_adj_l6,
  AVG(pr.wr_adj) AS wr_fp_allowed_adj_l6,
  AVG(pr.te_adj) AS te_fp_allowed_adj_l6
FROM spine s
LEFT JOIN prior pr
  ON pr.team = s.team AND pr.season = s.season AND pr.week = s.week AND pr.k <= 6
GROUP BY 1, 2, 3;
