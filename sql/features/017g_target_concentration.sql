-- Target concentration (2026-08-01, candidate feature): share of the
-- team's targets going to its top-2 targeted players, per week, then l6
-- strictly prior. Concentrated offenses produce stronger stack
-- correlations than spread-the-ball offenses.
CREATE OR REPLACE TABLE `${features}.team_week_target_concentration` AS
WITH pw AS (
  SELECT team, season, week, player_id, SUM(targets) AS t
  FROM `${raw}.weekly_stats`
  WHERE targets IS NOT NULL
  GROUP BY team, season, week, player_id
),
tw AS (
  SELECT team, season, week,
         SUM(t) AS team_targets,
         SUM(IF(rnk <= 2, t, 0)) AS top2_targets
  FROM (
    SELECT *, ROW_NUMBER() OVER (
      -- player_id tie-break: equal target counts are common and an
      -- unkeyed rank drifts per rebuild (variance review 2026-08-04)
      PARTITION BY team, season, week ORDER BY t DESC, player_id) AS rnk
    FROM pw
  )
  GROUP BY team, season, week
)
SELECT
  team, season, week,
  SAFE_DIVIDE(SUM(top2_targets) OVER w, SUM(team_targets) OVER w)
    AS top2_target_share_l6
FROM tw
WINDOW w AS (
  PARTITION BY team ORDER BY season, week
  ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
);
