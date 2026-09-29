-- F5: winning lineups (top 1 of W1/W2, top 10 of W3) with per-player realized points + Millionaire ownership
WITH own AS (
  SELECT contest_id, display_name, SUM(pct_drafted) AS own, MAX(fpts) AS fpts, STRING_AGG(DISTINCT roster_position ORDER BY roster_position) AS pos
  FROM nfl_raw.contest_ownership WHERE contest_id IN ('193028206','195648007','195905122') GROUP BY 1,2
), e AS (
  SELECT week, contest_id, rank, REGEXP_REPLACE(entry_name, r'\s*\(\d+/\d+\)\s*$', '') AS user,
         REGEXP_EXTRACT(entry_name, r'\((\d+)/(\d+)\)') AS entry_k, REGEXP_EXTRACT(entry_name, r'/(\d+)\)') AS entry_n,
         points, lineup_slots_json, players_key
  FROM nfl_raw.contest_entries
  WHERE (contest_id IN ('193028206','195648007') AND rank = 1) OR (contest_id = '195905122' AND rank <= 10)
)
SELECT e.week, e.rank, e.user, e.entry_n, e.points, s.slot, s.player, o.pos, o.own, o.fpts
FROM e, UNNEST(JSON_EXTRACT_ARRAY(e.lineup_slots_json)) AS j
CROSS JOIN UNNEST([STRUCT(JSON_VALUE(j, '$.slot') AS slot, JSON_VALUE(j, '$.player') AS player)]) AS s
LEFT JOIN own o ON o.contest_id = e.contest_id AND o.display_name = s.player
ORDER BY e.week, e.rank, o.fpts DESC
