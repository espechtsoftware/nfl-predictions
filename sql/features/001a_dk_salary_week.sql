-- One salary row per player-week. This table is intentionally built before
-- actuals and usage: the historical replay universe must be the set of
-- players that could actually be selected from the DK salary file, not the
-- set that happened to record a target or carry.
--
-- Own snapshots win per player-week when both sources exist. Historical name
-- matching strips punctuation and generational suffixes. Historical weekly
-- roster identity on salary-side team/week is mandatory (position first).
-- The global player-id map may bridge football/legal names only when that
-- exact GSIS id is independently present on the same weekly roster; its
-- current-team field is never historical evidence. Team codes are normalized
-- on every source before identity and schedule joins.
CREATE OR REPLACE TABLE `${features}.dk_salary_week` AS
WITH own_log AS (
  SELECT
    m.gsis_id,
    CAST(s.season AS INT64) AS season,
    CAST(s.week AS INT64) AS week,
    s.dk_player_id,
    s.salary,
    s.status,
    s.dk_ppg,
    s.display_name,
    UPPER(s.position) AS position,
    CASE UPPER(s.team_abbr)
      WHEN 'GNB' THEN 'GB' WHEN 'KAN' THEN 'KC' WHEN 'JAC' THEN 'JAX'
      WHEN 'LAR' THEN 'LA' WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
      WHEN 'NOR' THEN 'NO' WHEN 'NWE' THEN 'NE' WHEN 'SFO' THEN 'SF'
      WHEN 'TAM' THEN 'TB' WHEN 'SD' THEN 'LAC' WHEN 'SDG' THEN 'LAC'
      WHEN 'STL' THEN 'LA'
      ELSE UPPER(s.team_abbr)
    END AS team,
    s.pulled_at,
    1 AS source_priority
  FROM `${raw}.dk_salaries` s
  JOIN `${features}.player_id_map` m USING (dk_player_id)
  WHERE s.slate_type = 'classic' AND s.week IS NOT NULL AND s.salary > 0
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY m.gsis_id, CAST(s.season AS INT64), CAST(s.week AS INT64)
    ORDER BY s.pulled_at DESC, s.dk_player_id
  ) = 1
),
norm_ids AS (
  SELECT DISTINCT
    gsis_id, UPPER(position) AS position,
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REGEXP_REPLACE(UPPER(TRIM(id_name)),
                       r'\s+(JR|SR|II|III|IV|V)\.?$', ''),
        r'[^A-Z ]', ''),
      r' +', ' ') AS clean_name
  FROM `${raw}.player_ids`, UNNEST([name, merge_name]) AS id_name
  WHERE gsis_id IS NOT NULL AND id_name IS NOT NULL
),
norm_rosters AS (
  -- Historical team/week identity resolves recycled names (for example the
  -- three NFL WRs named Mike Williams) without trusting player_ids.team,
  -- which is a current-team field. A salary row absent from that team's
  -- weekly roster remains unresolved rather than inheriting a later team.
  SELECT DISTINCT
    gsis_id, CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
    CASE UPPER(team)
      WHEN 'ARZ' THEN 'ARI' WHEN 'BLT' THEN 'BAL' WHEN 'CLV' THEN 'CLE'
      WHEN 'HST' THEN 'HOU' WHEN 'SL' THEN 'LA'
      WHEN 'GNB' THEN 'GB' WHEN 'KAN' THEN 'KC' WHEN 'JAC' THEN 'JAX'
      WHEN 'LAR' THEN 'LA' WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
      WHEN 'NOR' THEN 'NO' WHEN 'NWE' THEN 'NE' WHEN 'SFO' THEN 'SF'
      WHEN 'TAM' THEN 'TB' WHEN 'SD' THEN 'LAC' WHEN 'SDG' THEN 'LAC'
      WHEN 'STL' THEN 'LA' ELSE UPPER(team)
    END AS team,
    UPPER(position) AS position,
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REGEXP_REPLACE(UPPER(TRIM(roster_name)),
                       r'\s+(JR|SR|II|III|IV|V)\.?$', ''),
        r'[^A-Z ]', ''),
      r' +', ' ') AS clean_name
  FROM `${raw}.rosters_weekly`,
       UNNEST([full_name, CONCAT(football_name, ' ', last_name)]) AS roster_name
  WHERE gsis_id IS NOT NULL AND full_name IS NOT NULL
    AND roster_name IS NOT NULL
    AND game_type = 'REG'
),
schedule_games AS (
  SELECT
    season, week,
    CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE home_team END AS team,
    CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE away_team END AS opponent
  FROM `${raw}.schedules`
  WHERE game_type = 'REG'
  UNION ALL
  SELECT
    season, week,
    CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE away_team END,
    CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE home_team END
  FROM `${raw}.schedules`
  WHERE game_type = 'REG'
),
historical_name_aliases AS (
  -- Salary vendors use several football-name/marketing-name variants that
  -- neither full_name nor player_ids.name carries. These are stable identity
  -- aliases, not fuzzy guesses; team/week roster uniqueness is still required
  -- for the LineStar and DiscoveryLab regimes.
  SELECT * FROM UNNEST([
    STRUCT('BISI JOHNSON' AS source_name, 'OLABISI JOHNSON' AS roster_name),
    ('CHIG OKONKWO', 'CHIGOZIEM OKONKWO'),
    ('ELI MITCHELL', 'ELIJAH MITCHELL'),
    ('HOLLYWOOD BROWN', 'MARQUISE BROWN'),
    ('KENNY GAINWELL', 'KENNETH GAINWELL'),
    ('MITCH TRUBISKY', 'MITCHELL TRUBISKY'),
    ('NICK WESTBROOK', 'NICK WESTBROOKIKHINE'),
    ('PHILLY BROWN', 'COREY BROWN'),
    ('PJ WALKER', 'PHILLIP WALKER'),
    ('ROBBIE ANDERSON', 'ROBBY ANDERSON'),
    ('RODNEY WILLIAMS', 'ROD WILLIAMS'),
    ('SHAQ DAVIS', 'SHAQUAN DAVIS'),
    ('TYRON BILLY JOHNSON', 'TYRON JOHNSON')
  ])
),
historical_source AS (
  SELECT
    CAST(season AS INT64) AS season,
    CAST(week AS INT64) AS week,
    display_name,
    UPPER(position) AS position,
    CASE UPPER(team_abbr)
      WHEN 'GNB' THEN 'GB' WHEN 'KAN' THEN 'KC' WHEN 'JAC' THEN 'JAX'
      WHEN 'LAR' THEN 'LA' WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
      WHEN 'NOR' THEN 'NO' WHEN 'NWE' THEN 'NE' WHEN 'SFO' THEN 'SF'
      WHEN 'TAM' THEN 'TB' WHEN 'SD' THEN 'LAC' WHEN 'SDG' THEN 'LAC'
      WHEN 'STL' THEN 'LA'
      ELSE UPPER(team_abbr)
    END AS team,
    CASE UPPER(opponent)
      WHEN 'GNB' THEN 'GB' WHEN 'KAN' THEN 'KC' WHEN 'JAC' THEN 'JAX'
      WHEN 'LAR' THEN 'LA' WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
      WHEN 'NOR' THEN 'NO' WHEN 'NWE' THEN 'NE' WHEN 'SFO' THEN 'SF'
      WHEN 'TAM' THEN 'TB' WHEN 'SD' THEN 'LAC' WHEN 'SDG' THEN 'LAC'
      WHEN 'STL' THEN 'LA'
      ELSE UPPER(opponent)
    END AS opponent,
    CAST(salary AS INT64) AS salary,
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REGEXP_REPLACE(UPPER(TRIM(display_name)),
                       r'\s+(JR|SR|II|III|IV|V)\.?$', ''),
        r'[^A-Z ]', ''),
      r' +', ' ') AS clean_name
  FROM `${raw}.dk_salaries_historical`
  WHERE salary > 0
),
historical_corrected AS (
  -- LineStar's period payload combines multiple DK contest salary blocks.
  -- Prices are normally identical across blocks, but two trade-deadline
  -- players in 2024 W10 conflict even after matchup validation. The lower
  -- SalaryContainer IDs are in the Millionaire contest's owned-ID block
  -- (468692--469395); its Mike Williams row is independently linked by the
  -- contest ownership payload. Freeze both audited main-contest prices rather
  -- than applying an unjustified MIN/MAX rule to every historical duplicate.
  SELECT h.* REPLACE (
    CASE
      WHEN season = 2024 AND week = 10 AND clean_name = 'MIKE WILLIAMS'
           AND team = 'PIT' THEN 4100
      WHEN season = 2024 AND week = 10 AND clean_name = 'JONATHAN MINGO'
           AND team = 'DAL' THEN 3200
      ELSE salary
    END AS salary,
    COALESCE(a.roster_name, h.clean_name) AS clean_name
  )
  FROM historical_source h
  LEFT JOIN historical_name_aliases a ON a.source_name = h.clean_name
),
historical_norm AS (
  -- LineStar's adjacent-Thursday record can carry the following game's
  -- salary under the prior display week. Validate the matchup before any
  -- per-player aggregation; MAX(salary) previously selected the wrong row.
  -- DiscoveryLab's 2025 skill rows are a distinct one-row-per-player-week
  -- source and omit opponent (DST rows retain it). Validate their team/week
  -- against the schedule without inventing an opponent value.
  -- The hurricane-rescheduled 2017 MIA-TB game is the one older-source
  -- exception: its complete, scored salary rows use opponent='-' for both
  -- teams. Keep only that explicitly identified canonical matchup.
  SELECT
    h.season, h.week, h.display_name, h.position, h.team,
    MAX(h.salary) AS salary, h.clean_name
  FROM historical_corrected h
  JOIN schedule_games g
    ON g.season = h.season AND g.week = h.week
   AND g.team = h.team
   AND (g.opponent = h.opponent
        OR (h.season = 2025 AND h.opponent IS NULL
            AND h.position IN ('QB', 'RB', 'WR', 'TE'))
        OR (h.season = 2017 AND h.week = 11 AND h.opponent = '-'
            AND ((h.team = 'MIA' AND g.opponent = 'TB')
                 OR (h.team = 'TB' AND g.opponent = 'MIA'))))
  GROUP BY h.season, h.week, h.display_name, h.position, h.team, h.clean_name
),
historical_matched AS (
  SELECT
    h.season, h.week, h.display_name, h.position, h.team, h.salary,
    COALESCE(
      IF(COUNT(DISTINCT IF(r.position = h.position, r.gsis_id, NULL)) = 1,
         MAX(IF(r.position = h.position, r.gsis_id, NULL)), NULL),
      IF(COUNT(DISTINCT r.gsis_id) = 1, MAX(r.gsis_id), NULL),
      -- Salary/player-id football names can differ from the weekly roster's
      -- legal name (Jeff/Jeffery Wilson, Tank/Nathaniel Dell). Use the global
      -- name bridge only when that exact GSIS id is independently rostered on
      -- this salary-side team/week; this cannot revive a stale-team row.
      IF(COUNT(DISTINCT IF(ir.position = h.position, ir.gsis_id, NULL)) = 1,
         MAX(IF(ir.position = h.position, ir.gsis_id, NULL)), NULL),
      IF(COUNT(DISTINCT ir.gsis_id) = 1, MAX(ir.gsis_id), NULL)
    ) AS gsis_id
  FROM historical_norm h
  LEFT JOIN norm_rosters r
    ON r.season = h.season AND r.week = h.week
   AND r.team = h.team AND r.clean_name = h.clean_name
  LEFT JOIN norm_ids i ON i.clean_name = h.clean_name
  LEFT JOIN norm_rosters ir
    ON ir.season = h.season AND ir.week = h.week
   AND ir.team = h.team AND ir.gsis_id = i.gsis_id
  GROUP BY h.season, h.week, h.display_name, h.position, h.team, h.salary
),
historical AS (
  SELECT
    gsis_id, season, week,
    CAST(NULL AS INT64) AS dk_player_id,
    salary,
    CAST(NULL AS STRING) AS status,
    CAST(NULL AS FLOAT64) AS dk_ppg,
    display_name, position, team,
    CAST(NULL AS TIMESTAMP) AS pulled_at,
    2 AS source_priority
  FROM historical_matched
  WHERE gsis_id IS NOT NULL
),
deduped AS (
  SELECT *
  FROM (
    SELECT * FROM own_log
    UNION ALL
    SELECT * FROM historical
  )
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY gsis_id, season, week
    ORDER BY source_priority, pulled_at DESC, dk_player_id
  ) = 1
)
SELECT
  gsis_id, season, week, dk_player_id, salary, status, dk_ppg,
  display_name, position, team,
  salary - LAG(salary) OVER (PARTITION BY gsis_id, season ORDER BY week)
    AS salary_delta_wow
FROM deduped;
