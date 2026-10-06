${inc:norm_fn}
-- Insight 2: leverage that paid, and chalk that busted. Per player-week:
-- FP projected ownership, realized Millionaire ownership (lineup counts),
-- the player's rate in top-1% lineups, DK points.
--   leverage that paid: realized <= 0.6 x FP and FP - realized >= 3, and the
--                       top-1% rate >= 1.5 x realized;
--   chalk that busted:  FP >= 15 and the top-1% rate <= 0.5 x realized.
WITH m AS (${milly_contests}),
${inc:fp_latest},
${inc:field_ranked},
tops AS (SELECT contest_id, COUNT(DISTINCT entry_id) AS n_top1 FROM slots WHERE top1 GROUP BY 1),
own AS (
  SELECT s.week, s.contest_id, s.player, s.k, s.team,
         100.0 * COUNT(DISTINCT s.entry_id) / ANY_VALUE(s.n) AS realized,
         100.0 * COUNT(DISTINCT IF(s.top1, s.entry_id, NULL)) / ANY_VALUE(t.n_top1) AS top1_rate
  FROM slots s JOIN tops t USING (contest_id)
  GROUP BY 1, 2, 3, 4, 5
),
pts AS (
  SELECT contest_id, display_name, MAX(fpts) AS fpts
  FROM `${raw}.contest_ownership` WHERE season = ${season} GROUP BY 1, 2
),
j AS (
  SELECT own.week, own.player, fpo.fp_own, own.realized, own.top1_rate, pts.fpts
  FROM own
  JOIN fpo ON fpo.week = own.week AND fpo.k = own.k AND fpo.team = own.team
  LEFT JOIN pts ON pts.contest_id = own.contest_id AND pts.display_name = own.player
)
SELECT *,
  CASE
    WHEN realized <= 0.6 * fp_own AND fp_own - realized >= 3 AND top1_rate >= 1.5 * realized
      THEN 'leverage that paid'
    WHEN fp_own >= 15 AND top1_rate <= 0.5 * realized THEN 'chalk that busted'
  END AS category
FROM j
WHERE (realized <= 0.6 * fp_own AND fp_own - realized >= 3 AND top1_rate >= 1.5 * realized)
   OR (fp_own >= 15 AND top1_rate <= 0.5 * realized)
ORDER BY week, category, ABS(fp_own - realized) DESC
