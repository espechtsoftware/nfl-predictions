${inc:norm_fn}
-- Realized Millionaire ownership counted from the contest's own lineups
-- (book_vs_field_scoreboard.field_ownership_sql: the printed %Drafted rows
-- omit a player's second slot row), with the player's DK points, resolved to
-- the slate's DraftKings id and team by normalised name (names two slate
-- players share stay unresolved: dk_player_id and team NULL).
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
),
slate AS (
  SELECT contest_id, k, ANY_VALUE(team) AS team, ANY_VALUE(dk_player_id) AS dk_player_id
  FROM (
    SELECT m.contest_id, norm(d.display_name) AS k, team_code(d.team_abbr) AS team, d.dk_player_id
    FROM `${raw}.dk_salaries` d
    JOIN m ON d.draft_group_id = m.draft_group_id
    WHERE m.season = ${season} ${week_filter_m} AND d.slate_type = 'classic'
      AND (m.start_time IS NULL OR d.pulled_at < m.start_time)
    QUALIFY d.pulled_at = MAX(d.pulled_at) OVER (PARTITION BY m.contest_id)
  ) AS s
  GROUP BY 1, 2
  HAVING COUNT(DISTINCT s.dk_player_id) = 1   -- a shared normalised name is dropped, never merged
)
SELECT o.season, o.week, o.contest_id, o.display_name, o.own, pts.fpts,
       slate.team, slate.dk_player_id
FROM o
LEFT JOIN pts USING (contest_id, display_name)
LEFT JOIN slate ON slate.contest_id = o.contest_id AND slate.k = norm(o.display_name)
ORDER BY o.week, o.own DESC
