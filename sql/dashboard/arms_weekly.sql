-- Each week's arms from one publication: the newest SCORED publication when
-- there is one (a later unscored publish never hides scored rows), else the
-- newest.
WITH a AS (
  SELECT *,
         LOGICAL_OR(mean_points IS NOT NULL) OVER (PARTITION BY week, published_utc) AS scored
  FROM `${dashboard}.arms_weekly`
  WHERE season = ${season}
)
SELECT * EXCEPT (scored)
FROM a
QUALIFY DENSE_RANK() OVER (PARTITION BY week ORDER BY scored DESC, published_utc DESC) = 1
ORDER BY week, kind, arm
