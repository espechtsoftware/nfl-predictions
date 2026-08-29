-- DK player id <-> GSIS id crosswalk. Name matching alone fails on suffixes,
-- apostrophes, and ~two dozen collisions per season, so we require
-- (normalized name, canonical team, position) to agree. nflverse's fantasy
-- crosswalk uses provider codes such as NOS/TBB/LVR/GBP/JAC, while DK uses
-- NO/TB/LV/GB/JAX; comparing those representations directly dropped entire
-- teams from the live pool.
--
-- Some current UDFAs/camp players reach the weekly roster feed before the
-- fantasy crosswalk. They may fall back to the latest roster season only
-- when normalized name + canonical team + position identifies exactly one
-- distinct GSIS id. Ambiguous roster identities produce no mapping. Existing
-- precedence remains explicit: reviewed manual overrides first, then the
-- fantasy crosswalk, vetted name aliases, current weekly roster, and finally
-- the current exact depth-chart identity. Each automatic source admits only one
-- distinct GSIS id; ambiguous or team/position-conflicted rows remain
-- unmatched. Fail loudly on anything still unmatched -- a dropped player is
-- a lineup you cannot build (see leakage/QA checks).

CREATE TABLE IF NOT EXISTS `${features}.player_id_overrides` (
  dk_player_id INT64,
  gsis_id STRING,
  note STRING
);

-- Duplicate copies of one reviewed mapping are harmless and collapse below;
-- conflicting or NULL authorities are not. A manual correction must never
-- fan out the live pool or silently fall through to an automatic identity.
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT dk_player_id
    FROM `${features}.player_id_overrides`
    GROUP BY dk_player_id
    HAVING dk_player_id IS NULL
       OR COUNTIF(gsis_id IS NULL) > 0
       OR COUNT(DISTINCT gsis_id) != 1
  )
) AS 'player_id_overrides contains a NULL or conflicting DK-to-GSIS authority';

-- Bind all live fallbacks to the season of the newest DK intake, not to the
-- maximum season that happens to remain in a raw source. The NFLverse job
-- stamps its capture time on every replacement row; a stale or incomplete
-- source is a hard feature-build failure.
ASSERT COALESCE((
  SELECT
    COUNT(DISTINCT r.team) = 32
    AND COUNT(DISTINCT r.gsis_id) >= 1000
    AND MAX(r.nflverse_pulled_at) >=
        TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 72 HOUR)
  FROM `${raw}.rosters_weekly` r
  WHERE CAST(r.season AS INT64) = (
    SELECT MAX(CAST(season AS INT64))
    FROM `${raw}.dk_salaries`
    WHERE season IS NOT NULL
      AND slate_type = 'classic'
      AND pulled_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
  )
), FALSE) AS 'live DK season lacks a fresh complete 32-team weekly-roster receipt';

ASSERT COALESCE((
  SELECT
    COUNT(DISTINCT team) = 32
    AND COUNT(DISTINCT gsis_id) >= 1000
    AND MIN(team_latest) >=
        TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
    AND MAX(source_pulled_at) >=
        TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 72 HOUR)
  FROM (
    SELECT
      team,
      gsis_id,
      MAX(TIMESTAMP(dt)) OVER (PARTITION BY team) AS team_latest,
      nflverse_pulled_at AS source_pulled_at
    FROM `${raw}.depth_charts_snapshots`
    WHERE team IS NOT NULL AND gsis_id IS NOT NULL
      AND TIMESTAMP(dt) >=
          TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
      AND TIMESTAMP(dt) <=
          TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
  )
), FALSE) AS 'current depth source lacks a fresh complete 32-team receipt';

CREATE OR REPLACE TABLE `${features}.player_id_map` AS
WITH dk AS (
  -- The same DK id can appear under an earlier team elsewhere in the
  -- 365-day intake window. Keep one deterministic latest identity so this
  -- table can never fan out a live slate join merely because a player moved.
  SELECT dk_player_id, display_name, team_abbr, position
  FROM `${raw}.dk_salaries`
  WHERE pulled_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY dk_player_id
    ORDER BY pulled_at DESC, draft_group_id DESC, dk_draftable_id DESC
  ) = 1
),
live_dk_season AS (
  SELECT MAX(CAST(season AS INT64)) AS season
  FROM `${raw}.dk_salaries`
  WHERE season IS NOT NULL
    AND slate_type = 'classic'
    AND pulled_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
),
norm_dk AS (
  SELECT
    dk_player_id, display_name, team_abbr, UPPER(position) AS position,
    CASE UPPER(TRIM(team_abbr))
      WHEN 'ARZ' THEN 'ARI'
      WHEN 'BLT' THEN 'BAL'
      WHEN 'CLV' THEN 'CLE'
      WHEN 'HST' THEN 'HOU'
      WHEN 'GBP' THEN 'GB' WHEN 'GNB' THEN 'GB'
      WHEN 'JAC' THEN 'JAX'
      WHEN 'KCC' THEN 'KC' WHEN 'KAN' THEN 'KC'
      WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
      WHEN 'LAR' THEN 'LA' WHEN 'RAM' THEN 'LA' WHEN 'STL' THEN 'LA'
      WHEN 'NEP' THEN 'NE' WHEN 'NWE' THEN 'NE'
      WHEN 'NOS' THEN 'NO' WHEN 'NOR' THEN 'NO'
      WHEN 'SDC' THEN 'LAC' WHEN 'SDG' THEN 'LAC' WHEN 'SD' THEN 'LAC'
      WHEN 'SFO' THEN 'SF'
      WHEN 'TBB' THEN 'TB' WHEN 'TAM' THEN 'TB'
      WHEN 'WSH' THEN 'WAS'
      ELSE UPPER(TRIM(team_abbr))
    END AS canonical_team,
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REGEXP_REPLACE(UPPER(TRIM(display_name)),
                       r"\s+(JR|SR|II|III|IV|V)\.?$", ""),
        r"[^A-Z ]", ""),
      r" +", " ") AS clean_name
  FROM dk
),
unique_manual_overrides AS (
  SELECT dk_player_id, ANY_VALUE(gsis_id) AS gsis_id
  FROM `${features}.player_id_overrides`
  GROUP BY dk_player_id
  HAVING dk_player_id IS NOT NULL
     AND COUNTIF(gsis_id IS NULL) = 0
     AND COUNT(DISTINCT gsis_id) = 1
),
manual_matches AS (
  SELECT
    o.dk_player_id, o.gsis_id, d.display_name, d.team_abbr, d.position,
    'manual' AS match_source
  FROM unique_manual_overrides o
  JOIN norm_dk d USING (dk_player_id)
),
norm_nfl AS (
  SELECT DISTINCT
    p.gsis_id, UPPER(p.position) AS position,
    CASE UPPER(TRIM(p.team))
      WHEN 'ARZ' THEN 'ARI'
      WHEN 'BLT' THEN 'BAL'
      WHEN 'CLV' THEN 'CLE'
      WHEN 'HST' THEN 'HOU'
      WHEN 'GBP' THEN 'GB' WHEN 'GNB' THEN 'GB'
      WHEN 'JAC' THEN 'JAX'
      WHEN 'KCC' THEN 'KC' WHEN 'KAN' THEN 'KC'
      WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
      WHEN 'LAR' THEN 'LA' WHEN 'RAM' THEN 'LA' WHEN 'STL' THEN 'LA'
      WHEN 'NEP' THEN 'NE' WHEN 'NWE' THEN 'NE'
      WHEN 'NOS' THEN 'NO' WHEN 'NOR' THEN 'NO'
      WHEN 'SDC' THEN 'LAC' WHEN 'SDG' THEN 'LAC' WHEN 'SD' THEN 'LAC'
      WHEN 'SFO' THEN 'SF'
      WHEN 'TBB' THEN 'TB' WHEN 'TAM' THEN 'TB'
      WHEN 'WSH' THEN 'WAS'
      ELSE UPPER(TRIM(p.team))
    END AS canonical_team,
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REGEXP_REPLACE(UPPER(TRIM(id_name)),
                       r"\s+(JR|SR|II|III|IV|V)\.?$", ""),
        r"[^A-Z ]", ""),
      r" +", " ") AS clean_name
  FROM `${raw}.player_ids` p,
       UNNEST([p.name, p.merge_name]) AS id_name
  WHERE p.gsis_id IS NOT NULL AND id_name IS NOT NULL
),
unique_player_id_identity AS (
  SELECT
    clean_name, canonical_team, position,
    ANY_VALUE(gsis_id) AS gsis_id
  FROM norm_nfl
  WHERE clean_name != '' AND canonical_team IS NOT NULL
  GROUP BY clean_name, canonical_team, position
  HAVING COUNT(DISTINCT gsis_id) = 1
),
matched AS (
  SELECT d.dk_player_id, n.gsis_id, d.display_name, d.team_abbr, d.position,
         'auto' AS match_source
  FROM norm_dk d
  JOIN unique_player_id_identity n
    ON d.clean_name = n.clean_name
   AND d.canonical_team = n.canonical_team
   AND d.position   = n.position
  WHERE NOT EXISTS (
    SELECT 1 FROM manual_matches m WHERE m.dk_player_id = d.dk_player_id
  )
),
current_roster_season AS (
  SELECT season FROM live_dk_season
),
current_roster_latest_week AS (
  SELECT r.gsis_id, MAX(CAST(r.week AS INT64)) AS week
  FROM `${raw}.rosters_weekly` r
  CROSS JOIN current_roster_season s
  WHERE CAST(r.season AS INT64) = s.season
    AND r.gsis_id IS NOT NULL
    AND r.nflverse_pulled_at >=
        TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 72 HOUR)
  GROUP BY r.gsis_id
),
current_roster AS (
  SELECT DISTINCT
    r.gsis_id, roster_name, r.team, UPPER(r.position) AS position,
    CASE UPPER(TRIM(r.team))
      WHEN 'ARZ' THEN 'ARI'
      WHEN 'BLT' THEN 'BAL'
      WHEN 'CLV' THEN 'CLE'
      WHEN 'HST' THEN 'HOU'
      WHEN 'GBP' THEN 'GB' WHEN 'GNB' THEN 'GB'
      WHEN 'JAC' THEN 'JAX'
      WHEN 'KCC' THEN 'KC' WHEN 'KAN' THEN 'KC'
      WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
      WHEN 'LAR' THEN 'LA' WHEN 'RAM' THEN 'LA' WHEN 'STL' THEN 'LA'
      WHEN 'NEP' THEN 'NE' WHEN 'NWE' THEN 'NE'
      WHEN 'NOS' THEN 'NO' WHEN 'NOR' THEN 'NO'
      WHEN 'SDC' THEN 'LAC' WHEN 'SDG' THEN 'LAC' WHEN 'SD' THEN 'LAC'
      WHEN 'SFO' THEN 'SF'
      WHEN 'TBB' THEN 'TB' WHEN 'TAM' THEN 'TB'
      WHEN 'WSH' THEN 'WAS'
      ELSE UPPER(TRIM(r.team))
    END AS canonical_team,
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REGEXP_REPLACE(UPPER(TRIM(roster_name)),
                       r"\s+(JR|SR|II|III|IV|V)\.?$", ""),
        r"[^A-Z ]", ""),
      r" +", " ") AS clean_name
  FROM `${raw}.rosters_weekly` r,
       UNNEST([r.full_name, CONCAT(r.football_name, ' ', r.last_name)])
         AS roster_name
  CROSS JOIN current_roster_season s
  JOIN current_roster_latest_week w
    ON w.gsis_id = r.gsis_id AND w.week = CAST(r.week AS INT64)
  WHERE CAST(r.season AS INT64) = s.season
    AND r.gsis_id IS NOT NULL
    AND r.nflverse_pulled_at >=
        TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 72 HOUR)
    AND r.position IN ('QB', 'RB', 'WR', 'TE')
    AND roster_name IS NOT NULL
),
unique_roster_identity AS (
  SELECT
    clean_name, canonical_team, position,
    ANY_VALUE(gsis_id) AS gsis_id
  FROM current_roster
  WHERE clean_name != '' AND canonical_team IS NOT NULL
  GROUP BY clean_name, canonical_team, position
  HAVING COUNT(DISTINCT gsis_id) = 1
),
explicit_name_aliases AS (
  -- Reviewed 2026 source-name differences. Both sides still require the same
  -- canonical team and position and a unique player_ids identity. Joshua's
  -- current DK IR status remains an independent downstream exclusion signal.
  SELECT * FROM UNNEST([
    STRUCT('KENNY GAINWELL' AS source_clean_name,
           'KENNETH GAINWELL' AS target_clean_name),
    ('HOLLYWOOD BROWN', 'MARQUISE BROWN'),
    ('NICK SINGLETON', 'NICHOLAS SINGLETON'),
    ('JOSHUA PITSENBERGER', 'JOSH PITSENBERGER'),
    ('MATT HIBNER', 'MATTHEW HIBNER')
  ])
),
alias_matches AS (
  SELECT
    d.dk_player_id, n.gsis_id, d.display_name, d.team_abbr, d.position,
    'explicit_name_alias' AS match_source
  FROM norm_dk d
  JOIN explicit_name_aliases a
    ON a.source_clean_name = d.clean_name
  JOIN unique_player_id_identity n
    ON n.clean_name = a.target_clean_name
   AND n.canonical_team = d.canonical_team
   AND n.position = d.position
  WHERE NOT EXISTS (
    SELECT 1 FROM matched m WHERE m.dk_player_id = d.dk_player_id
  ) AND NOT EXISTS (
    SELECT 1 FROM manual_matches m WHERE m.dk_player_id = d.dk_player_id
  )
),
preserved_matches AS (
  SELECT * FROM manual_matches
  UNION ALL
  SELECT * FROM matched
  UNION ALL
  SELECT * FROM alias_matches
),
roster_fallback AS (
  SELECT
    d.dk_player_id, r.gsis_id, d.display_name, d.team_abbr, d.position,
    'roster_fallback' AS match_source
  FROM norm_dk d
  JOIN unique_roster_identity r
    ON r.clean_name = d.clean_name
   AND r.canonical_team = d.canonical_team
   AND r.position = d.position
  WHERE NOT EXISTS (
    SELECT 1 FROM preserved_matches p WHERE p.dk_player_id = d.dk_player_id
  )
),
roster_augmented_matches AS (
  SELECT * FROM preserved_matches
  UNION ALL
  SELECT * FROM roster_fallback
),
latest_depth_rows AS (
  SELECT
    gsis_id, player_name, team, pos_abb,
    CASE UPPER(TRIM(team))
      WHEN 'ARZ' THEN 'ARI'
      WHEN 'BLT' THEN 'BAL'
      WHEN 'CLV' THEN 'CLE'
      WHEN 'HST' THEN 'HOU'
      WHEN 'GBP' THEN 'GB' WHEN 'GNB' THEN 'GB'
      WHEN 'JAC' THEN 'JAX'
      WHEN 'KCC' THEN 'KC' WHEN 'KAN' THEN 'KC'
      WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
      WHEN 'LAR' THEN 'LA' WHEN 'RAM' THEN 'LA' WHEN 'STL' THEN 'LA'
      WHEN 'NEP' THEN 'NE' WHEN 'NWE' THEN 'NE'
      WHEN 'NOS' THEN 'NO' WHEN 'NOR' THEN 'NO'
      WHEN 'SDC' THEN 'LAC' WHEN 'SDG' THEN 'LAC' WHEN 'SD' THEN 'LAC'
      WHEN 'SFO' THEN 'SF'
      WHEN 'TBB' THEN 'TB' WHEN 'TAM' THEN 'TB'
      WHEN 'WSH' THEN 'WAS'
      ELSE UPPER(TRIM(team))
    END AS canonical_team,
    UPPER(pos_abb) AS position,
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REGEXP_REPLACE(UPPER(TRIM(player_name)),
                       r"\s+(JR|SR|II|III|IV|V)\.?$", ""),
        r"[^A-Z ]", ""),
      r" +", " ") AS clean_name
  FROM `${raw}.depth_charts_snapshots`
  WHERE gsis_id IS NOT NULL
    AND player_name IS NOT NULL
    AND UPPER(pos_abb) IN ('QB', 'RB', 'WR', 'TE')
    AND nflverse_pulled_at >=
        TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 72 HOUR)
    AND TIMESTAMP(dt) >=
        TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
  QUALIFY TIMESTAMP(dt) = MAX(TIMESTAMP(dt)) OVER (PARTITION BY team)
),
unique_depth_identity AS (
  SELECT
    clean_name, canonical_team, position,
    ANY_VALUE(gsis_id) AS gsis_id
  FROM latest_depth_rows
  WHERE clean_name != '' AND canonical_team IS NOT NULL
  GROUP BY clean_name, canonical_team, position
  HAVING COUNT(DISTINCT gsis_id) = 1
),
depth_fallback AS (
  SELECT
    d.dk_player_id, x.gsis_id, d.display_name, d.team_abbr, d.position,
    'current_depth_fallback' AS match_source
  FROM norm_dk d
  JOIN unique_depth_identity x
    ON x.clean_name = d.clean_name
   AND x.canonical_team = d.canonical_team
   AND x.position = d.position
  WHERE NOT EXISTS (
    SELECT 1 FROM roster_augmented_matches p
    WHERE p.dk_player_id = d.dk_player_id
  )
)
SELECT * FROM roster_augmented_matches
UNION ALL
SELECT * FROM depth_fallback;

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT dk_player_id
    FROM `${features}.player_id_map`
    GROUP BY dk_player_id
    HAVING COUNT(*) != 1 OR COUNT(DISTINCT gsis_id) != 1
  )
) AS 'player_id_map contains a duplicate or conflicting DK identity';
