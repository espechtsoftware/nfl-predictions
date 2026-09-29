-- F1/F2: per-user per-week finish + ownership stats, three 2026 Millionaires (all inputs realized/post-lock)
WITH own AS (
  SELECT contest_id, display_name, SUM(pct_drafted) AS own
  FROM nfl_raw.contest_ownership
  WHERE contest_id IN ('193028206','195648007','195905122')
  GROUP BY 1,2
), e AS (
  SELECT week, contest_id, entry_id, rank, points, players_key,
         REGEXP_REPLACE(entry_name, r'\s*\(\d+/\d+\)\s*$', '') AS user,
         COUNT(*) OVER (PARTITION BY contest_id) AS n_field
  FROM nfl_raw.contest_entries
  WHERE contest_id IN ('193028206','195648007','195905122')
), dup AS (
  SELECT contest_id, players_key, COUNT(*) AS n_same FROM e GROUP BY 1,2
), r AS (
  SELECT e.week, e.user, e.entry_id, e.rank, e.points, e.n_field, d.n_same,
         SUM(o.own) AS own_sum, COUNTIF(o.own < 5) AS n_sub5, COUNTIF(o.own >= 20) AS n_chalk,
         MAX(o.own) AS max_own, COUNTIF(o.own IS NULL) AS n_unmatched
  FROM e JOIN dup d USING (contest_id, players_key), UNNEST(SPLIT(e.players_key, '|')) AS p
  LEFT JOIN own o ON o.contest_id = e.contest_id AND o.display_name = p
  GROUP BY 1,2,3,4,5,6,7
)
SELECT week, user, COUNT(*) AS n,
       ROUND(AVG(rank / n_field * 100), 3) AS mean_pct,
       MIN(rank) AS best_rank, ROUND(MIN(rank / n_field * 100), 4) AS best_pct,
       ROUND(AVG(points), 2) AS mean_pts, ROUND(MAX(points), 2) AS max_pts,
       COUNTIF(rank <= 100) AS n_top100, COUNTIF(rank <= 10) AS n_top10,
       COUNTIF(rank <= n_field * 0.01) AS n_top1pct,
       COUNTIF(rank <= n_field * 0.2) AS n_top20pct,
       ROUND(AVG(own_sum), 2) AS own_sum, ROUND(AVG(n_sub5), 3) AS n_sub5, ROUND(AVG(n_chalk), 3) AS n_chalk,
       ROUND(AVG(max_own), 2) AS max_own, SUM(n_unmatched) AS n_unmatched,
       COUNTIF(n_same = 1) AS n_unique_in_field
FROM r GROUP BY 1,2
