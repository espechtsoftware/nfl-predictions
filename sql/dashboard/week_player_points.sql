-- DK points per player as the week's contest standings printed them
-- (covers DSTs and everyone drafted anywhere that week).
SELECT display_name, MAX(fpts) AS fpts
FROM `${raw}.contest_ownership`
WHERE season = ${season} AND week = ${week}
GROUP BY 1
