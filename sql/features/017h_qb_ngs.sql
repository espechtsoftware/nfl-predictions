-- QB NGS passing metrics (2026-08-01, candidate features): ngs_passing was
-- the audit's one fully-unused raw table. CPOE (completion % above
-- expectation) is the strongest public QB skill signal; time-to-throw
-- proxies protection/scheme. l6 strictly prior; NGS covers 2016+ and only
-- qualifying QBs (NaN elsewhere; build_X handles it). Gated behind
-- EXTRA_FEATURES like all candidates -- the 5-for-5 feature law applies.
CREATE OR REPLACE TABLE `${features}.qb_week_ngs` AS
WITH observations AS (
  SELECT
    player_gsis_id AS gsis_id, season, week,
    completion_percentage_above_expectation AS cpoe,
    avg_time_to_throw AS time_to_throw
  FROM `${raw}.ngs_passing`
  WHERE week > 0
),
-- O-22 (2026-10-05): AS-OF over the row spine. The old table had a row only for
-- QB-weeks with a qualifying NGS line (about 15+ attempts), joined by exact
-- week in 021, so a training row was non-NULL only when the QB actually threw
-- in the game being predicted (post-game information); serving used a synthetic
-- upcoming row, non-NULL for every QB with history. Now every player_week_usage
-- row of a player who ever has an NGS line gets the mean of his 6 most recent
-- NGS games strictly before it (across seasons, as before). Where the old table
-- had a row its values are unchanged; NULL now means only "no prior qualifying
-- game", in training and serving alike.
spine AS (
  SELECT DISTINCT u.gsis_id, u.season, u.week
  FROM `${features}.player_week_usage` u
  WHERE u.gsis_id IN (SELECT gsis_id FROM observations)
),
prior AS (
  SELECT s.gsis_id, s.season, s.week, o.cpoe, o.time_to_throw,
         ROW_NUMBER() OVER (
           PARTITION BY s.gsis_id, s.season, s.week
           ORDER BY o.season DESC, o.week DESC) AS k
  FROM spine s
  JOIN observations o
    ON o.gsis_id = s.gsis_id
   AND (o.season < s.season OR (o.season = s.season AND o.week < s.week))
)
SELECT s.gsis_id, s.season, s.week,
       AVG(pr.cpoe) AS qb_cpoe_l6,
       AVG(pr.time_to_throw) AS qb_time_to_throw_l6
FROM spine s
LEFT JOIN prior pr
  ON pr.gsis_id = s.gsis_id AND pr.season = s.season AND pr.week = s.week AND pr.k <= 6
GROUP BY 1, 2, 3;
