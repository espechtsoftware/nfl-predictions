${inc:norm_fn}
-- Insight 6: our book against the winners, joined on the DraftKings player
-- id (standings names resolved through the slate). Per player: our book share, the
-- share of top-0.1% lineups carrying him, the field's realized ownership and
-- FP's projection; divergence = book - top 0.1%.
WITH m AS (${milly_contests}),
${inc:fp_latest},
${inc:field_ranked},
n01 AS (SELECT contest_id, COUNT(DISTINCT entry_id) AS n FROM slots WHERE top01 GROUP BY 1),
own AS (
  SELECT s.week, s.contest_id, s.player, s.k, s.team, s.dk_player_id,
         100.0 * COUNT(DISTINCT s.entry_id) / ANY_VALUE(s.n) AS field_own,
         100.0 * COUNT(DISTINCT IF(s.top01, s.entry_id, NULL)) / ANY_VALUE(n01.n) AS top01_rate
  FROM slots s JOIN n01 USING (contest_id)
  WHERE s.dk_player_id IS NOT NULL
  GROUP BY 1, 2, 3, 4, 5, 6
),
pe AS (
  SELECT * FROM `${dashboard}.pool_exposure`
  WHERE season = ${season}
  QUALIFY published_utc = MAX(published_utc) OVER (PARTITION BY week)
)
SELECT COALESCE(own.week, pe.week) AS week, COALESCE(pe.player, own.player) AS player,
       pe.position, 100.0 * IFNULL(pe.book_share, 0) AS book_pct,
       IFNULL(own.top01_rate, 0) AS top01_pct, IFNULL(own.field_own, 0) AS field_pct,
       fpo.fp_own,
       100.0 * IFNULL(pe.book_share, 0) - IFNULL(own.top01_rate, 0) AS divergence
FROM own
FULL OUTER JOIN pe ON pe.week = own.week AND pe.dk_player_id = own.dk_player_id
LEFT JOIN fpo ON fpo.week = COALESCE(own.week, pe.week)
             AND fpo.k = COALESCE(own.k, norm(pe.player))
             AND fpo.team = COALESCE(own.team, team_code(pe.team))
WHERE COALESCE(own.week, pe.week) IN (SELECT DISTINCT week FROM r)   -- weeks with standings and FP
  AND (IFNULL(pe.book_share, 0) > 0 OR IFNULL(own.top01_rate, 0) >= 10)
ORDER BY week, ABS(100.0 * IFNULL(pe.book_share, 0) - IFNULL(own.top01_rate, 0)) DESC
