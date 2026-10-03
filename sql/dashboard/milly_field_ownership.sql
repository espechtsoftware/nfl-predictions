-- Realized Millionaire ownership counted from the contest's own lineups
-- (book_vs_field_scoreboard.field_ownership_sql: the printed %Drafted rows
-- omit a player's second slot row), with the player's DK points.
WITH m AS (${milly_contests}),
e AS (
  SELECT m.season, m.week, m.contest_id, x.entry_id, x.lineup_slots_json
  FROM `${raw}.contest_entries` x
  JOIN m ON x.season = m.season AND x.week = m.week AND x.contest_id = m.contest_id
  WHERE x.season = ${season} ${week_filter}
  QUALIFY ROW_NUMBER() OVER (PARTITION BY x.contest_id, x.entry_id
                             ORDER BY x.imported_at DESC) = 1
),
n AS (SELECT contest_id, COUNT(*) AS n FROM e GROUP BY 1),
o AS (
  SELECT e.season, e.week, e.contest_id, JSON_VALUE(it, '$.player') AS display_name,
         100.0 * COUNT(DISTINCT e.entry_id) / ANY_VALUE(n.n) AS own
  FROM e JOIN n USING (contest_id), UNNEST(JSON_QUERY_ARRAY(e.lineup_slots_json)) it
  GROUP BY 1, 2, 3, 4
),
pts AS (
  SELECT contest_id, display_name, MAX(fpts) AS fpts
  FROM `${raw}.contest_ownership`
  WHERE season = ${season}
  GROUP BY 1, 2
)
SELECT o.season, o.week, o.contest_id, o.display_name, o.own, pts.fpts
FROM o LEFT JOIN pts USING (contest_id, display_name)
ORDER BY o.week, o.own DESC
