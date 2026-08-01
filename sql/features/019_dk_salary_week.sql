-- One salary row per player-week: the last classic-slate pull before lock,
-- unioned with the RotoGuru historical backfill for pre-logging seasons.
-- salary_delta_wow (week over week) is the input to the salary-lag alert.
CREATE OR REPLACE TABLE `${features}.dk_salary_week` AS
WITH own_log AS (
  SELECT
    m.gsis_id, s.season, s.week, s.dk_player_id,
    ARRAY_AGG(s.salary ORDER BY s.pulled_at DESC LIMIT 1)[OFFSET(0)] AS salary,
    ARRAY_AGG(s.status ORDER BY s.pulled_at DESC LIMIT 1)[OFFSET(0)] AS status,
    ARRAY_AGG(s.dk_ppg ORDER BY s.pulled_at DESC LIMIT 1)[OFFSET(0)] AS dk_ppg
  FROM `${raw}.dk_salaries` s
  JOIN `${features}.player_id_map` m USING (dk_player_id)
  WHERE s.slate_type = 'classic' AND s.week IS NOT NULL
  GROUP BY 1, 2, 3, 4
),
historical AS (
  -- RotoGuru rows matched by normalized name, disambiguated by position;
  -- lower fidelity, only used for seasons before our own log starts.
  -- Team is deliberately NOT part of the match: player_ids carries only a
  -- player's CURRENT team, and RotoGuru uses a different abbreviation
  -- convention (GNB/KAN/NWE), so a team condition silently drops nearly
  -- every row for players who ever changed teams.
  SELECT
    gsis_id, season, week,
    CAST(NULL AS INT64) AS dk_player_id,
    salary,
    CAST(NULL AS STRING) AS status,
    CAST(NULL AS FLOAT64) AS dk_ppg
  FROM (
    SELECT
      -- Grouped by (name, position), NOT rotoguru_gid: LineStar-backfilled
      -- rows (2022-24, see ingest/linestar_backfill.py) carry NULL gid,
      -- which would collapse a whole week into one ambiguous group.
      h.season, h.week, h.display_name, h.position,
      ANY_VALUE(h.salary) AS salary,
      -- Unique name+position candidate first; unique name-only as fallback
      -- (position occasionally recorded differently, e.g. FB vs RB); rows
      -- ambiguous under both rules are dropped rather than guessed.
      COALESCE(
        IF(COUNT(DISTINCT IF(UPPER(i.position) = UPPER(h.position), i.gsis_id, NULL)) = 1,
           MAX(IF(UPPER(i.position) = UPPER(h.position), i.gsis_id, NULL)), NULL),
        IF(COUNT(DISTINCT i.gsis_id) = 1, MAX(i.gsis_id), NULL)
      ) AS gsis_id
    FROM `${raw}.dk_salaries_historical` h
    JOIN `${raw}.player_ids` i
      ON REGEXP_REPLACE(UPPER(h.display_name), r"[^A-Z ]", "") =
         REGEXP_REPLACE(UPPER(i.name), r"[^A-Z ]", "")
     AND i.gsis_id IS NOT NULL
    WHERE h.season NOT IN (SELECT DISTINCT season FROM own_log)
      AND h.salary > 0  -- RotoGuru encodes "no salary listed" as 0
    GROUP BY h.season, h.week, h.display_name, h.position
  )
  WHERE gsis_id IS NOT NULL
),
unioned AS (
  SELECT * FROM own_log
  UNION ALL
  SELECT * FROM historical
)
SELECT
  *,
  salary - LAG(salary) OVER (PARTITION BY gsis_id, season ORDER BY week)
    AS salary_delta_wow
FROM unioned;
