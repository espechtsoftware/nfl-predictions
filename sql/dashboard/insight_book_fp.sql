${inc:norm_fn}
-- Insight 1 (our row): the book's mean lineup sum of FP projected ownership
-- and FP projection = sum over players of book_share x value (linearity).
WITH ${inc:fp_latest},
pe AS (
  SELECT * FROM `${dashboard}.pool_exposure`
  WHERE season = ${season}
  QUALIFY built_utc = MAX(built_utc) OVER (PARTITION BY week)
)
SELECT pe.week, 'our book' AS grp, NULL AS n,
       SUM(pe.book_share * fpo.fp_own) AS own_sum,
       SUM(pe.book_share * fpp.fp_proj) AS proj_sum,
       SUM(IF(fpo.fp_own IS NULL, pe.book_share, 0)) AS unmatched
FROM pe
LEFT JOIN fpo ON fpo.week = pe.week AND fpo.k = norm(pe.player)
LEFT JOIN fpp ON fpp.week = pe.week AND fpp.k = norm(pe.player)
GROUP BY 1
