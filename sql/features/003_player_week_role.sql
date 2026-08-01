-- Role context per (player, season, week): depth chart rank at the player's
-- position, rookie flag, and draft capital. These are the inputs
-- models/coldstart.py's ROLE_PRIORS were designed around — a cold-start
-- backup should be priced by the role he steps into, not a league default.
--
-- Point-in-time: a depth chart for week W is published before W's games
-- (same discipline as the injury report in 018), so same-week rows are
-- legitimately knowable.
--
-- nflverse changed the depth charts format in 2025 (see the data deficiency
-- log), so ingest lands two raw tables and this file normalizes both:
--   ${raw}.depth_charts           2001-2024: season/week rows, depth_team rank
--   ${raw}.depth_charts_snapshots 2025-    : dated snapshots (dt), pos_rank
-- Snapshot rows are mapped to weeks point-in-time: the latest snapshot dated
-- on/before the team's gameday serves that week.
--
-- WR caveat: the legacy format lists alignment starters with equal
-- depth_team (e.g. two WR "1" rows), so ROW_NUMBER splits ties
-- deterministically by jersey number — ranks 1-3 all mean "starter tier".
-- The 2025 snapshot format publishes a true global pos_rank per position.
CREATE OR REPLACE TABLE `${features}.player_week_role` AS
WITH team_games AS (
  -- (season, week, team, gameday) for every scheduled game, both sides
  SELECT CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
         home_team AS team, gameday
  FROM `${raw}.schedules`
  UNION ALL
  SELECT CAST(season AS INT64), CAST(week AS INT64), away_team, gameday
  FROM `${raw}.schedules`
),
upcoming AS (
  -- Each team's next unplayed game: where live inference points
  SELECT season, team, MIN(week) AS week
  FROM team_games
  WHERE gameday >= CAST(CURRENT_DATE() AS STRING)
  GROUP BY season, team
),
roster AS (
  SELECT
    gsis_id,
    CAST(season AS INT64) AS season,
    CAST(week AS INT64) AS week,
    team,
    position,
    SAFE_CAST(rookie_year AS INT64) = CAST(season AS INT64) AS is_rookie,
    SAFE_CAST(entry_year AS INT64) AS entry_year,
    SAFE_CAST(draft_number AS INT64) AS draft_number
  FROM `${raw}.rosters_weekly`
  WHERE gsis_id IS NOT NULL AND position IN ('QB', 'RB', 'WR', 'TE')
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY gsis_id, CAST(season AS INT64), CAST(week AS INT64)
    ORDER BY team
  ) = 1
),
latest_roster AS (
  SELECT * FROM roster
  QUALIFY ROW_NUMBER() OVER (PARTITION BY gsis_id, season ORDER BY week DESC) = 1
),
-- Roster rows for the upcoming week, synthesized from each player's latest
-- known roster spot when nflverse hasn't published that week yet.
base AS (
  SELECT r.gsis_id, r.season, r.week, r.team, r.position,
         r.is_rookie, r.entry_year, r.draft_number
  FROM roster r
  UNION ALL
  SELECT lr.gsis_id, up.season, up.week, up.team, lr.position,
         lr.is_rookie, lr.entry_year, lr.draft_number
  FROM upcoming up
  JOIN latest_roster lr ON lr.season = up.season AND lr.team = up.team
  WHERE NOT EXISTS (
    SELECT 1 FROM roster r2
    WHERE r2.gsis_id = lr.gsis_id AND r2.season = up.season AND r2.week = up.week
  )
),
-- Legacy format: one rank per (team, week, position), deterministic tiebreak
legacy_rank AS (
  SELECT
    gsis_id,
    CAST(season AS INT64) AS season,
    SAFE_CAST(week AS INT64) AS week,
    club_code AS team,
    position,
    ROW_NUMBER() OVER (
      PARTITION BY club_code, CAST(season AS INT64), SAFE_CAST(week AS INT64), position
      ORDER BY SAFE_CAST(depth_team AS INT64), SAFE_CAST(jersey_number AS INT64), gsis_id
    ) AS depth_rank
  FROM `${raw}.depth_charts`
  WHERE gsis_id IS NOT NULL
    AND formation = 'Offense'
    AND position IN ('QB', 'RB', 'WR', 'TE')
    AND week IS NOT NULL
),
-- Snapshot format: pick the latest snapshot on/before each game day
snap AS (
  SELECT team, TIMESTAMP(dt) AS ts, gsis_id, pos_abb AS position, pos_rank
  FROM `${raw}.depth_charts_snapshots`
  WHERE gsis_id IS NOT NULL AND pos_abb IN ('QB', 'RB', 'WR', 'TE')
),
snap_ts_per_game AS (
  SELECT g.season, g.week, g.team, MAX(s.ts) AS ts
  FROM team_games g
  JOIN snap s ON s.team = g.team AND DATE(s.ts) <= DATE(g.gameday)
  GROUP BY g.season, g.week, g.team
),
snapshot_rank AS (
  SELECT p.season, p.week, p.team, s.gsis_id, s.position,
         CAST(s.pos_rank AS INT64) AS depth_rank
  FROM snap_ts_per_game p
  JOIN snap s ON s.team = p.team AND s.ts = p.ts
),
ranks AS (
  SELECT * FROM legacy_rank
  UNION ALL
  SELECT gsis_id, season, week, team, position, depth_rank FROM snapshot_rank
),
deduped AS (
SELECT
  b.gsis_id, b.season, b.week, b.team, b.position,
  r.depth_rank,
  COALESCE(b.is_rookie, FALSE) AS is_rookie,
  -- draft_picks.gsis_id is unset/non-GSIS for recent classes (see the
  -- deficiency log), so fall back to matching the roster's overall pick
  -- number within the player's entry-year draft.
  COALESCE(dg.round, dp.round) AS draft_round,
  COALESCE(b.week = up.week, FALSE) AS is_upcoming
FROM base b
LEFT JOIN ranks r
  ON r.gsis_id = b.gsis_id AND r.season = b.season AND r.week = b.week
LEFT JOIN (
  SELECT gsis_id, CAST(round AS INT64) AS round
  FROM `${raw}.draft_picks`
  WHERE gsis_id IS NOT NULL
  QUALIFY ROW_NUMBER() OVER (PARTITION BY gsis_id ORDER BY season DESC) = 1
) dg ON dg.gsis_id = b.gsis_id
LEFT JOIN (
  SELECT CAST(season AS INT64) AS draft_season, CAST(pick AS INT64) AS pick,
         CAST(round AS INT64) AS round
  FROM `${raw}.draft_picks`
) dp ON dp.draft_season = b.entry_year AND dp.pick = b.draft_number
LEFT JOIN upcoming up ON up.season = b.season AND up.team = b.team
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY b.gsis_id, b.season, b.week
  ORDER BY r.depth_rank NULLS LAST
) = 1
)
SELECT
  *,
  -- Depth-rank transition (Addendum 24): winning Milly punts are often
  -- NEWLY-promoted min-priced starters (rank 2 -> 1 in recent weeks, e.g.
  -- Gadsden wk 7) that static depth_rank can't distinguish from long-time
  -- starters. Positive = promoted vs the player's previous listed week.
  -- Both ranks are as-of-week-W roster knowledge (same discipline as
  -- depth_rank itself, see header), so no PRECEDING window is needed;
  -- computed AFTER dedup so LAG sees one row per (player, week).
  LAG(depth_rank) OVER (
    PARTITION BY gsis_id, season ORDER BY week
  ) - depth_rank AS depth_rank_delta
FROM deduped;
