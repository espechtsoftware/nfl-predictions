-- The newest published run's pool/book exposure per week (by publication
-- time, so a run without a receipt -- built_utc NULL -- is still visible).
SELECT * FROM `${dashboard}.pool_exposure` AS pool_exposure
WHERE season = ${season} ${week_filter}
QUALIFY published_utc = MAX(published_utc) OVER (PARTITION BY week)
