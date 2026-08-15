-- Injury designation and practice-participation trend, point-in-time. A
-- same-week row is knowable only when either its source modification time or
-- our append-only collector observation time is at/before the common slate
-- lock. Games missed uses strictly-prior weeks.
CREATE OR REPLACE TABLE `${features}.player_week_injury` AS
WITH slate_locks AS (
  -- Historical training and replay use the common Sunday-main lock, not a
  -- later inactive announcement for a 4pm game. nflverse schedule times are
  -- Eastern; the earliest Sunday-main kickoff is the DraftKings lock.
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
), source_modified AS (
  SELECT
    i.gsis_id,
    -- nflverse ships these as FLOAT in the injuries dataset (null-driven
    -- upcast); INT64 keeps join keys consistent and windows partitionable.
    CAST(i.season AS INT64) AS season,
    CAST(i.week AS INT64) AS week,
    i.report_status AS injury_status,
    -- Encode Wed/Thu/Fri practice as 0=DNP, 1=Limited, 2=Full and average
    (SELECT AVG(v) FROM UNNEST([
       CASE i.practice_status
         WHEN 'Did Not Participate In Practice' THEN 0.0
         WHEN 'Limited Participation in Practice' THEN 1.0
         WHEN 'Full Participation in Practice' THEN 2.0
       END
    ]) v WHERE v IS NOT NULL) AS practice_level,
    i.date_modified AS injury_source_modified_at,
    CAST(NULL AS TIMESTAMP) AS injury_snapshot_pulled_at,
    i.date_modified AS injury_information_at,
    'source_modified' AS injury_source_kind,
    i.team,
    i.practice_status,
    l.slate_lock_at
  FROM `${raw}.injuries` i
  JOIN slate_locks l
    ON l.season = CAST(i.season AS INT64)
   AND l.week = CAST(i.week AS INT64)
  WHERE i.gsis_id IS NOT NULL AND i.date_modified <= l.slate_lock_at
), collector_snapshot AS (
  SELECT
    i.gsis_id,
    CAST(i.season AS INT64) AS season,
    CAST(i.week AS INT64) AS week,
    i.report_status AS injury_status,
    (SELECT AVG(v) FROM UNNEST([
       CASE i.practice_status
         WHEN 'Did Not Participate In Practice' THEN 0.0
         WHEN 'Limited Participation in Practice' THEN 1.0
         WHEN 'Full Participation in Practice' THEN 2.0
       END
    ]) v WHERE v IS NOT NULL) AS practice_level,
    i.date_modified AS injury_source_modified_at,
    i.pulled_at AS injury_snapshot_pulled_at,
    i.pulled_at AS injury_information_at,
    'collector_snapshot' AS injury_source_kind,
    i.team,
    i.practice_status,
    l.slate_lock_at
  FROM `${raw}.injury_snapshots` i
  JOIN slate_locks l
    ON l.season = CAST(i.season AS INT64)
   AND l.week = CAST(i.week AS INT64)
  WHERE i.gsis_id IS NOT NULL
    AND i.pulled_at <= l.slate_lock_at
    -- A malformed source timestamp later than the observation itself cannot
    -- be smuggled in through an otherwise-valid collector timestamp.
    AND (i.date_modified IS NULL OR i.date_modified <= i.pulled_at)
), candidates AS (
  SELECT * FROM source_modified
  UNION ALL
  SELECT * FROM collector_snapshot
), inj AS (
  SELECT *
  FROM candidates
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY gsis_id, season, week
    ORDER BY injury_information_at DESC,
             IF(injury_source_kind = 'collector_snapshot', 0, 1),
             team DESC, practice_status DESC
  ) = 1
),
missed AS (
  -- Weeks on the injury report as Out, in the prior 4 weeks
  SELECT
    i.gsis_id, i.season, i.week,
    COUNTIF(i2.injury_status = 'Out') AS games_missed_l4
  FROM inj i
  LEFT JOIN inj i2
    ON i2.gsis_id = i.gsis_id AND i2.season = i.season
   AND i2.week BETWEEN i.week - 4 AND i.week - 1
  GROUP BY 1, 2, 3
)
SELECT
  i.gsis_id, i.season, i.week,
  i.injury_status,
  i.practice_level,
  i.practice_level - LAG(i.practice_level) OVER (
    PARTITION BY i.gsis_id, i.season ORDER BY i.week
  ) AS practice_participation_trend,
  COALESCE(m.games_missed_l4, 0) AS games_missed_l4,
  i.injury_source_modified_at,
  i.injury_snapshot_pulled_at,
  i.injury_information_at,
  i.injury_source_kind,
  i.slate_lock_at
FROM inj i
LEFT JOIN missed m USING (gsis_id, season, week);

-- Opportunity vacated by teammates ruled Out for week W: the sum of the
-- trailing-4-week target and carry shares of every player on the team's
-- report as Out that week. Point-in-time on both sides — the report is
-- published before W's games and the shares are strictly-prior windows —
-- so the models can learn next-man-up bumps instead of relying only on a
-- bolt-on inference adjustment. Consumers subtract the player's own share
-- (an Out player shouldn't count his own vacancy as opportunity).
--
-- The Out player's share comes from his latest usage row AT OR BEFORE the
-- report week, not a same-week equijoin: a player who sits has no usage
-- row that week, so the naive join would zero this feature across all of
-- training history while the upcoming week's synthetic rows (014) kept it
-- populated live — a train/serve skew that would teach the models to
-- ignore the signal.
CREATE OR REPLACE TABLE `${features}.team_week_vacated` AS
WITH outs AS (
  SELECT gsis_id, season, week
  FROM `${features}.player_week_injury`
  WHERE injury_status = 'Out'
),
asof AS (
  SELECT
    o.gsis_id, o.season, o.week,
    u.team, u.target_share_l4, u.carry_share_l4
  FROM outs o
  JOIN `${features}.player_week_usage` u
    ON u.gsis_id = o.gsis_id AND u.season = o.season AND u.week <= o.week
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY o.gsis_id, o.season, o.week ORDER BY u.week DESC
  ) = 1
)
SELECT
  team, season, week,
  SUM(COALESCE(target_share_l4, 0)) AS vacated_target_share,
  SUM(COALESCE(carry_share_l4, 0))  AS vacated_carry_share
FROM asof
GROUP BY team, season, week;
