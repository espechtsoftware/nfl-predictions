-- Neutral-situation pass rate (2026-08-01): score within 3, outside the
-- last 2 minutes of a half, regulation only -- strips blowout/desperation
-- script so the windowed rate reflects the staff's schematic identity
-- rather than last month's game states. Raw seasonal pass rate
-- double-counts script once a simulator (or the model's opponent
-- features) generates script separately.
--
-- Point-in-time: l6 window is strictly prior (1 PRECEDING).
CREATE OR REPLACE TABLE `${features}.team_week_neutral_pass` AS
WITH plays AS (
  SELECT posteam AS team, season, week, CAST(pass AS INT64) AS is_pass
  FROM `${raw}.pbp`
  WHERE posteam IS NOT NULL
    AND (pass = 1 OR rush = 1)
    AND ABS(COALESCE(score_differential, 0)) <= 3
    AND half_seconds_remaining > 120
    AND qtr <= 4
),
tw AS (
  SELECT team, season, week, SUM(is_pass) AS p, COUNT(*) AS n
  FROM plays
  GROUP BY team, season, week
)
SELECT
  team, season, week,
  SAFE_DIVIDE(SUM(p) OVER w, SUM(n) OVER w) AS neutral_pass_rate_l6
FROM tw
WINDOW w AS (
  PARTITION BY team ORDER BY season, week
  ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
);
