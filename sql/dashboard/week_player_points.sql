-- DK points per player as the week's Millionaire standings printed them
-- (covers DSTs). Only the Millionaire: other contests that week include
-- showdowns, whose captain rows carry 1.5x points.
WITH m AS (${milly_contests})
SELECT o.display_name, MAX(o.fpts) AS fpts
FROM `${raw}.contest_ownership` o
JOIN m ON m.season = o.season AND m.week = o.week AND m.contest_id = o.contest_id
WHERE o.season = ${season} AND o.week = ${week}
GROUP BY 1
