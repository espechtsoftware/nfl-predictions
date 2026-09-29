-- Our rows in the three Millionaires, identified from the W3 seat (rank 79343, players known from our_book.pkl)
WITH u AS (
  SELECT DISTINCT REGEXP_REPLACE(entry_name, r'\s*\(\d+/\d+\)\s*$', '') AS user
  FROM nfl_raw.contest_entries
  WHERE contest_id='195905122' AND rank=79343
    AND players_key LIKE '%Trevor Lawrence%' AND players_key LIKE '%Brenton Strange%' AND players_key LIKE '%Bengals%'
)
SELECT e.week, e.contest_id, e.rank, e.entry_name, e.points, e.players_key,
       COUNT(*) OVER (PARTITION BY e.contest_id) AS n_ours
FROM nfl_raw.contest_entries e JOIN u ON REGEXP_REPLACE(e.entry_name, r'\s*\(\d+/\d+\)\s*$', '') = u.user
WHERE e.contest_id IN ('193028206','195648007','195905122')
ORDER BY week, rank
