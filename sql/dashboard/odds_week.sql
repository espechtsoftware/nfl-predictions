-- Total and spread snapshots for games kicking off in [${start}, ${end}),
-- pulled no earlier than ${pulled_from}. start_time is an ISO 'Z' string.
SELECT pulled_at, event_id, event_name, start_time, market_type, selection,
       line, odds_american
FROM `${raw}.odds_snapshots`
WHERE start_time >= '${start}' AND start_time < '${end}'
  AND pulled_at >= TIMESTAMP('${pulled_from}')
  AND market_type IN ('Total', 'Spread')
