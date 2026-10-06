-- Cornerback / secondary coverage quality, from PFR advanced defense stats
-- (`${raw}.pfr_advstats_def`, 2018+): per-defender targets, completions and
-- yards allowed as the nearest defender, summed to the CB group (and the
-- whole secondary) per defense-game, then windowed strictly prior
-- (1 PRECEDING). "Nearest defender" attribution is charting — noisy per
-- play, serviceable summed per game.
--
-- The spine is schedule_long, not played games, so the upcoming week gets a
-- row too: its trailing windows and its injury-report-based top_cb_out are
-- both knowable before kickoff, which lets inference (023) join by exact
-- week instead of the as-of fallback the older defense table needs.
--
-- Positions come from snap_counts — also PFR-keyed, so the group aggregates
-- need no GSIS crosswalk; the crosswalk is only used (in 018a) to match the
-- snap-leader corner to the point-in-time injury report.
CREATE OR REPLACE TABLE `${features}.defense_week_coverage` AS
WITH def_pos AS (
  SELECT pfr_player_id, season, week, team, position, defense_snaps
  FROM `${raw}.snap_counts`
  WHERE defense_snaps > 0 AND pfr_player_id IS NOT NULL
),
-- Per defense-game concessions. Ratio of sums, not mean of player ratios:
-- a corner targeted once shouldn't weigh like one targeted nine times.
cov_games AS (
  SELECT
    a.team, a.season, a.week,
    SAFE_DIVIDE(
      SUM(IF(p.position = 'CB', a.def_yards_allowed, NULL)),
      NULLIF(SUM(IF(p.position = 'CB', a.def_targets, NULL)), 0)
    ) AS cb_ypt_allowed,
    SAFE_DIVIDE(
      SUM(IF(p.position = 'CB', a.def_completions_allowed, NULL)),
      NULLIF(SUM(IF(p.position = 'CB', a.def_targets, NULL)), 0)
    ) AS cb_comp_rate_allowed,
    SAFE_DIVIDE(
      SUM(IF(p.position IN ('CB', 'DB', 'S', 'FS', 'SS'), a.def_yards_allowed, NULL)),
      NULLIF(SUM(IF(p.position IN ('CB', 'DB', 'S', 'FS', 'SS'), a.def_targets, NULL)), 0)
    ) AS db_ypt_allowed
  FROM `${raw}.pfr_advstats_def` a
  JOIN def_pos p
    ON p.pfr_player_id = a.pfr_player_id
   AND p.season = a.season AND p.week = a.week
  GROUP BY 1, 2, 3
),
spine AS (
  SELECT team, season, week FROM `${features}.schedule_long`
),
windowed AS (
  SELECT
    s.team, s.season, s.week,
    AVG(c.cb_ypt_allowed)       OVER w6 AS cb_ypt_allowed_l6,
    AVG(c.cb_comp_rate_allowed) OVER w6 AS cb_comp_rate_allowed_l6,
    AVG(c.db_ypt_allowed)       OVER w6 AS db_ypt_allowed_l6
  FROM spine s
  LEFT JOIN cov_games c USING (team, season, week)
  WINDOW w6 AS (PARTITION BY s.team, s.season ORDER BY s.week
                ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING)
),
-- The snap-leader corner through the prior week, per spine row. Strictly
-- prior on the snaps side. Its same-week injury status is read in 018a from
-- the point-in-time injury table, never from raw injuries here.
cb1 AS (
  SELECT s.team, s.season, s.week, p.pfr_player_id
  FROM spine s
  JOIN def_pos p
    ON p.team = s.team AND p.season = s.season AND p.week < s.week
   AND p.position = 'CB'
  GROUP BY 1, 2, 3, 4
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY s.team, s.season, s.week
    ORDER BY SUM(p.defense_snaps) DESC, p.pfr_player_id
  ) = 1
)
SELECT
  w.team, w.season, w.week,
  w.cb_ypt_allowed_l6, w.cb_comp_rate_allowed_l6, w.db_ypt_allowed_l6,
  -- The snap-leader corner through the prior week (NULL until the team has a
  -- prior-snaps corner, i.e. week 1). top_cb_out is filled by
  -- 018a_defense_week_cb_out.sql from the point-in-time player_week_injury
  -- (O-22, 2026-10-05): this file runs before 018, and reading raw injuries
  -- here bypassed 018's common Sunday-main lock (date_modified / collector
  -- pulled_at <= lock), so 2025's NULL-timestamp rows and post-lock revisions
  -- leaked in. Placeholder until 018a rewrites the table.
  c.pfr_player_id AS top_cb_pfr_id,
  CAST(NULL AS BOOL) AS top_cb_out
FROM windowed w
LEFT JOIN cb1 c USING (team, season, week);
