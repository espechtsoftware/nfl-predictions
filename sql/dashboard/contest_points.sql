-- Standings points for the week's detailed contests (the publisher's cash
-- lines: the score at each contest's last paid rank).
SELECT x.contest_id, x.points
FROM `${raw}.contest_entries` x
WHERE x.season = ${season} AND x.week = ${week} AND x.contest_id IN (${contest_ids})
QUALIFY ROW_NUMBER() OVER (PARTITION BY x.contest_id, x.entry_id ORDER BY x.imported_at DESC) = 1
