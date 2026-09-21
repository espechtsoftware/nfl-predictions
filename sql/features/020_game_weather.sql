-- Latest weather snapshot per game, falling back to schedule temp/wind for
-- historical games (nflverse schedules carry both for outdoor games).
-- 2026-09-21 (Week-2 end-to-end audit, ING-002): the ingest has stored the
-- forecast precipitation probability (percent, 0-100) since the weather job
-- started, and this table dropped it; MIN-CHI carried 51% before the Week-2
-- lock. It is carried through here, with the snapshot time, as a pass-through
-- column for the point-in-time weather shadow. It is NOT a model feature
-- (models/featureset.py is unchanged) until that shadow supports it. Schedules
-- carry no precipitation, so historical games without a snapshot stay NULL.
CREATE OR REPLACE TABLE `${features}.game_weather` AS
WITH latest AS (
  SELECT game_id,
         ARRAY_AGG(temp_f ORDER BY pulled_at DESC LIMIT 1)[OFFSET(0)] AS temp_f,
         ARRAY_AGG(wind_mph ORDER BY pulled_at DESC LIMIT 1)[OFFSET(0)] AS wind_mph,
         ARRAY_AGG(is_dome ORDER BY pulled_at DESC LIMIT 1)[OFFSET(0)] AS is_dome,
         ARRAY_AGG(precip_prob ORDER BY pulled_at DESC LIMIT 1)[OFFSET(0)] AS precip_prob,
         MAX(pulled_at) AS weather_pulled_at
  FROM `${raw}.weather`
  GROUP BY game_id
)
SELECT
  s.game_id,
  COALESCE(l.temp_f, CAST(s.temp AS FLOAT64))  AS temp_f,
  COALESCE(l.wind_mph, CAST(s.wind AS FLOAT64)) AS wind_mph,
  COALESCE(l.is_dome, s.roof IN ('dome', 'closed')) AS is_dome,
  CAST(l.precip_prob AS FLOAT64) AS precip_prob,
  l.weather_pulled_at
FROM `${raw}.schedules` s
LEFT JOIN latest l USING (game_id);
