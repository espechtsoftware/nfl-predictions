-- Team-level game context: pace, pass rate over expected, and Vegas implied
-- totals. Rolling windows exclude the current week.
CREATE OR REPLACE TABLE `${features}.team_week_context` AS
WITH team_games AS (
  SELECT
    posteam AS team, season, week, game_id,
    COUNT(*) AS plays,
    COUNTIF(pass_attempt = 1 OR rush_attempt = 1) AS scrimmage_plays,
    SAFE_DIVIDE(COUNTIF(pass_attempt = 1),
                NULLIF(COUNTIF(pass_attempt = 1 OR rush_attempt = 1), 0)) AS pass_rate,
    -- Neutral-situation pass rate: 1st/2nd down, score within 10, >4 min left
    SAFE_DIVIDE(
      COUNTIF(pass_attempt = 1 AND down <= 2 AND ABS(score_differential) <= 10
              AND game_seconds_remaining > 240),
      NULLIF(COUNTIF((pass_attempt = 1 OR rush_attempt = 1) AND down <= 2
              AND ABS(score_differential) <= 10 AND game_seconds_remaining > 240), 0)
    ) AS neutral_pass_rate,
    -- Seconds per play as a pace proxy
    SAFE_DIVIDE(3600 - MIN(game_seconds_remaining), NULLIF(COUNT(*), 0)) AS sec_per_play,
    -- Red zone pass tendency, for xTD decomposition (guide §5.4)
    SAFE_DIVIDE(COUNTIF(pass_attempt = 1 AND yardline_100 <= 10),
                NULLIF(COUNTIF((pass_attempt = 1 OR rush_attempt = 1)
                       AND yardline_100 <= 10), 0)) AS rz10_pass_rate
  FROM `${raw}.pbp`
  WHERE posteam IS NOT NULL AND season_type = 'REG'
  GROUP BY 1, 2, 3, 4
),
league_week AS (
  -- League expectation for pass rate, to compute PROE
  SELECT season, week, AVG(neutral_pass_rate) AS league_neutral_pass_rate
  FROM team_games
  GROUP BY 1, 2
),
-- Synthetic rows for each team's next unplayed game (same device as 014):
-- NULL metrics, so the strictly-prior windows emit as-of-now pace/PROE on
-- the upcoming week's row for live inference.
team_games_all AS (
  SELECT team, season, week, plays, scrimmage_plays, pass_rate,
         neutral_pass_rate, sec_per_play, rz10_pass_rate
  FROM team_games
  UNION ALL
  SELECT s.team, s.season, MIN(s.week),
         NULL, NULL, NULL, NULL, NULL, NULL
  FROM `${features}.schedule_long` s
  WHERE s.gameday >= CAST(CURRENT_DATE() AS STRING)
    AND NOT EXISTS (
      SELECT 1 FROM team_games t2
      WHERE t2.team = s.team AND t2.season = s.season AND t2.week = s.week
    )
  GROUP BY s.team, s.season
),
rolled AS (
  SELECT
    t.team, t.season, t.week,
    AVG(t.scrimmage_plays)   OVER w4 AS plays_l4,
    AVG(t.pass_rate)         OVER w4 AS pass_rate_l4,
    AVG(t.sec_per_play)      OVER w4 AS pace_l4,
    AVG(t.rz10_pass_rate)    OVER wstd AS rz10_pass_rate_std,
    AVG(t.neutral_pass_rate - l.league_neutral_pass_rate) OVER w4 AS proe_l4
  FROM team_games_all t
  LEFT JOIN league_week l USING (season, week)
  WINDOW
    w4   AS (PARTITION BY t.team, t.season ORDER BY t.week
             ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING),
    wstd AS (PARTITION BY t.team, t.season ORDER BY t.week
             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
)
SELECT
  s.team, s.season, s.week, s.game_id, s.opponent,
  s.implied_team_total, s.team_spread AS spread, s.game_total,
  s.implied_team_total - s.implied_opponent_total AS expected_game_script,
  s.is_home, s.roof, s.surface, s.days_rest,
  r.plays_l4, r.pass_rate_l4, r.pace_l4, r.proe_l4, r.rz10_pass_rate_std,
  -- Pace-adjusted expected plays: recent volume scaled by game environment
  r.plays_l4 * SAFE_DIVIDE(s.game_total, 45.0) AS expected_plays
FROM `${features}.schedule_long` s
LEFT JOIN rolled r USING (team, season, week);
