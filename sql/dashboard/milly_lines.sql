-- Per Millionaire: field size, winning score, the top-0.1% and top-1% lines
-- (the score at that rank), and the cash line when the import carries
-- payouts (2026 standings imports leave payout NULL, so it is usually NULL).
WITH m AS (${milly_contests}),
e AS (
  SELECT m.season, m.week, m.contest_id, m.contest_name, x.entry_id, x.points, x.payout
  FROM `${raw}.contest_entries` x
  JOIN m ON x.season = m.season AND x.week = m.week AND x.contest_id = m.contest_id
  WHERE x.season = ${season}
  QUALIFY ROW_NUMBER() OVER (PARTITION BY x.contest_id, x.entry_id
                             ORDER BY x.imported_at DESC) = 1
),
r AS (
  SELECT *,
         -- RANK, not ROW_NUMBER: the line is the score at that rank, ties included.
         RANK() OVER (PARTITION BY contest_id ORDER BY points DESC) AS pos,
         COUNT(*) OVER (PARTITION BY contest_id) AS n
  FROM e
)
SELECT
  season, week, contest_id, ANY_VALUE(contest_name) AS contest_name,
  ANY_VALUE(n) AS n_entries,
  MAX(points) AS winning_score,
  MIN(IF(pos <= GREATEST(1, CAST(CEIL(0.001 * n) AS INT64)), points, NULL)) AS top_01pct_line,
  MIN(IF(pos <= GREATEST(1, CAST(CEIL(0.01 * n) AS INT64)), points, NULL)) AS top_1pct_line,
  MIN(IF(payout > 0, points, NULL)) AS cash_line,
  APPROX_QUANTILES(points, 2)[OFFSET(1)] AS median_score
FROM r
GROUP BY 1, 2, 3
ORDER BY season, week
