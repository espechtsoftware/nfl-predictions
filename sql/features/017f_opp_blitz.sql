-- Defense blitz rate (2026-08-01, candidate feature): share of opposing
-- dropbacks the defense sent >=1 blitzer at, l6 strictly prior. FTN
-- charting covers 2022+; earlier rows are NULL (build_X NaN-fills).
-- Claimed consumer: TE/quick-game production against heavy-blitz
-- defenses; the model interacts it with position itself.
CREATE OR REPLACE TABLE `${features}.defense_week_blitz` AS
WITH plays AS (
  SELECT p.defteam AS team, p.season, p.week,
         IF(f.n_blitzers >= 1, 1, 0) AS blitzed
  FROM `${raw}.pbp` p
  JOIN `${raw}.ftn_charting` f
    ON f.nflverse_game_id = p.game_id AND f.nflverse_play_id = p.play_id
  WHERE p.pass = 1 AND p.defteam IS NOT NULL
),
tw AS (
  SELECT team, season, week, SUM(blitzed) AS b, COUNT(*) AS n
  FROM plays GROUP BY team, season, week
),
with_upcoming AS (
  SELECT * FROM tw
  UNION ALL
  SELECT DISTINCT
    ro.team, ro.season, ro.week,
    CAST(NULL AS INT64) AS b,
    CAST(NULL AS INT64) AS n
  FROM `${features}.player_week_role` ro
  WHERE ro.is_upcoming
    AND NOT EXISTS (
      SELECT 1 FROM tw prior
      WHERE prior.team = ro.team AND prior.season = ro.season
        AND prior.week = ro.week
    )
)
SELECT
  team, season, week,
  SAFE_DIVIDE(SUM(b) OVER w, SUM(n) OVER w) AS blitz_rate_l6
FROM with_upcoming
WINDOW w AS (
  PARTITION BY team ORDER BY season, week
  ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
);
