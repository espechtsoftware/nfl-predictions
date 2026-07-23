-- DK player id <-> GSIS id crosswalk. Name matching alone fails on suffixes,
-- apostrophes, and ~two dozen collisions per season, so we require
-- (normalized name, team, position) to agree, then patch the remainder via
-- the manual override table. Fail loudly on unmatched slate players — a
-- dropped player is a lineup you can't build (see leakage/QA checks).

CREATE TABLE IF NOT EXISTS `${features}.player_id_overrides` (
  dk_player_id INT64,
  gsis_id STRING,
  note STRING
);

CREATE OR REPLACE TABLE `${features}.player_id_map` AS
WITH dk AS (
  SELECT DISTINCT dk_player_id, display_name, team_abbr, position
  FROM `${raw}.dk_salaries`
  WHERE pulled_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
),
norm_dk AS (
  SELECT
    dk_player_id, display_name, team_abbr, position,
    REGEXP_REPLACE(
      REGEXP_REPLACE(UPPER(display_name), r"\s+(JR|SR|II|III|IV|V)\.?$", ""),
      r"[^A-Z ]", "") AS clean_name
  FROM dk
),
norm_nfl AS (
  SELECT
    gsis_id, name, team, position,
    REGEXP_REPLACE(
      REGEXP_REPLACE(UPPER(name), r"\s+(JR|SR|II|III|IV|V)\.?$", ""),
      r"[^A-Z ]", "") AS clean_name
  FROM `${raw}.player_ids`
  WHERE gsis_id IS NOT NULL
),
matched AS (
  SELECT d.dk_player_id, n.gsis_id, d.display_name, d.team_abbr, d.position,
         'auto' AS match_source
  FROM norm_dk d
  JOIN norm_nfl n
    ON d.clean_name = n.clean_name
   AND d.team_abbr  = n.team
   AND d.position   = n.position
)
SELECT * FROM matched
UNION ALL
SELECT o.dk_player_id, o.gsis_id, d.display_name, d.team_abbr, d.position,
       'manual' AS match_source
FROM `${features}.player_id_overrides` o
JOIN norm_dk d USING (dk_player_id)
WHERE o.dk_player_id NOT IN (SELECT dk_player_id FROM matched);
