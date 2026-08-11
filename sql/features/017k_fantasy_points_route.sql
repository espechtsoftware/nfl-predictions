-- Licensed Fantasy Points Route Share, attached only from observations that
-- precede the target player-week. The raw table is append-only; unresolved
-- vendor identities are intentionally absent here and remain visible in the
-- ingest audit rather than being guessed into model rows.
CREATE OR REPLACE TABLE `${features}.player_week_fp_route` AS
WITH targets AS (
  SELECT DISTINCT gsis_id, CAST(season AS INT64) AS season,
         CAST(week AS INT64) AS week
  FROM `${features}.player_week_usage`
  WHERE gsis_id IS NOT NULL
),
history AS (
  SELECT gsis_id, CAST(season AS INT64) AS season,
         CAST(week AS INT64) AS week, route_share
  FROM `${raw}.fantasy_points_route_share`
  WHERE gsis_id IS NOT NULL AND route_share BETWEEN 0 AND 1
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY gsis_id, CAST(season AS INT64), CAST(week AS INT64)
    ORDER BY source_row
  ) = 1
),
ranked AS (
  SELECT
    t.gsis_id, t.season, t.week,
    h.season AS source_season, h.week AS source_week, h.route_share,
    ROW_NUMBER() OVER (
      PARTITION BY t.gsis_id, t.season, t.week
      ORDER BY h.season DESC, h.week DESC
    ) AS source_rank
  FROM targets t
  LEFT JOIN history h
    ON h.gsis_id = t.gsis_id
   AND h.season * 100 + h.week < t.season * 100 + t.week
)
SELECT
  gsis_id, season, week,
  MAX(IF(source_rank = 1, source_season, NULL)) AS fp_route_source_season,
  MAX(IF(source_rank = 1, source_week, NULL)) AS fp_route_source_week,
  COUNTIF(route_share IS NOT NULL) AS fp_route_prior_observations,
  MAX(IF(source_rank = 1, route_share, NULL)) AS fp_route_share_last,
  AVG(IF(source_rank <= 4, route_share, NULL)) AS fp_route_share_l4,
  MAX(IF(source_rank = 1, route_share, NULL))
    - MAX(IF(source_rank = 2, route_share, NULL)) AS fp_route_share_jump,
  IF(
    MAX(IF(source_rank = 1, source_season, NULL)) IS NULL,
    NULL,
    CAST(MAX(IF(source_rank = 1, source_season, NULL)) < season AS INT64)
  ) AS fp_route_cross_season,
  IF(
    MAX(IF(source_rank = 1, source_season, NULL)) IS NULL,
    'route-share-unavailable-fallback',
    'route-share-ready'
  ) AS fp_route_fallback
FROM ranked
GROUP BY gsis_id, season, week;
