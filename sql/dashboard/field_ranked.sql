-- Shared CTEs (an include: inc:field_ranked; needs m and fp_weeks):
-- every Millionaire entry in a week Fantasy Points covered, de-duplicated,
-- with its finishing position and the field size; and one row per slot.
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
         ROW_NUMBER() OVER (PARTITION BY contest_id ORDER BY points DESC, entry_id) AS pos,
         COUNT(*) OVER (PARTITION BY contest_id) AS n
  FROM e
),
slots AS (
  SELECT r.week, r.contest_id, r.entry_id, r.pos, r.n,
         r.pos <= GREATEST(1, CAST(CEIL(0.001 * r.n) AS INT64)) AS top01,
         r.pos <= GREATEST(1, CAST(CEIL(0.01 * r.n) AS INT64)) AS top1,
         JSON_VALUE(it, '$.slot') AS slot, JSON_VALUE(it, '$.player') AS player
  FROM r, UNNEST(JSON_QUERY_ARRAY(r.lineup_slots_json)) it
)
