-- EVERY Millionaire lineup of the listed users (operator 10-06: "look closely at how the winners do it ... is their
-- pool better only because of their volume?"): users are chosen by the caller (by entry count, never by results), and
-- ALL of their lineups are returned, in milly_top_lineups' columns so the graph loader treats them alike. `dupes`,
-- `rank` and `n_entries` are computed over the whole field before the user filter. The users array is a validated
-- array literal (data.fetch_milly_user_lineups refuses any name outside [A-Za-z0-9_.-]).
WITH m AS (${milly_contests}),
e AS (
  SELECT m.season, m.week, m.contest_id, x.entry_id, x.rank,
         x.points, x.payout, x.lineup_slots_json, x.players_key,
         REGEXP_REPLACE(TRIM(x.entry_name), r'\s*\(\d+/\d+\)$', '') AS username
  FROM `${raw}.contest_entries` x
  JOIN m ON x.season = m.season AND x.week = m.week AND x.contest_id = m.contest_id
  WHERE x.season = ${season} ${week_filter}
  QUALIFY ROW_NUMBER() OVER (PARTITION BY x.contest_id, x.entry_id
                             ORDER BY x.imported_at DESC) = 1
),
d AS (
  SELECT *,
         COUNT(*) OVER (PARTITION BY contest_id, players_key) AS dupes,
         ROW_NUMBER() OVER (PARTITION BY contest_id ORDER BY points DESC, rank, entry_id) AS pos,
         RANK() OVER (PARTITION BY contest_id ORDER BY points DESC) AS rk,
         COUNT(*) OVER (PARTITION BY contest_id) AS n,
         MIN(IF(payout > 0, points, NULL)) OVER (PARTITION BY contest_id) AS cash_line
  FROM e
),
c AS (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY contest_id, points = cash_line ORDER BY entry_id) AS cash_pos
  FROM d
)
SELECT
  season, week, contest_id,
  TO_HEX(SHA256(CONCAT(contest_id, ':', entry_id))) AS lineup_key,
  COALESCE(rank, pos) AS rank, points, lineup_slots_json, dupes, n AS n_entries, username,
  COALESCE(points = cash_line, FALSE) AS at_cash_line
FROM c
WHERE username IN UNNEST(${users_array})
ORDER BY season, week, username, pos
