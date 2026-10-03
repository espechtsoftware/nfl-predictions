-- Teams on a draft group (the Millionaire's main slate), newest pull.
SELECT DISTINCT team_abbr
FROM `${raw}.dk_salaries`
WHERE draft_group_id = ${draft_group}
  AND pulled_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 400 DAY)
QUALIFY pulled_at = MAX(pulled_at) OVER ()
