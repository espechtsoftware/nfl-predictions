-- top_cb_out, point in time (O-22, 2026-10-05). 017a picks each defense's
-- snap-leader corner through the prior week (top_cb_pfr_id) but runs before
-- 018, so it cannot read the point-in-time injury table. This step fills
-- top_cb_out from `${features}.player_week_injury`, which admits a same-week
-- injury row only when its source modification time or our collector's
-- observation time is at or before the common Sunday-main lock (018). The
-- raw nflverse injuries table is never read here.
--
-- Semantics kept from the original 017a: NULL when the team has no
-- prior-snaps corner (week 1; the first-row-null leakage invariant); FALSE
-- when the corner has no crosswalk match or no admissible Out designation;
-- TRUE when any crosswalk match is Out on the point-in-time report.
CREATE OR REPLACE TABLE `${features}.defense_week_coverage` AS
WITH outs AS (
  SELECT
    c.team, c.season, c.week,
    IFNULL(LOGICAL_OR(inj.injury_status = 'Out'), FALSE) AS top_cb_out
  FROM `${features}.defense_week_coverage` c
  LEFT JOIN `${raw}.player_ids` x ON x.pfr_id = c.top_cb_pfr_id
  LEFT JOIN `${features}.player_week_injury` inj
    ON inj.gsis_id = x.gsis_id
   AND inj.season = c.season
   AND inj.week = c.week
  WHERE c.top_cb_pfr_id IS NOT NULL
  GROUP BY 1, 2, 3
)
SELECT c.* EXCEPT (top_cb_out), o.top_cb_out
FROM `${features}.defense_week_coverage` c
LEFT JOIN outs o USING (team, season, week);
