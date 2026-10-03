-- The newest publication of each week's arms.
SELECT * FROM `${dashboard}.arms_weekly`
WHERE season = ${season}
QUALIFY published_utc = MAX(published_utc) OVER (PARTITION BY week)
ORDER BY week, kind, arm
