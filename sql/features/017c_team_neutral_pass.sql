-- Neutral-situation pass rate (2026-08-01): score within 3, outside the
-- last 2 minutes of a half, regulation only -- strips blowout/desperation
-- script so the windowed rate reflects the staff's schematic identity
-- rather than last month's game states. Raw seasonal pass rate
-- double-counts script once a simulator (or the model's opponent
-- features) generates script separately.
--
-- Point-in-time: the 6 most recent observed team-weeks strictly before the row.
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
),
-- O-22 (2026-10-05): AS-OF over the row spine, not an event-only row set. The
-- old table had a row only for team-weeks with at least one neutral-script
-- play, and 021 joins by exact week, so a training row was NULL exactly when
-- its OWN game was a blowout (post-game information), while a served row was
-- never NULL. Now every (team, season, week) that training or inference can
-- join (player_week_usage, upcoming rows included) carries the ratio over the
-- team's 6 most recent OBSERVED team-weeks strictly before it, across seasons as
-- the old ROWS window ran. Where the old table had a row its value is unchanged;
-- NULL now means only "no prior observed week", in training and serving alike.
spine AS (
  SELECT DISTINCT team, season, week
  FROM `${features}.player_week_usage`
  WHERE team IS NOT NULL
),
prior AS (
  SELECT s.team, s.season, s.week, t.p, t.n,
         ROW_NUMBER() OVER (
           PARTITION BY s.team, s.season, s.week
           ORDER BY t.season DESC, t.week DESC) AS k
  FROM spine s
  JOIN tw t
    ON t.team = s.team
   AND (t.season < s.season OR (t.season = s.season AND t.week < s.week))
)
SELECT s.team, s.season, s.week,
       SAFE_DIVIDE(SUM(pr.p), SUM(pr.n)) AS neutral_pass_rate_l6
FROM spine s
LEFT JOIN prior pr
  ON pr.team = s.team AND pr.season = s.season AND pr.week = s.week AND pr.k <= 6
GROUP BY 1, 2, 3;
