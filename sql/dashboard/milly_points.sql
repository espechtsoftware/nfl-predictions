-- Every entry's points (and payout, usually NULL) in the week's Millionaire:
-- the field our arms are ranked against.
WITH m AS (${milly_contests})
SELECT x.points, x.payout
FROM `${raw}.contest_entries` x
JOIN m ON x.season = m.season AND x.week = m.week AND x.contest_id = m.contest_id
WHERE x.season = ${season} AND x.week = ${week}
QUALIFY ROW_NUMBER() OVER (PARTITION BY x.contest_id, x.entry_id ORDER BY x.imported_at DESC) = 1
