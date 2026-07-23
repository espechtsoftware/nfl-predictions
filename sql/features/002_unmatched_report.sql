-- Players in the current pool with no GSIS mapping. This list should be
-- reviewed weekly and drained into player_id_overrides. Expect 10-30 manual
-- entries per season, mostly rookies and practice-squad call-ups.
CREATE OR REPLACE VIEW `${features}.unmatched_dk_players` AS
WITH latest_pull AS (
  SELECT MAX(pulled_at) AS ts FROM `${raw}.dk_salaries`
)
SELECT DISTINCT s.dk_player_id, s.display_name, s.team_abbr, s.position, s.salary
FROM `${raw}.dk_salaries` s, latest_pull
WHERE s.pulled_at = latest_pull.ts
  AND s.dk_player_id NOT IN (SELECT dk_player_id FROM `${features}.player_id_map`)
ORDER BY s.salary DESC;
