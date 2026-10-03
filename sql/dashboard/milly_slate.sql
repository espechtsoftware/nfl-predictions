-- The Millionaire's player pool: the draft group's last salary pull before
-- the contest starts (team, roster position, salary), keyed by the DraftKings
-- display name the standings print.
WITH m AS (${milly_contests}),
s AS (
  SELECT m.season, m.week, m.contest_id, d.display_name, d.team_abbr,
         d.position, d.salary, d.pulled_at
  FROM `${raw}.dk_salaries` d
  JOIN m ON d.draft_group_id = m.draft_group_id
  WHERE m.season = ${season} ${week_filter_m}
    AND d.slate_type = 'classic'
    AND (m.start_time IS NULL OR d.pulled_at < m.start_time)
  QUALIFY d.pulled_at = MAX(d.pulled_at) OVER (PARTITION BY m.contest_id)
)
SELECT season, week, contest_id, display_name,
       ANY_VALUE(team_abbr) AS team,
       ANY_VALUE(SPLIT(position, '/')[OFFSET(0)]) AS position,
       MAX(salary) AS salary
FROM s
GROUP BY 1, 2, 3, 4
