-- Line movement (2026-08-01): first-vs-latest snapshot per market line
-- from odds_snapshots (collecting 2x/day Wed-Sun since the odds-source
-- fix). "Late movement contains information" is the queued in-season
-- study; this view is its substrate and feeds the app's Market page now.
CREATE OR REPLACE VIEW `${raw}.odds_movement` AS
WITH ranked AS (
  SELECT
    event_name, market_type, selection, start_time,
    line, odds_american, pulled_at,
    ROW_NUMBER() OVER (PARTITION BY event_id, market_type, selection
                       ORDER BY pulled_at) AS rn_first,
    ROW_NUMBER() OVER (PARTITION BY event_id, market_type, selection
                       ORDER BY pulled_at DESC) AS rn_last
  FROM `${raw}.odds_snapshots`
)
SELECT
  f.event_name, f.market_type, f.selection, f.start_time,
  f.line AS open_line, l.line AS latest_line,
  l.line - f.line AS line_move,
  f.odds_american AS open_odds, l.odds_american AS latest_odds,
  f.pulled_at AS first_seen, l.pulled_at AS last_seen
FROM (SELECT * FROM ranked WHERE rn_first = 1) f
JOIN (SELECT * FROM ranked WHERE rn_last = 1) l
  USING (event_name, market_type, selection);
