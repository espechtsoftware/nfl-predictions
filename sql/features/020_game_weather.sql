-- Latest weather snapshot per game, falling back to schedule temp/wind for
-- historical games (nflverse schedules carry both for outdoor games).
-- 2026-09-21 (Week-2 end-to-end audit, ING-002): the ingest has stored the
-- forecast precipitation probability (percent, 0-100) since the weather job
-- started, and this table dropped it; MIN-CHI carried 51% before the Week-2
-- lock. It is carried through here, with the snapshot time, as a pass-through
-- column for the point-in-time weather shadow. It is NOT a model feature
-- (models/featureset.py is unchanged) until that shadow supports it. Schedules
-- carry no precipitation, so historical games without a snapshot stay NULL.
--
-- O-22 (d) (2026-10-05): "latest" had no time bound, so a completed game's
-- row carried a snapshot pulled after lock (up to and during the game) that
-- serving never sees. Only snapshots pulled at/before the earlier of the
-- game's kickoff and its week's Sunday-main lock (018's lock) count now; a
-- game with none falls back to the schedule, as historical games do.
CREATE OR REPLACE TABLE `${features}.game_weather` AS
WITH slate_locks AS (
  -- The common Sunday-main lock, as in 018 (schedule times are Eastern).
  SELECT season, week,
    MIN(TIMESTAMP(
      DATETIME(PARSE_DATE('%Y-%m-%d', gameday),
               SAFE.PARSE_TIME('%H:%M', gametime)),
      'America/New_York'
    )) AS slate_lock_at
  FROM `${raw}.schedules`
  WHERE game_type = 'REG' AND weekday = 'Sunday'
    AND SAFE.PARSE_TIME('%H:%M', gametime) >= TIME '13:00:00'
    AND SAFE.PARSE_TIME('%H:%M', gametime) < TIME '19:00:00'
  GROUP BY season, week
), game_lock AS (
  SELECT g.game_id, LEAST(g.kickoff_at, COALESCE(l.slate_lock_at, g.kickoff_at)) AS lock_at
  FROM (
    SELECT game_id, season, week,
           TIMESTAMP(DATETIME(PARSE_DATE('%Y-%m-%d', gameday),
                              SAFE.PARSE_TIME('%H:%M', gametime)),
                     'America/New_York') AS kickoff_at
    FROM `${raw}.schedules`) g
  LEFT JOIN slate_locks l ON l.season = g.season AND l.week = g.week
), latest AS (
  SELECT w.game_id,
         ARRAY_AGG(w.temp_f ORDER BY w.pulled_at DESC LIMIT 1)[OFFSET(0)] AS temp_f,
         ARRAY_AGG(w.wind_mph ORDER BY w.pulled_at DESC LIMIT 1)[OFFSET(0)] AS wind_mph,
         ARRAY_AGG(w.is_dome ORDER BY w.pulled_at DESC LIMIT 1)[OFFSET(0)] AS is_dome,
         ARRAY_AGG(w.precip_prob ORDER BY w.pulled_at DESC LIMIT 1)[OFFSET(0)] AS precip_prob,
         MAX(w.pulled_at) AS weather_pulled_at
  FROM `${raw}.weather` w
  JOIN game_lock g USING (game_id)
  WHERE w.pulled_at <= g.lock_at
  GROUP BY w.game_id
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
