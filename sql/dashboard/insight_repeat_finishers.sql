-- Insight 4: repeat top finishers by DraftKings user name, season-wide over
-- the main-slate Millionaires (operator 2026-10-03/04: user names are kept in
-- BigQuery derivations and shown in the IAP dashboard). The user name is the
-- entry name without its "(k/n)" entry counter. Entries are de-duplicated by
-- the newest import; finishing position is RANK over the whole field (entries
-- tied at a cut are all inside it), so blank names still count toward the
-- field and the cuts. Per user: entries, weeks entered, top-1% lineups and
-- weeks, top-0.1% lineups, best rank, top-1% rate (% of the user's entries),
-- and the QB used most often in the user's top-1% lineups.
WITH m AS (${milly_contests}),
e AS (
  SELECT m.season, m.week, m.contest_id, x.entry_id, x.points, x.lineup_slots_json,
         REGEXP_REPLACE(TRIM(x.entry_name), r'\s*\(\d+/\d+\)$', '') AS username
  FROM `${raw}.contest_entries` x
  JOIN m ON x.season = m.season AND x.week = m.week AND x.contest_id = m.contest_id
  WHERE x.season = ${season}
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
f AS (
  SELECT *,
         pos <= GREATEST(1, CAST(CEIL(0.01 * n) AS INT64)) AS top1,
         pos <= GREATEST(1, CAST(CEIL(0.001 * n) AS INT64)) AS top01
  FROM r
  WHERE username IS NOT NULL AND username != ''
),
u AS (
  SELECT username,
         COUNT(*) AS entries,
         COUNT(DISTINCT week) AS weeks,
         COUNTIF(top1) AS top1_lineups,
         COUNT(DISTINCT IF(top1, week, NULL)) AS top1_weeks,
         COUNTIF(top01) AS top01_lineups,
         MIN(pos) AS best_rank,
         100.0 * COUNTIF(top1) / COUNT(*) AS top1_rate
  FROM f
  GROUP BY 1
),
qb_n AS (
  SELECT f.username, JSON_VALUE(it, '$.player') AS top_qb, COUNT(*) AS top_qb_lineups
  FROM f, UNNEST(JSON_QUERY_ARRAY(f.lineup_slots_json)) it
  WHERE f.top1 AND JSON_VALUE(it, '$.slot') = 'QB'
  GROUP BY 1, 2
),
qb AS (
  SELECT * FROM qb_n
  QUALIFY ROW_NUMBER() OVER (PARTITION BY username ORDER BY top_qb_lineups DESC, top_qb) = 1
)
SELECT u.username, u.entries, u.weeks, u.top1_lineups, u.top1_weeks, u.top01_lineups,
       u.best_rank, u.top1_rate, qb.top_qb, qb.top_qb_lineups
FROM u
LEFT JOIN qb USING (username)
WHERE u.top1_lineups > 0
ORDER BY u.top1_weeks DESC, u.top1_lineups DESC, u.best_rank, u.username
LIMIT 50
