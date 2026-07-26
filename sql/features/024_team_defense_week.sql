-- Team-defense (DST) DK scoring per week, computed from play-by-play +
-- schedules, plus point-in-time trailing form. This is the in-season DST
-- actuals source (issue #7): dk_salaries_historical only covers seasons
-- someone exported, while pbp arrives weekly all season.
--
-- DK DST scoring: sack +1, INT +2, fumble recovery +2, def/ST return TD
-- +6, safety +2, blocked kick +2, plus the points-allowed tier.
-- Approximation: points allowed = opponent's final score (DK excludes
-- points the team's own offense surrendered, e.g. pick-sixes; final score
-- is the standard proxy and the bias is small and rare).

CREATE OR REPLACE TABLE `${features}.team_defense_week` AS
WITH def_events AS (
  SELECT
    season, week, defteam AS team,
    SUM(CAST(sack AS INT64)) AS sacks,
    SUM(CAST(interception AS INT64)) AS interceptions,
    SUM(CAST(fumble_lost AS INT64)) AS fumble_recoveries,
    SUM(CAST(safety AS INT64)) AS safeties,
    SUM(CASE WHEN punt_blocked = 1
              OR field_goal_result = 'blocked'
              OR extra_point_result = 'blocked' THEN 1 ELSE 0 END)
      AS blocked_kicks,
    -- Return/defensive TDs credited to the DST: any TD scored by this
    -- team on a play where it did NOT have possession (pick-six, scoop
    -- score, punt/kick return).
    SUM(CASE WHEN touchdown = 1 AND td_team = defteam THEN 1 ELSE 0 END)
      AS return_tds
  FROM `${raw}.pbp`
  WHERE defteam IS NOT NULL AND season_type = 'REG'
  GROUP BY season, week, defteam
),
points_allowed AS (
  SELECT season, week, home_team AS team, away_score AS pa FROM `${raw}.schedules`
  WHERE game_type = 'REG'
  UNION ALL
  SELECT season, week, away_team AS team, home_score AS pa FROM `${raw}.schedules`
  WHERE game_type = 'REG'
),
scored AS (
  SELECT
    e.season, e.week, e.team, p.pa,
    e.sacks, e.interceptions, e.fumble_recoveries, e.safeties,
    e.blocked_kicks, e.return_tds,
    e.sacks * 1 + e.interceptions * 2 + e.fumble_recoveries * 2
      + e.safeties * 2 + e.blocked_kicks * 2 + e.return_tds * 6
      + CASE
          WHEN p.pa = 0 THEN 10
          WHEN p.pa <= 6 THEN 7
          WHEN p.pa <= 13 THEN 4
          WHEN p.pa <= 20 THEN 1
          WHEN p.pa <= 27 THEN 0
          WHEN p.pa <= 34 THEN -1
          ELSE -4
        END AS dst_dk_points
  FROM def_events e
  JOIN points_allowed p USING (season, week, team)
)
SELECT
  *,
  -- Point-in-time trailing form: strictly prior weeks only (1 PRECEDING).
  AVG(dst_dk_points) OVER (
    PARTITION BY team, season ORDER BY week
    ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS dst_points_l4,
  AVG(dst_dk_points) OVER (
    PARTITION BY team ORDER BY season, week
    ROWS BETWEEN 16 PRECEDING AND 1 PRECEDING) AS dst_points_l16
FROM scored;
