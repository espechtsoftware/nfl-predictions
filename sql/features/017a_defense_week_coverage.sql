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
-- need no GSIS crosswalk; the crosswalk is only used to match the
-- snap-leader corner to the injury report.
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
-- prior on the snaps side; the injury report for week W is published before
-- W's games, so reading it same-week is legitimate (018 precedent).
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
),
cb1_out AS (
  SELECT
    c.team, c.season, c.week,
    -- No injury row (or no crosswalk) means no designation: playing.
    IFNULL(LOGICAL_OR(inj.report_status = 'Out'), FALSE) AS top_cb_out
  FROM cb1 c
  LEFT JOIN `${raw}.player_ids` i ON i.pfr_id = c.pfr_player_id
  LEFT JOIN `${raw}.injuries` inj
    ON inj.gsis_id = i.gsis_id
   AND CAST(inj.season AS INT64) = c.season
   AND CAST(inj.week AS INT64) = c.week
  GROUP BY 1, 2, 3
)
SELECT
  w.team, w.season, w.week,
  w.cb_ypt_allowed_l6, w.cb_comp_rate_allowed_l6, w.db_ypt_allowed_l6,
  -- NULL until the team has a prior-snaps corner (week 1): honest, and it
  -- keeps the first-row-null leakage invariant meaningful for this column.
  o.top_cb_out
FROM windowed w
LEFT JOIN cb1_out o USING (team, season, week);
