-- The newest published run's pool/book exposure per week.
SELECT * FROM `${dashboard}.pool_exposure`
WHERE season = ${season} ${week_filter}
QUALIFY built_utc = MAX(built_utc) OVER (PARTITION BY week)
