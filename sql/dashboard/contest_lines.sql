-- The newest published cash lines per week (scripts/publish_dashboard_week.py).
SELECT * FROM `${dashboard}.contest_lines`
WHERE season = ${season}
QUALIFY published_utc = MAX(published_utc) OVER (PARTITION BY week)
