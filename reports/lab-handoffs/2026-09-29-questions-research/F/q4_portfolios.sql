-- F2: every entry of (a) user-weeks with >=20 entries and a top-100 finish, (b) a mid-field pool (>=20 entries, mean pct 35-65) for matching
WITH e AS (
  SELECT week, contest_id, entry_id, rank, points, players_key, lineup_slots_json,
         REGEXP_REPLACE(entry_name, r'\s*\(\d+/\d+\)\s*$', '') AS user,
         COUNT(*) OVER (PARTITION BY contest_id) AS n_field
  FROM nfl_raw.contest_entries WHERE contest_id IN ('193028206','195648007','195905122')
), dup AS (SELECT contest_id, players_key, COUNT(*) AS n_same FROM e GROUP BY 1,2),
uw AS (
  SELECT week, user, COUNT(*) AS n, AVG(rank / n_field * 100) AS mean_pct, MIN(rank) AS best_rank
  FROM e GROUP BY 1,2 HAVING n >= 20
), sel AS (
  SELECT week, user, 'top100' AS grp FROM uw WHERE best_rank <= 100
  UNION ALL
  SELECT week, user, 'mid' AS grp FROM uw WHERE mean_pct BETWEEN 35 AND 65 AND best_rank > 1000
  QUALIFY grp = 'top100' OR ROW_NUMBER() OVER (PARTITION BY week, grp ORDER BY FARM_FINGERPRINT(user)) <= 600
)
SELECT e.week, s.grp, e.user, e.rank, e.points, d.n_same,
       (SELECT STRING_AGG(CONCAT(JSON_VALUE(j,'$.slot'), '=', JSON_VALUE(j,'$.player')), '|' ORDER BY off)
        FROM UNNEST(JSON_EXTRACT_ARRAY(e.lineup_slots_json)) AS j WITH OFFSET off) AS lineup
FROM e JOIN sel s USING (week, user) JOIN dup d USING (contest_id, players_key)
ORDER BY week, grp, user, rank
