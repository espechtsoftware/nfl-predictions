-- Injury designation and practice-participation trend, point-in-time: the
-- report for week W is published before W's games, so same-week rows are
-- legitimately knowable. Games missed uses strictly-prior weeks.
CREATE OR REPLACE TABLE `${features}.player_week_injury` AS
WITH inj AS (
  SELECT
    gsis_id,
    -- nflverse ships these as FLOAT in the injuries dataset (null-driven
    -- upcast); INT64 keeps join keys consistent and windows partitionable.
    CAST(season AS INT64) AS season,
    CAST(week AS INT64) AS week,
    report_status AS injury_status,
    -- Encode Wed/Thu/Fri practice as 0=DNP, 1=Limited, 2=Full and average
    (SELECT AVG(v) FROM UNNEST([
       CASE practice_status
         WHEN 'Did Not Participate In Practice' THEN 0.0
         WHEN 'Limited Participation in Practice' THEN 1.0
         WHEN 'Full Participation in Practice' THEN 2.0
       END
     ]) v WHERE v IS NOT NULL) AS practice_level
  FROM `${raw}.injuries`
  WHERE gsis_id IS NOT NULL
),
played AS (
  SELECT gsis_id, season, week FROM `${features}.player_week_actuals`
),
missed AS (
  -- Weeks on the injury report as Out, in the prior 4 weeks
  SELECT
    i.gsis_id, i.season, i.week,
    COUNTIF(i2.injury_status = 'Out') AS games_missed_l4
  FROM inj i
  LEFT JOIN inj i2
    ON i2.gsis_id = i.gsis_id AND i2.season = i.season
   AND i2.week BETWEEN i.week - 4 AND i.week - 1
  GROUP BY 1, 2, 3
)
SELECT
  i.gsis_id, i.season, i.week,
  i.injury_status,
  i.practice_level,
  i.practice_level - LAG(i.practice_level) OVER (
    PARTITION BY i.gsis_id, i.season ORDER BY i.week
  ) AS practice_participation_trend,
  COALESCE(m.games_missed_l4, 0) AS games_missed_l4
FROM inj i
LEFT JOIN missed m USING (gsis_id, season, week);
