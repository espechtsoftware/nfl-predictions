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
-- The final schema preserves the complete event vector, both reconstructed
-- and authoritative scalar scores, explicit reconciliation status, a
-- deterministic event-vector hash, and strictly-prior component windows.
-- Legacy columns retain their original names and leading order; all new
-- component-form fields use the dst_event_ prefix so SELECT d.* consumers do
-- not collide with their own historical aliases.

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
    AND home_score IS NOT NULL AND away_score IS NOT NULL
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
    IF(COALESCE(safety, 0) = 1
       AND play_type IN ('pass', 'run', 'qb_kneel', 'qb_spike'), 1, 0)
      AS defensive_safeties,
    IF(punt_blocked = 1 OR field_goal_result = 'blocked'
       OR extra_point_result = 'blocked', 1, 0) AS blocked_kicks,
    0 AS return_tds,
    0 AS defensive_return_tds,
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
    0, 0, 1, 0, 0, 0, 0, 0, 0
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
    0, 0, 1, 0, 0, 0, 0, 0, 0
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
    0, 0, 0, 0, 0, 0, 1,
    IF(return_touchdown = 1 AND td_team = defteam
       AND play_type IN ('pass', 'run', 'qb_kneel', 'qb_spike'), 1, 0),
    0
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
    SUM(defensive_safeties) AS defensive_safeties,
    SUM(blocked_kicks) AS blocked_kicks,
    SUM(return_tds) AS return_tds,
    SUM(defensive_return_tds) AS defensive_return_tds,
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
       AND play_type IN ('pass', 'run', 'qb_kneel', 'qb_spike'), 6, 0)
      AS defensive_td_points,
    IF(safety = 1
       AND play_type IN ('pass', 'run', 'qb_kneel', 'qb_spike'), 2, 0)
      AS safety_points
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
    s.away_team AS opponent,
    s.away_score AS opponent_final_score,
    COALESCE(o.defensive_td_points, 0) AS excluded_defensive_td_points,
    COALESCE(o.safety_points, 0) AS excluded_safety_points,
    s.away_score - COALESCE(o.defensive_td_points, 0)
                 - COALESCE(o.safety_points, 0) AS pa
  FROM schedules_normalized s
  LEFT JOIN offense_points_not_allowed o
    ON o.game_id = s.game_id AND o.team = s.home_team

  UNION ALL

  SELECT
    s.game_id, s.season, s.week, s.away_team AS team,
    s.home_team AS opponent,
    s.home_score AS opponent_final_score,
    COALESCE(o.defensive_td_points, 0) AS excluded_defensive_td_points,
    COALESCE(o.safety_points, 0) AS excluded_safety_points,
    s.home_score - COALESCE(o.defensive_td_points, 0)
                 - COALESCE(o.safety_points, 0) AS pa
  FROM schedules_normalized s
  LEFT JOIN offense_points_not_allowed o
    ON o.game_id = s.game_id AND o.team = s.away_team
),
scored AS (
  SELECT
    e.game_id, e.season, e.week, e.team, p.opponent,
    p.opponent_final_score, p.pa,
    p.excluded_defensive_td_points, p.excluded_safety_points,
    p.excluded_defensive_td_points + p.excluded_safety_points
      AS excluded_non_dst_points,
    e.sacks, e.interceptions, e.fumble_recoveries, e.safeties,
    e.defensive_safeties, e.blocked_kicks, e.return_tds,
    e.defensive_return_tds, e.defensive_conversions,
    CASE
      WHEN p.pa = 0 THEN 10
      WHEN p.pa <= 6 THEN 7
      WHEN p.pa <= 13 THEN 4
      WHEN p.pa <= 20 THEN 1
      WHEN p.pa <= 27 THEN 0
      WHEN p.pa <= 34 THEN -1
      ELSE -4
    END AS points_allowed_tier_points,
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
        END AS reconstructed_dst_dk_points
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
    game_id, season, week, home_team AS team, away_team AS opponent
  FROM schedules_normalized
  UNION ALL
  SELECT
    game_id, season, week, away_team, home_team
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
historical_source_by_game AS (
  -- Preserve source multiplicity and rejected-opponent rows. The historical
  -- feed can carry an adjacent game's row under the same display week. The
  -- hurricane-rescheduled 2017 MIA-TB game is the only explicit exception:
  -- its complete, scored rows use opponent='-' for both teams.
  SELECT
    g.game_id, g.season, g.week, g.team, g.opponent,
    COUNT(h.team) AS authoritative_source_raw_rows,
    COUNTIF(
      h.opponent = g.opponent
      OR (h.season = 2017 AND h.week = 11 AND h.opponent = '-'
          AND ((h.team = 'MIA' AND g.opponent = 'TB')
               OR (h.team = 'TB' AND g.opponent = 'MIA')))
    ) AS authoritative_source_matched_rows,
    COUNT(h.team) - COUNTIF(
      h.opponent = g.opponent
      OR (h.season = 2017 AND h.week = 11 AND h.opponent = '-'
          AND ((h.team = 'MIA' AND g.opponent = 'TB')
               OR (h.team = 'TB' AND g.opponent = 'MIA')))
    ) AS authoritative_source_rejected_rows,
    COUNT(DISTINCT IF(
      h.opponent = g.opponent
      OR (h.season = 2017 AND h.week = 11 AND h.opponent = '-'
          AND ((h.team = 'MIA' AND g.opponent = 'TB')
               OR (h.team = 'TB' AND g.opponent = 'MIA'))),
      h.exact_dk_points,
      NULL
    )) AS authoritative_distinct_score_count,
    MIN(IF(
      h.opponent = g.opponent
      OR (h.season = 2017 AND h.week = 11 AND h.opponent = '-'
          AND ((h.team = 'MIA' AND g.opponent = 'TB')
               OR (h.team = 'TB' AND g.opponent = 'MIA'))),
      h.exact_dk_points,
      NULL
    )) AS sole_authoritative_dst_dk_points
  FROM schedule_games g
  LEFT JOIN historical_exact_raw h
    ON h.season = g.season AND h.week = g.week AND h.team = g.team
  GROUP BY g.game_id, g.season, g.week, g.team, g.opponent
),
canonical_base AS (
  SELECT
    n.*,
    h.authoritative_source_raw_rows,
    h.authoritative_source_matched_rows,
    h.authoritative_source_rejected_rows,
    h.authoritative_distinct_score_count,
    CASE
      WHEN h.authoritative_source_raw_rows = 0 THEN 'source_unavailable'
      WHEN h.authoritative_source_matched_rows = 0 THEN 'source_unmatched'
      WHEN h.authoritative_distinct_score_count > 1 THEN 'source_conflict'
      WHEN h.authoritative_source_rejected_rows > 0
        THEN 'source_partial_rejection'
      WHEN h.authoritative_source_matched_rows > 1
        THEN 'source_match_duplicate_identical'
      ELSE 'source_match_unique'
    END AS authoritative_source_status,
    IF(h.authoritative_distinct_score_count = 1,
       h.sole_authoritative_dst_dk_points, NULL)
      AS authoritative_dst_dk_points,
    COALESCE(
      IF(h.authoritative_distinct_score_count = 1,
         h.sole_authoritative_dst_dk_points, NULL),
      n.reconstructed_dst_dk_points
    )
      AS dst_dk_points,
    IF(h.authoritative_distinct_score_count = 1,
       h.sole_authoritative_dst_dk_points, NULL)
      - n.reconstructed_dst_dk_points
      AS score_reconciliation_delta,
    CASE
      WHEN h.authoritative_source_matched_rows = 0
        AND h.authoritative_source_raw_rows > 0 THEN 'source_unmatched'
      WHEN h.authoritative_distinct_score_count > 1 THEN 'source_conflict'
      WHEN h.authoritative_source_rejected_rows > 0
        THEN 'source_partial_rejection'
      WHEN h.authoritative_distinct_score_count = 0 THEN 'reconstruction_only'
      WHEN ABS(h.sole_authoritative_dst_dk_points
               - n.reconstructed_dst_dk_points) <= 1e-9
        THEN 'authoritative_match'
      ELSE 'authoritative_override_mismatch'
    END AS score_reconciliation_status,
    'dst-team-game-event-frame-2026-08-17-v1' AS event_frame_version,
    'draftkings-nfl-classic-dst-2026-08-17-v1' AS scoring_law_id,
    'fb0ac704f9bbc5d8fd96727280ad8ef7760b1a9d2456474dd760904543d7bbe5'
      AS scoring_law_source_sha256
  FROM normalized n
  JOIN historical_source_by_game h
    USING (game_id, season, week, team, opponent)
),
payloads AS (
  SELECT
    b.*,
    TO_JSON_STRING(STRUCT(
      b.event_frame_version AS event_frame_version,
      b.scoring_law_id AS scoring_law_id,
      b.game_id AS game_id,
      b.season AS season,
      b.week AS week,
      b.team AS team,
      b.opponent AS opponent,
      b.sacks AS sacks,
      b.interceptions AS interceptions,
      b.fumble_recoveries AS fumble_recoveries,
      b.safeties AS safeties,
      b.defensive_safeties AS defensive_safeties,
      b.blocked_kicks AS blocked_kicks,
      b.return_tds AS return_tds,
      b.defensive_return_tds AS defensive_return_tds,
      b.defensive_conversions AS defensive_conversions,
      b.opponent_final_score AS opponent_final_score,
      b.excluded_defensive_td_points AS excluded_defensive_td_points,
      b.excluded_safety_points AS excluded_safety_points,
      b.pa AS points_allowed,
      b.reconstructed_dst_dk_points AS reconstructed_dst_dk_points
    )) AS event_vector_payload
  FROM canonical_base b
),
canonical AS (
  SELECT
    p.*,
    TO_HEX(SHA256(event_vector_payload)) AS event_vector_sha256
  FROM payloads p
)
SELECT
  -- Preserve the exact legacy leading column order.
  season, week, pa, sacks, interceptions, fumble_recoveries, safeties,
  blocked_kicks, return_tds, team, dst_dk_points,
  -- Point-in-time trailing form: strictly prior weeks only (1 PRECEDING).
  AVG(dst_dk_points) OVER (
    PARTITION BY team, season ORDER BY week
    ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS dst_points_l4,
  AVG(dst_dk_points) OVER (
    PARTITION BY team ORDER BY season, week
    ROWS BETWEEN 16 PRECEDING AND 1 PRECEDING) AS dst_points_l16,
  game_id, opponent, opponent_final_score,
  excluded_defensive_td_points, excluded_safety_points,
  excluded_non_dst_points, defensive_safeties, defensive_return_tds,
  defensive_conversions, points_allowed_tier_points,
  reconstructed_dst_dk_points, authoritative_source_raw_rows,
  authoritative_source_matched_rows, authoritative_source_rejected_rows,
  authoritative_distinct_score_count, authoritative_source_status,
  authoritative_dst_dk_points, score_reconciliation_delta,
  score_reconciliation_status, event_frame_version, scoring_law_id,
  scoring_law_source_sha256, event_vector_payload, event_vector_sha256,
  COUNT(*) OVER w4 AS dst_event_games_prior_l4,
  COUNT(*) OVER w16 AS dst_event_games_prior_l16,
  AVG(sacks) OVER w4 AS dst_event_sacks_l4,
  AVG(interceptions) OVER w4 AS dst_event_interceptions_l4,
  AVG(fumble_recoveries) OVER w4 AS dst_event_fumble_recoveries_l4,
  AVG(safeties) OVER w4 AS dst_event_safeties_l4,
  AVG(blocked_kicks) OVER w4 AS dst_event_blocked_kicks_l4,
  AVG(return_tds) OVER w4 AS dst_event_return_tds_l4,
  AVG(defensive_conversions) OVER w4 AS dst_event_defensive_conversions_l4,
  AVG(pa) OVER w4 AS dst_event_points_allowed_l4,
  AVG(sacks) OVER w16 AS dst_event_sacks_l16,
  AVG(interceptions) OVER w16 AS dst_event_interceptions_l16,
  AVG(fumble_recoveries) OVER w16 AS dst_event_fumble_recoveries_l16,
  AVG(safeties) OVER w16 AS dst_event_safeties_l16,
  AVG(blocked_kicks) OVER w16 AS dst_event_blocked_kicks_l16,
  AVG(return_tds) OVER w16 AS dst_event_return_tds_l16,
  AVG(defensive_conversions) OVER w16 AS dst_event_defensive_conversions_l16,
  AVG(pa) OVER w16 AS dst_event_points_allowed_l16
FROM canonical
WINDOW
  w4 AS (PARTITION BY team, season ORDER BY week
         ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING),
  w16 AS (PARTITION BY team ORDER BY season, week
          ROWS BETWEEN 16 PRECEDING AND 1 PRECEDING);
