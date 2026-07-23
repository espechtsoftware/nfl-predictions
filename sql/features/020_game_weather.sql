-- Latest weather snapshot per game, falling back to schedule temp/wind for
-- historical games (nflverse schedules carry both for outdoor games).
CREATE OR REPLACE TABLE `${features}.game_weather` AS
WITH latest AS (
  SELECT game_id,
         ARRAY_AGG(temp_f ORDER BY pulled_at DESC LIMIT 1)[OFFSET(0)] AS temp_f,
         ARRAY_AGG(wind_mph ORDER BY pulled_at DESC LIMIT 1)[OFFSET(0)] AS wind_mph,
         ARRAY_AGG(is_dome ORDER BY pulled_at DESC LIMIT 1)[OFFSET(0)] AS is_dome
  FROM `${raw}.weather`
  GROUP BY game_id
)
SELECT
  s.game_id,
  COALESCE(l.temp_f, CAST(s.temp AS FLOAT64))  AS temp_f,
  COALESCE(l.wind_mph, CAST(s.wind AS FLOAT64)) AS wind_mph,
  COALESCE(l.is_dome, s.roof IN ('dome', 'closed')) AS is_dome
FROM `${raw}.schedules` s
LEFT JOIN latest l USING (game_id);
