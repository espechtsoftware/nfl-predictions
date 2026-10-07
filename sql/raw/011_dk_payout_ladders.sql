-- P1 (the approved plan 2026-10-04, reports/2026-10-04-agent-proposed-studies.md; the operator's Wed 10-07 directive):
-- DraftKings payout ladders, one row per payout tier, loaded by scripts/load_payout_ladders.py from the public
-- contest-details captures (the full payoutSummary per contest). dk_contest_fills.payout_metadata_json is the lobby's
-- one-line prize summary (one entry for the Millionaire) and cannot give a ladder.
-- Append-only: a re-capture with new content adds rows under its own source_sha256; the views read the latest capture
-- per contest. Dollar values live here and in the views only; tracked files report multiples of the fee.
CREATE TABLE IF NOT EXISTS `${raw}.dk_payout_ladders` (
  loaded_at TIMESTAMP,
  season INT64,
  week INT64,
  contest_id STRING,            -- as contest_entries.contest_id
  contest_name STRING,
  draft_group_id INT64,
  entry_fee FLOAT64,
  max_entries INT64,            -- the field's capacity
  max_entries_per_user INT64,
  entries_at_capture INT64,
  contest_start TIMESTAMP,
  tier INT64,                   -- 1 = the best-paid positions; tiers run 1, 2, ... in position order, no gap or overlap
  min_position INT64,
  max_position INT64,
  cash_value FLOAT64,           -- per position in the tier (a tier pays cash OR a ticket, never both)
  ticket_value FLOAT64,         -- per position: DraftKings' stated value of the tier's ticket(s)
  ticket_description STRING,
  source_file STRING,
  source_sha256 STRING,         -- the capture's content identity (the loader refuses a sha already loaded)
  captured_at TIMESTAMP
)
PARTITION BY DATE(loaded_at)
CLUSTER BY season, week, contest_id;

-- The latest capture per contest (by captured_at, then loaded_at).
CREATE OR REPLACE VIEW `${raw}.v_dk_payout_ladder_latest` AS
SELECT l.* FROM `${raw}.dk_payout_ladders` l
JOIN (SELECT contest_id, ARRAY_AGG(source_sha256 ORDER BY captured_at DESC, loaded_at DESC LIMIT 1)[OFFSET(0)] AS sha
      FROM `${raw}.dk_payout_ladders` GROUP BY contest_id) k
  ON k.contest_id = l.contest_id AND k.sha = l.source_sha256;

-- Per contest, in multiples of the fee: positions paid and their share of the field, the pool ratio (paid / fees at
-- capacity), the first and min-cash multiples, the payout kind and, for a flat ladder (every paid position equal: the
-- satellites and supersats), the break-even rate as a multiple of the field's paid rate (1 / the pool ratio).
CREATE OR REPLACE VIEW `${raw}.v_dk_payout_structure` AS
SELECT season, week, contest_id, ANY_VALUE(contest_name) AS contest_name, ANY_VALUE(entry_fee) AS entry_fee,
       ANY_VALUE(max_entries) AS max_entries, MAX(max_position) AS paid_positions,
       SAFE_DIVIDE(MAX(max_position), ANY_VALUE(max_entries)) AS paid_share,
       SAFE_DIVIDE(SUM((max_position - min_position + 1) * (cash_value + ticket_value)),
                   ANY_VALUE(entry_fee) * ANY_VALUE(max_entries)) AS pool_ratio,
       SAFE_DIVIDE(MAX(IF(tier = 1, cash_value + ticket_value, NULL)), ANY_VALUE(entry_fee)) AS first_multiple,
       SAFE_DIVIDE(ARRAY_AGG(cash_value + ticket_value ORDER BY tier DESC LIMIT 1)[OFFSET(0)], ANY_VALUE(entry_fee)) AS min_cash_multiple,
       CASE WHEN LOGICAL_AND(ticket_value > 0) THEN 'ticket' WHEN LOGICAL_AND(cash_value > 0) THEN 'cash' ELSE 'mixed' END AS kind,
       IF(COUNT(DISTINCT cash_value + ticket_value) = 1,
          SAFE_DIVIDE(ANY_VALUE(entry_fee) * ANY_VALUE(max_entries),
                      SUM((max_position - min_position + 1) * (cash_value + ticket_value))), NULL) AS break_even_x_field_rate
FROM `${raw}.v_dk_payout_ladder_latest`
GROUP BY season, week, contest_id;

-- rank -> tier: each settled entry of the contest's LATEST import (2026 W1-4: one post-settlement import per contest, one
-- rank per entry), with n_tied (the entries sharing its reported rank) and two payouts in multiples of the fee:
--   payout_multiple       the tier at the REPORTED rank (0 out of the money). It ignores ties, so it OVERSTATES the paid
--                         entries at every tier boundary (79 extra on the W1 Millionaire): never use it for money;
--   split_payout_multiple DraftKings' rule: the prizes of positions rank .. rank + n_tied - 1 pooled and split equally
--                         (positions past the last tier pay 0, so a tie across the cash line gets its partial share).
--                         USE THIS ONE for realized payouts (scripts/load_payout_ladders.split_payout_multiple is the
--                         tested reference; the reviewer, 10-07).
-- tier / cash_value / ticket_value describe the reported rank's tier (NULL out of the money); both payouts are NULL for a
-- contest without a loaded ladder.
CREATE OR REPLACE VIEW `${raw}.v_dk_entry_tier` AS
WITH e AS (
  SELECT DISTINCT c.season, c.week, c.contest_id, c.entry_id, c.rank
  FROM `${raw}.contest_entries` c
  JOIN (SELECT contest_id, ARRAY_AGG(import_id ORDER BY imported_at DESC LIMIT 1)[OFFSET(0)] AS import_id
        FROM `${raw}.contest_entries` GROUP BY contest_id) k
    ON k.contest_id = c.contest_id AND k.import_id = c.import_id),
t AS (SELECT e.*, COUNT(*) OVER (PARTITION BY contest_id, rank) AS n_tied FROM e),
f AS (SELECT contest_id, ANY_VALUE(entry_fee) AS entry_fee FROM `${raw}.v_dk_payout_ladder_latest` GROUP BY contest_id)
SELECT t.season, t.week, t.contest_id, t.entry_id, t.rank, t.n_tied,
       MAX(IF(t.rank BETWEEN l.min_position AND l.max_position, l.tier, NULL)) AS tier,
       MAX(IF(t.rank BETWEEN l.min_position AND l.max_position, l.cash_value, NULL)) AS cash_value,
       MAX(IF(t.rank BETWEEN l.min_position AND l.max_position, l.ticket_value, NULL)) AS ticket_value,
       IF(ANY_VALUE(f.entry_fee) IS NULL, NULL,
          IFNULL(MAX(IF(t.rank BETWEEN l.min_position AND l.max_position, l.cash_value + l.ticket_value, NULL)), 0)
            / ANY_VALUE(f.entry_fee)) AS payout_multiple,
       IF(ANY_VALUE(f.entry_fee) IS NULL, NULL,
          IFNULL(SUM(GREATEST(0, LEAST(l.max_position, t.rank + t.n_tied - 1) - GREATEST(l.min_position, t.rank) + 1)
                     * (l.cash_value + l.ticket_value)), 0) / (t.n_tied * ANY_VALUE(f.entry_fee))) AS split_payout_multiple
FROM t
LEFT JOIN f ON f.contest_id = t.contest_id
LEFT JOIN `${raw}.v_dk_payout_ladder_latest` l
  ON l.contest_id = t.contest_id AND l.min_position <= t.rank + t.n_tied - 1 AND l.max_position >= t.rank
GROUP BY t.season, t.week, t.contest_id, t.entry_id, t.rank, t.n_tied;
