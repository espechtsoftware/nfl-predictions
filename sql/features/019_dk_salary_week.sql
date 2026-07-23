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
  -- RotoGuru rows matched by normalized name + team; lower fidelity, only
  -- used for seasons before our own log starts.
  SELECT
    i.gsis_id, h.season, h.week,
    CAST(NULL AS INT64) AS dk_player_id,
    h.salary,
    CAST(NULL AS STRING) AS status,
    CAST(NULL AS FLOAT64) AS dk_ppg
  FROM `${raw}.dk_salaries_historical` h
  JOIN `${raw}.player_ids` i
    ON REGEXP_REPLACE(UPPER(h.display_name), r"[^A-Z ]", "") =
       REGEXP_REPLACE(UPPER(i.name), r"[^A-Z ]", "")
   AND UPPER(h.team_abbr) = UPPER(i.team)
  WHERE i.gsis_id IS NOT NULL
    AND h.season NOT IN (SELECT DISTINCT season FROM own_log)
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
