${inc:norm_fn}
-- Insight 1: do Millionaire winners skew chalk or contrarian? Per lineup,
-- the sum of FP projected ownership and of FP projection over its nine
-- players; averaged over the top 0.1% and top 1%, against the field median.
-- (Our book's row comes from insight_book_fp.sql.)
WITH m AS (${milly_contests}),
${inc:fp_latest},
${inc:field_ranked},
lineup AS (
  SELECT s.week, s.entry_id, s.top01, s.top1,
         SUM(fpo.fp_own) AS own_sum, SUM(fpp.fp_proj) AS proj_sum,
         COUNTIF(fpo.fp_own IS NULL) AS unmatched
  FROM slots s
  LEFT JOIN fpo ON fpo.week = s.week AND fpo.k = s.k AND fpo.team = s.team
  LEFT JOIN fpp ON fpp.week = s.week AND fpp.k = s.k AND fpp.team = s.team
  GROUP BY 1, 2, 3, 4
)
SELECT week, 'top 0.1%' AS grp, COUNT(*) AS n, AVG(own_sum) AS own_sum,
       AVG(proj_sum) AS proj_sum, AVG(unmatched) AS unmatched
FROM lineup WHERE top01 GROUP BY week
UNION ALL
SELECT week, 'top 1%', COUNT(*), AVG(own_sum), AVG(proj_sum), AVG(unmatched)
FROM lineup WHERE top1 GROUP BY week
UNION ALL
SELECT week, 'field median', COUNT(*), APPROX_QUANTILES(own_sum, 2)[OFFSET(1)],
       APPROX_QUANTILES(proj_sum, 2)[OFFSET(1)], AVG(unmatched)
FROM lineup GROUP BY week
ORDER BY week, grp
