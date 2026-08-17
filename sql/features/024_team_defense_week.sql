-- Team-defense (DST) DK scoring per week, computed from play-by-play +
-- schedules, plus point-in-time trailing form. This is the in-season DST
-- actuals source (issue #7): dk_salaries_historical only covers seasons
-- someone exported, while pbp arrives weekly all season.
--
-- DK DST scoring: sack +1, INT +2, opponent-fumble recovery +2, def/ST
-- return TD +6, safety +2, blocked kick +2, defensive conversion +2, plus
-- the points-allowed tier. Points surrendered by the offense (defensive TDs
-- and safeties) do not count toward the DST's points-allowed bracket.
--
-- Do not group all events by defteam. On kicks and punts, nflverse's
-- defteam is not necessarily the fantasy defense receiving the recovery or
-- TD. Event-credit rows below use the recovery/TD team explicitly. This
-- scorer exactly reproduced all 17 known 2025 Milly-winning DST scores; the
-- former approximation omitted safeties, blocks, special-teams recoveries,
-- and some return TDs.
--
-- Scoring-law contract: draftkings-nfl-classic-dst-2026-08-17-v1.
-- Current official DK NFL Classic rules contain no yards-allowed fantasy
-- component. A defensive 2-point/extra-point return earns +2 for the returning
-- DST and also remains in the opposing DST's points-allowed total; only points
-- surrendered while that team's offense is on the field are excluded below.

CREATE OR REPLACE TABLE `${features}.team_defense_week` AS
WITH schedules_normalized AS (
  -- nflverse play-by-play uses current franchise codes for relocated teams
  -- even when the historical schedule still says OAK/SD/STL. Normalize the
  -- schedule before every event/points-allowed join; normalizing only the
  -- final scored rows silently dropped those defenses altogether.
  SELECT
    * EXCEPT(home_team, away_team),
    CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE home_team END AS home_team,
    CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE away_team END AS away_team
  FROM `${raw}.schedules`
  WHERE game_type = 'REG'
),
event_credits AS (
  SELECT
    game_id, season, week,
    CASE defteam WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                 WHEN 'STL' THEN 'LA' ELSE defteam END AS team,
    CAST(COALESCE(sack, 0) AS INT64) AS sacks,
    CAST(COALESCE(interception, 0) AS INT64) AS interceptions,
    0 AS fumble_recoveries,
    CAST(COALESCE(safety, 0) AS INT64) AS safeties,
    IF(punt_blocked = 1 OR field_goal_result = 'blocked'
       OR extra_point_result = 'blocked', 1, 0) AS blocked_kicks,
    0 AS return_tds,
    CAST(COALESCE(defensive_two_point_conv, 0) AS INT64)
      AS defensive_conversions
  FROM `${raw}.pbp`
  WHERE defteam IS NOT NULL AND season_type = 'REG'

  UNION ALL

  SELECT
    game_id, season, week,
    CASE fumble_recovery_1_team
      WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
      WHEN 'STL' THEN 'LA' ELSE fumble_recovery_1_team END,
    0, 0, 1, 0, 0, 0, 0
  FROM `${raw}.pbp`
  WHERE season_type = 'REG'
    AND fumble_recovery_1_team IS NOT NULL
    AND fumbled_1_team IS NOT NULL
    AND fumble_recovery_1_team != fumbled_1_team

  UNION ALL

  SELECT
    game_id, season, week,
    CASE fumble_recovery_2_team
      WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
      WHEN 'STL' THEN 'LA' ELSE fumble_recovery_2_team END,
    0, 0, 1, 0, 0, 0, 0
  FROM `${raw}.pbp`
  WHERE season_type = 'REG'
    AND fumble_recovery_2_team IS NOT NULL
    AND fumbled_2_team IS NOT NULL
    AND fumble_recovery_2_team != fumbled_2_team

  UNION ALL

  SELECT
    game_id, season, week,
    CASE td_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                 WHEN 'STL' THEN 'LA' ELSE td_team END,
    0, 0, 0, 0, 0, 1, 0
  FROM `${raw}.pbp`
  WHERE season_type = 'REG'
    AND touchdown = 1
    AND td_team IS NOT NULL
    AND ((return_touchdown = 1 AND td_team = defteam)
         OR play_type IN ('kickoff', 'punt', 'field_goal'))
),
def_events AS (
  SELECT
    game_id, season, week, team,
    SUM(sacks) AS sacks,
    SUM(interceptions) AS interceptions,
    SUM(fumble_recoveries) AS fumble_recoveries,
    SUM(safeties) AS safeties,
    SUM(blocked_kicks) AS blocked_kicks,
    SUM(return_tds) AS return_tds,
    SUM(defensive_conversions) AS defensive_conversions
  FROM event_credits
  GROUP BY game_id, season, week, team
),
offense_points_not_allowed_raw AS (
  SELECT
    game_id,
    CASE posteam WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                  WHEN 'STL' THEN 'LA' ELSE posteam END AS team,
    IF(return_touchdown = 1 AND td_team = defteam
       AND play_type IN ('pass', 'run'), 6, 0) AS defensive_td_points,
    IF(safety = 1, 2, 0) AS safety_points
  FROM `${raw}.pbp`
  WHERE season_type = 'REG' AND posteam IS NOT NULL
),
offense_points_not_allowed AS (
  SELECT game_id, team,
         SUM(defensive_td_points) AS defensive_td_points,
         SUM(safety_points) AS safety_points
  FROM offense_points_not_allowed_raw
  GROUP BY game_id, team
),
points_allowed AS (
  SELECT
    s.game_id, s.season, s.week, s.home_team AS team,
    GREATEST(0, s.away_score - COALESCE(o.defensive_td_points, 0)
                              - COALESCE(o.safety_points, 0)) AS pa
  FROM schedules_normalized s
  LEFT JOIN offense_points_not_allowed o
    ON o.game_id = s.game_id AND o.team = s.home_team

  UNION ALL

  SELECT
    s.game_id, s.season, s.week, s.away_team AS team,
    GREATEST(0, s.home_score - COALESCE(o.defensive_td_points, 0)
                              - COALESCE(o.safety_points, 0)) AS pa
  FROM schedules_normalized s
  LEFT JOIN offense_points_not_allowed o
    ON o.game_id = s.game_id AND o.team = s.away_team
),
scored AS (
  SELECT
    e.season, e.week, e.team, p.pa,
    e.sacks, e.interceptions, e.fumble_recoveries, e.safeties,
    e.blocked_kicks, e.return_tds,
    e.sacks * 1 + e.interceptions * 2 + e.fumble_recoveries * 2
      + e.safeties * 2 + e.blocked_kicks * 2 + e.return_tds * 6
      + e.defensive_conversions * 2
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
  JOIN points_allowed p USING (game_id, season, week, team)
),
normalized AS (
  SELECT
    * EXCEPT(team),
    CASE team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
              WHEN 'STL' THEN 'LA' ELSE team END AS team
  FROM scored
),
schedule_games AS (
  SELECT
    season, week, home_team AS team, away_team AS opponent
  FROM schedules_normalized
  UNION ALL
  SELECT
    season, week, away_team, home_team
  FROM schedules_normalized
),
historical_exact_raw AS (
  SELECT
    CAST(season AS INT64) AS season,
    CAST(week AS INT64) AS week,
    CASE UPPER(team_abbr)
      WHEN 'GNB' THEN 'GB' WHEN 'JAC' THEN 'JAX' WHEN 'KAN' THEN 'KC'
      WHEN 'LAR' THEN 'LA' WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
      WHEN 'NOR' THEN 'NO' WHEN 'NWE' THEN 'NE' WHEN 'SFO' THEN 'SF'
      WHEN 'TAM' THEN 'TB' WHEN 'SD' THEN 'LAC' WHEN 'SDG' THEN 'LAC'
      WHEN 'STL' THEN 'LA'
      ELSE UPPER(team_abbr)
    END AS team,
    CASE UPPER(opponent)
      WHEN 'GNB' THEN 'GB' WHEN 'JAC' THEN 'JAX' WHEN 'KAN' THEN 'KC'
      WHEN 'LAR' THEN 'LA' WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
      WHEN 'NOR' THEN 'NO' WHEN 'NWE' THEN 'NE' WHEN 'SFO' THEN 'SF'
      WHEN 'TAM' THEN 'TB' WHEN 'SD' THEN 'LAC' WHEN 'SDG' THEN 'LAC'
      WHEN 'STL' THEN 'LA'
      ELSE UPPER(opponent)
    END AS opponent,
    CAST(dk_points AS FLOAT64) AS exact_dk_points
  FROM `${raw}.dk_salaries_historical`
  WHERE UPPER(position) IN ('DEF', 'DST') AND dk_points IS NOT NULL
),
historical_exact AS (
  -- Match the actual NFL opponent before deduplication. The historical feed
  -- can carry the adjacent game's row under the same display week. The
  -- hurricane-rescheduled 2017 MIA-TB game is the only explicit exception:
  -- its complete, scored rows use opponent='-' for both teams.
  SELECT h.season, h.week, h.team, MAX(h.exact_dk_points) AS exact_dk_points
  FROM historical_exact_raw h
  JOIN schedule_games g
   ON g.season = h.season AND g.week = h.week
   AND g.team = h.team
   AND (g.opponent = h.opponent
        OR (h.season = 2017 AND h.week = 11 AND h.opponent = '-'
            AND ((h.team = 'MIA' AND g.opponent = 'TB')
                 OR (h.team = 'TB' AND g.opponent = 'MIA'))))
  GROUP BY h.season, h.week, h.team
),
canonical AS (
  SELECT
    n.* EXCEPT(dst_dk_points),
    COALESCE(h.exact_dk_points, n.dst_dk_points) AS dst_dk_points
  FROM normalized n
  LEFT JOIN historical_exact h USING (season, week, team)
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
FROM canonical;
