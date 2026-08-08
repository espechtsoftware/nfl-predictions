-- Referee-crew tendency (2026-08-01): flags extend drives (defensive
-- holding / DPI are automatic first downs), which adds plays upstream of
-- every player's volume. Crew spreads are large (2024: ~12.8 to ~17.8
-- flags/game between crews) and consistent season to season.
--
-- Point-in-time: the tendency for game G uses the referee's STRICTLY
-- PRIOR games (20-game window, min 5). The crew assignment itself is
-- public midweek, so knowing WHO refs game G is legitimate week-W
-- knowledge; nflverse `officials` records it per game (2015+, keyed by
-- the old numeric game_id -> join through pbp.old_game_id).
--
-- Live caveat: nflverse publishes officials post-game, so inference rows
-- for the upcoming week get NULL (build_X NaN-fills) until a midweek
-- assignment source is scraped -- this feature earns its keep in
-- training/replay first.
CREATE OR REPLACE TABLE `${features}.referee_game_tendency` AS
WITH game_pen AS (
  SELECT game_id, ANY_VALUE(old_game_id) AS old_game_id,
         ANY_VALUE(season) AS season, ANY_VALUE(week) AS week,
         SUM(CAST(penalty AS INT64)) AS flags,
         SUM(COALESCE(penalty_yards, 0)) AS pen_yards
  FROM `${raw}.pbp`
  GROUP BY game_id
),
ref AS (
  SELECT CAST(game_id AS STRING) AS old_game_id, official_name AS referee
  FROM `${raw}.officials`
  WHERE position = 'Referee'
  -- deterministic tie-break (variance review 2026-08-04): no ORDER
  -- BY = arbitrary referee row per game per rebuild
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY game_id ORDER BY official_name, official_id
  ) = 1
)
SELECT
  g.game_id, g.season, g.week, r.referee,
  AVG(g.flags) OVER w AS ref_flags_prior,
  AVG(g.pen_yards) OVER w AS ref_pen_yards_prior,
  COUNT(*) OVER w AS ref_prior_games
FROM game_pen g
JOIN ref r ON r.old_game_id = CAST(g.old_game_id AS STRING)
WINDOW w AS (
  PARTITION BY r.referee ORDER BY g.season, g.week
  ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
);
