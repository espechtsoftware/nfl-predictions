${inc:norm_fn}
-- Insight 3: QB + pass-catcher stacks among the top 1%. Per week and pair:
-- how many top-1% lineups carried it, its share, the pair's combined FP
-- projected ownership, and the game it came from.
WITH m AS (${milly_contests}),
${inc:fp_latest},
${inc:field_ranked},
t AS (
  SELECT s.week, s.contest_id, s.entry_id, s.slot, s.player, s.k, s.team, s.position
  FROM slots s
  WHERE s.top1 AND s.team IS NOT NULL
),
n1 AS (SELECT contest_id, COUNT(DISTINCT entry_id) AS n_top1 FROM t GROUP BY 1),
pairs AS (
  SELECT q.week, q.contest_id, q.player AS qb, c.player AS catcher, q.k AS qk, c.k AS ck, q.team,
         COUNT(DISTINCT q.entry_id) AS lineups
  FROM t q JOIN t c
    ON c.entry_id = q.entry_id AND c.contest_id = q.contest_id AND c.team = q.team
   AND c.position IN ('WR', 'TE')
  WHERE q.slot = 'QB'
  GROUP BY 1, 2, 3, 4, 5, 6, 7
)
SELECT p.week, p.qb, p.catcher, p.team, p.lineups,
       100.0 * p.lineups / n1.n_top1 AS share_top1,
       IFNULL(oq.fp_own, 0) + IFNULL(oc.fp_own, 0) AS pair_fp_own
FROM pairs p
JOIN n1 USING (contest_id)
LEFT JOIN fpo oq ON oq.week = p.week AND oq.k = p.qk AND oq.team = p.team
LEFT JOIN fpo oc ON oc.week = p.week AND oc.k = p.ck AND oc.team = p.team
QUALIFY ROW_NUMBER() OVER (PARTITION BY p.week ORDER BY p.lineups DESC) <= 15
ORDER BY p.week, p.lineups DESC
