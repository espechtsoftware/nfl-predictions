-- The top of each Millionaire: up to ${top_n} lineups and at least the top
-- ${top_share} of the field, plus up to ${cash_rows} entries sitting exactly on
-- the cash line when payouts are known. `username` is the DraftKings entry
-- name without its "(n/m)" entry counter (operator 10-03: user names are kept
-- in BigQuery, the IAP dashboard and the graph). `dupes` counts identical
-- rosters across the whole field.
WITH m AS (${milly_contests}),
e AS (
  SELECT m.season, m.week, m.contest_id, x.entry_id, x.rank,
         x.points, x.payout, x.lineup_slots_json, x.players_key,
         REGEXP_REPLACE(TRIM(x.entry_name), r'\s*\(\d+/\d+\)$', '') AS username
  FROM `${raw}.contest_entries` x
  JOIN m ON x.season = m.season AND x.week = m.week AND x.contest_id = m.contest_id
  WHERE x.season = ${season} ${week_filter}
  QUALIFY ROW_NUMBER() OVER (PARTITION BY x.contest_id, x.entry_id
                             ORDER BY x.imported_at DESC) = 1
),
d AS (
  SELECT *,
         COUNT(*) OVER (PARTITION BY contest_id, players_key) AS dupes,
         ROW_NUMBER() OVER (PARTITION BY contest_id ORDER BY points DESC, rank, entry_id) AS pos,
         RANK() OVER (PARTITION BY contest_id ORDER BY points DESC) AS rk,
         COUNT(*) OVER (PARTITION BY contest_id) AS n,
         MIN(IF(payout > 0, points, NULL)) OVER (PARTITION BY contest_id) AS cash_line
  FROM e
),
c AS (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY contest_id, points = cash_line ORDER BY entry_id) AS cash_pos
  FROM d
)
SELECT
  season, week, contest_id,
  TO_HEX(SHA256(CONCAT(contest_id, ':', entry_id))) AS lineup_key,
  COALESCE(rank, pos) AS rank, points, lineup_slots_json, dupes, n AS n_entries, username,
  COALESCE(points = cash_line, FALSE) AS at_cash_line
FROM c
-- RANK at the cut: entries tied with the last one inside are inside too.
WHERE rk <= LEAST(${top_n}, GREATEST(10, CAST(CEIL(${top_share} * n) AS INT64)))
   OR (cash_line IS NOT NULL AND points = cash_line AND cash_pos <= ${cash_rows})
ORDER BY season, week, pos
