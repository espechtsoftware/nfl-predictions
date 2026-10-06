-- Shared CTEs (an include: inc:field_ranked; needs m and fp_weeks):
-- every Millionaire entry in a week Fantasy Points covered, de-duplicated,
-- with its finishing position and the field size; the contest's slate keyed
-- by normalised name (names two players share are dropped, never merged:
-- scripts/o1_common.py's rule); and one row per slot, resolved to the slate's
-- DraftKings id and team (NULL when unresolved).
e AS (
  SELECT m.season, m.week, m.contest_id, x.entry_id, x.points, x.lineup_slots_json
  FROM `${raw}.contest_entries` x
  JOIN m ON x.season = m.season AND x.week = m.week AND x.contest_id = m.contest_id
  WHERE x.season = ${season} AND x.week IN (SELECT week FROM fp_weeks)
  QUALIFY ROW_NUMBER() OVER (PARTITION BY x.contest_id, x.entry_id
                             ORDER BY x.imported_at DESC) = 1
),
r AS (
  SELECT *,
         -- RANK, not ROW_NUMBER: entries tied at a cut are all inside it.
         RANK() OVER (PARTITION BY contest_id ORDER BY points DESC) AS pos,
         COUNT(*) OVER (PARTITION BY contest_id) AS n
  FROM e
),
slate AS (
  SELECT contest_id, k, ANY_VALUE(team) AS team, ANY_VALUE(dk_player_id) AS dk_player_id,
         ANY_VALUE(position) AS position
  FROM (
    SELECT m.contest_id, norm(d.display_name) AS k, team_code(d.team_abbr) AS team,
           d.dk_player_id, SPLIT(d.position, '/')[OFFSET(0)] AS position
    FROM `${raw}.dk_salaries` d
    JOIN m ON d.draft_group_id = m.draft_group_id
    WHERE m.season = ${season} AND m.week IN (SELECT week FROM fp_weeks)
      AND d.slate_type = 'classic' AND (m.start_time IS NULL OR d.pulled_at < m.start_time)
    QUALIFY d.pulled_at = MAX(d.pulled_at) OVER (PARTITION BY m.contest_id)
  ) AS s
  GROUP BY 1, 2
  HAVING COUNT(DISTINCT s.dk_player_id) = 1   -- a shared normalised name is dropped, never merged
),
raw_slots AS (
  SELECT r.week, r.contest_id, r.entry_id, r.pos, r.n,
         r.pos <= GREATEST(1, CAST(CEIL(0.001 * r.n) AS INT64)) AS top01,
         r.pos <= GREATEST(1, CAST(CEIL(0.01 * r.n) AS INT64)) AS top1,
         JSON_VALUE(it, '$.slot') AS slot, JSON_VALUE(it, '$.player') AS player
  FROM r, UNNEST(JSON_QUERY_ARRAY(r.lineup_slots_json)) it
),
slots AS (
  SELECT s.*, norm(s.player) AS k, sl.team, sl.dk_player_id, sl.position
  FROM raw_slots s
  LEFT JOIN slate sl ON sl.contest_id = s.contest_id AND sl.k = norm(s.player)
)
